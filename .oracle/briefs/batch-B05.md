# MEGADO BATCH B05-lite [HARD] — Journaled unexpected-exception rollback

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — executor: Grok (grok-4.6, workspace-write). You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only.

## Context
The agent-edit loop executes one model-authored batch of edit statements via `session.apply_batch` (`vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1917`). An uncaught exception mid-batch currently leaves partial state (working IR/UI, ledger, candidate artifacts, telemetry) — the failure analysis and exploration confirmed: WS turn events are fire-and-forget (no outbox), candidate_ui.json is written after mutations land, and the in-memory restore at `_parse_execute.py:89` is bypassed when `_execute_statements` raises at `:70-73`.

**This batch makes one model-authored batch atomic: on unexpected exception, restore exact pre-batch state, close the durable turn as aborted, re-raise. NO repair turn, NO retry loop, NO fingerprint.**

## Tasks (from .oracle/tasklist.md B05-lite)

1. **Loop-entry rollback journal** covering: existing mutable session snapshot (graph, ledger, landed/touched sets, name maps, `value_default_context`, render caches and counters — `vibecomfy/porting/edit/session.py:132`), UI payload, batch accumulators, budget and exit fields, AND exact bytes-or-absence of rendered Python, candidate UI, model request/response, and messages artifacts.
2. **Cover the FULL mutating path** through apply, render, `done()`, and final evidence promotion with ONE exception boundary.
3. **On unexpected exception**: restore session state; restore files byte-for-byte; truncate appended state; close the allocated durable turn as aborted; re-raise.
4. **Persist a separate bounded typed abort diagnostic** after restoration.
5. **Telemetry**: buffer until commit where practical; otherwise emit an explicit abort marker and ensure no event claims the rolled-back candidate committed.
6. **Add no repair call, retry loop, or fingerprint.**

## Sense-check precommit (adversary predictions — cover these FIRST)

From `.oracle/sensecheck-remaining-2026-08-13.md`:
1. **Rollback boundary starts too late.** Model request/response and message artifacts are already changed at `edit_batch_repl.py:1512`, well before mutation at `:1918`. A snapshot immediately before `apply_batch` will not restore loop-entry bytes — the journal must capture the true loop-entry state.
2. **Incomplete state restoration.** The oracle will inject faults after render, candidate write, `done()` and evidence finalization (`:2428`, `:2471`) and compare ALL session fields — not merely `working_ui`.
3. **Irreversible success telemetry.** WS events send immediately and swallow errors (`_frag_entrypoint.py:626`); a fault after the `"done"` event (`edit_batch_repl.py:2512`) can leave committed-looking telemetry for rolled-back work.

## Precommit fixtures (fault-injection matrix)
- absent / empty / non-empty files at the fault point;
- exact byte comparison of rendered Python + candidate UI before/after rollback;
- closed aborted durable turn (no allocated-but-unrecorded turns);
- bounded typed abort record present, no success claim;
- unchanged model-call count (no additional model call).

## Key files
- `vibecomfy/comfy_nodes/agent/edit_batch_repl.py` (apply loop `:1516-1928`, `done()`/finalize `:2428-2471`)
- `vibecomfy/porting/edit/session.py` (`:132` state), `_parse_execute.py` (`:70-90`)
- `vibecomfy/comfy_nodes/agent/_frag_entrypoint.py` (`:626` WS events)
- `vibecomfy/porting/edit/ledger.py` (`lifecycle_events.jsonl`, `rollback_complete`/`recoverable_error` states)
- tests: `tests/test_porting_edit_session_harness.py`, `tests/test_porting_edit_corpus.py`, `tests/test_comfy_nodes_agent_edit.py`, `tests/test_comfy_nodes_agent_backend_spine.py`

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_porting_edit_session_harness.py tests/test_porting_edit_corpus.py tests/test_comfy_nodes_agent_edit.py tests/test_comfy_nodes_agent_backend_spine.py -k 'rollback or abort or transaction or journal or restore or telemetry or atomic'
```
Plus the full targeted files (expected exit 0; the rerunfailures plugin binds a socket and cannot run here):
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_porting_edit_session_harness.py tests/test_comfy_nodes_agent_edit.py -k 'not slow'
```

## Acceptance (from tasklist)
- Faults after mutation, render, candidate write, `done()`, and finalization restore exact pre-batch state AND file existence.
- Ledger, hashes, name maps, and candidate state match the restored graph.
- No partial candidate is observable.
- Durable turns do not remain allocated-but-unrecorded.
- Telemetry cannot report rolled-back work as committed.
- Ordinary validation failures are unchanged.
- No additional model call occurs.

## Report
Return: journal shape + snapshot surface, the exception boundary location, restoration mechanics (state + files + ledger + telemetry), the fault-injection matrix results, fixture names, pytest output. Do NOT commit.
