# EXECUTOR BRIEF — Restore on_demand declarations for 5 new-50 scenarios (OQ2, operator-authorized)

## NORTH STAR
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

## CONTEXT
This runs ON THE AGENTBOX: ssh root@159.69.51.216, container 8ae259ba345f, worktree /workspace/vibecomfy-exec-spine-20260820/exec-spine (currently at 339c9e1e on oracle-run; local main has diverged — do NOT pull/merge, just work on the current checkout and commit on a new branch `declarations-new50`).

`schemas ensure` has captured ALL gated classes for the new-50 manifest (/tmp/manifest_new50.json, 50 video/multi scenarios): ACN_AdvancedControlNetApply + ACN_AdvancedControlNetApply_v2 → ComfyUI-Advanced-ControlNet@on_demand_static-a0563a3.json; easy forLoopStart/forLoopEnd → ComfyUI-Easy-Use@on_demand_import-4de1ab3.json.

`python3 -m tests.live_agentic_harness.compare_pipeline_modes --validate-only --manifest /tmp/manifest_new50.json` fails with "gated class 'X' has no exact schema provenance requirement" for 5 scenarios (no declaration rows exist):
- multi-animatediff-video-face-swapping-with-deflicker-506ebd: ACN_AdvancedControlNetApply
- video-animatediff-video-with-controlnet-and-depth-89b02a: ACN_AdvancedControlNetApply_v2
- video-animatediff-video-with-ipadapter-and-controlne-4eebf: ACN_AdvancedControlNetApply
- video-anime-video-to-video-with-controlnet-and-openp-cb5cd2: ACN_AdvancedControlNetApply
- multi-wan-vace-video-retargeting-driven: easy forLoopEnd, easy forLoopStart

## TASK
Same pattern as the earlier declarations-restore commit (339c9e1e — read it for the exact row shape):
1. For each of the 5 scenarios × gated classes: read the captured schema from the cache file (vibecomfy/porting/cache/object_info/ComfyUI-Advanced-ControlNet@on_demand_static-a0563a3.json / ComfyUI-Easy-Use@on_demand_import-4de1ab3.json) and add a declaration row to SCHEMA_EVIDENCE_REQUIREMENTS: class_type, pack, source = the file's actual source_kind (on_demand_static for ACN, on_demand_import for Easy-Use), required_inputs/required_widgets/required_outputs taken from the captured schema (real names only).
2. The classes are not in UNPROVEN_PROVIDER_CLASSES for these scenarios (they're new-50) — verify; if any are, remove.
3. Run: python3 -m tests.live_agentic_harness.compare_pipeline_modes --validate-only --manifest /tmp/manifest_new50.json → must print "ok": true. Verbatim in report.
4. Run focused: pytest tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py -q → green (update tests asserting the old state if any; preserve coverage; runtime_only strict must still reject on_demand).
5. Commit on new branch declarations-new50: "schemas-ensure: declarations for 5 new-50 scenarios (OQ2)". Do NOT push, do NOT merge, do NOT pull.

## RULES
- Declarations only; real ports from captures; no rubric edits; no docs/plans/**; @stub.json stays rejected; no fabricated provenance.
- Report: declaration rows verbatim, preflight output, test results.
