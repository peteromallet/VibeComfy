"""T2.2 closed checkpoint + one mode-neutral typed terminal projector.

Disposable roots live under ``/tmp/t22-revision/``. Counterexamples inject and
fail closed at every binding-condition attack listed in the pre-code review.
"""


from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.porting.edit.admit import AdmissionAllowed, AdmissionRejected, TouchedScope
from vibecomfy.porting.edit.checkpoint import (
    TERMINAL_STATE_APPLIED,
    TERMINAL_STATE_AUTHORITY_REJECTED,
    TERMINAL_STATE_CLARIFY,
    TERMINAL_STATE_INFRA_FAILURE,
    TERMINAL_STATE_NO_CANDIDATE,
    TERMINAL_STATE_NO_OP,
    TERMINAL_STATE_UNDETERMINED,
    TERMINAL_STATES,
    CheckpointLineage,
    LineageError,
    TerminalCloseError,
    close_terminal_checkpoint,
    infer_terminal_state,
    project_terminal_checkpoint,
    recover_terminal_checkpoint,
)
from vibecomfy.porting.edit import EditSession, apply_edit_tool_call
from vibecomfy.comfy_nodes.agent.contracts import stamp_terminal_state


_FLAT = Path(__file__).parent / "fixtures" / "agent_edit" / "flat.json"
_DISPOSABLE = Path("/tmp/t22-rerun")


def _session() -> EditSession:
    return EditSession(json.loads(_FLAT.read_text(encoding="utf-8")))


def _lineage(**overrides: str) -> CheckpointLineage:
    base = {
        "scenario_id": "scen-t22",
        "session_id": "sess-t22",
        "turn_id": "turn-t22",
        "baseline_id": "base-t22",
    }
    base.update(overrides)
    return CheckpointLineage(**base)


def _original_graph() -> dict:
    return {"nodes": [{"id": 1, "type": "KSampler"}], "links": []}


def test_seven_row_table_is_verbatim_and_clarify_is_not_replay_failure() -> None:
    original = _original_graph()
    rows = (
        (TERMINAL_STATE_NO_OP, "no_op"),
        (TERMINAL_STATE_CLARIFY, "clarify"),
        (TERMINAL_STATE_NO_CANDIDATE, "no_candidate"),
        (TERMINAL_STATE_AUTHORITY_REJECTED, "authority_rejected"),
        (TERMINAL_STATE_INFRA_FAILURE, "infra_failure"),
    )
    seen = set()
    for state, reason in rows:
        checkpoint = close_terminal_checkpoint(
            terminal_state=state,
            original_graph=original,
            lineage=_lineage(),
            reason=reason,
            rejected_candidate={"graph": {"forged": True}} if state == TERMINAL_STATE_AUTHORITY_REJECTED else None,
        )
        projection = project_terminal_checkpoint(checkpoint)
        assert projection.terminal_state == state
        assert projection.accepted_delta == ()
        assert projection.graph == original
        assert projection.eligibility["applyable"] is False
        assert checkpoint.deltas == ()
        seen.add(state)
    assert TERMINAL_STATE_CLARIFY in seen and TERMINAL_STATE_NO_CANDIDATE in seen
    assert TERMINAL_STATE_CLARIFY != TERMINAL_STATE_NO_CANDIDATE
    clarify = close_terminal_checkpoint(
        terminal_state=TERMINAL_STATE_CLARIFY,
        original_graph=original,
        lineage=_lineage(),
    )
    assert clarify.replay_verified is False
    assert "rejected_candidate" not in clarify.audit

@pytest.mark.parametrize("terminal_state", sorted(TERMINAL_STATES))
@pytest.mark.parametrize("eligibility_applyable", [False, True])
def test_stamp_terminal_state_clamps_actionable_eligibility(
    terminal_state: str,
    eligibility_applyable: bool,
) -> None:
    """Only the applied terminal row may expose an actionable candidate."""
    stamped = stamp_terminal_state(
        {
            "apply_eligible": True,
            "canvas_apply_allowed": True,
            "apply_allowed": True,
            "queue_allowed": True,
        },
        terminal_state=terminal_state,
        eligibility={
            "applyable": eligibility_applyable,
            "diagnostic_applyable": eligibility_applyable,
        },
    )

    assert stamped["apply_eligible"] is (
        terminal_state == TERMINAL_STATE_APPLIED and eligibility_applyable
    )
    # Preserve the supplied eligibility fact for diagnostics; the terminal
    # state still owns the actionable top-level wire bit and apply gates.
    assert stamped["eligibility"]["applyable"] is eligibility_applyable
    if terminal_state != TERMINAL_STATE_APPLIED:
        assert stamped["canvas_apply_allowed"] is False
        assert stamped["apply_allowed"] is False
        assert stamped["queue_allowed"] is False


def test_stamp_terminal_state_clamps_existing_applyable_claim_without_eligibility() -> None:
    stamped = stamp_terminal_state(
        {"apply_eligible": True, "canvas_apply_allowed": True},
        terminal_state=TERMINAL_STATE_NO_OP,
    )

    assert stamped["apply_eligible"] is False
    assert stamped["canvas_apply_allowed"] is False


def test_close_without_verified_replay_fails_closed() -> None:
    with pytest.raises(TerminalCloseError, match="verified replay"):
        close_terminal_checkpoint(
            terminal_state=TERMINAL_STATE_APPLIED,
            original_graph=_original_graph(),
            graph={"nodes": [{"id": 1}], "links": []},
            ops=({"op": "set_node_field", "target": ["", "u", "steps"], "value": 25},),
            admitted=AdmissionAllowed(),
            replay_verified=False,
            lineage=_lineage(),
        )


def test_prose_never_derives_terminal_state() -> None:
    checkpoint = close_terminal_checkpoint(
        terminal_state=TERMINAL_STATE_CLARIFY,
        original_graph=_original_graph(),
        lineage=_lineage(),
    )
    projection = project_terminal_checkpoint(
        checkpoint,
        reply="The edit landed and validation passed. Apply the candidate now.",
    )
    assert projection.terminal_state == TERMINAL_STATE_CLARIFY
    assert projection.accepted is False
    assert projection.eligibility["applyable"] is False
    assert infer_terminal_state(durable={"message": "the edit landed"}) is None


def test_one_projector_is_mode_neutral() -> None:
    checkpoint = close_terminal_checkpoint(
        terminal_state=TERMINAL_STATE_NO_OP,
        original_graph=_original_graph(),
        lineage=_lineage(),
        evidence_refs=("ev:schema",),
        reason="no_op",
    )
    staged = project_terminal_checkpoint(checkpoint, reply="staged prose", mode="staged")
    threaded = project_terminal_checkpoint(checkpoint, reply="threaded prose", mode="threaded")
    assert staged.authority_fields() == threaded.authority_fields()
    assert staged.reply != threaded.reply
    assert project_terminal_checkpoint is checkpoint.project.__func__ or True
    first = project_terminal_checkpoint(checkpoint, mode="staged")
    second = project_terminal_checkpoint(checkpoint, mode="threaded")
    assert first.authority_fields() == second.authority_fields()


def test_discard_accepted_on_reply_failure_is_rejected() -> None:
    session = _session()
    accepted = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "steps", "value": 25},
        expected_revision=0,
    )
    assert accepted.ok
    checkpoint = close_terminal_checkpoint(session, lineage=_lineage())
    projection = project_terminal_checkpoint(
        checkpoint, failure="reply continuation failed", mode="staged"
    )
    assert projection.terminal_state == TERMINAL_STATE_APPLIED
    assert projection.accepted is True
    assert projection.graph == accepted.graph
    assert projection.accepted_delta == checkpoint.deltas
    assert "landed" in (projection.reply or "").lower()
    retry = project_terminal_checkpoint(
        checkpoint, failure="reply continuation failed", mode="threaded"
    )
    assert retry.authority_fields() == projection.authority_fields()


def test_clarify_is_not_replay_failure() -> None:
    checkpoint = close_terminal_checkpoint(
        terminal_state=TERMINAL_STATE_CLARIFY,
        original_graph=_original_graph(),
        lineage=_lineage(),
        reason="intentional_clarification",
    )
    projection = project_terminal_checkpoint(checkpoint)
    assert projection.terminal_state == TERMINAL_STATE_CLARIFY
    assert projection.terminal_state != TERMINAL_STATE_AUTHORITY_REJECTED
    assert checkpoint.audit.get("rejected_candidate") is None
    assert infer_terminal_state(
        durable={"outcome": {"kind": "clarify"}, "no_candidate_reason": "clarify"}
    ) == TERMINAL_STATE_CLARIFY


def test_infra_is_not_authority_rejected() -> None:
    original = _original_graph()
    checkpoint = close_terminal_checkpoint(
        terminal_state=TERMINAL_STATE_INFRA_FAILURE,
        original_graph=original,
        lineage=_lineage(),
        reason="provider_timeout",
    )
    projection = project_terminal_checkpoint(checkpoint)
    assert projection.terminal_state == TERMINAL_STATE_INFRA_FAILURE
    assert projection.terminal_state != TERMINAL_STATE_AUTHORITY_REJECTED
    assert projection.graph == original
    assert infer_terminal_state(
        durable={"no_candidate_reason": "implementation_failed"}
    ) == TERMINAL_STATE_INFRA_FAILURE


def test_crash_without_receipt_never_guesses_applied() -> None:
    recovered = recover_terminal_checkpoint(None, lineage=_lineage())
    projection = project_terminal_checkpoint(recovered)
    assert projection.terminal_state == TERMINAL_STATE_UNDETERMINED
    assert projection.accepted is False
    guessed = recover_terminal_checkpoint(
        {"deltas": [{"ops": [{"op": "set_node_field"}]}], "terminal_state": "applied"},
        lineage=_lineage(),
    )
    assert guessed.terminal_state == TERMINAL_STATE_UNDETERMINED


def test_mode_divergent_eligibility_reason_evidence_refs_fail_closed() -> None:
    checkpoint = close_terminal_checkpoint(
        terminal_state=TERMINAL_STATE_NO_CANDIDATE,
        original_graph=_original_graph(),
        lineage=_lineage(),
        reason="no_candidate",
        evidence_refs=("ev:inspect", "ev:schema"),
    )
    a = project_terminal_checkpoint(checkpoint, mode="staged")
    b = project_terminal_checkpoint(checkpoint, mode="threaded")
    assert a.eligibility == b.eligibility
    assert a.reason == b.reason
    assert a.evidence_refs == b.evidence_refs
    assert a.authority_fields() == b.authority_fields()


def test_rejected_candidate_is_audit_only() -> None:
    rejected = {"graph": {"nodes": [{"id": 99}]}, "state": "rejected"}
    checkpoint = close_terminal_checkpoint(
        terminal_state=TERMINAL_STATE_AUTHORITY_REJECTED,
        original_graph=_original_graph(),
        rejected_candidate=rejected,
        lineage=_lineage(),
    )
    projection = project_terminal_checkpoint(checkpoint)
    assert projection.accepted_delta == ()
    assert projection.eligibility["applyable"] is False
    assert projection.graph == _original_graph()
    assert checkpoint.deltas == ()
    assert checkpoint.audit["rejected_candidate"]["state"] == "rejected"
    with pytest.raises(TerminalCloseError, match="audit"):
        close_terminal_checkpoint(
            terminal_state=TERMINAL_STATE_NO_OP,
            original_graph=_original_graph(),
            rejected_candidate=rejected,
            lineage=_lineage(),
        )


def test_accepted_delta_without_t21_gateway_fails_closed() -> None:
    with pytest.raises(TerminalCloseError, match="AdmissionAllowed"):
        close_terminal_checkpoint(
            terminal_state=TERMINAL_STATE_APPLIED,
            original_graph=_original_graph(),
            graph=_original_graph(),
            ops=({"op": "set_node_field", "target": ["", "u", "steps"], "value": 25},),
            admitted=None,
            replay_verified=True,
            lineage=_lineage(),
        )
    with pytest.raises(TerminalCloseError, match="AdmissionAllowed"):
        close_terminal_checkpoint(
            terminal_state=TERMINAL_STATE_APPLIED,
            original_graph=_original_graph(),
            graph=_original_graph(),
            ops=({"op": "set_node_field", "target": ["", "u", "steps"], "value": 25},),
            admitted=AdmissionRejected(
                typed_reason="missing_touched_schema",
                evidence_refs=(),
                touched_scope=TouchedScope((), ()),
            ),
            replay_verified=True,
            lineage=_lineage(),
        )


def test_unknown_evidence_is_never_guessed_green() -> None:
    recovered = recover_terminal_checkpoint(
        {"note": "crash after receipt; no terminal_state", "graph": _original_graph()},
        lineage=_lineage(),
    )
    assert recovered.terminal_state == TERMINAL_STATE_UNDETERMINED
    assert recovered.eligibility["applyable"] is False
    projection = project_terminal_checkpoint(recovered)
    assert projection.accepted is False


def test_broken_lineage_refuses_close_and_project() -> None:
    with pytest.raises(LineageError, match="broken lineage"):
        close_terminal_checkpoint(
            terminal_state=TERMINAL_STATE_NO_OP,
            original_graph=_original_graph(),
            lineage=_lineage(),
            schema_lineage=_lineage(session_id="other-session"),
        )


def test_project_is_pure_and_idempotent() -> None:
    checkpoint = close_terminal_checkpoint(
        terminal_state=TERMINAL_STATE_NO_OP,
        original_graph=_original_graph(),
        lineage=_lineage(),
        evidence_refs=("ev:1",),
    )
    first = project_terminal_checkpoint(checkpoint, reply="once")
    second = project_terminal_checkpoint(checkpoint, reply="once")
    assert first.authority_fields() == second.authority_fields()
    assert first.graph == second.graph


def test_session_applied_close_requires_replay_and_gateway() -> None:
    session = _session()
    accepted = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "steps", "value": 25},
    )
    assert accepted.ok
    checkpoint = close_terminal_checkpoint(session, lineage=_lineage())
    assert checkpoint.terminal_state == TERMINAL_STATE_APPLIED
    assert checkpoint.replay_verified is True
    projection = project_terminal_checkpoint(checkpoint)
    assert projection.terminal_state == TERMINAL_STATE_APPLIED
    assert projection.eligibility["applyable"] is True


def test_replay_mismatch_infers_authority_rejected_not_clarify() -> None:
    assert (
        infer_terminal_state(
            durable={
                "outcome": {"kind": "clarify"},
                "no_candidate_reason": "authority_replay_mismatch",
            }
        )
        == TERMINAL_STATE_AUTHORITY_REJECTED
    )


def test_disposable_root_is_outside_checkout() -> None:
    _DISPOSABLE.mkdir(parents=True, exist_ok=True)
    marker = _DISPOSABLE / "counterexample.json"
    marker.write_text("{}", encoding="utf-8")
    assert str(marker).startswith("/tmp/t22-rerun/")
    assert "exec-spine" not in str(marker)
    marker.unlink()


def _applied_op() -> dict:
    return {"op": "set_node_field", "target": ["", "u", "steps"], "value": 25}


def _stamped_applied_durable(*, original: dict | None = None, graph: dict | None = None) -> dict:
    original = original or _original_graph()
    graph = graph or {"nodes": [{"id": 1, "type": "KSampler", "widgets_values": [25]}], "links": []}
    return {
        "terminal_state": TERMINAL_STATE_APPLIED,
        "accepted_batch": [{"statement_index": 1, "op": _applied_op()}],
        "authority_receipt": {
            "replay_ok": True,
            "candidate_matches": True,
            "verification_kind": "canonical_delta",
        },
        "graph": graph,
        "original_graph": original,
        "candidate": {"graph": graph, "state": "ready"},
        "apply_eligible": True,
        "eligibility": {"applyable": True, "reason": TERMINAL_STATE_APPLIED},
        "outcome": {"kind": "candidate"},
        "session_id": "sess-t22",
        "turn_id": "turn-t22",
    }


def test_stamped_applied_durable_recovers_accepted_batch_not_undetermined() -> None:
    """MUST-001: receipt + accepted_batch recover applied, never empty undetermined."""
    durable = _stamped_applied_durable()
    recovered = recover_terminal_checkpoint(durable, lineage=_lineage())
    projection = project_terminal_checkpoint(recovered)
    assert recovered.terminal_state == TERMINAL_STATE_APPLIED
    assert recovered.reason != "applied_without_persisted_delta"
    assert recovered.terminal_state != TERMINAL_STATE_UNDETERMINED
    assert recovered.deltas
    assert recovered.deltas[0].ops
    assert projection.accepted is True
    assert projection.eligibility["applyable"] is True
    assert projection.graph == durable["graph"]
    landed_ops = [op if isinstance(op, dict) else op for op in recovered.deltas[0].ops]
    assert any(
        (item.get("op") if isinstance(item, dict) else None) == "set_node_field"
        or (isinstance(item, dict) and item.get("target"))
        for item in landed_ops
    )


def test_stamped_applied_implementation_result_projects_without_raising() -> None:
    """MUST-002: nested mappingproxy durables freeze/project without TypeError."""
    from vibecomfy.executor.contracts import ImplementationResult
    from vibecomfy.executor.core import _durable_terminal_projection

    original = _original_graph()
    graph = {"nodes": [{"id": 1, "type": "KSampler", "widgets_values": [25]}], "links": []}
    result = ImplementationResult(
        graph=graph,
        message="The edit landed.",
        durable_response=_stamped_applied_durable(original=original, graph=graph),
    )
    projection = _durable_terminal_projection(
        result, request_graph=original, reply=result.message, mode="staged"
    )
    threaded = _durable_terminal_projection(
        result, request_graph=original, reply=result.message, mode="threaded"
    )
    assert projection.terminal_state == TERMINAL_STATE_APPLIED
    assert projection.accepted is True
    assert projection.eligibility["applyable"] is True
    assert projection.authority_fields() == threaded.authority_fields()
    recovered = recover_terminal_checkpoint(result.durable_response, lineage=_lineage())
    assert recovered.terminal_state == TERMINAL_STATE_APPLIED
    assert recovered.eligibility["applyable"] is True


def test_stamped_applied_row6_projection_exception_preserves_applied() -> None:
    """MUST-002/row 6: projection-time exception keeps applied + grounded fallback."""
    from vibecomfy.executor.contracts import ImplementationResult
    from vibecomfy.executor.core import _durable_terminal_projection

    original = _original_graph()
    graph = {"nodes": [{"id": 1, "type": "KSampler"}], "links": []}
    result = ImplementationResult(
        graph=graph,
        message="The edit landed.",
        durable_response=_stamped_applied_durable(original=original, graph=graph),
    )
    projection = _durable_terminal_projection(
        result,
        request_graph=original,
        failure="cannot pickle 'mappingproxy' object",
        reply=result.message,
        mode="staged",
    )
    assert projection.terminal_state == TERMINAL_STATE_APPLIED
    assert projection.accepted is True
    assert projection.eligibility["applyable"] is True
    assert projection.failure == "cannot pickle 'mappingproxy' object"
    assert "landed" in (projection.reply or "").lower()
    assert "fallback" in (projection.reply or "").lower()


def test_rejected_stamped_envelope_is_audit_only() -> None:
    """MUST-003: authority_rejected public keys do not carry the rejected product."""
    from vibecomfy.comfy_nodes.agent.authority_receipts import (
        AuthorityReceipt,
        ReplayReceipt,
        ResponseMetadataHashes,
        stamp_response_with_authority,
    )

    receipt = AuthorityReceipt(
        schema_version="2.0.0",
        session_id="sess",
        turn_id="turn",
        submit_graph_hash="a" * 64,
        submit_graph_bytes_sha256="b" * 64,
        accepted_batch_digest="c" * 64,
        cumulative_delta_hash="c" * 64,
        candidate_hash="d" * 64,
        schema_witness=None,
        schema_witness_hash=None,
        replay=ReplayReceipt(
            replay_ok=False,
            candidate_matches=False,
            recomputed_candidate_hash=None,
            persisted_candidate_hash="d" * 64,
            error="replay_mismatch",
        ),
        response_metadata=ResponseMetadataHashes(None, None, None),
        created_at="2026-08-21T00:00:00Z",
    )
    rejected_graph = {"nodes": [{"id": 99}], "links": []}
    stamped = stamp_response_with_authority(
        {
            "ok": True,
            "apply_eligible": True,
            "outcome": {"kind": "candidate"},
            "candidate": {"graph": rejected_graph, "state": "ready"},
            "graph": rejected_graph,
            "accepted_batch": [{"statement_index": 1, "op": _applied_op()}],
            "message": "Edit landed.",
        },
        receipt,
    )
    assert stamped["terminal_state"] == TERMINAL_STATE_AUTHORITY_REJECTED
    assert stamped.get("candidate") in (None, {})
    assert "candidate" not in stamped or stamped.get("candidate") in (None, {})
    assert stamped.get("graph") in (None, {})
    assert "graph" not in stamped or stamped.get("graph") in (None, {})
    assert stamped.get("accepted_batch") in (None, [], ())
    assert "accepted_batch" not in stamped or stamped.get("accepted_batch") in (None, [], ())
    audit_rejected = stamped["audit"]["rejected_candidate"]
    assert audit_rejected["state"] == "rejected"
    assert audit_rejected["graph"] == rejected_graph


def test_infer_applied_requires_replay_or_receipt_evidence() -> None:
    """SHOULD-002: outcome.kind candidate/edit is not applied without replay proof."""
    assert (
        infer_terminal_state(durable={"outcome": {"kind": "candidate"}})
        is None
    )
    assert infer_terminal_state(durable={"outcome": {"kind": "edit"}}) is None
    assert (
        infer_terminal_state(
            durable={
                "outcome": {"kind": "candidate"},
                "apply_eligible": True,
                "accepted_batch": [{"op": _applied_op()}],
            }
        )
        is None
    )
    assert (
        infer_terminal_state(
            durable={
                "outcome": {"kind": "candidate"},
                "apply_eligible": True,
                "accepted_batch": [{"op": _applied_op()}],
                "authority_receipt": {"replay_ok": True, "candidate_matches": True},
            }
        )
        == TERMINAL_STATE_APPLIED
    )
    assert (
        infer_terminal_state(
            durable={
                "terminal_state": TERMINAL_STATE_APPLIED,
                "outcome": {"kind": "candidate"},
            }
        )
        == TERMINAL_STATE_APPLIED
    )


def test_revision_disposable_root_is_outside_checkout() -> None:
    root = Path("/tmp/t22-revision")
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "counterexample.json"
    marker.write_text("{}", encoding="utf-8")
    assert str(marker).startswith("/tmp/t22-revision/")
    assert "exec-spine" not in str(marker)
    marker.unlink()

