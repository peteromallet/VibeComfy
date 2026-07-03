from __future__ import annotations

import json

from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
from vibecomfy.comfy_nodes.agent.session import read_state


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
