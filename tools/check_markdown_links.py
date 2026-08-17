"""Check tracked Markdown files for broken local links."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)")
EXTERNAL_SCHEMES = {"http", "https", "mailto", "tel"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check tracked Markdown files for broken local links.")
    parser.add_argument("paths", nargs="*", type=Path, help="Markdown files or directories to scan.")
    args = parser.parse_args(argv)

    failures: list[str] = []
    for path in _markdown_files(args.paths):
        failures.extend(_broken_links(path))

    if failures:
        print("Broken Markdown links:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    return 0


def _markdown_files(paths: list[Path]) -> list[Path]:
    if paths:
        files: list[Path] = []
        for path in paths:
            resolved = path if path.is_absolute() else REPO_ROOT / path
            if resolved.is_dir():
                files.extend(p for p in resolved.rglob("*.md") if _is_tracked(p))
            elif resolved.suffix.lower() == ".md" and _is_tracked(resolved):
                files.append(resolved)
        return sorted(set(files))

    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    # `.oracle/` is a per-run artifact tree (findings/checkins/measurements/briefs),
    # not documentation: its links point at historical run clones and files that
    # intentionally rot between runs, so doc-link hygiene does not apply.
    return [
        REPO_ROOT / line
        for line in result.stdout.splitlines()
        if line and not line.startswith(".oracle/")
    ]


def _is_tracked(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _broken_links(path: Path) -> list[str]:
    failures: list[str] = []
    rel_path = path.relative_to(REPO_ROOT).as_posix()
    text = path.read_text(encoding="utf-8")
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in MARKDOWN_LINK_RE.finditer(line):
            target = _clean_target(match.group(1))
            if not target or _is_ignored_target(target):
                continue
            target_path = unquote(urlsplit(target).path)
            if not target_path:
                continue
            candidate = (REPO_ROOT / target_path.lstrip("/")) if target_path.startswith("/") else path.parent / target_path
            if not candidate.exists():
                failures.append(f"{rel_path}:{line_number}: {target}")
    return failures


def _clean_target(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if " " in target:
        target = target.split()[0]
    return target


def _is_ignored_target(target: str) -> bool:
    if target.startswith("#"):
        return True
    scheme = urlsplit(target).scheme.lower()
    return scheme in EXTERNAL_SCHEMES or target.startswith("data:")


if __name__ == "__main__":
    raise SystemExit(main())
