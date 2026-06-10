from __future__ import annotations

from vibecomfy.registry.ready_template import finalize_model_assets
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def test_finalise_model_assets_filters_raw_assets_but_keeps_extras() -> None:
    workflow = VibeWorkflow("filter-test", WorkflowSource("filter-test"))
    workflow.add_node("UNETLoader", widget_0="renamed.safetensors")
    workflow.metadata["model_assets"] = [
        {
            "name": "original.safetensors",
            "url": "https://example.test/original.safetensors",
            "subdir": "diffusion_models",
        },
        {
            "name": "renamed.safetensors",
            "url": "https://example.test/renamed.safetensors",
            "subdir": "diffusion_models",
        },
    ]
    workflow.metadata["model_assets_extra"] = [
        {
            "name": "extra.safetensors",
            "url": "https://example.test/extra.safetensors",
            "subdir": "vae",
        }
    ]

    finalize_model_assets(workflow)

    assert workflow.metadata["model_assets"] == [
        {
            "name": "renamed.safetensors",
            "url": "https://example.test/renamed.safetensors",
            "subdir": "diffusion_models",
        },
        {
            "name": "extra.safetensors",
            "url": "https://example.test/extra.safetensors",
            "subdir": "vae",
        },
    ]
