# EXECUTOR BRIEF — Batch E: doctor gap reporting, SKILL docs, e2e fixture

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

## TASK (from frozen plan — read .oracle/plan.md "Batch E" section for full detail)
Work in vibecomfy-oracle (branch oracle-run, HEAD = post-Batch-D 86e4a6ba). Batches A+C+D landed.

1. Shared helper `format_schema_gap(manifest_path, missing_classes) -> str` that ends with the exact command `vibecomfy schemas ensure --manifest <path>` (Batch A gap helper already exists — reuse it; do not duplicate).
2. `vibecomfy schemas validate-coverage`: add `--manifest` (reuses gap helper + Batch A missing_live_captures logic). Exit 1 when --manifest and gaps exist (template positional keeps exit 0 for back-compat). JSON includes missing_classes, ensure_command.
3. `vibecomfy doctor <path>` (vibecomfy/commands/doctor.py or commands/__init__.py entry): on unknown_class_type / missing schema for a workflow/template path, print the same ensure command (workflow/template: `vibecomfy schemas ensure <template>`; if a comparison manifest is not in hand, also print "or --manifest <comparison.json>"). Doctor must NOT clone or extract — reporting only.
4. `docs/agent-skill/SKILL.md`: one mechanical section: missing capture blocks preflight; `vibecomfy schemas ensure --manifest <m>` (registry→ephemeral clone→r1/r2→cache+provenance tier); preflight accepts on_demand_* as those tiers, @stub.json never; campaign-grade VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1; doctor / schemas validate-coverage --manifest print the command. Do NOT edit docs/plans/**.
5. E2E (deterministic, no GPU, network gated): fixture comparison-manifest + one synthetic gated class + local fixture pack (NOT a hand-authored @stub.json presented as live). In tests: empty tmp cache → preflight fails with ensure command in text → schemas ensure --manifest (registry mocked; real extract on fixture pack) → preflight green; recorded tier is on_demand_static or on_demand_import. Optionally host-only (skip if api.comfy.org unreachable — stop condition, do not fake schemas).
6. Evidence matrix — test docstrings or .oracle/evidence/ entry (not docs/plans/**): command, source_kind, commit, rung, preflight verdict, strict verdict, stub verdict.
7. Host once (executor, not a separate agent): pytest tests/ -k "schema or on_demand or obligation" -q AND a full suite sweep.

## ACCEPTANCE (Checkpoint E → done criteria)
- All four agent-goal items present in code.
- Focused pytest green; host full suite once (report verbatim).
- Fixture manifest: missing→ensure→preflight green USING ONLY on_demand captures (honest tier).
- docs/agent-skill/SKILL.md section exists.
- Final oracle full-contract review of the four-item contract (dispatched by host after this batch passes).

## RULES
- Read .oracle/plan.md Batch E IN FULL first; compose-map mechanisms only, no parallel systems.
- Do NOT touch docs/plans/**, assessment rubrics, or anything beyond scope.
- Commit when green: "schemas-ensure(E): doctor gap reporting + SKILL docs + e2e fixture".
- Report: files changed, verbatim test results (focused + full), any deviation with reason.
