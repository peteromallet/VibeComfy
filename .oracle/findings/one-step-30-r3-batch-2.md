# r3 fail analysis — batch 2 (one-step-30-r3, DeepSeek Flash)

## Summary table

| Scenario | Verdict | Class | Root cause | Fix leverage |
|---|---|---|---|---|
| audio-acestep-…-1b1360 (edit) | `fail` | `judge_fail` | Empty-Δ refusal: model claimed `AudioFilter` unaddable (contradicted by graph) and submitted plain `no_change` instead of the allowed `requires_custom_nodes` refusal or the edit | 3 |
| audio-acestep-…-f0859f (semantic) | `fail` | `judge_fail` | `UNGROUNDED-ANSWER`: mechanism claims + numeric recs with zero claim_refs; schema access admitted failed | 2 |
| image-dual-checkpoint-…-c9df19 (semantic) | `undetermined` | `judge_fail` (undetermined) | `INFRA`: judge's own response failed strict parse — `Extra data` at char 689 (same concatenated/trailing-JSON family as the executor bug) | 1 |

All three: `OUTCOME: EXPECTED-REMAINING`. Budget deaths (caps, transcript ceiling) not implicated anywhere — no scenario hit the 12-replacement ceiling (`replacement_attempts`: 1, 0, 0).

---

## Scenario 1 — audio-acestep-audio-generation-and-processing-workfl-1b1360

**Query (request.json:6485):** "Integrate a spectral-gating noise reduction pass before the audio separation step, then route the cleaned audio into both the vocal removal and the separation branches."

### 1. Verdict evidence (assessment.json issues[] VERBATIM)
- `{"check": "graph_changed", "detail": "Expected graph change but response.graph_unchanged is True.", "severity": "error"}`
- `{"check": "intent_judge", "detail": "edit_intent failed: The accepted Δ is empty (checked=0, no statements; pre/post diffs both show 'No changes'), so no noise-reduction node was added or wired and no parameters were changed; the intent's spectral-gating pre-processing step is entirely absent. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}", "severity": "error"}`

### 2. Root cause
The session ran 16 continuations / 13 tool calls / 77,290 output tokens / 1685s and ended with a **single well-formed** `{"action":"submit", …}` message (not concatenated JSON — `replacement_attempts: 1`, `replacement_used: true`). The executor then marked `no_candidate_reason: "route_not_applyable"`, `accepted_delta_ids: []`, `route: "adapt"`, `self_assessment.outcome: "no_change"`.

The model's refusal, verbatim from response.json `message`:
> "I couldn't wire in a spectral-gating noise-reduction pass, because this environment's node library has no spectral-gating node at all. … the editor also refuses to add a new AudioFilter node (its class type isn't in the editable schema here) … No changes were made."

The environment claim is **contradicted by the graph itself**: the original workflow (request.json nodes) already contains an `AudioFilter` node — uid 214 (`"class_type": "AudioFilter"`, line 5420) wired `213 (FrequencyFilterPreset, remove_rumble) → 214 → 221` — plus a **second, orphaned** `FrequencyFilterPreset` uid 216 (remove_hiss) with **no incoming/outgoing edges**. The model even identified the correct plan ("What you asked for would require node 115 (VAEDecodeAudio)'s output to pass through a filter applying remove_hiss before feeding AudioSeparation (uid 146) and VocalAndSoundRemoverNode (uid 155)") and then declared it impossible because a new `AudioFilter` "can't be created".

Two problems, both on the model/route side:
- **[INFERENCE]** The addability claim is at best unverified, at worst fabricated: a class_type instantiated in the loaded workflow is by definition registered in the backend, yet the model asserts `unknown class_type for add_node`. Only one evidence-bearing tool call is recorded (`tool:ready_template_list-audio`; `evidence_ids` has 1 entry vs `tool_calls: 13`), so we cannot see the actual add_node error transcript.
- **Refusal protocol not used:** `allow_safe_refusal_outcome_kinds: ["clarify", "requires_custom_nodes"]` — had the model emitted a refusal with kind `requires_custom_nodes`, the judge could have tolerated it. It instead submitted plain `no_change` (no delta, no refusal kind) against `expect_graph_changed: true` → both checks fail.

**Not** REPLACEMENT-EXHAUSTION (1 replacement) and **not** a budget death.

### 3. One-line fix hypothesis
In the executor's node-inventory/add_node guidance (prompt or tool docs): state that any `class_type` already present in the loaded workflow (e.g., `AudioFilter` at uid 214) is addable and surface the exact addable class list, and instruct the refusal classifier to map "required node unavailable" submissions to `outcome_kind: "requires_custom_nodes"` instead of `no_change`.

### 4. Tag
`CLASS: judge_fail | WRONG-EDIT (infra-availability claim contradicted by graph; empty Δ; safe-refusal kind not used)` + `OUTCOME: EXPECTED-REMAINING`

---

## Scenario 2 — audio-acestep-audio-generation-with-detail-daemon-f0859f

**Query (request.json:2063):** "The DetailDaemon sampler is used for enhancing audio detail. How does it work compared to standard audio diffusion samplers, and what settings would you recommend for generating a cinematic soundscape?"

### 1. Verdict evidence (assessment.json issues[] VERBATIM)
- `{"check": "semantic_answer", "detail": "semantic_answer failed: The answer's core mechanism claim—that DetailDaemonSamplerNode 'injects a detail-enhancement guidance signal... maximizing spectral detail' and 'amplifies high-frequency textures, transients'—is unsupported by the workflow evidence, which provides only widget names/values (detail_amount=0.1, start=1, end=1, etc.) and no algorithmic semantics; the answer itself admits schema access failed. The start/end fraction interpretations and all numeric setting recommendations are consequently speculative and materially ungrounded, so grounded and correct fail while relevance is intact. criteria={'grounded': False, 'relevant': True, 'correct': False}", "severity": "error"}`

### 2. Root cause
`UNGROUNDED-ANSWER` — the exact live "un/cited causal claims in research answers" issue. The session ran 6 continuations / 5 tool calls / 7,089 tokens / 271s, route `adapt`, `outcome: no_change`, `graph_unchanged: true`, and submitted a substantive answer whose core mechanism claims are **uncited**: the submitted message contains **no `claim_refs` key at all** (grep of response.json for `claim_refs` → 0 hits), and `claim_validation: {"status": "ok", "violations": []}` — so the validator blessed a fully-uncited causal answer. Evidence IDs are 11 `hivemind:external_resources:*` lookups (web knowledge), not workflow/schema evidence.

The answer itself flags the gap, then proceeds anyway (verbatim): "the exact meaning of `start`/`end` could not be verified without schema access, in many DetailDaemon implementations they control the timestep interval…" — followed by concrete recommendations: "**detail_amount**: Increase to 0.2–0.25", "**start**: Set to 0.25", "**end**: Set to 0.85", "**bias**: Try 0.6–0.7", "**fade**: Set to 0.05–0.1". The workflow evidence (original.ui/request.json `DetailDaemonSamplerNode`, widget_values_sig: `detail_amount 0.1`, `bias 0.5`, `cfg_scale_override 0`, `start 1`, `end 1`) supports only the widget inventory, not the "injects a detail-enhancement guidance signal… maximizing spectral detail / amplifying high-frequency textures, transients" mechanism. Grounded=False, correct=False, relevant=True per judge.

### 3. One-line fix hypothesis
In the grounding prompt + submit validator: require every mechanistic/causal sentence to carry a claim_ref (reject/flag submits whose `claim_refs` is absent or empty while the reply asserts node-internal semantics), and hard-instruct: no schema/object evidence → state "unknown", give **no** numeric recommendations (scenario 2's schema access failed and the answer still shipped six recommended values).

### 4. Tag
`CLASS: judge_fail | UNGROUNDED-ANSWER (zero claim_refs; mechanism claims + recs beyond workflow evidence)` + `OUTCOME: EXPECTED-REMAINING`

---

## Scenario 3 — image-dual-checkpoint-xl-image-generation-with-refin-c9df19

**Query (request.json:2464):** "I'm running this dual-checkpoint XL pipeline with juggernautXL as the base and sd_xl_refiner as the refiner. Are there any newer, better refiner models I should consider, and what are the tradeoffs between using a dedicated refiner vs. a single high-quality XL checkpoint… how the LoRA timing (before or after the refiner) affects flexibility."

### 1. Verdict evidence (assessment.json issues[] VERBATIM)
- `{"check": "semantic_answer", "detail": "semantic_answer could not run: could not parse judge response: Extra data: line 1 column 690 (char 689)", "severity": "undetermined"}`
- judge_results: `{"judge": "semantic_answer", "verdict": "undetermined", "pass_": null, "criteria": {}, "error": "could not parse judge response: Extra data: line 1 column 690 (char 689)"}`

### 2. Root cause
The **executor side did its job**: route `research`, 32 continuations / 30 tool calls / 43,737 tokens / 491s, `self_assessment: {"confidence": "high", "note": "Research-only answer; no graph edit. Prior hivemind searches covered refiner alternatives, dedicated-refiner-vs-single-checkpoint tradeoffs, and LoRA timing before/after the refiner."}`. The answer is graph-grounded (correctly reads Power Lora Loader uid 49 → KSampler Advanced uid 10 base; refiner uid 11 raw; steps 25/end_at_step 20) and quotes concrete model names (sd_xl_refiner_1.0_0.9vae, JuggernautXL v9, RealVisXL V4/V5…).

The failure is **judge-side**: the judge model emitted a valid JSON object followed by trailing data (`Extra data: line 1 column 690 (char 689)` = strict `json.loads` choked on content after char 689 of the judge's response). `error_count: 0`, `verdict: "undetermined"`, `score_class: "undetermined"` → counted as failure with zero product evidence either way.

This is the **same concatenated/trailing-JSON failure family** as the executor's `{apply}{submit}` bug that drives REPLACEMENT-EXHAUSTION — the model (same `deepseek/deepseek-v4-flash` via OpenRouter for judge and executor) emits JSON-plus-trailing-content; the executor path has the truncation-retry/graceful-degradation workaround, the judge path has **no** tolerance and hard-fails the scenario. Also notable: like scenario 2, the submitted answer has **no `claim_refs` key** (grep → 0 hits) — so the ungrounded-claim issue is present in both semantic products, though here it never got judged.

### 3. One-line fix hypothesis
In the judge-harness response parser: replace strict `json.loads` with first-JSON-object extraction (e.g., `json.JSONDecoder().raw_decode` over the raw text, or `response_format: {"type": "json_object"}`) — the identical hardening already planned for executor action parsing (PARSE-MULTI-JSON); one shared tolerant parser for both executor actions and judge verdicts kills this whole failure class.

### 4. Tag
`CLASS: judge_fail (verdict undetermined) | INFRA (judge-response parse: "Extra data" at char 689; product never evaluated)` + `OUTCOME: EXPECTED-REMAINING`

---

## Cross-cutting findings & leverage ranking

1. **Judge-response parse hardening (S3) — highest leverage, mechanical.** One scenario here died purely to a judge JSON-parse bug; the same model emits the same concatenated/trailing-JSON pattern that is the suspected dominant remaining executor failure (REPLACEMENT-EXHAUSTION). A single tolerant JSON extractor shared by executor-action and judge-verdict parsing addresses both. No criteria or bar changes involved — pure harness robustness.
2. **Claim-ref enforcement on submit (S2, and latent in S3) — high leverage, prompt+validation.** Both semantic answers shipped **zero claim_refs** while making causal mechanism claims and numeric recommendations; `claim_validation` returned `ok` with no violations in both. The grounding constraint landed in the prompt but is not enforced structurally. Add: non-empty `claim_refs` requirement when the reply asserts mechanism, and an explicit "schema unavailable → no recommendations" rule. This is the live, confirmed UNGROUNDED-ANSWER channel.
3. **Addability truth + refusal routing (S1) — narrower, one scenario.** The `AudioFilter` class is present in the workflow (uid 214) yet the model claimed it unaddable and submitted an empty-Δ `no_change`; even if the claim were true, the allowed `requires_custom_nodes` refusal kind was available and unused. Fix: make the addable-node inventory authoritative (classes in the graph are addable) and map no-op refusals to the safe-refusal kind.

No bar-softening or judge-criteria changes proposed; failures are attributed to specific model behaviors and harness gaps, not to the pipeline as a whole.
[launch_hermes_agent] done in 149.7s
