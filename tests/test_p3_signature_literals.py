"""P3-SIGNATURE-LITERALS focused tests.

Discovery signatures must keep snapshot-backed literals:

R1  the frozen schema_provider reaches editable-surface resolution through
    ``filter_signature_rows_to_in_graph_nodes`` — provider-only naming
    evidence keeps a field discoverable;
R2  a literal sealed onto an in-graph node by the frozen
    ``WorkflowSnapshot.field_snapshot`` roster is NEVER dropped, even when
    the live provider disagrees (stale-live must not erase a real field);
R3  no signature row is invented for fields absent from both the snapshot
    and the provider.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from vibecomfy.porting.emitter import (
    InputSignatureField,
    NodeSignatureRow,
    emit_available_node_signatures,
    filter_signature_rows_to_in_graph_nodes,
)
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import (
    RawWidgetPayload,
    VibeNode,
    VibeWorkflow,
    WorkflowSource,
)


class _ExplicitSchemaProvider:
    """Minimal schema provider backed by an explicit class→NodeSchema dict."""

    def __init__(self, schemas: dict[str, Any]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> Any | None:
        return self._schemas.get(class_type)


def _provider(
    class_type: str = "VoxelToMeshBasic",
    field: str = "threshold",
) -> _ExplicitSchemaProvider:
    return _ExplicitSchemaProvider(
        {
            class_type: NodeSchema(
                class_type=class_type,
                pack="core",
                inputs={field: InputSpec(type="FLOAT", required=True, default=0.6)},
                outputs=[OutputSpec(type="MESH", name="mesh")],
                confidence=1.0,
            ),
        }
    )


def _stale_live_provider() -> _ExplicitSchemaProvider:
    """A live provider whose roster drifted: slot 0 is ``alpha``, not ``threshold``."""
    return _provider(field="alpha")


def _single_node_workflow(
    class_type: str = "VoxelToMeshBasic",
    *,
    sealed_names: tuple[str, ...] | None,
) -> VibeWorkflow:
    """A one-node workflow whose only widget carrier is positional (``widget_0``)."""
    wf = VibeWorkflow("t", WorkflowSource(id="t", source_type="test"))
    wf.nodes["1"] = VibeNode(
        "1",
        class_type=class_type,
        uid="1",
        widgets={"widget_0": 0.6},
        raw_widgets=RawWidgetPayload(
            values=[0.6], shape="list", source="ui", has_dict_rows=False, length=1
        ),
    )
    if sealed_names is not None:
        from vibecomfy.ingest.snapshot import (
            SEMANTIC_HASH_VERSION,
            WORKFLOW_SNAPSHOT_METADATA_KEY,
            LayoutReference,
            WorkflowSnapshot,
        )

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
                    "class_type": class_type,
                    "widget_values_sig": (),
                    "incoming_edge_sig": (),
                    "outgoing_edge_sig": (),
                    "public_input_binding": (),
                    "widget_names_sig": sealed_names,
                }
            },
        )
    return wf


def _plain_ui_graph(class_type: str) -> dict[str, Any]:
    """A UI-dict graph node carrying only an anonymous ``widgets_values`` list."""
    return {
        "nodes": [
            {
                "id": 7,
                "type": class_type,
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
        ]
    }


def _voxel_rows() -> list[NodeSignatureRow]:
    rows = emit_available_node_signatures(_provider(), focus_types=["VoxelToMeshBasic"])
    assert len(rows) == 1
    assert "threshold" in {field.name for field in rows[0].inputs}
    return rows


def _input_names(rows: list[NodeSignatureRow]) -> set[str]:
    assert len(rows) == 1
    return {field.name for field in rows[0].inputs}


# ---------------------------------------------------------------------------
# (a) widget_N carrier + frozen snapshot naming ``threshold`` → row kept
# ---------------------------------------------------------------------------


def test_sealed_positional_carrier_keeps_snapshot_backed_literal() -> None:
    rows = _voxel_rows()

    kept = filter_signature_rows_to_in_graph_nodes(
        rows,
        _single_node_workflow(sealed_names=("threshold",)),
        schema_provider=_provider(),
    )
    assert "threshold" in _input_names(kept)


# ---------------------------------------------------------------------------
# (b) live provider missing the field while snapshot has it → still kept
# ---------------------------------------------------------------------------


def test_frozen_roster_beats_stale_live_provider() -> None:
    """R2: a field the snapshot seals stays advertised even when the live
    provider cannot resolve it; without the seal, stale-live erasure is
    exactly the leg-8 failure mode (class unknown to ambient sources)."""
    class_type = "MysteryMeshNode"  # absent from curated/semantic/object_info

    def rows_with_knob() -> list[NodeSignatureRow]:
        return [
            NodeSignatureRow(
                class_type=class_type,
                inputs=(InputSignatureField(name="knob", type="FLOAT", required=True),),
                outputs=(),
            )
        ]

    live = _provider(class_type, field="unrelated")  # roster misses ``knob``

    # Control: no seal, live provider missing the field → erased.
    erased = filter_signature_rows_to_in_graph_nodes(
        rows_with_knob(),
        _single_node_workflow(class_type, sealed_names=None),
        schema_provider=live,
    )
    assert _input_names(erased) == set()

    # Snapshot wins: the sealed roster keeps ``knob`` advertised.
    kept = filter_signature_rows_to_in_graph_nodes(
        rows_with_knob(),
        _single_node_workflow(class_type, sealed_names=("knob",)),
        schema_provider=live,
    )
    assert _input_names(kept) == {"knob"}


# ---------------------------------------------------------------------------
# (c) field in neither snapshot nor provider → not advertised
# ---------------------------------------------------------------------------


def test_field_absent_from_snapshot_and_provider_is_not_advertised() -> None:
    rows = _voxel_rows()
    padded_rows = [
        replace(
            rows[0],
            inputs=tuple(rows[0].inputs)
            + (InputSignatureField(name="mystery_boost", type="FLOAT", required=True),),
        )
    ]
    filtered = filter_signature_rows_to_in_graph_nodes(
        padded_rows,
        _single_node_workflow(sealed_names=("threshold",)),
        schema_provider=_provider(),
    )
    assert _input_names(filtered) == {"threshold"}


# ---------------------------------------------------------------------------
# (d) R1: the provider alone reaches editable-surface resolution
# ---------------------------------------------------------------------------


def test_provider_reaches_surface_resolution_for_anonymous_carrier() -> None:
    """R1: with no seal and no ambient knowledge, the schema provider alone
    names the anonymous carrier through editable-surface resolution."""
    class_type = "MysteryMeshNode"  # unknown to curated/semantic/object_info sources
    rows = emit_available_node_signatures(
        _provider(class_type, field="knob"), focus_types=[class_type]
    )
    assert len(rows) == 1
    assert {field.name for field in rows[0].inputs} == {"knob"}

    graph = _plain_ui_graph(class_type)
    without_provider = filter_signature_rows_to_in_graph_nodes(rows, graph)
    assert _input_names(without_provider) == set()

    with_provider = filter_signature_rows_to_in_graph_nodes(
        rows, graph, schema_provider=_provider(class_type, field="knob")
    )
    assert _input_names(with_provider) == {"knob"}
