# EXECUTOR BRIEF — Registry-miss fallback: resolve packs by direct URL when api.comfy.org has no entry

## NORTH STAR (complete)
# North Star — VibeComfy schema truth without installation

## End state
A machine with no ComfyUI install and no GPU can, in one command, obtain trustworthy node schemas for any workflow's gated classes: registry resolves the pack, a bounded ephemeral clone supplies the source, the extraction ladder derives the schema, and the result persists into the committed capture cache with an honest provenance tier. The harness preflight accepts these tiers and runs.

## Enduring qualities
- **Ephemeral by construction** — nothing permanent is installed: temp clone in, schema truth out, clone evicted (LRU-bounded).
- **Honest provenance** — every cache entry records its true tier (`on_demand_static` vs `on_demand_runtime` vs runtime capture), registry pack version, resolved commit, extraction rung. Never masquerade a lower tier as a higher one.
- **Fail closed, degrade honestly** — missing data blocks the scenario with an actionable message ("run this exact command"), never silently guessed schemas.
- **Compose, don't duplicate** — reuse registry/pack_resolver, schema/extract ladder, object_info build_cache, provenance ledger. New code is glue.

## Anti-patterns
- Hand-authored or stub schemas presented as authoritative (the campaign's R3 incident).
- Permanent pack installs or venvs created as a side effect of capture.
- Preflight walls of unactionable failures.
- Parallel schema systems where the existing ladder suffices.
- Silent tier upgrades: a static parse must never be labeled a runtime capture.

## Aligned progress feels like
Each merged piece shortens the path from "scenario blocked: missing capture" to "scenario runs", with the trust tier visible at every step.

## CONTEXT (verified on the box)
`vibecomfy schemas ensure --manifest tests/live_agentic_harness/threaded_comparison_manifest_final50.json` (run on the agentbox at main 0831bcce) currently fails 4 gated classes at RESOLVE time:
  - `ImageBatchSplitter //Inspire`  → needs ComfyUI-Inspire-Pack (github.com/ltdrdata/ComfyUI-Inspire-Pack)
  - `VocalAndSoundRemoverNode`      → audio pack (github.com/christian-byrke/audio-separation-nodes-comfyui has AudioSeparation etc; VocalAndSoundRemover is from a separate pack — search custom_node_refs.py / hivemind corpus for the right repo)
  - `easy forLoopEnd` / `easy forLoopStart` / `easy int` → ComfyUI-Easy-Use (github.com/yolain/ComfyUI-Easy-Use)
  - `llama_cpp_instruct_adv` / `llama_cpp_model_loader` / `llama_cpp_parameters` → ComfyUI-llama-cpp (github.com/stavsap/ComfyUI-llama-cpp or equivalent — verify via custom_node_refs.py / hivemind)
Registry (api.comfy.org) has NO source URL for these packs. The extraction ladder (r1 AST / r2 stubbed import) is ready and generalized — the only gap is the RESOLVER.

## TASK
1. In the resolve path used by `schemas ensure` (Batch C glue in `vibecomfy/commands/schemas.py` → `registry/pack_resolver.py:resolve_pack`/`resolve_missing_nodes`), add a **registry-miss fallback**: when the registry returns no pack (or no source URL), fall back to a static pack-url mapping checked in order: (a) `vibecomfy/custom_node_refs.py` entries if they carry URLs, (b) a small hardcoded fallback map `PACK_URL_FALLBACKS` in the resolve module for the 4 known packs above (name → github URL). Verify each URL actually contains the gated class by cloning ephemerally (existing `_ensure_clone` LRU sandbox) — if the class is not in the cloned pack's mappings, report and continue to the next candidate.
2. Do NOT loosen provenance: the persisted tier stays `on_demand_static`/`on_demand_import` (rung 1/2), with `repo` = the actual clone remote, `locked_commit` = clone rev-parse HEAD, `registry_pack_version` = null/None (registry had no entry — record `registry_pack_version: null` + add `source: direct_url` field).
3. No ComfyUI serve, no GPU, no permanent install. Same ephemeral sandbox LRU.
4. Tests: unit test the fallback (mocked registry miss → cloned fixture pack → captured); no real network in tests.

## ACCEPTANCE
- `vibecomfy schemas ensure --manifest tests/live_agentic_harness/threaded_comparison_manifest_final50.json` on the box resolves ALL 4 previously-failing classes and persists them as on_demand_* with direct_url provenance (the 2 already-covered easy-loop classes skip via tier guard).
- Exit 0; "Still missing" list is empty (or names only genuinely-unresolvable classes with evidence).
- Focused tests green: pytest tests/test_schemas_ensure.py tests/test_ensure_capture.py -q.
- Commit: "schemas-ensure: registry-miss fallback — direct pack URL resolution for off-registry packs".

## RULES
- Compose-map mechanisms only (pack_resolver, _ensure_clone, extract_pack_schemas, build_cache, provenance ledger).
- No docs/plans/**, no rubrics, no ComfyUI serve, no GPU.
- Report: files changed, verbatim test results, box verification output.
