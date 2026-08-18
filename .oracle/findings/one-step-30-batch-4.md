# Fail analysis batch 4 — DeepSeek Flash (classify-less one-step executor)

**Artifact root:** `out/compare-pipeline-modes/two-step-50/two_step` (+ `cache/*.pair.json` for the 2 scenarios with no output dir — their two_step runs died before writing per-scenario artifacts; evidence lives in the pair files' `two_step`/`guard` blocks).

**Global diff fact (all 7):** `final.ui.json == original.ui.json` in every scenario — zero node/link/widget changes. Confirmed by `response.graph_unchanged: true` (responses 1–5), and for the two cache-only scenarios by `graph_signature.final_pi_edit_digest == original_pi_edit_digest` (`4b54c9bc…`) in both pair files. No scenario produced any candidate edit.

**Dominant pattern:** 6/7 failures are hard budget aborts inside the single-message executor (`output_tokens` ×4, `wall_clock` ×1, `per_tool_calls` ×1) — the classify-less one-step executor runs research + implement + reply in ONE model message, and the structured `agent_edit_turn_v2` response blows past the per-message caps before any delta is emitted. Only 1/7 is a genuine reasoning failure.

---

## 1. multi-ai-video-upscaling-with-detail-daemon-sampler-673197 — `[inspect]`

**Verdict evidence** (assessment.json:11-17, `verdict: fail`, `scenario_kind: semantic_product`, `expect_graph_changed: false`):
> "semantic_answer failed: Point 5 hallucinates a connection: the links show BetaSamplingScheduler 428 outputs to Sigmas Rescale (430) and then to SamplerCustom 426, not to ClownOptions_SDE_Beta (431); only schedulers 432 and 433 feed 431. The '0.1 suppresses detail' and aspect-ratio 'stretched latents' causal claims are also speculative/unsupported by the evidence, so the answer is not fully grounded or correct. criteria={'grounded': False, 'relevant': True, 'correct': False}"

**Root cause:** Executor succeeded (`ok: true`, `outcome.kind: "noop"`, `reason: "Executor-only non-applyable turn."`, route `inspect`, no graph change expected). The 5-point reply (response.json:42) contains the hallucinated Point 5 verbatim — "three BetaSamplingSchedulers (uids 428, 432, 433) feeding into ClownOptions_SDE_Beta (uid 431)" — plus the speculative claims 3–4. Route/tooling worked; answer grounding failed. `budget_usage.tool_calls: 1`, self-assessment `confidence: "high"` — no verification step.

**One-line fix:** In the inspect reply contract, require per-claim link/widget citations (the judge's criteria literally demand `grounded`); anchor at response.json:42 / `report.executor.plan` (`intent: "explain_graph"`). [INFERENCE] prompt text lives in the inspect-route prompt template, not in the artifact tree.

**Tag:** `CLASS: judge_fail | PROMPT-GAP` — `OUTCOME: EXPECTED-REMAINING`

---

## 2. multi-animatediff-video-generation-with-controlnet-a7e2af — `[research]`

**Verdict evidence** (assessment.json:12-21):
> "response.ok is False: tool 'hivemind_search' per-message call cap (3)."
> "semantic_answer failed: The answer is an error message ('tool hivemind_search per-message call cap (3)') rather than a substantive response; it contains no workflow-grounded claims, does not address the DiT/AnimateDiff trade-off question, and provides no technically correct content. criteria={'grounded': False, 'relevant': False, 'correct': False}"

**Root cause:** `failure_kind: "per_tool_calls"`, `failure_stage: "execute"` (response.json:25-27). The research plan (classification.json:11-16) lists **5** `search_directions`; the per-message tool cap is **3** — the message aborted mid-search, `model_attempts: []` (no retry), and the error string became the reply. No graph change expected; failure is purely the missing research answer.

**One-line fix:** Raise the per-message `hivemind_search` cap for research routes (3 → ≥5, matching `search_directions`) or allow tool-call continuation across messages; anchor at response.json:10 (`"error"` field) / failure guard emitting `per-message call cap` [INFERENCE] in harness tool-loop config.

**Tag:** `CLASS: judge_fail | INFRA` — `OUTCOME: EXPECTED-REMAINING`

---

## 3. multi-crops-face-previews-it-sets — `[adapt]`

**Verdict evidence** (assessment.json:8-23):
> "response.ok is False: output_tokens: used 14301 of limit 12000"
> "Expected graph change but response.graph_unchanged is True."
> "edit_intent failed: The Δ contains no changes — delta_replay has zero statements and both pre/post views report 'No changes' — so no face-swap node or parameter was modified to address the likeness problem. The graph remains connected (no orphaned wiring), but the intent is not implemented. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"

**Root cause:** `failure_kind: "output_tokens"`, `failure_stage: "execute"` (response.json:27-29). `adapt` route locks `research: true` + `implement: true` in one message (classification.json:3-8). The single response reached 14,301 output tokens > 12,000 cap → hard abort → zero delta → graph unchanged → intent unimplemented. `budget_usage` all zeros: the abort happened on the first model call.

**One-line fix:** Split adapt into a research message + an implementation message (per-stage budgets), or raise `output_tokens` cap ≥ 16k; anchor at response.json:12 / classification.json:8 (`research: true`).

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 4. multi-flux2-image-and-video-generation-with-outpaint-435de2 — `[inspect/diagnose]`

**Verdict evidence** (assessment.json:12-21):
> "response.ok is False: wall_clock: used 136.39925295801368 of limit 60.0"
> "semantic_answer failed: The answer is just a resource-usage message ('wall_clock: used 136.39... of limit 60.0') and contains no substantive content about the workflow, the ColorMatch node, or the luminance mismatch. It fails grounded, relevant, and correct as an effectively empty/non-answer to the diagnosis question. criteria={'grounded': False, 'relevant': False, 'correct': False}"

**Root cause:** `failure_kind: "wall_clock"`, `failure_stage: "execute"` (response.json:27-29). The diagnose route inspected a very large graph (uids up to 5468; two ColorMatch nodes + PainterImageFromBatch subgraph, classification.json:5) and burned 136.4s vs a 60s limit → abort → error string as reply. No graph change expected.

**One-line fix:** Raise the wall-clock budget for inspect/diagnose (60s → ≥180s) or make graph inspection incremental/streaming; anchor at response.json:10 / flow_metadata.json:68 (`status: "executor_failure"`).

**Tag:** `CLASS: judge_fail | INFRA` — `OUTCOME: EXPECTED-REMAINING`

---

## 5. multi-image-to-3d-object-generation-with-background-1a7f84 — `[revise]`

**Verdict evidence** (assessment.json:12-26):
> "response.ok is False: output_tokens: used 8327 of limit 8000"
> "Expected graph change but response.graph_unchanged is True."
> "edit_intent failed: The accepted Δ is empty; no node was targeted or parameter changed, so the background removal still does not produce a transparent alpha channel. Only wiring is unchanged. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"

**Root cause:** `failure_kind: "output_tokens"` @ execute (response.json:27). A trivial edit — set alpha widgets on Rembg + VHS_VideoCombine, `effort: "low"` (classification.json:3) — still emitted 8,327 output tokens vs the 8,000 cap in the single structured message. Abort → no delta → intent unimplemented.

**One-line fix:** Raise `output_tokens` cap ≥ 10k for revise, or emit delta in a second continuation; anchor at response.json:12 (`"error"`).

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 6. multi-image-to-video-generation-with — `[revise]` (cache-only)

**Verdict evidence** (pair.json two_step.guard.assessment issues, 439-454):
> "response.ok is False: output_tokens: used 9261 of limit 8000"
> "Expected graph change but response.graph_unchanged is True."
> "edit_intent failed: The accepted Δ contains no operations (checked: 0, mismatches: []) and both pre/post diffs report 'No changes', so no KSampler node was targeted and no steps/sampler parameters were modified; the intent is therefore unimplemented. Topology remains connected, so no orphaned wiring exists. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"

**Root cause:** `status: "executor_failure"`, `error: "output_tokens: used 9261 of limit 8000"` (pair.json:405), `model_attempts: []`. Same single-message output-cap abort as #5 — this time on the revise route (set KSampler `dpmpp_2m`/steps 30). **Control evidence:** the paired full-mode run on the identical scenario PASSED with a 3-call session (batch + agent_turn + reply; 1,032 completion tokens, pair.json:231-285) — proving the edit is trivially easy and the two-step failure is purely the 8k output cap on the one-shot executor.

**One-line fix:** Same as #5 — raise `output_tokens` cap or split the turn; anchor at pair.json:405.

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## 7. multi-image-to-video-with-llm — `[adapt]` (cache-only)

**Verdict evidence** (pair.json two_step guard, 598-612):
> "response.ok is False: output_tokens: used 17378 of limit 12000"
> "Expected graph change but response.graph_unchanged is True."
> "edit_intent failed: The delta_replay is empty (no batch statements), meaning no change was made to any node or parameter. The intent requires an edit to improve the prompt's fidelity to the input image, but the Δ contains no evidence of any node being targeted, any parameter being changed, or any value being adjusted. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"

**Root cause:** `status: "executor_failure"`, `error: "output_tokens: used 17378 of limit 12000"` (pair.json:564). Worst output blowout of the batch (17.4k tokens in one message) on an adapt route (research + implement). **Control evidence:** full mode did produce an edit (node 182 `StringFunction|pysssss` widget_5) but still failed `value_semantically_matches_intent` (blanking the string, pair.json:35) — so even full mode had a semantics problem; two-step died before editing at all.

**One-line fix:** Raise cap / split adapt messages (primary); separately, adapt edit-selection quality (the blanking-a-string edit is a WRONG-EDIT seed) [INFERENCE]; anchor at pair.json:564.

**Tag:** `CLASS: judge_fail | BUDGET-EXHAUSTION` — `OUTCOME: EXPECTED-REMAINING`

---

## Ranked by fix leverage (moves the most scenarios)

| Rank | Fix | Scenarios moved | Rationale |
|---|---|---|---|
| 1 | Raise per-message `output_tokens` cap (8k/12k → ≥20k) for the one-step executor | 3, 5, 6, 7 (4/7) | All four died on the first model call with 8.3k–17.4k tokens; full-mode controls prove the underlying tasks are solvable. |
| 2 | Split adapt/research routes into research-turn + implement-turn (per-stage budgets) | 2, 3, 7 (3/7, overlaps #1) | Kills the single-message bloat that causes #1; also decouples the 3-call `hivemind_search` cap (scenario 2) from the edit message. #1 + #2 together ≈ 6/7. |
| 3 | Raise wall-clock budget for inspect/diagnose (60s → ≥180s) | 4 (1/7) | Graph inspection of large workflows (uids >5000) cannot finish in 60s. |
| 4 | Grounding instruction for inspect replies (cite-only-verified links/widgets) | 1 (1/7) | The only pure reasoning failure; judge explicitly wants `grounded`. |

No bar-softening or judge changes proposed. `OUTCOME: EXPECTED-REMAINING` for all 7 (first analysis run; root causes are executor-budget/harness-config, not scenario-intrinsic).
[launch_hermes_agent] done in 151.0s
