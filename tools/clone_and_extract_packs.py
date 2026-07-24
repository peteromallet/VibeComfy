"""Clone missing custom-node packs and extract object_info schemas.

One-shot ETL helper that augments ``vibecomfy/porting/cache/object_info`` from the
registry packs known to ``vibecomfy.node_packs``. Extraction (rungs 1 + 2 of the
on-demand ladder) lives in :mod:`vibecomfy.schema.extract`; this tool is the thin
clone → extract → cache ETL wrapper, and is also the seed of the auto-refreshing
corpus builder (see docs/plans/all-installable-nodes.md, Phase 3).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.node_packs import CustomNodePack, get_known_node_packs
from vibecomfy.schema.extract import ExtractResult, extract_pack_schemas

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "vibecomfy" / "porting" / "cache" / "object_info"
INDEX_PATH = CACHE_DIR / "index.json"
TMP_ROOT = ROOT / ".tmp_packs"


@dataclass
class PackReport:
    name: str
    repo: str
    cloned: bool = False
    sha7: str = ""
    method: str = ""
    class_count: int = 0
    cache_file: str = ""
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_index() -> dict[str, str]:
    if not INDEX_PATH.exists():
        return {}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def missing_packs(index: dict[str, str]) -> list[CustomNodePack]:
    missing: list[CustomNodePack] = []
    known = set(index)
    for pack in get_known_node_packs():
        if not set(pack.classes).issubset(known):
            missing.append(pack)
    return missing


def clone_pack(pack: CustomNodePack, report: PackReport) -> Path | None:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    dest = TMP_ROOT / pack.name
    if dest.exists():
        shutil.rmtree(dest)
    result = run(["git", "clone", "--depth", "1", pack.repo, str(dest)], check=False)
    if result.returncode != 0:
        report.failures.append(result.stderr.strip() or result.stdout.strip() or "git clone failed")
        return None
    report.cloned = True
    sha = run(["git", "rev-parse", "--short", "HEAD"], cwd=dest).stdout.strip()
    report.sha7 = sha
    return dest


def write_cache(pack: CustomNodePack, version: str, entries: dict[str, OrderedDict[str, Any]], index: dict[str, str], report: PackReport) -> None:
    filename = f"{pack.name}@{version}.json"
    path = CACHE_DIR / filename
    ordered = OrderedDict((name, entries[name]) for name in sorted(entries))
    path.write_text(json.dumps(ordered, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    report.cache_file = str(path.relative_to(ROOT))

    for class_name in sorted(entries):
        existing = index.get(class_name)
        if existing and existing != filename:
            report.warnings.append(f"{class_name}: index remapped from {existing} to {filename}")
        index[class_name] = filename


def process_pack(pack: CustomNodePack, index: dict[str, str]) -> PackReport:
    report = PackReport(name=pack.name, repo=pack.repo)
    pack_dir = clone_pack(pack, report)
    if pack_dir is None:
        return report

    version = f"local-{report.sha7}"
    result: ExtractResult = extract_pack_schemas(
        pack_dir,
        pack_name=pack.name,
        version=version,
        only_classes=set(pack.classes),
        allow_import=True,
        scratch_dir=TMP_ROOT,
    )
    report.method = result.method
    report.failures.extend(result.failures)

    if not result.entries:
        if not report.failures:
            report.failures.append("no classes extracted")
        return report

    report.class_count = len(result.entries)
    write_cache(pack, version, result.entries, index, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", action="append", help="Only process the named pack; can be repeated.")
    parser.add_argument("--keep", action="store_true", help="Keep .tmp_packs clones after extraction.")
    return parser.parse_args()


def main() -> int:
    os.chdir(ROOT)
    args = parse_args()
    index = load_index()
    original_index = dict(index)
    selected = missing_packs(index)
    if args.pack:
        wanted = set(args.pack)
        selected = [pack for pack in get_known_node_packs() if pack.name in wanted]

    print(f"Missing packs: {', '.join(pack.name for pack in selected) or '(none)'}")
    reports = [process_pack(pack, index) for pack in selected]
    if index != original_index:
        INDEX_PATH.write_text(json.dumps(dict(sorted(index.items())), indent=2) + "\n", encoding="utf-8")

    print("\nReport:")
    for report in reports:
        print(f"- {report.name}: {report.class_count} classes, method={report.method or 'none'}")
        if report.cache_file:
            print(f"  cache: {report.cache_file}")
        if report.warnings:
            print("  warnings:")
            for warning in report.warnings:
                print(f"    - {warning}")
        if report.failures:
            print("  failures:")
            for failure in report.failures:
                print(f"    - {failure}")

    if not args.keep:
        script = TMP_ROOT / "_import_extract.py"
        if script.exists():
            script.unlink()

    return 1 if any(report.failures and report.class_count == 0 for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
