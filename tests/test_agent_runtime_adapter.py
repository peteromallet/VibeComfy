from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from vibecomfy.comfy_nodes.agent import runtime
from vibecomfy.comfy_nodes.agent import provider as agent_provider
from vibecomfy.comfy_nodes.agent import worker
from vibecomfy.executor.agent_backend import run_classify_turn, run_reply_turn


def test_openrouter_agent_kwargs_use_openrouter_model_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    kwargs = runtime._build_agent_kwargs(
        "hermes",
        route="openrouter",
        model="openrouter:deepseek/deepseek-v4-pro",
    )

    assert kwargs["provider"] == "openrouter"
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert kwargs["model"] == "deepseek/deepseek-v4-pro"
    assert kwargs["max_tokens"] == 2048


def test_explicit_openrouter_route_cannot_be_hijacked_by_generic_endpoint_or_key_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_OPENROUTER_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("VIBECOMFY_HERMES_API_KEY", "generic-provider-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "native-deepseek-key")
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "sk-or-v1-openrouter-key")

    kwargs = runtime._build_agent_kwargs(
        "hermes",
        route="openrouter",
        model="openrouter:deepseek/deepseek-v4-pro",
    )

    assert kwargs["provider"] == "openrouter"
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert kwargs["api_key"] == "sk-or-v1-openrouter-key"
    assert kwargs["model"] == "deepseek/deepseek-v4-pro"


def test_provider_preserves_openrouter_route_at_runtime_boundary() -> None:
    descriptor = agent_provider._resolve_agent_route("openrouter")
    assert agent_provider._runtime_dispatch_route(
        descriptor, descriptor.normalized_route
    ) == "openrouter"


def test_unsupported_route_plumbs_unknown_provenance_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = agent_provider._resolve_agent_route("unsupported-route")
    assert descriptor.requested_route == "unsupported-route"
    assert descriptor.normalized_route == "unknown"
    assert agent_provider._runtime_dispatch_route(descriptor, descriptor.normalized_route) == "unknown"
    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: runtime)

    with pytest.raises(ImportError) as raised:
        agent_provider.run_model_turn(
            "test unsupported route",
            [{"role": "user", "content": "test unsupported route"}],
            route="unsupported-route",
            model="agent-edit",
            response_contract="text",
            profiling_context={"backend_phase": "classify"},
        )

    worker_result = raised.value.worker_result  # type: ignore[attr-defined]
    attempt = worker_result["model_attempts"][0]
    assert attempt["requested_model"] == "agent-edit"
    assert attempt["resolved_model"] == "unknown"
    assert attempt["adapter"] == "unknown"
    assert attempt["provider"] == "unknown"
    assert attempt["transport"] == "unknown"
    assert attempt["endpoint"] == "unknown"
    readiness = runtime.readiness(route="unsupported-route", model="agent-edit")
    assert readiness["route"] == "unknown"
    assert readiness["model"] == "unknown"


def test_agent_edit_contract_model_uses_openrouter_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    kwargs = runtime._build_agent_kwargs(
        "hermes",
        route="openrouter",
        model="agent-edit",
    )

    assert kwargs["provider"] == "openrouter"
    assert kwargs["model"] == "deepseek/deepseek-v4-pro"


def test_openrouter_readiness_does_not_report_contract_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    readiness = runtime.readiness(route="openrouter", model="agent-edit")

    assert readiness["ready"] is True
    assert readiness["route"] == "openrouter"
    assert readiness["model"] == "deepseek/deepseek-v4-pro"


def test_hermes_route_readiness_maps_to_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    readiness = runtime.readiness(route="hermes", model="agent-edit")

    assert readiness["ready"] is True
    assert readiness["route"] == "openrouter"
    assert readiness["model"] == "deepseek/deepseek-v4-pro"


def test_normalize_route_maps_hermes_to_openrouter() -> None:
    assert runtime._normalize_route("hermes") == "openrouter"
    assert runtime._requested_route("hermes") == "openrouter"


def test_provider_status_preserves_runtime_model_over_contract_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Runtime:
        @staticmethod
        def readiness(*, route: str, model: str | None = None) -> dict[str, object]:
            assert model == "agent-edit"
            return {
                "ready": True,
                "route": "openrouter",
                "model": "deepseek/deepseek-v4-pro",
                "reason": "ready",
            }

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)
    monkeypatch.setattr(agent_provider, "_openrouter_key_present", lambda: True)

    status = agent_provider.readiness(route="auto")

    assert status["ready"] is True
    assert status["route"] == "openrouter"
    assert status["model"] == "deepseek/deepseek-v4-pro"


def test_resolve_openrouter_key_prefers_openrouter_shaped_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY_2", raising=False)
    monkeypatch.setattr(
        runtime,
        "_read_env_file_entries",
        lambda path=runtime._HERMES_ENV_PATH: [
            ("OPENROUTER_API_KEY", "sk-or-v1-valid-openrouter-key"),
            ("OPENROUTER_API_KEY", "sk-stale-direct-key"),
        ],
    )

    assert runtime._resolve_openrouter_key() == "sk-or-v1-valid-openrouter-key"


def test_run_worker_mirrors_openrouter_key_into_backend_env_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "sk-or-v1-test-key")
    captured_env: dict[str, str] = {}

    def fake_run(args, **kwargs):
        captured_env.update(kwargs["env"])
        with open(args[3], "w", encoding="utf-8") as fh:
            json.dump({"content": "hello"}, fh)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    result = runtime._run_worker(
        {"api_key": "sk-or-v1-test-key"},
        "system",
        "user",
        response_contract="batch_repl",
        agent_id="hermes",
    )

    assert result["content"] == "hello"
    assert captured_env["OPENROUTER_API_KEY"] == "sk-or-v1-test-key"
    assert captured_env["OPENAI_API_KEY"] == "sk-or-v1-test-key"
    assert captured_env["HERMES_API_KEY"] == "sk-or-v1-test-key"


def test_run_worker_mirrors_parent_resolved_native_deepseek_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "sk-or-v1-stale-key")
    captured_env: dict[str, str] = {}

    def fake_run(args, **kwargs):
        captured_env.update(kwargs["env"])
        with open(args[3], "w", encoding="utf-8") as fh:
            json.dump({"content": "hello"}, fh)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    result = runtime._run_worker(
        {
            "api_key": "sk-native-deepseek-key",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-v4-flash",
        },
        "system",
        "user",
        response_contract="batch_repl",
        agent_id="hermes",
    )

    assert result["content"] == "hello"
    assert captured_env["OPENROUTER_API_KEY"] == "sk-native-deepseek-key"
    assert captured_env["OPENAI_API_KEY"] == "sk-native-deepseek-key"
    assert captured_env["HERMES_API_KEY"] == "sk-native-deepseek-key"


def test_codex_request_preserves_selected_model_and_reasoning_effort() -> None:
    request = worker._build_request(
        agent_id="codex",
        user_message="route this",
        system_message="return json",
        model="gpt-5.6-luna",
        effort="medium",
    )

    assert request.model == "gpt-5.6-luna"
    assert request.resolved_model == "gpt-5.6-luna"
    assert request.effort == "medium"


def test_runtime_serializes_codex_model_and_effort_for_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: dict[str, object] = {}

    def fake_run(args, **kwargs):
        with open(args[2], encoding="utf-8") as fh:
            captured_request.update(json.load(fh))
        with open(args[3], "w", encoding="utf-8") as fh:
            json.dump({"content": "ok"}, fh)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)
    result = runtime._run_worker(
        {},
        "system",
        "user",
        response_contract="text",
        agent_id="codex",
        model="gpt-5.6-sol",
        effort="medium",
    )

    assert result["content"] == "ok"
    assert captured_request["model"] == "gpt-5.6-sol"
    assert captured_request["effort"] == "medium"


def test_provider_forwards_codex_model_and_effort_to_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Runtime:
        @staticmethod
        def run_model_turn(**kwargs):
            captured.update(kwargs)
            return {"content": '{"reply":"ok"}', "json": {"reply": "ok"}}

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)

    result = agent_provider.run_model_turn(
        "judge this",
        route="codex",
        model="gpt-5.6-luna",
        effort="medium",
    )

    assert result["json"] == {"reply": "ok"}
    assert captured["route"] == "openai-codex"
    assert captured["model"] == "gpt-5.6-luna"
    assert captured["effort"] == "medium"


def test_worker_bootstraps_repo_root_from_neutral_cwd(tmp_path) -> None:
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(
        json.dumps(
            {
                "agent_id": "__missing_test_adapter__",
                "agent_kwargs": {
                    "max_iterations": 1,
                    "enabled_toolsets": [],
                    "save_trajectories": False,
                    "skip_context_files": True,
                    "skip_memory": True,
                    "quiet_mode": True,
                },
                "system_message": None,
                "user_message": "hello",
                "response_contract": "text",
            }
        ),
        encoding="utf-8",
    )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    proc = subprocess.run(
        [sys.executable, runtime._WORKER_PATH, str(request_path), str(result_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proc.returncode == 0
    assert result_path.is_file(), proc.stderr or proc.stdout
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["error_type"] == "LookupError"
    assert "No module named 'vibecomfy'" not in (proc.stderr + proc.stdout + json.dumps(result))


def test_run_worker_preserves_stdout_stderr_tail_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "sk-or-v1-test-key")

    def fake_run(args, **kwargs):
        with open(args[3], "w", encoding="utf-8") as fh:
            json.dump({"error": "Agent returned an empty batch_repl response.", "error_type": "ValueError"}, fh)
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="Error code: 402 - This request requires more credits",
            stderr="HTTP/1.1 402 Payment Required",
        )

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    result = runtime._run_worker(
        {"api_key": "sk-or-v1-test-key"},
        "system",
        "user",
        response_contract="batch_repl",
        agent_id="hermes",
    )

    assert result["worker_stdout_tail"] == "Error code: 402 - This request requires more credits"
    assert result["worker_stderr_tail"] == "HTTP/1.1 402 Payment Required"


def test_openrouter_empty_batch_response_surfaces_worker_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")
    monkeypatch.setattr(
        runtime,
        "_run_worker",
        lambda *args, **kwargs: {
            "error": "Agent returned an empty batch_repl response.",
            "error_type": "ValueError",
        },
    )

    with pytest.raises(RuntimeError, match="empty batch_repl response"):
        runtime.run_agent_turn_batch(
            task="make it brighter",
            route="openrouter",
            messages=[{"role": "user", "content": "User request:\nmake it brighter"}],
        )


def test_openrouter_worker_error_message_includes_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")
    monkeypatch.setattr(
        runtime,
        "_run_worker",
        lambda *args, **kwargs: {
            "error": "Connection error.",
            "error_type": "APIConnectionError",
        },
    )

    with pytest.raises(RuntimeError, match="APIConnectionError: Connection error\\."):
        runtime.run_agent_turn_batch(
            task="make it brighter",
            route="openrouter",
            messages=[{"role": "user", "content": "User request:\nmake it brighter"}],
        )


def test_openrouter_worker_401_error_is_permission_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")
    monkeypatch.setattr(
        runtime,
        "_run_worker",
        lambda *args, **kwargs: {
            "error": "ProviderCallError: Error code: 401 - Missing Authentication header",
            "error_type": "ProviderCallError",
        },
    )

    with pytest.raises(PermissionError, match="Missing Authentication header"):
        runtime.run_agent_turn_batch(
            task="make it brighter",
            route="openrouter",
            messages=[{"role": "user", "content": "User request:\nmake it brighter"}],
        )


@pytest.mark.parametrize(
    ("exc", "raw", "expected"),
    [
        (ValueError("empty"), "", "empty_response"),
        (json.JSONDecodeError("bad", "{bad", 1), "{bad", "malformed_json"),
        (json.JSONDecodeError("bad", "plain prose", 0), "plain prose", "non_json_content"),
        (ValueError("must include field reply"), '{"other":"x"}', "missing_required_fields"),
        (TimeoutError("late"), None, "timeout"),
        (RuntimeError("capacity"), None, "provider_failure"),
    ],
)
def test_worker_failure_taxonomy_is_structural(
    exc: BaseException,
    raw: str | None,
    expected: str,
) -> None:
    assert worker._model_attempt_failure_type(exc, raw) == expected


def test_worker_zero_filled_usage_without_calls_is_unavailable() -> None:
    request = {
        "agent_id": "hermes",
        "requested_model": "requested",
        "model": "resolved",
        "agent_kwargs": {
            "model": "resolved",
            "base_url": "https://openrouter.ai/api/v1",
        },
    }
    zero_usage = {
        "deepseek_usage": {
            "n_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    }

    unavailable = worker._model_attempt(
        request,
        {"backend_phase": "classify"},
        zero_usage,
        outcome="failure",
        failure_type="empty_response",
    )
    observed = worker._model_attempt(
        request,
        {"backend_phase": "classify"},
        {"deepseek_usage": {**zero_usage["deepseek_usage"], "n_calls": 1}},
        outcome="failure",
        failure_type="empty_response",
    )

    assert unavailable["token_usage"]["completion_tokens"] == "unknown"
    assert observed["token_usage"]["completion_tokens"] == 0


def _canonical_success_attempt() -> dict:
    return {
        "phase": "batch",
        "attempt": 1,
        "outcome": "success",
        "failure_type": None,
        "requested_model": "openrouter:requested/model",
        "resolved_model": "resolved/model",
        "adapter": "hermes",
        "provider": "openrouter",
        "transport": "openrouter",
        "endpoint": "https://openrouter.ai/api/v1",
        "finish_reason": "stop",
        "token_usage": {
            "prompt_tokens": 12,
            "completion_tokens": 3,
            "total_tokens": 15,
        },
    }


def test_three_runtime_success_paths_preserve_worker_attempt_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_hermes_credential_for", lambda route, model: "key")
    attempt = _canonical_success_attempt()

    def fake_worker(*args, response_contract, **kwargs):  # noqa: ANN001, ANN202, ARG001
        base = {"model_attempts": [attempt], "deepseek_usage": attempt["token_usage"]}
        if response_contract == "python":
            return {**base, "python": "pass", "message": "ok"}
        if response_contract == "delta":
            return {**base, "delta": [], "message": "ok"}
        return {**base, "content": "done\n```batch\ndone()\n```"}

    monkeypatch.setattr(runtime, "_run_worker", fake_worker)

    python_result = runtime.run_agent_turn(
        task="x", python_source="", route="openrouter", model="requested/model"
    )
    delta_result = runtime.run_agent_turn_delta(
        task="x", projection="{}", op_schema={}, route="openrouter", model="requested/model"
    )
    batch_result = runtime.run_agent_turn_batch(
        task="x", route="openrouter", model="requested/model", messages=[]
    )

    for result in (python_result, delta_result, batch_result):
        assert result["model_attempts"] == [attempt]
        assert result["deepseek_usage"] == attempt["token_usage"]


def test_batch_provider_audit_merges_worker_attempt_provenance() -> None:
    attempt = _canonical_success_attempt()
    result = agent_provider._normalize_batch_response(
        {
            "content": "Changed it.\n```batch\ndone()\n```",
            "model_attempts": [attempt],
            "deepseek_usage": attempt["token_usage"],
        },
        route="openrouter",
        model="requested/model",
        audit_metadata={"provider": "arnold"},
    )

    assert result.audit_metadata["model_attempts"] == [attempt]
    assert result.audit_metadata["deepseek_usage"] == attempt["token_usage"]


def test_batch_provider_retry_renumbers_all_worker_attempts_monotonically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    first_a = {**_canonical_success_attempt(), "outcome": "failure", "failure_type": "provider_failure"}
    first_b = {
        **_canonical_success_attempt(),
        "attempt": 2,
        "token_usage": {
            "prompt_tokens": 8,
            "completion_tokens": 0,
            "total_tokens": 8,
        },
    }
    second = _canonical_success_attempt()

    class Runtime:
        @staticmethod
        def run_agent_turn_batch(**kwargs):  # noqa: ANN003, ANN205, ARG004
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"content": "", "model_attempts": [first_a, first_b]}
            return {
                "content": "done\n```batch\ndone()\n```",
                "model_attempts": [second],
            }

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)

    result = agent_provider.run_agent_turn_batch(
        "edit it",
        [{"role": "user", "content": "edit it"}],
        route="openrouter",
        model="requested/model",
    )

    attempts = result.audit_metadata["model_attempts"]
    assert calls == 2
    assert [attempt["attempt"] for attempt in attempts] == [1, 2, 3]
    assert attempts[1]["failure_type"] == "empty_response"


def test_successful_classify_and_reply_attempts_reach_executor_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_model_turn(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
        nonlocal calls
        calls += 1
        phase = "classify" if calls == 1 else "reply"
        content = (
            '{"research":false,"implement":false,"reply":true,"route":"respond"}'
            if phase == "classify"
            else '{"reply":"hello"}'
        )
        attempt = {**_canonical_success_attempt(), "phase": phase}
        return {"content": content, "json": json.loads(content), "model_attempts": [attempt]}

    monkeypatch.setattr(agent_provider, "run_model_turn", fake_model_turn)
    token = runtime.begin_model_attempt_capture()
    try:
        decision = run_classify_turn("hello", route="openrouter", model="requested/model")
        assert run_reply_turn(
            "hello",
            route="openrouter",
            model="requested/model",
            plan=decision,
        ) == "hello"
        attempts = runtime.snapshot_model_attempt_capture()
    finally:
        runtime.end_model_attempt_capture(token)

    assert [item["phase"] for item in attempts] == ["classify", "reply"]
    assert all(item["outcome"] == "success" for item in attempts)
