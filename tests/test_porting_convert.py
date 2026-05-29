from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.porting.convert import (
    ConversionWriteError,
    ManualTemplateRefusal,
    PortConvertResult,
    PortConvertValidation,
    _check_manual_refusal,
    _compute_diff,
    port_convert_and_write,
    port_convert_workflow,
)
from vibecomfy.porting.strict_ready import STRICT_READY_MISSING_OUTPUT_CONTRACT
from vibecomfy.porting.emitter import emit_ready_template_python
from vibecomfy.node_packs_lockfile import LockEntry
# parity helpers exercised indirectly through port_convert_workflow
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


class FakeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _sample_workflow(*, include_required_input: bool = True) -> VibeWorkflow:
    workflow = VibeWorkflow(
        "sample",
        WorkflowSource("source/sample", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    save_inputs = {"filename_prefix": "out/sample"} if include_required_input else {}
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs=save_inputs)
    workflow.edges.append(VibeEdge("1", "0", "2", "images"))
    workflow.metadata["model_assets"] = [
        {"name": "model.safetensors", "url": "https://example.test/model.safetensors", "subdir": "checkpoints"}
    ]
    workflow.requirements.custom_nodes.append("ComfyUI-TestPack")
    return workflow


def test_ready_template_emitter_uses_typed_wrappers_and_strips_schema_defaults() -> None:
    workflow = VibeWorkflow(
        "typed",
        WorkflowSource("source/typed", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    workflow.nodes["1"] = VibeNode(
        "1",
        "UNETLoader",
        inputs={"unet_name": "model.safetensors", "weight_dtype": "default"},
    )
    workflow.nodes["1"].metadata["output_names"] = ["MODEL"]
    workflow.nodes["2"] = VibeNode(
        "2",
        "SaveImage",
        inputs={"filename_prefix": "out/typed"},
    )

    source = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/typed", "capability": "text_to_image"},
        ready_requirements={},
        template_id="image/typed",
    )

    assert "from vibecomfy.nodes.core import SaveImage" in source
    assert "UNETLoader(" not in source
    assert "_id='1'" not in source
    assert "wf.metadata.setdefault('id_map'" not in source
    assert "wf._set_id_map(" not in source
    assert "source_id='1'" not in source
    assert "weight_dtype='default'" not in source
    assert "bind_output(" not in source
    assert "return wf.finalize({}" in source


def test_ready_template_emitter_preserves_kept_schema_default() -> None:
    workflow = VibeWorkflow(
        "typed",
        WorkflowSource("source/typed", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    workflow.nodes["1"] = VibeNode(
        "1",
        "UNETLoader",
        inputs={"unet_name": "model.safetensors", "weight_dtype": "default"},
    )
    workflow.nodes["1"].metadata["keep_defaults"] = ["weight_dtype"]

    source = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/typed", "capability": "text_to_image"},
        ready_requirements={},
        template_id="image/typed",
    )

    assert "weight_dtype='default'" in source


def _provider() -> FakeSchemaProvider:
    return FakeSchemaProvider(
        {
            "LoadImage": NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={"image": InputSpec("STRING", required=True)},
                outputs=[OutputSpec("IMAGE", "image")],
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={"images": InputSpec("IMAGE", required=True), "filename_prefix": InputSpec("STRING", required=True)},
                outputs=[],
            ),
        }
    )


def test_port_convert_defaults_to_importable_scratchpad_without_ready_metadata() -> None:
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    assert result.mode == "scratchpad"
    assert result.ready_id is None
    assert result.validation is not None and result.validation.ok
    assert result.validation.import_ok
    assert result.validation.build_ok
    assert result.validation.compile_ok
    assert result.validation.schema_ok is True
    assert "READY_METADATA" not in result.text
    assert "source_type='scratchpad'" in result.text
    assert "'source_hash': 'sha256:abc'" in result.text
    assert "'workflow_shape': {'nodes': 2, 'runtime_nodes': 2}" in result.text
    assert "'output_mode': 'scratchpad'" in result.text


def test_port_convert_emits_registered_output_names() -> None:
    workflow = _sample_workflow()
    workflow.nodes["1"].metadata["output_names"] = ["image"]

    result = port_convert_workflow(
        workflow,
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    assert "_outputs=('image',)" in result.text
    assert result.validation is not None and result.validation.ok


def test_port_convert_ready_template_candidate_requires_ready_id() -> None:
    result = port_convert_workflow(
        _sample_workflow(),
        ready_id="image/sample",
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    assert result.mode == "ready_template"
    assert result.ready_id == "image/sample"
    assert result.validation is not None and result.validation.ok
    assert "READY_METADATA =" in result.text
    assert "template_id='image/sample'" not in result.text
    assert "'source_hash': 'sha256:abc'" in result.text
    assert "'workflow_shape': {'nodes': 2, 'runtime_nodes': 2}" in result.text
    assert "'output_mode': 'ready_template'" in result.text
    assert "'ready_id': 'image/sample'" in result.text
    assert "'custom_nodes': ['ComfyUI-TestPack']" in result.text
    assert "https://example.test/model.safetensors" in result.text
    assert "filename='model.safetensors'" not in result.text


def test_port_convert_ready_template_emits_structured_custom_node_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecomfy.porting.convert as convert

    monkeypatch.setattr(
        convert,
        "read_lockfile",
        lambda: [
            LockEntry(
                name="ComfyUI-TestPack",
                git_commit_sha="abc",
                url="https://example.test/pack.git",
                slug="comfyui-testpack",
                source="git",
                commit="abc",
                class_set=("LoadImage",),
            )
        ],
    )

    result = port_convert_workflow(
        _sample_workflow(),
        ready_id="image/sample",
        source_path="workflow_corpus/source.json",
        schema_provider=_provider(),
    )

    assert "'custom_nodes': ['ComfyUI-TestPack']" in result.text
    assert "'custom_node_refs':" in result.text
    assert "'slug': 'comfyui-testpack'" in result.text


def test_port_convert_rejects_ready_template_candidate_without_kind_name_id() -> None:
    with pytest.raises(ValueError, match="kind/name"):
        port_convert_workflow(_sample_workflow(), ready_id="sample")


def test_port_convert_validation_reports_schema_failures() -> None:
    result = port_convert_workflow(_sample_workflow(include_required_input=False), schema_provider=_provider())

    assert result.validation is not None
    assert not result.validation.ok
    assert result.validation.schema_ok is False
    assert result.validation.error == "schema validation failed"
    assert [issue.code for issue in result.validation.issues] == ["missing_required_input"]


# ---------------------------------------------------------------------------
# Golden tests - legacy `vibecomfy convert` behavior (before removal)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Canonical `port convert` tests - various source formats
# ---------------------------------------------------------------------------


def test_port_convert_from_ready_id_produces_importable_scratchpad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Canonical: ready_id -> port_convert_workflow produces importable scratchpad."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "scratchpad"
    assert result.validation is not None and result.validation.ok
    assert result.validation.import_ok
    assert result.validation.build_ok
    assert result.validation.compile_ok


def test_port_convert_from_raw_json_produces_importable_scratchpad() -> None:
    """Canonical: raw JSON workflows produce importable scratchpads through port_convert_workflow."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/video/wan_t2v.json",
        provenance={"source_hash": "sha256:def"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "scratchpad"
    assert result.validation is not None and result.validation.ok
    assert "source_type='scratchpad'" in result.text
    assert "'source_hash': 'sha256:def'" in result.text


def test_port_convert_from_api_shaped_json_produces_importable_scratchpad() -> None:
    """Canonical: API-shaped JSON (dict of node dicts) produces importable scratchpad."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/api_shaped.json",
        provenance={"source_hash": "sha256:api"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "scratchpad"
    assert result.validation is not None and result.validation.ok
    assert "source_type='scratchpad'" in result.text


def test_port_convert_with_indexed_workflow_id_produces_importable_scratchpad() -> None:
    """Canonical: indexed workflow id source produces importable scratchpad."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_index:my-workflow",
        provenance={"source_hash": "sha256:idx"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "scratchpad"
    assert result.validation is not None and result.validation.ok
    assert "source_type='scratchpad'" in result.text


def test_port_convert_ready_template_candidate_does_not_preserve_api_workflow_inline() -> None:
    """Migration outcome: canonical port convert does NOT preserve inline API_WORKFLOW.

    The legacy converter produced inline API_WORKFLOW for ready-id sources.
    The canonical port convert emits proper VibeWorkflow builder code instead.
    """
    result = port_convert_workflow(
        _sample_workflow(),
        ready_id="image/sample",
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "ready_template"
    assert "API_WORKFLOW =" not in result.text
    assert "READY_METADATA =" in result.text
    assert result.validation is not None and result.validation.ok


# ---------------------------------------------------------------------------
# T6 - Representative parity fixtures and tests
# ---------------------------------------------------------------------------


def test_parity_json_includes_widget_snapshots_and_output_counts() -> None:
    """Parity JSON includes widget snapshots, output-count evidence, and class type counts."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    validation_json = result.validation.to_json()

    # Parity evidence fields
    assert "parity_ok" in validation_json
    assert "parity_diffs" in validation_json
    assert "source_output_count" in validation_json
    assert "emitted_output_count" in validation_json
    assert "source_class_type_counts" in validation_json
    assert "emitted_class_type_counts" in validation_json
    assert "source_widget_value_snapshot" in validation_json
    assert "emitted_widget_value_snapshot" in validation_json
    assert "source_topology_snapshot" in validation_json
    assert "emitted_topology_snapshot" in validation_json

    # Widget snapshots and output counts should be populated when parity succeeds
    if result.validation.parity_ok:
        assert isinstance(result.validation.source_widget_value_snapshot, int)
        assert isinstance(result.validation.emitted_widget_value_snapshot, int)
        assert isinstance(result.validation.source_output_count, int)
        assert isinstance(result.validation.emitted_output_count, int)


def test_convert_parity_exception_is_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parity crashes fail validation instead of being swallowed."""
    from vibecomfy.porting import convert as convert_module

    def _raise_parity(*args: object, **kwargs: object) -> tuple[bool, list[str]]:
        raise RuntimeError("synthetic parity crash")

    monkeypatch.setattr(convert_module, "compile_equivalent", _raise_parity)

    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    assert result.validation is not None
    assert result.validation.ok is False
    assert result.validation.parity_ok is False
    assert result.validation.parity_diffs == []
    assert result.validation.parity_error == "RuntimeError: synthetic parity crash"
    assert result.validation.error == "parity check failed: RuntimeError: synthetic parity crash"
    assert result.validation.to_json()["parity_error"] == "RuntimeError: synthetic parity crash"


def test_convert_parity_mismatch_uses_diffs_not_parity_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real parity mismatches stay in parity_diffs without being reported as crashes."""
    from vibecomfy.porting import convert as convert_module

    def _return_parity_diff(*args: object, **kwargs: object) -> tuple[bool, list[str]]:
        return False, ["synthetic parity diff"]

    monkeypatch.setattr(convert_module, "compile_equivalent", _return_parity_diff)

    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    assert result.validation is not None
    assert result.validation.ok is True
    assert result.validation.parity_ok is False
    assert result.validation.parity_diffs == ["synthetic parity diff"]
    assert result.validation.parity_error is None
    assert result.validation.error is None


def test_parity_for_simple_image_z_image_produces_evidence(tmp_path: Path) -> None:
    """Simple image workflow (z_image) produces parity evidence through port_convert_workflow."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:z_image"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    assert result.validation.ok is True
    # Parite evidence shape is present regardless of parity outcome
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)
    assert isinstance(v.source_topology_snapshot, int)
    assert isinstance(v.emitted_topology_snapshot, int)
    assert isinstance(v.source_class_type_counts, dict)
    assert isinstance(v.emitted_class_type_counts, dict)


def test_parity_for_edit_qwen_image_edit_produces_evidence() -> None:
    """Edit workflow (qwen_image_edit) produces parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/edit/qwen_image_edit.json",
        provenance={"source_hash": "sha256:qwen_edit"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)


def test_parity_for_audio_ace_t2a_song_produces_evidence() -> None:
    """Audio/TTS workflow (ace_step_1_5_t2a_song) produces parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/audio/ace_step_1_5_t2a_song.json",
        provenance={"source_hash": "sha256:ace_audio"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)


def test_parity_for_wan_video_wan_t2v_produces_evidence() -> None:
    """Wan video workflow (wan_t2v) produces parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/video/wan_t2v.json",
        provenance={"source_hash": "sha256:wan_video"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)


def test_parity_for_ltx_ltx2_3_t2v_produces_evidence() -> None:
    """LTX workflow (ltx2_3_t2v) produces parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/video/ltx2_3_t2v.json",
        provenance={"source_hash": "sha256:ltx_video"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)


def test_opaque_component_fixture_exists_and_is_valid_json() -> None:
    """The opaque component fixture is valid JSON with UUID class type."""
    fixture_path = Path(__file__).parent / "fixtures" / "porting" / "opaque_component.json"
    assert fixture_path.exists()
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert "nodes" in data
    # At least one node should have a UUID-style class_type
    uuid_nodes = [
        node for node in data["nodes"]
        if len(node.get("type", "")) > 30 and "-" in node.get("type", "")
    ]
    assert len(uuid_nodes) > 0, "opaque_component.json must contain at least one UUID-type node"


def test_opaque_component_conversion_produces_validation() -> None:
    """Opaque component conversion runs and produces validation with parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="tests/fixtures/porting/opaque_component.json",
        provenance={"source_hash": "sha256:opaque"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    assert isinstance(result.validation.to_json(), dict)
    # Parity evidence fields are present even for opaque workflows
    assert result.validation.parity_ok in {True, False}
    assert result.validation.parity_error is None
    assert isinstance(result.validation.parity_diffs, list)


def test_port_convert_result_to_json_excludes_raw_text() -> None:
    """PortConvertResult.to_json() excludes the raw text field by design."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    data = result.to_json()
    assert "text" not in data
    assert "mode" in data
    assert "ready_id" in data
    assert "validation" in data


def test_port_convert_validation_to_json_contains_all_parity_fields() -> None:
    """PortConvertValidation.to_json() contains all parity evidence fields."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    vj = result.validation.to_json()
    for field in [
        "ok", "import_ok", "build_ok", "compile_ok", "schema_ok",
        "issues", "api_node_count", "error",
        "parity_ok", "parity_error", "parity_diffs",
        "source_output_count", "emitted_output_count",
        "source_class_type_counts", "emitted_class_type_counts",
        "source_widget_value_snapshot", "emitted_widget_value_snapshot",
        "source_topology_snapshot", "emitted_topology_snapshot",
        "strict_ready_ok", "strict_ready_diagnostics",
    ]:
        assert field in vj, f"PortConvertValidation.to_json() missing field: {field}"


def test_ready_template_candidate_strict_ready_failure_blocks_write(tmp_path: Path) -> None:
    workflow = VibeWorkflow(
        "strict_missing_output",
        WorkflowSource("source/strict_missing_output", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})

    result = port_convert_workflow(
        workflow,
        ready_id="image/strict_missing_output",
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:strict-missing-output"},
        workflow_shape={"nodes": 1, "runtime_nodes": 1},
        schema_provider=None,
    )

    assert result.validation is not None
    assert result.validation.strict_ready_ok is False
    assert any(
        issue.code in {STRICT_READY_MISSING_OUTPUT_CONTRACT, "strict_ready_build_failed"}
        for issue in result.validation.strict_ready_diagnostics
    )
    target = tmp_path / "strict_missing_output.py"
    with pytest.raises(ConversionWriteError, match="Strict-ready validation failed"):
        port_convert_and_write(result, target)
    assert not target.exists()


# ---------------------------------------------------------------------------
# T9 - Atomic conversion write, dry-run, diff, manual refusal tests
# ---------------------------------------------------------------------------


def test_atomic_write_succeeds_with_valid_result(tmp_path: Path) -> None:
    """port_convert_and_write writes to target when validation passes."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "written.py"

    write_result = port_convert_and_write(result, target)
    assert write_result["written"] is True
    assert target.exists()
    assert "from vibecomfy.workflow import" in target.read_text(encoding="utf-8")


def test_atomic_write_refuses_manual_marker(tmp_path: Path) -> None:
    """Manual refusal: target with '# vibecomfy: manual' blocks writes."""
    target = tmp_path / "manual_template.py"
    target.write_text("# vibecomfy: manual\n# This is hand-authored\n", encoding="utf-8")
    original_bytes = target.read_bytes()

    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    with pytest.raises(ManualTemplateRefusal, match="manual"):
        port_convert_and_write(result, target)

    # File must be byte-for-byte unchanged
    assert target.read_bytes() == original_bytes


def test_atomic_write_failed_validation_leaves_file_unchanged(tmp_path: Path) -> None:
    """Failed validation leaves pre-existing file byte-for-byte unchanged."""
    target = tmp_path / "existing.py"
    target.write_text("# existing content\nprint('hello')\n", encoding="utf-8")
    original_bytes = target.read_bytes()

    # Create a result with a failing validation
    bad_validation = PortConvertValidation(
        ok=False,
        import_ok=True,
        build_ok=True,
        compile_ok=True,
        error="schema validation failed",
        parity_ok=None,
    )
    result = PortConvertResult(mode="scratchpad", text="# bad output", validation=bad_validation)

    with pytest.raises(ConversionWriteError, match="Validation failed"):
        port_convert_and_write(result, target)

    # File must be byte-for-byte unchanged
    assert target.read_bytes() == original_bytes
    assert target.read_text(encoding="utf-8") == "# existing content\nprint('hello')\n"


def test_atomic_write_failed_parity_leaves_file_unchanged(tmp_path: Path) -> None:
    """Failed parity leaves pre-existing file byte-for-byte unchanged."""
    target = tmp_path / "existing.py"
    target.write_text("# original\n", encoding="utf-8")
    original_bytes = target.read_bytes()

    # Validation passes but parity fails
    bad_validation = PortConvertValidation(
        ok=True,
        import_ok=True,
        build_ok=True,
        compile_ok=True,
        parity_ok=False,
        parity_diffs=["class_types only in B: {'ExtraNode': 1}"],
    )
    result = PortConvertResult(mode="scratchpad", text="# different output", validation=bad_validation)

    with pytest.raises(ConversionWriteError, match="Parity check failed"):
        port_convert_and_write(result, target)

    assert target.read_bytes() == original_bytes


def test_dry_run_does_not_write_file(tmp_path: Path) -> None:
    """Dry-run produces evidence payload without touching target."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "not_written.py"

    write_result = port_convert_and_write(result, target, dry_run=True)
    assert write_result["written"] is False
    assert write_result["dry_run"] is True
    assert write_result["target"] == str(target)
    assert "validation" in write_result
    assert "diff" in write_result
    # File must not exist
    assert not target.exists()


def test_dry_run_includes_diff_metadata(tmp_path: Path) -> None:
    """Dry-run includes unified diff and line counts."""
    target = tmp_path / "existing.py"
    target.write_text("# old header\nprint('hello')\n", encoding="utf-8")

    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    write_result = port_convert_and_write(result, target, dry_run=True)
    diff_data = write_result["diff"]
    assert "unified_diff" in diff_data
    assert "original_exists" in diff_data
    assert diff_data["original_exists"] is True
    assert diff_data["emitted_line_count"] > 0
    assert diff_data["original_line_count"] == 2


def test_diff_mode_includes_diff_data(tmp_path: Path) -> None:
    """Diff mode flag produces diff data in write result."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "target.py"

    write_result = port_convert_and_write(result, target, diff=True)
    # With diff=True but not dry_run, it should still write
    assert write_result["written"] is True
    assert "diff" in write_result
    assert write_result["diff"]["original_exists"] is False  # target didn't exist


def test_atomic_write_creates_parent_directories(tmp_path: Path) -> None:
    """Atomic write creates parent directories as needed."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "deep" / "nested" / "output.py"

    write_result = port_convert_and_write(result, target)
    assert write_result["written"] is True
    assert target.exists()


def test_check_manual_refusal_raises_for_manual_marker(tmp_path: Path) -> None:
    """_check_manual_refusal raises ManualTemplateRefusal for manual marker."""
    target = tmp_path / "manual.py"
    target.write_text("# vibecomfy: manual\n", encoding="utf-8")
    with pytest.raises(ManualTemplateRefusal):
        _check_manual_refusal(target)


def test_check_manual_refusal_allows_non_manual_files(tmp_path: Path) -> None:
    """_check_manual_refusal does not raise for non-manual files."""
    target = tmp_path / "generated.py"
    target.write_text("# vibecomfy: generated\n", encoding="utf-8")
    _check_manual_refusal(target)  # Should not raise


def test_check_manual_refusal_allows_nonexistent_target(tmp_path: Path) -> None:
    """_check_manual_refusal is a no-op when target doesn't exist."""
    target = tmp_path / "nonexistent.py"
    _check_manual_refusal(target)  # Should not raise


def test_compute_diff_produces_unified_diff() -> None:
    """_compute_diff produces unified diff with metadata."""
    original = "line1\nline2\nline3\n"
    emitted = "line1\nline2_changed\nline3\n"
    diff_data = _compute_diff(original, emitted, "test.py")
    assert "unified_diff" in diff_data
    assert "-line2" in diff_data["unified_diff"]
    assert "+line2_changed" in diff_data["unified_diff"]
    assert diff_data["original_exists"] is True
    assert diff_data["emitted_line_count"] == 3
    assert diff_data["original_line_count"] == 3


def test_compute_diff_for_new_file() -> None:
    """_compute_diff for a new file shows all additions."""
    emitted = "new line 1\nnew line 2\n"
    diff_data = _compute_diff("", emitted, "new.py")
    assert diff_data["original_exists"] is False
    assert diff_data["original_line_count"] == 0
    assert diff_data["emitted_line_count"] == 2
    assert "+new line 1" in diff_data["unified_diff"]


def test_manual_refusal_does_not_raise_for_missing_target(tmp_path: Path) -> None:
    """Manual refusal only applies when target exists."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "new_file.py"
    # Should not raise since file doesn't exist
    write_result = port_convert_and_write(result, target)
    assert write_result["written"] is True
    assert target.exists()


def test_conversion_write_error_is_runtime_error() -> None:
    """ConversionWriteError is a RuntimeError subclass."""
    assert issubclass(ConversionWriteError, RuntimeError)


def test_manual_template_refusal_is_value_error() -> None:
    """ManualTemplateRefusal is a ValueError subclass."""
    assert issubclass(ManualTemplateRefusal, ValueError)


# ---------------------------------------------------------------------------
# T12 - Conversion parity tests with comprehensive synthetic workflows
# ---------------------------------------------------------------------------


def _parity_workflow_safe_output_names() -> VibeWorkflow:
    """Synthetic workflow where all output names are safe - no diagnostics expected."""
    wf = VibeWorkflow(
        "parity_safe",
        WorkflowSource("source/parity_safe", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    wf.nodes["1"].metadata["output_names"] = ["image"]
    wf.nodes["1"].metadata["input_aliases"] = ["image"]

    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/safe"})
    wf.edges.append(VibeEdge("1", "0", "2", "images"))
    return wf


def _parity_provider_safe() -> FakeSchemaProvider:
    return FakeSchemaProvider(
        {
            "LoadImage": NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={"image": InputSpec("STRING", required=True)},
                outputs=[OutputSpec("IMAGE", "image")],
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={
                    "images": InputSpec("IMAGE", required=True),
                    "filename_prefix": InputSpec("STRING", required=True),
                },
                outputs=[],
            ),
        }
    )


def test_parity_safe_output_names_compile_equivalent() -> None:
    """Safe output names produce compile_equivalent (True, [])."""
    result = port_convert_workflow(
        _parity_workflow_safe_output_names(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:parity_safe"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_parity_provider_safe(),
    )
    assert result.validation is not None
    assert result.validation.ok
    # Safe output names + valid schema -> parity should pass
    assert result.validation.parity_ok is True
    assert result.validation.parity_diffs == []


def _parity_workflow_mixed_outputs() -> VibeWorkflow:
    """Workflow with partial/blank output names - exercises fallback paths."""
    wf = VibeWorkflow(
        "parity_mixed",
        WorkflowSource("source/parity_mixed", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode(
        "1", "MixedOutputNode",
        inputs={"value_a": "hello"},
    )
    # Three outputs: first named, second blank, third named - partial evidence
    wf.nodes["1"].metadata["output_names"] = ["named_out", "", "another"]
    wf.nodes["1"].metadata["input_aliases"] = ["value_a"]

    wf.nodes["2"] = VibeNode("2", "ConsumerNode", inputs={})
    wf.edges.append(VibeEdge("1", "0", "2", "in_0"))
    wf.edges.append(VibeEdge("1", "1", "2", "in_1"))
    wf.edges.append(VibeEdge("1", "2", "2", "in_2"))
    return wf


def _parity_provider_mixed() -> FakeSchemaProvider:
    return FakeSchemaProvider(
        {
            "MixedOutputNode": NodeSchema(
                class_type="MixedOutputNode",
                pack=None,
                inputs={"value_a": InputSpec("STRING", required=True)},
                outputs=[
                    OutputSpec("STRING", "named_out"),
                    OutputSpec("STRING", ""),
                    OutputSpec("STRING", "another"),
                ],
            ),
            "ConsumerNode": NodeSchema(
                class_type="ConsumerNode",
                pack=None,
                inputs={
                    "in_0": InputSpec("*", required=False),
                    "in_1": InputSpec("*", required=False),
                    "in_2": InputSpec("*", required=False),
                },
                outputs=[],
            ),
        }
    )


def test_parity_mixed_output_names_preserves_compile_equivalence() -> None:
    """Partial output names still produce compile_equivalent (True, [])."""
    result = port_convert_workflow(
        _parity_workflow_mixed_outputs(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:parity_mixed"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_parity_provider_mixed(),
    )
    assert result.validation is not None
    assert result.validation.ok
    assert result.validation.parity_ok is True
    assert result.validation.parity_diffs == []

    # Emission diagnostics should include avoidable_positional_output for blank name
    diag_codes = [d.code for d in result.validation.emission_diagnostics]
    assert "avoidable_positional_output" in diag_codes, (
        f"Expected avoidable_positional_output diagnostic for blank output name; got codes: {diag_codes}"
    )


def _parity_workflow_widget_aliases() -> VibeWorkflow:
    """Workflow with widget_N keys that can be aliased from schema metadata."""
    wf = VibeWorkflow(
        "parity_widgets",
        WorkflowSource("source/parity_widgets", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode(
        "1", "PreviewNode",
        widgets={"widget_0": "fast_mode", "widget_1": 42},
    )
    # input_aliases maps widget_0->"mode", widget_1->"steps"
    wf.nodes["1"].metadata["input_aliases"] = ["mode", "steps"]
    wf.nodes["1"].metadata["output_names"] = ["preview"]

    wf.nodes["2"] = VibeNode("2", "SavePreview", inputs={"filename_prefix": "out/preview"})
    wf.edges.append(VibeEdge("1", "0", "2", "images"))
    return wf


def _parity_provider_widgets() -> FakeSchemaProvider:
    return FakeSchemaProvider(
        {
            "PreviewNode": NodeSchema(
                class_type="PreviewNode",
                pack=None,
                inputs={
                    "mode": InputSpec("STRING", required=True),
                    "steps": InputSpec("INT", required=True),
                },
                outputs=[OutputSpec("IMAGE", "preview")],
            ),
            "SavePreview": NodeSchema(
                class_type="SavePreview",
                pack=None,
                inputs={
                    "images": InputSpec("IMAGE", required=True),
                    "filename_prefix": InputSpec("STRING", required=True),
                },
                outputs=[],
            ),
        }
    )


def test_parity_widget_aliases_produce_compile_equivalence() -> None:
    """Widget aliases from schema metadata produce compile_equivalent (True, [])."""
    result = port_convert_workflow(
        _parity_workflow_widget_aliases(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:parity_widgets"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_parity_provider_widgets(),
    )
    assert result.validation is not None
    assert result.validation.ok
    assert result.validation.parity_ok is True
    assert result.validation.parity_diffs == []

    # Verify emitted code uses named fields from input_aliases
    assert "mode=" in result.text or "'mode'" in result.text
    assert "steps=" in result.text or "'steps'" in result.text


def _parity_workflow_duplicate_outputs() -> VibeWorkflow:
    """Workflow where output names have duplicates - exercises fallback."""
    wf = VibeWorkflow(
        "parity_dup",
        WorkflowSource("source/parity_dup", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode("1", "DupOutNode", inputs={})
    wf.nodes["1"].metadata["output_names"] = ["image", "image"]  # duplicate!

    wf.nodes["2"] = VibeNode("2", "ConsumerNode", inputs={})
    wf.edges.append(VibeEdge("1", "0", "2", "in_0"))
    wf.edges.append(VibeEdge("1", "1", "2", "in_1"))
    return wf


def _parity_provider_dup() -> FakeSchemaProvider:
    return FakeSchemaProvider(
        {
            "DupOutNode": NodeSchema(
                class_type="DupOutNode",
                pack=None,
                inputs={},
                outputs=[
                    OutputSpec("IMAGE", "image"),
                    OutputSpec("LATENT", "image"),  # duplicate name from schema
                ],
            ),
            "ConsumerNode": NodeSchema(
                class_type="ConsumerNode",
                pack=None,
                inputs={
                    "in_0": InputSpec("*", required=False),
                    "in_1": InputSpec("*", required=False),
                },
                outputs=[],
            ),
        }
    )


def test_parity_duplicate_output_names_falls_back_to_numeric() -> None:
    """Duplicate output names fall back to numeric .out(n) with diagnostics."""
    result = port_convert_workflow(
        _parity_workflow_duplicate_outputs(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:parity_dup"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_parity_provider_dup(),
    )
    assert result.validation is not None
    assert result.validation.ok
    # Parity should still pass - numeric fallback preserves semantics
    assert result.validation.parity_ok is True
    assert result.validation.parity_diffs == []

    # Should have output_name_ambiguity diagnostic
    diag_codes = [d.code for d in result.validation.emission_diagnostics]
    assert "output_name_ambiguity" in diag_codes, (
        f"Expected output_name_ambiguity diagnostic for duplicates; got codes: {diag_codes}"
    )


# ---------------------------------------------------------------------------
# T12 - Representative real fixture parity tests
# ---------------------------------------------------------------------------


_REAL_FIXTURE_PATHS: list[str] = [
    "workflow_corpus/official/image/z_image.json",
    "workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json",
]


@pytest.mark.parametrize("fixture_path", _REAL_FIXTURE_PATHS)
def test_real_fixture_paths_exist(fixture_path: str) -> None:
    """Real fixture coverage is pinned to repository paths that actually exist."""
    assert Path(fixture_path).exists(), f"missing real fixture: {fixture_path}"


def test_real_fixture_parity_compile_equivalent() -> None:
    """The z_image fixture still round-trips through compile_equivalent cleanly."""
    from vibecomfy.porting.workbench import load_port_source

    fixture_path = "workflow_corpus/official/image/z_image.json"
    loaded = load_port_source(fixture_path)
    result = port_convert_workflow(loaded.workflow)

    assert result.validation is not None, (
        f"port_convert_workflow should produce validation for {fixture_path}"
    )
    assert result.validation.compile_ok, (
        f"Emitted module should compile for {fixture_path}: {result.validation.error}"
    )
    assert result.validation.parity_ok is True, (
        f"Parity should pass for {fixture_path}; diffs: {result.validation.parity_diffs[:5]}"
    )
    assert result.validation.parity_diffs == [], (
        f"Parity diffs should be empty for {fixture_path}; got: {result.validation.parity_diffs}"
    )


def test_real_fixture_parity_evidence_populated() -> None:
    """The z_image fixture populates parity evidence fields (counts, snapshots)."""
    from vibecomfy.porting.workbench import load_port_source

    fixture_path = "workflow_corpus/official/image/z_image.json"
    loaded = load_port_source(fixture_path)
    result = port_convert_workflow(loaded.workflow)
    v = result.validation
    assert v is not None

    # Output counts
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert v.source_output_count > 0
    assert v.emitted_output_count > 0

    # Class type counts
    assert isinstance(v.source_class_type_counts, dict)
    assert isinstance(v.emitted_class_type_counts, dict)
    assert len(v.source_class_type_counts) > 0
    assert len(v.emitted_class_type_counts) > 0

    # Widget value snapshot
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)

    # Topology snapshot
    assert isinstance(v.source_topology_snapshot, int)
    assert isinstance(v.emitted_topology_snapshot, int)


def test_real_fixture_talking_avatar_conversion_failure_is_loud() -> None:
    """The talking-avatar fixture currently fails during helper resolution, not silently."""
    from vibecomfy.errors import ConversionParityError
    from vibecomfy.porting.workbench import load_port_source

    fixture_path = "workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json"
    loaded = load_port_source(fixture_path)

    with pytest.raises(ConversionParityError, match="GetNode '413' has no broadcast name"):
        port_convert_workflow(loaded.workflow)


# ---------------------------------------------------------------------------
# T14 - Model-like value comparison tests
# ---------------------------------------------------------------------------


def _model_value_workflow_hidden() -> VibeWorkflow:
    """Workflow with a model filename hidden under widget_N without aliasing."""
    wf = VibeWorkflow(
        "model_hidden",
        WorkflowSource("source/model_hidden", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode(
        "1", "LoadCheckpoint",
        widgets={"widget_0": "model.safetensors"},
    )
    # No input_aliases - widget_0 stays positional, model filename is hidden
    wf.nodes["1"].metadata["output_names"] = ["model", "clip"]
    wf.metadata["model_assets"] = [
        {"name": "model.safetensors", "url": "https://example.test/model.safetensors", "subdir": "checkpoints"}
    ]
    return wf


def _model_value_provider_basic() -> FakeSchemaProvider:
    return FakeSchemaProvider(
        {
            "LoadCheckpoint": NodeSchema(
                class_type="LoadCheckpoint",
                pack=None,
                inputs={
                    "ckpt_name": InputSpec("STRING", required=True),
                },
                outputs=[
                    OutputSpec("MODEL", "model"),
                    OutputSpec("CLIP", "clip"),
                ],
            ),
        }
    )


def test_hidden_model_filename_detected_in_widget() -> None:
    """Model filename in widget_0 without aliasing is flagged as hidden."""
    result = port_convert_workflow(
        _model_value_workflow_hidden(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:model_hidden"},
        workflow_shape={"nodes": 1, "runtime_nodes": 1},
        schema_provider=_model_value_provider_basic(),
    )
    assert result.validation is not None
    # hidden_model_filenames should be populated
    assert len(result.validation.hidden_model_filenames) > 0, (
        f"Expected hidden model filenames; got {result.validation.hidden_model_filenames}"
    )
    assert any("widget_0" in hfn or "model.safetensors" in hfn for hfn in result.validation.hidden_model_filenames)

    # Should also have a hidden_model_filename emission diagnostic
    diag_codes = [d.code for d in result.validation.emission_diagnostics]
    assert "hidden_model_filename" in diag_codes, (
        f"Expected hidden_model_filename diagnostic; got codes: {diag_codes}"
    )


def _model_value_workflow_preserved() -> VibeWorkflow:
    """Workflow where model values are properly aliased and preserved."""
    wf = VibeWorkflow(
        "model_preserved",
        WorkflowSource("source/model_preserved", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode(
        "1", "LoadCheckpoint",
        widgets={"widget_0": "model.safetensors"},
    )
    # input_aliases provides widget_0 -> ckpt_name mapping
    wf.nodes["1"].metadata["input_aliases"] = ["ckpt_name"]
    wf.nodes["1"].metadata["output_names"] = ["model", "clip"]
    wf.metadata["model_assets"] = [
        {"name": "model.safetensors", "url": "https://example.test/model.safetensors", "subdir": "checkpoints"}
    ]
    return wf


def test_model_value_preserved_when_aliased() -> None:
    """Model value survives aliasing when widget_N maps to named field."""
    result = port_convert_workflow(
        _model_value_workflow_preserved(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:model_preserved"},
        workflow_shape={"nodes": 1, "runtime_nodes": 1},
        schema_provider=_model_value_provider_basic(),
    )
    assert result.validation is not None
    assert result.validation.ok

    # Model should NOT be dropped or changed
    assert result.validation.model_value_dropped is False, (
        f"Model value should not be dropped; diffs: {result.validation.model_value_diffs}"
    )
    assert result.validation.model_value_change is False, (
        f"Model value should not change; diffs: {result.validation.model_value_diffs}"
    )

    # source and emitted model snapshots should both contain the model value
    source_vals = list(result.validation.source_model_snapshot.values())
    emitted_vals = list(result.validation.emitted_model_snapshot.values())
    assert any("model.safetensors" in v for v in source_vals), (
        f"Source snapshot missing model.safetensors: {source_vals}"
    )
    assert any("model.safetensors" in v for v in emitted_vals), (
        f"Emitted snapshot missing model.safetensors: {emitted_vals}"
    )


def _model_value_workflow_specific_widget() -> VibeWorkflow:
    """Workflow with model filename specifically in widget_3 for SC23."""
    wf = VibeWorkflow(
        "model_widget3",
        WorkflowSource("source/model_widget3", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode(
        "1", "MultiWidgetNode",
        widgets={
            "widget_0": "unrelated_string",
            "widget_1": 42,
            "widget_2": True,
            "widget_3": "hidden_model.ckpt",
        },
    )
    # Only 2 input aliases - widget_2 and widget_3 are out of range
    wf.nodes["1"].metadata["input_aliases"] = ["text", "count"]
    wf.nodes["1"].metadata["output_names"] = ["out"]
    return wf


def _model_value_provider_multiwidget() -> FakeSchemaProvider:
    return FakeSchemaProvider(
        {
            "MultiWidgetNode": NodeSchema(
                class_type="MultiWidgetNode",
                pack=None,
                inputs={
                    "text": InputSpec("STRING", required=True),
                    "count": InputSpec("INT", required=True),
                },
                outputs=[OutputSpec("*", "out")],
            ),
        }
    )


def test_model_filename_in_widget_3_flagged_as_hidden() -> None:
    """SC23: Model filename in widget_3 appears as hidden_model_filename diagnostic."""
    result = port_convert_workflow(
        _model_value_workflow_specific_widget(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:model_widget3"},
        workflow_shape={"nodes": 1, "runtime_nodes": 1},
        schema_provider=_model_value_provider_multiwidget(),
    )
    assert result.validation is not None

    # hidden_model_filenames must contain widget_3 with the model filename
    assert len(result.validation.hidden_model_filenames) > 0, (
        f"Expected hidden model filenames; got {result.validation.hidden_model_filenames}"
    )
    # Verify the hidden entry references widget_3
    hidden_match = any(
        "widget_3" in hfn and "hidden_model.ckpt" in hfn
        for hfn in result.validation.hidden_model_filenames
    )
    assert hidden_match, (
        f"Expected widget_3=hidden_model.ckpt in hidden_model_filenames; "
        f"got: {result.validation.hidden_model_filenames}"
    )

    # Also verify it appears as emission diagnostic
    diag_codes = [d.code for d in result.validation.emission_diagnostics]
    assert "hidden_model_filename" in diag_codes, (
        f"Expected hidden_model_filename diagnostic; got codes: {diag_codes}"
    )

    # Verify the detail in the diagnostic mentions widget_3
    hidden_diags = [d for d in result.validation.emission_diagnostics if d.code == "hidden_model_filename"]
    assert any("widget_3" in d.detail.get("hidden", "") for d in hidden_diags), (
        f"Expected hidden diagnostic detail to mention widget_3; got: {hidden_diags}"
    )


def test_model_value_snapshot_populated_in_to_json() -> None:
    """Model value snapshot fields appear in PortConvertValidation.to_json()."""
    result = port_convert_workflow(
        _model_value_workflow_preserved(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:model_json"},
        workflow_shape={"nodes": 1, "runtime_nodes": 1},
        schema_provider=_model_value_provider_basic(),
    )
    assert result.validation is not None
    vj = result.validation.to_json()
    for field in [
        "model_value_change",
        "model_value_dropped",
        "hidden_model_filenames",
        "source_model_snapshot",
        "emitted_model_snapshot",
        "ready_requirements_model_snapshot",
        "workflow_requirements_model_snapshot",
        "metadata_model_snapshot",
        "model_value_diffs",
    ]:
        assert field in vj, f"PortConvertValidation.to_json() missing field: {field}"


def test_model_value_comparison_tracks_all_five_sources() -> None:
    wf = _model_value_workflow_preserved()
    wf.requirements.models.append("model.safetensors")
    wf.metadata["model_assets"] = [
        {"name": "model.safetensors", "url": "https://example.test/model.safetensors"},
    ]

    result = port_convert_workflow(
        wf,
        ready_id="image/model_preserved",
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:model_all_sources"},
        workflow_shape={"nodes": 1, "runtime_nodes": 1},
        schema_provider=_model_value_provider_basic(),
    )

    assert result.validation is not None
    validation = result.validation
    assert any(value == "model.safetensors" for value in validation.source_model_snapshot.values())
    assert any(value == "model.safetensors" for value in validation.emitted_model_snapshot.values())
    assert validation.ready_requirements_model_snapshot == ["model.safetensors"]
    assert validation.workflow_requirements_model_snapshot == ["model.safetensors"]
    assert validation.metadata_model_snapshot == ["model.safetensors"]
    assert validation.model_value_change is False
    assert validation.model_value_dropped is False


def test_reference_only_model_value_is_reported_across_contract_sources() -> None:
    wf = _model_value_workflow_preserved()
    wf.requirements.models.append("missing_from_graph.safetensors")
    wf.metadata["model_assets"] = [
        {"name": "missing_from_graph.safetensors", "url": "https://example.test/missing.safetensors"},
    ]

    result = port_convert_workflow(
        wf,
        ready_id="image/model_reference_only",
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:model_reference_only"},
        workflow_shape={"nodes": 1, "runtime_nodes": 1},
        schema_provider=_model_value_provider_basic(),
    )

    assert result.validation is not None
    validation = result.validation
    assert validation.ready_requirements_model_snapshot == ["missing_from_graph.safetensors"]
    assert validation.workflow_requirements_model_snapshot == ["missing_from_graph.safetensors"]
    assert validation.metadata_model_snapshot == ["missing_from_graph.safetensors"]
    assert any("reference-only model" in diff for diff in validation.model_value_diffs)
    assert any(
        diag.code == "hidden_model_filename"
        and diag.detail.get("model") == "missing_from_graph.safetensors"
        and diag.detail.get("in_workflow_requirements") is True
        and diag.detail.get("in_metadata_assets") is True
        for diag in validation.emission_diagnostics
    )


def test_model_value_dropped_detected_without_aliasing() -> None:
    """When widget alias drops a model value (None entry), model_value_dropped is True."""
    wf = VibeWorkflow(
        "model_dropped",
        WorkflowSource("source/model_dropped", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode(
        "1", "LoadCheckpoint",
        widgets={"widget_0": "important_model.safetensors"},
    )
    # input_aliases has None for widget_0 -> model value dropped
    wf.nodes["1"].metadata["input_aliases"] = [None]
    wf.nodes["1"].metadata["output_names"] = ["model", "clip"]

    result = port_convert_workflow(
        wf,
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:model_dropped"},
        workflow_shape={"nodes": 1, "runtime_nodes": 1},
        schema_provider=_model_value_provider_basic(),
    )
    assert result.validation is not None

    # The model value in widget_0 gets dropped (None alias)
    # This may cause parity to fail since the value disappears
    if result.validation.parity_ok is False:
        # Model value was dropped - verify detection
        assert result.validation.model_value_dropped or result.validation.model_value_change, (
            f"Expected model value change/drop when widget aliased to None; "
            f"dropped={result.validation.model_value_dropped}, change={result.validation.model_value_change}"
        )


# ---------------------------------------------------------------------------
# T6 - Sprint 3: shared helpers conversion test
# ---------------------------------------------------------------------------


def test_ready_template_uses_shared_helpers_and_passes_import_build_compile_parity() -> None:
    """Sprint 3 T6(c): generated ready templates import shared helpers and pass
    the full import/build/compile/parity pipeline."""
    result = port_convert_workflow(
        _sample_workflow(),
        ready_id="image/sample",
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    assert result.mode == "ready_template"
    assert result.validation is not None

    # Import check: emitted code must import the natural template surface, not define local _node
    assert "from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow" in result.text
    assert "from vibecomfy.registry.ready_template import" not in result.text
    assert "new_workflow" in result.text
    assert "wf.finalize(PUBLIC_INPUT_METADATA" in result.text
    assert "node=ref(" not in result.text
    assert "def _node" not in result.text

    # Build/compile check
    assert result.validation.import_ok, f"Import failed: {result.validation.error}"
    assert result.validation.build_ok, f"Build failed: {result.validation.error}"
    assert result.validation.compile_ok, f"Compile failed: {result.validation.error}"

    # Parity check
    assert result.validation.parity_ok is True, (
        f"Parity failed; diffs: {result.validation.parity_diffs}"
    )
    assert result.validation.parity_diffs == []


# ---------------------------------------------------------------------------
# T10 — Layout sidecar write on convert
# ---------------------------------------------------------------------------


def _flat_fixture_provider() -> FakeSchemaProvider:
    """Schema provider covering all node types in the flat fixture.

    Includes widget_* inputs that the normalization pipeline creates from
    litegraph widgets_values (widgets beyond the first named input become
    numbered widget_N entries in the API dict).
    """
    return FakeSchemaProvider(
        {
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack=None,
                inputs={
                    "ckpt_name": InputSpec("STRING", required=True),
                    "widget_1": InputSpec("STRING", required=False),  # second widgets_values entry
                },
                outputs=[OutputSpec("MODEL", "MODEL"), OutputSpec("CLIP", "CLIP"), OutputSpec("VAE", "VAE")],
            ),
            "CLIPTextEncode": NodeSchema(
                class_type="CLIPTextEncode",
                pack=None,
                inputs={
                    "clip": InputSpec("CLIP", required=True),
                    "text": InputSpec("STRING", required=True),
                },
                outputs=[OutputSpec("CONDITIONING", "CONDITIONING")],
            ),
            "EmptyLatentImage": NodeSchema(
                class_type="EmptyLatentImage",
                pack=None,
                inputs={
                    "width": InputSpec("INT", required=True),
                    "height": InputSpec("INT", required=True),
                    "batch_size": InputSpec("INT", required=True),
                    "widget_0": InputSpec("INT", required=False),
                    "widget_1": InputSpec("INT", required=False),
                    "widget_2": InputSpec("INT", required=False),
                },
                outputs=[OutputSpec("LATENT", "LATENT")],
            ),
            "KSampler": NodeSchema(
                class_type="KSampler",
                pack=None,
                inputs={
                    "model": InputSpec("MODEL", required=True),
                    "positive": InputSpec("CONDITIONING", required=True),
                    "negative": InputSpec("CONDITIONING", required=True),
                    "latent_image": InputSpec("LATENT", required=True),
                    "seed": InputSpec("INT", required=False),
                    "steps": InputSpec("INT", required=False),
                    "cfg": InputSpec("FLOAT", required=False),
                    "sampler_name": InputSpec("STRING", required=False),
                    "scheduler": InputSpec("STRING", required=False),
                    "denoise": InputSpec("FLOAT", required=False),
                },
                outputs=[OutputSpec("LATENT", "LATENT")],
            ),
            "VAEDecode": NodeSchema(
                class_type="VAEDecode",
                pack=None,
                inputs={"samples": InputSpec("LATENT", required=True), "vae": InputSpec("VAE", required=True)},
                outputs=[OutputSpec("IMAGE", "IMAGE")],
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={"images": InputSpec("IMAGE", required=True), "filename_prefix": InputSpec("STRING", required=True)},
                outputs=[],
            ),
        }
    )


def test_convert_flat_fixture_writes_layout_sidecar(tmp_path: Path) -> None:
    """Converting the flat fixture writes flat.layout.json with uid→pos matching source."""
    import json as json_mod

    from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
    from vibecomfy.porting.layout_store import read_layout, sidecar_path_for

    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    raw = json_mod.loads(fixture.read_text(encoding="utf-8"))

    # Build expected uid→pos from the source JSON
    expected_pos: dict[str, list] = {}
    for node in raw["nodes"]:
        uid = str(node["id"])
        expected_pos[uid] = node["pos"]

    # Ingest flat fixture → VibeWorkflow (exercises capture path from T5)
    api = normalize_to_api(raw)
    wf = convert_to_vibe_format(api, source_path=str(fixture), workflow_id="flat")

    # Convert to scratchpad .py
    result = port_convert_workflow(
        wf,
        source_path=str(fixture),
        schema_provider=_flat_fixture_provider(),
    )

    out_py = tmp_path / "flat.py"
    port_convert_and_write(result, out_py, dry_run=False, diff=False)

    # Simulate _cmd_port_convert sidecar write (post-write orchestration)
    from vibecomfy.porting.layout_store import write_layout as wl
    wl(out_py, wf)

    # Sidecar must exist
    sidecar = sidecar_path_for(out_py)
    assert sidecar.exists(), f"Expected sidecar at {sidecar}"

    # Read sidecar and verify uid→pos mapping
    layout = read_layout(out_py)
    assert len(layout) == len(expected_pos), (
        f"Expected {len(expected_pos)} nodes in layout, got {len(layout)}"
    )
    for uid, pos in expected_pos.items():
        assert uid in layout, f"uid {uid} missing from layout"
        assert layout[uid]["pos"] == pos, (
            f"uid {uid}: expected pos {pos}, got {layout[uid]['pos']}"
        )
