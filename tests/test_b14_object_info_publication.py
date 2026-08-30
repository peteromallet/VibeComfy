"""B14a contract tests for committed object_info cache generations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.commands import schemas as schemas_command
import vibecomfy.porting.object_info.consume as consume
import vibecomfy.porting.object_info.serialize as serialize
from vibecomfy.errors import ObjectInfoCacheCorruptError
from vibecomfy.porting.object_info.serialize import build_cache


def _source(path: Path, class_type: str, *, pack: str = "Pack") -> Path:
    path.write_text(
        json.dumps(
            {
                class_type: {
                    "python_module": f"custom_nodes.{pack}.nodes",
                    "input": {"required": {"value": ["INT"]}},
                    "input_order": {"required": ["value"]},
                    "output": ["IMAGE"],
                    "output_name": ["IMAGE"],
                    "output_is_list": [False],
                }
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture(autouse=True)
def _reset_consumer() -> None:
    consume.reset_cache()
    yield
    consume.reset_cache()


def test_build_cache_publishes_one_committed_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "cache"
    build_cache(_source(tmp_path / "one.json", "One"), version="v1", cache_dir=cache)
    monkeypatch.setattr(consume, "CACHE_DIR", cache)
    monkeypatch.setattr(consume, "INDEX_PATH", cache / "index.json")

    marker = (cache / "CURRENT").read_text(encoding="utf-8").strip()
    generation = cache / "generations" / marker
    manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["generation"] == marker
    assert {"index.json", "provenance.json", "custom_nodes.Pack@v1.json"} <= set(manifest["files"])
    assert consume.get_class("One") is not None


def test_failed_marker_publication_leaves_previous_generation_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "cache"
    build_cache(_source(tmp_path / "one.json", "One"), version="v1", cache_dir=cache)
    previous = (cache / "CURRENT").read_text(encoding="utf-8")

    def fail_marker(*_args, **_kwargs):
        raise OSError("simulated publication crash")

    monkeypatch.setattr(serialize, "atomic_write_text", fail_marker)
    with pytest.raises(OSError, match="simulated publication crash"):
        build_cache(_source(tmp_path / "two.json", "Two"), version="v2", cache_dir=cache)

    assert (cache / "CURRENT").read_text(encoding="utf-8") == previous
    monkeypatch.setattr(consume, "CACHE_DIR", cache)
    monkeypatch.setattr(consume, "INDEX_PATH", cache / "index.json")
    consume.reset_cache()
    assert consume.get_class("One") is not None
    assert consume.get_class("Two") is None


def test_partial_or_corrupt_generation_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "cache"
    build_cache(_source(tmp_path / "one.json", "One"), version="v1", cache_dir=cache)
    marker = (cache / "CURRENT").read_text(encoding="utf-8").strip()
    (cache / "generations" / marker / "custom_nodes.Pack@v1.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(consume, "CACHE_DIR", cache)
    monkeypatch.setattr(consume, "INDEX_PATH", cache / "index.json")

    with pytest.raises(ObjectInfoCacheCorruptError, match="failed its hash check"):
        consume.get_class("One")


def test_pack_and_provider_filename_escape_is_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path / "one.json", "One")
    with pytest.raises(ValueError, match="pack_slug"):
        build_cache(source, version="v1", cache_dir=tmp_path / "cache", pack_slug="../outside")

    cache = tmp_path / "legacy"
    cache.mkdir()
    (cache / "provenance.json").write_text(json.dumps({"packs": {}}), encoding="utf-8")
    (cache / "index.json").write_text(json.dumps({"One": "../outside.json"}), encoding="utf-8")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(consume, "CACHE_DIR", cache)
        monkeypatch.setattr(consume, "INDEX_PATH", cache / "index.json")
        with pytest.raises(ObjectInfoCacheCorruptError, match="unsafe"):
            consume.get_class("One")
    finally:
        monkeypatch.undo()


def _structured_capture(path: Path, class_type: str) -> Path:
    path.write_text(
        json.dumps(
            {
                class_type: {
                    "inputs": {"value": {"type": "INT"}},
                    "outputs": [{"name": "out", "type": "INT"}],
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _use_cache(monkeypatch: pytest.MonkeyPatch, cache: Path) -> None:
    monkeypatch.setattr(schemas_command, "CACHE_DIR", cache)
    monkeypatch.setattr(consume, "CACHE_DIR", cache)
    monkeypatch.setattr(consume, "INDEX_PATH", cache / "index.json")
    consume.reset_cache()


def test_command_single_copy_republishes_after_existing_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    build_cache(_source(tmp_path / "old.json", "Old"), version="v1", cache_dir=cache)
    _use_cache(monkeypatch, cache)

    source = _structured_capture(tmp_path / "Pack@v2.json", "New")
    schemas_command.refresh_schema_cache_from_source(source)

    consume.reset_cache()
    assert consume.get_class("New") is not None
    assert consume.get_class("Old") is not None
    marker = (cache / "CURRENT").read_text(encoding="utf-8").strip()
    manifest = json.loads((cache / "generations" / marker / "manifest.json").read_text(encoding="utf-8"))
    index = json.loads((cache / "generations" / marker / "index.json").read_text(encoding="utf-8"))
    assert index["New"] == source.name
    assert manifest["generation"] == marker


def test_command_directory_copy_republishes_after_existing_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    build_cache(_source(tmp_path / "old.json", "Old"), version="v1", cache_dir=cache)
    _use_cache(monkeypatch, cache)

    source_dir = tmp_path / "structured"
    source_dir.mkdir()
    (source_dir / "index.json").write_text(json.dumps({"New": "Pack.json"}), encoding="utf-8")
    (source_dir / "Pack.json").write_text(
        json.dumps({"New": {"inputs": {}, "outputs": []}}), encoding="utf-8"
    )
    schemas_command.refresh_schema_cache_from_source(source_dir)

    consume.reset_cache()
    assert consume.get_class("New") is not None
    assert consume.get_class("Old") is None
    marker = (cache / "CURRENT").read_text(encoding="utf-8").strip()
    generation_index = json.loads(
        (cache / "generations" / marker / "index.json").read_text(encoding="utf-8")
    )
    assert generation_index["New"] == "Pack.json"


@pytest.mark.parametrize("artifact", ["manifest.json", "index.json", "custom_nodes.Pack@v1.json"])
def test_committed_generation_rejects_symlinked_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    cache = tmp_path / "cache"
    build_cache(_source(tmp_path / "one.json", "One"), version="v1", cache_dir=cache)
    _use_cache(monkeypatch, cache)
    marker = (cache / "CURRENT").read_text(encoding="utf-8").strip()
    generation = cache / "generations" / marker
    outside = tmp_path / f"outside-{artifact}"
    outside.write_bytes((generation / artifact).read_bytes())
    (generation / artifact).unlink()
    (generation / artifact).symlink_to(outside)

    with pytest.raises(ObjectInfoCacheCorruptError, match="symlink"):
        consume.get_class("One")
