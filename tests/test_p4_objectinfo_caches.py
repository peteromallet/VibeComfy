"""P4 object_info cache provisioning tests.

Covers card P4-OBJECTINFO-CACHES:

* R1 -- the four previously missing packs (AceStep SFT, ComfyUI-Whisper,
  ComfyUI-Easy-Use, ComfyUI-Hunyuan3DTools) are present in
  ``vibecomfy/porting/cache/object_info`` and load through the shipped cache
  consumer.
* R2 -- ``ComfyUI-IndexTTS@local.json`` exposes the real node surface instead
  of the former 2-input stub.
* R3 -- dynamic-choice combo inputs survive static/on-demand parsing as
  unresolved CHOICE specs instead of being dropped
  (regression guard for QwenEmotionNode.qwen_model).
* R4 -- every provisioned/regenerated cache passes the structural expectations
  of the offline loader (``consume`` / ``ObjectInfoIndexSchemaProvider``) and is
  attested in ``provenance.json``.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

import vibecomfy.porting.object_info.consume as consume
from tests.live_agentic_harness.scenario_obligations import _provenance_row
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider, SourceSchemaProvider

CACHE_DIR = Path(__file__).resolve().parents[1] / "vibecomfy" / "porting" / "cache" / "object_info"

PACK_FILES = {
    "ComfyUI-AceStep_SFT": "ComfyUI-AceStep_SFT@local-c2cfe8e.json",
    "ComfyUI-Whisper": "ComfyUI-Whisper@local-006a709.json",
    "ComfyUI-Easy-Use": "ComfyUI-Easy-Use@local-4de1ab3.json",
    "ComfyUI-Hunyuan3DTools": "ComfyUI-Hunyuan3DTools@local-621fb54.json",
    # Regenerated in place (R2); pinned source recorded in provenance.json.
    "ComfyUI-IndexTTS": "ComfyUI-IndexTTS@local.json",
}

EXPECTED_CLASSES = {
    "ComfyUI-AceStep_SFT": [
        "AceStepSFTGenerate",
        "AceStepSFTLoraLoader",
        "AceStepSFTModelLoader",
    ],
    "ComfyUI-Whisper": [
        "Apply Whisper",
        "Add Subtitles To Frames",
        "Save SRT",
    ],
    "ComfyUI-Easy-Use": [
        "easy pipeIn",
        "easy preSamplingCustom",
        "easy kSamplerInpainting",
        "easy controlnetLoader++",
    ],
    "ComfyUI-Hunyuan3DTools": [
        "Hy3DTools_RenderSpecificView",
        "Hy3DTools_BackProjectInpaint",
    ],
    "ComfyUI-IndexTTS": [
        "IndexTTSEngineNode",
        "IndexTTSEmotionOptionsNode",
        "QwenEmotionNode",
        "UnifiedTTSTextNode",
        "CharacterVoicesNode",
    ],
}


@pytest.fixture(autouse=True)
def _fresh_consume_cache():
    consume.reset_cache()
    yield
    consume.reset_cache()


# ---------------------------------------------------------------------------
# R1/R2 -- packs resolve through the offline consumer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("pack", "classes"), sorted(EXPECTED_CLASSES.items()))
def test_pack_classes_load_through_consumer(pack: str, classes: list[str]) -> None:
    filename = PACK_FILES[pack]
    assert (CACHE_DIR / filename).is_file(), f"missing cache file for {pack}"
    for class_type in classes:
        entry = consume.get_class(class_type)
        assert entry is not None, f"{class_type} ({pack}) missing from object_info cache"
        assert entry["inputs"], f"{class_type} resolved but carries no inputs"


def test_apply_whisper_exposes_model_combo_with_large_variants() -> None:
    """Leg 15's edit target: Apply Whisper.model must be authorable by name."""
    schema = ObjectInfoIndexSchemaProvider(CACHE_DIR).get_schema("Apply Whisper")
    assert schema is not None
    model_spec = schema.inputs["model"]
    assert model_spec.choices is not None and "large-v3" in model_spec.choices
    assert "turbo" in model_spec.choices


def test_ace_step_sft_generate_surface_is_authorable() -> None:
    """Leg 11: the SFT generator must expose named fields, not widget_N slots."""
    entry = consume.get_class("AceStepSFTGenerate")
    assert entry is not None
    assert len(entry["input_order_all"]) >= 30
    assert {"seed", "steps", "cfg", "duration"} <= set(entry["input_order_all"])
    lora = consume.get_class("AceStepSFTLoraLoader")
    assert lora is not None and lora["input_order_all"]


def test_hy3dtools_leg1_classes_are_indexed() -> None:
    idx = json.loads((CACHE_DIR / "index.json").read_text(encoding="utf-8"))
    for class_type in EXPECTED_CLASSES["ComfyUI-Hunyuan3DTools"]:
        assert idx.get(class_type) == PACK_FILES["ComfyUI-Hunyuan3DTools"]


# ---------------------------------------------------------------------------
# R2 -- regenerated IndexTTS surface replaces the 2-input stub
# ---------------------------------------------------------------------------


def test_indextts_emotion_options_has_full_slider_surface() -> None:
    entry = consume.get_class("IndexTTSEmotionOptionsNode")
    assert entry is not None
    inputs = list(entry["input_order_all"])
    assert len(inputs) > 2, "IndexTTSEmotionOptionsNode must expose its real slider surface"
    for slider in ("Happy", "Angry", "Sad", "Disgusted", "Calm"):
        assert slider in inputs


def test_qwen_emotion_node_keeps_dynamic_model_combo_in_cache() -> None:
    entry = consume.get_class("QwenEmotionNode")
    assert entry is not None
    order = entry["input_order_all"]
    assert "qwen_model" in order, "dynamic combo input must survive extraction"
    assert "emotion_text" in order
    spec = entry["inputs"]["required"]["qwen_model"]
    assert isinstance(spec, list) and spec
    # Static capture cannot enumerate runtime model discovery: choices stay
    # empty, but the render-visible default proves the widget.
    attrs = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    assert attrs.get("default") == "qwen0.6bemo4-merge"


# ---------------------------------------------------------------------------
# R3 -- dynamic combos survive the static/on_demand parsing path
# ---------------------------------------------------------------------------


_DYNAMIC_SOURCE = textwrap.dedent(
    """
    import folder_paths


    class DynamicComboNode:
        @classmethod
        def INPUT_TYPES(cls):
            models = cls._discover_models()
            return {
                "required": {
                    "dynamic_pick": (
                        models,
                        {"default": models[0] if models else "fallback-default"},
                    ),
                    "static_text": ("STRING", {"multiline": True, "default": ""}),
                }
            }

        RETURN_TYPES = ("STRING",)

        @classmethod
        def _discover_models(cls):
            return folder_paths.get_filename_list("models")
    """
)


def test_source_parser_keeps_dynamic_choice_input_as_unresolved_combo(tmp_path: Path) -> None:
    source = tmp_path / "dynamic_combo_node.py"
    source.write_text(_DYNAMIC_SOURCE, encoding="utf-8")

    provider = SourceSchemaProvider([tmp_path])
    schema = provider.get_schema("DynamicComboNode")

    assert schema is not None, "class with one dynamic input must still parse"
    assert set(schema.inputs) == {"dynamic_pick", "static_text"}, (
        "a dynamically computed choice list must never drop sibling inputs "
        "(QwenEmotionNode.qwen_model regression)"
    )
    pick = schema.inputs["dynamic_pick"]
    assert pick.type == "COMBO"
    assert not pick.choices, "statically unresolvable choices must be empty, not fabricated"
    assert schema.inputs["static_text"].type == "STRING"


def test_on_demand_static_provider_reports_dynamic_combo_class(tmp_path: Path) -> None:
    """End-to-end rung-1 shape: SourceSchemaProvider output feeds on_demand_static."""
    source = tmp_path / "dynamic_combo_node.py"
    source.write_text(_DYNAMIC_SOURCE, encoding="utf-8")

    schema = SourceSchemaProvider([tmp_path]).get_schema("DynamicComboNode")
    assert schema is not None and schema.inputs, "degenerate empty schema would fall through the ladder"
    assert "dynamic_pick" in schema.inputs


# ---------------------------------------------------------------------------
# R4 -- structural validation against loader expectations
# ---------------------------------------------------------------------------


def _iter_entries(filename: str):
    data = json.loads((CACHE_DIR / filename).read_text(encoding="utf-8"))
    for class_type, entry in data.items():
        yield class_type, entry


def _validate_entry_shape(class_type: str, entry: dict) -> None:
    assert isinstance(entry, dict), f"{class_type}: entry must be an object"
    inputs = entry.get("inputs")
    assert isinstance(inputs, dict) and inputs, f"{class_type}: inputs required/optional map missing"
    for section, group in inputs.items():
        assert section in {"required", "optional"}, f"{class_type}: unexpected section {section}"
        for name, spec in group.items():
            assert isinstance(spec, list) and spec, f"{class_type}.{name}: spec must be non-empty list"
            head = spec[0]
            assert isinstance(head, (str, list)), f"{class_type}.{name}: type must be str or choice list"
            if isinstance(head, list):
                assert all(isinstance(choice, str) for choice in head), (
                    f"{class_type}.{name}: choice list must contain strings"
                )
    widget_order = entry.get("object_info_widget_order")
    order_all = entry.get("input_order_all")
    assert isinstance(widget_order, list), f"{class_type}: object_info_widget_order missing"
    assert isinstance(order_all, list), f"{class_type}: input_order_all missing"
    assert len(widget_order) == len(order_all), (
        f"{class_type}: widget order {len(widget_order)} misaligned with input order {len(order_all)}"
    )
    outputs = entry.get("outputs")
    assert isinstance(outputs, list), f"{class_type}: outputs list missing"
    for out in outputs:
        assert {"type", "name", "is_list"} <= set(out), f"{class_type}: malformed output {out}"


@pytest.mark.parametrize("filename", sorted(PACK_FILES.values()))
def test_provisioned_caches_pass_loader_structure(filename: str) -> None:
    seen = 0
    for class_type, entry in _iter_entries(filename):
        _validate_entry_shape(class_type, entry)
        seen += 1
    assert seen > 0, f"{filename} is empty"


def test_index_rows_resolve_and_files_exist() -> None:
    idx = json.loads((CACHE_DIR / "index.json").read_text(encoding="utf-8"))
    for classes in EXPECTED_CLASSES.values():
        for class_type in classes:
            filename = idx.get(class_type)
            assert filename, f"{class_type} absent from index.json"
            assert (CACHE_DIR / filename).is_file(), f"{class_type} -> missing {filename}"


def test_every_provisioned_file_carries_real_provenance() -> None:
    prov = json.loads((CACHE_DIR / "provenance.json").read_text(encoding="utf-8"))
    for filename in PACK_FILES.values():
        row = prov["packs"].get(filename)
        assert row, f"{filename} has no provenance attestation"
        assert row.get("repo"), f"{filename} provenance lacks repo"
        locked = row.get("locked_commit")
        assert isinstance(locked, str) and len(locked) >= 7, f"{filename} provenance lacks locked commit"


@pytest.mark.parametrize(
    "class_type",
    ["IndexTTSEngineNode", "IndexTTSEmotionOptionsNode", "QwenEmotionNode"],
)
def test_gated_tts_classes_pass_provenance_gate(class_type: str) -> None:
    ok, message = _provenance_row(CACHE_DIR, class_type)
    assert ok, message
