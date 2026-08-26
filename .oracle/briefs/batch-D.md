# EXECUTOR BRIEF — Batch D: preflight bridge [XHARD]

## NORTH STAR (complete — advance this, avoid these)
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

## DELEGATION MANDATE
You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: ox-alpha. Invocation: `python3 /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model stealth/ox-alpha --query-file=<brief> --project-dir=/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`. Dispatch research/implementation/critique briefs to ox-alpha; critique passes optimize for elegance (KISS/YAGNI). Work yourself only for the irreducible judgment kernel (the trust-boundary semantics below).

## TASK (from frozen plan — read .oracle/plan.md "Batch D" section IN FULL for the trust-boundary detail)
Work in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (HEAD 5f3e635f, Batches A+C landed). This is the R3 trust boundary — the highest-risk change in the run. Core semantics:
1. Expand the obligations declaration `source` allowlist to exactly: `authoritative_object_info` | `on_demand_static` | `on_demand_import` | `on_demand_embedded`. NO aliases (`on_demand_runtime` invalid — stamp migrated in Batch A).
2. The preflight must READ the cache entry's actual `source_kind` (from the pack JSON, not NodeSchema.source_provider which the index provider overwrites) and require it to match the DECLARED source exactly. A declaration of `authoritative_object_info` is NOT satisfied by `on_demand_*` (no masquerade). `on_demand_static` is NOT satisfied by `on_demand_import` (no upgrades). Still require provenance repo/locked_commit pin; provenance source_kind must match entry when present.
3. Payload: add a parallel `resolution_tiers` map (scenario_id → class_type → {source_kind, extraction_rung, locked_commit}); existing boolean payload untouched.
4. Stub rejection unchanged (@stub.json index filter) + explicit fail if a resolved file is stub-shaped.
5. Strict flag: `preflight_scenario_obligations(..., runtime_only: bool | None = None)` + env `VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1` — when set, only authoritative_object_info declarations + runtime-family cache kinds pass; on_demand is a violation naming the strict flag.
6. Fail-closed copy names `vibecomfy schemas ensure --manifest <that manifest>`.
7. Do NOT rewrite campaign SCHEMA_EVIDENCE_REQUIREMENTS rows or assessment rubrics. Preflight stays local-only (no network, no cloning).
8. Tests per plan Batch D list (tmp caches; on-demand declared+matched → ok with tier recorded; authoritative declaration vs on_demand file → fail; stub → fail; runtime_only rejects on_demand; existing FINAL5 IndexTTS/LayerMask runtime pins still pass; FINAL50 unproven still fail).
Note the plan's corrected line refs: _provenance_row at scenario_obligations.py:745; require_schema_resolution no-op at :949.

## ACCEPTANCE (Checkpoint D)
- Old allowlist string gone; explicit allowlist present.
- pytest tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py -q green; Batch A+C tests still green.
- Commit: "schemas-ensure(D): preflight accepts on_demand tiers as themselves; runtime_only strict flag".

## RULES
- Preflight local-only. No docs/plans/** edits, no rubric edits.
- Report: files changed, verbatim test results, deviations with reasons.
