# MEGADO Phase 4 — Frozen Agent-Edit Pipeline Tasklist

**Frozen from:** `docs/failure-analysis/agentic-pipeline-improvement-2026-08.md` at repository SHA `6ac560fa`
**Revision 1 (pre-execution, orchestrator):** B02 re-scoped per the matcher deep-dive (2026-08-12) + design decision — **the agent always writes the message, from the facts**: remove deterministic prose gating (assessor `message_artifact` + producer-side discard-and-replace fallback), make synthesis fact-grounded (agent receives and must describe the structured outcome), scoring structured-only. Folded the `_frag_research.py:821` schema-precedence quick win in as a B02 rider. B06 updated to cover the remaining precedence sites.
**Execution order:** B01 → B02 → B03 → B04 → B05 → B06 → B07 → B08 → B09 → B10 → B11
**Normal executor:** DeepSeek V4 Flash, one executor per batch
**`[HARD]` executor:** GPT-5.6 Sol, high reasoning
**Oracle:** GPT-5.6 Sol, high reasoning, read-only review at every checkpoint

This file is the frozen Phase 4 execution contract. An executor may make the smallest supporting edit required by a listed task, but may not add a new objective, silently weaken an acceptance criterion, or reorder batches. Any necessary revision must be proposed as an oracle issue and recorded in the relevant `.oracle/checkins/batch-XX.md` before execution continues.

## Execution and checkpoint protocol

Before B01, the orchestrator records `C00`, the clean execution-start SHA after this tasklist is placed on the execution branch. After each batch:

1. Run every batch command and retain its complete output.
2. Commit only that batch's intentional files and record the resulting SHA as `CXX`.
3. Give the oracle the batch tasks and acceptance criteria below, implementation notes, command output, and the complete diff `git diff C(previous)..CXX` (plus `git diff --check C(previous)..CXX`).
4. The oracle writes exactly one formal checkpoint file, `.oracle/checkins/batch-XX.md`, whose verdict is either `PASS` or an issue list.
5. For an issue list, route rework to the same executor class, amend/commit the rework, rerun all acceptance commands, and resubmit the entire diff from the last passed checkpoint. Do not start the next batch until the verdict is `PASS`.

Every checkpoint must reject unrelated changes, untested fallback behavior, metric fields that cannot be derived from persisted evidence, and tests that merely restate implementation internals without exercising the reported failure.

---

## B01 — Lock the recovered batch-protocol retry

**Executor:** DeepSeek V4 Flash
**Plan item:** 4

### Tasks

1. Add a behavioral regression around the real sync protocol-retry path near `edit_batch_repl.py:1528`.
   - Touch: `tests/test_comfy_nodes_agent_edit.py` only.
   - Drive the facade so its first call raises `MalformedModelJSON` and its second returns a valid batch response.
   - Exercise the code that calls `dataclasses.replace`; do not settle for an import-presence or source-text assertion.
   - Assert exactly two facade calls, a successful normalized second result, and no `NameError`/failure-envelope conversion.

### Verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_comfy_nodes_agent_edit.py::test_agent_edit_batch_protocol_retry_executes_dataclasses_replace \
  tests/test_comfy_nodes_agent_backend_spine.py::test_run_agent_turn_batch_retries_empty_content_once_then_succeeds
```

Expected: 2 selected tests pass; the new regression fails if `import dataclasses` is removed.

### Acceptance criteria

- The test reaches the retry-time `dataclasses.replace` call and proves valid recovery on call two.
- Existing empty-content retry behavior remains green.
- Production code is unchanged in this batch.

### Formal checkpoint B01

Review the B01 criteria and `git diff C00..C01`. Confirm that this is a behavioral regression lock, not an implementation-coupled import check. Verdict: `PASS` or issue list; rework B01 until `PASS`.

---

## B02 — Demote message/artifact prose matching to warning; land schema-precedence quick win

**Executor:** DeepSeek V4 Flash (rider) + GPT-5.6 Sol (matcher demotion)
**Plan item:** 1 (revised per matcher deep-dive) + rider from item 7

### Context — why this changed

Deep-dive verdict (MatcherDeepDive, 2026-08-12): the prose matcher is **redundant with the producer-side narrative guard** (`edit_humanize.py:975-1070 _validate_narrative_message` runs the same edit-claim/no-edit-claim regexes at message-synthesis time and discards nonconforming LLM messages in favor of a deterministic fallback). The assessor's copy is a post-hoc second check of the same envelope. **28/28 firings were false positives at error severity (12 failed otherwise-clean runs); zero genuine catches.** The agent's prose must never be deterministically gated — structured fields (`graph_unchanged`, `outcome.kind`, `landed_operation_count`) are the truth and are already guarded by their own checks.

### Tasks

1. **[HARD] Remove deterministic prose gating; make message synthesis fact-grounded.**
   - Touch: `tests/live_agentic_harness/assessor.py` (remove/demote the `message_artifact` emission at `:868-870` and contradiction collector `:240-320`), `edit_humanize.py` (`_validate_narrative_message` at `:975-1070` and the discard-and-replace fallback at `:1150-1160`), the message-synthesis prompt, `tests/test_live_agentic_harness_guard_contract.py`, `tests/test_live_agentic_assessor_score_honesty.py`, `tests/test_comfy_nodes_agent_backend_spine.py`.
   - **End state (three clauses):**
     a. The agent ALWAYS writes the message — no deterministic substitute is ever shipped in its place; the producer-side discard-and-replace is removed.
     b. The message is written FROM the facts: the synthesis prompt feeds the agent the structured outcome (`graph_unchanged`, `outcome.kind`, `landed_operation_count`, validation/error details) and requires the narrative to describe exactly those facts ("you MUST state what happened per these fields; never claim an edit you did not land").
     c. Scoring is structured-only: prose never gates a scenario (`message_artifact` is removed or warning-only backstop at most).
   - Structured cross-checks (graph_changed, outcome_kind, landed counts) remain fully authoritative and unchanged.
   - Encode the nine enumerated matcher-only scenarios as counterexample fixtures proving no error-severity prose issue; keep four affirmative contradiction controls that must still fail via the STRUCTURED checks.

### Rider (quick win, pulled forward from B06)

2. **One-line schema-precedence swap** — `_frag_research.py:821` `CompositeSchemaProvider(provisional, state.schema_provider)` → `CompositeSchemaProvider(state.schema_provider, provisional)` (real schema first; the same invariant already holds at `:922`). Touch: `vibecomfy/comfy_nodes/agent/_frag_research.py` only. Verify the confirmed shadowing case no longer hides real fields behind `widget_N` (CutAndDragOnPath in the 485ff2 session).

### Verification

```bash
.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py \
  -k 'message_artifact or contradiction'
```

Expected: the 9 matcher-only scenarios produce no error-severity message_artifact issues; genuine contradiction controls still fail via structured checks.

```bash
.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py tests/test_comfy_nodes_agent_backend_spine.py
```

Expected: exit 0, no scoring regressions.

```bash
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy && .venv/bin/python -m pytest -q tests/test_comfy_nodes_agent_edit.py tests/test_m1_contracts.py -p no:cacheprovider
```

Expected: exit 0 (rider: schema swap does not regress the edit surface or m1 contracts).

### Acceptance criteria

- The 9 matcher-only failures recover (+9 true pass) via prose no longer being error-gated.
- The agent's message is ALWAYS the agent's own text — no deterministic fallback substitution exists in the pipeline.
- The synthesis prompt requires fact-grounded narratives (agent receives and must describe the structured outcome); verified by a fixture where the facts say unchanged and the narrative cannot claim landed edits.
- Genuine message/artifact inconsistency can never hide: it is caught by the structured checks, and the fact-grounded prompt prevents it at synthesis.
- Rider: `_frag_research.py:821` real-schema-first; the 485ff2 CutAndDragOnPath case resolves to named fields, not `widget_N`.

### Formal checkpoint B02

Review the end-state clauses (agent always writes / fact-grounded synthesis / structured-only scoring), the 9 counterexamples, the four structured controls, the removed fallback, the rider diff, and `git diff C01..C02`. Look for any residual deterministic prose gate anywhere in the pipeline and confirm the structured guards are untouched. Verdict: `PASS` or issue list; rework B02 until `PASS`.

---

## B03 — Truthful classification and typed model-failure evidence

**Executor:** GPT-5.6 Sol
**Plan items:** 2 and 11

### Tasks

1. **[HARD] Remove the fake classification fallback and make phase failure explicit.**
   - Touch as required: `vibecomfy/executor/core.py`, `vibecomfy/executor/contracts.py`, `vibecomfy/executor/agent_backend.py`, `vibecomfy/executor/provenance.py`, `vibecomfy/agent/artifacts.py`, `tests/test_executor_contracts.py`, and focused executor/artifact tests.
   - Replace failure-time `ClassifyDecision.respond_only()` artifacts with `classification_status: success|failed` and a nullable decision/plan. Preserve a typed phase failure without inventing `intent=respond` or `route=respond`.
   - Keep successful public response compatibility where it is truthful; update internal/report contracts deliberately rather than smuggling a sentinel `ClassifyDecision` through them.

2. **[HARD] Type empty provider responses and persist complete failed-call provenance.**
   - Touch as required: `vibecomfy/comfy_nodes/agent/worker.py`, `vibecomfy/comfy_nodes/agent/runtime.py`, `vibecomfy/comfy_nodes/agent/provider.py`, `vibecomfy/executor/agent_backend.py`, `vibecomfy/agent/artifacts.py`, `tests/test_agent_runtime_adapter.py`, `tests/test_headless_agent_artifacts.py`.
   - Distinguish `empty_response` from malformed nonempty JSON. Retry empty responses as fresh transport attempts; keep reply-side exhaustion as a presentation warning where the product contract allows it.
   - Every failed model call must persist: phase, parse reason, zero/nonzero completion-token flag (and count when known), finish reason, bounded raw preview, requested and resolved model, adapter/provider, and endpoint/base URL. Never persist credentials.

3. Make infra retry classification evidence-based.
   - Touch: `tests/live_agentic_harness/runner.py`, `tests/test_live_agentic_runner_persistence.py`.
   - Classify a parse failure as retryable infrastructure only when evidence says `completion_tokens == 0` and `parse_reason == empty` (or the equivalent typed fields). The phrase “could not be parsed” alone is insufficient. A nonzero-token parser/contract failure stays `product_fail` and does not receive the subprocess infra retry.

### Verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_executor_classify_only.py \
  tests/test_executor_contracts.py \
  tests/test_executor_flows.py \
  tests/test_agent_runtime_adapter.py \
  tests/test_headless_agent_artifacts.py \
  tests/test_live_agentic_runner_persistence.py \
  -k 'classification_failure_is_nullable_and_truthful or empty_worker_output_is_typed_empty_response or nonempty_invalid_json_remains_malformed_model_json or failed_model_call_artifact_has_complete_provenance or zero_token_empty_parse_is_retryable_infra or nonzero_token_parse_failure_is_product_fail or parse_phrase_without_evidence_is_product_fail'
```

Expected: the seven named focused tests pass.

```bash
.venv/bin/python -m pytest -q tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py
```

Expected: exit 0.

### Acceptance criteria

- A classify exception produces `classification_status=failed` and no fabricated decision, intent, or route.
- Empty output and malformed nonempty JSON are distinct typed failures at the worker, executor, artifact, and runner boundaries.
- 100% of deterministic failed-call fixtures contain the complete provenance field set; previews are bounded and secrets are absent.
- Zero-token/empty parse evidence becomes `retryable_infra` and reaches the existing retry; nonzero-token parse failures and phrase-only summaries remain `product_fail` with one attempt.
- Existing timeout/capacity retries and soft-search-429 non-retry controls remain green.

### Formal checkpoint B03

Review the public/internal contract change, evidence propagation end to end, retry classification truth table, redaction, and `git diff C02..C03`. Reject any default/sentinel decision that can again masquerade as a successful classification. Verdict: `PASS` or issue list; rework B03 until `PASS`.

---

## B04 — Lossless canonical graph boundary

**Executor:** GPT-5.6 Sol
**Plan item:** 3

### Tasks

1. **[HARD] Add a lossless rich-envelope decoder and make it the canonical ingest path.**
   - Touch as required: `vibecomfy/ingest/normalize.py`, `vibecomfy/comfy_nodes/agent/graph_normalization.py`, `tests/test_porting_normalize_ingest.py`, `tests/test_m1_contracts.py`.
   - For serialized Vibe envelopes, treat rich `nodes` and `edges` as structural authority. Decode them into the lossless `VibeWorkflow` editable representation, preserving node identity, stable UID, inputs/widgets/raw widget evidence, mode, metadata/UI evidence, and all edges. Treat `compiled_api` only as derived execution evidence; it must not decide which rich nodes survive.
   - Reuse the existing UI normalization semantics where possible and keep `compile('api')` a derived view.

2. Close every agent-edit normalization bypass.
   - Touch as required: `vibecomfy/comfy_nodes/agent/executor_durable.py`, `vibecomfy/comfy_nodes/agent/_frag_entrypoint.py`, `tests/test_agent_executor_durable.py`, `tests/test_m1_contracts.py`.
   - Normalize before allocation, persistence, hashing, and any executor-only durable path. Avoid a second divergent converter.

3. Guarantee stable UIDs on pinned opaque emission.
   - Touch: `vibecomfy/porting/emit/ui.py`, `tests/test_porting_ui_emitter.py`.
   - `_raw_ui_payload_for_pin` must emit `properties.vibecomfy_uid` from the canonical node UID even when the captured raw node omitted it.

### Verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_porting_normalize_ingest.py \
  tests/test_m1_contracts.py \
  tests/test_agent_executor_durable.py \
  tests/test_ui_emitter_widget_shape_verdict.py \
  tests/test_porting_ui_emitter.py \
  -k 'vibe_rich_ingest_preserves_90a1d5 or vibe_rich_ingest_is_idempotent or executor_durable_normalizes_before_allocation or pin_opaque_always_emits_vibecomfy_uid'
```

Expected: the four named regression tests pass.

```bash
.venv/bin/python -m pytest -q tests/test_porting_normalize_ingest.py tests/test_m1_contracts.py tests/test_agent_executor_durable.py tests/test_ui_emitter_widget_shape_verdict.py tests/test_porting_ui_emitter.py
```

Expected: exit 0.

### Acceptance criteria

- The `external_workflows/corpus/90a1d5ff9044902e.json` repro preserves exactly 15 rich nodes, 10 rich edges, all 15 distinct UIDs, and the mode distribution (9 mode-4, 6 mode-0); `TripoRefineNode` survives even though `compiled_api` contains only 2 nodes.
- Rich decode → canonical emit → re-ingest is idempotent under a projection containing node IDs/UIDs/classes/modes, edge endpoints, widgets, and relevant UI metadata.
- All agent-edit allocation paths receive canonical list-node UI graphs and use that same graph for persistence and hashes.
- Pinned opaque nodes emit zero missing/blank `properties.vibecomfy_uid` values, including the `cb5cd2`-style captured-raw case.
- Malformed or mixed rich entries fail closed; no partial graph is produced.

### Formal checkpoint B04

Review the decoder's information-preservation projection, canonical authority choice, bypass closure, pinned UID behavior, and `git diff C03..C04`. Run the exact 90a1d5 assertions rather than accepting node-count claims from implementation logs. Verdict: `PASS` or issue list; rework B04 until `PASS`.

---

## B05 — Semantic pinned-consumer guard

**Executor:** GPT-5.6 Sol
**Plan item:** 6

### Tasks

1. **[HARD] Replace pinned-output link cardinality checks with semantic terminal-consumer equivalence.**
   - Touch: `vibecomfy/porting/emit/ui.py`, `tests/test_porting_ui_emitter.py`.
   - For each pinned node output, compare the set of terminal consumers `{(target_uid, target_input)}` before and after lowering, traversing reroutes and broadcast Set/Get expansion. Link IDs and fan-out cardinality are representation details, not semantics.
   - Preserve fail-closed behavior when an endpoint cannot be resolved. Reject added, removed, or repointed semantic consumers even when link counts happen to match.

### Verification

```bash
.venv/bin/python -m pytest -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_porting_ui_emitter.py -k 'pinned_semantic_consumer'
```

Expected: four focused tests pass: broadcast expansion and reroute renumbering are accepted; same-cardinality repointing and dropped/added terminal consumers are rejected.

```bash
.venv/bin/python -m pytest -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_porting_ui_emitter.py tests/test_ui_emitter_parity.py
```

Expected: exit 0.

### Acceptance criteria

- The known Set/Get broadcast pattern that expands one raw link to four lowered links emits successfully when terminal consumers are unchanged.
- Link-ID changes and reroute insertion/removal do not cause false refusal when terminal `(target_uid, target_input)` sets are equal.
- Repointing, adding, or dropping a real consumer is refused with before/after semantic sets in diagnostics.
- Unresolved endpoints remain a typed refusal, not an assumed equivalence.

### Formal checkpoint B05

Review traversal termination, cycle handling, UID use, set equality, negative controls, and `git diff C04..C05`. Reject comparisons that still depend on raw link count or link ID. Verdict: `PASS` or issue list; rework B05 until `PASS`.

---

## B06 — Real-schema authority and apply-time combo validation

**Executor:** DeepSeek V4 Flash
**Plan item:** 7

### Tasks

1. Put real schemas before provisional evidence everywhere.
   - Touch: `vibecomfy/comfy_nodes/agent/_frag_research.py`, `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, and focused agent tests.
   - Change all applicable `CompositeSchemaProvider` construction so an existing live/real schema wins and provisional workflow/registry evidence fills only missing classes/fields. The `_frag_research.py:821` one-line swap already landed in **B02 (rider)**; B06 covers the remaining inconsistent sites at `_frag_research.py:874` and `edit_batch_repl.py:1115` plus widget-name derivation.
   - Derive widget/input names presented to the batch editor from the winning real schema.

2. Enforce semantic combo membership before candidate mutation.
   - Touch as required: `vibecomfy/porting/edit/apply_values.py`, `vibecomfy/porting/edit/apply_resolve_base.py`, `vibecomfy/porting/edit/apply_resolve_add.py`, `tests/test_porting_edit_apply_values.py`, and focused end-to-end edit tests.
   - Ensure both add-node values and set-field values use the same validation. Invalid semantic choices are blocking `value_not_in_enum` issues and never reach a candidate. Retain the deliberate warning behavior for missing local asset filenames; do not turn asset inventory into a semantic enum.

### Verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_porting_edit_apply_values.py \
  tests/test_porting_edit_apply.py \
  tests/test_comfy_nodes_agent_backend_spine.py \
  tests/test_comfy_nodes_agent_edit.py \
  -k 'real_schema_precedes_provisional or real_schema_widget_names_drive_batch_catalog or invalid_combo_rejected_before_candidate or asset_enum_accepts_missing_local_asset'
```

Expected: all selected tests pass; invalid add and set controls yield blocking `value_not_in_enum`, while the missing-asset control remains a warning.

```bash
.venv/bin/python -m pytest -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_edit.py
```

Expected: exit 0.

### Acceptance criteria

- A conflicting provisional schema cannot shadow a real schema at any hydration site.
- Batch-visible widget names and choices come from the winning real schema.
- Invalid semantic combo values fail before graph mutation for both add and set paths; no candidate artifact contains the invalid value.
- Valid/coercible choices still land, and missing local model/asset filenames retain their existing warning-only policy.

### Formal checkpoint B06

Review provider ordering at every construction site, the add/set apply paths, asset-vs-semantic controls, and `git diff C05..C06`. Verdict: `PASS` or issue list; rework B06 until `PASS`.

---

## B07 — Transactional batch execution and bounded semantic repair

**Executor:** GPT-5.6 Sol
**Plan item:** 5

### Tasks

1. **[HARD] Make one model-authored batch an atomic transaction.**
   - Touch as required: `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, `vibecomfy/porting/edit/_parse_execute.py`, and focused tests in `tests/test_comfy_nodes_agent_edit.py` / `tests/test_comfy_nodes_agent_backend_spine.py`.
   - Snapshot the working IR/UI/rendered Python and relevant ledger before executing a batch. Any uncaught batch exception must restore the exact snapshot before another model turn or terminal response. Persist a bounded traceback and exception fingerprint without leaking secrets.

2. **[HARD] Add one corrective semantic repair turn for eligible deterministic code exceptions.**
   - Feed the model the failed batch, typed exception/traceback, and unchanged authoritative state. Permit exactly one repair attempt for NameError-class deterministic batch exceptions.
   - Fingerprint failures and abort when the repair repeats the same fingerprint. Protocol/transport retries remain separate and do not multiply the semantic repair budget.
   - Persist repair eligibility, attempted/not-attempted, initial and repair fingerprints, rollback result, and repair outcome so the measurement gate can compute eligible/attempted/succeeded rates.

### Verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_porting_edit_session_harness.py \
  tests/test_porting_edit_corpus.py \
  tests/test_comfy_nodes_agent_edit.py \
  tests/test_comfy_nodes_agent_backend_spine.py \
  -k 'batch_transaction_rolls_back_on_exception or semantic_repair_succeeds_once or semantic_repair_repeated_fingerprint_aborts or ineligible_batch_exception_does_not_repair or semantic_repair_metrics_are_persisted'
```

Expected: five focused tests pass.

```bash
.venv/bin/python -m pytest -q tests/test_porting_edit_session_harness.py tests/test_porting_edit_corpus.py tests/test_comfy_nodes_agent_edit.py tests/test_comfy_nodes_agent_backend_spine.py
```

Expected: exit 0.

### Acceptance criteria

- A batch that mutates one statement and then raises leaves IR, UI, rendered Python, ledger, hashes, and candidate artifacts byte-/structure-equivalent to the pre-batch snapshot.
- Every eligible exception gets at most one semantic repair turn; a successful repair lands once from the restored state.
- A repeated fingerprint terminates without a third model call or partial mutation.
- Ineligible exceptions do not consume repair budget and preserve their typed failure.
- Persisted evidence is sufficient to compute eligible, attempted, success, rollback-integrity, and repeated-loop counts.

### Formal checkpoint B07

Review transaction scope, restoration completeness, fingerprint stability, retry-budget separation, metrics, and `git diff C06..C07`. Require negative tests for partial mutation and repeated failure. Verdict: `PASS` or issue list; rework B07 until `PASS`.

---

## B08 — Grounded-refusal adjudication and UI evidence coverage

**Executor:** GPT-5.6 Sol
**Plan item:** 8

### Tasks

1. **[HARD] Add an explicit refusal adjudication mode.**
   - Touch as required: `tests/live_agentic_harness/assessor.py`, `tests/live_agentic_harness/intent_judge.py`, `vibecomfy/intent/prompts/refusal_judge.prompt.md` (new, if a separate prompt is used), `tests/test_live_agentic_harness_guard_contract.py`, and focused judge tests.
   - For a no-edit refusal, adjudicate exactly: the stated blocker is supported by artifacts/schema, no viable representable edit was available, the response gives a specific next action, and it does not fabricate inability. Broaden `allow_safe_refusal` configuration without auto-passing the allowed outcome kind.
   - Return `pass`, `fail`, or `undetermined`; a judge outage/missing evidence is `undetermined` and never a pass.

2. Make UI evidence universal for adjudicated turns.
   - Touch: `vibecomfy/agent/artifacts.py`, `tests/test_headless_agent_artifacts.py`, plus any minimal durable-artifact plumbing required.
   - Always persist `original.ui.json` and `final.ui.json`; for an unchanged/refused turn, final is an explicit copy/projection of the authoritative original. Keep `candidate.ui.json` for edit-candidate compatibility where applicable.

### Verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_live_agentic_harness_guard_contract.py \
  tests/test_live_agentic_intent_judge_schema_context.py \
  tests/test_headless_agent_artifacts.py \
  -k 'grounded_refusal or refusal_judge_outage_is_undetermined or every_adjudicated_turn_has_original_and_final_ui'
```

Expected: grounded refusal passes, unsupported give-up and fabricated-inability controls fail, outage is undetermined/non-pass, and UI coverage tests pass.

```bash
.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py tests/test_live_agentic_intent_judge_schema_context.py tests/test_headless_agent_artifacts.py
```

Expected: exit 0.

### Acceptance criteria

- Merely configuring `allow_safe_refusal` cannot produce a pass; all four groundedness criteria must be positively supported.
- Grounded, ungrounded-give-up, fabricated-inability, and judge-outage fixtures produce `pass`, `fail`, `fail`, and `undetermined` respectively; only the first can satisfy the guard.
- Missing judge service or UI evidence is visible and counted as undetermined, never silently green.
- Deterministic fixtures have 100% `original.ui.json` + `final.ui.json` coverage for edit, refusal, clarify, and executor-only routes.
- Output exposes enough counts to calculate grounded-refusal precision/recall and judge availability in B11.

### Formal checkpoint B08

Review the four-part rubric, fail/undetermined distinction, allowed-refusal semantics, UI artifact authority, and `git diff C07..C08`. Reject any branch that turns outage or missing evidence into success. Verdict: `PASS` or issue list; rework B08 until `PASS`.

---

## B09 — Explicit transport selection and actual runtime provenance

**Executor:** DeepSeek V4 Flash
**Plan item:** 9

### Tasks

1. Add an explicit benchmark transport option while keeping product routing canonical.
   - Touch: `tests/live_agentic_harness/runner.py`, `tests/live_agentic_harness/adapter.py`, `tests/test_live_agentic_runner_persistence.py`, and adapter tests.
   - Add `--transport {openrouter,native}` and plumb it explicitly into each scenario process. Default product/harness behavior must not silently switch because a credential happens to exist. `openrouter` resolves to OpenRouter's canonical endpoint; `native` resolves to `https://api.deepseek.com/v1` and uses the native key/model normalization.

2. Record actual, stage-resolved transport/model provenance.
   - Touch as required: `vibecomfy/comfy_nodes/agent/runtime.py`, `vibecomfy/comfy_nodes/agent/worker.py`, `vibecomfy/agent/artifacts.py`, `tests/test_agent_runtime_adapter.py`, `tests/test_headless_agent_artifacts.py`.
   - For every model turn record stage, requested and resolved model, adapter, provider, normalized base URL/endpoint, and transport. The report must reflect the values actually sent to the adapter, not readiness labels or environment intent. Redact keys and query parameters.

### Verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_agent_runtime_adapter.py \
  tests/test_live_agentic_runner_persistence.py \
  tests/test_headless_agent_artifacts.py \
  -k 'explicit_transport or actual_runtime_provenance or transport_does_not_follow_ambient_credential or transport_provenance_redacts_secrets'
```

Expected: openrouter/native endpoint and model assertions pass; ambient-key and redaction controls pass.

```bash
.venv/bin/python -m tests.live_agentic_harness.runner --help | grep -F -- '--transport {openrouter,native}'
```

Expected: one matching help line and exit 0.

### Acceptance criteria

- The same scenario can be deliberately run on either transport without `VIBECOMFY_FORCE_MODEL` and without mutating the judge model.
- OpenRouter is the canonical default; native DeepSeek is an explicit benchmark lane.
- Runtime evidence identifies actual adapter/provider/base URL/model for classify, research, implement, and reply where those stages run.
- No API key, authorization header, or URL secret appears in artifacts.

### Formal checkpoint B09

Review CLI/subprocess plumbing, endpoint/model resolution, ambient-environment controls, provenance source, redaction, and `git diff C08..C09`. Verdict: `PASS` or issue list; rework B09 until `PASS`.

---

## B10 — All-Flash profile and prompt-drift reduction

**Executor:** GPT-5.6 Sol
**Plan item:** 10

### Tasks

1. Add a clean all-Flash experimental profile and a harness profile override.
   - Touch: `vibecomfy/executor/profile_data/all_flash.toml` (new), `vibecomfy/executor/profiles.py` only if discovery requires it, `tests/live_agentic_harness/runner.py`, `tests/live_agentic_harness/adapter.py`, `tests/test_executor_profiles.py`, and harness tests.
   - All four stages resolve to DeepSeek V4 Flash through normal profile selection. Add `--profile` as an explicit run-wide override. Do not use `VIBECOMFY_FORCE_MODEL`, because it contaminates judge/other model roles.
   - Keep `default.toml` pro-for-research/implement and flash-for-classify/reply.

2. **[HARD] Compress the +27% classify/reply prompt drift into auditable decision tables without semantic loss.**
   - Touch: `vibecomfy/executor/prompts.py`, focused prompt/route tests (principally `tests/test_executor_contracts.py` and existing prompt-routing tests).
   - Consolidate duplicated prose into explicit decision tables and shared constraints. Preserve all supported routes, ambiguity behavior, custom-node/adapt routing, attached-graph semantics, and strict JSON response contracts.
   - Add a byte-size regression ceiling based on the new prompt and behavioral route fixtures; do not approve a shorter prompt merely because it is shorter.

### Verification

```bash
.venv/bin/python -m pytest -q tests/test_executor_profiles.py tests/test_executor_contracts.py \
  -k 'all_flash or default_profile_keeps_pro_implement or prompt_size_ceiling or route_classification'
```

Expected: profile assertions, prompt ceiling, and all documented route-classification fixtures pass.

```bash
.venv/bin/python -m tests.live_agentic_harness.runner --help | grep -F -- '--profile'
```

Expected: one matching help line and exit 0.

```bash
.venv/bin/python -m pytest -q tests/test_executor_profiles.py tests/test_executor_contracts.py tests/test_comfy_nodes_agent_backend_spine.py -k 'prompt or profile or build_batch_messages'
```

Expected: exit 0.

### Acceptance criteria

- `all_flash` resolves Flash for classify/research/implement/reply; `default` still resolves Pro for research/implement and Flash for classify/reply.
- `--profile` reaches scenario requests without force-model environment mutation.
- The new prompt byte ceiling is at or below the pre-drift budget recorded by the test, and every existing documented route/contract fixture remains green.
- Prompt restructuring is table-driven and removes duplication; it does not delete a supported behavior to hit the size target.

### Formal checkpoint B10

Review profile isolation, absence of force-model contamination, prompt diff against behavioral fixtures, byte ceiling, and `git diff C09..C10`. The oracle must read the prompt change, not infer safety from test count alone. Verdict: `PASS` or issue list; rework B10 until `PASS`.

---

## B11 — Deterministic full gate and 2×2 transport/profile experiment

**Executor:** DeepSeek V4 Flash
**Plan items:** 9 and 10 measurement phase; validates items 1–11 together

### Tasks

1. Run the deterministic repository gate after all repairs.
   - Touch production/test code: none. Test-failure fixes must be routed back through the oracle to the owning earlier batch; do not patch forward inside B11.

2. Run the complete live 2×2 matrix after credentials/readiness are confirmed.
   - Matrix: `{openrouter,native} × {default,all_flash}` over all 100 scenarios in `tests/live_agentic_harness/scenarios/`, with the same runner concurrency/retry settings and unique tags.
   - Commands (the runner may exit nonzero for genuine scenario failures; a complete persisted summary is required):

```bash
.venv/bin/python -m tests.live_agentic_harness.runner --tag megado-openrouter-default --transport openrouter --profile default --max-workers 6 --infra-retries 1 --json
.venv/bin/python -m tests.live_agentic_harness.runner --tag megado-openrouter-all-flash --transport openrouter --profile all_flash --max-workers 6 --infra-retries 1 --json
.venv/bin/python -m tests.live_agentic_harness.runner --tag megado-native-default --transport native --profile default --max-workers 6 --infra-retries 1 --json
.venv/bin/python -m tests.live_agentic_harness.runner --tag megado-native-all-flash --transport native --profile all_flash --max-workers 6 --infra-retries 1 --json
```

3. Produce a durable comparison report.
   - Touch: `.oracle/measurements/transport-profile-matrix.md` (new) and, if useful, machine-readable `.oracle/measurements/transport-profile-matrix.json`.
   - Derive every number from the four persisted `run_summary.json` files and referenced attempt artifacts. Report per lane and per scenario class: first-attempt true pass, eventual-after-retry true pass, infra-adjusted pass, matcher-only failures, empty-response rate, nonzero parser-contract failures, refusal pass/fail/undetermined and judge availability, semantic-repair eligible/attempted/succeeded/repeated-fingerprint counts, resolved models, latency, tokens, estimated cost, and UI-artifact coverage.
   - Separate product failures from infra failures. Include scenario IDs behind every discrepancy and recommend whether to keep default or adopt all-Flash; do not change the product profile in this batch.

### Verification

```bash
make full-pytest
```

Expected: the non-GPU suite exits 0.

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
tags = (
    'megado-openrouter-default',
    'megado-openrouter-all-flash',
    'megado-native-default',
    'megado-native-all-flash',
)
for tag in tags:
    path = Path('out/agentic') / tag / 'run_summary.json'
    data = json.loads(path.read_text())
    assert data['complete'] is True, tag
    assert len(data['scenarios']) == 100, tag
print('4 complete lanes; 400 scenario results')
PY
```

Expected: exactly `4 complete lanes; 400 scenario results`.

```bash
test -s .oracle/measurements/transport-profile-matrix.md
```

Expected: exit 0.

### Acceptance criteria

- The full deterministic non-GPU suite passes.
- All four live lanes finish 100/100 scenarios; blocked or interrupted lanes are rerun/resumed before comparison.
- The nine matcher false-positive cases are no longer matcher failures, while genuine contradiction controls remain enforced.
- Failed-call evidence coverage is 100%; zero nonzero-token parser failures are labeled infra; zero uid-less `pin_opaque` emissions occur.
- The 90a1d5 preservation assertions and semantic broadcast/repointing controls remain green in the final suite.
- Repair, refusal, UI coverage, transport/model, latency, token, cost, and pass-rate metrics are all reported from evidence, with unknown values labeled unknown rather than inferred.
- The profile recommendation cites per-class quality and reliability tradeoffs; no profile flip occurs without a later oracle-approved revision.

### Formal checkpoint B11

Review the complete diff `git diff C10..C11` (expected to contain measurement artifacts only), full-suite output, four run summaries, sampled raw provenance, discrepancy scenario IDs, and the recommendation. Then review the cumulative implementation range `git diff C00..C11` for cross-batch coherence. Verdict: `PASS` or issue list; rework the owning batch and rerun affected B11 gates until `PASS`.

---

## Sequencing and dependency map

The chain is intentionally linear because each oracle checkpoint establishes the authority assumed by the next batch:

- B01 locks the already-landed recovery before further retry work.
- B02 makes the deterministic scorer trustworthy before new run measurements.
- B03 creates truthful typed evidence before canonicalization, repair, refusal, and experiment metrics consume it.
- B04 establishes the lossless canonical graph used by all later semantic comparisons and rollback snapshots.
- B05 depends on B04 UIDs and lossless topology.
- B06 depends on B04 canonical nodes and blocks deterministic bad candidates before repair is considered.
- B07 depends on B04/B06 so rollback restores the right representation and repair does not retry schema-invalid edits.
- B08 depends on B02/B03/B04 so refusal scoring has truthful language scoring, typed failures, and universal graph evidence.
- B09 makes transport choice and actual provenance explicit before experiments.
- B10 supplies the isolated profile and stable prompt under test.
- B11 is blocked by every prior checkpoint and changes no implementation.

| Plan item | Batch(es) | Delivery |
|---|---|---|
| 1 | B02 | Clause-aware message/artifact matcher |
| 2 | B03 | Evidence-gated zero-token infra classification |
| 3 | B04 | Lossless rich canonical decoder, bypass closure, pinned UID |
| 4 | B01 | Behavioral `dataclasses.replace` retry regression |
| 5 | B07 | Atomic batch rollback and one bounded semantic repair |
| 6 | B05 | Semantic terminal-consumer comparison |
| 7 | B06 | Real-schema precedence and combo validation |
| 8 | B08 | Grounded refusal and universal original/final UI evidence |
| 9 | B09, B11 | Explicit transport/provenance, then measured matrix |
| 10 | B10, B11 | All-Flash profile/prompt trim, then measured matrix |
| 11 | B03 | Truthful nullable classification and typed empty response |

The priority sequence is therefore preserved exactly as `4 → 1 → (2+11) → 3 → 6 → 7 → 5 → 8 → 9 → 10`, followed by the shared measurement gate.
