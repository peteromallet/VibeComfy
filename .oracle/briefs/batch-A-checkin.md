# ORACLE BATCH CHECK-IN — Batch A (persist glue + honest on_demand identity)

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
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (HEAD b430bbcb). Delta to review: `git diff 02927248..b430bbcb` (exclude .oracle/**). Acceptance criteria: .oracle/plan.md "Checkpoint A" section. Executor claims all tests implemented and green, no functional deviations.

## DELEGATION MANDATE
You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: ox-alpha. Invocation: `python3 /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model stealth/ox-alpha --query-file=<brief> --project-dir=/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`. Dispatch verification briefs (e.g. "run the acceptance tests and report verbatim output; probe the mixed-pack case; attempt to construct a tier-masquerade") to ox-alpha; critique passes optimize for elegance (KISS/YAGNI — flag overengineering). Your job: direct, then validate delegated output against acceptance criteria. Work yourself only where delegation is impossible.

## VERDICT
Binary: `PASS` or evidence-backed issue list. Include an explicit North Star alignment disposition (anti-patterns: tier masquerade, permanent installs, parallel schema systems, stub-as-truth). <300 words.
