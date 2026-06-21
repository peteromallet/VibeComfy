from __future__ import annotations

import importlib
import sys
import types

from vibecomfy.executor.contracts import ClassifyDecision, ExecutorResult, Report


def test_agent_executor_and_agent_edit_submit_share_executor_adapter(monkeypatch) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")

    registered = {}

    class _Routes:
        def post(self, path):
            def _decorator(fn):
                registered[("POST", path)] = fn
                return fn
            return _decorator

        def get(self, path):
            def _decorator(fn):
                registered[("GET", path)] = fn
                return fn
            return _decorator

    real_aiohttp = sys.modules.get("aiohttp")
    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.web = types.SimpleNamespace(
        json_response=lambda body, status=200: {"status": status, "body": body},
    )
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_module)

    captured = []
    to_thread_calls = []

    def _fake_run_executor(request, *, client_id=None):
        captured.append((request, client_id))
        return ExecutorResult.success(
            report=Report(plan=ClassifyDecision(route="revise", task="edit_graph")),
            graph={"nodes": [{"id": 1, "type": "PreviewImage"}], "links": []},
            reply="Changed the graph.",
        )

    async def _fake_to_thread(fn, /, *args, **kwargs):
        to_thread_calls.append(getattr(fn, "__name__", repr(fn)))
        return fn(*args, **kwargs)

    executor_core = importlib.import_module("vibecomfy.executor.core")
    monkeypatch.setattr(executor_core, "run_executor", _fake_run_executor)
    monkeypatch.setattr(routes.asyncio, "to_thread", _fake_to_thread)

    class _Request:
        def __init__(self, payload):
            self._payload = payload
            self.query = {}

        async def json(self):
            return self._payload

    try:
        routes.register_agent_edit_routes(types.SimpleNamespace(routes=_Routes()))

        assert ("POST", "/vibecomfy/agent-executor") in registered
        assert ("POST", "/vibecomfy/agent-edit") in registered
        assert ("POST", "/vibecomfy/agent-edit/accept") in registered

        executor_response = routes.asyncio.run(registered[("POST", "/vibecomfy/agent-executor")](
            _Request({"query": "add preview", "graph": {}, "session_id": "sess", "client_id": "client-a"})
        ))
        assert executor_response["status"] == 200
        assert captured[-1][0].query == "add preview"
        assert captured[-1][0].graph == {}
        assert captured[-1][0].session_id == "sess"
        assert captured[-1][1] == "client-a"
        assert to_thread_calls[-1] == "_handle_agent_executor_submit"
        assert executor_response["body"]["route"] == "revise"
        assert executor_response["body"]["apply_eligible"] is True
        assert executor_response["body"]["outcome"]["kind"] == "candidate"

        legacy_response = routes.asyncio.run(registered[("POST", "/vibecomfy/agent-edit")](
            _Request({"task": "legacy submit", "graph": {}, "client_id": "client-b"})
        ))
        assert legacy_response["status"] == 200
        assert captured[-1][0].query == "legacy submit"
        assert captured[-1][1] == "client-b"
        assert to_thread_calls[-1] == "_handle_agent_executor_submit"

        body = legacy_response["body"]
        assert body["route"] == "revise"
        assert body["reply"] == "Changed the graph."
        assert body["message"] == "Changed the graph."
        assert body["candidate"] == {"graph": body["graph"]}
        assert body["candidate_graph"] == body["graph"]
        assert body["apply_eligible"] is True
        assert body["apply_eligibility"]["applyable"] is True
        assert body["outcome"]["kind"] == "candidate"
    finally:
        if real_aiohttp is not None:
            sys.modules["aiohttp"] = real_aiohttp
        else:
            sys.modules.pop("aiohttp", None)
