from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.ingest.snapshot import capture_workflow_snapshot
from vibecomfy.runtime.execution import _final_output_chain_node_ids
from vibecomfy.runtime.reconciliation import (
    ReconciliationError,
    assert_execution_snapshot,
    build_execution_snapshot,
    reconcile_before_queue,
)
from vibecomfy.commands.runpod import _cmd_runpod_bind
from vibecomfy.runtime.session_binding import load_binding
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import RawWidgetPayload, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import (
    _generated_metadata_expressions,
    _make_bundle,
    emit_bundle,
    load_bundle,
)
from vibecomfy.security.provenance import Provenance


class _LiveProvider:
    requires_fresh_target = True
    server_url = "http://live.test"

    def __init__(self) -> None:
        self.generation = "process-7"
        self._schema = NodeSchema(
            class_type="DriftNode",
            pack="test",
            inputs={"strength": InputSpec(type="FLOAT")},
            outputs=[OutputSpec(type="ANY", name="output")],
            widget_input_order=("strength",),
            source_hash="target-schema",
            source_version="target-v2",
        )

    def object_info(self):
        return {"DriftNode": {"input": {"required": {"strength": ["FLOAT", {}]}}}}

    def get_schema(self, class_type: str):
        return self._schema if class_type == "DriftNode" else None


def _bundle(tmp_path: Path):
    workflow = VibeWorkflow(
        "drift",
        WorkflowSource(
            id="drift",
            path=str(tmp_path / "workflow.py"),
            source_type="python",
            provenance={"source_revision": "source-revision", "operation": "authored"},
        ),
    )
    workflow.nodes["1"] = VibeNode(
        "1",
        "DriftNode",
        uid="node-1",
        widgets={"widget_0": 0.5},
        metadata={"schema_source": {"hash": "source-schema", "version": "source-v1"}},
        raw_widgets=RawWidgetPayload(
            values=[0.5], shape="list", source="ui.widgets_values", has_dict_rows=False, length=1
        ),
    )
    workflow.metadata["_workflow_snapshot"] = capture_workflow_snapshot(
        {}, workflow, source_representation="python", schema_provider=_LiveProvider()
    )
    return _make_bundle(
        workflow,
        python_path=None,
        ui_sidecar=None,
        provenance={"operation": "authored", "provenance": {"source": "test"}},
        operation="authored",
    )


def test_live_reconciliation_maps_legacy_slot_and_records_target_generation(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    result = reconcile_before_queue(bundle, target_schema_provider=_LiveProvider(), publish=False)

    assert result.changed is True
    assert result.schema["generation"] == "process-7"
    assert result.decisions[0]["mappings"][0]["target_field"] == "strength"
    assert result.bundle.workflow.nodes["1"].widgets == {"strength": 0.5}
    assert result.bundle.workflow.metadata["reconciliation"]["target_schema_generation"] == "process-7"


def test_live_reconciliation_keeps_canonical_bundle_when_no_legacy_slots(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    bundle.workflow.nodes["1"].widgets = {"strength": 0.5}
    result = reconcile_before_queue(bundle, target_schema_provider=_LiveProvider(), publish=False)

    assert result.changed is False
    assert result.bundle is bundle


def test_execution_snapshot_rejects_schema_digest_or_generation_drift(tmp_path: Path) -> None:
    provider = _LiveProvider()
    result = reconcile_before_queue(_bundle(tmp_path), target_schema_provider=provider, publish=False)
    provider._object_info = provider.object_info()
    snapshot = build_execution_snapshot(
        result.bundle,
        result.bundle.compile(schema_provider=provider),
        schema=result.schema,
    ).to_dict()

    assert_execution_snapshot(
        snapshot,
        result.bundle,
        result.bundle.compile(schema_provider=provider),
        schema_provider=provider,
    )
    provider._object_info["AnotherNode"] = {}
    with pytest.raises(ReconciliationError, match="execution snapshot changed"):
        assert_execution_snapshot(
            snapshot,
            result.bundle,
            result.bundle.compile(schema_provider=provider),
            schema_provider=provider,
        )

    provider._object_info.pop("AnotherNode")
    provider.generation = "process-8"
    with pytest.raises(ReconciliationError, match="execution snapshot changed"):
        assert_execution_snapshot(
            snapshot,
            result.bundle,
            result.bundle.compile(schema_provider=provider),
            schema_provider=provider,
        )


def test_runpod_bind_records_named_custody_without_api_or_filesystem_provisioning(tmp_path: Path) -> None:
    args = SimpleNamespace(
        pod_id="pod-123",
        session="migration",
        comfy_root="/workspace/ComfyUI",
        python_executable="/workspace/ComfyUI/.venv/bin/python",
        custom_nodes_root="/workspace/ComfyUI/custom_nodes",
        models_root="/workspace/ComfyUI/models",
        launch_flags=["--use-ck-attention"],
        runtime_root=str(tmp_path),
        replace=False,
    )

    assert _cmd_runpod_bind(args) == 0
    binding = load_binding("migration", tmp_path)
    assert binding == {
        "pod_id": "pod-123",
        "comfy_root": "/workspace/ComfyUI",
        "python_executable": "/workspace/ComfyUI/.venv/bin/python",
        "custom_nodes_root": "/workspace/ComfyUI/custom_nodes",
        "models_root": "/workspace/ComfyUI/models",
        "launch_flags": ["--use-ck-attention"],
        "remote": True,
        "schema_version": 1,
        "session_id": "migration",
    }


def test_runpod_bind_can_record_reachable_comfy_endpoint(tmp_path: Path) -> None:
    args = SimpleNamespace(
        pod_id="pod-123",
        session="migration",
        comfy_root="/workspace/ComfyUI",
        python_executable="/workspace/ComfyUI/.venv/bin/python",
        custom_nodes_root=None,
        models_root=None,
        launch_flags=[],
        runtime_root=str(tmp_path),
        replace=False,
        comfy_url="https://pod-123-8188.proxy.runpod.net",
    )

    assert _cmd_runpod_bind(args) == 0
    binding = load_binding("migration", tmp_path)
    assert binding["comfy_url"] == "https://pod-123-8188.proxy.runpod.net"


def test_reconciliation_materializes_dynamic_ports_and_is_idempotent(tmp_path: Path) -> None:
    class DynamicProvider(_LiveProvider):
        def __init__(self) -> None:
            self.generation = "process-dynamic"
            self._schema = NodeSchema(
                class_type="ImageConcatMulti",
                pack="test",
                inputs={"inputcount": InputSpec(type="INT", required=True)},
                outputs=[OutputSpec(type="IMAGE", name="image")],
                widget_input_order=("inputcount",),
            )

        def object_info(self):
            return {"ImageConcatMulti": {"input": {"required": {"inputcount": ["INT", {}]}}}}

        def get_schema(self, class_type: str):
            return self._schema if class_type == "ImageConcatMulti" else None

    workflow = VibeWorkflow("dynamic", WorkflowSource("dynamic"))
    workflow.nodes["1"] = VibeNode(
        "1", "ImageConcatMulti", uid="dynamic-node", inputs={"inputcount": 3}
    )
    bundle = _make_bundle(
        workflow,
        python_path=None,
        ui_sidecar=None,
        provenance={"operation": "authored"},
        operation="authored",
    )
    provider = DynamicProvider()
    first = reconcile_before_queue(bundle, target_schema_provider=provider, publish=False)
    names = first.bundle.workflow.nodes["1"].native_input_names
    assert names is not None
    assert {"image_1", "image_2", "image_3"}.issubset(names)
    assert any(item["code"] == "dynamic_ports_materialized" for item in first.diagnostics)

    second = reconcile_before_queue(
        first.bundle, target_schema_provider=provider, publish=False
    )
    assert second.changed is False
    assert second.bundle.workflow.semantic_projection() == first.bundle.workflow.semantic_projection()


def test_final_output_chain_includes_authored_virtual_wire_ancestry(tmp_path: Path) -> None:
    workflow = VibeWorkflow("virtual-chain", WorkflowSource("virtual-chain"))
    workflow.nodes["1"] = VibeNode(
        "1", "Source", uid="source", native_output_names=["out"]
    )
    workflow.nodes["2"] = VibeNode(
        "2", "Target", uid="target", inputs={"value": None}, native_input_names=["value"]
    )
    workflow.virtual_wires = {
        "wire": {
            "scope_path": "",
            "legs": [{
                "scope_path": "",
                "leg_index": 0,
                "occurrence_index": 0,
                "from_node": "source",
                "from_output": "out",
                "to_node": "target",
                "to_input": "value",
            }],
        }
    }
    workflow.outputs = [VibeOutput("2", "Target")]
    bundle = _make_bundle(
        workflow,
        python_path=None,
        ui_sidecar=None,
        provenance={"operation": "authored"},
        operation="authored",
    )

    assert _final_output_chain_node_ids(bundle) == {"1", "2"}


def test_published_reconciliation_reloads_ready_metadata_snapshot(tmp_path: Path) -> None:
    workflow = _bundle(tmp_path).workflow
    path = tmp_path / "workflow.py"
    initial = emit_bundle(
        workflow, path, {"operation": "authored", "provenance": {"source": "test"}}
    )
    bound = _make_bundle(
        workflow,
        python_path=path,
        ui_sidecar=initial.ui_sidecar,
        provenance=initial.provenance,
        operation="authored",
    )

    result = reconcile_before_queue(
        bound, target_schema_provider=_LiveProvider(), publish=True
    )
    assert result.changed is True
    assert result.bundle.workflow.nodes["1"].widgets == {"strength": 0.5}
    reopened = load_bundle(
        path, trust=Provenance.USER_CONFIRMED, allow_unresolved=True
    )
    assert reopened.workflow.metadata["operation"] == "captured"
    assert isinstance(reopened.workflow.metadata["provenance"], dict)
    _expressions, metadata = _generated_metadata_expressions(path.read_bytes())
    assert metadata["operation"] == "captured"
    assert isinstance(metadata["provenance"], dict)
    assert isinstance(metadata["source_bundle"], dict)
    assert reopened.workflow.semantic_digest() == result.bundle.workflow.semantic_digest()
