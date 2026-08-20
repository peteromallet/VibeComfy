from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

from vibecomfy.comfy_nodes.agent.executor_durable import maybe_write_executor_only_durable_turn


def test_executor_durable_module_import_does_not_load_routes_edit_or_executor_core() -> None:
    code = """
import sys
import vibecomfy.comfy_nodes.agent.executor_durable
assert "vibecomfy.comfy_nodes.agent.routes" not in sys.modules
assert "vibecomfy.comfy_nodes.agent.edit" not in sys.modules
assert "vibecomfy.executor.core" not in sys.modules
"""

    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_applyable_executor_response_keeps_handle_agent_edit_durable_artifacts_delegated(tmp_path) -> None:
    calls: list[dict] = []
    response = {
        "ok": True,
        "route": "revise",
        "session_id": "sess-edit",
        "turn_id": "0001",
        "artifacts": {"response": "response.json", "chat": "chat.json"},
    }

    def fail_allocate_turn(**kwargs):
        calls.append(kwargs)
        raise AssertionError("applyable routes must not allocate executor-only durable turns")

    stamped = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload={"query": "make it brighter", "session_id": "sess-edit"},
        request=SimpleNamespace(query="make it brighter", graph={"nodes": []}),
        session_root=tmp_path,
        allocate_turn_func=fail_allocate_turn,
    )

    assert stamped is response
    assert calls == []
    assert not any(tmp_path.rglob("request.json"))
    assert not any(tmp_path.rglob("response.json"))
    assert not any(tmp_path.rglob("chat.json"))


def test_non_applyable_executor_response_writes_request_response_and_chat(tmp_path) -> None:
    request = SimpleNamespace(
        query="what does this workflow do?",
        graph={"nodes": [{"id": 1, "type": "LoadImage"}], "links": []},
    )
    response = {
        "ok": True,
        "route": "inspect",
        "reply": "It loads an image and previews it.",
        "message": "It loads an image and previews it.",
        "outcome": {"kind": "noop"},
    }

    stamped = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload={"query": request.query, "graph": request.graph, "session_id": "durable-test"},
        request=request,
        session_root=tmp_path,
    )

    session_id = stamped["session_id"]
    turn_id = stamped["turn_id"]
    turn_dir = tmp_path / session_id / "turns" / turn_id
    request_payload = json.loads((turn_dir / "request.json").read_text(encoding="utf-8"))
    response_payload = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
    chat_payload = json.loads((turn_dir / "chat.json").read_text(encoding="utf-8"))

    assert request_payload == {
        "query": request.query,
        "task": request.query,
        "session_id": session_id,
        "graph": request.graph,
    }
    assert response_payload["session_id"] == session_id
    assert response_payload["turn_id"] == turn_id
    assert response_payload["route"] == "inspect"
    assert response_payload["reply"] == response["reply"]
    assert response_payload["apply_eligible"] is False
    assert response_payload["graph_unchanged"] is True
    assert response_payload["no_candidate_reason"] == "route_not_applyable"
    assert chat_payload["session_id"] == session_id
    assert chat_payload["turn_id"] == turn_id
    assert chat_payload["route"] == "inspect"
    assert chat_payload["messages"][0]["text"] == request.query
    assert chat_payload["messages"][1]["text"] == response["reply"]
    original_ui = json.loads((turn_dir / "original.ui.json").read_text(encoding="utf-8"))
    final_ui = json.loads((turn_dir / "final.ui.json").read_text(encoding="utf-8"))
    assert original_ui == request.graph
    assert final_ui == original_ui


# ══════════════════════════════════════════════════════════════════════════════
# T15: Duplicate idempotency — work executed at most once
# ══════════════════════════════════════════════════════════════════════════════


def test_duplicate_idempotency_key_returns_cached_response_no_new_turn(
    tmp_path,
) -> None:
    """Two requests with the same idempotency key must return the cached
    response without allocating a second turn."""
    idempotency_key = "idem-dup-001"
    request = SimpleNamespace(
        query="what does this workflow do?",
        graph={"nodes": [{"id": 1, "type": "LoadImage"}], "links": []},
    )
    response = {
        "ok": True,
        "route": "inspect",
        "reply": "It loads an image and previews it.",
        "message": "It loads an image and previews it.",
        "outcome": {"kind": "noop"},
    }

    # First call — should allocate a turn and write artifacts
    first = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload={
            "query": request.query,
            "graph": request.graph,
            "session_id": "durable-idem-test",
            "idempotency_key": idempotency_key,
        },
        request=request,
        session_root=tmp_path,
    )
    assert first["idempotency_key"] == idempotency_key
    first_turn_id = first["turn_id"]
    first_session_id = first["session_id"]
    assert isinstance(first_turn_id, str) and first_turn_id

    # Second call with same key — must return the cached response
    second = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload={
            "query": request.query,
            "graph": request.graph,
            "session_id": first_session_id,
            "idempotency_key": idempotency_key,
        },
        request=request,
        session_root=tmp_path,
    )
    # Must return the same turn_id (idempotent replay)
    assert second["turn_id"] == first_turn_id, (
        f"Duplicate idempotency key allocated new turn: "
        f"{first_turn_id} → {second['turn_id']}"
    )
    assert second["session_id"] == first_session_id
    assert second.get("idempotency_key") == idempotency_key

    # Only one turn directory should exist
    turn_dirs = list((tmp_path / first_session_id / "turns").iterdir())
    assert len(turn_dirs) == 1, (
        f"Expected 1 turn dir, found {len(turn_dirs)}: {turn_dirs}"
    )


def test_duplicate_idempotency_does_not_repeat_provider_work(
    tmp_path,
) -> None:
    """A duplicate idempotent request must not re-execute provider/edit
    work — the cached response is returned directly without creating
    a second turn directory."""
    idempotency_key = "idem-provider-001"

    from vibecomfy.comfy_nodes.agent.session import record_idempotent_response

    request = SimpleNamespace(
        query="test idempotency",
        graph={"nodes": [{"id": 1, "type": "PreviewImage"}], "links": []},
    )
    response = {
        "ok": True,
        "route": "research",
        "reply": "Research result.",
        "message": "Research result.",
        "outcome": {"kind": "noop"},
    }
    payload = {
        "query": request.query,
        "graph": request.graph,
        "session_id": "idem-provider-sess",
        "idempotency_key": idempotency_key,
    }

    # First call — allocates a turn and writes artifacts
    first = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload=payload,
        request=request,
        session_root=tmp_path,
        record_idempotent_response_func=record_idempotent_response,
    )
    first_turn_id = first["turn_id"]
    first_session_id = first["session_id"]
    assert isinstance(first_turn_id, str) and first_turn_id

    # Verify first call created a turn directory
    turn_dirs_after_first = list(
        (tmp_path / first_session_id / "turns").iterdir()
    )
    assert len(turn_dirs_after_first) == 1

    # Second call — must replay without creating a new turn
    second_payload = dict(payload)
    second_payload["session_id"] = first_session_id
    second = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload=second_payload,
        request=request,
        session_root=tmp_path,
        record_idempotent_response_func=record_idempotent_response,
    )
    # Same turn_id returned (idempotent replay)
    assert second["turn_id"] == first_turn_id, (
        f"Duplicate idempotency call allocated new turn: "
        f"{first_turn_id} → {second['turn_id']}"
    )
    assert second["session_id"] == first_session_id

    # Only ONE turn directory — no new turn was allocated
    turn_dirs_after_second = list(
        (tmp_path / first_session_id / "turns").iterdir()
    )
    assert len(turn_dirs_after_second) == 1, (
        f"Duplicate idempotency call created a new turn dir: "
        f"expected 1, found {len(turn_dirs_after_second)}"
    )


def test_different_idempotency_keys_allocate_distinct_turns(
    tmp_path,
) -> None:
    """Two requests with different idempotency keys must allocate
    distinct turns (no false idempotency collision)."""
    request = SimpleNamespace(
        query="test",
        graph={"nodes": [{"id": 1, "type": "LoadImage"}], "links": []},
    )
    response = {
        "ok": True,
        "route": "inspect",
        "reply": "OK.",
        "message": "OK.",
        "outcome": {"kind": "noop"},
    }
    session_id = "distinct-keys-sess"

    first = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload={
            "query": request.query,
            "graph": request.graph,
            "session_id": session_id,
            "idempotency_key": "key-a",
        },
        request=request,
        session_root=tmp_path,
    )

    second = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload={
            "query": request.query,
            "graph": request.graph,
            "session_id": session_id,
            "idempotency_key": "key-b",
        },
        request=request,
        session_root=tmp_path,
    )

    assert first["turn_id"] != second["turn_id"], (
        "Different idempotency keys must allocate different turns"
    )
    # Both should have distinct turn directories
    turn_dirs = list((tmp_path / session_id / "turns").iterdir())
    assert len(turn_dirs) == 2, (
        f"Expected 2 distinct turn dirs, found {len(turn_dirs)}"
    )
