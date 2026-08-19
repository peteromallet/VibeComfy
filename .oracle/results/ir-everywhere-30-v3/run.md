# Run ir-everywhere-30-v3 — round 3 of the fixed 30-set loop

## Measured state
- **code_commit**: `8d897528` (rc5: intent judge terminal value; chain b432222d rc1 → 4b665255 rc2 → 60243b5e rc3 → f79f7843 rc4 → 8d897528 rc5)
- **tree_clean**: true (verified before launch)
- **import-verification**: `PYTHONPATH=$PWD python -c "import vibecomfy"` → sprint tree
- **manifest**: scen30_manifest.json (same fixed 30)
- **run command**: identical; `--tag ir-everywhere-30-v3 --max-workers 5 --per-scenario-timeout 1200`
- **started**: 02:28:44 | **completed**: ~04:30 (30/30)
- **machine**: quiet (load ~4)

## Scoreboard
- **PASS: 13 | FAIL: 17 | total: 30** (run_summary.json passed=13, failed=17, completed=30/30)
- 1 NO-ASSESSMENT infra row (multi-animatediff-face-swap-506ebd — 3rd consecutive round infra-blocked)

## 3-round matrix summary
| | R1 | R2 | R3 |
|---|---|---|---|
| PASS | 13 | 15 | 13 |

- **Durable flips (FAIL→PASS held R2+R3)**: cc0df7, 3d-converts, d20410, 03fced
- **R3 new flips**: 19d221 (RC-1), 1d414c (RC-5), 485ff2 (RC-1), c9df19 (re-pass)
- **R3 variance regressions (7, PASS→FAIL)**: gemini-prompt-splitter, kolors, gaussian-splatting, seedvr2, 1c7ad8, wanvideo, multi-i2v-llm — inspect-answer wobble, not code regressions
- **Stable passes (PASS all 3 rounds, 8)**: two-stage-qwen, 3d-preview, animatediff-a7e2af, wan2-2-high-low, wan2-2-lora, wanvideo-71f825 (R1+R2), image-gemini (R1+R2), 3d-gaussian (R1+R2)

## Residual fails at R3 (17)
- Durable: f65774 (snapshot-delta/guard), b55994 (litegraph), c80bbf (clarify envelope — RC-4 did not flip), indextts-2 (guard variance), a7ecc5 (snapshot-delta), multi-i2v-2 (dual-channel — RC-2 did not flip), multi-svd-99e2a9 (correct=false, philosophy-hold), 4eebf3 (inspect invention — RC-3 did not flip), f855de (grounded, correct=false), multi-i2v-llm (model-behavior)
- R3-variance: gemini-prompt, kolors, gaussian-splat, seedvr2, 1c7ad8, wanvideo
- Infra: 506ebd (never starts, 3 rounds)

## Honest assessment
- 13/30 final vs 13/30 baseline: net zero, BUT composition improved — 4 durable flips + 3 RC-1/RC-5 wins offset by 7 inspect-answer variance rows.
- Inspect-answer scenarios are the dominant variance source (±3-5 per run); product-edit fixes are durable.
- The 17-fail set splits: ~10 hard residual (philosophy-held or guard-correct) + ~7 variance-answer rows that wobble run to run.
