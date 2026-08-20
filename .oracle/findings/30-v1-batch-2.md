# ir-everywhere-30-v1 batch-2 failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v1 (fixed 30-set, rolling, 5 workers) — loop iteration 1
Batch: 2 (5 scenarios, all assessed)
Analysis agent: Flash (read-only, evidence-cited)
OUTCOME: BASELINE for all (run 1 of the fixed-30 loop)

## Verdicts (latest attempt, assessment.json passed)

| Scenario | CLASS | ROOT-CAUSE |
|---|---|---|
| 3d-3d-model-generation-and-preview-workflow-cc0df7 | judge_fail | other (self-loop in canonical product, apply-gate refused) |
| audio-audio-processing-with-chatterbox-tts-and-vc-b55994 | judge_fail | other (orphaned wiring + schema-less node blocking queue gate) |
| audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf | judge_fail | safe-refusal (AudioLDM2 unavailable) |
| image-animatediff-video-generation-with-vae-d20410 | judge_fail | malformed-model-json (classifier invalid JSON) |
| image-sd3-image-generation-with-controlnet-19d221 | judge_fail | other (implement-stage 'Missing stable link to port') |

Count: 5 judge_fail / 0 incomplete.

## Per-scenario evidence

### 3d-3d-model-generation-and-preview-workflow-cc0df7 — self-loop apply-gate refusal
- assessment.json passed:false, 1 issue: intent_judge self-loop; apply-gate refused the edit.
- response.json: executor ok:true, applyable, graph_unchanged:false, route revise — executor CLAIMED success but the judge found a self-loop in the canonical product.
- ROOT-CAUSE: edit produced a new self-loop; apply-gate correctly refused; executor/verdict discrepancy.

### audio-audio-processing-with-chatterbox-tts-and-vc-b55994 — orphaned wiring + schema-less node
- assessment.json passed:false, 3 issues: gates queue_validate_ok, intent_judge orphaned wiring, hard_diagnostic schema-less node 425.
- response.json: executor ok:true, apply eligible but queue_blocked_warning, route revise.
- ROOT-CAUSE: orphaned/broken wiring + schema-less node (425) blocking the queue gate.

### audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf — safe-refusal
- assessment.json passed:false, 5 issues: graph_changed, no_candidate_reason, intent_judge, hard_diagnostic litegraph-counter, upstream_failure (Hivemind timeout).
- response.json (attempt_2): executor ok:true, graph_unchanged:true, no_candidate_reason=no_changes, route adapt.
- ROOT-CAUSE: AudioLDM2 unavailable in schema — agent safe-refused (no_changes). Secondary: LiteGraph id-counter + Hivemind timeout.

### image-animatediff-video-generation-with-vae-d20410 — malformed-model-json
- assessment.json passed:false, 3 issues: response_ok (classifier invalid JSON), graph_changed, intent_judge zero Δ.
- response.json: executor ok:false, ValidationError stage classify, missing_required_fields.
- ROOT-CAUSE: classifier reply missing required fields / not valid JSON at classify stage → no graph change.

### image-sd3-image-generation-with-controlnet-19d221 — implement-stage port link failure
- assessment.json passed:false, 3 issues: response_ok (validation errors), graph_changed, intent_judge empty Δ (widget still 0.6).
- response.json: executor ok:false, ValidationError stage implement, no_candidate_reason=implementation_failed.
- implementation_result.json: 'Missing stable link to port'; node 60 strength never changed 0.6→0.5.
- ROOT-CAUSE: implement-stage validation failure; graph unchanged.

## Cross-batch observations
- b55994 and c80bbf were also in batch-1 analysis (static batch run); the rolling re-run produced fresh verdicts — same scenarios, same residual classes (litegraph-counter persists for c80bbf).
- cc0df7 flips between attempt-level detail: here self-loop apply-gate refusal; earlier runs showed fabricated-refusal (fixed by RC rounds) — this is a NEW-MODE residual, not the old fix failing.
