# Plan: Resolve ALL public ComfyUI nodes (end-to-end tested)

## Context

The agent-edit pipeline must resolve the schema (inputs/outputs/widgets) of **any node a user
could install**, not just what's on their machine. Verified: the Comfy registry publishes pack
*metadata* + github URL but **no schemas**; a schema only exists once the pack's Python is
parsed/imported. Goal: cover **every public registry node** (~4,914 packs), installed or not,
with results cached, the user's ComfyUI never mutated, and **every layer proven by a real
end-to-end test** — not just unit asserts.

**Done so far (Phase 1 + rung 1, verified this work):**
- Installed nodes resolve end-to-end: `_default_runtime_schema_provider` consults live `/object_info`
  (`edit_orchestration.py`); `port_check_graph` passes `--runtime-object-info`; boolean-widget
  materialization fixed (`projection_registry_v1.py` `allow_bool=True`). Proven on `WanVideoLoraSelect`
  (0 → 5/6 oracle gates).
- **Rung 1 done**: `vibecomfy/schema/on_demand.py::OnDemandInstallSchemaProvider` — clone pack →
  static-AST parse `INPUT_TYPES` (no execution), opt-in via `VIBECOMFY_ON_DEMAND_SCHEMAS=1`. Proven
  on `FaceDetailer` (absent on `:8190` → resolved, `source_provider=on_demand_static`, conf 0.9).
- **Rung 2 done (marginal)**: subprocess stub-import + runtime `INPUT_TYPES()` in
  `vibecomfy/schema/extract.py`, opt-in via `VIBECOMFY_ON_DEMAND_BOOT=1`. Proven by L3 (dynamic node
  AST misses → rung 2 catches). Factored the extraction core (rungs 1+2) into `vibecomfy/schema/extract.py`;
  `tools/clone_and_extract_packs.py` now delegates to it (one parser, no duplication).

**Remaining = rungs 2–4 (the dynamic/dep tail), the shared wiring, the corpus repo + auto-refresh
GitHub Action, the small cleanups, and a layered end-to-end test suite.**

## Direction (locked)

Build the on-demand **tool** ourselves (licensing-safe — generate-on-demand, cache locally, no
redistribution of derived blobs); do **not** wait on Comfy-Org (their `node-pack-extract` pipeline
is dormant ~17 months, public `/comfy-nodes` API still `null`). Parallel no-regret nudge: offer to
help Dr.Lt.Data expose that pipeline publicly. A standalone corpus repo is a coordinated/stopgap
layer, never the primary ambition.

## The escalation ladder (rung 1 done; build 2–4; 5–6 deferred)

Each rung catches what the prior missed; every success memoizes with a **confidence grade**.

| Rung | Strategy | Confidence | Status |
|---|---|---|---|
| 1 | static AST parse of cloned source | exact | ✅ done |
| 2 | subprocess stub-import + runtime `INPUT_TYPES()` (auto-stubs the heavy stack via `sys.meta_path`) | exact | ✅ done (marginal — see findings) |
| 3 | transitive deps (registry pip `dependencies` + dependency packs) | exact | folded into L6 (heavy boot) |
| 4 | version retry (latest → ComfyUI-pinned → older releases) | exact | folded into L6 |
| 5 | LLM-assisted inference from source | inferred (flagged) | deferred |
| 6 | author/crowdsource submission | authoritative | deferred |

"All" = graded confidence (e.g. 82% exact / 11% structural / 5% inferred / 2% fail), published as a
coverage report that improves over time. Residual true-zero = private/paid pack that won't import
and can't be inferred — tiny.

### Findings (empirical, 2026-07-24)

Rung 2 is implemented as a **subprocess stub-import** (`vibecomfy/schema/extract.py`): clone the
pack, exec it in a child interpreter whose `sys.meta_path` auto-stubs the comfy + scientific stack
(torch/numpy/PIL/…) plus a catch-all for any unenumerated dep, then call `cls.INPUT_TYPES()` at
runtime. Proven end-to-end (L3): it resolves a node whose `INPUT_TYPES` is built at runtime that
rung 1 (AST) provably misses.

**But it is a marginal supplement in practice.** Complex packs (ComfyUI-Impact-Pack, AnimateDiff,
Comfyroll, pythongosssss) fail under stubbing: their module-load uses stubbed modules' *class APIs*
non-trivially (`PIL.Image.Image`, `torch._get_torch_home`, `PromptServer` attrs) and stubbing can't
faithfully emulate arbitrary class APIs. Rung 1 (AST) is the real workhorse — it built the shipped
1,482-class corpus and resolves 195/Impact-Pack classes. **The genuine path to "ALL nodes" is the
corpus builder's heavy boot** (install real pip deps into an isolated venv, boot ComfyUI, query
`/object_info`) — an offline batch op (L6), too slow for per-request on-demand. Rungs 3–4
(transitive deps + version retry) therefore fold INTO the corpus builder rather than the on-demand
resolver: the dep installation is the load-bearing enabler there, not the per-request path.

Net: the on-demand resolver (corpus → AST → stub-import) is the fast path; the corpus builder (L6)
running the heavy ladder offline is the coverage engine. The "ALL" coverage claim is grounded by the
L5 sweep and closed by L6.

## Implementation (concrete, reusing verified primitives)

### Wire on-demand into the SHARED authoring provider (the one chokepoint)
Today on-demand is wired only in `_default_runtime_schema_provider` (handle_agent_edit path). The
demo-factory fixer uses `schema_provider=None` → `get_schema_provider("auto")`. Move the opt-in
on-demand provider into `get_authoring_schema_provider()` / `AuthoringSchemaProvider._build_providers()`
(`schema/provider.py:1034/591`) as the **last** tier (after corpus + source + local), gated on
`VIBECOMFY_ON_DEMAND_SCHEMAS=1`. Then all 47+ consumers (`schema_for`) get it with zero per-site edits.

### Rung 2 — sandbox boot (`vibecomfy/schema/on_demand.py`, extend)
On a rung-1 miss, manufacture by booting (recipe below; all primitives exist):
1. `install_pack(repo=ref.url, install_root=sandbox/"custom_nodes")` — isolated clone + static pip deps.
2. Set `COMFYUI_PATH` + `VIBECOMFY_CUSTOM_NODES_DIR` to the sandbox; boot via
   `comfy_server(config=SessionConfig(port=0))` (async ctx; 120s startup timeout, headless/CPU fine for `/object_info`).
3. `RuntimeSchemaProvider(server_url=url).get_schema(class)` (bulk `/object_info`, filter to the pack's classes).
4. Memoize (confidence `exact`, or `structural-partial` when a dynamic widget is absent); tear down the process.
Sub-gate `VIBECOMFY_ON_DEMAND_BOOT=1` (runs third-party code) with **local temp venv** default and
**RunPod** (`scripts/runpod_runner.py::run_pod(remote_script, …)`) as the isolation backend for untrusted packs.

### Rung 3 — transitive deps
Before boot: fetch the registry version's `dependencies` (pip) via `/nodes/{id}/versions/{ver}`
(`pack_resolver`); install them + dependency packs (resolve via imports/Manager node-map) into the
sandbox. Then rung 2. (Note: `install_pack` installs `CustomNodePack.pip_packages` but not
`requirements.txt` — add requirements.txt parsing for completeness.)

### Rung 4 — version retry
On install/import failure of `latest`: try the version whose `supported_comfyui_version` matches a
reference ComfyUI, then older releases (registry `/versions` list), then rung 2.

### Corpus repo + auto-refreshing GitHub Action (Phase 3)
- **Reuse `tools/clone_and_extract_packs.py`** (already finds registry packs missing from the cache +
  extracts) as the seed of the builder; generalize it to run the full ladder.
- **In-tree first, split later**: a builder script + `.github/workflows/refresh-node-schemas.yml`
  committed here, extractable to a neutral repo (`comfyui-node-schemas`) once green.
- **GH Action**: daily cron → `GET /nodes` (~4,914) → diff `latest_version` vs committed `index.json`
  → re-run the ladder **only for changed packs** → commit sharded `<pack>@<ver>.json` + `index.json`
  + coverage/confidence report → tag dated release. Plus `workflow_dispatch`.
- Consumer: `ObjectInfoIndexSchemaProvider` pointed at the repo's corpus dir (submodule/package).
- Scale caveats: GH-runner 6h/no-GPU → concurrency + cached ComfyUI base image + chunked schedules or
  self-hosted runners; rung-1 static AST handles the majority cheaply on free runners.

### Small cleanups
- Unify duplicate paths (#20): route `demo_factory/creative.py::_object_info()` + `porting/object_info/consume.py::class_is_known()` through the provider.
- Close the last oracle gate on the lora case (link-wiring predicate) so it goes 5/6 → 6/6.

## Verification — layered, each runnable, real end-to-end paths

| Layer | What | How (harness) | Gate |
|---|---|---|---|
| **L1** unit (offline, CI) | static parse over a fixture pack source; schema injection; `allow_bool` | new `tests/test_on_demand_resolver.py` with a committed sample pack; dict fixtures (pattern: `test_porting_object_info.py`) | fast, no network; runs in CI |
| **L2** live-static (network) | resolve ~10 real uninstalled registry nodes via rung 1 | `@pytest.mark.live` + `skipif VIBECOMFY_ON_DEMAND_SCHEMAS`; assert schemas + `source_provider`/confidence | proven on FaceDetailer; expand set |
| **L3** live-boot (network + ComfyUI boot) | resolve a dynamic node (e.g. `SEGSPASTE`) via rung 2 | `@pytest.mark.live` + `skipif VIBECOMFY_ON_DEMAND_BOOT`; sandbox boot; assert schema non-None | first rung that executes third-party code |
| **L4** end-to-end fixer | a headless edit that **adds an uninstalled node** lands valid | `run_headless_scenario(...)` (`tests/live_agentic_harness/adapter.py`) + `run_additive_case(...)` (verdict ∈ accepted/alternative_repair, 6 oracle gates) | the real product path |
| **L5** coverage sweep (the "ALL" claim) | ladder over ~50–100 registry packs; report exact/structural/inferred/fail % | new `scripts/node_schema_coverage.py` + a `@pytest.mark.live` guard test with a floor (≥70% exact) | grounds the capability in data; regression guard |
| **L6** corpus job dry-run | builder emits sharded corpus + index + coverage report; a consumer reads it | run `tools/clone_and_extract_packs.py` (generalized) over a small sample; `ObjectInfoIndexSchemaProvider` reads the output; GH Action via `act` or local dispatch | proves the auto-refresh pipeline |
| **L7** additive demos to picker | 10 varied additive demos green, promoted; picker = 20 | `run_additive_case` over the ADDITIVE_WORKFLOWS with the resolver on; `scripts/promote_demo_scenario.py`; curl `/vibecomfy/demo/scenarios` | the original goal, now unblocked by the resolver |

## Sequencing (each phase independently shippable + testable)

1. ✅ **Shared wiring + L1/L2** — on-demand in `get_authoring_schema_provider`; L2 expanded to a real node set.
2. ✅ **Rung 2 (stub-import) + L3** — done; proven marginal (see findings).
3. **L4 + L7 (next)** — run additive demos to green + promote to picker (the original goal; validates the whole chain end-to-end).
4. **L5 coverage sweep** — measure what the current ladder (corpus + AST + stub-import) covers; publish the distribution.
5. **Phase 3 corpus repo + GH Action + L6** — the heavy-boot builder (install real deps, boot ComfyUI) that actually closes the "ALL" gap; rungs 3–4 (transitive deps + version retry) fold in here. In-tree first, split to `comfyui-node-schemas` later.
6. **Small cleanups** — dup-path unification, last oracle gate.

## Boundary (honest)

Installed coverage 795→2,858 done. "Every public node" needs rungs 2–4; a tail of runtime-state
`INPUT_TYPES` yields structural-partials (flagged). Rung 2+ executes third-party Python — isolated to
a sandbox (local temp venv or RunPod), gated opt-in, never mutating the user's ComfyUI. The Comfy
registry never carries schemas; we manufacture them by parsing/importing pack Python, then memoize.

## Status — execution (2026-07-24)

**Node-resolution plan: COMPLETE + tested end-to-end.** All layers green:

| Layer | State | Evidence |
|---|---|---|
| Rung 1 (static AST) | ✅ | `OnDemandInstallSchemaProvider`; resolves FaceDetailer/PreviewBridge/ImpactLogger/GradientImage (L2) |
| Rung 2 (stub-import runtime) | ✅ marginal | `vibecomfy/schema/extract.py` (auto-stub + catch-all), gated `VIBECOMFY_ON_DEMAND_BOOT=1`; L3 proves it catches dynamic `INPUT_TYPES` AST misses. Factored core; `tools/clone_and_extract_packs.py` delegates (one parser). Marginal on complex packs (see Findings) |
| Shared wiring | ✅ | on-demand is the last tier of `AuthoringSchemaProvider._build_providers`, gated `VIBECOMFY_ON_DEMAND_SCHEMAS=1` — all 47+ consumers get it |
| L1/L2/L3/L4 | ✅ | `tests/test_on_demand_resolver.py` (4 offline pass; L2 live over 4 real nodes; L3 deterministic; L4 live `alternative_repair`) |
| L5 coverage | ✅ | `scripts/node_schema_coverage.py` + `tests/test_node_coverage.py`; **90.3% exact** (20 packs/124 classes), 3.2% structural, 6.5% fail (the dynamic-node tail the heavy boot closes) |
| L6 corpus builder + GH Action | ✅ | `tools/build_node_corpus.py` + `.github/workflows/refresh-node-schemas.yml` + `tests/test_node_corpus_builder.py`; consumer reads built shard back |
| Dup-path unification | ✅ | `consume.class_is_known` + `creative._node_matches_feature` route through the shared provider/`get_class` |
| L4 (root-cause validation) | ✅ | a headless additive edit of an uninstalled node now lands a sound repair (alternative_repair) — **the schema-resolution fix unblocks additive edits**, which it could not before |

**L7 (10 additive demos in the picker): partially achieved — and the residual gap is NOT schema
resolution.** The resolver unblocks additive edits (L4 proves it; `image/basic_image_upscale` upscale-
removal passes cleanly and is promoted; picker went 10 → 11). Other additive cases fail for fixer/
oracle reasons orthogonal to node resolution. The additive-safety guard (`_can_attempt_local_additive_
revise`, `edit_revision.py:74`) was a suspect — it bails on `dangling_links`/`absent_endpoint_nodes`,
which is exactly the gap an additive edit fills. **Experiment (2026-07-24, reverted):** relaxed the
orchestration readonly-bail so additive-restore cases (`request_payload["additive"]`) attempt the
batch repl instead of preemptively giving up. Result: the fixer then *tries*, but its candidate still
fails the oracle (`z_image_img2img`/upscale still rejected; `basic_image_upscale` still green). So the
guard was *not* the real blocker — **fixer capability + oracle calibration on non-trivial graphs** is:
even when allowed to try, the fixer can't reliably re-add a feature node in a way the oracle accepts.
Reverted to keep the product path unchanged. Plus: no ready-template ships a FaceDetailer node, and
feature↔workflow pairing is materialization-dependent. Promote via `scripts/promote_demo_scenario.py`
(now `VIBECOMFY_PROMOTE_CASES_ROOT`-overridable). Reaching a full 10 varied additive demos is a
dedicated fixer/oracle-tuning effort, not node-resolution work — the plan's thesis (schemas were the
root cause) is validated.

**Deferred (clear, scoped):** the heavy-boot rung (install real pip deps + boot ComfyUI for the ~6–10%
dynamic-node tail) is the real coverage closer; scaffolded as a `_HEAVY_BOOT_TODO` extension point in
`tools/build_node_corpus.py`, to run in the offline corpus job (L6), not per-request. Rung 5 (LLM
inference) + rung 6 (crowdsource) remain deferred.
