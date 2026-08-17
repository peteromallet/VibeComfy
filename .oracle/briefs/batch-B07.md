# B07 — 50-scenario lane + paired comparison harness (XHARD Pro + Flash)

Worktree: /private/tmp/vc-twostep (branch two-step-megado). Python: `PYENV_VERSION=3.11.11`, venv at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv, `PYTHONPATH=$PWD` if needed.

You are implementing batch B07. The comparator + all-100-classification bootstrap are
`[XHARD]` → DeepSeek Pro; runner CLI/manifest/doc tasks are Flash. B01–B06 must be present
first (`git log --oneline -10`).

## Tasks

1. (Flash) Extend the headless/live path:
   - `vibecomfy/agent/contracts.py` — pipeline_mode already threaded from B01; ensure the
     live path can pass it.
   - `tests/live_agentic_harness/adapter.py` (~135) + `runner.py` — add
     `--pipeline-mode {full,two_step}`; every two-step scenario gets a stable per-window
     `session_id`.

2. `[XHARD — Pro]` All-100 classification bootstrap + deterministic 50-case selection
   (route-stratification is impossible before locks exist):
   - Classify all 100 scenarios ONCE → freeze `classification_lock.json`.
   - Select/freeze 50 with the quota table:
     routes: clarify 2, respond 8, inspect 8, research 8, requires-custom-nodes 2,
     revise 12, adapt 8, reorganise 2; behavior: 24 edit / 26 non-edit; ledger:
     25 in-57 / 25 out; graph size: 15 small / 20 medium / 15 large; media:
     13 image / 14 video / 12 multimodal / 5 audio / 5 3D / 1 special.
     Route/edit/ledger quotas HARD; media/size best-fit with documented stable-hash
     fallback + committed actual quota table.
   - `tests/live_agentic_harness/two_step_50_manifest.json`: references ALL 100 canonical
     descriptors (strict validation intact), 50 included / 50 excluded; pin descriptor +
     source hashes.

3. `[XHARD — Pro]` `tests/live_agentic_harness/compare_pipeline_modes.py`:
   - Classify each scenario once, persist lock, run full + two-step with the IDENTICAL
     decision (test-only injection).
   - Separate durable session roots per mode (no cross-contamination).
   - Per-scenario + aggregate JSON/Markdown.
   - Compare: pi_edit(post), canonical Δ replay, judge outcome, evidence/claim correctness,
     failure family, rejection/replacement use, unsupported claims, self-check/judge
     disagreement, latency, tokens, cost, session-reuse rate.
   - Cache paired results so the 50-lane ∩ 57-ledger overlap is not billed twice.

4. (Flash) `tests/test_live_agentic_two_step_comparison.py`:
   - Manifest count/hash validation.
   - Lock completeness + route equality.
   - Pair completeness.
   - Comparator behavior WITHOUT model calls.
   - Honest treatment of blocked provider/infra results.

5. (Flash) Second comparator selection from `ledger_scenario_ids()`
   (`intent/_ledger.py:293`); ledger label `current` or `ir-everywhere-57-v3` —
   `ir-everywhere-57` is an INVALID legacy label.

6. (Flash) Document commands + rollout order in `tests/live_agentic_harness/README.md`:
   respond/inspect → simple revise/reorganise → bounded research; adapt opt-in.

## Acceptance gate (deterministic wiring)

```bash
python -m pytest -q \
  tests/test_live_agentic_two_step_comparison.py \
  tests/test_live_agentic_harness_corpus_manifest.py \
  tests/test_live_agentic_runner_persistence.py
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json --validate-only
```

Live paired runs happen AFTER the final sense-check (host runs them):
```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json --tag two-step-50 \
  --capture-classifications --max-workers 4 --json
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --ledger current --tag two-step-ledger-57 --capture-classifications --max-workers 4 --json
```

B07 passes when: both paired runs complete; every pair used the same locked classification;
all Δ replays + claim-reference checks valid; no full-mode compatibility regression;
respond/inspect meet non-inferiority gate; adapt reported but not auto-enabled.

## Constraints
- Commit by scope: Flash `git commit -m "B07: harness CLI + manifest + docs (Flash)"`;
  Pro `git commit -m "B07: comparator + 100-classification bootstrap (Pro)"`. Stage by path.
- Do NOT run the live 50/57 runs yourself — leave that for the host after the final
  sense-check. `--validate-only` IS in your gate.
- Report: files changed, gate output, deviations.
