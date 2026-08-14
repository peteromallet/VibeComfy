# B08 — All-Flash profile and prompt-drift reduction (HARD — grok)

Executor: grok (per user directive: grok is the extremely hard task doer).
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).
Work in place; DO NOT commit. Run the verification commands yourself; report PASS/FAIL with outputs.

## Tasks

1. Add a clean all-Flash experimental profile and a harness profile override.
   - Touch: `vibecomfy/executor/profile_data/all_flash.toml` (new), `vibecomfy/executor/profiles.py` only if discovery requires it, `tests/live_agentic_harness/runner.py`, `tests/live_agentic_harness/adapter.py`, `tests/test_executor_profiles.py`, and harness tests.
   - All four stages resolve to DeepSeek V4 Flash through normal profile selection. Add `--profile` as an explicit run-wide override. Do not use `VIBECOMFY_FORCE_MODEL`, because it contaminates judge/other model roles.
   - Keep `default.toml` pro-for-research/implement and flash-for-classify/reply.

2. **Compress the +27% classify/reply prompt drift into auditable decision tables without semantic loss.**
   - Touch: `vibecomfy/executor/prompts.py`, focused prompt/route tests (principally `tests/test_executor_contracts.py` and existing prompt-routing tests).
   - Consolidate duplicated prose into explicit decision tables and shared constraints. Preserve all supported routes, ambiguity behavior, custom-node/adapt routing, attached-graph semantics, and strict JSON response contracts.
   - Add a byte-size regression ceiling based on the new prompt and behavioral route fixtures; do not approve a shorter prompt merely because it is shorter.

## Verification (run all; exit 0 expected)

```bash
.venv/bin/python -m pytest -q tests/test_executor_profiles.py tests/test_executor_contracts.py \
  -k 'all_flash or default_profile_keeps_pro_implement or prompt_size_ceiling or route_classification'
```

```bash
.venv/bin/python -m tests.live_agentic_harness.runner --help | grep -F -- '--profile'
```

Expected: one matching help line and exit 0.

```bash
.venv/bin/python -m pytest -q tests/test_executor_profiles.py tests/test_executor_contracts.py tests/test_comfy_nodes_agent_backend_spine.py -k 'prompt or profile or build_batch_messages'
```

## Acceptance criteria

- `all_flash` resolves Flash for classify/research/implement/reply; `default` still resolves Pro for research/implement and Flash for classify/reply.
- `--profile` reaches scenario requests without force-model environment mutation.
- The new prompt byte ceiling is at or below the pre-drift budget recorded by the test, and every existing documented route/contract fixture remains green.
- Prompt restructuring is table-driven and removes duplication; it does not delete a supported behavior to hit the size target.

## Report
"B08 VERDICT: PASS|FAIL|BLOCKED — <one line>" + per-task changes (file:line), verification outputs, residuals. DO NOT commit.
