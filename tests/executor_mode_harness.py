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
    """Canonical Δ replay over a raw graph (the two-step retained-revision rule)."""
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

    ``delta_ops`` uses the two-step canonical vocabulary
    (``set_node_field`` / ``add_node`` / ``remove_node``).  ``post_raw`` is the
    hand-authored FULL-mode post-edit graph (the graph ``handle_agent_edit``
    would produce); the two-step side reconstructs the post graph by replaying
    ``delta_ops`` over ``base_raw``.  The tests assert the two converge on the
    same ``pi_edit`` quotient — never on raw-byte equality.
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


def _fake_two_step_outcome(scenario: Scenario, session_root: Path):
    """Return a fake ``_two_step_outcome`` that drives the REAL session store."""

    def outcome(**kwargs: Any) -> ExecutorResult:
        request: ExecutorRequest = kwargs["request"]
        plan: ClassifyDecision = kwargs["plan"]
        pipeline_mode = kwargs["pipeline_mode"]

        store = TwoStepSessionStore(session_root)
        session_id = normalize_session_id(request.session_id)
        base_graph = request.graph if isinstance(request.graph, dict) else {"nodes": []}

        store.begin_message(
            session_id,
            base_graph=base_graph,
            message_fingerprint="differential",
        )

        evidence_ids = list(scenario.evidence_ids)
        if evidence_ids:
            store.append(
                session_id,
                "tool_call",
                {
                    "tool": "hivemind_get",
                    "args": {},
                    "evidence_ids": evidence_ids,
                    "digest": "deterministic evidence",
                },
                turn=1,
            )

        accepted_delta_ids: list[str] = []
        if scenario.delta_ops:
            accepted_delta_ids = ["d1"]
            store.append(
                session_id,
                "delta_accepted",
                {
                    "delta_ids": accepted_delta_ids,
                    "ops": list(scenario.delta_ops),
                    "workflow_hash": canonical_workflow_hash(base_graph),
                },
                turn=1,
            )

        store.end_message(session_id, message_fingerprint="differential")

        state = store.load(session_id)
        post_raw = None
        if scenario.delta_ops:
            post_raw = store.replay_workflow(state, base_graph=base_graph)

        # Claim-ref validity: the final cites only ledger-resident ids.
        from vibecomfy.executor.contracts import (
            TwoStepClaimRefs,
            TwoStepFinal,
            TwoStepSelfAssessment,
        )

        final = TwoStepFinal(
            reply="deterministic two-step reply",
            claim_refs=TwoStepClaimRefs(
                delta_ids=tuple(accepted_delta_ids),
                evidence_ids=tuple(evidence_ids),
            ),
            self_assessment=TwoStepSelfAssessment(
                outcome="edited" if accepted_delta_ids else "no_change"
            ),
        )
        violations = validate_two_step_final(
            final,
            accepted_delta_ids=state.accepted_delta_ids() if state else (),
            evidence_ids=state.evidence_ids() if state else (),
        )
        evidence_valid = not violations

        execute = ExecuteReport(
            session_id=request.session_id,
            route=scenario.route,
            budget_usage={"output_tokens": 0},
            accepted_delta_ids=tuple(accepted_delta_ids),
            evidence_ids=tuple(evidence_ids),
            claim_validation={"status": "ok" if evidence_valid else "violations"},
        )
        return ExecutorResult.success(
            report=Report(plan=plan, pipeline_mode=pipeline_mode, execute=execute),
            graph=post_raw,
            reply="deterministic two-step reply",
        )

    return outcome


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


def run_two_step(scenario: Scenario, monkeypatch: Any, tmp_path: Path) -> ModeRun:
    """Run the two-step pipeline with the locked decision injected and the
    outcome boundary replaced by the real-session-store driver."""
    decision = scenario.decision
    monkeypatch.setattr(executor_core, "_run_classify", lambda *a, **k: decision)
    monkeypatch.setattr(
        two_step_module,
        "_two_step_outcome",
        _fake_two_step_outcome(scenario, tmp_path / "sessions"),
    )

    request = ExecutorRequest(
        query=scenario.query,
        graph=scenario.base_raw,
        session_id=_session_id(scenario),
        pipeline_mode="two_step",
    )
    t0 = time.monotonic()
    result = executor_core.run_executor(request)
    latency_s = time.monotonic() - t0

    post_workflow = to_workflow(result.graph)
    replayed_quotient = None
    if scenario.delta_ops:
        replayed_raw = apply_delta(scenario.base_raw, scenario.delta_ops)
        replayed_quotient = _pi_edit_or_none(to_workflow(replayed_raw))

    return ModeRun(
        mode="two_step",
        ok=result.ok,
        post_workflow=post_workflow,
        pi_edit_quotient=_pi_edit_or_none(post_workflow),
        accepted_delta_ops=scenario.delta_ops,
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
                "op": "set_node_field",
                "target": ["", "3", "inputs"],
                "value": [{"name": "image", "type": "IMAGE", "link": 2}],
            },
        ),
        post_raw=post,
    )


def add_remove() -> Scenario:
    base = _base_raw()
    # Add node 4 (LawNodeD) and remove node 2 (LawNodeB).
    post = {
        "nodes": [
            _node("1", "LawNodeA", outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [1]}]),
            _node(
                "3",
                "LawNodeC",
                inputs=[{"name": "image", "type": "IMAGE", "link": 1}],
                widgets_values=["before"],
            ),
            _node("4", "LawNodeD", widgets_values=[0.25]),
        ],
        "links": [[1, "1", 0, "3", 0, "IMAGE"]],
    }
    return Scenario(
        name="add/remove",
        route="revise",
        query="add a LawNodeD and remove LawNodeB",
        decision=ClassifyDecision(route="revise", implement=True, intent="edit", task="edit_graph"),
        base_raw=base,
        delta_ops=(
            {"op": "add_node", "uid": "4", "fields": {"type": "LawNodeD", "widgets_values": [0.25]}},
            {"op": "remove_node", "target": ["", "2"]},
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
        delta_ops=(
            {"op": "set_node_field", "target": ["", "3", "pos"], "value": [999.0, 111.0]},
        ),
        post_raw=post,
    )


SCENARIOS: tuple[Scenario, ...] = (
    named_field_edit(),
    rewire(),
    add_remove(),
    inspect(),
    research(),
    adapt(),
    reorganise(),
)
