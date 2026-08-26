# CRITIQUE — Checkpoint C completeness + KISS/YAGNI (read-only)

You are ox-alpha reviewing Batch C at HEAD `5f3e635f` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Do not run pytest (other agents own tests). Read the delta:

```
git diff b430bbcb..5f3e635f -- vibecomfy/commands/schemas.py tests/test_schemas_ensure.py
```

Acceptance is `.oracle/plan.md` Batch C tasks 1–6 and Checkpoint C.

## Check each plan task (PASS/FAIL + file:line)

1. register(): positional template kept; `--manifest PATH`; exactly one required; `--json`; `--comfy-version` / env `VIBECOMFY_EMBEDDED_COMFY_VERSION`; `--no-embedded` no-op placeholder; r2 cannot be turned off; do not honor `VIBECOMFY_ON_DEMAND_BOOT=0`.
2. Manifest gated-class discovery reuses `load_scenario_obligation` + `_GATED_CLASS_RE` (no copied regex). Classes = workflow classes matching regex ∪ declared `schema_evidence_requirements[].class_type`.
3. Per gap: `resolve_pack` / `resolve_missing_nodes` → PackRef with url; clone via `OnDemandInstallSchemaProvider._ensure_clone` (sandbox LRU, not `.tmp_packs`); `extract_pack_schemas(..., allow_import=True, import_timeout=120)` with NO `allow_embedded` kwarg; map method → persist token; pin from clone git remote + HEAD; `persist_on_demand_pack`; `_enforce_cap()` per pack.
4. Fail closed: registry miss / clone fail / all rungs empty → exit 1 in text AND `--json`; message names class, step, exact retry command; never hollow/stub write.
5. Template ensure rewired off `tools.clone_and_extract_packs.process_pack` onto the same engine; gap via `missing_live_captures`; standalone ETL tool untouched.
6. Tests actually call `_cmd_schemas_ensure` covering: noop attested; missing→mocked resolve+clone+real extract; r2 default-on; stub is gap; json failure non-zero; no network.

Checkpoint C:
- help shows `--manifest`
- fixture path described above
- `rg clone_and_extract_packs vibecomfy/commands/schemas.py` empty
- commit message matches `schemas-ensure(C): --manifest gated-class capture via ephemeral clone ladder`

## KISS / YAGNI (optimize for elegance)

Flag overengineering: extra helpers that wrap one call, duplicated gap logic, second provenance writer, copied regex, unused `--comfy-version` machinery that cannot fire until B, unnecessary abstraction around subprocess git pin.

Count new functions in schemas.py. Say whether C is glue or a parallel capture engine.

Executor deviations to judge:
- Tests create a real on-disk manifest even when discovery is monkeypatched (command checks `is_file()`). Acceptable fail-closed?
- Template-mode payload keys preserved but per-pack report shape changed to `{pack, method}`. Back-compat break?

Do not rubber-stamp. If a required task is missing, FAIL it.

## Return (max 400 words)

- Task 1–6 PASS/FAIL table
- Checkpoint C PASS/FAIL
- Overengineering findings (or "glue is thin enough")
- Payload-shape / manifest-file deviations: blocking or not
- Overall: PASS or issue list
