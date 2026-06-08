from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.schema import InputSpec, LocalSchemaProvider, NodeSchema
from vibecomfy.schema.validate import (
    SCHEMA_VALIDATION_SKIP_CLASSES,
    sanitize_api_against_schema,
    validate_api_against_schema,
)
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


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

    assert not report.ok
    assert [(issue.code, issue.detail["class_type"], issue.detail["input"]) for issue in report.issues] == [
        ("value_not_in_enum", "UNETLoader", "unet_name")
    ]


def test_sanitize_api_strips_unknown_runtime_inputs_and_coerces_portable_choices() -> None:
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

    sanitized = sanitize_api_against_schema(api, provider)

    assert sanitized["1"]["inputs"] == {
        "lora": "WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
        "strength": 1.0,
    }
    assert sanitized["2"]["inputs"] == {"image": "start.png"}
    assert api["1"]["inputs"]["widget_0"] == "ui copy"


def test_sanitize_preserves_ltx_dynamic_image_slots() -> None:
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

    sanitized = sanitize_api_against_schema(api, provider)

    assert "widget_0" not in sanitized["210"]["inputs"]
    assert sanitized["210"]["inputs"]["num_images.strength_1"] == 1.0
    assert sanitized["210"]["inputs"]["num_images.strength_2"] == 1.0


def test_ltx_dynamic_image_slots_validate_required_fields() -> None:
    provider = FakeSchemaProvider(
        {
            "LTXVImgToVideoInplaceKJ": _schema(
                "LTXVImgToVideoInplaceKJ",
                {"num_images": InputSpec("INT"), "latent": InputSpec("LATENT"), "vae": InputSpec("VAE")},
            )
        }
    )
    workflow = _workflow(
        VibeNode(
            "210",
            "LTXVImgToVideoInplaceKJ",
            inputs={
                "num_images": "2",
                "num_images.image_1": ["1", 0],
                "num_images.index_1": 0,
                "num_images.strength_1": 1.0,
                "num_images.image_2": ["2", 0],
                "num_images.index_2": -1,
            },
        )
    )

    report = workflow.validate(schema_provider=provider)

    assert not report.ok
    assert [(issue.code, issue.detail["input"]) for issue in report.issues] == [
        ("missing_dynamic_input", "num_images.strength_2")
    ]


def test_sanitize_preserves_simple_calculator_autogrow_variables() -> None:
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

    sanitized = sanitize_api_against_schema(api, provider)

    assert sanitized["2077"]["inputs"] == {
        "expression": "a",
        "variables": "a,b",
        "a": ["2078", 0],
        "b": ["2076", 0],
    }


def test_simple_calculator_autogrow_variables_validate_required_fields() -> None:
    provider = FakeSchemaProvider(
        {
            "SimpleCalculatorKJ": _schema(
                "SimpleCalculatorKJ",
                {"expression": InputSpec("STRING"), "variables": InputSpec("COMFY_AUTOGROW_V3")},
            )
        }
    )
    workflow = _workflow(
        VibeNode("2077", "SimpleCalculatorKJ", inputs={"expression": "a", "variables": "a,b", "a": ["2078", 0]})
    )

    report = workflow.validate(schema_provider=provider)

    assert not report.ok
    assert [(issue.code, issue.detail["input"]) for issue in report.issues] == [("missing_dynamic_input", "b")]


def test_sanitize_and_validate_preserve_linked_fixed_slot_inputs_not_in_local_schema() -> None:
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

    sanitized = sanitize_api_against_schema(api, provider)
    issues = validate_api_against_schema(sanitized, provider)

    assert sanitized["2"]["inputs"] == {
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


def test_skip_list_suppresses_unknown_and_value_issues_only() -> None:
    SCHEMA_VALIDATION_SKIP_CLASSES["LyingNode"] = "test-only"
    try:
        provider = FakeSchemaProvider(
            {
                "LyingNode": _schema(
                    "LyingNode",
                    {
                        "required": InputSpec("STRING", required=True),
                        "mode": InputSpec("STRING", choices=["a"]),
                    },
                )
            }
        )
        workflow = _workflow(VibeNode("1", "LyingNode", inputs={"mode": "b", "extra": "value"}))

        assert _codes(workflow, provider) == ["missing_required_input"]
    finally:
        SCHEMA_VALIDATION_SKIP_CLASSES.pop("LyingNode", None)


def test_range_enum_skipped_when_value_is_api_link() -> None:
    provider = FakeSchemaProvider({"ChoiceNode": _schema("ChoiceNode", {"mode": InputSpec("INT", min=10, choices=[10])})})
    report = _workflow(VibeNode("1", "ChoiceNode", inputs={"mode": ["3", 0]})).validate(schema_provider=provider)

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
    workflow = convert_to_vibe_format(api, workflow_id=snapshot.stem, schema_provider=provider)

    report = workflow.validate(schema_provider=provider)

    assert report.ok, [f"{issue.code}: {issue.message}" for issue in report.issues]
