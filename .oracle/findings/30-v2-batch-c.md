# ir-everywhere-30-v2 batch-C failure analysis (DeepSeek Flash)

Run: ir-everywhere-30-v2 (round 2 of fixed-30 loop, quiet machine, RC1-8 applied)
Batch: C (last 5 scenarios)

## Verdicts

| Scenario | CLASS | ROOT-CAUSE | OUTCOME vs round 1 |
|---|---|---|---|
| multi-svd-99e2a9 | judge_fail | semantic_answer correct=False — claims seed 'fixed' but KSampler(70) control_after_generate='randomize' | SAME-ROOTCAUSE |
| video-animatediff-4eebf3 | judge_fail | semantic_answer grounded=False — hallucinated widget_3→tile_size, widget_4→overlap for IPAdapterTiled | SAME-ROOTCAUSE |
| video-video-inpainting-485ff2 | judge_fail | edit queue-gate — edit landed (intent pass) but schema-less INPAINT node blocks queue_validate_ok | NEW-FAIL (was same class round 1: still queue-gate) |
| video-video-output-f855de | judge_fail | semantic_answer correct=False — grounded but wrong latent-upscaler causal claim | NEW-FAIL (round 1 was grounded=False; now grounded=True, correct=False) |
| multi-animatediff-face-swap-506ebd | incomplete | infra-timeout ×2, killed_before_first_attempt=true both rounds | SAME-ROOTCAUSE (infra, identical) |

Count: 4 judge_fail / 1 incomplete.

## Evidence notes
- 99e2a9: claims seed 'fixed' but KSampler(70) control_after_generate='randomize' — correct=False on a grounded answer. Keep failing per philosophy (no softening).
- 4eebf3: hallucinated widget_3→tile_size, widget_4→overlap mapping for IPAdapterTiled — grounded=False. RC-3 lens change landed but the model still invents widget semantics in this run.
- 485ff2: edit landed (intent passed) but schema-less INPAINT node blocks queue_validate_ok — the RC-2 pre-existing-unknown-class fix did NOT cover this schema-less node (still hard-blocked). SAME-ROOTCAUSE.
- f855de: NEW-FAIL shape — round 1 grounded=False (invented 8-bit VAE); round 2 grounded=True but correct=False (wrong latent-upscaler causal claim). Different miss mode.
- 506ebd: both attempts infra_timeout killed_before_first_attempt=true; stderr shows emit_ready.py output-arity disagreement warnings. Never exercises the model in either round.

## Round-2 synthesis (15 fails)
- SAME-ROOTCAUSE (8): f65774, b55994, c80bbf, 19d221, a7ecc5, multi-i2v-2, 99e2a9, 4eebf3
- VARIANCE (3): indextts-2, c9df19, 1d414c
- REGRESSION-REAL (1): multi-i2v-llm
- NEW-FAIL-mode (2): 485ff2 (schema-less queue-gate persists), f855de (correct=False now)
- INFRA (1): 506ebd (never starts)
- Effective quality: 15 PASS + 3 variance ≈ 16-17/30 real; the 3 variance rows are judge/luck not code.
