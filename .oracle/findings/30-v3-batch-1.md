# ir-everywhere-30-v3 batch-1 failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v3 (round 3, RC1-5 applied @ 8d897528)
Batch: 1 of 3 (5 scenarios)
Analysis agent: Flash (read-only, evidence-cited)

## Verdicts (latest attempt, vs round 2)

| Scenario | CLASS | ROOT-CAUSE | OUTCOME vs R2 |
|---|---|---|---|
| 3d-3d-model-generation-and-retargeting-f65774 | judge_fail | safe-refusal (grounded_refusal fail: specific_next_action=False, graph_unchanged) | NEW-FAIL-MODE (R2: RefusedEmit snapshot-delta; R3: grounded-refusal rejection) |
| audio-chatterbox-b55994 | judge_fail | litegraph-counter (ValidationError + hard_diagnostic LiteGraph id counter) | SAME-ROOTCAUSE |
| audio-ltx-c80bbf | judge_fail | safe-refusal (grounded_refusal fail: no_representable_edit=False, outcome requires_custom_nodes) | NEW-FAIL-MODE (R2: broken edit; R3: over-refusal) |
| audio-tts-narration-indextts-2 | judge_fail | RefusedEmit destroy-editor-state, empty edit_intent delta | SAME-ROOTCAUSE |
| image-wan2-2-chroma-a7ecc5 | judge_fail | ValidationError + hard_diagnostic LiteGraph id counter | NEW-FAIL-MODE (R2: RefusedEmit) |

Count: 5 judge_fail / 0 incomplete.

## Notes
- f65774: grounded_refusal fail (specific_next_action=False), graph_unchanged, no_changes, gates failed — attempt_2.
- b55994: same LiteGraph counter as rounds 1-2 (last_node_id regression).
- c80bbf: outcome requires_custom_nodes now — the RC-4 clarify envelope partially advanced (kind changed) but grounded_refusal still fails (no_representable_edit=False).
- indextts-2: RefusedEmit destroy-editor-state — the guard refusal, SAME across rounds.
- a7ecc5: NEW failure shape — ValidationError + LiteGraph counter (R2 was RefusedEmit).
