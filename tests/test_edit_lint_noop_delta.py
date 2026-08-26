"""RR2-REGRESSION: lint-proven no-op statements never enter the durable Δ.

Observed on rr1-window20 staged ``f65774`` (round-2 wave, HEAD ce7a34d6):
the model emitted a benign redundant re-assertion (``pbr = True`` next to
the real texture-quality write). Live admission landed it because the
schema-spec path of ``_validate_field`` skips positional old-value
comparison; the batch loop's lint gate then classified it ``dropped_noop``
(recorded as turn ``noop_field_changes``, subtracted from
``landed_op_count``, excluded from reply claims via ``real_field_changes``)
— but the durable Δ minted from ``accepted_batch`` still carried BOTH ops.
Authority replay must re-apply the Δ verbatim, hit ``ApplyOpsError("no_op")``
on the already-true write, and failed the whole candidate closed:
``authority_rejected``, graph unchanged, product_fail.

The fix: the durable Δ is the EFFECTIVE Δ. Statements whose op the lint
gate proved changed nothing are excluded where the Δ is minted
(``_frag_response_contract``), so Δ ≡ candidate ≡ claims and replay only
ever sees writes that can land.

Fixtures mirror the persisted payload shape exactly:
turn 0001 of session a17ab01a… — statements [texture_quality='detailed'
(applied), pbr=True (applied, lint-noop), done() (skipped)] with
``noop_field_changes=[{uid: "26", field_path: "pbr"}]``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from vibecomfy.comfy_nodes.agent._frag_response_contract import (
    _build_cumulative_batch_repl_delta_envelope,
    _effective_accepted_batch_statements,
    _statement_is_lint_noop,
)
from vibecomfy.comfy_nodes.agent._frag_state import derived_accepted_delta_envelope
from vibecomfy.comfy_nodes.agent.authority_receipts import recompute_apply


# ── fixtures: the persisted f65774 turn record, byte-shape identical ─────────


def _persisted_turn_record() -> dict[str, Any]:
    """Turn record mirroring out/.../f65774 turns/0001/model_response.json."""
    return {
        "turn_number": 0,
        "batch_ok": True,
        "batch": (
            "tripotexturenode.texture_quality = 'detailed'\n"
            "tripotexturenode.pbr = True\ndone()"
        ),
        "statement_count": 3,
        "landed_op_count": 1,
        "raw_landed_op_count": 2,
        "lint_dropped_op_count": 1,
        "statements": [
            {
                "ok": True,
                "landed": True,
                "status": "applied",
                "source": "tripotexturenode.texture_quality = 'detailed'",
                "op_kind": "set_node_field",
                "touched_uids": ["26"],
                "op": {
                    "op": "set_node_field",
                    "target": ["", "26", "texture_quality"],
                    "value": "detailed",
                },
            },
            {
                "ok": True,
                "landed": True,
                "status": "applied",
                "source": "tripotexturenode.pbr = True",
                "op_kind": "set_node_field",
                "touched_uids": ["26"],
                "op": {
                    "op": "set_node_field",
                    "target": ["", "26", "pbr"],
                    "value": True,
                },
            },
            {
                "ok": True,
                "landed": False,
                "status": "skipped",
                "source": "done()",
                "op_kind": "done",
                "touched_uids": [],
            },
        ],
        "noop_field_changes": [
            {"field_path": "pbr", "new": True, "old": None, "uid": "26"}
        ],
    }


def _state_with_persisted_turn() -> SimpleNamespace:
    return SimpleNamespace(batch_turns=[_persisted_turn_record()])


# ── the durable Δ excludes lint-proven no-ops ────────────────────────────────


def test_envelope_carries_only_the_effective_write() -> None:
    """Pre-fix this envelope carried both ops and replay died on ``no_op``."""
    envelope = _build_cumulative_batch_repl_delta_envelope(
        _state_with_persisted_turn()
    )
    assert envelope is not None
    assert envelope["ops"] == [
        {
            "op": "set_node_field",
            "target": ["", "26", "texture_quality"],
            "value": "detailed",
        }
    ]


def test_accepted_batch_entries_exclude_only_the_noop_statement() -> None:
    accepted = _effective_accepted_batch_statements(_state_with_persisted_turn())
    assert len(accepted) == 1
    assert accepted[0]["op"]["target"] == ["", "26", "texture_quality"]
    # Entry shape stays the canonical one consumers already read.
    assert set(accepted[0]) >= {
        "statement_index",
        "source",
        "op_kind",
        "touched_uids",
        "status",
        "reason",
        "op",
    }
    assert accepted[0]["source"] == "tripotexturenode.texture_quality = 'detailed'"


def test_all_noop_turn_yields_empty_delta_for_identity_apply() -> None:
    """A turn that only re-asserted existing values mints NO delta ops; the
    apply path synthesizes the canonical empty envelope (identity apply with
    explicit empty evidence) instead of failing replay on no-op writes."""
    noop_statement = {
        "ok": True,
        "landed": True,
        "status": "applied",
        "source": "tripotexturenode.pbr = True",
        "op_kind": "set_node_field",
        "touched_uids": ["26"],
        "op": {"op": "set_node_field", "target": ["", "26", "pbr"], "value": True},
    }
    done_statement = {
        "ok": True,
        "landed": False,
        "status": "skipped",
        "source": "done()",
        "op_kind": "done",
        "touched_uids": [],
    }
    turn = {
        "turn_number": 0,
        "batch_ok": True,
        "statements": [noop_statement, dict(noop_statement), done_statement],
        "noop_field_changes": [{"uid": "26", "field_path": "pbr"}],
    }
    envelope = _build_cumulative_batch_repl_delta_envelope(
        SimpleNamespace(batch_turns=[turn])
    )
    assert envelope is None


def test_non_set_field_kinds_are_never_dropped_by_field_keys() -> None:
    """add_node/remove_node have no FieldChange identity and survive even a
    same-(uid, field) noop record; link ops key off their ``to`` triple."""
    noop = frozenset({("9", "seed")})
    add_node = {
        "op": "add_node",
        "scope_path": "",
        "class_type": "Probe",
        "fields": {"seed": 1},
        "inputs": {},
    }
    assert not _statement_is_lint_noop({"op": add_node}, noop)

    upsert = {
        "op": "upsert_link",
        "from": ["", "3", "IMAGE_0"],
        "to": ["", "9", "seed"],
    }
    assert _statement_is_lint_noop({"op": upsert}, noop)

    set_mode = {"op": "set_mode", "target": ["", "9"], "mode": "bypassed"}
    assert not _statement_is_lint_noop({"op": set_mode}, noop)
    assert _statement_is_lint_noop(
        {"op": set_mode}, frozenset({("9", "mode")})
    )


# ── replay semantics on a minimal graph pair reproducing the receipt ────────


_SUBMIT_UI = {
    "nodes": [
        {
            "id": 26,
            "type": "ProbeNode",
            "mode": 4,
            "order": 0,
            "inputs": [],
            "outputs": [],
            "pos": [0, 0],
            "properties": {"vibecomfy_uid": "26"},
            "widgets_values": [True, "standard"],
        }
    ],
    "links": [],
}

_FROZEN_NAMES = {"26": ["pbr", "texture_quality"]}

_NOOP_OP = {"op": "set_node_field", "target": ["", "26", "pbr"], "value": True}
_REAL_OP = {
    "op": "set_node_field",
    "target": ["", "26", "texture_quality"],
    "value": "detailed",
}


def test_redundant_write_in_delta_fails_replay_closed() -> None:
    """The persisted receipt mechanism: replaying the unfiltered Δ raises the
    typed ``no_op`` rejection — why no-op statements must never be minted."""
    ok, _candidate, error, op_count = recompute_apply(
        _SUBMIT_UI,
        {"schema_version": "2.0.0", "ops": [_REAL_OP, _NOOP_OP]},
        name_authority=_FROZEN_NAMES,
    )
    assert ok is False
    assert error == "no_op"
    assert op_count == 2


def test_effective_delta_replays_and_lands_exactly_the_real_change() -> None:
    envelope = _build_cumulative_batch_repl_delta_envelope(
        _state_with_persisted_turn()
    )
    ok, candidate, error, op_count = recompute_apply(
        _SUBMIT_UI,
        envelope,
        name_authority=_FROZEN_NAMES,
    )
    assert ok is True
    assert error is None
    assert op_count == 1
    nodes = candidate["nodes"]
    node26 = nodes.get("26") if isinstance(nodes, dict) else next(
        n for n in nodes if n["id"] == 26
    )
    assert node26["widgets_values"] == [True, "detailed"]
    # The redundant re-assertion left no second edit anywhere: the emitted
    # row carries only the real change, and pbr stays at its captured value.
    assert node26["widgets_values"][0] is True


def test_envelope_matches_canonical_derivation_of_effective_batch() -> None:
    """The transient envelope and any consumer deriving from the effective
    accepted batch reach the identical apply-binding ops."""
    state = _state_with_persisted_turn()
    envelope = _build_cumulative_batch_repl_delta_envelope(state)
    canonical = derived_accepted_delta_envelope(
        {"accepted_batch": list(_effective_accepted_batch_statements(state))}
    )
    assert envelope == canonical


def test_clean_turns_pass_through_unchanged() -> None:
    """No noop records → the effective Δ is exactly the legacy durable Δ."""
    turn = _persisted_turn_record()
    del turn["noop_field_changes"]
    turn["lint_dropped_op_count"] = 0
    state = SimpleNamespace(batch_turns=[turn])
    assert _build_cumulative_batch_repl_delta_envelope(state)["ops"] == [
        _REAL_OP,
        _NOOP_OP,
    ]
