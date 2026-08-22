"""T5.1 artifact lineage manifest — failure-injection proofs.

Covers:
* every required lineage link is present for a representative
  scenario/session/turn/baseline (primary or typed fallback);
* a fallback row is distinguishable from a genuine candidate: typed reason,
  never a digest, and the validator rejects digest-carrying fallbacks;
* the manifest digest is tamper-evident;
* the executor-side builder produces a complete manifest from typed turn
  evidence, including the applied-edit happy path and the no-candidate path;
* the assessor flags fallback-impersonation when an envelope claims a landed
  edit while its lineage rows are typed fallbacks, and flags scenario-binding
  mismatches (stale-path / cross-turn assessment).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live_agentic_harness.lineage_check import (
    assess_artifact_lineage,
    load_artifact_lineage,
)
from vibecomfy.comfy_nodes.agent.artifact_lineage import (
    ARTIFACT_LINEAGE_SCHEMA_VERSION,
    ArtifactLineageError,
    FALLBACK_REASONS,
    LINK_KINDS,
    build_artifact_lineage,
    canonical_lineage_digest,
    fallback_row,
    primary_row,
    validate_artifact_lineage,
)

_SHA = "a" * 64


def _fallback_reason(kind: str) -> str:
    return sorted(FALLBACK_REASONS[kind])[0]


def _manifest(lineage: dict | None = None, rows: list | None = None) -> dict:
    return build_artifact_lineage(
        lineage=lineage
        or {"scenario_id": "s1", "session_id": "sess", "turn_id": "0001", "baseline_id": "0000"},
        rows=rows or [fallback_row(kind, _fallback_reason(kind)) for kind in LINK_KINDS],
    )


# ── structural completeness ──────────────────────────────────────────────────


def test_manifest_covers_every_required_link_kind() -> None:
    manifest = _manifest()
    kinds = [row["kind"] for row in manifest["rows"]]
    assert sorted(kinds) == sorted(LINK_KINDS)
    assert manifest["schema_version"] == ARTIFACT_LINEAGE_SCHEMA_VERSION
    assert manifest["lineage"] == {
        "scenario_id": "s1",
        "session_id": "sess",
        "turn_id": "0001",
        "baseline_id": "0000",
    }


def test_incomplete_manifest_is_rejected() -> None:
    rows = [fallback_row(k, _fallback_reason(k)) for k in LINK_KINDS[:-1]]
    with pytest.raises(ArtifactLineageError, match="incomplete"):
        build_artifact_lineage(lineage={"session_id": "s"}, rows=rows)


def test_duplicate_kind_is_rejected() -> None:
    rows = [fallback_row(k, _fallback_reason(k)) for k in LINK_KINDS]
    rows.append(fallback_row("candidate", "no_candidate_built"))
    with pytest.raises(ArtifactLineageError, match="duplicate"):
        build_artifact_lineage(lineage={"session_id": "s"}, rows=rows)


# ── fallback rows can never impersonate evidence ─────────────────────────────


def test_fallback_row_has_reason_and_never_a_digest() -> None:
    row = fallback_row("candidate", "no_candidate_built")
    assert row == {"kind": "candidate", "row_class": "fallback", "reason": "no_candidate_built"}
    assert "digest" not in row


def test_fallback_row_rejects_free_form_reason() -> None:
    with pytest.raises(ArtifactLineageError, match="typed vocabulary"):
        fallback_row("candidate", "trust me this is the candidate")


def test_fallback_row_rejects_digest_smuggling() -> None:
    with pytest.raises(ArtifactLineageError, match="never carry a digest"):
        fallback_row("candidate", "no_candidate_built", detail=None) if False else None
        # Direct construction path used by the guard:
        from vibecomfy.comfy_nodes.agent.artifact_lineage import _validated_row

        _validated_row(kind="candidate", row_class="fallback", reason="no_candidate_built", digest=_SHA)


def test_primary_row_requires_real_sha256() -> None:
    with pytest.raises(ArtifactLineageError, match="64-hex"):
        primary_row("candidate", "delta:abc123")
    with pytest.raises(ArtifactLineageError, match="requires a digest"):
        primary_row("candidate", "")


def test_primary_row_cannot_carry_reason() -> None:
    with pytest.raises(ArtifactLineageError, match="must not carry a reason"):
        primary_row("candidate", _SHA, detail=None) if False else None
        from vibecomfy.comfy_nodes.agent.artifact_lineage import _validated_row

        _validated_row(kind="candidate", row_class="primary", digest=_SHA, reason="no_candidate_built")


# ── tamper evidence ──────────────────────────────────────────────────────────


def test_manifest_digest_is_tamper_evident() -> None:
    manifest = _manifest()
    ok, error = validate_artifact_lineage(manifest)
    assert ok, error
    tampered = json.loads(json.dumps(manifest))
    tampered["lineage"]["session_id"] = "forged-session"
    ok, error = validate_artifact_lineage(tampered)
    assert not ok
    assert "manifest_digest" in error


def test_validate_rejects_non_manifest_garbage() -> None:
    assert validate_artifact_lineage({"graph": {"nodes": []}})[0] is False
    assert validate_artifact_lineage("candidate")[0] is False
    assert validate_artifact_lineage(None)[0] is False


# ── executor-side build: representative applied-edit turn ────────────────────


def _executor_request(scenario_id: str = "audio-tts-narration-using-indextts-2"):
    from vibecomfy.executor.contracts import ExecutorRequest

    return ExecutorRequest(
        query="set the narration seed to 7",
        graph={"nodes": [{"id": 1}]},
        session_id="sess-live",
        scenario_id=scenario_id,
    )


def _durable_applied() -> dict:
    return {
        "session_id": "sess-live",
        "turn_id": "0007",
        "baseline_turn_id": "0006",
        "workflow_source_digest": "b" * 64,
        "workflow_semantic_digest": "c" * 64,
        "workflow_source_representation": "ui",
        "accepted_batch": [
            {
                "ok": True,
                "landed": True,
                "op": {
                    "op": "set_node_field",
                    "target": ["", "1", "seed"],
                    "value": 7,
                },
            }
        ],
        "candidate": {"transaction_id": "tx-1", "graph": {"nodes": []}},
        "authority_receipt": {"replay_ok": True, "candidate_matches": True},
    }


def test_builder_emits_complete_manifest_with_primary_product_rows(monkeypatch) -> None:
    from vibecomfy.executor.contracts import ImplementationResult
    from vibecomfy.executor.core import _build_artifact_lineage_manifest

    monkeypatch.delenv("VIBECOMFY_SOURCE_COMMIT", raising=False)
    request = _executor_request()
    implementation = ImplementationResult(
        graph={"nodes": []},
        message="done",
        durable_response=_durable_applied(),
    )
    manifest = _build_artifact_lineage_manifest(
        request,
        plan=None,
        research=None,
        implementation_result=implementation,
        model_attempts=(
            {"model": "deepseek-v4-pro", "provider": "openrouter", "transport": "openrouter"},
        ),
        orchestration_mode="staged",
    )
    assert manifest is not None
    ok, error = validate_artifact_lineage(manifest)
    assert ok, error
    rows = {row["kind"]: row for row in manifest["rows"]}
    assert rows["candidate"]["row_class"] == "primary"
    assert rows["accepted_delta"]["row_class"] == "primary"
    assert rows["replay_proof"]["row_class"] == "primary"
    assert rows["workflow_snapshot"]["row_class"] == "primary"
    assert rows["source_representation"]["detail"] == "ui"
    assert rows["model_provider_transport"]["row_class"] == "primary"
    assert rows["terminal_response"]["row_class"] == "primary"
    # Lineage binding: scenario from the request, session/turn/baseline from
    # the durable payload.
    assert manifest["lineage"]["scenario_id"] == "audio-tts-narration-using-indextts-2"
    assert manifest["lineage"]["session_id"] == "sess-live"
    assert manifest["lineage"]["turn_id"] == "0007"
    assert manifest["lineage"]["baseline_id"] == "0006"
    # Unavailable links are typed fallbacks with reasons, not fabricated digests.
    assert rows["source_commit"] == {
        "kind": "source_commit",
        "row_class": "fallback",
        "reason": "unavailable_no_source_commit_evidence",
    }
    assert rows["assessment"]["reason"] == "assessment_pending"


def test_builder_records_source_commit_from_env(monkeypatch) -> None:
    from vibecomfy.executor.core import _build_artifact_lineage_manifest

    monkeypatch.setenv("VIBECOMFY_SOURCE_COMMIT", "f" * 40)
    manifest = _build_artifact_lineage_manifest(
        _executor_request(),
        plan=None,
        research=None,
        implementation_result=None,
        model_attempts=(),
        orchestration_mode="staged",
    )
    rows = {row["kind"]: row for row in manifest["rows"]}
    assert rows["source_commit"]["row_class"] == "primary"
    assert rows["source_commit"]["detail"] == "f" * 40


def test_builder_never_raises_on_garbage_durable(monkeypatch) -> None:
    from vibecomfy.executor.core import _build_artifact_lineage_manifest

    monkeypatch.delenv("VIBECOMFY_SOURCE_COMMIT", raising=False)
    manifest = _build_artifact_lineage_manifest(
        _executor_request(),
        plan=None,
        research=None,
        implementation_result=None,
        model_attempts=(),
        orchestration_mode="staged",
    )
    ok, error = validate_artifact_lineage(manifest)
    assert ok, error
    rows = {row["kind"]: row for row in manifest["rows"]}
    assert rows["candidate"]["row_class"] == "fallback"
    assert rows["candidate"]["reason"] in FALLBACK_REASONS["candidate"]
    assert "digest" not in rows["candidate"]


# ── assessor-side checks ─────────────────────────────────────────────────────


def _landed_edit_response() -> dict:
    return {
        "ok": True,
        "graph_unchanged": False,
        "change_details": {"landed_operation_count": 1},
        "gates": {"queue_validate_ok": True},
        "report": {"executor": {}},
    }


def test_assessor_flags_fallback_impersonation_on_landed_edit(tmp_path: Path) -> None:
    manifest = _manifest()  # all rows are typed fallbacks
    (tmp_path / "artifact_lineage.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = assess_artifact_lineage(tmp_path, _landed_edit_response(), {"id": "s1"})
    checks = {issue["check"] for issue in result["issues"]}
    assert "artifact_lineage_fallback_impersonation" in checks
    assert any(issue["severity"] == "error" for issue in result["issues"])


def test_assessor_flags_scenario_binding_mismatch(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["binding"] = {"scenario_id": "other-scenario", "pipeline_mode": "staged"}
    (tmp_path / "artifact_lineage.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = assess_artifact_lineage(tmp_path, {"ok": True}, {"id": "s1"})
    assert any(
        issue["check"] == "artifact_lineage_binding" and issue["severity"] == "error"
        for issue in result["issues"]
    )


def test_assessor_accepts_valid_bound_manifest(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["binding"] = {"scenario_id": "s1", "pipeline_mode": "threaded"}
    (tmp_path / "artifact_lineage.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = assess_artifact_lineage(tmp_path, {"ok": True, "graph_unchanged": True}, {"id": "s1"})
    assert result["present"] is True
    assert result["manifest_digest"] == manifest["manifest_digest"]
    assert result["binding"]["pipeline_mode"] == "threaded"
    assert result["issues"] == []


def test_assessor_records_absence_without_fabricating(tmp_path: Path) -> None:
    result = assess_artifact_lineage(tmp_path, {"ok": True}, {"id": "s1"})
    assert result["present"] is False
    assert result["provenance"] == "absent"
    assert result["issues"] == []


def test_assessor_flags_corrupted_manifest(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["rows"] = manifest["rows"][:-1]  # drop a row, keep stale digest
    (tmp_path / "artifact_lineage.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = assess_artifact_lineage(tmp_path, {"ok": True}, {"id": "s1"})
    assert any(
        issue["check"] == "artifact_lineage" and issue["severity"] == "error"
        for issue in result["issues"]
    )


def test_load_prefers_sidecar_over_envelope(tmp_path: Path) -> None:
    manifest = _manifest()
    (tmp_path / "artifact_lineage.json").write_text(json.dumps(manifest), encoding="utf-8")
    envelope_response = {
        "report": {"executor": {"artifact_lineage": {"schema_version": "bogus"}}}
    }
    loaded, provenance = load_artifact_lineage(tmp_path, envelope_response)
    assert provenance == "sidecar"
    assert loaded["manifest_digest"] == manifest["manifest_digest"]
