# Compatibility Ledger

Every legacy alias, compatibility shim, or retained duplicate path that remains
after the `pristine-agent-architecture` epic is recorded here.  Each entry has
an owner, evidence of current callers, fixture/test coverage, and a deletion
trigger.

## Legend

- **Owner**: module/team responsible for the compatibility path.
- **Caller evidence**: how we know it is still used.
- **Fixture coverage**: tests that would fail if the path were removed or
  changed.
- **Deletion trigger**: the condition under which the path may be removed.

## Backend compatibility paths

### Aggregate-free agent-edit candidates (read-only)

- **Owner**: `vibecomfy_roundtrip.js` migration adapter and response normalizer.
- **Purpose**: Historical V1 candidates can still be displayed, but cannot
  enter Apply or Reject action endpoints. All new V2 candidates require
  `candidate_transaction_v1` and the live scoped executor.
- **Caller evidence**: Old persisted sessions and characterization fixtures may
  omit `candidate_transaction`.
- **Fixture coverage**: missing-plan/read-only cases in
  `tests/browser/roundtrip_smoke.test.mjs` and response-contract legacy fixtures.
- **Deletion trigger**: Every supported persisted session has been migrated or
  aged out, and no rehydrate fixture contains an aggregate-free candidate. At
  that point delete the adapter and the unreachable legacy whole-graph Apply
  implementation together.

### `build_legacy_agent_edit_v1`

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py`
- **Purpose**: Adds v1 field aliases (`apply_allowed`, `candidate_graph`,
  `graph_unchanged`, etc.) to canonical agent-edit responses.
- **Caller evidence**: Called by `FailureEnvelope.to_dict`,
  `ensure_agent_edit_response_contract`, and legacy consumer code paths.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_contracts.py`,
  `tests/test_comfy_nodes_agent_edit.py`.
- **Deletion trigger**: All external consumers (panel, CLI, persisted session
  readers) have migrated to canonical field names and the frontend no longer
  reads v1 aliases.

### `apply_allowed` / `canvas_apply_allowed` / `queue_allowed` v1 booleans

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py`
- **Purpose**: Backward-compatible boolean flags produced by
  `build_legacy_agent_edit_v1`.
- **Caller evidence**: Frontend panel and some existing tests still read these
  fields.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_contracts.py`,
  `tests/test_comfy_nodes_agent_edit.py`.
- **Deletion trigger**: Frontend reads eligibility from the canonical
  `eligibility` object only.

### `FieldChange` frozen dataclass (unchanged)

- **Owner**: `vibecomfy/porting/edit/types.py`
- **Purpose**: Canonical 4-field representation of a field change.
- **Caller evidence**: Used across `contracts.py`, `edit.py`, porting, and
  executor modules.
- **Fixture coverage**: Extensive; `tests/test_comfy_nodes_agent_*` and
  porting tests.
- **Deletion trigger**: N/A — this is the canonical shape, not a compatibility
  path.

### `DiagnosticRecord` optional `path` / `mtime` fields

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py`
- **Purpose**: Carry local filesystem metadata for CLI debug consumers.
- **Caller evidence**: Used by `tests/test_comfy_nodes_agent_contracts.py`
  round-trip test and may be used by future CLI record consumers.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_contracts.py`.
- **Deletion trigger**: When all consumers read turn paths from the canonical
  `(session_id, turn_id)` tuple instead of the local `path` field.

### Raw session/chat readers (`read_session_chat`, `read_session_json`)

- **Owner**: `vibecomfy/comfy_nodes/agent/session.py` / `edit.py`
- **Purpose**: Persisted session artifacts retain raw execution internals for
  debug, audit, and issue-bundle surfaces while HTTP routes project normal UI
  payloads before serialization.
- **Caller evidence**: `read_session_bundle` and debug/CLI flows need raw
  evidence; `/agent-edit/chat` and `/agent-edit/session-json` apply public
  projection at the route boundary.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_edit.py`
  (`test_session_bundle_route_retains_raw_sentinels`) and public chat/session
  projection tests.
- **Deletion trigger**: When the storage format itself is migrated and all
  debug/audit consumers read through projected accessors.

### `AgentError`

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py`
- **Purpose**: Python import compatibility alias for `FailureEnvelope`.
- **Caller evidence**: `routes.py` and `edit.py` still import `AgentError` for
  failure response helper signatures; `contracts.py` exports
  `AgentError = FailureEnvelope`.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_contracts.py` asserts the
  alias identity, with failure envelope behavior covered by
  `tests/test_pristine_architecture_guardrails.py` and
  `tests/test_comfy_nodes_agent_edit.py`.
- **Deletion trigger**: Remove only when active imports use `FailureEnvelope`
  directly and downstream code no longer relies on the exported name.

### Failure hint camelCase inputs

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py` and
  `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`.
- **Purpose**: Normalize historical or frontend-shaped public error inputs such
  as `failureKind` and `nextAction` to canonical snake_case public outcomes.
- **Caller evidence**: `FAILURE_HINT_KEYS` includes both snake_case and
  camelCase forms, and the browser normalizer mirrors those accepted inputs.
- **Fixture coverage**:
  `tests/test_comfy_nodes_agent_contracts.py::test_ensure_agent_edit_response_contract_maps_all_failure_hint_keys_to_error`,
  browser response-contract tests, and persisted error stamping tests in
  `tests/test_comfy_nodes_agent_edit.py`.
- **Deletion trigger**: Drop camelCase inputs after historical persisted error
  outcomes using `failureKind`/`nextAction` are outside the supported rehydrate
  window and snake_case-only fixtures cover the same failures.

### `apply_eligible`

- **Owner**: agent-edit backend contract and frontend response normalizer.
- **Purpose**: Canonical executor/apply authorization bit, with compatibility
  fallback only where old payloads are normalized into eligibility state.
- **Caller evidence**: Backend edit/routes code stamps it on relevant
  responses; the browser normalizer and lifecycle code gate Apply behavior from
  it when canonical candidate data is present.
- **Fixture coverage**: `tests/test_pristine_architecture_guardrails.py`,
  `tests/test_comfy_nodes_agent_edit.py`,
  `tests/browser/agent_edit_response_contract.test.mjs`,
  `tests/browser/roundtrip_smoke.test.mjs`, and
  `tests/browser/payload_contracts.test.mjs`.
- **Deletion trigger**: N/A for the canonical authorization field. Remove only
  compatibility inference from historical raw payloads after
  `eligibility.applyable` and `ApplyCandidate` state are the only frontend
  apply contract.

### `apply_eligibility` legacy object

- **Owner**: agent-edit backend contract migration and frontend response
  normalizer/status boundaries.
- **Purpose**: Retained compatibility object for old submit, action,
  rebaseline, and rehydrate payloads. New code should treat this as a
  deletion-oriented bridge toward canonical `eligibility` / `apply_eligible`
  data, not as a permanent API commitment.
- **Caller evidence**: `contracts.py`, `edit.py`, `gates.py`, `routes.py`, and
  `session.py` still stamp, preserve, or derive the object while
  `agent_edit_response_contract.js`, its generated mirror, `agent_status_poller.js`,
  and `vibecomfy_roundtrip.js` normalize or display old payloads at boundary
  surfaces.
- **Fixture coverage**: `tests/browser/agent_edit_response_contract.test.mjs`,
  `tests/browser/agent_edit_response_malformed.test.mjs`,
  `tests/browser/agent_edit_lifecycle.test.mjs`,
  `tests/browser/payload_contracts.test.mjs`, and
  `tests/browser/roundtrip_smoke.test.mjs`.
- **Deletion trigger**: Delete once canonical `eligibility` or `apply_eligible`
  payloads are required by all active fixtures and old persisted sessions are
  outside the supported rehydrate window.

### `candidate_graph` / `graph` legacy candidate aliases

- **Owner**: agent-edit backend candidate compatibility adapter and frontend
  response normalizer/status display boundaries.
- **Purpose**: Preserve readability for historical candidate artifacts that
  carried a top-level `candidate_graph` or `graph` alias. This path exists to
  migrate callers to canonical `candidate.graph` plus `candidate_graph_hash`,
  not to commit new normal render or lifecycle code to top-level graph aliases.
- **Caller evidence**: `edit.py`, `routes.py`, and `session.py` still synthesize
  or rehydrate top-level candidate graph shapes; `agent_edit_response_contract.js`,
  its generated mirror, `agent_status_poller.js`, `panel_composer.js`, and
  `vibecomfy_roundtrip.js` read them only as boundary normalization,
  status/debug, or compatibility display inputs.
- **Fixture coverage**: `tests/browser/agent_edit_response_contract.test.mjs`,
  `tests/browser/payload_contracts.test.mjs`,
  `tests/browser/roundtrip_smoke.test.mjs`, and payload contract fixtures under
  `tests/fixtures/payload_contracts/`.
- **Deletion trigger**: Delete once canonical `candidate.graph` /
  `candidate_graph_hash` fixtures normalize with `allowLegacy=false` and
  persisted session rehydrate no longer needs top-level graph aliases.

### `field_changes` flat arrays on turns/messages

- **Owner**: agent-edit field-change projection migration across backend
  audit/session output and frontend response normalization/reporting.
- **Purpose**: Retain flat turn/message `field_changes` arrays so old audit,
  characterization, and rehydrate artifacts remain readable while normal code
  moves to canonical outcome `changes` and named field-change accessors.
- **Caller evidence**: `audit.py` and `edit.py` still write historical flat
  field-change shapes; `vibecomfy_roundtrip.js`, `panel_thread.js`,
  `agent_edit_response_contract.js`, and `diagnostics_reporting.js` extract or
  compact them for compatibility display/reporting.
- **Fixture coverage**: `tests/browser/roundtrip_smoke.test.mjs`,
  `tests/browser/agent_edit_lifecycle.test.mjs`,
  `tests/browser/agent_edit_response_contract.test.mjs`,
  `tests/browser/panel_thread_rating.test.mjs`,
  `tests/browser/payload_contracts.test.mjs`, and characterization fixtures
  under `tests/characterization/fixtures/agent_edit/`.
- **Deletion trigger**: Delete from normal render/lifecycle readers once
  `readFieldChanges()` is the only frontend accessor and rehydrate fixtures
  carry canonical outcome `changes`. Diagnostics and audit may keep read-only
  support only until historical artifacts age out.

### Clarify/noop forbidden-key guards

- **Owner**: `vibecomfy/comfy_nodes/agent/executor_response.py`.
- **Purpose**: `_NON_APPLYABLE_FORBIDDEN_KEYS` and
  `_strip_non_applyable_forbidden_fields` are the active production
  executor route-envelope guard that prevents candidate/apply fields from
  leaking into clarify/noop responses. `_CLARIFY_FORBIDDEN_KEYS` is a
  retained legacy alias for documentation/test traceability, not a compatibility path
  with production callers.
- **Caller evidence**: `serialize_executor_result` and
  `_sanitize_clarify_payload` call `_strip_non_applyable_forbidden_fields`
  before returning non-applyable response shapes; `routes.py` re-exports the
  helpers for legacy private callers. No production caller reads
  `_CLARIFY_FORBIDDEN_KEYS`; it aliases `_NON_APPLYABLE_FORBIDDEN_KEYS`.
- **Fixture coverage**: Clarify/noop response tests in
  `tests/test_comfy_nodes_agent_edit.py` and forbidden-field assertions in
  `tests/browser/payload_contracts.test.mjs`.
- **Deletion trigger**: N/A — this is a route contract guard, not a compatibility
  shim. Keep `_CLARIFY_FORBIDDEN_KEYS` only while ledger/test traceability needs
  the old name.

### Edit-layer clarify-response sanitizer

- **Owner**: `vibecomfy/comfy_nodes/agent/edit.py` response assembly.
- **Purpose**: `_CLARIFY_FORBIDDEN_RESPONSE_KEYS` and
  `_strip_clarify_forbidden_response_fields` sanitize pure clarify responses
  after backend response assembly so candidate/apply fields do not leak into the
  assembled clarify response. The edit-layer key set is content-identical to
  the route-layer set today, but it is owned by response assembly, not the
  route-envelope stripping boundary.
- **Caller evidence**: `_sanitize_pure_clarify_response` normalizes the public
  clarify outcome/message shape and then calls
  `_strip_clarify_forbidden_response_fields`. The batch and non-batch edit
  response builders call `_sanitize_pure_clarify_response` after
  `build_legacy_agent_edit_v1(...)` may have added candidate/apply aliases for
  legacy response compatibility.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_edit.py` pure clarify
  response tests, including
  `test_batch_repl_response_no_candidate_for_pure_clarify`, and the ledger
  marker assertions in `tests/test_agent_edit_compatibility_ledger.py`.
- **Deletion trigger**: Delete this sanitizer only after tests prove pure clarify
  response assembly no longer emits candidate/apply fields before sanitization;
  until then, keep it separate from the route-layer guard so route-envelope and
  edit-response ownership can be removed independently.

### Graph hash fields

- **Owner**: agent-edit backend session/edit contract and frontend lifecycle.
- **Purpose**: `client_graph_hash` identifies the client/request graph snapshot;
  `candidate_graph_hash` identifies candidate artifacts. These are canonical
  active/session/diagnostic fields, not removable legacy aliases.
- **Caller evidence**: `session.py` records and validates the hashes;
  `edit.py` stamps candidate and failure responses; `vibecomfy_roundtrip.js`
  sends request/action hashes and displays candidate hash diagnostics;
  `agent_edit_lifecycle.js` preserves recovery hashes.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_edit.py`,
  backend-spine graph-hash tests, `tests/browser/roundtrip_smoke.test.mjs`,
  `tests/browser/agent_edit_lifecycle.test.mjs`, and payload-contract fixtures.
- **Deletion trigger**: N/A for `client_graph_hash` and `candidate_graph_hash`.
  They may move behind named projections for UI display, but the backend/session
  identity fields remain canonical.

### `submitted_client_graph_hash` / `action_client_graph_hash`

- **Owner**: `vibecomfy/comfy_nodes/agent/session.py`.
- **Purpose**: Session migration/action-validation fields that preserve
  submit-time and action-time client hashes for stale-state checks.
- **Caller evidence**: Session allocation stores `submitted_client_graph_hash`;
  accept/reject validation reads it and records `action_client_graph_hash`;
  `edit.py` rehydrates submit hash from turn records.
- **Fixture coverage**:
  `tests/test_comfy_nodes_agent_edit.py::test_agent_edit_accept_matches_browser_client_graph_hash`,
  backend-spine stale-state/hash tests, and persisted session fixtures under
  `tests/fixtures/e2e_sessions/`.
- **Deletion trigger**: Remove only after persisted sessions are migrated and
  accept/reject tests prove canonical `submit_graph_hash` plus turn identity
  cover the same stale-state behavior.

## Frontend compatibility paths

### `vibecomfy_roundtrip.js` retained orchestration glue

- **Owner**: frontend panel (`vibecomfy/comfy_nodes/web/`)
- **Purpose**: Event wiring, lifecycle coordination, and dependency assembly
  after renderers/pollers were extracted in M5.
- **Caller evidence**: It is the top-level panel entry point and is loaded by
  ComfyUI.
- **Fixture coverage**: `tests/browser/roundtrip_smoke.test.mjs`,
  `tests/browser/agent_status_poller.test.mjs`.
- **Deletion trigger**: Only when the panel entry point is replaced by a
  smaller orchestrator and all event wiring has been moved to dedicated
  modules.

### Legacy import wrappers in `vibecomfy_roundtrip.js`

- **Owner**: frontend panel
- **Purpose**: Current import-wrapper surface while the panel is being split
  into owner modules. This documents the surfaces that exist today so they are
  auditable; it is not an indefinite preservation promise.
- **Caller evidence**: `vibecomfy_roundtrip.js` currently re-exports
  diagnostics helpers from `diagnostics_reporting.js`
  (`configureDiagnosticsDeps`, `buildIssueReport`, `buildAgentSolvePrompt`,
  `buildCurrentAuditEnvelope`, `downloadCurrentAudit`,
  `collectIssueReportFiles`, `downloadIssueReportZip`, `showIssueModal`,
  `submitRating`, and `installBrowserDiagnosticsCapture`); exposes facade
  entry points that adapt local graph helpers (`normalizeForSerialize`,
  `normalizeForDisplay`, `normalizeForApply`, and `repairLiveNodes`); and
  forwards scheduler exports from `panel_scheduler.js` / lifecycle state
  (`RENDER_SECTIONS`, `markAgentPanelDirty`, `markAllAgentPanelDirty`, and
  `scheduleRenderAgentPanel`). The related frontend view-model compatibility
  surface is the camelCase state field set listed in the fixture ledger:
  `applyAllowed`, `canvasApplyAllowed`, `auditRef`, `debugPayload`, and
  `lastSubmitFieldChanges`.
- **Fixture coverage**: `tests/browser/roundtrip_smoke.test.mjs`,
  `tests/browser/agent_status_poller.test.mjs`,
  `tests/browser/agent_edit_lifecycle.test.mjs`, and
  `tests/browser/agent_edit_lifecycle_transcript.test.mjs`.
- **Deletion trigger**: Remove each wrapper when its callers import directly
  from the canonical owner module or consume a named selector/view model
  instead of the retained camelCase panel-state field; keep only the smaller
  panel entry point needed by ComfyUI.

### `executor_pending`

- **Owner**: frontend lifecycle/transcript migration.
- **Purpose**: Temporary optimistic pending-row marker for in-flight assistant
  entries. Durable transcripts should converge on canonical `TurnIdentity` plus
  `pending_response` / stage state; this is deletion-oriented UI compatibility,
  not a persisted transcript API.
- **Caller evidence**: `vibecomfy_roundtrip.js` and `agent_edit_lifecycle.js`
  still construct or reconcile optimistic pending messages, and
  `panel_thread.js` renders pending rows while canonical rehydrate strips the
  marker from durable messages.
- **Fixture coverage**: `tests/browser/agent_edit_lifecycle.test.mjs`,
  `tests/browser/agent_edit_lifecycle_transcript.test.mjs`,
  `tests/browser/active_row_rendering.test.mjs`,
  `tests/browser/agent_edit_response_contract.test.mjs`,
  `tests/browser/panel_thread_rating.test.mjs`,
  `tests/browser/payload_contracts.test.mjs`, and
  `tests/browser/roundtrip_smoke.test.mjs`.
- **Deletion trigger**: Delete when pending assistant entries are keyed by
  canonical `TurnIdentity` plus `pending_response` / stage state, and transcript
  tests assert no durable rehydrate message carries `executor_pending`.

### camelCase frontend view-model fields

- **Owner**: frontend lifecycle/composer state migration.
- **Purpose**: Retain camelCase normalized state fields such as `applyAllowed`,
  `canvasApplyAllowed`, `auditRef`, `debugPayload`, and
  `lastSubmitFieldChanges` while tests and reducers still inspect internal view
  models. These are frontend view-model compatibility fields, not backend wire
  aliases or permanent API names.
- **Caller evidence**: `agent_edit_lifecycle.js`, `vibecomfy_roundtrip.js`, and
  `panel_composer.js` keep camelCase reducer/view-model fields that browser
  tests inspect directly while the wire contract remains canonical snake_case.
- **Fixture coverage**: `tests/browser/agent_edit_lifecycle.test.mjs`,
  `tests/browser/agent_edit_lifecycle_transcript.test.mjs`, and
  `tests/browser/roundtrip_smoke.test.mjs`.
- **Deletion trigger**: Delete or rename when canonical frontend selectors/view
  models replace panel state fields and tests no longer inspect reducer
  internals by camelCase name.

## Removed in this epic

- Duplicate status/settings renderers in `vibecomfy_roundtrip.js` (M5).
- Monolith-local status polling and choose-engine gating in
  `vibecomfy_roundtrip.js` (M5).
- Ad-hoc turn walk in `_agent_edit_debug.py`; replaced by
  `session.py:iter_turn_records` (M6).
- Field-change repair helpers in `edit.py`; canonical implementation moved to
  `contracts.py:repair_field_changes` (M6).
- Stale root scratch files (`comfyui_arnold_debug*.png`, `chain_run.pid`,
  `temp/counter.txt`) (M7).
