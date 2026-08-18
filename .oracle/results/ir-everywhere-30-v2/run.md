# Run ir-everywhere-30-v2 — round 2 of the fixed 30-set loop

## Measured state
- **code_commit**: `1328df11` (rc8: bound Hivemind research wall-clock; chain 07e623e4 rc1 → 57b928de rc2 → fdd1dadd rc3 → daf85ef7 rc4 → ba000e06 rc5 → b4d67343 rc6 → 3e894f40 rc7 → 1328df11 rc8)
- **tree_clean**: true (verified `git status --short` = 0 before launch)
- **import-verification**: `PYTHONPATH=$PWD python -c "import vibecomfy"` → sprint tree (verified)
- **manifest**: tests/live_agentic_harness/scen30_manifest.json (same fixed 30 as round 1)
- **run command**: identical to round 1; `--tag ir-everywhere-30-v2 --max-workers 5 --per-scenario-timeout 1200`
- **started**: 00:50:35 | **completed**: ~02:10 (30/30)
- **machine**: quiet (load ~4, no concurrent runs) — first fully-clean measurement of the fixed 30

## Scoreboard (terminal attempt, assessment.json passed)
- **PASS: 15 | FAIL: 15 | total: 30** (runner run_summary.json: passed=15, failed=15, completed=30/30)
- 1 NO-ASSESSMENT infra row (multi-animatediff-video-face-swapping-506ebd, 2 attempts, no assessment)

## Round 1 → Round 2 flip table
- **FLIPPED to PASS (6)**: cc0df7 (FAIL→PASS, rc2/rc5), 3d-converts (NO-ASSESS→PASS, rc8), d20410 (FAIL→PASS, rc4), kolors-d813fe (NO-ASSESS→PASS, rc8), 1c7ad8 (FAIL→PASS, rc3), 03fced (FAIL→PASS, rc2)
- **REGRESSED (4, variance suspects)**: audio-tts-narration (PASS→FAIL), dual-checkpoint-c9df19 (PASS→FAIL), inpainting-1d414c (PASS→FAIL), multi-image-to-video-with-llm (PASS→FAIL)
- **Same (20)**: 10 stayed PASS, 10 stayed FAIL

## Round-2 FAIL list (15) — for Flash batch analysis
3d-3d-model-generation-and-retargeting-f65774; audio-audio-processing-b55994; audio-ltx-c80bbf; audio-tts-narration (regression); image-dual-checkpoint-c9df19 (regression); image-inpainting-1d414c (regression); image-sd3-19d221; image-wan2-2-chroma-a7ecc5; multi-image-to-video-generation-with-2; multi-image-to-video-with-llm (regression); multi-svd-99e2a9; video-animatediff-4eebf3; video-video-inpainting-485ff2; video-video-output-f855de; multi-animatediff-face-swap-506ebd (infra)

## Strategy
Grok round-1 strategy: .oracle/improvement-strategy-30-round1.md (commit 81e54cbf); RCs 1–8 implemented (commits 07e623e4…1328df11)
