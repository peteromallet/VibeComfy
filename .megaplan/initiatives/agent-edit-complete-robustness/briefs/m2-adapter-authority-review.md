# M2 adapter authority review

## Verdict

M2 must be an ownership transfer, not a facade extraction:
`intent_graph_adapter.js` becomes the sole Agent Edit native-graph boundary,
while `comfy_adapter.js` stops being a graph adapter and retains only non-graph
ComfyUI integration hooks.

## Required boundary

| Concern | Owner after M2 |
| --- | --- |
| Acquire the active graph, capture immutable serialization, detect graph mutation capabilities, repaint after mutation | `intent_graph_adapter.js` |
| Mechanical stable-ID-to-live-object lookup, native node/link/group construction, dynamic native repair, delta execution, partial-prefix evidence, authorized restoration execution | `intent_graph_adapter.js`, private implementation |
| Stable identity validity, link identity, field meaning, ordering, semantic native normalization, projections, and projection hashes | `projection_registry_v1.js` |
| Delta envelope/version/op grammar and exact op values | `canonical_delta.js` |
| Prepared/restoration authority validation | `prepared_authority_v1.js` and `journal_durable_v1.js` |
| Success, mismatch, and rollback-verification decisions | M3 verifier |
| Queue guard, foreground draw-hook installation, extension registration, and non-graph frontend capability reporting | `comfy_adapter.js` |

`comfy_adapter.js` must no longer export or implement `getLiveGraph`,
`detectGraphApply`, `detectGraphDeltaApply`, `detectGraphLayoutApply`,
`preflightDeltaPlan`, `applyGraphDeltaInPlace`, `applyGraphLayoutInPlace`,
`applyGraphCandidateInPlace`, graph serialization, graph harness construction,
or stable graph lookup helpers. Moving those exports behind a wrapper would
leave two graph authorities.

Native normalization needs a strict split:

- The adapter may repair or preserve native representation so LiteGraph can
  serialize and continue functioning.
- The registry alone decides whether two serialized representations are
  semantically equivalent.
- The adapter must not rewrite a projected value merely to make a hash match.

## Non-negotiable invariants

1. Only `intent_graph_adapter.js` may read or write Agent Edit graph structure:
   `app.canvas.graph`, `_nodes`, `_groups`, native links, serialization, node
   factories, `add`, `remove`, `connect`, or `removeLink`.
2. The adapter never exposes live LiteGraph objects. Consumers receive frozen
   serialized captures, typed capabilities, and bounded evidence.
3. Stable UIDs/group IDs cross the boundary. Native IDs are candidate-bound
   aliases internal to one adapter operation and never fallback authority.
4. Forward mutation has no `loadGraphData`, `clear/configure`, or generic
   whole-graph replacement escape hatch.
5. Every failure before the first write produces zero mutation. Every failure
   after the first write returns the exact executed prefix, before/after
   captures when available, and still-valid restoration authority.
6. Adapter evidence records native execution; it does not declare semantic
   success. M3 owns that verdict.
7. Preview, Apply, rollback, compensation, and replay cannot retain separate
   mutation implementations.

## Ranked duplicate paths to remove

1. `comfy_adapter.js`: `canonicalNodeUid`, `buildGraphIndex`,
   `liveNodeIndex`, and `resolveLiveNode` fall back to native IDs and compete
   with registry identity.
2. `applyGraphCandidateInPlace` and its consumers in
   `vibecomfy_roundtrip.js`, `preview_picker.js`, and `agentic_replay.js`
   preserve generic whole-graph authority.
3. `vibecomfy_roundtrip.js`: `captureSerializedGraphForAgent`,
   `getLiveGraph`, `getLiveGraphNodes`, `repairLiveIntentNodesFromCandidate`,
   link-store repair, inverse construction, rollback restoration, and
   `loadGraphData`/`graph.configure` wrappers are a second native adapter.
4. `active_canvas_scope_guard.js` serializes the graph directly. It should
   consume an adapter capture rather than acquire graph state itself.
5. `panel_overlay.js` consumes live nodes through injected getters. It should
   consume an immutable adapter-produced draw snapshot; dependency injection
   does not remove graph authority.
6. `detectCapabilities` in `comfy_adapter.js` and
   `adapterCapabilitySnapshot` in `vibecomfy_roundtrip.js` independently
   inspect graph capability.
7. The harness-only serialize/clear/configure fallback in
   `applyGraphDeltaInPlace` contradicts the production ownership rule and can
   conceal missing native mutation support.

## Contract defects to resolve before Slice 4

The current brief has two foundational ambiguities.

First, M1 declares the six `delta_v1` operations as the sole forward mutation
language, but none represents node geometry or group creation/removal.
`applyGraphLayoutInPlace` consequently treats the candidate graph itself as a
parallel mutation language. M2 must not silently preserve that exception.
Layout needs an explicitly versioned operation payload—either a layout delta
contract or a declared versioned layout materialization contract—before the
adapter applies it.

Second, current `preflightDeltaPlan` derives `set_node_field` and `set_mode`
values from `candidateGraph`, even though canonical ops already carry
authoritative `value`/`mode`. That makes the candidate graph a second source
of mutation intent and is also why current inverse operations can copy forward
ops instead of carrying old values. The adapter must execute exact canonical
op values. Any extra add-node/restoration payload must be explicitly bound and
digested by prepared authority.

`projectCandidateGraphToRuntimeLayout` also mixes native measurement with a
layout policy that moves nodes. Native measurement may live privately at the
adapter boundary, but post-prepare collision placement changes authoritative
geometry and therefore belongs in an explicit pre-prepare layout operation,
not in the adapter.

## Enforcement

Add a source gate that permits graph-structure tokens only in
`intent_graph_adapter.js` and test harnesses, with a narrow canvas-drawing
allowlist. Add an import gate forbidding graph exports from
`comfy_adapter.js`. Assert that no graph-facing API returns live objects, no
identity helper falls back to native ID/title/position/index, every
normalization ledger row names an active fixture, and every supported
operation covers preflight refusal, success, every partial prefix,
serialization failure, inverse/restoration, and unknown-version refusal.
