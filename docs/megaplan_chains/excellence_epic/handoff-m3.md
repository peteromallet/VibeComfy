# Sprint 3 — Seams + IR purity: Handoff (M3)

**Branch:** `epic/excellence/m3-seams-ir`  
**Version:** 2.8.0 (controlled breaking minor under 2.x)  
**Sprint:** `sprint-3-seams-ir-purity-20260528-1903`  
**Completed:** 2026-05-29  

---

## 1. Public Breaking Changes (2.8.0)

| # | Change | Affected surface | Migration |
|---|--------|-----------------|-----------|
| 1 | `VibeWorkflow.set_input(name, value)` raises `ValueError` for unregistered names, unknown aliases, stale node targets, and stale field targets. Previously it parked unknowns silently in `metadata['unbound_inputs']`. | All callers of `set_input`, `set_prompt`, `set_seed`, `set_steps`, `set_model`. | Use `wf.inputs` to inspect registered names; fix template public-input registration before calling setters. |
| 2 | `set_input` no longer writes new `metadata['unbound_inputs']` entries. | Code that relied on deferred unknown-input parking. | Register inputs explicitly with `wf.register_input(name, node_id, field)` before calling `set_input`. |
| 3 | `VibeWorkflow.validate()` calls `compile('api')` unconditionally regardless of `schema_provider`. Compile failures produce error-severity `api_compile_failed` issues; `report.ok = False` when compile fails. | Code that assumed `report.ok = True` when no schema provider was given. | Check `report.ok`; fix compile errors exposed by unconditional check. |
| 4 | IR-neutral modules extracted: `vibecomfy._compile._helpers`, `vibecomfy._compile._resolve`, `vibecomfy._compile._widgets`. These are public via the `_compile/` private package. `vibecomfy.porting.helpers`, `vibecomfy.porting.helper_resolve`, `vibecomfy.porting.widget_aliases` remain as compatibility wrappers (marked `# REMOVE-M4`). | Code importing directly from `porting.helpers` or `porting.helper_resolve`. | Import from `vibecomfy._compile._helpers` / `vibecomfy._compile._resolve` / `vibecomfy._compile._widgets`. |
| 5 | `VibeWorkflow._next_node_id()` returns the lowest unused positive numeric id (gap-filling) rather than `max + 1`. | Code relying on monotonically-increasing auto node-id assignment. | Explicit node ids remain unaffected; tests that snapshot auto-ids must accept lowest-unused behavior. |
| 6 | `VibeWorkflow.connect()` / `replace_edge()`: bare string source refs default to output slot `0`; malformed refs raise `ValueError`. | Code passing bare string without intent of slot 0. | Explicit `Handle` refs or `"node_id.0"` syntax unchanged; check callers that relied on no-error behavior for malformed refs. |
| 7 | `vibecomfy.contracts.ir` added — stable IR contract anchor with 6 stable `ir.*` codes and `IRContractAnchor` dataclass. Lazily exposed via `vibecomfy.contracts`. | Any code that cached `vibecomfy.contracts.__all__` at import time. | Re-import after lazy attribute access; use `vibecomfy.contracts.ir` symbols for stable contract codes. |
| 8 | `EmbeddedSession._run_untracked()`: `cache_only=True` removed from `_warm_schema_provider` call. Embedded sessions now warm/use the runtime schema provider like server and one-shot paths. | Code that expected embedded sessions to skip schema provider warmup. | `VIBECOMFY_SCHEMA_VALIDATE=0` remains as off-ramp for schema validation. |
| 9 | `normalize_prompt_id()` reused in embedded session, server session, and one-shot run path for `RunResult.prompt_id` extraction (both dict and object return shapes supported). | Code that parsed `queued['prompt_id']` directly. | No action needed for external callers; `RunResult.prompt_id` now stable for both queue return shapes. |

---

## 2. Migration Examples

### set_input (formerly silent unknown)

```python
# Before 2.8.0: silently wrote metadata['unbound_inputs']
wf.set_input("nonexistent_field", "value")  # no error

# After 2.8.0: raises ValueError
# Fix: check wf.inputs or register the input first
print(list(wf.inputs.keys()))  # see registered public inputs
```

### set_prompt / set_seed / set_steps (convenience wrappers propagate ValueError)

```python
# Requires template to register 'prompt', 'seed', 'steps' as public inputs
wf = load_workflow_any("image/z_image")
wf.set_prompt("a glass teapot on basalt")  # ok — z_image registers 'prompt'
wf.set_seed(42)                             # ok — z_image registers 'seed'
wf.set_steps(20)                            # ok — z_image registers 'steps'
```

### register_input / InputSpec

```python
# Post-finalize registration (generated template pattern) still works;
# finalize_metadata() restores valid manual descriptors
from vibecomfy import load_workflow_any
wf = load_workflow_any("image/z_image")
wf.finalize_metadata()
wf.register_input("my_input", node_id="42", field="text")
wf.finalize_metadata()  # manual descriptor preserved on re-finalize
```

### validate + compile unconditional

```python
wf = load_workflow_any("image/z_image")
report = wf.validate()          # compile('api') runs regardless of schema_provider
assert report.ok                # True means compile succeeded + no schema errors
compiled = wf.compile("api")    # safe to call directly after validate
```

---

## 3. Import-Linter Command and Config

**Config file:** `.importlinter` (committed at repo root)

```ini
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
    vibecomfy._compile._helpers
    vibecomfy._compile._resolve
    vibecomfy._compile._widgets
forbidden_modules =
    vibecomfy.porting
    vibecomfy.commands
    vibecomfy.ops
    vibecomfy.blocks
    vibecomfy.patches
    vibecomfy.runtime
```

**Run command:**
```bash
uv run --extra dev lint-imports
```

**Result (2026-05-29):** `Contracts: 1 kept, 0 broken.`

---

## 4. Validation Commands and Observed Outputs

```bash
# Focused gate suite (acceptance + core + helpers + edge + finalize + template + run + runtime + contract + aliases)
PYTHONPATH=$PWD pytest tests/test_acceptance.py tests/test_workflow_core.py \
  tests/test_workflow_helpers.py tests/test_edge_primitives.py \
  tests/test_finalize_metadata.py tests/test_ready_template_helpers.py \
  tests/test_run_command.py tests/test_runtime_run.py \
  tests/test_runtime_session_validation.py tests/test_contract_ir.py \
  tests/test_contract.py tests/test_widget_aliases.py -q --tb=short
# Result: 216 passed, 1 skipped

# Import-linter
uv run --extra dev lint-imports
# Result: Contracts: 1 kept, 0 broken.

# CLI consistency check
python -m vibecomfy.cli check --json
# Result: all checks ok (non_vendor_stale_legacy_references + thin_wrapper_import_smoke + ...)

# Full suite (excluding pre-existing collection-error files)
PYTHONPATH=$PWD pytest -q --tb=no \
  --ignore=tests/test_agentic_affordances.py \
  --ignore=tests/test_testing_api.py
# Result: 203 failed / 1726 passed / 73 skipped
```

---

## 5. Baseline Comparisons

| Suite | Sprint-3 result | Pre-sprint baseline | Delta |
|-------|-----------------|---------------------|-------|
| Focused gate (12 test files) | 216 passed, 1 skipped | 90–142 passed (partial suites) | +new acceptance/runtime tests |
| Full suite (excl. 2 collection-error files) | 203 failed / 1726 passed / 73 skipped | 204 failed / 1708–1712 passed | -1 failure (rounding), +14–18 passes from new tests |
| M2B focused suite | 4 failed / 63 passed / 65 skipped | same 4 pre-existing | 0 regressions |

**Pre-existing collection errors (not attributable to sprint-3):**
- `tests/test_agentic_affordances.py` — cannot import `CanonicalParityFailure`
- `tests/test_testing_api.py` — duplicate `vibecomfy.testing._pytest_plugin` registration

**Pre-existing M2B failures (not attributable to sprint-3):**
1. `test_generated_wrapper_rejects_multiple_positional_workflows` — `ContextVarBindingError` for nested workflow contexts
2. `test_ready_template_matches_source_api[video/wan_i2v]` — non-link value/type drift
3. `test_audited_seed_sensitive_fields_keep_source_values_and_types[video/ltx2_3_runexx_talking_avatar_qwen_tts-fields1]` — voice field type drift (str vs int)
4. `test_wan_i2v_matches_independent_golden_api_fixture` — same wan_i2v parity failure

---

## 6. Acceptance Smoke

**Test:** `tests/test_acceptance.py::test_acceptance_z_image_public_knobs_validate_compile`

**Workflow:** `image/z_image`  
**Exact observed compiled node count:** 9  
**Minimum threshold:** 5  
**Inputs exercised:** `set_prompt("a glass teapot on basalt")`, `set_seed(42)`, `set_steps(20)`  
**Assertions:** `report.ok is True`, `len(compiled) > 0`, `len(compiled) >= 5`

**Reproduction:**
```python
from vibecomfy import load_workflow_any
wf = load_workflow_any("image/z_image")
wf.set_prompt("a glass teapot on basalt")
wf.set_seed(42)
wf.set_steps(20)
report = wf.validate()
compiled = wf.compile("api")
assert report.ok          # True
assert len(compiled) >= 5 # 9 nodes compiled
```

---

## 7. Widget-Alias Audit

**Audit date:** 2026-05-29  
**IR-neutral module:** `vibecomfy/_widget_aliases.py`  
**Compile alias class types (`COMPILE_WIDGET_ALIAS_CLASS_TYPES`):** 87  
**Widget schema entries (`WIDGET_SCHEMA`):** 164  
**Object-info-only fallback class coverage:** 0 (no classes require object-info at compile time)  
**Missing classes for ready-template dependencies:** 0  

All 87 compile-alias class types have static entries in `_widget_aliases.py`. Object-info fallback behavior remains in `vibecomfy/porting/widget_aliases.py` and `vibecomfy/porting/widget_schema.py` for conversion/emitter tooling only.

**Static additions for ready templates:** None required — all ready-template alias dependencies were already present in the static schema.

---

## 8. Helper-Edge Cycle and Missing-Endpoint Hardening

**Implementation:** `vibecomfy/workflow.py::_compile_resolved_edge_inputs()`

This shared helper is consumed by both `compile("api")` and `_compile_graphbuilder()`. It:

- Recursively walks compile-stripped helper chains (`SetNode`/`GetNode`/`Note`/`MarkdownNote`) with visited-state cycle detection
- Preserves `Reroute`/`PrimitiveNode`/value-primitive nodes (conversion-only decision, see §12)
- Raises `WorkflowCompileError` with stable codes on failure:
  - `helper_edge_cycle` — circular SetNode/GetNode reference chain
  - `helper_edge_unresolved` — broadcast/UI-only helper with no reachable real source
  - `compiled_edge_missing_endpoint` — traced source not present in compiled output

**Stable codes (from `vibecomfy/contracts/ir.py`):**
- `ir.compile.edge_endpoint_resolved`
- `ir.compile.helper_edge_rewired_or_reported`

---

## 9. Standalone-Helper Boundary

Standalone helper nodes (Note, MarkdownNote, SetNode, GetNode with no connected real target) are stripped silently at compile time. They do not raise errors when they have no outgoing edges to runtime nodes. Only when a runtime node's input depends on a helper chain that cannot be resolved does `helper_edge_unresolved` raise.

---

## 10. Reroute/Primitive Conversion-Only Decision (SD2)

**Decision:** Reroute, PrimitiveNode, and value-primitive nodes are NOT stripped at compile time in Sprint 3. They remain conversion-only for now.

**Rationale:** Avoids broad snapshot churn; matches explicit Sprint 3 scope boundary. The plan's SD2 states: "Keep Reroute, PrimitiveNode, and primitive value nodes conversion-only for Sprint 3 compile unless a focused failing test proves compile-time stripping is required."

**Test evidence:** `tests/test_workflow_core.py` contains regression tests confirming compile strips only `Note`/`MarkdownNote`/`SetNode`/`GetNode` while preserving `Reroute`/`PrimitiveNode`/`PrimitiveInt`.

---

## 11. Manual Input Provenance

**Implementation:** `VibeWorkflow._manual_input_names: set[str]` (private)

- `register_input()` marks the primary name as manually registered
- `finalize_metadata()` snapshots valid manual descriptors, rebuilds inferred inputs/outputs/requirements, then restores valid manual descriptors with precedence on name collisions
- Preserved descriptor fields: `aliases`, `default`, `required`, `type`, `range`, `media_semantics`, `value`
- **Invalid manual descriptor removal:** descriptors whose `node_id` no longer exists in `self.nodes`, or whose `field` no longer exists on the target node's widget list, are dropped deterministically (logged at debug level, no ValueError)
- **Stale set_input ValueError behavior:** `set_input()` checks graph state at call time — stale targets raise `ValueError` with node class and available fields regardless of whether `finalize_metadata()` has been called

---

## 12. Invalid Manual Dropping

After `finalize_metadata()`, manual inputs whose node or field targets are no longer valid are dropped. This is deterministic and silent (no error raised). The input name is removed from `_manual_input_names` as well, so a subsequent `set_input(name, ...)` will raise `ValueError` (name no longer registered).

---

## 13. normalize_prompt_id Reuse

**Module:** `vibecomfy/runtime/execution.py::normalize_prompt_id(queued)`

Reused in:
- `vibecomfy/runtime/session.py` — embedded session and server session `_run_untracked()` paths
- `vibecomfy/runtime/run.py` — one-shot run path
- `vibecomfy/runtime/eval_prompt.py` — eval prompt path

Supports both dict (`queued['prompt_id']`) and object (`queued.prompt_id`) queue return shapes; coerces numeric ids to `str`.

---

## 14. Caller Audits

**set_input / convenience wrappers audit (T8):**
- `vibecomfy/porting/emitter.py` `set_inputs` patch — audited; intentional template-emit pattern
- `vibecomfy/porting/node_kwargs.py` — audited; does not call `set_input`
- `vibecomfy/commands/run.py` `--seed` flag — **updated** to use public-input contract instead of propagated `set_seed` failure
- `vibecomfy/ops/image.py`, `ops/video.py`, `ops/_common.py` — audited; no caller changes required
- `ready_templates/` — audited; `z_image` and others already register public inputs

**register_input / finalize_metadata callers (T10):**
- Post-finalize registrations in generated templates remain intentional (generated template convention)
- `vibecomfy/_helper_resolve.py` — registers broadcast-derived public inputs before returning converted workflows; finalize-after-register path relies on preservation
- `vibecomfy/ops/_common.py`, patches — finalize-after-register paths work correctly under new preservation semantics

---

## 15. API/GraphBuilder Parity Test

**Test:** `tests/test_workflow_core.py::test_compile_api_graphbuilder_parity`

Verifies that `compile("api")` and `_compile_graphbuilder()` produce the same normalized `{node_id: {input_name: source}}` mapping for target inputs. Uses a fake `GraphBuilder` so the parity check is not skipped off-machine.

---

## 16. Unresolved-Broadcast Test Rewrite

**Test:** `tests/test_workflow_core.py::test_helper_diagnostics_report_unresolved_broadcasts_before_compile`

Rewrote to assert both:
1. `wf.compile("api")` raises `WorkflowCompileError` with code `helper_edge_unresolved`
2. `wf.validate(schema_provider=None)` produces one error-severity `api_compile_failed` issue and `report.ok is False`

(Previously asserted only a diagnostic warning, not a compile error.)

---

## 17. prompt.py Duplicate Helper Note

`vibecomfy/runtime/prompt.py:93` contains a dead/duplicate `_prepare_prompt_async`. Nothing imports from `vibecomfy.runtime.prompt`; all live callers use `session.py`'s `_prepare_prompt_async` at line 863 (imported by `run.py` at line 28). The dead code in `prompt.py` was left untouched to avoid scope creep. It is a known discoverability trap: `rg '_prepare_prompt_async'` returns two definitions.

---

## 18. IR Contract Decisions

**Module:** `vibecomfy/contracts/ir.py`  
**Exposed via:** `vibecomfy/contracts/__init__.py` lazy `__getattr__`

**Stable codes:**
```python
ir.public_input.unregistered        # set_input called with unregistered name
ir.public_input.stale_target        # set_input target node/field no longer present
ir.validation.report_ok_field       # report.ok field is the public validation result
ir.validation.ok_implies_compile_api # report.ok=True implies compile('api') succeeded
ir.compile.edge_endpoint_resolved   # all compiled edges have reachable endpoints
ir.compile.helper_edge_rewired_or_reported  # helper edges are rewired or raised
```

**Shape constants:**
- `IR_CONTRACT_VERSION = "vibecomfy.ir_contract.v2.8.0"`
- `IR_CONTRACT_SHAPE = "ir_contract.v1"`

**Lazy import guarantee:** `vibecomfy.contracts.ir` is not imported until an IR attribute is accessed.

---

## 19. Escalations / Unresolved Items

None from Sprint 3 scope. Known open debt carried forward:

- **REMOVE-M4 markers:** `vibecomfy/porting/helpers.py` and `vibecomfy/porting/helper_resolve.py` re-exports are marked `# REMOVE-M4` for removal in M4.
- **Reroute/Primitive compile stripping:** deferred to M4+ per SD2.
- **prompt.py dead code:** `vibecomfy/runtime/prompt.py:93` `_prepare_prompt_async` — dead, safe to delete in a future sprint.
- **public-input-metadata debt:** legacy direct `metadata['unbound_inputs']` writes can still exist from code that has not been migrated. `set_input` no longer writes new ones but does not clear old ones.
- **wf-node-out-api-contract:** `.out(name)` still raises `NotImplementedError` for non-digit slot names. Deferred per MP-6 schema integration note in CLAUDE.md.

---

## 20. Files Changed (Sprint 3 cumulative)

### New files
- `vibecomfy/_workflow_helpers.py`
- `vibecomfy/_helper_resolve.py`
- `vibecomfy/_widget_aliases.py`
- `vibecomfy/contracts/ir.py`
- `docs/release_notes/v2.8.0.md`
- `docs/megaplan_chains/excellence_epic/prep-m3.md`
- `.importlinter`
- `tests/test_acceptance.py`
- `tests/test_contract_ir.py`
- `tests/test_widget_aliases.py`
- `tests/test_workflow_helpers.py`

### Modified files
- `pyproject.toml` (version → 2.8.0; import-linter dev dep)
- `uv.lock`
- `docs/release_notes.md`
- `vibecomfy/workflow.py`
- `vibecomfy/contracts/__init__.py`
- `vibecomfy/contracts/validation.py`
- `vibecomfy/porting/helpers.py` (compatibility wrapper)
- `vibecomfy/porting/helper_resolve.py` (compatibility wrapper)
- `vibecomfy/porting/widget_aliases.py`
- `vibecomfy/porting/widget_schema.py`
- `vibecomfy/porting/convert.py`
- `vibecomfy/porting/emitter.py`
- `vibecomfy/porting/strict_ready.py`
- `vibecomfy/porting/subgraph_resolve.py`
- `vibecomfy/porting/ui_emitter.py`
- `vibecomfy/registry/ready_template.py`
- `vibecomfy/runtime/session.py`
- `vibecomfy/runtime/run.py`
- `vibecomfy/runtime/eval_prompt.py`
- `vibecomfy/commands/run.py`
- `tests/test_edge_primitives.py`
- `tests/test_finalize_metadata.py`
- `tests/test_ready_template_helpers.py`
- `tests/test_run_command.py`
- `tests/test_runtime_run.py`
- `tests/test_runtime_session_validation.py`
- `tests/test_workflow_core.py`
