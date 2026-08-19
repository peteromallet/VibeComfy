# ir-everywhere-30-v3 batch-2 failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v3 (round 3, RC1-5 applied @ 8d897528)
Batch: 2 of 3 (5 scenarios)
Analysis agent: Flash (read-only, evidence-cited)

## Verdicts (latest attempt, vs round 2)

| Scenario | CLASS | ROOT-CAUSE | OUTCOME vs R2 |
|---|---|---|---|
| multi-3d-gaussian-splatting-432652 | judge_fail | infra-timeout at reply stage (TimeoutError, research route, empty research) | REGRESSION-REAL (R2 PASS grounded HWMInference answer) |
| multi-animatediff-face-swap-506ebd | incomplete | infra-timeout ×2, killed_before_first_attempt, emit_ready.py arity-disagreement stderr | SAME-ROOTCAUSE (identical 3 rounds) |
| multi-image-to-video-with-llm | judge_fail | batch-repl-queue-fail-closed (Unrepresentable, dunder_name_not_allowed, 4 turns/3 errors, nothing landed) | NEW-FAIL-MODE (R2 landed wrong-param Δ; R3 landed nothing) |
| multi-svd-99e2a9 | judge_fail | answer-misattribution (hallucinated link numbers: init_image=19→actual 24, passthrough=21→actual 8) | VARIANCE (R2: different claim, seed/randomize correct=False) |
| video-animatediff-4eebf3 | judge_fail | answer-misattribution (hallucinated widget mapping node 265: widgets [1.2,ease-in-out,concat,0,1,0,V only], links 35/36/34 not 48/49/50) | SAME-ROOTCAUSE (identical node-265 hallucination) |

Count: 4 judge_fail / 1 incomplete.

## Notes
- 432652: research route, graph unchanged, research empty → reply-stage timeout. R2 passed with grounded answer.
- 506ebd: only agentic_summary.json in both attempts; no assessment ever. Same infra signature all 3 rounds.
- multi-i2v-llm: batch edit surface hard-refused (dunder_name_not_allowed) — the edit tool rejected the model's batch before commit.
- 99e2a9: NEW failure flavor — link-number hallucination (grounded=False now vs R2's grounded=True/correct=False).
- 4eebf3: identical node-265 widget hallucination as R2 — RC-3 lens fix did NOT reach this model turn.
