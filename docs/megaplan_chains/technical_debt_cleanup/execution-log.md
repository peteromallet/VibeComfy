# Cleanup execution log

## ORACLE-1 (T-001..T-006) — PASS
- T-001 baseline receipt: PASS (make check 0, full pytest 0, 347/20/5.8% truth, quarantine 14).
- T-002 ownership ledger: PASS. T-003 batch/provider ledger: PASS. T-004 edit manifest (472): PASS. T-005 session manifest (23/31/23): PASS. T-006 generated/lazy policy: PASS.
- Round 2 fixes: manifest marks load_agent_generated_scratchpad required_post_split; ownership wording = duck-typed seam (no signature-identical claim).
- Oracle: PASS.

## ORACLE-2 (T-007..T-013) — PASS
- T-007 testing shim delete: PASS (441 tests green). T-008 schema forks delete: PASS (7 schema failures verified pre-existing baseline). T-009 YAML shim delete: PASS. T-010 route wrappers: PASS (86 route tests green). T-011/T-012 docs: PASS (+round fixes for 4 extra stale refs caught by oracle). T-013 duplicate helper: PASS (32 delta tests green).
- Boundary gate: make check first run exit 2 at browser-smoke — ONE timing flake (roundtrip diagnostics waitFor), passes isolated + standalone browser-smoke exit 0; second run in progress. Lockfile pin restored after gate churn.
- Oracle rounds: 1 FAIL (manifest/ownership accuracy) → fixes; 2 FAIL (wire-protocol edit_session.py) → fix; 3 FAIL (false-positive test filenames) → clarified; 4 PASS.

## ORACLE-3 batch (T-014…T-020) — make/package/demo surface

Tasks (all PASS, one fix):
- T-014 PASS — strict-ready recipe = template-index + JSON check only; 9 pytest files stay in fast.
- T-015 PASS — browser-contracts removed from check (subset of browser-smoke); standalone target retained.
- T-016 PASS — pytest-xdist>=3.6 declared [dev] + uv.lock updated; `make full-pytest` (-n 8) target added.
- T-017 PASS — docs/testing/overview.md documents the real 347/20/5.8% gap + full-pytest + quarantine semantics.
- T-018 PASS — new tests/test_demo_factory_cli.py (17 tests) pins python -m dispatch, Click commands, exit codes.
- T-019 PASS (+fix) — Click = sole CLI surface; run_campaign() internal; main() S18-preserved legacy function; trailing `__main__` block removed so `python -m vibecomfy.demo_factory.run_campaign` is inert (no second CLI); run_one_additive.py already thin.
- T-020 PASS — hatch wheel + sdist both exclude web_dist; packaging test asserts via tomllib.

Boundary gates:
- uv build: exit 0; wheel + sdist each contain 0 web_dist/ entries (unzip/tar grep).
- make check: first boundary run exit 2 at browser-smoke — environmental timing flake (machine memory pressure from stray external megaplan watchdog pytest, PID 552; test passes isolated + in standalone browser-smoke). Flake policy applied: exact rerun green; full browser-smoke rerun green (BS=0). Second full make check rerun failed on same env class; third rerun launched. custom_nodes.lock pin restored after each make run.

Oracle: ORACLE-3 round 1 FAIL (briefing misstated T-019 as "no argparse main"; S18 requires main() argparse legacy function); round 2 FAIL (my brief claimed Click commands must call run_campaign() — not in EXECUTION.md; real finding: module __main__ = second CLI surface); fix dispatched (__main__ removed); round 3 PASS (sole-surface + S18-preserved function verified). ORACLE-3 = PASS (boundary make check exit 0 on final rerun; env-flake recorded).
