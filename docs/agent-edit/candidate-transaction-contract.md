# Candidate Transaction Contract

`candidate_transaction_v1` is the authority shared by persistence, preview,
Apply, Reject, rollback, finalization, chat rehydration, and restart recovery.
Panel phases and mutable `session_state.json` fields are projections, never a
second transaction state machine.

## Aggregate and state vocabulary

Every applyable V2 turn persists an immutable aggregate at
`turns/<turn>/transactions/<plan>/candidate_transaction.json`. It binds:

- session, turn, and mutation-plan identity;
- the persisted `accepted_batch` (sole durable Δ) and the content hash of
  its derived apply-time ops projection;
- submit and candidate full/structural graph hashes;
- an optional, explicitly versioned layout authority for layout-only turns;
- the immutable authority-receipt hash;
- persisted schema-witness provenance and replay verdict.

Append-only transaction events project that aggregate into exactly these
states: `candidate_ready`, `prepared`, `canvas_verified`, `finalized`,
`discarded`, `rollback_complete`, `recoverable_error`, and `superseded`.
Available actions are derived from state: Apply/Reject only in
`candidate_ready`, rollback only in `prepared`, finalize/rollback in
`canvas_verified`, and no actions in terminal states. During rehydration all
browser actions are suspended until this durable projection is known.

## Mutation and finalization

Preview and Apply consume the same persisted normalized plan. Prepare returns
that exact plan plus its generation and lease; the browser rejects any changed
plan, hash, ordering, or landed step without persisted provenance. The V2
functional-edit executor is `applyGraphDeltaInPlace` using live LiteGraph
primitives. Layout-only authority uses `applyGraphLayoutInPlace`, which mutates
only node geometry and native groups. Neither forward path may call
`graph.clear()` or whole-graph `graph.configure()`.

`layout_verification_v1` binds the candidate layout hash to the
`browser_layout_v1` projection. That projection contains root-scope node
position/size and native group id/scope/title/bounds/color, while excluding
compiler-only group membership and native serialization defaults. Groups
without stable IDs and nested-scope layouts are rejected. Unknown versions fail
closed. Historical layout transactions without this authority retain their
historical full-graph verification semantics.

Finalize receives the complete serialized post-apply graph and the applied
delta hash. The backend recomputes full and structural hashes and, for a
versioned layout turn, the bound layout projection hash. It requires the
structural result to equal the persisted candidate, requires the applied delta
hash to equal the persisted plan, and requires the versioned layout hash when
present. It records `canvas_verified`, then `finalized`, and advances the
baseline. A duplicate identical terminal request is idempotent; an opposite
terminal request is a typed conflict.

Replay uses the schema witness frozen into the authority receipt. Ambient node
schema discovery after candidate publication cannot redefine replay.
Operational authority artifacts are exact, unredacted JSON; redaction applies
only to audit/display artifacts. Immutable aggregate and receipt publication is
create-exclusive, so concurrent writers cannot replace an already-published
authority artifact.

## Recovery

On partial canvas failure, recovery first builds and applies the canonical
inverse delta and verifies the pre-apply structural hash. Whole-graph restore
is an explicit last-resort recovery mechanism and never a forward path. Server
rollback is attempted only after canvas restoration is verified when mutation
occurred. Baseline restoration is ownership-fenced so a stale rollback cannot
overwrite a newer finalized baseline.

Startup/reconcile rebuilds transaction state, prepared/idempotency indexes, and
baseline ownership from immutable aggregate/events. A malformed, out-of-order,
or identity-mismatched event log fails closed instead of projecting a plausible
partial lifecycle. Prepared leases carry an ownership nonce, are renewed while
held, and rollback must present the exact nonce. Browser diagnostics retain only
a bounded message, substage, and at most eight bounded stack lines.

Every failure after prepare must end in one of two observable conditions:

- verified compensation completed, with the server in `rollback_complete`; or
- `RECOVERY_REQUIRED`, retaining the canonical transaction, lease identity,
  original recovery graph, and a visible rollback action.

`FINALIZING` is non-terminal. A lost or ambiguous prepare/finalize response is
reconciled against durable server receipts before the browser decides whether
to retry, roll back, or project `FINALIZED`. The lease nonce is read from the
canonical prepared transaction or the nested durable receipt; a receipt
envelope must never erase it.

## Migration boundary

Historical candidates without `candidate_transaction_v1` are read-only: they
may be inspected but cannot enter Apply or Reject action endpoints. Remove this adapter
when every supported persisted session has either been migrated or aged out and
rehydration fixtures no longer contain aggregate-free candidates. The legacy
whole-graph code remains unreachable behind this adapter until that removal.

Contract coverage lives in the focused transaction tests in
`tests/test_comfy_nodes_agent_backend_spine.py`,
`tests/test_authority_receipts.py`, `tests/browser/agent_edit_transaction.test.mjs`,
`tests/browser/graph_projection.test.mjs`, the exact
`tests/fixtures/agent_edit/a66422e6_layout_regression.json` fixture, and the V2
roundtrip cases in `tests/browser/roundtrip_smoke.test.mjs`.
