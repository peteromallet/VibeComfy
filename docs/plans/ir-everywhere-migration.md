# IR-everywhere migration plan

## Target and baseline

The target is one authoritative `VibeWorkflow`: UI/API/envelope JSON enters once through a named importer, every stage receives the IR or `render(wf, lens)`, edits are immutable interpretations of Python batches, and UI JSON is emitted only at the exit. At `5e41420e`, batch REPL is already the product protocol, but `EditSession` owns `original_ui`/`working_ui` and rebuilds IR for every render. Also, contrary to the historical gap description, `apply_batch()` currently reaches `guard_full_ui` through `apply_delta`; the migration must preserve that fidelity at the exit boundary.

Define checkpoint **S** as:

```text
pytest -q tests/test_comfy_nodes_agent_edit.py tests/test_agent_edit_parameter_tweak_fallback.py tests/test_porting_edit_apply.py tests/test_executor_flows.py tests/test_executor_stage_contracts.py tests/test_agent_tool_surface.py
```

Every checkpoint below requires S with no new failures; the existing `test_schema_precedence_across_all_seven_construction_sites` `_GAP` failure may remain until independently fixed. Failure estimates are overlapping likely eliminations from the recovery run's 57 failures, not additive forecasts.

## Phase 0 — Freeze the laws and inventory

- **Goal:** executable contracts before behavior changes.
- **Files:** new `tests/test_ir_laws.py`, `tests/test_ir_boundary_kpi.py`; extend `tests/test_porting_normalize_ingest.py`, `tests/test_b02_rich_preservation.py`, `tests/test_porting_ui_emitter.py`, `tests/property/test_emitter_fuzz.py`.
- **Change:** encode the door, Python-isomorphism, diff/interpret, lens-subset, deterministic-name, and raw-JSON-boundary laws; inventory top-level/node/link fields lost today.
- **Verification/checkpoint:** law tests initially mark only documented gaps; S matches baseline. Failure reach: 0/57 directly.
- **Risk/rollback:** false equality can bless loss; compare canonical dataclasses plus byte-equal untouched UI nodes. Tests-only rollback.
- **Elegance:** establishes Laws 1–5 and the KPI as merge gates.

## Phase 1 — Lossless door and retained IR

- **Goal:** `emit_ui_json(from_ui(J)) ≡ J`, and ingest retains that IR.
- **Files:** `vibecomfy/workflow.py`, `vibecomfy/ingest/normalize.py`, `vibecomfy/ingest/snapshot.py`, `vibecomfy/porting/emit/ui.py`, `vibecomfy/comfy_nodes/agent/{graph_normalization.py,_frag_entrypoint.py,_frag_ingest.py,_frag_state.py}`.
- **Change:** add first-class wire-retention for `extra`, `definitions`, link ids/order/counters and untouched node payloads; make `AgentEditState.workflow` authoritative at allocation. UI compatibility accessors are derived, never a second writer.
- **Verification/checkpoint:** UI/API/envelope corpus round-trips, including 90a1d5 and subgraphs; untouched node dictionaries are byte-equal; targeted door tests + S. Reach: 4–8/57 format/identity failures.
- **Risk/rollback:** current `prior_store`/`prior_ui_payload` hide missing IR fields. Keep a versioned read-only compatibility adapter for one phase.
- **Elegance:** Law 1 door half; raw JSON becomes a wire concern.

## Phase 2 — Purge positional and mutable identity leaks

- **Goal:** stable names/types independent of stage or turn.
- **Files:** `vibecomfy/workflow.py`, `vibecomfy/porting/emit/{naming.py,emit_prepare.py,emit_kwargs.py,emit_agent_edit.py,ui.py}`, `vibecomfy/porting/edit/{_ir_utils.py,_resolve.py,projection.py}`, `vibecomfy/security/provenance.py`.
- **Change:** introduce `NodeMode` in IR (LiteGraph int only on emit); replace `output_0` with typed synthetic names such as `LATENT_0` carrying `schema_status`; derive variable names purely from `(class_type, uid-order)` and remove session locks. Add provenance ordering and `join`; edits become copy-on-write while public IR immutability remains deferred.
- **Verification/checkpoint:** golden naming across stages/turns, mode and synthetic-port door round-trips, provenance lattice laws; targeted emitter/session tests + S. Reach: 4–8/57 positional/identity failures.
- **Risk/rollback:** old batches mention positional aliases. Accept them read-only at ingest/parse for one release, never emit them.
- **Elegance:** Law 5; immutable-session and provenance secondaries.

## Phase 3 — One generated surface and IR interpreter

- **Goal:** `interpret(empty, emit_agent_edit_python(wf)) == wf`; batch REPL remains product but becomes IR-native.
- **Files:** new `vibecomfy/porting/edit/{grammar.py,editable_surface.py,interpret.py}`; change `session.py`, `_parse.py`, `_parse_execute.py`, `_render.py`, `_resolve.py`, `_gates.py`, `_describe.py`, `vibecomfy/porting/emit/signatures.py`, `vibecomfy/comfy_nodes/agent/{provider.py,edit_batch_repl.py,_frag_batch_loop.py,_frag_batch_memory.py}` and `docs/architecture/python_authoring_edit_surface.md`.
- **Change:** one machine-readable grammar generates AST admission, prompt help, typed node library, and doc table. `EditableSurface` separates literal fields from sockets and models unknown schemas explicitly; unknown names and literal-to-socket writes fail during resolution. `interpret(pre,batch)` returns a new IR; remaining guard is CAS plus value bounds, while commit runs the independent door-fidelity guard. Document bounded `for` as macro expansion.
- **Verification/checkpoint:** full-view replay, corpus samples, every grammar form, illegal-state negatives, multi-turn replay, guard attribution, fuzz; `tests/test_porting_edit_session*.py` + S. Reach: 18–28/57 edit-target/schema/wiring failures.
- **Risk/rollback:** exact isomorphism may require a compact interpreted `wire(...)` preamble for opaque UI state. Prove feasibility on messy `_ui`; never weaken equality silently. Roll back the phase, not via dual writes.
- **Elegance:** Laws 1 and 4; immutable session history `(wf_i, Δ_i)`.

## Phase 4 — Diff is a batch value

- **Goal:** `post=interpret(pre,Δ)` and `interpret(pre,diff(pre,post))=post`.
- **Files:** `vibecomfy/porting/edit/{ops.py,_diff.py,_session_types.py,session.py}`, `vibecomfy/comfy_nodes/agent/{_frag_batch_reports.py,_frag_humanize.py,_frag_response_contract.py}`, `vibecomfy/executor/contracts.py`, `tests/live_agentic_harness/intent_judge.py`.
- **Change:** canonicalize accepted edits as the same valid batch language; compose per-turn batches, derive replay/undo/audit from them, and delete the separate prose/JSON diff-report category. Reply receives accepted Δ; edit judge grades Δ directly.
- **Verification/checkpoint:** inverse, minimality, determinism, zero-diff, cumulative replay/undo and judge fixtures; delta/session tests + S. Reach: 6–12/57 contract/report/judge failures.
- **Risk/rollback:** downstream response consumers may expect `delta_ops_envelope`; retain a derived compatibility serializer only.
- **Elegance:** Law 2.

## Phase 5 — One renderer, composable lenses

- **Goal:** no stage-specific graph projections or evidence asymmetry.
- **Files:** new `vibecomfy/porting/render.py`; change `vibecomfy/porting/emit/emit_agent_edit.py`, `vibecomfy/executor/{core.py,prompts.py,graph_inspection.py}`, `vibecomfy/comfy_nodes/agent/provider.py`, `tests/live_agentic_harness/intent_judge.py`.
- **Change:** implement `render(wf, lens)` for composable `census`, `surface`, `topology`, `diff(Δ)`. Classify gets census/reference map; reply gets surface+diff+topology; judges get only subsets of the reply lens. Retire `_build_text_summary` as an authority.
- **Verification/checkpoint:** lens goldens, no truncation-induced topology loss, enforced `judge_lens ⊆ reply_lens`, 3c978e regression; graph-inspection/executor/judge tests + S. Reach: 12–20/57 semantic-answer/intent-judge failures.
- **Risk/rollback:** larger reply prompts. Lenses remain bounded and composable; compatibility wrappers may call the renderer.
- **Elegance:** Law 3 and same-facts-for-model/judge.

## Phase 6 — IR-shaped research and attempt semantics

- **Goal:** research consumes/returns Python views; semantic replies never depend on research success.
- **Files:** `vibecomfy/executor/{hivemind_tools.py,agent_research_stage.py,contracts.py,stage_contracts.py,core.py,prompts.py}`.
- **Change:** named-import workflow records and serve `render(wf,surface)` while retaining raw source only in evidence artifacts. Add closed `ResearchAttempt={never,empty,thin,grounded}` derived from the ledger; remove `finish_premature`. Semantic routes always reply from graph+knowledge; adapt implements on `thin|grounded`, skips on `never|empty|non-OK`.
- **Verification/checkpoint:** workflow-record round-trips plus never/empty/thin/grounded, timeout and off-topic cases; research-shadow/Hivemind/executor tests + S. Reach: 8–14/57 research-gate/unsupported-conclusion failures.
- **Risk/rollback:** malformed corpus bodies. Return typed non-workflow evidence without pretending normalization succeeded; keep additive old trace fields temporarily.
- **Elegance:** one representation, computed attempt type, semantic non-gating.

## Phase 7 — Query and model-JSON repair

- **Goal:** remove avoidable 57014 and one-shot parse losses.
- **Files:** `vibecomfy/executor/{hivemind_clients.py,hivemind_tools.py,agent_backend.py,prompts.py}`; new `vibecomfy/executor/model_json.py`; `tests/live_agentic_harness/intent_judge.py`.
- **Change:** preserve phrase-only message scope, cap external-resource patterns, and retry 57014 once with fewer columns/patterns and a smaller limit, never the identical URL. Use a shared balanced `JSONDecoder.raw_decode` extractor; classify and each judge get one bounded format-repair turn with original/repair evidence.
- **Verification/checkpoint:** exact URL/query tests, simulated 57014 cost reduction, fenced/trailing/truncated/multi-object JSON and retry-budget tests; runtime-adapter/Hivemind/judge tests + S. Reach: 5–13/57 query-timeout/parse failures.
- **Risk/rollback:** repair can change semantics. Prompt it to preserve fields and repair format only; fail closed after one retry. Independently revertible.
- **Elegance:** deterministic evidence handling; no retry loops.

## Phase 8 — Remove dual paths and enforce zero raw-JSON graph logic

- **Goal:** only named doors touch graph JSON.
- **Files:** delete obsolete paths from `vibecomfy/comfy_nodes/agent/{_frag_orchestration.py,_frag_transform_stages.py,graph_normalization.py}` and `vibecomfy/porting/edit/{ledger.py,apply.py,apply_core.py,apply_gate.py,apply_links.py,apply_mutate.py,apply_resolve.py,normalize.py,projection.py}` after caller count reaches zero; update `_frag_entrypoint.py`, `_frag_session_bundle.py`, `edit.py`; add `scripts/check_ir_boundary.py` and `tests/test_ir_boundary_kpi.py`.
- **Change:** remove `delta|full` dev protocols and raw-UI mutation engine; move any still-required placement logic under `porting/layout`. CI permits graph JSON only in `ingest/normalize.py`, `porting/emit/ui.py`, and transport/artifact adapters; KPI outside that allow-list is zero lines.
- **Verification/checkpoint:** `rg`/AST caller audit, KPI zero, two consecutive full-suite runs, then the 57-case live rerun with failure-family deltas. Reach: 0 direct; recurrence prevention.
- **Risk/rollback:** dev-gate blast radius or lost `guard_full_ui`. Delete only after Phases 3–7 shadow cleanly; the new exit guard must pass all old guard fixtures before removal.
- **Elegance:** completes Laws 1–5 and eliminates representational duality.

## Execution order

Land `0 → 1`; then `2` and the query half of `7` may land together. Land `3 → 4 → 5`; the parse half of `7` can accompany `5`. Land `6` after the renderer contract. Run the full suite and a small live shadow after 5 and 6. Phase 8 is deletion-only and waits for two suite-green checkpoints plus the live shadow.

## Principal risks

| Risk | Severity | Mitigation |
|---|---|---|
| Isomorphism over messy `_ui` is infeasible without noisy Python | Critical | Inventory first; use one compact interpreted wire preamble or redesign IR equality explicitly. Never claim a weaker law. |
| IR migration drops current product `guard_full_ui` behavior | Critical | Port its untouched-byte fixtures to the exit guard before changing session authority. |
| Two writers drift during migration | Critical | Compatibility code is read/serialize-only; IR interpreter is the sole mutation authority. |
| Generated surface rejects valid custom nodes | High | Explicit `schema_status`, instance-hydrated fields, corpus property cases, typed refusal. |
| Dev-protocol removal breaks recovery tooling | High | Caller audit, shadow artifacts, two green checkpoints, then delete in one revertible phase. |
| Judge changes conceal product defects | High | Judge sees a strict reply-lens subset and grades independently replayable Δ. |
