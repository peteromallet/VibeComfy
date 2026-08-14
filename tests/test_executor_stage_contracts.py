"""F01 contract tests for typed agent-stage handoffs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.executor.evidence_pack import (
    EvidenceArtifact,
    EvidenceLedger,
    EvidenceLedgerEntry,
    EvidencePack,
    MAX_LEDGER_CONCLUSION_CHARS,
    canonical_json,
)
from vibecomfy.executor.stage_contracts import (
    NeedsInput,
    StageDiagnostic,
    StagePackage,
    StageRequest,
    validate_stage_handoff,
)
from vibecomfy.executor.tool_contracts import TOOL_STATUSES, ToolResult, ToolStatus


SCHEMAS = Path(__file__).parents[1] / "vibecomfy" / "executor" / "schemas"


def _artifact() -> EvidenceArtifact:
    return EvidenceArtifact(
        evidence_id="ev:hivemind:42",
        kind="hivemind_record",
        source="hivemind",
        body={
            "title": "Wan audio conditioning precedent",
            "full_source_body": "A deliberately large body would live here.",
        },
        metadata={"fetched_at": "2026-08-14T12:00:00Z"},
    )


def _package(*, status: str = "ok") -> StagePackage:
    artifact = _artifact()
    return StagePackage(
        stage_id="research",
        produced_at="2026-08-14T14:00:00+02:00",
        artifacts={artifact.evidence_id: artifact},
        diagnostics=(
            StageDiagnostic(
                code="source_inspected",
                message="The cited record was inspected.",
                severity="info",
                evidence_ids=(artifact.evidence_id,),
                details={"tool": "hivemind_get"},
            ),
        ),
        status=status,
        next_stage_hints=("Use the supported audio-conditioning chain.",),
        ledger=EvidenceLedger(entries=(
            EvidenceLedgerEntry(
                decision="Choose an audio-conditioning chain.",
                conclusion="Use the inspected Wan precedent.",
                evidence_ids=(artifact.evidence_id,),
                uncertainty="Runtime node availability still needs a schema probe.",
            ),
        )),
    )


def _request(*, priorities: tuple[str, ...] = ("Preserve the current graph.",)) -> StageRequest:
    return StageRequest(
        goal="Add audio conditioning to the current Wan workflow.",
        priorities=priorities,
        route="adapt",
        interaction_mode="interactive",
        previous_package_refs=("research:1",),
    )


def test_stage_request_round_trip_is_deterministic_and_json_safe() -> None:
    request = _request()
    wire = request.to_dict()

    encoded = json.dumps(wire, sort_keys=True, separators=(",", ":"), allow_nan=False)
    restored = StageRequest.from_dict(json.loads(encoded))

    assert restored.to_dict() == wire
    assert canonical_json(restored) == encoded


def test_stage_package_round_trip_is_deterministic_and_json_safe() -> None:
    package = _package()
    wire = package.to_dict()

    encoded = json.dumps(wire, sort_keys=True, separators=(",", ":"), allow_nan=False)
    restored = StagePackage.from_dict(json.loads(encoded))

    assert restored.to_dict() == wire
    assert restored.produced_at == "2026-08-14T12:00:00Z"
    assert canonical_json(restored) == encoded


@pytest.mark.parametrize("missing", ["goal", "priorities", "previous_package_refs"])
def test_stage_request_rejects_missing_goal_priority_or_package(missing: str) -> None:
    payload = _request().to_dict()
    payload.pop(missing)

    with pytest.raises(ValueError, match="missing required field"):
        StageRequest.from_dict(payload)


def test_stage_handoff_rejects_unresolved_previous_package_ref() -> None:
    with pytest.raises(ValueError, match="Unresolved previous package ref"):
        validate_stage_handoff(_request(), {})


def test_stage_package_rejects_unresolved_ledger_evidence_id() -> None:
    with pytest.raises(ValueError, match="unresolved evidence ID"):
        StagePackage(
            stage_id="research",
            produced_at="2026-08-14T12:00:00Z",
            artifacts={},
            diagnostics=(),
            status="ok",
            next_stage_hints=(),
            ledger=EvidenceLedger(entries=(
                EvidenceLedgerEntry(
                    decision="Choose a chain.",
                    conclusion="Use precedent.",
                    evidence_ids=("ev:missing",),
                    uncertainty="",
                ),
            )),
        )


def test_stage_package_rejects_unresolved_diagnostic_and_needs_input_ids() -> None:
    for kwargs in (
        {
            "diagnostics": (
                StageDiagnostic(
                    code="missing",
                    message="Missing evidence.",
                    evidence_ids=("ev:missing",),
                ),
            ),
        },
        {
            "needs_input": NeedsInput(
                decision="Pick a model family.",
                question="Which model family should be used?",
                missing_information=("model family",),
                evidence_ids=("ev:missing",),
            ),
        },
    ):
        values = {
            "stage_id": "classify",
            "produced_at": "2026-08-14T12:00:00Z",
            "artifacts": {},
            "diagnostics": (),
            "status": "ok",
            "next_stage_hints": (),
        }
        values.update(kwargs)
        with pytest.raises(ValueError, match="unresolved evidence ID"):
            StagePackage(**values)


def test_changing_priority_alone_cannot_change_deterministic_gate_result() -> None:
    package = _package()
    packages = {"research:1": package}
    preserve = validate_stage_handoff(
        _request(priorities=("Preserve existing nodes.",)), packages
    )
    simplify = validate_stage_handoff(
        _request(priorities=("Prefer the simplest graph.",)), packages
    )

    assert dict(preserve) == dict(simplify)
    json.dumps(preserve, allow_nan=False)
    assert _request(priorities=("A",)).deterministic_gate_digest() == _request(
        priorities=("B",)
    ).deterministic_gate_digest()


def test_deterministic_gate_digest_still_binds_the_goal() -> None:
    original = _request()
    different_goal = StageRequest(
        goal="Explain the current Wan workflow without editing it.",
        priorities=original.priorities,
        route=original.route,
        interaction_mode=original.interaction_mode,
        previous_package_refs=original.previous_package_refs,
    )

    assert original.deterministic_gate_digest() != different_goal.deterministic_gate_digest()


def test_full_source_bodies_live_only_behind_evidence_ids() -> None:
    package = _package().to_dict()
    ledger_entry = package["ledger"]["entries"][0]

    assert set(ledger_entry) == {
        "decision",
        "conclusion",
        "evidence_ids",
        "uncertainty",
    }
    assert "full_source_body" not in json.dumps(ledger_entry)
    assert (
        package["artifacts"]["ev:hivemind:42"]["body"]["full_source_body"]
        == "A deliberately large body would live here."
    )

    polluted = dict(ledger_entry, body="source dump")
    with pytest.raises(ValueError, match="unknown field.*body"):
        EvidenceLedgerEntry.from_dict(polluted)
    with pytest.raises(ValueError, match="compact ledger limit"):
        EvidenceLedgerEntry(
            decision="Summarize one source.",
            conclusion="x" * (MAX_LEDGER_CONCLUSION_CHARS + 1),
            evidence_ids=("ev:hivemind:42",),
            uncertainty="",
        )


def test_evidence_pack_round_trip_resolves_ledger_references() -> None:
    package = _package()
    pack = EvidencePack(artifacts=package.artifacts, ledger=package.ledger)
    restored = EvidencePack.from_dict(json.loads(json.dumps(pack.to_dict())))

    assert restored.to_dict() == pack.to_dict()


def test_no_results_ledger_may_record_a_conclusion_without_source_ids() -> None:
    package = StagePackage(
        stage_id="research",
        produced_at="2026-08-14T12:00:00Z",
        artifacts={},
        diagnostics=(),
        status="no_results",
        next_stage_hints=("Ask whether to broaden the research question.",),
        ledger=EvidenceLedger(entries=(
            EvidenceLedgerEntry(
                decision="Find an exact precedent.",
                conclusion="No matching precedent was returned.",
                evidence_ids=(),
                uncertainty="Absence of a result is not evidence of impossibility.",
            ),
        )),
    )

    assert package.status is ToolStatus.NO_RESULTS
    assert package.ledger.entries[0].evidence_ids == ()


def test_needs_input_is_a_typed_decision_critical_package() -> None:
    clarification = NeedsInput(
        decision="Choose the checkpoint family before authoring nodes.",
        question="Should this target Wan 2.1 or Wan 2.2?",
        missing_information=("target checkpoint family",),
        options=("Wan 2.1", "Wan 2.2"),
        bounded_assumption="Use Wan 2.2 in unattended mode.",
    )

    assert NeedsInput.from_dict(clarification.to_dict()) == clarification
    with pytest.raises(ValueError, match="at least one"):
        NeedsInput(
            decision="Choose a model.",
            question="Which model?",
            missing_information=(),
        )


@pytest.mark.parametrize("status", sorted(TOOL_STATUSES))
def test_tool_statuses_round_trip_without_collapsing_failures(status: str) -> None:
    result = ToolResult(
        tool_name="hivemind_search",
        status=status,
        result={"items": []},
        evidence_ids=(),
        diagnostics=(),
        retry_after_seconds=3 if status == "rate_limited" else None,
    )

    restored = ToolResult.from_dict(json.loads(json.dumps(result.to_dict())))
    assert restored.status.value == status


def test_rate_limit_timeout_and_unavailable_are_not_no_results() -> None:
    failure_statuses = {
        ToolResult(tool_name="lookup", status=status).status
        for status in ("rate_limited", "timeout", "unavailable")
    }

    assert ToolStatus.NO_RESULTS not in failure_statuses
    assert failure_statuses == {
        ToolStatus.RATE_LIMITED,
        ToolStatus.TIMEOUT,
        ToolStatus.UNAVAILABLE,
    }


def test_contracts_reject_non_json_safe_values() -> None:
    with pytest.raises(ValueError, match="JSON-safe"):
        EvidenceArtifact(evidence_id="ev:1", kind="record", body={"bad": {1, 2}})
    with pytest.raises(ValueError, match="NaN"):
        ToolResult(tool_name="lookup", status="ok", result=float("nan"))
    with pytest.raises(ValueError, match="finite"):
        ToolResult(
            tool_name="lookup",
            status="rate_limited",
            retry_after_seconds=float("inf"),
        )


def test_json_schemas_are_valid_json_and_freeze_required_wire_fields() -> None:
    expected = {
        "evidence_pack.schema.json",
        "needs_input.schema.json",
        "stage_package.schema.json",
        "stage_request.schema.json",
        "tool_result.schema.json",
    }
    schemas = {path.name: json.loads(path.read_text()) for path in SCHEMAS.glob("*.json")}

    assert set(schemas) == expected
    assert set(schemas["stage_request.schema.json"]["required"]) >= {
        "goal", "priorities", "previous_package_refs"
    }
    assert schemas["stage_package.schema.json"]["properties"]["status"]["$ref"]
    ledger_properties = schemas["evidence_pack.schema.json"]["$defs"][
        "evidence_ledger_entry"
    ]["properties"]
    assert "body" not in ledger_properties
