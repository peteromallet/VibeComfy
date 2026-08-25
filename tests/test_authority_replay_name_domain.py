"""RR1-FIX(1) — live/replay widget-name domain coherence.

Regression pair encoded from the persisted finale receipts (f65774/d66a66/
8800a9 dive citations): a class whose input order leads with a custom-typed
socket (``MODEL_TASK_ID``) used to seal a phantom ``widget_0``-shifted frozen
roster on replay, mangling adjacent widgets and failing gate-green candidates
with ``candidate_hash_mismatch``. The fixed domain equals the live roster and
replay verifies the candidate byte-for-byte.
"""

from __future__ import annotations

import copy
import json

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    canonical_frozen_name_table,
    verify_replay,
)
from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider
from vibecomfy.schema.types import (
    FrozenSchemaSnapshotProvider,
    capture_schema_snapshot,
    schema_payload_from_node_schema,
)

OBJECT_INFO_ROOT = "vibecomfy/porting/cache/object_info"


def _tripo_fixture() -> dict:
    """Minimal faithful pair from the f65774 dive citation.

    Node 7 produces ``MODEL_TASK_ID``; node 26 (TripoTextureNode) consumes it
    through a LEADING custom-typed linked socket and carries the persisted
    widget row ``[true, true, 42, "standard", "original_image"]``.
    """
    return json.loads(
        r'''
{"nodes":[
  {"id":7,"type":"TripoTextToModelNode","mode":0,"pos":[0,0],"size":[270,174],"flags":{},"order":0,"properties":{"Node name for S&R":"TripoTextToModelNode"},
   "inputs":[{"name":"prompt","type":"STRING","widget":{"name":"prompt"}}],
   "outputs":[{"name":"model_file","type":"STRING","links":null,"slot_index":0},{"name":"model task_id","type":"MODEL_TASK_ID","links":[2],"slot_index":1}],
   "widgets_values":["a rustic wooden table", true, true, -1, "standard", "detailed", false, "quad"]},
  {"id":26,"type":"TripoTextureNode","mode":0,"pos":[300,0],"size":[270,174],"flags":{},"order":1,"properties":{"Node name for S&R":"TripoTextureNode"},
   "inputs":[{"name":"model_task_id","type":"MODEL_TASK_ID","link":2}],
   "outputs":[{"name":"model_file","type":"STRING","links":null,"slot_index":0},{"name":"model task_id","type":"MODEL_TASK_ID","links":null,"slot_index":1}],
   "widgets_values":[true,true,42,"standard","original_image"]}
 ],
 "links":[[2,7,1,26,"model_task_id","MODEL_TASK_ID"]]}
'''
    )


def _frozen_provider() -> tuple[FrozenSchemaSnapshotProvider, ObjectInfoIndexSchemaProvider]:
    prov = ObjectInfoIndexSchemaProvider(OBJECT_INFO_ROOT)
    cts = ["TripoTextureNode", "TripoTextToModelNode"]
    payloads = {ct: schema_payload_from_node_schema(ct, prov.get_schema(ct)) for ct in cts}
    snap = capture_schema_snapshot(
        class_types=sorted(cts),
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": payloads,
            "missing_classes": [],
        },
        node_classes={"7": "TripoTextToModelNode", "26": "TripoTextureNode"},
    )
    return FrozenSchemaSnapshotProvider(snap), prov


def test_frozen_roster_compacts_leading_custom_socket() -> None:
    """The sealed roster must equal the live literal-widget roster exactly.

    Fails on pre-fix code: the phantom ``widget_0`` shift truncated the tail
    (persisted receipt froze ``["widget_0","texture","pbr","texture_seed",
    "texture_quality"]``).
    """
    ui = _tripo_fixture()
    frozen, _prov = _frozen_provider()
    table = canonical_frozen_name_table(ui, schema_provider=frozen)
    assert table["26"] == (
        "texture",
        "pbr",
        "texture_seed",
        "texture_quality",
        "texture_alignment",
    )


def test_persisted_receipt_regression_candidate_matches() -> None:
    """Replaying the accepted delta must verify the live-produced candidate.

    Fails on pre-fix code with ``candidate_hash_mismatch`` (the exact verdict
    persisted on the f65774 receipt).
    """
    ui = _tripo_fixture()
    frozen, _prov = _frozen_provider()
    table = canonical_frozen_name_table(ui, schema_provider=frozen)
    candidate = copy.deepcopy(ui)
    candidate["nodes"][1]["widgets_values"] = [True, True, 42, "detailed", "original_image"]
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "26", "texture_quality"],
                "value": "detailed",
            }
        ],
    }
    receipt = verify_replay(
        ui,
        envelope,
        candidate,
        schema_provider=frozen,
        name_authority={k: v for k, v in table.items()},
    )
    assert receipt.replay_ok is True
    assert receipt.candidate_matches is True, receipt.error
    assert receipt.error is None


def test_resolver_compacts_linked_holes_without_explicit_order() -> None:
    """Hole compaction repairs full-input-order alias rosters directly.

    With no explicit widget-slot order available, ``metadata.input_aliases``
    interleaves the linked socket; dropping it must COMPACT positions instead
    of leaving a null hole that truncates the tail during alignment.
    """
    node = {
        "class_type": "TripoTextureNode",
        "widgets_values": [True, True, 42, "standard", "original_image"],
        "inputs": [{"name": "model_task_id", "type": "MODEL_TASK_ID", "link": 2}],
        "metadata": {
            "input_aliases": [
                "model_task_id",
                "texture",
                "pbr",
                "texture_seed",
                "texture_quality",
                "texture_alignment",
            ]
        },
    }
    resolution = compact_widget_names_for_node(node, linked_inputs={"model_task_id"})
    assert resolution.names == (
        "texture",
        "pbr",
        "texture_seed",
        "texture_quality",
        "texture_alignment",
    )
    assert resolution.complete is True


def test_explicit_widget_order_round_trips_snapshot_serialization() -> None:
    """Runtime-captured widget-slot order survives payload serialization."""
    prov = ObjectInfoIndexSchemaProvider(OBJECT_INFO_ROOT)
    schema = prov.get_schema("TripoTextureNode")
    assert schema.widget_input_order == (
        "texture",
        "pbr",
        "texture_seed",
        "texture_quality",
        "texture_alignment",
    )
    payload = schema_payload_from_node_schema("TripoTextureNode", schema)
    assert payload["widget_input_order"] == [
        "texture",
        "pbr",
        "texture_seed",
        "texture_quality",
        "texture_alignment",
    ]


def test_ambiguous_unlinked_socket_domain_stays_fail_closed() -> None:
    """An unlinked custom socket cannot be distinguished from a widget.

    The roster then keeps the socket name, the sealed domain diverges from the
    true layout, and authority must refuse the candidate instead of guessing.
    """
    ui = _tripo_fixture()
    ui["nodes"][0]["outputs"][1]["links"] = None
    ui["nodes"][1]["inputs"][0].pop("link")
    ui["links"] = []
    frozen, _prov = _frozen_provider()
    table = canonical_frozen_name_table(ui, schema_provider=frozen)
    candidate = copy.deepcopy(ui)
    candidate["nodes"][1]["widgets_values"] = [True, True, 42, "detailed", "original_image"]
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "26", "texture_quality"],
                "value": "detailed",
            }
        ],
    }
    receipt = verify_replay(
        ui,
        envelope,
        candidate,
        schema_provider=frozen,
        name_authority={k: v for k, v in table.items()} or None,
    )
    assert receipt.candidate_matches is False


def test_zero_net_change_accepted_delta_is_phantom_landing() -> None:
    """A declared landing whose emitted bytes are identical to submit is rejected.

    8800a9: Gate A certified "1 edit verified" while the candidate equaled the
    submit graph byte-for-byte. Authority now refuses with a typed reason
    instead of minting a phantom landing.
    """
    ui = _tripo_fixture()
    frozen, _prov = _frozen_provider()
    table = canonical_frozen_name_table(ui, schema_provider=frozen)
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "26", "texture_quality"],
                "value": "detailed",
            },
            {
                "op": "set_node_field",
                "target": ["", "26", "texture_quality"],
                "value": "standard",
            },
        ],
    }
    receipt = verify_replay(
        ui,
        envelope,
        ui,
        schema_provider=frozen,
        name_authority={k: v for k, v in table.items()},
    )
    assert receipt.replay_ok is False
    assert receipt.candidate_matches is False
    assert receipt.error == "phantom_landing_no_byte_change"
    assert receipt.op_count == 2
