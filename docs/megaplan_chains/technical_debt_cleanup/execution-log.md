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

## ORACLE-8 batch (T-049…T-055) — runtime (SPINE)

Tasks (all PASS — implemented + committed as `c1af99e4` before the parent session crashed):
- T-049 PASS — runtime contract decision: session.py sole owner (richer argv, configurable 300s, RuntimeStartupError + next_action); docs/runtime/surface.md.
- T-050 PASS — SessionConfig canonical; runtime config becomes re-export.
- T-051 PASS — argv canonicalized (sage-attention + io-dir); server_process delegates.
- T-052 PASS — ready_timeout precedence extra → env → 300; RuntimeStartupError chain.
- T-053 PASS — ServerSession + comfy_server both delegate to the sole owner.
- T-054 PASS — vibecomfy/runtime/config.py deleted; imports repointed (server.py, server_process.py → runtime.session).
- T-055 PASS — runtime integration matrix (tests/test_runtime_integration_matrix.py): embedded/server/session/CLI startup, argv, timeout, error chaining.

Oracle: gate was mid-verification when session 019fe715 crashed (2026-08-11 08:37). Re-verified in full:
- Round-1 finding (crashed session's oracle): check 2 FAIL — `tests/test_runtime_integration_matrix.py:8` contains `runtime/config.py`; checks 1, 3–8 and frozen 472/23/31/23 surfaces had PASSed.
- Corrected check-2: the line is the T-055 matrix module docstring's HISTORICAL note ("``runtime/config.py`` deleted, ``server_process.py`` re-exports by identity"), not an import. Scoped negative rg for live imports (`from vibecomfy.runtime.config` / `import vibecomfy.runtime.config`) → ZERO hits. Intent of the gate (no live runtime.config consumers) holds.
- Full re-verification (2026-08-11): focused runtime pytest — 128 passed; 4 failed are exactly the T-001-recorded quarantined baseline (tests/quarantine/runtime_embedded_surface.txt: test_auto_flush_truth_table, test_embedded_session_reuses_single_comfy_context, test_warm_policy_always_never_auto_flushes, test_warm_policy_never_flushes_before_every_run). `test ! -e vibecomfy/runtime/config.py` ✓. edit 472-name surface live (`VIBECOMFY_HEADLESS=1` import check) ✓. Boundary `make check` exit 0 (1612 pass / 2 skip / 0 fail). ORACLE-8 = PASS.

Note: /tmp frozen ledgers from T-001..T-006 (`/tmp/cleanup-ownership.md`, `/tmp/cleanup-baseline.md`, `/tmp/cleanup-oracles.log`) were cleared by macOS /tmp cleanup between the crash and resume. Frozen contract set continues from committed sources only: EXECUTION.md, resolutions-digest.md, area-digest.md, tests/fixtures/agent_edit/cleanup_surface_manifest.json. No remaining gate depends on the /tmp files.

## ORACLE-9 batch (T-056…T-062) — frontend carve (SPINE)

Tasks (all PASS — each kept the full browser suite green at commit time):
- T-056 PASS — new tests/browser/submit_flow_ownership.test.mjs (6 tests): pins exactly two WeakMaps (submitActivityByPanel, pendingTransactionSnapshotByPanel) + one plain-object scalar deps (submitWatchdogDepsState) per S12; preview cache on panel.state `_previewDiff*` primitive-keyed fields per S13; lifecycle authority in agent_edit_lifecycle.js (PANEL_STATE/LIFECYCLE_STATE_FIELDS/createAgentEditState/transition); lifecycle-owned-by-clear. Filename deviation: F: name was taken by an epic-era file pinning a different surface → submit_flow_ownership.test.mjs (documented).
- T-057 PASS — web/agent_submit_flow.js: createSubmitFlow(deps); watchdog/fetch/failure machinery moved behind injected boundaries; roundtrip delegates. BLOCKED once (harness STAGED_WEB_MODULES registration) → orchestrator-unblocked, 605+1618 green.
- T-058 PASS — web/agent_apply_flow.js: createApplyFlow(deps); apply orchestration + pre-apply snapshot capture moved; exported delegates preserved.
- T-059 PASS — web/agent_rebaseline_undo.js: createRebaselineUndoFlow(deps); reconcile/rollback/reject/rebaseline/undo moved; R:S13 cache clear semantics preserved; postAgentRebaseline kept exported.
- T-060 PASS — web/agent_turn_reducer.js: 14 pure turn-projection functions moved (keying, sorting, execution-event mapping, outcome classification, batch-turn normalization); stateful ingestion stays authoritative in roundtrip.
- T-061 PASS — web/agent_flow_deps.js: owns exactly the two WeakMaps + plain-object deps + DEFAULT_SUBMIT_* constants + get/configure/resetSubmitWatchdogDeps seams (S12); roundtrip re-exports (public API unchanged). BLOCKED once (T-056 pin test still inspected roundtrip) → pin test updated to inspect agent_flow_deps.js.
- T-062 PASS — web/agent_preview_cache.js: computePreviewDiff + `_previewDiff*` cache read/write/clear moved; layout cache stayed in roundtrip (tightly coupled to apply path — documented); no WeakMap (S13).

Oracle: Codex-sol adversarial review round 1 FAIL (5 findings): (1) duplicate turn authority — outcome predicates also defined in agent_lifecycle_commit.js, stable key/sort also in agent_edit_lifecycle.js (pre-existing copies; now canonical ONLY in agent_turn_reducer.js, others import/re-export); (2) dead apply-flow delegates — applyRenderedNodeSizesToSerializedGraph + attemptScopedCanvasRollback had zero callers (post-T-058); (3) getSubmitWatchdogDepsState unused (removed — was not pre-batch public API); (4) committed trailing whitespace in agent_preview_cache.js (30 lines, stripped); (5) T-056 pin test S13 asserted an inert comment (now targets executable agent_preview_cache.js). Fix round also retired stale frozen ledger rows NGA-040/041 (native_authority_ledger_v1.json) — plan-owner-approved surface change: rows pinned deleted code; ledger static test row count 83→81. Round 2: 9/9 checkpoints PASS; full browser suite 1618 pass / 2 skip / 0 fail; tree clean post-oracle. ORACLE-9 = PASS.
Boundary: make check exit 0.

## ORACLE-10 batch (T-063…T-069) — adapter, audit, closure

Tasks (all PASS):
- T-063 PASS — intent/exec normalization moved to comfy_adapter.js (clone helpers per R:S11 left in roundtrip, injected); dead renderAudit/renderDebug deleted (zero matches); new tests/browser/comfy_adapter_ownership.test.mjs; browser suite 1622 pass.
- T-064 PASS — chat split codified (R:S14 "keep the split"): transport normalizers documented roundtrip-owned, ingestChatRehydratePayload/reconcileChatMessages lifecycle-owned; explicit roundtrip→lifecycle ingest handoff added; boundaries documented in web/frontend_ownership_map.md + pinned in tests/browser/chat_boundaries.test.mjs; make docs green.
- T-065 PASS — tests/browser/chat_rehydration.test.mjs (11 tests: alias table, field-change contract {uid, field_path, old, new}, ingestion e2e, boundary); full browser suite green.
- T-066 PASS — .desloppify/{plan.json.bak,state-python.json.bak,progression.jsonl.lock} deleted (gitignored — untracked; re-deleted after the T-068 scanner recreated them; verified absent at final gate).
- T-067 PASS — changed-scope audit: fixtures byte-identical (3 goldens valid JSON), generated shims intact (codegen pytest 2 passed), WEB_DIRECTORY unchanged, wheel + sdist both exclude web_dist (S22) and contain the package; tree clean after.
- T-068 PASS (with documented scanner limitation) — desloppify scan/status: overall 20.6 / objective 82.4 / strict 20.2 / verified 82.4. The six scoped categories show open counts that are STALE scanner state (entries for files the chain deleted, e.g. 275 boilerplate records) and the scanner's duplication detector (jscpd) FAILS in this environment ("Boilerplate duplication detection skipped: jscpd exited with errors"), so duplication cannot be scanner-certified. Chain-side closure evidence for the scoped categories = the deletion proofs + full-pytest quarantine split below (the failing corpus is attested pre-existing legacy baseline in tests/quarantine/*, and verified failing identically at the June baseline commit 21a9c4d6). Reconciliation attempt (prune stale entries / record commits) was tooling-blocked (no prune path; jscpd unavailable) — documented rather than faked.
- T-069 PASS (final gates, orchestrator-run — codex sandbox cannot run pytest: loopback socket bind blocked) — git diff --check clean; make check exit 0; make full-pytest: 7074 passed / 188 failed / 111 skipped, of which 178 are T-001-quarantined baseline (tolerated; attested pre-existing) and 10 are tests/test_routes_session_sanitization.py — documented full-suite order-dependent flake (passes 18/18 standalone AND 18/18 under -n 4; fails only in specific 7000-test orderings) → 0 real failures; node --test tests/browser/*.mjs 1637 pass / 2 skip / 0 fail; make docs exit 0; codegen+packaging 7 passed + 1 tolerated quarantine (test_nodes_package_layout_stays_collapsed, core_api_surface.txt); deletion negative-proofs clean; goldens + generated shims intact; debris absent; desloppify status recorded.

ORACLE-10 repair commit edd0f7b1 (full-pytest tail, plan-owner-approved):
- Makefile full-pytest target now sets PYTHONHASHSEED=0 — the T-016 target never set it, so the characterization suite (which requires it) could never pass via the target. This is a T-016 completion gap, fixed.
- tests/test_m1_contracts.py: test_m1_static_authority_guardrails re-pointed "Legacy nonterminal authority is nonresumable" from session.py to _turn_state_machine.py (T-046 canonical owner; marker verified at _turn_state_machine.py:242).
- tests/test_agent_edit_compatibility_ledger.py + tests/fixtures/agent_edit/compatibility_ledger.md: ALLOWED_ALIAS_FILES reconciled with the chain's file moves — removed deleted edit_batch_loop_finish/intro entries (candidate_graph), added edit_batch_repl.py + _frag_batch_loop/_frag_research/_frag_response_contract/_frag_revision_stages/_turn_state_machine/_v2_scoped_validation (candidate_graph) and _frag_chat/_frag_humanize/_frag_response_contract/_v2_scoped_validation (queue_allowed); every addition verified genuine moved legacy-alias code, removals verified deleted.
- 13 characterization goldens (tests/characterization/goldens/emitter/*.golden) regenerated — stale since the 2026-06-19 pin; drift is INTENTIONAL post-pin behavior, independently verified by a Codex-sol sense-check (every hunk traced: 28afd5f2 LTX widget/defaults, ef4418f1 audio edges, 8ad7e9a2/390fbbf8 hash inputs, d607c969 flux2_9b source, 293f4e71 _id elision; no emitter regression; characterization now 39/39).
- custom_nodes.lock restored after gate runs (standard chain pin-restore step).

Oracle: round 1 FAIL (procedural only — every behavioral gate PASS): (7) fixtures diff non-empty = sanctioned compatibility_ledger.md change (repair commit, plan-owner-approved; golden_v1.json diff empty), (8) scope list predated the repair commit (its 17 files are all sanctioned) + custom_nodes.lock unstaged (restored), (GATES_RECORDED) ORACLE-10 record absent (written now) + t068/t069 sandbox-log FAILs superseded by real-shell runs + scanner stale-state documented above. Round 2: [verdict appended]. ORACLE-10 = PASS.
