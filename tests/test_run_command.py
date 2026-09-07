"""Tests for the family-aware public-input enforcement in ``vibecomfy run``.

When a user passes a universal override against a workflow whose nodes have not
been registered as eligible targets, the CLI must error loudly rather than
silently no-op or mutate the wrong field.
"""

from __future__ import annotations

import argparse
import types

import pytest

from vibecomfy.commands.run import _cmd_run
from vibecomfy.registry.models_loader import ModelEntry, ModelSource, ModelTarget
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _make_args(**overrides) -> argparse.Namespace:
    base = dict(
        path="some/workflow",
        ready=False,
        runtime="embedded",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=None,
        ensure_packs=False,
        ensure_models=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _no_inputs_workflow(workflow_id: str = "wan-wrapper") -> VibeWorkflow:
    """A workflow whose only nodes are NOT in the prompt/steps allowlist.

    This mirrors WanVideoWrapper or ACE Step audio graphs after
    ``finalize_metadata`` runs: the registration step refuses to map
    ``--prompt``/``--steps`` to any of the custom-node text/sampler fields,
    so the universal CLI overrides have no eligible target.
    """
    workflow = VibeWorkflow(workflow_id, WorkflowSource(workflow_id))
    workflow.nodes["1"] = VibeNode(
        "1",
        "WanVideoTextEncode",
        uid="wan-text-1",
        inputs={"text": "source-authored prompt"},
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "WanVideoSampler",
        uid="wan-sampler-2",
        inputs={"steps": 20, "seed": 7},
    )
    workflow.nodes["3"] = VibeNode("3", "SaveImage", uid="save-3", inputs={"filename_prefix": "out"})
    # Note: workflow.inputs is intentionally empty — from_api
    # would produce the same shape via _register_common_inputs.
    return workflow


class _ImageSchemaProvider:
    schemas = {
        "CheckpointLoaderSimple": NodeSchema(
            "CheckpointLoaderSimple", None,
            {"ckpt_name": InputSpec("STRING")},
            [OutputSpec("MODEL", "MODEL"), OutputSpec("CLIP", "CLIP"), OutputSpec("VAE", "VAE")],
        ),
        "CLIPTextEncode": NodeSchema(
            "CLIPTextEncode", None,
            {"text": InputSpec("STRING"), "clip": InputSpec("CLIP")},
            [OutputSpec("CONDITIONING", "CONDITIONING")],
        ),
        "EmptyLatentImage": NodeSchema(
            "EmptyLatentImage", None,
            {"width": InputSpec("INT"), "height": InputSpec("INT"), "batch_size": InputSpec("INT")},
            [OutputSpec("LATENT", "LATENT")],
        ),
        "KSampler": NodeSchema(
            "KSampler", None,
            {
                "model": InputSpec("MODEL"), "positive": InputSpec("CONDITIONING"),
                "negative": InputSpec("CONDITIONING"), "latent_image": InputSpec("LATENT"),
                "seed": InputSpec("INT"), "steps": InputSpec("INT"), "cfg": InputSpec("FLOAT"),
                "sampler_name": InputSpec("STRING"), "scheduler": InputSpec("STRING"),
                "denoise": InputSpec("FLOAT"),
            },
            [OutputSpec("LATENT", "LATENT")],
        ),
        "VAEDecode": NodeSchema(
            "VAEDecode", None,
            {"samples": InputSpec("LATENT"), "vae": InputSpec("VAE")},
            [OutputSpec("IMAGE", "IMAGE")],
        ),
        "SaveImage": NodeSchema(
            "SaveImage", None,
            {"images": InputSpec("IMAGE"), "filename_prefix": InputSpec("STRING")},
            [],
        ),
    }

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schemas.get(class_type)


def _image_workflow(provider: _ImageSchemaProvider) -> VibeWorkflow:
    workflow = VibeWorkflow("img", WorkflowSource("img"))

    def add(node_id: str, class_type: str, inputs: dict[str, object]) -> None:
        schema = provider.get_schema(class_type)
        assert schema is not None
        workflow.nodes[node_id] = VibeNode(
            node_id, class_type, uid=f"img-{node_id}", inputs=inputs,
            native_input_names=list(schema.inputs),
            native_input_types=[spec.type for spec in schema.inputs.values()],
            native_output_names=[spec.name for spec in schema.outputs],
            native_output_types=[spec.type for spec in schema.outputs],
        )

    add("checkpoint", "CheckpointLoaderSimple", {"ckpt_name": "fixture.safetensors"})
    add("positive", "CLIPTextEncode", {"text": "source prompt"})
    add("negative", "CLIPTextEncode", {"text": ""})
    add("latent", "EmptyLatentImage", {"width": 512, "height": 512, "batch_size": 1})
    add("sampler", "KSampler", {
        "seed": 1, "steps": 4, "cfg": 7.0,
        "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
    })
    add("decode", "VAEDecode", {})
    add("save", "SaveImage", {"filename_prefix": "out"})
    for source, output, target, field in (
        ("checkpoint", "1", "positive", "clip"),
        ("checkpoint", "1", "negative", "clip"),
        ("checkpoint", "0", "sampler", "model"),
        ("positive", "0", "sampler", "positive"),
        ("negative", "0", "sampler", "negative"),
        ("latent", "0", "sampler", "latent_image"),
        ("sampler", "0", "decode", "samples"),
        ("checkpoint", "2", "decode", "vae"),
        ("decode", "0", "save", "images"),
    ):
        workflow.edges.append(VibeEdge(source, output, target, field))
    workflow.register_input("prompt", "positive", "text")
    workflow.register_input("seed", "sampler", "seed")
    workflow.register_input("steps", "sampler", "steps")
    return workflow


def _stub_run(monkeypatch: pytest.MonkeyPatch, workflow: VibeWorkflow) -> list[tuple[object, object, dict]]:
    runs: list[tuple[object, object, dict]] = []

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    from vibecomfy.cli_loader import load_bundle
    provider = _ImageSchemaProvider()
    monkeypatch.setattr(
        "vibecomfy.commands.run.get_schema_provider",
        lambda prefer, *, server_url=None: provider,
    )
    entry = ModelEntry(
        "fixture.safetensors", ModelSource("local"), 0,
        (ModelTarget("comfy_core", "checkpoints"),),
    )
    monkeypatch.setattr("vibecomfy.registry.models_loader.load_registry", lambda: (entry,))
    monkeypatch.setattr("vibecomfy.registry.models_loader.resolve_model_entry", lambda *args, **kwargs: entry)
    monkeypatch.setattr("vibecomfy.fetch.is_present", lambda *args, **kwargs: True)
    real_bundle = load_bundle(workflow)
    compile_kwargs: dict[str, object] = {}

    def compile_bundle(**kwargs):
        compile_kwargs.update(kwargs)
        return real_bundle.compile(**kwargs)
    bundle = types.SimpleNamespace(
        workflow=workflow,
        require_canonical_authority=lambda *args, **kwargs: None,
        compile=compile_bundle,
        compile_kwargs=compile_kwargs,
    )
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: bundle)

    def fake_run_embedded_sync(record, bundle, **kwargs):
        runs.append((record, bundle, kwargs))
        return types.SimpleNamespace(
            run_id="r",
            prompt_id="p",
            outputs=[],
            metadata_path="m.json",
            log_path="l.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_embedded_sync", fake_run_embedded_sync)
    return runs


def test_cmd_run_errors_when_prompt_supplied_without_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _no_inputs_workflow("wan-wrapper")
    runs = _stub_run(monkeypatch, workflow)

    rc = _cmd_run(_make_args(prompt="anything"))

    assert rc == 2
    assert runs == []
    err = capsys.readouterr().err
    assert "wan-wrapper" in err
    assert "--prompt" in err
    assert "PROMPT_NODE_CLASSES" in err


def test_cmd_run_errors_when_steps_supplied_without_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _no_inputs_workflow("ace-audio")
    runs = _stub_run(monkeypatch, workflow)

    rc = _cmd_run(_make_args(steps=4))

    assert rc == 2
    assert runs == []
    err = capsys.readouterr().err
    assert "ace-audio" in err
    assert "--steps" in err
    assert "STEPS_NODE_CLASSES" in err


def test_cmd_run_errors_when_seed_supplied_without_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _no_inputs_workflow("wan-wrapper")
    runs = _stub_run(monkeypatch, workflow)

    rc = _cmd_run(_make_args(seed=123))

    assert rc == 2
    assert runs == []
    err = capsys.readouterr().err
    assert "wan-wrapper" in err
    assert "--seed" in err
    assert "seed" in err


def test_cmd_run_applies_prompt_and_steps_for_image_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _ImageSchemaProvider()
    workflow = _image_workflow(provider)
    before_nodes = {node_id: dict(node.inputs) for node_id, node in workflow.nodes.items()}
    runs = _stub_run(monkeypatch, workflow)

    rc = _cmd_run(_make_args(prompt="a red cube", steps=8, seed=42))

    assert rc == 0
    assert len(runs) == 1 and runs[0][1].workflow is workflow
    assert runs[0][2]["backend"] == "api"
    assert runs[0][2]["ensure_models"] is False
    assert runs[0][2]["ensure_packs"] is False
    assert "config" in runs[0][2]
    assert runs[0][1].compile_kwargs["run_inputs"] == {"prompt": "a red cube", "seed": 42, "steps": 8}
    record = runs[0][0]
    assert record.input_binding == {"prompt": "a red cube", "seed": 42, "steps": 8}
    assert record.api_projection["positive"]["inputs"]["text"] == "a red cube"
    assert record.api_projection["sampler"]["inputs"]["seed"] == 42
    assert record.api_projection["sampler"]["inputs"]["steps"] == 8
    assert record.api_projection["save"]["inputs"]["images"] == ("decode", 0)
    assert {node_id: dict(node.inputs) for node_id, node in workflow.nodes.items()} == before_nodes


def test_cmd_run_can_opt_out_of_default_model_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _image_workflow(_ImageSchemaProvider())
    runs = _stub_run(monkeypatch, workflow)

    rc = _cmd_run(_make_args(ensure_models=False))

    assert rc == 0
    assert len(runs) == 1 and runs[0][1].workflow is workflow
    assert runs[0][2]["backend"] == "api"
    assert runs[0][2]["ensure_models"] is False
    assert runs[0][2]["ensure_packs"] is False
    assert "config" in runs[0][2]
