# Findings — one-step-30-r6 round-2 batch 3 (6 failed scenarios)

Run: `one-step-30-r6` (30-scenario rerun at HEAD `edb0553a`, post `bcf92497`/`a6a81bcb`).
Evidence base: `/private/tmp/vc-twostep/out/agentic/one-step-30-r6/attempts/<scenario>/attempt_1/<scenario>/` (the run the digest judged),
with the task-specified `one-step-30-r5` dirs and the **shared** durable session transcripts
(`out/editor_sessions/two-step-<id>/two_step_execute.jsonl`, accumulated across the r4 → r5 → r6 runs of the same scenario)
as deeper evidence. The criteria arrays in `/tmp/r6-batch3-digest.md` match the on-disk `one-step-30-r6` assessment.json verbatim; the digest's RATIONALE lines are the same text as the assessment rationales (truncated at the digest's line cap).

Headline: 4 of 6 failures are the **same harness failure** — the agent landed a correct, accepted Δ and the turn
then died on budget; the failure response dropped the landed Δ, so the judge (which reads only
response.json + original/final UI artifacts) correctly-but-unfairly saw an empty delta. 1 of 6 (sharpening) is a
grounding-citation gap amplified by a judge that grades the guard's error string instead of the answer.
1 of 6 (gemini) is an uncited-but-tool-grounded availability claim that the UI-only judge surface failed as a
hallucination (a regression vs. r5's more hedged phrasing).

---

### image-gemini-prompt-splitter-and-text-display-workfl-caae97
- Judge verdict: FAIL (criteria: `correct: false, grounded: false, relevant: true`)
- What the agent did: Research-only answer (no edit requested). In the r6 turn it called
  `node_schema(node_class='ClaudeNode')` → `ok: available=True, inputs: api_key_comfy_org, auth_token_comfy_org, comfy_usage_source, images, model, prompt, seed, system_prompt, unique_id`,
  then asserted in the final reply: "I also confirmed the ClaudeNode class is available in your environment
  (inputs: prompt, system_prompt, images, model, seed, unique_id, plus the Comfy.org API-key/usage-source fields)."
  The submit carried `claim_refs.evidence_ids: []` — the node_schema evidence was **not cited**.
- Why it failed: The judge's rationale: "The answer claims ClaudeNode is available in the user's environment, but
  the inspected workflow evidence contains no ClaudeNode and the node inventory is empty; this is a hallucination…".
  The claim is **tool-grounded in the session ledger** (`tool:node_schema-claudenode` is in the r6 evidence_ids, and
  the listed inputs match the schema result exactly) — but the semantic judge's payload
  (`intent_judge.py:1302` — `node_inventory = _ui_node_inventory(original_ui)`) contains **only the UI node inventory**,
  which has no ClaudeNode, and the submit cited no evidence ids. The judge therefore could not see the grounding and
  failed it. The r5 run of the same scenario submitted the *opposite* hedge ("a drop-in Claude text node is not
  confirmed in this environment") and **passed** — this scenario is listed as `regressed` in
  `.oracle/results/one-step-30-r6.json`. Model-variance phrasing flipped a stochastic LLM judge; the stronger claim
  outran the visible (uncited) evidence.
- Class: grounding_or_evidence (submission citation gap; judge surface is UI-only — tool evidence invisible to it)
- Root cause (code-level): agent submits with empty `claim_refs` despite a real tool call (citation discipline);
  judge evidence surface limited to the UI node inventory — `tests/live_agentic_harness/intent_judge.py:1302`
  (`node_inventory = _ui_node_inventory(original_ui)`) and `:1310-1316` (payload has no tool/evidence ledger).
- Evidence:
  - transcript `two-step-c9277aa90d011e2c5d6e46ca` `[75] 22:39:01`: `node_schema(node_class='ClaudeNode') — ok: available=True … inputs: api_key_comfy_org, auth_token_comfy_org, comfy_usage_source, images, model, prompt, seed, system_prompt, unique_id`
  - transcript `[84] 22:42:31` submit: `"I also confirmed the ClaudeNode class is available in your environment…"` with `claim_refs: {"delta_ids": [], "lens_fact_ids": [], "evidence_ids": []}`
  - r6 assessment.json rationale: "the inspected workflow evidence contains no ClaudeNode and the node inventory is empty; this is a hallucination that makes the recommendation to test ClaudeNode ungrounded and technically misleading."

### image-image-comparison-and-enhancement-with-florence-007018
- Judge verdict: FAIL (criteria: `correct_node_targeted: false, correct_parameter_changed: false, no_orphaned_wiring: true, value_semantically_matches_intent: false`)
- What the agent did: r6 turn 30 researched heavily (cont 48→64), then at 23:10:06 submitted an `edit_batch` adding
  five `ImageBlend` nodes (`blend_hp, blend_sharpen, blend_normalmap, blend_saturation, blend_invert`) —
  **accepted as Δ d1** (`delta_accepted` + `apply_accepted`, `apply_batches` budget 0→1, sidecar grew to 48 nodes).
  The turn then died on the session continuation cap (`session_model_continuations: used 64 of limit 64`); the
  response is the generic fallback "I ran out of budget before completing the request; here's what I have: a partial
  edit was applied" with `ok: false`.
- Why it failed: The judge rationale: "The delta_replay is empty and the pre/post IR topologies are identical,
  indicating no nodes were added or modified…". That is true **of the artifacts the judge is allowed to see**:
  the budget-failure response carries `accepted_delta_ids: []`, and `final.ui.json == original.ui.json` (43 nodes),
  so the judge's Δ source (`intent_judge.py:884-914`: response accepted batch, else `diff(pre_wf, post_wf)` of the UI
  pair) is empty. The landed Δ d1 is real and durable (transcript + sidecar) but invisible to the judge.
  Two harness defects compound: (a) the session continuation budget (64) was **carried over** from the r4/r5 runs
  sharing the same session id — the r6 phase started at 48/64 and had only 16 continuations, burning them on
  research before landing d1 at the cap; (b) on budget death the accepted Δ is dropped from the response.
  (In the earlier r5 run the same scenario failed differently: every target resolved as
  `unknown_target` — "no node in the current render resolves to 'imagescaleby'/'278'" — a pre-RC-P1 resolution bug
  that is fixed at current HEAD.) Note also d1 alone would only be a **partial** implementation of the full intent
  (independent float-slider weights were never wired).
- Class: budget_or_retry_exhaustion (with lost-accepted-delta measurement defect + cross-run budget carryover)
- Root cause (code-level): budget death path drops the accepted Δ —
  `vibecomfy/executor/agent_backend.py:779-791` (BudgetExceeded → `_failure_outcome`) + `vibecomfy/executor/two_step.py:1075-1081` (`ExecutorResult.failure` without `accepted_delta_ids`);
  judge cannot see the transcript — `tests/live_agentic_harness/intent_judge.py:884-914`;
  session budget persisted across runs — `vibecomfy/executor/two_step_session.py:874-903` (ingest_transcript folds prior budget records).
- Evidence:
  - transcript `two-step-0a6c65e2b37e35501c7fa633` `[219]/[220]/[222] 23:10:06`: `delta_accepted delta_ids=['d1'] ops=[add_node ImageBlend … node_id 285 …]`, `apply_accepted delta_ids=['d1']`, then `budget apply_batches=1 cont=64`
  - r6 response.json: `error: session_model_continuations: used 64 of limit 64`, `ok: false`, reply "…a partial edit was applied."
  - r6 final.ui.json vs original.ui.json: identical (43 nodes) — the d1 nodes are absent from the graded artifact.

### image-image-editing-with-qwen-image
- Judge verdict: FAIL (criteria: `correct_node_targeted: false, correct_parameter_changed: false, no_orphaned_wiring: true, value_semantically_matches_intent: false`)
- What the agent did: diagnosed the correct fix (positive-prompt text on `TextEncodeQwenImageEditPlus` uid 133 must
  match the reference lighting). At 22:35:24 `edit_node(target='textencodeqwenimageeditplus', field='prompt', value=…same lighting, shadows, color temperature, tone, and exposure…)`
  was **accepted as Δ d1** (`set_node_field ["","133","prompt"]`). It then continued researching (denoise/KSampler)
  and attempted further edits; the per-message apply cap blocked the next apply
  (`apply_batches: used 1 of limit 1`), killing the turn with `ok: false` and the fallback reply.
- Why it failed: Judge rationale: "The accepted Δ is empty (verified=null, checked=0, mismatches=[]) and the pre/post
  diff reports 'No changes'…". The landed d1 (the *correct* lighting edit) was dropped from the failed response
  (`accepted_delta_ids: []`, `final.ui.json == original.ui.json`), so the judge saw no edit.
  (r5's run of this scenario failed on the same pre-fix resolution bug — every target, including uid `133`, rejected
  as `unknown_target`; in r6 resolution worked and the edit landed — but the budget/measurement layer lost it.)
- Class: budget_or_retry_exhaustion (lost-accepted-delta on apply-cap death)
- Root cause (code-level): after one accepted apply in a message, the next apply attempt raises BudgetExceeded and
  fails the whole turn — `vibecomfy/executor/agent_backend.py:783-786` (`check_apply_batch(message_budget, budget_usage)`)
  — and the failure response drops the accepted Δ (`two_step.py:1075-1081`); judge sees only
  response + UI pair (`intent_judge.py:884-914`).
- Evidence:
  - transcript `two-step-711e58b236cba97f77992164` `[137]-[140] 22:35:24`: `delta_accepted delta_ids=['d1'] ops=[{"op":"set_node_field","target":["","133","prompt"],"value":"In exactly the same lighting, shadows, color temperature, tone, and exposure…"}]`, `apply_accepted delta_ids=['d1']`
  - r6 response.json: `error: apply_batches: used 1 of limit 1`, `ok: false`, `graph_unchanged: true`
  - r5 transcript `[89] 19:46:58`: `apply_rejected reason=unknown_target diags=["no node in the current render resolves to '133'."]` (pre-fix resolution failure)

### image-image-processing-with-sharpening-film-grain-an-9aa0f1
- Judge verdict: FAIL (criteria: `correct: false, grounded: false, relevant: false`)
- What the agent did: gave substantive sharpening-alternative answers (unsharp mask, DoG, halo-vs-detail tradeoffs —
  visible in the transcript `[13]` submit, which even names uid:1/uid:9/uid:10 wiring). But every submission contained
  causal/mechanistic phrasing ("lifts fine texture", "pushes broad edge contrast", "isolates a frequency band",
  "sharpening") and carried **no cited grounding evidence** (`claim_refs.evidence_ids` empty; the r4/r5
  `node_schema('Image High Pass Filter')`/`VividSharpenV2` calls returned `no_results`, and the r6 schema hit for
  VividSharpenV2 was never cited). The executor's P2 grounding gate failed closed
  (`failure_kind: ungrounded_answer`, stage `execute`), and the **response.reply became the guard's error string**:
  "causal/mechanistic claim requires cited grounding evidence (hivemind_get / node_schema / registry_lookup / ready_template_load)".
- Why it failed: Judge rationale: "The answer is a meta-comment about needing tool citations, not a response to the
  question… it is empty/refusal-like and fails all three criteria." The judge graded exactly what was in
  response.json — the guard's error message (`intent_judge.py:1287` `answer = _structured_answer_text(response)`),
  because the guard had replaced the agent's answer on fail-closed. Two real defects: (a) the agent never attaches
  evidence citations to its mechanism claims (grounding discipline); (b) the judge's comparison surface is the
  guard's error string, so a substantive-but-uncited answer is scored as an empty refusal.
- Class: grounding_or_evidence (uncited mechanism claims → fail-closed guard), amplified by a judge-surface defect
  (the judge grades the guard error, not the product answer)
- Root cause (code-level): `vibecomfy/executor/contracts.py:2906-2910` (`_has_mechanistic_claim(reply)` and no
  `_GROUNDING_TOOL_NAMES` intersection → violation), fail-closed in `agent_backend.py:899-910`;
  response surfaces the guard error as the reply; judge consumes it —
  `tests/live_agentic_harness/intent_judge.py:1285-1293`.
- Evidence:
  - r6 response.json (identical to r5): `error/failure_message: "causal/mechanistic claim requires cited grounding evidence (hivemind_get / node_schema / registry_lookup / ready_template_load)"`, `claim_validation.failure_kind: "ungrounded_answer"`, `ok: false`
  - transcript `two-step-8b3f4d4e88320a931c11fe5d` `[13] 11:56:10`: the real (uncited) answer — "Practical replacements for the uid:1 detail layer: 1. Unsharp mask … 2. Difference of Gaussians (DoG) …" (never reached the judge)
  - r6 assessment.json rationale: "a meta-statement about needing evidence and does not address the user's question…"

### image-style-transfer-using-ip-adapter
- Judge verdict: FAIL (criteria: `correct_node_targeted: false, correct_parameter_changed: false, no_orphaned_wiring: true, value_semantically_matches_intent: false`)
- What the agent did: diagnosed the correct cause (StyleModelApply uid 12 has no explicit `strength` override, so the
  checkpoint's photo-like output dominates) and at 22:39:47 landed
  `edit_node(target='stylemodelapply', field='strength', value=2.0)` — **accepted as Δ d1**
  (`set_node_field ["","12","strength"] = 2.0`, `apply_accepted`). It continued researching
  (ready_template_list, node_schema) and attempted a further edit; the per-message apply cap
  (`apply_batches: used 1 of limit 1`) killed the turn with `ok: false`.
- Why it failed: Judge rationale: "The accepted delta is empty (no ops), so no node was targeted…". Same lost-delta
  chain as qwen: the accepted d1 never reached response.json/final.ui.json
  (`final.ui.json == original.ui.json`), so `intent_judge.py:884-914` derived an empty Δ and failed C1–C3.
  The r5 run of this scenario failed on the pre-fix resolution bug ("no node in the current render resolves to '12'/'stylemodelapply'").
- Class: budget_or_retry_exhaustion (lost-accepted-delta on apply-cap death)
- Root cause (code-level): identical to qwen — `vibecomfy/executor/agent_backend.py:783-786` + `two_step.py:1075-1081` + `intent_judge.py:884-914`.
- Evidence:
  - transcript `two-step-1b4a5c7bd2a53ff64d798b05` `[96]/[97]/[99]/[100] 22:39:47`: `delta_accepted delta_ids=['d1'] ops=[{"op":"set_node_field","target":["","12","strength"],"value":2.0}]`, `apply_accepted`, `budget apply_batches=1`
  - r6 response.json: `error: apply_batches: used 1 of limit 1`, `ok: false`
  - r5 transcript `[46] 19:53:34`: `apply_rejected reason=unknown_target diags=["no node in the current render resolves to '12'."]`

### image-two-stage-qwen-image-generation
- Judge verdict: FAIL (criteria: `correct_node_targeted: false, correct_parameter_changed: false, no_orphaned_wiring: true, value_semantically_matches_intent: false`)
- What the agent did: traced the distortion to the refinement pass (LatentUpscaleBy uid 53, 1.5× bislerp; second
  SamplerCustom), and at 22:49:34 landed `edit_node(target='latentupscaleby', field='upscale_method', value='bilinear')` —
  **accepted as Δ d1** (`set_node_field ["","53","upscale_method"] = "bilinear"`, `apply_accepted`). It then researched
  SplitSigmas/sampler tuning for a second edit; the apply cap (`used 1 of limit 1`) killed the turn with `ok: false`.
- Why it failed: Judge rationale: "The accepted Δ contains no changes (delta_replay shows zero checked/mismatches and
  pre/post diffs are 'No changes')…". Same lost-delta chain as qwen/ip_adapter. The r5 run failed on the pre-fix
  resolution bug ("no node in the current render resolves to 'latentupscaleby'/'53'").
- Class: budget_or_retry_exhaustion (lost-accepted-delta on apply-cap death)
- Root cause (code-level): identical to qwen — `agent_backend.py:783-786` + `two_step.py:1075-1081` + `intent_judge.py:884-914`.
- Evidence:
  - transcript `two-step-60f10fc901357fc47e1c8539` `[100]/[101]/[103]/[104] 22:49:34`: `delta_accepted delta_ids=['d1'] ops=[{"op":"set_node_field","target":["","53","upscale_method"],"value":"bilinear"}]`, `apply_accepted`, `budget apply_batches=1`
  - r6 response.json: `error: apply_batches: used 1 of limit 1`, `ok: false`
  - r5 transcript `[73] 20:01:16`: `apply_rejected reason=unknown_target diags=["no node in the current render resolves to '53'."]`

---

## Batch summary

Dominant failure class: **budget_or_retry_exhaustion (4/6)** — every one of the four edit scenarios landed a
correct, mechanically-accepted Δ (prompt lighting fix on uid 133, style strength 2.0 on uid 12, upscale method on
uid 53, five ImageBlend add-nodes) and then the turn died on a budget cap (per-message apply cap 1, or the
64-continuation session cap that was already 48/64 from prior runs sharing the same session id), and the
budget-failure response **dropped the accepted Δ** — `accepted_delta_ids: []`, `final.ui.json` left equal to the
original — so the `edit_intent` judge (which reads only response.json + the UI pair, `intent_judge.py:884-914`)
correctly-but-unfairly graded an empty delta. The r5-era root cause for these scenarios (every target resolving as
`unknown_target`/"no node in the current render resolves to '133'", `edit_tools.py:262-290`) is fixed at current
HEAD — the rerun exposed the next layer. The two answer-only failures are grounding-citation gaps (sharpening:
mechanism claims with no cited evidence → P2 guard fail-closed at `contracts.py:2906`, and the judge then grades the
guard's error string; gemini: a tool-grounded ClaudeNode claim submitted with `claim_refs.evidence_ids: []` that the
UI-only judge surface (`intent_judge.py:1302`) failed as a hallucination — a regression vs. r5's hedged phrasing).

Single highest-leverage fix: **make the judge see landed edits even when the turn ends in failure** — on any
budget/guard failure after an accepted apply, carry the accepted Δ (`accepted_delta_ids`, the applied ops, and the
post-edit graph) into the response and the final.ui.json artifact (and/or have the judge consult the durable
transcript's `delta_accepted` records), and treat "second apply attempt after an accepted apply" as a soft stop or a
new message instead of a turn-killing `BudgetExceeded`; additionally reset session budget state (or mint fresh
session ids) when a scenario is re-run, so carry-over budget cannot starve a rerun mid-edit. Secondary fix: give the
semantic judge the session evidence ledger (tool call ids/grounding evidence) alongside the UI inventory so
evidence-backed claims are not graded as hallucinations, and surface the agent's actual answer (not the guard's
error string) to the judge when the guard fails closed.
