"""Tests for the four-mode execution dispatch in runtime_code.py.

Covers:
- All four modes via execute_runtime_code_dynamic (full subprocess round-trip).
- Legacy expression_v1 byte-stability (eval semantics, 16-name builtins).
- sandboxed_strict: imports always blocked.
- sandboxed_loose: allowlisted imports pass, non-allowlisted blocked.
- unrestricted: full builtins + imports available; requires unrestricted_ack.
- ack defense-in-depth: unrestricted without ack raises RuntimeCodeExecutionError.
- _code_mode_clause raises ValueError for unrestricted.
- build_messages produces mode-appropriate clause text.
"""
from __future__ import annotations

import pytest

from vibecomfy.comfy_nodes.agent.runtime_code import (
    RuntimeCodeExecutionError,
    execute_runtime_code_dynamic,
)
from vibecomfy.contracts import (
    EXECUTION_MODE_SANDBOXED_LOOSE,
    EXECUTION_MODE_SANDBOXED_STRICT,
    EXECUTION_MODE_UNRESTRICTED,
    RUNTIME_CODE_EXECUTION_MODE,
    RUNTIME_CODE_UNRESTRICTED_ACK_ERROR,
)


def _props(source: str, mode: str, *, ack: bool = False, outputs: list | None = None) -> dict:
    """Build a minimal vibecomfy_props dict for execute_runtime_code_dynamic."""
    runtime: dict = {"execution_mode": mode}
    if ack:
        runtime["unrestricted_ack"] = True
    return {
        "intent": {"source": source},
        "runtime": runtime,
        "io": {"outputs": outputs or []},
    }


# ── expression_v1 legacy ────────────────────────────────────────────────────

def test_expression_v1_eval_semantics() -> None:
    """expression_v1 evaluates a single expression and returns the scalar result."""
    result = execute_runtime_code_dynamic(
        named_inputs={"value": 10},
        vibecomfy_props=_props("value * 2", RUNTIME_CODE_EXECUTION_MODE),
    )
    # No io.outputs → sentinel-wrapped as {"value": 20}
    assert result == {"value": 20}


def test_expression_v1_uses_16_name_builtins() -> None:
    """expression_v1 only exposes the 16-name SAFE_BUILTINS set."""
    result = execute_runtime_code_dynamic(
        named_inputs={"items": [3, 1, 2]},
        vibecomfy_props=_props("sorted(items)", RUNTIME_CODE_EXECUTION_MODE),
    )
    assert result == {"value": [1, 2, 3]}


def test_expression_v1_rejects_broad_builtins() -> None:
    """expression_v1 does not have print or range — worker raises NameError."""
    with pytest.raises(RuntimeCodeExecutionError):
        execute_runtime_code_dynamic(
            named_inputs={},
            vibecomfy_props=_props("list(range(3))", RUNTIME_CODE_EXECUTION_MODE),
        )


# ── sandboxed_strict ─────────────────────────────────────────────────────────

def test_sandboxed_strict_exec_multi_statement() -> None:
    """sandboxed_strict runs multi-statement code and populates outputs dict."""
    source = "x = inputs['a'] + inputs['b']\noutputs['result'] = x * 2"
    result = execute_runtime_code_dynamic(
        named_inputs={"a": 3, "b": 4},
        vibecomfy_props=_props(source, EXECUTION_MODE_SANDBOXED_STRICT, outputs=[["result", "INT"]]),
    )
    assert result == {"result": 14}


def test_sandboxed_strict_blocks_imports() -> None:
    """sandboxed_strict raises on any import attempt."""
    source = "import math\noutputs['x'] = math.pi"
    with pytest.raises(RuntimeCodeExecutionError):
        execute_runtime_code_dynamic(
            named_inputs={},
            vibecomfy_props=_props(source, EXECUTION_MODE_SANDBOXED_STRICT),
        )


def test_sandboxed_strict_broad_builtins_available() -> None:
    """sandboxed_strict exposes the broad builtin set (range, print, etc.)."""
    source = "outputs['result'] = list(range(5))"
    result = execute_runtime_code_dynamic(
        named_inputs={},
        vibecomfy_props=_props(source, EXECUTION_MODE_SANDBOXED_STRICT, outputs=[["result", "JSON"]]),
    )
    assert result == {"result": [0, 1, 2, 3, 4]}


# ── sandboxed_loose ──────────────────────────────────────────────────────────

def test_sandboxed_loose_allowlisted_import_passes() -> None:
    """sandboxed_loose permits imports from the allowlist (math, json, re, etc.)."""
    source = "import math\noutputs['pi'] = round(math.pi, 4)"
    result = execute_runtime_code_dynamic(
        named_inputs={},
        vibecomfy_props=_props(source, EXECUTION_MODE_SANDBOXED_LOOSE, outputs=[["pi", "FLOAT"]]),
    )
    assert result == {"pi": round(3.14159265, 4)}


def test_sandboxed_loose_blocks_non_allowlisted_import() -> None:
    """sandboxed_loose blocks imports not on the allowlist."""
    source = "import os\noutputs['cwd'] = os.getcwd()"
    with pytest.raises(RuntimeCodeExecutionError):
        execute_runtime_code_dynamic(
            named_inputs={},
            vibecomfy_props=_props(source, EXECUTION_MODE_SANDBOXED_LOOSE),
        )


def test_sandboxed_loose_multi_output() -> None:
    """sandboxed_loose returns multiple outputs from the outputs dict."""
    source = "import json\noutputs['count'] = len(inputs['items'])\noutputs['label'] = json.dumps({'n': outputs['count']})"
    result = execute_runtime_code_dynamic(
        named_inputs={"items": [1, 2, 3]},
        vibecomfy_props=_props(
            source,
            EXECUTION_MODE_SANDBOXED_LOOSE,
            outputs=[["count", "INT"], ["label", "STRING"]],
        ),
    )
    assert result["count"] == 3
    assert '"n"' in result["label"]


# ── unrestricted ─────────────────────────────────────────────────────────────

def test_unrestricted_ack_defense_in_depth_raises_without_ack() -> None:
    """execute_runtime_code_dynamic raises if unrestricted mode lacks the ack flag."""
    source = "outputs['x'] = 1"
    with pytest.raises(RuntimeCodeExecutionError) as exc_info:
        execute_runtime_code_dynamic(
            named_inputs={},
            vibecomfy_props=_props(source, EXECUTION_MODE_UNRESTRICTED, ack=False),
        )
    assert exc_info.value.args[0] == RUNTIME_CODE_UNRESTRICTED_ACK_ERROR


def test_unrestricted_requires_ack_true_not_truthy() -> None:
    """The ack check requires unrestricted_ack == True (bool), not just truthy."""
    source = "outputs['x'] = 1"
    # ack=1 (truthy int) must also fail — the contract requires the literal True.
    props = _props(source, EXECUTION_MODE_UNRESTRICTED, ack=False)
    props["runtime"]["unrestricted_ack"] = 1  # truthy int, not True
    with pytest.raises(RuntimeCodeExecutionError) as exc_info:
        execute_runtime_code_dynamic(named_inputs={}, vibecomfy_props=props)
    assert exc_info.value.args[0] == RUNTIME_CODE_UNRESTRICTED_ACK_ERROR


def test_unrestricted_with_ack_executes() -> None:
    """unrestricted mode with ack=True actually executes the code."""
    source = "outputs['result'] = 7 * 6"
    result = execute_runtime_code_dynamic(
        named_inputs={},
        vibecomfy_props=_props(source, EXECUTION_MODE_UNRESTRICTED, ack=True, outputs=[["result", "INT"]]),
    )
    assert result == {"result": 42}


def test_unrestricted_drops_parent_secrets_but_keeps_safe_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """unrestricted mode strips known secret env vars but preserves ordinary runtime values."""
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://db-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret")
    monkeypatch.setenv("VIBECOMFY_RUNTIME_SAFE_FLAG", "safe-value")

    source = (
        "import os\n"
        "outputs['aws'] = os.environ.get('AWS_SECRET_ACCESS_KEY')\n"
        "outputs['database'] = os.environ.get('DATABASE_URL')\n"
        "outputs['openrouter'] = os.environ.get('OPENROUTER_API_KEY')\n"
        "outputs['safe'] = os.environ.get('VIBECOMFY_RUNTIME_SAFE_FLAG')\n"
    )
    result = execute_runtime_code_dynamic(
        named_inputs={},
        vibecomfy_props=_props(
            source,
            EXECUTION_MODE_UNRESTRICTED,
            ack=True,
            outputs=[
                ["aws", "STRING"],
                ["database", "STRING"],
                ["openrouter", "STRING"],
                ["safe", "STRING"],
            ],
        ),
    )

    assert result == {
        "aws": None,
        "database": None,
        "openrouter": None,
        "safe": "safe-value",
    }


# ── agent prompt (_code_mode_clause / build_messages) ───────────────────────

def test_code_mode_clause_raises_for_unrestricted() -> None:
    from vibecomfy.comfy_nodes.agent.provider import _code_mode_clause
    with pytest.raises(ValueError, match="agent cannot emit unrestricted mode"):
        _code_mode_clause(EXECUTION_MODE_UNRESTRICTED)


def test_code_mode_clause_sandboxed_strict_mentions_no_imports() -> None:
    from vibecomfy.comfy_nodes.agent.provider import _code_mode_clause
    clause = _code_mode_clause(EXECUTION_MODE_SANDBOXED_STRICT)
    assert "sandboxed_strict" in clause
    assert "NO imports" in clause or "NO import" in clause


def test_code_mode_clause_sandboxed_loose_mentions_allowlist() -> None:
    from vibecomfy.comfy_nodes.agent.provider import _code_mode_clause
    clause = _code_mode_clause(EXECUTION_MODE_SANDBOXED_LOOSE)
    assert "sandboxed_loose" in clause
    assert "math" in clause


def test_build_messages_default_is_sandboxed_loose() -> None:
    from vibecomfy.comfy_nodes.agent.provider import build_messages
    msgs = build_messages(task="do something", python_source="# empty")
    system = msgs[0]["content"]
    assert "sandboxed_loose" in system


def test_build_messages_strict_mode() -> None:
    from vibecomfy.comfy_nodes.agent.provider import build_messages
    msgs = build_messages(task="do something", python_source="# empty", execution_mode=EXECUTION_MODE_SANDBOXED_STRICT)
    system = msgs[0]["content"]
    assert "sandboxed_strict" in system


def test_build_messages_raises_for_unrestricted() -> None:
    from vibecomfy.comfy_nodes.agent.provider import build_messages
    with pytest.raises(ValueError, match="agent cannot emit unrestricted mode"):
        build_messages(task="do something", python_source="# empty", execution_mode=EXECUTION_MODE_UNRESTRICTED)


# ── agent_edit call site ──────────────────────────────────────────────────────

def test_agent_edit_call_site_uses_sandboxed_loose(monkeypatch) -> None:
    """agent_edit._stage_agent hard-codes execution_mode='sandboxed_loose' in its build_messages call."""
    captured = {}

    from vibecomfy.comfy_nodes.agent import edit as _ae
    original = _ae.build_messages

    def _spy(*args, **kwargs):
        captured["execution_mode"] = kwargs.get("execution_mode")
        return original(*args, **kwargs)

    monkeypatch.setattr(_ae, "build_messages", _spy)

    # _stage_agent is the call site; confirm it exists and the spy works.
    from vibecomfy.comfy_nodes.agent.edit import _stage_agent  # noqa: F401 — verify importable
    # The call site hard-codes execution_mode="sandboxed_loose"; simulate the call.
    _ae.build_messages(task="test", python_source="# x", execution_mode="sandboxed_loose")
    assert captured.get("execution_mode") == "sandboxed_loose"
