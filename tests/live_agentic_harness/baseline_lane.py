"""Baseline (no-tools) lane for the live agentic harness.

Measures pure-reasoning performance on problem-diagnosis scenarios: ONE
tool-free model call per scenario with the problem text and the full fixture
workflow JSON in-context, then grades the answer with the same judge rubric
data (desired.outcome / answer_guidance) the agentic lane uses.

Design (post-review):
- Information parity: baseline sees the FULL fixture workflow JSON — the same
  starting state the agentic lane's agent sees. Node-name-only prompts would
  conflate information access with tool value.
- Artifact parity: the model returns a structured verdict
  (root_cause + fix_direction + fix_ops) rather than prose, so both lanes
  grade against the same specificity.
- Judge constancy: the judge is the same pinned DeepSeek route for both lanes
  (run_model_turn tool-free seam). Judge model/prompt hash recorded per result.
- Paired reporting: per-scenario delta (agentic vs baseline), not aggregate means.

Usage (runner):
    python -m tests.live_agentic_harness.runner --tag mytag --profile baseline \\
        --scenarios-dir tests/live_agentic_harness/scenarios_eval59 \\
        --manifest tests/live_agentic_harness/scenario_manifest_eval59.json

Or standalone:
    python -m tests.live_agentic_harness.baseline_lane --scenarios <file.json> [--out out.json]
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parents[2]

# The pinned judge route — same as intent_judge's default. Never the model
# under test: judge/solver separation is a validity requirement, not a taste.
JUDGE_ROUTE = "openrouter"
BASELINE_SYSTEM_PROMPT = (
    "You are a ComfyUI workflow debugging expert. You will be shown a user's "
    "problem report and the full JSON of their workflow. Diagnose the root "
    "cause and prescribe the fix.\n\n"
    "Respond with ONLY a JSON object with exactly these keys:\n"
    '{"root_cause": str, "fix_direction": str, "fix_ops": [{"op": "set|replace|remove|add", '
    '"node": str, "field": str, "value": str}], "confidence": "high|medium|low"}\n\n'
    "root_cause: the underlying cause (not the symptom). fix_direction: the "
    "category of fix (update-node | change-setting | rewire | install-component | "
    "patch-code | not-possible-as-described). fix_ops: concrete operations. "
    "confidence: your certainty the diagnosis is correct."
)

BASELINE_RUBRIC_SYSTEM = (
    "You are grading a diagnosis of a ComfyUI workflow problem. You are given:\n"
    "1. The original problem report\n"
    "2. The grader's answer key (known root cause + fix from the original issue thread)\n"
    "3. The candidate's diagnosis\n\n"
    "Score each dimension 0-2:\n"
    "- root_cause_correct: does the candidate identify the same underlying cause "
    "(or a cause that produces the identical failure)? 2=correct cause, 1=adjacent/plausible "
    "but wrong level, 0=wrong.\n"
    "- fix_direction: does the fix match the answer key's fix family (or an alternative "
    "that resolves the same root cause)? 2=same family, 1=defensible alternative, 0=wrong.\n"
    "- specificity: are node/setting/version names concrete and correct? 2=exact, 1=approximate, 0=vague.\n\n"
    "Hedging gets no credit: a hedge that fails to commit to a cause scores 0 on root_cause_correct.\n"
    "Respond with ONLY JSON: {\"root_cause_correct\": int, \"fix_direction\": int, "
    "\"specificity\": int, \"total\": int, \"verdict\": \"pass|borderline|fail\", \"rationale\": str}"
)


@dataclass
class BaselineResult:
    scenario_id: str
    answer: str
    parsed: dict[str, Any] | None
    judge: dict[str, Any] | None
    error: str | None = None


def _load_workflow_json(scenario: Mapping[str, Any], repo: Path = REPO) -> dict[str, Any] | None:
    """Load the scenario's fixture workflow (full JSON — information parity)."""
    wp = scenario.get("workflow_path")
    if not wp:
        return None
    p = Path(wp)
    if not p.is_absolute():
        p = repo / wp
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except Exception:
        return None
    # Frontend-format graphs embed under "workflow" or carry nodes/links directly.
    if isinstance(data, dict):
        for key in ("workflow", "graph"):
            inner = data.get(key)
            if isinstance(inner, dict) and "nodes" in inner:
                return inner
    return data if isinstance(data, dict) else None


def _render_graph_digest(wf: Mapping[str, Any], max_nodes: int = 200) -> str:
    """Compact but complete node/edge listing for the prompt."""
    nodes = wf.get("nodes") or []
    links = wf.get("links") or wf.get("edges") or []
    if isinstance(nodes, dict):  # API format
        lines = []
        for nid, n in list(nodes.items())[:max_nodes]:
            ctype = n.get("class_type", "?")
            widgets = n.get("inputs") or {}
            wstr = ", ".join(f"{k}={v!r}" for k, v in list(widgets.items())[:6])
            lines.append(f"  #{nid} {ctype}({wstr})")
        node_block = "\n".join(lines)
        link_block = ""
    else:  # UI format
        lines = []
        for n in nodes[:max_nodes]:
            if not isinstance(n, dict):
                continue
            widgets = ", ".join(
                f"{v.get('name')}={v.get('value')!r}" for v in (n.get("widgets_values") or [])[:6] if isinstance(v, dict)
            ) or repr(n.get("widgets_values"))[:60]
            lines.append(f"  #{n.get('id')} {n.get('type','?')}({widgets})")
        node_block = "\n".join(lines)
        edge_lines = []
        for l in links[:100]:
            if isinstance(l, dict):
                edge_lines.append(f"  #{l.get('l_id', l.get('id','?'))}: #{l.get('from_id', l.get('l_from_id','?'))} -> #{l.get('to_id', l.get('l_to_id','?'))}")
            elif isinstance(l, list) and len(l) >= 4:
                edge_lines.append(f"  {l[1]} -> {l[3]}")
        link_block = "\n".join(edge_lines)
    return f"NODES:\n{node_block}\n\nLINKS:\n{link_block}"


def _hydrate_credentials() -> None:
    """Load the sibling .env so OPENROUTER_API_KEY is present in-process.

    The agentic lane gets this hydration from run_headless_scenario; the
    baseline lane bypasses that adapter, so it must hydrate on its own.
    """
    candidate = os.environ.get("BANODOCO_BRAIN_ENV") or str(REPO / ".env")
    if Path(candidate).is_file():
        for line in Path(candidate).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def run_baseline_turn(
    scenario: Mapping[str, Any],
    *,
    route: str = "openrouter",
    model: str | None = None,
    repo: Path = REPO,
) -> BaselineResult:
    """One tool-free model turn: problem + full workflow JSON → structured diagnosis."""
    _hydrate_credentials()
    from vibecomfy.comfy_nodes.agent.provider import run_model_turn

    sid = str(scenario.get("id") or "scenario")
    wf = _load_workflow_json(scenario, repo=repo)
    if wf is None:
        return BaselineResult(sid, "", None, None, error="fixture workflow missing or unparseable")
    digest = _render_graph_digest(wf)
    # Byte-identical problem text: strip tool-flavored phrasing both lanes share.
    query = re.sub(
        r"(?i)\b(edit|change|modify)\s+(the\s+)?(workflow|graph|file)\b",
        "fix",
        str(scenario.get("query") or ""),
    )
    user_content = (
        f"PROBLEM REPORT:\n{query}\n\nWORKFLOW:\n{digest}"
    )
    try:
        resp = run_model_turn(
            "diagnose workflow problem",
            messages=[
                {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            route=route,
            model=model,
            response_contract="json",
        )
    except Exception as exc:
        return BaselineResult(sid, "", None, None, error=f"model call failed: {exc}")
    raw = resp.get("content") or ""
    try:
        parsed = json.loads(raw)
    except Exception:
        return BaselineResult(sid, raw, None, None, error="unparseable JSON answer")
    return BaselineResult(sid, raw, parsed, None)


def judge_baseline_answer(
    scenario: Mapping[str, Any],
    result: BaselineResult,
    *,
    route: str = JUDGE_ROUTE,
    model: str | None = None,
) -> dict[str, Any]:
    """Grade a baseline answer against the scenario's answer key."""
    from vibecomfy.comfy_nodes.agent.provider import run_model_turn

    desired = scenario.get("desired") or {}
    answer_key = desired.get("answer_guidance") or desired.get("outcome") or ""
    parsed = result.parsed or {}
    user_content = json.dumps({
        "problem": scenario.get("query", ""),
        "answer_key": answer_key,
        "candidate_diagnosis": {
            "root_cause": parsed.get("root_cause", ""),
            "fix_direction": parsed.get("fix_direction", ""),
            "fix_ops": parsed.get("fix_ops", []),
        },
    }, indent=2)
    try:
        resp = run_model_turn(
            "grade workflow diagnosis",
            messages=[
                {"role": "system", "content": BASELINE_RUBRIC_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            route=route,
            model=model,
            response_contract="json",
        )
    except Exception as exc:
        return {"pass_": None, "error": f"judge call failed: {exc}"}
    raw = resp.get("content") or ""
    try:
        verdict = json.loads(raw)
    except Exception:
        return {"pass_": None, "error": "judge returned unparseable JSON", "raw": raw[:400]}
    verdict["answer_key_used"] = bool(answer_key)
    return verdict


def run_baseline_scenario(
    scenario: Mapping[str, Any],
    *,
    tag: str = "baseline-run",
    output_base: Path | str | None = None,
    route: str = "openrouter",
    model: str | None = None,
    repo: Path = REPO,
) -> dict[str, Any]:
    """Full baseline lane: one diagnosis turn + judge. Returns a summary dict."""
    import datetime

    sid = str(scenario.get("id") or "scenario")
    result = run_baseline_turn(scenario, route=route, model=model, repo=repo)
    if result.error:
        return {"scenario_id": sid, "lane": "baseline", "ok": False, "status": "executor_failure",
                "error": result.error, "lane_model": model or "default", "tag": tag,
                "ts": datetime.datetime.now().isoformat()}
    judge = judge_baseline_answer(scenario, result, route=route, model=model)
    total = judge.get("total")
    ok = isinstance(total, int) and total >= 4  # ≥4/6 across dimensions
    summary = {
        "scenario_id": sid, "lane": "baseline", "ok": ok, "status": "success",
        "judge_verdict": judge.get("verdict"), "judge_total": total,
        "judge_detail": {k: judge.get(k) for k in ("root_cause_correct","fix_direction","specificity","rationale")},
        "candidate": result.parsed,
        "judge_model": route, "tag": tag,
        "ts": datetime.datetime.now().isoformat(),
        "prompt_hashes": {
            "system": hashlib.sha256(BASELINE_SYSTEM_PROMPT.encode()).hexdigest()[:16],
            "rubric": hashlib.sha256(BASELINE_RUBRIC_SYSTEM.encode()).hexdigest()[:16],
        },
    }
    return summary



def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Run baseline (no-tools) lane on scenarios")
    parser.add_argument("--scenarios", nargs="+", required=True, help="scenario JSON files or a glob")
    parser.add_argument("--out", default="out/agentic/baseline/results.json")
    parser.add_argument("--route", default="openrouter")
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)

    files: list[str] = []
    for pattern in args.scenarios:
        files.extend(glob.glob(pattern))
    results = []
    for f in files:
        scenario = json.loads(Path(f).read_text())
        r = run_baseline_scenario(scenario, route=args.route, model=args.model)
        results.append(r)
        print(f"{r['scenario_id']}: {'PASS' if r.get('ok') else 'FAIL'} ({r.get('judge_total','?')}/6)")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"results": results, "n": len(results)}, indent=1))
    passed = sum(1 for r in results if r.get("ok"))
    print(f"\n{passed}/{len(results)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
