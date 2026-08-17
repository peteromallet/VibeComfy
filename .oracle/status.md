# Sprint status — IR-everywhere migration

Updated: 2026-08-17 (L-R3 ledger reconcile against finished v3)

## Phase: L-R3 complete — v3 reconciled

Worktree: `/tmp/vc-sol3` @ `sol3-improvements`. Venv: `PYTHONPATH=$PWD` + `reigh-workspace/vibecomfy/.venv`.

Sprint tree `vibecomfy/` is frozen for the 12x evidence gatherer. Do not edit it.

### v3 finished artifact

`/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy/out/agentic/ir-everywhere-57-v3/run_summary.json`

- `complete: true`
- `final_score: 16/57`
- judge verdicts from `attempts/<id>/attempt_1/<id>/assessment.json` `passed` (not executor `ok`)
- 16 passed / 8 infra_timeout / 33 product_fail

### Ledger after reconcile

| status | count | note |
|---|---|---|
| resolved | 16 | v3 `assessment.json` `passed=true`; mechanism = v3 live rerun on ir-everywhere branch |
| capability_floor | 3 | Class D `cc0df7`/`90a1d5` (`b09_reducer.py`) + variance `multi-wan-vace-video-retargeting-driven` (`variance.md`); v3 still product_fail |
| infra_out_of_scope | 8 | v3 `failure_class=infra_timeout` |
| pending_live_rerun | 30 | remaining product_fail, including `video-video-combine-with-image-loading-5b31ce` (research_attempt=never + refusal; not a named floor) |

`5b31ce` stays `pending_live_rerun`. `docs/failure-analysis/other.md` is an ambiguous bucket; v3-batch-5 confirms product_fail, not Class-D / variance evidence.

### 16 resolved ids

- `audio-acestep-audio-generation-with-detail-daemon-f0859f`
- `image-dual-checkpoint-xl-image-generation-with-refin-c9df19`
- `image-gemini-prompt-splitter-and-text-display-workfl-caae97`
- `image-image-processing-with-sharpening-film-grain-an-9aa0f1`
- `image-qwen-image-inpainting-with-controlnet-09fc64`
- `live-graph-explanation-smoke`
- `multi-3d-gaussian-splatting-from-video-with-hunyuan-432652`
- `multi-animatediff-video-generation-with-controlnet-a7e2af`
- `multi-flux2-image-and-video-generation-with-outpaint-435de2`
- `multi-svd-image-to-video-with-animation-builder-99e2a9`
- `video-animatediff-video-to-video-with-controlnet-and-3c978e`
- `video-animatediff-video-with-controlnet-and-depth-89b02a`
- `video-inpaint-and-video-composition-with-spline-path-0c2716`
- `video-video-loading-and-saving-workflow-1c7ad8`
- `video-video-output-workflow-f855de`
- `video-wanvideo-text-to-video-generation-71f825`

## Earlier sprint notes

- Review-3 residuals (C2-R3/C3-R3/B1-R3/B2-R3/B3-R3) landed at `d66e6e1b`; L-R3 was deferred until v3 completed.
- Spike: **GO**. Batches 1–16 landed. Review 1 C1/L2 confirmed FIXED.
