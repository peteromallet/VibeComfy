"""Batch E e2e: fixture manifest missing→ensure→preflight green using only on_demand captures.

Evidence matrix (one row, fixture pack):

| command                                   | source_kind            | commit (clone HEAD) | rung (ast/import) | preflight verdict | strict verdict | stub verdict |
|-------------------------------------------|------------------------|---------------------|-------------------|-------------------|----------------|--------------|
| vibecomfy schemas ensure --manifest <m>  | on_demand_static or on_demand_import | <sha7 of fixture clone> | ast or import (real extract on fixture pack) | missing→fail (names ensure command) then green after ensure | runtime_only=1 → fail (on-demand rejected) | @stub.json never passes |

Deterministic, no GPU, network gated (registry mocked; real extract on fixture pack).
Host-only optional: if api.comfy.org unreachable, skip (do not fake schemas).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.live_agentic_harness import scenario_obligations as so

_FIXTURE_SLUG = "fixture-pack"
_FIXTURE_URL = f"https://example.com/{_FIXTURE_SLUG}.git"
_FIXTURE_VERSION = "1.0.0"
_FIXTURE_PACK_SOURCE = '''\
from nodes import NODE_CLASS_MAPPINGS as _ORIG
class FixtureNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"value": ("INT", {"default": 1})}}
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "pack"
    def run(self, value):
        return (None,)
NODE_CLASS_MAPPINGS = {"FixtureNode": FixtureNode}
NODE_DISPLAY_NAME_MAPPINGS = {"FixtureNode": "FixtureNode"}
'''

_SYNTH_SID = "audio-tts-narration-using-indextts-2"


def _make_fixture_clone(base: Path) -> Path:
    clone = base / _FIXTURE_SLUG
    clone.mkdir(parents=True, exist_ok=True)
    (clone / "__init__.py").write_text("")
    pkg = clone / "custom_nodes" / _FIXTURE_SLUG
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "nodes.py").write_text(_FIXTURE_PACK_SOURCE)
    (pkg / "__init__.py").write_text("from .nodes import NODE_CLASS_MAPPINGS\n")
    subprocess.run(["git", "init", "-q"], cwd=clone, check=True)
    subprocess.run(["git", "config", "user.email", "e2e@test"], cwd=clone, check=True)
    subprocess.run(["git", "config", "user.name", "e2e"], cwd=clone, check=True)
    subprocess.run(["git", "add", "."], cwd=clone, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=clone, check=True)
    subprocess.run(["git", "remote", "add", "origin", _FIXTURE_URL], cwd=clone, check=True)
    return clone


def _patch_registry(monkeypatch, *, fail: bool = False) -> None:
    from types import SimpleNamespace
    from vibecomfy.registry import pack_resolver

    if fail:
        def _boom(*a, **kw):
            raise RuntimeError("registry unreachable")
        monkeypatch.setattr(pack_resolver, "resolve_missing_nodes", _boom)
        monkeypatch.setattr(pack_resolver, "resolve_pack", _boom)
        return
    ref = pack_resolver.PackRef(
        slug=_FIXTURE_SLUG,
        source="registry",
        version=_FIXTURE_VERSION,
        url=_FIXTURE_URL,
    )
    monkeypatch.setattr(
        pack_resolver,
        "resolve_missing_nodes",
        lambda *a, **kw: SimpleNamespace(candidates=[SimpleNamespace(ref=ref)]),
    )


def _sandbox_provider(sandbox_root: Path):
    from vibecomfy.schema.on_demand import OnDemandInstallSchemaProvider
    return OnDemandInstallSchemaProvider(sandbox_root=sandbox_root)


def _synthetic_obligation():
    return so.ScenarioObligation(
        scenario_id=_SYNTH_SID,
        purpose="e2e fixture",
        expected_change="edit",
        invariants=(),
        research_requirements=(),
        custom_node_classes=("FixtureNode",),
        schema_evidence_requirements=(
            {
                "class_type": "FixtureNode",
                "pack": _FIXTURE_SLUG,
                "source": "on_demand_static",
            },
        ),
        prompt_tool_contract={},
        requires_edit=True,
    )


def test_e2e_fixture_missing_ensure_preflight_green(tmp_path, monkeypatch, capsys):
    """E2E: empty cache -> preflight fails with ensure command -> ensure -> preflight green.

    Uses only on_demand captures (honest tier: on_demand_static or on_demand_import).
    Real extract on a local fixture pack (not hand-authored @stub.json).
    """
    from vibecomfy.commands import schemas as schemas_command
    from vibecomfy.porting.object_info import consume as consume_module
    from vibecomfy.schema.ensure_capture import format_schema_gap

    cache_root = tmp_path / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
    clone = _make_fixture_clone(sandbox)
    head = subprocess.run(
        ["git", "-C", str(clone), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    sha7 = head[:7]

    monkeypatch.setattr(consume_module, "CACHE_DIR", cache_root)
    monkeypatch.setattr(consume_module, "INDEX_PATH", cache_root / "index.json")
    consume_module.reset_cache()
    monkeypatch.setattr(so, "_authoritative_cache_roots", lambda: [cache_root])
    monkeypatch.setattr(so, "load_scenario_obligation", lambda sid: _synthetic_obligation() if sid == _SYNTH_SID else None)
    monkeypatch.setitem(so.SCHEMA_EVIDENCE_REQUIREMENTS, _SYNTH_SID, (
        {"class_type": "FixtureNode", "pack": _FIXTURE_SLUG, "source": "on_demand_static"},
    ))

    manifest = tmp_path / "comparison.json"
    manifest.write_text(json.dumps({"entries": [{"id": _SYNTH_SID}]}))

    with pytest.raises(so.ScenarioObligationError) as excinfo:
        so.preflight_scenario_obligations(manifest)
    msg = str(excinfo.value)
    assert f"vibecomfy schemas ensure --manifest {manifest}" in msg
    assert format_schema_gap(manifest) in msg or f"vibecomfy schemas ensure --manifest {manifest}" in msg

    code = schemas_command._cmd_schemas_validate_coverage(
        argparse.Namespace(template=None, manifest=str(manifest), json=True)
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert "FixtureNode" in payload["missing_classes"]
    assert payload["ensure_command"].endswith(f"vibecomfy schemas ensure --manifest {manifest}")
    assert payload["ensure_command"] == format_schema_gap(manifest, ["FixtureNode"])

    _patch_registry(monkeypatch)
    monkeypatch.setattr(schemas_command, "_on_demand_provider", lambda: _sandbox_provider(sandbox))
    monkeypatch.setattr(schemas_command, "_manifest_gated_classes", lambda p: (["FixtureNode"], []))

    code = schemas_command._cmd_schemas_ensure(
        argparse.Namespace(template=None, manifest=str(manifest), json=True, comfy_version=None, no_embedded=False)
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0, payload
    assert payload["action"] == "extracted"

    matches = list(cache_root.glob(f"{_FIXTURE_SLUG}@on_demand_*-{sha7}.json"))
    assert len(matches) == 1, list(cache_root.iterdir())
    pack_data = json.loads(matches[0].read_text())
    assert set(pack_data) == {"FixtureNode"}
    entry = pack_data["FixtureNode"]
    assert entry["source_kind"] in ("on_demand_static", "on_demand_import")
    source_kind = entry["source_kind"]
    rung = "ast" if source_kind == "on_demand_static" else "import"

    provenance = json.loads((cache_root / "provenance.json").read_text())
    row = provenance["packs"][matches[0].name]
    assert row["repo"] == _FIXTURE_URL
    assert row["locked_commit"] == head
    assert row["source_kind"] == source_kind
    assert row["extraction_rung"] == rung
    assert row["registry_pack_version"] == _FIXTURE_VERSION

    result = so.preflight_scenario_obligations(manifest)
    assert result["ok"] is True
    tier = result["resolution_tiers"][_SYNTH_SID]["FixtureNode"]
    assert tier["source_kind"] == source_kind
    assert tier["extraction_rung"] == rung
    assert tier["locked_commit"] == head

    with pytest.raises(so.ScenarioObligationError) as excinfo2:
        so.preflight_scenario_obligations(manifest, runtime_only=True)
    assert "VIBECOMFY_OBLIGATION_RUNTIME_ONLY" in str(excinfo2.value) or "runtime_only" in str(excinfo2.value).lower()

    monkeypatch.setenv("VIBECOMFY_OBLIGATION_RUNTIME_ONLY", "1")
    with pytest.raises(so.ScenarioObligationError):
        so.preflight_scenario_obligations(manifest)
    monkeypatch.delenv("VIBECOMFY_OBLIGATION_RUNTIME_ONLY", raising=False)

    stub_file = cache_root / "SomePack@stub.json"
    stub_file.write_text(json.dumps({"Stubbed": {"inputs": {}, "outputs": []}}))
    index = json.loads((cache_root / "index.json").read_text())
    index["Stubbed"] = stub_file.name
    (cache_root / "index.json").write_text(json.dumps(index))
    from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider
    provider = ObjectInfoIndexSchemaProvider(str(cache_root))
    assert provider.get_schema("Stubbed") is None


def test_host_optional_real_registry_skip_if_unreachable(monkeypatch):
    """Optional host-only: try real registry for one UNPROVEN class; skip if unreachable."""
    import socket
    try:
        socket.create_connection(("api.comfy.org", 443), timeout=2).close()
    except OSError:
        pytest.skip("api.comfy.org unreachable — host-only stop condition, do not fake schemas")
    from vibecomfy.registry import pack_resolver
    try:
        ref = pack_resolver.resolve_pack("IndexTTSEngineNode")
        assert ref is not None
    except Exception:
        pytest.skip("registry miss — blocked, do not fake schemas")


def test_doctor_prints_ensure_command(tmp_path, monkeypatch, capsys):
    """Doctor on unknown_class_type prints the shared ensure command (no clone/extract)."""
    from vibecomfy.commands.doctor import _cmd_doctor

    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    scratchpad = tmp_path / "doctor_gap.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
def build():
    wf = VibeWorkflow(id="gap", source=WorkflowSource(id="gap"))
    wf.nodes["1"] = VibeNode(id="1", class_type="FixtureNode", inputs={})
    wf.finalize_metadata()
    return wf
"""
    )
    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])
    code = _cmd_doctor(argparse.Namespace(path=str(scratchpad), json=False, lint=False, allow_drift=False))
    assert code == 1
    out = capsys.readouterr().out
    assert f"vibecomfy schemas ensure {scratchpad}" in out
    assert "vibecomfy schemas ensure --manifest" in out


def test_validate_coverage_manifest_gap_helper(tmp_path, monkeypatch, capsys):
    """validate-coverage --manifest reuses missing_live_captures and helper, exits 1 with ensure_command."""
    from vibecomfy.commands import schemas as schemas_command
    from vibecomfy.porting.object_info import consume as consume_module
    from vibecomfy.schema.ensure_capture import format_schema_gap

    cache_root = tmp_path / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(consume_module, "CACHE_DIR", cache_root)
    monkeypatch.setattr(consume_module, "INDEX_PATH", cache_root / "index.json")
    consume_module.reset_cache()
    monkeypatch.setattr(schemas_command, "_manifest_gated_classes", lambda p: (["MissingNode"], []))
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"entries": [{"id": "x"}]}))

    code = schemas_command._cmd_schemas_validate_coverage(
        argparse.Namespace(template=None, manifest=str(manifest), json=False)
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "Missing:" in out
    assert f"vibecomfy schemas ensure --manifest {manifest}" in out
    assert format_schema_gap(manifest, ["MissingNode"]) in out

    code_json = schemas_command._cmd_schemas_validate_coverage(
        argparse.Namespace(template=None, manifest=str(manifest), json=True)
    )
    payload = json.loads(capsys.readouterr().out)
    assert code_json == 1
    assert payload["missing_classes"] == ["MissingNode"]
    assert payload["ensure_command"].endswith(f"vibecomfy schemas ensure --manifest {manifest}")
    assert payload["ensure_command"] == format_schema_gap(manifest, ["MissingNode"])
