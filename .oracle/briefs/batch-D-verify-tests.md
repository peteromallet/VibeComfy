# VERIFY — Batch D acceptance tests (read-only except pytest)

You are ox-alpha verifying Batch D at HEAD `86e4a6ba` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Tests may run; do not commit. If pytest dirties
`vibecomfy/porting/cache`, capture evidence then `git checkout --` that tree.

## What to do

1. `cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`
   Confirm `git rev-parse HEAD` is `86e4a6ba3b458c3ba5ec985452dae6a7fe7577fd`.

2. Old allowlist string must be gone; explicit allowlist present:
   ```
   rg -n "only 'authoritative_object_info' is authoritative" tests/live_agentic_harness/scenario_obligations.py; echo "rg_exit=$?"
   rg -n "DECLARED_SCHEMA_SOURCES|on_demand_static|on_demand_import|on_demand_embedded|on_demand_runtime" tests/live_agentic_harness/scenario_obligations.py tests/test_scenario_obligation_preflight.py
   ```
   Paste verbatim.

3. Run Checkpoint D tests:
   ```
   python3 -m pytest tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py -q --tb=short
   ```
   Paste the FULL summary line and ANY failure bodies verbatim.

4. Confirm Batch A+C still green (do not treat pre-existing `test_schemas_ensure.py` failures as D):
   ```
   python3 -m pytest tests/test_ensure_capture.py tests/test_schemas_ensure.py -q --tb=line
   ```
   Paste summary. Name which failures (if any) existed before D vs new.

5. Required test inventory — for each, report PRESENT + test function name, or ABSENT:
   - tmp cache: on-demand attested file + declaration `source=on_demand_static` → preflight ok; payload records `on_demand_static`
   - same file vs declaration `authoritative_object_info` → fail (no masquerade)
   - `@stub.json` indexed+attested → fail
   - `runtime_only=True` (and/or `VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1`) rejects on-demand even if declared `on_demand_*`
   - FINAL5 IndexTTS/LayerMask still pass (runtime pins)
   - FINAL50 unproven classes still fail
   - missing on-demand evidence names `vibecomfy schemas ensure --manifest <that manifest>`
   - `@on_demand_` filename cannot satisfy `authoritative_object_info` even if JSON `source_kind` lies

6. After pytest: `git status --porcelain`. Report dirty paths. Restore cache if dirtied.

7. Confirm commit message:
   ```
   git log -1 --oneline
   ```
   Expected: `86e4a6ba schemas-ensure(D): preflight accepts on_demand tiers as themselves; runtime_only strict flag`

## Return (max 400 words)

- Verbatim rg of old string (expect no match / exit 1) and DECLARED_SCHEMA_SOURCES hit
- Verbatim pytest summaries
- Table: required test vs present/absent + function name
- Cache/source dirty after tests: yes/no + paths
- Checkpoint D test/rg/commit criteria: PASS or FAIL with evidence
