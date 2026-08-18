# Fail analysis batch 3 — DeepSeek Flash (two-step pipeline, classify-less run)

**Artifact root:** `/private/tmp/vc-twostep/out/compare-pipeline-modes/two-step-50/two_step` · **Model:** `deepseek/deepseek-v4-flash` via OpenRouter · **Contract:** `agent_edit_turn_v2`
**Method:** each scenario read via assessment.json (verbatim issues), response.json (failure_kind/stage/plan), classification.json (locked route), request.json (query), flow_metadata.json (status), plus targeted greps on original/final.ui.json to verify the Δ. All 7: `graph_unchanged: true`; `model_attempts: []` (no retries anywhere).

---

## 1. image-image-editing-with-qwen-image `[adapt]`

**Verdict evidence (verbatim):**
- `"response_ok"`: `"response.ok is False: output_tokens: used 14533 of limit 12000"`
- `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"`: `"edit_intent failed: The accepted Δ is empty (verified: null, checked: 0, mismatches: [], and both pre/post show 'No changes'), so no node was targeted, no parameter was changed..."`

**Root cause:** Query: *"The added soldier looks pasted on — it doesn't match the scene's lighting."* Classifier locked `route: adapt, task: edit_graph, implement: true` (classification.json). Executor died at claim validation with `failure_kind: output_tokens`, `failure_stage: execute`, `no_candidate_reason: implementation_failed`. `evidence.research: {}`, `graph_inspection: {}`, `tool_calls: 0`, `model_attempts: []` — the 14.5k tokens were consumed in one generation before any evidence/tool work was recorded `[INFERENCE]`. UI diff: empty (verified by judge + no candidate). The research+plan preamble of the adapt route blew the 12k cap before the edit tool was ever called.

**One-line fix:** Raise the `output_tokens` limit (observed `12000`, response.json `error`) for implement routes, or make the research phase write evidence incrementally so a cap hit still yields a candidate. `[INFERENCE: executor limit constant]`

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## 2. image-image-processing-with-sharpening-film-grain-an-9aa0f1 `[research]`

**Verdict evidence (verbatim):**
- `"response_ok"`: `"response.ok is False: wall_clock: used 220.24696133297402 of limit 180.0"`
- `"semantic_answer"`: `"semantic_answer failed: The answer is 'wall_clock: used 220.24696133297402 of limit 180.0', which is a system diagnostic message containing no substantive content..."`

**Root cause:** Query asks for sharpening-alternative research with tradeoffs. Route `research`, `implement: false` — but the session never produced an answer: `failure_kind: wall_clock`, `failure_stage: execute`, `evidence.research: {}`, `reply` = the bare diagnostic string. The 180s budget was exhausted (220.2s) before any research evidence or answer was written; the diagnostic string leaked through as the reply. flow_metadata: `status: executor_failure`. No UI diff (not expected; `expect_graph_changed: false` — failure is purely the missing product).

**One-line fix:** Bump the `wall_clock` budget (`limit 180.0`) for research routes and add a graceful-degradation path so a budget hit returns a partial answer instead of echoing the diagnostic. `[INFERENCE: executor limit constant]`

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## 3. image-qwen-image-inpainting-with-controlnet-09fc64 `[research]`

**Verdict evidence (verbatim):**
- `"response_ok"`: `"response.ok is False: tool 'hivemind_search' per-message call cap (3)."`
- `"semantic_answer"`: `"semantic_answer failed: The answer is an empty tool-call status message ('tool 'hivemind_search' per-message call cap (3).') containing no substantive technical content..."`

**Root cause:** Query explicitly asks *"Before editing anything, research the best techniques..."* — a research-precedent task, correctly routed (`research`, `task: research_precedent`). Executor hit `failure_kind: per_tool_calls` at `failure_stage: execute`; `evidence.research: {}` — the model made 3 hivemind_search calls in one message, hit the per-message cap, and the whole turn collapsed to the cap diagnostic as `reply`. Same pattern as #2: a limiter hit surfaces a system string instead of any answer; judge gets nothing to grade.

**One-line fix:** Raise `hivemind_search` per-message cap (observed `(3)`) or allow the agent to continue in follow-up messages, and convert cap hits into "summarize what you have" fallbacks. `[INFERENCE: tool-call limiter config]`

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` (tool-call cap) · `OUTCOME: EXPECTED-REMAINING`

---

## 4. image-style-transfer-using-ip-adapter `[respond]`

**Verdict evidence (verbatim):**
- `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
- `"outcome_kind"`: `"Expected edit but outcome.kind='noop'."`
- `"intent_judge"`: `"edit_intent failed: The accepted Δ is empty (checked=0, no ops, and both pre/post Diff views report 'No changes'), so no node or parameter was modified to fix the statue style..."`

**Root cause:** Query: *"The statue style isn't coming through at all — it just looks like a normal photo."* — a complaint demanding a fix, but the classifier locked `route: respond, implement: false, task: respond` (classification.json: `"Respond to correction by outputting valid classify JSON."`). The executor then produced an excellent diagnosis (StyleModelApply default strength 1.0, prompt/denoise balance, concrete fix `"raise the style strength on StyleModelApply (e.g. try 1.4–1.8)"`) and explicitly declined to apply it: `"I can make that change if you'd like — just confirm the strength value"`. `outcome.kind: noop`, `no_candidate_reason: route_not_applyable`, flow_metadata `status: success` — the harness considers this a *successful* no-op turn. Judge requires a graph change. Root cause is the route contract: a correction/complaint turn was classified as `respond` and respond is structurally non-applyable, so a fully-specified Δ (target node + value) was thrown away.

**One-line fix:** In the classifier (classification.json producer), treat output-quality complaints on `expect_graph_changed` scenarios as `edit/adapt` rather than `respond`; or in the executor's respond branch, emit an applyable candidate when the reply names a target node + widget value. `[INFERENCE: classify step + respond executor branch]`

**Tag:** `CLASS: incomplete | NO-OP` (misrouted to respond; root cause is route assignment) · `OUTCOME: EXPECTED-REMAINING`

---

## 5. image-two-stage-qwen-image-generation `[adapt]`

**Verdict evidence (verbatim):**
- `"response_ok"`: `"response.ok is False: output_tokens: used 16173 of limit 12000"`
- `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"`: `"edit_intent failed: The accepted Δ is empty — no nodes were added, replaced, or modified..."`

**Root cause:** Query: *"The image gets distorted and the faces look wrong after the upscale/refinement stage."* Route `adapt`, `implement: true`, `task: research_precedent`. Identical failure mode to #1: `failure_kind: output_tokens`, `failure_stage: execute`, 16173 > 12000, `research: {}`, `tool_calls: 0`, `model_attempts: []`, no candidate (`implementation_failed`). The 5 search directions + known_graph_context preamble consumed the budget before any tool call or edit. UI diff empty.

**One-line fix:** Same as #1 — raise `output_tokens` cap for adapt routes and/or stream research evidence so an overflow still leaves an editable candidate. `[INFERENCE: executor limit constant]`

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## 6. multi-3d-gaussian-splatting-from-video-with-hunyuan-432652 `[research]`

**Verdict evidence (verbatim):**
- `"semantic_answer"`: `"semantic_answer failed: The answer's claim that HWMInference's widget_1='randomize' 'can resample noise independently per frame and is a classic cause of flicker' is not supported by the provided workflow/schema evidence, which only shows the widget value but no information about how that mode affects per-frame noise; this assertion is ungrounded. criteria={'grounded': False, 'relevant': True, 'correct': True}"`

**Root cause:** The one genuinely substantive failure. Route `research` (correct; query asks to investigate + suggest). Executor `ok: true`, 4 tool calls, 7607 output tokens, 5 continuations; reply is detailed, `relevant: True, correct: True`. Sole failure: `grounded: False` — the claim that `widget_1='randomize'` resamples noise per-frame (causing flicker) goes beyond the schema evidence. Note the widget value itself is factual — `final.ui.json` line 362 still shows `"randomize"` on HWMInference — but the *causal semantics* of that mode are asserted, not cited. (Reply was also truncated at 5 suggestions — `...[truncated]`.) No graph change expected/needed. This is answer-quality, not execution: the model extrapolated a mechanism it couldn't source.

**One-line fix:** Add a grounding constraint to the research-answer prompt/validator: causal claims about a node's widget semantics must cite schema/registry/docs, else be framed as hypotheses. `[INFERENCE: research answer prompt or grounding validator]`

**Tag:** `CLASS: judge_fail | PROMPT-GAP` (ungrounded causal assertion; otherwise correct/relevant) · `OUTCOME: EXPECTED-REMAINING`

---

## 7. multi-3d-preview-and-image-output-workflow-d93baf `[revise]`

**Verdict evidence (verbatim):**
- `"response_ok"`: `"response.ok is False: Agent worker timed out after 240 seconds."`
- `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"`: `"edit_intent failed: The Δ contains no ops (verified null, checked 0, mismatches []) and the pre/post diff shows 'No changes', so no SaveGLB node was targeted and no filename_prefix was changed to '3d/moge-top-down'..."`

**Root cause:** The easiest task in the batch — a single widget edit, perfectly scoped: `route: revise`, `effort: low`, `research: false`, target `SaveGLB` node 21, `widget_0: '3d/ComfyUI' → '3d/moge-top-down'` (classification.json). Executor returned `failure_kind: ExecuteError`, `"Agent worker timed out after 240 seconds."`, `failure_stage: execute`, `tool_calls: 0`. The trivial edit never happened because the worker itself died on the wall clock. `final.ui.json` still carries `'3d/ComfyUI'` (lines 49, 354, 370, 376) — Δ confirmed empty. flow_metadata: `executor_failure`.

**One-line fix:** Raise the agent-worker timeout (observed `240 seconds`) and/or add retry with a tighter prompt for trivial widget edits so a slow first LLM response doesn't kill an otherwise one-shot edit. `[INFERENCE: worker timeout constant in harness]`

**Tag:** `CLASS: incomplete | INFRA` (worker timeout; adjacent to BUDGET-EXHAUSTION) · `OUTCOME: EXPECTED-REMAINING`

---

## Ranking by fix leverage

1. **Executor budget/limit tuning (moves 5/7 scenarios: #1, #2, #3, #5, #7).** All five are limit hits — `output_tokens` 12000 (×2), `wall_clock` 180s, `per_tool_calls` cap 3, worker timeout 240s — with an identical symptom: the limit's diagnostic string becomes the reply and no product exists. Raising limits **and** adding graceful degradation (return partial research/answer on cap hit, never echo the diagnostic) is the single highest-leverage change.
2. **Respond-route applyability (1/7: #4).** Allow a `respond` turn that names a concrete node+value (StyleModelApply strength 1.4–1.8) to emit an applyable candidate — or stop routing complaint-turns to `respond` when the scenario expects a graph change. High per-scenario value, low blast radius.
3. **Research-answer grounding (1/7: #6).** Constrain causal claims about widget semantics to cited schema/docs evidence. Only fixes one scenario, but it's the only true `judge_fail` with a graded product.

**Cross-cutting note:** 6 of 7 failures are pre-judge execution failures (`incomplete`) — the model never got to demonstrate edit/answer ability; only #6 produced a graded product. The batch is dominated by harness limits, not reasoning quality. No bar-softening or judge changes proposed.
[launch_hermes_agent] done in 96.7s
