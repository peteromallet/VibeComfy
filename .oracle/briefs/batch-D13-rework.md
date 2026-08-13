# MEGADO D13 REWORK (oracle finding 5) — desired-edit refusal judge bypass

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. D13 is in the tree at `b39f0c91` — fix on top, do not revert.

## The issue (D13 oracle FAIL, finding 5)

Three retained `desired` edits can pass via an unjudged, ungrounded refusal:

- `tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json:8-18`
- `tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json:8-17`
- `tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json:8-18`

Mechanism: `tests/live_agentic_harness/assessor.py:641-646` accepts the outcome label (allowlisted safe refusal, e.g. `clarify`/`requires_custom_nodes`), after which `:812-817` SKIPS the `judge_edit_intent()` call for the scenario. No evidence establishes the refusal is grounded. The regression at `tests/test_live_agentic_harness_guard_contract.py:288-332` explicitly permits this path with only prose and failed edit gates.

## What to change

1. **`assessor.py:641-646` + `:812-817`**: a `desired` scenario must NOT bypass all judging merely through an allowlisted refusal label. Either:
   - (a) require an ACTIVE grounded-refusal judge for those scenarios (judge must run and confirm the refusal is grounded: supported blocker, no representable edit, specific next action, no fabricated inability), failing closed when the judge is unavailable; or
   - (b) remove the refusal bypass for `desired` scenarios entirely.
   Pick the option that keeps genuine grounded refusals passable but makes fabricated/unsupported refusals fail. `graph_unchanged=false` + refusal label + no grounded judge verdict must fail closed.
2. **`tests/test_live_agentic_harness_guard_contract.py:288-332`**: add coverage proving an unsupported or fabricated `clarify`/`requires_custom_nodes` refusal cannot pass (for a desired edit).
3. **`tests/test_live_agentic_harness_corpus_manifest.py:76-79`**: extend the desired-edit corpus assertion to detect judge-bypassing refusal configurations (any desired scenario whose configuration would let a refusal skip the judge must fail validation).

## Verification (run, retain output)

```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_harness_runner_persistence.py
```

Expected exit 0. The three scenarios' configurations must still be manifest-valid (they stay desired edits; the judge path now gates refusals).

## Report
Return: exact changes (files + line refs), which option you picked, fixture names, pytest output. Do NOT commit.
