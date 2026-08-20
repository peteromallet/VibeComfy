# ir-everywhere-30-v2 batch-B failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v2 (round 2 of fixed-30 loop, quiet machine, RC1-8 applied)
Batch: B (5 scenarios)

## Verdicts

| Scenario | CLASS | ROOT-CAUSE | OUTCOME vs round 1 |
|---|---|---|---|
| image-inpainting-1d414c | judge_fail | intent_judge flags feathering 16 as decrease from prior 40 | **VARIANCE** — candidate graph hash 0e7610 byte-IDENTICAL to round-1 PASS; judge strictness flipped |
| image-sd3-19d221 | judge_fail | schema-less node queue-gate (queue_validate_ok + hard_diagnostic) | SAME-ROOTCAUSE |
| image-wan2-2-chroma-a7ecc5 | judge_fail | RefusedEmit snapshot-delta guard (nodes 10,24,26,29) | SAME-ROOTCAUSE |
| multi-image-to-video-generation-with-2 | judge_fail | no_changes / delta-replay-mismatch (graph_unchanged, no_candidate=no_changes) | SAME-ROOTCAUSE |
| multi-image-to-video-with-llm | judge_fail | cleared node 182 widgets, judged not addressing intent | **REGRESSION-REAL** — round-1 PASS rewired Florence2Run 176 → raw LoadImage 185; round-2 agent made a different, judged-wrong edit |

Count: 5 judge_fail / 0 incomplete.

## Evidence notes
- 1d414c: R2 fail assessment flags feathering 16 vs R1 pass same delta; response.json candidate hash 0e7610 identical to R1; final.ui.json node 56 widgets_values [32,32,32,32,16]. Judge strictness flipped on identical product — VARIANCE.
- 19d221: gates queue_validate_ok false + hard_diagnostic schema-less node; response apply_eligibility queue_blocked_warning; edit_intent passed — product blocked pre-apply.
- a7ecc5: implementation_result RefusedEmit snapshot-delta (nodes 10,24,26,29).
- multi-i2v-2: response graph_unchanged=true no_candidate_reason=no_changes — delta replay mismatch.
- multi-i2v-llm: R2 reply cleared StringFunction node 182 widget_4/widget_5 (judged wrong); R1 PASS rewired Florence2Run 176 to raw LoadImage 185. Only REGRESSION-REAL of the four regressions.

## Regression synthesis (4 round-1 PASS → round-2 FAIL)
- VARIANCE ×3: indextts-2 (guard correctly refused new shape), c9df19 (judge strictness on substantively-correct answer), 1d414c (byte-identical candidate, judge flip)
- REGRESSION-REAL ×1: multi-image-to-video-with-llm (agent chose wrong edit)
- Net real regression: 1. Effective round-2 quality ≈ 16-17/30 (3 variance rows are judge/luck, not code)
