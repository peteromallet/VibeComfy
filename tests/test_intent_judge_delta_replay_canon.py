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
import re
from collections.abc import Mapping
from decimal import Decimal
from tests.live_agentic_harness.intent_judge import (
    _canonical_edit_value,
    _canonicalize_op_field_paths,
    _field_canon_context,
    _op_fingerprint,
    _resolve_field_slot,
    _to_workflow_ir,
    _verify_delta_replay,
)

from vibecomfy.porting.edit._diff import diff

from vibecomfy.porting.edit.ops import parse_edit_delta
from vibecomfy.schema import get_schema_provider


def _ksampler_ui(steps: object, *, uid: str = "sampler") -> dict:
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


# ── P8-R2: fingerprint equality ⟺ diff-layer value equality ────────────────


_CANON_INT_TEXT = re.compile(r"-?[0-9]+")


def _numeric_identity(value: object) -> Decimal | None:
    """Decimal identity for exactly the R1 collapse set — numeric-tower
    members and canonical integer text — else ``None``."""
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, (int, float)):
        return Decimal(value)
    if isinstance(value, str) and _CANON_INT_TEXT.fullmatch(value) and str(int(value)) == value:
        return Decimal(int(value))
    return None


def _diff_layer_equal(a: object, b: object) -> bool:
    """The equality diff() applies to stored IR values, recursively.

    ``vibecomfy.porting.edit._diff`` compares pre/post widget/input maps
    with plain Python ``!=`` (``pre_widgets.get(name) != post_widgets.get(name)``)
    at every level — key sets must match exactly, ``None`` entries are real
    distinctions.  On top of plain ``==`` sits exactly one documented
    carve-out, pinned by the R1 tests above and applied at every depth:
    int/float/bool and canonical integer text are spellings of one widget
    number (a claimed Δ arrives as JSON where the same value may be spelled
    ``30``, ``30.0``, or ``"30"``, nested in fields just like at the top).
    """
    na, nb = _numeric_identity(a), _numeric_identity(b)
    if na is not None and nb is not None:
        return na == nb
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        return set(a) == set(b) and all(_diff_layer_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(
            _diff_layer_equal(x, y) for x, y in zip(a, b)
        )
    return a == b


def test_nested_none_and_value_shapes_never_collapse() -> None:
    """(P8-R2 must a) These pairs fingerprinted EQUAL under None elision even
    though diff() sees them unequal; every distinction is preserved now."""
    collisions = [
        ({"y": None}, {}),  # None-valued entry vs absent key
        ({"y": None}, {"z": None}),  # two distinct None-only maps
        ({"x": {"y": None}}, {"x": {}}),  # nested None vs nested absence
        ({"x": {"y": None}}, {"x": {"z": None}}),  # distinct nested keys
        ({"x": {"y": None}}, {"x": {"y": False}}),  # nested None vs falsy value
        ([{"y": None}], []),  # None inside arrays too
        ({}, []),  # empty map vs empty array
        ("None", None),  # text vs absence sentinel
    ]
    for a, b in collisions:
        assert _canonical_edit_value(a) != _canonical_edit_value(b), (a, b)
        fa = _op_fingerprint(parse_edit_delta([_set_field_op("n", "steps", a)])[0])
        fb = _op_fingerprint(parse_edit_delta([_set_field_op("n", "steps", b)])[0])
        assert fa != fb, (a, b)

    # No overcorrection: identical shapes still share a projection/fingerprint.
    assert _canonical_edit_value({"x": {"y": None}}) == _canonical_edit_value(
        {"x": {"y": None}}
    )
    same = parse_edit_delta([_set_field_op("n", "steps", {"x": {"y": None}})])[0]
    assert _op_fingerprint(same) == _op_fingerprint(same)


def test_delta_masked_by_none_elision_is_rejected_end_to_end() -> None:
    """(P8-R2 must a, end-to-end) post stores {'y': None}; a claimed Δ of {}
    used to verify True because elision collapsed both fingerprints AND the
    leftover spelling filter. Both directions are rejected now."""
    schema_provider = get_schema_provider("auto")
    pre = _ksampler_ui(20)
    for post_value, claimed_value in (({"y": None}, {}), ({}, {"y": None})):
        result = _verify_delta_replay(
            pre,
            _ksampler_ui(post_value),
            [_set_field_op("sampler", "steps", claimed_value)],
            schema_provider=schema_provider,
        )
        assert result["verified"] is False, (post_value, claimed_value, result)

    # Control: the honest nested claim still verifies.
    honest = _verify_delta_replay(
        pre,
        _ksampler_ui({"y": None}),
        [_set_field_op("sampler", "steps", {"y": None})],
        schema_provider=schema_provider,
    )
    assert honest == {"verified": True, "checked": 1, "mismatches": []}


_IFF_BATTERY = [
    # spellings of one number (R1 collapse set)
    30, 30.0, "30",
    -2, "-2",
    0, False,
    True, 1, "1",
    # numerics that must stay distinct
    31, 30.5, "31", -1,
    12345678901234567890,  # exactness: no float rounding in the projection
    # non-canonical text stays text
    "030", "1.50", "dpm_2", "",
    # absence / falsy shapes
    None,
    # nested containers
    {}, [], {"y": None}, {"y": {}}, {"y": 30}, {"y": "30"}, {"z": None},
    {"x": {"y": None}}, {"x": {}},
    [1, 2], [2, 1], [1, "2"], [{"a": 1}],
]


def test_fingerprint_equality_iff_diff_layer_equality() -> None:
    """(P8-R2 must b) For EVERY ordered battery pair — both directions —
    fingerprints are equal exactly when the diff layer sees the underlying
    workflow values as equal (plain == over stored IR, plus the pinned R1
    numeric-spelling collapse)."""
    fps = [
        _op_fingerprint(parse_edit_delta([_set_field_op("n", "steps", v)])[0])
        for v in _IFF_BATTERY
    ]
    for i, a in enumerate(_IFF_BATTERY):
        for j, b in enumerate(_IFF_BATTERY):
            expected = _diff_layer_equal(a, b)
            assert (fps[i] == fps[j]) == expected, (i, a, j, b, fps[i], fps[j])


def _empty_latent_ui(batch_size: object, *, uid: str = "9") -> dict:
    """Schema-rostered node whose stored IR keeps positional widget keys.

    ``EmptyLatentImage`` resolves through the widget name authority to
    ``('width', 'height', 'batch_size')`` while the ingest stores its values
    under ``widget_0..2`` — exactly the claimed-vs-actual spelling split the
    R2-SPOT-FORENSIC verdict-(a) leg exhibited (claimed ``batch_size`` vs
    actual ``widget_2``, same node, same value).
    """
    return {
        "nodes": [
            {
                "id": uid,
                "type": "EmptyLatentImage",
                "mode": 0,
                "properties": {"vibecomfy_uid": uid},
                "widgets_values": [512, 512, batch_size],
            }
        ],
        "links": [],
    }


def test_widget_n_and_named_slot_spellings_are_one_statement() -> None:
    """(g) Same slot spelled ``widget_N`` vs schema-proven name, same node and
    value → one edit statement.

    End-to-end in the admitted direction: the accepted Δ spells the roster
    name while the actual diff spells the stored positional key (the forensic
    verdict-a shape) — verified True.  The mirror direction is decided at the
    fingerprint-law layer: after name-authority resolution a claimed
    ``widget_N`` op and the actual schema-named op share one fingerprint.
    End-to-end, a raw positional claim stays gated by the layer's own
    no-positional-writes rule (pinned by
    ``test_positional_alias_claims_stay_rejected``); canonicalization never
    bypasses that gate.
    """
    schema_provider = get_schema_provider("auto")
    result = _verify_delta_replay(
        _empty_latent_ui(16),
        _empty_latent_ui(8),
        [_set_field_op("9", "batch_size", 8)],
        schema_provider=schema_provider,
    )
    assert result == {"verified": True, "checked": 1, "mismatches": []}

    # Mirror direction: claimed widget_N vs actual schema-proven name.
    pre_wf = _to_workflow_ir(_empty_latent_ui(16), schema_provider=schema_provider)
    post_wf = _to_workflow_ir(_empty_latent_ui(8), schema_provider=schema_provider)
    ctx = _field_canon_context(pre_wf, post_wf, schema_provider=schema_provider)
    claimed = parse_edit_delta([_set_field_op("9", "widget_2", 8)])[0]
    actual = next(
        op
        for op in diff(pre_wf, post_wf)
        if getattr(getattr(op, "target", None), "field_path", "") == "widget_2"
    )
    assert _op_fingerprint(_canonicalize_op_field_paths(claimed, ctx)) == _op_fingerprint(
        _canonicalize_op_field_paths(actual, ctx)
    )
    # The resolution itself is symmetric: both spellings bind to slot 2.
    assert _resolve_field_slot("9", "widget_2", ctx) == ("slot", "9", 2)
    assert _resolve_field_slot("9", "batch_size", ctx) == ("slot", "9", 2)


def test_positional_named_pair_with_different_value_still_mismatches() -> None:
    """(h) Same shape as (g) but a genuinely different target value never
    passes — the spelling bridge must not carry value divergence."""
    schema_provider = get_schema_provider("auto")
    result = _verify_delta_replay(
        _empty_latent_ui(16),
        _empty_latent_ui(8),
        [_set_field_op("9", "batch_size", 9)],
        schema_provider=schema_provider,
    )
    assert result["verified"] is False
    assert any(
        "not what actually changed" in m for m in result["mismatches"]
    ), result["mismatches"]

    # And across the bridge: claimed widget_N=9 vs actual named-slot value 8
    # fingerprints APART — only node/slot identity is canonicalized.
    pre_wf = _to_workflow_ir(_empty_latent_ui(16), schema_provider=schema_provider)
    post_wf = _to_workflow_ir(_empty_latent_ui(8), schema_provider=schema_provider)
    ctx = _field_canon_context(pre_wf, post_wf, schema_provider=schema_provider)
    claimed = parse_edit_delta([_set_field_op("9", "widget_2", 9)])[0]
    actual = next(
        op
        for op in diff(pre_wf, post_wf)
        if getattr(getattr(op, "target", None), "field_path", "") == "widget_2"
    )
    assert _op_fingerprint(_canonicalize_op_field_paths(claimed, ctx)) != _op_fingerprint(
        _canonicalize_op_field_paths(actual, ctx)
    )
    # Wrong slot under the other spelling stays apart too (height ≠ batch_size).
    wrong_slot = parse_edit_delta([_set_field_op("9", "widget_1", 8)])[0]
    assert _op_fingerprint(_canonicalize_op_field_paths(wrong_slot, ctx)) != _op_fingerprint(
        _canonicalize_op_field_paths(actual, ctx)
    )


def test_unresolved_path_fallback_keeps_both_sides_symmetric() -> None:
    """(i) Unresolvable paths fall back to the RAW string on BOTH sides —
    no invented equality, no lost equality."""
    schema_provider = get_schema_provider("auto")
    pre_wf = _to_workflow_ir(_empty_latent_ui(16), schema_provider=schema_provider)
    post_wf = _to_workflow_ir(_empty_latent_ui(8), schema_provider=schema_provider)
    ctx = _field_canon_context(pre_wf, post_wf, schema_provider=schema_provider)

    # Resolution failures: unknown node, out-of-range position, empty path.
    assert _resolve_field_slot("ghost", "widget_0", ctx) is None
    assert _resolve_field_slot("9", "widget_7", ctx) is None
    assert _resolve_field_slot("9", "", ctx) is None

    def fp(uid: str, field: str, value: object = 8):
        return _op_fingerprint(
            _canonicalize_op_field_paths(
                parse_edit_delta([_set_field_op(uid, field, value)])[0], ctx
            )
        )

    # Raw fallback compares raw strings: identical raws stay equal, distinct
    # raws stay unequal — exactly the pre-canonicalization relation.
    assert fp("ghost", "widget_0") == fp("ghost", "widget_0")
    assert fp("ghost", "widget_0") != fp("ghost", "steps")
    assert fp("9", "widget_7") == fp("9", "widget_7")
    assert fp("9", "widget_7") != fp("9", "batch_size")

    # End-to-end: the schema-unresolved positional claim stays rejected by the
    # apply boundary's own validation gate, NOT by fingerprint asymmetry — its
    # fingerprint against the identically-spelled actual change is equal.
    result = _verify_delta_replay(
        _splitsigmas_ui(6),
        _splitsigmas_ui(8),
        [_set_field_op("47", "widget_0", 8)],
        schema_provider=schema_provider,
    )
    assert result["verified"] is False
    sig_pre = _to_workflow_ir(_splitsigmas_ui(6), schema_provider=schema_provider)
    sig_post = _to_workflow_ir(_splitsigmas_ui(8), schema_provider=schema_provider)
    sig_ctx = _field_canon_context(sig_pre, sig_post, schema_provider=schema_provider)
    claimed = parse_edit_delta([_set_field_op("47", "widget_0", 8)])[0]
    actual = next(
        op
        for op in diff(sig_pre, sig_post)
        if getattr(getattr(op, "target", None), "uid", "") == "47"
    )
    assert _op_fingerprint(_canonicalize_op_field_paths(claimed, sig_ctx)) == _op_fingerprint(
        _canonicalize_op_field_paths(actual, sig_ctx)
    )
