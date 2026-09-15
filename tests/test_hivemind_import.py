from __future__ import annotations

import json
import hashlib
from types import MappingProxyType, SimpleNamespace

import pytest

from vibecomfy.commands.import_workflow import _folder_name_from_reference
from vibecomfy.porting.hivemind_source import (
    evidence_id_for_reference,
    fetch_hivemind_source,
    revision_for_reference,
)


def test_hivemind_reference_forms_normalize_to_one_evidence_id() -> None:
    assert evidence_id_for_reference("hivemind:external_resources:4018") == (
        "hivemind:external_resources:4018"
    )
    assert evidence_id_for_reference("hivemind://resource/4018") == (
        "hivemind:external_resources:4018"
    )
    assert evidence_id_for_reference("hivemind://workflows/4018") == (
        "hivemind:external_resources:4018"
    )
    assert revision_for_reference("hivemind://resources/4018/revisions/4006") == "4006"
    assert evidence_id_for_reference("/tmp/workflow.json") is None
    assert _folder_name_from_reference("hivemind://resource/4018") == "4018"


def test_fetch_hivemind_source_returns_canonical_bytes_and_origin(monkeypatch) -> None:
    workflow = {"3": {"class_type": "Integer", "inputs": {"value": 7}}}
    row = {
        "id": 4018,
        "title": "Example workflow",
        "revision_id": "4006",
        "kind": "workflow",
        "payload": {"workflow_json": workflow},
    }
    observed: list[str] = []

    def fake_get(evidence_id: str, *, timeout: float):
        observed.append(evidence_id)
        assert timeout == 10.0
        return SimpleNamespace(status="ok", result={"row": row})

    monkeypatch.setattr("vibecomfy.executor.hivemind_tools.hivemind_get", fake_get)
    source = fetch_hivemind_source("hivemind://resource/4018")

    assert observed == ["hivemind:external_resources:4018"]
    assert json.loads(source.source_bytes) == workflow
    assert source.workflow_id == "4018"
    assert source.revision == "4006"
    assert source.provenance == {
        "origin_kind": "hivemind",
        "origin_uri": "hivemind:external_resources:4018",
        "origin_pin": "4006",
        "source_digest": "sha256:" + hashlib.sha256(source.source_bytes).hexdigest(),
    }


def test_fetch_hivemind_source_thaws_frozen_tool_result(monkeypatch) -> None:
    workflow = MappingProxyType(
        {"3": MappingProxyType({"class_type": "Integer", "inputs": MappingProxyType({"value": 7})})}
    )
    row = MappingProxyType(
        {
            "id": 4018,
            "kind": "workflow",
            "payload": MappingProxyType({"workflow_json": workflow}),
        }
    )
    monkeypatch.setattr(
        "vibecomfy.executor.hivemind_tools.hivemind_get",
        lambda *_args, **_kwargs: SimpleNamespace(status="ok", result={"row": row}),
    )

    source = fetch_hivemind_source("hivemind:external_resources:4018")

    assert json.loads(source.source_bytes) == {"3": {"class_type": "Integer", "inputs": {"value": 7}}}


def test_unversioned_hivemind_row_uses_content_snapshot_pin(monkeypatch) -> None:
    source_bytes = b'{"3":{"class_type":"Integer","inputs":{"value":7}}}'
    row = {
        "id": 4018,
        "kind": "workflow",
        "payload": {"workflow_json": json.loads(source_bytes)},
    }
    monkeypatch.setattr(
        "vibecomfy.executor.hivemind_tools.hivemind_get",
        lambda *_args, **_kwargs: SimpleNamespace(status="ok", result={"row": row}),
    )

    source = fetch_hivemind_source("hivemind:external_resources:4018")

    assert source.provenance["origin_pin"] == (
        "snapshot:sha256:" + hashlib.sha256(source.source_bytes).hexdigest()
    )


def test_hivemind_revision_selector_is_verified_against_returned_row(monkeypatch) -> None:
    row = {
        "id": 4018,
        "revision_id": "4006",
        "kind": "workflow",
        "payload": {"workflow_json": {"3": {"class_type": "Integer", "inputs": {"value": 7}}}},
    }
    monkeypatch.setattr(
        "vibecomfy.executor.hivemind_tools.hivemind_get",
        lambda *_args, **_kwargs: SimpleNamespace(status="ok", result={"row": row}),
    )
    assert fetch_hivemind_source("hivemind://resources/4018/revisions/4006").revision == "4006"
    with pytest.raises(ValueError, match="not requested revision"):
        fetch_hivemind_source("hivemind://resources/4018/revisions/9999")


def test_fetch_hivemind_source_rejects_records_without_workflow(monkeypatch) -> None:
    monkeypatch.setattr(
        "vibecomfy.executor.hivemind_tools.hivemind_get",
        lambda *_args, **_kwargs: SimpleNamespace(status="ok", result={"row": {"id": 1}}),
    )
    try:
        fetch_hivemind_source("hivemind:external_resources:1")
    except ValueError as exc:
        assert "does not contain workflow JSON" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("missing workflow JSON must fail closed")


def test_cli_hivemind_input_uses_the_same_import_service(monkeypatch, tmp_path, capsys) -> None:
    from vibecomfy.cli import build_parser
    from vibecomfy.commands import import_workflow
    from vibecomfy.porting.import_service import ImportArtifacts

    source_bytes = b'{"3":{"class_type":"Integer","inputs":{"value":7}}}'
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        "vibecomfy.porting.hivemind_source.fetch_hivemind_source",
        lambda reference: SimpleNamespace(
            source_bytes=source_bytes,
            workflow_id="4018",
            evidence_id=reference,
            provenance={
                "origin_kind": "hivemind",
                "origin_uri": reference,
                "origin_pin": "4006",
                "source_digest": "sha256:source",
            },
        ),
    )

    def fake_import(payload: bytes, *, workflow_id: str, source_provenance=None, **_kwargs):
        observed.update(payload=payload, workflow_id=workflow_id, source_provenance=source_provenance)
        return ImportArtifacts(
            source_bytes=payload,
            python_bytes=b"# workflow\n",
            companion_bytes=b"{}",
            report={
                "workflow_id": workflow_id,
                "revision_id": "local-revision",
                "members": {},
                "readiness": {},
                "diagnostics": [],
            },
        )

    monkeypatch.setattr("vibecomfy.porting.import_service.import_workflow_bytes", fake_import)
    monkeypatch.chdir(tmp_path)
    args = build_parser().parse_args(["import", "hivemind://resource/4018", "--json"])

    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert observed == {
        "payload": source_bytes,
        "workflow_id": "4018",
        "source_provenance": {
            "origin_kind": "hivemind",
            "origin_uri": "hivemind://resource/4018",
            "origin_pin": "4006",
            "source_digest": "sha256:source",
        },
    }
    assert payload["source_reference"] == "hivemind:external_resources:4018"
    assert (tmp_path / "workflows" / "4018" / "source.json").read_bytes() == source_bytes
