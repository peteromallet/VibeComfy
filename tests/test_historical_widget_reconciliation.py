"""D10/C11: historical compact-widget admission tests.

These tests exercise the narrow bridge between captured source evidence and the
existing target resolver.  The bridge is deliberately non-mutating: applying a
mapping belongs to the later bundle transaction task.
"""

from __future__ import annotations

import copy

import pytest

from vibecomfy.ingest.snapshot import (
    capture_workflow_snapshot,
    historical_widget_evidence_by_uid,
    historical_widget_evidence_for_uid,
)
from vibecomfy.porting.widgets.historical import (
    HistoricalWidgetEvidence,
    HistoricalWidgetMappingRefused,
    admit_historical_widget_mappings,
)
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import RawWidgetPayload, VibeNode, VibeWorkflow, WorkflowSource


class _Provider:
    def __init__(self, schema: NodeSchema) -> None:
        self.schema = schema

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schema if class_type == self.schema.class_type else None


def _target_provider(
    class_type: str,
    order: tuple[str | None, ...],
    *,
    digest: str = "target-schema-digest",
) -> _Provider:
    inputs = {
        name: InputSpec(type="FLOAT")
        for name in order
        if isinstance(name, str) and name not in {"control_after_generate"}
    }
    schema = NodeSchema(
        class_type=class_type,
        pack="test-pack",
        inputs=inputs,
        outputs=[OutputSpec(type="ANY", name="output")],
        widget_input_order=order,
        source_provider="target_object_info",
        source_hash=digest,
        source_version="target-v2",
    )
    return _Provider(schema)


def _evidence(
    order: tuple[str | None, ...],
    values: tuple[object, ...],
    *,
    node_id: str = "h3-controller",
    class_type: str = "MiniMaxH3ReferenceToVideo",
    revision: str = "h3-source-revision",
    schema_digest: str | None = "historical-schema-digest",
    schema_version: str | None = "comfy-v0.35",
    span: str = "workflow.py:118",
    source: str = "pinned-h3-roster",
) -> HistoricalWidgetEvidence:
    return HistoricalWidgetEvidence(
        source_node_id=node_id,
        class_type=class_type,
        source_widget_order=order,
        source_widget_values=values,
        source_revision=revision,
        source_schema_digest=schema_digest,
        source_schema_version=schema_version,
        source_span=span,
        evidence_source=source,
    )


def test_pinned_h3_roster_maps_all_controller_slots_across_target_reorder() -> None:
    source_order = (
        "context_length",
        "audio_feather_ticks",
        "num_frames",
        "strength",
        "seed",
    )
    target_order = (
        "seed",
        "strength",
        "audio_feather_ticks",
        "context_length",
        "num_frames",
    )
    source = _evidence(source_order, (81, 6, 97, 0.72, 42))
    target_provider = _target_provider(source.class_type, target_order)
    target_node = {
        "class_type": source.class_type,
        "widgets_values": [42, 0.72, 6, 81, 97],
    }
    before = copy.deepcopy(target_node)

    result = admit_historical_widget_mappings(
        source,
        target_node=target_node,
        target_schema_provider=target_provider,
        target_schema_generation=7,
    )

    assert target_node == before
    assert result.status == "accepted"
    assert [mapping.source_field for mapping in result.mappings] == list(source_order)
    assert [mapping.target_widget_index for mapping in result.mappings] == [3, 2, 4, 1, 0]
    assert [mapping.source_value for mapping in result.mappings] == [81, 6, 97, 0.72, 42]
    assert result.target_schema_digest == "target-schema-digest"
    assert result.target_schema_generation == "7"
    assert result.mappings[0].target_widget_order == target_order
    assert result.mappings[0].resolver_source == "input_aliases"


def test_linked_context_and_audio_controls_are_holes_not_shifted_widgets() -> None:
    class_type = "H3WithLinkedControls"
    order = ("context_length", "audio_feather_ticks", "strength")
    provider = _target_provider(class_type, order)
    target_node = {
        "class_type": class_type,
        "widgets_values": [None, None, 0.8],
        "inputs": [
            {"name": "context_length", "link": 11},
            {"name": "audio_feather_ticks", "link": 12},
        ],
    }
    source = _evidence(
        (None, None, "strength"),
        (None, None, 0.8),
        class_type=class_type,
    )

    result = admit_historical_widget_mappings(
        source,
        target_node=target_node,
        target_schema_provider=provider,
        target_schema_generation=8,
    )

    assert [(item.source_widget_index, item.source_field, item.target_widget_index) for item in result.mappings] == [
        (2, "strength", 2)
    ]
    assert [(item.source_widget_index, item.reason) for item in result.preserved_slots] == [
        (0, "source hole/UI-only slot"),
        (1, "source hole/UI-only slot"),
    ]
    assert result.status == "accepted_partial"


def test_ui_only_control_is_resolved_by_the_existing_compact_target_resolver() -> None:
    order = ("seed", "control_after_generate", "steps")
    source = _evidence(order, (42, "fixed", 20), class_type="KSampler")
    provider = _target_provider("KSampler", order)
    result = admit_historical_widget_mappings(
        source,
        target_node={"class_type": "KSampler", "widgets_values": [42, "fixed", 20]},
        target_schema_provider=provider,
        target_schema_generation=9,
    )

    assert [(item.source_field, item.target_widget_index, item.source_value) for item in result.mappings] == [
        ("seed", 0, 42),
        ("control_after_generate", 1, "fixed"),
        ("steps", 2, 20),
    ]


def test_partial_vector_maps_observed_prefix_and_preserves_unobserved_slots() -> None:
    order = ("width", "height", "length", "fps")
    source = _evidence(order, (512, 512), class_type="PartialVectorNode")
    result = admit_historical_widget_mappings(
        source,
        target_widget_order=order,
        target_schema_digest="target-partial-digest",
        target_schema_generation="generation-10",
    )

    assert [(item.source_field, item.source_value) for item in result.mappings] == [
        ("width", 512),
        ("height", 512),
    ]
    assert [item.source_widget_index for item in result.preserved_slots] == [2, 3]
    assert result.status == "accepted_partial"


def test_conflicting_source_rosters_refuse_with_actionable_source_location() -> None:
    first = _evidence(("strength",), (0.5,), class_type="AmbiguousNode", source="roster-a")
    second = _evidence(("seed",), (0.5,), class_type="AmbiguousNode", source="roster-b")

    with pytest.raises(HistoricalWidgetMappingRefused) as caught:
        admit_historical_widget_mappings(
            [first, second],
            target_widget_order=("strength", "seed"),
            target_schema_digest="target-digest",
            target_schema_generation=11,
        )

    error = caught.value
    assert error.code == "conflicting_historical_evidence"
    assert "AmbiguousNode node h3-controller" in str(error)
    assert "workflow.py:118" in str(error)
    assert "widget_0=0.5" in str(error)
    assert "roster-a says 'strength'" in str(error)
    assert "provide a pinned historical widget roster" in str(error)


def test_missing_historical_identity_and_synthetic_widget_name_never_use_current_schema() -> None:
    source = _evidence(
        ("widget_0",),
        (0.5,),
        class_type="CurrentSchemaWouldSayStrength",
        schema_digest=None,
        schema_version=None,
    )

    with pytest.raises(HistoricalWidgetMappingRefused) as caught:
        admit_historical_widget_mappings(
            source,
            target_widget_order=("strength",),
            target_schema_digest="target-digest",
            target_schema_generation=12,
        )

    error = caught.value
    assert error.code == "missing_historical_source_identity"
    assert "CurrentSchemaWouldSayStrength" in str(error)
    assert "widget_0=0.5" in str(error)
    assert "do not infer the mapping from the current schema or widget_n" in str(error).lower()


def test_snapshot_adapter_preserves_source_revision_schema_identity_and_values() -> None:
    workflow = VibeWorkflow(
        "historical",
        WorkflowSource(
            id="historical",
            path="workflow.py",
            source_type="python",
            provenance={"source_revision": "python-revision-1"},
        ),
    )
    workflow.nodes["1"] = VibeNode(
        "1",
        "HistoricalNode",
        uid="node-1",
        widgets={"widget_0": 0.75},
        metadata={
            "input_aliases": ["strength"],
            "schema_source": {"hash": "source-schema-1", "version": "old-v1"},
            "source_span": "workflow.py:44",
        },
        raw_widgets=RawWidgetPayload(
            values=[0.75], shape="list", source="ui", has_dict_rows=False, length=1
        ),
    )
    workflow.metadata["_workflow_snapshot"] = capture_workflow_snapshot(
        {}, workflow, source_representation="python"
    )

    evidence = historical_widget_evidence_for_uid(workflow, "node-1")
    all_evidence = historical_widget_evidence_by_uid(workflow)

    assert evidence is not None
    assert evidence.source_widget_order == ("strength",)
    assert evidence.source_widget_values == (0.75,)
    assert evidence.source_revision == "python-revision-1"
    assert evidence.source_schema_digest == "source-schema-1"
    assert evidence.source_schema_version == "old-v1"
    assert evidence.source_span == "workflow.py:44"
    assert all_evidence["node-1"] == evidence
