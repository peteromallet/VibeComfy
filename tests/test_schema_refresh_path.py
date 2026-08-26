"""RRSYN2-3 mechanical half: ``schemas refresh`` ingest path correctness.

A real pinned capture ingested via ``refresh_schema_cache_from_source``
must regenerate the index rows AND its provenance attestation (payload
digest, class count, capture identity) so the preflight can treat it as
authoritative.  Stale index rows pointing at replaced/removed captures are
pruned.  No workflow-observation fallback is added.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.commands import schemas as schemas_cmd


@pytest.fixture()
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "object_info"
    root.mkdir()
    monkeypatch.setattr(schemas_cmd, "CACHE_DIR", root)
    return root


def _capture(
    classes: dict[str, dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        name: {
            "pack": "SomePack",
            "inputs": {name: {"type": "INT"}},
            "outputs": [],
        }
        for name in classes
    }
    if metadata is not None:
        data["_cache_metadata"] = metadata
    return data


def test_single_capture_ingest_regenerates_index_and_provenance(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    (cache_dir / "index.json").write_text("{}", encoding="utf-8")
    payload = _capture({"WidgetA", "WidgetB"})
    source = tmp_path / "ComfyUI-SomePack@local-abc123.json"
    raw = json.dumps(payload, indent=2)
    source.write_text(raw, encoding="utf-8")

    result = schemas_cmd.refresh_schema_cache_from_source(str(source))

    assert result["status"] == "ok"
    assert result["classes_indexed"] == 2
    # Index regenerated with rows for every captured class.
    index = json.loads((cache_dir / "index.json").read_text(encoding="utf-8"))
    assert index == {
        "WidgetA": source.name,
        "WidgetB": source.name,
    }
    # Provenance attestation written: digest over the exact payload bytes.
    provenance = json.loads(
        (cache_dir / "provenance.json").read_text(encoding="utf-8")
    )
    entry = provenance["packs"][source.name]
    assert entry["schema_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert entry["classes"] == 2
    assert entry["pack"] == "SomePack"
    assert entry["ingested_at"]
    assert result["provenance"]["schema_sha256"] == entry["schema_sha256"]


def test_ingest_without_repo_or_commit_stays_non_authoritative(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    """Fail-closed: a digest alone never mints authority — repo or locked
    commit must come from the capture's own attestation."""
    (cache_dir / "index.json").write_text("{}", encoding="utf-8")
    source = tmp_path / "ComfyUI-SomePack@local-abc123.json"
    source.write_text(json.dumps(_capture({"WidgetA"})), encoding="utf-8")

    result = schemas_cmd.refresh_schema_cache_from_source(str(source))

    assert result["authoritative"] is False
    provenance = json.loads(
        (cache_dir / "provenance.json").read_text(encoding="utf-8")
    )
    entry = provenance["packs"][source.name]
    assert not entry.get("repo")
    assert not entry.get("locked_commit")


def test_cache_metadata_attestation_makes_ingest_authoritative(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    (cache_dir / "index.json").write_text("{}", encoding="utf-8")
    source = tmp_path / "ComfyUI-SomePack@local-abc123.json"
    source.write_text(
        json.dumps(
            _capture(
                {"WidgetA"},
                metadata={
                    "pack": "ComfyUI-SomePack",
                    "repo": "https://github.com/example/ComfyUI-SomePack.git",
                    "locked_commit": "abc123def4567890abc123def4567890abc123de",
                    "captured_at": "2026-08-26T00:00:00Z",
                },
            )
        ),
        encoding="utf-8",
    )

    result = schemas_cmd.refresh_schema_cache_from_source(str(source))

    assert result["authoritative"] is True
    provenance = json.loads(
        (cache_dir / "provenance.json").read_text(encoding="utf-8")
    )
    entry = provenance["packs"][source.name]
    assert entry["repo"].endswith("ComfyUI-SomePack.git")
    assert entry["locked_commit"] == "abc123def4567890abc123def4567890abc123de"
    assert entry["captured_at"] == "2026-08-26T00:00:00Z"


def test_reingest_prunes_rows_pointing_at_removed_captures(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    """Replacing a stale pack (e.g. AceStep c2cfe8e) with a real pinned
    capture must drop index rows whose old file no longer exists."""
    # The stale pack file no longer exists (replaced/removed capture); only
    # its index rows and the kept capture's file linger.
    (cache_dir / "index.json").write_text(
        json.dumps(
            {
                "OldNode": "ComfyUI-StalePack@local-old.json",
                "KeptNode": "ComfyUI-LTXVideo@runpod-snapshot.json",
            }
        ),
        encoding="utf-8",
    )
    (cache_dir / "ComfyUI-LTXVideo@runpod-snapshot.json").write_text(
        "{}", encoding="utf-8"
    )
    source = tmp_path / "ComfyUI-NewPack@local-new.json"
    source.write_text(
        json.dumps(
            _capture(
                {"NewNode"},
                metadata={"repo": "https://github.com/example/newpack.git"},
            )
        ),
        encoding="utf-8",
    )

    result = schemas_cmd.refresh_schema_cache_from_source(str(source))

    index = json.loads((cache_dir / "index.json").read_text(encoding="utf-8"))
    assert "OldNode" not in index
    assert index["KeptNode"] == "ComfyUI-LTXVideo@runpod-snapshot.json"
    assert index["NewNode"] == source.name
    assert result["stale_rows_pruned"] == 1


def test_reingest_under_existing_filename_never_inherits_stale_authority(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    """Batch-review RR2: capture identity comes ONLY from the newly ingested
    payload's own attestation.  Hand-authored/unattested bytes re-ingested
    under an existing filename must not retain the previous revision's
    repo / locked_commit / captured_at, and must report non-authoritative."""
    (cache_dir / "index.json").write_text("{}", encoding="utf-8")
    source = tmp_path / "ComfyUI-SomePack@local-abc123.json"
    source.write_text(
        json.dumps(
            _capture(
                {"WidgetA"},
                metadata={
                    "pack": "ComfyUI-SomePack",
                    "repo": "https://github.com/example/ComfyUI-SomePack.git",
                    "locked_commit": "abc123def4567890abc123def4567890abc123de",
                    "captured_at": "2026-08-26T00:00:00Z",
                },
            )
        ),
        encoding="utf-8",
    )
    first = schemas_cmd.refresh_schema_cache_from_source(str(source))
    assert first["authoritative"] is True

    # Unattested replacement bytes under the SAME filename.
    source.write_text(json.dumps(_capture({"HandNode"})), encoding="utf-8")
    second = schemas_cmd.refresh_schema_cache_from_source(str(source))

    assert second["authoritative"] is False
    provenance = json.loads(
        (cache_dir / "provenance.json").read_text(encoding="utf-8")
    )
    entry = provenance["packs"][source.name]
    assert not entry.get("repo")
    assert not entry.get("locked_commit")
    assert not entry.get("captured_at")
    assert entry["schema_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_same_filename_replacement_regenerates_index_membership(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    """OldNode -> replacement: every index row mapped to the replaced file is
    removed before the new payload's classes are added — a surviving row
    would attest a class absent from the payload."""
    (cache_dir / "index.json").write_text(
        json.dumps({"OldNode": "Pack.json"}), encoding="utf-8"
    )
    # The OLD pack file still exists on disk (it was overwritten in place),
    # so missing-file pruning alone cannot catch this.
    (cache_dir / "Pack.json").write_text(
        json.dumps(_capture({"OldNode"})), encoding="utf-8"
    )
    source = tmp_path / "Pack.json"
    source.write_text(
        json.dumps(
            _capture(
                {"NewNode"},
                metadata={"repo": "https://github.com/example/newpack.git"},
            )
        ),
        encoding="utf-8",
    )

    result = schemas_cmd.refresh_schema_cache_from_source(str(source))

    index = json.loads((cache_dir / "index.json").read_text(encoding="utf-8"))
    assert index == {"NewNode": "Pack.json"}
    assert result["stale_rows_pruned"] == 1
    provenance = json.loads(
        (cache_dir / "provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["class_count"] == len(index)
