"""Tests for the family-aware ``--prompt``/``--steps`` registration policy.

These tests exercise the class-type allowlists in :mod:`vibecomfy.metadata`
that gate which nodes the universal CLI overrides may attach to. The intent
is to keep ``--prompt``/``--steps`` from silently mutating audio tag fields,
WanVideoWrapper sampler conditioning, or other custom-node text inputs that
look textual but mean something completely different.
"""

from __future__ import annotations

import pytest

from vibecomfy.ingest.normalize import from_api


def _ksampler_chain(class_type: str) -> dict[str, dict]:
    return {
        "1": {"class_type": class_type, "inputs": {"text": "old prompt"}},
        "2": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 4, "positive": ["1", 0]}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    }


def test_prompt_registered_for_clip_text_encode() -> None:
    workflow = from_api(_ksampler_chain("CLIPTextEncode"), workflow_id="img")

    assert "prompt" in workflow.inputs
    assert workflow.inputs["prompt"].node_id == "1"
    assert workflow.inputs["prompt"].field == "text"


def test_prompt_registered_for_qwen_image_edit_text_encoder() -> None:
    workflow = from_api(_ksampler_chain("TextEncodeQwenImageEdit"), workflow_id="qwen")

    assert "prompt" in workflow.inputs
    assert workflow.inputs["prompt"].node_id == "1"


def test_prompt_not_registered_for_wanvideo_text_encoder() -> None:
    workflow = from_api(_ksampler_chain("WanVideoTextEncode"), workflow_id="wan")

    # The WanVideoWrapper text encoder accepts sampler-conditioning text and
    # must not be silently rewritten by the universal --prompt flag.
    assert workflow.inputs.get("prompt") is None


def test_prompt_not_registered_for_ace_step_audio_text_encoder() -> None:
    workflow = from_api(_ksampler_chain("TextEncodeAceStepAudio1.5"), workflow_id="ace")

    # ACE Step audio expects tag strings, not free-form image prompts.
    assert workflow.inputs.get("prompt") is None


def test_prompt_not_registered_for_unknown_custom_class() -> None:
    workflow = from_api(_ksampler_chain("MyCompletelyCustomTextNode"), workflow_id="custom")

    assert workflow.inputs.get("prompt") is None


def test_steps_registered_for_ksampler() -> None:
    raw = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "a"}},
        "2": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 4, "positive": ["1", 0]}},
    }

    workflow = from_api(raw, workflow_id="ks")

    assert "steps" in workflow.inputs
    assert workflow.inputs["steps"].node_id == "2"


def test_steps_registered_for_sampler_custom_advanced() -> None:
    raw = {
        "1": {"class_type": "SamplerCustomAdvanced", "inputs": {"steps": 8}},
    }

    workflow = from_api(raw, workflow_id="sca")

    assert "steps" in workflow.inputs
    assert workflow.inputs["steps"].node_id == "1"


def test_steps_not_registered_for_wanvideo_sampler() -> None:
    raw = {
        "1": {"class_type": "WanVideoSampler", "inputs": {"steps": 20, "seed": 7}},
    }

    workflow = from_api(raw, workflow_id="wansampler")

    assert workflow.inputs.get("steps") is None
    # seed remains universal and continues to register.
    assert workflow.inputs.get("seed") is not None


def test_steps_not_registered_for_unknown_custom_sampler() -> None:
    raw = {
        "1": {"class_type": "TotallyCustomSamplerNode", "inputs": {"steps": 12}},
    }

    workflow = from_api(raw, workflow_id="custom-sampler")

    assert workflow.inputs.get("steps") is None


def test_seed_registration_unchanged_across_families() -> None:
    raw = {
        "1": {"class_type": "WanVideoSampler", "inputs": {"seed": 42, "steps": 20}},
        "2": {"class_type": "TextEncodeAceStepAudio1.5", "inputs": {"text": "tag"}},
    }

    workflow = from_api(raw, workflow_id="seed-everywhere")

    assert workflow.inputs.get("seed") is not None
    assert workflow.inputs["seed"].node_id == "1"


def test_legacy_env_var_restores_old_field_name_only_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_LEGACY_OVERRIDES", "1")
    workflow = from_api(_ksampler_chain("WanVideoTextEncode"), workflow_id="legacy")

    # Under legacy mode the field-name match is enough to register, even for
    # custom-node text encoders.
    assert workflow.inputs.get("prompt") is not None
    assert workflow.inputs["prompt"].node_id == "1"


def test_legacy_env_var_restores_steps_registration_for_custom_samplers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_LEGACY_OVERRIDES", "1")
    raw = {"1": {"class_type": "TotallyCustomSamplerNode", "inputs": {"steps": 12}}}

    workflow = from_api(raw, workflow_id="legacy-steps")

    assert workflow.inputs.get("steps") is not None
