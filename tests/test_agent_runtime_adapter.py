from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from typing import Any

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
    assert kwargs["max_tokens"] == 16384
    # Cluster B: bounded, configurable per-turn iteration budget (default 2).
    assert kwargs["max_iterations"] == 2


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
    assert kwargs["model"] == "deepseek/deepseek-v4-flash-0731"


def test_openrouter_readiness_does_not_report_contract_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    readiness = runtime.readiness(route="openrouter", model="agent-edit")

    assert readiness["ready"] is True
    assert readiness["route"] == "openrouter"
    assert readiness["model"] == "deepseek/deepseek-v4-flash-0731"


def test_hermes_route_readiness_maps_to_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    readiness = runtime.readiness(route="hermes", model="agent-edit")

    assert readiness["ready"] is True
    assert readiness["route"] == "openrouter"
    assert readiness["model"] == "deepseek/deepseek-v4-flash-0731"


def test_normalize_route_maps_hermes_to_openrouter() -> None:
    assert runtime._normalize_route("hermes") == "openrouter"
    assert runtime._requested_route("hermes") == "openrouter"


def test_hermes_cli_route_stays_distinct_and_never_resolves_a_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime, "_find_runnable_hermes_cli_command", lambda: ("/opt/bin/hermes",)
    )

    assert runtime._normalize_route("hermes-cli") == "hermes-cli"
    assert runtime._requested_route("hermes-cli") == "hermes-cli"
    assert runtime._agent_id_for_route("hermes-cli") == "hermes-cli"
    assert runtime._runtime_model_for_route("hermes-cli", "default") is None
    assert runtime._runtime_model_for_route("hermes-cli", "some/model") is None
    kwargs = runtime._build_agent_kwargs(
        "hermes-cli", route="hermes-cli", model="some/model"
    )
    assert kwargs["cli_command"] == ["/opt/bin/hermes"]
    assert "model" not in kwargs
    assert "provider" not in kwargs


def test_hermes_cli_readiness_checks_the_local_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_hermes_cli_commands", lambda: (("/opt/bin/hermes",),))
    monkeypatch.setattr(
        runtime, "_find_runnable_hermes_cli_command", lambda: ("/opt/bin/hermes",)
    )

    status = runtime.readiness(route="hermes-cli", model="agent-edit")

    assert status["ready"] is True
    assert status["route"] == "hermes-cli"
    assert status["model"] == "configured default"
    assert status["hermes_cli_runnable"] is True


def test_provider_preserves_hermes_cli_route_without_browser_credentials() -> None:
    descriptor = agent_provider._resolve_agent_route("hermes-cli")

    assert descriptor.normalized_route == "hermes-cli"
    assert descriptor.browser_api_key_allowed is False
    assert agent_provider._runtime_dispatch_route(
        descriptor, descriptor.normalized_route
    ) == "hermes-cli"
    assert "hermes-cli" in agent_provider.SUPPORTED_BROWSER_ROUTES
    assert agent_provider._supported_browser_route_options()["hermes-cli"][
        "normalized_route"
    ] == "hermes-cli"


def test_executor_payload_maps_hermes_cli_selection_to_hermes_profile() -> None:
    from vibecomfy.comfy_nodes.agent.routes import _executor_request_payload

    payload = _executor_request_payload(
        {"query": "inspect this", "route": "hermes-cli", "profile": "openai"}
    )

    assert payload["route"] == "hermes-cli"
    assert payload["profile"] == "hermes"


def test_worker_invokes_hermes_oneshot_without_model_or_provider_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cli_path = tmp_path / "hermes"
    cli_path.write_text("#!/bin/sh\n", encoding="utf-8")
    cli_path.chmod(0o755)
    monkeypatch.setenv("HERMES_INFERENCE_MODEL", "must-not-leak")
    monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "must-not-leak")
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, stdout='{"ok": true}\n', stderr="")

    monkeypatch.setattr(worker.subprocess, "run", fake_run)

    text, metadata = worker._dispatch_turn(
        agent_id="hermes-cli",
        agent_kwargs={"cli_command": [str(cli_path), "/checkout/hermes"]},
        system_message="Return JSON only.",
        user_message="Say hello.",
        model=None,
    )

    command = captured["command"]
    assert command[:4] == [
        str(cli_path),
        "/checkout/hermes",
        "--ignore-rules",
        "-z",
    ]
    assert "--model" not in command and "-m" not in command
    assert "--provider" not in command
    assert "System instructions:\nReturn JSON only." in command[4]
    assert "User request:\nSay hello." in command[4]
    assert "HERMES_INFERENCE_MODEL" not in captured["env"]
    assert "HERMES_INFERENCE_PROVIDER" not in captured["env"]
    assert text == '{"ok": true}\n'
    assert metadata["resolved_model"] == "configured default"


def test_worker_reports_missing_or_failed_hermes_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    with pytest.raises(FileNotFoundError, match="No runnable Hermes CLI"):
        worker._dispatch_turn(
            agent_id="hermes-cli",
            agent_kwargs={"cli_path": None},
            system_message=None,
            user_message="hello",
        )

    cli_path = tmp_path / "hermes"
    cli_path.write_text("#!/bin/sh\n", encoding="utf-8")
    cli_path.chmod(0o755)
    monkeypatch.setattr(
        worker.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 2, stdout="", stderr="configuration failed"
        ),
    )
    with pytest.raises(RuntimeError, match="exited with code 2"):
        worker._dispatch_turn(
            agent_id="hermes-cli",
            agent_kwargs={"cli_path": str(cli_path)},
            system_message=None,
            user_message="hello",
        )

    assert runtime._is_runtime_unavailable(
        {"error_type": "FileNotFoundError", "error": "missing"}
    )


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

    def fake_subprocess(command, **kwargs):
        captured_env.update(kwargs["env"])
        with open(command[3], "w", encoding="utf-8") as fh:
            json.dump({"content": "hello"}, fh)
        return (0, "", "")

    monkeypatch.setattr(runtime, "_run_worker_subprocess", fake_subprocess)

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

    def fake_subprocess(command, **kwargs):
        captured_env.update(kwargs["env"])
        with open(command[3], "w", encoding="utf-8") as fh:
            json.dump({"content": "hello"}, fh)
        return (0, "", "")

    monkeypatch.setattr(runtime, "_run_worker_subprocess", fake_subprocess)

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

    def fake_subprocess(command, **kwargs):
        with open(command[2], encoding="utf-8") as fh:
            captured_request.update(json.load(fh))
        with open(command[3], "w", encoding="utf-8") as fh:
            json.dump({"content": "ok"}, fh)
        return (0, "", "")

    monkeypatch.setattr(runtime, "_run_worker_subprocess", fake_subprocess)
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

    def fake_subprocess(command, **kwargs):
        with open(command[3], "w", encoding="utf-8") as fh:
            json.dump({"error": "Agent returned an empty batch_repl response.", "error_type": "ValueError"}, fh)
        return (
            0,
            "Error code: 402 - This request requires more credits",
            "HTTP/1.1 402 Payment Required",
        )

    monkeypatch.setattr(runtime, "_run_worker_subprocess", fake_subprocess)

    result = runtime._run_worker(
        {"api_key": "sk-or-v1-test-key"},
        "system",
        "user",
        response_contract="batch_repl",
        agent_id="hermes",
    )

    assert result["worker_stdout_tail"] == "Error code: 402 - This request requires more credits"
    assert result["worker_stderr_tail"] == "HTTP/1.1 402 Payment Required"


def _pid_alive(pid: int, *, timeout_s: float = 3.0) -> bool:
    """True while *pid* still exists (polling; an unreaped zombie counts as alive)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        time.sleep(0.02)
    return True


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="POSIX process groups required")
def test_worker_pipe_hang_grandchild_is_killed_with_process_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Deterministic repro of the cluster-A worker pipe hang (PR-A).

    The "worker" spawns a grandchild that INHERITS its stdout/stderr (so the
    grandchild holds the worker's stdio fds open) and then sleeps forever. The
    old ``subprocess.run(capture_output=True, timeout=...)`` path blocked in
    ``communicate()`` forever here: the timeout could kill the worker but not
    the grandchild holding the captured pipe, so the 180s turn timeout never
    fired and the whole scenario burned the runner budget.

    With ``Popen(start_new_session=True)`` + regular temp files, the 0.2s turn
    timeout must fire, the whole call must complete in under 2s, and BOTH the
    worker and its grandchild (same process group) must be dead.
    """
    pid_file = tmp_path / "worker.pids"
    helper = tmp_path / "hang_worker.py"
    helper.write_text(
        textwrap.dedent(
            f"""\
            import os
            import sys

            # Record OUR pid first so the test can observe us even if the
            # timeout fires during interpreter startup.
            with open({str(pid_file)!r}, "w", encoding="utf-8") as fh:
                fh.write(str(os.getpid()) + "\\n")

            import subprocess  # noqa: E402
            import time  # noqa: E402

            # Grandchild inherits OUR stdout/stderr and outlives us — the pipe
            # hang: it keeps the worker's stdio fds open after we are killed.
            grandchild = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(300)"]
            )
            with open({str(pid_file)!r}, "a", encoding="utf-8") as fh:
                fh.write(str(grandchild.pid) + "\\n")
            time.sleep(300)
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime, "_WORKER_PATH", str(helper))
    monkeypatch.setattr(runtime, "_TURN_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(runtime, "_TURN_KILL_GRACE_SECONDS", 0.1)

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="timed out after 0.2 seconds"):
        runtime._run_worker_once(
            {},
            "system",
            "user",
            response_contract="text",
            agent_id="hermes",
        )
    elapsed = time.monotonic() - started
    assert elapsed < 2.0, f"pipe-hang repro took {elapsed:.2f}s; group kill did not fire"

    # The worker wrote its pid first thing; the grandchild pid lands right after
    # the grandchild spawn. Poll briefly so a slow interpreter is not flaky.
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        lines = pid_file.read_text(encoding="utf-8").split()
        if len(lines) >= 2:
            break
        time.sleep(0.02)
    assert len(lines) >= 2, f"grandchild never spawned; pid file: {lines!r}"

    worker_pid, grandchild_pid = (int(part) for part in lines[:2])
    assert _pid_alive(worker_pid) is False, "worker survived the timeout kill"
    assert _pid_alive(grandchild_pid) is False, (
        "grandchild survived the process-group kill"
    )


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


def test_empty_worker_output_is_typed_empty_response() -> None:
    """Empty output is typed ``empty_response``, never a content parse failure."""
    from vibecomfy.comfy_nodes.agent.worker import (
        EmptyModelResponseError,
        _parse_failure_reason,
        _persist_parse_evidence,
    )

    exc = EmptyModelResponseError("Agent returned an empty json response.")
    assert _parse_failure_reason(exc, "") == "empty"
    assert _parse_failure_reason(exc, None) == "empty"

    out: dict = {}
    _persist_parse_evidence(
        out,
        exc,
        "",
        {"finish_reason": "stop", "deepseek_usage": {"completion_tokens": 0, "prompt_tokens": 10, "total_tokens": 10}},
        {
            "agent_id": "hermes",
            "model": "deepseek-v4-flash",
            "agent_kwargs": {
                "model": "deepseek-v4-flash",
                "provider": "openrouter",
                "base_url": "https://api.deepseek.com/v1",
            },
        },
        {"backend_phase": "classify"},
    )

    assert out["parse_reason"] == "empty"
    assert out["empty_response"] is True
    assert out["completion_tokens_zero"] is True
    assert out["completion_tokens"] == 0
    assert out["finish_reason"] == "stop"
    assert out["resolved_model"] == "deepseek-v4-flash"
    assert out["adapter"] == "hermes"
    assert out["provider"] == "openrouter"
    assert out["endpoint"] == "https://api.deepseek.com/v1"
    assert out["phase"] == "classify"
    # Credentials never persist.
    assert "api_key" not in out


def test_empty_worker_result_is_retried_as_fresh_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typed empty response is a transient infra outcome: _run_worker retries
    it as a fresh transport attempt, never surfacing it as a content failure."""
    empty = {
        "error": "Agent returned an empty json response.",
        "error_type": "EmptyModelResponseError",
        "empty_response": True,
        "parse_reason": "empty",
        "completion_tokens": 0,
        "completion_tokens_zero": True,
    }
    good = {"content": '{"reply": "ok"}', "json": {"reply": "ok"}}
    calls = []

    def fake_once(*args, **kwargs):
        calls.append((args, kwargs))
        return empty if len(calls) == 1 else good

    monkeypatch.setattr(runtime, "_run_worker_once", fake_once)
    monkeypatch.setattr(runtime.time, "sleep", lambda _s: None)

    result = runtime._run_worker(
        {"api_key": "***"},
        "sys",
        "usr",
        response_contract="json",
        agent_id="hermes",
        model="openrouter:deepseek/deepseek-v4-pro",
    )

    assert result == good
    assert len(calls) == 2
    assert calls[1][1]["profiling_context"]["transient_retry_count"] == 1


def test_nonempty_invalid_json_remains_malformed_model_json() -> None:
    """Nonempty invalid JSON stays a content/parser failure (malformed_json),
    never the typed empty_response, and never consumes a transport retry."""
    from vibecomfy.comfy_nodes.agent.worker import _parse_failure_reason, _persist_parse_evidence

    import json as _json

    exc = _json.JSONDecodeError("Expecting value", "{not json", 0)
    assert _parse_failure_reason(exc, "{not json") == "malformed_json"

    out: dict = {}
    _persist_parse_evidence(
        out,
        exc,
        "{not json",
        {"finish_reason": "stop", "deepseek_usage": {"completion_tokens": 42, "prompt_tokens": 100, "total_tokens": 142}},
        {
            "agent_id": "hermes",
            "model": "deepseek-v4-flash",
            "agent_kwargs": {
                "model": "deepseek-v4-flash",
                "provider": "openrouter",
                "base_url": "https://api.deepseek.com/v1",
            },
        },
        {"backend_phase": "classify"},
    )

    assert out["parse_reason"] == "malformed_json"
    assert out.get("empty_response") is not True
    assert out["completion_tokens_zero"] is False
    assert out["completion_tokens"] == 42
    assert out["raw_response_preview"] == "{not json"

    # The runtime treats a malformed nonempty JSON worker error as non-transient
    # (owned by the response-contract retry layer) — never a fresh transport.
    assert (
        runtime._is_transient_worker_result(
            {"error": "bad json", "error_type": "JSONDecodeError", "parse_reason": "malformed_json"}
        )
        is False
    )
    # And the provider boundary keeps raising MalformedModelJSON for nonempty
    # invalid JSON.
    with pytest.raises(agent_provider.MalformedModelJSON):
        agent_provider._extract_json_object("{not json")


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


def test_classify_malformed_first_reply_is_retried_with_corrective_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A genuinely unparseable first classify reply must be retried with a
    corrective system message carrying the redacted preview — not fail the
    whole turn with a bogus validation-error envelope."""
    calls: list[list[dict[str, Any]]] = []

    def fake_model_turn(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
        captured = list(args[1]) if len(args) > 1 else list(kwargs.get("messages") or [])
        calls.append(captured)
        if len(calls) == 1:
            # Genuinely unparseable first reply (prose only) — the retry must
            # recover it with the corrective nudge.
            content = "Let me think about the distillation {LoRA} question first."
        else:
            content = (
                '{"research": false, "implement": false, "reply": true, '
                '"effort": "low", "plan_summary": "Clarify the request"}'
            )
        attempt = {**_canonical_success_attempt(), "phase": "classify"}
        return {"content": content, "json": json.loads(content) if len(calls) > 1 else None, "model_attempts": [attempt]}

    monkeypatch.setattr(agent_provider, "run_model_turn", fake_model_turn)
    decision = run_classify_turn("Which distillation lora for Minimax should I use???", route="openrouter", model="requested/model")

    # Exactly two provider calls: the malformed first + the corrective retry.
    assert len(calls) == 2
    # The retry call carries the corrective nudge with the raw preview.
    retry_message = calls[1][-1]
    assert retry_message["role"] == "system"
    assert "classify contract" in retry_message["content"]
    assert "Previous response preview" in retry_message["content"]
    assert "{LoRA}" in retry_message["content"]
    # The recovered decision is the one from the retry.
    assert decision.research is False
    assert decision.implement is False
    assert decision.reply is True


def test_classify_never_retries_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider-level failures (AuthError) must NOT be masked by the
    corrective retry — they propagate immediately."""
    from vibecomfy.comfy_nodes.agent.provider import AuthError

    calls = 0

    def fake_model_turn(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
        nonlocal calls
        calls += 1
        raise AuthError("provider rejected credentials")

    monkeypatch.setattr(agent_provider, "run_model_turn", fake_model_turn)
    with pytest.raises(AuthError):
        run_classify_turn("hello", route="openrouter", model="requested/model")
    assert calls == 1  # never retried


def test_revise_classification_with_malformed_needs_input_reaches_implement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = json.dumps(
        {
            "research": False,
            "implement": True,
            "reply": True,
            "intent": "edit",
            "route": "revise",
            "task": "edit_graph",
            "needs_input": {"question": "Which count?", "options": 49},
        }
    )
    monkeypatch.setattr(
        agent_provider,
        "run_model_turn",
        lambda *_args, **_kwargs: {
            "content": content,
            "json": json.loads(content),
            "model_attempts": [],
        },
    )

    decision = run_classify_turn(
        "set the frame count",
        route="openrouter",
        model="requested/model",
    )

    assert decision.effective_route == "revise"
    assert decision.implement is True
    assert getattr(decision, "needs_input", None) is None


# ── B07-lite: explicit transport pinning beats ambient credentials ───────────


def test_transport_native_pin_overrides_ambient_openrouter_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sense-check 2: ambient OpenRouter key/base URL cannot win over an
    explicit native selection — endpoint resolves to api.deepseek.com with the
    native key, and the resolved model is the native slug."""
    from tests.live_agentic_harness import adapter

    monkeypatch.setenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-ambient")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-native-key")
    monkeypatch.delenv("VIBECOMFY_TRANSPORT", raising=False)

    resolved = adapter._ensure_transport_env("native")
    assert resolved == "native"
    assert os.environ["VIBECOMFY_TRANSPORT"] == "native"
    assert os.environ["VIBECOMFY_OPENROUTER_BASE_URL"] == "https://api.deepseek.com/v1"

    kwargs = runtime._build_agent_kwargs(
        "hermes", route="unknown", model="openrouter:deepseek/deepseek-v4-pro"
    )
    assert kwargs["base_url"] == "https://api.deepseek.com/v1"
    assert kwargs["api_key"] == "sk-native-key"
    # route="unknown" drops the explicit model and resolves the runtime
    # OpenRouter default, normalized to the bare native slug.
    assert kwargs["model"] == "deepseek-v4-flash"


def test_transport_openrouter_pin_overrides_ambient_native_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reverse direction: ambient native base URL + native key cannot win
    over an explicit OpenRouter selection."""
    from tests.live_agentic_harness import adapter

    monkeypatch.setenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-native-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-ambient")
    monkeypatch.delenv("VIBECOMFY_TRANSPORT", raising=False)
    # Isolate from the real ~/.hermes/.env: the ambient file must not clobber.
    monkeypatch.setattr(runtime, "_read_env_file_entries", lambda *a, **k: [])
    monkeypatch.setattr(runtime, "_read_env_file", lambda *a, **k: {})

    resolved = adapter._ensure_transport_env("openrouter")
    assert resolved == "openrouter"
    assert os.environ["VIBECOMFY_TRANSPORT"] == "openrouter"
    assert (
        os.environ["VIBECOMFY_OPENROUTER_BASE_URL"] == "https://openrouter.ai/api/v1"
    )

    kwargs = runtime._build_agent_kwargs(
        "hermes", route="unknown", model="openrouter:deepseek/deepseek-v4-pro"
    )
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert kwargs["api_key"] == "sk-or-ambient"
    # route="unknown" drops the explicit model and resolves the runtime
    # OpenRouter default.
    assert kwargs["model"] == "deepseek/deepseek-v4-flash-0731"


def test_transport_default_is_deterministic_openrouter_ignoring_ambient_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rework 2 (oracle issue 1d): with no explicit selector the harness default
    is the canonical OpenRouter product route — an ambient native base URL/key
    can never silently switch the no-flag default to native."""
    from tests.live_agentic_harness import adapter

    monkeypatch.setenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "***")
    monkeypatch.delenv("VIBECOMFY_TRANSPORT", raising=False)

    resolved = adapter._ensure_transport_env(None)
    assert resolved == "openrouter"
    assert (
        os.environ["VIBECOMFY_OPENROUTER_BASE_URL"] == "https://openrouter.ai/api/v1"
    )
    assert runtime._base_url_for_route("unknown") == "https://openrouter.ai/api/v1"
    assert runtime._is_native_deepseek_endpoint() is False


def test_transport_native_pin_wins_over_route_openrouter_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The explicit transport pin is the strongest contract: even with the
    route-level OpenRouter default, an explicit native pin resolves the
    endpoint, credential, and model slug to the native transport."""
    monkeypatch.setenv("VIBECOMFY_TRANSPORT", "native")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "***")
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "sk-or-key")

    kwargs = runtime._build_agent_kwargs(
        "hermes", route="openrouter", model="openrouter:deepseek/deepseek-v4-pro"
    )
    assert kwargs["base_url"] == "https://api.deepseek.com/v1"
    assert kwargs["api_key"] == "***"
    assert kwargs["model"] == "deepseek-v4-pro"

    provider, transport, endpoint = runtime._runtime_provider_transport(
        agent_id="hermes", agent_kwargs=kwargs
    )
    assert (provider, transport, endpoint) == (
        "deepseek",
        "native",
        "https://api.deepseek.com/v1",
    )


def test_transport_native_pin_wins_over_ambient_openrouter_key_on_all_phases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conflicting-evidence regression: an ambient OpenRouter key present plus
    an explicit ``--transport native`` selection MUST observe native on every
    profile phase (classify/research/implement/reply).  The ambient OpenRouter
    key/base URL can never silently switch the transport; the observed endpoint
    is api.deepseek.com/v1 with the redacted native key on each phase."""
    from tests.live_agentic_harness import adapter

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-ambient")
    monkeypatch.setenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "***")
    monkeypatch.delenv("VIBECOMFY_TRANSPORT", raising=False)
    # Isolate from the real ~/.hermes/.env: the ambient file must not clobber.
    monkeypatch.setattr(runtime, "_read_env_file_entries", lambda *a, **k: [])
    monkeypatch.setattr(runtime, "_read_env_file", lambda *a, **k: {})

    resolved = adapter._ensure_transport_env("native")  # --transport native
    assert resolved == "native"
    assert os.environ["VIBECOMFY_TRANSPORT"] == "native"

    for phase in ("classify", "research", "implement", "reply"):
        kwargs = runtime._build_agent_kwargs(
            "hermes", route="openrouter", model="openrouter:deepseek/deepseek-v4-pro"
        )
        provider, transport, endpoint = runtime._runtime_provider_transport(
            agent_id="hermes", agent_kwargs=kwargs
        )
        assert provider == "deepseek", phase
        assert transport == "native", phase
        assert endpoint == "https://api.deepseek.com/v1", phase
        assert kwargs["base_url"] == "https://api.deepseek.com/v1", phase
        assert kwargs["api_key"] == "***", phase  # redacted native key, never sk-or-ambient
        assert kwargs["model"] == "deepseek-v4-pro", phase

        # The probe's observed transport is recorded worker-side; assert the
        # same resolution through the worker's observation path.
        w_provider, w_transport, w_endpoint = worker._worker_provider_transport(
            {"agent_id": "hermes", "agent_kwargs": kwargs}
        )
        assert (w_provider, w_transport, w_endpoint) == (
            "deepseek",
            "native",
            "https://api.deepseek.com/v1",
        ), phase


def test_runtime_never_hydrates_transport_selecting_keys_from_hermes_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """~/.hermes/.env provides credentials only: transport-selecting keys stored
    there are ignored, so the ambient file cannot silently switch transports."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENROUTER_API_KEY=sk-or-file\n"
        "DEEPSEEK_API_KEY=sk-native-file\n"
        "VIBECOMFY_TRANSPORT=openrouter\n"
        "VIBECOMFY_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n"
        "VIBECOMFY_FORCE_MODEL=openrouter:deepseek/deepseek-v4-flash\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("VIBECOMFY_TRANSPORT", raising=False)
    monkeypatch.delenv("VIBECOMFY_OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("VIBECOMFY_FORCE_MODEL", raising=False)

    runtime._load_env_file_into_environ(env_file)

    assert os.environ.get("OPENROUTER_API_KEY") == "sk-or-file"
    assert os.environ.get("DEEPSEEK_API_KEY") == "sk-native-file"
    assert "VIBECOMFY_TRANSPORT" not in os.environ
    assert "VIBECOMFY_OPENROUTER_BASE_URL" not in os.environ
    assert "VIBECOMFY_FORCE_MODEL" not in os.environ


def test_adapter_credential_env_file_skips_transport_selecting_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Rework 2 (oracle issue 3 — env-skip mirror): the adapter's credential
    file hydrate mirrors ``runtime._load_env_file_into_environ`` — it supplies
    keys only, and transport-selecting keys stored in an ambient .env never
    hydrate, so the file cannot set ``VIBECOMFY_TRANSPORT`` when the explicit
    flag is absent and the default is OpenRouter."""
    from tests.live_agentic_harness import adapter

    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENROUTER_API_KEY=sk-or-file\n"
        "DEEPSEEK_API_KEY=***\n"
        "VIBECOMFY_TRANSPORT=native\n"
        "VIBECOMFY_OPENROUTER_BASE_URL=https://api.deepseek.com/v1\n"
        "VIBECOMFY_FORCE_MODEL=openrouter:deepseek/deepseek-v4-flash\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("VIBECOMFY_TRANSPORT", raising=False)
    monkeypatch.delenv("VIBECOMFY_OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("VIBECOMFY_FORCE_MODEL", raising=False)

    adapter._load_credential_env_file(env_file)

    assert os.environ.get("OPENROUTER_API_KEY") == "sk-or-file"
    assert os.environ.get("DEEPSEEK_API_KEY") == "***"
    assert "VIBECOMFY_TRANSPORT" not in os.environ
    assert "VIBECOMFY_OPENROUTER_BASE_URL" not in os.environ
    assert "VIBECOMFY_FORCE_MODEL" not in os.environ
