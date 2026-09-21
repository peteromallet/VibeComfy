"""CPU-only checks of the CLI's durable boundary before author code runs."""
from __future__ import annotations

import argparse
import json
from types import SimpleNamespace

import pytest

from vibecomfy.commands import run as command
from vibecomfy.runtime.run_context import RunContext


def args(tmp_path, **overrides):
    values = dict(
        path="fixture", runtime_root=str(tmp_path), runtime="server",
        server_url="http://comfy.test", prompt=None, seed=None, steps=None,
        json=True, backend="api",
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def only_receipt(tmp_path):
    paths = list((tmp_path / "out" / "runs").glob("*/attempt.json"))
    assert len(paths) == 1
    return paths[0], json.loads(paths[0].read_text())


@pytest.mark.parametrize("failure", [SyntaxError("bad Python"), FileNotFoundError("missing input"), TypeError("invalid handle"), SystemExit(2), KeyboardInterrupt()])
def test_receipt_exists_before_loading_and_finalizes_load_errors(tmp_path, monkeypatch, capsys, failure):
    monkeypatch.setattr(command, "load_binding", lambda *_: None)
    monkeypatch.setattr(command, "get_schema_provider", lambda *a, **kw: None)

    def load(*a, **kw):
        path, initial = only_receipt(tmp_path)
        assert initial["status"] == "started"
        assert initial["queue_status"] == "not_attempted"
        assert initial["receipt_path"] == str(path)
        raise failure

    monkeypatch.setattr(command, "load_bundle", load)
    assert command._cmd_run(args(tmp_path)) == 1
    path, receipt = only_receipt(tmp_path)
    assert receipt["status"] == "failed"
    assert receipt["phase"] == "workflow_load"
    assert receipt["error"]["type"] == type(failure).__name__
    assert receipt["diagnostics"]
    assert receipt["queue_status"] == "not_attempted"
    assert receipt["prompt_id"] is None
    assert json.loads(capsys.readouterr().out)["receipt_path"] == str(path)


@pytest.mark.parametrize("runtime", ["server", "embedded"])
def test_cli_hands_off_same_context_and_allocates_unique_attempts(tmp_path, monkeypatch, capsys, runtime):
    monkeypatch.setattr(command, "load_binding", lambda *_: None)
    monkeypatch.setattr(command, "active_session_metadata", lambda *a, **kw: None)
    monkeypatch.setattr(command, "get_schema_provider", lambda *a, **kw: None)
    workflow = SimpleNamespace(id="fixture", inputs={}, requirements=None, metadata={}, source=None)
    bundle = SimpleNamespace(
        workflow=workflow, is_unresolved=False, unresolved=[],
        require_canonical_authority=lambda *_: None, compile=lambda **kw: object(),
    )
    monkeypatch.setattr(command, "load_bundle", lambda *a, **kw: bundle)
    identities = []

    def execute(record, bundle, *, run_context, **kwargs):
        receipt = json.loads(run_context.receipt_path.read_text())
        assert receipt["run_id"] == run_context.run_id
        identities.append(run_context.run_id)
        return SimpleNamespace(run_id=run_context.run_id, prompt_id="fixture-prompt", metadata_path="fixture", log_path=None)

    monkeypatch.setattr(command, "run_sync", execute)
    monkeypatch.setattr(command, "run_embedded_sync", execute)
    for _ in range(2):
        assert command._cmd_run(args(tmp_path, runtime=runtime, server_url="http://comfy.test" if runtime == "server" else None)) == 0
        assert json.loads(capsys.readouterr().out)["run_id"] == identities[-1]
    assert len(set(identities)) == 2
    assert len(list((tmp_path / "out/runs").iterdir())) == 2


@pytest.mark.parametrize("phase", ["schema", "dependencies", "mapping", "inputs", "compile"])
def test_all_prequeue_failure_phases_finalize_one_attempt(tmp_path, monkeypatch, capsys, phase):
    from vibecomfy.runtime import dependencies

    monkeypatch.setattr(command, "load_binding", lambda *_: None)

    def fail(*a, **kw):
        only_receipt(tmp_path)
        raise ValueError(f"{phase} diagnostic")

    monkeypatch.setattr(command, "get_schema_provider", fail if phase == "schema" else lambda *a, **kw: None)
    workflow = SimpleNamespace(id="fixture", inputs={}, requirements=None, metadata={}, source=None)
    bundle = SimpleNamespace(
        workflow=workflow, is_unresolved=False,
        unresolved=[{"kind": "mapping", "message": "unmapped input"}] if phase == "mapping" else [],
        require_canonical_authority=lambda *_: None,
        compile=fail,
    )
    monkeypatch.setattr(command, "load_bundle", lambda *a, **kw: bundle)
    if phase == "dependencies":
        monkeypatch.setattr(dependencies, "runtime_requirements_from_workflow", fail)
    monkeypatch.setattr(command, "run_sync", lambda *a, **kw: pytest.fail("must not queue"))
    assert command._cmd_run(args(tmp_path, prompt="override" if phase == "inputs" else None)) != 0
    path, receipt = only_receipt(tmp_path)
    assert receipt["phase"] == phase
    assert receipt["status"] == "failed"
    assert receipt["queue_status"] == "not_attempted"
    assert receipt["prompt_id"] is None
    assert receipt["diagnostics"]
    assert not (tmp_path / "out" / "dependency-failures").exists()
    assert json.loads(capsys.readouterr().out)["receipt_path"] == str(path)


@pytest.mark.parametrize("acceptance", ["accepted", "rejected", "unknown"])
def test_cli_failure_does_not_erase_queue_witness(tmp_path, acceptance):
    context = RunContext("run-existing", tmp_path)
    context.begin("fixture")
    receipt = json.loads(context.receipt_path.read_text())
    receipt.update(
        status="existing-runtime-status",
        queue_acceptance={"status": acceptance, "prompt_id": "p" if acceptance == "accepted" else None},
        terminal={"phase": "retrieval", "reason": "original diagnostic"},
    )
    context.receipt_path.write_text(json.dumps(receipt))
    result = context.fail(RuntimeError("CLI unwind"))
    assert result["queue_status"] == acceptance
    assert result["terminal"] == receipt["terminal"]
    assert result["status"] == receipt["status"]
