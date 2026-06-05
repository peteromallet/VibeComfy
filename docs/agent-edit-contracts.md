# Agent Edit Contracts

This note documents the implemented M1 contracts for edit-state baseline authority and Apply eligibility.

## 1. Edit-state baseline authority

Authority lives in [agent_session.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_session.py:162) through `_set_baseline_authoritatively()` and in [agent_session.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_session.py:238) through `_normalize_baseline_state()`. No other module should write baseline fields directly.

Authoritative baseline fields:

- `baseline_turn_id`: accepted turn id, or `null` after a rebaseline.
- `baseline_graph_hash`: current backend structural CAS hash.
- `baseline_graph_hash_kind`: current authority kind. Implemented flows now write `structural`.
- `baseline_graph_hash_version`: structural projection version used for `baseline_graph_hash`.
- `baseline_source`: `"none"`, `"turn"`, or `"rebaseline"`.
- `baseline_rebaseline_id`: current rebaseline id when `baseline_source == "rebaseline"`, else `null`.
- `baseline_graph_source_path`: source artifact used to heal projection drift. For accepts this is `turns/<turn_id>/candidate.ui.json`; for rebaseline this is `_rebaseline/<rebaseline_id>/graph.ui.json`.

Submit-time snapshots are captured in [agent_session.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_session.py:867) and read back through `_expected_baseline_for_turn()` in [agent_session.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_session.py:671). The persisted snapshot fields are:

- `submitted_baseline_graph_hash`
- `submitted_baseline_graph_hash_kind`
- `submitted_baseline_graph_hash_version`
- `submitted_baseline_source`
- `submitted_baseline_rebaseline_id`
- `submitted_baseline_turn_id`
- `submitted_baseline_graph_source_path`

CAS rules:

- Accept uses structural CAS only. The authoritative expected baseline comes from the submit snapshot or the fail-closed legacy derivation in `_expected_baseline_for_turn()`.
- Rebaseline uses structural CAS only. `rebaseline_session()` in [agent_session.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_session.py:1374) requires `last_known_baseline_graph_hash`, accepts explicit `null` for the no-baseline case, and rejects mismatches with `FailureKind.STALE_STATE_MISMATCH`.
- `client_live_canvas_token` is not backend CAS authority. It remains browser-local race evidence only.

Rebaseline reasons are declared in [agent_session.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_session.py:29):

- `undo`
- `stale_state_recovery`
- `continue_from_canvas`

Implemented rebaseline request shape for `POST /vibecomfy/agent-edit/rebaseline`:

```json
{
  "session_id": "session-123",
  "graph": { "nodes": [], "links": [] },
  "reason": "undo",
  "last_known_baseline_graph_hash": "abcd1234",
  "client_graph_hash": "optional-canonical-ui-hash",
  "client_structural_graph_hash": "optional-structural-hash",
  "idempotency_key": "rebaseline:session-123:undo:abcd1234:deadbeefcafe"
}
```

Implemented success response shape from `rebaseline_session()` plus route wiring in [routes.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/routes.py:186):

```json
{
  "ok": true,
  "action": "rebaseline",
  "session_id": "session-123",
  "baseline_turn_id": null,
  "baseline_graph_hash": "next-structural-hash",
  "baseline_graph_hash_kind": "structural",
  "baseline_graph_hash_version": 2,
  "baseline_source": "rebaseline",
  "baseline_rebaseline_id": "0001",
  "baseline_graph_source_path": "_rebaseline/0001/graph.ui.json",
  "previous_baseline_graph_hash": "prev-hash-or-null",
  "previous_baseline_graph_hash_kind": "structural",
  "expected_baseline_graph_hash": "prev-hash-or-null",
  "rebaseline_id": "0001",
  "reason": "undo",
  "client_graph_hash": "optional-canonical-ui-hash",
  "client_structural_graph_hash": "optional-structural-hash",
  "computed_structural_graph_hash": "next-structural-hash",
  "idempotency_key": "rebaseline:...",
  "canvas_apply_allowed": false,
  "apply_allowed": false,
  "queue_allowed": false,
  "apply_eligibility": {
    "applyable": false,
    "reason": "no_candidate",
    "message": "No candidate is available to apply.",
    "warnings": []
  },
  "audit_ref": {
    "path": ".../_rebaseline/0001/audit/audit.json"
  }
}
```

Rebaseline persistence and audit:

- Source graph artifact: `session/_rebaseline/<rebaseline_id>/graph.ui.json`
- Metadata artifact: `session/_rebaseline/<rebaseline_id>/metadata.json`
- Response artifact: `session/_rebaseline/<rebaseline_id>/response.json`
- Route-level audit artifact: `session/_rebaseline/<rebaseline_id>/audit/audit.json`

Recovery metadata for stale ingest is created in `_stale_rebaseline_recovery_issue()` in [agent_edit.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_edit.py:627) and promoted to the top-level failure response in `_failure_response()` in [agent_edit.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_edit.py:1768). Implemented wire shape:

```json
{
  "rebaseline_recovery": {
    "action": "rebaseline",
    "endpoint": "/vibecomfy/agent-edit/rebaseline",
    "reason": "stale_state_recovery",
    "last_known_baseline_graph_hash": "authoritative-structural-hash",
    "submit_graph_hash": "submit-ui-hash",
    "submit_structural_graph_hash": "submit-structural-hash",
    "client_graph_hash": "submitted-client-ui-hash",
    "client_structural_graph_hash": "submitted-client-structural-hash"
  }
}
```

## 2. Apply eligibility

The backend contract lives in `ApplyEligibility`, `derive_apply_eligibility()`, and `apply_eligibility_payload()` in [agent_contracts.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_contracts.py:63). `agent_gates.py` re-exports the derivation and includes it in `GateDerivation`.

Implemented `apply_eligibility.reason` enum:

- `applyable`
- `no_candidate`
- `not_latest`
- `superseded`
- `server_blocked`
- `stale_canvas`
- `queue_blocked_warning`

Semantics of `derive_apply_eligibility()`:

- `no_candidate`: no candidate exists.
- `not_latest`: caller asked about an older candidate.
- `superseded`: candidate state is terminal or no longer current.
- `stale_canvas`: live structural hash differs from the submitted structural baseline.
- `server_blocked`: backend apply gates failed.
- `queue_blocked_warning`: Apply is allowed but Queue is still blocked.
- `applyable`: Apply is allowed and Queue is also allowed.

Compatibility fields remain on responses:

- `canvas_apply_allowed`: backend apply-gate result.
- `apply_allowed`: mirrors `apply_eligibility.applyable`.
- `queue_allowed`: backend queue-gate result.

Response assembly points with `apply_eligibility`:

- Submit failures and submit successes in [agent_edit.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/agent_edit.py:1768)
- Accept, reject, and rebaseline route responses in [routes.py](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/routes.py:136)

Browser authority rule:

- The browser uses `applyEligibility(panel, liveCanvasSnapshot)` in [vibecomfy_roundtrip.js](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:1422).
- Structural authority comparison is `liveCanvasSnapshot.structuralHash` versus `panel.state.lastSubmit.client_structural_graph_hash`.
- `client_live_canvas_token` is only a local guard around async apply and rebaseline races. It is captured by `captureLiveCanvasToken()`, checked before local configure in the apply path, and never sent back as backend CAS authority.

Implemented browser-side rebaseline state fields in [vibecomfy_roundtrip.js](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:1736):

- `baselineTurnId`
- `baselineGraphHash`
- `baselineGraphHashKind`
- `baselineGraphHashVersion`
- `baselineSource`
- `baselineRebaselineId`
- `baselineGraphSourcePath`
- `rebaselinePending`
- `rebaselineRecovery`

The browser syncs those fields with `syncBaselineFromResponse()` in [vibecomfy_roundtrip.js](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:1300) and sends rebaseline requests with `postAgentRebaseline()` in [vibecomfy_roundtrip.js](/Users/peteromalley/Documents/.megaplan-worktrees/agent-edit-chat-platform/vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4788).
