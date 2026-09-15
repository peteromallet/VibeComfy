from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from vibecomfy.cli import build_parser
from vibecomfy.commands.templates import _cmd_create


class _FakeWorkflow:
    def __init__(self) -> None:
        self.id = "draft"
        self.source = SimpleNamespace(id="draft")
        self.metadata: dict[str, object] = {"provenance": {"origin_kind": "hivemind"}}

    def copy(self) -> "_FakeWorkflow":
        clone = _FakeWorkflow()
        clone.id = self.id
        clone.source.id = self.source.id
        clone.metadata = {key: (dict(value) if isinstance(value, dict) else value) for key, value in self.metadata.items()}
        return clone


class _FakeBundle(SimpleNamespace):
    def require_canonical_authority(self, _operation: str) -> None:
        return None


def test_templates_create_consumes_bundle_and_writes_only_python_pair(monkeypatch, tmp_path: Path, capsys) -> None:
    bundle_path = tmp_path / "bundle"
    bundle_path.mkdir()
    out = tmp_path / "ready.py"
    workflow = _FakeWorkflow()
    bundle = _FakeBundle(workflow=workflow, provenance={"origin_kind": "hivemind", "origin_pin": "4006"})
    seen: dict[str, object] = {}

    monkeypatch.setattr("vibecomfy.commands.templates.load_bundle", lambda *_args, **_kwargs: bundle)

    def fake_emit(candidate, destination, provenance, _ui, **kwargs):
        seen.update(candidate=candidate, destination=destination, provenance=provenance, kwargs=kwargs)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_text("generated", encoding="utf-8")
        return SimpleNamespace(revision_id="revision", semantic_digest="semantic", ui_digest="ui")

    monkeypatch.setattr("vibecomfy.commands.templates.emit_bundle_with_candidate", fake_emit)
    args = build_parser().parse_args(["templates", "create", str(bundle_path), "--id", "image/demo", "--out", str(out), "--json"])

    assert args.func(args) == 0
    assert out.read_text(encoding="utf-8") == "generated"
    assert not (tmp_path / "bundle" / "source.json").exists()
    assert seen["candidate"].id == "image/demo"
    assert seen["kwargs"]["source_format"] == "ready_template"
    payload = capsys.readouterr().out
    assert '"template_id": "image/demo"' in payload
    assert '"candidate_status": "created"' in payload
    assert '"runtime_verification": "not_run"' in payload
    assert '"ready_eligible": false' in payload


def test_port_check_and_convert_are_no_longer_public_commands() -> None:
    parser = build_parser()
    root_subparsers = next(action for action in parser._actions if action.dest == "cmd")
    port_parser = root_subparsers.choices["port"]
    port_subparsers = next(action for action in port_parser._actions if action.dest == "port_cmd")
    assert "check" not in port_subparsers.choices
    assert "convert" not in port_subparsers.choices
