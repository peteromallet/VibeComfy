# North Star: One Transaction, One Owner at Every Boundary

Every Agent Edit operation is a versioned canonical delta coordinated by one
workflow-scoped controller, executed through one native LiteGraph adapter,
judged by one operation-specific verifier, and completed by durable finalize or
verified rollback.

The finished architecture has exactly one owner for each consequential
decision:

- the projection registry owns structural, layout, and workflow projection
  meaning;
- the native adapter alone observes and mutates LiteGraph;
- the verifier alone compares transaction preconditions, landed operations,
  postconditions, and rollback outcomes;
- the workflow controller alone coordinates lifecycle and asynchronous commit
  authority;
- the API module alone owns Agent Edit transport;
- the lifecycle reducer alone owns legal state transitions; and
- stable identifiers, never titles, positions, or incidental order, identify
  workflows, scopes, nodes, groups, sessions, turns, candidates, and
  transactions.

The Comfy workflow UUID owns workflow context and conversation identity. A tab
nonce may namespace browser persistence but never owns the conversation. A
graph fingerprint is revision and precondition evidence, never identity;
structural edits under one workflow UUID must not create a new session, scope,
or transcript.

There is no production `candidateGraph` or whole-graph path to native forward
mutation. Whole-graph loading may exist only as an explicitly authorized,
receipt-bound compensation strategy. Compatibility code survives only when it
implements a declared, versioned migration contract; otherwise it is deleted.

Every workflow tab has an isolated complete context. An async continuation can
commit only while its workflow, activation, operation, submit/apply epoch,
session, turn, candidate, transaction, lease, generation, and panel authority
remain current. Switching tabs or refreshing never transfers authority.
Transaction receipts, generation, and lease live inside one identity-qualified
active transaction projection; they are not free-floating panel fields. A new
turn replaces that projection atomically, so evidence from turn N cannot be
combined with or projected onto turn N+1.
The loaded frontend build is part of that authority: server restart or checkout
switch cannot let a stale browser module graph mutate against a different build.

Every durable post-prepare state has an idempotent recovery action. A generic
terminal error without retry, reconciliation, verified rollback, or exact
retained recovery evidence is forbidden.
Native mutation and compensation attempts leave durable step-level receipts, so
`RECOVERY_REQUIRED` is reconstructible even after the browser document is gone.
Semantic workflow fields resolve through native widget identity and adapter
carrier evidence. Serialized input-descriptor order is never treated as widget
serialization order: ComfyUI may serialize auxiliary widgets that have no input
descriptor. The typed delta owns the intended value; the verifier judges the
adapter's resolved carrier and landed projection rather than reconstructing a
physical widget index from an incomplete graph encoding.
Preflight is an explicit no-mutation boundary. A failure before the first native
write rolls back only the prepared lease and must not run inverse mutation,
whole-graph restoration, or claim that the canvas was mutated.
Rehydration has one exhaustive classification: a stale response is ignored; a
valid success replaces the safe projection; an explicit
`CHAT_REHYDRATE_MISSING_SESSION` clears only the current workflow's binding;
every other transport, server, schema, or projection failure preserves the last
safe transcript and exposes retry. Activating another workflow first
deactivates the departed context, so retention cannot leak messages across
workflows. Finalization changes transaction state only: it neither creates
persistent conversation content nor clears the thread.

Compatibility/session CAS digests are versioned boundary values, not typed
transaction projection witnesses. A finalized rehydrate recovers the exact
generation and lease from one coherent durable identity source bound to the
same transaction and generation, even when a terminal receipt does not repeat
those fields at its top level. Identity fragments from different generations
must never be combined.

The exact `a66422e…`, `eb45e…`, detached `Displays / Labels`, duplicate-title,
workflow-tab isolation, fingerprint-scoped chat, getter-only native-widget, and
KSampler auxiliary `control_after_generate`/`denoise` incidents remain permanent
gates. Real ComfyUI must
prove forward success, native serialization, verification, finalize, refresh,
persistence, injected failure, rollback, recovery, and switching for every
supported transaction family.

“Completely cleaned up” means the old owners, dead exports, copied helpers,
fallback mutation paths, title-identity heuristics, stale ledger exceptions,
and obsolete compatibility facades are removed; `vibecomfy_roundtrip.js` is
only bootstrap/event/view composition; all S3/S4 rows are closed; static CI
guards make regression architecturally illegal; and the final proof map and
completion manifest directly prove every requirement.

Root workflow scope is the boundary of this epic. Nested scopes and subgraphs
must fail closed before mutation and are deliberately deferred.
