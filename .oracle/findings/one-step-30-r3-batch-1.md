# r3 Fail Analysis — Batch 1 (DeepSeek Flash) · one-step-30-r3

**Run context (verified):** 13/30 completed, 3 passed, 10 failed (`run_summary.partial.json`: `"passed": 3, "failed": 10`, `product_or_assessment_failures: 10`, 0 infra failures). All 7 batch scenarios are `scenario_kind: "edit"`, `expect_graph_changed: true`, all `verdict: "fail"`. 6 of 7 died **before any apply batch landed** (`accepted_delta_ids: []`, `apply_batches: 0` in every case). One (scenario 7) completed with a no-change submit.

---

## 1. `3d-3d-model-generation-and-preview-workflow-cc0df7`

**Query:** *"Swap the Rodin3D generation model from Rodin Large to Rodin Fusion and ensure all downstream nodes (detailing, smoothing, preview) remain connected and functional."*

**Verdict evidence (issues[] verbatim):**
- `"response_ok"` → `"response.ok is False: replacement_attempts: used 1 of limit 1"`
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The accepted Δ contains no changes (delta_replay has 0 checked/0 mismatches and the pre/post diff both show 'No changes'), so no Rodin3D node was targeted or had its generation model parameter swapped, and the intent is entirely unimplemented. criteria={'correct_node_targeted': False, 'correct_parameter_changed': False, 'value_semantically_matches_intent': False, 'no_orphaned_wiring': True}"`

**Root cause:** `failure_kind: "replacement_attempts"`, `failure_stage: "execute"`, `graph_unchanged: true`, reply `"I ran out of budget before completing the request; here's what I have: 63 research result(s) were collected."` — the graceful-degradation path. The session did heavy research (63 results) but no apply batch ever landed. `model_attempts: []`, so the offending raw output was not persisted. `[INFERENCE]` The failure signature (a single replacement consumed, then hard stop at `limit 1`) matches the confirmed concatenated-JSON parse failure seen in scenario 2 of this same run; a single malformed turn exhausts the per-message replacement cap (`two_step.py:617`, `max_replacements` observed = 1) and the session dies.

**Fix:** `vibecomfy/executor/prompts.py:999` — `_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)` is greedy first-`{`→last-`}`; it spans concatenated objects and fails `json.loads`. Replace with a balanced/non-greedy first-object extractor (or sequence-aware parse) so `{apply}{submit}` yields the apply instead of a `ValueError` at `prompts.py:1033`.

**Tag:** `CLASS: incomplete | REPLACEMENT-EXHAUSTION (PARSE-MULTI-JSON, inferred)` + `OUTCOME: EXPECTED-REMAINING`

---

## 2. `3d-converts-image-to-3d-model` — the smoking gun

**Query:** *"The 3D model looks too smooth and featureless — I want sharper surface detail."* Graph: `Rodin3D_Regular` node `"28"`, `widget_2: "200K-Triangle"`.

**Verdict evidence (issues[] verbatim):**
- `"response_ok"` → `"response.ok is False: Could not extract a JSON object from: '{\"action\": \"apply\", \"python\": \"rodin3d_regular.widget_2 = \\'1M-Triangle\\'\"}{\"action\": \"submit\", \"reply\": \"I raised the polygon count on the Rodin3D_Regular node from \\'200K-Triangle\\' to \\'1M-Triangle\\'. Th'"` (truncated at 200 chars by the parser itself)
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The accepted Δ contains no replay statements (checked: 0, mismatches: []) and both pre/post IR views show 'No changes', so no node was targeted or parameter adjusted to increase surface detail; ..."`

**Root cause — CONFIRMED PARSE-MULTI-JSON.** The model emitted **two top-level JSON objects back-to-back** — an `apply` **and** a `submit` in one turn, exactly the suspected dominant cause. The edit itself was *correct* (right node class, right widget, right value: `200K-Triangle` → `1M-Triangle`). The raw text shows `failure_kind: "ExecuteError"`, `claim_validation.status: "failed"`. Mechanically: `json.loads` fails on the concatenation; the fallback regex `\{.*\}` (greedy, DOTALL, `prompts.py:999`) captures `{apply}{submit}` as one span; `json.loads(match.group(0))` fails; `ValueError("Could not extract a JSON object from: ...")` raised at `prompts.py:1033`. `[INFERENCE]` Even if parsing had succeeded, `rodin3d_regular.widget_2` is a class-type-derived name, not a name in the session's `_transient_name_index` (see scenario 7) — it would likely have been rejected as `unknown_source_name` post-parse.

**Fix:** Same as #1 — non-greedy/balanced JSON extraction at `prompts.py:999-1033` (fixes the parse); plus the node-reference convention fix from scenario 7 (fixes the would-be-apply).

**Tag:** `CLASS: incomplete | PARSE-MULTI-JSON (confirmed, raw text quoted)` + `OUTCOME: EXPECTED-REMAINING`

---

## 3. `audio-audio-processing-with-chatterbox-tts-and-vc-b55994`

**Query:** *"Change the output audio format from MP3 to WAV."* (Judge: output node 428 uses `SaveAudioMP3`.)

**Verdict evidence (issues[] verbatim):**
- `"response_ok"` → `"response.ok is False: replacement_attempts: used 1 of limit 1"`
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The Δ contains no changes, so the output node (428) still uses SaveAudioMP3 and the format is not changed to WAV. No node was targeted or parameter modified to achieve the intent. ..."`

**Root cause:** `failure_kind: "replacement_attempts"`, reply `"I ran out of budget before completing the request; here's what I have: 2 research result(s) were collected."` Only 2 research results — the session barely started before a malformed turn consumed its single replacement. `model_attempts: []`, no raw text. `[INFERENCE]` Same concatenated-JSON mechanism as scenario 2 (identical failure family, same run).

**Fix:** Same parser fix as #1/#2.

**Tag:** `CLASS: incomplete | REPLACEMENT-EXHAUSTION (PARSE-MULTI-JSON, inferred)` + `OUTCOME: EXPECTED-REMAINING`

---

## 4. `audio-transcribes-audio-appends-text-regenerates`

**Query:** *"The transcription has too many errors — the speech-to-text stage seems weak."*

**Verdict evidence (issues[] verbatim):**
- `"response_ok"` → `"response.ok is False: replacement_attempts: used 1 of limit 1"`
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The delta_replay contains no batch statements (verified is null, checked is 0), yet the intent calls for improving speech-to-text accuracy. No node was targeted, no parameter was changed, and no value was modified. ..."`

**Root cause:** `failure_kind: "replacement_attempts"`, reply `"I ran out of budget before completing the request; here's what I have: 41 research result(s) were collected."` Same signature as #1/#3. `[INFERENCE]` Concatenated-JSON mechanism; raw text not persisted (`model_attempts: []`).

**Fix:** Parser fix at `prompts.py:999`.

**Tag:** `CLASS: incomplete | REPLACEMENT-EXHAUSTION (PARSE-MULTI-JSON, inferred)` + `OUTCOME: EXPECTED-REMAINING`

---

## 5. `audio-tts-narration-using-indextts-2`

**Query:** *"The narration sounds flat and monotone — can you make it more engaging?"*

**Verdict evidence (issues[] verbatim):**
- `"response_ok"` → `"response.ok is False: replacement_attempts: used 1 of limit 1"`
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The accepted Δ is empty (no changes), so no node was targeted or parameter modified to address the flat narration intent. ..."`

**Root cause:** `failure_kind: "replacement_attempts"`. Reply variant: `"I ran out of budget before completing the request; here's what I have: a partial edit was applied."` — note `accepted_delta_ids: []` and `apply_batches: 0`, so "partial edit" is a message-template variant, not a real landed delta. `[INFERENCE]` Same mechanism as #1/#3/#4.

**Fix:** Parser fix at `prompts.py:999`.

**Tag:** `CLASS: incomplete | REPLACEMENT-EXHAUSTION (PARSE-MULTI-JSON, inferred)` + `OUTCOME: EXPECTED-REMAINING`

---

## 6. `image-animatediff-video-generation-with-vae-d20410`

**Query:** *"Reduce the number of frames from 16 to 8 for quicker test renders."*

**Verdict evidence (issues[] verbatim):**
- `"response_ok"` → `"response.ok is False: replacement_attempts: used 1 of limit 1"`
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The accepted Δ contains no operations (verified null, checked 0, mismatches [], and both pre/post diffs report 'No changes'), so the frame count was never reduced from 16 to 8; no node or parameter was actually modified to realize the intent. ..."`

**Root cause:** `failure_kind: "replacement_attempts"`, reply `"I ran out of budget before completing the request; here's what I have: 112 research result(s) were collected."` — the most research-heavy of the batch (112 results) before a malformed turn killed it. `[INFERENCE]` Same mechanism.

**Fix:** Parser fix at `prompts.py:999`.

**Tag:** `CLASS: incomplete | REPLACEMENT-EXHAUSTION (PARSE-MULTI-JSON, inferred)` + `OUTCOME: EXPECTED-REMAINING`

---

## 7. `3d-generates-a-3d-mesh-from` — the distinct one

**Query:** *"The generated 3D mesh is full of floating bits and noise."* Graph facts (verified in `original.ui.json`): `VoxelToMeshBasic` is node **`"62"`** with `widget_0: 0.6000000000000001`; `VAEDecodeHunyuan3D` has `widget_1: 256` (octree resolution). The model's diagnosis was **correct**.

**Verdict evidence (issues[] verbatim):**
- `"graph_changed"` → `"Expected graph change but response.graph_unchanged is True."`
- `"intent_judge"` → `"edit_intent failed: The accepted Δ is empty (delta_replay shows no changes, diff says 'No changes'), meaning no node was targeted and no parameter was modified to address the floating bits and noise. ..."`

Note: `error_count: 2` — **no `response_ok` issue**: `response.ok is True`, `flow_metadata.status: "success"` (the run completed; the judge rejected the product).

**Root cause — WRONG-EDIT (node-reference convention), graceful degradation.** The session actually exercised the edit path (`model_continuations: 10`, `tool_calls: 7`, `output_tokens: 28527`, `replacement_used: true`) and then submitted a `no_change` with `self_assessment.outcome: "no_change"`. The model's own note: *"No edit batch was accepted: prior Python batches were rejected as unknown_source_name. Recommend manual VoxelToMeshBasic threshold increase from 0.6 to ~0.72–0.8."* The engine's `_resolve.py:1552` emits `code_unknown="unknown_source_name"` when an AST name can't be resolved, and the session's name index is initialized empty (`session.py:322`: `self._transient_name_index = {}`) — nothing pre-populates it with class_type→node aliases. `[INFERENCE]` The model referenced nodes by class-type-derived names (`voxeltomeshbasic`/`VoxelToMeshBasic`) rather than a resolvable bound name, every batch was rejected, and it degraded to a submit-with-guidance. The final reply's content is high-quality (correct node, correct widget, correct direction, appropriately hedged) — the failure is purely in edit delivery, not understanding.

**Fix:** Seed `_transient_name_index` at `session.py:322` with node aliases (class_type slug → node id, e.g. `voxeltomeshbasic` → `"62"`) at session init so class-derived references resolve; and/or state the exact node-reference syntax in the agent prompt.

**Tag:** `CLASS: judge_fail | WRONG-EDIT (node-reference convention)` + `OUTCOME: EXPECTED-REMAINING`

---

## Cross-scenario synthesis

| # | Scenario | failure_kind | Root cause | Evidence strength |
|---|---|---|---|---|
| 2 | 3d-converts-image-to-3d-model | ExecuteError | PARSE-MULTI-JSON | **Raw text** |
| 1,3,4,5,6 | 3d-model-gen / chatterbox / transcribe / indextts / animatediff | replacement_attempts | PARSE-MULTI-JSON (inferred) | Signature match; raw text not persisted |
| 7 | 3d-generates-a-3d-mesh-from | — (ok:true, no_change) | WRONG-EDIT (node refs) | self-assessment note |

**Shared facts:** all six parse/replacement deaths show `accepted_delta_ids: []`, `apply_batches: 0`, `graph_unchanged: true`, and the same hard stop `"replacement_attempts: used 1 of limit 1"` — i.e., **one** malformed turn kills the attempt because the per-message replacement cap is 1 (`two_step.py:617`, `check_replacement_attempt`, `"at most one per message (B02)"`), independent of the session ceiling of 12 (`two_step.py:799`).

## Ranked fix leverage

1. **Parser resilience — `vibecomfy/executor/prompts.py:999`** (regex `\{.*\}` greedy). Fixes **6 of 7** scenarios. Make the fallback extract the *first balanced* JSON object (or split on top-level `}{` boundaries), so concatenated `{apply}{submit}` parses as the apply instead of raising at `prompts.py:1033`. One line, highest leverage, no judge/prompt changes.
2. **Node-reference resolution — `vibecomfy/porting/edit/session.py:322`** (empty `_transient_name_index`). Seed class_type→node-id aliases at session init (or surface the exact binding syntax in the prompt). Fixes scenario 7's delivery and prevents scenario 2's correct edit from failing post-parse.
3. *(Defense-in-depth, not required)* Per-message replacement cap 1 (`two_step.py:617`) means zero tolerance for a single malformed turn; once #1 lands this is mostly moot.

**Outcome: all 7 EXPECTED-REMAINING under the current harness — 6 blocked on one regex, 1 on node-name seeding.** No bar-softening or judge changes proposed.
[launch_hermes_agent] done in 215.5s
