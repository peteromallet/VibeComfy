from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.commands.doctor import _cmd_doctor, _video_frame_cap_warnings
from vibecomfy.errors import MissingModelAssetError
from vibecomfy.cli_loader import load_bundle as real_load_bundle
from vibecomfy.security.provenance import Provenance
from vibecomfy.registry import models_loader
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


MODEL_ENTRY = {
    "name": "missing.safetensors",
    "url": "https://example.test/models/missing.safetensors",
    "subdir": "checkpoints",
}


@pytest.fixture(autouse=True)
def _explicit_local_doctor_authorization(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "vibecomfy.commands.doctor.load_bundle",
        lambda path: real_load_bundle(path, trust=Provenance.USER_CONFIRMED),
    )
    registry = tmp_path / "models.yaml"
    registry.write_text(
        "models:\n"
        "  - id: missing.safetensors\n"
        "    canonical_name: missing.safetensors\n"
        "    source:\n"
        "      kind: url\n"
        "      url: https://example.test/models/missing.safetensors\n"
        "      filename: missing.safetensors\n"
        "    min_size: 0\n"
        "    targets:\n"
        "      - node_pack: comfy_core\n"
        "        path: checkpoints/missing.safetensors\n"
        "      - node_pack: comfy_core\n"
        "        path: vae/missing.safetensors\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(models_loader, "DEFAULT_REGISTRY_PATH", registry)
    models_loader._clear_cache()


def _write_scratchpad(path: Path) -> Path:
    path.write_text(
        f"""
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

def build():
    workflow = VibeWorkflow(
        id="test/model-missing",
        source=WorkflowSource(id="test/model-missing", path=__file__),
        metadata={{"model_assets": [{MODEL_ENTRY!r}] }},
    )
    workflow.nodes["1"] = VibeNode(
        id="1", class_type="CheckpointLoaderSimple", inputs={{"ckpt_name": "missing.safetensors"}}, uid="model-missing-1"
    )
    return workflow
""",
        encoding="utf-8",
    )
    return path


def _write_raw_json_workflow(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "workflow_id": "test/raw-model",
                "nodes": [
                    {
                        "id": 1,
                        "uid": "test/raw-model:1",
                        "type": "VAELoader",
                        "properties": {
                            "models": [
                                {
                                    "name": MODEL_ENTRY["name"],
                                    "url": MODEL_ENTRY["url"],
                                }
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_canonical_vae_workflow(path: Path) -> Path:
    """Write a retained, named Python workflow; this is an authoring door."""
    path.write_text(
        f"""
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

MODEL_ASSET = {dict(MODEL_ENTRY, subdir="vae")!r}

def build():
    workflow = VibeWorkflow(
        id="test/named-vae",
        source=WorkflowSource(id="test/named-vae", path=__file__),
        metadata={{"model_assets": [MODEL_ASSET]}},
    )
    workflow.nodes["1"] = VibeNode(
        id="1",
        class_type="VAELoader",
        inputs={{"vae_name": MODEL_ASSET["name"]}},
        uid="named-vae-1",
    )
    return workflow
""",
        encoding="utf-8",
    )
    return path


def test_doctor_reports_missing_model_with_url_and_expected_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    scratchpad = _write_scratchpad(tmp_path / "scratch.py")
    models_root = tmp_path / "models"
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(models_root))

    # B5 lockfile drift verification is default-on per Step 16; this test predates B5 and isolates from the seam to keep its existing assertions stable.
    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad))) == 1

    captured = capsys.readouterr()
    expected_path = models_root / MODEL_ENTRY["subdir"] / MODEL_ENTRY["name"]
    assert "Missing models:" in captured.out
    assert f"missing model {MODEL_ENTRY['name']}" in captured.out
    assert str(expected_path) in captured.out
    assert MODEL_ENTRY["url"] in captured.out


def test_doctor_rejects_raw_json_before_canonical_conversion(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    workflow = _write_raw_json_workflow(tmp_path / "workflow.json")
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path / "models"))
    monkeypatch.setattr("vibecomfy.commands.doctor.get_schema_provider", lambda _mode: None)
    monkeypatch.setattr("vibecomfy.commands.doctor._read_doctor_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(workflow))) == 1
    output = capsys.readouterr().out.lower()
    assert "workflow diagnosis requires canonical python" in output
    assert "port check" in output

    assert _cmd_doctor(
        argparse.Namespace(path=str(workflow), json=True)
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert payload["layer"] == "Python scratchpad import/build"
    assert "requires canonical Python workflow authority" in payload["errors"][0]
    assert payload["recommended_command"].endswith(" --json")


def test_doctor_reports_missing_model_from_canonical_named_workflow(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workflow = _write_canonical_vae_workflow(tmp_path / "workflow.py")
    models_root = tmp_path / "models"
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(models_root))
    monkeypatch.setattr("vibecomfy.commands.doctor.get_schema_provider", lambda _mode: None)
    monkeypatch.setattr("vibecomfy.commands.doctor._read_doctor_lockfile", lambda: [])

    assert _cmd_doctor(argparse.Namespace(path=str(workflow))) == 1

    captured = capsys.readouterr()
    expected_path = models_root / "vae" / MODEL_ENTRY["name"]
    assert "Missing models:" in captured.out
    assert f"missing model {MODEL_ENTRY['name']}" in captured.out
    assert str(expected_path) in captured.out
    assert MODEL_ENTRY["url"] in captured.out


def test_doctor_passes_when_model_exists(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    scratchpad = _write_scratchpad(tmp_path / "scratch.py")
    models_root = tmp_path / "models"
    model_path = models_root / MODEL_ENTRY["subdir"] / MODEL_ENTRY["name"]
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"model")
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(models_root))

    # B5 lockfile drift verification is default-on per Step 16; this test predates B5 and isolates from the seam to keep its existing assertions stable.
    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad))) == 0

    captured = capsys.readouterr()
    assert "Missing models:" not in captured.out
    assert "missing model" not in captured.out


def test_doctor_models_flag_reports_unset_models_root(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    scratchpad = _write_scratchpad(tmp_path / "scratch.py")
    monkeypatch.delenv("VIBECOMFY_MODELS_ROOT", raising=False)
    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])

    code = _cmd_doctor(
        argparse.Namespace(
            path=str(scratchpad),
            models=True,
            json=False,
            allow_drift=False,
            lint=False,
        )
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "VIBECOMFY_MODELS_ROOT not set; cannot check model presence" in captured.out

    code = _cmd_doctor(
        argparse.Namespace(
            path=str(scratchpad),
            models=True,
            json=True,
            allow_drift=False,
            lint=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["status"] == "error"
    assert payload["layer"] == "model asset diagnostics"
    assert "VIBECOMFY_MODELS_ROOT not set; cannot check model presence" in payload["errors"][0]


def test_doctor_models_next_action_uses_registered_flag() -> None:
    action = MissingModelAssetError.default_next_action
    parts = shlex.split(action)
    workflow_arg = parts.index("<workflow>")
    parts[workflow_arg] = "image/z_image"

    args = build_parser().parse_args(parts[1:])

    assert parts[:2] == ["vibecomfy", "doctor"]
    assert args.cmd == "doctor"
    assert args.path == "image/z_image"
    assert args.models is True


def test_doctor_warns_when_bounded_video_generation_has_uncapped_loadvideo() -> None:
    workflow = VibeWorkflow(
        "video/bounded",
        WorkflowSource(id="video/bounded"),
        metadata={"unbound_inputs": {"num_frames": "10.length"}},
    )
    workflow.nodes["1"] = VibeNode(id="1", class_type="LoadVideo", inputs={"file": "source.mp4"}, uid="video/bounded:1")

    warnings = _video_frame_cap_warnings(workflow)

    assert warnings == [
        "LoadVideo node 1 has no frame-load cap, but the workflow exposes a generated frame-count binding; "
        "the caller must cap or normalize source video before runtime if preprocessing should only consume generated frames."
    ]
