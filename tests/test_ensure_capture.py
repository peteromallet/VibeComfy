"""Checkpoint A tests — persist glue + honest on-demand identity.

Covers ``vibecomfy/schema/ensure_capture.py``: tier-stamped persistence into a
tmp object_info cache, provenance attestation, the never-overwrite-higher guard,
stub-index gap detection, and mixed-pack file hygiene. No network, no clones.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict

import pytest

from vibecomfy.porting.object_info.consume import (
    ObjectInfoIdentityAmbiguityError,
    get_class_by_identity,
    reset_cache,
)
from vibecomfy.porting.object_info.serialize import CacheIdentity, build_cache
from vibecomfy.porting.object_info import consume as consume_module
from vibecomfy.schema.ensure_capture import (
    capture_tier,
    missing_live_captures,
    persist_on_demand_pack,
)
import vibecomfy.commands.schemas as schemas_command


COMMIT = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
SHA7 = COMMIT[:7]


@pytest.fixture(autouse=True)
def _fresh_consume_cache():
    reset_cache()
    yield
    reset_cache()


def _extract_entry(class_name: str, *, pack: str = "Pack") -> OrderedDict:
    """A normalize_entry-shaped extract result for one synthetic class."""
    return OrderedDict(
        (
            ("pack", pack),
            ("pack_version", "1.2.3"),
            ("python_module", f"custom_nodes.{pack}.nodes"),
            ("category", "pack"),
            ("name", class_name),
            ("display_name", class_name),
            ("description", ""),
            ("inputs", {"required": {"value": ["INT", {"default": 1}]}}),
            ("input_order", {"required": ["value"]}),
            ("input_order_all", ["value"]),
            ("object_info_widget_order", [None]),
            ("outputs", [{"type": "IMAGE", "name": "IMAGE", "is_list": False}]),
            ("function", class_name.lower()),
        )
    )


def _persist(cache_root: Path, entries: dict, rung: str = "ast"):
    return persist_on_demand_pack(
        pack_slug="Pack",
        registry_pack_version="1.2.3",
        repo="https://github.com/example/Pack",
        locked_commit=COMMIT,
        extraction_rung=rung,
        entries=entries,
        cache_dir=cache_root,
    )


def _seed_runtime_capture(cache_root: Path, class_type: str) -> tuple[str, str]:
    """Seed an attested runtime capture via build_cache itself; return (file, commit)."""
    commit = "f00f00f00f00f00f00f00f00f00f00f00f00f00f"
    dump = {
        class_type: {
            "python_module": "custom_nodes.Pack.nodes",
            "category": "pack",
            "name": class_type,
            "display_name": class_type,
            "description": "",
            "function": class_type.lower(),
            "input": {"required": {"value": ["INT", {"default": 2}]}},
            "input_order": {"required": ["value"]},
            "output": ["IMAGE"],
            "output_name": ["IMAGE"],
            "output_is_list": [False],
        }
    }
    source = cache_root / "runtime-dump.json"
    cache_root.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(dump), encoding="utf-8")
    build_cache(
        source,
        "runpod-snapshot",
        cache_dir=cache_root,
        identity=CacheIdentity(
            pack_slug="Pack",
            pack_version="runpod-snapshot",
            git_commit=commit,
            evidence_identity=f"runpod-snapshot:{commit}",
            source_kind="runtime_object_info",
        ),
    )
    runtime_file = "Pack@runpod-snapshot.json"
    provenance = {"packs": {runtime_file: {
        "pack": "Pack",
        "repo": "https://github.com/example/Pack",
        "locked_commit": commit,
        "schema_sha256": hashlib.sha256((cache_root / runtime_file).read_bytes()).hexdigest(),
        "source_kind": "runtime_object_info",
        "captured_at": "2026-01-01T00:00:00.000+00:00",
    }}}
    (cache_root / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    return runtime_file, commit


# ---------------------------------------------------------------------------
# Checkpoint A cases
# ---------------------------------------------------------------------------


def test_persist_ast_extract_writes_static_tier(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    result = _persist(cache_root, {"GapNode": _extract_entry("GapNode")}, rung="ast")

    assert not result.no_op
    filename = f"Pack@on_demand_static-{SHA7}.json"
    assert result.filename == filename
    assert (cache_root / filename).is_file()

    data = json.loads((cache_root / filename).read_text(encoding="utf-8"))
    assert set(data) == {"GapNode"}
    assert data["GapNode"]["source_kind"] == "on_demand_static"
    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert index["GapNode"] == filename

    prov = json.loads((cache_root / "provenance.json").read_text(encoding="utf-8"))
    row = prov["packs"][filename]
    assert row["repo"] == "https://github.com/example/Pack"
    assert row["locked_commit"] == COMMIT
    assert row["extraction_rung"] == "ast"
    assert row["registry_pack_version"] == "1.2.3"
    assert row["source_kind"] == "on_demand_static"
    assert row["schema_sha256"] == hashlib.sha256((cache_root / filename).read_bytes()).hexdigest()
    assert row["captured_at"]

    reset_cache()
    assert missing_live_captures(["GapNode"], cache_dir=cache_root) == []


def test_persist_import_extract_stamps_on_demand_import(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    result = _persist(cache_root, {"DynNode": _extract_entry("DynNode")}, rung="import")

    filename = f"Pack@on_demand_import-{SHA7}.json"
    assert result.filename == filename
    data = json.loads((cache_root / filename).read_text(encoding="utf-8"))
    entry = data["DynNode"]
    assert entry["source_kind"] == "on_demand_import"
    assert entry["source_kind"] != "runtime_object_info"
    assert entry["evidence_identity"] == f"on_demand:import:{COMMIT}"

    prov = json.loads((cache_root / "provenance.json").read_text(encoding="utf-8"))
    assert prov["packs"][filename]["extraction_rung"] == "import"


def test_mixed_pack_hygiene_keeps_runtime_class_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = tmp_path / "cache"
    # Identity lookups glob consume's module-level CACHE_DIR/INDEX_PATH; point them
    # at the tmp cache so the uniqueness assertion exercises real files.
    monkeypatch.setattr(consume_module, "CACHE_DIR", cache_root)
    monkeypatch.setattr(consume_module, "INDEX_PATH", cache_root / "index.json")
    runtime_file, runtime_commit = _seed_runtime_capture(cache_root, "RuntimeClass")
    entries = {
        "RuntimeClass": _extract_entry("RuntimeClass"),
        "GapNode": _extract_entry("GapNode"),
    }
    result = _persist(cache_root, entries, rung="ast")

    on_demand_file = f"Pack@on_demand_static-{SHA7}.json"
    assert result.filename == on_demand_file
    on_demand_data = json.loads((cache_root / on_demand_file).read_text(encoding="utf-8"))
    assert set(on_demand_data) == {"GapNode"}  # R not copied

    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert index["RuntimeClass"] == runtime_file
    assert index["GapNode"] == on_demand_file

    # Runtime file byte-for-byte unchanged.
    runtime_data = json.loads((cache_root / runtime_file).read_text(encoding="utf-8"))
    assert set(runtime_data) == {"RuntimeClass"}
    assert runtime_data["RuntimeClass"]["git_commit"] == runtime_commit

    # Unique identity resolution — no ambiguity error from the duplicated pack.
    reset_cache()
    try:
        entry = get_class_by_identity(
            "RuntimeClass",
            pack_slug="Pack",
            git_commit=runtime_commit,
        )
    except ObjectInfoIdentityAmbiguityError as exc:
        pytest.fail(f"identity ambiguity after mixed-pack persist: {exc.matches}")
    assert entry is not None
    assert entry["source_kind"] == "runtime_object_info"


def test_persist_over_runtime_capture_is_no_op(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    runtime_file, _ = _seed_runtime_capture(cache_root, "RuntimeClass")
    before = (cache_root / runtime_file).read_bytes()

    result = _persist(cache_root, {"RuntimeClass": _extract_entry("RuntimeClass")})

    assert result.no_op
    assert result.written_classes == []
    assert not any("on_demand" in p.name for p in cache_root.glob("*.json"))
    assert (cache_root / runtime_file).read_bytes() == before
    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert index["RuntimeClass"] == runtime_file


def test_stub_index_row_treated_as_gap(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    stub_file = "Pack@stub.json"
    cache_root.mkdir(parents=True)
    (cache_root / stub_file).write_text(json.dumps({"Stubbed": {
        "source_kind": "workflow_json_stub",
        "pack_version": "stub",
    }}), encoding="utf-8")
    (cache_root / "index.json").write_text(json.dumps({"Stubbed": stub_file}), encoding="utf-8")

    assert capture_tier(cache_root, "Stubbed") < 0
    assert missing_live_captures(["Stubbed"], cache_dir=cache_root) == ["Stubbed"]

    # ...and it is replaceable by a lower-tier on-demand capture.
    result = _persist(cache_root, {"Stubbed": _extract_entry("Stubbed")})
    assert not result.no_op
    assert result.written_classes == ["Stubbed"]
    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert index["Stubbed"] == f"Pack@on_demand_static-{SHA7}.json"


def test_gap_definitions(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    runtime_file, _ = _seed_runtime_capture(cache_root, "AttestedRuntime")
    reset_cache()

    # Attested runtime capture is NOT a gap.
    assert missing_live_captures(["AttestedRuntime"], cache_dir=cache_root) == []

    # Unindexed class IS a gap.
    assert missing_live_captures(["NeverSeen"], cache_dir=cache_root) == ["NeverSeen"]

    # Indexed but unattested (no provenance row) IS a gap.
    unattested = cache_root / "Pack@on_demand_import-deadbee.json"
    unattested.write_text(json.dumps({"Unattested": {"source_kind": "on_demand_import"}}), encoding="utf-8")
    idx = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    (cache_root / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    reset_cache()
    assert missing_live_captures(["Unattested"], cache_dir=cache_root) == ["Unattested"]

    # Provenance row without repo or locked_commit IS a gap.
    prov = json.loads((cache_root / "provenance.json").read_text(encoding="utf-8"))
    prov["packs"][runtime_file] = {"pack": "Pack", "repo": "", "locked_commit": ""}
    (cache_root / "provenance.json").write_text(json.dumps(prov), encoding="utf-8")
    reset_cache()
    assert missing_live_captures(["AttestedRuntime"], cache_dir=cache_root) == ["AttestedRuntime"]


def test_same_tier_repersist_extends_same_file_without_orphans(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    first = _persist(cache_root, {"GapNode": _extract_entry("GapNode")})
    assert not first.no_op

    # A second extract of the same pack at the same tier+commit reuses the
    # filename; the earlier class must survive the hygiene strip.
    second = _persist(cache_root, {"GapNode": _extract_entry("GapNode"), "Other": _extract_entry("Other")})
    assert second.skipped_classes == ["GapNode"]
    assert second.written_classes == ["Other"]

    data = json.loads((cache_root / first.filename).read_text(encoding="utf-8"))
    assert set(data) == {"GapNode", "Other"}
    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert index["GapNode"] == index["Other"] == first.filename

    reset_cache()
    assert missing_live_captures(["GapNode", "Other"], cache_dir=cache_root) == []


def test_unknown_rung_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _persist(tmp_path / "cache", {"X": _extract_entry("X")}, rung="runtime")


def test_schemas_provenance_helpers_accept_explicit_root(tmp_path: Path) -> None:
    # Back-compat: no cache_root argument still resolves against the package cache.
    provenance = schemas_command._load_provenance(tmp_path / "missing")
    assert provenance == {}
    target = tmp_path / "root"
    schemas_command._write_provenance({"class_count": 0}, target)
    assert json.loads((target / "provenance.json").read_text(encoding="utf-8")) == {"class_count": 0}
