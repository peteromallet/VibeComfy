"""All-100 classification capture + 50-case selection for the paired comparison.

The frozen ``classification_lock.json`` and ``two_step_50_manifest.json`` are
the single source of truth for the Pro B07 comparator.  This module is the ONLY
place that writes them.

Two capture paths
-----------------
1. **Real classifier capture** — :func:`capture_classifications` runs the
   ACTUAL classifier (``vibecomfy.executor.core._run_classify``'s underlying
   ``run_classify_turn`` seam, or ``_run_classify`` itself) over all 100
   canonical scenarios and freezes the decisions.  This is the only path that
   produces a lock with ``provenance.capture == "real_classifier"``.  It makes
   one model call per scenario, so it is invoked exclusively by
   ``compare_pipeline_modes --bootstrap --capture-classifications`` (or
   ``--capture-classifications`` alone) and run by the host — never inside the
   deterministic gate.

   Each scenario's classify turn carries the SAME bounded parse-retry ladder
   as production (``core._run_classify``): up to ``_CLASSIFY_CAPTURE_ATTEMPTS``
   attempts with the production nudge message appended after a malformed /
   missing-fields reply.  A retry-exhausted scenario is NOT an abort: its
   entry records ``classification_failed: true``, a ``classification_failure``
   block (failure type + raw-text preview + attempts), the heuristic route as
   the locked route, and ``route_source: "heuristic_fallback"`` — so one bad
   model response cannot kill the whole 100-scenario bootstrap.

2. **Provisional freeze** — :func:`build_classification_lock` builds the
   deterministic heuristic lock currently committed to
   ``classification_lock.json`` (``provenance.capture ==
   "provisional_heuristic"``, ``bootstrap_pending == true``).  It exists so the
   gate, ``--validate-only``, and ``--run`` can consume a byte-stable lock until
   the host executes the real bootstrap.  It is NOT the classification
   authority; it is an audited placeholder and is marked as such in the lock
   payload.

The two share the same lock schema, selection (hard quotas exact, media/size
best-fit with a documented stable-hash fallback), and validation, so switching
from the provisional freeze to the real capture is a pure re-run.

Classification dimensions
-------------------------
* ``route`` — the LOCKED route: the classifier's decision in the 8-route
  vocabulary (``clarify`` / ``respond`` / ``inspect`` / ``research`` /
  ``requires_custom_nodes`` / ``revise`` / ``adapt`` / ``reorganise``).  The
  install-intent route ``requires_custom_nodes`` is a *locked* route here even
  though the executor canonicalizes it (see below).
* ``effective_route`` — the route the executor actually runs after its
  install-intent migration (``_normalize_explicit_route``).  For
  ``requires_custom_nodes`` with edit intent this is ``adapt``; for every other
  route it equals ``route``.  Both are recorded so the locked route is never
  silently conflated with the canonical route.
* ``decision`` — the frozen :class:`~vibecomfy.executor.contracts.ClassifyDecision`
  payload (``to_dict()``) that the comparator injects identically into both
  pipeline legs.  In the real capture it is the classifier's actual output; in
  the provisional freeze it is the documented per-route stand-in.
* ``behavior`` — ``edit`` for ``revise``/``adapt``/``reorganise``/
  ``requires_custom_nodes``, else ``non-edit``.
* ``ledger`` — ``in`` when the id is in the 57-ledger (``ledger_scenario_ids()``),
  else ``out``.
* ``graph_size`` — small (<=15 nodes), medium (16-40), large (>40).
* ``media`` — image / video / multimodal / audio / 3d / special.

Selection
---------
The 50-case selection is exact on the HARD quotas (route / behavior / ledger)
and best-fit on media/size with a documented stable-hash fallback (see the
module body).  The committed actual media/size table is recorded under
``quota_table.actual`` so soft-target deviation is auditable without re-running
the selection.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

LOGGER = logging.getLogger(__name__)

# ── route vocabulary (mirrors vibecomfy.executor.two_step.TWO_STEP_ROUTE_POLICIES)
ROUTES: tuple[str, ...] = (
    "clarify",
    "respond",
    "inspect",
    "research",
    "requires_custom_nodes",
    "revise",
    "adapt",
    "reorganise",
)
EDIT_ROUTES = frozenset({"revise", "adapt", "reorganise", "requires_custom_nodes"})
NON_EDIT_ROUTES = frozenset({"clarify", "respond", "inspect", "research"})

# ── HARD quotas (route / behavior / ledger) ──────────────────────────────────
ROUTE_QUOTA: dict[str, int] = {
    "clarify": 2,
    "respond": 8,
    "inspect": 8,
    "research": 8,
    "requires_custom_nodes": 2,
    "revise": 12,
    "adapt": 8,
    "reorganise": 2,
}
BEHAVIOR_QUOTA: dict[str, int] = {"edit": 24, "non-edit": 26}
LEDGER_QUOTA: dict[str, int] = {"in": 25, "out": 25}

# ── SOFT (best-fit) targets ───────────────────────────────────────────────────
MEDIA_TARGET: dict[str, int] = {
    "image": 13,
    "video": 14,
    "multimodal": 12,
    "audio": 5,
    "3d": 5,
    "special": 1,
}
SIZE_TARGET: dict[str, int] = {"small": 15, "medium": 20, "large": 15}

_SMALL_MAX_NODES = 15
_MEDIUM_MAX_NODES = 40

# ── Bootstrap route overrides ─────────────────────────────────────────────────
#
# PROVISIONAL ONLY.  The live corpus has no natural tool-free-Q&A (``respond``),
# clarifying-question (``clarify``), missing-custom-node
# (``requires_custom_nodes``), or layout-only (``reorganise``) descriptors, so
# the provisional freeze fills those lanes with this explicit, audited override
# table.  ``route_source: "explicit"`` is recorded on each override so the
# bootstrap nature stays visible.  The real capture REPLACES these overrides
# with the actual classifier output.
EXPLICIT_ROUTES: dict[str, str] = {
    # reorganise (2)
    "image-generates-a-2x2-seed-variation": "reorganise",
    "image-background-removal-and-grid-composition-54a681": "reorganise",
    # requires_custom_nodes (2)
    "audio-acestep-audio-generation-workflow-2a31ec": "requires_custom_nodes",
    "hotshot-16-frames-agent-edit": "requires_custom_nodes",
    # clarify (2)
    "live-graph-explanation-smoke": "clarify",
    "video-wan-video-generation-with-vace-and-multi-outpu-d1caec": "clarify",
    # respond (8)
    "multi-animated-image-to-video-with-svd-and-lora-4ed6d9": "respond",
    "multi-audio-to-image-mel-band-roformer-workflow-b22937": "respond",
    "multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14": "respond",
    "video-animatediff-video-to-video-with-controlnet-and-3c978e": "respond",
    "video-image-to-video-with-svd-and-webp-output-1882aa": "respond",
    "video-inpaint-and-video-composition-with-spline-path-0c2716": "respond",
    "video-seedvr2-video-upscaling-workflow-052e59": "respond",
    "video-video-loading-and-saving-workflow-1c7ad8": "respond",
}

# ── Provisional per-route decision stand-in ──────────────────────────────────
#
# Used ONLY by the provisional freeze to synthesize a frozen
# ``ClassifyDecision`` per locked route.  The real capture replaces these with
# the classifier's actual ``ClassifyDecision`` output.  ``requires_custom_nodes``
# maps to an edit-intent decision; the executor's install-intent migration
# canonicalizes it to ``adapt`` — which is exactly why the lock records BOTH
# ``route`` (locked) and ``effective_route`` (canonical).
_ROUTE_PLAN_FIELDS: dict[str, dict[str, Any]] = {
    "clarify": {"research": False, "implement": False, "intent": "respond", "task": ""},
    "respond": {"research": False, "implement": False, "intent": "respond", "task": ""},
    "inspect": {"research": False, "implement": False, "intent": "explain_graph", "task": "inspect_graph"},
    "research": {"research": True, "implement": False, "intent": "research", "task": "research_nodes"},
    "requires_custom_nodes": {"research": False, "implement": False, "intent": "edit", "task": "edit_graph"},
    "revise": {"research": False, "implement": True, "intent": "edit", "task": "edit_graph"},
    "adapt": {"research": True, "implement": True, "intent": "edit", "task": "research_precedent"},
    "reorganise": {"research": False, "implement": True, "intent": "edit", "task": "layout_reorganise"},
}

_PROVISIONAL_CLASSIFIER_NOTE = (
    "Provisional freeze: routes derive from descriptor heuristics, not live "
    "classifier calls.  Run `python -m tests.live_agentic_harness."
    "compare_pipeline_modes --bootstrap --capture-classifications` to capture "
    "the 100 real classifier decisions."
)


class ClassificationError(ValueError):
    """Raised when the frozen lock/manifest is internally inconsistent."""


# ── provisional decision synthesis ───────────────────────────────────────────


def provisional_decision(route: str) -> dict[str, Any]:
    """Return the frozen provisional ``ClassifyDecision.to_dict()`` for *route*.

    Only used by the provisional freeze; the real capture records the actual
    classifier output instead.
    """
    from vibecomfy.executor.contracts import ClassifyDecision  # noqa: PLC0415

    if route not in _ROUTE_PLAN_FIELDS:
        raise ClassificationError(f"unknown provisional route {route!r}")
    plan = ClassifyDecision(route=route, reply=True, **_ROUTE_PLAN_FIELDS[route])
    return plan.to_dict()


def provisional_effective_route(route: str) -> str:
    """Return the executor-canonical route for the provisional *route*."""
    from vibecomfy.executor.contracts import ClassifyDecision  # noqa: PLC0415

    if route not in _ROUTE_PLAN_FIELDS:
        raise ClassificationError(f"unknown provisional route {route!r}")
    return ClassifyDecision(route=route, reply=True, **_ROUTE_PLAN_FIELDS[route]).effective_route


# ── deterministic dimension derivation (provisional heuristic) ──────────────


def _node_count(graph: Any) -> int | None:
    """Count nodes in a ComfyUI workflow (API map, litegraph, or corpus shape)."""
    if not isinstance(graph, dict):
        return None
    nodes = graph.get("nodes")
    if isinstance(nodes, dict):
        return len(nodes)
    if isinstance(nodes, list):
        return len(nodes)
    values = list(graph.values())
    if values and all(isinstance(v, dict) and "class_type" in v for v in values):
        return len(values)
    return None


def _graph_size(node_count: int | None) -> str:
    if node_count is None:
        return "small"  # graph-less descriptor (research health control)
    if node_count <= _SMALL_MAX_NODES:
        return "small"
    if node_count <= _MEDIUM_MAX_NODES:
        return "medium"
    return "large"


_ID_MEDIA_PREFIXES = (
    ("3d", "3d"),
    ("audio", "audio"),
    ("image", "image"),
    ("video", "video"),
    ("multi", "multimodal"),
)


def _media(scenario: Mapping[str, Any]) -> str:
    tags = scenario.get("_tags") or {}
    modality = tags.get("modality")
    if modality:
        return "multimodal" if modality == "multi" else str(modality)
    scenario_id = str(scenario.get("id") or "")
    for prefix, value in _ID_MEDIA_PREFIXES:
        if scenario_id.startswith(prefix + "-"):
            return value
    if not scenario.get("workflow_path") and "graph" not in scenario:
        return "special"
    return "image"


def _route_for(scenario: Mapping[str, Any]) -> tuple[str, str]:
    """Return ``(route, route_source)`` for the provisional heuristic."""
    scenario_id = str(scenario.get("id") or "")
    if scenario_id in EXPLICIT_ROUTES:
        return EXPLICIT_ROUTES[scenario_id], "explicit"

    classification = scenario.get("classification") or {}
    kind = classification.get("kind")
    tags = scenario.get("_tags") or {}
    query_type = tags.get("query_type", "")

    if kind == "health_control":
        route = "research" if scenario_id == "speed-distillation-research" else "inspect"
        return route, "health_control"
    if scenario.get("answer_rubric"):
        route = "research" if query_type == "research" else "inspect"
        return route, "query_type"
    if query_type == "big_adjustment":
        return "adapt", "query_type"
    return "revise", "query_type_default"


def _load_graph(scenario: Mapping[str, Any]) -> dict[str, Any] | None:
    """Load the source workflow graph for a scenario descriptor."""
    if scenario.get("workflow_path"):
        path = Path(str(scenario["workflow_path"]))
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
    if isinstance(scenario.get("graph"), dict):
        return scenario["graph"]
    return None


# ── classification (shared by both capture paths) ───────────────────────────


def classify_scenario(
    scenario: Mapping[str, Any],
    *,
    in_57_ids: frozenset[str],
) -> dict[str, Any]:
    """Classify one descriptor into the five dimensions (provisional heuristic).

    Produces the provisional ``route`` / ``effective_route`` / ``decision``.
    The real capture path (:func:`capture_classifications`) produces the same
    entry shape but fills ``route`` / ``effective_route`` / ``decision`` from
    the live classifier.
    """
    scenario_id = str(scenario.get("id") or "")
    route, route_source = _route_for(scenario)
    effective_route = provisional_effective_route(route)
    decision = provisional_decision(route)
    node_count = _node_count(_load_graph(scenario))
    return {
        "id": scenario_id,
        "route": route,
        "effective_route": effective_route,
        "route_source": route_source,
        "behavior": "edit" if route in EDIT_ROUTES else "non-edit",
        "ledger": "in" if scenario_id in in_57_ids else "out",
        "graph_size": _graph_size(node_count),
        "media": _media(scenario),
        "node_count": node_count,
        "decision": decision,
    }


# ── real classifier capture (--capture-classifications) ─────────────────────

# Bounded parse-retry for the real capture, mirroring production
# ``vibecomfy.executor.core._run_classify`` (core.py:702-784): a single
# classify model call is retried up to a small budget with the SAME nudge
# message production appends after a malformed/missing-fields reply, and a
# retry-exhausted scenario is recorded as a documented heuristic fallback
# instead of aborting the whole 100-scenario bootstrap.
_CLASSIFY_CAPTURE_ATTEMPTS = 3

# Mirrors ``vibecomfy.executor.core._CLASSIFY_JSON_NUDGE`` (the retry nudge
# ``_run_classify`` appends at core.py:777-780).  Kept local so the capture
# path never depends on a private core symbol.
_CLASSIFY_RETRY_NUDGE = (
    "Your previous reply was missing required fields or was not valid JSON. "
    "Return the exact JSON object required by the classify schema and nothing else."
)

_CLASSIFY_RAW_PREVIEW_LIMIT = 500


class ClassificationCaptureError(ClassificationError):
    """Real-classifier parse exhaustion for ONE scenario (never a global abort).

    Carries the raw-output preview + failure type so the caller can record a
    documented heuristic fallback for that single scenario.
    """

    def __init__(self, *, raw_preview: str, failure_type: str, attempts: int) -> None:
        super().__init__(
            f"real classifier produced no parseable decision after {attempts} attempts"
        )
        self.raw_preview = raw_preview
        self.failure_type = failure_type
        self.attempts = attempts


def _raw_preview(raw: str | None) -> str:
    """Bounded, whitespace-normalized preview of raw model output."""
    if not isinstance(raw, str) or not raw.strip():
        return ""
    normalized = " ".join(raw.split())
    if len(normalized) <= _CLASSIFY_RAW_PREVIEW_LIMIT:
        return normalized
    return normalized[:_CLASSIFY_RAW_PREVIEW_LIMIT] + "…"


def _classify_capture_is_retryable(exc: BaseException) -> bool:
    """True when *exc* is a model-output parse failure worth one more nudge.

    Mirrors ``vibecomfy.executor.core._classify_parse_is_retryable``:
    provider JSON-contract failures (``MalformedModelJSON`` /
    ``MissingRequiredField``) and the plain ``ValueError`` that
    ``parse_classify_response`` raises on prose / malformed JSON / empty
    content are retryable.  Auth / timeout / generic provider errors are
    infrastructure failures and propagate immediately.
    """
    from vibecomfy.comfy_nodes.agent.provider import (  # noqa: PLC0415
        AuthError,
        MalformedModelJSON,
        MissingRequiredField,
        ProviderError,
    )

    if isinstance(exc, (MalformedModelJSON, MissingRequiredField)):
        return True
    if isinstance(exc, (AuthError, TimeoutError)):
        return False
    if isinstance(exc, ProviderError):
        return False
    return isinstance(exc, ValueError)


def _classify_capture_failure_type(exc: BaseException, raw: str | None) -> str:
    """Best-effort failure taxonomy for a retry-exhausted classifier reply."""
    from vibecomfy.executor.agent_backend import _downstream_failure_type  # noqa: PLC0415

    raw_for_type = raw
    if not isinstance(raw_for_type, str) or not raw_for_type.strip():
        raw_for_type = getattr(exc, "raw_response", None)
        if not isinstance(raw_for_type, str) or not raw_for_type.strip():
            raw_for_type = getattr(exc, "raw_response_preview", None)
    return _downstream_failure_type(raw_for_type if isinstance(raw_for_type, str) else None)


def _extract_raw_route(raw: str) -> str:
    """Return the classifier's RAW ``route`` field, pre-normalization.

    The executor's install-intent migration canonicalizes
    ``requires_custom_nodes`` to ``adapt`` inside :class:`ClassifyDecision`,
    so the raw route is read back out of the JSON text itself to keep the
    install-intent route as the locked route.
    """
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("route"), str):
            return parsed["route"].strip()
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return ""


def _classify_scenario_once(
    scenario: Mapping[str, Any],
    spec: Any,
) -> tuple[str, str, dict[str, Any]]:
    """Run the REAL classifier with a bounded parse-retry and return
    ``(locked, effective, decision)``.

    Mirrors ``vibecomfy.executor.core._run_classify``'s inner
    ``run_classify_turn`` seam but ALSO preserves the raw ``route`` field the
    classifier emitted BEFORE the executor's install-intent migration, so the
    install-intent route ``requires_custom_nodes`` survives as the locked route
    instead of being silently folded into ``adapt``.

    A model output that cannot be parsed after ``_CLASSIFY_CAPTURE_ATTEMPTS``
    raises :class:`ClassificationCaptureError` (with a raw preview + failure
    type); it is the CALLER's job to record a per-scenario fallback so one bad
    response cannot abort the whole bootstrap.
    """
    from vibecomfy.executor.core import _render_census_text  # noqa: PLC0415
    from vibecomfy.executor.agent_backend import _extract_content  # noqa: PLC0415
    from vibecomfy.executor.prompts import (  # noqa: PLC0415
        build_classify_messages,
        parse_classify_response,
    )
    from vibecomfy.comfy_nodes.agent.provider import run_model_turn  # noqa: PLC0415

    graph = _load_graph(scenario)
    query = str(scenario.get("query") or "").strip()
    has_graph = graph is not None
    graph_summary = _render_census_text(graph)
    base_messages = build_classify_messages(
        query,
        has_graph=has_graph,
        graph_summary=graph_summary,
    )

    scenario_id = str(scenario.get("id") or "")
    last_exc: BaseException | None = None
    last_raw: str | None = None
    for attempt in range(1, _CLASSIFY_CAPTURE_ATTEMPTS + 1):
        messages = list(base_messages)
        if attempt > 1:
            # Production appends the nudge as a user turn (core.py:777-780).
            messages.append({"role": "user", "content": _CLASSIFY_RETRY_NUDGE})
        try:
            result = run_model_turn(
                query,
                messages,
                route=spec.agent,
                model=spec.model,
                effort=spec.effort,
                response_contract="json",
                profiling_context={"backend_phase": "classify"},
            )
            raw = _extract_content(result)
            last_raw = raw
            raw_route = _extract_raw_route(raw)
            decision = parse_classify_response(raw)
            locked = raw_route or decision.effective_route or "respond"
            return locked, decision.effective_route, decision.to_dict()
        except Exception as exc:  # noqa: BLE001 - retry/fallback at the seam
            last_exc = exc
            if not _classify_capture_is_retryable(exc):
                raise
            LOGGER.info(
                "classify capture retry %d/%d for %r (%s)",
                attempt,
                _CLASSIFY_CAPTURE_ATTEMPTS,
                scenario_id,
                type(exc).__name__,
            )

    raw_evidence = (
        last_raw
        if isinstance(last_raw, str) and last_raw.strip()
        else getattr(last_exc, "raw_response", None)
    )
    raise ClassificationCaptureError(
        raw_preview=_raw_preview(raw_evidence),
        failure_type=_classify_capture_failure_type(last_exc, last_raw),
        attempts=_CLASSIFY_CAPTURE_ATTEMPTS,
    ) from last_exc


def _real_classify_entry(
    scenario: Mapping[str, Any],
    *,
    in_57_ids: frozenset[str],
    spec: Any,
) -> dict[str, Any]:
    scenario_id = str(scenario.get("id") or "")
    try:
        locked, effective, decision = _classify_scenario_once(scenario, spec)
        route_source = "classifier"
        classification_failed = False
        classification_failure: dict[str, Any] | None = None
    except ClassificationCaptureError as exc:
        # Documented per-scenario fallback: keep the heuristic route so the
        # selection stays feasible, but mark the entry as classifier-failed
        # with the raw preview + failure taxonomy instead of aborting.
        locked, _ = _route_for(scenario)
        effective = provisional_effective_route(locked)
        decision = provisional_decision(locked)
        route_source = "heuristic_fallback"
        classification_failed = True
        classification_failure = {
            "failure_type": exc.failure_type,
            "attempts": exc.attempts,
            "raw_text_preview": exc.raw_preview,
        }
        LOGGER.warning(
            "classify capture fallback for %r: %s after %d attempts",
            scenario_id,
            exc.failure_type,
            exc.attempts,
        )

    node_count = _node_count(_load_graph(scenario))
    behavior = "edit" if locked in EDIT_ROUTES else "non-edit"
    entry: dict[str, Any] = {
        "id": scenario_id,
        "route": locked,
        "effective_route": effective,
        "route_source": route_source,
        "classification_failed": classification_failed,
        "behavior": behavior,
        "ledger": "in" if scenario_id in in_57_ids else "out",
        "graph_size": _graph_size(node_count),
        "media": _media(scenario),
        "node_count": node_count,
        "decision": decision,
    }
    if classification_failure is not None:
        entry["classification_failure"] = classification_failure
    return entry



def capture_classifications(
    scenarios: list[Mapping[str, Any]],
    *,
    in_57_ids: frozenset[str],
    profile: str | None = "default",
    max_workers: int = 1,
) -> dict[str, Any]:
    """Run the REAL classifier over all *scenarios* and freeze a lock payload.

    One model call per scenario.  ``provenance.capture`` is ``"real_classifier"``
    and ``bootstrap_pending`` is false.  Invoked only by ``--bootstrap
    --capture-classifications`` (host).
    """
    from vibecomfy.executor.core import _resolve_spec  # noqa: PLC0415

    spec = _resolve_spec(profile, "classify")

    def _one(scenario: Mapping[str, Any]) -> dict[str, Any]:
        return _real_classify_entry(scenario, in_57_ids=in_57_ids, spec=spec)

    if max_workers and max_workers > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            entries = list(pool.map(_one, scenarios))
    else:
        entries = [_one(s) for s in scenarios]

    entries.sort(key=lambda e: e["id"])
    selected_ids, actual_quota = select_50(entries)
    return _assemble_lock(entries, selected_ids, actual_quota, capture="real_classifier")


# ── selection ────────────────────────────────────────────────────────────────


def _stable_key(scenario_id: str) -> str:
    """Documented stable-hash fallback for selection tie-breaks."""
    return hashlib.sha256(scenario_id.encode("utf-8")).hexdigest()


def _route_pools(lock_entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    pools: dict[str, list[str]] = {route: [] for route in ROUTES}
    for entry in lock_entries:
        pools[entry["route"]].append(entry["id"])
    for route in ROUTES:
        pools[route].sort()
    return pools


def _deviation(actual: Mapping[str, int], target: Mapping[str, int]) -> int:
    return sum(abs(int(actual.get(k, 0)) - int(t)) for k, t in target.items())


def select_50(lock_entries: list[dict[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    """Select the 50 cases (hard quotas exact, media/size best-fit).

    Returns ``(selected_ids, actual_quota_table)``.
    """
    by_id = {e["id"]: e for e in lock_entries}
    pools = _route_pools(lock_entries)

    # 1. Routes whose pool exactly matches their quota are forced in.
    forced: set[str] = set()
    for route in ROUTES:
        if len(pools[route]) == ROUTE_QUOTA[route]:
            forced.update(pools[route])

    remaining_routes = ["inspect", "research", "revise", "adapt"]

    forced_in = sum(1 for s in forced if by_id[s]["ledger"] == "in")
    forced_out = len(forced) - forced_in
    need_in = LEDGER_QUOTA["in"] - forced_in
    need_out = LEDGER_QUOTA["out"] - forced_out

    avail: dict[str, tuple[list[str], list[str]]] = {}
    for route in remaining_routes:
        ins = [s for s in pools[route] if s not in forced and by_id[s]["ledger"] == "in"]
        outs = [s for s in pools[route] if s not in forced and by_id[s]["ledger"] == "out"]
        avail[route] = (ins, outs)

    def pick_for_allocation(alloc: dict[str, int]) -> tuple[set[str], int]:
        selected = set(forced)
        media_counts: Counter[str] = Counter(by_id[s]["media"] for s in selected)
        size_counts: Counter[str] = Counter(by_id[s]["graph_size"] for s in selected)

        def rank(scenario_id: str) -> tuple[int, int, str]:
            media = by_id[scenario_id]["media"]
            size = by_id[scenario_id]["graph_size"]
            media_need = MEDIA_TARGET.get(media, 0) - media_counts.get(media, 0)
            size_need = SIZE_TARGET.get(size, 0) - size_counts.get(size, 0)
            return (media_need, size_need, _stable_key(scenario_id))

        for route in remaining_routes:
            ins, outs = avail[route]
            take_in = alloc[route]
            take_out = ROUTE_QUOTA[route] - take_in
            ins_sorted = sorted(ins, key=rank)
            outs_sorted = sorted(outs, key=rank)
            for scenario_id in ins_sorted[:take_in] + outs_sorted[:take_out]:
                selected.add(scenario_id)
                media_counts[by_id[scenario_id]["media"]] += 1
                size_counts[by_id[scenario_id]["graph_size"]] += 1
        return selected, _deviation(media_counts, MEDIA_TARGET) + _deviation(
            size_counts, SIZE_TARGET
        )

    best: tuple[tuple[int, ...], set[str], dict[str, int]] | None = None
    for insp_in in range(4, 9):
        for res_in in range(4, 9):
            for rev_in in range(0, 13):
                for adapt_in in range(6, 9):
                    if insp_in + res_in + rev_in + adapt_in != need_in:
                        continue
                    alloc = {
                        "inspect": insp_in,
                        "research": res_in,
                        "revise": rev_in,
                        "adapt": adapt_in,
                    }
                    feasible = True
                    for route in remaining_routes:
                        ins, outs = avail[route]
                        take_in = alloc[route]
                        take_out = ROUTE_QUOTA[route] - take_in
                        if take_in > len(ins) or take_out > len(outs):
                            feasible = False
                            break
                    if not feasible:
                        continue
                    selected, deviation = pick_for_allocation(alloc)
                    key = (deviation, insp_in, res_in, rev_in, adapt_in)
                    if best is None or key < best[0]:
                        best = (key, selected, alloc)

    assert best is not None, "no feasible 50-case selection"
    _, selected, alloc = best

    selected_ids = sorted(selected)
    actual_quota = _actual_quota_table(by_id, selected_ids, alloc)
    return selected_ids, actual_quota


def _actual_quota_table(
    by_id: Mapping[str, dict[str, Any]],
    selected_ids: list[str],
    alloc: Mapping[str, int],
) -> dict[str, Any]:
    route_counts = Counter(by_id[s]["route"] for s in selected_ids)
    behavior_counts = Counter(by_id[s]["behavior"] for s in selected_ids)
    ledger_counts = Counter(by_id[s]["ledger"] for s in selected_ids)
    media_counts = Counter(by_id[s]["media"] for s in selected_ids)
    size_counts = Counter(by_id[s]["graph_size"] for s in selected_ids)
    return {
        "routes": {r: route_counts.get(r, 0) for r in ROUTES},
        "behavior": {b: behavior_counts.get(b, 0) for b in ("edit", "non-edit")},
        "ledger": {k: ledger_counts.get(k, 0) for k in ("in", "out")},
        "media": {k: media_counts.get(k, 0) for k in MEDIA_TARGET},
        "graph_size": {k: size_counts.get(k, 0) for k in SIZE_TARGET},
        "in_57_allocation": {k: int(v) for k, v in alloc.items()},
    }


# ── lock assembly ────────────────────────────────────────────────────────────


def _assemble_lock(
    entries: list[dict[str, Any]],
    selected_ids: list[str],
    actual_quota: dict[str, Any],
    *,
    capture: str,
) -> dict[str, Any]:
    is_real = capture == "real_classifier"
    return {
        "schema_version": 1,
        "scenario_count": len(entries),
        "selected_count": len(selected_ids),
        "selected_ids": selected_ids,
        "provenance": {
            "capture": capture,
            "bootstrap_pending": not is_real,
            "classifier_target": "vibecomfy.executor.core._run_classify",
            "note": "" if is_real else _PROVISIONAL_CLASSIFIER_NOTE,
        },
        "quota_table": {
            "routes": dict(ROUTE_QUOTA),
            "behavior": dict(BEHAVIOR_QUOTA),
            "ledger": dict(LEDGER_QUOTA),
            "media_target": dict(MEDIA_TARGET),
            "graph_size_target": dict(SIZE_TARGET),
            "actual": actual_quota,
        },
        "rules": {
            "behavior": "derived from route (edit = revise/adapt/reorganise/requires_custom_nodes)",
            "ledger": "in == scenario id present in the 57-ledger (ledger_scenario_ids())",
            "graph_size_thresholds": {
                "small": f"<= {_SMALL_MAX_NODES} nodes",
                "medium": f"{_SMALL_MAX_NODES + 1}-{_MEDIUM_MAX_NODES} nodes",
                "large": f"> {_MEDIUM_MAX_NODES} nodes",
                "graphless_default": "small",
            },
            "media": "modality tag -> id prefix -> special (graph-less) / image fallback",
            "stable_hash_fallback": "sha256(scenario_id) breaks selection ties",
            "explicit_route_overrides": dict(EXPLICIT_ROUTES),
            "effective_route": (
                "executor-canonical route after _normalize_explicit_route; "
                "requires_custom_nodes -> adapt (edit intent) is recorded, not hidden."
            ),
            "classification_failure_fallback": (
                "real capture only: a retry-exhausted classifier reply records "
                "classification_failed=true + classification_failure "
                "(failure_type/attempts/raw_text_preview), the heuristic route as "
                "route, and route_source='heuristic_fallback' — never an abort."
            ),
        },
        "entries": entries,
    }


def build_classification_lock(
    scenarios: list[Mapping[str, Any]],
    *,
    in_57_ids: frozenset[str],
) -> dict[str, Any]:
    """Build the deterministic PROVISIONAL lock payload (idempotent).

    This is the provisional freeze only.  It reproduces the committed
    ``classification_lock.json`` byte-for-byte (modulo formatting) so the gate
    and ``--validate-only``/``--run`` can consume a stable lock until the host
    runs the real capture.
    """
    entries = [classify_scenario(s, in_57_ids=in_57_ids) for s in scenarios]
    entries.sort(key=lambda e: e["id"])
    selected_ids, actual_quota = select_50(entries)
    return _assemble_lock(entries, selected_ids, actual_quota, capture="provisional_heuristic")


def build_two_step_manifest(
    lock: Mapping[str, Any],
    *,
    scenarios_dir: Path | None = None,
    manifest_path: Path | None = None,
    repo: Path | None = None,
) -> dict[str, Any]:
    """Build the strict 50/50 two-step manifest from the frozen lock.

    Reuses :func:`tests.live_agentic_harness.scenario_manifest.build_manifest`
    so descriptor/source hashes are byte-identical to the authoritative
    ``scenario_manifest.json``; only ``inclusion_status`` and the frozen
    ``classification`` block are overlaid.
    """
    from .scenario_manifest import build_manifest as _build_manifest  # noqa: PLC0415

    kwargs: dict[str, Any] = {}
    if scenarios_dir is not None:
        kwargs["scenarios_dir"] = scenarios_dir
    if repo is not None:
        kwargs["repo"] = repo
    manifest = _build_manifest(**kwargs)
    selected = set(lock["selected_ids"])
    lock_by_id = {e["id"]: e for e in lock["entries"]}
    for entry in manifest["entries"]:
        scenario_id = entry["id"]
        entry["inclusion_status"] = "included" if scenario_id in selected else "excluded"
        cls = lock_by_id[scenario_id]
        entry["classification"] = {
            "route": cls["route"],
            "effective_route": cls["effective_route"],
            "route_source": cls["route_source"],
            "behavior": cls["behavior"],
            "ledger": cls["ledger"],
            "graph_size": cls["graph_size"],
            "media": cls["media"],
        }
    manifest["scenario_count"] = sum(
        1 for e in manifest["entries"] if e["inclusion_status"] == "included"
    )
    manifest["selection"] = {
        "included": len(selected),
        "excluded": len(manifest["entries"]) - len(selected),
        "quota_table": lock["quota_table"],
    }
    return manifest


# ── lock / manifest validation ───────────────────────────────────────────────


def validate_lock(
    lock: Mapping[str, Any],
    *,
    scenario_ids: frozenset[str],
    in_57_ids: frozenset[str],
) -> None:
    """Validate a classification lock against the canonical descriptor set."""
    if lock.get("schema_version") != 1:
        raise ClassificationError("lock schema_version must be 1")
    provenance = lock.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ClassificationError("lock must carry a provenance block")
    if provenance.get("capture") not in {"provisional_heuristic", "real_classifier"}:
        raise ClassificationError("lock provenance.capture is invalid")
    entries = lock.get("entries")
    if not isinstance(entries, list) or len(entries) != len(scenario_ids):
        raise ClassificationError("lock must classify exactly the canonical scenarios")
    lock_ids = {e.get("id") for e in entries}
    if lock_ids != set(scenario_ids):
        raise ClassificationError(
            f"lock id set mismatch: missing={sorted(set(scenario_ids) - lock_ids)}, "
            f"extra={sorted(lock_ids - set(scenario_ids))}"
        )
    for entry in entries:
        for field in ("route", "effective_route", "behavior", "ledger", "graph_size", "media"):
            if not entry.get(field):
                raise ClassificationError(f"lock entry {entry.get('id')!r} missing {field}")
        if entry["route"] not in ROUTES:
            raise ClassificationError(f"lock entry {entry.get('id')!r} bad route {entry['route']!r}")
        if entry["behavior"] not in {"edit", "non-edit"}:
            raise ClassificationError(f"lock entry {entry.get('id')!r} bad behavior")
        expected_behavior = "edit" if entry["route"] in EDIT_ROUTES else "non-edit"
        if entry["behavior"] != expected_behavior:
            raise ClassificationError(f"lock entry {entry.get('id')!r} behavior/route mismatch")
        if entry["ledger"] not in {"in", "out"}:
            raise ClassificationError(f"lock entry {entry.get('id')!r} bad ledger")
        expected_ledger = "in" if entry["id"] in in_57_ids else "out"
        if entry["ledger"] != expected_ledger:
            raise ClassificationError(f"lock entry {entry.get('id')!r} ledger mismatch")
        decision = entry.get("decision")
        if not isinstance(decision, Mapping):
            raise ClassificationError(f"lock entry {entry.get('id')!r} missing decision")
        if entry["effective_route"] not in ROUTES:
            raise ClassificationError(
                f"lock entry {entry.get('id')!r} bad effective_route {entry['effective_route']!r}"
            )
        if entry["route"] == "requires_custom_nodes":
            if entry["effective_route"] == "requires_custom_nodes":
                raise ClassificationError(
                    f"lock entry {entry.get('id')!r}: requires_custom_nodes must record "
                    "its canonical effective_route, not itself"
                )
        elif entry["effective_route"] != entry["route"]:
            raise ClassificationError(
                f"lock entry {entry.get('id')!r}: effective_route {entry['effective_route']!r} "
                f"diverges from locked route {entry['route']!r} unexpectedly"
            )


def validate_manifest_quotas(manifest: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    """Validate the 50-manifest selection against the lock's hard quotas."""
    lock_by_id = {e["id"]: e for e in lock["entries"]}
    included = [e["id"] for e in manifest["entries"] if e["inclusion_status"] == "included"]
    if len(included) != 50:
        raise ClassificationError(f"manifest must include 50 scenarios, got {len(included)}")

    route_counts = Counter(lock_by_id[s]["route"] for s in included)
    for route, quota in ROUTE_QUOTA.items():
        if route_counts.get(route, 0) != quota:
            raise ClassificationError(
                f"route quota {route}: expected {quota}, got {route_counts.get(route, 0)}"
            )
    behavior_counts = Counter(lock_by_id[s]["behavior"] for s in included)
    for behavior, quota in BEHAVIOR_QUOTA.items():
        if behavior_counts.get(behavior, 0) != quota:
            raise ClassificationError(
                f"behavior quota {behavior}: expected {quota}, got {behavior_counts.get(behavior, 0)}"
            )
    ledger_counts = Counter(lock_by_id[s]["ledger"] for s in included)
    for ledger, quota in LEDGER_QUOTA.items():
        if ledger_counts.get(ledger, 0) != quota:
            raise ClassificationError(
                f"ledger quota {ledger}: expected {quota}, got {ledger_counts.get(ledger, 0)}"
            )
