from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from vibecomfy.errors import QueueError, RuntimeNodeError, WorkflowQueueError

from vibecomfy.commands.logs import _cmd_logs
from vibecomfy.commands.run import _cmd_run
import vibecomfy.runtime.session as session_module
from vibecomfy.artifacts import Artifact
from vibecomfy.registry.models_loader import ModelEntry, ModelSource, ModelTarget
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.testing.canonical import canonical_digest
from vibecomfy.runtime.session import SessionConfig
from vibecomfy.workflow import VibeEdge, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import WorkflowBundleError, load_bundle

runtime_run_module = importlib.import_module("vibecomfy.runtime.run")


def test_queue_server_prompt_rejects_structured_node_errors() -> None:
    from vibecomfy.runtime.execution import queue_server_prompt

    class Client:
        async def _post_prompt(self, _prompt: dict) -> dict:
            return {
                "prompt_id": "prompt-with-node-error",
                "node_errors": {"90": {"class_type": "MiniMaxH3StreamLiveExtensionAVToVHS", "errors": ["missing crf"]}},
            }

    workflow = _workflow()
    record, bundle = _approved(workflow)
    with pytest.raises(WorkflowQueueError, match="missing crf") as caught:
        asyncio.run(queue_server_prompt(record, bundle, client=Client()))
    assert caught.value.completion_status == "Failed — final output rejected"
    assert caught.value.output_verification["source"] == "comfy_queue_node_errors"


def test_declared_output_contract_rejects_preview_when_final_sink_is_missing() -> None:
    workflow = _workflow()
    workflow.outputs = [VibeOutput("91", "MiniMaxH3FinalizeVHSOutput")]
    history = {
        "prompt-1": {
            "outputs": {
                "65": {"gifs": [{"filename": "preview.mp4"}]},
            },
            "status": {"status_str": "success", "completed": True, "messages": []},
        }
    }
    with pytest.raises(RuntimeNodeError, match="declared final output node"):
        session_module._validate_declared_output_contract(workflow, history, "prompt-1")


def test_declared_output_contract_accepts_artifact_from_declared_sink() -> None:
    workflow = _workflow()
    workflow.outputs = [VibeOutput("90", "MiniMaxH3StreamLiveExtensionAVToVHS")]
    history = {
        "prompt-1": {
            "outputs": {
                "90": {"gifs": [{"filename": "final.mp4"}]},
            },
            "status": {"status_str": "success", "completed": True, "messages": []},
        }
    }
    session_module._validate_declared_output_contract(workflow, history, "prompt-1")


def test_declared_video_media_requires_bounded_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _workflow()
    workflow.outputs = [VibeOutput(
        "1", "SaveVideo", name="final", artifact_kind="video", mime_type="video/mp4"
    )]
    path = tmp_path / "final.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(session_module.shutil, "which", lambda name: "/usr/bin/ffprobe")
    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "streams": [
                    {"codec_type": "video", "width": 1280, "height": 720, "duration": "1.5"},
                    {"codec_type": "audio", "duration": "1.5"},
                ],
                "format": {"duration": "1.5"},
            }),
            stderr="",
        ),
    )
    result = session_module._verify_declared_media(
        workflow,
        [{"reported_path": str(path), "path": str(path)}],
        adapter_kind="managed",
    )
    assert result["status"] == "verified"
    assert result["artifacts"][0]["width"] == 1280
    assert result["artifacts"][0]["audio_streams"] == 1


def test_declared_video_media_does_not_accept_remote_filename_only() -> None:
    workflow = _workflow()
    workflow.outputs = [VibeOutput("1", "SaveVideo", artifact_kind="video", mime_type="video/mp4")]
    with pytest.raises(RuntimeNodeError, match="media could not be verified") as caught:
        session_module._verify_declared_media(
            workflow,
            [{"reported_path": "final.mp4", "path": None, "location": "https://remote.test/final.mp4"}],
            adapter_kind="external",
        )
    assert caught.value.diagnostics[0]["code"] == "final_media_unverified"


def test_declared_video_media_verifies_shared_filesystem_for_external_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _workflow()
    workflow.outputs = [VibeOutput("1", "SaveVideo", artifact_kind="video", mime_type="video/mp4")]
    path = tmp_path / "final.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(session_module.shutil, "which", lambda name: "/usr/bin/ffprobe")
    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "streams": [{"codec_type": "video", "width": 960, "height": 544}],
                "format": {"duration": "10.8"},
            }),
            stderr="",
        ),
    )

    result = session_module._verify_declared_media(
        workflow,
        [{"reported_path": str(path), "path": str(path)}],
        adapter_kind="external",
    )

    assert result["status"] == "verified"
    assert result["artifacts"][0]["video_streams"] == 1


def test_external_media_retrieval_failure_is_incomplete_not_final_rejection() -> None:
    record, _bundle = _approved(_workflow())
    exc = RuntimeNodeError("remote artifact was not retrievable")
    exc.output_verification = {
        "status": "invalid",
        "media": {
            "status": "invalid",
            "adapter_kind": "external",
        },
    }
    evidence = session_module._runtime_failure_evidence(
        record,
        adapter_kind="external",
        backend="api",
        endpoint="https://comfy.example",
        schema_provenance={},
        queue_acceptance={"status": "accepted", "prompt_id": "p-retrieve"},
        phase="output",
        exc=exc,
        queue_started=True,
    )
    assert evidence["terminal"]["completion_status"] == (
        "Incomplete — generation verified but retrieval failed"
    )


def test_local_verification_failure_preserves_generation_delivery_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _workflow()
    workflow.nodes["1"].class_type = "SaveVideo"
    workflow.outputs = [
        VibeOutput("1", "SaveVideo", artifact_kind="video", mime_type="video/mp4")
    ]
    local_path = tmp_path / "downloaded-artifacts/output/video/final.mp4"
    local_path.parent.mkdir(parents=True)
    local_path.write_bytes(b"not a decodable fixture")
    monkeypatch.setattr(
        session_module,
        "_probe_media_file",
        lambda _path: {"status": "invalid", "reason": "decode failed"},
    )
    output_verification = {"status": "final_output_produced", "prompt_id": "p-local"}

    with pytest.raises(RuntimeNodeError) as caught:
        session_module._verify_declared_media(
            workflow,
            [{
                "reported_path": "video/final.mp4",
                "path": str(local_path),
                "location": "https://pod.test/view?filename=final.mp4&subfolder=video&type=output",
            }],
            adapter_kind="runpod_lifecycle",
            output_verification=output_verification,
        )

    delivery = caught.value.delivery_state
    assert delivery["execution"]["status"] == "succeeded"
    assert delivery["retrieval"]["status"] == "succeeded"
    assert delivery["verification"]["status"] == "failed"
    record, _bundle = _approved(workflow)
    evidence = session_module._runtime_failure_evidence(
        record,
        adapter_kind="runpod_lifecycle",
        backend="api",
        endpoint="https://pod.test",
        schema_provenance={},
        queue_acceptance={"status": "accepted", "prompt_id": "p-local"},
        phase="verification",
        exc=caught.value,
        queue_started=True,
    )
    assert evidence["terminal"]["execution_state"] == "succeeded"
    assert evidence["terminal"]["retrieval_state"] == "succeeded"
    assert evidence["terminal"]["verification_state"] == "failed"
    assert evidence["terminal"]["completion_status"] == "Failed — final output rejected"


def test_declared_output_contract_persists_structured_diagnostics_for_preview_false_success() -> None:
    workflow = _workflow()
    workflow.outputs = [VibeOutput("91", "MiniMaxH3FinalizeVHSOutput")]
    history = {
        "prompt-1": {
            "outputs": {"65": {"gifs": [{"filename": "preview.mp4"}]}},
            "node_errors": {"90": {"errors": ["missing crf"]}},
            "status": {
                "status_str": "success",
                "completed": True,
                "messages": [["execution_start", {}], ["execution_success", {}]],
            },
        }
    }
    with pytest.raises(RuntimeNodeError) as caught:
        session_module._validate_declared_output_contract(workflow, history, "prompt-1")
    assert caught.value.diagnostics == [{
        "code": "comfy_node_errors",
        "field": "node_errors",
        "detail": {"90": {"errors": ["missing crf"]}},
    }]


@pytest.mark.parametrize("missing", ["crf", "trim_to_audio", "pix_fmt", "save_metadata"])
def test_final_output_chain_required_inputs_are_checked_against_live_schema(missing: str) -> None:
    workflow = _workflow()
    workflow.outputs = [VibeOutput("1", "SaveImage", name="final", artifact_kind="video")]
    workflow.nodes["1"].inputs.update({
        "crf": 19,
        "trim_to_audio": True,
        "pix_fmt": "yuv420p",
        "save_metadata": False,
    })
    workflow.nodes["1"].inputs.pop(missing)
    record, bundle = _approved(workflow)

    class _FinalSchemaProvider:
        def get_schema(self, class_type):
            assert class_type == "SaveImage"
            return NodeSchema(
                class_type,
                None,
                {
                    name: InputSpec(required=True)
                    for name in ("images", "filename_prefix", "crf", "trim_to_audio", "pix_fmt", "save_metadata")
                },
                [],
            )

    with pytest.raises(Exception, match=f"missing required input {missing}"):
        session_module._prepare_runtime_prompt_with_evidence(
            record,
            bundle,
            schema_provider=_FinalSchemaProvider(),
        )


def _workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("runtime-test", WorkflowSource("runtime-test"))
    workflow.nodes["1"] = VibeNode(
        "1", "SaveImage", inputs={"filename_prefix": "test", "images": "fixture-image"}
    )
    return workflow


def _approved(workflow: VibeWorkflow):
    for node in workflow.nodes.values():
        if not node.uid:
            node.uid = f"runtime-{node.id}"
    bundle = load_bundle(workflow)
    class _FixtureProvider:
        def get_schema(self, class_type):
            return NodeSchema(class_type, None, {}, [])

    entry = ModelEntry(
        "runtime-fixture-model",
        ModelSource("local"),
        0,
        (ModelTarget("comfy_core", "checkpoints"),),
    )
    with (
        patch("vibecomfy.registry.models_loader.load_registry", return_value=(entry,)),
        patch("vibecomfy.registry.models_loader.resolve_model_entry", return_value=entry),
        patch("vibecomfy.fetch.is_present", return_value=True),
    ):
        return bundle.compile(schema_provider=_FixtureProvider()), bundle


def _command_bundle():
    workflow = VibeWorkflow("command-runtime-test", WorkflowSource("command-runtime-test"))
    workflow.add_node("Integer", uid="integer-node", value=7)
    return load_bundle(workflow)


def _successful_history(prompt_id: str, outputs: object) -> dict:
    return {
        prompt_id: {
            "outputs": outputs,
            "status": {
                "status_str": "success",
                "completed": True,
                "messages": [],
            },
        }
    }


def _runtime_events(tmp_path: Path, record):
    run_dir = next(path for path in (tmp_path / "out/runs").iterdir() if path.is_dir())
    attempt = json.loads((run_dir / "attempt.json").read_text(encoding="utf-8"))
    lifecycle = run_dir / "transactions" / record.api_digest / "lifecycle_events.jsonl"
    events = [json.loads(line) for line in lifecycle.read_text(encoding="utf-8").splitlines()]
    return run_dir, attempt, events


_RECORD_KEYS = {
    "revision_id", "selected_variant", "input_binding",
    "api_projection", "ui_projection", "api_digest",
}


def _assert_exact_runtime_record(document: dict, record) -> None:
    evidence_objects: list[dict] = []
    full_record_paths: list[tuple[object, ...]] = []

    def walk(value, path: tuple[object, ...] = ()) -> None:
        if isinstance(value, dict):
            if _RECORD_KEYS <= set(value):
                full_record_paths.append(path)
            runtime_evidence = value.get("runtime_evidence")
            if isinstance(runtime_evidence, dict):
                evidence_objects.append(runtime_evidence)
            for key, child in value.items():
                walk(child, (*path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, (*path, index))

    walk(document)
    assert evidence_objects
    assert len(full_record_paths) == len(evidence_objects)
    record_dict = record.to_dict()
    for evidence in evidence_objects:
        approved = evidence["approved_projection"]
        assert isinstance(approved, dict)
        assert len(approved) == 6
        assert set(approved) == _RECORD_KEYS
        assert approved == record_dict
        assert evidence["api_digest"] == record.api_digest
        assert evidence["ui_digest"] == canonical_digest(record_dict["ui_projection"])
        assert evidence["record_digest"] == canonical_digest(record_dict)
        assert evidence["queue_acceptance"] == document.get("queue_acceptance", evidence["queue_acceptance"])
        assert evidence["terminal"] == document.get("terminal", evidence["terminal"])
        assert evidence["adapter"] == document.get("adapter", evidence["adapter"])
        assert evidence["schema_provenance"] == document.get("schema_provenance", evidence["schema_provenance"])
    assert all(path[-2:] == ("runtime_evidence", "approved_projection") for path in full_record_paths)
    assert not {"approved_projection", "approval_record", "approved_record"} & set(document)
    assert not (_RECORD_KEYS - {"api_digest"}) & set(document)
    if "runtime_evidence" in document:
        evidence = document["runtime_evidence"]
        for key in ("queue_acceptance", "terminal", "adapter", "schema_provenance"):
            if key in document:
                assert document[key] == evidence[key]
        if "api_digest" in document:
            assert document["api_digest"] == evidence["api_digest"]


def test_run_starts_server_before_building(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    entered_server = False

    @asynccontextmanager
    async def fail_if_entered(*args, **kwargs):
        nonlocal entered_server
        entered_server = True
        yield "http://127.0.0.1:8188"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fail_if_entered)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    with pytest.raises(ValueError, match="approved API projection"):
        asyncio.run(runtime_run_module.run(*_approved(_workflow()), backend="missing"))

    assert entered_server is True
    assert (tmp_path / "out").exists()


def test_run_embedded_starts_before_building(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeComfy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = lambda configuration=None: FakeComfy()
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="approved API projection"):
        asyncio.run(runtime_run_module.run_embedded(*_approved(_workflow()), backend="missing"))

    # Rework-1 publishes the record-bearing prepared attempt before schema
    # preparation, so the run root is durable even when preparation rejects.
    assert (tmp_path / "out/runs").exists()


def test_run_validates_before_queueing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    entered_server = False

    @asynccontextmanager
    async def fail_if_entered(*args, **kwargs):
        nonlocal entered_server
        entered_server = True
        yield "http://127.0.0.1:8188"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fail_if_entered)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    with pytest.raises(TypeError):
        asyncio.run(runtime_run_module.run(VibeWorkflow("empty", WorkflowSource("empty"))))

    assert entered_server is False
    assert not (tmp_path / "out").exists()


def test_run_surfaces_queue_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    queued_prompts: list[dict] = []

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    class FailingClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def _post_prompt(self, prompt: dict) -> dict:
            queued_prompts.append(prompt)
            raise RuntimeError("runtime rejected prompt")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FailingClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    workflow = _workflow()
    workflow.metadata["id_map"] = {"save": "1"}
    workflow.nodes["1"].metadata["source_id"] = "7"

    with pytest.raises(RuntimeError, match="Workflow queue failed: runtime rejected prompt") as exc_info:
        asyncio.run(runtime_run_module.run(*_approved(workflow), server_url="http://runtime.test"))

    assert queued_prompts == [
        {
            "1": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "test", "images": "fixture-image"},
            }
        }
    ]
    message = str(exc_info.value)
    assert "id_map=" in message
    assert "'save': '1'" in message
    assert "'7': '1'" in message


@pytest.mark.parametrize("server_url", ["http://runtime.test", None])
def test_one_shot_raw_queue_timeout_is_unknown_and_not_retried(
    server_url: str | None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    calls = 0
    async def timeout_queue(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise asyncio.TimeoutError("queue timeout")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: None)
    monkeypatch.setattr(runtime_run_module, "queue_server_prompt", timeout_queue)
    record, bundle = _approved(_workflow())
    with pytest.raises(TimeoutError):
        asyncio.run(runtime_run_module.run(record, bundle, server_url=server_url))
    _run_dir, attempt, events = _runtime_events(tmp_path, record)
    assert calls == 1
    assert attempt["queue_acceptance"]["status"] == "unknown"
    evidence = events[-1]["receipt"]["runtime_evidence"]
    assert evidence["queue_acceptance"]["status"] == "unknown"
    assert evidence["terminal"]["acceptance_known"] is False
    assert [event["event_type"] for event in events] == ["prepared", "discarded"]
    assert len([event for event in events if event["event_type"] == "discarded"]) == 1
    assert not any(event["event_type"] == "finalized" for event in events)
    assert evidence["terminal"] == {
        "phase": "queue",
        "reason_type": "TimeoutError",
        "reason": "queue timeout",
        "acceptance_known": False,
    }
    _assert_exact_runtime_record(attempt, record)
    _assert_exact_runtime_record(events[-1], record)


def test_one_shot_acceptance_witness_failure_is_nonretryable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    class FakeClient:
        def __init__(self, _url: str) -> None:
            pass
        async def _post_prompt(self, _prompt: dict) -> dict:
            return {"prompt_id": "one-shot-witness"}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: None)
    real_persist = session_module._persist_runtime_evidence
    calls = 0
    def fail_witness(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("witness disk full")
        return real_persist(*args, **kwargs)
    monkeypatch.setattr(session_module, "_persist_runtime_evidence", fail_witness)
    record, bundle = _approved(_workflow())
    with pytest.raises(QueueError, match="acceptance could not be recorded"):
        asyncio.run(runtime_run_module.run(record, bundle, server_url="http://runtime.test"))
    _run_dir, attempt, events = _runtime_events(tmp_path, record)
    assert calls == 2
    assert attempt["queue_acceptance"]["status"] == "unknown"
    assert attempt["queue_acceptance"]["prompt_id"] == "one-shot-witness"
    assert [event["event_type"] for event in events] == ["prepared", "discarded"]
    assert not any(event["event_type"] == "finalized" for event in events)
    _assert_exact_runtime_record(attempt, record)
    _assert_exact_runtime_record(events[-1], record)


def _run_one_shot_post_witness_failure(
    failure_kind: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    queue_calls = 0

    class FakeClient:
        def __init__(self, _url: str) -> None:
            pass

        async def _post_prompt(self, _prompt: dict) -> dict:
            nonlocal queue_calls
            queue_calls += 1
            return {"prompt_id": "post-witness"}

    async def history(_url: str, prompt_id: str | None, config=None):
        return _successful_history(prompt_id or "", {})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", history)
    record, bundle = _approved(_workflow())

    if failure_kind == "output":
        monkeypatch.setattr(
            runtime_run_module, "_artifact_records",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("output collection failed")),
        )
    elif failure_kind == "metadata":
        real_atomic = session_module.atomic_write_json

        def fail_metadata(path, value):
            if Path(path).name == "metadata.json":
                raise OSError("metadata disk full")
            return real_atomic(path, value)

        monkeypatch.setattr(session_module, "atomic_write_json", fail_metadata)
    elif failure_kind == "completed_attempt":
        real_persist = session_module._persist_runtime_evidence
        persist_calls = 0

        def fail_completed_attempt(*args, **kwargs):
            nonlocal persist_calls
            persist_calls += 1
            if persist_calls == 3:
                raise OSError("completion attempt disk full")
            return real_persist(*args, **kwargs)

        monkeypatch.setattr(session_module, "_persist_runtime_evidence", fail_completed_attempt)
        monkeypatch.setattr(runtime_run_module, "_persist_runtime_evidence", fail_completed_attempt)
    else:
        async def interrupted_history(*_args, **_kwargs):
            raise KeyboardInterrupt("interrupted after acceptance")

        monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", interrupted_history)

    expected_type = KeyboardInterrupt if failure_kind == "keyboard_interrupt" else (
        QueueError if failure_kind in {"metadata", "completed_attempt"} else OSError
    )
    with pytest.raises(expected_type) as exc_info:
        asyncio.run(runtime_run_module.run(record, bundle, server_url="http://runtime.test"))
    if failure_kind == "completed_attempt":
        assert isinstance(exc_info.value, QueueError)
        assert isinstance(exc_info.value.__cause__, OSError)

    run_dir, attempt, events = _runtime_events(tmp_path, record)
    assert queue_calls == 1
    if failure_kind == "completed_attempt":
        assert persist_calls == 4
    assert attempt["queue_acceptance"] == {"status": "accepted", "prompt_id": "post-witness"}
    assert len([event for event in events if event["event_type"] in {"discarded", "superseded"}]) == 1
    assert len(events) == 2
    assert events[-1]["receipt"]["runtime_evidence"]["queue_acceptance"] == attempt["queue_acceptance"]
    terminal = events[-1]["receipt"]["runtime_evidence"]["terminal"]
    if failure_kind == "output":
        assert terminal == {
            "phase": "output",
            "reason_type": "OSError",
            "reason": "output collection failed",
            "acceptance_known": True,
            "completion_status": "Incomplete — generation verified but retrieval failed",
        }
    elif failure_kind == "keyboard_interrupt":
        assert terminal == {
            "phase": "interrupted",
            "reason_type": "KeyboardInterrupt",
            "reason": "interrupted after acceptance",
            "acceptance_known": True,
        }
    else:
        assert terminal["phase"] == "metadata"
        assert terminal["reason_type"] == "QueueError"
        assert terminal["acceptance_known"] is True
    _assert_exact_runtime_record(attempt, record)
    _assert_exact_runtime_record(events[-1], record)
    assert not (run_dir / "metadata.json").exists()


@pytest.mark.parametrize("failure_kind", ["output", "metadata", "keyboard_interrupt"])
def test_one_shot_post_witness_failure_matrix(
    failure_kind: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _run_one_shot_post_witness_failure(failure_kind, monkeypatch, tmp_path)


def test_one_shot_completed_attempt_write_failure_is_nonretryable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _run_one_shot_post_witness_failure("completed_attempt", monkeypatch, tmp_path)


def test_one_shot_external_loaded_schema_provenance_is_retained(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    class FakeClient:
        def __init__(self, _url: str) -> None:
            pass
        async def _post_prompt(self, _prompt: dict) -> dict:
            return {"prompt_id": "external-schema"}

    async def history(_url: str, prompt_id: str | None, config=None):
        return _successful_history(prompt_id or "", {})

    from vibecomfy.schema import RuntimeSchemaProvider
    from vibecomfy.schema.cache import object_info_payload_checksum

    provider = RuntimeSchemaProvider(server_url="http://runtime.test")
    provider._object_info = {
        "SaveImage": {
            "input": {"required": {}, "optional": {}, "hidden": {}},
            "output": [], "output_name": [], "name": "SaveImage",
            "display_name": "SaveImage", "description": "",
        }
    }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: provider)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", history)
    record, bundle = _approved(_workflow())
    result = asyncio.run(runtime_run_module.run(record, bundle, server_url="http://runtime.test"))
    _run_dir, attempt, events = _runtime_events(tmp_path, record)
    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    for evidence in (attempt["runtime_evidence"], events[-1]["receipt"]["runtime_evidence"], metadata["runtime_evidence"]):
        assert evidence["adapter"]["kind"] == "external"
        assert evidence["schema_provenance"]["schema_digest"] == object_info_payload_checksum(dict(provider._object_info))
        assert evidence["schema_provenance"]["digest_canonicalization"] == "object_info_payload_checksum"
    _assert_exact_runtime_record(attempt, record)
    _assert_exact_runtime_record(events[-1], record)
    _assert_exact_runtime_record(metadata, record)


def test_runtime_terminal_recovery_reads_known_append_only_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    class FakeClient:
        def __init__(self, _url: str) -> None:
            pass
        async def _post_prompt(self, _prompt: dict) -> dict:
            return {"prompt_id": "recoverable"}

    async def history(_url: str, prompt_id: str | None, config=None):
        return _successful_history(prompt_id or "", {})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", history)
    record, bundle = _approved(_workflow())
    result = asyncio.run(runtime_run_module.run(record, bundle, server_url="http://runtime.test"))
    run_dir, _attempt, _events = _runtime_events(tmp_path, record)
    txn_dir = run_dir / "transactions" / record.api_digest
    (run_dir / "attempt.json").unlink()
    for name in ("prepared.json", "finalized.json"):
        path = txn_dir / name
        if path.exists():
            path.unlink()
    from vibecomfy.comfy_nodes.agent import _artifact_store as S
    recovered = S.read_transaction_lifecycle(txn_dir)
    assert recovered[-1]["event_type"] == "finalized"
    assert recovered[-1]["generation"] == recovered[0]["generation"]
    evidence = recovered[-1]["receipt"]["runtime_evidence"]
    assert evidence["api_digest"] == record.api_digest
    assert evidence["adapter"]["kind"] == "external"
    assert evidence["terminal"]["phase"] == "completed"
    _assert_exact_runtime_record(recovered[-1], record)
    assert result.prompt_id == "recoverable"


@pytest.mark.parametrize("failure", ["attempt", "journal"])
def test_run_initial_lifecycle_failure_is_visible_before_transport(
    failure: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    queue_calls: list[dict] = []

    class FakeClient:
        def __init__(self, _server_url: str) -> None:
            pass

        async def _post_prompt(self, payload: dict) -> dict:
            queue_calls.append(payload)
            return {"prompt_id": "must-not-queue"}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    if failure == "attempt":
        def fail_attempt(*_args, **_kwargs):
            raise OSError("attempt write failed")

        monkeypatch.setattr(
            session_module,
            "write_attempt_json",
            fail_attempt,
        )
    else:
        from vibecomfy.comfy_nodes.agent import _session_transaction_journal as journal

        def fail_prepare(*_args, **_kwargs):
            raise OSError("journal append failed")

        monkeypatch.setattr(journal, "record_prepared_transaction_impl", fail_prepare)

    with pytest.raises(QueueError, match="lifecycle could not be persisted"):
        asyncio.run(runtime_run_module.run(*_approved(_workflow())))
    assert queue_calls == []


def test_run_managed_server_uses_workflow_session_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured_configs = []

    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 5,
        "port": 8205,
    }

    @asynccontextmanager
    async def fake_server(*, server_url=None, log_path=None, config=None):
        captured_configs.append(config)
        yield "http://managed.test"

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def _post_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "prompt-managed"}

        async def history(self, prompt_id: str) -> dict:
            return _successful_history(prompt_id, {"9": {"filename": "managed.mp4"}})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(session_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    result = asyncio.run(runtime_run_module.run(*_approved(workflow), server_url=None))

    assert result.prompt_id == "prompt-managed"
    assert result.outputs == ["managed.mp4"]
    assert len(captured_configs) == 1
    config = captured_configs[0]
    assert config.memory_profile == 5
    assert config.port == 8205
    assert config.vram_policy == "low"
    assert config.cache_policy == "lru:1"
    assert config.reserve_vram_gb == 4.0
    assert config.disable_smart_memory is True


def test_run_external_server_does_not_apply_workflow_session_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured_configs = []
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {"memory_profile": 5}

    @asynccontextmanager
    async def fake_server(*, server_url=None, log_path=None, config=None):
        captured_configs.append(config)
        yield server_url

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def _post_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "prompt-external"}

        async def history(self, prompt_id: str) -> dict:
            return _successful_history(prompt_id, {"9": {"filename": "external.mp4"}})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(session_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    result = asyncio.run(runtime_run_module.run(*_approved(workflow), server_url="http://external.test"))

    assert result.prompt_id == "prompt-external"
    assert result.outputs == ["external.mp4"]
    assert result.log_path is None
    assert result.log_provenance == {
        "available": False,
        "kind": "external_server",
        "path": None,
        "reason": "Comfy server owns its logs; VibeComfy did not capture them.",
    }
    assert result.artifacts == [{
        "reported_path": "external.mp4",
        "filename": "external.mp4",
        "subfolder": "",
        "type": "output",
        "descriptor": {"filename": "external.mp4"},
        "source": "external_comfy_server",
        "location": "http://external.test/view?filename=external.mp4&subfolder=&type=output",
        "path": None,
    }]
    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    assert metadata["outputs"] == ["external.mp4"]
    assert metadata["artifacts"] == result.artifacts
    assert metadata["log_path"] is None
    assert metadata["log_provenance"] == result.log_provenance
    assert result.completion_path == str(Path(result.metadata_path).parent / "completion.json")
    completion = json.loads(Path(result.completion_path).read_text(encoding="utf-8"))
    attempt = json.loads((Path(result.metadata_path).parent / "attempt.json").read_text(encoding="utf-8"))
    assert attempt["status"] == result.status
    assert attempt["completion_status"] == result.status
    assert attempt["prompt_id"] == result.prompt_id
    assert attempt["metadata_path"] == result.metadata_path
    assert attempt["completion_path"] == result.completion_path
    assert attempt["outputs"] == result.outputs
    assert attempt["artifact_paths"] == result.outputs
    assert attempt["log_path"] == result.log_path
    assert attempt["log_provenance"] == result.log_provenance
    assert completion["run_id"] == result.run_id
    assert completion["prompt_id"] == result.prompt_id
    assert completion["status"] == "completed"
    assert completion["outputs"] == ["external.mp4"]
    assert completion["artifacts"] == result.artifacts
    assert completion["artifact_locations"] == [
        "http://external.test/view?filename=external.mp4&subfolder=&type=output"
    ]
    assert completion["log_path"] is None
    assert completion["log_provenance"] == result.log_provenance
    assert captured_configs == [None]


def test_external_log_locator_is_recorded_as_reference_only() -> None:
    provenance = session_module._log_provenance(
        None,
        "external",
        external_log_locator="ssh://runpod/workspace/comfyui-h3.log",
    )

    assert provenance == {
        "available": False,
        "kind": "external_server",
        "path": None,
        "locator": "ssh://runpod/workspace/comfyui-h3.log",
        "locator_kind": "configured_external_log",
        "reason": (
            "Comfy server owns its logs; VibeComfy did not capture them; "
            "the configured locator is a reference only."
        ),
    }


def test_artifact_records_keep_mixed_descriptors_and_paths_paired() -> None:
    descriptors_and_paths = {
        "node_with_descriptor": {
            "images": [{
                "filename": "remote.mp4",
                "subfolder": "clips",
                "type": "output",
            }],
        },
        "node_with_path_only": {"path": "/remote/second.png"},
    }

    artifacts = session_module._artifact_records(
        descriptors_and_paths,
        adapter_kind="external",
        adapter_endpoint="http://external.test",
    )

    assert [artifact["reported_path"] for artifact in artifacts] == [
        "clips/remote.mp4",
        "/remote/second.png",
    ]
    assert artifacts == [
        {
            "reported_path": "clips/remote.mp4",
            "filename": "remote.mp4",
            "subfolder": "clips",
            "type": "output",
            "descriptor": {
                "filename": "remote.mp4",
                "subfolder": "clips",
                "type": "output",
            },
            "source": "external_comfy_server",
            "location": "http://external.test/view?filename=remote.mp4&subfolder=clips&type=output",
            "path": None,
        },
        {
            "reported_path": "/remote/second.png",
            "filename": "second.png",
            "subfolder": "",
            "type": "output",
            "descriptor": None,
            "source": "external_comfy_server",
            "location": None,
            "path": None,
            "location_reason": "Comfy history returned a path without a retrievable output descriptor.",
        },
    ]


def test_artifact_records_deduplicate_comfy_video_descriptor_views() -> None:
    outputs = {
        "node": {
            "gifs": [{
                "filename": "continuation.mp4",
                "subfolder": "video",
                "type": "output",
                "format": "video/h264-mp4",
            }],
            "images": [{
                "filename": "continuation.mp4",
                "subfolder": "video",
                "type": "output",
            }],
            "animated": [True],
        }
    }

    entries = session_module._collect_output_entries(outputs)

    assert len(entries) == 1
    assert entries[0][0]["format"] == "video/h264-mp4"
    assert entries[0][0]["descriptor_sources"] == ["gifs", "images"]


def test_artifact_records_keep_distinct_nested_paths_and_reject_conflicts() -> None:
    outputs = {
        "gifs": [
            {"filename": "same.mp4", "subfolder": "video/a", "type": "output"},
            {"filename": "same.mp4", "subfolder": "video/b", "type": "output"},
        ],
    }

    entries = session_module._collect_output_entries(outputs)

    assert [path for _descriptor, path in entries] == [
        "video/a/same.mp4",
        "video/b/same.mp4",
    ]

    contradictory = {
        "gifs": [{
            "filename": "same.mp4",
            "subfolder": "video/a",
            "type": "output",
            "format": "video/h264-mp4",
        }],
        "images": [{
            "filename": "same.mp4",
            "subfolder": "video/a",
            "type": "output",
            "format": "image/gif",
        }],
    }
    with pytest.raises(RuntimeNodeError) as caught:
        session_module._collect_output_entries(contradictory)
    assert caught.value.diagnostics[0]["code"] == "conflicting_comfy_output_descriptors"


def test_nested_output_descriptor_resolves_under_configured_root_only(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    resolved = session_module._resolve_comfy_output_filename(
        {
            "filename": "masked_av_extension_00001-audio.mp4",
            "subfolder": "video/nested",
            "type": "output",
        },
        output_root,
    )

    assert Path(resolved) == output_root / "video/nested/masked_av_extension_00001-audio.mp4"
    with pytest.raises(RuntimeNodeError) as caught:
        session_module._resolve_comfy_output_filename(
            {"filename": "escape.mp4", "subfolder": "../outside", "type": "output"},
            output_root,
        )
    assert caught.value.diagnostics[0]["code"] == "unsafe_comfy_output_descriptor"


def test_embedded_configuration_uses_hiddenswitch_configuration_object(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeConfiguration(dict):
        def __getattr__(self, name: str):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

    def default_configuration() -> FakeConfiguration:
        return FakeConfiguration({"cwd": None, "reserve_vram": 0.0, "cache_none": False})

    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.default_configuration = default_configuration
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.setenv("VIBECOMFY_COMFY_CONFIGURATION", '{"reserve_vram":12,"cache_none":true}')

    config = runtime_run_module._embedded_configuration(_workflow())

    assert isinstance(config, FakeConfiguration)
    assert config.cwd is None
    assert config.reserve_vram == 12
    assert config.cache_none is True


def test_run_embedded_ignores_hiddenswitch_cleanup_bug_after_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FakeComfy:
        def __init__(self, configuration=None) -> None:
            self.configuration = configuration

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            raise AttributeError("'NoneType' object has no attribute 'model_mmap_residency'")

        async def queue_prompt_api(self, api_dict):
            return {"prompt_id": "embedded-cleanup", "outputs": {"1": {"filename": "output.mp4"}}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = FakeComfy
    embedded.default_configuration = lambda: {}
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)

    result = runtime_run_module.run_embedded_sync(*_approved(_workflow()))

    assert result.outputs == ["output.mp4"]


@pytest.mark.parametrize(
    "cleanup_error",
    [
        RuntimeError("cannot cancel futures in this implementation"),
        RuntimeError("Abnormal termination"),
    ],
)
def test_run_embedded_ignores_comfy_kitchen_cleanup_bug_after_success(
    cleanup_error: RuntimeError,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class FakeComfy:
        def __init__(self, configuration=None) -> None:
            self.configuration = configuration

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            raise cleanup_error

        async def queue_prompt_api(self, api_dict):
            return {"prompt_id": "embedded-cleanup", "outputs": {"1": {"filename": "output.mp4"}}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = FakeComfy
    embedded.default_configuration = lambda: {}
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)

    result = runtime_run_module.run_embedded_sync(*_approved(_workflow()))

    assert result.outputs == ["output.mp4"]


def test_run_embedded_resolves_comfy_filename_outputs_against_configured_output_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    output_dir = tmp_path / "standard-output"

    class FakeComfy:
        def __init__(self, configuration=None) -> None:
            self.configuration = configuration

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def queue_prompt_api(self, api_dict):
            return {
                "prompt_id": "embedded-output",
                "outputs": {
                    "19": {
                        "images": [
                            {
                                "filename": "Wanimate_00001_.mp4",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                }
            }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_COMFY_CONFIGURATION", f'{{"output_directory":"{output_dir}"}}')
    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = FakeComfy
    embedded.default_configuration = lambda: {}
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)

    record, bundle = _approved(_workflow())
    result = runtime_run_module.run_embedded_sync(record, bundle)

    assert result.outputs == [str(output_dir / "Wanimate_00001_.mp4")]
    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    assert metadata["runtime_evidence"]["approved_projection"] == record.to_dict()
    assert "approval_record" not in metadata
    assert "approved_projection" not in metadata
    assert metadata["api_digest"] == record.api_digest
    assert metadata["adapter"] == {
        "kind": "embedded",
        "backend": "api",
        "endpoint": metadata["adapter"]["endpoint"],
    }
    assert metadata["outputs"] == result.outputs
    assert metadata["artifact_paths"] == result.outputs
    assert metadata["artifact_manifest"] == {
        "schema_version": 1,
        "by_output": {},
        "unmapped": result.outputs,
        "attribution": [],
    }
    assert metadata["comfy_outputs"] == {
        "19": {
            "images": [
                {
                    "filename": "Wanimate_00001_.mp4",
                    "subfolder": "",
                    "type": "output",
                }
            ]
        }
    }
    assert metadata["compiled_prompt"]["1"]["inputs"]["filename_prefix"] == "test"


@pytest.mark.parametrize("runtime", ["embedded", "server", "external"])
def test_artifact_run_fails_closed_without_approved_record(runtime: str, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = _workflow()
    artifact = Artifact(workflow=workflow, node_id="1", output_slot=0, kind="image")
    monkeypatch.setattr("vibecomfy.runtime.run_embedded_sync", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("embedded transport reached")))
    monkeypatch.setattr("vibecomfy.runtime.run_sync", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("server transport reached")))
    with pytest.raises(WorkflowBundleError) as caught:
        artifact.run(runtime=runtime, chain_id="chain-1", parent_run_id="run-0")
    text = str(caught.value)
    assert "finalizing and approving a candidate" in text
    assert "ApprovedProjectionRecord" in text
    assert "WorkflowBundle" in text
    assert "run_embedded_sync(record, bundle)" in text
    assert "run_sync(record, bundle, server_url=...)" in text
    assert "vibecomfy import <source>" in text


def test_artifact_run_preserves_unknown_runtime_error() -> None:
    artifact = Artifact(workflow=_workflow(), node_id="1", output_slot=0, kind="image")
    with pytest.raises(ValueError, match="Unknown artifact runtime: local"):
        artifact.run(runtime="local")


def test_run_sync_forwards_chain_kwargs_to_async_run(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run(record, bundle, *, chain_id=None, parent_run_id=None, **kwargs):
        captured.update(
            {
                "record": record,
                "bundle": bundle,
                "chain_id": chain_id,
                "parent_run_id": parent_run_id,
                "kwargs": kwargs,
            }
        )
        return types.SimpleNamespace(run_id="run-sync")

    monkeypatch.setattr(runtime_run_module, "run", fake_run)

    workflow = _workflow()
    approved = _approved(workflow)
    result = runtime_run_module.run_sync(*approved, server_url="http://runtime.test", chain_id="chain-1", parent_run_id="run-0")

    assert result.run_id == "run-sync"
    assert captured == {
        "record": approved[0],
        "bundle": approved[1],
        "chain_id": "chain-1",
        "parent_run_id": "run-0",
        "kwargs": {
            "server_url": "http://runtime.test",
            "backend": "api",
            "config": None,
            "ensure_models": False,
            "shared_models_root": None,
            "strict_drift": None,
        },
    }


def test_run_embedded_sync_forwards_chain_kwargs_to_async_run_embedded(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_embedded(record, bundle, *, chain_id=None, parent_run_id=None, **kwargs):
        captured.update(
            {
                "record": record,
                "bundle": bundle,
                "chain_id": chain_id,
                "parent_run_id": parent_run_id,
                "kwargs": kwargs,
            }
        )
        return types.SimpleNamespace(run_id="run-embedded")

    monkeypatch.setattr(runtime_run_module, "run_embedded", fake_run_embedded)

    workflow = _workflow()
    approved = _approved(workflow)
    result = runtime_run_module.run_embedded_sync(*approved, chain_id="chain-1", parent_run_id="run-0")

    assert result.run_id == "run-embedded"
    assert captured == {
        "record": approved[0],
        "bundle": approved[1],
        "chain_id": "chain-1",
        "parent_run_id": "run-0",
        "kwargs": {
            "backend": "api",
            "config": None,
            "ensure_packs": False,
            "ensure_models": False,
            "strict_drift": None,
        },
    }


def test_run_passes_chain_kwargs_into_metadata_writer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def _post_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "prompt-chain"}

        async def history(self, prompt_id: str) -> dict:
            return _successful_history(prompt_id, {"9": {"filename": "chain.mp4"}})

    def fake_run_metadata(**kwargs):
        captured.update(kwargs)
        return {"run_id": kwargs["run_id"], "outputs": kwargs["outputs"]}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(session_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)
    monkeypatch.setattr(runtime_run_module, "_run_metadata", fake_run_metadata)

    result = asyncio.run(
        runtime_run_module.run(
            *_approved(_workflow()),
            server_url="http://runtime.test",
            chain_id="chain-1",
            parent_run_id="run-0",
        )
    )

    assert result.prompt_id == "prompt-chain"
    assert captured["chain_id"] == "chain-1"
    assert captured["parent_run_id"] == "run-0"


def test_cmd_run_prints_clear_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="embedded",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )

    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *args, **kwargs: None)
    handoff: list[tuple[object, object]] = []
    def fake_embedded(record, bundle, **kwargs):
        handoff.append((record, bundle))
        return types.SimpleNamespace(run_id="r", prompt_id="p", metadata_path="m")
    monkeypatch.setattr("vibecomfy.commands.run.run_embedded_sync", fake_embedded)
    assert _cmd_run(args) == 0
    captured = capsys.readouterr()
    assert "run_id: r" in captured.out
    assert "prompt_id: p" in captured.out
    assert "metadata_path: m" in captured.out
    assert captured.err == ""
    assert len(handoff) == 1
    assert handoff[0][0].revision_id == handoff[0][1].revision_id


def test_cmd_run_json_surfaces_outputs_and_external_log_provenance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="server",
        server_url="http://external.test",
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        json=True,
    )

    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_sync",
        lambda *args, **kwargs: types.SimpleNamespace(
            run_id="r",
            prompt_id="p",
            outputs=["external.mp4"],
            artifacts=[{"location": "http://external.test/view?filename=external.mp4"}],
            metadata_path="m",
            completion_path="completion.json",
            log_path=None,
            log_provenance={"kind": "external_server", "available": False, "path": None},
            status="completed",
            media_validated=False,
        ),
    )

    assert _cmd_run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["queue_status"] == "accepted"
    assert payload["media_validated"] is False
    assert payload["outputs"] == ["external.mp4"]
    assert payload["artifacts"] == [{"location": "http://external.test/view?filename=external.mp4"}]
    assert payload["completion_path"] == "completion.json"
    assert payload["log_path"] is None
    assert payload["log_provenance"]["kind"] == "external_server"


def test_cmd_run_text_agrees_with_unavailable_log_provenance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="embedded",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        json=False,
    )

    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda *args, **kwargs: types.SimpleNamespace(
            run_id="r",
            prompt_id="p",
            outputs=[],
            artifacts=[],
            metadata_path="m",
            log_path=None,
            log_provenance={"kind": "vibecomfy_captured_file", "available": False, "path": None},
            status="completed",
            media_validated=False,
        ),
    )

    assert _cmd_run(args) == 0
    output = capsys.readouterr().out
    assert "log_path: unavailable (captured process log is unavailable)" in output
    assert "external server owns its logs" not in output


def test_cmd_logs_surfaces_completion_record(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir = tmp_path / "out" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    completion = {
        "run_id": "run-1",
        "prompt_id": "prompt-1",
        "status": "completed",
        "artifact_locations": ["http://external.test/view?filename=clip.mp4"],
        "log_provenance": {"kind": "external_server", "available": False},
    }
    (run_dir / "completion.json").write_text(json.dumps(completion), encoding="utf-8")

    assert _cmd_logs(argparse.Namespace(run_id="run-1", tail=4000)) == 0
    output = capsys.readouterr().out
    assert "== out/runs/run-1/completion.json ==" in output
    assert "http://external.test/view?filename=clip.mp4" in output
    assert "external_server" in output


def test_cmd_run_auto_uses_active_session_for_schema_and_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="auto",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    schema_calls: list[tuple[str, str | None]] = []
    loaded_schema_providers: list[object] = []
    run_calls: list[tuple[object, object, str | None, str]] = []
    provider = None

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: "http://warm.test")

    def fake_schema_provider(prefer: str, *, server_url: str | None = None):
        schema_calls.append((prefer, server_url))
        return provider

    def fake_load_workflow_reference(*args, **kwargs):
        loaded_schema_providers.append(kwargs["schema_provider"])
        return _workflow()

    def fake_run_sync(record: object, bundle: object, *, server_url: str | None, backend: str, **kwargs):
        run_calls.append((record, bundle, server_url, backend))
        return types.SimpleNamespace(
            run_id="run-1",
            prompt_id="prompt-1",
            outputs=[],
            metadata_path="metadata.json",
            log_path="comfy.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", fake_schema_provider)
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())
    monkeypatch.setattr("vibecomfy.commands.run.run_sync", fake_run_sync)
    assert _cmd_run(args) == 0

    assert schema_calls == [("auto", "http://warm.test")]
    assert not loaded_schema_providers
    assert len(run_calls) == 1
    record, bundle, route_url, route_backend = run_calls[0]
    assert record.revision_id == bundle.revision_id
    assert route_url == "http://warm.test"
    assert route_backend == "api"
    assert capsys.readouterr().err == ""


def test_cmd_run_consumes_named_runpod_binding_endpoint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="auto",
        server_url=None,
        session="migration",
        runtime_root=str(tmp_path),
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    run_calls: list[dict[str, object]] = []
    monkeypatch.setattr("vibecomfy.commands.run.active_session_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.load_binding",
        lambda *args, **kwargs: {
            "pod_id": "pod-123",
            "comfy_root": "/workspace/ComfyUI",
            "python_executable": "/workspace/ComfyUI/.venv/bin/python",
            "comfy_url": "https://pod-123-8188.proxy.runpod.net",
            "launch_flags": ["--use-ck-attention"],
        },
    )
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())

    def fake_run_sync(record, bundle, **kwargs):
        run_calls.append(kwargs)
        return types.SimpleNamespace(
            run_id="run-bound",
            prompt_id="prompt-bound",
            outputs=[],
            artifacts=[],
            metadata_path="metadata.json",
            log_path=None,
            log_provenance={"available": False},
            status="completed",
            media_validated=False,
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_sync", fake_run_sync)
    assert _cmd_run(args) == 0
    assert run_calls[0]["server_url"] == "https://pod-123-8188.proxy.runpod.net"
    target = run_calls[0]["runtime_target"]
    assert target["pod_id"] == "pod-123"
    assert target["python_executable"] == "/workspace/ComfyUI/.venv/bin/python"
    assert target["_runpod_lifecycle_adapter"].describe()["provider"] == "runpod_lifecycle"
    assert capsys.readouterr().err == ""


def test_cmd_run_routes_local_source_preparation_to_bound_lifecycle_coordinator(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "workflow.py"
    source.write_text("# remote workflow is already staged on the pod\n", encoding="utf-8")
    args = argparse.Namespace(
        path=str(source),
        ready=True,
        runtime="auto",
        server_url=None,
        session="migration",
        runtime_root=str(tmp_path),
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        deps="sync",
        ensure_models=False,
        json=False,
    )
    prepare_calls: list[dict[str, object]] = []

    class FakeLifecycleAdapter:
        def __init__(self, binding, *, session_id):
            assert binding["pod_id"] == "pod-123"
            assert session_id == "migration"

        def prepare(self, **kwargs):
            prepare_calls.append(kwargs)
            return {"provider": "runpod_lifecycle", "status": "prepared"}

        def describe(self):
            return {"provider": "runpod_lifecycle", "status": "attached"}

    monkeypatch.setattr("vibecomfy.commands.runpod.BoundRunPodLifecycleAdapter", FakeLifecycleAdapter)
    monkeypatch.setattr("vibecomfy.commands.run.active_session_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.load_binding",
        lambda *args, **kwargs: {
            "pod_id": "pod-123",
            "remote": True,
            "comfy_root": "/workspace/runpod-slim/ComfyUI",
            "python_executable": "/workspace/runpod-slim/ComfyUI/.venv/bin/python",
            "comfy_url": "https://pod-123-8188.proxy.runpod.net",
            "remote_workflow": "/workspace/workflows/workflow.py",
        },
    )
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())

    def fake_run_sync(record, bundle, **kwargs):
        return types.SimpleNamespace(
            run_id="run-bound-prepared",
            prompt_id="prompt-bound-prepared",
            outputs=[],
            artifacts=[],
            metadata_path="metadata.json",
            log_path=None,
            log_provenance={"available": False},
            status="completed",
            media_validated=False,
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_sync", fake_run_sync)
    assert _cmd_run(args) == 0
    assert len(prepare_calls) == 1
    assert prepare_calls[0]["dependency_mode"] == "sync"
    assert prepare_calls[0]["runtime_target"]["python_executable"].endswith("/python")
    assert "status: completed" in capsys.readouterr().out


def test_cmd_run_auto_without_active_session_falls_back_to_embedded(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="auto",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    schema_calls: list[tuple[str, str | None]] = []
    embedded_calls: list[tuple[object, object, dict]] = []

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.get_schema_provider",
        lambda prefer, *, server_url=None: schema_calls.append((prefer, server_url)) or None,
    )
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())
    def fake_run_embedded_sync(record: object, bundle: object, **kwargs):
        embedded_calls.append((record, bundle, kwargs))
        return types.SimpleNamespace(
            run_id="run-embedded",
            prompt_id="prompt-embedded",
            outputs=[],
            metadata_path="metadata.json",
            log_path="embedded.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_embedded_sync", fake_run_embedded_sync)
    assert _cmd_run(args) == 0

    assert schema_calls == [("auto", None)]
    assert len(embedded_calls) == 1
    assert embedded_calls[0][0].revision_id == embedded_calls[0][1].revision_id
    assert capsys.readouterr().err == ""


def test_cmd_run_server_without_active_session_starts_one_shot_managed_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="server",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    run_calls: list[tuple[object, object, str | None, str]] = []

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.get_schema_provider",
        lambda prefer, *, server_url=None: None,
    )
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())

    def fake_run_sync(record: object, bundle: object, *, server_url: str | None, backend: str, **kwargs):
        run_calls.append((record, bundle, server_url, backend))
        return types.SimpleNamespace(
            run_id="run-managed",
            prompt_id="prompt-managed",
            outputs=[],
            metadata_path="metadata.json",
            log_path="comfy.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_sync", fake_run_sync)
    assert _cmd_run(args) == 0

    assert len(run_calls) == 1
    record, bundle, route_url, route_backend = run_calls[0]
    assert record.revision_id == bundle.revision_id
    assert route_url is None
    assert route_backend == "api"
    assert capsys.readouterr().err == ""


def test_cmd_run_memory_profile_overrides_embedded_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="embedded",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=5,
    )
    embedded_configs: list[tuple[object, object, SessionConfig]] = []

    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda prefer, *, server_url=None: None)
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())

    def fake_run_embedded_sync(
        workflow: VibeWorkflow,
        bundle: object,
        *,
        backend: str,
        config: SessionConfig,
        ensure_models: bool,
        **kwargs,
    ):
        assert backend == "api"
        assert ensure_models is False
        embedded_configs.append((workflow, bundle, config))
        return types.SimpleNamespace(
            run_id="run-embedded",
            prompt_id="prompt-embedded",
            outputs=[],
            metadata_path="metadata.json",
            log_path="embedded.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_embedded_sync", fake_run_embedded_sync)
    assert _cmd_run(args) == 0
    assert len(embedded_configs) == 1
    assert embedded_configs[0][2].memory_profile == 5
    assert embedded_configs[0][0].revision_id == embedded_configs[0][1].revision_id


def test_cmd_run_memory_profile_overrides_new_managed_server_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="server",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=5,
    )
    server_configs: list[tuple[object, object, SessionConfig]] = []

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda prefer, *, server_url=None: None)
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *args, **kwargs: _command_bundle())

    def fake_run_sync(
        workflow: VibeWorkflow,
        bundle: object,
        *,
        server_url: str | None,
        backend: str,
        config: SessionConfig,
        **kwargs,
    ):
        server_configs.append((workflow, bundle, config))
        return types.SimpleNamespace(
            run_id="run-managed",
            prompt_id="prompt-managed",
            outputs=[],
            metadata_path="metadata.json",
            log_path="comfy.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_sync", fake_run_sync)
    assert _cmd_run(args) == 0
    assert len(server_configs) == 1
    assert server_configs[0][2].memory_profile == 5
    assert server_configs[0][0].revision_id == server_configs[0][1].revision_id


def test_cmd_run_memory_profile_rejects_explicit_external_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="server",
        server_url="http://external.test",
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=5,
    )

    monkeypatch.setattr(
        "vibecomfy.commands.run.load_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("workflow should not load")),
    )

    assert _cmd_run(args) == 2

    assert "requires a new local VibeComfy runtime" in capsys.readouterr().err


def test_cmd_run_memory_profile_rejects_active_session(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="server",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=5,
    )

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: "http://warm.test")
    monkeypatch.setattr(
        "vibecomfy.commands.run.load_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("workflow should not load")),
    )

    assert _cmd_run(args) == 2

    assert "Stop/restart the session" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# T7: eval-node tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T5: drift tests
# ---------------------------------------------------------------------------


def test_attempt_lockfile_snapshot_reads_current_toml(tmp_path, monkeypatch):
    """Attempt evidence snapshots the TOML lock rather than JSON-decoding it."""
    from vibecomfy.runtime.attempt import _read_lockfile_snapshot

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "vibecomfy.node_packs.resolve_lockfile_path",
        lambda path=None: tmp_path / (path or "custom_nodes.lock"),
    )
    Path("custom_nodes.lock").write_text(
        '[nodepacks.Example]\nname = "Example"\ncommit = "abc123"\nurl = "https://example.test/example.git"\n',
        encoding="utf-8",
    )

    snapshot = _read_lockfile_snapshot()
    assert snapshot == {
        "nodepacks": {
            "Example": {
                "name": "Example",
                "slug": "Example",
                "source": "git",
                "commit": "abc123",
                "git_commit_sha": "abc123",
                "url": "https://example.test/example.git",
            }
        }
    }


def test_collect_drift_no_lockfile(tmp_path, monkeypatch):
    """When lockfile is missing, collect_drift reports 'lockfile not found'."""
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "vibecomfy.node_packs.resolve_lockfile_path",
        lambda path=None: tmp_path / (path or "custom_nodes.lock"),
    )
    monkeypatch.setattr(
        "vibecomfy.runtime.drift.resolve_lockfile_path",
        lambda path=None: tmp_path / (path or "custom_nodes.lock"),
    )
    wf = VibeWorkflow("drift-no-lock", WorkflowSource("drift-no-lock"))
    wf.requirements.custom_nodes = ["some-pack"]

    _invalidate_cache_entry(wf)
    result = collect_drift(wf)
    assert result["actual"]["custom_node_packs"] == "lockfile not found"
    assert result["pinned"]["custom_node_packs"] == ["some-pack"]
    assert result["mismatches"] == []


def test_collect_drift_pinned_comfy_commit(tmp_path, monkeypatch):
    """Workflow.metadata comfy_commit pinned vs observed."""
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-comfy", WorkflowSource("drift-comfy"))
    wf.metadata["comfy_commit"] = "abc123def"

    # Mock _comfyui_git_head to return a different commit
    monkeypatch.setattr(
        "vibecomfy.runtime.drift._comfyui_git_head",
        lambda: "xyz789",
    )

    _invalidate_cache_entry(wf)
    result = collect_drift(wf)
    assert result["pinned"]["comfy_commit"] == "abc123def"
    assert result["actual"]["comfy_commit"] == "xyz789"
    assert any("ComfyUI commit" in m for m in result["mismatches"])


def test_collect_drift_uses_known_comfy_core_commit_fallback(tmp_path, monkeypatch):
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-comfy-core", WorkflowSource("drift-comfy-core"))
    wf.metadata["comfy_core"] = {"commit": "core-pinned"}
    monkeypatch.setattr("vibecomfy.runtime.drift._comfyui_git_head", lambda: "different")

    _invalidate_cache_entry(wf)
    result = collect_drift(wf)
    assert result["pinned"]["comfy_commit"] == "core-pinned"
    assert any("pinned core-pinned" in m for m in result["mismatches"])


def test_collect_drift_ignores_unknown_comfy_core_commit(tmp_path, monkeypatch):
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-comfy-unknown", WorkflowSource("drift-comfy-unknown"))
    wf.metadata["comfy_core"] = {"commit": "unknown"}
    monkeypatch.setattr("vibecomfy.runtime.drift._comfyui_git_head", lambda: "different")

    _invalidate_cache_entry(wf)
    result = collect_drift(wf)
    assert result["pinned"]["comfy_commit"] is None
    assert not any("ComfyUI commit" in m for m in result["mismatches"])


def test_collect_drift_canonical_schema_hash_match_is_not_mismatch(tmp_path, monkeypatch):
    """Canonical object_info metadata is comparable and matching hashes pass."""
    from vibecomfy.node_packs import LockEntry, compute_schema_hash
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift
    import vibecomfy.porting.object_info as object_info

    monkeypatch.chdir(tmp_path)
    pack_dir = tmp_path / "vendor" / "ExamplePack"
    (pack_dir / ".git").mkdir(parents=True)
    schema = {
        "ExampleNode": {
            "pack_slug": "example-pack",
            "git_commit": "abc123",
            "inputs": {"required": {"value": ["INT", {"default": 1}]}},
            "input_order": {"required": ["value"]},
            "outputs": [{"name": "INT", "type": "INT", "is_list": False}],
        }
    }
    expected_hash = compute_schema_hash(schema)
    schema["ExampleNode"]["schema_hash"] = expected_hash
    schema["ExampleNode"]["class_schema_sha256"] = expected_hash
    entry = LockEntry(
        name="ExamplePack",
        git_commit_sha="abc123",
        slug="example-pack",
        class_set=("ExampleNode",),
        class_schema_sha256=expected_hash,
    )

    monkeypatch.setattr("vibecomfy.runtime.drift.read_lockfile", lambda: [entry], raising=False)
    monkeypatch.setattr("vibecomfy.node_packs.read_lockfile", lambda path=None: [entry])
    monkeypatch.setattr("vibecomfy.runtime.drift._nodepack_dir", lambda name: pack_dir)
    monkeypatch.setattr("vibecomfy.runtime.drift._git_head", lambda path: "abc123")
    monkeypatch.setattr(
        object_info,
        "get_class_by_identity",
        lambda class_type, *, pack_slug, git_commit=None, evidence_identity=None: schema[class_type],
    )

    wf = VibeWorkflow("drift-canonical", WorkflowSource("drift-canonical"))
    _invalidate_cache_entry(wf)
    result = collect_drift(wf)

    pack_info = result["actual"]["custom_node_packs"]["ExamplePack"]
    assert pack_info["schema_hash_status"] == "canonical"
    assert pack_info["actual_schema_hash"] == expected_hash
    assert result["mismatches"] == []


def test_collect_drift_legacy_schema_hash_is_unverified_not_mismatch(tmp_path, monkeypatch):
    """Legacy lockfile hashes without class_set are not compared as canonical hashes."""
    from vibecomfy.node_packs import LockEntry
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift

    monkeypatch.chdir(tmp_path)
    pack_dir = tmp_path / "vendor" / "LegacyPack"
    (pack_dir / ".git").mkdir(parents=True)
    (pack_dir / "node.py").write_text("changed schema source", encoding="utf-8")
    entry = LockEntry(
        name="LegacyPack",
        git_commit_sha="abc123",
        class_schema_sha256="legacy-file-byte-hash",
    )

    monkeypatch.setattr("vibecomfy.node_packs.read_lockfile", lambda path=None: [entry])
    monkeypatch.setattr("vibecomfy.runtime.drift._nodepack_dir", lambda name: pack_dir)
    monkeypatch.setattr("vibecomfy.runtime.drift._git_head", lambda path: "abc123")

    wf = VibeWorkflow("drift-legacy", WorkflowSource("drift-legacy"))
    _invalidate_cache_entry(wf)
    result = collect_drift(wf)

    pack_info = result["actual"]["custom_node_packs"]["LegacyPack"]
    assert pack_info["schema_hash_status"] == "unverified_legacy"
    assert "actual_schema_hash" not in pack_info
    assert result["mismatches"] == []


def test_enforce_strict_drift_raises_on_mismatch(tmp_path, monkeypatch):
    """enforce_strict_drift raises DriftError when mismatches exist."""
    from vibecomfy.runtime.drift import _invalidate_cache_entry, enforce_strict_drift
    from vibecomfy.errors import DriftError

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-strict", WorkflowSource("drift-strict"))
    wf.metadata["comfy_commit"] = "pinned-commit"

    monkeypatch.setattr(
        "vibecomfy.runtime.drift._comfyui_git_head",
        lambda: "different-commit",
    )

    _invalidate_cache_entry(wf)
    with pytest.raises(DriftError, match="Pre-queue drift check failed"):
        enforce_strict_drift(wf)


def test_enforce_strict_drift_passes_without_mismatch(tmp_path, monkeypatch):
    """enforce_strict_drift does nothing when no mismatches exist."""
    from vibecomfy.runtime.drift import _invalidate_cache_entry, enforce_strict_drift

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-ok", WorkflowSource("drift-ok"))

    _invalidate_cache_entry(wf)
    # Should not raise
    enforce_strict_drift(wf)


def test_drift_caching(tmp_path, monkeypatch):
    """Per-process caching prevents repeated filesystem/git calls."""
    import vibecomfy.runtime.drift as drift_module

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-cache", WorkflowSource("drift-cache"))

    call_count = [0]
    original = getattr(drift_module, "_comfyui_git_head", None)

    def counting_git_head():
        call_count[0] += 1
        return None

    monkeypatch.setattr(drift_module, "_comfyui_git_head", counting_git_head)
    drift_module._invalidate_cache_entry(wf)

    result1 = drift_module.collect_drift(wf)
    result2 = drift_module.collect_drift(wf)
    # Second call should hit the cache, so the git head function is called only once
    assert result1 is result2
    assert call_count[0] == 1


def test_session_config_strict_drift_default():
    """SessionConfig.strict_drift defaults to False."""
    config = SessionConfig()
    assert config.strict_drift is False


def test_session_config_strict_drift_explicit():
    """SessionConfig.strict_drift can be set explicitly."""
    config = SessionConfig(strict_drift=True)
    assert config.strict_drift is True


# ---------------------------------------------------------------------------
# T21: normalize_prompt_id queue return shape tests
# ---------------------------------------------------------------------------
# normalize_prompt_id must extract prompt_id from both dict and object queue
# return shapes.  Each path that writes RunResult.prompt_id or metadata must
# be covered.
# ---------------------------------------------------------------------------


def _make_one_shot_run_wf() -> VibeWorkflow:
    """Minimal workflow usable in one-shot run tests."""
    wf = VibeWorkflow("one-shot-test", WorkflowSource("one-shot-test"))
    wf.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "t21"})
    return wf


class _ObjectQueueResult:
    """Simulates a queue result returned as an object (attribute access)."""

    def __init__(self, prompt_id: str, outputs: list | None = None) -> None:
        self.prompt_id = prompt_id
        self.outputs = outputs or []


def test_normalize_prompt_id_dict_shape() -> None:
    """normalize_prompt_id extracts prompt_id from a dict return."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    result = normalize_prompt_id({"prompt_id": "abc-123", "extra": "ignored"})
    assert result == "abc-123"


def test_normalize_prompt_id_object_shape() -> None:
    """normalize_prompt_id extracts prompt_id from an object return."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    result = normalize_prompt_id(_ObjectQueueResult("obj-456"))
    assert result == "obj-456"


def test_normalize_prompt_id_dict_missing_key() -> None:
    """normalize_prompt_id returns None when prompt_id key absent in dict."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    assert normalize_prompt_id({}) is None
    assert normalize_prompt_id({"other": "x"}) is None


def test_normalize_prompt_id_object_missing_attr() -> None:
    """normalize_prompt_id returns None when object lacks prompt_id attr."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    class _NoId:
        pass

    assert normalize_prompt_id(_NoId()) is None


def test_normalize_prompt_id_numeric_coerced_to_str() -> None:
    """normalize_prompt_id stringifies numeric prompt_ids for both shapes."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    assert normalize_prompt_id({"prompt_id": 7}) == "7"

    class _NumId:
        prompt_id = 99

    assert normalize_prompt_id(_NumId()) == "99"


def test_one_shot_run_dict_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One-shot run path: dict queue result → RunResult.prompt_id via normalize_prompt_id."""

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _DictClient:
        def __init__(self, server_url: str) -> None:
            pass

        async def _post_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "dict-prompt-id"}

        async def history(self, prompt_id: str) -> dict:
            return _successful_history(prompt_id, {})

    async def _fake_history_dict(url: str, pid: str | None, config=None) -> dict:
        return _successful_history(pid, {}) if pid else {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _DictClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", _fake_history_dict)

    result = asyncio.run(runtime_run_module.run(*_approved(_make_one_shot_run_wf())))
    assert result.prompt_id == "dict-prompt-id"


def test_bound_runpod_uses_lifecycle_adapter_and_same_attempt_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "https://pod-123-8188.proxy.runpod.net"

    class FakeLifecycleAdapter:
        calls: list[str] = []

        def describe(self):
            return {
                "provider": "runpod_lifecycle",
                "operation": "attach/status/download",
                "pod_id": "pod-123",
                "status": "not_attached",
            }

        async def attach(self):
            self.calls.append("attach")
            return {
                "provider": "runpod_lifecycle",
                "operation": "attach/status/download",
                "pod_id": "pod-123",
                "status": "attached",
                "desired_status": "RUNNING",
                "actual_status": "RUNNING",
            }

        async def download_artifacts(self, *, local_root: Path):
            self.calls.append("download")
            output = local_root / "output" / "final.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fixture")
            return {
                "provider": "runpod_lifecycle",
                "status": "retrieved",
                "remote_root": "/workspace/ComfyUI",
                "artifact_paths": ["output", "out"],
                "local_root": str(local_root),
            }

        async def capture_log(self, *, local_path: Path):
            self.calls.append("log")
            return {
                "provider": "runpod_lifecycle",
                "status": "unavailable",
                "remote_path": "/workspace/ComfyUI/comfy.log",
                "local_path": None,
                "reason": "fixture has no remote log",
            }

    class FakeClient:
        def __init__(self, _server_url: str) -> None:
            pass

        async def _post_prompt(self, _prompt: dict) -> dict:
            return {"prompt_id": "lifecycle-prompt"}

    async def fake_history(_url: str, prompt_id: str | None, config=None) -> dict:
        return _successful_history(
            prompt_id,
            {"1": {"images": [{"filename": "final.png", "subfolder": "", "type": "output"}]}}
        ) if prompt_id else {}

    adapter = FakeLifecycleAdapter()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", fake_history)

    workflow = _make_one_shot_run_wf()
    workflow.outputs = [VibeOutput("1", "SaveImage", name="final")]
    result = asyncio.run(
        runtime_run_module.run(
            *_approved(workflow),
            server_url="https://pod-123-8188.proxy.runpod.net",
            runtime_target={"managed": True, "_runpod_lifecycle_adapter": adapter},
        )
    )

    assert adapter.calls == ["attach", "download", "log"]
    run_dir = Path(result.metadata_path).parent
    attempt = json.loads((run_dir / "attempt.json").read_text(encoding="utf-8"))
    assert attempt["adapter"]["kind"] == "runpod_lifecycle"
    assert attempt["adapter"]["lifecycle"]["status"] == "attached"
    assert attempt["lifecycle_retrieval"]["status"] == "retrieved"
    assert attempt["prompt_id"] == "lifecycle-prompt"
    assert attempt["completion_path"] == result.completion_path
    assert result.artifacts[0]["path"].endswith("downloaded-artifacts/output/final.png")
    assert attempt["artifacts"][0]["path"] == result.artifacts[0]["path"]


def test_bound_runpod_retrieval_failure_preserves_generation_and_delivery_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    queue_calls: list[str] = []

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "https://pod-123-8188.proxy.runpod.net"

    class FakeLifecycleAdapter:
        async def attach(self):
            return {"provider": "runpod_lifecycle", "pod_id": "pod-123", "status": "attached"}

        async def download_artifacts(self, *, local_root: Path):
            raise OSError("archive connection closed")

        async def capture_log(self, *, local_path: Path):
            local_path.write_text("render completed before retrieval failed", encoding="utf-8")
            return {
                "provider": "runpod_lifecycle",
                "status": "captured",
                "remote_path": "/workspace/ComfyUI/comfy.log",
                "local_path": str(local_path),
            }

    class FakeClient:
        def __init__(self, _server_url: str) -> None:
            pass

        async def _post_prompt(self, _prompt: dict) -> dict:
            queue_calls.append("queue")
            return {"prompt_id": "generated-prompt"}

    async def fake_history(_url: str, prompt_id: str | None, config=None) -> dict:
        return _successful_history(
            prompt_id,
            {"1": {"gifs": [{
                "filename": "final.mp4",
                "subfolder": "video/nested",
                "type": "output",
            }]}},
        ) if prompt_id else {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", fake_history)

    workflow = _make_one_shot_run_wf()
    workflow.outputs = [VibeOutput("1", "SaveImage", name="final")]
    with pytest.raises(RuntimeNodeError, match="retrieval failed") as caught:
        asyncio.run(
            runtime_run_module.run(
                *_approved(workflow),
                server_url="https://pod-123-8188.proxy.runpod.net",
                runtime_target={
                    "managed": True,
                    "_runpod_lifecycle_adapter": FakeLifecycleAdapter(),
                },
            )
        )

    assert queue_calls == ["queue"]
    assert caught.value.completion_status == "Incomplete — generation verified but retrieval failed"
    assert caught.value.delivery_state["execution"]["status"] == "succeeded"
    assert caught.value.delivery_state["retrieval"]["status"] == "failed"
    attempt_path = Path(caught.value.receipt_path)
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    assert attempt["prompt_id"] == "generated-prompt"
    assert attempt["completion_status"] == "Incomplete — generation verified but retrieval failed"
    assert attempt["terminal"]["execution_state"] == "succeeded"
    assert attempt["terminal"]["verification_state"] == "pending"
    assert attempt["terminal"]["retrieval_state"] == "failed"
    assert attempt["artifacts"][0]["reported_path"] == "video/nested/final.mp4"
    assert attempt["log_path"].endswith("runpod-comfy.log")


def test_retry_delivery_reuses_attempt_without_queueing(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "out/runs/run-existing"
    run_dir.mkdir(parents=True)
    attempt_path = run_dir / "attempt.json"
    attempt_path.write_text(json.dumps({
        "queue_acceptance": {"status": "accepted", "prompt_id": "existing-prompt"},
        "terminal": {
            "phase": "retrieval",
            "completion_status": "Incomplete — generation verified but retrieval failed",
        },
        "adapter": {"kind": "runpod_lifecycle"},
        "artifacts": [{
            "reported_path": "video/nested/final.mp4",
            "filename": "final.mp4",
            "subfolder": "video/nested",
            "type": "output",
            "location": "https://pod.test/view?filename=final.mp4&subfolder=video%2Fnested&type=output",
            "path": None,
        }],
        "delivery_state": {
            "execution": {"status": "succeeded"},
            "verification": {"status": "pending"},
            "retrieval": {"status": "failed"},
            "retryable": True,
        },
    }), encoding="utf-8")

    class RetryAdapter:
        calls: list[str] = []

        async def attach(self):
            self.calls.append("attach")
            return {"provider": "runpod_lifecycle", "status": "attached"}

        async def download_artifacts(self, *, local_root: Path):
            self.calls.append("download")
            target = local_root / "output/video/nested/final.mp4"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"existing generation")
            return {"status": "retrieved", "local_root": str(local_root)}

        async def capture_log(self, *, local_path: Path):
            self.calls.append("log")
            local_path.write_text("existing prompt log", encoding="utf-8")
            return {"status": "captured", "local_path": str(local_path)}

    adapter = RetryAdapter()
    result = asyncio.run(
        runtime_run_module.retry_delivery(attempt_path, lifecycle_adapter=adapter)
    )

    assert adapter.calls == ["attach", "download", "log"]
    assert result["prompt_id"] == "existing-prompt"
    assert result["delivery_state"]["retrieval"]["status"] == "succeeded"
    assert result["artifacts"][0]["path"].endswith(
        "downloaded-artifacts/output/video/nested/final.mp4"
    )
    updated = json.loads(attempt_path.read_text(encoding="utf-8"))
    assert updated["queue_acceptance"]["prompt_id"] == "existing-prompt"
    assert updated["terminal"]["phase"] == "delivery_retry"
    assert updated["terminal"]["retrieval_state"] == "succeeded"


def test_one_shot_run_object_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One-shot run path: object queue result → RunResult.prompt_id via normalize_prompt_id."""

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _ObjectClient:
        def __init__(self, server_url: str) -> None:
            pass

        async def _post_prompt(self, prompt: dict) -> _ObjectQueueResult:
            return _ObjectQueueResult("obj-prompt-id")

        async def history(self, prompt_id: str) -> dict:
            return _successful_history(prompt_id, {})

    async def _fake_history_obj(url: str, pid: str | None, config=None) -> dict:
        return _successful_history(pid, {}) if pid else {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _ObjectClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", _fake_history_obj)

    result = asyncio.run(runtime_run_module.run(*_approved(_make_one_shot_run_wf())))
    assert result.prompt_id == "obj-prompt-id"


def test_one_shot_run_terminal_error_fails_before_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class FakeClient:
        def __init__(self, _server_url: str) -> None:
            pass

        async def _post_prompt(self, _prompt: dict) -> dict:
            return {"prompt_id": "one-shot-error"}

    async def fake_history(_url: str, prompt_id: str | None, config=None) -> dict:
        assert prompt_id == "one-shot-error"
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
                                "node_id": "1",
                                "exception_message": "one-shot node failed",
                            },
                        ]
                    ],
                },
            }
        }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", fake_history)

    with pytest.raises(RuntimeNodeError, match="one-shot node failed"):
        asyncio.run(runtime_run_module.run(*_approved(_make_one_shot_run_wf())))

    assert not list(tmp_path.glob("out/runs/*/metadata.json"))


def test_one_shot_run_persists_accepted_prompt_before_wait_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class FakeClient:
        def __init__(self, _server_url: str) -> None:
            pass

        async def _post_prompt(self, _prompt: dict) -> dict:
            return {"prompt_id": "accepted-before-wait"}

    async def interrupted_history(_url: str, prompt_id: str | None, config=None) -> dict:
        assert prompt_id == "accepted-before-wait"
        attempt_path = next(tmp_path.glob("out/runs/*/attempt.json"))
        attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
        assert attempt["queue_acceptance"] == {
            "status": "accepted",
            "prompt_id": "accepted-before-wait",
        }
        raise TimeoutError("history wait interrupted")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", interrupted_history)

    record, bundle = _approved(_make_one_shot_run_wf())
    with pytest.raises(TimeoutError, match="history wait interrupted"):
        asyncio.run(runtime_run_module.run(record, bundle))

    attempt_path = next(tmp_path.glob("out/runs/*/attempt.json"))
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    assert attempt["runtime_evidence"]["approved_projection"] == record.to_dict()
    assert "approval_record" not in attempt
    assert "approved_projection" not in attempt
    assert attempt["adapter"]["kind"] == "managed"
    assert attempt["adapter"]["backend"] == "api"
    assert attempt["schema_provenance"]["provider"] is None
    assert attempt["schema_provenance"]["validation"] == "structural-only"
    assert attempt["schema_provenance"]["schema_digest"] is None
    assert attempt["queue_acceptance"] == {
        "status": "accepted",
        "prompt_id": "accepted-before-wait",
    }
    _assert_exact_runtime_record(attempt, record)
    run_dir = attempt_path.parent
    lifecycle_path = (
        run_dir
        / "transactions"
        / record.api_digest
        / "lifecycle_events.jsonl"
    )
    lifecycle = [
        json.loads(line)
        for line in lifecycle_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [event["event_type"] for event in lifecycle] == ["prepared", "discarded"]
    assert lifecycle[-1]["generation"] == lifecycle[0]["generation"]
    assert lifecycle[-1]["receipt"]["runtime_evidence"]["queue_acceptance"] == {
        "status": "accepted",
        "prompt_id": "accepted-before-wait",
    }
    assert lifecycle[-1]["receipt"]["runtime_evidence"]["terminal"] == {
        "phase": "history",
        "reason_type": "TimeoutError",
        "reason": "history wait interrupted",
        "acceptance_known": True,
    }
    assert len([event for event in lifecycle if event["event_type"] == "discarded"]) == 1
    assert not any(event["event_type"] == "finalized" for event in lifecycle)
    _assert_exact_runtime_record(lifecycle[-1], record)


@pytest.mark.parametrize("queue_response", [{}, {"prompt_id": "   "}])
@pytest.mark.parametrize("server_url", ["http://runtime.test", None])
def test_one_shot_run_ambiguous_queue_acceptance_is_not_retried(
    queue_response: dict, server_url: str | None,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    queue_calls = 0

    class FakeClient:
        def __init__(self, _server_url: str) -> None:
            pass

        async def _post_prompt(self, _prompt: dict) -> dict:
            nonlocal queue_calls
            queue_calls += 1
            return queue_response

    async def unexpected_history(_url: str, _prompt_id: str | None, config=None) -> dict:
        raise AssertionError("ambiguous queue acceptance must not enter history polling")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda _url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", unexpected_history)
    record, bundle = _approved(_make_one_shot_run_wf())

    with pytest.raises(QueueError, match="acceptance is ambiguous"):
        asyncio.run(runtime_run_module.run(record, bundle, server_url=server_url))

    assert queue_calls == 1
    attempt_path = next(tmp_path.glob("out/runs/*/attempt.json"))
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    assert attempt["queue_acceptance"] == {
        "status": "unknown",
        "prompt_id": None,
    }
    lifecycle_path = attempt_path.parent / "transactions" / record.api_digest / "lifecycle_events.jsonl"
    lifecycle = [
        json.loads(line)
        for line in lifecycle_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [event["event_type"] for event in lifecycle] == ["prepared", "discarded"]
    assert lifecycle[-1]["receipt"]["runtime_evidence"]["queue_acceptance"] == attempt["queue_acceptance"]
    assert lifecycle[-1]["receipt"]["runtime_evidence"]["terminal"] == {
        "phase": "acceptance_witness",
        "reason_type": "QueueError",
        "reason": "Comfy queue response did not include a prompt_id; acceptance is ambiguous and must not be retried automatically next action: vibecomfy runtime doctor",
        "acceptance_known": False,
    }
    assert lifecycle[-1]["generation"] == lifecycle[0]["generation"]
    assert not list(tmp_path.glob("out/runs/*/metadata.json"))
    _assert_exact_runtime_record(attempt, record)
    _assert_exact_runtime_record(lifecycle[-1], record)


def test_embedded_session_dict_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Embedded session: dict queue result → RunResult.prompt_id via normalize_prompt_id."""

    class FakeComfy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def queue_prompt_api(self, api_dict: dict) -> dict:
            return {"prompt_id": "emb-dict-id", "outputs": []}

        async def clear_cache(self) -> None:
            pass

    import sys
    import types as _types

    monkeypatch.setitem(sys.modules, "comfy", _types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", _types.ModuleType("comfy.client"))
    embedded = _types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = lambda configuration=None: FakeComfy()

    def _default_config():
        class _C(dict):
            def __getattr__(self, k):
                try:
                    return self[k]
                except KeyError as e:
                    raise AttributeError(k) from e

        return _C({"cwd": None})

    embedded.default_configuration = _default_config
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)
    monkeypatch.delenv("VIBECOMFY_WARM", raising=False)
    monkeypatch.chdir(tmp_path)
    # Disable schema validation so schema provider is not needed
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    wf = _make_one_shot_run_wf()
    result = asyncio.run(
        session_module.EmbeddedSession().run(*_approved(wf))
    )
    assert result.prompt_id == "emb-dict-id"


def test_embedded_session_object_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Embedded session: object queue result → RunResult.prompt_id via normalize_prompt_id."""

    class FakeComfy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def queue_prompt_api(self, api_dict: dict) -> _ObjectQueueResult:
            return _ObjectQueueResult("emb-obj-id")

        async def clear_cache(self) -> None:
            pass

    import sys
    import types as _types

    monkeypatch.setitem(sys.modules, "comfy", _types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", _types.ModuleType("comfy.client"))
    embedded = _types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = lambda configuration=None: FakeComfy()

    def _default_config():
        class _C(dict):
            def __getattr__(self, k):
                try:
                    return self[k]
                except KeyError as e:
                    raise AttributeError(k) from e

        return _C({"cwd": None})

    embedded.default_configuration = _default_config
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)
    monkeypatch.delenv("VIBECOMFY_WARM", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    wf = _make_one_shot_run_wf()
    result = asyncio.run(
        session_module.EmbeddedSession().run(*_approved(wf))
    )
    assert result.prompt_id == "emb-obj-id"


def test_server_session_dict_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Server session: dict queue result → RunResult.prompt_id via normalize_prompt_id."""

    class _FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def _post_prompt(self, api_dict: dict) -> dict:
            return {"prompt_id": "srv-dict-id"}

    async def _fake_history(url: str, pid: str | None, *, config=None) -> dict:
        return _successful_history(pid, {}) if pid else {}

    async def _fake_start(self) -> None:
        self.url = "http://fake-srv.test"

    async def _fake_watchdog(*args, **kwargs):
        return None

    async def _fake_finalize_watchdog(*args, **kwargs):
        pass

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module.ServerSession, "start", _fake_start)
    monkeypatch.setattr(session_module, "ComfyClient", _FakeClient)
    monkeypatch.setattr(session_module, "_wait_for_server_history", _fake_history)
    monkeypatch.setattr(session_module, "_start_watchdog", _fake_watchdog)
    monkeypatch.setattr(session_module, "_finalize_watchdog", _fake_finalize_watchdog)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    wf = _make_one_shot_run_wf()
    result = asyncio.run(session_module.ServerSession()._run_untracked(*_approved(wf)))
    assert result.prompt_id == "srv-dict-id"
    assert result.log_path is None
    assert result.log_provenance["available"] is False


def test_server_session_reports_persistent_process_log_not_per_run_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "out" / "sessions" / "default" / "comfy.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("managed Comfy log\n", encoding="utf-8")

    class _FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def _post_prompt(self, api_dict: dict) -> dict:
            return {"prompt_id": "srv-persistent-log"}

    async def _fake_history(url: str, pid: str | None, *, config=None) -> dict:
        return _successful_history(pid, {}) if pid else {}

    async def _fake_start(self) -> None:
        self.url = "http://fake-srv.test"
        self.log_handle = object()
        self._process_configuration = session_module._RuntimeConfigurationSnapshot(
            values={"server_log_path": str(log_path)},
            cwd=tmp_path,
            use_sage_attention=False,
        )

    async def _fake_watchdog(*args, **kwargs):
        return None

    async def _fake_finalize_watchdog(*args, **kwargs):
        pass

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module.ServerSession, "start", _fake_start)
    monkeypatch.setattr(session_module, "ComfyClient", _FakeClient)
    monkeypatch.setattr(session_module, "_wait_for_server_history", _fake_history)
    monkeypatch.setattr(session_module, "_start_watchdog", _fake_watchdog)
    monkeypatch.setattr(session_module, "_finalize_watchdog", _fake_finalize_watchdog)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    result = asyncio.run(
        session_module.ServerSession()._run_untracked(*_approved(_make_one_shot_run_wf()))
    )

    assert result.log_path == str(log_path)
    assert result.log_provenance == {
        "available": True,
        "kind": "vibecomfy_captured_file",
        "path": str(log_path),
    }
    assert not Path(result.metadata_path).parent.joinpath("comfy.log").exists()
    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    assert metadata["log_path"] == str(log_path)
    assert metadata["log_provenance"] == result.log_provenance


def test_server_session_object_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Server session: object queue result → RunResult.prompt_id via normalize_prompt_id."""

    class _FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def _post_prompt(self, api_dict: dict) -> _ObjectQueueResult:
            return _ObjectQueueResult("srv-obj-id")

    async def _fake_history(url: str, pid: str | None, *, config=None) -> dict:
        return _successful_history(pid, {}) if pid else {}

    async def _fake_start(self) -> None:
        self.url = "http://fake-srv.test"

    async def _fake_watchdog(*args, **kwargs):
        return None

    async def _fake_finalize_watchdog(*args, **kwargs):
        pass

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module.ServerSession, "start", _fake_start)
    monkeypatch.setattr(session_module, "ComfyClient", _FakeClient)
    monkeypatch.setattr(session_module, "_wait_for_server_history", _fake_history)
    monkeypatch.setattr(session_module, "_start_watchdog", _fake_watchdog)
    monkeypatch.setattr(session_module, "_finalize_watchdog", _fake_finalize_watchdog)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    wf = _make_one_shot_run_wf()
    result = asyncio.run(session_module.ServerSession()._run_untracked(*_approved(wf)))
    assert result.prompt_id == "srv-obj-id"


def test_prompt_id_consistency_across_run_result_and_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RunResult.prompt_id matches the prompt_id stored in the metadata.json queued field.

    The 'queued' value is written verbatim into metadata.json, while RunResult.prompt_id
    is the normalized string.  For a dict return the two must agree without expansion.
    """
    import json as _json

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _DictClient:
        def __init__(self, server_url: str) -> None:
            pass

        async def _post_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "meta-check-id", "extra_field": "ignored"}

        async def history(self, prompt_id: str) -> dict:
            return _successful_history(prompt_id, {})

    async def _fake_history_meta(url: str, pid: str | None, config=None) -> dict:
        return _successful_history(pid, {}) if pid else {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _DictClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", _fake_history_meta)

    result = asyncio.run(runtime_run_module.run(*_approved(_make_one_shot_run_wf())))

    assert result.prompt_id == "meta-check-id"
    metadata = _json.loads(Path(result.metadata_path).read_text())
    # queued is stored verbatim; prompt_id in RunResult is the normalized string
    assert metadata["queued"]["prompt_id"] == "meta-check-id"
    # RunResult does not gain extra fields beyond what is already in its dataclass
    assert not hasattr(result, "extra_field")


# ---------------------------------------------------------------------------
# T6: _allocate_run_dir tests (collision-resistant run directory allocation)
# ---------------------------------------------------------------------------


def test_allocate_run_dir_prefix_and_unique_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_allocate_run_dir produces IDs with stable prefix, timestamp, and uuid4 hex."""
    import time as _time

    monkeypatch.chdir(tmp_path)
    run_id, run_dir = runtime_run_module._allocate_run_dir("testprefix")

    # Stable prefix
    assert run_id.startswith(
        "testprefix-"
    ), f"Expected 'testprefix-' prefix, got {run_id!r}"

    # Format: testprefix-<timestamp>-<8 hex chars>
    suffix = run_id[len("testprefix-"):]
    parts = suffix.split("-")
    assert len(parts) == 2, f"Expected 2 parts after prefix, got {parts}"

    # First part is integer timestamp within a reasonable window
    assert parts[0].isdigit(), f"Expected integer timestamp, got {parts[0]!r}"
    ts = int(parts[0])
    now = int(_time.time())
    assert abs(ts - now) <= 5, f"Timestamp {ts} too far from now ({now})"

    # Second part is 8 lowercase hex chars (uuid4 hex fragment)
    assert len(parts[1]) == 8, f"Expected 8 hex chars, got {parts[1]!r} (len={len(parts[1])})"
    assert all(c in "0123456789abcdef" for c in parts[1]), (
        f"Non-hex chars in uuid fragment {parts[1]!r}"
    )

    # Directory was created
    assert run_dir.exists()
    assert run_dir.is_dir()


def test_drift_cache_distinguishes_explicit_lockfiles_with_same_mtime(tmp_path):
    import os
    from types import SimpleNamespace
    from vibecomfy.runtime.drift import _cache_key

    first = tmp_path / "first.lock"
    second = tmp_path / "second.lock"
    for path in (first, second):
        path.write_text("", encoding="utf-8")
        os.utime(path, (1000, 1000))
    workflow = SimpleNamespace(id="same-workflow")
    assert _cache_key(workflow, first) != _cache_key(workflow, second)


def test_allocate_run_dir_smoke_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_allocate_run_dir('smoke') produces IDs with 'smoke-' prefix."""
    monkeypatch.chdir(tmp_path)
    run_id, run_dir = runtime_run_module._allocate_run_dir("smoke")
    assert run_id.startswith("smoke-")
    assert run_dir.exists()


def test_allocate_run_dir_collision_raises_file_exists_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forced collision in _allocate_run_dir raises FileExistsError (no artifact merging)."""
    import time as _time
    import uuid as _uuid

    monkeypatch.chdir(tmp_path)

    # Freeze uuid4 and time so a second call inevitably collides
    fixed_uuid = "deadbeef-cafe-4bad-babe-123456789abc"
    monkeypatch.setattr(_uuid, "uuid4", lambda: _uuid.UUID(fixed_uuid))
    frozen_time = 1000000.0
    monkeypatch.setattr(_time, "time", lambda: frozen_time)

    # First allocation succeeds
    run_id1, run_dir1 = runtime_run_module._allocate_run_dir("collision")
    assert run_dir1.exists()
    assert run_id1 == "collision-1000000-deadbeef"

    # Second allocation with identical prefix+timestamp+uuid must collide
    with pytest.raises(FileExistsError):
        runtime_run_module._allocate_run_dir("collision")


def test_allocate_run_dir_different_prefixes_no_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Different prefixes produce distinct directories even with frozen time + uuid."""
    import time as _time
    import uuid as _uuid

    monkeypatch.chdir(tmp_path)

    fixed_uuid = "deadbeef-cafe-4bad-babe-123456789abc"
    monkeypatch.setattr(_uuid, "uuid4", lambda: _uuid.UUID(fixed_uuid))
    frozen_time = 2000000.0
    monkeypatch.setattr(_time, "time", lambda: frozen_time)

    run_id_a, run_dir_a = runtime_run_module._allocate_run_dir("alpha")
    run_id_b, run_dir_b = runtime_run_module._allocate_run_dir("beta")

    assert run_id_a.startswith("alpha-")
    assert run_id_b.startswith("beta-")
    assert run_id_a != run_id_b
    assert run_dir_a != run_dir_b
    assert run_dir_a.exists()
    assert run_dir_b.exists()


def test_run_uses_collision_resistant_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """run() produces a run_id with the 'run-' collision-resistant prefix and uuid suffix."""
    import re

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _FakeClient:
        def __init__(self, server_url: str) -> None:
            pass

        async def _post_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "prompt-t6-run"}

        async def history(self, prompt_id: str) -> dict:
            return _successful_history(prompt_id, {})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _FakeClient)
    monkeypatch.setattr(
        runtime_run_module, "_build_schema_provider", lambda active_url: None
    )
    # _wait_for_server_history needs to return something valid
    async def _fake_history(url: str, pid: str | None, config=None) -> dict:
        return _successful_history(pid, {}) if pid else {}

    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", _fake_history)

    result = asyncio.run(runtime_run_module.run(*_approved(_make_one_shot_run_wf())))

    # run_id format: run-<timestamp>-<8 hex>
    assert re.match(r"^run-\d+-[0-9a-f]{8}$", result.run_id), (
        f"run_id {result.run_id!r} does not match expected collision-resistant pattern"
    )
    run_dir = tmp_path / "out" / "runs" / result.run_id
    assert run_dir.is_dir()
    assert (run_dir / "metadata.json").exists()


def test_smoke_runtime_uses_collision_resistant_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """smoke_runtime() produces a run_id with the 'smoke-' collision-resistant prefix."""
    import re

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def object_info(self) -> dict:
            return {"KSampler": {}, "SaveImage": {}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _FakeClient)

    result = asyncio.run(runtime_run_module.smoke_runtime())

    assert re.match(r"^smoke-\d+-[0-9a-f]{8}$", result["run_id"]), (
        f"run_id {result['run_id']!r} does not match expected collision-resistant pattern"
    )
    assert result["node_count"] == 2
    run_dir = tmp_path / "out" / "runs" / result["run_id"]
    assert run_dir.is_dir()
