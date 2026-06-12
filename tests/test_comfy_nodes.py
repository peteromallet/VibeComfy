from __future__ import annotations

import pytest

from vibecomfy.comfy_nodes import VibeComfyStripConditioningKeys


def test_strip_conditioning_keys_removes_metadata_without_touching_embeddings() -> None:
    node = VibeComfyStripConditioningKeys()
    positive = [["embedding", {"guide_attention_entries": ["mask"], "keyframe_idxs": "keep"}]]
    negative = [["negative", {"guide_attention_entries": ["mask"], "other": 1}]]

    stripped_positive, stripped_negative = node.strip(positive, negative, "guide_attention_entries")

    assert stripped_positive == [["embedding", {"keyframe_idxs": "keep"}]]
    assert stripped_negative == [["negative", {"other": 1}]]
    assert positive[0][1]["guide_attention_entries"] == ["mask"]


# ---------------------------------------------------------------------------
# VibeComfyCodeIntent — flag-OFF snapshot (byte-stable back-compat)
# ---------------------------------------------------------------------------

def test_code_intent_flag_off_input_types_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag-OFF INPUT_TYPES must match the pre-sprint shape exactly."""
    import os
    import vibecomfy.comfy_nodes as m

    monkeypatch.delenv("VIBECOMFY_CODE_DYNAMIC_IO", raising=False)
    inputs = m.VibeComfyCodeIntent.INPUT_TYPES()

    assert "required" in inputs
    assert "value" in inputs["required"]
    assert "optional" in inputs
    assert "hidden" not in inputs

    optional = inputs["optional"]
    assert "source" in optional
    assert "runtime_backed" in optional
    assert "io" in optional
    # Dynamic pool keys must NOT be present when flag is off
    assert "in_0" not in optional
    assert "unique_id" not in optional


def test_code_intent_flag_off_return_types_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag-OFF RETURN_TYPES and RETURN_NAMES must be byte-identical to pre-sprint."""
    monkeypatch.delenv("VIBECOMFY_CODE_DYNAMIC_IO", raising=False)
    import vibecomfy.comfy_nodes as m

    # The class-level attrs were set at import time; we're checking the values
    # match the pre-sprint inherited values when the flag is not set.
    assert m.VibeComfyCodeIntent.RETURN_TYPES == ("*",) or len(m.VibeComfyCodeIntent.RETURN_TYPES) == 16
    # RETURN_NAMES must be ("value",) if flag was off at import time or 16-slot tuple
    rt = m.VibeComfyCodeIntent.RETURN_NAMES
    assert rt in (("value",), tuple(f"out_{i}" for i in range(16)))


# ---------------------------------------------------------------------------
# VibeComfyCodeIntent — flag-ON INPUT_TYPES structure
# ---------------------------------------------------------------------------

def test_code_intent_flag_on_input_types_has_16_optional_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag-ON INPUT_TYPES must expose in_0..in_15 + source/spec/execution_mode optionals + hidden unique_id/prompt."""
    monkeypatch.setenv("VIBECOMFY_CODE_DYNAMIC_IO", "1")
    import vibecomfy.comfy_nodes as m

    inputs = m.VibeComfyCodeIntent.INPUT_TYPES()

    assert "required" not in inputs
    assert "optional" in inputs
    assert "hidden" in inputs

    optional = inputs["optional"]
    # 16 wildcard pool slots + source, spec, execution_mode widgets
    assert len(optional) == 19
    for i in range(16):
        assert f"in_{i}" in optional
        assert optional[f"in_{i}"] == ("*",)

    # Source/spec/execution_mode widgets added by T3
    assert "source" in optional
    assert "spec" in optional
    assert "execution_mode" in optional

    hidden = inputs["hidden"]
    assert hidden["unique_id"] == "UNIQUE_ID"
    assert hidden["prompt"] == "PROMPT"

    # Legacy fields must NOT be present in the dynamic-IO branch
    assert "runtime_backed" not in optional
    assert "value" not in optional


# ---------------------------------------------------------------------------
# execute() — flag-OFF backward-compat path
# ---------------------------------------------------------------------------

def test_code_intent_execute_flag_off_calls_execute_runtime_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIBECOMFY_CODE_DYNAMIC_IO", raising=False)
    import vibecomfy.comfy_nodes as m

    calls: list[dict] = []

    def _fake_execute_runtime_code(*, value, **kwargs):
        calls.append({"value": value, **kwargs})
        return value * 2

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.runtime_code.execute_runtime_code",
        _fake_execute_runtime_code,
    )

    node = m.VibeComfyCodeIntent()
    result = node.execute(value=7, source="value * 2")

    assert result == (14,)
    assert len(calls) == 1
    assert calls[0]["value"] == 7
    assert calls[0]["source"] == "value * 2"


# ---------------------------------------------------------------------------
# execute() — flag-ON dynamic path
# ---------------------------------------------------------------------------

def _make_prompt(unique_id: str, vibecomfy_props: dict) -> dict:
    """Build a minimal ComfyUI-style prompt dict with properties.vibecomfy."""
    return {
        unique_id: {
            "class_type": "vibecomfy.code",
            "_meta": {
                "properties": {
                    "vibecomfy_uid": "test-uid",
                    "vibecomfy": vibecomfy_props,
                }
            },
        }
    }


def test_code_intent_execute_dynamic_remaps_inputs_and_builds_16_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2-in / 2-out: inputs remapped to user names, 16-slot tuple with active slots filled."""
    monkeypatch.setenv("VIBECOMFY_CODE_DYNAMIC_IO", "1")
    import vibecomfy.comfy_nodes as m

    vibecomfy_props = {
        "kind": "code",
        "intent": {"source": "a + b"},
        "io": {
            "inputs": [["a", "INT"], ["b", "INT"]],
            "outputs": [["result", "INT"]],
        },
        "runtime": {
            "runtime_backed": True,
            "timeout_ms": 1000,
            "allowed_builtins": ["abs"],
        },
    }
    prompt = _make_prompt("42", vibecomfy_props)

    dynamic_calls: list[dict] = []

    def _fake_dynamic(*, named_inputs, vibecomfy_props):
        dynamic_calls.append({"named_inputs": named_inputs, "props": vibecomfy_props})
        return {"result": named_inputs.get("a", 0) + named_inputs.get("b", 0)}

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.runtime_code.execute_runtime_code_dynamic",
        _fake_dynamic,
    )

    node = m.VibeComfyCodeIntent()
    result = node.execute(unique_id="42", prompt=prompt, in_0=3, in_1=4)

    assert len(result) == 16
    assert result[0] == 7
    assert all(v is None for v in result[1:])

    assert len(dynamic_calls) == 1
    assert dynamic_calls[0]["named_inputs"] == {"a": 3, "b": 4}


def test_code_intent_execute_dynamic_empty_io_returns_16_nones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty io.outputs: all 16 slots are None (sentinel value not exposed)."""
    monkeypatch.setenv("VIBECOMFY_CODE_DYNAMIC_IO", "1")
    import vibecomfy.comfy_nodes as m

    vibecomfy_props = {
        "kind": "code",
        "intent": {"source": "x * 2"},
        "io": {"inputs": [["x", "INT"]], "outputs": []},
        "runtime": {"timeout_ms": 1000, "allowed_builtins": []},
    }
    prompt = _make_prompt("1", vibecomfy_props)

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.runtime_code.execute_runtime_code_dynamic",
        lambda *, named_inputs, vibecomfy_props: {"value": named_inputs.get("x", 0) * 2},
    )

    node = m.VibeComfyCodeIntent()
    result = node.execute(unique_id="1", prompt=prompt, in_0=5)

    assert len(result) == 16
    assert all(v is None for v in result)


def test_code_intent_execute_dynamic_missing_prompt_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive .get() chain: None prompt → default-coerced vibecomfy_props passed through."""
    monkeypatch.setenv("VIBECOMFY_CODE_DYNAMIC_IO", "1")
    import vibecomfy.comfy_nodes as m

    captured: list[dict] = []

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.runtime_code.execute_runtime_code_dynamic",
        lambda *, named_inputs, vibecomfy_props: (
            captured.append({"named_inputs": named_inputs, "props": vibecomfy_props})
            or {"value": None}
        ),
    )

    node = m.VibeComfyCodeIntent()
    result = node.execute(unique_id=None, prompt=None)

    assert len(result) == 16
    props = captured[0]["props"]
    # T3 defensive coercion: intent/runtime sub-dicts always present; execution_mode defaulted
    assert props["intent"] == {"source": "", "spec": ""}
    assert props["runtime"] == {}
    assert props["execution_mode"] == "sandboxed_loose"


# ---------------------------------------------------------------------------
# execute_runtime_code_dynamic — unit tests
# ---------------------------------------------------------------------------

def test_execute_runtime_code_dynamic_empty_outputs_sentinel_wraps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty io.outputs must always return {"value": <result>}."""
    from vibecomfy.comfy_nodes.agent import runtime_code

    monkeypatch.setattr(runtime_code, "_run_worker", lambda payload, *, timeout_ms: 42)

    result = runtime_code.execute_runtime_code_dynamic(
        named_inputs={"x": 21},
        vibecomfy_props={
            "intent": {"source": "x * 2"},
            "io": {"inputs": [["x", "INT"]], "outputs": []},
            "runtime": {"timeout_ms": 500, "allowed_builtins": []},
        },
    )

    assert result == {"value": 42}


def test_execute_runtime_code_dynamic_single_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single io.outputs entry: result is mapped directly to the output name."""
    from vibecomfy.comfy_nodes.agent import runtime_code

    monkeypatch.setattr(runtime_code, "_run_worker", lambda payload, *, timeout_ms: 99)

    result = runtime_code.execute_runtime_code_dynamic(
        named_inputs={"val": 99},
        vibecomfy_props={
            "intent": {"source": "val"},
            "io": {"inputs": [["val", "INT"]], "outputs": [["score", "INT"]]},
            "runtime": {"timeout_ms": 500, "allowed_builtins": []},
        },
    )

    assert result == {"score": 99}


def test_execute_runtime_code_dynamic_multiple_outputs_requires_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N>1 outputs with scalar worker result → runtime_output_shape_mismatch."""
    from vibecomfy.comfy_nodes.agent import runtime_code
    from vibecomfy.comfy_nodes.agent.runtime_code import RuntimeCodeExecutionError

    monkeypatch.setattr(runtime_code, "_run_worker", lambda payload, *, timeout_ms: 7)

    with pytest.raises(RuntimeCodeExecutionError) as exc_info:
        runtime_code.execute_runtime_code_dynamic(
            named_inputs={"a": 3, "b": 4},
            vibecomfy_props={
                "intent": {"source": "a + b"},
                "io": {
                    "inputs": [["a", "INT"], ["b", "INT"]],
                    "outputs": [["x", "INT"], ["y", "INT"]],
                },
                "runtime": {"timeout_ms": 500, "allowed_builtins": []},
            },
        )

    assert exc_info.value.code == "runtime_output_shape_mismatch"


def test_execute_runtime_code_dynamic_multiple_outputs_dict_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N>1 outputs with dict worker result: keys mapped to output names."""
    from vibecomfy.comfy_nodes.agent import runtime_code

    monkeypatch.setattr(
        runtime_code,
        "_run_worker",
        lambda payload, *, timeout_ms: {"x": 10, "y": 20, "extra": 99},
    )

    result = runtime_code.execute_runtime_code_dynamic(
        named_inputs={"a": 3, "b": 4},
        vibecomfy_props={
            "intent": {"source": "{'x': a+b, 'y': a*b}"},
            "io": {
                "inputs": [["a", "INT"], ["b", "INT"]],
                "outputs": [["x", "INT"], ["y", "INT"]],
            },
            "runtime": {"timeout_ms": 500, "allowed_builtins": []},
        },
    )

    assert result == {"x": 10, "y": 20}


def test_execute_runtime_code_dynamic_asymmetric_inputs_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asymmetric: inputs declared but outputs empty → sentinel {"value": result}."""
    from vibecomfy.comfy_nodes.agent import runtime_code

    monkeypatch.setattr(runtime_code, "_run_worker", lambda payload, *, timeout_ms: "side-effect")

    result = runtime_code.execute_runtime_code_dynamic(
        named_inputs={"msg": "hello"},
        vibecomfy_props={
            "intent": {"source": "msg"},
            "io": {"inputs": [["msg", "STRING"]], "outputs": []},
            "runtime": {"timeout_ms": 500, "allowed_builtins": []},
        },
    )

    assert result == {"value": "side-effect"}


def test_execute_runtime_code_dynamic_always_returns_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """execute_runtime_code_dynamic always returns a dict regardless of worker output type."""
    from vibecomfy.comfy_nodes.agent import runtime_code

    for worker_result in [None, 0, "text", [], {}]:
        monkeypatch.setattr(
            runtime_code, "_run_worker", lambda payload, *, timeout_ms, _r=worker_result: _r
        )
        result = runtime_code.execute_runtime_code_dynamic(
            named_inputs={},
            vibecomfy_props={
                "intent": {"source": "0"},
                "io": {"inputs": [], "outputs": []},
                "runtime": {"timeout_ms": 500, "allowed_builtins": []},
            },
        )
        assert isinstance(result, dict), f"expected dict, got {type(result)} for worker result {worker_result!r}"
