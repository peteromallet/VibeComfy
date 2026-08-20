"""Failure-analysis helpers for live agentic harness runs.

The live runner writes durable per-scenario evidence. This module turns failed
scenario summaries into durable investigation briefs, optionally dispatches one
DeepSeek/Hermes subagent per failure, and optionally asks Codex/GPT-5.5 to
summarize the resulting failure reports.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


REPO = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS_MODEL = "deepseek:deepseek-v4-flash-0731"
DEFAULT_RECOMMENDATIONS_MODEL = "gpt-5.5"
DEFAULT_ANALYSIS_WORKERS = 12
DEFAULT_AGENT_TIMEOUT_S = 1800
TAXONOMY = (
    "intended_safe_refusal_or_legit_block",
    "false_safety_block",
    "missing_custom_node_or_schema_resolution",
    "research_or_precedent_selection_error",
    "planning_or_execution_topology_gap",
    "parameter_field_mapping_error",
    "output_arity_or_socket_mapping_error",
    "guard_or_assessor_false_negative",
    "harness_or_scenario_bug",
    "timeout_or_infrastructure",
    "model_semantic_miss",
    "unknown_needs_human",
)


@dataclass(frozen=True)
class FailedScenario:
    scenario_id: str
    scenario_path: Path
    output_dir: Path
    summary_path: Path
    summary: dict[str, Any]


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")[:140] or "scenario"


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario_path_for(scenarios_dir: Path, scenario_id: str) -> Path:
    for suffix in (".json", ".yaml", ".yml"):
        candidate = scenarios_dir / f"{scenario_id}{suffix}"
        if candidate.exists():
            return candidate
    return scenarios_dir / f"{scenario_id}.json"


def _scenario_summary_path(output_dir: Path, fallback_summary: dict[str, Any]) -> Path:
    path = output_dir / "agentic_summary.json"
    if not path.exists():
        _write_json_atomic(path, fallback_summary)
    return path


def failed_scenarios_from_summary(
    run_summary: dict[str, Any],
    *,
    scenarios_dir: Path,
) -> list[FailedScenario]:
    failed: list[FailedScenario] = []
    for summary in run_summary.get("scenarios", []):
        guard = summary.get("guard") or {}
        if guard.get("live_agentic_success") is True:
            continue
        scenario_id = str(summary.get("scenario_id") or "")
        if not scenario_id:
            continue
        output_dir = Path(summary.get("output_dir") or "")
        if not output_dir:
            continue
        failed.append(
            FailedScenario(
                scenario_id=scenario_id,
                scenario_path=_scenario_path_for(scenarios_dir, scenario_id),
                output_dir=output_dir,
                summary_path=_scenario_summary_path(output_dir, summary),
                summary=summary,
            )
        )
    return failed


def _artifact_lines(output_dir: Path) -> str:
    names = [
        "response.json",
        "implementation_result.json",
        "implementation_payload.json",
        "flow_metadata.json",
        "classification.json",
        "research.json",
        "agentic_summary.json",
    ]
    lines = []
    for name in names:
        path = output_dir / name
        if path.exists():
            lines.append(f"- `{path}`")
    return "\n".join(lines) if lines else "- No standard evidence artifacts found."


def _file_excerpt(path: Path, *, max_chars: int = 4000) -> str:
    if not path.exists():
        return "(missing)"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...(truncated)"
    return text


def build_failure_prompt(
    failed: FailedScenario,
    *,
    run_summary_path: Path,
) -> str:
    taxonomy = "\n".join(f"- `{item}`" for item in TAXONOMY)
    return f"""# Live Agentic Failure Analysis: {failed.scenario_id}

You are a DeepSeek V4 Pro subagent investigating one failed VibeComfy live-agentic eval scenario.

Working directory:
`{REPO}`

Your job is not to fix code. Your job is to deeply explain what went wrong in this one scenario by tracing the whole path from scenario intent through routing/research/planning/execution/guard evidence. Be specific and evidence-backed.

## Inputs

- Scenario file: `{failed.scenario_path}`
- Evidence directory: `{failed.output_dir}`
- Per-scenario scored summary: `{failed.summary_path}`
- Full suite summary: `{run_summary_path}`

Scenario file excerpt:

```text
{_file_excerpt(failed.scenario_path)}
```

Read at least:
1. The scenario file.
2. The per-scenario summary.
3. These evidence artifacts if present:
{_artifact_lines(failed.output_dir)}
4. Any nearby VibeComfy code needed to understand the failing route, gate, validator, guard, or assessor. Keep tool use focused on this scenario.

## Taxonomy

Choose exactly one primary category and at most one secondary category:

{taxonomy}

## Required Output

Write a markdown report with exactly these sections:

### Scenario
- id
- user task/query
- expected behavior in one sentence

### Verdict
- primary category
- optional secondary category
- one-sentence verdict

### Trace
Step through what happened: classification/routing, research/precedent, implementation or refusal, validation/apply, guard/assessor. Include file names and concrete values/messages.

### Evidence
Bullet artifact facts. Cite the artifact path and the exact field/message where possible.

### Root Cause
Separate:
- agent/model behavior
- VibeComfy code or harness behavior
- scenario/rubric expectation

### Fix Direction
Concrete fix or investigation. Name likely files/functions if you found them.

### Confidence
High/Medium/Low and why.

Do not discuss other failures except as clearly-marked hypotheses.
"""


def default_hermes_launcher() -> Path:
    candidates = [
        Path.home() / ".claude" / "skills" / "subagent-launcher" / "launch_hermes_agent.py",
        Path.home()
        / "Documents"
        / "Arnold"
        / "arnold_pipelines"
        / "megaplan"
        / "skills"
        / "subagent-launcher"
        / "launch_hermes_agent.py",
        Path.home() / "Documents" / "poms_skills" / "subagent-launcher" / "launch_hermes_agent.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def run_deepseek_analysis(
    prompt_path: Path,
    output_path: Path,
    *,
    model: str = DEFAULT_ANALYSIS_MODEL,
    timeout_s: int = DEFAULT_AGENT_TIMEOUT_S,
    launcher_path: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    launcher = launcher_path or default_hermes_launcher()
    cmd = [
        sys.executable,
        str(launcher),
        "--model",
        model,
        "--toolsets=file,web,terminal",
        "--query-file",
        str(prompt_path),
        "--project-dir",
        str(REPO),
    ]
    proc = runner(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=timeout_s)
    text = proc.stdout or ""
    if not text.strip() and proc.stderr:
        text = proc.stderr
    _write_text_atomic(output_path, text)
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout_bytes": len(proc.stdout or ""),
        "stderr_tail": (proc.stderr or "")[-4000:],
    }


def _analysis_dir_for(failed: FailedScenario) -> Path:
    return failed.output_dir / "failure_analysis"


def prepare_failure_analysis(
    run_summary_path: Path,
    *,
    scenarios_dir: Path,
) -> dict[str, Any]:
    run_summary = _load_json(run_summary_path)
    failed = failed_scenarios_from_summary(run_summary, scenarios_dir=scenarios_dir)
    index: dict[str, Any] = {
        "run_summary": str(run_summary_path),
        "failed_count": len(failed),
        "failures": [],
    }
    for item in failed:
        analysis_dir = _analysis_dir_for(item)
        brief_path = analysis_dir / "brief.md"
        diagnosis_path = analysis_dir / "diagnosis.md"
        meta_path = analysis_dir / "meta.json"
        _write_text_atomic(brief_path, build_failure_prompt(item, run_summary_path=run_summary_path))
        existing = _load_json(meta_path) if meta_path.exists() else {}
        meta = {
            "scenario_id": item.scenario_id,
            "scenario_path": str(item.scenario_path),
            "output_dir": str(item.output_dir),
            "summary_path": str(item.summary_path),
            "brief_path": str(brief_path),
            "diagnosis_path": str(diagnosis_path),
            "status": existing.get("status") or "prepared",
        }
        for key in ("agent", "error"):
            if key in existing:
                meta[key] = existing[key]
        _write_json_atomic(meta_path, meta)
        index["failures"].append(meta | {"meta_path": str(meta_path)})
    _write_json_atomic(_run_analysis_dir(run_summary_path) / "index.json", index)
    return index


def _run_analysis_dir(run_summary_path: Path) -> Path:
    if run_summary_path.name in {"run_summary.json", "run_summary.partial.json"}:
        return run_summary_path.parent / "failure_analysis"
    return run_summary_path.with_suffix("") / "failure_analysis"


def load_failure_analysis_index(run_summary_path: Path) -> dict[str, Any]:
    index_path = _run_analysis_dir(run_summary_path) / "index.json"
    index = _load_json(index_path)
    merged = []
    for item in index.get("failures", []):
        meta_path = Path(item["meta_path"])
        if meta_path.exists():
            merged.append(_load_json(meta_path) | {"meta_path": str(meta_path)})
        else:
            merged.append(item)
    index["failures"] = merged
    _write_json_atomic(index_path, index)
    return index


def analyze_failures(
    run_summary_path: Path,
    *,
    scenarios_dir: Path,
    model: str = DEFAULT_ANALYSIS_MODEL,
    max_workers: int = DEFAULT_ANALYSIS_WORKERS,
    timeout_s: int = DEFAULT_AGENT_TIMEOUT_S,
    resume: bool = True,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    index = prepare_failure_analysis(run_summary_path, scenarios_dir=scenarios_dir)
    failures = index["failures"]
    if resume:
        failures = [
            meta
            for meta in failures
            if _load_json(Path(meta["meta_path"])).get("status") != "done"
        ]
    sem = threading.Semaphore(max(1, max_workers))
    lock = threading.Lock()

    def worker(meta: dict[str, Any]) -> None:
        meta_path = Path(meta["meta_path"])
        with sem:
            current = _load_json(meta_path)
            current["status"] = "running"
            _write_json_atomic(meta_path, current)
            try:
                result = run_deepseek_analysis(
                    Path(current["brief_path"]),
                    Path(current["diagnosis_path"]),
                    model=model,
                    timeout_s=timeout_s,
                    runner=runner,
                )
                current["status"] = "done" if result["returncode"] == 0 else "agent_failed"
                current["agent"] = result
            except Exception as exc:  # noqa: BLE001 - keep one failed diagnosis isolated
                current["status"] = "error"
                current["error"] = str(exc)
            _write_json_atomic(meta_path, current)
            with lock:
                done = 0
                for item in index["failures"]:
                    status = _load_json(Path(item["meta_path"])).get("status")
                    done += int(status in {"done", "agent_failed", "error"})
                print(
                    f"[failure-analysis] completed={done}/{len(index['failures'])} latest={current['scenario_id']} status={current['status']}",
                    file=sys.stderr,
                    flush=True,
                )

    threads = [threading.Thread(target=worker, args=(meta,), daemon=True) for meta in failures]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    return load_failure_analysis_index(run_summary_path)


def build_recommendations_prompt(index_path: Path) -> str:
    index = _load_json(index_path)
    diagnosis_paths = [
        Path(item["diagnosis_path"])
        for item in index.get("failures", [])
        if Path(item.get("diagnosis_path", "")).exists()
    ]
    report_list = "\n".join(f"- `{path}`" for path in diagnosis_paths)
    failed_count = index.get("failed_count", len(diagnosis_paths))
    return f"""# Aggregate Live Agentic Failure Recommendations

You are Codex/GPT-5.5 reviewing all failed-scenario diagnosis reports for a VibeComfy live-agentic suite.
This invocation is expected to run with extra-high reasoning. Think deeply, but write a concise, evidence-backed recommendations document.

Working directory:
`{REPO}`

Index:
`{index_path}`

Diagnosis reports:
{report_list}

Known failed scenario count from the index: {failed_count}

Read the index and all diagnosis reports. Produce a concise but deep recommendations document. Do not edit files. Do not hand-wave: every recommendation should say which failures it may improve and what risk it carries.

Required sections:

## Executive Summary
- final score, failure count if available, and top 3 themes

## Failure Categories
- table: category, scenarios, evidence pattern, likely owner

## Per-Failure Primary Cause
- table with one row per failed scenario
- columns: scenario id, primary cause, secondary cause if useful, planning/RPE relevance, one-sentence explanation
- normalize primary causes into a small set such as:
  - research / precedent / adaptation handoff gap
  - guard / assessor / scenario false negative
  - missing schema / authoring surface
  - field / socket / widget mapping error
  - model semantic miss
  - infrastructure / provider flake
  - legitimate safe refusal or invalid scenario
- do not leave this section at category-level; every failed scenario must appear exactly once

## Architecture Impact
- assess whether the researched/planning/execution changes appear to have helped, hurt, or merely made failures safer
- distinguish capability improvement from safety improvement
- call out any target scenario, especially HotShotXL/video precedent cases, where the new planning layer prevented unsafe application but still failed to complete the edit

## Highest-Leverage Fixes
- ranked fixes, with:
  - affected scenario ids, grouped as "likely improved", "possibly improved", and "not affected"
  - expected score impact as a range, e.g. +3 to +6
  - confidence
  - likely files/functions
  - implementation risk: Low / Medium / High
  - downside risk: what could regress, and why
  - why this fix generalizes rather than gaming the score

## Low-Risk / Easy Wins
- small harness or product fixes that are unlikely to make behavior worse

## Medium/High-Risk Bets
- fixes that may improve many failures but need stronger verification because they can change agent behavior broadly

## Scenario Or Harness Bugs
- identify failures that should not count against product behavior
- distinguish invalid scenario, assessor false negative, infrastructure/model-provider flake, and legitimate product failure

## Regression Tests To Add
- concrete tests or agentic scenarios to lock in fixes

## Recommended Next Bet
- choose one coherent next implementation bet before the next 100-scenario run
- list exactly which scenarios you expect it to improve
- estimate the next-run score after that bet, with a conservative and optimistic range
- explain what evidence would falsify the bet

## Open Questions
- only questions that block confident implementation

Do not just summarize reports. Synthesize what should be fixed to improve the score.
"""


def run_codex_recommendations(
    index_path: Path,
    output_path: Path,
    *,
    model: str = DEFAULT_RECOMMENDATIONS_MODEL,
    timeout_s: int = DEFAULT_AGENT_TIMEOUT_S,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    prompt_path = output_path.with_name("recommendations-brief.md")
    _write_text_atomic(prompt_path, build_recommendations_prompt(index_path))
    prompt = prompt_path.read_text(encoding="utf-8")
    cmd = [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "-c",
        'model_reasoning_effort="xhigh"',
        "-m",
        model,
        prompt,
    ]
    env = os.environ.copy()
    env.setdefault("CODEX_SANDBOX_NETWORK_DISABLED", "1")
    proc = runner(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        input="",
        env=env,
    )
    text = proc.stdout or ""
    if not text.strip() and proc.stderr:
        text = proc.stderr
    _write_text_atomic(output_path, text)
    meta = {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout_bytes": len(proc.stdout or ""),
        "stderr_tail": (proc.stderr or "")[-4000:],
        "prompt_path": str(prompt_path),
        "output_path": str(output_path),
    }
    _write_json_atomic(output_path.with_suffix(".meta.json"), meta)
    return meta


def recommendations_for_run(
    run_summary_path: Path,
    *,
    model: str = DEFAULT_RECOMMENDATIONS_MODEL,
    timeout_s: int = DEFAULT_AGENT_TIMEOUT_S,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    analysis_dir = _run_analysis_dir(run_summary_path)
    index_path = analysis_dir / "index.json"
    output_path = analysis_dir / "recommendations.md"
    return run_codex_recommendations(
        index_path,
        output_path,
        model=model,
        timeout_s=timeout_s,
        runner=runner,
    )
