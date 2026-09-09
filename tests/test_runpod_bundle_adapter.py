from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from vibecomfy.runtime import execution
from vibecomfy.runtime import runpod_adapter
from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import (
    ApprovedProjectionRecord,
    WorkflowBundle,
    WorkflowBundleError,
    canonical_json,
    load_bundle,
)


def _approved() -> tuple[ApprovedProjectionRecord, WorkflowBundle]:
    workflow = VibeWorkflow("runpod-adapter-test", WorkflowSource("runpod-adapter-test"))
    workflow.add_node("Integer", uid="integer-node", value=7)
    bundle = load_bundle(workflow)
    return bundle.compile(), bundle


def test_prepare_is_exact_canonical_record_and_round_trips() -> None:
    record, bundle = _approved()
    first = runpod_adapter.prepare_runpod_transport(record, bundle)
    second = runpod_adapter.prepare_runpod_transport(record, bundle)

    assert first == record.to_canonical_bytes() == second
    assert set(json.loads(first)) == {
        "revision_id", "selected_variant", "input_binding", "api_projection", "ui_projection", "api_digest"
    }
    assert runpod_adapter.load_runpod_transport(first) == record
    assert len(hashlib.sha256(first).hexdigest()) == 64


def test_stub_parity_with_authorized_fence_and_detached_payload() -> None:
    record, bundle = _approved()
    expected = execution.authorized_queue_payload(record, bundle)
    calls: list[dict[str, Any]] = []

    def queue(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return {"prompt_id": "stub-1", "outputs": {"1": {"filename": "out.png"}}}

    result = runpod_adapter.queue_runpod_stub(record, bundle, queue=queue)
    assert calls == [expected]
    assert calls[0] == record.to_dict()["api_projection"]
    assert result.prompt_id == "stub-1"
    assert result.outputs == ["out.png"]
    assert record.api_digest == record.to_dict()["api_digest"]
    assert record.revision_id == bundle.revision_id


def test_prepare_and_stub_are_detached_from_nested_mutations() -> None:
    record, bundle = _approved()
    transport = runpod_adapter.prepare_runpod_transport(record, bundle)
    original = record.to_dict()
    mutable = record.to_dict()
    mutable["api_projection"]["1"]["inputs"]["value"] = 99
    mutable["ui_projection"]["nodes"][0]["widgets_values"][0] = 99
    seen: list[dict[str, Any]] = []
    runpod_adapter.queue_runpod_stub(record, bundle, queue=lambda payload: seen.append(payload) or {})
    seen[0]["1"]["inputs"]["value"] = 123
    assert transport == record.to_canonical_bytes()
    assert record.to_dict() == original


@pytest.mark.parametrize(
    "kind",
    ["revision_id", "selected_variant", "input_binding", "api_projection", "ui_projection", "api_digest", "extra", "missing", "whitespace"],
)
def test_canonical_tampering_fails_closed(kind: str) -> None:
    record, bundle = _approved()
    value = record.to_dict()
    if kind == "revision_id":
        value["revision_id"] = "tampered"
    elif kind == "selected_variant":
        value["selected_variant"] = 123
    elif kind == "input_binding":
        value["input_binding"] = []
    elif kind == "api_projection":
        value["api_projection"]["1"]["inputs"]["value"] = 9
    elif kind == "ui_projection":
        value["ui_projection"]["nodes"][0]["widgets_values"][0] = 9
        value["revision_id"] = "tampered"
    elif kind == "api_digest":
        value["api_digest"] = "tampered"
    elif kind == "extra":
        value["extra"] = True
    elif kind == "missing":
        del value["api_digest"]
    encoded = canonical_json(value).encode()
    if kind == "whitespace":
        encoded = json.dumps(value, indent=2).encode()
    if kind in {"revision_id", "ui_projection"}:
        decoded = runpod_adapter.load_runpod_transport(encoded)
        with pytest.raises(WorkflowBundleError):
            runpod_adapter.queue_runpod_stub(decoded, bundle, queue=lambda payload: None)
    else:
        with pytest.raises(WorkflowBundleError):
            runpod_adapter.load_runpod_transport(encoded)


def test_stale_current_bundle_fails_before_callback() -> None:
    record, bundle = _approved()
    bundle.workflow.source.provenance["source_digest"] = "changed"
    calls: list[Any] = []
    with pytest.raises(WorkflowBundleError, match="revision"):
        runpod_adapter.prepare_runpod_transport(record, bundle)
    with pytest.raises(WorkflowBundleError, match="revision"):
        runpod_adapter.queue_runpod_stub(record, bundle, queue=lambda payload: calls.append(payload))
    assert calls == []


@pytest.mark.parametrize("bad", [{}, {"prompt": {}}, "workflow.py", VibeWorkflow("raw", WorkflowSource("raw"))])
def test_raw_inputs_fail_before_queue(bad: Any) -> None:
    _, bundle = _approved()
    calls: list[Any] = []
    with pytest.raises(WorkflowBundleError) as exc_info:
        runpod_adapter.queue_runpod_stub(bad, bundle, queue=lambda payload: calls.append(payload))
    assert runpod_adapter.RAW_RUNPOD_TRANSPORT_MIGRATION.splitlines()[1] in str(exc_info.value)
    assert calls == []


def test_decoded_record_requires_current_bundle() -> None:
    record, _ = _approved()
    decoded = runpod_adapter.load_runpod_transport(record.to_canonical_bytes())
    calls: list[Any] = []
    with pytest.raises(WorkflowBundleError):
        runpod_adapter.queue_runpod_stub(decoded, None, queue=lambda payload: calls.append(payload))
    assert calls == []


def test_load_and_stub_do_not_contact_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    record, bundle = _approved()
    monkeypatch.setattr(WorkflowBundle, "compile", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("compile")))
    monkeypatch.setattr(WorkflowBundle, "materialize_ui", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ui")))
    monkeypatch.setattr(execution, "ComfyClient", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("client")))
    decoded = runpod_adapter.load_runpod_transport(record.to_canonical_bytes())
    result = runpod_adapter.queue_runpod_stub(decoded, bundle, queue=lambda payload: {"prompt_id": "offline"})
    assert result.prompt_id == "offline"


def test_adapter_public_surface_is_exact() -> None:
    assert set(runpod_adapter.__all__) == {
        "RAW_RUNPOD_TRANSPORT_MIGRATION", "prepare_runpod_transport", "load_runpod_transport", "queue_runpod_stub"
    }
