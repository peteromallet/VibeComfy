from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.comfy_nodes.agent.authority_receipts import verify_replay
from vibecomfy.porting.edit.apply_core import apply_delta
from vibecomfy.porting.edit.ops import normalize_delta_ops
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec


FIXTURE = (
    Path(__file__).parent
    / "characterization"
    / "fixtures"
    / "agent_edit"
    / "case_01_widget_set"
    / "input_ui.json"
)


def _submit_graph() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_nonempty_canonical_v2_envelope_replays_all_operations() -> None:
    submit_graph = _submit_graph()
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "2", "text"],
                "value": "hello world",
            }
        ],
    }
    applied = apply_delta(submit_graph, normalize_delta_ops(envelope))
    assert applied.ok is True
    assert applied.candidate is not None

    receipt = verify_replay(submit_graph, envelope, applied.candidate)

    assert receipt.replay_ok is True
    assert receipt.candidate_matches is True
    assert receipt.op_count == 1
    assert receipt.error is None


def test_malformed_nonempty_v2_envelope_fails_closed() -> None:
    submit_graph = _submit_graph()
    malformed_envelope = {
        # Missing schema_version is a legacy/malformed shape, not an empty delta.
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "2", "text"],
                "value": "hello world",
            }
        ]
    }

    receipt = verify_replay(submit_graph, malformed_envelope, submit_graph)

    assert receipt.replay_ok is False
    assert receipt.candidate_matches is False
    assert receipt.op_count == 1
    assert receipt.error is not None
    assert receipt.error.startswith("invalid_delta_envelope:")


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def test_add_node_and_dependent_upserts_replay_with_original_schema_provider() -> None:
    submit_graph = {
        "last_node_id": 74,
        "last_link_id": 2,
        "nodes": [
            {
                "id": 10,
                "type": "VAEDecode",
                "pos": [0, 0],
                "size": [210, 80],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1, 2], "slot_index": 0}],
                "properties": {"vibecomfy_uid": "10"},
                "widgets_values": [],
            },
            {
                "id": 12,
                "type": "SaveImage",
                "pos": [500, 0],
                "size": [210, 80],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                "outputs": [],
                "properties": {"vibecomfy_uid": "12"},
                "widgets_values": [],
            },
            {
                "id": 74,
                "type": "ADE_AnimateDiffCombine",
                "pos": [500, 160],
                "size": [210, 80],
                "flags": {},
                "order": 2,
                "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE", "link": 2}],
                "outputs": [],
                "properties": {"vibecomfy_uid": "74"},
                "widgets_values": [],
            },
        ],
        "links": [
            [1, 10, 0, 12, 0, "IMAGE"],
            [2, 10, 0, 74, 0, "IMAGE"],
        ],
        "groups": [],
        "config": {},
        "extra": {},
    }
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "ImageScale",
                "uid": "n1",
                "node_id": "97",
                "fields": {
                    "upscale_method": "lanczos",
                    "width": 2048,
                    "height": 1152,
                    "crop": "disabled",
                },
                "inputs": {"image": ["", "10", "IMAGE"]},
                "anchor": {"relation": "right_of", "near": ["", "10"]},
            },
            {
                "op": "upsert_link",
                "from": ["", "n1", "IMAGE"],
                "to": ["", "12", "images"],
            },
            {
                "op": "upsert_link",
                "from": ["", "n1", "IMAGE"],
                "to": ["", "74", "images"],
            },
        ],
    }
    provider = _Provider(
        {
            "ImageScale": NodeSchema(
                class_type="ImageScale",
                pack=None,
                inputs={
                    "image": InputSpec(type="IMAGE", required=True),
                    "upscale_method": InputSpec(
                        type="COMBO",
                        required=True,
                        choices=["nearest-exact", "bilinear", "area", "bicubic", "lanczos"],
                    ),
                    "width": InputSpec(type="INT", required=True),
                    "height": InputSpec(type="INT", required=True),
                    "crop": InputSpec(
                        type="COMBO",
                        required=True,
                        choices=["disabled", "center"],
                    ),
                },
                outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
            )
        }
    )
    applied = apply_delta(
        submit_graph,
        normalize_delta_ops(envelope),
        schema_provider=provider,
    )
    assert applied.ok is True
    assert applied.candidate is not None

    without_schema = verify_replay(submit_graph, envelope, applied.candidate)
    assert without_schema.replay_ok is False

    receipt = verify_replay(
        submit_graph,
        envelope,
        applied.candidate,
        schema_provider=provider,
    )

    assert receipt.replay_ok is True
    assert receipt.candidate_matches is True
    assert receipt.op_count == 3
    assert receipt.error is None
