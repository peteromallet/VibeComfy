# ir-everywhere-30-v3 failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v3 (round 3 of fixed-30 loop, quiet machine, RC-1..5 applied @ 8d897528)
Analysis agent: Flash (read-only, evidence-cited)

## Verdicts

| Scenario | CLASS | ROOT-CAUSE | OUTCOME |
|---|---|---|---|
| image-gemini-prompt-splitter-caae97 | judge_fail | semantic_answer fail (hallucinated hivemind:3166 Claude node + wrong Flash pricing) | **VARIANCE** (R2 PASS grounded same product; answer wobble) |
| image-kolors-d813fe | judge_fail | MalformedModelJSON (multiple ```batch blocks) | **VARIANCE** (R2 PASS grounded-refusal; GroundingDINO absent both rounds; format flake) |
| video-video-loading-1c7ad8 | judge_fail | semantic_answer fail (ignored mode=4 bypass, claimed 3 videos) | **VARIANCE** (R2 PASS identified one active branch; answer wobble) |
| video-wanvideo-71f825 | incomplete | TimeoutError at reply stage, both attempts (infra_blocked) | **VARIANCE** (R2 PASS grounded inspect; infra timeout this run) |
| multi-image-to-video-generation-with-2 | judge_fail | edit landed (candidate non-null, applyable) but edit_intent failed: agent chose VHS_VideoCombine 239.frame_rate 24→25 (video-only combiner) instead of audio node 220 | **RC-PARTIALLY-LANDED** — RC-2 primitive-alias fix (4b665255) LIVE and eliminated R2's mechanical failure; R3 agent picked a different wrong target |

Count: 4 judge_fail / 1 incomplete.

## Key takeaways
- All 4 R2→R3 regressions are VARIANCE — no code regressions. The 3 judge-fail variance rows are inspect-answer wobble; the 4th is a reply-stage infra timeout.
- multi-i2v-2: RC-2 fix verified live (primitive write now persists, candidate produced, edit applies). Remaining failure is model target-selection (wrong node), not the dual-channel defect.
- Confirms the R3 scoreboard: 13 PASS / 17 FAIL with ~7 variance-answer rows wobbling run-to-run; durable product fixes (cc0df7, 3d-converts, d20410, 03fced, 19d221, 1d414c, 485ff2) hold.
