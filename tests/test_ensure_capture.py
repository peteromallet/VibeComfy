"""Checkpoint A tests — persist glue + honest on-demand identity.

Covers ``vibecomfy/schema/ensure_capture.py``: tier-stamped persistence into a
tmp object_info cache, provenance attestation, the never-overwrite-higher guard,
stub-index gap detection, and mixed-pack file hygiene. No network, no clones.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path

import pytest

from vibecomfy.porting.object_info.consume import (
    ObjectInfoIdentityAmbiguityError,
    get_class_by_identity,
    reset_cache,
)
from vibecomfy.porting.object_info.serialize import CacheIdentity, build_cache
from vibecomfy.porting.object_info.generation import validate_generation
from vibecomfy.porting.object_info import consume as consume_module
import vibecomfy.porting.object_info.serialize as serialize_module
from vibecomfy.schema.ensure_capture import (
    capture_tier,
    missing_live_captures,
    persist_on_demand_pack,
)
import vibecomfy.commands.schemas as schemas_command
import vibecomfy.schema.ensure_capture as ensure_capture_module


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


def _assert_committed_capture(
    cache_root: Path,
    classes: set[str],
    *,
    expect_attestation: bool = True,
) -> None:
    """Check the reader-visible generation, rather than just root mirrors."""
    marker = (cache_root / "CURRENT").read_text(encoding="utf-8").strip()
    assert marker
    generation = cache_root / "generations" / marker
    manifest = validate_generation(generation)
    assert manifest["generation"] == marker
    index = json.loads((generation / "index.json").read_text(encoding="utf-8"))
    provenance = json.loads((generation / "provenance.json").read_text(encoding="utf-8"))
    filename = f"Pack@on_demand_static-{SHA7}.json"
    assert set(index) >= classes
    assert {index[class_type] for class_type in classes} == {filename}
    provider = json.loads((generation / filename).read_text(encoding="utf-8"))
    assert set(provider) >= classes
    row = provenance["packs"][filename]
    if expect_attestation:
        assert row["locked_commit"] == COMMIT
    assert row["schema_sha256"] == hashlib.sha256((cache_root / filename).read_bytes()).hexdigest()


def test_persist_disjoint_threads_are_one_cache_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two same-filename writers cannot lose a class or publish mixed state."""
    cache_root = tmp_path / "cache"
    start = threading.Barrier(3)
    active_lock = threading.Lock()
    active = 0
    peak_active = 0
    original_to_raw_dump = ensure_capture_module._to_raw_dump

    def slow_to_raw_dump(entry):
        nonlocal active, peak_active
        with active_lock:
            active += 1
            peak_active = max(peak_active, active)
        try:
            # This makes an unscoped read/merge transaction overlap
            # deterministically; the repaired outer lock keeps it at one.
            time.sleep(0.05)
            return original_to_raw_dump(entry)
        finally:
            with active_lock:
                active -= 1

    monkeypatch.setattr(ensure_capture_module, "_to_raw_dump", slow_to_raw_dump)
    results: list[object] = []
    errors: list[BaseException] = []

    def worker(class_type: str) -> None:
        try:
            start.wait(timeout=10)
            results.append(_persist(cache_root, {class_type: _extract_entry(class_type)}))
        except BaseException as exc:  # pragma: no cover - assertion below reports it
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(class_type,)) for class_type in ("First", "Second")]
    for thread in threads:
        thread.start()
    start.wait(timeout=10)
    for thread in threads:
        thread.join(timeout=20)
    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 2
    assert peak_active == 1
    _assert_committed_capture(cache_root, {"First", "Second"})


def test_persist_disjoint_processes_preserve_committed_generation(tmp_path: Path) -> None:
    """The outer flock also serializes independent processes on one cache."""
    cache_root = tmp_path / "cache"
    script = r'''
import sys
from collections import OrderedDict
from vibecomfy.schema.ensure_capture import persist_on_demand_pack

cache_root, class_type = sys.argv[1:]
entry = OrderedDict([
    ("pack", "Pack"),
    ("python_module", "custom_nodes.Pack.nodes"),
    ("category", "pack"),
    ("name", class_type),
    ("display_name", class_type),
    ("description", ""),
    ("inputs", {"required": {"value": ["INT", {"default": 1}]}}),
    ("input_order", {"required": ["value"]}),
    ("outputs", [{"type": "IMAGE", "name": "IMAGE", "is_list": False}]),
    ("function", class_type.lower()),
])
persist_on_demand_pack(
    pack_slug="Pack",
    registry_pack_version="1.2.3",
    repo="https://github.com/example/Pack",
    locked_commit="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    extraction_rung="ast",
    entries={class_type: entry},
    cache_dir=cache_root,
)
'''
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(cache_root), class_type],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for class_type in ("First", "Second")
    ]
    outputs = [process.communicate(timeout=30) for process in processes]
    assert all(process.returncode == 0 for process in processes), outputs
    _assert_committed_capture(cache_root, {"First", "Second"})


def test_cache_transaction_unlock_fault_releases_thread_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OS unlock failures must not wedge later same-root writers."""
    if serialize_module.fcntl is None:
        pytest.skip("POSIX flock fault injection is not available")
    real_flock = serialize_module.fcntl.flock
    failed = False

    def fail_once(file_descriptor, operation):
        nonlocal failed
        if operation == serialize_module.fcntl.LOCK_UN and not failed:
            failed = True
            raise OSError("unlock fault")
        return real_flock(file_descriptor, operation)

    monkeypatch.setattr(serialize_module.fcntl, "flock", fail_once)
    cache_root = tmp_path / "cache"
    with pytest.raises(OSError, match="unlock fault"):
        with serialize_module.cache_publish_transaction(cache_root):
            pass

    finished = threading.Event()
    errors: list[BaseException] = []

    def retry() -> None:
        try:
            with serialize_module.cache_publish_transaction(cache_root):
                pass
        except BaseException as exc:  # pragma: no cover - assertion below reports it
            errors.append(exc)
        finally:
            finished.set()

    thread = threading.Thread(target=retry)
    thread.start()
    assert finished.wait(timeout=10)
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert not errors


def test_failed_compatibility_mirror_cannot_discard_current_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial root mirror is never accepted by a later republish."""
    cache_root = tmp_path / "cache"
    first = _persist(cache_root, {"First": _extract_entry("First")})
    current_before = (cache_root / "CURRENT").read_text(encoding="utf-8")
    real_atomic_replace = serialize_module._atomic_replace_text
    failed = False

    def fail_index_once(destination: Path, text: str) -> None:
        nonlocal failed
        if destination.name == "provenance.json" and not failed:
            failed = True
            raise OSError("mirror fault")
        real_atomic_replace(destination, text)

    monkeypatch.setattr(serialize_module, "_atomic_replace_text", fail_index_once)
    with pytest.raises(OSError, match="mirror fault"):
        _persist(cache_root, {"Second": _extract_entry("Second")})
    assert (cache_root / "CURRENT").read_text(encoding="utf-8") == current_before
    # Root index/pack files may already be a mixed compatibility mirror, but
    # the standalone provider must read the committed CURRENT generation.
    from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider

    assert ObjectInfoIndexSchemaProvider(cache_root).get_schema("Second") is None

    monkeypatch.setattr(serialize_module, "_atomic_replace_text", real_atomic_replace)
    serialize_module.republish_cache_root(cache_root)
    _assert_committed_capture(cache_root, {"First"})
    assert first.filename == "Pack@on_demand_static-a1b2c3d.json"

    # The same recovery must preserve a first-ever committed generation even
    # when CURRENT had not been advanced before the mirror fault.
    fresh_root = tmp_path / "fresh-cache"
    failed = False
    monkeypatch.setattr(serialize_module, "_atomic_replace_text", fail_index_once)
    with pytest.raises(OSError, match="mirror fault"):
        _persist(fresh_root, {"First": _extract_entry("First")})
    monkeypatch.setattr(serialize_module, "_atomic_replace_text", real_atomic_replace)
    serialize_module.republish_cache_root(fresh_root)
    _assert_committed_capture(fresh_root, {"First"}, expect_attestation=False)


def test_first_generation_marker_failure_is_recovered_by_republish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A committed generation remains discoverable if pending-marker I/O fails."""
    cache_root = tmp_path / "cache"
    real_atomic_write = serialize_module.atomic_write_text
    failed = False

    def fail_pending_marker(destination: Path, text: str) -> None:
        nonlocal failed
        if destination.name == ".object_info.mirror" and text.startswith("pending:") and not failed:
            failed = True
            raise OSError("pending marker fault")
        real_atomic_write(destination, text)

    monkeypatch.setattr(serialize_module, "atomic_write_text", fail_pending_marker)
    with pytest.raises(OSError, match="pending marker fault"):
        _persist(cache_root, {"First": _extract_entry("First")})
    assert not (cache_root / "CURRENT").exists()
    assert not (cache_root / ".object_info.mirror").exists()
    assert list((cache_root / "generations").iterdir())

    monkeypatch.setattr(serialize_module, "atomic_write_text", real_atomic_write)
    serialize_module.republish_cache_root(cache_root)
    _assert_committed_capture(cache_root, {"First"}, expect_attestation=False)


def test_cache_transaction_process_fallback_serializes_subprocesses(tmp_path: Path) -> None:
    """The no-fcntl path still excludes independent processes."""
    cache_root = tmp_path / "cache"
    script = r'''
import sys
import time
from pathlib import Path
import vibecomfy.porting.object_info.serialize as serialize

serialize.fcntl = None
root = Path(sys.argv[1])
stamp = root / f"{sys.argv[2]}.txt"
start = time.monotonic()
with serialize.cache_publish_transaction(root):
    entered = time.monotonic()
    time.sleep(0.25)
stamp.write_text(f"{start} {entered} {time.monotonic()}" )
'''
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(cache_root), str(index)],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in (1, 2)
    ]
    outputs = [process.communicate(timeout=30) for process in processes]
    assert all(process.returncode == 0 for process in processes), outputs
    intervals = [
        tuple(float(value) for value in (cache_root / f"{index}.txt").read_text().split())
        for index in (1, 2)
    ]
    first, second = intervals
    assert first[1] >= second[2] or second[1] >= first[2]


def test_cache_transaction_process_fallback_reclaims_crashed_owner(tmp_path: Path) -> None:
    """A dead fallback owner is reclaimed, while live owners remain protected."""
    cache_root = tmp_path / "cache"
    crash_script = r'''
import os
import sys
import vibecomfy.porting.object_info.serialize as serialize

serialize.fcntl = None
serialize.msvcrt = None
with serialize.cache_publish_transaction(sys.argv[1]):
    os._exit(0)
'''
    crashed = subprocess.run(
        [sys.executable, "-c", crash_script, str(cache_root)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert crashed.returncode == 0
    owner_dir = cache_root / ".object_info.lock.d"
    assert owner_dir.is_dir()
    owner = json.loads((owner_dir / "owner.json").read_text(encoding="utf-8"))
    assert owner["pid"] > 0
    assert owner["start_token"]

    recover_script = r'''
import sys
import vibecomfy.porting.object_info.serialize as serialize

serialize.fcntl = None
serialize.msvcrt = None
with serialize.cache_publish_transaction(sys.argv[1]):
    pass
'''
    recovered = subprocess.run(
        [sys.executable, "-c", recover_script, str(cache_root)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert recovered.returncode == 0, recovered.stderr
    assert not owner_dir.exists()


def test_fallback_owner_metadata_fails_closed_for_malformed_live_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed owner fields cannot authorize a live-lock reclaim."""
    directory = tmp_path / ".object_info.lock.d"
    directory.mkdir()
    owner_path = directory / "owner.json"
    now = time.time()
    valid = {
        "pid": os.getpid(),
        "start_token": "a" * 32,
        "acquired_at": now,
        "lease_expires": now + 10,
    }
    malformed_records = [
        {**valid, "pid": True},
        {**valid, "pid": -1},
        {**valid, "pid": 10**20},
        {**valid, "pid": "123"},
        {**valid, "start_token": "9" * 257},
        {**valid, "start_token": ""},
        {**valid, "start_token": "bogus"},
        {**valid, "lease_expires": float("nan")},
        {**valid, "lease_expires": float("inf")},
        {**valid, "lease_expires": -1},
        {**valid, "lease_expires": now + 10**9},
        {**valid, "acquired_at": now + 10**9},
    ]
    for record in malformed_records:
        owner_path.write_text(json.dumps(record), encoding="utf-8")
        assert not serialize_module._fallback_lock_is_stale(directory)

    owner_path.write_text("{not-json", encoding="utf-8")
    assert not serialize_module._fallback_lock_is_stale(directory)

    def no_pid_probe(_pid: int):
        raise AssertionError("invalid PID reached os.kill probe")

    monkeypatch.setattr(serialize_module, "_pid_is_alive", no_pid_probe)
    owner_path.write_text(json.dumps({**valid, "pid": 10**20}), encoding="utf-8")
    assert not serialize_module._fallback_lock_is_stale(directory)


def test_fallback_owner_identity_distinguishes_dead_and_pid_reused_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / ".object_info.lock.d"
    directory.mkdir()
    now = time.time()
    owner_path = directory / "owner.json"
    owner_path.write_text(
        json.dumps(
            {
                "pid": 1234,
                "start_token": "a" * 32,
                "acquired_at": now,
                "lease_expires": now + 10,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(serialize_module, "_pid_is_alive", lambda _pid: False)
    assert serialize_module._fallback_lock_is_stale(directory)

    # A live PID remains protected even when its recorded token differs; the
    # metadata could have been tampered with, and mismatch is not authenticated
    # PID-reuse evidence.
    monkeypatch.setattr(serialize_module, "_pid_is_alive", lambda _pid: True)
    monkeypatch.setattr(serialize_module, "_process_start_token", lambda _pid: "b" * 32)
    assert not serialize_module._fallback_lock_is_stale(directory)

    # Fresh-boot /proc start tokens can be short; any nonempty digit token is
    # valid, while the bounded length rejects pathological metadata.
    owner_path.write_text(
        json.dumps({
            "pid": 1234,
            "start_token": "1",
            "acquired_at": now,
            "lease_expires": now + 10,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(serialize_module, "_pid_is_alive", lambda _pid: False)
    assert serialize_module._fallback_lock_is_stale(directory)

    # A live owner with an unrecognized/tampered token remains protected.
    owner_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "start_token": "bogus",
                "acquired_at": now,
                "lease_expires": now + 10,
            }
        ),
        encoding="utf-8",
    )
    assert not serialize_module._fallback_lock_is_stale(directory)
