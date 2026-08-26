# FINAL REVIEW — one-owner full-suite sweep (YOU ARE THE ONLY PYTEST OWNER)

You are Spark (`openrouter/meta/muse-spark-1.2-contributor`) in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
HEAD must be `d2975269`. Branch `oracle-run`.

Do NOT edit source. Do NOT commit. You MAY run pytest. If pytest dirties
`vibecomfy/porting/cache`, restore with `git checkout -- vibecomfy/porting/cache`
before you finish. Leave `.oracle/receipts/` writes only.

You are the SINGLE owner of the full suite for this review. Run it ONCE.

## Commands (run in order)

1. Confirm identity:
```
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
git rev-parse HEAD
git log -1 --oneline
```
Abort if HEAD is not `d2975269`.

2. Restore cache first so the suite starts clean:
```
git checkout -- vibecomfy/porting/cache || true
```

3. Official full-suite gate (`Makefile` target `full-pytest`), with watchdog
   ignored because this venv lacks `arnold.pipelines.megaplan` (collection error).
   Use the venv interpreter. Tee the full log:
```
mkdir -p .oracle/receipts
# There is NO .venv in this worktree. Use python3 (pytest 9.0.2, xdist 3.8.0).
# Do not `make full-pytest` — Makefile PYTHON=.venv/bin/python is missing.
PYTHONHASHSEED=0 python3 -m pytest -n 8 -q -p no:cacheprovider \
  --ignore=tests/test_live_agentic_watchdog.py \
  --tb=line \
  2>&1 | tee .oracle/receipts/final-full-suite.log
echo EXIT:$? | tee -a .oracle/receipts/final-full-suite.log
```
   This will take a long time (tens of minutes). Do not kill it early.
   Do not add extra `-k` filters. Do not skip more files unless collection
   is impossible; if you must add another ignore, name the exact error.

4. After pytest:
```
git status --porcelain
git checkout -- vibecomfy/porting/cache || true
git status --porcelain
```

5. Classify failures:
   - Read `tests/quarantine/*.txt` and mark each failed node as
     QUARANTINED (listed) vs NEW vs PREEXISTING-UNQUARANTINED.
   - Files this branch added/changed (A–E, exclude `.oracle/**`):
     `vibecomfy/schema/ensure_capture.py`, `vibecomfy/schema/on_demand.py`,
     `vibecomfy/commands/schemas.py`, `vibecomfy/commands/doctor.py`,
     `tests/live_agentic_harness/scenario_obligations.py`,
     `tests/test_ensure_capture.py`, `tests/test_schemas_ensure.py`,
     `tests/test_scenario_obligation_preflight.py`,
     `tests/test_p4_objectinfo_caches.py`, `tests/test_batch_e_e2e.py`,
     `docs/agent-skill/SKILL.md`.
   - A failure in an untouched file is not a schema-capture regression
     unless the traceback points into those files.

## Return (max 500 words)

- HEAD SHA
- exact command run + wall time
- pytest summary line verbatim (N passed, N failed, N skipped, …)
- process exit code
- table: each failed node → QUARANTINED / NEW / PREEXISTING, and whether
  traceback touches A–E files
- cache restored: yes/no
- verdict: FULL-SUITE-GREEN | FULL-SUITE-QUARANTINED-ONLY | FULL-SUITE-REGRESSION
  (regression = any NEW failure in A–E files or caused by A–E code)
