# Two-step pipeline mode — frozen tasklist (megado run)

Execution order: B01 → B02 → B03 → B04 → B05 → B06 → B07. Each batch: commit only its
scope, run its gate, then the final sense-check loop reviews cumulatively.

Model routing: `[XHARD]` tasks → **DeepSeek V4 Pro**; all other tasks → **DeepSeek V4 Flash**.
The final sense-check: one Codex (Sol) pass, then up to 3 rounds of DeepSeek Pro feedback
with changes implemented between rounds.

## B01 — Mode plumbing and dispatch toggle (Flash)

1. `vibecomfy/executor/contracts.py`: add `PipelineMode = Literal["full", "two_step"]`;
   typed `PipelineModeRequestError` / `PipelineModeConfigurationError`;
   `coerce_pipeline_mode()` / `resolve_pipeline_mode(request, environ=None)`;
   optional `ExecutorRequest.pipeline_mode` (validate direct construction + `from_payload()`;
   omit in `to_dict()` when unspecified).
2. `vibecomfy/agent/contracts.py`: optional `HeadlessAgentRequest.pipeline_mode`, carried
   through parsing + `to_executor_request()`.
3. `vibecomfy/executor/core.py`: resolve mode once (profiler/report); preserve classify +
   `answer_only`; branch immediately after the `answer_only` block (before research begins,
   ~core.py:1865/1912/1928): `if pipeline_mode == "two_step": return _run_two_step(...)`.
   Keep the full research→implement→reply block structurally untouched. `classify_only`:
   full emits existing skipped events; two-step emits only `execute: skipped`.
   **Do not resolve the optional `execute` profile before the `classify_only` return.**
4. Add `vibecomfy/executor/two_step.py` with typed entrypoint seam + test-injectable
   outcome boundary. Real execution lands B03–B04.
5. Fixture `tests/fixtures/payload_contracts/agent_executor_two_step_request.json`; do not
   rewrite the existing request fixture.
6. Tests: `tests/test_executor_pipeline_mode.py`; mode round-trips in
   `tests/test_executor_contracts.py`; branch/classify-only cases in
   `tests/test_executor_classify_only.py`.

Gate:
```bash
python -m pytest -q tests/test_executor_pipeline_mode.py tests/test_executor_contracts.py \
  tests/test_executor_classify_only.py tests/test_executor_flows.py
```
Prove: request > env > default "full"; invalid request = request error; invalid env =
configuration error; `classify_only` never invokes execute; `answer_only` rewrite runs
before two-step; full-mode phase calls/events unchanged.

## B02 — Route policy, tool gating, host budgets `[XHARD: tasks 5–6]`

1. In `two_step.py`: frozen types `TwoStepRoutePolicy`, `MessageBudget`, `SessionBudget`,
   `BudgetUsage`, `BudgetExceeded`.
2. `TWO_STEP_ROUTE_POLICIES` authoritative table (clarify/respond: no tools, 2k, 30s;
   inspect: `node_schema`, 4k, 2 calls, 60s; research: hivemind+registry+schema+templates+
   policy-enabled web, 8k, 180s; requires_custom_nodes: registry+schema, 4k, 90s; revise:
   schema+templates+suggestions+layout+Python, 8k, 180s; adapt: all ten + Python, 12k, 240s;
   reorganise: layout+Python, 6k, 120s). Assert `set(policies) == set(_ROUTE_BEHAVIORS)`
   (lazy import `_ROUTE_BEHAVIORS`; do not duplicate the authority).
3. **Exact per-tool caps frozen here** (correction #2): hivemind_search 3, hivemind_get 4,
   registry_lookup 2, node_schema 4, ready_template_list 2, ready_template_load 2,
   rank_edit_targets 2, suggest_seed_nodes 2, layout_hints 2, web_search 1 (denied unless
   explicitly enabled). Aggregate per-message tool calls: clarify/respond 0, inspect 2,
   research 8, requires_custom_nodes 3, revise 6, adapt 8, reorganise 2.
4. `[XHARD]` Cumulative budgets + provider-wide output-cap propagation: plumb remaining
   output cap through `comfy_nodes/agent/worker.py:254` (`AgentRequest`) and each provider
   adapter; runtime applies cap at `comfy_nodes/agent/runtime.py:573`; `None` preserves
   full-mode behavior. Per-message enforcement in B02; cumulative-session enforcement moves
   to B03's session authority (correction: B02 = immutable policy/types + per-message).
5. Tool catalogs via `tool_catalog_docs(phase=None, allowed_names=effective_route_tools)`
   (correction #1 — NOT `phase="research"`; node_schema/templates are implement-phase at
   tool_specs.py:760/771). Enforce route allowlist before handler invocation/budget
   consumption. `web_search` denied unless existing policy enables it (no production owner
   enables it today).
6. Budget checks before/after every model/tool call: per-message slice, session ceiling,
   aggregate output tokens, per-tool caps, apply/replacement counters, wall clock.
7. Tests: `tests/test_executor_two_step_policy.py`, `tests/test_executor_two_step_tools.py`,
   runtime-cap cases in `tests/test_agent_runtime_adapter.py`.

Gate:
```bash
python -m pytest -q tests/test_executor_two_step_policy.py tests/test_executor_two_step_tools.py \
  tests/test_executor_hivemind_tools.py tests/test_executor_lookup_tools.py \
  tests/test_executor_layout_hints.py tests/test_agent_runtime_adapter.py
```
Prove exact route coverage, exact catalogs, denial-before-dispatch, disabled web, every
budget family, aggregate-token exhaustion, cumulative-session exhaustion.

## B03 — Execute prompt + thread-continuous session `[XHARD: 1, 2, 3, 4]`

1. `[XHARD]` `vibecomfy/executor/two_step_session.py`: session identity keyed by
   normalized chat-window `session_id`; compact append-only execute transcript under the
   durable session dir; persist accepted Δ refs, lens facts, evidence ledger, replies,
   route history, cumulative budget usage, last retained workflow revision; serialize with
   the existing process-safe lock (`comfy_nodes/agent/session.py:385` — reuse, don't
   recreate); concurrent/stale detection before model work; in-process `EditSession` cache
   (15-min idle eviction, max 128, LRU; eviction only drops cache — durable transcript
   rehydratable); reconstruct only through named ingest door + canonical Δ replay.
2. `[XHARD]` First-message browser identity: `comfy_nodes/web/scoped_session_storage.js:111`
   gains get-or-create UUIDv4 before first POST (server does NOT mint IDs for two-step;
   correction #5); `agent_submit_flow.js:56` sends the bound ID. Headless/custom two-step
   without `session_id` → typed invalid-request error before classification. Never turn an
   expired/closed ID into a fresh session → typed `session_expired`.
3. `[XHARD]` `build_two_step_execute_messages()` in `executor/prompts.py`: every design
   section + explicit `STAGES AND AVAILABLE TOOLS` (RESEARCH tools → CHANGE tools + Python
   allowed? → SUBMIT: no tools, final JSON contract); unavailable tools denied by host;
   same-window continuity rule verbatim; non-edit routes: no change may be submitted;
   render only route-allowed catalog.
4. `[XHARD]` Bounded continuation loop: `run_execute_turn()` in `executor/agent_backend.py`;
   parse host actions (tool call / batch submission / final contract); re-inject compact
   accumulated transcript into every continuation — **flatten into the final user payload
   (runtime.py:557 `_split_messages()` keeps only first system + last user; correction #3)**;
   no provider-native memory; one logical execute-session identity across messages/routes;
   derive `research_attempt` from session ledger.
5. Prompt goldens: `tests/fixtures/executor/two_step_prompt_{clarify,respond,inspect,research,
   requires_custom_nodes,revise,adapt,reorganise}.txt`.
6. Tests: `tests/test_executor_two_step_prompt.py`, `tests/test_executor_two_step_continuity.py`
   (initial), browser identity in existing submit-flow suite.

Gate:
```bash
python -m pytest -q tests/test_executor_two_step_prompt.py \
  tests/test_executor_two_step_continuity.py tests/test_routes_session_sanitization.py \
  tests/test_agent_executor_durable.py
make browser-contracts   # correction #6: NOT `npm test -- --runInBand` (root has no package.json)
```
Inspect every prompt golden: visible sequence research → change → submit, exact tools,
no union-catalog leakage.

## B04 — Atomic edit, precedent projection, claim refs `[XHARD: all]`

1. `[XHARD]` Execute state machine in `two_step.py`: research/tool continuations may precede
   editing; exactly one complete Python batch accepted; one replacement only after
   rejection; after acceptance no further edits; second rejection → no candidate; parse/
   resolution/CAS/channel/bounds/done-gate failure → zero Δ.
2. **Reuse `EditSession.apply_batch()` as the parse/interpret/gate/commit authority**
   (`porting/edit/_parse_execute.py:22` — do NOT independently call parse/interpret/
   verify_apply again; correction #7).
3. `[XHARD]` CAS definition: request baseline + current session revision only (no
   model-supplied per-op old-values; correction #8 — do NOT extend grammar/op schemas).
   Typed stale-baseline diagnostics to the one replacement continuation.
4. `[XHARD]` `render_fact_pack()` in `porting/render.py`: stable fact IDs from canonical
   lens items (text = canonical rendered lines; topology = canonical tuples); IDs reference
   facts, no new graph representation; preserve Law 4 lens ceiling. **Separate from the
   canonical topology renderer** (correction #9) so complete-topology contract holds.
5. `[XHARD]` Precedent projection: `HivemindRecordView` (`executor/contracts.py:2358`) +
   `serve_hivemind_record()` (`hivemind_tools.py:345`, currently surface-only) expose
   immutable surface+topology, never raw workflow JSON; oversize bound: 64 KiB / 128 nodes /
   256 edges, rank exact→1-hop→2-hop, stable ties `(class_type, uid)`, induced edges only,
   always `omitted_node_count`/`omitted_edge_count`/`global_topology_complete=false`;
   apply same sanitization to ready-template observations (`lookup_tools.py:610`,
   `tool_specs.py:359`; correction #10).
6. Typed final contracts in `executor/contracts.py`: `TwoStepClaimRefs`,
   `TwoStepSelfAssessment`, `TwoStepFinal`, `TwoStepExecutionReport`.
7. `[XHARD]` `validate_two_step_final()`: delta_ids ⊆ accumulated accepted Δ ledger;
   lens_fact_ids ⊆ current reply-lens facts; evidence_ids ⊆ accumulated tool ledger;
   edit-success requires nonempty accepted Δ; turn-1 refs valid later only when present in
   session; forged/cross-session refs fail closed.
8. Map accepted work into existing `ImplementationResult`, durable candidate, `ExecutorResult`
   envelope; Δ IDs are metadata over canonical accepted-batch ops.
9. Tests: `tests/test_executor_two_step_contracts.py`, `tests/test_executor_two_step_atomic.py`,
   `tests/test_executor_two_step_precedents.py`, fact-ID cases in `tests/test_ir_laws.py`.

Gate:
```bash
python -m pytest -q tests/test_executor_two_step_contracts.py tests/test_executor_two_step_atomic.py \
  tests/test_executor_two_step_precedents.py tests/test_porting_edit_session.py \
  tests/test_porting_edit_session_harness.py tests/test_porting_edit_delta_contract.py \
  tests/test_ir_laws.py
```
Fault injections: stale baseline, unknown schema, socket/literal mismatch, invalid mixed
batch, done-gate failure, first-reject-then-valid-replacement, two rejections, research
timeout/empty, forged evidence ID, forged lens fact ID, cross-session delta ID, claimed
edit with zero accepted Δ.

## B05 — Profiles, report, profiler, events (Flash)

1. `executor/profiles.py`: split `DECLARED_STAGES` into `REQUIRED_STAGES` (classify,
   research, implement, reply) + `ALLOWED_STAGES` (+ execute) (correction #11,
   profiles.py:28/108/225); typed `MissingProfileStageError`; resolve `execute` only for
   two-step; never fall back to `implement`; `core._resolve_spec()` preserves the typed
   error (not generic ValueError).
2. Add explicit `execute` specs to `profile_data/{default,openai,openrouter,anthropic,
   opensource}.toml`. Packaged TOMLs are the sole runtime authority (correction: don't
   mirror Arnold package; fix stale Arnold comments).
3. `Report`: serialize resolved `pipeline_mode` for both modes (always, including "full");
   optional `execute` report for two-step (session identity, route, budget usage,
   tool/evidence IDs, accepted delta IDs, claim validation, replacement use,
   self-assessment); top-level executor envelope unchanged.
4. Profiler: `pipeline_mode` on request/result records; one `phase="execute"` span
   (continuation/tool/budget counters); full-mode spans preserved.
5. Events: `execute` start/working/done/error/skipped for two-step (use canonical
   `done/error`, NOT completed/failed — correction #12); frontend
   `comfy_nodes/web/executor_progress.js:29` adds execute phase; backend payload
   construction at core.py:1663; browser payload fixtures
   (`tests/browser/payload_contracts.test.mjs:1177`) updated; **full-mode websocket event
   payloads byte-identical**; fixture `websocket_executor_phase_execute.json`.
6. Tests: `tests/test_executor_profiles.py`, `tests/test_executor_two_step_reporting.py`,
   event cases in `tests/test_executor_flows.py`, response fixtures in
   `tests/test_agent_executor_response.py`.

Gate:
```bash
python -m pytest -q tests/test_executor_profiles.py tests/test_executor_two_step_reporting.py \
  tests/test_executor_flows.py tests/test_agent_executor_response.py \
  tests/test_agent_executor_durable.py
```
Fixture-level assertion: full-mode phase events byte-identical to pre-change JSON.

## B06 — Unit, continuity, IR-law, differential validation `[XHARD: 2, 4]`

1. Complete 5 thread-continuity cases in `tests/test_executor_two_step_continuity.py`:
   same session reuses identity (turn-1 Δ/observations visible); new window fresh (no
   prior refs); mid-thread route change keeps session; follow-up referencing missing turn-1
   Δ fails; budgets accumulate with per-message slices.
2. `[XHARD]` Concurrency/recovery: two simultaneous messages serialize or one stale-fails;
   server restart reconstructs via ingest + Δ replay; changed canvas vs retained revision
   fails CAS; idempotent replay does not duplicate tool calls/Δ.
3. Reuse all five IR laws against both modes (mode-parameterized executor adapter; keep
   lower-level law suite unchanged).
4. `[XHARD]` `tests/executor_mode_harness.py` + `tests/test_executor_two_step_differential.py`:
   inject same locked `ClassifyDecision` into both modes (patch `_run_classify()` or the
   test-only outcome boundary — no new production classifier API); cover named-field edits,
   rewires, add/remove, inspect, research, adapt, reorganise; compare `pi_edit(post)`
   (import the helper from `test_ir_laws.py:198` deliberately — correction #13, it's not a
   production API), accepted Δ replay, evidence validity, failure family, latency/tokens/
   cost; never prose equality; judge outcomes stay in B07 (deterministic stub only here —
   correction #13).
5. Full-path regressions: classify_only, answer_only, missing execute profile, route-policy
   coverage, tool denial, budget exhaustion, prompt sections, events/report compat.

Gate:
```bash
python -m pytest -q tests/test_executor_pipeline_mode.py tests/test_executor_two_step_policy.py \
  tests/test_executor_two_step_tools.py tests/test_executor_two_step_prompt.py \
  tests/test_executor_two_step_contracts.py tests/test_executor_two_step_atomic.py \
  tests/test_executor_two_step_precedents.py tests/test_executor_two_step_continuity.py \
  tests/test_executor_two_step_reporting.py tests/test_executor_two_step_differential.py \
  tests/test_executor_profiles.py tests/test_executor_classify_only.py \
  tests/test_executor_flows.py tests/test_ir_laws.py
PYTHONHASHSEED=0 python -m pytest -n 8 -q -p no:cacheprovider
```
No B06 pass if any atomicity/reference-integrity/continuity/full-mode-compat test is
quarantined or xfailed.

## B07 — 50-scenario lane + paired comparison `[XHARD: 1, 2+3 bootstrap]`

1. `[XHARD]` Extend headless/live path: `agent/contracts.py`, `tests/live_agentic_harness/
   adapter.py:135`, `runner.py` — add `--pipeline-mode {full,two_step}`; every two-step
   scenario gets a stable per-window `session_id`.
2. `[XHARD]` All-100 classification bootstrap + deterministic 50-case selection
   (correction #14 — route-stratification impossible before locks exist): classify all 100
   once → freeze `classification_lock.json` → select/freeze 50 with quota table:
   routes clarify 2 / respond 8 / inspect 8 / research 8 / requires-custom-nodes 2 /
   revise 12 / adapt 8 / reorganise 2; behavior 24 edit / 26 non-edit; ledger 25-in-57 /
   25-out; graph size 15/20/15; media 13 img / 14 vid / 12 multimodal / 5 audio / 5 3D /
   1 special. Route/edit/ledger quotas hard; media/size best-fit with documented stable
   hash fallback. `two_step_50_manifest.json` references all 100 descriptors (strict
   validation intact), 50 included / 50 excluded; pin descriptor+source hashes.
3. `[XHARD]` `tests/live_agentic_harness/compare_pipeline_modes.py`: classify each once,
   persist lock, run full+two_step with identical decision (test-only injection); separate
   durable session roots per mode; per-scenario + aggregate JSON/Markdown; compare
   pi_edit(post), Δ replay, judge outcome, evidence/claim correctness, failure family,
   rejection/replacement use, unsupported claims, self-check/judge disagreement, latency/
   tokens/cost, session-reuse rate; cache paired results so 50-lane ∩ 57-ledger overlap is
   not billed twice (correction #15).
4. `tests/test_live_agentic_two_step_comparison.py`: manifest count/hash, lock completeness
   + route equality, pair completeness, comparator behavior without model calls, honest
   infra-blocked handling.
5. Second comparator selection from `ledger_scenario_ids()` (`intent/_ledger.py:293`);
   ledger label `current` or `ir-everywhere-57-v3` (NOT `ir-everywhere-57` — invalid legacy
   label; correction #15).
6. Document commands + rollout order in `tests/live_agentic_harness/README.md`:
   respond/inspect → simple revise/reorganise → bounded research; adapt opt-in.

Gate:
```bash
python -m pytest -q tests/test_live_agentic_two_step_comparison.py \
  tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_runner_persistence.py
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json --validate-only
```
Paired live runs (post sense-check):
```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json --tag two-step-50 \
  --capture-classifications --max-workers 4 --json
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --ledger current --tag two-step-ledger-57 --capture-classifications --max-workers 4 --json
```
B07 passes when: both paired runs complete; every pair same locked classification; all Δ
replays + claim-ref checks valid; no full-mode compat regression; respond/inspect meet
non-inferiority gate; adapt reported but not auto-enabled.

## Final sense-check protocol (after B01–B07 implementation)

1. One Codex (Sol, read-only) sense-check of the full diff vs the design doc + this tasklist.
2. Then up to 3 rounds of **DeepSeek Pro** feedback; each round's issues are implemented
   (Flash for normal fixes, Pro for XHARD fixes) before the next round.
3. Then the paired 50-scenario + 57-ledger live runs (B07 gates) and final score report.

## Sense-check cadence (user ruling)

- Per batch: exactly ONE sense-check (the batch acceptance gate). No multi-round rework
  loop inside a batch — pass the gate or fix once and re-verify; do not run repeated
  oracle rounds per batch.
- The up-to-3-rounds feedback loop runs ONLY at the very end (final sense-check above).


## Scope deliberately cut

No new graph authority/edit DSL/declared-target format; no native browser settings panel
(request/env = toggle); no automatic fallback/escalate-to-full; no new tool registry; no
provider-native session memory (host-owned continuity); no model prose comparison; no
production rollout controller (fixed manifests + telemetry); no distributed lease/database
(multi-process only via shared durable session root).
