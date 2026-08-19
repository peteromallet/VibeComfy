# ir-everywhere-30-v3 batch-3 failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v3 (round 3, RC1-5 applied @ 8d897528)
Batch: 3 of 3 (2 scenarios)
Analysis agent: Flash (read-only, evidence-cited)

## Verdicts (latest attempt, vs round 2)

| Scenario | CLASS | ROOT-CAUSE | OUTCOME vs R2 |
|---|---|---|---|
| video-seedvr2-052e59 | judge_fail | answer-misattribution (ignored bypass flags nodes 17/19 mode=4 + link-over-widget precedence link 10 that R2 handled correctly) | REGRESSION-REAL (R2 PASS) |
| video-video-output-f855de | judge_fail | answer-misattribution (misread node 5012 as disconnected when links 1/2/5/6 show it fully connected; grounding dropped true→false) | NEW-FAIL-MODE (R2: H.264/latent-upscaler claim) |

Count: 2 judge_fail / 0 incomplete.

## Notes
- Both pure inspect routes (semantic_product), executor OK, graph unchanged, apply_eligible=false.
- 052e59: REGRESSION-REAL — model ignored bypass mode=4 and link-over-widget precedence it handled in R2.
- f855de: NEW mode — grounding degraded; node 5012 connectivity misread despite links 1/2/5/6.
- Evidence set: agentic_summary/assessment/response/request/chat/classification/flow_metadata/model_attempts/final.ui/original.ui (no implementation_result/research/execution_log in inspect routes).

## Round-3 full synthesis (all 17 fails analyzed)
- SAME-ROOTCAUSE (5): b55994 (litegraph), indextts-2 (guard), 4eebf3 (widget hallucination), 506ebd (infra), + f65774 partially
- NEW-FAIL-MODE (6): f65774 (grounded-refusal), c80bbf (over-refusal), a7ecc5 (ValidationError), multi-i2v-llm (nothing landed), 99e2a9 (link hallucination), f855de (connectivity misread)
- VARIANCE (2): 99e2a9, caae97-family
- REGRESSION-REAL (2): 432652 (infra timeout), 052e59 (bypass misread)
- Already-analyzed round-3 doc (5): caae97, d813fe, multi-i2v-2, 1c7ad8, 71f825
