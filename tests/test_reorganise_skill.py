from __future__ import annotations

import json

from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit, read_session_chat
from vibecomfy.comfy_nodes.agent.session import payload_hash, read_state, structural_graph_hash


def _node(node_id: int, class_type: str, uid: str) -> dict:
    return {
        "id": node_id,
        "type": class_type,
        "class_type": class_type,
        "pos": [node_id * 10, node_id * 20],
        "size": [200, 80],
        "properties": {"vibecomfy_uid": uid, "kept": uid},
    }


def _ui() -> dict:
    return {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "CLIPTextEncode", "positive"),
            _node(3, "KSampler", "sample"),
            _node(4, "VAEDecode", "decode"),
            _node(5, "SaveImage", "save"),
        ],
        "links": [
            [1, 1, 0, 3, 0, "MODEL"],
            [2, 2, 0, 3, 1, "CONDITIONING"],
            [3, 3, 0, 4, 0, "LATENT"],
            [4, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [{"title": "Existing", "bounding": [0, 0, 100, 100], "nodes": [1]}],
        "extra": {"ds": {"scale": 1.0, "offset": [0, 0]}},
    }


def _ui_with_branch() -> dict:
    graph = json.loads(json.dumps(_ui()))
    graph["nodes"].extend(
        [
            _node(6, "CLIPTextEncode", "branch-positive"),
            _node(7, "KSampler", "branch-sample"),
            _node(8, "VAEDecode", "branch-decode"),
            _node(9, "SaveImage", "branch-save"),
        ]
    )
    for node in graph["nodes"]:
        if node["id"] >= 6:
            node["pos"] = [12, 24]
    graph["links"].extend(
        [
            [5, 1, 0, 7, 0, "MODEL"],
            [6, 6, 0, 7, 1, "CONDITIONING"],
            [7, 7, 0, 8, 0, "LATENT"],
            [8, 8, 0, 9, 0, "IMAGE"],
        ]
    )
    return graph


def test_explicit_reorganise_skill_runs_inside_durable_agent_turn(tmp_path) -> None:
    graph = _ui()
    result = handle_agent_edit(
        {
            "task": "/reorganise_comfy_workflow",
            "graph": graph,
            "session_id": "reorganise-session",
            "idempotency_key": "reorganise-once",
        },
        schema_provider=object(),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["route"] == "reorganise"
    assert result["outcome"]["kind"] == "candidate"
    assert result["candidate"]["state"] == "candidate"
    assert result["candidate"]["turn_identity"]["session_id"] == "reorganise-session"
    assert result["candidate"]["turn_identity"]["turn_id"] == result["turn_id"]
    assert result["apply_eligibility"]["applyable"] is True
    assert result["candidate_graph_hash"] != result["submit_graph_hash"]
    assert result["gates"]["plan_validate_ok"] is True
    assert result["gates"]["ui_emit_ok"] is True
    assert result["gates"]["ui_fidelity_ok"] is True
    assert result["report"]["evidence"]["layout_only_structural_noop"] is True
    assert result["report"]["evidence"]["candidate_available"] is True
    assert result["report"]["evidence"]["full_ui_payload_hash_changed"] is True
    patch_apply = result["report"]["evidence"]["patch_apply"]
    assert patch_apply["structural_hash_before"] == patch_apply["structural_hash_after"]

    turn_dir = tmp_path / "reorganise-session" / "turns" / result["turn_id"]
    for artifact in (
        "request.json",
        "original.ui.json",
        "projection.txt",
        "reorganisation_plan.json",
        "reorganisation_report.md",
        "reorganisation_metrics.json",
        "structural_noop_evidence.json",
        "candidate.ui.json",
        "response.json",
        "chat.json",
    ):
        assert (turn_dir / artifact).exists(), artifact

    persisted = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
    assert persisted["candidate"]["graph"] == result["candidate"]["graph"]
    state = read_state(tmp_path / "reorganise-session")
    assert state["turns"][result["turn_id"]]["state"] == "candidate"


def test_candidate_mode_reorganise_uses_durable_candidate_lifecycle(
    tmp_path,
    monkeypatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

    monkeypatch.setenv("VIBECOMFY_REORGANISE_AUTO", "candidate")
    before = _ui()
    functional = _ui_with_branch()
    functional_hash = payload_hash(functional)

    def _fake_functional_candidate(state, context, **_kwargs):
        state.ui_payload = functional
        state.batch_exit_mode = "done"
        state.batch_done_summary = "Added the branch."
        for gate_name in list(context.gate_results):
            context.set_gate(gate_name, True)
        return state

    monkeypatch.setattr(
        agent_edit_module,
        "_run_batch_repl_product_path",
        _fake_functional_candidate,
    )
    payload = {
        "task": "add a preview branch",
        "graph": before,
        "session_id": "auto-reorganise-session",
        "idempotency_key": "auto-reorganise-once",
    }

    result = handle_agent_edit(
        payload,
        schema_provider=object(),
        session_root=tmp_path,
    )
    replay = handle_agent_edit(
        payload,
        schema_provider=object(),
        session_root=tmp_path,
    )

    assert replay == result
    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert result["apply_eligibility"]["applyable"] is True
    assert result["layout_reorganisation"]["result"] == "prepare_candidate"
    assert result["layout_reorganisation"]["candidate_prepared"] is True
    assert result["layout_reorganisation"]["functional_candidate_graph_hash"] == functional_hash
    assert result["layout_reorganisation"]["evidence"]["layout_only_structural_noop"] is True
    assert result["candidate_graph_hash"] != functional_hash
    assert result["candidate"]["graph"] == result["graph"]

    turn_dir = tmp_path / "auto-reorganise-session" / "turns" / result["turn_id"]
    persisted = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
    persisted_candidate = json.loads((turn_dir / "candidate.ui.json").read_text(encoding="utf-8"))
    assert persisted["candidate"]["graph"] == result["candidate"]["graph"]
    assert persisted_candidate == result["candidate"]["graph"]
    state = read_state(tmp_path / "auto-reorganise-session")
    assert state["turns"][result["turn_id"]]["state"] == "candidate"
    assert state["turns"][result["turn_id"]]["candidate_graph_hash"] == result["candidate_graph_hash"]

    chat = read_session_chat(tmp_path, "auto-reorganise-session")
    assert chat["latest_candidate"]["turn_id"] == result["turn_id"]
    assert chat["latest_candidate"]["candidate_graph_hash"] == result["candidate_graph_hash"]

    stale = _handle_agent_edit_accept(
        {
            "session_id": "auto-reorganise-session",
            "turn_id": result["turn_id"],
            "client_graph_hash": "not-the-submitted-graph",
            "idempotency_key": "accept-stale",
        },
        session_root=tmp_path,
    )
    assert stale["ok"] is False
    assert stale["kind"] == "StaleStateMismatch"

    accepted = _handle_agent_edit_accept(
        {
            "session_id": "auto-reorganise-session",
            "turn_id": result["turn_id"],
            "client_graph_hash": result["submit_graph_hash"],
            "idempotency_key": "accept-auto-reorganise",
        },
        session_root=tmp_path,
    )
    assert accepted["ok"] is True
    assert accepted["candidate_graph_hash"] == result["candidate_graph_hash"]
    assert accepted["baseline_graph_hash"] == result["candidate_structural_graph_hash"]


def test_reorganise_route_bad_plan_fails_closed_without_candidate(tmp_path) -> None:
    result = handle_agent_edit(
        {
            "task": "please clean this layout",
            "route": "reorganise",
            "graph": _ui(),
            "session_id": "reorganise-session",
            "layout_plan": {"version": 2, "sections": []},
        },
        schema_provider=object(),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["route"] == "reorganise"
    assert result["outcome"]["kind"] == "noop"
    assert result["candidate"] is None
    assert result["apply_eligibility"]["applyable"] is False
    assert result["no_candidate_reason"] == "reorganise_preview_failed"
    turn_dir = tmp_path / "reorganise-session" / "turns" / result["turn_id"]
    assert not (turn_dir / "candidate.ui.json").exists()
    assert (turn_dir / "reorganisation_plan.json").exists()


def test_reorganise_route_rejects_bad_layout_plan_outputs_without_candidate(tmp_path) -> None:
    bad_plans = [
        "this is not json",
        {
            "version": 1,
            "sections": [
                {
                    "id": "sampling",
                    "kind": "sampling",
                    "nodes": [["", "sample"], ["", "ghost"]],
                }
            ],
            "unassigned_policy": "reject",
        },
        {
            "version": 1,
            "sections": [
                {
                    "id": "sampling",
                    "kind": "sampling",
                    "nodes": [["", "sample"], ["", "save"]],
                },
                {
                    "id": "output",
                    "kind": "output",
                    "nodes": [
                        ["", "checkpoint"],
                        ["", "positive"],
                        ["", "decode"],
                        ["", "save"],
                    ],
                },
            ],
            "unassigned_policy": "reject",
        },
    ]

    for index, plan in enumerate(bad_plans):
        result = handle_agent_edit(
            {
                "task": "please clean this layout",
                "route": "reorganise",
                "graph": _ui(),
                "session_id": f"reorganise-bad-plan-{index}",
                "layout_plan": plan,
            },
            schema_provider=object(),
            session_root=tmp_path,
        )

        assert result["ok"] is True
        assert result["route"] == "reorganise"
        assert result["outcome"]["kind"] == "noop"
        assert result["candidate"] is None
        assert result["candidate_graph_hash"] is None
        assert result["apply_eligibility"]["applyable"] is False
        assert result["gates"]["plan_validate_ok"] is False
        assert result["gates"]["ui_emit_ok"] is False
        assert result["gates"]["ui_fidelity_ok"] is False
        assert result["no_candidate_reason"] == "reorganise_preview_failed"
        turn_dir = tmp_path / f"reorganise-bad-plan-{index}" / "turns" / result["turn_id"]
        assert not (turn_dir / "candidate.ui.json").exists()


def test_reorganise_route_layout_patch_structural_drift_fails_closed(
    tmp_path,
    monkeypatch,
) -> None:
    def _raise_structural_drift(*_args, **_kwargs):
        raise ValueError("layout candidate patch changed workflow structure")

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.reorganise.apply_layout_candidate_patch_to_ui",
        _raise_structural_drift,
    )

    result = handle_agent_edit(
        {
            "task": "/reorganise_comfy_workflow",
            "graph": _ui(),
            "session_id": "reorganise-structural-drift",
        },
        schema_provider=object(),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["route"] == "reorganise"
    assert result["outcome"]["kind"] == "noop"
    assert result["candidate"] is None
    assert result["apply_eligibility"]["applyable"] is False
    assert result["gates"]["plan_validate_ok"] is True
    assert result["gates"]["ui_emit_ok"] is False
    assert result["gates"]["ui_load_safe_ok"] is False
    assert result["report"]["evidence"]["candidate_available"] is False
    assert result["report"]["evidence"]["patch_apply_error"]["code"] == (
        "layout_candidate_patch_apply_failed"
    )
