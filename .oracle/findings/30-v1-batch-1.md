# ir-everywhere-30-v1 batch-1 failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v1 (fixed 30-set, loop iteration 1)
Batch: scen30b1 (first 5 of the seeded random 30)
Analysis agent: Flash (read-only, evidence-cited)
OUTCOME baseline: BASELINE (run 1 of the fixed-30 loop)

## Verdicts (terminal attempt, assessment.json passed)

| Scenario | passed | CLASS | ROOT-CAUSE |
|---|---|---|---|
| 3d-3d-model-generation-and-preview-workflow-cc0df7 | (pending at analysis time) | — | — |
| 3d-3d-model-generation-and-retargeting-workflow-f65774 | False | judge_fail | infra-timeout |
| 3d-converts-image-to-3d-model | False | judge_fail | malformed-model-json |
| audio-audio-processing-with-chatterbox-tts-and-vc-b55994 | False | judge_fail | litegraph-counter |
| audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf | False | judge_fail | other (editor-state guardrail) |

Count: 4 judge_fail / 0 incomplete (of the 4 assessed).

## Per-scenario evidence

### 3d-3d-model-generation-and-retargeting-workflow-f65774 — infra-timeout
- assessment.json passed:false; only error = `upstream_failure` (Hivemind statement timeout).
- The model's refusal was accepted as a grounded/safe clarify (`kind='clarify'`) — not a product defect.
- Cross-grounded against ir-everywhere-100 response.json: `ok:true route:adapt graph_unchanged:true no_candidate_reason:no_changes`.
- ROOT-CAUSE: research-starvation (Hivemind timeout), not judge/implement.

### 3d-converts-image-to-3d-model — malformed-model-json
- assessment.json passed:false; `response_ok False` (response could not be parsed), graph unchanged, empty delta; intent unimplemented.
- Co-occurring upstream_failure.
- ROOT-CAUSE: unparseable model JSON → no edit applied.

### audio-audio-processing-with-chatterbox-tts-and-vc-b55994 — litegraph-counter
- assessment.json passed:false; `failure_kind=ValidationError`, `failure_stage=implement` (verbatim).
- Judge hard_diagnostic: "Candidate changed a LiteGraph id counter except for monotonic advancement".
- Cross-grounded: ir-everywhere-100 response.json matches error text verbatim (`no_candidate_reason='implementation_failed'`).
- ROOT-CAUSE: non-monotonic LiteGraph id-counter tampering at implement.

### audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf — other (editor-state guardrail)
- assessment.json passed:false; "candidate graph would destroy editor state and was blocked", empty delta.
- AudioLDM2 intent unimplemented (+upstream_failure co-occurring).
- ROOT-CAUSE: editor-state guardrail block — candidate rejected before application; intent unimplemented.

## Notes
- The rolling relaunch (22:18) wiped response/summary/ui files after the batch-1 assessment capture; failure_kind/stage for chatterbox and retargeting are grounded verbatim, others marked [INFERENCE] where schema details came from the ir-everywhere-100 prior-run cross-reference.
- cc0df7 was still pending at analysis time; will be covered in a later batch doc once its verdict lands.
