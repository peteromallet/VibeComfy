# M2 Slices 3–4 atomic-boundary review

Status: proposed implementation gate. Subordinate to
`m2-native-adapter.md` and `m2-slices-3-4-implementation.md`; where the current
ledger or partial implementation contradicts those briefs, stop and reconcile
the authority rather than silently reclassifying rows.

## Decision

An **atomic native-owner cutover across S3 and S4 is justified**, but an atomic
"move everything" rewrite is not. The dependency trace shows that the S3
identity/index/link/factory helpers are private dependencies of S4 preflight,
apply, layout, inverse, and restore. Moving only the helpers either leaves
wrappers back into the old owner or creates two implementations. The smallest
lawful release unit is therefore:

1. land and freeze the missing cross-language intent/restoration contracts;
2. build the adapter's private read + mutation core against those contracts;
3. in one cutover, route every Agent Edit native consumer through the adapter
   and delete the old native implementations, exports, fallbacks, and ledger
   rows.

Contracts and tests can land in earlier green checkpoints. The ownership
cutover itself cannot be split into a released "new adapter plus old wrappers"
state.

## Why S3 alone is not a closed extraction

In `comfy_adapter.js`, `canonicalNodeUid`, `buildGraphIndex`,
`iterateLinkRecords`, `linkShapeForGraph`, `resolveEndpoint`, `resolveFactory`,
`liveNodeIndex`, and `liveLinkEntries` are used directly by candidate-driven
preflight and all six structural mutation implementations. In roundtrip, the
same identity/link/widget helpers feed preview planning, Apply, inverse
construction, rollback, Undo, dynamic-exec repair, and whole-graph fallbacks.

Leaving these callers behind requires one of three illegal designs: export
live lookup/index methods from the adapter; retain compatibility wrappers in
the old owner; or reimplement identity/link semantics twice. The authoritative
brief forbids all three. This is a dependency-cycle problem, not merely a file
size problem.

## Minimal lawful closure

### Move atomically behind `intent_graph_adapter.js`

- The exact 27 S3 observation rows named by current acceptance:
  NGA-006, 008, 011–014, 017, 023–024, 040, 042, 044–047, 051, 054–055,
  057, 059–061, 063–065, 068, and 074.
- The seven formerly misclassified persistent/semantic-write rows:
  NGA-048, 050, 062, 067, 070, 072, and 078, plus every remaining S4
  preflight/delta/layout/inverse/restoration row consumed by this core.
- Unique root graph acquisition, serialization, native representation
  enumeration, rendered measurement, revision/repaint coupled to mutation.
- Closure-private stable UID/group-ID resolution, operation-local native-ID
  aliasing, named endpoint/slot resolution, link enumeration/allocation, and
  node/group factory resolution. Identity validity and field meaning continue
  to delegate to `projection_registry_v1.js`.
- Declared native normalization for dynamic exec sockets/widgets, converted
  widgets, reroutes, link containers, opaque fields, and stable group IDs.
- Strict preflight from validated `prepared_authority_v1` only.
- Native execution of the six `delta_v1` operations and four
  `layout_operation_v1` operations.
- Landed/partial primitive evidence, exact inverse execution, and explicitly
  authorized snapshot compensation.
- Normalized post-mutation serialization and frozen draw snapshots.

### Route in the same cutover

- Roundtrip Apply, rollback, Undo/recovery execution, preview diff inputs, and
  normalized capture.
- `preview_picker.js` and `agentic_replay.js`: retain sequencing/UI state, but
  replace candidate/original whole-graph application with prepared canonical
  forward/inverse or authorized restoration calls.
- `active_canvas_scope_guard.js` and `scope_resolver.js`: consume frozen adapter
  evidence, never a graph reference.
- `panel_overlay.js`: draw only from `captureDrawSnapshot()` evidence.

### Delete in the same cutover

- `comfy_adapter.js` graph apply/preflight/layout/delta implementations and
  every private native identity/link/factory/group helper they depend on.
- Roundtrip native normalization/repair, native resolvers, inverse builder,
  link repair, group/layout mutation, rollback execution, and configure/load
  monkey patches named by the authoritative S4 brief.
- Public/re-exported compatibility facades for those implementations.
- Production whole-graph forward capability, harness serialize/configure
  fallback, and direct candidateGraph mutation intent.

### May remain outside the adapter

Transport, panel lifecycle/state transitions, rendering schedules, user
messages, queue guards, transaction orchestration, and M3 verification verdicts
remain in their existing owners. They may pass versioned authority and frozen
evidence; they may not inspect or mutate native graph objects.

## Contract prerequisites and order

1. **`layout_operation_v1` first:** JS/Python owners, closed `1.0.0` envelope,
   golden corpus, prepared-authority integration, exact digest binding, root
   scope, stable node/group IDs, duplicate-title and nested-scope refusals.
2. **`mutation_materialization_v1` second:** JS/Python owners and goldens;
   exact source-op-index binding for add/re-add payloads and opaque fields; no
   implicit candidate links; immutable candidate→prepared digest.
3. **Restoration binding third:** prepared authority binds exact
   `inverse_delta_v1` plus materialization or
   `inverse_layout_operation_v1`, and optionally root-scoped,
   digest/ref/identity/projection-fenced `baseline_snapshot_v1`. Browser-built
   inverse evidence must byte-match the bound strategy before mutation.
4. **Adapter preflight API fourth:** accept prepared authority, never
   candidateGraph. Validate versions, root scope, projection/identity fence,
   capabilities, materialization, and restoration before the first native
   write.
5. **Native execution fifth:** implement and fault-test each primitive behind
   the adapter while still unreachable from production consumers.
6. **Atomic consumer/deletion/ledger cutover sixth.** Only this checkpoint
   declares S3/S4 native ownership complete.
7. **Real ComfyUI proof seventh:** forward structural and layout flows,
   serialization, inverse/authorized restore, exact incidents, duplicate
   titles, and poisoned forward clear/configure/loadGraphData.

## Review of the current partial S3 diff

The focused adapter tests were green during review, but the evolving diff is
not an ownership-complete S3 checkpoint:

- It adds a second normalization implementation while all old S3/S4 bodies
  remain. At review time, zero of the 27 coupled observation rows had
  transferred; the seven S4 reclassifications are truthful debt labels, not an
  ownership move.
- Public `captureIdentityIndex({candidate})` is detached and has been hardened
  not to return its alias map, but it still expands the public candidate-graph
  surface and cannot serve the coupled live mutation code. At atomic cutover,
  candidate-bound aliasing belongs inside one prepared operation, not in a
  reusable public index API.
- `captureNormalized` still returns `normalization.exec_nodes[].native_id`
  while its own module comment says no native ID is emitted. Public results
  must contain stable IDs/named endpoints only.
- `captureNormalized` manually chooses `properties.vibecomfy.io` versus
  `widgets_values[1]`. That is semantic widget normalization already owned by
  the registry; the imported `normalizeDerivedWidgetFieldsV1` is unused.
- `live_writes: 0` is self-asserted metadata, not observed primitive evidence.
  The test harness serializes a detached JSON store and cannot prove what real
  LiteGraph/custom-node serialization callbacks do.
- The test named "byte-preserves ... incident" constructs only three nodes and
  two links from the 98-node candidate and compares selected descriptor fields;
  it does not byte/canonical-compare the full captured graph or opaque fields.
- The hardened draw snapshot now refuses missing/duplicate identity, but this
  does not close group configure/serialize identity behavior in real ComfyUI.
- The detached normalization covers only exact-type `vibecomfy.exec`. It does
  not close the S3 ledger rows for link shapes, reroutes, groups, measurements,
  aliases, unknown families, Node 2.0, opaque fields, or serialize/reload.
- All seven persistent-write rows are now reclassified S3→S4, matching current
  preparatory acceptance. They remain old-owner debt; the reclassification is
  honest preparation, not transfer or S3 closure.
- Fixture provenance has been hardened with original/candidate/messages/
  response SHA-256 values and response outcome. The untracked builder remains
  local-path-dependent, so durability rests on the committed self-contained
  fixture and deterministic digest assertions, not the path existing later.

## Bounded checkpoints

1. **C0 contracts only:** cross-language goldens and authority transitions;
   no live code changes.
2. **C1 adapter isolated proof:** private internals and faithful fault-injected
   LiteGraph harness tests. Old production path remains active, so this is not
   an ownership-complete release and no duplicate public APIs are introduced.
3. **C2 atomic cutover:** consumers route to adapter; old definitions, imports,
   exports, wrappers, and forward fallbacks deleted; ledger updated in the same
   diff. Ownership static gates must pass here.
4. **C3 integration:** roundtrip/preview/replay/rollback tests plus all
   primitive-prefix failures and unrelated-state preservation.
5. **C4 real ComfyUI:** exact `a66422e6` and `eb45e`, structural/layout Apply,
   serialize/project/finalize, inverse and authorized restoration.

Each checkpoint is independently green and reviewable. C2 may be a large diff,
but its scope is mechanically closed by the ledger rows and consumer list; it
must not absorb M3 verdict ownership, M4 controller extraction, or M5 recovery
product work.

## Stop conditions

Stop rather than add a wrapper or broaden the move if:

- prepared authority cannot bind layout, materialization, inverse, and
  restoration payloads without a cross-language change;
- any public apply/preflight method still needs candidateGraph;
- any consumer still needs a live node/link/group/factory or public lookup;
- lossless Map/Proxy/array/object link handling or stable group IDs cannot be
  proven in real ComfyUI;
- normalization must choose/drop projected data rather than return a typed
  unsupported diagnostic;
- partial primitive failure cannot return exact landed/partial evidence plus a
  usable already-bound restoration strategy;
- preview/replay can work only through raw whole-graph replacement;
- the atomic diff begins moving lifecycle/verifier/recovery-product ownership;
- ownership gates require a broad allowlist or compatibility exception;
- exact incidents pass only in a fake object-shaped graph, not real LiteGraph.

The safe boundary is therefore **contracts first, one atomic native-owner
cutover second, real proof third**. Atomicity is needed to eliminate duplicated
authority, not to excuse an unreviewable migration.
