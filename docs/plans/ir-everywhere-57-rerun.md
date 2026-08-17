# L1 — 57-case post-migration live rerun

Checkpoint 16 requires the 57 first-attempt failures from

`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-recovery-run/out/agentic/recovery-rerun/run_summary.json`

to be rerun on the final IR-everywhere commit and reconciled to
`resolved | capability_floor | infra_out_of_scope`.

## Command attempted

Ran from `/Users/peteromalley/Documents/reigh-workspace/vibecomfy-recovery-run`
with the ir-everywhere product tree on `PYTHONPATH`:

```bash
PYTHONPATH=/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy \
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/bin/python \
  -m tests.live_agentic_harness.runner \
  --tag ir-everywhere-57 \
  --scenarios-dir tests/live_agentic_harness/scenfails57 \
  --manifest tests/live_agentic_harness/scenfails57_manifest.json \
  --transport openrouter \
  --output-base out/agentic \
  --max-workers 6 \
  --per-scenario-timeout 1200 \
  --infra-retries 1 \
  --json
```

The 57 JSON files and manifest were copied into
`tests/live_agentic_harness/scenfails57/` in the recovery-run worktree
(the runner requires scenario paths inside that repo).

Output: `out/agentic/ir-everywhere-57/` (and `/tmp/ir-everywhere-57-run.log`).

## Allowed statuses

Judge verdicts are `assessment.json` `passed`, not executor-level `ok`.

- `resolved`: v3 judge `passed=true` (16 ids). Mechanism: v3 live rerun on ir-everywhere branch.
- `capability_floor`: named evidence only (Class D `cc0df7`/`90a1d5` in `b09_reducer.py`; variance `multi-wan-vace-video-retargeting-driven` in `variance.md`) that v3 still confirms as product_fail.
- `infra_out_of_scope`: v3 `failure_class=infra_timeout` (8 ids).
- `pending_live_rerun`: remaining v3 product_fail, including `5b31ce` (`other.md` is not named floor evidence).

## Result (v3 complete)

`out/agentic/ir-everywhere-57-v3/run_summary.json`: `complete: true`,
`final_score: 16/57` (16 passed / 8 infra / 33 product_fail).

Ledger after reconcile: **16 `resolved`**, **3 `capability_floor`**,
**8 `infra_out_of_scope`**, **30 `pending_live_rerun`**.
