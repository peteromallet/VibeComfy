# EditSession contract (M1 — offline-provable Python edit surface)

This document freezes the public API, grammar, diagnostics, identity rules, safety
model, proof gates, and integration boundary of `EditSession`. It is the
authoritative reference for M1 and every consumer that builds on it (M2 agent
loop, browser/UI wiring, M3 replay/audit).

**Everything below is implemented and verified** by the M1 test suite
(`tests/test_porting_edit_session.py`, 177+ tests).

---

## 1. Lifecycle

```
session = EditSession(raw_ui_json, caps=..., schema_provider=..., ...)
source  = session.render()          # produce the editable Python view
result  = session.apply_batch(code) # interpret code, lower to typed ops
final   = session.done()            # run proof gates A/B/C
```

- `render()` must be called at least once before `apply_batch`. The first
  `render()` seeds the write-once `name_by_uid` ↔ `uid_by_name` lock tables.
- Later `render()` calls **enforce** those locks strictly; a re-render that
  changes a locked name or uid produces an error diagnostic.
- `apply_batch` may be called zero or more times after the first render.
- `done()` must be called exactly once at the end; it replays all landed ops
  through the deterministic apply path and runs the proof gates.

---

## 2. Constructor

```python
EditSession(
    raw_ui_json: Mapping[str, Any],
    *,
    schema_provider: Any | None = None,
    caps: frozenset[str] | set[str] | tuple[str, ...] = (),
    render_budget_ms: float | None = None,
    max_batch_bytes: int = 20_000,
    max_statements: int = 100,
    max_expanded_statements: int = 500,
    max_for_iterations: int = 100,
)
```

| Parameter | Default | Purpose |
|---|---|---|
| `raw_ui_json` | (required) | The user's verbatim ComfyUI graph — the **substrate**. Stored as `original_ui`. |
| `schema_provider` | `get_schema_provider("auto")` | Schema source for node lookups and compatibility checks. |
| `caps` | `()` | Capability flags (reserved for M2+). |
| `render_budget_ms` | `None` | Emit a warning diagnostic if `render()` exceeds this budget. |
| `max_batch_bytes` | 20 000 | UTF-8 byte cap per `apply_batch` call. |
| `max_statements` | 100 | Top-level statement cap (before `for`-expansion). |
| `max_expanded_statements` | 500 | Statement cap after `for`-loop expansion. |
| `max_for_iterations` | 100 | Maximum iterations for any single `for i in range(N)` loop. |

The constructor deep-copies `raw_ui_json` into both `original_ui` (never mutated
after construction) and `working_ui` (mutated by landed edit ops). It ingests
both into `EditLedger` instances (`original_ledger` and `ledger`).

---

## 3. `render()` → `str`

```
source_string = session.render()
```

**Internal pipeline:**

1. Re-ingest `working_ui` into `self.ledger`.
2. Convert `working_ui` → `normalize_to_api(…, use_comfy_converter=False)` → `convert_to_vibe_format(…)`.
3. Call `emit_agent_edit_python(workflow, …, variable_name_locks=name_by_uid, strict_variable_name_locks=…)`.
4. Parse `# uid:` comments from the emitted source to extract `(uid, name)` pairs.
5. Seed (first call) or validate (later calls) the lock tables.
6. If `render_budget_ms` is set and elapsed time exceeds it, emit a
   `render_budget_exceeded` warning diagnostic.

**Identity invariants:**

- First render: every `uid`↔`name` pair seeds `name_by_uid` and `uid_by_name`.
  These are write-once — an existing mapping is never silently overwritten.
- Later renders: strict lock enforcement. A re-render that changes a locked name
  produces `render_name_lock_mismatch`; a re-render that maps a locked name to a
  different uid produces `render_uid_lock_mismatch`; a previously-locked uid
  absent from the render produces `render_locked_uid_missing`.
- The source always passes `ast.parse` before being returned (a `SyntaxError`
  raises `RuntimeError` at the emitter level).

**Output format:**

The rendered source is a valid-Python assignment view where each node becomes a
variable assignment:

```python
# vibecomfy: agent-edit
# Edit node assignments only; uid comments are the stable identity fallback.

loader = CheckpointLoaderSimple(ckpt_name="sd_xl.safetensors")  # uid:abc123
```

- Each line ends with `# uid:<vibecomfy_uid>` — the stable identity fallback.
- Virtual substrate nodes (`GetNode`, `SetNode`, `Reroute`) are tagged `[virtual]`.
- Edge references use codec-derived output slot aliases: `loader.model`,
  `vaedecode.image`.
- The emitter accepts only `VibeWorkflow`, never raw LiteGraph UI JSON.
- Keyword-safe slot aliases use the slot codec (see §10).

---

## 4. `apply_batch(code)` → `BatchResult`

```python
result = session.apply_batch(code)
# result.ok          — True iff all statements succeeded and no batch-level diags exist
# result.statements  — tuple of StatementResult (one per expanded statement)
# result.diagnostics — tuple of CompactDiagnostic (batch-level)
# result.landed_ops  — tuple of EditOp (successfully applied typed ops)
```

### 4.1 Parsing and validation

1. **Byte cap**: if `len(code.encode("utf-8")) > max_batch_bytes`, fail with
   `batch_byte_cap_exceeded`.
2. **Parse**: `ast.parse(code, mode="exec")`. Syntax errors produce
   `batch_syntax_error`.
3. **Statement cap**: if `len(module.body) > max_statements`, fail with
   `batch_statement_cap_exceeded`.
4. **Validate each statement** against the allow-list (§5). Unsafe forms are
   rejected immediately with per-statement diagnostics.
5. **Expand `for` loops**: `for i in range(N): …` is expanded into `N` copies of
   the loop body with `i` bound in each copy's constant environment. Only
   `range(…)` iterators are allowed; non-constant bounds, non-integer bounds,
   `for`/`else`, and oversized loops are rejected.
6. **Expanded-statement cap**: if expansion produces more than
   `max_expanded_statements` total statements, fail with
   `batch_expanded_statement_cap_exceeded`.

### 4.2 Execution

Statements are executed **sequentially** in source order. Each statement:

1. **Resolves** against the current `uid_by_name` / `name_by_uid` lock tables.
2. **Lowers** to a typed edit op (`SetNodeFieldOp`, `UpsertLinkOp`, …).
3. **Applies** through the existing `apply_delta(working_ui, (op,), …)` path
   (unchanged from the existing edit infrastructure).
4. **Records** the op in `self.landed_ops` and updates `self.ledger`.

**Partial success:** if one statement fails, later *independent* statements still
land. Only statements that directly name an unbound variable (from a
failed `AddNodeOp` earlier in the *same* batch) are skipped with
`unbound_graph_name`.

### 4.3 StatementResult

```python
@dataclass(slots=True)
class StatementResult:
    statement_index: int        # line number in source
    source: str                 # exact source text of this statement
    ok: bool                    # did interpretation succeed?
    diagnostics: tuple[CompactDiagnostic, ...]
    landed: bool                # was an edit op applied?
    op_kind: str | None         # "set_node_field", "upsert_link", "remove_link",
                                # "remove_node", "set_mode", "node_call",
                                # "done", "query"
    detail: dict[str, Any]      # resolved target/endpoint/call info
    touched_uids: tuple[str, ...]  # uids affected by this op (empty if not landed)
    dependency_cause: str | None   # if failed due to a dependency
    teaching_hint: str | None      # human-readable hint for recovery
```

### 4.4 BatchResult

```python
@dataclass(slots=True)
class BatchResult:
    ok: bool
    statements: tuple[StatementResult, ...]
    diagnostics: tuple[CompactDiagnostic, ...]
    landed_ops: tuple[Any, ...]     # EditOp instances
```

---

## 5. Batch grammar (allowed forms)

### 5.1 Field assignment → `SetNodeFieldOp`

```python
node.widget_field = literal_value
```

- `node` must be a known graph name (from `uid_by_name`).
- The field value is folded through the safe constant folder (§6).
- The target node must not be an original virtual substrate node.

### 5.2 Mode assignment → `SetModeOp`

```python
node.mode = "enabled"    # mode 0
node.mode = "muted"      # mode 2
node.mode = "bypass"     # mode 4
```

- Mode labels are resolved through the reverse of `edit_projection.MODE_LABELS`.
- Only string literals are accepted (constant-folded).

### 5.3 Link assignment → `UpsertLinkOp`

```python
node.input_field = source_node.output_slot
```

- `source_node.output_slot` must reference a known graph name and an output slot
  that exists in the node's schema or UI metadata.
- The slot alias is reverse-mapped through the slot codec.
- Bare `source_node` (no explicit slot) is allowed only when the node has
  **exactly one** schema-typed, socket-compatible output.

### 5.4 Link removal → `RemoveLinkOp`

```python
node.input_field = None
```

### 5.5 Node deletion → `RemoveNodeOp`

```python
del node
```

- Only bare graph names may be deleted (not attribute chains).
- Original virtual substrate nodes cannot be deleted.

### 5.6 Add node → `AddNodeOp`

```python
var = ClassType(
    field_name=literal_value,
    input_name=source.output_slot,
    near=existing_node,
    relation="right_of",
    group="my_cluster",
)
```

- `var` is bound to the minted uid after successful apply. It may be referenced
  by later statements in the same batch.
- Literal kwargs become `AddNodeOp.fields`.
- Handle-ref kwargs (`source.output`) become `AddNodeOp.inputs`.
- Placement hints (`near`, `relation`, `group`) are resolved through the batch
  placement inference step (§9).
- Raw coordinate kwargs (`pos`, `position`, `coords`, `x`, `y`) are rejected.
- `vibecomfy.*` intent-class construction is rejected.
- If the add fails (e.g., `apply_delta` rejects it), the name is marked
  **unbound** and dependent later statements fail with `unbound_graph_name`.

### 5.7 Read-only queries (never land ops)

```python
describe('node_name')
```

- Side-effect-free. Does not mutate `working_ui` or record a landed op.
- Returns a `NodeDescriptor` via `session.describe(name)` (Python API only).

### 5.8 Bounded `for` loops

```python
for i in range(3):
    node.seed = i
```

- Only `range(N)`, `range(start, stop)`, or `range(start, stop, step)` are
  allowed.
- Bounds must be safe constant-foldable integers.
- Each iteration expands the loop body with the loop variable bound.
- Per-loop cap: `max_for_iterations` (default 100).
- `for`/`else` is not allowed.

---

## 6. Safe constant-only folding

Constants are folded through a restricted AST evaluator with **no side effects**:

| Allowed | Rejected |
|---|---|
| `int`, `float`, `str`, `bytes`, `bool`, `None`, `Ellipsis` | `import`, `exec`, `eval`, `__import__`, `compile`, `globals`, `locals`, `open` |
| `list`, `tuple`, `set`, `dict` (recursively folded) | comprehensions (`listcomp`, `setcomp`, `dictcomp`, `generatorexp`) |
| `+x`, `-x` (unary) | `lambda` |
| `+`, `-`, `*`, `/`, `//`, `%` (binary) | f-strings (`JoinedStr`) |
| `range(…)` (only as for-loop iterator) | `range(…)` outside for-loop context |
| Variable references (from `for`-loop binding environment) | nested/non-constant calls, dunder attributes, `**kwargs` |

The folder is called `_fold_constant` (internal). It operates on AST nodes, never
executes Python code, and never accesses the filesystem or network.

---

## 7. Unsafe AST rejection

The following AST forms are **rejected at validation time** before any ops are
lowered:

| Form | Diagnostic code |
|---|---|
| `import X` / `from X import Y` | `import_not_allowed` |
| `exec(…)`, `eval(…)`, `__import__(…)`, `compile(…)` | `call_not_allowed` |
| `globals()`, `locals()`, `open()` | `call_not_allowed` |
| Comprehensions (list/set/dict/gen) | `comprehension_not_allowed` |
| `lambda` | `lambda_not_allowed` |
| f-strings (`f"…"`) | `f_string_not_allowed` |
| Dunder names (`__something__`) | `dunder_name_not_allowed` |
| Dunder attributes (`obj.__attr`) | `dunder_attribute_not_allowed` |
| Nested calls (`f(g())`) | `nested_call_not_allowed` |
| `**kwargs` unpacking | `kwargs_unpack_not_allowed` |
| Positional args in node calls | `positional_args_not_allowed` |
| Non-`range` for-loop iterators | `for_iter_not_range` |
| `for`/`else` | `for_else_not_allowed` |
| Oversized `for` range | `for_iteration_cap_exceeded` |
| Scope escapes (`a.b.c`) | `scope_escape_not_allowed` |
| Non-name/attribute assignment targets | `assignment_target_not_allowed` |
| Non-name delete targets | `delete_target_not_allowed` |
| `vibecomfy.*` intent-class construction | `intent_class_construction_not_allowed` |
| Raw coordinate placement kwargs | `raw_coordinate_kwarg_not_allowed` |

---

## 8. Name / UID rules

### 8.1 Identity format

- Every node has a **vibecomfy_uid** (stored in `properties.vibecomfy_uid`).
- Subgraph-internal nodes use **scope-qualified** uids: `make_uid(scope_path,
  local_uid)`.
- UIDs are stable across renders and batches.

### 8.2 Lock tables

- `name_by_uid: dict[str, str]` — maps `uid` → `variable_name`.
- `uid_by_name: dict[str, str]` — maps `variable_name` → `uid`.
- Both are **write-once**: an existing mapping is never silently overwritten.
- Seeded on first `render()` from `# uid:` comments in the emitted source.
- Enforced strictly on later `render()` calls.

### 8.3 Unbound names

- When an `AddNodeOp` fails, the target variable name is marked **unbound**
  (`self.unbound_names`).
- Later statements in the same batch that reference an unbound name fail with
  `unbound_graph_name`.
- Unbound names are cleared on the next `render()`.

### 8.4 Name resolution in apply_batch

- `uid_by_name[name]` → stale check against `ledger.resolve_node` → passes or
  fails with `stale_graph_name`.
- If not in `uid_by_name`, fails with `unknown_graph_name`.
- Dunder names are rejected at validation time.

---

## 9. Batch placement inference

Before `AddNodeOp` construction, a **pre-pass** over the parsed batch:

1. **Extracts** add-node facts and rewire facts from the batch AST.
2. **Detects splices**: a new node *consumes* the exact pre-existing source
   endpoint that a later assignment *rewires* the downstream input through the
   new node's output. Only then is a true splice detected and the new node gets
   an inferred anchor.
3. **Infers left-to-right cluster anchors** for 2+ connected add-node
   statements using dataflow order. The cluster tie-break uses
   `estimate_node_size(…)` width as a spacing hint only.
4. **Explicit placement hints** (`near=…`, `relation=…`, `group=…`) take
   priority over inferred placement.

The existing `edit_apply.py` semantics and the raw-coordinate surface are
**unchanged**.

---

## 10. Slot codec

`vibecomfy/porting/slot_codec.py` provides deterministic, reversible
conversion between raw slot names and valid Python identifiers.

### 10.1 Public API

| Function | Purpose |
|---|---|
| `to_python_identifier(raw_name, *, used=None)` | Encode a raw name → valid Python identifier |
| `to_raw_name(encoded, context)` | Reverse lookup: encoded → raw (KeyError or ValueError on failure) |
| `build_reverse_map(raw_names)` | Batch reverse map with collision detection |
| `encode_slot_names(raw_names)` | Batch forward map with collision avoidance |

### 10.2 Encoding rules

1. Empty names → `"_"`.
2. Lowercase.
3. Non-alphanumeric characters (except `_`) → `_`.
4. Collapse consecutive underscores.
5. Strip leading underscores unconditionally.
6. Strip trailing underscores (but track for collision detection).
7. Leading digit → prepend `_` (`3d_model` → `_3d_model`).
8. Python keyword → trailing `_` (`in` → `in_`), matching PEP 8.
9. Python builtin → trailing `_` (`list` → `list_`).
10. Collision: if a keyword-mapped name collides with a raw `_`-suffixed name,
    the latter gets `_2` instead (`in`→`in_`, raw `in_`→`in_2`).
11. If `used` set is provided, deduplicate with `_2`, `_3`, … suffixes.

### 10.3 Reverse resolution

`to_raw_name` requires a `context` dict mapping every candidate raw name to
itself. It encodes each key and returns the one matching the given encoded
identifier. Raises `KeyError` if no match, `ValueError` if ambiguous.

---

## 11. Virtual-node immutability

Original substrate virtual nodes (`GetNode`, `SetNode`, `Reroute`) are
**immutable** through the edit surface:

- Cannot be mutated (field/link/mode assignment rejected).
- Cannot be deleted (`del node` rejected).
- Attempted mutation/deletion produces `original_virtual_node_immutable`.

The check compares nodes against `original_ledger`, so it is
**independent of any mutations applied during the session**.

Session-created virtual nodes (added via `AddNodeOp` in the same session) remain
fully mutable.

---

## 12. Proof gates (`done()`)

`done()` runs three sequential gates. It returns `DoneResult(ok=True, …)` only
when all three pass.

### 12.1 Gate A — Byte-faithfulness replay

1. Replay every landed op over `original_ui` through `apply_delta(…, ops)`.
2. If `apply_delta` fails (or `guard_full_ui` fails), `done()` fails with
   per-issue diagnostics.
3. Assert `recomputed_candidate == working_ui` (deep equality).
4. If zero ops were landed, assert `working_ui == original_ui`.

### 12.2 Gate B — Touched-region compile isomorphism

1. Compile `original_ui`, `working_ui`, and `candidate_ui` through
   `normalize_to_api` → `VibeWorkflow` → `compile("api")`.
2. Derive the **touched region** (set of API node ids):
   - All nodes explicitly touched by landed ops (via uid → node_id mappings).
   - Added nodes (in working/candidate but not original).
   - Removed nodes (in original but not working/candidate).
   - One-hop neighbors of every node in the region.
   - All endpoints of changed edges.
3. Subset working and candidate API graphs to the touched region.
4. Compare with `parity.compile_equivalent(working_region, candidate_region)`.
5. On failure, return diff lines in the diagnostic detail.

### 12.3 Gate C — Plain-language summary

Generates a human-readable summary sentence for each landed op:

| Op type | Summary format |
|---|---|
| `SetNodeFieldOp` | "Changed *name*.*field* from *old* to *new*." |
| `AddNodeOp` | "Added *ClassType* node '*name*' with inputs: *src.slot (TYPE)*; with fields: *k=v*." |
| `RemoveNodeOp` | "Removed *ClassType* node '*name*'." |
| `UpsertLinkOp` | "Connected *src.slot* (TYPE) → *dst.field*." or "Rewired *dst.field* (TYPE) from *prev.src* → *new.src*." |
| `RemoveLinkOp` | "Disconnected *name.field* from *prev.src*." |
| `SetModeOp` | "Changed *name* mode from *old_label* to *new_label*." |

### 12.4 DoneResult

```python
@dataclass(slots=True)
class DoneResult:
    ok: bool
    summary: str
    diagnostics: tuple[CompactDiagnostic, ...] = ()
```

---

## 13. Diagnostic shape

```python
@dataclass(frozen=True, slots=True)
class CompactDiagnostic:
    code: str                       # machine-readable error code
    message: str                    # human-readable message
    severity: str = "warning"       # "error" | "warning" | "info"
    detail: dict[str, Any] = {}     # structured context
    teaching_hint: str | None = None  # recovery guidance for the agent
```

Teaching hints are defined in `_TEACHING_HINTS` and cover all major diagnostic
codes (`unbound_graph_name`, `unknown_graph_name`, `stale_graph_name`,
`unknown_target_field`, `unknown_output_slot`, `ambiguous_bare_reference`,
`scope_escape_not_allowed`, `original_virtual_node_immutable`,
`raw_coordinate_kwarg_not_allowed`, `intent_class_construction_not_allowed`,
`anchor_target_missing`, `cross_scope_add_node_unsupported`).

---

## 14. Read-only queries

### 14.1 `describe(name)` → `NodeDescriptor`

Returns a structured, side-effect-free description of a graph node. Does **not**
count as a landed operation and never mutates `working_ui`.

```python
@dataclass(frozen=True, slots=True)
class NodeDescriptor:
    name: str
    uid: str
    scope_path: str
    class_type: str
    mode: int
    mode_label: str
    is_virtual: bool
    is_helper: bool
    title: str | None
    pos: tuple[float, float] | None
    size: tuple[float, float] | None
    widget_values: tuple[Any, ...]
    fields: tuple[InputSlotInfo, ...]
    outputs: tuple[OutputSlotInfo, ...]
```

### 14.2 `search(…)` → `list[NodeSignatureRow] | str`

Queries available node signatures from the session's schema provider.
Side-effect-free; never mutates `working_ui`.

```python
session.search(
    focus_types=["KSampler", "VAEDecode"],        # per-node lookup
    compatible_input_type="MODEL",                # filter by output compatibility
    compatible_output_type="LATENT",              # filter by input compatibility
    formatted=True,                                # return formatted text
)
```

When `formatted=False`, returns `list[NodeSignatureRow]`. When `formatted=True`,
returns a deterministic text catalog via `format_signature_rows`.

`NodeSignatureRow` fields: `class_type`, `inputs` (list of
`InputSignatureField`), `outputs` (list of `OutputSignatureField`),
`source_confidence`, `pack`.

---

## 15. BATCHES ARE INTERPRETED, NEVER EXECUTED

This is the foundational safety rule of the edit surface:

- All batch code is parsed with `ast.parse`.
- All values are obtained via the safe constant folder (`_fold_constant`).
- Statements are mapped to typed edit ops and applied through `apply_delta`.
- **At no point is `exec`, `eval`, `compile`, `__import__`, or any similar
  mechanism invoked on user/authored code.**
- The code is a **declarative description** of edits, not executable Python.

---

## 16. M1 boundary (what is NOT included)

M1 delivers the offline-provable `EditSession` as a self-contained building
block. The following are explicitly **out of scope** for M1:

| Out of scope | Where it lives |
|---|---|
| Agent-provider loop (LLM call → edit → re-render) | M2 |
| Browser/UI wiring (websocket, real-time graph sync) | M2 |
| `handle_agent_edit` replacement or integration | M2 |
| `tools/format_as_python.py` modifications | Never (legacy delegation wrapper) |
| `emit_scratchpad_python` removal or modification | Never (coexists as parallel path) |
| Multi-session replay / audit trail | M3 |
| Subgraph-scoped edit operations | M4+ |

**Existing paths preserved:**

- `emit_scratchpad_python(…)` is **untouched** and continues to serve the
  existing agent-edit pipeline.
- `emit_agent_edit_python(…)` is the **new parallel entry point** used by
  `EditSession.render()`.
- The existing typed edit-op infrastructure (`edit_ops.py`, `edit_apply.py`,
  `edit_ledger.py`) is **unchanged** — `EditSession` lowers its interpreted
  statements to the same op types.

---

## 17. Public module surface

All public M1 symbols are exported from `vibecomfy.porting`:

```python
from vibecomfy.porting import (
    # Session
    EditSession,
    # Results
    BatchResult,
    StatementResult,
    DoneResult,
    # Diagnostics
    CompactDiagnostic,
    # Queries
    NodeDescriptor,
    InputSlotInfo,
    OutputSlotInfo,
    # Emitter
    emit_agent_edit_python,
    EmissionDiagnostic,
    emit_available_node_signatures,
    format_signature_rows,
    NodeSignatureRow,
    InputSignatureField,
    OutputSignatureField,
    # Slot codec
    slot_codec,
    to_python_identifier,
    to_raw_name,
    build_reverse_map,
    encode_slot_names,
)
```

**Not exported** (private): `_slugify_identifier`, `_safe_var`, `_unique_var`,
`_safe_kwarg_name`, `_safe_output_name`, `_build_subgraph_def`,
`_emit_subgraph_functions`, `_build_input_signature_fields`,
`_build_output_signature_fields`.
