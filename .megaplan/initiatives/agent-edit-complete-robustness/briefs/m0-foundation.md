# M0 — Ratify and Freeze the Incident Foundation

## Outcome

Turn the current dirty three-incident repair into a coherent, independently
committed baseline with reproducible gates. Preserve the layout, dynamic-exec,
workflow-tab, recovery, and transaction-contract fixes before extraction work.

## Scope

Classify the dirty worktree, exclude unrelated artifacts, repair any weakened
or skipped assertions, run exact regressions, create a machine-readable gate
manifest, and commit the baseline.

## Locked decisions

- `candidate_transaction_v1` remains the durable aggregate.
- Aggregate-free legacy candidates are read-only.
- Nested scopes remain rejected before mutation.
- Forward mutation cannot use whole-graph replacement.
- Stable IDs outrank labels and positions.
- `scorecard.png` is unrelated and must remain uncommitted.

## Open questions

- Are all dirty code/test/doc changes intended baseline work?
- Do the replacement tests cover the two skipped rollback diagnostics?
- Which real-browser claims reproduce in a clean environment?

## Constraints

Do not extract modules or redesign contracts. Preserve user work. Use exact
incident fixtures and record ambient third-party failures separately.

## Done criteria

- Focused browser, Python, and ownership suites are green.
- Exact incidents fail on their pre-fix revision and pass now.
- Skipped diagnostic coverage is restored or explicitly superseded.
- A gate manifest records commands and expected results.
- The baseline is one independent commit excluding unrelated files.

## Touchpoints

Current dirty files, incident fixtures, transaction contract, graph projection,
lifecycle/runtime tests, reorganise compiler, test documentation.

## Anti-scope

No controller, verifier, adapter, projection-family, nested-scope, or UI work.
