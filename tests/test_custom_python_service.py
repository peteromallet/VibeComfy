from __future__ import annotations

import hashlib

import pytest

from vibecomfy.porting.custom_python_service import (
    add_exec_source_node,
    inspect_exec_source_node,
    prepare_exec_source_node,
)
from vibecomfy.porting.edit.ops import AddNodeOp


def test_prepare_exec_source_node_uses_canonical_op_and_stable_identity() -> None:
    source = "return {'image': image}"
    prepared = prepare_exec_source_node(
        source,
        {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]},
        uid="exec-stable",
    )

    assert isinstance(prepared.operation, AddNodeOp)
    assert prepared.operation.class_type == "vibecomfy.exec"
    assert prepared.operation.uid == "exec-stable"
    assert prepared.operation.fields["source"] == source
    assert prepared.metadata.io["inputs"] == (("image", "IMAGE"),)
    assert prepared.metadata.source_digest == hashlib.sha256(source.encode()).hexdigest()


def test_prepare_supports_installed_entrypoint_as_explicit_metadata_mode() -> None:
    prepared = prepare_exec_source_node(
        "return {}",
        {"outputs": []},
        uid="installed",
        mode="installed_entrypoint",
        entrypoint="my_package.handlers:run",
    )

    assert prepared.metadata.mode == "installed_entrypoint"
    assert prepared.metadata.entrypoint == "my_package.handlers:run"
    assert prepared.operation.fields.keys() == {"source", "io"}


def test_prepare_rejects_installed_mode_without_entrypoint() -> None:
    with pytest.raises(ValueError, match="requires entrypoint"):
        prepare_exec_source_node("return {}", {}, uid="x", mode="installed_entrypoint")


def test_add_and_inspect_delegate_to_edit_session() -> None:
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.schema import FrozenSchemaSnapshotProvider
    from vibecomfy.schema.provider import _builtin_schema
    from vibecomfy.schema.types import capture_schema_snapshot, schema_payload_from_node_schema

    schema = _builtin_schema("vibecomfy.exec")
    assert schema is not None
    snapshot = capture_schema_snapshot(
        class_types=("vibecomfy.exec",),
        request_snapshot={
            "schemas": {"vibecomfy.exec": schema_payload_from_node_schema("vibecomfy.exec", schema)},
            "missing_classes": [],
        },
        node_classes={},
    )

    session = EditSession(
        {"nodes": [], "links": [], "last_node_id": 0, "last_link_id": 0},
        schema_provider=FrozenSchemaSnapshotProvider(snapshot),
    )
    _prepared, result = add_exec_source_node(
        session,
        "return {'value': value}",
        {"inputs": [["value", "INT"]], "outputs": [["value", "INT"]]},
        uid="exec-1",
    )

    assert result.ok is True
    inspected = inspect_exec_source_node(session, "exec-1")
    assert inspected.descriptor.uid == "exec-1"
    assert inspected.metadata.source == "return {'value': value}"
    assert inspected.metadata.source_digest == _prepared.metadata.source_digest
