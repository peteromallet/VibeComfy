# Prerequisite: Preserve Per-Tier Reasoning Effort in Megaplan

Work in the supplied isolated Arnold worktree.

## Goal

Fix Megaplan execution-tier routing so a tier-selected `AgentMode` preserves
its reasoning effort all the way to the worker command. Support the installed
Codex model effort values needed by this initiative.

## Proven defect

- `execute/batch.py::_resolve_tier_spec()` currently returns only agent, mode,
  and model, dropping `AgentMode.effort`.
- `_run_and_merge_batch()` therefore receives the phase fallback effort rather
  than the selected tier effort.
- `workers/_impl.py::_VALID_CODEX_EFFORTS` only permits
  `minimal|low|medium|high` and normalizes newer supported values down.

## Required behavior

1. Preserve the complete tier-selected model and effort through both execution
   call paths in `execute/batch.py`.
2. A tier entry such as `codex:gpt-5.6-terra:xhigh` must invoke Codex with
   `model_reasoning_effort=xhigh`.
3. Accept at least `xhigh` and `max` for Codex. Do not add `ultra` unless the
   parser and worker contract are deliberately extended and tested.
4. Preserve phase fallback effort when a selected tier spec omits effort.
5. Preserve all existing provider/model/mode behavior.

## Tests

Add focused regression tests in a new test file if that avoids touching
existing dirty test files. Cover:

- selected tier effort overrides fallback effort;
- absent tier effort retains fallback effort;
- xhigh and max reach Codex command construction unchanged;
- invalid effort still fails clearly.

Run the smallest focused suites plus any nearby tier/worker tests needed to
prove no regression.

## Constraints

- Do not modify unrelated dirty work from the main Arnold checkout.
- Do not redesign profile parsing or execution batching.
- Return a concise summary, exact tests, and commit the isolated-worktree
  change.
