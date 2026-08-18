# Fail analysis batch 2 — DeepSeek Flash (two-step, classify-less pipeline)

**Pipeline under test:** `two_step` live agentic harness, model `deepseek/deepseek-v4-flash` via OpenRouter (`flow_metadata.json` readiness: provider arnold, route openrouter). All 7 runs end in `flow_metadata.status: "executor_failure"`. Every scenario shares one structural fact: **the executor never made a single model call** — `model_attempts: []`, `tool_calls: 0`, `accepted_delta_ids: []`, `candidate: null` in all 7 `response.json` files. All failures are pre-execution budget/harness failures, not agent reasoning failures.

---

## 1. `audio-transcribes-audio-appends-text-regenerates` — [adapt]

**Verdict evidence (issues[] VERBATIM):**
- `"response_ok"` → `"response.ok is False: wall_clock: used 273.24716979207005 of limit 240.0"`
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The Δ is empty (checked=0, no statements, and the diff shows no changes), so no speech-to-text node or parameter was targeted or changed to address the weak transcription; the graph remains connected but the intent is unimplemented. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** Query: `"The transcription has too many errors — the speech-to-text stage seems weak."` Classifier produced a correct adapt plan (`target_node_type: "Apply Whisper"`, `research: true`, 4 search directions). But `evidence.research: {}` is **empty** — the research stage produced zero artifacts — and the wall clock died at 273s (>240s adapt route limit) before any implementation. Judge diff confirms zero node/widget change (11 `class_type` in original = 11 in final). `[INFERENCE]` The wall-clock timer covers the research stage, which burned the entire 240s budget on deepseek-v4-flash research turns; the execute turn never started.

**One-line fix:** Scope the wall clock to the executor's own model turns (or give the research stage its own budget) — `vibecomfy/executor/two_step.py:566-581` (`check_wall_clock` reads `usage.started_at`, default `time.monotonic()` at `BudgetUsage` construction, `two_step.py:475`).

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 2. `audio-tts-narration-using-indextts-2` — [adapt]

**Verdict evidence (issues[] VERBATIM):**
- `"response_ok"` → `"response.ok is False: wall_clock: used 323.27594433305785 of limit 240.0"`
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The delta_replay claims no changes were made (Diff: No changes, verified: null), so no node was targeted, no parameter was changed, and no new engaging configuration was applied despite the intent requesting more engaging narration. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** Query: `"The narration sounds flat and monotone — can you make it more engaging?"` Same signature as #1: correct adapt plan naming `CharacterVoicesNode`, `IndexTTSEmotionOptionsNode`, `QwenEmotionNode` (`research: true`), but `evidence.research: {}` empty, wall clock exhausted at 323s (83s over limit) with `model_attempts: []`. Graph untouched (21 `class_type` both sides). The plan was actually viable (emotion widgets exist, e.g. node 125 `IndexTTSEmotionOptionsNode` `widget_6: 1.2` speed) — the agent never got to touch them.

**One-line fix:** Same as #1 — wall-clock budget must exclude research-phase time; `two_step.py:566-581` / route table `two_step.py:295+` (adapt = 240s).

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 3. `image-animatediff-image-to-video-with-latent-composi-17dc9b` — [inspect]

**Verdict evidence (issues[] VERBATIM):**
- `"response_ok"` → `"response.ok is False: Agent worker timed out after 240 seconds."`
- `"semantic_answer"` → `"semantic_answer failed: The answer 'Agent worker timed out after 240 seconds.' is substantively empty and constitutes a refusal/failure to address the question; it names no nodes, makes no comparison, and provides no technical content. criteria={'grounded': False, 'relevant': False, 'correct': False}"`

**Root cause:** Query: `"How does the latent compositing approach here compare to using an init image directly in the video latent space? Which gives better temporal coherence?"` Pure explain task (`inspect`, `research: false`, `implement: false`, effort low). `evidence.graph_inspection.used_for_reply: true` — **the inspection succeeded**; the worker-level watchdog (`runtime/watchdog.py`, 240s) then killed the turn before the reply model call returned. No research/edits needed; this scenario only needed one model call to write the answer. `[INFERENCE]` Provider latency on the reply generation (or per-node inspection overhead) exceeded the 240s worker ceiling; the route's own budget is only 60s (`two_step.py:241-248`), which was evidently not the gate that fired.

**One-line fix:** For inspect/explain routes, run the single reply generation as a bounded call with a shorter watchdog or retry — raise the worker ceiling / decouple the watchdog from model-call latency; `vibecomfy/runtime/watchdog.py:267-268` (per-node elapsed).

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 4. `image-animatediff-video-generation-with-vae-d20410` — [revise]

**Verdict evidence (issues[] VERBATIM):**
- `"response_ok"` → `"response.ok is False: wall_clock: used 208.2777982079424 of limit 180.0"`
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The accepted Δ is empty (checked=0, no mismatches) and the pre/post Diff both report 'No changes', so no node was targeted and no frame-count parameter was changed from 16 to 8. Wiring remains intact, but the intent is entirely unimplemented. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** Query: `"Reduce the number of frames from 16 to 8 for quicker test renders."` — the simplest edit in the batch: one widget on `ADE_AnimateDiffCombine` (`target_node_type` locked, `research: false`, effort low). It still died at 208s (>180s revise limit) with zero model attempts. This is the cleanest proof that **the wall-clock timer includes pre-execute time** (classification of a 24-node graph): a single-widget edit cannot consume 208s of executor time it never started (`budget_usage.wall_clock_seconds: 0`). Graph untouched (24 `class_type` both sides).

**One-line fix:** Start `BudgetUsage.started_at` at the first executor model turn, not at execute-turn construction (`agent_backend.py:578`, `two_step.py:475`); or subtract classification/planning elapsed from the route ceiling.

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 5. `image-dual-checkpoint-xl-image-generation-with-refin-c9df19` — [research]

**Verdict evidence (issues[] VERBATIM):**
- `"response_ok"` → `"response.ok is False: tool 'hivemind_search' per-message call cap (3)."`
- `"semantic_answer"` → `"semantic_answer failed: The answer is a tool error message ('tool hivemind_search per-message call cap (3)') and contains no substantive claims, technical comparison, or workflow analysis grounded in the provided evidence. It does not address the user's question about refiner models, tradeoffs, or LoRA timing, and is technically vacuous. criteria={'grounded': False, 'relevant': False, 'correct': False}"`

**Root cause:** Query asks about newer SDXL refiner models + refiner-vs-single-checkpoint tradeoffs + LoRA timing (explicitly "just research"). Plan set 3 search directions — the agent's first research message attempted ≥4 `hivemind_search` calls and tripped `PER_TOOL_CALL_CAPS["hivemind_search"] = 3` (`two_step.py:115-128`, raised at `two_step.py:531-549`). The cap error **became the final answer**: no partial synthesis from the searches already returned, no second message, no fallback to the rich `known_graph_context` (juggernautXL + sd_xl_refiner + Power Lora Loader). `evidence.research: {}` — nothing retained.

**One-line fix:** On research routes, treat per-tool cap as "continue in next message" or fall back to answering from graph context + partial evidence, instead of propagating `BudgetExceeded` as the reply — `two_step.py:542-549` (raise site) / research-stage caller `core.py:1066-1110`.

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 6. `image-gemini-prompt-splitter-and-text-display-workfl-caae97` — [research]

**Verdict evidence (issues[] VERBATIM):**
- `"response_ok"` → `"response.ok is False: tool 'hivemind_search' per-message call cap (3)."`
- `"semantic_answer"` → `"semantic_answer failed: The answer is a vacuous error message ('tool hivemind_search per-message call cap (3)') that makes no substantive claims about Gemini vs Claude, does not address the user's question about trade-offs, and contains no information grounded in the workflow evidence. It fails all three criteria. criteria={'grounded': False, 'relevant': False, 'correct': False}"`

**Root cause:** Query: `"...compare Gemini to Claude for generating complex, multi-part image prompts... Just research, don't modify the workflow."` Identical signature to #5: plan has **5** search directions (`Gemini vs Claude ...`, rate limits, cost, structure, Claude multi-part) — the first message burned the 3-call cap before finishing direction #2, and the raw cap error became the reply. Nothing grounded, `evidence.research: {}`. Gemini-vs-Claude tradeoffs are also largely answerable from `known_graph_context` (GeminiNode + VRGDG_PromptSplitter_General) — no fallback was attempted.

**One-line fix:** Same as #5 (`two_step.py:542-549`) + bias research prompts to ≤3 directions per message or make the cap message-scoped with automatic continuation.

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 7. `image-image-comparison-and-enhancement-with-florence-007018` — [revise]

**Verdict evidence (issues[] VERBATIM):**
- `"response_ok"` → `"response.ok is False: output_tokens: used 11943 of limit 8000"`
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The Δ is empty (delta_replay.verified is null, checked is 0, mismatches empty, and diff lens shows 'No changes' between identical pre/post topologies), meaning no nodes were added, replaced, or modified to introduce independent filter weights or a multi-input weighted blend; the graph remains structurally identical without any edit implementing the intent. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': False}"`

**Root cause:** Query: `"Restructure the blending logic so that instead of a single composite, the user can adjust the contribution of each filter (saturation, invert, high-pass, sharpen, normal map) independently using float sliders..."` — a legitimate multi-node restructure of an 86-node graph (86 `class_type` both sides, unchanged). The agent's single generation attempt produced 11,943 output tokens (>8000 revise cap, `check_output_tokens` at `two_step.py:552-563`) — i.e., it tried to emit the full replacement graph/diff in one shot and was cut off before any delta was committed (`accepted_delta_ids: []`). No incremental apply happened (`apply_batches: 0`). `[INFERENCE]` The harness contract encourages one monolithic submit for a large edit; a streaming/partial-apply mode would have committed the first valid batch before the cap.

**One-line fix:** For `allows_python_edits` routes, emit and validate deltas incrementally (commit per-batch before output-token exhaustion) or raise `max_output_tokens` for the revise route — `two_step.py:287` (revise `max_output_tokens`) / `check_output_tokens` `two_step.py:552-563`.

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## Ranking by fix leverage (moves most scenarios)

1. **Wall-clock budget scoping** (4 scenarios: #1, #2, #3, #4) — the timer includes classification/research/worker overhead before the executor's first model call (proven by #4: a one-widget edit died at 208s with 0 model attempts; and by #1/#2 where `evidence.research: {}` is empty yet 273–323s elapsed). Fix at `two_step.py:566-581` + `two_step.py:475` (`BudgetUsage.started_at`): measure per model turn, or give the research stage its own budget, or subtract planning time. **Also fixes the `per_tool_calls` scenarios' cousin problem** (research stage budget separation).
2. **Research-route cap resilience** (2 scenarios: #5, #6) — `hivemind_search` cap of 3 (`two_step.py:115-128`, raised `two_step.py:542-549`) hard-fails the turn and the raw error string becomes the final answer. Fix: auto-continue across messages on cap, or fall back to answering from `known_graph_context` when research is exhausted.
3. **Output-token headroom for large-graph edits** (1 scenario: #7) — 11,943/8,000 tokens on an 86-node restructure with zero incremental commits. Fix: incremental delta commit or route-specific `max_output_tokens` (`two_step.py:287`).

**Bottom line:** 7/7 are `judge_fail` with an empty Δ — the two-step pipeline is currently spending its entire budget *before* the executor acts (classification + research + worker overhead), then failing closed. No scenario shows a wrong edit, refusal, or agent reasoning defect; all are harness budget-accounting and cap-policy failures. First fix (#1) addresses 57% of the batch.

**Tags:** all 7 — `OUTCOME: EXPECTED-REMAINING` (first analysis run; no bar-softening proposed; fixes are pipeline-side).
[launch_hermes_agent] done in 194.8s
