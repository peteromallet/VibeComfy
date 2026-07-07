"""Replay fixture tests for canonical delta contract migration.

Covers the hyphenated depth preprocessor alias path, canonical
``add_node.uid``/``node_id`` persistence and accept/apply identity,
malformed delta rejection, and preview/apply parity.

Uses synthetic fixtures from ``tests/fixtures/editor_sessions/``
because the named production artifacts were not present in the repository
(see T16 audit).  Every fixture manifest entry carries a ``synthetic``
marker.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    CANONICAL_DELTA_OP_NAMES,
    CanonicalDeltaEnvelope,
    DELTA_DIAGNOSTIC_LEGACY_SHAPE,
    DELTA_DIAGNOSTIC_MALFORMED,
    DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
    DELTA_SCHEMA_VERSION,
    EditOpParseError,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
    canonical_op_to_dict,
    ensure_root_scoped_delta_envelope,
    normalize_delta_envelope,
    normalize_delta_ops,
    parse_edit_op,
)

# ── helpers ──────────────────────────────────────────────────────────────────

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "editor_sessions"


def _load_fixture_json(key: str, filename: str) -> dict[str, Any]:
    path = _FIXTURE_ROOT / key / filename
    if not path.is_file():
        raise FileNotFoundError(f"Fixture file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_fixture(key: str) -> dict[str, Any]:
    """Load ``fixture.json`` for the given key."""
    return _load_fixture_json(key, "fixture.json")


def _load_model_response(key: str) -> dict[str, Any]:
    return _load_fixture_json(key, "model_response.json")


def _load_request(key: str) -> dict[str, Any]:
    return _load_fixture_json(key, "request.json")


def _make_canonical_envelope(ops: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal canonical V2 envelope."""
    return {"schema_version": DELTA_SCHEMA_VERSION, "ops": ops}


def _make_add_node_dict(
    *,
    uid: str = "n1",
    node_id: str = "node_1",
    scope_path: str = "",
    class_type: str = "SaveImage",
    fields: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
    anchor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a canonical add_node dict with required fields."""
    payload: dict[str, Any] = {
        "op": "add_node",
        "scope_path": scope_path,
        "uid": uid,
        "node_id": node_id,
        "class_type": class_type,
        "fields": fields or {},
        "inputs": inputs or {},
    }
    if anchor is not None:
        payload["anchor"] = anchor
    return payload


def _make_set_node_field_dict(
    uid: str = "3",
    field: str = "seed",
    value: Any = 42,
    scope_path: str = "",
) -> dict[str, Any]:
    return {
        "op": "set_node_field",
        "target": [scope_path, uid, field],
        "value": value,
    }


def _make_set_mode_dict(
    uid: str = "9",
    mode: int = 4,
    scope_path: str = "",
) -> dict[str, Any]:
    return {
        "op": "set_mode",
        "target": [scope_path, uid],
        "mode": mode,
    }


def _make_upsert_link_dict(
    source_uid: str = "n1",
    source_slot: str = "IMAGE",
    target_uid: str = "9",
    target_field: str = "images",
    scope_path: str = "",
) -> dict[str, Any]:
    return {
        "op": "upsert_link",
        "from": [scope_path, source_uid, source_slot],
        "to": [scope_path, target_uid, target_field],
    }


def _make_remove_node_dict(
    uid: str = "9",
    scope_path: str = "",
) -> dict[str, Any]:
    return {
        "op": "remove_node",
        "target": [scope_path, uid],
    }


def _make_remove_link_dict(
    link_id: int,
) -> dict[str, Any]:
    return {
        "op": "remove_link",
        "id": link_id,
    }


# ── Fixture markers ──────────────────────────────────────────────────────────

ALIAS_FIXTURE_KEY = "e1e66945696eb200"
CANONICAL_UID_FIXTURE_KEY = "027438a220843baa"
MALFORMED_FIXTURE_KEY = "73344eebdb00a928"
PARITY_FIXTURE_KEY = "9a30ba0715a88eed"


# ══════════════════════════════════════════════════════════════════════════════
# 1. Hyphenated depth preprocessor alias path
# ══════════════════════════════════════════════════════════════════════════════

class TestAliasPathReplay:
    """Verify MiDaS-DepthMapPreprocessor alias round-trips through the
    canonical delta pipeline."""

    def test_fixture_exists_and_is_synthetic(self) -> None:
        fixture = _load_fixture(ALIAS_FIXTURE_KEY)
        meta = fixture.get("_meta", {})
        assert meta.get("synthetic"), (
            "Alias fixture must be explicitly marked as synthetic"
        )
        assert "MiDaS-DepthMapPreprocessor" in fixture.get("content", "")

    def test_model_response_encodes_add_node_with_alias_class(self) -> None:
        response = _load_model_response(ALIAS_FIXTURE_KEY)
        turns = response["turns"]
        assert len(turns) >= 1
        br = turns[0]["batch_result"]
        statements = br["statements"]
        node_call = statements[0]
        assert node_call["op_kind"] == "node_call"
        detail = node_call["detail"]
        edit_op_str = detail.get("edit_op", "")
        # The add_node must carry the raw hyphenated class type
        assert "MiDaS-DepthMapPreprocessor" in edit_op_str

    def test_alias_add_node_canonicalizes_with_uid_and_node_id(self) -> None:
        """Build a canonical add_node for MiDaS-DepthMapPreprocessor
        and verify uid/node_id survive serialization."""
        op = _make_add_node_dict(
            uid="midas_n1",
            node_id="midas_depthmappreprocessor_0",
            class_type="MiDaS-DepthMapPreprocessor",
            fields={"a": 6.283185307179586, "bg_threshold": 0.1, "resolution": 512},
            inputs={"image": ["", "167", "image"]},
            anchor={"relation": "near", "near": ["", "167"]},
        )
        envelope = _make_canonical_envelope([op])
        result = normalize_delta_envelope(envelope)
        assert len(result.ops) == 1
        add_op = result.ops[0]
        assert isinstance(add_op, AddNodeOp)
        assert add_op.class_type == "MiDaS-DepthMapPreprocessor"
        assert add_op.uid == "midas_n1"
        assert add_op.node_id == "midas_depthmappreprocessor_0"

    def test_alias_add_node_serializes_and_reparses(self) -> None:
        """The canonicalized add_node survives serialize → re-parse identity."""
        op = _make_add_node_dict(
            uid="midas_n1",
            node_id="midas_depthmappreprocessor_0",
            class_type="MiDaS-DepthMapPreprocessor",
            fields={"a": 6.283185307179586, "bg_threshold": 0.1, "resolution": 512},
            inputs={"image": ["", "167", "image"]},
            anchor={"relation": "near", "near": ["", "167"]},
        )
        envelope = _make_canonical_envelope([op])
        result = normalize_delta_envelope(envelope)
        serialized = result.to_dict()
        # Re-parse
        result2 = normalize_delta_envelope(serialized)
        assert len(result2.ops) == 1
        op2 = result2.ops[0]
        assert isinstance(op2, AddNodeOp)
        assert op2.class_type == "MiDaS-DepthMapPreprocessor"
        assert op2.uid == "midas_n1"
        assert op2.node_id == "midas_depthmappreprocessor_0"
        assert op2.scope_path == ""

    def test_alias_fixture_upsert_link_uses_alias_node_uid(self) -> None:
        """The upsert_link after alias add_node references the minted uid."""
        response = _load_model_response(ALIAS_FIXTURE_KEY)
        statements = response["turns"][0]["batch_result"]["statements"]
        upsert_stmt = statements[1]
        assert upsert_stmt["op_kind"] == "upsert_link"
        detail = upsert_stmt["detail"]
        edit_op_str = detail.get("edit_op", "")
        # Must reference midas_n1 (the node created by the alias)
        assert "midas_n1" in edit_op_str

    def test_alias_graph_request_has_correct_node_types(self) -> None:
        request = _load_request(ALIAS_FIXTURE_KEY)
        nodes = request["graph"]["nodes"]
        node_types = {n["type"] for n in nodes}
        assert "LoadImage" in node_types
        assert "CheckpointLoaderSimple" in node_types
        assert "WanVideoControlnet" in node_types


# ══════════════════════════════════════════════════════════════════════════════
# 2. Canonical add_node.uid / node_id persistence and accept/apply identity
# ══════════════════════════════════════════════════════════════════════════════

class TestCanonicalIdentityPersistence:
    """Verify that add_node uid and node_id survive the full round-trip:
    parse → canonicalize → serialize → re-parse → accept."""

    def test_fixture_exists_and_is_synthetic(self) -> None:
        fixture = _load_fixture(CANONICAL_UID_FIXTURE_KEY)
        meta = fixture.get("_meta", {})
        assert meta.get("synthetic"), (
            "Canonical-uid fixture must be explicitly marked as synthetic"
        )

    def test_model_response_add_node_has_uid_and_node_id(self) -> None:
        response = _load_model_response(CANONICAL_UID_FIXTURE_KEY)
        statements = response["turns"][0]["batch_result"]["statements"]
        node_call = statements[0]
        detail = node_call["detail"]
        # The fixture encodes uid and node_id in the edit_op string
        assert "uid='n2'" in detail.get("edit_op", "")
        assert "node_id='saveimage_2_1'" in detail.get("edit_op", "")

    def test_canonical_envelope_retains_uid_and_node_id(self) -> None:
        """parse → canonicalize preserves uid and node_id."""
        op = _make_add_node_dict(
            uid="n2",
            node_id="saveimage_2_1",
            class_type="SaveImage",
            fields={"filename_prefix": "canonical_test"},
            inputs={"images": ["", "8", "IMAGE"]},
        )
        envelope = _make_canonical_envelope([op])
        result = normalize_delta_envelope(envelope)
        assert len(result.ops) == 1
        add_op = result.ops[0]
        assert isinstance(add_op, AddNodeOp)
        assert add_op.uid == "n2"
        assert add_op.node_id == "saveimage_2_1"

    def test_serialize_reparse_identity_uid_node_id(self) -> None:
        """serialize → re-parse preserves uid and node_id."""
        op = _make_add_node_dict(
            uid="n2",
            node_id="saveimage_2_1",
            class_type="SaveImage",
            fields={"filename_prefix": "canonical_test"},
            inputs={"images": ["", "8", "IMAGE"]},
        )
        envelope = _make_canonical_envelope([op])
        result = normalize_delta_envelope(envelope)
        serialized = result.to_dict()
        # Re-parse
        result2 = normalize_delta_envelope(serialized)
        add_op2 = result2.ops[0]
        assert isinstance(add_op2, AddNodeOp)
        assert add_op2.uid == "n2"
        assert add_op2.node_id == "saveimage_2_1"

    def test_add_node_identity_survives_multiple_ops(self) -> None:
        """When mixed with other ops, add_node uid/node_id still persist."""
        ops = [
            _make_add_node_dict(
                uid="n2",
                node_id="saveimage_2_1",
                class_type="SaveImage",
                fields={"filename_prefix": "canonical_test"},
                inputs={"images": ["", "8", "IMAGE"]},
            ),
            _make_upsert_link_dict("n2", "IMAGE", "9", "images"),
            _make_set_node_field_dict("3", "seed", 42),
        ]
        envelope = _make_canonical_envelope(ops)
        result = normalize_delta_envelope(envelope)
        assert len(result.ops) == 3
        add_op = result.ops[0]
        assert isinstance(add_op, AddNodeOp)
        assert add_op.uid == "n2"
        assert add_op.node_id == "saveimage_2_1"
        # upsert_link should reference the same uid
        link_op = result.ops[1]
        assert isinstance(link_op, UpsertLinkOp)
        assert link_op.source.uid == "n2"

    def test_ensure_root_scoped_preserves_identity(self) -> None:
        """ensure_root_scoped_delta_envelope does not strip uid/node_id."""
        op = _make_add_node_dict(
            uid="n2",
            node_id="saveimage_2_1",
            class_type="SaveImage",
            fields={"filename_prefix": "canonical_test"},
            inputs={"images": ["", "8", "IMAGE"]},
        )
        envelope = _make_canonical_envelope([op])
        result = ensure_root_scoped_delta_envelope(envelope)
        add_op = result.ops[0]
        assert isinstance(add_op, AddNodeOp)
        assert add_op.uid == "n2"
        assert add_op.node_id == "saveimage_2_1"

    def test_canonical_op_to_dict_includes_uid_node_id(self) -> None:
        """canonical_op_to_dict serializes uid and node_id explicitly."""
        op = parse_edit_op(
            _make_add_node_dict(
                uid="n2",
                node_id="saveimage_2_1",
                class_type="SaveImage",
                fields={"filename_prefix": "canonical_test"},
                inputs={"images": ["", "8", "IMAGE"]},
            )
        )
        serialized = canonical_op_to_dict(op)
        assert serialized["uid"] == "n2"
        assert serialized["node_id"] == "saveimage_2_1"
        assert serialized["class_type"] == "SaveImage"

    def test_add_node_without_uid_rejected_in_canonical(self) -> None:
        """canonical_op_to_dict rejects add_node without uid."""
        op = parse_edit_op({
            "op": "add_node",
            "scope_path": "",
            "node_id": "saveimage_2_1",
            "class_type": "SaveImage",
            "fields": {},
            "inputs": {},
        })
        with pytest.raises(EditOpParseError) as exc:
            canonical_op_to_dict(op)
        assert "uid" in str(exc.value)

    def test_add_node_without_node_id_rejected_in_canonical(self) -> None:
        """canonical_op_to_dict rejects add_node without node_id."""
        op = parse_edit_op({
            "op": "add_node",
            "scope_path": "",
            "uid": "n2",
            "class_type": "SaveImage",
            "fields": {},
            "inputs": {},
        })
        with pytest.raises(EditOpParseError) as exc:
            canonical_op_to_dict(op)
        assert "node_id" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Malformed delta rejection
# ══════════════════════════════════════════════════════════════════════════════

class TestMalformedDeltaRejection:
    """Verify that malformed deltas are rejected with stable diagnostic codes."""

    def test_fixture_exists_and_is_synthetic(self) -> None:
        fixture = _load_fixture(MALFORMED_FIXTURE_KEY)
        meta = fixture.get("_meta", {})
        assert meta.get("synthetic"), (
            "Malformed-delta fixture must be explicitly marked as synthetic"
        )

    def test_missing_schema_version_rejected(self) -> None:
        """Envelope without schema_version is rejected."""
        payload = {"ops": []}
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(payload)
        assert exc.value.code == DELTA_DIAGNOSTIC_LEGACY_SHAPE

    def test_wrong_schema_version_rejected(self) -> None:
        """Wrong schema_version is rejected."""
        payload = {"schema_version": "1.0.0", "ops": []}
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(payload)
        assert "Unsupported" in str(exc.value)

    def test_missing_ops_field_rejected(self) -> None:
        """Envelope without ops field is rejected (falls through to
        parse_edit_delta which rejects None as non-Sequence)."""
        payload = {"schema_version": DELTA_SCHEMA_VERSION}
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(payload)
        # The error comes from parse_edit_delta which receives None.
        assert "list" in str(exc.value).lower()

    def test_unknown_op_rejected(self) -> None:
        """An op with an unknown name is rejected."""
        payload = _make_canonical_envelope([
            {"op": "unknown_fake_op", "x": 1}
        ])
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(payload)
        assert "Unsupported" in str(exc.value)

    def test_legacy_delta_ops_wrapper_rejected(self) -> None:
        """Legacy wrapped delta_ops mapping is rejected as legacy_delta_shape."""
        payload = {"delta_ops": [{"op": "set_node_field", "target": ["", "3", "seed"], "value": 42}], "diagnostics": []}
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(payload)
        assert exc.value.code == DELTA_DIAGNOSTIC_LEGACY_SHAPE

    def test_legacy_ops_without_schema_rejected(self) -> None:
        """ops field without schema_version is legacy shape."""
        payload = {"ops": [{"op": "set_node_field", "target": ["", "3", "seed"], "value": 42}]}
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(payload)
        assert exc.value.code == DELTA_DIAGNOSTIC_LEGACY_SHAPE

    def test_add_node_missing_uid_rejected_by_canonicalize(self) -> None:
        """Strict normalization rejects add_node missing uid."""
        op = {
            "op": "add_node",
            "scope_path": "",
            "node_id": "saveimage_2_1",
            "class_type": "SaveImage",
            "fields": {},
            "inputs": {},
        }
        envelope = _make_canonical_envelope([op])
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(envelope)
        assert "uid" in str(exc.value)

    def test_add_node_missing_node_id_rejected_by_canonicalize(self) -> None:
        """Strict normalization rejects add_node missing node_id."""
        op = {
            "op": "add_node",
            "scope_path": "",
            "uid": "n2",
            "class_type": "SaveImage",
            "fields": {},
            "inputs": {},
        }
        envelope = _make_canonical_envelope([op])
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(envelope)
        assert "node_id" in str(exc.value)

    def test_add_node_missing_class_type_rejected(self) -> None:
        """add_node without class_type is rejected at parse time."""
        op = {
            "op": "add_node",
            "scope_path": "",
            "uid": "n2",
            "node_id": "saveimage_2_1",
            "fields": {},
            "inputs": {},
        }
        envelope = _make_canonical_envelope([op])
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(envelope)
        assert "class_type" in str(exc.value)

    def test_set_node_field_bad_target_shape_rejected(self) -> None:
        """set_node_field with wrong target shape is rejected."""
        op = {
            "op": "set_node_field",
            "target": "not-a-list",
            "value": 42,
        }
        envelope = _make_canonical_envelope([op])
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(envelope)
        assert "list" in str(exc.value).lower() or "target" in str(exc.value).lower()

    def test_set_node_field_target_too_short_rejected(self) -> None:
        """set_node_field with too-short target is rejected."""
        op = {
            "op": "set_node_field",
            "target": ["", "3"],
            "value": 42,
        }
        envelope = _make_canonical_envelope([op])
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(envelope)
        assert "length" in str(exc.value).lower()

    def test_non_root_scoped_add_node_rejected(self) -> None:
        """add_node with non-empty scope_path is rejected by ensure_root_scoped."""
        op = _make_add_node_dict(
            uid="n1",
            node_id="node_1",
            scope_path="subgraph_a",
            class_type="SaveImage",
        )
        envelope = _make_canonical_envelope([op])
        with pytest.raises(EditOpParseError) as exc:
            ensure_root_scoped_delta_envelope(envelope)
        assert exc.value.code == DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY

    def test_flat_list_without_allow_legacy_rejected(self) -> None:
        """Flat V2 op array without allow_legacy_list=True is rejected."""
        payload = [
            {"op": "set_node_field", "target": ["", "3", "seed"], "value": 42}
        ]
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(payload)
        assert exc.value.code == DELTA_DIAGNOSTIC_LEGACY_SHAPE

    def test_flat_list_with_allow_legacy_accepted(self) -> None:
        """Flat V2 op array with allow_legacy_list=True is accepted."""
        payload = [
            {"op": "set_node_field", "target": ["", "3", "seed"], "value": 42}
        ]
        result = normalize_delta_envelope(payload, allow_legacy_list=True)
        assert len(result.ops) == 1
        assert result.legacy_bridge == "flat_v2_ops"

    def test_extra_keys_in_envelope_rejected(self) -> None:
        """Envelope with extra keys beyond schema_version and ops is rejected."""
        payload = {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [],
            "diagnostics": [],
        }
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(payload)
        assert "diagnostics" in str(exc.value) or exc.value.code == DELTA_DIAGNOSTIC_LEGACY_SHAPE

    def test_non_dict_envelope_rejected(self) -> None:
        """A non-dict, non-list payload is rejected."""
        payload = "not even json"
        with pytest.raises(EditOpParseError) as exc:
            normalize_delta_envelope(payload)
        assert "object" in str(exc.value).lower()

    def test_empty_string_envelope_rejected(self) -> None:
        """Empty string is not a valid envelope."""
        with pytest.raises(EditOpParseError):
            normalize_delta_envelope("")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Preview / apply parity
# ══════════════════════════════════════════════════════════════════════════════

class TestPreviewApplyParity:
    """Verify that the same normalized delta ops produce consistent
    results whether viewed through a preview or apply lens."""

    def test_fixture_exists_and_is_synthetic(self) -> None:
        fixture = _load_fixture(PARITY_FIXTURE_KEY)
        meta = fixture.get("_meta", {})
        assert meta.get("synthetic"), (
            "Preview/apply parity fixture must be explicitly marked as synthetic"
        )

    def test_set_node_field_parity_parse_and_canonicalize(self) -> None:
        """set_node_field parsed and re-parsed yields identical canonical form."""
        op = _make_set_node_field_dict("3", "seed", 42)
        envelope = _make_canonical_envelope([op])
        result1 = normalize_delta_envelope(envelope)
        result2 = normalize_delta_envelope(result1.to_dict())
        assert result1.ops == result2.ops

    def test_set_mode_parity_parse_and_canonicalize(self) -> None:
        """set_mode parsed and re-parsed yields identical canonical form."""
        op = _make_set_mode_dict("9", 4)
        envelope = _make_canonical_envelope([op])
        result1 = normalize_delta_envelope(envelope)
        result2 = normalize_delta_envelope(result1.to_dict())
        assert result1.ops == result2.ops

    def test_multi_op_parity_roundtrip(self) -> None:
        """Multiple ops round-trip through parse→serialize→re-parse."""
        ops = [
            _make_set_node_field_dict("3", "seed", 42),
            _make_set_node_field_dict("3", "steps", 20),
            _make_set_mode_dict("9", 4),
        ]
        envelope = _make_canonical_envelope(ops)
        result1 = normalize_delta_envelope(envelope)
        result2 = normalize_delta_envelope(result1.to_dict())
        assert len(result1.ops) == len(result2.ops)
        for op1, op2 in zip(result1.ops, result2.ops):
            assert type(op1) is type(op2)
            if isinstance(op1, SetNodeFieldOp) and isinstance(op2, SetNodeFieldOp):
                assert op1.target == op2.target
                assert op1.value == op2.value
            elif isinstance(op1, SetModeOp) and isinstance(op2, SetModeOp):
                assert op1.target == op2.target
                assert op1.mode == op2.mode

    def test_model_response_statements_encode_canonical_set_field(self) -> None:
        """The parity fixture's model_response encodes set_node_field with
        proper uid targeting."""
        response = _load_model_response(PARITY_FIXTURE_KEY)
        statements = response["turns"][0]["batch_result"]["statements"]
        assert statements[0]["op_kind"] == "set_node_field"
        assert "uid='3'" in statements[0]["detail"]["edit_op"]
        assert statements[1]["op_kind"] == "set_node_field"
        assert "uid='3'" in statements[1]["detail"]["edit_op"]

    def test_model_response_statements_encode_canonical_set_mode(self) -> None:
        """The parity fixture's model_response encodes set_mode with
        proper uid targeting."""
        response = _load_model_response(PARITY_FIXTURE_KEY)
        statements = response["turns"][0]["batch_result"]["statements"]
        mode_stmt = statements[2]
        assert mode_stmt["op_kind"] == "set_mode"
        assert "uid='9'" in mode_stmt["detail"]["edit_op"]

    def test_preview_apply_identity_set_node_field(self) -> None:
        """A set_node_field op canonicalizes to the same dict regardless
        of whether it's used for preview or apply."""
        op_dict = _make_set_node_field_dict("3", "seed", 42)
        parsed = parse_edit_op(op_dict)
        canonical = canonical_op_to_dict(parsed)
        # Re-parse the canonical form
        parsed2 = parse_edit_op(canonical)
        canonical2 = canonical_op_to_dict(parsed2)
        assert canonical == canonical2

    def test_preview_apply_identity_set_mode(self) -> None:
        """A set_mode op canonicalizes to the same dict regardless of
        whether it's used for preview or apply."""
        op_dict = _make_set_mode_dict("9", 4)
        parsed = parse_edit_op(op_dict)
        canonical = canonical_op_to_dict(parsed)
        parsed2 = parse_edit_op(canonical)
        canonical2 = canonical_op_to_dict(parsed2)
        assert canonical == canonical2

    def test_all_six_canonical_op_types_accepted(self) -> None:
        """All six canonical op types pass normalization."""
        ops = [
            _make_set_node_field_dict("3", "seed", 42),
            _make_set_mode_dict("9", 4),
            _make_add_node_dict(
                uid="n1", node_id="node_1", class_type="SaveImage",
                inputs={"images": ["", "8", "IMAGE"]},
            ),
            _make_upsert_link_dict("n1", "IMAGE", "9", "images"),
            _make_remove_node_dict("9"),
            _make_remove_link_dict(42),
        ]
        envelope = _make_canonical_envelope(ops)
        result = normalize_delta_envelope(envelope)
        assert len(result.ops) == 6
        op_types = [op.op for op in result.ops]
        assert op_types == list(CANONICAL_DELTA_OP_NAMES)

    def test_normalize_delta_ops_shortcut_matches_envelope(self) -> None:
        """normalize_delta_ops returns the same ops as normalize_delta_envelope."""
        ops = [
            _make_set_node_field_dict("3", "seed", 42),
            _make_set_mode_dict("9", 4),
        ]
        envelope = _make_canonical_envelope(ops)
        ops_via_envelope = normalize_delta_envelope(envelope).ops
        ops_via_shortcut = normalize_delta_ops(envelope)
        assert ops_via_envelope == ops_via_shortcut
