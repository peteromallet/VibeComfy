# ir-everywhere-30-v2 batch-A failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v2 (round 2 of fixed-30 loop, quiet machine, RC1-8 applied)
Batch: A (5 scenarios)

## Verdicts

| Scenario | CLASS | ROOT-CAUSE | OUTCOME vs round 1 |
|---|---|---|---|
| 3d-3d-model-generation-and-retargeting-f65774 | judge_fail | safe-refusal (RefusedEmit snapshot-delta guard) | SAME-ROOTCAUSE |
| audio-audio-processing-chatterbox-b55994 | judge_fail | litegraph-counter (last_node_id 428→427) | SAME-ROOTCAUSE |
| audio-ltx-c80bbf | judge_fail | unbound-name (AudioLDM2 absent; removed MelBand nodes then stalled) | SAME-ROOTCAUSE |
| audio-tts-narration-indextts-2 | judge_fail | widget-shape overflow refused (node 124, 2 vs schema 1) | **VARIANCE** (round-1 PASS edited node 125 matching shape; guard correctly refused) |
| image-dual-checkpoint-c9df19 | judge_fail | semantic_answer grounded=False 'handoff at step 20' | **VARIANCE** (round-1 PASS accepted substantively identical '25 steps, switch at 20'; original.ui.json confirms end_at_step=20) |

Count: 5 judge_fail / 0 incomplete.

## Evidence notes
- f65774: implementation_result RefusedEmit guard_emit snapshot-delta; 3 assessment issues (response_ok/graph_changed/intent_judge).
- b55994: hard_diagnostic litegraph counter; ValidationError last_node_id 428->427.
- c80bbf: implementation_result 'AudioLDM2 is absent from the local schema' + 4 remove_node ops left broken wiring.
- indextts-2: implementation_result widget shape refused overflow on node 124 QwenEmotionNode (candidate 2 vs schema 1); round-1 PASS assessment edited node 125 IndexTTSEmotionOptionsNode matching shape. Guard correctly refused — VARIANCE.
- c9df19: round-2 semantic_answer grounded=False vs round-1 accepted same content; original.ui.json base end_at_step=20 + refiner start_at_step confirms the answer was correct — judge-strictness VARIANCE.
