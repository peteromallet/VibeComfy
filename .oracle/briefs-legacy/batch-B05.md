# B05 — Transactional batch execution and bounded semantic repair (HARD — grok)

Executor: grok (per user directive: grok is the extremely hard task doer).
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).
Work in place; DO NOT commit. Run the verification commands yourself; report PASS/FAIL with outputs.

## Tasks

1. **Make one model-authored batch an atomic transaction.**
   - Touch as required: `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, `vibecomfy/porting/edit/_parse_execute.py`, and focused tests in `tests/test_comfy_nodes_agent_edit.py` / `tests/test_comfy_nodes_agent_backend_spine.py`.
   - Snapshot the working IR/UI/rendered Python and relevant ledger before executing a batch. Any uncaught batch exception must restore the exact snapshot before another model turn or terminal response. Persist a bounded traceback and exception fingerprint without leaking secrets.

2. **Add one corrective semantic repair turn for eligible deterministic code exceptions.**
   - Feed the model the failed batch, typed exception/traceback, and unchanged authoritative state. Permit exactly one repair attempt for NameError-class deterministic batch exceptions.
   - Fingerprint failures and abort when the repair repeats the same fingerprint. Protocol/transport retries remain separate and do not multiply the semantic repair budget.
   - Persist repair eligibility, attempted/not-attempted, initial and repair fingerprints, rollback result, and repair outcome so the measurement gate can compute eligible/attempted/succeeded rates.

## Verification (run all; exit 0 expected)

```bash
.venv/bin/python -m pytest -q \
  tests/test_porting_edit_session_harness.py \
  tests/test_porting_edit_corpus.py \
  tests/test_comfy_nodes_agent_edit.py \
  tests/test_comfy_nodes_agent_backend_spine.py \
  -k 'batch_transaction_rolls_back_on_exception or semantic_repair_succeeds_once or semantic_repair_repeated_fingerprint_aborts or ineligible_batch_exception_does_not_repair or semantic_repair_metrics_are_persisted'
```

```bash
.venv/bin/python -m pytest -q tests/test_porting_edit_session_harness.py tests/test_porting_edit_corpus.py tests/test_comfy_nodes_agent_edit.py tests/test_comfy_nodes_agent_backend_spine.py
```

## Acceptance criteria

- A batch that mutates one statement and then raises leaves IR, UI, rendered Python, ledger, hashes, and candidate artifacts byte-/structure-equivalent to the pre-batch snapshot.
- Every eligible exception gets at most one semantic repair turn; a successful repair lands once from the restored state.
- A repeated fingerprint terminates without a third model call or partial mutation.
- Ineligible exceptions do not consume repair budget and preserve their typed failure.
- Persisted evidence is sufficient to compute eligible, attempted, success, rollback-integrity, and repeated-loop counts.

## Report
"B05 VERDICT: PASS|FAIL|BLOCKED — <one line>" + per-task changes (file:line), verification outputs, residuals. DO NOT commit.
