"""P7-LINEAGE-EVIDENCE Sub-fix B focused tests — abort-path evidence persistence.

Mid-turn aborts (in-loop render/emit fault, parse/protocol failure before
apply, generic pre-apply client fault, ingest-stage crash) persist the full
failure context — batch transcript, submitted ops, structured error context,
and graph state refs — to ``batch_failure_evidence.json`` in the turn
directory.  When even evidence persistence fails, the original abort behavior
stands unchanged (fail-closed).
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
from vibecomfy.comfy_nodes.agent.session import turn_dir_for
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema.provider import InputSpec, NodeSchema
from vibecomfy.schema.types import OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

_BATCH_FAILURE_EVIDENCE_FILENAME = "batch_failure_evidence.json"


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return self._schemas


def _schema(class_type: str, outputs: list[OutputSpec] | None = None) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={},
        outputs=outputs or [],
        source_provider="test",
        confidence=1.0,
    )


def _p7_provider() -> _Provider:
    return _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={
                    "images": InputSpec("IMAGE", required=True),
                    "filename_prefix": InputSpec("STRING"),
                },
                outputs=[],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )


def _emit_provider() -> _Provider:
    return _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage", [OutputSpec("IMAGE", "images")]),
        }
    )


def _ui_graph() -> dict:
    wf = VibeWorkflow("p7-workflow", WorkflowSource("p7-workflow"))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "before"})
    wf.connect("1.0", "2.images")
    graph = emit_ui_json(wf, schema_provider=_emit_provider())
    for node in graph["nodes"]:
        node.setdefault("properties", {})["vibecomfy_uid"] = str(node["id"])
    return graph


@pytest.fixture(autouse=True)
def _hermetic_narrator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the LLM narrator hermetic — never a live model call."""
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
        lambda **_kwargs: {"json": {}},
    )


def _apply_client(messages: list[dict[str, str]]) -> dict[str, str]:
    return {
        "batch": 'saveimage.filename_prefix = "after"\ndone()',
        "message": "Applied the requested save-prefix change.",
    }


def _journal_mod():
    return importlib.import_module(
        "vibecomfy.comfy_nodes.agent.batch_rollback_journal"
    )


def _install_render_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    journal = _journal_mod()

    def _injector(seen_point: str) -> None:
        if seen_point != "after_render":
            return
        raise journal.InjectedBatchFault(seen_point)

    monkeypatch.setattr(journal, "BATCH_FAULT_INJECTOR", _injector)


def _evidence_for(result: dict, session_root: Path, session_id: str) -> dict:
    assert result["ok"] is False
    evidence_path = (
        turn_dir_for(session_root, session_id, result["turn_id"])
        / _BATCH_FAILURE_EVIDENCE_FILENAME
    )
    assert evidence_path.is_file(), f"missing failure evidence in {session_root}"
    return json.loads(evidence_path.read_text(encoding="utf-8"))


# ── in-loop fault: batch body + ops + error survive the journaled rollback ──


def test_emit_fault_abort_persists_batch_ops_and_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    _install_render_fault(monkeypatch)
    session_id = "p7-render-fault"

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "workflow_id": "p7-workflow",
            "task": "change the save prefix",
            "session_id": session_id,
            "max_batches": 3,
            "max_consecutive_errors": 2,
        },
        schema_provider=_p7_provider(),
        deepseek_client=_apply_client,
        session_root=tmp_path,
    )

    evidence = _evidence_for(result, tmp_path, session_id)
    assert evidence["code"] == "agent_batch_failure_evidence"
    assert evidence["stage"]
    assert evidence["failure_kind"]
    # THE BATCH BODY survives the journaled rollback…
    failed_turn = evidence["transcript"][-1]
    assert failed_turn.get("aborted_mid_turn") is True
    assert 'saveimage.filename_prefix = "after"' in failed_turn.get("batch", "")
    assert failed_turn["abort"]["error_type"] == "InjectedBatchFault"
    # …with its submitted ops…
    ops = evidence["ops_submitted"]
    assert ops and ops[-1]["op"] == "set_node_field"
    assert ops[-1]["value"] == "after"
    # …the structured error context…
    context_issues = evidence["failure_context"]["issues"]
    assert any(
        isinstance(issue, dict) and issue.get("code") == "agent_batch_stage_exception"
        for issue in context_issues
    ), context_issues
    # …and graph state refs into this turn's durable artifacts.
    refs = evidence["graph_state_refs"]
    assert refs.get("submit_graph_hash")
    assert result["turn_id"] in refs.get("turn_dir", "")


# ── parse/protocol failure BEFORE apply: failing turn still reaches evidence ┌
# The protocol-failure handlers re-raise OUTSIDE the journaled apply region,
# so they must record the aborted turn themselves.


def test_repeated_parse_failures_persist_transcript_and_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real protocol-failure branch: ``run_agent_turn_batch`` raising typed
    ``MalformedModelJSON`` on BOTH attempts aborts the loop from OUTSIDE the
    journaled apply region — the failing turn must still reach the durable
    evidence artifact."""
    import vibecomfy.comfy_nodes.agent.edit as edit_module
    from vibecomfy.comfy_nodes.agent.provider import MalformedModelJSON

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    session_id = "p7-parse-failures"

    def _garbage_turn(*args: Any, **kwargs: Any) -> None:
        raise MalformedModelJSON(
            "Agent response does not contain a ```batch fenced block.",
            parse_reason="missing_fence",
        )

    monkeypatch.setattr(edit_module, "run_agent_turn_batch", _garbage_turn)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "workflow_id": "p7-workflow",
            "task": "change the save prefix",
            "session_id": session_id,
            "max_batches": 3,
            "max_consecutive_errors": 2,
        },
        schema_provider=_p7_provider(),
        deepseek_client=None,
        session_root=tmp_path,
    )

    evidence = _evidence_for(result, tmp_path, session_id)
    assert evidence["failure_kind"]
    # The FAILING turn itself survives as an aborted-transcript row.
    assert evidence["transcript"], evidence.keys()
    failed_turn = evidence["transcript"][-1]
    assert failed_turn.get("aborted_mid_turn") is True
    # Nothing was applied, so nothing was rolled back.
    assert failed_turn.get("rolled_back") is False
    assert failed_turn["abort"]["code"] == "batch_abort_before_apply"
    assert failed_turn["abort"]["error_type"] == "MalformedModelJSON"
    assert "batch fenced block" in failed_turn["abort"]["message"]
    assert result["turn_id"] in evidence["graph_state_refs"].get("turn_dir", "")


def test_preapply_client_fault_also_persists_failing_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic pre-apply exception branch (non-provider error raised by the
    client normalization): the failing turn reaches the durable evidence."""
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    session_id = "p7-preapply-fault"

    def _bad_client(messages: list[dict[str, str]]) -> dict[str, str]:
        # Missing the required string `batch` key entirely.
        return {"message": "I cannot produce a batch right now, sorry."}

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "workflow_id": "p7-workflow",
            "task": "change the save prefix",
            "session_id": session_id,
            "max_batches": 3,
            "max_consecutive_errors": 2,
        },
        schema_provider=_p7_provider(),
        deepseek_client=_bad_client,
        session_root=tmp_path,
    )

    evidence = _evidence_for(result, tmp_path, session_id)
    failed_turn = evidence["transcript"][-1]
    assert failed_turn.get("aborted_mid_turn") is True
    assert failed_turn["abort"]["error_type"] == "ValueError"
    assert "string key `batch`" in failed_turn["abort"]["message"]


# ── ingest-stage crash mid-turn ──────────────────────────────────────────────


def test_ingest_stage_crash_mid_turn_persists_failure_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecomfy.comfy_nodes.agent.edit as edit_module

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _crashing_ingest(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("p7 ingest boom")

    monkeypatch.setattr(edit_module, "_stage_ingest_v2", _crashing_ingest)
    session_id = "p7-ingest-crash"

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "workflow_id": "p7-workflow",
            "task": "change the save prefix",
            "session_id": session_id,
        },
        schema_provider=_p7_provider(),
        deepseek_client=_apply_client,
        session_root=tmp_path,
    )

    evidence = _evidence_for(result, tmp_path, session_id)
    assert evidence["stage"]
    assert evidence["failure_kind"]
    # The ingest-stage crash carries the error in the failure context.
    assert (
        "p7 ingest boom" in json.dumps(evidence["failure_context"])
    ), evidence["failure_context"]
    assert result["turn_id"] in evidence["graph_state_refs"].get("turn_dir", "")


# ── (d) fail-closed: evidence-write failure leaves the abort unchanged ──────


def test_evidence_write_failure_leaves_abort_behavior_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When even evidence persistence fails, the original abort behavior
    stands — same typed failure envelope, nothing extra escapes, and the run
    does not crash."""
    import vibecomfy.comfy_nodes.agent.audit as audit_module

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    payload = {
        "graph": _ui_graph(),
        "workflow_id": "p7-workflow",
        "task": "change the save prefix",
        "session_id": "p7-write-failure",
        "max_batches": 3,
        "max_consecutive_errors": 2,
    }

    # Both runs abort identically: an in-loop render fault.
    _install_render_fault(monkeypatch)

    # Control run: normal abort with evidence persisted.
    control_root = tmp_path / "control"
    control_root.mkdir()
    control = handle_agent_edit(
        dict(payload),
        schema_provider=_p7_provider(),
        deepseek_client=_apply_client,
        session_root=control_root,
    )

    # Patched run: the evidence write itself detonates.
    def _exploding_write(path: Path, value: Any) -> None:
        raise OSError("p7 evidence disk full")

    monkeypatch.setattr(audit_module, "write_json_artifact", _exploding_write)
    patched_root = tmp_path / "patched"
    patched_root.mkdir()
    patched = handle_agent_edit(
        dict(payload),
        schema_provider=_p7_provider(),
        deepseek_client=_apply_client,
        session_root=patched_root,
    )

    # The abort envelope is unchanged: same ok flag, same stage/kind.
    assert control["ok"] is False and patched["ok"] is False
    assert control["stage"] == patched["stage"]
    assert (
        (control.get("outcome") or {}).get("failure_kind")
        == (patched.get("outcome") or {}).get("failure_kind")
    ), (control.get("outcome"), patched.get("outcome"))
    # The control root DID get its evidence artifact…
    assert list(control_root.rglob(_BATCH_FAILURE_EVIDENCE_FILENAME))
    # …and no evidence artifact could be written on the patched root.
    assert not list(patched_root.rglob(_BATCH_FAILURE_EVIDENCE_FILENAME))
