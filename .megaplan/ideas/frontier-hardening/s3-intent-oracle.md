# S3 — intent-oracle: the existential gate #1 (correctness, not faithfulness)

## Outcome
An **independent judge of "did the edit do what the user ASKED"** — separate from faithfulness. It can
fail an edit that the codec applied perfectly and the refusal-spine allowed, because the edit was
*wrong for the request*. This is the gate that will let a future editor go write-enabled.

## Why (the gremlin)
Roadmap §14 lens 2 (verdict: existential). The whole safety apparatus proves FAITHFULNESS — "we changed
exactly the delta, nothing else." A confidently-wrong-but-intended edit (LoRA wired at the wrong point;
`denoise=1.0` on a hires pass; wrong sampler) passes the semantic gate AND the refusal-spine *by
construction* (allowing the intended delta is literally the T4 spike's success criterion). The intent
judge does not exist in code, and the scratchpad-emitter chain ends at read-only m7. `grep` for
`edit.correct|intent.judge|render.diff|execution.diff` returns nothing.

## Scope — IN
- A **"wrong-but-faithful" corpus**: ~15 hand-authored IR edits that satisfy the literal NL request but are
  task-wrong — the falsification harness (predicted: the existing refusal-spine ALLOWs all 15).
- An **execution/render-diff oracle**: run pre/post graphs via embedded `queue_prompt_api`, diff outputs
  (images/latents) with a defined tolerance.
- An **LLM-judge panel** scoring the post-edit graph against the NL intent (independent of VibeComfy's compile).
- An **`edit-correctness %`** metric (§5), reported per-family; explicitly NOT measured via `convert_ui_to_api`.

## Scope — OUT
- The agent loop that PRODUCES edits (separate concern). Auto-remediation of wrong edits.
- Wiring the oracle into a live editor (that's the future write-enable milestone, gated ON this).

## Locked decisions
- The intent oracle is **INDEPENDENT of `convert_ui_to_api`** — that oracle judges faithfulness only;
  reusing it here re-enters the self-reference the roadmap §6.1 condemns. (The sweep flagged this trap.)
- "Verified faithful" and "verified right" are DIFFERENT claims and reported separately.

## Open questions (resolve in planning / prep)
- Render-diff metric + tolerance (perceptual vs exact; how to handle seed/nondeterminism).
- Judge-panel composition (how many judges, what rubric, how to aggregate) and its own validation.
- How much GPU/compute the execution-diff needs and whether a CPU/proxy path suffices for CI.

## Constraints
- The execution-diff path may need real model execution — keep a deterministic/proxy mode for CI.
- Must build on S1's version-anchored oracle so the *faithfulness* baseline is trustworthy.

## Done criteria
- The wrong-but-faithful corpus scores **< 100% pass** on the new intent oracle **while** the existing
  refusal-spine ALLOWs all 15 — proving the judge catches what faithfulness structurally cannot.
- An `edit-correctness %` is produced for at least one family, with a written self-reference tripwire test
  asserting the intent operand is NOT a VibeComfy compile.

## Touchpoints
- New `vibecomfy/intent/` module, the embedded runtime (`run_embedded*` / `queue_prompt_api`),
  `tests/` (the wrong-but-faithful corpus + the metric).

## Anti-scope
- Do not build the agent/editor. Do not reuse `convert_ui_to_api` as the intent judge. Do not ship any
  write path — this sprint produces the GATE, not the editor.

## Handoff artifact
The `edit-correctness %` gate + the wrong-but-faithful corpus — a prerequisite the future write-enable
milestone must pass before any edit reaches a user's canvas.
