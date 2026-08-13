from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.demo_factory import additive_judge
from vibecomfy.demo_factory.additive_judge import AdditiveJudgeResult
from vibecomfy.demo_factory import baseline
from vibecomfy.demo_factory.baseline import (
    run_baseline,
    structural_check_graph,
    write_baseline_proof,
)
from vibecomfy.demo_factory.case import Case, _evaluate
from vibecomfy.demo_factory.oracle import Oracle, Verdict
from vibecomfy.demo_factory.predicates import AdditiveWitnessVerdict
from vibecomfy.demo_factory.run_campaign import (
    _multinode_spec,
    _remove_subgraph_fault,
)
from vibecomfy.ingest.normalize import from_api, normalize_to_api


def _connected_graph(
    sink_type: str = "SaveImage",
    *,
    source_type: str = "CustomProducer",
) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 1,
                "type": source_type,
                "inputs": [],
                "outputs": [{"name": "value", "type": "*", "links": [1]}],
                "widgets_values": [],
            },
            {
                "id": 2,
                "type": sink_type,
                "mode": 0,
                "inputs": [{"name": "value", "type": "*", "link": 1}],
                "outputs": [],
                "widgets_values": [],
            },
        ],
        "links": [[1, 1, 0, 2, 0, "*"]],
    }


def _report(
    monkeypatch: pytest.MonkeyPatch,
    diagnostics: list[dict[str, Any]] | None = None,
    *,
    ok: bool = False,
) -> None:
    payload = {
        "ok": ok,
        "diagnostics": diagnostics or [],
        "public_outputs": [],
    }
    monkeypatch.setattr(
        baseline,
        "_run_port_check_report",
        lambda graph, *, timeout, allow_environment_resolution: (None, payload),
    )


def _diag(
    code: str,
    *,
    class_type: str | None = None,
    node_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": code,
        "severity": "error",
        "class_type": class_type,
        "node_id": node_id,
        "detail": detail or {},
        "recommendation": None,
    }


def test_unresolved_custom_class_with_reachable_output_is_structural_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _report(
        monkeypatch,
        [
            _diag(
                "unresolved_runtime_class",
                class_type="CustomProducer",
                detail={"runtime_class_type": "CustomProducer"},
            ),
            _diag(
                "unknown_class_type",
                class_type="CustomProducer",
                node_id="1",
            ),
        ],
    )

    result = structural_check_graph(_connected_graph())

    assert result["passed"] is True
    assert result["structural_safe"] is True
    assert result["output_reachable"] is True
    assert result["schema_unavailable_classes"] == ["CustomProducer"]
    assert result["checks_skipped_for_missing_schema"][0]["class_type"] == (
        "CustomProducer"
    )


def test_pre_existing_unresolved_never_blocks_candidate_gate_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _report(
        monkeypatch,
        [_diag("unknown_class_type", class_type="CustomProducer", node_id="1")],
    )

    result = structural_check_graph(
        _connected_graph(),
        pre_existing_types={"CustomProducer", "SaveImage"},
    )

    assert result["passed"] is True
    warning = next(
        item
        for item in result["warnings"]
        if item["code"] == "unknown_class_type"
    )
    assert warning["detail"]["node_origin"] == "pre_existing"
    assert warning["detail"]["fixer_introduced"] is False


def test_fixer_introduced_unresolved_is_flagged_without_false_nonexistence_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _connected_graph()
    graph["nodes"].append(
        {
            "id": 3,
            "type": "InventedButUnprovenNode",
            "inputs": [],
            "outputs": [],
            "widgets_values": [],
        }
    )
    _report(
        monkeypatch,
        [
            _diag(
                "unresolved_runtime_class",
                class_type="InventedButUnprovenNode",
                detail={"runtime_class_type": "InventedButUnprovenNode"},
            )
        ],
    )

    result = structural_check_graph(
        graph,
        pre_existing_types={"CustomProducer", "SaveImage"},
    )

    assert result["passed"] is True
    assert result["fixer_introduced_schema_unavailable_classes"] == [
        "InventedButUnprovenNode"
    ]
    warning = next(
        item
        for item in result["warnings"]
        if item["code"] == "unresolved_runtime_class"
    )
    assert warning["detail"]["node_origin"] == "fixer_introduced"


def test_defaultable_vhs_fields_warn_in_structural_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics = [
        _diag(
            "known_runtime_required_input_missing",
            class_type="VHS_VideoCombine",
            node_id="2",
            detail={
                "category": "runtime_contract",
                "input": field,
                "source": "committed_runtime_required_inputs",
            },
        )
        for field in ("loop_count", "pingpong", "save_output")
    ]
    _report(monkeypatch, diagnostics)

    result = structural_check_graph(_connected_graph("VHS_VideoCombine"))

    assert result["passed"] is True
    assert not result["hard_blockers"]
    assert {
        item["detail"]["input"]
        for item in result["warnings"]
        if item["code"] == "known_runtime_required_input_missing"
    } == {"loop_count", "pingpong", "save_output"}


def test_credible_exposed_non_defaultable_required_input_is_hard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _connected_graph()
    graph["nodes"][0]["inputs"] = [
        {"name": "required_value", "type": "STRING", "link": None}
    ]
    _report(
        monkeypatch,
        [
            _diag(
                "missing_required_input",
                class_type="CustomProducer",
                node_id="1",
                detail={
                    "node_id": "1",
                    "class_type": "CustomProducer",
                    "input": "required_value",
                    "has_default": False,
                    "schema_confidence": 1.0,
                },
            )
        ],
    )

    result = structural_check_graph(graph)

    assert result["passed"] is False
    assert result["hard_blockers"][0]["detail"]["structural_reason"] == (
        "credible_non_defaultable_required_input"
    )


def test_asset_enum_warns_but_semantic_enum_is_hard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset = _diag(
        "value_not_in_enum",
        class_type="VAELoader",
        node_id="1",
        detail={
            "input": "vae_name",
            "value": "remote-only.safetensors",
            "choice_scope": "environment_asset",
        },
    )
    _report(monkeypatch, [asset])
    asset_result = structural_check_graph(_connected_graph())
    assert asset_result["passed"] is True
    assert asset_result["warnings"][0]["detail"]["structural_reason"] == (
        "environment_asset_inventory"
    )

    semantic = _diag(
        "value_not_in_enum",
        class_type="KSampler",
        node_id="1",
        detail={
            "input": "sampler_name",
            "value": "definitely-not-a-sampler",
            "choice_scope": "semantic",
        },
    )
    _report(monkeypatch, [semantic])
    semantic_result = structural_check_graph(_connected_graph())
    assert semantic_result["passed"] is False
    assert semantic_result["hard_blockers"][0]["detail"][
        "structural_reason"
    ] == "semantic_enum"


def test_genuine_raw_dangling_edge_is_hard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _connected_graph()
    graph["links"][0][1] = 99
    _report(monkeypatch)

    result = structural_check_graph(graph)

    assert result["passed"] is False
    assert any(
        blocker["code"] == "raw_link_missing_endpoint"
        for blocker in result["hard_blockers"]
    )


@pytest.mark.parametrize("sink_type", ["ModelSave", "SaveAudio", "PreviewAudio"])
def test_model_and_audio_output_boundaries_are_recognized(
    monkeypatch: pytest.MonkeyPatch,
    sink_type: str,
) -> None:
    _report(monkeypatch)

    result = structural_check_graph(_connected_graph(sink_type))

    assert result["passed"] is True
    assert result["output_boundary"]["class_type"] == sink_type
    assert result["output_boundary"]["rule"] in {
        "shared_output_catalog",
        "shared_terminal_output_heuristic",
    }


def test_no_reachable_output_still_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "SaveImage",
                "inputs": [],
                "outputs": [],
                "widgets_values": [],
            }
        ],
        "links": [],
    }
    _report(monkeypatch)

    result = structural_check_graph(graph)

    assert result["passed"] is False
    assert result["output_reachable"] is False
    assert any(
        blocker["code"] == "no_reachable_output"
        for blocker in result["hard_blockers"]
    )


def test_baseline_proof_persists_complete_structured_port_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    long_message = "unresolved schema: " + ("x" * 300)
    diagnostic = _diag(
        "unknown_class_type",
        class_type="CustomProducer",
        node_id="1",
    )
    diagnostic["message"] = long_message
    _report(monkeypatch, [diagnostic])

    result = run_baseline(_connected_graph())
    write_baseline_proof(result, tmp_path)
    proof = json.loads(
        (tmp_path / "proof" / "baseline.json").read_text(encoding="utf-8")
    )

    assert proof["passed"] is True
    assert proof["port_report"]["diagnostics"][0]["message"] == long_message
    assert proof["warnings"][0]["code"] == "unknown_class_type"


def test_widget_shaped_literal_does_not_manufacture_runtime_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = {
        "nodes": [
            {
                "id": 4,
                "type": "Integer",
                "inputs": [],
                "outputs": [{"links": [1], "type": "INT"}],
                "widgets_values": [1],
            },
            {
                "id": 6,
                "type": "LazySwitchKJ",
                "inputs": [{"name": "on_true", "link": 1, "type": "INT"}],
                "outputs": [{"links": [2], "type": "*"}],
                "widgets_values": [["1897", 1]],
            },
            {
                "id": 7,
                "type": "VHS_VideoCombine",
                "inputs": [{"name": "images", "link": 2, "type": "*"}],
                "outputs": [],
                "widgets_values": [],
            },
        ],
        "links": [
            [1, 4, 0, 6, 0, "INT"],
            [2, 6, 0, 7, 0, "*"],
        ],
    }
    manufactured = _diag(
        "api_compile_failed",
        detail={
            "category": "schema",
            "compile_code": "compiled_edge_missing_endpoint",
            "source_node_id": "1897",
            "source_output": 1,
            "target_node_id": "6",
            "target_input": "on_false",
        },
    )
    _report(monkeypatch, [manufactured])

    result = structural_check_graph(graph)
    normalized = normalize_to_api(graph, use_comfy_converter=False)
    workflow = from_api(normalized)

    assert result["passed"] is True
    assert result["warnings"][0]["detail"]["structural_reason"] == (
        "manufactured_widget_edge"
    )
    assert not any(edge.from_node == "1897" for edge in workflow.edges)
    assert workflow.nodes["6"].inputs["switch"] == ["1897", 1]


def test_saved_previously_reached_candidate_keeps_witness_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    case_dir = (
        root
        / "out"
        / "demo-candidate-factory"
        / "20260729-multinode-batch2"
        / "cases"
        / "6efa4e39d7e2"
    )
    response_path = case_dir / "attempts" / "001" / "response.json"
    if not response_path.is_file():
        pytest.skip("saved deterministic candidate artifact is not present")

    golden = json.loads(
        (case_dir / "source" / "golden.ui.json").read_text(encoding="utf-8")
    )
    broken = json.loads(
        (case_dir / "broken" / "broken.ui.json").read_text(encoding="utf-8")
    )
    candidate = json.loads(response_path.read_text(encoding="utf-8"))[
        "candidate_graph"
    ]
    spec = _multinode_spec("distilled_preview_branch")
    injection = _remove_subgraph_fault(
        golden,
        spec.slice_node_ids,
        spec.feature_key,
    )
    assert injection.broken == broken

    monkeypatch.setattr(
        additive_judge,
        "judge_additive_candidate",
        lambda *args, **kwargs: AdditiveJudgeResult(
            verdict=AdditiveWitnessVerdict.ACCEPTED,
            reason="frozen saved-candidate judge decision",
            source="test",
            profile="offline",
        ),
    )
    old_result = Oracle(
        injection.fault_predicate,
        injection.repaired_predicate,
        broken,
        golden,
    ).evaluate(
        candidate,
        execution_safe=True,
        output_reachable=True,
    )
    _report(monkeypatch, ok=True)
    replay_case = Case(
        case_id="saved-replay",
        case_dir=tmp_path,
        golden=golden,
        broken=broken,
        injection=injection,
        source="multinode",
    )

    new_result = _evaluate(replay_case, candidate).oracle_result

    assert new_result is not None
    assert old_result.verdict is Verdict.ACCEPTED
    assert new_result.verdict is old_result.verdict
    old_witness = {
        gate.name: (gate.passed, gate.reason, gate.detail)
        for gate in old_result.gates
        if gate.name in {"fault_removal", "repair_postcondition", "non_noop"}
    }
    new_witness = {
        gate.name: (gate.passed, gate.reason, gate.detail)
        for gate in new_result.gates
        if gate.name in {"fault_removal", "repair_postcondition", "non_noop"}
    }
    assert new_witness == old_witness
