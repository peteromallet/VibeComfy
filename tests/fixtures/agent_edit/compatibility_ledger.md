# Agent-Edit Compatibility Ledger

## Purpose

This ledger is the allowlist for legacy agent-edit aliases retained during the
M1 canonical-contract migration. New normal render, lifecycle, route, or backend
assembly code should use canonical snake_case wire payloads and typed/named view
models. If an alias is still needed, it must be listed here with an owner, an
allowed file boundary, fixture or test coverage, and a deletion trigger.

Canonical server-side `FieldChange` remains
`vibecomfy.porting.edit.types.FieldChange`; `vibecomfy/comfy_nodes/agent/contracts.py`
is the builder/re-export boundary, not a duplicate type definition.

## Retained Alias Allowlist

| Alias or shape | Owner | Allowed files | Fixture coverage | Deletion trigger |
|---|---|---|---|---|
| `apply_allowed` | M1 backend contract migration | Backend builder/pre-adapter files: `vibecomfy/comfy_nodes/agent/contracts.py`, `vibecomfy/comfy_nodes/agent/edit.py`, `vibecomfy/comfy_nodes/agent/routes.py`; JS boundary files: `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`, `vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js`; temporary lifecycle tests/state ingestion in `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js` | `tests/browser/agent_edit_response_contract.test.mjs`, `tests/browser/agent_edit_response_malformed.test.mjs`, `tests/browser/agent_edit_lifecycle.test.mjs`, `tests/browser/payload_contracts.test.mjs`, `tests/browser/roundtrip_smoke.test.mjs`, `tests/fixtures/payload_contracts/agent_edit_accept_response.json`, `tests/fixtures/payload_contracts/agent_edit_rebaseline_response.json`, `tests/fixtures/payload_contracts/chat_rehydrate_response.json` | Delete outside the Python legacy adapter (`build_legacy_agent_edit_v1`) and JS normalizer once canonical `ApplyCandidate`/`apply_eligibility.applyable` payloads cover submit, accept, reject, rebaseline, and rehydrate fixtures with `allowLegacy=false`. |
| `canvas_apply_allowed` | M1 backend contract migration | Same as `apply_allowed`, plus audit/debug display reads in `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` | Same as `apply_allowed`, plus `tests/browser/payload_contracts.test.mjs`; debug display smoke is covered by `tests/browser/roundtrip_smoke.test.mjs` assertions that render `canvasApplyAllowed`/`canvas_apply_allowed` status text. | Delete from normal payload assembly after the Python compatibility adapter is the only producer and frontend selectors expose canonical candidate eligibility. Keep debug display only if it reads normalized selector state rather than the raw alias. |
| `queue_allowed` | M1 backend contract migration | Backend builder/pre-adapter files: `vibecomfy/comfy_nodes/agent/contracts.py`, `vibecomfy/comfy_nodes/agent/edit.py`, `vibecomfy/comfy_nodes/agent/gates.py`, `vibecomfy/comfy_nodes/agent/routes.py`, `vibecomfy/comfy_nodes/agent/session.py`; JS boundary/display files: `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`, `vibecomfy/comfy_nodes/web/agent_status_poller.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` | `tests/browser/agent_edit_response_contract.test.mjs`, `tests/browser/agent_edit_lifecycle.test.mjs`, `tests/browser/payload_contracts.test.mjs`, `tests/browser/roundtrip_smoke.test.mjs`, payload contract fixtures under `tests/fixtures/payload_contracts/` | Delete when route/status and apply eligibility are represented by the named `RouteStatus`/`ApplyCandidate` projections and no UI branch reads the flattened queue flag. |
| `apply_eligibility` legacy object | M1 backend contract migration | Backend builder/pre-adapter files: `vibecomfy/comfy_nodes/agent/contracts.py`, `vibecomfy/comfy_nodes/agent/edit.py`, `vibecomfy/comfy_nodes/agent/gates.py`, `vibecomfy/comfy_nodes/agent/routes.py`, `vibecomfy/comfy_nodes/agent/session.py`; JS boundary/status files: `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`, `vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js`, `vibecomfy/comfy_nodes/web/agent_status_poller.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` | `tests/browser/agent_edit_response_contract.test.mjs`, `tests/browser/agent_edit_response_malformed.test.mjs`, `tests/browser/agent_edit_lifecycle.test.mjs`, `tests/browser/payload_contracts.test.mjs`, `tests/browser/roundtrip_smoke.test.mjs` | Delete when canonical `eligibility` or `apply_eligible` payloads are required by all active fixtures and old persisted sessions are outside the supported rehydrate window. |
| `candidate_graph` / `graph` legacy candidate aliases | M1 backend contract migration | Backend builder/session files: `vibecomfy/comfy_nodes/agent/edit.py`, `vibecomfy/comfy_nodes/agent/routes.py`, `vibecomfy/comfy_nodes/agent/session.py`; JS boundary/status/display files: `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`, `vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js`, `vibecomfy/comfy_nodes/web/agent_status_poller.js`, `vibecomfy/comfy_nodes/web/panel_composer.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` | `tests/browser/agent_edit_response_contract.test.mjs`, `tests/browser/payload_contracts.test.mjs`, `tests/browser/roundtrip_smoke.test.mjs`, payload contract fixtures under `tests/fixtures/payload_contracts/` | Delete when canonical `candidate.graph` / `candidate_graph_hash` fixtures normalize with `allowLegacy=false` and persisted session rehydrate no longer needs top-level graph aliases. |
| `executor_pending` | Frontend lifecycle/render migration | Existing pending-message construction and reconciliation in `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`, and pending-row rendering in `vibecomfy/comfy_nodes/web/panel_thread.js` | `tests/browser/agent_edit_lifecycle.test.mjs`, `tests/browser/agent_edit_lifecycle_transcript.test.mjs`, `tests/browser/active_row_rendering.test.mjs`, `tests/browser/agent_edit_response_contract.test.mjs`, `tests/browser/panel_thread_rating.test.mjs`, `tests/browser/payload_contracts.test.mjs`, `tests/browser/roundtrip_smoke.test.mjs` | Delete when pending assistant entries are keyed by canonical `TurnIdentity` plus `pending_response`/stage state, and transcript tests assert no durable rehydrate message carries `executor_pending`. |
| `field_changes` flat arrays on turns/messages | M1 field-change projection migration | Backend audit/session writers in `vibecomfy/comfy_nodes/agent/audit.py` and `vibecomfy/comfy_nodes/agent/edit.py`; frontend extraction/display and normalization in `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `vibecomfy/comfy_nodes/web/panel_thread.js`, `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`, and `vibecomfy/comfy_nodes/web/diagnostics_reporting.js` | `tests/browser/roundtrip_smoke.test.mjs`, `tests/browser/agent_edit_lifecycle.test.mjs`, `tests/browser/agent_edit_response_contract.test.mjs`, `tests/browser/panel_thread_rating.test.mjs`, `tests/browser/payload_contracts.test.mjs`, characterization fixtures under `tests/characterization/fixtures/agent_edit/` | Delete from normal render/lifecycle readers when `readFieldChanges()` is the only frontend accessor and rehydrate fixtures carry canonical outcome `changes`. Diagnostics/audit may retain read-only display support until historical audit entries age out. |
| `candidate_graph_hash` and graph-hash diagnostics | Session/diagnostics migration | `vibecomfy/comfy_nodes/agent/edit.py`, `vibecomfy/comfy_nodes/agent/session.py`, `vibecomfy/comfy_nodes/web/agent_status_poller.js`, `vibecomfy/comfy_nodes/web/panel_composer.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` | `tests/browser/payload_contracts.test.mjs`, `tests/browser/roundtrip_smoke.test.mjs`, `tests/fixtures/payload_contracts/chat_rehydrate_response.json` | This is a canonical diagnostic/hash field, not a legacy graph payload alias. Keep it where it identifies candidate artifacts; remove only from UI debug panels once a named `ApplyCandidate` projection supplies the same display value. |
| camelCase normalized fields (`applyAllowed`, `canvasApplyAllowed`, `auditRef`, `debugPayload`, `lastSubmitFieldChanges`) | Frontend view-model migration | Frontend state and tests only: `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `vibecomfy/comfy_nodes/web/panel_composer.js`, browser tests under `tests/browser/` | `tests/browser/agent_edit_lifecycle.test.mjs`, `tests/browser/agent_edit_lifecycle_transcript.test.mjs`, `tests/browser/roundtrip_smoke.test.mjs` | These are not wire aliases. Delete or rename only when canonical frontend selectors/view models replace panel state fields and tests no longer inspect reducer internals by camelCase name. |

## Expected Exceptions

### Normalizer Inference

`vibecomfy/comfy_nodes/web/agent_edit_response_contract.js` is the browser
compatibility boundary. It may infer public outcomes and candidate eligibility
from legacy aliases when `allowLegacy=true`. Tests may pass legacy-shaped input
to that file to prove old responses normalize, but new normal UI consumers
should not branch directly on raw legacy fields.

`vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js` is a
checked-in generated mirror. It documents canonical snake_case schemas and may
mention legacy input support only as a note pointing back to the handwritten
normalizer.

### Python Compatibility Adapter

Until the M1 backend adapter lands, legacy booleans and graph aliases still
appear in `routes.py`/`edit.py` assembly helpers. The target boundary is a named
adapter, `build_legacy_agent_edit_v1(canonical)`, with canonical payloads built
first and aliases stamped afterward. New backend work should move aliases toward
that adapter rather than copying inline stamping.

### Persisted And Session Rehydrate Fixtures

Persisted chat/session fixtures may carry aliases so old sessions remain
readable. Current fixture coverage is:

- `tests/fixtures/payload_contracts/chat_rehydrate_response.json`
- `tests/fixtures/e2e_sessions/**/session_state.json` and `turns/*/*.json`
- Browser rehydrate coverage in `tests/browser/agent_edit_lifecycle_transcript.test.mjs`
  and `tests/browser/roundtrip_smoke.test.mjs`

Deletion requires canonical rehydrate fixtures that pass through
`normalizeAgentEditResponse(..., { allowLegacy: false })` and preserve durable
turn identity, candidate eligibility, audit refs, and field changes.

### Audit And Debug Display

Audit/debug surfaces may display historical raw keys so operators can understand
old artifacts. This exception is limited to read-only display in:

- `vibecomfy/comfy_nodes/web/diagnostics_reporting.js`
- audit/history/debug rendering in `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`

These files should not use aliases to drive normal apply, lifecycle, or routing
behavior. They may show raw `field_changes`, `canvas_apply_allowed`, or
`queue_allowed` as diagnostic text until historical artifacts are migrated or
expired.

### Diagnostics Reporting

`diagnostics_reporting.js` may read `entry.field_changes` or
`raw.field_changes` only to compact audit/report text. It may also accept
camelCase display alternatives such as `changeDetails`; those are report view
models, not canonical wire fields. Delete this exception when diagnostics input
is emitted exclusively as canonical `change_details`/outcome `changes`.

### Tests

Tests may contain legacy aliases for three purposes:

1. Compatibility input tests for `agent_edit_response_contract.js`.
2. Rehydrate/persisted-session fixtures that model old durable data.
3. Negative assertions proving canonical output no longer carries the alias.

New test fixtures for canonical behavior should prefer snake_case canonical
payloads and set `allowLegacy=false` when the migration phase supports it.

## Verification Commands

Use these grep checks before changing this ledger:

```sh
rg -n "executor_pending|apply_allowed|canvas_apply_allowed|queue_allowed|apply_eligibility|candidate_graph|field_changes" \
  vibecomfy/comfy_nodes tests/browser tests/fixtures/payload_contracts tests/fixtures/e2e_sessions tests/characterization \
  -g '!*.png'
```

Expected non-test owners are the JS normalizer, generated contract mirror,
Python compatibility adapter or its pre-adapter assembly helpers, audit/debug
display, diagnostics reporting, and temporary frontend pending-message
reconciliation. Any new direct consumer in normal render/lifecycle code must
either be moved behind a selector/adapter or added here with coverage and a
deletion trigger.
