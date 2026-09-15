from __future__ import annotations

import hashlib
import json
from pathlib import Path

from vibecomfy.cli import build_parser
from vibecomfy.security import GateContext, set_gate_context
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow_bundle import load_bundle
from tests.test_edit_bundle_service import _bundle, _provider
from vibecomfy.porting.custom_python_service import _BuiltinAwareProvider


def _invoke(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


def test_edit_cli_batch_can_reference_added_uid_and_writes_one_reported_revision(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    python_path, source_bytes, provider = _bundle(tmp_path / "workflow")
    monkeypatch.setattr("vibecomfy.schema.get_authoring_schema_provider", lambda **_kwargs: provider)
    ops_path = tmp_path / "ops.json"
    ops_path.write_text(json.dumps({
        "schema_version": 1,
        "expected_revision": 0,
        "ops": [
            {"op": "remove_node", "target": "integer-one"},
            {"op": "add_node", "class_type": "Integer", "uid": "new-integer", "fields": {"value": 2}},
            {"op": "edit_node", "target": "new-integer", "field": "value", "value": 23},
        ],
    }), encoding="utf-8")
    set_gate_context(GateContext(non_interactive=True, assume_yes=True))

    code = _invoke(["edit", str(python_path), "--yes", "--json", "batch", str(ops_path)])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "saved"
    assert payload["tracking"]["mode"] == "untracked"
    assert payload["report"]["transition_kind"] == "typed_edit"
    # The editor lowers add-then-set of the same fresh UID to one canonical
    # add operation carrying the final value; success still proves that the
    # second batch statement resolved the just-added target.
    assert len(payload["operations"]) == 2
    bundle = load_bundle(python_path, trust=Provenance.USER_CONFIRMED, schema_provider=provider)
    assert len(bundle.workflow.nodes) == 1
    assert {node.inputs.get("value") for node in bundle.workflow.nodes.values()} == {23}
    assert (python_path.parent / "source.json").read_bytes() == source_bytes
    report = payload["report"]
    assert report["parent_revision"] is not None
    assert report["after"]["revision_id"] == payload["revision"]
    assert report["after"]["members"]["workflow.py"] == "sha256:" + hashlib.sha256(python_path.read_bytes()).hexdigest()
    assert not (python_path.parent / "edit-report.json").exists()


def test_edit_cli_dry_run_does_not_change_bundle(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    python_path, _source_bytes, provider = _bundle(tmp_path / "workflow")
    monkeypatch.setattr("vibecomfy.schema.get_authoring_schema_provider", lambda **_kwargs: provider)
    before_python = python_path.read_bytes()
    before_companion = python_path.with_suffix(".vibe.json").read_bytes()
    set_gate_context(GateContext(non_interactive=True, assume_yes=True))

    code = _invoke([
        "edit", str(python_path), "--yes", "--dry-run", "--json", "set", "integer-one.value", "31"
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "preview"
    assert python_path.read_bytes() == before_python
    assert python_path.with_suffix(".vibe.json").read_bytes() == before_companion


def test_edit_cli_exec_add_uses_source_service_and_dry_run_is_atomic(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    python_path, _source_bytes, base_provider = _bundle(tmp_path / "workflow")
    provider = _BuiltinAwareProvider(base_provider)
    monkeypatch.setattr("vibecomfy.schema.get_authoring_schema_provider", lambda **_kwargs: provider)
    ports_path = tmp_path / "ports.json"
    ports_path.write_text(json.dumps({
        "inputs": {"value": "INT"},
        "outputs": {"value": "INT"},
    }), encoding="utf-8")
    bindings_path = tmp_path / "bindings.json"
    bindings_path.write_text(json.dumps({"value": 4}), encoding="utf-8")
    before_python = python_path.read_bytes()
    before_companion = python_path.with_suffix(".vibe.json").read_bytes()
    set_gate_context(GateContext(non_interactive=True, assume_yes=True))

    code = _invoke([
        "edit", str(python_path), "--yes", "--dry-run", "--json", "exec", "add",
        "--source-body", "return {'value': value + 1}",
        "--ports", str(ports_path), "--bindings", str(bindings_path), "--uid", "increment",
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "preview"
    assert payload["operations"][0]["class_type"] == "vibecomfy.exec"
    assert python_path.read_bytes() == before_python
    assert python_path.with_suffix(".vibe.json").read_bytes() == before_companion


def test_edit_set_value_file_preserves_multiline_text(tmp_path: Path) -> None:
    from vibecomfy.commands.edit import _operation

    value_file = tmp_path / "long prompt.txt"
    value_file.write_text("first line\nsecond line\n", encoding="utf-8")
    args = build_parser().parse_args([
        "edit", "workflows/example", "--json", "set", "prompt_node.text",
        "--value-file", str(value_file),
    ])

    operation = _operation(args)
    assert operation == {
        "tool": "edit_node",
        "args": {"target": "prompt_node", "field": "text", "value": "first line\nsecond line\n"},
    }

    list_args = build_parser().parse_args([
        "edit", "workflows/example", "set", "prompt_node.choices", '["first", "second"]'
    ])
    list_operation = _operation(list_args)
    assert list_operation["args"]["value"] == ["first", "second"]
