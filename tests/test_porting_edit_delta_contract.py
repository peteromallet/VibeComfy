from __future__ import annotations

import pytest

from vibecomfy.porting.edit.ops import (
    DELTA_DIAGNOSTIC_LEGACY_SHAPE,
    DELTA_DIAGNOSTIC_MALFORMED,
    DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
    DELTA_SCHEMA_VERSION,
    EditOpParseError,
    canonical_op_to_dict,
    ensure_root_scoped_delta_envelope,
    normalize_delta_envelope,
    op_to_dict,
    parse_edit_delta,
)


CANONICAL_OP_CASES = (
    {
        "op": "set_node_field",
        "target": ["", "seed-node", "inputs.seed"],
        "value": 7,
    },
    {
        "op": "set_mode",
        "target": ["", "mute-node"],
        "mode": 4,
    },
    {
        "op": "add_node",
        "scope_path": "",
        "uid": "new-uid",
        "node_id": "9001",
        "class_type": "PreviewImage",
        "fields": {"filename_prefix": "after"},
        "inputs": {"images": ["", "seed-node", "IMAGE"]},
    },
    {
        "op": "upsert_link",
        "from": ["", "seed-node", "IMAGE"],
        "to": ["", "preview-node", "images"],
    },
    {
        "op": "remove_node",
        "target": ["", "old-node"],
    },
    {
        "op": "remove_link",
        "to": ["", "preview-node", "images"],
    },
)


@pytest.mark.parametrize(
    "payload",
    CANONICAL_OP_CASES,
    ids=[case["op"] for case in CANONICAL_OP_CASES],
)
def test_canonical_delta_op_roundtrips_through_parse_normalize_and_serialize(
    payload: dict[str, object],
) -> None:
    parsed_ops = parse_edit_delta([payload])
    assert len(parsed_ops) == 1

    parsed_op = parsed_ops[0]
    assert op_to_dict(parsed_op) == payload
    assert canonical_op_to_dict(parsed_op) == payload

    envelope = normalize_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [payload],
        }
    )
    assert envelope.to_dict() == {
        "schema_version": DELTA_SCHEMA_VERSION,
        "ops": [payload],
    }

    reparsed = normalize_delta_envelope(envelope.to_dict())
    assert tuple(canonical_op_to_dict(op) for op in reparsed.ops) == (payload,)
    assert reparsed.to_dict() == envelope.to_dict()


def test_canonical_delta_envelope_roundtrips_all_six_ops_together() -> None:
    payload = {
        "schema_version": DELTA_SCHEMA_VERSION,
        "ops": list(CANONICAL_OP_CASES),
    }

    envelope = normalize_delta_envelope(payload)
    reparsed = normalize_delta_envelope(envelope.to_dict())

    assert tuple(canonical_op_to_dict(op) for op in envelope.ops) == CANONICAL_OP_CASES
    assert tuple(canonical_op_to_dict(op) for op in reparsed.ops) == CANONICAL_OP_CASES
    assert reparsed.to_dict() == payload


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("uid", "Canonical add_node ops must include `uid`."),
        ("node_id", "Canonical add_node ops must include `node_id`."),
    ],
)
def test_normalize_delta_envelope_rejects_add_node_missing_required_identity(
    field: str,
    message: str,
) -> None:
    add_node = dict(CANONICAL_OP_CASES[2])
    del add_node[field]

    with pytest.raises(EditOpParseError, match=message) as exc_info:
        normalize_delta_envelope(
            {
                "schema_version": DELTA_SCHEMA_VERSION,
                "ops": [add_node],
            }
        )

    assert exc_info.value.code == DELTA_DIAGNOSTIC_MALFORMED
    assert exc_info.value.detail == {"op": "add_node", "field": field}


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (
            [{"op": "set_node_field", "target": ["", "only-two"], "value": 1}],
            r"target must be a list of length 3",
        ),
        (
            [{"op": "remove_node", "target": "u1"}],
            r"target must be a list of length 2",
        ),
        (
            [{"op": "upsert_link", "from": ["", "u1"], "to": ["", "u2", "images"]}],
            r"from must be a list of length 3",
        ),
        (
            [{"op": "remove_link", "to": ["", "u2"]}],
            r"to must be a list of length 3",
        ),
    ],
)
def test_parse_edit_delta_rejects_bad_target_and_source_shapes(
    payload: list[dict[str, object]],
    match: str,
) -> None:
    with pytest.raises(EditOpParseError, match=match) as exc_info:
        parse_edit_delta(payload)

    assert exc_info.value.code == DELTA_DIAGNOSTIC_MALFORMED


@pytest.mark.parametrize(
    "payload",
    [
        [{"op": "rename_everything", "target": ["", "u1"], "value": "x"}],
        [{"op": "noop"}],
        {"schema_version": DELTA_SCHEMA_VERSION, "ops": [{"op": "rename_everything"}]},
    ],
)
def test_delta_contract_rejects_unknown_ops(payload: object) -> None:
    with pytest.raises(EditOpParseError, match="Unsupported edit op") as exc_info:
        if isinstance(payload, dict):
            normalize_delta_envelope(payload)
        else:
            parse_edit_delta(payload)

    assert exc_info.value.code == DELTA_DIAGNOSTIC_MALFORMED


@pytest.mark.parametrize(
    ("payload", "expected_keys"),
    [
        ({"delta_ops": {"ops": []}}, ["delta_ops"]),
        ({"ops": [], "diagnostics": []}, ["diagnostics", "ops"]),
        (
            {"schema_version": DELTA_SCHEMA_VERSION, "ops": [], "automatic_link_removals": []},
            ["automatic_link_removals", "ops"],
        ),
    ],
)
def test_normalize_delta_envelope_rejects_legacy_wrapped_shapes(
    payload: dict[str, object],
    expected_keys: list[str],
) -> None:
    with pytest.raises(EditOpParseError) as exc_info:
        normalize_delta_envelope(payload)

    assert exc_info.value.code == DELTA_DIAGNOSTIC_LEGACY_SHAPE
    assert exc_info.value.detail == {"keys": expected_keys}


def test_ensure_root_scoped_delta_envelope_reports_non_root_scope_diagnostics() -> None:
    with pytest.raises(
        EditOpParseError,
        match="Non-root scoped apply is unsupported for canonical delta consumers.",
    ) as exc_info:
        ensure_root_scoped_delta_envelope(
            {
                "schema_version": DELTA_SCHEMA_VERSION,
                "ops": [
                    {
                        "op": "upsert_link",
                        "from": ["sg:nested", "seed-node", "IMAGE"],
                        "to": ["", "preview-node", "images"],
                    }
                ],
            }
        )

    assert exc_info.value.code == DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY
    assert exc_info.value.detail == {
        "scope_paths": ["sg:nested"],
        "op": "upsert_link",
    }


# ── T4: Producer / persistence tests ────────────────────────────────────────


def test_add_node_op_to_dict_includes_uid_and_node_id_when_present() -> None:
    """The flat legacy bridge (``op_to_dict``) carries uid/node_id when populated."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    op = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="PreviewImage",
        fields={"filename_prefix": "after"},
        inputs={},
        uid="assigned-uid",
        node_id="42",
    )
    payload = op_to_dict(op)
    assert payload["uid"] == "assigned-uid"
    assert payload["node_id"] == "42"


def test_add_node_op_to_dict_omits_uid_and_node_id_when_none() -> None:
    """The flat legacy bridge omits uid/node_id when they are None (pre-apply)."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    op = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="PreviewImage",
        fields={},
        inputs={},
    )
    payload = op_to_dict(op)
    assert "uid" not in payload
    assert "node_id" not in payload


def test_canonical_op_to_dict_rejects_add_node_missing_uid() -> None:
    """Strict canonicalisation rejects add_node without uid."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    op = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="PreviewImage",
        fields={},
        inputs={},
        node_id="42",
    )
    with pytest.raises(EditOpParseError, match="must include `uid`"):
        canonical_op_to_dict(op)


def test_canonical_op_to_dict_rejects_add_node_missing_node_id() -> None:
    """Strict canonicalisation rejects add_node without node_id."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    op = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="PreviewImage",
        fields={},
        inputs={},
        uid="some-uid",
    )
    with pytest.raises(EditOpParseError, match="must include `node_id`"):
        canonical_op_to_dict(op)


def test_normalize_delta_envelope_non_strict_accepts_add_node_without_identity() -> None:
    """Pre-apply normalization (strict=False) accepts add_node without uid/node_id."""
    add_node_dict = {
        "op": "add_node",
        "scope_path": "",
        "class_type": "PreviewImage",
        "fields": {},
        "inputs": {},
    }
    envelope = normalize_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [add_node_dict],
        },
        strict=False,
    )
    assert len(envelope.ops) == 1
    # Re-serialized via op_to_dict (tolerant) should match the input
    assert op_to_dict(envelope.ops[0]) == add_node_dict


def test_normalize_delta_envelope_strict_rejects_add_node_without_identity() -> None:
    """Post-apply normalization (strict=True, the default) rejects add_node
    without uid/node_id."""
    add_node_dict = {
        "op": "add_node",
        "scope_path": "",
        "class_type": "PreviewImage",
        "fields": {},
        "inputs": {},
    }
    with pytest.raises(EditOpParseError, match="must include `uid`"):
        normalize_delta_envelope(
            {
                "schema_version": DELTA_SCHEMA_VERSION,
                "ops": [add_node_dict],
            },
            strict=True,
        )


def test_add_node_roundtrip_through_non_strict_then_strict_after_populate() -> None:
    """Simulate the pre-apply → apply → post-apply flow: parse without identity,
    populate uid/node_id, then strict-canonicalise successfully."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    # Pre-apply: model returns add_node without uid/node_id
    pre_apply_dict = {
        "op": "add_node",
        "scope_path": "",
        "class_type": "PreviewImage",
        "fields": {"filename_prefix": "after"},
        "inputs": {"images": ["", "seed-node", "IMAGE"]},
    }
    envelope = normalize_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [pre_apply_dict],
        },
        strict=False,
    )
    pre_op = envelope.ops[0]
    assert isinstance(pre_op, AddNodeOp)
    assert pre_op.uid is None
    assert pre_op.node_id is None

    # Apply assigns uid/node_id (simulated)
    populated_op = AddNodeOp(
        op=pre_op.op,
        scope_path=pre_op.scope_path,
        class_type=pre_op.class_type,
        fields=dict(pre_op.fields),
        inputs=dict(pre_op.inputs),
        anchor=pre_op.anchor,
        uid="minted-uid",
        node_id="101",
    )

    # Post-apply: strict canonicalisation succeeds
    canonical = canonical_op_to_dict(populated_op)
    assert canonical["uid"] == "minted-uid"
    assert canonical["node_id"] == "101"
    assert canonical["scope_path"] == ""
    assert canonical["class_type"] == "PreviewImage"

    # Full envelope roundtrip with strict
    strict_envelope = ensure_root_scoped_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [canonical],
        },
        strict=True,
    )
    assert strict_envelope.to_dict()["ops"] == [canonical]


def test_agent_delta_turn_result_produces_envelope_and_flat_bridge_never_legacy_wrapped() -> None:
    """``AgentDeltaTurnResult.to_dict()`` emits ``delta_ops_envelope`` (canonical)
    and ``delta_ops`` (derived flat legacy bridge), never a legacy wrapped mapping."""
    from vibecomfy.porting.edit.ops import AgentDeltaTurnResult, AddNodeOp

    result = AgentDeltaTurnResult(
        delta=(
            AddNodeOp(
                op="add_node",
                scope_path="",
                class_type="PreviewImage",
                fields={},
                inputs={},
                uid="uid-1",
                node_id="99",
            ),
        ),
        message="added node",
        route="test",
        model="agent-edit-v2",
        audit_metadata={"provider": "test"},
    )
    payload = result.to_dict()

    # Canonical envelope present
    assert "delta_ops_envelope" in payload
    envelope = payload["delta_ops_envelope"]
    assert envelope["schema_version"] == DELTA_SCHEMA_VERSION
    assert len(envelope["ops"]) == 1
    assert envelope["ops"][0]["uid"] == "uid-1"
    assert envelope["ops"][0]["node_id"] == "99"

    # Flat bridge mirrors the envelope ops (key is ``delta`` in to_dict())
    assert "delta" in payload
    assert payload["delta"] == envelope["ops"]

    # Never a legacy wrapped mapping
    assert "delta_ops" not in envelope  # envelope itself is clean
    assert "diagnostics" not in envelope
    assert "automatic_link_removals" not in envelope


def test_non_strict_normalize_never_emits_legacy_wrapped_shape() -> None:
    """Even with strict=False, normalization never emits a legacy wrapped
    ``delta_ops`` mapping — it always produces a ``{schema_version, ops}`` envelope."""
    envelope = normalize_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [],
        },
        strict=False,
    )
    payload = envelope.to_dict()
    assert set(payload.keys()) == {"schema_version", "ops"}
    assert "delta_ops" not in payload
    assert "diagnostics" not in payload
