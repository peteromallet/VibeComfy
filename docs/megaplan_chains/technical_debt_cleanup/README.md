# VibeComfy Technical-Debt Cleanup — Refined Execution Plan

Date: 2026-08-09. Status: approved for execution (Codex sense-checked; 28-area DeepSeek investigation complete).
Baseline: `make check` exit 0; full pytest (`-n 8`) exit 0 with only quarantined-baseline tolerated.

## Provenance

- High-level plan + Codex sense-check (corrections: Phase-0 inventory first, batch_repl-canonical before decomposition, façade-before-split, keep generated files, protocol-not-merge diagnostics, schema shims are deletions not behavior changes, SessionConfig canonicalization before enum work).
- 28 read-only DeepSeek scouts (one per area, evidence-backed verdicts) → `/tmp/area-digest.md`.
- Codex detailed plan (this doc) with tasks + oracle checkpoints.

## Work packages and tasks

### WP-0 — Baseline inventory (5 tasks)
- WP-0.1 Record baseline status, digest verdicts, changed-file policy, quarantined baseline. Verify: `git diff --check`, `make check`, full pytest.
- WP-0.2 Write `/tmp/cleanup-ownership.md` naming canonical owners + leave-alone layers (apply_core, provider seam, projection_registry pair, generated shims).
- WP-0.3 Record canonical batch path `_stage_agent_batch_repl → EditSession.apply_batch → apply_delta`; do not merge provider seams.
- WP-0.4 Add `tests/fixtures/agent_edit/cleanup_surface_manifest.json` (edit.__all__, required session attrs, patched private names). Verify session/backend pytest.
- WP-0.5 Record generated-file + lazy-import policy (guarded NODE_CLASS_MAPPINGS imports stay lazy; web_dist ignored). 

### WP-1 — Deletions and staleness (6 tasks)
- WP-1.1 Delete `vibecomfy/testing/agent_edit.py`. Verify no references + testing pytest.
- WP-1.2 Delete `schema/{local,object_info,parsing,runtime}.py` (dead fork; keep provider.py). Verify schema pytest.
- WP-1.3 Delete `runtime/_local_library_yaml.py`. Verify runtime session pytest.
- WP-1.4 Remove dead sync handlers in `agent/routes.py` (keep `_handle_agent_edit` until envelope unification). Verify route tests. Risk: med.
- WP-1.5 Fix stale docs paths (agent_provider/agent_edit/agent_contracts → agent/*) + node_resolution d02 version-pin claim. Verify `make docs`.
- WP-1.6 Remove the silently-overwritten duplicate `_canonical_delta_ops_envelope_payload` in edit_transform_stages.py. Verify delta/response tests.

### WP-2 — Build/test and CLI consolidation (5 tasks)
- WP-2.1 Make `strict-ready` own only `check_strict_ready_templates --json`; `fast` owns the 9 overlapping files. Verify `make -n check`.
- WP-2.2 Remove `browser-contracts` from `check` (subset of `browser-smoke`); keep as explicit target. Risk: med.
- WP-2.3 Add `full-pytest` target (`-n 8`); document the ~180 tests outside make check.
- WP-2.4 demo_factory: Click CLI = sole user-facing surface; `run_campaign.main()` → internal function; scripts = thin wrappers. Risk: med.
- WP-2.5 Add demo-factory CLI/worker compatibility tests. Risk: med.

### WP-3 — Python boundary cleanup (5 tasks)
- WP-3.1 Unify routes.py's two envelope builders into one `_failure_response` path; preserve FailureEnvelope wire contract; keep VibeComfyError CLI boundary. Risk: med.
- WP-3.2 Fix `canonical_hash.js` docstring (mirrors `_canonical_contract_primitives.py`, not orchestrate.py); do not merge hash families.
- WP-3.3 Replace hand-parsed lockfile TOML in `tools/class_inventory_audit.py` with `read_lockfile()`.
- WP-3.4 Add `DiagnosticLike` structural Protocol; fix stale inheritance docstring; keep domain diagnostic types separate. Risk: med.
- WP-3.5 Move duplicate curated widget entries to the canonical widget source. Risk: med.

### WP-4 — JS clone and contract foundations (5 tasks)
- WP-4.1 New `web/deep_plain.js`: cycle-aware structural clone/freeze, explicit undefined/function handling, NO return-original-on-cycle fallback. Risk: HIGH.
- WP-4.2 Migrate Group-A clone/freeze (4 files) to the shared owner.
- WP-4.3 Audit + migrate Group-B call sites (agentic_replay, preview_picker, roundtrip) for JSON-roundtrip assumptions. Risk: HIGH.
- WP-4.4 Add cyclic-snapshot regression for `agentic_replay.js:532-568` (proves no alias/cycle-silent-return). Risk: HIGH.
- WP-4.5 Promote golden fixtures to generator input; regenerate committed contract JS whole; keep hand-mirrored validation. Risk: med.

### WP-5 — Exec-assembler split (5 tasks)
- WP-5.1 Turn the surface manifest into a failing compatibility test first.
- WP-5.2 Extract `_stage_agent_batch_repl` into `edit_batch_repl.py` (explicit deps; retain apply_batch path).
- WP-5.3 Convert remaining orchestration group from source concatenation to explicit imports in dependency order. Risk: HIGH.
- WP-5.4 Keep `edit.py` as façade re-exporting EVERY frozen symbol (public + private). Do not make `__all__` public-only.
- WP-5.5 Remove obsolete exec machinery only after import/reflection/CLI compatibility passes. Risk: HIGH.

### WP-6 — Session façade and extraction (5 tasks)
- WP-6.1 Add façade imports/re-exports before moving implementation.
- WP-6.2 Extract `_artifact_store` (session.py :1147-1459, :3467-3647); preserve write_state_atomic + patchable attrs.
- WP-6.3 Extract `_v2_scoped_validation` (:4637-5821); re-export `_scoped_sentinel_payload` etc.
- WP-6.4 Extract `_turn_state_machine` (:5828-6402); keep transaction façade in session.py.
- WP-6.5 Prove module-attr patching, private imports, __all__, routes compatible. Risk: HIGH.

### WP-7 — Runtime consolidation (5 tasks)
- WP-7.1 Record canonical SessionConfig fields + compat imports.
- WP-7.2 Make session's richer `_comfy_server_argv` canonical (sage-attention + io dirs); keep server-process re-export.
- WP-7.3 Move 300s readiness + RuntimeStartupError semantics into canonical `_spawn_comfy_server`; ServerSession delegates.
- WP-7.4 Repoint server.py/server_process.py imports to runtime.session; delete runtime/config.py.
- WP-7.5 Verify embedded/server/session CLI behavior. Risk: HIGH.

### WP-8 — Frontend carve and final audit (7 tasks)
- WP-8.1 Freeze shell-owned WeakMaps, public exports, injected-dependency boundaries (ownership tests).
- WP-8.2 Extract `agent_submit_flow.js` (roundtrip ~9100-10330).
- WP-8.3 Extract `agent_apply_flow.js` (~10330-12000); don't move lifecycle authority.
- WP-8.4 Extract `agent_rebaseline_undo.js`, `agent_turn_reducer.js`, `preview_diff_cache.js`; keep 3 WeakMaps in one injected-deps module. Risk: HIGH.
- WP-8.5 Move intent/exec normalization to comfy_adapter; delete dead renderAudit/renderDebug.
- WP-8.6 Collapse double chat-rehydrate projection into lifecycle/contract owner.
- WP-8.7 Final audit: oracle log, `.desloppify` status, gates, no generated/node/web_dist deletions.

## Oracle check-in points (after every ~5 tasks)

All verdicts one line: `PASS|FAIL|BLOCKED — observed: <cmd/output>; scope: <files>`.

- ORACLE-1 (after WP-0.5): canonical-owner ledger, frozen edit/session manifests, lazy guarded imports, generated policy, baseline. Cmds: `make check`, full pytest, `rg NODE_CLASS_MAPPINGS`, focused apply/session tests.
- ORACLE-2 (after WP-1.6): 6 dead modules absent, no imports remain, route deletions intentional, docs fixed, one delta-envelope helper. Cmds: deletion `rg` negatives, route/schema/runtime tests, `make docs`, `make check`.
- ORACLE-3 (after WP-2.5): no double-run prerequisites, full-pytest explicit, one demo CLI. Cmds: `make -n check`, `make -n full-pytest`, demo CLI help, demo tests, `make check`.
- ORACLE-4 (after WP-3.5): one routes envelope builder, correct hash docs, read_lockfile, Protocol-not-merge, one widget-order owner. Cmds: focused pytest, `node --test tests/browser/canonical_hash.test.mjs`, `make check`.
- ORACLE-5 (after WP-4.5): deep_plain sole clone owner, Group-B semantics explicit, golden fixtures drive constants, generated JS committed. Cmds: clone/contract node tests, codegen pytest, generator diff, `make check`.
- ORACLE-6 (after WP-5.5): every frozen edit.py symbol survives, private imports/monkeypatches resolve, batch still uses apply_batch, no eager guarded import. Cmds: surface test, agent backend/edit pytest, `make check`.
- ORACLE-7 (after WP-6.5): façade exports, write_state_atomic, private helper patches, transaction replay, routes/session imports. Cmds: session/transaction/backend/route tests, `make check`.
- ORACLE-8 (after WP-7.5): one SessionConfig, one argv owner, one spawn, preserved readiness/errors, no runtime.config imports. Cmds: runtime tests, negative rg, `make check`.
- ORACLE-9 (after WP-8.5): roundtrip shell ownership, extracted flow imports, lifecycle authority, WeakMap placement, adapter exec normalization, dead renderers removed. Cmds: ownership/static node tests, `node --test tests/browser/*.mjs`, `make check`.
- ORACLE-10 (after WP-8.7): full changed-file scope, generated parity, docs, debt-map categories, gates. Cmds: `make check`, full pytest, `node --test tests/browser/*.mjs`, `desloppify scan --path .`, `desloppify status`, `make docs`.

## Risk register (top 10)

1. Exec flat-name breakage → freeze+test __all__, re-export private names, split incrementally.
2. Session private-helper coupling → façade-first + manifest + monkeypatch tests.
3. Group-B clone semantics → audit callers, cycle-aware clone, explicit tests.
4. Routes envelope drift → one builder, preserve FailureEnvelope, test every error path.
5. Generated-file drift → regenerate whole via existing generator, never hand-edit/delete.
6. Browser-contracts double-run removal → keep explicit targets, remove only duplicate check prereqs.
7. web_dist policy → ignored build output; never delete or gate on it.
8. Runtime startup regression → preserve argv/readiness/logging/errors; test both spawn surfaces.
9. 180 tests outside make check → full-pytest target, run at every risky oracle + final gate.
10. Frontend/lazy-import ownership → preserve WeakMaps + lifecycle authority; keep both guarded imports lazy.

## Definition of done

- All 48 tasks complete; every oracle log entry `PASS`.
- `make check` and full `pytest -n 8` exit 0 with only the quarantined baseline tolerated.
- `desloppify scan/status` shows deletion, duplication, staleness, coupling categories closed.
- Canonical hash/diagnostics/lockfile/ownership/stale-doc fixes landed.
- Generated contract parity byte-for-byte green; generated node shims intact.
- Public imports, CLI surfaces, reflection, batch execution, session patch seams, runtime startup, browser contracts behaviorally equivalent.
