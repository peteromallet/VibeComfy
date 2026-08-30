from __future__ import annotations

import sys
import types

import pytest

from vibecomfy.porting.emit import emit_ready_template_python, emit_scratchpad_python
from vibecomfy.workflow import (
    NodeMode,
    VibeEdge,
    VibeNode,
    VibeWorkflow,
    WorkflowCompileError,
    WorkflowSource,
)


def _chain(mode: object) -> VibeWorkflow:
    workflow = VibeWorkflow("b11b", WorkflowSource("b11b"))
    workflow.nodes["1"] = VibeNode("1", "Source")
    workflow.nodes["2"] = VibeNode("2", "Middle", mode=mode)  # type: ignore[arg-type]
    workflow.nodes["3"] = VibeNode("3", "SaveImage")
    workflow.edges.extend(
        [
            VibeEdge("1", "0", "2", "in"),
            VibeEdge("2", "0", "3", "images"),
        ]
    )
    return workflow


def _install_fake_graphbuilder(monkeypatch: pytest.MonkeyPatch) -> None:
    graph_utils = types.ModuleType("comfy_execution.graph_utils")

    class FakeGraphBuilder:
        def __init__(self, prefix: str = "") -> None:
            self.nodes: dict[str, dict[str, object]] = {}

        def node(self, class_type: str, id: str, **inputs: object) -> None:
            self.nodes[str(id)] = {"class_type": class_type, "inputs": inputs}

        def finalize(self) -> dict[str, dict[str, object]]:
            return self.nodes

    graph_utils.GraphBuilder = FakeGraphBuilder
    monkeypatch.setitem(sys.modules, "comfy_execution", types.ModuleType("comfy_execution"))
    monkeypatch.setitem(sys.modules, "comfy_execution.graph_utils", graph_utils)


@pytest.mark.parametrize(
    ("label", "mode", "expected_nodes", "expected_sink"),
    [
        ("live", NodeMode.ENABLED, {"1", "2", "3"}, ["2", 0]),
        ("muted", NodeMode.MUTED, {"1", "3"}, None),
        ("bypass", NodeMode.BYPASSED, {"1", "3"}, ["1", 0]),
        ("never", "never", {"1", "3"}, None),
    ],
)
def test_api_and_graphbuilder_share_execution_projection(
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    mode: object,
    expected_nodes: set[str],
    expected_sink: list[object] | None,
) -> None:
    del label
    _install_fake_graphbuilder(monkeypatch)
    workflow = _chain(mode)

    api = workflow.compile("api")
    graph = workflow.compile("graphbuilder")

    assert set(api) == expected_nodes
    assert set(graph) == expected_nodes
    assert graph == api
    assert api["3"]["inputs"].get("images") == expected_sink


def test_projection_resolves_multi_hop_bypass_reroutes() -> None:
    workflow = VibeWorkflow("reroute", WorkflowSource("reroute"))
    workflow.nodes["1"] = VibeNode("1", "Source")
    workflow.nodes["2"] = VibeNode("2", "Middle", mode=NodeMode.BYPASSED)
    workflow.nodes["3"] = VibeNode("3", "Middle", mode=NodeMode.BYPASSED)
    workflow.nodes["4"] = VibeNode("4", "SaveImage")
    workflow.edges.extend(
        [
            VibeEdge("1", "0", "2", "in"),
            VibeEdge("2", "0", "3", "in"),
            VibeEdge("3", "0", "4", "images"),
        ]
    )

    assert workflow.compile("api")["4"]["inputs"]["images"] == ["1", 0]


def test_target_cardinality_fails_execution_but_preserves_duplicate_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_graphbuilder(monkeypatch)
    workflow = VibeWorkflow("cardinality", WorkflowSource("cardinality"))
    workflow.nodes["1"] = VibeNode("1", "Source")
    workflow.nodes["2"] = VibeNode("2", "Source")
    workflow.nodes["3"] = VibeNode("3", "SaveImage")
    workflow.edges.extend(
        [
            VibeEdge("1", "0", "3", "images"),
            VibeEdge("2", "0", "3", "images"),
        ]
    )

    for backend in ("api", "graphbuilder"):
        with pytest.raises(WorkflowCompileError, match="target_input_cardinality"):
            workflow.compile(backend)

    report = workflow.validate(schema_provider=None)
    assert not report.ok
    assert any(
        issue.code == "api_compile_failed"
        and issue.detail["compile_code"] == "target_input_cardinality"
        for issue in report.issues
    )
    envelope = workflow.to_envelope()
    assert len(envelope["edges"]) == 2


def test_custom_json_socket_values_are_not_reinterpreted() -> None:
    workflow = VibeWorkflow("opaque", WorkflowSource("opaque"))
    payload = {"socket": "custom", "rows": [{"value": 1}, {"value": [2, 3]}]}
    workflow.nodes["1"] = VibeNode("1", "OpaqueNode", inputs={"payload": payload})

    assert workflow.compile("api")["1"]["inputs"]["payload"] == payload


@pytest.mark.parametrize("emitter", [emit_scratchpad_python, emit_ready_template_python])
def test_emitted_python_preserves_mode_and_execution_projection(emitter) -> None:
    workflow = _chain(NodeMode.BYPASSED)
    kwargs = {}
    if emitter is emit_scratchpad_python:
        kwargs.update(prune_dead_branches=False)
    else:
        kwargs.update(
            ready_metadata={"ready_template": "test/b11b"},
            ready_requirements={"models": [], "custom_nodes": []},
            template_id="test/b11b",
        )

    source = emitter(workflow, **kwargs)
    assert "_mode=4" in source
    namespace: dict[str, object] = {"__file__": "b11b_emitted.py"}
    exec(compile(source, "b11b emitted", "exec"), namespace)  # noqa: S102
    rebuilt = namespace["build"]()

    assert rebuilt.nodes["2"].mode is NodeMode.BYPASSED
    assert rebuilt.compile("api") == workflow.compile("api")
