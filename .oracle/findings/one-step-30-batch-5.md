# Fail analysis batch 5 — DeepSeek Flash (two-step, classify-less)

Both scenarios in this batch failed identically: **`failure_kind=output_tokens` at `failure_stage=execute`**, with **zero tool calls, zero model attempts, zero apply batches** — the model's single generation blew its per-route output-token ceiling, the harness hard-failed, and no candidate/reply was ever produced. The classification layer (the thing this pipeline is testing) was **not** the failure point; both routes were locked correctly and matched the query intent.

---

## 1. multi-svd-image-to-video-with-animation-builder-99e2a9 `[inspect]`

### Verdict evidence (assessment.json issues[], verbatim)
- `"response_ok"` → `"response.ok is False: output_tokens: used 4769 of limit 4000"` (severity error)
- `"semantic_answer"` → `"semantic_answer failed: The 'answer' field contains only a token usage placeholder, not a substantive response; it makes no claims about the workflow, fails to address the flickering/jitter diagnosis, and thus is empty of grounded content. criteria={'grounded': False, 'relevant': False, 'correct': False}"`

Judge verdict: `fail`; `scenario_kind: semantic_product`; `expect_graph_changed: false`.

### Root cause
Query: *"The generated video has severe flickering and jittery motion, with frames occasionally going black. What in the workflow could be causing this?"* — a pure explain/diagnose task. Classification was correct (`route: inspect`, `task: inspect_graph`, `intent: explain_graph`, `implement: false`). The graph-inspection evidence **was** collected (`evidence.graph_inspection.used_for_reply: true`), but the final answer generation consumed 4769 output tokens against a 4000 ceiling; the provider truncated, the executor raised `output_tokens`, and the entire reply was discarded and replaced by the placeholder string `"output_tokens: used 4769 of limit 4000"` (`response.reply`, `response.message`). `model_attempts: []`, `tool_calls: 0` — no retry/continuation path exists for truncation. UI diff: `original.ui.json` and `final.ui.json` are byte-identical (55,382 bytes / 2,516 lines); `graph_unchanged: true` (correct for inspect — no edit was expected). The judge therefore saw only the error placeholder as the "answer." The diagnosis itself never reached the judge.

### One-line fix hypothesis
In the two-step executor's token-budget config, raise the `inspect` route `max_output_tokens` (4000 → ≥8k) and, more importantly, make `finish_reason=length` retryable: on `output_tokens` at the reply step, retry once with a "concise answer" instruction or continue the truncated generation instead of hard-failing with a placeholder — locate via the literal error string `"used %d of limit %d"` in the executor/claim-validation path (`response.json` lines 56–59 show `claim_validation.failure_kind: "output_tokens"`).

### Tags
`CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 2. multi-svd-image-to-video-with-webp-and-png-output-bd3afb `[adapt]`

### Verdict evidence (assessment.json issues[], verbatim)
- `"response_ok"` → `"response.ok is False: output_tokens: used 16555 of limit 12000"` (severity error)
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."` (severity error)
- `"intent_judge"` → `"edit_intent failed: The delta is empty — no claim of any change at all — so it cannot demonstrate a modification to the SaveImage node (10) input from a placeholder to the video's first frame. While the topology is not orphaned, zero of the required edit actions are present in the Δ. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

Judge verdict: `fail`; `scenario_kind: edit`; `expect_graph_changed: true`.

### Root cause
Query: *"Can you make the static PNG output save the first frame of the generated video instead of a separate placeholder image?"* Classification was correct and ambitious (`route: adapt`, `task: edit_graph`, `intent: edit`, `implement: true`, `research: true` with a valid `research_goal` and 5 `search_directions`). But the model **never acted**: `evidence.research: {}`, `evidence.implementation: {}`, `tool_call_ids: []`, `apply_batches: 0`, `model_attempts: []`. It spent its single turn generating text until it hit the 12,000-token output ceiling (used 16,555) before emitting even one tool call, so research, candidate construction, and edit all collapsed (`no_candidate_reason: "implementation_failed"`). UI diff: `graph_unchanged: true`; judge confirms `"The delta is empty"` — node 10 (SaveImage, currently fed from the placeholder LoadImage path, edge 4→10 per `request.json` lines 8–12) was never rewired. `[INFERENCE]` DeepSeek V4 Flash, faced with the full 17 KB graph serialization in context, generated an extremely verbose pre-action analysis; no agentic loop guard (e.g., cap on first-turn text, "must emit a tool call" pressure) intervened, and the ceiling hit was treated as terminal rather than retryable.

### One-line fix hypothesis
Same family as #1 — the executor's output-token ceiling (12k for `adapt`) plus no truncation retry; additionally, enforce an early tool-call: cap the assistant's first-turn non-tool text (or inject a continuation turn on `finish_reason=length` with "proceed to research/edit now") so the agentic loop cannot be starved by one over-long narrative turn. File pointer: same `"used %d of limit %d"` executor path; budget_usage shows `model_continuations: 0` — the continuation mechanism exists in the schema but is not engaged for `output_tokens`.

### Tags
`CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## Cross-cutting root cause & fix ranking

Both failures are **the same bug**: per-route hard output-token ceilings (inspect 4000, adapt 12000) with **no retry/continuation on truncation**. The model runs long (verbose single-generation style of DeepSeek V4 Flash on large graph contexts), hits `finish_reason=length`, the executor converts it to a terminal `output_tokens` failure with a placeholder reply, and the judge correctly rejects the empty artifact. Classification quality is *not* implicated — both routes were correct; this is an executor/budget-layer defect that wasted otherwise-correct routing.

Fix ranking by leverage (2/2 scenarios moved):

1. **Make `output_tokens` truncation retryable/continuable** (`model_continuations` already in `budget_usage`, currently 0) — moves **both** scenarios: #1's diagnosis would be delivered (possibly partially), #2's agent loop could resume and actually research+edit. Highest leverage, one code path.
2. **Raise `max_output_tokens` per route** (inspect 4000→≥8k, adapt 12000→≥24k) or scale it with graph size — moves both, but is a band-aid: it delays rather than fixes the no-retry design, and oversized graphs will re-hit any ceiling.
3. **Agentic-loop guard for adapt routes** — require a tool call early (first-turn text cap / "act now" continuation) — moves only #2, but prevents the same starvation for future large-graph edits.

No judge changes proposed; `allow_safe_refusal_outcome_kinds` (`clarify`, `requires_custom_nodes`) was never relevant — no refusal occurred. Neither scenario is `incomplete` (no refusal/no-op path taken; a product was attempted and rejected), so both tag as `judge_fail` with root cause `BUDGET-EXHAUSTION`. Both remain `EXPECTED-REMAINING` on this first analysis run.
[launch_hermes_agent] done in 81.0s
