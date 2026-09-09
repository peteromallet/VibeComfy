from vibecomfy._compile._widgets import WIDGET_SCHEMA
from vibecomfy.schema.provider import NodeSchema
from vibecomfy.schema.types import InputSpec
from vibecomfy.schema.validate import validate_api_against_schema


class _Provider:
    def __init__(self, schemas):
        self.schemas = schemas

    def get_schema(self, class_type):
        return self.schemas.get(class_type)


def test_h3_widget_slots_preserve_core_and_lanpaint_values():
    assert WIDGET_SCHEMA["ResolutionSelector"] == ["aspect_ratio", "megapixels", "multiple"]
    assert WIDGET_SCHEMA["LanPaint_SamplerCustomAdvanced"][-1] is None
    assert WIDGET_SCHEMA["ComfyMathExpression"] == ["expression"]


def test_comfy_math_expression_accepts_autogrow_dotted_values():
    provider = _Provider(
        {
            "ComfyMathExpression": NodeSchema(
                class_type="ComfyMathExpression",
                pack="comfy_core",
                inputs={
                    "expression": InputSpec("STRING", required=True),
                    "values": InputSpec("COMFY_AUTOGROW_V3", required=True),
                },
                outputs=[],
            )
        }
    )
    issues = validate_api_against_schema(
        {
            "107": {
                "class_type": "ComfyMathExpression",
                "inputs": {
                    "expression": "a * 2",
                    "values.a": ["115", 1],
                },
            }
        },
        provider,
    )
    assert not [issue for issue in issues if issue.severity == "error"]
