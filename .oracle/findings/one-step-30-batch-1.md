# Fail analysis batch 1 — DeepSeek Flash (two-step classify-less pipeline)

**Run:** `compare-pipeline-modes/two-step-50/two_step` · **Model:** `deepseek/deepseek-v4-flash` via OpenRouter (flow_metadata: `route: openrouter`, `dispatcher: real`, model_behavior `agentic`, contract `agent_edit_turn_v2`) · **Mode:** one-step (classify-less) — both CLASS tiers applied per scenario.

## Summary table

| # | Scenario | Route | failure_kind (stage) | Used/Limit | Δ UI |
|---|---|---|---|---|---|
| 1 | 3d-3d-model-generation-and-preview-workflow-cc0df7 | revise | output_tokens (execute) | 9955/8000 | none (53,066 B = 53,066 B) |
| 2 | 3d-3d-shape-generation-and-export-workflow-8800a9 | revise | output_tokens (execute) | 9907/8000 | none (25,601 B = 25,601 B) |
| 3 | 3d-converts-image-to-3d-model | adapt | replacement_attempts (execute) | 1/1 | none (471 B = 471 B) |
| 4 | 3d-generates-a-3d-mesh-from | adapt | wall_clock (execute) | 256.1s/240s | none (1,831 B = 1,831 B) |
| 5 | audio-acestep-audio-generation-and-processing-workfl-1b1360 | adapt | per_tool_calls (execute) | hivemind_search 3 | none (151,818 B = 151,818 B) |
| 6 | audio-acestep-audio-generation-with-detail-daemon-f0859f | research | output_tokens (execute) | 8449/8000 | none (48,181 B = 48,181 B) |
| 7 | audio-audio-processing-with-chatterbox-tts-and-vc-b55994 | revise | output_tokens (execute) | 10463/8000 | none (23,475 B = 23,475 B) |

**All 7:** `candidate: null`, `model_attempts: []`, `tool_calls: 0`, `deepseek_usage` all-zero, `graph_unchanged: true`, `no_candidate_reason: implementation_failed` (#6: `route_not_applyable`). `original.ui.json` and `final.ui.json` are byte-identical in every scenario (verified line count + file_size). Every failure was raised by the executor's **first-message budget check** (`claim_validation.status: failed`) before any tool result was recorded.

**Cross-cutting root cause `[INFERENCE]`:** the agent-edit contract re-emits the full graph render in the edit payload (see `tests/fixtures/editor_sessions/*/model_request.json`: "Current scratchpad Python (full render)"). DeepSeek Flash's single first response for these graphs exceeds the 8000-token per-message slice, so `check_output_tokens` (projected `usage.output_tokens + tokens > budget.max_output_tokens`, `vibecomfy/executor/two_step.py:552-563`) kills the session before any candidate exists. The `used > limit` values (9955, 9907, 10463, 8449) are consistent with one oversized message, not accumulation. The other three budgets (replacement, wall-clock, per-tool cap) are the same class of first-message death.

---

## 1. `3d-3d-model-generation-and-preview-workflow-cc0df7` [revise]

**Verdict evidence (assessment.json `issues[]`, verbatim):**
> `"response_ok"`: `"response.ok is False: output_tokens: used 9955 of limit 8000"`
> `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
> `"intent_judge"`: `"edit_intent failed: The accepted Δ is empty (delta_replay has no statements and pre/post diff says 'No changes'), so no Rodin3D generator node was targeted or parameter changed to swap Rodin Large to Rodin Fusion; only C4 holds since the unchanged topology remains connected. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** Classification was correct and specific — `plan_summary`: *"Change the model widget on the Rodin3D_Regular node from 'rodin large' to 'rodin fusion', preserving all existing downstream edges…"* (target `Rodin3D_Regular`, route `revise`, effort low — the user query: *"Swap the Rodin3D generation model from Rodin Large to Rodin Fusion…"*). The executor never got to implement: `failure_kind: output_tokens`, `failure_stage: execute`, zero tool calls, zero attempts — the first message's 9955 output tokens blew the 8000 cap (graph is 1787 lines / 53 KB, so a full-render payload is ~10 K tokens). No candidate, no Δ; judge correctly rejects with only `no_orphaned_wiring` passing vacuously.

**One-line fix:** raise the per-message `max_output_tokens` for the `revise` route (`vibecomfy/executor/two_step.py:287`, value redacted in source view but enforced at 8000) to ≥16000 — or shrink the edit payload to a delta (nodes touched) instead of the full graph render, which is the durable fix.

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## 2. `3d-3d-shape-generation-and-export-workflow-8800a9` [revise]

**Verdict evidence (verbatim):**
> `"response_ok"`: `"response.ok is False: output_tokens: used 9907 of limit 8000"`
> `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
> `"intent_judge"`: `"edit_intent failed: The accepted Δ is empty (checked 0, verified null, no mismatches) and both pre/post views show 'No changes' in the diff, so no node or parameter was modified to set the UltraShapeRefine strength to 0.4. The graph remains connected, but the intent is not implemented. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** Identical pattern to #1. Correct locked route (`revise`, `plan_summary`: *"Set UltraShapeRefine strength widget to 0.4."` — a trivial one-widget edit) but `failure_kind: output_tokens` 9907/8000 on the first message; graph 1057 lines/25.6 KB. Zero attempts, zero tool calls; nothing was ever applied.

**One-line fix:** same as #1 — `vibecomfy/executor/two_step.py:287` (`revise.max_output_tokens` 8000→≥16000) or delta-only edit emission. A one-widget change should never need a 9.9 K-token message; payload compaction alone likely clears it.

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## 3. `3d-converts-image-to-3d-model` [adapt]

**Verdict evidence (verbatim):**
> `"response_ok"`: `"response.ok is False: replacement_attempts: used 1 of limit 1"`
> `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
> `"intent_judge"`: `"edit_intent failed: The accepted Δ is empty (checked 0, pre/post both report 'No changes'), so no node was targeted or parameter changed to add sharper surface detail; the graph remains connected vacuously as an unchanged topology. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** Route `adapt` (research_precedent) with a plan to *"Research Rodin3D_Regular settings for enhancing surface detail, then adjust parameters to reduce smoothness and add sharpness."* `failure_kind: replacement_attempts` 1/1 — the single `max_replacements=1` slot was consumed without a valid candidate (zero recorded attempts/tool calls, so the first emitted edit was rejected/oversized `[INFERENCE]`). Secondary weakness: the plan targets no concrete parameter (graph widgets are `widget_0: 0, widget_1: "PBR", widget_2: "200K-Triangle"` — nothing named "smoothness"/"sharpness"), so even with budget the edit target is underspecified (`[INFERENCE]` PROMPT-GAP would be the next-class candidate if budget were fixed).

**One-line fix:** `vibecomfy/executor/two_step.py:316` (`adapt.max_replacements` 1→2) plus the #1 payload fix; optionally require the classifier to name a concrete widget in `plan_summary` for adapt plans.

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## 4. `3d-generates-a-3d-mesh-from` [adapt]

**Verdict evidence (verbatim):**
> `"response_ok"`: `"response.ok is False: wall_clock: used 256.09719400003087 of limit 240.0"`
> `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
> `"intent_judge"`: `"edit_intent failed: The accepted Δ contains no operations (checked: 0) and the diff shows no changes, so no node or parameter was modified to address the floating bits/noise; the only passing criterion is that the unchanged graph remains structurally connected. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** Route `adapt` targeting `KSampler` with research goal on Hunyuan3Dv2 KSampler/ModelSamplingAuraFlow settings. `failure_kind: wall_clock` 256.1s > 240s — the first message (research phase + edit generation) exceeded the per-message wall clock (`adapt.max_wall_clock_seconds=240.0`, `two_step.py:313`). Graph is tiny (116 lines), so the time went to the slow first LLM call/search round-trips `[INFERENCE]`; zero attempts recorded.

**One-line fix:** raise `max_wall_clock_seconds` for `adapt` (`vibecomfy/executor/two_step.py:313`, 240→360) and/or cap `search_directions` (this plan emitted 4 directions; each maps to a search call) so research finishes inside budget.

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## 5. `audio-acestep-audio-generation-and-processing-workfl-1b1360` [adapt]

**Verdict evidence (verbatim):**
> `"response_ok"`: `"response.ok is False: tool 'hivemind_search' per-message call cap (3)."`
> `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
> `"intent_judge"`: `"edit_intent failed: The Δ is empty — no node was added or modified. The pre and post IR views are identical, so no noise reduction pass was integrated, no parameters were changed, and the intent is not implemented. The graph remains connected (no orphaned wiring), but the edit completely fails to achieve the desired outcome. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** Route `adapt` (insert a spectral-gating noise-reduction node before AudioSeparation/VocalAndSoundRemover branches — the largest graph here, 6476 lines / 151 KB). The classifier emitted **4 `search_directions`**; the model fired one `hivemind_search` per direction in a single message and hit the per-message cap of 3 (`PER_TOOL_CALL_CAPS: {"hivemind_search": 3}`, `two_step.py:115-128`) before any implementation. `research` evidence is empty — results never landed. Plan structure (4 directions > 3-call cap) guarantees this failure for any model that maps directions 1:1 to calls.

**One-line fix:** either raise the cap at `vibecomfy/executor/two_step.py:117` (`hivemind_search: 3` → 5) or clamp `search_directions` to ≤3 in the classifier; the cap-vs-directions mismatch is the deterministic trigger.

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## 6. `audio-acestep-audio-generation-with-detail-daemon-f0859f` [research]

**Verdict evidence (verbatim):**
> `"response_ok"`: `"response.ok is False: output_tokens: used 8449 of limit 8000"`
> `"semantic_answer"`: `"semantic_answer failed: The answer field contains only the placeholder text 'output_tokens: used 8449 of limit 8000' with no actual response content, so it addresses none of the question and makes no substantive claims to evaluate against the workflow evidence. criteria={'grounded': False, 'relevant': False, 'correct': False}"`

**Root cause:** Pure research route (`intent: research`, `implement: false`, `apply: false` — semantic-product scenario, no graph change expected; `expect_graph_changed: false`). The research answer itself (DetailDaemonSamplerNode mechanism + cinematic-soundscape settings) exceeded 8000 output tokens on the first message (`research.max_output_tokens`, `two_step.py:262`). `reply` contains only the placeholder; no answer was ever returned, so the semantic judge correctly fails all three criteria.

**One-line fix:** raise `research.max_output_tokens` (`vibecomfy/executor/two_step.py:262`, 8000→≥16000) or instruct research replies to cap at ~6 K tokens; the model tried to emit a comprehensive research memo and was truncated by the budget.

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## 7. `audio-audio-processing-with-chatterbox-tts-and-vc-b55994` [revise]

**Verdict evidence (verbatim):**
> `"response_ok"`: `"response.ok is False: output_tokens: used 10463 of limit 8000"`
> `"graph_changed"`: `"Expected graph change but response.graph_unchanged is True."`
> `"intent_judge"`: `"edit_intent failed: The Δ contains no batch statements (checked=0, no ops), and the post-edit topology still shows SaveAudioMP3 (428) saving from 425.0 to 428.audio, so no node or parameter was changed to switch output to WAV. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** The simplest possible edit — user query *"Change the output audio format from MP3 to WAV."*, plan *"Replace the SaveAudioMP3 node (id 428) with a SaveAudioWAV node"* — killed by `output_tokens` 10463/8000, the worst of the batch. Graph is 902 lines/23.5 KB; the full-render edit payload alone (~10.5 K tokens) exceeds the cap before any apply. Worst-case evidence that the 8000-token slice is smaller than the contract's own payloads.

**One-line fix:** same as #1/#2 — `vibecomfy/executor/two_step.py:287` (`revise.max_output_tokens` 8000→≥16000), with delta-only emission as the durable fix.

**Tag:** `CLASS: incomplete | BUDGET-EXHAUSTION` · `OUTCOME: EXPECTED-REMAINING`

---

## Ranking by fix leverage

1. **Raise per-message `max_output_tokens` (8000→≥16000) for `revise`/`research`/`adapt`** — `vibecomfy/executor/two_step.py:287, 262, 311` (values redacted `***` in source view; enforced at 8000 per failure messages). Directly unblocks **4/7** (#1, #2, #6, #7) and removes the pressure behind #3 (replacement consumed on an oversized first edit) and #4 (oversized/slow first message). The single highest-leverage change.
2. **Shrink edit payload to delta-only (touched nodes/links) instead of full graph render** — fixes the root cause of the same 6/7 and trims wall-clock; requires changing the agent-edit scratchpad contract, not just a constant.
3. **Clamp classifier `search_directions` to ≤ per-tool caps (or raise `hivemind_search: 3` → 5, `two_step.py:117`)** — deterministic fix for #5 (4 directions vs 3-call cap); also protects the adapt/research routes' wall-clock.
4. **`max_replacements` 1→2 (`two_step.py:316`)** and **`max_wall_clock_seconds` 240→360 (`two_step.py:313`)** — cheap insurance for #3 and #4 respectively.

No bar-softening or judge changes proposed; the judge verdicts are correct on all 7 (empty Δ, unchanged graph, placeholder answer). All seven are budget/contract failures at the executor's first message, not semantic misses — fixing #1 (output-token slice) plus #3 (direction/cap mismatch) would move all 7.
[launch_hermes_agent] done in 153.6s
