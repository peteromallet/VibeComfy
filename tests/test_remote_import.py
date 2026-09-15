from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from vibecomfy.cli import build_parser
from vibecomfy.porting.remote_source import fetch_remote_source, is_http_url


def test_http_url_detection() -> None:
    assert is_http_url("https://example.com/workflow.json")
    assert is_http_url("http://example.com/workflow.json")
    assert not is_http_url("file:///tmp/workflow.json")
    assert not is_http_url("https:///missing-host")


def test_remote_source_preserves_bytes_and_uses_snapshot_provenance(monkeypatch) -> None:
    payload = b'{"3":{"class_type":"Integer","inputs":{"value":7}}}'

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def geturl(self):
            return "https://example.com/workflow.json"

        def read(self, _size):
            if not self._done:
                self._done = True
                return payload
            return b""

        _done = False

    monkeypatch.setattr("vibecomfy.porting.remote_source.urlopen", lambda *_args, **_kwargs: Response())
    source = fetch_remote_source("https://example.com/workflow.json")

    assert source.source_bytes == payload
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    assert source.provenance == {
        "origin_kind": "url",
        "origin_uri": "https://example.com/workflow.json",
        "origin_pin": "snapshot:" + digest,
        "source_digest": digest,
    }


def test_remote_source_rejects_non_http_redirect(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def geturl(self):
            return "ftp://example.com/workflow.json"

    monkeypatch.setattr("vibecomfy.porting.remote_source.urlopen", lambda *_args, **_kwargs: Response())
    import pytest

    with pytest.raises(ValueError, match="redirect must remain"):
        fetch_remote_source("https://example.com/workflow.json")


def test_cli_accepts_remote_url_through_normal_import_path(monkeypatch, tmp_path, capsys) -> None:
    from vibecomfy.commands import import_workflow

    source_bytes = b'{"3":{"class_type":"Integer","inputs":{"value":7}}}'
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        "vibecomfy.porting.remote_source.fetch_remote_source",
        lambda url: SimpleNamespace(
            source_bytes=source_bytes,
            provenance={
                "origin_kind": "url",
                "origin_uri": url,
                "origin_pin": "snapshot:sha256:source",
                "source_digest": "sha256:source",
            },
        ),
    )

    class Artifacts:
        def __init__(self):
            self.report = {"workflow_id": "workflow", "revision_id": "rev", "members": {}, "readiness": {}, "diagnostics": []}
            self.python_bytes = b"# workflow\n"
            self.companion_bytes = b"{}"
            self.source_bytes = source_bytes

    monkeypatch.setattr(
        "vibecomfy.porting.import_service.import_workflow_bytes",
        lambda payload, *, workflow_id, source_provenance=None, **_kwargs: (
            observed.update(payload=payload, workflow_id=workflow_id, source_provenance=source_provenance) or Artifacts()
        ),
    )
    monkeypatch.chdir(tmp_path)
    args = build_parser().parse_args(["import", "https://example.com/workflow.json", "--json"])
    assert args.func(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert observed["workflow_id"] == "workflow"
    assert output["source_reference"] == "https://example.com/workflow.json"


def test_remote_url_project_tracking_is_rejected_before_fetch(monkeypatch, tmp_path, capsys) -> None:
    from vibecomfy.cli import build_parser

    monkeypatch.setattr(
        "vibecomfy.porting.remote_source.fetch_remote_source",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )
    monkeypatch.chdir(tmp_path)
    args = build_parser().parse_args(
        ["import", "https://example.com/workflow.json", "--project", "demo", "--json"]
    )
    assert args.func(args) == 1
    payload = json.loads(capsys.readouterr().out)
    assert "local files" in payload["message"]
