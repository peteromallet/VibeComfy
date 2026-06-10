# M4 Resolution Context — Divergence Inventory

> **LIVING DOCUMENT** — This file records every known divergence between the
> lint-side and apply-side `_resolve_*` functions as of M4 Step 1. It is
> intentionally incomplete: **Step 10 (the terminal gate) will expand this
> document** when golden-diff audits reveal unlisted divergences. Unexplained
> golden changes are not automatically bugs; they are invitations to add a
> new inventory entry with a justifying note.

---

## (a) Divergence Inventory Table

### edit_lint.py:487–747 — 7 `_resolve_*` functions

| # | Function | Line | Input Ref Type | Backend | LG-id Aliasing | Widget-Field Tolerance | Error Shape | Schema Usage |
|---|----------|------|----------------|---------|----------------|------------------------|-------------|-------------|
| 1 | `_resolve_uid` | 487 | `str` (uid_str) | `LintIndex` | **YES** — `_try_parse_lg_id` → `index.uid_for_lg_id` | N/A | `tuple[str\|None, LintIssue\|None]` | None |
| 2 | `_resolve_node_target` | 531 | `NodeTarget` | `LintIndex` | YES (via `_resolve_uid`) | N/A | `tuple[NodeTarget\|None, LintIssue\|None]` | None |
| 3 | `_resolve_node_field_target` | 550 | `NodeFieldTarget` | `LintIndex` | YES (via `_resolve_uid`) | N/A | `tuple[NodeFieldTarget\|None, LintIssue\|None]` | None |
| 4 | `_resolve_link_source` | 573 | `LinkSourceRef` | `LintIndex` | YES (via `_resolve_uid`) | N/A | `tuple[LinkSourceRef\|None, LintIssue\|None]` | None |
| 5 | `_resolve_link_target` | 596 | `LinkTargetRef` | `LintIndex` | YES (via `_resolve_uid`) | N/A | `tuple[LinkTargetRef\|None, LintIssue\|None]` | None |
| 6 | `_resolve_output_slot_index` | 675 | `str\|int` (output_slot) | `LintIndex` | N/A (slot-level) | N/A — validates `int` by `output_slots.values()` AND positional index | `int\|None` | Only via `_NodeMeta.output_slots`/`.output_names` |
| 7 | `_resolve_input_slot_index` | 709 | `str` (input_field) | `LintIndex` | N/A (slot-level) | **Strict** — `input_names.index()` ValueError → None | `int\|None` | Only via `_NodeMeta.input_names` |

### edit_apply.py:837–1750 + 2496–2572 — 15 `_resolve_*` functions

| # | Function | Line | Input Ref Type | Backend | LG-id Aliasing | Widget-Field Tolerance | Error Shape | Schema Usage |
|---|----------|------|----------------|---------|----------------|------------------------|-------------|-------------|
| 8 | `_resolve_op` | 837 | `EditOp` | `EditLedger` | Depends on dispatchee | N/A | `tuple[ResolvedOp\|None, list[PortIssue]]` | Passed to callees |
| 9 | `_resolve_scope` | 860 | `str` (scope_path) | `EditLedger` | N/A | N/A | `tuple[ScopeState\|None, list[PortIssue]]` | None |
| 10 | `_resolve_node` | 873 | `NodeTarget` | `EditLedger` | **NO** — `ledger.resolve_node()` is a plain `node_index.get()` | N/A | `tuple[ResolvedNodeRef\|None, list[PortIssue]]` | None (class_type from node dict) |
| 11 | `_resolve_node_only` | 902 | `NodeTarget` | `EditLedger` | NO (via `_resolve_node`) | N/A | `tuple[ResolvedOp\|None, list[PortIssue]]` | None |
| 12 | `_resolve_remove_node` | 910 | `NodeTarget` | `EditLedger` | NO (via `_resolve_node`) | N/A | `tuple[ResolvedOp\|None, list[PortIssue]]` | None |
| 13 | `_resolve_set_node_field` | 985 | `SetNodeFieldOp` | `EditLedger` | NO (via `_resolve_node`) | **YES** — widget+input+schema triple resolution with `_widget_index_for_field`, `_widget_name_for_input`, `_widget_index_from_input_stubs`, schema-input existence | `tuple[ResolvedOp\|None, list[PortIssue]]` | YES — `schema_for` for input validation and `_validate_literal_value` |
| 14 | `_resolve_upsert_link` | 1114 | `UpsertLinkOp` | `EditLedger` | NO (via `_resolve_source/target_endpoint` → `_resolve_node`) | Partial — target endpoint uses `_find_named_slot` + schema fallback | `tuple[ResolvedOp\|None, list[PortIssue]]` | YES — `schema_for` for socket-type compatibility |
| 15 | `_resolve_remove_link` | 1174 | `RemoveLinkOp` | `EditLedger` | NO (via `_resolve_node` for target-based path) | N/A | `tuple[ResolvedOp\|None, list[PortIssue]]` | None |
| 16 | `_resolve_add_node` | 1245 | `AddNodeOp` | `EditLedger` | N/A (no node target) | N/A | `tuple[ResolvedOp\|None, list[PortIssue]]` | YES — `schema_for` for class-type and input validation |
| 17 | `_resolve_reorder` | 1404 | `ReorderOp` | `EditLedger` | NO (via `_resolve_node`) | N/A | `tuple[ResolvedOp\|None, list[PortIssue]]` | None |
| 18 | `_resolve_add_node_anchor` | 1472 | `AnchorRef` | `EditLedger` | NO (via `_resolve_node`) | N/A | 5-tuple with `list[PortIssue]` | None |
| 19 | `_resolve_source_endpoint` | 1532 | `LinkSourceRef` | `EditLedger` | NO (via `_resolve_node`) | N/A — output_slot: `int` checked by `len(outputs)`, `str` scanned linearly + schema fallback | `tuple[ResolvedLinkEndpoint\|None, list[PortIssue]]` | YES — `schema_for` for output-name lookup and `_schema_output_type` |
| 20 | `_resolve_target_endpoint` | 1610 | `LinkTargetRef` | `EditLedger` | NO (via `_resolve_node`) | **YES** — `_find_named_slot` returns `dict\|None`, then schema fallback (`schema_input` check); slot_index populated from raw input's position in list | `tuple[ResolvedLinkEndpoint\|None, list[PortIssue]]` | YES — `schema_for` for socket-type extraction |
| 21 | `_resolve_getnode_source` | 2496 | `node:Mapping`, `scope_path:str` | `scope_graph` | **EXCLUDED** (SD3) — traverses `scope_graph['nodes']` by integer LG ID, not uid | N/A | `tuple[tuple[int,int]\|None, list[PortIssue]]` | None |
| 22 | `_resolve_passthrough_source` | 2534 | `node_id:int`, `scope_path:str` | `scope_graph` | **EXCLUDED** (SD3) — traverses `scope_graph['nodes']` by integer LG ID recursively, not uid | N/A | `tuple[tuple[int,int]\|None, list[PortIssue]]` | None |

### Summary grid

| Aspect | lint (edit_lint.py) | apply (edit_apply.py) |
|--------|---------------------|----------------------|
| Backend | `LintIndex` (has `_lg_id_to_uid` reverse-map pre-built) | `EditLedger` (raw `node_index.get()`, no LG-id map) |
| LG-id aliasing | **Yes** — `"42"` → canonical uid | **No** — requires exact uid string |
| Error shape | `LintIssue \| None` (singular) | `list[PortIssue]` (plural) |
| UID resolution return | `str \| None` (just canonical uid) | `ResolvedNodeRef` (full node dict + class_type + node_id) |
| Source endpoint return | `LinkSourceRef` (uid+slot only) | `ResolvedLinkEndpoint` (full node + slot_index + slot_name + socket_type) |
| Target endpoint return | `LinkTargetRef` (uid+input_field only) | `ResolvedLinkEndpoint` (full node + slot_index + slot_name + socket_type) |
| Widget-field tolerance | **None** — lint only resolves uid; field existence checked post-resolution | **Rich** — widget/input/schema triple dispatch |
| Schema usage | None (lint uses pre-built `_NodeMeta`) | Yes (schema_for for type validation, socket compatibility, output-name lookups) |
| Slot index resolution | `_resolve_output_slot_index` / `_resolve_input_slot_index` | Inline in `_resolve_source_endpoint` / `_resolve_target_endpoint` |

---

## (b) Recorded Known Divergences

### D1: LG-id aliasing missing in apply

- **Lint**: `_resolve_uid` (line 505) calls `_try_parse_lg_id(uid_str)`. If the input looks like an integer (e.g., `"42"`), it translates it to a canonical uid via `LintIndex.uid_for_lg_id(scope_path, lg_id)`.
- **Apply**: `_resolve_node` (line 873) calls `ledger.resolve_node(target.scope_path, target.uid)` which is a bare `node_index.get((scope_path, uid))`. No LG-id parsing or aliasing.
- **Impact**: A delta that uses LG integer IDs as uid references (e.g., `{"uid": "42", ...}`) passes lint but fails apply resolution. This is the primary convergence gap that M4 closes.
- **Mitigation in M4**: `EditLedgerBackend` builds the `(scope_path, lg_id) → uid` reverse index so `ResolutionContext.resolve_uid` works identically on both backends.

### D2: LintIssue (singular) vs list[PortIssue] (plural)

- **Lint**: Every `_resolve_*` returns `LintIssue | None` — at most one issue per call.
- **Apply**: Every `_resolve_*` returns `list[PortIssue]` — potentially multiple issues.
- **Impact**: Different error shapes. The `ResolutionContext` returns `list[ResolutionIssue]` (plural, like apply). Adapters `to_lint_issue` and `to_port_issues` bridge the gap.
- **Mitigation in M4**: `ResolveResult[T]` carries `list[ResolutionIssue]`; the shims pick the first issue (lint) or pass the list through (apply).

### D3: Widget vs slot tolerance in `_resolve_target_endpoint`

- **Lint**: `_resolve_input_slot_index` is strict — `input_names.index(input_field)` raises `ValueError` → `None` if the input doesn't exist. No widget/schema fallback.
- **Apply**: `_resolve_target_endpoint` uses `_find_named_slot(raw_inputs, input_field)`. If the raw input slot is missing, it checks `schema_input `— a field can exist in the schema (e.g., as a widget-only input) even if it's not in the node's raw `inputs` list. Returns `None` only when BOTH raw and schema are absent.
- **Impact**: A target input that exists only as a schema-declared widget field (no raw input slot) would be rejected by lint but accepted by apply.
- **Mitigation in M4**: `ResolutionContext.resolve_target_endpoint` follows the apply-side tolerance (schema fallback) so lint convergence is achieved by making lint more permissive.

### D4: `int` vs `str` output_slot in `_resolve_output_slot_index` / `_resolve_source_endpoint`

- **Lint**: `_resolve_output_slot_index` (line 686-695) validates integer output_slot by checking BOTH `output_slots.values()` (a dict mapping name→index) AND positional index against `len(output_names)`.
- **Apply**: `_resolve_source_endpoint` (line 1554-1562) validates integer output_slot by checking `ref.output_slot < 0 or ref.output_slot >= len(outputs)` — a simpler bounds check.
- **Impact**: If `output_slots` dict has gaps (e.g., slot names mapping to non-contiguous indices), the lint path could reject an integer slot that apply would accept (or vice versa).
- **Mitigation in M4**: The unified `resolve_output_slot_index` uses the apply-side logic (bounds check + schema fallback for string names) as the convergence target.

### D5: Output slot name resolution: pre-built `_NodeMeta` vs inline schema lookup

- **Lint**: `_resolve_output_slot_index` uses pre-built `_NodeMeta.output_slots` (dict of name→index) and `output_names` (list).
- **Apply**: `_resolve_source_endpoint` scans the raw `outputs[]` list linearly, then falls back to `schema_for(...).outputs`.
- **Impact**: Minor performance difference; functional equivalence when both have access to the same data.
- **Mitigation in M4**: `node_meta_for` on both backends returns equivalent metadata; the resolver uses a single algorithm.

---

## (c) Living-Document Declaration

This document is **not a static requirements artifact**. It is a **living inventory** that Step 10 of the M4 plan expands.

- **During Steps 1–9**: This document records the known divergence inventory (sections a–b above).
- **During Step 10 (terminal gate)**: When the post-execution `pytest` suite is diffed against `artifacts/m4/m4_baseline_pre_apply.txt`, any golden-test change whose cause is **not** already listed in section (b) MUST be added as a new `Dn` entry with a justifying explanation. "Unlisted golden diff → expand inventory, then re-baseline" — never auto-flag as a regression.
- **After M4 lands**: This document serves as an auditable rationale for every characterization-golden change introduced by the unified resolution path.

---

## (d) ResolutionContext API Spec

### NodeBackend Protocol

```python
class NodeBackend(Protocol):
    """Abstract backend for node lookups. Implemented by LintIndexBackend and EditLedgerBackend."""

    def node_for(self, scope_path: str, uid: str) -> dict[str, Any] | None: ...
    def node_exists(self, scope_path: str, uid: str) -> bool: ...
    def uid_for_lg_id(self, scope_path: str, lg_id: int) -> str | None: ...
    def node_meta_for(self, scope_path: str, uid: str) -> _NodeMeta | None: ...
```

### LintIndexBackend (thin wrapper around `LintIndex`)

- Delegates `node_for` → `index.node_by_uid`
- Delegates `node_exists` → `index.node_exists`
- Delegates `uid_for_lg_id` → `index.uid_for_lg_id`
- Delegates `node_meta_for` → `index.node_meta_for`

### EditLedgerBackend (~50-80 LOC)

- `__init__(ledger: EditLedger)`: builds **`_lg_id_to_uid: dict[tuple[str, int], str]`** reverse map by iterating `ledger.node_index.items()`, extracting `node.get("id")` (the LiteGraph integer ID) for each `(scope_path, uid)` entry. Also builds `_uid_to_lg_id` for the reverse direction.
- `node_for(scope_path, uid)`: `ledger.resolve_node(scope_path, uid)`
- `node_exists(scope_path, uid)`: `(scope_path, uid) in ledger.node_index`
- `uid_for_lg_id(scope_path, lg_id)`: `self._lg_id_to_uid.get((scope_path, lg_id))`
- `node_meta_for(scope_path, uid)`: extracts `class_type` (from `node.get("type") or node.get("class_type")`), `input_names` (from `node["inputs"]` list), `output_names` (from `node["outputs"]` list), `output_slots` (dict mapping output name→index). Caches results to avoid repeated extraction.

### ResolveResult[T]

```python
@dataclass(frozen=True)
class ResolveResult(Generic[T]):
    value: T | None
    issues: list[ResolutionIssue]  # always plural
```

### ResolutionIssue

```python
@dataclass(frozen=True)
class ResolutionIssue:
    code: str
    message: str
    severity: str  # "error" | "warning" | "info"
    scope_path: str | None
    uid: str | None
    detail: dict[str, Any]
```

### ResolutionContext methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `resolve_uid` | `(backend, scope_path, uid_str)` | `ResolveResult[str]` |
| `resolve_node_target` | `(backend, target: NodeTarget)` | `ResolveResult[NodeTarget]` |
| `resolve_node_field_target` | `(backend, target: NodeFieldTarget)` | `ResolveResult[NodeFieldTarget]` |
| `resolve_link_source` | `(backend, source: LinkSourceRef)` | `ResolveResult[LinkSourceRef]` |
| `resolve_link_target` | `(backend, target: LinkTargetRef)` | `ResolveResult[LinkTargetRef]` |
| `resolve_source_endpoint` | `(backend, ref: LinkSourceRef, *, schema_provider)` | `ResolveResult[ResolvedLinkEndpoint]` |
| `resolve_target_endpoint` | `(backend, ref: LinkTargetRef, *, schema_provider)` | `ResolveResult[ResolvedLinkEndpoint]` |
| `resolve_output_slot_index` | `(backend, scope_path, uid, output_slot)` | `ResolveResult[int]` |
| `resolve_input_slot_index` | `(backend, scope_path, uid, input_field)` | `ResolveResult[int]` |

### Adapter functions

```python
def to_lint_issue(ri: ResolutionIssue, *, op_index: int, op_kind: str) -> LintIssue:
    """Convert a ResolutionIssue to a LintIssue (singular adapter for lint shims)."""

def to_port_issues(result: ResolveResult[T]) -> list[PortIssue]:
    """Extract PortIssue list from a ResolveResult (plural adapter for apply shims)."""
```

---

## (e) EditLedgerBackend Implementation Sketch (~50–80 LOC)

```
class EditLedgerBackend:
    def __init__(self, ledger: EditLedger):
        self._ledger = ledger
        # Build (scope_path, lg_id) → uid reverse index
        self._lg_id_to_uid: dict[tuple[str, int], str] = {}
        self._uid_to_lg_id: dict[tuple[str, str], int] = {}
        for (scope_path, uid), node in ledger.node_index.items():
            node_id = node.get("id")
            if isinstance(node_id, int):
                self._lg_id_to_uid[(scope_path, node_id)] = uid
                self._uid_to_lg_id[(scope_path, uid)] = node_id
        # Metadata cache
        self._meta_cache: dict[tuple[str, str], _NodeMeta] = {}

    def node_for(self, scope_path: str, uid: str) -> dict[str, Any] | None:
        return self._ledger.resolve_node(scope_path, uid)

    def node_exists(self, scope_path: str, uid: str) -> bool:
        return (scope_path, uid) in self._ledger.node_index

    def uid_for_lg_id(self, scope_path: str, lg_id: int) -> str | None:
        return self._lg_id_to_uid.get((scope_path, lg_id))

    def node_meta_for(self, scope_path: str, uid: str) -> _NodeMeta | None:
        key = (scope_path, uid)
        if key in self._meta_cache:
            return self._meta_cache[key]
        node = self.node_for(scope_path, uid)
        if node is None:
            return None
        meta = _extract_node_meta(node, scope_path, uid)
        self._meta_cache[key] = meta
        return meta
```

The shared `build_lg_id_maps` helper (moved from `edit_lint.py:205`) is used by BOTH `LintIndex.build` and `EditLedgerBackend.__init__`.

---

## (f) Provenance: Helpers Moving Into resolution.py

| Helper | Current Location | New Location | Notes |
|--------|-----------------|-------------|-------|
| `_build_lg_id_maps` | `edit_lint.py:205` | `resolution.py` (shared free function) | Used by `LintIndex.build` and `EditLedgerBackend.__init__` |
| `_try_parse_lg_id` | `edit_lint.py:472` | `resolution.py` (shared free function) | Currently only used in `edit_lint.py`; will also be used by `ResolutionContext.resolve_uid` |
| `_NodeMeta` | `edit_lint.py:138` | `resolution.py` (re-exported or shared) | Used by both `LintIndexBackend` and `EditLedgerBackend.node_meta_for` |

---

## (g) Assumption A8 — Parser-Side Resolution Is Out of Scope

**Assumption A8**: The 13 `EditLedger.resolve_node` call sites in `edit_session_describe.py` (11) and `edit_session_parse_execute.py` (2) are **NOT** targets for M4 LG-id aliasing. The parser-side `_ResolveMixin` in `edit_session_resolve.py` already canonicalizes uids from edit-language syntax before they reach session-level code, so those call sites receive pre-resolved canonical uids and have no need for LG-id aliasing.

**Settled Decision SD1**: Parser-side `_ResolveMixin` stays separate. `ResolutionContext` is a new, orthogonal apply/lint resolver — not a replacement for the parser-side resolver.

---

*Last updated: 2026-06-10 (M4 Step 1). Step 10 will add entries for any golden diffs not already catalogued above.*
