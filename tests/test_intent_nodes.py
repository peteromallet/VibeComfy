from __future__ import annotations

import pytest

from vibecomfy.contracts import (
    INTENT_CODE_MAX_BYTES,
    INTENT_LOOP_MAX_ITERATIONS,
    INTENT_NODE_CONTRACT_INVALID_CODE,
    INTENT_NODE_EDITOR_ONLY_CODE,
    intent_node_payload_from_metadata,
    intent_node_properties,
    intent_node_properties_from_metadata,
    validate_intent_node_contract,
)
from vibecomfy.contracts.intent_nodes import INTENT_SPEC_MAX_BYTES
from vibecomfy.contracts.validation import comfyui_node_issue_specs
from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.ui_emitter import emit_ui_json
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _metadata(properties: dict[str, object]) -> dict[str, object]:
    return {"_ui": {"properties": properties}}


def test_intent_node_properties_builds_programmatic_properties_blob() -> None:
    properties = intent_node_properties(
        kind="code",
        uid="intent-1",
        intent={"source": "value = 1"},
        inputs=[("prompt", "STRING")],
        outputs=[("image", "IMAGE")],
        extra_properties={"title": "Intent code"},
    )

    assert properties == {
        "title": "Intent code",
        "vibecomfy_uid": "intent-1",
        "vibecomfy": {
            "kind": "code",
            "intent": {"source": "value = 1"},
            "io": {
                "inputs": [["prompt", "STRING"]],
                "outputs": [["image", "IMAGE"]],
            },
        },
    }
    assert intent_node_properties_from_metadata(_metadata(properties)) == properties
    assert intent_node_payload_from_metadata(_metadata(properties)) == properties["vibecomfy"]


def test_workflow_validate_treats_valid_intent_node_as_warning_only() -> None:
    workflow = VibeWorkflow("intent", WorkflowSource("intent"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.code",
        metadata=_metadata(
            intent_node_properties(
                kind="code",
                uid="intent-1",
                intent={"source": "value = 1"},
                inputs=[("prompt", "STRING")],
                outputs=[("image", "IMAGE")],
            )
        ),
    )

    report = workflow.validate()

    assert report.ok
    assert [issue.code for issue in report.issues] == [INTENT_NODE_EDITOR_ONLY_CODE]
    assert report.issues[0].severity == "warning"
    assert workflow.compile("api")["1"]["class_type"] == "vibecomfy.code"


def test_workflow_validate_treats_valid_loop_intent_node_as_warning_only() -> None:
    workflow = VibeWorkflow("intent-loop", WorkflowSource("intent-loop"))
    workflow.nodes["2"] = VibeNode(
        "2",
        "vibecomfy.loop",
        metadata=_metadata(
            intent_node_properties(
                kind="loop",
                uid="loop-1",
                intent={"var": "seed", "count": 3},
                inputs=[("image", "IMAGE")],
                outputs=[("image", "IMAGE")],
            )
        ),
    )

    report = workflow.validate()

    assert report.ok
    assert [issue.code for issue in report.issues] == [INTENT_NODE_EDITOR_ONLY_CODE]
    assert report.issues[0].severity == "warning"
    assert workflow.compile("api")["2"]["class_type"] == "vibecomfy.loop"


def test_validate_intent_node_contract_reports_missing_uid_and_forbidden_source() -> None:
    result = validate_intent_node_contract(
        node_id="7",
        class_type="vibecomfy.code",
        metadata=_metadata(
            {
                "vibecomfy": {
                    "kind": "code",
                    "intent": {"source": "import os\nvalue = 1"},
                    "io": {"inputs": [["prompt", "STRING"]], "outputs": [["image", "IMAGE"]]},
                }
            }
        ),
    )

    assert not result.ok
    assert {problem.code for problem in result.problems} >= {"missing_uid", "forbidden_import"}


def test_validate_intent_node_contract_enforces_loop_bounds() -> None:
    result = validate_intent_node_contract(
        node_id="9",
        class_type="vibecomfy.loop",
        metadata=_metadata(
            intent_node_properties(
                kind="loop",
                uid="loop-1",
                intent={"var": "seed", "over": list(range(INTENT_LOOP_MAX_ITERATIONS + 1))},
                inputs=[("image", "IMAGE")],
                outputs=[("image", "IMAGE")],
            )
        ),
    )

    assert not result.ok
    assert {problem.code for problem in result.problems} == {"loop_bound"}


@pytest.mark.parametrize(
    ("class_type", "properties", "expected_problem_codes"),
    [
        pytest.param(
            "vibecomfy.code",
            {
                "vibecomfy": {
                    "kind": "code",
                    "intent": {"source": "value = 1"},
                    "io": {"inputs": [["prompt", "STRING"]], "outputs": [["image", "IMAGE"]]},
                }
            },
            {"missing_uid"},
            id="missing-uid",
        ),
        pytest.param(
            "vibecomfy.code",
            {
                "vibecomfy_uid": "intent-missing-kind",
                "vibecomfy": {
                    "intent": {"source": "value = 1"},
                    "io": {"inputs": [["prompt", "STRING"]], "outputs": [["image", "IMAGE"]]},
                },
            },
            {"missing_kind"},
            id="missing-kind",
        ),
        pytest.param(
            "vibecomfy.code",
            intent_node_properties(
                kind="loop",
                uid="intent-kind-mismatch",
                intent={"var": "seed", "count": 2},
                inputs=[("prompt", "STRING")],
                outputs=[("image", "IMAGE")],
            ),
            {"kind_class_mismatch"},
            id="kind-class-mismatch",
        ),
        pytest.param(
            "vibecomfy.code",
            {
                "vibecomfy_uid": "intent-missing-io",
                "vibecomfy": {
                    "kind": "code",
                    "intent": {"source": "value = 1"},
                },
            },
            {"missing_typed_io"},
            id="missing-typed-io",
        ),
        pytest.param(
            "vibecomfy.code",
            intent_node_properties(
                kind="code",
                uid="intent-large-source",
                intent={"source": "x" * (INTENT_CODE_MAX_BYTES + 1)},
                inputs=[("prompt", "STRING")],
                outputs=[("image", "IMAGE")],
            ),
            {"text_too_large"},
            id="oversized-source",
        ),
        pytest.param(
            "vibecomfy.code",
            intent_node_properties(
                kind="code",
                uid="intent-large-spec",
                intent={"spec": "x" * (INTENT_SPEC_MAX_BYTES + 1)},
                inputs=[("prompt", "STRING")],
                outputs=[("image", "IMAGE")],
            ),
            {"text_too_large"},
            id="oversized-spec",
        ),
        pytest.param(
            "vibecomfy.code",
            intent_node_properties(
                kind="code",
                uid="intent-forbidden-call",
                intent={"source": "eval('1')\n"},
                inputs=[("prompt", "STRING")],
                outputs=[("image", "IMAGE")],
            ),
            {"forbidden_call"},
            id="forbidden-operations",
        ),
        pytest.param(
            "vibecomfy.loop",
            intent_node_properties(
                kind="loop",
                uid="loop-missing-bound",
                intent={"var": "seed"},
                inputs=[("image", "IMAGE")],
                outputs=[("image", "IMAGE")],
            ),
            {"missing_loop_bound"},
            id="missing-loop-bound",
        ),
        pytest.param(
            "vibecomfy.loop",
            intent_node_properties(
                kind="loop",
                uid="loop-excessive-bound",
                intent={"var": "seed", "count": INTENT_LOOP_MAX_ITERATIONS + 1},
                inputs=[("image", "IMAGE")],
                outputs=[("image", "IMAGE")],
            ),
            {"loop_bound"},
            id="excessive-loop-bound",
        ),
    ],
)
def test_validate_intent_node_contract_invalid_cases(
    class_type: str,
    properties: dict[str, object],
    expected_problem_codes: set[str],
) -> None:
    result = validate_intent_node_contract(
        node_id="99",
        class_type=class_type,
        metadata=_metadata(properties),
    )

    assert not result.ok
    assert expected_problem_codes <= {problem.code for problem in result.problems}


def test_comfyui_node_issue_specs_marks_invalid_intent_node_as_contract_error() -> None:
    issues = comfyui_node_issue_specs(
        [
            (
                "3",
                "vibecomfy.code",
                {},
                _metadata(
                    intent_node_properties(
                        kind="code",
                        uid="intent-3",
                        intent={"spec": "x" * (INTENT_CODE_MAX_BYTES + 1)},
                        inputs=[("prompt", "STRING")],
                        outputs=[("image", "IMAGE")],
                    )
                ),
            )
        ]
    )

    assert [issue.code for issue in issues] == [INTENT_NODE_CONTRACT_INVALID_CODE]
    assert issues[0].detail["intent_issue_code"] == "text_too_large"


def test_code_contract_preserves_agent_scanner_forbidden_codes_in_issue_details() -> None:
    issues = comfyui_node_issue_specs(
        [
            (
                "3",
                "vibecomfy.code",
                {},
                _metadata(
                    intent_node_properties(
                        kind="code",
                        uid="intent-3",
                        intent={
                            "source": (
                                "from vibecomfy.templates import node\n"
                                "value = __secret\n"
                                "eval('1')\n"
                                "thing.__class__\n"
                            )
                        },
                        inputs=[("prompt", "STRING")],
                        outputs=[("image", "IMAGE")],
                    )
                ),
            )
        ]
    )

    assert {issue.code for issue in issues} == {INTENT_NODE_CONTRACT_INVALID_CODE}
    assert {issue.detail["intent_issue_code"] for issue in issues} >= {
        "forbidden_call",
        "forbidden_name",
        "dunder_access",
    }


def test_comfyui_node_issue_specs_remains_backward_compatible_for_legacy_triplets() -> None:
    issues = comfyui_node_issue_specs([("1", "SaveImage", {"filename_prefix": "test"})])

    assert issues == []


def test_intent_comfy_nodes_register_editor_only_noop_classes() -> None:
    from vibecomfy.comfy_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

    source_payload = object()
    spec_payload = object()

    for class_type, kind, display in (
        ("vibecomfy.code", "code", "VibeComfy Code Intent"),
        ("vibecomfy.loop", "loop", "VibeComfy Loop Intent"),
    ):
        node_cls = NODE_CLASS_MAPPINGS[class_type]

        assert NODE_DISPLAY_NAME_MAPPINGS[class_type] == display
        assert node_cls.CATEGORY == "vibecomfy/intent"
        assert node_cls.RETURN_TYPES == ("*",)
        assert node_cls.RETURN_NAMES == ("value",)
        assert node_cls.FUNCTION == "passthrough"
        assert node_cls.VIBECOMFY_INTENT_KIND == kind
        assert node_cls.VIBECOMFY_EDITOR_ONLY is True
        assert node_cls.VIBECOMFY_RUNTIME_BACKED is False
        assert node_cls.VIBECOMFY_LOWERED is False
        assert node_cls.INPUT_TYPES()["required"] == {"value": ("*",)}
        assert node_cls().passthrough(
            "sentinel",
            source=source_payload,
            spec=spec_payload,
        ) == ("sentinel",)


def test_ui_json_intent_properties_survive_ingest_and_emit_round_trip() -> None:
    code_properties = intent_node_properties(
        kind="code",
        uid="code-uid",
        intent={"source": "value = 1"},
        inputs=[("prompt", "STRING")],
        outputs=[("image", "IMAGE")],
    )
    loop_properties = intent_node_properties(
        kind="loop",
        uid="loop-uid",
        intent={"var": "frame", "count": 3},
        inputs=[("image", "IMAGE")],
        outputs=[("image", "IMAGE")],
    )
    ui_graph = {
        "version": 0.4,
        "last_node_id": 2,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "vibecomfy.code",
                "pos": [10, 20],
                "size": [240, 120],
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": code_properties,
                "widgets_values": [],
            },
            {
                "id": 2,
                "type": "vibecomfy.loop",
                "pos": [300, 20],
                "size": [240, 120],
                "order": 1,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": loop_properties,
                "widgets_values": [],
            },
        ],
        "links": [],
        "groups": [],
    }

    workflow = convert_to_vibe_format(ui_graph)

    assert workflow.nodes["1"].metadata["_ui"]["properties"] == code_properties
    assert workflow.nodes["2"].metadata["_ui"]["properties"] == loop_properties
    assert workflow.nodes["1"].uid == "code-uid"
    assert workflow.nodes["2"].uid == "loop-uid"

    emitted = emit_ui_json(workflow)
    emitted_by_id = {node["id"]: node for node in emitted["nodes"]}

    for node_id, original in ((1, code_properties), (2, loop_properties)):
        emitted_properties = emitted_by_id[node_id]["properties"]
        assert emitted_properties["vibecomfy_uid"] == original["vibecomfy_uid"]
        assert emitted_properties["vibecomfy"] == original["vibecomfy"]
        assert emitted_properties["Node name for S&R"] == emitted_by_id[node_id]["type"]
        assert emitted_properties["vibecomfy_id"].startswith(f"{emitted_by_id[node_id]['type']}_")


def test_programmatic_intent_node_properties_export_with_stable_uid_and_typed_io() -> None:
    workflow = VibeWorkflow("programmatic-intent", WorkflowSource("programmatic-intent"))
    builder = workflow.node("vibecomfy.code", value="preview")
    properties = intent_node_properties(
        kind="code",
        uid=builder.node.uid,
        intent={"source": "value = preview"},
        inputs=[("prompt", "STRING")],
        outputs=[("image", "IMAGE")],
    )
    builder.node.metadata["_ui"] = {"properties": properties}

    emitted = emit_ui_json(workflow)
    node = next(item for item in emitted["nodes"] if item["type"] == "vibecomfy.code")

    assert node["properties"]["vibecomfy_uid"] == builder.node.uid
    assert node["properties"]["vibecomfy"]["io"] == {
        "inputs": [["prompt", "STRING"]],
        "outputs": [["image", "IMAGE"]],
    }
    assert workflow.nodes[builder.id].uid == builder.node.uid
