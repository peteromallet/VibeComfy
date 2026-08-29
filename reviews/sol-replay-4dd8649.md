# B13 replay authorization review

Status: **closed**

Base: `4dd8649`.

## Decision

The apply gate compares a complete editable identity:

- every node must have a nonblank, unique UID;
- node-map keys must be valid and agree with each node's declared ID;
- every edge must have four nonblank endpoint fields;
- every edge source and destination node ID must resolve to a retained node UID;
- malformed node/edge containers and unresolved endpoints fail closed as `unverifiable_identity`.

The canonical graph signature contains UID-addressed node class/fields/mode and a sorted edge **multiset**. Duplicate edges remain duplicate records. Runtime link IDs, link ordering, node IDs, layout, and emit furniture are excluded; semantic endpoint/slot changes, additions, and removals remain differences.

The redundant leftover-link waiver helper/branch was removed. The partial `requires_custom_nodes` commit waiver was removed from the Python batch commit path; interpreter-side refusal shaping remains non-authoritative and cannot publish a candidate. A rejected batch therefore cannot publish a partial graph.

## Atomicity evidence

Focused tests cover rejection without revision/history advancement at:

- direct `verify_apply` identity, topology, and multiplicity checks;
- Python `apply_batch` with injected UID-less, dangling, and duplicate-edge candidates;
- typed `apply_ops` with injected UID-less and duplicate-edge candidates;
- `done()` commit boundary after a retained-IR replay failure.

The tests assert `landed_ops == ()`, unchanged workflow/UI state where applicable, unchanged revision, and unchanged history on rejection.

## Emitter semantics evidence

Offline emitter round-trip coverage proves:

- link-ID renumbering is ignored when canonical edges are unchanged;
- an attributed semantic link removal survives emitted link removal and counter materialization;
- decreasing an unrelated `last_link_id` cannot authorize a changed canonical edge; replay rejects it.

No live ComfyUI, network, or push was used.
