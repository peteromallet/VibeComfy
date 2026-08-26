# ORACLE FINAL OVERALL REVIEW — 4-item contract (schema-capture integration)

## NORTH STAR (complete — every pass must cite it)
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
Repo: vibecomfy-oracle (HEAD d2975269, branch oracle-run, base 96a9d810, origin/fixer/...). Review the FROZEN run contract against the WORKTREE STATE.

Frozen artifacts on disk: .oracle/agent_goal.md (4 done criteria + stop conditions), .oracle/northstar.md, .oracle/plan.md (A/C/D/E, B deferred), .oracle/tasklist.md or plan.md task ordering, batch check-ins .oracle/checkins/{batch-A,batch-C,batch-D,batch-E}.md, per-batch commits (A:b430bbcb C:5f3e635f D:86e4a6ba E:d2975269), and raw receipts/evidence.

Batches:
- A: persist glue + honest tier identity (preserve-on-demand-pack, merge with index hygiene, tier guard, provenance ledger) — Batch A PASS
- C: schemas ensure --manifest (ephemeral clone ladder, rung2 default-ON) — Batch C PASS
- D: preflight bridge (allowlist, source_kind exact match, tiers map, strict flag) — Batch D PASS
- E: doctor gap reporting + SKILL docs + e2e fixture (format_schema_gap, validate-coverage --manifest, doctor hint, honest-tier e2e) — Batch E PASS

Final validation contract (agent_goal.md): focused `pytest tests/ -k "schema or on_demand or obligation" -q` green + one authoritative host/oracle full-suite sweep (one owner), one expensive/live validation once (other agents may inspect). Also: fixture manifest missing→ensure→preflight green using only on_demand captures (E2E), SKILL section exists.

Include:
- Evidence-backed mapping of EVERY agent-goal criterion to its evidence path/command/result/reviewer disposition.
- Short North Star alignment disposition (ephemeral clone, honest provenance, fail closed, no permanent installs, no parallel schema systems, tier masquerade avoided — name any anti-pattern reproduced).
- Stop-classification (blocked/failed/undetermined/retryable/escalate) if applicable.
- One owner runs the broad/full suite ONCE: include its result now if already in receipts, otherwise run it as part of this review. One owner runs each expensive/live validation once.

## DELEGATION MANDATE
You are a manager and validator of the normal execution pool, NOT a worker for the validation itself. For the full-suite sweep, delegate ONE normal-pool invocation (Spark: openrouter/meta/muse-spark-1.2-contributor, via launch_hermes_agent.py --model openrouter/meta/muse-spark-1.2-contributor) to run the broad suite once; have another verify the fixture e2e fixture end-to-end by reading the existing .oracle/evidence/batch-E-matrix.md + test_batch_e_e2e.py receipts. Dispatch research/critique briefs to Spark — critique passes optimize for elegance (KISS/YAGNI). Your job: direct, then validate delegated output against acceptance criteria. Work yourself only where delegation is impossible.

## VERDICT
Binary: PASS or evidence-backed issue list covering goal criteria + North Star. Also state final sync authorization (push oracle-run to origin, fast-forward main to reviewed merge) as authorized in agent_goal.md (no force-push). Final disposition must name the head SHA reviewed.
