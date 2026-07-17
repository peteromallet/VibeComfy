# M2 Slice 3 Preparatory and Atomic S3+S4 Acceptance

This checklist separates the independently landable observation-only S3
Family A from the atomic S3+S4 ownership cut required by
`m2-slices-3-4-implementation.md` and the authoritative
`m2-native-adapter.md`.

Family A can be accepted as preparatory work. It is not standalone S3
ownership closure. Stable identity/index/link ownership closes only when its
preflight/delta/layout/apply/inverse consumers move behind
`intent_graph_adapter.js` in the same atomic S3+S4 change, without moving
semantic meaning out of `projection_registry_v1.js`.

Recorded substate (2026-07-17): preparatory Family A is accepted. The exact
incident fixture, detached observation APIs, identity refusals, ledger
reclassification, and browser gates are green. This records 0/27 coupled
ownership transfers; S3 is not closed, and the contract-first atomic S3+S4
cut remains pending.

## GLM-validated boundary

No truthful API lets old S4 code consume an adapter-private live
node/index/link/factory without exposing live objects, wrapping the old owner,
or copying the implementation. Therefore the former standalone 27-row
transfer is not an acceptance gate. Wrapper ownership remains forbidden.

## Preparatory Family A boundary

- In scope: stable UID/group-ID lookup, candidate-bound native aliases, named
  endpoint/link observation, detached dynamic socket/widget representation,
  converted-widget observation, rendered measurement capture, lossless native
  link enumeration, immutable overlay draw snapshots, and normalized
  serialization.
- `intent_graph_adapter.js` owns native mechanics and returns frozen plain
  evidence. Its live resolvers, factories, indexes, and repair helpers remain
  closure-private.
- `identity_contract_v1.js` and `projection_registry_v1.js` continue to own
  identity validity, projected field meaning, ordering, semantic equivalence,
  and hashes. The adapter consumes those decisions; it does not copy them.
- Slice 4 canonical mutation, layout execution, inverse execution, and
  authorized restoration are not Family A exit requirements. Coupled legacy
  identity/index/link rows remain truthfully with their S4 consumers and are
  not relabelled as adapter-owned.
- The absent `layout_operation_v1` and `mutation_materialization_v1` owners are
  S4 prerequisites, not S3 blockers. S3 must not compensate for their absence
  with candidate-driven placement, materialization, inverse, or restore.
- M3 verification verdicts, M4 controller work, M5 recovery behavior, and
  nested/subgraph support are out of scope.

## Required public behavior

- [ ] `capture()` accepts only the declared root-scoped normalization option,
      including `native_normalization_v1`, and returns a deeply frozen,
      detached serialized graph/evidence envelope.
- [ ] Normalized serialization after detached normalization, or after the
      bounded repair lease below, uses the same adapter
      boundary and never exposes a live graph, node, link, group, widget,
      factory, slot, or native-ID map.
- [ ] `captureDrawSnapshot()` returns frozen plain draw geometry/widgets only;
      `panel_overlay.js` receives no injected live-node getter or live graph.
- [ ] Rendered measurement capture is explicit and cannot silently rewrite
      authoritative geometry or projected values.
- [ ] `vibecomfy_roundtrip.js`, `active_canvas_scope_guard.js`,
      `agentic_replay.js`, `preview_picker.js`, `panel_overlay.js`, and
      `scope_resolver.js` consume adapter-produced plain evidence for the S3
      responsibilities they need.
- [ ] Public adapter results contain stable IDs and named endpoints only.
      Candidate-bound native aliases never escape in success or diagnostics.
- [ ] Every public S3 call is observational: no persistent live socket,
      widget, property, link-store, configure, revision, repaint, lifecycle,
      or panel transition is attributable to the adapter.

## Identity refusal matrix

Each refusal must be a frozen typed diagnostic, must not select the first
match, and must leave the live graph and all repair/mutation counters
unchanged.

- [ ] A node with native `id` but no `vibecomfy_uid` returns
      `missing_identity`; native ID, title, position, type/class, and array
      order are not fallback authority.
- [ ] An id-less group returns `missing_identity` even when its title is
      unique. No title is copied into an ID.
- [ ] Two live nodes with the same stable UID fail as ambiguous identity;
      neither node is selected and the diagnostic code is explicitly asserted.
- [ ] Two groups with the same stable group ID fail as ambiguous identity;
      neither group is selected.
- [ ] Duplicate group titles with distinct stable IDs remain distinct and
      succeed through capture, serialization/reload, and `layout_v1`.
- [ ] A named link endpoint that resolves to zero or multiple native slots
      fails closed; slot index or first-match fallback is forbidden.
- [ ] Candidate-bound native-ID translation succeeds only when the candidate
      carries an explicit stable UID. The same native ID without a candidate
      UID returns `missing_identity`.
- [ ] Reusing a native ID for a different stable UID cannot cross the
      candidate boundary or reuse a stale alias.
- [ ] Remove node A, then add a different node B reusing A's native ID: the
      next operation cannot resolve A or return its cached object and resolves
      B only through B's stable UID. Repeat with the same UID on a new native
      object to prove the current object, not a stale cache entry, is used.
- [ ] Identity indexes are rebuilt per operation or bound to a proven graph
      revision; no closure cache survives a remove/re-add without invalidation.
- [ ] Non-root scope, nested `definitions`, nested group scope, and any
      cross-scope endpoint return `unsupported_scope` before identity lookup or
      repair.

Do not permit an untyped thrown error for duplicate identities. If no existing
contract code names identity ambiguity, the implementation must declare one
and assert it consistently rather than silently treating ambiguity as
`missing_identity` or success.

## Strict serialization-repair lease

Detached normalization is the default. An adapter-authored live write is
permitted only when a known fixture proves that faithful native serialization
is otherwise impossible and all of these lease conditions hold:

- [ ] The lease is private, synchronous, versioned, fixture-specific, and
      projection-neutral. It cannot accept candidate data as repair authority
      or span an `await`, callback, lifecycle hook, or ambient monkey patch.
- [ ] Before the first write it captures the exact affected live state,
      including object/array references, own keys and descriptors, socket and
      widget order, widget values, properties, link references/back-pointers,
      and any opaque fields touched by the lease.
- [ ] Only the minimum allowlisted representation fields are written. It may
      not call configure/load, factory construction, add/remove/connect,
      revision, repaint, panel/scope orchestration, or persistent hydration.
- [ ] One lexical `try/finally` encloses every leased write and the complete
      serialize/clone path. The `finally` restores exact before-state on
      success, normalization throw, getter/callback throw, serialization
      failure, clone/projection failure, cancellation/abort, and any early
      return.
- [ ] Restoration proves reference, descriptor, order, multiplicity, value,
      and back-pointer equality—not merely JSON or projection equality. If
      exact restoration cannot be proved, the representation returns
      `unsupported_normalization` before the first write.
- [ ] Tests inject a failure after every leased primitive and during serialize;
      each test observes the exact original live state, unchanged revision and
      repaint counters, a bounded typed diagnostic, and no leaked live object.
- [ ] Repeated capture is idempotent: evidence is identical and the live graph
      serialization/revision before, between, and after calls is unchanged.

Any live repair without this lease is S4 mutation, regardless of whether its
function or ledger category contains the word “normalize.”

## Native normalization matrix

- [ ] Promote the exact incident to
      `tests/fixtures/agent_edit/eb45e_dynamic_exec_v1.json` from
      `/Users/peteromalley/Documents/reigh-workspace/ComfyUI/out/editor_sessions/eb45e0ef50e146c6985417bf1449e96a/turns/0001/original.ui.json`,
      `candidate.ui.json`, `messages.jsonl`, and `response.json`. The fixture
      records session/turn provenance and raw artifact digests and preserves
      the complete relevant original/candidate graph payloads; a simplified
      hand-written exec node is not acceptable.
      Required SHA-256 provenance is:
      `original.ui.json` `829fe306efb90413e2d5adbef60713dece62b1819f2bdca2a6f56a7f8c88926c`,
      `candidate.ui.json` `710c79865b320dc53f3e2824cd8df0f725382fc943170d0b1240cbcd06854e80`,
      `messages.jsonl` `982ef57b4cefb455cd899a17976a8af3273d6de70bd51e2d44d0a883242f68c3`,
      and `response.json` `8830157f2c7ff14b1954500eb989734ce971a957dd2fe5dc9b1763c3ce0349e4`.
- [ ] The exact
      `tests/fixtures/agent_edit/a66422e6_layout_regression.json` fixture
      preserves stable group IDs and duplicate titles across native
      configure/serialize behavior.
- [ ] `tests/fixtures/agent_edit/m1_projection_golden_v1.json` remains the
      shared semantic corpus for converted-widget, opaque-extension,
      duplicate-title, missing-identity, and nested-scope cases.
- [ ] Dynamic inputs/outputs and converted widgets normalize without false
      `structural_v1` drift and survive serialize/reload. Capture and display
      paths perform no persistent socket removal/addition, widget/property
      hydration, candidate import, revision, or repaint; a permitted lease is
      exactly restored before either path returns.
- [ ] Dynamic exec capture preserves `source`, `io`, all widgets and converted
      widgets, all socket records, link references, and opaque properties.
      Display labels (`label`, `name`, or `title`) are never promoted into
      semantic state or persisted as a repair.
- [ ] Reroutes and native link arrays, objects, `Map`s, Proxy-wrapped maps, and
      class instances produce equivalent detached evidence while the source
      container remains untouched.
- [ ] Link evidence preserves cardinality and multiplicity—including parallel
      links and multiple records targeting one port—plus link IDs, endpoints,
      port names/types/order, and opaque serialized fields. Enumeration never
      deduplicates, drops, chooses a winner, or replaces `graph.links`.
- [ ] Malformed, throwing-Proxy, or internally inconsistent link records
      return a typed bounded refusal without rewriting the container.
- [ ] Opaque extension-owned values survive capture, repair, serialize, and
      reload recursively and exactly. They are excluded only when the registry
      declares them non-semantic.
- [ ] Native-generated defaults are recorded and normalized only where a
      concrete fixture proves the representation.
- [ ] An unknown node family is accepted only when its observed native
      difference is projection-neutral by registry proof and all opaque data
      is preserved; otherwise it returns `unsupported_normalization`.
- [ ] Node 2.0 or another unsupported representation returns
      `unsupported_normalization` before socket/widget/group repair.
- [ ] Serialization/getter/custom-callback failure remains bounded and typed,
      does not leak native objects or stacks, and satisfies the repair lease's
      exact-finally restoration proof.

## Representation repair versus semantic meaning

Both proofs below are required; one cannot substitute for the other.

1. **Lossless native proof:** compare the captured graph before and after
   normalize → native serialize/reload. Stable node/group IDs, named endpoint
   identity, unrelated fields, geometry, link connectivity, and opaque
   extension payloads must be preserved. Only representation fields named by
   the concrete normalization fixture may change.
2. **Semantic-owner proof:** project both representations through the exported
   `projection_registry_v1` API and byte-compare the declared projection. The
   adapter must delegate projection and hashing; it may not drop, rewrite, or
   synthesize a projected value merely to obtain equality.

Tests must assert the normalized serialized payload as well as its projection.
A matching hash alone is insufficient because destructive normalization could
otherwise hide lost native or opaque data.

Static review must also show that the adapter has not copied registry field
sets, ordering rules, identity-validity rules, canonicalization, or hash code.
The registry may import no native graph implementation in return.

## Ledger state and atomic transfer gates

### Preparatory Family A

- [ ] No legacy row is marked transferred merely because an additive detached
      observation API or test now exists. The former standalone 27-row
      transfer is explicitly not required and not permitted at this checkpoint.
- [ ] New Family A native access is classified source-truthfully with concrete
      fixture proof; existing coupled rows remain in their current owners with
      unresolved migration status.
- [ ] The seven persistent/semantic-write rows below are reclassified to S4
      debt and cannot be called by Family A capture/display paths.

### Atomic S3+S4 closure

These 27 identity/index/link/observation rows transfer to private adapter-owned
regions only in the same change that moves their S4 consumers:

`NGA-006`, `NGA-008`, `NGA-011`–`NGA-014`, `NGA-017`, `NGA-023`–`NGA-024`,
`NGA-040`, `NGA-042`, `NGA-044`–`NGA-047`, `NGA-051`,
`NGA-054`–`NGA-055`, `NGA-057`, `NGA-059`–`NGA-061`, `NGA-063`–`NGA-065`,
`NGA-068`, and `NGA-074`.

Atomic transfer means decomposition, not copying: `NGA-040` becomes a separate
stable-UID-keyed measurement channel; `NGA-047`, `NGA-051`, and `NGA-061`
must shed all candidate/live persistent-write subcalls and operate only on
detached evidence (apart from a separately proven strict lease). Their old
call graphs are not accepted merely because the top-level row moved.

These seven persistent/semantic-write rows do **not** transfer in preparatory
Family A and must first be truthfully reclassified to Slice 4 migration debt:

- `NGA-048`: socket removal/type rewriting in `decorateIntentNode`;
- `NGA-050`: replacement/repair of the live `graph.links` store;
- `NGA-062`: live exec widget/property rewriting before serialization;
- `NGA-067`: candidate-driven live socket/widget/property replacement;
- `NGA-070`: lossy link sanitation, deduplication, and slot rewriting;
- `NGA-072`: persistent widget/`widgets_values`/property writes; and
- `NGA-078`: ambient `graph.configure` monkey patch and panel orchestration.

- [ ] At atomic closure every listed 27-row ID remains present exactly once,
      now names
      `intent_graph_adapter.js` and semantic owner `intent_graph_adapter`,
      remains Slice `S3`, has `supported_adapter_owner` status, and names a
      concrete active fixture/test identifier.
- [ ] Its file/region/access counts exactly match the source-derived scanner.
- [ ] No listed ID retains an old `comfy_adapter.js` or
      `vibecomfy_roundtrip.js` mapping.
- [ ] No extra row or compatibility row preserves the old implementation.
- [ ] The ledger remains closed-schema, has 78 unique stable IDs, has no
      duplicate source mapping, stale mapping, count drift, placeholder proof,
      unknown enum, or unmatched production access.
- [ ] During Family A, S4 rows remain classified as S4 debt and are not
      relabelled to make S3 appear complete. The scanner/schema and mutation
      sentinels are not weakened.
- [ ] During Family A, the seven rows above remain outside the adapter, have
      `slice: "S4"` and
      an unresolved S4 status, and are not copied, called, wrapped, or
      re-described as S3 repair. `NGA-078` is an explicit S4 boundary: S3
      installs no configure hook, callback wrapper, or panel/scope side effect.
- [ ] S3 may observe already-issued stable identities after a native configure
      cycle, but only as a bounded read of the resulting graph. It cannot
      monkey-patch `graph.configure`, repair during configure, call panel code,
      or accept candidate data as repair authority. If identity preservation
      requires any of those powers, NGA-078 remains an explicit S4/contract
      blocker rather than a partial S3 relocation.
- [ ] At atomic closure the seven rows and every other S3/S4 debt row are
      moved behind the adapter or deleted with their consumers; no unresolved
      identity/index/link/mutation/restoration owner remains outside it.

Atomic-closure row check (not a Family A gate):

```sh
# Atomic closure only:
S3_IDS='NGA-006 NGA-008 NGA-011 NGA-012 NGA-013 NGA-014 NGA-017 NGA-023 NGA-024 NGA-040 NGA-042 NGA-044 NGA-045 NGA-046 NGA-047 NGA-051 NGA-054 NGA-055 NGA-057 NGA-059 NGA-060 NGA-061 NGA-063 NGA-064 NGA-065 NGA-068 NGA-074'
jq -e --arg ids "$S3_IDS" '
  ($ids | split(" ")) as $wanted
  | [.rows[] | select(.id as $id | $wanted | index($id))] as $rows
  | ($rows | length) == 27
    and all($rows[];
      .file == "intent_graph_adapter.js"
      and .semantic_owner == "intent_graph_adapter"
      and .slice == "S3"
      and .support_status == "supported_adapter_owner"
      and (.fixture_proof.path | length) > 0
      and (.fixture_proof.identifier | length) > 0)
' tests/fixtures/agent_edit/native_authority_ledger_v1.json

# Preparatory Family A reclassification:
S4_RECLASSIFIED='NGA-048 NGA-050 NGA-062 NGA-067 NGA-070 NGA-072 NGA-078'
jq -e --arg ids "$S4_RECLASSIFIED" '
  ($ids | split(" ")) as $wanted
  | [.rows[] | select(.id as $id | $wanted | index($id))] as $rows
  | ($rows | length) == 7
    and all($rows[];
      .file != "intent_graph_adapter.js"
      and .semantic_owner != "intent_graph_adapter"
      and .slice == "S4"
      and (.support_status == "migration_debt"
           or .support_status == "blocking_migration"))
' tests/fixtures/agent_edit/native_authority_ledger_v1.json
```

The authoritative ownership test must still validate the exact inventory; the
`jq` command is only a focused transfer sentinel.

## Exact atomic source ownership searches

The following old-owner helper search must return no output. It is deliberately
limited to the two former implementation owners so similarly named UI-only
helpers do not create false positives. This is an atomic S3+S4 exit gate, not
a preparatory Family A gate.

```sh
rg -n --glob '*.js' \
  '\b(buildGraphIndex|canonicalNodeUid|getNodeFieldValue|iterateLinkRecords|linkShapeForGraph|liveLinkEntries|liveNodeIndex|resolveEndpoint|resolveFactory|applyRenderedNodeSizesToSerializedGraph|buildGraphNodeIndex|decorateIntentGraphPayload|findSerializedLinkByTarget|getLiveGraphNodes|getUid|liveGraphNodeIndex|lookupLiveNodeByUid|normalizedSerializedLinks|normalizeForSerialize|readNodeFieldValue|readNodeLinkSource|resolveLiveNodeFromCandidate|widgetIndexFromFieldPath)\b' \
  vibecomfy/comfy_nodes/web/comfy_adapter.js \
  vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js
```

During Family A, the reclassified S4 bodies may remain in the old owner only as
declared debt; they must not appear in or be called by the adapter
capture/display path:

```sh
rg -n --glob '*.js' \
  '\b(decorateIntentNode|ensureLiveGraphLinkStore|normalizeLiveExecNodesForSerialization|replaceDynamicExecSlotsFromCandidate|sanitizeSerializedGraphLinks|setExecWidgetValue|installGraphConfigureIntentFallback)\b' \
  vibecomfy/comfy_nodes/web/intent_graph_adapter.js
```

That command must return no output. Static call-chain sentinels must also fail
if `capture`, normalized serialization, or display/draw capture reaches one of
those S4 bodies indirectly through an alias, callback, computed property, or
monkey patch.

These consumer regions may remain as orchestration/UI logic, but the ownership
scanner must report no S3 native access inside them: `collectQueueIssues`,
`computePreviewDiff`, and `readGraphActualForOp`.

Audit all remaining identity/normalization primitives. Any result outside
`intent_graph_adapter.js`, `identity_contract_v1.js`, or
`projection_registry_v1.js` must be a fixture/test or an explicitly reviewed
non-native consumer; no Agent Edit consumer may implement the rule.

```sh
rg -n --glob '*.js' \
  '\b(stableNodeUidV1|stableNodeIdentityV1|resolveLiveNodeByUid|nativeNormalization|unsupported_normalization)\b|properties(?:\?\.|\.)vibecomfy_uid|\b(addInput|addOutput|removeInput|removeOutput|disconnectInput|disconnectOutput)\s*\(|\bwidgets(?:_values)?\s*(?:=|\[)' \
  vibecomfy/comfy_nodes/web
```

Explicit fallback audit; production matches outside the adapter/registry owner
pair are blockers and must also be covered by mutation sentinels in
`intent_graph_adapter_ownership_static.test.mjs`:

```sh
rg -n --glob '*.js' \
  'vibecomfy_uid[^;\n]*(?:\|\||\?\?)[^;\n]*(?:\.id|title|pos|type|class_type)|canonicalNodeUid\([^)]*\)\s*(?:\|\||\?\?)|find\([^\n]*(?:title|pos|class_type)' \
  vibecomfy/comfy_nodes/web
```

No wrapper, alias, re-export, or synchronized copy is allowed:

```sh
rg -n --glob '*.js' \
  "must stay in sync|keep in sync|from [\"']\\./(?:comfy_adapter|vibecomfy_roundtrip)\\.js[\"']" \
  vibecomfy/comfy_nodes/web/intent_graph_adapter.js \
  vibecomfy/comfy_nodes/web/comfy_adapter.js \
  vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js
```

The full native-access search is an inventory input during Family A, not a
zero-result sole-owner gate: correctly classified coupled and S4 access still
exists until the atomic cut. At atomic exit it becomes a sole-owner gate and
fails on any native identity/index/link/mutation/restoration access outside the
adapter or any unclassified access.

## Atomic S3+S4 acceptance

The ownership cut is accepted only as one change satisfying every gate below.

### Contract-first gates

- [ ] BC#1 lands first: versioned cross-language `layout_operation_v1`, exact
      four-op closed grammar, golden corpus, prepared-authority envelope and
      digest binding, root-only scope, stable node/group IDs, duplicate-title
      safety, structural pre==post witness, and unknown/malformed/non-finite/
      nested/structural-field refusals.
- [ ] BC#2 lands next: versioned cross-language
      `mutation_materialization_v1`, exact source-op-indexed add-node and
      inverse re-add payloads, canonical digest binding across prepare, no
      implicit links, and duplicate/unreferenced/UID-class/extra-key/tamper
      refusals.
- [ ] No mutation preflight/apply/inverse API accepts `candidateGraph` or reads
      candidate data as intent. `set_node_field` uses exact `op.value`,
      `set_mode` exact `op.mode`, links exact named `op.from`/`op.to`, node
      construction exact bound materialization, and layout exact
      `layout_operation_v1` values.

Absent layout/materialization contracts do not block preparatory Family A;
they are hard blockers before the atomic ownership cut begins.

### Coupled ownership and execution gates

- [ ] The 27 identity/index/link/observation rows, the seven persistent-write
      rows, and all remaining S4 preflight/delta/layout/inverse/restoration
      rows move or disappear with their consumers in the same change.
- [ ] Old `comfy_adapter.js` and `vibecomfy_roundtrip.js` definitions, imports,
      exports, aliases, wrappers, callbacks, candidate-consistency reads, and
      copied helpers disappear. Orchestration receives only frozen typed
      adapter envelopes.
- [ ] All six `delta_v1` operations and all four `layout_operation_v1`
      operations fully preflight before the first write, use native primitives,
      serialize through LiteGraph, preserve unrelated/opaque state, and return
      stable landed/partial evidence without taking M3 verdict ownership.
- [ ] Exact digested inverse/restoration authority exists before mutation;
      inverse runs in reverse causal order. Snapshot loading is explicitly
      authorized, fenced compensation only.
- [ ] Forward whole-graph replacement is deleted. Forward Apply succeeds while
      `loadGraphData`, `graph.clear`, generic `graph.configure`, and all legacy
      replacement fallbacks are poisoned. Production removes
      `HARNESS_DELTA_APPLY_FALLBACK_MARKER`, `harness-serialize-configure`,
      `legacy_whole_graph_replace`, and graph-apply capability escape hatches.

### Fault and incident gates

- [ ] Deterministic injection covers factory, new-node configure, add/remove,
      connect/removeLink, widget/mode assignment, socket repair, group
      construct/configure/add/remove, geometry, repaint, and serialization.
- [ ] Every preflight/version/scope/identity/capability refusal has zero native
      writes. Every completed-prefix and mid-operation failure returns exact
      landed and primitive-partial evidence plus still-usable restoration
      authority; serialization failure after mutation is included.
- [ ] The exact promoted `eb45e…` dynamic-exec incident and exact
      `a66422e6…` duplicate-title layout incident pass native
      prepare → preflight/apply → serialize → project and inverse/authorized
      restore → serialize → rollback-projection flows.
- [ ] Real ComfyUI/LiteGraph—not an object-shaped fake—proves structural and
      layout success, dynamic-exec normalization, post-mutation failure and
      rollback, adapter-only native call stacks, and poisoned forward whole-
      graph replacement. Preserve serialized artifacts, screenshots, call
      records, and before/after/inverse projection digests.

### Atomic contract commands

```sh
node --test \
  tests/browser/layout_operation_v1.test.mjs \
  tests/browser/mutation_materialization_v1.test.mjs \
  tests/browser/intent_graph_adapter.test.mjs \
  tests/browser/canonical_delta.test.mjs \
  tests/browser/graph_projection.test.mjs \
  tests/browser/m1_contracts.test.mjs \
  tests/browser/intent_graph_adapter_ownership_static.test.mjs

python -m pytest \
  tests/test_layout_operation_v1.py \
  tests/test_mutation_materialization_v1.py \
  tests/test_m1_contracts.py \
  tests/test_candidate_transaction_layout_contract.py
```

## Preparatory Family A focused gate

```sh
node --test \
  tests/browser/intent_graph_adapter.test.mjs \
  tests/browser/dynamic_io_smoke.test.mjs \
  tests/browser/graph_projection.test.mjs \
  tests/browser/intent_graph_adapter_ownership_static.test.mjs
```

Focused cases must include the exact `a66422e6…` and `eb45e…` fixtures,
duplicate node/group identities, missing identities, candidate-bound native-ID
aliases, remove/re-add native-ID reuse, named-port ambiguity, duplicate group
titles, converted defaults, reroutes, array/object/Map/Proxy link containers
with multiplicity and opaque fields, dynamic-exec/display nonmutation, every
repair-lease failure point, unknown normalization, unsupported Node 2.0,
nested scope, draw snapshots, repeated capture, and serialize/reload.

## Shared broad regression gate

```sh
node --test \
  tests/browser/ownership_contract.test.mjs \
  tests/browser/frontend_ownership_regression.test.mjs \
  tests/browser/m1_contracts.test.mjs

node --test tests/browser/roundtrip_smoke.test.mjs

python -m pytest \
  tests/test_m1_contracts.py \
  tests/test_candidate_transaction_layout_contract.py

make browser-contracts
git diff --check
```

Record exact test counts and skips. Slice 3 adds no skip and does not waive an
M0/M1 regression. Protected `scorecard.png` and
`docs/plans/vibecomfy-screen-share-recording-brief.md` remain unmodified,
untracked, and outside the diff.

For preparatory Family A, this broad gate does not require
`layout_operation_v1` or `mutation_materialization_v1` tests to exist. Their
absence blocks the atomic cut, not Family A observation acceptance. Atomic
acceptance runs the contract commands above plus this entire regression gate.

## Exit rule

Preparatory Family A passes when its fixture-backed observation APIs and tests
are green, all seven persistent-write rows are truthfully S4 debt, coupled
legacy rows remain truthfully unresolved, all identity/normalization refusals
are typed and observational, the exact promoted incident fixture and
`a66422e6…` survive capture/serialize evidence, and every leased write restores
exact state in `finally`. It does not close S3.

Atomic S3+S4 passes only when both versioned contracts land first, BC#2 is
exact-op and candidate-free, every coupled owner and consumer moves together
without wrappers, all ten operations plus inverse/restoration pass native and
fault proofs, forward whole-graph replacement is deleted, exact incidents pass
real ComfyUI success and rollback, and the ledger/static gates prove one owner
with no unresolved S3/S4 debt outside the adapter.

Do not mark M2 complete. Family A leaves S3/S4 ownership open; the atomic cut
closes S3/S4 only. Slice 5 native incident proof and Slice 6 final ownership
coverage remain open afterward.
