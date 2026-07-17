# M2 Slices 3–4 — authoritative implementation brief

Work in `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

This is a bounded implementation brief for the **coupled M2 Slice 3 and Slice
4 closure only**. A preparatory observation-only S3 Family A may land first,
but it does not close S3 ownership.

Recorded substate (2026-07-17): Family-A preparation is accepted. S3 remains
open, the coupled ownership transfer is 0/27, and the versioned contracts plus
atomic S3+S4 consumer/deletion/ledger cut below remain pending.

Do not begin until the commit curator has sealed the accepted S1–S2 tree. At
start, re-read the committed versions of:

- `.megaplan/initiatives/agent-edit-complete-robustness/briefs/m2-native-adapter.md`
  — authoritative when this brief conflicts;
- `.megaplan/initiatives/agent-edit-complete-robustness/briefs/m2-adapter-authority-review.md`;
- `tests/fixtures/agent_edit/native_authority_ledger_v1.json`;
- `vibecomfy/comfy_nodes/web/intent_graph_adapter.js`;
- `vibecomfy/comfy_nodes/web/native_normalization_ledger.md`.

Do not implement M3 verification ownership, M4 controller extraction, the M5
recovery product, nested/subgraph support, or a general third-party-node
compatibility layer. Do not commit. Preserve `scorecard.png` and
`docs/plans/vibecomfy-screen-share-recording-brief.md`.

## Required end state

`intent_graph_adapter.js` becomes the sole Agent Edit owner of live
ComfyUI/LiteGraph graph mechanics in one atomic S3+S4 ownership cut. Stable
identity/index/link mechanics cannot move truthfully while old S4
preflight/delta/layout/apply/inverse consumers still require private live
objects. The only independently landable S3 work is observation-only Family A
described below.

The result is an ownership transfer, not a wrapper:

- callers receive frozen plain evidence and typed diagnostics, never live
  graph/node/link/group objects;
- `projection_registry_v1.js` remains the projection, field-meaning, stable
  identity validity, ordering, and hash owner;
- `canonical_delta.js` remains the exact six-op structural grammar owner;
- prepared/restoration authority remains owned by
  `prepared_authority_v1.js`, its Python mirror, and durable authority code;
- the adapter records native execution evidence but does not declare semantic
  success; M3 will own comparison and verdicts;
- forward Apply never reaches `loadGraphData`, `graph.clear`, generic
  `graph.configure`, or raw whole-graph replacement;
- preview, Apply, rollback, compensation, and replay do not retain separate
  native mutation implementations.

## GLM-validated atomic boundary

There is no compliant public API that lets an old S4 module consume an
adapter-private live node/index/link/factory without exposing a live object,
installing a callback lease, retaining a wrapper, or copying ownership. All of
those violate the locked adapter boundary. Therefore:

- Family A may add fixture-backed detached observation, normalized evidence,
  draw/measurement capture, failure diagnostics, and strict reversible
  serialization-repair tests without claiming legacy ownership transfer.
- The physical deletion and ledger transfer of the stable identity, native
  index, endpoint/link, widget-field, and factory helpers is atomically coupled
  to moving every preflight, delta/layout Apply, inverse, and restoration
  consumer that uses them.
- A green preparatory Family A checkpoint is not “S3 complete,” does not make
  the adapter the sole native owner, and cannot relabel old rows as supported
  adapter ownership.
- Wrappers, re-exports, callbacks exposing live objects, public live lookup
  methods, and “temporary” copied helpers are forbidden at both checkpoints.

## Contract work that must land before native mutation moves

### 1. Resolve BC#1 with `layout_operation_v1`

Create cross-language, versioned layout grammar owners:

- `vibecomfy/comfy_nodes/web/layout_operation_v1.js`;
- `vibecomfy/comfy_nodes/agent/layout_operation_v1.py`;
- `tests/fixtures/agent_edit/layout_operation_golden_v1.json`;
- `tests/browser/layout_operation_v1.test.mjs`;
- `tests/test_layout_operation_v1.py`.

Freeze contract name `layout_operation_v1`, wire version `1.0.0`, a closed
envelope, and exactly these root-scoped operations:

1. `set_node_geometry`: stable node `uid`, exact `pos`, exact `size` when size
   changes;
2. `add_group`: stable group `id` plus exact `bounding`, `title`, and `color`;
3. `set_group_geometry`: stable group `id` plus exact changed values from the
   same closed group field set;
4. `remove_group`: stable group `id`.

No operation may identify a node/group by title, native ID, position, class,
array index, or candidate order. Duplicate titles are valid. Reject unknown
versions/keys/ops, missing IDs, non-finite geometry, non-root scope, nested
definitions, and structural fields before native acquisition or mutation.

Update both authority mirrors:

- `vibecomfy/comfy_nodes/web/prepared_authority_v1.js`;
- `vibecomfy/comfy_nodes/agent/projection_registry_v1.py`;
- `vibecomfy/comfy_nodes/agent/candidate_transaction.py`;
- `tests/browser/m1_contracts.test.mjs`;
- `tests/test_m1_contracts.py`;
- `tests/test_candidate_transaction_layout_contract.py`.

For `operation_family: "layout"`, candidate/prepared authority must carry an
exact `layout_operation` envelope and digest, keep structural `delta_v1` ops
empty, bind the existing `layout_v1` pre/post references, and require the
existing structural pre==post witness. Candidate→prepared transition must
prove the layout envelope and digest are unchanged. The full candidate graph
is preview evidence only and is never layout mutation intent.

Do not confuse this operation grammar with
`layout_verification_contract.js`; that contract describes browser-verifiable
evidence, not mutation instructions.

### 2. Resolve BC#2 with bound materialization and restoration

Create the closed cross-language materialization contract and its golden
proofs in exactly these files:

- `vibecomfy/comfy_nodes/web/mutation_materialization_v1.js`;
- `vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py`;
- `tests/fixtures/agent_edit/mutation_materialization_golden_v1.json`;
- `tests/browser/mutation_materialization_v1.test.mjs`;
- `tests/test_mutation_materialization_v1.py`.

The contract freezes `mutation_materialization_v1`, wire version `1.0.0`, and
is consumed by the existing JS/Python prepared-authority owners rather than
becoming a second authority owner. It binds only data the six canonical ops
cannot carry directly:

- `add_node` source-op index → exact native construction payload, including
  stable UID, node type/class, allowed initial fields/widgets/geometry, and
  opaque extension-owned values;
- inverse `remove_node` → exact re-add payload;
- no implicit candidate links: every link is an explicit canonical
  `upsert_link` operation.

The materialization payload is canonicalized, digested, stored in candidate
authority, and immutable across prepare. Reject unreferenced entries, duplicate
source-op indexes, UID/class mismatches, extra keys, or digest mismatch.

Structural preflight must take validated prepared authority only. It executes:

- `set_node_field` from exact `op.value`;
- `set_mode` from exact `op.mode`;
- link operations from exact named `op.from`/`op.to` identities;
- node add/remove from the op plus its bound materialization entry.

Delete every read of `candidateGraph` as a source of field, mode, node, link,
or layout intent. Do not accept `candidateGraph` in public preflight/apply APIs.

Before the first native write, prepared authority must also bind one exact,
digested restoration strategy:

- `inverse_delta_v1` containing strict canonical inverse ops plus required
  materialization; or
- `inverse_layout_operation_v1` containing strict layout inverse ops; and
- optionally `baseline_snapshot_v1` as compensation-only authority, with root
  scope, original snapshot digest/ref, and identity/projection fence.

Inverse values come from the authoritative pre-apply capture: old field/mode,
old named link endpoints, removed-node payload and links, old geometry, and old
group payload. Never clone a forward `set_node_field` or `set_mode` as its own
inverse. Browser-generated inverse evidence must byte-match the already-bound
strategy or preflight refuses before mutation.

## Preparatory S3 Family A — observation only

Family A may land and remain green before the atomic cut. It prepares evidence
and tests; it does not transfer the coupled legacy owners or close S3.

### Files and transfer order

1. Extend focused tests first:
   `tests/browser/intent_graph_adapter.test.mjs`,
   `tests/browser/dynamic_io_smoke.test.mjs`,
   `tests/browser/graph_projection.test.mjs`, and
   `tests/browser/intent_graph_adapter_ownership_static.test.mjs`.
2. Add an exact durable dynamic-exec incident fixture at
   `tests/fixtures/agent_edit/eb45e_dynamic_exec_v1.json`, reconstructed from
   the recorded incident artifacts, not a simplified hand-written graph.
3. Add only additive adapter-owned observation that does not require an old
   S4 consumer to receive a live node/index/link/factory: detached normalized
   capture, draw snapshots, stable-UID-keyed measurements, lossless native
   representation evidence, and bounded typed refusal.
4. Add the strict synchronous serialization-repair lease only when a concrete
   fixture proves it is necessary: exact before-state, projection-neutral
   allowlist, and unconditional restoration in `finally` on every success,
   throw, cancellation, serialization, and clone failure.
5. Route only consumers that can accept frozen plain evidence without a
   compatibility wrapper. Leave coupled legacy consumers and their private
   helpers together until the atomic S3+S4 cut.
6. Keep `native_authority_ledger_v1.json` source-truthful. New Family A access
   is classified, but no legacy identity/index/link row is marked transferred
   merely because a parallel observational API now exists. Do not weaken the
   scanner/schema or claim sole ownership.

### Adapter behavior and API

Family A keeps any observation-local resolver closure-private and operation
local. It does not export stable UID→live node, named endpoint→native slot,
group→live group, link-store, or factory methods for old S4 consumers. Native
IDs may be used only as candidate-bound aliases during one operation; they
never become returned identity or fallback authority.

Extend the existing typed adapter envelope additively with:

- normalized capture options on `capture()`, including declared
  `native_normalization_v1` and optional rendered measurements;
- `captureDrawSnapshot()` returning frozen plain draw geometry/widgets for
  overlays, with no live nodes;
- normalized serialization evidence designed for later S4 use.

Do not publish live lookup/index/factory methods. Public normalization results
contain frozen serialized graph/evidence only.

The adapter may repair native representation only inside the strict temporary
lease so LiteGraph can serialize. It must restore exact live state before
return and must not change a projected value to make a digest match. The
registry alone decides semantic equivalence.

### S3 invariants and cases

- Missing stable node or group identity returns `missing_identity`; no native
  ID/title/position/index/class fallback.
- Existing registry-owned candidate-bound native-ID translation may only
  locate an explicit candidate UID and must never admit a candidate lacking a
  UID. Add a regression test rather than copying this rule into the adapter.
- `vibecomfy.exec` dynamic `io`, sockets, widgets, and converted widgets
  normalize without false `structural_v1` drift.
- Reroutes and named-port aliases preserve stable link identity.
- Stable group IDs survive configure/serialize; duplicate titles remain
  distinct in `layout_v1`.
- Opaque extension values survive Family A capture/serialize/reload and remain
  excluded only when the registry declares them non-semantic; atomic Apply
  later proves the same preservation across mutation.
- Unknown node-family normalization is either projection-neutral by registry
  proof or returns `unsupported_normalization`; callers never invent a rule.
- Nested scope and Node 2.0/unsupported representations refuse before repair.

The preparatory checkpoint tests must include the exact `a66422e6_layout_regression.json`,
the new `eb45e_dynamic_exec_v1.json`, duplicate-title groups, missing identity,
converted defaults, reroute links, opaque properties, and serialize/reload.

At this checkpoint the corrected persistent-write rows NGA-048, NGA-050,
NGA-062, NGA-067, NGA-070, NGA-072, and NGA-078 are S4 debt. The remaining
legacy identity/index/link rows also stay with their S4 consumers until the
atomic cut. Family A acceptance never requires or permits an impossible
standalone 27-row transfer.

## Atomic S3+S4 ownership cut

Do not begin the physical coupled move until both versioned contract sections
above are implemented and green. Then move the following families together:

| Coupled family | Legacy rows | Consumers that force the atomic move |
| --- | --- | --- |
| Stable identity, live indexes, endpoint and field resolution | `NGA-006`, `008`, `011`, `017`, `023`, `042`, `044`–`045`, `055`, `057`, `059`, `063`–`064`, `068`, `074` | strict preflight, exact field/mode reads, node/link execution, inverse construction, preview/highlight consumers |
| Native link shape, enumeration and lookup | `NGA-012`–`014`, `046`, `051`, `060`, `065` | link preconditions, upsert/remove, inverse link evidence, preview diff |
| Observation/normalization/factory mechanics used by mutation | `NGA-024`, `040`, `047`, `054`, `061` | native construction capability, measurements, detached serialization, dynamic evidence |
| Persistent/semantic write debt | `NGA-048`, `050`, `062`, `067`, `070`, `072`, `078` | socket/widget/link repair and configure hooks that must move, be redesigned, or be deleted with S4 |

The first three table rows are the corrected 27-row coupled set. The fourth is
S4 debt. No row in any family can be declared closed through a wrapper or a
parallel copied helper.

1. Stable UID/group identity, live indexes, named endpoints/ports, link-store
   enumeration, widget-field reads, factory capability, and operation-local
   candidate-bound aliases.
2. Prepared precondition reads and strict preflight for all exact canonical
   operations, with no public or private `candidateGraph` mutation-intent
   parameter.
3. Native execution for all six `delta_v1` operations and all four
   `layout_operation_v1` operations.
4. Bound inverse construction/validation, reverse-causal inverse execution,
   and explicitly authorized compensation restoration.
5. Every preview/Apply/rollback/Undo/recovery/replay consumer that otherwise
   needs one of those private native mechanics.

Only this atomic cut deletes the old helpers, transfers their ledger rows,
and closes native ownership. Delete rather than wrap; after the cut, old
modules may orchestrate only with frozen adapter envelopes.

## Slice 4 — canonical mutation, layout, inverse, restoration

Slice 4 is also the closure point for the coupled S3 identity/index/link
families. It is not accepted as a façade over old helpers.

### Public adapter operations

Add typed methods that all validate root scope, contract versions, prepared
authority, identity fence, capabilities, and complete preflight before writing:

- `preflightPrepared(preparedAuthority)` → frozen plan plus bound inverse and
  zero writes;
- `applyCanonicalDelta(preparedAuthority, options)`;
- `applyLayoutOperation(preparedAuthority, options)`;
- `applyInverse(restorationAuthority, options)`;
- `restoreAuthorized(restorationAuthority, authorizedSnapshot, options)`.

Success/failure envelopes extend the accepted S1–S2 shape and include:
`operation`, `scope`, `before`, `after`, `landed`, `failed_at`,
`partial_operation`, `restoration`, and bounded `diagnostic`. They never return
the graph or native objects. Evidence records what happened; it does not claim
the prepared postcondition passed.

### Native transfer order

1. Move pure strict preflight into the adapter, consuming prepared authority
   and its materialization/restoration payloads. Remove
   `comfy_adapter.preflightDeltaPlan` and all candidate consistency reads.
   Public and private preflight/apply APIs do not accept `candidateGraph`;
   `set_node_field` uses exact `op.value`, `set_mode` exact `op.mode`, links
   exact named `op.from`/`op.to`, and add/remove exact digested
   `mutation_materialization_v1` entries.
2. Move stable live execution for all six structural ops:
   `set_node_field`, `set_mode`, `add_node`, `upsert_link`, `remove_node`, and
   `remove_link`. Use native factory/add/connect/removeLink/remove primitives;
   preserve unrelated nodes, links, fields, geometry, groups, and opaque data.
3. Move versioned layout execution: node geometry and group add/update/remove
   by stable IDs. No post-prepare collision placement, title matching, or
   candidate-driven “replace all groups” operation.
4. Move inverse execution in reverse causal order and authorized snapshot
   compensation into the adapter.
5. Route Apply/rollback/Undo/recovery orchestration in
   `vibecomfy_roundtrip.js`; preview in `preview_picker.js`; and replay in
   `agentic_replay.js` through those public methods. Orchestration may remain,
   native mechanics may not.
6. Delete from old owners, rather than wrap:
   `applyGraphCandidateInPlace`, `preflightDeltaPlan`,
   `applyGraphDeltaInPlace`, `applyGraphLayoutInPlace`, live link map helpers,
   group construction/configuration, `buildInverseDeltaOps`,
   `attemptScopedCanvasRollback`, `restoreCandidateLinksOnLiveGraph`,
   `loadGraphDataWithoutScopeSwitch`, `undoLastApply`,
   `installIntentNodeFallback`, and `installGraphConfigureIntentFallback`.
7. Remove production `HARNESS_DELTA_APPLY_FALLBACK_MARKER`,
   `harness-serialize-configure`, `legacy_whole_graph_replace`, and forward
   graph-apply capability. A faithful test harness must implement native
   operations; production cannot carry a test-only clear/configure escape.
8. Refresh the 78-row machine ledger and target catalog. At S4 exit there are
   no S3/S4 `migration_debt` or `blocking_migration` rows outside the adapter;
   compensation-only whole-graph primitives, if any, are adapter-owned and
   explicitly classified as authorized restoration.

### Atomicity, landed evidence, and injected faults

Build the full plan and inverse/restoration proof before the first write. For
each source op, record native primitive writes. Append to `landed` only after
that source op completes. If a multi-write op fails mid-operation, return:

- the exact completed source-op prefix;
- `partial_operation` with primitive writes already made;
- before/after serialized evidence when serialization remains available;
- the failed source index/kind and bounded native diagnostic;
- restoration authority valid for both the landed prefix and partial writes.

Add deterministic failure injection to `tests/browser/harness.mjs` at every
native primitive boundary: factory, configure-new-node, add/remove node,
connect, removeLink, widget/mode assignment, socket repair, group construct,
group configure/add/remove, geometry assignment, repaint, and serialize.
Test failure before the first write, after every complete prefix, inside each
multi-write operation, and on serialization after mutation. Preflight/version/
scope/identity/capability failures must prove zero primitive calls.

### Required structural and layout cases

For every six-op structural kind and every four-op layout kind, test:

1. unknown-version and malformed refusal;
2. missing identity/capability/precondition refusal with zero writes;
3. success through native serialize and declared projection;
4. unrelated-state preservation;
5. primitive-boundary partial failure evidence;
6. inverse in reverse causal order;
7. serialized rollback projection equal to the original declared projection.

Also test one dependency chain:
`add_node → add_node → upsert_link → set_node_field → set_mode → remove_link → remove_node`,
with every prefix faulted. Layout must cover movement-only structural no-op,
group add/update/remove, duplicate titles, and exact `a66422e6…` geometry.

Snapshot restoration tests require valid root-scoped
`baseline_snapshot_v1`, exact digest/ref and identity fence. Missing, stale,
wrong-scope, wrong-projection, or tampered authority returns
`unauthorized_restoration` without loading/configuring. An authorized snapshot
may use whole-graph loading only inside `restoreAuthorized`, only after a
mutation failure, and must expose evidence for later M3 verification.

## Atomic S3+S4 acceptance order

Acceptance is all-or-nothing in this order:

1. `layout_operation_v1` JS/Python owners, golden corpus, prepared-authority
   binding, digest stability, root-only refusals, and four-op tests are green.
2. `mutation_materialization_v1` JS/Python owners, golden corpus, exact source
   op binding, digest stability, inverse materialization, and tamper/extra/
   duplicate/unreferenced-entry refusals are green.
3. BC#2 proves candidate-free execution: no preflight/apply/inverse code reads
   a candidate graph for field, mode, node, link, geometry, group, or inverse
   intent, and no public adapter mutation API accepts one.
4. The coupled identity/index/link/factory consumers and all structural/layout
   preflight/apply/inverse/restoration mechanics move behind the adapter in one
   change; old definitions, imports, exports, wrappers, aliases, and copies
   disappear together.
5. All six exact structural ops and all four exact layout ops preflight before
   the first write, serialize natively, preserve unrelated/opaque state, and
   emit stable landed/partial evidence without declaring the M3 verdict.
6. Exact, digested inverse/restoration authority exists before mutation;
   inverse executes in reverse causal order and authorized snapshot loading is
   compensation-only.
7. Forward whole-graph replacement is deleted: production has no forward
   `loadGraphData`, `graph.clear/configure`,
   `HARNESS_DELTA_APPLY_FALLBACK_MARKER`, `harness-serialize-configure`,
   `legacy_whole_graph_replace`, or graph-apply capability escape hatch.
8. Deterministic faults at every primitive boundary and every completed prefix
   prove zero writes before preflight success and exact recoverable evidence
   after partial writes, including serialization failure.
9. The exact `a66422e6…` and promoted `eb45e…` incidents pass both focused
   native tests and the real ComfyUI/LiteGraph flows below, including rollback.
10. The ledger/static gates prove one native owner and no S3/S4 debt outside
    the adapter; the full browser/M1/M0 regression matrix has no new skip.

## Real ComfyUI/LiteGraph proof

Fake browser tests are necessary but insufficient. Add or extend:

- `tests/e2e/specs/intent_graph_adapter_native.spec.mjs` (new);
- `tests/e2e/specs/test_dynamic_exec_refresh.spec.mjs`;
- `tests/e2e/specs/agent_panel_reorganise.spec.mjs`;
- `tests/e2e/helpers/canvas-debug-probes.mjs` only for read-only evidence and
  bounded call recording.

Against a real running ComfyUI frontend and `window.app.canvas.graph`, prove:

1. prepare → public adapter Apply → real LiteGraph serialize → projection →
   finalize for a structural multi-op transaction;
2. the same flow for `a66422e6…` layout operations with duplicate group titles
   and stable IDs;
3. real dynamic `vibecomfy.exec` socket/widget normalization using `eb45e…`;
4. forced post-mutation failure → public adapter inverse/authorized restore →
   real serialize → rollback projection;
5. native call recording shows the adapter boundary on every graph mutation;
6. poisoning `clear`, generic `configure`, and `loadGraphData` during forward
   Apply does not break structural or layout success.

Record browser screenshots/serialized artifacts plus before/after/inverse
projection digests. Do not count an object-shaped fake as “real LiteGraph.”

## Ownership exit gates

Extend `tests/browser/intent_graph_adapter_ownership_static.test.mjs`,
`tests/browser/ownership_contract.test.mjs`, and
`tests/browser/frontend_ownership_regression.test.mjs` so they fail on:

- native graph acquisition, `_nodes`, `_groups`, live link stores,
  serialization, factories, add/remove/connect/removeLink/configure, dynamic
  repair, or native identity lookup outside `intent_graph_adapter.js`;
- old graph exports/definitions in `comfy_adapter.js`;
- native mutation/restoration in roundtrip, picker, replay, scope, lifecycle,
  projection, or transport modules;
- any consumer identity fallback to native ID/title/position/index/class;
- candidateGraph passed into preflight/apply or used as mutation intent;
- forward `loadGraphData`, clear/configure, or whole-graph replacement;
- a normalization/operation/restoration rule without an active fixture proof;
- public adapter results containing live objects;
- layout/native operation versions reaching mutation before validation.

The scanner must distinguish registry-owned serialized projection reads and
permitted canvas drawing from native graph ownership. `web_dist` is excluded
and cannot satisfy source gates.

S3/S4 ownership is complete only when every old S3/S4 ledger source row is
gone or migrated to the adapter, all replacement rows validate semantically,
and no compatibility wrapper preserves the old implementation.

## Proof commands and acceptance

Run and report exact counts for at least:

```bash
node --test \
  tests/browser/intent_graph_adapter.test.mjs \
  tests/browser/layout_operation_v1.test.mjs \
  tests/browser/mutation_materialization_v1.test.mjs \
  tests/browser/dynamic_io_smoke.test.mjs \
  tests/browser/graph_projection.test.mjs \
  tests/browser/canonical_delta.test.mjs \
  tests/browser/m1_contracts.test.mjs \
  tests/browser/ownership_contract.test.mjs \
  tests/browser/frontend_ownership_regression.test.mjs \
  tests/browser/intent_graph_adapter_ownership_static.test.mjs

node --test tests/browser/roundtrip_smoke.test.mjs

python -m pytest -q \
  tests/test_layout_operation_v1.py \
  tests/test_mutation_materialization_v1.py \
  tests/test_m1_contracts.py \
  tests/test_candidate_transaction_layout_contract.py \
  tests/test_authority_receipts.py

make browser-contracts
make browser-smoke
```

Run the real browser specs through the repository E2E runner against the
actual ComfyUI checkout and record the exact command/environment and artifacts.

Acceptance requires all of the following, with no new skips:

- exact op values, materialization, layout ops, inverse, and restoration are
  bound before mutation;
- all preflight failures make zero native calls;
- every primitive-boundary failure returns actionable exact evidence;
- all structural/layout cases survive real native serialization and inverse;
- `a66422e6…` and `eb45e…` pass through public adapter APIs;
- forward whole-graph tripwires remain uncalled;
- S3/S4 native authority exists only in the adapter;
- M0 incident, M1 cross-language, full browser-contract, roundtrip, and real
  ComfyUI gates are green.

## Stop conditions

Stop rather than improvising if the committed S1–S2 API/ledger differs from
this brief, the exact `eb45e…` artifacts cannot be recovered, real ComfyUI
cannot expose stable group IDs, or candidate/prepared authority cannot bind the
new layout/materialization/restoration payloads without a cross-language
contract update. Those are contract blockers, not reasons to restore
candidateGraph or whole-graph forward fallbacks.
