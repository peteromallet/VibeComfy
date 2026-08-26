# CRITIQUE — Checkpoint D completeness + KISS/YAGNI (read-only)

You are ox-alpha reviewing Batch D at HEAD `86e4a6ba` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Do not run pytest (other agents own tests).

Read:
```
git diff 5f3e635f..86e4a6ba -- tests/live_agentic_harness/scenario_obligations.py tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py
```
Acceptance: `.oracle/plan.md` Batch D tasks 1–7 and Checkpoint D.

Optimize for elegance (KISS/YAGNI). Flag overengineering. Do not rubber-stamp.

## Check each plan task (PASS/FAIL + file:line)

1. Declaration allowlist exactly: `authoritative_object_info` | `on_demand_static` | `on_demand_import` | `on_demand_embedded`. No `on_demand_runtime` alias.
2. After `ObjectInfoIndexSchemaProvider.get`: read cache `source_kind` from pack JSON (not `NodeSchema.source_provider`). Exact match to declared source for on-demand tokens. `authoritative_object_info` is a runtime-family claim, never satisfied by `on_demand_*`. Provenance `repo` or `locked_commit` required; ledger `source_kind` matches entry if present. Parallel `resolution_tiers` map; boolean `resolution` untouched.
3. Stub rejection: keep `@stub.json` index filter; explicit fail if resolved file is stub-shaped (`source_kind==workflow_json_stub` or filename suffix).
4. `preflight_scenario_obligations(..., runtime_only: bool | None = None)` + env `VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1` (do not reuse dead `VIBECOMFY_OBLIGATION_SCHEMA_CHECK`). When set: only authoritative declarations + runtime-family cache kinds; on-demand violation names the strict flag; `schemas ensure` is NOT claimed as enough.
5. Missing on-demand evidence includes `vibecomfy schemas ensure --manifest <that manifest>`.
6. No rewrite of campaign `SCHEMA_EVIDENCE_REQUIREMENTS` or assessment rubrics. Preflight local-only (no `OnDemandInstallSchemaProvider.get_schema`).
7. Tests listed in plan Checkpoint D / Batch D task 7.

Checkpoint D:
- `rg "only 'authoritative_object_info' is authoritative" tests/live_agentic_harness/scenario_obligations.py` gone
- explicit allowlist
- commit message matches `schemas-ensure(D): preflight accepts on_demand tiers as themselves; runtime_only strict flag`

## KISS / YAGNI

- Count new helpers in `scenario_obligations.py`. Glue or a parallel schema system?
- Substring-sniff for env/flag/stub path? Executor claimed a KISS cut: reuse `_read_existing_index`, no substring-sniff for the strict flag. Verify that landed.
- Runtime-family recognizer: is the legacy `@local.json` unstamped clause the smallest honest fix, or a second allowlist that will rot?
- Duplicate source_kind readers vs compose-don't-duplicate.
- Test helpers: over-mocked? Ceremonial assertions that cannot fail?

Executor deviations to judge (blocking vs acceptable):
1. Two vocabularies: declaration `authoritative_object_info` vs cache never stamping that string; FINAL5 via legacy-ingest.
2. Stale FINAL50 test rewritten to assert fail (unproven) rather than ok.
3. Kernel follow-up after first ox-alpha: stub test class name, `@on_demand_` filename gate, ensure-command copy.

## Return (max 400 words)

- Task 1–7 PASS/FAIL table
- Checkpoint D PASS/FAIL
- Overengineering findings (or "glue is thin enough")
- Deviations: blocking or not
- Overall: PASS or issue list
