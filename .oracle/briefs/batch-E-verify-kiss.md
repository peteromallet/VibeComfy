# CRITIQUE — Checkpoint E completeness + KISS/YAGNI (read-only)

You are Spark reviewing Batch E at HEAD `d2975269` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Do not run pytest (other agents own tests).

Read:
```
git diff 86e4a6ba..d2975269 -- . ':!.oracle/**'
```
Also read `.oracle/plan.md` Batch E tasks 1–7 and Checkpoint E (around lines 227–265).
Optimize for elegance (KISS/YAGNI). Flag overengineering. Do not rubber-stamp.

## Check each plan task (PASS/FAIL + file:line)

1. Shared `format_schema_gap(manifest_path, missing_classes) -> str` ending with exact command `vibecomfy schemas ensure --manifest <path>`.
2. `validate-coverage --manifest`: Batch A missing-live-captures helper; exit 1 on gaps; template positional exit 0; JSON `missing_classes` + `ensure_command`.
3. Doctor prints ensure command (template form + or `--manifest <comparison.json>`); JSON `ensure_command`; does NOT clone/extract.
4. SKILL.md one mechanical section (see plan bullets). No `docs/plans/**`.
5. E2E fixture: comparison-manifest + synthetic gated class + local fixture pack (not stub-as-live). Empty tmp cache → preflight fails with ensure command → ensure --manifest (registry mocked, extract real) → preflight green; recorded tier `on_demand_static` or `on_demand_import`. Optional host registry probe may be skipped.
6. Evidence matrix in `.oracle/evidence/` or test docstrings, not `docs/plans/**`.
7. Host pytest: you do not re-run; judge from code whether tests exist to satisfy “focused pytest”. Note if there is no evidence the 8512-test full suite actually completed (executor receipt said it timed out at 300s) — classify as blocking vs acceptable residual.

Checkpoint E:
- All four agent-goal items present in code
- Fixture missing → ensure → preflight green using only on-demand captures
- SKILL.md section exists
- Commit message matches `schemas-ensure(E): doctor gap reporting + SKILL docs + e2e fixture`

## KISS / YAGNI

- Is `format_template_gap` needed or a second helper that should have been one function with a path kind?
- Did validate-coverage grow a parallel gap scanner?
- Did doctor grow capture logic, new flags, or a mini-ensure?
- SKILL.md: one section or a second documentation system?
- E2E test: over-mocked? Ceremonial assertions that cannot fail? Does it actually extract a real `INPUT_TYPES` node from a git fixture, or assemble a schema dict in-process and call that “on-demand”?
- Duplicate command-string construction vs compose-don't-duplicate.
- Any new schema parser / persist path besides glue around existing ladder + `build_cache` + ledger?

North Star anti-patterns to hunt in the delta (blocking if present):
- stub/hand-authored schema presented as live
- permanent pack install / venv as side effect of doctor or e2e
- unactionable gap messages
- parallel schema system
- silent tier upgrade (`on_demand_runtime` alias, static labeled runtime)

## Return (max 400 words)

- Task 1–7 PASS/FAIL table
- Checkpoint E PASS/FAIL
- Overengineering findings (or “glue is thin enough”)
- Full-suite residual: blocking or not
- Overall: PASS or issue list
