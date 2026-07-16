# M2 Slices 1–2 — Bounded Acceptance Checklist

This checklist is scoped to the first two ordered slices in
`m2-native-adapter.md`. It deliberately does not require the identity,
normalization, mutation, inverse, or restoration work assigned to Slices 3–6.
The full milestone checklist is preserved in `m2-full-acceptance.md`.

## Acceptance record — 2026-07-17

Accepted. Exact evidence: 77/77 focused adapter/ownership/projection/M1 tests,
519/519 browser contracts, 238 roundtrip passes with 2 intentional legacy
skips, and a schema-validated sole machine ledger with 78 unique stable rows
and 120 unique file/region/kind mappings. Both Arnold profiles and all 68 agent
specs parse through the production parser; `git diff --check` is clean.

This record closes only ordered Slices 1–2. Slices 3–6 and overall M2 remain
open.

## Boundary

- Slice 1 inventories and freezes every native graph access in
  `native_normalization_ledger.md`.
- Slice 2 introduces `intent_graph_adapter.js` as the public Agent Edit graph
  boundary for acquisition, capabilities, immutable capture, projection,
  revision notification, and repaint/invalidation.
- `comfy_adapter.js` may temporarily retain private low-level mutation and
  normalization substrate recorded for Slices 3–4. It must not expose a
  competing public graph-acquisition or repaint API.
- Raw identity lookup, dynamic-node normalization, native mutation, layout
  materialization, preview/replay mutation, inverse execution, and restoration
  remain later-slice work. Their presence is not an S1/S2 failure when it has
  an explicit ledger row and migration slice.

## Slice 1 — Inventory freeze

Acceptance requires:

- [x] The ledger covers at least these production consumers:
      `comfy_adapter.js`, `vibecomfy_roundtrip.js`, `preview_picker.js`,
      `agentic_replay.js`, `active_canvas_scope_guard.js`, `panel_overlay.js`,
      and `scope_resolver.js`.
- [x] Every native graph acquisition, structural read, serialize call,
      mutation, whole-graph load, group operation, native factory access,
      repaint coupled to mutation, and local identity/normalization helper has
      exactly one ledger row.
- [x] Every row names its current owner, access kind, semantic purpose, target
      adapter API, projection or identity effect, normalization category,
      fixture/proof, support status, and migration slice.
- [x] Canvas-only, non-graph, projection-only, and harness access are marked
      explicitly rather than silently omitted.
- [x] Later-slice blockers are explicit. In particular, the ledger records the
      missing versioned layout/group operation and the candidate-derived
      `set_node_field`/`set_mode` value problem.
- [x] A static test derives the native-access inventory from production source
      and fails when an access has no matching ledger row. Merely checking that
      known filenames occur in the ledger is insufficient.

The following searches are inventory inputs, not zero-result ownership gates
for S1/S2. Every result must be classified in the ledger:

```sh
rg -n --glob '*.js' \
  '(app|helpers\.app)(\?\.|\.)?(canvas(\?\.|\.)?)?graph\b|\b_nodes\b|\blinks\b|\.serialize\s*\(' \
  vibecomfy/comfy_nodes/web

rg -n --glob '*.js' \
  '\b(loadGraphData|loadGraphDataWithoutScopeSwitch|clear|configure|add|remove|removeLink|connect)\b' \
  vibecomfy/comfy_nodes/web

rg -n --glob '*.js' \
  'canonicalNodeUid|liveNodeIndex|resolveLiveNode|normalizeLive|applyRenderedNodeSizes|repairLiveIntentNodes' \
  vibecomfy/comfy_nodes/web
```

## Slice 2 — Typed public adapter boundary

Acceptance requires:

- [x] `intent_graph_adapter.js` imports without browser globals and exposes a
      dependency-injected factory.
- [x] The factory object is immutable and never exposes the live LiteGraph
      object.
- [x] Missing or ambiguous active graphs return typed failures.
- [x] Unknown adapter/scope contract versions and nested scopes fail before
      serialization or mutation.
- [x] Capture returns a deeply frozen detached serialization.
- [x] Cyclic or throwing native serialization returns bounded typed
      diagnostics with no native stack leak.
- [x] Capability results are immutable plain data and fail closed when graph
      access is unavailable.
- [x] Projection calls delegate to the M1 projection registry and match the
      browser/Python golden corpus.
- [x] Revision and repaint operations return typed results and do not change
      structural or layout projections.
- [x] Roundtrip, active-scope guard, replay capture, and preview repaint enter
      through the adapter for the S2 responsibilities already migrated.
- [x] `comfy_adapter.js` no longer exports public `getLiveGraph`,
      `detectGraphApply`, or `repaintGraph` owner APIs.
- [x] Remaining private low-level S3/S4 substrate is recorded in the ledger;
      no compatibility re-export creates a second public adapter.

## Exact executable gates

```sh
node --test \
  tests/browser/intent_graph_adapter.test.mjs \
  tests/browser/intent_graph_adapter_ownership_static.test.mjs \
  tests/browser/graph_projection.test.mjs \
  tests/browser/ownership_contract.test.mjs \
  tests/browser/frontend_ownership_regression.test.mjs \
  tests/browser/m1_contracts.test.mjs

node --test tests/browser/roundtrip_smoke.test.mjs

make browser-contracts

git diff --check
```

The profile gate must also parse both project profiles and every phase/tier
agent spec through the production Arnold parser. Protected unrelated files
`scorecard.png` and
`docs/plans/vibecomfy-screen-share-recording-brief.md` must remain untracked
and outside the diff.

## Exit rule

Slices 1–2 pass only when all executable gates are green and the inventory
test proves source-derived ledger completeness. Green adapter tests alone do
not waive a weak inventory guard. Conversely, expected S3/S4 accesses do not
fail S1/S2 merely because the full-milestone zero-result searches are not yet
clean; they fail only when unclassified, duplicated as public authority, or
used outside the declared transitional boundary.
