# B06 — Grounded-refusal adjudication and UI evidence coverage (HARD — grok)

Executor: grok (per user directive: grok is the extremely hard task doer).
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).
Work in place; DO NOT commit. Run the verification commands yourself; report PASS/FAIL with outputs.

## Tasks

1. **Add an explicit refusal adjudication mode.**
   - Touch as required: `tests/live_agentic_harness/assessor.py`, `tests/live_agentic_harness/intent_judge.py`, `vibecomfy/intent/prompts/refusal_judge.prompt.md` (new, if a separate prompt is used), `tests/test_live_agentic_harness_guard_contract.py`, and focused judge tests.
   - For a no-edit refusal, adjudicate exactly: the stated blocker is supported by artifacts/schema, no viable representable edit was available, the response gives a specific next action, and it does not fabricate inability. Broaden `allow_safe_refusal` configuration without auto-passing the allowed outcome kind.
   - Return `pass`, `fail`, or `undetermined`; a judge outage/missing evidence is `undetermined` and never a pass.

2. Make UI evidence universal for adjudicated turns.
   - Touch: `vibecomfy/agent/artifacts.py`, `tests/test_headless_agent_artifacts.py`, plus any minimal durable-artifact plumbing required.
   - Always persist `original.ui.json` and `final.ui.json`; for an unchanged/refused turn, final is an explicit copy/projection of the authoritative original. Keep `candidate.ui.json` for edit-candidate compatibility where applicable.

## Verification (run all; exit 0 expected)

```bash
.venv/bin/python -m pytest -q \
  tests/test_live_agentic_harness_guard_contract.py \
  tests/test_live_agentic_intent_judge_schema_context.py \
  tests/test_headless_agent_artifacts.py \
  -k 'grounded_refusal or refusal_judge_outage_is_undetermined or every_adjudicated_turn_has_original_and_final_ui'
```

```bash
.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py tests/test_live_agentic_intent_judge_schema_context.py tests/test_headless_agent_artifacts.py
```

## Acceptance criteria

- Merely configuring `allow_safe_refusal` cannot produce a pass; all four groundedness criteria must be positively supported.
- Grounded, ungrounded-give-up, fabricated-inability, and judge-outage fixtures produce `pass`, `fail`, `fail`, and `undetermined` respectively; only the first can satisfy the guard.
- Missing judge service or UI evidence is visible and counted as undetermined, never silently green.
- Deterministic fixtures have 100% `original.ui.json` + `final.ui.json` coverage for edit, refusal, clarify, and executor-only routes.
- Output exposes enough counts to calculate grounded-refusal precision/recall and judge availability in B09.

## Report
"B06 VERDICT: PASS|FAIL|BLOCKED — <one line>" + per-task changes (file:line), verification outputs, residuals. DO NOT commit.
