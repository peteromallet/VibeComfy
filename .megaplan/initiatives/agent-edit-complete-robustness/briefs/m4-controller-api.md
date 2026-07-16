# M4 — Workflow-Scoped Controller and Transport Boundary

## Outcome

Create one controller aggregate per workflow, one Agent Edit transport owner,
and reduce roundtrip to bootstrap, event wiring, and view composition.

## Scope

Add `agent_edit_api.js`, `agent_edit_controller.js`, complete
`WorkflowEditContext`, atomic activation/deactivation, and universal async
authority fences across all transaction phases.

## Locked decisions

- Scope activation installs a fresh or exact restored context atomically.
- Deactivation revokes prior async authority.
- Durable transaction state outranks UI phase.
- Transport normalization belongs at the API boundary.
- The lifecycle reducer remains transition authority; the controller
  orchestrates and fulfills obligations.

## Open questions

- Inactive context retention/eviction policy.
- Draft/transcript persistence across browser restart.
- Cancellation behavior after durable prepare.

## Constraints

No visual redesign, nested-canvas controller, or generalized state framework.
Preserve adapter and verifier ownership boundaries.

## Done criteria

- Workflow switching during every phase cannot leak or accept late results.
- Refresh restores the exact workflow/transaction context.
- Roundtrip owns no transport, graph, hashing, verification, rollback, or
  transaction-coordination decision.
- Empty and structurally identical workflows remain isolated.

## Touchpoints

New controller/API, lifecycle reducer, panel runtime/composer, scope resolver,
roundtrip, websocket/event feed, workflow-switch tests.

## Anti-scope

No visual redesign, nested scopes, or speculative framework extraction.
