"""Build the auto-refreshing community node-schema corpus.

Generalizes the clone → extract → cache ETL in
:mod:`tools.clone_and_extract_packs` into a driver that sweeps a *set* of packs
(default: the bounded, known-good seed from :func:`get_known_node_packs`;
optionally a network sample drawn from the Comfy registry via
:func:`resolve_missing_nodes`) and writes the sharded corpus that
:class:`~vibecomfy.schema.provider.ObjectInfoIndexSchemaProvider` consumes as a
fast cache.

Extraction is delegated ENTIRELY to :func:`extract_pack_schemas` (rungs 1 + 2 of
the on-demand ladder — static AST, then stubbed subprocess import). This tool
never parses a schema itself and **never boots ComfyUI**. The "heavy boot" rung
(install real pip deps + boot ComfyUI to catch the ~6–10% of dynamic nodes the
stubs miss — rungs 3–4 of the ladder) is deferred to the corpus-builder's heavy
job per the plan's findings; see ``_HEAVY_BOOT_TODO``.

Output layout (identical to the existing cache so the provider reads it back
unchanged):

* ``<cache_root>/<pack>@<version>.json`` — one object_info-shaped shard per pack.
* ``<cache_root>/index.json`` — ``class_name -> shard_filename`` map.
* ``<report_root>/node_corpus_coverage.json`` — per-pack + overall coverage.

Robustness: each pack is processed in its own ``try/except`` so one bad pack
never aborts the sweep. The process exits non-zero when the overall extraction
yield drops below a configurable floor.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from vibecomfy.node_packs import CustomNodePack, get_known_node_packs
from vibecomfy.schema.extract import ExtractResult, extract_pack_schemas

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "vibecomfy" / "porting" / "cache" / "object_info"
INDEX_PATH = CACHE_DIR / "index.json"
OUT_DIR = ROOT / "out"
COVERAGE_PATH = OUT_DIR / "node_corpus_coverage.json"

# Heavy-boot extension point (OUT OF SCOPE here — see module docstring).
# To close the last ~6–10% of dynamic nodes the stubs miss: install the pack's
# real pip deps (registry ``dependencies`` + ``requirements.txt``) into an
# isolated venv, boot ComfyUI headless/CPU, query /object_info, and merge. This
# is rung 3–4 of the ladder and lives in the corpus builder's heavy job, NOT the
# per-request on-demand resolver (too slow). extract_pack_schemas already does
# stub-import (rung 2); do NOT attempt to boot ComfyUI here.
_HEAVY_BOOT_TODO = (
    "install real pip deps + boot ComfyUI for the dynamic-node tail "
    "(plan Phase 3 heavy boot; deferred — rungs 3–4 fold in here)"
)

# The comfy-core-fallback "pack" is a special-case marker for Comfy built-in
# primitives (PrimitiveNode/Reroute), not a real custom-node repo to clone.
_PACK_BLOCKLIST = {"comfy-core-fallback"}

# Default yield floor (fraction of attempted packs that produced >=1 class).
# Below this the builder exits non-zero so a regression in extract_pack_schemas
# surfaces in CI instead of silently shipping an empty corpus.
DEFAULT_YIELD_FLOOR = 0.25


@dataclass
class PackReport:
    """Per-pack outcome recorded in the coverage report."""

    name: str
    repo: str
    version: str = ""
    classes_total: int = 0
    classes_extracted: int = 0
    method: str = ""  # "import" | "ast" | "" (nothing extracted)
    cloned: bool = False
    cache_file: str = ""
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "repo": self.repo,
            "version": self.version,
            "classes_total": self.classes_total,
            "classes_extracted": self.classes_extracted,
            "method": self.method,
            "cloned": self.cloned,
            "cache_file": self.cache_file,
            "failures": list(self.failures),
            "warnings": list(self.warnings),
        }


@dataclass
class CorpusReport:
    """Overall sweep outcome."""

    packs: list[PackReport] = field(default_factory=list)
    packs_attempted: int = 0
    packs_succeeded: int = 0
    classes_total: int = 0
    classes_extracted: int = 0
    yield_ratio: float = 0.0
    generated_at: str = ""
    heavy_boot_todo: str = _HEAVY_BOOT_TODO

    def to_json(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "packs_attempted": self.packs_attempted,
            "packs_succeeded": self.packs_succeeded,
            "classes_total": self.classes_total,
            "classes_extracted": self.classes_extracted,
            "yield_ratio": round(self.yield_ratio, 4),
            "packs": [pack.to_json() for pack in self.packs],
            "heavy_boot_todo": self.heavy_boot_todo,
        }


# ---------------------------------------------------------------------------
# Pack selection
# ---------------------------------------------------------------------------


def select_packs(
    *,
    only: set[str] | None,
    limit: int | None,
    from_registry: int | None,
) -> list[CustomNodePack]:
    """Choose the pack set to sweep.

    * default: ``get_known_node_packs()`` minus the blocklist.
    * ``only``: restrict to the named packs (still filtered by blocklist).
    * ``limit``: cap the resulting list.
    * ``from_registry``: draw a network sample from the Comfy registry instead.
    """
    if from_registry and from_registry > 0:
        packs = _registry_sample(from_registry)
    else:
        known = [pack for pack in get_known_node_packs() if pack.name not in _PACK_BLOCKLIST]
        if only:
            wanted = set(only)
            packs = [pack for pack in known if pack.name in wanted]
        else:
            packs = list(known)

    if limit is not None and limit > 0:
        packs = packs[:limit]
    return packs


def _registry_sample(limit: int) -> list[CustomNodePack]:
    """Sample ``limit`` packs from the Comfy registry via resolve_missing_nodes.

    Uses the registry client's search endpoint (network). Returns packs as
    ``CustomNodePack`` with an empty ``classes`` set — the builder extracts every
    resolvable class, so we do not need a priori class names for registry packs.
    """
    # Imported lazily so the offline default path never needs the registry deps.
    from vibecomfy.registry.pack_resolver import (  # noqa: PLC0415
        AmbiguousPackError,
        resolve_missing_nodes,
    )

    # A broad capability query returns a cross-section of registry packs. We
    # take the top ``limit`` candidates with a usable git URL.
    resolution = resolve_missing_nodes("comfyui")
    candidates = resolution.candidates
    seen: set[str] = set()
    packs: list[CustomNodePack] = []
    for candidate in candidates:
        url = candidate.ref.url
        slug = candidate.ref.slug
        if not url or not url.endswith(".git") or slug in seen:
            continue
        seen.add(slug)
        packs.append(
            CustomNodePack(name=slug, repo=url, classes=frozenset(), pip_packages=())
        )
        if len(packs) >= limit:
            break

    if not packs:
        # resolve_missing_nodes may raise AmbiguousPackError upstream; surface
        # a clear message if the sample came back empty.
        print(
            "registry sample returned no usable packs "
            f"(warnings: {list(resolution.warnings)})",
            file=sys.stderr,
        )
    return packs


# ---------------------------------------------------------------------------
# Clone + extract (reuses extract_pack_schemas — no parsing duplication)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def clone_pack(repo: str, dest: Path, *, timeout: int = 180) -> tuple[bool, str, str]:
    """Shallow-clone ``repo`` into ``dest``. Returns (ok, sha7, error)."""
    if dest.exists():
        shutil.rmtree(dest)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo, str(dest)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if result.returncode != 0:
        return False, "", (result.stderr.strip() or result.stdout.strip() or "git clone failed")
    sha = _run(["git", "rev-parse", "--short", "HEAD"], cwd=dest).stdout.strip()
    return True, sha, ""


def _count_classes(pack_dir: Path) -> int:
    """Best-effort count of NODE_CLASS_MAPPINGS keys for classes_total.

    Used only to populate the coverage denominator; extraction itself never
    depends on this number.
    """
    import re  # noqa: PLC0415

    pattern = re.compile(r"^(\s*[\"'])([A-Za-z_][A-Za-z0-9_]*)\1\s*:")
    keys: set[str] = set()
    for path in pack_dir.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "NODE_CLASS_MAPPINGS" not in text:
            continue
        # crude: keys are string-literals mapping to classes in the mappings dict
        for line in text.splitlines():
            match = pattern.match(line)
            if match:
                keys.add(match.group(2))
    return len(keys)


def process_pack(
    pack: CustomNodePack,
    *,
    cache_dir: Path,
    index: dict[str, str],
    scratch_dir: Path,
    keep: bool,
) -> PackReport:
    """Clone, extract, and cache one pack. Never raises (records failures)."""
    report = PackReport(name=pack.name, repo=pack.repo)
    try:
        dest = scratch_dir / pack.name
        ok, sha, err = clone_pack(pack.repo, dest)
        if not ok:
            report.failures.append(err)
            return report
        report.cloned = True
        report.version = f"local-{sha}" if sha else "local"

        result: ExtractResult = extract_pack_schemas(
            dest,
            pack_name=pack.name,
            version=report.version,
            only_classes=set(pack.classes) if pack.classes else None,
            allow_import=True,
            scratch_dir=scratch_dir,
        )
        report.method = result.method
        report.failures.extend(result.failures)
        report.classes_total = _count_classes(dest)
        report.classes_extracted = len(result.entries)

        if not result.entries:
            if not report.failures:
                report.failures.append("no classes extracted")
            return report

        _write_shard(pack, report.version, result.entries, cache_dir, index, report)
    except Exception as exc:  # noqa: BLE001 — one bad pack must never abort the sweep
        report.failures.append(f"{type(exc).__name__}: {exc}")
    finally:
        if not keep and "dest" in dir() and dest.exists():
            # leave clones alone on --keep so re-runs reuse them
            pass
    return report


def _write_shard(
    pack: CustomNodePack,
    version: str,
    entries: dict[str, OrderedDict[str, Any]],
    cache_dir: Path,
    index: dict[str, str],
    report: PackReport,
) -> None:
    """Write one sharded cache file + update the class->file index (clone_and_extract parity)."""
    filename = f"{pack.name}@{version}.json"
    path = cache_dir / filename
    ordered = OrderedDict((name, entries[name]) for name in sorted(entries))
    path.write_text(json.dumps(ordered, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    report.cache_file = str(path.relative_to(ROOT)) if _is_relative(path, ROOT) else str(path)

    for class_name in sorted(entries):
        existing = index.get(class_name)
        if existing and existing != filename:
            report.warnings.append(f"{class_name}: index remapped from {existing} to {filename}")
        index[class_name] = filename


def _is_relative(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------


def write_coverage(report: CorpusReport, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.to_json(), indent=2) + "\n", encoding="utf-8")


def finalize_report(report: CorpusReport) -> CorpusReport:
    report.packs_attempted = len(report.packs)
    report.packs_succeeded = sum(1 for pack in report.packs if pack.classes_extracted > 0)
    report.classes_total = sum(pack.classes_total for pack in report.packs)
    report.classes_extracted = sum(pack.classes_extracted for pack in report.packs)
    report.yield_ratio = (report.packs_succeeded / report.packs_attempted) if report.packs_attempted else 0.0
    report.generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return report


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def build_corpus(
    *,
    packs: list[CustomNodePack],
    cache_dir: Path = CACHE_DIR,
    index_path: Path = INDEX_PATH,
    out_path: Path = COVERAGE_PATH,
    keep: bool = False,
    scratch_dir: Path | None = None,
) -> CorpusReport:
    """Sweep ``packs`` and write sharded corpus + index + coverage report."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    scratch = scratch_dir or (ROOT / ".tmp_packs")
    scratch.mkdir(parents=True, exist_ok=True)

    index: dict[str, str] = {}
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    original_index = dict(index)

    report = CorpusReport()
    for pack in packs:
        print(f"[corpus] {pack.name} <- {pack.repo}", flush=True)
        pack_report = process_pack(
            pack,
            cache_dir=cache_dir,
            index=index,
            scratch_dir=scratch,
            keep=keep,
        )
        report.packs.append(pack_report)
        print(
            f"  -> {pack_report.classes_extracted} classes "
            f"(total~{pack_report.classes_total}), method={pack_report.method or 'none'}",
            flush=True,
        )
        if pack_report.failures:
            for failure in pack_report.failures:
                print(f"     ! {failure}", file=sys.stderr, flush=True)

    if index != original_index:
        index_path.write_text(
            json.dumps(dict(sorted(index.items())), indent=2) + "\n", encoding="utf-8"
        )

    finalize_report(report)
    write_coverage(report, out_path)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pack",
        action="append",
        help="Only process the named pack; can be repeated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of packs processed (applied after --pack/--from-registry).",
    )
    parser.add_argument(
        "--from-registry",
        type=int,
        default=None,
        help="Draw a network sample of N packs from the Comfy registry (requires network).",
    )
    parser.add_argument(
        "--yield-floor",
        type=float,
        default=DEFAULT_YIELD_FLOOR,
        help="Exit non-zero when the pack yield ratio drops below this (default: %(default)s).",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep .tmp_packs clones after extraction.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=CACHE_DIR,
        help="Sharded corpus output directory (default: %(default)s).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=COVERAGE_PATH,
        help="Coverage report output path (default: %(default)s).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    os.chdir(ROOT)

    packs = select_packs(
        only=set(args.pack) if args.pack else None,
        limit=args.limit,
        from_registry=args.from_registry,
    )
    if not packs:
        print("no packs selected; nothing to do", file=sys.stderr)
        return 0

    # Derive the index path from the cache dir so --cache-dir keeps the shard
    # files and the class->file index consistent (both live in the same dir).
    index_path = args.cache_dir / "index.json"
    print(f"sweeping {len(packs)} pack(s): {', '.join(p.name for p in packs)}", flush=True)
    report = build_corpus(
        packs=packs,
        cache_dir=args.cache_dir,
        index_path=index_path,
        out_path=args.out,
        keep=args.keep,
    )

    print(
        f"\ncoverage: {report.packs_succeeded}/{report.packs_attempted} packs, "
        f"{report.classes_extracted} classes extracted "
        f"(yield={report.yield_ratio:.1%}); report -> {args.out}",
        flush=True,
    )

    if report.yield_ratio < args.yield_floor:
        print(
            f"yield {report.yield_ratio:.1%} below floor {args.yield_floor:.1%}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
