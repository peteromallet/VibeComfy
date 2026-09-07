from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from typing import Any

import pytest

import vibecomfy.runtime.execution as execution_module
from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import (
    ApprovedProjectionRecord,
    WorkflowBundleError,
    canonical_digest,
    load_bundle,
)
from vibecomfy.runtime.execution import (
    authorized_queue_payload,
    collect_output_paths,
    embedded_outputs,
    normalize_prompt_id,
    queue_embedded_prompt,
    queue_server_prompt,
)


def _runtime_errors():
    return importlib.import_module("vibecomfy.errors")


def _approved():
    workflow = VibeWorkflow("runtime-execution-test", WorkflowSource("runtime-execution-test"))
    workflow.add_node("Integer", uid="integer-node", value=7)
    bundle = load_bundle(workflow)
    return bundle.compile(), bundle


class _EmbeddedQueueFailure:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def queue_prompt_api(self, api_dict: dict[str, Any]) -> Any:
        raise self.exc


class _ServerQueueFailure:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def _post_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
        raise self.exc


def test_normalize_prompt_id_accepts_dicts_and_objects() -> None:
    assert normalize_prompt_id({"prompt_id": "prompt-dict"}) == "prompt-dict"
    assert normalize_prompt_id(SimpleNamespace(prompt_id=123)) == "123"
    assert normalize_prompt_id({}) is None


def test_collect_output_paths_recurses_through_payloads() -> None:
    payload = {
        "images": [{"filename": "image.png"}, {"ignored": "value"}],
        "video": {"fullpath": "/tmp/video.mp4"},
        "audio": {"path": "audio.wav"},
    }

    assert collect_output_paths(payload) == ["image.png", "/tmp/video.mp4", "audio.wav"]


def test_embedded_outputs_accepts_result_objects_and_dict_payloads() -> None:
    result = SimpleNamespace(outputs={"1": {"filename": "object.png"}})

    assert embedded_outputs(result) == ["object.png"]
    assert embedded_outputs({"outputs": {"1": {"abs_path": "/tmp/dict.png"}}}) == ["/tmp/dict.png"]


def test_authorized_payload_is_detached_exact_record_projection() -> None:
    record, bundle = _approved()

    payload = authorized_queue_payload(record, bundle)
    assert payload == record.to_dict()["api_projection"]
    payload["1"]["inputs"]["value"] = 99
    assert record.to_dict()["api_projection"]["1"]["inputs"]["value"] == 7


def test_digest_consistent_forged_record_is_rejected_before_queue() -> None:
    record, bundle = _approved()
    payload = record.to_dict()
    api = dict(payload["api_projection"])
    node = dict(api["1"])
    inputs = dict(node["inputs"])
    inputs["value"] = 99
    node["inputs"] = inputs
    api["1"] = node
    forged = ApprovedProjectionRecord(
        payload["revision_id"],
        payload["selected_variant"],
        payload["input_binding"],
        api,
        payload["ui_projection"],
        canonical_digest(api),
    )
    with pytest.raises(WorkflowBundleError, match="current bundle"):
        authorized_queue_payload(forged, bundle)
    assert authorized_queue_payload(record, bundle)["1"]["inputs"]["value"] == 7


def test_bare_payload_is_rejected_before_embedded_transport() -> None:
    calls: list[dict[str, Any]] = []

    class Queue:
        async def queue_prompt_api(self, payload):
            calls.append(payload)
            return {"prompt_id": "unexpected"}

    _, bundle = _approved()
    with pytest.raises(ValueError, match="ApprovedProjectionRecord"):
        asyncio.run(queue_embedded_prompt(Queue(), {}, bundle))
    assert calls == []


def test_stale_bundle_is_rejected_before_server_transport() -> None:
    calls: list[dict[str, Any]] = []

    class Client:
        async def _post_prompt(self, payload):
            calls.append(payload)
            return {"prompt_id": "unexpected"}

    record, bundle = _approved()
    bundle.workflow.source.provenance["source_digest"] = "changed"
    with pytest.raises(ValueError, match="revision"):
        asyncio.run(queue_server_prompt(record, bundle, client=Client()))
    assert calls == []


def test_queue_embedded_prompt_wraps_failures_and_returns_outputs() -> None:
    class FakeEmbeddedQueue:
        async def queue_prompt_api(self, api_dict: dict[str, Any]) -> Any:
            assert api_dict == _approved()[0].to_dict()["api_projection"]
            return SimpleNamespace(prompt_id="prompt-embedded", outputs={"1": {"filename": "out.png"}})

    result = asyncio.run(
        queue_embedded_prompt(
            FakeEmbeddedQueue(),
            *_approved(),
        )
    )

    assert result.prompt_id == "prompt-embedded"
    assert result.outputs == ["out.png"]


def test_queue_embedded_prompt_wraps_queue_failure() -> None:
    with pytest.raises(RuntimeError, match="Workflow queue failed: embedded rejected prompt"):
        asyncio.run(queue_embedded_prompt(_EmbeddedQueueFailure(ValueError("embedded rejected prompt")), *_approved()))


def test_queue_embedded_prompt_wraps_non_timeout_failure_as_typed_queue_error() -> None:
    errors = _runtime_errors()

    with pytest.raises(errors.WorkflowQueueError) as exc_info:
        asyncio.run(queue_embedded_prompt(_EmbeddedQueueFailure(ValueError("embedded rejected prompt")), *_approved()))

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert exc_info.value.next_action


def test_queue_embedded_prompt_preserves_asyncio_timeout() -> None:
    errors = _runtime_errors()

    with pytest.raises(asyncio.TimeoutError) as exc_info:
        asyncio.run(queue_embedded_prompt(_EmbeddedQueueFailure(asyncio.TimeoutError("embedded queue timed out")), *_approved()))

    assert not isinstance(exc_info.value, errors.WorkflowQueueError)


def test_queue_server_prompt_uses_client_without_collecting_outputs() -> None:
    class FakeClient:
        async def _post_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
            assert prompt == _approved()[0].to_dict()["api_projection"]
            return {"prompt_id": "prompt-server", "outputs": {"1": {"filename": "ignored.png"}}}

    result = asyncio.run(
        queue_server_prompt(
            *_approved(),
            client=FakeClient(),
        )
    )

    assert result.prompt_id == "prompt-server"
    assert result.outputs == []


def test_queue_server_prompt_builds_client_from_active_server_url(monkeypatch: pytest.MonkeyPatch) -> None:
    constructed_urls: list[str] = []

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            constructed_urls.append(server_url)

        async def _post_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
            return {"prompt_id": "prompt-from-url"}

    monkeypatch.setattr(execution_module, "ComfyClient", FakeClient)

    result = asyncio.run(queue_server_prompt(*_approved(), server_url="http://active.test"))

    assert constructed_urls == ["http://active.test"]
    assert result.prompt_id == "prompt-from-url"
    assert result.outputs == []


def test_queue_server_prompt_wraps_queue_failure() -> None:
    with pytest.raises(RuntimeError, match="Workflow queue failed: server rejected prompt"):
        asyncio.run(queue_server_prompt(*_approved(), client=_ServerQueueFailure(ValueError("server rejected prompt"))))


def test_queue_server_prompt_wraps_non_timeout_failure_as_typed_queue_error() -> None:
    errors = _runtime_errors()

    with pytest.raises(errors.WorkflowQueueError) as exc_info:
        asyncio.run(queue_server_prompt(*_approved(), client=_ServerQueueFailure(ValueError("server rejected prompt"))))

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert exc_info.value.next_action


def test_queue_server_prompt_preserves_asyncio_timeout() -> None:
    errors = _runtime_errors()

    with pytest.raises(asyncio.TimeoutError) as exc_info:
        asyncio.run(queue_server_prompt(*_approved(), client=_ServerQueueFailure(asyncio.TimeoutError("server queue timed out"))))

    assert not isinstance(exc_info.value, errors.WorkflowQueueError)
