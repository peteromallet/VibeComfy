# EXECUTOR BRIEF — Batch C: `vibecomfy schemas ensure --manifest`

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

## TASK (from frozen plan — read .oracle/plan.md "Batch C" section for full detail)
Work in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run, HEAD = post-Batch-A). Batch A already landed: `vibecomfy/schema/ensure_capture.py` (persist_on_demand_pack, missing_live_captures, tier guard). Implement Batch C exactly as the plan specifies:
1. Extend `register()` in `vibecomfy/commands/schemas.py`: keep positional `template` back-compat; add `--manifest PATH` (comparison manifest, entries[].id); exactly one of template/--manifest; `--json`; `--comfy-version` flag-or-env `VIBECOMFY_EMBEDDED_COMFY_VERSION` only, fail closed naming both if r3 needed and unset; `--no-embedded` accepted as documented no-op placeholder (r3 not yet available — Batch B deferred; if a class can only be served by r3, fail closed naming deferred B). Rung 2 cannot be disabled on this command.
2. Manifest gated-class discovery: reuse `load_scenario_obligation` + `_GATED_CLASS_RE` from tests/live_agentic_harness/scenario_obligations.py — do not copy the regex.
3. Per missing live capture (Batch A helper): resolve_pack/resolve_missing_nodes → PackRef; clone via OnDemandInstallSchemaProvider._ensure_clone (sandbox LRU — do NOT use .tmp_packs/clone_and_extract_packs.clone_pack); extract_pack_schemas(allow_import=True, import_timeout=120) — **NO allow_embedded kwarg** (doesn't exist; TypeErrors); map result.method → persist token; persist_on_demand_pack (Batch A); _enforce_cap after each pack.
4. Fail closed: registry miss / clone fail / all rungs empty → non-zero exit (text AND --json; fix the emit→0 swallow at schemas.py:567-568); message names class + failed step + exact retry command. Never write hollow/stub schemas.
5. Rewire existing template ensure off tools.clone_and_extract_packs.process_pack onto this glue. Leave the standalone ETL tool untouched.
6. Tests in tests/test_schemas_ensure.py actually calling _cmd_schemas_ensure (per plan: noop when attested; missing→mocked resolve+clone→real extract on fixture→cache+provenance; r2 default-on regardless of VIBECOMFY_ON_DEMAND_BOOT; stub-indexed = gap; --json failure non-zero; no network).

## ACCEPTANCE (Checkpoint C)
- `vibecomfy schemas ensure --help` shows --manifest.
- Fixture: missing gated class, mocked registry+clone, real extract on fixture pack → on_demand file + provenance; get_class/index provider returns it; @stub.json still filtered.
- `grep -r clone_and_extract_packs vibecomfy/commands/schemas.py` empty.
- pytest tests/test_schemas_ensure.py tests/test_on_demand_resolver.py -q green; Batch A tests still green.
- Commit: "schemas-ensure(C): --manifest gated-class capture via ephemeral clone ladder".

## RULES
- Compose-map mechanisms only. No docs/plans/** edits, no rubric edits, nothing beyond scope.
- Report: files changed, verbatim test results, deviations with reasons.
