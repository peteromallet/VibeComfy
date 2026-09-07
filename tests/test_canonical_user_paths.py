"""Five no-GPU canonical user paths for the final immutable candidate."""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.security.provenance import Provenance


REPO_ROOT = Path(
    os.environ.get("VIBECOMFY_T25_ROOT", Path(__file__).resolve().parents[1])
)
H3_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "h3_canonical.py"


class _ConvertProvider:
    def __init__(self) -> None:
        self._schemas = {
            "EmptyImage": NodeSchema(
                "EmptyImage", None,
                {
                    "width": InputSpec("INT", True, 64),
                    "height": InputSpec("INT", True, 64),
                    "batch_size": InputSpec("INT", True, 1),
                    "color": InputSpec("INT", False, 0),
                },
                [OutputSpec("IMAGE", "IMAGE")],
                widget_input_order=("width", "height", "batch_size", "color"),
            ),
            "SaveImage": NodeSchema(
                "SaveImage", None,
                {
                    "images": InputSpec("IMAGE", True, None),
                    "filename_prefix": InputSpec("STRING", False, "out"),
                },
                [],
                widget_input_order=("filename_prefix",),
            ),
        }

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return dict(self._schemas)


def _convert_ui() -> dict:
    return {
        "workflow_id": "workflow",
        "last_node_id": 2,
        "last_link_id": 1,
        "nodes": [
            {
                "id": 1, "type": "EmptyImage", "pos": [20, 30], "size": [180, 80],
                "flags": {}, "order": 0, "mode": 0, "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
                "properties": {"vibecomfy_uid": "t25-source"},
                "widgets_values": [64, 64, 1, 0],
            },
            {
                "id": 2, "type": "SaveImage", "pos": [300, 30], "size": [180, 80],
                "flags": {}, "order": 1, "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                "outputs": [], "properties": {"vibecomfy_uid": "t25-save"},
                "widgets_values": ["out/t25"],
            },
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
        "groups": [], "config": {}, "extra": {}, "version": 0.4,
    }


def test_ui_json_convert_optional_sidecar_loads_and_compiles_exact_graph(tmp_path: Path) -> None:
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.convert import port_convert_and_write, port_convert_workflow
    from vibecomfy.workflow_bundle import capture_bundle, load_bundle

    provider = _ConvertProvider()
    raw_ui = _convert_ui()
    workflow = from_ui(raw_ui, schema_provider=provider, use_comfy_converter=False)
    expected_api = {
        "1": {"class_type": "EmptyImage", "inputs": {"width": 64, "height": 64, "batch_size": 1, "color": 0}},
        "2": {"class_type": "SaveImage", "inputs": {"filename_prefix": "out/t25", "images": ["1", 0]}},
    }
    assert workflow.compile("api") == expected_api

    plain_path = tmp_path / "plain.py"
    conversion = port_convert_workflow(
        workflow, source_path="workflow.json", raw_workflow=raw_ui,
        schema_provider=provider, validate=True,
    )
    assert conversion.validation is not None and conversion.validation.parity_ok is True
    assert port_convert_and_write(conversion, plain_path)["written"] is True
    plain = load_bundle(plain_path, trust=Provenance.USER_CONFIRMED, schema_provider=provider)
    assert plain.ui_sidecar is None
    assert plain.workflow.compile("api") == expected_api

    paired_path = tmp_path / "paired.py"
    captured = capture_bundle(
        raw_ui, paired_path, {"operation": "captured"}, schema_provider=provider,
    )
    assert paired_path.with_suffix(".vibe.json").is_file()
    paired = load_bundle(paired_path, trust=Provenance.USER_CONFIRMED, schema_provider=provider)
    assert paired.workflow.compile("api") == expected_api
    assert paired.semantic_digest == captured.semantic_digest
    emitted_ui = paired.materialize_ui(schema_provider=provider)
    assert {str(node["id"]): node["pos"] for node in emitted_ui["nodes"]} == {
        "1": [20.0, 30.0], "2": [300.0, 30.0],
    }


def test_canvas_edit_prepare_persist_finalize_and_reopen_retains_ui_authority(tmp_path: Path) -> None:
    from tests import test_comfy_nodes_agent_backend_spine as spine

    root, session_id, turn_id, candidate_hash, structural_hash, plan_hash = (
        spine._setup_v2_session_with_candidate(tmp_path)
    )
    prepared = spine.prepare_turn_transaction(
        session_root=root, session_id=session_id, turn_id=turn_id,
        request_payload={"plan_hash": plan_hash, "candidate_graph_hash": candidate_hash},
    )
    assert prepared["phase"] == "prepared"
    persisted_prepared = spine.reconcile_turn_transactions(
        session_root=root, session_id=session_id, turn_id=turn_id,
    )["transactions_by_turn"][turn_id]
    assert persisted_prepared["state"] == "prepared"
    assert persisted_prepared["generation"] == prepared["generation"]
    assert persisted_prepared["lease_nonce"] == prepared["lease_nonce"]
    assert persisted_prepared["plan"] == prepared["candidate_transaction"]["plan"]

    applied_graph = spine.canonical_candidate_graph(root, session_id, turn_id)
    applied_snapshot = copy.deepcopy(applied_graph)
    finalized = spine.finalize_turn_transaction(
        session_root=root, session_id=session_id, turn_id=turn_id,
        request_payload={
            "plan_hash": plan_hash,
            "generation": prepared["generation"],
            "lease_nonce": prepared["lease_nonce"],
            "post_apply_hash": structural_hash,
            "post_apply_graph": applied_graph,
            "applied_delta_hash": prepared["candidate_transaction"]["plan"]["delta_hash"],
            "post_apply_hash_verified": True,
            "browser_verified": True,
        },
    )
    approved_canonical = finalized["approved_record_canonical"]
    approved = json.loads(approved_canonical)
    assert finalized["phase"] == "finalized"
    assert approved["revision_id"] == finalized["revision_id"]
    assert approved["revision_id"] != finalized["parent_revision"]

    # Reopen both durable views after mutating caller-owned copies.  Neither
    # the response nor applied UI authority may alias those copies.
    applied_graph["nodes"][0]["type"] = "TamperedAfterFinalize"
    approved["revision_id"] = "tampered-after-finalize"
    reopened_ui = json.loads(
        (root / session_id / "turns" / turn_id / "applied.ui.json").read_text(encoding="utf-8")
    )
    assert reopened_ui == applied_snapshot
    assert json.loads(approved_canonical)["revision_id"] == finalized["revision_id"]
    reconciled = spine.reconcile_turn_transactions(
        session_root=root, session_id=session_id, turn_id=turn_id,
    )
    assert reconciled["transactions_by_turn"][turn_id]["state"] == "finalized"


def test_cli_server_and_runpod_use_one_immutable_approved_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.commands import run as run_command
    from vibecomfy.runtime.execution import queue_server_prompt
    from vibecomfy.runtime.runpod_adapter import queue_runpod_stub
    from vibecomfy.testing.canonical import canonical_digest

    captured: list[tuple[object, object]] = []

    def embedded_transport(record, bundle, **_kwargs):
        captured.append((record, bundle))
        return SimpleNamespace(run_id="t25-cli", prompt_id="t25-cli", metadata_path="offline.json")

    monkeypatch.setattr(run_command, "run_embedded_sync", embedded_transport)
    args = argparse.Namespace(
        path="smoke/empty_image_red", runtime="embedded", server_url=None,
        backend="api", prompt=None, seed=None, steps=None, memory_profile=None,
        ensure_packs=False, ensure_models=False, shared_models_root=None,
        quiet_schema_degradation=False,
    )
    assert run_command._cmd_run(args) == 0
    record, bundle = captured[0]
    canonical_before = record.to_canonical_bytes()

    payloads: list[dict] = []

    class Server:
        async def _post_prompt(self, payload):
            payloads.append(payload)
            return {"prompt_id": "t25-server"}

    asyncio.run(queue_server_prompt(record, bundle, client=Server()))
    queue_runpod_stub(
        record, bundle,
        queue=lambda payload: payloads.append(payload) or {"prompt_id": "t25-runpod"},
    )
    assert len(payloads) == 2
    assert all(canonical_digest(payload) == record.api_digest for payload in payloads)
    assert record.revision_id == bundle.revision_id
    assert record.to_canonical_bytes() == canonical_before


def test_unknown_node_and_model_return_parallel_exact_reconciliation_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    import vibecomfy.commands.nodes as nodes_command
    from vibecomfy.registry import models_loader
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource
    from vibecomfy.workflow_bundle import emit_bundle

    workflow = VibeWorkflow("t25-reconcile", WorkflowSource("t25-reconcile"))
    workflow.add_node(
        "UnknownT25Node", _id="1", uid="unknown-t25",
        ckpt_name="missing-t25.safetensors",
    )
    source = tmp_path / "candidate.py"
    emit_bundle(workflow, source, {"operation": "authored"})
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text("", encoding="utf-8")

    class EmptyProvider:
        def schemas(self):
            return {}

        def get_schema(self, _class_type):
            return None

    # Only external evidence seams are fixed.  The CLI parser, workflow loader,
    # source trust boundary, scanner, pairing, and remediation formatter run.
    monkeypatch.setattr(nodes_command, "get_authoring_schema_provider", lambda **_: EmptyProvider())
    monkeypatch.setattr(nodes_command.node_packs_install, "get_known_node_packs", lambda *_: ())
    monkeypatch.setattr(models_loader, "load_registry", lambda *_: ())
    monkeypatch.setattr(models_loader, "resolve_model_entry", lambda *_args, **_kwargs: None)
    args = argparse.Namespace(
        workflow=str(source), json=True, lockfile=str(lockfile),
        registry=str(tmp_path / "models.yaml"), models_root=str(tmp_path / "models"),
        server_url=None,
    )
    assert nodes_command._cmd_nodes_reconcile(args) == 1
    payload = json.loads(capsys.readouterr().out)
    diagnostics = {
        (item["subject_type"], item["code"], item["details"]["target"])
        for item in payload["diagnostics"]
    }
    assert diagnostics == {
        ("node", "unknown_node", "UnknownT25Node"),
        ("model", "unknown_model", "missing-t25.safetensors"),
    }
    commands = {item["action"]: item["command"] for item in payload["remediations"]}
    assert commands["lookup"] == "vibecomfy nodes lookup 'UnknownT25Node' --json"
    assert commands["register"] == (
        f"add a valid model row to '{tmp_path / 'models.yaml'}' and rerun "
        f"vibecomfy nodes reconcile --workflow '{source}' --json "
        f"--lockfile '{lockfile}' --registry '{tmp_path / 'models.yaml'}' "
        f"--models-root '{tmp_path / 'models'}'"
    )


def test_h3_load_and_compile_retain_reference_mask_and_active_output_roles() -> None:
    from vibecomfy.workflow_bundle import load_bundle
    from vibecomfy.workflow import NodeMode

    text = H3_FIXTURE.read_text(encoding="utf-8")
    assert "def build()" in text
    assert "._node" not in text
    assert ".add(" not in text
    assert "raw_call(" in text
    bundle = load_bundle(H3_FIXTURE, trust=Provenance.USER_CONFIRMED)
    workflow = bundle.workflow
    reopened = load_bundle(H3_FIXTURE, trust=Provenance.USER_CONFIRMED).workflow
    assert workflow.metadata["h3_source_repository"] == (
        "seitanism/ComfyUI-H3-Motion-Context-MultiRef"
    )
    assert workflow.metadata["h3_source_commit"] == (
        "2ed4b27e5e262a996ad2670ac6d2fd2e505cf3a3"
    )
    assert workflow.semantic_digest() == reopened.semantic_digest()
    assert workflow.compile("api") == reopened.compile("api")
    api = workflow.compile("api")
    assert (len(workflow.nodes), len(workflow.edges)) == (100, 259)
    assert sum(node.mode is NodeMode.ENABLED for node in workflow.nodes.values()) == 43
    assert sum(node.mode is NodeMode.BYPASSED for node in workflow.nodes.values()) == 57

    by_type = {}
    for node_id, item in api.items():
        by_type.setdefault(item["class_type"], []).append((node_id, item))
    ref_id, reference = by_type["MiniMaxH3ReferenceToVideo"][0]
    guider_id, guider = by_type["BasicGuider"][0]
    mask_id, masked = by_type["MiniMaxH3StartMaskedContext"][0]
    sampler_id, sampler = by_type["SamplerCustomAdvanced"][0]
    stream_id, stream = by_type["MiniMaxH3StreamLiveExtensionAVToVHS"][0]
    assert guider["inputs"]["conditioning"] == [ref_id, 0]
    assert masked["inputs"]["latent"] == [ref_id, 1]
    assert sampler["inputs"]["guider"] == [guider_id, 0]
    assert sampler["inputs"]["latent_image"] == [mask_id, 0]
    assert stream["inputs"]["extension_1"] == [sampler_id, 0]
    for field in ("ref_images.ref_image_0", "ref_images.ref_image_1"):
        source_id, slot = reference["inputs"][field]
        assert slot == 0
        assert api[source_id]["class_type"] == "LoadImage"
