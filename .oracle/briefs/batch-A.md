# EXECUTOR BRIEF — Batch A: persist glue + honest on-demand identity

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

## TASK (from frozen plan — read .oracle/plan.md "Batch A" section for full detail)
Work in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run, base 96a9d810). Implement Batch A exactly as the plan specifies:
1. New thin glue module `vibecomfy/schema/ensure_capture.py` (or on_demand_persist.py — one module).
2. Adapter: `extract.normalize_entry` shape → build_cache raw dump shape (see plan for field mapping; do NOT teach build_cache a second dialect).
3. `persist_on_demand_pack(...)`: build_cache with CacheIdentity(source_kind=<on_demand_static|on_demand_import>, evidence_identity=f"on_demand:{rung}:{sha}", git_commit=resolved clone sha), **full_pack_refresh=False**, then the TWO-LAYER post-processing from the plan's "File hygiene" bullet: (a) strip non-newly-captured classes from the new pack file, (b) restore index.json mappings for pre-existing classes. Attest provenance.json row: pack, repo (clone remote), locked_commit (clone rev-parse), schema_sha256, source_kind, extraction_rung, registry_pack_version, captured_at. Reuse _load_provenance/_write_provenance.
4. Gap helper `missing_live_captures(...)` per plan (index-missing / stub / no-provenance / no-pin = gap; list_classes alone insufficient).
5. Tier guard: never overwrite higher tier (runtime family > on_demand_embedded > on_demand_import > on_demand_static); same-or-higher = no-op; stubs replaceable.
6. consume.reset_cache() after write.

## ACCEPTANCE (Checkpoint A — implement the tests, they are the deliverable)
All tests in tests/test_ensure_capture.py (tmp cache dirs, no network):
- persist AST extract → Pack@on_demand_static-<sha>.json; entries source_kind==on_demand_static; provenance row complete; index maps class to that file.
- persist import extract → on_demand_import, NOT runtime_object_info.
- **Mixed-pack case**: runtime capture for class R of pack P exists; extract P (R + gap G) → on_demand file keys == {G} EXACTLY (R not copied); index[R] still runtime file; index[G] on_demand file; get_class_by_identity(R) unique (no ObjectInfoIdentityAmbiguityError).
- persist over existing runtime capture for same class = no-op; runtime file + index unchanged.
- @stub.json index row treated as gap.
- pytest tests/test_ensure_capture.py -q green; also run pytest tests/test_schemas_ensure.py tests/test_on_demand_resolver.py -q (must stay green).

## RULES
- Read .oracle/plan.md Batch A + Canonical tokens first; compose-map mechanisms only, no parallel systems.
- Do NOT touch docs/plans/**, assessment rubrics, or anything outside the scope above.
- Commit when green: message "schemas-ensure(A): persist glue + honest on_demand identity + mixed-pack hygiene".
- Report: files changed, test results verbatim, any deviation from plan with reason.
