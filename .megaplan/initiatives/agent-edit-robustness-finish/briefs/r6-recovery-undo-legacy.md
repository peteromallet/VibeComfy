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
- Reconciliation replaces the active transaction projection from one coherent
  `(session, turn, transaction)` snapshot. Absent current-turn receipts clear
  absent stages; foreign-turn/session receipts are ignored or rejected, never
  merged into the active projection.
- Rehydrate finalized transactions with the exact generation and lease from
  the durable receipt/identity fence: use the direct receipt nonce when
  present, otherwise `journal_durable.identity_fence`, otherwise a validated
  prepared-lease fallback. Do not assume terminal receipts repeat every
  identity field at their top level. Generation and lease must come from one
  source bound to the same transaction/finalized generation; never combine a
  newer generation with an older receipt's lease.
- Preserve authority across refresh, restart, and switching; show exact verifier
  diffs after rollback failure.
- Persist browser mutation-failure and rollback-attempt receipts before volatile
  panel state can disappear. Evidence must include frontend build identity,
  failing plan step/op, resolved named and numeric ports, native types, landed
  prefix, bounded structural snapshot/diff, compensation attempt, and outcome.
- Persist whether the first native write began. Recovery for a prepared lease
  with `mutation_started=false` cancels/rolls back the lease without applying an
  inverse delta or restoring the canvas; it must not be projected as a partial
  Apply merely because prepare succeeded.
- Persist `preflight_complete` separately from `mutation_started`. If either
  checkpoint is absent after prepare, recovery compares the live typed
  projection with the authoritative pre/post projections and deterministically
  cancels, restores, or resumes; it never infers mutation status from panel
  phase or assumes `canvas_was_mutated=false` merely because the browser died
  before advancing UI state.
- Bind every recovery decision to client-build attestation and a bounded lease
  deadline. When the live typed projection equals the precondition, expose an
  idempotent Resume Apply that consumes the existing generation/lease without a
  second prepare; when it equals the postcondition, resume finalize; otherwise
  restore or require explicit recovery from durable evidence. Never leave a
  prepared lease waiting forever on an in-memory browser promise.
- Enforce versioned legacy continuation/migration/non-resumable behavior.
- Declare `workflow_chat_scope_binding_v0_fingerprint_to_v1_uuid` as the
  fingerprint-qualified session-key → workflow-UUID-owned key migration. Only
  inspect the current revision's legacy key; a valid v1 key wins when both
  exist; repeated migration is idempotent; never scan/copy other fingerprints
  or workflow UUIDs; malformed or empty keys refuse without clearing state.
  Retain the v0 key read-only for at least 30 days and two released versions.
  Delete it only after the versioned migration ledger records zero successful
  v0 reads for that entire interval, then require a reviewed version bump.
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
- `migrateFingerprintScopedSessionId` is a declared migration owner until its
  versioned age-out condition is met, not an unexplained compatibility shim.

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
- Refresh after finalization restores the transcript and exact transaction
  generation/lease. Old fingerprint-qualified keys migrate without merging
  different workflow UUIDs.
- Finalization durably stores the exact browser-serialized applied graph and
  its compatibility digest. Refresh/restart reconstructs the next-submit CAS
  baseline from that applied artifact, never from the pre-materialized server
  candidate when native UI carriers differ.
- Stale responses are ignored; successful responses replace; explicit
  `CHAT_REHYDRATE_MISSING_SESSION` clears only the current workflow binding;
  every other transport, 5xx, schema, or projection failure preserves the safe
  transcript and retry state.
- Receipt tests cover stale earlier lease/newer terminal generation, mismatched
  journal fence, missing identity sources, and a prepared fallback bound to the
  same generation. Incoherent or absent identity fails closed without erasing
  the transcript.
- Consecutive-turn recovery tests prove that finalized/prepared/verified
  evidence from turn N cannot influence the state, actions, generation, or
  lease projected for turn N+1.
- Migration tests cover v1-wins, malformed/empty refusal, repeat idempotence,
  no broad key search, v0 retention, and different-UUID isolation.
- The migration ledger is the authoritative age-out source and records release
  versions, interval bounds, and v0 read counts; R8 deletion requires 30 days,
  two releases, and zero successful reads across the full interval.
- Rollback failure exposes exact bounded diff and safe next action.
- Preflight-failure recovery is idempotent, records an empty landed prefix, and
  makes zero native forward, inverse, or whole-graph writes across retry/refresh.
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
- Versioned chat-scope migration contract/evidence and finalized
  receipt-projection evidence.
- Cleanup inventory consumed by R7 and mandatory recovery evidence consumed by R8.

## Megaplan dial

Overall plan difficulty: **5/5**; profile: **partnered-5**; robustness:
**thorough**; depth: **high**; vendor: **claude** with active GLM 5.2; prep
required. Durable recovery/migration can corrupt authority while normal paths pass.

Prep direction: inventory every durable state, receipt, refresh path, Undo store,
legacy version, and ambiguous exit before encoding recovery.
