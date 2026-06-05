# Agent-edit contracts (M2 — typed result contracts & protocol collapse)

This document defines the canonical response envelope, typed outcome contracts,
provider readiness surface, and compatibility aliases for the agent-edit
pipeline. It is the authoritative reference for M2 and every consumer that builds
on it (browser/UI wiring, M3 replay/audit, future runtime cancellation).

**Everything below is implemented and verified** by the M2 test suites
(`tests/test_comfy_nodes_agent_edit.py`, `tests/test_comfy_nodes_agent_backend_spine.py`,
`tests/test_comfy_nodes_agent_contracts.py`, `tests/browser/roundtrip_smoke.test.mjs`).

---

## 1. Protocol selection (collapsed)

The agent-edit pipeline uses **one canonical protocol**: `batch_repl`.

```
VIBECOMFY_AGENT_EDIT_LEGACY=delta|full   ← dev-test only, quarantined
(default)                                 ← batch_repl (production)
```

- `VIBECOMFY_AGENT_EDIT_V2` and `VIBECOMFY_AGENT_EDIT_BATCH_REPL` are **removed**
  as protocol selectors and no longer appear in debug output.
- Legacy `delta` and `full` contracts are reachable **only** through
  `VIBECOMFY_AGENT_EDIT_LEGACY` and exist solely for quarantined compatibility
  tests. They are not product paths.

---

## 2. Typed result contracts

### 2.1 `FieldChange` — a single landed field edit

```python
@dataclass(frozen=True)
class FieldChange:
    uid: str           # node unique identifier
    field_path: str    # dotted field path, e.g. "widget_values.filename_prefix"
    old: Any           # value from the original ledger; None when no matching node/field
    new: Any           # value after the edit landed
```

| Field | Type | Nullable | Description |
|---|---|---|---|
| `uid` | `str` | no | The node's unique identifier. |
| `field_path` | `str` | no | Dotted path to the edited field within the node. |
| `old` | `Any` | **yes** | Original ledger value. `None` when the original ledger has no matching node or field — this is a genuine absent value, not a client-side diff. |
| `new` | `Any` | no | Value after the edit landed. |

**Serialized form** (via `to_dict()`):

```json
{
  "uid": "123",
  "field_path": "widget_values.filename_prefix",
  "old": null,
  "new": "ComfyUI"
}
```

**Key rules:**

- `old` is recovered from the **original ledger** at edit-application time via
  `EditSession._original_node_field_value()`. It is never inferred from a
  client-side diff.
- `old` serializes as JSON `null` when the original ledger has no entry. This is
  the expected shape for newly-created nodes.
- Falsey-but-not-None values (`0`, `""`, `false`) are preserved as-is — they are
  distinct from "no prior value."
- `FieldChange` is frozen and hashable; it can be used as a dict key.

### 2.2 `TurnOutcome` — typed outcome for a single turn

```python
@dataclass(frozen=True)
class TurnOutcome:
    kind: str                          # one of the six canonical kinds
    changes: tuple[FieldChange, ...]   # landed field edits (empty for non-edit outcomes)
```

**Valid `kind` values:**

| `kind` | Meaning | `changes` |
|---|---|---|
| `"edit"` | The turn landed edits without a pending clarification. | non-empty |
| `"clarify"` | The turn needs clarification and landed **no** edits. | empty |
| `"edit+clarify"` | The turn landed edits **and** still needs a user clarification. | non-empty |
| `"failure"` | The turn failed before producing a candidate. | empty |
| `"noop"` | The turn completed without edits or clarification. | empty |
| `"budget"` | The turn exhausted its allowed edit budget. | may be non-empty |

**Serialized form** (via `to_dict()`):

```json
{
  "kind": "edit+clarify",
  "changes": [
    {"uid": "123", "field_path": "widget_values.filename_prefix", "old": null, "new": "ComfyUI"}
  ]
}
```

**Key rules:**

- `kind` is validated at construction time; invalid values raise `ValueError`.
- For `"edit"` and `"edit+clarify"`, `changes` must be non-empty (enforced by
  the producer, not the dataclass).
- For `"clarify"`, `"failure"`, and `"noop"`, `changes` is empty.
- `TurnOutcome` is frozen and hashable.

---

## 3. Canonical success envelope

Every successful agent-edit response carries these **primary typed fields**:

```json
{
  "ok": true,
  "session_id": "sess-abc123",
  "turn_id": "turn-xyz789",
  "baseline_turn_id": "turn-prev456",

  "outcome": {
    "kind": "edit",
    "changes": [
      {"uid": "123", "field_path": "widget_values.filename_prefix", "old": null, "new": "ComfyUI"}
    ]
  },

  "candidate": {
    "graph": { ... },
    "baseline_graph_hash": "sha256:...",
    "submit_graph_hash": "sha256:...",
    "submit_structural_graph_hash": "sha256:...",
    "submitted_client_graph_hash": "sha256:...",
    "submitted_client_structural_graph_hash": "sha256:...",
    "candidate_graph_hash": "sha256:...",
    "candidate_structural_graph_hash": "sha256:..."
  },

  "eligibility": {
    "canvas_apply_allowed": true,
    "apply_allowed": true,
    "queue_allowed": false
  },

  "message": "Renamed SaveImage filename_prefix to ComfyUI.",
  "graph": { ... },
  "report": { ... },
  "artifacts": { ... },

  "changes": [
    {"uid": "123", "field_path": "widget_values.filename_prefix", "old": null, "new": "ComfyUI"}
  ],

  "batch_turns": [ ... ],

  "gates": {
    "python_load_ok": true,
    "lower_ok": true,
    "ir_validate_ok": true,
    "ui_emit_ok": true,
    "ui_fidelity_ok": true,
    "ui_load_safe_ok": true,
    "state_match_ok": true
  },

  "audit_ref": {
    "path": "out/editor_sessions/sess-abc123/turn-xyz789/audit.json",
    "sha256": "sha256:...",
    "byte_count": 1234,
    "preview": "..."
  },

  "version": 1
}
```

### 3.1 Primary typed fields

| Field | Type | Description |
|---|---|---|
| `outcome` | `TurnOutcome` (dict) | The typed turn outcome: `kind` + `changes`. |
| `candidate` | dict | Graph hashes and the candidate graph payload. |
| `eligibility` | dict | Gate-derived flags: `canvas_apply_allowed`, `apply_allowed`, `queue_allowed`. May also carry `graph_unchanged`, `retryable`, and `next_action` when relevant. |
| `message` | `str` | Non-empty, user-facing message. Synthesized from provider prose, `clarify()` text, `done()` summary, edit counts, or fallback prose. |
| `changes` | `list[FieldChange]` | Top-level alias for `outcome.changes`. See §4. |
| `audit_ref` | `ArtifactRef` (dict) | Reference to the staged audit artifact. Inserted **after** the audit is written, never before. |

### 3.2 Audit ordering

The audit reference is intentionally **absent** from `success_envelope()` in
`agent_contracts.py`. The call site in `agent_edit.py` follows this order:

1. Build the canonical response envelope (without `audit_ref`).
2. Stage the audit artifact with the response payload.
3. Insert `audit_ref` into the response.
4. Return the complete response.

This eliminates the dependency cycle where the audit needed the response but the
response contained the audit reference.

---

## 4. Debug and backward-compatibility aliases

During M2, the following aliases are preserved so that browser consumers and
legacy tests can migrate incrementally. **New code should use the primary typed
fields** from §3.

### 4.1 Field-changes aliases

| Alias | Primary | Notes |
|---|---|---|
| `field_changes` (in batch turn records) | `changes` | Identical content. Both keys are emitted in turn records. |
| `field_changes` (top-level, legacy) | `outcome.changes` | The top-level `changes` key holds the same data as `outcome.changes`. |

The JS `normalizeBatchTurn()` function reads `changes` first, then falls back to
`field_changes`:

```javascript
const changes =
  Array.isArray(payload.changes)
    ? payload.changes
    : Array.isArray(payloadOutcome?.changes)
      ? payloadOutcome.changes
      : (Array.isArray(payload.field_changes) ? payload.field_changes : []);
```

### 4.2 Clarification aliases

| Alias | Primary | Notes |
|---|---|---|
| `clarification_required` (boolean) | `outcome.kind === "clarify" \|\| "edit+clarify"` | Retained as a top-level boolean for one milestone. |
| `clarification_message` (string) | Synthesized into `message` | Raw clarification text, preserved for browser consumers. |

The JS `normalizeBatchTurn()` infers clarification state from `outcome.kind`
while still checking the legacy `clarification_required` flag:

```javascript
const clarificationRequired =
  payload.clarification_required === true
  || payloadOutcomeKind === "clarify"
  || payloadOutcomeKind === "edit+clarify";
```

### 4.3 Eligibility aliases

The top-level `canvas_apply_allowed`, `apply_allowed`, and `queue_allowed`
booleans are preserved alongside the nested `eligibility` object. Both carry
identical values.

---

## 5. Failure envelope

Failure responses use the `FailureEnvelope` dataclass from `agent_contracts.py`:

```json
{
  "ok": false,
  "kind": "ValidationError",
  "stage": "validate",
  "session_id": "sess-abc123",
  "turn_id": "turn-xyz789",
  "canvas_apply_allowed": false,
  "apply_allowed": false,
  "queue_allowed": false,
  "graph_unchanged": true,
  "retryable": true,
  "next_action": "agent should fix structural issues",
  "message": "The edited workflow has validation errors and was not applied. See details.",
  "user_facing_message": "The edited workflow has validation errors and was not applied. See details.",
  "agent_failure_context": { "explanation": "..." },
  "audit_ref": null,
  "audit_error": null
}
```

**Key rules:**

- `message` and `user_facing_message` carry the same user-facing text.
- `kind` is a `FailureKind` enum value (string-serialized).
- `graph_unchanged` is always `true` for transient/provider failures; it may be
  `false` for queue-blocker failures where the candidate graph was applied.
- `retryable` indicates whether the same request can be retried.
- `audit_ref` is `null` when audit staging failed.

### 5.1 Failure kinds (closed set)

| `FailureKind` | Retryable | Description |
|---|---|---|
| `SyntaxError` | yes | Generated Python has a syntax error. |
| `ASTScanFailure` | yes | Generated Python uses forbidden constructs. |
| `OversizedPayload` | no | Generated Python is too large. |
| `MalformedModelJSON` | yes | Model response could not be parsed as JSON. |
| `MissingRequiredField` | yes | Model response is incomplete. |
| `ProviderError` | yes | Model provider is temporarily unavailable. |
| `AuthError` | no | Provider rejected authentication. |
| `TimeoutError` | yes | Model did not respond in time. |
| `ValidationError` | yes | Edited workflow has validation errors. |
| `UnsatisfiedInputError` | yes | Nodes are missing required inputs. |
| `RefusedEmit` | yes | Candidate would destroy editor state. |
| `EditorAheadConflict` | no | Editor has conflicting changes. |
| `StaleStateMismatch` | no | Submitted graph no longer matches canvas. |
| `UnsupportedNonDAG` | no | Request requires unsupported control flow. |
| `LoweringFailure` | yes | Workflow could not be lowered to a static graph. |
| `SchemaLessQueueBlocker` | no | Node schemas are unavailable. |
| `LowConfidenceQueueBlocker` | no | Schema/provider confidence too low for queueing. |
| `EditorOnlyNodeQueueBlocker` | no | Editor-only nodes block queueing. |
| `AuditWriteWarning` | no | Audit written with warnings. |
| `AuditWriteFailure` | no | Audit could not be written; turn aborted. |
| `BatchBudgetExhausted` | no | Agent exhausted its batch edit budget. |
| `ClarificationRequired` | no | Agent needs clarification before continuing. |
| `ModelMistake` | yes | Agent exhausted budget on fixable edit mistakes. |
| `Unrepresentable` | no | Request cannot be represented in the edit surface. |
| `SchemaGap` | no | Budget exhausted because required schema info is missing. |

---

## 6. Provider readiness

Provider readiness is reported through a single canonical surface:
`get_agent_status()` in `megaplan_runtime.py`, exposed via
`_handle_agent_status()` in `routes.py`.

### 6.1 Status endpoint

```
GET /vibecomfy/agent-status?route=arnold&model=claude-sonnet-4-5
```

Returns:

```json
{
  "ok": true,
  "backend": "megaplan.agent.run_agent.AIAgent",
  "model": "claude-sonnet-4-5",
  "detail": "Arnold/Hermes (Claude) credential resolved via local OAuth/API key."
}
```

### 6.2 Readiness contract

| Field | Type | Description |
|---|---|---|
| `ok` | `bool` | **The canonical readiness gate.** `true` when the selected route has the required credentials. |
| `backend` | `str` | Always `"megaplan.agent.run_agent.AIAgent"` in VibeComfy. |
| `model` | `str` | The resolved model name for the route. |
| `detail` | `str` | Human-readable reason for the readiness state. |

For the `deepseek` route, additional fields are present:

| Field | Type | Description |
|---|---|---|
| `base_url` | `str` | The DeepSeek API base URL. |
| `deepseek_key_present` | `bool` | Whether `DEEPSEEK_API_KEY` is resolved. |

### 6.3 Browser consumption

The JS settings panel reads `provider_available` from the provider's status
snapshot (a separate surface maintained by `agent_provider.py`) and combines it
with the route descriptor from `get_agent_status()`:

```javascript
const providerAvailable = panel.state.statusSnapshot?.provider_available;
const availability = providerAvailable === false ? "provider unavailable" : "provider ready";
```

The `provider_available` flag is set by `agent_provider.py` during route
selection:
- `true` when a route is successfully selected and a model is resolved.
- `false` when route selection raises an exception.

---

## 7. Message synthesis

Every success envelope guarantees `message` is present and `message.strip()` is
non-empty. The synthesis chain in `agent_provider.py` (`synthesize_message()`)
follows this 7-level precedence:

| Priority | Source | Example result |
|---|---|---|
| 1 | Non-empty prose from the provider response | Agent's natural-language text |
| 2 | `clarify("...")` extraction | The clarification question text |
| 3 | `done()` summary | "Applied 3 edits: added LoadImage, wired to SaveImage" |
| 4 | Edit-line count | "Made 2 edit(s)." |
| 5 | Comment/control-only batch | "Batch processed." |
| 6 | `is_fallback` (budget exhausted) | "The agent used its available turns." |
| 7 | Catch-all | "Agent response received." |

Synthesis runs in two places:
- `_normalize_batch_response()` in `agent_provider.py` for live provider responses.
- `_finalize_success_message()` in `agent_edit.py` as a final guard before the
  envelope is returned.

The legacy `"Applied the requested edit."` fallback in `megaplan_worker.py` has
been **removed** — canonical message fallback is owned exclusively by
`agent_provider.py`.

---

## 8. Batch-turn classification

The batch-repl protocol classifies each turn before dispatch:

| Classification | Action | `outcome.kind` |
|---|---|---|
| **Pure clarify** | `clarify("...")` present, no edit ops → skip `apply_batch()`, return clarification immediately | `"clarify"` |
| **Pure edit** | No `clarify()` calls, edit ops present → apply edits, return result | `"edit"` |
| **Mixed edit+clarify** | Both `clarify()` and edit ops present → apply edits first, then surface clarification | `"edit+clarify"` |

**Key rules:**

- `graph_unchanged` is set to `true` **only** when no edits landed.
- A turn that lands edits and asks for clarification returns `outcome.kind:
  "edit+clarify"` with `graph_unchanged` absent (not `true`).
- Pure-clarify turns that land no edits set `graph_unchanged: true`.

---

## 9. WebSocket turn events

Batch turns emit WebSocket events through `_emit_agent_edit_turn_event()` →
`_agent_edit_turn_event_payload()`. Each event carries:

```json
{
  "session_id": "sess-abc123",
  "turn_id": "turn-xyz789",
  "entry_type": "batch",
  "status": "in_progress",
  "turn_number": 0,
  "message": "Made 1 edit(s).",
  "outcome": {
    "kind": "edit",
    "changes": [ ... ]
  },
  "changes": [ ... ],
  "clarification_required": false,
  "clarification_message": null,
  "batch_ok": true,
  "statement_count": 1,
  "landed_op_count": 1,
  "brief_statements": [ ... ]
}
```

**Excluded from WebSocket events** (too large/sensitive for wire transport):
raw batch text, diff text, file paths, provider metadata, and raw JSON blobs.

**Status values:**

| `status` | Meaning |
|---|---|
| `"in_progress"` | A batch turn completed; more turns may follow. |
| `"clarify"` | The turn exited with a pending clarification. |
| `"done"` | The turn completed successfully with `done()`. |
| `"budget_exhausted"` | The turn budget was exhausted; no more turns will follow. |

---

## 10. Cancellation descope

**M2 does not implement runtime cancellation.** The "Stop" button in the
browser UI is dismiss-only — it clears the in-flight state on the client side
but does not send a cancellation signal to the backend agent loop.

**Decision recorded:** Cancellation will be addressed in a separate runtime
cancellation milestone (tentatively M4). Until then:

- There is no `"cancelled"` outcome kind.
- The `TurnOutcome` enum does not include a cancellation variant.
- No `cancel_turn()` endpoint exists.
- The browser "Stop" button resets local panel state only.

---

## 11. Cross-language consumer contract

The JS `normalizeBatchTurn()` and `reconcileResponseBatchTurns()` functions in
`vibecomfy_roundtrip.js` are the canonical browser-side consumers of the
contracts defined here.

### 11.1 `normalizeBatchTurn(payload, options)`

Accepts a raw batch-turn payload (from a WebSocket event or response
`batch_turns` array) and normalizes it to the panel's internal turn-entry shape:

- Reads `outcome.kind` to infer clarification state.
- Falls back to `clarification_required` for legacy payloads.
- Reads `changes` first, then `outcome.changes`, then `field_changes`.
- Preserves `clarification_message` for display.

### 11.2 `reconcileResponseBatchTurns(panel, result)`

Merges the `batch_turns` array from a completed response into the panel's turn
history, deduplicating by `turn_key` and preserving expanded/collapsed state.

---

## 12. Test coverage

| Test file | Focus |
|---|---|
| `tests/test_comfy_nodes_agent_contracts.py` | `FieldChange`, `TurnOutcome` serialization and validation |
| `tests/test_comfy_nodes_agent_edit.py` | Envelope construction, outcome classification, audit ordering, field-change wiring |
| `tests/test_comfy_nodes_agent_backend_spine.py` | Message synthesis, batch normalization, provider fallback |
| `tests/test_porting_edit_session.py` | `FieldChange` collection from `EditSession`, `clarify()` parsing |
| `tests/browser/roundtrip_smoke.test.mjs` | JS `normalizeBatchTurn()` / `reconcileResponseBatchTurns()` |
