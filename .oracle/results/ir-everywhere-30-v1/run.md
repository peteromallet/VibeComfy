# Run ir-everywhere-30-v1 — round 1 of the fixed 30-set loop

## Measured state
- **code_commit**: `a779d762` (manifest: split scen30 into 6 fixed batches; scen30 corpus + manifest from `8f2feb9c`)
- **tree_clean**: true (verified `git status --short` = 0 before launch)
- **import-verification**: `PYTHONPATH=$PWD python -c "import vibecomfy"` → `/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy/vibecomfy/__init__.py` (sprint tree, not main)
- **manifest**: tests/live_agentic_harness/scen30_manifest.json (30 scenarios, seeded random 20260816, hashes verified by discover_manifest_scenarios)
- **run command**: `python -m tests.live_agentic_harness.runner --tag ir-everywhere-30-v1 --scenarios-dir tests/live_agentic_harness/scen30 --manifest tests/live_agentic_harness/scen30_manifest.json --transport openrouter --max-workers 5 --per-scenario-timeout 1200 --json`
- **started**: 22:18:00 | **completed**: ~23:30 (30/30, run_summary.json final)
- **machine**: rolling 5-worker pool; load peaked 300 (concurrent with user's one-step-3 run) then quieted to ~4.5

## Scoreboard (terminal attempt, assessment.json passed)
- **PASS: 13 | FAIL: 13 | NO-ASSESSMENT (infra): 4 | total: 30**
- runner run_summary.json: passed=13, failed=17, completed=30/30 (NO-ASSESSMENT counted in failed)

## PASS (13)
audio-tts-narration-using-indextts-2; image-dual-checkpoint-xl-image-generation-with-refin-c9df19; image-gemini-prompt-splitter-and-text-display-workfl-caae97; image-inpainting-with-differential-diffusion-and-rea-1d414c; image-two-stage-qwen-image-generation; multi-3d-gaussian-splatting-from-video-with-hunyuan-432652; multi-3d-preview-and-image-output-workflow-d93baf; multi-animatediff-video-generation-with-controlnet-a7e2af; multi-image-to-video-with-llm; video-seedvr2-video-upscaling-workflow-052e59; video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3; video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a; video-wanvideo-text-to-video-generation-71f825

## FAIL (13)
3d-3d-model-generation-and-preview-workflow-cc0df7 (self-loop apply-gate); audio-audio-processing-with-chatterbox-tts-and-vc-b55994 (orphaned wiring + schema-less node); audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf (safe-refusal AudioLDM2); image-animatediff-video-generation-with-vae-d20410 (classifier invalid JSON); image-sd3-image-generation-with-controlnet-19d221 (Missing stable link to port); image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5; multi-image-to-video-generation-with-2; multi-svd-image-to-video-with-animation-builder-99e2a9; video-animatediff-video-with-ipadapter-and-controlne-4eebf3; video-video-inpainting-with-spline-based-cut-and-dra-485ff2; video-video-loading-and-saving-workflow-1c7ad8; video-video-output-workflow-f855de; video-wan2-2-text-to-video-with-dual-unet-and-model-03fced

## NO-ASSESSMENT (4, infra)
3d-3d-model-generation-and-retargeting-workflow-f65774; 3d-converts-image-to-3d-model; image-kolors-image-generation-with-segs-detailer-and-d813fe; multi-animatediff-video-face-swapping-with-deflicker-506ebd

## Analysis status
- batch-1 Flash doc: `.oracle/findings/30-v1-batch-1.md` (commit bd49d43d) — 4 fails
- batch-2 Flash doc: `.oracle/findings/30-v1-batch-2.md` (commit 5a4edf68) — 5 fails
- remaining fails (8) + NO-ASSESSMENT (4): pending Flash analysis (batch-3)
