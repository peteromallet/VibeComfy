# Native Normalization Ledger — NON-AUTHORITATIVE DERIVED VIEW

This document is explanatory only. The sole machine authority is
`tests/fixtures/agent_edit/native_authority_ledger_v1.json`.

The machine ledger assigns every detected production native-access tuple to
exactly one stable `NGA-*` row. Each row records its source region, exact access
counts, purpose, semantic owner, target API, migration slice,
projection/identity effect, normalization category, concrete test or fixture
proof, and support status. The browser ownership contract validates that schema
and fails on unmatched source access, duplicate mappings, count drift, stale
rows, unknown enum values, placeholder metadata, and unknown keys.

The checked-in scanner deliberately uses only Node built-ins so fresh CI does
not depend on an incidental parser installation. It is conservative: it scans
all production `web/*.js`, tracks direct and computed graph acquisition,
destructuring, and chained local aliases to a fixed point, and inventories
native graph operations, group construction/configuration, dynamic
socket/widget rebuild, stable-identity and normalization helpers, plus relevant
canvas invalidation/draw access.

Open support statuses in the JSON authority identify the remaining migration
work:

- `migration_debt`: intentional S3/S4 access awaiting adapter ownership.
- `blocking_migration`: layout/group behavior that cannot be supported until
  the versioned layout operation contract is implemented.
- `supported_adapter_owner`, `permitted_canvas`, `permitted_harness`, and
  `projection_only`: reviewed access that is already in its declared owner.

## S3/S4 mutation boundary (corrected authoritative classification)

This is **preparatory observational work, not S3 closure**. Slice 3 is atomic
with Slice 4 because the live-normalization bridge that the S4 mutation rows
implement is the only thing that can faithfully move some detached evidence
back onto the live graph. No partial S3 "complete" claim is made here.

Slice 3 transfers only detached, frozen, observational evidence. Native
helpers that write live state are S4 mutation/harness behavior and are NOT
moved into the S3 adapter even where they were historically filed under S3
"normalization". The machine authority now classifies these seven rows as
`S4` (still `migration_debt`, awaiting Slice 4 ownership), with purpose text
that states the mutation reason:

- `NGA-048` `decorateIntentNode` — removes/rebuilds live sockets.
- `NGA-050` `ensureLiveGraphLinkStore` — replaces the native `graph.links`
  store with plain objects.
- `NGA-062` `normalizeLiveExecNodesForSerialization` — writes live exec
  widgets, `widgets_values`, and `properties.vibecomfy` before serialization.
- `NGA-067` `replaceDynamicExecSlotsFromCandidate` — overwrites live exec
  sockets/widgets/properties from candidate data.
- `NGA-070` `sanitizeSerializedGraphLinks` — rewrites `graph.links`,
  `node.inputs[].link`, and `node.outputs[].links` in place to dedupe and
  drop orphaned entries.
- `NGA-072` `setExecWidgetValue` — overwrites `widget.value`,
  `widgets_values` array slots, and converted-io entries in place.
- `NGA-078` `installGraphConfigureIntentFallback` — monkey-patches
  `graph.configure`, mutates the incoming graph, repairs live nodes, and
  calls panel orchestration.

The adapter's S3 capture path (`captureNormalized`, `captureDrawSnapshot`)
performs zero live writes, delegates stable identity validity and projection
to `projection_registry_v1.js`, returns `missing_identity` for any node/group
lacking a stable identity (in `captureDrawSnapshot`), returns
`ambiguous_identity` for duplicate stable node/group IDs (in
`captureDrawSnapshot`), never exposes native ids in its public output, and
attaches only a minimal contract/version evidence tag to the detached
serialized graph. The adapter does not derive semantic exec io/widget
descriptors and does not self-attest a live-write count it cannot prove;
semantic normalization authority and the live-normalization lease stay with
`projection_registry_v1.js` and the S4 mutation bridge. A public
`captureIdentityIndex({candidate})` candidate-graph surface is intentionally
absent: it is not production-ready for the atomic cutover, and its private
identity internals were removed rather than shipped as dead duplicate
authority.

The former hand-maintained numbered table and its 56-row summary were removed
because they duplicated and could drift from the machine authority.
