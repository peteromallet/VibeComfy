from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import from_api
from vibecomfy.schema import InputSpec, LocalSchemaProvider, NodeSchema
from vibecomfy.schema.validate import (
    NormalizationApproval,
    SchemaNormalizationMismatch,
    SchemaNormalizationRequired,
    apply_schema_normalization,
    field_compatibility_for,
    propose_schema_normalization,
    validate_api_against_schema,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


class FakeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return self._schemas


def _workflow(*nodes: VibeNode) -> VibeWorkflow:
    workflow = VibeWorkflow("schema-validate-test", WorkflowSource("schema-validate-test"))
    workflow.nodes = {node.id: node for node in nodes}
    return workflow


def _schema(class_type: str, inputs: dict[str, InputSpec]) -> NodeSchema:
    return NodeSchema(class_type=class_type, pack=None, inputs=inputs, outputs=[])


def _codes(workflow: VibeWorkflow, provider: FakeSchemaProvider) -> list[str]:
    return [issue.code for issue in workflow.validate(schema_provider=provider).issues]


def _dynamic_schema(class_type: str) -> NodeSchema:
    if class_type == "LTXVImgToVideoInplaceKJ":
        inputs = {
            "num_images": InputSpec("COMFY_DYNAMICCOMBO_V3"),
            "latent": InputSpec("LATENT"),
            "vae": InputSpec("VAE"),
        }
    else:
        inputs = {
            "inputcount": InputSpec("INT", min=2, max=1000),
            "image_1": InputSpec("IMAGE"),
            "direction": InputSpec("STRING"),
            "match_image_size": InputSpec("BOOLEAN"),
        }
    return _schema(class_type, inputs)


def _dynamic_inputs(class_type: str, count: int) -> dict[str, object]:
    if class_type == "LTXVImgToVideoInplaceKJ":
        inputs: dict[str, object] = {"num_images": count}
        for index in range(1, count + 1):
            inputs.update(
                {
                    f"num_images.image_{index}": f"image-{index}",
                    f"num_images.index_{index}": index,
                    f"num_images.strength_{index}": 1.0,
                }
            )
        return inputs
    return {
        "inputcount": count,
        "direction": "right",
        "match_image_size": False,
        **{f"image_{index}": f"image-{index}" for index in range(1, count + 1)},
    }


def _dynamic_count_only_inputs(class_type: str, count: object) -> dict[str, object]:
    if class_type == "LTXVImgToVideoInplaceKJ":
        return {"num_images": count}
    return {
        "inputcount": count,
        "direction": "right",
        "match_image_size": False,
    }


def _dynamic_report(class_type: str, count: object, inputs: dict[str, object] | None = None):
    payload_inputs = inputs if inputs is not None else _dynamic_inputs(class_type, count)  # type: ignore[arg-type]
    provider = FakeSchemaProvider({class_type: _dynamic_schema(class_type)})
    return validate_api_against_schema(
        {"node": {"class_type": class_type, "inputs": payload_inputs}}, provider
    )


def test_missing_required_input_emits_error() -> None:
    provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", {"text": InputSpec("STRING", required=True)})})
    report = _workflow(VibeNode("1", "PromptNode")).validate(schema_provider=provider)

    assert not report.ok
    assert report.issues[0].code == "missing_required_input"
    assert report.issues[0].detail == {"node_id": "1", "class_type": "PromptNode", "input": "text"}


def test_unknown_input_emits_error() -> None:
    provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", {"text": InputSpec("STRING")})})
    report = _workflow(VibeNode("1", "PromptNode", inputs={"extra": "value"})).validate(schema_provider=provider)

    assert not report.ok
    assert report.issues[0].code == "unknown_input"
    assert report.issues[0].detail == {"node_id": "1", "class_type": "PromptNode", "input": "extra"}


def test_value_out_of_range_emits_error() -> None:
    provider = FakeSchemaProvider({"AceNode": _schema("AceNode", {"bpm": InputSpec("INT", min=10)})})
    report = _workflow(VibeNode("1", "AceNode", inputs={"bpm": 2})).validate(schema_provider=provider)

    assert not report.ok
    issue = report.issues[0]
    assert issue.code == "value_out_of_range"
    assert issue.detail["node_id"] == "1"
    assert issue.detail["class_type"] == "AceNode"
    assert issue.detail["input"] == "bpm"
    assert issue.detail["value"] == "2"
    assert issue.detail["min"] == 10
    assert issue.detail["max"] is None


def test_value_not_in_enum_emits_error() -> None:
    provider = FakeSchemaProvider({"ChoiceNode": _schema("ChoiceNode", {"mode": InputSpec("STRING", choices=["a", "b"])})})
    report = _workflow(VibeNode("1", "ChoiceNode", inputs={"mode": "c"})).validate(schema_provider=provider)

    assert not report.ok
    issue = report.issues[0]
    assert issue.code == "value_not_in_enum"
    assert issue.detail["node_id"] == "1"
    assert issue.detail["class_type"] == "ChoiceNode"
    assert issue.detail["input"] == "mode"
    assert issue.detail["value"] == "'c'"
    assert issue.detail["choices"] == ["a", "b"]


def test_dynamic_file_picker_choices_do_not_reject_task_inputs() -> None:
    provider = FakeSchemaProvider(
        {
            "LoadImage": _schema("LoadImage", {"image": InputSpec("STRING", choices=["previous.png"])}),
            "UNETLoader": _schema("UNETLoader", {"unet_name": InputSpec("STRING", choices=["model-a.safetensors"])}),
        }
    )
    workflow = _workflow(
        VibeNode("1", "LoadImage", inputs={"image": "task-specific.png"}),
        VibeNode("2", "UNETLoader", inputs={"unet_name": "missing-model.safetensors"}),
    )

    report = workflow.validate(schema_provider=provider)

    # Dynamic file pickers never reject task inputs: LoadImage is exempt
    # entirely, and a not-yet-installed model asset is a warning (structurally
    # valid), never a hard error (S01 / PR-E contract).
    assert report.ok
    issues = [
        issue for issue in report.issues
        if issue.code == "value_not_in_enum" and issue.detail.get("class_type") == "UNETLoader"
    ]
    assert issues, "UNETLoader env-asset mismatch should surface as a warning issue"
    assert issues[0].severity == "warning"
    assert issues[0].detail.get("choice_scope") == "environment_asset"
    assert not any(
        issue.detail.get("class_type") == "LoadImage" for issue in report.issues
    )


def test_normalization_proposal_drops_unknown_inputs_and_coerces_portable_choices() -> None:
    provider = FakeSchemaProvider(
        {
            "WanVideoLoraSelect": _schema(
                "WanVideoLoraSelect",
                {
                    "lora": InputSpec(
                        "STRING",
                        choices=["WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"],
                    ),
                    "strength": InputSpec("FLOAT"),
                },
            ),
            "LoadImage": _schema("LoadImage", {"image": InputSpec("STRING")}),
        }
    )
    api = {
        "1": {
            "class_type": "WanVideoLoraSelect",
            "inputs": {
                "lora": "WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                "strength": 1.0,
                "widget_0": "ui copy",
            },
        },
        "2": {"class_type": "LoadImage", "inputs": {"image": "start.png", "widget_0": "start.png"}},
    }
    before = copy.deepcopy(api)

    proposal = propose_schema_normalization(api, provider)

    # Queue preparation must never silently mutate the payload.
    assert api == before
    assert [(op.node_id, op.field, op.kind) for op in proposal.ops] == [
        ("1", "lora", "coerce"),
        ("1", "widget_0", "drop"),
        ("2", "widget_0", "drop"),
    ]
    coerce = proposal.ops[0]
    assert coerce.before == "WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"
    assert coerce.after == "WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"
    assert coerce.kind == "coerce"
    drop = proposal.ops[1]
    assert drop.before == "ui copy"
    assert drop.after is None
    assert "not declared" in drop.reason

    applied = apply_schema_normalization(api, proposal)

    assert applied["1"]["inputs"] == {
        "lora": "WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
        "strength": 1.0,
    }
    assert applied["2"]["inputs"] == {"image": "start.png"}
    assert api["1"]["inputs"]["widget_0"] == "ui copy"


def test_normalization_preserves_ltx_dynamic_image_slots() -> None:
    provider = FakeSchemaProvider(
        {
            "LTXVImgToVideoInplaceKJ": _schema(
                "LTXVImgToVideoInplaceKJ",
                {"num_images": InputSpec("INT"), "latent": InputSpec("LATENT"), "vae": InputSpec("VAE")},
            )
        }
    )
    api = {
        "210": {
            "class_type": "LTXVImgToVideoInplaceKJ",
            "inputs": {
                "num_images": "2",
                "num_images.image_1": ["1", 0],
                "num_images.index_1": 0,
                "num_images.strength_1": 1.0,
                "num_images.image_2": ["2", 0],
                "num_images.index_2": -1,
                "num_images.strength_2": 1.0,
                "widget_0": "ui alias",
            },
        }
    }

    proposal = propose_schema_normalization(api, provider)

    assert [(op.node_id, op.field, op.kind) for op in proposal.ops] == [("210", "widget_0", "drop")]
    applied = apply_schema_normalization(api, proposal)
    assert "widget_0" not in applied["210"]["inputs"]
    assert applied["210"]["inputs"]["num_images.strength_1"] == 1.0
    assert applied["210"]["inputs"]["num_images.strength_2"] == 1.0


def test_ltx_dynamic_image_slots_validate_required_fields() -> None:
    provider = FakeSchemaProvider(
        {
            "ImageSource": _schema("ImageSource", {}),
            "LTXVImgToVideoInplaceKJ": _schema(
                "LTXVImgToVideoInplaceKJ",
                {"num_images": InputSpec("INT"), "latent": InputSpec("LATENT"), "vae": InputSpec("VAE")},
            )
        }
    )
    workflow = _workflow(
        VibeNode("1", "ImageSource"),
        VibeNode("2", "ImageSource"),
        VibeNode(
            "210",
            "LTXVImgToVideoInplaceKJ",
            inputs={
                "num_images": 2,
                "num_images.index_1": 0,
                "num_images.strength_1": 1.0,
                "num_images.index_2": -1,
            },
        )
    )
    workflow.edges.extend(
        [
            VibeEdge("1", "0", "210", "num_images.image_1"),
            VibeEdge("2", "0", "210", "num_images.image_2"),
        ]
    )

    report = workflow.validate(schema_provider=provider)

    assert not report.ok
    assert [(issue.code, issue.detail["input"]) for issue in report.issues] == [
        ("missing_dynamic_input", "num_images.strength_2")
    ]


@pytest.mark.parametrize(
    ("class_type", "count"),
    [
        ("LTXVImgToVideoInplaceKJ", 2),
        ("ImageConcatMulti", 2),
    ],
)
def test_dynamic_count_accepts_normal_integer_counts(class_type: str, count: int) -> None:
    report = _dynamic_report(class_type, count)

    assert not report


@pytest.mark.parametrize("count", [20, 21])
def test_ltx_dynamic_count_does_not_embed_provider_ceiling(count: int) -> None:
    report = _dynamic_report("LTXVImgToVideoInplaceKJ", count)

    assert not [
        issue
        for issue in report
        if issue.code in {"invalid_dynamic_input_count", "missing_dynamic_input", "dynamic_input_exceeds_count"}
    ]


@pytest.mark.parametrize(
    ("class_type", "count"),
    [
        ("LTXVImgToVideoInplaceKJ", 0),
        ("LTXVImgToVideoInplaceKJ", -1),
        ("LTXVImgToVideoInplaceKJ", True),
        ("LTXVImgToVideoInplaceKJ", 2.0),
        ("LTXVImgToVideoInplaceKJ", "2"),
        ("LTXVImgToVideoInplaceKJ", 10**10000),
        ("ImageConcatMulti", 0),
        ("ImageConcatMulti", 1),
        ("ImageConcatMulti", -1),
        ("ImageConcatMulti", True),
        ("ImageConcatMulti", 2.0),
        ("ImageConcatMulti", "2"),
        ("ImageConcatMulti", 10**10000),
    ],
    ids=[
        "ltx-zero",
        "ltx-negative",
        "ltx-bool",
        "ltx-float",
        "ltx-string",
        "ltx-huge",
        "concat-zero",
        "concat-below-minimum",
        "concat-negative",
        "concat-bool",
        "concat-float",
        "concat-string",
        "concat-huge",
    ],
)
def test_dynamic_count_rejects_non_grammar_values(class_type: str, count: object) -> None:
    report = _dynamic_report(class_type, count, _dynamic_count_only_inputs(class_type, count))
    issues = [issue for issue in report if issue.code == "invalid_dynamic_input_count"]

    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].detail["input"] in {"num_images", "inputcount"}


@pytest.mark.parametrize("class_type", ["LTXVImgToVideoInplaceKJ", "ImageConcatMulti"])
def test_dynamic_count_rejects_missing_and_excess_slots(class_type: str) -> None:
    inputs = _dynamic_inputs(class_type, 2)
    missing_name = "num_images.strength_2" if class_type == "LTXVImgToVideoInplaceKJ" else "image_2"
    excess_name = "num_images.image_3" if class_type == "LTXVImgToVideoInplaceKJ" else "image_3"
    del inputs[missing_name]
    inputs[excess_name] = "excess"

    report = _dynamic_report(class_type, 2, inputs)

    assert [(issue.code, issue.detail["input"]) for issue in report if issue.code in {
        "missing_dynamic_input", "dynamic_input_exceeds_count"
    }] == [
        ("missing_dynamic_input", missing_name),
        ("dynamic_input_exceeds_count", excess_name),
    ]


def test_normalization_preserves_simple_calculator_autogrow_variables() -> None:
    provider = FakeSchemaProvider(
        {
            "SimpleCalculatorKJ": _schema(
                "SimpleCalculatorKJ",
                {"expression": InputSpec("STRING"), "variables": InputSpec("COMFY_AUTOGROW_V3")},
            )
        }
    )
    api = {
        "2077": {
            "class_type": "SimpleCalculatorKJ",
            "inputs": {
                "expression": "a",
                "variables": "a,b",
                "a": ["2078", 0],
                "b": ["2076", 0],
                "widget_0": "ui alias",
            },
        }
    }

    proposal = propose_schema_normalization(api, provider)

    assert [(op.node_id, op.field, op.kind) for op in proposal.ops] == [("2077", "widget_0", "drop")]
    applied = apply_schema_normalization(api, proposal)
    assert applied["2077"]["inputs"] == {
        "expression": "a",
        "variables": "a,b",
        "a": ["2078", 0],
        "b": ["2076", 0],
    }


def test_simple_calculator_autogrow_variables_validate_required_fields() -> None:
    provider = FakeSchemaProvider(
        {
            "ValueSource": _schema("ValueSource", {}),
            "SimpleCalculatorKJ": _schema(
                "SimpleCalculatorKJ",
                {"expression": InputSpec("STRING"), "variables": InputSpec("COMFY_AUTOGROW_V3")},
            )
        }
    )
    workflow = _workflow(
        VibeNode("2077", "SimpleCalculatorKJ", inputs={"expression": "a", "variables": "a,b"}),
        VibeNode("2078", "ValueSource"),
    )
    workflow.edges.append(VibeEdge("2078", "0", "2077", "a"))

    report = workflow.validate(schema_provider=provider)

    assert not report.ok
    assert [(issue.code, issue.detail["input"]) for issue in report.issues] == [("missing_dynamic_input", "b")]


def test_normalization_preserves_linked_fixed_slot_inputs_not_in_local_schema() -> None:
    provider = FakeSchemaProvider(
        {
            "FixedSlotConsumer": _schema("FixedSlotConsumer", {"declared": InputSpec("STRING")}),
        }
    )
    api = {
        "2": {
            "class_type": "FixedSlotConsumer",
            "inputs": {
                "declared": "ok",
                "in_0": ["1", 0],
                "extra_literal": "drop-me",
            },
        }
    }

    proposal = propose_schema_normalization(api, provider)
    applied = apply_schema_normalization(api, proposal)
    issues = validate_api_against_schema(applied, provider)

    # The linked fixed-slot input is preserved; only the literal is proposed.
    assert [(op.node_id, op.field, op.kind) for op in proposal.ops] == [("2", "extra_literal", "drop")]
    assert applied["2"]["inputs"] == {
        "declared": "ok",
        "in_0": ["1", 0],
    }
    assert all(
        not (issue.code == "unknown_input" and issue.detail.get("input") == "in_0")
        for issue in issues
    )


def test_invalid_link_shape_emits_error_for_dict_shaped_link() -> None:
    provider = FakeSchemaProvider({"Sink": _schema("Sink", {"latent": InputSpec("LATENT")})})
    report = _workflow(VibeNode("1", "Sink", inputs={"latent": {"link": 1, "node": "2"}})).validate(
        schema_provider=provider
    )

    assert not report.ok
    issue = report.issues[0]
    assert issue.code == "invalid_link_shape"
    assert issue.detail["node_id"] == "1"
    assert issue.detail["class_type"] == "Sink"
    assert issue.detail["input"] == "latent"
    assert issue.detail["value_repr"] == "{'link': 1, 'node': '2'}"


def test_field_compatibility_allows_only_the_documented_field_and_code() -> None:
    """A compatibility entry covers one (class_type, input) and one code — never a class."""
    # WanVideoModelLoader.vace_model is a documented known version mismatch
    # (snapshot predates the input); every OTHER unknown input stays an error.
    provider = FakeSchemaProvider(
        {
            "WanVideoModelLoader": _schema(
                "WanVideoModelLoader",
                {"model": InputSpec("STRING")},
            )
        }
    )
    workflow = _workflow(
        VibeNode(
            "1",
            "WanVideoModelLoader",
            inputs={"model": "wan.safetensors", "vace_model": "wan_vace.safetensors", "bogus": "value"},
        )
    )

    assert _codes(workflow, provider) == ["unknown_input"]

    # ImagePadKJ.pad_mode is a documented enum drift; type/range errors on the
    # same class are NOT suppressed.
    provider = FakeSchemaProvider(
        {
            "ImagePadKJ": _schema(
                "ImagePadKJ",
                {
                    "pad_mode": InputSpec("STRING", choices=["edge", "color"]),
                    "left": InputSpec("INT"),
                },
            )
        }
    )
    workflow = _workflow(
        VibeNode("2", "ImagePadKJ", inputs={"pad_mode": "255,255,255", "left": "not-an-int"})
    )

    assert _codes(workflow, provider) == ["value_type_mismatch"]


def test_field_compatibility_entry_is_typed_and_evidence_backed() -> None:
    entry = field_compatibility_for("WanVideoModelLoader", "vace_model")

    assert entry is not None
    assert entry.class_type == "WanVideoModelLoader"
    assert entry.input == "vace_model"
    assert entry.evidence.startswith("docs/node_pack_reconciliation.md")
    assert "unknown_input" in entry.codes

    assert field_compatibility_for("WanVideoModelLoader", "model") is None
    assert field_compatibility_for("WanVideoVACEModelSelect", "vace_model") is not None


def test_unknown_inputs_on_undocumented_stub_classes_remain_errors() -> None:
    """Fail-closed: no class-wide suppression survives; stub classes error."""
    provider = FakeSchemaProvider(
        {
            "Florence2Run": _schema(
                "Florence2Run",
                {"image": InputSpec("IMAGE"), "task": InputSpec("STRING", choices=["caption"])},
            )
        }
    )
    workflow = _workflow(
        VibeNode("1", "Florence2Run", inputs={"image": "fake-image", "task": "ocr", "extra": "value"})
    )

    assert _codes(workflow, provider) == ["unknown_input", "value_not_in_enum"]


def test_normalization_requires_explicit_approval_and_refusal_carries_details() -> None:
    provider = FakeSchemaProvider(
        {
            "WanVideoLoraSelect": _schema(
                "WanVideoLoraSelect",
                {"lora": InputSpec("STRING"), "strength": InputSpec("FLOAT")},
            )
        }
    )
    api = {
        "1": {
            "class_type": "WanVideoLoraSelect",
            "inputs": {"lora": "a.safetensors", "strength": 1.0, "widget_0": "ui copy"},
        }
    }

    proposal = propose_schema_normalization(api, provider)

    assert proposal.ops
    assert proposal.approved_by(None) is False
    assert proposal.approved_by("not-the-digest") is False

    refusal = SchemaNormalizationRequired(proposal)
    text = str(refusal)
    assert "Queue normalization requires agent approval" in text
    assert "node=1" in text
    assert "field=widget_0" in text
    assert "before='ui copy'" in text
    assert "after=None" in text
    assert "reason=" in text
    payload = refusal.to_dict()
    assert payload["normalization"]["ops"][0]["node_id"] == "1"
    assert payload["normalization"]["ops"][0]["field"] == "widget_0"


def test_approval_binds_to_exact_proposal_digest() -> None:
    provider = FakeSchemaProvider(
        {
            "WanVideoLoraSelect": _schema(
                "WanVideoLoraSelect",
                {"lora": InputSpec("STRING", choices=["WanVideo/a.safetensors"]), "strength": InputSpec("FLOAT")},
            ),
        }
    )
    # api_a needs a coerce + a drop; api_b only needs the drop.
    api_a = {
        "1": {
            "class_type": "WanVideoLoraSelect",
            "inputs": {"lora": "WanVideo\\a.safetensors", "strength": 1.0, "extra": "x"},
        }
    }
    api_b = {
        "1": {
            "class_type": "WanVideoLoraSelect",
            "inputs": {"lora": "WanVideo/a.safetensors", "strength": 1.0, "extra": "x"},
        }
    }

    proposal_a = propose_schema_normalization(api_a, provider)
    proposal_b = propose_schema_normalization(api_b, provider)

    assert [(op.field, op.kind) for op in proposal_a.ops] == [("extra", "drop"), ("lora", "coerce")]
    assert [(op.field, op.kind) for op in proposal_b.ops] == [("extra", "drop")]
    assert proposal_a.digest() != proposal_b.digest()
    approval = NormalizationApproval(proposal_a.digest(), granted_by="test-agent")
    assert proposal_a.approved_by(approval) is True
    # A bare digest string is also an explicit approval.
    assert proposal_a.approved_by(proposal_a.digest()) is True
    # The approval never applies to a different proposal.
    assert proposal_b.approved_by(approval) is False


def test_apply_schema_normalization_refuses_stale_proposals() -> None:
    provider = FakeSchemaProvider(
        {
            "WanVideoLoraSelect": _schema(
                "WanVideoLoraSelect",
                {"lora": InputSpec("STRING"), "strength": InputSpec("FLOAT")},
            )
        }
    )
    api = {
        "1": {
            "class_type": "WanVideoLoraSelect",
            "inputs": {"lora": "a.safetensors", "strength": 1.0, "widget_0": "ui copy"},
        }
    }

    proposal = propose_schema_normalization(api, provider)

    # Value changed since the proposal was computed: applying must refuse.
    drifted = copy.deepcopy(api)
    drifted["1"]["inputs"]["widget_0"] = "different copy"
    with pytest.raises(SchemaNormalizationMismatch):
        apply_schema_normalization(drifted, proposal)

    # Node disappeared: applying must refuse.
    gone = {"2": {"class_type": "Other", "inputs": {}}}
    with pytest.raises(SchemaNormalizationMismatch):
        apply_schema_normalization(gone, proposal)


def test_normalization_never_proposes_changes_for_compatible_fields() -> None:
    """Known version-mismatch fields are compatible: never proposed for drop."""
    provider = FakeSchemaProvider(
        {
            "WanVideoModelLoader": _schema(
                "WanVideoModelLoader",
                {"model": InputSpec("STRING")},
            ),
            "WanVideoVACEModelSelect": _schema(
                "WanVideoVACEModelSelect",
                {"vace_model": InputSpec("STRING", choices=["ltx-2.3-22b.safetensors"])},
            ),
        }
    )
    api = {
        "1": {
            "class_type": "WanVideoModelLoader",
            "inputs": {"model": "wan.safetensors", "vace_model": ["4", 0]},
        },
        "2": {
            "class_type": "WanVideoVACEModelSelect",
            "inputs": {"vace_model": "WanVideo/Wan2_1-VACE_module_1_3B_bf16.safetensors"},
        },
    }

    proposal = propose_schema_normalization(api, provider)

    assert proposal.ops == ()


def test_normalization_preserves_widget_schema_api_links() -> None:
    class WidgetSchemaProvider(FakeSchemaProvider):
        pass

    schema = _schema("WanVideoSampler", {"steps": InputSpec("INT")})
    object.__setattr__(schema, "source_provider", "widget_schema")
    provider = WidgetSchemaProvider({"WanVideoSampler": schema})
    api = {
        "1": {
            "class_type": "WanVideoSampler",
            "inputs": {"steps": 20, "text_embeds": ["2", 0]},
        }
    }

    proposal = propose_schema_normalization(api, provider)

    assert proposal.ops == ()


def test_range_enum_skipped_when_value_is_api_link() -> None:
    provider = FakeSchemaProvider(
        {
            "ChoiceNode": _schema("ChoiceNode", {"mode": InputSpec("INT", min=10, choices=[10])}),
            "ValueSource": _schema("ValueSource", {}),
        }
    )
    workflow = _workflow(VibeNode("1", "ChoiceNode"), VibeNode("3", "ValueSource"))
    workflow.edges.append(VibeEdge("3", "0", "1", "mode"))
    report = workflow.validate(schema_provider=provider)

    assert report.ok
    assert report.issues == []


# Schema regression-guard contract — see .megaplan/plans/brief-a-internal-testing-20260516-0048/ (T7).
@pytest.mark.parametrize("snapshot", sorted(Path("tests/snapshots").glob("*.api.json")))
def test_snapshot_api_workflows_validate_against_permissive_local_schema(snapshot: Path, tmp_path: Path) -> None:
    api = json.loads(snapshot.read_text(encoding="utf-8"))
    rows: dict[str, dict] = {}
    for node in api.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", "Unknown"))
        row = rows.setdefault(class_type, {"class_type": class_type, "inputs": {}})
        for name in (node.get("inputs") or {}):
            row["inputs"][name] = "*"
    index_path = tmp_path / "node_index.json"
    index_path.write_text(json.dumps(list(rows.values())), encoding="utf-8")
    provider = LocalSchemaProvider(index_path)
    workflow = from_api(api, workflow_id=snapshot.stem, schema_provider=provider)

    report = workflow.validate(schema_provider=provider)

    assert report.ok, [f"{issue.code}: {issue.message}" for issue in report.issues]

# ── T16: advisory_validation_for_precedent tests ────────────────────────────


def test_advisory_validation_for_precedent_returns_empty_for_none_route() -> None:
    """Returns empty list when route is None."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    issues = [type("Issue", (), {"code": "missing_required_input", "message": "missing text"})()]
    result = advisory_validation_for_precedent(issues, route=None)
    assert result == []


def test_advisory_validation_for_precedent_returns_empty_for_direct_edit() -> None:
    """Returns empty list when route is direct_edit (structural gate applies)."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    issues = [type("Issue", (), {"code": "missing_required_input", "message": "missing text"})()]
    result = advisory_validation_for_precedent(issues, route="direct_edit")
    assert result == []


def test_advisory_validation_for_precedent_returns_empty_for_inspect_only() -> None:
    """Returns empty list when route is inspect_only."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    issues = [type("Issue", (), {"code": "unsatisfied_input", "message": "input missing"})()]
    result = advisory_validation_for_precedent(issues, route="inspect_only")
    assert result == []


def test_advisory_validation_for_precedent_returns_empty_for_clarify() -> None:
    """Returns empty list when route is clarify."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    issues = [type("Issue", (), {"code": "schema_gap", "message": "unknown node"})()]
    result = advisory_validation_for_precedent(issues, route="clarify")
    assert result == []


def test_advisory_validation_for_precedent_converts_issues_for_precedent_research() -> None:
    """precedent_research route maps validation issues to advisory entries."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    issues = [
        type("Issue", (), {"code": "missing_required_input", "message": "missing 'text' input"})()
    ]
    result = advisory_validation_for_precedent(issues, route="precedent_research")
    assert len(result) == 1
    assert result[0]["check"] == "schema:missing_required_input"
    assert result[0]["status"] == "advisory"
    assert result[0]["satisfaction"] == "advisory"
    assert "missing 'text' input" in result[0]["description"]


def test_advisory_validation_for_precedent_multiple_issues() -> None:
    """Multiple validation issues produce multiple advisory entries."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    issues = [
        type("Issue", (), {"code": "missing_required_input", "message": "missing input"})(),
        type("Issue", (), {"code": "unsatisfied_input", "message": "unsatisfied link"})(),
    ]
    result = advisory_validation_for_precedent(issues, route="precedent_research")
    assert len(result) == 2
    assert result[0]["check"] == "schema:missing_required_input"
    assert result[1]["check"] == "schema:unsatisfied_input"
    for entry in result:
        assert entry["status"] == "advisory"
        assert entry["satisfaction"] == "advisory"


def test_advisory_validation_for_precedent_handles_issue_without_code() -> None:
    """Issue without a code attribute uses 'schema:validation' as check key."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    # Object with message but no code
    issue = type("Issue", (), {"message": "some problem"})()
    result = advisory_validation_for_precedent([issue], route="precedent_research")
    assert len(result) == 1
    assert result[0]["check"] == "schema:validation"


def test_advisory_validation_for_precedent_handles_dict_issues() -> None:
    """Issues passed as dicts are handled correctly."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    issues = [{"code": "schema_gap", "message": "node not in registry"}]
    result = advisory_validation_for_precedent(issues, route="precedent_research")
    assert len(result) == 1
    assert result[0]["check"] == "schema:schema_gap"
    assert result[0]["description"] == "node not in registry"


def test_advisory_validation_for_precedent_truncates_long_messages() -> None:
    """Descriptions are truncated at 500 characters."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    long_message = "x" * 1000
    issues = [type("Issue", (), {"code": "E1", "message": long_message})()]
    result = advisory_validation_for_precedent(issues, route="precedent_research")
    assert len(result) == 1
    assert len(result[0]["description"]) <= 500


def test_advisory_validation_for_precedent_empty_issues() -> None:
    """Empty issues list returns empty list."""
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    result = advisory_validation_for_precedent([], route="precedent_research")
    assert result == []


def test_advisory_validation_for_precedent_does_not_block_structural_gates() -> None:
    """precedent semantic checks are advisory only and do not alter structural gating.
    
    When route is precedent_research, issues are downgraded to advisory entries
    but the original validation issues list is unchanged — the caller still owns
    the structural gate decision.
    """
    from vibecomfy.schema.validate import advisory_validation_for_precedent
    issues = [
        type("Issue", (), {"code": "missing_required_input", "message": "missing input"})(),
        type("Issue", (), {"code": "unsatisfied_input", "message": "unsatisfied link"})(),
    ]
    original_count = len(issues)
    result = advisory_validation_for_precedent(issues, route="precedent_research")
    # The advisory entries exist for observability
    assert len(result) == original_count
    # But the original issues list length is unchanged (caller still owns gating)
    assert len(issues) == original_count
