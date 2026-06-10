# prep-m3.md — Sprint 3 Prep: Seams + IR Purity (`premium/thorough/high +prep`)

**Plan:** `sprint-3-seams-ir-purity-20260528-1903` (v5)
**Created:** 2026-05-28
**Batch:** 3 of 26 (T3 only)
**Status:** Complete
**Depends on:** T1 (release metadata), T2 (IR contract anchor)

---

## 1. Release Metadata

- **Target version:** `2.8.0` (bumped from `2.7.0`)
- **Semver classification:** Controlled breaking minor under the 2.x line
- **Source of truth:** `pyproject.toml:7` (`version = "2.8.0"`)
- **Console entrypoint:** Unchanged — `vibecomfy = "vibecomfy.cli:main"` at `pyproject.toml:35`
- **Version exposure:** `importlib.metadata.version("vibecomfy")` in `vibecomfy/runtime/attempt.py` — no `__version__` needed
- **Release notes:** `docs/release_notes/v2.8.0.md` (created), `docs/release_notes.md` (updated with v2.8.0 entry)
- **No top-level CHANGELOG.md:** Versioned release notes under `docs/release_notes/` is the active convention

---

## 2. IR Contract Sketch

### 2.1 Anchor Location

`vibecomfy/contracts/ir.py` — the code-facing public IR contract anchor.

### 2.2 Stable Contract Codes

| Code | Guarantee |
|------|-----------|
| `ir.public_input.unregistered` | `set_input(name, value)` only mutates registered public inputs |
| `ir.public_input.stale_target` | `set_input(name, value)` rejects public inputs whose node or field target is stale |
| `ir.validation.report_ok_field` | `ValidationReport` exposes pass/fail through `report.ok` |
| `ir.validation.ok_implies_compile_api` | `validate().ok` means `compile("api")` succeeds |
| `ir.compile.edge_endpoint_resolved` | Every compiled edge endpoint resolves to a node present in the compiled prompt |
| `ir.compile.helper_edge_rewired_or_reported` | Helper/UI-stripped edges are rewired or reported; never silently dropped |

### 2.3 Contract Shape Constants

- `IR_CONTRACT_VERSION = "vibecomfy.ir_contract.v2.8.0"`
- `IR_CONTRACT_SHAPE = "ir_contract.v1"`
- `IR_CONTRACT_CODES` — tuple of all six stable codes
- `IRContractAnchor` — frozen dataclass with `code`, `guarantee`, `migration_hint`
- `IR_CONTRACT_ANCHORS` — tuple of all six anchor objects

### 2.4 Public Helpers

- `ir_contract_codes()` → `tuple[str, ...]`
- `is_ir_contract_code(code)` → `bool`
- `require_ir_contract_code(code)` → `str` (raises `ValueError` on unknown)

### 2.5 Lazy Exposure

`vibecomfy/contracts/__init__.py` exposes all IR symbols through `_EXPORTS` + `__getattr__`. The `vibecomfy.contracts.ir` module is not imported until an IR attribute is accessed.

### 2.6 Validation Contract

- `ValidationReport.ok` is the canonical pass/fail field — no `ValidationReport.is_valid` alias
- `validate()` invokes `compile("api")` unconditionally for graph-local checks (T15)
- Compile failures are error-severity `api_compile_failed` issues in the validation report
- Schema-backed node validation remains conditional on `schema_provider`

---

## 3. Breaking-Change Inventory

| # | Change | Affected Users | Migration |
|---|--------|---------------|-----------|
| 1 | `validate()` calls `compile("api")` unconditionally; compile failures are validation errors | Anyone calling `wf.validate()` | Check `report.ok` instead of assuming silent passes |
| 2 | `set_input()` raises `ValueError` for unregistered or stale input targets | Template authors using `wf.set_input()` or convenience methods (`set_prompt`, `set_seed`, `set_steps`, `set_model`) | Register inputs via `bind_input()` or `InputSpec` before calling `set_input()` |
| 3 | Public input metadata (`bind_input`/`finalize_metadata`) required before `set_input` | Template authors who previously set inputs before registration | Move `bind_input()` calls before `set_input()` in template `build()` methods |
| 4 | `_next_node_id()` uses lowest-unused-gap instead of max+1 | Snapshot-based test authors | Auto-generated node IDs may change when gaps exist; selectively accept deltas |
| 5 | Helper classification extracted to `vibecomfy/_workflow_helpers.py` | Direct importers of internal helper APIs | Import from new canonical module |
| 6 | Helper-edge resolution extracted to `vibecomfy/_helper_resolve.py` | Direct importers of `porting/helper_resolve` | Import from new IR-neutral module for graph-resolution semantics; porting module kept as conversion wrapper |
| 7 | Widget-alias dependency extracted to `vibecomfy/_widget_aliases.py` | Compile-time alias consumers | Compile-time aliasing lives in `_widget_aliases`; porting keeps emitter/object-info fallback |
| 8 | `OPAQUE_COMPONENT_CLASS_RE` moved from `workflow.py` to `contracts/validation.py` | Direct importers of this regex from workflow | Import from `contracts/validation` |
| 9 | Embedded session removes `cache_only=True` default | Runtime embedded users | Schema warmup now matches server/one-shot behavior; `VIBECOMFY_SCHEMA_VALIDATE=0` remains off-ramp |

---

## 4. Migration-Note Outline

See `docs/release_notes/v2.8.0.md` for the full public migration guide. Key migration steps:

1. **set_input registration:** `rg "set_input\|set_prompt\|set_seed\|set_steps\|set_model" ready_templates/` — ensure all `set_input()` calls follow `bind_input()` or `InputSpec` registration
2. **Validate after compile changes:** `vibecomfy port check <ready-id> --json`
3. **Update extracted imports:**
   - Old: `from vibecomfy.workflow import _classify_helper`
   - New: `from vibecomfy._workflow_helpers import classify_helper`
4. **Snapshot regeneration:** `uv run pytest tests/test_snapshot_*.py --update-snapshots` (only when node ID changes are explained by gap-reuse behavior)

---

## 5. Extraction Map

```
vibecomfy/porting/helpers.py ──extract──> vibecomfy/_workflow_helpers.py
  (keep porting/helpers.py as compatibility wrapper; mark temp exports # REMOVE-M4)

vibecomfy/porting/helper_resolve.py ──extract──> vibecomfy/_helper_resolve.py
  (keep conversion wrappers/errors in porting; IR-neutral core extracted)

vibecomfy/porting/widget_aliases.py ──extract──> vibecomfy/_widget_aliases.py
  vibecomfy/porting/widget_schema.py (static subset)
  (keep emitter/object-info fallback in porting; static compile-time subset extracted)

vibecomfy/workflow.py:
  - Import helper classification from _workflow_helpers (not porting)
  - Import helper-edge resolution from _helper_resolve (not porting)
  - Import widget aliasing from _widget_aliases (not porting)
  - Move OPAQUE_COMPONENT_CLASS_RE to contracts/validation.py
  - Move VAELoaderKJ/LTX audio VAE check to contracts/validation.py

Protected IR-core modules (import-linter):
  - vibecomfy.workflow
  - vibecomfy.metadata
  - vibecomfy.contracts.ir
  - vibecomfy._workflow_helpers (after T4)
  - vibecomfy._helper_resolve (after T5, if created)
  - vibecomfy._widget_aliases (after T6)
  - vibecomfy.handles (only if exact-module syntax groups it)

Forbidden imports for protected modules:
  - vibecomfy.porting
  - vibecomfy.commands
  - vibecomfy.ops
  - vibecomfy.blocks
  - vibecomfy.patches
  - vibecomfy.runtime

NOT in protected list (imports porting):
  - vibecomfy.contracts.surface (still imports porting.strict_ready, porting.widget_aliases)
```

---

## 6. Critique-Settled Decisions

All decisions are from the v5 plan cycle and gate-carry review. No decision requires re-litigation.

### 6.1 Gate-Carry Settled Decisions (SD1–SD4)

| ID | Decision | Rationale |
|----|----------|-----------|
| SD1 | Proceed with Sprint 3 execution under v5 plan | Remaining concerns are execution notes, not plan-invalidating objections |
| SD2 | Keep Reroute, PrimitiveNode, primitive value nodes conversion-only for Sprint 3 compile | Avoids broad snapshot churn; matches explicit scope boundary |
| SD3 | Use actual extracted module names in `.importlinter` after Steps 4-6 | Protected list must guard real IR-neutral modules, not placeholder names |
| SD4 | Treat `metadata['unbound_inputs']` direct writes as legacy/deferred | `set_input()` stops writing it and raises loudly; full deprecation is broader than Sprint 3 scope |

### 6.2 Flag-Verified Decisions (from evaluator_verdict.json)

All 54 flag verifications in `evaluator_verdict.json` are verified/closed. Key implementation-critical decisions:

- **FLAG-S3-001 (correctness-2):** Shared resolver must maintain visited set keyed by `(node_id, output_slot)` and fail loudly with `helper_edge_cycle` / `helper_edge_unresolved`
- **FLAG-S3-002 (correctness-1):** Manual input provenance via private VibeWorkflow set + descriptor snapshotting, restored after rebuilding inferred inputs
- **FLAG-S3-003 (all_locations-3):** Mandatory reuse of `normalize_prompt_id()` in embedded, server, and one-shot paths
- **FLAG-S3-008 (correctness-8):** `validate()` invokes `compile("api")` unconditionally; `api_compile_failed` severity changed from warning to error
- **scope-8:** API and graphbuilder compile share one resolved-edge-input assembly helper; parity test compares normalized target input dicts
- **scope-9:** `validate()` calls real `compile("api")` instead of replicating prechecks
- **scope-10:** `test_helper_diagnostics_report_unresolved_broadcasts_before_compile` rewritten to expect failure
- **scope-11:** `set_input()` raises `ValueError` for stale target fields; no raw `KeyError`
- **callers-5:** `set_input()` raises `ValueError` for missing nodes; no `metadata['unbound_inputs']` parking
- **callers-6:** `contracts.validation` returns neutral issue specs; `workflow.validate()` converts them to `ValidationIssue`
- **callers-7:** Reroute/PrimitiveNode/value primitive behavior locked conversion-only for Sprint 3

### 6.3 Carried Flag Guidance (from gate_carry.json)

| Flag ID | Guidance |
|---------|----------|
| `issue_hints` (dead `_prepare_prompt_async` in `prompt.py`) | Discoverability note: Step 13 targets `session.py`; document the `prompt.py` trap in `handoff-m3.md` |
| `scope-12` (moved `OPAQUE_COMPONENT_CLASS_RE`) | Migration note must explicitly call out the moved workflow-level regex export |
| `scope-13` (legacy `metadata['unbound_inputs']`) | Accept scoped tradeoff: `set_input()` is loud; full deprecation deferred |
| `scope-14` (M2B test file existence) | Execution gate: verify test files exist before claiming M2B success |
| `scope-15` (function-name enumeration for Step 13) | Audit runtime test files; update cache-only assertions to parity tests |
| `all_locations-7` (shared edge-input format) | Lock return shape: `dict[target_node_id][target_input] = resolved_source` |
| `all_locations-8` (graphbuilder missing-endpoint check) | Shared helper must validate resolved sources before either backend consumes them |
| `all_locations-9` (convenience wrapper audit) | Expand audit scope to include `set_prompt`/`set_seed`/`set_steps`/`set_model` callers |
| `prerequisite_ordering-6` (snapshot deltas from id changes) | Selectively accept only deltas following lowest-unused-positive-id rule; no blanket regeneration |
| `prerequisite_ordering-7` (validate/compile deduplication) | Replace old guarded compile check; do not add a second path |
| `prerequisite_ordering-8` (linter config module names) | `.importlinter` written after extraction; protects actual chosen IR-neutral modules |
| `prerequisite_ordering-9` (stale targets pre-finalization) | Add focused tests for stale node/field before finalization; aligned with loud `set_input` contract |

---

## 7. contracts.surface Boundary

### Current State

`vibecomfy/contracts/surface.py` imports from:
- `vibecomfy.contracts.model` (same package — allowed)
- `vibecomfy.porting.strict_ready` (porting — Layer-2)
- `vibecomfy.porting.widget_aliases` (porting — Layer-2)
- `vibecomfy.utils` (utilities — allowed)
- `vibecomfy.workflow` (IR core — allowed)

### Boundary Decision

`contracts.surface` is **NOT** part of the initial forbidden-import boundary because it still imports `porting`. It is adjacent to the IR-core contract but not protected.

**Rule:** `.importlinter` must not blanket-protect `vibecomfy.contracts` as a package. Only individual IR-neutral submodules (`contracts.ir`, and `contracts.validation` after T17 moves ComfyUI-specific checks there) are in the protected list.

**If `contracts.surface` dependencies are later moved** to be IR-clean via a narrow, behavior-preserving change, it can be admitted to the protected list — but not in Sprint 3.

---

## 8. Import-Linter Command/Config Plan

### 8.1 Dependency

`import-linter` is part of the existing `dev` optional dependency group in `pyproject.toml` (T7).

### 8.2 Config File

Root [`.importlinter`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.importlinter) — INI-style config with one explicit forbidden-import contract.

### 8.3 Contract Shape (whitelist-style, exact modules)

```
[importlinter]
root_package = vibecomfy

[importlinter:contract:ir-core-no-porting]
name = IR core must not import porting or Layer-2 modules
type = forbidden
allow_indirect_imports = true
source_modules =
    vibecomfy.workflow
    vibecomfy.metadata
    vibecomfy.contracts.ir
    vibecomfy._workflow_helpers
    vibecomfy._helper_resolve
    vibecomfy._widget_aliases
forbidden_modules =
    vibecomfy.porting
    vibecomfy.commands
    vibecomfy.ops
    vibecomfy.blocks
    vibecomfy.patches
    vibecomfy.runtime
```

### 8.4 Rules

- No exception clauses
- No blanket `vibecomfy.contracts` rule (would false-positive on `contracts.surface`)
- `vibecomfy.handles` included only if exact-module syntax requires grouping another IR-core module
- Do not rely on trivially clean modules as evidence of fixing current violations
- The actual protected module names come from Steps 4-6 extraction results, not from planning text

### 8.5 Command

```bash
lint-imports
```

Run with no extra flags; it picks up the committed [`.importlinter`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.importlinter) config from the repo root. Document in `handoff-m3.md`.

---

## 9. Widget-Alias Audit Requirement

### 9.1 Audit Scope (T6.5)

Before removing the `porting.object_info.consume.object_info_widget_order` fallback from the compile path:

1. List every `COMPILE_WIDGET_ALIAS_CLASS_TYPES` class whose positional alias order is provided **only** by object-info fallback (not committed static tables)
2. Record the **count** and **affected class names** in `prep-m3.md` or `handoff-m3.md`

### 9.2 Resolution Path

- If a ready template depends on object-info-only compile aliasing:
  - Add a committed static alias entry for that class in `_widget_aliases.py`, OR
  - Update the template to avoid unresolved `widget_N` compile inputs
- **Do not keep a Layer-1 import of `porting.object_info`**

### 9.3 Deterministic Precedence

1. `node.widgets` values first
2. `node.inputs` values override
3. Positional widget aliases applied
4. Unused aliases dropped

Lock with regression tests to prevent future inversions.

### 9.4 T6 Audit Delta

Command:

```bash
python - <<'PY'
from vibecomfy.porting.widget_aliases import COMPILE_WIDGET_ALIAS_CLASS_TYPES
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA
from vibecomfy.porting.object_info.consume import object_info_widget_order

object_only = []
missing = []
for class_type in sorted(COMPILE_WIDGET_ALIAS_CLASS_TYPES):
    if class_type in WIDGET_SCHEMA:
        continue
    names = object_info_widget_order(class_type)
    if names:
        object_only.append((class_type, names))
    else:
        missing.append(class_type)
print("compile classes", len(COMPILE_WIDGET_ALIAS_CLASS_TYPES))
print("static", sum(1 for c in COMPILE_WIDGET_ALIAS_CLASS_TYPES if c in WIDGET_SCHEMA))
print("object_info_only", len(object_only))
print("no_static_no_object", len(missing))
PY
```

Result:

- Compile alias class types: 87
- Static committed alias/schema coverage: 87
- Object-info-only fallback class coverage: 0
- Missing static and object-info coverage: 0

No ready-template dependency needed an additional static alias or template fix
before removing object-info fallback from the compile path.

---

## 10. Validation Compile Invocation (T15)

### 10.1 Behavior Change

`VibeWorkflow.validate()` now invokes `compile("api")` **unconditionally** for graph-local checks:

- Even when `schema_provider is None`
- Compile failures are recorded as **error-severity** `api_compile_failed` issues
- `report.ok` implies `compile("api")` succeeded

### 10.2 Deduplication

The old schema-provider-guarded compile check at `workflow.py` (line ~440) must be **replaced**, not supplemented. Only one compile path in `validate()`.

### 10.3 Schema-Backed Checks

Schema-backed node validation remains conditional on `schema_provider` — no change to that path.

### 10.4 Interaction with Step 13

After Step 13 removes `cache_only=True`, embedded runtime prompt preparation uses the warmed schema provider, then calls `workflow.validate(schema_provider=effective)`. With the new unconditional compile check, the old guarded compile (line ~440) must be removed to avoid double-compile.

---

## 11. Helper Extraction Details

### 11.1 Helper Classification (T4 — `vibecomfy/_workflow_helpers.py`)

Extracted from `vibecomfy/porting/helpers.py`:

**Public exports:**
- Helper class sets (`HELPER_CLASS_TYPES`, etc.)
- `HelperDiagnostic`
- `helper_stripped_nodes`
- `helper_stripped_class_types`
- `collect_helper_diagnostics`
- `collect_broadcast_sources`
- `is_helper_class_type`
- `broadcast_name`
- `first_link_input`
- `is_api_link`

**Private dependencies (extracted but kept private):**
- `_sorted_nodes`
- `_node_sort_key`
- `_node_class_type`
- `_node_inputs`
- `_node_widgets`
- `_edge_attr`

**Compatibility:** `vibecomfy/porting/helpers.py` remains as a re-export wrapper. Temporary exports marked `# REMOVE-M4`.

### 11.2 Helper-Edge Resolution (T5 — `vibecomfy/_helper_resolve.py`)

Extracted from `vibecomfy/porting/helper_resolve.py`:

- Multi-hop upstream walking with visited set `(node_id, output_slot)`
- SetNode/GetNode broadcast resolution
- Standalone UI-only nodes silently stripped
- Helper/UI nodes in runtime edge paths either resolve or raise `helper_edge_unresolved` / `helper_edge_cycle`
- Reroute/PrimitiveNode routines retained for porting compatibility but compile mode must not strip these nodes

**Compile-stripped helpers (Sprint 3):** `Note`, `MarkdownNote`, `SetNode`, `GetNode` only.

**Not stripped:** `Reroute`, `PrimitiveNode`, primitive value nodes (SD2).

---

## 12. Shared Edge-Input Assembly (T14)

### 12.1 Contract

A single internal helper in `workflow.py` uses the extracted IR-neutral resolver to produce:

```python
dict[target_node_id][target_input] = resolved_source
```

### 12.2 Consumers

Both `compile("api")` and `_compile_graphbuilder()` consume the same mapping.

### 12.3 Failure Modes

| Mode | Stable Code |
|------|-------------|
| Helper cycle detected | `helper_edge_cycle` |
| Unresolvable helper path | `helper_edge_unresolved` |
| Resolved source not in compiled API | `compiled_edge_missing_endpoint` |
| Compile failure (general) | `api_compile_failed` |

### 12.4 Parity Test

A focused test compares normalized target input dicts from API and graphbuilder compile for the same helper-edge workflow.

---

## 13. Gate Corrections and Watch Items

### 13.1 Execution Order Rationale

1. Land release/version and contract docs before behavior changes (T1-T3)
2. Add focused failing tests for IR contract before modifying `workflow.py` (T8-T9)
3. Extract helper classification, helper-resolution, and widget-alias dependencies before adding import-linter (T4-T6 → T7)
4. Implement public input, metadata provenance, connect, and id fixes before helper-edge rewiring (T8-T13)
5. Implement helper-edge compile behavior through shared resolved-edge-input assembly (T14-T16)
6. Make `validate()` call `compile("api")` unconditionally (T15)

### 13.2 Watch Items

| Item | Resolution |
|------|------------|
| Do not invoke megaplan CLI or nested plans | Locked |
| Reroute/PrimitiveNode conversion-only for Sprint 3 compile | SD2 |
| One unconditional `compile("api")` in `validate()` | T15 |
| Shared edge-input assembly return shape | `dict[target_node_id][target_input]` |
| `set_input()` loud but legacy `unbound_inputs` deferred | SD4 |
| Manual inputs survive finalize while valid; invalid dropped | T10 |
| Widget alias remove Layer-1 porting imports | T6 |
| `.importlinter` uses actual module names, not blanket contracts | SD3 |
| No broad emitter/session/runtime refactors | Scope boundary |
| M2B test file existence verified before gate claim | Preflight (T24) |
| Audit convenience wrappers (`set_prompt` etc.) | T8.7 |
| `prompt.py` dead `_prepare_prompt_async` trap | Document in handoff |
| Snapshot deltas from id gap reuse selectively accepted | T13 |
| Use `ValidationReport.ok`, not `is_valid` | T2 verified |

### 13.3 Prior Batch Deviation Resolution

From execution_batch_2.json deviations:

- **Full pytest collection failures** (CanonicalParityFailure, duplicate plugin registration): Documented as pre-existing, out-of-scope. These are baseline, not Sprint 3 regressions.
- **Advisory observation mismatch:** Files were observed and verified; the mismatch was in git detection, not file presence.
- **Missing sense check acknowledgments (SC3-SC26):** All remaining sense checks belong to future batches. SC3 is acknowledged in this batch.

---

## 14. Test Baseline

### 14.1 Full-Suite Status

- Full `pytest` collection blocked by two pre-existing issues:
  1. Missing `CanonicalParityFailure` in `vibecomfy.errors` for `tests/test_agentic_affordances.py`
  2. Duplicate registration of `vibecomfy.testing._pytest_plugin` in `tests/test_testing_api.py`
- These are baseline, not Sprint 3 regressions
- `baseline_test_failures` in `finalize.json` is empty (baseline could not be captured cleanly)

### 14.2 Focused Test Gates (from plan)

| Gate | Command |
|------|---------|
| Workflow core | `pytest tests/test_workflow_core.py -q` |
| Finalize metadata | `pytest tests/test_finalize_metadata.py -q` |
| Acceptance | `pytest tests/test_acceptance.py -q` |
| Runtime parity | `pytest tests/test_runtime_session_validation.py tests/test_runtime_session_embedded.py tests/test_runtime_run.py -q` |
| Lint imports | `lint-imports` |
| CLI check | `python -m vibecomfy.cli check --json` |
| M2B focused suite | Verified files first, then run |
| Sprint-1 roundtrip | Compared against documented baseline |

---

## 15. Deferred / Known Limitations

- **Reroute/PrimitiveNode compile stripping:** Deferred beyond Sprint 3 (SD2)
- **`metadata['unbound_inputs']` full deprecation:** Deferred; `set_input()` stops writing but legacy direct writes elsewhere are not touched (SD4)
- **`contracts.surface` porting imports:** Not moved in Sprint 3; excluded from import-linter protected list
- **`prompt.py` dead `_prepare_prompt_async`:** Documented trap; active path is `session.py`

---

## 16. Task Dependency Chain (Remaining)

```
T3 (this task) ──> T4 ──> T5 ──> T6 ──> T7 ──> T8 ──> T9 ──> T10 ──> T11 ──> T12
                                                                                    │
T26 <── T25 <── T24 <── T23 <── T22 <── T21 <── T20 <── T19 <── T18 <── T17 <── T16 <── T13
```

---

*prep-m3.md is the handoff prep artifact for Sprint 3. It captures all critique-settled decisions and execution corrections required before beginning the extraction and behavior-change phases (T4 onward).*
