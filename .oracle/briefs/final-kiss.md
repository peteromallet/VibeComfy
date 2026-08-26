# FINAL REVIEW — KISS/YAGNI critique of the A–E schema-capture contract

You are Spark, read-only. Repo
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle` HEAD `d2975269`.
Do NOT edit. Do NOT run pytest. Optimize for elegance (KISS/YAGNI).

North Star: compose, don't duplicate. New code is glue. Reuse
`registry/pack_resolver`, `schema/extract` ladder, `schema/on_demand` LRU clone,
`porting/object_info/serialize.build_cache`, provenance ledger in
`commands/schemas.py`. Frozen compose map is `.oracle/plan.md` lines 5–16.

## Diffs to read

```
git diff --stat 96a9d810..d2975269 -- . ':!.oracle/**' ':!docs/plans/**'
git diff 96a9d810..d2975269 -- vibecomfy/schema/ensure_capture.py vibecomfy/schema/on_demand.py vibecomfy/schema/extract.py vibecomfy/commands/schemas.py vibecomfy/commands/doctor.py tests/live_agentic_harness/scenario_obligations.py
```

Also skim tests only enough to see if they test glue or invent a second system:
`tests/test_ensure_capture.py`, `tests/test_schemas_ensure.py` (new Test* classes),
`tests/test_batch_e_e2e.py`.

Batch B (rung 3 embedded) is DEFERRED — `--no-embedded` is a documented no-op.
Do not demand B.

## Judge (do not rubber-stamp)

For each, PASS (thin glue) or FAIL (overbuilt / duplicate / YAGNI):

1. Is `ensure_capture.py` one persist/gap module, or a parallel schema system?
2. Does ensure still call `extract_pack_schemas` + `_ensure_clone` + `build_cache`
   + existing `_load_provenance`/`_write_provenance`? Name any second writer.
3. Did anyone persist via `tools/clone_and_extract_packs.write_cache`?
   `rg clone_and_extract_packs vibecomfy/` must be empty for commands/schemas.py.
4. Preflight: smallest allowlist + exact `source_kind` match, or a new schema
   provider / alias layer (`on_demand_runtime` still present?)?
5. Doctor/coverage: shared `format_schema_gap` vs copied strings everywhere.
6. Dead machinery for deferred B that actually runs (pip/venv/server) vs a
   fail-closed flag that cannot fire.
7. Count new public functions in the four production files. Too many?

Prior batch nits to re-evaluate at whole-contract scope (not automatically
blockers): unused `RUNTIME_SOURCE_KINDS`; `format_template_gap` duplication;
`retry_command` splitting `"; run "`; unstamped `@weird.json` legacy ingest
satisfying `authoritative_object_info`.

## Return (max 400 words)

- Glue vs parallel-system verdict (one sentence)
- Table: question 1–7 → PASS/FAIL → file:line
- Overengineering list (only if you would revert it)
- YAGNI to delete now vs later
- Overall: KISS-PASS (merge-ok) or KISS-FAIL (must slim before merge)
