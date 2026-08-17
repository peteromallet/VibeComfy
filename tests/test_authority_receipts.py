from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    build_authority_receipt,
    load_authority_receipt,
    recompute_apply,
    verify_replay,
    write_authority_receipt,
)
from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    build_schema_witness,
    schema_provider_from_witness,
)
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
    ok, candidate, error, _ = recompute_apply(submit_graph, envelope)
    assert ok is True, error
    assert candidate is not None

    receipt = verify_replay(submit_graph, envelope, candidate)

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


def test_layout_only_candidate_uses_structural_noop_authority() -> None:
    submit_graph = _submit_graph()
    candidate = json.loads(json.dumps(submit_graph))
    candidate["nodes"][0]["pos"] = [1234, 567]
    candidate["groups"] = [
        {"title": "Generated layout group", "bounding": [1200, 500, 400, 300]}
    ]
    response = {
        "route": "reorganise",
        "change_details": {
            "layout_only": True,
            "structural_noop_evidence": {
                "candidate_available": True,
                "layout_only_structural_noop": True,
                "patch_apply_error": None,
            },
        },
        "outcome": {"kind": "candidate"},
    }

    receipt = build_authority_receipt(
        session_id="layout-session",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope={"schema_version": "2.0.0", "ops": []},
        candidate=candidate,
        response=response,
        schema_version="2.0.0",
    )

    assert receipt.is_applyable is True
    assert receipt.replay.replay_ok is True
    assert receipt.replay.candidate_matches is True
    assert receipt.replay.verification_kind == "layout_structural_noop"
    assert receipt.replay.op_count == 0


def test_layout_authority_rejects_semantic_change_despite_forged_layout_evidence() -> None:
    submit_graph = _submit_graph()
    candidate = json.loads(json.dumps(submit_graph))
    candidate["nodes"][0]["widgets_values"] = ["semantic mutation"]
    response = {
        "route": "reorganise",
        "change_details": {
            "layout_only": True,
            "structural_noop_evidence": {
                "candidate_available": True,
                "layout_only_structural_noop": True,
                "patch_apply_error": None,
            },
        },
        "outcome": {"kind": "candidate"},
    }

    receipt = build_authority_receipt(
        session_id="layout-session",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope={"schema_version": "2.0.0", "ops": []},
        candidate=candidate,
        response=response,
        schema_version="2.0.0",
    )

    assert receipt.is_applyable is False
    assert receipt.replay.replay_ok is False
    assert receipt.replay.candidate_matches is False
    assert receipt.replay.error == "layout_authority_mismatch"


def test_authority_receipt_schema_covers_every_serialized_v2_field() -> None:
    submit_graph = _submit_graph()
    receipt = build_authority_receipt(
        session_id="schema-session",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope={"schema_version": "2.0.0", "ops": []},
        candidate=submit_graph,
        response={"outcome": {"kind": "candidate"}},
        schema_version="2.0.0",
    )
    schema_path = (
        Path(__file__).parents[1]
        / "vibecomfy"
        / "porting"
        / "edit"
        / "schemas"
        / "v2"
        / "authority_receipt.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    serialized = receipt.to_dict()
    assert set(serialized) <= set(schema["properties"])
    assert set(schema["required"]) == set(serialized)
    assert set(serialized["replay"]) <= set(schema["$defs"]["ReplayReceipt"]["properties"])
    assert set(schema["$defs"]["ReplayReceipt"]["required"]) == set(serialized["replay"])
    assert set(schema["$defs"]["ResponseMetadataHashes"]["required"]) == set(serialized["response_metadata"])
    assert schema["properties"]["contract_version"]["const"] == "authority_receipt_v2"
    assert schema["properties"]["schema_version"]["const"] == "2.0.0"


def test_authority_receipt_persists_exact_operational_delta_evidence(
    tmp_path: Path,
) -> None:
    submit_graph = _submit_graph()
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "2", "text"],
                "value": "durable evidence",
            }
        ],
    }
    ok, candidate, error, _ = recompute_apply(submit_graph, envelope)
    assert ok is True, error
    assert candidate is not None
    receipt = build_authority_receipt(
        session_id="session-exact",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=candidate,
        response={"outcome": {"kind": "candidate"}},
        schema_version="2.0.0",
    )

    turn_dir = tmp_path / "turns" / "0001"
    path = write_authority_receipt(turn_dir, receipt)
    raw = json.loads(path.read_text(encoding="utf-8"))

    assert "cumulative_delta_envelope" not in raw
    assert "ops" not in raw
    assert isinstance(raw["accepted_batch_digest"], str)
    assert len(raw["accepted_batch_digest"]) == 64
    assert raw["accepted_batch_digest"] == raw["cumulative_delta_hash"]
    assert load_authority_receipt(turn_dir) == receipt
    assert write_authority_receipt(turn_dir, receipt) == path
    with pytest.raises(ValueError, match="collision"):
        write_authority_receipt(turn_dir, replace(receipt, created_at="different"))
    assert load_authority_receipt(turn_dir) == receipt


def test_missing_or_unknown_receipt_contract_and_delta_schema_fail_closed(
    tmp_path: Path,
) -> None:
    submit_graph = _submit_graph()
    envelope = {"schema_version": "2.0.0", "ops": []}
    receipt = build_authority_receipt(
        session_id="strict-receipt",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=submit_graph,
        response={"outcome": {"kind": "candidate"}},
        schema_version="2.0.0",
    )
    raw = receipt.to_dict()
    assert receipt.is_applyable is True

    turn_dir = tmp_path / "turns" / "0001"
    path = turn_dir / "authority" / "receipt.json"
    path.parent.mkdir(parents=True)
    for contract_version, schema_version in (
        (None, "2.0.0"),
        ("authority_receipt_v999", "2.0.0"),
        ("authority_receipt_v2", "9.0.0"),
    ):
        mutated = dict(raw)
        if contract_version is None:
            mutated.pop("contract_version", None)
        else:
            mutated["contract_version"] = contract_version
        mutated["schema_version"] = schema_version
        path.write_text(json.dumps(mutated), encoding="utf-8")
        loaded = load_authority_receipt(turn_dir)
        assert loaded is not None
        assert loaded.is_applyable is False


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
    ok, candidate, error, _ = recompute_apply(
        submit_graph,
        envelope,
        schema_provider=provider,
    )
    assert ok is True, error
    assert candidate is not None

    receipt = verify_replay(
        submit_graph,
        envelope,
        candidate,
        schema_provider=provider,
    )

    assert receipt.replay_ok is True
    assert receipt.candidate_matches is True
    assert receipt.op_count == 3
    assert receipt.error is None

    witness = build_schema_witness(
        schema_provider=provider,
        submit_graph=submit_graph,
        candidate_payload=candidate,
        delta_envelope=envelope,
    )
    frozen_provider = schema_provider_from_witness(witness)

    # Ambient schema discovery may change after candidate publication. Replay
    # remains tied to the persisted witness, while the changed ambient provider
    # cannot silently redefine the authored plan.
    provider._schemas["ImageScale"] = NodeSchema(
        class_type="ImageScale",
        pack=None,
        inputs={
            "image": InputSpec(type="IMAGE", required=True),
            "width": InputSpec(type="INT", required=True, min=4096),
        },
        outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
    )
    ambient_replay = verify_replay(
        submit_graph,
        envelope,
        candidate,
        schema_provider=provider,
    )
    frozen_replay = verify_replay(
        submit_graph,
        envelope,
        candidate,
        schema_provider=frozen_provider,
    )

    assert frozen_replay.replay_ok is True
    assert frozen_replay.candidate_matches is True
