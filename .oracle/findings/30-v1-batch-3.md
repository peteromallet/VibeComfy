# ir-everywhere-30-v1 batch-3 failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v1 (fixed 30-set, rolling, 5 workers) — loop iteration 1, batch 3
Analysis agent: Flash (read-only, evidence-cited)
OUTCOME: BASELINE for all 5

## Verdicts (latest attempt, assessment.json verdict:fail)

| Scenario | CLASS | ROOT-CAUSE |
|---|---|---|
| image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5 | judge_fail | unbound-name (batch rejected on stale `cliptextencode_4`) |
| multi-image-to-video-generation-with-2 | judge_fail | snapshot-delta (edited non-serialized `value`, widget_0 unchanged) |
| multi-svd-image-to-video-with-animation-builder-99e2a9 | judge_fail | other (technically-wrong SVD denoise claim) |
| video-animatediff-video-with-ipadapter-and-controlne-4eebf3 | judge_fail | other (hallucinated widget indices + non-existent `overlap` param) |
| video-video-inpainting-with-spline-based-cut-and-dra-485ff2 | judge_fail | queue-gate (candidate_topology_blockers on done()) |

Count: 5 judge_fail / 0 incomplete. Executor ok:true in ALL 5 — failures are product/judge-side, not infra.

## Per-scenario evidence (verbatim issue highlights)

### image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5 — unbound-name
- Agent tried text→video → image→video (add LoadImage, wire vaeencode.pixels) but referenced stale `cliptextencode_4`.
- hard_diagnostic: "Unknown graph name 'cliptextencode_4'. Render the session again if the canvas changed."
- hard_diagnostic: "Batch rejected before commit because it references unbound or stale graph names... Re-render and use only names or uids present in the current graph."
- queue_validate_ok:false; outcome noop; graph_unchanged:true. Executor ok:true (route adapt), judge fail.

### multi-image-to-video-generation-with-2 — snapshot-delta
- Edited Float(uid:218) `value` 25→24.0 (non-serialized field); serialized `widget_0` stayed '25'.
- Executor IR committed (landed_operation_count:1, queue_validate_ok:true, gates pass) but graph_unchanged:true, candidate:null.
- intent_judge PASSED (criteria all True) at IR level; product graph_changed + no_candidate_reason checks FAILED.
- Classic fixture-green/live-red class: IR Δ real, snapshot Δ empty.

### multi-svd-image-to-video-with-animation-builder-99e2a9 — technically-wrong answer (semantic_product)
- semantic_answer failed: "SVD samples all video frames jointly via temporal layers, and denoise=1 is standard for SVD_img2vid_Conditioning" — recommending 0.6–0.8 as flicker fix is materially misleading.
- criteria: grounded=True, relevant=True, correct=False. Route inspect; no edit expected.

### video-animatediff-video-with-ipadapter-and-controlne-4eebf3 — hallucinated widgets (semantic_product)
- Correct culprit (IPAdapterTiled uid:265, correct:true) but hallucinated widget_0/2/3/6 indices + non-existent `overlap` param.
- Actual widgets_values: [1.2, 'ease in-out', 'concat', 0, 1, 0, 'V only'] — no labeled indices, no overlap.
- criteria: grounded=False, relevant=True, correct=True.

### video-video-inpainting-with-spline-based-cut-and-dra-485ff2 — queue-gate
- Set INPAINT_InpaintWithModel.widget_0=42 (uid:18) landed in IR, but done() rejected: candidate_topology_blockers → queue_validate_ok:false → rollback → noop.
- Model ran python()/search probes, failed to clear blocker, ended no_changes. Seed never set (still 534667941392889).

## Cross-batch synthesis so far (round-1 fails analyzed: 14 of 17)
- Edit-side residuals: unbound-name (stale names after canvas re-render), queue-gate topology blockers, snapshot-delta (value vs widget_0), malformed classify JSON, litegraph id-counter, self-loop apply-gate, port-link validation.
- Semantic-product residuals: technically-wrong answers (correct:false), hallucinated widget detail (grounded:false).
- Infra: 4 NO-ASSESSMENT scenarios (2 attempts each, no assessment) — Hivemind/research timeouts likely.
