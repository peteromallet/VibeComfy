# M2 C0–C1 Contract Checkpoint — Decisive Implementation Specification

Status: **ACCEPTED 2026-07-17 — bounded checkpoint for C0 (contracts) and C1
(adapter-isolated preflight/plan proof only). C1 makes zero native calls,
including harness writes. C2 atomic cutover remains pending.** Subordinate to `m2-native-adapter.md` (authority) and
`m2-slices-3-4-implementation.md` (acceptance). Read-only design resolved against
current code; this document does not edit tracked source.

Scope hard limits (re-stated so they cannot drift):

- **C0** lands cross-language contracts, goldens, prepared-authority binding,
  and fail-closed corpus. **Zero** production live-code behavior change, zero
  new public adapter mutation methods, zero consumer rerouting. The only
  production-file structural change is a behavior-preserving relocation of the
  shared hash primitives into a zero-dependency leaf (§0.3) so the new contract
  modules can import them without a cycle; all symbols are re-exported by
  `projection_registry_v1.py` with identical identity, so every existing caller
  is unaffected.
- **C1** is **preflight/plan proof only with no native writes at all —
  including harness writes.** C1 adds a private, pure plan-builder module that
  consumes prepared authority, validates every fail-closed condition, and builds
  a frozen plan. Zero-native-call proof is produced **externally** — by the
  harness-owned sentinel counters and by static import-reachability analysis
  (§6.3) — never by the builder attesting its own behavior (Gate #4: no
  self-attested `sentinelCounts`, no dependency-injected asserters/hash). It may
  build a frozen private plan and validate already-bound
  inverse/restoration digests, but it does **not** generate an inverse from
  live state and does **not** execute a primitive. Primitive execution,
  landed-prefix evidence, partial mutation, serialization-after-mutation,
  inverse execution, repaint, and fault-after-write proofs belong to **C2/C3**,
  not C1. Old production path stays active. **No** public consumer routing,
  **no** native writes of any kind, **no** S3/S4 ownership-complete claim,
  **no** duplicate public APIs.

---

## 0. Current code reality (resolved, not assumed)

This section pins the exact owners that must be **extended**, never duplicated.
"Do not invent a second owner" is enforced by naming them here.

### 0.1 Canonical delta — two owners, already aligned

| Side | File | Frozen constants |
| --- | --- | --- |
| JS | `vibecomfy/comfy_nodes/web/canonical_delta.js` | `DELTA_CONTRACT_V1="delta_v1"`, `DELTA_SCHEMA_VERSION="2.0.0"`, `CANONICAL_DELTA_OP_NAMES` = exactly `set_node_field, set_mode, add_node, upsert_link, remove_node, remove_link`. Exports `normalizeDeltaV1`, `ensureRootScopedOps`, `normalizeDeltaEnvelope`, `DeltaDiagnosticError`. |
| Python | `vibecomfy/porting/edit/ops.py` | `DELTA_SCHEMA_VERSION="2.0.0"`, `CANONICAL_DELTA_OP_NAMES` (same six), `normalize_delta_v1`, `ensure_root_scoped_delta_envelope`, `EditOpParseError`. |

`AddNodeOp` (Python, `porting/edit/ops.py`) already carries `op, scope_path,
class_type, fields, inputs, anchor, uid, node_id`. JS `canonical_delta.js`
enforces non-empty `uid`, `node_id`, `class_type` on every `add_node`. **`node_id`
is the stable native instance id; `class_type` is the node type. They are
distinct and both already authoritative inside the op.** Authority consumers
reach the delta owner through
`projection_registry_v1.py:_strict_delta` (which imports
`ensure_root_scoped_delta_envelope`). C0 does **not** add a third delta owner.

### 0.2 Prepared authority — exactly two validator owners

| Side | Validator file | Role |
| --- | --- | --- |
| JS | `vibecomfy/comfy_nodes/web/prepared_authority_v1.js` | `validateCandidateAuthorityV1`, `validatePreparedAuthorityV1`, `validateCandidateTransactionV2`. **Sole JS authority validator.** Restoration shape check is the local `digest()` helper; transition-equality is the inline key list in `validateCandidateTransactionV2`. |
| Python | `vibecomfy/comfy_nodes/agent/projection_registry_v1.py` | `validate_candidate_authority_v1`, `validate_prepared_authority_v1`, `validate_candidate_transaction_v2`. **Sole Python authority validator.** Imports delta strictness from `porting/edit/ops.py`. Restoration shape check is `_restoration`; transition-equality is the inline tuple in `validate_candidate_transaction_v2`. |

`vibecomfy/comfy_nodes/agent/candidate_transaction.py` is the **aggregate
builder** (`build_candidate_transaction`, `project_transaction_state`,
schema-witness). It imports every validator from `projection_registry_v1.py`.
It mints envelopes; it does not own validation. New layout/materialization
envelopes are **minted** in `candidate_transaction.py` and **validated** in
`projection_registry_v1.py` — never the reverse, never a second validator.

The existing prepared-authority common validator already enforces
(`_validate_candidate_authority_common` / `validateAuthorityCommon`):
`contract_version`, issued identities, `workflow_id` UUID, root scope,
`authority_receipt_contract_version`/`delta_schema`/`digest`,
`operation.delta_contract=="delta_v1"` + `wire_version=="2.0.0"` + strict
root-scoped ops, `operation_family ∈ {structural, layout}`, forward projection
family match for pre/post/rollback, **layout `structural_witness`
pre==post**, and a shaped `restoration_strategy`. C0 extends this exact
function; it does not fork it.

### 0.3 Canonical hashing — one shared contract (no second hash)

| Side | Owner | API |
| --- | --- | --- |
| JS | `vibecomfy/comfy_nodes/web/canonical_hash.js` (**already a leaf — no cycle**) | `canonicalJsonString` (ensure_ascii=true), `canonicalSessionJsonString` (ensure_ascii=false), `canonicalJsonBytes`, `sha256Hex`, `sha256HexFromString`. |
| Python | new leaf `vibecomfy/comfy_nodes/agent/_canonical_contract_primitives.py` (re-exports below) + `projection_registry_v1.py` (public re-export) | `canonical_json`, `canonical_json_bytes_v1`, `_hash`, `_order_json_objects_utf16`, `ContractError`. Uses `_order_json_objects_utf16` to byte-match JS UTF-16 key ordering. |

`candidate_transaction.py:canonical_json_bytes`/`content_hash` are thin
facades over `_registry_canonical_json_bytes`. **All new digests in C0 reuse
these exact functions.** New contract modules import the shared hash owner;
they never call `hashlib.sha256(json.dumps(...))` directly.

**Cycle resolution (Python only).** The new Python contract modules
(`layout_operation_v1.py`, `mutation_materialization_v1.py`) need
`ContractError` + `canonical_json_bytes_v1`, while `projection_registry_v1.py`
must call those modules' `assert_*_envelope` validators from inside
`_validate_candidate_authority_common`. That mutual import is a cycle. The
decisive, minimal fix is a **zero-dependency leaf**,
`vibecomfy/comfy_nodes/agent/_canonical_contract_primitives.py`, owning
`ContractError`, `canonical_json`, `canonical_json_bytes_v1`, `_hash`, and
`_order_json_objects_utf16` (the code is moved verbatim — no logic change),
**plus** the new `canonicalize_contract_numeric` preprocessor (§0.3.1). JS
`canonical_hash.js` gains the mirror export `canonicalizeContractNumeric`.
Neither the Python leaf nor the JS module modifies the existing `sha256Hex` /
`_hash` / `canonical_json` / `canonical_json_bytes_v1` entry points: the
numeric normalizer is a value preprocessor the new contract modules call
**before** hashing, never a replacement for the shared hash identity.
`projection_registry_v1.py` does `from ._canonical_contract_primitives import
ContractError, canonical_json, canonical_json_bytes_v1, _hash,
_order_json_objects_utf16, canonicalize_contract_numeric` and re-exports them unchanged, so every existing
`from projection_registry_v1 import ...` resolves to **the same objects**
(identity-preserving, behavior-preserving). Dependency direction is one-way:

```
_canonical_contract_primitives.py   (leaf, imports nothing in agent/)
        ↑                ↑                ↑
        │                │                │
projection_registry_v1.py   layout_operation_v1.py   mutation_materialization_v1.py
        │
        └──→ (imports, runtime calls) layout_operation_v1.py, mutation_materialization_v1.py
```

No module below the leaf imports `projection_registry_v1.py`. The leaf is the
single hash owner; `projection_registry_v1.py` remains the sole public
re-export facade. **No validator logic, no hash logic is duplicated.** JS needs
no leaf because `canonical_hash.js` is already import-cycle-free.

**No invented hash-injection owner/API.** The JS hash surface used by every new
contract is exactly the named exports of `canonical_hash.js`:
`canonicalJsonString`, `canonicalJsonBytes`, `sha256Hex`, `sha256HexFromString`,
**and** `canonicalizeContractNumeric` (the numeric preprocessor, §0.3.1). The
Python surface is exactly `canonical_json`, `canonical_json_bytes_v1`, `_hash`,
**and** `canonicalize_contract_numeric` (re-exported from the leaf). No
contract module defines its own
`hashlib.sha256(json.dumps(...))`, its own JSON text canonicalizer, or a "hash injection"
parameter that lets a caller substitute the hashing identity. The numeric
preprocessor transforms *values* (coercing integer-valued floats to ints on the
Python side); it does not sort keys, emit JSON text, or substitute the hashing
identity — it is a value preprocessor, not a second canonicalizer or hash
owner. The C1 plan
builder (§6.3) imports these named exports directly; it does **not** receive a
hash function as a dependency-injected argument (that would let the subject
attest its own digest identity).

### 0.3.1 Cross-language canonical numeric parity (resolved, not assumed)

Python `json.dumps` and JS `JSON.stringify` diverge on numeric spellings, all
of which appear inside geometry payloads and would silently break
byte-identical digests if left un-handled. Inspection of the actual codebase
confirms the divergence is real and one-sided — **it is always Python that
emits a different spelling**; JS `JSON.stringify` is already canonical for
every finite number after `JSON.parse`:

| Source token | Python parse | Python `json.dumps` | JS parse | JS `JSON.stringify` | Pre-hash normalizer output (both sides) |
| --- | --- | --- | --- | --- | --- |
| `1` | `int 1` | `1` | `1` | `1` | `1` |
| `1.0` | `float 1.0` | `1.0` | `1` | `1` | `1` |
| `-0.0` | `float -0.0` | `-0.0` | `-0` | `0` | `0` |
| `1e2` / `1E2` | `float 100.0` | `100.0` | `100` | `100` | `100` |
| `1.5` | `float 1.5` | `1.5` | `1.5` | `1.5` | `1.5` |

**Why REJECT is impossible (codebase-verified).** The prior draft proposed an
`_assertCanonicalNumber` / `assertCanonicalNumber` that rejects integer-valued
floats. After `JSON.parse("1.0")`, JavaScript holds the IEEE-754 double `1`,
which is bit-identical to the value parsed from `"1"`. There is no field, tag,
or property on a JS `Number` that records whether the source token carried a
decimal point or an exponent. Any predicate `f: Number → boolean` that returns
`true` for `1.0` (post-parse value `1`) necessarily returns `true` for `1` as
well — it would reject every ordinary integer coordinate. The REJECT policy is
therefore unimplementable in JavaScript and is withdrawn.

**Policy: NORMALIZE to JS-compatible spelling (the sole feasible, deterministic,
cross-language contract).** The new contract modules
(`layout_operation_v1`, `mutation_materialization_v1`, and any restoration
payload they own) call a shared preprocessor,
`canonicalize_contract_numeric(value, *, finite_error_code)` (Python, in the
leaf §0.3) / `canonicalizeContractNumeric(value, { finiteErrorCode })` (JS, in
`canonical_hash.js`), **before** passing the value to `sha256Hex` /
`canonical_json_bytes_v1`. The preprocessor recursively walks dicts (by value)
and lists (by element) and applies the following rules to every numeric leaf:

| Input | JS action | Python action | Result |
| --- | --- | --- | --- |
| `typeof === "number"` finite / `int` or `float` (not `bool`) | return as-is (JS serialization is already canonical) | `float` with `.is_integer()` and `abs(x) ≤ 2^53−1` → `int(x)`; `int` → as-is; genuine fraction `float` → as-is | byte-identical |
| `NaN`, `±Infinity` | throw `finiteErrorCode` | throw `finite_error_code` | rejected |
| `bool` in a numeric position (Python `True`/`False`) | n/a (`typeof === "boolean"`, not reached) | raise `non_canonical_number` | rejected |
| integer-valued `float` with `abs(x) > 2^53−1` | n/a (JS `Number` cannot represent exactly — caught as non-finite or pre-truncated by caller) | raise `non_canonical_number` | rejected |

This guarantees byte-identical `sha256Hex` preimages for ordinary integer
geometry (`pos: [100, 200]`), integer-valued floats (`1.0` → `1`), negative
zero (`-0.0` → `0`), exponent-origin inputs (`1e2` → `100`), and genuine
fractions (`1.5` → `1.5`) — all without rejecting any legal coordinate.

**Why this is not a second hash owner.** The normalizer transforms the *value*
before it reaches the shared hash; it does not sort keys, emit JSON text, or
call `hashlib`. The hash identity remains `sha256Hex` / `_hash` /
`canonical_json_bytes_v1`. The preprocessor lives in the shared leaf
(`_canonical_contract_primitives.py`) / shared JS leaf (`canonical_hash.js`),
not in each contract module, so there is exactly one normalizer owner. The
existing `sha256Hex` / `_hash` / `canonical_json` entry points are **not**
modified, so every existing m1/m0 digest is unchanged: callers that do not
call the normalizer get byte-identical output to today.

**Tests (§5.1)** include explicit cross-language **parity** cases proving that
`pos: [1.0, -0.0]`, `pos: [1e2, 200]`, and `pos: [1, 0]` all produce the
**same** `expected_digest` in both JS and Python (normalization, not rejection),
plus negative cases for `NaN`/`±Infinity` → `non_finite_geometry` /
`non_finite_materialization`. The `non_canonical_number` code survives only
for the truly non-normalizable case of a `bool` (Python) or an unsafe-range
integer exceeding `2^53−1`; it is **not** raised for `1.0`, `-0.0`, or
exponents.

### 0.4 Identity / scope / projection / fields — one registry pair

- JS: `vibecomfy/comfy_nodes/web/projection_registry_v1.js` (sole). Facades
  `identity_contract_v1.js`, `field_registry_v1.js`, `graph_projection.js`
  re-export only.
- Python: `vibecomfy/comfy_nodes/agent/projection_registry_v1.py` (sole).
- Root scope: JS `root_scope_v1.js` is real and tiny; Python's
  `assert_root_scope_v1` lives in `projection_registry_v1.py`. Already
  enforces `{kind:"root", path:""}` and rejects `definitions`/nested group
  scopes.

### 0.5 Restoration / durable authority — one journal owner

- JS: `vibecomfy/comfy_nodes/web/journal_durable_v1.js`
  (`validateJournalDurableV1`, `JOURNAL_DURABLE_V1`).
- Python: `validate_journal_durable_v1` in `projection_registry_v1.py`.

Both validate `baseline.{structural_hash_before,structural_hash_after}` (hex64),
`identity_fence.{transaction_id,candidate_id,plan_hash,lease_nonce,generation}`,
and `inverse_or_restore.{contract_version,digest,payload|ref}`. C0 narrows the
`restoration_strategy.contract_version` to a frozen enum
(`inverse_delta_v1`, `inverse_layout_operation_v1`, grandfathered
`baseline_snapshot_v1`) and closes the `payload`/`ref` mutual-exclusion rule
(§3.1). C0 also introduces the **separately digested, prepare-owned optional**
`restoration_strategy_compensation` slot (§3.4) — this does **not** create a
second restoration validator owner: compensation validation extends the
existing `_restoration` / `digest()` code paths alongside the mandatory slot.

### 0.6 Native mutation — current legacy owner (deleted only at C2)

`vibecomfy/comfy_nodes/web/comfy_adapter.js` is today's de-facto native
mutation owner. The **candidate-value reads** C0/C1 must make bannable (and C2
must delete) are exactly:

- `preflightDeltaPlan(liveGraphSnapshot, candidateGraph, deltaOps, options)`
  — reads `candidateGraph` for `set_node_field` value, `set_mode` mode,
  `upsert_link`/`remove_link` endpoint resolution, `add_node` payload.
- `applyGraphDeltaInPlace(app, { deltaOps, candidateGraph }, options)`.
- `applyGraphLayoutInPlace(app, { candidateGraph }, options)` — whole-graph
  geometry + group replace driven by `candidateGraph.nodes`/`.groups`.
- `materializeAddNodePayload(candidateGraph, op)` — constructs the added node
  from the candidate graph.
- `appendCandidateLinksForAddedNodes(workingGraph, candidateGraph, plan)` —
  **implicit candidate links**, the exact thing BC#2 forbids.
- `findCandidateLinkForOp(candidateGraph, op)`, `resolveEndpoint`,
  `resolveNodeFromGraph`, `verifyCandidateGraphConsistency`,
  `projectCandidateGraphToRuntimeLayout`.
- Identity fallbacks `canonicalNodeUid(node) || \`id:${String(node.id)}\`` and
  group `|| \`id:...\`` in the layout apply loop — native-ID identity fallback.

All of these exist in `comfy_adapter.js` and are reachable from
`vibecomfy_roundtrip.js`, `preview_picker.js`, `agentic_replay.js`. At C0/C1
they remain untouched; C0 defines the contracts that replace them and C1
proves the replacement privately with zero native writes.

### 0.7 Adapter — current state

`vibecomfy/comfy_nodes/web/intent_graph_adapter.js` exposes
`createIntentGraphAdapter(app)`, capability detection
(`graph_apply`, `delta_apply`, `layout_apply`), `capture`, `captureDrawSnapshot`,
and a typed `{contract_version:"intent_graph_adapter_v1", ok, data|diagnostic,
scope, operation}` envelope. It **does not yet** have any prepared-plan
internals. C1 adds a **separate private pure module**
(`_prepared_plan_builder_v1.mjs`, §6.3) — it does **not** add public methods to
the adapter and does **not** mutate the adapter's exports.
`HARNESS_DELTA_APPLY_FALLBACK_MARKER` and `legacy_whole_graph_replace` are
present as capability labels; both are deleted at C2.

---

## 1. `layout_operation_v1` — closed grammar, version `1.0.0`, four ops

### 1.1 Files (new)

| Path | Side |
| --- | --- |
| `vibecomfy/comfy_nodes/web/layout_operation_v1.js` | JS owner |
| `vibecomfy/comfy_nodes/agent/layout_operation_v1.py` | Python owner |
| `tests/fixtures/agent_edit/layout_operation_golden_v1.json` | shared golden |
| `tests/browser/layout_operation_v1.test.mjs` | JS golden + fail-closed |
| `tests/test_layout_operation_v1.py` | Python golden + fail-closed |

### 1.2 Envelope (frozen, identical JS+Python)

```jsonc
{
  "contract_version": "layout_operation_v1",
  "wire_version": "1.0.0",
  "ops": [ <LayoutOp>, ... ],
  "digest": "<64-hex>"
}
```

- `contract_version` MUST equal `"layout_operation_v1"` else `unknown_contract`.
- `wire_version` MUST equal `"1.0.0"` else `unsupported_wire_version`.
- Top-level keys are exactly `{contract_version, wire_version, ops, digest}`.
  Extra keys → `malformed_layout_operation`.
- `digest` = `sha256Hex({contract_version, wire_version, ops})` over the
  canonical form (sorted keys, ASCII-safe) using the **shared** hash owner
  (§0.3), applied **after** `canonicalizeContractNumeric` /
  `canonicalize_contract_numeric` (§0.3.1) normalizes every numeric value in
  `ops` to its JS-compatible spelling. Mismatch → `layout_operation_digest_mismatch`.

### 1.3 The four ops — root-scoped, stable-ID only

All ops carry `op` (enum) and are root-scoped by construction (no `scope_path`
field exists). Identity is **never** title, native id, position, class, or
array index. Duplicate titles are valid and remain distinct because identity is
the stable id, not the title.

| `op` | Required keys | Types / rules |
| --- | --- | --- |
| `set_node_geometry` | `uid`, `pos` | `uid`: non-empty string (stable `vibecomfy_uid`). `pos`: `[number, number]`, both finite. `size`: optional `[number, number]` finite — present only when size changes. |
| `add_group` | `id`, `bounding`, `title`, `color` | `id`: non-empty string (stable group id). `bounding`: `[number,number,number,number]` finite. `title`: string (may be non-unique). `color`: string or `null`. |
| `set_group_geometry` | `id`, plus ≥1 changed value from the `add_group` field set | `id`: non-empty string. `bounding`/`title`/`color` each optional but at least one present; same type rules as `add_group`. |
| `remove_group` | `id` | `id`: non-empty string. |

Allowed per-op key sets are **closed**. Unknown key → `malformed_layout_op`.
Every numeric component of `pos`/`size`/`bounding` is normalized through
`canonicalizeContractNumeric` / `canonicalize_contract_numeric` (§0.3.1) with
`finiteErrorCode="non_finite_geometry"` before any geometry check:
integer-valued floats (`1.0`), `-0.0`, and exponent spellings (`1e2`) are
**normalized to their JS-compatible integer spelling** (not rejected); ordinary
integer coordinates remain legal and unchanged; genuine fractions (e.g. `1.5`)
are unchanged; non-finite (`NaN`/`±Infinity`) → `non_finite_geometry`.
Missing/empty `uid`/`id` → `missing_identity`.

### 1.4 Exported API (both sides, mirror names)

JS (`layout_operation_v1.js`):

- `LAYOUT_OPERATION_CONTRACT_V1 = "layout_operation_v1"`
- `LAYOUT_OPERATION_WIRE_VERSION = "1.0.0"`
- `LAYOUT_OPERATION_OP_NAMES = Object.freeze(["set_node_geometry","add_group","set_group_geometry","remove_group"])`
- `LayoutOperationError extends Error` (`code`, `detail`)
- `normalizeLayoutOperationV1(envelope)` → frozen `{contract_version, wire_version, ops, digest}`
- `computeLayoutOperationDigest(ops)` → hex64 (canonical, via `sha256Hex` from `canonical_hash.js`)
- `assertLayoutOperationEnvelope(value)` → throws typed `LayoutOperationError` on any §1.2/§1.3 violation; returns frozen envelope on success

Python (`layout_operation_v1.py`): identical names in snake_case
(`LAYOUT_OPERATION_CONTRACT_V1`, `normalize_layout_operation_v1`,
`compute_layout_operation_digest`, `assert_layout_operation_envelope`,
`LayoutOperationError(ContractError)`). Imports `ContractError` and
`canonical_json_bytes_v1` from the leaf `_canonical_contract_primitives.py`
(§0.3), **not** from `projection_registry_v1.py` (avoids the cycle).

### 1.5 Prepared-authority binding (extend §0.2 validator, do not fork)

In `validateAuthorityCommon` (JS) and `_validate_candidate_authority_common`
(Python), when `operation_family === "layout"`:

1. `operation.ops` MUST be `[]` (empty structural delta). Non-empty →
   `layout_family_requires_empty_structural_ops`.
2. `operation.layout_operation` MUST be present and pass
   `assertLayoutOperationEnvelope`. Absent/malformed → `missing_layout_operation`
   / typed layout error.
3. `operation.layout_operation_digest` MUST equal the recomputed canonical
   digest. Mismatch → `layout_operation_digest_mismatch`.
4. `precondition`/`postcondition`/`rollback_projection` MUST be `layout_v1`
   (already enforced; keep).
5. `structural_witness` pre==post MUST hold (already enforced; keep). This is
   the **structural no-op witness for layout**.

When `operation_family === "structural"`: `operation.layout_operation` MUST be
**absent**. Presence → `unexpected_layout_operation`.

Transition immutability (item 6 reconciliation): the candidate→prepared
equality check in `validateCandidateTransactionV2` compares the whole
`operation` key in both languages (JS `JSON.stringify(prepared[k]) !==
JSON.stringify(candidate[k])`; Python `prepared.get(k) != candidate.get(k)`,
which is deep). Because `operation` is compared as an entire mapping,
`operation.layout_operation` and `operation.layout_operation_digest` are
**already transition-immutable by construction** — no nested key needs adding.
The candidate→prepared transition-equality key list (§6.5) gains exactly **one**
new top-level key: `restoration_strategy_compensation` (§3.4). Unlike every
other transition key, this key is **prepare-owned additive**: its candidate
presence is **forbidden** (`candidate_compensation_forbidden`) and its prepared
value may be **absent** (compensation not minted) or a **valid compensation
envelope** (prepare-minted after lease acquisition, §3.4); all other authority
drift remains `prepared_authority_transition_mismatch`. See §6.5 for the full
closed transition-key set and the absent-vs-null parity rule for every
optional key.

### 1.6 Candidate transaction minting (extend `candidate_transaction.py`)

`build_candidate_transaction` gains `layout_operation_envelope` parameter
(optional; required when `verification_kind == "layout_structural_noop"`).
When layout, it builds `operation = {delta_contract, wire_version, ops: [],
layout_operation: <normalized envelope>, layout_operation_digest: <digest>}`.
The existing `plan.delta_ops_envelope` stays the structural envelope (empty for
layout). The transaction's `hashes` block gains
`layout_operation_digest`. `validate_candidate_transaction` recomputes and
compares it.

JS has no aggregate builder mirror; JS authority is constructed by tests via
the validator directly. No JS second owner is created.

---

## 2. `mutation_materialization_v1` — bound native construction payload for `add_node`

### 2.1 Files (new)

| Path | Side |
| --- | --- |
| `vibecomfy/comfy_nodes/web/mutation_materialization_v1.js` | JS owner |
| `vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py` | Python owner |
| `tests/fixtures/agent_edit/mutation_materialization_golden_v1.json` | shared golden |
| `tests/browser/mutation_materialization_v1.test.mjs` | JS golden + fail-closed |
| `tests/test_mutation_materialization_v1.py` | Python golden + fail-closed |

### 2.2 Envelope (frozen, identical JS+Python)

```jsonc
{
  "contract_version": "mutation_materialization_v1",
  "wire_version": "1.0.0",
  "entries": [ <MaterializationEntry>, ... ],
  "digest": "<64-hex>"
}
```

- `contract_version="mutation_materialization_v1"`, `wire_version="1.0.0"`,
  closed top-level key set `{contract_version, wire_version, entries, digest}`;
  extra keys → `malformed_materialization`.
- `digest` binds the envelope **to the accompanying delta ops**, not merely to
  its own entries. Exact preimage:

  ```
  digest = sha256Hex({
    contract_version: "mutation_materialization_v1",
    wire_version: "1.0.0",
    entries: <normalized entries, ascending by source_op_index>,
    accompanying_ops_digest: sha256Hex(<accompanyingOps canonical form>)
  })
  ```

  `accompanying_ops_digest` is the canonical hash of the **exact** ops array the
  envelope is bound to (`operation.ops` forward, or
  `restoration_strategy.payload.ops` inverse — §3.1). This makes re-binding an
  envelope to a different delta with an `add_node` at the same index detectable.
  The envelope does **not** store `accompanying_ops_digest` as a field; it is
  recomputed by the validator from the `accompanyingOps` argument and folded
  into the digest. Mismatch → `mutation_materialization_digest_mismatch` (the
  diagnostic carries `detail.accompanying_ops_bound=true` so a rebind is
  distinguishable from a tampered entry).

### 2.3 Entry shape — exact source-op binding, native construction data only

A materialization envelope accompanies **one** delta envelope — either the
forward `operation.ops` or an inverse `restoration_strategy.payload.ops` (§3.1).
Each entry binds exactly one `add_node` op **in that accompanying envelope** and
carries only the native construction data that is **not already authoritative
in the op** (the op already carries `uid`, `node_id`, `class_type`, `fields`,
`inputs`; these MUST NOT be duplicated here) plus an opaque extension-owned
serialized payload.

```jsonc
{
  "source_op_index": <int>,        // index into the accompanying delta envelope's ops array
  "kind": "add_node",              // the ONLY permitted kind
  "widgets_values": [ ... ],       // optional; NATIVE LiteGraph widget serialization (an array)
  "pos": [n, n],                   // optional; finite initial construction geometry [number, number]
  "size": [n, n],                  // optional; finite initial construction geometry [number, number]
  "opaque": { ... }                // optional; extension-owned serialized payload, passed through untouched
}
```

Rules (closed):

- `source_op_index` is a non-negative integer. Two distinct failure modes
  (Gate #2): an index `>= accompanying_ops.length` (or negative, or
  non-integer) → `materialization_source_op_index_out_of_range` (the index does
  not address any op at all); an index that addresses an op whose `op` is not
  `add_node` → `materialization_source_op_kind_mismatch` (the op exists but is
  the wrong kind). These two diagnostics are distinct and both are asserted in
  tests (§5.1).
  **Duplicate** `source_op_index` across entries → `duplicate_materialization_source_op`.
- `kind` MUST equal `"add_node"` (the sole member of `MATERIALIZATION_KINDS`).
  Any other value → `unsupported_materialization_kind`.
- `widgets_values`, when present, MUST match the **actual native ComfyUI
  serialized contract**, which is a JSON **array** (LiteGraph serializes widget
  values positionally; confirmed by `comfy_adapter.js`
  `Array.isArray(node.widgets_values)` and by the m1 golden
  `widgets_values: ["x"]`). Non-array → `malformed_materialization_entry`.
  **Exception — `vibecomfy.exec` dynamic-IO mapping shape:** the existing
  `projection_registry_v1._widgets` path already documents that
  `vibecomfy.exec` nodes carry `widgets_values` as a JSON object (the dynamic-IO
  widget dict). For a materialization entry whose bound `add_node.class_type ==
  "vibecomfy.exec"`, `widgets_values` MAY be a JSON object with the same shape
  `_widgets` already accepts (the `io` key is stripped at projection time by the
  existing code path and is therefore non-authoritative here). This is the
  **only** object-form escape and it is pinned to the single `vibecomfy.exec`
  class type; any other class type carrying an object `widgets_values` →
  `malformed_materialization_entry`.
- `pos`/`size`, when present, MUST be `[number, number]` of correct length with
  every component normalized through `canonicalizeContractNumeric` /
  `canonicalize_contract_numeric` (§0.3.1) with
  `finiteErrorCode="non_finite_materialization"`: integer-valued floats,
  `-0.0`, and exponents are normalized to JS-compatible spelling (not
  rejected); non-finite → `non_finite_materialization`.
- `opaque`, when present, MUST be a JSON object. It is passed through
  untouched; the registry alone may later declare it non-semantic. The
  materialization contract does not interpret it.
- **No implicit links.** The canonical `add_node` op already carries its
  inbound edges as `inputs: Mapping[str, LinkSourceRef]`; every other link
  topology change is an explicit `upsert_link`/`remove_link` op. The entry has
  **no** `links`/`inputs`/`fields`/`uid`/`node_id`/`class_type` key. Presence of
  any of those → `malformed_materialization_entry`.
- Permitted keys per entry are exactly
  `{source_op_index, kind, widgets_values, pos, size, opaque}`. Extra key →
  `malformed_materialization_entry`.

### 2.4 Cross-binding with the accompanying structural delta

`assertMutationMaterializationEnvelope(envelope, { accompanyingOps })`
validates:

- `accompanyingOps` is a non-empty array of canonical delta ops (the forward
  `operation.ops` or the inverse `restoration_strategy.payload.ops`). It is the
  sole authority for what index `i` means; the envelope never carries the ops.
- every `add_node` op at index `i` in `accompanyingOps` has **exactly one**
  entry with `source_op_index=i, kind="add_node"` —
  `missing_materialization_entry` if an `add_node` has none;
- every entry's `source_op_index` resolves within range: negative, non-integer,
  or `>= accompanyingOps.length` →
  `materialization_source_op_index_out_of_range` (distinct from kind mismatch);
- every in-range `source_op_index` resolves to an `add_node` op in
  `accompanyingOps` (else `materialization_source_op_kind_mismatch`);
- no unreferenced entries (`unreferenced_materialization_entry`);
- no duplicate `source_op_index` (`duplicate_materialization_source_op`);
- `widgets_values` array/object rule follows §2.3 (class-type-pinned
  `vibecomfy.exec` exception);
- digest matches the §2.2 preimage, which folds in
  `sha256Hex(accompanyingOps)`; an envelope whose entries are unchanged but
  whose bound ops were swapped fails with
  `mutation_materialization_digest_mismatch` (`detail.accompanying_ops_bound=true`).

`accompanyingOps` is `operation.ops` for the **forward** envelope and
`restoration_strategy.payload.ops` for an **inverse** envelope (§3.1). The same
validator is reused for both directions; no second validator, no inverse-only
kind. There is **no** `remove_node_inverse` kind and no entry indexed against a
forward `remove_node` op; the inverse of `remove_node` is itself a canonical
`add_node` op living in the inverse envelope, materialized by the inverse
envelope's own entries.

### 2.5 Prepared-authority binding (extend §0.2 validator)

When `operation_family === "structural"`:

- If `operation.ops` contains ≥1 `add_node` op,
  `operation.mutation_materialization` MUST be present and pass
  `assertMutationMaterializationEnvelope(..., {accompanyingOps: operation.ops})`.
  Absent → `missing_materialization`.
- If `operation.ops` contains **no** `add_node` op,
  `operation.mutation_materialization` MUST be absent. Presence →
  `unexpected_materialization`. (A structural delta that only does
  `set_node_field`/`set_mode`/`upsert_link`/`remove_link`/`remove_node` has no
  forward construction and needs no forward materialization.)
- `operation.mutation_materialization_digest` MUST equal the recomputed digest
  whenever `operation.mutation_materialization` is present (presence parity —
  absent together).
- Transition immutability: covered by the whole-`operation` deep comparison
  (§1.5); no nested key is added.

When `operation_family === "layout"`:
`operation.mutation_materialization` MUST be absent.

### 2.6 No candidateGraph source — the BC#2 rule, encoded

The validator and the envelope carry **no** graph reference. Native
construction values (`widgets_values`, `pos`, `size`, `opaque`) come
exclusively from the materialization entry; node identity and type come
exclusively from the bound `add_node` op. The candidate graph is preview
evidence only; C2 deletes every `candidateGraph` read listed in §0.6. C0/C1 do
not touch those reads but make them statically bannable by removing the only
lawful public contract path that accepted them (the new preflight signature
takes prepared authority only).

---

## 3. Restoration binding — one mandatory slot + one prepare-owned optional compensation slot

The existing `restoration_strategy = {contract_version, digest, payload|ref}`
slot (validated today by `_restoration` / `digest()`, both of which accept
**either** `payload` **or** `ref`) is the **single, mandatory** restoration
binding point. It is minted **once** at candidate-build time and frozen
byte-identical across the candidate→prepared transition. C0 closes its
`contract_version` to the frozen enum and binds its payload shape to the
inverse-relation contract (§3.1–§3.2).

C0 also introduces **one** prepare-owned optional sibling,
`restoration_strategy_compensation` (§3.4), required by the parent task
(`m2-slices-3-4-implementation.md`: "optionally `baseline_snapshot_v1` as
compensation-only authority, with root scope, original snapshot digest/ref, and
identity/projection fence"). It is **separately digested**, **absent from
candidate authority**, and **minted only by the trusted prepare step** after
lease acquisition. It binds the prepared lease/identity/projection fences and
becomes immutable once prepared authority exists. It does **not** authorize
execution in C0/C1 — it is a contract slot only; any native compensation
restore is C2/C3 execution-time, explicitly out of scope.

### 3.0 Authority lifecycle — two restoration slots, distinct minting owners

1. **`restoration_strategy` (mandatory, candidate-owned):** `build_candidate_transaction` (Python)
   mints it exactly once when it builds `candidate_authority` (state
   `candidate_ready`). JS has no aggregate builder mirror; JS authority is
   constructed by tests via the validator directly with an explicit
   `restoration_strategy`. Frozen byte-identical across candidate→prepared.
2. **`restoration_strategy_compensation` (optional, prepare-owned):** the
   trusted prepare step **may** mint this slot **after** it has acquired the
   lease (`lease_nonce` + `generation`). It is **forbidden** in candidate
   authority (`candidate_compensation_forbidden`). On prepared authority it is
   either **absent** (prepare chose not to mint compensation) or a **valid
   compensation envelope** (§3.4). Once present on prepared authority it is
   immutable — any later mutation is `prepared_authority_transition_mismatch`.
3. **Transition rule:** `validate_candidate_transaction_v2` compares every
   standard transition-equality key (§6.5 list) by deep equality. The sole
   exception is `restoration_strategy_compensation`: candidate presence →
   `candidate_compensation_forbidden`; prepared absent → legal; prepared
   present → must pass `assert_restoration_strategy_compensation` (§3.4) and its
   fence must bind the prepared authority's own identity/projection fields.
   Prepare mints only `generation` + `lease_nonce` + optionally
   `restoration_strategy_compensation` on the prepared envelope; it does **not**
   rebind `restoration_strategy` or any other candidate-time key.

No new restoration validator owner is created; the closed key sets below are
enforced by extending `_restoration` (Python) and `digest()` (JS) in the
existing validators, with a sibling `_restoration_compensation` / `digest_compensation()`
extension for the optional slot. The m1 parity suites' placeholder payloads
(`payload: []`) are upgraded in C0 to well-formed payloads matching the closed
sets below, in both languages (§6.2 lists those test files as extended).

### 3.1 `restoration_strategy` — closed keys, two payload families + one grandfathered ref tag

`restoration_strategy` accepts exactly one of the shapes in the table. The
closed top-level key set is `{contract_version, digest}` plus **exactly one** of
`{payload, ref}` — never both, never neither. `payload` and `ref` are
mutually exclusive (presence of both → `malformed_restoration_payload`).

| `contract_version` | Family | Binding kind | Required content (closed keys) |
| --- | --- | --- | --- |
| `inverse_delta_v1` | structural | `payload` (mandatory) | `{ops, mutation_materialization, mutation_materialization_digest}` where `ops` = strict canonical delta_v1 inverse ops (validated by `ensureRootScopedOps` / `ensure_root_scoped_delta_envelope`); `mutation_materialization` + `mutation_materialization_digest` present **iff** `ops` contains ≥1 `add_node`, absent otherwise (presence parity), and cross-bound against `ops` via §2.4. |
| `inverse_layout_operation_v1` | layout | `payload` (mandatory) | `{layout_operation, layout_operation_digest}` where `layout_operation` passes `assertLayoutOperationEnvelope` and `layout_operation_digest` equals its recomputed digest. |
| `baseline_snapshot_v1` | either (legacy) | `ref` (grandfathered, **only** this tag) | `{ref}` where `ref` is a non-empty durable ref string. **This is the sole grandfathered legacy ref shape** (Gate #7). |

**Grandfathered legacy ref tag — exact shape current code actually mints.**
`build_candidate_transaction` today produces, verbatim:

```jsonc
"restoration_strategy": {
  "contract_version": "baseline_snapshot_v1",
  "digest": "<sha256Hex(canonical(submit_graph))>",
  "ref": "original.ui.json"
}
```

This is the **only** `ref`-carrying shape the contract permits. Its `digest` is
the canonical hash of the submit graph (the baseline), bound by the
`baseline_snapshot_v1` tag. It is grandfathered because it is the active
production minting path; C0 does **not** change `build_candidate_transaction`
(forbidden: no production live-code behavior change). Any **new** authority
that wants to carry an actual inverse must use one of the `inverse_*_v1`
payload tags. No other `contract_version` may carry `ref`; no `payload`-carrying
tag may carry `ref`. Unknown `contract_version` → `unknown_restoration_strategy`.

Digest rules (extend `_restoration` / `digest()`):

- `payload`-tag digest = `sha256Hex({contract_version, payload})` via the shared
  owner (§0.3), after every numeric value in `payload` is normalized via
  `canonicalize_contract_numeric` / `canonicalizeContractNumeric` (§0.3.1). Mismatch →
  `restoration_digest_mismatch`.
- `baseline_snapshot_v1` ref-tag digest = `sha256Hex({contract_version, ref})`.
  (The grandfathered production value happens to be the submit-graph digest
  because `build_candidate_transaction` computes `restoration_digest =
  content_hash(submit_graph)`; C0 does not alter that computation. The validator
  recomputes over `{contract_version, ref}` and the C0 test for the grandfathered
  shape pins the value the builder actually emits, so the two are reconciled by
  fixture, not by silently redefining the digest.) Mismatch →
  `restoration_digest_mismatch`.

Family binding rules:

- `contract_version` MUST be one of the three tags above, else
  `unknown_restoration_strategy`.
- `inverse_delta_v1` ↔ `operation_family == "structural"`;
  `inverse_layout_operation_v1` ↔ `operation_family == "layout"`. Family
  mismatch → `restoration_family_mismatch`. `baseline_snapshot_v1` is
  family-agnostic (legacy baseline) and is accepted under either family until
  C2 retires it.
- `payload`, when present, MUST contain exactly the closed keys for its tag;
  extra/missing key → `malformed_restoration_payload`.
- Inverse values come from authoritative pre-apply capture (old field/mode, old
  named link endpoints, removed-node payload+inputs, old geometry, old group
  payload). Self-inverse and unrelated-inverse checks are enforced by §3.2.
- An inverse is **generated and bound at authority-build time** from
  authoritative captured state (never from the candidate graph, never from live
  runtime state). C0/C1 only **validate** the already-bound inverse; generating
  an inverse from live state is a **C2/C3** responsibility, out of scope here.

### 3.2 Inverse-relation contract — every forward op bound to its correct inverse (Gate #11)

A payload-tagged `restoration_strategy` is not merely "a delta that differs
from the forward delta"; its ops must be the **correct inverse** of the forward
ops, bound by identity to prior state. The validator
(`_assert_inverse_relation(forward_ops, inverse_ops, family)` /
`assertInverseRelation(forwardOps, inverseOps, family)`, added to
`projection_registry_v1.py` and `prepared_authority_v1.js` and called from the
restoration-payload branch of `_restoration` / `digest()`) enforces this.

**Identity key per op class** (the stable identity the inverse must reuse):

| Forward op | Identity key | Required inverse op class(es) | Prior-state binding the inverse MUST carry |
| --- | --- | --- | --- |
| `set_node_field` | `target[1]` (uid) | `set_node_field` (same `target`) | the pre-apply field value at `target[2]` |
| `set_mode` | `target[1]` (uid) | `set_mode` (same `target`) | the pre-apply `mode` ∈ {0,2,4} |
| `add_node` | `uid` (+`node_id`) | `remove_node` (`target=[\"\", uid]`) | none (removal is the inverse of addition); a materialization entry is NOT required on the inverse side because no node is being constructed |
| `remove_node` | `target[1]` (uid) | `add_node` (same `uid`,`node_id`,`class_type`,`fields`,`inputs`) | the pre-removal node payload + inputs; a materialization entry IS required (§2.4) because the inverse constructs a node |
| `upsert_link` | endpoint pair (`from`,`to`) | `remove_link` (`to` = the upserted endpoint) **or** `upsert_link` carrying the pre-upsert endpoints | the pre-upsert link endpoints (or absence) |
| `remove_link` | endpoint pair (`to`) | `upsert_link` (same `from`,`to`) | the pre-removal link endpoints |

Layout ops (family `layout`, `inverse_layout_operation_v1`):

| Forward op | Identity key | Required inverse op class | Prior-state binding |
| --- | --- | --- | --- |
| `set_node_geometry` | `uid` | `set_node_geometry` (same `uid`) | pre-apply `pos` (and `size` if the forward op changed it) |
| `add_group` | `id` | `remove_group` (same `id`) | none |
| `set_group_geometry` | `id` | `set_group_geometry` (same `id`) | pre-apply value(s) for each field the forward op changed |
| `remove_group` | `id` | `add_group` (same `id`) | pre-removal `bounding`,`title`,`color` |

**Algorithm** (identical JS + Python):

1. Build `forward_by_id` mapping each forward op to its identity key (above).
   Reject duplicate forward identity within one envelope → `duplicate_identity`.
2. For each inverse op, derive its identity key and look up the matching forward
   op. No matching forward op → `inverse_identity_unbound` (the inverse touches
   something the forward never touched).
3. Check the inverse op's class is the **mandated** inverse class for the
   matched forward op (table above). Wrong class → `inverse_class_mismatch`.
4. Check the inverse op carries the prior-state binding for its class. Missing
   or non-matching prior state → `inverse_missing_prior_state`.
5. Reject a forward op cloned verbatim as its own inverse (e.g. a `set_node_field`
   whose `value` equals the forward value, not the prior value) →
   `invalid_inverse_strategy`.
6. Reject an inverse sequence that is merely "non-identical but unrelated" —
   i.e. every forward op has a matched inverse, but the inverse does not
   reconstruct the prior state (caught by step 4) →
   `inverse_missing_prior_state`; and an inverse set sharing no identity with
   the forward set → `inverse_unrelated`.
7. Every forward op MUST have exactly one matching inverse op. Unmatched forward
   op → `inverse_coverage_gap`. (Order independence: inverse ops are matched by
   identity, not array position.)

**Diagnostics (all added to §4 fail-closed matrix):** `duplicate_identity`,
`inverse_identity_unbound`, `inverse_class_mismatch`,
`inverse_missing_prior_state`, `invalid_inverse_strategy`, `inverse_unrelated`,
`inverse_coverage_gap`.

**Tests (§5.1, both languages):** for each of the 6 delta + 4 layout ops, a
positive case (correct inverse class + correct prior-state binding) and at
least one negative case per failure mode (wrong class, unbound identity,
missing prior state, self-inverse, unrelated inverse, coverage gap). The m1
golden `delta_ops` corpus is reused as the forward side; inverse fixtures are
added alongside.

This relation is enforced **only for payload tags** (`inverse_delta_v1`,
`inverse_layout_operation_v1`). The grandfathered `baseline_snapshot_v1` ref
tag carries no ops and is exempt (it restores by ref, not by inverse delta).

### 3.3 Identity/projection fence (reused, not reinvented)

The `identity_fence` / `projection_fence` shape is reused verbatim from
`journal_durable_v1` (§0.5): `transaction_id`, `candidate_id`, `plan_hash`,
`lease_nonce`, positive integer `generation`, and pre/post projection digests.
It lives on `journal_durable_v1` records, **not** on `restoration_strategy`.
No second fence contract; no fence fields are added to `restoration_strategy`.
The compensation slot (§3.4) **cites** these exact fence values from the
prepared authority to bind itself; it does not invent a new fence contract.

### 3.4 `restoration_strategy_compensation` — prepare-owned optional compensation slot

A **separately digested, optional** top-level key on prepared authority only.
It carries a `baseline_snapshot_v1` compensation-only restoration ref, bound to
the prepared authority's own lease, identity, and projection fences. It is the
**sole** narrowly authorized prepare-owned additive field in the
candidate→prepared transition.

**Exact shape (frozen, identical JS+Python):**

```jsonc
{
  "contract_version": "baseline_snapshot_v1",
  "wire_version": "1.0.0",
  "ref": "<non-empty durable ref string>",
  "fence": {
    "transaction_id":  "<uuid>",
    "candidate_id":    "<uuid>",
    "plan_hash":       "<hex64>",
    "lease_nonce":     "<non-empty string>",
    "generation":      <positive int>,
    "pre_projection_digest":  "<hex64>",
    "post_projection_digest": "<hex64>"
  },
  "digest": "<64-hex>"
}
```

- Top-level keys are exactly `{contract_version, wire_version, ref, fence, digest}`.
  Extra key → `malformed_restoration_compensation`. Unknown `contract_version` →
  `unknown_restoration_strategy`. Unknown `wire_version` →
  `unsupported_wire_version`. `contract_version` MUST equal
  `"baseline_snapshot_v1"` and `wire_version` MUST equal `"1.0.0"` — the sole
  permitted tag for compensation (it is compensation-only, never an inverse
  payload).
- `fence` keys are exactly `{transaction_id, candidate_id, plan_hash,
  lease_nonce, generation, pre_projection_digest, post_projection_digest}`.
  Extra/missing fence key → `malformed_restoration_compensation`.
  `generation` MUST be a positive integer. All other fence values are non-empty
  strings; `*_digest` values MUST match `_HEX64` / `/^[0-9a-f]{64}$/`.
- **Fence binding (the anti-replay guarantee):** every `fence.*` value MUST
  equal the corresponding value on the enclosing prepared authority:
  `fence.transaction_id` == `authority.transaction_id`; `fence.candidate_id`
  == `authority.candidate_id`; `fence.plan_hash` == `authority.plan_hash`;
  `fence.lease_nonce` == `authority.lease_nonce`; `fence.generation` ==
  `authority.generation`; `fence.pre_projection_digest` ==
  `authority.precondition.digest`; `fence.post_projection_digest` ==
  `authority.postcondition.digest`. Any mismatch →
  `compensation_fence_unbound` (the compensation does not belong to this
  prepared authority and must not be accepted).
- **Digest (separately computed, does not collide with `restoration_strategy.digest`):**
  ```
  digest = sha256Hex({
    contract_version: "baseline_snapshot_v1",
    wire_version:     "1.0.0",
    ref:              <ref>,
    fence:            <fence object, verbatim>
  })
  ```
  via the shared hash owner (§0.3). The normalizer (§0.3.1) runs over `fence`
  before hashing; `generation` is always an int so normalization is a no-op
  here, but the rule is uniform. Mismatch → `compensation_digest_mismatch`.
  The envelope does **not** store a separate `accompanying_ops_digest`; the
  compensation is ref-bound, not ops-bound.

**Minting owner and time:**

- **Sole minter:** the trusted prepare step (`project_transaction_state` in
  `candidate_transaction.py`, Python), invoked only **after** `lease_nonce` and
  `generation` have been issued for this prepared authority. JS has no
  aggregate builder mirror; JS tests construct the compensation envelope via
  the validator directly.
- **Forbidden in candidate authority:** `validate_candidate_authority_v1`
  rejects `restoration_strategy_compensation` if present on candidate authority
  → `candidate_compensation_forbidden`. This mirrors the existing
  `unexpected_prepare_identity` rejection of `generation`/`lease_nonce` on
  candidate.
- **Immutable after prepared minting:** once `restoration_strategy_compensation`
  exists on a prepared authority, it is part of the prepared envelope and any
  subsequent change is `prepared_authority_transition_mismatch`.

**Absent / null rules:**

- On candidate authority: key MUST be **absent** (not `null`, not present).
  Presence of `null` → `candidate_compensation_forbidden` (same as any value;
  null is not a legal spelling of "absent").
- On prepared authority: key is either **absent** (legal — prepare chose not to
  mint compensation) or **present with a valid envelope** (§3.4 shape).
  `null` is **not** a legal value → `malformed_restoration_compensation`.
- Once a prepared authority is finalized with the compensation present, later
  transitions (e.g. `canvas_verified`, `finalized`) must carry it
  byte-identical or be `prepared_authority_transition_mismatch`.

**Distinction from the grandfathered `baseline_snapshot_v1` ref in mandatory `restoration_strategy` (§3.1):**

| Aspect | `restoration_strategy` (mandatory, §3.1) | `restoration_strategy_compensation` (optional, §3.4) |
| --- | --- | --- |
| Minting owner | candidate-build (`build_candidate_transaction`) | prepare step (after lease) |
| When minted | `candidate_ready` | `prepared` (post-lease) |
| `contract_version` tag | `inverse_delta_v1` / `inverse_layout_operation_v1` / grandfathered `baseline_snapshot_v1` (ref) | `baseline_snapshot_v1` only |
| Shape | `{contract_version, digest, payload \| ref}` | `{contract_version, wire_version, ref, fence, digest}` |
| Digest preimage | `{contract_version, payload}` or `{contract_version, ref}` | `{contract_version, wire_version, ref, fence}` |
| Fence binding | none (candidate-time, no lease yet) | binds prepared `transaction_id`/`candidate_id`/`plan_hash`/`lease_nonce`/`generation`/projections |
| Candidate presence | mandatory | forbidden |
| Authorizes execution | defines the inverse for C2/C3 native rollback | defines compensation-only snapshot restore for C2/C3; **not** authorized in C0/C1 |

The mandatory `restoration_strategy`'s grandfathered `baseline_snapshot_v1`
ref (§3.1) is a **candidate-time** baseline pointer with no fence binding and
no `wire_version`; it is the active production minting path today. The
compensation slot is a **prepare-time** separately-digested envelope that binds
the lease and projections; it is a new C0 contract path. They are distinct
top-level keys with distinct digest preimages; neither shadows the other.

**Does NOT authorize execution in C0/C1.** The compensation slot is a contract
definition and validation target only. C0 adds the validator
(`_restoration_compensation` / `assert_restoration_strategy_compensation`,
extending the existing `_restoration` / `digest()` owners in
`projection_registry_v1.py` and `prepared_authority_v1.js`) and the
transition-rule special case. C1's plan builder may re-validate the
already-bound compensation digest; it does **not** execute a compensation
restore. Native compensation restore belongs to C2/C3.

**Schema closure:** the compensation key is added to the prepared-authority
closed key set as an optional member. Its absence is legal; its presence
requires the full §3.4 shape. No other new top-level key is added to prepared
or candidate authority.

---

## 4. Fail-closed matrix — enforced identically JS + Python before any native call

Every row MUST throw a typed diagnostic (`.code`) from the contract owner or
the prepared-authority validator, in both languages, **before** any native
acquire/mutate call. C0 covers contract/authority failures; C1 additionally
proves zero native primitive calls on each via sentinel instrumentation of the
private plan builder (§6.3, §6.6).

| Condition | Diagnostic code | Owner |
| --- | --- | --- |
| Unknown contract name (`layout_operation_v1`/`mutation_materialization_v1` mismatch) | `unknown_contract` | new owners |
| Unknown wire version | `unsupported_wire_version` | new owners |
| Unknown/extra envelope or op key | `malformed_layout_operation` / `malformed_materialization` / `malformed_layout_op` / `malformed_materialization_entry` | new owners |
| Unknown layout op name | `unsupported_layout_op` | `layout_operation_v1` |
| Unsupported materialization kind (anything but `add_node`) | `unsupported_materialization_kind` | `mutation_materialization_v1` |
| Unknown operation family / projection / authority version | `unknown_operation_family` / `unknown_projection_version` / `unknown_authority_version` | §0.2 validators |
| Non-root or nested scope (definitions, group `scope_path!=""`) | `unsupported_scope` | `root_scope_v1` / `projection_registry_v1` |
| Nested definitions in authority operation | `unsupported_scope` | §0.2 + §1.5 |
| Missing stable node/group id | `missing_identity` | `projection_registry_v1` |
| Duplicate stable id within one envelope (two ops same uid/id where uniqueness required) | `duplicate_identity` | new owners |
| Duplicate titles | **valid** (no diagnostic) | n/a |
| Non-finite geometry | `non_finite_geometry` | `layout_operation_v1` / `mutation_materialization_v1` |
| Boolean or unsafe-range integer (`abs > 2^53−1`) in a numeric position (the only non-normalizable numeric inputs; `1.0`, `-0.0`, exponents are normalized, not rejected) | `non_canonical_number` | new owners (§0.3.1) |
| Digest mismatch (layout/materialization/restoration/projection/authority receipt/compensation) | `<*_digest_mismatch>` / `restoration_digest_mismatch` / `compensation_digest_mismatch` | respective owners |
| Unreferenced materialization entry | `unreferenced_materialization_entry` | §2.4 |
| `add_node` op with no matching materialization entry | `missing_materialization_entry` | §2.4 |
| Duplicate materialization `source_op_index` | `duplicate_materialization_source_op` | §2.4 |
| Materialization `source_op_index` negative / non-integer / `>= ops.length` | `materialization_source_op_index_out_of_range` | §2.3 (distinct from kind mismatch) |
| Materialization index points at non-`add_node` op | `materialization_source_op_kind_mismatch` | §2.4 |
| Materialization `widgets_values` not an array (or non-`vibecomfy.exec` object form) | `malformed_materialization_entry` | §2.3 |
| Materialization entry carrying a forbidden key (`links`/`inputs`/`fields`/`uid`/`node_id`/`class_type`) | `malformed_materialization_entry` | §2.3 |
| Materialization envelope re-bound to different accompanying ops (digest folds in `sha256Hex(ops)`) | `mutation_materialization_digest_mismatch` (`detail.accompanying_ops_bound=true`) | §2.2/§2.4 |
| Layout family with non-empty structural ops | `layout_family_requires_empty_structural_ops` | §1.5 |
| Structural family carrying `layout_operation` | `unexpected_layout_operation` | §1.5 |
| Structural family with `add_node` missing materialization | `missing_materialization` | §2.5 |
| Structural family without `add_node` carrying materialization | `unexpected_materialization` | §2.5 |
| Structural witness pre≠post (layout) | `layout_structural_witness_mismatch` | §0.2 (exists) |
| Prepared authority mutated candidate-time authority (any standard transition-equality key, §6.5) | `prepared_authority_transition_mismatch` | §0.2 (exists) |
| Candidate authority carries `restoration_strategy_compensation` (any value, incl. `null`) | `candidate_compensation_forbidden` | §3.4 (new) |
| Prepared `restoration_strategy_compensation` present but malformed (bad shape, missing/extra key, bad digest, fence not matching prepared authority) | `malformed_restoration_compensation` / `compensation_digest_mismatch` / `compensation_fence_unbound` | §3.4 (new) |
| Restoration `contract_version` unknown; tag↔family mismatch; `payload`+`ref` both/neither | `unknown_restoration_strategy` / `restoration_family_mismatch` / `malformed_restoration_payload` | §3.1 |
| Restoration payload missing/extra closed key; tampered digest | `malformed_restoration_payload` / `restoration_digest_mismatch` | §3.1 |
| Inverse class wrong for its forward op | `inverse_class_mismatch` | §3.2 |
| Inverse op identity not present in forward ops | `inverse_identity_unbound` | §3.2 |
| Inverse missing required prior-state binding | `inverse_missing_prior_state` | §3.2 |
| Inverse shares no identity with forward (merely non-identical, unrelated) | `inverse_unrelated` | §3.2 |
| Forward op with no matching inverse | `inverse_coverage_gap` | §3.2 |
| Self-inverse (forward op cloned as inverse, same value not prior) | `invalid_inverse_strategy` | §3.2 |
| Forbidden `workflow_v1` projection | `forbidden_projection` | `projection_registry_v1` (exists) |

**Post-mutation failure handling (landed-prefix, partial-mutation evidence,
serialization-after-mutation, inverse execution, repaint, fault-after-write) is
out of scope for C0 and C1.** Those proofs belong to C2/C3, where native
execution first becomes legal. C0 only encodes the validator-side closed key
sets and digests above; C1 only proves the validator + plan builder make zero
native calls.

---

## 5. Browser/Python golden parity + negative mutation corpus

### 5.1 Golden fixtures (new)

`tests/fixtures/agent_edit/layout_operation_golden_v1.json`:

```jsonc
{
  "contract_version": "layout_operation_golden_v1",
  "cases": [
    { "id": "...", "ops": [], "expected_envelope": {}, "expected_digest": "<hex64>" }
  ],
  "negative_cases": [
    { "id": "...", "ops": [], "expected_code": "..." }
  ]
}
```

Required positive cases (each appears in `cases` and is asserted by both JS and
Python tests against the same `expected_digest`):

1. `set_node_geometry` pos-only.
2. `set_node_geometry` pos+size.
3. `add_group` full payload.
4. `add_group` color=null.
5. `set_group_geometry` bounding-only.
6. `set_group_geometry` title-only (rename, duplicate-title-safe).
7. `set_group_geometry` color-only.
8. `remove_group`.
9. Multi-op sequence mixing all four.
10. Duplicate titles across two `add_group` ops (distinct ids) — succeeds.
11. **`a66422e6 regression anchor (Gate #9) — three domain-labelled digests, kept separate.**
    The fixture `tests/fixtures/agent_edit/a66422e6_layout_regression.json` is a
    **legacy group-normalization regression**: its `original` graph carries
    native-integer group ids (`id: 7`, `id: 12`) with **no** `vibecomfy_group_id`,
    so it **cannot** pass the new `layout_v1` projection
    (`group_identity_v1` rejects it with `missing_identity`). It therefore
    cannot be reduced to a `layout_operation_v1` ops golden directly. Three
    distinct digests are pinned in the golden, each **explicitly domain-labelled**
    and never conflated:

    - **Fixture-integrity digest (informational, not a contract/projection
      digest):** the raw SHA-256 of the 3,569-byte fixture file on disk:
      ```
      fixture_raw_sha256 =
        "09e01de2c658b33180d9836db2d925a208459cff970cb7b2aa9ae7442edd0534"
      ```
      Both JS and Python tests read the file bytes (via `fs.readFileSync` /
      `path.read_bytes`) and assert `sha256(bytes) ==` this hex64. This is an
      **informational fixture-integrity assertion** — it detects accidental
      edits to the regression fixture; it is **not** a projection digest, not a
      layout-operation digest, and not a structural-witness digest. It is
      labelled `domain: "fixture_integrity_raw_file"` in the golden so no test
      consumer mistakes it for a contract digest.

    - **Structural-witness digest (domain: `"structural_witness_v1"`):** the
      cross-language parity sentinel the incident actually proved
      (`buildStructuralGraphProjection(original)` ==
      `buildStructuralGraphProjection(candidate)`):
      ```
      expected_structural_witness_digest =
        "2bf4f6b53ac2e8d575c7d5739a1b1b143e3b1709cb61503f4523bf759bad2906"
      ```
      (value computed from the actual fixture via
      `sha256(canonical_json_bytes(build_structural_graph_projection(fx["original"])))`;
      both sides recompute and assert byte-equality to this exact hex64).

    - **Layout-operation digest (domain: `"layout_operation_v1"`):** a
      **separate** derived golden case (`id:
      "a66422e6-derived-candidate-groups"`) reduces the fixture's
      `candidate.groups` (which DO carry stable ids `prompt-text-a` /
      `prompt-text-b`) to two `add_group` ops plus a `set_node_geometry` op for
      each candidate node uid, with its `expected_digest` computed at
      fixture-generation time via `computeLayoutOperationDigest` (after
      numeric normalization, §0.3.1) and pinned.

Required negative cases (assert exact `expected_code`, both languages):

- unknown op (`move_node`) → `unsupported_layout_op`
- unknown version (`1.0.1`) → `unsupported_wire_version`
- extra top-level key → `malformed_layout_operation`
- extra per-op key → `malformed_layout_op`
- missing `uid` → `missing_identity`
- missing group `id` → `missing_identity`
- non-finite pos (`NaN`,`Infinity`) → `non_finite_geometry`
- **numeric-normalization parity** (positive cases proving byte-identical
  digest preimages after normalization, §0.3.1): `pos: [1.0, -0.0]`,
  `pos: [1e2, 200]`, and `pos: [1, 0]` each produce the **same**
  `expected_digest` in both JS and Python — the normalizer coerces
  integer-valued floats / `-0.0` / exponents to their JS-compatible integer
  spelling, so the digest is byte-identical to the ordinary-integer spelling.
  These are asserted as three distinct positive parity cases, not rejections.
- boolean in a numeric position (Python `True`) → `non_canonical_number`
  (the sole remaining trigger for this code; §0.3.1)
- `set_group_geometry` with no changed value → `malformed_layout_op`
- title-only identity attempt (op keyed by title) → not representable; covered
  by missing-id case
- tampered digest → `layout_operation_digest_mismatch`

`tests/fixtures/agent_edit/mutation_materialization_golden_v1.json`:

```jsonc
{
  "contract_version": "mutation_materialization_golden_v1",
  "cases": [
    { "id": "...", "accompanying_ops": [], "entries": [], "expected_envelope": {}, "expected_digest": "<hex64>" }
  ],
  "negative_cases": [
    { "id": "...", "accompanying_ops": [], "entries": [], "expected_code": "..." }
  ]
}
```

Required positive cases:

1. Single `add_node` + one entry (kind `add_node`, `source_op_index=0`).
2. `add_node` + entry carrying `widgets_values` as a **JSON array**
   (e.g. `["latent"]`, matching the native LiteGraph serialization and the m1
   golden `widgets_values: ["x"]`).
3. `add_node` with `class_type: "vibecomfy.exec"` + entry carrying
   `widgets_values` as a **JSON object** (the dynamic-IO exception, §2.3); a
   second `vibecomfy.exec` case carrying an `io` key proves it is passed
   through untouched (non-authoritative).
4. `add_node` + entry carrying `pos`/`size` + `opaque`.
5. Two `add_node` ops + two entries (indices 0 and 1), interleaved with
   `upsert_link`/`set_node_field`/`set_mode` ops that have **no** entries.
6. The full forward chain
   `add_node→add_node→upsert_link→set_node_field→set_mode→remove_link→remove_node`
   with entries only for the two `add_node` ops.
7. **Inverse materialization:** an inverse envelope whose `ops` contain one
   `add_node` (the re-add inverting a forward `remove_node`) plus its own
   single `add_node` entry indexed into the **inverse** ops — proving the same
   validator handles both directions and there is no `remove_node_inverse`
   kind.
8. **Rebind detection:** the same valid entries + a *different* accompanying
   `ops` array (an `add_node` at the same index but different `uid`) MUST fail
   `mutation_materialization_digest_mismatch` with
   `detail.accompanying_ops_bound=true` (§2.2).

Required negative cases:

- duplicate `source_op_index` → `duplicate_materialization_source_op`
- **index out of range** (`source_op_index >= accompanying_ops.length`, negative,
  or non-integer) → `materialization_source_op_index_out_of_range` (distinct
  from the next row)
- index in range but pointing at `set_node_field`/`upsert_link`/`remove_node`
  → `materialization_source_op_kind_mismatch`
- an `add_node` with no entry → `missing_materialization_entry`
- unreferenced entry → `unreferenced_materialization_entry`
- entry carrying a forbidden `links`/`inputs`/`fields`/`uid`/`node_id`/`class_type`
  key → `malformed_materialization_entry`
- `widgets_values` as a non-array for a non-`vibecomfy.exec` class type →
  `malformed_materialization_entry`
- `widgets_values` as an object for a non-`vibecomfy.exec` class type →
  `malformed_materialization_entry`
- unsupported `kind` (e.g. `"remove_node_inverse"`) →
  `unsupported_materialization_kind`
- extra entry key → `malformed_materialization_entry`
- **numeric-normalization parity** (positive): `pos: [1.0, -0.0]` produces
  the same digest as `pos: [1, 0]` in both languages (§0.3.1)
- boolean in a numeric position → `non_canonical_number` (sole remaining
  trigger)
- tampered digest → `mutation_materialization_digest_mismatch`

**Inverse-relation golden** (`tests/fixtures/agent_edit/inverse_relation_golden_v1.json`,
new): for each of the 6 delta ops + 4 layout ops, one positive case (forward op
+ its correct inverse class carrying the correct prior-state binding) and the
negative cases enumerated in §3.2 (`inverse_class_mismatch`,
`inverse_identity_unbound`, `inverse_missing_prior_state`, `inverse_unrelated`,
`inverse_coverage_gap`, `invalid_inverse_strategy`). The forward side reuses
the m1 golden `delta_ops` corpus; both JS and Python assert every code exactly.

### 5.2 Cross-language parity assertion

Both `tests/browser/layout_operation_v1.test.mjs` and
`tests/test_layout_operation_v1.py` load the **same** golden file and assert,
for every case:

- `normalizeLayoutOperationV1`/`normalize_layout_operation_v1` returns the
  exact `expected_envelope` byte-for-byte;
- recomputed digest equals `expected_digest`;
- every negative case throws with the exact `expected_code`.

Same pattern for `mutation_materialization_v1` tests, including the
`accompanyingOps` argument to `assertMutationMaterializationEnvelope`. This is
the same parity discipline already used by `m1_projection_golden_v1.json`
(see `tests/browser/m1_contracts.test.mjs` + `tests/test_m1_contracts.py`).

### 5.3 Authority binding tests (extend existing parity suites)

Extend `tests/browser/m1_contracts.test.mjs` and `tests/test_m1_contracts.py`
with cases that build candidate/prepared authority and assert:

- layout family binds `operation.layout_operation` + digest; empty structural
  ops; structural witness enforced; whole-`operation` transition immutability
  covers the new nested keys;
- structural family binds `operation.mutation_materialization` exactly when
  `add_node` present; absent otherwise;
- `restoration_strategy` binds the correct tag for the family
  (`inverse_delta_v1`/`inverse_layout_operation_v1` payload, or the grandfathered
  `baseline_snapshot_v1` ref shape §3.1); candidate→prepared transition freezes
  `restoration_strategy` byte-identical;
- **compensation slot (§3.4):** candidate authority with
  `restoration_strategy_compensation` present (any value incl. `null`) →
  `candidate_compensation_forbidden` in both languages; prepared authority
  with compensation **absent** → legal; prepared authority with a **valid**
  compensation envelope → passes `assert_restoration_strategy_compensation`,
  its fence binds the prepared authority's own
  `transaction_id`/`candidate_id`/`plan_hash`/`lease_nonce`/`generation`/
  `precondition.digest`/`postcondition.digest`, and its separately-computed
  digest matches; prepared authority with a compensation whose fence cites a
  **different** prepared authority's identity → `compensation_fence_unbound`;
  prepared authority with a tampered compensation digest →
  `compensation_digest_mismatch`; prepared authority with a malformed
  compensation shape → `malformed_restoration_compensation`; once present, any
  mutation across `prepared`→`canvas_verified`→`finalized` →
  `prepared_authority_transition_mismatch`;
- the §3.2 inverse-relation validator accepts a correct inverse and rejects
  each §3.2 failure mode with the exact code, in both languages;
- each §4 fail-closed row raises the exact code in both languages;
- forbidden `workflow_v1` still raises `forbidden_projection`.

Extend `tests/test_candidate_transaction_layout_contract.py` to assert the
layout candidate transaction now carries the layout operation envelope and
digest and that tampering fails closed.

---

## 6. Files, APIs, schema, order, tests, commands, guards — exact

### 6.1 New files (C0)

```
vibecomfy/comfy_nodes/agent/_canonical_contract_primitives.py   (leaf: relocated hash + ContractError + canonicalize_contract_numeric; re-exported unchanged by projection_registry_v1.py)
vibecomfy/comfy_nodes/web/layout_operation_v1.js
vibecomfy/comfy_nodes/agent/layout_operation_v1.py
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py
tests/fixtures/agent_edit/layout_operation_golden_v1.json
tests/fixtures/agent_edit/mutation_materialization_golden_v1.json
tests/fixtures/agent_edit/inverse_relation_golden_v1.json
tests/browser/layout_operation_v1.test.mjs
tests/browser/mutation_materialization_v1.test.mjs
tests/browser/inverse_relation_v1.test.mjs
tests/test_layout_operation_v1.py
tests/test_mutation_materialization_v1.py
tests/test_inverse_relation_v1.py
```

### 6.2 Extended files (C0) — extend, never duplicate

```
vibecomfy/comfy_nodes/agent/projection_registry_v1.py    (import primitives from leaf + re-export; extend _restoration for the closed tag set + ref grandfather + inverse-relation check; add _restoration_compensation for §3.4; transition list gains restoration_strategy_compensation with prepare-owned-additive semantics)
vibecomfy/comfy_nodes/web/prepared_authority_v1.js       (extend digest() for the closed tag set + ref grandfather + inverse-relation check; add digest_compensation() / assertRestorationStrategyCompensation for §3.4; transition list gains restoration_strategy_compensation)
vibecomfy/comfy_nodes/agent/candidate_transaction.py     (build_candidate_transaction keeps minting the grandfathered baseline_snapshot_v1 ref; add layout/materialization envelope minting when supplied; project_transaction_state (prepare) may optionally mint restoration_strategy_compensation after lease issuance)
tests/browser/m1_contracts.test.mjs                      (authority binding + fail-closed parity; restoration payloads upgraded from placeholder [] to well-formed inverse payloads; compensation positive/negative cases)
tests/test_m1_contracts.py                               (mirror)
tests/test_candidate_transaction_layout_contract.py      (layout envelope + restoration parity + compensation parity in transaction)
```

### 6.3 C1-only new files (private pure plan proof; no production consumer; no native writes)

```
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs         (PRIVATE pure module: no app/DOM/LiteGraph imports; builds a frozen plan from prepared authority only)
tests/browser/harness.mjs                                        (EXTERNALLY-OWNED sentinel instrumentation at every native primitive boundary: factory/configure, add/remove node, connect, removeLink, widget/mode, socket repair, group construct/configure/add/remove, geometry assign, repaint, serialize)
tests/browser/prepared_plan_builder_v1.test.mjs                  (zero-native-call proof for every validation/preflight case, asserted from OUTSIDE the builder; frozen-plan shape assertions; already-bound inverse/restoration digest validation)
tests/browser/prepared_plan_builder_ownership_static.test.mjs    (static reachability: FAIL if the builder can reach any native primitive; FAIL if any production file imports the private builder or exports a new public mutation method; FAIL if candidateGraph appears in any preflight/apply signature outside the legacy C2 allowlist)
```

`_prepared_plan_builder_v1.mjs` exports a single pure function:

```
buildPreparedPlan(preparedAuthority) -> { ok: true, plan: Frozen<PlanShape> }
   | { ok: false, diagnostic: { code, detail } }
```

**No self-attestation (Gate #4).** The builder does **not** return
`sentinelCounts`, does **not** install sentinels, and does **not** report its
own zero-native-call proof. The subject cannot be the source of its own
evidence. Zero-native-call evidence is produced and asserted **entirely outside**
the builder, by the externally-owned harness (§6.3 line 2) and by static
reachability analysis (§6.3 line 4):

- **Externally-owned harness counters.** `tests/browser/harness.mjs` owns a
  throwaway instrumented graph object whose every native primitive method
  (factory/configure, add/remove node, connect, removeLink, widget/mode, socket
  repair, group construct/configure/add/remove, geometry assign, repaint,
  serialize) is wrapped by a sentinel that increments an **externally-held**
  counter and throws a sentinel marker. The builder receives this instrumented
  graph as an ordinary argument only if it were to call into it; because it is
  pure and prepared-authority-only, it never reaches any sentinel. The test
  (§6.6 step 11) reads the counters **from the harness**, never from the
  builder's return value.
- **Static reachability.**
  `tests/browser/prepared_plan_builder_ownership_static.test.mjs` parses the
  builder's import graph (AST) and asserts the transitive import closure of
  `_prepared_plan_builder_v1.mjs` excludes `comfy_adapter.js`,
  `intent_graph_adapter.js`, LiteGraph, DOM, and any module exporting a native
  primitive. This proves zero-native-call without runtime counters at all — a
  second, independent line of evidence.

**No circular dependency injection (Gate #4 + #8).** The builder takes
**prepared authority only** as its sole argument — it does **not** receive the
asserters, the hash function, or the error classes as injected arguments. That
injection pattern let the subject select its own proof identity (Gate #8:
invented hash-injection owner). Instead the builder imports the C0 contract
modules and `canonical_hash.js` **directly by name** at module top level, so
the hashing identity is fixed at import time and cannot be swapped by a caller:

```
import { assertLayoutOperationEnvelope, LayoutOperationError } from "./layout_operation_v1.js";
import { assertMutationMaterializationEnvelope, MutationMaterializationError } from "./mutation_materialization_v1.js";
import { sha256Hex } from "./canonical_hash.js";
```

- It validates every §4 condition via these directly-imported asserters.
- It builds a **frozen** `PlanShape` (a pure description of intended primitives
  — never executed) and re-validates the already-bound `restoration_strategy`
  digest by recomputation (and re-validates the optional
  `restoration_strategy_compensation` digest if present, §3.4).
- It does **not** generate an inverse from live state; it only re-checks the
  already-bound inverse digest and runs the §3.2 inverse-relation check against
  the bound inverse ops.
- It does **not** import `comfy_adapter.js`, `intent_graph_adapter.js`,
  LiteGraph, or anything that can touch the DOM/runtime graph.
- Purity is enforced by the static-reachability test above, not by trusting the
  builder's own return value.

### 6.4 Exported APIs (C0) — exact surface

JS `layout_operation_v1.js`: `LAYOUT_OPERATION_CONTRACT_V1`,
`LAYOUT_OPERATION_WIRE_VERSION`, `LAYOUT_OPERATION_OP_NAMES`,
`LayoutOperationError`, `normalizeLayoutOperationV1`,
`computeLayoutOperationDigest`, `assertLayoutOperationEnvelope`,
`default` object re-export.

JS `mutation_materialization_v1.js`: `MUTATION_MATERIALIZATION_CONTRACT_V1`,
`MUTATION_MATERIALIZATION_WIRE_VERSION`,
`MATERIALIZATION_KINDS = Object.freeze(["add_node"])` (singleton closed set;
`add_node` is the only legal kind),
`MutationMaterializationError`, `normalizeMutationMaterializationV1`,
`computeMutationMaterializationDigest`, `assertMutationMaterializationEnvelope`.

Python mirrors in snake_case. `LayoutOperationError(ContractError)` and
`MutationMaterializationError(ContractError)` where `ContractError(ValueError)`
is imported from `_canonical_contract_primitives.py` (§0.3, matching the
existing base in code). `canonical_json_bytes_v1` / `canonical_json` /
`canonicalize_contract_numeric` imported
from the same leaf. `MATERIALIZATION_KINDS = ("add_node",)` (frozen tuple).
Both `normalize_layout_operation_v1` / `normalizeLayoutOperationV1` and
`normalize_mutation_materialization_v1` / `normalizeMutationMaterializationV1`
call `canonicalize_contract_numeric` / `canonicalizeContractNumeric` on the
ops/entries before computing the digest, so the normalized envelope stored on
the authority carries JS-compatible numeric spellings in both languages.

### 6.5 Schema keys/types and transition set (frozen)

Layout op identity: `uid`/`id` → non-empty string.
Geometry: arrays of finite numbers (pos/size len 2; bounding len 4); all
numeric components normalized to JS-compatible spelling per §0.3.1
(integer-valued floats, `-0.0`, and exponents are normalized, not rejected;
non-finite → `non_finite_geometry`).
Materialization `source_op_index`: integer ≥ 0 (range/kind checked at §2.3/§2.4
with distinct diagnostics).
Materialization `kind`: exactly `"add_node"`.
Materialization `widgets_values`: JSON **array** (native LiteGraph), or JSON
object **only** when the bound `add_node.class_type == "vibecomfy.exec"` (§2.3).
Materialization entry keys: exactly `{source_op_index, kind, widgets_values,
pos, size, opaque}`; `widgets_values`/`pos`/`size`/`opaque` each optional.
Digests: 64-char lowercase hex via shared canonical hash.
Restoration `restoration_strategy.contract_version`: closed enum
`{inverse_delta_v1, inverse_layout_operation_v1, baseline_snapshot_v1}`.
`inverse_*_v1` carry `payload` (family-bound); `baseline_snapshot_v1` carries
`ref` (grandfathered, §3.1). `payload` and `ref` are mutually exclusive.
All envelopes: closed key sets; extras fail closed.

Candidate→prepared transition-equality key set (frozen, identical JS+Python;
C0 adds exactly **one** key to the literal list already in
`validate_candidate_transaction_v2` in both languages — every existing key
retains deep-equality semantics; the new key has special prepare-owned-additive
semantics described below):

```
transaction_id, candidate_id, session_id, turn_id, plan_hash, workflow_id,
scope, operation, operation_family, precondition, postcondition,
rollback_projection, restoration_strategy, restoration_strategy_compensation,
authority_receipt_contract_version, authority_receipt_delta_schema,
authority_receipt_digest
```

**Exactly one new top-level transition key is added:**
`restoration_strategy_compensation`. It is the **sole prepare-owned additive**
field: its semantics differ from every other transition key — candidate
presence is forbidden; prepared absence or valid presence is allowed (§3.4).
Because `operation` is compared as a whole mapping (deep), every nested new key
(`operation.layout_operation`, `operation.layout_operation_digest`,
`operation.mutation_materialization`, `operation.mutation_materialization_digest`)
is already immutable across the transition.

**Absent-vs-null parity (Gate #5) — every optional key, closed rule.** "Absent"
(key not present) and "null" (key present with JSON `null`) are **distinct** and
must not be conflated. The candidate→prepared comparison treats them so:

| Key | Candidate value | Prepared value | Diagnostic on divergence |
| --- | --- | --- | --- |
| any transition-equality top-level key (list above) | `V` | must equal `V` byte-identical (deep) | `prepared_authority_transition_mismatch` |
| `operation.layout_operation` | absent (structural family) | must be absent | `prepared_authority_transition_mismatch` |
| `operation.layout_operation` | present (layout family) | must be byte-identical | `prepared_authority_transition_mismatch` |
| `operation.mutation_materialization` | absent (no `add_node`) | must be absent | `prepared_authority_transition_mismatch` |
| `operation.mutation_materialization` | present (≥1 `add_node`) | must be byte-identical | `prepared_authority_transition_mismatch` |
| `operation.mutation_materialization_digest` | follows materialization presence parity | follows materialization presence parity | `prepared_authority_transition_mismatch` |
| `structural_witness` | present (layout) / absent (structural) | same | `prepared_authority_transition_mismatch` |
| optional materialization entry field (`widgets_values`/`pos`/`size`/`opaque`) | absent | must be absent | `malformed_materialization_entry` (intra-envelope) — and the whole entry is immutable across transition via `operation` |
| optional materialization entry field | `null` | `null` is **not permitted** for these fields (they are "absent or a value", never null) → `malformed_materialization_entry` | n/a (rejected at validation) |
| `restoration_strategy.ref` | present (baseline_snapshot_v1) | byte-identical | `prepared_authority_transition_mismatch` |
| `restoration_strategy.payload` | present (inverse_*_v1) | byte-identical | `prepared_authority_transition_mismatch` |
| `restoration_strategy_compensation` | **absent** (candidate authority never mints it; any value incl. `null` → `candidate_compensation_forbidden`) | **absent** (legal — prepare chose not to mint) OR **present with valid §3.4 envelope** (byte-identical across `prepared`→`finalized`) | `candidate_compensation_forbidden` / `malformed_restoration_compensation` / `compensation_digest_mismatch` / `compensation_fence_unbound` / `prepared_authority_transition_mismatch` |

Rule of thumb: for the new contract fields, **`null` is never a legal value** —
an optional field is either present with a typed value or absent. This closes
the absent/null ambiguity that the existing `_restoration`/`digest()` left open
(they accepted `"payload" in value or "ref" in value` without distinguishing
`null`). The compensation slot follows the same rule: on candidate it must be
absent (never `null`); on prepared it is absent or a full envelope (never
`null`).

### 6.6 Implementation order (C0 then C1)

C0:

1. Create leaf `_canonical_contract_primitives.py` (relocate `ContractError`,
   `canonical_json`, `canonical_json_bytes_v1`, `_hash`,
   `_order_json_objects_utf16` verbatim; **add** `canonicalize_contract_numeric`
   per §0.3.1); add `canonicalizeContractNumeric` to `canonical_hash.js`;
   update `projection_registry_v1.py` to import + re-export them
   (behavior-preserving; all existing tests stay green — the normalizer is not
   called by any existing entry point).
2. `layout_operation_v1.{js,py}` + golden + tests (§1, §5.1) — each
   `normalize_*` / `compute_*_digest` calls `canonicalize_contract_numeric` /
   `canonicalizeContractNumeric` before hashing.
3. `mutation_materialization_v1.{js,py}` + golden + tests (§2, §5.1) — same
   normalizer before hashing.
4. Restoration strategy closed tag set + grandfathered ref + inverse-relation
   check in `_restoration`/`digest()` (§3.1–§3.3) — both languages. **Add**
   the `restoration_strategy_compensation` validator
   (`_restoration_compensation` / `assert_restoration_strategy_compensation`,
   extending the existing owners; §3.4) and the transition-rule special case
   (candidate presence → `candidate_compensation_forbidden`; prepared absent or
   valid present; §6.5). **Do NOT** change `build_candidate_transaction`'s
   mandatory `restoration_strategy` minting (it keeps emitting the grandfathered
   `baseline_snapshot_v1` ref); the compensation slot is minted only by the
   prepare step (`project_transaction_state`), optionally, after lease issuance.
5. Extend `prepared_authority_v1.js` + `projection_registry_v1.py`
   `_validate_candidate_authority_common`/`validateAuthorityCommon` (§1.5, §2.5,
   §3, §3.4). Do NOT add nested transition keys for `operation.*` (already
   covered by whole-`operation`); DO add `restoration_strategy_compensation` as
   the sole top-level transition-equality key with prepare-owned-additive
   semantics (§6.5).
6. Extend `candidate_transaction.py:build_candidate_transaction` to mint the
   new layout/materialization envelopes + digests; extend
   `project_transaction_state` (prepare step) to optionally mint
   `restoration_strategy_compensation` after lease issuance; extend
   `validate_candidate_transaction` recompute checks.
7. Extend `m1_contracts` parity suites + layout/restoration transaction test
   (§5.3) including compensation positive and negative cases.
8. Run §6.8 commands; record counts.

C1 (only after C0 is green; **no native writes anywhere**):

9. Add `_prepared_plan_builder_v1.mjs` (§6.3) — pure, prepared-authority-only,
   importing the C0 contract modules + `canonical_hash.js` **by name** (no
   dependency injection of asserters/hash).
10. Extend `tests/browser/harness.mjs` with **externally-owned sentinel
    instrumentation** (not fault execution) at every native primitive boundary.
    Each sentinel increments a counter held **by the harness** (not the builder)
    and blocks the call (throws a sentinel marker). Sentinels are installed into
    a throwaway harness graph; the plan builder never reaches them because it
    takes only prepared authority.
11. Add `tests/browser/prepared_plan_builder_v1.test.mjs`: for every
    validation/preflight case (every §4 fail-closed row plus the positive
    cases), call `buildPreparedPlan(preparedAuthority)` and assert, **reading
    the counters from the harness** (never from the builder return value), that
    every sentinel count is exactly `0` (zero native primitive calls), and that
    the frozen plan + already-bound inverse/restoration digests validate
    (including the optional `restoration_strategy_compensation` digest if
    present — re-validated, never generated). For
    invalid authority, assert the builder returns `{ok:false,
    diagnostic:{code}}` with the exact §4 code and that all harness sentinels
    still read zero. The builder return value is `{ok, plan|diagnostic}` only —
    no `sentinelCounts` field exists.
12. Add `tests/browser/prepared_plan_builder_ownership_static.test.mjs` that
    **fails** if any file under `vibecomfy/comfy_nodes/web/` (other than the
    builder itself and test files) imports `_prepared_plan_builder_v1`, if the
    builder's transitive import closure reaches any runtime/DOM/adapter module,
    if any production file exports a new public mutation method, or if
    `candidateGraph`/`candidate_graph` appears in any **new** symbol matching
    `preflight*`/`apply*`/`restore*`/`inverse*` **outside the exact legacy C2
    allowlist** in §6.7 (Gate #3: the check is "no NEW path", not a repo-wide
    zero assertion).

### 6.7 Ownership/deletion guards (what C0/C1 make bannable; C2 enforces deletion)

C0/C1 add **static** guard tests (not yet enforcement on production paths) for:

- A second JS or Python prepared-authority validator (forbidden; only
  `prepared_authority_v1.js` and `projection_registry_v1.py`).
- A second canonical-hash owner outside `canonical_hash.js` /
  `_canonical_contract_primitives.py` / `projection_registry_v1.py`.
- A second numeric-normalizer owner outside `canonical_hash.js`
  (`canonicalizeContractNumeric`) / `_canonical_contract_primitives.py`
  (`canonicalize_contract_numeric`). No contract module may define its own
  numeric coercion; it must call the shared preprocessor.
- A second compensation validator outside `_restoration_compensation` /
  `assertRestorationStrategyCompensation` (extending the existing
  `_restoration` / `digest()` owners in `projection_registry_v1.py` and
  `prepared_authority_v1.js`).
- `_prepared_plan_builder_v1` imported by any production file (C1 guard).
- Direct `hashlib.sha256(json.dumps(...))` / ad-hoc JSON hashing outside the
  shared owners.
- New public mutation methods on `intent_graph_adapter.js` exported before C2.

**`candidateGraph` ban — "no NEW path" + exact legacy C2 allowlist (Gate #3).**
The guard is **not** a repo-wide zero assertion (that is impossible: the legacy
functions below already exist and remain live through C1). The static guard
asserts that **no symbol beyond the frozen allowlist below** accepts a
parameter named `candidateGraph` / `candidate_graph`. Concretely, the guard
test computes the set `S = { symbols named preflight*/apply*/restore*/inverse*
that take a candidateGraph/candidate_graph parameter }` across
`vibecomfy/comfy_nodes/web/` and asserts `S == ALLOWLIST` (set equality). Any
growth of `S` fails the guard; the allowlist itself is frozen here so C2's
deletion is a mechanical diff against this exact set.

`ALLOWLIST` (the exact legacy candidateGraph-reading symbols, verified to exist
in current code, grouped by file):

```
# comfy_adapter.js
preflightDeltaPlan(liveGraphSnapshot, candidateGraph, deltaOps, options)
applyGraphDeltaInPlace(app, { deltaOps, candidateGraph }, options)
applyGraphLayoutInPlace(app, { candidateGraph }, options)
materializeAddNodePayload(candidateGraph, op)
appendCandidateLinksForAddedNodes(workingGraph, candidateGraph, plan)
findCandidateLinkForOp(candidateGraph, op)
resolveNodeFromGraph(graph, ...)            # graph arg is the candidate graph at call sites
verifyCandidateGraphConsistency(...)
projectCandidateGraphToRuntimeLayout(...)
resolveEndpoint / resolveFactory / canonicalNodeUid / buildGraphIndex /
  iterateLinkRecords / linkShapeForGraph / liveNodeIndex / liveLinkEntries /
  configureLiveGroup / serializedGroupKey / setLiveNodeGeometry
  (helpers reached transitively from the above; named so C2 deletes them together)

# vibecomfy_roundtrip.js
buildInverseDeltaOps(preApplyGraph, deltaOps)      # the existing inverse builder
attemptScopedCanvasRollback(preApplyGraph, deltaOps, scopedVerification)
restoreCandidateLinksOnLiveGraph(...)
undoLastApply(...)
loadGraphData / loadGraphDataWithoutScopeSwitch
installIntentNodeFallback / installGraphConfigureIntentFallback

# intent_graph_adapter.js (capability labels only; deleted at C2)
HARNESS_DELTA_APPLY_FALLBACK_MARKER, legacy_whole_graph_replace
```

This is an **allowlist**, not an aspiration: every member is a real symbol that
exists today. C0/C1 leave them all live; C2 deletes the set in one diff with
consumer rerouting. The guard's job at C0/C1 is only to prevent the set from
**growing** (no new candidateGraph path) and to make C2's deletion target
exact and mechanical.

**Native-ID identity fallback patterns** (deleted at C2): the
`canonicalNodeUid(x) || \`id:${String(x?.id)}\`` fallback (and the analogous
group `|| \`id:...\``) appears in `comfy_adapter.js` and
`vibecomfy_roundtrip.js:buildInverseDeltaOps`; both are recorded so C2 removes
them together with the symbols above.

**Note on `buildInverseDeltaOps` (Gate #11 grounding).** The inverse-relation
contract in §3.2 formalizes the output shape that
`vibecomfy_roundtrip.js:buildInverseDeltaOps` already produces (verified by
reading the function: `set_node_field`/`set_mode`→self-with-prior-value,
`upsert_link`→`remove_link`/prior-`upsert_link`, `remove_link`→`upsert_link`,
`add_node`→`remove_node`, `remove_node`→`add_node`+related-link-`upsert_link`s).
§3.2 does not invent a new inverse semantics; it specifies the validation that
the already-bound inverse (whichever builder produced it) must satisfy.

### 6.8 Proof commands (C0)

```bash
node --test \
  tests/browser/layout_operation_v1.test.mjs \
  tests/browser/mutation_materialization_v1.test.mjs \
  tests/browser/inverse_relation_v1.test.mjs \
  tests/browser/canonical_delta.test.mjs \
  tests/browser/m1_contracts.test.mjs \
  tests/browser/ownership_contract.test.mjs \
  tests/browser/frontend_ownership_regression.test.mjs

python -m pytest -q \
  tests/test_layout_operation_v1.py \
  tests/test_mutation_materialization_v1.py \
  tests/test_inverse_relation_v1.py \
  tests/test_m1_contracts.py \
  tests/test_candidate_transaction_layout_contract.py \
  tests/test_authority_receipts.py
```

C1 additionally:

```bash
node --test \
  tests/browser/prepared_plan_builder_v1.test.mjs \
  tests/browser/prepared_plan_builder_ownership_static.test.mjs
```

Record exact pass counts; no new skips permitted.

---

## 7. C0 / C1 exit criteria (decisive)

### 7.1 C0 exit — contracts only, no live-code behavior change

1. `layout_operation_v1` JS+Python owners, golden, four-op grammar, digest
   binding, root-scope/stable-id/duplicate-title rules, and the full §4
   fail-closed row set are green in both languages with byte-identical
   digests.
2. `mutation_materialization_v1` JS+Python owners, golden, exact `add_node`
   source-op binding (single kind, no duplicated op-authoritative fields, no
   implicit links), inverse-envelope reuse, opaque passthrough, and the full
   fail-closed row set are green in both languages.
3. Prepared authority (both mirrors) binds layout/materialization/restoration
   exactly as §1.5/§2.5/§3.1–§3.3 specify; the `restoration_strategy` closed tag
   set (two inverse payload tags + the grandfathered `baseline_snapshot_v1` ref) is
   enforced; the §3.2 inverse-relation validator accepts correct inverses and
   rejects every failure mode; the prepare-owned optional
   `restoration_strategy_compensation` slot (§3.4) is validated when present,
   forbidden in candidate authority, and immutable once minted on prepared
   authority; candidate→prepared transition list gains exactly one key
   (`restoration_strategy_compensation`, prepare-owned-additive); candidate
   transactions keep minting the grandfathered mandatory restoration and mint
   the new layout/materialization envelopes when supplied.
4. The hash-primitive leaf relocation is behavior-preserving: every existing
   test (incl. `m1_contracts`, `authority_receipts`) stays green and
   `projection_registry_v1.ContractError is _canonical_contract_primitives.ContractError`.
5. No production live-code path behavior change; no new public adapter mutation
   API; no consumer rerouted; `comfy_adapter.js` / `vibecomfy_roundtrip.js`
   legacy reads unchanged but now statically recorded as the frozen C2
   allowlist (§6.7).
6. No second owner introduced for delta, hash, identity, projection,
   authority, or restoration. The numeric normalizer
   (`canonicalize_contract_numeric` / `canonicalizeContractNumeric`) is the
   sole normalizer owner, living in the shared leaf; it is not a second hash
   owner.
7. The numeric normalizer (§0.3.1) produces byte-identical digest preimages for
   ordinary integer geometry, `1.0`, `-0.0`, exponent-origin inputs, and
   genuine fractions — in both languages, proven by parity tests — without
   altering any existing m1/m0 digest. `non_canonical_number` is raised only
   for booleans or unsafe-range integers, never for `1.0`/`-0.0`/exponents.

### 7.2 C1 exit — adapter-isolated private preflight/plan proof only, zero native writes

1. `_prepared_plan_builder_v1.mjs` exists as a pure, prepared-authority-only
   module (no app/DOM/LiteGraph imports; C0 contract modules + `canonical_hash.js`
   imported **by name**, never injected).
2. For every §4 fail-closed row and every positive case, the **externally-owned
   harness** sentinel counts are exactly `0` — read from the harness, never from
   the builder's return value. **Independently**, the static-reachability test
   confirms the builder's transitive import closure excludes every native
   primitive. Two independent lines of evidence; the builder itself attests
   nothing.
3. The frozen plan re-validates the already-bound `restoration_strategy` digest
   by recomputation (and the optional `restoration_strategy_compensation`
   digest, if present, §3.4); it does **not** generate an
   inverse from live state and does **not** execute a primitive, write,
   repaint, or serialization.
4. Invalid authority returns the exact §4 diagnostic code with all harness
   sentinels still zero.
5. **No** production consumer imports the private builder; **no** public
   mutation method is exported; **no** `candidateGraph` path exists outside the
   frozen §6.7 allowlist; **no** S3/S4 ownership-complete claim, ledger
   transfer, or ledger reclassification is made.

### 7.3 Explicit non-exit (what C0/C1 do NOT claim)

- Not S3/S4 ownership-complete. The 27 coupled rows and 7 S4-debt rows stay
  exactly as today; no row is relabeled transferred merely because a contract
  or private proof exists.
- Not consumer-routed. `vibecomfy_roundtrip.js`, `preview_picker.js`,
  `agentic_replay.js`, `active_canvas_scope_guard.js`, `scope_resolver.js`,
  `panel_overlay.js` are untouched.
- Not native-write-complete — not even from the harness. C1 makes **zero**
  native writes. Primitive execution, landed-prefix evidence,
  serialization-after-mutation, inverse execution, repaint, and fault-after-
  write proofs are deferred to C2/C3. Forward whole-graph replacement
  (`loadGraphData`, `graph.clear`/`configure`,
  `HARNESS_DELTA_APPLY_FALLBACK_MARKER`, `legacy_whole_graph_replace`) remains
  in place and is deleted only at C2.
- Not a real-ComfyUI proof. C4 owns that. C1 uses the sentinel-instrumented
  private plan builder only; it never drives a real LiteGraph.

---

## 8. Stop conditions (carry forward from the briefs)

Stop and reconcile rather than improvise if:

- prepared authority cannot bind layout/materialization/restoration without a
  cross-language contract change (it can — this spec is that change);
- any public apply/preflight still needs candidateGraph (C1 must not introduce
  such a signature; the §6.7 allowlist must not grow);
- canonical hashing cannot be shared (it already is — §0.3; the leaf relocation
  preserves identity; §0.3.1 closes numeric parity **via JS-compatible
  normalization**, not rejection — the normalizer is a value preprocessor, not
  a second hash owner);
- a second owner appears for delta/hash/identity/projection/authority/
  restoration/normalizer (forbidden by §0 and §6.7);
- the Python leaf relocation changes any existing test outcome (it must not —
  re-export is identity-preserving; the normalizer is not called by any
  existing entry point; if it does, stop and reconcile before C1);
- the plan builder cannot prove zero native calls on some validation case
  (must not happen — fail-closed is validator-side, before any sentinel; and
  the proof must come from the externally-owned harness / static reachability,
  not from the builder's own return value);
- the already-bound inverse/restoration/compensation digest cannot be
  recomputed by the plan builder, or the §3.2 inverse relation cannot be
  validated against the bound inverse ops (C1 must prove both, else stop
  before C2);
- the compensation slot (§3.4) appears to authorize execution or native
  mutation in C0/C1 (it must not — it is a contract/validation slot only;
  native compensation restore is C2/C3);
- the atomic C2 cutover begins moving lifecycle/verifier/recovery ownership
  (out of scope; M3/M4/M5).

The safe boundary remains **contracts first (C0), one isolated private
preflight/plan proof with zero native writes (C1), one atomic native-owner
cutover later (C2), real ComfyUI proof last (C4)**. This document closes C0
and bounds C1; it does not authorize C2.

## 9. Accepted execution record — 2026-07-17

C0 and C1 passed their bounded acceptance and are sealed by the checkpoint
commit. The adjacent scheduler activation fence is included as a separately
scoped release-safety repair: it fences panel rendering and observability only
and does not extend the C0/C1 native-mutation claim.

- Focused JavaScript: 156/156.
- Focused Python: 118/118.
- Lifecycle compatibility: 294/294.
- Dependency closure, legacy migration, inverse-v2, and M1 repair suite:
  60/60.
- Browser contracts: 569/569.
- Browser smoke: 1,531 passed, 0 failed, 2 intentional skips.
- Full roundtrip file: 238 passed, 0 failed, 2 intentional skips in each of two
  complete repetitions.
- Python fast gate: 584 passed, 1 intentional skip.
- Canonical parity: 64 templates.
- Arnold production profiles: 68/68 configured agent specs parsed.
- Import identity, compilation, dependency closure, diff check, numeric shared
  negatives, exact-op-order/no-dedup, and `inverse_delta_v2` regressions: green.

The non-exit remains binding: 0/27 coupled S3 rows transferred, all seven S4
debt rows remain open, and C2 is the next atomic consumer/deletion/ledger cut.
