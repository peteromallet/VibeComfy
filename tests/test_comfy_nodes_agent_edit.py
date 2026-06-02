from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from vibecomfy.comfy_nodes.agent_edit import AgentEditState, handle_agent_edit
from vibecomfy.comfy_nodes.agent_contracts import FailureKind, StageResult
from vibecomfy.comfy_nodes.agent_session import payload_hash
from vibecomfy.porting.convert import ConversionWriteError
from vibecomfy.porting.lowering import LoweringDiagnostic, LoweringEvidence, LoweringResult
from vibecomfy.porting.refuse import EditorAheadError, RefusedEmit
from vibecomfy.porting.ui_emitter import emit_ui_json
from vibecomfy.security.agent_generated_loader import AgentGeneratedLoadError, ScanFailure, ScanReport
from vibecomfy.security.agent_generated_loader import (
    load_agent_generated_scratchpad,
)
from vibecomfy.security.gate import GateContext, _gate_context_var, set_gate_context
from vibecomfy.security.provenance import confirm, read as read_provenance
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


# ── shared helpers ────────────────────────────────────────────────────────


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _schema(class_type: str, outputs: list[OutputSpec] | None = None) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={},
        outputs=outputs or [],
        source_provider="test",
        confidence=1.0,
    )


def _ui_graph() -> dict:
    wf = VibeWorkflow("agent-edit-test", WorkflowSource("agent-edit-test"))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "before"})
    wf.connect("1.0", "2.images")
    return emit_ui_json(
        wf,
        schema_provider=_Provider(
            {"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])}
        ),
    )


def _allocate_action_candidate(
    root: Path,
    *,
    session_id: str,
    label: str,
) -> tuple[str, str, str]:
    from vibecomfy.comfy_nodes.agent_session import allocate_turn, record_idempotent_response

    graph = {"nodes": [{"id": 1, "type": "SaveImage", "widgets_values": [label]}], "links": []}
    candidate_graph = {
        "nodes": [{"id": 2, "type": "SaveImage", "widgets_values": [f"{label}-candidate"]}],
        "links": [],
    }
    allocation = allocate_turn(
        session_root=root,
        session_id=session_id,
        request_payload={"graph": graph, "task": f"edit {label}"},
    )
    turn_id = str(allocation.context.turn_id)
    record_idempotent_response(
        session_root=root,
        session_id=session_id,
        scope="edit",
        idempotency_key=None,
        request_hash=allocation.request_hash,
        response={"ok": True, "turn_id": turn_id, "graph": candidate_graph},
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
    )
    return turn_id, payload_hash(graph), payload_hash(candidate_graph)


def _fake_deepseek_replace(
    replace_from: str, replace_to: str, message: str
):
    """Return a deepseek-client callable that mirrors the original Python
    but with one string replacement, matching the existing agent-edit test
    pattern (the model edits one widget value and preserves the rest)."""

    def _fake(messages):
        source = (
            messages[-1]["content"]
            .split("```python\n", 1)[1]
            .rsplit("\n```", 1)[0]
        )
        return {
            "python": source.replace(replace_from, replace_to),
            "message": message,
        }

    return _fake


def _fixture_source(name: str) -> str:
    fixture_dir = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "agent_generated_loader"
    )
    return (fixture_dir / name).read_text(encoding="utf-8")


def _assert_failure_defaults(
    result: dict,
    *,
    kind: str,
    stage: str,
    audit_ref_expected: bool,
) -> None:
    assert result["ok"] is False
    assert result["kind"] == kind
    assert result["stage"] == stage
    assert result["canvas_apply_allowed"] is False
    assert result["apply_allowed"] is False
    assert result["queue_allowed"] is False
    if audit_ref_expected:
        assert isinstance(result["audit_ref"], dict)
        assert result["audit_ref"]["path"]
    else:
        assert result["audit_ref"] is None


def test_agent_edit_state_exposes_explicit_lowering_fields(tmp_path: Path) -> None:
    state = AgentEditState(
        task="lowering smoke",
        graph={},
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submitted_client_graph_hash=None,
        session_dir=tmp_path,
        turn_dir=tmp_path,
        request_path=tmp_path / "request.json",
        original_ui_path=tmp_path / "original.ui.json",
        before_py_path=tmp_path / "before.py",
        after_py_path=tmp_path / "after.py",
        projection_path=tmp_path / "projection.txt",
        model_request_path=tmp_path / "model_request.json",
        model_response_path=tmp_path / "model_response.json",
        candidate_ui_path=tmp_path / "candidate.ui.json",
        messages_path=tmp_path / "messages.jsonl",
    )

    assert state.original_intent_workflow is None
    assert state.lowering_evidence == []
    assert state.lowering_recovery_entries == []


# ── gate context fixture ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _headless_gate_context() -> GateContext:
    ctx = GateContext(non_interactive=True, assume_yes=False, audit=[])
    token = set_gate_context(ctx)
    try:
        yield ctx
    finally:
        _gate_context_var.reset(token)


# ── existing T6 regression tests (refactored) ────────────────────────────


def test_handle_agent_edit_round_trips_deepseek_python(tmp_path: Path) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    graph = _ui_graph()
    client_graph_hash = payload_hash(graph)
    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "change the save prefix to after",
            "session_id": "t1",
            "client_graph_hash": client_graph_hash,
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    assert result["message"] == "Changed the save prefix."
    assert result["session_id"] == "t1"
    assert result["submit_graph_hash"] == client_graph_hash
    assert result["submitted_client_graph_hash"] == client_graph_hash
    assert result["candidate_graph_hash"] == payload_hash(result["graph"])
    assert result["baseline_graph_hash"] is None
    assert (
        Path(result["artifacts"]["python"])
        .read_text(encoding="utf-8")
        .count("after")
        >= 1
    )
    assert Path(result["artifacts"]["python"]).name == "after.py"
    assert Path(result["artifacts"]["before_python"]).name == "before.py"
    assert Path(result["artifacts"]["model_request"]).name == "model_request.json"
    assert Path(result["artifacts"]["model_response"]).name == "model_response.json"
    assert "before" in Path(result["artifacts"]["before_python"]).read_text(encoding="utf-8")
    assert "after" in Path(result["artifacts"]["after_python"]).read_text(encoding="utf-8")
    assert result["graph"]["nodes"]
    assert result["report"]["change"]
    assert result["gates"]["python_load_ok"] is True
    assert result["gates"]["lower_ok"] is True
    assert result["gates"]["ir_validate_ok"] is True
    assert result["gates"]["ui_emit_ok"] is True
    assert result["gates"]["ui_fidelity_ok"] is True
    assert result["gates"]["ui_load_safe_ok"] is True
    assert result["audit_ref"]["path"]
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert {
        "request",
        "original_ui",
        "before_python",
        "after_python",
        "model_request",
        "model_response",
        "candidate_ui",
        "messages",
    } <= set(audit["artifacts"])


def test_handle_agent_edit_v2_uses_delta_stage_sequence_without_authoring_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_V2", "1")

    def _fake_delta(messages):
        prompt = messages[-1]["content"]
        match = re.search(r'target=\["",\s*"([^"]+)"\].*class="SaveImage"', prompt)
        assert match is not None
        return {
            "delta": [
                {
                    "op": "set_node_field",
                    "target": ["", match.group(1), "filename_prefix"],
                    "value": "after",
                }
            ],
            "message": "Changed the save prefix.",
        }

    from vibecomfy.comfy_nodes import agent_edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent_audit import write_audit as real_write_audit

    stage_order: list[str] = []

    def _capture_audit(audit_dir, **kwargs):
        stage_order[:] = list((kwargs.get("stage_results") or {}).keys())
        return real_write_audit(audit_dir, **kwargs)

    monkeypatch.setattr(agent_edit_module, "write_audit", _capture_audit)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "v2-delta-success",
        },
        schema_provider=provider,
        deepseek_client=_fake_delta,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["message"] == "Changed the save prefix."
    assert "python" not in result["artifacts"]
    assert "before_python" not in result["artifacts"]
    assert "after_python" not in result["artifacts"]
    assert result["delta_ops"] == [
        {
            "op": "set_node_field",
            "target": ["", result["delta_ops"][0]["target"][1], "filename_prefix"],
            "value": "after",
        }
    ]
    assert Path(result["artifacts"]["projection"]).name == "projection.txt"
    assert result["graph"]["nodes"][1]["widgets_values"] == ["after"]
    assert stage_order == [
        "ingest",
        "project",
        "agent_delta",
        "apply_delta",
        "queue_validate",
        "summarize",
        "audit",
    ]
    assert {"convert", "agent", "load_python", "lower", "validate", "emit"}.isdisjoint(stage_order)

    request = json.loads(Path(result["artifacts"]["model_request"]).read_text(encoding="utf-8"))
    assert request["response_contract"] == "delta"
    assert "Return only JSON with keys `delta` and `message`." in request["messages"][0]["content"]
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert set(audit["artifacts"]) == {
        "request",
        "original_ui",
        "projection",
        "model_request",
        "model_response",
        "candidate_ui",
        "messages",
    }
    assert audit["metadata"]["agent_edit_v2"]["enabled"] is True
    assert audit["metadata"]["agent_edit_v2"]["op_count"] == 1
    assert audit["metadata"]["agent_edit_v2"]["delta_ops"]["ops"] == result["delta_ops"]
    assert audit["metadata"]["agent_edit_v2"]["delta_ops"]["automatic_link_removals"] == []
    assert audit["metadata"]["agent_edit_v2"]["delta_ops"]["re_stitches"] == []
    assert audit["metadata"]["agent_edit_v2"]["delta_ops"]["guard_result"]["ok"] is True
    # normalize availability depends on the environment (e.g. ComfyUI/litegraph
    # may not be importable in dev/test), so only assert the important invariant:
    # the allow-list must never be used for a simple set_node_field edit.
    assert audit["metadata"]["agent_edit_v2"]["delta_ops"]["normalize"]["allow_list_used"] is False
    assert isinstance(audit["metadata"]["agent_edit_v2"]["delta_ops"]["normalize"]["fallback_used"], bool)


def test_handle_agent_edit_v2_classifies_malformed_delta_as_closed_failure_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_V2", "1")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "v2-delta-malformed",
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: {
            "delta": [{"op": "bogus"}],
            "message": "bad delta",
        },
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.MALFORMED_MODEL_JSON.value,
        stage="agent_response",
        audit_ref_expected=True,
    )
    dumped = json.dumps(result, sort_keys=True)
    assert "EditOpParseError" not in dumped
    assert "ValueError" not in dumped
    assert "Unsupported edit op 'bogus'." == result["agent_failure_context"]["explanation"]


def test_handle_agent_edit_v2_classifies_provider_error_as_closed_failure_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_V2", "1")

    from vibecomfy.comfy_nodes import agent_provider as provider_mod

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent_edit.run_agent_turn_delta",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(provider_mod.ProviderError("not installed")),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "v2-delta-provider-error",
        },
        schema_provider=provider,
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.PROVIDER_ERROR.value,
        stage="agent_response",
        audit_ref_expected=True,
    )
    assert "temporarily unavailable" in result["message"]
    assert "ProviderError(" not in json.dumps(result, sort_keys=True)


# ── M2 T4 — flag-off regression tests ────────────────────────────────────


def test_flag_off_legacy_stage_order_and_prompt_unchanged_with_batch_repl_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When VIBECOMFY_AGENT_EDIT_BATCH_REPL is explicitly unset (and V2 is
    unset), the legacy pipeline stage order, provider prompt shape, and
    response artifacts remain identical to the pre-batch-REPL codebase."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    # Explicitly unset the batch flag — guarantee the flag-off invariant.
    monkeypatch.delenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", raising=False)
    monkeypatch.delenv("VIBECOMFY_AGENT_EDIT_V2", raising=False)

    from vibecomfy.comfy_nodes import agent_edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent_audit import write_audit as real_write_audit

    stage_order: list[str] = []

    def _capture_audit(audit_dir, **kwargs):
        stage_order[:] = list((kwargs.get("stage_results") or {}).keys())
        return real_write_audit(audit_dir, **kwargs)

    monkeypatch.setattr(agent_edit_module, "write_audit", _capture_audit)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "flag-off-legacy",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    # ── stage order ──────────────────────────────────────────────────
    assert result["ok"] is True
    # Legacy path records StageResults for ingest, convert, agent, load_python,
    # lower, validate, emit, queue_validate, and summarize.  The audit stage is
    # recorded as a StageResult only in the v2 path (for agent_edit_v2 metadata
    # injection); the legacy path calls _stage_audit directly without a preceding
    # _record, so "audit" does not appear in the captured stage_results.
    assert stage_order == [
        "ingest",
        "convert",
        "agent",
        "load_python",
        "lower",
        "validate",
        "emit",
        "queue_validate",
        "summarize",
    ]
    # Authoring / delta stages must NOT appear in the legacy path.
    assert {"project", "agent_delta", "apply_delta"}.isdisjoint(stage_order)

    # ── provider prompt shape ─────────────────────────────────────────
    request = json.loads(Path(result["artifacts"]["model_request"]).read_text(encoding="utf-8"))
    # Legacy prompt is simple JSON with keys `python` + `message` — never delta.
    assert "response_contract" not in request
    system = request["messages"][0]["content"]
    user = request["messages"][1]["content"]
    assert "Return only JSON with keys `python` and `message`." in system
    assert "Return only JSON with keys `delta` and `message`." not in system
    assert "```batch" not in system
    assert "batch" not in (system + user).lower()
    assert "Current scratchpad Python" in user
    assert "```python" in user

    # ── response artifacts ────────────────────────────────────────────
    assert "python" in result["artifacts"]
    assert "before_python" in result["artifacts"]
    assert "after_python" in result["artifacts"]
    assert Path(result["artifacts"]["before_python"]).name == "before.py"
    assert Path(result["artifacts"]["after_python"]).name == "after.py"
    # V2-only artifact must NOT leak into the legacy path.
    assert "projection" not in result["artifacts"]
    # delta_ops must NOT leak into the legacy response.
    assert "delta_ops" not in result

    # ── audit shape ───────────────────────────────────────────────────
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert "before_python" in audit["artifacts"]
    assert "after_python" in audit["artifacts"]
    assert "projection" not in audit["artifacts"]
    assert "agent_edit_v2" not in audit.get("metadata", {})
    assert "response_contract" not in json.dumps(audit)


def test_flag_off_v2_delta_stage_order_and_prompt_unchanged_with_batch_repl_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When VIBECOMFY_AGENT_EDIT_BATCH_REPL is explicitly unset but
    VIBECOMFY_AGENT_EDIT_V2=1, the v2 JSON-delta pipeline stage order,
    provider prompt shape, ``response_contract=\"delta\"`` marker, and
    response artifacts remain identical to the pre-batch-REPL codebase."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    # BATCH_REPL off, V2 on — the flag-off invariant for the v2 path.
    monkeypatch.delenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", raising=False)
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_V2", "1")

    def _fake_delta(messages):
        prompt = messages[-1]["content"]
        match = re.search(r'target=\[\"\",\s*\"([^\"]+)\"\].*class=\"SaveImage\"', prompt)
        assert match is not None, "projection must contain a SaveImage target address"
        return {
            "delta": [
                {
                    "op": "set_node_field",
                    "target": ["", match.group(1), "filename_prefix"],
                    "value": "after",
                }
            ],
            "message": "Set save prefix.",
        }

    from vibecomfy.comfy_nodes import agent_edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent_audit import write_audit as real_write_audit

    stage_order: list[str] = []

    def _capture_audit(audit_dir, **kwargs):
        stage_order[:] = list((kwargs.get("stage_results") or {}).keys())
        return real_write_audit(audit_dir, **kwargs)

    monkeypatch.setattr(agent_edit_module, "write_audit", _capture_audit)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "flag-off-v2",
        },
        schema_provider=provider,
        deepseek_client=_fake_delta,
        session_root=tmp_path,
    )

    # ── stage order ──────────────────────────────────────────────────
    assert result["ok"] is True
    assert stage_order == [
        "ingest",
        "project",
        "agent_delta",
        "apply_delta",
        "queue_validate",
        "summarize",
        "audit",
    ]
    # Authoring / legacy stages must NOT appear in the v2 delta path.
    assert {"convert", "agent", "load_python", "lower", "validate", "emit"}.isdisjoint(stage_order)

    # ── provider prompt shape ─────────────────────────────────────────
    request = json.loads(Path(result["artifacts"]["model_request"]).read_text(encoding="utf-8"))
    assert request["response_contract"] == "delta"
    system = request["messages"][0]["content"]
    user = request["messages"][1]["content"]
    assert "Return only JSON with keys `delta` and `message`." in system
    assert "Return only JSON with keys `python` and `message`." not in system
    assert "```batch" not in system
    assert "batch" not in (system + user).lower()
    assert "Address-preserving UI projection" in user

    # ── response artifacts ────────────────────────────────────────────
    assert "projection" in result["artifacts"]
    assert Path(result["artifacts"]["projection"]).name == "projection.txt"
    # Legacy-only artifacts must NOT leak into the v2 path.
    assert "python" not in result["artifacts"]
    assert "before_python" not in result["artifacts"]
    assert "after_python" not in result["artifacts"]
    # delta_ops must be present.
    assert "delta_ops" in result
    assert len(result["delta_ops"]) == 1
    assert result["delta_ops"][0]["op"] == "set_node_field"
    assert result["delta_ops"][0]["value"] == "after"

    # ── audit shape ───────────────────────────────────────────────────
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert "projection" in audit["artifacts"]
    assert "before_python" not in audit["artifacts"]
    assert "after_python" not in audit["artifacts"]
    assert audit["metadata"]["agent_edit_v2"]["enabled"] is True
    assert audit["metadata"]["agent_edit_v2"]["op_count"] == 1
    assert "batch_repl" not in json.dumps(audit)


def test_handle_agent_edit_batch_repl_runs_bounded_loop_with_turn0_render_then_diff_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
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
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    captured_messages: list[list[dict[str, str]]] = []
    session_stats = {"init": 0, "search_calls": []}

    from vibecomfy.porting import edit_session as edit_session_module

    real_edit_session = edit_session_module.EditSession

    class _TrackingSession(real_edit_session):
        def __init__(self, *args, **kwargs):
            session_stats["init"] += 1
            super().__init__(*args, **kwargs)

        def search(self, *, formatted=False, **kwargs):
            session_stats["search_calls"].append(formatted)
            return super().search(formatted=formatted, **kwargs)

    monkeypatch.setattr(edit_session_module, "EditSession", _TrackingSession)

    responses = iter(
        [
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Applied the requested save-prefix change.",
            },
            {
                "batch": 'saveimage.not_a_field = "bad"',
                "message": "Tried a follow-up edit.",
            },
        ]
    )

    def _fake_batch_client(messages):
        captured_messages.append(messages)
        return next(responses)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "batch-loop-core",
            "max_batches": 4,
            "max_consecutive_errors": 1,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.MODEL_MISTAKE.value,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    assert session_stats["init"] == 1
    assert session_stats["search_calls"] == [True]
    assert len(captured_messages) == 2

    turn0_system = captured_messages[0][0]["content"]
    turn0_user = captured_messages[0][1]["content"]
    assert "```batch" in turn0_system
    assert "Current scratchpad Python (full render):" in turn0_user
    assert "Available node signatures" in turn0_user
    assert "Diff from previous render" not in turn0_user

    turn1_user = captured_messages[1][1]["content"]
    assert "Current scratchpad Python (full render):" not in turn1_user
    assert "Diff from previous render:" in turn1_user
    assert "Teaching report from previous turn:" in turn1_user
    assert "filename_prefix='after'" in turn1_user
    assert "✓ Statement 1: set_node_field" in turn1_user

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["metadata"]["batch_repl"]["enabled"] is True
    assert audit["metadata"]["batch_repl"]["turn_count"] == 2
    assert audit["metadata"]["batch_repl"]["budget_state"]["remaining_batches"] == 2
    assert audit["metadata"]["batch_repl"]["budget_state"]["consecutive_errors"] == 1
    request_turns = json.loads(
        Path(audit["artifacts"]["model_request"]["path"]).read_text(encoding="utf-8")
    )["turns"]
    response_turns = json.loads(
        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
    )["turns"]
    assert len(request_turns) == 2
    assert len(response_turns) == 2
    assert response_turns[0]["batch_result"]["landed_op_count"] == 1
    assert response_turns[1]["batch_result"]["batch_ok"] is False


def test_batch_budget_failure_kind_prefers_schema_gap_then_unrepresentable_then_model_mistake() -> None:
    from vibecomfy.comfy_nodes import agent_edit as agent_edit_module

    assert (
        agent_edit_module._batch_budget_failure_kind(
            [
                {
                    "diagnostics": [
                        {
                            "code": "ambiguous_bare_reference",
                            "message": "requires a schema-backed target socket type",
                        }
                    ],
                    "statements": [],
                },
                {
                    "diagnostics": [
                        {
                            "code": "unknown_target_field",
                            "message": "unknown field",
                        }
                    ],
                    "statements": [],
                },
            ]
        )
        == FailureKind.SCHEMA_GAP
    )
    assert (
        agent_edit_module._batch_budget_failure_kind(
            [
                {
                    "diagnostics": [
                        {
                            "code": "cross_scope_add_node_unsupported",
                            "message": "cross-scope add-node unsupported",
                        }
                    ],
                    "statements": [],
                }
            ]
        )
        == FailureKind.UNREPRESENTABLE
    )
    assert (
        agent_edit_module._batch_budget_failure_kind(
            [
                {
                    "diagnostics": [
                        {
                            "code": "unknown_target_field",
                            "message": "unknown field",
                        }
                    ],
                    "statements": [],
                }
            ]
        )
        == FailureKind.MODEL_MISTAKE
    )


def test_handle_agent_edit_batch_repl_reports_partial_success_hints_dependency_cause_and_budget_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
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
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _fake_batch_client(_messages):
        return {
            "batch": "\n".join(
                [
                    'saveimage.filename_prefix = "after"',
                    'saveimage.not_a_field = "bad"',
                    "extra = SaveImage(images=loadimage.image, relation='right_of')",
                    "saveimage.images = extra.image",
                ]
            ),
            "message": "Tried a mixed batch with a few follow-up edits.",
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix and wire an extra save node",
            "session_id": "batch-partial-stop",
            "max_batches": 4,
            "max_consecutive_errors": 1,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.MODEL_MISTAKE.value,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    issue = result["agent_failure_context"]["issues"][0]
    assert issue["code"] == "batch_budget_exhausted"
    assert issue["detail"]["turn_count"] == 1
    assert issue["detail"]["budget_state"]["consecutive_errors"] == 1

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    batch_meta = audit["metadata"]["batch_repl"]
    assert batch_meta["turn_count"] == 1
    assert batch_meta["budget_state"]["remaining_batches"] == 3
    assert batch_meta["budget_state"]["consecutive_errors"] == 1
    assert batch_meta["exit_mode"] == ""
    assert batch_meta["final_summary"] == "Stopped after 1 batch turn(s); 3 batch(es) remaining."
    assert "Batch summary: 1 landed, 3 failed, 3 batch diagnostic(s), 3 batch(es) remaining, 1 consecutive error turn(s)." in batch_meta["feedback"]
    assert "✓ Statement 1: set_node_field" in batch_meta["feedback"]
    assert "✗ Statement 2: set_node_field" in batch_meta["feedback"]
    assert "cause: Statement depends on graph name 'extra' whose add-node statement did not land." in batch_meta["feedback"]
    assert "unknown_target_field: SaveImage has no editable field or input named 'not_a_field'." in batch_meta["feedback"]
    assert "unbound_graph_name: Graph name 'extra' is currently unbound because its add-node statement did not land." in batch_meta["feedback"]

    response_turns = json.loads(
        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
    )["turns"]
    turn0 = response_turns[0]["batch_result"]
    assert turn0["batch_ok"] is False
    assert turn0["landed_op_count"] == 1
    assert turn0["statement_count"] == 4
    assert len(turn0["diagnostics"]) == 3
    assert turn0["report"] == batch_meta["feedback"]

    statements = turn0["statements"]
    assert [item["landed"] for item in statements] == [True, False, False, False]
    assert statements[1]["diagnostics"][0]["code"] == "unknown_target_field"
    assert statements[1]["diagnostics"][0]["teaching_hint"] == (
        "Check the available field and input names. Use describe(name) to see the node's shape."
    )
    assert statements[2]["diagnostics"][0]["code"] == "anchor_target_missing"
    assert statements[3]["diagnostics"][0]["code"] == "unbound_graph_name"
    assert statements[3]["dependency_cause"] == (
        "Statement depends on graph name 'extra' whose add-node statement did not land."
    )
    assert statements[3]["diagnostics"][0]["teaching_hint"] == (
        "The add-node statement for this name did not land. Fix the node construction call or remove the dependent statement."
    )


def test_handle_agent_edit_batch_repl_returns_successful_non_commit_clarification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])}
    )
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _fake_batch_client(_messages):
        return {
            "batch": 'clarify("before or after the face restoration?")',
            "message": "I need one detail before continuing.",
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "adjust the final save behavior",
            "session_id": "batch-clarify",
            "max_batches": 3,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["clarification_required"] is True
    assert result["graph_unchanged"] is True
    assert result["message"] == "before or after the face restoration?"
    assert result["apply_allowed"] is False
    assert result["queue_allowed"] is False
    assert '"before"' in json.dumps(result["graph"], sort_keys=True)
    assert '"after"' not in json.dumps(result["graph"], sort_keys=True)
    assert "done_summary" not in result

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["metadata"]["batch_repl"]["exit_mode"] == "clarify"
    assert audit["metadata"]["batch_repl"]["turn_count"] == 1


def test_handle_agent_edit_batch_repl_done_commits_and_exposes_gate_c_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
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
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Adjusted the save prefix.",
            },
            {
                "batch": "done()",
                "message": "Ready to commit the candidate.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after and finish",
            "session_id": "batch-done",
            "max_batches": 4,
            "max_consecutive_errors": 2,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert result["queue_allowed"] is False
    assert result["message"].endswith(result["done_summary"])
    assert result["done_summary"].startswith("Gate A passed:")
    assert "Gate B passed:" in result["done_summary"]
    assert "Set saveimage.filename_prefix" in result["done_summary"]
    assert "after" in result["done_summary"]
    assert result["report"]["done_summary"] == result["done_summary"]

    graph_text = json.dumps(result["graph"], sort_keys=True)
    assert "after" in graph_text
    assert "before" not in graph_text

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["metadata"]["batch_repl"]["exit_mode"] == "done"
    assert audit["metadata"]["batch_repl"]["done_summary"] == result["done_summary"]


def test_handle_agent_edit_batch_repl_scripted_transcript_commits_structurally_correct_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={"image": InputSpec("STRING")},
                outputs=[OutputSpec("IMAGE", "image")],
                source_provider="test",
                confidence=1.0,
            ),
            "PassThroughImage": NodeSchema(
                class_type="PassThroughImage",
                pack=None,
                inputs={"image": InputSpec("IMAGE", required=True)},
                outputs=[OutputSpec("IMAGE", "IMAGE")],
                source_provider="test",
                confidence=1.0,
            ),
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
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    wf = VibeWorkflow("batch-transcript", WorkflowSource("batch-transcript"))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    wf.nodes["2"] = VibeNode("2", "PassThroughImage")
    wf.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "before"})
    wf.connect("1.0", "2.image")
    wf.connect("2.0", "3.images")
    graph = emit_ui_json(wf, schema_provider=provider)

    captured_messages: list[list[dict[str, str]]] = []
    scripted_turns = iter(
        [
            {
                "batch": "saveimage.images = loadimage.image",
                "message": "Bypassed the passthrough output.",
            },
            {
                "batch": 'saveimage.not_a_field = "bad"',
                "message": "Tried to finish the rename.",
            },
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Corrected the field name and updated the prefix.",
            },
            {
                "batch": "done()",
                "message": "Ready to commit the candidate.",
            },
        ]
    )

    def _fake_batch_client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_messages.append(messages)
        return next(scripted_turns)

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "bypass the passthrough and rename the final save output",
            "session_id": "batch-transcript",
            "max_batches": 5,
            "max_consecutive_errors": 3,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert result["queue_allowed"] is False
    assert result["done_summary"].startswith("Gate A passed:")
    assert "Rewired saveimage.images" in result["done_summary"]
    assert "Set saveimage.filename_prefix" in result["done_summary"]
    assert len(captured_messages) == 4
    assert "Teaching report from previous turn:" in captured_messages[2][1]["content"]
    assert "unknown_target_field: SaveImage has no editable field or input named 'not_a_field'." in captured_messages[2][1]["content"]

    final_graph = result["graph"]
    nodes_by_id = {str(node["id"]): node for node in final_graph["nodes"]}
    assert [nodes_by_id[node_id]["type"] for node_id in sorted(nodes_by_id)] == [
        "LoadImage",
        "PassThroughImage",
        "SaveImage",
    ]

    save_node = nodes_by_id["3"]
    assert save_node["widgets_values"] == ["after"]
    save_input = next(
        item for item in save_node["inputs"] if item.get("name") == "images"
    )
    passthrough_input = next(
        item for item in nodes_by_id["2"]["inputs"] if item.get("name") == "image"
    )
    link_rows = {
        (
            int(link[1]),
            int(link[2]),
            int(link[3]),
            int(link[4]),
        ): link
        for link in final_graph["links"]
    }
    assert (1, 0, 2, 0) in link_rows
    assert (1, 0, 3, 0) in link_rows
    assert (2, 0, 3, 0) not in link_rows
    assert passthrough_input["link"] == link_rows[(1, 0, 2, 0)][0]
    assert save_input["link"] == link_rows[(1, 0, 3, 0)][0]

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["metadata"]["batch_repl"]["turn_count"] == 4
    assert audit["metadata"]["batch_repl"]["exit_mode"] == "done"
    response_turns = json.loads(
        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
    )["turns"]
    assert [turn["response"]["batch"] for turn in response_turns] == [
        "saveimage.images = loadimage.image",
        'saveimage.not_a_field = "bad"',
        'saveimage.filename_prefix = "after"',
        "done()",
    ]
    assert response_turns[1]["batch_result"]["batch_ok"] is False
    assert response_turns[2]["batch_result"]["batch_ok"] is True


def test_handle_agent_edit_validates_lowered_copy_after_load_python(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    original = VibeWorkflow("original", WorkflowSource("original"))
    original.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    original.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "after"})
    original.connect("1.0", "2.images")
    lowered = original.copy()

    monkeypatch.setattr(
        "vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad",
        lambda _path: original,
    )
    monkeypatch.setattr(
        "vibecomfy.porting.lowering.lower_workflow",
        lambda workflow, **_kwargs: LoweringResult(
            ok=True,
            workflow=lowered,
            evidence=(),
            diagnostics=(),
            lowered_count=1,
        ),
    )

    def _validate(state: AgentEditState, _context) -> StageResult:
        assert state.original_intent_workflow is original
        assert state.edited_workflow is lowered
        return StageResult(
            stage="validate",
            ok=True,
            blocking=False,
            gate_updates={"ir_validate_ok": True},
        )

    def _emit(state: AgentEditState, _context) -> StageResult:
        state.ui_payload = _ui_graph()
        state.report = {"change": {}, "recovery": [], "felt": {}}
        return StageResult(
            stage="emit",
            ok=True,
            blocking=False,
            gate_updates={
                "ui_emit_ok": True,
                "ui_fidelity_ok": True,
                "ui_load_safe_ok": True,
            },
        )

    def _summarize(state: AgentEditState, _context) -> StageResult:
        state.artifacts = {}
        return StageResult(
            stage="summarize",
            ok=True,
            blocking=False,
            gate_updates={"queue_validate_ok": True},
        )

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent_edit._stage_validate", _validate)
    monkeypatch.setattr("vibecomfy.comfy_nodes.agent_edit._stage_emit", _emit)
    monkeypatch.setattr("vibecomfy.comfy_nodes.agent_edit._stage_summarize", _summarize)

    from vibecomfy.comfy_nodes import agent_edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent_audit import write_audit as real_write_audit

    stage_order: list[str] = []

    def _capture_audit(audit_dir, **kwargs):
        stage_order[:] = list((kwargs.get("stage_results") or {}).keys())
        return real_write_audit(audit_dir, **kwargs)

    monkeypatch.setattr(agent_edit_module, "write_audit", _capture_audit)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "lower-success",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["gates"]["lower_ok"] is True
    assert result["gates"]["ir_validate_ok"] is True
    assert stage_order == [
        "ingest",
        "convert",
        "agent",
        "load_python",
        "lower",
        "validate",
        "emit",
        "summarize",
    ]


def test_handle_agent_edit_blocks_on_lowering_failure_before_validate_or_emit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    monkeypatch.setattr(
        "vibecomfy.porting.lowering.lower_workflow",
        lambda *_args, **_kwargs: LoweringResult(
            ok=False,
            workflow=None,
            evidence=(),
            diagnostics=(
                LoweringDiagnostic(
                    code="lowered_copy_validation_failed",
                    message="Lowered edge validation failed.",
                    loop_node_id="10",
                    loop_uid="loop-10",
                    detail={"validation_issue": {"code": "invalid_link_shape"}},
                ),
            ),
            lowered_count=0,
        ),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "lower-fail",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.LOWERING_FAILURE.value,
        stage="lower",
        audit_ref_expected=True,
    )
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["gates"]["python_load_ok"] is True
    assert audit["gates"]["lower_ok"] is False
    assert audit["gates"]["ir_validate_ok"] is False
    stages = {stage["stage"]: stage for stage in audit["stage_results"]}
    assert {"ingest", "convert", "agent", "load_python", "lower"} <= set(stages)
    assert "validate" not in stages
    assert "emit" not in stages


def test_handle_agent_edit_threads_synthetic_lowered_provenance_without_emitting_loop_nodes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    original = VibeWorkflow("original-intent", WorkflowSource("original-intent"))
    original.nodes["10"] = VibeNode("10", "vibecomfy.loop")

    lowered = VibeWorkflow("lowered-native", WorkflowSource("lowered-native"))
    lowered.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    lowered.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "after"})
    lowered.connect("1.0", "2.images")

    monkeypatch.setattr(
        "vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad",
        lambda _path: original,
    )
    monkeypatch.setattr(
        "vibecomfy.porting.lowering.lower_workflow",
        lambda workflow, **_kwargs: LoweringResult(
            ok=True,
            workflow=lowered,
            evidence=(
                LoweringEvidence(
                    loop_uid="intent-loop-10",
                    loop_node_id="10",
                    original_intent_hash="intent-hash",
                    variable="seed",
                    iterations=2,
                    iteration_values=(101, 202),
                    lowered_node_count=2,
                    source_to_lowered_node_map={"intent-loop-10": ("native-1", "native-2")},
                    lowered_fragment_hash="lowered-hash",
                    layout_policy="horizontal_stride_clone:offset=300",
                    validation_result={"ok": True, "issues": []},
                ),
            ),
            diagnostics=(),
            lowered_count=1,
        ),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "lowered-provenance",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert all(node["type"] != "vibecomfy.loop" for node in result["graph"]["nodes"])
    assert all(node["class_type"] != "vibecomfy.loop" for node in lowered.compile("api").values())
    assert result["report"]["recovery"][-1] == {
        "node_id": "10",
        "class_type": "vibecomfy.loop",
        "kind": "loop",
        "uid": "intent-loop-10",
        "lowered": True,
        "runtime_backed": False,
        "provider": "static_lowering",
        "confidence": 1.0,
        "diagnostic": "statically lowered to 2 native node(s)",
        "lowered_native_count": 2,
        "source_node_id": "10",
        "source_node_uid": "intent-loop-10",
        "original_intent_hash": "intent-hash",
        "lowered_fragment_hash": "lowered-hash",
        "layout_policy": "horizontal_stride_clone:offset=300",
        "variable": "seed",
        "iterations": 2,
        "iteration_values": [101, 202],
    }
    assert result["report"]["change"]["lowered"] == [
        {
            "node_id": "10",
            "class_type": "vibecomfy.loop",
            "kind": "loop",
            "uid": "intent-loop-10",
            "lowered": True,
            "source_node_id": "10",
            "source_node_uid": "intent-loop-10",
            "lowered_native_count": 2,
            "original_intent_hash": "intent-hash",
            "lowered_fragment_hash": "lowered-hash",
        }
    ]
    assert result["report"]["queue_blockers"] == []
    assert result["queue_allowed"] is True


def test_handle_agent_edit_audit_threads_complete_lowering_metadata_and_keeps_queue_unblocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    original = VibeWorkflow("original-intent", WorkflowSource("original-intent"))
    original.nodes["10"] = VibeNode("10", "vibecomfy.loop")

    lowered = VibeWorkflow("lowered-native", WorkflowSource("lowered-native"))
    lowered.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    lowered.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "after"})
    lowered.connect("1.0", "2.images")

    monkeypatch.setattr(
        "vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad",
        lambda _path: original,
    )
    monkeypatch.setattr(
        "vibecomfy.porting.lowering.lower_workflow",
        lambda workflow, **_kwargs: LoweringResult(
            ok=True,
            workflow=lowered,
            evidence=(
                LoweringEvidence(
                    loop_uid="intent-loop-10",
                    loop_node_id="10",
                    original_intent_hash="intent-hash",
                    variable="prompt",
                    iterations=3,
                    iteration_values=("frame 1", "frame 2", "frame 3"),
                    lowered_node_count=3,
                    source_to_lowered_node_map={
                        "20": (
                            "intent-loop-10:iter0:20",
                            "intent-loop-10:iter1:20",
                            "intent-loop-10:iter2:20",
                        )
                    },
                    lowered_fragment_hash="lowered-hash",
                    layout_policy="horizontal_stride_clone:offset=300",
                    validation_result={
                        "ok": True,
                        "issue_count": 0,
                        "error_count": 0,
                        "warning_count": 0,
                        "issues": [],
                    },
                ),
            ),
            diagnostics=(),
            lowered_count=1,
        ),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "lowered-audit",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["queue_allowed"] is True
    assert result["report"]["queue_blockers"] == []

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["metadata"]["provider"] == {"provider": "test_client"}
    assert audit["metadata"]["lowering"] == [
        {
            "loop_uid": "intent-loop-10",
            "loop_node_id": "10",
            "original_intent_hash": "intent-hash",
            "variable": "prompt",
            "iterations": 3,
            "iteration_values": ["frame 1", "frame 2", "frame 3"],
            "node_count": 3,
            "source_to_lowered_node_map": {
                "20": [
                    "intent-loop-10:iter0:20",
                    "intent-loop-10:iter1:20",
                    "intent-loop-10:iter2:20",
                ]
            },
            "lowered_graph_fragment_hash": "lowered-hash",
            "layout_policy": "horizontal_stride_clone:offset=300",
            "validation_result": {
                "ok": True,
                "issue_count": 0,
                "error_count": 0,
                "warning_count": 0,
                "issues": [],
            },
        }
    ]


def test_handle_agent_edit_uses_agent_generated_loader(
    tmp_path: Path,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    with patch(
        "vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad"
    ) as load_generated:
        generated = VibeWorkflow(
            "agent-edit-generated", WorkflowSource("agent-edit-generated")
        )
        generated.nodes["1"] = VibeNode(
            "1",
            "LoadImage",
            inputs={"image": "input.png"},
            metadata={"provenance": "agent_generated"},
        )
        generated.nodes["2"] = VibeNode(
            "2",
            "SaveImage",
            inputs={"filename_prefix": "after"},
            metadata={"provenance": "agent_generated"},
        )
        generated.connect("1.0", "2.images")
        load_generated.return_value = generated

        result = handle_agent_edit(
            {
                "graph": _ui_graph(),
                "task": "change the save prefix to after",
                "session_id": "t2",
            },
            schema_provider=provider,
            deepseek_client=_fake_deepseek_replace(
                "before", "after", "Changed the save prefix."
            ),
            session_root=tmp_path,
        )

    load_generated.assert_called_once()
    for node in generated.nodes.values():
        assert node.metadata.get("provenance") == "agent_generated"
        confirm(node)
        assert node.metadata.get("provenance") == "agent_generated"
    assert result["graph"]["nodes"]


@pytest.mark.parametrize(
    ("payload", "explanation"),
    [
        (None, "Request body must be a JSON object."),
        ({"graph": _ui_graph()}, "`task` is required."),
        (
            {"graph": "oops", "task": "change the save prefix to after"},
            "`graph` must be a ComfyUI UI JSON object.",
        ),
    ],
)
def test_handle_agent_edit_input_failures_return_frozen_envelopes(
    tmp_path: Path,
    payload: object,
    explanation: str,
) -> None:
    result = handle_agent_edit(
        payload,  # type: ignore[arg-type]
        session_root=tmp_path,
        deepseek_client=lambda _: {},
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.MISSING_REQUIRED_FIELD.value,
        stage="ingest",
        audit_ref_expected=False,
    )
    assert result["agent_failure_context"]["explanation"] == explanation
    assert result["retryable"] is True
    assert "turn_id" not in result


# ── T7: focused agent-edit provenance & hostile-rejection tests ──────────


def test_agent_edit_nodes_never_user_confirmed(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Prove that model-edited Python loaded through the agent-edit path
    carries ``agent_generated`` provenance, never ``user_confirmed``.

    Even after ``confirm()`` / ``confirm_node()`` the provenance must remain
    ``agent_generated`` because the restricted loader is the only minter and
    ``confirm`` is a no-op for this literal.
    """
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t3",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    # The agent-edit round-trip succeeded (no exception).
    assert result["graph"]["nodes"]
    assert result["report"]["change"]

    # Load the model-edited Python back through the restricted loader and
    # inspect provenance directly.
    py_path = Path(result["artifacts"]["python"])
    edited_wf = load_agent_generated_scratchpad(py_path)

    assert len(edited_wf.nodes) >= 2, "Expected at least 2 nodes in model-edited workflow"

    # 1. Every node must carry agent_generated, NOT user_confirmed.
    for node_id, node in edited_wf.nodes.items():
        prov = read_provenance(node)
        assert prov == "agent_generated", (
            f"Node {node_id} ({node.class_type}) has provenance {prov!r}; "
            f"expected 'agent_generated', must NOT be 'user_confirmed'"
        )

    # 2. Free-function confirm() must be a no-op on agent_generated.
    for node_id, node in edited_wf.nodes.items():
        before = read_provenance(node)
        confirm(node)
        after = read_provenance(node)
        assert after == "agent_generated", (
            f"confirm() on node {node_id} changed provenance "
            f"from {before!r} to {after!r}; must remain 'agent_generated'"
        )

    # 3. workflow.confirm_node() must be a no-op on agent_generated.
    for node_id in edited_wf.nodes:
        before = read_provenance(edited_wf.nodes[node_id])
        edited_wf.confirm_node(node_id)
        after = read_provenance(edited_wf.nodes[node_id])
        assert after == "agent_generated", (
            f"confirm_node({node_id!r}) changed provenance "
            f"from {before!r} to {after!r}; must remain 'agent_generated'"
        )

    # 4. Pre-existing test: confirm() called a second time is still a no-op.
    for node in edited_wf.nodes.values():
        confirm(node)
        assert read_provenance(node) == "agent_generated"


def test_agent_edit_rejects_hostile_model_output(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Hostile model output (command execution via ``os.system``) is rejected
    by the AST scanner before execution and before any gate interaction."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    hostile_source = _fixture_source("command_execution.py")

    def hostile_deepseek(_messages):
        return {"python": hostile_source, "message": "done"}

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "run this hostile code",
            "session_id": "t4",
        },
        schema_provider=provider,
        deepseek_client=hostile_deepseek,
        session_root=tmp_path,
    )

    assert result["ok"] is False
    assert result["kind"] == FailureKind.AST_SCAN_FAILURE.value
    assert result["stage"] == "load_python"
    assert result["audit_ref"]["path"]
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    stages = {stage["stage"]: stage for stage in audit["stage_results"]}
    assert {"ingest", "convert", "agent", "load_python"} <= set(stages)
    assert "validate" not in stages
    assert "emit" not in stages
    assert stages["load_python"]["ok"] is False
    assert stages["load_python"]["blocking"] is True
    assert stages["ingest"]["duration_ms"] is not None
    assert stages["convert"]["artifacts"]
    assert audit["gates"]["python_load_ok"] is False


def test_agent_edit_rejects_hostile_canary_no_execution(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Hostile model output that writes a canary file at module level is
    rejected before execution — the canary file must not exist."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    canary = tmp_path / "should_not_exist.txt"
    hostile_source = _fixture_source("module_side_effect_canary.py").replace(
        "__CANARY_PATH__", str(canary)
    )

    def hostile_deepseek(_messages):
        return {"python": hostile_source, "message": "executed"}

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "run this hostile canary code",
            "session_id": "t5",
        },
        schema_provider=provider,
        deepseek_client=hostile_deepseek,
        session_root=tmp_path,
    )

    assert result["ok"] is False
    assert result["kind"] == FailureKind.AST_SCAN_FAILURE.value
    assert result["stage"] == "load_python"

    # The hostile module-level side effect must never have executed.
    assert not canary.exists(), (
        f"Canary file {canary} exists — hostile code was executed!"
    )


def test_agent_edit_rejects_multiple_hostile_bypass_classes(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """A representative set of hostile bypass classes is rejected before
    execution through the agent-edit path. Each fixture is fed as model
    output and must produce ``AgentGeneratedLoadError``."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    hostile_fixtures = [
        "file_read.py",
        "hidden_import.py",
        "dunder_traversal.py",
        "encoded_import_trick.py",
        "network_call.py",
        "socket_call.py",
        "subprocess_call.py",
        "env_read.py",
        "dynamic_attribute_access.py",
    ]

    for fixture_name in hostile_fixtures:
        hostile_source = _fixture_source(fixture_name)

        def hostile_deepseek(_messages, _src=hostile_source):
            return {"python": _src, "message": "done"}

        result = handle_agent_edit(
            {
                "graph": _ui_graph(),
                "task": "run hostile code",
                "session_id": f"t-{fixture_name}",
            },
            schema_provider=provider,
            deepseek_client=hostile_deepseek,
            session_root=tmp_path,
        )

        assert result["ok"] is False, f"{fixture_name} passed scan but should have failed"
        assert result["kind"] == FailureKind.AST_SCAN_FAILURE.value
        assert result["stage"] == "load_python"


def test_agent_edit_rejects_malformed_syntax_from_model(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Malformed Python syntax from the model is caught in the load_python
    phase and never executed."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    def hostile_deepseek(_messages):
        return {"python": "def build(:\n    pass\n", "message": "syntax error"}

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "return malformed syntax",
            "session_id": "t6",
        },
        schema_provider=provider,
        deepseek_client=hostile_deepseek,
        session_root=tmp_path,
    )

    assert result["ok"] is False
    assert result["kind"] == FailureKind.SYNTAX_ERROR.value
    assert result["stage"] == "load_python"


def test_agent_edit_stage_failure_keeps_untouched_gates_false_and_writes_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    def _boom(*_args, **_kwargs):
        raise RuntimeError("convert exploded")

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent_edit._stage_convert", _boom)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t7",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    assert result["ok"] is False
    assert result["kind"] == FailureKind.VALIDATION_ERROR.value
    assert result["stage"] == "convert"
    assert result["canvas_apply_allowed"] is False
    assert result["queue_allowed"] is False
    assert result["audit_ref"]["path"]
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert {stage["stage"] for stage in audit["stage_results"]} == {"ingest", "convert"}
    assert audit["gates"]["python_load_ok"] is False
    assert audit["gates"]["ir_validate_ok"] is False
    assert audit["gates"]["ui_emit_ok"] is False
    assert audit["gates"]["ui_fidelity_ok"] is False
    assert audit["gates"]["ui_load_safe_ok"] is False
    assert audit["gates"]["queue_validate_ok"] is False


def test_agent_edit_uses_provider_seam_and_classifies_provider_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    from vibecomfy.comfy_nodes import agent_provider as provider_mod

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent_edit.run_agent_turn", provider_mod.run_agent_turn)
    monkeypatch.setattr(
        provider_mod,
        "_load_arnold_runtime",
        lambda: (_ for _ in ()).throw(provider_mod.ProviderError("not installed")),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t8",
        },
        schema_provider=provider,
        session_root=tmp_path,
    )

    assert result["ok"] is False
    assert result["kind"] == FailureKind.PROVIDER_ERROR.value
    assert result["stage"] == "agent_response"
    assert "temporarily unavailable" in result["message"]
    assert result["audit_ref"]["path"]


def test_agent_edit_classifies_provider_malformed_and_missing_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    cases = [
        ("not-json", FailureKind.MALFORMED_MODEL_JSON.value),
        ({"python": "x = 1"}, FailureKind.MISSING_REQUIRED_FIELD.value),
    ]
    session_root = tmp_path / "provider-cases"

    for index, (provider_payload, expected_kind) in enumerate(cases, start=1):
        def _fake_run_agent_turn(*_args, _payload=provider_payload, **_kwargs):
            from vibecomfy.comfy_nodes import agent_provider as provider_mod
            return provider_mod._normalize_agent_response(  # type: ignore[attr-defined]
                _payload,
                route="arnold",
                model="agent-edit",
            )

        monkeypatch.setattr("vibecomfy.comfy_nodes.agent_edit.run_agent_turn", _fake_run_agent_turn)
        result = handle_agent_edit(
            {
                "graph": _ui_graph(),
                "task": "change the save prefix to after",
                "session_id": f"t9-{index}",
            },
            schema_provider=provider,
            session_root=session_root,
        )
        assert result["ok"] is False
        assert result["kind"] == expected_kind
        assert result["stage"] == "agent_response"
        assert result["apply_allowed"] is False
        assert result["queue_allowed"] is False
        assert result["audit_ref"]["path"]


@pytest.mark.parametrize(
    ("exc_factory", "expected_kind"),
    [
        (
            lambda: ConversionWriteError(
                "Validation failed", next_action="Fix the converted workflow."
            ),
            FailureKind.VALIDATION_ERROR.value,
        ),
        (lambda: ValueError("convert exploded"), FailureKind.VALIDATION_ERROR.value),
    ],
)
def test_agent_edit_convert_stage_classifies_known_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exc_factory,
    expected_kind: str,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    def _boom(*_args, **_kwargs):
        raise exc_factory()

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent_edit._stage_convert", _boom)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t10",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result, kind=expected_kind, stage="convert", audit_ref_expected=True
    )
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert {stage["stage"] for stage in audit["stage_results"]} == {"ingest", "convert"}


def test_agent_edit_hostile_loader_failure_keeps_exact_failure_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    report = ScanReport(
        ok=False,
        failures=(
            ScanFailure(
                code="forbidden_import",
                message="import os is forbidden",
                line=1,
                column=1,
            ),
        ),
    )

    def _reject(*_args, **_kwargs):
        raise AgentGeneratedLoadError("scan failed", report=report)

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent_edit.load_agent_generated_scratchpad", _reject,
        raising=False,
    )
    monkeypatch.setattr(
        "vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad",
        _reject,
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "run hostile code",
            "session_id": "t11",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.AST_SCAN_FAILURE.value,
        stage="load_python",
        audit_ref_expected=True,
    )
    assert result["agent_failure_context"]["scan_code"] == "forbidden_import"


@pytest.mark.parametrize(
    ("exc", "expected_kind"),
    [
        (RefusedEmit("guard emit refused", {"node-1": {"axis": "widget_shape"}}), FailureKind.REFUSED_EMIT.value),
        (EditorAheadError([{"uid": "node-2", "class_type": "Note"}]), FailureKind.EDITOR_AHEAD_CONFLICT.value),
    ],
)
def test_agent_edit_emit_stage_classifies_refusal_and_editor_ahead(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
    expected_kind: str,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    def _boom(*_args, **_kwargs):
        raise exc

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent_edit._stage_emit", _boom)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t12",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result, kind=expected_kind, stage="emit", audit_ref_expected=True
    )
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["gates"]["python_load_ok"] is True
    assert audit["gates"]["ir_validate_ok"] is True
    assert audit["gates"]["ui_emit_ok"] is False


def test_agent_edit_idempotency_conflict_returns_stale_state_mismatch(
    tmp_path: Path,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    first = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t13",
            "idempotency_key": "same-key",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )
    assert first["ok"] is True

    conflict = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to something else",
            "session_id": "t13",
            "idempotency_key": "same-key",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "other", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        conflict,
        kind=FailureKind.STALE_STATE_MISMATCH.value,
        stage="ingest",
        audit_ref_expected=True,
    )
    assert "_allocation_failures" in conflict["audit_ref"]["path"]


def test_agent_edit_stale_submit_fails_at_ingest_via_state_match_gate(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit_accept

    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    original_graph = _ui_graph()

    first = handle_agent_edit(
        {
            "graph": original_graph,
            "task": "change the save prefix to after",
            "session_id": "stale-submit",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )
    assert first["ok"] is True
    assert first["submit_graph_hash"] == payload_hash(original_graph)
    assert "submitted_client_graph_hash" in first
    assert first["submitted_client_graph_hash"] is None
    assert first["candidate_graph_hash"] == payload_hash(first["graph"])
    assert first["baseline_graph_hash"] is None

    accepted = _handle_agent_edit_accept(
        {
            "session_id": "stale-submit",
            "turn_id": first["turn_id"],
            "client_graph_hash": payload_hash(original_graph),
            "idempotency_key": "accept-stale-submit",
        },
        session_root=tmp_path,
    )
    assert accepted["ok"] is True
    assert accepted["baseline_graph_hash"] == payload_hash(first["graph"])

    stale = handle_agent_edit(
        {
            "graph": original_graph,
            "task": "change the save prefix to something else",
            "session_id": "stale-submit",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "other", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        stale,
        kind=FailureKind.STALE_STATE_MISMATCH.value,
        stage="ingest",
        audit_ref_expected=True,
    )
    assert stale["agent_failure_context"]["issues"][0]["failure_kind"] == FailureKind.STALE_STATE_MISMATCH.value
    detail = stale["agent_failure_context"]["issues"][0]["detail"]
    assert detail["reason"] == "hash_mismatch"
    assert detail["client_graph_hash_label"] == "submit_graph_hash"
    assert detail["baseline_graph_hash"] == payload_hash(first["graph"])
    assert detail["client_graph_hash"] == payload_hash(original_graph)
    audit = json.loads(Path(stale["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["gates"]["state_match_ok"] is False


def test_agent_edit_queue_blockers_keep_canvas_apply_true_but_queue_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    from vibecomfy.comfy_nodes.agent_contracts import StageResult

    queue_issue = {
        "code": "schema_less_queue_blocker",
        "severity": "error",
        "failure_kind": FailureKind.SCHEMA_LESS_QUEUE_BLOCKER.value,
        "detail": {"node_id": "42"},
        "message": "schema-less queue blocker",
    }
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent_edit.queue_stage_result",
        lambda **_kwargs: StageResult(
            stage="queue_validate",
            ok=False,
            blocking=False,
            issues=(queue_issue,),
        ),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t14",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["canvas_apply_allowed"] is True
    assert result["apply_allowed"] is True
    assert result["queue_allowed"] is False
    assert result["gates"]["queue_validate_ok"] is False
    assert result["audit_ref"]["path"]
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["turn_state"] == "candidate"


def test_agent_edit_unknown_transition_audit_failure_does_not_rollback_session_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes import agent_audit, agent_edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent_session import read_state

    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    first_turn_id, _submit_graph_hash, _candidate_graph_hash = _allocate_action_candidate(
        tmp_path,
        session_id="unknown-audit",
        label="first",
    )
    real_write_audit = agent_audit.write_audit

    def _write_with_unknown_failure(audit_dir, **kwargs):
        if Path(audit_dir).name == "unknown_audit":
            raise OSError("unknown audit unavailable")
        return real_write_audit(audit_dir, **kwargs)

    monkeypatch.setattr(agent_edit_module, "write_audit", _write_with_unknown_failure)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "unknown-audit",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    state = read_state(tmp_path / "unknown-audit")
    assert state["turns"][first_turn_id]["state"] == "unknown"
    assert not (
        tmp_path / "unknown-audit" / "turns" / first_turn_id / "unknown_audit" / "audit.json"
    ).exists()


def test_agent_edit_writes_unknown_transition_audit_with_unknown_turn_state(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent_session import read_state

    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    first_turn_id, _submit_graph_hash, _candidate_graph_hash = _allocate_action_candidate(
        tmp_path,
        session_id="unknown-audit-ok",
        label="first",
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "unknown-audit-ok",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    state = read_state(tmp_path / "unknown-audit-ok")
    assert state["turns"][first_turn_id]["state"] == "unknown"
    unknown_audit = json.loads(
        (
            tmp_path / "unknown-audit-ok" / "turns" / first_turn_id / "unknown_audit" / "audit.json"
        ).read_text(encoding="utf-8")
    )
    assert unknown_audit["turn_state"] == "unknown"
    assert unknown_audit["metadata"]["reason"] == "superseded_by_new_submit"


def test_agent_edit_audit_failure_returns_exact_failure_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent_edit._stage_audit",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t15",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.AUDIT_WRITE_FAILURE.value,
        stage="audit",
        audit_ref_expected=False,
    )
    assert result["audit_error"] == "disk full"


def test_agent_edit_route_returns_closed_failure_envelopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit

    missing_task = _handle_agent_edit({"graph": _ui_graph()}, session_root=tmp_path)
    _assert_failure_defaults(
        missing_task,
        kind=FailureKind.MISSING_REQUIRED_FIELD.value,
        stage="ingest",
        audit_ref_expected=False,
    )
    assert "ValueError" not in json.dumps(missing_task, sort_keys=True)

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.routes.handle_agent_edit",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    unexpected = _handle_agent_edit(
        {"graph": _ui_graph(), "task": "change the save prefix to after"},
        session_root=tmp_path,
    )
    _assert_failure_defaults(
        unexpected,
        kind=FailureKind.VALIDATION_ERROR.value,
        stage="route",
        audit_ref_expected=False,
    )
    assert unexpected["agent_failure_context"]["explanation"] == "boom"
    assert "RuntimeError" not in json.dumps(unexpected, sort_keys=True)


def test_agent_edit_route_preserves_classified_handler_failure_without_open_kinds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent_contracts import failure_envelope
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit

    classified = failure_envelope(
        FailureKind.PROVIDER_ERROR,
        "agent_response",
        agent_failure_context={"explanation": "provider unavailable"},
    ).to_dict()
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.routes.handle_agent_edit",
        lambda *_args, **_kwargs: classified,
    )

    result = _handle_agent_edit(
        {"graph": _ui_graph(), "task": "change the save prefix to after"},
        session_root=tmp_path,
    )

    assert result == classified
    assert result["kind"] == FailureKind.PROVIDER_ERROR.value
    assert result["kind"] in {kind.value for kind in FailureKind}
    assert "ProviderError(" not in json.dumps(result, sort_keys=True)


def test_agent_edit_action_routes_accept_reject_idempotency_and_audit(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent_session import read_state
    from vibecomfy.comfy_nodes.routes import (
        _handle_agent_edit_accept,
        _handle_agent_edit_audit,
        _handle_agent_edit_reject,
    )

    turn_id, submit_graph_hash, candidate_graph_hash = _allocate_action_candidate(
        tmp_path,
        session_id="s1",
        label="accept",
    )
    accept_payload = {
        "session_id": "s1",
        "turn_id": turn_id,
        "client_graph_hash": submit_graph_hash,
        "idempotency_key": "accept-1",
    }

    accepted = _handle_agent_edit_accept(accept_payload, session_root=tmp_path)
    replayed = _handle_agent_edit_accept(accept_payload, session_root=tmp_path)

    assert replayed == accepted
    assert accepted["ok"] is True
    assert accepted["action"] == "accept"
    assert accepted["baseline_turn_id"] == turn_id
    assert accepted["submit_graph_hash"] == submit_graph_hash
    assert accepted["candidate_graph_hash"] == candidate_graph_hash
    assert accepted["baseline_graph_hash"] == candidate_graph_hash
    assert accepted["audit_ref"]["path"].endswith("/accept_audit/audit.json")
    state = read_state(tmp_path / "s1")
    assert state["baseline_turn_id"] == turn_id
    assert state["turns"][turn_id]["state"] == "accepted"

    conflicting_reject = _handle_agent_edit_reject(
        {
            "session_id": "s1",
            "turn_id": turn_id,
            "idempotency_key": "reject-1",
        },
        session_root=tmp_path,
    )
    assert conflicting_reject["ok"] is False
    assert conflicting_reject["kind"] == FailureKind.EDITOR_AHEAD_CONFLICT.value

    downloaded = _handle_agent_edit_audit(
        {"session_id": "s1", "turn_id": turn_id, "action": "accept"},
        session_root=tmp_path,
    )
    assert downloaded["ok"] is True
    assert downloaded["headers"]["Content-Type"] == "application/json"
    assert "attachment;" in downloaded["headers"]["Content-Disposition"]
    audit_payload = json.loads(downloaded["body"].decode("utf-8"))
    assert audit_payload["metadata"]["action"] == "accept"
    assert audit_payload["turn_state"] == "accepted"


def test_agent_edit_accept_matches_browser_client_graph_hash(tmp_path: Path) -> None:
    """Regression: the browser hashes the graph with a different serialization
    than the backend's canonical ``submit_graph_hash``. Accept must match the
    client's own submit-time hash (``submitted_client_graph_hash``), otherwise a
    user can never apply a candidate from the panel (StaleStateMismatch)."""
    from vibecomfy.comfy_nodes.agent_session import (
        allocate_turn,
        record_idempotent_response,
    )
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit_accept

    graph = {"nodes": [{"id": 1, "type": "SaveImage", "widgets_values": ["browser"]}], "links": []}
    candidate_graph = {
        "nodes": [{"id": 2, "type": "SaveImage", "widgets_values": ["browser-candidate"]}],
        "links": [],
    }
    # A frontend-style hash that deliberately differs from the canonical one.
    browser_hash = "frontend-style-hash-0123456789abcdef"
    assert browser_hash != payload_hash(graph)

    allocation = allocate_turn(
        session_root=tmp_path,
        session_id="s-browser",
        request_payload={"graph": graph, "task": "edit", "client_graph_hash": browser_hash},
    )
    turn_id = str(allocation.context.turn_id)
    record_idempotent_response(
        session_root=tmp_path,
        session_id="s-browser",
        scope="edit",
        idempotency_key=None,
        request_hash=allocation.request_hash,
        response={"ok": True, "turn_id": turn_id, "graph": candidate_graph},
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
    )

    # A hash matching neither the canonical nor the client submit hash is stale.
    # Run this first while the turn is still in the `candidate` state so it
    # exercises the hash gate rather than a state transition.
    stale = _handle_agent_edit_accept(
        {
            "session_id": "s-browser",
            "turn_id": turn_id,
            "client_graph_hash": "totally-different-hash",
            "idempotency_key": "accept-stale",
        },
        session_root=tmp_path,
    )
    assert stale["ok"] is False
    assert stale["kind"] == FailureKind.STALE_STATE_MISMATCH.value

    accepted = _handle_agent_edit_accept(
        {
            "session_id": "s-browser",
            "turn_id": turn_id,
            "client_graph_hash": browser_hash,
            "idempotency_key": "accept-browser",
        },
        session_root=tmp_path,
    )
    assert accepted["ok"] is True, accepted
    assert accepted["action"] == "accept"


def test_agent_edit_v2_accept_requires_server_hash_candidate_hash_and_live_token(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent_session import (
        allocate_turn,
        record_idempotent_response,
    )
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit_accept

    graph = {"nodes": [{"id": 1, "type": "SaveImage", "widgets_values": ["v2"]}], "links": []}
    candidate_graph = {
        "nodes": [{"id": 2, "type": "SaveImage", "widgets_values": ["v2-candidate"]}],
        "links": [],
    }
    client_hash = "browser-hash-v2"
    live_token = "live:rev:1:browser-hash-v2"
    allocation = allocate_turn(
        session_root=tmp_path,
        session_id="s-v2-lock",
        request_payload={
            "graph": graph,
            "task": "edit v2",
            "client_graph_hash": client_hash,
            "client_live_canvas_token": live_token,
        },
    )
    turn_id = str(allocation.context.turn_id)
    record_idempotent_response(
        session_root=tmp_path,
        session_id="s-v2-lock",
        scope="edit",
        idempotency_key=None,
        request_hash=allocation.request_hash,
        response={
            "ok": True,
            "turn_id": turn_id,
            "graph": candidate_graph,
            "delta_ops": [{"op": "set_mode", "target": {"scope_path": [], "uid": "2"}, "mode": 4}],
        },
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
    )
    submit_hash = payload_hash(graph)
    candidate_hash = payload_hash(candidate_graph)

    stale_token = _handle_agent_edit_accept(
        {
            "session_id": "s-v2-lock",
            "turn_id": turn_id,
            "client_graph_hash": client_hash,
            "client_live_canvas_token": "live:rev:2:browser-hash-v2",
            "submit_graph_hash": submit_hash,
            "candidate_graph_hash": candidate_hash,
            "idempotency_key": "accept-v2-stale-token",
        },
        session_root=tmp_path,
    )
    assert stale_token["ok"] is False
    assert stale_token["kind"] == FailureKind.STALE_STATE_MISMATCH.value
    assert "live-canvas token" in stale_token["agent_failure_context"]["explanation"]

    wrong_candidate = _handle_agent_edit_accept(
        {
            "session_id": "s-v2-lock",
            "turn_id": turn_id,
            "client_graph_hash": client_hash,
            "client_live_canvas_token": live_token,
            "submit_graph_hash": submit_hash,
            "candidate_graph_hash": "wrong-candidate-hash",
            "idempotency_key": "accept-v2-wrong-candidate",
        },
        session_root=tmp_path,
    )
    assert wrong_candidate["ok"] is False
    assert wrong_candidate["kind"] == FailureKind.STALE_STATE_MISMATCH.value
    assert "persisted candidate graph hash" in wrong_candidate["agent_failure_context"]["explanation"]

    wrong_submit = _handle_agent_edit_accept(
        {
            "session_id": "s-v2-lock",
            "turn_id": turn_id,
            "client_graph_hash": client_hash,
            "client_live_canvas_token": live_token,
            "submit_graph_hash": "wrong-submit-hash",
            "candidate_graph_hash": candidate_hash,
            "idempotency_key": "accept-v2-wrong-submit",
        },
        session_root=tmp_path,
    )
    assert wrong_submit["ok"] is False
    assert wrong_submit["kind"] == FailureKind.STALE_STATE_MISMATCH.value
    assert "server-side submit graph hash" in wrong_submit["agent_failure_context"]["explanation"]

    accepted = _handle_agent_edit_accept(
        {
            "session_id": "s-v2-lock",
            "turn_id": turn_id,
            "client_graph_hash": client_hash,
            "client_live_canvas_token": live_token,
            "submit_graph_hash": submit_hash,
            "candidate_graph_hash": candidate_hash,
            "idempotency_key": "accept-v2-ok",
        },
        session_root=tmp_path,
    )
    assert accepted["ok"] is True, accepted
    assert accepted["baseline_graph_hash"] == candidate_hash


def test_agent_edit_action_routes_reject_candidates_without_baseline_update(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent_session import read_state
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit_reject

    turn_id, submit_graph_hash, candidate_graph_hash = _allocate_action_candidate(
        tmp_path,
        session_id="s2",
        label="reject",
    )
    reject_payload = {
        "session_id": "s2",
        "turn_id": turn_id,
        "client_graph_hash": submit_graph_hash,
        "idempotency_key": "reject-1",
    }

    rejected = _handle_agent_edit_reject(reject_payload, session_root=tmp_path)
    replayed = _handle_agent_edit_reject(reject_payload, session_root=tmp_path)

    assert replayed == rejected
    assert rejected["ok"] is True
    assert rejected["action"] == "reject"
    assert rejected["baseline_turn_id"] is None
    assert rejected["submit_graph_hash"] == submit_graph_hash
    assert rejected["candidate_graph_hash"] == candidate_graph_hash
    assert rejected["baseline_graph_hash"] is None
    assert rejected["audit_ref"]["path"].endswith("/reject_audit/audit.json")
    reject_audit = json.loads(Path(rejected["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert reject_audit["turn_state"] == "rejected"
    state = read_state(tmp_path / "s2")
    assert state["baseline_turn_id"] is None
    assert state["turns"][turn_id]["state"] == "rejected"


def test_agent_edit_action_routes_cover_replay_conflict_state_mismatch_and_audit_redaction(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent_session import read_state
    from vibecomfy.comfy_nodes.routes import (
        _handle_agent_edit_accept,
        _handle_agent_edit_audit,
        _handle_agent_edit_reject,
    )

    accepted_turn_id, accepted_submit_hash, _accepted_candidate_hash = _allocate_action_candidate(
        tmp_path,
        session_id="s3",
        label="first",
    )
    accepted = _handle_agent_edit_accept(
        {
            "session_id": "s3",
            "turn_id": accepted_turn_id,
            "client_graph_hash": accepted_submit_hash,
            "idempotency_key": "accept-a",
            "api_key": "deepseek-secret",
        },
        session_root=tmp_path,
    )
    repeated_accept = _handle_agent_edit_accept(
        {
            "session_id": "s3",
            "turn_id": accepted_turn_id,
            "client_graph_hash": accepted_submit_hash,
            "idempotency_key": "accept-b",
        },
        session_root=tmp_path,
    )
    accept_key_conflict = _handle_agent_edit_accept(
        {
            "session_id": "s3",
            "turn_id": accepted_turn_id,
            "client_graph_hash": "stale-hash",
            "idempotency_key": "accept-a",
        },
        session_root=tmp_path,
    )
    rejecting_accepted = _handle_agent_edit_reject(
        {
            "session_id": "s3",
            "turn_id": accepted_turn_id,
            "idempotency_key": "reject-accepted",
        },
        session_root=tmp_path,
    )

    rejected_turn_id, rejected_submit_hash, _rejected_candidate_hash = _allocate_action_candidate(
        tmp_path,
        session_id="s3",
        label="second",
    )
    rejected = _handle_agent_edit_reject(
        {
            "session_id": "s3",
            "turn_id": rejected_turn_id,
            "client_graph_hash": rejected_submit_hash,
            "idempotency_key": "reject-a",
        },
        session_root=tmp_path,
    )
    repeated_reject = _handle_agent_edit_reject(
        {
            "session_id": "s3",
            "turn_id": rejected_turn_id,
            "client_graph_hash": rejected_submit_hash,
            "idempotency_key": "reject-b",
        },
        session_root=tmp_path,
    )
    accepting_rejected = _handle_agent_edit_accept(
        {
            "session_id": "s3",
            "turn_id": rejected_turn_id,
            "client_graph_hash": rejected_submit_hash,
            "idempotency_key": "accept-rejected",
        },
        session_root=tmp_path,
    )
    missing_session = _handle_agent_edit_accept(
        {
            "session_id": "missing",
            "turn_id": "0001",
            "client_graph_hash": "hash-missing",
        },
        session_root=tmp_path,
    )
    missing_turn = _handle_agent_edit_reject(
        {
            "session_id": "s3",
            "turn_id": "9999",
        },
        session_root=tmp_path,
    )

    assert accepted["ok"] is True
    assert accepted["baseline_turn_id"] == accepted_turn_id
    assert accepted["baseline_graph_hash"] == accepted["candidate_graph_hash"]
    assert repeated_accept["ok"] is True
    assert repeated_accept["baseline_turn_id"] == accepted_turn_id
    assert repeated_accept["baseline_graph_hash"] == accepted["candidate_graph_hash"]
    assert accept_key_conflict["ok"] is False
    assert accept_key_conflict["kind"] == FailureKind.EDITOR_AHEAD_CONFLICT.value
    assert rejecting_accepted["ok"] is False
    assert rejecting_accepted["kind"] == FailureKind.EDITOR_AHEAD_CONFLICT.value

    assert rejected["ok"] is True
    assert rejected["baseline_turn_id"] == accepted_turn_id
    assert rejected["baseline_graph_hash"] == accepted["candidate_graph_hash"]
    assert repeated_reject["ok"] is True
    assert repeated_reject["baseline_turn_id"] == accepted_turn_id
    assert repeated_reject["baseline_graph_hash"] == accepted["candidate_graph_hash"]
    assert accepting_rejected["ok"] is False
    assert accepting_rejected["kind"] == FailureKind.EDITOR_AHEAD_CONFLICT.value

    assert missing_session["ok"] is False
    assert missing_session["kind"] == FailureKind.STALE_STATE_MISMATCH.value
    assert missing_turn["ok"] is False
    assert missing_turn["kind"] == FailureKind.STALE_STATE_MISMATCH.value

    state = read_state(tmp_path / "s3")
    assert state["baseline_turn_id"] == accepted_turn_id
    assert state["baseline_graph_hash"] == accepted["candidate_graph_hash"]
    assert state["turns"][accepted_turn_id]["state"] == "accepted"
    assert state["turns"][rejected_turn_id]["state"] == "rejected"
    assert state["idempotency_records"]["accept:accept-a"]["turn_id"] == accepted_turn_id
    assert state["idempotency_records"]["reject:reject-a"]["turn_id"] == rejected_turn_id

    accept_response_path = (
        tmp_path / "s3" / "turns" / accepted_turn_id / "accept_response.json"
    )
    reject_response_path = (
        tmp_path / "s3" / "turns" / rejected_turn_id / "reject_response.json"
    )
    accept_response = json.loads(accept_response_path.read_text(encoding="utf-8"))
    reject_response = json.loads(reject_response_path.read_text(encoding="utf-8"))
    assert accept_response["ok"] is True
    assert accept_response["action"] == "accept"
    assert accept_response["turn_id"] == accepted_turn_id
    assert accept_response["baseline_turn_id"] == accepted_turn_id
    assert accept_response["submit_graph_hash"] == accepted_submit_hash
    assert accept_response["baseline_graph_hash"] == accepted["candidate_graph_hash"]
    assert "audit_ref" not in accept_response
    assert reject_response["ok"] is True
    assert reject_response["action"] == "reject"
    assert reject_response["turn_id"] == rejected_turn_id
    assert reject_response["baseline_turn_id"] == accepted_turn_id
    assert reject_response["submit_graph_hash"] == rejected_submit_hash
    assert reject_response["baseline_graph_hash"] == accepted["candidate_graph_hash"]
    assert "audit_ref" not in reject_response

    downloaded = _handle_agent_edit_audit(
        {"session_id": "s3", "turn_id": accepted_turn_id, "action": "accept"},
        session_root=tmp_path,
    )
    assert downloaded["ok"] is True
    assert downloaded["headers"] == {
        "Content-Type": "application/json",
        "Content-Disposition": f'attachment; filename="s3-{accepted_turn_id}-accept_audit.json"',
        "X-Content-Type-Options": "nosniff",
    }
    audit_payload = json.loads(downloaded["body"].decode("utf-8"))
    assert audit_payload["metadata"]["action"] == "accept"
    assert audit_payload["artifacts"]["request"]["api_key"] == "<REDACTED>"
    assert "deepseek-secret" not in downloaded["body"].decode("utf-8")


# ── T8: route-level idempotency regression tests (no hash-value assertions) ─


def test_route_edit_idempotency_replays_same_request_body(
    tmp_path: Path,
) -> None:
    """Route-level same-body replay for the edit endpoint: sending the
    same payload with the same idempotency key returns the identical
    success response.

    No hash-value assertions — this isolates idempotency plumbing."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    payload = {
        "graph": _ui_graph(),
        "task": "change the save prefix to after",
        "session_id": "t-idem-edit-replay",
        "idempotency_key": "edit-replay-route",
    }
    first = handle_agent_edit(
        payload,
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )
    assert first["ok"] is True

    second = handle_agent_edit(
        payload,
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )
    assert second["ok"] is True
    assert second == first


def test_route_accept_idempotency_replays_same_request_body(
    tmp_path: Path,
) -> None:
    """Route-level same-body replay for the accept endpoint."""
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit_accept

    turn_id, submit_graph_hash, _candidate_graph_hash = _allocate_action_candidate(
        tmp_path,
        session_id="t-idem-accept-replay",
        label="accept-replay-route",
    )
    payload = {
        "session_id": "t-idem-accept-replay",
        "turn_id": turn_id,
        "client_graph_hash": submit_graph_hash,
        "idempotency_key": "accept-replay-route",
    }

    first = _handle_agent_edit_accept(payload, session_root=tmp_path)
    assert first["ok"] is True

    second = _handle_agent_edit_accept(payload, session_root=tmp_path)
    assert second == first


def test_route_accept_idempotency_conflicts_on_different_request_body(
    tmp_path: Path,
) -> None:
    """Route-level different-body conflict for the accept endpoint."""
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit_accept

    turn_id, submit_graph_hash, _candidate_graph_hash = _allocate_action_candidate(
        tmp_path,
        session_id="t-idem-accept-conflict",
        label="accept-conflict-route",
    )
    first = _handle_agent_edit_accept(
        {
            "session_id": "t-idem-accept-conflict",
            "turn_id": turn_id,
            "client_graph_hash": submit_graph_hash,
            "idempotency_key": "accept-conflict-route",
            "mode": "safe",
        },
        session_root=tmp_path,
    )
    assert first["ok"] is True

    conflict = _handle_agent_edit_accept(
        {
            "session_id": "t-idem-accept-conflict",
            "turn_id": turn_id,
            "client_graph_hash": submit_graph_hash,
            "idempotency_key": "accept-conflict-route",
            "mode": "force",
        },
        session_root=tmp_path,
    )
    assert conflict["ok"] is False
    assert conflict["kind"] == FailureKind.EDITOR_AHEAD_CONFLICT.value


def test_route_reject_idempotency_replays_same_request_body(
    tmp_path: Path,
) -> None:
    """Route-level same-body replay for the reject endpoint."""
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit_reject

    turn_id, submit_graph_hash, _candidate_graph_hash = _allocate_action_candidate(
        tmp_path,
        session_id="t-idem-reject-replay",
        label="reject-replay-route",
    )
    payload = {
        "session_id": "t-idem-reject-replay",
        "turn_id": turn_id,
        "client_graph_hash": submit_graph_hash,
        "idempotency_key": "reject-replay-route",
    }

    first = _handle_agent_edit_reject(payload, session_root=tmp_path)
    assert first["ok"] is True

    second = _handle_agent_edit_reject(payload, session_root=tmp_path)
    assert second == first


def test_route_reject_idempotency_conflicts_on_different_request_body(
    tmp_path: Path,
) -> None:
    """Route-level different-body conflict for the reject endpoint."""
    from vibecomfy.comfy_nodes.routes import _handle_agent_edit_reject

    turn_id, submit_graph_hash, _candidate_graph_hash = _allocate_action_candidate(
        tmp_path,
        session_id="t-idem-reject-conflict",
        label="reject-conflict-route",
    )
    first = _handle_agent_edit_reject(
        {
            "session_id": "t-idem-reject-conflict",
            "turn_id": turn_id,
            "client_graph_hash": submit_graph_hash,
            "idempotency_key": "reject-conflict-route",
            "mode": "soft",
        },
        session_root=tmp_path,
    )
    assert first["ok"] is True

    conflict = _handle_agent_edit_reject(
        {
            "session_id": "t-idem-reject-conflict",
            "turn_id": turn_id,
            "client_graph_hash": submit_graph_hash,
            "idempotency_key": "reject-conflict-route",
            "mode": "hard",
        },
        session_root=tmp_path,
    )
    assert conflict["ok"] is False
    assert conflict["kind"] == FailureKind.EDITOR_AHEAD_CONFLICT.value


def test_agent_status_and_credentials_route_helpers_do_not_leak_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes import agent_provider
    from vibecomfy.comfy_nodes.routes import _handle_agent_credentials, _handle_agent_status

    monkeypatch.setenv("ARNOLD_API_KEY", "arnold-secret")
    monkeypatch.setattr(
        agent_provider,
        "_load_arnold_runtime",
        lambda: (_ for _ in ()).throw(agent_provider.ProviderError("not installed")),
    )

    status = _handle_agent_status({"route": "anthropic", "model": "agent-edit"})

    assert status["ok"] is False
    assert status["provider_available"] is False
    assert status["route"] == "arnold"
    assert status["requested_route"] == "anthropic"
    assert status["route_metadata"]["tos_acknowledgement_required"] is True
    assert status["credential_presence"]["arnold_api_key"] is True
    assert "arnold-secret" not in json.dumps(status)

    env_path = tmp_path / ".hermes" / ".env"
    saved = _handle_agent_credentials(
        {"provider": "deepseek", "api_key": "deepseek-secret"},
        env_path=env_path,
    )
    ignored = _handle_agent_credentials(
        {"provider": "openai-codex", "api_key": "codex-secret"},
        env_path=tmp_path / ".hermes" / "codex.env",
    )

    assert saved["ok"] is True
    assert saved["stored"] is True
    assert "DEEPSEEK_API_KEY=deepseek-secret" in env_path.read_text(encoding="utf-8")
    assert "deepseek-secret" not in json.dumps(saved)
    assert ignored["ok"] is True
    assert ignored["stored"] is False
    assert ignored["ignored"] is True
    assert ignored["provider"] == "arnold"
    assert ignored["requested_route"] == "openai-codex"
    assert "Arnold/Hermes" in ignored["reason"]
    assert "codex-secret" not in json.dumps(ignored)


def test_agent_status_and_credentials_cover_provider_unavailable_redaction_and_secret_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes import agent_provider
    from vibecomfy.comfy_nodes.agent_audit import write_audit
    from vibecomfy.comfy_nodes.agent_contracts import TurnContext
    from vibecomfy.comfy_nodes.routes import _handle_agent_credentials, _handle_agent_status

    monkeypatch.setenv("ARNOLD_API_KEY", "arnold-secret")
    monkeypatch.setenv("HERMES_API_KEY", "hermes-secret")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-env-secret")

    class Runtime:
        @staticmethod
        def get_agent_status(**_kwargs):
            return {
                "ok": True,
                "detail": "healthy",
                "api_key": "runtime-secret",
                "authorization": "Bearer runtime-token",
                "provider_secret": "provider-secret",
            }

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)
    healthy = _handle_agent_status({"route": "openai-codex", "model": "agent-edit"})

    assert healthy["ok"] is True
    assert healthy["provider_available"] is True
    assert healthy["detail"] == "healthy"
    assert healthy["route"] == "arnold"
    assert healthy["requested_route"] == "openai-codex"
    assert healthy["route_metadata"]["normalized_route"] == "arnold"
    assert healthy["route_metadata"]["browser_api_key_allowed"] is False
    assert healthy["route_options"]["deepseek"]["browser_api_key_allowed"] is True
    assert healthy["credential_presence"] == {
        "arnold_api_key": True,
        "hermes_api_key": True,
        "deepseek_api_key": True,
    }
    dumped_healthy = json.dumps(healthy, sort_keys=True)
    assert "arnold-secret" not in dumped_healthy
    assert "hermes-secret" not in dumped_healthy
    assert "deepseek-env-secret" not in dumped_healthy
    assert "runtime-secret" not in dumped_healthy
    assert "runtime-token" not in dumped_healthy
    assert "provider-secret" not in dumped_healthy

    monkeypatch.setattr(
        agent_provider,
        "_load_arnold_runtime",
        lambda: (_ for _ in ()).throw(agent_provider.ProviderError("not installed")),
    )
    unavailable = _handle_agent_status({"route": "openai-codex", "model": "agent-edit"})

    assert unavailable == {
        "ok": False,
        "route": "arnold",
        "requested_route": "openai-codex",
        "model": "agent-edit",
        "provider": "arnold",
        "provider_available": False,
        "error": "not installed",
        "route_metadata": {
            "requested_route": "openai-codex",
            "normalized_route": "arnold",
            "browser_api_key_allowed": False,
            "guidance": "OpenAI Codex runs through local Arnold/Hermes. Configure local "
            "ARNOLD_API_KEY or HERMES_API_KEY; browser keys are not accepted.",
            "tos_acknowledgement_required": False,
        },
        "route_options": {
            "auto": {
                "requested_route": "auto",
                "normalized_route": "arnold",
                "browser_api_key_allowed": False,
                "guidance": "Use local Arnold/Hermes setup for this route. Configure "
                "ARNOLD_API_KEY or HERMES_API_KEY locally; browser-submitted API keys "
                "are not stored.",
                "tos_acknowledgement_required": False,
            },
            "deepseek": {
                "requested_route": "deepseek",
                "normalized_route": "deepseek",
                "browser_api_key_allowed": True,
                "guidance": "DeepSeek browser key submission is supported and stored locally.",
                "tos_acknowledgement_required": False,
            },
            "anthropic": {
                "requested_route": "anthropic",
                "normalized_route": "arnold",
                "browser_api_key_allowed": False,
                "guidance": "Anthropic/Claude runs through local Arnold/Hermes. "
                "Acknowledge the ToS in the UI and configure local ARNOLD_API_KEY or "
                "HERMES_API_KEY; browser keys are not accepted.",
                "tos_acknowledgement_required": True,
            },
            "openai-codex": {
                "requested_route": "openai-codex",
                "normalized_route": "arnold",
                "browser_api_key_allowed": False,
                "guidance": "OpenAI Codex runs through local Arnold/Hermes. Configure "
                "local ARNOLD_API_KEY or HERMES_API_KEY; browser keys are not accepted.",
                "tos_acknowledgement_required": False,
            },
        },
        "credential_presence": {
            "arnold_api_key": True,
            "hermes_api_key": True,
            "deepseek_api_key": True,
        },
        "legacy_deepseek_fallback_enabled": False,
    }

    env_path = tmp_path / ".hermes" / ".env"
    deepseek = _handle_agent_credentials(
        {
            "provider": "deepseek",
            "api_key": "deepseek-secret",
            "credential_payload": {"api_key": "deepseek-secret"},
        },
        env_path=env_path,
    )
    claude = _handle_agent_credentials(
        {"provider": "anthropic", "api_key": "claude-secret", "claude_api_key": "claude-secret"},
        env_path=env_path,
    )
    codex = _handle_agent_credentials(
        {"provider": "openai-codex", "api_key": "codex-secret", "codex_api_key": "codex-secret"},
        env_path=env_path,
    )

    assert deepseek == {
        "ok": True,
        "stored": True,
        "provider": "deepseek",
        "key_name": "DEEPSEEK_API_KEY",
        "path": str(env_path),
    }
    assert "deepseek-secret" not in json.dumps(deepseek)
    assert claude["stored"] is False
    assert codex["stored"] is False
    assert claude["provider"] == "arnold"
    assert claude["requested_route"] == "anthropic"
    assert codex["provider"] == "arnold"
    assert codex["requested_route"] == "openai-codex"
    assert "claude-secret" not in json.dumps(claude)
    assert "codex-secret" not in json.dumps(codex)

    written = env_path.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=deepseek-secret" in written
    assert "claude-secret" not in written
    assert "codex-secret" not in written

    audit_ref = write_audit(
        tmp_path / "credential-audit",
        context=TurnContext(session_id="cred", turn_id="0001"),
        response=deepseek,
        artifacts={
            "request": {
                "provider": "deepseek",
                "deepseek_api_key": "deepseek-secret",
                "credential_payload": {"api_key": "deepseek-secret"},
            }
        },
    )
    audit_payload = json.loads(Path(audit_ref.path).read_text(encoding="utf-8"))
    assert audit_payload["artifacts"]["request"]["deepseek_api_key"] == "<REDACTED>"
    assert audit_payload["artifacts"]["request"]["credential_payload"] == "<REDACTED>"
    assert "deepseek-secret" not in json.dumps(audit_payload)
