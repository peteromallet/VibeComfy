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
from vibecomfy.comfy_nodes.agent import authority_receipts as _authority_receipts
from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    build_schema_witness,
    schema_provider_from_witness,
)
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider
from vibecomfy.schema.types import (
    FrozenSchemaSnapshotProvider,
    capture_schema_snapshot,
    schema_payload_from_node_schema,
)


_OBJECT_INFO_ROOT = (
    Path(__file__).resolve().parents[1] / "vibecomfy" / "porting" / "cache" / "object_info"
)


def _frozen_provider(class_types: tuple[str, ...]) -> FrozenSchemaSnapshotProvider:
    """Frozen admission authority over whichever *class_types* resolve locally."""
    prov = ObjectInfoIndexSchemaProvider(str(_OBJECT_INFO_ROOT))
    payloads = {}
    for class_type in class_types:
        schema = prov.get_schema(class_type)
        if schema is not None:
            payloads[class_type] = schema_payload_from_node_schema(class_type, schema)
    snap = capture_schema_snapshot(
        class_types=sorted(payloads),
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": payloads,
            "missing_classes": [],
        },
        node_classes={str(i + 1): ct for i, ct in enumerate(sorted(payloads))},
    )
    return FrozenSchemaSnapshotProvider(snap)

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
            "VAEDecode": NodeSchema(
                class_type="VAEDecode",
                pack=None,
                inputs={},
                outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={"images": InputSpec(type="IMAGE", required=True)},
                outputs=[],
            ),
            "ADE_AnimateDiffCombine": NodeSchema(
                class_type="ADE_AnimateDiffCombine",
                pack="ComfyUI-AnimateDiff-Evolved",
                inputs={"images": InputSpec(type="IMAGE", required=True)},
                outputs=[],
            ),
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

    admission_snapshot = capture_schema_snapshot(
        class_types=sorted(provider._schemas),
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": {
                class_type: schema_payload_from_node_schema(class_type, schema)
                for class_type, schema in provider._schemas.items()
            },
            "missing_classes": [],
        },
        node_classes={
            "10": "VAEDecode",
            "12": "SaveImage",
            "74": "ADE_AnimateDiffCombine",
        },
    )
    witness = build_schema_witness(
        schema_provider=FrozenSchemaSnapshotProvider(admission_snapshot),
        submit_graph=submit_graph,
        candidate_payload=candidate,
        delta_envelope=envelope,
    )
    frozen_provider = schema_provider_from_witness(witness)

    # Publication reconstructs admission authority from the persisted witness
    # plus the original submit graph. The submit graph must not be ignored:
    # the sequential simulator needs it to recognize ImageScale after the
    # add_node op so the two dependent upserts can be admitted.
    from vibecomfy.porting.edit.admit import (
        AdmissionAllowed,
        admit_operations,
        snapshot_from_schema_witness,
    )

    reconstructed = snapshot_from_schema_witness(
        witness,
        submit_graph=submit_graph,
    )
    assert isinstance(admit_operations(reconstructed, envelope["ops"]), AdmissionAllowed)

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


def test_stamp_response_maps_replay_mismatch_to_authority_rejected() -> None:
    from vibecomfy.comfy_nodes.agent.authority_receipts import (
        AuthorityReceipt,
        ReplayReceipt,
        ResponseMetadataHashes,
        stamp_response_with_authority,
    )

    receipt = AuthorityReceipt(
        schema_version="2.0.0",
        session_id="sess",
        turn_id="turn",
        submit_graph_hash="a" * 64,
        submit_graph_bytes_sha256="b" * 64,
        accepted_batch_digest="c" * 64,
        cumulative_delta_hash="c" * 64,
        candidate_hash="d" * 64,
        schema_witness=None,
        schema_witness_hash=None,
        replay=ReplayReceipt(
            replay_ok=False,
            candidate_matches=False,
            recomputed_candidate_hash=None,
            persisted_candidate_hash="d" * 64,
            error="replay_mismatch",
        ),
        response_metadata=ResponseMetadataHashes(None, None, None),
        created_at="2026-08-21T00:00:00Z",
    )
    stamped = stamp_response_with_authority(
        {
            "ok": True,
            "apply_eligible": True,
            "outcome": {"kind": "candidate"},
            "candidate": {"graph": {"nodes": [{"id": 1}]}, "state": "ready"},
            "message": "Edit landed.",
        },
        receipt,
    )
    assert stamped["terminal_state"] == "authority_rejected"
    assert stamped["outcome"]["kind"] != "clarify"
    assert stamped["apply_eligible"] is False
    assert "candidate" not in stamped or stamped.get("candidate") in (None, {})
    assert "graph" not in stamped or stamped.get("graph") in (None, {})
    assert "accepted_batch" not in stamped or stamped.get("accepted_batch") in (None, [], ())
    assert stamped["audit"]["rejected_candidate"]["state"] == "rejected"
    assert stamped["audit"]["rejected_candidate"]["graph"] == {"nodes": [{"id": 1}]}
    assert stamped.get("accepted_delta_ids") in ((), [], None) or list(stamped.get("accepted_delta_ids") or ()) == []



# ── T2.3 crash-boundary injections ──────────────────────────────────────────


def _ksampler_schema() -> NodeSchema:
    return NodeSchema(
        class_type="KSampler",
        pack="core",
        inputs={
            "model": InputSpec(type="MODEL", required=True),
            "positive": InputSpec(type="CONDITIONING", required=True),
            "negative": InputSpec(type="CONDITIONING", required=True),
            "seed": InputSpec(type="INT", required=True),
            "steps": InputSpec(type="INT", required=True),
            "cfg": InputSpec(type="FLOAT", required=True),
            "sampler_name": InputSpec(type="COMBO", required=True),
            "scheduler": InputSpec(type="COMBO", required=True),
            "denoise": InputSpec(type="FLOAT", required=True),
        },
        outputs=[OutputSpec(type="LATENT", name="LATENT")],
    )


def _mode_turn_fixture() -> tuple[dict, dict, dict, list]:
    """(submit graph, candidate graph, delta envelope, accepted batch)."""
    submit = {
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "mode": 0,
                "pos": [10, 20],
                "size": [320, 240],
                "properties": {"vibecomfy_uid": "sampler-1"},
                "widgets_values": [],
                "inputs": [],
                "outputs": [],
            }
        ],
        "links": [],
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4,
    }
    candidate = json.loads(json.dumps(submit))
    candidate["nodes"][0]["mode"] = 4
    envelope = {
        "schema_version": "2.0.0",
        "ops": [{"op": "set_mode", "target": ["", "sampler-1"], "mode": 4}],
    }
    accepted = [{"op": op} for op in envelope["ops"]]
    return submit, candidate, envelope, accepted


def test_crash_after_delta_before_receipt_leaves_no_authority_and_recovers_undetermined(
    tmp_path: Path,
) -> None:
    """Injection 4: the process dies after persisting submit+delta but before
    authority/receipt.json exists. The turn must carry NO authority, and
    recovery must refuse to guess ``applied`` from unverified delta evidence.
    """
    from vibecomfy.porting.edit.checkpoint import (
        TERMINAL_STATE_UNDETERMINED,
        recover_terminal_checkpoint,
    )

    submit, candidate, _envelope, accepted = _mode_turn_fixture()
    turn_dir = tmp_path / "sessions" / "crash-a" / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    (turn_dir / "request.json").write_text(json.dumps({"graph": submit}), encoding="utf-8")
    evidence = {"original_graph": submit, "graph": candidate, "accepted_batch": accepted}

    assert load_authority_receipt(turn_dir) is None
    checkpoint = recover_terminal_checkpoint(evidence)
    assert checkpoint.terminal_state == TERMINAL_STATE_UNDETERMINED
    assert checkpoint.replay_verified is False
    assert checkpoint.reason == "unknown_evidence_not_guessed_applied"
    assert checkpoint.deltas == ()


def test_crash_after_receipt_before_projection_recovers_applied_deterministically(
    tmp_path: Path,
) -> None:
    """Injection 5: the receipt is durable but response.json / session-state /
    projection never landed. Recovery classifies deterministically from the
    persisted receipt + accepted delta (row 7), never by guessing.
    """
    from vibecomfy.porting.edit.checkpoint import (
        TERMINAL_STATE_APPLIED,
        project_terminal_checkpoint,
        recover_terminal_checkpoint,
    )

    submit, candidate, envelope, accepted = _mode_turn_fixture()
    response = {
        "agent_edit_protocol": "v2_delta",
        "graph": candidate,
        "accepted_batch": accepted,
        "eligibility": {"applyable": True, "reason": "applyable", "message": "ok"},
    }
    turn_dir = tmp_path / "sessions" / "crash-b" / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    receipt = build_authority_receipt(
        session_id="crash-b",
        turn_id="0001",
        submit_graph=submit,
        cumulative_delta_envelope=envelope,
        candidate=candidate,
        response=response,
        schema_version="2.0.0",
        schema_provider=_Provider({"KSampler": _ksampler_schema()}),
    )
    assert receipt.is_applyable
    write_authority_receipt(turn_dir, receipt)
    assert load_authority_receipt(turn_dir) == receipt

    evidence = {
        "authority_receipt": receipt.to_dict(),
        "original_graph": submit,
        "graph": candidate,
        "accepted_batch": accepted,
    }
    checkpoint = recover_terminal_checkpoint(evidence)
    assert checkpoint.terminal_state == TERMINAL_STATE_APPLIED
    assert checkpoint.replay_verified is True
    assert len(checkpoint.deltas) == 1

    # The frozen mode-neutral projector mirrors the recovered checkpoint; it
    # does not invent a different terminal state from partial evidence.
    projection = project_terminal_checkpoint(checkpoint)
    assert projection.terminal_state == TERMINAL_STATE_APPLIED
    assert projection.accepted is True
    assert projection.landed_count == 1


def test_mint_fails_closed_when_frozen_name_table_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RRSYN-1 / RR1-FIX-REV: an op-bearing delta over an EXISTING node may
    never mint applyable authority when the frozen name domain cannot be
    derived — the old code silently replayed unpinned."""
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
    monkeypatch.setattr(
        _authority_receipts,
        "canonical_frozen_name_table",
        lambda *args, **kwargs: {},
    )

    receipt = build_authority_receipt(
        session_id="s",
        turn_id="t",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=None,
        response={},
        schema_version="2.0.0",
        schema_provider=_frozen_provider(("CLIPTextEncode",)),
    )

    assert receipt.is_applyable is False
    assert receipt.replay.replay_ok is False
    assert receipt.replay.op_count == 1
    assert receipt.replay.error is not None
    assert receipt.replay.error.startswith("frozen_name_table_unavailable:")


def test_mint_still_applies_when_frozen_name_table_derives() -> None:
    """Positive control: a derivable table leaves ordinary receipts intact."""
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

    receipt = build_authority_receipt(
        session_id="s",
        turn_id="t",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=recompute_apply(submit_graph, envelope)[1],
        response={},
        schema_version="2.0.0",
        schema_provider=_frozen_provider(("CLIPTextEncode",)),
    )

    assert receipt.is_applyable is True
    assert receipt.replay.frozen_name_table


def test_mint_applies_with_explicit_empty_roster_row_for_widgetless_node() -> None:
    """RR1-FIX-REV2: an explicitly represented EMPTY roster is legitimate
    per-node coverage.  A sealed widgetless existing node derives a ``()``
    row, so a legal delta touching it (mode flip) mints an applyable,
    fully-pinned receipt instead of failing coarse table absence."""
    submit_graph = {
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 7,
                "type": "PreviewImage",
                "mode": 0,
                "pos": [0, 0],
                "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
                "outputs": [],
                "properties": {"vibecomfy_uid": "pv"},
            }
        ],
        "links": [],
    }
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_mode",
                "target": ["", "pv"],
                "mode": 4,
            }
        ],
    }
    candidate = recompute_apply(submit_graph, envelope)[1]

    receipt = build_authority_receipt(
        session_id="s",
        turn_id="t",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=candidate,
        response={},
        schema_version="2.0.0",
        schema_provider=_frozen_provider(("PreviewImage",)),
    )

    assert receipt.is_applyable is True
    assert receipt.replay.error is None
    assert receipt.replay.frozen_name_table == {"7": ()}


def _two_node_probe_graph() -> dict:
    """Reviewer probe shape: existing node WITH a derivable roster plus an
    existing WIDGETLESS node carrying a distinct vibecomfy_uid."""
    return {
        "last_node_id": 7,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 6,
                "type": "CLIPTextEncode",
                "mode": 0,
                "pos": [0, 0],
                "inputs": [{"name": "clip", "type": "CLIP", "link": None}],
                "outputs": [],
                "widgets_values": ["prompt"],
                "properties": {},
            },
            {
                "id": 7,
                "type": "PreviewImage",
                "mode": 0,
                "pos": [0, 0],
                "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
                "outputs": [],
                "properties": {"vibecomfy_uid": "pv"},
            },
        ],
        "links": [],
    }


def test_mint_rejects_partial_name_domain_when_other_existing_node_touched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RR1-FIX-REV2 reviewer probe: a two-node graph whose derived table
    covers node 6 only, while ``remove_node`` targets EXISTING node 7
    (uid ``pv``).  The REV mint guard fired only when the WHOLE table was
    falsey, so this non-empty-but-partial table minted an applyable receipt
    replaying node pv's removal unpinned.  Coverage is now per touched
    EXISTING node: the missing row must fail the mint."""
    submit_graph = _two_node_probe_graph()
    envelope = {
        "schema_version": "2.0.0",
        "ops": [{"op": "remove_node", "target": ["", "pv"]}],
    }
    # Genuine candidate: pre-revision this replayed clean against the
    # partial table and minted an applyable receipt — the exact reviewer
    # observation.
    candidate = recompute_apply(submit_graph, envelope)[1]
    monkeypatch.setattr(
        _authority_receipts,
        "canonical_frozen_name_table",
        lambda *args, **kwargs: {"6": ("text",)},
    )

    receipt = build_authority_receipt(
        session_id="s",
        turn_id="t",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=candidate,
        response={},
        schema_provider=_frozen_provider(("CLIPTextEncode", "PreviewImage")),
        schema_version="2.0.0",
    )

    assert receipt.is_applyable is False
    assert receipt.replay.replay_ok is False
    assert receipt.replay.op_count == 1
    assert receipt.replay.error is not None
    assert receipt.replay.error.startswith("frozen_name_table_unavailable:")
    assert "pv" in receipt.replay.error


def test_verify_replay_requires_row_for_every_touched_existing_node() -> None:
    """Verify side of the same law: an explicitly EMPTY or partial authority
    mapping no longer passes seal verification just because it is truthy-
    adjacent — every touched existing node needs its own row."""
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
    for label, authority in (
        ("empty-mapping", {}),
        ("foreign-row-only", {"999": ("unrelated",)}),
    ):
        ok, _candidate, error, _op_count = recompute_apply(
            submit_graph,
            envelope,
            name_authority=authority,
        )
        assert ok is False, label
        assert error is not None, label
        assert "frozen_name_table_row_missing" in error, label
        assert "(uid 2)" in error, label


def test_explicit_empty_roster_row_is_legitimate_coverage() -> None:
    """An explicitly represented EMPTY roster satisfies per-node coverage;
    absence of a row never does."""
    submit_graph = {
        "last_node_id": 7,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 7,
                "type": "PreviewImage",
                "mode": 0,
                "pos": [0, 0],
                "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
                "outputs": [],
                "properties": {"vibecomfy_uid": "pv"},
            }
        ],
        "links": [],
    }
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "pv", "anything"],
                "value": 1,
            }
        ],
    }

    ok, _candidate, error, _op_count = recompute_apply(
        submit_graph,
        envelope,
        schema_provider=_frozen_provider(("PreviewImage",)),
        name_authority={"7": ()},
    )

    # Coverage passes; whatever rejection follows comes from admission on the
    # unknown field, never from the name-domain row law.
    assert error is not None
    assert "frozen_name_table_row_missing" not in error
    assert "name_domain_divergence" not in error
