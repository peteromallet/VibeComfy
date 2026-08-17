"""B04 — typed two-step final contracts + claim-ref validation.

Covers the four typed final contracts (TwoStepClaimRefs, TwoStepSelfAssessment,
TwoStepFinal, TwoStepExecutionReport) and ``validate_two_step_final`` — the
fail-closed claim-ref authority: delta_ids ⊆ accepted-Δ ledger,
lens_fact_ids ⊆ reply-lens facts, evidence_ids ⊆ tool ledger, edit-success
requires a non-empty accepted Δ, and forged / cross-session references fail
closed.
"""

from __future__ import annotations

from typing import Any

from vibecomfy.executor.contracts import (
    TwoStepClaimRefs,
    TwoStepExecutionReport,
    TwoStepFinal,
    TwoStepSelfAssessment,
    validate_two_step_final,
)


def _final(
    *,
    delta_ids: tuple[str, ...] = (),
    lens_fact_ids: tuple[str, ...] = (),
    evidence_ids: tuple[str, ...] = (),
    outcome: str = "",
) -> TwoStepFinal:
    return TwoStepFinal(
        reply="done",
        claim_refs=TwoStepClaimRefs(
            delta_ids=delta_ids,
            lens_fact_ids=lens_fact_ids,
            evidence_ids=evidence_ids,
        ),
        self_assessment=TwoStepSelfAssessment(outcome=outcome),
    )


# ── typed contract shapes ────────────────────────────────────────────────────


def test_claim_refs_normalize_and_round_trip() -> None:
    refs = TwoStepClaimRefs(delta_ids=["d1"], lens_fact_ids=["f1"], evidence_ids=["e1"])
    assert refs.delta_ids == ("d1",)
    assert refs.lens_fact_ids == ("f1",)
    assert refs.evidence_ids == ("e1",)
    rebuilt = TwoStepClaimRefs.from_mapping(refs.to_dict())
    assert rebuilt == refs


def test_claim_refs_coerce_non_strings() -> None:
    refs = TwoStepClaimRefs(delta_ids=[1, None, "d2"])
    assert refs.delta_ids == ("1", "d2")


def test_final_and_assessment_round_trip() -> None:
    final = _final(delta_ids=("d1",), evidence_ids=("e1",), outcome="edited")
    payload = final.to_dict()
    assert payload["claim_refs"]["delta_ids"] == ["d1"]
    assert payload["self_assessment"]["outcome"] == "edited"
    rebuilt = TwoStepFinal.from_mapping(payload)
    assert rebuilt.reply == final.reply
    assert rebuilt.claim_refs == final.claim_refs
    assert rebuilt.self_assessment == final.self_assessment


def test_execution_report_round_trip_and_freeze() -> None:
    report = TwoStepExecutionReport(
        session_id="sess-1",
        route="revise",
        reply="edited",
        accepted_delta_ids=["d1"],
        evidence_ids=["e1"],
        lens_fact_ids=["f1"],
        replacement_used=True,
        graph={"nodes": []},
        claim_validation={"status": "ok"},
    )
    payload = report.to_dict()
    assert payload["session_id"] == "sess-1"
    assert payload["accepted_delta_ids"] == ["d1"]
    assert payload["graph"] == {"nodes": []}
    assert payload["replacement_used"] is True


def test_execution_report_delta_ids_are_metadata_not_body() -> None:
    report = TwoStepExecutionReport(accepted_delta_ids=["d1"])
    payload = report.to_dict()
    # Delta IDs are metadata pointers; the canonical ops live in the ledger.
    assert "delta" not in payload
    assert payload["accepted_delta_ids"] == ["d1"]


# ── validate_two_step_final ──────────────────────────────────────────────────


def test_valid_final_has_no_violations() -> None:
    final = _final(delta_ids=("d1",), lens_fact_ids=("f1",), evidence_ids=("e1",))
    violations = validate_two_step_final(
        final,
        accepted_delta_ids=("d1",),
        lens_fact_ids=("f1",),
        evidence_ids=("e1",),
    )
    assert violations == ()


def test_forged_delta_id_fails_closed() -> None:
    final = _final(delta_ids=("forged",))
    violations = validate_two_step_final(final, accepted_delta_ids=("d1",))
    assert any("forged" in v for v in violations)


def test_cross_session_delta_id_fails_closed() -> None:
    # A Δ accepted in a DIFFERENT session is never in this session's ledger.
    final = _final(delta_ids=("other-session-d1",))
    violations = validate_two_step_final(final, accepted_delta_ids=("d1",))
    assert any("other-session-d1" in v for v in violations)


def test_forged_evidence_id_fails_closed() -> None:
    final = _final(evidence_ids=("ev-forged",))
    violations = validate_two_step_final(final, evidence_ids=("ev-real",))
    assert any("ev-forged" in v for v in violations)


def test_forged_lens_fact_id_fails_closed() -> None:
    final = _final(lens_fact_ids=("fact-forged",))
    violations = validate_two_step_final(final, lens_fact_ids=("fact-real",))
    assert any("fact-forged" in v for v in violations)


def test_edit_success_requires_nonempty_accepted_delta() -> None:
    final = _final(outcome="edited")
    violations = validate_two_step_final(final, accepted_delta_ids=())
    assert any("accepted Δ" in v for v in violations)


def test_no_change_outcome_does_not_require_delta() -> None:
    final = _final(outcome="no_change")
    violations = validate_two_step_final(final, accepted_delta_ids=())
    assert violations == ()


def test_accepts_raw_mapping_final() -> None:
    violations = validate_two_step_final(
        {
            "reply": "done",
            "claim_refs": {"delta_ids": ["d1"]},
            "self_assessment": {"outcome": "edited"},
        },
        accepted_delta_ids=("d1",),
    )
    assert violations == ()


def test_non_mapping_final_reports_violation() -> None:
    violations = validate_two_step_final(42)  # type: ignore[arg-type]
    assert violations != ()
