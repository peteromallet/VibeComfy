# M2 — Native Graph Adapter and Canonical Mutation Path

## Outcome

Create `intent_graph_adapter.js` as the sole Agent Edit boundary to native
ComfyUI/LiteGraph representation and make canonical operations the only
forward mutation language.

## Scope

Move graph capture, native normalization, identity preservation, mutation,
restoration planning, serialization, and capability checks behind the adapter.
Inventory native normalization behavior and route all mutation consumers
through canonical operations.

## Locked decisions

- No forward `clear/configure` or `loadGraphData()` replacement.
- Roundtrip cannot inspect or mutate LiteGraph directly.
- Extension-owned opaque fields are preserved but excluded unless declared.
- Adapter methods return typed results and diagnostics, not booleans.
- Nested scopes remain rejected.

## Open questions

- Which node families require normalization plugins?
- Are inverse deltas sufficient for every supported operation?
- What is the safe limit of snapshot restoration as compensation?

## Constraints

Keep lifecycle coordination stable except for dependency injection. Add
ownership guards as each responsibility moves.

## Done criteria

- All Agent Edit graph access flows through the adapter.
- Every supported canonical operation survives real LiteGraph serialization.
- Dynamic-node normalization cannot create false failure.
- Partial mutation yields a verifiable inverse or restoration plan.

## Touchpoints

New adapter, `comfy_adapter.js`, `canonical_delta.js`, preview/replay,
roundtrip graph access, native/browser tests, normalization ledger.

## Anti-scope

No controller extraction, nested scopes, or arbitrary node-pack compatibility
promise.
