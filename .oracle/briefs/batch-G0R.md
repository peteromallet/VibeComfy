# MEGADO BATCH G0R — Truthful scorer/narrator and formal re-verdict

Repo (worktree): /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python` (symlinked to main's venv). You have file/web/terminal tools. Skip formatters, linters, and project-wide test suites; run only the focused tests below.

## Context

The G0 quick-win gate landed on main (`5daad9e6`), but its oracle checkpoint FAILED with 7 issues. Issues 5–7 were genuinely fixed (`ec732251`, `b85e173f`). Issues 1–4 were claimed fixed in `bfcde5a9` but that commit contained ZERO code changes — they remain live:

1. `tests/live_agentic_harness/assessor.py:774` — residual `"unchanged"` implementation-message substring gate (error severity) still gates scoring.
2. Missing structural expected-edit guard: `graph_unchanged=false` with zero/missing `landed_operation_count` passes.
3. `vibecomfy/comfy_nodes/agent/_frag_narrator.py` — artifact-write failure inside the outer fallback catch can replace an already-selected narrator message.
4. `_frag_narrator.py:245` region — narrator prompt contradiction: it forbids mentioning validation while requiring `validation.passed` to be described.

## Tasks

1. **Remove the residual `"unchanged"` prose gate** in `tests/live_agentic_harness/assessor.py` (around `:774`): delete the substring failure over `implementation_result.message`. Add a counterexample fixture: an edit message like "Updated the sampler; other nodes are unchanged" must NOT affect scoring.

2. **Restore the structural expected-edit guard** (around `assessor.py:613`): for an expected successful edit, `graph_unchanged=false` must be accompanied by a positive integer `change_details.landed_operation_count`. Missing, malformed, or zero counts fail closed. Grounded-refusal and explicitly non-edit routes are exempt. Add a negative control fixture.

3. **Preserve the selected narrator message if artifact persistence fails**: in `vibecomfy/comfy_nodes/agent/_frag_narrator.py`, ensure the already-selected agent message still ships even when `_write_narrative_artifacts` itself raises (the call is currently inside the outer fallback catch around `:457–477`). Add a regression that forces the write to raise and proves the selected message is preserved. Refactor only as much as the regression requires.

4. **Remove the narrator prompt contradiction** around `_frag_narrator.py:245`: the prompt must not simultaneously forbid mentioning validation and require describing `validation.passed`. Make the instruction consistent (describe validation outcome truthfully).

5. **Preserve regressions for** (these already exist from G0-T4/issues 5–6 rework; verify they still pass, fix only if broken):
   - provider-exception evidence (`test_agent_edit_*` or executor tests for `ProviderError` evidence);
   - nullable failed classification (no invented route/task/intent after classify failure);
   - no invented `respond_only`.

6. **Historical rescore**: check whether `out/agentic/` artifacts exist in this worktree (they do NOT — gitignored/absent). If absent, record "historical re-binning unavailable; source artifacts absent" in the batch report. Do NOT infer re-binning from documentation.

## Verification (run these, retain output)

```bash
.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py -x
```

Add your new fixtures to the guard-contract / score-honesty files so the above slice covers them. Also run:

```bash
.venv/bin/python -m pytest -q tests/test_comfy_nodes_agent_backend_spine.py -k 'narrative or message' tests/test_live_agentic_assessor_score_honesty.py tests/test_live_agentic_harness_guard_contract.py
```

Expected: focused G0 tests pass; the nine former matcher counterexample cases have zero matcher failures.

## Acceptance (from tasklist)

- No substring matcher, narrator phrasing, or implementation message gates scoring.
- Prose affects semantic quality only through B06's explicit rubric-driven judge (not this batch).
- Zero/missing landed-operation fixtures fail structurally.
- Narrator artifact-write failure preserves the selected response.
- The nine former matcher cases have zero matcher failures, though independent structured failures may remain.
- Focused G0 tests pass.

## Report

Return: what you changed (files + line refs), the fixture names you added, the pytest output (pass counts), and the historical-artifacts verdict (present or "unavailable"). Do NOT commit — the orchestrator commits after you finish.
