"""Live agentic harness runner for VibeComfy headless scenarios.

Scenarios run CONCURRENTLY — each in its own subprocess (process isolation +
kill-on-timeout via ``subprocess.run``), bounded by ``--max-workers``. Modeled
on the subagent-launcher fanout: one process per task, a bounded pool, a
per-task timeout. ``--single`` is the per-scenario subprocess entry point.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.agent.deepseek_usage import (
    add_deepseek_usage,
    coerce_deepseek_usage,
    combine_deepseek_cost_bases,
)

from .failure_analysis import (
    DEFAULT_AGENT_TIMEOUT_S,
    DEFAULT_ANALYSIS_MODEL,
    DEFAULT_ANALYSIS_WORKERS,
    DEFAULT_RECOMMENDATIONS_MODEL,
    analyze_failures,
    prepare_failure_analysis,
    recommendations_for_run,
)

DEFAULT_MAX_WORKERS = 12
DEFAULT_PER_SCENARIO_TIMEOUT = 1200  # seconds; kills a wedged/over-slow scenario
DEFAULT_PROGRESS_EVERY = 10
DEFAULT_INFRA_RETRIES = 1
REPO = Path(__file__).resolve().parents[2]

def _scenario_paths(scenarios_dir: Path) -> list[Path]:
    if not scenarios_dir.is_dir():
        return []
    return sorted(p for p in scenarios_dir.iterdir() if p.suffix in {".yaml", ".yml", ".json"})


def _load_scenario(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _output_dir_for(output_base: Any, tag: str, scenario_id: str) -> Path:
    base = Path(output_base) if output_base else Path("out/agentic")
    return Path(base) / tag / scenario_id


def _run_dir_for(output_base: Any, tag: str) -> Path:
    base = Path(output_base) if output_base else Path("out/agentic")
    return Path(base) / tag


def _trim(s: str) -> str:
    return s if len(s) <= 400 else s[-400:]


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _scenario_expect_graph_changed(scenario: dict[str, Any] | None) -> bool:
    assessment = scenario.get("assessment") if isinstance(scenario, dict) else None
    if isinstance(assessment, dict) and "expect_graph_changed" in assessment:
        return bool(assessment["expect_graph_changed"])
    return False


def _synthetic_guard(
    detail: str,
    *,
    failure_class: str = "runner_error",
    expect_graph_changed: bool = False,
) -> dict[str, Any]:
    """A failing guard for scenarios that errored/timed out in the runner itself."""
    return {
        "live_agentic_success": False,
        "metadata_success": False,
        "failure_class": failure_class,
        "score_class": "infra_blocked" if failure_class.startswith("infra_") else "product_fail",
        "assessment": {
            "passed": False,
            "expect_graph_changed": expect_graph_changed,
            "issue_count": 1,
            "error_count": 1,
            "issues": [
                {
                    "check": "runner",
                    "severity": "error",
                    "detail": detail,
                    "failure_class": failure_class,
                }
            ],
        },
    }


def _failure_summary(
    scenario_id: str,
    output_base: Any,
    tag: str,
    detail: str,
    *,
    failure_class: str = "runner_error",
    attempt: int | None = None,
    expect_graph_changed: bool = False,
    stdout_tail: str | None = None,
    stderr_tail: str | None = None,
    elapsed_s: float | None = None,
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "status": "error",
        "ok": False,
        "error": detail,
        "output_dir": str(_output_dir_for(output_base, tag, scenario_id)),
        "guard": _synthetic_guard(
            detail,
            failure_class=failure_class,
            expect_graph_changed=expect_graph_changed,
        ),
        "failure_class": failure_class,
        "score_class": "infra_blocked" if failure_class.startswith("infra_") else "product_fail",
        "retryable_infra": failure_class.startswith("infra_"),
        "agent_exercised": False,
        "attempt": attempt,
        "elapsed_s": elapsed_s,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "deepseek_usage": {},
        "deepseek_est_cost_usd": 0.0,
        "deepseek_cost_basis": "not_available",
    }


def _persist_scenario_summary(summary: dict[str, Any], output_base: Any, tag: str) -> None:
    scenario_id = str(summary.get("scenario_id") or "")
    if not scenario_id:
        return
    output_dir = Path(summary.get("output_dir") or _output_dir_for(output_base, tag, scenario_id))
    _write_json_atomic(output_dir / "agentic_summary.json", summary)


def _persist_canonical_scenario_summary(
    summary: dict[str, Any],
    output_base: Any,
    tag: str,
    scenario_id: str,
) -> None:
    _write_json_atomic(_output_dir_for(output_base, tag, scenario_id) / "agentic_summary.json", summary)


def _attempt_tag(tag: str, scenario_id: str, attempt: int) -> str:
    return f"{tag}/attempts/{scenario_id}/attempt_{attempt}"


def _attempt_record(summary: dict[str, Any], *, attempt: int) -> dict[str, Any]:
    return {
        "attempt": attempt,
        "scenario_id": summary.get("scenario_id"),
        "status": summary.get("status"),
        "ok": summary.get("ok"),
        "output_dir": summary.get("output_dir"),
        "error": summary.get("error"),
        "failure_class": summary.get("failure_class")
        or (summary.get("guard") or {}).get("failure_class")
        or "product_or_assessment_failure",
        "score_class": summary.get("score_class") or (summary.get("guard") or {}).get("score_class"),
        "retryable_infra": bool(summary.get("retryable_infra")),
        "agent_exercised": summary.get("agent_exercised"),
        "elapsed_s": summary.get("elapsed_s"),
        "live_agentic_success": (summary.get("guard") or {}).get("live_agentic_success"),
        "model_attempts": summary.get("model_attempts", []),
    }


def _latest_failed_model_attempt(summary: Mapping[str, Any]) -> Mapping[str, Any] | None:
    attempts = summary.get("model_attempts")
    if not isinstance(attempts, (list, tuple)):
        return None
    for attempt in reversed(attempts):
        if isinstance(attempt, Mapping) and attempt.get("outcome") == "failure":
            return attempt
    return None


def _summary_completion_tokens(summary: dict[str, Any]) -> int | None:
    """Observed completion tokens of the attempt's model call, or None when absent.

    The attempt summary (agentic_summary) carries ``deepseek_usage`` at the top
    level — the executor result's usage dict.  ``completion_tokens == 0`` is the
    structured evidence of an empty/transport response; absence of the record is
    NOT evidence, so it never classifies as infra.
    """
    attempt = _latest_failed_model_attempt(summary)
    usage = attempt.get("token_usage") if isinstance(attempt, Mapping) else None
    if not isinstance(usage, Mapping):
        return None
    value = usage.get("completion_tokens")
    if not isinstance(value, (int, float)):
        return None
    return int(value)


def _provider_infra_failure_class(summary: dict[str, Any]) -> str | None:
    """Map only canonical typed attempt evidence; never inspect response prose."""
    attempt = _latest_failed_model_attempt(summary)
    if attempt is None:
        return None
    failure_type = attempt.get("failure_type")
    if failure_type == "empty_response" and _summary_completion_tokens(summary) == 0:
        return "infra_empty_response"
    if failure_type == "timeout":
        return "infra_timeout"
    if failure_type == "provider_failure":
        return "infra_provider_capacity"
    return None


def _mark_summary_as_infra(summary: dict[str, Any], failure_class: str) -> None:
    summary["failure_class"] = failure_class
    summary["score_class"] = "infra_blocked"
    summary["retryable_infra"] = failure_class == "infra_empty_response"
    guard = summary.get("guard")
    if isinstance(guard, dict):
        guard["failure_class"] = failure_class
        guard["score_class"] = "infra_blocked"
        assessment = guard.get("assessment")
        if isinstance(assessment, dict):
            assessment.setdefault("issues", []).append(
                {
                    "check": "infra_classification",
                    "severity": "warning",
                    "detail": (
                        f"{failure_class} failure was classified as "
                        "infrastructure, not product quality."
                    ),
                    "failure_class": failure_class,
                }
            )


def _classify_retryable_infra_summary(summary: dict[str, Any]) -> dict[str, Any]:
    failure_class = _provider_infra_failure_class(summary)
    if failure_class is not None and summary.get("guard", {}).get("live_agentic_success") is not True:
        _mark_summary_as_infra(summary, failure_class)
    return summary


def _is_retryable_infra_summary(summary: dict[str, Any]) -> bool:
    _classify_retryable_infra_summary(summary)
    return (
        summary.get("failure_class") == "infra_empty_response"
        and summary.get("retryable_infra") is True
        and _summary_completion_tokens(summary) == 0
    )


def _build_run_summary(
    tag: str,
    summaries: list[dict[str, Any]],
    *,
    total_scenarios: int,
    complete: bool,
) -> dict[str, Any]:
    passed = sum(1 for summary in summaries if summary["guard"].get("live_agentic_success") is True)
    failed = len(summaries) - passed
    raw_first_attempt_passed = sum(
        1
        for summary in summaries
        if summary.get("raw_first_attempt_success", summary["guard"].get("live_agentic_success")) is True
    )
    infra_failures = sum(
        1
        for summary in summaries
        if summary["guard"].get("live_agentic_success") is not True
        and str(summary.get("failure_class") or "").startswith("infra_")
    )
    score_classes: dict[str, int] = {}
    for summary in summaries:
        score_class = (
            summary.get("score_class")
            or summary["guard"].get("score_class")
            or ("pass" if summary["guard"].get("live_agentic_success") is True else "product_fail")
        )
        score_classes[str(score_class)] = score_classes.get(str(score_class), 0) + 1
    deepseek_usage = add_deepseek_usage(
        *[coerce_deepseek_usage(summary.get("deepseek_usage")) for summary in summaries]
    )
    deepseek_est_cost_usd = float(
        sum(float(summary.get("deepseek_est_cost_usd") or 0.0) for summary in summaries)
    )
    deepseek_cost_basis = combine_deepseek_cost_bases(
        [summary.get("deepseek_cost_basis") for summary in summaries]
    )
    return {
        "tag": tag,
        "scenario_count": len(summaries),
        "total_scenarios": total_scenarios,
        "completed": len(summaries),
        "pending": max(total_scenarios - len(summaries), 0),
        "passed": passed,
        "failed": failed,
        "final_score": f"{passed}/{len(summaries)}",
        "raw_first_attempt_passed": raw_first_attempt_passed,
        "raw_first_attempt_failed": len(summaries) - raw_first_attempt_passed,
        "raw_first_attempt_score": f"{raw_first_attempt_passed}/{len(summaries)}",
        "infra_failures": infra_failures,
        "product_or_assessment_failures": failed - infra_failures,
        "score_classes": score_classes,
        "overall_success": complete and failed == 0 and len(summaries) == total_scenarios,
        "complete": complete,
        "deepseek_usage": deepseek_usage,
        "deepseek_est_cost_usd": deepseek_est_cost_usd,
        "deepseek_cost_basis": deepseek_cost_basis,
        "scenarios": summaries,
    }


def _persist_run_summary(
    tag: str,
    results: list[dict[str, Any] | None],
    output_base: Any,
    *,
    total_scenarios: int,
    complete: bool,
) -> dict[str, Any]:
    summaries = [r for r in results if r]
    summary = _build_run_summary(
        tag,
        summaries,
        total_scenarios=total_scenarios,
        complete=complete,
    )
    run_dir = _run_dir_for(output_base, tag)
    if complete:
        _write_json_atomic(run_dir / "run_summary.json", summary)
        partial = run_dir / "run_summary.partial.json"
        if partial.exists():
            partial.unlink()
    else:
        _write_json_atomic(run_dir / "run_summary.partial.json", summary)
    return summary


def _analysis_index_path_for_summary(run_summary_path: Path) -> Path:
    if run_summary_path.name in {"run_summary.json", "run_summary.partial.json"}:
        return run_summary_path.parent / "failure_analysis" / "index.json"
    return run_summary_path.with_suffix("") / "failure_analysis" / "index.json"


def _run_failure_analysis_from_summary(
    run_summary_path: Path,
    *,
    scenarios_dir: Path,
    analyze_failures_enabled: bool,
    prepare_only: bool,
    recommend_fixes: bool,
    analysis_model: str,
    analysis_max_workers: int,
    analysis_timeout: int,
    resume_failure_analysis: bool,
    recommendations_model: str,
    recommendations_timeout: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "run_summary_path": str(run_summary_path),
        "analysis_index_path": None,
        "recommendations_path": None,
    }
    index_path = _analysis_index_path_for_summary(run_summary_path)
    should_prepare = prepare_only or analyze_failures_enabled or (recommend_fixes and not index_path.exists())
    if should_prepare:
        if analyze_failures_enabled:
            index = analyze_failures(
                run_summary_path,
                scenarios_dir=scenarios_dir,
                model=analysis_model,
                max_workers=analysis_max_workers,
                timeout_s=analysis_timeout,
                resume=resume_failure_analysis,
            )
        else:
            index = prepare_failure_analysis(run_summary_path, scenarios_dir=scenarios_dir)
        result["analysis_index_path"] = str(index_path)
        result["failed_count"] = index.get("failed_count", 0)
    elif index_path.exists():
        result["analysis_index_path"] = str(index_path)
    if recommend_fixes:
        meta = recommendations_for_run(
            run_summary_path,
            model=recommendations_model,
            timeout_s=recommendations_timeout,
        )
        result["recommendations_path"] = meta["output_path"]
        result["recommendations_returncode"] = meta["returncode"]
    return result


def run_single(scenario_path: str, tag: str, output_base: Any, out_file: Path | None) -> dict[str, Any]:
    """Run ONE scenario in-process; write its summary JSON to *out_file* if given.

    This is the entry point invoked by the per-scenario subprocess in parallel mode.
    """
    from .adapter import run_headless_scenario
    from .guard import guard_output_dir

    path = Path(scenario_path)
    scenario = _load_scenario(path)
    scenario.setdefault("id", path.stem)
    summary = run_headless_scenario(scenario, output_base=output_base, tag=tag)
    summary["guard"] = guard_output_dir(summary["output_dir"], scenario=scenario)
    _classify_retryable_infra_summary(summary)
    _persist_scenario_summary(summary, output_base, tag)
    if out_file is not None:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(summary, default=str), encoding="utf-8")
    return summary


def run_tag(
    tag: str,
    *,
    scenarios_dir: Path | None = None,
    output_base: Path | str | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
    per_scenario_timeout: int = DEFAULT_PER_SCENARIO_TIMEOUT,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
    infra_retries: int = DEFAULT_INFRA_RETRIES,
) -> dict[str, Any]:
    """Run every scenario under *scenarios_dir* CONCURRENTLY — each in its own
    subprocess (process-isolated + kill-on-timeout), bounded by *max_workers*."""
    if scenarios_dir is None:
        scenarios_dir = Path(__file__).with_name("scenarios")
    paths = _scenario_paths(scenarios_dir)
    results: list[dict[str, Any] | None] = [None] * len(paths)
    sem = threading.Semaphore(max(1, max_workers))
    lock = threading.Lock()
    tmpdir = Path(tempfile.mkdtemp(prefix="vibecomfy-runner-"))
    try:
        def record_result(idx: int, summary: dict[str, Any]) -> None:
            results[idx] = summary
            results[idx].setdefault("scenario_id", paths[idx].stem)
            _persist_scenario_summary(results[idx], output_base, tag)
            with lock:
                completed = sum(1 for r in results if r)
                run_summary = _persist_run_summary(
                    tag,
                    results,
                    output_base,
                    total_scenarios=len(paths),
                    complete=False,
                )
                if progress_every > 0 and (
                    completed == len(paths) or completed % progress_every == 0
                ):
                    print(
                        "[agentic-progress] "
                        f"tag={tag} completed={completed}/{len(paths)} "
                        f"passed={run_summary['passed']} failed={run_summary['failed']} "
                        f"pending={run_summary['pending']}",
                        file=sys.stderr,
                        flush=True,
                    )

        def worker(idx: int, path: Path) -> None:
            sid = path.stem
            scenario_for_synthetic = _load_scenario(path)
            expect_graph_changed = _scenario_expect_graph_changed(scenario_for_synthetic)
            attempts: list[dict[str, Any]] = []
            with sem:
                max_attempts = 1 + max(0, infra_retries)
                final_summary: dict[str, Any] | None = None
                for attempt in range(1, max_attempts + 1):
                    attempt_run_tag = _attempt_tag(tag, sid, attempt)
                    out_file = tmpdir / f"{idx:03d}-{attempt}.json"
                    cmd = [
                        sys.executable, "-m", "tests.live_agentic_harness.runner",
                        "--single", str(path), "--tag", attempt_run_tag,
                        "--single-out", str(out_file),
                    ]
                    if output_base is not None:
                        cmd += ["--output-base", str(output_base)]
                    started = time.monotonic()
                    try:
                        proc = subprocess.run(
                            cmd, cwd=str(REPO), capture_output=True, text=True,
                            timeout=per_scenario_timeout,
                        )
                        elapsed_s = time.monotonic() - started
                        if out_file.exists():
                            final_summary = json.loads(out_file.read_text(encoding="utf-8"))
                            final_summary["attempt"] = attempt
                            final_summary["elapsed_s"] = elapsed_s
                            final_summary["agent_exercised"] = True
                        else:
                            tail = _trim((proc.stderr or ""))
                            final_summary = _failure_summary(
                                sid,
                                output_base,
                                attempt_run_tag,
                                f"runner produced no summary (rc={proc.returncode}); {tail}",
                                failure_class="infra_no_summary",
                                attempt=attempt,
                                expect_graph_changed=expect_graph_changed,
                                stdout_tail=_trim(proc.stdout or ""),
                                stderr_tail=tail,
                                elapsed_s=elapsed_s,
                            )
                    except subprocess.TimeoutExpired as exc:
                        elapsed_s = time.monotonic() - started
                        final_summary = _failure_summary(
                            sid,
                            output_base,
                            attempt_run_tag,
                            f"scenario exceeded {per_scenario_timeout}s and was killed",
                            failure_class="infra_timeout",
                            attempt=attempt,
                            expect_graph_changed=expect_graph_changed,
                            stdout_tail=_trim((exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
                            stderr_tail=_trim((exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")),
                            elapsed_s=elapsed_s,
                        )
                    except Exception as exc:  # noqa: BLE001 — isolate one failure
                        elapsed_s = time.monotonic() - started
                        final_summary = _failure_summary(
                            sid,
                            output_base,
                            attempt_run_tag,
                            _trim(str(exc)),
                            failure_class="infra_runner_exception",
                            attempt=attempt,
                            expect_graph_changed=expect_graph_changed,
                            elapsed_s=elapsed_s,
                        )

                    retryable_infra = _is_retryable_infra_summary(final_summary)
                    attempts.append(_attempt_record(final_summary, attempt=attempt))
                    if not retryable_infra:
                        break

                if final_summary is None:
                    final_summary = _failure_summary(
                        sid,
                        output_base,
                        _attempt_tag(tag, sid, 1),
                        "runner produced no attempt result",
                        failure_class="infra_runner_exception",
                        attempt=1,
                        expect_graph_changed=expect_graph_changed,
                    )
                    attempts.append(_attempt_record(final_summary, attempt=1))

                final_summary["attempts"] = attempts
                final_summary["attempt_count"] = len(attempts)
                final_summary["final_attempt"] = attempts[-1]["attempt"]
                final_summary["raw_first_attempt_success"] = attempts[0].get("live_agentic_success") is True
                final_summary["final_success"] = final_summary["guard"].get("live_agentic_success") is True
                final_summary.setdefault(
                    "failure_class",
                    attempts[-1].get("failure_class") or "product_or_assessment_failure",
                )
                final_summary.setdefault(
                    "score_class",
                    attempts[-1].get("score_class") or (
                        "pass"
                        if final_summary["guard"].get("live_agentic_success") is True
                        else "product_fail"
                    ),
                )
                record_result(idx, final_summary)
                _persist_canonical_scenario_summary(
                    final_summary,
                    output_base,
                    tag,
                    sid,
                )

        threads = [
            threading.Thread(target=worker, args=(i, p), daemon=True)
            for i, p in enumerate(paths)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        for f in tmpdir.glob("*.json"):
            try:
                f.unlink()
            except Exception:  # noqa: BLE001
                pass
        try:
            tmpdir.rmdir()
        except Exception:  # noqa: BLE001
            pass

    return _persist_run_summary(
        tag,
        results,
        output_base,
        total_scenarios=len(paths),
        complete=True,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tests.live_agentic_harness.runner")
    parser.add_argument("--tag", default=None, help="Run tag (used in evidence path).")
    parser.add_argument(
        "--scenarios-dir",
        default=None,
        help="Directory containing scenario YAML/JSON files.",
    )
    parser.add_argument(
        "--output-base",
        default=None,
        help="Base evidence directory (default: out/agentic).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary instead of a short report.",
    )
    parser.add_argument(
        "--single",
        default=None,
        help="Run a SINGLE scenario file (subprocess entry point for parallel mode).",
    )
    parser.add_argument(
        "--single-out",
        default=None,
        help="Path to write the single-scenario summary JSON (used with --single).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"max concurrent scenarios (default {DEFAULT_MAX_WORKERS}).",
    )
    parser.add_argument(
        "--per-scenario-timeout",
        type=int,
        default=DEFAULT_PER_SCENARIO_TIMEOUT,
        help=f"per-scenario seconds before kill (default {DEFAULT_PER_SCENARIO_TIMEOUT}).",
    )
    parser.add_argument(
        "--infra-retries",
        type=int,
        default=DEFAULT_INFRA_RETRIES,
        help=(
            "retry subprocess-level infrastructure failures this many times "
            f"(default {DEFAULT_INFRA_RETRIES}; semantic guard failures are not retried)"
        ),
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        help=(
            "emit and persist aggregate progress every N completed scenarios "
            f"(default {DEFAULT_PROGRESS_EVERY}; 0 disables stderr progress)"
        ),
    )
    parser.add_argument(
        "--prepare-failure-analysis",
        action="store_true",
        help="Write per-failed-scenario analysis briefs and index without calling subagents.",
    )
    parser.add_argument(
        "--analyze-failures",
        action="store_true",
        help="After the run, launch one DeepSeek/Hermes diagnosis subagent per failed scenario.",
    )
    parser.add_argument(
        "--analysis-model",
        default=DEFAULT_ANALYSIS_MODEL,
        help=f"Model for per-failure diagnosis agents (default {DEFAULT_ANALYSIS_MODEL}).",
    )
    parser.add_argument(
        "--analysis-max-workers",
        type=int,
        default=DEFAULT_ANALYSIS_WORKERS,
        help=f"Maximum concurrent failure diagnosis agents (default {DEFAULT_ANALYSIS_WORKERS}).",
    )
    parser.add_argument(
        "--analysis-timeout",
        type=int,
        default=DEFAULT_AGENT_TIMEOUT_S,
        help=f"Seconds before killing one failure diagnosis agent (default {DEFAULT_AGENT_TIMEOUT_S}).",
    )
    parser.add_argument(
        "--restart-failure-analysis",
        action="store_true",
        help="Rerun every failed-scenario diagnosis, including ones already marked done.",
    )
    parser.add_argument(
        "--recommend-fixes",
        action="store_true",
        help="Use Codex/GPT-5.5 to synthesize all failure diagnoses into ranked fix recommendations.",
    )
    parser.add_argument(
        "--recommendations-model",
        default=DEFAULT_RECOMMENDATIONS_MODEL,
        help=f"Model for aggregate fix recommendations (default {DEFAULT_RECOMMENDATIONS_MODEL}).",
    )
    parser.add_argument(
        "--recommendations-timeout",
        type=int,
        default=DEFAULT_AGENT_TIMEOUT_S,
        help=f"Seconds before killing aggregate recommendations (default {DEFAULT_AGENT_TIMEOUT_S}).",
    )
    parser.add_argument(
        "--analyze-existing-summary",
        default=None,
        help=(
            "Analyze an existing run_summary.json or redirected summary JSON instead of running scenarios."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    scenarios_dir = Path(args.scenarios_dir) if args.scenarios_dir else Path(__file__).with_name("scenarios")

    if args.analyze_existing_summary:
        analysis = _run_failure_analysis_from_summary(
            Path(args.analyze_existing_summary),
            scenarios_dir=scenarios_dir,
            analyze_failures_enabled=args.analyze_failures,
            prepare_only=args.prepare_failure_analysis
            or not (args.analyze_failures or args.recommend_fixes),
            recommend_fixes=args.recommend_fixes,
            analysis_model=args.analysis_model,
            analysis_max_workers=args.analysis_max_workers,
            analysis_timeout=args.analysis_timeout,
            resume_failure_analysis=not args.restart_failure_analysis,
            recommendations_model=args.recommendations_model,
            recommendations_timeout=args.recommendations_timeout,
        )
        print(json.dumps({"failure_analysis": analysis}, indent=2, default=str))
        return 0

    if not args.tag:
        parser.error("--tag is required unless --analyze-existing-summary is used")

    if args.single:
        out_file = Path(args.single_out) if args.single_out else None
        ob = Path(args.output_base) if args.output_base else None
        summary = run_single(args.single, args.tag, ob, out_file)
        # Compact one-line stdout for liveness; the real payload is in --single-out.
        print(json.dumps({"scenario_id": summary.get("scenario_id"),
                          "ok": summary["guard"]["live_agentic_success"]}))
        return 0 if summary["guard"]["live_agentic_success"] else 1

    output_base = Path(args.output_base) if args.output_base else None
    summary = run_tag(
        args.tag,
        scenarios_dir=scenarios_dir,
        output_base=output_base,
        max_workers=args.max_workers,
        per_scenario_timeout=args.per_scenario_timeout,
        progress_every=args.progress_every,
        infra_retries=args.infra_retries,
    )
    if args.prepare_failure_analysis or args.analyze_failures or args.recommend_fixes:
        run_summary_path = _run_dir_for(output_base, summary["tag"]) / "run_summary.json"
        analysis = _run_failure_analysis_from_summary(
            run_summary_path,
            scenarios_dir=scenarios_dir,
            analyze_failures_enabled=args.analyze_failures,
            prepare_only=args.prepare_failure_analysis,
            recommend_fixes=args.recommend_fixes,
            analysis_model=args.analysis_model,
            analysis_max_workers=args.analysis_max_workers,
            analysis_timeout=args.analysis_timeout,
            resume_failure_analysis=not args.restart_failure_analysis,
            recommendations_model=args.recommendations_model,
            recommendations_timeout=args.recommendations_timeout,
        )
        summary["failure_analysis"] = analysis

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(f"tag: {summary['tag']}")
        print(f"scenarios: {summary['scenario_count']}")
        print(f"score: {summary['passed']}/{summary['scenario_count']}")
        print(
            f"raw_first_attempt_score: "
            f"{summary['raw_first_attempt_passed']}/{summary['scenario_count']}"
        )
        print(f"infra_failures: {summary['infra_failures']}")
        print(f"product_or_assessment_failures: {summary['product_or_assessment_failures']}")
        print(f"overall_success: {summary['overall_success']}")
        for s in summary["scenarios"]:
            assessment = s["guard"].get("assessment", {})
            errors = assessment.get("error_count", 0)
            print(
                f"  {s['scenario_id']}: {s['status']} "
                f"(live_agentic_success={s['guard']['live_agentic_success']}, "
                f"assessment_errors={errors})"
            )

    return 0 if summary["overall_success"] or summary["scenario_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
