"""Selected-client injection keeps the canonical server runner in charge."""
from __future__ import annotations

import asyncio
import importlib
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.runtime import session
from vibecomfy.workflow_bundle import WorkflowBundleError

runtime = importlib.import_module("vibecomfy.runtime.run")


def test_sync_runner_forwards_the_bound_client(monkeypatch):
    client = SimpleNamespace(server_url="http://127.0.0.1:8188")
    artifacts = SimpleNamespace(server_url=client.server_url)
    calls = []

    async def run(record, bundle, **kwargs):
        calls.append((record, bundle, kwargs))
        return "complete"

    monkeypatch.setattr(runtime, "run", run)
    assert runtime.run_sync(
        "approved", "canonical", server_url=client.server_url,
        server_client=client, artifact_client=artifacts,
    ) == "complete"
    assert calls[0][2]["server_client"] is client
    assert calls[0][2]["artifact_client"] is artifacts


@pytest.mark.parametrize("server_url", [None, "http://127.0.0.1:8189"])
def test_runner_rejects_a_client_for_another_target(server_url):
    client = SimpleNamespace(server_url="http://127.0.0.1:8188")
    with pytest.raises(WorkflowBundleError, match="selected server_url"):
        asyncio.run(runtime.run(None, None, server_url=server_url, server_client=client))


@pytest.mark.parametrize("server_url", [None, "http://127.0.0.1:8189"])
def test_runner_rejects_artifacts_for_another_target(server_url):
    client = SimpleNamespace(server_url="http://127.0.0.1:8188", download_artifacts=lambda: None)
    with pytest.raises(WorkflowBundleError, match="artifact client.*selected server_url"):
        asyncio.run(runtime.run(None, None, server_url=server_url, artifact_client=client))


def test_history_uses_the_supplied_client_and_keeps_terminal_validation(monkeypatch):
    monkeypatch.setenv("VIBECOMFY_HISTORY_POLL_INTERVAL_SEC", "0")
    monkeypatch.setattr(session, "ComfyClient", lambda *_: pytest.fail("unselected HTTP client"))

    class Client:
        calls = 0

        def __bool__(self):
            return False

        async def history(self, prompt_id):
            assert prompt_id == "accepted"
            self.calls += 1
            if self.calls == 1:
                return {}
            return {"accepted": {"status": {"status_str": "success", "completed": True, "messages": []},
                                 "outputs": {"2": {"images": [{"filename": "dog.png"}]}}}}

    client = Client()
    history = asyncio.run(session._wait_for_server_history(
        "http://127.0.0.1:8188", "accepted", config=None, client=client,
    ))
    assert client.calls == 2
    assert history["accepted"]["outputs"]["2"]["images"][0]["filename"] == "dog.png"


@pytest.mark.parametrize("delivery", ["success", "missing", "wrong-root"])
def test_bound_transport_retrieves_artifacts_and_keeps_external_completion(monkeypatch, tmp_path, delivery):
    from PIL import Image
    from vibecomfy.schema import NodeSchema
    from vibecomfy.workflow import VibeNode, VibeOutput, VibeWorkflow, WorkflowSource
    from vibecomfy.workflow_bundle import load_bundle

    url = "http://127.0.0.1:8188"
    calls = []

    @asynccontextmanager
    async def server(*, server_url, log_path, config):
        assert server_url == url
        assert log_path is None and config is None
        calls.append("attached")
        yield url

    class Client:
        server_url = url

        async def _post_prompt(self, _prompt):
            calls.append("prompt")
            return {"prompt_id": "accepted"}

        async def history(self, prompt_id):
            calls.append("history")
            return {prompt_id: {
                "status": {"status_str": "success", "completed": True, "messages": []},
                "outputs": {"1": {"images": [{"filename": "final.png", "subfolder": "", "type": "output"}]}},
            }}

    class Artifacts:
        server_url = url

        async def download_artifacts(self, *, local_root):
            attempt = json.loads((local_root.parent / "attempt.json").read_text())
            assert attempt["prompt_id"] == "accepted"
            assert attempt["artifacts"][0]["filename"] == "final.png"
            output = local_root / "output" / "final.png"
            output.parent.mkdir(parents=True)
            if delivery != "missing":
                Image.new("RGB", (4, 4)).save(output)
            calls.append("retrieved")
            return {"status": "retrieved", "local_root": str(
                tmp_path / "unattributed" if delivery == "wrong-root" else local_root
            )}

    workflow = VibeWorkflow("selected-client", WorkflowSource("selected-client"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", uid="save-image", inputs={"filename_prefix": "selected"})
    workflow.outputs = [VibeOutput("1", "SaveImage", name="final")]
    bundle = load_bundle(workflow)
    provider = SimpleNamespace(get_schema=lambda name: NodeSchema(name, None, {}, []))
    record = bundle.compile(schema_provider=provider)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime, "comfy_server", server)
    monkeypatch.setattr(runtime, "ComfyClient", lambda *_: pytest.fail("unselected HTTP client"))
    monkeypatch.setattr(runtime, "_build_schema_provider", lambda *_: None)
    def run():
        return asyncio.run(runtime.run(
            record, bundle, server_url=url, server_client=Client(), artifact_client=Artifacts(),
        ))

    if delivery != "success":
        from vibecomfy.errors import RuntimeNodeError

        with pytest.raises(RuntimeNodeError, match="External server artifact retrieval failed") as caught:
            run()
        assert caught.value.delivery_state["execution"]["status"] == "succeeded"
        assert caught.value.delivery_state["retrieval"]["status"] == "failed"
        attempt = json.loads(next((tmp_path / "out/runs").glob("*/attempt.json")).read_text())
        assert attempt["prompt_id"] == "accepted"
        assert attempt["artifact_retrieval"]["status"] == "failed"
        return

    result = run()
    assert calls == ["attached", "prompt", "history", "retrieved"]
    attempt = json.loads((Path(result.metadata_path).parent / "attempt.json").read_text())
    assert attempt["adapter"]["kind"] == "external"
    assert attempt["artifact_retrieval"]["status"] == "retrieved"
    assert "lifecycle_retrieval" not in attempt
    assert result.artifacts[0]["download_source"] == "external_http"
    assert Path(result.artifacts[0]["path"]).is_file()
    assert Path(result.completion_path).is_file()
