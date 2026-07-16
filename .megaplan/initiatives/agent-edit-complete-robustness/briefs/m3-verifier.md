# M3 — Single Apply and Rollback Verifier

## Outcome

Create `graph_apply_verifier.js` as the only owner of transaction graph
comparison, postcondition evidence, rollback verification, and mismatch
diagnostics.

## Scope

Centralize precondition, landed-operation, postcondition, finalize, rollback,
and diagnostic-diff decisions. Remove inline equivalents and add comprehensive
fault injection.

## Locked decisions

- Adapter observes/mutates; verifier decides equivalence.
- Controller coordinates but cannot compare graphs.
- Every post-prepare error retains reconciliation or rollback authority.
- Projection contracts drive verification, never incidental graph shape.

## Open questions

- Required diagnostic granularity for opaque extension data.
- Whether repairable normalization deserves a distinct verifier outcome.

## Constraints

Do not redesign the panel or move controller lifecycle work beyond the seams
needed to call the verifier.

## Done criteria

- Every Apply/finalize/rollback comparison calls the public verifier API.
- All exact incident fixtures pass through that API.
- Fault injection covers mismatch, serialization exception, partial Apply,
  inverse failure, and fallback restore.
- No copied projection comparison remains elsewhere.

## Touchpoints

New verifier, roundtrip, transaction lifecycle commits, projection registry,
rollback helpers, diagnostics fixtures.

## Anti-scope

No controller rewrite, visual redesign, nested scopes, or transport extraction.
