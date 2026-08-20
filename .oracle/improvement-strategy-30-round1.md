I'll read the pipeline skill and every attached input first, then write a tight prioritized RC list from the residual classes.The residual classes are clear. Next I’ll map each one to the actual implement/inspect/guard surfaces so the RCs cite real file:line, not guesses.Previous strategies and the live edit/inspect surfaces will tell me which of these residuals are already known and which need a new RC.I’ll pin the residual classes to the current implement, classify, emit, and inspect code so each RC can cite a real mechanism.The prior RCs already cover some of this. I’m reading the remaining hotspots so the new list only includes high-confidence, unshipped mechanisms.I have the mechanisms. Writing the round-1 strategy from the live artifacts and current code, not from the old 57-set leftovers.# Improvement strategy 1 — ir-everywhere-30-v1 (fixed-30 loop, round 1)

**Role:** strategy / philosophy audit for the 13 product fails + 4 infra rows.
**Measured baseline:** 13 PASS / 13 FAIL / 4 NO-ASSESSMENT at `a779d762`.
**Prior art:** RC1–RC17 already shipped (Hivemind degrade, graph-local act, classify retry, apply-gate, MODE_LABELS, widget names, infra typing). This pass is the *new* 30-v1 surface, not a second coat of those.
**Do not** soften groundedness. Do not loosen apply-gate self-loop, LiteGraph counter, or orphaned-wiring. Do not raise the 1200s outer kill.

---

## What the 17 rows actually are

| Class | n | Scenarios | Judge correct? |
|---|---|---|---|
| Dual-channel primitive write (`value` vs `widget_0`) | 1 | `multi-image-to-video-generation-with-2` | Mixed: intent_judge **passed** on IR; product UI unchanged |
| Queue/done veto of a landed widget Δ because of **pre-existing** unknown classes | 2 | `485ff2`, `03fced` | Yes on the rollback; the IR Δ was the requested edit |
| Inspect ungrounded / invented names | 3 | `1c7ad8`, `f855de`, `4eebf3` | Yes |
| Inspect technically wrong (grounded=true, correct=false) | 1 | `99e2a9` | Yes — keep failing |
| Classify `needs_input` shape hard-fail | 1 | `d20410` | Yes (no product) — parse is the defect |
| Clarify kind not emitted (class absent, allowlist already set) | 1 | `c80bbf` | Yes on empty Δ; envelope is the defect |
| Stale in-batch graph names after re-render | 1 | `a7ecc5` | Yes |
| Emit “Missing stable link to port” | 1 | `19d221` | Yes |
| Apply-gate new self-loop | 1 | `cc0df7` | Yes — **keep** |
| Orphaned wiring + schema-less TTS | 1 | `b55994` | Yes — **keep** |
| Infra 1200s / never started | 4 | `f65774`, `3d-converts`, `d813fe`, `506ebd` | n/a (principle 8) |

`c80bbf` also carries a LiteGraph-counter hard_diagnostic and a Hivemind 57014. Those are secondary; the scored miss is `outcome.kind=candidate` + `no_changes` on a well-formed clarify.

---

## Answers to the residual classes

### Edit-side: one mechanism, not ten

The ten “EDIT-side” labels in the batch docs collapse to **four** mechanical defects:

1. **Two authorities for one widget.** Live `multi-image-to-video-generation-with-2` diff is literal: `Float(widget_0='25')` → `Float(value=24.0, widget_0='25')`. IR committed `value=24.0`; emit still serializes `widget_0='25'`; every gate is green; `candidate_graph is None`; `graph_unchanged=true`. Principle 2 is already bent in-tree.
2. **Unknown-class veto of a landed widget Δ.** `485ff2` landed `18.widget_0` 534667941392889→42. `03fced` landed `57.steps` and `58.steps` 20→25. Both then `queue_validate_ok=false` with done-summary “N unknown class type(s)” and rolled back to noop. `_frag_revision.py:135-137` already *subtracts* pre-existing unknown classes, but `TopologyFindings.has_blockers` (`executor/contracts.py:1422-1430`) still includes them, and `_has_new_topology_blockers` (`revision_evidence.py:491-494`) keys unknown-class identity by the full `node_id=…: Class` string — emit remaps make the same class look new.
3. **Name index rebuilt from class+order mid-batch.** `a7ecc5` rejected on `cliptextencode_4`. `_refresh_bindings` (`_interpret.py:1218-1230`) recomputes names via `_compute_variable_names` after every apply. Emit already documents that `{class_type}_{order}` **renumbers on edits** and must never be a match key (`emit/ui.py:13-15`). The batch still uses those names.
4. **Slot remap gap on a linked widget write.** `19d221` is the live ACN strength 0.6→0.5 case of the defect `test_c8_sdxl_widget_override_renumbers_remaining_link_slots` already pins for `CLIPTextEncodeSDXL.text_g`. The remapper at `emit/ui.py:3064-3085` (`_emitted_socket_slot_for_link`) does not cover this class.

`cc0df7` and `b55994` are **not** this class. Apply-gate refused a new self-loop; the judge refused an orphaned ChatterboxVC output. Leave both failing.

### Semantic-product: do not treat 99e2a9 as the same bug

`1c7ad8` / `f855de` / `4eebf3` are `grounded=false`: invented composite semantics, invented 8-bit VAE / `codec=auto`→H.264, invented `widget_N` + `overlap`. The inspect prompt already says “Never invent parameters” (`prompts.py:509-513`); the lens still hands the model positional `widget_0` / unlabeled lists (`graph_inspection.py:237-248` — `name=None` when schema names are short).

`99e2a9` is `grounded=true, correct=false` — a real SVD denoise error. Do **not** inject a “denoise=1 is joint temporal sampling” fact card. Do **not** soften `correct`. Budget +0.

### Infra: not a product RC

Four rows never produced a terminal `assessment.json`. `f65774` attempt_1 *did* implement and died on `guard_emit` `presence:[false,true]` for uids 23/33 (RC15-shaped), then the 1200s wall hit. `3d-converts` / `d813fe` / `506ebd` are `killed_before_first_attempt` under load 300. Principle 8: score them infra. Do not raise 1200s. Bound research so a started scenario can still emit a product verdict; do not promise flips.

---

## Prioritized RCs

Order is expected flips per unit of implementation risk.

### RC-1 — One authority for primitive widget writes (`value` ≡ `widget_0`)

**Targets.** Snapshot-delta / dual-channel: `multi-image-to-video-generation-with-2`. Same family as any later Float/Int/Primitive `value` write that leaves `widget_0` stale.

**Evidence.** Live batch: `float.value = 24.0` / `done()`; `field_changes=[{uid:218, field_path:value, old:"25", new:24.0}]`; python diff `Float(widget_0='25')` → `Float(value=24.0, widget_0='25')`; `intent_judge` passed; `queue_validate_ok=true`; `candidate is None`; `graph_unchanged=true`.

**Fix.**
1. `apply_edit_cow` (`porting/edit/_ir_utils.py:658-671`): when `field` is a schema/instance alias of a serialized widget (`value` ↔ `widget_0` / `raw_widgets.values[0]` for `Float`/`Int`/`Primitive*`), write **all** aliases in the same apply. Never leave `inputs["value"]` and `widgets["widget_0"]` disagreeing.
2. Python surface (`emit_agent_edit_python`): print one name (`value=25` **or** `widget_0=25`, schema name wins). Setting either updates both.
3. Fixture: the live Float 25→24 graph must emit `widgets_values[0] == 24` (or `'24'`/`24.0` under the existing numeric canonicalizer) and produce a non-null candidate.

**Expected flips.** **+1 certain** (`multi-image-to-video-generation-with-2`).
**Risk.** Low if the alias map is closed (primitive `value` / `widget_0` only). Do not invent aliases for schema-less custom nodes.
**Philosophy.** Upholds **2** (one authority), **1** (the product artifact must be the edit), **3** (emit must round-trip the landed field). Does not bend 4 — we are not loosening `guard_emit`; we are naming the field the Δ already claimed.

---

### RC-2 — Queue/done must not veto a landed widget Δ for pre-existing unknown classes

**Targets.** Queue-gate: `485ff2` (seed 42), `03fced` (steps 20→25 on uids 57/58).

**Evidence.** Both: `ui_emit_ok=true`, `queue_validate_ok=false`, `outcome.kind=noop`, done-summary “N unknown class type(s)”. Narrative `landed_operation_count` is 1 (`18.widget_0`→42) and 2 (`57.steps`/`58.steps`→25). The judge then grades the **rollback**, not the landed IR.

**Fix.**
1. Post-edit eligibility / `done()` must use *new* blockers only (`_has_new_topology_blockers`), never `TopologyFindings.has_blockers` (which ORs in every pre-existing unknown class — `contracts.py:1422-1430`).
2. Unknown-class identity for the “new?” test is **class_type**, not `node_id=X: Class` (`revision_evidence.py:166-173` + `:491-494`). Emit remaps must not resurrect the same class as a new blocker.
3. `queue_stage_result` / recovery report (`_frag_transform_stages.py:191-224`, `:229-250`): a widget-only Δ on a uid that was already unknown in `original_ui` is a warning, not a hard `queue_validate_ok=false`. **New** unknown classes, slot-name changes, and dangling/missing-required additions stay hard-block.
4. Fixture: seed-only edit on `INPAINT_InpaintWithModel` with two pre-existing unknown classes must keep `queue_validate_ok=true` and persist `widget_0=42`. Dual `steps` 20→25 on two KSamplers in a graph that also contains one unknown class must persist 25.

**Expected flips.** **+2** (`485ff2` certain, `03fced` certain on the landed 25 — the judge’s “Δ sets steps=20 / replaced samplers” is the rolled-back view).
**Risk.** Medium. Fail-open only for *untouched-class, widget-only*. Do not warn-not-block a new unknown class or a rewire of a schema-less node (`b55994` must still fail). Do not touch apply-gate.
**Philosophy.** Upholds **4** (attribute narrowly — the veto currently blames the whole graph), **5** (the agent *did* act), **1** (grade the landed product). Slightly bends 4 toward fail-open; that is the honest trade vs a second “safe” predicate.

---

### RC-3 — Inspect lens: named fields or explicitly unlabeled; no invented semantics

**Targets.** Semantic-product ungrounded: `1c7ad8` (UUID nodes “identical” + invented composite), `f855de` (8-bit VAE + `codec=auto`→lossy H.264), `4eebf3` (`widget_0/2/3/6` + non-existent `overlap`). **Not** `99e2a9`.

**Evidence.** All three `route=inspect`, `grounded=false`. `4eebf3` `correct=true` — the culprit (IPAdapterTiled uid 265) was right; the names were fake. Actual widgets `[1.2, 'ease in-out', 'concat', 0, 1, 0, 'V only']`. `f855de` evidence is a shared VAE link + `['output','auto','auto']`. Prompt already forbids invention (`prompts.py:509-513`); the model still sees positional indices (`graph_inspection.py:237-248` sets `name=None` when schema names run out).

**Fix.**
1. `_widgets_from_ir` / inspect reply lens: emit `name=value` when a schema or instance name exists. When it does not, emit `unlabeled[i]=value` and **never** the token `widget_N` as if it were a field.
2. Print `class_type` **and** any distinct `type` / display-title fields for every cited node (`1c7ad8` type UUIDs differ; titles are not types).
3. Reply rule (one sentence, `prompts.py:498-513`): “If the lens marks a widget unlabeled, say so; do not name it. Do not infer codec families, bit depths, or compositing from the string `auto` or from a `switch` widget.”
4. Do **not** change `semantic_answer_judge.prompt.md` groundedness. Do not add an SVD denoise fact.

**Expected flips.** **+2–3** (`4eebf3` high — already correct; `f855de` and `1c7ad8` if the model stops inventing). `99e2a9` **+0**.
**Risk.** Low. A louder “unlabeled” marker can make answers more cautious, not less grounded. Softening `grounded` would violate 12 — not done.
**Philosophy.** Upholds **9** (names over indices), **1**, **12**. Does not bend 10 if we change the lens, not the model.

---

### RC-4 — Classify: coerce `needs_input` shape; do not abort a valid revise

**Targets.** Malformed classify JSON: `d20410`.

**Evidence.** RC14 retry *fired* (2 classify attempts). Attempt 1 is a complete `route=revise, implement=true` object plus `needs_input: {decision:assumed, question, missing_information: "<string>", options, bounded_assumption}`. Attempt 2 is `route=clarify` and still `missing_required_fields`. `_downstream_failure_type` (`agent_backend.py:91-102`) labels **any** parse `ValueError` on a dict as `missing_required_fields`. `NeedsInput.from_dict` (`stage_contracts.py:131-157`) + `_text_tuple` (`evidence_pack.py:46-48`) reject a string `missing_information`. Attempt 2 then also hits `parse_classify_response` (`prompts.py:881-886`): clarify + `bounded_assumption` raises.

**Fix.**
1. `NeedsInput.from_dict`: coerce a string `missing_information` to a 1-tuple; ignore unknown extra keys instead of `_check_keys` fail-closed on a sidecar the classifier is not the authority for.
2. `parse_classify_response`: if `route`/`implement`/`intent` already form a valid revise/adapt, a malformed `needs_input` is dropped (logged), not a classify hard-fail. Keep the clarify+assumption raise **only** when `effective_route=="clarify"` *after* coercion.
3. Fixture: the attempt-1 payload must parse as `route=revise` and reach implement.

**Expected flips.** **+1** (`d20410` — this is the historical RC2 EmptyLatentImage/ADE frame-count edit; classify never let it run).
**Risk.** Low. One retry already spent. Do not treat leftover malformed JSON as infra.
**Philosophy.** Upholds **7** (the first payload *is* a bounded assumption), **10** (default a missing/wrong-type key), **8** (format flake ≠ product). Does not bend 12.

---

### RC-5 — Emit `outcome.kind=clarify` when the named class is schema-absent

**Targets.** Safe-refusal envelope: `c80bbf`. Same envelope for `f65774` *if* a product turn completes.

**Evidence.** `c80bbf` scenario already allowlists `clarify` / `requires_custom_nodes`. Live `outcome.clarification.question` is a real 3-option question (“AudioLDM2 is not available in the local ComfyUI schema…”). `outcome.kind` is **`candidate`**, `no_candidate_reason=no_changes`, `graph_unchanged=true`. Assessor therefore never enters `judge_grounded_refusal`. Secondary LiteGraph-counter and Hivemind 57014 stay as-is.

**Fix.**
1. When implement proves the *named* target class (`AudioLDM2`) is absent from `get_schema` / `NODE_CLASS_MAPPINGS` **and** the reply already contains a question + options, set `outcome.kind=clarify` (or `requires_custom_nodes` if that is the typed blocker) via the existing envelope (`executor_response.py:92-119`, `contracts.py:1349`).
2. Populate `outcome.missing_classes` so `_response_proves_class_absence` (`assessor.py:347-363`) is true.
3. Do **not** default the allowlist on every edit scenario. Do **not** emit clarify for a representable same-socket swap (`d813fe` / face-style refusals stay out).

**Expected flips.** **+1** (`c80bbf`). `f65774` **+0** this pass (infra).
**Risk.** Low if gated on schema-absence + a real question. Blanket “any failed implement → clarify” would bend 5 and 6 — not done.
**Philosophy.** Upholds **7** and **8**. Would bend **5** if we allowed a refuse that had a graph-local move — that is why kolors/face stay out.

---

### RC-6 — UID-anchor graph names for the life of a batch

**Targets.** Unbound-name: `a7ecc5`.

**Evidence.** Hard diagnostics: `Unknown graph name 'cliptextencode_4'` and `batch_identity_rejected` (`_parse_execute.py:95-105`, already `retryable=True`). No re-render+retry ran. `_refresh_bindings` (`_interpret.py:1218-1230`) rebuilds `name_to_uid` from `_compute_variable_names` after every apply — the same `{class_type}_{order}` sequence emit/ui.py:13-15 forbids as a match key.

**Fix.**
1. `_refresh_bindings`: names already bound to a still-present uid stay bound. New nodes receive new names. Never reassign a live name mid-batch.
2. `_resolve_name`: if the token is a uid, use it (already does via `_node_by_uid`). Prefer uid in the rendered surface for nodes the batch just added.
3. Optional one-shot retry on `batch_identity_rejected` only after (1) — without stable names the retry is theater.

**Expected flips.** **+0–1**. `a7ecc5` is a text→video → image→video rewire, not a one-widget edit. Stable names unblock the batch; they do not guarantee the rewire is the right product.
**Risk.** Low. Do not keep names for *removed* uids (that is the stale-name hole the rejector is right about).
**Philosophy.** Upholds **2** and **9**. The current rejector upholds **4**; we keep it and stop *creating* the stale name.

---

### RC-7 — Generalize “Missing stable link to port” remapping

**Targets.** Port-link: `19d221` (ACN_AdvancedControlNetApply strength 0.6→0.5).

**Evidence.** `failure_stage=implement`, `Missing stable link to port`, widget still 0.6. `test_c8_sdxl_widget_override_renumbers_remaining_link_slots` already encodes this defect for a *different* class. Remap lives at `emit/ui.py:3064-3085`.

**Fix.** Same remapper: when a widget write deletes or collapses a linked input slot, remaining inbound links on that node re-slot by **canonical input name**, or the emit refuses with the full endpoint evidence (already the B2 path). Add a fixture on the live ACN node 60 strength 0.6→0.5 corpus, not only SDXL `text_g`.

**Expected flips.** **+0–1**. Certain only if strength is a linked-slot collapse (the sdxl shape). If the miss is a phantom output on a different node, this RC does not flip it — fail closed and keep the row.
**Risk.** Medium. A wrong remap writes a silent wrong edge. Prefer refuse-with-evidence over a guessed slot.
**Philosophy.** Upholds **3** (inverse pair: widget write must still emit a projectable graph) and **4** (narrow remap, not “drop all links”).

---

### RC-8 — Infra: bound research so a 1200s turn can still emit a product (0 promised flips)

**Targets.** Infra: `f65774`, `3d-converts`, `d813fe`, `506ebd`.

**Evidence.** Run.md load peaked 300. Two of four are `killed_before_first_attempt` twice. `f65774` attempt_1 implemented and hit `RefusedEmit` `presence:[false,true]` on uids 23/33, then the outer kill. Hivemind 57014 still starves research; that is no longer an implement skip (RC2 shipped).

**Fix.**
1. Cap Hivemind/search wall-clock so classify+implement can still run inside 1200s (degrade-then-stop; already sketched in RC1). Do **not** raise `DEFAULT_PER_SCENARIO_TIMEOUT`.
2. Do **not** ship RC15 (presence re-add) in this pass. Fixture-first or skip — that guard is what stopped B1-S2-class state destruction.
3. Measurement only: keep these four in the infra ledger. A completed `f65774` clarify would be RC-5, not an infra “fix.”

**Expected flips.** **+0** product. **+0–1** completed-verdict if `f65774` finishes and RC-5 emits clarify.
**Risk.** Raising 1200s or loosening `guard_emit` presence would burn the rerun and reintroduce state destruction. Not done.
**Philosophy.** Upholds **8** and **11**. A global timeout raise would bend **10**.

---

## Explicitly not this pass

| Residual | Why skipped |
|---|---|
| `cc0df7` self-loop | Apply-gate is correct (`apply_gate.py:67-70, 167-176`). Forcing a pass bends 3 and 6. |
| `b55994` orphaned VC output | Judge is correct. Schema-less 425 is adjacent, not the scoring miss. |
| `99e2a9` SVD denoise | `correct=false` on a grounded answer. Softening violates 12. |
| LiteGraph counter (`c80bbf` secondary, `b55994` batch-1) | Keep `_guard_counter` (`emit/ui.py:3715-3726`). Prefer reuse-ids later, not a relax. |
| RC15 presence-flip on `f65774` | High chance of reintroducing unattributed node re-adds. |
| “Smarter inspect prompt” as the primary `1c7ad8` fix | Principle 10. RC-3 changes the lens. |
| Two-step pipeline | Wrong venue (~60h). |

---

## Philosophy audit (residuals → fixes)

| Residual | Violates | Fix upholds | Fix would bend if we… |
|---|---|---|---|
| Dual `value`/`widget_0` | **2, 1, 3** | 2, 1, 3 | Wrote a third alias table instead of the schema map |
| Unknown-class veto of landed widget Δ | **4, 5, 1** | 4, 5, 1 | Warned on *new* unknown classes or rewires |
| Inspect invented names / codec / composite | **9, 1** | 9, 1, 12 | Softened `grounded` (`99e2a9`/`b3ba8a`-style) |
| `needs_input` string → classify death | **7, 10, 8** | 7, 10, 8 | Marked it harness-retryable infra |
| Clarify kind not emitted | **7, 8** | 7, 8 | Allowlisted every edit scenario |
| Mid-batch name renumber | **2, 9** | 2, 9 | Dropped the stale-name rejector |
| Missing stable link | **3** | 3, 4 | Guessed a slot instead of remapping by name |
| 1200s / never-started | **8, 11** | 8, 11 | Raised the wall or loosened `guard_emit` |
| Self-loop / orphan (`cc0df7`, `b55994`) | none — product holding | keep RC6 / judge | Shipping a pass here |

---

## Round-2 target

| Package | PASS | What has to be true |
|---|---|---|
| 30-v1 now | **13 / 30** | 13 fail + 4 infra |
| Conservative | **18 / 30** | RC-1 +1, RC-2 +2, RC-3 +1, RC-4 +1. RC-5/6/7 miss or variance. Infra still 4. |
| **Target** | **18–20 / 30** | Conservative **plus** RC-3 second inspect (`f855de` or `1c7ad8`) **and/or** RC-5 `c80bbf`. |
| Stretch | **21 / 30** | RC-6 or RC-7 also lands. Still 4 infra + `cc0df7` + `b55994` + `99e2a9`. |
| Do not promise | 22+ | Those three product holds + four infra are the honest ceiling this pass. |

**Significant = the target row (18–20 PASS), +5–7 on 13.** Measured by a fresh 30-v1 rerun on a clean HEAD, idle machine, `max-workers` 2–3. Count `assessment.json.passed` on the terminal attempt. Include `video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3` and `video-wanvideo-text-to-video-generation-71f825` as inspect regression guards (variance on RC-3).

Do not declare victory from unit tests.

---

## What this corpus is still missing

1. `d813fe` / `506ebd` have no Flash product packet — only the infra signature. Do not invent a kolors/face substitution RC from the 57-set memory.
2. `19d221` implement diagnostics are a one-line `Missing stable link to port` — no which endpoint. RC-7 is fixture-first or it stays +0–1.
3. `03fced` judge text (“replaced samplers, steps=20”) contradicts narrative `57.steps`/`58.steps`→25. After RC-2, if the product is 25 and the judge still fails, that is a **new** judge-surface row, not a reason to skip RC-2.
4. Inspect lens byte dumps for `1c7ad8` / `f855de` / `4eebf3` were not attached to the batch docs. RC-3 assumes `_widgets_from_ir` is what the model saw; confirm against `graph_inspection` in those `response.json`s before calling `1c7ad8` a certain flip.
5. Implement `user_msg`/`system_msg` sizes on the four I-B rows are still uncollected. That is why RC-8 does not raise a timeout.

---

## Implementation pointers

| RC | Files |
|---|---|
| RC-1 | `vibecomfy/porting/edit/_ir_utils.py:658-671`; `porting/emit/emit_agent_edit.py`; `porting/helper_resolve.py:50` (already reads `value` then `widget_0` — invert that into a single write) |
| RC-2 | `vibecomfy/executor/revision_evidence.py:465-499`; `executor/contracts.py:1422-1430`; `comfy_nodes/agent/_frag_transform_stages.py:191-250`; `comfy_nodes/agent/_frag_revision.py:127-147` (keep subtract; stop using unfiltered `has_blockers` at done()) |
| RC-3 | `vibecomfy/executor/graph_inspection.py:223-264`; `executor/prompts.py:498-513`; `intent/prompts/semantic_answer_judge.prompt.md` (**do not** weaken) |
| RC-4 | `vibecomfy/executor/stage_contracts.py:131-157`; `executor/prompts.py:881-888`; `executor/agent_backend.py:91-102` |
| RC-5 | `vibecomfy/comfy_nodes/agent/executor_response.py:92-119`; `assessor.py:347-393`; outcome envelope wherever `kind` is set to `candidate` on a clarify message |
| RC-6 | `vibecomfy/porting/edit/_interpret.py:986-1028, 1218-1230`; `_parse_execute.py:87-122` |
| RC-7 | `vibecomfy/porting/emit/ui.py:3064-3085`; extend `tests/test_porting_ui_emitter.py:3356` to the ACN live case |
| RC-8 | `vibecomfy/executor/hivemind_clients.py` / `agent_research_stage.py` wall-clock; `tests/live_agentic_harness/runner.py` 1200s **unchanged** |
| Do not touch | `porting/edit/apply_gate.py`; `emit/ui.py:3715` `_guard_counter`; groundedness bar |
