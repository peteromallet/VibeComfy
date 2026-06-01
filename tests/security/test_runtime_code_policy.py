from __future__ import annotations

import pytest

from vibecomfy.contracts import (
    INTENT_CODE_MAX_BYTES,
    RUNTIME_CODE_CONTRACT_VERSION,
    RUNTIME_CODE_EXECUTION_MODE,
    RUNTIME_CODE_POLICY_VERSION,
    intent_node_properties,
    validate_runtime_code_contract,
)

# Runtime-backed intent code is fenced by the AST policy before any executor
# exists. Subprocess isolation is containment and JSON protocol enforcement, not
# the primary capability boundary.


def _runtime_contract() -> dict[str, object]:
    return {
        "runtime_backed": True,
        "runtime_contract_version": RUNTIME_CODE_CONTRACT_VERSION,
        "execution_mode": RUNTIME_CODE_EXECUTION_MODE,
        "timeout_ms": 1000,
        "max_source_bytes": INTENT_CODE_MAX_BYTES,
        "allowed_builtins": ["abs", "dict", "len", "max", "min", "round", "str", "sum"],
        "redaction_policy": ["source_hash_only", "closed_set_redaction"],
        "policy_version": RUNTIME_CODE_POLICY_VERSION,
        "passthrough_on_non_json": False,
    }


def _rejects_before_execution(source: str) -> set[str]:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-security-fixture",
        intent={"source": source},
        inputs=[("value", "JSON"), ("items", "JSON"), ("payload", "STRING")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract()},
    )

    result = validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=properties["vibecomfy"],
    )

    assert not result.ok
    assert result.normalized is None
    assert {
        problem.detail.get("phase")
        for problem in result.problems
        if problem.code
        in {
            "dunder_access",
            "forbidden_attribute",
            "forbidden_call",
            "forbidden_name",
            "forbidden_node",
            "forbidden_statement",
        }
    } == {"intent_node_validate"}
    return {problem.code for problem in result.problems}


@pytest.mark.parametrize(
    ("source", "expected_codes"),
    [
        pytest.param("open('/tmp/secret').read()", {"forbidden_call"}, id="filesystem-open-read"),
        pytest.param("pathlib.Path('/tmp/secret').read_text()", {"forbidden_call"}, id="filesystem-pathlib"),
        pytest.param("socket.create_connection(('127.0.0.1', 80))", {"forbidden_call"}, id="network-socket"),
        pytest.param("requests.get('https://example.invalid')", {"forbidden_call"}, id="network-requests"),
        pytest.param("urllib.request.urlopen('https://example.invalid')", {"forbidden_call"}, id="network-urllib"),
        pytest.param("subprocess.run(['python', '-c', 'print(1)'])", {"forbidden_call"}, id="subprocess-run"),
        pytest.param("os.system('id')", {"forbidden_call"}, id="subprocess-os-system"),
        pytest.param("os.environ['TOKEN']", {"forbidden_attribute"}, id="environment-os-environ"),
        pytest.param("getattr(os, 'environ')", {"forbidden_call"}, id="environment-dynamic-getattr"),
        pytest.param("importlib.import_module('os')", {"forbidden_call"}, id="importlib-import-module"),
        pytest.param("__import__('os').getcwd()", {"forbidden_call"}, id="dunder-import"),
        pytest.param("globals()['__builtins__']", {"forbidden_call"}, id="globals-builtins-escape"),
        pytest.param("__builtins__['eval']('1 + 1')", {"forbidden_call"}, id="builtins-eval-escape"),
        pytest.param("eval('1 + 1')", {"forbidden_call"}, id="eval-call"),
        pytest.param("exec('value = 1')", {"forbidden_call"}, id="exec-call"),
        pytest.param("compile('1 + 1', '<x>', 'eval')", {"forbidden_call"}, id="compile-call"),
        pytest.param("dir(value)", {"forbidden_call"}, id="dir-reflection"),
        pytest.param("vars(value)", {"forbidden_call"}, id="vars-reflection"),
        pytest.param("type(value)", {"forbidden_call"}, id="type-reflection"),
        pytest.param("inspect.signature(value)", {"forbidden_call"}, id="inspect-reflection"),
        pytest.param("value.__class__", {"dunder_access"}, id="dunder-class"),
        pytest.param("value.__dict__", {"dunder_access"}, id="dunder-dict"),
        pytest.param("value.__class__.__mro__", {"dunder_access"}, id="dunder-mro"),
        pytest.param("().__class__.__mro__[1].__subclasses__()", {"dunder_access", "forbidden_call"}, id="subclasses-chain"),
        pytest.param("pickle.loads(payload)", {"forbidden_call"}, id="pickle-loads"),
        pytest.param("marshal.loads(payload)", {"forbidden_call"}, id="marshal-loads"),
        pytest.param("jsonpickle.decode(payload)", {"forbidden_call"}, id="jsonpickle-decode"),
        pytest.param("lambda x: x", {"forbidden_node"}, id="lambda-node"),
        pytest.param("[x for x in items]", {"forbidden_node"}, id="comprehension-node"),
        pytest.param("import os", {"forbidden_statement"}, id="import-statement"),
    ],
)
def test_runtime_code_policy_rejects_forbidden_operations_before_subprocess_execution(
    source: str,
    expected_codes: set[str],
) -> None:
    assert _rejects_before_execution(source) & expected_codes


@pytest.mark.parametrize(
    "source",
    [
        "round(max(value['score'], 0) / 2, 2)",
        "{'count': len(items), 'label': str(payload), 'total': sum(items)}",
    ],
)
def test_runtime_code_policy_keeps_json_expression_subset_available(source: str) -> None:
    properties = intent_node_properties(
        kind="code",
        uid="runtime-security-allowed",
        intent={"source": source},
        inputs=[("value", "JSON"), ("items", "JSON"), ("payload", "STRING")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={"runtime": _runtime_contract()},
    )

    result = validate_runtime_code_contract(
        class_type="vibecomfy.code",
        payload=properties["vibecomfy"],
    )

    assert result.ok
    assert result.normalized is not None
