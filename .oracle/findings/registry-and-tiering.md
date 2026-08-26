# Scout findings — registry/external sources + stub generators + trust tiering

## External metadata sources (RegistrySourceScout)
- `vibecomfy/registry/pack_resolver.py` — **Comfy Registry client that fetches node schemas via REST API** (note: "fetches node schemas" — verify exact payload during implementation; may be pack metadata + node lists).
- `schema/provider.py` — converts packed refs with `provisional_schema` into NodeSchema (ProvisionalRegistrySchemaProvider).
- `custom_node_refs.py` — ref data, no schemas.
- `executor/hivemind_clients.py` — workflow_semantics only, no input schemas.
- `registry/models_loader.py` — HF paths only.
- `executor/lookup_tools.py`, `agent_research_stage.py`, `comfy_nodes/agent/_frag_research.py`, `agent/artifacts.py` — research-phase registry lookups; `_frag_research` extracts workflow_schema for provisional schemas.
- **Gap:** the harness preflight (`tests/live_agentic_harness/` scenario obligations, at box HEAD 96a9d810) accepts only runtime object_info captures; on-demand tiers not wired.

## Stub generators + trust tiering (StubGenScout)
- Only ONE stub generator: `scripts/generate_hotshot_stub_schema.py` (derives from workflow JSONs). Other 5 bare @stub.json files (Florence2, Custom-Scripts, MelBandRoformer, controlnet_aux, GIMM-VFI) were manually committed, no generator.
- `extract_pack_schemas()` ladder (AST → stubbed-import) is the canonical install-free path; writes runpod-snapshot/local-* grade files, not stubs.
- Trust tiering: `is_workflow_stub_schema()` checks source_version=="stub" or @stub.json suffix; `ObjectInfoIndexSchemaProvider._load_index()` filters @stub.json entirely. Stubs structurally inert (rejected by index provider, add-node resolver, linter, signature emitter, widget resolver). `signatures.py` skips stubs, marks not_runtime_validated.
- Paradox: `_entry_has_authoritative_identity()` (consume.py) considers Hotshot stubs "authoritative" while `is_workflow_stub_schema()` rejects them — known inconsistency.
- Bare stubs consumed only by `generate_node_shims.py` for .pyi generation.
- **Verdict:** no UNUSED install-free solution — the ladder exists and is used by corpus tools; what's missing is (a) manifest-driven persist-to-cache wiring, (b) preflight acceptance of on_demand tiers.
