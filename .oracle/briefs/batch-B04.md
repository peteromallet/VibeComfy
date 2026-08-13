# MEGADO BATCH B04 — Real-schema authority (Flash executor)

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only.

## Context
G0-R1 already swapped `_frag_research.py:821` to real-first. Exploration found 7 total construction sites; 4 are provisional-first and must be fixed (the oracle-verified list):

1. `vibecomfy/comfy_nodes/agent/_frag_research.py:874` — `(provisional, state)` ✗
2. `vibecomfy/comfy_nodes/agent/_frag_response_contract.py:793` — `(provisional, session.schema_provider)` ✗ **poisons session AND state across turns**
3. `vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:910` — `(provisional, state)` ✗
4. `vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1115` — ✗ (remaining site)

Real-first invariant: `CompositeSchemaProvider.get_schema` is first-match-wins and `schemas()` merges `reversed(providers)` — the FIRST provider dominates both views, so real-first is required at every site.

## Tasks (from .oracle/tasklist.md B04)

1. Introduce ONE small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
2. Migrate all four provisional-first sites to real-first.
3. Assert precedence across ALL SEVEN construction sites for both `get_schema()` and merged `schemas()` (test).
4. Add a cross-turn regression for `_frag_response_contract.py:793` (currently poisons session + state — verify it no longer does).
5. Retain mechanism-level enum regressions for add and set (existing tests). Do NOT add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.

## Key files
- vibecomfy/comfy_nodes/agent/_frag_research.py, _frag_response_contract.py, _frag_batch_loop.py, edit_batch_repl.py, _frag_entrypoint.py (baseline), routes.py
- vibecomfy/comfy_nodes/agent/projection_registry_v1.py (get_schema/schemas semantics)
- tests: focused agent tests + test_executor_contracts.py

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_edit.py -k 'schema or precedence or provisional or real_schema or widget'
```
Plus run the full targeted files: `.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py` (expected exit 0; the rerunfailures plugin binds a socket and cannot run here).

## Acceptance
- All seven sites real-first.
- Session schema authority real-first across turns.
- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
- Invalid enum values rejected before mutation for add and set.
- Missing local asset filenames remain warning-only.

## Report
Return: helper name/location, per-site changes (file:line), the seven-site precedence test, cross-turn regression proof, enum regression results, pytest output. Do NOT commit.
