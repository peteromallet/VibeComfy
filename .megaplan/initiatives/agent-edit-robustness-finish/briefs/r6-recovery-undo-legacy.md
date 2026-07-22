# R6 — Exhaustive Recovery, Undo, and Legacy Closure

## Outcome

Give every durable nonterminal state a deterministic, idempotent,
identity-fenced recovery action consistent with ratified Undo and legacy
contracts, including refresh and workflow switching.

## Input handoff

- R5 controller/context contract and async-fence matrix.
- R4 verifier/diff contract and R3 inverse/compensation evidence.
- M1 Undo and legacy migration decisions.

## IN

- Encode all prepared, mutated, verified, finalizing, rollback, refresh, and
  switched transaction states as executable recovery obligations.
- End each action finalized, verified rolled back, safely cancelled, or explicit
  actionable `RECOVERY_REQUIRED` retaining exact authority/evidence.
- Implement Undo as a new authorized inverse/restoration transaction.
- Reconcile ambiguous prepare/finalize responses from durable receipts.
- Preserve authority across refresh, restart, and switching; show exact verifier
  diffs after rollback failure.
- Persist browser mutation-failure and rollback-attempt receipts before volatile
  panel state can disappear. Evidence must include frontend build identity,
  failing plan step/op, resolved named and numeric ports, native types, landed
  prefix, bounded structural snapshot/diff, compensation attempt, and outcome.
- Enforce versioned legacy continuation/migration/non-resumable behavior.
- Inject crash/restart, retry, duplicate callback, stale identity, partial
  rollback, and compensation failure.
- Delete obsolete error terminals, dead helpers/shims, and duplicate migrations.

## OUT

Nested recovery, arbitrary manual-graph repair, R7 environment/matrix and CI,
R8 terminal audit, or broad retention-product tuning.

## Locked decisions

- Generic terminal `ERROR` is forbidden after prepare.
- Recovery is idempotent, receipt-bound, and cannot overwrite a newer baseline.
- Legacy authority is never silently reinterpreted.
- Failed automation preserves exact evidence and authority.

## Open questions for the planner

- Safe bounded journal/inactive-context retention default.
- Operator action when inverse and compensation both fail.
- Legacy age-out policy consistent with M1.

## Constraints

- Every durable state appears in a machine-readable coverage table.
- Actions remain safe under repetition, stale callbacks, and switching.
- Preserve earlier boundaries and protected files.

## Done criteria

- Every state/action row has applicable success, failure, retry, refresh/restart,
  switch, stale-identity, and idempotence evidence.
- Restart cannot strand/transfer authority; Undo and legacy match M1 contracts.
- Rollback failure exposes exact bounded diff and safe next action.
- Every `RECOVERY_REQUIRED` state is reconstructible from durable artifacts;
  the backend may not retain only `prepared` when native mutation or local
  compensation has already been attempted.
- Static audit finds no generic post-prepare terminal, duplicate migration owner,
  dead recovery export, or silent reinterpretation.
- Focused and broad suites pass; two independent acceptances.

## Touchpoints

Controller, verifier, transaction backend/API, session journal, lifecycle UI,
legacy converters, recovery tests, and crash/restart harness.

## Anti-scope

No nested recovery, opaque auto-repair, silent reinterpretation, swallowed
evidence, unbounded retention project, facade, or protected-file change.

## Output handoff and proof artifacts

- Machine-readable recovery-state/action matrix.
- Undo/migration contracts and crash/restart evidence pack.
- Cleanup inventory consumed by R7 and mandatory recovery evidence consumed by R8.

## Megaplan dial

Overall plan difficulty: **5/5**; profile: **partnered-5**; robustness:
**thorough**; depth: **high**; vendor: **claude** with active GLM 5.2; prep
required. Durable recovery/migration can corrupt authority while normal paths pass.

Prep direction: inventory every durable state, receipt, refresh path, Undo store,
legacy version, and ambiguous exit before encoding recovery.
