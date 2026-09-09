from __future__ import annotations

import json
from types import MappingProxyType
from types import SimpleNamespace

from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit, read_session_chat
from vibecomfy.comfy_nodes.agent.reorganise import _metrics_payload
from vibecomfy.comfy_nodes.agent.session import payload_hash, read_state, structural_graph_hash
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


_INPUT_ROSTERS = {
    "CheckpointLoaderSimple": ["ckpt_name"],
    "CLIPTextEncode": ["text", "clip"],
    "KSampler": ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise", "model", "positive", "negative", "latent_image"],
    "VAEDecode": ["samples", "vae"],
    "SaveImage": ["filename_prefix", "images"],
}
def _reorganise_schema_provider():
    class Provider:
        def __init__(self):
            self._schemas = {
                "CheckpointLoaderSimple": NodeSchema(
                    class_type="CheckpointLoaderSimple",
                    pack=None,
                    inputs={"ckpt_name": InputSpec("COMBO")},
                    outputs=[OutputSpec("MODEL", "MODEL"), OutputSpec("CLIP", "CLIP"), OutputSpec("VAE", "VAE")],
                    source_provider="test",
                    confidence=1.0,
                ),
                "CLIPTextEncode": NodeSchema(
                    class_type="CLIPTextEncode",
                    pack=None,
                    inputs={"text": InputSpec("STRING"), "clip": InputSpec("CLIP")},
                    outputs=[OutputSpec("CONDITIONING", "CONDITIONING")],
                    source_provider="test",
                    confidence=1.0,
                ),
                "KSampler": NodeSchema(
                    class_type="KSampler",
                    pack=None,
                    inputs={name: InputSpec("ANY") for name in _INPUT_ROSTERS["KSampler"]},
                    outputs=[OutputSpec("LATENT", "LATENT")],
                    source_provider="test",
                    confidence=1.0,
                ),
                "VAEDecode": NodeSchema(
                    class_type="VAEDecode",
                    pack=None,
                    inputs={"samples": InputSpec("LATENT"), "vae": InputSpec("VAE")},
                    outputs=[OutputSpec("IMAGE", "IMAGE")],
                    source_provider="test",
                    confidence=1.0,
                ),
                "SaveImage": NodeSchema(
                    class_type="SaveImage",
                    pack=None,
                    inputs={"filename_prefix": InputSpec("STRING"), "images": InputSpec("IMAGE")},
                    outputs=[],
                    source_provider="test",
                    confidence=1.0,
                ),
                "PreviewImage": NodeSchema(
                    class_type="PreviewImage",
                    pack=None,
                    inputs={"images": InputSpec("IMAGE", required=True)},
                    outputs=[],
                    source_provider="test",
                    confidence=1.0,
                ),
            }
        def get_schema(self, class_type):
            return self._schemas.get(class_type)
        def schemas(self):
            return self._schemas
    return Provider()


_OUTPUT_ROSTERS = {
    "CheckpointLoaderSimple": ["MODEL", "CLIP", "VAE"],
    "CLIPTextEncode": ["CONDITIONING"],
    "KSampler": ["LATENT"],
    "VAEDecode": ["IMAGE"],
    "SaveImage": [],
}


def _node(node_id: int, class_type: str, uid: str) -> dict:
    return {
        "id": node_id,
        "type": class_type,
        "pos": [node_id * 10, node_id * 20],
        "size": [200, 80],
        "color": "#202020",
        "bgcolor": "#101010",
        "title": class_type,
        "inputs": [{"name": name} for name in _INPUT_ROSTERS[class_type]],
        "outputs": [{"name": name} for name in _OUTPUT_ROSTERS[class_type]],
        "properties": {
            "vibecomfy_uid": uid,
        },
    }


def _with_revision(graph: dict, tmp_path, *, schema_provider=None) -> dict:
    from vibecomfy.workflow_bundle import capture_bundle

    seeded = json.loads(json.dumps(graph))
    seeded["workflow_id"] = "6b4611de-b2b2-42f2-b358-5f566d6a8933"
    bundle = capture_bundle(
        seeded,
        tmp_path / "seed.py",
        {"operation": "captured"},
        schema_provider=schema_provider or _reorganise_schema_provider(),
    )
    seeded["revision_id"] = bundle.revision_id
    seeded["parent_revision"] = ""
    return seeded


def _preview_edit_provider():
    class Provider:
        def __init__(self):
            self._schemas = {
                "LoadImage": NodeSchema(
                    class_type="LoadImage",
                    pack=None,
                    inputs={"image": InputSpec("STRING")},
                    outputs=[OutputSpec("IMAGE", "IMAGE"), OutputSpec("MASK", "MASK")],
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
                "PreviewImage": NodeSchema(
                    class_type="PreviewImage",
                    pack=None,
                    inputs={"images": InputSpec("IMAGE", required=True)},
                    outputs=[],
                    source_provider="test",
                    confidence=1.0,
                ),
            }

        def get_schema(self, class_type):
            return self._schemas.get(class_type)

        def schemas(self):
            return self._schemas

    return Provider()


def _preview_edit_ui() -> dict:
    workflow_id = "6b4611de-b2b2-42f2-b358-5f566d6a8933"
    wf = VibeWorkflow(workflow_id, WorkflowSource(workflow_id))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "before"})
    wf.connect("1.0", "2.images")
    graph = emit_ui_json(wf, schema_provider=_preview_edit_provider())
    for node in graph["nodes"]:
        node.setdefault("properties", {})["vibecomfy_uid"] = str(node["id"])
        node.setdefault("color", "#202020")
        node.setdefault("bgcolor", "#101010")
    return graph


def _ui() -> dict:
    graph = {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "CLIPTextEncode", "positive"),
            _node(3, "KSampler", "sample"),
            _node(4, "VAEDecode", "decode"),
            _node(5, "SaveImage", "save"),
        ],
        "links": [
            [1, 1, 0, 3, 6, "MODEL"],
            [2, 2, 0, 3, 7, "CONDITIONING"],
            [3, 3, 0, 4, 0, "LATENT"],
            [4, 4, 0, 5, 1, "IMAGE"],
        ],
        "groups": [
            {
                "vibecomfy_group_id": "g-1",
                "title": "Existing",
                "bounding": [0, 0, 100, 100],
            }
        ],
        "extra": {"ds": {"scale": 1.0, "offset": [0, 0]}},
    }
    for link_id, _source, _source_slot, target, target_slot, _kind in graph["links"]:
        graph["nodes"][target - 1]["inputs"][target_slot]["link"] = link_id
    return graph


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
            [5, 1, 0, 7, 6, "MODEL"],
            [6, 6, 0, 7, 7, "CONDITIONING"],
            [7, 7, 0, 8, 0, "LATENT"],
            [8, 8, 0, 9, 1, "IMAGE"],
        ]
    )
    for link_id, _source, _source_slot, target, target_slot, _kind in graph["links"][-4:]:
        graph["nodes"][target - 1]["inputs"][target_slot]["link"] = link_id
    return graph


def test_explicit_reorganise_skill_runs_inside_durable_agent_turn(tmp_path) -> None:
    graph = _with_revision(_ui(), tmp_path)
    result = handle_agent_edit(
        {
            "task": "/reorganise_comfy_workflow",
            "graph": graph,
            "revision_id": graph["revision_id"],
            "parent_revision": graph["parent_revision"],
            "workflow_id": "6b4611de-b2b2-42f2-b358-5f566d6a8933",
            "session_id": "reorganise-session",
            "idempotency_key": "reorganise-once",
        },
        schema_provider=_reorganise_schema_provider(),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["route"] == "reorganise"
    assert result["outcome"]["kind"] == "candidate"
    assert result["candidate"]["state"] == "candidate_ready"
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
    metrics = result["report"]["metrics"]
    assert metrics["before_assessment"] is not None
    assert metrics["after_assessment"] is not None
    assert metrics["assessment"] == metrics["after_assessment"]
    assert "Assessed graph: candidate" in result["report"]["report"]
    patch_apply = result["report"]["evidence"]["patch_apply"]
    assert patch_apply["layout_only_structural_noop"] is True
    assert result["authority_receipt"]["verification_kind"] == "layout_structural_noop"
    assert result["authority_receipt"]["replay_ok"] is True
    assert result["authority_receipt"]["candidate_matches"] is True

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
    assert state["turns"][result["turn_id"]]["state"] == "candidate_ready"


def test_reorganise_accepts_litegraph_indexed_geometry(tmp_path) -> None:
    graph = _with_revision(_ui(), tmp_path)
    graph["nodes"][0]["size"] = {"0": 315, "1": 122}
    graph["nodes"][1]["pos"] = {"0": 123.5, "1": 456.5}

    result = handle_agent_edit(
        {
            "task": "Reorganise this workflow",
            "route": "reorganise",
            "executor_route": "reorganise",
            "graph": graph,
            "workflow_id": "6b4611de-b2b2-42f2-b358-5f566d6a8933",
            "revision_id": graph["revision_id"],
            "parent_revision": graph["parent_revision"],
            "session_id": "reorganise-indexed-geometry",
            "idempotency_key": "reorganise-indexed-geometry-once",
        },
        schema_provider=_reorganise_schema_provider(),
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["route"] == "reorganise"
    assert result["outcome"]["kind"] == "candidate"
    assert result["candidate"]["state"] == "candidate_ready"


def test_reorganise_metrics_thaw_mappingproxy_diagnostics() -> None:
    """Compile diagnostics can carry frozen edge-pair mappings."""

    result = SimpleNamespace(
        assessment=SimpleNamespace(to_json=lambda: {"diagnostics": [], "issues": [], "verdict": "ok"}),
        graph_summary=SimpleNamespace(to_json=lambda: {"nodes": []}),
        projection=SimpleNamespace(
            token_estimate=1,
            scope_count=1,
            canonical_ref_count=1,
            summarized=False,
            truncated=False,
        ),
        compile_result=SimpleNamespace(
            ok=True,
            options=SimpleNamespace(to_json=lambda: {}),
            report=SimpleNamespace(
                to_json=lambda: {
                    "diagnostics": [
                        {
                            "code": "edge_crossings",
                            "detail": {
                                "edge_pairs": [
                                    [
                                        MappingProxyType({"source": ["", "1"], "target": ["", "2"]}),
                                        MappingProxyType({"source": ["", "3"], "target": ["", "4"]}),
                                    ]
                                ]
                            },
                        }
                    ]
                }
            ),
            node_layouts=[object()],
            group_layouts=[],
        ),
    )

    payload = _metrics_payload(result)

    assert payload["compile"]["report"]["diagnostics"][0]["detail"]["edge_pairs"][0][0] == {
        "source": ["", "1"],
        "target": ["", "2"],
    }
    json.dumps(payload, sort_keys=True)


def test_candidate_mode_reorganise_uses_durable_candidate_lifecycle(
    tmp_path,
    monkeypatch,
) -> None:
    from vibecomfy.comfy_nodes.agent.routes import _handle_agent_edit_accept

    monkeypatch.setenv("VIBECOMFY_REORGANISE_AUTO", "candidate")
    monkeypatch.delenv("VIBECOMFY_NARRATOR_ROUTE", raising=False)
    monkeypatch.delenv("VIBECOMFY_NARRATOR_MODEL", raising=False)
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
        lambda **_kwargs: {"json": {}},
    )
    from vibecomfy.workflow_bundle import capture_bundle

    provider = _preview_edit_provider()
    graph = _preview_edit_ui()
    workflow_id = "6b4611de-b2b2-42f2-b358-5f566d6a8933"
    revision_id = capture_bundle(
        {**graph, "workflow_id": workflow_id},
        tmp_path / "seed.py",
        {"operation": "captured"},
        schema_provider=provider,
    ).revision_id

    def _functional_batch(_messages):
        return {
            "batch": "preview = PreviewImage(images=loadimage.IMAGE)\ndone()",
            "message": "Added a preview image output.",
        }

    payload = {
        "task": "add a preview branch",
        "graph": graph,
        "workflow_id": workflow_id,
        "revision_id": revision_id,
        "parent_revision": "",
        "session_id": "auto-reorganise-session",
        "idempotency_key": "auto-reorganise-once",
    }

    result = handle_agent_edit(
        payload,
        schema_provider=provider,
        deepseek_client=_functional_batch,
        session_root=tmp_path,
    )
    replay = handle_agent_edit(
        payload,
        schema_provider=provider,
        deepseek_client=_functional_batch,
        session_root=tmp_path,
    )

    assert replay == result
    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"
    assert result["apply_eligibility"]["applyable"] is True
    accepted = result["accepted_batch"]
    assert accepted
    assert any(
        item["op"]["op"] == "add_node" and item["op"]["class_type"] == "PreviewImage"
        for item in accepted
    )
    layout = result["layout_reorganisation"]
    assert layout["result"] == "prepare_candidate"
    assert layout["candidate_prepared"] is True
    functional_hash = layout["functional_candidate_graph_hash"]
    assert functional_hash
    assert layout["evidence"]["layout_only_structural_noop"] is True
    assert result["candidate_graph_hash"] != functional_hash
    assert result["candidate"]["graph"] == result["graph"]
    assert result["authority_receipt"]["verification_kind"] == "layout_structural_noop"
    assert result["authority_receipt"]["replay_ok"] is True
    assert result["authority_receipt"]["candidate_matches"] is True

    turn_dir = tmp_path / "auto-reorganise-session" / "turns" / result["turn_id"]
    persisted = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
    persisted_candidate = json.loads((turn_dir / "candidate.ui.json").read_text(encoding="utf-8"))
    assert persisted["candidate"]["graph"] == result["candidate"]["graph"]
    assert persisted_candidate == result["candidate"]["graph"]
    state = read_state(tmp_path / "auto-reorganise-session")
    assert state["turns"][result["turn_id"]]["state"] == "candidate_ready"
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
    assert stale["kind"] == "EditorAheadConflict"

    legacy_accept = _handle_agent_edit_accept(
        {
            "session_id": "auto-reorganise-session",
            "turn_id": result["turn_id"],
            "client_graph_hash": result["submit_graph_hash"],
            "idempotency_key": "accept-auto-reorganise",
        },
        session_root=tmp_path,
    )
    assert legacy_accept["ok"] is False
    assert legacy_accept["kind"] == "EditorAheadConflict"
    state_after_legacy_accept = read_state(tmp_path / "auto-reorganise-session")
    assert state_after_legacy_accept["turns"][result["turn_id"]]["state"] == "candidate_ready"


def test_reorganise_route_bad_plan_fails_closed_without_candidate(tmp_path) -> None:
    result = handle_agent_edit(
        {
            "task": "please clean this layout",
            "route": "reorganise",
            "graph": _ui(),
            "session_id": "reorganise-session",
            "layout_plan": {"version": 2, "sections": []},
        },
        schema_provider=_reorganise_schema_provider(),
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
        schema_provider=_reorganise_schema_provider(),
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
