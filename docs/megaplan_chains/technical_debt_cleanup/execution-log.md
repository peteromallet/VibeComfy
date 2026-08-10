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

## ORACLE-4 batch (T-021…T-027) — Python boundaries

Tasks (all PASS):
- T-021 PASS — new tests/test_agent_route_families.py (7 tests): executor-submit family (3 routes) vs 5 legacy test-only handlers distinct; reject_turn alive; no /agent-edit/audit route.
- T-022 PASS — single `_failure_response` (routes.py:1011); legacy + executor families emit unified envelope; wire + CLI boundaries byte-identical (verified vs old legacy output incl. EDITOR_AHEAD_CONFLICT + nested-recovery).
- T-023 PASS — canonical_hash.js docs cite _canonical_contract_primitives.py; diff comment-only; 38/38 browser tests.
- T-024 PASS — class_inventory_audit uses node_packs._lockfile.read_lockfile(); hand-parsed TOML removed; 3 new tests.
- T-025 PASS — DiagnosticLike Protocol (code/message/severity/detail; non-runtime_checkable; no to_json; exported via ir/__init__); 6 new tests.
- T-026 PASS — 'inplace' at static WIDGET_SCHEMA slot 4; _CURATED_WIDGET_ORDERS deleted; _CURATED_OUTPUTS (output fallback) correctly retained.
- T-027 PASS — generator + regenerated JS emit corrupted_delta family; zero delta_corrupted; codegen 1 + browser 85/63 tests green.

Oracle: round 1 FAIL (over-broad briefing flagged _CURATED_OUTPUTS LTX2_NAG entry — assessed as output-fallback, out of S20 widget scope); round 2 PASS with corrected contract (widget curation gone, schema canonical, _failure_response single, spellings aligned). ORACLE-4 = PASS (boundary make check pending).

## ORACLE-5 batch (T-028…T-034) — JS clone + codegen

Tasks (all PASS, two fix rounds):
- T-028 PASS — tests/browser/deep_plain.test.mjs pins Family-A semantics (17 tests; module missing pre-T-029 by design).
- T-029 PASS — W/deep_plain.js: recursion-stack WeakSet clone; 17/17 green.
- T-030 PASS — Family A migrated to shared deep_plain (lifecycle/response_contract/transaction, 49 call sites); canonical_delta dead _clonePlainData removed; 572/572.
- T-031 PASS — Family B pinned (6 tests: undefined/fn-drop + method injection); harness.mjs STAGED_WEB_MODULES + deep_plain.js (sanctioned T-030 fallout).
- T-032 PASS (+fix) — W/json_clone.js shared JSON-family clone (~90 sites); injected-method outputs never re-cloned; jsonClone no longer aliases on cycle (throws TypeError — S8 bug fixed after T-033 pin exposed it).
- T-033 PASS (after fix) — replay-snapshot independence + cycle-throw pins; agentic_replay 9/9.
- T-034 PASS — generator ownership verified/documented (4 constants + 2 embedded blocks; zero golden reads); guard test; goldens byte-identical.

Oracle: round 1 FAIL — 2 real findings: (1) _cloneLifecycleBaselineValue return-original fallback (last aliasing JSON clone), (2) deep_plain own-__proto__ key corruption. Fixes: jsonClone route + defineProperty copy (2 new __proto__ pins; 383/383). Round 2 PASS. ORACLE-5 = PASS. Boundary make check exit 0. roundtrip_smoke load-flake class re-observed (with/without change, different tests per run) — recorded.
