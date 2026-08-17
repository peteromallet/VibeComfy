"""Live agentic harness runner for VibeComfy headless scenarios.

Scenarios run CONCURRENTLY — each in its own subprocess (process isolation +
kill-on-timeout), bounded by ``--max-workers``. Modeled on the subagent-launcher
fanout: one process per task, a bounded pool, a per-task timeout. ``--single``
is the per-scenario subprocess entry point.

Each scenario child runs in its OWN PROCESS GROUP with stdout/stderr going to
regular temp files (never pipes), mirroring ``runtime.py``'s ``_run_worker_subprocess``
(PR-A): a grandchild (model HTTP call / research subprocess) that inherits the
child's stdio fds can no longer hold a captured pipe open past the timeout, so
the per-scenario timeout actually fires. On timeout the whole group is
SIGTERM'd (short grace) then SIGKILL'd and the direct child is reaped before
the timeout is reported. If the child already wrote a valid ``--single-out``
summary before hanging (the flow SUCCEEDED but shutdown wedged), the summary is
recovered and annotated ``post_flow_exit_cleanup`` instead of fabricating
``infra_timeout``.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping

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
from .scenario_manifest import discover_manifest_scenarios
from .adapter import _HARNESS_DEFAULT_TRANSPORT, _TRANSPORT_SELECTING_ENV_KEYS

DEFAULT_MAX_WORKERS = 6
DEFAULT_PER_SCENARIO_TIMEOUT = 1200  # seconds; kills a wedged/over-slow scenario
DEFAULT_PROGRESS_EVERY = 10
DEFAULT_INFRA_RETRIES = 1
_RETRYABLE_INFRA_CLASSES = frozenset({"infra_empty_response", "infra_timeout"})
_SCENARIO_KILL_GRACE_SECONDS = float(os.getenv("VIBECOMFY_RUNNER_KILL_GRACE", "2"))
REPO = Path(__file__).resolve().parents[2]


def _pinned_child_env(transport: str | None) -> dict[str, str]:
    """Return the child environment with transport-selecting keys pinned.

    With an explicit ``--transport`` the child must not inherit ANY ambient
    transport-selecting variable (base URL, model force-overs, endpoint pins):
    the explicit selector is the only authority and the adapter re-establishes
    the pinned values from it.  Credential keys (OPENROUTER_API_KEY /
    DEEPSEEK_API_KEY) are preserved — they supply keys, they do not select
    transport.  ``run_tag``/``run_single`` resolve the no-flag default to the
    canonical OpenRouter route BEFORE calling this, so a plain run never
    inherits an ambient ``VIBECOMFY_TRANSPORT``; the ``None`` pass-through is
    only reachable by direct callers, where an operator's deliberate
    ``VIBECOMFY_TRANSPORT`` pin still applies.
    """
    if transport is None:
        return dict(os.environ)
    return {
        key: value
        for key, value in os.environ.items()
        if key not in _TRANSPORT_SELECTING_ENV_KEYS
    }

def _scenario_paths(
    scenarios_dir: Path,
    *,
    manifest_path: Path | None = None,
) -> list[Path]:
    if not scenarios_dir.is_dir():
        raise FileNotFoundError(f"scenario directory is missing: {scenarios_dir}")
    return discover_manifest_scenarios(scenarios_dir, manifest_path=manifest_path)


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


def _terminate_scenario_group(pid: int) -> None:
    """Terminate the scenario child's process GROUP and let the caller reap it.

    The child is spawned with ``start_new_session=True``, so it is a session
    leader whose process-group id equals its pid; signalling the group reaches
    every grandchild that inherited the child's stdio fds (the cluster-A pipe
    hang: ``subprocess.run(timeout=...)`` blocked in ``communicate()`` forever
    because a grandchild held the captured pipe open). SIGTERM first with a
    short grace so a well-behaved child can flush; then SIGKILL, which is
    uncatchable, so the caller's subsequent ``wait()`` cannot hang.

    ``PermissionError`` (EPERM) from ``killpg`` is treated like ESRCH: macOS
    returns EPERM for a process group whose members are all zombies (nothing
    left to signal), which is exactly the "already gone" state we probe for.
    """
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return  # already gone, or only zombies remain
    deadline = time.monotonic() + _SCENARIO_KILL_GRACE_SECONDS
    while time.monotonic() < deadline:
        try:
            os.killpg(pid, 0)
        except (ProcessLookupError, PermissionError):
            return  # group exited during the grace window
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_scenario_subprocess(
    command: list[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    timeout: float,
    stdout_path: str,
    stderr_path: str,
    before_terminate: Callable[[], None] | None = None,
) -> tuple[int, str, str]:
    """Run *command* in its own process group; return (returncode, stdout, stderr).

    stdout/stderr go to regular temp FILES, never pipes: a grandchild that
    inherits the child's stdio fds cannot keep a pipe open past our timeout, so
    the per-scenario timeout actually fires (mirrors ``runtime.py``'s
    ``_run_worker_subprocess``, PR-A). On timeout the whole process GROUP is
    terminated (SIGTERM → short grace → SIGKILL), the direct child is reaped
    before ``subprocess.TimeoutExpired`` is re-raised, and the timeout carries
    the captured temp-file tails so the caller can build its failure summary.
    """
    with open(stdout_path, "w", encoding="utf-8") as out_fh, open(
        stderr_path, "w", encoding="utf-8"
    ) as err_fh:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=out_fh,
            stderr=err_fh,
            start_new_session=True,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if before_terminate is not None:
                try:
                    before_terminate()
                except Exception:  # noqa: BLE001 - timeout termination must proceed
                    pass
            _terminate_scenario_group(proc.pid)
            try:
                proc.wait(timeout=5.0)  # bounded reap after SIGKILL
            except subprocess.TimeoutExpired:
                pass  # group already SIGKILLed; a lingering zombie is harmless
            with open(stdout_path, encoding="utf-8", errors="replace") as fh:
                stdout_text = fh.read()
            with open(stderr_path, encoding="utf-8", errors="replace") as fh:
                stderr_text = fh.read()
            raise subprocess.TimeoutExpired(
                cmd=command, timeout=timeout, output=stdout_text, stderr=stderr_text
            ) from None
    with open(stdout_path, encoding="utf-8", errors="replace") as fh:
        stdout_text = fh.read()
    with open(stderr_path, encoding="utf-8", errors="replace") as fh:
        stderr_text = fh.read()
    return proc.returncode, stdout_text, stderr_text


def _load_valid_summary(path: Path) -> dict[str, Any] | None:
    """Load *path* as a summary dict, or None when missing or not valid JSON.

    Used for post-flow recovery: a summary the child already wrote before it
    wedged during shutdown is real evidence the flow completed, so a timeout
    must recover it instead of fabricating an infrastructure failure.
    """
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _timeout_tail(exc: subprocess.TimeoutExpired, attr: str) -> str:
    """Text of *attr* (``"output"``/``"stderr"``) on a TimeoutExpired, decoded."""
    value = getattr(exc, attr)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


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
            "verdict": "fail",
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
    killed_before_first_attempt: bool = False,
) -> dict[str, Any]:
    summary = {
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
        "retryable_infra": failure_class == "infra_empty_response",
        "agent_exercised": False,
        "attempt": attempt,
        "elapsed_s": elapsed_s,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "model_attempts": [],
        "deepseek_usage": {},
        "deepseek_est_cost_usd": 0.0,
        "deepseek_cost_basis": "not_available",
    }
    if killed_before_first_attempt:
        summary["killed_before_first_attempt"] = True
    return summary


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
        "killed_before_first_attempt": summary.get("killed_before_first_attempt") is True,
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
    summary["retryable_infra"] = failure_class in _RETRYABLE_INFRA_CLASSES
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


def _clear_stale_retryable_infra_markers(summary: dict[str, Any]) -> None:
    """Drop inherited retryable-infra markers the canonical evidence no longer supports.

    ``failure_class``/``retryable_infra`` are authoritative ONLY while they are
    re-derived from the canonical ``model_attempts`` evidence on the same
    summary. A summary that previously persisted ``infra_empty_response`` (from
    an earlier attempt or a resumed run) must not keep claiming retryability
    when the typed evidence is now, say, ``malformed_json`` (oracle finding 4).
    """
    stale_retryable = (
        summary.get("failure_class") == "infra_empty_response"
        or summary.get("retryable_infra") is True
    )
    if summary.get("failure_class") == "infra_empty_response":
        del summary["failure_class"]
    if summary.get("retryable_infra") is True:
        summary["retryable_infra"] = False
    if stale_retryable and summary.get("score_class") == "infra_blocked":
        del summary["score_class"]
    guard = summary.get("guard")
    if isinstance(guard, dict):
        if guard.get("failure_class") == "infra_empty_response":
            del guard["failure_class"]
        if stale_retryable and guard.get("score_class") == "infra_blocked":
            del guard["score_class"]


def _classify_retryable_infra_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Re-derive infra classification from canonical typed evidence only.

    Never trusts inherited ``failure_class``/``retryable_infra`` flags: when the
    canonical ``model_attempts`` evidence supports an infra class the summary is
    marked; otherwise stale retryable-infra markers are cleared so persisted
    summaries cannot mislead later decisions.
    """
    if summary.get("guard", {}).get("live_agentic_success") is True:
        _clear_stale_retryable_infra_markers(summary)
        return summary
    if _is_outer_timeout_before_first_attempt(summary):
        _mark_summary_as_infra(summary, "infra_timeout")
        return summary
    failure_class = _provider_infra_failure_class(summary)
    if failure_class is not None:
        _mark_summary_as_infra(summary, failure_class)
    else:
        _clear_stale_retryable_infra_markers(summary)
    return summary


def _is_outer_timeout_before_first_attempt(summary: Mapping[str, Any]) -> bool:
    """True only for the runner's typed outer kill with no model attempt."""
    attempts = summary.get("model_attempts")
    return (
        summary.get("failure_class") == "infra_timeout"
        and summary.get("killed_before_first_attempt") is True
        and isinstance(attempts, (list, tuple))
        and not attempts
    )


def _is_retryable_infra_summary(summary: dict[str, Any]) -> bool:
    """Decide retryability from the CANONICAL typed evidence on every call.

    The decision is the latest failed ``model_attempts`` entry's failure type
    plus the observed completion tokens, or the runner's explicit outer-kill
    marker with an empty attempt list — never the inherited
    ``failure_class``/``retryable_infra`` flags, which can be stale from an
    earlier attempt. A succeeded scenario is never retried.
    """
    _classify_retryable_infra_summary(summary)
    if summary.get("guard", {}).get("live_agentic_success") is True:
        return False
    return (
        _is_outer_timeout_before_first_attempt(summary)
        or _provider_infra_failure_class(summary) in _RETRYABLE_INFRA_CLASSES
    )


def _build_run_summary(
    tag: str,
    summaries: list[dict[str, Any]],
    *,
    total_scenarios: int,
    complete: bool,
    transport: str | None = None,
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
        "transport": transport,
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
    transport: str | None = None,
) -> dict[str, Any]:
    summaries = [r for r in results if r]
    summary = _build_run_summary(
        tag,
        summaries,
        total_scenarios=total_scenarios,
        complete=complete,
        transport=transport,
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


def run_single(
    scenario_path: str,
    tag: str,
    output_base: Any,
    out_file: Path | None,
    transport: str | None = None,
) -> dict[str, Any]:
    """Run ONE scenario in-process; write its summary JSON to *out_file* if given.

    This is the entry point invoked by the per-scenario subprocess in parallel mode.
    ``transport=None`` resolves to the canonical OpenRouter product route
    (``_HARNESS_DEFAULT_TRANSPORT``), never to an ambient credential.
    """
    transport = transport or _HARNESS_DEFAULT_TRANSPORT
    from .adapter import run_headless_scenario
    from .guard import guard_output_dir

    path = Path(scenario_path)
    scenario = _load_scenario(path)
    scenario.setdefault("id", path.stem)
    summary = run_headless_scenario(
        scenario, output_base=output_base, tag=tag, transport=transport
    )
    summary.setdefault("transport", transport)
    summary["guard"] = guard_output_dir(summary["output_dir"], scenario=scenario)
    _classify_retryable_infra_summary(summary)
    _persist_scenario_summary(summary, output_base, tag)
    if out_file is not None:
        # Atomic (temp+rename) so a runner that kills us mid-write never
        # observes a truncated summary — it either sees the full valid summary
        # (post-flow recovery) or nothing at all.
        _write_json_atomic(out_file, summary)
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
    manifest_path: Path | None = None,
    transport: str | None = None,
) -> dict[str, Any]:
    """Run every scenario under *scenarios_dir* CONCURRENTLY — each in its own
    subprocess (process-isolated + kill-on-timeout), bounded by *max_workers*.

    *transport* (``"openrouter"`` / ``"native"`` / ``None``) is forwarded
    explicitly onto every child command line and the child environment is
    pinned against ambient transport-selecting variables, so the selector
    survives subprocess isolation into every profile phase.  ``None`` resolves
    to the canonical OpenRouter product route (``_HARNESS_DEFAULT_TRANSPORT``)
    — the no-flag default is pinned to OpenRouter, never an ambient/native pin.
    """
    transport = transport or _HARNESS_DEFAULT_TRANSPORT
    if scenarios_dir is None:
        scenarios_dir = Path(__file__).with_name("scenarios")
    paths = _scenario_paths(scenarios_dir, manifest_path=manifest_path)
    results: list[dict[str, Any] | None] = [None] * len(paths)
    sem = threading.Semaphore(max(1, max_workers))
    lock = threading.Lock()
    tmpdir = Path(tempfile.mkdtemp(prefix="vibecomfy-runner-"))
    try:
        def record_result(idx: int, summary: dict[str, Any]) -> None:
            results[idx] = summary
            results[idx].setdefault("scenario_id", paths[idx].stem)
            results[idx].setdefault("transport", transport)
            _persist_scenario_summary(results[idx], output_base, tag)
            with lock:
                completed = sum(1 for r in results if r)
                run_summary = _persist_run_summary(
                    tag,
                    results,
                    output_base,
                    total_scenarios=len(paths),
                    complete=False,
                    transport=transport,
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
                    stdout_path = tmpdir / f"{idx:03d}-{attempt}.out.log"
                    stderr_path = tmpdir / f"{idx:03d}-{attempt}.err.log"
                    cmd = [
                        sys.executable, "-m", "tests.live_agentic_harness.runner",
                        "--single", str(path), "--tag", attempt_run_tag,
                        "--single-out", str(out_file),
                    ]
                    if output_base is not None:
                        cmd += ["--output-base", str(output_base)]
                    if transport is not None:
                        cmd += ["--transport", transport]
                    child_env = _pinned_child_env(transport)
                    started = time.monotonic()

                    def persist_outer_timeout_marker() -> None:
                        partial = _failure_summary(
                            sid,
                            output_base,
                            attempt_run_tag,
                            f"scenario exceeded {per_scenario_timeout}s; terminating",
                            failure_class="infra_timeout",
                            attempt=attempt,
                            expect_graph_changed=expect_graph_changed,
                            elapsed_s=time.monotonic() - started,
                            killed_before_first_attempt=True,
                        )
                        _persist_scenario_summary(
                            partial,
                            output_base,
                            attempt_run_tag,
                        )

                    try:
                        returncode, stdout_text, stderr_text = _run_scenario_subprocess(
                            cmd,
                            cwd=str(REPO),
                            env=child_env,
                            timeout=per_scenario_timeout,
                            stdout_path=str(stdout_path),
                            stderr_path=str(stderr_path),
                            before_terminate=persist_outer_timeout_marker,
                        )
                        elapsed_s = time.monotonic() - started
                        recovered = _load_valid_summary(out_file)
                        if recovered is not None:
                            final_summary = recovered
                            final_summary["attempt"] = attempt
                            final_summary["elapsed_s"] = elapsed_s
                            final_summary["agent_exercised"] = True
                        else:
                            tail = _trim(stderr_text or "")
                            final_summary = _failure_summary(
                                sid,
                                output_base,
                                attempt_run_tag,
                                f"runner produced no summary (rc={returncode}); {tail}",
                                failure_class="infra_no_summary",
                                attempt=attempt,
                                expect_graph_changed=expect_graph_changed,
                                stdout_tail=_trim(stdout_text or ""),
                                stderr_tail=tail,
                                elapsed_s=elapsed_s,
                            )
                    except subprocess.TimeoutExpired as exc:
                        elapsed_s = time.monotonic() - started
                        recovered = _load_valid_summary(out_file)
                        if recovered is not None:
                            # Post-flow exit cleanup: the child wrote a valid
                            # summary BEFORE wedging during shutdown, so the
                            # flow itself completed. Recover the summary and
                            # annotate the exit-cleanup hiccup instead of
                            # fabricating an infra_timeout.
                            final_summary = recovered
                            final_summary["attempt"] = attempt
                            final_summary["elapsed_s"] = elapsed_s
                            final_summary["agent_exercised"] = True
                            final_summary["failure_class"] = "post_flow_exit_cleanup"
                            if isinstance(final_summary.get("guard"), dict):
                                final_summary["guard"].setdefault(
                                    "failure_class", "post_flow_exit_cleanup"
                                )
                        else:
                            final_summary = _failure_summary(
                                sid,
                                output_base,
                                attempt_run_tag,
                                f"scenario exceeded {per_scenario_timeout}s and was killed",
                                failure_class="infra_timeout",
                                attempt=attempt,
                                expect_graph_changed=expect_graph_changed,
                                stdout_tail=_trim(_timeout_tail(exc, "output")),
                                stderr_tail=_trim(_timeout_tail(exc, "stderr")),
                                elapsed_s=elapsed_s,
                                killed_before_first_attempt=True,
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
        for f in tmpdir.iterdir():
            try:
                if f.is_file():
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
        transport=transport,
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
        "--manifest",
        default=None,
        help=(
            "Authoritative scenario manifest (default: scenario_manifest.json "
            "beside the scenarios directory)."
        ),
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
        "--transport",
        choices=("openrouter", "native"),
        default=None,
        help=(
            "Explicit model-call transport for every profile phase "
            "(classify/research/implement/reply). When set, ambient "
            "credentials/base URLs can never select the transport; the child "
            "environment is pinned and this flag is forwarded to every "
            "subprocess. Default: the canonical product route (openrouter), "
            "pinned — never an ambient credential."
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
        summary = run_single(args.single, args.tag, ob, out_file, transport=args.transport)
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
        manifest_path=Path(args.manifest) if args.manifest else None,
        transport=args.transport,
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
