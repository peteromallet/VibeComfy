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

## ORACLE-6 batch (T-035…T-041) — edit exec split (SPINE)

Tasks (all PASS):
- T-035 PASS — A/edit_batch_repl.py: EditBatchReplDeps (75 fields: 58 private + 17 public, symtable-derived) + invocation-time build_edit_batch_repl_deps; stdlib-only imports; no singleton; 8 tests.
- T-036 PASS — tests/test_cleanup_surface_manifest.py (19 tests): 472 __all__ set-equality, 13 patched, 4 imported, required_post_split membership.
- T-037 PASS — 3 batch-loop fragments (2436 lines) → edit_batch_repl.py real functions behind late-built deps; edit.py delegates; apply_batch retained.
- T-038 PASS — 8 foundation fragments → _frag_*.py modules (dependency order); 12 call-time late imports break cycles; 111-test slice.
- T-039 PASS — 8 orchestration groups → _frag_*.py (142 names); guarded imports preserved; load_agent_generated_scratchpad live; 2 T-038 latent fixes.
- T-040 PASS (+fix) — edit.py clean re-export façade; exec machinery deleted; __all__ static frozenset (472); adversarial review found LOGGER dual-provider + _stage_agent_batch_repl dual-provider → fixed (LOGGER unified to pre-split name ...edit_response_contract; -1568 lines).
- T-041 PASS (+doc/test fixes) — 3 obsolete fragment files deleted; negative rg zero; stale contracts.md link fixed (make docs); _ws_send emit-scan test updated to agent-package scope.

Oracle: adversarial Codex-sol review round 1 FAIL (LOGGER + _stage_agent_batch_repl dual providers) → fixed → round 2 PASS. ORACLE-6 oracle round 1 FAIL (briefing over-scope: 7 edit_batch_loop matches were ledger/provenance docs + 1 real stale doc link) → doc fixed → round 2 PASS. ORACLE-6 = PASS.

Boundary gates: full test_comfy_nodes_agent_edit.py AE=0 (441 tests; 1 static-scan test fixed), full backend_spine SPINE=0, browser-smoke standalone BS=0 (env flake class — stray external watchdog pytest PID 552 caused waitFor timeouts; process now exited), make docs green, final make check exit 0. custom_nodes.lock pin restored after each gate.

## ORACLE-7 batch (T-042…T-048) — session extraction (SPINE)

Tasks (all PASS):
- T-042 PASS — tests/test_cleanup_surface_manifest.py +58 session tests (23/31/23 exact lists; 77 total).
- T-043 PASS — empty _artifact_store/_v2_scoped_validation/_turn_state_machine scaffolds + session façade star-imports.
- T-044 PASS — _artifact_store.py: 18 names from ranges :1147-1459/:3467-3647; zero write_state_atomic; session -494 lines pure deletion.
- T-045 PASS — _v2_scoped_validation.py: 49-name module; session -1241 lines; all 23 private_imported_by_name resolve.
- T-046 PASS — _turn_state_machine.py: _mutate_turn_state extracted; write_state_atomic late-bound at call time (S6); session -2259 lines.
- T-047 PASS — record_idempotent_response + transaction API stay in session as thin delegates; load_candidate_transaction* wrappers restored.
- T-048 PASS — importer audit clean (executor core/builder, debug cmd, routes); debug ownership test → _turn_state_machine.py canonical owner; atomic-write monkeypatch tests green.

Oracle: PASS round 1 (first batch without oracle iterations). Boundary: full backend_spine 0 (291), full agent-edit 0 (441), browser-smoke standalone 0, make check exit 0 (clean run); settings-popover waitFor flake class re-recorded (env timing; standalone green). ORACLE-7 = PASS.
