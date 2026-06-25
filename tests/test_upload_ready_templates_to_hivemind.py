from __future__ import annotations

import json
from typing import Any

from scripts import upload_ready_templates_to_hivemind as upload


def test_envelope_includes_optional_description_in_body_metadata_and_payload() -> None:
    row = {
        "id": "video/example",
        "path": "ready_templates/video/example.py",
        "media": "video",
        "description": "  Turns a single portrait into a short motion clip.  ",
    }

    envelope = upload._envelope(row, "def build():\n    pass\n")

    data = envelope["data"]
    assert "Description: Turns a single portrait into a short motion clip." in data["body"]
    assert data["metadata"]["description"] == "Turns a single portrait into a short motion clip."
    assert data["payload"]["description"] == "Turns a single portrait into a short motion clip."


def test_envelope_includes_normalized_graph_identity(monkeypatch) -> None:
    row = {
        "id": "video/example",
        "path": "ready_templates/video/example.py",
        "media": "video",
    }

    def fake_identity(template_id: str) -> dict[str, Any]:
        assert template_id == "video/example"
        return {
            "graph_identity_version": 1,
            "canonical_workflow_hash": "graph-hash",
            "node_class_multiset": {"KSampler": 1, "LoadImage": 2},
            "canonical_workflow_representation": "vibecomfy.compile.api.v1",
            "canonical_workflow_node_count": 3,
        }

    monkeypatch.setattr(upload, "_load_workflow_identity", fake_identity)

    envelope = upload._envelope(row, "def build():\n    pass\n")
    identity = envelope["data"]["payload"]["graph_identity"]

    assert identity["graph_identity_status"] == "ok"
    assert identity["canonical_workflow_hash"] == "graph-hash"
    assert identity["node_class_multiset"] == {"KSampler": 1, "LoadImage": 2}
    assert identity["representation"] == "python"
    assert identity["source_file_sha256"] == upload._sha256_text("def build():\n    pass\n")
    assert envelope["data"]["metadata"]["canonical_workflow_hash"] == "graph-hash"
    assert envelope["data"]["metadata"]["node_class_multiset"] == {"KSampler": 1, "LoadImage": 2}


def test_workflow_identity_falls_back_to_source_hash_when_compile_fails(monkeypatch) -> None:
    row = {
        "id": "video/missing",
        "path": "ready_templates/video/missing.py",
    }

    def fail_identity(_template_id: str) -> dict[str, Any]:
        raise RuntimeError("cannot import")

    monkeypatch.setattr(upload, "_load_workflow_identity", fail_identity)

    identity = upload._workflow_identity(row, "print('source')\n")

    assert identity["graph_identity_version"] == 1
    assert identity["graph_identity_status"] == "error"
    assert identity["graph_identity_error"] == "RuntimeError: cannot import"
    assert identity["representation"] == "python"
    assert identity["source_file_sha256"] == upload._sha256_text("print('source')\n")


def test_description_map_can_enrich_by_template_id_path_or_filename(tmp_path) -> None:
    description_map = tmp_path / "descriptions.json"
    description_map.write_text(
        json.dumps(
            {
                "image/by-id": "Matched by id.",
                "ready_templates/video/by-path.py": "Matched by path.",
                "by-filename.py": "Matched by filename.",
            }
        ),
        encoding="utf-8",
    )
    args = upload.build_parser().parse_args(
        [
            "--dry-run",
            "--description-map",
            str(description_map),
        ]
    )

    descriptions = upload._read_description_args(args, root=tmp_path)

    assert upload._apply_description(
        {"id": "image/by-id", "path": "ready_templates/image/by-id.py"},
        descriptions,
    )["description"] == "Matched by id."
    assert upload._apply_description(
        {"id": "video/other", "path": "ready_templates/video/by-path.py"},
        descriptions,
    )["description"] == "Matched by path."
    assert upload._apply_description(
        {"id": "audio/other", "path": "ready_templates/audio/by-filename.py"},
        descriptions,
    )["description"] == "Matched by filename."


def test_inline_description_applies_as_batch_default() -> None:
    args = upload.build_parser().parse_args(
        [
            "--dry-run",
            "--description",
            "  Useful because it combines depth conditioning with a stylized LoRA. ",
        ]
    )

    descriptions = upload._read_description_args(args, root=upload._repo_root())
    row = upload._apply_description(
        {"id": "image/depth-style", "path": "ready_templates/image/depth_style.py"},
        descriptions,
    )

    assert row["description"] == "Useful because it combines depth conditioning with a stylized LoRA."


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_verify_recorded_checks_description_body_metadata_and_payload(monkeypatch) -> None:
    row = {
        "id": "video/example",
        "path": "ready_templates/video/example.py",
        "media": "video",
        "description": "Special because it combines camera control with image-to-video.",
    }
    envelope = upload._envelope(row, "def build():\n    pass\n")

    def fake_urlopen(request: object, timeout: int = 30) -> _FakeResponse:
        return _FakeResponse(
            [
                {
                    "id": 123,
                    "kind": "workflow",
                    "source": "vibecomfy",
                    "external_id": "vibecomfy:ready_template:video/example",
                    "title": "video/example",
                    "body": envelope["data"]["body"],
                    "metadata": envelope["data"]["metadata"],
                    "payload": envelope["data"]["payload"],
                }
            ]
        )

    monkeypatch.setattr(upload.urllib.request, "urlopen", fake_urlopen)

    result = upload._verify_recorded(
        envelope,
        api_url="https://example.test/rest/v1",
        anon_key="anon",
    )

    assert result["ok"] is True
    assert result["checks"] == {
        "kind": True,
        "source": True,
        "external_id": True,
        "title": True,
        "metadata_description": True,
        "payload_description": True,
        "body_description": True,
    }


def test_find_existing_resource_uses_source_external_id(monkeypatch) -> None:
    row = {"id": "video/example", "path": "ready_templates/video/example.py"}
    envelope = upload._envelope(row, "def build():\n    pass\n")
    seen: dict[str, Any] = {}

    def fake_postgrest_get(
        table: str,
        params: dict[str, str],
        *,
        api_url: str,
        anon_key: str,
    ) -> list[dict[str, Any]]:
        seen.update(
            {
                "table": table,
                "params": params,
                "api_url": api_url,
                "anon_key": anon_key,
            }
        )
        return [
            {
                "id": 123,
                "source": "vibecomfy",
                "external_id": "vibecomfy:ready_template:video/example",
                "title": "video/example",
                "updated_at": "2026-06-24T00:00:00Z",
            }
        ]

    monkeypatch.setattr(upload, "_postgrest_get", fake_postgrest_get)

    result = upload._find_existing_resource(
        envelope,
        api_url="https://example.test/rest/v1",
        anon_key="anon",
    )

    assert seen["table"] == "external_resources"
    assert seen["params"]["source"] == "eq.vibecomfy"
    assert seen["params"]["external_id"] == "eq.vibecomfy:ready_template:video/example"
    assert seen["params"]["limit"] == "2"
    assert result["exists"] is True
    assert result["resource_id"] == 123


def test_main_skips_existing_resource_before_post(monkeypatch, tmp_path, capsys) -> None:
    template_path = tmp_path / "ready_templates" / "video" / "example.py"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("def build():\n    pass\n", encoding="utf-8")
    index_path = tmp_path / "template_index.json"
    index_path.write_text(
        json.dumps(
            {
                "templates": [
                    {
                        "id": "video/example",
                        "path": "ready_templates/video/example.py",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    posted: list[dict[str, Any]] = []

    monkeypatch.setattr(upload, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("HIVEMIND_CONTRIBUTOR_KEY", "contributor")
    monkeypatch.setattr(
        upload,
        "_find_existing_resource",
        lambda *args, **kwargs: {
            "exists": True,
            "source": "vibecomfy",
            "external_id": "vibecomfy:ready_template:video/example",
            "resource_id": 123,
            "duplicate_count": 1,
        },
    )
    monkeypatch.setattr(upload, "_post", lambda envelope, **kwargs: posted.append(envelope))

    exit_code = upload.main(["--index", str(index_path), "--coverage", "", "--sleep", "0"])

    assert exit_code == 0
    assert posted == []
    output = capsys.readouterr().out
    assert '"status": "skipped_existing"' in output


def test_dry_run_preflight_reports_existing_without_upload(monkeypatch, tmp_path, capsys) -> None:
    template_path = tmp_path / "ready_templates" / "video" / "example.py"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("def build():\n    pass\n", encoding="utf-8")
    index_path = tmp_path / "template_index.json"
    index_path.write_text(
        json.dumps(
            {
                "templates": [
                    {
                        "id": "video/example",
                        "path": "ready_templates/video/example.py",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    posted: list[dict[str, Any]] = []

    monkeypatch.setattr(upload, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        upload,
        "_find_existing_resource",
        lambda *args, **kwargs: {
            "exists": True,
            "source": "vibecomfy",
            "external_id": "vibecomfy:ready_template:video/example",
            "resource_id": 123,
            "duplicate_count": 1,
        },
    )
    monkeypatch.setattr(upload, "_post", lambda envelope, **kwargs: posted.append(envelope))

    exit_code = upload.main(
        ["--index", str(index_path), "--coverage", "", "--dry-run", "--dry-run-preflight"]
    )

    assert exit_code == 0
    assert posted == []
    output = capsys.readouterr().out
    assert '"status": "would_skip_existing"' in output
