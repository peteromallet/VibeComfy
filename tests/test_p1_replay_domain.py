"""P1-REPLAY-HASH-DOMAIN focused tests.

R1  single hash domain — replay recomputes against the retained IR plus the
    FROZEN snapshot field table recorded on the receipt; a second, drifted
    schema provider can never shift the widget/slot zip again.
R2  empty graph ≠ candidate — ``candidate={"graph": {}}`` carries NO
    candidate authority, so a pure clarify survives verbatim instead of being
    misrouted to ``authority_rejected``.
R3  apply eligibility gate — ``apply_eligible`` may be true ONLY IF the
    accepted batch is non-empty AND the replay matched. Fail-closed direction
    everywhere else (mismatched replay ⇒ authority_rejected).

Every scenario below fails on pre-change code: R1 needs
``canonical_frozen_name_table`` / the ``name_authority`` replay input /
``ReplayReceipt.frozen_name_table``, none of which existed before P1.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    build_authority_receipt,
    canonical_frozen_name_table,
    stamp_response_with_authority,
    validate_authority_receipt_v2,
    verify_replay,
)
from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    build_schema_witness,
    schema_provider_from_witness,
)
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit.ops import normalize_delta_ops
from vibecomfy.porting.emit.ui import emit_ui_json, pin_untouched_ui
from vibecomfy.schema import (
    FrozenSchemaSnapshotProvider,
    InputSpec,
    NodeSchema,
    capture_schema_snapshot,
)

FIXTURE = (
    Path(__file__).parent
    / "characterization"
    / "fixtures"
    / "agent_edit"
    / "case_01_widget_set"
    / "input_ui.json"
)

DRIFT_CLASS = "P1DomainDriftNode"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _drift_object_info(slot_order: tuple[str, str]) -> dict:
    """object_info surface whose compact slots are named in *slot_order*."""
    return {
        DRIFT_CLASS: {
            "input": {
                "required": {
                    slot_order[0]: ["INT", {"default": 0}],
                    slot_order[1]: ["INT", {"default": 1}],
                }
            },
            "input_order": list(slot_order),
            "output": ["INT"],
            "output_node": True,
            "name": DRIFT_CLASS,
            "category": "test",
        }
    }


class _DriftedAmbientProvider:
    """Second provider whose widget roster disagrees with the sealed domain."""

    def get_schema(self, class_type: str) -> NodeSchema | None:
        if class_type != DRIFT_CLASS:
            return None
        return NodeSchema(
            class_type=DRIFT_CLASS,
            pack="core",
            inputs={
                "steps": InputSpec(type="INT", required=True, default=1),
                "seed": InputSpec(type="INT", required=True, default=0),
            },
            outputs=[],
            confidence=1.0,
        )


def _frozen_replay_provider() -> tuple[Any, FrozenSchemaSnapshotProvider]:
    """The admission-locked domain of record (seed first) as replay sees it."""
    snapshot = capture_schema_snapshot(
        request_snapshot=_drift_object_info(("seed", "steps")),
        class_types=[DRIFT_CLASS],
    )
    locked = FrozenSchemaSnapshotProvider(snapshot)
    witness = build_schema_witness(
        schema_provider=locked,
        submit_graph=None,
        candidate_payload=None,
        delta_envelope=None,
    )
    return schema_provider_from_witness(witness), locked


def _submit_graph() -> dict:
    submit = json.loads(FIXTURE.read_text(encoding="utf-8"))
    submit["nodes"].append(
        {
            "id": 9,
            "type": DRIFT_CLASS,
            "pos": [0, 0],
            "size": [100, 100],
            "flags": {},
            "order": 0,
            "mode": 0,
            "inputs": [],
            "outputs": [],
            "properties": {"Node name for S&R": DRIFT_CLASS},
            # No metadata alias surfaces at all: name resolution depends on
            # whatever provider ingests this graph — the D-a zip-shift setup.
            "widgets_values": [7, 30],
        }
    )
    submit["last_node_id"] = 9
    return submit


def _envelope() -> dict:
    return {
        "schema_version": "2.0.0",
        "ops": [
            {"op": "set_node_field", "target": ["", "9", "seed"], "value": 99}
        ],
    }


def _admission_candidate(submit_graph: dict, envelope: dict, schema_provider: Any) -> dict:
    ops = normalize_delta_ops(envelope)
    workflow = from_ui(
        dict(submit_graph), schema_provider=schema_provider, use_comfy_converter=False
    )
    for op in ops:
        step = interpret(workflow, (op,), schema_provider=schema_provider)
        assert step.ok, step.diagnostics
        workflow = step.workflow
    emitted = emit_ui_json(
        workflow,
        schema_provider=schema_provider,
        include_virtual_wires=True,
        prior_ui_payload=submit_graph,
    )
    return pin_untouched_ui(submit_graph, emitted, ops)


def _widgets_of(candidate: dict, node_id: int) -> list:
    node = next(n for n in candidate["nodes"] if n.get("id") == node_id)
    return node["widgets_values"]


# ---------------------------------------------------------------------------
# R1 — single replay hash domain
# ---------------------------------------------------------------------------


def test_retained_delta_matches_under_drifted_second_provider() -> None:
    """(a) The frozen domain pins the zip: a drifted second provider cannot move it.

    Pre-change, replay under the drifted provider resolved ``seed`` onto slot
    1 and rejected the byte-identical retained delta with
    ``candidate_hash_mismatch`` (the d66a66 defect).
    """
    submit_graph = _submit_graph()
    envelope = _envelope()
    replay_provider, _locked = _frozen_replay_provider()

    candidate = _admission_candidate(submit_graph, envelope, replay_provider)
    assert _widgets_of(candidate, 9) == [99, 30]

    # Defect control: WITHOUT the frozen domain the drifted provider shifts the zip.
    drifted = _DriftedAmbientProvider()
    unpinned = verify_replay(submit_graph, envelope, candidate, schema_provider=drifted)
    assert unpinned.replay_ok is True
    assert unpinned.candidate_matches is False
    assert unpinned.error == "candidate_hash_mismatch"

    # With the frozen field table derived from the RETAINED domain, the same
    # drifted second provider replays to the identical candidate.
    frozen_table = canonical_frozen_name_table(
        submit_graph, schema_provider=replay_provider
    )
    assert frozen_table.get("9") == ("seed", "steps")

    pinned = verify_replay(
        submit_graph,
        envelope,
        candidate,
        schema_provider=drifted,
        name_authority=frozen_table,
    )
    assert pinned.replay_ok is True
    assert pinned.candidate_matches is True, pinned.error


def test_receipt_records_one_frozen_name_domain_for_later_verification() -> None:
    """The minted receipt carries its name domain of record; consuming it later
    reproduces the exact hash domain regardless of ambient provider drift."""
    submit_graph = _submit_graph()
    envelope = _envelope()
    replay_provider, locked = _frozen_replay_provider()

    candidate = _admission_candidate(submit_graph, envelope, replay_provider)
    response = {
        "graph": candidate,
        "accepted_batch": envelope["ops"],
        "eligibility": {"applyable": True},
        "outcome": {"kind": "candidate"},
    }
    receipt = build_authority_receipt(
        session_id="p1-domain",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=candidate,
        response=response,
        schema_version="2.0.0",
        schema_provider=locked,
    )

    assert receipt.is_applyable is True
    recorded = receipt.replay.frozen_name_table or {}
    assert recorded.get("9") == ("seed", "steps")

    # Round-trip through the persisted representation keeps the domain.
    revived = type(receipt.replay).from_dict(receipt.replay.to_dict())
    assert revived.frozen_name_table == receipt.replay.frozen_name_table

    # A later verification under the DRIFTED ambient provider consumes the
    # recorded domain and reaches the identical verdict.
    late = verify_replay(
        submit_graph,
        envelope,
        candidate,
        schema_provider=_DriftedAmbientProvider(),
        name_authority=receipt.replay.frozen_name_table,
    )
    assert late.replay_ok is True
    assert late.candidate_matches is True, late.error

    # Strict validation accepts the new optional replay field…
    validate_authority_receipt_v2(receipt.to_dict())
    # …and receipts minted before P1 (no field) stay valid.
    legacy = receipt.to_dict()
    legacy["replay"] = {
        key: value
        for key, value in legacy["replay"].items()
        if key != "frozen_name_table"
    }
    validate_authority_receipt_v2(legacy)


# ---------------------------------------------------------------------------
# R2 — empty graph ≠ candidate
# ---------------------------------------------------------------------------


def test_pure_clarify_with_empty_candidate_object_survives_verbatim() -> None:
    """(b) ``candidate={"graph": {}}`` is NOT candidate authority.

    A clarify turn carrying an empty candidate object must survive verbatim;
    pre-change the truthy-but-empty carrier misrouted it to
    ``authority_rejected``, rewriting outcome/message/eligibility.
    """
    submit_graph = _submit_graph()
    replay_provider, locked = _frozen_replay_provider()
    response = {
        "outcome": {"kind": "clarify"},
        "graph_unchanged": True,
        "candidate": {"graph": {}},
        "message": "Which node do you mean by that?",
    }
    receipt = build_authority_receipt(
        session_id="p1-clarify",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope=None,
        candidate=None,
        response=response,
        schema_version="",
        schema_provider=locked,
    )
    assert receipt.is_applyable is False

    stamped = stamp_response_with_authority(dict(response), receipt)
    assert isinstance(stamped.get("outcome"), dict)
    assert stamped["outcome"].get("kind") == "clarify", stamped["outcome"]
    assert stamped.get("no_candidate_reason") != "authority_replay_mismatch"
    assert stamped.get("message") == response["message"]
    assert stamped.get("apply_eligible") is not False

    # Fail-closed direction preserved: a REAL candidate hidden under a clarify
    # label is still rejected.
    real_candidate = _admission_candidate(submit_graph, _envelope(), replay_provider)
    spoof = {
        "outcome": {"kind": "clarify"},
        "graph_unchanged": True,
        "candidate": {"graph": real_candidate},
    }
    spoof_receipt = build_authority_receipt(
        session_id="p1-clarify-spoof",
        turn_id="0002",
        submit_graph=submit_graph,
        cumulative_delta_envelope=None,
        candidate=real_candidate,
        response=spoof,
        schema_version="",
        schema_provider=locked,
    )
    spoof_stamped = stamp_response_with_authority(dict(spoof), spoof_receipt)
    assert (spoof_stamped.get("eligibility") or {}).get("reason") == "authority_rejected"


# ---------------------------------------------------------------------------
# R3 — apply eligibility gate
# ---------------------------------------------------------------------------


def test_apply_eligible_false_when_accepted_batch_empty() -> None:
    """(c) A matched replay with NOTHING admitted never projects applyability."""
    submit_graph = _submit_graph()
    envelope = _envelope()
    replay_provider, locked = _frozen_replay_provider()
    candidate = _admission_candidate(submit_graph, envelope, replay_provider)

    response = {
        "graph": candidate,
        "accepted_batch": [],
        "apply_eligible": True,
        "eligibility": {"applyable": True},
        "outcome": {"kind": "candidate"},
    }
    receipt = build_authority_receipt(
        session_id="p1-empty-batch",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=candidate,
        response=response,
        schema_version="2.0.0",
        schema_provider=locked,
    )
    # The delta itself verifies — the gate fires purely on the empty batch.
    assert receipt.replay.replay_ok is True
    assert receipt.replay.candidate_matches is True

    stamped = stamp_response_with_authority(dict(response), receipt)
    assert stamped["apply_eligible"] is False
    assert stamped["canvas_apply_allowed"] is False
    assert stamped["queue_allowed"] is False
    assert stamped["apply_allowed"] is False
    assert (stamped.get("eligibility") or {}).get("reason") == "no_accepted_batch"
    assert stamped.get("terminal_state") == "no_candidate"


def test_apply_eligible_false_when_candidate_matches_false() -> None:
    """(d) A mismatched replay keeps the full fail-closed rejection envelope."""
    submit_graph = _submit_graph()
    envelope = _envelope()
    replay_provider, locked = _frozen_replay_provider()
    candidate = _admission_candidate(submit_graph, envelope, replay_provider)

    tampered = copy.deepcopy(candidate)
    for node in tampered["nodes"]:
        if node.get("id") == 9:
            node["widgets_values"] = [7, 99]  # the drifted-zip rendering

    response = {
        "graph": tampered,
        "accepted_batch": envelope["ops"],
        "apply_eligible": True,
        "outcome": {"kind": "candidate"},
    }
    receipt = build_authority_receipt(
        session_id="p1-mismatch",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=tampered,
        response=response,
        schema_version="2.0.0",
        schema_provider=locked,
    )
    assert receipt.is_applyable is False

    stamped = stamp_response_with_authority(dict(response), receipt)
    assert stamped["apply_eligible"] is False
    assert (stamped.get("eligibility") or {}).get("reason") == "authority_rejected"
    assert stamped.get("terminal_state") == "authority_rejected"
