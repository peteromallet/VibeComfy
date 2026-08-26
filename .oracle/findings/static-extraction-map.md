# Scout findings — static extraction map (StaticExtractScout, 2026-08-26)

SIX install-free extraction mechanisms exist:

1. **AST literal-return parser on cloned packs** — `schema/extract.py:extract_by_ast` / `SafeEval` / `static_env` / `input_types_return` / `normalize_entry`; Rung-2 stubbed-subprocess extractor `extract_by_import` (`_IMPORT_EXTRACTOR` with AutoStubFinder+CatchAllStubFinder); `extract_pack_schemas` runs the ladder. Runtime INPUT_TYPES() executes pack code but never boots ComfyUI.
2. **AST parser on installed source trees** — `schema/provider.py:SourceSchemaProvider` (`_schema_from_python_source`, `_class_literal_values`, `_input_types_return`, `_literal_eval_node`), confidence 0.9, `dynamic_input_types_miss` at 0.0.
3. **On-demand clone-then-parse provider** — `schema/on_demand.py:OnDemandInstallSchemaProvider`: registry-led pack resolution (`_resolve_pack` via registry.pack_resolver), bounded sandbox shallow-clone (`_ensure_clone`, LRU max_packs/max_bytes), Rung 1 static (0.9, on_demand_static), Rung 2 sub-gated `extract_by_import` (1.0, on_demand_runtime, VIBECOMFY_ON_DEMAND_BOOT=1). Opt-in via VIBECOMFY_ON_DEMAND_SCHEMAS (default ON in AuthoringSchemaProvider).
4. **Committed JSON snapshot readers** — `ObjectInfoSchemaProvider`, `ObjectInfoIndexSchemaProvider` (filters @stub.json at provider.py:440-442), `porting/object_info/consume.py`, `node_index.json` via `LocalSchemaProvider` (confidence 1.0).
5. **Hardcoded literal tables** — `_compile/_widgets.py:WIDGET_SCHEMA` + `WIDGET_SEMANTIC_NAMES`, fallback confidence 0.3.
6. **Workflow-JSON-derived stubs** — `scripts/generate_hotshot_stub_schema.py` → `@stub.json` (source_kind=workflow_json_stub).

Trust tiers: stubs actively rejected everywhere (`is_workflow_stub_schema`, index filter, compact_resolver:470-482); confidence 1.0 (node_index) → 0.9 (AST/on-demand static) → 0.8 (object_info cache, demoted 0.4/0.5 stale/missing-fp) → 0.6 (live runtime, opt-in) → 0.3 (widget fallback).

Cache ETL: `serialize.py:build_cache` + `CacheIdentity` writes PackName@<provenance>.json + index.json; `tools/clone_and_extract_packs.py` and `tools/build_node_corpus.py` use `extract_pack_schemas()` and persist full capture-grade files.
