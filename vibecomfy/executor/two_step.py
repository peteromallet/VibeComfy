"""Two-step pipeline mode entrypoint seam (B01) + route policy (B02).

B01 defines the typed entrypoint, re-resolves the pipeline mode, and routes
through a test-injectable outcome boundary so orchestration tests can prove
the dispatch toggle without model calls.  Real execution lands in B03–B04.

B02 (Flash scope) adds the frozen route-policy table and per-message budget
types: :data:`TWO_STEP_ROUTE_POLICIES` (the authoritative two-step route
table), :data:`PER_TOOL_CALL_CAPS`, the catalog builders
(:func:`effective_route_tools` / :func:`route_catalog_docs`), the per-message
budget primitives (:class:`MessageBudget` / :class:`BudgetUsage` /
:func:`check_before_tool_call` / :func:`consume_tool_call` /
:func:`consume_output_tokens` / ...), and the frozen session type
(:class:`SessionBudget`) that the B03 session authority / cumulative-budget
plumbing wires in.  Session persistence and cumulative enforcement are NOT
implemented here — this module provides immutable policy/type definitions and
the per-message enforcement primitives only.

B05 (Flash scope) wires the two-step profile ``execute`` resolution (typed
``MissingProfileStageError``, never a fallback to ``implement``), the
``phase="execute"`` lifecycle events (start/working/done/error), the single
``phase="execute"`` profiler span with the execute budget counters, and the
``report.executor.execute`` section.

The full-mode route authority (``core._ROUTE_BEHAVIORS``) is never moved or
duplicated: :func:`assert_route_policy_coverage` imports it lazily and asserts
exact route-set coverage.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecuteReport,
    ExecutorRequest,
    ExecutorResult,
    PipelineMode,
    Report,
)
from vibecomfy.executor.profiler import (
    ProfilerSpan,
    profiler_log,
    profiler_span,
    short_text,
)

LOGGER = logging.getLogger(__name__)


# ── B02: budget families ─────────────────────────────────────────────────────
#
# Every typed exhaustion/denial carries one canonical ``family`` so callers
# (and the B03 session authority) can distinguish the budget that was hit
# without string-matching messages.


BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST = "route_tool_allowlist"
BUDGET_FAMILY_ROUTE_TOOL_CALLS = "route_tool_calls"
BUDGET_FAMILY_PER_TOOL_CALLS = "per_tool_calls"
BUDGET_FAMILY_OUTPUT_TOKENS = "output_tokens"
BUDGET_FAMILY_WALL_CLOCK = "wall_clock"
BUDGET_FAMILY_APPLY_BATCHES = "apply_batches"
BUDGET_FAMILY_REPLACEMENT_ATTEMPTS = "replacement_attempts"
BUDGET_FAMILY_SESSION_OUTPUT_TOKENS = "session_output_tokens"
BUDGET_FAMILY_SESSION_MODEL_CONTINUATIONS = "session_model_continuations"
BUDGET_FAMILY_SESSION_TOOL_CALLS = "session_tool_calls"
BUDGET_FAMILY_SESSION_WALL_CLOCK = "session_wall_clock"
BUDGET_FAMILY_SESSION_APPLY_BATCHES = "session_apply_batches"
BUDGET_FAMILY_SESSION_REPLACEMENT_ATTEMPTS = "session_replacement_attempts"
BUDGET_FAMILY_SESSION_USER_MESSAGES = "session_user_messages"


class BudgetExceeded(Exception):
    """Typed budget-exhaustion / denial signal (B02, Flash scope).

    Raised BEFORE a denied or over-budget operation is dispatched — never
    after the fact, and never as a side effect of mutation (all budget state
    is immutable; a breach consumes nothing).  Carries the exhausted budget
    ``family``, the ceiling (``limit``), the usage at the breach (``used``),
    the owning ``route`` when known, and an optional human-readable
    ``detail``.
    """

    def __init__(
        self,
        *,
        family: str,
        limit: int | float,
        used: int | float,
        route: str | None = None,
        detail: str = "",
    ) -> None:
        super().__init__(detail or f"{family}: used {used} of limit {limit}")
        self.family = family
        self.limit = limit
        self.used = used
        self.route = route
        self.detail = detail


# ── B02: per-tool call caps (frozen, authoritative) ──────────────────────────
#
# Exact per-tool per-message call caps (tasklist B02 #3).  These apply to every
# route that admits the tool; the route's aggregate ``max_tool_calls`` is the
# second, independent gate.  ``web_search`` is capped at 1 AND denied unless
# policy explicitly enables it (see :func:`effective_route_tools`).

PER_TOOL_CALL_CAPS: Mapping[str, int] = MappingProxyType(
    {
        "hivemind_search": 3,
        "hivemind_get": 4,
        "registry_lookup": 2,
        "node_schema": 4,
        "ready_template_list": 2,
        "ready_template_load": 2,
        "rank_edit_targets": 2,
        "suggest_seed_nodes": 2,
        "layout_hints": 2,
        "web_search": 1,
    }
)


# ── B02: route policy table (frozen, authoritative) ──────────────────────────
#
# ``allowed_tools`` lists only REGISTERED agent tools (the ten
# ``tool_specs.TOOL_SPECS`` names).  The Python edit capability is not a
# registered tool: edit routes flag it via ``allows_python_edits`` and carry
# per-message apply/replacement counters (at most one of each per message;
# session ceilings live on :class:`SessionBudget`).


@dataclass(frozen=True)
class TwoStepRoutePolicy:
    """One two-step route's per-message budget slice and tool allowlist (B02).

    Frozen by contract: the route table is authoritative and immutable.  A
    route's registered-tool allowlist is ``allowed_tools`` (the "effective"
    set additionally drops ``web_search`` unless policy enables it — see
    :func:`effective_route_tools`); ``allows_python_edits`` marks the routes
    whose agent may submit Python edit statements (apply/replacement), with
    per-message ``max_apply_batches`` / ``max_replacements`` counters.
    """

    route: str
    allowed_tools: frozenset[str]
    max_output_tokens: int
    max_tool_calls: int
    max_wall_clock_seconds: float
    allows_python_edits: bool = False
    max_apply_batches: int = 0
    max_replacements: int = 0

    def __post_init__(self) -> None:
        if not self.route:
            raise ValueError("TwoStepRoutePolicy requires a non-empty route name.")
        if self.max_output_tokens <= 0:
            raise ValueError(f"Route {self.route!r}: max_output_tokens must be positive.")
        if self.max_tool_calls < 0:
            raise ValueError(f"Route {self.route!r}: max_tool_calls must be >= 0.")
        if self.max_wall_clock_seconds <= 0:
            raise ValueError(f"Route {self.route!r}: max_wall_clock_seconds must be positive.")
        if self.max_apply_batches < 0 or self.max_replacements < 0:
            raise ValueError(f"Route {self.route!r}: apply/replacement caps must be >= 0.")
        # The Python edit capability and the apply/replacement counters travel
        # together: an edit route admits apply/replacement (at most one of each
        # per message), a non-edit route admits neither.
        if self.allows_python_edits != (
            self.max_apply_batches > 0 or self.max_replacements > 0
        ):
            raise ValueError(
                f"Route {self.route!r}: allows_python_edits must agree with the "
                "apply/replacement counters."
            )


def _policy(
    *,
    route: str,
    allowed_tools: frozenset[str],
    max_output_tokens: int,
    max_tool_calls: int,
    max_wall_clock_seconds: float,
    allows_python_edits: bool = False,
    max_apply_batches: int = 0,
    max_replacements: int = 0,
) -> TwoStepRoutePolicy:
    return TwoStepRoutePolicy(
        route=route,
        allowed_tools=allowed_tools,
        max_output_tokens=max_output_tokens,
        max_tool_calls=max_tool_calls,
        max_wall_clock_seconds=max_wall_clock_seconds,
        allows_python_edits=allows_python_edits,
        max_apply_batches=max_apply_batches,
        max_replacements=max_replacements,
    )


# The authoritative two-step route table (tasklist B02 #2).  "Python" in the
# tasklist means the Python edit capability (``allows_python_edits``), not a
# registered tool.  ``web_search`` appears only where the table says
# "policy-enabled web" (research, adapt) and is denied unless explicitly
# enabled — no production owner enables it today.
TWO_STEP_ROUTE_POLICIES: Mapping[str, TwoStepRoutePolicy] = MappingProxyType(
    {
        "clarify": _policy(
            route="clarify",
            allowed_tools=frozenset(),
            max_output_tokens=2_000,
            max_tool_calls=0,
            max_wall_clock_seconds=30.0,
        ),
        "respond": _policy(
            route="respond",
            allowed_tools=frozenset(),
            max_output_tokens=2_000,
            max_tool_calls=0,
            max_wall_clock_seconds=30.0,
        ),
        "inspect": _policy(
            route="inspect",
            allowed_tools=frozenset({"node_schema"}),
            max_output_tokens=4_000,
            max_tool_calls=2,
            max_wall_clock_seconds=60.0,
        ),
        "research": _policy(
            route="research",
            allowed_tools=frozenset(
                {
                    "hivemind_search",
                    "hivemind_get",
                    "registry_lookup",
                    "node_schema",
                    "ready_template_list",
                    "ready_template_load",
                    "web_search",
                }
            ),
            max_output_tokens=8_000,
            max_tool_calls=8,
            max_wall_clock_seconds=180.0,
        ),
        "requires_custom_nodes": _policy(
            route="requires_custom_nodes",
            allowed_tools=frozenset({"registry_lookup", "node_schema"}),
            max_output_tokens=4_000,
            max_tool_calls=3,
            max_wall_clock_seconds=90.0,
        ),
        "revise": _policy(
            route="revise",
            allowed_tools=frozenset(
                {
                    "node_schema",
                    "ready_template_list",
                    "ready_template_load",
                    "rank_edit_targets",
                    "suggest_seed_nodes",
                    "layout_hints",
                }
            ),
            max_output_tokens=8_000,
            max_tool_calls=6,
            max_wall_clock_seconds=180.0,
            allows_python_edits=True,
            max_apply_batches=1,
            max_replacements=1,
        ),
        "adapt": _policy(
            route="adapt",
            allowed_tools=frozenset(
                {
                    "hivemind_search",
                    "hivemind_get",
                    "registry_lookup",
                    "web_search",
                    "node_schema",
                    "ready_template_list",
                    "ready_template_load",
                    "rank_edit_targets",
                    "suggest_seed_nodes",
                    "layout_hints",
                }
            ),
            max_output_tokens=12_000,
            max_tool_calls=8,
            max_wall_clock_seconds=240.0,
            allows_python_edits=True,
            max_apply_batches=1,
            max_replacements=1,
        ),
        "reorganise": _policy(
            route="reorganise",
            allowed_tools=frozenset({"layout_hints"}),
            max_output_tokens=6_000,
            max_tool_calls=2,
            max_wall_clock_seconds=120.0,
            allows_python_edits=True,
            max_apply_batches=1,
            max_replacements=1,
        ),
    }
)


def assert_route_policy_coverage() -> None:
    """Assert the two-step route table covers the full-mode route authority.

    Imports ``core._ROUTE_BEHAVIORS`` lazily — ``core`` imports this module
    during its own initialization, so a module-level import would observe the
    partially-initialized ``core`` (and fail whenever ``core`` is imported
    first).  The assertion therefore runs on every two-step execution
    (:func:`_run_two_step`) and directly from tests; the full-mode route
    authority is never moved or duplicated here.
    """
    from vibecomfy.executor.core import _ROUTE_BEHAVIORS  # lazy, full-mode authority
    from vibecomfy.executor.tool_specs import AGENT_TOOL_CALL_NAMES  # lazy registry

    if set(TWO_STEP_ROUTE_POLICIES) != set(_ROUTE_BEHAVIORS):
        raise ValueError(
            "TWO_STEP_ROUTE_POLICIES must cover every full-mode route exactly once: "
            f"missing={sorted(set(_ROUTE_BEHAVIORS) - set(TWO_STEP_ROUTE_POLICIES))}, "
            f"extra={sorted(set(TWO_STEP_ROUTE_POLICIES) - set(_ROUTE_BEHAVIORS))}."
        )
    if set(PER_TOOL_CALL_CAPS) != set(AGENT_TOOL_CALL_NAMES):
        raise ValueError(
            "PER_TOOL_CALL_CAPS must cover every registered agent tool exactly once: "
            f"missing={sorted(set(AGENT_TOOL_CALL_NAMES) - set(PER_TOOL_CALL_CAPS))}, "
            f"extra={sorted(set(PER_TOOL_CALL_CAPS) - set(AGENT_TOOL_CALL_NAMES))}."
        )
    for route, policy in TWO_STEP_ROUTE_POLICIES.items():
        unknown = set(policy.allowed_tools) - set(AGENT_TOOL_CALL_NAMES)
        if unknown:
            raise ValueError(
                f"Route {route!r} allowlist contains unregistered tools: {sorted(unknown)}."
            )


# ── B02: effective route tools + advertised catalogs ─────────────────────────


def effective_route_tools(
    route: str, *, web_search_enabled: bool = False
) -> frozenset[str]:
    """Registered tool names actually admitted on *route* for one message.

    ``web_search`` is denied unless *web_search_enabled* (existing policy only;
    no production owner enables it today) — it stays out of the effective set
    even when the route table lists it ("policy-enabled web").  Unknown routes
    are a typed :class:`ValueError`, never a silent empty allowlist.
    """
    try:
        policy = TWO_STEP_ROUTE_POLICIES[route]
    except KeyError:
        raise ValueError(f"Unknown two-step route {route!r}.") from None
    tools = set(policy.allowed_tools)
    if "web_search" in tools and not web_search_enabled:
        tools.remove("web_search")
    return frozenset(tools)


def route_catalog_docs(route: str, *, web_search_enabled: bool = False) -> str:
    """Prompt-doc catalog for *route*: exactly the route's effective tools.

    Built with ``tool_catalog_docs(phase=None, allowed_names=...)`` — never
    ``phase="research"``: ``node_schema`` and the template tools are
    implement-phase (tool_specs.py:760/771) and would be hidden by a research
    phase filter.  ``web_search`` is advertised only when policy enables it.
    """
    from vibecomfy.executor.tool_specs import tool_catalog_docs  # lazy

    return tool_catalog_docs(
        phase=None,
        allowed_names=effective_route_tools(
            route, web_search_enabled=web_search_enabled
        ),
    )


# ── B02: per-message budget types ────────────────────────────────────────────


@dataclass(frozen=True)
class MessageBudget:
    """Frozen per-message ceiling bundle for one route (B02, Flash scope).

    The route slice derived from :data:`TWO_STEP_ROUTE_POLICIES`: aggregate
    output-token slice, aggregate tool-call cap, wall-clock ceiling, the
    global per-tool caps, and the apply/replacement counters.  Consumption is
    tracked separately by :class:`BudgetUsage`; the ``check_*`` /
    ``consume_*`` helpers enforce these ceilings and raise
    :class:`BudgetExceeded`.
    """

    route: str
    max_output_tokens: int
    max_tool_calls: int
    max_wall_clock_seconds: float
    per_tool_caps: Mapping[str, int]
    max_apply_batches: int = 0
    max_replacements: int = 0

    @classmethod
    def for_route(cls, route: str) -> "MessageBudget":
        """Build the message budget for *route* from the authoritative table."""
        try:
            policy = TWO_STEP_ROUTE_POLICIES[route]
        except KeyError:
            raise ValueError(f"Unknown two-step route {route!r}.") from None
        return cls(
            route=policy.route,
            max_output_tokens=policy.max_output_tokens,
            max_tool_calls=policy.max_tool_calls,
            max_wall_clock_seconds=policy.max_wall_clock_seconds,
            per_tool_caps=PER_TOOL_CALL_CAPS,
            max_apply_batches=policy.max_apply_batches,
            max_replacements=policy.max_replacements,
        )


@dataclass(frozen=True)
class BudgetUsage:
    """Immutable per-message usage snapshot (B02, Flash scope).

    Every ``record_*`` helper returns a NEW instance; nothing mutates in
    place, so snapshots are safe to hand across the B03 session boundary.
    ``started_at`` is the monotonic clock at message start (overridable via
    :func:`dataclasses.replace` in tests); ``active_model_seconds``
    accumulates model/tool active time so the session accumulator can fold it
    into cumulative wall time.
    """

    route: str
    output_tokens: int = 0
    tool_call_counts: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    total_tool_calls: int = 0
    apply_batches: int = 0
    replacement_attempts: int = 0
    active_model_seconds: float = 0.0
    started_at: float = field(default_factory=time.monotonic)

    def record_output_tokens(self, tokens: int) -> "BudgetUsage":
        if tokens < 0:
            raise ValueError("tokens must be >= 0.")
        return replace(self, output_tokens=self.output_tokens + tokens)

    def record_tool_call(self, name: str) -> "BudgetUsage":
        counts = dict(self.tool_call_counts)
        counts[name] = counts.get(name, 0) + 1
        return replace(
            self,
            tool_call_counts=MappingProxyType(counts),
            total_tool_calls=self.total_tool_calls + 1,
        )

    def record_apply_batch(self) -> "BudgetUsage":
        return replace(self, apply_batches=self.apply_batches + 1)

    def record_replacement_attempt(self) -> "BudgetUsage":
        return replace(self, replacement_attempts=self.replacement_attempts + 1)

    def record_active_seconds(self, seconds: float) -> "BudgetUsage":
        if seconds < 0:
            raise ValueError("seconds must be >= 0.")
        return replace(self, active_model_seconds=self.active_model_seconds + seconds)


# ── B02: per-message enforcement helpers ─────────────────────────────────────
#
# Contract (tasklist B02 #6): a check runs BEFORE every model/tool call, and
# consumption is checked-and-recorded AFTER every model/tool call.  A breach
# raises :class:`BudgetExceeded`; a breach consumes nothing (all state is
# immutable, and the helpers check before recording).


def check_tool_allowed(
    budget: MessageBudget, tool: str, *, web_search_enabled: bool = False
) -> None:
    """Route-allowlist gate — denial BEFORE dispatch or budget consumption."""
    effective = effective_route_tools(
        budget.route, web_search_enabled=web_search_enabled
    )
    if tool not in effective:
        raise BudgetExceeded(
            family=BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST,
            limit=0,
            used=0,
            route=budget.route,
            detail=(
                f"tool {tool!r} is not on the {budget.route!r} route allowlist"
                f" (effective tools: {sorted(effective)})."
            ),
        )


def check_tool_call_caps(budget: MessageBudget, usage: BudgetUsage, tool: str) -> None:
    """Aggregate route tool-call cap and exact per-tool cap (B02)."""
    if usage.total_tool_calls >= budget.max_tool_calls:
        raise BudgetExceeded(
            family=BUDGET_FAMILY_ROUTE_TOOL_CALLS,
            limit=budget.max_tool_calls,
            used=usage.total_tool_calls,
            route=budget.route,
        )
    per_tool = budget.per_tool_caps.get(tool, 1)
    used_tool = usage.tool_call_counts.get(tool, 0)
    if used_tool >= per_tool:
        raise BudgetExceeded(
            family=BUDGET_FAMILY_PER_TOOL_CALLS,
            limit=per_tool,
            used=used_tool,
            route=budget.route,
            detail=f"tool {tool!r} per-message call cap ({per_tool}).",
        )


def check_output_tokens(budget: MessageBudget, usage: BudgetUsage, tokens: int) -> None:
    """Aggregate per-message output-token slice (B02)."""
    if tokens < 0:
        raise ValueError("tokens must be >= 0.")
    projected = usage.output_tokens + tokens
    if projected > budget.max_output_tokens:
        raise BudgetExceeded(
            family=BUDGET_FAMILY_OUTPUT_TOKENS,
            limit=budget.max_output_tokens,
            used=projected,
            route=budget.route,
        )


def check_wall_clock(
    budget: MessageBudget, usage: BudgetUsage, *, now: float | None = None
) -> None:
    """Per-message wall-clock ceiling from message start (B02).

    ``now`` is the monotonic clock (defaults to ``time.monotonic()``); tests
    inject a fake clock and/or ``replace(usage, started_at=...)``.
    """
    elapsed = (time.monotonic() if now is None else now) - usage.started_at
    if elapsed > budget.max_wall_clock_seconds:
        raise BudgetExceeded(
            family=BUDGET_FAMILY_WALL_CLOCK,
            limit=budget.max_wall_clock_seconds,
            used=elapsed,
            route=budget.route,
        )


def check_apply_batch(budget: MessageBudget, usage: BudgetUsage) -> None:
    """Per-message accepted-edit-batch counter (B02)."""
    if usage.apply_batches >= budget.max_apply_batches:
        raise BudgetExceeded(
            family=BUDGET_FAMILY_APPLY_BATCHES,
            limit=budget.max_apply_batches,
            used=usage.apply_batches,
            route=budget.route,
        )


def check_replacement_attempt(budget: MessageBudget, usage: BudgetUsage) -> None:
    """Per-message replacement-attempt counter — at most one per message (B02)."""
    if usage.replacement_attempts >= budget.max_replacements:
        raise BudgetExceeded(
            family=BUDGET_FAMILY_REPLACEMENT_ATTEMPTS,
            limit=budget.max_replacements,
            used=usage.replacement_attempts,
            route=budget.route,
        )


def check_before_tool_call(
    budget: MessageBudget,
    usage: BudgetUsage,
    tool: str,
    *,
    web_search_enabled: bool = False,
    now: float | None = None,
) -> None:
    """Run every pre-dispatch gate for one tool call (B02).

    Order is deliberate: allowlist denial first (before any budget
    consumption), then call caps, then wall clock.
    """
    check_tool_allowed(budget, tool, web_search_enabled=web_search_enabled)
    check_tool_call_caps(budget, usage, tool)
    check_wall_clock(budget, usage, now=now)


def check_before_model_call(
    budget: MessageBudget, usage: BudgetUsage, *, now: float | None = None
) -> None:
    """Pre-model-call gate: wall clock (output tokens are checked after)."""
    check_wall_clock(budget, usage, now=now)


def consume_tool_call(budget: MessageBudget, usage: BudgetUsage, tool: str) -> BudgetUsage:
    """Check-and-record one completed tool call; returns the new usage."""
    check_tool_call_caps(budget, usage, tool)
    return usage.record_tool_call(tool)


def consume_output_tokens(
    budget: MessageBudget, usage: BudgetUsage, tokens: int
) -> BudgetUsage:
    """Check-and-record *tokens* of model output; returns the new usage."""
    check_output_tokens(budget, usage, tokens)
    return usage.record_output_tokens(tokens)


def consume_apply_batch(budget: MessageBudget, usage: BudgetUsage) -> BudgetUsage:
    """Check-and-record one accepted edit batch; returns the new usage."""
    check_apply_batch(budget, usage)
    return usage.record_apply_batch()


def consume_replacement_attempt(
    budget: MessageBudget, usage: BudgetUsage
) -> BudgetUsage:
    """Check-and-record one replacement attempt; returns the new usage."""
    check_replacement_attempt(budget, usage)
    return usage.record_replacement_attempt()


# ── B02: session budget type (frozen; enforcement wiring lands in B03) ───────
#
# Frozen ceilings + cumulative usage counters for one two-step session.  This
# is the type the cumulative-session plumbing (B03 authority / provider
# output-cap path) wires in — nothing here persists state.  Every ``record_*``
# helper checks its ceiling and raises :class:`BudgetExceeded` on exhaustion;
# it never silently resets the session.

SESSION_BUDGET_CEILINGS: Mapping[str, int | float] = MappingProxyType(
    {
        "max_output_tokens": 48_000,
        "max_model_continuations": 64,
        "max_tool_calls": 64,
        "max_wall_clock_seconds": 1_800.0,
        "max_apply_batches": 12,
        "max_replacement_attempts": 12,
        "max_user_messages": 32,
    }
)


@dataclass(frozen=True)
class SessionBudget:
    """Frozen cumulative-session budget: ceilings + usage counters (B02).

    The seven fixed ceilings from the tasklist (48k aggregate output tokens,
    64 model continuations, 64 registered-tool calls, 1800 s cumulative wall
    time, 12 accepted edit batches, 12 replacement attempts total, 32 user
    messages) plus the matching cumulative usage counters.  ``record_*``
    returns a NEW instance and raises :class:`BudgetExceeded` when the
    ceiling would be exceeded; nothing is silently reset.  ``to_dict`` /
    ``from_dict`` give the B03 session authority a plain serialization shape
    (persistence itself is B03's job).
    """

    # Fixed ceilings.
    max_output_tokens: int = 48_000
    max_model_continuations: int = 64
    max_tool_calls: int = 64
    max_wall_clock_seconds: float = 1_800.0
    max_apply_batches: int = 12
    max_replacement_attempts: int = 12
    max_user_messages: int = 32
    # Cumulative usage counters.
    output_tokens: int = 0
    model_continuations: int = 0
    tool_calls: int = 0
    wall_clock_seconds: float = 0.0
    apply_batches: int = 0
    replacement_attempts: int = 0
    user_messages: int = 0

    def __post_init__(self) -> None:
        if dict(SESSION_BUDGET_CEILINGS) != {
            "max_output_tokens": self.max_output_tokens,
            "max_model_continuations": self.max_model_continuations,
            "max_tool_calls": self.max_tool_calls,
            "max_wall_clock_seconds": self.max_wall_clock_seconds,
            "max_apply_batches": self.max_apply_batches,
            "max_replacement_attempts": self.max_replacement_attempts,
            "max_user_messages": self.max_user_messages,
        }:
            raise ValueError("SessionBudget ceilings are frozen; do not override them.")

    def remaining_output_tokens(self) -> int:
        """Remaining aggregate output tokens for the provider output-cap path."""
        return max(0, self.max_output_tokens - self.output_tokens)

    def record_output_tokens(self, tokens: int) -> "SessionBudget":
        if tokens < 0:
            raise ValueError("tokens must be >= 0.")
        projected = self.output_tokens + tokens
        if projected > self.max_output_tokens:
            raise BudgetExceeded(
                family=BUDGET_FAMILY_SESSION_OUTPUT_TOKENS,
                limit=self.max_output_tokens,
                used=projected,
            )
        return replace(self, output_tokens=projected)

    def record_model_continuation(self) -> "SessionBudget":
        if self.model_continuations >= self.max_model_continuations:
            raise BudgetExceeded(
                family=BUDGET_FAMILY_SESSION_MODEL_CONTINUATIONS,
                limit=self.max_model_continuations,
                used=self.model_continuations,
            )
        return replace(self, model_continuations=self.model_continuations + 1)

    def record_tool_call(self) -> "SessionBudget":
        if self.tool_calls >= self.max_tool_calls:
            raise BudgetExceeded(
                family=BUDGET_FAMILY_SESSION_TOOL_CALLS,
                limit=self.max_tool_calls,
                used=self.tool_calls,
            )
        return replace(self, tool_calls=self.tool_calls + 1)

    def record_active_seconds(self, seconds: float) -> "SessionBudget":
        if seconds < 0:
            raise ValueError("seconds must be >= 0.")
        projected = self.wall_clock_seconds + seconds
        if projected > self.max_wall_clock_seconds:
            raise BudgetExceeded(
                family=BUDGET_FAMILY_SESSION_WALL_CLOCK,
                limit=self.max_wall_clock_seconds,
                used=projected,
            )
        return replace(self, wall_clock_seconds=projected)

    def record_apply_batch(self) -> "SessionBudget":
        if self.apply_batches >= self.max_apply_batches:
            raise BudgetExceeded(
                family=BUDGET_FAMILY_SESSION_APPLY_BATCHES,
                limit=self.max_apply_batches,
                used=self.apply_batches,
            )
        return replace(self, apply_batches=self.apply_batches + 1)

    def record_replacement_attempt(self) -> "SessionBudget":
        if self.replacement_attempts >= self.max_replacement_attempts:
            raise BudgetExceeded(
                family=BUDGET_FAMILY_SESSION_REPLACEMENT_ATTEMPTS,
                limit=self.max_replacement_attempts,
                used=self.replacement_attempts,
            )
        return replace(self, replacement_attempts=self.replacement_attempts + 1)

    def record_user_message(self) -> "SessionBudget":
        if self.user_messages >= self.max_user_messages:
            raise BudgetExceeded(
                family=BUDGET_FAMILY_SESSION_USER_MESSAGES,
                limit=self.max_user_messages,
                used=self.user_messages,
            )
        return replace(self, user_messages=self.user_messages + 1)

    def to_dict(self) -> dict[str, int | float]:
        """Plain serialization shape for the B03 session authority."""
        return {
            name: getattr(self, name) for name in self.__dataclass_fields__
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SessionBudget":
        """Rebuild from a :meth:`to_dict` payload (unknown keys ignored)."""
        fields = set(cls.__dataclass_fields__)
        return cls(**{key: data[key] for key in fields if key in data})


# ── B01 entrypoint (unchanged semantics + coverage assertion) ────────────────

# Interval between ``vibecomfy.executor.phase`` ``status="working"`` heartbeat
# events emitted while the execute phase is running (B05; mirrors the
# full-mode implement heartbeat).
_EXECUTE_HEARTBEAT_INTERVAL_SECONDS = 15.0


def _run_two_step(
    request: ExecutorRequest,
    *,
    plan: ClassifyDecision,
    pipeline_mode: PipelineMode,
    client_id: str | None = None,
    executor_id: str,
    additive: bool = False,
) -> ExecutorResult:
    """Two-step execute entrypoint (B01 seam; B05 wiring; execution in B03–B04).

    The request has already been classified by
    :func:`vibecomfy.executor.core.run_executor`; for ``answer_only``
    interactions the plan has additionally been rewritten to forbid edits
    before this seam is reached.  The pipeline mode is resolved ONCE in
    ``run_executor`` and passed in here — this entrypoint never re-resolves
    it.  It delegates to the injectable outcome boundary.

    B05: the explicit two-step ``execute`` profile stage is resolved here —
    NEVER a fallback to ``implement``; a missing stage is a typed
    :class:`~vibecomfy.executor.profiles.MissingProfileStageError` that
    surfaces as a typed profile failure result.  The execute lifecycle events
    (start/working/done/error) and the single ``phase="execute"`` profiler
    span with the execute budget counters are emitted around the outcome
    boundary.  B02: the route-policy coverage assertion runs on every
    execution (lazy import of the full-mode route authority).
    """
    assert_route_policy_coverage()

    # Lazy imports: ``core`` imports this module during its own
    # initialization, so module-level imports would observe the
    # partially-initialized ``core`` (same pattern as
    # :func:`assert_route_policy_coverage`).
    from vibecomfy.executor.core import (  # noqa: PLC0415
        _emit_executor_phase_event,
        _resolve_spec,
        _spec_fields,
    )
    from vibecomfy.comfy_nodes.agent.contracts import classify_failure  # noqa: PLC0415

    # ── Resolve the execute profile spec (two-step ONLY) ────────────────
    # ``execute`` is never synthesized from ``implement``: the profile must
    # declare it explicitly, otherwise the typed MissingProfileStageError
    # (preserved by ``_resolve_spec``) becomes a typed profile failure.
    try:
        execute_spec = _resolve_spec(request.profile, "execute")
    except Exception as exc:
        failure = classify_failure("profile", exc)
        return ExecutorResult.failure(
            kind=failure.kind.value,
            stage="profile",
            message=failure.user_facing_message,
            report=Report(plan=plan, pipeline_mode=pipeline_mode),
        )

    request_fields = {
        "executor_id": executor_id,
        "pipeline_mode": pipeline_mode,
        "profile": request.profile or "default",
        "session_id": request.session_id,
        "has_graph": request.graph is not None,
        "query_preview": short_text(request.query),
    }

    profiler_log(
        LOGGER,
        "executor.profile_resolved",
        **request_fields,
        execute=_spec_fields(execute_spec),
    )

    _emit_executor_phase_event(
        request,
        executor_id=executor_id,
        phase="execute",
        status="start",
        client_id=client_id,
    )

    # Keep the panel alive during long model-backed execute turns: a daemon
    # thread re-emits phase="execute" status="working" every ~15s until the
    # outcome boundary returns.  send_sync is thread-safe.
    heartbeat_stop = threading.Event()

    def _execute_heartbeat() -> None:
        while not heartbeat_stop.wait(_EXECUTE_HEARTBEAT_INTERVAL_SECONDS):
            _emit_executor_phase_event(
                request,
                executor_id=executor_id,
                phase="execute",
                status="working",
                client_id=client_id,
            )

    heartbeat_thread = threading.Thread(
        target=_execute_heartbeat,
        name="vibecomfy-executor-execute-heartbeat",
        daemon=True,
    )

    with profiler_span(
        LOGGER,
        "executor.phase",
        **request_fields,
        phase="execute",
        **_spec_fields(execute_spec),
    ) as span:
        heartbeat_thread.start()
        try:
            result = _two_step_outcome(
                request=request,
                plan=plan,
                pipeline_mode=pipeline_mode,
                client_id=client_id,
                executor_id=executor_id,
                additive=additive,
            )
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=2.0)
        _span_update_from_execute_result(span, result)

    # Canonical terminal statuses: "done" on success, "error" on failure —
    # never "completed"/"failed".
    if getattr(result, "ok", False):
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="execute",
            status="done",
            client_id=client_id,
        )
    else:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="execute",
            status="error",
            client_id=client_id,
        )

    profiler_log(
        LOGGER,
        "executor.result",
        **request_fields,
        has_execute=True,
        result_has_graph=getattr(result, "graph", None) is not None,
        reply_preview=short_text(getattr(result, "reply", None)),
    )
    return result


def _span_update_from_execute_result(span: ProfilerSpan, result: ExecutorResult) -> None:
    """Fold the execute report's budget counters and identity into the span.

    The execute span is the ONE ``phase="execute"`` profiler span; its
    result fields mirror the canonical execute budget counters so the
    profiler log carries continuation/tool/budget usage without a second
    span.  Identity fields are prefixed (``execute_route`` /
    ``execute_session_id``) so they never collide with the span's base
    spec fields (``route`` / ``model`` / ``effort``).  Canned test outcomes
    without an execute report are skipped.
    """
    report = getattr(result, "report", None)
    execute = getattr(report, "execute", None)
    if execute is None:
        return
    span.update(
        execute_route=execute.route,
        execute_session_id=execute.session_id,
        **dict(execute.budget_usage),
    )


def _two_step_outcome(
    *,
    request: ExecutorRequest,
    plan: ClassifyDecision,
    pipeline_mode: PipelineMode,
    client_id: str | None,
    executor_id: str,
    additive: bool,
) -> ExecutorResult:
    """Real B03 execute boundary (was a B01 stub).

    Validates the two-step session identity, resolves the ``execute`` profile
    spec (never falling back to ``implement``), and runs the bounded execute
    loop.  Session failures map to typed failure results; a missing session id
    and a closed session are validated here (``begin_message`` enforces
    expiry/staleness/concurrency before any model work).
    """
    del client_id, executor_id, additive
    from vibecomfy.executor.two_step_session import (  # noqa: PLC0415
        TwoStepSessionError,
        TwoStepSessionStore,
        normalize_session_id,
    )

    if not request.session_id:
        exc = TwoStepSessionError(
            "invalid_request",
            "two-step execute requires a session_id (the server never mints ids).",
        )
        return ExecutorResult.failure(
            kind=exc.kind,
            stage="request",
            message=str(exc),
            report=Report(plan=plan, pipeline_mode=pipeline_mode),
        )

    route = plan.effective_route or _fallback_route(plan)
    store = TwoStepSessionStore()
    session_id = normalize_session_id(request.session_id)

    from vibecomfy.executor.agent_backend import run_execute_turn  # noqa: PLC0415

    try:
        from vibecomfy.executor.core import _resolve_spec  # noqa: PLC0415

        spec = _resolve_spec(request.profile, "execute")
        graph_render = _two_step_graph_render(request.graph)
        edit_session = _two_step_edit_session(request.graph)
        fact_pack = _two_step_fact_pack(request.graph)
        tool_executor = _two_step_tool_executor(
            route=route,
            edit_session=edit_session,
            web_search_enabled=False,
        )
        outcome = run_execute_turn(
            request,
            plan=plan,
            route=route,
            spec=spec,
            session_store=store,
            session_id=session_id,
            graph_render=graph_render,
            tool_executor=tool_executor,
            edit_session=edit_session,
            fact_pack=fact_pack,
        )
    except TwoStepSessionError as exc:
        return ExecutorResult.failure(kind=exc.kind, stage="request", message=str(exc))
    except Exception as exc:  # noqa: BLE001 - typed failure envelope
        return ExecutorResult.failure(kind="ExecuteError", stage="execute", message=str(exc))

    if not outcome.get("ok"):
        failure = outcome.get("failure")
        # Budget denials/exhaustion carry a canonical ``family`` (B02); session
        # errors carry ``kind`` — either becomes the typed failure kind.
        kind = (
            getattr(failure, "kind", None)
            or getattr(failure, "family", None)
            or "ExecuteError"
        )
        return ExecutorResult.failure(
            kind=kind,
            stage="execute",
            message=str(failure),
            report=Report(plan=plan, pipeline_mode=pipeline_mode),
        )
    # B04: map accepted work into the existing ImplementationResult + durable
    # candidate + ExecutorResult envelope.  Delta IDs are metadata pointing at
    # the canonical accepted-batch operations (already in the session ledger) —
    # never a new delta body.  B05: the two-step report always serializes the
    # resolved pipeline mode and carries the optional ``execute`` section.
    from vibecomfy.executor.contracts import ImplementationResult  # noqa: PLC0415

    budget = outcome.get("budget")
    budget_usage = _execute_budget_usage(budget)
    graph = outcome.get("graph")
    accepted_delta_ids = tuple(str(i) for i in (outcome.get("accepted_delta_ids") or ()))
    evidence_ids = tuple(str(i) for i in (outcome.get("evidence_ids") or ()))
    tool_call_ids = tuple(str(i) for i in (outcome.get("tool_call_ids") or ()))
    lens_fact_ids = tuple(str(i) for i in (outcome.get("lens_fact_ids") or ()))
    claim_validation = outcome.get("claim_validation") or {"status": "not_run"}
    self_assessment = outcome.get("self_assessment")

    implementation: ImplementationResult | None = None
    if graph is not None:
        durable_response = outcome.get("durable_response")
        implementation = ImplementationResult(
            graph=graph,
            message=str(outcome.get("reply") or ""),
            durable_response=durable_response if isinstance(durable_response, Mapping) else None,
        )

    return ExecutorResult.success(
        report=Report(
            plan=plan,
            pipeline_mode=pipeline_mode,
            implementation=implementation,
            execute=ExecuteReport(
                session_id=request.session_id,
                route=route,
                budget_usage=budget_usage,
                tool_call_ids=tool_call_ids,
                evidence_ids=evidence_ids,
                accepted_delta_ids=accepted_delta_ids,
                claim_validation=claim_validation,
                replacement_used=bool(outcome.get("replacement_used")),
                self_assessment=self_assessment,
            ),
        ),
        graph=graph,
        reply=outcome.get("reply"),
    )


_EXECUTE_BUDGET_USAGE_KEYS: tuple[str, ...] = (
    "output_tokens",
    "model_continuations",
    "tool_calls",
    "apply_batches",
    "replacement_attempts",
    "wall_clock_seconds",
)


def _execute_budget_usage(budget: Any) -> dict[str, int | float]:
    """Fold a two-step session budget into the canonical execute counters."""
    usage: dict[str, int | float] = {key: 0 for key in _EXECUTE_BUDGET_USAGE_KEYS}
    to_dict = getattr(budget, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, Mapping):
            for key in _EXECUTE_BUDGET_USAGE_KEYS:
                value = payload.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    usage[key] = value
    return usage


def _fallback_route(plan: ClassifyDecision) -> str:
    """Canonical route fallback without importing ``core`` at module scope."""
    if plan.implement and plan.research:
        return "adapt"
    if plan.implement:
        return "revise"
    if plan.research:
        return "research"
    return "respond"


class _TwoStepToolSession:
    """Per-turn session namespace handed to the registered tool handlers.

    Bridges the retained :class:`~vibecomfy.porting.edit.session.EditSession`
    (``schema_provider`` / IR / emit snapshot) with the injected research fakes
    and the disabled-by-default web flag, so the two-step execute phase shares
    ONE dispatch path with the full-mode tool registry.
    """

    __slots__ = ("edit_session", "search_fn", "get_fn", "cache_root", "web_search_enabled")

    def __init__(self, edit_session: Any, *, web_search_enabled: bool = False) -> None:
        self.edit_session = edit_session
        self.search_fn = None
        self.get_fn = None
        self.cache_root = None
        self.web_search_enabled = web_search_enabled

    @property
    def schema_provider(self) -> Any:
        return getattr(self.edit_session, "schema_provider", None)

    @property
    def workflow(self) -> Any:
        return getattr(self.edit_session, "workflow", None)

    def _emit_working_snapshot(self) -> Any:
        emit = getattr(self.edit_session, "_emit_working_snapshot", None)
        if callable(emit):
            return emit()
        return None


def _two_step_graph_render(graph: Any) -> str | None:
    """Render the current workflow's reply lenses for the execute prompt."""
    if not graph:
        return None
    try:
        from vibecomfy.porting.render import render_text  # noqa: PLC0415

        return render_text(graph, lenses=("surface", "topology"))
    except Exception:  # noqa: BLE001 - render is best-effort prompt context
        return None


def _two_step_edit_session(graph: Any) -> Any:
    """Construct the retained :class:`EditSession` from the request graph."""
    if not graph:
        return None
    try:
        from vibecomfy.porting.edit.session import EditSession  # noqa: PLC0415

        return EditSession(dict(graph))
    except Exception:  # noqa: BLE001 - a graph that cannot be ingested yields no edits
        return None


def _two_step_fact_pack(graph: Any) -> tuple[str, ...]:
    """Stable reply-lens fact IDs for *graph* (the current fact pack)."""
    if not graph:
        return ()
    try:
        from vibecomfy.porting.render import render_fact_pack  # noqa: PLC0415

        return tuple(str(ref.fact_id) for ref in render_fact_pack(graph, lenses=("surface", "topology")))
    except Exception:  # noqa: BLE001
        return ()


def _two_step_tool_executor(
    *,
    route: str,
    edit_session: Any,
    web_search_enabled: bool = False,
) -> Any:
    """Return a REAL route-gated tool dispatcher for the execute phase.

    The route allowlist/caps are enforced by ``check_before_tool_call`` in the
    loop; this dispatcher invokes the registered handler and projects the
    result through the registered ledger projector (``invoke_tool`` /
    ``project_tool_evidence``) so evidence artifacts + ledger entry + digest
    flow into the session transcript exactly like the full-mode research stage.
    """
    from vibecomfy.executor.tool_specs import (  # noqa: PLC0415
        TOOL_SPEC_BY_NAME,
        invoke_tool,
        project_tool_evidence,
    )

    def executor(tool: str, args: dict[str, Any]) -> Any:
        spec = TOOL_SPEC_BY_NAME.get(tool)
        if spec is None:
            return None
        session = _TwoStepToolSession(edit_session, web_search_enabled=web_search_enabled)
        result = invoke_tool(spec, session, args, None)
        return project_tool_evidence(spec, args, result, session)

    return executor


# ── B04: atomic edit state machine ───────────────────────────────────────────
#
# The two-step execute phase may run several model continuations; research /
# tool continuations may precede editing.  Editing itself is ATOMIC:
#
#   * exactly ONE complete Python batch may be accepted per message;
#   * one complete replacement is allowed ONLY after a rejection;
#   * after acceptance, further edit submissions are denied;
#   * a second rejection returns no candidate.
#
# Parse, resolution, CAS, channel, bounds, or done-gate failure returns ZERO Δ
# (``EditSession.apply_batch`` is the parse/interpret/gate/commit authority —
# its all-or-nothing interpreter already rolls a failed batch back, and the
# done-gate failure below rolls the just-applied batch back too).
#
# CAS is the request baseline + the current session revision ONLY — never
# model-supplied per-op old-values (the grammar/op schemas are NOT extended).
# The stale-baseline diagnostic surfaces on the one replacement continuation.


@dataclass(frozen=True)
class ApplyBatchOutcome:
    """The apply authority's verdict for one Python batch (B04)."""

    ok: bool
    landed_ops: tuple[Any, ...] = ()
    graph: Any = None
    reason: str = ""
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class TwoStepApplyResult:
    """The state machine's verdict for one edit submission (B04)."""

    accepted: bool
    delta_ids: tuple[str, ...] = ()
    graph: Any = None
    reason: str = ""
    diagnostics: tuple[str, ...] = ()
    replacement_allowed: bool = False
    no_candidate: bool = False


def _batch_reject_reason(result: Any) -> str:
    """Derive a stable rejection reason from an ``apply_batch`` result."""
    for diagnostic in (getattr(result, "diagnostics", ()) or ()):
        code = getattr(diagnostic, "code", "")
        if code:
            return str(code)
    if not getattr(result, "ok", False):
        return "batch_failed"
    if not getattr(result, "landed_ops", ()):
        return "no_landed_ops"
    if not getattr(result, "apply_eligible", False):
        return "apply_gate_rejected"
    return "rejected"


def apply_python_batch(
    edit_session: Any,
    code: str,
    *,
    done_fn: Any | None = None,
    emit_graph: bool = True,
) -> ApplyBatchOutcome:
    """Apply ONE Python batch through ``EditSession.apply_batch()`` (B04).

    ``apply_batch`` is the parse/interpret/gate/commit authority: this helper
    never independently calls parse / interpret / verify_apply.  After a
    successful apply the done-gate runs (``EditSession.done()``); a done-gate
    failure rolls the just-applied batch back so zero Δ is retained.
    """
    result = edit_session.apply_batch(code)
    if not (
        getattr(result, "ok", False)
        and getattr(result, "landed_ops", ())
        and getattr(result, "apply_eligible", False)
    ):
        diagnostics = tuple(
            str(getattr(d, "message", "") or getattr(d, "code", ""))
            for d in (getattr(result, "diagnostics", ()) or ())
        )
        return ApplyBatchOutcome(
            ok=False,
            reason=_batch_reject_reason(result),
            diagnostics=diagnostics,
        )
    done = done_fn() if done_fn is not None else edit_session.done()
    if not getattr(done, "ok", False):
        try:
            edit_session.rollback(1)
        except Exception:  # noqa: BLE001 - best-effort rollback
            pass
        return ApplyBatchOutcome(
            ok=False,
            reason="done_gate_failed",
            diagnostics=(str(getattr(done, "summary", "") or "done_gate_failed"),),
        )
    graph: Any = None
    if emit_graph:
        try:
            graph = edit_session.working_ui
        except Exception:  # noqa: BLE001 - graph emission is best-effort
            graph = None
    return ApplyBatchOutcome(ok=True, landed_ops=tuple(result.landed_ops), graph=graph)


class TwoStepEditStateMachine:
    """Atomic edit lifecycle for ONE two-step message turn (B04)."""

    def __init__(
        self,
        *,
        apply_fn: Any,
        id_factory: Any | None = None,
    ) -> None:
        self._apply_fn = apply_fn
        self._id_factory = id_factory or (lambda seq: f"d{seq}")
        self._accepted = False
        self._rejections = 0
        self._seq = 0
        self._accepted_delta_ids: tuple[str, ...] = ()
        self._graph: Any = None
        self._replacement_used = False

    # -- queries -------------------------------------------------------------

    @property
    def accepted(self) -> bool:
        return self._accepted

    @property
    def accepted_delta_ids(self) -> tuple[str, ...]:
        return self._accepted_delta_ids

    @property
    def graph(self) -> Any:
        return self._graph

    @property
    def replacement_used(self) -> bool:
        return self._replacement_used

    # -- mutation ------------------------------------------------------------

    def submit(self, code: str) -> TwoStepApplyResult:
        """Submit one Python batch; enforce the atomic lifecycle."""
        if self._accepted:
            return TwoStepApplyResult(
                accepted=False,
                reason="edit_already_accepted",
            )
        if self._rejections >= 2:
            return TwoStepApplyResult(
                accepted=False,
                reason="second_rejection_no_candidate",
                no_candidate=True,
            )
        if self._rejections == 1:
            self._replacement_used = True
        outcome = self._apply_fn(code)
        if getattr(outcome, "ok", False):
            self._accepted = True
            self._seq += 1
            self._accepted_delta_ids = (self._id_factory(self._seq),)
            self._graph = getattr(outcome, "graph", None)
            return TwoStepApplyResult(
                accepted=True,
                delta_ids=self._accepted_delta_ids,
                graph=self._graph,
                reason="accepted",
            )
        self._rejections += 1
        return TwoStepApplyResult(
            accepted=False,
            reason=str(getattr(outcome, "reason", "") or "rejected"),
            diagnostics=tuple(getattr(outcome, "diagnostics", ()) or ()),
            replacement_allowed=(self._rejections == 1),
            no_candidate=(self._rejections >= 2),
        )
