bun(44662) MallocStackLogging: can't turn off malloc stack logging because it was not enabled.
I'll start by reading the megado skill and the B05-lite tasklist so the review stays on the stated acceptance criteria.Next I’ll pull the B05-lite acceptance criteria and fan out read-only verification so the gate is evidence-based, not just the executor’s report.I have the acceptance bar. Next I’ll read the journal and session snapshot surface, then dispatch independent verification while the focused tests run.The journal exists; now I’ll check whether the session snapshot and exception boundary actually cover the full loop-entry surface.The journal is taken at loop entry, which is the right place. I still need to confirm the single exception boundary actually wraps apply through finalize.The boundary starts at apply, which matches the task. Next I’ll check snapshot completeness, ledger restore, and whether tests actually cover the fault matrix.Tests cover the named fault points. I’ll now inspect helpers and exception handling, and send independent Flash reviews in parallel.The abort path re-raises into `_run_stage`, which is the right shape. Next I’ll check the failure response for leaked candidates, then run the focused tests and independent reviews.Tests and Flash reviews are running. I’ll keep probing restore gaps and whether the failure path can still publish a candidate.The loop-body delta is only the journal wrap. Next I’ll check whether revision-evidence objects are mutated in place after snapshot.Flash finished. I’ll read those reviews against the code before locking the verdict.Independent Flash review is in. One agent wanted a FAIL on schema-cache leftovers and pre-apply model-call paths; those sit outside the stated mutating-path contract, and `_run_stage` still records the turn. The rest of the evidence supports a pass.

**B05 CHECKPOINT VERDICT: PASS — Loop-entry journal + one apply→finalize boundary restores session/files, closes the turn aborted, and cannot emit committed telemetry.**

## Per-focus findings

### 1. Journal snapshot surface — COMPLETE for the required contract

`capture_loop_entry_journal` runs at true loop entry (`edit_batch_repl.py:1457`), before model-request write (`:1524`) and well before mutation (`:1933`). That closes sense-check #1 (snapshot-too-late).

Session snapshot (`_parse_execute.py:141–155`) now includes the `session.py:132` mutable edit surface the oracle said it would compare:

- `working_ui` (deepcopy), `landed_ops`, `touched_uids` / `touched_node_ids`
- `uid_by_name` / `name_by_uid` / `unbound_names`
- `value_default_context` (frozen; apply reassigns via `protect_node`)
- `render_count`, `last_rendered_source`, `last_rendered_workflow`, `last_render_diagnostics`

Ledger is not stored as a second object; `_restore_snapshot` re-ingests from the restored UI (`:159`). That matches “ledger … match the restored graph,” and is the same restore apply_batch already used.

REPL state (`batch_rollback_journal.py:28–49`) covers UI payload, Python-after, batch accumulators, budget/exit/done/final summaries, report/artifacts, revision evidence, provider metadata, and `plan_evaluation`. Journaled files (`:50–57`) are after.py, candidate UI, model request/response, messages, and revision evidence — bytes or absence.

Not journaled, and **not** a gate fail against the written tasklist: `schema_provider` / `provisional_registry_candidate_hashes` (B04 cache wrap at `_frag_response_contract.py:769–795`) and `execution_plan.json` / `plan_evaluation.json` (only written when a plan exists). Those are not graph/candidate artifacts; the failure path still sets `has_candidate=False`.

### 2. Exception boundary — ONE boundary on the mutating path; no escape

Non-whitespace delta in `edit_batch_repl.py` is +35 lines: journal import, loop-entry capture, `begin_turn_event_buffer` + `try` at `:1930–1932`, five inject points, `except` → `abort_journaled_batch` + re-raise (`:2635–2646`), `finally` commit only if not aborted.

That `try` wraps apply → enrich → render → candidate write → lint/accumulators → `done()` → finalize → done telemetry construction. Every listed fault point is inside it.

`apply_batch` itself gained a matching `try` (`_parse_execute.py:70–139`) so an unexpected raise during execute restores the inner snapshot before the outer journal runs. Validation still returns `BatchResult` (no raise).

Model-call / protocol handlers at `:1595–1674` sit **before** the mutating `try`. That is the specified boundary (“apply, render, `done()`, final evidence promotion”), not a hole in it. Those exceptions still become `_StageBlocked` via `_run_stage` (`_frag_orchestration.py:29–46`) and are recorded as ordinary failures — they are not allocated-and-forgotten.

### 3. Restoration — byte/struct-exact on the required surface

`abort_journaled_batch` order is restore → `abort.json` → close durable turn → abort WS marker (`batch_rollback_journal.py:308–345`). Diagnostic is bounded (`error` capped at 500), typed (`batch_repl_abort_v1` / `unexpected_batch_exception` / `aborted` / `committed: false`), and written **after** restore.

Files: absent → unlink; empty/non-empty → exact bytes (`restore_file` `:111–125`). Appended `messages.jsonl` is restored by byte replace, which is truncation.

Durable turn: `close_allocated_turn_as_aborted` stamps `turns[turn_id].abort` and forces `no_candidate` when there is no hash (`:261–275`). `_StageBlocked` then `record_idempotent_response` may overwrite `response.json` with the product failure envelope (`has_candidate=False`); it does **not** clear the abort stamp, and `_mapping_graph_hash` only stamps a candidate when `response["graph"]` is present — failure responses do not carry one.

### 4. Telemetry / validation / model calls — HOLDS

Buffer is the sense-check #3 fix, not ornament:

- `begin` at apply (`:1930`); `done` / `in_progress` inside the `try` are buffered (`_frag_entrypoint.py:679–682`)
- abort discards the buffer then emits `status=aborted` immediately (`:673–678`, `journal.py:320–341`): `rolled_back=True`, `committed=False`, `landed_op_count=0`, `done_summary` stripped
- `finally` commits only when `_journal_failed` is false (`:2647–2649`)
- `after_finalize` inject is **before** the `done` emit (`:2495` vs `:2532`); a throw after emit is still caught and discarded

Ordinary validation is unchanged: `apply_batch` still returns `ok=False` + `batch_transaction_rolled_back`; `done()` `ok=False` returns `StageResult` at `:2461–2481` without abort. No repair/retry/fingerprint on the abort path. Model-call count stays 1 (`test_batch_repl_abort_does_not_make_another_model_call`). The `model_attempts` typed-empty addition on `test_agent_edit_batch_empty_model_response_retries_once_then_commits` is a B01 backstop, not a new retry.

### 5. Fixtures — matrix present

| Requirement | Coverage |
| --- | --- |
| absent / empty / nonempty files | `test_file_snapshot_journal_restores_absent_empty_and_nonempty` |
| after apply / render / candidate write / done / finalize | parametrized `test_batch_repl_unexpected_exception_journal_restores_loop_entry` |
| second-turn nonempty byte restore | `test_batch_repl_abort_restores_nonempty_loop_entry_files_on_second_turn` |
| closed aborted turn + abort.json + no candidate hash | `:20733–20749` |
| no `done` telemetry | `test_batch_repl_abort_telemetry_does_not_claim_done` |
| no extra model call | `test_batch_repl_abort_does_not_make_another_model_call` |
| session journal + validation rollback unchanged | `test_apply_batch_unexpected_exception_restores_session_journal`, `test_apply_batch_validation_rollback_unchanged_on_later_edit_failure` |

No dedicated REPL test that a validation-failed batch leaves `abort.json` absent. Not blocking: that path does not raise, and the existing transaction-rollback tests still run in this slice.

### 6. Scope + whitespace — CLEAN

`git diff --check 655d2f11..6109a9ab` exit 0.

Files: `.oracle/briefs/batch-B05.md`, `batch_rollback_journal.py` (new), `edit_batch_repl.py`, `_parse_execute.py`, `_frag_entrypoint.py`, `tests/test_comfy_nodes_agent_edit.py`, `tests/test_porting_edit_session_harness.py`. No extras.

`edit_batch_repl.py` `git diff -w` is only the journal wrap; the +1291/−697 is indent.

### 7. Focused slice (this session)

```
.venv/bin/python -m pytest -p no:rerunfailures -q \
  tests/test_porting_edit_session_harness.py \
  tests/test_porting_edit_corpus.py \
  tests/test_comfy_nodes_agent_edit.py \
  tests/test_comfy_nodes_agent_backend_spine.py \
  -k 'rollback or abort or transaction or journal or restore or telemetry or atomic or fault or byte'
```

**62 passed**, 725 deselected, 17.60s, exit 0.

## Residual notes (not blocking)

- Schema-provider enrichment and provisional-hash frozenset are not rolled back. Cache-only; failure responses stay non-applyable. Worth journaling only if a later batch treats that wrap as authority.
- Plan evaluation **files** are not journaled (`plan_evaluation` **state** is). Harmless in the current matrix (no plan); leftover eval JSON on a planned request would be a leftover artifact, not a candidate.
- `_BATCH_STATE_FIELDS` is a drift list. Explicit is still better than `vars(state)` (paths, session objects).
- `restore_file` / `close_allocated_turn_as_aborted` swallow I/O errors; the `_StageBlocked` recorder is the backstop for turn close.

No issue list. B05-lite may proceed.
