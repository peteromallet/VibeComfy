from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.mutation_materialization_v1 import (
    MATERIALIZATION_KINDS,
    MUTATION_MATERIALIZATION_CONTRACT_V1,
    MUTATION_MATERIALIZATION_WIRE_VERSION,
    MutationMaterializationError,
    assert_mutation_materialization_envelope,
    compute_mutation_materialization_digest,
    build_mutation_materialization_v1,
    normalize_mutation_materialization_v1,
)


def test_builder_binds_every_add_node_and_ignores_other_ops() -> None:
    ops = [
        {"op": "set_node_field", "target": ["", "n1", "steps"], "value": 30},
        {"op": "add_node", "scope_path": "", "uid": "n2", "node_id": "2", "class_type": "SaveImage", "fields": {}, "inputs": {}},
        {"op": "add_node", "scope_path": "", "uid": "n3", "node_id": "3", "class_type": "PreviewImage", "fields": {}, "inputs": {}},
    ]

    envelope = build_mutation_materialization_v1(ops)

    assert envelope["entries"] == [
        {"source_op_index": 1, "kind": "add_node"},
        {"source_op_index": 2, "kind": "add_node"},
    ]
    assert_mutation_materialization_envelope(envelope, accompanying_ops=ops)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "agent_edit"
    / "mutation_materialization_golden_v1.json"
)
GOLDEN = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _envelope(entries, accompanying_ops, *, digest=None):
    return {
        "contract_version": MUTATION_MATERIALIZATION_CONTRACT_V1,
        "wire_version": MUTATION_MATERIALIZATION_WIRE_VERSION,
        "entries": entries,
        "digest": digest
        or compute_mutation_materialization_digest(entries, accompanying_ops),
    }


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=[c["id"] for c in GOLDEN["cases"]])
def test_materialization_golden_positive_cases(case):
    normalized = normalize_mutation_materialization_v1(
        _envelope(case["entries"], case["accompanying_ops"]),
        accompanying_ops=case["accompanying_ops"],
    )
    assert normalized["digest"] == case["expected_digest"]
    assert (
        compute_mutation_materialization_digest(case["entries"], case["accompanying_ops"])
        == case["expected_digest"]
    )


def test_materialization_kind_singleton():
    assert MATERIALIZATION_KINDS == ("add_node",)
    assert MUTATION_MATERIALIZATION_CONTRACT_V1 == "mutation_materialization_v1"
    assert MUTATION_MATERIALIZATION_WIRE_VERSION == "1.0.0"


def test_materialization_numeric_normalization_parity():
    cases = {c["id"]: c for c in GOLDEN["parity_cases"]}
    float_negzero = cases["numeric_normalize_float_negzero"]["expected_digest"]
    plain_int = cases["numeric_normalize_plain_int"]["expected_digest"]
    assert float_negzero == plain_int  # [1.0,-0.0] == [1,0]
    for case in GOLDEN["parity_cases"]:
        assert (
            compute_mutation_materialization_digest(case["entries"], case["accompanying_ops"])
            == case["expected_digest"]
        )


def test_materialization_rebind_detection():
    case = GOLDEN["rebind_case"]
    # Same valid entries + a DIFFERENT accompanying ops array (add_node at the
    # same index but a different uid) must fail with the bound-ops diagnostic.
    envelope = _envelope(case["entries"], case["accompanying_ops_original"])
    with pytest.raises(MutationMaterializationError) as caught:
        assert_mutation_materialization_envelope(
            envelope, accompanying_ops=case["accompanying_ops_rebind"]
        )
    assert caught.value.code == "mutation_materialization_digest_mismatch"
    assert getattr(caught.value, "detail", {}).get("accompanying_ops_bound") is True


def test_materialization_exec_dynamic_io_widgets_object():
    case = next(c for c in GOLDEN["cases"] if c["id"] == "exec_widgets_object_dynamic_io")
    # vibecomfy.exec may carry widgets_values as a JSON object; the io key is
    # passed through untouched (non-authoritative).
    normalized = assert_mutation_materialization_envelope(
        _envelope(case["entries"], case["accompanying_ops"]),
        accompanying_ops=case["accompanying_ops"],
    )
    assert normalized["entries"][0]["widgets_values"]["io"] == {"rebuilt": True}


@pytest.mark.parametrize(
    "case", GOLDEN["negative_cases"], ids=[c["id"] for c in GOLDEN["negative_cases"]]
)
def test_materialization_golden_negative_cases_fail_closed(case):
    # Structural failures reject before the digest is consulted; use a uniform
    # placeholder so we never compute a digest over malformed entries outside
    # the assertion boundary (the tampered-digest case carries its own value).
    digest = case.get("envelope_digest", "0" * 64)
    envelope = _envelope(case["entries"], case["accompanying_ops"], digest=digest)
    with pytest.raises(MutationMaterializationError) as caught:
        assert_mutation_materialization_envelope(
            envelope, accompanying_ops=case["accompanying_ops"]
        )
    assert caught.value.code == case["expected_code"]


def test_materialization_unknown_contract_version_fails_closed():
    env = _envelope(
        [{"source_op_index": 0, "kind": "add_node"}], GOLDEN["add_node_template"]
    )
    env["contract_version"] = "mutation_materialization_v9"
    with pytest.raises(MutationMaterializationError) as caught:
        assert_mutation_materialization_envelope(
            env, accompanying_ops=[GOLDEN["add_node_template"]]
        )
    assert caught.value.code == "unknown_contract"


def test_materialization_numeric_edge_cases_fail_closed():
    """Cross-language numeric-edge rejection (§0.3.1).

    NaN / Infinity are not JSON-portable and remain Python-inline-only; boolean
    and unsafe-integer rejections are now symmetric with the JS mirror.
    """
    add = GOLDEN["add_node_template"]

    def _expect(entries, code):
        env = _envelope(entries, [add], digest="0" * 64)
        with pytest.raises(MutationMaterializationError) as caught:
            assert_mutation_materialization_envelope(env, accompanying_ops=[add])
        assert caught.value.code == code

    geo = lambda x: [{"source_op_index": 0, "kind": "add_node", "pos": [x, 2]}]

    # Non-finite (Python-only inline: NaN/Infinity are not JSON-portable).
    _expect(geo(float("nan")), "non_finite_materialization")

    # Boolean in geometry — cross-language non_canonical_number.
    _expect(geo(True), "non_canonical_number")

    # Unsafe integers — cross-language non_canonical_number.
    _expect(geo(2 ** 53), "non_canonical_number")
    _expect(geo(-(2 ** 53)), "non_canonical_number")
    _expect(geo(2 ** 60), "non_canonical_number")


def test_materialization_safe_integer_boundary_remains_canonical():
    """2^53 - 1 must be accepted by both languages with an identical digest
    (golden parity case ``numeric_normalize_safe_integer_boundary``)."""
    add = GOLDEN["add_node_template"]
    entries = [{"source_op_index": 0, "kind": "add_node", "pos": [2 ** 53 - 1, 0]}]
    digest = compute_mutation_materialization_digest(entries, [add])
    cases = {c["id"]: c for c in GOLDEN["parity_cases"]}
    assert (
        digest
        == cases["numeric_normalize_safe_integer_boundary"]["expected_digest"]
    )
