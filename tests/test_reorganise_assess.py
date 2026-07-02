from __future__ import annotations

from copy import deepcopy

from vibecomfy.porting.reorganise.assess import (
    GROUP_COHERENCE_CONTAINMENT_WEIGHT,
    GROUP_COHERENCE_LABEL_WEIGHT,
    GROUP_COHERENCE_TOPOLOGY_WEIGHT,
    ISSUE_BACKWARD_EDGE_RATIO_HIGH,
    ISSUE_GROUP_COHERENCE_LOW,
    ISSUE_HELPER_DISTANCE_WARNING,
    ISSUE_OVERLAPPING_NODES,
    ISSUE_SPACING_DENSITY_HIGH,
    ISSUE_WEAK_GROUP_SIGNAL,
    METRIC_BACKWARD_EDGE_RATIO,
    METRIC_GROUP_COHERENCE,
    METRIC_GROUP_SIGNAL_STRENGTH,
    METRIC_HELPER_DISTANCE_WARNING_COUNT,
    METRIC_OVERLAP_COUNT,
    METRIC_SPACING_DENSITY,
    assess_layout_facts,
    assess_layout_from_ui,
)
from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts
from vibecomfy.porting.reorganise.report import diagnostic_report_from_assessment


def _quality_signal_ui() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "pos": [100, 100],
                "size": [300, 100],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "pos": [50, 110],
                "size": [300, 100],
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "pos": [80, 120],
                "size": [300, 100],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 11}],
            },
            {
                "id": 4,
                "type": "Reroute",
                "class_type": "Reroute",
                "properties": {"vibecomfy_uid": "reroute"},
                "pos": [900, 900],
                "size": [40, 40],
                "inputs": [{"name": "", "type": "*", "link": 12}],
                "outputs": [{"name": "", "type": "*", "links": [13]}],
            },
            {
                "id": 5,
                "type": "PreviewImage",
                "class_type": "PreviewImage",
                "properties": {"vibecomfy_uid": "preview"},
                "pos": [170, 130],
                "size": [300, 100],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 13}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
            [12, 1, 0, 4, 0, "IMAGE"],
            [13, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [
            {
                "title": "Too small",
                "bounding": [0, 0, 200, 140],
                "nodes": [1, 2],
            }
        ],
    }


def test_assessment_returns_ordered_metrics_issues_and_diagnostics() -> None:
    report = assess_layout_from_ui(_quality_signal_ui())

    assert report.verdict == "needs_reorganise"
    assert [metric.name for metric in report.metrics] == [
        METRIC_OVERLAP_COUNT,
        METRIC_BACKWARD_EDGE_RATIO,
        METRIC_SPACING_DENSITY,
        METRIC_GROUP_SIGNAL_STRENGTH,
        METRIC_GROUP_COHERENCE,
        METRIC_HELPER_DISTANCE_WARNING_COUNT,
    ]
    metrics = {metric.name: metric.value for metric in report.metrics}
    assert metrics[METRIC_OVERLAP_COUNT] == 6
    assert metrics[METRIC_BACKWARD_EDGE_RATIO] == 0.3333
    assert metrics[METRIC_SPACING_DENSITY] > 1.0
    assert metrics[METRIC_GROUP_SIGNAL_STRENGTH] == 0.5
    assert metrics[METRIC_GROUP_COHERENCE] < 0.65
    assert metrics[METRIC_HELPER_DISTANCE_WARNING_COUNT] == 1

    assert [issue.code for issue in report.issues] == [
        ISSUE_OVERLAPPING_NODES,
        ISSUE_BACKWARD_EDGE_RATIO_HIGH,
        ISSUE_SPACING_DENSITY_HIGH,
        ISSUE_GROUP_COHERENCE_LOW,
        ISSUE_HELPER_DISTANCE_WARNING,
    ]
    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        ISSUE_BACKWARD_EDGE_RATIO_HIGH,
        ISSUE_GROUP_COHERENCE_LOW,
        ISSUE_HELPER_DISTANCE_WARNING,
        ISSUE_OVERLAPPING_NODES,
        ISSUE_SPACING_DENSITY_HIGH,
    ]
    diagnostic_report = diagnostic_report_from_assessment(report)
    assert diagnostic_report.ok is False
    assert [diagnostic.code for diagnostic in diagnostic_report.diagnostics] == [
        diagnostic.code for diagnostic in report.diagnostics
    ]


def test_assessment_reports_missing_or_weak_group_signal_for_larger_ungrouped_graph() -> None:
    ui = {
        "nodes": [
            {
                "id": index,
                "type": "PreviewImage",
                "class_type": "PreviewImage",
                "properties": {"vibecomfy_uid": f"preview-{index}"},
                "pos": [index * 500, 0],
                "size": [160, 80],
            }
            for index in range(1, 5)
        ],
        "links": [],
        "groups": [],
    }

    report = assess_layout_from_ui(ui)

    assert report.verdict == "needs_reorganise"
    assert [issue.code for issue in report.issues] == [ISSUE_WEAK_GROUP_SIGNAL]
    issue = report.issues[0]
    assert issue.detail["primary_node_count"] == 4
    assert issue.detail["coverage"] == 0.0


def test_assessment_group_coherence_uses_named_constant_weights() -> None:
    report = assess_layout_from_ui(_quality_signal_ui())
    issue = next(issue for issue in report.issues if issue.code == ISSUE_GROUP_COHERENCE_LOW)

    assert issue.detail["containment_weight"] == GROUP_COHERENCE_CONTAINMENT_WEIGHT
    assert issue.detail["topology_weight"] == GROUP_COHERENCE_TOPOLOGY_WEIGHT
    assert issue.detail["label_weight"] == GROUP_COHERENCE_LABEL_WEIGHT
    assert (
        GROUP_COHERENCE_CONTAINMENT_WEIGHT
        + GROUP_COHERENCE_TOPOLOGY_WEIGHT
        + GROUP_COHERENCE_LABEL_WEIGHT
    ) == 1.0


def test_assessment_is_read_only_for_ui_sidecar_widgets_links_topology_and_node_classes() -> None:
    ui = _quality_signal_ui()
    ui["nodes"][1]["widgets_values"] = ["kept-widget"]
    sidecar = {
        "store_version": 2,
        "schema_hash": "test",
        "entries": {
            "load": {"pos": [100, 100], "size": [300, 100]},
            "sample": {"pos": [50, 110], "size": [300, 100]},
        },
        "virtual_wires": {
            "wire-image": {
                "type": "SetNode",
                "channel": "IMAGE",
                "endpoints": ["load", "sample"],
            }
        },
        "lastRerouteId": 9,
    }
    ui_before = deepcopy(ui)
    sidecar_before = deepcopy(sidecar)

    assess_layout_from_ui(ui, sidecar_envelope=sidecar)

    assert ui == ui_before
    assert sidecar == sidecar_before
    assert [node["class_type"] for node in ui["nodes"]] == [
        node["class_type"] for node in ui_before["nodes"]
    ]
    assert [node.get("widgets_values") for node in ui["nodes"]] == [
        node.get("widgets_values") for node in ui_before["nodes"]
    ]
    assert ui["links"] == ui_before["links"]

    facts = extract_graph_facts(ui, sidecar_envelope=sidecar)
    facts_before = deepcopy(facts.to_json())
    assess_layout_facts(facts)

    assert facts.to_json() == facts_before
