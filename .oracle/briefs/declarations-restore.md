# EXECUTOR BRIEF — Restore on_demand declarations for the 6 capture-blocked scenarios (OQ2 authorization)

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

## CONTEXT (operator-authorized; plan OQ2: "If the oracle wants a real previously-blocked scenario green, authorize adding declarations (not rubrics)")
On the agentbox (container 8ae259ba345f, ssh root@159.69.51.216), `schemas ensure --manifest final50` has now captured ALL 18 gated classes with honest on_demand tiers (files `vibecomfy/porting/cache/object_info/*on_demand_*.json` + provenance ledger: ComfyUI-Easy-Use@on_demand_import, ComfyUI-Inspire-Pack@on_demand_import, audio-separation-nodes-comfyui@on_demand_import, ComfyUI-DeepExtract@on_demand_import, comfyui_ryanonyheinside@on_demand_import, ComfyUI-llama-cpp@on_demand_import, ComfyUI-Advanced-ControlNet@on_demand_static, ComfyUI-VibeVoice@on_demand_static, ComfyUI-SubjectStyle-CSV@on_demand_static, comfyui-advanced-controlnet@on_demand_static).

The preflight still fails because `tests/live_agentic_harness/scenario_obligations.py`:
- `SCHEMA_EVIDENCE_REQUIREMENTS` has NO declarations for the 6 scenarios (they were deliberately removed by RR1-FIX-REV when their old captures proved to be offline stubs), and
- `UNPROVEN_PROVIDER_CLASSES` lists their gated classes as typed violations.

Plan OQ2 now authorizes restoring declarations backed by the NEW on_demand captures (declarations only — NOT assessment rubrics).

## TASK (work on the AGENTBOX, inside /workspace/vibecomfy-exec-spine-20260820/exec-spine, branch oracle-run — pull first; commit there; do NOT push)
For each of the 6 previously-blocked scenarios:
  audio-acestep-audio-generation-and-processing-workfl-1b1360
  audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676
  audio-audio-processing-with-voice-tts-and-noise-remo-b80848
  image-generates-a-2x2-seed-variation
  image-llama-cpp-instruct-image-preview-and-save-5b54bf
  image-sd3-image-generation-with-controlnet-19d221
1. Read the captured on_demand cache entry for each of its gated classes (the real schema is IN the cache file — inputs/widgets/outputs are the truth).
2. Add a declaration row to SCHEMA_EVIDENCE_REQUIREMENTS: class_type, pack (the captured pack), `source` = the file's actual source_kind (on_demand_static or on_demand_import), and required_inputs/required_widgets/required_outputs taken FROM the captured schema (real names only — no invented ports). Where the old commented-out rows had port expectations, verify they match the capture; if the capture differs, the CAPTURE wins (record the diff in the commit message).
3. Remove those classes from UNPROVEN_PROVIDER_CLASSES (entries that become empty tuples are removed).
4. Sanity: declarations of source on_demand_static must point at capture files with source_kind on_demand_static (exact match, no upgrades) — the preflight enforces this.
5. Run on the box: `python3 -m tests.live_agentic_harness.compare_pipeline_modes --validate-only --manifest tests/live_agentic_harness/threaded_comparison_manifest_final50.json` → must print `"ok": true`. Include verbatim.
6. Run focused: pytest tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py tests/test_batch_e_e2e.py -q → green (some tests may assert the old UNPROVEN violations for these scenarios — update those tests to the new honest declarations; do not delete coverage).
7. Commit on oracle-run: "schemas-ensure: restore on_demand declarations for 6 previously-blocked scenarios (OQ2, operator-authorized)". Do NOT push.

## RULES
- Declarations only; NO rubric/scoring edits; NO docs/plans/**; no fabricated ports; @stub.json stays rejected; runtime_only strict flag must still reject on_demand (test it).
- Report: files changed, the declaration rows added (verbatim), preflight output verbatim, test results verbatim.
