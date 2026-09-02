from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools import validate_template_traceability as traceability
from vibecomfy.node_packs import LockEntry, write_lockfile


def _write_template(root: Path, *, source_sha: str | None, commit: str = "abc") -> Path:
    template = root / "ready_templates" / "image" / "example.py"
    template.parent.mkdir(parents=True)
    sha_line = f"# ported from ready_templates/sources/official/image/example.json (sha256: {source_sha})\n" if source_sha else ""
    template.write_text(
        sha_line
        + f"""
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

MODELS = {{
    "main": ModelAsset(
        filename="model.safetensors",
        url="https://huggingface.co/acme/example/resolve/rev1/model.safetensors",
        subdir="checkpoints",
        sha256="{"0" * 64}",
        hf_revision="rev1",
        size_bytes=123,
    ),
}}
PUBLIC_INPUTS = {{}}
READY_METADATA = ReadyMetadata.build(
    template_id="image/example",
    capability="text_to_image",
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix="image/example",
    requirements={{"custom_nodes": ["ExamplePack"], "custom_node_refs": [{{"slug": "ExamplePack", "source": "git", "commit": "{commit}"}}]}},
    provenance={{"source_workflow": "ready_templates/sources/official/image/example.json"}},
    vibecomfy_version="0.1.0",
    comfy_core={{"status": "discovered", "version": "unknown", "commit": "unknown", "min_version": "unknown", "tested_at": "2026-05-20T00:00:00+00:00"}},
)
def build():
    wf = new_workflow(READY_METADATA, source_path=__file__)
    node(wf, "ExampleNode", "1")
    return finalize(wf, PUBLIC_INPUTS, READY_METADATA, output_node="1")
""",
        encoding="utf-8",
    )
    return template


def _write_project_files(tmp_path: Path, *, source_body: bytes = b"{}", template_commit: str = "abc") -> tuple[Path, Path, Path]:
    (tmp_path / "pyproject.toml").write_text("[project]\nversion = \"0.1.0\"\n", encoding="utf-8")
    source = tmp_path / "ready_templates/sources" / "official" / "image" / "example.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(source_body)
    template = _write_template(tmp_path, source_sha=hashlib.sha256(source_body).hexdigest(), commit=template_commit)
    index = tmp_path / "template_index.json"
    index.write_text(
        json.dumps(
            {
                "templates": [
                    {
                        "id": "image/example",
                        "path": "ready_templates/image/example.py",
                        "source_workflow": "ready_templates/sources/official/image/example.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    lockfile = tmp_path / "custom_nodes.lock"
    write_lockfile(
        [
            LockEntry(
                "ExamplePack",
                source="git",
                slug="ExamplePack",
                commit="abc",
                url="https://github.com/acme/ExamplePack.git",
                class_set=("ExampleNode",),
            )
        ],
        lockfile,
    )
    return template, index, lockfile


def test_clean_traceability_fixture_passes(monkeypatch, tmp_path: Path) -> None:
    _template, index, lockfile = _write_project_files(tmp_path)
    registry = tmp_path / "models.yaml"
    registry.write_text(
        """
models:
  - id: example
    source:
      kind: huggingface
      repo: acme/example
      filename: model.safetensors
      revision: rev1
    min_size: 1
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"
    size_bytes: 123
    targets:
      - node_pack: comfy_core
        path: checkpoints/model.safetensors
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(traceability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(traceability, "build_pack_provenance_report", lambda: {"diagnostics": []})

    report = traceability.build_traceability_report(template_index=index, model_registry=registry, lockfile=lockfile, allowlist=())

    assert report["ok"] is True
    assert report["summary"]["diagnostics"] == 0


def test_default_migration_allowlist_has_one_active_auditable_deadline() -> None:
    assert traceability.DEFAULT_MIGRATION_ALLOWLIST
    assert {
        entry.expires for entry in traceability.DEFAULT_MIGRATION_ALLOWLIST
    } == {traceability.MIGRATION_ALLOWLIST_EXPIRES}
    assert traceability.MIGRATION_ALLOWLIST_EXPIRES == "2027-03-01"


def test_expired_allowlist_entry_does_not_suppress_matching_diagnostic() -> None:
    entry = traceability.AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_source_sha_missing",
        owner="test",
        reason="test",
        expires="2000-01-01",
        removal_condition="test",
    )

    result = traceability._apply_allowlist(
        {
            "code": "template_source_sha_missing",
            "target": "ready_templates/image/example.py",
        },
        (entry,),
    )

    assert result["allowlisted"] is False


def test_diagnostic_code_not_in_allowlist_remains_unsuppressed() -> None:
    result = traceability._apply_allowlist(
        {
            "code": "new_traceability_diagnostic",
            "target": "ready_templates/image/example.py",
        },
        traceability.DEFAULT_MIGRATION_ALLOWLIST,
    )

    assert result["allowlisted"] is False


def test_source_sha_mismatch_is_unallowlisted(monkeypatch, tmp_path: Path) -> None:
    _template, index, lockfile = _write_project_files(tmp_path, source_body=b"old")
    (tmp_path / "ready_templates/sources" / "official" / "image" / "example.json").write_bytes(b"new")
    registry = tmp_path / "models.yaml"
    registry.write_text("models: []\n", encoding="utf-8")
    monkeypatch.setattr(traceability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(traceability, "build_pack_provenance_report", lambda: {"diagnostics": []})

    report = traceability.build_traceability_report(template_index=index, model_registry=registry, lockfile=lockfile, allowlist=())

    assert report["ok"] is False
    assert "template_source_sha_mismatch" in report["summary"]["by_code_unallowlisted"]


def test_custom_node_pin_conflict_is_reported(monkeypatch, tmp_path: Path) -> None:
    _template, index, lockfile = _write_project_files(tmp_path, template_commit="different")
    registry = tmp_path / "models.yaml"
    registry.write_text("models: []\n", encoding="utf-8")
    monkeypatch.setattr(traceability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(traceability, "build_pack_provenance_report", lambda: {"diagnostics": []})

    report = traceability.build_traceability_report(template_index=index, model_registry=registry, lockfile=lockfile, allowlist=())

    assert report["ok"] is False
    assert "template_custom_node_ref_pin_conflict" in report["summary"]["by_code_unallowlisted"]


def test_template_model_asset_missing_pins_can_be_allowlisted(monkeypatch, tmp_path: Path) -> None:
    template, index, lockfile = _write_project_files(tmp_path)
    text = template.read_text(encoding="utf-8")
    text = text.replace('        sha256="' + "0" * 64 + '",\n        hf_revision="rev1",\n        size_bytes=123,\n', "")
    template.write_text(text, encoding="utf-8")
    registry = tmp_path / "models.yaml"
    registry.write_text("models: []\n", encoding="utf-8")
    monkeypatch.setattr(traceability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(traceability, "build_pack_provenance_report", lambda: {"diagnostics": []})

    report = traceability.build_traceability_report(template_index=index, model_registry=registry, lockfile=lockfile)

    assert report["ok"] is True
    assert report["summary"]["allowlisted"] == 3
    allowlist = report["diagnostics"][0]["allowlist"]
    assert {"owner", "reason", "expires", "removal_condition"}.issubset(allowlist)


def test_model_registry_missing_pins_can_be_allowlisted(monkeypatch, tmp_path: Path) -> None:
    _template, index, lockfile = _write_project_files(tmp_path)
    registry = tmp_path / "models.yaml"
    registry.write_text(
        """
models:
  - id: example
    source:
      kind: huggingface
      repo: acme/example
      filename: model.safetensors
    min_size: 1
    targets:
      - node_pack: comfy_core
        path: checkpoints/model.safetensors
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(traceability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(traceability, "build_pack_provenance_report", lambda: {"diagnostics": []})

    report = traceability.build_traceability_report(template_index=index, model_registry=registry, lockfile=lockfile)

    assert report["ok"] is True
    assert {
        "model_registry_missing_revision",
        "model_registry_missing_sha256",
        "model_registry_missing_size_bytes",
    }.issubset(report["summary"]["by_code"])


def test_cli_strict_exits_nonzero_for_unallowlisted_errors(monkeypatch, tmp_path: Path, capsys) -> None:
    _template, index, lockfile = _write_project_files(tmp_path, source_body=b"old")
    (tmp_path / "ready_templates/sources" / "official" / "image" / "example.json").write_bytes(b"new")
    registry = tmp_path / "models.yaml"
    registry.write_text("models: []\n", encoding="utf-8")
    monkeypatch.setattr(traceability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(traceability, "build_pack_provenance_report", lambda: {"diagnostics": []})

    exit_code = traceability.main([
        "--strict",
        "--json",
        "--template-index",
        str(index),
        "--model-registry",
        str(registry),
        "--lockfile",
        str(lockfile),
    ])

    assert exit_code == 1
    assert "template_source_sha_mismatch" in capsys.readouterr().out
