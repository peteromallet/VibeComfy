from __future__ import annotations

import copy
import sys
import types
from typing import Any

import pytest

from vibecomfy.workflow import (
    VibeNode,
    VibeWorkflow,
    WorkflowCompileError,
    WorkflowSource,
    _resolve_workflow_virtual_wire_records,
)
from vibecomfy.workflow_bundle import WorkflowBundleError, materialize_ui_json


def _install_fake_graphbuilder(monkeypatch: pytest.MonkeyPatch) -> None:
    graph_utils = types.ModuleType("comfy_execution.graph_utils")

    class FakeGraphBuilder:
        def __init__(self, prefix: str = "") -> None:
            del prefix
            self.nodes: dict[str, dict[str, object]] = {}

        def node(self, class_type: str, id: str, **inputs: object) -> None:
            self.nodes[str(id)] = {"class_type": class_type, "inputs": inputs}

        def finalize(self) -> dict[str, dict[str, object]]:
            return self.nodes

    graph_utils.GraphBuilder = FakeGraphBuilder
    monkeypatch.setitem(sys.modules, "comfy_execution", types.ModuleType("comfy_execution"))
    monkeypatch.setitem(sys.modules, "comfy_execution.graph_utils", graph_utils)


def _workflow(*, source_roster: Any = None, target_roster: Any = None) -> VibeWorkflow:
    workflow = VibeWorkflow("canonical-wire", WorkflowSource("canonical-wire"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "Source",
        uid="source",
        native_output_names=["preview", "mask"] if source_roster is None else source_roster,
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "Target",
        uid="target",
        inputs={"ignored": None, "image": None},
        native_input_names=["ignored", "image"] if target_roster is None else target_roster,
    )
    return workflow


def _canonical_leg(*, scope_path: str = "") -> dict[str, object]:
    return {
        "scope_path": scope_path,
        "leg_index": 0,
        "occurrence_index": 0,
        "from_node": "source",
        "from_output": "mask",
        "to_node": "target",
        "to_input": "image",
    }


def test_canonical_virtual_wire_is_identical_for_resolver_execution_and_ui(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_graphbuilder(monkeypatch)
    workflow = _workflow()
    workflow.virtual_wires = {"bus": {"legs": [_canonical_leg()]}}
    authored_before = copy.deepcopy(workflow.to_envelope())

    records = _resolve_workflow_virtual_wire_records(workflow)
    [record] = records[("", "bus")]
    assert (
        record.from_lookup,
        record.from_output,
        record.from_port,
        record.to_lookup,
        record.to_input,
        record.to_port,
    ) == ("1", "mask", 1, "2", "image", 1)

    api = workflow.compile("api")
    assert api["2"]["inputs"]["image"] == ["1", 1]
    assert workflow.compile("graphbuilder") == api

    ui = materialize_ui_json(workflow)
    assert any(link[2] == 1 and link[4] == 1 for link in ui["links"])
    assert workflow.to_envelope() == authored_before


@pytest.mark.parametrize(
    ("virtual_wires", "code"),
    [
        ({"bus": {"legs": [("source", 1, "target", 1)]}}, "virtual_wire_malformed"),
        ({"bus": {"legs": [["source", 1, "target", 1]]}}, "virtual_wire_malformed"),
        (
            {
                "bus": {
                    "legs": [{
                        "from_node": "source",
                        "from_output": "mask",
                        "to_node": "target",
                        "to_input": "image",
                    }]
                }
            },
            "virtual_wire_malformed",
        ),
        (
            {
                "bus": {
                    "legs": [{
                        "scope_path": "",
                        "leg_index": 0,
                        "occurrence_index": 0,
                        "from_uid": "source",
                        "from_port": "mask",
                        "to_uid": "target",
                        "to_port": "image",
                    }]
                }
            },
            "virtual_wire_malformed",
        ),
        ({"bus": {"legs": (_canonical_leg(),)}}, "virtual_wire_malformed"),
        ({"bus": {"channel": "bus", "endpoints": []}}, "legacy_virtual_wire"),
    ],
    ids=(
        "tuple-leg",
        "list-leg",
        "missing-scope-indexes",
        "legacy-aliases",
        "tuple-leg-container",
        "legacy-wire",
    ),
)
def test_resolver_and_execution_reject_every_noncanonical_leg_shape(
    virtual_wires: object,
    code: str,
) -> None:
    workflow = _workflow()
    workflow.virtual_wires = virtual_wires  # type: ignore[assignment]
    authored_before = copy.deepcopy(workflow.to_envelope())

    for operation in (
        lambda: _resolve_workflow_virtual_wire_records(workflow),
        lambda: workflow.compile("api"),
    ):
        with pytest.raises(WorkflowCompileError) as exc:
            operation()
        assert exc.value.code == code
    with pytest.raises(WorkflowBundleError, match=code):
        materialize_ui_json(workflow)
    assert workflow.to_envelope() == authored_before


@pytest.mark.parametrize(
    "missing", ["source", "source-index", "target", "authoritative-empty"]
)
def test_resolver_and_execution_reject_missing_or_invented_port_rosters(
    missing: str,
) -> None:
    workflow = _workflow()
    leg = _canonical_leg()
    if missing in {"source", "source-index"}:
        workflow.nodes["1"].native_output_names = None
        if missing == "source-index":
            # An explicit number still needs a roster proving that the slot
            # exists; it must not become the downstream string "1".
            leg["from_output"] = 1
    elif missing == "target":
        # The input mapping deliberately contains the requested field.  Its
        # insertion order is value storage, never socket ordinal authority.
        workflow.nodes["2"].native_input_names = None
    else:
        workflow.nodes["1"].native_output_names = []
        workflow.nodes["1"].metadata["output_names"] = ["preview", "mask"]
    workflow.virtual_wires = {"bus": {"legs": [leg]}}

    for operation in (
        lambda: _resolve_workflow_virtual_wire_records(workflow),
        lambda: workflow.compile("api"),
    ):
        with pytest.raises(WorkflowCompileError) as exc:
            operation()
        assert exc.value.code == "unknown_virtual_wire_port"
    with pytest.raises(WorkflowBundleError, match="unknown_virtual_wire_port"):
        materialize_ui_json(workflow)


def test_metadata_rosters_are_used_only_when_native_rosters_are_absent() -> None:
    workflow = _workflow(source_roster=None, target_roster=None)
    workflow.nodes["1"].native_output_names = None
    workflow.nodes["1"].metadata["output_names"] = ("preview", "mask")
    workflow.nodes["2"].native_input_names = None
    workflow.nodes["2"].metadata["input_names"] = ("ignored", "image")
    workflow.virtual_wires = {"bus": {"legs": [_canonical_leg()]}}

    [record] = _resolve_workflow_virtual_wire_records(workflow)[("", "bus")]
    assert (record.from_port, record.to_port) == (1, 1)
    assert workflow.compile()["2"]["inputs"]["image"] == ["1", 1]


def test_structural_scopes_keep_repeated_local_ids_isolated() -> None:
    workflow = VibeWorkflow("scoped-wire", WorkflowSource("scoped-wire"))
    for scope in ("left", "right"):
        workflow.nodes[f"{scope}#source"] = VibeNode(
            f"{scope}#source",
            "Source",
            uid="source",
            native_output_names=["out"],
        )
        workflow.nodes[f"{scope}#target"] = VibeNode(
            f"{scope}#target",
            "Target",
            uid="target",
            inputs={"value": None},
            native_input_names=["value"],
        )
    workflow.virtual_wires = {
        "bus": {
            "legs": [
                {
                    "scope_path": scope,
                    "leg_index": 0,
                    "occurrence_index": 0,
                    "from_node": "source",
                    "from_output": "out",
                    "to_node": "target",
                    "to_input": "value",
                }
                for scope in ("right", "left")
            ]
        }
    }

    records = _resolve_workflow_virtual_wire_records(workflow)
    assert set(records) == {("left", "bus"), ("right", "bus")}
    compiled = workflow.compile()
    assert compiled["left#target"]["inputs"]["value"] == ["left#source", 0]
    assert compiled["right#target"]["inputs"]["value"] == ["right#source", 0]


def test_scoped_leg_never_borrows_unqualified_root_nodes() -> None:
    workflow = _workflow()
    workflow.virtual_wires = {"bus": {"legs": [_canonical_leg(scope_path="nested")]}}

    for operation in (
        lambda: _resolve_workflow_virtual_wire_records(workflow),
        lambda: workflow.compile("api"),
    ):
        with pytest.raises(WorkflowCompileError) as exc:
            operation()
        assert exc.value.code == "virtual_wire_unresolved"
