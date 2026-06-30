# Agent Edit Contracts

This note documents the implemented M1 contracts for edit-state baseline authority and Apply eligibility.

## 1. Edit-state baseline authority

### 1.0 Protocol version branching

The `agent_edit_protocol` field on each turn record cleanly branches accept
behavior:

- **`v2_delta`** (V2): Accept uses **scoped delta-region validation**. Only the
  nodes, fields, and links referenced by `delta_ops` are compared between the
  submit-time graph and the live accept graph. Unrelated graph drift (e.g. a
  node added elsewhere on the canvas) does not block accept. Whole-graph
  structural CAS is computed as a diagnostic only and never gates V2 accept.
- **Legacy / absent** (V1): Accept uses the existing **whole-graph structural
  CAS** and submit-hash checks. These gates are preserved unchanged.

V1 candidates lack `delta_ops` and cannot be scoped; preserving their existing
gates avoids risk to legacy workflows.

### 1.1 Baseline authority

Authority lives in [agent_session.py](../../vibecomfy/comfy_nodes/agent/session.py) through `_set_baseline_authoritatively()` and in [agent_session.py](../../vibecomfy/comfy_nodes/agent/session.py) through `_normalize_baseline_state()`. No other module should write baseline fields directly.

Authoritative baseline fields:

- `baseline_turn_id`: accepted turn id, or `null` after a rebaseline.
- `baseline_graph_hash`: current backend structural CAS hash.
- `baseline_graph_hash_kind`: current authority kind. Implemented flows now write `structural`.
- `baseline_graph_hash_version`: structural projection version used for `baseline_graph_hash`.
- `baseline_source`: `"none"`, `"turn"`, or `"rebaseline"`.
- `baseline_rebaseline_id`: current rebaseline id when `baseline_source == "rebaseline"`, else `null`.
- `baseline_graph_source_path`: source artifact used to heal projection drift. For accepts this is `turns/<turn_id>/candidate.ui.json`; for rebaseline this is `_rebaseline/<rebaseline_id>/graph.ui.json`.

Submit-time snapshots are captured in [agent_session.py](../../vibecomfy/comfy_nodes/agent/session.py) and read back through `_expected_baseline_for_turn()` in [agent_session.py](../../vibecomfy/comfy_nodes/agent/session.py). The persisted snapshot fields are:

- `submitted_baseline_graph_hash`
- `submitted_baseline_graph_hash_kind`
- `submitted_baseline_graph_hash_version`
- `submitted_baseline_source`
- `submitted_baseline_rebaseline_id`
- `submitted_baseline_turn_id`
- `submitted_baseline_graph_source_path`

CAS rules:

- Accept uses structural CAS only. The authoritative expected baseline comes from the submit snapshot or the fail-closed legacy derivation in `_expected_baseline_for_turn()`.
- Accept requests send `live_graph` as the current serialized canvas snapshot. Submit and rebaseline continue using `graph`; accept does not reuse that field name.
- `submit_graph_hash` and `candidate_graph_hash` on accept identify the persisted submit snapshot and candidate snapshot for the turn. They are request-integrity echoes, not replacements for the live snapshot payload.
- Rebaseline uses structural CAS only. `rebaseline_session()` in [agent_session.py](../../vibecomfy/comfy_nodes/agent/session.py) requires `last_known_baseline_graph_hash`, accepts explicit `null` for the no-baseline case, and rejects mismatches with `FailureKind.STALE_STATE_MISMATCH`.
- `client_live_canvas_token` is not backend CAS authority. It remains browser-local race evidence only.

### V2 scoped accept (replaces whole-graph CAS for v2_delta turns)

When `agent_edit_protocol == "v2_delta"`, the accept gate uses **scoped
delta-region validation** instead of whole-graph structural CAS equality.

#### Touched region

The **touched region** is the set of nodes, fields, modes, link endpoints, and
ordering positions referenced by `delta_ops`. For each op, the backend resolves:

- `expected_old`: the value at that location in the **submit-time graph**
  (loaded from persisted `request.json`).
- `actual_before`: the value at that location in the **live graph** (the
  `live_graph` field sent with the accept request).
- `desired_new`: the mutation target value (from `delta_ops` or the candidate
  graph for add-node / link ops).

Only mismatches within the touched region cause accept rejection. Unrelated
nodes, fields, or links that changed elsewhere on the canvas are ignored.

#### Scoped validation plan (`_build_scoped_validation_plan`)

Each `delta_op` produces one validation entry:

| Field | Source | Description |
|---|---|---|
| `op` | `delta_op.op` | The op kind (`set_node_field`, `set_mode`, `reorder`, `upsert_link`, `remove_link`, `add_node`, `remove_node`). |
| `target` | `delta_op.target` or `delta_op.to` | Graph location path (e.g. `["nodes", "abc123", "widgets_values", 0]`). |
| `expected_old` | submit graph | Value resolved from the submit-time graph. |
| `actual_before` | live graph | Value resolved from the live graph sent with accept. |
| `desired_new` | candidate graph / delta_op | The mutation target value. |
| `status` | computed | One of `ok`, `conflict`, `noop`, `already_applied`, `already_absent`, `unscopable`. |
| `error` | string or null | Diagnostic message when status is `unscopable`. |

Acceptable statuses: `ok`, `noop`, `already_applied`, `already_absent`. An
`already_applied` status (live already equals desired) does not cause a
conflict. An `already_absent` status (remove_node target already gone) is
also acceptable.

#### No-op desired values

If `actual_before` (live) already equals `desired_new`, the entry status is
`already_applied`. This does **not** count as a conflict — the backend accepts
the turn because the desired state is already present on the canvas.

#### Evidence loading fail-closed

If the backend cannot load required V2 evidence (missing `submit_graph` from
`request.json`, missing `delta_ops` from `response.json`), accept **fails
closed** with `MISSING_REQUIRED_FIELD` / `evidence_loading_failure` diagnostics
and a `rebaseline_recovery` payload scoped to the turn.

If `live_graph` is absent from the accept request body, V2 accept fails closed
with `MISSING_REQUIRED_FIELD` before any evidence loading occurs.

#### Diagnostic whole-graph hash

Whole-graph structural CAS is still computed on the live graph but is used as a
**diagnostic only** for V2. When it mismatches, a `whole_graph_hash_mismatch`
diagnostic entry (severity: `info`) is appended to the response `diagnostics`
array. It never gates V2 accept.

#### Scoped conflict failure shape

When scoped validation finds conflicts, the backend returns a
`StaleStateMismatch` failure envelope with:

- `graph_unchanged: true`
- `queue_allowed: false`
- `agent_failure_context.issues[]` — one entry per conflicting op, each with
  `code` (`scoped_conflict` or `unscopable_delta_op`), `node_uid`, `field_path`,
  `expected_old`, `actual_before`, `status`, `message`, `detail`, and
  `rebaseline_recovery`.
- Top-level `rebaseline_recovery` with `reason: "scoped_accept_conflict"`.

#### V1 preservations

- V1 structural CAS and submit-hash checks remain blocking for non-v2_delta
  turns. No V1 gate was weakened.
- V1 candidates (lacking `delta_ops`) cannot reach the V2 scoped path.
- `client_live_canvas_token` remains browser-local race diagnostic only.

Rebaseline reasons are declared in [agent_session.py](../../vibecomfy/comfy_nodes/agent/session.py):

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

Implemented success response shape from `rebaseline_session()` plus route wiring in [routes.py](../../vibecomfy/comfy_nodes/agent/routes.py):

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

Recovery metadata for stale ingest is created in `_stale_rebaseline_recovery_issue()` in [agent_edit.py](../../vibecomfy/comfy_nodes/agent/edit.py) and promoted to the top-level failure response in `_failure_response()` in [agent_edit.py](../../vibecomfy/comfy_nodes/agent/edit.py). Implemented wire shape:

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

The backend contract lives in `ApplyEligibility`, `derive_apply_eligibility()`, and `apply_eligibility_payload()` in [agent_contracts.py](../../vibecomfy/comfy_nodes/agent/contracts.py). `agent_gates.py` re-exports the derivation and includes it in `GateDerivation`.

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

- Submit failures and submit successes in [agent_edit.py](../../vibecomfy/comfy_nodes/agent/edit.py)
- Accept, reject, and rebaseline route responses in [routes.py](../../vibecomfy/comfy_nodes/agent/routes.py)

Browser authority rule:

- The browser uses `applyEligibility(panel, liveCanvasSnapshot)` in [vibecomfy_roundtrip.js](../../vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js).
- Client-side structural hash comparison is a diagnostic parity check only (`liveCanvasSnapshot.structuralHash` versus `panel.state.lastSubmit.client_structural_graph_hash`). It is **not** Apply authority — backend CAS is the single Apply authority. `client_structural_graph_hash` is submitted as a backend-parity snapshot in submit/rebaseline payloads and is never used by the backend to decide Apply eligibility.
- `client_live_canvas_token` is only a local guard around async apply and rebaseline races. It is captured by `captureLiveCanvasToken()`, checked before local configure in the apply path, and never sent back as backend CAS authority.

### 2.1 Execution-plan enforcement handoff

Plan-backed turns keep the public payload boundary compatible: the executor
continues to pass the plan under
`execution_protocol_notes.execution_plan.plan`. At turn setup, [edit_entrypoint.py](../../vibecomfy/comfy_nodes/agent/edit_entrypoint.py)
hydrates that nested value into `AgentEditState.execution_plan`, persists
`turns/<turn_id>/execution_plan.json`, and later persists
`turns/<turn_id>/plan_evaluation.json` through [execution_plan_runtime.py](../../vibecomfy/comfy_nodes/agent/execution_plan_runtime.py).
No public top-level `execution_plan` field is introduced.

`plan_validate_ok` participates in the same gate system as the other backend
validation gates:

- In [contracts.py](../../vibecomfy/comfy_nodes/agent/contracts.py), `plan_validate_ok`
  is part of `DEFAULT_GATE_NAMES` and `CANVAS_APPLY_GATE_NAMES`.
- In [gates.py](../../vibecomfy/comfy_nodes/agent/gates.py),
  `update_plan_validate_gate()` marks the gate `true` when no execution plan
  exists, `false` when a plan-backed turn has not been evaluated, and equal to
  `PlanEvaluation.ok` once evaluation exists. Failed evidence includes the
  `plan_id`, `blocking`, failed condition ids, evaluator feedback, and
  `plan_evaluation_v1` contract version.
- For non-plan turns, this is pass-through compatibility. Existing direct,
  inspect, research, respond, and revise behavior is not made stricter merely
  because the new gate exists.

`done()` acceptance is also plan-backed. In [edit_batch_loop_finish.py](../../vibecomfy/comfy_nodes/agent/edit_batch_loop_finish.py),
a requested `done()` reevaluates the latest candidate graph when
`state.execution_plan` exists. If the resulting `PlanEvaluation` is
`ok: false` and `blocking: true`, `done()` is not accepted; the next model turn
receives compact refusal feedback with missing required step ids, failed
condition ids, the plan id, and evaluator feedback. Only a passing evaluation
allows `done()` to finish the batch.

Candidate payloads, task satisfaction, debug gates, and apply eligibility all
use the same `plan_validate_ok` result:

- [edit_response_contract.py](../../vibecomfy/comfy_nodes/agent/edit_response_contract.py)
  suppresses `candidate`, candidate aliases, `canvas_apply_allowed`, and
  applyability when a plan-backed evaluation fails or is missing.
- Successful plan evaluation keeps normal candidate payloads and records
  `execution_plan_status`, `execution_plan_feedback`, `artifacts.execution_plan`,
  `artifacts.plan_evaluation`, and `debug.execution_plan_artifacts`.
- `debug.gates.plan_validate_ok` mirrors the top-level `gates.plan_validate_ok`
  snapshot so failures are visible in both compatibility and typed envelopes.
- `task_satisfaction` receives a `"check": "execution_plan"` entry with
  `"satisfaction": "pass"` or `"fail"` and the failed condition ids.
- `apply_eligibility` remains derived from backend gates. A failed plan yields
  `reason: "no_candidate"` because no candidate is exposed. A passed plan can
  still yield `reason: "queue_blocked_warning"` if only Queue validation fails.

Queue blockers therefore remain warnings only after structural plan
completeness passes. If the plan does not structurally validate, Queue state
does not rescue the turn into applyability; the response has no candidate.

Operational boundaries for plan-backed turns:

- The only accepted inbound plan payload is nested under
  `execution_protocol_notes.execution_plan.plan`.
- Public responses expose compact status, feedback, artifacts, and debug refs;
  they do not expose the raw plan at top level.
- `plan_validate_ok` is `true` for non-plan turns, `false` for an unevaluated or
  failed plan-backed turn, and equal to `PlanEvaluation.ok` after evaluation.
- Failed plan validation suppresses candidate aliases (`candidate`,
  `candidate_graph`) and apply aliases (`canvas_apply_allowed`,
  `apply_allowed`) through the normal response contract.
- Compact plan feedback is prompt-scoped retry guidance. It belongs in active
  plan-backed execute-turn prompts and persisted model artifacts, not in
  unrelated follow-up prompts.
- Queue validation is anti-scope for plan semantics. Queue blockers can warn on
  a complete plan; they cannot make an incomplete plan applyable.

Failed HotShotXL sidecar example: adding an `ADE_AnimateDiffLoaderWithContext`
node beside `SaveImage` and calling `done()` does not satisfy the active video
path plan, because motion never reaches a video terminal.

`execution_plan_v1` input:

```json
{
  "contract_version": "execution_plan_v1",
  "plan_id": "hotshotxl-active-video-path",
  "goal": "HotShotXL/AnimateDiff nodes must feed a video terminal on the active output path, not sit in a sidecar branch.",
  "required_steps": [
    {
      "id": "add-animatediff-motion-node",
      "kind": "add_node",
      "criticality": "required",
      "status": "required",
      "class_type": "ADE_AnimateDiffLoaderWithContext"
    },
    {
      "id": "add-video-terminal",
      "kind": "add_node",
      "criticality": "required",
      "status": "required",
      "class_type": "VHS_VideoCombine"
    },
    {
      "id": "wire-motion-into-video-terminal",
      "kind": "wire_active_path",
      "criticality": "required",
      "status": "required",
      "conditions": [
        {
          "condition_id": "hotshotxl.motion_reaches_video_terminal",
          "kind": "terminal_consumes"
        }
      ]
    }
  ],
  "active_path_conditions": [
    {
      "condition_id": "hotshotxl.active_output_is_video",
      "kind": "terminal_class",
      "class_type": "VHS_VideoCombine"
    }
  ]
}
```

Blocking `plan_evaluation_v1` result:

```json
{
  "contract_version": "plan_evaluation_v1",
  "plan_id": "hotshotxl-active-video-path",
  "ok": false,
  "blocking": true,
  "failed_conditions": [
    {
      "condition_id": "add-video-terminal.required_class",
      "severity": "required",
      "message": "Required class VHS_VideoCombine is not present."
    },
    {
      "condition_id": "hotshotxl.motion_reaches_video_terminal",
      "severity": "required",
      "message": "AnimateDiff output does not feed the video terminal."
    },
    {
      "condition_id": "hotshotxl.active_output_is_video",
      "severity": "required",
      "message": "The active output path is still image-only."
    }
  ],
  "feedback": "plan evaluation failed: the HotShotXL motion branch is not wired into a video terminal."
}
```

Response effects for the failed example:

```json
{
  "candidate": null,
  "apply_allowed": false,
  "canvas_apply_allowed": false,
  "apply_eligibility": {
    "applyable": false,
    "reason": "no_candidate"
  },
  "gates": {
    "plan_validate_ok": false
  },
  "execution_plan_status": {
    "plan_id": "hotshotxl-active-video-path",
    "ok": false,
    "blocking": true,
    "failed_condition_ids": [
      "add-video-terminal.required_class",
      "hotshotxl.motion_reaches_video_terminal",
      "hotshotxl.active_output_is_video"
    ]
  },
  "debug": {
    "gates": {
      "plan_validate_ok": false
    },
    "execution_plan_artifacts": {
      "execution_plan": {
        "path": "turns/0001/execution_plan.json"
      },
      "plan_evaluation": {
        "path": "turns/0001/plan_evaluation.json"
      }
    }
  }
}
```

Passing HotShotXL example: the candidate adds
`ADE_AnimateDiffLoaderWithContext`, adds `VHS_VideoCombine`, and wires
`video.images` from the motion branch before calling `done()`.

Passing `plan_evaluation_v1` result:

```json
{
  "contract_version": "plan_evaluation_v1",
  "plan_id": "hotshotxl-active-video-path",
  "ok": true,
  "blocking": false,
  "failed_conditions": [],
  "feedback": "plan evaluation passed."
}
```

Response effects when only Queue validation still fails:

```json
{
  "candidate": {
    "state": "candidate"
  },
  "apply_allowed": true,
  "canvas_apply_allowed": true,
  "queue_allowed": false,
  "apply_eligibility": {
    "applyable": true,
    "reason": "queue_blocked_warning",
    "warnings": ["queue_blocked"]
  },
  "gates": {
    "plan_validate_ok": true,
    "queue_validate_ok": false
  },
  "execution_plan_status": {
    "plan_id": "hotshotxl-active-video-path",
    "ok": true,
    "blocking": false,
    "failed_condition_ids": []
  },
  "task_satisfaction": [
    {
      "check": "execution_plan",
      "satisfaction": "pass",
      "failed_condition_ids": []
    }
  ],
  "artifacts": {
    "execution_plan": "turns/0001/execution_plan.json",
    "plan_evaluation": "turns/0001/plan_evaluation.json"
  }
}
```

### 2.2 Extending precedent-backed plan patterns

New precedent-backed workflow families should reuse this handoff:

1. Route only normalized `adapt` decisions into plan construction.
2. Add builder fixtures and golden JSON for the new `ExecutionPlan`.
3. Add evaluator conditions or shared condition kinds for the semantic
   obligation.
4. Add runtime evidence for both a connected complete graph and a disconnected
   sidecar or incomplete graph.
5. Confirm public response compatibility: no top-level `execution_plan`,
   artifact refs present, `debug.gates.plan_validate_ok` present, failed plans
   non-applyable, and passed plans allowed to carry `queue_blocked_warning`.
6. Confirm simple local edit routes bypass planning and do not leak nested
   payloads.

Avoid new route-specific Apply enums or bespoke response fields. A new pattern
should only change builder evidence, plan fixture contents, evaluator
expectations, and tests around the shared `plan_validate_ok` gate.

Implemented browser-side rebaseline state fields in [vibecomfy_roundtrip.js](../../vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js):

- `baselineTurnId`
- `baselineGraphHash`
- `baselineGraphHashKind`
- `baselineGraphHashVersion`
- `baselineSource`
- `baselineRebaselineId`
- `baselineGraphSourcePath`
- `rebaselinePending`
- `rebaselineRecovery`

The browser syncs those fields with `syncBaselineFromResponse()` in [vibecomfy_roundtrip.js](../../vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js) and sends rebaseline requests with `postAgentRebaseline()` in [vibecomfy_roundtrip.js](../../vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js).

## 3. Typed TurnOutcome contract

The typed outcome model lives in `TurnOutcome` within [agent_contracts.py](../../vibecomfy/comfy_nodes/agent/contracts.py). Every turn produces exactly one `TurnOutcome` whose `kind` is one of the discriminants declared in `TURN_OUTCOME_KINDS`. The contract version is `agent_edit_turn_v2` (see `AGENT_EDIT_TURN_CONTRACT_VERSION`).

`TurnOutcome` constructors — `TurnOutcome.edit()`, `TurnOutcome.clarify()`, `TurnOutcome.edit_and_clarify()`, `TurnOutcome.noop()`, `TurnOutcome.budget()`, and `TurnOutcome.from_failure()` — enforce internal invariants: only `failure` may carry failure metadata, and only `edit` / `edit+clarify` may carry field changes. Serialization is via `TurnOutcome.to_dict()`.

### 3.1 `edit` outcome

An edit turn that produced two field changes (a widget value update and a title change on node `abc123`).

```json
{
  "kind": "edit",
  "changes": [
    {
      "uid": "abc123",
      "field_path": "widgets_values[0]",
      "old": 512,
      "new": 768
    },
    {
      "uid": "abc123",
      "field_path": "title",
      "old": "Old Title",
      "new": "New Title"
    }
  ]
}
```

Construction:

```python
from vibecomfy.porting.edit.types import FieldChange
from vibecomfy.comfy_nodes.agent_contracts import TurnOutcome

outcome = TurnOutcome.edit(
    changes=(
        FieldChange(uid="abc123", field_path="widgets_values[0]", old=512, new=768),
        FieldChange(uid="abc123", field_path="title", old="Old Title", new="New Title"),
    )
)
# outcome.to_dict() produces the JSON shape above
```

An edit with no landed field changes produces an empty `changes` list:

```json
{
  "kind": "edit",
  "changes": []
}
```

### 3.2 `clarify` outcome

A turn where the agent needs clarification before proceeding (no graph mutation occurred).

```json
{
  "kind": "clarify",
  "question": "Which resolution should I use for the upscale — 2x or 4x?"
}
```

Construction:

```python
outcome = TurnOutcome.clarify(question="Which resolution should I use for the upscale — 2x or 4x?")
```

A `clarify` outcome must not carry `changes` or any failure metadata — the constructor raises `ValueError` if any are provided.

### 3.3 `edit+clarify` outcome

A turn where some edits landed but the agent still needs additional input. The outcome carries both `changes` and a `question`.

```json
{
  "kind": "edit+clarify",
  "changes": [
    {
      "uid": "def456",
      "field_path": "widgets_values[0]",
      "old": "v1.5",
      "new": "v2.0"
    }
  ],
  "question": "I updated the checkpoint — should I also adjust the scheduler?"
}
```

Construction:

```python
outcome = TurnOutcome.edit_and_clarify(
    changes=(
        FieldChange(uid="def456", field_path="widgets_values[0]", old="v1.5", new="v2.0"),
    ),
    question="I updated the checkpoint — should I also adjust the scheduler?",
)
```

### 3.4 Failure, noop, and budget outcomes

These are documented for completeness but are separate from the edit/clarify surface.

**`failure`** — constructed via `TurnOutcome.from_failure(envelope)` or directly with all required failure fields. Serialized shape:

```json
{
  "kind": "failure",
  "failure_kind": "SyntaxError",
  "stage": "ingest",
  "retryable": true,
  "next_action": "wait and retry; agent should fix syntax",
  "graph_unchanged": true,
  "changes": []
}
```

**`noop`** — the agent deliberately produced no edits (e.g. "nothing to do").

```json
{
  "kind": "noop",
  "reason": "The graph already contains the requested nodes."
}
```

**`budget`** — the agent exhausted its batch budget without completing.

```json
{
  "kind": "budget",
  "reason": "Batch budget of 5 turns exhausted before completing the task."
}
```

## 4. Typed turn envelope

The product `batch_repl` response envelope is assembled by `turn_envelope()` in [agent_contracts.py](../../vibecomfy/comfy_nodes/agent/contracts.py) and by the batch response builders in [agent_edit.py](../../vibecomfy/comfy_nodes/agent/edit.py). The canonical typed shape is:

```json
{
  "contract_version": "agent_edit_turn_v2",
  "message": "Applied 1 edit. Gate A passed: updated the save prefix to after.",
  "outcome": {
    "kind": "edit",
    "changes": [
      {
        "uid": "2",
        "field_path": "filename_prefix",
        "old": null,
        "new": "after"
      }
    ]
  },
  "candidate": {
    "state": "candidate",
    "graph": { "nodes": [], "links": [] },
    "graph_hash": "candidate-ui-hash",
    "structural_graph_hash": "candidate-structural-hash",
    "baseline_graph_hash": "baseline-structural-hash-or-null",
    "submit_graph_hash": "submit-ui-hash",
    "submit_structural_graph_hash": "submit-structural-hash"
  },
  "eligibility": {
    "applyable": true,
    "reason": "applyable",
    "message": "Apply is allowed.",
    "warnings": []
  },
  "audit_ref": {
    "path": "out/editor_sessions/session-123/turns/0001/audit/audit.json"
  },
  "debug": {
    "gates": {
      "python_load_ok": true,
      "lower_ok": true,
      "ir_validate_ok": true,
      "ui_emit_ok": true,
      "ui_fidelity_ok": true,
      "ui_load_safe_ok": true,
      "queue_validate_ok": false,
      "state_match_ok": true
    },
    "hashes": {
      "baseline_graph_hash": "baseline-structural-hash-or-null",
      "submit_graph_hash": "submit-ui-hash",
      "submit_structural_graph_hash": "submit-structural-hash",
      "submitted_client_graph_hash": "submitted-client-ui-hash-or-null",
      "submitted_client_structural_graph_hash": "submitted-client-structural-hash-or-null",
      "candidate_graph_hash": "candidate-ui-hash",
      "candidate_structural_graph_hash": "candidate-structural-hash",
      "client_graph_hash": "submitted-client-ui-hash-or-null"
    },
    "batch_repl": {
      "turn_count": 2,
      "exit_mode": "done",
      "done_summary": "Gate A passed: updated the save prefix to after.",
      "final_summary": "Gate A passed: updated the save prefix to after.",
      "budget_state": {
        "max_batches": 4,
        "max_consecutive_errors": 2,
        "remaining_batches": 2,
        "remaining_consecutive_errors": 2,
        "consecutive_errors": 0
      }
    }
  }
}
```

Compatibility fields intentionally remain at the top level during M2:

- `graph`, `gates`, `report`, `artifacts`, and `batch_turns`
- hash fields such as `baseline_graph_hash`, `submit_graph_hash`, `submit_structural_graph_hash`, `candidate_graph_hash`, and `candidate_structural_graph_hash`
- apply booleans: `canvas_apply_allowed`, `apply_allowed`, and `queue_allowed`
- compatibility eligibility mirror: `apply_eligibility`
- clarify/no-op compatibility flags such as `clarification_required`, `graph_unchanged`, and `done_summary`

Rules for the split:

- `eligibility` is the canonical typed location for apply eligibility.
- `apply_eligibility` is a temporary compatibility mirror and must match `eligibility`.
- `debug.gates` is sourced from `context.gate_snapshot()`; the legacy top-level `gates` field remains for compatibility during M2.

Deprecation note:

- Compatibility fields stay in place through M2. Naming and timing for removal must be called out explicitly during the planned M4 UI migration, rather than being removed opportunistically in backend work.

## 5. Provider readiness

The canonical readiness contract is `agent_provider.readiness(route, model)` in [agent_provider.py](../../vibecomfy/comfy_nodes/agent/provider.py). All status routes and UI consumers must derive their availability signal from this single entry point. No caller should compute readiness independently.

### 5.1 Readiness payload shape

```json
{
  "ready": true,
  "reason": "Anthropic/OpenRouter credential resolved via local OAuth/API key.",
  "backend": "megaplan.agent.run_agent.AIAgent",
  "route": "anthropic",
  "model": "claude-opus-4-5",
  "base_url": null,
  "deepseek_key_present": false,
  "provider": "arnold",
  "provider_available": true,
  "contract_version": "agent_edit_turn_v2",
  "requested_route": "anthropic",
  "route_metadata": { "requested_route": "anthropic", "normalized_route": "anthropic" },
  "route_options": ["anthropic", "deepseek"],
  "credential_presence": {
    "arnold_api_key": true,
    "hermes_api_key": true,
    "deepseek_api_key": false
  },
  "legacy_deepseek_fallback_enabled": false
}
```

Key fields:

| Field | Meaning |
|-------|---------|
| `ready` | `true` when the provider can accept agent-edit turns; `false` when a credential or runtime is missing. This is the single authority for availability. |
| `reason` | Human-readable explanation of the readiness state. For unavailable states this is surfaced as the `error` field in status responses. |
| `provider_available` | Whether the Arnold runtime itself loaded successfully (distinct from credential readiness). |
| `contract_version` | Always `"agent_edit_turn_v2"` in product responses. |
| `credential_presence` | Boolean presence flags for each supported credential. Never contains secret values — only `true`/`false`. |
| `route_options` | Routes the browser may select from the provider dropdown. |

### 5.2 Readiness resolution flow

1. **Route/model resolution**: `_resolve_route_and_model()` normalizes the requested route (e.g. `"deepseek"` → `"deepseek"`, `None` → default `"anthropic"`) and selects the model from the explicit parameter or `VIBECOMFY_AGENT_MODEL`.

2. **Runtime load**: `_load_arnold_runtime()` is called exactly once. If it raises `ProviderError`, readiness returns `ready: false` immediately with the error as `reason`. The runtime is never re-imported inside a single readiness call.

3. **Delegate to runtime**: When the runtime loads, `agent_provider.readiness()` prefers `runtime.readiness(route, model)` if the runtime exposes that callable. This is the backend-local readiness path implemented in [runtime.py](../../vibecomfy/comfy_nodes/agent/runtime.py). If `readiness` is absent, it falls back to `runtime.get_agent_status(route, model)`.

4. **Normalize**: `_normalize_readiness_payload()` extracts `ready` (falling back to `ok` for legacy runtimes), picks a non-empty `reason` (falling back through `detail`, `error`, `message`, then a default), and strips all secret fields from the runtime payload via `_non_secret_mapping()` → `redact_closed_set()`.

5. **Merge metadata**: `_provider_status_metadata()` attaches route/model metadata, credential presence (booleans only), supported route options, and the contract version. These are provider-owned fields, never derived from runtime internals.

### 5.3 Secret redaction

`_non_secret_mapping()` passes the runtime payload through `redact_closed_set()`, which removes any keys matching known secret patterns (API key substrings, token fields, authorization headers). Credential presence is reported as boolean flags only — `credential_presence.arnold_api_key: true` confirms a key exists but never exposes its value. This guarantee holds for both the `available` and `unavailable` paths.

### 5.4 get_agent_status() — compatibility wrapper

`get_agent_status()` in [agent_provider.py](../../vibecomfy/comfy_nodes/agent/provider.py) is a thin compatibility wrapper around `readiness()`. It calls `readiness()`, derives `ok` strictly from `ready`, and adds legacy fields (`readiness: "ready" | "unavailable"`, `error` for unavailable-credential cases). Callers migrating to the typed contract should call `readiness()` directly.

### 5.5 Route integration

`_handle_agent_status()` in [routes.py](../../vibecomfy/comfy_nodes/agent/routes.py) calls `readiness()` directly, derives `ok` from `ready`, and reports one clear unavailable-credential reason via the `error` field. No independent readiness computation exists in the routes layer — the provider is the single source of truth.

### 5.6 Backend-local readiness

`runtime.readiness(route, model)` in [runtime.py](../../vibecomfy/comfy_nodes/agent/runtime.py) provides backend-specific readiness without importing `agent_provider`. It normalizes the route, resolves credentials directly (e.g. `DEEPSEEK_API_KEY` from environment or `~/.hermes/.env` for deepseek; Arnold OAuth/API key for anthropic), and returns `ready` with a descriptive `reason`. This keeps the dependency direction clean: the provider depends on the runtime, not vice versa.

## 6. Cancellation (deferred)

Cancellation is not implemented in M2. The M4 "Stop" button in the UI is dismiss-UI-only — it hides the agent panel client-side but does not interrupt a running turn, terminate a provider process, or produce a `cancelled` outcome.

### 6.1 Current behaviour

- Pressing "Stop" in the M4 UI removes the agent panel from the DOM and stops polling for results.
- The backend turn continues to execute to completion (or budget exhaustion).
- No `/cancel` endpoint exists. No process handle is stored.
- No `cancelled` outcome kind exists in `TurnOutcome`.

### 6.2 Required work for real cancellation

A future milestone (targeted after M4 UI migration) must add:

1. **`Popen` process management**: The agent provider must retain a `subprocess.Popen` handle (or equivalent) for each active turn so it can send a termination signal.

2. **Handle registry**: A session-scoped registry mapping `session_id` → active process handles, so the cancel handler can locate the right process.

3. **`/cancel` endpoint**: A new route (`POST /vibecomfy/agent-edit/cancel`) that accepts `session_id`, looks up the active handle, sends `SIGTERM` (or platform equivalent), and returns a cancellation acknowledgment.

4. **Cancelled outcomes**: A new `TurnOutcome.cancelled()` constructor and `"kind": "cancelled"` discriminant, with a `reason` field describing what was cancelled and when. Cancelled turns must produce a valid turn envelope with `outcome.kind == "cancelled"`, an empty `changes` list, and `graph_unchanged: true`.

### 6.3 Rationale for deferral

- M2 is scoped to typed result contracts, protocol collapse, and provider readiness — all synchronous, single-turn concerns.
- Process lifecycle management requires cross-cutting changes (provider state, route handlers, session cleanup) that would expand M2 beyond its contract-settling mandate.
- The M4 UI already has a client-side dismiss path; real cancellation becomes valuable once the UI migration settles and users can meaningfully interact with long-running turns.
- Naming and timing for cancellation must be called out explicitly during M4 UI migration planning, alongside compatibility field removal.

## 8. Iteration context contract

The batch-REPL provider iterates through multiple turns within a single submit, managed by `_stage_agent_batch_repl()` in [agent_edit.py](../../vibecomfy/comfy_nodes/agent/edit.py). Each turn is a full model round-trip through `run_agent_turn_batch()` in [agent_provider.py](../../vibecomfy/comfy_nodes/agent/provider.py).

### 8.1 Budget and loop guard

The iteration is bounded by two counters declared at the start of `_stage_agent_batch_repl()`:

- `max_batches`: maximum number of model round-trips (default from `state.batch_max_turns`, floor 1).
- `max_consecutive_errors`: maximum tolerable consecutive error turns before the loop breaks (default from `state.batch_max_consecutive_errors`, floor 1).

The loop tracks `consecutive_errors` (reset to 0 on a successful turn) and `total_landed` (cumulative count of landed ops across all turns). Budget state is written into `state.batch_budget_state` after every turn with the keys `max_batches`, `max_consecutive_errors`, `remaining_batches`, `remaining_consecutive_errors`, and `consecutive_errors`.

If `consecutive_errors >= max_consecutive_errors`, the loop breaks immediately and exits with `batch_exit_mode = "budget"` (see §8.3).

### 8.2 Turn iteration

The loop runs `for turn_number in range(max_batches)` with the following per-turn invariants:

1. **Message construction**: `build_batch_messages()` in [agent_provider.py](../../vibecomfy/comfy_nodes/agent/provider.py) builds a `[system, user]` message pair. Turn 0 always includes the full Python render, typed signatures, available node names, the node-variable index, budget, and (when provided) a compact "Recent conversation" block. Later turns include the node-variable index on every iteration; the full render is re-included only when the previous turn landed zero ops (a no-edit search/report turn). All turns include `previous_model_message` (the model's own prose from the prior turn), a diff block, and a teaching report when available.

2. **Model call**: `run_agent_turn_batch()` calls the Arnold/Hermes runtime with the prepared messages. Internally it retries up to 3 times on `MalformedModelJSON` (empty or no-fence responses), appending `_BATCH_RETRY_NUDGE` as an additional system message on retries 1 and 2. `AuthError` and `TimeoutError` are re-raised immediately; `ProviderError` and `MissingRequiredField` are raised without retry.

3. **Batch fencing**: `extract_batch_fence()` in [agent_provider.py](../../vibecomfy/comfy_nodes/agent/provider.py) enforces exactly one ` ```batch ` fenced block per response. Zero or multiple fences raise `MalformedModelJSON`. The prose outside the fence becomes the user-visible agent message.

4. **Clarify split**: `split_terminal_clarify()` detects a `clarify("...")` call within the batch code. When present, the clarify message is extracted and the remaining batch code (if any) is executed. If only a `clarify()` call exists with no editable batch, the loop exits immediately (see §8.3).

5. **Batch application**: `session.apply_batch(editable_batch)` applies the fenced code to the in-memory EditSession. It returns a `BatchResult` with `ok`, `diagnostics`, `statements`, `landed_ops`, and `field_changes`.

6. **State update**: After each turn the loop writes `state.python_after`, `state.ui_payload`, `state.batch_turn_count`, `state.batch_budget_state`, appends a `turn_record` to `state.batch_turns`, and persists the model request/response artifacts.

### 8.3 Exit modes

The batch loop exits through one of five modes stored in `state.batch_exit_mode`:

| Mode | Constant | Trigger |
|------|----------|---------|
| `done` | `_BATCH_EXIT_DONE` | `done()` call accepted; at least one edit landed. |
| `noop` | `_BATCH_EXIT_NOOP` | `done()` call accepted; zero edits ever landed. |
| `pure_clarify` | `_BATCH_EXIT_PURE_CLARIFY` | `clarify()` call with no batch code and no prior landed edits. |
| `edit_clarify` | `_BATCH_EXIT_EDIT_CLARIFY` | `clarify()` call with prior landed edits (or with batch code that also landed). |
| `budget` | `_BATCH_EXIT_BUDGET` | Loop exhausted `max_batches` or `max_consecutive_errors`. |

### 8.4 `done()` refusal

The loop does **not** blindly honor a `done()` call. Two refusal cases are enforced, each bounded to at most 2 nudges so a genuine no-change request still commits:

1. **No-edit done** (`total_landed == 0` and `done_noop_nudges < 2`): The model called `done()` but nothing ever landed. The loop sends a hint instructing the model to construct/wire nodes or confirm the no-change intent with a second `done()`.

2. **Error-before-done** (`turn_has_errors` and `done_error_nudges < 2`): Some statements in the current batch failed to land. The loop sends a hint with the diagnostic details and forces one more turn so the model can fix the failed statements.

When `done()` is refused, `last_report` is amended with the refusal hint and `continue` restarts the loop without counting the turn as done.

### 8.5 Conversation context injection

On turn 0 only, `build_batch_messages()` injects a "Recent conversation" block derived from `conversation_messages` (passed through from the submit route). Each message is compacted to `Role: text` with a 200-character truncation limit. Compact change annotations (`[op_kind | ...]`) are appended when the message carries 3 or fewer changes. This block is placed before "User request:" in the turn-0 user message.

### 8.6 Provider retry contract

`run_agent_turn_batch()` in [agent_provider.py](../../vibecomfy/comfy_nodes/agent/provider.py) implements exactly 3 attempts (1 initial + 2 retries). On retries 1 and 2:

- `_BATCH_RETRY_NUDGE` is appended as an additional system message.
- `audit_metadata` records `batch_repl_retry` with `count` and `reason`.
- After all 3 attempts fail, the last `MalformedModelJSON` is raised.

`AuthError` (permission denied) and `TimeoutError` are never retried. `ProviderError` and `MissingRequiredField` are never retried.
