from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.layout_operation_v1 import (
    LAYOUT_OPERATION_CONTRACT_V1,
    LAYOUT_OPERATION_OP_NAMES,
    LAYOUT_OPERATION_WIRE_VERSION,
    LayoutOperationError,
    assert_layout_operation_envelope,
    compute_layout_operation_digest,
    normalize_layout_operation_v1,
)
from vibecomfy.comfy_nodes.agent.projection_registry_v1 import (
    structural_graph_hash_compat,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "agent_edit"
    / "layout_operation_golden_v1.json"
)
GOLDEN = json.loads(FIXTURE.read_text(encoding="utf-8"))
A66422E6 = (
    Path(__file__).parent / "fixtures" / "agent_edit" / "a66422e6_layout_regression.json"
)


def _envelope(ops, **overrides):
    envelope = {
        "contract_version": LAYOUT_OPERATION_CONTRACT_V1,
        "wire_version": LAYOUT_OPERATION_WIRE_VERSION,
        "ops": ops,
    }
    if "digest" in overrides:
        envelope["digest"] = overrides.pop("digest")
    else:
        envelope["digest"] = compute_layout_operation_digest(ops)
    envelope.update(overrides)
    return envelope


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=[c["id"] for c in GOLDEN["cases"]])
def test_layout_golden_positive_cases(case):
    normalized = normalize_layout_operation_v1(_envelope(case["ops"]))
    assert normalized["digest"] == case["expected_digest"]
    # The recomputed digest must also equal computeLayoutOperationDigest (parity
    # entrypoint used by the JS mirror).
    assert compute_layout_operation_digest(case["ops"]) == case["expected_digest"]
    if "expected_envelope" in case:
        assert normalized == case["expected_envelope"]


def test_layout_op_names_are_exactly_four():
    assert LAYOUT_OPERATION_OP_NAMES == (
        "set_node_geometry",
        "add_group",
        "set_group_geometry",
        "remove_group",
    )
    assert LAYOUT_OPERATION_CONTRACT_V1 == "layout_operation_v1"
    assert LAYOUT_OPERATION_WIRE_VERSION == "1.0.0"


def test_layout_numeric_normalization_parity():
    """Integer-valued floats, -0.0, and exponents normalise to the JS spelling."""
    cases = {c["id"]: c for c in GOLDEN["parity_cases"]}
    float_negzero = cases["numeric_normalize_float_and_negzero"]["expected_digest"]
    exponent = cases["numeric_normalize_exponent"]["expected_digest"]
    plain_int = cases["numeric_normalize_plain_int"]["expected_digest"]
    # [1.0, -0.0] and [1, 0] must collapse to the SAME canonical spelling.
    assert float_negzero == plain_int
    # [1e2, 200] is a distinct geometry, not equal to [1, 0].
    assert exponent != plain_int
    # Each parity digest is independently recomputable from the raw ops.
    for case in GOLDEN["parity_cases"]:
        assert compute_layout_operation_digest(case["ops"]) == case["expected_digest"]


def test_layout_a66422e6_regression_anchor_three_separate_digests():
    raw = A66422E6.read_bytes()
    anchor = GOLDEN["a66422e6_anchor"]
    # (1) Fixture-integrity digest (informational, not a contract digest).
    integrity = anchor["fixture_integrity_raw_file"]
    assert integrity["domain"] == "fixture_integrity_raw_file"
    assert integrity["informational"] is True
    assert hashlib.sha256(raw).hexdigest() == integrity["sha256"]
    assert len(raw) == integrity["byte_length"]
    # (2) Structural-witness digest (cross-language parity sentinel).
    fixture = json.loads(raw)
    assert (
        structural_graph_hash_compat(fixture["original"])
        == anchor["structural_witness_v1"]["expected_digest"]
    )
    assert (
        anchor["structural_witness_v1"]["domain"] == "structural_witness_v1"
    )
    # (3) Layout-operation digest: the derived candidate-groups case is a
    # separate golden entry with its own domain-labelled digest.
    derived = next(
        c for c in GOLDEN["cases"] if c["id"] == "a66422e6-derived-candidate-groups"
    )
    assert compute_layout_operation_digest(derived["ops"]) == derived["expected_digest"]
    assert derived["expected_digest"] != integrity["sha256"]
    assert derived["expected_digest"] != anchor["structural_witness_v1"]["expected_digest"]


@pytest.mark.parametrize(
    "case", GOLDEN["negative_cases"], ids=[c["id"] for c in GOLDEN["negative_cases"]]
)
def test_layout_golden_negative_cases_fail_closed(case):
    with pytest.raises(LayoutOperationError) as caught:
        if "envelope" in case:
            envelope = dict(case["envelope"])
        else:
            # Op-level failures reject before the digest is ever consulted, so a
            # placeholder digest is sufficient and avoids computing a digest over
            # malformed ops outside the assertion boundary.
            envelope = _envelope(case["ops"], digest="0" * 64)
        assert_layout_operation_envelope(envelope)
    assert caught.value.code == case["expected_code"]


def test_layout_unknown_contract_version_fails_closed():
    envelope = _envelope([])
    envelope["contract_version"] = "layout_operation_v9"
    with pytest.raises(LayoutOperationError) as caught:
        assert_layout_operation_envelope(envelope)
    assert caught.value.code == "unknown_contract"


def test_layout_duplicate_identity_within_class_fails_closed():
    ops = [
        {"op": "set_node_geometry", "uid": "dup", "pos": [1, 2]},
        {"op": "set_node_geometry", "uid": "dup", "pos": [3, 4]},
    ]
    with pytest.raises(LayoutOperationError) as caught:
        compute_layout_operation_digest(ops)
    assert caught.value.code == "duplicate_identity"


def test_layout_cross_class_same_id_is_allowed():
    ops = [
        {"op": "add_group", "id": "g", "bounding": [1, 2, 3, 4], "title": "T", "color": None},
        {"op": "set_group_geometry", "id": "g", "title": "T2"},
        {"op": "remove_group", "id": "g"},
    ]
    # No exception: add -> configure -> remove on the same id is a legal sequence.
    assert compute_layout_operation_digest(ops)


def test_layout_numeric_edge_cases_fail_closed():
    """Cross-language numeric-edge rejection (§0.3.1).

    NaN / Infinity are not JSON-portable and remain Python-inline-only; boolean
    and unsafe-integer rejections are now symmetric with the JS mirror.  Every
    case below must fail with ``non_canonical_number`` (boolean / unsafe int) or
    ``non_finite_geometry`` (NaN / ±Infinity) — matching the JS mirror's
    diagnostic exactly so the two languages never diverge on a numeric edge.
    """

    def _expect(ops, code):
        envelope = _envelope(ops, digest="0" * 64)
        with pytest.raises(LayoutOperationError) as caught:
            assert_layout_operation_envelope(envelope)
        assert caught.value.code == code

    geo = lambda x: [{"op": "set_node_geometry", "uid": "n", "pos": [x, 2]}]

    # Non-finite (Python-only inline: NaN/Infinity are not JSON-portable).
    _expect(geo(float("nan")), "non_finite_geometry")
    _expect(geo(float("inf")), "non_finite_geometry")

    # Boolean in geometry — cross-language non_canonical_number.
    _expect(geo(True), "non_canonical_number")

    # Unsafe integers — cross-language non_canonical_number.
    # +2^53 and -2^53 are exactly representable doubles but exceed ±(2^53-1).
    _expect(geo(2 ** 53), "non_canonical_number")
    _expect(geo(-(2 ** 53)), "non_canonical_number")
    # 2^60 is a native Python int; Python serialises the exact decimal
    # "...476" while JS emits the shortest round-trippable "...500".
    _expect(geo(2 ** 60), "non_canonical_number")


def test_layout_safe_integer_boundary_remains_canonical():
    """2^53 - 1 (Number.MAX_SAFE_INTEGER) is the largest safe int and must be
    accepted by both languages with an identical digest (golden parity case
    ``numeric_normalize_safe_integer_boundary``)."""
    ops = [{"op": "set_node_geometry", "uid": "n", "pos": [2 ** 53 - 1, 0]}]
    digest = compute_layout_operation_digest(ops)
    cases = {c["id"]: c for c in GOLDEN["parity_cases"]}
    assert digest == cases["numeric_normalize_safe_integer_boundary"]["expected_digest"]
