"""Unit tests for the pure logic in scripts/live_agentic_watchdog.py.

Covers the digest builder, regression detection, issue extraction, the
run-control-file readers, baseline-diff detection, and the codex brief
(including the per-turn checklist). No network, no models, no git.
"""

from __future__ import annotations

import json

from scripts import live_agentic_watchdog as w


# ---- fixtures --------------------------------------------------------------- #
def _scenario(sid: str, ok: bool, *, issues=None, status="completed", error=None,
              expect_graph_changed=True, error_count=None, output_dir="/nonexistent"):
    issues = issues or []
    guard = {
        "live_agentic_success": ok,
        "metadata_success": True,
        "assessment": {
            "passed": ok,
            "expect_graph_changed": expect_graph_changed,
            "issue_count": len(issues),
            "error_count": error_count if error_count is not None else len(issues),
            "issues": issues,
        },
    }
    return {"scenario_id": sid, "status": status, "ok": ok, "error": error,
            "output_dir": output_dir, "guard": guard}


def _summary(scenarios, overall=None):
    if overall is None:
        overall = all(s["guard"]["live_agentic_success"] for s in scenarios)
    return {"tag": "t", "scenario_count": len(scenarios),
            "overall_success": overall, "scenarios": scenarios}


# ---- _results_map / _issue_lines / _scenario_issue_map ---------------------- #
def test_results_map():
    sm = _summary([_scenario("a", True), _scenario("b", False)])
    assert w._results_map(sm) == {"a": True, "b": False}


def test_issue_lines_filters_to_errors_and_intent_judge():
    issues = [
        {"check": "graph_unchanged", "severity": "error", "detail": "no change"},
        {"check": "intent_judge", "severity": "warning", "detail": "C2 failed: x"},  # kept (judge)
        {"check": "timing", "severity": "info", "detail": "slow"},                  # dropped
    ]
    lines = w._issue_lines(issues)
    assert len(lines) == 2
    assert "[error/graph_unchanged]" in lines[0]
    assert "[warning/intent_judge]" in lines[1]


def test_scenario_issue_map_single_pass():
    sm = _summary([_scenario("a", False, issues=[{"check": "x", "severity": "error", "detail": "d"}]),
                   _scenario("b", True)])
    m = w._scenario_issue_map(sm)
    assert set(m) == {"a", "b"}
    assert m["a"] == [{"check": "x", "severity": "error", "detail": "d"}]
    assert m["b"] == []


# ---- build_digest ----------------------------------------------------------- #
def test_build_digest_all_pass_says_nothing_to_fix():
    sm = _summary([_scenario("a", True), _scenario("b", True)])
    out = w.build_digest(sm, None)
    assert "2 passed / 0 failed" in out
    assert "nothing to fix" in out
    assert "Movement" not in out  # no prev_results


def test_main_missing_arnold_reports_prerequisite_error(monkeypatch, capsys):
    """The live command fails clearly while pure helpers remain importable."""
    missing = ModuleNotFoundError("No module named 'arnold'", name="arnold")
    monkeypatch.setattr(w, "_ARNOLD_AGENT_IMPORT_ERROR", missing)

    assert w.main(["--dry-codex"]) == 2
    assert "optional Arnold agent runtime" in capsys.readouterr().err


def test_build_digest_surfaces_intent_judge_and_sorts_by_signal():
    low = _scenario("low", False, issues=[{"check": "graph_unchanged", "severity": "error", "detail": "x"}])
    high = _scenario("high", False, issues=[
        {"check": "intent_judge", "severity": "error", "detail": "C2 failed: frames!=16"}])
    out = w.build_digest(_summary([low, high]), None)
    # higher-signal (intent_judge) scenario must come first
    assert out.index("### high") < out.index("### low")
    assert "intent_judge" in out
    assert "frames!=16" in out


def test_build_digest_harness_weirdness_bucket():
    err = _scenario("flaky", False, status="error", error="Hivemind HTTP error 500")
    out = w.build_digest(_summary([err]), None)
    assert "Harness weirdness" in out
    assert "flaky" in out
    assert "HTTP error 500" in out


def test_build_digest_movement_flags_regressions_and_fixes():
    cur = _summary([_scenario("a", True), _scenario("b", False)])  # a fixed, b regressed
    prev = {"a": False, "b": True}
    out = w.build_digest(cur, prev)
    assert "newly fixed" in out and "a" in out
    assert "REGRESSIONS" in out and "b" in out


# ---- last_focus_block ------------------------------------------------------- #
def test_last_focus_block_extracts_last_turn():
    focus = "intro\n## Turn 1\n- a\n## Turn 2\n- b\n- c\n"
    assert "Turn 2" in w.last_focus_block(focus)
    assert "- b" in w.last_focus_block(focus)


def test_last_focus_block_empty_or_none():
    assert w.last_focus_block("") == ""
    assert w.last_focus_block("no turns here") == ""


# ---- read_tests_to_run ------------------------------------------------------ #
def _patch_known(monkeypatch, known):
    monkeypatch.setattr(w, "all_scenario_ids", lambda _d: list(known))


def test_read_tests_to_run_valid(monkeypatch, tmp_path):
    _patch_known(monkeypatch, ["a", "b", "c"])
    (tmp_path / "tests_to_run.json").write_text(json.dumps(["a", "c", "zzz"]))  # zzz unknown
    assert w.read_tests_to_run(tmp_path, ["b"]) == ["a", "c"]


def test_read_tests_to_run_invalid_falls_back(monkeypatch, tmp_path):
    _patch_known(monkeypatch, ["a", "b", "c"])
    (tmp_path / "tests_to_run.json").write_text("not json")
    assert w.read_tests_to_run(tmp_path, ["b", "c", "zzz"]) == ["b", "c"]


def test_read_tests_to_run_empty_file_uses_fallback(monkeypatch, tmp_path):
    _patch_known(monkeypatch, ["a", "b", "c"])
    (tmp_path / "tests_to_run.json").write_text("[]")
    assert w.read_tests_to_run(tmp_path, ["a"]) == ["a"]


def test_read_tests_to_run_no_file_returns_all_known(monkeypatch, tmp_path):
    _patch_known(monkeypatch, ["a", "b", "c"])
    assert w.read_tests_to_run(tmp_path, []) == ["a", "b", "c"]


# ---- _is_editable (editable-surface predicate) ----------------------------- #
def test_is_editable_pipeline_and_grader_code_yes_scenario_data_no():
    yes = [
        "vibecomfy/executor/prompts.py",
        "vibecomfy/comfy_nodes/agent/provider.py",
        "vibecomfy/intent/prompts/text_judge.prompt.md",
        "vibecomfy/porting/cache/object_info/index.json",
        "tests/live_agentic_harness/guard.py",
        "tests/live_agentic_harness/intent_judge.py",
    ]
    for p in yes:
        assert w._is_editable(p), f"should be editable: {p}"
    no = [
        "tests/live_agentic_harness/scenarios/hotshot-16-frames-agent-edit.json",
        "tests/test_executor_contracts.py",
        "tests/test_live_agentic_watchdog.py",
        "scripts/live_agentic_watchdog.py",
        "docs/watchdog-babysitting-loop.md",
        "README.md",
    ]
    for p in no:
        assert not w._is_editable(p), f"should NOT be editable: {p}"


def test_is_editable_ignores_run_artifacts_and_noise():
    for p in [".watchdog-runs/run-x/outcome.json", "out/agentic/x/y.json",
              ".venv/lib/python3.11/x.py", "__pycache__/x.pyc", "agent-jury/run.sh"]:
        assert not w._is_editable(p), f"noise should not be editable: {p}"


# ---- build_codex_brief ------------------------------------------------------ #
def test_brief_checklist_is_complete_without_test_edits():
    brief = w.build_codex_brief(
        1, "run-x", "DIGEST", False, "", None, ["s1"], "f", "sw")
    for needle in ["MAKE YOUR BET", "focus.md", "turn-r1-report.md",
                   "tests_to_run.json", "bigger_swings.md", "STAY IN BOUNDS",
                   "WHAT YOU CAN CHANGE", "GRADER-EDITS ARE HIGH-TRUST", "NEVER GAME"]:
        assert needle in brief, f"brief missing: {needle}"
    assert "allowlist" not in brief.lower()          # old model fully gone
    # no test-edit step when allow_test_edits is False
    assert "MAY edit the scenario file" not in brief


def test_brief_checklist_includes_test_edit_step_when_allowed():
    brief = w.build_codex_brief(
        1, "run-x", "DIGEST", True, "", None, ["s1"], "f", "sw")
    assert "MAY edit the scenario file" in brief


def test_brief_includes_prev_summary_and_report_pointer_after_turn_1():
    focus = "## Turn 1\n- Bet: did the thing\n"
    brief = w.build_codex_brief(
        2, "run-x", "DIGEST", False, "", {"s1": True}, ["s1"], focus, "sw")
    assert "PREVIOUS CODEX'S SUMMARY" in brief
    assert "did the thing" in brief                      # prev summary surfaced in-prompt
    assert "turn-r1-report.md" in brief                  # in-depth report pointer
    assert "passed (1)" in brief                         # prev turn results


def test_brief_round_1_has_no_prev_summary():
    brief = w.build_codex_brief(
        1, "run-x", "DIGEST", False, "", None, ["s1"], "f", "sw")
    assert "PREVIOUS CODEX'S SUMMARY" not in brief


def test_watchdog_skips_when_optional_megaplan_package_is_missing(
    monkeypatch, capsys
):
    monkeypatch.setattr(w, "MEGAPLAN_WATCHDOG_AVAILABLE", False)
    assert w.main(["--smoke", "--dry-codex"]) == 0
    assert "SKIPPED" in capsys.readouterr().err
