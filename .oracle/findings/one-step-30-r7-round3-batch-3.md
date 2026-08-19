# Failure analysis — one-step-30-r5, batch 3 (6 scenarios) — DeepSeek Flash

Run under analysis: `one-step-30-r5` (commit bcf92497, typed edit tools + retained IR).
Judge verdicts below are quoted from the per-scenario `assessment.json` in the attempt dirs; the batch digest (`/tmp/r7-batch3-digest.md`) is the re-judged criteria for this batch and is cross-checked where it differs. Every claim is grounded in the artifacts quoted.

---

### image-image-editing-with-qwen-image

- Judge verdict: FAIL — `edit_intent`: criteria `{correct_node_targeted: False, correct_parameter_changed: False, value_semantically_matches_intent: False, no_orphaned_wiring: True}`.
  > "The accepted Δ is empty; no nodes or parameters were changed, so the edit fails to target any node, change any parameter, or achieve the lighting-matching intent." (assessment.json, `edit_intent` rationale)
- What the agent did: Correctly diagnosed the fix — rewrite the `prompt` text on `TextEncodeQwenImageEditPlus` (uid 133) so the added soldier matches the scene lighting — then attempted `edit_batch`/`edit_node` calls with the binding name `textencodeqwenimageeditplus`, the request-graph id `133`, and `uid:133`. All were rejected; the final submit declared `graph_unchanged: true` with zero accepted deltas.
- Why it failed: The judge is right about the **artifact** (Δ empty), but the agent's output was not the problem — the tool rejected *valid* targets. The session trace shows three separate invocations (turns 1, 5, 13) rejected with `unknown_target_name` / `unknown_target` ("Unknown graph name 'textencodeqwenimageeditplus'...", "no node in the current render resolves to '133'."), and **turn 24 executed the identical `edit_node(field='prompt', target='textencodeqwenimageeditplus', ...)` and it was ACCEPTED (`apply_accepted ... delta_ids: ["d1"]`)**. A local reproduction of the exact session construction (`EditSession(dict(request.graph))`) proves the name was always resolvable: `uid_by_name` contains `textencodeqwenimageeditplus → 133`, and `resolve_target` returns `133`. The official `response.json` was frozen from turn 13's failed submit (its reported budget — 39 continuations / 26 tool calls / 154 681 tokens — matches turn-13's budget events exactly), so the judge never saw the edit that later landed.
- Class: `judge_or_harness_bug` — spurious edit-target rejection during the scored invocation; the scored artifact froze a pre-acceptance state while the session later accepted the same edit (Δ=d1). Not model capability.
- Root cause (code-level): target resolution / retained-IR session state in the execute path — `resolve_target` (`vibecomfy/executor/edit_tools.py:262-290`), the derived name map `EditSession.uid_by_name` (`vibecomfy/porting/edit/session.py:246-272`), and base-graph selection `retained_workflow(...) if ... else request.graph` (`vibecomfy/executor/two_step.py:1119-1122`). The exact degenerate state during the scored invocations is **not recoverable from retained evidence**: `two_step_base_graph.json` was written at 13:49, *after* the first invocations (11:49, 12:44), so the session store was incomplete mid-run. The mechanism (empty/stale retained workflow or code-version drift across the run day) is `unknown_needs_human`; the repro proves the current code resolves these names correctly, so the bug is in what the scored invocation *actually* held, not in name derivation.
- Evidence:
  - `apply_rejected` seq 14: `["Unknown graph name 'textencodeqwenimageeditplus'. Render the session again if the canvas changed.", "Unknown graph name 'textencodeqwenimageeditplus_2'. ...", "A later edit statement failed, so all edits from this batch were rolled back."]`
  - `apply_rejected` seq 90: `["no node in the current render resolves to '133'."]`
  - `apply_accepted` seq 141: `{"delta_ids": ["d1"], "kind": "apply_accepted", "turn": 24}` (same call as the rejected ones)
  - Repro: `uid_by_name["textencodeqwenimageeditplus"] == "133"`; `resolve_target(sess, "textencodeqwenimageeditplus") -> 133`
  - response.json budget `{"model_continuations": 39, "tool_calls": 26, "output_tokens": 154681, "replacement_attempts": 2, "apply_batches": 0}` == trace seq 125-126 (turn 13).

---

### image-image-processing-with-sharpening-film-grain-an-9aa0f1

- Judge verdict: FAIL — `semantic_answer`: criteria `{correct: False, grounded: False, relevant: False}`.
  > "The answer is a meta-comment about needing tool citations, not a response to the question; it names no alternative sharpening methods, discusses no halo vs. detail tradeoffs, and engages none of the workflow evidence..." (assessment.json, `semantic_answer` rationale)
- What the agent did: On turn 1 it produced a substantive, workflow-grounded answer ("No graph changes were made. I checked the Hivemind corpus... The high-pass blend path to replace is uid:1 (Image High Pass Filter, currently widget_0=5, widget_1=2.5...)... treat node-specific widget semantics below as unverified — I'm inferring from the observed values..."), after research that was heavily infra-degraded (hivemind 57014 timeouts; `node_schema` unavailable for `Image High Pass Filter` / `VividSharpenV2`).
- Why it failed: The deterministic grounding gate flagged the answer for "causal/mechanistic claim requires cited grounding evidence", fed one corrective continuation, and on the second violation failed closed — replacing the entire reply with the gate's own violation text. The judge then scored the placeholder. Trace: `grounding_retry` violations at seq 22 (turn 3), seq 58 (turn 5), seq 106 (turn 17); final artifact `response.json` has `ok: false`, `error` and `reply` both equal to the placeholder string, `claim_validation.status: "failed"`, `failure_kind: "ungrounded_answer"`. There is a genuine model component (the answers make causal claims — e.g. sharpening/upscaling mechanism verbs — without citing `node_schema`/`hivemind_get` evidence), but the *failure mode* — the answer being destroyed and replaced by the gate's own text — is a harness design issue (philosophy #6 "safety through verification, not refusal", #8 infra ≠ product).
- Class: `refusal_or_block` — a gate-manufactured placeholder refusal (with a real `grounding_or_evidence` sub-component: the model's causal phrasing without citations).
- Root cause (code-level): `grounding_violations` mechanistic-claim gate — `vibecomfy/executor/contracts.py:2865-2924` (violation raised at 2915-2919 via `_has_mechanistic_claim`, `_MECHANISM_RE` at 2788) — and the executor fail-closed path `agent_backend.py:1033-1058`: one corrective continuation (`grounding_retry_used`), then `TwoStepSessionError(ERROR_UNGROUNDED_ANSWER)` → `_terminal(exc, ok=False)` whose message becomes the final reply.
- Evidence:
  - `grounding_retry` seq 22: `{"violations": ["causal/mechanistic claim requires cited grounding evidence (hivemind_get / node_schema / registry_lookup / ready_template_load)"]}`
  - response.json: `"reply": "causal/mechanistic claim requires cited grounding evidence (hivemind_get / node_schema / registry_lookup / ready_template_load)"`, `"ok": false`
  - Trace turn-1 reply (seq 14) shows the real answer that was discarded.

---

### image-qwen-image-inpainting-with-controlnet-09fc64

- Judge verdict: FAIL — but the two assessment sources disagree, and the r5 assessment is demonstrably wrong:
  - r5 `assessment.json`: `semantic_answer` `{correct: False, grounded: False, relevant: True}` — rationale: "The answer claims node 80 (LoraLoaderModelOnly) has mode=0 (enabled) and is active in the pipeline, but the original_ui/final_ui evidence shows it has mode=4 (bypassed)..."
  - Batch digest / r7 re-judge: `{correct: True, grounded: False, relevant: True}` — rationale: "The answer is relevant and technically sound, but it names nodes (ImageCompositeMasked, ImageBlend) and community workflow precedents that are absent from the node inventory/evidence, and it asserts schema fields for ControlNetInpaintingAliMamaApply..."
- What the agent did: Research-only (request: "Before editing anything, research the best techniques...", `apply: false`) — the correct behavior for this request. It produced a technically sound, workflow-observed answer (mask path, bypassed ImagePadForOutpaint, KSampler denoise=1, schema fields for ControlNetInpaintingAliMamaApply, no numeric recommendations), while naming two nodes absent from evidence (ImageCompositeMasked, ImageBlend) and asserting the ControlNet node's schema fields without payload documentation.
- Why it failed: The r5 judge's rationale is **fabricated**: the agent's reply never mentions node 80, LoraLoaderModelOnly, or any mode. Grep of the attempt dir shows "node 80" appears *only* inside `assessment.json`/`agentic_summary.json` (the judge's own text); `original.ui.json` shows node 80 `mode=4`, which the agent never discussed. The batch digest's re-judge matches the actual reply and the fail is honest: ungrounded node-name claims. So: genuine grounding failure by the agent (model capability), plus a hallucinated r5 judge rationale (harness bug).
- Class: `grounding_or_evidence` (primary — ungrounded node names/community precedents in the answer), with `judge_or_harness_bug` for the r5 assessment rationale.
- Root cause (code-level): agent-side hallucination (no code-level defect in the agent path); r5 judge rationale fabrication is in the assessment/judge layer (specific file not determinable — the fabricated claim appears only in generated `assessment.json`/`agentic_summary.json`).
- Evidence:
  - Full reply (response.json message): "**Post-decode masked compositing.** ... A masked-composite node such as ImageCompositeMasked is the standard approach here; a registry lookup for that exact class returned no authoritative ownership..." — no node-80/mode claim anywhere.
  - `grep -rn "node 80"` in the attempt dir → only `assessment.json` and `agentic_summary.json`.
  - `original.ui.json`: node `80 LoraLoaderModelOnly mode= 4`.
  - r7 re-judge: `criteria: {"grounded": false, "relevant": true, "correct": true}`.

---

### image-style-transfer-using-ip-adapter

- Judge verdict: FAIL — `edit_intent`: criteria `{correct_node_targeted: False, correct_parameter_changed: False, value_semantically_matches_intent: False, no_orphaned_wiring: True}`.
  > "The Δ is empty (verified: null, diff: No changes) — no node was targeted and no parameter was changed, so the edit made no adjustment to address the statue style weakness." (assessment.json)
- What the agent did: Correctly diagnosed the target — `StyleModelApply` (binding `stylemodelapply`), raising `strength` to 2.0 and setting `strength_type=multiply` — and attempted it repeatedly. One early genuine syntax slip ("Subscript is not an allowed edit-surface construct", seq 33) aside, the tool rejected the valid targets (`unknown_target_name 'stylemodelapply'`; "no node in the current render resolves to '12'/'stylemodelapply'"), and the session burned its replacement windows. Final submit: `graph_unchanged: true`.
- Why it failed: Identical pattern to scenario 1: at turn 17 the **same** `edit_node(field='strength', target='stylemodelapply', value=2.0)` was **accepted** (`apply_accepted ["d1"]`), but the official `response.json` froze the earlier failed submit ("the editor could not match the style node for editing after the earlier attempts"). Judge's verdict is correct for the frozen artifact; the agent's edit was correct and eventually landed.
- Class: `judge_or_harness_bug` — spurious target-resolution rejections during the scored invocation; artifact captured before the accepted Δ.
- Root cause (code-level): same session/tool resolution layer as scenario 1 (`edit_tools.py:262-290` `resolve_target`; `session.py:246-272` `uid_by_name`; `two_step.py:1119-1122` base-graph selection). Exact live-session state at the scored invocation not recoverable → `unknown_needs_human` for the precise line.
- Evidence:
  - `apply_rejected` seq 36: `["Unknown graph name 'stylemodelapply'. Render the session again if the canvas changed.", ...]`
  - `apply_rejected` seq 47/51: `["no node in the current render resolves to '12'."]` / `["no node in the current render resolves to 'stylemodelapply'."]`
  - `apply_accepted` seq 100: `["d1"]` (turn 17, identical args: `edit_node {field: strength, target: stylemodelapply, value: 2.0}`).

---

### image-two-stage-qwen-image-generation

- Judge verdict: FAIL — `edit_intent`: criteria `{correct_node_targeted: False, correct_parameter_changed: False, value_semantically_matches_intent: False, no_orphaned_wiring: True}`.
  > "The accepted Δ contains no statements (verified=null, checked=0, mismatches=[]) and both pre/post views show 'No changes' with identical topology..." (assessment.json)
- What the agent did: Correctly localized the distortion to the refinement stage — `LatentUpscaleBy` (1.5×/bislerp) and the second `ClownSampler_Beta` (`widget_0=0.4`) — and attempted `edit_node(field='upscale_method', target='latentupscaleby', value='bilinear')` plus the id `'53'`. All rejected (`unknown_target_name`, "no node in the current render resolves to '53'/'latentupscaleby'"). Final submit: `graph_unchanged: true`.
- Why it failed: Same pattern again — at turn 15 the **identical** `edit_node(target='latentupscaleby', field='upscale_method', value='bilinear')` was **accepted** (`apply_accepted ["d1"]`), while the official artifact froze the earlier failed submit ("every attempt ... was rejected because the node target wouldn't resolve — the session's retained graph looks out of sync with the render"). Note also: the batch digest's claim that "the post-IR topology is empty (0 nodes, 0 edges)" is contradicted by the artifact — `final.ui.json` is byte-identical in shape to `original.ui.json` (24 nodes, raw node-id-keyed dict). The digest/r7-era judge appears to have parsed the raw-format UI dict as LiteGraph `{nodes, edges}` and read 0 nodes — a judge serialization mis-read (philosophy #1: diff over two different serializations is narrative).
- Class: `judge_or_harness_bug` — spurious edit-target rejection during the scored invocation; artifact frozen pre-acceptance; plus a digest-side post-IR serialization mis-read.
- Root cause (code-level): same session/tool resolution layer as scenarios 1/4 (`edit_tools.py:262-290`, `session.py:246-272`, `two_step.py:1119-1122`); exact degenerate state `unknown_needs_human`. Judge-side: post-IR serialization parsing of raw-format UI (judge layer, file not determined).
- Evidence:
  - `apply_rejected` seq 41/47: `["Unknown graph name 'latentupscaleby'. Render the session again if the canvas changed.", ...]`
  - `apply_rejected` seq 61/74: `["no node in the current render resolves to 'latentupscaleby'."]` / `["no node in the current render resolves to '53'."]`
  - `apply_accepted` seq 104: `["d1"]` (turn 15, identical args).
  - `original.ui.json` / `final.ui.json` both keyed `['1','10','14','16','19','2','20','28','29','3',...]` — identical, non-empty.

---

### multi-3d-gaussian-splatting-from-video-with-hunyuan-432652

- Judge verdict: FAIL — `semantic_answer`: criteria `{correct: False, grounded: False, relevant: False}`.
  > "The answer is a placeholder meta-comment ('causal/mechanistic claim requires cited grounding evidence...') that contains no substantive analysis of the workflow. It never names or grounds claims in the required nodes (HWMInference, Save3DGaussians, etc.)..." (assessment.json)
- What the agent did: Produced substantive, graph-grounded answers — e.g. turn 1: "I inspected the graph: it's a single-pass HunyuanWorld-Mirror pipeline — VHS_LoadVideo (frame_load_cap=64...) → PreprocessImagesForHWM (crop to 518) → HWMInference → then parallel saves/previews... The flicker is most plausibly from per-frame depth/normals that aren't temporally constrained." Research was heavily infra-degraded (repeated hivemind 57014 timeouts; `node_schema`/`registry_lookup` no-results for HWMInference).
- Why it failed: Same grounding-gate mechanism as scenario 2: the causal phrase "most plausibly from per-frame depth/normals" without qualifying citations tripped `_has_mechanistic_claim`; the gate gave one corrective continuation and then failed closed, replacing the answer with its own violation text (`response.json`: `ok: false`, reply = placeholder, `claim_validation.status: "failed"`). The judge scored the placeholder. Genuine model component (causal claims without citations) + destructive gate design.
- Class: `refusal_or_block` — gate-manufactured placeholder refusal (with a real `grounding_or_evidence` sub-component).
- Root cause (code-level): same as scenario 2 — `contracts.py:2865-2924` (violation at 2915-2919), fail-closed path `agent_backend.py:1033-1058`.
- Evidence:
  - Trace turn-1 reply (seq 20): "...The flicker is most plausibly from per-frame depth/normals that aren't temporally constrained. HWMInference is a monolithic node wit..." (the discarded real answer).
  - `grounding_retry` seq 39/72: violations = the causal-claim text.
  - response.json: `"reply": "causal/mechanistic claim requires cited grounding evidence (hivemind_get / node_schema / registry_lookup / ready_template_load)"`, `"ok": false`, `failure_kind: "ungrounded_answer"`, `failure_stage: "execute"`.

---

## Batch summary

The dominant failure class in this batch is **judge_or_harness_bug — the edit/tool layer rejected valid targets during the scored invocation and the artifacts froze a pre-acceptance state** (scenarios 1, 4, 5): in every edit scenario the agent picked the right node, field, and value (proven by local reproduction of `uid_by_name` and by the identical `edit_node`/`edit_batch` call being **accepted** on a later turn of the same session — Δ=d1 — while the official `response.json`/`assessment.json` captured the earlier failed submit with an empty Δ). Two further judge-side defects: the r5 judge fabricated the node-80/mode-0 claim for scenario 3, and the digest's "post-IR is empty" claim for scenario 5 contradicts the non-empty, identical `final.ui.json` (raw-format dict mis-parsed as LiteGraph). The second cluster is the **grounding-gate placeholder** (scenarios 2, 6): the deterministic causal-claim gate (`contracts.py:2915-2919` + `agent_backend.py:1033-1058`) destroyed substantive, workflow-grounded answers after one retry and replaced the reply with its own violation text, which the judge then correctly scored as empty. Genuine model-capability failure is limited to ungrounded claims: node-name hallucination in scenario 3's answer, and causal phrasing without citations in scenarios 2/6.

Single highest-leverage fix: **make the scored artifact reflect the session's real accepted-Δ ledger** — i.e., fix the retained-IR target-resolution path so valid binding names resolve on the first invocation (the current code resolves them; the scored invocations hit a degenerate session state, so assert/fail-loudly when `uid_by_name` is empty instead of rejecting valid names), and have the harness capture the terminal session state (including later-accepted Δs) rather than the first failed submit — this alone flips scenarios 1, 4, and 5 to passes. Second, make the grounding gate **non-destructive**: on retry exhaustion, return the model's answer with the violation attached as a warning instead of substituting the gate's own text for the reply (philosophy #6/#8), which recovers scenarios 2 and 6's substantive content for the judge.
