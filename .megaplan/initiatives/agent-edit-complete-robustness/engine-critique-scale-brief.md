# Prerequisite: Unify Critique Complexity Routing with the 1–10 Contract

Work in the supplied isolated Arnold worktree.

## Live failure

The critique evaluator prompt and validator correctly use a 1–10 complexity
scale. A real M0 run emitted `correctness.complexity = 7`.
`orchestration/critique_runtime.py::_apply_adaptive_critique_routing()` still
rejects values above 5, producing `critique_complexity_invariant` and preventing
all critique execution.

Built-in and historical user `tier_models.critique` tables commonly contain
only keys 1–5, while new profiles may declare the full 1–10 scale.

## Required architecture

1. Treat evaluator complexity 1–10 as the sole current critique-complexity
   contract.
2. Route full 1–10 critique tables by exact tier.
3. Preserve backward compatibility for legacy 1–5 critique tables with one
   explicit deterministic projection:
   - evaluator 1–2 → legacy tier 1
   - evaluator 3–4 → legacy tier 2
   - evaluator 5–6 → legacy tier 3
   - evaluator 7–8 → legacy tier 4
   - evaluator 9–10 → legacy tier 5
4. Detect legacy tables deliberately and unambiguously. A table containing any
   tier above 5 is a current 1–10 table.
5. Record both the evaluator complexity and the resolved routing tier in
   observability fields. Do not rewrite the evaluator artifact.
6. Preserve global critic pin fallback and missing-tier failure semantics.
7. Reject complexity outside 1–10 clearly.

## Tests

Add focused tests in a new file where possible so unrelated dirty Arnold tests
are untouched. Cover:

- real complexity 7 routes through a legacy 1–5 table to tier 4;
- complexity 10 routes through legacy table to tier 5;
- full 1–10 table routes 7 and 10 exactly;
- observability distinguishes evaluator complexity from resolved tier;
- 0, 11, missing, and invalid complexity fail;
- missing projected/exact tier without a pin still fails;
- global pin fallback still works.

Run focused critique routing/profile tests and `git diff --check`. Commit the
isolated change.

## Constraints

- Do not change the evaluator prompt back to 1–5.
- Do not silently clamp 6–10 to 5.
- Do not edit unrelated existing dirty files in the main Arnold checkout.
- Avoid a broad profile migration; compatibility belongs at the routing
  boundary, with later profiles free to adopt full 1–10 tables.
