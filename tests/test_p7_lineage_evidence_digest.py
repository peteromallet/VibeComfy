"""P7-LINEAGE-EVIDENCE Sub-fix A focused tests — digest-mismatch severity.

``manifest_digest does not match manifest content`` used to be ERROR-severity
in ``assess_artifact_lineage`` even on G1 legs whose product checks all pass,
unfairly failing the leg.  After the fix:

* (a) the mismatch on an otherwise-clean leg surfaces as WARNING and carries
  no error — the assessment cannot fail the leg by itself;
* (b) the SAME mismatch alongside ANY failing check stays ERROR-severity:
  binding-scenario mismatch, cross-turn session/turn identity mismatch, and
  fallback impersonation on a landed-edit claim;
* every OTHER invalid-manifest shape keeps its hard error (no demotion).
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.live_agentic_harness.lineage_check import assess_artifact_lineage
from vibecomfy.comfy_nodes.agent.artifact_lineage import (
    FALLBACK_REASONS,
    LINK_KINDS,
    build_artifact_lineage,
    fallback_row,
)


def _fallback_reason(kind: str) -> str:
    return sorted(FALLBACK_REASONS[kind])[0]


def _manifest() -> dict:
    return build_artifact_lineage(
        lineage={
            "scenario_id": "s1",
            "session_id": "sess",
            "turn_id": "0001",
            "baseline_id": "0000",
        },
        rows=[fallback_row(kind, _fallback_reason(kind)) for kind in LINK_KINDS],
    )


def _envelope_response(manifest: dict | None = None, **extra) -> dict:
    executor: dict = {}
    if manifest is not None:
        executor["artifact_lineage"] = json.loads(json.dumps(manifest))
    response: dict = {"ok": True, "report": {"executor": executor}}
    response.update(extra)
    return response


def _stale_digest(manifest: dict) -> dict:
    """Mutate digest-participating content WITHOUT re-sealing the digest.

    Mirrors the production corruption seen on the G1 legs: the manifest body
    changed after ``manifest_digest`` was computed, so validation fails with
    exactly "manifest_digest does not match manifest content" while every
    structural contract still holds.  The mutation targets a row detail so
    no binding/identity check is disturbed.
    """
    for row in manifest["rows"]:
        if row["kind"] == "terminal_response":
            row["detail"] = "post-seal evidence refresh"
            break
    else:  # pragma: no cover - vocabulary always contains terminal_response
        raise AssertionError("terminal_response row missing")
    return manifest


# ── (a): stale digest alone can no longer fail a clean leg ──────────────────


def test_digest_mismatch_alone_demotes_to_warning(tmp_path: Path) -> None:
    manifest = _stale_digest(_manifest())
    manifest["binding"] = {"scenario_id": "s1", "pipeline_mode": "staged"}
    (tmp_path / "artifact_lineage.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    result = assess_artifact_lineage(tmp_path, _envelope_response(manifest), {"id": "s1"})
    assert result["present"] is True
    severities = [issue["severity"] for issue in result["issues"]]
    assert "error" not in severities, result["issues"]
    assert severities == ["warning"]
    issue = result["issues"][0]
    assert issue["check"] == "artifact_lineage"
    assert "manifest_digest does not match manifest content" in issue["detail"]
    assert "demoted to warning" in issue["detail"]


# ── (b): any failing product check keeps the mismatch an error ──────────────


def test_digest_mismatch_with_binding_mismatch_stays_error(tmp_path: Path) -> None:
    manifest = _stale_digest(_manifest())
    manifest["binding"] = {"scenario_id": "other-scenario", "pipeline_mode": "staged"}
    (tmp_path / "artifact_lineage.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    result = assess_artifact_lineage(
        tmp_path, _envelope_response(manifest), {"id": "s1"}
    )
    checks = {(issue["check"], issue["severity"]) for issue in result["issues"]}
    assert ("artifact_lineage_binding", "error") in checks
    assert ("artifact_lineage", "error") in checks


def test_digest_mismatch_with_turn_identity_mismatch_stays_error(
    tmp_path: Path,
) -> None:
    manifest = _stale_digest(_manifest())
    manifest["binding"] = {"scenario_id": "s1", "pipeline_mode": "threaded"}
    (tmp_path / "artifact_lineage.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    response = _envelope_response(manifest, session_id="sess-new", turn_id="turn-new")
    result = assess_artifact_lineage(tmp_path, response, {"id": "s1"})
    identity_errors = [
        issue
        for issue in result["issues"]
        if issue["check"] == "artifact_lineage_binding"
        and issue["severity"] == "error"
    ]
    assert identity_errors
    assert any(
        issue["check"] == "artifact_lineage" and issue["severity"] == "error"
        for issue in result["issues"]
    )


def test_digest_mismatch_with_fallback_impersonation_stays_error(
    tmp_path: Path,
) -> None:
    manifest = _stale_digest(_manifest())  # every row is a typed fallback
    manifest["binding"] = {"scenario_id": "s1", "pipeline_mode": "staged"}
    (tmp_path / "artifact_lineage.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    response = _envelope_response(
        manifest,
        graph_unchanged=False,
        change_details={"landed_operation_count": 1},
        gates={"queue_validate_ok": True},
    )
    result = assess_artifact_lineage(tmp_path, response, {"id": "s1"})
    checks = {(issue["check"], issue["severity"]) for issue in result["issues"]}
    assert ("artifact_lineage_fallback_impersonation", "error") in checks
    assert ("artifact_lineage", "error") in checks


def test_structural_manifest_corruption_is_never_demoted(tmp_path: Path) -> None:
    """Only the exact digest-recomputation failure demotes; a dropped row
    (coverage mismatch) and every other invalid-manifest shape stays an error."""
    manifest = _manifest()
    manifest["rows"] = manifest["rows"][:-1]
    manifest["binding"] = {"scenario_id": "s1", "pipeline_mode": "staged"}
    (tmp_path / "artifact_lineage.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    result = assess_artifact_lineage(
        tmp_path, _envelope_response(manifest), {"id": "s1"}
    )
    issues = [
        issue for issue in result["issues"] if issue["check"] == "artifact_lineage"
    ]
    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "demoted to warning" not in issues[0]["detail"]
