# VERIFY — Batch E acceptance tests (read-only except pytest)

You are Spark verifying Batch E at HEAD `d2975269` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Tests may run; do not commit. If pytest dirties
`vibecomfy/porting/cache`, capture evidence then `git checkout --` that tree.

## What to do

1. `cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`
   Confirm `git rev-parse HEAD` starts with `d2975269`.
   Confirm `git log -1 --oneline` is
   `d2975269 schemas-ensure(E): doctor gap reporting + SKILL docs + e2e fixture`

2. File inventory of the code delta (exclude `.oracle/**`):
   ```
   git diff --stat 86e4a6ba..d2975269 -- . ':!.oracle/**'
   ```
   Expected six files: `docs/agent-skill/SKILL.md`, `tests/live_agentic_harness/scenario_obligations.py`, `tests/test_batch_e_e2e.py`, `vibecomfy/commands/doctor.py`, `vibecomfy/commands/schemas.py`, `vibecomfy/schema/ensure_capture.py`.
   Report extra/missing files.

3. Run Checkpoint E focused tests. Paste FULL summary lines and ANY failure bodies verbatim:
   ```
   python3 -m pytest tests/test_batch_e_e2e.py -q --tb=short
   python3 -m pytest tests/test_ensure_capture.py tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py tests/test_batch_e_e2e.py -q --tb=line
   python3 -m pytest tests/test_schemas_ensure.py -q --tb=line
   ```
   Name which `test_schemas_ensure.py` failures (if any) are pre-existing quarantined baselines vs new.

4. Also run the plan's host focused filter (NOT the 8512-test full suite):
   ```
   python3 -m pytest tests/ -k "schema or on_demand or obligation" --ignore=tests/test_live_agentic_watchdog.py -q --tb=line
   ```
   Paste the summary. If this exceeds ~4 minutes, note that and report whatever finished.

5. Required test inventory — for each, report PRESENT + test function name, or ABSENT. Read `tests/test_batch_e_e2e.py` (do not just trust names):
   - empty tmp cache → preflight fails AND the message contains `vibecomfy schemas ensure --manifest <path>`
   - then `schemas ensure --manifest` with mocked registry + real extract on a local fixture pack (not a hand-authored `@stub.json`)
   - then preflight green with `resolution_tiers[...][FixtureNode].source_kind` in `{on_demand_static, on_demand_import}`
   - `runtime_only=True` and/or `VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1` reject after on-demand capture
   - stub/`@stub.json` never passes as live
   - doctor prints ensure command (template form and/or `--manifest` hint); doctor test does not call clone/extract
   - `validate-coverage --manifest` exits 1 on gaps; JSON has `missing_classes` and `ensure_command`; template positional still exit 0
   - fixture pack is real source (`INPUT_TYPES` / nodes.py in a git repo), not a stub file presented as live

6. After pytest: `git status --porcelain`. Report dirty paths. Restore cache if dirtied.

## Return (max 400 words)

- HEAD + commit message (verbatim)
- diff --stat (verbatim)
- Verbatim pytest summaries (all three + k-filter if it completed)
- Table: required test vs present/absent + function name
- Cache/source dirty after tests: yes/no + paths
- Checkpoint E test criteria: PASS or FAIL with evidence
