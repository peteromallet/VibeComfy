**PASS**

Checkpoint D holds at `86e4a6ba`. Delta is three files (`tests/live_agentic_harness/scenario_obligations.py`, `tests/test_scenario_obligation_preflight.py`, `tests/test_p4_objectinfo_caches.py`). Old allowlist string gone (`rg` exit 1); `DECLARED_SCHEMA_SOURCES` is explicit. Commit message matches.

Tests (verbatim):

```
pytest tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py -q
53 passed, 1 warning in 1.80s

pytest tests/test_ensure_capture.py -q
9 passed, 1 warning in 0.58s
```

`test_schemas_ensure.py`: two quarantined pre-existing failures, not D; it still rewrites committed `index.json` (restored).

ox-alpha dispatch failed: OpenRouter `404 No endpoints found for ox-alpha` (catalog has no stealth/ox models). Same briefs were executed locally.

Masquerade/mixed-pack probes: on-demand cannot satisfy `authoritative_object_info`; `on_demand_import` cannot satisfy `on_demand_static`; `@on_demand_` filename blocked even when JSON lies `runtime_*`; stubs fail; missing pin fails; ledger/file `source_kind` disagreement fails; `on_demand_runtime` invalid; `runtime_only` names t**PASS**

Checkpoint D holds at `86e4a6ba`. Delta is three files (`tests/live_agentic_harness/scenario_obligations.py`, `tests/test_scenario_obligation_preflight.py`, `tests/test_p4_objectinfo_caches.py`). Old allowlist string gone (`rg` exit 1); `DECLARED_SCHEMA_SOURCES` is explicit. Commit message matches.

Tests (verbatim):

```
pytest tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py -q
53 passed, 1 warning in 1.80s

pytest tests/test_ensure_capture.py -q
9 passed, 1 warning in 0.58s
```

`test_schemas_ensure.py`: two quarantined pre-existing failures, not D; it still rewrites committed `index.json` (restored).

ox-alpha dispatch failed: OpenRouter `404 No endpoints found for ox-alpha` (catalog has no stealth/ox models). Same briefs were executed locally.

Masquerade/mixed-pack probes: on-demand cannot satisfy `authoritative_object_info`; `on_demand_import` cannot satisfy `on_demand_static`; `@on_demand_` filename blocked even when JSON lies `runtime_*`; stubs fail; missing pin fails; ledger/file `source_kind` disagreement fails; `on_demand_runtime` invalid; `runtime_only` names the strict flag and does not claim `schemas ensure`. Mixed cache: G does not ride R. `resolution` stays bools; `resolution_tiers` records the cache stamp (FINAL5 `source_kind=""`). No `OnDemandInstallSchemaProvider`. Campaign rows untouched.

Executor quirk (`.oracle/receipts/batch-D-execution.log`): Grok progress was concatenated without newlines into one paragraph.

**North Star:** aligned. No tier masquerade, no silent rung upgrade, no stub-as-truth, no permanent install, no parallel extract, no ceremonial tests.

Residual (not a D blocker): unstamped non-`@on_demand_` files, including constructed `Pack@weird.json`, satisfy `authoritative_object_info` via the FINAL5 `@local.json` legacy-ingest clause. Payload does not relabel them `runtime_*`. Tighten later to `@local.json` | `@runpod-snapshot` | `runtime_core`.

KISS: six helpers composing existing index/provenance/stub filters. Glue is thin enough.
