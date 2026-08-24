"""P8-DELTA-REPLAY-CANON: canonical delta-replay fingerprint equality.

The intent judge's ``_verify_delta_replay`` compares the accepted Δ against
``diff(pre_ir, post_ir)`` via ``_op_fingerprint``.  The fingerprints must be
canonical: equality exactly when the edit layer treats the two statements as
identical (R1) — while any genuine divergence (wrong node, wrong field,
different value beyond numeric identity, extra/missing op) must keep
mismatching (R2), as a pure function of op contents (R3).

Regression shape (window R1-WINDOW20, dive verdict SPINE BUG ×5): honest
passes were suppressed because semantically identical operations — int 30 vs
"30", float formatting, node-id/slot str-int spelling — fingerprinted apart.
"""

from __future__ import annotations

import json

from tests.live_agentic_harness.intent_judge import (
    _canonical_edit_value,
    _op_fingerprint,
    _verify_delta_replay,
)
from vibecomfy.porting.edit.ops import parse_edit_delta
from vibecomfy.schema import get_schema_provider


def _ksampler_ui(steps: float | int | str, *, uid: str = "sampler") -> dict:
    return {
        "nodes": [
            {
                "id": uid,
                "type": "KSampler",
                "mode": 0,
                "properties": {"vibecomfy_uid": uid},
                "widgets_values": [42, "fixed", steps, 7, "euler", "normal", 1],
            }
        ],
        "links": [],
    }


def _set_field_op(uid: str, field: str, value: object) -> dict:
    return {"op": "set_node_field", "target": ["", uid, field], "value": value}


# ── R1: canonical equality across spellings ────────────────────────────────


def test_claimed_int_float_and_text_spellings_all_verify() -> None:
    """(a) claimed Δ == actual diff modulo int/float/text spelling → verified."""
    schema_provider = get_schema_provider("auto")
    for claimed_value in (30, 30.0, "30"):
        result = _verify_delta_replay(
            _ksampler_ui(20),
            _ksampler_ui(30),
            [_set_field_op("sampler", "steps", claimed_value)],
            schema_provider=schema_provider,
        )
        assert result["verified"] is True, (claimed_value, result)
        assert result["mismatches"] == []
        assert result["checked"] == 1


def test_fingerprint_numeric_identity_across_spellings() -> None:
    """int/float/bool/numeric-text spellings of one number share a fingerprint."""
    base_ops = [
        {"op": "set_node_field", "target": ["", "n", "steps"], "value": spelling}
        for spelling in (30, 30.0, "30")
    ]
    parsed = [tuple(_op_fingerprint(op) for op in parse_edit_delta(base_ops))]
    assert len(set(parsed[0])) == 1

    # bool collapses like Python == inside the diff layer (True == 1).
    bool_fp = _op_fingerprint(parse_edit_delta([_set_field_op("n", "flag", True)])[0])
    int_fp = _op_fingerprint(parse_edit_delta([_set_field_op("n", "flag", 1)])[0])
    assert bool_fp == int_fp


def test_fingerprint_node_and_slot_identity_string_forms() -> None:
    """Node ids and link slots compare in their canonical string form."""
    typed = parse_edit_delta(
        [{"op": "upsert_link", "from": ["", "7", 0], "to": ["", "9", "samples"]}]
    )[0]
    str_typed = parse_edit_delta(
        [{"op": "upsert_link", "from": ["", "7", "0"], "to": ["", "9", "samples"]}]
    )[0]
    assert _op_fingerprint(typed) == _op_fingerprint(str_typed)

    # Raw mapping side: int uid vs digit-string uid are the same identity.
    raw_int = {"op": "set_node_field", "target": ["", 9, "steps"], "value": 8}
    raw_str = {"op": "set_node_field", "target": ["", "9", "steps"], "value": 8}
    assert _op_fingerprint(raw_int) == _op_fingerprint(raw_str)


def test_fingerprint_drops_none_valued_default_keys_only() -> None:
    """Absence-vs-None is ignored (dict.get semantics); absence-vs-value isn't."""
    without = {"op": "remove_link", "to": ["", "9", "image"]}
    with_none = {"op": "remove_link", "id": None, "to": ["", "9", "image"]}
    assert _op_fingerprint(without) == _op_fingerprint(with_none)

    # A present uid can never equal an absent one (add_node authority).
    with_uid = dict(_set_field_op("9", "steps", 8))
    assert _op_fingerprint({"op": "add_node", "class_type": "X", "fields": {}, "inputs": {}}) != (
        _op_fingerprint(
            {"op": "add_node", "uid": "5", "class_type": "X", "fields": {}, "inputs": {}}
        )
    )
    del with_uid  # presence/absence strictness asserted above; keep lints quiet


def test_canonical_value_keeps_non_canonical_text_strict() -> None:
    """No invented looseness: only canonical integer text collapses to a number."""
    assert _canonical_edit_value("30") == _canonical_edit_value(30)
    assert _canonical_edit_value("-2") == _canonical_edit_value(-2)
    # Leading zeros / decimal text are NOT canonical spellings: they stay strings.
    assert _canonical_edit_value("030") != _canonical_edit_value(30)
    assert _canonical_edit_value("1.50") != _canonical_edit_value(1.5)
    assert _canonical_edit_value("abc") != _canonical_edit_value(30)


# ── R2: anti-gaming strictness ─────────────────────────────────────────────


def test_different_target_node_still_mismatches() -> None:
    """(b) claimed Δ targeting a DIFFERENT node than actual → still mismatched."""
    schema_provider = get_schema_provider("auto")
    pre = {
        "nodes": [_ksampler_ui(20, uid="a")["nodes"][0], _ksampler_ui(20, uid="b")["nodes"][0]],
        "links": [],
    }
    post = {
        "nodes": [_ksampler_ui(30, uid="a")["nodes"][0], _ksampler_ui(20, uid="b")["nodes"][0]],
        "links": [],
    }
    result = _verify_delta_replay(
        pre,
        post,
        [_set_field_op("b", "steps", 30)],
        schema_provider=schema_provider,
    )
    assert result["verified"] is False
    assert any("not what actually changed" in m for m in result["mismatches"])

    # Unknown uid: same fail-closed outcome.
    unknown = _verify_delta_replay(
        pre,
        post,
        [_set_field_op("ghost", "steps", 30)],
        schema_provider=schema_provider,
    )
    assert unknown["verified"] is False


def test_different_value_beyond_numeric_identity_still_mismatches() -> None:
    """(c) a different target value (31 / '31' / 30.5) never passes as 30."""
    schema_provider = get_schema_provider("auto")
    for claimed in (31, "31", 30.5):
        result = _verify_delta_replay(
            _ksampler_ui(20),
            _ksampler_ui(30),
            [_set_field_op("sampler", "steps", claimed)],
            schema_provider=schema_provider,
        )
        assert result["verified"] is False, (claimed, result)


def test_claimed_op_absent_from_actual_still_mismatches() -> None:
    """(d) extra-op strictness: a claim with no actual counterpart fails."""
    schema_provider = get_schema_provider("auto")
    identical = _ksampler_ui(20)
    result = _verify_delta_replay(
        identical,
        json.loads(json.dumps(identical)),
        [_set_field_op("sampler", "steps", 30)],
        schema_provider=schema_provider,
    )
    assert result["verified"] is False
    assert any("not what actually changed" in m for m in result["mismatches"])


def test_genuine_drift_stays_unverified() -> None:
    """(f) drift: Δ names a change that is not what actually changed."""
    schema_provider = get_schema_provider("auto")
    drifted = json.loads(json.dumps(_ksampler_ui(20)))
    drifted["nodes"][0]["widgets_values"][4] = "dpm_2"  # scheduler changed, not steps
    result = _verify_delta_replay(
        _ksampler_ui(20),
        drifted,
        [_set_field_op("sampler", "steps", 30)],
        schema_provider=schema_provider,
    )
    assert result["verified"] is False


# ── Window regression + R3 determinism ─────────────────────────────────────


def test_window_shape_string_typed_step_value_verifies_end_to_end() -> None:
    """(e) window failure shape: string-typed step value in Δ vs int in IR diff.

    Mirrors the R1-WINDOW20 legs: the post IR holds the typed int while the
    accepted Δ spells the same number as text.  Field names resolve through
    the ingest-side compact tables exactly as in the judged runs.
    """
    schema_provider = get_schema_provider("auto")
    result = _verify_delta_replay(
        _ksampler_ui(6),
        _ksampler_ui(8),
        [_set_field_op("sampler", "steps", "8")],
        schema_provider=schema_provider,
    )
    assert result == {"verified": True, "checked": 1, "mismatches": []}


def _splitsigmas_ui(step_value: float | int | str, *, uid: str = "47") -> dict:
    """Schema-unresolved custom node: the step slot stays positional."""
    return {
        "nodes": [
            {
                "id": uid,
                "type": "SplitSigmas",
                "mode": 0,
                "properties": {"vibecomfy_uid": uid},
                "widgets_values": [step_value],
            }
        ],
        "links": [],
    }


def test_positional_alias_claims_stay_rejected() -> None:
    """Canonicalization never bypasses the layer's own validation gates."""
    schema_provider = get_schema_provider("auto")
    result = _verify_delta_replay(
        _splitsigmas_ui(6),
        _splitsigmas_ui(8),
        [_set_field_op("47", "widget_0", "8")],
        schema_provider=schema_provider,
    )
    assert result["verified"] is False


def test_verify_is_deterministic_pure_function_of_contents() -> None:
    """(R3) same inputs, same verdict — no environment dependence."""
    schema_provider = get_schema_provider("auto")
    args = (
        _ksampler_ui(20),
        _ksampler_ui(30),
        [_set_field_op("sampler", "steps", "30")],
    )
    first = _verify_delta_replay(*args, schema_provider=schema_provider)
    second = _verify_delta_replay(*args, schema_provider=schema_provider)
    assert first == second

    fp = _op_fingerprint(parse_edit_delta([_set_field_op("n", "steps", "30")])[0])
    assert fp == _op_fingerprint(parse_edit_delta([_set_field_op("n", "steps", "30")])[0])


def test_fingerprint_mapping_key_order_irrelevant() -> None:
    """Field-map ordering never changes the fingerprint (sort_keys parity)."""
    one = {"op": "add_node", "class_type": "X", "fields": {"a": 1, "b": 2}, "inputs": {}}
    two = {"op": "add_node", "class_type": "X", "fields": {"b": 2, "a": 1}, "inputs": {}}
    assert _op_fingerprint(one) == _op_fingerprint(two)
