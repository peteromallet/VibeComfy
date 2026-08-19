# 30-set ledger — per-scenario status across rounds 1-3

Fixed 30-set: scen30 (seed 20260816). Measured commits: R1=a779d762, R2=1328df11, R3=8d897528.
Verdicts from terminal-attempt assessment.json.passed; NO-ASSESS = infra (no assessment landed).

| scenario | R1 | R2 | R3 | stable? |
|---|---|---|---|---|
| 3d-3d-model-generation-and-preview-workflow-cc0df7 | FAIL | PASS | PASS | varies |
| 3d-3d-model-generation-and-retargeting-workflow-f65774 | NO-ASSESS | FAIL | FAIL | varies |
| 3d-converts-image-to-3d-model | NO-ASSESS | PASS | PASS | varies |
| audio-audio-processing-with-chatterbox-tts-and-vc-b55994 | FAIL | FAIL | FAIL | stable-fail |
| audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf | FAIL | FAIL | FAIL | stable-fail |
| audio-tts-narration-using-indextts-2 | PASS | FAIL | FAIL | varies |
| image-animatediff-video-generation-with-vae-d20410 | FAIL | PASS | PASS | varies |
| image-dual-checkpoint-xl-image-generation-with-refin-c9df19 | PASS | FAIL | PASS | varies |
| image-gemini-prompt-splitter-and-text-display-workfl-caae97 | PASS | PASS | FAIL | varies |
| image-inpainting-with-differential-diffusion-and-rea-1d414c | PASS | FAIL | PASS | varies |
| image-kolors-image-generation-with-segs-detailer-and-d813fe | NO-ASSESS | PASS | FAIL | varies |
| image-sd3-image-generation-with-controlnet-19d221 | FAIL | FAIL | PASS | varies |
| image-two-stage-qwen-image-generation | PASS | PASS | PASS | stable-pass |
| image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5 | FAIL | FAIL | FAIL | stable-fail |
| multi-3d-gaussian-splatting-from-video-with-hunyuan-432652 | PASS | PASS | FAIL | varies |
| multi-3d-preview-and-image-output-workflow-d93baf | PASS | PASS | PASS | stable-pass |
| multi-animatediff-video-face-swapping-with-deflicker-506ebd | NO-ASSESS | NO-ASSESS | NO-ASSESS | stable-infra |
| multi-animatediff-video-generation-with-controlnet-a7e2af | PASS | PASS | PASS | stable-pass |
| multi-image-to-video-generation-with-2 | FAIL | FAIL | FAIL | stable-fail |
| multi-image-to-video-with-llm | PASS | FAIL | FAIL | varies |
| multi-svd-image-to-video-with-animation-builder-99e2a9 | FAIL | FAIL | FAIL | stable-fail |
| video-animatediff-video-with-ipadapter-and-controlne-4eebf3 | FAIL | FAIL | FAIL | stable-fail |
| video-seedvr2-video-upscaling-workflow-052e59 | PASS | PASS | FAIL | varies |
| video-video-inpainting-with-spline-based-cut-and-dra-485ff2 | FAIL | FAIL | PASS | varies |
| video-video-loading-and-saving-workflow-1c7ad8 | FAIL | PASS | FAIL | varies |
| video-video-output-workflow-f855de | FAIL | FAIL | FAIL | stable-fail |
| video-wan2-2-text-to-video-with-dual-unet-and-model-03fced | FAIL | PASS | PASS | varies |
| video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3 | PASS | PASS | PASS | stable-pass |
| video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a | PASS | PASS | PASS | stable-pass |
| video-wanvideo-text-to-video-generation-71f825 | PASS | PASS | FAIL | varies |

Summary: R1=13/30, R2=15/30, R3=13/30.
Stable-pass: 5 of 30. Durable flips: cc0df7, 3d-converts, d20410, 03fced (R2+), 19d221, 1d414c, 485ff2 (R3).
Variance rows (PASS/FAIL wobble): gemini-prompt, kolors, gaussian-splat, seedvr2, 1c7ad8, wanvideo, multi-i2v-llm, indextts-2, c9df19.
Stable-infra: multi-animatediff-face-swap-506ebd (never starts, all 3 rounds).
