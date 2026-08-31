#!/usr/bin/env python3
"""Live agentic self-improving watchdog loop for VibeComfy.

Runs the live agentic test suite on DeepSeek, digests the failures, hands them
to Codex (via Arnold's ``CodexAdapter``) to improve the harness — especially the
prompts and the data passed between pipeline stages — then re-runs, for N
iterations. Mirrors Arnold's ``megaplan_live_watchdog`` shape (scan → digest →
repair → recheck → log) while reusing Arnold's CodexAdapter / RetryLoop /
log_event. VibeComfy owns the suite-run and the failure digest.

Loop model (per turn):
  1. Read ``tests_to_run.json`` (the list Codex set last turn) → run exactly
     those scenarios on DeepSeek.
  2. Digest the results, flagging movement vs. the prior turn (regressions +
     newly-fixed) so Codex sees whether its last bet helped.
  3. Codex gets a focused "bet" brief carrying: the north-star research/
     execute/reply philosophy, the failure digest, prior-turn results, the
     cumulative diff of pipeline edits so far, and the current focus doc.
  4. Codex (a) improves the pipeline (any file under ``vibecomfy/`` + the
     grading/harness code), (b) updates ``focus.md`` (next turn's bet + reflection),
     and (c) updates ``tests_to_run.json`` (next turn's tests — must carry forward
     this turn's so we catch regressions).
  5. Safety gate (editable-surface-only edits + package imports) → git commit → log.

Codex is steered to make the pipeline *fundamentally* better (no overfitting,
no hardcoded answers, no one-off green-flips), to think at a high level of
abstraction, to be skeptical of the tests (some are impossible or bad), and to
judge the harness itself (is the right data gathered / visible?).

Usage::

    python3 scripts/live_agentic_watchdog.py --iterations 10        # real run
    python3 scripts/live_agentic_watchdog.py --smoke                # 1-round validation
    python3 scripts/live_agentic_watchdog.py --smoke --dry-codex    # plumbing check
    python3 scripts/live_agentic_watchdog.py --from-summary X.json --dry-codex
    python3 scripts/live_agentic_watchdog.py --resume <run_id>

Outputs land under ``.watchdog-runs/<run_id>/``: ``outcome.json``, ``auto.log``,
``focus.md``, ``tests_to_run.json``, per-round ``codex-rR-prompt.md`` /
``codex-rR.out`` / ``summary-rR.json``. Each round commits Codex's edits to the
editable surface (``vibecomfy/`` + the grading/harness code) on the current branch (``watchdog rR: …``) so a bad round is ``git revert``-able; the
rest of the working tree is never staged.
"""

from __future__ import annotations

# When run as a script, self-correct to the repo venv BEFORE importing arnold.
# The venv has the fully-installed `arnold` (incl. arnold.pipelines.megaplan); a
# bare `python3` on this machine resolves `arnold` to a shadowing local Arnold
# checkout that lacks that submodule and crashes on import. Gated on __main__ so
# importing the module (e.g. for pytest) is unaffected — tests run in the venv.
if __name__ == "__main__":
    import os as _os
    import sys as _sys
    from pathlib import Path as _Path
    _vpy = _Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python"
    if _vpy.exists() and _os.path.realpath(_sys.executable) != _os.path.realpath(str(_vpy)):
        _os.execv(str(_vpy), [str(_vpy), *_sys.argv])

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# --- Arnold (installed in the VibeComfy venv via the [agent] extra) ----------
# Keep the pure digest/control-file helpers importable without the optional
# agent runtime.  The live boundary below reports a clear prerequisite error.
try:
    from arnold.agent.adapters.codex import CodexAdapter
    from arnold.agent.contracts import AgentRequest
except ModuleNotFoundError as exc:
    if exc.name != "arnold" and not str(exc.name or "").startswith("arnold.agent"):
        raise
    CodexAdapter = None  # type: ignore[assignment,misc]
    AgentRequest = None  # type: ignore[assignment,misc]
    _ARNOLD_AGENT_IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    _ARNOLD_AGENT_IMPORT_ERROR = None

if _ARNOLD_AGENT_IMPORT_ERROR is not None:
    MEGAPLAN_WATCHDOG_AVAILABLE = False
    _MEGAPLAN_WATCHDOG_IMPORT_ERROR = _ARNOLD_AGENT_IMPORT_ERROR

    class RetryCapExceeded(RuntimeError):
        """Compatibility type for the unavailable optional agent runtime."""

    class RetryOutcome:
        RESOLVED = "resolved"
        UNRESOLVED = "unresolved"

    class RetryLoop:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "live agentic watchdog requires arnold.pipelines.megaplan"
            ) from _MEGAPLAN_WATCHDOG_IMPORT_ERROR

    def log_event(logger: Any, event: str, **fields: Any) -> None:
        logger.info("%s %s", event, fields)

    def setup_logging(*, log_path: Path) -> Any:
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger("live_agentic_watchdog")
else:
    try:
        from arnold.pipelines.megaplan.watchdog.log import log_event, setup_logging
        from arnold.pipelines.megaplan.watchdog.retry import (
            RetryCapExceeded,
            RetryLoop,
            RetryOutcome,
        )
    except ModuleNotFoundError as exc:
        if exc.name != "arnold.pipelines.megaplan":
            raise

        MEGAPLAN_WATCHDOG_AVAILABLE = False
        _MEGAPLAN_WATCHDOG_IMPORT_ERROR = exc

        class RetryCapExceeded(RuntimeError):
            """Compatibility type for the unavailable optional watchdog package."""

        class RetryOutcome:
            RESOLVED = "resolved"
            UNRESOLVED = "unresolved"

        class RetryLoop:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise RuntimeError(
                    "live agentic watchdog requires arnold.pipelines.megaplan"
                ) from _MEGAPLAN_WATCHDOG_IMPORT_ERROR

        def log_event(logger: Any, event: str, **fields: Any) -> None:
            logger.info("%s %s", event, fields)

        def setup_logging(*, log_path: Path) -> Any:
            logging.basicConfig(level=logging.INFO)
            return logging.getLogger("live_agentic_watchdog")
    else:
        MEGAPLAN_WATCHDOG_AVAILABLE = True
        _MEGAPLAN_WATCHDOG_IMPORT_ERROR = None

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIOS_DIR = "tests/live_agentic_harness/scenarios"
# Same path, named for its role as the editable-scenarios tree (--allow-test-edits).
SCENARIOS_GLOB = DEFAULT_SCENARIOS_DIR

# --- Editable surface (replaces the old fixed allowlist) --------------------
# Codex may edit the whole PIPELINE (anything under vibecomfy/) AND the live-agentic
# grading/harness CODE, but NOT the test data (scenarios) or anything outside the
# pipeline. Anti-gaming is preserved by fencing the grades: scenario data, other
# unit tests, the watchdog driver, docs and config stay off-limits, so Codex can't
# rig pass/fail. Editing the grading code IS allowed but is high-trust (see brief).
EDITABLE_PREFIXES: tuple[str, ...] = ("vibecomfy/", "tests/live_agentic_harness/")
SCENARIOS_PREFIX = "tests/live_agentic_harness/scenarios/"
# Paths that are never "a change Codex made" — run artifacts, venv, build noise.
NOISE_PREFIXES: tuple[str, ...] = (
    ".watchdog-runs/", "out/", ".venv/", ".git/", "__pycache__/", "agent-jury/",
    ".claude/", ".codex/", "node_modules/",
)


def _is_noise(path: str) -> bool:
    return any(path == p.rstrip("/") or path.startswith(p) for p in NOISE_PREFIXES)


def _is_editable(path: str) -> bool:
    """True iff Codex is allowed to have changed *path*: the pipeline
    (``vibecomfy/``) or the live-agentic grading/harness code
    (``tests/live_agentic_harness/`` minus its ``scenarios/`` data)."""
    if _is_noise(path):
        return False
    if path.startswith("vibecomfy/"):
        return True
    if path.startswith("tests/live_agentic_harness/") and not path.startswith(SCENARIOS_PREFIX):
        return True
    return False


# Static prose describing the editable surface (shown verbatim in the Codex brief).
EDITABLE_BLURB = (
    "The entire `vibecomfy/` pipeline — prompts, inter-stage data, runtime, "
    "executor, the node-schema/registry (incl. the object_info schema cache), "
    "agent + intent code — AND the live-agentic grading/harness code under "
    "`tests/live_agentic_harness/` (guard/assessor/intent_judge/runner/adapter). "
    "You may NOT edit test scenario data (`.../scenarios/`), other unit tests, "
    "`scripts/live_agentic_watchdog.py`, `docs/`, or config."
)

SMOKE_SCENARIOS: list[str] = [
    "image-sdxl-txt2img-cat-in-spacesuit",
    "hotshot-16-frames-agent-edit",
]

DIGEST_BUDGET_CHARS = 20000  # ~6-7k tokens; low-signal tail is truncated
PER_SCENARIO_DETAIL_CAP = 1200


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess:
    kw.setdefault("cwd", REPO)
    kw.setdefault("text", True)
    kw.setdefault("capture_output", True)
    return subprocess.run(cmd, **kw)  # noqa: S603


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _trim(text: Any, limit: int) -> str:
    s = text if isinstance(text, str) else json.dumps(text, indent=2, default=str)
    return s if len(s) <= limit else s[:limit] + "\n…[truncated]"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def all_scenario_ids(scenarios_dir: Path) -> list[str]:
    if not scenarios_dir.is_dir():
        return []
    return sorted(p.stem for p in scenarios_dir.iterdir() if p.suffix == ".json")


# --------------------------------------------------------------------------- #
# Run-control files Codex edits each turn (focus.md + tests_to_run.json)
# --------------------------------------------------------------------------- #
FOCUS_TEMPLATE = """# Watchdog focus — run {run_id}

This document steers the loop. Codex updates it EVERY turn. It records the bet
for the next turn, reflection on the current turn, and test/harness notes.

Rules:
- Each turn is a focused BET on one problem (or a small related set).
- Carry forward prior turns' progress; do not revert working improvements.
- Be concise. Append a new `## Turn N` block each turn.

## Turn 1
- Bet: (state the problem you are betting on this turn)
- Did: (what you changed in the pipeline, and why it generalizes)
- Observed: (outcome of this turn's tests + any test/harness observations)
- Next bet: (the problem you will target next turn)
"""


def seed_focus_doc(run_dir: Path, run_id: str) -> None:
    (run_dir / "focus.md").write_text(FOCUS_TEMPLATE.format(run_id=run_id), encoding="utf-8")


BIGGER_SWINGS_TEMPLATE = """# Bigger swings — run {run_id}

A running log of LARGER changes worth doing that are OUT OF SCOPE for a single
per-turn optimization (new data sources, pipeline restructuring, new/changed
stages, significant refactors). The per-turn codex does NOT implement these — it
only APPENDS candidates here with reasoning, so a human (or a later, bigger
effort) can pick them up.

Append a new entry each turn (don't edit prior ones). Per entry:

## Swing: <short title>
- Proposed turn: <N>
- Why: <what failure or recurring pattern motivates it>
- What it'd unlock: <expected generalization / capability gained>
- Rough shape: <sketch of the change>
- Risk/effort: <notes>
"""


def seed_bigger_swings(run_dir: Path, run_id: str) -> None:
    (run_dir / "bigger_swings.md").write_text(
        BIGGER_SWINGS_TEMPLATE.format(run_id=run_id), encoding="utf-8")


def seed_tests_to_run(run_dir: Path, ids: list[str]) -> None:
    (run_dir / "tests_to_run.json").write_text(json.dumps(ids, indent=2) + "\n", encoding="utf-8")


def read_tests_to_run(run_dir: Path, fallback_ids: list[str]) -> list[str]:
    """Robustly read the JSON list; fall back if missing/invalid/unknown ids."""
    data = _read_json(run_dir / "tests_to_run.json")
    src_dir = REPO / DEFAULT_SCENARIOS_DIR
    known = set(all_scenario_ids(src_dir))
    if isinstance(data, list) and data:
        ids = [str(x) for x in data if str(x) in known]
        if ids:
            return ids
    return [i for i in fallback_ids if i in known] or sorted(known)


def build_turn_scenarios_dir(ids: list[str], src_dir: Path, dest_dir: Path) -> Path:
    """Symlink the selected scenario files into a fresh per-turn dir.

    Symlinks (not copies) so Codex's edits to the original scenario files are
    reflected when the suite runs.
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        src = src_dir / f"{sid}.json"
        if src.exists():
            (dest_dir / f"{sid}.json").symlink_to(src)
    return dest_dir


# --------------------------------------------------------------------------- #
# Suite runner
# --------------------------------------------------------------------------- #
def run_suite(tag: str, scenarios_dir: Path, output_base: Path, timeout: int,
              logger: Any) -> dict[str, Any] | None:
    cmd = [
        sys.executable, "-m", "tests.live_agentic_harness.runner",
        "--tag", tag, "--scenarios-dir", str(scenarios_dir),
        "--output-base", str(output_base), "--json",
    ]
    log_event(logger, "suite_start", tag=tag, scenarios_dir=str(scenarios_dir))
    try:
        proc = _run(cmd, timeout=timeout)
    except subprocess.TimeoutExpired:
        log_event(logger, "suite_timeout", tag=tag, timeout=timeout)
        return None
    if proc.returncode != 0:
        log_event(logger, "suite_nonzero", tag=tag, returncode=proc.returncode,
                  stderr_tail=(proc.stderr or "")[-600:])
    try:
        summary = json.loads(proc.stdout)
    except Exception:
        log_event(logger, "suite_unparseable", tag=tag,
                  stdout_tail=(proc.stdout or "")[-600:])
        return None
    log_event(logger, "suite_done", tag=tag,
              scenario_count=summary.get("scenario_count"),
              overall_success=summary.get("overall_success"))
    return summary


def save_summary(summary: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Failure digest
# --------------------------------------------------------------------------- #
def _results_map(summary: dict[str, Any]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for s in summary.get("scenarios", []) or []:
        sid = s.get("scenario_id") or s.get("id") or "?"
        out[sid] = bool((s.get("guard") or {}).get("live_agentic_success"))
    return out


def _issue_lines(issues: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for it in issues or []:
        sev = it.get("severity", "info")
        check = it.get("check", "?")
        if sev == "error" or check == "intent_judge":
            out.append(f"[{sev}/{check}] {_trim(it.get('detail', ''), PER_SCENARIO_DETAIL_CAP)}")
    return out


def _scenario_issue_map(summary: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Map scenario_id → its assessment issues, built in a single pass."""
    out: dict[str, list[dict[str, Any]]] = {}
    for s in summary.get("scenarios", []) or []:
        sid = s.get("scenario_id") or s.get("id")
        if not sid:
            continue
        out[sid] = (((s.get("guard") or {}).get("assessment") or {}).get("issues") or [])
    return out


def _response_signals(output_dir: Path) -> dict[str, Any]:
    sig: dict[str, Any] = {}
    resp = _read_json(output_dir / "response.json")
    if isinstance(resp, dict):
        for key in ("ok", "graph_unchanged", "no_candidate_reason"):
            if key in resp:
                sig[key] = resp[key]
        outcome = resp.get("outcome")
        if isinstance(outcome, dict) and "kind" in outcome:
            sig["outcome_kind"] = outcome["kind"]
        gates = resp.get("gates")
        if isinstance(gates, dict):
            failed = [k for k, v in gates.items() if v is False]
            if failed:
                sig["failed_gates"] = failed
        diags = resp.get("diagnostics")
        if isinstance(diags, list) and diags:
            hard = [d.get("message", d) for d in diags
                    if isinstance(d, dict) and d.get("severity") in ("error", "fatal")]
            if hard:
                sig["hard_diagnostics"] = _trim(hard, 400)
    meta = _read_json(output_dir / "flow_metadata.json")
    if isinstance(meta, dict):
        for key in ("status", "dispatcher", "model_behavior"):
            if key in meta:
                sig[f"meta_{key}"] = meta[key]
    return sig


def build_digest(summary: dict[str, Any], prev_results: dict[str, bool] | None) -> str:
    scenarios = summary.get("scenarios", []) or []
    total = len(scenarios)
    passed_ids: list[str] = []
    failed: list[dict[str, Any]] = []
    weird: list[str] = []
    cur_results = _results_map(summary)
    for s in scenarios:
        sid = s.get("scenario_id") or s.get("id") or "?"
        guard = s.get("guard") or {}
        if guard.get("live_agentic_success"):
            passed_ids.append(sid)
        else:
            failed.append(s)
            flags = []
            if s.get("status") and s.get("status") != "completed":
                flags.append(f"status={s.get('status')}")
            if s.get("error"):
                flags.append(f"error={_trim(s.get('error'), 140)}")
            rd = s.get("readiness")
            if isinstance(rd, dict) and rd.get("ready") is False:
                flags.append(f"readiness={_trim(rd, 140)}")
            if flags:
                weird.append(f"- {sid}: {' | '.join(flags)}")

    def _signal(s: dict[str, Any]) -> int:
        a = (s.get("guard") or {}).get("assessment") or {}
        return a.get("error_count", 0) + (2 if any(
            i.get("check") == "intent_judge" for i in (a.get("issues") or [])) else 0)
    failed.sort(key=_signal, reverse=True)

    lines = [
        f"# Failure digest — {len(passed_ids)} passed / {len(failed)} failed of {total} "
        f"(overall_success={summary.get('overall_success')})",
        "",
    ]

    # Movement vs prior turn (did the last bet help?).
    if prev_results is not None:
        regressed = [sid for sid, ok in cur_results.items()
                     if not ok and prev_results.get(sid)]
        fixed = [sid for sid, ok in cur_results.items()
                 if ok and prev_results.get(sid) is False]
        lines.append("## Movement vs previous turn")
        lines.append(f"- newly fixed: {fixed or 'none'}")
        lines.append(f"- REGRESSIONS (were passing, now failing): {regressed or 'none'}")
        lines.append("")

    if not failed:
        lines.append("All scenarios passed — nothing to fix this round.")
        lines.append("")
        lines.append("## Passing (do not regress)")
        lines.append(", ".join(passed_ids) if passed_ids else "(none)")
        return "\n".join(lines)

    lines.append("## Failing scenarios (highest-signal first)")
    lines.append("")
    budget = DIGEST_BUDGET_CHARS
    for s in failed:
        sid = s.get("scenario_id") or s.get("id") or "?"
        guard = s.get("guard") or {}
        a = guard.get("assessment") or {}
        block = [f"### {sid}"]
        block.append(f"- guard: metadata_success={guard.get('metadata_success')} "
                     f"assessment.passed={a.get('passed')} "
                     f"expect_graph_changed={a.get('expect_graph_changed')}")
        output_dir = Path(s["output_dir"]) if s.get("output_dir") else None
        if output_dir and output_dir.exists():
            sig = _response_signals(output_dir)
            if sig:
                block.append(f"- response: {_trim(sig, 500)}".replace("\n", " "))
            cls = _read_json(output_dir / "classification.json")
            if isinstance(cls, dict):
                route = cls.get("route") or (cls.get("decision") or {}).get("route")
                intent = cls.get("intent") or (cls.get("decision") or {}).get("intent")
                if route or intent:
                    block.append(f"- classified: route={route} intent={_trim(intent, 120)}")
        issue_lines = _issue_lines(a.get("issues") or [])
        if issue_lines:
            block.append("- error issues:")
            block.extend(f"  - {ln}" for ln in issue_lines[:6])
        chunk = "\n".join(block)
        if len(chunk) > budget:
            lines.append("…[further failing scenarios truncated to stay within budget]")
            break
        lines.append(chunk)
        lines.append("")
        budget -= len(chunk) + 2

    if weird:
        lines.append("## Harness weirdness (likely harness/infra bugs, not model failures)")
        lines.extend(weird[:20])
        lines.append("")

    lines.append("## Passing scenarios (do NOT regress these)")
    lines.append(", ".join(passed_ids) if passed_ids else "(none)")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Codex brief
# --------------------------------------------------------------------------- #
BRIEF_HEADER = """# Task: make the VibeComfy live agentic pipeline genuinely better (one focused bet per turn)

You are improving a REAL agentic pipeline: a ComfyUI workflow editor driven by a
batch-REPL LLM agent on DeepSeek (classify → research → implement → reply). A
focused set of tests just ran; the results are below.

## YOUR GOAL (the *what*, not the *how*)
Make the pipeline genuinely better — so similar real inputs succeed more often
and more robustly. The goal is what matters; HOW you get there is your judgment.
Be smart, not mechanical. This is not about greening one specific run.

The spirit of "better": research should FIND what's needed (Hivemind Discord
messages for knowledge, Hivemind workflows for change-by-precedent, online as a
fallback) and return both usable knowledge AND concrete node-combination
references; execute should apply that; reply should explain what actually
happened. Use your judgment to move the pipeline toward that, however is smartest.

## WHAT YOU CAN CHANGE (the whole pipeline — trust your judgment)
You may edit ANY file under `vibecomfy/` — prompts, the data passed between
stages, the runtime, the executor, the node-schema/registry (incl. the
`object_info` schema cache — the root of the "missing node schema" failures),
agent and intent code — AND the live-agentic grading/harness code under
`tests/live_agentic_harness/` (guard/assessor/intent_judge/runner/adapter).
Rethink the process. Reshape how data flows between stages. Add or fix data
sources. Restructure where it genuinely helps. Go to where the REAL problem is,
not just the prompts. You're trusted to make these calls.

## WHAT YOU MUST NOT TOUCH (the fence that keeps the grades honest)
- Test SCENARIO DATA (`tests/.../scenarios/`) and other unit tests
  (`tests/test_*.py`) — never. {test_edits_line}
- `scripts/live_agentic_watchdog.py` (this loop's driver), `docs/`, and config.
Anything outside `vibecomfy/` + `tests/live_agentic_harness/` code fails the
safety gate and your turn is reverted.

## THE PRINCIPLES (how to decide well)
- GENERALIZE: no hardcoded expected answers, no special-casing a test's exact
  strings, no branch-on-scenario-id. Fix the CLASS of problem, not one test.
- NEVER GAME: never weaken a check or loosen an assertion to raise the pass
  count. Making a grader MORE accurate (e.g. crediting a genuinely correct
  refusal) is good; making it less rigorous is gaming.
- GRADER-EDITS ARE HIGH-TRUST: you MAY edit the grading/harness code, but ONLY
  to fix a test that is genuinely WRONG (fails for the wrong reason, crashes, or
  asserts incorrect behavior). Every such edit must make the test MORE accurate
  and be justified in your report. If you'd be editing a grader to make more
  tests pass, STOP — that's gaming; fix the pipeline instead.
- RIGHT LEVEL: if you're re-tightening what a prior turn loosened (or
  vice-versa) on the same mechanism, the real fix is probably structural or
  missing data, not another prompt tweak — escalate it to `bigger_swings.md`.
- Some tests are impossible or bad; that's fine — judge each failure (pipeline
  weakness vs. impossible/bad test vs. harness gap) and act on your judgment.
- REASONABLE SCOPE: proper root-cause solutions, not one-off green-flips and not
  huge speculative refactors. Prefer the smallest change that genuinely fixes the
  cause; if it needs to be large, write it up as a big-swing instead.
- Keep the package importing (the safety gate runs `import vibecomfy...`).

## READING REFUSALS — good refusal vs bad refusal
When the pipeline DECLINES to build or finish a workflow, judge the refusal:
- GOOD refusal = correct behavior. Do NOT try to "fix" it, and it should NOT
  count as a failure: the request is genuinely impossible, makes no sense as a
  workflow, or there is legitimately no findable information on how to do it.
- BAD refusal = a real pipeline weakness. Fix it: the request makes sense for the
  workflow but the pipeline bailed for a weak reason — "no nodepack installed",
  "no model available", "I wasn't sure", a missing node it could have substituted.
  It should ATTEMPT the task (fetch/install the nodepack, use an available model,
  pick a reasonable substitute, make a best-effort build) instead of giving up.
Label every decline good or bad in your diagnosis. Target the BAD refusals.
Protect the GOOD ones — don't push the pipeline to attempt the impossible. The
intent judge (`intent/prompts/text_judge.prompt.md`) is where a good refusal gets
credited rather than counted as a failure; refine it if it's punishing good ones.

## SCOPE — two kinds of work (don't mix them up)
- DO NOW: a focused, root-cause fix to the pipeline (any file you're allowed to
  edit). Small, surgical, generalizes. This is what you implement and commit.
- BIG SWINGS (write, DON'T do): if the right fix is a LARGER change — adding new
  data sources, restructuring the pipeline, adding/changing stages, a significant
  refactor — do NOT implement it this turn. Append it to `bigger_swings.md`
  (see handoff) with your reasoning. A human or a later, bigger effort picks those up.

## THIS TURN IS A BET
Make a focused bet on one optimization (or a small related set). Read the
previous codex's summary below; build on prior progress, don't regress it.

## HANDOFF — you write these each turn (the next codex reads them)
- `.watchdog-runs/{run_id}/focus.md` — append a `## Turn {turn}` block: a short
  summary = a one-line headline + a paragraph of what you did and why.
- `.watchdog-runs/{run_id}/turn-r{turn}-report.md` — your IN-DEPTH report:
  diagnosis, exactly what you changed, why it generalizes, what to try next, and
  any test/harness observations. The next codex will be pointed here.
- `.watchdog-runs/{run_id}/tests_to_run.json` — JSON list of scenario ids to run
  NEXT turn. Carry forward THIS turn's tests (regression check); add your next
  bet's targets; drop a test only if you've concluded it's impossible/bad (say
  why in your report).
- `.watchdog-runs/{run_id}/bigger_swings.md` — if you have a new big-swing idea,
  APPEND an entry (don't edit prior ones) with: title, why, what it'd unlock,
  rough shape, risk/effort. Do NOT implement it. See the current log below.
"""


def last_focus_block(focus_md: str) -> str:
    """Extract the last '## Turn N' block from the focus doc (prev codex's summary)."""
    if not focus_md:
        return ""
    chunks = focus_md.split("## Turn ")
    if len(chunks) <= 1:
        return ""
    return _trim("## Turn " + chunks[-1].rstrip(), 1500)


def build_codex_brief(
    round_num: int,
    run_id: str,
    digest: str,
    allow_test_edits: bool,
    prior_diff: str,
    prev_results: dict[str, bool] | None,
    this_turn_tests: list[str],
    focus_md: str,
    bigger_swings_md: str = "",
) -> str:
    if allow_test_edits:
        test_edits_line = (
            "You MAY edit test scenario files, but only to fix a genuinely bad/impossible "
            "test — never to weaken one into passing. Say so in your report."
        )
    else:
        test_edits_line = (
            "Test scenario files are NOT editable this run; if a test is bad, propose the "
            "change in your report instead of editing it."
        )
    parts = [BRIEF_HEADER.format(run_id=run_id, turn=round_num, test_edits_line=test_edits_line)]

    # Previous codex's handoff: its summary (in-prompt) + pointer to its in-depth report.
    prev_summary = last_focus_block(focus_md) if round_num > 1 else ""
    if round_num > 1:
        parts.append("## PREVIOUS CODEX'S SUMMARY (their short summary — build on it)")
        parts.append(prev_summary or "(no summary block found — read the focus doc below)")
        parts.append(f"In-depth report from last turn: `.watchdog-runs/{run_id}/turn-r{round_num - 1}-report.md`")
        parts.append("")

    parts.append("## WHAT YOU CAN EDIT (recap)")
    parts.append(EDITABLE_BLURB)
    parts.append("")

    parts.append(f"## PRIOR PIPELINE CHANGES (rounds 1..{round_num - 1}; do NOT regress working progress)")
    parts.append(prior_diff.strip() if prior_diff.strip() else "(none yet — this is round 1)")
    parts.append("")

    if prev_results:
        ok = [k for k, v in prev_results.items() if v]
        bad = [k for k, v in prev_results.items() if not v]
        parts.append("## PREVIOUS TURN RESULTS")
        parts.append(f"- passed ({len(ok)}): {', '.join(ok) if ok else 'none'}")
        parts.append(f"- failed ({len(bad)}): {', '.join(bad) if bad else 'none'}")
        parts.append("")

    parts.append(f"## THIS TURN'S TESTS ({len(this_turn_tests)})")
    parts.append(", ".join(this_turn_tests))
    parts.append("")
    parts.append("## FULL FOCUS LOG (yours — append your `## Turn "
                 f"{round_num}` block this turn)")
    parts.append(_trim(focus_md, 4000))
    parts.append("")
    parts.append("## BIGGER SWINGS LOG (append new ideas here — do NOT implement them this turn)")
    parts.append(_trim(bigger_swings_md, 3000) if bigger_swings_md.strip() else "(empty so far)")
    parts.append("")
    parts.append(f"## ROUND {round_num} RESULTS DIGEST")
    parts.append(digest)
    parts.append("")
    # Complete, explicit checklist of everything to do this turn (dynamic numbering).
    checklist = [
        "MAKE YOUR BET — implement a focused, root-cause fix to the pipeline (any "
        "editable file: prompts / data-feeding / runtime / executor / schema / grader code). "
        "Generalize; don't overfit; don't green-flip one run.",
        "JUDGE REFUSALS — in your report, label every decline GOOD (correctly declined an "
        "impossible / no-info request) or BAD (bailed on a doable request over a missing "
        "nodepack / model / low confidence). Fix BAD refusals; protect GOOD ones.",
    ]
    if allow_test_edits:
        checklist.append("IF you found a genuinely bad/impossible test, you MAY edit the scenario "
                         "file — never weaken a test into passing; justify it in your report.")
    checklist.append(f"APPEND a `## Turn {round_num}` summary block to `focus.md` "
                     "(one-line headline + a paragraph of what you did and why).")
    checklist.append(f"WRITE the in-depth report to `turn-r{round_num}-report.md` "
                     "(diagnosis, exactly what you changed, why it generalizes, what to try next).")
    checklist.append("UPDATE `tests_to_run.json` for next turn — carry forward THIS turn's tests "
                     "(regression check) and add your next bet's targets.")
    checklist.append("APPEND any new big-swing idea to `bigger_swings.md` (do NOT implement it).")
    checklist.append("STAY IN BOUNDS — edit only the pipeline + grading/harness code (never "
                     "scenario data, the driver, or docs); keep the package importing; never game "
                     "the tests; don't regress prior progress.")
    parts.append("## YOUR CHECKLIST THIS TURN (do every item)")
    parts.extend(f"{i}. {item}" for i, item in enumerate(checklist, 1))
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Codex invocation (Arnold CodexAdapter)
# --------------------------------------------------------------------------- #
def invoke_codex(brief: str, model: str, effort: str, timeout: int,
                 out_path: Path, logger: Any, round_num: int) -> dict[str, Any]:
    if AgentRequest is None or CodexAdapter is None:
        raise RuntimeError(
            "live agentic watchdog requires the optional Arnold agent runtime"
        ) from _ARNOLD_AGENT_IMPORT_ERROR
    req = AgentRequest(
        agent="codex",
        mode="revise",           # telemetry label only; oneshot uses a fixed step
        model=model or None,
        effort=effort,
        read_only=False,         # mutating turn → workspace-write / bypass sandbox
        prompt=brief,
        metadata={"work_dir": str(REPO)},
        timeout_seconds=timeout,
    )
    log_event(logger, "codex_start", round=round_num, model=model, effort=effort)
    t0 = time.time()
    try:
        result = CodexAdapter()(req)
    except Exception as exc:
        log_event(logger, "codex_error", round=round_num, error=_trim(str(exc), 500))
        return {"invoked": True, "ok": False, "error": _trim(str(exc), 800),
                "duration_s": round(time.time() - t0, 1)}
    raw = getattr(result, "raw_output", "") or ""
    out_path.write_text(raw, encoding="utf-8")
    # CodexAdapter runs codex ephemeral + via the free-text path, which zeroes
    # cost/token accounting; and on ChatGPT-OAuth there is no per-call $ cost
    # anyway. Report what is real (duration, sizes) — not a misleading $0 / 0.
    duration_s = round(getattr(result, "duration_ms", 0) / 1000.0, 1)
    record = {
        "invoked": True, "ok": True,
        "model_actual": getattr(result, "model_actual", None),
        "session_id": getattr(result, "session_id", None),
        "duration_s": duration_s,
        "prompt_chars": len(brief),
        "output_chars": len(raw),
        "cost_usd": None,        # not tracked: ChatGPT-sub codex, ephemeral session
        "total_tokens": None,    # not exposed by CodexAdapter's free-text path
        "diagnosis_excerpt": _trim(raw, 1000),
    }
    log_event(logger, "codex_done", round=round_num, duration_s=duration_s,
              prompt_chars=record["prompt_chars"], output_chars=record["output_chars"])
    return record


# --------------------------------------------------------------------------- #
# Safety: round-start baseline, editable-surface gate, import check, git
# --------------------------------------------------------------------------- #
def _git_untracked() -> set[str]:
    proc = _run(["git", "-C", str(REPO), "ls-files", "--others", "--exclude-standard"])
    return {ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()}


def capture_round_baseline() -> tuple[str, set[str]]:
    """Snapshot repo state at round start as ``(tree_sha, start_untracked)``.

    ``tree_sha`` is a tree-ish capturing the current working tree (committed +
    uncommitted tracked changes) via ``git stash create`` (falling back to HEAD
    when clean). Comparing back to it later catches everything Codex changed this
    round — *including self-committed edits*, which a porcelain-only check would
    miss. ``start_untracked`` lets us spot brand-new files Codex creates. Used by
    the safety gate, the commit, and the clean revert.
    """
    stash = _run(["git", "-C", str(REPO), "stash", "create"]).stdout.strip()
    tree_sha = stash or _run(["git", "-C", str(REPO), "rev-parse", "HEAD"]).stdout.strip()
    return tree_sha, _git_untracked()


def changes_since(round_baseline: tuple[str, set[str]]) -> set[str]:
    """Paths changed since round start — tracked (diff vs the round-start tree)
    plus new untracked files Codex created — minus run/venv/build noise."""
    tree_sha, start_untracked = round_baseline
    diff = _run(["git", "-C", str(REPO), "diff", "--name-only", tree_sha])
    changed = {ln.strip() for ln in (diff.stdout or "").splitlines() if ln.strip()}
    changed |= (_git_untracked() - start_untracked)
    return {p for p in changed if p and not _is_noise(p)}


def import_ok() -> bool:
    proc = _run([sys.executable, "-c",
                 "import vibecomfy.comfy_nodes.agent.provider, vibecomfy.executor.prompts, "
                 "vibecomfy.agent.artifacts"])
    return proc.returncode == 0


def safety_gate(round_baseline: tuple[str, set[str]],
                allow_test_edits: bool) -> tuple[bool, list[str]]:
    """Pass iff every change this round is on the editable surface and the package imports."""
    rogue: list[str] = []
    for p in sorted(changes_since(round_baseline)):
        if _is_editable(p):
            continue
        if allow_test_edits and p.startswith(SCENARIOS_PREFIX) and p.endswith(".json"):
            continue  # an explicitly-allowed scenario edit
        rogue.append(p)
    violations: list[str] = []
    if rogue:
        violations.append(f"files outside the editable surface changed by codex: {rogue}")
    if not import_ok():
        violations.append("import check failed (package would not import)")
    return (not violations), violations


def revert_round(round_baseline: tuple[str, set[str]]) -> None:
    """Undo everything Codex changed this round: restore tracked files to the
    round-start tree, and delete any new files Codex created."""
    tree_sha, _start_untracked = round_baseline
    diff = _run(["git", "-C", str(REPO), "diff", "--name-only", tree_sha])
    tracked = [ln.strip() for ln in (diff.stdout or "").splitlines()
               if ln.strip() and not _is_noise(ln.strip())]
    if tracked:
        _run(["git", "-C", str(REPO), "checkout", tree_sha, "--", *tracked])
    for p in sorted(_git_untracked() - _start_untracked):
        if _is_noise(p):
            continue
        tgt = REPO / p
        if tgt.is_file():
            tgt.unlink()


def git_commit(round_baseline: tuple[str, set[str]], allow_test_edits: bool,
               message: str) -> str | None:
    """Commit Codex's editable changes this round (pipeline + grading/harness code;
    plus scenario edits only if --allow-test-edits). Returns the short SHA or None."""
    changed = changes_since(round_baseline)
    paths = {p for p in changed if _is_editable(p)}
    if allow_test_edits:
        paths |= {p for p in changed if p.startswith(SCENARIOS_PREFIX) and p.endswith(".json")}
    if not paths:
        return None
    _run(["git", "-C", str(REPO), "add", "--", *sorted(paths)])
    if _run(["git", "-C", str(REPO), "diff", "--cached", "--quiet"]).returncode == 0:
        return None
    if _run(["git", "-C", str(REPO), "commit", "-m", message]).returncode != 0:
        return None
    return _run(["git", "-C", str(REPO), "rev-parse", "HEAD"]).stdout.strip()[:12] or None


def prior_diff(run_start_commit: str) -> str:
    """Cumulative diff of editable pipeline/harness files since the run started."""
    if not run_start_commit:
        return "(no run-start baseline)"
    proc = _run(["git", "-C", str(REPO), "diff", "--unified=2", run_start_commit, "--",
                 "vibecomfy/", "tests/live_agentic_harness/"])
    out = (proc.stdout or "").strip()
    return _trim(out, 8000) if out else "(none yet — this is round 1)"


# --------------------------------------------------------------------------- #
# One round
# --------------------------------------------------------------------------- #
def repair_with_retry(
    brief: str, round_baseline: tuple[str, set[str]], args: argparse.Namespace,
    run_dir: Path, logger: Any, round_num: int,
) -> dict[str, Any]:
    loop = RetryLoop(max_attempts=args.codex_max_attempts)
    codex_out = run_dir / f"codex-r{round_num}.out"
    record: dict[str, Any] = {"attempts": 0, "reverted": False, "revert_reason": ""}
    mutable_brief = brief
    while True:
        record["attempts"] += 1
        res = invoke_codex(mutable_brief, args.codex_model, args.codex_effort,
                           args.codex_timeout, codex_out, logger, round_num)
        record["codex"] = res
        if not res.get("ok"):
            _, done = loop.attempt(RetryOutcome.UNRESOLVED)
            if done:
                record["reverted"] = True
                record["revert_reason"] = f"codex error: {res.get('error', 'unknown')}"
                revert_round(round_baseline)
                break
            mutable_brief = brief + f"\n\n## RETRY {record['attempts']}: previous codex turn errored ({res.get('error', '')}). Try again."
            continue
        ok, violations = safety_gate(round_baseline, args.allow_test_edits)
        verdict = RetryOutcome.RESOLVED if ok else RetryOutcome.UNRESOLVED
        _, done = loop.attempt(verdict)
        if ok:
            break
        if done:
            record["reverted"] = True
            record["revert_reason"] = "; ".join(violations) or "safety gate failed after retries"
            revert_round(round_baseline)
            log_event(logger, "round_reverted", round=round_num, reason=record["revert_reason"])
            break
        mutable_brief = brief + (
            f"\n\n## RETRY {record['attempts']}: your previous edit FAILED the safety gate:\n- "
            + "\n- ".join(violations)
            + "\nFix ONLY this. Do not revert prior progress. Smallest edit.")
        log_event(logger, "codex_retry", round=round_num, attempt=record["attempts"],
                  violations="; ".join(violations))
    return record


def run_round(
    round_num: int, args: argparse.Namespace, run_dir: Path,
    outcome: dict[str, Any], logger: Any, run_start_commit: str, run_base_rel: str,
) -> dict[str, Any]:
    # Tag is unique per run+turn so out/agentic/<tag>/ evidence never collides
    # across runs (a new run won't overwrite a previous run's artifacts).
    tag = f"{args.tag_prefix}-{outcome['run_id']}-r{round_num}"
    log_event(logger, "round_start", round=round_num, tag=tag)

    src_dir = REPO / DEFAULT_SCENARIOS_DIR
    prev_round = outcome["rounds"][-1] if outcome.get("rounds") else None
    prev_results = prev_round.get("results") if prev_round else None

    # 1. capture the round-start baseline (tree + untracked) for the safety gate / commit / revert
    round_baseline = capture_round_baseline()

    # 2. which tests to run this turn (+ run them, or load a saved summary)
    summary_path = run_dir / f"summary-r{round_num}.json"
    if args.from_summary and round_num == outcome.get("_start_round", 1):
        summary = _read_json(Path(args.from_summary)) or {}
        log_event(logger, "suite_loaded", round=round_num, src=args.from_summary)
        this_turn_tests = list(_results_map(summary).keys()) or read_tests_to_run(run_dir, [])
    else:
        this_turn_tests = read_tests_to_run(run_dir, all_scenario_ids(src_dir))
        scenarios_dir = build_turn_scenarios_dir(
            this_turn_tests, src_dir, run_dir / f"turn-r{round_num}-scenarios")
        summary = run_suite(tag, scenarios_dir, Path(args.output_base), args.run_timeout, logger)
        if summary is None:
            summary = {"tag": tag, "scenario_count": 0, "overall_success": False,
                       "scenarios": [], "error": "suite failed to produce a summary"}
    save_summary(summary, summary_path)

    cur_results = _results_map(summary)
    pass_count = sum(1 for v in cur_results.values() if v)
    fail_count = len(cur_results) - pass_count
    log_event(logger, "scan", round=round_num, tag=tag, ran=len(cur_results),
              passed=pass_count, failed=fail_count,
              overall_success=summary.get("overall_success"))

    # 3-4. digest + brief
    digest = build_digest(summary, prev_results)
    prior_pipeline_diff = prior_diff(run_start_commit)
    focus_md = (run_dir / "focus.md").read_text(encoding="utf-8") if (run_dir / "focus.md").exists() else ""
    bigger_swings_md = (run_dir / "bigger_swings.md").read_text(encoding="utf-8") if (run_dir / "bigger_swings.md").exists() else ""
    brief = build_codex_brief(round_num, outcome["run_id"], digest,
                              args.allow_test_edits, prior_pipeline_diff, prev_results,
                              this_turn_tests, focus_md, bigger_swings_md)
    brief_path = run_dir / f"codex-r{round_num}-prompt.md"
    brief_path.write_text(brief, encoding="utf-8")

    # 5-6. codex repair (+ safety gate, with retry)
    if args.dry_codex:
        codex_record: dict[str, Any] = {"invoked": False, "dry_run": True}
        log_event(logger, "codex_skipped_dry", round=round_num)
    else:
        codex_record = repair_with_retry(brief, round_baseline,
                                         args, run_dir, logger, round_num)

    # Capture loop-steering updates Codex made (focus.md / tests_to_run.json / report).
    next_tests = read_tests_to_run(run_dir, this_turn_tests)
    focus_tail = ""
    if (run_dir / "focus.md").exists():
        focus_tail = _trim((run_dir / "focus.md").read_text(encoding="utf-8"), 1200)
    report_path = run_dir / f"turn-r{round_num}-report.md"
    report_written = report_path.exists()
    swings_path = run_dir / "bigger_swings.md"
    swings_now = swings_path.read_text(encoding="utf-8") if swings_path.exists() else ""
    swings_appended = swings_now != bigger_swings_md  # bigger_swings_md = pre-codex content
    log_event(logger, "loop_steering", round=round_num,
              tests_next_turn=len(next_tests),
              tests_changed=(next_tests != this_turn_tests),
              report_written=report_written, swings_appended=swings_appended)

    # 7. post-commit (editable pipeline + grading/harness files; scenario edits only if allowed)
    sha = None
    if not args.dry_codex and not codex_record.get("reverted"):
        sha = git_commit(round_baseline, args.allow_test_edits,
                         f"watchdog r{round_num}: codex edits (pass={pass_count}/{len(cur_results)})")
        if sha:
            log_event(logger, "committed", round=round_num, sha=sha)

    # 8. record
    issue_map = _scenario_issue_map(summary)
    round_record = {
        "round": round_num, "tag": tag,
        "tests_run": this_turn_tests,
        "results": cur_results,
        "scan": {"ran": len(cur_results), "passed": pass_count, "failed": fail_count,
                 "overall_success": summary.get("overall_success")},
        "failing": [{"scenario_id": sid, "reasons": _issue_lines(issue_map.get(sid, []))}
                    for sid, ok in cur_results.items() if not ok],
        "codex": codex_record,
        "next_turn_tests": next_tests,
        "focus_tail": focus_tail,
        "report": str(report_path) if report_written else None,
        "swings_appended": swings_appended,
        "git_commit": sha,
    }
    outcome["rounds"].append(round_record)
    write_outcome(outcome, run_dir / "outcome.json")
    log_event(logger, "round_done", round=round_num, passed=pass_count, failed=fail_count,
              reverted=codex_record.get("reverted", False), sha=sha)
    return round_record


# --------------------------------------------------------------------------- #
# Outcome persistence
# --------------------------------------------------------------------------- #
def write_outcome(outcome: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(outcome, indent=2, default=str), encoding="utf-8")


def finalize_outcome(outcome: dict[str, Any]) -> None:
    rounds = outcome.get("rounds", [])
    best = max((r["scan"]["passed"] for r in rounds), default=0)
    last = rounds[-1]["scan"]["passed"] if rounds else 0
    outcome["final"] = {
        "rounds_run": len(rounds),
        "best_passed": best,
        "last_passed": last,
        "converged": bool(rounds and rounds[-1]["scan"].get("overall_success")),
        "ended_ts": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python3 scripts/live_agentic_watchdog.py",
        description="Self-improving watchdog: run the live agentic suite, let Codex "
                    "improve the harness prompts + inter-stage data, repeat.",
    )
    p.add_argument("--iterations", type=int, default=10, help="turns (default 10)")
    p.add_argument("--tag-prefix", default="watchdog")
    p.add_argument("--scenarios-dir", default=DEFAULT_SCENARIOS_DIR)
    p.add_argument("--output-base", default="out/agentic")
    p.add_argument("--run-base", default=".watchdog-runs")
    p.add_argument("--run-timeout", type=int, default=2700, help="per-suite seconds (45m)")
    p.add_argument("--codex-model", default="gpt-5.5")
    p.add_argument("--codex-effort", default="medium", choices=["low", "medium", "high"])
    p.add_argument("--codex-timeout", type=int, default=1800, help="per-codex-turn seconds")
    p.add_argument("--codex-max-attempts", type=int, default=2,
                   help="codex attempts per turn on safety-gate failure")
    p.add_argument("--allow-test-edits", action="store_true",
                   help="let codex edit test scenario files (to fix genuinely bad tests; "
                        "every edit is logged + recorded in outcome.json)")
    p.add_argument("--stop-on-green", type=int, default=0,
                   help="stop after N consecutive fully-green turns (0 = never)")
    p.add_argument("--dry-codex", action="store_true",
                   help="build digest+brief, skip the codex call (no codex spend)")
    p.add_argument("--smoke", action="store_true",
                   help="1 turn on a 2-scenario subset to validate the loop end-to-end")
    p.add_argument("--from-summary", default=None,
                   help="reuse a saved runner summary JSON for turn 1 instead of running the suite")
    p.add_argument("--resume", default=None, help="run_id under run-base to resume")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if _ARNOLD_AGENT_IMPORT_ERROR is not None:
        print(
            "ERROR: live agentic watchdog requires the optional Arnold agent runtime; "
            "install the [agent] extra",
            file=sys.stderr,
        )
        return 2
    if not MEGAPLAN_WATCHDOG_AVAILABLE:
        print(
            "SKIPPED: live agentic watchdog requires optional "
            "arnold.pipelines.megaplan",
            file=sys.stderr,
        )
        return 0

    # --from-summary reuses one saved summary (turn 1 only); clamp to 1 turn.
    if args.from_summary and args.iterations > 1:
        args.iterations = 1

    run_base = REPO / args.run_base
    run_base.mkdir(parents=True, exist_ok=True)

    if args.resume:
        run_id = args.resume
        run_dir = run_base / run_id
        outcome = _read_json(run_dir / "outcome.json") or {}
        outcome.setdefault("rounds", [])
        outcome["_start_round"] = len(outcome["rounds"]) + 1
        args.iterations = outcome.get("iterations_target", args.iterations)
    else:
        run_id = time.strftime("run-%Y%m%dT%H%M%S", time.gmtime()) + ("-smoke" if args.smoke else "")
        run_dir = run_base / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        outcome = {"run_id": run_id, "started_ts": _now_iso(),
                   "iterations_target": args.iterations,
                   "allow_test_edits": args.allow_test_edits, "rounds": [], "_start_round": 1}
        outcome["iterations_target"] = args.iterations

    logger = setup_logging(log_path=run_dir / "auto.log")
    log_event(logger, "watchdog_start", run_id=run_id, iterations=args.iterations,
              smoke=args.smoke, dry_codex=args.dry_codex,
              allow_test_edits=args.allow_test_edits)

    # Capture the run-start commit once: prior_diff shows the cumulative pipeline
    # edits across all rounds (vs this baseline). Robust to Codex self-commits.
    run_start_commit = capture_round_baseline()[0]

    # Seed run-control files Codex edits each turn.
    if not (run_dir / "focus.md").exists():
        seed_focus_doc(run_dir, run_id)
    if not (run_dir / "bigger_swings.md").exists():
        seed_bigger_swings(run_dir, run_id)
    src_dir = REPO / args.scenarios_dir
    if not (run_dir / "tests_to_run.json").exists():
        seed_ids = SMOKE_SCENARIOS if args.smoke else all_scenario_ids(src_dir)
        seed_tests_to_run(run_dir, seed_ids)
    if args.smoke:
        args.iterations = 1

    start_round = outcome.get("_start_round", 1)
    green_streak = 0
    try:
        for r in range(start_round, args.iterations + 1):
            rec = run_round(r, args, run_dir, outcome, logger, run_start_commit, args.run_base)
            if rec["scan"].get("overall_success"):
                green_streak += 1
                if args.stop_on_green and green_streak >= args.stop_on_green:
                    log_event(logger, "early_stop", round=r, green_streak=green_streak)
                    break
            else:
                green_streak = 0
    except KeyboardInterrupt:
        log_event(logger, "interrupted", round=len(outcome["rounds"]) + 1)
        finalize_outcome(outcome)
        outcome.pop("_start_round", None)
        write_outcome(outcome, run_dir / "outcome.json")
        print(f"\n[interrupted] outcome: {run_dir / 'outcome.json'}", file=sys.stderr)
        return 130
    except RetryCapExceeded as exc:
        log_event(logger, "retry_cap_exceeded", error=str(exc))

    finalize_outcome(outcome)
    outcome.pop("_start_round", None)
    write_outcome(outcome, run_dir / "outcome.json")
    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir),
                      "final": outcome.get("final", {})}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
