from __future__ import annotations

import asyncio
import base64
import importlib
import json
import re
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from vibecomfy.comfy_nodes.agent.edit import (
    AgentEditState,
    _StageBlocked,
    _ABSENT_FIELD_OLD,
    _agent_edit_contract,
    _agent_edit_turn_event_payload,
    _batch_warning_sentence,
    _build_batch_repl_response,
    _conversation_with_candidate_reference,
    _format_available_node_names,
    _human_change_phrase,
    _humanized_edit_message,
    _landed_edit_lead,
    _operation_detail_payload,
    _recovery_report_from_ui_payload,
    _repair_field_changes_from_original_ui,
    _run_batch_repl_product_path,
    _safe_session_id,
    _stamped_message_outcome,
    _stamped_turn_response_outcome,
    _synthesize_post_validation_narrative,
    _synthesize_batch_repl_message,
    _validate_narrative_message,
    _write_turn_chat_artifact,
    _ws_send,
    handle_agent_edit,
    read_session_chat,
    read_session_json,
    split_terminal_clarify,
)
from vibecomfy.porting.edit.types import FieldChange
from vibecomfy.comfy_nodes.agent.contracts import (
    AGENT_EDIT_TURN_CONTRACT_VERSION,
    FailureEnvelope,
    FailureKind,
    PUBLIC_OUTCOME_KINDS,
    StageResult,
    TURN_OUTCOME_KINDS,
    TurnContext,
    TurnOutcome,
    classify_failure,
    failure_envelope,
    public_chat_rehydrate_payload,
)
from vibecomfy.executor.contracts import (
    ReadinessReport,
    ResearchResult,
    RevisionEvidence,
    ScopedDiff,
    TopologyFindings,
)
from vibecomfy.comfy_nodes.agent.provider import ProviderError
from vibecomfy.comfy_nodes.agent.session import (
    payload_hash,
    session_dir_for,
    structural_graph_hash,
    turn_dir_for,
)
from vibecomfy.porting.convert import ConversionWriteError
from vibecomfy.porting.lowering import LoweringDiagnostic, LoweringEvidence, LoweringResult
from vibecomfy.porting.refuse import EditorAheadError, RefusedEmit
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.security.agent_generated_loader import AgentGeneratedLoadError, ScanFailure, ScanReport
from vibecomfy.security.agent_generated_loader import (
    load_agent_generated_scratchpad,
)
from vibecomfy.comfy_nodes.agent.execution_plan import (
    ExecutionPlan,
    PlanCondition,
    PlanEvaluation,
    PlanStep,
    SocketRef,
)
from vibecomfy.security.gate import GateContext, _gate_context_var, set_gate_context
from vibecomfy.security.provenance import confirm, read as read_provenance
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


# ── shared helpers ────────────────────────────────────────────────────────


def test_format_available_node_names_bounds_large_catalog() -> None:
    rows = [types.SimpleNamespace(class_type=f"Node{i:03d}") for i in range(220)]

    formatted = _format_available_node_names(rows, max_names=25)

    assert "Node000" in formatted
    assert "Node024" in formatted
    assert "Node025" not in formatted
    assert "195 more node type names omitted" in formatted
    assert "use search(...)" in formatted


def test_schema_less_preexisting_node_rewire_preserves_queue_safety() -> None:
    original = {
        "nodes": [
            {
                "id": 1,
                "type": "AudioLoader",
                "outputs": [{"name": "AUDIO", "type": "AUDIO", "slot_index": 0, "links": [1]}],
            },
            {
                "id": 2,
                "type": "AudioSeparation",
                "inputs": [{"name": "audio", "type": "AUDIO", "link": 1}],
                "outputs": [{"name": "vocals", "type": "AUDIO", "slot_index": 0, "links": [2]}],
            },
            {
                "id": 3,
                "type": "SaveAudio",
                "inputs": [{"name": "audio", "type": "AUDIO", "link": 2}],
                "outputs": [],
            },
        ],
        "links": [
            [1, 1, 0, 2, 0, "AUDIO"],
            [2, 2, 0, 3, 0, "AUDIO"],
        ],
    }
    candidate = {
        "nodes": [
            {
                "id": 1,
                "type": "AudioLoader",
                "outputs": [{"name": "AUDIO", "type": "AUDIO", "slot_index": 0, "links": [3]}],
            },
            {
                "id": 4,
                "type": "NoiseReduce",
                "inputs": [{"name": "audio", "type": "AUDIO", "link": 3}],
                "outputs": [{"name": "AUDIO", "type": "AUDIO", "slot_index": 0, "links": [4]}],
            },
            {
                "id": 2,
                "type": "AudioSeparation",
                "inputs": [{"name": "audio", "type": "AUDIO", "link": 4}],
                "outputs": [{"name": "vocals", "type": "AUDIO", "slot_index": 0, "links": [2]}],
            },
            {
                "id": 3,
                "type": "SaveAudio",
                "inputs": [{"name": "audio", "type": "AUDIO", "link": 2}],
                "outputs": [],
            },
        ],
        "links": [
            [2, 2, 0, 3, 0, "AUDIO"],
            [3, 1, 0, 4, 0, "AUDIO"],
            [4, 4, 0, 2, 0, "AUDIO"],
        ],
    }

    recovery = _recovery_report_from_ui_payload(
        candidate,
        _batch_repl_provider(),
        original_ui_payload=original,
    )

    entry = next(item for item in recovery if item["node_id"] == "2")
    assert entry["schema_less"] is True
    assert entry["preexisting_ui_node"] is True
    assert entry["ui_connection_shape_unchanged"] is False
    assert entry["schema_less_queue_safe"] is True
    assert entry["schema_less_safety"] == "preexisting_output_destinations_safe"
    assert entry["schema_less_queue_schema"]["inputs"] == [
        {"name": "audio", "type": "AUDIO"}
    ]


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


def _batch_repl_provider() -> _Provider:
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


def _hotshotxl_video_provider() -> _Provider:
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
            "ADE_AnimateDiffLoaderWithContext": NodeSchema(
                class_type="ADE_AnimateDiffLoaderWithContext",
                pack=None,
                inputs={},
                outputs=[OutputSpec("IMAGE", "IMAGE")],
                source_provider="test",
                confidence=1.0,
            ),
            "VHS_VideoCombine": NodeSchema(
                class_type="VHS_VideoCombine",
                pack=None,
                inputs={"images": InputSpec("IMAGE", required=True)},
                outputs=[],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )


def _hotshotxl_active_video_plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="hotshotxl-active-video-path",
        goal=(
            "HotShotXL/AnimateDiff nodes must feed a video terminal on the "
            "active output path, not sit in a sidecar branch."
        ),
        required_steps=(
            PlanStep(
                step_id="add-animatediff-motion-node",
                kind="add_node",
                class_type="ADE_AnimateDiffLoaderWithContext",
            ),
            PlanStep(
                step_id="add-video-terminal",
                kind="add_node",
                class_type="VHS_VideoCombine",
            ),
            PlanStep(
                step_id="wire-motion-into-video-terminal",
                kind="wire_active_path",
                conditions=(
                    PlanCondition(
                        condition_id="hotshotxl.motion_reaches_video_terminal",
                        kind="terminal_consumes",
                        source=SocketRef(class_type="ADE_AnimateDiffLoaderWithContext"),
                        target=SocketRef(class_type="VHS_VideoCombine"),
                        message=(
                            "AnimateDiff output must feed the active VHS video "
                            "terminal, not remain sidecar-only."
                        ),
                    ),
                ),
            ),
        ),
        active_path_conditions=(
            PlanCondition(
                condition_id="hotshotxl.active_output_is_video",
                kind="active_output_domain",
                expected="VIDEO",
                message="The active terminal output must be video.",
            ),
        ),
    )


def _use_dev_full(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS", "1")
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL", "full")


def _use_dev_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS", "1")
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL", "delta")


def test_split_terminal_clarify_detects_terminal_line_and_inline_calls() -> None:
    line_level = split_terminal_clarify(
        'saveimage.filename_prefix = "after"\nclarify("Should I rename it too?")'
    )
    assert line_level.batch == 'saveimage.filename_prefix = "after"'
    assert line_level.message == "Should I rename it too?"

    inline = split_terminal_clarify(
        'saveimage.filename_prefix = "after"; clarify("Use the same stem?")'
    )
    assert inline.batch == 'saveimage.filename_prefix = "after"'
    assert inline.message == "Use the same stem?"

    with_done = split_terminal_clarify(
        'clarify("Install Hotshot first?")\ndone()'
    )
    assert with_done.batch == ""
    assert with_done.message == "Install Hotshot first?"

    edit_with_clarify_done = split_terminal_clarify(
        'saveimage.filename_prefix = "after"\nclarify("Also rename the node?")\ndone()'
    )
    assert edit_with_clarify_done.batch == 'saveimage.filename_prefix = "after"'
    assert edit_with_clarify_done.message == "Also rename the node?"


def test_split_terminal_clarify_rejects_strings_comments_nested_and_non_terminal_calls() -> None:
    cases = [
        'note = "clarify(\\"not a call\\")"',
        '# clarify("not a call")\nsaveimage.filename_prefix = "after"',
        'wrapper(clarify("nested"))',
        'clarify("first")\nsaveimage.filename_prefix = "after"',
        'clarify("first"); clarify("second")',
        'clarify(question="keyword form is not terminal protocol")',
    ]
    for batch in cases:
        result = split_terminal_clarify(batch)
        assert result.batch == batch
        assert result.message is None


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


def _json_clone(value: dict) -> dict:
    return json.loads(json.dumps(value))


def _layout_reorganisation_base_ui() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "pos": [100, 100],
                "size": [180, 80],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sampler"},
                "pos": [420, 100],
                "size": [220, 100],
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "pos": [820, 100],
                "size": [180, 80],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 11}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
        ],
        "groups": [
            {
                "title": "Generation",
                "bounding": [50, 50, 1000, 180],
                "nodes": [1, 2, 3],
            }
        ],
    }


def _layout_reorganisation_branch_ui() -> dict:
    after = _json_clone(_layout_reorganisation_base_ui())
    after["nodes"][1]["outputs"][0]["links"].append(12)
    after["nodes"].append(
        {
            "id": 4,
            "type": "PreviewImage",
            "class_type": "PreviewImage",
            "properties": {"vibecomfy_uid": "preview"},
            "pos": [820, 260],
            "size": [180, 80],
            "inputs": [{"name": "images", "type": "IMAGE", "link": 12}],
        }
    )
    after["links"].append([12, 2, 0, 4, 0, "IMAGE"])
    after["groups"][0]["bounding"] = [50, 50, 1000, 360]
    after["groups"][0]["nodes"].append(4)
    return after


def _with_volatile_canvas_drift(graph: dict) -> dict:
    drifted = _json_clone(graph)
    drifted["groups"] = [{"title": "layout-only", "bounding": [0, 0, 100, 100]}]
    drifted["extra"] = {"ds": {"scale": 1.5, "offset": [44, 55]}}
    for index, node in enumerate(drifted.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        node["pos"] = [999 + index, 888 + index]
        node["size"] = [321, 123]
        node["order"] = 1000 - index
        node["flags"] = {"collapsed": index % 2 == 0}
    return drifted


def _with_first_widget_mutated(graph: dict, value: str) -> dict:
    mutated = _json_clone(graph)
    nodes = mutated.get("nodes")
    if isinstance(nodes, list) and nodes:
        node = nodes[-1] if isinstance(nodes[-1], dict) else nodes[0]
        if isinstance(node, dict):
            node["widgets_values"] = [value]
    return mutated


def _primitive_float_helper_ui_graph() -> dict:
    return {
        "nodes": [
            {
                "id": 285,
                "type": "PrimitiveFloat",
                "title": "FPS",
                "inputs": [
                    {
                        "name": "value",
                        "type": "FLOAT",
                        "link": None,
                        "widget": {"name": "value"},
                    }
                ],
                "outputs": [{"name": "FLOAT", "type": "FLOAT", "links": [530, 533]}],
                "widgets_values": [24],
                "pos": [0, 0],
                "size": [210, 60],
                "properties": {},
            },
            {
                "id": 284,
                "type": "SetNode",
                "title": "Set_fps",
                "inputs": [{"name": "FLOAT", "type": "FLOAT", "link": 530}],
                "outputs": [{"name": "*", "type": "*", "links": None}],
                "widgets_values": ["fps"],
                "pos": [0, 100],
                "size": [210, 34],
                "properties": {},
            },
            {
                "id": 287,
                "type": "SimpleCalculatorKJ",
                "title": "Calc",
                "inputs": [
                    {"name": "variables.a", "type": "INT,FLOAT,BOOLEAN", "link": None},
                    {"name": "variables.b", "type": "INT,FLOAT,BOOLEAN", "link": None},
                    {"name": "a", "type": "*", "link": None},
                    {"name": "b", "type": "*", "link": 533},
                ],
                "outputs": [{"name": "FLOAT", "type": "FLOAT", "links": []}],
                "widgets_values": ["1+ 8*(round(a*b)/8)"],
                "pos": [0, 200],
                "size": [210, 136],
                "properties": {},
            },
        ],
        "links": [
            [530, 285, 0, 284, 0, "FLOAT"],
            [533, 285, 0, 287, 3, "FLOAT"],
        ],
    }


def _allocate_action_candidate(
    root: Path,
    *,
    session_id: str,
    label: str,
) -> tuple[str, str, str]:
    from vibecomfy.comfy_nodes.agent.session import allocate_turn, record_idempotent_response

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


def _assert_product_failure_contract(
    result: dict,
    *,
    failure_kind: str,
    stage: str,
) -> None:
    assert result["contract_version"] == AGENT_EDIT_TURN_CONTRACT_VERSION
    assert isinstance(result["message"], str)
    assert result["message"].strip()
    assert result["outcome"]["kind"] == "error"
    assert result["outcome"]["failure_kind"] == failure_kind
    assert result["outcome"]["stage"] == stage
    assert result["internal_outcome"]["kind"] == "failure"
    assert "candidate" in result
    assert "eligibility" in result
    assert result["eligibility"] == result["apply_eligibility"]
    assert "audit_ref" in result
    assert "debug" in result
    assert result["debug"]["failure"]["kind"] == failure_kind


def test_ws_send_prefers_send_sync_and_targets_sid(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, object], str | None]] = []

    class _PromptServerInstance:
        def send_sync(self, event, payload, sid=None):
            calls.append(("sync", event, payload, sid))

        def send_json(self, event, payload, sid=None):
            calls.append(("json", event, payload, sid))

    server_module = types.ModuleType("server")
    server_module.PromptServer = types.SimpleNamespace(instance=_PromptServerInstance())
    monkeypatch.setitem(sys.modules, "server", server_module)

    payload = {"ok": True}
    _ws_send("vibecomfy.agent_edit.turn", payload, client_id="client-sync")

    assert calls == [("sync", "vibecomfy.agent_edit.turn", payload, "client-sync")]


def test_ws_send_falls_back_to_send_json_and_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, object], str | None]] = []

    class _JsonOnlyPromptServerInstance:
        send_sync = None

        def send_json(self, event, payload, sid=None):
            calls.append(("json", event, payload, sid))

    json_only_module = types.ModuleType("server")
    json_only_module.PromptServer = types.SimpleNamespace(instance=_JsonOnlyPromptServerInstance())
    monkeypatch.setitem(sys.modules, "server", json_only_module)

    payload = {"status": "ok"}
    _ws_send("vibecomfy.agent_edit.turn", payload, client_id="client-json")
    assert calls == [("json", "vibecomfy.agent_edit.turn", payload, "client-json")]

    class _ExplodingPromptServerInstance:
        def send_sync(self, event, payload, sid=None):
            raise RuntimeError("boom")

    exploding_module = types.ModuleType("server")
    exploding_module.PromptServer = types.SimpleNamespace(instance=_ExplodingPromptServerInstance())
    monkeypatch.setitem(sys.modules, "server", exploding_module)
    _ws_send("vibecomfy.agent_edit.turn", {"status": "boom"}, client_id="client-error")


def test_turn_event_name_matches_between_backend_emit_and_frontend_listener() -> None:
    """The live turn feed only works if the backend emit string and the frontend
    addEventListener string are byte-identical. They were silently divergent
    (`vibecomfy.agent_edit.turn` vs `vibecomfy/agent-edit/turn`), which delivered
    zero live events. Pin them together so the two sides can never drift again."""
    repo_root = Path(__file__).resolve().parents[1]
    backend_src = (repo_root / "vibecomfy" / "comfy_nodes" / "agent" / "edit.py").read_text(
        encoding="utf-8"
    )
    frontend_src = (
        repo_root / "vibecomfy" / "comfy_nodes" / "web" / "vibecomfy_roundtrip.js"
    ).read_text(encoding="utf-8")

    backend_match = re.search(r'_ws_send\(\s*"([^"]+)"', backend_src)
    assert backend_match, "could not find the backend _ws_send(...) emit string"
    backend_event = backend_match.group(1)

    frontend_match = re.search(
        r'addEventListener\(\s*"([^"]+)"\s*,\s*agentTurnEventListener', frontend_src
    )
    assert frontend_match, "could not find the frontend turn-event addEventListener"
    frontend_event = frontend_match.group(1)

    assert backend_event == frontend_event == "vibecomfy.agent_edit.turn", (
        f"turn-event name drift: backend emits {backend_event!r}, "
        f"frontend listens for {frontend_event!r}"
    )


def test_agent_edit_turn_event_payload_compacts_and_excludes_sensitive_fields(
    tmp_path: Path,
) -> None:
    state = AgentEditState(
        task="tighten the save behavior",
        graph={},
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
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
    state.batch_exit_mode = "done"
    state.batch_done_summary = "Gate A passed: applied the save prefix rename."
    state.batch_budget_state = {
        "remaining_batches": 2,
        "consecutive_errors": 0,
    }
    context = TurnContext(session_id="batch-compact", turn_id="0007")
    turn_record = {
        "turn_number": 3,
        "batch": 'saveimage.filename_prefix = "after"',
        "message": "Adjusted the save prefix.",
        "provider_metadata": {"token_usage": {"prompt": 123}},
        "batch_ok": True,
        "statement_count": 1,
        "landed_op_count": 1,
        "diagnostics": [
            {
                "code": "unknown_target_field",
                "message": "bad field",
                "detail": {"path": "/tmp/secret.json"},
            }
        ],
        "statements": [
            {
                "statement_index": 0,
                "ok": True,
                "landed": True,
                "op_kind": "set_node_field",
                "teaching_hint": "Use describe(name) to confirm the field name.",
                "dependency_cause": "blocked by earlier failure",
                "diagnostics": [
                    {
                        "code": "unknown_target_field",
                        "message": "bad field",
                        "detail": {"raw_source": "secret"},
                    }
                ],
                "touched_uids": ["save-1"],
                "raw_source": "saveimage.filename_prefix = 'after'",
            }
        ],
        "diff": "--- private diff ---",
        "report": "private report",
    }

    payload = _agent_edit_turn_event_payload(
        state,
        context,
        turn_record,
        status="done",
    )

    assert payload["session_id"] == "batch-compact"
    assert payload["turn_id"] == "0007"
    assert payload["turn_number"] == 3
    assert payload["status"] == "done"
    assert payload["statement_count"] == 1
    assert payload["landed_op_count"] == 1
    assert payload["done_summary"] == state.batch_done_summary
    assert payload["budget"] == {
        "remaining_batches": 2,
        "consecutive_errors": 0,
    }
    assert payload["diagnostics"] == [
        {"code": "unknown_target_field", "message": "bad field"}
    ]
    assert payload["statements"] == [
        {
            "statement_index": 0,
            "ok": True,
            "landed": True,
            "op_kind": "set_node_field",
            "teaching_hint": "Use describe(name) to confirm the field name.",
            "dependency_cause": "blocked by earlier failure",
            "diagnostics": [
                {"code": "unknown_target_field", "message": "bad field"}
            ],
            "touched_uids": ["save-1"],
        }
    ]
    assert "batch" not in payload
    assert "diff" not in payload
    assert "report" not in payload
    assert "provider_metadata" not in payload
    assert "raw_source" not in json.dumps(payload, sort_keys=True)
    assert "/tmp/secret.json" not in json.dumps(payload, sort_keys=True)


def test_agent_edit_route_extracts_only_non_empty_string_client_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")
    real_aiohttp = sys.modules.get("aiohttp")
    real_server = sys.modules.get("server")

    registered: dict[str, Any] = {}

    class _Routes:
        def post(self, path):
            def _decorator(fn):
                registered[path] = fn
                return fn
            return _decorator

        def get(self, path):
            def _decorator(fn):
                registered[path] = fn
                return fn
            return _decorator

    server_module = types.ModuleType("server")
    server_module.PromptServer = types.SimpleNamespace(instance=types.SimpleNamespace(routes=_Routes()))

    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.web = types.SimpleNamespace(
        json_response=lambda body, status=200: {"status": status, "body": body},
        Response=lambda **kwargs: kwargs,
    )

    monkeypatch.setitem(sys.modules, "server", server_module)
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_module)

    captured: list[tuple[dict, str | None]] = []
    to_thread_calls: list[str] = []

    def _fake_handle_agent_executor_submit(payload, *, client_id=None):
        captured.append((payload, client_id))
        return {"ok": True}, 200

    routes = importlib.reload(routes)
    monkeypatch.setattr(
        routes,
        "_handle_agent_executor_submit",
        _fake_handle_agent_executor_submit,
    )
    agent_edit_route = registered.get("/vibecomfy/agent-edit")
    assert agent_edit_route is not None, "agent-edit route was not registered"

    async def _fake_to_thread(fn, /, *args, **kwargs):
        to_thread_calls.append(getattr(fn, "__name__", repr(fn)))
        return fn(*args, **kwargs)

    monkeypatch.setattr(routes.asyncio, "to_thread", _fake_to_thread)

    class _Request:
        def __init__(self, payload):
            self._payload = payload

        async def json(self):
            return self._payload

    try:
        response = asyncio.run(agent_edit_route(_Request({"graph": {}, "task": "x", "client_id": "client-123"})))
        assert response["status"] == 200
        assert captured[-1][1] == "client-123"
        assert to_thread_calls[-1] == "_fake_handle_agent_executor_submit"

        response = asyncio.run(agent_edit_route(_Request({"graph": {}, "task": "x", "client_id": 99})))
        assert response["status"] == 200
        assert captured[-1][1] is None
        assert to_thread_calls[-1] == "_fake_handle_agent_executor_submit"

        response = asyncio.run(agent_edit_route(_Request({"graph": {}, "task": "x", "client_id": "   "})))
        assert response["status"] == 200
        assert captured[-1][1] is None
        assert to_thread_calls[-1] == "_fake_handle_agent_executor_submit"
    finally:
        if real_aiohttp is not None:
            sys.modules["aiohttp"] = real_aiohttp
        else:
            sys.modules.pop("aiohttp", None)
        if real_server is not None:
            sys.modules["server"] = real_server
        else:
            sys.modules.pop("server", None)
        importlib.reload(routes)


def test_agent_edit_state_exposes_explicit_lowering_fields(tmp_path: Path) -> None:
    state = AgentEditState(
        task="lowering smoke",
        graph={},
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
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
    assert state.batch_max_turns == 50


# ── gate context fixture ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _headless_gate_context() -> GateContext:
    ctx = GateContext(non_interactive=True, assume_yes=False, audit=[])
    token = set_gate_context(ctx)
    try:
        yield ctx
    finally:
        _gate_context_var.reset(token)


def test_batch_response_default_off_does_not_add_reorganisation_advisory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VIBECOMFY_REORGANISE_AUTO", raising=False)
    monkeypatch.delenv("VIBECOMFY_NARRATOR_ROUTE", raising=False)
    monkeypatch.delenv("VIBECOMFY_NARRATOR_MODEL", raising=False)
    before = _layout_reorganisation_base_ui()
    after = _layout_reorganisation_branch_ui()
    before_hash = payload_hash(before)
    after_hash = payload_hash(after)
    state = AgentEditState(
        task="add a preview branch",
        graph=before,
        request_payload={"task": "add a preview branch", "graph": before},
        schema_provider=_batch_repl_provider(),
        baseline_graph_hash=before_hash,
        submit_graph_hash=before_hash,
        submit_structural_graph_hash=structural_graph_hash(before),
        submitted_client_graph_hash=before_hash,
        submitted_client_structural_graph_hash=structural_graph_hash(before),
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
        narrative_context_path=tmp_path / "narrative_context.json",
        narrative_request_path=tmp_path / "narrative_request.json",
        narrative_response_path=tmp_path / "narrative_response.json",
        narrative_validation_path=tmp_path / "narrative_validation.json",
    )
    state.route = "dev"
    state.ui_payload = after
    state.batch_exit_mode = "done"
    state.batch_done_summary = "Added the preview branch."
    context = TurnContext(session_id="default-no-reorganise", turn_id="0001")
    for gate_name in list(context.gate_results):
        context.set_gate(gate_name, True)

    response = _build_batch_repl_response(state, context)

    assert response["ok"] is True
    assert response["outcome"]["kind"] == "candidate"
    assert response["candidate"] is not None
    assert response["candidate"]["graph"] == after
    assert payload_hash(response["candidate"]["graph"]) == after_hash
    assert payload_hash(response["graph"]) == after_hash
    assert payload_hash(before) == before_hash
    assert response["candidate_graph_hash"] == after_hash
    assert "layout_reorganisation" not in response["change_details"]
    assert "layout_reorganisation" not in response
    assert "/reorganise_comfy_workflow" not in response["message"]
    assert response["apply_allowed"] is True
    narrative_context = json.loads(
        (tmp_path / "narrative_context.json").read_text(encoding="utf-8")
    )
    assert "layout_reorganisation" not in narrative_context["change_details"]


def test_batch_response_explicit_suggest_adds_reorganisation_advisory_without_second_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_REORGANISE_AUTO", "suggest")
    monkeypatch.delenv("VIBECOMFY_NARRATOR_ROUTE", raising=False)
    monkeypatch.delenv("VIBECOMFY_NARRATOR_MODEL", raising=False)
    before = _layout_reorganisation_base_ui()
    after = _layout_reorganisation_branch_ui()
    before_hash = payload_hash(before)
    after_hash = payload_hash(after)
    state = AgentEditState(
        task="add a preview branch",
        graph=before,
        request_payload={"task": "add a preview branch", "graph": before},
        schema_provider=_batch_repl_provider(),
        baseline_graph_hash=before_hash,
        submit_graph_hash=before_hash,
        submit_structural_graph_hash=structural_graph_hash(before),
        submitted_client_graph_hash=before_hash,
        submitted_client_structural_graph_hash=structural_graph_hash(before),
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
        narrative_context_path=tmp_path / "narrative_context.json",
        narrative_request_path=tmp_path / "narrative_request.json",
        narrative_response_path=tmp_path / "narrative_response.json",
        narrative_validation_path=tmp_path / "narrative_validation.json",
    )
    state.route = "dev"
    state.ui_payload = after
    state.batch_exit_mode = "done"
    state.batch_done_summary = "Added the preview branch."
    context = TurnContext(session_id="suggest-reorganise", turn_id="0001")
    for gate_name in list(context.gate_results):
        context.set_gate(gate_name, True)

    response = _build_batch_repl_response(state, context)

    assert response["ok"] is True
    assert response["outcome"]["kind"] == "candidate"
    assert response["candidate"] is not None
    assert response["candidate"]["graph"] == after
    assert payload_hash(response["candidate"]["graph"]) == after_hash
    assert payload_hash(response["graph"]) == after_hash
    assert payload_hash(before) == before_hash
    assert response["candidate_graph_hash"] == after_hash
    advisory = response["change_details"]["layout_reorganisation"]
    assert advisory["result"] == "offer_reorganisation"
    assert advisory["suggested_command"] == "/reorganise_comfy_workflow"
    assert response["layout_reorganisation"] == advisory
    assert "/reorganise_comfy_workflow" in response["message"]
    assert response["apply_allowed"] is True
    assert "reorganisation_candidate" not in response
    narrative_context = json.loads(
        (tmp_path / "narrative_context.json").read_text(encoding="utf-8")
    )
    assert (
        narrative_context["change_details"]["layout_reorganisation"]["result"]
        == "offer_reorganisation"
    )


def test_batch_response_candidate_mode_replaces_functional_candidate_with_reorganised_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_REORGANISE_AUTO", "candidate")
    monkeypatch.delenv("VIBECOMFY_NARRATOR_ROUTE", raising=False)
    monkeypatch.delenv("VIBECOMFY_NARRATOR_MODEL", raising=False)
    before = _layout_reorganisation_base_ui()
    functional = _layout_reorganisation_branch_ui()
    before_hash = payload_hash(before)
    functional_hash = payload_hash(functional)
    state = AgentEditState(
        task="add a preview branch",
        graph=before,
        request_payload={"task": "add a preview branch", "graph": before},
        schema_provider=_batch_repl_provider(),
        baseline_graph_hash=before_hash,
        submit_graph_hash=before_hash,
        submit_structural_graph_hash=structural_graph_hash(before),
        submitted_client_graph_hash=before_hash,
        submitted_client_structural_graph_hash=structural_graph_hash(before),
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
        narrative_context_path=tmp_path / "narrative_context.json",
        narrative_request_path=tmp_path / "narrative_request.json",
        narrative_response_path=tmp_path / "narrative_response.json",
        narrative_validation_path=tmp_path / "narrative_validation.json",
    )
    state.route = "dev"
    state.ui_payload = functional
    state.batch_exit_mode = "done"
    state.batch_done_summary = "Added the preview branch."
    context = TurnContext(session_id="candidate-reorganise", turn_id="0001")
    for gate_name in list(context.gate_results):
        context.set_gate(gate_name, True)

    response = _build_batch_repl_response(state, context)

    assert response["ok"] is True
    assert response["outcome"]["kind"] == "candidate"
    assert response["apply_eligibility"]["applyable"] is True
    layout = response["change_details"]["layout_reorganisation"]
    assert layout["result"] == "prepare_candidate"
    assert layout["candidate_prepared"] is True
    assert layout["functional_candidate_graph_hash"] == functional_hash
    assert layout["reorganised_candidate_graph_hash"] == response["candidate_graph_hash"]
    assert response["layout_reorganisation"] == layout
    assert response["candidate"]["graph"] == response["graph"]
    assert response["candidate"]["graph"] != functional
    assert response["candidate_graph_hash"] != functional_hash
    assert layout["evidence"]["layout_only_structural_noop"] is True
    persisted_candidate = json.loads(
        (tmp_path / "candidate.ui.json").read_text(encoding="utf-8")
    )
    assert persisted_candidate == response["candidate"]["graph"]
    assert (tmp_path / "post_edit_reorganisation_plan.json").is_file()
    assert any(
        snapshot["stage"] == "post_edit_reorganise"
        for snapshot in response["debug"]["stage_snapshots"]
    )


def test_batch_response_candidate_mode_does_not_preview_when_functional_candidate_is_not_applyable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("optional reorganise preview should not run")

    monkeypatch.setenv("VIBECOMFY_REORGANISE_AUTO", "candidate")
    monkeypatch.delenv("VIBECOMFY_NARRATOR_ROUTE", raising=False)
    monkeypatch.delenv("VIBECOMFY_NARRATOR_MODEL", raising=False)
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.reorganise.preview_reorganise_workflow",
        _fail_if_called,
    )
    before = _layout_reorganisation_base_ui()
    functional = _layout_reorganisation_branch_ui()
    before_hash = payload_hash(before)
    functional_hash = payload_hash(functional)
    state = AgentEditState(
        task="add a preview branch",
        graph=before,
        request_payload={"task": "add a preview branch", "graph": before},
        schema_provider=_batch_repl_provider(),
        baseline_graph_hash=before_hash,
        submit_graph_hash=before_hash,
        submit_structural_graph_hash=structural_graph_hash(before),
        submitted_client_graph_hash=before_hash,
        submitted_client_structural_graph_hash=structural_graph_hash(before),
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
        narrative_context_path=tmp_path / "narrative_context.json",
        narrative_request_path=tmp_path / "narrative_request.json",
        narrative_response_path=tmp_path / "narrative_response.json",
        narrative_validation_path=tmp_path / "narrative_validation.json",
    )
    state.route = "dev"
    state.ui_payload = functional
    state.batch_exit_mode = "done"
    context = TurnContext(session_id="candidate-reorganise-blocked", turn_id="0001")

    response = _build_batch_repl_response(state, context)

    assert response["ok"] is True
    assert response["outcome"]["kind"] == "candidate"
    assert response["apply_eligibility"]["applyable"] is False
    assert response["candidate"]["graph"] == functional
    assert response["candidate_graph_hash"] == functional_hash
    assert "layout_reorganisation" not in response["change_details"]
    assert "layout_reorganisation" not in response


# ── existing T6 regression tests (refactored) ────────────────────────────


def test_agent_edit_contract_defaults_to_batch_repl_and_warns_for_legacy(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    agent_edit_module._WARNED_LEGACY_CONTRACTS.clear()
    agent_edit_module._WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS.clear()
    monkeypatch.delenv("VIBECOMFY_AGENT_EDIT_LEGACY", raising=False)
    monkeypatch.delenv("VIBECOMFY_AGENT_EDIT_V2", raising=False)
    monkeypatch.delenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", raising=False)
    monkeypatch.delenv("VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS", raising=False)
    monkeypatch.delenv("VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL", raising=False)
    assert _agent_edit_contract() == "batch_repl"

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_V2", "1")
    with caplog.at_level("WARNING"):
        assert _agent_edit_contract() == "batch_repl"
    assert "ignoring legacy public protocol env vars (VIBECOMFY_AGENT_EDIT_V2)" in caplog.text

    caplog.clear()
    monkeypatch.delenv("VIBECOMFY_AGENT_EDIT_V2", raising=False)
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    assert _agent_edit_contract() == "batch_repl"

    with caplog.at_level("WARNING"):
        monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_LEGACY", "full")
        assert _agent_edit_contract() == "batch_repl"
    assert "ignoring legacy public protocol env vars (VIBECOMFY_AGENT_EDIT_LEGACY)" in caplog.text

    caplog.clear()
    assert _agent_edit_contract() == "batch_repl"
    assert "ignoring legacy public protocol env vars" not in caplog.text

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS", "1")
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL", "bogus")
    assert _agent_edit_contract() == "batch_repl"

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL", "full")
    with caplog.at_level("WARNING"):
        assert _agent_edit_contract() == "full"
    assert "agent-edit legacy contract 'full' selected" in caplog.text


def test_run_batch_repl_product_path_only_runs_ingest_then_agent_batch_and_returns_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    state = AgentEditState(
        task="change the save prefix",
        graph=_ui_graph(),
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
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
    context = TurnContext(session_id="runner-session", turn_id="runner-turn")
    calls: list[str] = []

    def _fake_run_stage(name, passed_state, passed_context, fn=None, **kwargs):
        calls.append(name)
        assert passed_state is state
        assert passed_context is context
        if name == "ingest":
            assert fn is agent_edit_module._stage_ingest_v2
            assert kwargs == {}
        elif name == "revision_evidence":
            assert fn is agent_edit_module._stage_revision_evidence
            assert kwargs == {
                "route": None,
                "conversation_messages": None,
            }
        elif name == "agent_batch":
            assert fn is agent_edit_module._stage_agent_batch_repl
            assert kwargs == {
                "deepseek_client": "client",
                "route": "router",
                "model": "model-x",
                "client_id": "client-7",
                "conversation_messages": None,
            }
        else:
            pytest.fail(f"unexpected stage {name}")
        return StageResult(stage=name, ok=True, blocking=False)

    monkeypatch.setattr(agent_edit_module, "_run_stage", _fake_run_stage)

    returned = _run_batch_repl_product_path(
        state,
        context,
        deepseek_client="client",  # type: ignore[arg-type]
        route="router",
        model="model-x",
        client_id="client-7",
    )

    assert returned is state
    assert calls == ["ingest", "revision_evidence", "agent_batch"]


def test_run_batch_repl_product_path_routes_adapt_apply_false_domain_mismatch_to_readonly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    graph = _ui_graph()
    graph["nodes"] = [
        {"id": 1, "class_type": "Rodin3D_Regular"},
        {"id": 2, "class_type": "Preview3D"},
        {"id": 3, "class_type": "LoadImage"},
    ]
    state = AgentEditState(
        task="Diagnose why this Rodin graph cannot be swapped to a Wan video template",
        graph=graph,
        request_payload={"apply": False},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
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
        route="adapt",
    )
    state.executor_adaptation_plan = {
        "selected_slice": {
            "source_class_type": "video/wanvideo_wrapper_wan_animate",
            "node_types": [
                "WanVideoModelLoader",
                "WanVideoSampler",
                "WanVideoDecode",
                "WanVideoVAELoader",
                "WanVideoTextEncodeCached",
                "LoadImage",
            ],
        }
    }
    context = TurnContext(session_id="runner-session", turn_id="runner-turn")
    calls: list[tuple[str, Any, dict[str, Any]]] = []

    def _fake_run_stage(name, passed_state, passed_context, fn=None, **kwargs):
        calls.append((name, fn, kwargs))
        assert passed_state is state
        assert passed_context is context
        return StageResult(stage=name, ok=True, blocking=False)

    monkeypatch.setattr(agent_edit_module, "_run_stage", _fake_run_stage)

    returned = _run_batch_repl_product_path(
        state,
        context,
        deepseek_client="client",  # type: ignore[arg-type]
        route="adapt",
        model="model-x",
        client_id="client-7",
    )

    assert returned is state
    assert [name for name, _fn, _kwargs in calls] == ["ingest", "revision_evidence", "agent_batch"]
    assert calls[-1][1] is agent_edit_module._stage_readonly_diagnostic_report
    assert calls[-1][2]["no_candidate_reason"] == "domain_mismatch"
    assert "different workflow domain" in calls[-1][2]["message"]


def test_run_batch_repl_product_path_keeps_adapt_apply_true_on_agent_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    graph = _ui_graph()
    graph["nodes"] = [
        {"id": 1, "class_type": "Rodin3D_Regular"},
        {"id": 2, "class_type": "Preview3D"},
        {"id": 3, "class_type": "LoadImage"},
    ]
    state = AgentEditState(
        task="Replace Rodin Large with Rodin Fusion",
        graph=graph,
        request_payload={"apply": True},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
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
        route="adapt",
    )
    state.executor_adaptation_plan = {
        "selected_slice": {
            "source_class_type": "video/wanvideo_wrapper_wan_animate",
            "node_types": [
                "WanVideoModelLoader",
                "WanVideoSampler",
                "WanVideoDecode",
                "WanVideoVAELoader",
                "WanVideoTextEncodeCached",
                "LoadImage",
            ],
        }
    }
    context = TurnContext(session_id="runner-session", turn_id="runner-turn")
    calls: list[tuple[str, Any]] = []

    def _fake_run_stage(name, passed_state, passed_context, fn=None, **kwargs):
        calls.append((name, fn))
        assert passed_state is state
        assert passed_context is context
        return StageResult(stage=name, ok=True, blocking=False)

    monkeypatch.setattr(agent_edit_module, "_run_stage", _fake_run_stage)

    returned = _run_batch_repl_product_path(
        state,
        context,
        deepseek_client="client",  # type: ignore[arg-type]
        route="adapt",
        model="model-x",
        client_id="client-7",
    )

    assert returned is state
    assert calls[-1][1] is agent_edit_module._stage_agent_batch_repl


def test_handle_agent_edit_preserves_stage_blocked_from_extracted_product_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _blocked_runner(state, context, **_kwargs):
        raise _StageBlocked(
            StageResult(
                stage="agent_batch",
                ok=False,
                blocking=True,
                issues=({"code": "runner_blocked", "message": "runner blocked"},),
            ),
            failure_envelope(
                FailureKind.MODEL_MISTAKE,
                "agent_batch",
                context,
                agent_failure_context={"explanation": "runner blocked"},
            ),
        )

    monkeypatch.setattr(
        agent_edit_module,
        "_run_batch_repl_product_path",
        _blocked_runner,
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "batch-runner-blocked",
        },
        schema_provider=_batch_repl_provider(),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.MODEL_MISTAKE.value,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    _assert_product_failure_contract(
        result,
        failure_kind=FailureKind.MODEL_MISTAKE.value,
        stage="agent_batch",
    )
    assert result["agent_failure_context"]["explanation"] == "runner blocked"


def test_batch_repl_provider_error_writes_messages_artifact(tmp_path: Path) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    state = AgentEditState(
        task="add a code node that processes images with PIL",
        graph=_ui_graph(),
        request_payload={},
        schema_provider=_batch_repl_provider(),
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
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
    context = TurnContext(session_id="provider-error-session", turn_id="0001")

    def _provider_error(_messages):
        raise ProviderError("Agent returned an empty batch_repl response.")

    with pytest.raises(ProviderError):
        agent_edit_module._stage_agent_batch_repl(
            state,
            context,
            deepseek_client=_provider_error,
        )

    assert state.model_request_path.is_file()
    assert state.model_response_path.is_file()
    assert state.messages_path.is_file()

    message_line = json.loads(state.messages_path.read_text(encoding="utf-8").strip())
    assert message_line["error_type"] == "ProviderError"
    assert "empty batch_repl" in message_line["error"]
    assert message_line["request_messages"]

    response = json.loads(state.model_response_path.read_text(encoding="utf-8"))
    assert response["turns"][0]["error"]["type"] == "ProviderError"


def test_batch_repl_exec_insert_done_ignores_lint_false_positive_for_new_uid(
    tmp_path: Path,
) -> None:
    source = (
        "from PIL import ImageOps\n"
        "processed = ImageOps.autocontrast(image)\n"
        "return {\"image\": processed}"
    )
    batch = (
        f"code_node = vibecomfy.exec(source={source!r}, "
        "io={\"inputs\": [[\"image\", \"IMAGE\"]], \"outputs\": [[\"image\", \"IMAGE\"]]}, "
        "in_0=loadimage.image)\n"
        "saveimage.images = code_node.out_0\n"
        "done()"
    )

    def _client(_messages):
        return {
            "message": "Inserted a PIL processing code node.",
            "batch": batch,
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Add a code node that processes images with PIL",
            "session_id": "batch-exec-insert",
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert len(result["batch_turns"]) == 1
    assert "unknown_target" not in result["batch_turns"][0]["report"]
    assert result["debug"]["batch_repl"]["exit_mode"] == "done"
    assert result["debug"]["batch_repl"]["done_summary"]


def test_batch_repl_code_node_addition_preserves_unrelated_unknown_graph_blockers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    graph = _json_clone(_ui_graph())
    graph["nodes"].append(
        {
            "id": 140,
            "type": "VHS_VideoCombine",
            "inputs": [{"name": "images"}],
            "widgets_values": [],
        }
    )
    source = (
        "from PIL import ImageOps\n"
        "processed = ImageOps.autocontrast(image)\n"
        "return {\"image\": processed}"
    )
    batch = (
        f"code_node = vibecomfy.exec(source={source!r}, "
        "io={\"inputs\": [[\"image\", \"IMAGE\"]], \"outputs\": [[\"image\", \"IMAGE\"]]}, "
        "in_0=loadimage.image)\n"
        "saveimage.images = code_node.out_0\n"
        "done()"
    )
    provider_calls = 0

    def _client(_messages):
        nonlocal provider_calls
        provider_calls += 1
        return {
            "message": "Inserted a PIL processing code node.",
            "batch": batch,
        }

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "Add a code node that processes images with PIL",
            "session_id": "batch-exec-insert-messy-graph",
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_client,
        session_root=tmp_path,
    )

    assert provider_calls == 1
    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert result["candidate"] is not None
    assert result["debug"]["batch_repl"]["exit_mode"] == "done"


def test_batch_repl_code_node_addition_accepts_dict_io_format(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: the prompt example allows io={'inputs': {'image': 'IMAGE'},
    'outputs': {'image': 'IMAGE'}}; the emit/validation path must parse it."""
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    graph = _json_clone(_ui_graph())
    source = (
        "from PIL import ImageOps\n"
        "processed = ImageOps.autocontrast(image)\n"
        'return {"image": processed}'
    )
    batch = (
        f"code_node = vibecomfy.exec(source={source!r}, "
        'io={"inputs": {"image": "IMAGE"}, "outputs": {"image": "IMAGE"}}, '
        "in_0=loadimage.image)\n"
        "saveimage.images = code_node.out_0\n"
        "done()"
    )

    def _client(_messages):
        return {"message": "Inserted a PIL processing code node.", "batch": batch}

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "Add a code node that processes images with PIL",
            "session_id": "batch-exec-dict-io",
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert result["candidate"] is not None


def test_localized_code_node_addition_keeps_new_candidate_blockers(tmp_path: Path) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    state = AgentEditState(
        task="Add a code node that processes images with PIL",
        graph={"nodes": [{"id": 1, "type": "MissingPackNode"}], "links": []},
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
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
        revision_evidence=RevisionEvidence(
            topology=TopologyFindings(
                unknown_class_types=("node_id=1: MissingPackNode",),
                missing_required_inputs=(
                    {
                        "node_id": 1,
                        "class_type": "MissingPackNode",
                        "input_name": "images",
                    },
                ),
            ),
            readiness=ReadinessReport(
                missing_models=("old-model.safetensors",),
                missing_node_packs=("OldPack",),
            ),
        ),
    )

    (
        original_topology,
        original_readiness,
        candidate_topology,
        candidate_readiness,
    ) = agent_edit_module._localized_additive_scoped_evidence(
        state,
        candidate_topology=TopologyFindings(
            unknown_class_types=(
                "node_id=1: MissingPackNode",
                "node_id=9: NewlyBadNode",
            ),
            missing_required_inputs=(
                {
                    "node_id": 1,
                    "class_type": "MissingPackNode",
                    "input_name": "images",
                },
                {
                    "node_id": 9,
                    "class_type": "NewlyBadNode",
                    "input_name": "required",
                },
            ),
        ),
        candidate_readiness=ReadinessReport(
            missing_models=("old-model.safetensors", "new-model.safetensors"),
            missing_node_packs=("OldPack", "NewPack"),
        ),
    )

    assert original_topology is not None
    assert original_readiness is not None
    assert candidate_topology is not None
    assert candidate_readiness is not None
    assert candidate_topology.unknown_class_types == ("node_id=9: NewlyBadNode",)
    assert len(candidate_topology.missing_required_inputs) == 1
    assert candidate_topology.missing_required_inputs[0]["node_id"] == 9
    assert candidate_readiness.missing_models == ("new-model.safetensors",)
    assert candidate_readiness.missing_node_packs == ("NewPack",)


def test_batch_repl_code_task_prefetches_vibecomfy_exec_signature(
    tmp_path: Path,
) -> None:
    provider = _Provider(
        {
            **_batch_repl_provider().schemas(),
            "vibecomfy.exec": NodeSchema(
                class_type="vibecomfy.exec",
                pack=None,
                inputs={
                    "source": InputSpec("STRING", required=True),
                    "io": InputSpec("JSON", required=True),
                    "in_0": InputSpec("IMAGE", required=True),
                },
                outputs=[OutputSpec("IMAGE", "out_0")],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )
    captured_messages: list[list[dict[str, str]]] = []

    def _client(messages):
        captured_messages.append(messages)
        return {"batch": "done()", "message": "No changes needed."}

    handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Add a code node that processes images with PIL",
            "session_id": "batch-code-prefetch",
            "max_batches": 1,
        },
        schema_provider=provider,
        deepseek_client=_client,
        session_root=tmp_path,
    )

    system = captured_messages[0][0]["content"]
    user = captured_messages[0][1]["content"]
    catalog = user.split("Signatures for nodes currently in the graph:", 1)[1].split(
        "Other available node type names", 1
    )[0]

    assert "def vibecomfy.exec" in catalog
    assert "source: STRING" in catalog
    assert "in_0:" in catalog
    assert "out_0:" in catalog
    assert "Use the included `vibecomfy.exec` signature" in system
    assert 'search(focus_types=["vibecomfy.exec"])` first' not in system


def test_handle_agent_edit_batch_repl_uses_product_response_builder_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    builder_calls: list[str] = []

    def _fake_runner(state, _context, **_kwargs):
        state.user_message = "product path"
        state.batch_exit_mode = "done"
        return state

    def _batch_builder(state, context):
        builder_calls.append("batch")
        assert state.user_message == "product path"
        assert context.turn_id
        return {
            "ok": True,
            "builder": "batch",
            "message": state.user_message,
            "outcome": {"kind": "candidate"},
            "candidate": {"state": "candidate", "graph_hash": "batch"},
            "eligibility": {"applyable": False, "reason": "no_candidate", "message": "none"},
        }

    monkeypatch.setattr(agent_edit_module, "_run_batch_repl_product_path", _fake_runner)
    monkeypatch.setattr(agent_edit_module, "_build_batch_repl_response", _batch_builder)
    monkeypatch.setattr(
        agent_edit_module,
        "_build_dev_success_response",
        lambda *_args, **_kwargs: pytest.fail("dev success builder should not run for batch_repl"),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "batch-product-builder",
        },
        schema_provider=_batch_repl_provider(),
        session_root=tmp_path,
    )

    assert builder_calls == ["batch"]
    assert result["builder"] == "batch"
    assert result["message"] == "product path"


def test_handle_agent_edit_dev_delta_uses_dev_success_builder_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    _use_dev_delta(monkeypatch)
    builder_calls: list[str] = []

    def _fake_runner(state, _context, **_kwargs):
        state.user_message = "dev success"
        return state

    def _dev_builder(state, context, *, contract):
        builder_calls.append(contract)
        assert state.user_message == "dev success"
        assert context.turn_id
        return {
            "ok": True,
            "builder": contract,
            "message": state.user_message,
            "outcome": {"kind": "candidate"},
            "candidate": {"state": "candidate", "graph_hash": contract},
            "eligibility": {"applyable": True, "reason": "applyable", "message": "ok"},
        }

    monkeypatch.setattr(agent_edit_module, "_run_delta_dev_path", _fake_runner)
    monkeypatch.setattr(agent_edit_module, "_build_dev_success_response", _dev_builder)
    monkeypatch.setattr(
        agent_edit_module,
        "_build_batch_repl_response",
        lambda *_args, **_kwargs: pytest.fail("batch builder should not run for dev delta"),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "dev-delta-builder",
        },
        schema_provider=_batch_repl_provider(),
        session_root=tmp_path,
    )

    assert builder_calls == ["delta"]
    assert result["builder"] == "delta"
    assert result["message"] == "dev success"


def test_handle_agent_edit_dev_delta_uses_dev_failure_builder_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    _use_dev_delta(monkeypatch)

    def _blocked_runner(_state, context, **_kwargs):
        raise _StageBlocked(
            StageResult(
                stage="agent_delta",
                ok=False,
                blocking=True,
                issues=({"code": "dev_runner_blocked", "message": "dev runner blocked"},),
            ),
            failure_envelope(
                FailureKind.MODEL_MISTAKE,
                "agent_delta",
                context,
                agent_failure_context={"explanation": "dev runner blocked"},
            ),
        )

    monkeypatch.setattr(agent_edit_module, "_run_delta_dev_path", _blocked_runner)
    monkeypatch.setattr(
        agent_edit_module,
        "_build_batch_repl_failure_response",
        lambda *_args, **_kwargs: pytest.fail("batch failure builder should not run for dev delta"),
    )
    monkeypatch.setattr(
        agent_edit_module,
        "_build_dev_failure_response",
        lambda *_args, **_kwargs: {
            "ok": False,
            "builder": "dev-failure",
            "message": "dev runner blocked",
            "outcome": {
                "kind": "error",
                "failure_kind": FailureKind.MODEL_MISTAKE.value,
                "stage": "agent_delta",
                "retryable": True,
                "next_action": "retry",
                "graph_unchanged": True,
            },
            "eligibility": {"applyable": False, "reason": "server_blocked", "message": "blocked"},
        },
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "dev-delta-failure-builder",
        },
        schema_provider=_batch_repl_provider(),
        session_root=tmp_path,
    )

    assert result["ok"] is False
    assert result["builder"] == "dev-failure"
    assert result["message"] == "dev runner blocked"
    assert result["outcome"]["kind"] == "error"


def test_handle_agent_edit_round_trips_deepseek_python(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
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


def test_handle_agent_edit_dev_delta_uses_delta_stage_sequence_without_authoring_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    _use_dev_delta(monkeypatch)

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

    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent.audit import write_audit as real_write_audit

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
    assert result["report"]["change"]["delta_ops_envelope"] == result["delta_ops_envelope"]
    assert result["report"]["change"]["ops"] == result["delta_ops"]
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
    model_response = json.loads(Path(result["artifacts"]["model_response"]).read_text(encoding="utf-8"))
    assert request["response_contract"] == "delta"
    assert "Return only JSON with keys `delta` and `message`." in request["messages"][0]["content"]
    assert model_response["delta_ops_envelope"] == result["delta_ops_envelope"]
    assert model_response["delta"] == result["delta_ops"]
    assert set(model_response["delta_ops_envelope"]) == {"schema_version", "ops"}
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
    assert audit["metadata"]["agent_edit_v2"]["delta_ops_envelope"] == result["delta_ops_envelope"]
    assert audit["metadata"]["agent_edit_v2"]["delta_audit"]["automatic_link_removals"] == []
    assert audit["metadata"]["agent_edit_v2"]["delta_audit"]["re_stitches"] == []
    assert audit["metadata"]["agent_edit_v2"]["delta_audit"]["guard_result"]["ok"] is True
    assert "ops" not in audit["metadata"]["agent_edit_v2"]["delta_audit"]
    # normalize availability depends on the environment (e.g. ComfyUI/litegraph
    # may not be importable in dev/test), so only assert the important invariant:
    # the allow-list must never be used for a simple set_node_field edit.
    assert audit["metadata"]["agent_edit_v2"]["delta_audit"]["normalize"]["allow_list_used"] is False
    assert isinstance(audit["metadata"]["agent_edit_v2"]["delta_audit"]["normalize"]["fallback_used"], bool)


def test_agent_edit_render_resolves_primitive_float_helpers_before_emission() -> None:
    from vibecomfy._compile._helpers import RESOLVABLE_HELPER_CLASS_TYPES
    from vibecomfy.porting.edit.session import EditSession

    session = EditSession(_primitive_float_helper_ui_graph())
    source = session.render()
    workflow = session.last_rendered_workflow

    assert workflow is not None
    assert "PrimitiveFloat" not in source
    assert "285" not in workflow.nodes
    assert all(
        node.class_type not in RESOLVABLE_HELPER_CLASS_TYPES
        for node in workflow.nodes.values()
    )
    assert workflow.nodes["287"].inputs["b"] == 24.0


def test_agent_edit_batch_internal_failure_is_not_provider_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("Resolver bug: unresolved helper node 285 survived to emission")

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit._stage_agent_batch_repl",
        _boom,
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "batch-internal-error",
        },
        schema_provider=provider,
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.VALIDATION_ERROR.value,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    assert "temporarily unavailable" not in result["message"]
    assert result["agent_failure_context"]["explanation"] == (
        "Resolver bug: unresolved helper node 285 survived to emission"
    )


def test_agent_edit_batch_empty_model_response_is_malformed_not_provider_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    from vibecomfy.comfy_nodes.agent import provider as provider_mod

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.run_agent_turn_batch",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            provider_mod.MalformedModelJSON(
                "Agent batch_repl response was empty. Expected exactly one ```batch fenced block."
            )
        ),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "batch-empty-model-response",
        },
        schema_provider=provider,
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.MALFORMED_MODEL_JSON.value,
        stage="agent_response",
        audit_ref_expected=True,
    )
    assert "temporarily unavailable" not in result["message"]
    assert "batch_repl response was empty" in result["agent_failure_context"]["explanation"]


def test_agent_edit_batch_empty_model_response_retries_once_then_commits(
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

    from vibecomfy.comfy_nodes.agent import provider as provider_mod

    calls: list[dict[str, object]] = []
    responses = iter(
        [
            {"content": ""},
            {
                "content": (
                    "Applied.\n\n```batch\n"
                    "saveimage.filename_prefix = \"after\"\n"
                    "done()\n"
                    "```"
                )
            },
        ]
    )

    class RetryRuntime:
        @staticmethod
        def run_agent_turn_batch(**kwargs):
            calls.append(kwargs)
            return next(responses)

    monkeypatch.setattr(provider_mod, "_load_arnold_runtime", lambda: RetryRuntime)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "batch-empty-retry-success",
            "max_batches": 2,
        },
        schema_provider=provider,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert "after" in json.dumps(result["graph"], sort_keys=True)
    assert len(calls) == 2
    assert calls[1]["messages"][-1]["role"] == "system"  # type: ignore[index]
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    response_turns = json.loads(
        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
    )["turns"]
    assert response_turns[0]["error"]["retrying"] is True
    assert response_turns[0]["error"]["parse_reason"] == "empty"
    provider_metadata = response_turns[1]["batch_result"]["provider_metadata"]
    assert provider_metadata["batch_repl_protocol_retry"]["count"] == 1
    assert provider_metadata["batch_repl_protocol_retry"]["parse_reason"] == "empty"
    assert "batch_repl response was empty" in provider_metadata["batch_repl_protocol_retry"]["reason"]


def test_handle_agent_edit_dev_delta_classifies_malformed_delta_as_closed_failure_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    _use_dev_delta(monkeypatch)

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
    assert result["contract_version"] == AGENT_EDIT_TURN_CONTRACT_VERSION
    assert result["outcome"]["kind"] == "error"
    assert result["internal_outcome"]["kind"] == "failure"
    assert "Unsupported edit op 'bogus'." == result["agent_failure_context"]["explanation"]


def test_handle_agent_edit_dev_delta_classifies_provider_error_as_closed_failure_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    _use_dev_delta(monkeypatch)

    from vibecomfy.comfy_nodes.agent import provider as provider_mod

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.run_agent_turn_delta",
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


# ── Dev-only parity coverage ──────────────────────────────────────────


def test_flag_off_dev_full_stage_order_and_prompt_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the dev-only full protocol is enabled
    (VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS=1,
    VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL=full), the pipeline stage order,
    provider prompt shape, and response artifacts remain identical to the
    pre-batch-REPL codebase full-protocol path."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    _use_dev_full(monkeypatch)

    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent.audit import write_audit as real_write_audit

    stage_order: list[str] = []

    def _capture_audit(audit_dir, **kwargs):
        stage_order[:] = list((kwargs.get("stage_results") or {}).keys())
        return real_write_audit(audit_dir, **kwargs)

    monkeypatch.setattr(agent_edit_module, "write_audit", _capture_audit)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "flag-off-dev-full",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    # ── stage order ──────────────────────────────────────────────────
    assert result["ok"] is True
    # Dev-only full path records StageResults for ingest, convert, agent,
    # load_python, lower, validate, emit, queue_validate, and summarize.  The audit
    # stage is recorded as a StageResult only in the delta path (for agent_edit_v2
    # metadata injection); the full path calls _stage_audit directly without a
    # preceding _record, so "audit" does not appear in the captured stage_results.
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
    # Authoring / delta stages must NOT appear in the dev-only full path.
    assert {"project", "agent_delta", "apply_delta"}.isdisjoint(stage_order)

    # ── provider prompt shape ─────────────────────────────────────────
    request = json.loads(Path(result["artifacts"]["model_request"]).read_text(encoding="utf-8"))
    # Full-protocol prompt is simple JSON with keys `python` + `message` — never delta.
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
    # Delta-only artifact must NOT leak into the full path.
    assert "projection" not in result["artifacts"]
    # delta_ops must NOT leak into the full-protocol response.
    assert "delta_ops" not in result

    # ── audit shape ───────────────────────────────────────────────────
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert "before_python" in audit["artifacts"]
    assert "after_python" in audit["artifacts"]
    assert "projection" not in audit["artifacts"]
    assert "agent_edit_v2" not in audit.get("metadata", {})
    assert "response_contract" not in json.dumps(audit)


def test_flag_off_dev_delta_stage_order_and_prompt_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the dev-only delta protocol is enabled
    (VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS=1,
    VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL=delta), the pipeline stage order,
    provider prompt shape, ``response_contract=\"delta\"`` marker, and
    response artifacts remain identical to the pre-batch-REPL delta path."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )
    _use_dev_delta(monkeypatch)

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

    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent.audit import write_audit as real_write_audit

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
    # Authoring / full-protocol stages must NOT appear in the dev-only delta path.
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
    # Full-protocol artifacts must NOT leak into the delta path.
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

    from vibecomfy.porting.edit import session as edit_session_module

    real_edit_session = edit_session_module.EditSession

    class _TrackingSession(real_edit_session):
        def __init__(self, *args, **kwargs):
            session_stats["init"] += 1
            super().__init__(*args, **kwargs)

        def search(self, *, formatted=False, **kwargs):
            session_stats["search_calls"].append({"formatted": formatted, **kwargs})
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
    assert session_stats["search_calls"] == [
        {"formatted": True, "focus_types": ["LoadImage", "SaveImage"]},
        {"formatted": False},
    ]
    assert len(captured_messages) == 2

    turn0_system = captured_messages[0][0]["content"]
    turn0_user = captured_messages[0][1]["content"]
    assert "```batch" in turn0_system
    assert "Current scratchpad Python (full render):" in turn0_user
    assert "Signatures for nodes currently in the graph:" in turn0_user
    assert "Other available node type names" in turn0_user
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
    assert (
        response_turns[0]["batch_result"]["delta_ops"]
        == response_turns[0]["batch_result"]["delta_ops_envelope"]["ops"]
    )
    assert set(response_turns[0]["batch_result"]["delta_ops_envelope"]) == {"schema_version", "ops"}
    assert response_turns[1]["batch_result"]["batch_ok"] is False


def test_default_runtime_schema_provider_falls_back_to_authoring_object_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    monkeypatch.setattr(agent_edit_module, "_build_object_info_in_process", lambda: None)
    agent_edit_module._RUNTIME_OBJECT_INFO_PATH.clear()

    provider = agent_edit_module._default_runtime_schema_provider()

    assert len(provider.schemas()) > 100
    assert provider.get_schema("KSampler") is not None
    assert provider.get_schema("VAEDecode") is not None
    assert provider.get_schema("SaveImage") is not None


def test_agent_edit_batch_failed_edits_cannot_be_reported_as_successful_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {
                "batch": "decoded = MissingDecodeNode(images=loadimage.image)\ndone()",
                "message": "I will add the decode node.",
            },
            {
                "batch": "search(focus_types=[\"MissingDecodeNode\"])",
                "message": "I will inspect the missing type.",
            },
            {
                "batch": "done()",
                "message": "Nothing else to do.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Add a decode and save chain",
            "session_id": "failed-edits-not-noop",
            "max_batches": 3,
            "max_consecutive_errors": 3,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.MODEL_MISTAKE.value,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    assert result["outcome"]["kind"] != "noop"
    assert "already matches" not in result["message"]
    response_path = tmp_path / "failed-edits-not-noop" / "turns" / "0001" / "response.json"
    assert response_path.is_file()
    response = json.loads(response_path.read_text(encoding="utf-8"))
    assert response["ok"] is False
    assert response["kind"] == FailureKind.MODEL_MISTAKE.value
    assert response["outcome"]["failure_kind"] == FailureKind.MODEL_MISTAKE.value


def test_handle_agent_edit_batch_repl_turn0_catalog_is_scoped_and_search_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={"images": InputSpec("IMAGE", required=True)},
                outputs=[],
                source_provider="test",
                confidence=1.0,
            ),
            "ImageScaleBy": NodeSchema(
                class_type="ImageScaleBy",
                pack=None,
                inputs={
                    "image": InputSpec("IMAGE", required=True),
                    "scale_by": InputSpec("FLOAT", required=False, default=1.0),
                },
                outputs=[OutputSpec("IMAGE", "IMAGE")],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    captured_messages: list[list[dict[str, str]]] = []

    def _fake_batch_client(messages):
        captured_messages.append(messages)
        return {"batch": "done()", "message": "No changes needed."}

    handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "inspect the graph",
            "session_id": "batch-scoped-catalog",
            "max_batches": 1,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    system = captured_messages[0][0]["content"]
    user = captured_messages[0][1]["content"]
    catalog = user.split("Signatures for nodes currently in the graph:", 1)[1].split(
        "Other available node type names", 1
    )[0]
    names = user.split("Other available node type names", 1)[1]

    assert "def LoadImage" in catalog
    assert "def SaveImage" in catalog
    assert "def ImageScaleBy" not in catalog
    assert "ImageScaleBy" in names
    assert "do NOT search for them" in system
    assert "Search first" in system
    assert "current authoring-schema lookup" in system
    assert "Reference EXISTING nodes by EXACT names" in system
    assert "Bare ambiguous refs are rejected." in system
    assert "for a NEW node TYPE you want to ADD" in system
    assert "schema lookup" in system
    assert 'research("query words", sources=["workflows", "registry", "messages", "web"])' in system
    assert "if sources are omitted it searches internal workflows/templates only" in system
    assert "factual current authoring-schema lookup" in system
    assert 'sources=["web"]' in system
    assert "workflow context is mandatory" in system
    assert "smallest named artifact" in system
    assert "research workflow precedents and community knowledge" in system
    assert "use `workflows` first" in system
    assert "Use `registry` only when the user explicitly asks" in system
    assert "tentative retrieval hints, not findings, implementation instructions, or validation tasks" in system
    assert "Do not research installation, provider packs, registry, or local addability" in system
    assert "reinterpret such a hint as a request to find workflow precedents" in system
    assert "URL/title is a lead, not yet workflow context" in system
    assert "Only after workflow/example context identifies a pack" in system
    assert 'sources=["workflows"]' in system
    assert 'sources=["registry"]' in system
    assert "do not search generic constraints by themselves" in system
    assert "Do not invent likely class names" in system
    assert "Do not call `search(focus_types=[...])` for guessed names" in system


def test_batch_repl_search_query_output_is_in_next_turn_report() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    provider = _Provider(
        {
            "ImageScaleBy": NodeSchema(
                class_type="ImageScaleBy",
                pack=None,
                inputs={"image": InputSpec("IMAGE", required=True)},
                outputs=[OutputSpec("IMAGE", "IMAGE")],
                source_provider="test",
                confidence=1.0,
            )
        }
    )
    session = EditSession(_ui_graph(), schema_provider=provider)

    result = session.apply_batch('search(focus_types=["ImageScaleBy"])')
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    assert result.ok is True
    assert result.statements[0].op_kind == "query"
    assert "def ImageScaleBy" in result.statements[0].detail["query_output"]
    assert "def ImageScaleBy" in report


def test_batch_repl_search_exact_hit_includes_related_class_hints() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "IMAGE")]),
            "Rodin3D_Gen2": NodeSchema(
                class_type="Rodin3D_Gen2",
                pack=None,
                inputs={"image": InputSpec("IMAGE", required=True)},
                outputs=[OutputSpec("MESH", "MESH")],
                source_provider="test",
                confidence=1.0,
            ),
            "Rodin3D_Regular": NodeSchema(
                class_type="Rodin3D_Regular",
                pack=None,
                inputs={"image": InputSpec("IMAGE", required=True)},
                outputs=[OutputSpec("MESH", "MESH")],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )
    session = EditSession(_ui_graph(), schema_provider=provider)

    result = session.apply_batch('search(focus_types=["Rodin3D_Regular"])')
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    query_output = result.statements[0].detail["query_output"]
    assert "def Rodin3D_Regular" in query_output
    assert "Related available class names" in query_output
    assert "- Rodin3D_Regular: Rodin3D_Gen2" in query_output
    assert "def Rodin3D_Gen2" not in query_output
    assert "Rodin3D_Gen2" in report


def test_batch_repl_search_exact_miss_explains_local_schema_lookup() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    provider = _Provider(
        {
            "SaveAnimatedWEBP": NodeSchema(
                class_type="SaveAnimatedWEBP",
                pack=None,
                inputs={"images": InputSpec("IMAGE", required=True)},
                outputs=[],
                source_provider="test",
                confidence=1.0,
            )
        }
    )
    session = EditSession(_ui_graph(), schema_provider=provider)

    result = session.apply_batch('search(focus_types=["HotshotXL"])')
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    assert result.ok is True
    assert result.statements[0].op_kind == "query"
    query_output = result.statements[0].detail["query_output"]
    assert "No node signature found for exact class type(s): 'HotshotXL'." in query_output
    assert "not an internet or precedent search" in query_output
    assert "Missing class name(s): HotshotXL" in query_output
    assert "Do not broaden this into guessed branded constructors" in query_output
    assert "Use workflow precedent as pattern evidence" in query_output
    assert "No available local class names contain the requested terms." in report


def test_batch_repl_search_graph_present_miss_reports_adjacent_authorable_nodes() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    provider = _Provider(
        {
            "LoadMask": NodeSchema(
                class_type="LoadMask",
                pack=None,
                inputs={"image": InputSpec("STRING")},
                outputs=[OutputSpec("MASK", "MASK")],
                source_provider="test",
                confidence=1.0,
            ),
            "GrowMaskWithBlur": NodeSchema(
                class_type="GrowMaskWithBlur",
                pack=None,
                inputs={
                    "mask": InputSpec("MASK", required=True),
                    "expand": InputSpec("INT", default=4),
                    "blur": InputSpec("INT", default=2),
                },
                outputs=[OutputSpec("MASK", "MASK")],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )
    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadMask",
                "inputs": [{"name": "image", "type": "STRING", "link": None}],
                "outputs": [{"name": "MASK", "type": "MASK", "links": [10]}],
            },
            {
                "id": 2,
                "type": "MissingMaskBridge",
                "inputs": [{"name": "mask", "type": "MASK", "link": 10}],
                "outputs": [{"name": "MASK", "type": "MASK", "links": [11]}],
            },
            {
                "id": 3,
                "type": "GrowMaskWithBlur",
                "inputs": [{"name": "mask", "type": "MASK", "link": 11}],
                "outputs": [{"name": "MASK", "type": "MASK", "links": []}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "MASK"],
            [11, 2, 0, 3, 0, "MASK"],
        ],
    }
    session = EditSession(graph, schema_provider=provider)

    result = session.apply_batch('search(focus_types=["MissingMaskBridge"])')
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    query_output = result.statements[0].detail["query_output"]
    assert "No node signature found for exact class type(s): 'MissingMaskBridge'." in query_output
    assert "Graph context: the missing class is already present in the current graph" in query_output
    assert "Adjacent schema-backed candidates near MissingMaskBridge:" in query_output
    assert "upstream via MASK: LoadMask#1 (LoadMask)" in query_output
    assert "def LoadMask" in query_output
    assert "downstream via mask: GrowMaskWithBlur#3 (GrowMaskWithBlur)" in query_output
    assert "def GrowMaskWithBlur" in query_output
    assert "GrowMaskWithBlur" in report


def test_batch_repl_search_partial_exact_miss_reports_missing_classes() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    provider = _Provider(
        {
            "KSamplerAdvanced": NodeSchema(
                class_type="KSamplerAdvanced",
                pack=None,
                inputs={"model": InputSpec("MODEL", required=True)},
                outputs=[OutputSpec("LATENT", "LATENT")],
                source_provider="test",
                confidence=1.0,
            )
        }
    )
    session = EditSession(_ui_graph(), schema_provider=provider)

    result = session.apply_batch(
        'search(focus_types=["ADE_AnimateDiffLoaderWithContext", '
        '"ADE_AnimateDiffUniformContextOptions", "KSamplerAdvanced"])'
    )
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    query_output = result.statements[0].detail["query_output"]
    assert "def KSamplerAdvanced" in query_output
    assert (
        "No node signature found for exact class type(s): "
        "'ADE_AnimateDiffLoaderWithContext', 'ADE_AnimateDiffUniformContextOptions'."
    ) in query_output
    assert "Use workflow precedent as pattern evidence" in query_output
    assert "ADE_AnimateDiffLoaderWithContext" in report


def test_batch_repl_research_query_output_is_in_next_turn_report(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    calls: list[dict[str, object]] = []

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        calls.append({"query": query, **kwargs})
        return ResearchResult(
            summary="Found Hotshot XL custom-node installation and workflow precedent.",
            sources=(
                {
                    "title": "ComfyUI-HotshotXL",
                    "url": "https://example.test/hotshot",
                    "description": "HotshotXL provides video generation custom nodes for ComfyUI.",
                },
            ),
            warnings=("local corpus unavailable",),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch('research("Hotshot XL ComfyUI 16 frames")')
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    assert result.ok is True
    assert result.statements[0].op_kind == "query"
    assert calls[0]["query"] == "Hotshot XL ComfyUI 16 frames"
    assert calls[0]["local_limit"] == 5
    assert calls[0]["registry_resolver"] is None
    assert calls[0]["hivemind_client"] is None
    assert calls[0]["web_search_client"] is None
    assert result.statements[0].detail["research_sources"] == ("workflows",)
    assert result.statements[0].detail["requested_research_sources"] == ("workflows",)
    assert "Found Hotshot XL custom-node installation" in result.statements[0].detail["query_output"]
    assert "Workflow-first check" in result.statements[0].detail["query_output"]
    assert "ComfyUI-HotshotXL" in report
    assert "local corpus unavailable" in report


def test_batch_repl_research_can_choose_web_only_source(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.porting.edit.session import EditSession

    calls: list[dict[str, object]] = []

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        calls.append({"query": query, **kwargs})
        return ResearchResult(summary="Web-only result.", sources=())

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch('research("HotshotXL ComfyUI", sources=["web"])')

    assert result.ok is True
    assert calls[0]["query"] == "HotshotXL ComfyUI"
    assert calls[0]["local_limit"] == 0
    assert calls[0]["hivemind_client"] is None
    assert calls[0]["web_search_client"] is not None
    assert result.statements[0].detail["research_sources"] == ("web",)


def test_batch_repl_web_url_only_research_prompts_concrete_workflow_followup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.porting.edit.session import EditSession

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        return ResearchResult(
            summary="Found URL leads.",
            sources=(
                {
                    "source": "web",
                    "title": "Hotshot XL OpenArt workflow",
                    "url": "https://openart.ai/workflows/example/hotshot-xl/abc",
                    "description": "External search result from openart.ai",
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch('research("Hotshot XL ComfyUI workflow", sources=["web"])')

    query_output = result.statements[0].detail["query_output"]
    assert "External workflow check" in query_output
    assert "URL/title leads, not yet a workflow pattern" in query_output
    assert "workflow JSON, repo example, or page result" in query_output


def test_batch_repl_web_workflow_json_prompts_exact_schema_followup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.porting.edit.session import EditSession

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        return ResearchResult(
            summary="Found GitHub workflow JSON.",
            sources=(
                {
                    "source": "external_workflow",
                    "source_type": "github_workflow_json",
                    "title": "workflow-vid2vid-hotshotXL.json",
                    "url": "https://github.com/example/repo/blob/main/workflow-vid2vid-hotshotXL.json",
                    "description": "Fetched GitHub workflow JSON.",
                    "node_types": [
                        "ADE_AnimateDiffUniformContextOptions",
                        "VHS_LoadImagesPath",
                        "KSamplerAdvanced",
                    ],
                    "source_workflow_path": "/tmp/workflow-vid2vid-hotshotXL.json",
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch('research("Hotshot XL ComfyUI workflow", sources=["web"])')

    query_output = result.statements[0].detail["query_output"]
    assert "Concrete workflow pattern found" in query_output
    assert "ADE_AnimateDiffUniformContextOptions" in query_output
    assert "VHS_LoadImagesPath" in query_output
    assert "/tmp/workflow-vid2vid-hotshotXL.json" in query_output
    assert "python() only shows the current graph" in query_output
    assert "broad custom-node queries such as only the model name" in query_output


def test_batch_repl_research_memory_keeps_workflow_evidence_across_turns() -> None:
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _batch_research_memory_summary

    state = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 1,
                "statements": [
                    {
                        "source": 'research("Hotshot XL ComfyUI workflow", sources=["web"])',
                        "detail": {
                            "query": "research",
                            "research_query": "Hotshot XL ComfyUI workflow",
                            "requested_research_sources": ("web",),
                            "query_output": (
                                "Sources:\n"
                                "- workflow.json (github_workflow_json; source_workflow_path=/tmp/hotshot.json)\n"
                                "Concrete workflow pattern found: node types found: "
                                "ADE_AnimateDiffUniformContextOptions, VHS_LoadImagesPath."
                            ),
                        },
                    }
                ],
            },
            {
                "turn_number": 2,
                "statements": [
                    {
                        "source": 'search(focus_types=["ADE_AnimateDiffUniformContextOptions"])',
                        "detail": {
                            "query": "search",
                            "query_output": (
                                "No node signature found for exact class type(s): "
                                "'ADE_AnimateDiffUniformContextOptions'. "
                                "Use workflow precedent as pattern evidence."
                            ),
                        },
                    }
                ],
            },
        ]
    )

    memory = _batch_research_memory_summary(state)

    assert "github_workflow_json" in memory
    assert "ADE_AnimateDiffUniformContextOptions" in memory
    assert "VHS_LoadImagesPath" in memory
    assert "No node signature found" in memory
    assert "Use workflow precedent as pattern evidence" in memory


# ── T16: cross-turn memory compactness, no full-packet reserialization,
#        forbidden-key absence ──────────────────────────────────────────

_FORBIDDEN_MEMORY_KEYS: frozenset[str] = frozenset({
    "winner", "best", "selected", "score", "rank", "primary",
    "preferred", "chosen", "pick", "choice", "top", "recommended",
})


def _assert_no_forbidden_keys_in_text(text: str, label: str) -> None:
    """Fail if any forbidden public-key name appears as a label in *text*."""
    lowered = text.lower()
    for key in _FORBIDDEN_MEMORY_KEYS:
        assert f" {key}:" not in lowered, f"{label}: forbidden key '{key}:' in output"
        assert f'"{key}"' not in lowered, f'{label}: forbidden key "{key}" in output'


def test_batch_repl_memory_packet_aware_compact_summary() -> None:
    """Turn >0 with precedent_packet: compact one-line-per-option summary,
    not full packet reserialization and not verbatim query_output dump."""
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _batch_research_memory_summary

    packet: dict[str, Any] = {
        "context_note": "Evidence/context only — NOT a winner, recommendation, or required implementation.",
        "options": [
            {
                "source_class_type": "LTXVideoToVideo",
                "description": "LTX 0.9.5 video-to-video workflow with IPAdapter face",
                "source_workflow_path": "/tmp/ltx_v2v.json",
                "node_ids": ["1", "2", "3", "4", "5"],
                "node_types": ["LTXVideoToVideo", "IPAdapterFace", "LoadImage", "SaveVideo"],
                "notes": ["source: github_workflow_json", "Caveat: requires LTX 0.9.5+", "Uses experimental IPAdapterFace"],
            },
            {
                "source_class_type": "HotshotXLPipeline",
                "description": "Hotshot XL vid2vid pipeline with ControlNet depth",
                "source_workflow_path": "/tmp/hotshot.json",
                "node_ids": ["10", "11"],
                "node_types": ["HotshotXLPipeline", "ControlNetDepth"],
                "notes": ["source: hivemind_workflow", "Caveat: 24GB+ VRAM"],
            },
        ],
        "warnings": ["Some nodes may require custom packs"],
    }

    state = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 1,
                "statements": [
                    {
                        "source": 'research("video to video workflow", sources=["web"])',
                        "detail": {
                            "query": "research",
                            "research_query": "video to video workflow",
                            "requested_research_sources": ("web",),
                            "precedent_packet": packet,
                            "query_output": "FULL VERBATIM OUTPUT THAT SHOULD NOT APPEAR IN MEMORY " * 50,
                        },
                    }
                ],
            },
            {
                "turn_number": 2,
                "statements": [],
            },
        ]
    )

    memory = _batch_research_memory_summary(state)

    # ── compact packet-aware output present ────────────────────────
    assert "LTXVideoToVideo" in memory
    assert "HotshotXLPipeline" in memory
    assert "github_workflow_json" in memory   # source tier extracted from notes
    assert "hivemind_workflow" in memory     # source tier extracted from notes
    assert "IPAdapter face" in memory         # one-line pattern summary
    assert "ControlNet depth" in memory       # one-line pattern summary
    assert "caveat(s)" in memory.lower()      # caveat count present
    assert "precedent option(s)" in memory    # packet-aware header

    # ── full packet NOT reserialized ───────────────────────────────
    assert "context_note" not in memory           # packet-level field not leaked
    assert "FULL VERBATIM" not in memory          # query_output not dumped verbatim
    assert '"node_ids"' not in memory             # full option fields omitted
    assert '"node_types"' not in memory
    assert "/tmp/ltx_v2v.json" not in memory      # raw source_workflow_path not leaked
    assert "Evidence/context only" not in memory  # context_note text not leaked


def test_batch_repl_memory_no_full_packet_reserialization() -> None:
    """Memory output must never contain full packet fields
    (context_note, node_ids, node_types, raw source_workflow_path, verbatim query_output)."""
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _batch_research_memory_summary

    packet: dict[str, Any] = {
        "context_note": "Should not appear in memory.",
        "options": [
            {
                "source_class_type": "BigNode",
                "description": "A long description that should be first-line truncated. "
                + ("extra detail " * 50),
                "source_workflow_path": "/very/long/path/to/workflow.json",
                "node_ids": [str(i) for i in range(100)],
                "node_types": ["TypeA", "TypeB", "TypeC"],
                "notes": ["source: web", "note1", "note2"],
            },
        ],
        "warnings": ["warning1", "warning2", "warning3"],
    }

    state = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 1,
                "statements": [
                    {
                        "source": 'research("test", sources=["web"])',
                        "detail": {
                            "query": "research",
                            "precedent_packet": packet,
                            "query_output": "IRRELEVANT VERBATIM " * 100,
                        },
                    }
                ],
            },
        ]
    )

    memory = _batch_research_memory_summary(state)

    # ── full packet fields absent ──────────────────────────────────
    assert "context_note" not in memory
    assert '"node_ids"' not in memory
    assert '"node_types"' not in memory
    assert "/very/long/path/to/workflow.json" not in memory
    assert "IRRELEVANT VERBATIM" not in memory

    # ── compact summary present ────────────────────────────────────
    assert "BigNode" in memory
    assert "precedent option(s)" in memory
    assert "caveat(s)" in memory.lower()


def test_batch_repl_memory_forbidden_keys_absent_packet_path() -> None:
    """No score/winner/best/selected/chosen keys leak into memory
    via the packet-aware summary path."""
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _batch_research_memory_summary

    packet: dict[str, Any] = {
        "options": [
            {
                "source_class_type": "CleanNode",
                "description": "A clean node without forbidden keys.",
                "notes": ["source: curated"],
            },
            {
                "source_class_type": "AnotherNode",
                "description": "Another clean node.",
                "notes": ["source: hivemind"],
            },
        ],
        "warnings": [],
    }

    state = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 1,
                "statements": [
                    {
                        "source": 'research("test", sources=["curated"])',
                        "detail": {
                            "query": "research",
                            "precedent_packet": packet,
                            "query_output": "some output",
                        },
                    }
                ],
            },
        ]
    )

    memory = _batch_research_memory_summary(state)
    _assert_no_forbidden_keys_in_text(memory, "packet-aware memory")


def test_batch_repl_memory_forbidden_keys_absent_legacy_path() -> None:
    """No score/winner/best/selected/chosen keys leak into memory
    via the legacy marker-matched query_output path."""
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _batch_research_memory_summary

    state = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 1,
                "statements": [
                    {
                        "source": 'research("test", sources=["web"])',
                        "detail": {
                            "query": "research",
                            "research_query": "test",
                            "query_output": (
                                "Concrete workflow pattern found: SomeNode, AnotherNode.\n"
                                "source_workflow_path=/tmp/test.json\n"
                                "github_workflow_json evidence collected."
                            ),
                        },
                    }
                ],
            },
        ]
    )

    memory = _batch_research_memory_summary(state)
    _assert_no_forbidden_keys_in_text(memory, "legacy memory")


def test_summarize_precedent_packet_compact_fields_only() -> None:
    """_summarize_precedent_packet carries only source title, source tier,
    one-line pattern summary, and caveat count — no full packet fields leak."""
    from vibecomfy.comfy_nodes.agent.edit import _summarize_precedent_packet

    packet: dict[str, Any] = {
        "context_note": "Should not appear.",
        "options": [
            {
                "source_class_type": "MyNode",
                "description": "First line of description.\nSecond line that should NOT appear.",
                "source_workflow_path": "/tmp/path.json",
                "node_ids": ["1", "2", "3"],
                "node_types": ["MyNode", "HelperNode"],
                "notes": ["source: github", "caveat: needs GPU", "caveat: large model"],
            },
        ],
        "warnings": ["global warning 1"],
    }

    result = _summarize_precedent_packet(packet, turn_number=2)

    assert result is not None
    # ── compact fields present ─────────────────────────────────────
    assert "MyNode" in result                # source title
    assert "github" in result                # source tier from notes
    assert "First line of description" in result  # one-line pattern summary
    assert "caveat(s)" in result             # caveat count

    # ── full packet fields NOT leaked ──────────────────────────────
    assert "context_note" not in result
    assert "/tmp/path.json" not in result
    assert '"node_ids"' not in result
    assert '"node_types"' not in result
    assert "HelperNode" not in result
    assert "Second line" not in result
    assert "global warning 1" not in result


def test_summarize_precedent_packet_description_truncation() -> None:
    """One-line pattern summary truncated at 120 chars with ellipsis."""
    from vibecomfy.comfy_nodes.agent.edit import _summarize_precedent_packet

    long_desc = "A" * 200
    packet: dict[str, Any] = {
        "options": [
            {
                "source_class_type": "TruncNode",
                "description": long_desc,
                "notes": [],
            },
        ],
        "warnings": [],
    }

    result = _summarize_precedent_packet(packet, turn_number=3)

    assert result is not None
    # Truncated form present, full 200-char string absent
    assert "A" * 117 + "..." in result
    assert long_desc not in result


def test_summarize_precedent_packet_forbidden_keys_in_output() -> None:
    """_summarize_precedent_packet must never emit forbidden keys
    (winner, best, selected, score, rank, primary, preferred, chosen,
    pick, choice, top, recommended) in its output string."""
    from vibecomfy.comfy_nodes.agent.edit import _summarize_precedent_packet

    packet: dict[str, Any] = {
        "options": [
            {
                "source_class_type": "Node1",
                "description": "A normal description.",
                "notes": ["source: curated", "note A"],
            },
            {
                "source_class_type": "Node2",
                "description": "Another normal description.",
                "notes": [],
            },
        ],
        "warnings": [],
    }

    result = _summarize_precedent_packet(packet, turn_number=1)
    assert result is not None
    _assert_no_forbidden_keys_in_text(result, "_summarize_precedent_packet")


def test_batch_repl_memory_packet_absent_falls_back_to_marker_path() -> None:
    """When precedent_packet is absent, the legacy marker-matched
    query_output path is used (not the packet-aware header)."""
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _batch_research_memory_summary

    state = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 1,
                "statements": [
                    {
                        "source": 'research("test", sources=["web"])',
                        "detail": {
                            "query": "research",
                            "research_query": "test",
                            "requested_research_sources": ("web",),
                            "query_output": (
                                "Concrete workflow pattern found: NodeX.\n"
                                "github_workflow_json evidence.\n"
                                "No node signature found for exact class type(s): 'NodeY'.\n"
                                "Use workflow precedent as pattern evidence."
                            ),
                        },
                    }
                ],
            },
        ]
    )

    memory = _batch_research_memory_summary(state)

    # Legacy marker-matched path active
    assert "NodeX" in memory
    assert "NodeY" in memory
    assert "github_workflow_json" in memory
    assert "Use workflow precedent as pattern evidence" in memory

    # Packet-aware header absent
    assert "precedent option(s)" not in memory


def test_batch_repl_memory_mixed_packet_and_marker_turns() -> None:
    """Memory handles mixed turns: some with precedent_packet,
    some with legacy marker-matched query_output."""
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _batch_research_memory_summary

    packet: dict[str, Any] = {
        "options": [
            {
                "source_class_type": "PacketNode",
                "description": "From packet-aware turn.",
                "notes": ["source: curated"],
            },
        ],
        "warnings": [],
    }

    state = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 1,
                "statements": [
                    {
                        "source": 'research("packet turn", sources=["curated"])',
                        "detail": {
                            "query": "research",
                            "precedent_packet": packet,
                            "query_output": "SHOULD NOT APPEAR",
                        },
                    }
                ],
            },
            {
                "turn_number": 2,
                "statements": [
                    {
                        "source": 'search(focus_types=["NodeX"])',
                        "detail": {
                            "query": "search",
                            "query_output": "No node signature found for exact class type(s): 'NodeX'.",
                        },
                    }
                ],
            },
        ]
    )

    memory = _batch_research_memory_summary(state)

    # Packet-aware turn
    assert "PacketNode" in memory
    assert "precedent option(s)" in memory
    assert "SHOULD NOT APPEAR" not in memory

    # Legacy marker-matched turn
    assert "NodeX" in memory
    assert "No node signature found" in memory


def test_batch_repl_memory_max_items_limit() -> None:
    """max_items parameter limits the number of records in the summary."""
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _batch_research_memory_summary

    turns = []
    for i in range(5):
        turns.append({
            "turn_number": i + 1,
            "statements": [
                {
                    "source": f'research("turn {i+1}", sources=["web"])',
                    "detail": {
                        "query": "research",
                        "research_query": f"turn {i+1}",
                        "query_output": (
                            f"Concrete workflow pattern found: Node{i}.\n"
                            "github_workflow_json."
                        ),
                    },
                }
            ],
        })

    state = SimpleNamespace(batch_turns=turns)

    memory_full = _batch_research_memory_summary(state, max_items=10)
    memory_limited = _batch_research_memory_summary(state, max_items=2)

    # Full memory has all 5 turns
    for i in range(5):
        assert f"Node{i}" in memory_full

    # Limited memory only has last 2
    assert "Node3" in memory_limited
    assert "Node4" in memory_limited
    assert "Node0" not in memory_limited
    assert "Node1" not in memory_limited
    assert "Node2" not in memory_limited


def test_batch_repl_memory_turn_number_in_output() -> None:
    """Memory output includes turn numbers for traceability
    (both packet-aware and legacy paths)."""
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _batch_research_memory_summary

    # Legacy path
    state_legacy = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 3,
                "statements": [
                    {
                        "source": 'research("test", sources=["web"])',
                        "detail": {
                            "query": "research",
                            "research_query": "test",
                            "query_output": "Concrete workflow pattern found: NodeA.",
                        },
                    }
                ],
            },
        ]
    )

    memory_legacy = _batch_research_memory_summary(state_legacy)
    assert "turn 3" in memory_legacy
    assert "NodeA" in memory_legacy

    # Packet-aware path
    packet: dict[str, Any] = {
        "options": [
            {
                "source_class_type": "PacketNode",
                "description": "From packet turn 5.",
                "notes": ["source: curated"],
            },
        ],
        "warnings": [],
    }

    state_packet = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 5,
                "statements": [
                    {
                        "source": 'research("pkt", sources=["curated"])',
                        "detail": {
                            "query": "research",
                            "precedent_packet": packet,
                            "query_output": "VERBATIM NOT USED",
                        },
                    }
                ],
            },
        ]
    )

    memory_packet = _batch_research_memory_summary(state_packet)
    assert "turn 5" in memory_packet
    assert "PacketNode" in memory_packet


def test_missing_custom_node_clarify_does_not_force_registry_after_schema_miss() -> None:
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _premature_missing_custom_node_clarify_feedback

    state = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 1,
                "statements": [
                    {
                        "detail": {
                            "query": "research",
                            "requested_research_sources": ("web",),
                            "query_output": (
                                "workflow.json (github_workflow_json)\n"
                                "Concrete workflow pattern found: "
                                "ADE_AnimateDiffUniformContextOptions"
                            ),
                        }
                    }
                ],
            },
            {
                "turn_number": 2,
                "statements": [
                    {
                        "detail": {
                            "query": "search",
                            "query_output": (
                                "No node signature found for exact class type(s): "
                                "'ADE_LoadAnimateDiffModel', "
                                "'ADE_AnimateDiffUniformContextOptions'."
                            ),
                        }
                    }
                ],
            },
        ]
    )

    feedback = _premature_missing_custom_node_clarify_feedback(
        state,
        "The required custom nodes are not installed.",
    )

    assert feedback == ""

    state.batch_turns.append(
        {
            "turn_number": 3,
            "statements": [
                {
                    "detail": {
                        "query": "research",
                        "requested_research_sources": ("registry",),
                        "query_output": "Found ComfyUI-AnimateDiff-Evolved.",
                    }
                }
            ],
        }
    )

    assert _premature_missing_custom_node_clarify_feedback(
        state,
        "The required custom nodes are not installed.",
    ) == ""


def test_workflow_schema_clarify_does_not_force_uninstalled_provisional_nodes() -> None:
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _premature_workflow_schema_clarify_feedback

    state = SimpleNamespace(
        batch_turns=[
            {
                "turn_number": 1,
                "landed_op_count": 0,
                "statements": [
                    {
                        "detail": {
                            "query": "research",
                            "requested_research_sources": ("web",),
                            "query_output": (
                                "workflow vid2vid hotshotXL ipadapterplusface ipadapter.json "
                                "(github_workflow_json)\n"
                                "workflow_schema ADE_AnimateDiffLoaderWithContext: "
                                "inputs=context_options, model; widgets=widget_0, widget_1; outputs=MODEL\n"
                                "workflow_schema ADE_AnimateDiffUniformContextOptions: "
                                "widgets=widget_0, widget_1, widget_2, widget_3, widget_4; outputs=CONTEXT_OPTIONS"
                            ),
                        }
                    }
                ],
            },
            {
                "turn_number": 2,
                "landed_op_count": 0,
                "statements": [
                    {
                        "detail": {
                            "query": "search",
                            "query_output": (
                                "def ADE_AnimateDiffLoaderWithContext(widget_0: STRING = ..., "
                                "widget_1: STRING = ..., model: MODEL, "
                                "context_options: CONTEXT_OPTIONS) -> MODEL:\n"
                                "def ADE_AnimateDiffUniformContextOptions(widget_0: INT = ..., "
                                "widget_1: INT = ...) -> CONTEXT_OPTIONS:"
                            ),
                        }
                    }
                ],
            },
        ]
    )

    feedback = _premature_workflow_schema_clarify_feedback(
        state,
        "The current graph lacks the required AnimateDiff nodes, so I cannot build this.",
    )

    assert feedback == ""


def test_workflow_schema_clarify_rejects_asking_for_present_workflow_signatures() -> None:
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.edit import _premature_workflow_schema_clarify_feedback

    state = SimpleNamespace(
        execution_protocol_notes={
            "selected_precedent": {
                "name": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
                "minimal_spine": [
                    "ADE_AnimateDiffLoaderWithContext",
                    "ADE_AnimateDiffUniformContextOptions",
                    "VHS_VideoCombine",
                ],
            },
            "research_sources": [
                {
                    "source": "hivemind_workflow",
                    "pack": "workflow",
                    "workflow_schema": {
                        "ADE_AnimateDiffLoaderWithContext": {
                            "input": {
                                "required": {
                                    "model": {"type": "MODEL"},
                                    "context_options": {"type": "CONTEXT_OPTIONS"},
                                },
                                "optional": {},
                            },
                            "outputs": [{"name": "MODEL", "type": "MODEL"}],
                        },
                        "ADE_AnimateDiffUniformContextOptions": {
                            "input": {"required": {}, "optional": {}},
                            "outputs": [
                                {"name": "CONTEXT_OPTIONS", "type": "CONTEXT_OPTIONS"}
                            ],
                        },
                    },
                }
            ],
        },
        executor_research_sources=(),
    )

    feedback = _premature_workflow_schema_clarify_feedback(
        state,
        (
            "I need to look up the exact schemas for "
            "ADE_AnimateDiffLoaderWithContext and "
            "ADE_AnimateDiffUniformContextOptions to wire this."
        ),
    )

    assert "Premature workflow-schema clarification rejected" in feedback
    assert "ADE_AnimateDiffLoaderWithContext" in feedback
    assert "execution_protocol_notes.research_sources[].workflow_schema" in feedback


def test_selected_precedent_unknown_constructor_stops_as_authoring_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    calls = 0

    def client(_messages):
        nonlocal calls
        calls += 1
        return {
            "batch": (
                "positive = HotshotXLCLIPTextEncode()\n"
                "negative = HotshotXLPAGTextEncode()\n"
                "done()"
            ),
            "message": "I'll use HotShotXL-specific constructors.",
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "route": "adapt",
            "execution_protocol_notes": {
                "workflow_precedent_status": "compatible_workflow_found",
                "selected_precedent": {
                    "name": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
                    "minimal_spine": [
                        "KSamplerAdvanced",
                        "VHS_VideoCombine",
                        "ADE_AnimateDiffLoaderWithContext",
                        "ADE_AnimateDiffUniformContextOptions",
                    ],
                    "terminal_output_path": ["SaveImage", "VHS_VideoCombine"],
                },
                "research_sources": [
                    {
                        "source": "hivemind_workflow",
                        "pack": "workflow",
                        "workflow_schema": {
                            "ADE_AnimateDiffLoaderWithContext": {
                                "input": {
                                    "required": {
                                        "model": {"type": "MODEL"},
                                        "context_options": {"type": "CONTEXT_OPTIONS"},
                                    },
                                    "optional": {},
                                },
                                "outputs": [{"name": "MODEL", "type": "MODEL"}],
                            },
                            "ADE_AnimateDiffUniformContextOptions": {
                                "input": {"required": {}, "optional": {}},
                                "outputs": [
                                    {"name": "CONTEXT_OPTIONS", "type": "CONTEXT_OPTIONS"}
                                ],
                            },
                        },
                    }
                ],
            },
            "session_id": "hotshot-invented-constructor-blocker",
            "max_batches": 4,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=client,
        session_root=tmp_path,
    )

    assert calls == 1
    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert result["graph_unchanged"] is True
    assert "cannot author the required workflow classes" in result["message"]
    assert "I found a HotShotXL workflow precedent" not in result["message"]
    assert "AnimateDiff Video Generation with ControlNet and IP-Adapter" in result["message"]
    assert "HotshotXLCLIPTextEncode" in result["message"]
    messages_path = (
        tmp_path
        / "hotshot-invented-constructor-blocker"
        / "turns"
        / "0001"
        / "messages.jsonl"
    )
    turns = [
        json.loads(line)
        for line in messages_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert turns[0]["authoring_blocker"] == "selected_precedent_unknown_class"


def test_selected_precedent_workflow_schema_class_is_authorable_provisionally(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "route": "adapt",
            "execution_protocol_notes": {
                "workflow_precedent_status": "compatible_workflow_found",
                "selected_precedent": {
                    "name": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
                    "minimal_spine": [
                        "ADE_AnimateDiffLoaderWithContext",
                        "ADE_AnimateDiffUniformContextOptions",
                        "VHS_VideoCombine",
                    ],
                },
                "research_sources": [
                    {
                        "source": "hivemind_workflow",
                        "pack": "workflow",
                        "workflow_schema": {
                            "ADE_AnimateDiffLoaderWithContext": {
                                "input": {
                                    "required": {
                                        "model": {"type": "MODEL"},
                                        "context_options": {"type": "CONTEXT_OPTIONS"},
                                    },
                                    "optional": {},
                                },
                                "outputs": [{"name": "MODEL", "type": "MODEL"}],
                            },
                            "ADE_AnimateDiffUniformContextOptions": {
                                "input": {"required": {}, "optional": {}},
                                "outputs": [
                                    {"name": "CONTEXT_OPTIONS", "type": "CONTEXT_OPTIONS"}
                                ],
                            },
                        },
                    }
                ],
            },
            "session_id": "hotshot-workflow-schema-provisional-node",
            "max_batches": 2,
            "max_consecutive_errors": 1,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: {
            "batch": "motion = ADE_AnimateDiffLoaderWithContext(near=saveimage)\ndone()",
            "message": "Added the exact AnimateDiff node from the HotShotXL workflow precedent.",
        },
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert any(
        node.get("type") == "ADE_AnimateDiffLoaderWithContext"
        for node in result["graph"].get("nodes", [])
        if isinstance(node, dict)
    )
    model_request = json.loads(
        (
            tmp_path
            / "hotshot-workflow-schema-provisional-node"
            / "turns"
            / "0001"
            / "model_request.json"
        ).read_text(encoding="utf-8")
    )
    request_text = json.dumps(model_request)
    assert "def ADE_AnimateDiffLoaderWithContext" in request_text
    assert "provisional_schema" in request_text


def test_rejected_terminal_clarify_is_durable_budget_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    events: list[tuple[str, dict[str, object], str | None]] = []
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit._ws_send",
        lambda event, payload, *, client_id=None: events.append((event, payload, client_id)),
    )
    responses = iter(
        [
            {
                "batch": 'search(focus_types=["SaveImage"])',
                "message": "I checked the workflow-derived constructor schema.",
            },
            {
                "batch": 'clarify("The current graph lacks the required node, so I cannot build this.")',
                "message": "I cannot continue without the missing node.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Generate 8 frames with Hotshot",
            "session_id": "rejected-terminal-clarify",
            "max_batches": 5,
            "max_consecutive_errors": 1,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
        client_id="client-rejected-clarify",
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.SCHEMA_GAP.value,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    issue = result["agent_failure_context"]["issues"][0]
    assert issue["code"] == "batch_budget_exhausted"
    assert issue["detail"]["turn_count"] == 2
    assert issue["detail"]["budget_state"]["remaining_batches"] == 3
    assert issue["detail"]["budget_state"]["consecutive_errors"] == 1
    assert [payload["status"] for _, payload, _ in events] == [
        "in_progress",
        "budget_exhausted",
    ]

    response_path = tmp_path / "rejected-terminal-clarify" / "turns" / "0001" / "response.json"
    assert response_path.is_file()
    response = json.loads(response_path.read_text(encoding="utf-8"))
    assert response["ok"] is False
    model_response = json.loads(
        (tmp_path / "rejected-terminal-clarify" / "turns" / "0001" / "model_response.json").read_text(
            encoding="utf-8"
        )
    )
    rejected = model_response["turns"][1]["rejected_clarification"]
    assert rejected["diagnostics"][0]["code"] == "premature_missing_custom_node_clarify"
    assert "Premature clarification rejected" in rejected["report"]


def test_rejected_terminal_clarify_after_partial_edit_fails_fast(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {
                "batch": "del saveimage\nreplacement = MissingHotshotNode(images=loadimage.image)",
                "message": "I will replace the output node.",
            },
            {
                "batch": 'search(focus_types=["SaveImage"])',
                "message": "I checked the constructor schema.",
            },
            {
                "batch": 'clarify("The current graph lacks the required node, so I cannot safely build this.")',
                "message": "I cannot continue without the missing node.",
            },
            {
                "batch": "done()",
                "message": "This response must not be requested.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Replace the output node with Hotshot",
            "session_id": "rejected-clarify-partial-edit",
            "max_batches": 5,
            "max_consecutive_errors": 3,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.SCHEMA_GAP.value,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    issue = result["agent_failure_context"]["issues"][0]
    assert issue["code"] == "batch_budget_exhausted"
    assert issue["detail"]["turn_count"] == 3
    assert issue["detail"]["budget_state"]["remaining_batches"] == 2

    turn_dir = tmp_path / "rejected-clarify-partial-edit" / "turns" / "0001"
    assert (turn_dir / "response.json").is_file()
    model_request = json.loads((turn_dir / "model_request.json").read_text(encoding="utf-8"))
    model_response = json.loads((turn_dir / "model_response.json").read_text(encoding="utf-8"))
    assert len(model_request["turns"]) == 3
    assert len(model_response["turns"]) == 3
    assert model_response["turns"][0]["batch_result"]["landed_op_count"] == 0
    assert "rejected_clarification" in model_response["turns"][2]


def test_batch_repl_research_honors_workflows_plus_web_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.porting.edit.session import EditSession

    calls: list[dict[str, object]] = []

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        calls.append({"query": query, **kwargs})
        return ResearchResult(summary="External workflow result.", sources=())

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch(
        'research("Hotshot XL ComfyUI workflow", sources=["workflows", "web"])'
    )

    assert result.ok is True
    assert calls[0]["query"] == "Hotshot XL ComfyUI workflow"
    assert calls[0]["local_limit"] == 5
    assert calls[0]["registry_resolver"] is None
    assert calls[0]["web_search_client"] is not None
    assert result.statements[0].detail["research_sources"] == ("workflows", "web")
    assert "Workflow-first check" in result.statements[0].detail["query_output"]


def test_batch_repl_research_honors_web_plus_registry_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.porting.edit.session import EditSession

    calls: list[dict[str, object]] = []

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        calls.append({"query": query, **kwargs})
        return ResearchResult(summary="External workflow result.", sources=())

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch(
        'research("Hotshot XL ComfyUI workflow nodes", sources=["web", "registry", "messages"])'
    )

    assert result.ok is True
    assert calls[0]["local_limit"] == 0
    assert callable(calls[0]["registry_resolver"])
    assert calls[0]["hivemind_client"] is not None
    assert calls[0]["web_search_client"] is not None
    assert result.statements[0].detail["research_sources"] == ("web", "registry", "messages")
    assert "Research-order check" not in result.statements[0].detail["query_output"]


def test_batch_repl_research_can_choose_registry_source(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.executor.research import ResearchResult
    from vibecomfy.porting.edit.session import EditSession

    calls: list[dict[str, object]] = []

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        calls.append({"query": query, **kwargs})
        return ResearchResult(
            summary="Found registry candidate.",
            sources=(
                {
                    "source": "comfy-registry",
                    "class_type": "ComfyUI-AnimateDiff-Evolved",
                    "pack": "ComfyUI-AnimateDiff-Evolved",
                    "description": "Expected classes: ADE_AnimateDiffLoaderWithContext",
                    "resolver_candidate": {
                        "pack": {"slug": "ComfyUI-AnimateDiff-Evolved"},
                        "expected_classes": ["ADE_AnimateDiffLoaderWithContext"],
                    },
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    monkeypatch.setattr(research_module, "resolve_missing_nodes", object())
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch('research("Hotshot XL ComfyUI nodes", sources=["registry"])')

    assert result.ok is True
    assert calls[0]["query"] == "Hotshot XL ComfyUI nodes"
    assert calls[0]["local_limit"] == 0
    assert callable(calls[0]["registry_resolver"])
    assert calls[0]["hivemind_client"] is None
    assert calls[0]["web_search_client"] is None
    assert result.statements[0].detail["research_sources"] == ("registry",)
    assert result.statements[0].detail["resolver_candidates"]
    assert "ComfyUI-AnimateDiff-Evolved" in result.statements[0].detail["query_output"]
    assert "Registry check" in result.statements[0].detail["query_output"]


def test_handle_agent_edit_batch_repl_adds_workflow_json_provisional_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor.research import ResearchResult

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        return ResearchResult(
            summary=f"Concrete workflow evidence for {query}.",
            sources=(
                {
                    "source": "external_workflow",
                    "source_type": "github_workflow_json",
                    "class_type": "workflow vid2vid hotshotXL ipadapterplusface ipadapter.json",
                    "pack": "github.com",
                    "url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
                    "source_workflow_path": "/tmp/hotshot-workflow.json",
                    "node_types": ["ADE_AnimateDiffUniformContextOptions"],
                    "workflow_schema_classes": ["ADE_AnimateDiffUniformContextOptions"],
                    "workflow_schema": {
                        "ADE_AnimateDiffUniformContextOptions": {
                            "input": {
                                "required": {},
                                "optional": {
                                    "widget_0": {"type": "INT", "default": 8},
                                    "widget_1": {"type": "INT", "default": 1},
                                    "widget_2": {"type": "INT", "default": 3},
                                    "widget_3": {"type": "STRING", "default": "uniform"},
                                    "widget_4": {"type": "BOOLEAN", "default": False},
                                },
                            },
                            "outputs": [{"name": "CONTEXT_OPTIONS", "type": "CONTEXT_OPTIONS"}],
                            "object_info_widget_order": [
                                "widget_0",
                                "widget_1",
                                "widget_2",
                                "widget_3",
                                "widget_4",
                            ],
                        }
                    },
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    responses = iter(
        [
            {
                "batch": 'research("Hotshot XL ComfyUI workflow", sources=["web"])',
                "message": "Found a concrete Hotshot workflow JSON.",
            },
            {
                "batch": (
                    "context = ADE_AnimateDiffUniformContextOptions("
                    "widget_0=16, widget_1=1, widget_2=3, widget_3='uniform', widget_4=False, "
                    "near=saveimage)\ndone()"
                ),
                "message": "Added the workflow-derived unresolved ADE context node.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch to generating 16 frames with Hotshot",
            "session_id": "hotshot-workflow-json-provisional-node",
            "max_batches": 4,
            "max_consecutive_errors": 2,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert result["canvas_apply_allowed"] is True
    assert any(
        node.get("type") == "ADE_AnimateDiffUniformContextOptions"
        for node in result["graph"].get("nodes", [])
        if isinstance(node, dict)
    )


def test_workflow_json_research_does_not_hydrate_local_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor.research import ResearchResult
    from vibecomfy.porting.edit.session import EditSession

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        return ResearchResult(
            summary=f"Concrete workflow evidence for {query}.",
            sources=(
                {
                    "source": "external_workflow",
                    "source_type": "github_workflow_json",
                    "class_type": "workflow vid2vid hotshotXL ipadapterplusface ipadapter.json",
                    "pack": "github.com",
                    "url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
                    "workflow_schema_classes": ["ADE_AnimateDiffUniformContextOptions"],
                    "workflow_schema": {
                        "ADE_AnimateDiffUniformContextOptions": {
                            "input": {
                                "required": {},
                                "optional": {"widget_0": {"type": "INT", "default": 8}},
                            },
                            "outputs": [{"name": "CONTEXT_OPTIONS", "type": "CONTEXT_OPTIONS"}],
                            "object_info_widget_order": ["widget_0"],
                        }
                    },
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_batch_repl_provider())

    session.apply_batch('research("Hotshot XL ComfyUI workflow", sources=["web"])')
    result = session.apply_batch(
        'search(focus_types=["ADE_AnimateDiffUniformContextOptions"])'
    )
    query_output = result.statements[0].detail["query_output"]

    assert "No node signature found for exact class type(s)" in query_output
    assert "def ADE_AnimateDiffUniformContextOptions" not in query_output


def test_registry_class_only_research_does_not_hydrate_local_search(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor.research import ResearchResult

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        return ResearchResult(
            summary=f"Registry evidence for {query}.",
            sources=(
                {
                    "source": "github",
                    "class_type": "ComfyUIWorkflowSuite",
                    "pack": "ComfyUIWorkflowSuite",
                    "description": "Expected classes: Limbicnation, ComfyUIWorkflowSuite, HotshotXL, User",
                    "resolver_candidate": {
                        "pack": {
                            "slug": "ComfyUIWorkflowSuite",
                            "source": "github",
                            "url": "https://github.com/Limbicnation/ComfyUIWorkflowSuite",
                        },
                        "expected_classes": [
                            "Limbicnation",
                            "ComfyUIWorkflowSuite",
                            "Txt2Vid",
                            "HotshotXL",
                            "User",
                        ],
                        "validation_mode": "class_validatable",
                        "provisional_schema": {},
                        "runnable": False,
                        "stable_install_hash": "workflow-suite-class-only",
                    },
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    responses = iter(
        [
            {
                "batch": 'research("HotShotXL Hotshot video generation 8 frames", sources=["registry"])',
                "message": "Found class-only registry evidence.",
            },
            {
                "batch": 'search(focus_types=["HotshotXL"])\ndone()',
                "message": "Checking whether the registry class is authorable.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch to generating 8 frames with Hotshot",
            "session_id": "hotshot-class-only-registry",
            "max_batches": 2,
            "max_consecutive_errors": 2,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    search_turn = result["batch_turns"][1]
    query_output = search_turn["statements"][0]["detail"]["query_output"]

    assert result["graph_unchanged"] is True
    assert "No node signature found for exact class type(s): 'HotshotXL'." in query_output
    assert "def HotshotXL" not in query_output


def test_handle_agent_edit_batch_repl_adds_registry_provisional_missing_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor.research import ResearchResult

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        return ResearchResult(
            summary=f"Registry evidence for {query}.",
            sources=(
                {
                    "source": "comfy-registry",
                    "class_type": "ADE_AnimateDiffLoaderWithContext",
                    "pack": "ComfyUI-AnimateDiff-Evolved",
                    "description": "Expected classes: ADE_AnimateDiffLoaderWithContext",
                    "resolver_candidate": {
                        "pack": {
                            "slug": "ComfyUI-AnimateDiff-Evolved",
                            "source": "comfy-registry",
                            "url": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved",
                        },
                        "expected_classes": ["ADE_AnimateDiffLoaderWithContext"],
                        "validation_mode": "class_validatable",
                        "provisional_schema": {
                            "version": "1.0.0",
                            "runnable": False,
                            "schema": {
                                "nodes": {
                                    "ADE_AnimateDiffLoaderWithContext": {
                                        "input": {"required": {}, "optional": {}},
                                        "output": ["MODEL"],
                                        "output_name": ["MODEL"],
                                    }
                                }
                            },
                        },
                        "runnable": False,
                        "stable_install_hash": "ade-registry-evidence",
                    },
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    monkeypatch.setattr(research_module, "resolve_missing_nodes", object())
    responses = iter(
        [
            {
                "batch": 'research("Hotshot XL ComfyUI nodes", sources=["registry"])',
                "message": "Found the registry-backed Hotshot node pack.",
            },
            {
                "batch": "hotshot = ADE_AnimateDiffLoaderWithContext(near=saveimage)\ndone()",
                "message": "Added the unresolved Hotshot custom node as a candidate.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch to generating 16 frames with Hotshot",
            "session_id": "hotshot-provisional-node",
            "max_batches": 4,
            "max_consecutive_errors": 2,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert any(
        node.get("type") == "ADE_AnimateDiffLoaderWithContext"
        for node in result["graph"].get("nodes", [])
        if isinstance(node, dict)
    )


def test_research_required_unresolved_capability_clarify_does_not_force_registry_before_stopping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        raise AssertionError(f"unexpected forced research call: {query!r} {kwargs!r}")

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    responses = iter(
        [
            {
                "batch": (
                    'clarify("HotShotXL needs an authorable AnimateDiff path '
                    '(ADE_LoadAnimateDiffModel, ADE_ApplyAnimateDiffModel) plus '
                    'VHS_VideoCombine before I can safely author that workflow pattern.")'
                ),
                "message": "I found the HotShotXL workflow shape but not an authorable adaptation.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "route": "adapt",
            "executor_classification": {
                "route": "adapt",
                "task": "edit_graph",
                "implement": True,
                "research": True,
                "known_graph_context": "HotShotXL is not authorable from local schema.",
                "research_goal": "Find canonical HotShotXL workflow precedent.",
            },
            "executor_research_brief": {
                "research_goal": "Find canonical HotShotXL workflow.",
                "source_preferences": ["workflows", "messages"],
            },
            "session_id": "hotshot-preloaded-context-clarify",
            "max_batches": 4,
            "max_consecutive_errors": 2,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert result["clarification_required"] is True
    assert result["graph_unchanged"] is True
    assert len(result["batch_turns"]) == 1


def test_adapt_prefetch_compiles_workflow_classes_into_schema_backed_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def fake_resolve_missing_nodes(query: str, *, query_intent: str | None = None, **_kwargs: object) -> object:
        if query != "ADE_LoadAnimateDiffModel":
            return types.SimpleNamespace(candidates=())
        assert query_intent == "class_name"
        candidate = {
            "pack": {
                "slug": "ComfyUI-AnimateDiff-Evolved",
                "source": "comfyui-manager",
                "url": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved",
            },
            "expected_classes": ["ADE_LoadAnimateDiffModel"],
            "validation_mode": "class_validatable",
            "evidence": [
                {
                    "source": "custom-node-map",
                    "tier": "comfy-manager",
                    "class_type": "ADE_LoadAnimateDiffModel",
                }
            ],
            "provisional_schema": {},
            "runnable": False,
            "stable_install_hash": "ade-prefetch-class-map",
        }
        return types.SimpleNamespace(candidates=(candidate,))

    monkeypatch.setattr(
        "vibecomfy.registry.pack_resolver.resolve_missing_nodes",
        fake_resolve_missing_nodes,
    )
    responses = iter(
        [
            {
                "batch": "ade_model = ADE_LoadAnimateDiffModel(near=saveimage)\ndone()",
                "message": "Placed the schema-backed AnimateDiff model loader from precompiled precedent capabilities.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "route": "adapt",
            "executor_classification": {
                "route": "adapt",
                "task": "edit_graph",
                "implement": True,
                "research": True,
                "research_goal": "Find canonical HotShotXL workflow wiring.",
            },
            "execution_protocol_notes": {
                "workflow_precedent_status": "compatible_workflow_found",
                "research_sources": [
                    {
                        "source": "hivemind_workflow",
                        "pack": "workflow",
                        "node_types": [
                            "CheckpointLoaderSimple",
                            "ADE_LoadAnimateDiffModel",
                            "SaveImage",
                        ],
                        "reasons": ["hivemind:body matched 'HotShotXL'"],
                    }
                ],
            },
            "session_id": "hotshot-prefetch-capabilities",
            "max_batches": 2,
            "max_consecutive_errors": 1,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert result["queue_allowed"] is False
    assert any(
        node.get("type") == "ADE_LoadAnimateDiffModel"
        for node in result["graph"].get("nodes", [])
        if isinstance(node, dict)
    )
    model_request = json.loads(
        (tmp_path / "hotshot-prefetch-capabilities" / "turns" / "0001" / "model_request.json").read_text(
            encoding="utf-8"
        )
    )
    request_text = json.dumps(model_request)
    assert "def ADE_LoadAnimateDiffModel" in request_text
    assert "schema_placeholder" in request_text


def test_adapt_prompt_uses_execution_protocol_discardability_header(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "route": "adapt",
            "execution_protocol_notes": {
                "_discardability": (
                    "This research context is provided as evidence. Use selected_precedent "
                    "as the grounding workflow interpretation unless it contradicts the "
                    "user's explicit request."
                ),
                "selected_precedent": {
                    "name": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
                    "minimal_spine": [
                        "ADE_AnimateDiffLoaderWithContext",
                        "ADE_AnimateDiffUniformContextOptions",
                        "VHS_VideoCombine",
                    ],
                },
                "research_sources": [
                    {
                        "source": "hivemind_workflow",
                        "pack": "workflow",
                        "workflow_schema": {
                            "ADE_AnimateDiffLoaderWithContext": {
                                "input": {
                                    "required": {
                                        "model": {"type": "MODEL"},
                                        "context_options": {"type": "CONTEXT_OPTIONS"},
                                    },
                                    "optional": {},
                                },
                                "outputs": [{"name": "MODEL", "type": "MODEL"}],
                            }
                        },
                    }
                ],
            },
            "session_id": "selected-precedent-header",
            "max_batches": 1,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: {
            "batch": "done()",
            "message": "No edit in this prompt-header regression.",
        },
        session_root=tmp_path,
    )

    assert "artifacts" in result
    model_request = json.loads(
        (tmp_path / "selected-precedent-header" / "turns" / "0001" / "model_request.json").read_text(
            encoding="utf-8"
        )
    )
    request_text = json.dumps(model_request)
    assert "Use selected_precedent as the grounding workflow interpretation" in request_text
    assert "This is contextual evidence, NOT authoritative guidance" not in request_text


def test_adapt_prompt_compacts_large_execution_protocol_notes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    huge_schema = {
        f"ADE_HugeWorkflowNode_{index}": {
            "input": {
                "required": {
                    f"field_{field_index}": {"type": "STRING", "default": "x" * 200}
                    for field_index in range(20)
                },
                "optional": {},
            },
            "outputs": [{"name": "MODEL", "type": "MODEL"}],
        }
        for index in range(40)
    }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "route": "adapt",
            "execution_protocol_notes": {
                "_discardability": (
                    "This research context is provided as evidence. Use selected_precedent "
                    "as the grounding workflow interpretation unless it contradicts the "
                    "user's explicit request."
                ),
                "workflow_precedent_status": "compatible_workflow_found",
                "research_goal": "Investigate HotShotXL workflow wiring.",
                "selected_precedent": {
                    "name": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
                    "minimal_spine": [
                        "ADE_AnimateDiffLoaderWithContext",
                        "ADE_AnimateDiffUniformContextOptions",
                        "VHS_VideoCombine",
                    ],
                    "terminal_output_path": ["VHS_VideoCombine"],
                },
                "research_sources": [
                    {
                        "source": "hivemind_workflow",
                        "pack": "workflow",
                        "description": "Detailed external workflow evidence. " * 500,
                        "node_types": [f"NodeType_{index}" for index in range(80)],
                        "workflow_schema": huge_schema,
                    },
                    {
                        "source": "hivemind_workflow",
                        "pack": "workflow",
                        "description": "Secondary source. " * 500,
                        "workflow_schema": huge_schema,
                    },
                    {
                        "source": "hivemind_workflow",
                        "pack": "workflow",
                        "description": "Tertiary source. " * 500,
                        "workflow_schema": huge_schema,
                    },
                    {
                        "source": "hivemind_workflow",
                        "pack": "workflow",
                        "description": "Omitted source. " * 500,
                        "workflow_schema": huge_schema,
                    },
                ],
            },
            "session_id": "selected-precedent-large-context",
            "max_batches": 1,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: {
            "batch": "done()",
            "message": "No edit in this large-context regression.",
        },
        session_root=tmp_path,
    )

    assert "artifacts" in result
    model_request_path = (
        tmp_path
        / "selected-precedent-large-context"
        / "turns"
        / "0001"
        / "model_request.json"
    )
    model_request = json.loads(model_request_path.read_text(encoding="utf-8"))
    request_text = json.dumps(model_request)
    assert model_request_path.stat().st_size < 80_000
    assert "selected_precedent" in request_text
    assert "ADE_AnimateDiffLoaderWithContext" in request_text
    assert "workflow_schema_omitted" in request_text
    assert "field_19" not in request_text
    assert "ADE_HugeWorkflowNode_39" not in request_text
    assert "research_sources_omitted" in request_text


def test_adapt_prompt_marks_unhydrated_workflow_schema_classes_observed_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "route": "adapt",
            "execution_protocol_notes": {
                "_discardability": (
                    "This research context is provided as evidence. Use selected_precedent "
                    "as the grounding workflow interpretation unless it contradicts the "
                    "user's explicit request."
                ),
                "selected_precedent": {
                    "name": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
                    "minimal_spine": [
                        "ADE_AnimateDiffLoaderWithContext",
                        "ADE_AnimateDiffUniformContextOptions",
                        "VHS_VideoCombine",
                    ],
                },
                "research_sources": [
                    {
                        "source": "hivemind_workflow",
                        "pack": "workflow",
                        "node_types": [
                            "ADE_AnimateDiffLoaderWithContext",
                            "ADE_AnimateDiffUniformContextOptions",
                            "VHS_VideoCombine",
                        ],
                        "workflow_schema": {
                            "ADE_AnimateDiffLoaderWithContext": {
                                "input": {
                                    "required": {
                                        "model": {"type": "MODEL"},
                                        "context_options": {"type": "CONTEXT_OPTIONS"},
                                    },
                                    "optional": {},
                                },
                                "outputs": [{"name": "MODEL", "type": "MODEL"}],
                            },
                            "ADE_AnimateDiffUniformContextOptions": {
                                "input": {"required": {}, "optional": {}},
                                "outputs": [{"name": "CONTEXT_OPTIONS", "type": "CONTEXT_OPTIONS"}],
                            },
                        },
                    }
                ],
            },
            "session_id": "selected-precedent-research-context",
            "max_batches": 1,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: {
            "batch": "done()",
            "message": "No edit in this workflow authoring status regression.",
        },
        session_root=tmp_path,
    )

    assert "artifacts" in result
    model_request = json.loads(
        (
            tmp_path
            / "selected-precedent-research-context"
            / "turns"
            / "0001"
            / "model_request.json"
        ).read_text(encoding="utf-8")
    )
    request_text = json.dumps(model_request)
    assert "ADE_AnimateDiffLoaderWithContext" in request_text
    assert "selected_precedent" in request_text
    assert "Workflow Authoring Status" not in request_text
    assert "Workflow-observed only, not addable yet" not in request_text
    assert "exact-class registry/schema research" not in request_text


def test_weak_registry_code_search_allows_install_blocker_clarify_without_authoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        assert kwargs.get("registry_resolver") is not None
        return ResearchResult(
            summary="Found 1 research result(s): ComfyUIWorkflowSuite",
            sources=(
                {
                    "source": "github",
                    "class_type": "ComfyUIWorkflowSuite",
                    "pack": "ComfyUIWorkflowSuite",
                    "description": "Expected classes: Limbicnation, ComfyUIWorkflowSuite, HotshotXL, User",
                    "resolver_candidate": {
                        "pack": {
                            "slug": "ComfyUIWorkflowSuite",
                            "source": "github",
                            "url": "https://github.com/Limbicnation/ComfyUIWorkflowSuite",
                        },
                        "expected_classes": ["HotshotXL", "ComfyUIWorkflowSuite", "User"],
                        "validation_mode": "class_validatable",
                        "evidence": [
                            {"source": "code-search", "tier": "github"},
                        ],
                        "provisional_schema": {},
                        "runnable": False,
                        "stable_install_hash": "weak-hotshot-code-search",
                    },
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    responses = iter(
        [
            {
                "batch": 'research("HotShotXL", sources=["registry"])',
                "message": "Found a weak GitHub code-search lead.",
            },
            {
                "batch": 'clarify("I could not find an authorable HotShotXL workflow adaptation from the available evidence.")',
                "message": "I could not find an authorable HotShotXL workflow adaptation from the available evidence.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "route": "adapt",
            "executor_classification": {
                "route": "adapt",
                "task": "edit_graph",
                "implement": True,
                "research": True,
                "research_goal": "Find canonical HotShotXL workflow wiring.",
            },
            "executor_research_brief": {
                "research_goal": "Find canonical HotShotXL workflow wiring.",
                "source_preferences": ["workflows", "messages"],
            },
            "session_id": "hotshot-weak-registry-clarify",
            "max_batches": 2,
            "max_consecutive_errors": 2,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert result["clarification_required"] is True
    assert result["graph_unchanged"] is True
    assert "could not find an authorable HotShotXL workflow adaptation" in result["message"]
    assert "apply_allowed" not in result
    assert "queue_allowed" not in result
    messages_path = tmp_path / "hotshot-weak-registry-clarify" / "turns" / "0001" / "messages.jsonl"
    turns = [
        json.loads(line)
        for line in messages_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert turns[1]["batch"] == 'clarify("I could not find an authorable HotShotXL workflow adaptation from the available evidence.")'
    assert turns[1]["clarification_required"] == "I could not find an authorable HotShotXL workflow adaptation from the available evidence."


def test_revise_hydrates_existing_unknown_node_from_registry_before_readonly_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    graph = {
        "nodes": [
            {
                "id": 12,
                "type": "ADE_AnimateDiffUniformContextOptions",
                "inputs": [],
                "outputs": [
                    {
                        "name": "CONTEXT_OPTIONS",
                        "slot_index": 0,
                        "type": "CONTEXT_OPTIONS",
                    }
                ],
                "properties": {"vibecomfy_uid": "n12"},
                "widgets_values": [8, 1, 3, "uniform", False],
            }
        ],
        "links": [],
    }

    def fake_resolve_missing_nodes(query: str, *, query_intent: str | None = None, **_kwargs: object) -> object:
        assert query == "ADE_AnimateDiffUniformContextOptions"
        assert query_intent == "class_name"
        candidate = {
            "pack": {
                "slug": "ComfyUI-AnimateDiff-Evolved",
                "source": "comfy-registry",
            },
            "expected_classes": ["ADE_AnimateDiffUniformContextOptions"],
            "provisional_schema": {
                "version": "1.0.0",
                "runnable": False,
                "schema": {
                    "nodes": {
                        "ADE_AnimateDiffUniformContextOptions": {
                            "input": {
                                "required": {},
                                "optional": {
                                    "widget_0": {"type": "INT", "default": 8},
                                    "widget_1": {"type": "INT", "default": 1},
                                    "widget_2": {"type": "INT", "default": 3},
                                    "widget_3": {"type": "STRING", "default": "uniform"},
                                    "widget_4": {"type": "BOOLEAN", "default": False},
                                },
                            },
                            "output": ["CONTEXT_OPTIONS"],
                            "output_name": ["CONTEXT_OPTIONS"],
                        }
                    }
                },
            },
            "stable_install_hash": "ade-context-options-schema",
        }
        return types.SimpleNamespace(candidates=(candidate,))

    monkeypatch.setattr(
        "vibecomfy.registry.pack_resolver.resolve_missing_nodes",
        fake_resolve_missing_nodes,
    )

    responses = iter(
        [
            {
                "batch": "ade_animatediffuniformcontextoptions.widget_0 = 16\ndone()",
                "message": "Changed the existing Hotshot context frame count to 16.",
            }
        ]
    )

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "can you make that actually generate 16 frames?",
            "session_id": "revise-existing-registry-hydrated-node",
            "route": "revise",
            "executor_classification": {
                "route": "revise",
                "task": "edit_graph",
                "implement": True,
                "research": False,
            },
            "max_batches": 2,
            "max_consecutive_errors": 1,
        },
        schema_provider=_Provider({}),
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] in {"candidate", "edit"}
    node = result["graph"]["nodes"][0]
    assert node["type"] == "ADE_AnimateDiffUniformContextOptions"
    assert node["widgets_values"] == [16, 1, 3, "uniform", False]
    evidence_path = tmp_path / "revise-existing-registry-hydrated-node" / "turns" / "0001" / "revision_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))["revision_evidence"]
    assert evidence["safe_candidate_possible"] is True
    assert evidence["topology"]["unknown_class_types"] == []
    assert evidence["readiness"]["missing_node_packs"] == []


def test_batch_repl_research_output_includes_later_web_source(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        local_sources = tuple(
            {
                "class_type": f"local/template/{index}",
                "source": "ready_template",
                "description": "Local template result.",
            }
            for index in range(7)
        )
        return ResearchResult(
            summary="Found mixed local and web evidence.",
            sources=(
                *local_sources,
                {
                    "class_type": "KintCark/Hotshot-XL-Gradio-Cpu-Termux",
                    "source": "web",
                    "url": "https://github.com/KintCark/Hotshot-XL-Gradio-Cpu-Termux",
                    "description": "GitHub result mentioning HotshotXL and ComfyUI.",
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch('research("ComfyUI HotshotXL")')
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    assert result.ok is True
    assert "local/template/0" in report
    assert "KintCark/Hotshot-XL-Gradio-Cpu-Termux" in report


def test_batch_repl_search_exact_miss_explains_local_schema_lookup() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    provider = _Provider(
        {
            "SaveAnimatedWEBP": NodeSchema(
                class_type="SaveAnimatedWEBP",
                pack=None,
                inputs={"images": InputSpec("IMAGE", required=True)},
                outputs=[],
                source_provider="test",
                confidence=1.0,
            )
        }
    )
    session = EditSession(_ui_graph(), schema_provider=provider)

    result = session.apply_batch('search(focus_types=["HotshotXL"])')
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    assert result.ok is True
    assert result.statements[0].op_kind == "query"
    query_output = result.statements[0].detail["query_output"]
    assert "No node signature found for exact class type(s): 'HotshotXL'." in query_output
    assert "not an internet or precedent search" in query_output
    assert "No available local class names contain the requested terms." in report


def test_batch_repl_research_query_output_is_in_next_turn_report(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    calls: list[dict[str, object]] = []

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        calls.append({"query": query, **kwargs})
        return ResearchResult(
            summary="Found Hotshot XL custom-node installation and workflow precedent.",
            sources=(
                {
                    "title": "ComfyUI-HotshotXL",
                    "url": "https://example.test/hotshot",
                    "description": "HotshotXL provides video generation custom nodes for ComfyUI.",
                },
            ),
            warnings=("local corpus unavailable",),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch('research("Hotshot XL ComfyUI 16 frames")')
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    assert result.ok is True
    assert result.statements[0].op_kind == "query"
    assert calls[0]["query"] == "Hotshot XL ComfyUI 16 frames"
    assert calls[0]["local_limit"] == 5
    assert calls[0]["hivemind_client"] is not None
    # Default ``workflows`` source now maps to local templates + Hivemind external
    # workflows; web search is only enabled when ``sources=["web"]`` is requested.
    assert calls[0]["web_search_client"] is None
    assert "Found Hotshot XL custom-node installation" in result.statements[0].detail["query_output"]
    assert "ComfyUI-HotshotXL" in report
    assert "local corpus unavailable" in report


def test_batch_repl_research_can_choose_web_only_source(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.porting.edit.session import EditSession

    calls: list[dict[str, object]] = []

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        calls.append({"query": query, **kwargs})
        return ResearchResult(summary="Web-only result.", sources=())

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch('research("HotshotXL ComfyUI", sources=["web"])')

    assert result.ok is True
    assert calls[0]["query"] == "HotshotXL ComfyUI"
    assert calls[0]["local_limit"] == 0
    assert calls[0]["hivemind_client"] is None
    assert calls[0]["web_search_client"] is not None
    assert result.statements[0].detail["research_sources"] == ("web",)


def test_batch_repl_research_output_includes_later_web_source(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import EditSession

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        local_sources = tuple(
            {
                "class_type": f"local/template/{index}",
                "source": "ready_template",
                "description": "Local template result.",
            }
            for index in range(7)
        )
        return ResearchResult(
            summary="Found mixed local and web evidence.",
            sources=(
                *local_sources,
                {
                    "class_type": "KintCark/Hotshot-XL-Gradio-Cpu-Termux",
                    "source": "web",
                    "url": "https://github.com/KintCark/Hotshot-XL-Gradio-Cpu-Termux",
                    "description": "GitHub result mentioning HotshotXL and ComfyUI.",
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)
    session = EditSession(_ui_graph(), schema_provider=_Provider({}))

    result = session.apply_batch('research("ComfyUI HotshotXL")')
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=1)

    assert result.ok is True
    assert "local/template/0" in report
    assert "KintCark/Hotshot-XL-Gradio-Cpu-Termux" in report


def test_batch_budget_failure_kind_prefers_schema_gap_then_unrepresentable_then_model_mistake() -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

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


def test_batch_budget_artifixer_report_hard_refuses_unrepresentable_surface() -> None:
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    graph = {"nodes": [{"id": 1, "type": "LoadImage"}], "links": []}
    state = SimpleNamespace(
        graph=graph,
        ui_payload=graph,
        batch_field_changes=(),
        batch_turn_count=1,
        batch_budget_state={"remaining_batches": 49, "consecutive_errors": 1},
        batch_turns=[
            {
                "landed_op_count": 0,
                "diagnostics": [
                    {
                        "code": "cross_scope_add_node_unsupported",
                        "message": "cross-scope add node unsupported",
                    }
                ],
                "statements": [],
            }
        ],
    )

    report = agent_edit_module._batch_budget_artifixer_report(
        state,
        FailureKind.UNREPRESENTABLE,
    )

    assert report["policy"] == "diagnostics_only"
    assert report["attempted"] is False
    assert report["outcome"] == "hard_refusal"
    assert report["reason"] == "unrepresentable_edit_surface"
    assert report["hard_refusal"] is True
    assert report["hard_refusal_codes"] == ["cross_scope_add_node_unsupported"]
    assert report["candidate_graph_changed"] is False


def test_batch_budget_artifixer_report_marks_changed_candidate_for_later_repair_study() -> None:
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    state = SimpleNamespace(
        graph={
            "nodes": [{"id": 1, "type": "SaveImage", "widgets_values": ["before"]}],
            "links": [],
        },
        ui_payload={
            "nodes": [{"id": 1, "type": "SaveImage", "widgets_values": ["after"]}],
            "links": [],
        },
        batch_field_changes=(),
        batch_turn_count=1,
        batch_budget_state={"remaining_batches": 49, "consecutive_errors": 1},
        batch_turns=[
            {
                "landed_op_count": 1,
                "diagnostics": [],
                "statements": [
                    {
                        "diagnostics": [
                            {
                                "code": "unknown_target_field",
                                "message": "unknown field on follow-up edit",
                            }
                        ]
                    }
                ],
            }
        ],
    )

    report = agent_edit_module._batch_budget_artifixer_report(
        state,
        FailureKind.MODEL_MISTAKE,
    )

    assert report["policy"] == "diagnostics_only"
    assert report["attempted"] is False
    assert report["outcome"] == "candidate_available"
    assert report["reason"] == "diagnostics_only"
    assert report["hard_refusal"] is False
    assert report["candidate_graph_changed"] is True
    assert report["landed_edits"] is True
    assert report["diagnostic_codes"] == ["unknown_target_field"]


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
    assert issue["detail"]["artifixer"]["policy"] == "diagnostics_only"
    assert issue["detail"]["artifixer"]["attempted"] is False
    assert issue["detail"]["artifixer"]["outcome"] == "not_attempted"
    assert issue["detail"]["artifixer"]["reason"] == "no_candidate_graph_change"
    diagnostics = result["agent_failure_context"]["diagnostics"]
    assert diagnostics[0]["code"] == "artifixer_not_attempted"
    assert diagnostics[0]["detail"]["failure_kind"] == FailureKind.MODEL_MISTAKE.value
    assert result["message"] == "I ran out of turn budget before completing the remaining changes."
    assert issue["detail"]["turn_count"] == 1
    assert issue["detail"]["budget_state"]["consecutive_errors"] == 1

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    batch_meta = audit["metadata"]["batch_repl"]
    assert batch_meta["turn_count"] == 1
    assert batch_meta["budget_state"]["remaining_batches"] == 3
    assert batch_meta["budget_state"]["consecutive_errors"] == 1
    assert batch_meta["exit_mode"] == "budget"
    assert batch_meta["final_summary"] == "Stopped after 1 turn(s); 3 turn(s) remaining."
    assert "Turn summary: 0 landed, 4 failed, 4 diagnostic(s), 3 turn(s) remaining, 1 consecutive error turn(s)." in batch_meta["feedback"]
    assert "✗ Statement 1: set_node_field" in batch_meta["feedback"]
    assert "✗ Statement 2: set_node_field" in batch_meta["feedback"]
    assert "batch_transaction_rolled_back" in batch_meta["feedback"]
    assert "cause: Statement depends on graph name 'extra' whose add-node statement did not land." in batch_meta["feedback"]
    assert "unknown_target_field: SaveImage has no editable field or input named 'not_a_field'." in batch_meta["feedback"]
    assert "unbound_graph_name: Graph name 'extra' is currently unbound because its add-node statement did not land." in batch_meta["feedback"]

    response_turns = json.loads(
        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
    )["turns"]
    turn0 = response_turns[0]["batch_result"]
    assert turn0["batch_ok"] is False
    assert turn0["landed_op_count"] == 0
    assert turn0["statement_count"] == 4
    assert len(turn0["diagnostics"]) == 4
    assert turn0["report"] == batch_meta["feedback"]

    statements = turn0["statements"]
    assert [item["landed"] for item in statements] == [False, False, False, False]
    assert statements[0]["diagnostics"][-1]["code"] == "batch_transaction_rolled_back"
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


def test_batch_repl_refuses_read_only_done_after_partial_failed_edit_and_allows_repair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack=None,
                inputs={"ckpt_name": InputSpec("CHOICE", choices=["juggernautXL_v8Rundiffusion.safetensors"])},
                outputs=[
                    OutputSpec("MODEL", "MODEL"),
                    OutputSpec("CLIP", "CLIP"),
                    OutputSpec("VAE", "VAE"),
                ],
                source_provider="test",
                confidence=1.0,
            ),
            "EmptyLatentImage": NodeSchema(
                class_type="EmptyLatentImage",
                pack=None,
                inputs={
                    "width": InputSpec("INT"),
                    "height": InputSpec("INT"),
                    "batch_size": InputSpec("INT"),
                },
                outputs=[OutputSpec("LATENT", "LATENT")],
                source_provider="test",
                confidence=1.0,
            ),
            "LoadImage": NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={"image": InputSpec("CHOICE", required=True, choices=["example.png"])},
                outputs=[OutputSpec("IMAGE", "IMAGE"), OutputSpec("MASK", "MASK")],
                source_provider="test",
                confidence=1.0,
            ),
            "VAEEncode": NodeSchema(
                class_type="VAEEncode",
                pack=None,
                inputs={
                    "pixels": InputSpec("IMAGE", required=True),
                    "vae": InputSpec("VAE", required=True),
                },
                outputs=[OutputSpec("LATENT", "LATENT")],
                source_provider="test",
                confidence=1.0,
            ),
            "KSampler": NodeSchema(
                class_type="KSampler",
                pack=None,
                inputs={
                    "model": InputSpec("MODEL", required=True),
                    "latent_image": InputSpec("LATENT", required=True),
                    "denoise": InputSpec("FLOAT"),
                },
                outputs=[OutputSpec("LATENT", "LATENT")],
                source_provider="test",
                confidence=1.0,
            ),
            "VAEDecode": NodeSchema(
                class_type="VAEDecode",
                pack=None,
                inputs={
                    "samples": InputSpec("LATENT", required=True),
                    "vae": InputSpec("VAE", required=True),
                },
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

    wf = VibeWorkflow("img2img-repair", WorkflowSource("img2img-repair"))
    wf.nodes["1"] = VibeNode(
        "1",
        "CheckpointLoaderSimple",
        inputs={"ckpt_name": "juggernautXL_v8Rundiffusion.safetensors"},
    )
    wf.nodes["2"] = VibeNode(
        "2",
        "EmptyLatentImage",
        inputs={"width": 1024, "height": 1024, "batch_size": 1},
    )
    wf.nodes["3"] = VibeNode("3", "KSampler", inputs={"denoise": 1.0})
    wf.nodes["4"] = VibeNode("4", "VAEDecode")
    wf.nodes["5"] = VibeNode("5", "SaveImage", inputs={"filename_prefix": "before"})
    wf.connect("1.0", "3.model")
    wf.connect("2.0", "3.latent_image")
    wf.connect("3.0", "4.samples")
    wf.connect("1.2", "4.vae")
    wf.connect("4.0", "5.images")
    graph = emit_ui_json(wf, schema_provider=provider)

    captured_messages: list[list[dict[str, str]]] = []
    scripted_turns = iter(
        [
            {
                "message": "Tried img2img with a placeholder input.",
                "batch": "\n".join(
                    [
                        "del emptylatentimage",
                        "loadimage = LoadImage(image='input.png')",
                        "vaeencode = VAEEncode(pixels=loadimage.IMAGE, vae=checkpointloadersimple.VAE)",
                        "ksampler.latent_image = vaeencode.LATENT",
                        "ksampler.denoise = 0.8",
                        "done()",
                    ]
                ),
            },
            {
                "message": "Looked up the valid LoadImage input.",
                "batch": 'search(focus_types=["LoadImage", "VAEEncode"])\ndone()',
            },
            {
                "message": "Repaired the img2img pipeline with the available image.",
                "batch": "\n".join(
                    [
                        "loadimage = LoadImage(image='example.png')",
                        "vaeencode = VAEEncode(pixels=loadimage.IMAGE, vae=checkpointloadersimple.VAE)",
                        "ksampler.latent_image = vaeencode.LATENT",
                        "done()",
                    ]
                ),
            },
        ]
    )

    def _fake_batch_client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_messages.append(messages)
        return next(scripted_turns)

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "Make it img2img",
            "session_id": "batch-read-only-done-after-partial-failure",
            "max_batches": 4,
            "max_consecutive_errors": 3,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert len(captured_messages) == 3
    assert "done() was NOT accepted" in captured_messages[2][1]["content"]
    assert "A search() is read-only and does NOT fix" in captured_messages[2][1]["content"]
    assert "def LoadImage(image: CHOICE[\"example.png\"])" in captured_messages[2][1]["content"]

    node_types = [node["type"] for node in result["graph"]["nodes"]]
    assert "LoadImage" in node_types
    assert "VAEEncode" in node_types
    ksampler = next(node for node in result["graph"]["nodes"] if node["type"] == "KSampler")
    latent_input = next(item for item in ksampler["inputs"] if item["name"] == "latent_image")
    assert latent_input["link"] is not None


def test_handle_agent_edit_batch_repl_returns_successful_non_commit_clarification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    events: list[tuple[str, dict[str, object], str | None]] = []

    def _capture_ws_send(event: str, payload: dict[str, object], *, client_id: str | None = None) -> None:
        turn_dir = turn_dir_for(tmp_path, "batch-clarify", str(payload["turn_id"]))
        assert (turn_dir / "candidate.ui.json").is_file()
        assert (turn_dir / "model_response.json").is_file()
        assert (turn_dir / "messages.jsonl").is_file()
        events.append((event, payload, client_id))

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit._ws_send", _capture_ws_send)

    def _fake_batch_client(_messages):
        return {
            "batch": 'clarify("before or after the face restoration?")\ndone()',
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
        client_id="client-clarify",
    )

    assert result["ok"] is True
    assert result["contract_version"] == AGENT_EDIT_TURN_CONTRACT_VERSION
    assert result["outcome"]["kind"] == "clarify"
    assert result["outcome"]["question"].startswith("before or after the face restoration?")
    assert result["outcome"]["clarification"]["message"] == result["outcome"]["question"]
    assert result["internal_outcome"] == {
        "kind": "clarify",
        "question": result["outcome"]["question"],
    }
    for forbidden in (
        "candidate",
        "graph",
        "candidate_graph",
        "candidate_graph_hash",
        "candidate_structural_graph_hash",
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
    ):
        assert forbidden not in result
    assert result["debug"]["batch_repl"]["exit_mode"] == "pure_clarify"
    assert result["clarification_required"] is True
    assert result["graph_unchanged"] is True
    assert result["message"] == result["outcome"]["question"]
    assert "done_summary" not in result
    assert len(result["batch_turns"]) == 1
    assert result["batch_turns"][0]["turn_number"] == 0
    assert result["batch_turns"][0]["batch"] == 'clarify("before or after the face restoration?")\ndone()'
    assert result["batch_turns"][0]["message"] == "I need one detail before continuing."
    assert result["batch_turns"][0]["clarification_required"] is True
    assert result["batch_turns"][0]["clarification_message"] == "before or after the face restoration?"
    assert result["batch_turns"][0]["field_changes"] == []
    assert events == [
        (
            "vibecomfy.agent_edit.turn",
            {
                "session_id": "batch-clarify",
                "turn_id": events[0][1]["turn_id"],
                "turn_number": 0,
                "entry_type": "batch",
                "status": "clarify",
                "message": "I need one detail before continuing.",
                "clarification_required": True,
                "clarification_message": "before or after the face restoration?",
                "statements": [
                    {
                        "clarification": True,
                        "message": "before or after the face restoration?",
                    }
                ],
                "exit_mode": "pure_clarify",
                "budget": {
                    "remaining_batches": 2,
                    "consecutive_errors": 0,
                },
            },
            "client-clarify",
        )
    ]

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["metadata"]["batch_repl"]["exit_mode"] == "pure_clarify"
    assert audit["metadata"]["batch_repl"]["turn_count"] == 1


def test_handle_agent_edit_research_route_writes_agentic_messages_and_blocks_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    captured_messages: list[list[dict[str, str]]] = []

    def _fake_batch_client(messages):
        captured_messages.append(messages)
        return {
            "batch": 'research("distilled faster ComfyUI inference", sources=["workflows"])\ndone()',
            "message": "Distilled/faster options depend on the model family and available workflow precedent.",
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "is there a distilled/faster way to run?",
            "route": "research",
            "executor_route": "research",
            "research_brief": {
                "research_goal": "Find distilled or faster ways to run the current ComfyUI video workflow.",
                "search_directions": [
                    "distilled or lightning video/motion models compatible with AnimateDiff-style workflows",
                    "AnimateDiff speed settings such as context length, sampler, steps, and frame count",
                ],
                "source_preferences": ["workflows", "messages", "web"],
                "avoid": [
                    "generic searches for the raw sentence",
                    "stopword-only searches such as there way run",
                ],
                "known_graph_context": "The attached graph uses sampler/image-generation nodes.",
            },
            "session_id": "research-route",
            "max_batches": 3,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result.get("candidate") is None
    assert result["apply_eligibility"]["applyable"] is False
    assert result.get("graph_unchanged") is True
    assert captured_messages
    system_prompt = captured_messages[0][0]["content"]
    user_prompt = captured_messages[0][1]["content"]
    assert "research(" in system_prompt
    assert "You are answering a research question" in system_prompt
    assert "Do not edit the graph" in system_prompt
    assert "When a Research brief appears" in system_prompt
    assert "Do not search the raw user sentence" in system_prompt
    assert "Research brief from triage (tentative retrieval hints; not findings)" in user_prompt
    assert "Use these hints to seed focused research" in user_prompt
    assert "prefer evidence that matches the user goal and current graph" in user_prompt
    assert "distilled or lightning video/motion models" in user_prompt
    assert "stopword-only searches such as there way run" in user_prompt
    assert "Research evidence/context" not in user_prompt

    turn_dir = turn_dir_for(tmp_path, "research-route", result["turn_id"])
    messages_path = turn_dir / "messages.jsonl"
    assert messages_path.is_file()
    records = [
        json.loads(line)
        for line in messages_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records
    assert records[0]["batch"].startswith('research("distilled faster')
    assert (turn_dir / "model_request.json").is_file()
    assert (turn_dir / "model_response.json").is_file()


def test_handle_agent_edit_research_route_blocks_apply_even_if_model_emits_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _fake_batch_client(_messages):
        return {
            "batch": 'saveimage.filename_prefix = "after"\ndone()',
            "message": "I found a faster option and changed the graph.",
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "is there a distilled/faster way to run?",
            "route": "research",
            "executor_route": "research",
            "session_id": "research-route-edit-attempt",
            "max_batches": 2,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result.get("candidate") is None
    assert result["apply_eligibility"]["applyable"] is False
    assert result.get("canvas_apply_allowed") in (None, False)
    assert result["batch_turns"][0]["landed_op_count"] == 1
    turn_dir = turn_dir_for(tmp_path, "research-route-edit-attempt", result["turn_id"])
    assert (turn_dir / "messages.jsonl").is_file()


def test_handle_agent_edit_batch_repl_stops_repeated_discovery_only_turns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        return ResearchResult(
            summary="No workflow/template precedents found.",
            sources=(),
            warnings=("precedent research: no workflow/template precedents found",),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)

    calls = 0

    def _fake_batch_client(_messages):
        nonlocal calls
        calls += 1
        return {
            "batch": 'research("Hotshot XL ComfyUI workflow", sources=["workflows"])',
            "message": "Looking for the Hotshot XL workflow pattern.",
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch to generating 16 frames with Hotshot",
            "session_id": "batch-discovery-stop",
            "max_batches": 8,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert result["graph_unchanged"] is True
    assert result["debug"]["batch_repl"]["exit_mode"] == "pure_clarify"
    assert result["debug"]["batch_repl"]["turn_count"] == 6
    assert "could not produce a safe graph edit" in result["message"].lower()
    assert calls == 6
    assert len(result["batch_turns"]) == 6
    for turn in result["batch_turns"]:
        assert turn["landed_op_count"] == 0
        assert [statement["op_kind"] for statement in turn["statements"]] == ["query"]


def test_handle_agent_edit_batch_repl_nudges_after_three_discovery_only_turns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    captured_messages: list[list[dict[str, str]]] = []
    calls = 0

    def _fake_batch_client(messages: list[dict[str, str]]) -> dict[str, str]:
        nonlocal calls
        captured_messages.append(messages)
        calls += 1
        if calls <= 3:
            return {
                "batch": 'search(focus_types=["MissingSpectralGate"])',
                "message": "Checking the named spectral-gate authoring surface.",
            }
        return {
            "batch": (
                'clarify("Need an AUDIO typed path because no named '
                'spectral-gate node is available.")'
            ),
            "message": "I need a typed audio path before changing the graph.",
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Add spectral gating to the audio path",
            "session_id": "batch-discovery-nudge",
            "max_batches": 5,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert len(captured_messages) == 4
    early_user_prompts = "\n".join(
        messages[1]["content"] for messages in captured_messages[:3]
    )
    nudged_prompt = captured_messages[3][1]["content"]
    assert "Discovery-only loop nudge" not in early_user_prompts
    assert "Discovery-only loop nudge" in nudged_prompt
    assert "stop broad searching" in nudged_prompt
    assert "vibecomfy.exec" in nudged_prompt
    assert "typed `io` as a fallback" in nudged_prompt
    assert 'clarify("...")' in nudged_prompt


def test_handle_agent_edit_batch_repl_converges_repeated_discovery_to_existing_tweak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    calls = 0
    saw_direct_tweak_feedback = False

    def _fake_batch_client(messages):
        nonlocal calls, saw_direct_tweak_feedback
        calls += 1
        prompt_text = json.dumps(messages)
        if "Direct existing-node tweak fallback applies here" in prompt_text:
            saw_direct_tweak_feedback = True
        if calls <= 3:
            return {
                "batch": 'search(focus_types=["SaveImage"])',
                "message": "Looking up the save node schema.",
            }
        assert saw_direct_tweak_feedback
        return {
            "batch": 'saveimage.filename_prefix = "after"\ndone()',
            "message": "Changing the existing save prefix.",
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Change the output format prefix.",
            "session_id": "batch-discovery-existing-tweak",
            "max_batches": 6,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["graph_unchanged"] is False
    assert result["outcome"]["kind"] == "candidate"
    assert result["outcome"]["changes"] == [
        {"uid": "2", "field_path": "filename_prefix", "old": "before", "new": "after"}
    ]
    assert result["debug"]["batch_repl"]["exit_mode"] == "done"
    assert calls == 4
    assert saw_direct_tweak_feedback is True


def test_handle_agent_edit_batch_repl_discovery_nudge_suppressed_after_landed_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    captured_messages: list[list[dict[str, str]]] = []
    scripted_turns = iter(
        [
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Updated the save prefix.",
            },
            {
                "batch": 'search(focus_types=["MissingSpectralGate"])',
                "message": "Checking the named spectral-gate authoring surface.",
            },
            {
                "batch": 'search(focus_types=["MissingSpectralGate"])',
                "message": "Checking again for the same authoring surface.",
            },
            {
                "batch": 'search(focus_types=["MissingSpectralGate"])',
                "message": "One more lookup before finalizing.",
            },
            {
                "batch": "done()",
                "message": "Committed the candidate.",
            },
        ]
    )

    def _fake_batch_client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_messages.append(messages)
        return next(scripted_turns)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix and inspect audio gating options",
            "session_id": "batch-discovery-nudge-after-edit",
            "max_batches": 5,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert len(captured_messages) == 5
    all_user_prompts = "\n".join(
        messages[1]["content"] for messages in captured_messages
    )
    assert "Discovery-only loop nudge" not in all_user_prompts


def test_handle_agent_edit_batch_repl_unresolved_schema_capability_does_not_emit_noop_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        return ResearchResult(
            summary="Found registry-backed Hotshot schema evidence.",
            sources=(
                {
                    "source": "comfy-registry",
                    "class_type": "ComfyUI-AnimateDiff-Evolved",
                    "pack": "ComfyUI-AnimateDiff-Evolved",
                    "description": "Expected classes: ADE_AnimateDiffLoaderWithContext",
                    "resolver_candidate": {
                        "pack": {"slug": "ComfyUI-AnimateDiff-Evolved"},
                        "expected_classes": ["ADE_AnimateDiffLoaderWithContext"],
                        "evidence": [{"source": "custom-node-map", "tier": "comfy-manager"}],
                    },
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)

    responses = iter(
        [
            {
                "batch": 'research("Hotshot XL ComfyUI nodes", sources=["registry"])',
                "message": "Looking for Hotshot workflow precedent.",
            },
            {
                "batch": 'clarify("I could not find an authorable Hotshot workflow adaptation from the available evidence.")',
                "message": "I could not find an authorable Hotshot workflow adaptation from the available evidence.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch to generating 16 frames with Hotshot",
            "session_id": "batch-missing-custom-nodes-message",
            "max_batches": 4,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert result["clarification_required"] is True
    assert result["graph_unchanged"] is True
    assert result["message"] == "I could not find an authorable Hotshot workflow adaptation from the available evidence."
    assert result["message"] != "No graph changes were needed."


def test_handle_agent_edit_batch_repl_treats_followup_after_clarify_as_continuation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _clarify_client(_messages):
        return {
            "batch": 'clarify("Which image file should be used as the input?")',
            "message": "I need one detail before continuing.",
        }

    first = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Can you switch this to img2img",
            "session_id": "clarify-continuation",
            "max_batches": 1,
        },
        schema_provider=provider,
        deepseek_client=_clarify_client,
        session_root=tmp_path,
    )
    assert first["outcome"]["kind"] == "clarify"

    captured_messages: list[list[dict[str, str]]] = []

    def _done_client(messages):
        captured_messages.append(messages)
        return {
            "batch": "done()",
            "message": "Using the default image selection for the img2img setup.",
        }

    second = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Default for now",
            "session_id": "clarify-continuation",
            "max_batches": 1,
        },
        schema_provider=provider,
        deepseek_client=_done_client,
        session_root=tmp_path,
    )

    assert second["ok"] is True
    user_msg = captured_messages[0][1]["content"]
    assert "Conversation state (JSON; derived from the latest clarify outcome):" in user_msg
    assert '"active_request": "Can you switch this to img2img"' in user_msg
    assert '"current_user_request_is": "answer_to_pending_clarification"' in user_msg
    assert '"pending_clarification": "Which image file should be used as the input?' in user_msg
    assert "User request:\nDefault for now" in user_msg


def test_handle_agent_edit_batch_repl_done_commits_and_exposes_gate_c_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    events: list[tuple[str, dict[str, object], str | None]] = []
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit._ws_send",
        lambda event, payload, *, client_id=None: events.append((event, payload, client_id)),
    )
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
        client_id="client-done",
    )

    assert result["ok"] is True
    assert result["contract_version"] == AGENT_EDIT_TURN_CONTRACT_VERSION
    assert result["apply_allowed"] is True
    assert result["queue_allowed"] is True
    assert result["gates"]["queue_validate_ok"] is True
    assert any(
        stage["stage"] == "queue_validate" and stage["ok"] is True
        for stage in result["debug"]["stage_snapshots"]
    )
    assert result["candidate"]["state"] == "candidate"
    assert result["candidate"]["graph"] == result["graph"]
    assert result["candidate"]["graph_hash"] == result["candidate_graph_hash"]
    assert result["candidate"]["structural_graph_hash"] == result["candidate_structural_graph_hash"]
    assert result["candidate"]["baseline_graph_hash"] == result["baseline_graph_hash"]
    assert result["candidate"]["submit_graph_hash"] == result["submit_graph_hash"]

    assert (
        result["candidate"]["submit_structural_graph_hash"]
        == result["submit_structural_graph_hash"]
    )
    assert result["candidate"]["turn_identity"] == {
        "session_id": "batch-done",
        "turn_id": result["turn_id"],
        "baseline_turn_id": None,
        "idempotency_key": None,
    }
    assert result["eligibility"] == result["apply_eligibility"]
    assert result["debug"]["gates"] == result["gates"]
    assert result["debug"]["hashes"]["candidate_graph_hash"] == result["candidate_graph_hash"]
    assert result["debug"]["turn_identity"] == result["candidate"]["turn_identity"]
    assert "audit_ref" not in result["debug"]
    assert result["debug"]["batch_repl"]["exit_mode"] == "done"
    assert result["message"] == "Updated SaveImage filename_prefix from before to after."
    assert result["done_summary"] not in result["message"]
    assert result["done_summary"].startswith("Gate A passed:")
    assert "Gate B passed:" in result["done_summary"]
    assert "saveimage.filename_prefix" in result["done_summary"]
    assert "after" in result["done_summary"]
    assert result["change_details"]["done_summary"] == result["done_summary"]
    assert result["change_details"]["landed_operation_count"] == 1
    assert result["change_details"]["operations"] == [
        {
            "uid": "2",
            "field_path": "filename_prefix",
            "old": "before",
            "new": "after",
            "summary": "Changed 2.filename_prefix from before to after.",
        }
    ]
    assert result["report"]["done_summary"] == result["done_summary"]
    assert result["outcome"] == {
        "kind": "candidate",
        "changes": [
            {
                "uid": "2",
                "field_path": "filename_prefix",
                "old": "before",
                "new": "after",
            }
        ],
    }
    assert result["internal_outcome"]["kind"] == "edit"
    assert len(result["batch_turns"]) == 2
    assert result["batch_turns"][0]["turn_number"] == 0
    assert result["batch_turns"][0]["batch_ok"] is True
    assert result["batch_turns"][0]["statement_count"] == 1
    assert result["batch_turns"][0]["landed_op_count"] == 1
    assert result["batch_turns"][0]["field_changes"] == [
        {
            "uid": "2",
            "field_path": "filename_prefix",
            "old": "before",
            "new": "after",
        }
    ]
    assert (
        result["batch_turns"][0]["delta_ops"]
        == result["batch_turns"][0]["delta_ops_envelope"]["ops"]
    )
    assert set(result["batch_turns"][0]["delta_ops_envelope"]) == {"schema_version", "ops"}
    assert result["batch_turns"][0]["diff"]
    assert result["batch_turns"][0]["report"]
    assert result["batch_turns"][1]["turn_number"] == 1
    assert result["batch_turns"][1]["statements"][0]["op_kind"] == "done"
    assert result["batch_turns"][1]["message"] == "Ready to commit the candidate."
    assert result["batch_turns"][1]["field_changes"] == []

    graph_text = json.dumps(result["graph"], sort_keys=True)
    assert "after" in graph_text
    assert "before" not in graph_text

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["metadata"]["batch_repl"]["exit_mode"] == "done"
    assert audit["metadata"]["batch_repl"]["done_summary"] == result["done_summary"]
    turn_dir = tmp_path / "batch-done" / "turns" / result["turn_id"]
    persisted_response = json.loads(
        (turn_dir / "response.json").read_text(encoding="utf-8")
    )
    assert persisted_response["candidate"] == result["candidate"]
    assert persisted_response["candidate"]["graph_hash"] == result["candidate_graph_hash"]
    assert (
        persisted_response["candidate"]["structural_graph_hash"]
        == result["candidate_structural_graph_hash"]
    )
    assert persisted_response["outcome"]["changes"] == result["outcome"]["changes"]
    assert (
        persisted_response["change_details"]["operations"]
        == result["change_details"]["operations"]
    )
    assert "audit_ref" not in persisted_response["debug"]
    assert persisted_response["audit_ref"] == result["audit_ref"]
    chat = json.loads((turn_dir / "chat.json").read_text(encoding="utf-8"))
    agent_message = next(message for message in chat["messages"] if message["role"] == "agent")
    assert agent_message["outcome"] == result["outcome"]
    assert agent_message["change_details"]["operations"] == result["change_details"]["operations"]
    rehydrated = read_session_chat(tmp_path, "batch-done", max_messages=10)
    latest_agent = [msg for msg in rehydrated["messages"] if msg["role"] == "agent"][-1]
    assert latest_agent["outcome"] == result["outcome"]
    assert latest_agent["change_details"]["operations"] == [
        {
            "summary": result["change_details"]["operations"][0]["summary"],
            "field_path": "filename_prefix",
        }
    ]
    assert [payload["status"] for _, payload, _ in events] == ["in_progress", "done"]
    assert all(event == "vibecomfy.agent_edit.turn" for event, _, _ in events)
    assert all(client_id == "client-done" for _, _, client_id in events)
    assert events[0][1]["turn_number"] == 0
    assert events[0][1]["batch_ok"] is True
    assert events[0][1]["landed_op_count"] == 1
    assert events[1][1]["turn_number"] == 1
    assert events[1][1]["exit_mode"] == "done"
    assert events[1][1]["done_summary"] == result["done_summary"]


def test_handle_agent_edit_batch_repl_records_plan_evaluation_after_candidate_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    plan = ExecutionPlan(
        plan_id="save-prefix-plan",
        goal="SaveImage filename prefix must be updated.",
        done_conditions=(
            PlanCondition(
                condition_id="saveimage.filename_prefix.after",
                kind="required_value",
                class_type="SaveImage",
                expected="after",
            ),
        ),
    )
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
    captured_model_messages: list[list[dict[str, str]]] = []

    def _client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_model_messages.append(messages)
        return next(responses)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after and finish",
            "session_id": "batch-plan-runtime",
            "max_batches": 4,
            "execution_protocol_notes": {
                "execution_plan": {
                    "plan": plan.to_dict(),
                },
            },
        },
        schema_provider=provider,
        deepseek_client=_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["batch_turns"][0]["field_changes"] == [
        {
            "uid": "2",
            "field_path": "filename_prefix",
            "old": "before",
            "new": "after",
        }
    ]
    first_status = result["batch_turns"][0]["execution_plan_status"]
    assert first_status["plan_id"] == "save-prefix-plan"
    assert first_status["ok"] is True
    assert first_status["blocking"] is False
    assert first_status["failed_condition_ids"] == []
    assert result["batch_turns"][1]["execution_plan_status"]["ok"] is True
    assert len(captured_model_messages) == 2
    turn0_prompt = captured_model_messages[0][1]["content"]
    turn1_prompt = captured_model_messages[1][1]["content"]
    assert "Execution plan status (authoritative compact JSON):" in turn0_prompt
    assert '"plan_id": "save-prefix-plan"' in turn0_prompt
    assert '"ok": null' in turn0_prompt
    assert "plan has not been evaluated yet." not in turn0_prompt
    assert "Execution plan status (authoritative compact JSON):" in turn1_prompt
    assert '"plan_id": "save-prefix-plan"' in turn1_prompt
    assert '"ok": true' in turn1_prompt
    assert '"blocking": false' in turn1_prompt
    assert '"failed_condition_ids": []' in turn1_prompt

    turn_dir = turn_dir_for(tmp_path, "batch-plan-runtime", result["turn_id"])
    persisted_evaluation = json.loads(
        (turn_dir / "plan_evaluation.json").read_text(encoding="utf-8")
    )
    assert persisted_evaluation["ok"] is True
    assert persisted_evaluation["failed_conditions"] == []

    messages_text = (turn_dir / "messages.jsonl").read_text(encoding="utf-8")
    message_records = [
        json.loads(line)
        for line in messages_text.splitlines()
        if line.strip()
    ]
    assert message_records[0]["execution_plan_status"] == first_status
    model_response = json.loads(
        (turn_dir / "model_response.json").read_text(encoding="utf-8")
    )
    assert model_response["turns"][0]["batch_result"]["execution_plan_status"] == first_status


def test_handle_agent_edit_batch_repl_refuses_done_when_plan_evaluation_blocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    condition = PlanCondition(
        condition_id="saveimage.filename_prefix.after",
        kind="required_value",
        class_type="SaveImage",
        expected="after",
    )
    plan = ExecutionPlan(
        plan_id="save-prefix-required-step",
        goal="SaveImage filename prefix must be updated before completion.",
        required_steps=(
            PlanStep(
                step_id="save-prefix-step",
                kind="set_widget",
                class_type="SaveImage",
                conditions=(condition,),
            ),
        ),
    )
    responses = iter(
        [
            {
                "batch": 'saveimage.filename_prefix = "wrong"\ndone()',
                "message": "Changed the save prefix.",
            },
            {
                "batch": 'saveimage.filename_prefix = "after"\ndone()',
                "message": "Corrected the save prefix.",
            },
        ]
    )
    captured_model_messages: list[list[dict[str, str]]] = []

    def _client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_model_messages.append(messages)
        return next(responses)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after and finish",
            "session_id": "batch-plan-done-refusal",
            "max_batches": 3,
            "execution_protocol_notes": {
                "execution_plan": {
                    "plan": plan.to_dict(),
                },
            },
        },
        schema_provider=provider,
        deepseek_client=_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert len(result["batch_turns"]) == 2
    assert result["debug"]["batch_repl"]["budget_state"]["max_batches"] == 3
    assert result["debug"]["batch_repl"]["budget_state"]["remaining_batches"] == 1
    assert len(captured_model_messages) == 2
    first_prompt = captured_model_messages[0][1]["content"]
    retry_prompt = captured_model_messages[1][1]["content"]
    assert "done() was NOT accepted" not in first_prompt
    assert "Execution plan status (authoritative compact JSON):" in retry_prompt
    assert '"plan_id": "save-prefix-required-step"' in retry_prompt
    assert '"ok": false' in retry_prompt
    assert '"blocking": true' in retry_prompt
    assert '"feedback": "plan evaluation failed: saveimage.filename_prefix.after."' in retry_prompt
    assert '"failed_condition_ids": [' in retry_prompt
    assert '"saveimage.filename_prefix.after"' in retry_prompt
    assert '"step_id": "save-prefix-step"' in retry_prompt
    assert "done() was NOT accepted" in retry_prompt
    assert "missing required execution-plan step ids: save-prefix-step" in retry_prompt
    assert (
        "failed execution-plan condition ids: saveimage.filename_prefix.after"
        in retry_prompt
    )
    assert result["batch_turns"][0]["execution_plan_status"]["ok"] is False
    assert result["batch_turns"][0]["execution_plan_status"]["blocking"] is True
    assert result["batch_turns"][0]["execution_plan_status"]["failed_condition_ids"] == [
        "saveimage.filename_prefix.after"
    ]
    assert result["batch_turns"][1]["execution_plan_status"]["ok"] is True
    assert result["batch_turns"][1]["execution_plan_status"]["blocking"] is False

    turn_dir = turn_dir_for(tmp_path, "batch-plan-done-refusal", result["turn_id"])
    persisted_request = json.loads(
        (turn_dir / "model_request.json").read_text(encoding="utf-8")
    )
    assert len(persisted_request["turns"]) == 2
    assert (
        "done() was NOT accepted"
        not in persisted_request["turns"][0]["messages"][1]["content"]
    )
    assert (
        "done() was NOT accepted"
        in persisted_request["turns"][1]["messages"][1]["content"]
    )
    persisted_response = json.loads(
        (turn_dir / "model_response.json").read_text(encoding="utf-8")
    )
    assert (
        "done() was NOT accepted"
        in persisted_response["turns"][0]["batch_result"]["report"]
    )
    persisted_evaluation = json.loads(
        (turn_dir / "plan_evaluation.json").read_text(encoding="utf-8")
    )
    assert persisted_evaluation["ok"] is True
    assert persisted_evaluation["failed_conditions"] == []

    non_plan_responses = iter(
        [
            {
                "batch": 'saveimage.filename_prefix = "plain"\ndone()',
                "message": "Changed the save prefix without a plan.",
            },
        ]
    )
    non_plan_messages: list[list[dict[str, str]]] = []

    def _non_plan_client(messages: list[dict[str, str]]) -> dict[str, str]:
        non_plan_messages.append(messages)
        return next(non_plan_responses)

    non_plan_result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to plain and finish",
            "session_id": "batch-no-plan-after-plan-refusal",
            "max_batches": 3,
        },
        schema_provider=provider,
        deepseek_client=_non_plan_client,
        session_root=tmp_path,
    )

    assert non_plan_result["ok"] is True
    assert len(non_plan_messages) == 1
    non_plan_prompt = non_plan_messages[0][1]["content"]
    assert "Execution plan status (authoritative compact JSON):" not in non_plan_prompt
    assert "done() was NOT accepted" not in non_plan_prompt
    assert "save-prefix-required-step" not in non_plan_prompt
    assert "saveimage.filename_prefix.after" not in non_plan_prompt


def test_handle_agent_edit_hotshotxl_sidecar_done_remains_non_applyable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _hotshotxl_video_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    captured_model_messages: list[list[dict[str, str]]] = []
    responses = iter(
        [
            {
                "batch": "motion = ADE_AnimateDiffLoaderWithContext(near=saveimage)\ndone()",
                "message": "Added the HotShotXL AnimateDiff node.",
            },
            {
                "batch": (
                    'clarify("I cannot complete HotShotXL until the '
                    'AnimateDiff branch is wired into the video terminal.")'
                ),
                "message": "I cannot complete the requested HotShotXL edit yet.",
            },
        ]
    )

    def _client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_model_messages.append(messages)
        return next(responses)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "session_id": "hotshotxl-sidecar-plan-block",
            "max_batches": 2,
            "max_consecutive_errors": 2,
            "execution_protocol_notes": {
                "execution_plan": {
                    "plan": _hotshotxl_active_video_plan().to_dict(),
                },
            },
        },
        schema_provider=provider,
        deepseek_client=_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["candidate"] is None
    assert result["apply_allowed"] is False
    assert result["canvas_apply_allowed"] is False
    assert result["apply_eligibility"]["applyable"] is False
    assert result["gates"]["plan_validate_ok"] is False
    assert result["debug"]["gates"]["plan_validate_ok"] is False
    assert result["execution_plan_status"]["ok"] is False
    assert result["execution_plan_status"]["blocking"] is True
    assert set(result["execution_plan_status"]["failed_condition_ids"]) == {
        "add-video-terminal.required_class",
        "hotshotxl.motion_reaches_video_terminal",
        "hotshotxl.active_output_is_video",
    }
    assert "plan evaluation failed" in result["execution_plan_feedback"]
    assert "done() was NOT accepted" in result["batch_turns"][0]["report"]
    assert "hotshotxl.motion_reaches_video_terminal" in result["batch_turns"][0]["report"]
    assert "hotshotxl-active-video-path" in result["batch_turns"][0]["report"]
    assert len(captured_model_messages) == 2
    retry_prompt = captured_model_messages[1][1]["content"]
    assert "done() was NOT accepted" in retry_prompt
    assert "failed execution-plan condition ids:" in retry_prompt

    turn_dir = turn_dir_for(
        tmp_path,
        "hotshotxl-sidecar-plan-block",
        result["turn_id"],
    )
    assert Path(result["artifacts"]["execution_plan"]) == turn_dir / "execution_plan.json"
    assert Path(result["artifacts"]["plan_evaluation"]) == turn_dir / "plan_evaluation.json"
    persisted_evaluation = json.loads(
        (turn_dir / "plan_evaluation.json").read_text(encoding="utf-8")
    )
    assert persisted_evaluation["ok"] is False
    assert persisted_evaluation["blocking"] is True
    assert {
        item["condition_id"]
        for item in persisted_evaluation["failed_conditions"]
    } >= {
        "hotshotxl.motion_reaches_video_terminal",
        "hotshotxl.active_output_is_video",
    }
    response_payload = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
    assert response_payload["candidate"] is None
    assert response_payload["gates"]["plan_validate_ok"] is False
    assert response_payload["artifacts"]["plan_evaluation"] == str(
        turn_dir / "plan_evaluation.json"
    )
    debug_artifacts = response_payload["debug"]["execution_plan_artifacts"]
    assert debug_artifacts["execution_plan"]["path"] == str(turn_dir / "execution_plan.json")
    assert debug_artifacts["plan_evaluation"]["path"] == str(
        turn_dir / "plan_evaluation.json"
    )


def test_handle_agent_edit_hotshotxl_complete_plan_keeps_queue_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _hotshotxl_video_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    queue_issue = {
        "code": "schema_less_queue_blocker",
        "severity": "error",
        "failure_kind": FailureKind.SCHEMA_LESS_QUEUE_BLOCKER.value,
        "detail": {"node_id": "video"},
        "message": "HotShotXL custom video node is not queue-validated locally.",
    }
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.queue_stage_result",
        lambda **_kwargs: StageResult(
            stage="queue_validate",
            ok=False,
            blocking=False,
            issues=(queue_issue,),
            gate_updates={"queue_validate_ok": False},
        ),
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch this to instead generate 8 frames of video using HotShotXL",
            "session_id": "hotshotxl-complete-plan-queue-warning",
            "max_batches": 2,
            "max_consecutive_errors": 2,
            "execution_protocol_notes": {
                "execution_plan": {
                    "plan": _hotshotxl_active_video_plan().to_dict(),
                },
            },
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: {
            "batch": (
                "motion = ADE_AnimateDiffLoaderWithContext(near=saveimage)\n"
                "video = VHS_VideoCombine(images=motion.IMAGE, near=motion)\n"
                "done()"
            ),
            "message": "Wired the HotShotXL motion branch into a video terminal.",
        },
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert result["candidate"] is not None
    assert result["apply_allowed"] is True
    assert result["canvas_apply_allowed"] is True
    assert result["queue_allowed"] is False
    assert result["apply_eligibility"]["reason"] == "queue_blocked_warning"
    assert result["apply_eligibility"]["warnings"] == ["queue_blocked"]
    assert result["gates"]["plan_validate_ok"] is True
    assert result["gates"]["queue_validate_ok"] is False
    assert result["execution_plan_status"]["ok"] is True
    assert result["execution_plan_status"]["failed_condition_ids"] == []
    assert result["execution_plan_feedback"].endswith("plan evaluation passed.")
    assert result["task_satisfaction"][-1]["check"] == "execution_plan"
    assert result["task_satisfaction"][-1]["satisfaction"] == "pass"

    node_types = {node.get("type") for node in result["graph"]["nodes"]}
    assert "ADE_AnimateDiffLoaderWithContext" in node_types
    assert "VHS_VideoCombine" in node_types
    turn_dir = turn_dir_for(
        tmp_path,
        "hotshotxl-complete-plan-queue-warning",
        result["turn_id"],
    )
    persisted_evaluation = json.loads(
        (turn_dir / "plan_evaluation.json").read_text(encoding="utf-8")
    )
    assert persisted_evaluation["ok"] is True
    assert persisted_evaluation["failed_conditions"] == []
    response_payload = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
    assert response_payload["candidate"] is not None
    assert response_payload["apply_eligibility"]["reason"] == "queue_blocked_warning"
    assert response_payload["execution_plan_status"]["ok"] is True
    assert response_payload["artifacts"]["execution_plan"] == str(
        turn_dir / "execution_plan.json"
    )
    assert response_payload["artifacts"]["plan_evaluation"] == str(
        turn_dir / "plan_evaluation.json"
    )


def test_batch_repl_response_failed_execution_plan_suppresses_candidate_and_exposes_refs(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response

    plan = ExecutionPlan(
        plan_id="save-prefix-plan",
        goal="SaveImage filename prefix must be updated.",
        done_conditions=(
            PlanCondition(
                condition_id="saveimage.filename_prefix.after",
                kind="required_value",
                class_type="SaveImage",
                expected="after",
            ),
        ),
    )
    evaluation = PlanEvaluation(
        plan_id=plan.plan_id,
        ok=False,
        blocking=True,
        failed_conditions=(
            {
                "condition_id": "saveimage.filename_prefix.after",
                "severity": "required",
                "message": "Save prefix is still wrong.",
            },
        ),
        feedback="plan evaluation blocked: SaveImage prefix is still wrong.",
    )
    execution_plan_path = tmp_path / "execution_plan.json"
    plan_evaluation_path = tmp_path / "plan_evaluation.json"
    execution_plan_path.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    plan_evaluation_path.write_text(json.dumps(evaluation.to_dict()), encoding="utf-8")
    state = _make_state(
        graph={"nodes": []},
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="applied change",
        execution_plan=plan,
        plan_evaluation=evaluation,
        execution_plan_path=execution_plan_path,
        plan_evaluation_path=plan_evaluation_path,
        artifacts={},
    )
    context = TurnContext(session_id="plan-fail", turn_id="0001")
    for gate_name in context.gate_results:
        context.set_gate(gate_name, True)

    response = _build_batch_repl_response(state, context)

    assert "execution_plan" not in response
    assert response["outcome"]["kind"] in PUBLIC_OUTCOME_KINDS
    assert response["candidate"] is None
    assert response.get("candidate_graph") is None
    assert response["outcome"]["kind"] == "noop"
    assert response["eligibility"] == response["apply_eligibility"]
    assert response["apply_allowed"] is False
    assert response["apply_eligibility"]["applyable"] is False
    assert response["apply_eligibility"]["reason"] == "no_candidate"
    assert response["canvas_apply_allowed"] is False
    assert response["queue_allowed"] is False
    assert response["gates"]["plan_validate_ok"] is False
    assert response["debug"]["gates"]["plan_validate_ok"] is False
    assert response["execution_plan_status"]["ok"] is False
    assert response["execution_plan_status"]["blocking"] is True
    assert response["execution_plan_status"]["failed_condition_ids"] == [
        "saveimage.filename_prefix.after"
    ]
    assert "SaveImage prefix is still wrong" in response["execution_plan_feedback"]
    assert "failed_conditions=saveimage.filename_prefix.after" in response["execution_plan_feedback"]
    assert response["artifacts"]["execution_plan"] == str(execution_plan_path)
    assert response["artifacts"]["plan_evaluation"] == str(plan_evaluation_path)
    debug_artifacts = response["debug"]["execution_plan_artifacts"]
    assert debug_artifacts["execution_plan"]["path"] == str(execution_plan_path)
    assert debug_artifacts["execution_plan"]["sha256"]
    assert debug_artifacts["execution_plan"]["byte_count"] > 0
    assert debug_artifacts["plan_evaluation"]["path"] == str(plan_evaluation_path)
    assert debug_artifacts["plan_evaluation"]["sha256"]
    assert debug_artifacts["plan_evaluation"]["byte_count"] > 0
    plan_entry = response["task_satisfaction"][0]
    assert plan_entry["check"] == "execution_plan"
    assert plan_entry["satisfaction"] == "fail"
    assert plan_entry["failed_condition_ids"] == ["saveimage.filename_prefix.after"]
    assert "SaveImage prefix is still wrong" in plan_entry["feedback"]


def test_batch_repl_response_no_plan_preserves_legacy_candidate_aliases() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response

    state = _make_state(
        graph={"nodes": []},
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="applied change",
    )
    context = TurnContext(session_id="no-plan-compat", turn_id="0001")
    for gate_name in context.gate_results:
        context.set_gate(gate_name, True)
    context.set_gate("plan_validate_ok", False)

    response = _build_batch_repl_response(state, context)

    assert "execution_plan" not in response
    assert "execution_plan_status" not in response
    assert "execution_plan_feedback" not in response
    assert "task_satisfaction" not in response
    assert "execution_plan_artifacts" not in response["debug"]
    assert response["outcome"]["kind"] in PUBLIC_OUTCOME_KINDS
    assert response["outcome"]["kind"] == "candidate"
    assert response["candidate"] is not None
    assert response["candidate_graph"] == response["candidate"]["graph"]
    assert response["graph"] == response["candidate"]["graph"]
    assert response["eligibility"] == response["apply_eligibility"]
    assert response["apply_allowed"] is True
    assert response["apply_eligibility"]["applyable"] is True
    assert response["apply_eligibility"]["reason"] == "applyable"
    assert response["canvas_apply_allowed"] is True
    assert response["queue_allowed"] is True
    assert response["gates"]["plan_validate_ok"] is True
    assert response["debug"]["gates"]["plan_validate_ok"] is True


def test_batch_repl_response_passing_execution_plan_keeps_queue_warning_candidate(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response

    plan = ExecutionPlan(
        plan_id="save-prefix-plan",
        goal="SaveImage filename prefix must be updated.",
    )
    evaluation = PlanEvaluation(
        plan_id=plan.plan_id,
        ok=True,
        blocking=False,
        feedback="plan evaluation passed.",
    )
    execution_plan_path = tmp_path / "execution_plan.json"
    plan_evaluation_path = tmp_path / "plan_evaluation.json"
    execution_plan_path.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    plan_evaluation_path.write_text(json.dumps(evaluation.to_dict()), encoding="utf-8")
    state = _make_state(
        graph={"nodes": []},
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="applied change",
        execution_plan=plan,
        plan_evaluation=evaluation,
        execution_plan_path=execution_plan_path,
        plan_evaluation_path=plan_evaluation_path,
        artifacts={},
    )
    context = TurnContext(session_id="plan-pass", turn_id="0001")
    for gate_name in context.gate_results:
        context.set_gate(gate_name, True)
    context.set_gate("queue_validate_ok", False)

    response = _build_batch_repl_response(state, context)

    assert "execution_plan" not in response
    assert response["outcome"]["kind"] in PUBLIC_OUTCOME_KINDS
    assert response["candidate"] is not None
    assert response["candidate_graph"] == response["candidate"]["graph"]
    assert response["outcome"]["kind"] == "candidate"
    assert response["eligibility"] == response["apply_eligibility"]
    assert response["apply_allowed"] is True
    assert response["apply_eligibility"]["applyable"] is True
    assert response["apply_eligibility"]["reason"] == "queue_blocked_warning"
    assert response["canvas_apply_allowed"] is True
    assert response["queue_allowed"] is False
    assert response["gates"]["plan_validate_ok"] is True
    assert response["debug"]["gates"]["plan_validate_ok"] is True
    assert response["execution_plan_status"]["ok"] is True
    assert response["artifacts"]["execution_plan"] == str(execution_plan_path)
    assert response["artifacts"]["plan_evaluation"] == str(plan_evaluation_path)
    plan_entry = response["task_satisfaction"][0]
    assert plan_entry["check"] == "execution_plan"
    assert plan_entry["satisfaction"] == "pass"


def test_batch_repl_response_uses_post_validation_narrative_and_exposes_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    state = _make_state(
        graph={"nodes": []},
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        user_message="executor prose should stay non-public",
        session_dir=tmp_path / "session",
        turn_dir=tmp_path,
        narrative_context_path=tmp_path / "narrative_context.json",
        narrative_request_path=tmp_path / "narrative_request.json",
        narrative_response_path=tmp_path / "narrative_response.json",
        narrative_validation_path=tmp_path / "narrative_validation.json",
        artifacts={},
    )
    context = TurnContext(session_id="narrative-batch", turn_id="0001")
    for gate_name in context.gate_results:
        context.set_gate(gate_name, True)

    captured: dict[str, Any] = {}

    def _fake_narrative(
        state: AgentEditState,
        context: TurnContext,
        *,
        outcome: TurnOutcome | None = None,
        failure: FailureEnvelope | None = None,
        public_outcome: str | None = None,
        apply_eligibility: ApplyEligibility | None = None,
    ) -> str:
        del context, failure
        captured["outcome_kind"] = outcome.kind if outcome is not None else None
        captured["public_outcome"] = public_outcome
        captured["apply_eligibility"] = (
            apply_eligibility.to_dict() if apply_eligibility is not None else None
        )
        state.narrative_context_path.write_text("{}", encoding="utf-8")
        state.narrative_request_path.write_text(
            json.dumps({"attempted": False}, sort_keys=True),
            encoding="utf-8",
        )
        state.narrative_response_path.write_text(
            json.dumps({"selected_source": "fallback"}, sort_keys=True),
            encoding="utf-8",
        )
        state.narrative_validation_path.write_text(
            json.dumps(
                {
                    "attempted": False,
                    "selected_source": "fallback",
                    "fallback_reason": "deterministic_only",
                    "final_validation": {"ok": True},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        state.artifacts = {
            **(state.artifacts or {}),
            "narrative_context": str(state.narrative_context_path),
            "narrative_request": str(state.narrative_request_path),
            "narrative_response": str(state.narrative_response_path),
            "narrative_validation": str(state.narrative_validation_path),
        }
        return "Narrated final message."

    monkeypatch.setattr(
        agent_edit_module,
        "_narrate_final_message",
        _fake_narrative,
    )

    response = agent_edit_module._build_batch_repl_response(state, context)

    assert response["message"] == "Narrated final message."
    assert response["internal_outcome"]["kind"] == "edit"
    assert captured["outcome_kind"] == "edit"
    assert captured["public_outcome"] == response["outcome"]["kind"]
    assert captured["apply_eligibility"] == response["apply_eligibility"]
    assert response["artifacts"]["narrative_context"] == str(state.narrative_context_path)
    assert response["artifacts"]["narrative_request"] == str(state.narrative_request_path)
    narrative_debug = response["debug"]["narrative"]
    assert narrative_debug["attempted"] is False
    assert narrative_debug["selected_source"] == "fallback"
    assert narrative_debug["fallback_reason"] == "deterministic_only"
    assert narrative_debug["final_validation_ok"] is True
    assert (
        narrative_debug["artifacts"]["narrative_validation"]["path"]
        == str(state.narrative_validation_path)
    )


def test_validate_narrative_message_rejects_edit_contradictions() -> None:
    validation = _validate_narrative_message(
        "The graph is unchanged.",
        narrative_context={
            "outcome": {"internal_kind": "edit"},
            "change": {"landed_operation_count": 1, "graph_changed": True},
            "validation": {"passed": True},
        },
    )

    assert validation["ok"] is False
    assert "contradicts_edit_outcome" in validation["issues"]
    assert "claims_no_edit_when_edits_landed" in validation["issues"]


def test_validate_narrative_message_requires_clarify_question_shape() -> None:
    validation = _validate_narrative_message(
        "I need one more detail before continuing.",
        narrative_context={
            "outcome": {
                "internal_kind": "clarify",
                "clarification_question": "Which node should I change?",
            },
            "change": {"landed_operation_count": 0, "graph_changed": False},
            "validation": {"passed": False},
        },
    )

    assert validation["ok"] is False
    assert "clarify_without_question" in validation["issues"]
    assert "clarify_question_missing" in validation["issues"]


def test_synthesize_post_validation_narrative_provider_failure_falls_back_and_persists_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_NARRATOR_ROUTE", "test-route")
    monkeypatch.setenv("VIBECOMFY_NARRATOR_MODEL", "test-model")
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
        lambda **_kwargs: (_ for _ in ()).throw(ProviderError("narrator provider offline")),
    )

    state = _make_state(
        graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
        ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
        batch_field_changes=(
            FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
        ),
        batch_exit_mode="done",
        raw_executor_message="Executor raw success line that must stay non-public.",
        session_dir=tmp_path / "session",
        turn_dir=tmp_path / "turns" / "0001",
        narrative_context_path=Path("narrative_context.json"),
        narrative_request_path=Path("narrative_request.json"),
        narrative_response_path=Path("narrative_response.json"),
        narrative_validation_path=Path("narrative_validation.json"),
        artifacts={},
    )
    state.turn_dir.mkdir(parents=True, exist_ok=True)
    context = TurnContext(session_id="narrative-provider-failure", turn_id="0001")
    for gate_name in context.gate_results:
        context.set_gate(gate_name, True)

    message = _synthesize_post_validation_narrative(
        state,
        context,
        outcome=TurnOutcome.edit(changes=state.batch_field_changes),
        public_outcome="candidate",
    )

    assert "after" in message
    assert message != state.raw_executor_message
    assert state.artifacts == {
        "narrative_context": str(state.turn_dir / "narrative_context.json"),
        "narrative_request": str(state.turn_dir / "narrative_request.json"),
        "narrative_response": str(state.turn_dir / "narrative_response.json"),
        "narrative_validation": str(state.turn_dir / "narrative_validation.json"),
    }

    request_payload = json.loads((state.turn_dir / "narrative_request.json").read_text(encoding="utf-8"))
    validation_payload = json.loads(
        (state.turn_dir / "narrative_validation.json").read_text(encoding="utf-8")
    )
    assert request_payload["attempted"] is True
    assert request_payload["raw_executor_message"] == state.raw_executor_message
    assert validation_payload["fallback_reason"] == "provider_failure"
    assert validation_payload["selected_source"] == "fallback"
    assert validation_payload["final_validation"]["ok"] is True


def test_synthesize_post_validation_narrative_malformed_response_falls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_NARRATOR_ROUTE", "test-route")
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
        lambda **_kwargs: {"json": {}},
    )

    state = _make_state(
        graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
        ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
        batch_field_changes=(
            FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
        ),
        batch_exit_mode="done",
        raw_executor_message="Executor malformed narrator fallback sentinel.",
        session_dir=tmp_path / "session",
        turn_dir=tmp_path / "turns" / "0001",
        narrative_context_path=Path("narrative_context.json"),
        narrative_request_path=Path("narrative_request.json"),
        narrative_response_path=Path("narrative_response.json"),
        narrative_validation_path=Path("narrative_validation.json"),
        artifacts={},
    )
    state.turn_dir.mkdir(parents=True, exist_ok=True)
    context = TurnContext(session_id="narrative-malformed-response", turn_id="0001")
    for gate_name in context.gate_results:
        context.set_gate(gate_name, True)

    message = _synthesize_post_validation_narrative(
        state,
        context,
        outcome=TurnOutcome.edit(changes=state.batch_field_changes),
        public_outcome="candidate",
    )

    validation_payload = json.loads(
        (state.turn_dir / "narrative_validation.json").read_text(encoding="utf-8")
    )
    assert "after" in message
    assert message != state.raw_executor_message
    assert validation_payload["fallback_reason"] == "malformed_response"
    assert validation_payload["selected_source"] == "fallback"
    assert validation_payload["error"]["type"] == "MissingRequiredField"


def test_dev_success_response_failed_execution_plan_has_no_candidate(tmp_path: Path) -> None:
    from vibecomfy.comfy_nodes.agent.edit import _build_dev_success_response

    plan = ExecutionPlan(
        plan_id="dev-plan",
        goal="A required plan-backed condition must pass.",
    )
    evaluation = PlanEvaluation(
        plan_id=plan.plan_id,
        ok=False,
        blocking=True,
        failed_conditions=(
            {
                "condition_id": "dev.condition",
                "severity": "required",
                "message": "Required condition failed.",
            },
        ),
        feedback="plan evaluation blocked: required condition failed.",
    )
    execution_plan_path = tmp_path / "execution_plan.json"
    plan_evaluation_path = tmp_path / "plan_evaluation.json"
    execution_plan_path.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    plan_evaluation_path.write_text(json.dumps(evaluation.to_dict()), encoding="utf-8")
    state = _make_state(
        graph={"nodes": []},
        ui_payload={"nodes": [{"id": 1}]},
        execution_plan=plan,
        plan_evaluation=evaluation,
        execution_plan_path=execution_plan_path,
        plan_evaluation_path=plan_evaluation_path,
        artifacts={},
    )
    context = TurnContext(session_id="dev-plan-fail", turn_id="0001")
    for gate_name in context.gate_results:
        context.set_gate(gate_name, True)

    response = _build_dev_success_response(state, context, contract="full")

    assert response["candidate"] is None
    assert response["outcome"]["kind"] == "noop"
    assert response["apply_eligibility"]["reason"] == "no_candidate"
    assert response["debug"]["gates"]["plan_validate_ok"] is False
    assert response["execution_plan_status"]["failed_condition_ids"] == ["dev.condition"]
    assert response["task_satisfaction"][0]["satisfaction"] == "fail"


def test_handle_agent_edit_batch_repl_queue_blocker_keeps_canvas_apply_true_but_queue_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()

    from vibecomfy.comfy_nodes.agent.contracts import StageResult

    queue_issue = {
        "code": "schema_less_queue_blocker",
        "severity": "error",
        "failure_kind": FailureKind.SCHEMA_LESS_QUEUE_BLOCKER.value,
        "detail": {"node_id": "42"},
        "message": "schema-less queue blocker",
    }
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.queue_stage_result",
        lambda **_kwargs: StageResult(
            stage="queue_validate",
            ok=False,
            blocking=False,
            issues=(queue_issue,),
            gate_updates={"queue_validate_ok": False},
        ),
    )
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
            "session_id": "batch-queue-blocker",
            "max_batches": 4,
            "max_consecutive_errors": 2,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["canvas_apply_allowed"] is True
    assert result["apply_allowed"] is True
    assert result["queue_allowed"] is False
    assert result["apply_eligibility"]["reason"] == "queue_blocked_warning"
    assert result["apply_eligibility"]["warnings"] == ["queue_blocked"]
    assert result["gates"]["queue_validate_ok"] is False
    assert result["report"]["queue_blockers"] == [queue_issue]
    assert any(
        stage["stage"] == "queue_validate" and stage["ok"] is False
        for stage in result["debug"]["stage_snapshots"]
    )


def test_handle_agent_edit_research_route_writes_batch_artifacts_but_no_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Checking whether this edit would help.",
            },
            {
                "batch": "done()",
                "message": "Research complete; no canvas change should be applied.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "research faster save-image workflow options",
            "route": "research",
            "executor_route": "research",
            "session_id": "batch-research-no-candidate",
            "max_batches": 4,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    turn_dir = tmp_path / "batch-research-no-candidate" / "turns" / "0001"
    assert result["ok"] is True
    assert result["apply_allowed"] is False
    assert result["apply_eligibility"]["applyable"] is False
    assert result["eligibility"] == result["apply_eligibility"]
    assert result["candidate"] is None
    assert result["graph_unchanged"] is True
    assert result["no_candidate_reason"] == "route_not_applyable"
    assert result["debug"]["batch_repl"]["turn_count"] == 2
    assert (turn_dir / "messages.jsonl").is_file()
    assert (turn_dir / "model_request.json").is_file()
    assert (turn_dir / "model_response.json").is_file()


def test_handle_agent_edit_batch_repl_noop_does_not_enter_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "set the save prefix to before",
            "session_id": "batch-noop",
            "max_batches": 2,
            "max_consecutive_errors": 1,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: {
            "batch": 'saveimage.filename_prefix = "before"\ndone()',
            "message": "No change needed.",
        },
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "noop"
    assert result["candidate"] is None
    assert result["apply_allowed"] is False
    assert result["canvas_apply_allowed"] is False
    assert result["queue_allowed"] is False
    assert result["apply_eligibility"]["reason"] == "no_candidate"
    assert result["graph_unchanged"] is True
    assert result["debug"]["batch_repl"]["exit_mode"] == "noop"
    assert result["change_details"]["landed_operation_count"] == 0
    assert result["change_details"]["operations"] == []
    assert result["batch_turns"][0]["field_changes"] == []
    assert result["batch_turns"][0]["noop_field_changes"] == [
        {
            "uid": "2",
            "field_path": "filename_prefix",
            "old": "before",
            "new": "before",
        }
    ]
    assert result["message"] == "SaveImage filename_prefix is already before; no change needed."


def test_handle_agent_edit_batch_repl_clarify_after_edit_returns_edit_and_clarify_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Adjusted the save prefix.",
            },
            {
                "batch": 'clarify("Should I also rename the file stem?")',
                "message": "I need one more detail before I continue.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix, then ask if the file stem should change too",
            "session_id": "batch-edit-clarify",
            "max_batches": 4,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["contract_version"] == AGENT_EDIT_TURN_CONTRACT_VERSION
    assert result["clarification_required"] is True
    assert result["graph_unchanged"] is False
    assert result["apply_allowed"] is True
    assert result["apply_eligibility"]["reason"] == "queue_blocked_warning"
    assert result["candidate_graph_hash"] == payload_hash(result["graph"])
    assert result["message"] == "Applied 1 edit. Should I also rename the file stem?"
    assert result["outcome"]["kind"] == "candidate"
    assert result["outcome"]["changes"] == [
        {
            "uid": "2",
            "field_path": "filename_prefix",
            "old": "before",
            "new": "after",
        }
    ]
    assert result["outcome"]["question"] == "Should I also rename the file stem?"
    assert result["outcome"]["clarification"]["message"] == "Should I also rename the file stem?"
    assert result["internal_outcome"]["kind"] == "edit+clarify"
    assert result["batch_turns"][0]["field_changes"] == [
        {
            "uid": "2",
            "field_path": "filename_prefix",
            "old": "before",
            "new": "after",
        }
    ]
    assert result["batch_turns"][1]["field_changes"] == []
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["metadata"]["batch_repl"]["exit_mode"] == "edit_clarify"


def test_handle_agent_edit_batch_repl_edit_clarify_with_unresolved_schema_capability_downgrades(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression guard for the unresolved schema-capability trigger being broadened to
    # edit_clarify (the Moonvalley widget-guess path: agent lands an edit, then
    # appends a clarifying question, while unresolved schema evidence was surfaced).
    # Such a run must downgrade to a clarification and drop the landed
    # edit, NOT report it as a successful candidate. The `bool(resolver_candidates)`
    # conjunct is what keeps the plain edit_clarify case above (real edit + a
    # genuine follow-up question, no unresolved schema evidence) on the candidate path.
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def fake_research(query: str, **kwargs: object) -> ResearchResult:
        return ResearchResult(
            summary="Found registry-backed Hotshot schema evidence.",
            sources=(
                {
                    "source": "comfy-registry",
                    "class_type": "ComfyUI-AnimateDiff-Evolved",
                    "pack": "ComfyUI-AnimateDiff-Evolved",
                    "description": "Expected classes: ADE_AnimateDiffLoaderWithContext",
                    "resolver_candidate": {
                        "pack": {"slug": "ComfyUI-AnimateDiff-Evolved"},
                        "expected_classes": ["ADE_AnimateDiffLoaderWithContext"],
                        "evidence": [{"source": "custom-node-map", "tier": "comfy-manager"}],
                    },
                },
            ),
        )

    research_module = importlib.import_module("vibecomfy.executor.research")
    monkeypatch.setattr(research_module, "research", fake_research)

    responses = iter(
        [
            {
                "batch": 'research("Hotshot XL ComfyUI nodes", sources=["registry"])',
                "message": "Looking for Hotshot workflow precedent.",
            },
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Adjusted the save prefix.",
            },
            {
                "batch": 'clarify("I could not find an authorable Hotshot workflow adaptation from the available evidence.")',
                "message": "I could not find an authorable Hotshot workflow adaptation from the available evidence.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Switch to generating 16 frames with Hotshot",
            "session_id": "batch-edit-clarify-missing-custom-nodes",
            "max_batches": 5,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    # The landed save-prefix edit must be dropped: the request cannot be
    # satisfied without the unresolved schema capability, so this is not a candidate.
    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert result["clarification_required"] is True
    assert result["graph_unchanged"] is True
    assert result["message"] == "I could not find an authorable Hotshot workflow adaptation from the available evidence."


def test_handle_agent_edit_batch_repl_inline_edit_then_clarify_applies_edit_and_keeps_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix, then ask if the file stem should change too",
            "session_id": "batch-inline-edit-clarify",
            "max_batches": 2,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: {
            "batch": 'saveimage.filename_prefix = "after"; clarify("Should I also rename the file stem?")',
            "message": "Adjusted the prefix and need one more detail.",
        },
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["graph_unchanged"] is False
    assert result["apply_allowed"] is True
    assert result["candidate_graph_hash"] == payload_hash(result["graph"])
    assert result["message"] == "Applied 1 edit. Should I also rename the file stem?"
    assert result["outcome"]["kind"] == "candidate"
    assert result["outcome"]["changes"] == [
        {
            "uid": "2",
            "field_path": "filename_prefix",
            "old": "before",
            "new": "after",
        }
    ]
    assert result["outcome"]["question"] == "Should I also rename the file stem?"
    assert result["outcome"]["clarification"]["message"] == "Should I also rename the file stem?"
    assert result["internal_outcome"]["kind"] == "edit+clarify"
    assert len(result["batch_turns"]) == 1
    assert result["batch_turns"][0]["landed_op_count"] == 1
    assert result["batch_turns"][0]["clarification_required"] is True
    assert result["batch_turns"][0]["field_changes"] == result["outcome"]["changes"]


@pytest.mark.parametrize(
    ("session_id", "batch", "expected_prefix"),
    [
        (
            "batch-comment-clarify-text",
            '# clarify("not a call")\nsaveimage.filename_prefix = "after"\ndone()',
            "after",
        ),
        (
            "batch-string-clarify-text",
            'saveimage.filename_prefix = "clarify(\\"not a call\\")"\ndone()',
            'clarify("not a call")',
        ),
    ],
)
def test_handle_agent_edit_batch_repl_ignores_clarify_inside_comments_and_strings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    session_id: str,
    batch: str,
    expected_prefix: str,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix and finish",
            "session_id": session_id,
            "max_batches": 1,
            "max_consecutive_errors": 1,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: {
            "batch": batch,
            "message": "Applied the requested change.",
        },
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"] == {
        "kind": "candidate",
        "changes": [
            {
                "uid": "2",
                "field_path": "filename_prefix",
                "old": "before",
                "new": expected_prefix,
            }
        ],
    }
    assert result["internal_outcome"]["kind"] == "edit"
    assert not result.get("clarification_required", False)
    assert result["batch_turns"][0]["batch"] == batch
    assert "clarification_required" not in result["batch_turns"][0]
    assert result["batch_turns"][0]["field_changes"] == result["outcome"]["changes"]


@pytest.mark.parametrize(
    ("session_id", "batch", "failure_kind", "diagnostic_code"),
    [
        (
            "batch-non-terminal-clarify",
            'clarify("first")\nsaveimage.filename_prefix = "after"',
            FailureKind.MODEL_MISTAKE.value,
            "unsupported_query_call",
        ),
        (
            "batch-nested-clarify",
            'saveimage.filename_prefix = str(clarify("nested"))',
            FailureKind.UNREPRESENTABLE.value,
            "nested_call_not_allowed",
        ),
        (
            "batch-malformed-clarify",
            'saveimage.filename_prefix = "after"; clarify("unterminated"',
            FailureKind.MODEL_MISTAKE.value,
            "batch_syntax_error",
        ),
    ],
)
def test_handle_agent_edit_batch_repl_rejects_malformed_or_non_terminal_clarify_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    session_id: str,
    batch: str,
    failure_kind: str,
    diagnostic_code: str,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix and finish",
            "session_id": session_id,
            "max_batches": 1,
            "max_consecutive_errors": 1,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: {
            "batch": batch,
            "message": "Tried to finish the request.",
        },
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=failure_kind,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    _assert_product_failure_contract(
        result,
        failure_kind=failure_kind,
        stage="agent_batch",
    )
    assert not result.get("clarification_required", False)
    assert "question" not in result["outcome"]
    assert result["internal_outcome"]["kind"] == "failure"

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["metadata"]["batch_repl"]["exit_mode"] == "budget"
    response_turns = json.loads(
        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
    )["turns"]
    turn0 = response_turns[0]["batch_result"]
    assert turn0["batch"] == batch
    assert "clarification_required" not in turn0
    assert any(
        diagnostic["code"] == diagnostic_code
        for diagnostic in (
            list(turn0.get("diagnostics") or [])
            + [
                diagnostic
                for statement in turn0.get("statements") or []
                for diagnostic in statement.get("diagnostics") or []
            ]
        )
    )


def test_handle_agent_edit_batch_repl_refused_done_skips_emit_and_budget_failure_emits_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    events: list[tuple[str, dict[str, object], str | None]] = []
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit._ws_send",
        lambda event, payload, *, client_id=None: events.append((event, payload, client_id)),
    )
    responses = iter(
        [
            {
                "batch": "done()",
                "message": "No changes needed.",
            },
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Applied the requested rename.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "rename the save prefix",
            "session_id": "batch-refused-done-budget",
            "max_batches": 2,
            "max_consecutive_errors": 2,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
        client_id="client-budget",
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.MODEL_MISTAKE.value,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    issue = result["agent_failure_context"]["issues"][0]
    assert issue["code"] == "batch_budget_exhausted"
    assert [payload["status"] for _, payload, _ in events] == [
        "in_progress",
        "budget_exhausted",
    ]
    assert [payload["turn_number"] for _, payload, _ in events] == [1, 1]
    assert all(event == "vibecomfy.agent_edit.turn" for event, _, _ in events)
    assert all(client_id == "client-budget" for _, _, client_id in events)
    assert events[0][1]["message"] == "Applied the requested rename."
    assert events[1][1]["message"] == "Applied the requested rename."


def test_handle_agent_edit_batch_repl_applies_assignment_add_and_rewire(
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
            "ImageScaleBy": NodeSchema(
                class_type="ImageScaleBy",
                pack=None,
                inputs={
                    "image": InputSpec("IMAGE", required=True),
                    "scale_by": InputSpec("FLOAT"),
                },
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

    def _fake_batch_client(_messages):
        return {
            "message": "Inserted the scale node and rewired the save input.",
            "batch": "\n".join(
                [
                    "upscaled = ImageScaleBy(image=loadimage.image, scale_by=2.0, near=loadimage)",
                    "saveimage.images = upscaled.IMAGE",
                    "done()",
                ]
            ),
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "Add an upscaling step after the image load and wire it into the save node",
            "session_id": "batch-assignment-upscale",
            "max_batches": 2,
            "max_consecutive_errors": 1,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["apply_allowed"] is True
    assert result["done_summary"].startswith("Gate A passed:")
    assert result["outcome"] == {
        "kind": "candidate",
        "changes": [
            {
                "uid": "2",
                "field_path": "images",
                "old": {"uid": "1", "output_slot": 2, "scope_path": ""},
                "new": {"uid": "n1", "output_slot": "IMAGE", "scope_path": ""},
            }
        ],
    }
    assert result["internal_outcome"]["kind"] == "edit"

    nodes = result["graph"]["nodes"]
    scale_node = next(node for node in nodes if node["type"] == "ImageScaleBy")
    save_node = next(node for node in nodes if node["type"] == "SaveImage")
    load_node = next(node for node in nodes if node["type"] == "LoadImage")

    links = result["graph"]["links"]
    image_to_scale = next(
        link
        for link in links
        if link[1] == load_node["id"] and link[3] == scale_node["id"]
    )
    scale_to_save = next(
        link
        for link in links
        if link[1] == scale_node["id"] and link[3] == save_node["id"]
    )

    assert image_to_scale[5] == "IMAGE"
    assert scale_to_save[5] == "IMAGE"
    assert 2.0 in scale_node["widgets_values"]

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    turn0 = json.loads(
        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
    )["turns"][0]["batch_result"]
    assert turn0["landed_op_count"] == 2
    assert turn0["field_changes"] == [
        {
            "uid": "2",
            "field_path": "images",
            "old": {"uid": "1", "output_slot": 2, "scope_path": ""},
            "new": {"uid": "n1", "output_slot": "IMAGE", "scope_path": ""},
        }
    ]
    assert [item["op_kind"] for item in turn0["statements"]] == [
        "node_call",
        "upsert_link",
        "done",
    ]


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
    assert result["queue_allowed"] is True
    assert result["gates"]["queue_validate_ok"] is True
    assert result["done_summary"].startswith("Gate A passed:")
    assert "Rewired saveimage.images" in result["done_summary"]
    assert "saveimage.filename_prefix" in result["done_summary"]
    assert result["outcome"] == {
        "kind": "candidate",
        "changes": [
            {
                "uid": "3",
                "field_path": "images",
                "old": {"uid": "2", "output_slot": 3, "scope_path": ""},
                "new": {"uid": "1", "output_slot": "image", "scope_path": ""},
            },
            {
                "uid": "3",
                "field_path": "filename_prefix",
                "old": "before",
                "new": "after",
            }
        ],
    }
    assert result["internal_outcome"]["kind"] == "edit"
    assert len(captured_messages) == 4
    assert "Node variable index:" in captured_messages[1][1]["content"]
    assert "loadimage = LoadImage" in captured_messages[1][1]["content"]
    assert "saveimage = SaveImage" in captured_messages[1][1]["content"]
    assert "Previous agent message:" in captured_messages[1][1]["content"]
    assert "Bypassed the passthrough output." in captured_messages[1][1]["content"]
    assert captured_messages[1][1]["content"].count("Budget: 4 turn(s) remaining out of 5.") == 1
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
    assert response_turns[1]["batch_result"]["field_changes"] == []
    assert response_turns[2]["batch_result"]["batch_ok"] is True
    assert response_turns[2]["batch_result"]["field_changes"] == [
        {
            "uid": "3",
            "field_path": "filename_prefix",
            "old": "before",
            "new": "after",
        }
    ]


def test_handle_agent_edit_batch_repl_reincludes_render_after_search_only_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    captured_messages: list[list[dict[str, str]]] = []
    responses = iter(
        [
            {
                "batch": 'search(focus_types=["SaveImage"])',
                "message": "I checked the SaveImage signature.",
            },
            {
                "batch": "done()",
                "message": "No graph change is needed.",
            },
        ]
    )

    def _fake_batch_client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_messages.append(messages)
        return next(responses)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "inspect save image and stop",
            "session_id": "batch-search-only",
            "max_batches": 2,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert len(captured_messages) == 2
    second_user = captured_messages[1][1]["content"]
    assert "Current scratchpad Python (full render):" in second_user
    assert "saveimage = SaveImage" in second_user
    assert "Node variable index:" in second_user
    assert "Previous agent message:" in second_user
    assert "I checked the SaveImage signature." in second_user
    assert second_user.count("Budget: 1 turn(s) remaining out of 2.") == 1


def test_handle_agent_edit_batch_repl_repeated_search_only_turns_keep_render_previous_message_and_index(
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
            "ImageScaleBy": NodeSchema(
                class_type="ImageScaleBy",
                pack=None,
                inputs={
                    "image": InputSpec("IMAGE", required=True),
                    "scale_by": InputSpec("FLOAT", required=False, default=1.0),
                },
                outputs=[OutputSpec("IMAGE", "IMAGE")],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    captured_messages: list[list[dict[str, str]]] = []
    responses = iter(
        [
            {
                "batch": 'search(focus_types=["SaveImage"])',
                "message": "I checked the SaveImage signature.",
            },
            {
                "batch": 'search(focus_types=["ImageScaleBy"])',
                "message": "I checked the ImageScaleBy signature next.",
            },
            {
                "batch": "done()",
                "message": "No graph change is needed.",
            },
        ]
    )

    def _fake_batch_client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_messages.append(messages)
        return next(responses)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "inspect two node signatures and then stop",
            "session_id": "batch-search-only-repeat",
            "max_batches": 3,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert len(captured_messages) == 3

    second_user = captured_messages[1][1]["content"]
    third_user = captured_messages[2][1]["content"]
    for user_msg, previous_message, budget_line in (
        (
            second_user,
            "I checked the SaveImage signature.",
            "Budget: 2 turn(s) remaining out of 3.",
        ),
        (
            third_user,
            "I checked the ImageScaleBy signature next.",
            "Budget: 1 turn(s) remaining out of 3.",
        ),
    ):
        assert "Current scratchpad Python (full render):" in user_msg
        assert "saveimage = SaveImage" in user_msg
        assert "Node variable index:" in user_msg
        assert "loadimage = LoadImage" in user_msg
        assert "saveimage = SaveImage" in user_msg
        assert "Previous agent message:" in user_msg
        assert previous_message in user_msg
        assert budget_line in user_msg


def test_handle_agent_edit_batch_repl_budget_exhaustion_reports_final_status_metadata_and_budget_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    events: list[tuple[str, dict[str, object], str | None]] = []
    captured_messages: list[list[dict[str, str]]] = []

    def _capture_ws_send(
        event: str,
        payload: dict[str, object],
        *,
        client_id: str | None = None,
    ) -> None:
        events.append((event, payload, client_id))

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit._ws_send", _capture_ws_send)

    responses = iter(
        [
            {
                "batch": 'search(focus_types=["SaveImage"])',
                "message": "I inspected SaveImage first.",
            },
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "I applied the rename but did not commit yet.",
            },
        ]
    )

    def _fake_batch_client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_messages.append(messages)
        return next(responses)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "rename the save prefix after checking the node signature",
            "session_id": "batch-budget-metadata",
            "max_batches": 2,
            "max_consecutive_errors": 2,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
        client_id="client-budget-meta",
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.MODEL_MISTAKE.value,
        stage="agent_batch",
        audit_ref_expected=True,
    )
    assert len(captured_messages) == 2
    assert "Budget: 2 turn(s) remaining out of 2." in captured_messages[0][0]["content"]
    assert "Budget: 1 turn(s) remaining out of 2." in captured_messages[1][1]["content"]
    assert [payload["status"] for _, payload, _ in events] == [
        "in_progress",
        "in_progress",
        "budget_exhausted",
    ]
    final_payload = events[-1][1]
    assert final_payload["exit_mode"] == "budget"
    assert final_payload["budget"] == {
        "remaining_batches": 0,
        "consecutive_errors": 0,
    }

    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    batch_meta = audit["metadata"]["batch_repl"]
    assert batch_meta["turn_count"] == 2
    assert batch_meta["exit_mode"] == "budget"
    assert batch_meta["final_summary"] == "Stopped after 2 turn(s); 0 turn(s) remaining."
    assert batch_meta["budget_state"]["remaining_batches"] == 0
    assert batch_meta["budget_state"]["consecutive_errors"] == 0
    request_turns = json.loads(
        Path(audit["artifacts"]["model_request"]["path"]).read_text(encoding="utf-8")
    )["turns"]
    assert [turn["budget_remaining"] for turn in request_turns] == [2, 1]


def test_handle_agent_edit_batch_repl_updates_next_prompt_index_after_node_add_and_remove(
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
            "ImageScaleBy": NodeSchema(
                class_type="ImageScaleBy",
                pack=None,
                inputs={
                    "image": InputSpec("IMAGE", required=True),
                    "scale_by": InputSpec("FLOAT", required=False, default=1.0),
                },
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

    wf = VibeWorkflow("batch-index-refresh", WorkflowSource("batch-index-refresh"))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    wf.nodes["2"] = VibeNode("2", "PassThroughImage")
    wf.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "before"})
    wf.connect("1.0", "2.image")
    wf.connect("2.0", "3.images")
    graph = emit_ui_json(wf, schema_provider=provider)

    captured_messages: list[list[dict[str, str]]] = []
    responses = iter(
        [
            {
                "batch": "\n".join(
                    [
                        "upscaled = ImageScaleBy(image=loadimage.image, scale_by=2.0, near=loadimage)",
                        "saveimage.images = upscaled.IMAGE",
                        "del passthroughimage",
                    ]
                ),
                "message": "I inserted the upscale node and removed the passthrough.",
            },
            {
                "batch": "done()",
                "message": "Ready to commit the candidate.",
            },
        ]
    )

    def _fake_batch_client(messages: list[dict[str, str]]) -> dict[str, str]:
        captured_messages.append(messages)
        return next(responses)

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "replace the passthrough with an upscale node",
            "session_id": "batch-index-refresh",
            "max_batches": 2,
        },
        schema_provider=provider,
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert len(captured_messages) == 2
    second_user = captured_messages[1][1]["content"]
    node_index = second_user.split("Node variable index:\n```\n", 1)[1].split("\n```", 1)[0]
    assert "upscaled = ImageScaleBy" in node_index
    assert "loadimage = LoadImage" in node_index
    assert "saveimage = SaveImage" in node_index
    assert "passthroughimage = PassThroughImage" not in node_index


def test_handle_agent_edit_validates_lowered_copy_after_load_python(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
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

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit._stage_validate", _validate)
    monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit._stage_emit", _emit)
    monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit._stage_summarize", _summarize)

    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent.audit import write_audit as real_write_audit

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
    _use_dev_full(monkeypatch)
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
    _use_dev_full(monkeypatch)
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
    assert result["apply_eligibility"]["reason"] == "applyable"


def test_handle_agent_edit_audit_threads_complete_lowering_metadata_and_keeps_queue_unblocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
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
    _assert_product_failure_contract(
        result,
        failure_kind=FailureKind.MISSING_REQUIRED_FIELD.value,
        stage="ingest",
    )
    assert result["agent_failure_context"]["explanation"] == explanation
    assert result["retryable"] is True
    assert "turn_id" not in result


def test_handle_agent_edit_batch_repl_audit_failure_includes_typed_product_failure_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit._stage_audit",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
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
            "session_id": "batch-audit-failure",
            "max_batches": 4,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    _assert_failure_defaults(
        result,
        kind=FailureKind.AUDIT_WRITE_FAILURE.value,
        stage="audit",
        audit_ref_expected=False,
    )
    _assert_product_failure_contract(
        result,
        failure_kind=FailureKind.AUDIT_WRITE_FAILURE.value,
        stage="audit",
    )
    assert result["audit_error"] == "disk full"


# ── T7: focused agent-edit provenance & hostile-rejection tests ──────────


def test_agent_edit_nodes_never_user_confirmed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _headless_gate_context: GateContext,
) -> None:
    _use_dev_full(monkeypatch)
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
    monkeypatch: pytest.MonkeyPatch,
    _headless_gate_context: GateContext,
) -> None:
    _use_dev_full(monkeypatch)
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
    monkeypatch: pytest.MonkeyPatch,
    _headless_gate_context: GateContext,
) -> None:
    _use_dev_full(monkeypatch)
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
    monkeypatch: pytest.MonkeyPatch,
    _headless_gate_context: GateContext,
) -> None:
    _use_dev_full(monkeypatch)
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
    monkeypatch: pytest.MonkeyPatch,
    _headless_gate_context: GateContext,
) -> None:
    _use_dev_full(monkeypatch)
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
    _use_dev_full(monkeypatch)
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    def _boom(*_args, **_kwargs):
        raise RuntimeError("convert exploded")

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit._stage_convert", _boom)

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
    _use_dev_full(monkeypatch)
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    from vibecomfy.comfy_nodes.agent import provider as provider_mod

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit.run_agent_turn", provider_mod.run_agent_turn)
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
    _use_dev_full(monkeypatch)
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
            from vibecomfy.comfy_nodes.agent import provider as provider_mod
            return provider_mod._normalize_agent_response(  # type: ignore[attr-defined]
                _payload,
                route="arnold",
                model="agent-edit",
            )

        monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit.run_agent_turn", _fake_run_agent_turn)
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
    _use_dev_full(monkeypatch)
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    def _boom(*_args, **_kwargs):
        raise exc_factory()

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit._stage_convert", _boom)

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
    _use_dev_full(monkeypatch)
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
        "vibecomfy.comfy_nodes.agent.edit.load_agent_generated_scratchpad", _reject,
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
    _use_dev_full(monkeypatch)
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    def _boom(*_args, **_kwargs):
        raise exc

    monkeypatch.setattr("vibecomfy.comfy_nodes.agent.edit._stage_emit", _boom)

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
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
    assert conflict["agent_failure_context"]["idempotency_key"] == "same-key"
    assert conflict["debug"]["failure"]["agent_failure_context"] == conflict[
        "agent_failure_context"
    ]
    assert "audit_ref" not in conflict["debug"]["failure"]
    assert "audit_ref" not in conflict["debug"]
    audit = json.loads(Path(conflict["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["failure"]["kind"] == FailureKind.STALE_STATE_MISMATCH.value
    assert (
        audit["failure"]["agent_failure_context"]["idempotency_key"]
        == "same-key"
    )


def test_agent_edit_stale_submit_auto_rebaselines_at_ingest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

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
    assert first["candidate_structural_graph_hash"] == structural_graph_hash(first["graph"])
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
    assert accepted["baseline_graph_hash"] == structural_graph_hash(first["graph"])
    assert accepted["baseline_graph_hash_kind"] == "structural"

    # The canvas now differs from the accepted baseline. Submit AUTO-REBASELINES
    # to the live canvas instead of blocking: the submitted graph is authoritative
    # on submit, so the edit proceeds and produces a candidate rather than failing
    # with STALE_STATE_MISMATCH. (The stale-state guard remains on the APPLY path.)
    rebaselined = handle_agent_edit(
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

    assert rebaselined["ok"] is True
    assert "agent_failure_context" not in rebaselined
    assert rebaselined["submit_graph_hash"] == payload_hash(original_graph)
    assert rebaselined["candidate_graph_hash"] == payload_hash(rebaselined["graph"])
    audit = json.loads(Path(rebaselined["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["gates"]["state_match_ok"] is True


def test_agent_edit_submit_after_accept_allows_only_volatile_reserialize_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

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
            "session_id": "submit-after-accept",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )
    assert first["ok"] is True

    accepted = _handle_agent_edit_accept(
        {
            "session_id": "submit-after-accept",
            "turn_id": first["turn_id"],
            "client_graph_hash": payload_hash(original_graph),
            "idempotency_key": "accept-first",
        },
        session_root=tmp_path,
    )
    assert accepted["ok"] is True, accepted

    reserialized = _with_volatile_canvas_drift(first["graph"])
    assert payload_hash(reserialized) != payload_hash(first["graph"])
    assert structural_graph_hash(reserialized) == structural_graph_hash(first["graph"])

    second = handle_agent_edit(
        {
            "graph": reserialized,
            "task": "change the save prefix to final",
            "session_id": "submit-after-accept",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace("after", "final", "Changed the save prefix."),
        session_root=tmp_path,
    )
    if second["ok"] is False:
        assert second["kind"] != FailureKind.STALE_STATE_MISMATCH.value, second
        assert second["stage"] != "ingest", second
    else:
        assert second["baseline_graph_hash"] == structural_graph_hash(first["graph"])
        assert second["submit_structural_graph_hash"] == structural_graph_hash(first["graph"])


def test_agent_edit_submit_after_accept_does_not_stale_block_live_canvas_divergence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

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
            "session_id": "submit-after-accept-mutated",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )
    assert first["ok"] is True

    accepted = _handle_agent_edit_accept(
        {
            "session_id": "submit-after-accept-mutated",
            "turn_id": first["turn_id"],
            "client_graph_hash": payload_hash(original_graph),
            "idempotency_key": "accept-first-mutated",
        },
        session_root=tmp_path,
    )
    assert accepted["ok"] is True, accepted

    mutated = _with_first_widget_mutated(first["graph"], "manual-divergence")
    assert structural_graph_hash(mutated) != structural_graph_hash(first["graph"])

    stale = handle_agent_edit(
        {
            "graph": mutated,
            "task": "change the save prefix to final",
            "session_id": "submit-after-accept-mutated",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace("after", "final", "Changed the save prefix."),
        session_root=tmp_path,
    )

    if stale["ok"] is False:
        assert stale["kind"] != FailureKind.STALE_STATE_MISMATCH.value, stale
        assert stale["stage"] != "ingest", stale
    else:
        assert stale["baseline_graph_hash"] == structural_graph_hash(first["graph"])
        assert stale["submit_structural_graph_hash"] == structural_graph_hash(mutated)


def test_agent_edit_queue_blockers_keep_canvas_apply_true_but_queue_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    from vibecomfy.comfy_nodes.agent.contracts import StageResult

    queue_issue = {
        "code": "schema_less_queue_blocker",
        "severity": "error",
        "failure_kind": FailureKind.SCHEMA_LESS_QUEUE_BLOCKER.value,
        "detail": {"node_id": "42"},
        "message": "schema-less queue blocker",
    }
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.queue_stage_result",
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
    assert result["apply_eligibility"]["reason"] == "queue_blocked_warning"
    assert result["apply_eligibility"]["warnings"] == ["queue_blocked"]
    assert result["gates"]["queue_validate_ok"] is False
    assert result["audit_ref"]["path"]
    audit = json.loads(Path(result["audit_ref"]["path"]).read_text(encoding="utf-8"))
    assert audit["turn_state"] == "candidate"


def test_agent_edit_unknown_transition_audit_failure_does_not_rollback_session_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
    from vibecomfy.comfy_nodes.agent import audit as agent_audit, edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent.session import read_state

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
    from vibecomfy.comfy_nodes.agent.session import read_state

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
    _use_dev_full(monkeypatch)
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit._stage_audit",
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
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit

    missing_task = _handle_agent_edit({"graph": _ui_graph()}, session_root=tmp_path)
    _assert_failure_defaults(
        missing_task,
        kind=FailureKind.MISSING_REQUIRED_FIELD.value,
        stage="ingest",
        audit_ref_expected=False,
    )
    assert "ValueError" not in json.dumps(missing_task, sort_keys=True)

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.routes.handle_agent_edit",
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
    from vibecomfy.comfy_nodes.agent.contracts import failure_envelope
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit

    classified = failure_envelope(
        FailureKind.PROVIDER_ERROR,
        "agent_response",
        agent_failure_context={"explanation": "provider unavailable"},
    ).to_dict()
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.routes.handle_agent_edit",
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


def test_agent_edit_route_sanitizes_pure_clarify_candidate_and_apply_leaks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.routes.handle_agent_edit",
        lambda *_args, **_kwargs: {
            "ok": True,
            "message": "Which node should change?",
            "outcome": {"kind": "clarify", "question": "Which node should change?"},
            "candidate": {"graph": {"nodes": [{"id": 1}]}},
            "graph": {"nodes": [{"id": 1}]},
            "candidate_graph": {"nodes": [{"id": 1}]},
            "candidate_graph_hash": "leaked",
            "apply_eligibility": {"applyable": True},
            "eligibility": {"applyable": True},
            "apply_allowed": True,
            "canvas_apply_allowed": True,
            "queue_allowed": True,
        },
    )

    result = _handle_agent_edit(
        {"graph": _ui_graph(), "task": "maybe change a node"},
        session_root=tmp_path,
    )

    assert result["outcome"]["kind"] == "clarify"
    assert result["message"] == "Which node should change?"
    assert result["outcome"]["question"] == result["message"]
    for forbidden in (
        "candidate",
        "graph",
        "candidate_graph",
        "candidate_graph_hash",
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
    ):
        assert forbidden not in result


def test_agent_executor_route_sanitizes_clarify_candidate_and_apply_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_executor_submit

    class _ClarifyResult:
        def to_dict(self) -> dict[str, object]:
            return {
                "ok": True,
                "route": "clarify",
                "reply": "Which option should I use?",
                "candidate": {"graph": {"nodes": [{"id": 1}]}},
                "graph": {"nodes": [{"id": 1}]},
                "candidate_graph": {"nodes": [{"id": 1}]},
                "candidate_graph_hash": "leaked",
                "apply_eligible": True,
            }

    monkeypatch.setattr("vibecomfy.executor.core.run_executor", lambda *_args, **_kwargs: _ClarifyResult())

    result, status = _handle_agent_executor_submit({"query": "maybe edit this", "graph": _ui_graph()})

    assert status == 200
    assert result["route"] == "clarify"
    assert result["outcome"]["kind"] == "clarify"
    assert result["reply"] == "Which option should I use?"
    assert result["message"] == result["reply"]
    for forbidden in (
        "candidate",
        "graph",
        "candidate_graph",
        "candidate_graph_hash",
        "apply_eligible",
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
    ):
        assert forbidden not in result


def test_agent_executor_route_sanitizes_nonapplyable_adapt_outcome_candidate_leaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_executor_submit

    class _RequiresCustomNodesResult:
        def to_dict(self) -> dict[str, object]:
            return {
                "ok": True,
                "route": "adapt",
                "reply": "Hotshot schema evidence was not grounded.",
                "outcome": {
                    "kind": "requires_custom_nodes",
                    "candidates": [
                        {
                            "pack": {"slug": "ComfyUI-AnimateDiff-Evolved"},
                            "expected_classes": ["ADE_UseEvolvedSampling"],
                        }
                    ],
                },
                "candidate": {"graph": {"nodes": [{"id": 1}]}},
                "graph": {"nodes": [{"id": 1}]},
                "candidate_graph": {"nodes": [{"id": 1}]},
                "candidate_graph_hash": "leaked",
                "apply_eligible": True,
                "apply_eligibility": {"applyable": True},
                "eligibility": {"applyable": True},
                "apply_allowed": True,
                "canvas_apply_allowed": True,
                "queue_allowed": True,
            }

    monkeypatch.setattr("vibecomfy.executor.core.run_executor", lambda *_args, **_kwargs: _RequiresCustomNodesResult())

    result, status = _handle_agent_executor_submit({"query": "Switch to Hotshot", "graph": _ui_graph()})

    assert status == 200
    assert result["route"] == "adapt"
    assert result["outcome"]["kind"] == "requires_custom_nodes"
    assert result["outcome"]["candidates"][0]["pack"]["slug"] == "ComfyUI-AnimateDiff-Evolved"
    for forbidden in (
        "candidate",
        "graph",
        "candidate_graph",
        "candidate_graph_hash",
        "apply_eligible",
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
    ):
        assert forbidden not in result


def test_agent_edit_action_routes_accept_reject_idempotency_and_audit(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent.session import read_state
    from vibecomfy.comfy_nodes.agent.routes import (
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
    assert accepted["outcome"]["kind"] == "noop"
    assert accepted["canvas_apply_allowed"] is False
    assert accepted["apply_allowed"] is False
    assert accepted["queue_allowed"] is False
    assert accepted["apply_eligibility"]["reason"] == "superseded"
    assert accepted["baseline_turn_id"] == turn_id
    assert accepted["submit_graph_hash"] == submit_graph_hash
    assert accepted["candidate_graph_hash"] == candidate_graph_hash
    assert accepted["baseline_graph_hash"] == accepted["candidate_structural_graph_hash"]
    assert accepted["baseline_graph_hash_kind"] == "structural"
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
    assert conflicting_reject["outcome"]["kind"] == "error"

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
    from vibecomfy.comfy_nodes.agent.session import (
        allocate_turn,
        record_idempotent_response,
    )
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

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
    assert stale["rebaseline_recovery"]["action"] == "rebaseline"
    issues = stale["agent_failure_context"]["issues"]
    assert issues[0]["rebaseline_recovery"] == stale["rebaseline_recovery"]
    assert stale["outcome"]["rebaseline_recovery"] == stale["rebaseline_recovery"]

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
    assert accepted["outcome"]["kind"] == "noop"


def test_agent_edit_v2_accept_requires_server_hash_candidate_hash_and_live_token(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent.session import (
        allocate_turn,
        record_idempotent_response,
    )
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

    graph = {"nodes": [{"id": 1, "type": "SaveImage", "widgets_values": ["v2"]}], "links": []}
    candidate_graph = {
        "nodes": [{"id": 1, "type": "SaveImage", "widgets_values": ["v2-candidate"]}],
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
    (allocation.turn_dir / "request.json").write_text(
        json.dumps(
            {
                "graph": graph,
                "task": "edit v2",
                "client_graph_hash": client_hash,
                "client_live_canvas_token": live_token,
            }
        ),
        encoding="utf-8",
    )
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
            "delta_ops": [
                {
                    "op": "set_node_field",
                    "target": ["nodes", "1", "widgets_values.0"],
                    "value": "v2-candidate",
                }
            ],
        },
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
    )
    submit_hash = payload_hash(graph)
    candidate_hash = payload_hash(candidate_graph)

    wrong_candidate = _handle_agent_edit_accept(
        {
            "session_id": "s-v2-lock",
            "turn_id": turn_id,
            "client_graph_hash": client_hash,
            "live_graph": graph,
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
            "live_graph": graph,
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
            "live_graph": graph,
            "client_live_canvas_token": "live:rev:2:browser-hash-v2",
            "submit_graph_hash": submit_hash,
            "candidate_graph_hash": candidate_hash,
            "idempotency_key": "accept-v2-ok",
        },
        session_root=tmp_path,
    )
    assert accepted["ok"] is True, accepted
    assert accepted["baseline_graph_hash"] == structural_graph_hash(candidate_graph)
    assert accepted["outcome"]["kind"] == "noop"
    assert accepted["diagnostics"][0]["code"] == "client_live_canvas_token_mismatch"
    assert (
        accepted["diagnostics"][0]["detail"]["client_live_canvas_token"]
        == "live:rev:2:browser-hash-v2"
    )
    assert accepted["apply_eligibility"]["reason"] == "superseded"


def test_agent_edit_accept_route_forwards_live_graph_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import routes

    live_graph = {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []}
    captured: dict[str, object] = {}

    def fake_accept_turn(**kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "action": "accept",
            "session_id": "s-live-route",
            "turn_id": "0001",
            "baseline_turn_id": "0000",
            "baseline_graph_hash": "baseline-structural-hash",
            "baseline_graph_hash_kind": "structural",
            "accepted_state": "accepted",
            "submit_graph_hash": "submit-ui-hash",
            "candidate_graph_hash": "candidate-ui-hash",
        }

    monkeypatch.setattr(routes, "accept_turn", fake_accept_turn)

    response = routes._handle_agent_edit_accept(
        {
            "session_id": "s-live-route",
            "turn_id": "0001",
            "client_graph_hash": "live-ui-hash",
            "live_graph": live_graph,
            "submit_graph_hash": "submit-ui-hash",
            "candidate_graph_hash": "candidate-ui-hash",
            "idempotency_key": "accept-live-graph",
        },
        session_root=tmp_path,
    )

    assert response["ok"] is True
    assert captured["client_graph_hash"] == "live-ui-hash"
    assert captured["request_payload"]["live_graph"] == live_graph
    assert "graph" not in captured["request_payload"]


def test_agent_edit_v2_accept_fails_closed_without_live_graph(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent.session import (
        allocate_turn,
        record_idempotent_response,
    )
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

    graph = {"nodes": [{"id": 1, "type": "SaveImage", "widgets_values": ["v2"]}], "links": []}
    candidate_graph = {
        "nodes": [{"id": 2, "type": "SaveImage", "widgets_values": ["v2-candidate"]}],
        "links": [],
    }
    client_hash = "browser-hash-v2"
    live_token = "live:rev:2:browser-hash-v2"
    allocation = allocate_turn(
        session_root=tmp_path,
        session_id="s-v2-no-live-graph",
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
        session_id="s-v2-no-live-graph",
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

    result = _handle_agent_edit_accept(
        {
            "session_id": "s-v2-no-live-graph",
            "turn_id": turn_id,
            "client_graph_hash": client_hash,
            "client_live_canvas_token": live_token,
            "submit_graph_hash": submit_hash,
            "candidate_graph_hash": candidate_hash,
            "idempotency_key": "accept-v2-no-live-graph",
        },
        session_root=tmp_path,
    )
    assert result["ok"] is False, result
    assert result["kind"] == FailureKind.MISSING_REQUIRED_FIELD.value
    assert "live_graph" in result["agent_failure_context"]["explanation"]


def test_agent_edit_rebaseline_route_returns_no_candidate_apply_eligibility(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_rebaseline

    graph = _ui_graph()

    result = _handle_agent_edit_rebaseline(
        {
            "session_id": "reb-eligibility",
            "graph": graph,
            "reason": "continue_from_canvas",
            "last_known_baseline_graph_hash": None,
            "idempotency_key": "reb-1",
        },
        session_root=tmp_path,
    )

    assert result["ok"] is True, result
    assert result["action"] == "rebaseline"
    assert result["outcome"]["kind"] == "noop"
    assert result["canvas_apply_allowed"] is False
    assert result["apply_allowed"] is False
    assert result["queue_allowed"] is False
    assert result["apply_eligibility"]["reason"] == "no_candidate"
    persisted = json.loads(
        (
            tmp_path
            / "reb-eligibility"
            / "_rebaseline"
            / result["rebaseline_id"]
            / "response.json"
        ).read_text(encoding="utf-8")
    )
    assert persisted["action"] == "rebaseline"
    assert persisted["baseline_graph_hash"] == result["baseline_graph_hash"]
    assert persisted["baseline_graph_hash_kind"] == "structural"
    assert persisted["baseline_graph_source_path"] == result["baseline_graph_source_path"]
    assert persisted["computed_structural_graph_hash"] == result["baseline_graph_hash"]
    for legacy_key in (
        "apply_eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
        "audit_ref",
        "debug",
    ):
        assert legacy_key not in persisted


def test_agent_edit_action_routes_reject_candidates_without_baseline_update(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent.session import read_state
    from vibecomfy.comfy_nodes.agent.edit import read_session_chat
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_reject

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
    assert rejected["outcome"]["kind"] == "noop"
    assert rejected["canvas_apply_allowed"] is False
    assert rejected["apply_allowed"] is False
    assert rejected["queue_allowed"] is False
    assert rejected["apply_eligibility"]["reason"] == "superseded"
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
    chat = read_session_chat(tmp_path, "s2")
    assert chat["latest_candidate"] is None


def test_agent_edit_action_routes_cover_replay_conflict_state_mismatch_and_audit_redaction(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent.session import read_state
    from vibecomfy.comfy_nodes.agent.routes import (
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
    assert accepted["outcome"]["kind"] == "noop"
    assert accepted["baseline_turn_id"] == accepted_turn_id
    assert accepted["baseline_graph_hash"] == accepted["candidate_structural_graph_hash"]
    assert repeated_accept["ok"] is False
    assert repeated_accept["kind"] == FailureKind.STALE_STATE_MISMATCH.value
    assert repeated_accept["outcome"]["kind"] == "error"
    assert repeated_accept["agent_failure_context"]["reason"] == "structural_baseline_cas_mismatch"
    assert accept_key_conflict["ok"] is False
    assert accept_key_conflict["kind"] == FailureKind.EDITOR_AHEAD_CONFLICT.value
    assert accept_key_conflict["outcome"]["kind"] == "error"
    assert rejecting_accepted["ok"] is False
    assert rejecting_accepted["kind"] == FailureKind.EDITOR_AHEAD_CONFLICT.value
    assert rejecting_accepted["outcome"]["kind"] == "error"

    assert rejected["ok"] is True
    assert rejected["outcome"]["kind"] == "noop"
    assert rejected["baseline_turn_id"] == accepted_turn_id
    assert rejected["baseline_graph_hash"] == accepted["candidate_structural_graph_hash"]
    assert repeated_reject["ok"] is True
    assert repeated_reject["baseline_turn_id"] == accepted_turn_id
    assert repeated_reject["baseline_graph_hash"] == accepted["candidate_structural_graph_hash"]
    assert accepting_rejected["ok"] is False
    assert accepting_rejected["kind"] == FailureKind.EDITOR_AHEAD_CONFLICT.value
    assert accepting_rejected["outcome"]["kind"] == "error"

    assert missing_session["ok"] is False
    assert missing_session["kind"] == FailureKind.STALE_STATE_MISMATCH.value
    assert missing_session["outcome"]["kind"] == "error"
    assert missing_turn["ok"] is False
    assert missing_turn["kind"] == FailureKind.STALE_STATE_MISMATCH.value
    assert missing_turn["outcome"]["kind"] == "error"

    state = read_state(tmp_path / "s3")
    assert state["baseline_turn_id"] == accepted_turn_id
    assert state["baseline_graph_hash"] == accepted["candidate_structural_graph_hash"]
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
    assert accept_response["baseline_graph_hash"] == accepted["candidate_structural_graph_hash"]
    assert "audit_ref" not in accept_response
    assert reject_response["ok"] is True
    assert reject_response["action"] == "reject"
    assert reject_response["turn_id"] == rejected_turn_id
    assert reject_response["baseline_turn_id"] == accepted_turn_id
    assert reject_response["submit_graph_hash"] == rejected_submit_hash
    assert reject_response["baseline_graph_hash"] == accepted["candidate_structural_graph_hash"]
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_dev_full(monkeypatch)
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
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

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
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

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
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_reject

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
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_reject

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
    from vibecomfy.comfy_nodes.agent import provider as agent_provider
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_credentials, _handle_agent_status

    monkeypatch.setenv("ARNOLD_API_KEY", "arnold-secret")
    monkeypatch.setattr(
        agent_provider,
        "_load_arnold_runtime",
        lambda: (_ for _ in ()).throw(agent_provider.ProviderError("not installed")),
    )

    status = _handle_agent_status({"route": "anthropic", "model": "agent-edit"})

    assert status["ok"] is False
    assert status["provider_available"] is False
    assert status["error"] == {
        "message": "The model provider is unavailable. Check local provider configuration.",
        "type": "provider_unavailable",
    }
    assert status["reason"] == "The model provider is unavailable. Check local provider configuration."
    assert status["message"] == "The model provider is unavailable. Check local provider configuration."
    assert status["debug"]["provider_status"]["raw_error"] == "not installed"
    assert status["route"] == "arnold"
    assert status["requested_route"] == "anthropic"
    assert status["route_metadata"]["tos_acknowledgement_required"] is True
    assert status["credential_presence"]["arnold_api_key"] is True
    assert "arnold-secret" not in json.dumps(status)

    env_path = tmp_path / ".hermes" / ".env"
    saved = _handle_agent_credentials(
        {"provider": "openrouter", "api_key": "openrouter-secret"},
        env_path=env_path,
    )
    ignored = _handle_agent_credentials(
        {"provider": "openai-codex", "api_key": "codex-secret"},
        env_path=tmp_path / ".hermes" / "codex.env",
    )

    assert saved["ok"] is True
    assert saved["stored"] is True
    assert "OPENROUTER_API_KEY=openrouter-secret" in env_path.read_text(encoding="utf-8")
    assert "openrouter-secret" not in json.dumps(saved)
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
    from vibecomfy.comfy_nodes.agent import provider as agent_provider
    from vibecomfy.comfy_nodes.agent.audit import write_audit
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_credentials, _handle_agent_status

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ARNOLD_API_KEY", "arnold-secret")
    monkeypatch.setenv("HERMES_API_KEY", "hermes-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-env-secret")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

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
    assert healthy["route_options"]["openrouter"]["browser_api_key_allowed"] is True
    assert healthy["credential_presence"] == {
        "arnold_api_key": True,
        "hermes_api_key": True,
        "openrouter_api_key": True,
        "deepseek_api_key": False,
    }
    dumped_healthy = json.dumps(healthy, sort_keys=True)
    assert "arnold-secret" not in dumped_healthy
    assert "hermes-secret" not in dumped_healthy
    assert "openrouter-env-secret" not in dumped_healthy
    assert "runtime-secret" not in dumped_healthy
    assert "runtime-token" not in dumped_healthy
    assert "provider-secret" not in dumped_healthy

    monkeypatch.setattr(
        agent_provider,
        "_load_arnold_runtime",
        lambda: (_ for _ in ()).throw(agent_provider.ProviderError("not installed")),
    )
    unavailable = _handle_agent_status({"route": "openai-codex", "model": "agent-edit"})

    assert unavailable["ok"] is False
    assert unavailable["ready"] is False
    assert unavailable["reason"] == "The model provider is unavailable. Check local provider configuration."
    assert unavailable["message"] == "The model provider is unavailable. Check local provider configuration."
    assert unavailable["readiness"] == "unavailable"
    assert unavailable["route"] == "arnold"
    assert unavailable["requested_route"] == "openai-codex"
    assert unavailable["model"] == "agent-edit"
    assert unavailable["provider"] == "arnold"
    assert unavailable["provider_available"] is False
    assert unavailable["contract_version"] == "agent_edit_turn_v2"
    assert unavailable["error"] == {
        "message": "The model provider is unavailable. Check local provider configuration.",
        "type": "provider_unavailable",
    }
    assert unavailable["debug"]["provider_status"]["raw_error"] == "not installed"
    assert unavailable["route_metadata"] == {
        "requested_route": "openai-codex",
        "normalized_route": "arnold",
        "browser_api_key_allowed": False,
        "guidance": "OpenAI Codex runs through local Arnold/Hermes. Configure local "
        "ARNOLD_API_KEY or HERMES_API_KEY; browser keys are not accepted.",
        "tos_acknowledgement_required": False,
    }
    assert unavailable["route_options"]["openrouter"]["browser_api_key_allowed"] is True
    assert unavailable["route_options"]["anthropic"]["tos_acknowledgement_required"] is True
    assert unavailable["credential_presence"] == {
        "arnold_api_key": True,
        "hermes_api_key": True,
        "openrouter_api_key": True,
        "deepseek_api_key": False,
    }
    assert unavailable["legacy_deepseek_fallback_enabled"] is False

    env_path = tmp_path / ".hermes" / ".env"
    openrouter = _handle_agent_credentials(
        {
            "provider": "openrouter",
            "api_key": "openrouter-secret",
            "credential_payload": {"api_key": "openrouter-secret"},
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

    assert openrouter == {
        "ok": True,
        "stored": True,
        "provider": "openrouter",
        "key_name": "OPENROUTER_API_KEY",
        "path": str(env_path),
    }
    assert "openrouter-secret" not in json.dumps(openrouter)
    assert claude["stored"] is False
    assert codex["stored"] is False
    assert claude["provider"] == "arnold"
    assert claude["requested_route"] == "anthropic"
    assert codex["provider"] == "arnold"
    assert codex["requested_route"] == "openai-codex"
    assert "claude-secret" not in json.dumps(claude)
    assert "codex-secret" not in json.dumps(codex)

    written = env_path.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=openrouter-secret" in written
    assert "claude-secret" not in written
    assert "codex-secret" not in written

    audit_ref = write_audit(
        tmp_path / "credential-audit",
        context=TurnContext(session_id="cred", turn_id="0001"),
        response=openrouter,
        artifacts={
            "request": {
                "provider": "openrouter",
                "openrouter_api_key": "openrouter-secret",
                "credential_payload": {"api_key": "openrouter-secret"},
            }
        },
    )
    audit_payload = json.loads(Path(audit_ref.path).read_text(encoding="utf-8"))
    assert audit_payload["artifacts"]["request"]["openrouter_api_key"] == "<REDACTED>"
    assert audit_payload["artifacts"]["request"]["credential_payload"] == "<REDACTED>"
    assert "openrouter-secret" not in json.dumps(audit_payload)


# ── message-synthesis tests (T24) ─────────────────────────────────────────


def _make_state(**overrides: Any) -> AgentEditState:
    """Create a minimal AgentEditState for message-synthesis testing."""
    from pathlib import Path as _Path

    defaults: dict[str, Any] = {
        "task": "test task",
        "graph": {},
        "request_payload": {},
        "schema_provider": None,
        "baseline_graph_hash": None,
        "submit_graph_hash": None,
        "submit_structural_graph_hash": None,
        "submitted_client_graph_hash": None,
        "submitted_client_structural_graph_hash": None,
        "session_dir": _Path("/tmp/test_session"),
        "turn_dir": _Path("/tmp/test_session/turn_001"),
        "request_path": _Path("/tmp/test_session/request.json"),
        "original_ui_path": _Path("/tmp/test_session/original.json"),
        "before_py_path": _Path("/tmp/test_session/before.py"),
        "after_py_path": _Path("/tmp/test_session/after.py"),
        "projection_path": _Path("/tmp/test_session/projection.json"),
        "model_request_path": _Path("/tmp/test_session/model_request.json"),
        "model_response_path": _Path("/tmp/test_session/model_response.json"),
        "candidate_ui_path": _Path("/tmp/test_session/candidate.json"),
        "messages_path": _Path("/tmp/test_session/messages.json"),
        "user_message": "",
        "batch_field_changes": (),
        "batch_done_summary": "",
        "batch_final_summary": "",
        "batch_exit_mode": "",
    }
    defaults.update(overrides)
    return AgentEditState(**defaults)


def test_synthesize_message_empty_prose_with_valid_batch_fence() -> None:
    """Empty user_message with no outcome still produces a non-empty sentence."""
    state = _make_state(user_message="")
    msg = _synthesize_batch_repl_message(state)
    assert len(msg) > 0
    assert msg[-1] in ".!?"
    assert "completed" in msg.lower() or "edit" in msg.lower()


def test_synthesize_message_empty_prose_with_noop_outcome() -> None:
    """Empty prose with explicit noop outcome produces a sensible message."""
    state = _make_state(user_message="")
    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.noop())
    assert len(msg) > 0
    assert msg[-1] in ".!?"


def test_synthesize_message_noop_done_with_summary() -> None:
    """No-op done() with a summary message uses that summary."""
    state = _make_state(
        user_message="",
        batch_done_summary="All requested changes already match the current graph",
        batch_exit_mode="noop",
    )
    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.noop())
    assert "All requested changes already match the current graph" in msg


def test_synthesize_message_noop_done_without_summary_falls_back() -> None:
    """No-op done() without summary falls back to default message."""
    state = _make_state(user_message="", batch_exit_mode="noop")
    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.noop())
    assert len(msg) > 0
    assert msg[-1] in ".!?"
    assert "graph" in msg.lower()


def test_synthesize_message_diagnostic_only_turn() -> None:
    """A turn that only produces diagnostics (no edits) gets a noop message."""
    state = _make_state(
        user_message="",
        batch_exit_mode="noop",
        batch_done_summary="",
    )
    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.noop(reason="Diagnostic scan complete"))
    # The reason is stored on the outcome but not used by the synthesis for noop;
    # the synthesis uses batch_done_summary, which is empty, so it falls back.
    assert len(msg) > 0
    assert msg[-1] in ".!?"


def test_synthesize_message_zero_ops_noop_hides_gate_jargon() -> None:
    """Zero-op no-op summaries keep gate diagnostics out of the user-facing sentence."""
    state = _make_state(
        user_message="",
        batch_exit_mode="noop",
        batch_done_summary="No edits applied - identity verified; Gate B passed. Summary: No operations were applied.",
    )
    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.noop())

    assert msg == "Nothing needed changing; the workflow already matches that."
    assert "Gate" not in msg
    assert "identity" not in msg
    assert "No operations" not in msg


def test_synthesize_message_answer_only_noop_uses_terminal_done_prose() -> None:
    """Answer-only turns should show the model's final explanation, not edit status."""
    state = _make_state(
        user_message="",
        batch_exit_mode="noop",
        batch_done_summary=(
            "No edits applied - identity verified; Gate B passed. "
            "Summary: No operations were applied."
        ),
        batch_turns=[
            {
                "turn_number": 0,
                "batch": "done()",
                "message": "This workflow loads an image and generates a short video.",
                "statements": [{"op_kind": "done", "ok": True, "landed": False}],
            },
            {
                "turn_number": 1,
                "batch": "done()",
                "message": "Final answer: it is an image-to-video workflow with audio.",
                "statements": [{"op_kind": "done", "ok": True, "landed": False}],
            },
        ],
    )
    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.noop())

    assert msg == "Final answer: it is an image-to-video workflow with audio."
    assert "Nothing needed changing" not in msg
    assert "Gate" not in msg


def test_rendered_chat_message_uses_answer_only_noop_prose(tmp_path: Path) -> None:
    """Persisted chat text must carry answer prose for no-edit question turns."""
    from vibecomfy.comfy_nodes.agent.edit import _change_details_payload

    context = TurnContext(session_id="chat-answer-noop", turn_id="0001")
    state = _make_state(
        task="What's happening in this workflow?",
        session_dir=tmp_path / "chat-answer-noop",
        turn_dir=tmp_path / "chat-answer-noop" / "turns" / "0001",
        batch_exit_mode="noop",
        batch_done_summary=(
            "No edits applied - identity verified; Gate B passed. "
            "Summary: No operations were applied."
        ),
        batch_turns=[
            {
                "turn_number": 0,
                "batch": "done()",
                "message": "This workflow generates video from an input image.",
                "statements": [{"op_kind": "done", "ok": True, "landed": False}],
            },
        ],
    )
    message = _synthesize_batch_repl_message(state, outcome=TurnOutcome.noop())
    response = {
        "message": message,
        "outcome": TurnOutcome.noop(reason=state.batch_done_summary).to_dict(),
        "change_details": _change_details_payload(state, context),
    }

    _write_turn_chat_artifact(state, context, response, "batch_repl")
    chat = json.loads((state.turn_dir / "chat.json").read_text(encoding="utf-8"))
    agent = chat["messages"][1]
    assert agent["text"] == "This workflow generates video from an input image."
    assert agent["outcome"]["kind"] == "noop"
    assert "Gate B passed" in agent["outcome"]["reason"]
    assert agent["change_details"]["batch_turns"][0]["message"].startswith("This workflow")


def test_synthesize_message_budget_exhaustion() -> None:
    """Budget exhaustion produces the expected budget message."""
    state = _make_state(
        user_message="",
        batch_exit_mode="budget",
        batch_final_summary="Too many turns without progress",
    )
    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.budget())
    assert "budget" in msg.lower() or "ran out" in msg.lower()
    assert len(msg) > 0
    assert msg[-1] in ".!?"


def test_synthesize_message_budget_exhaustion_with_landed_edits() -> None:
    """Budget exhaustion outcome produces plain budget message (no lead for outcome path)."""
    from vibecomfy.porting.edit.types import FieldChange

    state = _make_state(
        user_message="",
        batch_exit_mode="budget",
        batch_final_summary="Could not finish all edits",
        batch_field_changes=(
            FieldChange(uid="widget", field_path="seed", old=1, new=9),
            FieldChange(uid="widget", field_path="steps", old=20, new=30),
        ),
    )
    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.budget())
    # Budget outcome path returns the budget message directly; lead is only added
    # in the failure path (where failure + _BATCH_EXIT_BUDGET combines lead + warning).
    assert "budget" in msg.lower() or "ran out" in msg.lower()
    assert len(msg) > 0
    assert msg[-1] in ".!?"


def test_synthesize_message_partial_success_with_diagnostics() -> None:
    """Partial success: some edits landed, failure set (with budget exit) — lead + warning."""
    from vibecomfy.porting.edit.types import FieldChange

    failure = failure_envelope(
        FailureKind.MODEL_MISTAKE,
        "agent_batch",
        TurnContext(session_id="s1", turn_id="t1"),
    )
    state = _make_state(
        user_message="",
        batch_exit_mode="budget",
        batch_final_summary="Some edits could not be applied",
        batch_field_changes=(
            FieldChange(uid="node1", field_path="x", old=0, new=100),
        ),
    )
    msg = _synthesize_batch_repl_message(state, failure=failure)
    assert "Applied 1 edit" in msg
    assert len(msg) > 0
    assert msg[-1] in ".!?"


def test_synthesize_message_partial_success_with_diagnostics_no_lead() -> None:
    """Partial success with failure but zero landed edits — just the warning."""
    failure = failure_envelope(
        FailureKind.VALIDATION_ERROR,
        "lower",
        TurnContext(session_id="s1", turn_id="t1"),
    )
    state = _make_state(
        user_message="",
        batch_exit_mode="",
        batch_field_changes=(),
    )
    msg = _synthesize_batch_repl_message(state, failure=failure)
    assert len(msg) > 0
    assert msg[-1] in ".!?"
    assert "Applied" not in msg  # No lead for zero edits


def test_synthesize_message_landed_edit_lead_single() -> None:
    """Single landed edit produces 'Applied 1 edit.' lead."""
    from vibecomfy.porting.edit.types import FieldChange

    state = _make_state(
        batch_field_changes=(FieldChange(uid="a", field_path="p", old=1, new=2),),
    )
    lead = _landed_edit_lead(state)
    assert lead == "Applied 1 edit."


def test_synthesize_message_landed_edit_lead_multiple() -> None:
    """Multiple landed edits produce 'Applied N edits.' lead."""
    from vibecomfy.porting.edit.types import FieldChange

    state = _make_state(
        batch_field_changes=(
            FieldChange(uid="a", field_path="p", old=1, new=2),
            FieldChange(uid="b", field_path="q", old=3, new=4),
            FieldChange(uid="c", field_path="r", old=5, new=6),
        ),
    )
    lead = _landed_edit_lead(state)
    assert lead == "Applied 3 edits."


def test_synthesize_message_landed_edit_lead_zero() -> None:
    """Zero landed edits produces empty lead string."""
    state = _make_state(batch_field_changes=())
    lead = _landed_edit_lead(state)
    assert lead == ""


def test_repair_field_changes_uses_named_widget_old_value_for_ksampler_steps() -> None:
    graph = {
        "nodes": [
            {
                "id": 2,
                "type": "KSampler",
                "properties": {"vibecomfy_uid": "ksampler"},
                "widgets_values": [123, "randomize", 20, 7.5, "euler", "normal", 1],
            }
        ],
        "links": [],
    }
    repaired = _repair_field_changes_from_original_ui(
        graph,
        (
            FieldChange(
                uid="ksampler",
                field_path="steps",
                old="normal",
                new=28,
            ),
        ),
    )

    assert repaired == (
        FieldChange(uid="ksampler", field_path="steps", old=20, new=28),
    )


def test_repair_field_changes_repairs_null_old_from_original_ui() -> None:
    """Null old values are repaired from the original UI graph when the field exists."""
    graph = {
        "nodes": [
            {
                "id": 5,
                "type": "CLIPTextEncode",
                "properties": {"vibecomfy_uid": "clip"},
                "widgets_values": ["a beautiful sunset"],
            }
        ],
        "links": [],
    }
    repaired = _repair_field_changes_from_original_ui(
        graph,
        (
            FieldChange(
                uid="clip",
                field_path="text",
                old=None,
                new="a starry night",
            ),
        ),
    )
    assert repaired == (
        FieldChange(uid="clip", field_path="text", old="a beautiful sunset", new="a starry night"),
    )


def test_repair_field_changes_preserves_null_when_absent_from_original_ui() -> None:
    """Genuinely absent fields keep old=None after the repair attempt."""
    graph: dict[str, Any] = {"nodes": [], "links": []}
    repaired = _repair_field_changes_from_original_ui(
        graph,
        (
            FieldChange(
                uid="nonexistent",
                field_path="missing_field",
                old=None,
                new=42,
            ),
        ),
    )
    assert repaired == (
        FieldChange(uid="nonexistent", field_path="missing_field", old=None, new=42),
    )


def test_human_change_phrase_set_wording_for_absent_old() -> None:
    """_human_change_phrase uses 'set X to Y' when old is None."""
    change = FieldChange(uid="node1", field_path="title", old=None, new="My Workflow")
    phrase = _human_change_phrase(change)
    assert phrase == "set node1.title to My Workflow"


def test_human_change_phrase_updated_wording_for_present_old() -> None:
    """_human_change_phrase still uses 'updated X from A to B' when old is present."""
    change = FieldChange(uid="node1", field_path="title", old="Old Title", new="New Title")
    phrase = _human_change_phrase(change)
    assert phrase == "updated node1.title from Old Title to New Title"


def test_operation_detail_payload_set_wording_for_null_old() -> None:
    """_operation_detail_payload uses 'Set X to Y.' when old is None."""
    changes = (FieldChange(uid="a", field_path="b", old=None, new=99),)
    payload = _operation_detail_payload(changes)
    assert payload == [
        {
            "uid": "a",
            "field_path": "b",
            "old": None,
            "new": 99,
            "summary": "Set a.b to 99.",
        }
    ]


def test_operation_detail_payload_changed_wording_for_present_old() -> None:
    """_operation_detail_payload uses 'Changed X from A to B.' when old is present."""
    changes = (FieldChange(uid="a", field_path="b", old=1, new=99),)
    payload = _operation_detail_payload(changes)
    assert payload == [
        {
            "uid": "a",
            "field_path": "b",
            "old": 1,
            "new": 99,
            "summary": "Changed a.b from 1 to 99.",
        }
    ]


def test_operation_detail_payload_mixed_null_and_present_old() -> None:
    """Mixed absent/present old values produce correct summaries."""
    changes = (
        FieldChange(uid="a", field_path="x", old=None, new=10),
        FieldChange(uid="b", field_path="y", old=5, new=20),
    )
    payload = _operation_detail_payload(changes)
    assert payload == [
        {
            "uid": "a",
            "field_path": "x",
            "old": None,
            "new": 10,
            "summary": "Set a.x to 10.",
        },
        {
            "uid": "b",
            "field_path": "y",
            "old": 5,
            "new": 20,
            "summary": "Changed b.y from 5 to 20.",
        },
    ]


def test_operation_detail_payload_filters_noop_field_changes() -> None:
    payload = _operation_detail_payload(
        (
            FieldChange(uid="ksampler", field_path="cfg", old=6.5, new=6.5),
            FieldChange(uid="ksampler", field_path="steps", old=20, new=30),
        )
    )

    assert payload == [
        {
            "uid": "ksampler",
            "field_path": "steps",
            "old": 20,
            "new": 30,
            "summary": "Changed ksampler.steps from 20 to 30.",
        }
    ]


def test_humanized_edit_message_set_wording_for_single_absent_old() -> None:
    """_humanized_edit_message produces 'Set ...' for a single change with absent old."""
    state = _make_state(
        graph={"nodes": [{"id": 1, "type": "SaveImage", "properties": {"vibecomfy_uid": "1"}}]},
        batch_field_changes=(
            FieldChange(uid="1", field_path="filename_prefix", old=None, new="output"),
        ),
    )
    msg = _humanized_edit_message(state)
    assert msg == "Set SaveImage filename_prefix to output."


def test_humanized_edit_message_mixed_absent_and_present() -> None:
    """_humanized_edit_message mixes 'set' and 'updated' for two changes."""
    state = _make_state(
        graph={
            "nodes": [
                {"id": 1, "type": "SaveImage", "properties": {"vibecomfy_uid": "1"}},
                {"id": 2, "type": "KSampler", "properties": {"vibecomfy_uid": "2"}},
            ]
        },
        batch_field_changes=(
            FieldChange(uid="1", field_path="filename_prefix", old=None, new="output"),
            FieldChange(uid="2", field_path="steps", old=20, new=30),
        ),
    )
    msg = _humanized_edit_message(state)
    assert "set saveimage filename_prefix to output" in msg.lower()
    assert "updated ksampler steps from 20 to 30" in msg.lower()


def test_humanized_edit_message_describes_added_nodes_not_internal_widget_uid() -> None:
    """Add-only turns describe the added node classes and key values, not n-prefixed uids."""
    original_graph = {
        "nodes": [
            {
                "id": 18,
                "type": "Upscale Image (using Model)",
                "title": "Upscale Image (using Model)",
                "properties": {"vibecomfy_uid": "upscale"},
                "outputs": [{"name": "IMAGE"}],
            }
        ],
        "links": [],
    }
    candidate_graph = {
        "nodes": [
            *original_graph["nodes"],
            {
                "id": "n11",
                "type": "ImageScaleBy",
                "properties": {"vibecomfy_uid": "n11"},
                "inputs": [{"name": "image", "link": 101}],
                "widgets": [{"name": "scale_by"}, {"name": "upscale_method"}],
                "widgets_values": [0.5, "area"],
            },
            {
                "id": "n12",
                "type": "SaveImage",
                "properties": {"vibecomfy_uid": "n12"},
                "inputs": [{"name": "images", "link": 102}],
                "widgets": [{"name": "filename_prefix"}],
                "widgets_values": ["crane/half"],
            },
        ],
        "links": [
            [101, 18, 0, "n11", 0, "IMAGE"],
            [102, "n11", 0, "n12", 0, "IMAGE"],
        ],
    }
    state = _make_state(
        graph=original_graph,
        ui_payload=candidate_graph,
        batch_done_summary="Gate A passed: 2 edit operation(s) verified.",
        batch_field_changes=(
            FieldChange(uid="n11", field_path="upscale_method", old=None, new="area"),
        ),
    )

    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.edit())

    assert "Added" in msg
    assert "ImageScaleBy" in msg
    assert "50%" in msg
    assert "area" in msg
    assert "SaveImage" in msg
    assert "crane/half" in msg
    assert "{" not in msg
    assert "Gate A" not in msg
    assert "n11" not in msg
    assert "n12" not in msg


def test_humanized_edit_message_describes_removed_nodes_without_gate_dump() -> None:
    """Remove-only turns synthesize a human summary instead of leaking done() gate text."""
    original_graph = {
        "nodes": [
            {"id": 1, "type": "VAE Decode", "properties": {"vibecomfy_uid": "vae"}},
            {
                "id": "imagescaleby",
                "type": "ImageScaleBy",
                "properties": {"vibecomfy_uid": "imagescaleby"},
                "widgets": [{"name": "scale_by"}, {"name": "upscale_method"}],
                "widgets_values": [0.5, "area"],
            },
            {
                "id": "saveimage_3",
                "type": "SaveImage",
                "properties": {"vibecomfy_uid": "saveimage_3"},
                "widgets": [{"name": "filename_prefix"}],
                "widgets_values": ["crane/half"],
            },
        ],
        "links": [],
    }
    candidate_graph = {"nodes": [original_graph["nodes"][0]], "links": []}
    state = _make_state(
        graph=original_graph,
        ui_payload=candidate_graph,
        batch_done_summary=(
            "Gate A passed: 2 edit operation(s) verified. Gate B passed: touched compile "
            "region is isomorphic. Summary: Removed ImageScaleBy node 'imagescaleby'."
        ),
        batch_field_changes=(),
    )

    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.edit())

    assert "Removed" in msg
    assert "ImageScaleBy" in msg
    assert "SaveImage" in msg
    assert "crane/half" in msg
    assert "{" not in msg
    assert "Gate A" not in msg
    assert "Gate B" not in msg
    assert "imagescaleby" not in msg
    assert "saveimage_3" not in msg


def test_humanized_edit_message_describes_rewire_link_refs_without_raw_dicts() -> None:
    """Link FieldChange mapping values resolve to node labels instead of raw dict text."""
    original_graph = {
        "nodes": [
            {
                "id": 8,
                "type": "VAEDecode",
                "title": "VAE Decode",
                "properties": {"vibecomfy_uid": "vae_decode"},
                "outputs": [{"name": "IMAGE"}],
            },
            {
                "id": 18,
                "type": "ImageUpscaleWithModel",
                "outputs": [{"name": "IMAGE"}],
            },
            {
                "id": 19,
                "type": "SaveImage",
                "properties": {"vibecomfy_uid": "final_save"},
                "inputs": [{"name": "images", "link": 12}],
            },
        ],
        "links": [[12, 18, 0, 19, 0, "IMAGE"]],
    }
    candidate_graph = {
        "nodes": [
            original_graph["nodes"][0],
            {
                "id": 18,
                "type": "ImageUpscaleWithModel",
            },
            {
                "id": 19,
                "type": "SaveImage",
                "properties": {"vibecomfy_uid": "final_save"},
                "inputs": [{"name": "images", "link": 13}],
            },
        ],
        "links": [[13, 8, 0, 19, 0, "IMAGE"]],
    }
    state = _make_state(
        graph=original_graph,
        ui_payload=candidate_graph,
        batch_field_changes=(
            FieldChange(
                uid="final_save",
                field_path="images",
                old={"scope_path": "", "uid": 18, "output_slot": 0},
                new={"scope_path": "", "uid": "vae_decode", "output_slot": 0},
            ),
        ),
    )

    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.edit())

    assert "Rewired SaveImage images" in msg
    assert "VAE Decode" in msg
    assert "ImageUpscaleWithModel" in msg
    assert "unknown source" not in msg
    assert "{" not in msg
    assert "scope_path" not in msg
    assert "uid" not in msg
    assert "Gate A" not in msg


def test_humanized_edit_message_resolves_live_rewire_link_id_endpoint_shape() -> None:
    """Live response artifacts may carry LiteGraph id uid + stale link id as output_slot."""
    response_artifact = {
        "graph": {
            "nodes": [
                {
                    "id": 8,
                    "type": "VAEDecode",
                    "properties": {"Node name for S&R": "VAEDecode", "vibecomfy_uid": "8"},
                    "outputs": [
                        {
                            "localized_name": "IMAGE",
                            "name": "IMAGE",
                            "slot_index": 0,
                            "type": "IMAGE",
                            "links": [23, 43, 47],
                        }
                    ],
                },
                {
                    "id": 18,
                    "type": "ImageUpscaleWithModel",
                    "properties": {
                        "Node name for S&R": "ImageUpscaleWithModel",
                        "vibecomfy_id": "ImageUpscaleWithModel_0",
                        "vibecomfy_uid": "n3",
                    },
                    "outputs": [
                        {
                            "localized_name": "IMAGE",
                            "name": "IMAGE",
                            "slot_index": 0,
                            "type": "IMAGE",
                            "links": [],
                        }
                    ],
                },
                {
                    "id": 25,
                    "type": "SaveImage",
                    "properties": {
                        "Node name for S&R": "SaveImage",
                        "vibecomfy_id": "SaveImage_0",
                        "vibecomfy_uid": "n10",
                    },
                    "inputs": [
                        {"localized_name": "images", "name": "images", "type": "IMAGE", "link": 47},
                        {
                            "localized_name": "filename_prefix",
                            "name": "filename_prefix",
                            "type": "STRING",
                            "widget": {"name": "filename_prefix"},
                            "link": None,
                        },
                    ],
                    "outputs": [],
                },
            ],
            "links": [[47, 8, 0, 25, 0, "IMAGE"]],
        },
        "candidate": {
            "graph": {
                "nodes": [
                    {
                        "id": 8,
                        "type": "VAEDecode",
                        "properties": {"Node name for S&R": "VAEDecode", "vibecomfy_uid": "8"},
                        "outputs": [
                            {
                                "localized_name": "IMAGE",
                                "name": "IMAGE",
                                "slot_index": 0,
                                "type": "IMAGE",
                                "links": [23, 43, 47],
                            }
                        ],
                    },
                    {
                        "id": 18,
                        "type": "ImageUpscaleWithModel",
                        "properties": {
                            "Node name for S&R": "ImageUpscaleWithModel",
                            "vibecomfy_id": "ImageUpscaleWithModel_0",
                            "vibecomfy_uid": "n3",
                        },
                        "outputs": [
                            {
                                "localized_name": "IMAGE",
                                "name": "IMAGE",
                                "slot_index": 0,
                                "type": "IMAGE",
                                "links": [],
                            }
                        ],
                    },
                    {
                        "id": 25,
                        "type": "SaveImage",
                        "properties": {
                            "Node name for S&R": "SaveImage",
                            "vibecomfy_id": "SaveImage_0",
                            "vibecomfy_uid": "n10",
                        },
                        "inputs": [
                            {"localized_name": "images", "name": "images", "type": "IMAGE", "link": 47},
                            {
                                "localized_name": "filename_prefix",
                                "name": "filename_prefix",
                                "type": "STRING",
                                "widget": {"name": "filename_prefix"},
                                "link": None,
                            },
                        ],
                        "outputs": [],
                    },
                ],
                "links": [[47, 8, 0, 25, 0, "IMAGE"]],
            }
        },
        "batch_turns": [
            {
                "field_changes": [
                    {
                        "uid": "n10",
                        "field_path": "images",
                        "old": {"output_slot": 25, "scope_path": "", "uid": "18"},
                        "new": {"output_slot": "IMAGE", "scope_path": "", "uid": "8"},
                    }
                ]
            }
        ],
    }
    changes = tuple(
        FieldChange(**item)
        for item in response_artifact["batch_turns"][0]["field_changes"]
    )
    state = _make_state(
        graph=response_artifact["graph"],
        ui_payload=response_artifact["candidate"]["graph"],
        batch_field_changes=changes,
    )

    msg = _humanized_edit_message(state)

    assert msg == (
        "Rewired SaveImage images to come from VAEDecode IMAGE instead of "
        "ImageUpscaleWithModel."
    )
    assert "unknown source" not in msg
    assert "{" not in msg


def test_absent_field_old_not_serialized_in_to_dict() -> None:
    """FieldChange.to_dict() serializes absent old as null, not a sentinel object."""
    change = FieldChange(uid="x", field_path="y", old=None, new=1)
    d = change.to_dict()
    assert d["old"] is None
    assert d["new"] == 1
    # The sentinel _ABSENT_FIELD_OLD must never leak into serialized output
    from vibecomfy.comfy_nodes.agent.edit import _ABSENT_FIELD_OLD
    assert d["old"] is not _ABSENT_FIELD_OLD

def test_synthesize_message_edit_outcome_with_done_summary() -> None:
    """Edit outcome uses repaired FieldChange values for the visible message."""
    from vibecomfy.porting.edit.types import FieldChange

    state = _make_state(
        graph={"nodes": [{"id": 3, "type": "KSampler", "properties": {"vibecomfy_uid": "ksampler"}}]},
        user_message="",
        batch_exit_mode="done",
        batch_done_summary="Gate A passed: 1 edit operation(s) verified. Changed ksampler.steps from 'normal' to 26.",
        batch_field_changes=(
            FieldChange(uid="ksampler", field_path="steps", old=20, new=26),
        ),
    )
    msg = _synthesize_batch_repl_message(state, outcome=TurnOutcome.edit())
    assert "KSampler steps" in msg
    assert "20" in msg
    assert "26" in msg
    assert "Gate A" not in msg
    assert "normal" not in msg


def test_rendered_chat_message_uses_humanized_repaired_old_value(tmp_path: Path) -> None:
    """Persisted chat text uses the final human message, not raw gate summary text."""
    from vibecomfy.comfy_nodes.agent.edit import _change_details_payload

    context = TurnContext(session_id="chat-repaired", turn_id="0001")
    state = _make_state(
        task="set steps to 26",
        session_dir=tmp_path / "chat-repaired",
        turn_dir=tmp_path / "chat-repaired" / "turns" / "0001",
        batch_done_summary="Gate A passed: 1 edit operation(s) verified. Changed ksampler.steps from 'normal' to 26.",
        batch_final_summary="Gate B passed: touched compile region is isomorphic.",
        batch_field_changes=(
            FieldChange(uid="ksampler", field_path="steps", old=20, new=26),
        ),
    )
    message = _synthesize_batch_repl_message(state, outcome=TurnOutcome.edit(changes=state.batch_field_changes))
    response = {
        "message": message,
        "outcome": TurnOutcome.edit(changes=state.batch_field_changes).to_dict(),
        "change_details": _change_details_payload(state, context),
    }

    _write_turn_chat_artifact(state, context, response, "batch_repl")
    chat = json.loads((state.turn_dir / "chat.json").read_text(encoding="utf-8"))
    agent = chat["messages"][1]
    assert "ksampler.steps" in agent["text"]
    assert "20" in agent["text"]
    assert "normal" not in agent["text"]
    assert "Gate A" not in agent["text"]
    assert "Gate A passed" in agent["change_details"]["done_summary"]


def test_synthesize_message_clarify_outcome() -> None:
    """Pure clarify produces the expected clarification message."""
    state = _make_state(user_message="Which prompt should I edit?", batch_exit_mode="pure_clarify")
    msg = _synthesize_batch_repl_message(
        state, outcome=TurnOutcome.clarify(question="Which prompt should I edit?")
    )
    assert msg == "Which prompt should I edit?"


def test_synthesize_message_edit_clarify_outcome() -> None:
    """Edit+clarify combines lead + clarification warning."""
    from vibecomfy.porting.edit.types import FieldChange

    state = _make_state(
        user_message="",
        batch_exit_mode="edit_clarify",
        batch_field_changes=(
            FieldChange(uid="a", field_path="x", old=0, new=1),
        ),
    )
    msg = _synthesize_batch_repl_message(
        state, outcome=TurnOutcome.edit_and_clarify(question="Should I continue?")
    )
    assert "Applied 1 edit" in msg
    assert "Should I continue?" in msg


def test_synthesize_message_failure_budget_with_lead() -> None:
    """Failure with budget exit and landed edits gives lead + budget message."""
    from vibecomfy.porting.edit.types import FieldChange

    failure = failure_envelope(
        FailureKind.MODEL_MISTAKE,
        "agent_batch",
        TurnContext(session_id="s1", turn_id="t1"),
    )
    state = _make_state(
        user_message="",
        batch_exit_mode="budget",
        batch_final_summary="Budget exhausted",
        batch_field_changes=(
            FieldChange(uid="n1", field_path="a", old=0, new=1),
        ),
    )
    msg = _synthesize_batch_repl_message(state, failure=failure)
    assert "Applied 1 edit" in msg
    assert "budget" in msg.lower() or "ran out" in msg.lower()


def test_synthesize_message_failure_non_budget() -> None:
    """Non-budget failure uses the typed user-facing failure message."""
    failure = failure_envelope(
        FailureKind.VALIDATION_ERROR,
        "lower",
        TurnContext(session_id="s1", turn_id="t1"),
    )
    state = _make_state(user_message="")
    msg = _synthesize_batch_repl_message(state, failure=failure)
    assert len(msg) > 0
    assert msg[-1] in ".!?"
    assert msg == "The edited workflow has validation errors and was not applied. See details."


def test_synthesize_message_malformed_model_json_uses_user_facing_message() -> None:
    failure = failure_envelope(
        FailureKind.MALFORMED_MODEL_JSON,
        "agent_response",
        TurnContext(session_id="s1", turn_id="t1"),
    )
    state = _make_state(user_message="")
    msg = _synthesize_batch_repl_message(state, failure=failure)
    assert msg == "The model response could not be parsed. The graph is unchanged."
    assert "Some requested edits" not in msg


def test_synthesize_message_stale_state_failure_describes_baseline_mismatch() -> None:
    failure = failure_envelope(
        FailureKind.STALE_STATE_MISMATCH,
        "ingest",
        TurnContext(session_id="s1", turn_id="t1"),
    )
    state = _make_state(user_message="", batch_exit_mode="", batch_field_changes=())

    msg = _synthesize_batch_repl_message(state, failure=failure)

    assert "submitted graph" in msg.lower() or "canvas changed" in msg.lower()
    assert "did not land" not in msg.lower()


def test_synthesize_message_all_messages_are_non_empty() -> None:
    """Every code path produces a non-empty sentence-shaped message."""
    from vibecomfy.porting.edit.types import FieldChange

    scenarios: list[tuple[AgentEditState, TurnOutcome | None, FailureEnvelope | None]] = [
        # (state, outcome, failure)
        (_make_state(), None, None),
        (_make_state(), TurnOutcome.edit(), None),
        (_make_state(), TurnOutcome.noop(), None),
        (_make_state(), TurnOutcome.clarify(), None),
        (_make_state(), TurnOutcome.budget(), None),
        (
            _make_state(
                batch_field_changes=(FieldChange(uid="x", field_path="y", old=1, new=2),),
            ),
            TurnOutcome.edit_and_clarify(),
            None,
        ),
        (
            _make_state(),
            None,
            failure_envelope(
                FailureKind.MODEL_MISTAKE,
                "agent_batch",
                TurnContext(session_id="s1", turn_id="t1"),
            ),
        ),
    ]
    for state, outcome, failure in scenarios:
        msg = _synthesize_batch_repl_message(state, outcome=outcome, failure=failure)
        assert len(msg) > 0, f"Empty message for outcome={outcome}, failure={failure}"
        assert msg[-1] in ".!?", f"Message not sentence-shaped: {msg!r}"


# ── T2: Backend persistence tests ───────────────────────────────────────────


def test_batch_repl_ingest_writes_request_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``batch_repl`` product path write ``request.json`` during ingest."""
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _fake_batch_client(_messages):
        return {"batch": "done()", "message": "Done."}

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "write request.json test",
            "session_id": "batch-request-json",
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result.get("ok") is True
    turn_dir = turn_dir_for(tmp_path, "batch-request-json", str(result["turn_id"]))
    request_path = turn_dir / "request.json"
    assert request_path.is_file(), f"request.json not found at {request_path}"
    on_disk = json.loads(request_path.read_text(encoding="utf-8"))
    assert on_disk["task"] == "write request.json test"


def test_chat_json_written_for_allocated_success_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``chat.json`` is written for an allocated success response in the
    ``batch_repl`` path."""
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _fake_batch_client(_messages):
        return {"batch": "done()", "message": "Successfully applied the edit."}

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "chat json success test",
            "session_id": "batch-chat-success",
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_fake_batch_client,
        session_root=tmp_path,
    )

    assert result.get("ok") is True
    turn_dir = turn_dir_for(tmp_path, "batch-chat-success", str(result["turn_id"]))
    chat_path = turn_dir / "chat.json"
    assert chat_path.is_file(), f"chat.json not found at {chat_path}"
    on_disk = json.loads(chat_path.read_text(encoding="utf-8"))
    assert on_disk["session_id"] == "batch-chat-success"
    assert on_disk["turn_id"] == str(result["turn_id"])
    messages = on_disk["messages"]
    assert len(messages) >= 2
    assert messages[0]["role"] == "user"
    assert messages[0]["text"] == "chat json success test"
    assert messages[1]["role"] == "agent"
    assert len(messages[1]["text"]) > 0


def test_chat_json_written_for_allocated_stage_blocked_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``chat.json`` is written for an allocated stage-blocked (failure)
    response in the ``batch_repl`` path."""
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _blocked_runner(state, context, **_kwargs):
        raise _StageBlocked(
            StageResult(
                stage="agent_batch",
                ok=False,
                blocking=True,
                issues=(),
            ),
            failure_envelope(
                FailureKind.MODEL_MISTAKE,
                "agent_batch",
                context,
                agent_failure_context={"explanation": "intentional test block"},
            ),
        )

    monkeypatch.setattr(
        agent_edit_module,
        "_run_batch_repl_product_path",
        _blocked_runner,
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "chat json block test",
            "session_id": "batch-chat-blocked",
        },
        schema_provider=_batch_repl_provider(),
        session_root=tmp_path,
    )

    assert result.get("ok") is False
    turn_id = str(result["turn_id"])
    turn_dir = turn_dir_for(tmp_path, "batch-chat-blocked", turn_id)
    chat_path = turn_dir / "chat.json"
    assert chat_path.is_file(), f"chat.json not found at {chat_path}"
    on_disk = json.loads(chat_path.read_text(encoding="utf-8"))
    assert on_disk["session_id"] == "batch-chat-blocked"
    assert on_disk["turn_id"] == turn_id


def test_handle_agent_edit_revise_writes_revision_evidence_before_first_model_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    captured_messages: list[list[dict[str, str]]] = []
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

    def _client(messages):
        captured_messages.append(messages)
        return next(responses)

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {"route": "revise", "task": "edit_graph"},
            "session_id": "revise-evidence-prompt",
            "max_batches": 3,
        },
        schema_provider=provider,
        deepseek_client=_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    user_prompt = captured_messages[0][1]["content"]
    assert "Revision evidence (JSON; collected before this model call):" in user_prompt
    assert '"safe_candidate_possible": true' in user_prompt
    turn_dir = turn_dir_for(tmp_path, "revise-evidence-prompt", str(result["turn_id"]))
    evidence_path = turn_dir / "revision_evidence.json"
    assert evidence_path.is_file()
    artifact = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence = artifact["revision_evidence"]
    assert artifact["classification"]["route"] == "revise"
    assert evidence["safe_candidate_possible"] is True
    assert evidence["candidate_eligible"] is True
    assert evidence["scoped_diff"]["candidate_eligible"] is True
    assert result["report"]["revision_evidence"]["candidate_eligible"] is True


def test_handle_agent_edit_direct_edit_public_revise_emits_scoped_diff_and_rationale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Changed only the save prefix.",
            },
            {
                "batch": "done()",
                "message": "Ready.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change node 2 filename prefix to after",
            "target_node_ids": ["2"],
            "route": "direct_edit",
            "executor_route": "direct_edit",
            "provider_route": "codex",
            "executor_classification": {"route": "direct_edit", "task": "edit_graph"},
            "session_id": "direct-edit-public-revise",
            "max_batches": 3,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert result["candidate"] is not None
    assert result["change_focus"] == "Focused change"
    assert "direct_edit" not in json.dumps(
        {
            "outcome": result["outcome"],
            "change_focus": result["change_focus"],
            "report": result["report"],
        }
    )
    operations = result["change_details"]["operations"]
    assert operations
    assert any(
        op.get("field_path") == "filename_prefix" and op.get("new") == "after"
        for op in operations
    )
    evidence = result["report"]["revision_evidence"]
    assert evidence["candidate_eligible"] is True
    scoped = evidence["scoped_diff"]
    assert scoped["candidate_eligible"] is True
    assert scoped["target_node_ids"] == ["2"]
    assert scoped["target_matched"] is True
    assert scoped["changed_nodes"] == ["2"]
    assert scoped["eligibility_blockers"] == []
    assert any(path.startswith("nodes.2.") for path in scoped["diff_paths"])
    turn_dir = turn_dir_for(tmp_path, "direct-edit-public-revise", str(result["turn_id"]))
    artifact = json.loads((turn_dir / "revision_evidence.json").read_text(encoding="utf-8"))
    assert artifact["revision_evidence"]["scoped_diff"]["changed_nodes"] == ["2"]


def test_handle_agent_edit_revise_blocks_broken_graph_before_provider_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    broken_graph = _json_clone(_ui_graph())
    broken_graph["links"].append([999, 1, 0, 404, 0, "IMAGE"])

    def _provider_must_not_run(_messages):
        raise AssertionError("provider should not be called for blocked revise evidence")

    result = handle_agent_edit(
        {
            "graph": broken_graph,
            "task": "fix this broken graph",
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {"route": "revise", "task": "edit_graph"},
            "session_id": "revise-evidence-blocked",
            "max_batches": 1,
        },
        schema_provider=provider,
        deepseek_client=_provider_must_not_run,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "noop"
    assert result["candidate"] is None
    assert result["apply_allowed"] is False
    assert result["canvas_apply_allowed"] is False
    assert result["report"]["read_only"] is True
    evidence = result["report"]["revision_evidence"]
    assert evidence["safe_candidate_possible"] is False
    assert evidence["topology"]["has_blockers"] is True
    assert "dangling" in evidence["topology"]["summary"]
    turn_dir = turn_dir_for(tmp_path, "revise-evidence-blocked", str(result["turn_id"]))
    assert not (turn_dir / "model_request.json").exists()
    artifact = json.loads((turn_dir / "revision_evidence.json").read_text(encoding="utf-8"))
    assert artifact["revision_evidence"]["no_candidate_reason"] == "no_changes"


def test_handle_agent_edit_revise_strips_target_mismatched_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    responses = iter(
        [
            {
                "batch": 'loadimage.image = "other.png"',
                "message": "Changed the loader.",
            },
            {
                "batch": "done()",
                "message": "Ready.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change node 2 filename prefix to after",
            "target_node_ids": ["2"],
            "route": "direct_edit",
            "executor_route": "direct_edit",
            "provider_route": "codex",
            "executor_classification": {"route": "direct_edit", "task": "edit_graph"},
            "session_id": "revise-target-mismatch",
            "max_batches": 3,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "noop"
    assert result["candidate"] is None
    assert result["apply_allowed"] is False
    evidence = result["report"]["revision_evidence"]
    assert evidence["candidate_eligible"] is False
    assert evidence["scoped_diff"]["target_node_ids"] == ["2"]
    assert evidence["scoped_diff"]["target_matched"] is False
    assert "target_mismatch" in evidence["scoped_diff"]["eligibility_blockers"]


def test_handle_agent_edit_revise_strips_target_scope_violation_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {
                "batch": 'loadimage.image = "other.png"\nsaveimage.filename_prefix = "after"',
                "message": "Changed the loader and save prefix.",
            },
            {
                "batch": "done()",
                "message": "Ready.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change node 2 filename prefix to after",
            "target_node_ids": ["2"],
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {"route": "revise", "task": "edit_graph"},
            "session_id": "revise-target-scope-violation",
            "max_batches": 3,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "noop"
    assert result["candidate"] is None
    assert result["apply_allowed"] is False
    assert result["report"]["read_only"] is True
    evidence = result["report"]["revision_evidence"]
    assert evidence["candidate_eligible"] is False
    assert evidence["no_candidate_reason"] == "no_changes"
    scoped = evidence["scoped_diff"]
    assert set(scoped["changed_nodes"]) == {"1", "2"}
    assert "target_scope_violation" in scoped["eligibility_blockers"]


def test_handle_agent_edit_revise_strips_confirmed_noop_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _batch_repl_provider()
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {"batch": "done()", "message": "Nothing to change."},
            {"batch": "done()", "message": "Confirmed nothing to change."},
        ]
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to before",
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {"route": "revise", "task": "edit_graph"},
            "session_id": "revise-confirmed-noop",
            "max_batches": 2,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "noop"
    assert result["candidate"] is None
    assert result["apply_allowed"] is False
    assert result["canvas_apply_allowed"] is False
    assert result["report"]["read_only"] is True
    evidence = result["report"]["revision_evidence"]
    assert evidence["candidate_eligible"] is False
    scoped = evidence["scoped_diff"]
    assert scoped["candidate_eligible"] is False
    assert scoped["has_diff"] is False
    assert "no_diff" in scoped["eligibility_blockers"]


def test_handle_agent_edit_revise_ignores_preexisting_assets_and_unknown_nodes_for_local_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack=None,
                inputs={
                    "ckpt_name": InputSpec(
                        "CHOICE",
                        required=False,
                        choices=["present.safetensors"],
                    )
                },
                outputs=[OutputSpec("MODEL", "MODEL")],
                source_provider="test",
                confidence=1.0,
            ),
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
    graph = {
        "nodes": [
            *(_ui_graph()["nodes"]),
            {
                "id": 3,
                "type": "CheckpointLoaderSimple",
                "widgets": [{"name": "ckpt_name"}],
                "widgets_values": ["missing.safetensors"],
            },
            {"id": 4, "type": "MissingPackNode", "widgets_values": []},
        ],
        "links": list(_ui_graph()["links"]),
    }
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {
                "batch": 'saveimage.filename_prefix = "after"',
                "message": "Adjusted the save prefix.",
            },
            {
                "batch": "done()",
                "message": "Ready.",
            },
        ]
    )

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "change the save prefix to after",
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {"route": "revise", "task": "edit_graph"},
            "session_id": "revise-readiness-blocked",
            "max_batches": 2,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert result["candidate"] is not None
    assert result["apply_allowed"] is True
    readiness = result["report"]["revision_evidence"]["readiness"]
    assert readiness["has_blockers"] is False
    assert readiness["missing_models"] == ["missing.safetensors"]
    assert readiness["missing_node_packs"] == ["MissingPackNode"]
    turn_dir = turn_dir_for(tmp_path, "revise-readiness-blocked", str(result["turn_id"]))
    assert (turn_dir / "model_request.json").exists()
    artifact = json.loads((turn_dir / "revision_evidence.json").read_text(encoding="utf-8"))
    assert artifact["revision_evidence"]["safe_candidate_possible"] is True
    assert artifact["revision_evidence"]["candidate_eligible"] is True
    assert artifact["revision_evidence"]["scoped_diff"]["changed_nodes"] == ["2"]
    assert artifact["revision_evidence"]["readiness"]["missing_models"] == [
        "missing.safetensors"
    ]


def test_handle_agent_edit_revise_parameter_tweak_reaches_provider_despite_missing_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack=None,
                inputs={
                    "ckpt_name": InputSpec(
                        "CHOICE",
                        required=False,
                        choices=["present.safetensors"],
                    )
                },
                outputs=[OutputSpec("MODEL", "MODEL")],
                source_provider="test",
                confidence=1.0,
            ),
            "ACN_AdvancedControlNetApply": NodeSchema(
                class_type="ACN_AdvancedControlNetApply",
                pack=None,
                inputs={"strength": InputSpec("FLOAT", required=False)},
                outputs=[],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )
    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "widgets": [{"name": "ckpt_name"}],
                "widgets_values": ["missing.safetensors"],
            },
            {
                "id": 56,
                "type": "ACN_AdvancedControlNetApply",
                "widgets": [{"name": "strength"}],
                "widgets_values": [0.5],
            },
        ],
        "links": [],
    }
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    captured_messages: list[list[dict[str, str]]] = []

    def _provider(messages):
        captured_messages.append(messages)
        return {
            "batch": "done()",
            "message": "No concrete graph change was emitted.",
        }

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "increase the ControlNet conditioning strength",
            "query": "increase the ControlNet conditioning strength",
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {"route": "revise", "task": "edit_graph"},
            "session_id": "revise-parameter-tweak-missing-model",
            "max_batches": 1,
        },
        schema_provider=provider,
        deepseek_client=_provider,
        session_root=tmp_path,
    )

    assert captured_messages, "concrete existing-node tweaks should reach provider"
    prompt = captured_messages[0][1]["content"]
    assert "Direct existing-node tweak fallback applies here" in prompt
    assert "No-op proof requirement" in prompt
    assert result["ok"] is True
    turn_dir = turn_dir_for(tmp_path, "revise-parameter-tweak-missing-model", str(result["turn_id"]))
    assert (turn_dir / "model_request.json").exists()


def test_handle_agent_edit_revise_parameter_tweak_candidate_ignores_preexisting_missing_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack=None,
                inputs={
                    "ckpt_name": InputSpec(
                        "CHOICE",
                        required=False,
                        choices=["present.safetensors"],
                    )
                },
                outputs=[OutputSpec("MODEL", "MODEL")],
                source_provider="test",
                confidence=1.0,
            ),
            "ACN_AdvancedControlNetApply": NodeSchema(
                class_type="ACN_AdvancedControlNetApply",
                pack=None,
                inputs={"strength": InputSpec("FLOAT", required=False)},
                outputs=[],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )
    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "widgets": [{"name": "ckpt_name"}],
                "widgets_values": ["missing.safetensors"],
            },
            {
                "id": 56,
                "type": "ACN_AdvancedControlNetApply",
                "widgets": [{"name": "strength"}],
                "widgets_values": [0.5],
            },
        ],
        "links": [],
    }
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    responses = iter(
        [
            {
                "batch": "acn_advancedcontrolnetapply.widget_0 = 0.85",
                "message": "Increased ControlNet strength.",
            },
            {"batch": "done()", "message": "Ready."},
        ]
    )

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "increase the ControlNet conditioning strength",
            "query": "increase the ControlNet conditioning strength",
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {"route": "revise", "task": "edit_graph"},
            "session_id": "revise-parameter-tweak-candidate-missing-model",
            "max_batches": 3,
        },
        schema_provider=provider,
        deepseek_client=lambda _messages: next(responses),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    evidence = result["report"]["revision_evidence"]
    assert evidence["candidate_eligible"] is True
    assert evidence["readiness"]["missing_models"] == ["missing.safetensors"]
    assert evidence["scoped_diff"]["eligibility_blockers"] == []


def test_handle_agent_edit_you_decide_pil_code_node_uses_classifier_summary_to_attempt_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack=None,
                inputs={
                    "ckpt_name": InputSpec(
                        "CHOICE",
                        required=False,
                        choices=["present.safetensors"],
                    )
                },
                outputs=[OutputSpec("MODEL", "MODEL")],
                source_provider="test",
                confidence=1.0,
            ),
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
        }
    )
    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "widgets": [{"name": "ckpt_name"}],
                "widgets_values": ["missing.safetensors"],
            },
            {"id": 2, "type": "MissingPackNode", "widgets_values": []},
        ],
        "links": [],
    }
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    captured_messages: list[list[dict[str, str]]] = []

    def _provider(messages):
        captured_messages.append(messages)
        return {
            "batch": "done()",
            "message": "No concrete graph change was emitted.",
        }

    result = handle_agent_edit(
        {
            "graph": graph,
            "task": "You decide",
            "query": "You decide",
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {
                "intent": "edit",
                "route": "revise",
                "task": "edit_graph",
                "plan_summary": (
                    "Add a PIL transformation code node to the video pipeline, "
                    "applying resize and color jitter to frames before video combine."
                ),
            },
            "session_id": "you-decide-pil-code-node",
            "max_batches": 1,
        },
        schema_provider=provider,
        deepseek_client=_provider,
        session_root=tmp_path,
    )

    assert captured_messages, "classifier-resolved PIL/code-node edits should reach provider"
    first_user_prompt = captured_messages[0][1]["content"]
    assert "Resolved executor plan/context" in first_user_prompt
    assert "Add a PIL transformation code node" in first_user_prompt
    assert "def vibecomfy.exec" in first_user_prompt
    assert result["ok"] is True
    assert result["outcome"]["kind"] == "noop"
    evidence = result["report"]["revision_evidence"]
    assert evidence["safe_candidate_possible"] is False
    turn_dir = turn_dir_for(tmp_path, "you-decide-pil-code-node", str(result["turn_id"]))
    assert (turn_dir / "model_request.json").exists()


def test_handle_agent_edit_empty_sd15_workflow_reaches_provider_with_seed_signatures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(
        {
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack=None,
                inputs={
                    "ckpt_name": InputSpec(
                        "CHOICE",
                        required=False,
                        choices=["v1-5-pruned-emaonly.safetensors"],
                    )
                },
                outputs=[
                    OutputSpec("MODEL", "MODEL"),
                    OutputSpec("CLIP", "CLIP"),
                    OutputSpec("VAE", "VAE"),
                ],
                source_provider="test",
                confidence=1.0,
            ),
            "CLIPTextEncode": NodeSchema(
                class_type="CLIPTextEncode",
                pack=None,
                inputs={
                    "text": InputSpec("STRING", required=True),
                    "clip": InputSpec("CLIP", required=True),
                },
                outputs=[OutputSpec("CONDITIONING", "CONDITIONING")],
                source_provider="test",
                confidence=1.0,
            ),
            "EmptyLatentImage": NodeSchema(
                class_type="EmptyLatentImage",
                pack=None,
                inputs={
                    "width": InputSpec("INT", required=False),
                    "height": InputSpec("INT", required=False),
                    "batch_size": InputSpec("INT", required=False),
                },
                outputs=[OutputSpec("LATENT", "LATENT")],
                source_provider="test",
                confidence=1.0,
            ),
            "KSampler": NodeSchema(
                class_type="KSampler",
                pack=None,
                inputs={
                    "model": InputSpec("MODEL", required=True),
                    "positive": InputSpec("CONDITIONING", required=True),
                    "negative": InputSpec("CONDITIONING", required=True),
                    "latent_image": InputSpec("LATENT", required=True),
                    "seed": InputSpec("INT", required=False),
                    "steps": InputSpec("INT", required=False),
                    "cfg": InputSpec("FLOAT", required=False),
                    "sampler_name": InputSpec("CHOICE", required=False, choices=["euler"]),
                    "scheduler": InputSpec("CHOICE", required=False, choices=["normal"]),
                    "denoise": InputSpec("FLOAT", required=False),
                },
                outputs=[OutputSpec("LATENT", "LATENT")],
                source_provider="test",
                confidence=1.0,
            ),
            "VAEDecode": NodeSchema(
                class_type="VAEDecode",
                pack=None,
                inputs={
                    "samples": InputSpec("LATENT", required=True),
                    "vae": InputSpec("VAE", required=True),
                },
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
    captured_messages: list[list[dict[str, str]]] = []

    def _provider(messages):
        captured_messages.append(messages)
        return {
            "batch": (
                'ckpt = CheckpointLoaderSimple(ckpt_name="v1-5-pruned-emaonly.safetensors")\n'
                'pos = CLIPTextEncode(text="a beautiful landscape", clip=ckpt.CLIP)\n'
                'neg = CLIPTextEncode(text="blurry, low quality", clip=ckpt.CLIP)\n'
                "latent = EmptyLatentImage(width=512, height=512, batch_size=1)\n"
                "sampler = KSampler(model=ckpt.MODEL, positive=pos.CONDITIONING, "
                "negative=neg.CONDITIONING, latent_image=latent.LATENT, seed=42, "
                'steps=20, cfg=7.0, sampler_name="euler", scheduler="normal", denoise=1.0)\n'
                "decode = VAEDecode(samples=sampler.LATENT, vae=ckpt.VAE)\n"
                'save = SaveImage(images=decode.IMAGE, filename_prefix="SD1.5")\n'
                "done()"
            ),
            "message": (
                "I created a standard SD1.5 text-to-image workflow with a "
                "CheckpointLoaderSimple, positive and negative CLIPTextEncode "
                "nodes, an EmptyLatentImage, KSampler, VAEDecode, and SaveImage."
            ),
        }

    result = handle_agent_edit(
        {
            "graph": {
                "config": {},
                "extra": {},
                "groups": [],
                "id": "empty-sd15",
                "last_link_id": 0,
                "last_node_id": 0,
                "links": [],
                "nodes": [],
                "version": 0.4,
            },
            "task": "Generate the standard SD1.5 workflow",
            "query": "Generate the standard SD1.5 workflow",
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {
                "effort": "medium",
                "implement": True,
                "intent": "edit",
                "plan_summary": (
                    "Create a standard SD1.5 text-to-image workflow with "
                    "CheckpointLoader, CLIPTextEncode, KSampler, VAE Decode, "
                    "and SaveImage."
                ),
                "research": False,
                "route": "revise",
                "task": "edit_graph",
            },
            "session_id": "empty-sd15-workflow",
            "max_batches": 1,
        },
        schema_provider=provider,
        deepseek_client=_provider,
        session_root=tmp_path,
    )

    assert captured_messages, "empty-canvas workflow generation should reach provider"
    first_user_prompt = captured_messages[0][1]["content"]
    assert "Resolved executor plan/context" in first_user_prompt
    assert "Create a standard SD1.5 text-to-image workflow" in first_user_prompt
    assert "def CheckpointLoaderSimple" in first_user_prompt
    assert "def CLIPTextEncode" in first_user_prompt
    assert "def KSampler" in first_user_prompt
    assert "def VAEDecode" in first_user_prompt
    assert "def SaveImage" in first_user_prompt
    system_prompt = captured_messages[0][0]["content"]
    assert "user-facing prose sentence" in system_prompt
    assert "Never respond with only a fenced block" in system_prompt
    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert result["message"].startswith("Added CheckpointLoaderSimple")
    assert "KSampler" in result["message"]
    assert "VAEDecode" in result["message"]
    assert "SaveImage" in result["message"]
    assert result["apply_allowed"] is True
    assert result["candidate"] is not None
    assert len(result["candidate"]["graph"]["nodes"]) == 7
    evidence = result["report"]["revision_evidence"]
    assert evidence["candidate_eligible"] is True
    assert evidence["scoped_diff"]["candidate_eligible"] is True
    assert evidence["scoped_diff"]["eligibility_blockers"] == []
    turn_dir = turn_dir_for(tmp_path, "empty-sd15-workflow", str(result["turn_id"]))
    assert (turn_dir / "model_request.json").exists()


def test_handle_agent_edit_no_gpu_runtime_request_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def _provider_must_not_run(_messages):
        raise AssertionError("provider should not run for no-GPU runtime request")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "run this workflow and show the output",
            "route": "revise",
            "executor_route": "revise",
            "provider_route": "codex",
            "executor_classification": {"route": "revise", "task": "edit_graph"},
            "runtime": {"execution_requested": True, "no_gpu_detected": True},
            "session_id": "revise-no-gpu-runtime",
            "max_batches": 1,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_provider_must_not_run,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "noop"
    assert result["candidate"] is None
    assert result["apply_allowed"] is False
    assert result["report"]["read_only"] is True
    assert result["report"]["graph_unchanged"] is True
    evidence = result["report"]["revision_evidence"]
    assert evidence["readiness"]["no_gpu_detected"] is True
    assert evidence["readiness"]["has_blockers"] is True
    turn_dir = turn_dir_for(tmp_path, "revise-no-gpu-runtime", str(result["turn_id"]))
    assert not (turn_dir / "model_request.json").exists()
    for fabricated_key in (
        "run_id",
        "run_state",
        "execution_result",
        "output_images",
        "generated_outputs",
    ):
        assert fabricated_key not in result


def test_handle_agent_edit_direct_clarify_has_no_candidate_or_apply_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "make that one stronger",
            "route": "clarify",
            "executor_route": "clarify",
            "provider_route": "codex",
            "session_id": "direct-clarify-no-candidate",
            "max_batches": 1,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: {
            "batch": 'clarify("Which node should I change?")',
            "message": "I need one detail.",
        },
        session_root=tmp_path,
    )

    assert result["outcome"]["kind"] == "clarify"
    assert result["message"] == "Which node should I change?"
    for forbidden in (
        "candidate",
        "graph",
        "candidate_graph",
        "apply_eligible",
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
    ):
        assert forbidden not in result


def test_no_chat_json_for_pre_allocation_validation_failure() -> None:
    """Early pre-allocation validation failures (e.g. missing ``task``) do
    not write ``chat.json``."""
    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
        },
        schema_provider=_batch_repl_provider(),
        session_root=Path("/tmp/test-pre-alloc-failure"),
    )

    assert result.get("ok") is False
    # 'task' missing -> pre-allocation failure; no turn_dir should exist
    assert "turn_id" not in result


# ── T5: Backend reader/detail route tests ────────────────────────────────────


def _write_chat_artifact(
    turn_dir: Path, session_id: str, turn_id: str, user_text: str, agent_text: str
) -> None:
    """Write a minimal chat.json for a single turn."""
    turn_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "session_id": session_id,
        "turn_id": turn_id,
        "messages": [
            {"role": "user", "text": user_text, "turn_id": turn_id},
            {"role": "agent", "text": agent_text, "turn_id": turn_id},
        ],
    }
    (turn_dir / "chat.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


def _write_request_response_fallback(
    turn_dir: Path, task: str, agent_message: str
) -> None:
    """Write request.json + response.json (no chat.json) for fallback testing."""
    turn_dir.mkdir(parents=True, exist_ok=True)
    (turn_dir / "request.json").write_text(
        json.dumps({"task": task}) + "\n", encoding="utf-8"
    )
    (turn_dir / "response.json").write_text(
        json.dumps({"message": agent_message, "ok": True}) + "\n",
        encoding="utf-8",
    )


def _assert_no_public_session_json_internals(
    value: object,
    *,
    forbidden_values: tuple[str, ...],
    path_fragment: str,
) -> None:
    forbidden_keys = {
        "session_path",
        "turns_dir",
        "turn_path",
        "detail_json_path",
        "request.json",
        "response.json",
        "chat.json",
        "raw_prompt",
        "prompt_budget",
        "debug_payload",
        "raw_session_state",
        "provider_diagnostics",
        "audit_ref",
        "audit_path",
        "batch_turns",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            assert key not in forbidden_keys
            _assert_no_public_session_json_internals(
                item,
                forbidden_values=forbidden_values,
                path_fragment=path_fragment,
            )
        return
    if isinstance(value, list):
        for item in value:
            _assert_no_public_session_json_internals(
                item,
                forbidden_values=forbidden_values,
                path_fragment=path_fragment,
            )
        return
    if isinstance(value, str):
        assert path_fragment not in value
        for forbidden in forbidden_values:
            assert forbidden not in value


def test_read_session_chat_deterministic_sorting(tmp_path: Path) -> None:
    """Turn directories are read in deterministic sorted order (zero-padded integers)."""
    session_id = "sort-test"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"

    # Create turns out of order: 0003, 0001, 0002, 0010, 0000
    for tid in ("0003", "0001", "0002", "0010", "0000"):
        _write_chat_artifact(
            turns_dir / tid, session_id, tid,
            f"user {tid}", f"agent {tid}",
        )

    result = read_session_chat(tmp_path, session_id, max_messages=20)
    assert result["ok"] is True
    messages = result["messages"]
    # Should be sorted: 0000, 0001, 0002, 0003, 0010 → 10 messages (2 per turn)
    assert len(messages) == 10
    assert messages[0]["turn_id"] == "0000"
    assert messages[2]["turn_id"] == "0001"
    assert messages[4]["turn_id"] == "0002"
    assert messages[6]["turn_id"] == "0003"
    assert messages[8]["turn_id"] == "0010"


def test_read_session_chat_last_five_messages(tmp_path: Path) -> None:
    """Returns exactly the last five display messages in chronological order."""
    session_id = "last-five-test"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"

    # Create 5 turns (2 messages each = 10 messages total)
    for tid in ("0000", "0001", "0002", "0003", "0004"):
        _write_chat_artifact(
            turns_dir / tid, session_id, tid,
            f"user-{tid}", f"agent-{tid}",
        )

    result = read_session_chat(tmp_path, session_id, max_messages=5)
    assert result["ok"] is True
    messages = result["messages"]
    # Default max_messages=5; last 5 of 10 chronological messages
    assert len(messages) == 5
    # Should be: agent-0002, user-0003, agent-0003, user-0004, agent-0004
    assert messages[0]["role"] == "agent"
    assert messages[0]["turn_id"] == "0002"
    assert messages[1]["role"] == "user"
    assert messages[1]["turn_id"] == "0003"
    assert messages[4]["role"] == "agent"
    assert messages[4]["turn_id"] == "0004"


def test_read_session_chat_default_display_window_returns_more_than_five_messages(
    tmp_path: Path,
) -> None:
    session_id = "default-window-test"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"

    for index in range(9):
        tid = f"{index:04d}"
        _write_chat_artifact(
            turns_dir / tid, session_id, tid,
            f"user-{tid}", f"agent-{tid}",
        )

    result = read_session_chat(tmp_path, session_id)

    assert result["ok"] is True
    assert len(result["messages"]) == 18
    assert result["messages"][0]["turn_id"] == "0000"
    assert result["messages"][-1]["turn_id"] == "0008"


def test_agent_edit_chat_endpoint_defaults_to_bounded_fifty_message_window(
    tmp_path: Path,
) -> None:
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")
    session_id = "endpoint-window-test"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"

    for index in range(30):
        tid = f"{index:04d}"
        _write_chat_artifact(
            turns_dir / tid, session_id, tid,
            f"user-{tid}", f"agent-{tid}",
        )

    default_result = routes._handle_agent_edit_chat(
        {"session_id": session_id},
        session_root=tmp_path,
    )
    oversized_result = routes._handle_agent_edit_chat(
        {"session_id": session_id, "max_messages": "500"},
        session_root=tmp_path,
    )

    assert default_result["ok"] is True
    assert default_result["outcome"]["kind"] == "noop"
    assert len(default_result["messages"]) == 50
    assert default_result["messages"][0]["turn_id"] == "0005"
    assert oversized_result["ok"] is True
    assert oversized_result["outcome"]["kind"] == "noop"
    assert len(oversized_result["messages"]) == 50


def test_agent_edit_chat_endpoint_projects_raw_rehydrate_payload_at_route_boundary(
    tmp_path: Path,
) -> None:
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")
    session_id = "endpoint-public-rehydrate"
    turn_id = "0000"
    turn_dir = session_dir_for(tmp_path, session_id) / "turns" / turn_id
    turn_dir.mkdir(parents=True, exist_ok=True)
    chat_path = turn_dir / "chat.json"
    raw_change_details = {
        "raw_prompt": "internal prompt must stay persisted",
        "batch_turns": [
            {
                "message": "Validated compact route diagnostic.",
                "stage": "queue_validate",
                "ok": False,
                "debug_payload": {"trace": "private"},
            }
        ],
    }
    chat_path.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "messages": [
                    {"role": "user", "text": "user request", "turn_id": turn_id},
                    {
                        "role": "agent",
                        "text": "agent response",
                        "turn_id": turn_id,
                        "change_details": raw_change_details,
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    raw_result = read_session_chat(tmp_path, session_id, max_messages=10)
    raw_agent = raw_result["messages"][-1]
    assert "session_path" in raw_result
    assert "detail_json_path" in raw_result
    assert "change_details" in raw_agent
    assert "batch_turns" in raw_agent["change_details"]

    public_result = routes._handle_agent_edit_chat(
        {"session_id": session_id, "max_messages": 10},
        session_root=tmp_path,
    )

    assert public_result["ok"] is True
    assert public_result["messages"][-1] == {
        "role": "agent",
        "text": "agent response",
        "turn_id": turn_id,
        "timestamp": raw_agent["timestamp"],
    }
    assert "session_path" not in public_result
    assert "detail_json_path" not in public_result
    assert "change_details" not in public_result["messages"][-1]
    assert {
        "turn_id": turn_id,
        "source": "messages.change_details.batch_turns[0]",
        "message": "Validated compact route diagnostic.",
    } in public_result["diagnostics"]
    persisted = json.loads(chat_path.read_text(encoding="utf-8"))
    assert persisted["messages"][-1]["change_details"]["raw_prompt"] == "internal prompt must stay persisted"


def test_read_session_chat_fallback_from_request_response(tmp_path: Path) -> None:
    """Falls back to request.json + response.json when chat.json is absent."""
    session_id = "fallback-test"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"
    turn_dir = turns_dir / "0000"

    _write_request_response_fallback(turn_dir, "add a node", "I added a node.")

    result = read_session_chat(tmp_path, session_id, max_messages=5)
    assert result["ok"] is True
    messages = result["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["text"] == "add a node"
    assert messages[1]["role"] == "agent"
    assert "I added a node" in messages[1]["text"]


def test_read_session_chat_skips_turns_missing_artifacts(tmp_path: Path) -> None:
    """Skips turn directories that have no chat.json and no request.json+response.json."""
    session_id = "skip-test"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"

    # Turn 0000: valid chat.json
    _write_chat_artifact(
        turns_dir / "0000", session_id, "0000",
        "user-0", "agent-0",
    )
    # Turn 0001: empty dir (no artifacts)
    (turns_dir / "0001").mkdir(parents=True, exist_ok=True)
    # Turn 0002: valid fallback (request.json + response.json, no chat.json)
    _write_request_response_fallback(
        turns_dir / "0002", "do something", "Did something.",
    )
    # Turn 0003: corrupted json (unreadable)
    (turns_dir / "0003").mkdir(parents=True, exist_ok=True)
    (turns_dir / "0003" / "chat.json").write_text("not valid json", encoding="utf-8")
    # Turn 0004: valid chat.json
    _write_chat_artifact(
        turns_dir / "0004", session_id, "0004",
        "user-4", "agent-4",
    )

    result = read_session_chat(tmp_path, session_id, max_messages=20)
    assert result["ok"] is True
    messages = result["messages"]
    # Turns 0001 (empty) and 0003 (corrupted) should be skipped
    # Turns 0000 (2 msgs), 0002 (2 msgs), 0004 (2 msgs) = 6 messages
    assert len(messages) == 6
    turn_ids = {m["turn_id"] for m in messages}
    assert turn_ids == {"0000", "0002", "0004"}


def test_read_session_chat_sanitized_session_enforcement(tmp_path: Path) -> None:
    """Session IDs with path-traversal characters are sanitized before use."""
    malicious_id = "../../etc/passwd"
    safe_id = _safe_session_id(malicious_id)
    turns_dir = session_dir_for(tmp_path, safe_id) / "turns"

    _write_chat_artifact(
        turns_dir / "0000", safe_id, "0000",
        "legit user", "legit agent",
    )

    result = read_session_chat(tmp_path, malicious_id, max_messages=5)
    # Must succeed — the sanitized id maps to the same directory we wrote
    assert result["ok"] is True
    assert result["session_id"] == safe_id
    assert result["session_path"] == str(session_dir_for(tmp_path, safe_id))
    assert result["session_path_resolved"] == str(session_dir_for(tmp_path, safe_id).resolve())
    assert malicious_id not in result["session_path"]
    assert ".." not in result["session_path"]
    assert len(result["messages"]) == 2


def test_read_session_chat_metadata_fields(tmp_path: Path) -> None:
    """Returns session_path, latest_turn_path, and detail metadata."""
    session_id = "meta-test"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"

    _write_chat_artifact(
        turns_dir / "0000", session_id, "0000",
        "first user", "first agent",
    )
    _write_chat_artifact(
        turns_dir / "0001", session_id, "0001",
        "second user", "second agent",
    )

    result = read_session_chat(tmp_path, session_id, max_messages=5)
    assert result["ok"] is True
    assert "session_path" in result
    assert result["session_path"].endswith(session_id)
    assert result["session_path_resolved"] == str(session_dir_for(tmp_path, session_id).resolve())
    assert result["latest_turn_id"] == "0001"
    assert "detail_json_path" in result
    assert result["detail_json_path"] is not None
    assert "response.json" in result["detail_json_path"]
    assert result["detail_json_path_resolved"] == str(
        (turns_dir / "0001" / "response.json").resolve()
    )


def test_read_session_chat_missing_session_reports_exists_false(tmp_path: Path) -> None:
    result = read_session_chat(tmp_path, "deleted-session", max_messages=5)

    assert result["ok"] is True
    assert result["exists"] is False
    assert result["session_id"] == "deleted-session"
    assert result["messages"] == []
    assert result["latest_candidate"] is None


def test_read_session_chat_returns_latest_open_candidate_state(tmp_path: Path) -> None:
    session_id = "rehydrate-candidate"
    session_dir = session_dir_for(tmp_path, session_id)
    turn_dir = session_dir / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    graph = {"nodes": [{"id": 2, "type": "SaveImage"}], "links": []}
    response = {
        "ok": True,
        "session_id": session_id,
        "turn_id": "0001",
        "message": "Candidate ready.",
        "graph": graph,
        "candidate_graph_hash": "candidate-hash",
        "submit_graph_hash": "submit-hash",
        "canvas_apply_allowed": True,
        "apply_allowed": True,
        "queue_allowed": False,
        "apply_eligibility": {
            "applyable": True,
            "reason": "queue_blocked_warning",
            "message": "Apply is allowed, but Queue remains blocked for this candidate.",
            "warnings": ["queue_blocked"],
        },
        "outcome": {"kind": "edit", "changes": []},
        "report": {"change": {"content_edits": {"edited": ["2"]}}},
    }
    (turn_dir / "request.json").write_text(json.dumps({"task": "edit"}), encoding="utf-8")
    (turn_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")
    (turn_dir / "candidate.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (session_dir / "session_state.json").write_text(
        json.dumps(
            {
                "turns": {
                    "0001": {
                        "state": "candidate",
                        "candidate_graph_hash": "candidate-hash",
                        "submit_graph_hash": "submit-hash",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = read_session_chat(tmp_path, session_id, max_messages=5)

    latest = result["latest_candidate"]
    assert latest["turn_id"] == "0001"
    assert latest["graph"] == graph
    assert latest["candidate_graph_hash"] == "candidate-hash"
    assert latest["apply_eligibility"]["reason"] == "queue_blocked_warning"
    assert latest["queue_allowed"] is False


def test_conversation_with_candidate_reference_appends_compact_context() -> None:
    messages = [{"role": "user", "text": "Make it stronger"}]
    augmented = _conversation_with_candidate_reference(
        messages,
        {
            "turn_id": "0003",
            "outcome": {"kind": "candidate"},
            "change_details": {
                "operations": [
                    {"summary": "changed KSampler steps"},
                    {"field_path": "nodes.2.widgets_values.1"},
                ]
            },
        },
    )

    assert augmented is not None
    assert augmented[-1]["role"] == "agent"
    assert "Latest candidate reference" in augmented[-1]["text"]
    assert "turn=0003" in augmented[-1]["text"]
    assert "changed KSampler steps" in augmented[-1]["text"]


def test_read_session_json_turn_summaries_and_artifacts(tmp_path: Path) -> None:
    """read_session_json returns sorted turn summaries with artifact paths."""
    session_id = "session-json-test"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"

    # Turn 0000: full chat.json + request.json + response.json
    td0 = turns_dir / "0000"
    _write_chat_artifact(td0, session_id, "0000", "user-0", "agent-0")
    (td0 / "request.json").write_text(
        json.dumps({"task": "user-0"}) + "\n", encoding="utf-8"
    )
    (td0 / "response.json").write_text(
        json.dumps({"message": "agent-0", "ok": True}) + "\n", encoding="utf-8"
    )

    # Turn 0001: fallback only (request.json + response.json, no chat.json)
    _write_request_response_fallback(
        turns_dir / "0001", "fallback task", "fallback response",
    )

    result = read_session_json(tmp_path, session_id, max_messages=10)
    assert result["ok"] is True
    assert result["session_id"] == session_id
    assert result["turn_count"] == 2
    assert len(result["turns"]) == 2

    # Turn 0000 should have all three artifacts
    t0 = result["turns"][0]
    assert t0["turn_id"] == "0000"
    assert t0["turn_path"].endswith("/turns/0000")
    assert "chat.json" in t0
    assert "request.json" in t0
    assert "response.json" in t0
    assert t0["chat.json"].endswith("/chat.json")
    assert t0["request.json"].endswith("/request.json")
    assert t0["response.json"].endswith("/response.json")
    assert t0.get("message_count") == 2

    # Turn 0001 should have only request.json and response.json
    t1 = result["turns"][1]
    assert t1["turn_id"] == "0001"
    assert t1["turn_path"].endswith("/turns/0001")
    assert "chat.json" not in t1
    assert "request.json" in t1
    assert "response.json" in t1
    assert t1["request.json"].endswith("/request.json")
    assert t1["response.json"].endswith("/response.json")
    assert result["session_path"].endswith(f"/{session_id}")
    assert result["turns_dir"].endswith(f"/{session_id}/turns")
    assert result["detail_json_path"].endswith("/turns/0001/response.json")

    # Last-five messages should be present
    assert "messages" in result
    assert len(result["messages"]) == 4  # 2 turns × 2 messages


def test_session_json_public_route_projects_artifact_paths_to_boolean_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")
    edit_module = importlib.import_module("vibecomfy.comfy_nodes.agent.edit")
    monkeypatch.setattr(edit_module, "_SESSION_ROOT", tmp_path)

    registered: dict[tuple[str, str], Any] = {}

    class _Routes:
        def post(self, path):
            def _decorator(fn):
                registered[("POST", path)] = fn
                return fn
            return _decorator

        def get(self, path):
            def _decorator(fn):
                registered[("GET", path)] = fn
                return fn
            return _decorator

    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.web = types.SimpleNamespace(
        json_response=lambda body, status=200: {"status": status, "body": body},
    )
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_module)

    session_id = "session-json-public-route"
    turn_id = "0000"
    turn_dir = session_dir_for(tmp_path, session_id) / "turns" / turn_id
    _write_chat_artifact(turn_dir, session_id, turn_id, "user-0", "agent-0")
    raw_chat = json.loads((turn_dir / "chat.json").read_text(encoding="utf-8"))
    raw_chat["session_path"] = str(session_dir_for(tmp_path, session_id))
    raw_chat["turn_path"] = str(turn_dir)
    raw_chat["raw_session_state"] = {
        "debug_payload": "RAW_SESSION_STATE_SENTINEL",
    }
    raw_chat["messages"][-1]["change_details"] = {
        "raw_prompt": "INTERNAL_RAW_PROMPT_SENTINEL",
        "prompt_budget": "PRIVATE_BUDGET_SENTINEL",
        "debug_payload": {"secret": "DEBUG_PAYLOAD_SENTINEL"},
        "raw_session_state": "RAW_SESSION_STATE_SENTINEL",
        "provider_diagnostics": ["PROVIDER_DIAGNOSTIC_SENTINEL"],
        "audit_ref": {"path": str(turn_dir / "audit.json")},
        "batch_turns": [
            {
                "code": "internal-debug",
                "message": "BATCH_TURN_SENTINEL",
            }
        ],
    }
    (turn_dir / "chat.json").write_text(
        json.dumps(raw_chat, indent=2) + "\n",
        encoding="utf-8",
    )
    (turn_dir / "request.json").write_text(
        json.dumps(
            {
                "task": "user-0",
                "raw_prompt": "INTERNAL_RAW_PROMPT_SENTINEL",
                "debug_payload": "DEBUG_PAYLOAD_SENTINEL",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (turn_dir / "response.json").write_text(
        json.dumps(
            {
                "message": "agent-0",
                "ok": True,
                "provider_diagnostics": ["PROVIDER_DIAGNOSTIC_SENTINEL"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (turn_dir / "audit.json").write_text(
        json.dumps({"path": str(turn_dir / "audit.json")}) + "\n",
        encoding="utf-8",
    )

    raw_result = read_session_json(tmp_path, session_id, max_messages=10)
    raw_turn = raw_result["turns"][0]
    assert raw_result["session_path"].endswith(f"/{session_id}")
    assert raw_result["turns_dir"].endswith(f"/{session_id}/turns")
    assert raw_result["detail_json_path"].endswith("/turns/0000/response.json")
    assert raw_turn["turn_path"].endswith("/turns/0000")
    assert raw_turn["request.json"].endswith("/request.json")
    assert raw_turn["response.json"].endswith("/response.json")
    assert raw_turn["chat.json"].endswith("/chat.json")

    class _Request:
        query = {"session_id": session_id}

    routes.register_agent_edit_routes(types.SimpleNamespace(routes=_Routes()))
    session_json_route = registered[("GET", "/vibecomfy/agent-edit/session-json")]
    response = asyncio.run(session_json_route(_Request()))

    assert response["status"] == 200
    body = response["body"]
    assert body["ok"] is True
    assert body["session_id"] == session_id
    assert "session_path" not in body
    assert "turns_dir" not in body
    assert "detail_json_path" not in body
    assert body["messages"] == [
        {"role": "user", "text": "user-0", "turn_id": turn_id},
        {"role": "agent", "text": "agent-0", "turn_id": turn_id},
    ]

    public_turn = body["turns"][0]
    assert public_turn == {
        "turn_id": turn_id,
        "message_count": 2,
        "artifacts": {
            "has_request": True,
            "has_response": True,
            "has_chat": True,
            "has_detail": True,
            "has_audit": False,
        },
    }
    assert set(public_turn["artifacts"]) == {
        "has_request",
        "has_response",
        "has_chat",
        "has_detail",
        "has_audit",
    }
    assert "request.json" not in public_turn
    assert "response.json" not in public_turn
    assert "chat.json" not in public_turn
    _assert_no_public_session_json_internals(
        body,
        forbidden_values=(
            "INTERNAL_RAW_PROMPT_SENTINEL",
            "PRIVATE_BUDGET_SENTINEL",
            "DEBUG_PAYLOAD_SENTINEL",
            "RAW_SESSION_STATE_SENTINEL",
            "PROVIDER_DIAGNOSTIC_SENTINEL",
            "BATCH_TURN_SENTINEL",
        ),
        path_fragment=str(tmp_path),
    )


def test_chat_route_honors_max_messages_query_parameter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /vibecomfy/agent-edit/chat passes max_messages to read_session_chat."""
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")
    edit_module = importlib.import_module("vibecomfy.comfy_nodes.agent.edit")
    monkeypatch.setattr(edit_module, "_SESSION_ROOT", tmp_path)

    registered: dict[tuple[str, str], Any] = {}

    class _Routes:
        def post(self, path):
            def _decorator(fn):
                registered[("POST", path)] = fn
                return fn
            return _decorator

        def get(self, path):
            def _decorator(fn):
                registered[("GET", path)] = fn
                return fn
            return _decorator

    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.web = types.SimpleNamespace(
        json_response=lambda body, status=200: {"status": status, "body": body},
    )
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_module)

    session_id = "chat-route-max-messages"
    for tid in ("0000", "0001"):
        _write_chat_artifact(
            session_dir_for(tmp_path, session_id) / "turns" / tid,
            session_id,
            tid,
            f"user-{tid}",
            f"agent-{tid}",
        )

    routes.register_agent_edit_routes(types.SimpleNamespace(routes=_Routes()))
    chat_route = registered[("GET", "/vibecomfy/agent-edit/chat")]

    class _Request:
        query = {"session_id": session_id, "max_messages": "1"}

    response = asyncio.run(chat_route(_Request()))
    assert response["status"] == 200
    body = response["body"]
    assert body["ok"] is True
    assert len(body["messages"]) == 1
    assert body["messages"][0]["text"] == "agent-0001"


def test_read_session_json_empty_session(tmp_path: Path) -> None:
    """Empty session (no turns) returns empty lists with ok=True."""
    session_id = "empty-session"
    # Don't create a turns directory at all
    result = read_session_json(tmp_path, session_id)
    assert result["ok"] is True
    assert result["turn_count"] == 0
    assert result["turns"] == []
    assert result["messages"] == []
    assert result["latest_turn_id"] is None


def test_read_session_json_sanitized_session(tmp_path: Path) -> None:
    """Sanitized session id enforcement in read_session_json."""
    malicious_id = "../escape"
    safe_id = _safe_session_id(malicious_id)
    turns_dir = session_dir_for(tmp_path, safe_id) / "turns"

    _write_chat_artifact(
        turns_dir / "0000", safe_id, "0000",
        "safe user", "safe agent",
    )

    result = read_session_json(tmp_path, malicious_id, max_messages=5)
    assert result["ok"] is True
    assert result["session_id"] == safe_id
    assert len(result["turns"]) == 1


# ---------------------------------------------------------------------------
# T1: Focused chat contract tests — /chat payload shape including
# latest_candidate and agent-message outcomes, no user-message outcomes
# ---------------------------------------------------------------------------


def _write_chat_artifact_with_outcome(
    turn_dir: Path, session_id: str, turn_id: str,
    user_text: str, agent_text: str, outcome: dict[str, Any] | None,
) -> None:
    """Write a chat.json with an optional outcome on the agent message."""
    turn_dir.mkdir(parents=True, exist_ok=True)
    agent_msg: dict[str, Any] = {
        "role": "agent",
        "text": agent_text,
        "turn_id": turn_id,
    }
    if outcome is not None:
        agent_msg["outcome"] = outcome
    record = {
        "session_id": session_id,
        "turn_id": turn_id,
        "messages": [
            {"role": "user", "text": user_text, "turn_id": turn_id},
            agent_msg,
        ],
    }
    (turn_dir / "chat.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


def test_chat_agent_message_carries_outcome_when_present_in_chat_json(
    tmp_path: Path,
) -> None:
    """When chat.json includes an outcome on the agent message,
    read_session_chat preserves it."""
    session_id = "chat-outcome-test"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"
    _write_chat_artifact_with_outcome(
        turns_dir / "0000", session_id, "0000",
        "user request", "agent response",
        {"kind": "candidate", "changes": []},
    )

    result = read_session_chat(tmp_path, session_id, max_messages=5)
    assert result["ok"] is True
    messages = result["messages"]
    assert len(messages) == 2
    agent_msg = next(m for m in messages if m["role"] == "agent")
    assert "outcome" in agent_msg
    assert agent_msg["outcome"]["kind"] == "candidate"


def test_chat_agent_message_outcome_kinds_are_public_union_members(
    tmp_path: Path,
) -> None:
    """Agent message outcomes in chat.json use the closed public union:
    candidate, noop, clarify, error."""
    session_id = "chat-outcome-kinds"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"

    for index, kind in enumerate(PUBLIC_OUTCOME_KINDS):
        outcome: dict[str, Any] = {"kind": kind}
        if kind == "candidate":
            outcome["changes"] = [{"uid": f"n{index}", "field_path": "x", "old": 0, "new": 1}]
        elif kind == "noop":
            outcome["reason"] = f"reason-{index}"
        elif kind == "clarify":
            outcome["question"] = f"question-{index}"
        elif kind == "error":
            outcome["failure_kind"] = "TimeoutError"
            outcome["stage"] = "agent_response"
        _write_chat_artifact_with_outcome(
            turns_dir / f"{index:04d}", session_id, f"{index:04d}",
            f"user-{index}", f"agent-{index}", outcome,
        )

    result = read_session_chat(tmp_path, session_id, max_messages=20)
    agent_msgs = [m for m in result["messages"] if m["role"] == "agent"]
    assert len(agent_msgs) == len(PUBLIC_OUTCOME_KINDS)
    for msg in agent_msgs:
        assert "outcome" in msg, f"agent message missing outcome: {msg}"
        kind = msg["outcome"]["kind"]
        assert kind in PUBLIC_OUTCOME_KINDS, f"unexpected outcome kind {kind!r}"


@pytest.mark.parametrize(
    "persisted_outcome",
    [
        {"kind": "error", "failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        {"kind": "error", "failureKind": FailureKind.STALE_STATE_MISMATCH.value},
    ],
)
def test_stamped_message_outcome_preserves_persisted_minimal_error_outcomes(
    persisted_outcome: dict[str, Any],
) -> None:
    """Persisted chat.json outcomes may predate strict live error fields.

    Rehydration stamping owns compatibility normalization so frontend render code
    does not need to infer missing error metadata from historical artifacts.
    """
    stamped = _stamped_message_outcome(persisted_outcome, stage="chat")

    assert stamped == {
        "kind": "error",
        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
        "stage": "chat",
        "retryable": False,
        "next_action": "resubmit from the current canvas",
        "graph_unchanged": True,
        "agent_failure_context": {
            "explanation": "The submitted graph no longer matches the current canvas. Resubmit."
        },
    }


@pytest.mark.parametrize(
    "persisted_outcome",
    [
        {"kind": "error", "failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        {"kind": "error", "failureKind": FailureKind.STALE_STATE_MISMATCH.value},
    ],
)
def test_stamped_turn_response_outcome_preserves_persisted_minimal_error_outcomes(
    persisted_outcome: dict[str, Any],
) -> None:
    """Persisted response.json outcomes survive fallback chat rehydration.

    The safe defaults are applied at the edit.py stamping helper rather than by
    browser selectors or render paths.
    """
    stamped = _stamped_turn_response_outcome(
        {"ok": False, "outcome": persisted_outcome},
        stage="submit",
    )

    assert stamped == {
        "kind": "error",
        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
        "stage": "submit",
        "retryable": False,
        "next_action": "resubmit from the current canvas",
        "graph_unchanged": True,
        "agent_failure_context": {
            "explanation": "The submitted graph no longer matches the current canvas. Resubmit."
        },
    }


def test_chat_user_messages_never_carry_outcome(
    tmp_path: Path,
) -> None:
    """User messages in chat.json never carry outcome metadata."""
    session_id = "chat-no-user-outcome"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"
    # Write chat with outcome on agent only
    _write_chat_artifact_with_outcome(
        turns_dir / "0000", session_id, "0000",
        "user says hi", "agent responds",
        {"kind": "candidate", "changes": []},
    )
    # Also write a basic chat without outcome
    _write_chat_artifact(
        turns_dir / "0001", session_id, "0001",
        "another user message", "another agent message",
    )

    result = read_session_chat(tmp_path, session_id, max_messages=10)
    user_msgs = [m for m in result["messages"] if m["role"] == "user"]
    assert len(user_msgs) >= 1
    for msg in user_msgs:
        assert "outcome" not in msg, f"user message should not carry outcome: {msg}"


def test_chat_fallback_agent_message_derives_outcome_from_turn_response(
    tmp_path: Path,
) -> None:
    """When read_session_chat falls back to request.json + response.json
    (no chat.json), the agent message derives a normalized public outcome
    from response.json."""
    session_id = "chat-fallback-no-outcome"
    turns_dir = session_dir_for(tmp_path, session_id) / "turns"
    turn_dir = turns_dir / "0000"
    _write_request_response_fallback(
        turn_dir, "do something", "Did something."
    )
    response_path = turn_dir / "response.json"
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["outcome"] = {"kind": "edit", "changes": []}
    response_path.write_text(json.dumps(response), encoding="utf-8")

    result = read_session_chat(tmp_path, session_id, max_messages=5)
    agent_msgs = [m for m in result["messages"] if m["role"] == "agent"]
    assert len(agent_msgs) == 1
    assert agent_msgs[0]["outcome"]["kind"] == "candidate"


def test_chat_agent_message_derives_outcome_from_turn_response_when_chat_json_omits_it(
    tmp_path: Path,
) -> None:
    session_id = "chat-derive-from-response"
    turn_dir = session_dir_for(tmp_path, session_id) / "turns" / "0000"
    _write_chat_artifact(turn_dir, session_id, "0000", "user request", "agent response")
    (turn_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "turn_id": "0000",
                "message": "Candidate ready.",
                "graph": {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []},
                "outcome": {"kind": "edit+clarify", "changes": [], "question": "before or after?"},
            }
        ),
        encoding="utf-8",
    )

    result = read_session_chat(tmp_path, session_id, max_messages=5)
    agent_msg = next(m for m in result["messages"] if m["role"] == "agent")
    assert agent_msg["outcome"] == {
        "kind": "candidate",
        "changes": [],
        "question": "before or after?",
        "clarification": {"message": "before or after?"},
    }


def test_latest_candidate_in_chat_response_includes_outcome(
    tmp_path: Path,
) -> None:
    """The /chat response's latest_candidate payload should include an
    outcome when the underlying response.json has one."""
    session_id = "latest-candidate-outcome"
    session_dir = session_dir_for(tmp_path, session_id)
    turn_dir = session_dir / "turns" / "0000"
    turn_dir.mkdir(parents=True)
    graph = {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []}
    response = {
        "ok": True,
        "session_id": session_id,
        "turn_id": "0000",
        "message": "Candidate with outcome.",
        "graph": graph,
        "candidate_graph_hash": "hash-abc",
        "canvas_apply_allowed": True,
        "apply_allowed": True,
        "queue_allowed": False,
        "apply_eligibility": {
            "applyable": True,
            "reason": "queue_blocked_warning",
            "message": "Apply allowed, Queue blocked.",
            "warnings": ["queue_blocked"],
        },
        "outcome": {"kind": "candidate", "changes": [
            {"uid": "1", "field_path": "widgets_values.0", "old": "before", "new": "after"}
        ]},
    }
    (turn_dir / "request.json").write_text(
        json.dumps({"task": "edit"}), encoding="utf-8"
    )
    (turn_dir / "response.json").write_text(
        json.dumps(response), encoding="utf-8"
    )
    (turn_dir / "candidate.ui.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    (session_dir / "session_state.json").write_text(
        json.dumps({
            "turns": {
                "0000": {
                    "state": "candidate",
                    "candidate_graph_hash": "hash-abc",
                }
            }
        }),
        encoding="utf-8",
    )

    result = read_session_chat(tmp_path, session_id, max_messages=5)
    latest = result["latest_candidate"]
    assert latest is not None, "latest_candidate should be present"
    assert "outcome" in latest, (
        "latest_candidate should include outcome from response.json"
    )
    assert latest["outcome"]["kind"] == "candidate"
    assert len(latest["outcome"]["changes"]) == 1
    assert latest["outcome"]["changes"][0]["uid"] == "1"


def test_latest_candidate_in_chat_response_preserves_report_evidence(
    tmp_path: Path,
) -> None:
    """Reloaded candidate previews need the same compact report evidence as submit."""
    session_id = "latest-candidate-report"
    session_dir = session_dir_for(tmp_path, session_id)
    turn_dir = session_dir / "turns" / "0000"
    turn_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": 6, "type": "VAEDecode"},
            {"id": 34, "type": "vibecomfy.exec"},
        ],
        "links": [[59, 6, 0, 34, 0, "IMAGE"]],
    }
    report = {
        "revision_evidence": {
            "scoped_diff": {
                "summary": "2 changed node(s); 1 added link(s)",
                "has_diff": True,
                "changed_nodes": ["6", "34"],
                "added_links": [
                    {
                        "link_id": 59,
                        "origin_node": 6,
                        "origin_slot": 0,
                        "target_node": 34,
                        "target_slot": 0,
                        "type": "IMAGE",
                    }
                ],
            }
        }
    }
    response = {
        "ok": True,
        "session_id": session_id,
        "turn_id": "0000",
        "message": "Candidate with report.",
        "graph": graph,
        "candidate_graph_hash": "hash-report",
        "canvas_apply_allowed": True,
        "apply_allowed": True,
        "queue_allowed": False,
        "apply_eligibility": {
            "applyable": True,
            "reason": "queue_blocked_warning",
            "message": "Apply allowed, Queue blocked.",
            "warnings": ["queue_blocked"],
        },
        "report": report,
        "outcome": {"kind": "candidate", "changes": []},
    }
    (turn_dir / "request.json").write_text(
        json.dumps({"task": "edit"}), encoding="utf-8"
    )
    (turn_dir / "response.json").write_text(
        json.dumps(response), encoding="utf-8"
    )
    (turn_dir / "candidate.ui.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    (session_dir / "session_state.json").write_text(
        json.dumps({
            "turns": {
                "0000": {
                    "state": "candidate",
                    "candidate_graph_hash": "hash-report",
                }
            }
        }),
        encoding="utf-8",
    )

    result = read_session_chat(tmp_path, session_id, max_messages=5)
    latest = result["latest_candidate"]
    assert latest is not None
    assert latest["report"] == report

    public = public_chat_rehydrate_payload(result)
    assert public["latest_candidate"]["report"] == report


def test_latest_candidate_excludes_noop_turns_and_still_has_outcome(
    tmp_path: Path,
) -> None:
    """latest_candidate skips noop turns when searching for the latest
    candidate. When a candidate-turn is found, its outcome is included."""
    session_id = "latest-outcome-noop-skip"
    session_dir = session_dir_for(tmp_path, session_id)
    graph = {"nodes": [{"id": 7, "type": "KSampler"}], "links": []}

    # Turn 0000: noop (should be skipped)
    td0 = session_dir / "turns" / "0000"
    td0.mkdir(parents=True)
    (td0 / "request.json").write_text(
        json.dumps({"task": "noop task"}), encoding="utf-8"
    )
    (td0 / "response.json").write_text(
        json.dumps({
            "ok": True,
            "outcome": {"kind": "noop", "reason": "nothing to change"},
            "graph_unchanged": True,
            "apply_allowed": False,
        }),
        encoding="utf-8",
    )

    # Turn 0001: candidate (should be the latest)
    td1 = session_dir / "turns" / "0001"
    td1.mkdir(parents=True)
    (td1 / "request.json").write_text(
        json.dumps({"task": "real edit"}), encoding="utf-8"
    )
    (td1 / "response.json").write_text(
        json.dumps({
            "ok": True,
            "turn_id": "0001",
            "message": "Real candidate.",
            "graph": graph,
            "canvas_apply_allowed": True,
            "apply_allowed": True,
            "queue_allowed": True,
            "apply_eligibility": {
                "applyable": True,
                "reason": "applyable",
                "message": "Apply allowed.",
            },
            "outcome": {
                "kind": "candidate",
                "changes": [
                    {"uid": "7", "field_path": "widgets.seed", "old": 0, "new": 42}
                ],
            },
        }),
        encoding="utf-8",
    )
    (td1 / "candidate.ui.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )

    (session_dir / "session_state.json").write_text(
        json.dumps({
            "turns": {
                "0000": {"state": "rejected"},
                "0001": {"state": "candidate"},
            }
        }),
        encoding="utf-8",
    )

    result = read_session_chat(tmp_path, session_id, max_messages=5)
    latest = result["latest_candidate"]
    assert latest is not None
    assert latest["turn_id"] == "0001", "should skip noop turn 0000"
    assert "outcome" in latest, (
        "latest_candidate should include outcome"
    )
    assert latest["outcome"]["kind"] == "candidate"


def test_chat_endpoint_response_has_public_outcome_kind(
    tmp_path: Path,
) -> None:
    """The chat endpoint response (via _handle_agent_edit_chat) carries an
    outcome with a valid public kind."""
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")
    session_id = "chat-endpoint-outcome"
    result = routes._handle_agent_edit_chat(
        {"session_id": session_id},
        session_root=tmp_path,
    )
    # Even for a non-existent session, the chat endpoint returns ok=True
    # with a noop outcome.
    assert result["ok"] is True
    assert "outcome" in result
    assert result["outcome"]["kind"] in PUBLIC_OUTCOME_KINDS


def test_chat_agent_message_outcome_derivable_from_turn_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When handle_agent_edit completes successfully, the written chat.json
    agent message carries the response outcome (stamped by
    _write_turn_chat_artifact)."""
    _use_dev_full(monkeypatch)
    provider = _batch_repl_provider()

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "rename the save prefix",
            "session_id": "chat-derivable-outcome",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            '"before"', '"after"',
            "Renamed the save prefix.",
        ),
        session_root=tmp_path,
    )

    assert result.get("ok") is True
    turn_id = result["turn_id"]
    turn_dir = tmp_path / "chat-derivable-outcome" / "turns" / turn_id
    chat_path = turn_dir / "chat.json"
    assert chat_path.is_file(), "chat.json should be written for successful turn"

    chat = json.loads(chat_path.read_text(encoding="utf-8"))
    agent_msgs = [m for m in chat["messages"] if m["role"] == "agent"]
    assert len(agent_msgs) == 1
    agent_msg = agent_msgs[0]
    assert "outcome" in agent_msg, (
        "agent message in chat.json should carry outcome from response"
    )
    assert agent_msg["outcome"]["kind"] in PUBLIC_OUTCOME_KINDS, (
        f"outcome kind in chat should be a public kind, got {agent_msg['outcome']['kind']!r}"
    )


# ── session bundle + chat reasoning tests ─────────────────────────────────────


def test_read_session_chat_surfaces_trimmed_agent_reasoning(tmp_path: Path) -> None:
    """The chat endpoint carries a trimmed view of the agent's per-step reasoning
    so a reloaded panel's diagnostic report can show what the agent tried and the
    engine diagnostics — without shipping the bulky diff/statements."""
    from vibecomfy.comfy_nodes.agent.edit import read_session_chat

    session_id = "reasoning-trim"
    turn_dir = tmp_path / session_id / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    chat = {
        "messages": [
            {"role": "user", "text": "Add a VAE Decode", "turn_id": "0001"},
            {
                "role": "agent",
                "text": "Nothing needed changing.",
                "turn_id": "0001",
                "outcome": {"kind": "noop"},
                "change_details": {
                    "done_summary": "No edits applied.",
                    "batch_turns": [
                        {
                            "turn_number": 0,
                            "batch_ok": False,
                            "message": "I'll load ae.safetensors and wire a VAEDecode.",
                            "batch": "vae = VAELoader(vae_name='ae.safetensors')",
                            "diff": "HUGE DIFF " * 1000,  # bulky → must be dropped
                            "statements": [{"x": 1}],  # bulky → must be dropped
                            "diagnostics": [
                                {
                                    "code": "value_not_in_enum",
                                    "severity": "error",
                                    "message": "value 'ae.safetensors' is not in the declared enum.",
                                    "detail": {
                                        "input": "vae_name",
                                        "value": "ae.safetensors",
                                        "choices": ["pixel_space"],
                                    },
                                }
                            ],
                        }
                    ],
                },
            },
        ]
    }
    (turn_dir / "chat.json").write_text(json.dumps(chat), encoding="utf-8")

    result = read_session_chat(tmp_path, session_id)
    agent_msgs = [m for m in result["messages"] if m["role"] == "agent"]
    assert len(agent_msgs) == 1
    cd = agent_msgs[0].get("change_details")
    assert isinstance(cd, dict), "agent message must carry trimmed change_details"
    assert cd["done_summary"] == "No edits applied."
    steps = cd["batch_turns"]
    assert len(steps) == 1
    step = steps[0]
    assert step["batch_ok"] is False
    assert "ae.safetensors" in step["message"]
    assert "VAELoader" in step["batch"]
    # Bulky fields are trimmed out entirely.
    assert "diff" not in step
    assert "statements" not in step
    # The root-cause diagnostic and the valid enum choices survive.
    diag = step["diagnostics"][0]
    assert diag["code"] == "value_not_in_enum"
    assert diag["detail"]["choices"] == ["pixel_space"]


def test_read_session_bundle_bundles_text_and_binary_artifacts(tmp_path: Path) -> None:
    """read_session_bundle returns every artifact under a session dir.

    This is an explicit raw debug/report retention surface, not a normal public
    renderer payload. It intentionally remains exempt from
    _assert_no_public_session_json_internals so issue bundles keep raw evidence
    that projected browser routes must hide.
    """
    from vibecomfy.comfy_nodes.agent.edit import read_session_bundle

    session_id = "bundle-all"
    session_dir = tmp_path / session_id
    turn_dir = session_dir / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    raw_sentinel = "RAW_BUNDLE_RETENTION_SENTINEL"
    raw_path = str(turn_dir / "raw-debug.json")
    (turn_dir / "messages.jsonl").write_text(
        json.dumps(
            {
                "message": "hi",
                "raw_prompt": f"keep raw prompt {raw_sentinel}",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (turn_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "provider_diagnostics": [raw_sentinel],
                "audit_ref": {"path": raw_path},
            }
        ),
        encoding="utf-8",
    )
    (session_dir / "session_state.json").write_text(
        json.dumps(
            {
                "turns": {},
                "raw_session_state": {
                    "debug_payload": raw_sentinel,
                    "path": raw_path,
                },
            }
        ),
        encoding="utf-8",
    )
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x01\x02\x03"
    (turn_dir / "preview.png").write_bytes(png_bytes)

    result = read_session_bundle(tmp_path, session_id)
    assert result["ok"] is True and result["exists"] is True
    by_name = {f["name"]: f for f in result["files"]}

    assert "turns/0001/messages.jsonl" in by_name
    messages = json.loads(by_name["turns/0001/messages.jsonl"]["text"])
    assert messages["message"] == "hi"
    assert messages["raw_prompt"] == f"keep raw prompt {raw_sentinel}"
    response = json.loads(by_name["turns/0001/response.json"]["text"])
    assert response["provider_diagnostics"] == [raw_sentinel]
    assert response["audit_ref"]["path"] == raw_path
    session_state = json.loads(by_name["session_state.json"]["text"])
    assert session_state["raw_session_state"] == {
        "debug_payload": raw_sentinel,
        "path": raw_path,
    }
    assert "session_state.json" in by_name
    png = by_name["turns/0001/preview.png"]
    assert "base64" in png and "text" not in png
    assert base64.b64decode(png["base64"]) == png_bytes


def test_read_session_bundle_missing_session_returns_empty(tmp_path: Path) -> None:
    from vibecomfy.comfy_nodes.agent.edit import read_session_bundle

    result = read_session_bundle(tmp_path, "does-not-exist")
    assert result["ok"] is True
    assert result["exists"] is False
    assert result["files"] == []


def test_read_session_bundle_sanitized_session_enforcement(tmp_path: Path) -> None:
    from vibecomfy.comfy_nodes.agent.edit import read_session_bundle

    malicious_id = "../../bundle-session"
    safe_id = _safe_session_id(malicious_id)
    turn_dir = session_dir_for(tmp_path, safe_id) / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    (turn_dir / "response.json").write_text(
        json.dumps({"ok": True, "message": "contained bundle"}) + "\n",
        encoding="utf-8",
    )

    result = read_session_bundle(tmp_path, malicious_id)

    assert result["ok"] is True
    assert result["exists"] is True
    assert result["session_id"] == safe_id
    assert result["session_path"] == str(session_dir_for(tmp_path, safe_id))
    assert malicious_id not in result["session_path"]
    assert ".." not in result["session_path"]
    assert {entry["name"] for entry in result["files"]} == {"turns/0001/response.json"}


def test_read_session_bundle_records_oversize_skips(tmp_path: Path) -> None:
    from vibecomfy.comfy_nodes.agent.edit import read_session_bundle

    session_id = "bundle-skip"
    turn_dir = tmp_path / session_id / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    (turn_dir / "small.json").write_text("{}", encoding="utf-8")
    (turn_dir / "big.json").write_text("x" * 5000, encoding="utf-8")

    result = read_session_bundle(tmp_path, session_id, max_file_bytes=1000)
    by_name = {f["name"]: f for f in result["files"]}
    assert "turns/0001/small.json" in by_name
    skipped = {s["name"]: s for s in result["skipped"]}
    assert skipped.get("turns/0001/big.json", {}).get("reason") == "too_large"


def test_session_bundle_route_retains_raw_sentinels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP /vibecomfy/agent-edit/session-bundle remains a raw debug/report surface.

    This route-level regression test proves raw sentinel fields survive HTTP
    serialization, documenting the intentional exemption from normal public-payload
    projection assertions.
    """
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")
    edit_module = importlib.import_module("vibecomfy.comfy_nodes.agent.edit")
    monkeypatch.setattr(edit_module, "_SESSION_ROOT", tmp_path)

    registered: dict[tuple[str, str], Any] = {}

    class _Routes:
        def post(self, path):
            def _decorator(fn):
                registered[("POST", path)] = fn
                return fn
            return _decorator

        def get(self, path):
            def _decorator(fn):
                registered[("GET", path)] = fn
                return fn
            return _decorator

    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.web = types.SimpleNamespace(
        json_response=lambda body, status=200: {"status": status, "body": body},
    )
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_module)

    session_id = "bundle-route-raw"
    turn_dir = tmp_path / session_id / "turns" / "0000"
    turn_dir.mkdir(parents=True)
    (turn_dir / "request.json").write_text(
        json.dumps({"task": "user-0", "raw_prompt": "INTERNAL_RAW_PROMPT_SENTINEL"})
        + "\n",
        encoding="utf-8",
    )
    (turn_dir / "response.json").write_text(
        json.dumps(
            {
                "message": "agent-0",
                "ok": True,
                "provider_diagnostics": ["PROVIDER_DIAGNOSTIC_SENTINEL"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class _Request:
        query = {"session_id": session_id}

    routes.register_agent_edit_routes(types.SimpleNamespace(routes=_Routes()))
    bundle_route = registered[("GET", "/vibecomfy/agent-edit/session-bundle")]
    response = asyncio.run(bundle_route(_Request()))

    assert response["status"] == 200
    body = response["body"]
    assert body["ok"] is True
    by_name = {f["name"]: f for f in body["files"]}
    assert "turns/0000/request.json" in by_name
    assert "turns/0000/response.json" in by_name
    request_file = by_name["turns/0000/request.json"]
    response_file = by_name["turns/0000/response.json"]
    assert "text" in request_file
    assert "text" in response_file
    assert "INTERNAL_RAW_PROMPT_SENTINEL" in request_file["text"]
    assert "PROVIDER_DIAGNOSTIC_SENTINEL" in response_file["text"]


# ── batch lint wiring tests ───────────────────────────────────────────────────


def test_field_change_is_noop_with_lint_dropped_ids() -> None:
    """_field_change_is_noop returns True when (uid, field_path) is in
    lint_dropped_op_ids even if old != new."""
    from vibecomfy.comfy_nodes.agent.edit import (
        _field_change_is_noop,
        _ABSENT_FIELD_OLD,
    )

    # A change that would normally NOT be a no-op (old != new).
    change = FieldChange(
        uid="node-1", field_path="filename_prefix", old="before", new="after"
    )
    assert not _field_change_is_noop(change)
    assert not _field_change_is_noop(change, lint_dropped_op_ids=frozenset())

    # Lint drops this identity → classified as no-op.
    dropped = frozenset({("node-1", "filename_prefix")})
    assert _field_change_is_noop(change, lint_dropped_op_ids=dropped)

    # Different (uid, field_path) is NOT dropped.
    other_dropped = frozenset({("node-2", "other_field")})
    assert not _field_change_is_noop(change, lint_dropped_op_ids=other_dropped)

    # ABSENT_FIELD_OLD still works correctly: absent old → not a no-op unless lint says so.
    absent_change = FieldChange(
        uid="node-3", field_path="new_field", old=None, new="hello"
    )
    # old=None is the serialized form; ABSENT_FIELD_OLD is internal.
    # The function checks `change.old is not _ABSENT_FIELD_OLD`.
    # We need to set old to _ABSENT_FIELD_OLD explicitly.
    absent_change_internal = FieldChange(
        uid="node-3", field_path="new_field", old=_ABSENT_FIELD_OLD, new="hello"
    )
    assert not _field_change_is_noop(absent_change_internal)
    # But lint can still drop it.
    dropped_absent = frozenset({("node-3", "new_field")})
    assert _field_change_is_noop(
        absent_change_internal, lint_dropped_op_ids=dropped_absent
    )


def test_real_field_changes_respects_lint_dropped_op_ids() -> None:
    """_real_field_changes excludes changes whose (uid, field_path) is in
    lint_dropped_op_ids, even when the old/new values differ."""
    from vibecomfy.comfy_nodes.agent.edit import _real_field_changes

    changes = (
        FieldChange(uid="a", field_path="f1", old="old", new="new"),
        FieldChange(uid="b", field_path="f2", old="same", new="same"),  # value no-op
        FieldChange(uid="c", field_path="f3", old="old", new="changed"),
    )

    # Without lint: only the value no-op is excluded.
    real = _real_field_changes(changes)
    assert len(real) == 2
    assert {c.uid for c in real} == {"a", "c"}

    # With lint: the lint-dropped identity wins, so (c, f3) is excluded even
    # though old != new.
    dropped = frozenset({("c", "f3")})
    real_lint = _real_field_changes(changes, lint_dropped_op_ids=dropped)
    assert len(real_lint) == 1
    assert real_lint[0].uid == "a"


def test_noop_field_changes_respects_lint_dropped_op_ids() -> None:
    """_noop_field_changes includes changes whose (uid, field_path) is in
    lint_dropped_op_ids PLUS the usual value no-ops."""
    from vibecomfy.comfy_nodes.agent.edit import _noop_field_changes

    changes = (
        FieldChange(uid="a", field_path="f1", old="old", new="new"),
        FieldChange(uid="b", field_path="f2", old="same", new="same"),  # value no-op
        FieldChange(uid="c", field_path="f3", old="old", new="changed"),
    )

    # Without lint: only the value no-op.
    noop = _noop_field_changes(changes)
    assert len(noop) == 1
    assert noop[0].uid == "b"

    # With lint: the lint-dropped identity ALSO counts as no-op.
    dropped = frozenset({("c", "f3")})
    noop_lint = _noop_field_changes(changes, lint_dropped_op_ids=dropped)
    assert len(noop_lint) == 2
    assert {c.uid for c in noop_lint} == {"b", "c"}


def test_format_batch_report_includes_lint_diagnostics() -> None:
    """_format_batch_report appends lint diagnostics and mentions
    lint_dropped_count in the summary line."""
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
    from vibecomfy.porting.edit.session import BatchResult, StatementResult

    br = BatchResult(
        ok=True,
        statements=(
            StatementResult(
                statement_index=0,
                source="set_node_field(n1, 'f', 'v')",
                ok=True,
                landed=True,
                op_kind="set_node_field",
                diagnostics=(),
            ),
        ),
        diagnostics=(),
    )
    lint_diags: tuple[dict[str, Any], ...] = (
        {"code": "noop_field", "message": "field 'f' already has value 'v'", "severity": "info"},
    )

    report = _format_batch_report(
        br,
        consecutive_errors=0,
        budget_remaining=3,
        lint_dropped_count=1,
        lint_diagnostics=lint_diags,
    )
    assert "1 lint-dropped no-op(s)" in report
    assert "[lint] noop_field: field 'f' already has value 'v'" in report

    # Without lint args: no lint-dropped mention, no lint diagnostics.
    report_no_lint = _format_batch_report(
        br, consecutive_errors=0, budget_remaining=3
    )
    assert "lint-dropped" not in report_no_lint
    assert "[lint]" not in report_no_lint


def test_format_batch_report_json_includes_lint_fields() -> None:
    """_format_batch_report_json includes lint_dropped in summary and
    lint_diagnostics top-level key when provided."""
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report_json
    from vibecomfy.porting.edit.session import BatchResult, StatementResult

    br = BatchResult(
        ok=True,
        statements=(
            StatementResult(
                statement_index=0,
                source="set_node_field(n1, 'f', 'v')",
                ok=True,
                landed=True,
                op_kind="set_node_field",
                diagnostics=(),
            ),
        ),
        diagnostics=(),
    )
    lint_diags: tuple[dict[str, Any], ...] = (
        {"code": "noop_field", "message": "already set", "severity": "info"},
    )

    json_report = _format_batch_report_json(
        br,
        consecutive_errors=0,
        budget_remaining=3,
        lint_dropped_count=1,
        lint_diagnostics=lint_diags,
    )
    assert json_report["summary"]["lint_dropped"] == 1
    assert json_report["lint_diagnostics"] == [{"code": "noop_field", "message": "already set", "severity": "info"}]

    # Without lint args: no lint keys.
    json_no_lint = _format_batch_report_json(
        br, consecutive_errors=0, budget_remaining=3
    )
    assert "lint_dropped" not in json_no_lint["summary"]
    assert "lint_diagnostics" not in json_no_lint


def test_field_change_is_noop_without_lint_dropped_ids_flag_off() -> None:
    """When lint_dropped_op_ids is None (flag-off), behavior matches the
    original: only old==new changes are no-ops."""
    from vibecomfy.comfy_nodes.agent.edit import (
        _field_change_is_noop,
        _real_field_changes,
        _noop_field_changes,
    )

    changes = (
        FieldChange(uid="a", field_path="f1", old="old", new="new"),
        FieldChange(uid="b", field_path="f2", old="same", new="same"),
        FieldChange(uid="c", field_path="f3", old="x", new="y"),
    )

    # Flag-off (lint_dropped_op_ids=None, the default)
    assert not _field_change_is_noop(changes[0])
    assert _field_change_is_noop(changes[1])
    assert not _field_change_is_noop(changes[2])

    real = _real_field_changes(changes)
    assert len(real) == 2
    assert {c.uid for c in real} == {"a", "c"}

    noop = _noop_field_changes(changes)
    assert len(noop) == 1
    assert noop[0].uid == "b"


# ── flag-off parity tests (T7) ──────────────────────────────────────────


def test_flag_off_lint_noop_field_set_follows_pre_lint_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When VIBECOMFY_AGENT_EDIT_LINT=0, a no-op set_mode (same mode value)
    passes through to apply_delta() unchanged rather than being dropped by the
    lint gate.  The pre-lint path never classifies it as a no-op."""
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_LINT", "0")

    from vibecomfy.comfy_nodes.agent.edit import (
        _edit_lint_enabled,
        _stage_apply_delta,
        AgentEditState,
    )
    from vibecomfy.porting.edit.ops import NodeTarget, SetModeOp
    from pathlib import Path as _Path

    # Verify the flag is genuinely off
    assert not _edit_lint_enabled()

    # Build a minimal state with a no-op set_mode on the flat.json fixture
    import json as _json
    fixture = _json.loads(
        (_Path("tests/fixtures/agent_edit/flat.json")).read_text(encoding="utf-8")
    )

    state = AgentEditState(
        task="flag-off noop mode",
        graph=fixture,
        guard_original_ui=fixture,
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
        session_dir=_Path("/tmp/test_flag_off"),
        turn_dir=_Path("/tmp/test_flag_off/turn_001"),
        request_path=_Path("/tmp/test_flag_off/request.json"),
        original_ui_path=_Path("/tmp/test_flag_off/original.json"),
        before_py_path=_Path("/tmp/test_flag_off/before.py"),
        after_py_path=_Path("/tmp/test_flag_off/after.py"),
        projection_path=_Path("/tmp/test_flag_off/projection.json"),
        model_request_path=_Path("/tmp/test_flag_off/model_request.json"),
        model_response_path=_Path("/tmp/test_flag_off/model_response.json"),
        candidate_ui_path=_Path("/tmp/test_flag_off/candidate.json"),
        messages_path=_Path("/tmp/test_flag_off/messages.json"),
    )

    # Node 2 (CLIPTextEncode) has mode=0 in flat.json.  Setting mode=0 again
    # is a no-op that lint would drop, but the pre-lint path applies it through.
    state.delta_ops = (
        SetModeOp(
            op="set_mode",
            target=NodeTarget(scope_path="", uid="2"),
            mode=0,
        ),
    )

    from vibecomfy.comfy_nodes.agent.contracts import TurnContext
    result = _stage_apply_delta(
        state, TurnContext(session_id="flag-off-noop", turn_id="0001")
    )

    # Pre-lint behaviour: the op is not rejected and not silently dropped.
    # apply_delta() resolves and applies it (even though the value is unchanged).
    # The StageResult is ok=True because apply_delta succeeds.
    assert result.ok is True, f"Expected ok=True, got {result.value}"

    # The no-op is NOT lint-dropped; it flows through to apply_delta → guard.
    # The resulting report/candidate reflect normal application.
    assert state.report is not None
    # lint_noop must NOT appear (that key is set only by the lint gate)
    assert state.report.get("change", {}).get("lint_noop") is not True


def test_flag_off_lint_malformed_unknown_node_follows_pre_lint_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When VIBECOMFY_AGENT_EDIT_LINT=0, a malformed set_node_field targeting a
    non-existent uid follows the pre-lint apply_delta() path: it fails in
    resolve_delta() with an "unknown_node_target" diagnostic rather than
    producing a lint-specific "unknown_node" rejection."""
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_LINT", "0")

    from vibecomfy.comfy_nodes.agent.edit import (
        _edit_lint_enabled,
        _stage_apply_delta,
        AgentEditState,
    )
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
    from pathlib import Path as _Path

    assert not _edit_lint_enabled()

    import json as _json
    fixture = _json.loads(
        (_Path("tests/fixtures/agent_edit/flat.json")).read_text(encoding="utf-8")
    )

    state = AgentEditState(
        task="flag-off unknown node",
        graph=fixture,
        guard_original_ui=fixture,
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
        session_dir=_Path("/tmp/test_flag_off_unk"),
        turn_dir=_Path("/tmp/test_flag_off_unk/turn_001"),
        request_path=_Path("/tmp/test_flag_off_unk/request.json"),
        original_ui_path=_Path("/tmp/test_flag_off_unk/original.json"),
        before_py_path=_Path("/tmp/test_flag_off_unk/before.py"),
        after_py_path=_Path("/tmp/test_flag_off_unk/after.py"),
        projection_path=_Path("/tmp/test_flag_off_unk/projection.json"),
        model_request_path=_Path("/tmp/test_flag_off_unk/model_request.json"),
        model_response_path=_Path("/tmp/test_flag_off_unk/model_response.json"),
        candidate_ui_path=_Path("/tmp/test_flag_off_unk/candidate.json"),
        messages_path=_Path("/tmp/test_flag_off_unk/messages.json"),
    )

    # uid "999" does not exist in flat.json
    state.delta_ops = (
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(
                scope_path="", uid="999", field_path="widgets_values"
            ),
            value="any",
        ),
    )

    from vibecomfy.comfy_nodes.agent.contracts import TurnContext
    result = _stage_apply_delta(
        state, TurnContext(session_id="flag-off-unk", turn_id="0001")
    )

    # Pre-lint behaviour: resolve_delta fails because the node doesn't exist.
    # The StageResult is ok=False with a blocking validation error.
    assert result.ok is False
    assert result.blocking is True

    # The failure kind comes from apply_delta's path, not lint.
    assert result.value.get("failure_kind") == "ValidationError"

    # The diagnostics should contain the pre-lint "unknown_node_target" message,
    # NOT lint-specific issue codes like "unknown_node".
    issue_codes = {i.get("code") for i in (result.issues or ())}
    assert "unknown_node_target" in issue_codes, (
        f"Expected pre-lint 'unknown_node_target' in codes, got {issue_codes}"
    )
    assert "unknown_node" not in issue_codes, (
        f"Lint 'unknown_node' code leaked into flag-off path: {issue_codes}"
    )
    # The message should mention the uid
    issue_messages = " ".join(
        str(i.get("message", "")) for i in (result.issues or ())
    )
    assert "999" in issue_messages


# ---------------------------------------------------------------------------
# Agent-runtime-unavailable classification
#
# Regression: a failure to load the agent runtime (e.g. ``import megaplan``
# fails because a shadowing stub or broken editable install hides the package)
# used to be flattened into a retryable ``ProviderError`` reported to the user
# as "The model provider is temporarily unavailable. ... try again". That is a
# setup fault, not a transient outage, and retrying never helps. It must be
# classified as a non-retryable AGENT_RUNTIME_UNAVAILABLE failure whose
# user-facing message names the real cause.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stage, exc",
    [
        ("agent_batch", ModuleNotFoundError("No module named 'megaplan'")),
        ("agent_response", ImportError("cannot import name 'AIAgent' from 'megaplan.agent'")),
        ("agent_delta", ModuleNotFoundError("No module named 'arnold'")),
    ],
)
def test_classify_import_failure_is_runtime_unavailable_not_retryable(stage, exc):
    env = classify_failure(stage, exc)
    assert env.kind is FailureKind.AGENT_RUNTIME_UNAVAILABLE
    assert env.retryable is False
    # The original cause must reach both the structured context and the message.
    assert str(exc) in env.agent_failure_context.get("explanation", "")
    assert str(exc) in env.message


def test_classify_provider_error_wrapping_import_message_is_runtime_unavailable():
    # Even when the worker error is flattened into ProviderError before it
    # reaches classification, the "no module named" message routes it to the
    # non-retryable runtime-unavailable kind via the message fallback.
    env = classify_failure("agent_response", ProviderError("No module named 'megaplan'"))
    assert env.kind is FailureKind.AGENT_RUNTIME_UNAVAILABLE
    assert env.retryable is False


def test_classify_genuine_provider_outage_stays_retryable_provider_error():
    # A real transient provider failure must NOT be reclassified.
    env = classify_failure("agent_response", ProviderError("502 upstream gateway timeout"))
    assert env.kind is FailureKind.PROVIDER_ERROR
    assert env.retryable is True


# ── Precedent adaptation prompt assembly tests (T14) ────────────────────────
# Verify that prompt assembly injects precedent context only for
# precedent_research route and keeps direct-edit prompts clean.


def test_build_precedent_adaptation_prompt_returns_empty_for_none_plan() -> None:
    """_build_precedent_adaptation_prompt returns '' when adaptation_plan is None."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    result = _build_precedent_adaptation_prompt(None)
    assert result == ""

    result = _build_precedent_adaptation_prompt(None, precedent_slices=())
    assert result == ""


def test_build_precedent_adaptation_prompt_returns_empty_for_empty_dict() -> None:
    """_build_precedent_adaptation_prompt returns '' when adaptation_plan is empty dict."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    result = _build_precedent_adaptation_prompt({})
    assert result == ""


def test_build_precedent_adaptation_prompt_returns_empty_for_failed_empty_plan() -> None:
    """Failed plans with no concrete edits must not enter implementation prompts."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    plan = {
        "selected_slice": {"source_class_type": "HotShotWorkflow", "node_ids": []},
        "anchor_bindings": [],
        "required_new_nodes": [],
        "required_rewires": [],
        "edit_ops": [],
        "structural_validation": "fail",
        "semantic_validation": "not_evaluated",
    }

    assert _build_precedent_adaptation_prompt(plan) == ""


def test_build_precedent_adaptation_prompt_includes_selected_slice_info() -> None:
    """_build_precedent_adaptation_prompt includes selected_slice details."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    plan = {
        "selected_slice": {
            "source_class_type": "AudioLipsyncWorkflow",
            "node_ids": [1, 2, 3],
            "entry_anchor": "input_audio",
            "exit_anchor": "output_video",
            "python_path": "/templates/audio_lipsync.py",
        },
        "edit_ops": [
            {"kind": "add_node", "target": "audio_loader"},
        ],
    }
    result = _build_precedent_adaptation_prompt(plan)
    assert "AudioLipsyncWorkflow" in result
    assert "3 node(s)" in result
    assert "entry_anchor=input_audio" in result
    assert "exit_anchor=output_video" in result
    assert "path=/templates/audio_lipsync.py" in result


def test_build_precedent_adaptation_prompt_includes_anchor_bindings() -> None:
    """_build_precedent_adaptation_prompt includes anchor bindings section."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    plan = {
        "selected_slice": {"source_class_type": "TestWorkflow"},
        "anchor_bindings": [
            {"input_audio": "node_5"},
            {"output_video": "node_10"},
        ],
        "required_rewires": [
            {"from": "node_5", "to": "node_10", "slot": "audio"},
        ],
    }
    result = _build_precedent_adaptation_prompt(plan)
    assert "Anchor bindings:" in result
    assert "input_audio → node_5" in result
    assert "output_video → node_10" in result


def test_build_precedent_adaptation_prompt_includes_required_new_nodes() -> None:
    """_build_precedent_adaptation_prompt includes required new nodes."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    plan = {
        "selected_slice": {"source_class_type": "TestWorkflow"},
        "required_new_nodes": [
            {"class_type": "VAEDecode", "id": "node_new_1"},
            {"class_type": "SaveImage", "id": "node_new_2"},
        ],
    }
    result = _build_precedent_adaptation_prompt(plan)
    assert "Required new nodes:" in result
    assert "VAEDecode" in result
    assert "SaveImage" in result


def test_build_precedent_adaptation_prompt_includes_required_rewires() -> None:
    """_build_precedent_adaptation_prompt includes required rewires."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    plan = {
        "selected_slice": {"source_class_type": "TestWorkflow"},
        "required_rewires": [
            {"from": "node_1", "to": "node_new_1", "slot": "LATENT"},
        ],
    }
    result = _build_precedent_adaptation_prompt(plan)
    assert "Required rewires:" in result
    assert "node_1 → node_new_1.LATENT" in result


def test_build_precedent_adaptation_prompt_includes_edit_ops() -> None:
    """_build_precedent_adaptation_prompt includes edit ops."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    plan = {
        "selected_slice": {"source_class_type": "TestWorkflow"},
        "edit_ops": [
            {"kind": "set_field", "target": "node_1.seed", "value": 42},
        ],
    }
    result = _build_precedent_adaptation_prompt(plan)
    assert "Edit ops:" in result
    assert "set_field" in result
    assert "42" in result


def test_build_precedent_adaptation_prompt_includes_socket_evidence_from_slices() -> None:
    """_build_precedent_adaptation_prompt includes socket evidence from precedent_slices."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    plan = {"selected_slice": {"source_class_type": "MainWorkflow"}}
    plan["required_new_nodes"] = [{"class_type": "HelperNode", "id": "new_1"}]
    slices = (
        {"source_class_type": "HelperA", "entry_anchor": "in1", "exit_anchor": "out1"},
        {"source_class_type": "HelperB"},
    )
    result = _build_precedent_adaptation_prompt(plan, precedent_slices=slices)
    assert "Socket evidence" in result
    assert "HelperA (in=in1, out=out1)" in result
    assert "HelperB" in result


def test_build_precedent_adaptation_prompt_includes_structural_validation() -> None:
    """Actionable failed plans keep validation warnings; empty failed plans do not render."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    plan_fail = {"selected_slice": {"source_class_type": "BadWF"}, "structural_validation": "fail"}
    result = _build_precedent_adaptation_prompt(plan_fail)
    assert result == ""

    plan_fail_with_ops = {
        "selected_slice": {"source_class_type": "BadWF"},
        "structural_validation": "fail",
        "edit_ops": [{"kind": "set_field", "target": "node_1.seed", "value": 42}],
    }
    result = _build_precedent_adaptation_prompt(plan_fail_with_ops)
    assert "AVOID" in result
    assert "structural validation FAILED" in result

    plan_advisory = {
        "selected_slice": {"source_class_type": "WarnWF"},
        "structural_validation": "advisory",
        "required_new_nodes": [{"class_type": "WarnNode", "id": "new_1"}],
    }
    result = _build_precedent_adaptation_prompt(plan_advisory)
    assert "NOTE:" in result
    assert "structural validation has advisories" in result


def test_build_precedent_adaptation_prompt_includes_semantic_validation() -> None:
    """_build_precedent_adaptation_prompt includes semantic validation status."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    plan_pass = {
        "selected_slice": {"source_class_type": "GoodWF"},
        "semantic_validation": "pass",
        "edit_ops": [{"kind": "set_field", "target": "node_1.seed", "value": 42}],
    }
    result = _build_precedent_adaptation_prompt(plan_pass)
    assert "Semantic validation: PASS" in result

    plan_fail = {"selected_slice": {"source_class_type": "BadWF"}, "semantic_validation": "fail"}
    result = _build_precedent_adaptation_prompt(plan_fail)
    assert result == ""

    plan_fail_with_ops = {
        "selected_slice": {"source_class_type": "BadWF"},
        "semantic_validation": "fail",
        "edit_ops": [{"kind": "set_field", "target": "node_1.seed", "value": 42}],
    }
    result = _build_precedent_adaptation_prompt(plan_fail_with_ops)
    assert "AVOID" in result
    assert "semantic validation FAILED" in result


def test_build_batch_messages_no_precedent_text_when_empty() -> None:
    """build_batch_messages does not include 'Precedent adaptation plan' when
    precedent_adaptation_plan is empty string."""
    from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

    messages = build_batch_messages(
        task="change seed to 42",
        turn_number=0,
        python_source="x = LoadImage()",
        signature_catalog="LoadImage(image)",
        available_node_names="LoadImage, SaveImage",
        precedent_adaptation_plan="",  # Empty — should NOT appear
    )
    user_content = messages[1]["content"]
    assert "Precedent adaptation plan" not in user_content
    assert "precedent" not in user_content.lower()


def test_build_batch_messages_includes_precedent_text_when_provided() -> None:
    """build_batch_messages includes 'Precedent adaptation plan' block when
    precedent_adaptation_plan is non-empty."""
    from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

    plan_text = "Selected slice: AudioWorkflow\nRequired new nodes: VAEDecode, SaveImage"
    messages = build_batch_messages(
        task="adapt audio workflow",
        turn_number=0,
        python_source="x = LoadAudio()",
        signature_catalog="LoadAudio(audio)",
        available_node_names="LoadAudio, VAEDecode, SaveImage",
        precedent_adaptation_plan=plan_text,
    )
    user_content = messages[1]["content"]
    assert "Precedent adaptation plan (structured):" in user_content
    assert "AudioWorkflow" in user_content
    assert "VAEDecode" in user_content


def test_build_batch_messages_no_precedent_text_in_later_turn_when_empty() -> None:
    """build_batch_messages does not include precedent text in later turns
    when precedent_adaptation_plan is empty."""
    from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

    messages = build_batch_messages(
        task="continue editing",
        turn_number=1,
        python_source="",
        diff="+x.seed = 42",
        report="Previous turn applied seed change.",
        precedent_adaptation_plan="",  # Empty
    )
    user_content = messages[1]["content"]
    assert "Precedent adaptation plan" not in user_content


def test_build_batch_messages_direct_edit_scenario_no_precedent_leak() -> None:
    """build_batch_messages with typical direct-edit parameters does not
    inject the structured precedent adaptation plan block into the prompt."""
    from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

    messages = build_batch_messages(
        task="change the sampler seed to 42",
        turn_number=0,
        python_source="sampler = KSampler(seed=0)",
        signature_catalog="KSampler(seed, steps, cfg, sampler_name, scheduler, denoise)",
        available_node_names="LoadImage, KSampler, VAEDecode, SaveImage",
        research_summary="",  # No research context
        graph_report="",
        precedent_adaptation_plan="",  # No precedent context
    )
    # The system prompt may contain general guidance about precedents,
    # but the structured precedent adaptation plan block must NOT be injected.
    user_content = messages[1]["content"]
    assert "Precedent adaptation plan (structured):" not in user_content
    # Research context should also be absent when empty
    assert "Research findings (external + local corpus):" not in user_content


def test_compact_execution_protocol_notes_preserves_adaptation_actionability() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _compact_execution_protocol_notes_for_prompt

    compact = _compact_execution_protocol_notes_for_prompt(
        {
            "_discardability": "context only",
            "adaptation_plan_actionability": {
                "actionability": "non_actionable",
                "non_actionable_reason": "structural_validation_failed_without_concrete_edits",
                "allowed_followups": [
                    "apply_bound_current_graph_edit_if_schema_sufficient",
                    "build_execution_plan_with_required_nodes_and_rewires",
                    "typed_refusal_or_clarification_if_authoring_surface_missing",
                ],
                "full_plan": {"selected_slice": {"source_class_type": "BadWF"}},
            },
        }
    )

    actionability = compact["adaptation_plan_actionability"]
    assert actionability["actionability"] == "non_actionable"
    assert actionability["non_actionable_reason"] == (
        "structural_validation_failed_without_concrete_edits"
    )
    assert "apply_bound_current_graph_edit_if_schema_sufficient" in actionability["allowed_followups"]
    assert not any(
        "search" in item or "retry" in item
        for item in actionability["allowed_followups"]
    )
    assert "full_plan" not in actionability


# ── T14: provider research tool exposure and neutral formatting tests ──────


class TestBuildBatchMessagesResearchToolExposure:
    """build_batch_messages research tool parameter schema, bounded guidance,
    evidence/context labeling, and neutral formatting."""

    def test_research_tool_parameter_schema_is_clear(self) -> None:
        """System prompt includes research() with explicit parameter schema:
        query string + sources list with allowed values."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(
            task="add upscale",
            python_source="x = LoadImage()",
            signature_catalog="LoadImage(image)",
            available_node_names="LoadImage, ImageScaleBy",
        )
        system = messages[0]["content"]

        # Parameter schema: contains research() invocation pattern in system prompt
        rq = 'research("query words", sources='
        rq_alt = "research(\"query words\", sources="
        assert rq in system or rq_alt in system, (
            "System prompt must contain research() tool signature with query + sources"
        )

        # All four allowed source tiers are in the schema example
        assert "workflows" in system
        assert "registry" in system
        assert "messages" in system
        assert "web" in system

        # Sources list shows the explicit parameter
        assert "sources=[" in system

        # Default behavior described
        assert "if sources are omitted" in system
        assert "internal workflows/templates only" in system

    def test_bounded_guidance_label_present(self) -> None:
        """The research strategy section is labeled as bounded guidance."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(
            task="inspect",
            python_source="x = LoadImage()",
        )
        system = messages[0]["content"]
        assert "Research strategy (bounded guidance):" in system

    def test_bounded_guidance_contains_evidence_tier_strategy(self) -> None:
        """Bounded guidance describes evidence-tier call strategy."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(
            task="inspect",
            python_source="x = LoadImage()",
        )
        system = messages[0]["content"]
        # Key bounded guidance phrases
        assert "tentative retrieval hints" in system
        assert "research workflow precedents and community knowledge" in system
        assert "use `workflows` first" in system
        assert "then `messages` or `web`" in system
        assert "Use `registry` only when the user explicitly asks" in system
        assert "Do not research installation, provider packs, registry, or local addability" in system

    def test_effective_surface_guidance_is_execute_only(self) -> None:
        """Effective-surface guidance belongs to edit execution, not research."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        execute_messages = build_batch_messages(
            task="change the linked frame rate",
            python_source="video = VHS_VideoCombine(frame_rate=24)",
        )
        research_messages = build_batch_messages(
            task="which node controls frame rate?",
            python_source="video = VHS_VideoCombine(frame_rate=24)",
            research_only=True,
        )

        execute_system = execute_messages[0]["content"]
        research_combined = "\n".join(message["content"] for message in research_messages)

        assert "Effective surface rule:" in execute_system
        assert "linked/overridden" in execute_system
        assert "effective source" in execute_system
        assert "typed refusal" in execute_system
        assert "Effective surface rule:" not in research_combined
        assert "linked override" not in research_combined
        assert "effective source" not in research_combined

    def test_research_block_uses_evidence_context_label_turn0(self) -> None:
        """Research block on turn 0 uses 'Research evidence/context' as the section
        label rather than 'Research findings'."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(
            task="add upscale",
            turn_number=0,
            python_source="x = LoadImage()",
            research_summary="Found workflow precedent.",
        )
        user = messages[1]["content"]
        assert "Research evidence/context (external + local corpus):" in user
        # The section label must be evidence/context, not findings
        assert "Research findings (external + local corpus):" not in user

    def test_research_block_uses_evidence_context_label_later_turn(self) -> None:
        """Research block on later turns uses 'Research evidence/context' as
        the section label rather than 'Research findings'."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(
            task="continue",
            turn_number=1,
            python_source="",
            research_summary="Followup evidence.",
            diff="+x.seed = 42",
            report="Applied change.",
        )
        user = messages[1]["content"]
        assert "Research evidence/context (external + local corpus):" in user
        assert "Research findings (external + local corpus):" not in user

    def test_research_block_absent_when_empty(self) -> None:
        """No research block is injected when research_summary is empty."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(
            task="edit seed",
            python_source="x = KSampler(seed=0)",
            research_summary="",
        )
        user = messages[1]["content"]
        assert "Research evidence/context" not in user
        assert "Research findings" not in user

    def test_no_option_menu_language_in_system_prompt(self) -> None:
        """System prompt must not contain option-menu or recommendation language."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(
            task="inspect the graph",
            python_source="x = LoadImage()",
            signature_catalog="LoadImage(image)",
            available_node_names="LoadImage",
        )
        system = messages[0]["content"]
        lower = system.lower()
        forbidden = (
            "option menu", "choose from these", "pick one of", "we recommend",
            "our recommendation", "select the best", "best option",
            "menu of sources", "pick a source",
        )
        for term in forbidden:
            assert term not in lower, (
                f"Forbidden option-menu term '{term}' found in system prompt"
            )

    def test_no_winner_ranking_language_in_system_prompt(self) -> None:
        """System prompt must not contain winner/ranking language for sources."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(
            task="inspect the graph",
            python_source="x = LoadImage()",
        )
        system = messages[0]["content"]
        lower = system.lower()
        for term in ("winner", "best source", "top source", "preferred source",
                      "primary source", "chosen source"):
            assert term not in lower, (
                f"Forbidden ranking term '{term}' found in system prompt"
            )

    def test_system_prompt_frames_research_as_evidence_not_recommendation(self) -> None:
        """The research tool description frames output as evidence/context."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(
            task="inspect",
            python_source="x = LoadImage()",
        )
        system = messages[0]["content"]
        # The research() call description should be neutral
        assert "research(" in system
        # Should frame as evidence-gathering, not as picking recommendations
        lower = system.lower()
        assert "no edit lands" in lower

    def test_precedent_adaptation_block_framed_as_structured_not_recommendation(self) -> None:
        """Precedent adaptation plan block is labeled as 'structured', not 'recommendation'."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        plan_text = "Selected slice: AudioWorkflow\nRequired new nodes: VAEDecode, SaveImage"
        messages = build_batch_messages(
            task="adapt audio workflow",
            turn_number=0,
            python_source="x = LoadAudio()",
            signature_catalog="LoadAudio(audio)",
            available_node_names="LoadAudio, VAEDecode, SaveImage",
            precedent_adaptation_plan=plan_text,
        )
        user = messages[1]["content"]
        assert "Precedent adaptation plan (structured):" in user
        # Should NOT be labeled as recommendation
        assert "recommendation" not in user.lower()
        assert "recommended" not in user.lower()

    def test_no_forbidden_keys_in_precedent_adaptation_block(self) -> None:
        """The precedent adaptation block content must not contain forbidden keys."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        # Construct a plan text with neutral language (no forbidden keys)
        plan_text = (
            "all_slices:\n"
            "- source_class_type: HotshotXLLoader\n"
            "- source_class_type: AnimateDiffLoader\n"
            "context_note: This material is provided as presentation context only; "
            "it is not an authoritative directive or required implementation.\n"
        )
        messages = build_batch_messages(
            task="adapt workflow",
            python_source="x = LoadImage()",
            precedent_adaptation_plan=plan_text,
        )
        user = messages[1]["content"]
        lower = user.lower()
        # Only check for forbidden ranking/evaluation keys (not words that may
        # appear negated in context_note like 'winner' or 'recommendation')
        for key in ("best", "selected", "score", "rank",
                     "primary", "preferred", "top pick"):
            assert key not in lower, (
                f"Forbidden key '{key}' found in precedent adaptation block"
            )


# ── T16: route-specific validation/reporting tests ─────────────────────────

# ── _route_blocks_apply unit tests ─────────────────────────────────────────


def test_route_blocks_apply_inspect_only() -> None:
    """_route_blocks_apply returns True for inspect_only route (legacy alias)."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("inspect_only") is True


def test_route_blocks_apply_inspect_canonical() -> None:
    """_route_blocks_apply returns True for canonical inspect route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("inspect") is True


def test_route_blocks_apply_clarify() -> None:
    """_route_blocks_apply returns True for clarify route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("clarify") is True


def test_route_blocks_apply_direct_edit() -> None:
    """_route_blocks_apply returns False for direct_edit route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("direct_edit") is False


def test_route_blocks_apply_precedent_research() -> None:
    """_route_blocks_apply returns False for precedent_research route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("precedent_research") is False


def test_route_blocks_apply_asset_lookup() -> None:
    """_route_blocks_apply returns False for asset_lookup route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("asset_lookup") is False


def test_route_blocks_apply_diagnose_repair() -> None:
    """_route_blocks_apply returns False for diagnose_repair route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("diagnose_repair") is False


def test_route_blocks_apply_subgraph_preview() -> None:
    """_route_blocks_apply returns False for subgraph_preview route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("subgraph_preview") is False


def test_route_blocks_apply_none_route() -> None:
    """_route_blocks_apply returns False for None route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply(None) is False


def test_route_blocks_apply_empty_string_route() -> None:
    """_route_blocks_apply returns False for empty string route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("") is False


def test_route_blocks_apply_unknown_route() -> None:
    """_route_blocks_apply returns False for an unrecognized route string."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("some_future_route") is False


def test_route_blocks_apply_respond() -> None:
    """_route_blocks_apply returns True for respond route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("respond") is True


def test_route_blocks_apply_research() -> None:
    """_route_blocks_apply returns True for research route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("research") is True


def test_route_blocks_apply_revise_passes() -> None:
    """_route_blocks_apply returns False for canonical revise route (applyable)."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("revise") is False


def test_route_blocks_apply_adapt_passes() -> None:
    """_route_blocks_apply returns False for canonical adapt route (applyable)."""
    from vibecomfy.comfy_nodes.agent.edit import _route_blocks_apply
    assert _route_blocks_apply("adapt") is False


# ── _route_change_focus_label unit tests ────────────────────────────────────


def test_route_change_focus_label_direct_edit() -> None:
    """_route_change_focus_label returns 'Focused change' for direct_edit."""
    from vibecomfy.comfy_nodes.agent.edit import _route_change_focus_label
    assert _route_change_focus_label("direct_edit") == "Focused change"


def test_route_change_focus_label_inspect_only() -> None:
    """_route_change_focus_label returns '' for inspect_only (legacy alias)."""
    from vibecomfy.comfy_nodes.agent.edit import _route_change_focus_label
    assert _route_change_focus_label("inspect_only") == ""


def test_route_change_focus_label_inspect_canonical() -> None:
    """_route_change_focus_label returns '' for canonical inspect."""
    from vibecomfy.comfy_nodes.agent.edit import _route_change_focus_label
    assert _route_change_focus_label("inspect") == ""


def test_route_change_focus_label_clarify() -> None:
    """_route_change_focus_label returns '' for clarify."""
    from vibecomfy.comfy_nodes.agent.edit import _route_change_focus_label
    assert _route_change_focus_label("clarify") == ""


def test_route_change_focus_label_precedent_research() -> None:
    """_route_change_focus_label returns '' for precedent_research."""
    from vibecomfy.comfy_nodes.agent.edit import _route_change_focus_label
    assert _route_change_focus_label("precedent_research") == ""


def test_route_change_focus_label_none() -> None:
    """_route_change_focus_label returns '' for None route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_change_focus_label
    assert _route_change_focus_label(None) == ""


def test_route_change_focus_label_empty_string() -> None:
    """_route_change_focus_label returns '' for empty string."""
    from vibecomfy.comfy_nodes.agent.edit import _route_change_focus_label
    assert _route_change_focus_label("") == ""


def test_route_change_focus_label_unknown_route() -> None:
    """_route_change_focus_label returns '' for an unknown route."""
    from vibecomfy.comfy_nodes.agent.edit import _route_change_focus_label
    assert _route_change_focus_label("other_route") == ""


# ── _build_precedent_semantic_check_entries unit tests ──────────────────────


def test_precedent_semantic_entries_empty_for_none_plan() -> None:
    """Returns empty list when executor_adaptation_plan is None."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    state = _make_state(executor_adaptation_plan=None)
    assert _build_precedent_semantic_check_entries(state) == []


def test_precedent_semantic_entries_empty_for_non_dict_plan() -> None:
    """Returns empty list when executor_adaptation_plan is not a dict."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    state = _make_state(executor_adaptation_plan="not_a_dict")
    assert _build_precedent_semantic_check_entries(state) == []


def test_precedent_semantic_entries_empty_for_empty_dict_plan() -> None:
    """Returns empty list when plan is an empty dict."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    state = _make_state(executor_adaptation_plan={})
    assert _build_precedent_semantic_check_entries(state) == []


def test_precedent_semantic_entries_both_validation_pass() -> None:
    """Produces two entries when both structural and semantic validation pass."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    plan = {"structural_validation": "pass", "semantic_validation": "pass"}
    state = _make_state(executor_adaptation_plan=plan)
    entries = _build_precedent_semantic_check_entries(state)
    assert len(entries) == 2
    structural = [e for e in entries if e["check"] == "structural_validation"][0]
    assert structural["status"] == "pass"
    assert structural["satisfaction"] == "pass"
    assert "compatible" in structural["description"]
    semantic = [e for e in entries if e["check"] == "semantic_validation"][0]
    assert semantic["status"] == "pass"
    assert semantic["satisfaction"] == "pass"
    assert "sound" in semantic["description"]


def test_precedent_semantic_entries_both_validation_fail() -> None:
    """Produces entries with fail status for both validations."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    plan = {"structural_validation": "fail", "semantic_validation": "fail"}
    state = _make_state(executor_adaptation_plan=plan)
    entries = _build_precedent_semantic_check_entries(state)
    assert len(entries) == 2
    structural = [e for e in entries if e["check"] == "structural_validation"][0]
    assert structural["status"] == "fail"
    assert structural["satisfaction"] == "fail"
    semantic = [e for e in entries if e["check"] == "semantic_validation"][0]
    assert semantic["status"] == "fail"
    assert semantic["satisfaction"] == "fail"


def test_precedent_semantic_entries_advisory_status() -> None:
    """Advisory status maps to advisory satisfaction."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    plan = {"structural_validation": "advisory", "semantic_validation": "advisory"}
    state = _make_state(executor_adaptation_plan=plan)
    entries = _build_precedent_semantic_check_entries(state)
    assert len(entries) == 2
    for entry in entries:
        assert entry["status"] == "advisory"
        assert entry["satisfaction"] == "advisory"


def test_precedent_semantic_entries_not_evaluated_status() -> None:
    """not_evaluated status maps to not_evaluated satisfaction."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    plan = {"structural_validation": "not_evaluated", "semantic_validation": "not_evaluated"}
    state = _make_state(executor_adaptation_plan=plan)
    entries = _build_precedent_semantic_check_entries(state)
    assert len(entries) == 2
    for entry in entries:
        assert entry["status"] == "not_evaluated"
        assert entry["satisfaction"] == "not_evaluated"


def test_precedent_semantic_entries_only_structural_present() -> None:
    """When only structural_validation is present, produces one entry."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    plan = {"structural_validation": "pass"}
    state = _make_state(executor_adaptation_plan=plan)
    entries = _build_precedent_semantic_check_entries(state)
    assert len(entries) == 1
    assert entries[0]["check"] == "structural_validation"


def test_precedent_semantic_entries_only_semantic_present() -> None:
    """When only semantic_validation is present, produces one entry."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    plan = {"semantic_validation": "advisory"}
    state = _make_state(executor_adaptation_plan=plan)
    entries = _build_precedent_semantic_check_entries(state)
    assert len(entries) == 1
    assert entries[0]["check"] == "semantic_validation"


def test_precedent_semantic_entries_skips_unknown_validation_values() -> None:
    """Validation fields with unknown values are silently skipped."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    plan = {"structural_validation": "unknown_value", "semantic_validation": "other"}
    state = _make_state(executor_adaptation_plan=plan)
    entries = _build_precedent_semantic_check_entries(state)
    assert entries == []


def test_precedent_semantic_entries_mixed_known_unknown() -> None:
    """Known validation values produce entries; unknown values are skipped."""
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_semantic_check_entries
    plan = {"structural_validation": "pass", "semantic_validation": "bogus"}
    state = _make_state(executor_adaptation_plan=plan)
    entries = _build_precedent_semantic_check_entries(state)
    assert len(entries) == 1
    assert entries[0]["check"] == "structural_validation"


# ── Integration: _build_batch_repl_response route-specific behavior ─────────


def test_batch_repl_response_direct_edit_includes_change_focus() -> None:
    """direct_edit route injects change_focus into batch repl response."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="direct_edit",
        ui_payload={"nodes": []},
        batch_exit_mode="done",
        batch_done_summary="applied seed change",
    )
    context = TurnContext(session_id="t16-d1", turn_id="0001")
    response = _build_batch_repl_response(state, context)
    assert response["change_focus"] == "Focused change"
    # No research leak: task_satisfaction should not contain precedent entries
    task_sat = response.get("task_satisfaction", [])
    precedent_entries = [e for e in task_sat if "precedent" in e.get("check", "").lower()
                         or "validation" in e.get("check", "")]
    assert precedent_entries == []


def test_batch_repl_response_direct_edit_apply_not_blocked() -> None:
    """direct_edit route does not block Apply eligibility."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="direct_edit",
        ui_payload={"nodes": [{"id": 1}]},
        graph={"nodes": [{"id": 1, "widgets_values": ["before"]}]},
        batch_exit_mode="done",
        batch_done_summary="applied change",
        revision_evidence=RevisionEvidence(
            scoped_diff=ScopedDiff(
                changed_nodes=("1",),
                diff_paths=("nodes.1.widgets_values.0",),
                candidate_eligible=True,
            ),
            candidate_eligible=True,
        ),
    )
    context = TurnContext(session_id="t16-d2", turn_id="0001")
    response = _build_batch_repl_response(state, context)
    # direct_edit should NOT be blocked - Apply should be derivable
    assert response.get("apply_eligibility", {}).get("reason") != "no_candidate"
    # change_focus is present
    assert response.get("change_focus") == "Focused change"


def test_batch_repl_response_inspect_only_apply_blocked() -> None:
    """inspect_only route (legacy alias) blocks Apply eligibility in batch repl response."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="inspect_only",
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="inspection complete",
    )
    context = TurnContext(session_id="t16-i1", turn_id="0001")
    response = _build_batch_repl_response(state, context)
    eligibility = response.get("apply_eligibility", {})
    assert eligibility.get("applyable") is False
    assert eligibility.get("reason") == "no_candidate"
    assert "inspect_only" in eligibility.get("message", "")
    # No change_focus for inspect_only
    assert "change_focus" not in response


def test_batch_repl_response_inspect_canonical_apply_blocked() -> None:
    """Canonical inspect route blocks Apply eligibility in batch repl response."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="inspect",
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="inspection complete",
    )
    context = TurnContext(session_id="t16-i2", turn_id="0001")
    response = _build_batch_repl_response(state, context)
    eligibility = response.get("apply_eligibility", {})
    assert eligibility.get("applyable") is False
    assert eligibility.get("reason") == "no_candidate"
    # Apply blocked — no candidate graph produced
    assert response.get("apply_allowed") is False
    # No change_focus for inspect
    assert "change_focus" not in response


def test_batch_repl_response_clarify_apply_blocked() -> None:
    """clarify route blocks Apply eligibility in batch repl response."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="clarify",
        ui_payload={"nodes": []},
        batch_exit_mode="pure_clarify",
        batch_done_summary="",
    )
    context = TurnContext(session_id="t16-c1", turn_id="0001")
    response = _build_batch_repl_response(state, context)
    assert response["outcome"]["kind"] == "clarify"
    assert isinstance(response["message"], str) and response["message"]
    for forbidden in ("apply_eligibility", "eligibility", "apply_allowed", "canvas_apply_allowed", "queue_allowed"):
        assert forbidden not in response
    # No change_focus for clarify
    assert "change_focus" not in response


def test_batch_repl_response_precedent_research_includes_semantic_checks() -> None:
    """precedent_research route injects semantic check entries."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    plan = {"structural_validation": "advisory", "semantic_validation": "not_evaluated"}
    state = _make_state(
        route="precedent_research",
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="adaptation applied",
        executor_adaptation_plan=plan,
    )
    context = TurnContext(session_id="t16-p1", turn_id="0001")
    response = _build_batch_repl_response(state, context)
    task_sat = response.get("task_satisfaction", [])
    assert len(task_sat) == 2
    checks = {e["check"] for e in task_sat}
    assert "structural_validation" in checks
    assert "semantic_validation" in checks
    # No change_focus for precedent_research
    assert "change_focus" not in response


def test_batch_repl_response_precedent_research_apply_not_blocked() -> None:
    """precedent_research route does not block Apply eligibility."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    plan = {"structural_validation": "pass", "semantic_validation": "pass"}
    state = _make_state(
        route="precedent_research",
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="adapted precedent",
        executor_adaptation_plan=plan,
    )
    context = TurnContext(session_id="t16-p2", turn_id="0001")
    response = _build_batch_repl_response(state, context)
    eligibility = response.get("apply_eligibility", {})
    # precedent_research should NOT be blocked from Apply
    assert eligibility.get("reason") != "no_candidate"


def test_batch_repl_response_precedent_empty_plan_no_semantic_checks() -> None:
    """precedent_research without adaptation_plan does not inject entries."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="precedent_research",
        ui_payload={"nodes": []},
        batch_exit_mode="done",
        batch_done_summary="no adaptation",
        executor_adaptation_plan=None,
    )
    context = TurnContext(session_id="t16-p3", turn_id="0001")
    response = _build_batch_repl_response(state, context)
    task_sat = response.get("task_satisfaction", [])
    assert task_sat == []


def test_batch_repl_response_none_route_no_route_effects() -> None:
    """None route produces no change_focus, no task_satisfaction, no apply block."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route=None,
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="done",
    )
    context = TurnContext(session_id="t16-n1", turn_id="0001")
    response = _build_batch_repl_response(state, context)
    assert "change_focus" not in response
    assert "task_satisfaction" not in response  # not added for non-precedent routes


def test_batch_repl_success_uses_canonical_candidate_identity_and_stage_snapshots() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import StageResult, TurnContext

    state = _make_state(
        graph={"nodes": []},
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="applied change",
    )
    context = TurnContext(
        session_id="canonical-batch",
        turn_id="0003",
        baseline_turn_id="0002",
        idempotency_key="submit:canonical",
    )
    context.record_stage(
        StageResult(
            stage="agent_batch",
            ok=True,
            blocking=False,
            duration_ms=12,
            gate_updates={"python_load_ok": True},
            issues=({"code": "advisory"},),
            value={"summary": "ok"},
        )
    )

    response = _build_batch_repl_response(state, context)

    assert response["candidate"]["turn_identity"] == {
        "session_id": "canonical-batch",
        "turn_id": "0003",
        "baseline_turn_id": "0002",
        "idempotency_key": "submit:canonical",
    }
    assert response["debug"]["turn_identity"] == response["candidate"]["turn_identity"]
    assert response["debug"]["stage_snapshots"] == [
        {
            "stage": "agent_batch",
            "ok": True,
            "blocking": False,
            "duration_ms": 12,
            "gates": {"python_load_ok": True},
            "artifacts": [],
            "issues": [{"code": "advisory"}],
            "value": {"summary": "ok"},
        }
    ]


# ── Integration: _build_dev_success_response route-specific behavior ────────


def test_dev_success_response_direct_edit_includes_change_focus() -> None:
    """direct_edit route injects change_focus into dev success response."""
    from vibecomfy.comfy_nodes.agent.edit import _build_dev_success_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="direct_edit",
        ui_payload={"nodes": []},
    )
    context = TurnContext(session_id="t16-dd1", turn_id="0001")
    response = _build_dev_success_response(state, context, contract="full")
    assert response["change_focus"] == "Focused change"


def test_dev_success_response_inspect_only_apply_blocked() -> None:
    """inspect_only route blocks Apply eligibility in dev success response."""
    from vibecomfy.comfy_nodes.agent.edit import _build_dev_success_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="inspect_only",
        ui_payload={"nodes": []},
    )
    context = TurnContext(session_id="t16-di1", turn_id="0001")
    response = _build_dev_success_response(state, context, contract="full")
    eligibility = response.get("apply_eligibility", {})
    assert eligibility.get("applyable") is False
    assert eligibility.get("reason") == "no_candidate"
    assert "change_focus" not in response


def test_dev_success_response_clarify_apply_blocked() -> None:
    """clarify route blocks Apply eligibility in dev success response."""
    from vibecomfy.comfy_nodes.agent.edit import _build_dev_success_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="clarify",
        ui_payload={"nodes": []},
    )
    context = TurnContext(session_id="t16-dc1", turn_id="0001")
    response = _build_dev_success_response(state, context, contract="full")
    assert response["outcome"]["kind"] == "clarify"
    assert isinstance(response["message"], str) and response["message"]
    for forbidden in ("apply_eligibility", "eligibility", "apply_allowed", "canvas_apply_allowed", "queue_allowed"):
        assert forbidden not in response
    assert "change_focus" not in response


def test_dev_success_response_precedent_research_includes_semantic_checks() -> None:
    """precedent_research injects semantic checks into dev success response."""
    from vibecomfy.comfy_nodes.agent.edit import _build_dev_success_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    plan = {"structural_validation": "pass", "semantic_validation": "advisory"}
    state = _make_state(
        route="precedent_research",
        ui_payload={"nodes": []},
        executor_adaptation_plan=plan,
    )
    context = TurnContext(session_id="t16-dp1", turn_id="0001")
    response = _build_dev_success_response(state, context, contract="full")
    task_sat = response.get("task_satisfaction", [])
    assert len(task_sat) == 2
    checks = {e["check"] for e in task_sat}
    assert "structural_validation" in checks
    assert "semantic_validation" in checks


def test_dev_success_response_precedent_empty_plan_no_entries() -> None:
    """precedent_research without plan does not inject task_satisfaction."""
    from vibecomfy.comfy_nodes.agent.edit import _build_dev_success_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="precedent_research",
        ui_payload={"nodes": []},
        executor_adaptation_plan=None,
    )
    context = TurnContext(session_id="t16-dp2", turn_id="0001")
    response = _build_dev_success_response(state, context, contract="full")
    task_sat = response.get("task_satisfaction", [])
    assert task_sat == []


def test_dev_success_response_none_route_no_route_effects() -> None:
    """None route dev success response has no change_focus or task_satisfaction."""
    from vibecomfy.comfy_nodes.agent.edit import _build_dev_success_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route=None,
        ui_payload={"nodes": []},
    )
    context = TurnContext(session_id="t16-dn1", turn_id="0001")
    response = _build_dev_success_response(state, context, contract="full")
    assert "change_focus" not in response
    assert "task_satisfaction" not in response


def test_dev_success_uses_canonical_candidate_identity_and_stage_snapshots() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _build_dev_success_response
    from vibecomfy.comfy_nodes.agent.contracts import StageResult, TurnContext

    state = _make_state(
        graph={"nodes": []},
        ui_payload={"nodes": [{"id": 1}]},
    )
    context = TurnContext(
        session_id="canonical-dev",
        turn_id="0004",
        baseline_turn_id="0003",
        idempotency_key="submit:dev",
    )
    context.record_stage(
        StageResult(
            stage="validate",
            ok=True,
            blocking=False,
            duration_ms=7,
            gate_updates={"ir_validate_ok": True},
            value={"validated": True},
        )
    )

    response = _build_dev_success_response(state, context, contract="full")

    assert response["candidate"]["turn_identity"] == {
        "session_id": "canonical-dev",
        "turn_id": "0004",
        "baseline_turn_id": "0003",
        "idempotency_key": "submit:dev",
    }
    assert response["debug"]["turn_identity"] == response["candidate"]["turn_identity"]
    assert response["debug"]["stage_snapshots"] == [
        {
            "stage": "validate",
            "ok": True,
            "blocking": False,
            "duration_ms": 7,
            "gates": {"ir_validate_ok": True},
            "artifacts": [],
            "issues": [],
            "value": {"validated": True},
        }
    ]


# ── Integration: no research leak in direct_edit reports ────────────────────


def test_batch_repl_direct_edit_no_research_context_leak() -> None:
    """direct_edit reports must not carry accidental research/precedent keys."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="direct_edit",
        ui_payload={"nodes": [{"id": 1}]},
        batch_exit_mode="done",
        batch_done_summary="applied change",
    )
    context = TurnContext(session_id="t16-nl1", turn_id="0001")
    response = _build_batch_repl_response(state, context)

    # String-scan for research/precedent leaks in the entire response JSON
    response_str = json.dumps(response, sort_keys=True)
    assert "precedent" not in response_str.lower(), (
        "direct_edit response accidentally leaked 'precedent' text"
    )
    # The change_focus label is "Focused change", which is fine
    assert response.get("change_focus") == "Focused change"


def test_dev_success_direct_edit_no_research_context_leak() -> None:
    """direct_edit dev success reports must not carry accidental research keys."""
    from vibecomfy.comfy_nodes.agent.edit import _build_dev_success_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="direct_edit",
        ui_payload={"nodes": [{"id": 1}]},
    )
    context = TurnContext(session_id="t16-nl2", turn_id="0001")
    response = _build_dev_success_response(state, context, contract="full")

    response_str = json.dumps(response, sort_keys=True)
    assert "precedent" not in response_str.lower(), (
        "direct_edit dev response accidentally leaked 'precedent' text"
    )


# ── Structural validation descriptions ──────────────────────────────────────


def test_structural_validation_description_pass() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _structural_validation_description
    desc = _structural_validation_description("pass")
    assert "compatible" in desc


def test_structural_validation_description_fail() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _structural_validation_description
    desc = _structural_validation_description("fail")
    assert "incompatibilities" in desc.lower()


def test_structural_validation_description_advisory() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _structural_validation_description
    desc = _structural_validation_description("advisory")
    assert "advisories" in desc.lower() or "verify" in desc.lower()


def test_structural_validation_description_not_evaluated() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _structural_validation_description
    desc = _structural_validation_description("not_evaluated")
    assert "not evaluated" in desc.lower()


def test_structural_validation_description_unknown_falls_back() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _structural_validation_description
    desc = _structural_validation_description("bogus")
    assert "not evaluated" in desc.lower()


def test_semantic_validation_description_pass() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _semantic_validation_description
    desc = _semantic_validation_description("pass")
    assert "sound" in desc.lower()


def test_semantic_validation_description_fail() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _semantic_validation_description
    desc = _semantic_validation_description("fail")
    assert "alternative" in desc.lower() or "expected" in desc.lower()


def test_semantic_validation_description_advisory() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _semantic_validation_description
    desc = _semantic_validation_description("advisory")
    assert "review" in desc.lower() or "advisories" in desc.lower()


def test_semantic_validation_description_not_evaluated() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _semantic_validation_description
    desc = _semantic_validation_description("not_evaluated")
    assert "not evaluated" in desc.lower()


def test_semantic_validation_description_unknown_falls_back() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _semantic_validation_description
    desc = _semantic_validation_description("bogus")
    assert "not evaluated" in desc.lower()


# ── T18: latest_candidate skips non-candidate (inspect_only / clarify) turns ─

def test_latest_candidate_skips_clarify_outcome_even_with_candidate_state(
    tmp_path: Path,
) -> None:
    """_latest_session_candidate_payload skips turns whose outcome.kind
    is 'clarify', even when the turn state is 'candidate'."""
    from vibecomfy.comfy_nodes.agent.edit import _latest_session_candidate_payload

    session_id = "t18-lc-clarify"
    session_dir = session_dir_for(tmp_path, session_id)
    graph = {"nodes": [{"id": 1, "type": "KSampler"}], "links": []}

    td = session_dir / "turns" / "0000"
    td.mkdir(parents=True)
    (td / "request.json").write_text(
        json.dumps({"task": "clarify task"}), encoding="utf-8"
    )
    (td / "response.json").write_text(
        json.dumps({
            "ok": True,
            "turn_id": "0000",
            "graph": graph,
            "canvas_apply_allowed": False,
            "apply_allowed": False,
            "queue_allowed": False,
            "apply_eligibility": {
                "applyable": False,
                "reason": "no_candidate",
                "message": "No candidate is available to apply.",
            },
            "outcome": {
                "kind": "clarify",
                "question": "Which model should I use?",
            },
        }),
        encoding="utf-8",
    )
    (td / "candidate.ui.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )

    (session_dir / "session_state.json").write_text(
        json.dumps({
            "turns": {
                "0000": {
                    "state": "candidate",
                    "candidate_graph_hash": "hash-clarify",
                }
            }
        }),
        encoding="utf-8",
    )

    result = _latest_session_candidate_payload(session_dir, ["0000"])
    # Clarify outcomes must be skipped — no candidate should be returned
    assert result is None, (
        "clarify outcome must be skipped by _latest_session_candidate_payload"
    )


def test_latest_candidate_skips_noop_outcome_with_candidate_state(
    tmp_path: Path,
) -> None:
    """_latest_session_candidate_payload skips turns whose outcome.kind
    is 'noop' (inspect_only-like), even when the turn state is 'candidate'."""
    from vibecomfy.comfy_nodes.agent.edit import _latest_session_candidate_payload

    session_id = "t18-lc-noop-candidate-state"
    session_dir = session_dir_for(tmp_path, session_id)
    graph = {"nodes": [{"id": 2, "type": "SaveImage"}], "links": []}

    td = session_dir / "turns" / "0000"
    td.mkdir(parents=True)
    (td / "request.json").write_text(
        json.dumps({"task": "inspect graph"}), encoding="utf-8"
    )
    (td / "response.json").write_text(
        json.dumps({
            "ok": True,
            "turn_id": "0000",
            "graph": graph,
            "graph_unchanged": True,
            "canvas_apply_allowed": False,
            "apply_allowed": False,
            "queue_allowed": False,
            "apply_eligibility": {
                "applyable": False,
                "reason": "no_candidate",
                "message": "No candidate is available to apply.",
            },
            "outcome": {
                "kind": "noop",
                "reason": "graph inspection complete — no edits requested",
            },
        }),
        encoding="utf-8",
    )
    (td / "candidate.ui.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )

    (session_dir / "session_state.json").write_text(
        json.dumps({
            "turns": {
                "0000": {
                    "state": "candidate",
                    "candidate_graph_hash": "hash-noop",
                }
            }
        }),
        encoding="utf-8",
    )

    result = _latest_session_candidate_payload(session_dir, ["0000"])
    # Noop (inspect_only) outcomes must be skipped
    assert result is None, (
        "noop outcome must be skipped by _latest_session_candidate_payload"
    )


def test_latest_candidate_skips_non_candidate_state_turns(
    tmp_path: Path,
) -> None:
    """_latest_session_candidate_payload skips turns whose state is not
    'candidate', regardless of outcome."""
    from vibecomfy.comfy_nodes.agent.edit import _latest_session_candidate_payload

    session_id = "t18-lc-non-candidate-state"
    session_dir = session_dir_for(tmp_path, session_id)
    graph = {"nodes": [{"id": 3, "type": "CLIPTextEncode"}], "links": []}

    td = session_dir / "turns" / "0000"
    td.mkdir(parents=True)
    (td / "request.json").write_text(
        json.dumps({"task": "some task"}), encoding="utf-8"
    )
    (td / "response.json").write_text(
        json.dumps({
            "ok": True,
            "turn_id": "0000",
            "graph": graph,
            "canvas_apply_allowed": True,
            "apply_allowed": True,
            "outcome": {"kind": "candidate", "changes": []},
        }),
        encoding="utf-8",
    )
    (td / "candidate.ui.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )

    (session_dir / "session_state.json").write_text(
        json.dumps({
            "turns": {
                "0000": {
                    "state": "accepted",  # not "candidate"
                    "candidate_graph_hash": "hash-accepted",
                }
            }
        }),
        encoding="utf-8",
    )

    result = _latest_session_candidate_payload(session_dir, ["0000"])
    # Non-"candidate" state turns must be skipped
    assert result is None, (
        "non-candidate state turns must be skipped"
    )


def test_latest_candidate_finds_valid_candidate_after_skipping_clarify_and_noop(
    tmp_path: Path,
) -> None:
    """_latest_session_candidate_payload skips clarify and noop turns and
    returns the most recent valid candidate turn."""
    from vibecomfy.comfy_nodes.agent.edit import _latest_session_candidate_payload

    session_id = "t18-lc-skip-multiple"
    session_dir = session_dir_for(tmp_path, session_id)
    graph = {"nodes": [{"id": 4, "type": "PreviewImage"}], "links": []}

    # Turn 0000: clarify (should be skipped)
    td0 = session_dir / "turns" / "0000"
    td0.mkdir(parents=True)
    (td0 / "request.json").write_text(
        json.dumps({"task": "clarify"}), encoding="utf-8"
    )
    (td0 / "response.json").write_text(
        json.dumps({
            "ok": True,
            "outcome": {"kind": "clarify", "question": "Which node?"},
            "apply_eligibility": {
                "applyable": False,
                "reason": "no_candidate",
                "message": "No candidate.",
            },
        }),
        encoding="utf-8",
    )

    # Turn 0001: noop / inspect_only (should be skipped)
    td1 = session_dir / "turns" / "0001"
    td1.mkdir(parents=True)
    (td1 / "request.json").write_text(
        json.dumps({"task": "inspect"}), encoding="utf-8"
    )
    (td1 / "response.json").write_text(
        json.dumps({
            "ok": True,
            "outcome": {"kind": "noop", "reason": "inspection only"},
            "apply_eligibility": {
                "applyable": False,
                "reason": "no_candidate",
                "message": "No candidate.",
            },
        }),
        encoding="utf-8",
    )

    # Turn 0002: real candidate (should be found)
    td2 = session_dir / "turns" / "0002"
    td2.mkdir(parents=True)
    (td2 / "request.json").write_text(
        json.dumps({"task": "real edit"}), encoding="utf-8"
    )
    (td2 / "response.json").write_text(
        json.dumps({
            "ok": True,
            "turn_id": "0002",
            "message": "Real candidate.",
            "graph": graph,
            "canvas_apply_allowed": True,
            "apply_allowed": True,
            "queue_allowed": False,
            "apply_eligibility": {
                "applyable": True,
                "reason": "queue_blocked_warning",
                "message": "Apply allowed.",
            },
            "outcome": {
                "kind": "candidate",
                "changes": [
                    {"uid": "4", "field_path": "type", "old": "Note", "new": "PreviewImage"}
                ],
            },
        }),
        encoding="utf-8",
    )
    (td2 / "candidate.ui.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )

    (session_dir / "session_state.json").write_text(
        json.dumps({
            "turns": {
                "0000": {"state": "completed"},
                "0001": {"state": "completed"},
                "0002": {"state": "candidate"},
            }
        }),
        encoding="utf-8",
    )

    result = _latest_session_candidate_payload(session_dir, ["0002", "0001", "0000"])
    assert result is not None, "should find the real candidate"
    assert result["turn_id"] == "0002", "should skip clarify and noop turns"
    assert result["outcome"]["kind"] == "candidate"


# ── T18: browser-level normalization contract tests (Python-side equivalents) ─

def test_batch_repl_response_inspect_only_blocks_apply_even_if_graph_changes() -> None:
    """inspect_only route blocks Apply eligibility even when a graph is
    present. The graph may be present for inspection purposes, but the
    eligibility reason is always 'no_candidate' and canvas_apply_allowed is
    False. This is the server-side counterpart to browser normalization
    that strips candidateGraph for non-candidate outcomes."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="inspect_only",
        ui_payload={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
        batch_exit_mode="done",
        batch_done_summary="inspection complete",
    )
    context = TurnContext(session_id="t18-ii1", turn_id="0001")
    response = _build_batch_repl_response(state, context)

    # Apply must be blocked regardless of graph presence
    eligibility = response.get("apply_eligibility", {})
    assert eligibility.get("applyable") is False
    assert eligibility.get("reason") == "no_candidate"
    assert "inspect_only" in eligibility.get("message", "")
    # canvas_apply_allowed must be False for inspect_only
    assert response.get("canvas_apply_allowed") is False
    assert response.get("apply_allowed") is False
    # No change_focus for inspect_only
    assert "change_focus" not in response


def test_batch_repl_response_no_candidate_for_pure_clarify() -> None:
    """Pure clarify (no edit+clarify) produces no candidate, Apply blocked,
    graph_unchanged True, canvas_apply_allowed False."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="clarify",
        ui_payload={"nodes": [{"id": 2, "type": "LoadAudio"}], "links": []},
        batch_exit_mode="pure_clarify",
        batch_done_summary="",
    )
    context = TurnContext(session_id="t18-cc1", turn_id="0001")
    response = _build_batch_repl_response(state, context)

    assert response["outcome"]["kind"] == "clarify"
    assert isinstance(response["message"], str) and response["message"]
    for forbidden in (
        "candidate",
        "graph",
        "candidate_graph",
        "candidate_graph_hash",
        "candidate_structural_graph_hash",
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
    ):
        assert forbidden not in response
    # Graph unchanged
    assert response.get("graph_unchanged") is True


def test_batch_repl_response_direct_edit_applyable_with_graph_changes_and_gates() -> None:
    """direct_edit produces a candidate with Apply eligibility when graph
    changes and gates allow. The candidate is present and applyable."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route="direct_edit",
        ui_payload={"nodes": [{"id": 3, "type": "KSampler"}], "links": []},
        graph={"nodes": [{"id": 3, "type": "KSampler", "widgets_values": [1]}], "links": []},
        batch_exit_mode="done",
        batch_done_summary="applied seed change",
        revision_evidence=RevisionEvidence(
            scoped_diff=ScopedDiff(
                changed_nodes=("3",),
                diff_paths=("nodes.3.widgets_values.0",),
                candidate_eligible=True,
            ),
            candidate_eligible=True,
        ),
    )
    context = TurnContext(session_id="t18-de1", turn_id="0001")
    # Simulate passing gates
    context.set_gate("python_load_ok", True, evidence={"ok": True})
    context.set_gate("lower_ok", True, evidence={"ok": True})
    context.set_gate("ir_validate_ok", True, evidence={"ok": True})
    response = _build_batch_repl_response(state, context)

    # Candidate should be present (graph wasn't None + route allows Apply)
    # Apply should NOT be blocked
    eligibility = response.get("apply_eligibility", {})
    assert eligibility.get("reason") != "no_candidate", (
        "direct_edit with gates passing should not be blocked"
    )
    # change_focus marks it as direct_edit
    assert response.get("change_focus") == "Focused change"


def test_batch_repl_response_precedent_research_applyable_with_valid_candidate() -> None:
    """precedent_research produces Apply-eligible candidate when adaptation
    produces a valid graph and gates pass."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    plan = {"structural_validation": "pass", "semantic_validation": "pass"}
    state = _make_state(
        route="precedent_research",
        ui_payload={"nodes": [{"id": 4, "type": "KSampler"}], "links": []},
        batch_exit_mode="done",
        batch_done_summary="adapted precedent",
        executor_adaptation_plan=plan,
    )
    context = TurnContext(session_id="t18-pr1", turn_id="0001")
    response = _build_batch_repl_response(state, context)

    # Apply should NOT be blocked
    eligibility = response.get("apply_eligibility", {})
    assert eligibility.get("reason") != "no_candidate", (
        "precedent_research with valid graph should not be blocked from Apply"
    )
    # semantic checks should be present
    task_sat = response.get("task_satisfaction", [])
    assert len(task_sat) >= 1
    checks = {e["check"] for e in task_sat}
    assert "structural_validation" in checks


def test_batch_repl_response_noop_has_no_candidate_no_apply() -> None:
    """A noop outcome (no graph changes) produces no candidate and no Apply,
    regardless of route. This is the browser normalization baseline."""
    from vibecomfy.comfy_nodes.agent.edit import _build_batch_repl_response
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    state = _make_state(
        route=None,  # legacy no-route path
        ui_payload=None,  # no graph
        batch_exit_mode="noop",
        batch_done_summary="no changes needed",
    )
    context = TurnContext(session_id="t18-no1", turn_id="0001")
    response = _build_batch_repl_response(state, context)

    # No candidate
    assert response.get("candidate") is None
    assert response.get("candidate_graph") is None
    # No Apply
    eligibility = response.get("apply_eligibility", {})
    assert eligibility.get("applyable") is False
    assert eligibility.get("reason") == "no_candidate"
    assert response.get("canvas_apply_allowed") is False
    assert response.get("graph_unchanged") is True



# ── Integration: legacy handle_agent_edit wrapper preserves canonical envelope ─


def test_handle_agent_edit_inspect_route_returns_non_applyable_canonical_envelope(
    tmp_path: Path,
) -> None:
    """The legacy handle_agent_edit wrapper cannot be coerced into emitting an
    applyable edit response for an explanation/planning turn.  A canonical
    inspect route produces a non-applyable envelope even when the underlying
    model returns a batch-looking answer.
    """

    def _inspect_client(_messages):
        return {
            "message": "This workflow loads an image and saves it.",
            "batch": "done()",
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "what does this workflow do?",
            "session_id": "legacy-inspect-envelope",
            "route": "inspect",
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_inspect_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "noop"
    assert result.get("apply_allowed") is False
    assert result.get("canvas_apply_allowed") is False
    eligibility = result.get("apply_eligibility", {})
    assert eligibility.get("applyable") is False
    assert eligibility.get("reason") == "no_candidate"
    assert result.get("candidate") is None
    assert result.get("candidate_graph") is None
    assert result.get("graph_unchanged") is True


def test_handle_agent_edit_clarify_route_returns_non_applyable_canonical_envelope(
    tmp_path: Path,
) -> None:
    """The legacy handle_agent_edit wrapper returns a canonical clarify envelope
    with Apply blocked when the route is clarify.
    """

    def _clarify_client(_messages):
        return {
            "message": "Which style would you like?",
            "batch": 'clarify("Which style would you like?")',
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "make it more cinematic",
            "session_id": "legacy-clarify-envelope",
            "route": "clarify",
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_clarify_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert result["message"] == "Which style would you like?"
    for forbidden in (
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
        "candidate",
        "candidate_graph",
    ):
        assert forbidden not in result, f"{forbidden} should not leak into clarify envelope"
    assert result.get("graph_unchanged") is True


# ── T2: executor durability tests for revise / adapt through handle_agent_edit ─


def test_executor_revise_route_writes_durable_artifacts(
    tmp_path: Path,
) -> None:
    """Executor revise route through handle_agent_edit writes request.json,
    response.json, and chat.json to the turn directory."""
    root = tmp_path / "sessions"

    def _revise_client(_messages):
        return {
            "message": "Changed filename prefix to after.",
            "batch": 'saveimage.filename_prefix = "after"\ndone()',
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "exec-revise-artifacts",
            "route": "revise",
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_revise_client,
        session_root=root,
    )

    assert result["ok"] is True, f"Expected ok=True, got: {json.dumps(result, default=str)[:500]}"
    assert "session_id" in result or result.get("turn_id"), (
        "Revise result must carry durable session/turn metadata"
    )

    turn_id = result.get("turn_id")
    session_id = result.get("session_id", "exec-revise-artifacts")

    # Verify durable turn artifacts on disk
    from vibecomfy.comfy_nodes.agent.session import session_dir_for
    sdir = session_dir_for(root, session_id)
    assert sdir.is_dir(), "Session directory must exist"

    if turn_id:
        turn_dir = sdir / "turns" / turn_id
        assert turn_dir.is_dir(), f"Turn directory {turn_dir} must exist"
        assert (turn_dir / "request.json").is_file(), "request.json must be written"
        assert (turn_dir / "response.json").is_file(), "response.json must be written"
        response_data = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
        assert response_data.get("ok") is True


def test_executor_adapt_route_writes_durable_artifacts(
    tmp_path: Path,
) -> None:
    """Executor adapt route through handle_agent_edit writes durable turn
    artifacts."""
    root = tmp_path / "sessions"

    def _adapt_client(_messages):
        return {
            "message": "Adapted precedent: updated the filename prefix.",
            "batch": 'saveimage.filename_prefix = "adapted"\ndone()',
        }

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "add a preview after the save",
            "session_id": "exec-adapt-artifacts",
            "route": "adapt",
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=_adapt_client,
        session_root=root,
    )

    assert result["ok"] is True, f"Expected ok=True, got: {json.dumps(result, default=str)[:500]}"
    turn_id = result.get("turn_id")
    session_id = result.get("session_id", "exec-adapt-artifacts")

    from vibecomfy.comfy_nodes.agent.session import session_dir_for
    sdir = session_dir_for(root, session_id)
    assert sdir.is_dir()

    if turn_id:
        turn_dir = sdir / "turns" / turn_id
        assert turn_dir.is_dir()
        assert (turn_dir / "request.json").is_file()
        assert (turn_dir / "response.json").is_file()


def test_executor_revise_idempotency_replay_through_edit(
    tmp_path: Path,
) -> None:
    """Executor revise route: same idempotency_key + same payload replays
    the same turn without creating a duplicate."""
    root = tmp_path / "sessions"

    def _revise_client(_messages):
        return {
            "message": "Updated the prefix.",
            "batch": 'saveimage.filename_prefix = "idem-test"\ndone()',
        }

    payload = {
        "graph": _ui_graph(),
        "task": "change the save prefix to idem-test",
        "session_id": "exec-revise-idem",
        "route": "revise",
        "idempotency_key": "exec-revise-key-1",
    }

    first = handle_agent_edit(
        payload,
        schema_provider=_batch_repl_provider(),
        deepseek_client=_revise_client,
        session_root=root,
    )
    assert first["ok"] is True, f"Expected ok=True, got: {json.dumps(first, default=str)[:500]}"
    first_turn_id = first.get("turn_id")
    assert first_turn_id is not None

    # Replay with same payload + same idempotency key
    second = handle_agent_edit(
        dict(payload),
        schema_provider=_batch_repl_provider(),
        deepseek_client=_revise_client,
        session_root=root,
    )
    assert second["ok"] is True, f"Replay failed: {json.dumps(second, default=str)[:500]}"
    # Should return the same turn_id (replay, not new allocation)
    assert second.get("turn_id") == first_turn_id, (
        "Replay must return the same turn_id without allocating a new turn"
    )

    # Verify only one turn exists on disk
    from vibecomfy.comfy_nodes.agent.session import session_dir_for, read_state
    sdir = session_dir_for(root, "exec-revise-idem")
    state = read_state(sdir)
    assert state["next_turn_index"] == 2, (
        "Only one turn allocated; next_turn_index must be 2 (1-based count)"
    )


def test_executor_revise_idempotency_conflict_through_edit(
    tmp_path: Path,
) -> None:
    """Executor revise route: same idempotency_key + different payload
    produces a conflict."""
    root = tmp_path / "sessions"

    def _revise_client(_messages):
        return {
            "message": "Updated the prefix.",
            "batch": 'saveimage.filename_prefix = "conflict-A"\ndone()',
        }

    payload_a = {
        "graph": _ui_graph(),
        "task": "change the save prefix to conflict-A",
        "session_id": "exec-revise-conflict",
        "route": "revise",
        "idempotency_key": "exec-revise-conflict-key",
    }

    first = handle_agent_edit(
        payload_a,
        schema_provider=_batch_repl_provider(),
        deepseek_client=_revise_client,
        session_root=root,
    )
    assert first["ok"] is True, f"Expected ok=True, got: {json.dumps(first, default=str)[:500]}"

    # Different payload, same key
    payload_b = {
        "graph": _ui_graph(),
        "task": "change the save prefix to conflict-B",
        "session_id": "exec-revise-conflict",
        "route": "revise",
        "idempotency_key": "exec-revise-conflict-key",
    }

    conflict = handle_agent_edit(
        payload_b,
        schema_provider=_batch_repl_provider(),
        deepseek_client=_revise_client,
        session_root=root,
    )
    # Conflict should be surfaced as a failure envelope
    assert (
        conflict.get("ok") is False
        or conflict.get("kind") == "StaleStateMismatch"
        or conflict.get("failure_kind") == "StaleStateMismatch"
    ), f"Expected conflict, got: {json.dumps(conflict, default=str)[:500]}"
