# B06 — Unit, continuity, IR-law, differential validation (Flash + XHARD Pro)

Worktree: /private/tmp/vc-twostep (branch two-step-megado). Python: `PYENV_VERSION=3.11.11`, venv at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv, `PYTHONPATH=$PWD` if needed.

You are implementing batch B06. The differential harness tasks are `[XHARD]` → DeepSeek Pro;
the continuity/IR-law/regression tasks are Flash. If you are the Flash agent, do the
non-XHARD tasks; if Pro, do the XHARD tasks. B01–B05 must be present first
(`git log --oneline -8`).

## Tasks

1. (Flash) Complete the five thread-continuity cases in `tests/test_executor_two_step_continuity.py`:
   - Same session ID reuses ONE execute identity; turn-1 observations + accepted Δ visible.
   - New chat-window ID starts fresh; no prior refs.
   - Route changes mid-thread after reclassification WITHOUT replacing the execute session.
   - Follow-up claiming a missing turn-1 Δ fails.
   - Session budgets accumulate while each message receives only its route slice.

2. (Flash) Reuse all five IR laws against BOTH modes — mode-parameterized executor adapter;
   keep the existing lower-level law suite unchanged.

3. (Flash) Full-path regressions: `classify_only`, `answer_only`, missing execute profile,
   route-policy coverage, tool denial, budget exhaustion, prompt sections,
   events/report compatibility.

4. `[XHARD — Pro]` Concurrency/recovery cases (append to `test_executor_two_step_continuity.py`):
   - Two simultaneous messages for one session serialize or one fails stale.
   - Server restart reconstructs retained state through named ingest + canonical Δ replay.
   - Changed current canvas that does not match retained revision fails CAS.
   - Idempotent message replay does not duplicate tool calls or Δ.

5. `[XHARD — Pro]` `tests/executor_mode_harness.py` + `tests/test_executor_two_step_differential.py`:
   - Inject the SAME locked `ClassifyDecision` into both modes through a test-only seam
     (patch `_run_classify()` or the test-injectable outcome boundary — NO new production
     classifier API).
   - Cover: named-field edits, rewires, add/remove, inspect, research, adapt, reorganise.
   - Compare: `pi_edit(post)` (import the helper deliberately from `tests/test_ir_laws.py:198`
     — it is NOT a production API), accepted Δ replay, evidence validity, failure family,
     latency, tokens, cost.
   - NEVER compare prose equality.
   - Judge outcomes stay in B07 — use a deterministic stub judge here at most.
   - Resolve + inventory all 57 IDs from `vibecomfy.intent._ledger`
     (`ledger_scenario_ids()` at `intent/_ledger.py:293`); refuse duplicate/missing/
     unmanifested ledger IDs.

## Acceptance gate (run everything)

```bash
python -m pytest -q \
  tests/test_executor_pipeline_mode.py tests/test_executor_two_step_policy.py \
  tests/test_executor_two_step_tools.py tests/test_executor_two_step_prompt.py \
  tests/test_executor_two_step_contracts.py tests/test_executor_two_step_atomic.py \
  tests/test_executor_two_step_precedents.py tests/test_executor_two_step_continuity.py \
  tests/test_executor_two_step_reporting.py tests/test_executor_two_step_differential.py \
  tests/test_executor_profiles.py tests/test_executor_classify_only.py \
  tests/test_executor_flows.py tests/test_ir_laws.py
PYTHONHASHSEED=0 python -m pytest -n 8 -q -p no:cacheprovider
```

No B06 pass if any atomicity, reference-integrity, continuity, or full-mode compatibility
test is quarantined or xfailed.

## Constraints
- Flash agent commits its portion: `git commit -m "B06: continuity + IR-law + regressions (Flash)"`.
- Pro agent commits its portion: `git commit -m "B06: differential harness + concurrency (Pro)"`.
  Stage by path to avoid clobbering.
- Do not start B07 work.
- Report: files changed, gate output, deviations.
