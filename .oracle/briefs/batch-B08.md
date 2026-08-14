# MEGADO BATCH B08-cut [HARD] — Deterministic endpoint integrity

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — executor: Grok (grok-4.6, workspace-write). You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only.

## Context — the C8/C9 root (explorer-verified to file:line)

Failure class C8 ("Missing stable link from port", ~6 scenarios) and C9 (wrong-semantic edits) share ONE editor/catalog defect:

1. **Phantom-slot chain**: `resolve_source_endpoint` (`vibecomfy/porting/resolution.py:641-678`) falls back to the schema catalog when a source output name is absent from the working node's `outputs` array, returning a catalog `slot_index` with NO bounds check. `_apply_upsert_link` (`vibecomfy/porting/edit/apply_mutate.py:203`) writes `origin_slot=source.slot_index or 0` unchecked. `_ensure_output_link_reference` silently no-ops when out of range (`apply_links.py:314-334`). Projection then resolves ports by index → `_native_port_name` raises "Missing stable link from port" (`vibecomfy/comfy_nodes/agent/projection_registry_v1.py:115-120, 123-149`).
2. **Target-side fabrication**: `_ensure_input_slot` appends `{"name", "type": "*", "link": None}` for ANY unknown name (`apply_links.py:289-300`); `resolve_target_endpoint` accepts schema-only inputs absent from the node (`resolution.py:744-773`) → `slot_index=None` → fabricate. `resolve_output_slot_index` duplicates the schema fallback (`resolution.py:493-525`).
3. **Silent drops**: `_set_input_link_reference` silently returns (`apply_links.py:307`); `_ensure_output_link_reference` silently no-ops (`:324`) — dangling links, no diagnostic.

## Tasks (from .oracle/tasklist.md B08-cut)

1. **Regressions for**: catalog output name absent from working outputs; schema-derived source index out of bounds; add-node link resolution; unknown target input; valid named multi-input/output links; the late "Missing stable link from port" signature.
2. **Working-graph ports authoritative during endpoint resolution.** Schema may validate or enrich but cannot return a slot absent from the node.
3. **One shared pre-mutation endpoint invariant** for upsert-link and add-node links.
4. **Bounds-check source slots before `_apply_upsert_link`.**
5. **Remove synthetic input fabrication for unknown target names** — legitimate dynamic inputs require an explicit node/schema contract.
6. **The ONE shared concrete dynamic-port contract** (tasklist): count-driven families (`ImageConcatMulti` `image_N`, `LTXVImgToVideoInplaceKJ` `num_images.*`, `SimpleCalculator` `input_N`, `LTXVAddGuide` `guide_N`, `SimpleCalculatorKJ` payload vars, `in_N` fixed slots); helpers/proxies (`Reroute`, `GetNode`, `SetNode`, `PrimitiveNode`); dynamic `INPUT_TYPES` custom nodes — ONE predicate used by resolution, mutation, and projection. A port is valid iff present in `node["outputs"]`/`["inputs"]` OR the class matches the dynamic contract AND the schema-fallback slot is bounds-verified before link write.
7. **Materialize-then-validate**: build schema input sockets into `inputs` at `vibecomfy/porting/emit/ui.py:1325` symmetric with outputs; keep write-time bounds checks but emit typed diagnostics instead of silent returns at `apply_links.py:303/314`.
8. **Resolve projection ports by canonical name with a validated index fallback.**
9. **Typed pre-apply diagnostics** instead of malformed links failing during projection.

## Sense-check precommit (adversary predictions — cover these FIRST)

From `.oracle/sensecheck-remaining-2026-08-13.md`:
1. **Schema still authorizes a ghost output**: `resolution.py:641` fallback can return an index absent from working outputs → mutation writes it (`apply_mutate.py:197`) → projection fails (`projection_registry_v1.py:115`).
2. **Dynamic contract becomes carte blanche**: require POSITIVE + ONE-PAST-BOUNDARY fixtures for every named family; "has dynamic INPUT_TYPES" alone cannot authorize arbitrary names; Get/Set/Reroute need their actual directional semantics (B03 already resolves these in the pin path — reuse that understanding).
3. **Materialization shifts physical slots**: new-node inputs are empty at `ui.py:1325`; materialize socket inputs in SCHEMA ORDER excluding literal widgets, otherwise KSampler-like nodes acquire wrong indices; replace silent returns at `apply_links.py:303` with propagated typed diagnostics.

## Key files
- `vibecomfy/porting/resolution.py` (`:493-525, :641-678, :744-773`), `vibecomfy/porting/edit/apply_mutate.py` (`:157, :197-203, :224, :276`), `vibecomfy/porting/edit/apply_links.py` (`:289-334`), `vibecomfy/porting/edit/apply_resolve_add.py` (`:39-313, :467-500`), `apply_resolve_base.py`, `vibecomfy/porting/edit/lint.py` (`:84-111, :405-415`), `vibecomfy/porting/emit/ui.py` (`:1073-1083, :1282-1342, :1325`), `vibecomfy/comfy_nodes/agent/projection_registry_v1.py` (`:115-149`), `vibecomfy/porting/validate.py` (`:444-471` dynamic contract precedent)
- tests: `tests/test_porting_edit_apply_values.py`, `tests/test_porting_edit_apply.py`, `tests/test_comfy_nodes_agent_edit.py`, `tests/test_m1_contracts.py`

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py tests/test_comfy_nodes_agent_edit.py tests/test_m1_contracts.py -k 'endpoint or port or link or slot or dynamic or materialize or bounds or ghost or add_node or upsert'
```
Plus the full targeted files (expected exit 0; rerunfailures plugin binds a socket and cannot run here).

## Acceptance (from tasklist)
- Malformed endpoints fail before mutation and roll back cleanly.
- No undeclared synthetic ports are created.
- Valid named links project correctly despite serialized ordering differences.
- Resolver, mutation, and projection share ONE endpoint invariant.
- C8/C9 mechanism regressions and relevant porting/edit suites pass.
- No scenario recovery count is claimed without restored run artifacts.

## Report
Return: the shared invariant + dynamic-contract predicate location, per-site changes (file:line), materialize-then-validate implementation, typed-diagnostic path, fixture names, pytest output. Do NOT commit.
