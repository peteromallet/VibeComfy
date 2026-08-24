"""P0-WIDGET-CANON focused tests.

R1  linked-socket exclusion — an input carried by a graph connection never
    qualifies as a compact-widget name source.
R2  positional-carrier rewrite — assigning a schema name onto a slot stored
    as ``widgets['widget_N']`` rewrites THAT carrier; no named key is
    dual-written beside it (one value, one carrier).
R3  frozen snapshot table — the per-uid name roster sealed onto
    ``WorkflowSnapshot.field_snapshot`` at ingest is the ONLY name authority
    consumed by interpret / apply / replay; ambient providers and object_info
    cannot move a sealed name.
"""

from __future__ import annotations

import copy
from typing import Any

from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit._ir_utils import apply_edit_cow
from vibecomfy.porting.edit.ops import parse_edit_delta
from vibecomfy.porting.widgets.compact_resolver import (
    compact_widget_names_for_node,
    widget_index_for_field,
)
from vibecomfy.workflow import RawWidgetPayload, VibeNode, VibeWorkflow, WorkflowSource


def _snapshot_api():
    """Imported lazily so pre-change baselines fail inside R3 tests only."""
    from vibecomfy.ingest.snapshot import (
        SEMANTIC_HASH_VERSION,
        WORKFLOW_SNAPSHOT_METADATA_KEY,
        LayoutReference,
        WorkflowSnapshot,
        frozen_widget_names_by_uid,
    )

    return (
        SEMANTIC_HASH_VERSION,
        WORKFLOW_SNAPSHOT_METADATA_KEY,
        LayoutReference,
        WorkflowSnapshot,
        frozen_widget_names_by_uid,
    )
# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _single_node_ui(node: dict[str, Any]) -> dict[str, Any]:
    node_id = node.get("id")
    assert isinstance(node_id, int)
    return {
        "last_node_id": node_id,
        "last_link_id": 0,
        "nodes": [copy.deepcopy(node)],
        "links": [],
    }


class _ExplicitSchemaProvider:
    """Minimal schema provider backed by an explicit class→NodeSchema dict."""

    def __init__(self, schemas: dict[str, Any]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> Any | None:
        return self._schemas.get(class_type)


def _drift_provider(slot0_name: str = "alpha") -> _ExplicitSchemaProvider:
    """A provider whose widget roster disagrees with any sealed evidence.

    The drift schema names compact slot 0 ``alpha``; every input is a literal
    widget so provider-based resolution would happily advertise it.
    """
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    return _ExplicitSchemaProvider(
        {
            "VoxelToMeshBasic": NodeSchema(
                class_type="VoxelToMeshBasic",
                pack="core",
                inputs={
                    slot0_name: InputSpec(type="FLOAT", required=True, default=0.6),
                },
                outputs=[OutputSpec(type="MESH", name="mesh")],
                confidence=1.0,
            ),
            "MysteryKnobs": NodeSchema(
                class_type="MysteryKnobs",
                pack="core",
                inputs={
                    "alpha": InputSpec(type="FLOAT", required=True, default=0.0),
                    "beta": InputSpec(type="INT", required=True, default=1),
                },
                outputs=[],
                confidence=1.0,
            ),
        }
    )


def _ksampler_node_with_positional_carrier(workflow_id: str = "t") -> VibeWorkflow:
    wf = VibeWorkflow(workflow_id, WorkflowSource(id=workflow_id, source_type="test"))
    wf.nodes["1"] = VibeNode(
        "1",
        class_type="KSampler",
        uid="1",
        widgets={"widget_0": 123},
        raw_widgets=RawWidgetPayload(
            values=[123, "fixed", 20, 7.0, "euler", "normal", 1.0],
            shape="list",
            source="ui",
            has_dict_rows=False,
            length=7,
        ),
    )
    return wf


# ---------------------------------------------------------------------------
# R1 — linked-socket exclusion
# ---------------------------------------------------------------------------


def test_linked_socket_never_qualifies_as_compact_widget_name() -> None:
    """metadata.input_aliases prefers socket+widget order, so a LINKED socket
    name must be filtered out of every candidate source (falls back to honest
    positional ``widget_N`` addressing); the same alias survives unlinked."""
    linked_node: dict[str, Any] = {
        "class_type": "VoxelToMeshBasic",
        "widgets_values": [0.6],
        "metadata": {
            "input_aliases": ["voxel"],
            "_ui": {
                "inputs": [
                    {"name": "voxel", "type": "VOXEL", "link": 7},
                ]
            },
        },
    }
    resolution = compact_widget_names_for_node(linked_node, "VoxelToMeshBasic")
    assert resolution.names == ("widget_0",)
    assert "voxel" not in resolution.names

    unlinked_node = copy.deepcopy(linked_node)
    unlinked_node["metadata"]["_ui"]["inputs"][0]["link"] = None
    resolution = compact_widget_names_for_node(unlinked_node, "VoxelToMeshBasic")
    assert resolution.names == ("voxel",)


def test_linked_ir_input_value_excluded_from_compact_names() -> None:
    """Retained-IR shape: an inputs entry holding a [source, slot] link pair
    is connected and must not advertise itself as a widget-name candidate."""
    node = VibeNode(
        "1",
        class_type="VoxelToMeshBasic",
        uid="1",
        inputs={"voxel": ["2", 0]},
        widgets={"widget_1": 0.6},
        raw_widgets=RawWidgetPayload(
            values=[0.5, 0.6], shape="list", source="ui", has_dict_rows=False, length=2
        ),
        metadata={"input_aliases": ["voxel"]},
    )
    resolution = compact_widget_names_for_node(node, node.class_type)
    assert "voxel" not in resolution.names

    scalar = copy.deepcopy(node)
    scalar.inputs["voxel"] = 0.5
    resolution = compact_widget_names_for_node(scalar, scalar.class_type)
    assert "voxel" in resolution.names


def test_explicit_linked_inputs_evidence_is_honored() -> None:
    """Callers holding edge truth can pass ``linked_inputs`` directly; the
    excluded name leaves the roster while alignment is preserved."""
    node: dict[str, Any] = {
        "class_type": "KSampler",
        "widgets_values": [123, "fixed", 20, 7.0, "euler", "normal", 1.0],
    }
    resolution = compact_widget_names_for_node(node, "KSampler")
    assert resolution.names[0] == "seed"

    wired = compact_widget_names_for_node(node, "KSampler", linked_inputs=("seed",))
    assert "seed" not in wired.names
    assert wired.names[0] == "widget_0"
    assert wired.names[2:] == ("steps", "cfg", "sampler_name", "scheduler", "denoise")


# ---------------------------------------------------------------------------
# R2 — positional-carrier rewrite (no dual-write)
# ---------------------------------------------------------------------------


def test_schema_name_assignment_rewrites_positional_carrier_without_dual_write() -> None:
    """``seed = 456`` against a node storing slot 0 as ``widgets['widget_0']``
    rewrites that positional carrier; no named key appears in either channel."""
    wf = _ksampler_node_with_positional_carrier()
    op = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "1", "seed"], "value": 456}]
    )[0]

    post = apply_edit_cow(wf, op)
    node = post.nodes["1"]

    assert node.widgets == {"widget_0": 456}
    assert "seed" not in node.widgets
    assert "seed" not in node.inputs
    # the parallel raw/UI mirrors of the SAME positional slot follow
    assert node.raw_widgets is not None and node.raw_widgets.values[0] == 456
    # one value, one carrier: pre-state untouched (COW)
    assert wf.nodes["1"].widgets == {"widget_0": 123}


def test_unresolved_named_assignment_still_lands_in_inputs_channel() -> None:
    """A name with no positional carrier keeps the unknown-channel fallback —
    R2 only redirects assignments whose slot IS stored positionally."""
    wf = _ksampler_node_with_positional_carrier()
    op = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "1", "extra_knob"], "value": 7}]
    )[0]

    post = apply_edit_cow(wf, op)
    node = post.nodes["1"]
    assert node.inputs.get("extra_knob") == 7
    assert node.widgets == {"widget_0": 123}


# ---------------------------------------------------------------------------
# R3 — sealed snapshot table is the sole name authority
# ---------------------------------------------------------------------------


_VOXEL_UI = {
    "id": 1,
    "type": "VoxelToMeshBasic",
    "pos": [0, 0],
    "size": [210, 58],
    "flags": {},
    "order": 0,
    "mode": 0,
    "inputs": [],
    "outputs": [],
    "properties": {},
    "widgets_values": [0.6],
}


def test_sealed_table_overrides_drifted_provider_in_canonicalization() -> None:
    """Replay canonicalizes ``widget_0`` to the SEALED name even when the live
    provider would resolve the slot differently (pre-change this landed the
    drifted spelling)."""
    ui = _single_node_ui(_VOXEL_UI)
    wf = from_ui(dict(ui), use_comfy_converter=False)
    frozen = _snapshot_api()[4](wf)
    assert frozen.get("1") == ("threshold",), "seal must capture the object-info roster"

    result = interpret(
        wf,
        "voxeltomeshbasic.widget_0 = 9",
        schema_provider=_drift_provider(),
    )
    assert result.ok is True, result.diagnostics
    landed = [op for op in result.landed_ops if op is not None]
    assert landed, "the assignment must land an edit op"
    field_paths = [op.target.field_path for op in landed]
    assert field_paths == ["threshold"], (
        "canonicalization must use the frozen table, not the drifted provider "
        f"(got {field_paths})"
    )


def test_frozen_authority_beats_mutated_ambient_metadata() -> None:
    """Once sealed, mutating the node's ambient alias metadata cannot move the
    name authority for that uid."""
    node = VibeNode(
        "1",
        class_type="VoxelToMeshBasic",
        uid="1",
        widgets={"widget_0": 0.6},
        raw_widgets=RawWidgetPayload(
            values=[0.6], shape="list", source="ui", has_dict_rows=False, length=1
        ),
        metadata={"input_aliases": ["tampered_after_seal"]},
    )
    authority = {"1": ("threshold",)}

    drifted = compact_widget_names_for_node(node, node.class_type)
    assert drifted.names == ("tampered_after_seal",)

    sealed = compact_widget_names_for_node(
        node, node.class_type, name_authority=authority, schema_provider=None
    )
    assert sealed.source == "field_snapshot"
    assert sealed.names == ("threshold",)


def test_apply_replay_consumes_frozen_table_for_positional_rewrite() -> None:
    """apply/replay resolves name→slot through the FROZEN table: a sealed
    roster makes the positional-carrier rewrite work even when no ambient
    source could resolve the name at all."""
    wf = VibeWorkflow("t", WorkflowSource(id="t", source_type="test"))
    wf.nodes["1"] = VibeNode(
        "1",
        class_type="MysteryKnobs",
        uid="1",
        widgets={"widget_0": 0.0, "widget_1": 1},
        raw_widgets=RawWidgetPayload(
            values=[0.0, 1], shape="list", source="ui", has_dict_rows=False, length=2
        ),
    )

    (
        SEMANTIC_HASH_VERSION,
        WORKFLOW_SNAPSHOT_METADATA_KEY,
        LayoutReference,
        WorkflowSnapshot,
        _,
    ) = _snapshot_api()

    wf.metadata[WORKFLOW_SNAPSHOT_METADATA_KEY] = WorkflowSnapshot(
        workflow=wf.copy(),
        source_representation="test",
        source_digest="",
        semantic_hash_version=SEMANTIC_HASH_VERSION,
        semantic_digest="",
        layout=LayoutReference(kind="test"),
        raw_sidecar={},
        identity=("1",),
        topology=(),
        field_snapshot={
            "1": {
                "class_type": "MysteryKnobs",
                "widget_values_sig": (),
                "incoming_edge_sig": (),
                "outgoing_edge_sig": (),
                "public_input_binding": (),
                "widget_names_sig": ("knob_a", "knob_b"),
            }
        },
    )

    # Ambient resolution alone cannot name either slot.
    bare = widget_index_for_field(wf.nodes["1"], "knob_a")
    assert bare is None

    op = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "1", "knob_a"], "value": 5}]
    )[0]
    post = apply_edit_cow(wf, op)
    node = post.nodes["1"]

    assert node.widgets == {"widget_0": 5, "widget_1": 1}
    assert "knob_a" not in node.widgets
    assert "knob_a" not in node.inputs


def test_snapshot_capture_excludes_linked_sockets_and_keeps_digest_stable() -> None:
    """Seal-time capture applies R1 against incoming-edge truth, and adding
    the name table does not change semantic-digest equality semantics."""
    from vibecomfy.ingest.snapshot import snapshot_of

    voxel = copy.deepcopy(_VOXEL_UI)
    sampler = {
        "id": 2,
        "type": "KSampler",
        "pos": [200, 0],
        "size": [210, 58],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [{"name": "voxel", "type": "VOXEL", "link": 1}],
        "outputs": [],
        "properties": {},
        "widgets_values": [123, "fixed", 20, 7.0, "euler", "normal", 1.0],
    }
    ui = {
        "last_node_id": 2,
        "last_link_id": 1,
        "nodes": [voxel, sampler],
        "links": [[1, 1, 0, 2, 0, "VOXEL"]],
    }

    from vibecomfy.ingest.snapshot import snapshot_of

    frozen = _snapshot_api()[4]
    wf = from_ui(dict(ui), use_comfy_converter=False)
    snap = snapshot_of(wf)
    assert snap is not None
    names = frozen(wf)

    # The KSampler's linked `voxel` input never enters its roster...
    sampler_roster = next(
        roster
        for uid, roster in names.items()
        if uid in {str(n.uid) for n in wf.nodes.values()
                   if n.class_type == "KSampler"}
    )
    assert "voxel" not in sampler_roster
    assert sampler_roster[0] == "seed"

    # ...and digest equality across identical ingests is unchanged.
    wf_again = from_ui(copy.deepcopy(ui), use_comfy_converter=False)
    assert snapshot_of(wf_again).semantic_digest == snap.semantic_digest
