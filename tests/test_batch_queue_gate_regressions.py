from __future__ import annotations

from types import SimpleNamespace

from vibecomfy.comfy_nodes.agent._frag_humanize import _batch_candidate_graph_changed
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import RawWidgetPayload, VibeNode, VibeWorkflow, WorkflowSource


class _QwenProvider:
    def get_schema(self, class_type: str) -> NodeSchema | None:
        if class_type != "TextEncodeQwenImageEditPlus":
            return None
        return NodeSchema(
            class_type,
            "test",
            {"prompt": InputSpec("STRING")},
            [OutputSpec("CONDITIONING", "CONDITIONING")],
        )


def _qwen_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("qwen-regression", WorkflowSource("test"))
    workflow.nodes["133"] = VibeNode(
        "133",
        "TextEncodeQwenImageEditPlus",
        uid="133",
        widgets={"widget_0": "old prompt"},
        raw_widgets=RawWidgetPayload(
            values=["old prompt"],
            shape="list",
            source="ui.widgets_values",
            has_dict_rows=False,
            length=1,
        ),
        metadata={
            "_ui": {
                "id": 133,
                "type": "TextEncodeQwenImageEditPlus",
                "widgets_values": ["old prompt"],
                "properties": {},
            }
        },
    )
    return workflow


def test_semantic_qwen_edit_reaches_candidate_without_duplicate_widget_rows() -> None:
    provider = _QwenProvider()
    workflow = _qwen_workflow()
    session = EditSession(
        emit_ui_json(workflow, schema_provider=provider),
        schema_provider=provider,
        initial_workflow=workflow,
    )

    result = session.apply_batch(
        "textencodeqwenimageeditplus.prompt = 'new prompt'"
    )

    assert result.ok is True
    assert result.field_changes[0].old == "old prompt"
    node = session.working_ui["nodes"][0]
    assert node["widgets_values"] == ["new prompt"]


def test_batch_candidate_change_compares_api_baseline_to_ui_candidate() -> None:
    provider = _QwenProvider()
    workflow = _qwen_workflow()
    session = EditSession(
        emit_ui_json(workflow, schema_provider=provider),
        schema_provider=provider,
        initial_workflow=workflow,
    )
    result = session.apply_batch(
        "textencodeqwenimageeditplus.prompt = 'new prompt'"
    )
    assert result.ok is True

    baseline_api = {
        "133": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {"widget_0": "old prompt"},
        }
    }
    state = SimpleNamespace(
        graph=baseline_api,
        ui_payload=session.working_ui,
        schema_provider=provider,
    )
    assert _batch_candidate_graph_changed(state) is True

    state.ui_payload = EditSession(
        emit_ui_json(workflow, schema_provider=provider),
        schema_provider=provider,
        initial_workflow=workflow,
    ).working_ui
    assert _batch_candidate_graph_changed(state) is False
