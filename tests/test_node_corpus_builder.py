"""Consumer tests for the L6 node-schema corpus builder.

Two layers:

* **Offline (CI)**: build the corpus over a tiny committed fixture pack set,
  assert it writes a shard + updates ``index.json``, and that
  :class:`ObjectInfoIndexSchemaProvider` reads a class back out of the built
  corpus. No network, no clone.
* **Live (opt-in)**: run the real builder over a bounded slice of
  ``get_known_node_packs()`` (clones public repos). Skipped unless
  ``VIBECOMFY_RUN_COVERAGE_SWEEP=1`` — mirrors the project's live-test gate.

This proves the L6 contract (plan verification L6): the builder emits a corpus
a consumer can read as a fast cache.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider

from tools.build_node_corpus import (
    CorpusReport,
    build_corpus,
    select_packs,
)

LIVE_ENV = "VIBECOMFY_RUN_COVERAGE_SWEEP"
pytestmark_live = pytest.mark.live
skip_live = pytest.mark.skipif(
    not __import__("os").environ.get(LIVE_ENV),
    reason=f"set {LIVE_ENV}=1 to run the live coverage sweep (clones public repos)",
)


# ---------------------------------------------------------------------------
# Fixture pack source (mirrors tests/test_on_demand_resolver.py's sample pack)
# ---------------------------------------------------------------------------


def _write_fixture_pack(root: Path) -> Path:
    """A tiny custom-node pack whose INPUT_TYPES is statically parseable."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "nodes.py").write_text(
        """
NODE_CLASS_MAPPINGS = {"FixtureWidgetNode": FixtureWidgetNode}

class FixtureWidgetNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "strength": ("FLOAT", {"default": 0.8, "min": 0.0, "max": 1.0}),
            },
        }
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "execute"
    CATEGORY = "fixture/tests"
""",
        encoding="utf-8",
    )
    return root


def test_builder_writes_shard_and_index_and_report(tmp_path: Path) -> None:
    """Offline: the builder over a fixture pack writes shard + index + coverage."""
    from vibecomfy.node_packs import CustomNodePack

    cache_dir = tmp_path / "object_info"
    out_path = tmp_path / "out" / "node_corpus_coverage.json"
    clone_root = tmp_path / "clones"
    scratch = tmp_path / "scratch"

    # Materialize a fixture pack source as if it were cloned.
    _write_fixture_pack(clone_root / "fixture-pack")

    # Select nothing from the registry; hand the builder a fake pack whose
    # repo resolves to the local clone via a process_pack override path.
    # Simplest: point select_packs at a stub CustomNodePack and monkeypatch
    # clone_pack to copy the fixture dir instead of git-cloning.
    import tools.build_node_corpus as builder

    pack = CustomNodePack(
        name="fixture-pack",
        repo="https://example.invalid/fixture-pack.git",
        classes=frozenset(),
    )

    def fake_clone(repo: str, dest: Path, **kwargs):  # type: ignore[no-untyped-def]
        import shutil

        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(clone_root / "fixture-pack", dest)
        return True, "abcdef0", ""

    original_clone = builder.clone_pack
    builder.clone_pack = fake_clone  # type: ignore[assignment]
    try:
        report = build_corpus(
            packs=[pack],
            cache_dir=cache_dir,
            index_path=cache_dir / "index.json",
            out_path=out_path,
            scratch_dir=scratch,
        )
    finally:
        builder.clone_pack = original_clone  # type: ignore[assignment]

    assert isinstance(report, CorpusReport)
    assert report.packs_attempted == 1
    assert report.packs_succeeded == 1
    assert report.classes_extracted >= 1

    # Shard file written, named <pack>@<version>.json.
    shards = list(cache_dir.glob("fixture-pack@*.json"))
    assert len(shards) == 1, f"expected one shard, got {shards}"
    shard = json.loads(shards[0].read_text(encoding="utf-8"))
    assert "FixtureWidgetNode" in shard

    # index.json maps the class to the shard.
    index = json.loads((cache_dir / "index.json").read_text(encoding="utf-8"))
    assert index["FixtureWidgetNode"].startswith("fixture-pack@")

    # Coverage report written with per-pack + overall totals.
    coverage = json.loads(out_path.read_text(encoding="utf-8"))
    assert coverage["packs_attempted"] == 1
    assert coverage["packs_succeeded"] == 1
    assert coverage["classes_extracted"] >= 1
    assert coverage["packs"][0]["name"] == "fixture-pack"
    assert coverage["packs"][0]["classes_extracted"] >= 1


def test_consumer_reads_class_from_built_corpus(tmp_path: Path) -> None:
    """Offline: ObjectInfoIndexSchemaProvider reads a class out of the built corpus."""
    from vibecomfy.node_packs import CustomNodePack

    cache_dir = tmp_path / "object_info"
    out_path = tmp_path / "out" / "node_corpus_coverage.json"
    clone_root = tmp_path / "clones"
    scratch = tmp_path / "scratch"
    _write_fixture_pack(clone_root / "fixture-pack")

    import tools.build_node_corpus as builder

    pack = CustomNodePack(
        name="fixture-pack",
        repo="https://example.invalid/fixture-pack.git",
        classes=frozenset(),
    )

    def fake_clone(repo: str, dest: Path, **kwargs):  # type: ignore[no-untyped-def]
        import shutil

        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(clone_root / "fixture-pack", dest)
        return True, "abcdef0", ""

    original_clone = builder.clone_pack
    builder.clone_pack = fake_clone  # type: ignore[assignment]
    try:
        build_corpus(
            packs=[pack],
            cache_dir=cache_dir,
            index_path=cache_dir / "index.json",
            out_path=out_path,
            scratch_dir=scratch,
        )
    finally:
        builder.clone_pack = original_clone  # type: ignore[assignment]

    provider = ObjectInfoIndexSchemaProvider(cache_dir)
    schema = provider.get_schema("FixtureWidgetNode")
    assert schema is not None, "consumer failed to read built corpus"
    assert schema.class_type == "FixtureWidgetNode"
    assert schema.pack == "fixture-pack"
    assert schema.source_provider == "object_info_index"


def test_builder_skips_blocklisted_fallback_pack() -> None:
    """The comfy-core-fallback marker is never cloned (it's a built-in shim)."""
    packs = select_packs(only=None, limit=None, from_registry=None)
    names = {pack.name for pack in packs}
    assert "comfy-core-fallback" not in names


@skip_live
@pytestmark_live
def test_builder_small_slice_known_packs(tmp_path: Path) -> None:
    """Live: build over a 2-pack slice of get_known_node_packs and read a class back.

    Clones public repos; gated on VIBECOMFY_RUN_COVERAGE_SWEEP=1.
    """
    cache_dir = tmp_path / "object_info"
    out_path = tmp_path / "out" / "node_corpus_coverage.json"
    packs = select_packs(only=None, limit=2, from_registry=None)
    assert packs, "no known packs available"

    report = build_corpus(
        packs=packs,
        cache_dir=cache_dir,
        index_path=cache_dir / "index.json",
        out_path=out_path,
    )
    assert report.packs_attempted == 2
    # At least one of the two known seed packs must yield classes.
    assert report.classes_extracted > 0

    provider = ObjectInfoIndexSchemaProvider(cache_dir)
    assert provider._load_index(), "index empty after live build"
