from __future__ import annotations

import json
import urllib.error
from typing import Any

import pytest

from scripts import upload_external_workflows_to_hivemind as ext_upload


def _sample_row(**overrides: Any) -> dict[str, Any]:
    return {
        "workflow_id": "abc123",
        "canonical_workflow_hash": "abcdef1234567890",
        "corpus_path": "external_workflows/corpus/abc123.json",
        "primary_source": {
            "source": "banodoco-discord-archive",
            "source_url": "https://cdn.discordapp.com/attachments/chanid999/attachid888/workflow.json?ex=abc&is=def&hm=secret",
            "source_type": "discord_attachment",
            "authority_tier": "community",
            "filename": "workflow.json",
            "channel_name": "comfyui",
            "message_id": "msgid777",
            "canonical_workflow_hash": "abcdef1234567890",
            "node_count": 5,
            "node_class_multiset": {"KSampler": 1, "LoadCheckpoint": 2},
            "discovered_by": "scanner",
            "discovered_at": "2026-06-24T00:00:00Z",
            "ingested_at": "2026-06-24T01:00:00Z",
        },
        "summary": {
            "title": "Test workflow title",
            "description": "A test workflow that does things.",
            "tags": ["test", "image-generation"],
            "task_type": "text_to_image",
            "media_type": "image",
            "flags": {"is_animated": False, "requires_custom_nodes": True},
            "complexity": 2,
        },
        **overrides,
    }


def test_envelope_uses_summary_title_and_description() -> None:
    row = _sample_row()
    envelope = ext_upload._envelope(row)
    data = envelope["data"]

    assert data["title"] == "Test workflow title"
    assert "Description: A test workflow that does things." in data["body"]
    assert "Tags: test, image-generation." in data["body"]
    assert data["source"] == "vibecomfy-external"
    assert data["external_id"] == "vibecomfy:external_workflow:abcdef1234567890"
    assert data["metadata"]["workflow_semantics_version"] == 1
    assert data["metadata"]["workflow_semantics"]["task_type"] == "text_to_image"
    assert "Workflow semantics" in data["body"]


def test_envelope_metadata_and_payload_carry_summary() -> None:
    row = _sample_row()
    envelope = ext_upload._envelope(row)
    metadata = envelope["data"]["metadata"]
    payload = envelope["data"]["payload"]

    assert metadata["asset_kind"] == "vibecomfy_external_workflow"
    assert metadata["description"] == "A test workflow that does things."
    assert metadata["summary"]["task_type"] == "text_to_image"
    assert metadata["summary"]["complexity"] == 2
    assert payload["summary"]["title"] == "Test workflow title"
    assert payload["description"] == "A test workflow that does things."


def test_envelope_carries_workflow_json_compiled_api_and_python(monkeypatch, tmp_path) -> None:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    workflow_path = corpus_dir / "abc123.json"
    workflow_json = {
        "vibecomfy_format_version": 1,
        "nodes": {"1": {"class_type": "LoadCheckpoint"}},
        "edges": [],
        "compiled_api": {"1": {"class_type": "LoadCheckpoint", "inputs": {}}},
    }
    workflow_path.write_text(json.dumps(workflow_json), encoding="utf-8")
    row = _sample_row(corpus_path=str(workflow_path))
    monkeypatch.setattr(
        ext_upload,
        "_emit_external_workflow_python",
        lambda path, row: "# vibecomfy: generated scratchpad\nwf = build_workflow()\n",
    )

    envelope = ext_upload._envelope(row, corpus_dir=corpus_dir)
    metadata = envelope["data"]["metadata"]
    payload = envelope["data"]["payload"]

    assert metadata["representation"] == "vibecomfy_external_workflow"
    assert metadata["representations"] == ["vibecomfy_json", "compiled_api", "scratchpad_python"]
    assert metadata["has_workflow_json"] is True
    assert metadata["has_rich_nodes"] is True
    assert metadata["has_python_source"] is True
    assert metadata["workflow_semantics"]["node_class_multiset"] == {"LoadCheckpoint": 1}
    assert metadata["workflow_semantics"]["promotion_gates"]["has_rich_nodes"] is True
    assert payload["workflow_json"] == workflow_json
    assert payload["compiled_api"] == workflow_json["compiled_api"]
    assert payload["python_source"].startswith("# vibecomfy: generated scratchpad")
    assert "Python scratchpad source:" in envelope["data"]["body"]


def test_envelope_sidecar_less_envelope_keeps_rich_nodes_gate(monkeypatch, tmp_path) -> None:
    """A new envelope without compiled_api still ranks rich: has_rich_nodes gate (P4)."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    workflow_path = corpus_dir / "def456.json"
    workflow_json = {
        "vibecomfy_format_version": "1.0",
        "nodes": {
            "1": {"class_type": "LoadCheckpoint"},
            "2": {"class_type": "PreviewImage"},
        },
        "edges": [],
    }
    workflow_path.write_text(json.dumps(workflow_json), encoding="utf-8")
    row = _sample_row(corpus_path=str(workflow_path))
    monkeypatch.setattr(
        ext_upload,
        "_emit_external_workflow_python",
        lambda path, row: "# vibecomfy: generated scratchpad\nwf = build_workflow()\n",
    )

    envelope = ext_upload._envelope(row, corpus_dir=corpus_dir)
    metadata = envelope["data"]["metadata"]
    payload = envelope["data"]["payload"]

    # No sidecar → no compiled_api representation; the rich-nodes gate stays on
    # so the hivemind rank does not drop 30 points for sidecar-less envelopes.
    assert metadata["representations"] == ["vibecomfy_json", "scratchpad_python"]
    assert metadata["has_rich_nodes"] is True
    assert metadata["has_workflow_json"] is True
    assert metadata["workflow_semantics"]["node_class_multiset"] == {
        "LoadCheckpoint": 1,
        "PreviewImage": 1,
    }
    assert metadata["workflow_semantics"]["promotion_gates"]["has_rich_nodes"] is True
    assert "has_compiled_api" not in metadata["workflow_semantics"]["promotion_gates"]
    assert payload["workflow_json"] == workflow_json
    assert payload["compiled_api"] is None


def test_envelope_body_includes_provenance() -> None:
    row = _sample_row()
    envelope = ext_upload._envelope(row)
    body = envelope["data"]["body"]

    assert "Source: banodoco-discord-archive" in body
    assert "Source URL: https://cdn.discordapp.com/attachments/_/_/workflow.json" in body
    assert "Discord channel: comfyui" in body
    assert "Canonical workflow hash: abcdef1234567890" in body
    assert "Node classes: KSampler (1), LoadCheckpoint (2)." in body


def test_envelope_url_prefers_source_url() -> None:
    row = _sample_row()
    envelope = ext_upload._envelope(row)
    assert envelope["data"]["url"] == "https://cdn.discordapp.com/attachments/_/_/workflow.json"


def test_envelope_strips_discord_signed_tokens_and_ids() -> None:
    row = _sample_row()
    envelope = ext_upload._envelope(row)
    rendered = json.dumps(envelope, sort_keys=True)

    assert "ex=abc" not in rendered
    assert "hm=secret" not in rendered
    assert "chanid999" not in rendered
    assert "attachid888" not in rendered
    assert "msgid777" not in rendered
    assert "https://cdn.discordapp.com/attachments/_/_/workflow.json" in rendered


def test_envelope_url_falls_back_to_corpus_path() -> None:
    row = _sample_row()
    row["primary_source"]["source_url"] = None
    envelope = ext_upload._envelope(row)
    assert envelope["data"]["url"] == "file://external_workflows/corpus/abc123.json"


def test_title_fallback_uses_filename_when_summary_empty() -> None:
    row = _sample_row()
    row["summary"]["title"] = "   "
    envelope = ext_upload._envelope(row)
    assert envelope["data"]["title"] == "External workflow: workflow.json"


def test_title_fallback_uses_workflow_id_when_no_filename() -> None:
    row = _sample_row()
    row["summary"] = {}
    row["primary_source"] = {}
    envelope = ext_upload._envelope(row)
    assert envelope["data"]["title"] == "External workflow abc123"


def test_enrich_row_summary_updates_row_without_dry_run_persistence(monkeypatch, tmp_path) -> None:
    corpus_dir = tmp_path / "corpus"
    cache_dir = tmp_path / "cache"
    corpus_dir.mkdir()
    workflow_path = corpus_dir / "abc123.json"
    workflow_json = {
        "nodes": {"1": {"class_type": "CheckpointLoaderSimple"}},
        "edges": [],
        "outputs": [{"output_type": "IMAGE"}],
        "requirements": {"models": [], "custom_nodes": []},
        "metadata": {"summary": {"_content_hash": "existing-hash"}},
    }
    workflow_path.write_text(json.dumps(workflow_json), encoding="utf-8")
    row = _sample_row(corpus_path=str(workflow_path), summary={"title": "", "description": ""})

    def fake_summarize(_adapter: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "title": "Enriched title",
            "description": "Enriched description.",
            "tags": ["enriched"],
            "task_type": "text_to_image",
            "media_type": "image",
            "flags": {},
            "complexity": 1,
        }

    monkeypatch.setattr("vibecomfy.ingest.summarize.summarize_workflow", fake_summarize)

    assert ext_upload._enrich_row_summary(
        row,
        corpus_dir=corpus_dir,
        cache_dir=cache_dir,
        llm_client=object(),
        persist=False,
    )
    assert row["summary"]["title"] == "Enriched title"
    assert row["summary"]["_content_hash"] == "existing-hash"
    persisted = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert persisted["metadata"]["summary"] == {"_content_hash": "existing-hash"}


def test_external_id_uses_workflow_id_when_canonical_hash_missing() -> None:
    row = _sample_row()
    row["canonical_workflow_hash"] = ""
    envelope = ext_upload._envelope(row)
    assert envelope["data"]["external_id"] == "vibecomfy:external_workflow:abc123"


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_main_skips_existing_resource_before_post(monkeypatch, tmp_path, capsys) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "workflow_id": "abc123",
                        "canonical_workflow_hash": "abcdef1234567890",
                        "corpus_path": "external_workflows/corpus/abc123.json",
                        "primary_source": {},
                        "summary": {
                            "title": "Test",
                            "description": "Test workflow.",
                            "tags": [],
                            "task_type": "other",
                            "media_type": "image",
                            "flags": {},
                            "complexity": 1,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ext_upload, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        ext_upload,
        "_find_existing_resource",
        lambda *args, **kwargs: {
            "exists": True,
            "source": "vibecomfy-external",
            "external_id": "vibecomfy:external_workflow:abcdef1234567890",
            "resource_id": 123,
            "duplicate_count": 1,
        },
    )
    posted: list[dict[str, Any]] = []
    monkeypatch.setattr(ext_upload, "_post", lambda envelope, **kwargs: posted.append(envelope))

    exit_code = ext_upload.main(["--manifest", str(manifest_path), "--sleep", "0"])

    assert exit_code == 0
    assert posted == []
    output = capsys.readouterr().out
    assert '"status": "skipped_existing"' in output
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["workflows"][0]["hivemind_upload"]["status"] == "skipped_existing"


def test_main_uploads_when_resource_does_not_exist(monkeypatch, tmp_path, capsys) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "workflow_id": "abc123",
                        "canonical_workflow_hash": "abcdef1234567890",
                        "corpus_path": "external_workflows/corpus/abc123.json",
                        "primary_source": {},
                        "summary": {
                            "title": "Test",
                            "description": "Test workflow.",
                            "tags": [],
                            "task_type": "other",
                            "media_type": "image",
                            "flags": {},
                            "complexity": 1,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ext_upload, "_repo_root", lambda: tmp_path)
    monkeypatch.delenv("HIVEMIND_CONTRIBUTOR_KEY", raising=False)
    monkeypatch.setattr(
        ext_upload,
        "_find_existing_resource",
        lambda *args, **kwargs: {"exists": False},
    )

    captured_key: Any = "unset"

    def fake_post(envelope: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        nonlocal captured_key
        captured_key = kwargs.get("contributor_key")
        return {"id": 42, "status": "ok"}

    monkeypatch.setattr(ext_upload, "_post", fake_post)

    exit_code = ext_upload.main(["--manifest", str(manifest_path), "--sleep", "0"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"status": "uploaded"' in output
    assert captured_key is None
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    upload = persisted["workflows"][0]["hivemind_upload"]
    assert upload["status"] == "uploaded"
    assert upload["response"] == {"id": 42, "status": "ok"}


def test_batch_preflight_uses_one_postgrest_query_for_multiple_rows(monkeypatch) -> None:
    envelopes = [
        ext_upload._envelope(_sample_row(workflow_id="one", canonical_workflow_hash="hash1")),
        ext_upload._envelope(_sample_row(workflow_id="two", canonical_workflow_hash="hash2")),
    ]
    calls: list[dict[str, str]] = []

    def fake_get(_table: str, params: dict[str, str], **_kwargs: Any) -> list[dict[str, Any]]:
        calls.append(params)
        return [{"id": 7, "source": "vibecomfy-external", "external_id": "vibecomfy:external_workflow:hash2"}]

    monkeypatch.setattr("scripts.upload_ready_templates_to_hivemind._postgrest_get", fake_get)
    result = ext_upload._find_existing_resources(envelopes, api_url="https://api.example", anon_key="anon")

    assert len(calls) == 1
    assert result[("vibecomfy-external", "vibecomfy:external_workflow:hash1")]["exists"] is False
    assert result[("vibecomfy-external", "vibecomfy:external_workflow:hash2")]["exists"] is True


def test_post_with_backoff_retries_retryable_http(monkeypatch) -> None:
    envelope = ext_upload._envelope(_sample_row())
    calls = 0

    def fake_post(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                url="https://example.test",
                code=429,
                msg="rate limited",
                hdrs={},
                fp=None,
            )
        return {"ok": True}

    monkeypatch.setattr(ext_upload, "_post", fake_post)
    monkeypatch.setattr(ext_upload.time, "sleep", lambda *_args: None)

    assert ext_upload._post_with_backoff(envelope, contribute_url="https://example.test", contributor_key=None) == {"ok": True}
    assert calls == 2


def test_postgrest_get_with_backoff_retries_retryable_http(monkeypatch) -> None:
    calls = 0

    def fake_get(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                url="https://example.test",
                code=503,
                msg="temporarily unavailable",
                hdrs={},
                fp=None,
            )
        return []

    monkeypatch.setattr("scripts.upload_ready_templates_to_hivemind._postgrest_get", fake_get)
    monkeypatch.setattr(ext_upload.time, "sleep", lambda *_args: None)

    assert ext_upload._postgrest_get_with_backoff(
        "external_resources",
        {"select": "id"},
        api_url="https://api.example",
        anon_key="anon",
    ) == []
    assert calls == 2
