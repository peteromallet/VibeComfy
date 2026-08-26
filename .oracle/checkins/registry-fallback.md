I'll act as manager, not worker: load the brief and launch ox-alpha to verify the registry-miss fallback against the north star.I'll write a self-contained ox-alpha brief covering the three probes, then launch it against this repo.The ox-alpha model id 404'd; I'll resolve the correct stealth/ox-alpha selector from omp and relaunch.The stealth provider sent `ox-alpha` to OpenRouter and 404'd. Relaunching with `openrouter/stealth/ox-alpha`, the selector that actually reaches ox-alpha.OpenRouter retired ox-alpha (it was GLM-5.3 Flash). Launching the successor for the same probes.Verifier reported PASS but also “2 failed” with exit 0 — I’ll confirm the focused pytest result before the verdict.**PASS**

North Star: **aligned**. Registry-miss falls back to a static URL, ephemeral clone, extraction ladder, and honest `on_demand_*` persist with `source: direct_url` and `registry_pack_version: null`. No serve/GPU/permanent install; no silent tier upgrade.

Verifier: ox-alpha is retired (OpenRouter: it was GLM-5.3 Flash). Probes ran on `openrouter/z-ai/glm-5.3-flash`.

**Delta** `9af848dc..7a362ec2` (excl `.oracle`): `vibecomfy/registry/pack_resolver.py`, `vibecomfy/commands/schemas.py`, `vibecomfy/schema/ensure_capture.py`, `schema/extract.py`, `porting/object_info/{core_regen,pinned_venv}.py`, `tests/test_schemas_ensure.py`, `tests/test_extract_embedded.py`.

**Probe 1** (verbatim): `pytest tests/test_schemas_ensure.py tests/test_ensure_capture.py -q` → exit 0, `2 failed, 53 passed`. Both failures are quarantined baselines (`node_resolution_surface.txt`); plugin: “No regressions.” Registry mocked; clones are local git fixtures.

**Probe 2:** fallback persist is `source_kind=on_demand_static`, `extraction_rung=ast`, `source=direct_url`, `registry_pack_version=null`. Forcing `runtime_object_info` / `executed_object_info` / `on_demand_runtime` → `ValueError: unknown extraction rung` (`ensure_capture.py` closed `SOURCE_KIND_BY_RUNG`). Non-blocking: unsanitized `source` string can be forged as prose; `source_kind`/tier stay static.

**Probe 3:** registry hit with a poisoned `PACK_URL_FALLBACKS` decoy → cloned only the registry URL; provenance `registry_pack_version="9.9.9"`, no `direct_url`. Fallback is LookupError-only.

**Box:** no `schemas ensure` output in tree for this commit; live box run not repeated.

KISS/YAGNI: glue on existing resolver/clone/ladder; no parallel schema system.
