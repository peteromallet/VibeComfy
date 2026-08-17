# Sprint status — IR-everywhere migration

Updated: 2026-08-17 (sol review-3 fix)

## Phase: review-3 close on sol3-improvements

Worktree: `/tmp/vc-sol3` @ `sol3-improvements`. Venv: `PYTHONPATH=$PWD` + `reigh-workspace/vibecomfy/.venv`.

Sprint tree `vibecomfy/` is frozen for the v3 57-run. Do not edit it.

### Ledger (L-R3)

v3 (`ir-everywhere-57-v3`) was **not complete** at this pass (`run_summary.partial.json` only). No id is `resolved`.

Honest interim counts:

| status | count | ids |
|---|---|---|
| capability_floor | 3 | `cc0df7`, `90a1d5`, `multi-wan-vace-video-retargeting-driven` |
| infra_out_of_scope | 3 | `c24aa2`, `f65774`, `00444a` |
| pending_live_rerun | 51 | remaining, including `video-video-combine-with-image-loading-5b31ce` |
| resolved | 0 | — |

`5b31ce` was prematurely `capability_floor`. `docs/failure-analysis/other.md` is an ambiguous bucket, not named Class-D / variance evidence. Reclassified `pending_live_rerun` until a finished v3 artifact names a floor.

Reconcile again when `out/agentic/ir-everywhere-57-v3/run_summary.json` has `complete: true`.
