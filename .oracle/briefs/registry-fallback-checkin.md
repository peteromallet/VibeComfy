# ORACLE BATCH CHECK-IN — registry-miss fallback (direct pack URL resolution)

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

## REVIEW TARGET
Repo: vibecomfy-oracle (HEAD 7a362ec2). Delta: `git diff 9af848dc..7a362ec2` (exclude .oracle/**). Acceptance: the brief at .oracle/briefs/registry-fallback.md (registry-miss fallback → direct URL → ephemeral clone → ladder → on_demand_* persist with source:direct_url provenance; tier guard intact; no serve/GPU/permanent install; mocked-registry unit tests; box verification output included).

## DELEGATION MANDATE
Manager/validator of the normal pool, not a worker. Delegate verification to ox-alpha: `python3 /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model stealth/ox-alpha --query-file=<brief> --project-dir=/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`. Probes: (1) run focused tests verbatim; (2) construct a tier-masquerade attempt via the fallback path; (3) verify fallback URL mapping cannot shadow a registry-covered pack. KISS/YAGNI on critique.

## VERDICT
Binary: PASS or evidence-backed issues. North Star alignment disposition explicit. <300 words.
