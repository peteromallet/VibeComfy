# Megado run-2 failure investigation — consolidated findings (live-elegance-r2, main @ 37631ecb)

100 scenarios, flash-pinned (openrouter:deepseek/deepseek-v4-flash), 12 workers, 900s timeout.
Run 2: 40/100 pass. Run 1 (pre-megado): 53/100. Historical recorded baseline: 38/100.
ONE regression already found + FIXED (commit 37631ecb): Batch B's normalize_agent_edit_graph hard-routed non-list graphs to from_envelope; API-format prompt dicts (node_id->node, no "nodes" key) raised "serialized vibe envelope 'nodes' must be a mapping of node objects". 19 scenarios killed at ingest. Fix: route API-shaped dicts to from_api. Re-run of those 19 in flight (tag live-19-fix).

Remaining 41 failures → 12 root-cause clusters (4-scout investigation, evidence-cited):

## Cluster A — worker subprocess pipe hang (4, ALL infra_timeout)
audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676, multi-animatediff-video-face-swapping-with-deflicker-506ebd, multi-image-to-video-with-upscaling-and-color-matchi-359848, video-hunyuanvideo-image-to-video-generation-with-en-ff076a
- Evidence: killed at exactly 900s (per-scenario timeout), agent_exercised=false, stderr_tail ends at `runtime.worker_subprocess.start`; no worker_result ever written. _TURN_TIMEOUT_SECONDS=180 (runtime.py:63) never fires.
- Mechanism [INFERENCE]: subprocess.run(timeout=180) in _run_worker_once blocks in communicate() because a grandchild (DeepSeek HTTP call / web_search tool subprocess) inherits the captured stdout/stderr pipe and holds it open; timeout can't kill the grandchild → the 180s turn timeout doesn't apply, whole scenario burns the 900s runner budget.
- 506ebd also shows GitHub search 422 (GroundingDinoSAMSegment) — web_search 422 may loop.
- Fix hint: kill worker process GROUP / close inherited pipes so subprocess.run(timeout=180) terminates; surface 180s turn timeout as infra error; guard web_search 422 from looping.
- NOTE: apply=false diagnose scenarios route through the same worker subprocess (ff076a).

## Cluster B — IterationLimitMalformedJSON (5)
multi-3d-gaussian-splatting-from-video-with-hunyuan-432652 (classify), multi-ai-video-upscaling-with-detail-daemon-sampler-673197 (reply), multi-animated-image-to-video-with-svd-and-lora-4ed6d9 (reply), 3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2 (classify), video-wan-video-generation-with-vace-and-multi-outpu-d1caec (reply)
- Evidence: model_response.json finish_reason='length', parse_reason='malformed_json', completion_tokens=0, raw="I reached the iteration limit and couldn't generate a summary."
- Mechanism: deepseek-v4-flash agentic loop hits iteration/token limit and emits literal prose instead of the required JSON. Phases hit: classify AND reply.
- Fix hint: raise iteration/token budget for the hermes agent loop; make iteration-limit output retryable/fallback in classify + reply adapters.

## Cluster C — ResearchScenarioForcedThroughEditGate (4)
image-gemini-prompt-splitter-and-text-display-workfl-caae97, image-image-processing-with-sharpening-film-grain-an-9aa0f1, image-qwen-image-inpainting-with-controlnet-09fc64, multi-animatediff-video-generation-with-controlnet-a7e2af
- Evidence: classification.json intent=research implement=false (scenario defs apply=false expect_graph_changed=false judge=semantic_answer) BUT implementation_result.json failure_kind=MalformedModelJSON stage=implement "Agent response does not contain a ```batch fenced block."
- Mechanism: harness routes apply:false research scenarios through the EDIT implement gate (which demands a ```batch fence) instead of the semantic_answer reply path.
- Fix hint: harness routing — apply:false research scenarios must NOT run the edit batch-block gate; emit research answer via reply path.

## Cluster D — SchemaGapRefusal (4)
3d-3d-model-generation-and-preview-workflow-cc0df7, 3d-3d-model-generation-and-retargeting-workflow-f65774, 3d-3d-model-generation-and-rigging-from-image-352066, audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf
- Evidence: agent refusal text: "no Rodin3D_Fusion node exists in the current authoring schema", "No procedural PBR material generator class is available", "Tripo's rig/retarget nodes don't expose a joint-orientation parameter", "AudioLDM2 is not an authorable node type here". Graph unchanged.
- Mechanism: requested node class/field absent from local authoring schema; agent defensibly refuses.
- Fix hint: add the missing node/field signatures to the authoring schema, or sanction a reroute/fallback splice.

## Cluster E — EditBatchBlockMissing / MalformedBatchBlock (6)
audio-acestep-audio-generation-with-detail-daemon-f0859f, hotshot-16-frames-agent-edit, image-flux-image-inpainting-and-compositing-with-con-00444a, image-image-comparison-and-enhancement-with-florence-007018, multi-deforum-stable-diffusion-animation-with-ip-ada-78afac, video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9 (this one apply=false routed to adapt)
- Evidence: failure_kind=MalformedModelJSON, "Agent response does not contain a ```batch fenced block. Include exactly one ```batch code block with your edit statements." (provider.py:348 extract_batch_fence)
- Mechanism: model omitted the single ```batch fence on a real edit turn (or a non-edit query was routed to edit).
- Fix hint: retry/regenerate when the edit turn omits the fence; strengthen batch-repl prompt; route non-edit intents away from edit gate (see C).

## Cluster F — malformed_json_reply (3)
video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9, video-wanvideo-text-to-video-generation-71f825, video-wan-video-generation-with-vace-and-multi-outpu-d1caec (also in B)
- Evidence: phase=reply, parse_reason='malformed_json', finish_reason='stop', completion_tokens≈810, raw is SUBSTANTIVE PROSE not wrapped in {reply:...} (parse_reply_response prompts.py:897; _REPLY_SYSTEM prompts.py:539)
- Mechanism: reply phase demands strict JSON {reply:...}; flash returns good prose, fails parse → product_fail, graph unchanged.
- Fix hint: lenient prose fallback for the reply phase, or prompt compliance.

## Cluster G — NoOpEdit (1)
image-kolors-image-generation-with-segs-detailer-and-d813fe
- Evidence: graph_changed error "Expected graph change but response.graph_unchanged is True"; first attempt iteration-limit missing_batch_fence, retry ran search() with landed_op_count=0; all gates failed.
- Fix hint: ensure edit turn lands graph ops; retry on graph_unchanged when expect_graph_changed.

## Cluster H — SemanticEditMismatch (1)
image-image-to-image-with-stable-zero123-and-backgro-def5b5
- Evidence: executor success but intent_judge error: BasicScheduler steps 8->30 contradicts "speed up" intent; value_semantically_matches_intent=False.
- Mechanism: agent changed value in the wrong direction vs stated intent.
- Fix hint: edit turns should reason about direction; judge flag/retry on semantic mismatch (harness-level).

## Cluster I — TurnBudgetExhausted (1)  ← USER FLAGGED
3d-3d-model-generation-and-rigging-workflow-90a1d5
- Evidence: code=batch_budget_exhausted but budget_state={remaining_batches:45, remaining_consecutive_errors:2, consecutive_errors:1}, turn_count=5, "Stopped after 5 turn(s); 45 turn(s) remaining."
- Mechanism: loop stopped at turn 5 despite max_batches=50 (state.batch_max_turns default 50, _frag_state.py:228; edit_batch_repl.py:1463 max_batches from batch_max_turns) and max_consecutive_errors=3. NO loop condition fires at 5 — mislabeled/mis-wired early stop. The user wants the effective per-request turn limit RAISED (suggestion: 50, configurable up to 250).
- Fix hint: find the real 5-turn stop (request payload carries max_batches? harness default? provider budget n=12?) and raise it; fix the budget-exhausted mislabel (should not report exhausted with 45 remaining).

## Cluster J — ValidationError (1)
audio-acestep-audio-generation-workflow-2a31ec
- Evidence: failure_kind=ValidationError "The edited workflow has validation errors and was not applied." (query: swap checkpoint to acestep-sft-v2.safetensors)
- Fix hint: improve validation feedback so model-file swaps validate; resolve checkpoint path.

## Cluster K — AdviceQueryRefusal (1)
image-dual-checkpoint-xl-image-generation-with-refin-c9df19
- Evidence: research/advice query (apply=false) routed to edit; agent refused: "I could not produce a safe graph edit from the available workflow precedent and current authoring surface. The graph is unchanged."
- Fix hint: same as C — route non-edit intents to explain/advice path.

## Cluster L — ClassifyOutputTruncation (covered in B)
(3d-3d-inpainting...c24aa2, multi-3d-gaussian...432652)

## Overlap notes
- Clusters C + K + E(video-wan2-2-i2v) are the SAME harness-routing theme: apply:false scenarios forced through the edit batch-fence gate. Count together: 4 (C) + 1 (K) + 1 (E-video-wan2-2-i2v) = 6.
- Clusters B + F are the SAME model-format theme (flash returns prose/iteration-stub where strict JSON is demanded): 5 + 3 = 8, plus some overlap (vace-d1caec in both).
- A is infra (4). D is schema/product gap (4). E(real edit) = 5. G,H,J = 3.

## Priorities (orchestrator's read — grok decides)
1. A (4 infra, 900s each — most expensive failures)
2. C/K routing (6) + F lenient reply (3) + B iteration budget (5) — same "model vs harness contract" family
3. I turn limit (user-flagged)
4. D schema gaps (4 — product work, not harness)
5. E fence retry (5), G no-op (1), H semantic (1), J validation (1)

## Turn-limit context (user: raise it)
- state.batch_max_turns: int = 50 (_frag_state.py:228); edit_batch_repl.py:1463 max_batches = max(1, int(state.batch_max_turns or 1)); _frag_entrypoint.py:282 overrides from payload["max_batches"] when present.
- Harness request.json for 90a1d5: max_batches=null, max_consecutive_errors=null (so default 50 applies — yet it stopped at 5!).
- provider.py: `n: int = 12` budget prompt ("Budget: N turn(s) remaining out of 12") — the MODEL-SEEN budget is 12; the loop's own budget is 50. The 5-turn stop is neither 12 nor 50 — a third cap exists or the loop mis-stops.
- User direction: set the limit to ~50 (configurable; outer bound 250), and fix the mislabel.
