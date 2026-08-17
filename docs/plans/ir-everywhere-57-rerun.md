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

`pending_live_rerun` is only legal *before* this rerun completes. After
results land, every id must become `resolved`, `capability_floor`, or
`infra_out_of_scope`. The named floors already classified from the 2026-08-15
recovery rerun stay as:

- capability_floor: `cc0df7`, `90a1d5`, `multi-wan-vace-video-retargeting-driven`, `5b31ce`
- infra_out_of_scope: `c24aa2`, `f65774`, `00444a`

## Result (partial, run still live at commit time)

The runner process is live (`--max-workers 6`, OpenRouter). After the
first ~8 minutes the partial summary recorded 4/57 completed, 0 passed,
4 product_fail, `complete: false`. Early ids include the already-named
floors (`cc0df7`, `c24aa2`) plus `8800a9` and `f0859f` — none qualify
as `resolved`.

The ledger therefore still has **50 `pending_live_rerun`**, **4
`capability_floor`**, **3 `infra_out_of_scope`**, **0 `resolved`**.
That is honest: the post-migration rerun was launched and is not yet
complete. Reconcile again when
`out/agentic/ir-everywhere-57/run_summary.json` has `complete: true`.
