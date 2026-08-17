from types import SimpleNamespace

import pytest

from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit.ops import parse_edit_delta
from vibecomfy.porting.edit.validate import validate_literal_value
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema import InputSpec, NodeSchema


def _validate(value: object, spec: SimpleNamespace, *, input_name: str) -> list:
    return validate_literal_value(
        value=value,
        spec=spec,
        class_type="TestNode",
        input_name=input_name,
        context="test",
    )


@pytest.mark.parametrize(
    ("spec", "input_name", "value"),
    [
        (SimpleNamespace(choices=["installed.safetensors"], type="lora"), "lora", "missing"),
        (
            SimpleNamespace(choices=["models/installed.safetensors"], type="STRING"),
            "choice",
            "missing",
        ),
        (
            SimpleNamespace(choices=["installed"], type="STRING"),
            "choice",
            "WanVid/notinstalled.safetensors",
        ),
    ],
)
def test_validate_asset_enum_accepts_missing_local_asset_with_warning(
    spec: SimpleNamespace,
    input_name: str,
    value: str,
) -> None:
    issues = _validate(value, spec, input_name=input_name)

    assert [(issue.code, issue.severity) for issue in issues] == [
        ("asset_not_installed", "warning")
    ]
    assert issues[0].detail["value"] == value


@pytest.mark.parametrize(
    ("input_name", "value"),
    [
        ("scheduler", "bogus_scheduler"),
        ("model_type", "bogus_model_type"),
    ],
)
def test_validate_constrained_enum_still_rejects_unknown_value(
    input_name: str,
    value: str,
) -> None:
    spec = SimpleNamespace(choices=["euler", "dpm++_2m"], type="STRING", min=None, max=None)

    issues = _validate(value, spec, input_name=input_name)

    assert [(issue.code, issue.severity) for issue in issues] == [
        ("value_not_in_enum", "error")
    ]


def test_validate_asset_enum_does_not_accept_non_string_value() -> None:
    spec = SimpleNamespace(choices=["installed.safetensors"], type="lora")

    issues = _validate(123, spec, input_name="lora")

    assert issues[0].code == "value_not_in_enum"
    assert issues[0].severity == "error"


def test_interpret_add_node_keeps_missing_asset_filename_and_warning() -> None:
    schema = NodeSchema(
        class_type="WanVideoLoraSelect",
        pack="test",
        inputs={
            "lora": InputSpec(
                type="lora",
                choices=["installed.safetensors"],
            )
        },
        outputs=[],
    )
    provider = SimpleNamespace(get_schema=lambda class_type: schema if class_type == schema.class_type else None)
    ui = {"last_node_id": 0, "last_link_id": 0, "nodes": [], "links": []}
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": schema.class_type,
                "fields": {"lora": "WanVid/notinstalled.safetensors"},
                "inputs": {},
            }
        ]
    )

    workflow = from_ui(ui, schema_provider=provider, use_comfy_converter=False)
    result = interpret(workflow, delta, schema_provider=provider)

    assert result.ok is True
    candidate = emit_ui_json(
        result.workflow,
        schema_provider=provider,
        include_virtual_wires=True,
        prior_ui_payload=ui,
    )
    assert candidate["nodes"][0]["widgets_values"] == ["WanVid/notinstalled.safetensors"]
    warning = next(issue for issue in result.diagnostics if issue.code == "asset_not_installed")
    assert warning.severity == "warning"
