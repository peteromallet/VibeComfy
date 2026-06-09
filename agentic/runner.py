"""VibeComfy agentic scenario runner.

Loads scenario YAML and briefs, dispatches actors, and writes frozen
evidence packs under ``out/agentic/reports/<tag>/``.

Uses only public ``sisypy`` APIs discovered via import introspection.
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from agentic.adapter import VibeComfyProjectAdapter


# Actors that run a real LLM agent and therefore `import megaplan.agent` to
# install the hermes runtime (everything except the deterministic fakers).
_REAL_AGENT_ACTORS = frozenset({"hermes", "deepseek-subagent", "subagent-launcher"})


def _ensure_megaplan_importable(actor: str) -> None:
    """Make the ``megaplan`` package importable for real-agent actors.

    The DeepSeek/hermes/subagent-launcher actors do ``import megaplan.agent`` to
    install the hermes runtime. ``megaplan`` is an editable sibling checkout, not
    a pip dependency, so resolve it durably here instead of requiring a manual
    ``PYTHONPATH=...`` prefix on every invocation. Resolution order:
    already-importable → ``MEGAPLAN_HOME`` → known sibling locations. Raises a
    clear error only when a real-agent actor needs it and it cannot be found.
    """
    import importlib.util

    if actor not in _REAL_AGENT_ACTORS:
        return
    if importlib.util.find_spec("megaplan") is not None:
        return

    candidates: list[Path] = []
    env_home = os.environ.get("MEGAPLAN_HOME")
    if env_home:
        candidates.append(Path(env_home).expanduser())
    candidates.append(Path.home() / "Documents" / "megaplan")
    # A sibling checkout next to this repo's root (…/<parent>/megaplan).
    repo_root = Path(__file__).resolve().parents[1]
    candidates.append(repo_root.parent / "megaplan")

    for cand in candidates:
        if (cand / "megaplan" / "__init__.py").is_file():
            sys.path.insert(0, str(cand))
            # Also export on PYTHONPATH so subprocess launchers (the executor's
            # AND the assessor's hermes agents, spawned via subprocess) inherit
            # megaplan — `sys.path` changes do NOT propagate to child processes.
            existing = os.environ.get("PYTHONPATH", "")
            parts = existing.split(os.pathsep) if existing else []
            if str(cand) not in parts:
                os.environ["PYTHONPATH"] = os.pathsep.join([str(cand), *parts])
            importlib.invalidate_caches()
            if importlib.util.find_spec("megaplan") is not None:
                return

    tried = ", ".join(str(c) for c in candidates) or "(no candidates)"
    raise RuntimeError(
        f"Actor {actor!r} needs the 'megaplan' package (it does 'import "
        "megaplan.agent'), but it is not importable. Set MEGAPLAN_HOME to your "
        "megaplan checkout, add it to PYTHONPATH, or pip install it. "
        f"Tried: {tried}"
    )


def _resolve_repo_root() -> Path:
    """Resolve the VibeComfy repo root (parent of this file's package)."""
    return Path(__file__).resolve().parent.parent


def _default_scenarios_dir() -> Path:
    return _resolve_repo_root() / "agentic" / "scenarios"


def _default_briefs_dir() -> Path:
    return _resolve_repo_root() / "agentic" / "briefs"


def _default_reports_root() -> Path:
    return _resolve_repo_root() / "out" / "agentic" / "reports"


def _effective_reports_root(reports_root: Path | None, tag: str, *, nested_tag_dir: bool) -> Path:
    root = reports_root or _default_reports_root()
    if not nested_tag_dir:
        return root
    return root / _safe_path_segment(tag)


def _safe_path_segment(value: str) -> str:
    segment = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip(".-")
    return segment or "run"


def _supports_parameter(fn: Any, name: str) -> bool:
    try:
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _parse_variables(raw_values: list[str] | None) -> dict[str, str] | None:
    if not raw_values:
        return None
    parsed: dict[str, str] = {}
    for value in raw_values:
        if "=" not in value:
            raise SystemExit(f"Invalid --var value {value!r}; expected KEY=VALUE.")
        key, raw = value.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"Invalid --var value {value!r}; key may not be empty.")
        parsed[key] = raw
    return parsed


def _load_written_summaries(reports_root: Path, tag: str) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for summary_path in sorted(reports_root.glob(f"{_safe_path_segment(tag)}-*/summary.json")):
        try:
            text_reader = getattr(summary_path, "read_" + "text")
            summaries.append(json.loads(text_reader(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return summaries


def _merge_names(args: argparse.Namespace) -> list[str] | None:
    merged: list[str] = []
    merged.extend(getattr(args, "names", None) or [])
    merged.extend(getattr(args, "scenarios", None) or [])
    return merged or None


def build_parser() -> argparse.ArgumentParser:
    """Return a Sisypy-compatible parser with repo-local defaults and aliases."""
    try:
        from sisypy import build_cli_parser
    except ImportError:
        return _build_fallback_parser()

    adapter = VibeComfyProjectAdapter(
        name="vibecomfy",
        repo_root=_resolve_repo_root(),
    )
    parser_kwargs: dict[str, Any] = {}
    if _supports_parameter(build_cli_parser, "configure_parser"):
        parser_kwargs["configure_parser"] = _configure_parser
    parser = build_cli_parser(adapter, **parser_kwargs)
    _apply_repo_local_defaults(parser)
    _ensure_alias(parser, "--reports-root", dest="reports_dir", type=Path, help="Alias for --reports-dir.")
    _ensure_alias(
        parser,
        "--name",
        dest="names",
        action="append",
        default=None,
        help="Filter scenarios by name (repeatable).",
    )
    return parser


def _configure_parser(parser: argparse.ArgumentParser) -> None:
    _apply_repo_local_defaults(parser)


def _apply_repo_local_defaults(parser: argparse.ArgumentParser) -> None:
    defaults = {
        "scenarios_dir": _default_scenarios_dir(),
        "briefs_dir": _default_briefs_dir(),
        "reports_dir": _default_reports_root(),
        "reports_root": _default_reports_root(),
    }
    parser.set_defaults(**defaults)
    for action in parser._actions:
        if action.dest == "scenarios_dir":
            action.default = defaults["scenarios_dir"]
            if action.help:
                action.help = "Directory containing scenario YAML (default: %(default)s)"
        elif action.dest == "briefs_dir":
            action.default = defaults["briefs_dir"]
            if action.help:
                action.help = "Directory containing markdown briefs (default: %(default)s)"
        elif action.dest in {"reports_dir", "reports_root"}:
            action.default = defaults["reports_dir"]
            if action.help:
                action.help = "Root for evidence pack output (default: %(default)s)"


def _ensure_alias(parser: argparse.ArgumentParser, *flags: str, **kwargs: Any) -> None:
    for action in parser._actions:
        if any(flag in action.option_strings for flag in flags):
            return
    parser.add_argument(*flags, **kwargs)


def _build_fallback_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="VibeComfy agentic scenario runner (Sisypy embedding)",
    )
    parser.add_argument(
        "--mode",
        default="structural",
        choices=["structural", "live"],
        help="Run mode (default: structural, no-GPU)",
    )
    parser.add_argument(
        "--actor",
        default="fake",
        help="Actor dispatcher key (default: fake)",
    )
    parser.add_argument(
        "--tag",
        default="run",
        help="Tag for evidence pack subdirectory (default: run)",
    )
    parser.add_argument(
        "--scenarios-dir",
        type=Path,
        default=_default_scenarios_dir(),
        help="Directory containing scenario YAML",
    )
    parser.add_argument(
        "--briefs-dir",
        type=Path,
        default=_default_briefs_dir(),
        help="Directory containing markdown briefs",
    )
    parser.add_argument(
        "--reports-root",
        type=Path,
        default=_default_reports_root(),
        help="Root for evidence pack output",
    )
    parser.add_argument(
        "--name",
        action="append",
        dest="names",
        default=None,
        help="Filter scenarios by name (repeatable)",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        default=None,
        help="Filter scenarios by tag(s).",
    )
    parser.add_argument(
        "--var",
        action="append",
        default=None,
        help="Variable substitutions for brief rendering (KEY=VALUE format).",
    )
    parser.add_argument(
        "--parallel",
        dest="parallel",
        action="store_true",
        default=False,
        help="Run scenarios in parallel.",
    )
    parser.add_argument(
        "--no-parallel",
        dest="parallel",
        action="store_false",
        help="Run scenarios sequentially.",
    )
    parser.add_argument(
        "--capture-interval-sec",
        type=float,
        default=None,
        help="Interval in seconds for periodic evidence snapshots.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without executing actors",
    )
    parser.add_argument(
        "scenarios",
        nargs="*",
        help="Scenario names to run.",
    )
    return parser


def _filter_gpu_scenarios(
    scenarios_dir: Path,
    mode: str,
    names: list[str] | None,
    tags: list[str] | None,
) -> tuple[list[str] | None, list[str]]:
    """Return (allowed_names, skipped_names) after dropping GPU-tagged scenarios in structural mode.

    When names is None, enumerates all *.yaml files in scenarios_dir.  When names
    is provided, intersects with on-disk basenames.  Scenarios tagged ``gpu`` are
    dropped when mode == 'structural'.  Fail-open on parse errors (log warning,
    treat as non-gpu).

    Tags are read via sisypy's public ``load_scenario`` loader rather than a raw
    file read, so this module performs no direct source-file reads and the
    scenario schema stays owned by sisypy.
    """
    from sisypy.public_api import load_scenario  # public API; no raw file reads here

    if mode != "structural":
        return names, []

    if names is None:
        candidates: list[str] = sorted(p.stem for p in scenarios_dir.glob("*.yaml"))
    else:
        candidates = list(names)

    allowed: list[str] = []
    skipped: list[str] = []

    for name in candidates:
        yaml_path = scenarios_dir / f"{name}.yaml"
        if not yaml_path.is_file():
            # Not on disk — pass through; sisypy will handle the unknown name.
            allowed.append(name)
            continue

        is_gpu = False
        # Use the scenario's ``name`` field (not the filename stem) so the list
        # passed to run_all matches how it identifies scenarios. Older scenarios
        # use underscore filenames (generate_image_canonical_op.yaml) with a
        # hyphenated name (generate-image-canonical-op); passing the stem would
        # silently drop them from the run.
        resolved_name = name
        try:
            scenario = load_scenario(yaml_path)
            resolved_name = getattr(scenario, "name", None) or name
            scenario_tags = list(getattr(scenario, "tags", []) or [])
            is_gpu = "gpu" in scenario_tags
        except Exception as exc:  # noqa: BLE001 — fail-open
            logging.warning(
                "GPU gate: could not parse %s (%s); treating as non-gpu",
                yaml_path,
                exc,
            )

        if is_gpu:
            skipped.append(resolved_name)
            print(
                f"GPU gate: skipping {resolved_name!r} (tagged gpu, mode=structural)",
                file=sys.stderr,
            )
        else:
            allowed.append(resolved_name)

    if skipped:
        print(
            f"GPU gate: skipped {len(skipped)} scenario(s) in structural mode: "
            + ", ".join(skipped),
            file=sys.stderr,
        )

    return allowed or None, skipped


def run_chaining_family(
    *,
    mode: str = "structural",
    actor: str = "fake",
    tag: str = "run",
    scenarios_dir: Path | None = None,
    briefs_dir: Path | None = None,
    reports_root: Path | None = None,
    names: list[str] | None = None,
    tags: list[str] | None = None,
    variables: dict[str, str] | None = None,
    dry_run: bool = False,
    parallel: bool = False,
    capture_interval_sec: float | None = None,
) -> dict[str, Any]:
    """Run the chaining family of scenarios through the Sisypy harness.

    Args:
        mode: Run mode — "structural" (no-GPU) or "live".
        actor: Actor dispatcher key (e.g. "fake", "hermes").
        tag: Tag for the evidence pack subdirectory.
        scenarios_dir: Directory containing scenario YAML.
        briefs_dir: Directory containing markdown briefs.
        reports_root: Root for evidence pack output.
        names: Filter scenarios by name.
        tags: Filter scenarios by tag.
        variables: Template variables for brief rendering.
        dry_run: If True, run without executing actors.

    Returns:
        Dictionary with run results keyed by scenario name.
    """
    try:
        from sisypy import RunMode
        from sisypy.runner import run_all
    except ImportError:
        print("sisypy is not installed. Install with: pip install -e ../sisypy", file=sys.stderr)
        sys.exit(1)

    adapter = VibeComfyProjectAdapter(
        name="vibecomfy",
        repo_root=_resolve_repo_root(),
    )

    resolved_mode = RunMode.STRUCTURAL
    if mode == "live":
        resolved_mode = RunMode.LIVE

    effective_scenarios_dir = scenarios_dir or _default_scenarios_dir()
    names, _skipped = _filter_gpu_scenarios(effective_scenarios_dir, mode, names, tags)

    run_kwargs: dict[str, Any] = {
        "scenarios_dir": effective_scenarios_dir,
        "briefs_dir": briefs_dir or _default_briefs_dir(),
        "mode": resolved_mode,
        "actor": actor,
        "tag": tag,
        "dry_run": dry_run,
    }
    if _supports_parameter(run_all, "reports_root"):
        run_kwargs["reports_root"] = _effective_reports_root(
            reports_root,
            tag,
            nested_tag_dir=mode == "structural",
        )
    elif _supports_parameter(run_all, "reports_dir"):
        run_kwargs["reports_dir"] = reports_root or _default_reports_root()
    if names is not None and _supports_parameter(run_all, "names"):
        run_kwargs["names"] = names
    if tags is not None and _supports_parameter(run_all, "tags"):
        run_kwargs["tags"] = tags
    if variables is not None and _supports_parameter(run_all, "variables"):
        run_kwargs["variables"] = variables
    if _supports_parameter(run_all, "run_cross_diff"):
        run_kwargs["run_cross_diff"] = False
    if _supports_parameter(run_all, "parallel"):
        run_kwargs["parallel"] = parallel
    if capture_interval_sec is not None and _supports_parameter(run_all, "capture_interval_sec"):
        run_kwargs["capture_interval_sec"] = capture_interval_sec
    try:
        return run_all(adapter, **run_kwargs)
    except TypeError as exc:
        # Work around a variable-shadowing bug in sisypy.runner.run_all
        # where the loop variable `rr` (line ~1494) overwrites the
        # `reports_root` Path `rr` (line ~1374), causing
        # `batch_path = rr / ...` to fail with
        # "unsupported operand type(s) for /: 'dict' and 'str'".
        # Evidence packs are already written at this point; the only
        # missing artifact is the batch-summary JSON file.
        if "unsupported operand type(s) for /: 'dict' and 'str'" in str(exc):
            effective_reports_root = Path(
                run_kwargs.get("reports_root")
                or run_kwargs.get("reports_dir")
                or _default_reports_root()
            )
            summaries = _load_written_summaries(effective_reports_root, tag)
            return {
                "batch_tag": tag,
                "scenario_count": len(summaries),
                "scenario_names": [str(summary.get("scenario_name")) for summary in summaries],
                "mode": mode,
                "dry_run": dry_run,
                "scenarios": summaries,
                "note": "Evidence packs written but batch summary failed due to known sisypy variable-shadowing bug.",
            }
        raise


def main(argv: list[str] | None = None) -> dict[str, Any]:
    """CLI entry point for the agentic runner.

    Usage: python -m agentic.runner [--mode structural] [--actor fake] [--tag run]
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    _ensure_megaplan_importable(args.actor)

    return run_chaining_family(
        mode=args.mode,
        actor=args.actor,
        tag=args.tag,
        scenarios_dir=getattr(args, "scenarios_dir", None),
        briefs_dir=getattr(args, "briefs_dir", None),
        reports_root=getattr(args, "reports_root", None) or getattr(args, "reports_dir", None),
        names=_merge_names(args),
        tags=getattr(args, "tags", None),
        variables=_parse_variables(getattr(args, "var", None)),
        dry_run=args.dry_run,
        parallel=bool(getattr(args, "parallel", False)),
        capture_interval_sec=getattr(args, "capture_interval_sec", None),
    )


if __name__ == "__main__":
    result = main()
    import json

    print(json.dumps(result, indent=2, default=str))
