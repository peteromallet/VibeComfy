# VibeComfy Technical-Debt Cleanup — EXECUTABLE TASK LIST (execute-and-review)

Status: FINAL — solidified by Codex (gpt-5.6-sol) from the refined plan + 23 ground-truth scout resolutions. This replaces the epic/WP structure. Workers execute T-001…T-069 numerically; an oracle reviews after every batch (ORACLE-1…10).

Baseline: `make check` exit 0; full pytest exit 0 with quarantined-baseline tolerated. Truth facts: 347 test_*.py files; make check covers 20 (~5.8%); pytest-xdist undeclared (must be added); edit.__all__ membership-only (order not contractual); session surface = 23 `__all__` + 31 direct-public + 23 private; batch REPL needs a dependency object (75 real deps); runtime has two spawn owners + two timeout contracts (consolidate); golden fixtures are parity corpora NOT generator input; generated JS is test-only; corrupted_delta vs delta_corrupted divergence exists.

---

## ORACLE-1 batch — baseline and manifests

- **T-001 Baseline receipt** — Record HEAD, dirty scope, quarantine, 347/20 Make truth, gate output. F: /tmp/cleanup-baseline.md, /tmp/cleanup-oracles.log. V: `git diff --check; make check; ALL`. low/S; d:—; L1; O1. (R:S17,S23)
- **T-002 Ownership ledger** — Record canonical owners + leave-alone layers. F: /tmp/cleanup-ownership.md. V: `test -s /tmp/cleanup-ownership.md`. low/S; d:T001; L1; O1. (R:S9,S13)
- **T-003 Batch/provider ledger** — Pin `_stage_agent_batch_repl → EditSession.apply_batch → apply_delta`; provider seams separate. F: /tmp/cleanup-ownership.md. V: `rg 'apply_batch|apply_delta|provider' /tmp/cleanup-ownership.md`. low/S; d:T002; L10; O1. (R:S4)
- **T-004 Edit manifest** — Store sorted 472-member `edit.__all__` set + patched/imported subsets. F: `tests/fixtures/agent_edit/cleanup_surface_manifest.json`. V: `VIBECOMFY_HEADLESS=1 .venv/bin/python -c 'from vibecomfy.comfy_nodes.agent import edit; print(len(set(edit.__all__)))'`. low/S; d:T001; L10; O1. (R:S2,S3)
- **T-005 Session manifest** — Store exact `__all__` (23), 31 direct-public, 23 private lists. F: `tests/fixtures/agent_edit/cleanup_surface_manifest.json`. V: `P tests/test_comfy_nodes_agent_session.py tests/test_comfy_nodes_agent_backend_spine.py`. low/S; d:T001; L11; O1. (R:S5,S6)
- **T-006 Generated/lazy policy** — Record generator inputs, parity-only goldens, guarded imports, web_dist policy. F: /tmp/cleanup-ownership.md. V: `rg 'generated|golden|NODE_CLASS_MAPPINGS|web_dist' /tmp/cleanup-ownership.md`. low/S; d:T002,T003; L1; O1. (R:S9,S22)

## ORACLE-2 batch — deletion and staleness

- **T-007 Delete testing shim** — Delete `vibecomfy/testing/agent_edit.py`. V: `! rg 'testing\.agent_edit' vibecomfy tests; P tests/test_comfy_nodes_agent_edit.py`. low/S; L2; O2.
- **T-008 Delete schema forks** — Delete `vibecomfy/schema/{local,object_info,parsing,runtime}.py`. V: `! rg 'schema\.(local|object_info|parsing|runtime)' vibecomfy tests; P tests/test_object_info_schema.py`. low/S; L2; O2. (R:S15)
- **T-009 Delete YAML shim** — Delete `RT/_local_library_yaml.py`. V: `! rg '_local_library_yaml' vibecomfy tests; P tests/test_runtime_session_config.py`. low/S; L2; O2.
- **T-010 Route-wrapper cleanup** — Repoint async handlers to `_session_*`; delete prepare/finalize/rollback/reconcile wrappers; retain `reject_turn` + 5 legacy handlers. F: `A/routes.py`, route tests. V: `P tests/test_agent_executor_routes.py tests/test_routes_session_sanitization.py`. med/M; L6; O2. (R:S1)
- **T-011 Live-doc repair** — Correct stale session/contracts/gates/provider/edit/chat paths. F: `docs/agent-edit/{contracts,wire-protocol,response-contract}.md`. V: negative rg + `make docs`. low/S; L3; O2. (R:S19)
- **T-012 Historical-doc repair** — Correct `_install`/`_lockfile`/pack-resolver/exec-design paths (don't rewrite history). F: `docs/architecture/vibecomfy_exec_node_design.md`, d02 evidence. V: `make docs`. low/S; d:T011; L3; O2. (R:S19)
- **T-013 Remove overwritten helper** — Keep one `_canonical_delta_ops_envelope_payload`. F: `A/edit_transform_stages.py`. V: count==1 + delta tests. low/S; L2; O2.

## ORACLE-3 batch — Make, packaging, CLI

- **T-014 Deduplicate strict-ready** — `strict-ready` = JSON check only; nine files stay in `fast`. F: Makefile. V: `make -n check`. low/S; L4; O3. (R:S17)
- **T-015 Deduplicate browser gates** — Remove `browser-contracts` from `check` only. F: Makefile. V: `make -n check; make -n browser-contracts`. med/S; d:T014; L4; O3.
- **T-016 Declare full pytest** — Add pytest-xdist to [dev], lock, add `full-pytest` (`-n 8`). F: Makefile, pyproject.toml, uv.lock. V: `uv lock --check; make -n full-pytest; uv run pytest --help | rg -- '-n'`. med/M; d:T014,T015; L4; O3. (R:S17,S23)
- **T-017 Document the real gap** — 347 files / 20 selected / 5.8% / quarantine behavior / full gate. F: docs/testing/overview.md. V: rg + `make docs`. low/S; d:T016; L4; O3. (R:S17,S23)
- **T-018 Freeze demo exits** — Tests for both module invocations, Click commands, campaign 0/1, additive 0/2, export/missing-arg. F: new `tests/test_demo_factory_cli.py`. V: `P tests/test_demo_factory_cli.py`. med/M; L5; O3. (R:S18)
- **T-019 Consolidate demo CLI** — Click = sole public surface; campaign internal; wrapper thin; exits pinned. F: demo_factory/{cli,run_campaign}.py, scripts/run_one_additive.py. V: demo CLI tests + `python -m vibecomfy.demo_factory --help`. med/M; d:T018; L5; O3. (R:S18)
- **T-020 Exclude web_dist artifacts** — `exclude=["/vibecomfy/comfy_nodes/web_dist/**"]` under wheel AND sdist. F: pyproject.toml, tests/test_packaging.py. V: `P tests/test_packaging.py`. med/S; L4; O3. (R:S22)

## ORACLE-4 batch — Python boundaries

- **T-021 Characterize route families** — Prove executor routes vs 5 legacy test-only handlers distinct. V: route tests. med/M; L6; O4. (R:S1)
- **T-022 Unify failure envelope** — One `_failure_response`; preserve wire + CLI boundaries. F: A/routes.py + tests. med/M; d:T021; L6; O4. (R:S1)
- **T-023 Correct hash documentation** — JS hash docs → `_canonical_contract_primitives.py`. F: W/canonical_hash.js. V: `N tests/browser/canonical_hash.test.mjs`. low/S; L9; O4.
- **T-024 Reuse lockfile reader** — Replace hand-parsed TOML with `read_lockfile()`. F: tools/class_inventory_audit.py + new test. V: `P tests/test_class_inventory_audit.py`. low/S; L6; O4.
- **T-025 Add DiagnosticLike** — Non-runtime-checkable 4-field Protocol, exported; no to_json requirement. F: ir/{diagnostic,__init__}.py. V: `P tests/test_diagnostics.py`. med/S; L7; O4. (R:S21)
- **T-026 Canonicalize LTX2_NAG** — `inplace` at WIDGET_SCHEMA slot 4; delete consumer curation. F: _compile/_widgets.py, porting/object_info/consume.py. V: `P tests/test_porting_object_info.py`. med/S; L7; O4. (R:S20)
- **T-027 Align delta diagnostics** — Generated JS uses Python-canonical corrupted/truncated/absent/replay_mismatch spellings. F: tools/generate_agent_contract_js.py, generated JS, codegen+parity tests. V: `P tests/test_agent_contract_codegen.py; N tests/browser/{agent_edit_response_contract,canonical_delta}.test.mjs`. med/M; L9; O4. (R:S10)

## ORACLE-5 batch — JS clone and codegen

- **T-028 Specify deep-plain semantics** — Family-A behavior, symbol-key drop, special-value pass-through, repeated-ref reclone, cycle `TypeError`. F: new `tests/browser/deep_plain.test.mjs`. V: `N tests/browser/deep_plain.test.mjs`. high/M; L8; O5. (R:S8)
- **T-029 Implement deep_plain** — Recursive clone/freeze with recursion-stack WeakSet (remove on unwind). F: new `W/deep_plain.js`. V: `N tests/browser/deep_plain.test.mjs`. high/M; d:T028; L8; O5. (R:S8)
- **T-030 Migrate Family A** — 4 manual owners → shared imports. F: agent_edit_lifecycle, agent_edit_response_contract, agent_edit_transaction, canonical_delta + tests. high/M; d:T029; L8; O5. (R:S8)
- **T-031 Characterize Family B** — Pin undefined/function behavior + method injection (cloneDynamicSlot/liveLinkRecord) before migration. F: agentic_replay, preview_picker, roundtrip_smoke, dynamic_io_smoke tests. high/M; d:T029; L8; O5. (R:S8,S11)
- **T-032 Migrate Family B** — Replace JSON clones; never re-clone injected-method outputs. F: agentic_replay, preview_picker, vibecomfy_roundtrip + tests. high/L; d:T031; L8; O5. (R:S8,S11)
- **T-033 Add replay-cycle regression** — Snapshots neither alias nor silently accept cycles. F: tests/browser/agentic_replay.test.mjs. high/S; d:T032; L8; O5. (R:S8)
- **T-034 Correct generator ownership** — Generate only from 4 contract constants + 2 embedded blocks; goldens untouched. F: tools/generate_agent_contract_js.py, generated JS, codegen test. V: codegen pytest + `git diff --exit-code -- FX/*golden_v1.json`. med/M; L9; O5. (R:S9,S10)

## ORACLE-6 batch — edit exec split

- **T-035 Design batch dependencies** — `EditBatchReplDeps` built at invocation resolving the exact 75 names from façade globals; stdlib imports only for Any/Mapping/dataclasses/json/time; no singleton snapshot. F: new `A/edit_batch_repl.py`, new `tests/test_edit_batch_repl_dependencies.py`. high/M; SPINE; O6. (R:S4)
- **T-036 Activate edit compatibility test** — `edit.__all__` as sets + all pinned monkeypatch/import attrs. F: new `tests/test_cleanup_surface_manifest.py`. med/S; d:T004,T035; SPINE; O6. (R:S2,S3)
- **T-037 Extract batch loop** — Move 3 stitched fragments behind late-built deps; retain apply_batch. F: A/edit.py, A/edit_batch_repl.py, delete 3 fragments later. high/L; d:T035,T036; SPINE; O6. (R:S4)
- **T-038 Convert foundation fragments** — Source strings → modules/imports in dependency order (state/humanize/memory/reports/chat/session_bundle/ingest/research). high/L; d:T036; SPINE; O6. (R:S3)
- **T-039 Convert orchestration fragments** — revision/transform/narrator/response/orchestration/entrypoint; preserve guarded imports. high/L; d:T038; SPINE; O6. (R:S3)
- **T-040 Solidify edit façade** — Re-export every frozen public/private member; membership-only `__all__`. med/M; d:T037,T039; SPINE; O6. (R:S2,S3)
- **T-041 Remove exec assembler** — Delete loader/compile/exec machinery + 3 obsolete fragment files. V: negative rg for exec/compile/_SOURCE_GROUPS; surface + backend tests. high/M; d:T040; SPINE; O6. (R:S3,S4)

## ORACLE-7 batch — session extraction

- **T-042 Enforce session manifest** — Exact 23/31/23 name tests. F: tests/test_cleanup_surface_manifest.py. high/S; d:T041,T005; SPINE; O7. (R:S5)
- **T-043 Scaffold façade-first modules** — Empty `_artifact_store`/`_v2_scoped_validation`/`_turn_state_machine` + façade re-exports. high/M; d:T042; SPINE; O7. (R:S5,S6)
- **T-044 Extract artifact store** — No write_state_atomic in range → ordinary injection/imports. V: `! rg 'write_state_atomic' A/_artifact_store.py; P backend_spine`. high/L; d:T043; SPINE; O7. (R:S6)
- **T-045 Extract scoped validation** — Re-export pinned sentinels/helpers. high/L; d:T043; SPINE; O7. (R:S5)
- **T-046 Extract turn state machine** — Late-bind façade write_state_atomic inside `_mutate_turn_state`. high/L; d:T044,T045; SPINE; O7. (R:S5,S6)
- **T-047 Preserve transaction façade** — record_idempotent_response + transaction API stay in session, delegate internals. high/M; d:T046; SPINE; O7. (R:S5,S6)
- **T-048 Close importer compatibility** — executor core/builder, debug cmd, routes, private imports, 4 atomic-write monkeypatch tests. high/M; d:T047; SPINE; O7. (R:S5,S6)

## ORACLE-8 batch — runtime

- **T-049 Decide runtime contract** — session.py sole owner: richer argv, configurable 300s, RuntimeStartupError + exact next action. F: docs/runtime/surface.md + tests. high/M; SPINE; O8. (R:S7)
- **T-050 Canonicalize SessionConfig** — session authoritative; config becomes re-export. high/M; d:T049; SPINE; O8. (R:S7)
- **T-051 Canonicalize argv** — session's sage-attention + io-dir args; server_process delegates. high/M; d:T050; SPINE; O8. (R:S7)
- **T-052 Canonicalize spawn** — ready_timeout precedence extra → env → 300; RuntimeStartupError chain. high/M; d:T051; SPINE; O8. (R:S7)
- **T-053 Delegate both surfaces** — ServerSession + comfy_server use the sole owner. high/M; d:T052; SPINE; O8. (R:S7)
- **T-054 Delete runtime config** — Repoint imports, delete RT/config.py. V: negative rg; `test ! -e`. high/S; d:T053; SPINE; O8. (R:S16)
- **T-055 Runtime integration matrix** — embedded/server/session/CLI startup, argv, timeout, error chaining. high/M; d:T054; SPINE; O8. (R:S7)

## ORACLE-9 batch — frontend carve

- **T-056 Freeze frontend ownership** — Pin exports, lifecycle authority, TWO WeakMaps + scalar deps object, panel-state preview cache. F: tests/browser/frontend_ownership_regression.test.mjs. high/M; d:T049–T055; L13; O9. (R:S12,S13)
- **T-057 Extract submit flow** — Move submit orchestration behind injected boundaries. high/L; d:T056; SPINE; O9.
- **T-058 Extract apply flow** — Apply orchestration; lifecycle authority stays. high/L; d:T057; SPINE; O9.
- **T-059 Extract rebaseline/undo** — Preserve lifecycle clears + panel-state cache semantics. high/L; d:T058; SPINE; O9. (R:S13)
- **T-060 Extract turn reducer** — Pure turn projection out; ingestion/lifecycle stays authoritative. high/L; d:T059; SPINE; O9. (R:S14)
- **T-061 Centralize flow dependencies** — Own exactly submitActivityByPanel + pendingTransactionSnapshotByPanel (WeakMaps) + scalar submitWatchdogDepsState. F: new W/agent_flow_deps.js. high/M; d:T060; SPINE; O9. (R:S12)
- **T-062 Extract preview cache** — Operate on panel.state `_previewDiff*` fields; NEVER WeakMap. high/M; d:T061; SPINE; O9. (R:S13)

## ORACLE-10 batch — adapter, audit, closure

- **T-063 Move adapter normalization** — intent/exec normalization → comfy_adapter; delete dead renderAudit/renderDebug. high/M; d:T056–T062; SPINE; O10. (R:S11)
- **T-064 Codify chat split** — transport normalizers in roundtrip, ingestChatRehydratePayload in lifecycle; document distinct boundaries. med/S; d:T063; SPINE; O10. (R:S14)
- **T-065 Test chat rehydration** — snake/camel aliases, field-change normalization, ingestion end-to-end. high/M; d:T064; SPINE; O10. (R:S14)
- **T-066 Delete debt-state debris** — `.desloppify/{plan.json.bak,state-python.json.bak,progression.jsonl.lock}`. low/S; L13; O10.
- **T-067 Changed-scope audit** — fixtures/generated nodes/WEB_DIRECTORY survived; inspect both archives. med/S; d:T063,T066; L13; O10. (R:S9,S22)
- **T-068 Debt rescan and ledger** — desloppify scan/status; execution log. med/M; d:T067; L13; O10.
- **T-069 Final gates** — every repo/browser/docs/build/negative-deletion gate; no code changes. high/L; d:T065,T068; L13; O10. (R:S17,S22,S23)

---

## Oracle checkpoint briefings

Every checkpoint appends: `PASS|FAIL|BLOCKED — observed: <command/output>; scope: <files>`

- **ORACLE-1 (T-001..006):** owners, 472-member edit set, session lists, canonical batch path, lazy imports, baseline recorded. Cmds: `git diff --check; make check; ALL; rg NODE_CLASS_MAPPINGS; focused session/apply pytest`.
- **ORACLE-2 (T-007..013):** 6 dead modules absent; route repoint safe; reject + 5 legacy handlers remain; stale names + duplicate helper gone. Cmds: deletion `test ! -e` loop; negative rg; `make docs; make check`.
- **ORACLE-3 (T-014..020):** no duplicate make prereqs; full-pytest declared; demo exits pinned; both archives exclude web_dist. Cmds: `make -n check; make -n full-pytest; demo CLI tests; uv build + unzip/tar negative grep for web_dist; make check`.
- **ORACLE-4 (T-021..027):** one failure builder; route families distinct; hash docs correct; shared lockfile parser; 4-field Protocol; canonical inplace; Python delta spellings. Cmds: focused tests; `rg -c '^def _failure_response' == 1`; negative rg for delta_* spellings in generator; `make check`.
- **ORACLE-5 (T-028..034):** deep_plain sole clone owner; Family-B + cycles + injected methods pass; goldens unchanged; codegen deterministic. Cmds: focused Node tests; codegen pytest; `git diff --exit-code -- FX/*golden_v1.json`; `make check`.
- **ORACLE-6 (T-035..041):** frozen edit members survive; 13+4+extra seams resolve; deps count 75; batch uses apply_batch; exec machinery absent; guarded imports lazy. Cmds: surface/deps/edit/backend/narrative tests; negative rg exec/compile/_SOURCE_GROUPS; `make check`.
- **ORACLE-7 (T-042..048):** session 23/31/23 pass; artifact store no atomic late binding; turn-state mutation does; replay/routes/importers pass. Cmds: manifest/session/backend/routes tests; `! rg write_state_atomic _artifact_store`; `rg write_state_atomic _turn_state_machine`; `make check`.
- **ORACLE-8 (T-049..055):** one config/argv/spawn owner; richer argv + configurable timeout/error contract; config module gone. Cmds: runtime tests; `! rg 'runtime\.config'`; `test ! -e RT/config.py`; `make check`.
- **ORACLE-9 (T-056..062):** flows import cleanly; two WeakMaps + scalar deps; preview cache on panel state; lifecycle authoritative. Cmds: frontend ownership/roundtrip/lifecycle/preview tests; `N tests/browser/*.mjs`; `make check`.
- **ORACLE-10 (T-063..069):** adapter/chat ownership; deletion proofs; codegen; packages; docs; debt state. Cmds: `git diff --check; make check; make full-pytest; N tests/browser/*.mjs; make docs; codegen+packaging pytest; debt-debris empty; desloppify scan/status`.

## Weak-worker protocol

1. Work on a cleanup branch; never directly on main.
2. Execute numeric order; parallelize only dependency-ready tasks in different lanes within one batch; one worker owns SPINE.
3. Read every listed file first; unexpected required file = BLOCKED, not improvisation.
4. Characterization tests land before risky moves; run task verify + `git diff --check`; reviewer inspects the diff.
5. Report `PASS|FAIL|BLOCKED — observed: ...; scope: ...`. Repair before advancing.
6. Do not update frozen manifests to make a refactor pass; surface changes need plan-owner approval.
7. Regenerate generated JS whole; never hand-edit. Goldens are parity corpora. Preserve guarded lazy imports.
8. No quarantine, skips, waivers, or dependency loosening.
9. Commit one logical task/pair; record with the debt tracker.
10. No batch starts until its preceding oracle is PASS.

## Definition of done

All T-001–T-069 and ORACLE-1–10 PASS; final commands exit zero; only baseline quarantine remains; both package formats exclude web_dist; deletion negative proofs pass; edit/session/runtime/frontend surfaces match pinned contracts; generated node shims + 3 goldens intact; execution log + desloppify status show all scoped categories closed.
