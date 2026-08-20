# ir-everywhere-30-v1 batch-4 failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v1 (fixed 30-set, rolling, 5 workers) — loop iteration 1, batch 4
Analysis agent: Flash (read-only, evidence-cited)
OUTCOME: BASELINE for all 5

## Verdicts (latest attempt)

| Scenario | CLASS | ROOT-CAUSE |
|---|---|---|
| video-video-loading-and-saving-workflow-1c7ad8 | judge_fail | ungrounded-refusal (hallucinated UUID composite semantics) |
| video-video-output-workflow-f855de | judge_fail | ungrounded-refusal (8-bit VAE / codec=auto fabrication) |
| video-wan2-2-text-to-video-with-dual-unet-and-model-03fced | judge_fail | queue-gate (steps 20 vs 25 + post-edit validation rollback) |
| 3d-3d-model-generation-and-retargeting-workflow-f65774 | incomplete | infra-timeout (2×1200s kills; snapshot-delta RefusedEmit in attempt_1) |
| 3d-converts-image-to-3d-model | incomplete | infra-timeout (2×1200s kills, killed before first attempt) |

Count: 3 judge_fail / 2 incomplete.

## Per-scenario evidence (verbatim highlights)

### video-video-loading-and-saving-workflow-1c7ad8 — ungrounded answer (semantic_product)
- semantic_answer failed: calls three UUID nodes 'identical' though type fields differ; guesses switch=True 'composites' image onto frames (unsupported — image input labeled 'first frame').
- criteria: grounded=False, relevant=True, correct=False. Route inspect, executor ok:true, 1 attempt, 102.8s.

### video-video-output-workflow-f855de — ungrounded answer (semantic_product)
- semantic_answer failed: claims 'Standard 8-bit VAEs' + SaveVideo 'codec=auto' lossy H.264/H.265 — evidence shows only shared VAE connection + widgets ['output','auto','auto']; derives 8x cascade from display titles.
- criteria: grounded=False, relevant=True, correct=False. 1 attempt, 186.8s.

### video-wan2-2-text-to-video-with-dual-unet-and-model-03fced — queue-gate (edit)
- 5 issues: graph_changed, no_candidate_reason, outcome_kind, gates (queue_validate_ok failed), intent_judge.
- intent_judge: Δ replaces both samplers but sets steps=20 (not requested 25) on uids 57/58; upsert_link structural discrepancy; criteria correct_parameter_changed=False.
- implementation_result.json: "Two step changes were applied... (nodes 57 and 58 set to 25), but post-edit validation failed, resulting in a noop outcome."
- 6 model calls / 30,560 tokens; 262.3s.

### 3d-3d-model-generation-and-retargeting-workflow-f65774 — infra-timeout ×2
- attempt_1: 1200s kill, killed_before_first_attempt, retryable_infra:false. Stale artifacts: research.json (exhausted→refine, 1 thin hivemind search, 10 irrelevant MiniMax-H3 hits); implementation_result.json RefusedEmit: "guard_emit refused re-emit: 2 uid-matched node(s) changed outside snapshot_delta" (uids 23,33).
- attempt_2: 1200s kill, retryable_infra:true, killed before first attempt, no assessment.json.
- ROOT: infra + snapshot-delta guard friction in attempt_1.

### 3d-converts-image-to-3d-model — infra-timeout ×2
- attempt_1: 1200s kill, killed_before_first_attempt:true, no model attempts.
- attempt_2: 1200s kill, retryable_infra:true; stderr_tail shows batch_repl/text worker (route hermes, deepseek-v4-flash) running when killed.
- ROOT: never advanced past worker launch; no assessment.json either attempt.

## Round-1 synthesis complete (17 fails analyzed across batches 1–4)
- Edit-side: unbound-name, queue-gate (topology blockers + wrong-param), snapshot-delta (value vs widget_0), malformed classify JSON, litegraph id-counter, self-loop apply-gate, port-link validation.
- Semantic-product: ungrounded answers (composite/VAE/codec fabrication), technically-wrong answers (SVD denoise), hallucinated widget indices.
- Infra: 4 scenarios × 1200s kills (f65774, 3d-converts, kolors, animatediff-face-swap) — Hivemind research starvation + snapshot-delta guard friction.
