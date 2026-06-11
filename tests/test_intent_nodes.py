from __future__ import annotations

import pytest

from vibecomfy.contracts import (
    INTENT_CODE_MAX_BYTES,
    INTENT_LOOP_MAX_ITERATIONS,
    INTENT_NODE_CONTRACT_INVALID_CODE,
    INTENT_NODE_EDITOR_ONLY_CODE,
    RUNTIME_CODE_CONTRACT_VERSION,
    RUNTIME_CODE_EXECUTION_MODE,
    RUNTIME_CODE_POLICY_VERSION,
    intent_node_payload_from_metadata,
    intent_node_properties,
    intent_node_properties_from_metadata,
    is_intent_class_type,
    validate_intent_node_contract,
    validate_runtime_code_contract,
)
from vibecomfy.contracts.intent_nodes import INTENT_SPEC_MAX_BYTES
from vibecomfy.contracts.validation import comfyui_node_issue_specs
from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema.provider import NodeSchema, schema_for
from vibecomfy.schema.validate import sanitize_api_against_schema, validate_api_against_schema
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _metadata(properties: dict[str, object]) -> dict[str, object]:
    return {"_ui": {"properties": properties}}


def _runtime_contract(**overrides: object) -> dict[str, object]:
    contract: dict[str, object] = {
        "runtime_backed": True,
        "runtime_contract_version": RUNTIME_CODE_CONTRACT_VERSION,
        "execution_mode": RUNTIME_CODE_EXECUTION_MODE,
        "timeout_ms": 1000,
        "max_source_bytes": INTENT_CODE_MAX_BYTES,
        "allowed_builtins": ["abs", "len", "min", "max", "round"],
        "redaction_policy": ["source_hash_only", "closed_set_redaction"],
        "policy_version": RUNTIME_CODE_POLICY_VERSION,
        "passthrough_on_non_json": False,
    }
    contract.update(overrides)
    return contract


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
    assert "1" not in workflow.compile("api")


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
    assert "2" not in workflow.compile("api")


def test_is_intent_class_type_only_matches_known_vibecomfy_intents() -> None:
    assert is_intent_class_type("vibecomfy.code") is True
    assert is_intent_class_type("vibecomfy.loop") is True
    assert is_intent_class_type("vibecomfy.exec") is False


def test_compile_materializes_valid_runtime_backed_code_as_queue_visible_inputs() -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": "value + 1", "spec": "increment"},
        inputs=[("value", "INT")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract(timeout_ms=250, max_source_bytes=128)},
    )
    workflow = VibeWorkflow("runtime-intent", WorkflowSource("runtime-intent"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.code",
        inputs={"value": 41},
        metadata=_metadata(properties),
    )

    compiled = workflow.compile("api")

    assert compiled["1"]["class_type"] == "vibecomfy.code"
    assert compiled["1"]["inputs"] == {
        "value": 41,
        "runtime_backed": True,
        "runtime_contract_version": RUNTIME_CODE_CONTRACT_VERSION,
        "execution_mode": RUNTIME_CODE_EXECUTION_MODE,
        "timeout_ms": 250,
        "max_source_bytes": 128,
        "allowed_builtins": ["abs", "len", "min", "max", "round"],
        "redaction_policy": ["source_hash_only", "closed_set_redaction"],
        "policy_version": RUNTIME_CODE_POLICY_VERSION,
        "passthrough_on_non_json": False,
        "vibecomfy_uid": "runtime-code",
        "kind": "code",
        "io": {"inputs": [["value", "INT"]], "outputs": [["result", "JSON"]]},
        "source": "value + 1",
        "spec": "increment",
    }


def test_attempt_bundle_redacts_runtime_source_and_records_contract_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.runtime import attempt as attempt_module

    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": "value + 1", "spec": "increment"},
        inputs=[("value", "INT")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract(timeout_ms=250, max_source_bytes=128)},
    )
    workflow = VibeWorkflow("runtime-intent", WorkflowSource("runtime-intent"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.code",
        inputs={"value": 41},
        metadata=_metadata(properties),
    )
    api = workflow.compile("api")
    monkeypatch.setattr(attempt_module, "_collect_drift_for_bundle", lambda workflow: {})

    bundle = attempt_module.build_attempt_bundle(workflow, api, backend="api")

    compiled_source = bundle["compiled_prompt"]["1"]["inputs"]["source"]
    runtime_entry = bundle["runtime_intent_nodes"][0]
    assert compiled_source["redacted"] is True
    assert compiled_source["byte_count"] == len("value + 1")
    assert "value + 1" not in repr(bundle)
    assert bundle["node_lookups"]["1"]["class_type"] == "vibecomfy.code"
    assert runtime_entry["source_hash"] == compiled_source["sha256"]
    assert runtime_entry["resource_limits"] == {"timeout_ms": 250, "max_source_bytes": 128}
    assert runtime_entry["redaction"] == {
        "policy": ["source_hash_only", "closed_set_redaction"],
        "status": "source_hash_only",
    }
    assert "runtime_source" in bundle["redactions"]


def test_schema_sanitize_preserves_runtime_backed_code_inputs() -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": "value + 1", "spec": "increment"},
        inputs=[("value", "INT")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract(timeout_ms=250, max_source_bytes=128)},
    )
    workflow = VibeWorkflow("runtime-intent", WorkflowSource("runtime-intent"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.code",
        inputs={"value": 41},
        metadata=_metadata(properties),
    )
    api = workflow.compile("api")

    class StrictProvider:
        def schemas(self) -> dict[str, NodeSchema]:
            return {"KnownNode": NodeSchema("KnownNode", None, {}, [])}

        def get_schema(self, class_type: str) -> None:
            return None

    sanitized = sanitize_api_against_schema(api, StrictProvider())
    issues = validate_api_against_schema(sanitized, StrictProvider())

    assert sanitized["1"]["inputs"] == api["1"]["inputs"]
    assert issues == []
    schema = schema_for(StrictProvider(), "vibecomfy.code")
    assert schema is not None
    assert schema.source_provider == "vibecomfy_builtin"
    assert schema.confidence == 1.0


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


def test_validate_runtime_code_contract_normalizes_valid_runtime_backed_metadata() -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": "value + 1"},
        inputs=[("value", "INT")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract(timeout_ms=250, max_source_bytes=128)},
    )

    result = validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=properties["vibecomfy"],
    )

    assert result.ok
    assert result.normalized is not None
    assert result.normalized.as_dict() == {
        "runtime_backed": True,
        "runtime_contract_version": RUNTIME_CODE_CONTRACT_VERSION,
        "execution_mode": RUNTIME_CODE_EXECUTION_MODE,
        "timeout_ms": 250,
        "max_source_bytes": 128,
        "allowed_builtins": ["abs", "len", "min", "max", "round"],
        "redaction_policy": ["source_hash_only", "closed_set_redaction"],
        "policy_version": RUNTIME_CODE_POLICY_VERSION,
        "passthrough_on_non_json": False,
    }
    assert validate_intent_node_contract(
        node_id="1",
        class_type="vibecomfy.code",
        metadata=_metadata(properties),
    ).ok


def test_validate_runtime_code_contract_reports_missing_runtime_block_when_required() -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": "value + 1"},
        inputs=[("value", "INT")],
        outputs=[("result", "JSON")],
    )

    result = validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=properties["vibecomfy"],
    )

    assert not result.ok
    assert {problem.code for problem in result.problems} == {"missing_runtime_contract"}


def test_validate_runtime_code_contract_rejects_unsupported_execution_mode() -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": "value + 1"},
        inputs=[("value", "INT")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract(execution_mode="function_body_v1")},
    )

    result = validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=properties["vibecomfy"],
    )

    assert not result.ok
    assert {problem.code for problem in result.problems} == {"unsupported_execution_mode"}


def test_validate_runtime_code_contract_rejects_source_over_runtime_limit() -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": "value + 1"},
        inputs=[("value", "INT")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract(max_source_bytes=3)},
    )

    result = validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=properties["vibecomfy"],
    )

    assert not result.ok
    assert {problem.code for problem in result.problems} == {"runtime_source_too_large"}


def test_validate_runtime_code_contract_rejects_non_json_io_declarations() -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": "pixels"},
        inputs=[("pixels", "IMAGE"), ("latent", "LATENT")],
        outputs=[("result", "*")],
        extra_vibecomfy={"runtime": _runtime_contract()},
    )

    result = validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=properties["vibecomfy"],
    )

    assert not result.ok
    assert {problem.code for problem in result.problems} == {"runtime_non_json_io"}


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        pytest.param("import os", "forbidden_statement", id="import-statement"),
        pytest.param("value = 1", "forbidden_statement", id="assignment-statement"),
        pytest.param("eval('1')", "forbidden_call", id="eval-call"),
        pytest.param("exec('value')", "forbidden_call", id="exec-call"),
        pytest.param("open('/tmp/x').read()", "forbidden_call", id="file-open-call"),
        pytest.param("__import__('os')", "forbidden_call", id="import-reflection-call"),
        pytest.param("getattr(value, 'x')", "forbidden_call", id="dynamic-attribute-call"),
        pytest.param("value.__class__", "dunder_access", id="dunder-attribute"),
        pytest.param("os.environ", "forbidden_attribute", id="environment-api"),
        pytest.param("subprocess.run(['true'])", "forbidden_call", id="process-api"),
        pytest.param("socket.create_connection(['localhost', 80])", "forbidden_call", id="network-api"),
        pytest.param("inspect.signature(value)", "forbidden_call", id="reflection-api"),
    ],
)
def test_runtime_code_contract_rejects_forbidden_expression_policy_before_execution(
    source: str,
    expected_code: str,
) -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": source},
        inputs=[("value", "JSON")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract()},
    )

    result = validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=properties["vibecomfy"],
    )

    assert not result.ok
    assert expected_code in {problem.code for problem in result.problems}
    assert {problem.detail.get("phase") for problem in result.problems if problem.code == expected_code} == {
        "intent_node_validate"
    }


def test_runtime_code_contract_allows_declared_json_expression_subset() -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-code",
        intent={"source": "round(max(value, 1) / 2, 2)"},
        inputs=[("value", "FLOAT")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract(allowed_builtins=["round", "max"])},
    )

    result = validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=properties["vibecomfy"],
    )

    assert result.ok


def test_legacy_editor_only_code_and_loop_metadata_remain_valid_without_runtime_contract() -> None:
    code_properties = intent_node_properties(
        kind="code",
        uid="editor-code",
        intent={"source": "value = 1"},
        inputs=[("prompt", "STRING")],
        outputs=[("image", "IMAGE")],
    )
    loop_properties = intent_node_properties(
        kind="loop",
        uid="editor-loop",
        intent={"var": "seed", "count": 2},
        inputs=[("image", "IMAGE")],
        outputs=[("image", "IMAGE")],
    )

    code_result = validate_intent_node_contract(
        node_id="1",
        class_type="vibecomfy.code",
        metadata=_metadata(code_properties),
    )
    loop_result = validate_intent_node_contract(
        node_id="2",
        class_type="vibecomfy.loop",
        metadata=_metadata(loop_properties),
    )

    assert code_result.ok
    assert loop_result.ok
    assert validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=code_properties["vibecomfy"],
        require_runtime=False,
    ).ok


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
        assert node_cls.VIBECOMFY_INTENT_KIND == kind
        assert node_cls.VIBECOMFY_EDITOR_ONLY is True
        assert node_cls.VIBECOMFY_LOWERED is False
        inputs = node_cls.INPUT_TYPES()
        assert inputs["required"] == {"value": ("*",)}
        if kind == "code":
            assert node_cls.FUNCTION == "execute"
            assert node_cls.VIBECOMFY_RUNTIME_BACKED is True
            assert {"runtime_backed", "source", "spec", "io"} <= set(inputs["optional"])
        else:
            assert node_cls.FUNCTION == "passthrough"
            assert node_cls.VIBECOMFY_RUNTIME_BACKED is False
            assert "optional" not in inputs
            assert node_cls().passthrough(
                "sentinel",
                source=source_payload,
                spec=spec_payload,
            ) == ("sentinel",)


def test_exec_node_registered_and_not_intent() -> None:
    from vibecomfy.comfy_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    from vibecomfy.comfy_nodes.exec_node import EXEC_CLASS_TYPE, EXEC_SLOT_COUNT, VibeComfyExec

    # --- constants ----------------------------------------------------------
    assert EXEC_CLASS_TYPE == "vibecomfy.exec"
    assert EXEC_SLOT_COUNT == 16

    # --- registration -------------------------------------------------------
    assert EXEC_CLASS_TYPE in NODE_CLASS_MAPPINGS
    assert NODE_CLASS_MAPPINGS[EXEC_CLASS_TYPE] is VibeComfyExec
    assert NODE_DISPLAY_NAME_MAPPINGS[EXEC_CLASS_TYPE] == "VibeComfy Exec"

    # --- classification: NOT an intent node --------------------------------
    assert VibeComfyExec.VIBECOMFY_INTENT_NODE is False
    from vibecomfy.contracts.intent_nodes import is_intent_class_type

    assert is_intent_class_type(EXEC_CLASS_TYPE) is False

    # --- classification: NOT in UI-only / helper class sets -----------------
    from vibecomfy._compile._helpers import (
        UI_ONLY_CLASS_TYPES,
        BROADCAST_HELPER_CLASS_TYPES,
        HELPER_CLASS_TYPES,
        is_ui_only_class_type,
        is_helper_class_type,
    )

    assert EXEC_CLASS_TYPE not in UI_ONLY_CLASS_TYPES
    assert EXEC_CLASS_TYPE not in BROADCAST_HELPER_CLASS_TYPES
    assert EXEC_CLASS_TYPE not in HELPER_CLASS_TYPES
    assert is_ui_only_class_type(EXEC_CLASS_TYPE) is False
    assert is_helper_class_type(EXEC_CLASS_TYPE) is False

    # --- node spec ----------------------------------------------------------
    assert VibeComfyExec.CATEGORY == "vibecomfy/exec"
    assert VibeComfyExec.FUNCTION == "execute"
    assert VibeComfyExec.RETURN_TYPES == tuple(["*"] * EXEC_SLOT_COUNT)
    assert VibeComfyExec.RETURN_NAMES == tuple(f"out_{i}" for i in range(EXEC_SLOT_COUNT))
    assert VibeComfyExec.VIBECOMFY_EDITOR_ONLY is False
    assert VibeComfyExec.VIBECOMFY_RUNTIME_BACKED is False
    assert VibeComfyExec.VIBECOMFY_LOWERED is False

    input_types = VibeComfyExec.INPUT_TYPES()
    assert set(input_types["required"]) == {"source", "io"}
    assert input_types["required"]["source"] == ("STRING", {"default": "", "multiline": True})
    assert input_types["required"]["io"] == ("JSON",)

    optional_keys = set(input_types["optional"])
    assert optional_keys == {f"in_{i}" for i in range(EXEC_SLOT_COUNT)}
    for i in range(EXEC_SLOT_COUNT):
        assert input_types["optional"][f"in_{i}"] == ("*",)

    # --- execute path: declared outputs padded to fixed arity ---------------
    instance = VibeComfyExec()
    result = instance.execute(
        source="return {'result': value + 1}",
        io={"inputs": [["value", "INT"]], "outputs": [["result", "INT"]]},
        in_0=41,
        in_5="ignored",
    )
    assert result == (42,) + tuple([None] * (EXEC_SLOT_COUNT - 1))
    assert len(result) == EXEC_SLOT_COUNT

    # --- execute path: empty body defaults to empty dict / padded outputs ---
    result_empty = instance.execute(io={"outputs": []})
    assert result_empty == tuple([None] * EXEC_SLOT_COUNT)


def test_exec_node_survives_compile_api() -> None:
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    workflow = VibeWorkflow("exec-compile", WorkflowSource("exec-compile"))
    workflow.nodes["10"] = VibeNode(
        "10",
        "vibecomfy.exec",
        inputs={"in_0": ["20", 0], "source": "return 42"},
        widgets={"io": {}},
    )
    workflow.nodes["20"] = VibeNode("20", "CheckpointLoaderSimple", inputs={"ckpt_name": "model.safetensors"})
    workflow.edges = []

    compiled = workflow.compile("api")

    assert "10" in compiled
    assert compiled["10"]["class_type"] == "vibecomfy.exec"
    assert compiled["10"]["inputs"] == {"in_0": ["20", 0], "source": "return 42", "io": {}}


def test_exec_node_has_builtin_schema_and_widget_aliases() -> None:
    from vibecomfy._compile._widgets import WIDGET_SCHEMA
    from vibecomfy.schema.provider import schema_for

    schema = schema_for(None, "vibecomfy.exec")

    assert schema is not None
    assert schema.source_provider == "vibecomfy_builtin"
    assert list(schema.inputs)[:2] == ["source", "io"]
    assert {f"in_{index}" for index in range(16)} <= set(schema.inputs)
    assert [output.name for output in schema.outputs] == [f"out_{index}" for index in range(16)]
    assert WIDGET_SCHEMA["vibecomfy.exec"] == ["source", "io"]


def test_runtime_code_executor_returns_json_result_from_child_process() -> None:
    from vibecomfy.comfy_nodes.agent.runtime_code import execute_runtime_code

    result = execute_runtime_code(
        value=2,
        source="max(value + 3, 4)",
        io={"inputs": [["value", "INT"]], "outputs": [["result", "JSON"]]},
        runtime_backed=True,
        runtime_contract_version=RUNTIME_CODE_CONTRACT_VERSION,
        execution_mode=RUNTIME_CODE_EXECUTION_MODE,
        timeout_ms=1000,
        max_source_bytes=128,
        allowed_builtins=["max"],
        redaction_policy=["source_hash_only"],
        policy_version=RUNTIME_CODE_POLICY_VERSION,
        passthrough_on_non_json=False,
    )

    assert result == 5


def test_runtime_code_executor_rejects_non_json_inputs_and_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.comfy_nodes.agent import runtime_code
    from vibecomfy.comfy_nodes.agent.runtime_code import RuntimeCodeExecutionError, execute_runtime_code

    with pytest.raises(RuntimeCodeExecutionError, match="runtime_input_not_json"):
        execute_runtime_code(
            value=float("nan"),
            source="value",
            io={"inputs": [["value", "FLOAT"]], "outputs": [["result", "JSON"]]},
            runtime_backed=True,
            runtime_contract_version=RUNTIME_CODE_CONTRACT_VERSION,
            execution_mode=RUNTIME_CODE_EXECUTION_MODE,
            timeout_ms=1000,
            max_source_bytes=128,
            allowed_builtins=[],
            redaction_policy=["source_hash_only"],
            policy_version=RUNTIME_CODE_POLICY_VERSION,
            passthrough_on_non_json=False,
        )

    monkeypatch.setattr(
        runtime_code,
        "_WORKER_SOURCE",
        "import sys\nsys.stdout.write('not-json')\n",
    )
    with pytest.raises(RuntimeCodeExecutionError, match="runtime_protocol_non_json"):
        runtime_code._run_worker(
            {"source": "value", "value": 1, "inputs": {"value": 1}, "allowed_builtins": []},
            timeout_ms=1000,
        )


def test_runtime_code_executor_enforces_timeout_and_scrubbed_child_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from vibecomfy.comfy_nodes.agent import runtime_code
    from vibecomfy.comfy_nodes.agent.runtime_code import RuntimeCodeExecutionError

    monkeypatch.setenv("VIBECOMFY_RUNTIME_TEST_SECRET", "leak")
    monkeypatch.setattr(
        runtime_code,
        "_WORKER_SOURCE",
        "import json, os, sys\n"
        "sys.stdout.write(json.dumps({'ok': True, 'result': {"
        "'pid': os.getpid(), "
        "'parent_secret': os.environ.get('VIBECOMFY_RUNTIME_TEST_SECRET'), "
        "'cwd': os.getcwd()}}))\n",
    )

    result = runtime_code._run_worker(
        {"source": "value", "value": 1, "inputs": {"value": 1}, "allowed_builtins": []},
        timeout_ms=1000,
    )

    assert result["pid"] != os.getpid()
    assert result["parent_secret"] is None
    assert os.path.basename(result["cwd"]).startswith("vibecomfy-runtime-code-")

    monkeypatch.setattr(runtime_code, "_WORKER_SOURCE", "import time\ntime.sleep(1)\n")
    with pytest.raises(RuntimeCodeExecutionError, match="runtime_timeout"):
        runtime_code._run_worker(
            {"source": "value", "value": 1, "inputs": {"value": 1}, "allowed_builtins": []},
            timeout_ms=10,
        )


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


@pytest.mark.comfy
@pytest.mark.info
def test_runtime_backed_code_embedded_queue_smoke() -> None:
    """Opt-in live ComfyUI smoke: prove the runtime-backed node queues successfully."""
    import importlib.util
    import json
    import os
    from pathlib import Path

    if os.environ.get("VIBECOMFY_RUNTIME_CODE_SMOKE") != "1":
        pytest.skip("runtime-backed ComfyUI smoke is opt-in (set VIBECOMFY_RUNTIME_CODE_SMOKE=1)")
    if importlib.util.find_spec("comfy.client.embedded_comfy_client") is None:
        pytest.skip("embedded ComfyUI runtime is unavailable for the live smoke test")

    from vibecomfy.runtime import run_embedded_sync

    properties = intent_node_properties(
        kind="code",
        uid="runtime-code-live",
        intent={"source": "value + 1", "spec": "increment"},
        inputs=[("value", "INT")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract(timeout_ms=1000, max_source_bytes=128)},
    )
    workflow = VibeWorkflow("runtime-intent-live", WorkflowSource("runtime-intent-live"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.code",
        inputs={"value": 41},
        metadata=_metadata(properties),
    )

    result = run_embedded_sync(workflow)

    assert result.prompt_id is not None
    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    assert metadata["runtime"] == "embedded"
    assert metadata["queued"]
