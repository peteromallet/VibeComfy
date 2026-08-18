"""Two-step execute-session authority (B03).

The two-step pipeline replaces the full-mode research → implement → reply
phases with a single bounded *execute* phase that may run over several model
continuations for ONE logical user message.  That phase needs a durable,
thread-continuous session so a follow-up message in the same chat window can
reference work (accepted Δ, lens facts, evidence) produced by earlier turns,
without provider-native memory.

This module is the single authority for that session.  It is deliberately NOT
an in-memory dict: the source of truth is a compact, append-only execute
transcript (JSON Lines) written under the *existing* durable session directory
(``out/editor_sessions/<session_id>/``) and guarded by the process-safe
:class:`~vibecomfy.comfy_nodes.agent.session.SessionStateLock` that the agent
edit path already uses.  Reconstruction happens only through the named ingest
door (:meth:`TwoStepSessionStore.ingest_transcript`) followed by canonical Δ
replay (:meth:`TwoStepSessionStore.replay_workflow`); the in-process
:class:`EditSessionCache` is a rehydratable cache only — eviction drops the
cache, never the durable transcript.

Typed errors distinguish the failure modes the loop must surface *before* any
model work:

* ``invalid_request``        — a two-step message arrived without a session id.
* ``session_expired``        — the chat window id is closed/expired; never
                               silently minted into a fresh session.
* ``stale_message``          — the message's baseline no longer matches the
                               retained workflow revision (CAS precursor).
* ``concurrent_message``     — another message for the same session is still
                               in flight (detected via the in-flight marker).
* ``missing_delta_reference`` — a final contract cites a Δ id that is not in
                               the session's accumulated accepted-Δ ledger.
* ``ungrounded_answer``       — a submit's reply asserts a causal mechanism or
                               a numeric recommendation without the required
                               grounding citation, after one corrective
                               continuation already ran.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from vibecomfy.comfy_nodes.agent.session import (
    DEFAULT_LOCK_TIMEOUT_SECONDS,
    SessionStateLock,
    normalize_session_id,
    session_dir_for,
)
from vibecomfy.executor.tool_specs import RESEARCH_PHASE_TOOLS
from vibecomfy.executor.two_step import SessionBudget
LOGGER = logging.getLogger(__name__)

# ── Durable layout ───────────────────────────────────────────────────────────

DEFAULT_TWO_STEP_SESSION_ROOT = Path("out/editor_sessions")
TWO_STEP_TRANSCRIPT_NAME = "two_step_execute.jsonl"
TWO_STEP_BASE_GRAPH_NAME = "two_step_base_graph.json"
TWO_STEP_WORKFLOW_NAME = "two_step_workflow.json"
TWO_STEP_IN_FLIGHT_NAME = ".two_step_in_flight"
TWO_STEP_OUTCOMES_NAME = "two_step_outcomes.jsonl"

# ── Typed error kinds ────────────────────────────────────────────────────────

ERROR_INVALID_REQUEST = "invalid_request"
ERROR_SESSION_EXPIRED = "session_expired"
ERROR_STALE_MESSAGE = "stale_message"
ERROR_CONCURRENT_MESSAGE = "concurrent_message"
ERROR_MISSING_DELTA_REFERENCE = "missing_delta_reference"
ERROR_UNGROUNDED_ANSWER = "ungrounded_answer"

_TWO_STEP_ERROR_KINDS = frozenset(
    {
        ERROR_INVALID_REQUEST,
        ERROR_SESSION_EXPIRED,
        ERROR_STALE_MESSAGE,
        ERROR_CONCURRENT_MESSAGE,
        ERROR_MISSING_DELTA_REFERENCE,
        ERROR_UNGROUNDED_ANSWER,
    }
)


class TwoStepSessionError(Exception):
    """Typed two-step session failure (see module docstring for the kinds)."""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        session_id: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        if kind not in _TWO_STEP_ERROR_KINDS:
            raise ValueError(f"Unknown two-step session error kind {kind!r}.")
        super().__init__(message)
        self.kind = kind
        self.session_id = session_id
        self.detail = dict(detail or {})


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def mint_lease_token() -> str:
    """A fresh, collision-resistant lease token for one whole-turn session lease.

    Used when a message arrives without an idempotency key: the session still
    holds a durable in-flight lease (scoped to this token) so a concurrent
    message for the same session can be detected, and ``end_message`` can
    release exactly the lease this turn acquired.
    """
    return f"anon:{uuid.uuid4().hex}"


def _jsonish(value: Any) -> Any:
    """Coerce *value* to a JSON-safe primitive (best-effort, non-lossy-ish).

    Dataclasses/exceptions map to their ``__dict__``-like shape; ``Mapping`` /
    sequences recurse; anything else is ``str()``-fallback.  Used only for the
    durable completed-outcome record, never for the authoritative transcript.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonish(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonish(item) for item in value]
    if isinstance(value, BaseException):
        return {
            "type": type(value).__name__,
            "message": str(value),
        }
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _jsonish(to_dict())
        except Exception:  # noqa: BLE001
            pass
    if hasattr(value, "__dict__"):
        return {str(k): _jsonish(v) for k, v in vars(value).items()}
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


# ── Research-attempt derivation ──────────────────────────────────────────────
#
# ``research_attempt`` is a Python-derived statement of what research actually
# DID (from the session's evidence ledger), never a model judgment:
#   * never    — no research-phase tool was ever invoked in this session.
#   * empty    — research tools ran but recorded zero evidence ids.
#   * thin     — evidence ids exist but they are only search *hits*.
#   * grounded — at least one resolved record (hivemind_get / node_schema /
#                registry_lookup / ready_template_load) backs the evidence.

_GROUNDING_TOOLS = frozenset(
    {"hivemind_get", "node_schema", "registry_lookup", "ready_template_load"}
)


def derive_research_attempt(evidence_ledger: Any) -> str:
    """Derive ``never``/``empty``/``thin``/``grounded`` from an evidence ledger.

    *evidence_ledger* is any iterable of per-call entries; each entry must be a
    mapping with a ``tool`` name and an ``evidence_ids`` sequence.
    """
    entries = [e for e in evidence_ledger if isinstance(e, Mapping)]
    research_entries = [e for e in entries if e.get("tool") in RESEARCH_PHASE_TOOLS]
    if not research_entries:
        return "never"
    evidence_ids: list[str] = []
    for entry in research_entries:
        ids = entry.get("evidence_ids") or ()
        if isinstance(ids, (list, tuple)):
            evidence_ids.extend(str(i) for i in ids if i)
    if not evidence_ids:
        return "empty"
    grounded = any(e.get("tool") in _GROUNDING_TOOLS for e in research_entries)
    return "grounded" if grounded else "thin"


# ── Session state ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TwoStepSessionState:
    """Reconstructed snapshot of one two-step execute session.

    Every field is derivable from the append-only transcript; this dataclass is
    the rehydrated *view*, never the authority.
    """

    session_id: str
    route_history: tuple[dict[str, Any], ...] = ()
    accepted_delta_refs: tuple[dict[str, Any], ...] = ()
    lens_facts: tuple[dict[str, Any], ...] = ()
    evidence_ledger: tuple[dict[str, Any], ...] = ()
    replies: tuple[dict[str, Any], ...] = ()
    budget: SessionBudget = field(default_factory=SessionBudget)
    messages: tuple[dict[str, Any], ...] = ()
    last_workflow_hash: str | None = None
    closed: bool = False
    created_at: str = ""
    updated_at: str = ""

    # -- queries -------------------------------------------------------------

    def accepted_delta_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for ref in self.accepted_delta_refs:
            for delta_id in (ref.get("delta_ids") or ()):
                if delta_id:
                    ids.append(str(delta_id))
        return tuple(ids)

    def lens_fact_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for fact in self.lens_facts:
            for fact_id in (fact.get("fact_ids") or ()):
                if fact_id:
                    ids.append(str(fact_id))
        return tuple(ids)

    def evidence_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for entry in self.evidence_ledger:
            for evidence_id in (entry.get("evidence_ids") or ()):
                if evidence_id:
                    ids.append(str(evidence_id))
        return tuple(ids)

    def evidence_tool_map(self) -> dict[str, str]:
        """Return ``{evidence_id: tool}`` provenance from the evidence ledger.

        First tool wins per evidence id (ids are minted per tool call, so a
        collision is a harness bug, not a real ambiguity).
        """
        tools: dict[str, str] = {}
        for entry in self.evidence_ledger:
            tool = str(entry.get("tool") or "")
            for evidence_id in (entry.get("evidence_ids") or ()):
                if evidence_id and str(evidence_id) not in tools:
                    tools[str(evidence_id)] = tool
        return tools

    def research_attempt(self) -> str:
        return derive_research_attempt(self.evidence_ledger)

    def validate_delta_references(self, delta_ids: Any) -> None:
        """Raise :class:`TwoStepSessionError` when *delta_ids* cites a Δ id that
        is not in this session's accumulated accepted-Δ ledger (fail closed)."""
        accepted = set(self.accepted_delta_ids())
        for delta_id in delta_ids or ():
            if delta_id and str(delta_id) not in accepted:
                raise TwoStepSessionError(
                    ERROR_MISSING_DELTA_REFERENCE,
                    f"delta id {delta_id!r} is not an accepted Δ in session "
                    f"{self.session_id!r}.",
                    session_id=self.session_id,
                    detail={"delta_id": str(delta_id), "accepted": sorted(accepted)},
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "route_history": list(self.route_history),
            "accepted_delta_refs": list(self.accepted_delta_refs),
            "lens_facts": list(self.lens_facts),
            "evidence_ledger": list(self.evidence_ledger),
            "replies": list(self.replies),
            "budget": self.budget.to_dict(),
            "messages": list(self.messages),
            "last_workflow_hash": self.last_workflow_hash,
            "closed": self.closed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TwoStepSessionState":
        return cls(
            session_id=str(data.get("session_id") or ""),
            route_history=tuple(
                d for d in (data.get("route_history") or ()) if isinstance(d, Mapping)
            ),
            accepted_delta_refs=tuple(
                d for d in (data.get("accepted_delta_refs") or ()) if isinstance(d, Mapping)
            ),
            lens_facts=tuple(
                d for d in (data.get("lens_facts") or ()) if isinstance(d, Mapping)
            ),
            evidence_ledger=tuple(
                d for d in (data.get("evidence_ledger") or ()) if isinstance(d, Mapping)
            ),
            replies=tuple(
                d for d in (data.get("replies") or ()) if isinstance(d, Mapping)
            ),
            budget=SessionBudget.from_dict(data.get("budget") or {}),
            messages=tuple(
                d for d in (data.get("messages") or ()) if isinstance(d, Mapping)
            ),
            last_workflow_hash=(
                str(data["last_workflow_hash"]) if data.get("last_workflow_hash") else None
            ),
            closed=bool(data.get("closed")),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )


def fresh_state(session_id: str, *, now_iso: str | None = None) -> TwoStepSessionState:
    ts = now_iso or _now_iso()
    return TwoStepSessionState(
        session_id=session_id,
        budget=SessionBudget(),
        created_at=ts,
        updated_at=ts,
    )


# ── In-process cache (LRU + idle eviction) ───────────────────────────────────

DEFAULT_IDLE_TTL_SECONDS = 900.0  # 15 minutes
DEFAULT_MAX_CACHE_ENTRIES = 128


class EditSessionCache:
    """Bounded LRU cache of rehydrated :class:`TwoStepSessionState` views.

    Idle entries (no ``get`` touch for ``idle_ttl_seconds``) are evicted on
    access/insert.  Eviction drops ONLY the cache — the durable transcript is
    always rehydratable via the store's ingest door.
    """

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_CACHE_ENTRIES,
        idle_ttl_seconds: float = DEFAULT_IDLE_TTL_SECONDS,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError("EditSessionCache max_entries must be >= 1.")
        self.max_entries = max_entries
        self.idle_ttl_seconds = idle_ttl_seconds
        self._now = now
        # session_id -> (last_access_monotonic, state)
        self._entries: "OrderedDict[str, tuple[float, TwoStepSessionState]]" = OrderedDict()

    def evict_idle(self, now: float | None = None) -> list[str]:
        now = self._now() if now is None else now
        evicted: list[str] = []
        for session_id in list(self._entries):
            last_access, _state = self._entries[session_id]
            if now - last_access > self.idle_ttl_seconds:
                self._entries.pop(session_id, None)
                evicted.append(session_id)
        return evicted

    def get(self, session_id: str) -> TwoStepSessionState | None:
        self.evict_idle()
        entry = self._entries.get(session_id)
        if entry is None:
            return None
        # Touch: move to most-recently-used end.
        self._entries.pop(session_id, None)
        self._entries[session_id] = (self._now(), entry[1])
        return entry[1]

    def put(self, session_id: str, state: TwoStepSessionState) -> None:
        self.evict_idle()
        self._entries.pop(session_id, None)
        self._entries[session_id] = (self._now(), state)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)  # drop least-recently-used

    def remove(self, session_id: str) -> None:
        self._entries.pop(session_id, None)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, session_id: str) -> bool:
        return session_id in self._entries


# ── Canonical Δ replay ───────────────────────────────────────────────────────
#
# The retained workflow revision is never persisted as an in-memory dict of
# record: it is re-derived by replaying the accepted canonical Δ ops over the
# session's base graph.  Replay routes EVERY op through the IR + emit door
# (Law 5): ``from_ui`` (the ingest door, ``use_comfy_converter=False``) builds
# the retained :class:`~vibecomfy.workflow.VibeWorkflow` once, each canonical
# op is parsed with ``parse_edit_op`` and applied copy-on-write by
# ``apply_edit_cow``, and the emit door (``emit_ui_json`` + ``pin_untouched_ui``)
# is the ONLY place ``widgets_values`` / ``links`` / ``nodes`` are written —
# this module never touches raw UI JSON structure.  Untouched nodes and links
# stay byte-identical to the base graph (Law 1): ``pin_untouched_ui`` restores
# original JSON for anything the accepted ops did not attribute.


def _replay_widgets_values_ops(
    workflow: Any,
    op: Mapping[str, Any],
) -> tuple[Any, ...]:
    """Translate a legacy whole-``widgets_values`` replace into per-widget ops.

    The pre-IR replay vocabulary allowed ``set_node_field`` with
    ``field_path == "widgets_values"`` and a list value to replace the node's
    entire widget list.  The IR has no whole-list channel: each widget is a
    named field, so the list is applied positionally to the target node's
    current widget names (``widget_N`` under a schema-less ingest, the schema
    widget names otherwise).  Returns the translated typed ops, or ``()`` when
    the target cannot be resolved on the IR.
    """
    target = op.get("target")
    if not (isinstance(target, (list, tuple)) and len(target) >= 3):
        return ()
    scope_path = str(target[0] or "")
    uid = str(target[1])
    from vibecomfy.porting.edit._ir_utils import _root_node_for_uid  # noqa: PLC0415
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp  # noqa: PLC0415

    try:
        _node_id, node = _root_node_for_uid(workflow, scope_path, uid)
    except Exception:  # noqa: BLE001 - scoped targets are not IR-resolvable
        node = None
    if node is None and scope_path:
        # Legacy Δ ops recorded scope_path="node" for root nodes; the IR root
        # scope is "".  Retry the empty scope before giving up.
        try:
            _node_id, node = _root_node_for_uid(workflow, "", uid)
        except Exception:  # noqa: BLE001
            node = None
    if node is None:
        return ()
    widget_names = list(getattr(node, "widgets", {}) or {})
    if not widget_names:
        # Schema-driven ingest stores widget-backed values in ``inputs`` (the
        # STRING/INT/FLOAT scalar inputs that are widgets when unlinked) with
        # the raw UI evidence preserved in ``raw_widgets``.  The legacy
        # whole-list op replaces the node's widget VALUES positionally — map
        # onto the input names in widgets_values order so the emit door
        # projects them back into ``widgets_values`` under the schema names.
        raw = getattr(node, "raw_widgets", None)
        raw_values = getattr(raw, "values", None) if raw is not None else None
        if not isinstance(raw_values, (list, tuple)):
            raw_values = ()
        input_names = [str(name) for name in (getattr(node, "inputs", {}) or {})]
        widget_names = [
            name
            for index, name in enumerate(input_names)
            if index < len(raw_values)
        ]
        if not widget_names:
            # No schema / no matching inputs: fall back to positional names so
            # the per-widget ops still land on a channel the emit can project.
            widget_names = [f"widget_{i}" for i in range(len(raw_values))]
        if not widget_names:
            return ()
    value = op.get("value")
    if not isinstance(value, (list, tuple)):
        value = (value,)
    translated: list[Any] = []
    for index, name in enumerate(widget_names):
        translated.append(
            SetNodeFieldOp(
                op="set_node_field",
                target=NodeFieldTarget(
                    # Legacy Δ ops recorded scope_path="node" for root nodes;
                    # the IR root scope is "" and apply_edit_cow cannot
                    # resolve a non-root scope it never created.
                    scope_path="", uid=uid, field_path=str(name)
                ),
                value=value[index] if index < len(value) else None,
            )
        )
    return tuple(translated)


def _replay_named_field_op(
    workflow: Any,
    op: Mapping[str, Any],
    *,
    schema_provider: Any = None,
) -> Any | None:
    """Map a schema-less named field onto the node's widget channel.

    The live typed path records ``set_node_field`` with the SCHEMA field name
    the model saw in the render (philosophy #9: names over indices — the
    ``edit_node`` tool rejects positional ``widget_N`` fields).  A schema-less
    ingest (the replay default) renames every widget positionally to
    ``widget_N``, so the recorded name matches neither IR channel.  The named
    field is resolved to the correct widget slot BY POSITION in the node's
    ``raw_widgets`` / ``widgets_values`` order — schema names when available,
    else the committed/object_info widget order, else the single-widget
    heuristic (which was always unambiguous).  Returns the translated typed
    op, or ``None`` when the field resolves in an IR channel, the node has
    zero widgets, or the value looks like canvas furniture (list/dict) — in
    those cases the caller falls through to the canonical parse (the
    ``unknown channel -> inputs`` policy).
    """
    target = op.get("target")
    if not (isinstance(target, (list, tuple)) and len(target) >= 3):
        return None
    scope_path = str(target[0] or "")
    uid = str(target[1])
    field = str(target[2])
    value = op.get("value")
    if isinstance(value, (list, tuple, dict)):
        return None
    from vibecomfy.porting.edit._ir_utils import _root_node_for_uid  # noqa: PLC0415
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp  # noqa: PLC0415

    try:
        _node_id, node = _root_node_for_uid(workflow, scope_path, uid)
    except Exception:  # noqa: BLE001 - scoped targets are not IR-resolvable
        node = None
    if node is None and scope_path:
        try:
            _node_id, node = _root_node_for_uid(workflow, "", uid)
        except Exception:  # noqa: BLE001
            node = None
    if node is None:
        return None
    widgets = getattr(node, "widgets", {}) or {}
    inputs = getattr(node, "inputs", {}) or {}
    if field in widgets or field in inputs:
        return None
    widget_names = list(widgets)
    if not widget_names:
        return None
    if len(widget_names) == 1:
        # Single widget: the named literal field IS that widget.
        widget_key = widget_names[0]
    else:
        # Multi-widget node: resolve the named field to its positional slot.
        from vibecomfy.porting.widgets.compact_resolver import (  # noqa: PLC0415
            widget_index_for_field,
        )

        index = widget_index_for_field(node, field, schema_provider=schema_provider)
        if index is None:
            return None
        positional = f"widget_{index}"
        if positional in widgets:
            widget_key = positional
        elif 0 <= index < len(widget_names):
            widget_key = widget_names[index]
        else:
            return None
    return SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget(
            # The recorded scope may be the legacy "node" marker; the IR root
            # scope is "" and apply_edit_cow resolves only scopes it created.
            scope_path="", uid=uid, field_path=str(widget_key)
        ),
        value=value,
    )


def _replay_legacy_add_node(op: Mapping[str, Any]) -> dict[str, Any] | None:
    """Translate the legacy raw-payload ``add_node`` shape to the canonical form.

    Legacy: ``{uid, fields: {type, widgets_values, ...}}`` — the flattened raw
    node payload the pre-IR vocabulary recorded.  The live typed path never
    emits this shape (``canonical_op_to_dict`` always records ``class_type`` +
    named ``fields`` + ``inputs``); the translation re-attaches the positional
    widget list as ``widget_N`` fields so the emit door can project it back
    into ``widgets_values``.  Returns ``None`` when the op is not the legacy
    shape.
    """
    fields = op.get("fields")
    if not isinstance(fields, Mapping):
        return None
    class_type = fields.get("type")
    if not isinstance(class_type, str) or not class_type:
        return None
    uid = op.get("uid")
    if uid is None:
        return None
    cleaned: dict[str, Any] = {}
    positional: Any = None
    for key, value in fields.items():
        if key == "widgets_values":
            positional = value
        elif key != "type":
            cleaned[key] = value
    if isinstance(positional, (list, tuple)):
        for index, item in enumerate(positional):
            cleaned[f"widget_{index}"] = item
    elif positional is not None:
        cleaned["widget_0"] = positional
    raw_inputs = op.get("inputs")
    return {
        "op": "add_node",
        "scope_path": str(op.get("scope_path") or ""),
        "uid": str(uid),
        "node_id": str(op.get("node_id") if op.get("node_id") is not None else uid),
        "class_type": class_type,
        "fields": cleaned,
        "inputs": dict(raw_inputs) if isinstance(raw_inputs, Mapping) else {},
    }


def _replay_add_node_named_fields(op: Mapping[str, Any]) -> dict[str, Any]:
    """Translate a canonical ``add_node``'s named fields to positional ``widget_N``.

    The typed ``add_node`` tool records semantic field names (``prompt`` /
    ``steps`` / ``seed`` …) without widget names.  Schema-less replay
    classifies only ``widget_N`` keys as widgets, so the named fields would
    otherwise land in ``inputs`` and emit as ``widgets_values=[]``.  This
    translation records the field ORDER as the canonical widget order (kept in
    ``widget_field_names`` for schema-aware consumers) and re-keys the fields
    positionally so the emit door projects them back into ``widgets_values``.
    Returns the op unchanged when there is nothing to translate.
    """
    fields = op.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return dict(op)
    ordered = op.get("widget_field_names")
    if isinstance(ordered, (list, tuple)):
        names = [str(name) for name in ordered]
    else:
        names = [str(name) for name in fields]
    positional: dict[str, Any] = {}
    seen: set[str] = set()
    index = 0
    for name in names:
        if name in seen or name not in fields:
            continue
        positional[f"widget_{index}"] = fields[name]
        seen.add(name)
        index += 1
    # Any leftover named fields (not in the recorded order) keep their names at
    # the tail so no value is ever dropped.
    for name, value in fields.items():
        if name in seen:
            continue
        positional[f"widget_{index}"] = value
        seen.add(name)
        index += 1
    if positional == dict(fields):
        return dict(op)
    translated = dict(op)
    translated["fields"] = positional
    translated["widget_field_names"] = names
    return translated


def _replay_canonical_op(
    workflow: Any,
    op: Mapping[str, Any],
    *,
    schema_provider: Any = None,
) -> tuple[Any, ...]:
    """Translate one canonical Δ dict into typed op(s) for the IR apply engine.

    Every canonical op kind the live typed path records is supported
    (``set_node_field`` / ``add_node`` / ``remove_node`` / ``upsert_link`` /
    ``remove_link`` / ``set_mode`` / ``subgraph_interface``); the legacy
    pre-IR shapes (whole-``widgets_values`` replace, raw-payload ``add_node``)
    and the schema-less named-field channel mapping are translated at the op
    level before the IR apply.  Raises for ops that are neither canonical nor
    translatable (the caller skips them).
    """
    from vibecomfy.porting.edit.ops import parse_edit_op  # noqa: PLC0415

    kind = op.get("op")
    if kind == "set_node_field":
        target = op.get("target")
        if (
            isinstance(target, (list, tuple))
            and len(target) >= 3
            and str(target[2]) == "widgets_values"
        ):
            return _replay_widgets_values_ops(workflow, op)
        named = _replay_named_field_op(workflow, op, schema_provider=schema_provider)
        if named is not None:
            return (named,)
    if kind == "add_node" and op.get("class_type") is None:
        legacy = _replay_legacy_add_node(op)
        if legacy is not None:
            op = legacy
    if kind == "add_node":
        op = _replay_add_node_named_fields(op)
    return (parse_edit_op(op),)


def _apply_delta_ops(
    base_graph: Mapping[str, Any] | None,
    ops: Any,
    *,
    schema_provider: Any = None,
) -> dict[str, Any] | None:
    """Replay canonical Δ ops over *base_graph* through the IR + emit door.

    The raw graph is never patched in this module: ``from_ui`` ingests it into
    the retained IR, every op is applied copy-on-write on the IR, and the emit
    door projects the result back to UI JSON with ``pin_untouched_ui``
    attribution (untouched nodes and links stay byte-identical to the base).
    Ops the door cannot apply are skipped with a warning, never fatal: replay
    must reconstruct a usable revision even for a stale/legacy Δ ledger.
    """
    if not isinstance(base_graph, Mapping):
        return None
    ops = tuple(ops or ())
    if not ops:
        return json.loads(json.dumps(dict(base_graph)))

    from vibecomfy.ingest.normalize import from_ui  # noqa: PLC0415
    from vibecomfy.porting.edit._ir_utils import apply_edit_cow  # noqa: PLC0415
    from vibecomfy.porting.emit.ui import emit_ui_json, pin_untouched_ui  # noqa: PLC0415

    raw = dict(base_graph)
    try:
        workflow = from_ui(
            raw,
            use_comfy_converter=False,
            schema_provider=schema_provider,
        )
    except Exception:  # noqa: BLE001 - a base the ingest door rejects cannot be replayed
        LOGGER.warning(
            "two-step replay: ingest door rejected the base graph; returning it unchanged"
        )
        return json.loads(json.dumps(raw))

    applied: list[Any] = []
    for op in ops:
        if not isinstance(op, Mapping):
            continue
        try:
            typed_ops = _replay_canonical_op(workflow, op, schema_provider=schema_provider)
        except Exception as exc:  # noqa: BLE001 - malformed ops are skipped, never fatal
            LOGGER.warning(
                "two-step replay: skipping unsupported op %r: %s", op.get("op"), exc
            )
            continue
        for typed in typed_ops:
            try:
                workflow = apply_edit_cow(workflow, typed, schema_provider=schema_provider)
            except Exception as exc:  # noqa: BLE001 - unresolvable targets are skipped
                LOGGER.warning(
                    "two-step replay: skipping unapplicable op %r: %s", typed.op, exc
                )
                continue
            applied.append(typed)

    try:
        emitted = emit_ui_json(
            workflow,
            schema_provider=schema_provider,
            include_virtual_wires=True,
            prior_ui_payload=raw,
        )
        return pin_untouched_ui(raw, emitted, tuple(applied))
    except Exception:  # noqa: BLE001 - a degenerate IR must not break reconstruction
        LOGGER.warning(
            "two-step replay: emit door rejected the replayed IR; returning base unchanged"
        )
        return json.loads(json.dumps(raw))


def serialize_delta_ops(landed_ops: Any) -> tuple[dict[str, Any], ...]:
    """Serialize landed typed edit ops to canonical dicts for the Δ ledger.

    The canonical dict form is produced by
    :func:`vibecomfy.porting.edit.ops.canonical_op_to_dict` — the same shape
    :func:`_apply_delta_ops` replays — so restart reconstruction and the live
    apply path share ONE interpreter contract for every operation kind.
    """
    from vibecomfy.porting.edit.ops import canonical_op_to_dict  # noqa: PLC0415

    serialized: list[dict[str, Any]] = []
    for op in landed_ops or ():
        if isinstance(op, Mapping):
            serialized.append(dict(op))
            continue
        try:
            serialized.append(canonical_op_to_dict(op))
        except Exception:  # noqa: BLE001 - best-effort serialization
            continue
    return tuple(serialized)


def canonical_workflow_hash(graph: Any) -> str | None:
    """Stable hash for the retained revision (used for stale-message CAS)."""
    if graph is None:
        return None
    import hashlib

    raw = json.dumps(graph, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ── The durable store ────────────────────────────────────────────────────────


class TwoStepSessionStore:
    """Durable append-only transcript + rehydratable in-process cache.

    ``session_root`` defaults to the existing durable session directory
    (``out/editor_sessions``).  All transcript mutations are serialized with the
    process-safe :class:`SessionStateLock` (reused, never recreated) and write
    one JSON line per event under ``<session_dir>/two_step_execute.jsonl``.
    """

    def __init__(
        self,
        session_root: Path | str = DEFAULT_TWO_STEP_SESSION_ROOT,
        *,
        idle_ttl_seconds: float = DEFAULT_IDLE_TTL_SECONDS,
        max_cache_entries: int = DEFAULT_MAX_CACHE_ENTRIES,
        lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
        now: Callable[[], float] = time.monotonic,
        now_iso: Callable[[], str] = _now_iso,
    ) -> None:
        self.session_root = Path(session_root)
        self.cache = EditSessionCache(
            max_entries=max_cache_entries,
            idle_ttl_seconds=idle_ttl_seconds,
            now=now,
        )
        self.lock_timeout_seconds = lock_timeout_seconds
        self._now = now
        self._now_iso = now_iso

    # -- paths ---------------------------------------------------------------

    def session_dir(self, session_id: str) -> Path:
        return session_dir_for(self.session_root, normalize_session_id(session_id))

    def transcript_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_TRANSCRIPT_NAME

    def base_graph_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_BASE_GRAPH_NAME

    def workflow_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_WORKFLOW_NAME

    # -- load / ingest -------------------------------------------------------

    def load(self, session_id: str) -> TwoStepSessionState | None:
        """Return the cached view, else rehydrate from the durable transcript.

        Returns ``None`` when no transcript exists (the caller decides whether
        to open a fresh session — a missing id is NEVER silently created here).
        """
        safe_id = normalize_session_id(session_id)
        cached = self.cache.get(safe_id)
        if cached is not None:
            return cached
        state = self.ingest_transcript(safe_id)
        if state is not None:
            self.cache.put(safe_id, state)
        return state

    def exists(self, session_id: str) -> bool:
        return self.transcript_path(session_id).is_file()

    def ingest_transcript(self, session_id: str) -> TwoStepSessionState | None:
        """Named ingest door: rebuild the state view from the JSONL transcript.

        The transcript is the single source of truth.  If it is absent, the
        session has no durable record and this returns ``None``.
        """
        safe_id = normalize_session_id(session_id)
        path = self.transcript_path(safe_id)
        if not path.is_file():
            return None
        state = fresh_state(safe_id, now_iso="")
        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    LOGGER.warning("two-step transcript: skipping corrupt line in %s", path)
                    continue
                if isinstance(event, dict):
                    events.append(event)
        state = self._fold_events(state, events)
        if not state.created_at and events:
            first = events[0]
            state = replace(state, created_at=str(first.get("ts") or ""))
        state = replace(state, updated_at=str(events[-1].get("ts") or "") if events else "")
        return state

    def replay_workflow(
        self, state: TwoStepSessionState, *, base_graph: Mapping[str, Any] | None = None, schema_provider: Any = None
    ) -> dict[str, Any] | None:
        """Canonical Δ replay: re-derive the retained revision from the base
        graph plus the session's accepted Δ ops (in acceptance order)."""
        if base_graph is None:
            base_graph = self._read_base_graph(state.session_id)
        graph = base_graph
        for ref in state.accepted_delta_refs:
            graph = _apply_delta_ops(graph, ref.get("ops"), schema_provider=schema_provider)
        return graph

    def retained_workflow(self, session_id: str) -> dict[str, Any] | None:
        """Return the retained revision: canonical Δ replay is authoritative.

        The sidecar is only a derived cache: it is used ONLY when its hash
        matches the transcript-derived revision (replay).  A missing, corrupt,
        stale, or hash-mismatched sidecar falls back to canonical replay.
        """
        state = self.load(session_id)
        if state is None:
            return None
        replayed = self.replay_workflow(state)
        sidecar = self.workflow_path(session_id)
        if sidecar.is_file():
            try:
                cached = json.loads(sidecar.read_text(encoding="utf-8"))
                if cached is not None and canonical_workflow_hash(cached) == canonical_workflow_hash(replayed):
                    return dict(cached)
            except (OSError, json.JSONDecodeError):
                pass
        return replayed

    def write_workflow(self, session_id: str, graph: Mapping[str, Any]) -> None:
        """Persist the retained revision sidecar (durable candidate graph cache).

        Written ATOMICALLY (tmp + rename) under the reused process-safe lock so
        a concurrent reader never observes a half-written revision.  Replay
        stays the authority when the sidecar is absent or hash-mismatched.
        """
        safe_id = normalize_session_id(session_id)
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            session_dir.mkdir(parents=True, exist_ok=True)
            target = self.workflow_path(safe_id)
            tmp = target.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(dict(graph), sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp.replace(target)

    # -- mutation ------------------------------------------------------------

    def append(
        self,
        session_id: str,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        turn: int | None = None,
    ) -> TwoStepSessionState:
        """Serialize and append one transcript event; return the new state view.

        Uses the reused process-safe :class:`SessionStateLock`; a concurrent
        writer (same session) blocks until the lock is free, so the transcript
        stays append-only and ordered.
        """
        return self.append_events(session_id, [{"kind": kind, "turn": turn, **(dict(payload or {}))}])

    def append_events(self, session_id: str, events: list[dict[str, Any]]) -> TwoStepSessionState:
        safe_id = normalize_session_id(session_id)
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            session_dir.mkdir(parents=True, exist_ok=True)
            path = self.transcript_path(safe_id)
            existing = self.ingest_transcript(safe_id)
            state = existing if existing is not None else fresh_state(safe_id)
            next_seq = self._next_seq(state, path)
            ts = self._now_iso()
            with path.open("a", encoding="utf-8") as handle:
                for event in events:
                    record: dict[str, Any] = {"seq": next_seq, "ts": ts, "kind": event.get("kind")}
                    if event.get("turn") is not None:
                        record["turn"] = int(event["turn"])
                    record.update({k: v for k, v in event.items() if k not in ("kind", "turn")})
                    handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                    state = self._fold_event(state, record)
                    next_seq += 1
            state = replace(state, updated_at=ts)
            self.cache.put(safe_id, state)
            return state

    # -- open / close / begin-turn ------------------------------------------

    def open_session(
        self, session_id: str, *, base_graph: Mapping[str, Any] | None = None
    ) -> TwoStepSessionState:
        """Open (or reload) a session.  Never mints a fresh session for an id
        whose durable transcript exists but is closed (callers must check)."""
        safe_id = normalize_session_id(session_id)
        existing = self.load(safe_id)
        if existing is not None:
            if existing.closed:
                raise TwoStepSessionError(
                    ERROR_SESSION_EXPIRED,
                    f"session {safe_id!r} is closed/expired.",
                    session_id=safe_id,
                )
            return existing
        state = fresh_state(safe_id)
        if base_graph is not None:
            self._write_base_graph(safe_id, base_graph)
            state = replace(state, last_workflow_hash=canonical_workflow_hash(base_graph))
        self.cache.put(safe_id, state)
        return state

    def close(self, session_id: str) -> TwoStepSessionState:
        """Close a session; subsequent messages raise ``session_expired``."""
        return self.append(session_id, "closed", {"closed": True})

    def begin_message(
        self,
        session_id: str | None,
        *,
        base_graph: Mapping[str, Any] | None = None,
        expected_baseline_hash: str | None = None,
        message_fingerprint: str | None = None,
        lease_token: str | None = None,
    ) -> TwoStepSessionState:
        """Validate identity + staleness/concurrency BEFORE any model work.

        * Missing ``session_id`` → ``invalid_request``.
        * Closed session → ``session_expired`` (never a fresh session).
        * ``expected_baseline_hash`` that disagrees with the retained revision
          → ``stale_message``.
        * ``message_fingerprint`` (or *lease_token*) already in flight →
          ``concurrent_message``.

        Every message — with or without an idempotency key — acquires a durable
        whole-turn lease (keyed by ``message_fingerprint`` when present, else a
        fresh :func:`mint_lease_token`).  Leases from different fingerprints
        coexist (a second, distinct message is NOT lost), while a replay of the
        SAME key is refused so tools/edits are never duplicated.
        """
        if not session_id:
            raise TwoStepSessionError(
                ERROR_INVALID_REQUEST,
                "two-step execute requires a session_id (the server never mints ids).",
            )
        safe_id = normalize_session_id(session_id)
        lease_key = lease_token or message_fingerprint or mint_lease_token()
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            existing = self.load(safe_id)
            if existing is not None and existing.closed:
                raise TwoStepSessionError(
                    ERROR_SESSION_EXPIRED,
                    f"session {safe_id!r} is closed/expired.",
                    session_id=safe_id,
                )
            # Stale detection against the retained revision (CAS precursor).
            if expected_baseline_hash and existing is not None and existing.last_workflow_hash:
                if expected_baseline_hash != existing.last_workflow_hash:
                    raise TwoStepSessionError(
                        ERROR_STALE_MESSAGE,
                        "message baseline does not match the retained workflow revision.",
                        session_id=safe_id,
                        detail={
                            "expected": expected_baseline_hash,
                            "retained": existing.last_workflow_hash,
                        },
                    )
            marker = self._read_in_flight(safe_id)
            if lease_key in marker:
                raise TwoStepSessionError(
                    ERROR_CONCURRENT_MESSAGE,
                    "a message for this session is already in flight.",
                    session_id=safe_id,
                    detail={"fingerprint": lease_key},
                )
            self._acquire_in_flight(safe_id, lease_key)
            state = self.open_session(safe_id, base_graph=base_graph)
            return state

    def end_message(
        self,
        session_id: str,
        *,
        message_fingerprint: str | None = None,
        lease_token: str | None = None,
    ) -> None:
        """Release the in-flight lease set by :meth:`begin_message`.

        Only the lease this turn acquired is released — a distinct message's
        lease (and a replay-refused lease) is never cleared.  Pass
        *lease_token* for anonymous (no-idempotency-key) turns.
        """
        key = lease_token or message_fingerprint
        if not session_id or not key:
            return
        safe_id = normalize_session_id(session_id)
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            self._release_in_flight(safe_id, key)

    # -- internal ------------------------------------------------------------

    def _in_flight_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_IN_FLIGHT_NAME

    def _read_in_flight(self, session_id: str) -> dict[str, Any]:
        path = self._in_flight_path(session_id)
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _acquire_in_flight(self, session_id: str, lease_key: str) -> None:
        marker = self._read_in_flight(session_id)
        marker[lease_key] = {"ts": self._now()}
        self.session_dir(session_id).mkdir(parents=True, exist_ok=True)
        self._in_flight_path(session_id).write_text(
            json.dumps(marker, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _release_in_flight(self, session_id: str, lease_key: str) -> None:
        marker = self._read_in_flight(session_id)
        marker.pop(lease_key, None)
        path = self._in_flight_path(session_id)
        if marker:
            path.write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)

    # -- completed fingerprint → outcome (idempotent retry) ------------------

    def outcomes_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_OUTCOMES_NAME

    def record_completed(
        self,
        session_id: str,
        fingerprint: str,
        outcome: Mapping[str, Any],
    ) -> None:
        """Persist a completed fingerprint → outcome record.

        A later retry of the SAME fingerprint returns the stored outcome instead
        of re-running tools/edits (idempotent replay).
        """
        if not fingerprint:
            return
        safe_id = normalize_session_id(session_id)
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            session_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "fingerprint": fingerprint,
                "ts": self._now_iso(),
                "outcome": _jsonish(outcome),
            }
            with self.outcomes_path(safe_id).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")

    def completed_outcome(
        self, session_id: str, fingerprint: str
    ) -> dict[str, Any] | None:
        """Return the most recent completed outcome for *fingerprint*, if any."""
        if not fingerprint:
            return None
        path = self.outcomes_path(session_id)
        if not path.is_file():
            return None
        found: dict[str, Any] | None = None
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, Mapping) and record.get("fingerprint") == fingerprint:
                        outcome = record.get("outcome")
                        found = outcome if isinstance(outcome, Mapping) else None
        except OSError:
            return None
        return dict(found) if found is not None else None

    def _read_base_graph(self, session_id: str) -> dict[str, Any] | None:
        path = self.base_graph_path(session_id)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_base_graph(self, session_id: str, base_graph: Mapping[str, Any]) -> None:
        session_dir = self.session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        self.base_graph_path(session_id).write_text(
            json.dumps(dict(base_graph), sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _next_seq(self, state: TwoStepSessionState, path: Path) -> int:
        # The seq is derived from the transcript itself (count lines), not from
        # in-memory state, so a restarted process never reuses a sequence.
        if not path.is_file():
            return 1
        count = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
        return count + 1

    def _fold_event(self, state: TwoStepSessionState, event: Mapping[str, Any]) -> TwoStepSessionState:
        kind = event.get("kind")
        turn = int(event.get("turn") or 0)
        route = event.get("route")

        if kind == "route":
            state = replace(
                state,
                route_history=state.route_history + ({"route": route, "turn": turn, "at": event.get("ts") or _now_iso()},),
            )
        elif kind == "user_message":
            query = str(event.get("query") or "")
            state = replace(
                state,
                messages=state.messages + ({"turn": turn, "role": "user", "content": query, "route": route},),
                budget=state.budget.record_user_message(),
            )
        elif kind == "tool_call":
            state = replace(
                state,
                evidence_ledger=state.evidence_ledger + (
                    {
                        "turn": turn,
                        "tool": event.get("tool"),
                        "evidence_ids": list(event.get("evidence_ids") or ()),
                        "digest": str(event.get("digest") or ""),
                    },
                ),
                messages=state.messages + (
                    {"turn": turn, "role": "assistant_tool", "content": str(event.get("digest") or ""), "route": route},
                ),
            )
        elif kind == "delta_accepted":
            state = replace(
                state,
                accepted_delta_refs=state.accepted_delta_refs + (
                    {
                        "turn": turn,
                        "delta_ids": list(event.get("delta_ids") or ()),
                        "ops": list(event.get("ops") or ()),
                    },
                ),
                last_workflow_hash=event.get("workflow_hash") or state.last_workflow_hash,
            )
        elif kind == "lens_fact":
            state = replace(
                state,
                lens_facts=state.lens_facts + (
                    {"turn": turn, "fact_ids": list(event.get("fact_ids") or ()), "route": route},
                ),
            )
        elif kind == "reply":
            reply_text = str(event.get("reply") or "")
            state = replace(
                state,
                replies=state.replies + ({"turn": turn, "reply": reply_text, "at": event.get("ts") or _now_iso()},),
                messages=state.messages + ({"turn": turn, "role": "assistant_reply", "content": reply_text, "route": route},),
            )
        elif kind == "apply_accepted":
            ids = list(event.get("delta_ids") or ())
            text = f"edit accepted: delta_ids={ids}"
            state = replace(
                state,
                messages=state.messages + ({"turn": turn, "role": "assistant_edit", "content": text, "route": route},),
            )
        elif kind == "apply_rejected":
            diagnostics = " | ".join(str(d) for d in (event.get("diagnostics") or ()))
            text = f"edit rejected: {event.get('reason') or 'rejected'}" + (
                f" — {diagnostics}" if diagnostics else ""
            )
            if event.get("replacement_allowed"):
                text += " (one replacement allowed)"
            if event.get("no_candidate"):
                text += " (no candidate — do not submit another edit)"
            state = replace(
                state,
                messages=state.messages + ({"turn": turn, "role": "assistant_feedback", "content": text, "route": route},),
            )
        elif kind == "grounding_retry":
            diagnostics = " | ".join(str(d) for d in (event.get("violations") or ()))
            text = (
                "submit rejected for missing grounding: " + diagnostics
                + " — re-submit with proper claim_refs (cite node_schema / "
                + "fetched-doc evidence, or state 'unknown' and drop numeric "
                + "recommendations)."
            )
            state = replace(
                state,
                messages=state.messages + ({"turn": turn, "role": "assistant_feedback", "content": text, "route": route},),
            )
        elif kind == "model_truncated":
            # A provider ``finish_reason=length`` cut the model off mid-action.
            # The partial output is retained so the next continuation sees what
            # was already produced and resumes it (RC1).
            state = replace(
                state,
                messages=state.messages + (
                    {
                        "turn": turn,
                        "role": "assistant_partial",
                        "content": str(event.get("content") or "")[:2000],
                        "route": route,
                    },
                ),
            )
        elif kind == "budget":
            state = replace(state, budget=SessionBudget.from_dict(event.get("budget") or {}))
        elif kind == "closed":
            state = replace(state, closed=True)
        return state

    def _fold_events(self, state: TwoStepSessionState, events: list[dict[str, Any]]) -> TwoStepSessionState:
        for event in events:
            state = self._fold_event(state, event)
        return state


__all__ = [
    "DEFAULT_IDLE_TTL_SECONDS",
    "DEFAULT_MAX_CACHE_ENTRIES",
    "DEFAULT_TWO_STEP_SESSION_ROOT",
    "ERROR_CONCURRENT_MESSAGE",
    "ERROR_INVALID_REQUEST",
    "ERROR_MISSING_DELTA_REFERENCE",
    "ERROR_SESSION_EXPIRED",
    "ERROR_STALE_MESSAGE",
    "ERROR_UNGROUNDED_ANSWER",
    "EditSessionCache",
    "SessionBudget",
    "TwoStepSessionError",
    "TwoStepSessionState",
    "TwoStepSessionStore",
    "canonical_workflow_hash",
    "derive_research_attempt",
    "fresh_state",
    "mint_lease_token",
    "normalize_session_id",
    "serialize_delta_ops",
]
