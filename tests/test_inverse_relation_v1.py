"""Inverse-relation parity tests (§3.2 / §5.1).

Both Python and JS load the same golden fixture and assert every positive case
passes and every negative case throws the exact expected diagnostic code.
Covers all six delta op classes plus all four layout op classes, plus every
§3.2 failure mode.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.projection_registry_v1 import (
    ContractError,
    _assert_inverse_relation,
    _hash,
    _restoration,
    forward_operation_digest,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/agent_edit/inverse_relation_golden_v1.json").read_text()
)


@pytest.mark.parametrize(
    "case",
    FIXTURE["structural_cases"] + FIXTURE["layout_cases"],
    ids=lambda case: case["id"],
)
def test_inverse_relation_golden_cases(case):
    if case.get("expected") == "ok":
        _assert_inverse_relation(case["forward_ops"], case["inverse_ops"], case["family"])
    else:
        with pytest.raises(ContractError) as caught:
            _assert_inverse_relation(case["forward_ops"], case["inverse_ops"], case["family"])
        assert caught.value.code == case["expected_code"], (
            f"{case['id']}: expected {case['expected_code']}, got {caught.value.code}"
        )


def test_empty_forward_and_inverse_is_valid():
    _assert_inverse_relation([], [], "structural")


def test_empty_inverse_with_forward_is_unrelated():
    with pytest.raises(ContractError) as caught:
        _assert_inverse_relation(
            [{"op": "set_node_field", "target": ["", "uid-1", "f"], "value": "n"}],
            [],
            "structural",
        )
    assert caught.value.code == "inverse_unrelated"


def test_unrelated_inverse_shares_no_identity():
    forward = [{"op": "set_node_field", "target": ["", "uid-A", "f"], "value": "n"}]
    inverse = [{"op": "set_node_field", "target": ["", "uid-B", "f"], "value": "o"}]
    with pytest.raises(ContractError) as caught:
        _assert_inverse_relation(forward, inverse, "structural")
    assert caught.value.code == "inverse_identity_unbound"


_REWIRE_FORWARD = [
    {"op": "remove_link", "to": ["", "dst-1", "images"]},
    {"op": "upsert_link", "from": ["", "src-new", "IMAGE"], "to": ["", "dst-1", "images"]},
]
_REWIRE_INVERSE = [
    {"op": "remove_link", "to": ["", "dst-1", "images"]},
    {"op": "upsert_link", "from": ["", "src-old", "IMAGE"], "to": ["", "dst-1", "images"]},
]
_REWIRE_WITNESSES = [
    {"from": ["", "src-old", "IMAGE"], "to": ["", "dst-1", "images"]},
]


def _v2_restoration(*, forward_ops=_REWIRE_FORWARD, inverse_ops=_REWIRE_INVERSE,
                    witnesses=_REWIRE_WITNESSES, forward_digest=None):
    payload = {
        "ops": inverse_ops,
        "forward_operation_digest": forward_digest or forward_operation_digest(forward_ops),
        "prior_link_witnesses": witnesses,
    }
    return {
        "contract_version": "inverse_delta_v2",
        "payload": payload,
        "digest": _hash({"contract_version": "inverse_delta_v2", "payload": payload}),
    }


def test_inverse_delta_v2_binds_exact_rewire_prior_state():
    assert forward_operation_digest(_REWIRE_FORWARD) == "65f6700bb89c271b2a454a08abd2088c247f927a631dbaca63bb843c97d01e0d"
    _restoration(
        _v2_restoration(), family="structural", forward_ops=_REWIRE_FORWARD
    )


def test_inverse_delta_v2_requires_exact_remove_link_witness_coverage():
    with pytest.raises(ContractError) as caught:
        _restoration(
            _v2_restoration(witnesses=[]),
            family="structural",
            forward_ops=_REWIRE_FORWARD,
        )
    assert caught.value.code == "inverse_missing_prior_state"


def test_inverse_delta_v2_rejects_wrong_prior_source():
    wrong = [{"from": ["", "wrong", "IMAGE"], "to": ["", "dst-1", "images"]}]
    with pytest.raises(ContractError) as caught:
        _restoration(
            _v2_restoration(witnesses=wrong),
            family="structural",
            forward_ops=_REWIRE_FORWARD,
        )
    assert caught.value.code == "inverse_missing_prior_state"


def test_inverse_delta_v2_rejects_forward_digest_transplant():
    transplanted = forward_operation_digest([
        {"op": "remove_link", "to": ["", "other-dst", "images"]},
    ])
    with pytest.raises(ContractError) as caught:
        _restoration(
            _v2_restoration(forward_digest=transplanted),
            family="structural",
            forward_ops=_REWIRE_FORWARD,
        )
    assert caught.value.code == "forward_operation_digest_mismatch"


def test_inverse_delta_v2_outer_digest_binds_witness_payload():
    restoration = _v2_restoration()
    restoration["payload"]["prior_link_witnesses"] = []
    with pytest.raises(ContractError) as caught:
        _restoration(restoration, family="structural", forward_ops=_REWIRE_FORWARD)
    assert caught.value.code == "restoration_digest_mismatch"
