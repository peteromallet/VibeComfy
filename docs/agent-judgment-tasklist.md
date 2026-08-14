# Updated task list

### F01 — Freeze typed handoff, tool-result, evidence-pack contracts

- Batch: 0 — serial foundation.
- Files: new `vibecomfy/executor/stage_contracts.py`, `tool_contracts.py`, `evidence_pack.py`; new JSON schemas under `vibecomfy/executor/schemas/`; new `tests/test_executor_stage_contracts.py`.
- Change: define `StageRequest`, `StagePackage`, compact ledger, artifact references, structured diagnostics, `needs_input`, and tool statuses `ok|no_results|rate_limited|timeout|unavailable|invalid_request|refused`.
- Acceptance:
  - Round-trip serialization is deterministic and JSON-safe.
  - Missing GOAL/PRIORITY/PACKAGE or unresolved evidence IDs fails typed validation.
  - Changing PRIORITY alone cannot change deterministic validation/gate results.
  - Full source bodies live behind artifact/evidence IDs, never in ledger entries.
- Contract: establishes C0–C6.

### A01 — Hivemind `search/get` tools

- Batch: 1.
- Files: `vibecomfy/executor/hivemind_clients.py`; new `hivemind_tools.py`; new `tests/test_executor_hivemind_tools.py`.
- Change: implement `hivemind_search(query, filters, cursor, limit≤20)` and `hivemind_get(evidence_id)` over `external_resources`, Discord/unified feed, and curated distillations.
- Acceptance:
  - All declared filters, opaque cursor, sort, and limit work.
  - Every hit has a stable resolvable evidence ID.
  - Client performs transport/query translation only: no task classification, winner selection, enough-check, or stop decision.
  - 429/Retry-After, timeout, unavailable, and no-results return typed results; rate-limit circuit is tested.
- Contract: C0 → C1.

### A02 — Registry, node-schema, and ready-template tools

- Batch: 1.
- Files: new `vibecomfy/executor/lookup_tools.py`; new `tests/test_executor_lookup_tools.py`.
- Change: add `registry_lookup(node_class)`, `node_schema(node_class)`, `ready_template_list(...)`, and `ready_template_load(id)`.
- Acceptance:
  - Registry/schema lookups are exact and diagnostic; no inferred replacement class.
  - Registry batch budget is one per research stage.
  - Ready templates are labeled direct assets, not research evidence.
  - Template loading is path-confined and returns stable identity/hash.
- Contract: C1 and C2 support.

### A03 — Live runtime schema probe

- Batch: 1.
- Files: new `vibecomfy/runtime/schema_probe.py`; new `tests/test_runtime_schema_probe.py`.
- Change: implement `live_runtime_schema_probe()` with runtime identity, endpoint identity, timestamp, schema digest, readiness, class results, and typed failure status.
- Acceptance:
  - Stable digest for identical `object_info`; changed schema changes digest.
  - Timeout/unavailable/stale/mismatched-runtime states are explicit.
  - Receipt contains enough material for independent queue-gate verification.
  - No fabricated “strong tier” string is accepted as a receipt.
- Contract: C3 → C4.

### A04 — Optional target and seed suggestion tools

- Batch: 1.
- Files: new `vibecomfy/executor/edit_suggestion_tools.py`; new `tests/test_executor_edit_suggestion_tools.py`.
- Change: implement `rank_edit_targets(graph, intent)` and `suggest_seed_nodes(intent, constraints)`.
- Acceptance:
  - Results expose candidates and scoring factors, never “must edit” instructions.
  - Tools run only on explicit agent calls.
  - Existing-node, empty-graph, and no-candidate cases are typed.
  - No result is automatically injected into an authoring package.
- Contract: C0/C1 → C2. Covers B5/B14.

### A05 — Agent-invoked layout hints

- Batch: 1.
- Files: `vibecomfy/executor/layout_hints.py`, `tests/test_executor_layout_hints.py`.
- Change: replace classify-time use with `layout_hints(graph, operation, anchors?)`; retain geometry calculations as evidence only.
- Acceptance:
  - No classify/pipeline import invokes layout analysis automatically.
  - Tool returns anchors, signals, graph hash, and diagnostics.
  - Geometry fallback is labeled `last_resort` with reason and anchors.
- Contract: C1 → C2. Covers M2.

### A06 — Explicit last-resort web tool

- Batch: 1.
- Files: new `vibecomfy/executor/web_tools.py`; new `tests/test_executor_web_tools.py`.
- Change: expose `web_search` as an explicit agent tool, disabled by default.
- Acceptance:
  - Disabled calls return visible policy rejection, not silent omission.
  - No automatic Hivemind→web fallback exists.
  - Enabled calls use typed timeout/rate-limit results and record evidence IDs.
  - Tool trace records the agent’s stated unresolved question.
- Contract: C1.

### A07 — Assessment-first evidence rules

- Batch: 1.
- Files: new `tests/live_agentic_harness/research_assessment.py`; `tests/live_agentic_harness/assessor.py`; `tests/test_live_agentic_assessor_score_honesty.py`; `tests/live_agentic_harness/scenarios/hotshot-16-frames-agent-edit.json`.
- Change:
  - Remove `max_model_request_bytes` and `forbid_model_request_substrings`.
  - Make shared-effective-source changes valid by default.
  - Add question-before-search, query relevance, required-Hivemind invocation, citation resolution, no-local-search, and evidence-pack-capture assertions.
- Acceptance:
  - Prose length/content never gates.
  - Effects determine edit correctness, including intentional shared-source edits.
  - Missing/unresolvable citation, local-corpus agent search, or search-before-question fails.
  - Different implementation paths with equivalent effects receive equivalent scores.
- Contract: assesses C1–C5. Covers B12/B13.

### I01 — Integrate the agent tool surface and research budget

- Batch: 2.
- Files: `vibecomfy/porting/edit/_parse.py`, `_resolve.py`; `vibecomfy/comfy_nodes/agent/provider.py`, `_frag_batch_memory.py`, `_frag_state.py`, `edit.py`; `tests/test_porting_edit_resolve.py`; new `tests/test_agent_tool_surface.py`.
- Change: add the named tool calls to the batch protocol; persist the compact ledger across turns; enforce effort budgets of 3 searches, 6 fetches, 1 registry batch, and approximately 90 seconds.
- Acceptance:
  - Agent can interleave question → search → get → synthesize → enough/refine.
  - Budget exhaustion is typed and preserves gathered evidence.
  - Tool output enters subsequent turns only as ledger entries/evidence IDs.
  - Legacy `research()` remains temporarily available only for shadow comparison.
- Contract: C0 → C1 → C2/C5.

### S01 — Fail-closed queue normalization and field compatibility

- Batch: 2.
- Files: `vibecomfy/schema/validate.py`, `vibecomfy/runtime/session.py`; `tests/test_schema_validate.py`, `tests/test_runtime_session_validation.py`, `tests/test_intent_nodes.py`.
- Change:
  - Replace silent `sanitize_api_against_schema` mutation with a typed normalization proposal/diagnostic and explicit agent approval.
  - Replace `SCHEMA_VALIDATION_SKIP_CLASSES` with field-level compatibility policy.
- Acceptance:
  - Queue preparation never silently deletes inputs or coerces choices.
  - Unapproved normalization refuses queueing with node/field/before/after/reason.
  - Explicit approval applies exactly the proposed normalization and is evidenced.
  - No class-wide suppression symbol or behavior remains.
- Contract: C2 → C3 → C4. Covers B1/B8.

### S02 — Never drop an emitted edge

- Batch: 2.
- Files: `vibecomfy/porting/emit/ui.py`, `vibecomfy/porting/refuse.py`, `tests/test_porting_ui_emitter.py`, `tests/test_refuse.py`.
- Change: replace source/target socket warning-and-continue paths with `RefusedEmit`.
- Acceptance:
  - Every input edge is either emitted/remapped or causes refusal.
  - Refusal evidence includes both endpoints, requested sockets/slots, emitted socket arrays, and attempted remaps.
  - Valid remapping behavior remains unchanged.
  - Property test asserts `emitted_edges == input_edges` or `RefusedEmit`.
- Contract: C2 → C3. Covers B2.

### H01 — Agent-owned research in shadow/dual-evaluation mode

- Batch: 3.
- Files: new `vibecomfy/executor/agent_research_stage.py`; `vibecomfy/executor/core.py`; `vibecomfy/agent/artifacts.py`; new `tests/test_agent_research_shadow.py`.
- Change: run the C1 agent stage beside legacy research for research/adapt routes; capture both evidence packs, but retain legacy behavioral output until cutover.
- Acceptance:
  - Shadow result cannot alter route, graph, reply, or queue decision.
  - Agent trace proves explicit question and enough/refine judgment.
  - No full legacy result or workflow schema dump is injected into the model request.
  - Dual report compares evidence coverage, citation validity, and lifecycle assertions.
- Contract: C0 → C1 → C2/C5.

### H02 — Queue gate consumes probe receipts

- Batch: 3.
- Files: `vibecomfy/comfy_nodes/agent/gates.py`, `_frag_transform_stages.py`, `_frag_orchestration.py`, `_frag_response_contract.py`; new `tests/test_agent_runtime_probe_gate.py`.
- Change: pass and verify the A03 receipt at the queue gate.
- Acceptance:
  - Fresh matching successful probe satisfies runtime-schema evidence.
  - Missing, stale, mismatched, unavailable, or fabricated receipts block queueing with typed diagnostics.
  - A bare tier label no longer satisfies the gate.
- Contract: C3 → C4. Covers M1.

### H03 — Agent-authored, revisable, advisory execution plans

- Batch: 3.
- Files: `vibecomfy/comfy_nodes/agent/execution_plan.py`, `execution_plan_runtime.py`, `edit_batch_repl.py`, `_frag_batch_loop.py`; `tests/test_execution_plan_contracts.py`, `tests/test_execution_plan_runtime.py`, `tests/test_agent_execution_plan_hydration.py`.
- Change: separate advisory steps from agent-declared invariants; add authorship/revision provenance; remove plan-step `done()` refusal.
- Acceptance:
  - Missing advisory steps produce diagnostics but do not block `done()`.
  - Failed declared safety/invariant conditions still block.
  - Agent can revise the plan and persisted revision/history is auditable.
  - Provenance is `agent_authored`, `enforced=false`; no `m3_execute_enforcement`.
- Contract: C1/C2 → C3/C4. Covers B3.

### C01 — Switch routing, research, and headless ambiguity to agent judgment

- Batch: 4.
- Files: `vibecomfy/executor/core.py`, `prompts.py`, `agent_backend.py`; `vibecomfy/agent/contracts.py`, `service.py`; `vibecomfy/commands/agentic.py`; `tests/test_executor_flows.py`, `tests/test_agent_executor_routes.py`, `tests/test_release_guard_four_category.py`, `tests/test_headless_agent_service.py`.
- Change:
  - Promote shadow research to active.
  - Remove `_revise_research_uncertainty_triggers`, automatic prefetch, `_sanitize_source_preferences`, phrase-based delegated clarification, and forced headless route overrides.
  - Emit typed `needs_input`, or accept an agent-recorded bounded assumption.
- Acceptance:
  - No research occurs without an agent tool call.
  - Unsupported source requests produce visible policy diagnostics.
  - Headless clarification is driven by typed agent output, never phrase lists or `prior_route`.
  - Research-only returns C5 memo; edit routes receive only C1 ledger.
  - No deterministic execution-plan builder is invoked.
- Contract: C0 → C1/C5/C6. Covers B7/B9/B10 and B3 cutover.

### C02 — Remove deterministic batch judgment and hardcoded recipes

- Batch: 4.
- Files: `vibecomfy/comfy_nodes/agent/_frag_batch_memory.py`, `_frag_revision.py`, `_frag_research.py`, `edit_batch_repl.py`, `provider.py`, `edit.py`; `tests/test_comfy_nodes_agent_edit.py`, `tests/test_agent_edit_parameter_tweak_fallback.py`.
- Change:
  - Delete keyword task classifiers, premature-clarify rejection, “Stop searching” injection, hardcoded frame-extractor/ControlNet recipes, automatic target/seed injection, and four-turn research cap.
  - Retain A04/A05 only as optional tools.
- Acceptance:
  - Banned helpers/copy strings are absent.
  - Justified `clarify()` is accepted and evidenced.
  - Neither target nor seed suggestions appear unless called.
  - Layout fallback is explicit and recorded.
  - Only safety/typed validation feedback can preempt an agent action.
- Contract: C0/C1 → C2/C6. Covers B4/B5/B6/B11/B14/M2.

### D01 — Delete legacy research engine

- Batch: 5.
- Files removed: `vibecomfy/executor/research.py`, `research_sources.py`, `execution_plan_builder.py`; retire/replace `tests/test_executor_research.py`, `test_executor_research_sources.py`, `test_research_deadline.py`, legacy portions of `test_executor_hivemind_messages.py`.
- Change: remove local-corpus tier, deterministic relevance/ranking/selection/adaptation machinery, web fallback chain, and deterministic plan builder.
- Acceptance:
  - No agent/executor import reaches `vibecomfy.search` or the 38-row corpus.
  - Transport/schema/safety primitives still needed have already moved to tool or validation modules.
  - Import graph and package tests pass without deleted modules.
- Contract: enforces C1/C2 agent ownership.

### D02 — Remove `ResearchResult` and legacy core contracts

- Batch: 5.
- Files: `vibecomfy/executor/contracts.py`, `core.py`, `__init__.py`; `tests/test_executor_contracts.py`, legacy sections of `tests/test_executor_flows.py`.
- Change: replace `ResearchResult`, precedent packets, deterministic adaptation plans, and `report.research` with typed stage/evidence packages.
- Acceptance:
  - `rg` finds no `ResearchResult`, `run_research_phase`, `_should_prefetch_research`, `_delegated_clarification_plan`, or source sanitizer.
  - Public serialization carries compact package/artifact references.
  - Backward-incompatible payloads fail explicitly rather than being silently rewritten.
- Contract: C0–C6 canonicalization.

### D03 — Remove giant prompt/payload injection path

- Batch: 5.
- Files: `vibecomfy/comfy_nodes/agent/_frag_entrypoint.py`, `_frag_state.py`, `_frag_research.py`, `_frag_batch_memory.py`, `edit_batch_repl.py`, `provider.py`, `edit.py`; `tests/fixtures/agent_edit/cleanup_surface_manifest.json`; relevant portions of `tests/test_comfy_nodes_agent_edit.py`, `tests/test_porting_edit_resolve.py`.
- Change: remove `executor_research_*`, `research_context_packet`, full workflow schemas, precedent/adaptation dumps, and old prompt compactors.
- Acceptance:
  - Model requests contain ledger entries and resolvable IDs only.
  - Full evidence remains available in the evidence-pack artifact.
  - No 22,978-line/full-result injection path survives.
  - No prompt-size/prose-content gate is introduced as replacement.
- Contract: enforces compact C1 → C2 handoff.

### V01 — Eight end-to-end evidence scenarios

- Batch: 6.
- Files: new `tests/structural_harness/actors_agent_judgment.py`; `tests/structural_harness/adapter.py`; eight new scenario YAMLs and briefs under `tests/structural_harness/{scenarios,briefs}/`.
- Scenarios:
  1. revise without forced research;
  2. empty-graph authoring;
  3. research-only decision memo;
  4. headless ambiguity/`needs_input`;
  5. schema drift and approved normalization;
  6. Hivemind rate limiting;
  7. invalid emitted socket;
  8. queue refusal/valid runtime probe.
- Acceptance:
  - Each scenario freezes request, stage packages, evidence pack, tool trace, diagnostics, and final effect.
  - Rubrics score effects and evidence, not exact node recipes or prose.
  - Research scenarios enforce question/relevance/Hivemind/citation/no-local-search assertions.
  - Fake/no-GPU structural run passes; designated live research subset passes.
- Contract: validates C0–C6 end to end.

### V02 — Release proof and contract documentation

- Batch: 7 — serial closeout.
- Files: new `docs/agent-judgment-pipeline.md`; update `docs/testing/headless-agentic-harnesses.md`, `vibecomfy/comfy_nodes/agent/OWNERSHIP.md`.
- Acceptance:
  - Focused unit suites, all eight structural scenarios, package/import tests, and selected live scenarios pass.
  - Static banned-symbol/string audit passes.
  - Evidence-pack citation resolver reports zero dangling IDs.
  - Documentation names GOAL/PRIORITY/PACKAGE ownership and deletion of legacy paths.
- Contract: final C0–C6 proof.

# Parallelism map

Every task in a wave forks from the same post-previous-wave SHA. No two concurrent tasks own the same file.

| Task | Concurrent with | Ownership partition |
|---|---|---|
| F01 | none | New contract/schema files |
| A01 | A02–A07 | Hivemind client/tool |
| A02 | A01, A03–A07 | Lookup/direct-asset tool |
| A03 | A01–A02, A04–A07 | Runtime probe |
| A04 | A01–A03, A05–A07 | Edit suggestions |
| A05 | A01–A04, A06–A07 | Layout tool |
| A06 | A01–A05, A07 | Web tool |
| A07 | A01–A06 | Live assessor |
| I01 | S01, S02 | Batch parser/resolver/tool memory |
| S01 | I01, S02 | Schema validation/runtime preparation |
| S02 | I01, S01 | UI emitter/refusal |
| H01 | H02, H03 | Executor research orchestration |
| H02 | H01, H03 | Queue gates/stage gate adapters |
| H03 | H01, H02 | Execution-plan runtime/batch completion |
| C01 | C02 | Executor routing/headless service |
| C02 | C01 | Batch judgment/prompt behavior |
| D01 | D02, D03 | Legacy research files |
| D02 | D01, D03 | Executor core/contracts |
| D03 | D01, D02 | Agent prompt/payload state |
| V01 | none | Cross-cutting scenario integration |
| V02 | none | Final verification/docs |

With four execution slots, Batch 1 runs as two physical subwaves, but A01–A07 are pairwise merge-safe.

Dependency graph:

```text
F01
 ├─ A01 A02 A03 A04 A05 A06
 └─ A07 assessment
        ↓
I01 ───────────────┐
S01 S02            │
        ↓           │
H01 ← tools + assessment
H02 ← A03 + assessment
H03 ← assessment
        ↓
C01 C02
        ↓
D01 D02 D03
        ↓
V01
        ↓
V02
```

Serial barriers:

1. F01 must land before any tool work.
2. A07 must land before S01/S02 or later behavioral flips.
3. All A-tools plus I01 must land before H01 shadow mode.
4. Shadow evidence must pass before C01 cutover.
5. Cutover must pass before deletion.
6. V02 is the final serial release gate.

# Merge sequence

| Order | Merge action | Conflict/risk | Review |
|---|---|---|---|
| 1 | Merge F01 | High contract risk; low textual conflict | Contract reviewer |
| 2 | Merge A07 first, then A01–A06 in any order | Low textual; medium API consistency | Independent assessment reviewer for A07; tool/API reviewer for A01–A06 |
| 3 | Run foundation/tool/assessment suites | Detect envelope drift before behavior changes | Contract reviewer |
| 4 | Merge I01 | Medium integration risk | Agent-tool reviewer |
| 5 | Merge S01, then S02 | High safety semantics; files disjoint | Safety reviewer; independent negative-test review |
| 6 | Merge H01, H02, H03 in any order | High semantic interaction despite no textual conflicts | Agent-judgment reviewer for H01/H03; runtime safety reviewer for H02 |
| 7 | Run shadow comparison and queue/emitter/schema suites | Required cutover gate | Independent assessment reviewer |
| 8 | Merge C01, then C02 | Very high behavioral risk | Same independent reviewer reads both combined diff; operator approves cutover |
| 9 | Run focused and structural suites before deletion | Must prove active paths no longer import legacy code | Release reviewer |
| 10 | Merge D02 and D03, then D01 last | Medium import/dead-code risk; deleting D01 last keeps intermediate tree runnable | Dependency/import reviewer |
| 11 | Merge V01 | High rubric/evidence correctness risk | Sisypy/evidence reviewer |
| 12 | Merge V02 after full proof | Release risk | Operator plus independent release reviewer |

Coverage: B1/B8→S01; B2→S02; B3→H03/C01; B4/B5/B6/B11/B14→A04/I01/C02; B7/B9/B10→C01; B12/B13→A07; M1→A03/H02; M2→A05/I01/C02; full research A-track→F01, A01/A02/A06/A07, I01, H01, C01, D01–D03, V01.
tokens used
213,228
Base verified: clean `main` at `105f6bd5`. No files edited.

## Stage contracts

All agent stages use:

```text
StageRequest = {
  GOAL,                    # user outcome; authoritative
  PRIORITY,                # advisory brief; never a gate or rewrite rule
  PACKAGE                  # compact output from previous stage
}

StagePackage = {
  version,
  stage,
  status,
  decisions[],
  conclusions[],
  evidence_ledger[],       # Decision / Conclusion / Evidence IDs / Uncertainty
  diagnostics[],
  needs_input?,
  artifact_refs[],
  tool_trace[]
}
```

Handoffs:

- `C0 Triage`: request/graph → questions, route judgment, research need, budget.
- `C1 Research`: triage package → compact evidence ledger.
- `C2 Author`: ledger/graph → candidate delta, advisory plan, declared invariants.
- `C3 Validate`: candidate → typed validation/emission diagnostics.
- `C4 Queue`: validated candidate → runtime-probe receipt and queue decision.
- `C5 Memo`: research ledger → bounded decision memo with resolvable citations.
- `C6 Needs-input`: justified typed request, or a recorded bounded assumption.

`PRIORITY` may influence agent judgment but cannot alter `GOAL`, satisfy a gate, or mutate a package deterministically.

# Updated task list

### F01 — Freeze typed handoff, tool-result, evidence-pack contracts

- Batch: 0 — serial foundation.
- Files: new `vibecomfy/executor/stage_contracts.py`, `tool_contracts.py`, `evidence_pack.py`; new JSON schemas under `vibecomfy/executor/schemas/`; new `tests/test_executor_stage_contracts.py`.
- Change: define `StageRequest`, `StagePackage`, compact ledger, artifact references, structured diagnostics, `needs_input`, and tool statuses `ok|no_results|rate_limited|timeout|unavailable|invalid_request|refused`.
- Acceptance:
  - Round-trip serialization is deterministic and JSON-safe.
  - Missing GOAL/PRIORITY/PACKAGE or unresolved evidence IDs fails typed validation.
  - Changing PRIORITY alone cannot change deterministic validation/gate results.
  - Full source bodies live behind artifact/evidence IDs, never in ledger entries.
- Contract: establishes C0–C6.

### A01 — Hivemind `search/get` tools

- Batch: 1.
- Files: `vibecomfy/executor/hivemind_clients.py`; new `hivemind_tools.py`; new `tests/test_executor_hivemind_tools.py`.
- Change: implement `hivemind_search(query, filters, cursor, limit≤20)` and `hivemind_get(evidence_id)` over `external_resources`, Discord/unified feed, and curated distillations.
- Acceptance:
  - All declared filters, opaque cursor, sort, and limit work.
  - Every hit has a stable resolvable evidence ID.
  - Client performs transport/query translation only: no task classification, winner selection, enough-check, or stop decision.
  - 429/Retry-After, timeout, unavailable, and no-results return typed results; rate-limit circuit is tested.
- Contract: C0 → C1.

### A02 — Registry, node-schema, and ready-template tools

- Batch: 1.
- Files: new `vibecomfy/executor/lookup_tools.py`; new `tests/test_executor_lookup_tools.py`.
- Change: add `registry_lookup(node_class)`, `node_schema(node_class)`, `ready_template_list(...)`, and `ready_template_load(id)`.
- Acceptance:
  - Registry/schema lookups are exact and diagnostic; no inferred replacement class.
  - Registry batch budget is one per research stage.
  - Ready templates are labeled direct assets, not research evidence.
  - Template loading is path-confined and returns stable identity/hash.
- Contract: C1 and C2 support.

### A03 — Live runtime schema probe

- Batch: 1.
- Files: new `vibecomfy/runtime/schema_probe.py`; new `tests/test_runtime_schema_probe.py`.
- Change: implement `live_runtime_schema_probe()` with runtime identity, endpoint identity, timestamp, schema digest, readiness, class results, and typed failure status.
- Acceptance:
  - Stable digest for identical `object_info`; changed schema changes digest.
  - Timeout/unavailable/stale/mismatched-runtime states are explicit.
  - Receipt contains enough material for independent queue-gate verification.
  - No fabricated “strong tier” string is accepted as a receipt.
- Contract: C3 → C4.

### A04 — Optional target and seed suggestion tools

- Batch: 1.
- Files: new `vibecomfy/executor/edit_suggestion_tools.py`; new `tests/test_executor_edit_suggestion_tools.py`.
- Change: implement `rank_edit_targets(graph, intent)` and `suggest_seed_nodes(intent, constraints)`.
- Acceptance:
  - Results expose candidates and scoring factors, never “must edit” instructions.
  - Tools run only on explicit agent calls.
  - Existing-node, empty-graph, and no-candidate cases are typed.
  - No result is automatically injected into an authoring package.
- Contract: C0/C1 → C2. Covers B5/B14.

### A05 — Agent-invoked layout hints

- Batch: 1.
- Files: `vibecomfy/executor/layout_hints.py`, `tests/test_executor_layout_hints.py`.
- Change: replace classify-time use with `layout_hints(graph, operation, anchors?)`; retain geometry calculations as evidence only.
- Acceptance:
  - No classify/pipeline import invokes layout analysis automatically.
  - Tool returns anchors, signals, graph hash, and diagnostics.
  - Geometry fallback is labeled `last_resort` with reason and anchors.
- Contract: C1 → C2. Covers M2.

### A06 — Explicit last-resort web tool

- Batch: 1.
- Files: new `vibecomfy/executor/web_tools.py`; new `tests/test_executor_web_tools.py`.
- Change: expose `web_search` as an explicit agent tool, disabled by default.
- Acceptance:
  - Disabled calls return visible policy rejection, not silent omission.
  - No automatic Hivemind→web fallback exists.
  - Enabled calls use typed timeout/rate-limit results and record evidence IDs.
  - Tool trace records the agent’s stated unresolved question.
- Contract: C1.

### A07 — Assessment-first evidence rules

- Batch: 1.
- Files: new `tests/live_agentic_harness/research_assessment.py`; `tests/live_agentic_harness/assessor.py`; `tests/test_live_agentic_assessor_score_honesty.py`; `tests/live_agentic_harness/scenarios/hotshot-16-frames-agent-edit.json`.
- Change:
  - Remove `max_model_request_bytes` and `forbid_model_request_substrings`.
  - Make shared-effective-source changes valid by default.
  - Add question-before-search, query relevance, required-Hivemind invocation, citation resolution, no-local-search, and evidence-pack-capture assertions.
- Acceptance:
  - Prose length/content never gates.
  - Effects determine edit correctness, including intentional shared-source edits.
  - Missing/unresolvable citation, local-corpus agent search, or search-before-question fails.
  - Different implementation paths with equivalent effects receive equivalent scores.
- Contract: assesses C1–C5. Covers B12/B13.

### I01 — Integrate the agent tool surface and research budget

- Batch: 2.
- Files: `vibecomfy/porting/edit/_parse.py`, `_resolve.py`; `vibecomfy/comfy_nodes/agent/provider.py`, `_frag_batch_memory.py`, `_frag_state.py`, `edit.py`; `tests/test_porting_edit_resolve.py`; new `tests/test_agent_tool_surface.py`.
- Change: add the named tool calls to the batch protocol; persist the compact ledger across turns; enforce effort budgets of 3 searches, 6 fetches, 1 registry batch, and approximately 90 seconds.
- Acceptance:
  - Agent can interleave question → search → get → synthesize → enough/refine.
  - Budget exhaustion is typed and preserves gathered evidence.
  - Tool output enters subsequent turns only as ledger entries/evidence IDs.
  - Legacy `research()` remains temporarily available only for shadow comparison.
- Contract: C0 → C1 → C2/C5.

### S01 — Fail-closed queue normalization and field compatibility

- Batch: 2.
- Files: `vibecomfy/schema/validate.py`, `vibecomfy/runtime/session.py`; `tests/test_schema_validate.py`, `tests/test_runtime_session_validation.py`, `tests/test_intent_nodes.py`.
- Change:
  - Replace silent `sanitize_api_against_schema` mutation with a typed normalization proposal/diagnostic and explicit agent approval.
  - Replace `SCHEMA_VALIDATION_SKIP_CLASSES` with field-level compatibility policy.
- Acceptance:
  - Queue preparation never silently deletes inputs or coerces choices.
  - Unapproved normalization refuses queueing with node/field/before/after/reason.
  - Explicit approval applies exactly the proposed normalization and is evidenced.
  - No class-wide suppression symbol or behavior remains.
- Contract: C2 → C3 → C4. Covers B1/B8.

### S02 — Never drop an emitted edge

- Batch: 2.
- Files: `vibecomfy/porting/emit/ui.py`, `vibecomfy/porting/refuse.py`, `tests/test_porting_ui_emitter.py`, `tests/test_refuse.py`.
- Change: replace source/target socket warning-and-continue paths with `RefusedEmit`.
- Acceptance:
  - Every input edge is either emitted/remapped or causes refusal.
  - Refusal evidence includes both endpoints, requested sockets/slots, emitted socket arrays, and attempted remaps.
  - Valid remapping behavior remains unchanged.
  - Property test asserts `emitted_edges == input_edges` or `RefusedEmit`.
- Contract: C2 → C3. Covers B2.

### H01 — Agent-owned research in shadow/dual-evaluation mode

- Batch: 3.
- Files: new `vibecomfy/executor/agent_research_stage.py`; `vibecomfy/executor/core.py`; `vibecomfy/agent/artifacts.py`; new `tests/test_agent_research_shadow.py`.
- Change: run the C1 agent stage beside legacy research for research/adapt routes; capture both evidence packs, but retain legacy behavioral output until cutover.
- Acceptance:
  - Shadow result cannot alter route, graph, reply, or queue decision.
  - Agent trace proves explicit question and enough/refine judgment.
  - No full legacy result or workflow schema dump is injected into the model request.
  - Dual report compares evidence coverage, citation validity, and lifecycle assertions.
- Contract: C0 → C1 → C2/C5.

### H02 — Queue gate consumes probe receipts

- Batch: 3.
- Files: `vibecomfy/comfy_nodes/agent/gates.py`, `_frag_transform_stages.py`, `_frag_orchestration.py`, `_frag_response_contract.py`; new `tests/test_agent_runtime_probe_gate.py`.
- Change: pass and verify the A03 receipt at the queue gate.
- Acceptance:
  - Fresh matching successful probe satisfies runtime-schema evidence.
  - Missing, stale, mismatched, unavailable, or fabricated receipts block queueing with typed diagnostics.
  - A bare tier label no longer satisfies the gate.
- Contract: C3 → C4. Covers M1.

### H03 — Agent-authored, revisable, advisory execution plans

- Batch: 3.
- Files: `vibecomfy/comfy_nodes/agent/execution_plan.py`, `execution_plan_runtime.py`, `edit_batch_repl.py`, `_frag_batch_loop.py`; `tests/test_execution_plan_contracts.py`, `tests/test_execution_plan_runtime.py`, `tests/test_agent_execution_plan_hydration.py`.
- Change: separate advisory steps from agent-declared invariants; add authorship/revision provenance; remove plan-step `done()` refusal.
- Acceptance:
  - Missing advisory steps produce diagnostics but do not block `done()`.
  - Failed declared safety/invariant conditions still block.
  - Agent can revise the plan and persisted revision/history is auditable.
  - Provenance is `agent_authored`, `enforced=false`; no `m3_execute_enforcement`.
- Contract: C1/C2 → C3/C4. Covers B3.

### C01 — Switch routing, research, and headless ambiguity to agent judgment

- Batch: 4.
- Files: `vibecomfy/executor/core.py`, `prompts.py`, `agent_backend.py`; `vibecomfy/agent/contracts.py`, `service.py`; `vibecomfy/commands/agentic.py`; `tests/test_executor_flows.py`, `tests/test_agent_executor_routes.py`, `tests/test_release_guard_four_category.py`, `tests/test_headless_agent_service.py`.
- Change:
  - Promote shadow research to active.
  - Remove `_revise_research_uncertainty_triggers`, automatic prefetch, `_sanitize_source_preferences`, phrase-based delegated clarification, and forced headless route overrides.
  - Emit typed `needs_input`, or accept an agent-recorded bounded assumption.
- Acceptance:
  - No research occurs without an agent tool call.
  - Unsupported source requests produce visible policy diagnostics.
  - Headless clarification is driven by typed agent output, never phrase lists or `prior_route`.
  - Research-only returns C5 memo; edit routes receive only C1 ledger.
  - No deterministic execution-plan builder is invoked.
- Contract: C0 → C1/C5/C6. Covers B7/B9/B10 and B3 cutover.

### C02 — Remove deterministic batch judgment and hardcoded recipes

- Batch: 4.
- Files: `vibecomfy/comfy_nodes/agent/_frag_batch_memory.py`, `_frag_revision.py`, `_frag_research.py`, `edit_batch_repl.py`, `provider.py`, `edit.py`; `tests/test_comfy_nodes_agent_edit.py`, `tests/test_agent_edit_parameter_tweak_fallback.py`.
- Change:
  - Delete keyword task classifiers, premature-clarify rejection, “Stop searching” injection, hardcoded frame-extractor/ControlNet recipes, automatic target/seed injection, and four-turn research cap.
  - Retain A04/A05 only as optional tools.
- Acceptance:
  - Banned helpers/copy strings are absent.
  - Justified `clarify()` is accepted and evidenced.
  - Neither target nor seed suggestions appear unless called.
  - Layout fallback is explicit and recorded.
  - Only safety/typed validation feedback can preempt an agent action.
- Contract: C0/C1 → C2/C6. Covers B4/B5/B6/B11/B14/M2.

### D01 — Delete legacy research engine

- Batch: 5.
- Files removed: `vibecomfy/executor/research.py`, `research_sources.py`, `execution_plan_builder.py`; retire/replace `tests/test_executor_research.py`, `test_executor_research_sources.py`, `test_research_deadline.py`, legacy portions of `test_executor_hivemind_messages.py`.
- Change: remove local-corpus tier, deterministic relevance/ranking/selection/adaptation machinery, web fallback chain, and deterministic plan builder.
- Acceptance:
  - No agent/executor import reaches `vibecomfy.search` or the 38-row corpus.
  - Transport/schema/safety primitives still needed have already moved to tool or validation modules.
  - Import graph and package tests pass without deleted modules.
- Contract: enforces C1/C2 agent ownership.

### D02 — Remove `ResearchResult` and legacy core contracts

- Batch: 5.
- Files: `vibecomfy/executor/contracts.py`, `core.py`, `__init__.py`; `tests/test_executor_contracts.py`, legacy sections of `tests/test_executor_flows.py`.
- Change: replace `ResearchResult`, precedent packets, deterministic adaptation plans, and `report.research` with typed stage/evidence packages.
- Acceptance:
  - `rg` finds no `ResearchResult`, `run_research_phase`, `_should_prefetch_research`, `_delegated_clarification_plan`, or source sanitizer.
  - Public serialization carries compact package/artifact references.
  - Backward-incompatible payloads fail explicitly rather than being silently rewritten.
- Contract: C0–C6 canonicalization.

### D03 — Remove giant prompt/payload injection path

- Batch: 5.
- Files: `vibecomfy/comfy_nodes/agent/_frag_entrypoint.py`, `_frag_state.py`, `_frag_research.py`, `_frag_batch_memory.py`, `edit_batch_repl.py`, `provider.py`, `edit.py`; `tests/fixtures/agent_edit/cleanup_surface_manifest.json`; relevant portions of `tests/test_comfy_nodes_agent_edit.py`, `tests/test_porting_edit_resolve.py`.
- Change: remove `executor_research_*`, `research_context_packet`, full workflow schemas, precedent/adaptation dumps, and old prompt compactors.
- Acceptance:
  - Model requests contain ledger entries and resolvable IDs only.
  - Full evidence remains available in the evidence-pack artifact.
  - No 22,978-line/full-result injection path survives.
  - No prompt-size/prose-content gate is introduced as replacement.
- Contract: enforces compact C1 → C2 handoff.

### V01 — Eight end-to-end evidence scenarios

- Batch: 6.
- Files: new `tests/structural_harness/actors_agent_judgment.py`; `tests/structural_harness/adapter.py`; eight new scenario YAMLs and briefs under `tests/structural_harness/{scenarios,briefs}/`.
- Scenarios:
  1. revise without forced research;
  2. empty-graph authoring;
  3. research-only decision memo;
  4. headless ambiguity/`needs_input`;
  5. schema drift and approved normalization;
  6. Hivemind rate limiting;
  7. invalid emitted socket;
  8. queue refusal/valid runtime probe.
- Acceptance:
  - Each scenario freezes request, stage packages, evidence pack, tool trace, diagnostics, and final effect.
  - Rubrics score effects and evidence, not exact node recipes or prose.
  - Research scenarios enforce question/relevance/Hivemind/citation/no-local-search assertions.
  - Fake/no-GPU structural run passes; designated live research subset passes.
- Contract: validates C0–C6 end to end.

### V02 — Release proof and contract documentation

- Batch: 7 — serial closeout.
- Files: new `docs/agent-judgment-pipeline.md`; update `docs/testing/headless-agentic-harnesses.md`, `vibecomfy/comfy_nodes/agent/OWNERSHIP.md`.
- Acceptance:
  - Focused unit suites, all eight structural scenarios, package/import tests, and selected live scenarios pass.
  - Static banned-symbol/string audit passes.
  - Evidence-pack citation resolver reports zero dangling IDs.
  - Documentation names GOAL/PRIORITY/PACKAGE ownership and deletion of legacy paths.
- Contract: final C0–C6 proof.

# Parallelism map

Every task in a wave forks from the same post-previous-wave SHA. No two concurrent tasks own the same file.

| Task | Concurrent with | Ownership partition |
|---|---|---|
| F01 | none | New contract/schema files |
| A01 | A02–A07 | Hivemind client/tool |
| A02 | A01, A03–A07 | Lookup/direct-asset tool |
| A03 | A01–A02, A04–A07 | Runtime probe |
| A04 | A01–A03, A05–A07 | Edit suggestions |
| A05 | A01–A04, A06–A07 | Layout tool |
| A06 | A01–A05, A07 | Web tool |
| A07 | A01–A06 | Live assessor |
| I01 | S01, S02 | Batch parser/resolver/tool memory |
| S01 | I01, S02 | Schema validation/runtime preparation |
| S02 | I01, S01 | UI emitter/refusal |
| H01 | H02, H03 | Executor research orchestration |
| H02 | H01, H03 | Queue gates/stage gate adapters |
| H03 | H01, H02 | Execution-plan runtime/batch completion |
| C01 | C02 | Executor routing/headless service |
| C02 | C01 | Batch judgment/prompt behavior |
| D01 | D02, D03 | Legacy research files |
| D02 | D01, D03 | Executor core/contracts |
| D03 | D01, D02 | Agent prompt/payload state |
| V01 | none | Cross-cutting scenario integration |
| V02 | none | Final verification/docs |

With four execution slots, Batch 1 runs as two physical subwaves, but A01–A07 are pairwise merge-safe.

Dependency graph:

```text
F01
 ├─ A01 A02 A03 A04 A05 A06
 └─ A07 assessment
        ↓
I01 ───────────────┐
S01 S02            │
        ↓           │
H01 ← tools + assessment
H02 ← A03 + assessment
H03 ← assessment
        ↓
C01 C02
        ↓
D01 D02 D03
        ↓
V01
        ↓
V02
```

Serial barriers:

1. F01 must land before any tool work.
2. A07 must land before S01/S02 or later behavioral flips.
3. All A-tools plus I01 must land before H01 shadow mode.
4. Shadow evidence must pass before C01 cutover.
5. Cutover must pass before deletion.
6. V02 is the final serial release gate.

# Merge sequence

| Order | Merge action | Conflict/risk | Review |
|---|---|---|---|
| 1 | Merge F01 | High contract risk; low textual conflict | Contract reviewer |
| 2 | Merge A07 first, then A01–A06 in any order | Low textual; medium API consistency | Independent assessment reviewer for A07; tool/API reviewer for A01–A06 |
| 3 | Run foundation/tool/assessment suites | Detect envelope drift before behavior changes | Contract reviewer |
| 4 | Merge I01 | Medium integration risk | Agent-tool reviewer |
| 5 | Merge S01, then S02 | High safety semantics; files disjoint | Safety reviewer; independent negative-test review |
| 6 | Merge H01, H02, H03 in any order | High semantic interaction despite no textual conflicts | Agent-judgment reviewer for H01/H03; runtime safety reviewer for H02 |
| 7 | Run shadow comparison and queue/emitter/schema suites | Required cutover gate | Independent assessment reviewer |
| 8 | Merge C01, then C02 | Very high behavioral risk | Same independent reviewer reads both combined diff; operator approves cutover |
| 9 | Run focused and structural suites before deletion | Must prove active paths no longer import legacy code | Release reviewer |
| 10 | Merge D02 and D03, then D01 last | Medium import/dead-code risk; deleting D01 last keeps intermediate tree runnable | Dependency/import reviewer |
| 11 | Merge V01 | High rubric/evidence correctness risk | Sisypy/evidence reviewer |
| 12 | Merge V02 after full proof | Release risk | Operator plus independent release reviewer |

Coverage: B1/B8→S01; B2→S02; B3→H03/C01; B4/B5/B6/B11/B14→A04/I01/C02; B7/B9/B10→C01; B12/B13→A07; M1→A03/H02; M2→A05/I01/C02; full research A-track→F01, A01/A02/A06/A07, I01, H01, C01, D01–D03, V01.

# Status
- F01: in progress (contract foundation)
- Wave A (A01-A07): pending
- Wave B (I01, S01, S02): pending
- Wave H (H01, H02, H03): pending
- Wave C (C01, C02): pending
- Wave D (D01-D03): pending
- V01, V02: pending
- Execution tracker: 7 waves, forks from same SHA per wave, disjoint file ownership, merges per the table above.
