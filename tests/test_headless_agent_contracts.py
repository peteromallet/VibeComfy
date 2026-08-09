from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from vibecomfy.agent.contracts import HeadlessAgentRequest
from vibecomfy.executor.contracts import ExecutorRequest
from vibecomfy.executor.profiles import set_profile_override_dir


def test_headless_request_to_executor_request() -> None:
    headless = HeadlessAgentRequest(
        query="make it brighter",
        graph={"nodes": []},
        session_id="session-1",
        profile="default",
        idempotency_key="idem-1",
    )
    executor_request = headless.to_executor_request()
    assert isinstance(executor_request, ExecutorRequest)
    assert executor_request.query == "make it brighter"
    assert executor_request.graph == {"nodes": []}
    assert executor_request.session_id == "session-1"
    assert executor_request.profile == "default"
    assert executor_request.idempotency_key == "idem-1"
    assert {field.name for field in fields(executor_request)} == {
        "query",
        "graph",
        "workflow_id",
        "session_id",
        "profile",
        "idempotency_key",
        "client_graph_hash",
        "client_structural_graph_hash",
        "client_live_canvas_token",
        "expected_baseline_graph_hash",
        "expected_baseline_graph_hash_present",
        "on_demand_schemas",
    }


def test_headless_request_loads_workflow_path(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow = {"1": {"class_type": "SaveImage", "inputs": {"filename_prefix": "out"}}}
    workflow_path.write_text(json.dumps(workflow), encoding="utf-8")

    headless = HeadlessAgentRequest.from_payload({
        "query": "inspect this",
        "workflow_path": str(workflow_path),
    })

    assert headless.graph == workflow
    assert headless.to_executor_request().graph == workflow


def test_headless_request_accepts_workflow_alias(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps({"nodes": []}), encoding="utf-8")

    headless = HeadlessAgentRequest.from_payload({
        "query": "inspect this",
        "workflow": workflow_path,
    })

    assert headless.graph == {"nodes": []}


def test_headless_request_rejects_graph_and_workflow_path(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps({"nodes": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="either `graph` or `workflow_path`"):
        HeadlessAgentRequest.from_payload({
            "query": "inspect this",
            "graph": {"nodes": []},
            "workflow_path": str(workflow_path),
        })


def test_headless_request_rejects_invalid_workflow_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Workflow file not found"):
        HeadlessAgentRequest.from_payload({
            "query": "inspect this",
            "workflow_path": str(tmp_path / "missing.json"),
        })

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        HeadlessAgentRequest.from_payload({
            "query": "inspect this",
            "workflow_path": str(invalid_path),
        })

    array_path = tmp_path / "array.json"
    array_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON object"):
        HeadlessAgentRequest.from_payload({
            "query": "inspect this",
            "workflow_path": str(array_path),
        })


def test_headless_request_resolves_provider_kwargs_from_profile_spec(tmp_path: Path) -> None:
    profile_path = tmp_path / "custom.toml"
    profile_path.write_text(
        "\n".join([
            "[profiles.custom]",
            'classify = "hermes:openrouter:classify-model:low"',
            'research = "codex:gpt-5.5:medium"',
            'implement = "claude:claude-opus-4-7:high"',
            'reply = "hermes:openrouter:reply-model:low"',
        ]),
        encoding="utf-8",
    )
    set_profile_override_dir(tmp_path)
    try:
        headless = HeadlessAgentRequest(query="classify", profile="custom")
        assert headless.resolve_provider_readiness_kwargs() == {
            "route": "hermes",
            "model": "openrouter:classify-model",
        }
        assert headless.resolve_provider_readiness_kwargs(stage="implement") == {
            "route": "claude",
            "model": "claude-opus-4-7",
        }
    finally:
        set_profile_override_dir(None)


def test_headless_request_from_payload_round_trip() -> None:
    payload = {
        "query": "explain this graph",
        "graph": {"nodes": [{"id": 1}]},
        "session_id": "session-2",
        "profile": "speed",
        "idempotency_key": "idem-2",
        "output_dir": "/tmp/out",
        "live": False,
        "dry_run": True,
        "apply": True,
        "network": False,
        "timeout": 120.0,
        "extra": {"key": "value"},
    }
    headless = HeadlessAgentRequest.from_payload(payload)
    assert headless.query == "explain this graph"
    assert headless.graph == {"nodes": [{"id": 1}]}
    assert headless.session_id == "session-2"
    assert headless.profile == "speed"
    assert headless.idempotency_key == "idem-2"
    assert headless.output_dir_path == Path("/tmp/out")
    assert headless.live is False
    assert headless.dry_run is True
    assert headless.apply is True
    assert headless.network is False
    assert headless.timeout == 120.0
    assert headless.extra == {"key": "value"}
    assert headless.additive is False
    assert "additive" in headless.to_dict()
    assert headless.to_dict()["additive"] is False


def test_headless_request_defaults() -> None:
    headless = HeadlessAgentRequest(query="hello")
    assert headless.live is True
    assert headless.dry_run is False
    assert headless.apply is False
    assert headless.network is True
    assert headless.timeout is None
    assert headless.output_dir_path is None
    assert headless.graph is None
    assert headless.additive is False


def test_headless_request_additive_flag_round_trips() -> None:
    """The additive hint must survive to_dict/from_payload serialization.

    This is the contract the demo_factory remove_feature path relies on to
    tell the revise pipeline that the input graph's topology gap is the
    intended fault, not pre-existing damage.
    """
    headless = HeadlessAgentRequest(query="add the upscale back", additive=True)
    assert headless.additive is True
    payload = headless.to_dict()
    assert payload["additive"] is True
    restored = HeadlessAgentRequest.from_payload(payload)
    assert restored.additive is True
    # String "true" is accepted via the shared bool parser.
    restored_str = HeadlessAgentRequest.from_payload(
        {"query": "add it back", "additive": "true"}
    )
    assert restored_str.additive is True


def test_headless_request_rejects_non_bool_additive() -> None:
    with pytest.raises(ValueError, match="additive"):
        HeadlessAgentRequest(query="x", additive="yes please")  # type: ignore[arg-type]


def test_headless_request_requires_query() -> None:
    with pytest.raises(ValueError, match="non-empty string `query`"):
        HeadlessAgentRequest.from_payload({})
    with pytest.raises(ValueError, match="non-empty string `query`"):
        HeadlessAgentRequest.from_payload({"query": "   "})
    with pytest.raises(ValueError, match="non-empty string `query`"):
        HeadlessAgentRequest.from_payload({"query": 123})


def test_headless_request_validates_graph_type() -> None:
    with pytest.raises(ValueError, match="`graph` must be a dict or null"):
        HeadlessAgentRequest.from_payload({"query": "ok", "graph": [1, 2]})


def test_headless_request_validates_session_id_type() -> None:
    with pytest.raises(ValueError, match="`session_id` must be a string or null"):
        HeadlessAgentRequest.from_payload({"query": "ok", "session_id": 123})


def test_headless_request_validates_control_field_types() -> None:
    with pytest.raises(ValueError, match="`workflow_path` must be a string/Path or null"):
        HeadlessAgentRequest.from_payload({"query": "ok", "workflow_path": 123})
    with pytest.raises(ValueError, match="`output_dir` must be a string/Path or null"):
        HeadlessAgentRequest.from_payload({"query": "ok", "output_dir": 123})
    with pytest.raises(ValueError, match="`timeout` must be a number"):
        HeadlessAgentRequest.from_payload({"query": "ok", "timeout": "soon"})
    with pytest.raises(ValueError, match="`timeout` must be greater than zero"):
        HeadlessAgentRequest.from_payload({"query": "ok", "timeout": 0})
    with pytest.raises(ValueError, match="`live` must be a boolean"):
        HeadlessAgentRequest.from_payload({"query": "ok", "live": "sometimes"})
    with pytest.raises(ValueError, match="`extra` must be a mapping or null"):
        HeadlessAgentRequest.from_payload({"query": "ok", "extra": []})


def test_headless_request_to_dict_omits_none() -> None:
    headless = HeadlessAgentRequest(query="ok")
    payload = headless.to_dict()
    assert "graph" not in payload
    assert "session_id" not in payload
    assert "profile" not in payload
    assert "idempotency_key" not in payload
    assert "output_dir" not in payload
    assert "timeout" not in payload
    assert payload["query"] == "ok"
    assert payload["live"] is True
