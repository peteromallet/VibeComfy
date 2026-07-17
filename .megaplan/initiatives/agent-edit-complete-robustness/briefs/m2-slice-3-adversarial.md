# M2 Slice 3 adversarial pre-mortem

Status: implementation gate for Slice 3. This brief is subordinate to
`m2-native-adapter.md` and `m2-slices-3-4-implementation.md`.

## Root risk model

Slice 3 is an ownership transfer, but many ledger entries called
"normalization" currently combine three different powers:

1. **Interpretation** — deciding identity, field meaning, port identity, or
   semantic equivalence. This remains owned by `projection_registry_v1.js`
   (with `identity_contract_v1.js` only a compatibility facade).
2. **Observation** — acquiring the one live root graph, serializing it,
   enumerating native representations, measuring rendered geometry, and
   returning detached evidence. This moves to the adapter in S3.
3. **Native normalization repair** — a narrow S3 exception when a known,
   fixture-backed native representation cannot otherwise serialize faithfully.
   It must run as a bounded lease: exact affected native state captured first,
   only projection-neutral repair, unconditional restoration in `finally`, and
   typed refusal when reversibility cannot be proved.
4. **Semantic mutation** — applying candidate intent, changing a projected
   value, repairing links by choosing which survive, persistent socket/widget
   rewriting, configure/load orchestration, or layout placement. This is S4
   behavior and must not enter S3 merely because it is named normalization.

The principal failure mode is therefore a faithful relocation of an unsafe
routine. S3 passes only if it decomposes old routines and transfers observation
without transferring mutation or reimplementing registry semantics.

## Concrete traps in the current tree

- **Identity duplication:** `canonicalNodeUid` in both old owners accepts
  `properties.uid`, `node.uid`, and `node.id`; their indexes then fall back to
  `byId` (`comfy_adapter.js` NGA-006/008/017/023 and
  `vibecomfy_roundtrip.js` NGA-042/044/057/059/063/068). The sole accepted
  node identity is `vibecomfy_uid`. The registry's native-ID bridge is legal
  only when a candidate already supplies that UID; it is not a general lookup
  fallback. Numeric slot indexes and labels must likewise not become stable
  port identities.
- **Capture that mutates:** `captureSerializedGraphForAgent()` calls live
  normalization before capture. `normalizeLiveExecNodesForSerialization`
  (NGA-062) reaches live nodes, and `setExecWidgetValue` (NGA-072) rewrites
  widgets, `widgets_values`, and properties. A read path can therefore alter
  the user's graph even if serialization or the request later fails.
- **Socket repair disguised as display/normalization:** `decorateIntentNode`
  (NGA-048) changes socket types and removes inputs/outputs;
  `replaceDynamicExecSlotsFromCandidate` (NGA-067) replaces live socket arrays,
  widgets, and properties from candidate data. Neither is S3 observation.
- **Lossy link sanitation:** `sanitizeSerializedGraphLinks` (NGA-070) drops
  unresolved links, chooses one link per target, rewrites node slot references,
  and reconstructs links from six known fields. Unknown link fields and
  representational distinctions are lost. `ensureLiveGraphLinkStore` (NGA-050)
  can replace a native `Map`/Proxy/class-instance store with plain objects.
  Enumeration must not be implemented by repair.
- **Mutation hook installation:** `installGraphConfigureIntentFallback`
  (NGA-078) replaces `graph.configure`, mutates its incoming graph, repairs live
  nodes, and calls panel scope orchestration. The brief lists this row in S3
  but orders deletion of the named fallback in S4. That is a boundary hazard:
  S3 may privately preserve already-issued identities across a native
  configure cycle, but must not relocate this body verbatim, call panel code,
  install an unbounded ambient repair hook, or turn candidate data into repair
  authority. If no bounded post-configure adapter mechanism satisfies both
  requirements, stop and resolve the brief rather than guessing.
- **Layout smuggling:** `applyRenderedNodeSizesToSerializedGraph` (NGA-040)
  locates by native ID and writes measured sizes into serialized graph data.
  S3 may return a separate measured-evidence channel keyed by stable UID; it
  may not silently change the captured layout or candidate mutation intent.
- **Factory leakage:** factory resolution (NGA-024) is capability observation
  in S3. Constructing/configuring a node, invoking lifecycle callbacks, or
  returning the factory/native node is S4.
- **Serialization side effects:** `graph.serialize()`, node/group `serialize`,
  getters, Proxies, and custom callbacks can themselves mutate or throw. S3
  cannot promise zero native writes if it invokes uncontrolled repair around
  them. It must bound the call, capture failure, and prove no adapter-authored
  writes; unsupported representations fail closed.
- **Stale private caches:** a closure-private UID→native-node cache is still
  unsafe if it outlives one operation. Remove/re-add can reuse a native ID for
  a different UID. Rebuild per call or bind the cache to a proven revision.
- **Capability back door:** the accepted adapter still advertises
  `legacy_whole_graph_replace`, `graph_apply`, and the harness-only
  serialize/configure fallback. S3 may report these capabilities, but no S3
  identity or normalization path may depend on or invoke them.

## Non-negotiable S3 acceptance invariants

1. `projection_registry_v1.js` remains the single owner of stable identity,
   field categories, ordering, projections, and equivalence. Adapter code calls
   those exports; it contains no locally equivalent UID/group/link rules.
2. Every public S3 operation is observational at its boundary. Adapter-authored
   live writes are forbidden except inside an explicit native-normalization
   lease with exact before-state, fixture-backed capability, projection-neutral
   proof, and unconditional restoration on success, throw, cancellation, and
   serialization failure. Configure/load, candidate-driven repair, factory
   construction, graph revision, repaint, and persistent writes are forbidden.
3. The adapter never returns a live graph/node/link/group/widget/socket,
   factory, callback, Proxy, Map, or class instance. Results are recursively
   frozen detached plain evidence.
4. Missing stable node/group identity returns `missing_identity`. No title,
   position, array order, class, native node ID, or numeric port fallback.
   Duplicate titles and duplicate-looking geometry remain distinct.
5. Native node IDs are closure-private, operation-local aliases only for an
   explicit candidate UID under the registry-owned translation rule. They are
   never cached as durable identity or returned.
6. Normalization is a declared, versioned, fixture-backed projection from a
   captured representation to detached evidence. It is deterministic and
   idempotent and cannot change a registry-projected value to force a hash.
7. Unknown node families or native forms are accepted only with a registry
   proof that the handling is projection-neutral; otherwise return
   `unsupported_normalization` without repair.
8. Link enumeration preserves cardinality, link IDs, both endpoints, port
   names/types/order, and opaque serialized fields. Map, Proxy-Map, object, and
   array inputs may yield one canonical evidence view but must not rewrite the
   source or silently deduplicate/drop malformed records; unsupported or
   internally inconsistent records produce a typed refusal.
9. Dynamic exec capture preserves source, `io`, widgets, converted widgets,
   all socket records, link references, and opaque properties. It cannot derive
   missing semantic state from display labels and persist it. A temporary
   serialization repair must restore every socket/widget/property/link
   back-pointer exactly; any persistent repair requires S4 prepared authority
   and inverse/restoration evidence.
10. Render measurement is optional evidence keyed by stable UID and separate
    from authoritative serialized geometry. It cannot change capture,
    candidate, layout operation, or projection meaning.
11. Nested scope, Node 2.0, and unsupported representations refuse before any
    adapter-authored repair. No compatibility fallback widens support.
12. Old S3 implementations are deleted, not wrapped, aliased, re-exported, or
    retained behind callbacks. The 78-row ledger and static scanner must prove
    one active native observation owner and one semantic owner.

## S3/S4 boundary

S3 may acquire the unique root graph; inspect capabilities; call bounded native
serialization; enumerate native nodes, groups, and links privately; translate
only through registry-owned stable identity; compute detached normalized
evidence; capture detached draw/measurement snapshots; and perform a narrowly
bounded, reversible, projection-neutral serialization repair for an explicitly
supported native representation.

S4 begins at the first persistent or semantic live write or lifecycle effect:
candidate-driven socket/widget repair, link-store repair that selects or drops
links, property/default hydration, node/group construction or configure,
geometry assignment, add/remove/connect/removeLink, revision/repaint tied to
mutation, inverse execution, and authorized restore.
Candidate data is never S3 repair authority. No S3 API should accept a full
candidate graph except the narrow registry-owned candidate-bound identity
translation input, and that input must not escape into normalization rules.

## Adversarial test matrix

| Case | Required proof |
| --- | --- |
| Exact `eb45e_dynamic_exec_v1` | capture is projection-correct and byte-preserves unrelated serialized fields; any leased writes are allowlisted and exact live state is restored |
| Exact `a66422e6_layout_regression` | stable node/group IDs survive capture; duplicate titles remain distinct; measurements are separate |
| Missing UID plus matching native ID | `missing_identity`; no lookup, repair, or returned alias |
| Duplicate native IDs/titles/positions/types | no collision or fallback resolution |
| Array/object/Map/Proxy-Map links with opaque keys | equal evidence, original container untouched, no dropped/deduped links |
| Dynamic sockets, converted widgets, trailing pool slots | exact order and link refs preserved; no persistent write, candidate import, or unleased removal/splice/property write |
| Throwing getter/serialize/custom callback | typed bounded failure, no live object leakage, no adapter-authored writes |
| Node 2.0/nested/unknown family | `unsupported_normalization` or `unsupported_scope` before repair |
| Repeated capture | identical evidence and unchanged live serialization/revision after each call |
| Failure inside each normalization primitive | `finally` restores exact sockets/widgets/properties/links; typed diagnostic; zero revision/repaint |
| Remove/re-add with reused native ID | operation-local index does not resolve the stale node or wrong UID |
| Consumer misuse | deep-freeze/native-reference tests prevent mutation through adapter results |
| Ownership scan | catches aliases, computed/destructured/optional/transitive calls, callbacks, monkey patches, and old wrappers |

## Stop conditions discovered by the pre-mortem

- `tests/fixtures/agent_edit/eb45e_dynamic_exec_v1.json` is currently absent.
  The authoritative brief requires reconstruction from the real incident, not
  a simplified graph. S3 cannot be accepted until it exists and drives both
  success and failure-path normalization tests.
- The S4 prerequisite owners `layout_operation_v1` and
  `mutation_materialization_v1` are not present yet. S3 must not compensate by
  importing candidate-driven placement, materialization, inverse, or restore.
- NGA-078's S3 migration instruction and S4 deletion instruction need an
  implementation that preserves existing stable IDs without retaining its
  ambient configure/panel mutation body. If that cannot be expressed within
  the normalization-lease contract, treat it as a contract blocker.

The checkpoint is not green merely because projections match. It is green only
when matching evidence is produced without an undeclared live transition and
without a second identity or normalization interpretation.
