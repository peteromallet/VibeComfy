# EXECUTOR BRIEF — Batch B: rung 3 (embedded pip-comfy, no server) [XHARD]

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
You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: Spark. Invocation: python3 /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model openrouter/meta/muse-spark-1.2-contributor --query-file=<brief> --project-dir=/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle. Dispatch research/implementation/critique briefs to Spark; critique passes optimize for elegance (KISS/YAGNI). Work yourself only for the irreducible judgment kernel.

## TASK (from frozen plan — read .oracle/plan.md "Batch B — DEFERRED" IN FULL for the factory detail)
Work in vibecomfy-oracle (branch oracle-run, HEAD = 9af848dc merge to main, base 96a9d810). Batches A/C/D/E landed (r1/r2 ladder + preflight bridge). This is the DEFERRED conditional: it only exists because schemas ensure --manifest on final50 left 2 gaps (easy int, easy forLoopEnd/Start) that r1 (AST) + r2 (stubbed import) could not serve — they need genuine comfy modules.

1. Factor ONLY the throwaway-venv + `pip install comfyui=={version}` helper out of `porting/object_info/core_regen.py` so both regen-core and rung 3 share it. Do NOT share _OBJECT_INFO_CAPTURE_SCRIPT (that one serves HTTP).
2. Add `extract_by_embedded(pack_dir, *, pack_name, version, only_classes=None, comfy_version, timeout, scratch_dir) -> (entries, "embedded")`: create venv under TemporaryDirectory; pip-install pinned comfyui=={comfy_version}; in a CHILD interpreter import real `comfy`/`nodes`, put pack_dir on sys.path, load pack NODE_CLASS_MAPPINGS, call INPUT_TYPES(), emit object_info-shaped JSON. NO main.main, NO bind, NO /object_info HTTP, NO GPU device init (fail closed if child tries to serve). Parent never imports comfy. Always rmtree the venv. Timeout env-tunable; default >120s. On TimeoutExpired return empty + failure string.
3. Extend extract_pack_schemas: keep order import (if allow_import, default True) → AST if empty. New: if still empty and allow_embedded=True (default False on the function; ensure will pass True), run rung 3. ExtractResult.method becomes "import"|"ast"|"embedded"|"" . Do NOT change OnDemandInstallSchemaProvider gating (VIBECOMFY_ON_DEMAND_BOOT) — that is the live authoring ladder, not persist.
4. Unit tests with a fake runner (mirror test_core_regen_runner_installs_pinned_comfyui_and_captures_object_info in tests/test_schemas_ensure.py:281–312): assert pip command, assert child -c script does not reference main.main / urlopen / port 8188, assert method "embedded". No real PyPI in unit tests.

## EVIDENCE FOR THIS TRIGGER
`vibecomfy schemas ensure --manifest tests/live_agentic_harness/threaded_comparison_manifest_final50.json` (rung 1/2 only, after A/C) left:
  easy int: empty extract (r1+r2) — needs r3
  easy forLoopEnd: same
These are from ComfyUI-Essentials / ComfyUI_Comfyroll_CustomNodes loop int nodes — only resolvable by executing INPUT_TYPES against real comfy.

## ACCEPTANCE (Checkpoint B)
- rg 'extract_by_embedded|allow_embedded|on_demand_embedded' hits the new API.
- Fake-runner test proves no server path.
- extract_pack_schemas(..., allow_import=True, allow_embedded=True) on a pack that succeeds at import never calls embedded (rung 3 miss-only).
- tests/test_on_demand_resolver.py still green; A/C/D/E still green.
- Commit: "schemas-ensure(B): embedded comfy-as-library extraction (rung 3, no server)".

## RULES
- Do NOT touch docs/plans/**, assessment rubrics, or anything beyond scope.
- Report: files changed, verbatim test results, any deviation with reason.
