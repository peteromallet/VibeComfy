# M2 Full Milestone — Executable Acceptance Checklist

This full-milestone acceptance design applies the M2 locked decisions to the current M1 tree.
It incorporates an independent DeepSeek Pro audit and the reconstructed
17-path native-access inventory.

Current substate (2026-07-17): ordered M2 Slices 1–2, the observation-only
Family-A preparation, and the C0–C1 contract/private-plan checkpoint are
accepted under their bounded checklists. The adjacent panel/workflow scheduler
activation fence is also accepted. Family A and C0–C1 do not close S3: 0/27
coupled ownership rows have transferred and all seven S4-debt rows remain
open. The C2 atomic S3+S4 consumer/deletion/ledger cut remains pending, as do
Slices 5–6 and every unchecked full-milestone gate in this document. M2 is not
complete.

Accepted C0–C1 proof: 156/156 focused JavaScript, 118/118 focused Python,
294/294 lifecycle, 60/60 repair/compatibility, and 569/569 browser-contract
tests; 64-template canonical parity; and successful parsing of all 68 Arnold
profile specs. Accepted scheduler-fence proof: browser smoke 1,531 passed with
2 intentional skips, plus two full roundtrip runs at 238 passed with 2
intentional skips each. These are prerequisite and release-safety proofs only;
they do not satisfy any unchecked native-owner/full-milestone item below.

The acceptance rule is stricter than “a new adapter file exists”:

> `intent_graph_adapter.js` is accepted only when it contains the native
> implementation, every Agent Edit consumer enters through its typed API, and
> previous owners can no longer capture, inspect, normalize, mutate, restore,
> or serialize live LiteGraph state.

## Reconstructed 17-path inventory

Each path must move behind `intent_graph_adapter.js` or be deleted.

| # | Current escape hatch | Required disposition |
|---|---|---|
| 1 | Roundtrip `normalizeLiveExecNodesForSerialization` reads live nodes | Adapter-private native normalization |
| 2 | `captureSerializedGraphForAgent` calls live `serialize()` | Adapter capture/serialize API |
| 3 | `applyRenderedNodeSizesToSerializedGraph` reads live nodes | Adapter capture normalization option |
| 4 | `restoreCandidateLinksOnLiveGraph` edits native stores and slots | Adapter canonical link restoration |
| 5 | `repairLiveIntentNodesFromCandidate` decorates native nodes | Adapter normalization plugin |
| 6 | Forward delta Apply through `comfy_adapter.js` | Adapter canonical mutation |
| 7 | Layout Apply/preview live mutation | Adapter layout operation |
| 8 | Inverse-delta rollback | Adapter restoration execution |
| 9 | Whole-graph rollback compensation | Typed adapter restoration plan only |
| 10 | `loadGraphDataWithoutScopeSwitch` | Compensation only; never forward Apply |
| 11 | Monkey-patched `app.loadGraphData` | Adapter/native hook integration or isolated non-Agent-Edit compatibility |
| 12 | Monkey-patched `graph.configure` | Adapter/native hook integration; no shell ownership |
| 13 | Shell `getLiveGraph`, `_nodes`, and `links` access | Adapter methods or detached snapshots |
| 14 | Revision/token/snapshot live serialization | Adapter capture result |
| 15 | Shell repaint via `change`/`setDirtyCanvas`/draw | Adapter `requestRepaint()` |
| 16 | Undo and legacy round-trip whole-graph loading | Adapter restoration or explicit legacy boundary |
| 17 | Scope guard, agentic replay, and preview picker raw graph access | Adapter calls; no raw graph helper dependency |

## Slice 1 — Native boundary, capture, normalization, ownership

### Required contract

- [ ] `intent_graph_adapter.js` owns graph acquisition, capability checks,
      capture, serialization, stable identity, native normalization, and
      repaint.
- [ ] Public methods return discriminated typed results and diagnostics, never
      bare booleans.
- [ ] Consumers receive detached snapshots or typed results, never the raw
      LiteGraph object.
- [ ] `graph_projection.js`, `canonical_delta.js`, and
      `layout_verification_contract.js` remain the M1 semantic owners. The
      adapter consumes rather than copies them.
- [ ] Dynamic-node normalization is plugin/handler based, including
      `vibecomfy.exec`.
- [ ] Extension-owned opaque fields are preserved and excluded only through a
      declared projection.
- [ ] Nested scopes fail before mutation-oriented capture or native mutation.

### Exact static ownership searches

Add `tests/browser/intent_graph_adapter_ownership.test.mjs`. These searches
must produce no output after excluding the owner:

```sh
# Raw graph acquisition.
rg -n --glob '*.js' \
  '(app|helpers\.app)(\?\.|\.)?(canvas(\?\.|\.)?)?graph\b' \
  vibecomfy/comfy_nodes/web \
  | rg -v '/intent_graph_adapter\.js:'

# Native capture/mutation/restoration.
rg -n --glob '*.js' \
  '\b(graph|liveGraph|network)\.(serialize|clear|configure|add|remove|removeLink|connect)\s*\(' \
  vibecomfy/comfy_nodes/web \
  | rg -v '/intent_graph_adapter\.js:'

# Whole-workflow loading.
rg -n --glob '*.js' \
  '\b(loadGraphData|loadGraphDataWithoutScopeSwitch)\b' \
  vibecomfy/comfy_nodes/web \
  | rg -v '/intent_graph_adapter\.js:'

# Known old-owner helpers.
rg -n \
  'normalizeLiveExecNodesForSerialization|captureSerializedGraphForAgent|applyRenderedNodeSizesToSerializedGraph|restoreCandidateLinksOnLiveGraph|repairLiveIntentNodesFromCandidate|installGraphConfigureIntentFallback' \
  vibecomfy/comfy_nodes/web \
  | rg -v '/intent_graph_adapter\.js:'
```

The ownership test must additionally prove:

- [ ] The new adapter does not import native graph implementations such as
      `getLiveGraph`, `applyGraphCandidateInPlace`,
      `applyGraphDeltaInPlace`, or `applyGraphLayoutInPlace` from
      `comfy_adapter.js`.
- [ ] `comfy_adapter.js` no longer exports or defines those owner APIs.
- [ ] Roundtrip, scope guard, replay, and preview picker use the new adapter and
      contain no raw acquisition.
- [ ] No identity helper falls back from a missing stable node/group ID to
      title, position, or array order.
- [ ] No copied implementation carries a “must stay in sync” comment.

Canvas repaint is UI-only, but raw graph acquisition to invoke it remains
adapter-owned. Consumers call `requestRepaint()`.

### Slice 1 runtime tests

Create `tests/browser/intent_graph_adapter.test.mjs` covering:

- [ ] Capture returns a detached serialized snapshot.
- [ ] Known `vibecomfy.exec` `io` representations normalize to the same
      `structural_v1` projection.
- [ ] Opaque extension fields survive capture and serialization.
- [ ] Stable node/group IDs survive native normalization; duplicate titles
      remain distinct.
- [ ] Missing group ID returns `LAYOUT_GROUP_ID_REQUIRED`; title matching is
      never attempted.
- [ ] Unknown projection/delta versions and nested scopes fail closed before
      mutation.
- [ ] Missing graph/serialize capabilities return typed diagnostics.
- [ ] `requestRepaint()` changes render counters while structural/layout
      projections remain unchanged.
- [ ] Exact `eb45e…` and `a66422e…` fixtures pass
      capture → normalize → serialize → project.

## Slice 2 — Canonical mutation and restoration planning

### Required mutation contract

- [ ] The six `delta_v1` operations are the only forward structural mutation
      language: `set_node_field`, `set_mode`, `add_node`, `upsert_link`,
      `remove_node`, and `remove_link`.
- [ ] Layout uses its declared versioned contract and proves structural no-op.
- [ ] Preview, Apply, rollback, Undo, and recovery enter the same adapter.
- [ ] Forward Apply never calls `clear`, `configure`, or `loadGraphData`.
- [ ] Snapshot/whole-graph restoration is compensation only and returns a
      typed plan with reason, scope, precondition, postcondition, and
      diagnostics.
- [ ] Preflight completes and records inverse/restoration authority before the
      first native mutation.

### Runtime tests

- [ ] Every canonical operation survives
      capture → preflight → apply → native serialize → project.
- [ ] Mixed operations preserve untouched node identity, fields, geometry,
      groups, links, and opaque data.
- [ ] Node creation uses native construction; links use native `connect`;
      removals use native `removeLink`/`remove`.
- [ ] No plain object is inserted into a modern `Map<LLink>`.
- [ ] Layout preserves semantics, stable group IDs, and duplicate titles.
- [ ] Malformed/unknown ops, missing or duplicate IDs, unresolved nodes/slots,
      failed native construction, and failed `connect()` return typed
      diagnostics.
- [ ] Every preflight failure produces zero native mutation calls.
- [ ] Failure after operation N reports the exact landed prefix and provides a
      verifiable inverse/restoration plan.
- [ ] Serialize failure after mutation retains mutation evidence and recovery
      authority.
- [ ] Applying the inverse restores the original operation-specific
      projection.
- [ ] A forward-path tripwire makes `clear`, `configure`, and `loadGraphData`
      throw while normal delta/layout Apply still succeeds.

### Authority-not-wrapper proof

Add an adapter call-boundary sentinel around every native fake-graph method.
Each native method asserts that the sentinel is active and captures its stack.

Acceptance requires:

- [ ] Every native stack includes `intent_graph_adapter.js`.
- [ ] No native stack includes `vibecomfy_roundtrip.js`, `comfy_adapter.js`,
      replay, picker, or scope guard as the caller that performed native work.
- [ ] Poisoning every legacy `comfy_adapter.js` graph API does not affect
      consumer tests because no consumer imports or calls it.
- [ ] Old graph-owner exports are absent, not retained as compatibility
      aliases or re-exported wrappers.

### Consumer route and ordering tests

- [ ] Submit capture, preview, Apply, rollback, Undo, rebaseline,
      recovery/rehydration, scope fingerprinting, replay, and demo picker each
      invoke a named adapter method.
- [ ] Apply ordering is:
      `prepare → adapter preflight/apply → adapter serialize → verify/finalize`.
- [ ] Rollback ordering is:
      `adapter restoration plan → adapter restore → adapter serialize →
      rollback verification`.
- [ ] Neither ordering contains forward whole-graph replacement.

## Commands and exit gate

```sh
node --test \
  tests/browser/intent_graph_adapter.test.mjs \
  tests/browser/intent_graph_adapter_ownership.test.mjs \
  tests/browser/canonical_delta.test.mjs \
  tests/browser/graph_projection.test.mjs \
  tests/browser/ownership_contract.test.mjs \
  tests/browser/frontend_ownership_regression.test.mjs

node --test tests/browser/roundtrip_smoke.test.mjs
```

Slices 1–2 are accepted only when:

1. All 17 inventory rows have a migrated/deleted disposition and static
   searches are clean.
2. Native implementations live in `intent_graph_adapter.js`; it does not
   delegate them to `comfy_adapter.js`.
3. Runtime stacks prove native calls occur within the adapter boundary.
4. All six operations and layout mutation survive native serialization.
5. Forward mutation performs zero whole-graph replacement calls.
6. Preflight failures are mutation-free and every partial/post-mutation failure
   retains actionable restoration authority.
7. Exact layout and dynamic-exec incident fixtures remain green.
