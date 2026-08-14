# MEGADO BATCH B06 [HARD] — Universal UI evidence and semantic adjudication

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — executor: Grok (grok-4.6, workspace-write). You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only.

## Context
Two gaps from the failure analysis: (1) refusal/unchanged/clarify/non-edit turns lack universal UI evidence (`original.ui.json`/`final.ui.json`), and (2) the 35 D13 semantic non-edit scenarios have rubrics but NO judge — they'd pass on health alone. Also: refusal-kind auto-acceptance currently bypasses groundedness judging.

D13 already delivered: 100-scenario manifest, 35 scenarios with `semantic_answer` rubrics (grounded/relevant/correct → pass; hallucinated/wrong/irrelevant/vacuous/empty → fail), 2 health controls (`excluded_from_semantic_product_rates: true`), 3 corrected edits, fail-closed judge verdict parsers (malformed verdicts fail, never pass). B01 delivered typed evidence. G0R/D13 made the assessor structured-only.

## Tasks (from .oracle/tasklist.md B06)

1. **Persist authoritative `original.ui.json` and `final.ui.json` for EVERY adjudicated route.** Unchanged/refused/clarify routes explicitly project final from original.
2. **Replace refusal-kind auto-acceptance with tri-state grounded-refusal adjudication**: supported blocker + no representable edit → pass; unsupported/fabricated inability → fail; missing evidence/judge outage → undetermined.
3. **Implement ONE rubric-driven tri-state answer judge for the 35 D13 semantic non-edits**: grounded, relevant, correct response → pass; hallucinated/wrong/irrelevant/vacuous/empty-but-valid → fail; unavailable evidence/judge outage → undetermined.
4. **Keep the two health controls structurally scored and separately reported.**
5. **Ensure the three corrected edits use the edit-intent judge.**
6. **Never use prose substrings as evidence.**

## Sense-check precommit (adversary predictions — cover these FIRST)

From `.oracle/sensecheck-remaining-2026-08-13.md`:
1. **"Universal" evidence misses non-edit routes.** Headless synthesis only copies whatever durable JSON happens to exist (`vibecomfy/agent/artifacts.py:467`); executor-only routes explicitly lack the normal edit turn (`vibecomfy/agent/service.py:207`). Require route-matrix fixtures proving BOTH files exist and `final == original` for respond/research/inspect/clarify/refusal.
2. **Refusal remains label-first.** `safe_refusal_accepted` is established BEFORE judging (`tests/live_agentic_harness/assessor.py:641`), and non-`desired` allowlisted refusals bypass the judge. Replace this exemption UNIVERSALLY — identical plausible prose with contradictory schema/graph evidence must fail.
3. **Tri-state collapses to Boolean.** Assessment returns only `passed` (`assessor.py:964`) and the guard maps directly to pass/product-fail. Persist `pass|fail|undetermined`; outage is `undetermined` but still cannot satisfy the scenario. Preserve D13's rule: malformed judge verdicts FAIL, not mislabeled outages.
4. **The 35 rubric scenarios never enter a judge** because judging is gated on expected edits (`assessor.py:821`). The semantic-answer judge must run for the 35 regardless of edit expectation.

## Key files
- `tests/live_agentic_harness/assessor.py`, `intent_judge.py`, `guard.py`, `runner.py`
- `vibecomfy/agent/artifacts.py` (`:467` headless synthesis), `vibecomfy/agent/service.py` (`:207` executor-only route)
- `tests/test_live_agentic_harness_guard_contract.py`, `tests/test_live_agentic_intent_judge_schema_context.py`, `tests/test_headless_agent_artifacts.py`, `tests/test_live_agentic_assessor_score_honesty.py`

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_intent_judge_schema_context.py tests/test_headless_agent_artifacts.py -k 'grounded_refusal or refusal or undetermined or original or final or semantic or rubric or ui_evidence or outage or judge'
```
Plus the full files (expected exit 0; rerunfailures plugin binds a socket and cannot run here):
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py tests/test_live_agentic_intent_judge_schema_context.py tests/test_headless_agent_artifacts.py
```

## Acceptance (from tasklist)
- Refusal fixtures produce pass/fail/fail/undetermined for grounded, unsupported, fabricated, and outage cases.
- A healthy but false explanation fails.
- Judge outage never passes.
- Every selected semantic non-edit has a rubric and judge result.
- All routes carry original/final UI evidence.
- Only `pass` satisfies a semantic scenario.

## Report
Return: per-task changes (file:line), the route-matrix fixtures, the tri-state persistence shape, refusal-judge + semantic-judge fixture results, pytest output. Do NOT commit.
