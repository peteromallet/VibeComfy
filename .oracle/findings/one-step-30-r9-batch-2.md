# Failure findings — one-step-30-r9 batch 2 (DeepSeek Flash)

Run: `one-step-30-r9` (live agentic harness, commit bcf92497, typed edit tools + retained IR; model `deepseek/deepseek-v4-flash` via OpenRouter; pipeline_mode `two_step`, one-step agent mode).
Batch definition: `/tmp/r9-batch2-digest.md` (authoritative for this batch). Note: the brief says "6 failed scenarios" but the digest contains **5** — the digest is the actual batch (the run was still in progress when digests were minted, per `/tmp/r9-monitor.log`); all 5 are analyzed. The digest's CRITERIA fields mirror each `judge_results` entry; the terminal verdicts are read from `assessment.json` (terminal truth).

---

### audio-acestep-audio-generation-with-detail-daemon-f0859f
- Judge verdict: FAIL (criteria: `correct=false, grounded=true, relevant=false` — judge `semantic_answer`, scenario kind `semantic_product`, `expect_graph_changed=false`)
- What the agent did: Answered with a graph-grounded description (two-stage path: KSampler `res_multistep`/60 steps → DetailDaemonSamplerNode wraps the sampler for SamplerCustom; listed current widget values `detail_amount=0.1, bias=0.5, start=1, end=1, …`), but **explicitly withheld the substantive answer**: no comparison to standard samplers and no recommended settings. It asked the user for docs and made no edit (`accepted_batch: null`, `graph_unchanged: true`, `no_candidate_reason: route_not_applyable`, `self_assessment.outcome=no_change`).
- Why it failed: The judge's rationale: the answer "declines to provide any actual explanation or recommendation, stating it cannot retrieve authoritative information and therefore will not give specific numbers… the substantive portions of the user's question—how DetailDaemon works compared to standard samplers and what settings to use for a cinematic soundscape—are left unanswered." This is a genuine refusal of the product question, not a judge error: the question was answerable in a graph-grounded way (the agent itself identified `detail_amount` as "the main lever"). Philosophy #5 ("the agent should act") — the agent held the correct diagnosis in its reply and still punted.
- Class: `refusal_or_block` (refusal to answer/recommend; no edit required by the scenario, but the answer was vacuous). The triggering cause is a grounding gap (schema + reference search returned nothing), but the *failure* is the refusal behavior on top of it.
- Root cause (code-level): Model/prompt behavior, not a single file:line defect — the one-step submit contract accepted an answer-only `no_change` outcome (`agent_backend.py` `_terminal` path; `self_assessment.outcome=no_change`). The agent over-applied "don't guess" instead of philosophy #5/#6 (act on graph-local evidence; verification not refusal).
- Evidence:
  - `assessment.json` judge rationale: "While the workflow description of the two-stage path and current settings is grounded in the evidence, the substantive portions of the user's question… are left unanswered, making the response irrelevant and vacuous."
  - `response.json` reply: "I don't have documented evidence for what each widget does or a safe numeric range, so I won't hand you specific numbers — that would be guessing… If you can share the node's docs… I can edit the DetailDaemonSamplerNode directly."
  - `response.json` self_assessment: `{"outcome": "no_change", "note": "Answer-only response. No schema/documentation… could be retrieved…"}`

### audio-audio-processing-with-chatterbox-tts-and-vc-b55994
- Judge verdict: FAIL (judge `edit_intent` **passed**: `correct_node_targeted=true, correct_parameter_changed=true, no_orphaned_wiring=true, value_semantically_matches_intent=true`; terminal fail caused by structural issue `landed_operation_count`: "Expected edit but change_details.landed_operation_count is None; a positive integer is required when graph_unchanged is false.")
- What the agent did: Accepted Δ d1: `remove_node` 428 (SaveAudioMP3) + `add_node` 429 (SaveAudio, wired to `425.AUDIO_0`, `filename_prefix=audio/ComfyUI`) to make the saved output WAV. The edit **landed**: `final.ui.json` contains node 429 (type SaveAudio) and no node 428; executor report `execute.route="adapt"`, `claim_validation.status=ok`, `replacement_used=false`.
- Why it failed: Harness/evidence-capture bug. The edit is correct and the intent judge passed it, but the response envelope carries no `change_details` at all, so the assessor's G0R structural guard fails closed (`graph_unchanged=false` because `accepted_batch` is non-empty, per `executor_response.py:52`). The agent's output was correct; the harness failed it.
- Class: `judge_or_harness_bug`
- Root cause (code-level): In the one-step terminal projector the durable response is a minimal 3-key dict that omits `change_details`:
  - `vibecomfy/executor/agent_backend.py:1094-1098` — `_terminal(...)` passes `durable_response={"reply": reply_text, "session_id": session_id, "route": route}` only (no `change_details`).
  - `vibecomfy/executor/two_step_session.py:1771-1854` (`project_terminal_product`) and `vibecomfy/executor/two_step.py:1257-1261` forward it unchanged into `ImplementationResult.durable_response`.
  - `vibecomfy/executor/contracts.py:2600-2606` — `ExecutorResult.to_dict` lifts `change_details` (listed in `_DURABLE_ENVELOPE_TOP_LEVEL_KEYS`, contracts.py:2534-2556) **only** from `impl.durable_response`; absent here → never reaches the response.
  - `tests/live_agentic_harness/assessor.py:802-825` — G0R guard: `response.get("graph_unchanged") is False` + `_landed_operation_count(response)` None → error issue → verdict fail. `_canonical_route` (assessor.py:238-263) returns `""` (plan is None in one-step mode, contracts.py:2440-2447 → `no_candidate_reason=route_not_applyable`, contracts.py:2514-2515), so no non-edit-route exemption applies.
- Evidence:
  - `assessment.json` issues: `{"check": "landed_operation_count", "detail": "Expected edit but change_details.landed_operation_count is None; a positive integer is required when graph_unchanged is false."}` alongside `{"check": "intent_judge", "detail": "edit_intent passed: The Δ removes the SaveAudioMP3 node (428) and adds a SaveAudio node (n1)…"}`.
  - `response.json` top-level keys contain `accepted_batch`, `graph_unchanged: false`, `no_candidate_reason: route_not_applyable`, `candidate: null` — and **no** `change_details`, `outcome`, or `route`.
  - `final.ui.json`: node 429 `type=SaveAudio` present; node 428 absent; `report.executor.execute.route="adapt"`.

### audio-transcribes-audio-appends-text-regenerates
- Judge verdict: FAIL (criteria: `correct_node_targeted=false, correct_parameter_changed=false, no_orphaned_wiring=true, value_semantically_matches_intent=false`; additional structural issue `graph_changed`: "Expected graph change but response.graph_unchanged is True.")
- What the agent did: Diagnosed the right target — "The 'Apply Whisper' node (uid:71) is currently set to the 'tiny' model… the smallest, fastest, but least accurate Whisper variant… likely the source of the transcription errors." It attempted edits, but per its self-assessment "all edit_node calls were rejected due to unknown field name" — the model widget is exposed only as `widget_0` and the node's schema was unavailable. It then refused and told the user to edit manually. No edit landed: `accepted_batch: null`, `graph_unchanged: true`, `final.ui.json` md5 identical to `original.ui.json`.
- Why it failed: Genuine product failure (model/harness capability gap, honestly surfaced). The Δ is empty; the speech-to-text stage was untouched; the judge correctly failed C1–C3. The agent's refusal was honest (it did not guess a binding name, philosophy #9/#12), but the typed edit tool cannot express "set widget_0" without a schema, and no schema was available.
- Class: `refusal_or_block` (safe block: tool validation rejected the positional/unnamed widget; enabler = schema unavailability / grounding gap). Not a judge error — the judge correctly failed an empty Δ.
- Root cause (code-level): Typed edit-tool validation rejects positional widget refs by design — `vibecomfy/executor/edit_tools.py:250-256` (`_reject_positional`, "…is a positional widget ref — use the named field/binding shown in the render (names over indices)") and `edit_tools.py:313-314` (field `widget_0` rejected before dispatch). With no schema for `Apply Whisper`, no named field exists to target, so every `edit_node` attempt is rejected and the one-step loop ends in a no-change submit (`agent_backend.py` `_terminal` path, `self_assessment.outcome=no_change`).
- Evidence:
  - `response.json` reply: "Unfortunately, the automatic edit could not be applied because the correct field name for the model parameter is unknown (the widget is shown as 'widget_0' but the node's schema is unavailable for verification). Please manually change the model in the ComfyUI canvas."
  - `response.json` self_assessment: `{"outcome": "no_change", "confidence": "high", "note": "Attempted to edit the model parameter of Apply Whisper node but all edit_node calls were rejected due to unknown field name; no further edits allowed."}`
  - `assessment.json` rationale: "The Δ contains no batch statements, so no node was modified; the speech-to-text stage (node 71, Apply Whisper) was untouched…"

### audio-tts-narration-using-indextts-2
- Judge verdict: FAIL (judge `edit_intent` **passed**: all four criteria true — "The Δ modifies node 125, an IndexTTSEmotionOptionsNode, by raising Sad/Happy/Surprised/Angry/Afraid emotion weights, which directly addresses the flat/monotone narration intent… node 125 remains wired into the TTS engine via 126 → 138"; terminal fail caused by the same `landed_operation_count` structural issue).
- What the agent did: Accepted Δ d1 of 5 `set_node_field` ops on node 125 (Sad=0.8, Happy=0.7, Surprised=0.5, Angry=0.4, Afraid=0.3). The edit **landed**: `final.ui.json` node 125 `widgets_values=[0.7, 0.4, 0.8, 0.5, 0.3, 0, 1.2, 0]`; executor `execute.route="adapt"`, `claim_validation.status=ok`, `replacement_used=false`, schema evidence fetched (`tool:node_schema-indexttsemotionoptionsnode`).
- Why it failed: Identical harness bug to b55994 — correct, landed edit failed only because `change_details` is missing from the envelope.
- Class: `judge_or_harness_bug`
- Root cause (code-level): Same chain as b55994: `agent_backend.py:1094-1098` (minimal `durable_response`) → `two_step_session.py:1771-1854` → `two_step.py:1257-1261` → `contracts.py:2600-2606` (nothing to lift) → `assessor.py:802-825` (G0R guard fails closed).
- Evidence:
  - `assessment.json` issues: `landed_operation_count` error + `intent_judge` info pass (rationale quoted above).
  - `response.json` accepted_batch (5 set_node_field ops, `delta_id=d1`, `turn=1`); `graph_unchanged: false`; no `change_details` key.
  - `final.ui.json` node 125 widget values confirm the landed Δ.

### image-animatediff-video-generation-with-vae-d20410
- Judge verdict: FAIL (judge `edit_intent` **passed**: all four criteria true — "The Δ sets node 9 (EmptyLatentImage) batch_size from 16 to 8, which is the AnimateDiff frame count in this graph; named_fields confirms batch_size is the correct field and topology shows no wiring changes or orphans"; terminal fail caused by the same `landed_operation_count` structural issue).
- What the agent did: Accepted Δ d1: `set_node_field` node 9 `batch_size=8` (16→8) to speed test renders. The edit **landed**: `final.ui.json` node 9 `widgets_values=[512, 512, 8]` vs `original.ui.json` `widgets={"widget_0": 512, "widget_1": 512, "widget_2": 16}`; executor `execute.route="adapt"`, `claim_validation.status=ok`.
- Why it failed: Identical harness bug — correct, landed edit failed only because `change_details` is missing from the envelope.
- Class: `judge_or_harness_bug`
- Root cause (code-level): Same chain as b55994/indextts-2 (see above).
- Evidence:
  - `assessment.json` issues: `landed_operation_count` error + `intent_judge` info pass (rationale quoted above).
  - `response.json` accepted_batch: `{"op": "set_node_field", "target": ["", "9", "batch_size"], "value": 8, "turn": 1}`; `graph_unchanged: false`; no `change_details` key.
  - `final.ui.json` node 9 `widgets_values=[512, 512, 8]`.

---

## Batch summary

The dominant failure class in this batch is **judge_or_harness_bug (3 of 5)**: one single harness defect flips three correct, landed, judge-approved edits (b55994, indextts-2, animatediff-vae) to terminal FAIL. The one-step terminal projector hands the executor a minimal `durable_response` (`agent_backend.py:1094-1098` — only `reply`/`session_id`/`route`), so `change_details.landed_operation_count` never reaches the response envelope (the lift in `contracts.py:2600-2606` only reads `impl.durable_response`), and the assessor's G0R structural guard (`assessor.py:802-825`) fails closed on a `None` count for every landed one-step edit. The single highest-leverage fix: make the one-step `_terminal`/`project_terminal_product` path carry the full durable response — or at minimum derive and attach `change_details={"landed_operation_count": N}` from the replayed accepted Δ — so the structural guard sees a positive count and the edit_intent judge's pass becomes the terminal verdict (expect ~3 flips, i.e., +10 points on this run). The remaining two failures are genuine product/behavior gaps: `audio-acestep-detail-daemon` is a refusal to answer a graph-answerable semantic question (philosophy #5 violation — give graph-grounded recommendations instead of punting), and `audio-transcribes` is a safe block where the typed tool rejects the unnamed `widget_0` field with no schema to resolve a named field (philosophy #9 vs. schema-availability gap — needs a sanctioned fallback or schema resolution, not a bar-softening).
