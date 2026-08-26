# Agent Goal — Registry-pinned ephemeral schema capture + preflight bridge

[North Star](./northstar.md) — this run turns the North Star's end state into shipped code: one-command install-free schema capture, persisted and preflight-accepted.

## Objective
On the VibeComfy repo (base `96a9d810`, branch `oracle-run`), implement and validate:
1. **`vibecomfy schemas ensure --manifest <m>`** — for every gated class in the manifest lacking a live capture: resolve the pack via the Comfy registry (`registry/pack_resolver.py`), temp shallow-clone (`schema/on_demand.py`), run the extraction ladder (`schema/extract.py:extract_pack_schemas`) with three rungs: (r1) AST parse; (r2, default-ON per operator) stubbed-subprocess import; (r3) pip-installable ComfyUI as a library — install the pip comfy package in the throwaway venv and load the pack's NODE_CLASS_MAPPINGS against genuine comfy modules to generate object_info-equivalent schemas in-process, **no server, no serve, no GPU**. Persist via `porting/object_info/serialize.py:build_cache` with `CacheIdentity` stamped `source_kind=on_demand_static|on_demand_import|on_demand_embedded`, registry pack version + resolved commit + rung in the provenance ledger. Sandbox evicted after (LRU bounds preserved).
2. **Preflight bridge** — the live-agentic-harness scenario-obligations preflight accepts `on_demand_static`/`on_demand_import`/`on_demand_embedded` tiers as valid provenance, recorded as their own tier; `@stub.json` rejection unchanged; a strict flag preserves runtime-only mode for campaign-grade runs.
3. **Doctor gap reporting** — `vibecomfy doctor` (or schemas validate-coverage) reports gated classes lacking captures + the exact `schemas ensure` command.
4. **Tests** — unit (persistence glue, tier stamping), preflight (on-demand accepted, stub still rejected, strict flag), e2e: a manifest with a missing-capture class → ensure → preflight green.
## Authoritative inputs / source ref
- Base SHA `96a9d81021a6ccee43ccb9afccdf49ff6ae4a5b5` (origin/fixer/workflow-execution-spine-consolidation, box HEAD), worktree `/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
- Scout findings: `.oracle/findings/` (three scout reports: static extraction map, registry sources, trust tiering).

## In scope / non-goals
- In scope: the four items above; agent-skill SKILL.md section documenting the flow.
- Non-goals: pip/uv ComfyUI runtime provisioning (separate future feature); changes to runtime-capture pipeline; assessment rubrics; live model calls; changes to `docs/plans/**` campaign evidence.

## Settled decisions (operator)
- Rung 2 (stubbed-subprocess import) **default-ON** in `schemas ensure`.
- Venue: land on **main** (operator: "MAIN LIKE EVERYTHING FROM THE BOX"); source = box latest (`96a9d810`).
- Model declaration (operator): **Normal = ox-alpha; Oracle = Grok 4.6; XHARD = oracle class (Grok 4.6)**.

## Authorization boundaries
- Mutate: worktree only; commit per batch.
- Sync: after final review PASS — push `oracle-run` to origin, then fast-forward `main` to the reviewed merge (explicit refspec, recorded). No force-push.
- No deployment.

## Done criteria
- All four items implemented, tests green (`pytest tests/ -k "schema or on_demand or obligation" -q` plus full suite once by host), preflight green for a previously-blocked manifest subset using only on-demand captures, evidence matrix complete, final oracle review PASS.

## Stop conditions
- `blocked` if the Comfy registry API is unreachable from this machine (capture e2e needs it) — report and stop.
- `failed` on any reproducible unmet criterion after rework loop.
