**PASS**

Checkpoint C holds at `5f3e635f`. Delta is two files (`vibecomfy/commands/schemas.py`, `tests/test_schemas_ensure.py`). Glue: `--manifest` + xor template, gated discovery imports `_GATED_CLASS_RE` (not copied), resolve → `_ensure_clone` LRU (no `.tmp_packs` / `clone_and_extract_packs`), `extract_pack_schemas(allow_import=True)` with no `allow_embedded`, `persist_on_demand_pack` + `_enforce_cap()`, exit 1 on text and `--json`. Checkout CLI help lists `--manifest` / `--comfy-version` / `--no-embedded`. Commit message matches.

ox-alpha: required `_cmd_schemas_ensure` tests present (noop attested, mocked resolve+clone+real extract, r2 on under `VIBECOMFY_ON_DEMAND_BOOT=0`, stub is gap, json failure non-zero, no network). `62 passed`; two failures are pre-existing quarantined baselines, not C. Masquerade A–J blocked; AST probe wrote `on_demand_static`, not runtime. Mixed-pack untested at CLI but delegates to Batch A persist (safe).

**North Star:** aligned. No stub-as-truth, no permanent install, no parallel extract, no tier masquerade.

Nit (pre-existing, not C, confirmed as asked): `test_schemas_refresh_command_text_surfaces_non_authoritative_identity` patches only `schemas_command.CACHE_DIR`; ra**PASS**

Checkpoint C holds at `5f3e635f`. Two-file glue: `--manifest` xor template, gated discovery imports `_GATED_CLASS_RE` (not copied), resolve → LRU `_ensure_clone` (no `.tmp_packs` / `clone_and_extract_packs`), `extract_pack_schemas(allow_import=True)` with no `allow_embedded`, `persist_on_demand_pack` + `_enforce_cap()`, exit 1 on text and `--json`. Checkout CLI help lists `--manifest` / `--comfy-version` / `--no-embedded`. Commit message matches.

ox-alpha: required `_cmd_schemas_ensure` tests are present (noop attested, mocked resolve+clone+real extract, r2 on under `VIBECOMFY_ON_DEMAND_BOOT=0`, stub is a gap, JSON failure non-zero, no network). `62 passed`; two failures are pre-existing quarantined baselines, not C. Masquerade A–J blocked; an AST probe wrote `on_demand_static`, not runtime. Mixed-pack is untested at CLI but delegates to Batch A persist (safe).

**North Star:** aligned. No stub-as-truth, no permanent install, no parallel extract, no tier masquerade.

Nit (pre-existing, not C, confirmed as asked): `test_schemas_refresh_command_text_surfaces_non_authoritative_identity` patches only `schemas_command.CACHE_DIR`; a raw dump refresh hits `serialize.CACHE_DIR` and strips the trailing newline of committed `index.json`. C’s `TestSchemasEnsureCommand._redirect_cache` patches `consume.CACHE_DIR` / `INDEX_PATH` and is clean. Restore-before-commit was correct; fix the refresh test later — not a C blocker.

Stale global `vibecomfy` on PATH omits `--manifest`; the checkout entrypoint does not.
