# Agent Edit Wire Protocol — Batch REPL (M2)

This document describes the batch-REPL wire protocol implemented in M2
(`VIBECOMFY_AGENT_EDIT_BATCH_REPL=1`).  It is the authoritative reference for
the protocol shape, turn lifecycle, budget semantics, exit classifications,
provider integration points, and transcript contract.  M3 corpus harness work
(replay, fuzzing, audit tooling, batch regression suites) is **out of scope**
for this document.

> **Flag gate.**  The batch-REPL path is behind `VIBECOMFY_AGENT_EDIT_BATCH_REPL=1`.
> Without it, requests route through the existing v2 delta path
> (`VIBECOMFY_AGENT_EDIT_V2=1`) or the legacy full-file path.  Routing
> precedence is **batch → v2 delta → legacy**.

Everything below is implemented and verified by the M2 test suite
(`tests/test_comfy_nodes_agent_edit.py`, batch-REPL tests).

---

## 1. Protocol overview

```
┌──────────┐    ```batch fenced block     ┌──────────────┐
│  Model   │ ──────────────────────────► │  EditSession │
│          │ ◄──── diff + report ─────── │  (frozen)    │
└──────────┘    (turn > 0 only)          └──────────────┘
```

The model receives a **system prompt + user message** and returns exactly
**one ```batch fenced block** plus surrounding prose.  The batch code is
applied through `EditSession.apply_batch()`.  Teaching feedback (diff +
per-statement report) is fed into the next turn's prompt.

### 1.1 The batch fence — exact-one stripping seam

Every model response **must** contain exactly one `` ```batch `` fenced block:

````text
Your prose explanation to the user goes here.

```batch
saveimage.images = loadimage.image
saveimage.filename_prefix = "after"
done()
```
````

- **Zero fences** → `MalformedModelJSON` ("does not contain a ```batch fenced block").
- **Multiple fences** → `MalformedModelJSON` ("contains multiple ```batch fenced blocks").
- Prose outside the fence becomes `BatchTurnResult.message` (the user-facing agent message).
- Fenced code becomes `BatchTurnResult.batch` (the edit statements).

The extractor (`extract_batch_fence` in `vibecomfy/comfy_nodes/agent_provider.py`)
uses a regex that matches `` ```batch `` (case-insensitive, optional language
annotation) and strips everything outside.

Non-batch fenced code (`` ```python ``, `` ```json ``, etc.) within the same
response is **ignored** — it appears in the prose and does not interfere with
the batch fence extraction.

---

## 2. Payload shapes — turn 0 vs later turns

### 2.1 Turn 0 (first turn)

The system prompt describes the batch grammar and budget.  The user message
includes the **full Python render** and **typed signature catalog**:

```
System: You edit a VibeComfy ComfyUI canvas through batch edit statements.
        Return prose + exactly one ```batch fenced code block.
        Batch statement grammar: add_node(...), set_node_field(...),
        remove_node(...), upsert_link(...), remove_link(...), set_mode(...),
        reorder(...). Use done() to commit. Use clarify("...") to ask.
        Return ONLY prose + one ```batch block. Do NOT return JSON.
        Budget: N batch(es) remaining out of M.

User:   User request:
        {task}

        Current scratchpad Python (full render):
        ```python
        {python_source}
        ```

        Available node signatures (typed catalog):
        ```
        {signature_catalog}
        ```
```

### 2.2 Later turns (turn > 0)

The system prompt is identical.  The user message replaces the full Python
render and catalog with a **compact diff** and **structured teaching report**:

```
User:   User request:
        {task}

        Diff from previous render:
        ```diff
        {diff}
        ```

        Teaching report from previous turn:
        {report}

        Budget: N batch(es) remaining out of M.
```

The diff is capped at **2000 characters** (truncated with `... [truncated]`).
The full Python source is **never re-dumped** after turn 0 — the model works
incrementally from the diff and report alone.

### 2.3 What is NOT in the prompt

- **No JSON-delta wording.**  The batch system prompt does not mention JSON
  response requirements, `delta` keys, or op schemas.
- **No `"response_contract": "delta"` language.**  The batch path uses its own
  contract identifier (`response_contract: "batch_repl"`).
- **No projection text.**  The batch path uses the typed signature catalog
  (searchable) instead of the address-preserving UI projection.

---

## 3. Batch statement grammar

The model emits one or more Python-like statements inside the `` ```batch ``
fence:

| Statement | Purpose |
|---|---|
| `node.field = value` | Set a node field (sugar for `set_node_field`) |
| `add_node("Type", name="x", ...)` | Add a new node |
| `remove_node("name")` | Remove a node by name |
| `upsert_link(from_node.slot, to_node.slot)` | Create or update a link |
| `remove_link(from_node.slot, to_node.slot)` | Remove a link |
| `set_mode("mode_name")` | Switch the canvas interaction mode |
| `reorder(nodes=["a","b","c"])` | Reorder nodes |
| `done()` | Commit the edit session (final turn) |
| `clarify("question")` | Ask the user a question (exits without commit) |

`done()` and `clarify("...")` are **in-band calls** within the batch fence.
They are detected by the loop, not by `EditSession`.

---

## 4. Budget semantics

### 4.1 Budget parameters

| Parameter | Source | Default | Meaning |
|---|---|---|---|
| `max_batches` | Request payload `max_batches` | 5 | Maximum batch turns before forced exit |
| `max_consecutive_errors` | Request payload `max_consecutive_errors` | 1 | Consecutive error turns before forced exit |

Both are settable by the caller (UI/browser) in the request payload.

### 4.2 Budget tracking

The loop maintains a `batch_budget_state` dict:

```json
{
  "max_batches": 5,
  "max_consecutive_errors": 3,
  "remaining_batches": 3,
  "remaining_consecutive_errors": 2,
  "consecutive_errors": 1
}
```

- `remaining_batches` = `max_batches - turn_count`
- `consecutive_errors` increments when a turn has errors (not `batch_result.ok`
  or has diagnostics); resets to 0 on a clean turn.
- `remaining_consecutive_errors` = `max(0, max_consecutive_errors - consecutive_errors)`

### 4.3 Budget exhaustion

When the loop exhausts `max_batches` or `max_consecutive_errors` without a
`done()` or `clarify()` exit, it returns a **blocking failure** with
`FailureKind.BATCH_BUDGET_EXHAUSTED`.  The failure is further classified into
one of three sub-kinds for diagnostics:

---

## 5. Exit classifications

### 5.1 `done()` — successful commit

When `done()` appears in `BatchResult.statements` with `ok=True`:

1. `session.done()` is called — this replays all landed ops through the
   deterministic apply path and runs **proof gates A, B, and C**.
2. All core gates are set to `True`: `python_load_ok`, `lower_ok`,
   `ir_validate_ok`, `ui_emit_ok`, `ui_fidelity_ok`, `ui_load_safe_ok`,
   `state_match_ok`.
3. The Gate C summary (e.g. "Gate A passed: … Gate B passed: … Gate C passed:
   Rewired saveimage.images, Set saveimage.filename_prefix") is exposed:
   - In `state.batch_done_summary` and `state.batch_final_summary`
   - In the response as `done_summary`
   - In audit metadata as `batch_repl.done_summary`
4. The response has `apply_allowed: True` and `queue_allowed: False`
   (committed but not queued).
5. `exit_mode = "done"`.

If `session.done()` returns `ok=False`, the response is a blocking failure
with `FailureKind.VALIDATION_ERROR` and the done diagnostics are surfaced.

### 5.2 `clarify("...")` — non-commit exit

`clarify("...")` is detected by a **pre-scan regex** *before*
`session.apply_batch()` is called.  The regex matches:

```
clarify("escaped string content")
```

- Only double-quoted strings are recognized.
- Escaped characters (`\"`, `\\`, etc.) are supported.
- The clarification message is extracted via `json.loads()` for proper
  unescaping, with a fallback to raw text.

When a clarification is detected:

1. `apply_batch()` is **never called** — the statement is not passed to
   `EditSession`.
2. The loop short-circuits with a successful (non-blocking) result.
3. `state.batch_exit_mode = "clarify"`.
4. The response includes `clarification_required: True` and
   `graph_unchanged: True`.
5. `state.user_message` is set to the clarification text (shown to the user).
6. The turn is recorded in audit with `clarification_required: True` and
   `clarification_message`.

### 5.3 Budget exhaustion — diagnostic classification

When the loop exits due to budget exhaustion, the failure kind is classified
from repeated diagnostic patterns across all turns:

| Classification | Pattern | Meaning |
|---|---|---|
| `SCHEMA_GAP` | Diagnostics mention "schema", "schema-backed", "socket type", "compatible output", or "confidence" | The model tried valid operations that the schema doesn't cover |
| `UNREPRESENTABLE` | Diagnostic codes like `statement_not_allowed`, `call_not_allowed`, `nested_call_not_allowed`, etc., or messages containing "not allowed" / "immutable" | The model tried operations the grammar cannot express |
| `MODEL_MISTAKE` | Everything else (bad field names, syntax errors, wrong types, etc.) | Fixable model errors that didn't converge within budget |

The classifier (`_batch_budget_failure_kind`) ranks by turn-hit frequency,
with a tiebreaker that prefers more specific categories (`SCHEMA_GAP` >
`UNREPRESENTABLE` > `MODEL_MISTAKE`).  If no diagnostic patterns match,
`MODEL_MISTAKE` is the default.

Each sub-kind has its own `FailureSpec` in `agent_contracts.py`:

| FailureKind | Retryable | Next action |
|---|---|---|
| `BATCH_BUDGET_EXHAUSTED` | No | Manual intervention or resubmit with narrower scope |
| `MODEL_MISTAKE` | Yes | Retry or restate the request more concretely |
| `UNREPRESENTABLE` | No | Reformulate as a supported static graph edit |
| `SCHEMA_GAP` | No | Reformulate avoiding the gap or file a schema request |

---

## 6. Teaching reports

After every turn (including the last before a `done()` or `clarify()`), the
loop produces a **deterministic teaching report** grounded only in
`BatchResult.statements` and `CompactDiagnostic` fields.  No schema hints or
other invented content are included.

### 6.1 Text report

```
Batch summary: L landed, F failed, D batch diagnostic(s), B batch(es) remaining, E consecutive error turn(s).
✓ Statement 0: upsert_link — landed (source: "saveimage.images = loadimage.image"; touched uids: ["1", "3"])
✗ Statement 1: set_node_field — not landed (source: "saveimage.not_a_field = \"bad\""; cause: field_not_found; unknown_target_field: SaveImage has no editable field or input named 'not_a_field'.; hint: Available fields: ['images', 'filename_prefix'])
! batch_size_exceeded: batch exceeds max_statements limit
```

### 6.2 JSON report

The JSON variant (`_format_batch_report_json`) produces a deterministic dict:

```json
{
  "summary": {"landed": 1, "failed": 1, "budget_remaining": 3, "consecutive_errors": 1},
  "statements": [
    {
      "statement_index": 0,
      "source": "saveimage.images = loadimage.image",
      "ok": true,
      "landed": true,
      "op_kind": "upsert_link",
      "detail": {},
      "touched_uids": ["1", "3"],
      "dependency_cause": null,
      "teaching_hint": null,
      "diagnostics": []
    }
  ],
  "diagnostics": []
}
```

### 6.3 Per statement fields

| Field | Source | Description |
|---|---|---|
| `statement_index` | `BatchResult.statement_index` | 0-based position in batch |
| `source` | `BatchResult.source` | Source text (truncated at 72 chars in text report) |
| `ok` | `BatchResult.ok` | Whether the statement succeeded |
| `landed` | `BatchResult.landed` | Whether the op was applied to working_ui |
| `op_kind` | `BatchResult.op_kind` | e.g. `upsert_link`, `set_node_field`, `done` |
| `touched_uids` | `BatchResult.touched_uids` | UIDs affected by this statement |
| `dependency_cause` | `BatchResult.dependency_cause` | Why a dependent statement was skipped |
| `teaching_hint` | `BatchResult.teaching_hint` | Actionable hint for the model |
| `diagnostics` | `BatchResult.diagnostics` | CompactDiagnostic list (code, message, severity, detail, teaching_hint) |

---

## 7. Provider integration points

### 7.1 Prompt construction — `build_batch_messages()`

Location: `vibecomfy/comfy_nodes/agent_provider.py`

```python
messages = build_batch_messages(
    task=task,
    turn_number=turn_number,
    python_source=initial_render,       # only when turn_number == 0
    signature_catalog=catalog,          # only when turn_number == 0
    diff=last_diff,                     # only when turn_number > 0
    report=last_report,                 # only when turn_number > 0
    budget_remaining=remaining,
    max_batches=max_batches,
)
```

Returns `[{"role": "system", "content": ...}, {"role": "user", "content": ...}]`.

### 7.2 Response parsing — `extract_batch_fence()`

Location: `vibecomfy/comfy_nodes/agent_provider.py`

```python
batch_code, prose = extract_batch_fence(raw_response_text)
```

Returns the code inside the `` ```batch `` fence and all prose outside it.
Raises `MalformedModelJSON` on 0 or 2+ fences.

### 7.3 Turn execution — `run_agent_turn_batch()`

Location: `vibecomfy/comfy_nodes/agent_provider.py`

```python
result = run_agent_turn_batch(task, messages, route=route, model=model)
# result: BatchTurnResult(batch=..., message=..., route=..., model=..., audit_metadata=...)
```

Routes through the existing Arnold/Hermes provider path.
`audit_metadata` includes `"response_contract": "batch_repl"`.

### 7.4 Runtime dispatch — `_call_batch_runtime()`

Tries three dispatch methods in order:
1. `runtime.run_agent_turn_batch(...)` — preferred
2. `runtime.run_agent_turn(...)` — fallback with `messages` kwarg
3. `runtime.run(...)` — fallback with `response_contract="batch_repl"`

### 7.5 Test seam — `deepseek_client`

The batch loop accepts an optional `deepseek_client` callable:

```python
def _fake_batch_client(messages: list[dict[str, str]]) -> dict[str, str]:
    return {"batch": "done()", "message": "Done."}

result = handle_agent_edit(payload, deepseek_client=_fake_batch_client, ...)
```

When provided, the loop calls `deepseek_client(messages)` instead of
`run_agent_turn_batch()`.  The response is normalized through
`_normalize_test_client_batch_response()`, which supports both raw strings
(parsed via `extract_batch_fence`) and pre-split `{"batch": ..., "message": ...}`
dicts.

### 7.6 Audit metadata

When `VIBECOMFY_AGENT_EDIT_BATCH_REPL=1`, the audit metadata includes:

```json
{
  "batch_repl": {
    "enabled": true,
    "turn_count": 4,
    "signature_catalog_available": true,
    "feedback": "...",
    "final_summary": "Gate A passed: …",
    "exit_mode": "done",
    "done_summary": "Gate A passed: …",
    "budget_state": { ... }
  }
}
```

Provider audit metadata (from `run_agent_turn_batch`) includes
`"response_contract": "batch_repl"` to distinguish batch turns from
v2 delta turns (`"response_contract": "delta"`) and legacy turns.

---

## 8. Pipeline stages (batch-REPL path)

When `VIBECOMFY_AGENT_EDIT_BATCH_REPL=1`:

```
ingest  →  agent_batch  →  audit
```

- **ingest** (`_stage_ingest_v2`): Loads the graph through the concrete-tree
  path, stamps identity uids, captures the original UI guard copy.
- **agent_batch** (`_stage_agent_batch_repl`): The full REPL loop — creates
  `EditSession`, renders turn 0, runs bounded turns, applies batches, formats
  reports, handles exits.  This is a **single stage** that internally loops.
- **audit** (`_stage_audit`): Writes session audit with batch-REPL metadata.

There are **no** `convert`, `load_python`, `lower`, `validate`, `emit`,
`queue_validate`, or `summarize` stages in the batch path — `EditSession`
handles the apply/gate logic internally.

---

## 9. Transcript example (scripted non-LLM test)

The test `test_handle_agent_edit_batch_repl_scripted_transcript_commits_structurally_correct_graph`
drives a four-turn batch REPL session with a fake provider:

### Setup
- Graph: `LoadImage` → `PassThroughImage` → `SaveImage`
- Task: "bypass the passthrough and rename the final save output"
- Budget: `max_batches=5`, `max_consecutive_errors=3`

### Turn 0 — Successful rewire
```
Model batch:   saveimage.images = loadimage.image
Model message: Bypassed the passthrough output.
Result:        1 landed (upsert_link), 0 failed. Diff shows the link change.
```

### Turn 1 — Failed statement (teaching feedback)
```
Model batch:   saveimage.not_a_field = "bad"
Model message: Tried to finish the rename.
Result:        0 landed, 1 failed.
Teaching:      "unknown_target_field: SaveImage has no editable field or
               input named 'not_a_field'. Available fields: ['images',
               'filename_prefix']"
Turn 2 prompt: Includes the teaching report from turn 1.
```

### Turn 2 — Correction
```
Model batch:   saveimage.filename_prefix = "after"
Model message: Corrected the field name and updated the prefix.
Result:        1 landed (set_node_field), 0 failed.
```

### Turn 3 — Commit
```
Model batch:   done()
Model message: Ready to commit the candidate.
Result:        done() detected → session.done() → Gate C summary:
               "Gate A passed: ... Gate B passed: ... Gate C passed:
                Rewired saveimage.images, Set saveimage.filename_prefix"
Response:      ok=True, apply_allowed=True, done_summary with Gate C text.
```

### Final assertions
- `result["ok"] is True`
- `result["apply_allowed"] is True`
- `result["done_summary"]` contains "Rewired saveimage.images" and
  "Set saveimage.filename_prefix"
- 4 turns were captured in the message log
- Turn 2's prompt includes the teaching feedback from turn 1
- Final graph has `LoadImage` linked directly to `SaveImage.images` (bypassing
  `PassThroughImage`)
- `SaveImage.filename_prefix` is `"after"`
- Audit metadata confirms `turn_count=4`, `exit_mode="done"`

---

## 10. Response envelope

### 10.1 Successful done() response

```json
{
  "ok": true,
  "apply_allowed": true,
  "queue_allowed": false,
  "message": "Ready to commit the candidate.\n\nGate A passed: … Gate C passed: …",
  "graph": { ... },
  "done_summary": "Gate A passed: … Gate C passed: Rewired saveimage.images, Set saveimage.filename_prefix",
  "audit_ref": { "path": "...", "hash": "..." }
}
```

### 10.2 Clarification response

```json
{
  "ok": true,
  "apply_allowed": false,
  "queue_allowed": false,
  "message": "What resolution should the output image be?",
  "graph": { ... },
  "clarification_required": true,
  "graph_unchanged": true,
  "audit_ref": { "path": "...", "hash": "..." }
}
```

Note: `apply_allowed=False` because the graph was not committed.

### 10.3 Budget exhaustion response

```json
{
  "ok": false,
  "apply_allowed": false,
  "queue_allowed": false,
  "failure": {
    "kind": "ModelMistake",
    "retryable": true,
    "message": "The agent exhausted its batch budget on fixable edit mistakes. The graph is unchanged.",
    "detail": {
      "turn_count": 5,
      "budget_state": { ... },
      "budget_classification": "ModelMistake"
    }
  },
  "audit_ref": { "path": "...", "hash": "..." }
}
```

---

## 11. M3 out of scope

The following is explicitly **not covered** by this document or the M2
implementation:

- **Corpus harness**: Automated replay of batch sessions against a golden
  corpus of workflows.
- **Fuzzing**: Randomized or adversarial batch input generation.
- **Audit tooling**: Post-hoc analysis, diffing, or visualization of batch
  session audit trails.
- **Batch regression suites**: Systematic comparison of batch-REPL results
  against v2 delta or legacy outputs for the same tasks.
- **Provider fallback chains**: Multi-provider retry or routing decisions
  within a single batch turn.

These are deferred to M3.

---

## 12. Key source files

| File | Role |
|---|---|
| `vibecomfy/comfy_nodes/agent_provider.py` | `BatchTurnResult`, `extract_batch_fence`, `build_batch_messages`, `run_agent_turn_batch`, `_normalize_batch_response`, `_call_batch_runtime` |
| `vibecomfy/comfy_nodes/agent_edit.py` | `_agent_edit_batch_repl_enabled`, `_stage_agent_batch_repl`, `_render_batch_diff`, `_format_batch_report`, `_format_batch_report_json`, `_extract_clarify_message`, `_batch_budget_failure_kind`, batch state fields, routing precedence |
| `vibecomfy/comfy_nodes/agent_contracts.py` | `FailureKind` entries (`BATCH_BUDGET_EXHAUSTED`, `CLARIFICATION_REQUIRED`, `MODEL_MISTAKE`, `UNREPRESENTABLE`, `SCHEMA_GAP`), `FAILURE_SPECS` for batch exits |
| `vibecomfy/porting/edit_session.py` | `EditSession` (frozen API), `ReorderOp` import |
| `tests/test_comfy_nodes_agent_edit.py` | Batch-REPL tests including flag-off regression, partial success, clarify/done/budget exit, structured reporting, and scripted transcript |
| `tests/test_comfy_nodes_agent_backend_spine.py` | Batch fence extraction, prompt shape, and provider contract tests |
