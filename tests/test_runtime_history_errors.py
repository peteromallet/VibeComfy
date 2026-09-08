from __future__ import annotations

import argparse
import asyncio

import pytest

from vibecomfy.commands.run import _cmd_run
from vibecomfy.errors import RuntimeExecutionError
import vibecomfy.runtime.session as session_module
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("history-error-test", WorkflowSource("history-error-test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "test"})
    return workflow


def test_wait_for_history_raises_typed_error_with_comfy_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "prompt-failed"

    class Client:
        async def history(self, _prompt_id: str) -> dict:
            return {
                prompt_id: {
                    "outputs": {},
                    "status": {
                        "status_str": "error",
                        "completed": True,
                        "messages": [
                            [
                                "execution_error",
                                {
                                    "node_id": "17",
                                    "exception_type": "ValueError",
                                    "exception_message": "bad latent shape",
                                    "traceback": "Traceback...\nValueError: bad latent shape",
                                },
                            ]
                        ],
                    },
                }
            }

    monkeypatch.setattr(session_module, "ComfyClient", lambda _url: Client())

    with pytest.raises(RuntimeExecutionError) as exc_info:
        asyncio.run(
            session_module._wait_for_server_history(
                "http://runtime.test", prompt_id, config=session_module.SessionConfig()
            )
        )

    error = exc_info.value
    assert error.prompt_id == prompt_id
    assert error.status == "error"
    assert error.node_id == "17"
    assert "node_id=17" in str(error)
    assert "ValueError" in str(error)
    assert "Traceback..." in str(error)
    assert error.traceback_text.startswith("Traceback...")


def test_wait_for_history_accepts_success_with_no_file_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "prompt-no-artifact"

    class Client:
        async def history(self, _prompt_id: str) -> dict:
            return {
                prompt_id: {
                    "outputs": {},
                    "status": {"status_str": "success", "completed": True, "messages": []},
                }
            }

    monkeypatch.setattr(session_module, "ComfyClient", lambda _url: Client())

    history = asyncio.run(
        session_module._wait_for_server_history(
            "http://runtime.test", prompt_id, config=session_module.SessionConfig()
        )
    )

    assert history[prompt_id]["status"]["status_str"] == "success"
    assert session_module._outputs_from_server_history(history, prompt_id) == {}


def test_cli_run_returns_nonzero_for_history_execution_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = argparse.Namespace(
        path="history-error-test",
        ready=True,
        runtime="server",
        server_url="http://runtime.test",
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        ensure_packs=False,
        ensure_models=None,
        memory_profile=None,
    )
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *a, **k: _workflow())
    failure = RuntimeExecutionError(
        "Comfy execution failed for prompt prompt-failed; node_id=17; traceback:\nboom",
        prompt_id="prompt-failed",
        status="error",
        node_id="17",
        traceback_text="boom",
    )
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_sync",
        lambda *_a, **_k: (_ for _ in ()).throw(failure),
    )

    assert _cmd_run(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "run failed: Comfy execution failed for prompt prompt-failed" in captured.err
    assert "node_id=17" in captured.err
    assert "traceback:" in captured.err
