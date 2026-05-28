# Handoff M2B — Node-spec cleanup + schema-provider handoff execution record

**Generated:** 2026-05-28T18:30Z  
**Source:** Approved sprint brief `m2b-node-spec-and-schema-handoff.md`, plan `sprint-2b-node-spec-cleanup-20260528-1639/plan_v2.meta.json`  
**Evidence:** All measured evidence gathered across tasks T1–T14, verified via `vibecomfy check --json` and focused test suites.

---

## 1. Deleted Files

Three legacy rich-wrapper node-spec modules were deleted (T11) after all safety gates passed:

| File | Pre-delete size | Origin commit | Status |
|------|----------------|---------------|--------|
| `vibecomfy/nodes/comfyui_kjnodes.py` | ~260,510 bytes (8,713 lines) | `9882173` | **Deleted** |
| `vibecomfy/nodes/comfyui_ltxvideo.py` | ~90,509 bytes (2,802 lines) | `9882173` | **Deleted** |
| `vibecomfy/nodes/rgthree_comfy.py` | ~34,988 bytes (765 lines) | `9882173` | **Deleted** |

**Preserved** (thin-wrapper re-export modules + generated counterparts):
- `vibecomfy/nodes/kjnodes.py` + `.pyi` stub
- `vibecomfy/nodes/ltxvideo.py` + `.pyi` stub
- `vibecomfy/nodes/rgthree.py` + `.pyi` stub
- `vibecomfy/nodes/_generated/kjnodes.py` (9,142 lines) + `.pyi` stub
- `vibecomfy/nodes/_generated/ltxvideo.py` (2,874 lines) + `.pyi` stub
- `vibecomfy/nodes/_generated/rgthree.py` (831 lines) + `.pyi` stub

---

## 2. Stale-Reference Scan Results

### Pre-delete scan (T1, T9)
```
rg 'comfyui_kjnodes|comfyui_ltxvideo|rgthree_comfy' --type py --glob '!vendor/**'
→ scripts/demo_wrapper_codegen.py:78: from vibecomfy.nodes.rgthree_comfy import Context_rgthree
```
One stale reference found. All other non-vendor Python files clean.

### Post-rewrite scan (T10)
`scripts/demo_wrapper_codegen.py` line 78 rewritten to use `vibecomfy.nodes.rgthree` (thin-wrapper). Smoke test passed: all three demo packs discovered, before/after demo produces identical API JSON, 329 total typed calls.

```
rg 'comfyui_kjnodes|comfyui_ltxvideo|rgthree_comfy' --type py --glob '!vendor/**'
→ Exit 1 (no matches except test-fixture strings in tests/test_check.py and
  check-infrastructure path constants in vibecomfy/checks.py)
```

### Post-delete scan (T11)
Only test-fixture strings in `tests/test_check.py` and `vibecomfy/checks.py` path constants remain — **zero live imports or usage of legacy module names**.

---

## 3. Final `check --json` Status (Post-Deletion)

```bash
python -m vibecomfy.cli check --json
# Exit code: 0
# Top-level: {"ok": true, "status": "ok"}
```

All 7 named checks pass:

| Check | Status | Key detail |
|-------|--------|------------|
| `non_vendor_stale_legacy_references` | pass | 0 matches |
| `thin_wrapper_import_smoke` | pass | kjnodes (230), ltxvideo (75), rgthree (24) — all export counts match generated |
| `representative_wrapper_symbol_import_smoke` | pass | All 6 symbols importable |
| `model_registry_node_pack_validation` | pass | 50 entries, 67 targets, 47 normalized, 3 documented gaps |
| `schema_object_info_cache_access` | pass | 1,401 classes, 23 pack files |
| `known_node_packs_usage_scan` | pass | 0 matches |
| `legacy_file_presence` | state | All 3 legacy files reported missing (correct post-deletion) |

---

## 4. `get_known_node_packs()` Consumer Inventory

All consumers migrated from the removed import-time `KNOWN_NODE_PACKS` constant to the lazy `get_known_node_packs()` accessor (T3, T4). Fingerprint-based `@lru_cache(maxsize=16)` cache keyed on resolved lockfile path + existence + mtime_ns + size.

### Runtime / Core consumers
1. **`vibecomfy/node_packs.py`** — defines `get_known_node_packs()`, `resolve_node_packs()`, `unresolved_class_types()`. `_known_node_packs()` preserved as uncached builder; `_cached_known_node_packs` is the `@lru_cache` private worker.
2. **`vibecomfy/node_packs_install.py`** — `install_pack()` calls `get_known_node_packs()` for post-install validation.
3. **`vibecomfy/runtime/session.py`** — `EmbeddedSession` uses `get_known_node_packs()` for runtime node-pack awareness.
4. **`vibecomfy/porting/wrapper_discovery.py`** — `discover_wrappers()` uses `get_known_node_packs()` for wrapper-to-pack mapping.

### Tool / CLI consumers
5. **`vibecomfy/commands/schemas.py`** — schema commands iterate `get_known_node_packs()`.
6. **`tools/check_pack_provenance.py`** — provenance checker monkeypatched via module namespace.
7. **`tools/backfill_custom_node_refs.py`** — reference backfiller.
8. **`tools/clone_and_extract_packs.py`** — pack extraction.
9. **`tools/validate_templates_against_packs.py`** — template validation.
10. **`tools/_legacy/narrate_template.py`** — legacy narration tool.

### Test consumers
11. **`tests/test_node_packs_compat.py`** — lockfile-mutation test proves temp `custom_nodes.lock` changes are reflected in the same interpreter via fingerprint-based cache invalidation.
12. **`tests/test_pack_provenance.py`** — monkeypatches `get_known_node_packs` on `tools.check_pack_provenance` module namespace.
13. **`tests/test_schemas_ensure.py`** — `TestNodePacksMapping` iterates `get_known_node_packs()` (lines 595–618).

### Verification
```bash
rg 'KNOWN_NODE_PACKS' --type py --glob '!vendor/**'
→ Exit 1 (no matches)
```

---

## 5. Generator Cleanup Behavior and Marker-Preservation Rule

### Location: `tools/generate_node_shims.py`

**Cleanup entry point** (T12, T13): `_prune_stale_thin_shims()` in `main()`.

**Conservative pruning rules:**
1. **Zero-cache guard**: If `_cache_pack_files()` returns zero pack files, pruning is skipped and a warning is emitted: `"warning: object-info cache pack-file discovery returned zero pack files; skipping thin-shim pruning"`.
2. **Target-set authority**: `_target_modules()` computes the authoritative module set from `BASE_TARGET_MODULES` (19 hardcoded modules) plus any additional modules discovered from `PACK_FILE_MODULES` mapping and pack-file names.
3. **Marker-based identification**:
   - `_generated/<module>.py`: Must start with `"""Auto-generated thin wrappers for ComfyUI node classes.`
   - `_generated/<module>.pyi`: Must start with `"""Type stubs for generated ComfyUI node wrappers."""`
   - `vibecomfy/nodes/<module>.py`: Must be a structural re-export-only file (2–4 lines, `from vibecomfy.nodes._generated.<module> import *` pattern).
   - `vibecomfy/nodes/<module>.pyi`: Must be a structural re-export-only stub.
4. **Rich-wrapper exclusion**: `wrapper_codegen.py`-generated rich `.add()` modules do not match thin-shim markers and are never pruned.
5. **`__init__.py` / `__init__.pyi`**: Always preserved (not candidate for pruning).

**Real-tree verification** (T13):
```bash
python -m tools.generate_node_shims
# → "generated 1399 wrappers across 19 modules"

git diff --stat -- vibecomfy/nodes/
# → Only the 3 intentional legacy deletions. Zero unexpected generated churn.
```

**Test coverage** (T13): `tests/test_node_shims.py::test_prune_stale_thin_shims_removes_only_generated_outputs` — builds a temp tree with 11 scenarios (stale generated .py/.pyi, stale re-export .py/.pyi, live targets, hand-authored files without markers), exercises cleanup, proves only stale generated files are removed.

---

## 6. Schema-Provider Contract for Sprint 4b

### Canonical provider: `ConversionSchemaProvider`

**Location:** `vibecomfy/schema/provider.py` (lines 352–597)

**Precedence order** (first hit wins):
1. **Committed `node_index.json`** — `LocalSchemaProvider` (confidence: 1.0)
2. **Provenance-matched object_info cache** — `ObjectInfoSchemaProvider` loaded from `object_info_cache_path`, with fingerprint metadata match validation (confidence: 0.8 when fingerprint matches, 0.4 when stale, 0.5 when missing metadata)
3. **Object_info index** — `ObjectInfoIndexSchemaProvider` backed by `object_info_index_root/index.json` + per-pack JSON files (confidence: 0.7)
4. **Source parser** — `SourceSchemaProvider` scanning installed custom-node source trees (confidence: 0.9)
5. **Widget schema fallback** — positional `widget_N` → named input aliases from `WIDGET_SCHEMA` (confidence: 0.3)
6. **Runtime** — `RuntimeSchemaProvider` consulted **only** when `enable_runtime=True` (off by default; confidence: 0.6)

**Each hit records provenance** via `SchemaSourceInfo` with `provider_name`, `source_path`, `cache_path`, `confidence`, `conflicts`, and `ignored_evidence`.

**Returns `None`** for unknown class types — never silently falls through.

### Current wiring in `vibecomfy/commands/port.py`

```python
# _build_conversion_provider() (line 918–931):
ConversionSchemaProvider(
    object_info_cache_path=object_info_cache,
    object_info_index_root=Path(__file__).resolve().parents[1] / "porting" / "cache" / "object_info",
    widget_schema=WIDGET_SCHEMA,
    enable_runtime=runtime_enabled,
    runtime_server_url=server_url,
)

# _build_authoring_provider() (line 934–939):
get_authoring_schema_provider(
    object_info_cache_path=object_info_cache,
    object_info_index_root=Path(__file__).resolve().parents[1] / "porting" / "cache" / "object_info",
)
```

**`object_info_index_root`** resolves to: `<repo>/vibecomfy/porting/cache/object_info/`

### Cache path

```
vibecomfy/porting/cache/object_info/
├── index.json                              (class_type → filename mapping)
├── provenance.json                         (origin metadata)
├── <PackName>@<source-tag>.json           (per-pack class entries)
│   e.g., comfy_core@runpod-snapshot.json
│         ComfyUI-KJNodes@runpod-snapshot.json
│         ComfyUI-LTXVideo@runpod-snapshot.json
│         rgthree-comfy@runpod-snapshot.json
│         ComfyUI-Custom-Scripts@stub.json  (stub = no runtime needed)
│         ...
└── (24 pack files total, 23 excluding index.json/provenance.json)
```

### Object-info cache refresh/extraction commands

**CLI: `vibecomfy schemas refresh`**
```bash
# From a live server
python -m vibecomfy.cli schemas refresh --server-url http://localhost:8188 --json

# From a captured object_info JSON dump
python -m vibecomfy.cli schemas refresh --source path/to/object_info.json --json

# From a structured cache directory
python -m vibecomfy.cli schemas refresh --source vibecomfy/porting/cache/object_info/ --json
```

**CLI: `vibecomfy schemas validate-coverage`**
```bash
python -m vibecomfy.cli schemas validate-coverage <template_path> --json
```

**Programmatic:** `refresh_from_source()` in `vibecomfy/porting/object_info/serialize.py`.

---

## 7. Measured Class Count, Pack-File Count, Stub-Pack List

| Metric | Value |
|--------|-------|
| Schema cache class count | **1,401** classes |
| Pack-file count | **23** pack files (24 total JSON files in cache dir, minus `index.json`) |
| Generated wrappers | **1,399** across **19** modules |
| Stub-pack inventory | **19** items |
| Model registry entries | **50** entries, **67** targets (47 normalized, 3 documented gaps) |

**Stub-pack inventory** (from `check --json`):
`ailab_audioduration`, `controlnet_aux`, `core`, `custom_scripts`, `depthanythingv2`, `florence2`, `gguf`, `gimm_vfi`, `kjnodes`, `ltxvideo`, `melbandroformer`, `qwen3tts`, `qwentts`, `rgthree`, `sam2`, `vibecomfy_internal`, `videohelpersuite`, `wananimatepreprocess`, `wanvideowrapper`

---

## 8. Degraded / Off-Machine Behavior

### ConversionSchemaProvider
When ComfyUI runtime is unavailable (CI, off-machine):
- **Tier 1** (node_index.json): Available if committed — no degradation.
- **Tier 2** (object_info cache): Available if cached files exist and fingerprint matches expected runtime identity. Confidence degrades to 0.4 if fingerprint is stale, 0.5 if fingerprint metadata is missing.
- **Tier 3** (object_info index): Available from committed `vibecomfy/porting/cache/object_info/` — no degradation.
- **Tier 4** (source parser): Available if custom-node source trees are installed — no degradation.
- **Tier 5** (widget schema): Always available as hardcoded fallback — confidence 0.3.
- **Tier 6** (runtime): Off by default (`enable_runtime=False`). Degraded → returns `None` when no prior tier hits.

### Generator cleanup
When `_cache_pack_files()` returns zero pack files (degraded/empty cache), pruning is **skipped with a warning** rather than computing a minimal target set from `BASE_TARGET_MODULES` alone. This prevents accidental deletion of live shims.

### Node-spec runtime checks
If no ComfyUI-capable CI or scheduled lane exists, node-spec validation is **degraded by design** — the object_info cache provides the offline truth source. See §11 for release-validation follow-up.

---

## 9. Sprint 4b Escalation Rule for Weak Coverage

If schema-provider coverage is weak (e.g., ready-template class-type coverage falls below an acceptable threshold or critical packs are stub-only), **sprint 4b must treat that as a blocker or explicit escalation** rather than silently falling back to heuristics.

**Current coverage measurement**: `vibecomfy schemas validate-coverage <template_path> --json` reports per-template class-type coverage against the object_info cache. This is the canonical measurement tool sprint 4b should use.

**Known weak-coverage areas**:
- Stub packs (`ComfyUI-Custom-Scripts`, `ComfyUI-Florence2`, `ComfyUI-GIMM-VFI`, `ComfyUI-MelBandRoformer`, `comfyui_controlnet_aux`) have minimal object_info entries — these are placeholder stubs, not full runtime captures.
- `ace_step` node_pack in `models.yaml` has no corresponding `CustomNodePack` in `node_packs.py` — documented as a gap.
- `comfy_core` and `kijai_ltx` are documented gaps in the model registry alias map.

---

## 10. Release-Validation Follow-Up

**Owner:** Porting / CI workstream  
**Target sprint:** Sprint 4b or Sprint 5  
**Command:**
```bash
python -m vibecomfy.cli schemas validate-coverage <template_path> --json
```

**Required before release:**
1. Run node-spec validation on a ComfyUI-equipped machine (RunPod or local GPU).
2. Refresh the object_info cache from a live runtime:
   ```bash
   python -m vibecomfy.cli schemas refresh --server-url <live_server_url> --json
   ```
3. Re-run `python -m vibecomfy.cli check --json` — verify `schema_object_info_cache_access` is still `pass` and class count has not regressed.
4. Run `python -m tools.generate_node_shims` and verify zero unexpected diff.
5. If stub-only packs remain, document their degraded status explicitly in the release notes.

**Manual operator command** (when no automated CI lane exists):
```bash
# 1. Launch a ComfyUI server (embedded or RunPod)
# 2. Capture object_info
python -m vibecomfy.cli schemas refresh --server-url http://localhost:8188 --json
# 3. Validate coverage for all ready templates
for tmpl in ready_templates/*/*.py; do
  python -m vibecomfy.cli schemas validate-coverage "$tmpl" --json
done
```

---

## 11. Baseline / Final Test Status Comparison

### Baseline (T2 — before any edits)
| Test file | Result |
|-----------|--------|
| `test_node_packs_compat.py` | **1 failed**, 2 passed |
| `test_pack_provenance.py` | 6 passed |
| `test_schemas_ensure.py` | **1 failed**, 28 passed |
| `test_models_registry.py` | 22 passed |
| `test_template_roundtrip.py` | **4 failed**, 2 passed, 65 skipped |
| **Broad** (`pytest -q`) | 115 failed, 1370 passed, 73 skipped, 6 errors + 12 collection-error files |

### Final (T14 — after all edits)

**Focused suite** (12 modules directly affected by sprint changes):
```bash
python -m pytest tests/test_node_packs_compat.py tests/test_pack_provenance.py \
  tests/test_schemas_ensure.py tests/test_models_registry.py \
  tests/test_models_registry_node_packs.py tests/test_check.py \
  tests/test_cli_misc.py tests/test_node_shims.py \
  tests/test_generated_node_wrappers.py tests/test_wrapper_discovery.py \
  tests/test_nodes_install.py tests/test_template_roundtrip.py -q
```
**Result: 5 failed, 153 passed, 65 skipped**

| Failure | Status |
|---------|--------|
| `test_extract_class_types_from_real_template` | **Pre-existing baseline** (schemas_ensure.py) |
| `test_generated_wrapper_rejects_multiple_positional_workflows` | **Pre-existing baseline** (nested workflow context binding) |
| `test_ready_template_matches_source_api[video/wan_i2v]` | **Pre-existing baseline** (roundtrip) |
| `test_audited_seed_sensitive_fields_keep_source_values_and_types[...]` | **Pre-existing baseline** (voice type drift) |
| `test_wan_i2v_matches_independent_golden_api_fixture` | **Pre-existing baseline** (roundtrip) |

**All failures are pre-existing baseline failures.** Zero regressions introduced by sprint 2b changes.

**Broad suite** (`pytest -q`): Still blocked by pre-existing collection errors in `tests/test_agentic_affordances.py` and `tests/test_testing_api.py` (`Plugin already registered under a different name`). These are unrelated to sprint 2b changes and were present in the baseline.

### Regression verification
Focused test files that were **passing at baseline and continue to pass**:
- `test_pack_provenance.py`: 6 passed (unchanged)
- `test_models_registry.py`: 22 passed (unchanged)
- `test_models_registry_node_packs.py`: **18 passed** (new tests added in T7)
- `test_node_packs_compat.py`: **4 passed** (improved from 1F/2P baseline — the pre-existing failure was resolved by the lazy catalog migration in T3)
- `test_check.py`: All passed (new tests added in T8)
- `test_cli_misc.py`: All passed
- `test_node_shims.py`: 4 passed (unchanged)
- `test_wrapper_discovery.py`: All passed (unchanged)
- `test_nodes_install.py`: All passed (unchanged)

---

## 12. Additional Artifacts

### Model registry node-pack alias validation (T6, T7)
- **Aliases defined**: `comfy_gguf → comfyui-gguf`, `ltx → comfyui-ltxvideo`, `wan_wrapper → comfyui-wanvideowrapper`
- **Documented gaps**: `comfy_core`, `kijai_ltx`, `ace_step`
- **Helper**: `canonical_model_node_pack(name)` normalizes aliases without mutating stored `ModelTarget.node_pack` values
- **Validation**: Post-load diagnostic; each target validated independently; typos outside canonical/alias/gap sets raise `ValueError`

### Check command implementation (T8)
- **Location**: `vibecomfy/commands/check.py` + `vibecomfy/checks.py`
- **CLI**: `python -m vibecomfy.cli check --json`
- **JSON output**: Named checks with `ok`/`status`/`details`, top-level `schema_cache_class_count`, `pack_file_count`, `stub_pack_inventory`

### Demo script update (T10)
- `scripts/demo_wrapper_codegen.py` line 78: `vibecomfy.nodes.rgthree_comfy` → `vibecomfy.nodes.rgthree`
- `Context_rgthree.add(wf_after)` → `Context_rgthree(wf_after)` (thin-wrapper function-call API)
- Smoke test passes: all three demo packs discovered, before/after demo produces identical API JSON, 329 total typed calls

---

## 13. Deferred Risks

1. **Stub packs**: 5 packs (`custom_scripts`, `florence2`, `gimm_vfi`, `melbandroformer`, `controlnet_aux`) are stub-only — no runtime object_info capture. Coverage is weak for these. Sprint 4b must treat these as documented gaps.

2. **Broad test suite**: Pre-existing collection errors in `test_agentic_affordances.py` and `test_testing_api.py` block full `pytest -q`. These are unrelated to sprint 2b and should be addressed separately.

3. **Off-machine node-spec validation**: The committed object_info cache is the offline truth source. Without periodic refresh from a ComfyUI-equipped machine, the cache can drift from reality. Sprint 4b should establish a scheduled refresh cadence.

4. **`ace_step` pack**: No corresponding `CustomNodePack` in `node_packs.py` and no pack file in the object_info cache. Models referencing `ace_step` rely on the documented-gap allowlist. Sprint 7 or a follow-up should resolve this.

5. **Static pack seed restart limitation**: `get_known_node_packs()` reflects lockfile changes in-process via fingerprint-based cache invalidation, but edits to `_STATIC_NODE_PACKS` in `vibecomfy/node_packs.py` still require a process restart.
