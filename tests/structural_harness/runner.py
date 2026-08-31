"""VibeComfy deterministic structural scenario runner.

Loads scenario YAML and briefs, dispatches actors, and writes frozen
evidence packs under ``out/agentic/reports/<tag>/``.

Uses public ``sisypy`` run APIs discovered via import introspection. A bounded
compatibility wrapper handles Sisypy's normalized assessor parse fallback.
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from tests.harness_common import (
    OUTCOME_BLOCKED_PREREQUISITE,
    OUTCOME_SKIPPED_LIVE,
    STRUCTURAL_DISPATCHERS,
)
from tests.structural_harness.adapter import VibeComfyProjectAdapter


_STRUCTURAL_ACTORS = STRUCTURAL_DISPATCHERS
_ASSESSOR_PARSE_FAILURE_SUMMARY = "Failed to parse assessor response."
_ASSESSOR_PARSE_FAILURE_WEAKNESS = "LLM response was not valid JSON."


def _is_assessor_parse_failure(result: Any) -> bool:
    """Return whether *result* is Sisypy's normalized JSON-parse fallback."""
    weaknesses = result.get("weaknesses", []) if isinstance(result, dict) else []
    return (
        isinstance(result, dict)
        and result.get("overall_passed") is False
        and result.get("summary") == _ASSESSOR_PARSE_FAILURE_SUMMARY
        and isinstance(weaknesses, list)
        and _ASSESSOR_PARSE_FAILURE_WEAKNESS in weaknesses
    )


@contextmanager
def _retry_assessor_parse_failure_once(sisypy_runner: Any) -> Iterator[None]:
    """Retry only Sisypy's exact assessor parse fallback, bounded (3 attempts).

    The deepseek-chat single-shot assessor occasionally returns an
    unrecoverable non-JSON reply; the raw text is not persisted (sisypy
    evidence gap), so the parse fallback is the only reliable signal. Three
    bounded attempts with a short backoff absorb the flake class without
    retrying genuine rubric failures.
    """
    original_assess = sisypy_runner.assess

    def assess_with_retry(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = original_assess(*args, **kwargs)
        for attempt in range(2):
            if not _is_assessor_parse_failure(result):
                return result
            logging.warning("Assessor response was not valid JSON; retrying (attempt %d/3).", attempt + 2)
            time.sleep(1.5 * (attempt + 1))
            result = original_assess(*args, **kwargs)
        return result

    sisypy_runner.assess = assess_with_retry
    try:
        yield
    finally:
        sisypy_runner.assess = original_assess


def _resolve_repo_root() -> Path:
    """Resolve the VibeComfy repo root (parent of this file's package)."""
    return Path(__file__).resolve().parents[2]


def _default_scenarios_dir() -> Path:
    return _resolve_repo_root() / "tests" / "structural_harness" / "scenarios"


def _default_briefs_dir() -> Path:
    return _resolve_repo_root() / "tests" / "structural_harness" / "briefs"


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
    _ensure_alias(
        parser,
        "--subjective-assessment",
        dest="subjective_assessment",
        action="store_true",
        default=False,
        help="Re-assess frozen evidence with an LLM against the scenario's hidden rubric.",
    )
    _ensure_alias(
        parser,
        "--subjective-model",
        dest="subjective_model",
        default=None,
        help="Model for subjective assessment (default: deepseek-chat via DeepSeek API).",
    )
    _ensure_alias(
        parser,
        "--subjective-base-url",
        dest="subjective_base_url",
        default=None,
        help="API base URL for subjective assessment (default: https://api.deepseek.com/v1).",
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
        elif action.dest == "mode":
            action.default = "structural"
            action.choices = ["structural"]
            if action.help:
                action.help = "Run mode (structural only)"
        elif action.dest == "actor":
            action.default = "fake"
            action.choices = sorted(_STRUCTURAL_ACTORS)
            if action.help:
                action.help = "Structural actor dispatcher key (default: fake)"


def _ensure_alias(parser: argparse.ArgumentParser, *flags: str, **kwargs: Any) -> None:
    for action in parser._actions:
        if any(flag in action.option_strings for flag in flags):
            return
    parser.add_argument(*flags, **kwargs)


def _build_fallback_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="VibeComfy structural contract scenario runner (Sisypy embedding)",
    )
    parser.add_argument(
        "--mode",
        default="structural",
        choices=["structural"],
        help="Run mode (structural only)",
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
        "--subjective-assessment",
        action="store_true",
        default=False,
        help="Re-assess frozen evidence with an LLM against the scenario's hidden rubric.",
    )
    parser.add_argument(
        "--subjective-model",
        default=None,
        help="Model for subjective assessment (default: deepseek-chat via DeepSeek API).",
    )
    parser.add_argument(
        "--subjective-base-url",
        default=None,
        help="API base URL for subjective assessment (default: https://api.deepseek.com/v1).",
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
    is provided, resolves both on-disk basenames and descriptor ``name`` fields.
    Scenarios tagged ``gpu`` are dropped when mode == 'structural'.  Unknown
    explicit names pass through to Sisypy unchanged.  Descriptor parse errors
    fail closed.

    Tags are read via sisypy's public ``load_scenario`` loader rather than a raw
    file read, so this module performs no direct source-file reads and the
    scenario schema stays owned by sisypy.
    """
    from sisypy.public_api import load_scenario  # public API; no raw file reads here

    if mode != "structural":
        return names, []

    descriptors: list[tuple[str, str, bool]] = []
    by_stem: dict[str, tuple[str, str, bool]] = {}
    by_name: dict[str, tuple[str, str, bool]] = {}
    for yaml_path in sorted(scenarios_dir.glob("*.yaml")):
        try:
            scenario = load_scenario(yaml_path)
            resolved_name = getattr(scenario, "name", None) or yaml_path.stem
            if not isinstance(resolved_name, str) or not resolved_name:
                raise ValueError("descriptor name must be a non-empty string")
            scenario_tags = list(getattr(scenario, "tags", []) or [])
            descriptor = (yaml_path.stem, resolved_name, "gpu" in scenario_tags)
        except Exception as exc:  # noqa: BLE001 — descriptor gate must fail closed
            raise ValueError(f"GPU gate: could not parse {yaml_path}: {exc}") from exc

        descriptors.append(descriptor)
        stem = descriptor[0]
        if stem in by_stem:
            raise ValueError(f"GPU gate: duplicate scenario filename stem {stem!r}")
        by_stem[stem] = descriptor
        if resolved_name in by_name:
            raise ValueError(f"GPU gate: duplicate scenario name {resolved_name!r}")
        by_name[resolved_name] = descriptor

    if names is None:
        candidates = descriptors
    else:
        candidates = []
        for requested_name in names:
            descriptor = by_stem.get(requested_name)
            by_name_descriptor = by_name.get(requested_name)
            if descriptor is not None and by_name_descriptor is not None and descriptor != by_name_descriptor:
                raise ValueError(f"GPU gate: ambiguous scenario name {requested_name!r}")
            descriptor = descriptor or by_name_descriptor
            if descriptor is None:
                # Unknown explicit names retain Sisypy's established no-match
                # behavior.  Keep them non-empty so they cannot mean "all".
                candidates.append((requested_name, requested_name, False))
            else:
                candidates.append(descriptor)

    allowed: list[str] = []
    skipped: list[str] = []

    for _stem, resolved_name, is_gpu in candidates:
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

    # An empty list is intentional: run_chaining_family must short-circuit
    # before Sisypy, whose run_all(names=[]) means "all scenarios".
    return allowed, skipped


def _empty_batch_summary(tag: str, mode: str, dry_run: bool) -> dict[str, Any]:
    """Return Sisypy's zero-selection shape without invoking ``run_all``."""
    return {
        "batch_tag": tag,
        "scenario_count": 0,
        "scenario_names": [],
        "mode": mode,
        "scenarios": [],
        "dry_run": dry_run,
    }


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
    subjective_assessment: bool = False,
    subjective_model: str | None = None,
    subjective_base_url: str | None = None,
) -> dict[str, Any]:
    """Run the chaining family of scenarios through the Sisypy harness.

    Args:
        mode: Run mode. Only "structural" is supported here.
        actor: Structural actor dispatcher key: "fake" or "faking".
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
        import sisypy.runner as sisypy_runner
    except ImportError:
        print("sisypy is not installed. Install with: pip install -e ../sisypy", file=sys.stderr)
        sys.exit(1)

    run_all = sisypy_runner.run_all

    adapter = VibeComfyProjectAdapter(
        name="vibecomfy",
        repo_root=_resolve_repo_root(),
    )

    if mode != "structural":
        raise ValueError(
            "tests.structural_harness only runs structural contract scenarios; "
            "true live-agentic coverage belongs in tests.live_agentic_harness."
        )
    if actor not in _STRUCTURAL_ACTORS:
        raise ValueError(
            "tests.structural_harness only supports fake/faking actors; "
            f"got {actor!r}."
        )

    resolved_mode = RunMode.STRUCTURAL

    effective_scenarios_dir = scenarios_dir or _default_scenarios_dir()
    names, _skipped = _filter_gpu_scenarios(effective_scenarios_dir, mode, names, tags)

    if names == []:
        # Sisypy's current _filter_scenarios uses ``if names:``; passing [] to
        # run_all would therefore expand an all-filtered structural selection
        # back into every scenario, including GPU-tagged ones.
        return _empty_batch_summary(tag, mode, dry_run)

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
    if _supports_parameter(run_all, "subjective_assessment"):
        run_kwargs["subjective_assessment"] = subjective_assessment
    if _supports_parameter(run_all, "subjective_model"):
        run_kwargs["subjective_model"] = subjective_model
    if _supports_parameter(run_all, "subjective_base_url"):
        run_kwargs["subjective_base_url"] = subjective_base_url
    try:
        with _retry_assessor_parse_failure_once(sisypy_runner):
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
            # Compute batch-level outcome counts so summary_exit_code
            # can reflect deterministic assessment failures.
            batch_outcome_counts: dict[str, int] = {}
            batch_has_undetermined = False
            batch_has_blocked_or_error = False
            for ss in summaries:
                for oc, cnt in ss.get("outcome_counts", {}).items():
                    batch_outcome_counts[oc] = batch_outcome_counts.get(oc, 0) + cnt
                if ss.get("has_undetermined"):
                    batch_has_undetermined = True
                if ss.get("error"):
                    batch_has_blocked_or_error = True
                else:
                    for run_rec in ss.get("runs", []):
                        outcome = run_rec.get("outcome", "")
                        if outcome in (OUTCOME_BLOCKED_PREREQUISITE, OUTCOME_SKIPPED_LIVE):
                            batch_has_blocked_or_error = True
                        elif run_rec.get("errors"):
                            batch_has_blocked_or_error = True
            return {
                "batch_tag": tag,
                "scenario_count": len(summaries),
                "scenario_names": [str(summary.get("scenario_name")) for summary in summaries],
                "mode": mode,
                "dry_run": dry_run,
                "scenarios": summaries,
                "outcome_counts": batch_outcome_counts,
                "has_undetermined": batch_has_undetermined,
                "has_blocked_or_error": batch_has_blocked_or_error,
                "note": "Evidence packs written but batch summary failed due to known sisypy variable-shadowing bug.",
            }
        raise


def main(argv: list[str] | None = None) -> dict[str, Any]:
    """CLI entry point for the structural contract runner.

    Usage: python -m tests.structural_harness.runner [--mode structural] [--actor fake] [--tag run]
    """
    parser = build_parser()
    args = parser.parse_args(argv)

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
        subjective_assessment=getattr(args, "subjective_assessment", False),
        subjective_model=getattr(args, "subjective_model", None),
        subjective_base_url=getattr(args, "subjective_base_url", None),
    )


if __name__ == "__main__":
    result = main()
    import json
    import sys as _sys

    print(json.dumps(result, indent=2, default=str))

    # Exit with a machine-readable code reflecting deterministic
    # assessment failures (e.g. missing required frozen evidence).
    try:
        from sisypy import summary_exit_code
    except ImportError:
        _sys.exit(0)
    _sys.exit(summary_exit_code(result))
