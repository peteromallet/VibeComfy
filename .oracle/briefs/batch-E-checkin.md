# ORACLE BATCH CHECK-IN — Batch E (doctor + docs + e2e fixture)

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
Repo: vibecomfy-oracle (HEAD d2975269). Delta to review: git diff 86e4a6ba..d2975269 (exclude .oracle/**). Acceptance criteria: .oracle/plan.md "Checkpoint E" section. Also verify the 5 executor-reported claims against the delta: (1) format_schema_gap helper single source, (2) validate-coverage --manifest reuses Batch A missing-live-captures helper, (3) doctor prints ensure command and injects ensure_command JSON, does NOT clone/extract, (4) SKILL.md mechanical section (missing blocks preflight, ensure flow, tier acceptance, stub rejection, strict flag, doctor/validate-coverage pointer), (5) e2e fixture: empty tmp cache -> preflight fails with ensure command -> schemas ensure --manifest -> preflight green with resolution_tiers on_demand_*, strict/stub rejections, no stub. Include explicit North Star alignment disposition.

## DELEGATION MANDATE
You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: Spark. Invocation: python3 /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model openrouter/meta/muse-spark-1.2-contributor --query-file=<brief> --project-dir=/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle. Dispatch verification briefs (run the acceptance tests and report verbatim output; probe doctor isolation; probe SKILL docs) to Spark; critique passes optimize for elegance (KISS/YAGNI). Your job: direct, then validate delegated output against acceptance criteria. Work yourself only where delegation is impossible.

## VERDICT
Binary: PASS or evidence-backed issue list. Include an explicit North Star alignment disposition. <350 words.
