# R5 — Workflow-Scoped Controller and Transport API

## Outcome

Create one workflow-scoped transaction controller and one transport API, make
all asynchronous authority workflow-affine, and reduce roundtrip to bootstrap,
event wiring, and view composition.

## Input handoff

- R3 sole native adapter/evidence contract.
- R4 sole verifier/bounded-diff contract.
- M1 lifecycle/identity contracts and scheduler activation fence.

## IN

- Create `agent_edit_api.js` as sole Agent Edit transport owner.
- Make every typed transport projection on the mutation path lossless for the
  complete authority envelope. HTTP ingress, `ExecutorRequest`, executor
  implementation dispatch, Agent Edit allocation, and durable artifacts must
  carry the same workflow/session/idempotency, client revision, live-canvas,
  expected-baseline, candidate, and transaction fences. An adapter may validate
  or rename a field only through one declared mapping; it must never silently
  omit an authority field when reconstructing a downstream payload.
- Apply the same lossless rule to typed implementation evidence that determines
  whether a candidate may be authored: an actionable precedent/adaptation plan
  must retain its selected integration slice, required nodes, anchor bindings,
  rewires, and edit operations across executor dispatch. A boolean
  `actionable` summary cannot substitute for the plan it summarizes.
- Keep runtime availability distinct from provisional authorability. Workflow
  JSON or an exact Comfy Registry resolution may supply a reviewable constructor
  schema without claiming that the live ComfyUI process can instantiate the
  class. Classify every required new class as `live_available`,
  `registry_resolvable`, or `unresolved`; preserve exact pack/install evidence
  as typed non-runnable dependency metadata across authoring and Apply. Only an
  unresolved class blocks authoring. A registry-resolvable class remains
  authorable, reviewable, and Applyable as a typed serialized placeholder that
  preserves exact class identity, sockets, widgets, graph identity, and Registry
  receipt. Placeholder materialization is a first-class controller decision,
  not an adapter guess or an alias for a live node. Queue/runtime execution stays
  unavailable until the dependency is installed and observed in live
  `/object_info`; refresh must preserve the placeholder and its owning
  workflow/session/transaction.
- Create `agent_edit_controller.js` with one complete `WorkflowEditContext` per
  workflow, containing all stable identity, activation, lifecycle, candidate,
  transcript/draft, queue, Undo/recovery, and in-flight authority state.
- Model transaction evidence as one identity-qualified active transaction
  projection inside `WorkflowEditContext`. Do not expose panel-wide
  `preparedReceipt`, `verifiedReceipt`, `generation`, or `leaseNonce` fields
  that can survive independently of their owning session/turn/transaction.
- Key that context and its conversation by the Comfy workflow UUID. The tab
  nonce only namespaces browser persistence; the structural fingerprint is
  revision/precondition evidence and must never mint a context or session.
- Coordinate submit, prepare, Apply, verify, finalize, reject, rollback, Undo,
  rehydrate, activate/deactivate, cancel, and late-result rejection.
- Make submitted canvas adoption an actual workflow revision transition, not a
  disabled comparison gate. Submit carries the controller's last-observed
  baseline revision; under the workflow/session lock the server CAS-checks it,
  durably persists a differing submitted semantic graph as the next baseline,
  and only then mints candidate/precondition authority. Candidate records must
  point at that adopted revision. A stale document or active prepared lease
  cannot overwrite a newer baseline.
- Bind every browser controller context to the server's exact frontend build
  identity. Refuse Submit, Apply, and recovery continuation with an actionable
  hard-reload-required state when a restarted/switched server disagrees with
  the already-loaded document; a server relaunch must never be mistaken for a
  client relaunch.
- Runtime identity is captured at process start, not recomputed from live Git
  state. Publish the loaded backend commit, resolved module `__file__` and repo
  root, backend code digest, frontend asset digest, process-start id, and every
  duplicate import/route-registration attempt. A checkout fast-forward without
  restart must remain visibly stale rather than advertise unloaded bytecode.
- Canonicalize the ComfyUI custom-node import boundary so the absolute-path
  loader alias and `vibecomfy.comfy_nodes.*` cannot create distinct session,
  contracts, routes, controller, verifier, or lock module objects. All HTTP
  handlers and executor calls must resolve through one module/lock domain.
- Fence every continuation by all declared panel/workflow/activation/operation/
  submit/apply/session/turn/candidate/transaction/lease/generation dimensions.
- Preserve the lifecycle reducer as sole legal-transition owner.
- Prove fresh activation versus exact restoration, switching during every phase,
  late callbacks, refresh, empty workflows, and structurally identical tabs.
- Delete old coordinator/transport owners, copied aggregates, dead exports, and shims.
- Treat finalization strictly as a transaction-state transition. It must not
  append durable conversation content, clear the transcript, or render the
  composer notice "Transaction finalized / The mutation has been committed to
  the baseline. You may submit a new edit."

## OUT

Visual redesign, generalized state framework, nested canvases, exhaustive R6
recovery behavior, R7 environment/matrix, or R8 terminal audit.

## Locked decisions

- Controller coordinates, reducer transitions, API transports, adapter mutates,
  verifier judges.
- Activation atomically installs fresh or exact-restored context; deactivation
  revokes all prior async authority.
- Durable transaction state outranks panel phase; rollback targets the originating workflow.
- Prepared, verified, finalized, and rollback receipts plus generation/lease
  are owned by `(session, turn, transaction)`, never by the panel as a whole.
  Activating a later candidate atomically replaces the prior turn's active
  receipt projection; reconcile treats absent current-turn receipts as absent
  rather than inheriting values from the previous turn.
- Pre-submit graph adoption is distinct from transaction finalization: it
  advances workflow revision/CAS evidence without creating chat content,
  changing workflow/session identity, or fabricating a finalized receipt.
  Artifact reconciliation must not replay an older finalized receipt over a
  newer durable submitted/rebaseline revision.
- Rehydration is exhaustive: ignore stale responses; replace from valid
  success; on explicit `CHAT_REHYDRATE_MISSING_SESSION`, clear only the current
  workflow binding; on every other transport, 5xx, malformed-schema, or
  projection failure, preserve the last safe transcript and expose retry.
- Successful rehydration projects the authoritative durable baseline fence as
  one complete record (turn/rebaseline identity, hash kind/version, source, and
  source path). The normalized controller contract must feed that exact fence
  into the next Submit; raw snake_case and normalized camelCase cannot select
  different baseline-sync paths.
- Scope activation deactivates the departed workflow before fetching the new
  scope, preventing preserved state from becoming a cross-workflow projection.
- R5 owns workflow-affine browser binding and the safe transcript projection;
  R6 owns durable receipt and restart reconstruction.

## Open questions for the planner

- Safe bounded inactive-context retention.
- Safe bounded retention duration for inactive workflow contexts.
- Cancellation semantics after durable prepare; authority cannot be discarded.

## Constraints

- Do not weaken scheduler fencing or create controller/reducer split-brain.
- Preserve prior owners' boundaries and protected files.

## Done criteria

- Switching during every phase yields no leak, cross-tab write, or stale commit.
- Refresh restores exact workflow/transaction context; identical tabs remain distinct.
- Refresh followed by a manual canvas edit sends the exact rehydrated durable
  baseline hash as `expected_baseline_graph_hash`; it may not fall back to null
  or an inferred graph fingerprint.
- Structural Apply/finalize may change the graph fingerprint but preserves the
  workflow UUID, session, scope, and transcript; the next submission reuses the
  original session.
- Finalize A followed by a manual semantic canvas edit and Submit B atomically
  adopts that submitted graph, records it as B's exact precondition baseline,
  and permits B to prepare without a user-visible rebaseline round trip.
- Two stale/concurrent documents cannot both adopt from the same prior
  baseline: the loser receives bounded CAS evidence and performs no baseline,
  turn, candidate, or conversation mutation.
- After turn N finalizes, a reviewable turn N+1 with an empty receipt set stays
  `AWAITING_REVIEW`; it cannot inherit N's generation, lease, prepared/verified
  receipts, or interrupted-Apply notice.
- Stale, `/chat` 500, transport, malformed-schema, and projection-failure
  responses leave prior messages safe and retryable; a confirmed missing
  session clears only the current workflow.
- Finalization produces no finalized composer notice and no persistent chat
  entry.
- A server/frontend build mismatch is detected before prepare or native mutation,
  and a fresh document proves the matching build before authority is restored.
- A composed executor-route contract test sends a non-null
  `expected_baseline_graph_hash` through HTTP ingress, `ExecutorRequest`,
  executor implementation dispatch, and turn allocation. The allocated turn
  must reference the adopted submitted baseline; omitting, defaulting, or
  re-deriving the fence fails before model execution and creates no candidate.
- Deployment acceptance requires a changed process-start id and startup backend
  commit/code digest equal to the requested release; frontend `?v=` is not
  backend provenance.
- A real ComfyUI-loader test asserts alias/canonical module object identity,
  one session lock registry, and one recorded route-handler module/file.
- An exact Registry-resolvable but not-yet-installed class remains authorable
  and reviewable with its dependency receipt intact, and Apply materializes it
  as a typed non-runnable placeholder without requiring a registered LiteGraph
  constructor. Save/refresh preserves its exact type, sockets, widgets, UID,
  receipt, workflow context, and transaction identity. It is never called live
  or runnable, and queue remains blocked until `/object_info` proves the real
  class is installed. Only an unresolved class stops authoring, and GitHub-only
  search evidence cannot satisfy that Registry decision.
- Static gates prove one controller/API/reducer and no coordination/transport/
  mutation/verification/rollback decision in roundtrip.
- Roundtrip is measurably reduced; dead coordinator exports/imports are absent.
- Focused lifecycle/fence and broad suites pass; two independent acceptances.

## Touchpoints

New controller/API, reducer, panel runtime/composer, scope resolver, transport,
roundtrip, workflow context persistence, ownership tests, and switch fixtures.

## Anti-scope

No general framework, visual redesign, nested scopes, reducer duplication,
compatibility facade, fence weakening, or protected-file change.

## Output handoff and proof artifacts

- Controller/API contracts and `WorkflowEditContext` schema.
- Mutation transport field ledger and lossless projection proof covering every
  typed adapter from browser request through durable turn allocation.
- Full async-fence/tab-switch and workflow-chat-identity matrices, plus the
  roundtrip responsibility audit.
- Stable durable-context interface consumed by R6.

## Megaplan dial

Overall plan difficulty: **5/5**; profile: **partnered-5**; robustness:
**thorough**; depth: **xhigh**; vendor: **claude** with active GLM 5.2; prep
required. Async topology can leak authority despite green unit behavior.

Prep direction: trace all transport, continuations, reducer actions, activations,
cancellations, and identity fences before moving coordination.
