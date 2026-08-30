"""copy-to-recipe command — materialize a ready template for hand-editing.

Resolves a ready-template ID to its source file, strips generation markers
and headers when ``--strip-markers`` is set, optionally appends a runner
block when ``--with-runner`` is used (default false), and writes to the
requested ``--out`` path.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from vibecomfy.registry.ready import (
    repo_ready_template_id_for_path,
    repo_ready_template_paths,
    repo_ready_template_root,
)

_HEADER_RE = re.compile(
    r"^#\s*vibecomfy:\s*(?:generated|manual).*?(?=\n\n)",
    re.DOTALL,
)

_GENERATED_RE = re.compile(
    r"# vibecomfy: generated.*?(?:\n|$)",
)

_MANUAL_RE = re.compile(
    r"# vibecomfy: manual.*?(?:\n|$)",
)


def _cmd_copy_to_recipe(args: argparse.Namespace) -> int:
    template_id: str = args.id
    out_path: Path = Path(args.out)
    strip_markers: bool = getattr(args, "strip_markers", False)
    with_runner: bool = getattr(args, "with_runner", False)

    # Resolve template ID to path
    source_path = _resolve_template_path(template_id)
    if source_path is None:
        print(f"Ready template not found: {template_id!r}", __import__("sys").stderr)
        return 1

    try:
        source_text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Failed to read {source_path}: {exc}", __import__("sys").stderr)
        return 1

    # Strip markers if requested
    if strip_markers:
        source_text = _strip_markers(source_text)

    # Optionally append runner
    if with_runner:
        source_text = _append_runner(source_text, template_id)

    # Write output
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(source_text, encoding="utf-8")
    except OSError as exc:
        print(f"Failed to write {out_path}: {exc}", __import__("sys").stderr)
        return 1

    print(f"Copied {template_id!r} → {out_path}")
    if strip_markers:
        print("  (markers stripped)")
    if with_runner:
        print("  (runner block appended)")
    return 0


def _resolve_template_path(template_id: str) -> Path | None:
    """Resolve a ready-template ID to its source file path."""
    ready_root = repo_ready_template_root()
    # Try repo paths first
    for path in repo_ready_template_paths(ready_root):
        rid = repo_ready_template_id_for_path(path, ready_root)
        if rid == template_id:
            return path

    # Try as a direct path
    direct = Path(template_id)
    if direct.is_file():
        return direct

    # Try with .py suffix
    py_path = Path(f"{template_id}.py")
    if py_path.is_file():
        return py_path

    # Try under ready_templates
    rt_path = ready_root / f"{template_id}.py"
    if rt_path.is_file():
        return rt_path

    return None


def _strip_markers(source: str) -> str:
    """Strip generation/marker header comments from source text."""
    # Remove first-line markers
    lines = source.splitlines(keepends=True)
    result_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if _GENERATED_RE.match(stripped) or _MANUAL_RE.match(stripped):
            continue
        result_lines.append(line)

    # Remove multi-line header blocks
    result = "".join(result_lines)

    # Strip any remaining vibecomfy: header blocks
    result = _HEADER_RE.sub("", result)

    # Clean up leading blank lines
    result = result.lstrip("\n")

    return result


def _append_runner(source: str, template_id: str) -> str:
    """Append an if __name__ == '__main__' block."""
    runner = f"""

if __name__ == '__main__':
    import json
    workflow = build()
    workflow.finalize()
    api = workflow.compile('api')
    print(f"Workflow '{template_id}' compiled successfully: {{len(api)}} nodes")
    # To run: python -m vibecomfy.cli run {template_id}
"""
    return source + runner


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "copy-to-recipe",
        help="Copy a ready template to a recipes/ path for hand-editing.",
    )
    parser.add_argument("id", help="Ready template ID (e.g. video/wan_i2v)")
    parser.add_argument("--out", required=True, help="Destination file path")
    parser.add_argument(
        "--strip-markers",
        action="store_true",
        help="Remove generation/manual markers and headers",
    )
    parser.add_argument(
        "--with-runner",
        action="store_true",
        default=False,
        help="Append an if __name__ == '__main__' runner block",
    )
    parser.set_defaults(func=_cmd_copy_to_recipe)
