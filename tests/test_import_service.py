from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from vibecomfy.porting.import_service import import_workflow_bytes
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow_bundle import emit_bundle, load_bundle


def test_import_persists_mixed_source_pins_without_cwd_lockfile(tmp_path: Path, monkeypatch) -> None:
    source = {
        "workflow_id": "provenance-import",
        "nodes": [
            {"id": 1, "type": "KSampler", "inputs": [], "widgets_values": [],
             "properties": {"cnr_id": "comfy-core", "ver": "0.24.0"}},
            {"id": 2, "type": "KSampler", "inputs": [], "widgets_values": [],
             "properties": {"cnr_id": "comfy-core", "ver": "0.25.0"}},
            {"id": 3, "type": "KSampler", "inputs": [], "widgets_values": [],
             "properties": {"aux_id": "owner/repo", "ver": "deadbeef"}},
        ],
    }
    monkeypatch.chdir(tmp_path)
    artifacts = import_workflow_bytes(
        json.dumps(source, separators=(",", ":")).encode(),
        workflow_id="provenance-import",
    )
    report = artifacts.report["provenance"]["source_provenance"]
    assert {pin["version"] for pin in report["version_pins"]} >= {"0.24.0", "0.25.0", "deadbeef"}
    assert any(conflict["code"] == "conflicting_authored_versions" for conflict in report["conflicts"])
    assert "source_provenance" in artifacts.python_bytes.decode()

    first = tmp_path / "first"
    first.mkdir()
    (first / "workflow.py").write_bytes(artifacts.python_bytes)
    (first / "workflow.vibe.json").write_bytes(artifacts.companion_bytes)
    loaded = load_bundle(first / "workflow.py", trust=Provenance.USER_CONFIRMED)
    assert loaded.provenance["source_provenance"] == report

    second = tmp_path / "second"
    emit_bundle(loaded.workflow, second / "workflow.py", loaded.provenance)
    reloaded = load_bundle(second / "workflow.py", trust=Provenance.USER_CONFIRMED)
    assert reloaded.provenance["source_provenance"] == report


def test_import_cli_preserves_source_pin_receipt(tmp_path: Path, monkeypatch, capsys) -> None:
    from vibecomfy.cli import build_parser
    from vibecomfy.porting.provenance import extract_provenance

    source = {
        "nodes": [
            {"id": 1, "type": "KSampler", "inputs": [], "widgets_values": [],
             "properties": {"cnr_id": "comfy-core", "ver": "0.24.0"}},
            {"id": 2, "type": "KSampler", "inputs": [], "widgets_values": [],
             "properties": {"aux_id": "owner/repo", "ver": "deadbeef"}},
        ],
    }
    monkeypatch.chdir(tmp_path)
    source_path = tmp_path / "input.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    output_path = tmp_path / "converted"
    args = build_parser().parse_args([
        "import", str(source_path), "--out", str(output_path), "--json",
    ])
    assert args.func(args) == 0, capsys.readouterr().out
    loaded = load_bundle(output_path, trust=Provenance.USER_CONFIRMED)
    expected = json.loads(json.dumps(extract_provenance(source).to_json()))
    assert json.loads(json.dumps(loaded.provenance["source_provenance"])) == expected
    assert json.loads(json.dumps(loaded.workflow.metadata["source_provenance"])) == expected


def test_import_service_carries_external_origin_into_bundle_provenance(tmp_path: Path, monkeypatch) -> None:
    source = {"nodes": [{"id": 1, "type": "KSampler", "inputs": [], "widgets_values": []}]}
    monkeypatch.chdir(tmp_path)
    source_bytes = json.dumps(source, separators=(",", ":")).encode()
    artifacts = import_workflow_bytes(
        source_bytes,
        workflow_id="hivemind-4018",
        source_provenance={
            "origin_kind": "hivemind",
            "origin_uri": "hivemind:external_resources:4018",
            "origin_pin": "4006",
            "source_digest": "sha256:" + hashlib.sha256(source_bytes).hexdigest(),
        },
    )
    assert artifacts.report["provenance"]["origin_kind"] == "hivemind"
    assert artifacts.report["provenance"]["origin_uri"] == "hivemind:external_resources:4018"
    assert artifacts.report["provenance"]["origin_pin"] == "4006"


def test_import_rejects_external_digest_that_does_not_match_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="digest does not match"):
        import_workflow_bytes(
            b'{"nodes": []}',
            workflow_id="digest-mismatch",
            source_provenance={"source_digest": "sha256:" + "0" * 64},
        )
