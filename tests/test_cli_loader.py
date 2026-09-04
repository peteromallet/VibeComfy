from __future__ import annotations

import json
from pathlib import Path

import pytest

import vibecomfy.cli_loader as cli_loader
from vibecomfy.cli_loader import load_bundle, load_workflow_any
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow_bundle import WorkflowBundleError


def test_load_workflow_any_accepts_basename_ready_id() -> None:
    workflow = load_workflow_any("z_image")

    assert workflow.metadata["ready_template"] == "image/z_image"


def test_load_workflow_any_accepts_slash_ready_id() -> None:
    workflow = load_workflow_any("video/wan_t2v")

    assert workflow.metadata["ready_template"] == "video/wan_t2v"


def test_load_workflow_any_accepts_scratchpad_path(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    wf = VibeWorkflow('scratch', WorkflowSource('scratch'))\n"
        "    wf.add_node('SaveImage', images='placeholder')\n"
        "    return wf.finalize_metadata()\n",
        encoding="utf-8",
    )

    workflow = load_workflow_any(str(scratchpad))

    assert workflow.id == "scratch"
    assert workflow.outputs[0].output_type == "SaveImage"


def test_load_workflow_any_accepts_json_path(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps({"1": {"class_type": "Integer", "inputs": {"value": 7}}}),
        encoding="utf-8",
    )

    workflow = load_workflow_any(str(workflow_path))

    assert workflow.id == "workflow"
    assert workflow.nodes["1"].class_type == "Integer"


@pytest.mark.parametrize("suffix", [".py", ".json"])
def test_direct_file_loading_does_not_require_ready_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    path = tmp_path / f"workflow{suffix}"
    if suffix == ".py":
        path.write_text(
            "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
            "def build():\n"
            "    return VibeWorkflow('direct', WorkflowSource('direct'))\n",
            encoding="utf-8",
        )
    else:
        path.write_text(
            json.dumps({"1": {"class_type": "Integer", "inputs": {"value": 7}}}),
            encoding="utf-8",
        )

    def unavailable() -> None:
        raise RuntimeError("ready discovery unavailable")

    monkeypatch.setattr(cli_loader, "ready_template_discovery", unavailable)

    workflow = load_workflow_any(str(path))

    assert workflow.id == ("direct" if suffix == ".py" else "workflow")


def test_load_workflow_any_missing_id_raises_key_error() -> None:
    with pytest.raises(KeyError):
        load_workflow_any("not_a_real_workflow_id")


def test_load_workflow_any_missing_path_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_workflow_any(str(tmp_path / "missing.json"))


def test_load_bundle_is_distinct_from_bare_compatibility_loader(tmp_path: Path) -> None:
    source = tmp_path / "bundle.py"
    source.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    return VibeWorkflow('bundle', WorkflowSource('bundle'))\n",
        encoding="utf-8",
    )

    bundle = load_bundle(source, trust=Provenance.USER_CONFIRMED)

    assert bundle.workflow.id == "bundle"
    assert bundle.workflow_identity == "bundle"
    assert bundle.ui_digest == ""


def test_load_bundle_imported_json_uses_offline_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vibecomfy.schema as schema

    source = tmp_path / "imported.json"
    source.write_text(
        json.dumps(
            {
                "workflow_id": "imported",
                "prompt": {"1": {"class_type": "Integer", "inputs": {"value": 7}}},
            }
        ),
        encoding="utf-8",
    )

    def fail_auto(*args, **kwargs):
        raise AssertionError("auto schema provider must not be used by load_bundle")

    monkeypatch.setattr(schema, "get_schema_provider", fail_auto)
    bundle = load_bundle(source)

    assert bundle.workflow_identity == "imported"


def test_load_bundle_imported_api_preserves_reserved_node_ids(tmp_path: Path) -> None:
    source = tmp_path / "reserved.json"
    source.write_text(
        json.dumps(
            {
                "workflow_id": "reserved",
                "source": {"class_type": "Integer", "inputs": {"value": 7}},
            }
        ),
        encoding="utf-8",
    )

    bundle = load_bundle(source)

    assert "source" in bundle.workflow.nodes


def test_load_bundle_prompt_identity_does_not_strip_inner_reserved_node(tmp_path: Path) -> None:
    source = tmp_path / "prompt.json"
    source.write_text(
        json.dumps(
            {
                "workflow_id": "prompted",
                "prompt": {
                    "source": {"class_type": "Integer", "inputs": {"value": 7}},
                },
            }
        ),
        encoding="utf-8",
    )

    bundle = load_bundle(source)

    assert bundle.workflow_identity == "prompted"
    assert "source" in bundle.workflow.nodes


def test_load_bundle_rejects_ambiguous_reserved_api_mapping(tmp_path: Path) -> None:
    source = tmp_path / "ambiguous.json"
    source.write_text(
        json.dumps({"workflow_id": "ambiguous", "source": {"not": "an identity"}}),
        encoding="utf-8",
    )

    with pytest.raises(WorkflowBundleError, match="ambiguous API envelope"):
        load_bundle(source)


def test_load_bundle_accepts_only_explicit_ephemeral_workflow() -> None:
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    workflow = VibeWorkflow("ephemeral", WorkflowSource("ephemeral"))
    bundle = load_bundle(workflow)

    assert bundle.python_path is None
    assert bundle.provenance == {"operation": "ephemeral"}
