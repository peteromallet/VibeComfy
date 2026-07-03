from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace

from vibecomfy.identity.scope import sg_key
from vibecomfy.identity.uid import make_uid
from vibecomfy.porting.reorganise import (
    LayoutCompileOptions,
    ReorganisePreviewOptions,
    SecondStagePlanningOptions,
    apply_layout_candidate_patch_to_ui,
    build_baseline_layout_plan,
    load_layout_sidecar_envelope,
    preview_reorganise_workflow,
)
import vibecomfy.porting.reorganise.orchestrate as orchestrate_module
from vibecomfy.porting.reorganise.orchestrate import assess_reorganise_workflow


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
            _node(6, "Reroute", "reroute"),
        ],
        "links": [
            [1, 1, 0, 3, 0, "MODEL"],
            [2, 2, 0, 3, 1, "CONDITIONING"],
            [3, 3, 0, 4, 0, "LATENT"],
            [4, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [{"title": "Existing", "bounding": [0, 0, 100, 100], "nodes": [1]}],
        "extra": {"ds": {"scale": 1.0, "offset": [0, 0]}},
        "lastRerouteId": 9,
    }


def _second_stage_plan_for_request(request) -> dict:
    return {
        "version": 1,
        "sections": [
            {
                "id": f"second_stage__{request.group.section_id}",
                "kind": "custom",
                "nodes": [ref.to_json() for ref in request.group.group_node_refs],
            }
        ],
    }


def test_preview_reorganise_workflow_builds_deterministic_offline_preview() -> None:
    result = preview_reorganise_workflow(
        _ui(),
        options=ReorganisePreviewOptions(
            compile_options=LayoutCompileOptions(spacing_preset="compact")
        ),
    )

    assert result.ok is True
    assert result.plan_source == "deterministic"
    assert result.parse_diagnostics == ()
    assert result.validation_report is not None
    assert result.validation_report.ok is True
    assert result.plan is not None
    assert result.plan.to_json()["version"] == 1
    assert "layout_reasoning_view" in result.projection.text
    assert result.graph_summary.to_json()["canonical_nodes"]
    assert result.assessment.to_json()["metrics"]
    assert result.candidate_patch is not None
    assert result.apply_data.layout_only_structural_noop is True
    assert result.apply_data.candidate_patch_sha256 is not None
    assert result.to_json()["candidate_patch"]["entries"]["checkpoint"]["properties"]["kept"] == "checkpoint"


def test_preview_reorganise_workflow_preserves_provided_sidecar_envelope() -> None:
    sidecar = {
        "store_version": 2,
        "vibecomfy_version": "sidecar-version",
        "schema_hash": "old",
        "entries": {},
        "groups": [{"title": "Preserved input", "bounding": [1, 2, 3, 4], "nodes": ["checkpoint"]}],
        "extra": {"ds": {"scale": 0.5, "offset": [4, 5]}, "kept": True},
        "lastRerouteId": 44,
        "definitions": {"subgraphs": []},
        "virtual_wires": {"wire": {"type": "GetNode", "endpoints": ["checkpoint"]}},
    }

    result = preview_reorganise_workflow(_ui(), sidecar_envelope=sidecar)

    assert result.ok is True
    assert result.sidecar_envelope["extra"] == sidecar["extra"]
    assert result.sidecar_envelope["lastRerouteId"] == 44
    assert result.compile_result is not None
    patch = result.compile_result.candidate_patch.to_json()
    assert patch["extra"] == sidecar["extra"]
    assert patch["lastRerouteId"] == 44
    assert patch["virtual_wires"] == sidecar["virtual_wires"]


def test_assess_and_preview_can_load_workflow_and_sidecar_paths(tmp_path) -> None:
    workflow_path = tmp_path / "workflow.json"
    sidecar_path = tmp_path / "workflow.layout.json"
    workflow_path.write_text(json.dumps(_ui()), encoding="utf-8")
    sidecar_path.write_text(
        json.dumps(
            {
                "layout_version": 1,
                "nodes": {"checkpoint": {"pos": [99, 100], "size": [200, 80]}},
            }
        ),
        encoding="utf-8",
    )

    sidecar = load_layout_sidecar_envelope(sidecar_path)
    assessment = assess_reorganise_workflow(workflow_path, sidecar_envelope=sidecar_path)
    preview = preview_reorganise_workflow(workflow_path, sidecar_envelope=sidecar_path)

    assert sidecar is not None
    assert sidecar["store_version"] == 2
    assert assessment.loaded.source_label == "workflow.json"
    assert assessment.loaded.source_bytes_sha256 is not None
    assert assessment.assessment.to_json()["verdict"] in {"ok", "needs_reorganise", "blocked"}
    assert preview.ok is True


def test_deterministic_baseline_plan_supports_nested_subgraph_scopes() -> None:
    ui = {
        "nodes": [_node(1, "SubgraphContainer", "container")],
        "definitions": {
            "subgraphs": [
                {
                    "name": "Nested",
                    "nodes": [_node(1, "PrimitiveNode", "inner")],
                    "links": [],
                }
            ]
        },
    }

    result = preview_reorganise_workflow(ui)

    assert result.ok is True
    assert result.validation_report is not None
    assert result.validation_report.diagnostics == ()
    plan = build_baseline_layout_plan(result.facts)
    assert any(section.kind == "container" for section in plan.sections)
    assert any(section.parent_id for section in plan.sections if section.nodes and section.nodes[0].scope_path)


def test_preview_reorganise_workflow_fails_closed_for_invalid_plan_payload() -> None:
    result = preview_reorganise_workflow(_ui(), plan_payload={"version": 2, "sections": []})

    assert result.ok is False
    assert result.plan is None
    assert result.parse_diagnostics
    assert result.validation_report is None
    assert result.compile_result is None
    assert result.candidate_patch is None
    assert result.apply_data.candidate_patch_sha256 is None


def test_semantic_plan_provider_receives_only_sanitized_planning_request() -> None:
    requests = []

    def provider(request):
        requests.append(request.to_json())
        return build_baseline_layout_plan(
            assess_reorganise_workflow(_ui()).facts
        ).to_json()

    result = preview_reorganise_workflow(
        _ui(),
        semantic_plan_provider=provider,
        options=ReorganisePreviewOptions(
            compile_options=LayoutCompileOptions(spacing_preset="wide")
        ),
    )

    assert result.ok is True
    assert result.plan_source == "semantic_provider"
    assert len(requests) == 1
    request = requests[0]
    assert set(request) == {
        "pythonic_projection",
        "graph_facts_summary",
        "layout_plan_schema_reminder",
        "compile_options",
    }
    assert "layout_reasoning_view" in request["pythonic_projection"]
    assert "nodes" not in request
    assert "links" not in request
    assert request["compile_options"]["spacing_preset"] == "wide"
    assert request["layout_plan_schema_reminder"]["name"] == "LayoutPlan v1"
    assert request["layout_plan_schema_reminder"]["schema"]["required"] == [
        "version",
        "sections",
    ]
    assert result.candidate_patch is not None


def test_second_stage_provider_is_not_called_below_complexity_thresholds() -> None:
    requests = []

    result = preview_reorganise_workflow(
        _ui(),
        second_stage_plan_provider=lambda request: requests.append(request),
    )

    assert result.ok is True
    assert requests == []
    assert result.second_stage_results == ()


def test_second_stage_provider_receives_only_complex_group_and_boundary_nodes() -> None:
    nodes = [
        _node(1, "CheckpointLoaderSimple", "source"),
        *[_node(index + 2, "ImageBlend", f"complex_{index}") for index in range(12)],
        _node(20, "SaveImage", "output"),
        _node(99, "CheckpointLoaderSimple", "unrelated"),
    ]
    links = [[1, 1, 0, 2, 0, "IMAGE"]]
    links.extend(
        [index + 2, index + 2, 0, index + 3, 0, "IMAGE"]
        for index in range(11)
    )
    links.append([40, 13, 0, 20, 0, "IMAGE"])
    ui = {"nodes": nodes, "links": links}
    requests = []

    result = preview_reorganise_workflow(
        ui,
        second_stage_plan_provider=lambda request: (
            requests.append(request.to_json()) or _second_stage_plan_for_request(request)
        ),
        options=ReorganisePreviewOptions(
            second_stage_options=SecondStagePlanningOptions(large_group_node_count=12)
        ),
    )

    assert result.ok is True
    assert len(requests) == 1
    request = requests[0]
    assert request["group"]["trigger_reasons"] == ["large_group_node_count"]
    assert sorted(request["group"]["group_node_refs"]) == sorted(
        [["", f"complex_{index}"] for index in range(12)]
    )
    assert sorted(request["group"]["boundary_node_refs"]) == sorted(
        [["", "source"], ["", "output"]]
    )
    assert request["scoped_projection"].splitlines()[0] == "scoped_layout_reasoning_view:"
    assert "complex_0" in request["scoped_projection"]
    assert "source" in request["scoped_projection"]
    assert "output" in request["scoped_projection"]
    assert "unrelated" not in request["scoped_projection"]
    assert "unrelated" not in json.dumps(request["graph_facts_summary"], sort_keys=True)


def test_second_stage_provider_triggers_for_ambiguous_multi_sampler_cluster() -> None:
    ui = {
        "nodes": [
            _node(1, "KSampler", "sampler_a"),
            _node(2, "KSampler", "sampler_b"),
            _node(3, "SaveImage", "output"),
        ],
        "links": [[1, 1, 0, 3, 0, "LATENT"]],
    }
    requests = []

    result = preview_reorganise_workflow(
        ui,
        second_stage_plan_provider=lambda request: (
            requests.append(request.to_json()) or _second_stage_plan_for_request(request)
        ),
        options=ReorganisePreviewOptions(
            second_stage_options=SecondStagePlanningOptions(large_group_node_count=99)
        ),
    )

    assert result.ok is True
    assert len(requests) == 1
    assert requests[0]["group"]["trigger_reasons"] == ["ambiguous_multi_sampler_cluster"]
    assert requests[0]["group"]["group_node_refs"] == [
        ["", "sampler_a"],
        ["", "sampler_b"],
    ]


def test_second_stage_provider_output_fails_closed_on_invalid_plan() -> None:
    nodes = [_node(index + 1, "ImageBlend", f"complex_{index}") for index in range(12)]
    ui = {"nodes": nodes, "links": []}

    result = preview_reorganise_workflow(
        ui,
        second_stage_plan_provider=lambda _request: "not-json",
    )

    assert result.ok is False
    assert len(result.second_stage_results) == 1
    assert result.second_stage_results[0].parse_diagnostics
    assert result.compile_result is None
    assert result.candidate_patch is None
    assert result.apply_data.candidate_patch_sha256 is None


def test_semantic_plan_provider_output_fails_closed_on_parse_validation_and_compile(
    monkeypatch,
) -> None:
    parse_failed = preview_reorganise_workflow(
        _ui(),
        semantic_plan_provider=lambda _request: "not-json",
    )
    assert parse_failed.ok is False
    assert parse_failed.plan_source == "semantic_provider"
    assert parse_failed.parse_diagnostics
    assert parse_failed.validation_report is None
    assert parse_failed.compile_result is None
    assert parse_failed.candidate_patch is None
    assert parse_failed.apply_data.candidate_patch_sha256 is None

    validation_failed = preview_reorganise_workflow(
        _ui(),
        semantic_plan_provider=lambda _request: {
            "version": 1,
            "sections": [
                {
                    "id": "unknown",
                    "kind": "custom",
                    "nodes": [["", "missing"]],
                }
            ],
        },
    )
    assert validation_failed.ok is False
    assert validation_failed.parse_diagnostics == ()
    assert validation_failed.validation_report is not None
    assert validation_failed.validation_report.ok is False
    assert validation_failed.compile_result is None
    assert validation_failed.candidate_patch is None
    assert validation_failed.apply_data.candidate_patch_sha256 is None

    real_compile = orchestrate_module.compile_layout_plan

    def blocked_compile(plan, facts, *, options=None):
        return replace(real_compile(plan, facts, options=options), ok=False)

    monkeypatch.setattr(orchestrate_module, "compile_layout_plan", blocked_compile)
    compile_failed = preview_reorganise_workflow(
        _ui(),
        semantic_plan_provider=lambda _request: build_baseline_layout_plan(
            assess_reorganise_workflow(_ui()).facts
        ).to_json(),
    )
    assert compile_failed.ok is False
    assert compile_failed.validation_report is not None
    assert compile_failed.validation_report.ok is True
    assert compile_failed.compile_result is None
    assert compile_failed.compile_diagnostics
    assert compile_failed.compile_diagnostics[0].code == "layout_compile_failed"
    assert compile_failed.candidate_patch is None
    assert compile_failed.apply_data.candidate_patch_sha256 is None
    assert compile_failed.to_json()["candidate_patch"] is None
    assert compile_failed.to_json()["compile_diagnostics"][0]["code"] == "layout_compile_failed"


def test_apply_layout_candidate_patch_to_ui_only_mutates_furniture_and_reports_noop() -> None:
    ui = _ui()
    ui["state"] = {"lastNodeId": 99, "lastLinkId": 88, "lastRerouteId": 77}
    ui["nodes"][0]["widgets_values"] = ["runtime prompt must stay put"]
    ui["nodes"][0]["inputs"] = [{"name": "model", "link": None, "type": "MODEL"}]
    ui["nodes"][0]["outputs"] = [{"name": "model", "links": [1], "type": "MODEL"}]
    inner_definition = {
        "name": "Inner",
        "nodes": [
            {
                **_node(1, "PrimitiveNode", "inner"),
                "widgets_values": ["inner runtime prompt"],
                "inputs": [{"name": "x", "link": None, "type": "FLOAT"}],
            }
        ],
        "links": [],
        "state": {"lastNodeId": 1, "lastLinkId": 0, "lastRerouteId": 3},
    }
    ui["definitions"] = {
        "subgraphs": [inner_definition]
    }
    original = deepcopy(ui)
    preview = preview_reorganise_workflow(_ui())
    assert preview.candidate_patch is not None
    patch = deepcopy(preview.candidate_patch)

    patch["entries"]["checkpoint"].update(
        {
            "pos": [1111, 2222],
            "type": "PreviewImage",
            "class_type": "PreviewImage",
            "widgets_values": ["malicious prompt rewrite"],
            "inputs": [],
            "properties": {
                "vibecomfy_uid": "evil",
                "kept": "changed layout property",
            },
        }
    )
    nested_key = make_uid(sg_key(inner_definition), "inner")
    patch["entries"][nested_key] = {
        "pos": [3333, 4444],
        "size": [201, 81],
        "flags": {},
        "properties": {"vibecomfy_uid": "evil-inner"},
        "class_type": "DifferentInner",
        "widgets_values": ["malicious inner prompt rewrite"],
    }
    patch["nodes"] = []
    patch["links"] = []
    patch["definitions"] = {
        "subgraphs": [
            {
                "name": "Injected",
                "nodes": [_node(99, "InjectedRuntimeNode", "injected")],
                "links": [[1, 99, 0, 99, 0, "BAD"]],
            }
        ]
    }
    patch["extra"] = {"ds": {"scale": 2.0, "offset": [9, 8]}, "kept_extra": True}
    patch["virtual_wires"] = {"wire-1": {"type": "GetNode", "endpoints": ["checkpoint"]}}
    patch["lastRerouteId"] = 123

    result = apply_layout_candidate_patch_to_ui(ui, patch)

    assert ui == original
    assert result.layout_only_structural_noop is True
    assert result.structural_hash_before == result.structural_hash_after
    assert "checkpoint" in result.applied_entry_keys
    assert nested_key in result.applied_entry_keys
    applied = result.ui_json
    root_node = applied["nodes"][0]
    original_root_node = original["nodes"][0]
    assert root_node["pos"] == [1111, 2222]
    assert root_node["type"] == original_root_node["type"]
    assert root_node["class_type"] == original_root_node["class_type"]
    assert root_node["widgets_values"] == original_root_node["widgets_values"]
    assert root_node["inputs"] == original_root_node["inputs"]
    assert root_node["outputs"] == original_root_node["outputs"]
    assert root_node["properties"]["vibecomfy_uid"] == "checkpoint"
    assert root_node["properties"]["kept"] == "changed layout property"
    assert applied["links"] == original["links"]
    assert applied["state"] == original["state"]
    assert applied["lastRerouteId"] == 123
    assert applied["extra"]["virtual_wires"] == patch["virtual_wires"]
    assert all(
        isinstance(node_id, int)
        for group in applied["groups"]
        for node_id in group.get("nodes", [])
    )

    applied_definition = applied["definitions"]["subgraphs"][0]
    original_definition = original["definitions"]["subgraphs"][0]
    assert applied_definition["name"] == "Inner"
    assert applied_definition["links"] == original_definition["links"]
    assert applied_definition["state"] == original_definition["state"]
    inner_node = applied_definition["nodes"][0]
    original_inner_node = original_definition["nodes"][0]
    assert inner_node["pos"] == [3333, 4444]
    assert inner_node["type"] == original_inner_node["type"]
    assert inner_node["class_type"] == original_inner_node["class_type"]
    assert inner_node["widgets_values"] == original_inner_node["widgets_values"]
    assert inner_node["inputs"] == original_inner_node["inputs"]
