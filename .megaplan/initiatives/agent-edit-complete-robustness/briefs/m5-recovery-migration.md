# M5 — Exhaustive Recovery, Undo, and Legacy Closure

## Outcome

Make every durable nonterminal transaction state deterministic, idempotent,
identity-fenced, refresh-safe, and consistent with the ratified Undo and legacy
version policies.

## Scope

Encode the recovery state table, reconcile ambiguous receipts, preserve
authority across refresh/switch, provide exact rollback differences, implement
Undo semantics, and close legacy compatibility paths.

## Locked decisions

- Generic terminal `ERROR` is forbidden after prepare.
- Recovery ends finalized, verified rolled back, or in explicit actionable
  `RECOVERY_REQUIRED`.
- Legacy transactions are never silently reinterpreted.
- Recovery cannot overwrite a newer workflow baseline.

## Open questions

- Recovery graph/journal retention duration.
- Operator escape hatch if inverse and snapshot restore both fail.
- Legacy support age-out window.

## Constraints

No nested-scope recovery or automatic repair of arbitrary manual graph surgery.
Keep precise diagnostics and retained authority when automation cannot finish.

## Done criteria

- Every durable-state row has success, failure, refresh, and retry tests.
- Browser restart cannot strand a transaction.
- Undo matches the M1 contract.
- Recovery actions are identity-fenced and idempotent.

## Touchpoints

Controller, verifier, transaction API/backend, session journal, lifecycle
presentation, crash/restart fault injection.

## Anti-scope

No nested scopes or opaque manual graph auto-repair.
