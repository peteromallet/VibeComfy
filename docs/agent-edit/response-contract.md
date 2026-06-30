# Agent Edit Response Contract

This document describes the **typed response contract** that governs every agent-edit API
response crossing the server→browser boundary.  It is the single source of truth for the
public outcome union, kind-specific fields, legacy/internal mapping rules, wire shape
versus client shape, recovery payloads, and `/chat` rehydration rules.

---

## 1. Public outcome union

Every agent-edit response carries an `outcome` object whose `kind` field is exactly one of:

| Kind        | Meaning                                                         |
|-------------|-----------------------------------------------------------------|
| `candidate` | A candidate graph edit was produced and is ready for review.    |
| `noop`      | The turn produced no change (no‑op).                            |
| `clarify`   | The agent needs clarification before it can proceed.            |
| `error`     | A recoverable or non‑recoverable failure occurred.              |

These four values constitute the **public union**.  No other `outcome.kind` value may
leave the server.  Both the server‑side contract gate (`ensure_agent_edit_response_contract`
in `agent_contracts.py`) and the browser boundary module
(`agent_edit_response_contract.js`) enforce this closed set.

---

## 2. Kind‑specific fields

### 2.1 `candidate`

```json
{
  "kind": "candidate",
  "changes": [{"uid": "n1", "field_path": "steps", "old": 20, "new": 30}],
  "question": "Would you also like me to adjust the CFG scale?",
  "clarification": {"message": "Would you also like me to adjust the CFG scale?"}
}
```

- `changes` (array, always present): the field‑change list from the edit turn.
  Empty array when no field changes were produced (e.g. budget‑exhausted candidate).
- `question` / `clarification` (optional, present only for `edit+clarify` internally):
  the agent's clarifying question embedded alongside the candidate.

### 2.2 `noop`

```json
{
  "kind": "noop",
  "reason": "The graph is already in the requested state."
}
```

- `reason` (optional string): human‑readable explanation of why no change was made.

### 2.3 `clarify`

```json
{
  "kind": "clarify",
  "question": "Which model resolution would you prefer?",
  "clarification": {"message": "Which model resolution would you prefer?"}
}
```

- `question` (string): the clarifying question from the agent.
- `clarification.message` (string): same text, in a nested object for consumer convenience.

### 2.4 `error`

```json
{
  "kind": "error",
  "failure_kind": "StaleStateMismatch",
  "stage": "accept",
  "retryable": false,
  "next_action": "resubmit from the current canvas",
  "graph_unchanged": true,
  "agent_failure_context": {
    "explanation": "The submitted graph no longer matches the current canvas. Resubmit.",
    "issues": [{"code": "stale_state_mismatch", "detail": "…"}]
  },
  "rebaseline_recovery": {
    "action": "rebaseline",
    "endpoint": "/vibecomfy/agent-edit/rebaseline",
    "reason": "stale_state_recovery"
  }
}
```

- `failure_kind` (string): the `FailureKind` enum value (e.g. `"StaleStateMismatch"`).
- `stage` (string): the pipeline stage where the failure occurred.
- `retryable` (boolean | null): whether the same request can be retried.
- `next_action` (string | null): recommended user or agent action.
- `graph_unchanged` (boolean | null): whether the server graph was unchanged.
- `agent_failure_context` (object, optional): structured diagnostic context including
  `explanation` and optionally `issues`.
- `rebaseline_recovery` (object, optional): recovery descriptor (see §5).

---

## 3. Legacy / internal kind mapping

The server uses **internal** outcome kinds internally (`edit`, `edit+clarify`, `failure`,
`budget`, `noop`, `clarify`) but normalizes them to the four public kinds before any
response leaves the server.  The mapping is:

| Internal kind    | Public kind   | Notes                                                                 |
|------------------|---------------|-----------------------------------------------------------------------|
| `edit`           | `candidate`   | Field changes carried forward as `changes`.                           |
| `edit+clarify`   | `candidate`   | Field changes + clarifying question attached.                         |
| `clarify`        | `clarify`     | Direct pass‑through.                                                  |
| `noop`           | `noop`        | Direct pass‑through.                                                  |
| `failure`        | `error`       | Failure metadata promoted to error outcome fields.                     |
| `budget`         | `candidate`   | When a candidate graph payload is present; `budget_exhausted: true`.  |
| `budget`         | `noop`        | When no candidate graph payload is present; `budget_exhausted: true`. |

The normalization entry points are:

- **Server:** `public_outcome_from_turn_outcome()` and
  `ensure_agent_edit_response_contract()` in `agent_contracts.py`.  The latter is the
  gate called by all route handlers (`_validated_success_response`,
  `_validated_failure_response`, `_handle_agent_edit`).
- **Browser:** `normalizePublicOutcome()` in `agent_edit_response_contract.js`.  The
  browser boundary also handles **legacy direct‑response inference** for server responses
  that arrive without an explicit `outcome` object (see §8).

---

## 4. Wire shape versus client shape

### 4.1 Wire: `snake_case`

The HTTP wire payloads use `snake_case` field names exclusively.  This is the canonical,
backward‑compatible format.  Examples:

```
outcome.rebaseline_recovery
candidate_graph_hash
apply_allowed
graph_unchanged
agent_failure_context
```

### 4.2 Client: `camelCase`

The browser boundary module (`agent_edit_response_contract.js`) normalizes every response
immediately after `res.json()` via `normalizeAgentEditResponse()`.  The normalized result
exposes **only camelCase** fields for consumer code:

```
outcome.rebaselineRecovery
candidateGraphHash
applyAllowed
graphUnchanged
agentFailureContext
```

The original `snake_case` raw payload is preserved on `normalized.raw` for debug paths
only.  No consumer outside the boundary module should read `snake_case` fields directly.

### 4.3 Normalization idempotency

The normalized object carries an internal marker (`__agentEditResponseNormalized`) so
that passing an already‑normalized response through the function again is a no‑op.

### 4.4 Accept request wire fields

`POST /vibecomfy/agent-edit/accept` uses a distinct request body from submit and
rebaseline:

```json
{
  "session_id": "session-123",
  "turn_id": "0007",
  "client_graph_hash": "live-ui-hash",
  "live_graph": {"nodes": [], "links": []},
  "client_live_canvas_token": "live:rev:7",
  "submit_graph_hash": "submit-ui-hash",
  "candidate_graph_hash": "candidate-ui-hash",
  "idempotency_key": "accept:session-123:0007:..."
}
```

- `live_graph` is the current serialized canvas snapshot captured immediately before
  Apply. It is reserved for accept-stage live-canvas evidence.
- `graph` remains the submit/rebaseline field. Accept does not redefine `graph` to
  mean the live snapshot.
- `submit_graph_hash` identifies the submit-time canvas snapshot persisted for the turn.
- `candidate_graph_hash` identifies the candidate snapshot being accepted.
- `client_live_canvas_token` is diagnostic race evidence only. It helps explain local
  drift but is not backend CAS authority.

#### 4.4.1 V2 scoped accept response fields

When the accepted turn carries `agent_edit_protocol == "v2_delta"`, the accept
success response includes two additional payload fields:

```json
{
  "ok": true,
  "action": "accept",
  "scoped_accept_verification": {
    "ok": true,
    "entries": [
      {
        "op": "set_node_field",
        "target": ["nodes", "abc123", "widgets_values", 0],
        "expected_old": "a cat sitting",
        "actual_before": "a cat sitting",
        "desired_new": "a dog running",
        "status": "ok",
        "error": null
      }
    ]
  },
  "delta_ops": [
    {
      "op": "set_node_field",
      "target": ["nodes", "abc123", "widgets_values", 0],
      "value": "a dog running"
    }
  ]
}
```

- `scoped_accept_verification.ok` — `true` when all entries have status `ok`,
  `noop`, `already_applied`, or `already_absent`. The backend accepted the turn.
- `scoped_accept_verification.entries[]` — one entry per `delta_op`. Each entry
  carries `op`, `target`, `expected_old` (value resolved from the submit-time
  graph), `actual_before` (value resolved from the live graph sent with the
  accept request), `desired_new` (the mutation target), `status` (one of `ok`,
  `conflict`, `noop`, `already_applied`, `already_absent`, `unscopable`), and
  optional `error`.
- `delta_ops` — echoed from the submit response. Always a plain array of dicts
  with at minimum `op` and `target`. This is the **authoritative mutation-intent
  source** for V2. The browser uses this (or `panel.state.deltaOps` from the
  submit response) to drive local canvas mutation.
- Repeated (idempotent) accept returns stable `scoped_accept_verification` and
  `delta_ops` payloads.

#### 4.4.2 V2 scoped accept failure: scoped conflict fields

When V2 scoped validation fails, the failure response carries structured
`agent_failure_context.issues[]` entries describing each conflict:

```json
{
  "kind": "error",
  "failure_kind": "StaleStateMismatch",
  "stage": "accept",
  "retryable": true,
  "graph_unchanged": true,
  "queue_allowed": false,
  "agent_failure_context": {
    "explanation": "Scoped accept verification failed.",
    "issues": [
      {
        "code": "scoped_conflict",
        "node_uid": "abc123",
        "field_path": "widgets_values[0]",
        "expected_old": "a cat sitting",
        "actual_before": "a dog running",
        "status": "conflict",
        "message": "Scoped accept verification failed for set_node_field because live state was conflict.",
        "detail": "Scoped accept verification failed for set_node_field because live state was conflict.",
        "rebaseline_recovery": {
          "action": "rebaseline",
          "endpoint": "/vibecomfy/agent-edit/rebaseline",
          "reason": "scoped_accept_conflict",
          "turn_id": "0007",
          "submit_graph_hash": "submit-ui-hash",
          "candidate_graph_hash": "candidate-ui-hash"
        }
      }
    ]
  },
  "rebaseline_recovery": {
    "action": "rebaseline",
    "endpoint": "/vibecomfy/agent-edit/rebaseline",
    "reason": "scoped_accept_conflict",
    "turn_id": "0007",
    "submit_graph_hash": "submit-ui-hash",
    "candidate_graph_hash": "candidate-ui-hash"
  }
}
```

Each scoped-conflict issue carries:
- `code`: `"scoped_conflict"` for live-state drift, `"unsupported_delta_op"` or
  `"unscopable_delta_op"` for unresolvable ops.
- `node_uid` / `field_path`: the specific node and field that drifted.
- `expected_old`: the value the submit-time graph had at submit time.
- `actual_before`: the value the live graph now has.
- `status`: `"conflict"` for drift, `"unscopable"` for unresolvable ops.
- `rebaseline_recovery`: a recovery descriptor scoped to the turn (reason:
  `"scoped_accept_conflict"`). The top-level `rebaseline_recovery` carries the
  same shape for symmetric stale-recovery handling.

Unrelated whole-graph drift (e.g. a node added or removed elsewhere on the
canvas) does **not** cause a scoped accept failure. That drift appears only as a
diagnostic `whole_graph_hash_mismatch` entry in `action_diagnostics` (see §4.4.3).

#### 4.4.3 V2 diagnostic whole-graph hashes

The V2 accept path computes whole-graph structural CAS on the live graph as a
**diagnostic only** (it never blocks V2 accept):

```json
{
  "diagnostics": [
    {
      "code": "whole_graph_hash_mismatch",
      "severity": "info",
      "message": "Whole-graph structural CAS mismatched at accept time; v2 used scoped validation instead.",
      "detail": {
        "expected_baseline_graph_hash": "...",
        "live_graph_structural_hash": "...",
        "submit_graph_hash": "...",
        "candidate_graph_hash": "..."
      }
    }
  ]
}
```

This diagnostic confirms that whole-graph CAS would have rejected the accept
under V1 rules, but the scoped validation allowed it because the **touched
region** (the specific nodes, fields, and links referenced by `delta_ops`) was
unchanged.

#### 4.4.4 Source-of-truth split for V2

| Artifact | Role |
|---|---|
| `submit_graph` (persisted, loaded from `request.json`) | Source of truth for `expected_old` — the value at submit time. |
| `live_graph` (sent in accept request body) | Source of truth for `actual_before` — the value at accept time. |
| `delta_ops` (persisted in `response.json`, echoed in accept success) | Authoritative mutation intent. The browser's primary mutation source is `panel.state.deltaOps` (populated from the submit response); the accept echo is a stable copy. |
| `scoped_accept_verification` | Evidence of backend validation, not mutation intent. The browser uses it for pre-apply local precondition recheck. |
| Whole-graph structural CAS | Diagnostic only for V2. Does not gate V2 accept. |
| `client_live_canvas_token` | Browser-local race diagnostic only. Never backend CAS authority. |

---

## 5. Execution-plan response fields

Plan-backed agent-edit responses preserve the public outcome union. They add
compact plan evidence fields, but never a public top-level `execution_plan`
payload.

Inbound plan boundary:

```json
{
  "execution_protocol_notes": {
    "execution_plan": {
      "plan": {"contract_version": "execution_plan_v1"}
    }
  }
}
```

Public response boundary:

```json
{
  "outcome": {"kind": "candidate"},
  "execution_plan_status": {
    "plan_id": "plan.hotshotxl_8f.example",
    "ok": true,
    "blocking": false,
    "failed_condition_ids": []
  },
  "execution_plan_feedback": "plan evaluation passed.",
  "gates": {"plan_validate_ok": true},
  "debug": {
    "gates": {"plan_validate_ok": true},
    "execution_plan_artifacts": {
      "execution_plan": {
        "path": "turns/0001/execution_plan.json",
        "sha256": "sha256:...",
        "byte_count": 1234
      },
      "plan_evaluation": {
        "path": "turns/0001/plan_evaluation.json",
        "sha256": "sha256:...",
        "byte_count": 567
      }
    }
  },
  "artifacts": {
    "execution_plan": "turns/0001/execution_plan.json",
    "plan_evaluation": "turns/0001/plan_evaluation.json"
  },
  "task_satisfaction": [
    {
      "check": "execution_plan",
      "satisfaction": "pass",
      "failed_condition_ids": []
    }
  ]
}
```

Failure response effects:

- `execution_plan_status.ok` is `false` and `blocking` is `true` for blocking
  semantic misses.
- `execution_plan_feedback` is compact and actionable, including failed
  condition ids and evaluator feedback.
- `candidate`, `candidate_graph`, `canvas_apply_allowed`, and `apply_allowed`
  are suppressed or false through the existing compatibility aliases.
- `apply_eligibility.reason` is `no_candidate`.
- `debug.gates.plan_validate_ok` mirrors `gates.plan_validate_ok`.
- artifact refs remain present so the failure can be audited.

Passing-plan response effects:

- candidate and candidate-graph aliases remain available.
- `apply_eligibility.reason` may be `applyable` or `queue_blocked_warning`.
- `queue_blocked_warning` does not alter plan semantics; it only means Apply is
  allowed while Queue remains blocked by the separate queue-validation layer.

The browser boundary normalizes these fields like any other response field:
snake_case on the wire, camelCase after `normalizeAgentEditResponse()`. Consumer
code should read compact status and artifact refs, not raw nested executor
notes.

---

## 6. Recovery payload shape

When a failure outcome carries recovery information (e.g. a stale‑state mismatch), the
`rebaseline_recovery` / `rebaselineRecovery` descriptor is extracted from one of several
supported positions:

| Priority | Position (wire)                          | Position (normalized)             |
|----------|------------------------------------------|-----------------------------------|
| 1        | `rebaseline_recovery` (top‑level)        | `rebaselineRecovery` (top‑level)  |
| 2        | `outcome.rebaseline_recovery`            | `outcome.rebaselineRecovery`      |
| 3        | `agent_failure_context.issues[].rebaseline_recovery` | (nested in agentFailureContext) |
| 4        | `debug.failure.agent_failure_context.issues[].rebaseline_recovery` | (deeply nested) |

The recovery descriptor shape (both wire and normalized) is:

```json
{
  "action": "rebaseline",
  "endpoint": "/vibecomfy/agent-edit/rebaseline",
  "reason": "stale_state_recovery",
  "last_known_baseline_graph_hash": "abc123",
  "submit_graph_hash": "def456",
  "submit_structural_graph_hash": "ghi789",
  "client_graph_hash": "jkl012",
  "client_structural_graph_hash": "mno345"
}
```

Hash fields accept both `snake_case` and `camelCase` inputs and are normalized to
camelCase on output.  The recovery object is always compacted (null/undefined keys
removed).

### Server‑side accept‑stage promotion

For accept‑stage `StaleStateMismatch` failures, the server **promotes** or synthesizes a
`rebaseline_recovery` descriptor before contract validation (`_promote_accept_rebaseline_recovery`
in `routes.py`).  This ensures accept‑stage and submit‑stage stale failures carry
symmetric recovery shapes.

---

## 7. `/chat` endpoint rules

The `GET /vibecomfy/agent-edit/chat` endpoint returns a rehydrated conversation history
with three outcome‑bearing surfaces:

### 7.1 Top‑level `outcome`

The chat response itself carries an `outcome` (always `noop` on success, `error` on
failure) validated through `_validated_success_response` / `_validated_failure_response`.

### 7.2 `messages[].outcome` (agent messages only)

Every agent‑role message in the `messages` array carries a normalized `outcome`:

- **When `chat.json` exists:** the outcome recorded in `chat.json` for that message is
  read and passed through `_stamped_message_outcome()` which normalizes it via
  `ensure_agent_edit_response_contract`.  This is the authoritative source.
- **When `chat.json` is absent (fallback):** the server constructs a fallback chat
  record from `request.json` + `response.json` and stamps the fallback agent message with
  the turn's derived outcome via `_stamped_turn_response_outcome()`.
- **User‑role messages never carry an `outcome`.**

Only public kinds (`candidate`, `noop`, `clarify`, `error`) appear.

### 7.3 `latest_candidate.outcome`

The `latest_candidate` object (see `_latest_session_candidate_payload`) contains an
`outcome` field derived via `_stamped_turn_response_outcome()`:

- Only turns in `"candidate"` state with a public `candidate` outcome **and** a graph
  payload are eligible for restoration.
- The outcome is the server‑stamped public outcome — the browser should **not**
  re‑infer the outcome from the raw `latest_candidate` fields.

### 7.4 Browser normalization

On the browser side, `normalizeAgentEditResponse()` is applied to the chat payload
immediately after `res.json()`.  The `latest_candidate` sub‑object is recursively
normalized.  Messages carry their outcomes already server‑stamped; the boundary module
applies `normalizeMessage()` which normalizes each message's `response` and `outcome`
through the same contract gate.

---

## 8. Server vs. browser normalization responsibilities

### 8.1 Server responsibilities

- **Authoritative stamping.**  The server `ensure_agent_edit_response_contract()` is the
  canonical gate for all endpoint responses (submit, accept, reject, rebaseline, chat).
- **`/chat` embedded outcomes.**  The server stamps public outcomes on every derivable
  agent message in the chat history **before** the response leaves the server.
- **`latest_candidate` eligibility.**  The server derives and stamps the public outcome,
  then uses it to gate restore eligibility (only `candidate` outcomes with a graph).
- **Closed‑set enforcement.**  The server rejects any response whose `outcome.kind` is
  not in the public union.

### 8.2 Browser responsibilities

- **Normalization boundary.**  The browser applies `normalizeAgentEditResponse()`
  immediately after `res.json()` at every fetch call site.  Only the normalized payload
  flows to consumer code.
- **Legacy inference.**  For responses that arrive without an explicit `outcome` (e.g.
  older server versions), the browser boundary performs **legacy direct‑response
  inference** in `inferLegacyOutcome()` to classify the response as `candidate`, `noop`,
  `clarify`, or `error`.  This is the **only** place legacy inference lives — all
  consumer code reads the normalized `outcome.kind` exclusively.
- **CamelCase translation.**  The boundary converts all `snake_case` fields to
  `camelCase` so consumer code never touches wire‑format field names.
- **Recovery extraction.**  The boundary module is the single source for
  `rebaselineRecovery` extraction across all supported positions.  No consumer should
  walk raw payload fields to find recovery data.

### 8.3 Single inference per code path

Each response path (server endpoint → wire → browser `fetch` → boundary normalization →
consumer) performs outcome classification **at most once**:

- **Server‑stamped path:** the server classifies, the browser normalizes (pass‑through
  for public kinds).
- **Legacy path:** the server omits an explicit outcome, the browser infers it once in
  the boundary module.

There is no second inference in consumer code.  Legacy inference helpers
(`resultLooksLikeNoopResponse`, `candidateGraphFromResult`, `outcomeFromResult`,
`eligibilityFromResult`, `adaptTypedResponse`) have been removed from
`vibecomfy_roundtrip.js` and exist only inside `agent_edit_response_contract.js` where
they serve the boundary‑only legacy path.

---

## 9. Reference: server contract functions

| Function                                   | Location              | Role                                           |
|--------------------------------------------|-----------------------|------------------------------------------------|
| `ensure_agent_edit_response_contract()`    | `agent_contracts.py`  | Canonical response gate for all endpoints.     |
| `public_outcome_from_turn_outcome()`       | `agent_contracts.py`  | Maps internal `TurnOutcome` to public outcome. |
| `_public_error_outcome_from_response()`    | `agent_contracts.py`  | Constructs public `error` outcome from failure. |
| `_stamped_turn_response_outcome()`         | `agent_edit.py`       | Stamps a public outcome from a persisted turn. |
| `_stamped_message_outcome()`               | `agent_edit.py`       | Normalizes chat.json message outcomes.         |
| `_latest_session_candidate_payload()`      | `agent_edit.py`       | Builds `latest_candidate` with stamped outcome. |
| `read_session_chat()`                      | `agent_edit.py`       | Rehydrates chat history with stamped outcomes. |
| `_validated_success_response()`            | `routes.py`           | Wraps success payloads through contract gate.  |
| `_validated_failure_response()`            | `routes.py`           | Wraps failure payloads through contract gate.  |
| `_promote_accept_rebaseline_recovery()`    | `routes.py`           | Accept‑stage recovery symmetry.                |

## 10. Reference: browser contract functions

| Function / Export                         | Location                            | Role                                              |
|-------------------------------------------|-------------------------------------|---------------------------------------------------|
| `normalizeAgentEditResponse()`            | `agent_edit_response_contract.js`   | Main boundary: normalizes wire → client shape.    |
| `normalizePublicOutcome()`                | (internal)                          | Maps internal/legacy kinds to public union.       |
| `inferLegacyOutcome()`                    | (internal)                          | Classifies legacy no‑outcome responses.           |
| `extractRebaselineRecovery()`             | (exported)                          | Extracts recovery from all supported positions.   |
| `normalizeRebaselineRecovery()`           | (exported)                          | Normalizes recovery field names to camelCase.     |
| `readOutcome()`                           | (exported)                          | Convenience: normalize + return outcome.          |
| `readCandidate()`                         | (exported)                          | Convenience: normalize + return candidate.        |
| `readCandidateGraph()`                    | (exported)                          | Convenience: normalize + return candidateGraph.   |
| `readEligibility()`                       | (exported)                          | Convenience: normalize + return eligibility.      |
| `readRebaselineRecovery()`                | (exported)                          | Convenience: normalize + return rebaselineRecovery. |
| `readLatestCandidate()`                   | (exported)                          | Convenience: normalize + return latestCandidate.  |
| `PUBLIC_OUTCOME_KINDS`                    | (exported)                          | Frozen array: `["candidate","noop","clarify","error"]`. |

---

## 11. Design decisions (settled)

- **SD1:** Legacy/internal `edit` and `edit+clarify` outcome kinds are normalized to
  public `candidate` before crossing the public boundary; they are not surfaced as public
  kinds.
- **SD2:** `snake_case` remains canonical on the wire; consumed browser fields are
  camelCase after `agent_edit_response_contract.js` normalization.  Raw snake_case may
  remain only in debug/`.raw` paths.
- **SD3:** Server‑side stamping is authoritative for `/chat` `latest_candidate` and
  derivable agent message outcomes before they reach the browser.  The browser boundary
  module normalizes direct‑response payloads and provides legacy inference as a fallback
  — but the browser never performs a second classification after the server already
  stamped an outcome.
