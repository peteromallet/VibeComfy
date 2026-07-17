# M2 — Native Graph Adapter and Canonical Mutation Path

## Outcome

Create
`vibecomfy/comfy_nodes/web/intent_graph_adapter.js` as the sole Agent Edit
boundary to live ComfyUI/LiteGraph state.

After M2, every Agent Edit capture, native normalization, stable-identity
translation, canonical delta mutation, inverse/restoration execution, and
native serialization must cross this adapter. No forward Agent Edit path may
use whole-graph `clear/configure` or `loadGraphData()` replacement.

M2 changes the native boundary, not lifecycle ownership. Transaction
coordination remains in its current owner until M4, and verification decisions
remain in their current owner until M3.

## M1 prerequisites

Do not begin the extraction until M1 is committed and its focused and M0
regression gates pass.

The adapter must consume, without reinterpreting:

- `projection_registry_v1` from
  `vibecomfy/comfy_nodes/web/projection_registry_v1.js`;
- `delta_v1` on wire version `2.0.0` from
  `vibecomfy/comfy_nodes/web/canonical_delta.js`;
- `root_scope_v1` from
  `vibecomfy/comfy_nodes/web/root_scope_v1.js`;
- stable identity rules from
  `vibecomfy/comfy_nodes/web/identity_contract_v1.js`;
- `candidate_transaction_v2` and `prepared_authority_v1` from
  `vibecomfy/comfy_nodes/web/prepared_authority_v1.js`;
- the forbidden-forward `workflow_v1` policy;
- `journal_durable_v1` restoration authority without implementing the M5
  product workflow.

Unknown contract versions, missing stable identity, unsupported fields,
non-root scope, forbidden `workflow_v1`, and unavailable native capabilities
must fail before mutation.

## Locked decisions

- `intent_graph_adapter.js` is the only Agent Edit module permitted to read or
  write live LiteGraph graph state.
- `projection_registry_v1.js` remains the only owner of projection semantics.
  The adapter invokes it; it must not copy its field, identity, ordering, or
  hashing rules.
- Canonical `delta_v1` operations are the only forward mutation language.
- Forward `app.loadGraphData()`, `graph.clear() + graph.configure()`, and raw
  whole-workflow replacement are forbidden.
- Rollback, compensation, Undo execution, preview materialization, and replay
  restoration use canonical inverse delta or an explicitly versioned
  restoration strategy through the same adapter.
- Snapshot restoration is compensation only. It must be explicitly authorized,
  root-scoped, identity-fenced, projection-bound, and verified by the later
  M3 verifier.
- Native node/link/group IDs are adapter-local aliases. Stable UIDs and group
  IDs cross the boundary.
- Extension-owned opaque fields are preserved during native round trips but
  excluded from projections unless M1 declares them.
- Adapter methods return typed result or diagnostic envelopes; callers do not
  infer success from truthy values or thrown native objects.
- Nested scopes and cross-scope links remain unsupported and fail before
  mutation.

## Ordered execution plan

### Current substate — 2026-07-17

Slices 1–2 are implemented and independently accepted. The observation-only
Family-A preparation for coupled S3+S4 is also accepted: 65/65 focused
adapter/ownership tests, 532/532 browser contracts, and 1,413 browser-smoke
passes with 2 intentional skips are green; the exact `eb45e0ef…` incident
fixture rebuilds byte-identically. The sole machine ledger still has 78 unique
stable rows and 120 unique file/region/kind mappings, with seven persistent-
write/harness rows truthfully reclassified as S4 migration debt.

This remains a bounded preparation acceptance only. S3 is not closed, 0/27
coupled identity/index/link ownership rows have transferred, and Slices 3–6
remain pending. Before the atomic S3+S4 cut, the versioned
`layout_operation_v1` and `mutation_materialization_v1` contracts must land;
then consumers, old implementations, and ledger ownership move together. The
M2 done criteria are not yet satisfied.

### Slice 1 — Inventory and freeze every native graph access

Produce a checked-in inventory before moving behavior.

Search all files under `vibecomfy/comfy_nodes/web/` for:

- `app.graph`, `app.canvas.graph`, `_nodes`, `links`, and `serialize()`;
- `loadGraphData`, `clear`, `configure`, `add`, `remove`, `removeLink`, and
  `node.connect`;
- direct group construction/configuration/removal;
- native node factories and dynamic socket/widget rebuilds;
- canvas repaint calls that are coupled to mutation;
- whole-graph snapshot capture and restore;
- local implementations of stable-ID lookup or native normalization.

At minimum, classify current access in:

- `vibecomfy/comfy_nodes/web/comfy_adapter.js`;
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`;
- `vibecomfy/comfy_nodes/web/preview_picker.js`;
- `vibecomfy/comfy_nodes/web/agentic_replay.js`;
- `vibecomfy/comfy_nodes/web/active_canvas_scope_guard.js`;
- `vibecomfy/comfy_nodes/web/panel_overlay.js`;
- `vibecomfy/comfy_nodes/web/scope_resolver.js`.

Write the inventory and field-semantics ledger to
`vibecomfy/comfy_nodes/web/native_normalization_ledger.md`. Each entry must
name the current owner, consumer, access kind, intended adapter method,
projection effect, native normalization behavior, support status, fixture, and
migration slice.

The inventory distinguishes graph access from harmless canvas/render access.
Overlay drawing may keep canvas APIs, but it must not read graph structure or
mutate graph state.

Acceptance:

- every native graph access has exactly one ledger row;
- a static inventory test fails if an unclassified access is added;
- no production behavior changes in this slice;
- M0 and M1 gates remain green.

### Slice 2 — Introduce the single adapter and typed capability surface

Create `vibecomfy/comfy_nodes/web/intent_graph_adapter.js`.

Start with a dependency-injected adapter factory so browser tests can supply
the current LiteGraph harness without global patching. Its public surface
should cover:

- root live-graph acquisition;
- capability detection;
- immutable serialized capture;
- native serialization after mutation;
- repaint/invalidation associated with adapter-owned mutations;
- projection calls delegated to `projection_registry_v1`;
- typed diagnostics for unavailable graph, unsupported scope, unsupported
  operation, missing identity, unsupported native representation, and native
  serialization failure.

Consolidate or wrap the relevant graph-facing parts of
`vibecomfy/comfy_nodes/web/comfy_adapter.js`; do not leave two public native
graph adapters. Non-graph responsibilities such as queue guards, extension
registration, and foreground overlay hooks may remain in `comfy_adapter.js`
temporarily, but the ownership split must be explicit and tested.

Callers receive adapter results shaped around declared contracts, for example:

```text
{ ok, operation, scope, before, after, landed, restoration, diagnostics }
```

The exact schema may differ, but it must carry the operation identity,
`root_scope_v1`, projection references, stable landed identities, and bounded
diagnostics.

Acceptance:

- missing or ambiguous active graph fails closed;
- unknown scope or contract version fails before capture/mutation;
- adapter capture is immutable and does not leak live LiteGraph objects;
- adapter projections byte-match the M1 browser/Python golden corpus;
- importing the adapter does not require a live browser global.

### Slice 3 — Move stable identity and native normalization behind the adapter

Move all native-to-stable translation into `intent_graph_adapter.js`, while
delegating identity validity to `identity_contract_v1.js` and projection
meaning to `projection_registry_v1.js`.

The adapter must own:

- locating live nodes by stable `vibecomfy_uid`;
- translating native node IDs only as an internal, candidate-bound alias;
- locating links by stable named endpoint identity;
- preserving stable group IDs through native configure/serialize cycles;
- preventing titles, positions, array indexes, class types, and native IDs
  from becoming fallback identity;
- normalizing dynamic sockets/widgets and native-generated defaults before
  projection;
- preserving extension-owned opaque values without declaring them semantic.

Populate `native_normalization_ledger.md` with observed behavior for:

- `vibecomfy.exec` dynamic `io`;
- converted widgets;
- dynamic inputs and outputs;
- reroutes;
- groups and duplicate group titles;
- extension-added properties;
- Node 2.0 or unsupported representations encountered by fixtures.

Unknown node-family normalization must either be projection-neutral by the M1
field registry or return an explicit unsupported diagnostic. It must never
silently invent a normalization rule in a caller.

Acceptance:

- the `eb45e…` dynamic-exec representation normalizes without a false
  structural difference;
- the `a66422e…` layout fixture preserves stable group identity across native
  serialization;
- duplicate group titles remain distinct;
- missing stable node/group identity fails before mutation;
- no adapter consumer contains a native-ID, title, position, or index fallback.

### Slice 4 — Route forward delta, inverse delta, and restoration through it

Move the live mutation and restoration machinery currently concentrated in
`comfy_adapter.js` and `vibecomfy_roundtrip.js` behind the adapter.

The adapter must preflight and apply every supported `delta_v1` operation:

- `set_node_field`;
- `set_mode`;
- `add_node`;
- `upsert_link`;
- `remove_node`;
- `remove_link`.

It must also:

- apply layout geometry through the declared layout operation family while
  preserving the structural no-op witness;
- return landed-operation provenance for every source op;
- construct or validate inverse delta/restoration authority before mutation;
- apply inverse delta in reverse causal order;
- execute an authorized snapshot restoration only as compensation;
- expose partial-mutation evidence sufficient for M3 verification;
- keep forward mutation free of whole-graph replacement.

Route current consumers through dependency injection:

- Apply and compensation paths in
  `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`;
- preview mutation/restoration in
  `vibecomfy/comfy_nodes/web/preview_picker.js`;
- replay capture/restoration in
  `vibecomfy/comfy_nodes/web/agentic_replay.js`;
- active graph serialization in
  `vibecomfy/comfy_nodes/web/active_canvas_scope_guard.js`;
- any graph-derived scope capture in
  `vibecomfy/comfy_nodes/web/scope_resolver.js`.

M2 may leave orchestration calls in roundtrip, but roundtrip must only call
adapter APIs. It must no longer inspect `_nodes`, serialize the graph, patch
`loadGraphData`/`graph.configure`, allocate links, mutate nodes/groups, or
restore a graph itself.

Acceptance:

- all six operations preflight fully before the first native write;
- malformed, unsupported, nested-scope, missing-identity, and capability
  failures produce zero native mutations;
- partial native failure returns the exact landed prefix plus usable
  inverse/restoration evidence;
- inverse delta restores the same declared projection family as forward;
- no forward Agent Edit call reaches `loadGraphData`, `graph.clear`, or
  whole-graph `graph.configure`.

### Slice 5 — Prove native operation and incident behavior through LiteGraph

Add focused adapter tests, then migrate existing large roundtrip assertions to
the public adapter boundary where practical.

Primary files:

- new `tests/browser/intent_graph_adapter.test.mjs`;
- update `tests/browser/harness.mjs` only to expose faithful LiteGraph behavior;
- update `tests/browser/dynamic_io_smoke.test.mjs`;
- update `tests/browser/graph_projection.test.mjs`;
- update focused cases in `tests/browser/roundtrip_smoke.test.mjs`;
- reuse `tests/fixtures/agent_edit/a66422e6_layout_regression.json`;
- reuse `tests/fixtures/agent_edit/m1_projection_golden_v1.json`;
- add an exact `eb45e…` dynamic-exec fixture under
  `tests/fixtures/agent_edit/` if one is not already durable.

For each supported operation, the test must:

1. capture a real LiteGraph-style serialization;
2. validate M1 prepared authority;
3. preflight without mutation;
4. apply through the adapter;
5. serialize through native graph behavior;
6. project with the declared M1 projection;
7. prove landed provenance;
8. apply inverse/restoration through the adapter;
9. serialize again and prove the rollback projection.

Required cases include:

- all six `delta_v1` operations individually and in a multi-op dependency
  chain;
- layout-only movement with structural no-op;
- dynamic `vibecomfy.exec` socket/widget reconstruction;
- duplicate-title stable groups and the `a66422e…` incident;
- converted widget/default normalization;
- reroute/link allocation behavior;
- mutation failure after each possible landed prefix;
- serialization failure after mutation;
- missing custom-node factory;
- missing stable identity;
- nested scope and cross-scope link rejection;
- forbidden `workflow_v1`;
- authorized compensation restore and unauthorized snapshot refusal.

Acceptance:

- supported operations survive native serialize/reload semantics without false
  projection mismatch;
- failure tests prove either no mutation or exact recoverable partial mutation;
- the M0 incident matrix and M1 cross-language contract matrix remain green;
- no test depends on browser-only normalization not recorded in the ledger.

### Slice 6 — Enforce ownership and normalization-ledger gates

Add architecture tests as the final migration step, not as follow-up work.

Extend:

- `tests/browser/ownership_contract.test.mjs`;
- `tests/browser/frontend_ownership_regression.test.mjs`;
- `tests/browser/m1_contracts.test.mjs`;
- `tests/test_m1_contracts.py` where cross-language ownership evidence belongs.

Add a focused static gate if clearer:
`tests/browser/intent_graph_adapter_ownership.test.mjs`.

The gates must fail when:

- any Agent Edit module other than `intent_graph_adapter.js` reads
  `app.graph`, `app.canvas.graph`, `_nodes`, native links/groups, or calls
  graph serialization;
- any other module calls graph/node/group mutation APIs;
- roundtrip, preview, replay, lifecycle, projection, or transport code invokes
  `loadGraphData`, `clear/configure`, `connect`, `removeLink`, `add`, or
  `remove` for Agent Edit;
- stable identity falls back to native ID, title, position, class type, or
  array index;
- native normalization or field categorization is implemented outside the
  adapter/registry owner pair;
- a normalization rule has no ledger entry and fixture;
- a supported canonical op lacks adapter success, preflight-failure,
  partial-failure, serialization, and inverse/restoration coverage;
- `workflow_v1` or nested scope reaches mutation.

The allowlist must be narrow and distinguish non-Agent-Edit rendering hooks
from graph access. Generated `web_dist` artifacts are not architecture owners
and must not be used to satisfy source gates.

Acceptance:

- repository-wide static scan has one native graph owner;
- every normalization ledger row names an active test;
- every supported operation has complete adapter coverage;
- full browser contracts, focused Python M1 contracts, and the M0 manifest
  matrix pass with zero new skips.

## Fail-closed acceptance matrix

Before M2 can be marked complete, tests must prove that each condition below
returns a typed diagnostic before mutation:

| Condition | Required result |
| --- | --- |
| Unknown delta/projection/authority version | Unsupported contract |
| Missing prepared authority or identity fence | Missing authority |
| `workflow_v1` forward operation | Forbidden operation |
| Non-root or nested scope | Unsupported scope |
| Cross-scope link | Unsupported scope |
| Missing node/group stable ID | Missing identity |
| Unknown semantic field | Unsupported field |
| Missing node factory or graph capability | Unsupported capability |
| Unclassified native representation | Unsupported normalization |
| Candidate/precondition mismatch discovered in preflight | Precondition refusal |
| Snapshot restore without explicit restoration authority | Unauthorized restoration |

For failures after mutation begins, the result must retain the prepared
authority, landed prefix, before/after serialized evidence, and inverse or
restoration authority. M3 will become the sole comparison/verifier owner; M2
must provide complete evidence without making a second verification contract.

## Proof commands

The implementer must record exact commands and counts. At minimum run:

```bash
node --test tests/browser/intent_graph_adapter.test.mjs
node --test tests/browser/dynamic_io_smoke.test.mjs
node --test tests/browser/graph_projection.test.mjs
node --test tests/browser/ownership_contract.test.mjs
node --test tests/browser/frontend_ownership_regression.test.mjs
node --test tests/browser/m1_contracts.test.mjs
python -m pytest tests/test_m1_contracts.py tests/test_candidate_transaction_layout_contract.py
make browser-contracts
```

If M1 renames or consolidates a listed test before commit, use the committed
M1 replacement and update this brief in the same M2 planning commit.

## Done criteria

- `intent_graph_adapter.js` is the sole Agent Edit native graph owner.
- All six supported canonical operations and layout mutation flow through it.
- Preview, Apply, inverse, compensation restoration, legacy preview/replay
  bridges, and future Undo execution have one adapter path.
- No forward whole-graph replacement remains.
- Stable identity and native normalization cannot be reinterpreted by callers.
- Every supported operation survives native LiteGraph serialization and
  inverse/restoration proof.
- Exact `a66422e…` and `eb45e…` incidents pass through the public adapter API.
- Ownership and normalization-ledger gates prevent duplicate native authority.
- M0 and M1 gates remain green with no new skips.

## Anti-scope

- No workflow controller extraction or API transport rewrite; those are M4.
- No central Apply/rollback verifier extraction; that is M3.
- No complete durable Undo/recovery product implementation; that is M5.
- No nested-scope/subgraph support.
- No general whole-workflow replacement.
- No arbitrary third-party node-pack compatibility promise; M2 records
  unsupported behavior, while M6 owns the pinned compatibility matrix.
