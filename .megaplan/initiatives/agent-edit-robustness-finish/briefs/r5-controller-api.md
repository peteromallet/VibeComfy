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
- Create `agent_edit_controller.js` with one complete `WorkflowEditContext` per
  workflow, containing all stable identity, activation, lifecycle, candidate,
  transcript/draft, queue, Undo/recovery, and in-flight authority state.
- Coordinate submit, prepare, Apply, verify, finalize, reject, rollback, Undo,
  rehydrate, activate/deactivate, cancel, and late-result rejection.
- Fence every continuation by all declared panel/workflow/activation/operation/
  submit/apply/session/turn/candidate/transaction/lease/generation dimensions.
- Preserve the lifecycle reducer as sole legal-transition owner.
- Prove fresh activation versus exact restoration, switching during every phase,
  late callbacks, refresh, empty workflows, and structurally identical tabs.
- Delete old coordinator/transport owners, copied aggregates, dead exports, and shims.

## OUT

Visual redesign, generalized state framework, nested canvases, exhaustive R6
recovery behavior, R7 environment/matrix, or R8 terminal audit.

## Locked decisions

- Controller coordinates, reducer transitions, API transports, adapter mutates,
  verifier judges.
- Activation atomically installs fresh or exact-restored context; deactivation
  revokes all prior async authority.
- Durable transaction state outranks panel phase; rollback targets the originating workflow.

## Open questions for the planner

- Safe bounded inactive-context retention.
- Whether draft/transcript persistence beyond the browser belongs here or R6.
- Cancellation semantics after durable prepare; authority cannot be discarded.

## Constraints

- Do not weaken scheduler fencing or create controller/reducer split-brain.
- Preserve prior owners' boundaries and protected files.

## Done criteria

- Switching during every phase yields no leak, cross-tab write, or stale commit.
- Refresh restores exact workflow/transaction context; identical tabs remain distinct.
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
- Full async-fence/tab-switch matrix and roundtrip responsibility audit.
- Stable durable-context interface consumed by R6.

## Megaplan dial

Overall plan difficulty: **5/5**; profile: **partnered-5**; robustness:
**thorough**; depth: **xhigh**; vendor: **claude** with active GLM 5.2; prep
required. Async topology can leak authority despite green unit behavior.

Prep direction: trace all transport, continuations, reducer actions, activations,
cancellations, and identity fences before moving coordination.
