# Dual-path root-fix strategy — 2026-08-20

**Role:** Grok strategy / philosophy audit for the four dual-path root-cause groups.
**Evidence:** `.oracle/findings/dual-path-20260820-batch-1.md`; four-mode comparator `/private/tmp/vibecomfy-dualpath-four-run-20260820-r3/comparison.json`; preserved audio pair `/private/tmp/vibecomfy-dualpath-five-run-20260820-r2/`.
**Philosophy:** `.oracle/agent_philosophy.md` is not in this tree; principles below are from the pipeline-reference copy (`pipeline-reference-2026-08-18/agent_philosophy.md`).
**Do not** bypass replay, accept positional `widget_N` as canonical, drop the one-batch-fence rule, or treat health-control `passed: true` as product success.

---

## Target

The same five locked identities must be **meaningfully exercised in both modes** after a clean committed rerun:

| Identity | Product job | Current both-mode result |
|---|---|---|
| `image-image-editing-with-qwen-image` | named prompt edit + replay | both fail `authority_replay_mismatch` (Δ is semantically right; field is `widget_0`) |
| `audio-tts-narration-using-indextts-2` | named IndexTTS field edits + replay | both fail; positional `widget_5/6/7` because schema missing |
| `multi-video-based-character-replacement-using` | named LayerMask/prompt edit + replay | staged: 37 research calls then second `multiple_batch_fences` abort; threaded: named `prompt` with LayerMask schema absent |
| `live-graph-explanation-smoke` | inspect 3-node/3-edge graph | both health-control pass; staged reply claims empty graph |
| `speed-distillation-research` | research with evidence, no graph | both health-control pass; threaded `n_calls=0`, `No graph attached; implementation skipped.` |

Locked inputs already match (`all_inputs_locked_equal: true`). Comparison success is **not** `both_pass` on health-control. It is: both modes run the shared request/edit/authority/evidence/assessment contracts; only deliberation policy differs.

Honest ceiling after this sprint, philosophy intact: **Qwen both-pass is the high-confidence flip. Inspect + research become honest exercises (likely pass once the short-circuits and census guard land). Audio and multi-video pass only if the touched custom-node schema is actually in the frozen witness — otherwise they must stay fail-closed.**

---

## Shared-contract rule (every RC)

Staged and threaded already share the edit kernel (`handle_agent_edit` / batch REPL), authority (`authority_receipts.recompute_apply` / `verify_replay` / `stamp_response_with_authority`), and reply grounding (`core._enforce_reply_grounding`). They must also share:

1. **Request purpose** derived from `request.graph` + `request.interaction_mode` (not a second classifier).
2. **Accepted Δ vocabulary** — render-visible names, never `widget_N`.
3. **Schema-witness gate** — a touched class missing from the frozen witness rejects the candidate *before* narration.
4. **Evidence/assessment** — research requires executed evidence; inspect must not contradict `inspect_graph()` census.

Deliberation may still differ: staged = classify then separate research/implement/reply; threaded = one bounded conversation. That is the only allowed split.

---

## RC-1 — Canonical named fields + schema-present gate (shared edit/authority)

**Problem.** Qwen, audio, and threaded multi-video all generated an edit the intent judge could like, then authority correctly failed closed. Two seams, one contract:

- Batch REPL records `set_node_field(..., "widget_0")`. `_interpret.py:_canonical_field` → `_canonical_schema_input_name` only reverse-maps Pythonic aliases (`prompt_` → `prompt`). It does **not** map positional `widget_N` onto schema-ordered names even when the frozen witness already exposes `prompt`. Typed tools (`typed_tools.py:135-141`) and `_op_validate._validate_field` already reject positional fields. Direct replay therefore disagrees with the live batch.
- `candidate_transaction.build_schema_witness` records `missing_class_types` and still lets the candidate narrate. Audio IndexTTS and LayerMask are in that hole: positional writes are accepted because there is no named field, then replay rejects.

Artifact synthesis keeping `final.ui.json == original` is **correct**. Do not change that.

**Fix (shared kernel, both modes).**

1. **Canonicalize before the accepted Δ is sealed.** In `_interpret.py:_canonical_field` (and the same helper used by typed-tool lowering if a positional slips through), resolve `widget_N` via `compact_widget_names_for_node` / `compact_field_names_for_node` (`porting/widgets/compact_resolver.py`, `settings_contract.py`). If slot N has a non-positional name in the schema/witness (`prompt`), rewrite the op target to that name **before** `accepted_batch` is persisted. Compact-resolver Law 5 already says positional aliases are never emitted.
2. **Missing schema is fail-closed, not a positional fallback.** If the touched class is in `schema_witness.missing_class_types`, reject the candidate before `_narrate_final_message` / reply projection. Put the gate next to `build_schema_witness` / `build_and_persist_authority_receipt` (`candidate_transaction.py`, `authority_receipts.py`). Reason stays a narrow schema-missing code, then existing stamp still forces applyability false. Do **not** invent names. Do **not** skip `verify_replay`.
3. **Keep `_op_validate` positional rejection.** Canonicalization is the live-path repair; the validator remains the replay/typed-tool backstop.
4. **Preserve `no_candidate_reason=authority_replay_mismatch`** when replay still fails. Qwen's assessment saw `no_changes` even though the receipt reason is mismatch — that rewrite is a measurement lie (`_frag_revision_stages.py` / response-contract collapse). Stop collapsing authority reasons into `no_changes`.

**Likely files/functions.**

- `vibecomfy/porting/edit/_interpret.py` — `_canonical_field`, `_surface_field_name`, `_set_field`
- `vibecomfy/porting/edit/_ir_utils.py` — `_canonical_schema_input_name`, `_canonical_input_name_for_class`
- `vibecomfy/porting/edit/widget_slots.py` — `_canonical_ui_only_widget_field` (today only maps `control_after_generate`)
- `vibecomfy/porting/edit/_op_validate.py` — `_validate_field` (keep reject)
- `vibecomfy/porting/edit/typed_tools.py` — `edit_node` positional reject (keep)
- `vibecomfy/porting/widgets/compact_resolver.py` — `compact_widget_names_for_node`, `widget_index_for_field`
- `vibecomfy/comfy_nodes/agent/candidate_transaction.py` — `build_schema_witness`, `validate_schema_witness`, `FrozenSchemaProvider`
- `vibecomfy/comfy_nodes/agent/authority_receipts.py` — `recompute_apply`, `verify_replay`, `stamp_response_with_authority`, `build_and_persist_authority_receipt`
- `vibecomfy/comfy_nodes/agent/_frag_response_contract.py` — candidate/narration sequencing
- Schema coverage for IndexTTS / LayerMask in the authoring provider (add the real schema; do not stub names)

**Regression tests.**

- Unit: Qwen `TextEncodeQwenImageEditPlus` `widget_0` assignment canonicalizes to `prompt`; `accepted_batch` field_path is `prompt`; `verify_replay` with frozen witness succeeds.
- Unit: positional `widget_N` with **no** named slot → `widget_unknown` / reject, never a sealed positional Δ.
- Unit: delta touching `IndexTTS*` / `LayerMask*` while class is in `missing_class_types` → candidate rejected **before** narration; `final.ui.json` unchanged; `no_candidate_reason` is schema-missing or `authority_replay_mismatch`, not `no_changes`.
- Unit: typed-tool `field="widget_0"` still raises `invalid_arguments`.
- Existing: `tests/test_agent_edit_settings_contract.py`, `tests/test_agent_edit_artifact_replay.py`, compact-resolver Law 5 tests.
- Lock: replay still fail-closed on hash mismatch (`stamp_response_with_authority`).

**Expected flips.** Qwen both-mode **high**. Audio **conditional** on IndexTTS schema actually freezing. Threaded multi-video **conditional** on LayerMask schema freezing. If the schema is genuinely absent, those rows stay honest FAIL.

**Risks.** Mapping the wrong slot when compact names are incomplete; unlabeled widgets must stay `widget_unknown`, not a guessed name. Do not feed live `/object_info` into replay — FrozenSchemaProvider is the replay authority. Do not loosen `_op_validate`.

**Philosophy.** Upholds 1 (Δ is the edit), 2 (one authority), 3 (replay identity), 4 (narrow fail-closed), 6 (verify, don't refuse a named write), 9 (names over indices). Would bend 3/4/9 if we accepted `widget_N` or skipped replay.

---

## RC-2 — Threaded research short-circuit (shared request + evidence)

**Problem.** `_threaded_plan` maps every non-`answer_only` request to `adapt/edit`. `_run_implement` then hits `if request.graph is None and executor_route != "research": skip`. Speed-distillation therefore makes **zero** provider calls. Staged classifies `research` and actually loops. Health-control assessment has no evidence requirement, so threaded `both_pass` is a measurement fake.

**Fix (host policy, not a classifier).**

1. Extract a shared purpose helper used by threaded (and as a floor for staged answer-only):
   - `graph is None` → `route="research"`, `implement=False` is wrong here: research **must run**. Threaded should call the shared research conversation / `_run_implement` with `executor_route="research"` so the `graph is None` skip does not fire.
   - `interaction_mode=="answer_only"` and graph present → `route="inspect"`, `implement=False`, inspect lens + reply (RC-3).
   - else → `adapt` as today.
2. Implement in `executor/threaded.py:_threaded_plan` and keep `_run_implement`'s skip only for non-research routes. Do not add a classifier call.
3. Assessment: a research-purpose scenario cannot pass with `research_attempt=="never"` / `n_calls==0` / empty `research.json`. Shared in `tests/live_agentic_harness/assessor.py`. Keep health-control exclusion from semantic rates if desired; do not let it rubber-stamp zero evidence.

**Likely files/functions.**

- `vibecomfy/executor/threaded.py` — `_threaded_plan`, `run_threaded_executor` (always calls `run_implement`; plan.route must be `research` when graph is None)
- `vibecomfy/executor/core.py` — `_run_implement` skip at ~1475, `_answer_only_plan`, `run_executor` dispatch
- `vibecomfy/executor/agent_research_stage.py` — staged research loop (unchanged contract; threaded research-only must produce the same ledger shape)
- `vibecomfy/agent/contracts.py` / `executor/contracts.py` — `interaction_mode`, `pipeline_mode`
- `tests/live_agentic_harness/scenarios/speed-distillation-research.json` — evidence requirement
- `tests/live_agentic_harness/assessor.py` — `_scenario_kind` / research evidence checks
- `tests/live_agentic_harness/compare_pipeline_modes.py` — locked fields already include `interaction_mode`

**Regression tests.**

- Fake-provider: no-graph query in threaded mode enters research tools; `n_calls >= 1`; `research.json` ledger non-empty; graph unchanged.
- Staged same query still research-route; ledger contract equal (not call-for-call).
- `answer_only` + no graph still cannot implement (`tests/test_executor_flows.py` answer_only cases).
- Assessor fails a research scenario with `n_calls==0`.

**Expected flips.** Speed-distillation **meaningfully exercised** both modes. Product pass likely if Hivemind is up; if Hivemind times out, mark **infra** (principle 8), do not call it product FAIL. That is a measurement fix as much as a product fix.

**Risks.** Routing every no-graph request to research, including accidental empty-graph edits. Acceptable: no graph cannot be edited. Do not infer `answer_only` from `apply=false`.

**Philosophy.** Upholds 5 (agent should act/research), 8 (infra ≠ product), 11 (honest measurement). Would bend 11 if health-control zero-call pass remains the score.

---

## RC-3 — Inspect census postcondition + persisted reply prompt (shared inspect)

**Problem.** Staged classified `inspect_graph`, `inspect_graph()` on the attached API graph is 3 nodes / 3 edges, and the reply still said the graph is empty. Threaded treated the same request as `adapt` and asked a useful clarify — better product, wrong route. The exact reply prompt is not persisted (`run_reply_turn` builds `build_reply_messages` then discards them). `_enforce_reply_grounding` checks landed-edit claims and node ids, not census contradictions. Health-control scores both as pass.

`inspect_graph` ingest-failure returning empty evidence is a real footgun (`graph_inspection.py:1018-1025`) but the finding is that the census **was** non-empty, so this is reply-vs-evidence, not ingest.

**Fix.**

1. **Mechanical census guard in the shared reply kernel.** After inspect/answer-only reply, if `inspect_graph(graph).node_count > 0` and the reply claims empty / 0 nodes / 0 links, fail-closed and **retry the reply once** with the census line (`node_count=N, edge_count=M`). Same shape as the existing one-shot inspect retry idea; live in `_enforce_reply_grounding` / `_run_reply` so threaded projection uses it too.
2. **Persist the exact reply messages** next to other turn artifacts (`run_reply_turn` in `agent_backend.py`; staged inspect currently has no `model_request` for reply content).
3. **Shared inspect purpose:** lock `interaction_mode=answer_only` on `live-graph-explanation-smoke` and map that + attached graph to `route="inspect"` in `_threaded_plan` **and** `_answer_only_plan` (today answer_only + inspect stays inspect in staged because inspect is in `_ANSWER_ONLY_ROUTES`; threaded answer_only currently goes to `research`). Threaded inspect must call `inspect_graph` + `_run_reply(..., graph_inspection=render_inspect_markdown(...))` rather than `run_implement`.
4. **Assessment:** inspect smoke cannot pass if reply contradicts census, even as health_control. Optional light rubric: names `CheckpointLoaderSimple` / `CLIPTextEncode` / `KSampler` or asks one clarify about missing latent/negative/VAE — both are grounded.

**Likely files/functions.**

- `vibecomfy/executor/core.py` — `_enforce_reply_grounding`, `_run_reply`, `_run_staged_executor` inspect branch (~2894), `_answer_only_plan`
- `vibecomfy/executor/threaded.py` — `_threaded_plan`, `run_threaded_executor` inspect/no-implement path
- `vibecomfy/executor/graph_inspection.py` — `inspect_graph`, `render_inspect_markdown`, `GraphEvidence.node_count`
- `vibecomfy/executor/agent_backend.py` — `run_reply_turn`
- `vibecomfy/executor/prompts.py` — `build_reply_messages`
- `tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json`
- `tests/live_agentic_harness/assessor.py`

**Regression tests.**

- Fixture 3-node graph + canned empty-graph reply → guard fires; after retry a census-bound reply passes; without retry the health-control would have passed (prove the new check).
- Persist `reply_messages.json` / model_request includes `graph_inspection` markdown with node_count=3.
- Ingest API-shaped `{id: {class_type, inputs}}` still yields 3 nodes (lock `inspect_graph` against empty-on-ingest).
- Threaded + `answer_only` + graph does not call implement; `graph_unchanged` true.
- Existing `tests/test_graph_inspection.py`, `tests/test_executor_contracts.py` inspect_graph routing.

**Expected flips.** Inspect **meaningfully exercised** both modes. Product pass **likely** with one retry; without retry, staged becomes an honest FAIL (better than today's fake pass).

**Risks.** Regex over-match (“empty latent”, “empty negative”). Scope the detector to graph-census claims (`0 nodes`, `empty graph`, `no links` as a graph statement). Do not strip `widget_N` from the **edit** surface.

**Philosophy.** Upholds 1 (prose cannot contradict the graph), 10 (detector + one retry, not a third prompt), 11, 12. Would bend 12 if we accepted the empty-graph paraphrase.

---

## RC-4 — Deterministic research/tool and protocol bounds (shared loop policy)

**Problem.** Staged research is bounded only by a 450s wall (`agent_research_stage._MAX_TURNS = None`, docstring: “calls and turns are unbounded”). Multi-video made 37 calls, many Hivemind 5s timeouts, then handed a huge ledger to implement. One protocol retry already exists (`edit_batch_repl.py` ~1091–1144). The retry still emitted multiple ````batch` fences; `extract_batch_fence` correctly aborted (`parse_reason=multiple_batch_fences`). That abort is right.

**Fix.**

1. **Finite production `max_turns` / max evidence calls** in `run_agent_research_stage` (suggested 8 decision turns, 12 tool calls, consecutive Hivemind timeouts 3 then stop searching). Use the same numbers as a host policy constant the threaded combined conversation can see (threaded already has `THREADED_MAX_AGENT_BATCHES=24`; do not let staged research exceed a similar envelope). Keep the 450s wall as a backstop, not the only bound.
2. **Timeouts are infra:** reuse `_hivemind_degraded_ilike` / 57014 degrade (`hivemind_clients.py`); after N consecutive timeouts, record typed exhausted evidence and finish. Do not keep hammering 5s timeouts until 450s.
3. **Protocol retry stays exactly one.** Lock `attempt_count==2` then abort. Do not add a second protocol retry to buy the multi-video pass. Smaller research context is the lever that makes the first implement turn parse.
4. Optional: after research, pass only the compact ledger (`_MAX_DIGEST_CHARS` already 4000) into implement — verify the 37-call run actually forwarded a compact ledger (`core.py` comment at 1451). If the full trace leaked, that is a contract bug to close.

**Likely files/functions.**

- `vibecomfy/executor/agent_research_stage.py` — `TOOL_PHASE_DEADLINE_SECONDS`, `_MAX_TURNS`, `run_agent_research_stage` loop ~1403, `_run_decision_turn_with_retry` (`_RESEARCH_DECISION_MAX_ATTEMPTS=3` is parse-retry, keep)
- `vibecomfy/executor/hivemind_clients.py` — timeout 5.0s, degrade path
- `vibecomfy/comfy_nodes/agent/provider.py` — `extract_batch_fence` (keep multi-fence reject)
- `vibecomfy/comfy_nodes/agent/edit_batch_repl.py` — protocol retry (keep one)
- `vibecomfy/comfy_nodes/agent/_frag_batch_loop.py` — `_BATCH_PROTOCOL_RETRY_PROMPT`, `_batch_protocol_retry_messages`
- `vibecomfy/executor/threaded.py` — `ThreadedPurposeBudget` (do not raise)

**Regression tests.**

- Fake judge that always `call`s `hivemind_search`: loop stops at the new max_turns/max_calls; status `exhausted`; evidence retained.
- Three consecutive timeouts → degrade then stop; no 37-call trace.
- Protocol: first response multiple fences → retry once → second multiple fences → `MalformedModelJSON`, graph unchanged (`tests/test_comfy_nodes_agent_edit.py` protocol-retry lock).
- Compact ledger byte-size cap at implement boundary (`tests/test_executor_flows.py` “only compact ledger crosses”).

**Expected flips.** Multi-video staged **stops being incomplete-amplification**. Product pass **low-to-medium**: still needs RC-1 LayerMask schema + a single well-formed batch. Do not budget a guaranteed PASS from bounds alone.

**Risks.** Cap too low → thin research on adapt routes (principle 5: graph-local edits may still proceed). Cap too high → same blowup. Prefer a hard call cap over a longer wall. Do not disable Hivemind.

**Philosophy.** Upholds 8 (timeouts are infra, bound them), 10 (boring caps). Would bend 6/10 if we allowed multiple batch fences or skipped the atomic-turn abort.

---

## Integration order

Land as separate commits, in this order. Do not rerun the five until 1–3 are committed on a clean tree.

| Step | RC | Why first |
|---|---|---|
| 1 | RC-1 canonicalize `widget_N` → named field in interpret | Unblocks Qwen without touching drivers. Shared kernel. |
| 2 | RC-1 missing-schema gate before narration + stop collapsing `authority_replay_mismatch` | Makes audio/LayerMask honest; keeps replay sacred. |
| 3 | RC-2/RC-3 shared purpose helper (`graph is None` → research; `answer_only`+graph → inspect) | One host-policy function; both drivers. |
| 4 | RC-3 census guard + persist reply prompt + inspect assessment | Makes inspect measurable. |
| 5 | RC-2 research-evidence assessment | Makes research measurable. |
| 6 | RC-4 finite research caps + consecutive-timeout stop | Prevents multi-video amplification; protocol retry stays 1. |
| 7 | Schema coverage for IndexTTS and LayerMask **only if the real schema exists** in the authoring provider | Optional pass-enabler; never a stub. |
| 8 | Clean committed dual-path rerun of the five identities | Measurement. |

Do **not** rescan or loosen guards mid-queue.

---

## Philosophy audit

| Residual | Violates today | Fix upholds |
|---|---|---|
| Positional Δ vs named witness | 3, 9 | 3, 9, 4 |
| Missing custom-node schema still narrated | 4, 6 | 4, 6 (verify then refuse) |
| Threaded zero-call research pass | 5, 11 | 5, 11, 8 |
| Empty-graph inspect vs census | 1, 11, 12 | 1, 10, 12 |
| Unbounded research + correct protocol abort | 8, 10 | 8, 10 |

Would **fail** this audit: skipping `verify_replay`; treating `widget_N` as canonical; a second protocol retry; health-control as the five-row score.

---

## What the corpus / harness is missing

- Comparison manifest default still has six rows (`3d-…cc0df7`, `audio-acestep-…`) and not the IndexTTS identity. The **rerun manifest must be exactly the five locked identities above**, with the r2 audio lock hash, not a silent substitution.
- `speed-distillation-research` and `live-graph-explanation-smoke` are `health_control` with `expect_graph_changed: false` only. That cannot detect the defects in this batch. Add mechanical evidence/census checks; do not pretend a semantic judge rewrite is required.
- Reply prompts are not artifacts. Persist them.
- No test today drives `widget_0` through interpret → accepted_batch → frozen-witness replay for Qwen.

---

## Rerun contract

- Clean HEAD, idle machine, `max-workers` 2–3.
- Tag e.g. `dual-path-20260820-r4`.
- Modes: staged + threaded, locked inputs unchanged.
- Score: per identity, both modes **exercised** (non-zero inspect/research/edit kernel work as appropriate) and **product pass/fail/infra** from `assessment.json`, not executor `ok`.
- Flip table vs this doc's expected flips. Variance on inspect is still possible; the census guard is the non-variance part.
