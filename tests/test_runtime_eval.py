from __future__ import annotations

import asyncio
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.cli_loader import load_bundle
from vibecomfy.errors import RuntimeNodeError
from vibecomfy.runtime.eval import approve_eval_subgraph, plan_eval_node, select_eval_workflow
from vibecomfy.runtime.eval import prompt as eval_prompt
from vibecomfy.runtime.session import RunResult
from vibecomfy.testing.canonical import canonical_digest
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import ApprovedProjectionRecord, WorkflowBundleError


def _bundle() -> object:
    workflow = VibeWorkflow("eval-source", WorkflowSource("eval-source"))
    workflow.nodes["1"] = VibeNode(
        "1", "VAEDecode", uid="source-1", inputs={"samples": ["latent", 0], "vae": ["vae", 0]}
    )
    workflow.nodes["latent"] = VibeNode("latent", "LatentSource", uid="latent", inputs={})
    workflow.nodes["vae"] = VibeNode("vae", "VAELoader", uid="vae", inputs={"vae_name": "x.vae"})
    workflow.edges.extend([
        __import__("vibecomfy.workflow", fromlist=["VibeEdge"]).VibeEdge("latent", "0", "1", "samples"),
        __import__("vibecomfy.workflow", fromlist=["VibeEdge"]).VibeEdge("vae", "0", "1", "vae"),
    ])
    return load_bundle(workflow)


def _record(bundle, api=None):
    api = api or {"1": {"class_type": "VAEDecode", "inputs": {}}}
    return ApprovedProjectionRecord(bundle.revision_id, None, {}, api, {}, canonical_digest(api))


def test_select_is_parent_bound_copy_with_deterministic_preview() -> None:
    parent = _bundle()
    candidate = select_eval_workflow(parent, "1")
    assert candidate.id == parent.workflow.id == candidate.source.id
    assert candidate is not parent.workflow
    assert candidate.nodes["1"] is not parent.workflow.nodes["1"]
    assert candidate.nodes["1_preview"].uid == "1_preview"
    assert candidate.groups == []
    assert {node.id for node in candidate.nodes.values()} == {"1", "latent", "vae", "1_preview"}
    assert "1_preview" not in parent.workflow.nodes


def test_selection_and_plan_reject_bare_inputs_without_compile() -> None:
    with pytest.raises(WorkflowBundleError, match="requires a WorkflowBundle"):
        select_eval_workflow("source.py", "1")
    with pytest.raises(WorkflowBundleError, match="requires a WorkflowBundle"):
        plan_eval_node("source.py", "1")
    parent = _bundle()
    with pytest.raises(RuntimeNodeError):
        select_eval_workflow(parent, "root/1")
    assert plan_eval_node(parent, "root/1").truncated_api == {}


def test_approval_uses_ephemeral_candidate_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _bundle()
    original = type(parent).compile
    calls = []

    def fake_compile(self, **kwargs):
        calls.append(self)
        api = {"1": {"class_type": "VAEDecode", "inputs": {}}, "1_preview": {"class_type": "PreviewImage", "inputs": {"images": ["1", 0]}}}
        return _record(self, api)

    monkeypatch.setattr(type(parent), "compile", fake_compile)
    try:
        candidate, record = approve_eval_subgraph(parent, "1")
        candidate2, record2 = approve_eval_subgraph(parent, "1")
    finally:
        monkeypatch.setattr(type(parent), "compile", original)
    assert candidate.revision_id != parent.revision_id
    assert record.revision_id == candidate.revision_id
    assert record.to_canonical_bytes() == record2.to_canonical_bytes()
    assert calls and all(item.workflow.id == parent.workflow.id for item in calls)


def test_plan_is_descriptive_and_has_no_raw_api() -> None:
    plan = plan_eval_node(_bundle(), "1")
    assert plan.queueable is True
    assert plan.truncated_api == {}
    assert "compile" not in {node.func.attr for node in ast.walk(ast.parse(Path(eval_prompt.__file__).read_text())) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}


def test_eval_delegates_prompt_id_and_candidate_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _bundle()
    candidate = _bundle()
    record = _record(candidate)
    seen = []

    async def fake_run_embedded(received_record, received_bundle, **kwargs):
        seen.append((received_record, received_bundle, kwargs))
        return RunResult("run-1", "prompt-1", ["out.png"], "meta.json", "run.log")

    monkeypatch.setattr(eval_prompt, "approve_eval_subgraph", lambda *args, **kwargs: (candidate, record))
    monkeypatch.setattr(eval_prompt, "run_embedded", fake_run_embedded)
    result = asyncio.run(eval_prompt.eval_node(parent, "1"))
    assert result.queued is True
    assert result.prompt_id == "prompt-1"
    assert result.history_outputs == ["out.png"]
    assert seen == [(record, candidate, {"config": None})]


def test_eval_failure_paths_make_zero_runtime_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _bundle()
    calls = []

    async def fail_run(*args, **kwargs):
        calls.append(args)
        raise AssertionError("runtime must not be called")

    monkeypatch.setattr(eval_prompt, "run_embedded", fail_run)
    with pytest.raises(RuntimeNodeError, match="RunPod transport is offline-only"):
        asyncio.run(eval_prompt.eval_node(parent, "1", runtime="runpod"))
    with pytest.raises(RuntimeNodeError):
        asyncio.run(eval_prompt.eval_node(parent, "root/1"))
    assert calls == []
