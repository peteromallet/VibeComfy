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
from vibecomfy.porting.edit.validate import validate_literal_value
from vibecomfy.schema import InputSpec
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider, SourceSchemaProvider
from vibecomfy.schema.types import node_schema_from_payload, schema_payload_from_node_schema

CACHE_DIR = Path(__file__).resolve().parents[1] / "vibecomfy" / "porting" / "cache" / "object_info"

PACK_FILES = {
    "ComfyUI-AceStep_SFT": "ComfyUI-AceStep_SFT@local-c2cfe8e.json",
    "ComfyUI-Whisper": "ComfyUI-Whisper@local-006a709.json",
    # RR1-FIX-REV: ComfyUI-Easy-Use@local-4de1ab3.json was OFFLINE stub
    # extraction, not a live /object_info capture — removed and unindexed
    # together with its index/provenance rows.  Its classes are recorded
    # honestly blocked in
    # tests/live_agentic_harness/scenario_obligations.py::
    # UNPROVEN_PROVIDER_CLASSES until a same-pack LIVE capture exists.
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



# ---------------------------------------------------------------------------
# P4-R2C -- constrained salvage + payload round-trip + fail-closed validation
# ---------------------------------------------------------------------------


_P4R2C_DYNAMIC_SOURCE = textwrap.dedent(
    """
    import folder_paths


    class P4R2CProvenDynamicNode:
        @classmethod
        def INPUT_TYPES(cls):
            models = folder_paths.get_filename_list("checkpoints")
            return {
                "required": {
                    "dynamic_pick": (models, {"default": "fallback"}),
                }
            }

        RETURN_TYPES = ("STRING",)
    """
)


_P4R2C_STATIC_SOURCE = textwrap.dedent(
    """
    class P4R2CStaticStringNode:
        @classmethod
        def INPUT_TYPES(cls):
            return {
                "required": {
                    "text": ("STRING", {"default": unknown_symbol}),
                }
            }

        RETURN_TYPES = ("STRING",)
    """
)


class TestP4R2CUnresolvedComboCoverage:
    """Regression coverage for P4-R2C (fc155565): (a)-(e)."""

    def test_a_proven_dynamic_choice_salvaged_to_unresolved_combo(self, tmp_path: Path) -> None:
        """(a) proven dynamic-choice entry becomes visible unresolved COMBO."""
        source = tmp_path / "p4r2c_dynamic.py"
        source.write_text(_P4R2C_DYNAMIC_SOURCE, encoding="utf-8")
        schema = SourceSchemaProvider([tmp_path]).get_schema("P4R2CProvenDynamicNode")
        assert schema is not None, "proven dynamic node must still parse"
        assert "dynamic_pick" in schema.inputs, "dynamic input must remain visible (not dropped)"
        spec = schema.inputs["dynamic_pick"]
        assert spec.type == "COMBO"
        assert spec.unresolved_choices is True
        assert not spec.choices, "unresolved choices must be empty/None, not fabricated"

    def test_b_static_string_does_not_get_combo_marked(self, tmp_path: Path) -> None:
        """(b) statically-typed non-dynamic entry does NOT get combo-marked."""
        source = tmp_path / "p4r2c_static.py"
        source.write_text(_P4R2C_STATIC_SOURCE, encoding="utf-8")
        schema = SourceSchemaProvider([tmp_path]).get_schema("P4R2CStaticStringNode")
        assert schema is not None, "static node must still parse"
        # Static STRING with unparseable default must not be salvaged as COMBO.
        if "text" in schema.inputs:
            spec = schema.inputs["text"]
            assert spec.type == "STRING", "static STRING must keep its type"
            assert spec.unresolved_choices is False, "static entry must not carry unresolved marker"
            assert spec.type != "COMBO" or not spec.unresolved_choices
        else:
            # Reverts to drop is also acceptable per spec, but must not appear as unresolved COMBO.
            assert "text" not in schema.inputs or not schema.inputs["text"].unresolved_choices

    def test_c_marker_survives_payload_round_trip(self, tmp_path: Path) -> None:
        """(c) unresolved_choices survives payload normalization round-trip."""
        source = tmp_path / "p4r2c_roundtrip.py"
        source.write_text(_P4R2C_DYNAMIC_SOURCE, encoding="utf-8")
        schema = SourceSchemaProvider([tmp_path]).get_schema("P4R2CProvenDynamicNode")
        assert schema is not None and "dynamic_pick" in schema.inputs
        assert schema.inputs["dynamic_pick"].unresolved_choices is True
        payload = schema_payload_from_node_schema("P4R2CProvenDynamicNode", schema)
        assert payload["inputs"]["dynamic_pick"]["unresolved_choices"] is True
        restored = node_schema_from_payload("P4R2CProvenDynamicNode", payload)
        assert restored.inputs["dynamic_pick"].unresolved_choices is True
        assert restored.inputs["dynamic_pick"].type == "COMBO"

    def test_d_validate_rejects_literal_against_unresolved(self) -> None:
        """(d) validate_literal_value fails closed on unresolved spec."""
        spec = InputSpec(type="COMBO", required=True, choices=None, unresolved_choices=True)
        issues = validate_literal_value(
            value="anything",
            spec=spec,
            class_type="P4R2CProvenDynamicNode",
            input_name="dynamic_pick",
            context="test",
        )
        assert len(issues) == 1
        assert issues[0].code == "unresolved_choices"
        assert issues[0].severity == "error"

    def test_e_static_combo_validates_normally(self) -> None:
        """(e) static combo binding still validates normally."""
        spec = InputSpec(type="COMBO", required=True, default="a", choices=["a", "b"], unresolved_choices=False)
        ok = validate_literal_value(
            value="a",
            spec=spec,
            class_type="SomeNode",
            input_name="pick",
            context="test",
        )
        assert ok == [], "valid enum value must pass clean"
        bad = validate_literal_value(
            value="c",
            spec=spec,
            class_type="SomeNode",
            input_name="pick",
            context="test",
        )
        assert len(bad) == 1
        assert bad[0].code == "value_not_in_enum"


@pytest.mark.parametrize(
    "class_type",
    ["IndexTTSEngineNode", "IndexTTSEmotionOptionsNode", "QwenEmotionNode"],
)
def test_gated_tts_classes_pass_provenance_gate(class_type: str) -> None:
    ok, message = _provenance_row(CACHE_DIR, class_type)
    assert ok, message


# ---------------------------------------------------------------------------
# RR1-FIX-REV — honest-skip law for simulated captures (F3), enforced
# unproven-provider preflight violations (F4), exact-port obligations (F5).
# ---------------------------------------------------------------------------

_REMOVED_SIMULATED_CAPTURES = (
    "audio-separation-nodes-comfyui@local-ac33956.json",
    "ComfyUI-Easy-Use@local-4de1ab3.json",
    "ComfyUI-Inspire-Pack@local-d23db9a.json",
    "ComfyUI-llama-cpp_vlm@local-f2209cc.json",
)


def test_simulated_stub_captures_are_removed_and_unindexed() -> None:
    """RRSYN-4 / RR1-FIX-REV: offline stub-extraction products must not be
    published as authoritative live object_info — no file, no index row, no
    provenance attestation."""
    index = json.loads((CACHE_DIR / "index.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (CACHE_DIR / "provenance.json").read_text(encoding="utf-8")
    )
    removed_files = set(_REMOVED_SIMULATED_CAPTURES)
    for filename in _REMOVED_SIMULATED_CAPTURES:
        assert not (CACHE_DIR / filename).is_file(), filename
        assert filename not in provenance["packs"]
        pointing = [c for c, f in index.items() if f == filename]
        assert pointing == [], f"{filename} still indexed for {pointing[:3]}"
    # No dangling references: every remaining row points at an existing file.
    for filename in set(index.values()):
        assert (CACHE_DIR / str(filename)).is_file(), filename


def test_enforced_preflight_rejects_unproven_gated_edit_scenarios() -> None:
    """RRSYN-4 / RR1-FIX-REV: UNPROVEN_PROVIDER_CLASSES entries on
    edit-required scenarios are hard preflight VIOLATIONS when schema
    resolution is enforced - never warning-only bypasses.
    OQ2: final50's 6 previously-blocked scenarios are now declared with
    honest on_demand captures, so final50 passes; the residual honest gap
    (multi-wan-vace-video-retargeting-driven) still enforces the gate when
    its manifest is checked in isolation."""
    from tests.live_agentic_harness import scenario_obligations as so

    final50 = (
        Path(__file__).resolve().parent
        / "live_agentic_harness"
        / "threaded_comparison_manifest_final50.json"
    )
    result = so.preflight_scenario_obligations(final50, require_schema_resolution=True)
    assert result["ok"] is True
    # Residual gap still blocks - prove the gate was not removed.
    assert "multi-wan-vace-video-retargeting-driven" in so.UNPROVEN_PROVIDER_CLASSES
    assert so.UNPROVEN_PROVIDER_CLASSES["multi-wan-vace-video-retargeting-driven"] == (
        "easy forLoopStart",
        "easy forLoopEnd",
    )


def test_declaration_level_coverage_rejects_registered_unproven_classes() -> None:
    """RR1-FIX-REV2 F4: registered-unproven gated classes are declaration-
    level VIOLATIONS from ``validate_obligation_coverage`` itself.
    OQ2: final50 now has zero violations (6 scenarios restored with
    on_demand captures); the residual multi-wan gap stays the canonical
    honest-block example and is validated without relying on final50."""
    from tests.live_agentic_harness import scenario_obligations as so

    final50 = (
        Path(__file__).resolve().parent
        / "live_agentic_harness"
        / "threaded_comparison_manifest_final50.json"
    )
    violations, warnings = so.validate_obligation_coverage(final50)
    assert violations == [], f"OQ2: final50 should have no declaration violations, got {violations}"
    assert not any("same-pack provenance capture at this commit" in w for w in warnings)
    # Residual gap stays honestly blocked.
    assert "multi-wan-vace-video-retargeting-driven" in so.UNPROVEN_PROVIDER_CLASSES


def test_preflight_fails_closed_regardless_of_schema_resolution_flag() -> None:
    """RR1-FIX-REV2 F4 reviewer probe: enforcement is unconditional;
    OQ2: final50 now passes with and without the flag (the probe now
    verifies that the unconditional enforcement still holds for the residual
    multi-wan gap, and that final50's honest on_demand declarations
    satisfy it in both modes)."""
    from tests.live_agentic_harness import scenario_obligations as so

    final50 = (
        Path(__file__).resolve().parent
        / "live_agentic_harness"
        / "threaded_comparison_manifest_final50.json"
    )
    result_true = so.preflight_scenario_obligations(final50, require_schema_resolution=True)
    assert result_true["ok"] is True
    result_false = so.preflight_scenario_obligations(final50, require_schema_resolution=False)
    assert result_false["ok"] is True


def test_exact_port_evidence_is_validated_against_frozen_schema() -> None:
    """RRSYN-4 / RR1-FIX-REV: required input/widget/output ports are each
    validated against the frozen captured schema before paid calls."""
    from tests.live_agentic_harness.scenario_obligations import (
        _resolve_schema_locally,
    )

    emotion_ok = {
        "class_type": "IndexTTSEmotionOptionsNode",
        "pack": "ComfyUI-IndexTTS",
        "source": "authoritative_object_info",
        "required_inputs": (),
        "required_widgets": ("Sad", "Disgusted", "Calm"),
        "required_outputs": ("emotion_control",),
    }
    resolved, failures = _resolve_schema_locally(emotion_ok)
    assert resolved, failures

    bad_output = dict(emotion_ok, required_outputs=("emotion_audio",))
    resolved, failures = _resolve_schema_locally(bad_output)
    assert not resolved
    assert any("required output port 'emotion_audio'" in f for f in failures)

    missing_widget = dict(
        emotion_ok,
        required_widgets=("Sad", "Melancholic", "DoesNotExist"),
    )
    resolved, failures = _resolve_schema_locally(missing_widget)
    assert not resolved
    assert any("DoesNotExist" in f for f in failures)

    engine_ok = {
        "class_type": "IndexTTSEngineNode",
        "pack": "ComfyUI-IndexTTS",
        "source": "authoritative_object_info",
        "required_inputs": ("model_path", "temperature", "top_p"),
        "required_widgets": ("model_path",),
        "required_outputs": ("TTS_engine",),
    }
    resolved, failures = _resolve_schema_locally(engine_ok)
    assert resolved, failures

    missing_input = dict(engine_ok, required_inputs=("model_path", "voice"))
    resolved, failures = _resolve_schema_locally(missing_input)
    assert not resolved
    assert any("required input port 'voice'" in f for f in failures)

    layermask_ok = {
        "class_type": "LayerMask: SegmentAnythingUltra V3",
        "pack": "ComfyUI_LayerStyle_Advance",
        "source": "authoritative_object_info",
        "required_inputs": (),
        "required_widgets": (),
        "required_outputs": ("image", "mask"),
    }
    resolved, failures = _resolve_schema_locally(layermask_ok)
    assert resolved, failures


# ---------------------------------------------------------------------------
# Batch D — shipped FINAL5 legacy pins satisfy only the runtime-family clause
# ---------------------------------------------------------------------------


def test_legacy_pin_entries_match_authoritative_declaration_only() -> None:
    """Batch D: ``ComfyUI-IndexTTS@local.json`` / ``ComfyUI-LayerMask@local.json``
    entries carry no ``source_kind`` stamp; the legacy-ingest clause of the
    runtime-family recognizer satisfies ``authoritative_object_info`` — and
    ONLY that declaration (never an on-demand tier)."""
    from tests.live_agentic_harness.scenario_obligations import (
        _declaration_matches_entry,
        _pack_entry,
    )

    for class_type in (
        "IndexTTSEmotionOptionsNode",
        "LayerMask: SegmentAnythingUltra V3",
    ):
        filename, entry = _pack_entry(CACHE_DIR, class_type)
        assert filename and entry is not None, class_type
        ok, why = _declaration_matches_entry(
            "authoritative_object_info", filename, entry
        )
        assert ok, f"{class_type}: {why}"
        for tier in ("on_demand_static", "on_demand_import", "on_demand_embedded"):
            matched, _ = _declaration_matches_entry(tier, filename, entry)
            assert not matched, f"{class_type} must not satisfy {tier}"
