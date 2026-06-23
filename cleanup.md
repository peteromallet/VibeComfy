# VibeComfy Cleanup Map

Last updated: 2026-06-23

This is the working cleanup backlog for the messaging / preview / apply architecture pass. It consolidates findings from the original Codex review, the 30-lens DeepSeek swarm, the redundancy-focused DeepSeek swarm, and follow-up cruft waves. The goal is to identify places where multiple systems are doing one job, internal-only state can leak into user UI, or old compatibility paths are making the code hard to reason about.

## Executive Direction

The main cleanup target is not a cosmetic refactor. The current system has too many overlapping representations of the same user-visible concept: chat turns, response details, execution/audit events, candidate/apply state, field changes, and stage/progress status. That overlap is what allowed internal batch text like `Turn 1 / working` to appear as if it were a user-facing stage.

The desired architecture is:

- `TranscriptMessage`: durable user-visible chat transcript only.
- `ResponseDetail`: safe expandable details for a user-visible response.
- `ExecutionEvent`: internal progress/debug/audit events, never rendered by default chat UI.
- `AuditArtifact`: downloadable evidence and diagnostics, reachable through explicit debug affordances.
- `ApplyCandidate`: one object describing the previewed/applied graph change and eligibility.
- `StageSnapshot`: one user-facing progress/stage model derived from execution state.

## Highest Priority Cleanup

### 1. Split Durable Chat From Internal Execution Events

**Problem:** `panel.state.turns`, `message.canonical_activity.details`, `batch_turns`, websocket `vibecomfy.agent_edit.turn`, and durable chat/session payloads all carry turn-like objects. Some are user transcript, some are internal execution state, and some are audit/debug detail.

**Why it matters:** Any renderer or rehydrate path that treats all turn-shaped objects as displayable can leak internal text. This is the direct class of bug behind the intermittent `Turn 1 / working` UI.

**Cleanup target:** create explicit state buckets:

- `panel.state.chatMessages`
- `panel.state.turnDetailSnapshots`
- `panel.state.executionEvents`
- `panel.state.durableTurnStatuses`
- `panel.state.auditRefs`

Only `chatMessages` and sanitized `turnDetailSnapshots` should be inputs to normal chat rendering.

**Likely files:** `vibecomfy/comfy_nodes/web/panel_thread.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `vibecomfy/comfy_nodes/agent/session_store.py`, `vibecomfy/comfy_nodes/agent/edit.py`.

### 2. Collapse Duplicate Progress / Stage Models

**Problem:** the UI appears to have several progress concepts that can diverge: executor progress, canonical activity phase progress, agent activity feed rows, durable pending rows, composer working/status labels, and batch turn statuses.

**Why it matters:** The user wants the stage display preserved. Today it is preserved by multiple mechanisms rather than one reliable projection, which is why stage text appears “only sometimes.”

**Cleanup target:** define `StageSnapshot` as the only user-facing progress model. All internal execution phases should map into it through one normalization function. Chat rows should render stage from `StageSnapshot`, not from raw execution records or batch turns.

**Likely files:** `vibecomfy/comfy_nodes/web/panel_thread.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, browser tests under `tests/browser`.

**Concrete sub-cleanups:**

- remove `executor_pending` if it remains an alias of `pending_response`
- avoid storing the same phase quad in `panel.state.executorProgress`, `message.progress`, and `message.canonical_activity.phase_progress`
- make `StageSnapshot` the UI-facing projection even if `canonical_activity.phase_progress` remains the internal source

### 3. Remove Raw Execution / Audit Details From Default Render Inputs

**Problem:** several payloads preserve rich detail under names like `details`, `canonical_activity`, `debug`, `audit`, `session_json`, or `batch_turns`. Those fields are useful, but their shape is too close to display data.

**Why it matters:** filtering leaks at the renderer is fragile. The boundary should exist before data reaches the renderer.

**Cleanup target:** use explicit safe projections for UI rendering. Keep raw details only behind debug/audit controls and downloads.

**Likely files:** `vibecomfy/comfy_nodes/web/panel_thread.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `vibecomfy/comfy_nodes/agent/audit.py`, `vibecomfy/commands/_agent_edit_debug.py`.

**Related failure-message boundary:** raw diagnostics should never be appended to user-facing messages. Reports found `classify_failure()` and provider readiness paths that can mix raw exception text into public strings. User-visible error text should be fixed/sanitized; raw explanation belongs under debug/diagnostics only.

**Related path-leak boundary:** UI-facing session/chat JSON should not include host filesystem paths. Strip `session_path`, `session_path_resolved`, `detail_json_path`, `detail_json_path_resolved`, `response_path`, `turn_path`, and raw artifact paths from renderable responses. Use `session_id` + `turn_id` and relative bundle file paths instead.

### 4. Unify Candidate / Apply Eligibility State

**Problem:** candidate state and apply permission seem to be represented by overlapping names such as `latestCandidate`, `changeDetails`, `fieldChanges`, `applyAllowed`, `canvasApplyAllowed`, `applyEligibility`, inline controls, and composer controls.

**Why it matters:** preview/apply bugs are likely when one control reads a stale eligibility path while another reads a newer path.

**Cleanup target:** create one `ApplyCandidate` projection with:

- candidate id / request id
- graph diff summary
- safe field changes
- eligibility status and reason
- apply lifecycle status

All apply buttons and preview rows should consume that object.

**Likely files:** `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `vibecomfy/comfy_nodes/web/panel_thread.js`, `vibecomfy/comfy_nodes/agent/edit.py`, `vibecomfy/comfy_nodes/agent/contracts.py`.

**Concrete sub-cleanups:**

- delete `canvasApplyAllowed` as live state; reports found it is always set equal to `applyAllowed`
- keep `canvasApplyAllowed` only as a backward-compatible serialized alias if older snapshots need it
- keep only `apply_eligibility` as the response key; remove the duplicate `eligibility` alias after frontend migration
- stop flattening `apply_allowed`, `canvas_apply_allowed`, and `queue_allowed` beside the eligibility object unless behind a legacy compatibility flag
- fold durable eligibility checks into `_candidateActionAllowed()`
- make `applyEligibility()` pure; move warning side effects to callers
- remove dead reads of `latestResponse` if confirmed still unwritten

### 5. Consolidate Field Change Sources

**Problem:** field changes appear to be available through multiple paths: outcome changes, report changes, compatibility response fields, batch turn field changes, preview labels, and local UI summaries.

**Why it matters:** the preview can disagree with the applied change, and the UI has to decide which representation wins.

**Cleanup target:** define one canonical field-change schema server-side, then derive preview text and detail rows from that schema only.

**Likely files:** `vibecomfy/comfy_nodes/agent/edit.py`, `vibecomfy/comfy_nodes/agent/contracts.py`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `tests/browser/roundtrip_smoke.test.mjs`.

**Concrete sub-cleanups:**

- decide whether `outcome.changes` is the only wire shape and mark `field_changes` as derived/legacy
- stop storing `batch_turns[*].field_changes` if it is a partition of `state.batch_field_changes`
- make `_operation_detail_payload()` build on `_field_changes_payload()` instead of duplicating its base serialization
- add `getContentEdits(report)` for repeated `report.change.content_edits` traversal in JS
- promote `FieldChange` from `porting/edit/types.py` as the canonical typed representation
- stop manually constructing `outcome.changes` dicts in audit paths when `FieldChange.to_dict()` can define the wire schema
- align `NodeFieldSnapshot` fields with delta code through a shared constant or generated field list
- consider adding a `kind` discriminator to distinguish widget, mode, link, and input-binding changes

## Structural Cleanup

### 6. Delete Stale Duplicated Renderers In `vibecomfy_roundtrip.js`

**Problem:** `vibecomfy_roundtrip.js` contains private renderer copies that are already exported from `panel_composer.js`.

**Concrete duplicates found:**

- `renderDeveloper`, `renderDeveloperDisclosure`, and `renderDeveloperSubsection` exist in both `vibecomfy_roundtrip.js` and `panel_composer.js`.
- `renderSettings` exists in both files, and the `vibecomfy_roundtrip.js` copy appears stale because `panel_composer.js` handles more route status branches.
- composer action dependency construction appears both in a wrapper and inline in `renderAgentPanelSections`.

**Cleanup target:** make `panel_composer.js` canonical for developer, settings, notice, and composer action rendering. `vibecomfy_roundtrip.js` should call imported functions with dependency objects, not keep closure-bound forks.

**Expected payoff:** remove roughly 200 duplicated lines and reduce divergence between route/status UI states.

### 7. Unify Agent Status Polling

**Problem:** `agent_status_poller.js` and `vibecomfy_roundtrip.js` both implement `/vibecomfy/agent/status` refresh logic: fetch, parse, set `statusSnapshot`, update route/model selects, derive `routeStatus`, and handle retry/error cases.

**Why it matters:** these paths already differ in readiness logic. Two pollers can race and overwrite status with differently derived route states.

**Cleanup target:** make `agent_status_poller.js` the single implementation and have roundtrip delegate to it.

**Tests:** status payload matrix covering ready, loading, missing options, malformed, unavailable, and fetch error.

**Concrete duplicates found:** `buildStatusUrl`, `routeStatusState`, `routeOptionsFromStatus`, `getRouteOptions`, `getRouteDescriptor`, `clearAgentStatusRetry`, `scheduleAgentStatusRetry`, `populateRouteSelect`, and `syncChooseEngineGate` should live in `agent_status_poller.js`, not as local roundtrip copies.

### 8. Unify Provider / Route Readiness Payloads

**Problem:** provider status and readiness payloads are assembled in multiple backend locations, then interpreted again by the frontend.

**Concrete duplicates found:**

- `comfy_nodes/agent/provider.py` readiness / `get_agent_status()`
- `comfy_nodes/agent/routes.py` `_handle_agent_status()`
- `comfy_nodes/agent/fixture_provider.py` readiness / `get_agent_status()`
- frontend polling and settings renderers

**Cleanup target:** make `provider.py::get_agent_status()` the canonical backend payload. Route handlers and fixture providers should pass through the canonical shape or call the same helper, not re-synthesize `ok`, `ready`, `readiness`, `provider_available`, or error fallback fields.

**Related cleanup:** credential detection has overlapping helpers in `provider.py`; remove unused `_arnold_creds_present()` if still unused and use one credential presence helper for env and `.env` scanning.

**Concrete sub-cleanups:**

- reconcile backend route aliases with frontend `ROUTE_ALIASES`; the maps disagree today
- reconsider `DEFAULT_ROUTE = "arnold"` if `auto` resolution actually prefers OpenRouter and the frontend defaults to OpenRouter
- disambiguate three "ready" concepts: provider availability, workflow/template maturity, and UI route status
- drop `ok` from status responses if the frontend uses `ready`/`provider_available` instead

### 9. Break Up `vibecomfy_roundtrip.js`

**Problem:** this file owns too many responsibilities: websocket/event handling, state normalization, graph apply logic, preview UI, candidate/apply controls, chat hydration, and compatibility behavior.

**Cleanup target:** split by responsibility:

- event intake and normalization
- transcript state
- candidate/apply state
- graph preview/apply adapter
- render adapters

### 10. Narrow `panel_thread.js` To Thread Rendering

**Problem:** the thread renderer still appears to know too much about detail filtering, progress semantics, row state, and activity classification.

**Cleanup target:** make it consume already-safe view models. The renderer should not decide whether a raw event is internal; it should never receive raw events.

### 11. Make Backend Response Contracts Explicit

**Problem:** `/agent-executor`, `/agent-edit/chat`, session artifacts, debug routes, and compatibility envelopes carry overlapping response fields.

**Cleanup target:** define typed contract builders for:

- user transcript response
- preview/apply candidate response
- execution progress event
- audit/debug artifact
- legacy compatibility response

The compatibility response should be an adapter around the canonical contracts, not a second source of truth.

### 12. Collapse Backend Chat Artifact Writers

**Problem:** applyable turns and executor-only turns write similar `chat.json` artifacts through different functions. Reports called out `_write_turn_chat_artifact()` in `edit.py` and `_write_executor_only_chat_artifact()` in `routes.py`.

**Why it matters:** session readers must understand multiple shapes for the same artifact. That spreads compatibility logic into read paths.

**Cleanup target:** one `write_chat_artifact(...)` helper, likely in `audit.py` or a new session artifact module, with route-aware optional sections.

### 13. Consolidate Compatibility / Envelope Builders

**Problem:** response builders layer `success_envelope`, `turn_envelope`, compatibility fields, session artifact fields, outcome, and apply eligibility in several different call sites.

**Concrete overlaps found:**

- `_build_compatibility_response_fields()` in `edit.py`
- `_executor_compatibility_fields()` in `routes.py`
- `_build_batch_repl_response`
- `_build_dev_success_response`
- `_build_batch_repl_failure_response`
- `_build_dev_failure_response`
- `_serialize_executor_result`

**Cleanup target:** one `response_envelope(context, state, result)` builder in `contracts.py` that composes canonical outcome, eligibility, hashes, audit refs, and legacy compatibility aliases.

### 14. Replace Overlapping Session Readers With One Artifact Iterator

**Problem:** session chat, session JSON, session bundle, debug CLI, and issue-report generation all walk the same session directory and read similar `chat.json`, `response.json`, `request.json`, audit, and artifact files.

**Concrete overlaps found:**

- `read_session_chat()`
- `read_session_json()`
- `read_session_bundle()`
- `_handle_agent_edit_chat()`
- `vibecomfy/commands/_agent_edit_debug.py`
- diagnostics report ZIP generation

**Cleanup target:** create one internal `read_session_artifacts(session_dir)` iterator with formatters for chat, JSON metadata, bundle, CLI, and diagnostics.

### 15. Merge Accept / Reject Action Handling

**Problem:** accept and reject route handlers have near-identical validation, action response normalization, audit attachment, and idempotency propagation.

**Cleanup target:** one `_handle_agent_edit_action(payload, action, session_fn)` plus shared action audit writing.

**Extend this cleanup to route wrappers:** accept/reject/rebaseline wrappers repeat JSON parsing, payload validation, `_safe_session_id`, `turn_id` checks, `asyncio.to_thread`, exception conversion, and response serialization. GET session routes for chat/session-bundle/session-json also share the same wrapper shape. Add `_coerce_idempotency_key(payload)`, `_build_action_route(...)`, and `_build_get_session_route(...)` helpers if this remains in `routes.py`.

### 16. Consolidate Audit Download And Debug Surfaces

**Problem:** audit/debug is exposed through multiple overlapping paths:

- bubble detail audit download
- per-turn audit download
- current audit download
- issue report ZIP audit/debug files
- developer raw JSON
- separate debug raw response region

**Cleanup target:** keep `buildAuditEnvelope()` as the canonical envelope builder and expose it through one UI action per scope: current response, selected turn, full issue report. Merge raw debug display into the developer section.

### 17. Consolidate Identity Keys

**Problem:** identity is represented by several string encodings and alias fields.

**Concrete duplicates found:**

- `turn_id` vs `detail_turn_id`; `detail_turn_id` appears JS-only and should be removed
- `turn_key` encodes `session_id`, `turn_id`, and status for dedupe
- `response_id` encodes `{session_id}/{turn_id}` for ratings
- `messageStableKey()` encodes several identity domains into strings
- snake_case wire ids are converted into camelCase JS state fields at many sites

**Cleanup target:** keep canonical identity as structured fields: `session_id`, `turn_id`, `entry_type` or `role`. Use typed/discriminated key objects internally instead of opaque string encodings where possible. If a legacy string id is required for an endpoint, derive it at the boundary.

### 18. Remove Runtime Mirror Fields

**Problem:** some state is mirrored under multiple property names for defensive fallback rather than real semantics.

**Concrete duplicates found:**

- `runtime.lastThreadRender` and `runtime._lastThreadRender` carry the same payload
- `runtime.lastThreadRender` and `panel.lastThreadRender` are both written by thread rendering
- `message.progress`, `message.progress_label`, and `message.canonical_activity` can represent the same progress state

**Cleanup target:** keep one canonical runtime/debug field per concept. If a fallback exists only for historical compatibility, migrate old data once and remove the live mirror.

### 19. Collapse Intent Metadata Aliases

**Problem:** intent node `execution_mode` is read from three nested locations and written to more than one location.

**Cleanup target:** make `properties.vibecomfy.runtime.execution_mode` canonical. Add one migration path for old nodes with widget-level `properties.execution_mode`, then stop writing the legacy path.

### 20. Consolidate Failure / Error Message Surfaces

**Problem:** failure messages and failure metadata are serialized in too many layers.

**Concrete duplicates found:**

- `FailureEnvelope.message` mirrors `FailureEnvelope.user_facing_message`
- failure `kind` / `stage` appears in envelope, outcome, debug payload, and executor result
- `state.user_message`, `state.batch_final_summary`, and `state.batch_done_summary` are often set to the same value
- diagnostics issues and failure envelopes describe the same root failure through parallel streams
- `ExecutorResult.failure_message` duplicates envelope message
- frontend code repeats `failure.user_facing_message || failure.message || failure.error` in many locations

**Cleanup target:** user-facing failure text should have one canonical channel. Structured diagnostics should attach to that envelope as details, not create a separate competing error model.

**Frontend helper:** add `resolveFailureMessage(failure, fallback)` and `resolveFailureDiagnosticMessage(...)` so thread bubbles, composer notices, and diagnostics use the same fallback chain.

**Tests:** assert failure envelopes do not emit duplicate message keys or repeat kind/stage across unrelated layers; assert frontend helper priority `user_facing_message > message > error > fallback`.

### 21. Remove Dead Legacy Activity-Strip Code

**Problem:** after removing user-visible batch activity rows, several legacy functions and mounts appear to remain as empty shells.

**Concrete candidates found:**

- `_renderDurableTurnRow` in `panel_thread.js`, reported as uncalled
- `populateActivityRows`, now apparently a hollow clear-only function
- `_injectProgressPulseStyle`, only needed by the old durable/batch row renderer
- below-thread `activityMount` scaffolding that is created and hidden but no longer populated
- legacy `.vibecomfy-batch-row` selectors in tests that intentionally assert the old strip stays gone
- possibly vestigial `remaining_batches` parsing/display if the backend no longer emits it

**Cleanup target:** delete truly unreachable render/CSS/mount code after confirming no current-source callers outside `web_dist`. Keep regression tests that assert the old activity strip does not come back, but move the old class name into a shared constant and update comments.

### 22. Remove Dead Compatibility Shims And Runtime Artifacts

**Problem:** reports found source-tree clutter that is either truly dead or generated/debug output.

**Concrete candidates:**

- `tools/_widget_schema.py`, reported as a zero-call compatibility wrapper
- stale `web_dist` hash directories not matching the active source hash
- root screenshots like `comfyui_*.png`
- stale session export ZIPs
- stale PID/scratch/local files such as `chain_run.pid`, `temp/counter.txt`, `local_env.sh`
- `agent_edit_e2e.mjs`, if confirmed not invoked by current scripts/CI

**Cleanup target:** remove only files that are gitignored or proven unreferenced. Keep generated-but-committed sources such as `vibecomfy/nodes/_generated`, `agent_edit_response_contract_generated.js`, snapshots, `template_index.json`, and `custom_nodes.lock`.

### 23. Modularize Thread Message Normalization

**Problem:** `vibecomfy_roundtrip.js` and `panel_thread.js` are coupled through a large mutable dependency bag for message normalization, signatures, rating state, detail snapshots, and bubble rendering.

**Cleanup target:** extract a `panel_thread_messages.js` module with:

- `ThreadMessageEntry` normalization
- stable key/signature computation
- safe detail-snapshot attachment
- rating state inputs as explicit fields, not roundtrip callbacks

This is a lower-risk extraction than moving transcript persistence because it can be additive and covered by browser tests.

### 24. Extract Backend Message Composition

**Problem:** `edit.py` contains pure functions for humanized edit messages, terminal answer messages, no-op messages, batch summaries, and batch reports. These are message-formatting concerns embedded in the edit pipeline.

**Cleanup target:** extract a backend `chat_message_composer.py` or similar pure module. Preserve fixture output byte-for-byte.

### 25. Consolidate Low-Level Normalizers

**Problem:** several small normalizers are duplicated exactly or nearly exactly across modules.

**Concrete duplicates found:**

- provenance path normalization in `_provenance_utils.py`, `porting/emitter.py`, and `porting/convert.py`
- `_normalize_input_aliases` in `ir/compile.py` and `workflow.py`
- model path normalization in `porting/emitter.py` and `porting/emit_constants.py`
- Comfy type normalization in `porting/resolution.py`, `schema/validate.py`, and `porting/edit/_ir_utils.py`
- exec IO metadata normalization in `porting/emit/ui.py`, `ingest/normalize.py`, and `comfy_nodes/exec_node.py`
- batch response normalization in `agent/provider.py` and `agent/edit.py`
- `_format_available_names` and `_is_ui_only_prompt_input` copied between `workflow.py` and `ir/compile.py`
- slug helpers copied between `porting/emitter.py` and `porting/emit_subgraph.py`
- `_strip_unused_template_imports` / `_import_binding_name` copied across emit modules
- clarify-response sanitizer helpers duplicated between `agent/routes.py` and `agent/edit.py`

**Cleanup target:** prefer existing canonical homes where present, especially `_provenance_utils.py`. Add small parity tests before deleting local copies.

### 26. Clean Generated / Stale Web Bundles

**Problem:** reports found multiple hash-named `web_dist/` snapshots. These appear to be generated build outputs and may contain stale copies of source JS.

**Cleanup target:** confirm the active bundle strategy, keep only the active/generated artifact if needed for local ComfyUI serving, and ensure stale hash directories are ignored or removed from source control if they are not meant to be tracked.

**Caution:** do not delete `web_dist` blindly while ComfyUI is running from a specific active hash. Verify runtime references first.

### 27. Move Overlay Drawing To `panel_overlay.js`

**Problem:** overlay label drawing appears duplicated between `panel_overlay.js` and `vibecomfy_roundtrip.js`.

**Cleanup target:** export one overlay drawing helper from `panel_overlay.js` and have roundtrip call it. Add visual or pixel-level regression coverage for label reservation, truncation, and padding.

### 28. Broader Module Boundary Cleanup

**Problem:** beyond the agent panel, several package modules carry too many responsibilities.

**Candidates:**

- `vibecomfy/workflow.py`: split dataclasses, graph mutation, compile/export, validation, and identity helpers
- `vibecomfy/ingest/normalize.py`: split shape detection, live Comfy converter gate, schema-backed normalization, and exec-source limits
- `vibecomfy/runpod_setup.py`: split config generation, node-pack install, server command, and RunPod-specific patching
- `vibecomfy/executor/core.py`: extract route behavior tables into an executor routes module
- `vibecomfy/commands/run.py`: decompose the large run command into session resolution, embedded dispatch, server dispatch, and CLI override helpers

**Cleanup target:** handle after the messaging-boundary cleanup unless a specific change already touches one of these files.

### 29. Consolidate CLI / Diagnostics Contracts

**Problem:** CLI commands, diagnostics modules, and web debug paths define overlapping status, diagnostic, and turn-record shapes.

**Concrete candidates:**

- `commands/_diagnostics.py` and `diagnostics/findings.py` have parallel diagnostic dataclasses/serializers
- `commands/doctor.py`, `diagnostics/health.py`, and `commands/port/_doctor_all.py` each orchestrate check-suite to findings to report
- `_agent_edit_debug.py` and web diagnostics reconstruct similar durable turn records
- runtime eval queueing manually reimplements parts of `runtime/run.py::run_embedded_sync()`

**Cleanup target:** make `diagnostics/findings.py` canonical for diagnostic records, `diagnostics/health.py` canonical for health orchestration, and define a documented `TurnRecord` / `StatusSnapshot` contract for CLI and web consumers.

## Test Cleanup

### 30. Add Boundary Tests For Internal Event Non-Rendering

**Problem:** current tests catch the known leak but should encode the broader rule: internal execution events must not render in normal chat even if they contain plausible user text.

**Cleanup target:** add fixtures for `batch_turns`, `canonical_activity.details`, websocket turn events, session rehydrate data, and debug/audit payloads.

### 31. Reduce Brittle Browser-Test Duplication

**Problem:** browser tests repeat setup, DOM dumping, and selector logic. Some tests assert implementation details rather than durable UI contracts.

**Cleanup target:** create shared browser harness helpers for:

- mounting the panel
- dispatching agent events
- extracting transcript rows
- extracting stage snapshots
- asserting internal text absence

**Concrete helpers to add:** `openAgentPanel`, `renderThread`, `STANDARD_MOCK_RESPONSES`, `selectors.progressSecondary`, `selectors.executorStage`, `assertNoLegacyActivityRows`, `assertMessagesInOrder`, `assertApplyControls`, and `assertNoInternalLeakage`.

## Follow-Up Evidence Log

The following external reports should be folded into this document as they finish:

- `/tmp/vibecomfy-deepseek-swarm/results`
- `/tmp/vibecomfy-deepseek-redundancy/results`
- `/tmp/vibecomfy-cruft-waves/wave1/results`
- `/tmp/vibecomfy-cruft-waves/wave2/results`

## Design Decisions To Resolve

## System-Level Smell Domains

Eight Codex domain audits looked above local duplication and converged on the same diagnosis: the minor smells are symptoms of unclear ownership for product concepts, contracts, state machines, and observability boundaries. The following domains should guide the cleanup work.

### Product Semantics

The product model is undernamed. A chat bubble can currently act as transcript entry, pending worker status, candidate review container, audit handle, failure envelope, or debug surface depending on fields attached to it.

Adopt explicit vocabulary:

- `ConversationMessage`: durable user/assistant transcript text only
- `AssistantWork`: in-progress assistant activity visible as status, not transcript
- `WorkPlan` / `AssistantMode`: classified task mode such as answer, inspect, research, propose edit, or research-and-propose-edit
- `ProviderConnection`: selected provider/model plus credential availability
- `WorkflowProposal`: reviewable graph candidate, diff summary, lifecycle, and staleness
- `ProposalEligibility`: whether the current proposal can be applied, with reason
- `WorkflowChangeSet`: canonical user-facing graph changes
- `ProgressSnapshot`: user-facing phase display derived from internal events
- `DiagnosticBundle`: audit/debug evidence, never normal transcript input
- `SessionEntry`: durable storage identity, separate from user-visible message

Rename overloaded axes where possible. In particular, use `providerRoute` for OpenRouter/Arnold/etc. and `assistantMode` or `workMode` for inspect/research/revise/adapt.

### Authority And Source Of Truth

The recurring smell is that multiple layers can answer the same question:

- Can this be applied?
- What is the latest candidate?
- What stage is this at?
- What changed?
- What is the transcript?
- Is the provider ready?
- Is this debug-only or user-facing?

Every answer should have one owner. The recommended owners are `ApplyCandidate`, `StageSnapshot`, `TranscriptMessage`, `FieldChange`, backend provider status, `AuditArtifact`, and a session artifact store. Compatibility fields should be adapter outputs, not new inputs.

### Contracts And Versioning

Contracts are currently treated as field sets to preserve, not versioned boundaries with explicit adapters and removal rules. Canonical fields and legacy aliases coexist in normal production envelopes.

Policy:

- define one canonical snake_case wire version for agent edit/session responses
- emit compatibility fields only through named adapters such as `build_legacy_agent_edit_v1(canonical)`
- keep frontend legacy tolerance in a boundary normalizer, not throughout render/lifecycle code
- add `allowLegacy=false` tests that prove the canonical contract stands without aliases
- gate legacy aliases with fixtures and deletion conditions

### Lifecycle State Machines

There are several implicit state machines: panel phase, candidate/apply lifecycle, durable turn lifecycle, submit/pending response lifecycle, batch/activity lifecycle, stage/progress lifecycle, rebaseline/undo lifecycle, route readiness, queue guard, and chat rehydrate.

Make these explicit reducers or diagrams:

- `panelReducer`
- `candidateReducer`
- `progressReducer`
- `transcriptReducer`
- `rebaselineReducer`
- `routeStatusReducer`
- backend durable `TurnState` / baseline-CAS diagram

The highest-risk bugs are transition bugs: stale progress after rehydrate, accept/reject replay disagreeing with frontend eligibility, rebaseline leaving conflicting flags, route-status pollers racing, and non-applyable routes inheriting edit-stage progress.

### Observability And Debug Boundaries

VibeComfy has observability primitives but not yet a clear observability architecture. Debug surfaces are currently acting as architecture.

Separate:

- operational telemetry: counters/timings/stage transitions/failure kind; no raw prompts, filesystem paths, graph bodies, or exceptions
- audit artifact: durable local evidence for one turn/action, redacted by default
- developer debug: raw-ish local-only inspection behind explicit disclosure
- user-facing error: one sanitized message plus stable failure kind/retryability/next action
- shareable issue report: opt-in, redacted, self-contained, no absolute paths or secrets

Normal UI render must never consume `raw_payload`, `debug`, `audit`, `batch_turns`, session JSON, absolute paths, raw exception strings, stack traces, model prompts/responses, or artifact previews.

### Artifact Lifecycle

Generated artifacts need a manifest and policy. Categories should be explicit:

- source
- generated committed source
- generated local build output
- runtime output
- diagnostic export
- scratch

Add an `ARTIFACTS.md` or equivalent table with path, lifecycle, committed status, generator, check command, cleanup command, and owner. `cleanup.md` itself should be deliberately classified: either durable docs, likely under `docs/`, or local audit scratch under an ignored path.

### Test Strategy

Tests should move from implementation-detail preservation toward system invariants:

- only safe projections render in default chat
- debug/audit data requires explicit affordance
- rehydrate, submit, websocket, and session artifacts all project to one transcript model
- UI status comes from one `StageSnapshot`
- all apply/reject controls read one `ApplyCandidate`
- public outcomes are closed and internal outcomes map before render
- hostile payloads containing internal text, gates, paths, raw batch code, diagnostics, or provider metadata never appear in default UI

Keep legacy compatibility tests quarantined. They should prove old payloads adapt into canonical models, not that legacy internals remain live.

### Ownership And Governance

Add ownership domains and PR guardrails:

- agent response contracts
- transcript/session durability
- execution/debug/audit
- provider/router readiness
- frontend panel rendering/state
- graph/edit/apply lifecycle
- workflow/IR/compiler
- generated artifacts

Guardrails:

- every new state field must declare its bucket
- new wire contracts must update Python builders, JS boundary normalizer, docs, and fixtures together
- renderers may consume only safe view models
- debug/audit additions need leakage tests
- generated code needs generator/check policy
- compatibility shims need owner, caller evidence, fixture coverage, and deletion condition

Useful automated checks: forbid direct snake_case reads outside the boundary normalizer, forbid renderers from reading `debug`/`audit`/`canonical_activity.details`/`batch_turns`, enforce contract parity, run fixture round-trip leak tests, check generated freshness, and warn on large-module growth without an extraction note.

### Transcript Source Of Truth vs Execution Source Of Truth

The reports disagree on whether `turns[]` or `chatMessages[]` should become canonical. The cleaner split is likely not choosing one array for everything:

- canonical user transcript: durable sanitized chat messages
- canonical execution state: internal execution events / canonical activity
- canonical user stage: `StageSnapshot`, derived from execution state
- renderer input: safe view models only

This preserves the existing stage UI while preventing internal execution records from being treated as transcript rows.

### Progress Model Canonical Direction

One report recommends eliminating standalone `executorProgress` in favor of `canonical_activity.phase_progress`; another earlier review recommends a named `StageSnapshot` projection. These can be reconciled by making `canonical_activity.phase_progress` internal/source data and `StageSnapshot` the only UI-facing projection.

## Recommended Migration Order

1. **Delete obvious dead code and exact duplicates first:** stale renderers in `vibecomfy_roundtrip.js`, dead activity-strip code, `canvasApplyAllowed`, `_lastThreadRender`, duplicated normalizers with parity tests.
2. **Unify safe projections:** `StageSnapshot`, `ApplyCandidate`, `FieldChange`, failure envelope shape, route/provider status payload.
3. **Extract audit/session readers:** audit artifacts and session artifact iteration are lower-risk because they can be byte-for-byte compared against existing outputs.
4. **Separate execution events from transcript:** introduce internal execution event storage/projection while leaving existing transcript rendering intact.
5. **Only then extract durable lifecycle and baseline/hash logic:** these touch CAS/stale-state behavior and need characterization over real session snapshots.
6. **Extract transcript persistence last:** it is highest risk because thread UI, stage UI, candidate details, and rehydrate all consume chat shape today.
