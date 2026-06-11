# Implementation Plan: M0 — Tier 1: All 11 LOW-risk reorg units

## Overview

Land all 11 LOW-risk mechanical reorg units from the phase2 reorg plan. Each unit is a behavior-preserving mechanical move — folder bundles, barrel-`__init__` re-exports, dead-file deletes, and the `nodes/` shim elimination. No logic changes; every public import path stays byte-for-byte valid.

### Verified Current State (as of 2026-06-11)

| Unit | Status | What's actually in the working tree |
|------|--------|-------------------------------------|
| 1 | **DONE** | `testing/__init__.py:60-66` already imports from `.fixtures` — NO-OP |
| 2 | **Partial** | `_debug_resolver.py` already gone; `node_index.json` still at root (`[]`, zero refs) |
| 3 | **NOT done** | `patches/resize_schema.py` exists (68 LOC), zero references, NOT in `patches/__init__.py` |
| 4 | **NOT done** | FOUR files at root: `node_packs.py` (465 LOC), `node_packs_lockfile.py` (334 LOC), `node_packs_install.py` (659 LOC), `node_packs_git.py` (123 LOC). `node_packs_git.py` has zero cross-refs with the other three; imported by `runtime/ensure_env.py:11` and `tests/test_node_packs_git.py:8`. |
| 5 | **NOT done** | `router.py` (51 LOC), `router_rules.py` (73 LOC) at root; internal cross-ref `router.py:8` → `router_rules`; external `extras.py:36` → `vibecomfy.router_rules` |
| 6 | **NOT done** | Two files at root: `fixtures.py` (288 LOC, zero Python importers, has `__main__` block for `python -m vibecomfy.fixtures`); `_agent_edit_debug.py` (504 LOC, 3 importers: `scripts/vibecomfy_debug.py:10`, `commands/debug.py:5`, `tests/test_cli_debug.py:143,181`) |
| 7 | **NOT done** | `wrapper_discovery.py` (616 LOC), `wrapper_codegen.py` (539 LOC) at `porting/`; internal cross-ref `wrapper_codegen.py:71` → `wrapper_discovery`; 6 external importers (3 files × 2 imports each) using `from vibecomfy.porting import wrapper_*` |
| 8 | **NOT done** | `eval.py` (401 LOC), `eval_plan.py` (187 LOC), `eval_prompt.py` (146 LOC), `preview_types.py` (83 LOC) at `runtime/`; internal cross-refs: `plan.py:8` → `preview_types`, `prompt.py:11` → `eval_plan`; external importers: `commands/runtime.py:13` (`from vibecomfy.runtime.eval import compile_eval_subgraph`), `test_agentic_affordances.py:12` (`import vibecomfy.runtime.eval_prompt as eval_prompt_module`), `test_agentic_affordances.py:25` (`from vibecomfy.runtime.eval_plan import plan_eval_node`), `tests/test_runtime_run.py` (5 sites: `from vibecomfy.runtime.eval import compile_eval_subgraph`) |
| 9 | **NOT done** | 2 of 5 dead runtime files already gone (`prompt.py`, `fingerprint.py`); 3 STILL EXIST: `discovery.py` (41 LOC), `policy.py` (35 LOC), `metadata.py` (52 LOC) — all verified zero Python importers |
| 10 | **NOT done** | All 19 shim files exist at `nodes/`; ~110 import sites use `from vibecomfy.nodes.X import`; `__init__.py` has 19 hardcoded wildcard imports; `__init__.pyi` has 19 hardcoded wildcard imports + `__all__: list[str]`; `_generated/__init__.py:1` exports `MODULES` list of all 19 pack names |
| 11 | **Partial** | `registry.py` and `factory.py` already gone; `provider.py:22` already imports `InputSpec`/`OutputSpec` from `.types`; `format.py` (9 LOC) has 3 external importers (`doctor.py:31`, `validate.py:17`, `session.py:931`); `diagnostics/__init__.py` has types defined inline at lines 8-53 (needs extraction to `findings.py`) |

### Locked decisions

- **Every barrel `__init__.py` re-exports the identical names** — existing `from vibecomfy.<x> import Y` paths stay byte-for-byte valid.
- **Dead-code deletes** (Units 2, 3, 9) confirmed via grep for zero importers.
- **Unit 5 (router) and Unit 10 (nodes/)** are the two that touch surfaces real code depends on — verify identity explicitly post-move.
- **Each unit lands as its own commit**, gate-green between each.
- **Thin shims at old locations for ALL moves** (Units 4, 5, 6, 7, 8) — this is the consistent strategy. No importer files are updated; thin shims preserve byte-for-byte compatibility universally.

### Decisions on open questions

1. **Unit 10 shim deletion**: Keep ALL 19 shim files. Do programmatic `__init__.py` rewrite only. The 19 wildcard lines become a loop over `_generated.MODULES`. Shims stay — `from vibecomfy.nodes.core import SaveImage` paths survive.

2. **Unit 4 includes node_packs_git.py**: The file EXISTS (verified). Bundle it as `node_packs/_git.py` with a thin shim at `node_packs_git.py`. This completes the "bundle ALL node_packs_* files into a package" intent.

3. **Unit 6 includes _agent_edit_debug.py**: The file EXISTS (verified). Move to `commands/_agent_edit_debug.py` with a thin shim at the old root location. This completes Unit 6's intended scope.

4. **Unit 7 uses thin shim strategy** (settled decision SD1): Create thin shims at `porting/wrapper_discovery.py` and `porting/wrapper_codegen.py` that re-export from the new `porting/wrappers/` package. No importer files are touched — all 6 external importers survive unchanged.

5. **Unit 8 uses thin shim strategy**: Create thin shims at `runtime/eval_prompt.py` and `runtime/eval_plan.py` that re-export from `runtime/eval/`. This preserves the 2 importers in `test_agentic_affordances.py`. `runtime/eval.py` becomes `runtime/eval/core.py`, and the new `runtime/eval/__init__.py` barrel preserves the `from vibecomfy.runtime.eval import compile_eval_subgraph` path.

6. **Unit 9 is NOT a NO-OP**: Three dead runtime files (`discovery.py`, `policy.py`, `metadata.py`) still exist and must be physically deleted.

7. **`queue_eval_subgraph` omitted from barrel**: Doesn't exist in any file (confirmed via grep). Not included.

8. **Unit 8 `preview_types.py`**: Exists at `runtime/preview_types.py` (confirmed). Move to `runtime/eval/preview_types.py`.

---

## Phase 0 — Land already-done units as NO-OP commits

### Step 1: Confirm and commit Unit 1 (testing fixtures)
**Complexity:** 1

1. **Verify** `vibecomfy/testing/__init__.py:60-66` already imports from `.fixtures` (confirmed — 5 names: `dry_runtime`, `make_handle_factory`, `make_workflow_factory`, `vibecomfy_handle_factory`, `vibecomfy_workflow_factory`).
2. **Gate**: `PYTHONHASHSEED=0 pytest tests/characterization -x -q`
3. **Commit** as NO-OP confirmation: `"Unit 1: testing fixture stubs — confirmed already wired (NO-OP)"`

### Step 2: Confirm and commit Unit 2 (_debug_resolver.py already gone)
**Complexity:** 1

1. **Verify** `_debug_resolver.py` absent from repo (confirmed — no file found, zero content references).
2. **Gate**: `python -c "import vibecomfy"` succeeds.
3. **Commit** as NO-OP: `"Unit 2: _debug_resolver.py removal — confirmed already gone (NO-OP)"`

---

## Phase 1 — Deletes (straightforward, lowest risk)

### Step 3: Delete node_index.json (Unit 2 remainder)
**Complexity:** 1

1. **Confirm** `node_index.json` contains `[]` and has zero references.
2. **Delete** `node_index.json`.
3. **Gate**: `python -c "import vibecomfy"` + characterization gate.
4. **Commit**.

### Step 4: Delete patches/resize_schema.py (Unit 3)
**Complexity:** 1

1. **Confirm** `vibecomfy/patches/resize_schema.py` is NOT in `patches/__init__.py`.
2. **Confirm** zero importers.
3. **Delete** `vibecomfy/patches/resize_schema.py`.
4. **Gate**: `python -c "import vibecomfy"` + characterization gate.
5. **Commit**.

### Step 5: Delete 3 remaining dead runtime files (Unit 9)
**Complexity:** 1

1. **Confirm** zero Python importers for all three (verified — `agentic/actors.py:8` is a docstring mention, not an import):
   - `vibecomfy/runtime/discovery.py`
   - `vibecomfy/runtime/policy.py`
   - `vibecomfy/runtime/metadata.py`
2. **Delete** all three files.
3. **Confirm** `vibecomfy/runtime/prompt.py` and `vibecomfy/runtime/fingerprint.py` are already absent.
4. **Gate**: `python -c "import vibecomfy"` + characterization gate.
5. **Commit**.

---

## Phase 2 — Units with thin-shim moves (no importer updates needed)

### Step 6: Bundle router + router_rules into router/ package (Unit 5)
**Complexity:** 2

1. **Create** `vibecomfy/router/` directory.
2. **Move** `vibecomfy/router.py` → `vibecomfy/router/_core.py`; `vibecomfy/router_rules.py` → `vibecomfy/router/_rules.py`.
3. **Update internal cross-ref** at `router/_core.py:8`: change `from vibecomfy.router_rules import rules` → `from ._rules import rules`.
4. **Create** `vibecomfy/router/__init__.py` barrel re-exporting `RouterResult`, `pick`, `Rule`, `register_route`, `rules`.
5. **Create thin shim** `vibecomfy/router_rules.py`: `from vibecomfy.router._rules import *`. Preserves `extras.py:36` and `router/_core.py` (now internal).
6. **Verify** `vibecomfy/__init__.py:15` (`from . import router`) still works — Python imports the `router/` package's `__init__.py`.
7. **Verify identity**: `python -c "from vibecomfy.router import pick, RouterResult; from vibecomfy.router_rules import register_route, rules; print('OK')"`.
8. **Gate**: characterization gate.
9. **Commit**.

### Step 7: Move fixtures.py → testing/_fixtures_smoke.py (Unit 6 — part A)
**Complexity:** 2

1. **Move** `vibecomfy/fixtures.py` → `vibecomfy/testing/_fixtures_smoke.py`.
2. **Create thin shim** `vibecomfy/fixtures.py` that re-exports from `vibecomfy.testing._fixtures_smoke` using `from vibecomfy.testing._fixtures_smoke import *` AND preserves the `__main__` block so `python -m vibecomfy.fixtures list` continues to work. The shim should include:
   ```python
   from vibecomfy.testing._fixtures_smoke import *
   from vibecomfy.testing._fixtures_smoke import __all__
   if __name__ == "__main__":
       from vibecomfy.testing._fixtures_smoke import main
       main()
   ```
3. **Verify** `python -m vibecomfy.fixtures list` still works.
4. **Gate**: characterization gate.
5. **Commit**.

### Step 8: Move _agent_edit_debug.py → commands/_agent_edit_debug.py (Unit 6 — part B)
**Complexity:** 2

1. **Move** `vibecomfy/_agent_edit_debug.py` → `vibecomfy/commands/_agent_edit_debug.py`.
2. **Create thin shim** `vibecomfy/_agent_edit_debug.py`: `from vibecomfy.commands._agent_edit_debug import *`. Preserves all 3 importers (`scripts/vibecomfy_debug.py:10`, `commands/debug.py:5`, `tests/test_cli_debug.py:143,181`).
3. **Verify** `python -c "from vibecomfy._agent_edit_debug import main, add_debug_subcommands, dispatch; print('OK')"`.
4. **Gate**: characterization gate.
5. **Commit**.

### Step 9: Move wrappers into porting/wrappers/ package (Unit 7)
**Complexity:** 2

1. **Create** `vibecomfy/porting/wrappers/` directory.
2. **Move** `vibecomfy/porting/wrapper_discovery.py` → `vibecomfy/porting/wrappers/discovery.py`.
3. **Move** `vibecomfy/porting/wrapper_codegen.py` → `vibecomfy/porting/wrappers/codegen.py`.
4. **Update internal cross-ref** at `wrappers/codegen.py:71`: change `from vibecomfy.porting.wrapper_discovery import ClassSpec, InputFieldSpec` → `from .discovery import ClassSpec, InputFieldSpec`.
5. **Create** `vibecomfy/porting/wrappers/__init__.py` barrel re-exporting `ClassSpec`, `InputFieldSpec`, `DiscoveryError`, `Source`, `DEFAULT_PRECEDENCE`, `discover_all`, `discover_pack`, `known_pack_slug`, `sha256_of_path` from discovery.py and `GENERATOR_VERSION`, `RenderResult`, `parse_generated_header`, `render_pack`, `render_widget_schema` from codegen.py.
6. **Create thin shims** at old locations:
   - `vibecomfy/porting/wrapper_discovery.py`: `from vibecomfy.porting.wrappers.discovery import *`
   - `vibecomfy/porting/wrapper_codegen.py`: `from vibecomfy.porting.wrappers.codegen import *`
   This preserves ALL 6 external importers without touching any of them:
   - `commands/nodes.py:24-25`
   - `tests/test_wrapper_codegen.py:18`
   - `tests/test_wrapper_discovery.py:16`
   - `scripts/demo_wrapper_codegen.py:27-28`
7. **Verify** `python -c "from vibecomfy.porting import wrapper_discovery as wd; from vibecomfy.porting import wrapper_codegen as wc; print('OK')"`.
8. **Gate**: characterization gate.
9. **Commit**.

### Step 10: Move eval files into runtime/eval/ package (Unit 8)
**Complexity:** 2

1. **Create** `vibecomfy/runtime/eval/` directory.
2. **Move files**:
   - `vibecomfy/runtime/eval.py` → `vibecomfy/runtime/eval/core.py`
   - `vibecomfy/runtime/eval_plan.py` → `vibecomfy/runtime/eval/plan.py`
   - `vibecomfy/runtime/eval_prompt.py` → `vibecomfy/runtime/eval/prompt.py`
   - `vibecomfy/runtime/preview_types.py` → `vibecomfy/runtime/eval/preview_types.py`
3. **Update internal imports**:
   - `plan.py:8` → `from .preview_types import preview_plan_for_type`
   - `prompt.py:11` → `from .plan import EvalNodePlan, plan_eval_node`
4. **Create** `vibecomfy/runtime/eval/__init__.py` barrel re-exporting `compile_eval_subgraph`, `EvalNodePlan`, `plan_eval_node`, `EvalNodeResult`, `eval_node`, `eval_node_sync`, `queue_api_for_plan`, `PreviewInjection`, `PreviewPlan`, `preview_plan_for_type`. Omit `queue_eval_subgraph` (doesn't exist — confirmed via grep).
5. **Create thin shims** at old locations:
   - `vibecomfy/runtime/eval_prompt.py`: `from vibecomfy.runtime.eval.prompt import *`
   - `vibecomfy/runtime/eval_plan.py`: `from vibecomfy.runtime.eval.plan import *`
   This preserves both importers in `test_agentic_affordances.py:12,:25`.
6. **Verify** the barrel path: `python -c "from vibecomfy.runtime.eval import compile_eval_subgraph; print('OK')"`. This works because `runtime/eval` is now a package with `__init__.py`.
7. **Verify** shim paths: `python -c "import vibecomfy.runtime.eval_prompt as ep; from vibecomfy.runtime.eval_plan import plan_eval_node; print('OK')"`.
8. **Gate**: characterization gate.
9. **Commit**.

---

## Phase 3 — Unit 4: Bundle ALL node_packs_* files (highest complexity)

### Step 11: Bundle all 4 node_packs_* files into node_packs/ package (Unit 4)
**Complexity:** 3

1. **Create** `vibecomfy/node_packs/` directory **if it doesn't already exist**. Note: after this step, `node_packs.py` at root is a shim, not the real module; `node_packs/` is the directory package.
   - To avoid a transient name collision during the move, do the moves before creating the package `__init__.py`.
2. **Move files**:
   - `vibecomfy/node_packs.py` → `vibecomfy/node_packs/_defs.py`
   - `vibecomfy/node_packs_lockfile.py` → `vibecomfy/node_packs/_lockfile.py`
   - `vibecomfy/node_packs_install.py` → `vibecomfy/node_packs/_install.py`
   - `vibecomfy/node_packs_git.py` → `vibecomfy/node_packs/_git.py`
3. **Update internal cross-references** to relative imports:
   - `_defs.py:7`: `from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile` → `from ._lockfile import LockEntry, read_lockfile`
   - `_install.py:7`: `from vibecomfy.node_packs import CustomNodePack, get_known_node_packs, resolve_node_packs, unresolved_class_types` → `from ._defs import CustomNodePack, get_known_node_packs, resolve_node_packs, unresolved_class_types`
   - `_install.py:8`: `from vibecomfy.node_packs_lockfile import LockEntry, upsert_lockfile_entry` → `from ._lockfile import LockEntry, upsert_lockfile_entry`
   - `_git.py` has no cross-refs to the other three (confirmed) — no updates needed.
4. **Create** `vibecomfy/node_packs/__init__.py` barrel re-exporting all public names from all four sub-modules:
   - From `_defs`: `CustomNodePack`, `get_known_node_packs`, `resolve_node_packs`, `unresolved_class_types`
   - From `_lockfile`: `LockEntry`, `read_lockfile`, `write_lockfile`, `upsert_lockfile_entry`
   - From `_install`: install-related public names (check `__all__` if present, otherwise all public functions/classes)
   - From `_git`: `InstalledPackGitRef`, `find_installed_pack_ref`
5. **Create thin shims** at ALL old locations:
   - `vibecomfy/node_packs.py`: `from vibecomfy.node_packs._defs import *`
   - `vibecomfy/node_packs_lockfile.py`: `from vibecomfy.node_packs._lockfile import *`
   - `vibecomfy/node_packs_install.py`: `from vibecomfy.node_packs._install import *`
   - `vibecomfy/node_packs_git.py`: `from vibecomfy.node_packs._git import *`
   This preserves ALL external import paths (~50+ importers across the codebase) without touching any of them.
6. **Verify edge case**: `commands/nodes.py:22` does `import vibecomfy.node_packs_install as node_packs_install` (direct `import`, not `from`). The thin shim module's namespace will contain the re-exported names via `from ._install import *`, so `node_packs_install.SomeClass` attribute access works through the shim. Verify: `python -c "import vibecomfy.node_packs_install as npi; print(dir(npi)[:10])"`.
7. **Verify** key import paths:
   - `python -c "from vibecomfy.node_packs import resolve_node_packs, CustomNodePack; print('OK')"`
   - `python -c "from vibecomfy.node_packs_lockfile import LockEntry; print('OK')"`
   - `python -c "from vibecomfy.node_packs_git import find_installed_pack_ref; print('OK')"`
8. **Gate**: characterization gate.
9. **Commit**.

**Note on move order**: Python cannot have both a `node_packs.py` file and a `node_packs/` directory in the same parent package. The move sequence must be:
1. Rename `node_packs.py` → `node_packs/_defs.py` (via git mv or OS move into the newly-created `node_packs/` dir)
2. Create `node_packs/__init__.py`
3. Create thin shim `node_packs.py`
The directory `node_packs/` must be created before the file moves into it. Use `mkdir -p vibecomfy/node_packs` first, then move all four files in, then create `__init__.py` and the four thin shims at the old locations.

---

## Phase 4 — Unit 10: Programmatic nodes/__init__.py

### Step 12: Rewrite nodes/__init__.py with programmatic wildcard imports (Unit 10)
**Complexity:** 2

1. **Read** `vibecomfy/nodes/_generated/__init__.py:1` — confirmed: `MODULES = ['core', 'kjnodes', 'ltxvideo', 'videohelpersuite', 'controlnet_aux', 'depthanythingv2', 'wanvideowrapper', 'qwentts', 'qwen3tts', 'gguf', 'rgthree', 'sam2', 'wananimatepreprocess', 'ailab_audioduration', 'custom_scripts', 'florence2', 'gimm_vfi', 'melbandroformer', 'vibecomfy_internal']` (19 entries).
2. **Rewrite** `vibecomfy/nodes/__init__.py`: replace the 19 hardcoded `from vibecomfy.nodes.<pack> import *` lines with a loop over `_generated.MODULES` that imports each, collects `__all__`, and merges into globals. The programmatic import pattern:
   ```python
   from __future__ import annotations
   from vibecomfy.nodes._generated import MODULES

   __all__: list[str] = []
   for _module_name in MODULES:
       _mod = __import__(f"vibecomfy.nodes.{_module_name}", fromlist=["*"])
       _mod_all = getattr(_mod, "__all__", None)
       if _mod_all is not None:
           __all__.extend(_mod_all)
           for _name in _mod_all:
               globals()[_name] = getattr(_mod, _name)
   ```
3. **Update** `vibecomfy/nodes/__init__.pyi` in lockstep. Since type checkers cannot resolve dynamic imports, the `.pyi` must declare a static `__all__: list[str]` listing all symbol names. Replace the 19 wildcard import lines with a single `__all__: list[str]` declaration. To get the actual list: run `python -c "from vibecomfy.nodes._generated import MODULES; all_names = []; exec('for m in MODULES:\\n    mod = __import__(f\\\"vibecomfy.nodes.{m}\\\", fromlist=[\\\"*\\\"])\\n    all_names.extend(getattr(mod, \\\"__all__\\\", []))'); print(repr(sorted(all_names)))'"` and copy the result into `__all__: list[str] = [...]`. The `.pyi` content:
   ```python
   from __future__ import annotations
   __all__: list[str] = [...]  # static list of all exported names
   ```
   Alternatively, keep the 19 wildcard import lines in the `.pyi` since it's a stub file for type-checkers — the wildcard imports work statically. Decision: keep the `.pyi` as-is (19 wildcard lines) because type-checkers resolve them statically and it's the safest approach.
4. **Keep all 19 shim files** — do not delete any. `from vibecomfy.nodes.core import SaveImage` paths survive.
5. **Verify identity**:
   - `python -c "from vibecomfy.nodes import *; print(len(__all__))"` — record the count before and after; must be identical.
   - `python -c "from vibecomfy.nodes.core import SaveImage; print('OK')"`
   - `python -c "from vibecomfy.nodes import SaveImage; print('OK')"`
6. **Gate**: characterization gate.
7. **Commit**.

---

## Phase 5 — Unit 11: Schema/diagnostics tidy

### Step 13: Merge format.py into validate.py; extract diagnostics to findings.py (Unit 11)
**Complexity:** 2

1. **Merge** `vibecomfy/schema/format.py` (9 LOC — `format_issue` function) into `vibecomfy/schema/validate.py`. Append the function to validate.py.
2. **Create thin shim** `vibecomfy/schema/format.py`: `from vibecomfy.schema.validate import format_issue`. Preserves 3 external importers (`doctor.py:31`, `validate.py:17`, `session.py:931`).
3. **Extract diagnostics types** from `vibecomfy/diagnostics/__init__.py` (lines 8-53: `Severity` type alias, `DiagnosticFinding` dataclass, `PatchSuggestion` dataclass, `finding_messages`, `findings_payload`, `patch_suggestions_payload`) to new `vibecomfy/diagnostics/findings.py`.
4. **Rewrite** `vibecomfy/diagnostics/__init__.py` as pure re-export barrel:
   ```python
   from __future__ import annotations
   from vibecomfy.diagnostics.findings import (
       DiagnosticFinding, PatchSuggestion, Severity,
       finding_messages, findings_payload, patch_suggestions_payload,
   )
   from vibecomfy.diagnostics.health import HealthReport, SubcheckFinding, SubcheckResult

   __all__ = [
       "DiagnosticFinding",
       "HealthReport",
       "PatchSuggestion",
       "Severity",
       "SubcheckFinding",
       "SubcheckResult",
       "finding_messages",
       "findings_payload",
       "patch_suggestions_payload",
   ]
   ```
5. **Verify** `provider.py:22` already imports `InputSpec`/`OutputSpec` from `.types` (confirmed — no dedup needed). No changes to `provider.py`.
6. **Verify** `registry.py` and `factory.py` are already absent from `vibecomfy/schema/` (confirmed — no merge needed).
7. **Verify** `python -c "from vibecomfy.schema.format import format_issue; print('OK')"`.
8. **Verify** `python -c "from vibecomfy.diagnostics import DiagnosticFinding, HealthReport; print('OK')"`.
9. **Gate**: characterization gate.
10. **Commit**.

---

## Execution Order

1. **Phase 0**: Steps 1–2 (NO-OP commits for Units 1 and 2 partial)
2. **Phase 1**: Steps 3–5 (deletes: node_index.json, resize_schema.py, dead runtime files)
3. **Phase 2**: Steps 6–10 (thin-shim moves: router, fixtures, _agent_edit_debug, wrappers, eval)
4. **Phase 3**: Step 11 (node_packs bundle — all 4 files)
5. **Phase 4**: Step 12 (nodes/__init__.py programmatic rewrite)
6. **Phase 5**: Step 13 (schema/diagnostics tidy)

Gate green between each commit.

## Validation Order

1. After each step: `PYTHONHASHSEED=0 pytest tests/characterization -x -q`
2. After each phase: `python -c "import vibecomfy"` + spot-check key import paths
3. After final step: full `pytest` against `tests/known_failures.txt` baseline
4. Final: `python -c "import vibecomfy; print([n for n in vibecomfy.__all__])"` — verify all names importable
