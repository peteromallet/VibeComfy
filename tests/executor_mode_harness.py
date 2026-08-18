"""Test-only differential harness for the two executor pipeline modes (B06 Pro).

This module is deliberately NOT a production API.  It drives the FULL-mode
pipeline (classify → research → implement → reply) and the two-step pipeline
(classify → bounded execute) through the real ``run_executor`` entrypoint with
the SAME locked :class:`ClassifyDecision` injected via the test-only seam
``vibecomfy.executor.core._run_classify`` (no new production classifier
surface), then normalizes both runs into a comparable :class:`ModeRun`.

The two-step side exercises the REAL :class:`TwoStepSessionStore` — the
named-ingest door and canonical Δ replay (:meth:`TwoStepSessionStore.replay_workflow`)
— by patching ``vibecomfy.executor.two_step._two_step_outcome`` (the
test-injectable outcome boundary named by the task).  The full-mode implement /
reply / research phases are stubbed deterministically.

The invariant the differential tests assert is *never* prose equality: it is
the editable quotient ``pi_edit(post)`` (imported deliberately from
``tests.test_ir_laws``), the accepted-Δ replay, evidence validity, failure
family, and the latency / tokens / cost instrumentation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.executor import agent_backend as agent_backend_module
from vibecomfy.executor import core as executor_core
from vibecomfy.executor import two_step as two_step_module
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecuteReport,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    validate_two_step_final,
)
from vibecomfy.executor.two_step_session import (
    TwoStepSessionStore,
    canonical_workflow_hash,
    normalize_session_id,
)
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.workflow import VibeWorkflow

# Imported deliberately from the law module — it is NOT a production API.
from tests.test_ir_laws import pi_edit  # noqa: E402

# The REAL outcome boundary, captured ONCE at import time so repeated
# ``run_two_step`` calls (which share one monkeypatch across a scenario loop)
# always wrap the genuine production function — never an already-wrapped copy.
_REAL_TWO_STEP_OUTCOME = two_step_module._two_step_outcome

# The REAL bounded-loop entrypoint, likewise captured ONCE at import time: a
# scenario loop that shares ONE monkeypatch would otherwise chain each
# scenario's scripted wrapper around the previous scenario's wrapper, and the
# innermost (first) script would drive every later run.  Each run must drive
# its OWN scripted model turn against the genuine loop.
_REAL_RUN_EXECUTE_TURN = agent_backend_module.run_execute_turn


class NullSchemaProvider:
    """Deterministic, offline schema provider: every class type is ``unknown``.

    Keeps the differential harness offline (``pi_edit`` and ``from_ui`` never
    touch ``api.comfy.org``) while preserving the schema-status dimension of
    the quotient.
    """

    def get_schema(self, class_type: str) -> None:
        del class_type
        return None


_NULL_PROVIDER = NullSchemaProvider()


def to_workflow(raw: dict[str, Any] | None) -> VibeWorkflow | None:
    """Parse a LiteGraph-style raw graph into a :class:`VibeWorkflow` (offline)."""
    if raw is None:
        return None
    return from_ui(
        raw,
        use_comfy_converter=False,
        schema_provider=_NULL_PROVIDER,
    )


def apply_delta(base_raw: dict[str, Any], ops: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Canonical Δ replay over a raw graph — the tests' ORACLE helper.

    The measured two-step replay lives in the store
    (``TwoStepSessionStore.replay_workflow``); this helper exists so the tests
    can compute the quotient the FIXTURE ``scenario.delta_ops`` predicts and
    compare it against the quotient of the ACTUAL accepted ops.
    """
    from vibecomfy.executor.two_step_session import _apply_delta_ops

    return _apply_delta_ops(base_raw, ops)  # type: ignore[return-value]


def _completion_tokens(result: ExecutorResult) -> int:
    attempts = result.report.model_attempts or ()
    total = 0
    for attempt in attempts:
        usage = attempt.get("token_usage")
        if isinstance(usage, dict):
            value = usage.get("completion_tokens")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total += max(0, int(value))
    return total


@dataclass(frozen=True)
class Scenario:
    """One differential scenario: a locked decision + a canonical edit.

    ``delta_ops`` is the CANONICAL ORACLE for the scenario's edit (the
    two-step canonical vocabulary: ``set_node_field`` / ``add_node`` /
    ``remove_node`` / ``upsert_link`` / ``remove_link`` / ``set_mode``).  It is
    NEVER the measured Δ: the harness reads the ACTUAL accepted ops from the
    durable transcript (``accepted_delta_refs[].ops``) and derives the two-step
    post graph from the store's canonical replay; the tests use ``delta_ops``
    only to assert the actual Δ produces the same ``pi_edit`` quotient.
    ``post_raw`` is the hand-authored FULL-mode post-edit graph (the graph
    ``handle_agent_edit`` would produce); the tests assert the two converge on
    the same ``pi_edit`` quotient — never on raw-byte equality.
    """

    name: str
    route: str
    query: str
    decision: ClassifyDecision
    base_raw: dict[str, Any]
    delta_ops: tuple[dict[str, Any], ...] = ()
    post_raw: dict[str, Any] | None = None
    evidence_ids: tuple[str, ...] = ()


@dataclass
class ModeRun:
    """Normalized, prose-free result of one mode run."""

    mode: str
    ok: bool
    post_workflow: VibeWorkflow | None
    pi_edit_quotient: tuple[Any, ...] | None
    accepted_delta_ops: tuple[dict[str, Any], ...]
    replayed_quotient: tuple[Any, ...] | None
    evidence_ids: tuple[str, ...]
    evidence_valid: bool
    failure_kind: str | None
    failure_stage: str | None
    latency_s: float
    tokens: int
    cost_usd: float | None


def _pi_edit_or_none(wf: VibeWorkflow | None) -> tuple[Any, ...] | None:
    if wf is None:
        return None
    return pi_edit(wf, schema_provider=_NULL_PROVIDER)


def _normalize_full(
    result: ExecutorResult, scenario: Scenario, latency_s: float
) -> ModeRun:
    post_workflow = to_workflow(result.graph)
    evidence_ids: tuple[str, ...] = ()
    research = result.report.research
    if research is not None:
        ledger = getattr(research, "ledger", None)
        entries = getattr(ledger, "entries", ()) or ()
        ids: list[str] = []
        for entry in entries:
            for eid in (getattr(entry, "evidence_ids", ()) or ()):
                if eid:
                    ids.append(str(eid))
        evidence_ids = tuple(dict.fromkeys(ids))
    return ModeRun(
        mode="full",
        ok=result.ok,
        post_workflow=post_workflow,
        pi_edit_quotient=_pi_edit_or_none(post_workflow),
        accepted_delta_ops=scenario.delta_ops,
        replayed_quotient=None,  # full mode has no separate Δ replay
        evidence_ids=evidence_ids or scenario.evidence_ids,
        evidence_valid=bool(evidence_ids) and len(evidence_ids) == len(set(evidence_ids)),
        failure_kind=result.failure_kind,
        failure_stage=result.failure_stage,
        latency_s=latency_s,
        tokens=_completion_tokens(result),
        cost_usd=result.report.deepseek_est_cost_usd,
    )


def _session_id(scenario: Scenario) -> str:
    return "win-" + scenario.name.replace(" ", "-").replace("/", "-")


# Offline schemas for the LawNode* fixture types so the REAL EditSession can
# ingest and edit the differential scenarios without touching api.comfy.org.


def _build_law_fixture_schemas() -> dict[str, Any]:
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    return {
        "LawNodeA": NodeSchema("LawNodeA", "law", {}, [OutputSpec("IMAGE", "IMAGE")]),
        "LawNodeB": NodeSchema("LawNodeB", "law", {}, [OutputSpec("IMAGE", "IMAGE")]),
        "LawNodeC": NodeSchema(
            "LawNodeC",
            "law",
            {"image": InputSpec("IMAGE"), "prompt": InputSpec("STRING")},
            [],
        ),
        "LawNodeD": NodeSchema(
            "LawNodeD", "law", {"value": InputSpec("FLOAT")}, []
        ),
    }


class _LawFixtureSchemaProvider:
    """Offline schema provider for the LawNode* differential fixtures."""

    def __init__(self) -> None:
        self._schemas = _build_law_fixture_schemas()

    def get_schema(self, class_type: str) -> Any:
        return self._schemas.get(class_type)


_LAW_FIXTURE_PROVIDER = _LawFixtureSchemaProvider()


def _law_edit_session(graph: Any) -> Any:
    """Build a REAL EditSession for the fixture graph (schema-aware)."""
    from vibecomfy.porting.edit.session import EditSession

    if not graph:
        return None
    return EditSession(dict(graph), schema_provider=_LAW_FIXTURE_PROVIDER)


# Typed edit-tool actions per differential scenario — the canonical Δ translated
# to the typed edit tools.  Most scenarios are a SINGLE edit tool call (one
# edit per message); ``batch-edit`` proves ATOMIC multi-op expressiveness via
# one ``edit_batch`` call lowering to TWO ops under ONE accepted Δ.
_SCENARIO_EDIT_ACTIONS: dict[str, list[dict[str, Any]]] = {
    "named-field edit": [
        {"action": "tool_call", "tool": "edit_node",
         "args": {"target": "lawnodec", "field": "prompt", "value": "after"}},
    ],
    "rewire": [
        {"action": "tool_call", "tool": "upsert_link",
         "args": {"source": "lawnodeb", "source_output": "IMAGE",
                  "target": "lawnodec", "target_input": "image"}},
    ],
    "add-node": [
        {"action": "tool_call", "tool": "add_node",
         "args": {"class_type": "LawNodeD", "widget_values": {"widget_0": 0.25}}},
    ],
    "remove-node": [
        {"action": "tool_call", "tool": "remove_node", "args": {"target": "lawnodeb"}},
    ],
    "remove-link": [
        {"action": "tool_call", "tool": "remove_link",
         "args": {"target": "lawnodec", "target_input": "image"}},
    ],
    "set-node-mode": [
        {"action": "tool_call", "tool": "set_node_mode",
         "args": {"target": "lawnodeb", "mode": "muted"}},
    ],
    "batch-edit": [
        {"action": "tool_call", "tool": "edit_batch",
         "args": {"ops": [
             {"op": "edit_node", "target": "lawnodec", "field": "prompt",
              "value": "batched"},
             {"op": "set_node_mode", "target": "lawnodeb", "mode": "muted"},
         ]}},
    ],
    "adapt": [
        {"action": "tool_call", "tool": "edit_node",
         "args": {"target": "lawnodec", "field": "prompt", "value": "adapted"}},
    ],
    "reorganise": [],
    "inspect": [],
    "research": [],
}


def _scripted_execute_turn(scenario: Scenario, *, delta_id: str = "d1"):
    """Return a ``run_execute_turn`` wrapper that drives the REAL bounded loop.

    Only the model is scripted (typed edit tool call(s) → ``submit`` citing the
    landed Δ); the real :class:`EditSession`, the real ``_two_step_tool_executor``,
    the real :class:`EditToolRuntime` and the real session store all run.
    ``delta_id`` is the Δ id the scripted submit cites — ``d1`` for a fresh
    session, ``d2`` for a follow-up message on a session that already accepted
    ``d1`` (session-wide Δ counter, see the concurrent-edits test).
    """
    import json as _json

    edit_actions = _SCENARIO_EDIT_ACTIONS.get(scenario.name, [])
    actions: list[dict[str, Any]] = list(edit_actions)
    actions.append(
        {
            "action": "submit",
            "reply": "deterministic two-step reply",
            "claim_refs": {"delta_ids": [delta_id] if edit_actions else []},
        }
    )

    def model_turn_fn(task: Any, messages: Any, **kwargs: Any) -> dict[str, Any]:
        action = actions.pop(0) if actions else {
            "action": "submit",
            "reply": "deterministic two-step reply",
            "claim_refs": {"delta_ids": []},
        }
        return {
            "content": _json.dumps(action),
            "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
        }

    def execute_turn(request: Any, **kwargs: Any) -> dict[str, Any]:
        return _REAL_RUN_EXECUTE_TURN(request, model_turn_fn=model_turn_fn, **kwargs)

    return execute_turn


def run_full(scenario: Scenario, monkeypatch: Any) -> ModeRun:
    """Run the FULL pipeline with the locked decision injected."""
    decision = scenario.decision
    monkeypatch.setattr(executor_core, "_run_classify", lambda *a, **k: decision)

    def fake_implement(
        request: ExecutorRequest,
        spec: Any,
        *,
        plan: ClassifyDecision,
        research_result: Any = None,
        client_id: Any = None,
        additive: bool = False,
    ) -> ImplementationResult:
        del request, spec, plan, research_result, client_id, additive
        graph = scenario.post_raw
        return ImplementationResult(
            graph=graph,
            message="deterministic full-mode edit",
            durable_response={"graph": graph} if graph is not None else None,
        )

    monkeypatch.setattr(executor_core, "_run_implement", fake_implement)
    monkeypatch.setattr(
        executor_core, "_run_reply", lambda *a, **k: "deterministic full-mode reply"
    )

    def fake_research_stage(*, route: str, question: str, spec: Any, research_brief: str = ""):
        del route, spec, research_brief
        from vibecomfy.executor.agent_research_stage import AgentResearchTrace
        from vibecomfy.executor.evidence_pack import EvidenceLedger, EvidencePack

        trace = AgentResearchTrace(
            route=scenario.route,
            question=question,
            iterations=(),
            final_verdict="enough",
            summary="deterministic research",
            citations=tuple(scenario.evidence_ids),
            uncertainty="low",
            status="ok",
            elapsed_seconds=0.0,
        )
        from vibecomfy.executor.evidence_pack import EvidenceLedgerEntry, EvidenceArtifact

        entries = (
            EvidenceLedgerEntry(
                decision="agent_research",
                conclusion="deterministic research evidence",
                evidence_ids=tuple(scenario.evidence_ids),
                uncertainty="low",
            ),
        ) if scenario.evidence_ids else ()
        artifacts = {
            eid: EvidenceArtifact(
                evidence_id=eid, kind="hivemind_get", body={"content": "fixture"}, source="hivemind"
            )
            for eid in scenario.evidence_ids
        }
        pack = EvidencePack(artifacts=artifacts, ledger=EvidenceLedger(entries=entries))
        return trace, pack

    monkeypatch.setattr(executor_core, "run_agent_research_stage", fake_research_stage)

    request = ExecutorRequest(
        query=scenario.query,
        graph=scenario.base_raw,
        pipeline_mode="full",
    )
    t0 = time.monotonic()
    result = executor_core.run_executor(request)
    latency_s = time.monotonic() - t0
    return _normalize_full(result, scenario, latency_s)


def run_two_step(
    scenario: Scenario,
    monkeypatch: Any,
    tmp_path: Path,
    *,
    session_id: str | None = None,
    delta_id: str = "d1",
) -> ModeRun:
    """Run the two-step pipeline with the locked decision injected, driving the
    REAL bounded execute loop (real EditSession + real tool dispatcher +
    scripted model emitting ``apply`` → ``submit``).

    Measurement is HONEST (Codex verdict §5): the accepted Δ ops and the post
    graph come from the durable transcript / the store's canonical replay —
    ``TwoStepSessionStore.load`` + ``accepted_delta_refs[].ops`` +
    ``replay_workflow`` / ``retained_workflow`` — NEVER from the fixture
    ``scenario.delta_ops`` or a local re-application of it.  The fixture Δ is
    only an oracle the tests compare the actual Δ against (same quotient).
    """
    decision = scenario.decision
    monkeypatch.setattr(executor_core, "_run_classify", lambda *a, **k: decision)
    # Inject the offline fixture schema into the REAL EditSession seam and
    # script only the model turn — the rest of the bounded loop is real.
    monkeypatch.setattr(two_step_module, "_two_step_edit_session", _law_edit_session)
    monkeypatch.setattr(
        "vibecomfy.executor.agent_backend.run_execute_turn",
        _scripted_execute_turn(scenario, delta_id=delta_id),
    )
    # Isolate the REAL TwoStepSessionStore durable root per test so repeated
    # gate runs never accumulate the 12-apply-batch session ceiling (B06 Pro).
    session_root = tmp_path / "editor_sessions"
    real_two_step_outcome = _REAL_TWO_STEP_OUTCOME

    def _isolated_outcome(
        *,
        request: Any,
        plan: Any,
        pipeline_mode: Any,
        client_id: Any,
        executor_id: Any,
        additive: bool,
    ) -> Any:
        return real_two_step_outcome(
            request=request,
            plan=plan,
            pipeline_mode=pipeline_mode,
            client_id=client_id,
            executor_id=executor_id,
            additive=additive,
            session_root=session_root,
        )

    monkeypatch.setattr(two_step_module, "_two_step_outcome", _isolated_outcome)

    request = ExecutorRequest(
        query=scenario.query,
        graph=scenario.base_raw,
        session_id=session_id if session_id is not None else _session_id(scenario),
        pipeline_mode="two_step",
    )
    t0 = time.monotonic()
    result = executor_core.run_executor(request)
    latency_s = time.monotonic() - t0

    # The durable transcript is the authority: reload the session through the
    # SAME store root the outcome boundary wrote, then read the ACTUAL accepted
    # ops and derive the post graph from the store's canonical replay.
    store = TwoStepSessionStore(session_root)
    sid = normalize_session_id(request.session_id)
    state = store.load(sid)
    assert state is not None, f"two-step run produced no durable session for {sid!r}"
    accepted_delta_ops = tuple(
        op for ref in state.accepted_delta_refs for op in (ref.get("ops") or ())
    )
    replayed_raw = store.replay_workflow(state)
    replayed_quotient = _pi_edit_or_none(to_workflow(replayed_raw))

    # The two-step post graph is the STORE's retained revision — the live
    # emitted graph sidecar when its hash matches the Δ replay, else the replay
    # itself (both come from the store; never a local ``apply_delta`` re-apply).
    # A graph-producing route that landed NO edit (e.g. reorganise's positional
    # furniture, which no typed tool expresses) retains the base revision.
    if state.accepted_delta_refs:
        post_workflow = to_workflow(store.retained_workflow(sid))
    elif scenario.post_raw is not None:
        post_workflow = to_workflow(replayed_raw)
    else:
        post_workflow = None

    return ModeRun(
        mode="two_step",
        ok=result.ok,
        post_workflow=post_workflow,
        pi_edit_quotient=_pi_edit_or_none(post_workflow),
        accepted_delta_ops=accepted_delta_ops,
        replayed_quotient=replayed_quotient,
        evidence_ids=scenario.evidence_ids,
        evidence_valid=True,
        failure_kind=result.failure_kind,
        failure_stage=result.failure_stage,
        latency_s=latency_s,
        tokens=_completion_tokens(result),
        cost_usd=result.report.deepseek_est_cost_usd,
    )


def run_both(scenario: Scenario, monkeypatch: Any, tmp_path: Path) -> tuple[ModeRun, ModeRun]:
    full = run_full(scenario, monkeypatch)
    two = run_two_step(scenario, monkeypatch, tmp_path)
    return full, two


# ── scenario builders ────────────────────────────────────────────────────────


def _base_raw() -> dict[str, Any]:
    """Three-node base graph: A and B feed C (A is the active source)."""
    return {
        "nodes": [
            {
                "id": "1",
                "type": "LawNodeA",
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
                "widgets_values": [],
            },
            {
                "id": "2",
                "type": "LawNodeB",
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [2]}],
                "widgets_values": [],
            },
            {
                "id": "3",
                "type": "LawNodeC",
                "inputs": [{"name": "image", "type": "IMAGE", "link": 1}],
                "outputs": [],
                "widgets_values": ["before"],
            },
        ],
        "links": [
            [1, "1", 0, "3", 0, "IMAGE"],
            [2, "2", 0, "3", 0, "IMAGE"],
        ],
    }


def _node(nid: str, class_type: str, **extra: Any) -> dict[str, Any]:
    node: dict[str, Any] = {"id": nid, "type": class_type, "inputs": [], "outputs": [], "widgets_values": []}
    node.update(extra)
    return node


def named_field_edit() -> Scenario:
    base = _base_raw()
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node("2", "LawNodeB", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [2]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[{"name": "image", "type": "IMAGE", "link": 1}],
                widgets_values=["after"],
            ),
        ],
        "links": base["links"],
    }
    return Scenario(
        name="named-field edit",
        route="revise",
        query="set the prompt field to 'after'",
        decision=ClassifyDecision(route="revise", implement=True, intent="edit", task="edit_graph"),
        base_raw=base,
        delta_ops=(
            {"op": "set_node_field", "target": ["", "3", "widgets_values"], "value": ["after"]},
        ),
        post_raw=post,
    )


def rewire() -> Scenario:
    base = _base_raw()
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node("2", "LawNodeB", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [2]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[{"name": "image", "type": "IMAGE", "link": 2}],
                widgets_values=["before"],
            ),
        ],
        "links": base["links"],
    }
    return Scenario(
        name="rewire",
        route="revise",
        query="rewire node C's image input from A to B",
        decision=ClassifyDecision(route="revise", implement=True, intent="edit", task="edit_graph"),
        base_raw=base,
        delta_ops=(
            {
                "op": "upsert_link",
                "from": ["", "2", "IMAGE"],
                "to": ["", "3", "image"],
            },
        ),
        post_raw=post,
    )


def add_node() -> Scenario:
    base = _base_raw()
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node("2", "LawNodeB", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [2]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[{"name": "image", "type": "IMAGE", "link": 1}],
                widgets_values=["before"],
            ),
            _node("n1", "LawNodeD", widgets_values=[0.25]),
        ],
        "links": base["links"],
    }
    return Scenario(
        name="add-node",
        route="revise",
        query="add a LawNodeD node",
        decision=ClassifyDecision(route="revise", implement=True, intent="edit", task="edit_graph"),
        base_raw=base,
        delta_ops=(
            {"op": "add_node", "uid": "n1", "fields": {"type": "LawNodeD", "widgets_values": [0.25]}},
        ),
        post_raw=post,
    )


def remove_node() -> Scenario:
    base = _base_raw()
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[{"name": "image", "type": "IMAGE", "link": 1}],
                widgets_values=["before"],
            ),
        ],
        "links": [[1, "1", 0, "3", 0, "IMAGE"]],
    }
    return Scenario(
        name="remove-node",
        route="revise",
        query="remove the LawNodeB node",
        decision=ClassifyDecision(route="revise", implement=True, intent="edit", task="edit_graph"),
        base_raw=base,
        delta_ops=(
            {"op": "remove_node", "target": ["", "2"]},
        ),
        post_raw=post,
    )


def remove_link() -> Scenario:
    base = _base_raw()
    # Removing the wire into node C's ``image`` input: BOTH links feed that one
    # input slot, so the input socket ends up unlinked and the two wires drop.
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node("2", "LawNodeB", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [2]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[],
                widgets_values=["before"],
            ),
        ],
        "links": [],
    }
    return Scenario(
        name="remove-link",
        route="revise",
        query="disconnect node C's image input",
        decision=ClassifyDecision(route="revise", implement=True, intent="edit", task="edit_graph"),
        base_raw=base,
        delta_ops=(
            {"op": "remove_link", "to": ["", "3", "image"]},
        ),
        post_raw=post,
    )


def set_node_mode() -> Scenario:
    base = _base_raw()
    # Muting node B is editable: the quotient carries the LiteGraph mode int.
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node("2", "LawNodeB", mode=2, outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [2]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[{"name": "image", "type": "IMAGE", "link": 1}],
                widgets_values=["before"],
            ),
        ],
        "links": base["links"],
    }
    return Scenario(
        name="set-node-mode",
        route="revise",
        query="mute the LawNodeB node",
        decision=ClassifyDecision(route="revise", implement=True, intent="edit", task="edit_graph"),
        base_raw=base,
        delta_ops=(
            {"op": "set_mode", "target": ["", "2"], "mode": 2},
        ),
        post_raw=post,
    )


def batch_edit() -> Scenario:
    base = _base_raw()
    # ONE ``edit_batch`` tool call lowers to TWO ops under ONE accepted Δ:
    # edit_node (prompt → widget channel) + set_node_mode (mode → 2).
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node("2", "LawNodeB", mode=2, outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [2]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[{"name": "image", "type": "IMAGE", "link": 1}],
                widgets_values=["batched"],
            ),
        ],
        "links": base["links"],
    }
    return Scenario(
        name="batch-edit",
        route="revise",
        query="set the prompt to 'batched' and mute node B in one batch",
        decision=ClassifyDecision(route="revise", implement=True, intent="edit", task="edit_graph"),
        base_raw=base,
        delta_ops=(
            {"op": "set_node_field", "target": ["", "3", "widgets_values"], "value": ["batched"]},
            {"op": "set_mode", "target": ["", "2"], "mode": 2},
        ),
        post_raw=post,
    )


def inspect() -> Scenario:
    base = _base_raw()
    return Scenario(
        name="inspect",
        route="inspect",
        query="describe this graph",
        decision=ClassifyDecision(route="inspect", intent="explain_graph", task="inspect_graph"),
        base_raw=base,
        delta_ops=(),
        post_raw=None,
    )


def research() -> Scenario:
    base = _base_raw()
    return Scenario(
        name="research",
        route="research",
        query="research a faster sampler for this graph",
        decision=ClassifyDecision(
            route="research", research=True, intent="research", task="research_nodes"
        ),
        base_raw=base,
        delta_ops=(),
        post_raw=None,
        evidence_ids=("e1",),
    )


def adapt() -> Scenario:
    base = _base_raw()
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node("2", "LawNodeB", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [2]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[{"name": "image", "type": "IMAGE", "link": 1}],
                widgets_values=["adapted"],
            ),
        ],
        "links": base["links"],
    }
    return Scenario(
        name="adapt",
        route="adapt",
        query="adapt the prompt after researching",
        decision=ClassifyDecision(
            route="adapt", research=True, implement=True, intent="edit", task="research_precedent"
        ),
        base_raw=base,
        delta_ops=(
            {"op": "set_node_field", "target": ["", "3", "widgets_values"], "value": ["adapted"]},
        ),
        post_raw=post,
        evidence_ids=("e1",),
    )


def reorganise() -> Scenario:
    base = _base_raw()
    # Position changes are canvas furniture: they must NOT change π_edit.
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node("2", "LawNodeB", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [2]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[{"name": "image", "type": "IMAGE", "link": 1}],
                widgets_values=["before"],
                pos=[999.0, 111.0],
            ),
        ],
        "links": base["links"],
    }
    return Scenario(
        name="reorganise",
        route="reorganise",
        query="move node C to the right",
        decision=ClassifyDecision(
            route="reorganise", implement=True, intent="edit", task="layout_reorganise"
        ),
        base_raw=base,
        # No canonical Δ can express canvas position (there is no typed tool
        # for furniture), so the two-step lands NO edit and the retained
        # revision is the base.  The fixture ``post_raw`` keeps the moved pos
        # for the FULL-mode side only; π_edit must be identical (furniture).
        delta_ops=(),
        post_raw=post,
    )


SCENARIOS: tuple[Scenario, ...] = (
    named_field_edit(),
    rewire(),
    add_node(),
    remove_node(),
    remove_link(),
    set_node_mode(),
    batch_edit(),
    inspect(),
    research(),
    adapt(),
    reorganise(),
)
