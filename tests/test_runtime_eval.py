from __future__ import annotations

import asyncio
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vibecomfy.cli_loader import load_bundle
from vibecomfy.errors import RuntimeNodeError
from vibecomfy.runtime.eval import approve_eval_subgraph, plan_eval_node, select_eval_workflow
from vibecomfy.runtime.eval import prompt as eval_prompt
from vibecomfy.runtime.session import RunResult
from vibecomfy.testing.canonical import canonical_digest
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.registry.models_loader import ModelEntry, ModelSource, ModelTarget
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import ApprovedProjectionRecord, WorkflowBundleError


def _bundle() -> object:
    workflow = VibeWorkflow("eval-source", WorkflowSource("eval-source"))
    workflow.nodes["1"] = VibeNode(
        "1", "VAEDecode", uid="source-1", inputs={"samples": ["latent", 0], "vae": ["vae", 0]}
    )
    workflow.nodes["latent"] = VibeNode("latent", "LatentSource", uid="latent", inputs={})
    workflow.nodes["vae"] = VibeNode("vae", "VAELoader", uid="vae", inputs={"vae_name": "x.vae"})
    workflow.edges.extend([
        VibeEdge("latent", "0", "1", "samples"),
        VibeEdge("vae", "0", "1", "vae"),
    ])
    return load_bundle(workflow)


def _record(bundle, api=None):
    api = api or {"1": {"class_type": "VAEDecode", "inputs": {}}}
    return ApprovedProjectionRecord(bundle.revision_id, None, {}, api, {}, canonical_digest(api))


def test_select_is_parent_bound_copy_with_deterministic_preview() -> None:
    parent = _bundle()
    candidate = select_eval_workflow(parent, "1")
    assert candidate.id == parent.workflow.id == candidate.source.id
    assert candidate is not parent.workflow
    assert candidate.nodes["1"] is not parent.workflow.nodes["1"]
    assert candidate.nodes["1_preview"].uid == "1_preview"
    assert candidate.groups == []
    assert {node.id for node in candidate.nodes.values()} == {"1", "latent", "vae", "1_preview"}
    assert "1_preview" not in parent.workflow.nodes


def test_selection_and_plan_reject_bare_inputs_without_compile() -> None:
    with pytest.raises(WorkflowBundleError, match="requires a WorkflowBundle"):
        select_eval_workflow("source.py", "1")
    with pytest.raises(WorkflowBundleError, match="requires a WorkflowBundle"):
        plan_eval_node("source.py", "1")
    parent = _bundle()
    with pytest.raises(RuntimeNodeError):
        select_eval_workflow(parent, "root/1")
    assert plan_eval_node(parent, "root/1").truncated_api == {}


def test_approval_uses_ephemeral_candidate_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _bundle()
    original = type(parent).compile
    calls = []

    def fake_compile(self, **kwargs):
        calls.append(self)
        api = {"1": {"class_type": "VAEDecode", "inputs": {}}, "1_preview": {"class_type": "PreviewImage", "inputs": {"images": ["1", 0]}}}
        return _record(self, api)

    monkeypatch.setattr(type(parent), "compile", fake_compile)
    try:
        candidate, record = approve_eval_subgraph(parent, "1")
        candidate2, record2 = approve_eval_subgraph(parent, "1")
    finally:
        monkeypatch.setattr(type(parent), "compile", original)
    assert candidate.revision_id != parent.revision_id
    assert record.revision_id == candidate.revision_id
    assert record.to_canonical_bytes() == record2.to_canonical_bytes()
    assert calls and all(item.workflow.id == parent.workflow.id for item in calls)


def test_plan_is_descriptive_and_has_no_raw_api() -> None:
    plan = plan_eval_node(_bundle(), "1")
    assert plan.queueable is True
    assert plan.truncated_api == {}
    assert "compile" not in {node.func.attr for node in ast.walk(ast.parse(Path(eval_prompt.__file__).read_text())) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}


def test_eval_delegates_prompt_id_and_candidate_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _bundle()
    candidate = _bundle()
    record = _record(candidate)
    seen = []

    async def fake_run_embedded(received_record, received_bundle, **kwargs):
        seen.append((received_record, received_bundle, kwargs))
        return RunResult("run-1", "prompt-1", ["out.png"], "meta.json", "run.log")

    monkeypatch.setattr(eval_prompt, "approve_eval_subgraph", lambda *args, **kwargs: (candidate, record))
    monkeypatch.setattr(eval_prompt, "run_embedded", fake_run_embedded)
    result = asyncio.run(eval_prompt.eval_node(parent, "1"))
    assert result.queued is True
    assert result.prompt_id == "prompt-1"
    assert result.history_outputs == ["out.png"]
    assert seen == [(record, candidate, {"config": None})]


def test_eval_failure_paths_make_zero_runtime_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _bundle()
    calls = []

    async def fail_run(*args, **kwargs):
        calls.append(args)
        raise AssertionError("runtime must not be called")

    monkeypatch.setattr(eval_prompt, "run_embedded", fail_run)
    with pytest.raises(RuntimeNodeError, match="RunPod transport is offline-only"):
        asyncio.run(eval_prompt.eval_node(parent, "1", runtime="runpod"))
    with pytest.raises(RuntimeNodeError):
        asyncio.run(eval_prompt.eval_node(parent, "root/1"))
    assert calls == []


def _latent_bundle(*, vae_loader: bool = False, second_emitter: bool = False, roster: object = "valid", checkpoint: bool = True):
    workflow = VibeWorkflow("latent-source", WorkflowSource("latent-source"))
    checkpoint_metadata = {}
    if roster == "valid":
        checkpoint_metadata = {"output_names": ["MODEL", "CLIP", "VAE"], "output_types": ["MODEL", "CLIP", "VAE"]}
    elif roster is not None:
        checkpoint_metadata = {"output_names": roster}
    if checkpoint:
        workflow.nodes["checkpoint"] = VibeNode(
            "checkpoint", "CheckpointLoaderSimple", uid="checkpoint-uid",
            inputs={"ckpt_name": "model.safetensors"}, metadata=checkpoint_metadata,
        )
    workflow.nodes["2"] = VibeNode(
        "2", "KSampler", uid="sampler-uid", inputs={"seed": 1, "steps": 2, "cfg": 1.0},
        native_input_names=["model", "vae"],
    )
    if checkpoint:
        workflow.edges.append(VibeEdge("checkpoint", "0", "2", "model"))
    if vae_loader:
        workflow.nodes["vae"] = VibeNode("vae", "VAELoader", uid="vae-uid", inputs={"vae_name": "vae.safetensors"})
        workflow.edges.append(VibeEdge("vae", "0", "2", "vae"))
    if second_emitter:
        workflow.nodes["vae2"] = VibeNode("vae2", "VAELoader", uid="vae2-uid", inputs={"vae_name": "vae2.safetensors"})
        workflow.edges.append(VibeEdge("vae2", "0", "2", "vae2"))
    return load_bundle(workflow)


def test_latent_checkpoint_selection_wires_real_slot_two() -> None:
    bundle = _latent_bundle()
    candidate = select_eval_workflow(bundle, "2")
    assert ("checkpoint", "2", "2_vaedecode", "vae") in {
        (edge.from_node, edge.from_output, edge.to_node, edge.to_input) for edge in candidate.edges
    }
    assert ("2", "0", "2_vaedecode", "samples") in {
        (edge.from_node, edge.from_output, edge.to_node, edge.to_input) for edge in candidate.edges
    }
    assert ("2_vaedecode", "0", "2_preview", "images") in {
        (edge.from_node, edge.from_output, edge.to_node, edge.to_input) for edge in candidate.edges
    }
    assert bundle.workflow.nodes["checkpoint"].uid == "checkpoint-uid"


def test_latent_checkpoint_real_compile_binds_vae_slot_two() -> None:
    class FixtureProvider:
        schemas = {
            "CheckpointLoaderSimple": NodeSchema(
                "CheckpointLoaderSimple", None,
                {"ckpt_name": InputSpec("STRING")},
                [OutputSpec("MODEL", "MODEL"), OutputSpec("CLIP", "CLIP"), OutputSpec("VAE", "VAE")],
            ),
            "KSampler": NodeSchema(
                "KSampler", None,
                {"model": InputSpec("MODEL"), "seed": InputSpec("INT"), "steps": InputSpec("INT"), "cfg": InputSpec("FLOAT")},
                [OutputSpec("LATENT", "LATENT")],
            ),
            "VAEDecode": NodeSchema(
                "VAEDecode", None,
                {"samples": InputSpec("LATENT"), "vae": InputSpec("VAE")},
                [OutputSpec("IMAGE", "IMAGE")],
            ),
            "PreviewImage": NodeSchema("PreviewImage", None, {"images": InputSpec("IMAGE")}, []),
        }

        def get_schema(self, class_type):
            return self.schemas.get(class_type)

    entry = ModelEntry(
        "runtime-eval-model", ModelSource("local"), 0,
        (ModelTarget("comfy_core", "checkpoints"),),
    )
    with (
        patch("vibecomfy.registry.models_loader.load_registry", return_value=(entry,)),
        patch("vibecomfy.registry.models_loader.resolve_model_entry", return_value=entry),
        patch("vibecomfy.fetch.is_present", return_value=True),
    ):
        candidate_bundle, record = approve_eval_subgraph(
            _latent_bundle(), "2", schema_provider=FixtureProvider()
        )
    assert record.to_dict()["api_projection"]["2_vaedecode"]["inputs"]["vae"] == ["checkpoint", 2]
    assert candidate_bundle.workflow.id == "latent-source"


def test_latent_vaeloader_uses_slot_zero_and_consumers_are_not_emitters() -> None:
    bundle = _latent_bundle(vae_loader=True, checkpoint=False)
    candidate = select_eval_workflow(bundle, "2")
    vae_edges = [edge for edge in candidate.edges if edge.to_node == "2_vaedecode" and edge.to_input == "vae"]
    assert [(edge.from_node, edge.from_output) for edge in vae_edges] == [("vae", "0")]

    consumer = VibeWorkflow("consumer", WorkflowSource("consumer"))
    consumer.nodes["consumer"] = VibeNode("consumer", "VAEDecode", uid="consumer-uid")
    consumer.nodes["2"] = VibeNode("2", "KSampler", uid="sampler-uid")
    consumer.edges.append(VibeEdge("consumer", "0", "2", "model"))
    assert plan_eval_node(load_bundle(consumer), "2").queueable is False


def test_latent_ambiguous_emitters_fail_closed_before_t14(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _latent_bundle(vae_loader=True, second_emitter=True)
    plan = plan_eval_node(bundle, "2")
    assert plan.queueable is False
    assert any(item["code"] == "vae_source_ambiguous" for item in plan.warnings)
    with pytest.raises(RuntimeNodeError, match="vae_source_ambiguous"):
        select_eval_workflow(bundle, "2")
    calls = []
    monkeypatch.setattr(eval_prompt, "run_embedded", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(RuntimeNodeError, match="not queueable"):
        asyncio.run(eval_prompt.eval_node(bundle, "2"))
    assert calls == []


@pytest.mark.parametrize("roster", [[], ["MODEL"], ["MODEL", "CLIP", "VAE", "VAE"], ["MODEL", None, "VAE"]])
def test_latent_malformed_roster_and_specialized_loader_are_unresolved(
    roster, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _latent_bundle(roster=roster)
    assert plan_eval_node(bundle, "2").queueable is False
    monkeypatch.setattr(eval_prompt, "approve_eval_subgraph", lambda *args, **kwargs: pytest.fail("approval called"))
    with pytest.raises(RuntimeNodeError, match="not queueable"):
        asyncio.run(eval_prompt.eval_node(bundle, "2"))

    specialized = VibeWorkflow("specialized", WorkflowSource("specialized"))
    specialized.nodes["special"] = VibeNode("special", "WanVideoVAELoader", uid="special-uid")
    specialized.nodes["2"] = VibeNode("2", "KSampler", uid="sampler-uid")
    specialized.edges.append(VibeEdge("special", "0", "2", "model"))
    assert plan_eval_node(load_bundle(specialized), "2").queueable is False


@pytest.mark.parametrize("collision", ["2_vaedecode", "2_preview"])
def test_latent_synthetic_id_and_uid_collisions_reject_without_parent_mutation(collision: str) -> None:
    workflow = _latent_bundle().workflow
    workflow.nodes["collision"] = VibeNode("collision", "Integer", uid=collision)
    before = workflow.semantic_digest()
    with pytest.raises(RuntimeNodeError, match="collides"):
        select_eval_workflow(load_bundle(workflow), "2")
    assert workflow.semantic_digest() == before
