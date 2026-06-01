# Text-to-Graph Agent Maximal Viable Product

This is the product shape for a ComfyUI graph copilot where the user only types
a requested change and the graph updates. Python is an internal edit substrate:
the backend converts the current UI JSON to VibeComfy Python, lets an agent edit
that Python, validates it, exports UI JSON, and sends the candidate graph back to
the browser.

"Maximal viable" means the complete useful loop, not the smallest demo: the user
gets text-to-graph editing, apply-safe validation, undo, follow-up turns,
downloadable per-turn audits, and enough error reporting to trust the system.

## User experience

The browser should not expose generated Python as the primary workflow.

The user sees:

- the normal ComfyUI graph canvas;
- an "Edit with VibeComfy" command;
- a text box: "Describe the workflow change";
- a short agent response;
- changed-node / warning summary;
- Apply, Cancel, and Undo.

The canonical flow:

```text
current ComfyUI graph
  -> user types "make this 16:9, cinematic, stronger negative prompt"
  -> backend edits through Python
  -> browser previews candidate graph + summary
  -> user applies
  -> ComfyUI canvas changes
```

Debug mode may expose the generated Python and artifacts, but that is not the
main product.

## UX Elegance Bar

The frontend should feel like a native graph assistant, not a debugging console
bolted onto ComfyUI.

The elegant shape:

- **One calm panel:** a compact side panel or durable modal anchored to ComfyUI,
  not a stack of popups.
- **One primary action:** the dominant action is "Run edit" before a turn, then
  "Apply to canvas" after a valid candidate. Secondary actions stay visually
  quiet: Reject, Undo, Download audit, Details.
- **Progressive disclosure:** normal users see request, agent message, changed
  nodes, warnings, and Apply/Reject. Advanced details, raw reports, hashes, and
  artifacts live behind a disclosure.
- **Canvas-first feedback:** changed nodes are highlighted on the graph; special
  intent nodes carry small badges. The user should not have to read a JSON-ish
  report to understand what changed.
- **Clear state language:** distinguish "Can apply to canvas" from "Can queue".
  Editor-only intent nodes can be inspectable and useful while still not
  executable.
- **No scary failure wall:** failures render as a concise explanation, graph
  status, and next action. The audit download is available, but not shoved into
  the main path.
- **Undo is obvious:** after Apply, Undo is visible and immediate.
- **ComfyUI-native density:** controls should be compact, readable, and aligned
  with the existing ComfyUI visual language. Avoid a separate app-within-an-app.

## Backend loop

The backend-owned pipeline is:

```text
UI JSON
  -> convert_to_vibe_format()
  -> port_convert_workflow()
  -> generated scratchpad Python
  -> Arnold resolves route/model/credentials and edits complete Python file
  -> validate agent response shape
  -> inspect edited Python as untrusted agent-authored code
  -> load_scratchpad() through restricted/isolation path
  -> validate VibeWorkflow
  -> emit_ui_json(prior_store=store_from_ui_json(original_ui))
  -> return candidate UI JSON + report + session id
```

The Python file is an editable intermediate and audit artifact, not a trusted
program. Model-authored Python must never be loaded as `user_confirmed`.
Before any import/load step, the backend must validate the model response shape,
apply size limits, scan the AST for forbidden imports/calls/side effects, and
load through an `agent_generated` provenance path. If that cannot be made safe
enough, S0 must switch the mutation contract to a structured IR patch while
keeping Python as the inspectable representation.

### Python Loading Derisk Spike

Before S1 implementation work starts, run a focused spike that tries to break
the model-authored Python boundary. The spike should be short, adversarial, and
allowed to kill the current design.

Goal: prove we can safely turn agent-authored Python into a `VibeWorkflow`
without giving that Python normal process privileges.

Required experiment:

- implement a tiny prototype loader path for `agent_generated` scratchpads;
- accept only a narrow authoring subset: imports from approved VibeComfy modules,
  `new_workflow`, `node`, literals, handles, assignments, and metadata;
- reject module-level side effects, arbitrary imports, dynamic attribute access,
  `eval` / `exec` / `compile`, `__import__`, file/network/process APIs, path
  traversal, environment reads, and unknown calls before import/execution;
- run hostile fixtures through it: obvious `os.system`, hidden `getattr`,
  encoded import tricks, object dunder traversal, file reads, network calls,
  huge payloads, and benign real generated templates;
- verify all failures return classified `load_python` errors and still write
  redacted audit artifacts;
- measure whether real converted workflows still pass without needing a broad
  Python interpreter.

Kill criterion: if this cannot load useful generated templates without a broad
Python execution surface, do not proceed with model-edited Python as the primary
mutation contract. Switch S0 to a structured IR patch / edit-operation response
and keep Python as a generated audit/recipe view.

**Spike result (KEEP):** The derisking spike was completed and the Python-loading
path is kept as the primary mutation contract for S1. The restricted AST-gated
loader rejects all 12 hostile bypass classes before execution, benign generated
templates load and validate, all 64 checked-in ready templates pass the same scan,
and the `agent_edit.py` proof path is wired to the restricted loader with
`agent_generated` provenance. See
[`agent_text_to_graph_python_loading_spike.md`](./agent_text_to_graph_python_loading_spike.md)
for full fixture coverage, residual risk analysis, and the keep/kill decision.

The user should not have to debug the pipeline unaided. If any stage fails, the
backend returns a classified failure, the browser keeps the current graph
untouched, and the agent sees enough structured context to understand the
failure, explain it plainly, and either propose a recovery or attempt a safe
retry when the failure class allows it.

## What exists now

The first end-to-end backend splice exists:

- `vibecomfy/comfy_nodes/agent_edit.py`
  - accepts `{graph, task, session_id?}`;
  - converts UI JSON into a `VibeWorkflow`;
  - generates Python with `port_convert_workflow`;
  - currently calls DeepSeek directly with an OpenAI-compatible HTTP request;
  - expects model JSON with `python` and `message`;
  - loads the edited Python with `load_scratchpad`;
  - exports candidate UI JSON with `emit_ui_json`;
  - writes artifacts under `out/editor_sessions/<session_id>/`.
- `vibecomfy/comfy_nodes/routes.py`
  - exposes `POST /vibecomfy/agent-edit`.
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
  - registers `VibeComfy.AgentEdit`;
  - opens a task modal;
  - posts the current graph and task;
  - shows the backend message and change report;
  - applies the returned graph with `app.loadGraphData(graph)`.
- `tests/test_comfy_nodes_agent_edit.py`
  - covers the torch-free handler with a fake DeepSeek client,
    `agent_generated` (not `user_confirmed`) provenance through the
    restricted `load_agent_generated_scratchpad` path, and hostile
    model-output rejection for 9 bypass classes (T6–T7).

No committed browser tests exist yet for this feature. A temporary Playwright
smoke harness has verified the proof path outside the repo, but product
coverage for command registration, task submission, response handling, Apply,
Undo, turn history, failure rendering, and audit download still needs to be
added.

## Current Implementation Reality

The spec below is ahead of the current proof-path code. That is intentional, but
contributors should not mistake the target contract for implemented behavior.

| Surface | Current proof path | Maximal viable target |
|---|---|---|
| Response envelope | `{graph, message, report, session_id, artifacts, version}` | `ok`, `stage`, `kind`, `turn_id`, `canvas_apply_allowed`, `queue_allowed`, `summary`, `audit`, `agent_failure_context` |
| Session storage | flat `out/editor_sessions/<session_id>/current.py` etc. | isolated `out/editor_sessions/<session_id>/<turn_id>/...` |
| Validation | load + emit only | explicit validation gate before applyable response |
| Failure handling | route returns `{error, kind}` | classified failure envelope with retry guidance and audit |
| Frontend | one-shot modal | durable multi-turn text-to-graph surface |
| Browser tests | none committed for VibeComfy extension | Playwright coverage for success, failure, undo, audit, history |

## What is missing

We do not yet have the whole backend product.

The current backend proves the main idea, but it is not production-complete
because it lacks:

- **Hard validation gate:** edited Python is loaded and emitted, but the handler
  should explicitly run workflow validation and reject bad candidates before
  returning an applyable graph.
- **Error taxonomy:** syntax errors, DeepSeek JSON errors, validation errors,
  editor-ahead/refused-emit errors, schema-less warnings, and network failures
  should return stable `kind`, `stage`, `message`, and `details` fields.
- **Agent-visible failure context:** failures should not be dead-end browser
  errors. The backend should return structured context that an agent can reason
  about and communicate: what failed, why it likely failed, whether the current
  graph is unchanged, whether retry is safe, and what the next repair action is.
- **Session continuation:** artifacts are written, but follow-up turns currently
  do not reliably use the previous candidate as the new baseline. A session
  should track accepted graph, rejected graph, current Python, and turn history.
- **Undo contract:** frontend can apply a graph, but the backend should expose
  enough session state for restore/retry/debug. The browser should also keep a
  local previous-graph stack.
- **Diff contract:** change reports exist, but the API should return a compact,
  stable summary: nodes added, removed, edited, preserved, warnings, and whether
  Apply is allowed.
- **Safety constraints:** the restricted AST-gated `agent_generated_loader`
  (S0 T3–T5) scans model-authored Python before execution, rejects forbidden
  imports/calls/dunder traversal/filesystem operations, and only allows a
  narrow generated-template subset. The `agent_edit.py` proof path (S0 T6–T7)
  is wired to this loader with `agent_generated` provenance. See
  [`agent_text_to_graph_python_loading_spike.md`](./agent_text_to_graph_python_loading_spike.md)
  for fixture coverage and residual risk.
- **Provider/model configurability:** DeepSeek is hardwired by env vars. That is
  fine for now, but the API should report the configured provider/model and fail
  clearly when credentials are missing.
- **Real ComfyUI integration test:** the browser smoke uses a stubbed Comfy app.
  We still need a test against an actual running ComfyUI frontend/plugin install.
- **Concurrency/atomicity:** session writes should be atomic per turn. Two
  requests for the same session must not corrupt `current.py` or candidate JSON.
- **Large graph UX:** the backend prompt sends a complete Python file. For large
  workflows this needs size limits, truncation strategy, or a structured edit
  protocol before it can be trusted broadly.
- **Downloadable turn audit:** scattered artifacts are not enough. Each turn,
  including failures, needs one canonical audit file that captures everything
  needed for deep inspection and can be downloaded from the browser.
- **Product-grade frontend:** the current frontend is a proof modal. A maximal
  viable product needs a durable editing surface with turn history, progress,
  safe apply states, failure communication, audit downloads, and undo. The
  backend can be correct and still feel unusable if the browser surface is only
  a blocking prompt plus a raw diff list.
- **Baseline and stale-response protocol:** the frontend currently serializes
  the graph too early and has no response-to-request correlation. The protocol
  must prevent applying a candidate generated from a stale graph.
- **Accept/reject semantics:** the backend cannot infer that a returned
  candidate was accepted. Apply, reject, and follow-up turns need explicit state
  semantics so rejected candidates never become the baseline.
- **Custom code and control-flow representation:** VibeComfy can express
  ordinary static ComfyUI DAGs, and Python recipes can use normal Python control
  flow outside one graph. But the product does not yet have a shipped way to
  render custom code, `for` loops, branches, or multi-workflow orchestration as
  first-class graph objects and then prove the resulting workflow is valid.
  `docs/python_on_the_graph.md` is an RFC for this, not an implemented feature.

## API shape

Keep the public browser API small.

### `POST /vibecomfy/agent-edit`

Request:

```json
{
  "graph": {},
  "task": "change the prompt and make it 16:9",
  "session_id": "optional-existing-session",
  "baseline_turn_id": "optional-last-accepted-turn",
  "client_graph_hash": "sha256-of-submitted-graph",
  "idempotency_key": "client-generated-uuid",
  "frontend_version": "optional-version-string",
  "apply_policy": "preview"
}
```

Response on success:

```json
{
  "ok": true,
  "graph": {},
  "message": "Changed the prompt and resolution.",
  "session_id": "abc123",
  "turn_id": "0003",
  "baseline_turn_id": "0002",
  "client_graph_hash": "sha256-of-submitted-graph",
  "canvas_apply_allowed": true,
  "queue_allowed": true,
  "apply_allowed": true,
  "summary": {
    "added": [],
    "edited": ["uid-ksampler", "uid-positive"],
    "removed": [],
    "warnings": []
  },
  "report": {},
  "audit": {
    "path": "out/editor_sessions/abc123/0003/audit.json",
    "download_url": "/vibecomfy/agent-edit/audit?session_id=abc123&turn_id=0003"
  },
  "artifacts": {
    "original_ui": "out/editor_sessions/abc123/0003/original.ui.json",
    "python_before": "out/editor_sessions/abc123/0003/before.py",
    "python_after": "out/editor_sessions/abc123/0003/after.py",
    "candidate_ui": "out/editor_sessions/abc123/0003/candidate.ui.json"
  }
}
```

Response on failure:

```json
{
  "ok": false,
  "stage": "validate",
  "kind": "ValidationError",
  "message": "Edited workflow is missing required input `model` on KSampler.",
  "session_id": "abc123",
  "turn_id": "0003",
  "baseline_turn_id": "0002",
  "apply_allowed": false,
  "canvas_apply_allowed": false,
  "queue_allowed": false,
  "graph_unchanged": true,
  "user_facing_message": "The KSampler node lost its model connection, so the graph was not changed.",
  "agent_failure_context": {
    "explanation": "The edited Python removed a required KSampler model input.",
    "retry_safe": true,
    "suggested_repair": "Restore the original model connection and only change prompt/resolution fields."
  },
  "audit": {
    "path": "out/editor_sessions/abc123/0003/audit.json",
    "download_url": "/vibecomfy/agent-edit/audit?session_id=abc123&turn_id=0003"
  },
  "details": {}
}
```

The browser should only call `app.loadGraphData()` when `ok` and
`canvas_apply_allowed` are both true. The frontend must not use legacy
`apply_allowed` as its primary gate. `apply_allowed` is kept only as a
back-compat alias for `canvas_apply_allowed` while the API is settling, and
contract tests should prove this alias behaves as documented.

- **Canvas apply:** may this candidate be loaded into the editor?
- **Queue:** may this graph be sent to ComfyUI for execution?

A graph containing an editor-valid `vibecomfy.loop` or `vibecomfy.code` node may
be safe to apply to the canvas so the user can inspect and manually edit it, but
not safe to queue. That response should use `canvas_apply_allowed: true`,
`queue_allowed: false`, and include queue blockers.

On failure, the browser should show `user_facing_message` plus concise recovery
guidance, not just a raw exception. The agent can use `agent_failure_context`
plus the audit artifact to reason about the failure and make the next attempt
more precise.

### Accept / Reject

Candidate creation is not acceptance. The backend must not use a candidate as
the next accepted baseline until the browser explicitly marks it accepted, or
until the next request sends the full current canvas graph and the backend
treats that graph as authoritative.

Required explicit endpoints:

```text
POST /vibecomfy/agent-edit/accept
POST /vibecomfy/agent-edit/reject
```

Request:

```json
{
  "session_id": "abc123",
  "turn_id": "0003",
  "graph": {},
  "client_graph_hash": "sha256-of-current-canvas"
}
```

Every follow-up request should still include the full current browser graph,
serialized at submit time, as a recovery/source-of-truth check. That graph does
not replace explicit acceptance state; it lets the backend detect divergence and
avoid trusting stale session files.

### Baseline And Concurrency

- The frontend must serialize `app.canvas.graph.serialize()` immediately before
  submitting the request, not when the modal/panel opens.
- Each response must echo `baseline_turn_id` and `client_graph_hash`. The
  frontend must discard or warn on responses whose baseline no longer matches
  the current canvas/session state.
- Each request must include a client-generated `idempotency_key`. The backend
  should deduplicate by `(session_id, idempotency_key)` or reject conflicting
  in-flight requests.
- Two simultaneous requests for the same `session_id` must be serialized or
  rejected with a conflict response. They must not race on `current.py`,
  `candidate.ui.json`, or `messages.jsonl`.
- The browser graph submitted with the request is the source of truth for graph
  state. Backend accepted state is advisory context only when hashes match. On
  mismatch, regenerate Python from the submitted UI JSON and record baseline
  divergence in the audit.
- The frontend must mark the canvas dirty if the user edits it while a turn is
  pending. A stale response may still show the agent message, but Apply must be
  blocked unless the user explicitly chooses an overwrite path.

### Apply-Safety Gates

Apply safety is not one boolean derived from Python load success. A successful
turn should record these named checks:

| Gate | Meaning |
|---|---|
| `python_load_ok` | generated Python parsed and loaded through the restricted agent-generated path |
| `ir_validate_ok` | `VibeWorkflow` structural validation passed |
| `ui_emit_ok` | UI JSON emission completed without refusal or editor-ahead errors |
| `ui_fidelity_ok` | required editor state was preserved or intentionally transformed |
| `ui_load_safe_ok` | candidate is safe to load into the browser canvas |
| `queue_validate_ok` | candidate is safe to send to ComfyUI queue |
| `state_match_ok` | response still matches the submitted baseline/hash |

`canvas_apply_allowed` requires `python_load_ok`, `ir_validate_ok`,
`ui_emit_ok`, `ui_fidelity_ok`, `ui_load_safe_ok`, and `state_match_ok`.
`queue_allowed` additionally requires `queue_validate_ok` and no unresolved
editor-only intent nodes. An empty, stale, or degraded schema/object_info
provider is not proof of queueability. Unknown custom nodes, unresolved
`widget_N` fields, missing object_info, unresolved model assets, or editor-only
furniture should block Queue while possibly still allowing Canvas Apply.

Queue confidence should be explicit:

| Level | Meaning |
|---|---|
| `unknown_schema_blocks_queue` | graph may be canvas-safe, but schema/object_info is absent or stale |
| `schema_confident` | node classes, widgets, sockets, and model picker values match trusted schema |
| `runtime_verified` | graph has also passed a real ComfyUI/API conversion or queue oracle where available |

`queue_allowed: true` requires at least `schema_confident`; high-risk cases
should require `runtime_verified`.

### UI Fidelity Contract

The round-trip must classify editor state as preserved, intentionally changed,
or refused before a candidate can be canvas-applyable. The protected surface
includes:

- stable node identity via a persistent `vibecomfy_uid` stored in node
  properties; LiteGraph numeric ids are transient and must not be the diff key;
- positions and size;
- links, widgets, and widget payload shape;
- groups, notes, reroutes, get/set helpers, bypass/mute state;
- `properties`, extension metadata, and `properties.vibecomfy`;
- subgraph definitions and internal topology;
- custom-node class types and schema confidence;
- model picker values and unresolved `widget_N` aliases.

If the backend cannot prove safe preservation for editor-only furniture, it
should return a classified failure or set `canvas_apply_allowed: false`.

### Audit Download Route

```text
GET /vibecomfy/agent-edit/audit?session_id=<id>&turn_id=<id>
```

The route should return `application/json` with `Content-Disposition:
attachment`. Unknown sessions or turns return 404. Unreadable artifacts return
  a classified failure. The route must serve the redacted audit artifact, never
  raw prompt headers or environment material.

### Closed Failure Enum Table

Every failure the backend returns must use one of the `kind` values below. The
columns encode the contract the frontend and agent rely on: no ad-hoc error
strings, no ambiguous retry advice, no silent graph mutation.

| stage | kind | retry safe | user action | graph unchanged | canvas apply allowed | queue allowed | agent_failure_context | user_facing_message |
|---|---|---|---|---|---|---|---|---|
| `load_python` | `SyntaxError` | yes | wait and retry; agent should fix syntax | true | false | false | `{explanation, suggested_repair}` — the AST parse line/offset, what the parser expected, and likely fix | "The generated Python has a syntax error and was not loaded. The graph is unchanged." |
| `load_python` | `ASTScanFailure` | yes | wait and retry; agent must remove forbidden constructs | true | false | false | `{explanation, forbidden_construct, location, suggested_repair}` — which forbidden import/call/dunder was found and where | "The generated Python uses a forbidden operation and was not loaded. The graph is unchanged." |
| `load_python` | `OversizedPayload` | no | reduce scope or split request; graph too large for current context window | true | false | false | `{explanation, size_bytes, limit_bytes}` — actual vs limit | "The generated Python is too large to load safely and was rejected. The graph is unchanged." |
| `agent_response` | `MalformedModelJSON` | yes | wait and retry; model response did not parse as valid JSON | true | false | false | `{explanation, parse_error, raw_preview_truncated}` — JSON parse error plus truncated preview for debugging | "The model response could not be parsed. The graph is unchanged." |
| `agent_response` | `MissingRequiredField` | yes | wait and retry; model response missing `python` or `message` | true | false | false | `{explanation, missing_field}` — which required field was absent | "The model response is incomplete. The graph is unchanged." |
| `agent_response` | `ProviderError` | yes (same route) or no (different route) | try again or switch route; provider returned non-200 or connection failed | true | false | false | `{explanation, provider_id, route, http_status, retry_after_seconds}` — provider/network detail | "The model provider is temporarily unavailable. The graph is unchanged." |
| `agent_response` | `AuthError` | no (without credential change) | check credentials in Agent Settings; provider returned 401/403 | true | false | false | `{explanation, provider_id, route, http_status}` — auth failure detail (no keys) | "The model provider rejected authentication. Check your credentials in Agent Settings." |
| `agent_response` | `TimeoutError` | yes | retry with same request; model did not respond in time | true | false | false | `{explanation, timeout_seconds}` — configured timeout | "The model did not respond in time. The graph is unchanged." |
| `validate` | `ValidationError` | yes | agent should fix structural issues; user sees what broke | true | false | false | `{explanation, violations[], suggested_repair}` — list of validation failures with node/field detail | "The edited workflow has validation errors and was not applied. See details." |
| `validate` | `UnsatisfiedInputError` | yes | agent should restore or provide missing required inputs | true | false | false | `{explanation, missing_inputs[], suggested_repair}` — which nodes lack required inputs | "Some nodes are missing required inputs. The graph is unchanged." |
| `emit` | `RefusedEmit` | yes | agent must avoid editing protected editor state; user may manually adjust | true | false | false | `{explanation, refused_items[], suggested_repair}` — which editor-owned items would be destroyed | "The candidate graph would destroy editor state and was blocked. The graph is unchanged." |
| `emit` | `EditorAheadConflict` | no (explicit user choice needed) | user must choose: keep editor changes or overwrite with candidate | true | false | false | `{explanation, conflicting_items[], resolution_options}` — which items conflict between editor and candidate | "The editor has changes that conflict with the candidate. Choose keep or overwrite." |
| `ingest` | `StaleStateMismatch` | no | resubmit from current canvas; baseline hash does not match | true | false | false | `{explanation, submitted_hash, expected_hash}` — hash mismatch detail | "The submitted graph no longer matches the current canvas. Resubmit." |
| `ingest` | `UnsupportedNonDAG` | no | reformulate as static graph edit; custom code/loops/branches not supported in v1 | true | false | false | `{explanation, unsupported_construct, fallback_suggestion}` — what construct was requested and a static-graph alternative | "This request requires custom code or control flow that is not yet supported. Try a static graph edit." |
| `queue_validate` | `SchemaLessQueueBlocker` | no (until schema available) | inspect candidate on canvas; Queue blocked but Canvas Apply allowed when other gates pass | depends on other gates | depends on other gates | false | `{explanation, missing_schema_nodes[], queue_confidence}` — which node classes lack trusted schema | "Some node schemas are unavailable, so Queue is blocked. You can still inspect the graph." |
| `queue_validate` | `LowConfidenceQueueBlocker` | no (until providers confirmed) | inspect candidate on canvas; degraded schema/provider means Queue is unsafe | depends on other gates | depends on other gates | false | `{explanation, degraded_providers[], queue_confidence}` — which providers are degraded and why | "Schema or provider confidence is too low for safe queueing. Canvas Apply may still be available." |
| `queue_validate` | `EditorOnlyNodeQueueBlocker` | no (until nodes lowered or removed) | remove or lower editor-only `vibecomfy.*` nodes before queueing | false (graph may contain editor-only nodes for inspection) | true (if other gates pass) | false | `{explanation, blocking_nodes[], lowering_options}` — which editor-only nodes block Queue and possible remedies | "Editor-only nodes are present and block Queue. You can inspect them on the canvas." |
| `audit` | `AuditWriteWarning` | n/a (non-blocking) | no action needed; audit was written but with non-fatal issues | false (candidate was computed) | depends on other gates | depends on other gates | `{explanation, warning_detail}` — what was degraded in audit capture | "The audit file was written with warnings. All graph decisions are preserved." |
| `audit` | `AuditWriteFailure` | no (cannot proceed without audit) | report issue; turn cannot complete without a verifiable audit artifact | true (candidate not applied) | false | false | `{explanation, write_error}` — why the audit file could not be written | "The audit file could not be written and the turn was aborted. The graph is unchanged." |

**Column contract:**

- **stage:** The pipeline stage that classified the failure. Stages are ordered:
  `ingest` → `convert` → `agent_response` → `load_python` → `validate` →
  `emit` → `queue_validate` → `audit`. A failure at one stage prevents later
  stages from running. `audit` failures are special: `AuditWriteWarning` is
  non-blocking (the candidate graph is still valid), while `AuditWriteFailure`
  aborts the turn.

- **kind:** Stable string identifier. Frontends and agents may branch on `kind`.
  New `kind` values must be added to this table with full column semantics before
  they can appear in a response.

- **retry safe:** Whether the same request can be retried without the user
  changing anything. `yes` means the agent can retry autonomously within
  reasonable limits. `no` means the user or environment must change first
  (credentials, canvas state, scope, or explicit overwrite choice).

- **user action:** What the user sees and does. This is a plain-English summary,
  not implementation guidance.

- **graph unchanged:** Whether the browser canvas graph was not mutated by this
  turn. `true` means the canvas is exactly as it was before the request. `false`
  means the candidate graph may be partially visible for inspection but was not
  applied. No failure may mutate the canvas without explicit user Apply.

- **canvas apply allowed:** Whether the candidate graph may be loaded into the
  browser canvas for inspection, even if Queue is blocked. `depends on other
  gates` means the decision is not determined by this failure alone.

- **queue allowed:** Whether the candidate graph may be sent to the ComfyUI
  execution queue. Always `false` on failure except for `AuditWriteWarning`
  where it depends on the other apply-safety gates.

- **agent_failure_context:** Structured JSON with `explanation` (always), plus
  kind-specific fields. This is the primary debugging surface for the agent on
  its next turn. Fields listed are required when the kind is returned; the agent
  may assume their presence.

- **user_facing_message:** A plain-English sentence suitable for display in the
  failure card. Frontends must show this, not raw `kind` or `explanation`. The
  message must include "The graph is unchanged." when `graph_unchanged` is true.

## Provider Credentials And Agent Routing

Model execution should go through Arnold, not through separate VibeComfy-owned
DeepSeek / Claude / Codex clients. Arnold already owns provider resolution,
credential discovery, API mode, OAuth stores, model catalogs, and telemetry.
VibeComfy should ask Arnold for a runtime route and then call Arnold's
single-turn agent path.

The public VibeComfy execution provider is:

```text
provider_id = "arnold"
```

DeepSeek, Claude, Codex, Fireworks, OpenRouter, and other model routes are
Arnold internals. The frontend may expose an advanced "Arnold route" override,
but it must still execute through Arnold:

| Browser label | Arnold request | Credential source | Execution path |
|---|---|---|---|
| Arnold default | `auto` | Arnold/Hermes active provider, config, env | `resolve_runtime_provider(...)` -> `AIAgent` |
| DeepSeek via Arnold | `deepseek` | pasted key saved as `DEEPSEEK_API_KEY` or existing Arnold/Hermes key | `chat_completions` through Arnold |
| Claude via Arnold | `anthropic` | existing local Claude / Arnold / Hermes auth only | `anthropic_messages` through Arnold |
| Codex via Arnold | `openai-codex` | existing local Codex / Arnold / Hermes auth only | `codex_responses` through Arnold |

Frontend shape:

- an Agent Settings affordance inside the VibeComfy panel;
- execution label: Arnold;
- optional route selector: Arnold default, DeepSeek via Arnold, Claude via
  Arnold, Codex via Arnold;
- model text field or curated model select populated from Arnold/Hermes
  provider catalogs when available;
- API key password field only for DeepSeek. Claude and Codex must not accept
  pasted keys in the VibeComfy UI; they use the local machine's Arnold/Hermes
  auth state;
- Claude route warning: using local Claude/Claude Code automation may violate
  Anthropic or Claude Code terms depending on the user's account, plan, and
  usage. The UI should require explicit acknowledgement before first use;
- status row showing Arnold ready / unavailable, route ready / missing auth /
  last test failed;
- no raw API key in `localStorage`, browser history, URL params, turn history,
  or audit preview.

Backend shape:

```text
GET  /vibecomfy/agent/status
POST /vibecomfy/agent/settings
POST /vibecomfy/agent/test
```

The settings response should expose only redacted status:

```json
{
  "provider_id": "arnold",
  "route": "auto",
  "arnold": {
    "available": true,
    "agent_root": "/private/tmp/arnold-target/megaplan/agent",
    "provider_actual": "openai-codex",
    "model_actual": "gpt-5.3-codex",
    "api_mode": "codex_responses",
    "credential_source": "hermes-auth-store"
  },
  "routes": {
    "auto": { "configured": true },
    "deepseek": { "configured": true, "env_key": "DEEPSEEK_API_KEY" },
    "anthropic": {
      "configured": false,
      "credential_source": "local_arnold_or_claude_auth",
      "tos_warning_required": true
    },
    "openai-codex": { "configured": true, "credential_source": "hermes-auth-store" }
  },
  "warnings": []
}
```

For execution, VibeComfy should call Arnold in this order:

```python
runtime = resolve_runtime_provider(requested=route)
agent = AIAgent(
    provider=runtime["provider"],
    api_mode=runtime["api_mode"],
    base_url=runtime["base_url"],
    api_key=runtime["api_key"],
    model=model,
    quiet_mode=True,
    skip_context_files=True,
    skip_memory=True,
    enabled_toolsets=[],
)
result = agent.run_conversation(prompt, response_format={"type": "json_object"})
```

Do not instantiate `AIAgent` bare, because its defaults can route through the
wrong provider. Always use Arnold's `resolve_runtime_provider(...)` first.

Credential storage should reuse Arnold/Hermes conventions:

- the only frontend-pasted model key is DeepSeek, saved as `DEEPSEEK_API_KEY`
  in `~/.hermes/.env`, written with Arnold/Hermes helper semantics, preserving
  unrelated keys and file permissions;
- non-secret provider/model preference belongs in `~/.hermes/config.yaml`;
- Codex OAuth belongs in `~/.hermes/auth.json`; VibeComfy should not write
  Codex OAuth tokens itself and should not accept a Codex API key in the
  browser;
- existing Codex CLI auth in `~/.codex/auth.json` may be imported by Arnold;
- Claude may resolve through `ANTHROPIC_API_KEY`, `ANTHROPIC_TOKEN`,
  `CLAUDE_CODE_OAUTH_TOKEN`, Hermes OAuth, or Claude Code credentials; VibeComfy
  should not duplicate that logic and should not accept a Claude key in the
  browser.

The route should accept a DeepSeek key only over same-origin local ComfyUI HTTP;
it should never echo a key back. The audit file should record Arnold provider,
model, API mode, credential source, and redaction category, but not credential
values. For Claude, the audit and UI should record that the user acknowledged
the route warning, but not make any legal claim that the route is allowed.

Frozen S0 provider/route decisions:

- **Public provider id:** `arnold`.
- **Route override ids:** `auto`, `deepseek`, `anthropic`, `openai-codex`.
- **Default route:** `auto` (Arnold resolves the active provider).
- **DeepSeek is the only route** where users can paste an API key in the
  VibeComfy UI. Claude and Codex must use local Arnold/Hermes/CLI auth
  discovery and must not accept a pasted key in the browser. Missing-auth
  guidance is surfaced through the Agent Settings panel for each route.
- **Claude warning text (exact):**
  > Claude routes use local Claude/Claude Code automation discovered through
  > Arnold. Depending on your account, organization policy, and usage, this
  > may violate Anthropic or Claude Code terms. Continue only if you are
  > authorized to use this route.
- **Claude acknowledgement:** the warning appears the first time a user
  selects a Claude route in a browser profile and again whenever the resolved
  Claude route id changes. The user must check "I understand and am authorized
  to use this Claude route" before Test or Submit is enabled for that route.
  The acknowledgement state is recorded in audit metadata (boolean, timestamp,
  route id), not as a credential.
- **Test behavior (v1):** validate Arnold runtime resolution only; no model
  call. Test confirms that Arnold can resolve a provider, locate credentials,
  and report provider/model/API-mode without sending any prompt or spending
  tokens.
- **Audit capture:** every turn records provider id, requested route, resolved
  provider, model, API mode, credential source, redaction category, and Claude
  acknowledgement state. No credential values are written to the audit.

## Custom Code And Control Flow

There are three different cases, and they should not be conflated.

1. **Static graph edits:** prompt changes, widget changes, node insertion,
   rewiring, patching, and static fan-out. These are normal `VibeWorkflow` edits
   and can be validated as a ComfyUI DAG.
2. **Python orchestration outside one graph:** repeated `.run()`, image-to-video
   chains, human approval gates, and result-dependent branching. These can exist
   today as Python recipes/scripts, but they are not one ComfyUI graph and
   should not be represented as if they are directly queueable in a single
   prompt. In the first canvas product, represent this as a generated
  recipe/staged plan outside the canvas, an inspectable `vibecomfy.code` block
  when useful, or a classified rejection. Defer `vibecomfy.workflowref` until
  there is a concrete staged-workflow/VibeFlow state model.
3. **On-graph intent nodes:** rendered custom code, `for` loops, branches, and
   workflow references shown inside ComfyUI as `vibecomfy.*` nodes. This is the
   direction described in `docs/python_on_the_graph.md`, but it is not shipped.

For a maximal viable text-to-graph product, we need an explicit boundary and a
fallback representation:

- v1 may reject requests that require custom code, dynamic loops, branches, or
  multi-workflow orchestration, with a clear failure explanation;
- static loops with known bounds should lower to repeated ordinary graph
  structure before Queue; a request like "run this for these five seeds" should
  render five concrete executions, not a fake loop node, when the body can be
  duplicated safely;
- requests that cannot honestly lower into ordinary ComfyUI nodes should become
  special editable intent nodes where possible, not disappear into invisible
  backend magic;
- any `vibecomfy.code`, `vibecomfy.loop`, or future specific `vibecomfy.*`
  node must carry typed I/O, a persistent `vibecomfy_uid`, and intent metadata;
- validation must prove either that the construct was lowered to a valid
  static ComfyUI DAG, or that the remaining opaque intent node is editor-only
  and cannot be queued as a normal ComfyUI API graph;
- Queue must stay disabled for graphs containing unresolved `vibecomfy.*`
  control-flow/code nodes unless there is a runtime implementation and a
  validator for that node kind. Canvas Apply may still be enabled when the
  intent node is editor-valid, because the point is to place an inspectable,
  manually editable representation on the graph.

### Editable Intent Nodes

When the user asks for something richer than a static ComfyUI DAG, the product
should have a visible, inspectable representation rather than pretending the
graph is ordinary.

Examples:

- `vibecomfy.code`: an editable code block with typed inputs and outputs.
- `vibecomfy.loop`: a loop band or paired start/end node with editable iterator
  spec, body scope, max-iteration guard, and typed carried values.
- `vibecomfy.branch`: a conditional with editable predicate and explicit true /
  false outputs.
- `vibecomfy.workflowref`: deferred. It should not ship until there is a
  concrete staged-workflow/VibeFlow model.

Programmatic emitters should construct these metadata blobs with
`intent_node_properties(...)` rather than hand-rolling
`properties.vibecomfy`.

**Frozen architecture:** Editor-only `vibecomfy.*` nodes are extension-owned UI
nodes. They register in `NODE_CLASS_MAPPINGS` as real ComfyUI custom node
classes so `app.loadGraphData()` can load them predictably. They expose
`object_info` entries with `properties.vibecomfy` carrying intent semantics
(kind, io, spec, status). Every shipped intent node carries
`vibecomfy_editor_only=true` metadata on the node instance. They are
non-executable: the registered `execute()` method returns a classified
error or a controlled no-op. Queue is blocked for graphs containing any
unresolved `vibecomfy.*` node unless the node has been lowered to
runtime-backed normal nodes and the lowering evidence is recorded.

> **Premortem traceability:** This resolves kickoff blocker 7 (Queue blocking
> must reach native Queue path) and the S0 sprint amendment defining whether
> editor-only `vibecomfy.*` nodes are extension-owned UI nodes, normal custom
> nodes, or both (see premortem incorporation table).

These nodes are not "normal ComfyUI nodes" unless a runtime implementation
exists. They are editor-visible intent, but their registration surface is
fixed: `NODE_CLASS_MAPPINGS`, `INPUT_TYPES`, `RETURN_TYPES`, `CATEGORY`,
`object_info`, `properties.vibecomfy` metadata, and a controlled no-op/error
execution path that prevents accidental Queue success. Their UI should make
that status clear:

- show the code/spec inline with an Edit button;
- show typed input/output sockets;
- show whether the node is `lowered`, `runtime-backed`, or `editor-only`;
- show why Queue is blocked if unresolved;
- include the intent source in the per-turn audit file;
- allow manual edits, but re-run validation after any edit.

Validation for these nodes has two layers:

1. **Intent validation:** the node has a known `vibecomfy.*` kind, valid metadata
   shape, stable uid, typed sockets, bounded code/spec size, and no forbidden
   operations.
2. **Execution validation:** either the intent has been lowered to a static DAG,
   or a runtime-backed node exists and schema validation says the graph can be
   queued.

So if the user asks for "run this prompt for ten seeds", the agent should first
try to make the graph literally contain ten queueable executions. It can:

- statically unroll ten graph copies when the loop bound and body are known;
- create a visible `vibecomfy.loop` intent node marked editor-only / not
  queueable yet when the loop cannot be safely duplicated;
- or return an orchestration-not-supported explanation.

It should not invent a loop node that looks valid but fails at queue time.
The visible loop node is a fallback representation for non-lowerable logic, not
the preferred rendering for a simple bounded sweep.

### Expressiveness Boundary

The agent must classify requests that cannot honestly become one queueable
ComfyUI DAG:

| Request class | Product behavior |
|---|---|
| Multi-workflow chain, e.g. image -> video | generated recipe/staged plan or explain that this needs multiple executions; defer `vibecomfy.workflowref` until a staged-workflow model exists |
| Runtime result decides next action | `vibecomfy.branch` if runtime-backed; otherwise editor-only or reject |
| External file/folder resolved at execution time | editor-only `vibecomfy.code` / staged plan; folder watching is outside graph |
| Async jobs, polling, callbacks | editor-only `vibecomfy.code` / generated recipe when useful; otherwise reject as text-to-graph v1 |
| Dynamic batch size / CSV / per-item retry | static unroll if bounded and known; otherwise `vibecomfy.loop` intent or reject |
| Retry/backoff on transient failures | generated recipe/staged plan; not a queueable graph node in v1 |
| Model availability / download-driven switching | pre-queue orchestration, not graph execution |
| Human approval between stages | split into multiple executions with a manual gate |
| Webhooks, notifications, external APIs | side-effect intent node only if runtime/sandbox exists; otherwise reject |
| Quality-threshold refinement loops | `vibecomfy.loop` only with runtime-backed predicate support; otherwise reject |

The rule: lower to static nodes when truthful, create visible code/intent blocks
when useful but not queueable, or reject with a clear explanation. Never emit a
normal graph that misrepresents execution semantics.

Code blocks are the generic abstraction for logic that is meaningful to inspect
but cannot be expressed as a native ComfyUI DAG. A `vibecomfy.code` block should
carry typed inputs/outputs and a constrained code/spec payload. More specific
nodes such as `vibecomfy.loop` and `vibecomfy.branch` are preferred when the
shape is known enough to render better than a generic code block.

Complexity budget: ship the generic `vibecomfy.code` abstraction plus the first
specific shape that removes real ambiguity. `vibecomfy.loop` earns its place for
bounded sweeps and repeatable body scopes. `vibecomfy.workflowref`,
`vibecomfy.branch`, and runtime-backed nodes should stay deferred until user
requests prove that code blocks, static lowering, and generated staged recipes
are not enough.

### Intent Node Frontend

Special nodes need their own UI treatment. The visual language is frozen:

- **Status badges** (rendered on the node body, not a floating overlay):
  | Badge | CSS class | Meaning |
  |---|---|---|
  | `Editor-only` | `vc-status-editor-only` | Valid intent, no runtime; Queue blocked |
  | `Lowered` | `vc-status-lowered` | Intent lowered to native nodes; Queue allowed after re-validation |
  | `Runtime-backed` | `vc-status-runtime-backed` | Concrete runtime node exists; Queue allowed |
  | `Invalid` | `vc-status-invalid` | Unknown kind, missing metadata, or unsafe; Apply and Queue blocked |
- **Inline edit control:** label `Edit spec` for structured intent nodes
  (`vibecomfy.loop`, `vibecomfy.branch`); label `Edit code` only for
  `vibecomfy.code` and audit/debug code views. Edit state is dirty-tracked
  and triggers re-validation on save.
- **Typed socket labels:** rendered from `properties.vibecomfy.io` (the
  canonical typed I/O definition), not inferred from `object_info`. Socket
  labels must survive full export/import round-trips.
- **Canvas-level and panel-level Apply/Queue blockers** for editor-only or
  invalid nodes. The panel must show which specific node(s) block Queue
  and why.
- **Intent-level diffing** in turn review: code diff for `vibecomfy.code`,
  loop-spec diff for `vibecomfy.loop`, predicate diff for `vibecomfy.branch`.
  Do not reduce intent changes to raw widget-level diffs.
- **Full undo preservation of `properties.vibecomfy`:** undo/snapshot/restore
  must preserve the entire `properties.vibecomfy` object exactly, including
  kind, io, spec, status, and any future extension fields.
- **Audit inclusion** of the full intent metadata (kind, io, spec, status,
  uid, lowered evidence if applicable).

The frontend must make editor-only status impossible to miss. A user should not
see a node on the canvas and assume it can be queued if it is only an editable
intent placeholder.

### Intent Validation And Queueability

Validation should distinguish these states:

| Status | Meaning | Apply / Queue |
|---|---|---|
| `editor-valid` | known `vibecomfy.*` kind, valid metadata, typed I/O, no runtime | Canvas Apply allowed, Queue blocked |
| `lowerable` | can become a static DAG | lower first, then validate again |
| `runtime-backed` | concrete runtime node exists and schema knows it | Canvas Apply and Queue allowed after validation |
| `queueable` | ordinary graph passes schema + refusal gates | Canvas Apply and Queue allowed |
| `blocked` | unknown type, missing required input, unsafe code, emit/refusal error | Canvas Apply and Queue blocked |

For agent-edited graphs, `canvas_apply_allowed` and `queue_allowed` are separate
gates:

- `canvas_apply_allowed` is true when the candidate can be safely loaded into
  the editor without losing work or corrupting graph state. Editor-valid intent
  nodes are allowed here.
- `queue_allowed` is true only when there are no `editor-valid` or `blocked`
  nodes, no unresolved `vibecomfy.*` intents, and the schema/refusal gates pass.

An empty or degraded schema provider should not be treated as proof of validity
for a non-trivial graph.

### Agent Decision Policy

Before editing, the agent should decide:

1. Is the user request concrete enough? If not, ask or return a clarification
   failure rather than guessing.
2. Can the change be a normal static graph edit? If yes, edit and validate.
3. Can it be statically lowered, such as a bounded seed sweep or fixed prompt
   batch? If yes, lower by duplicating the affected native graph structure,
   preserve intent metadata, and validate the lowered graph.
4. Can it be represented as a useful editable intent node? If yes, create the
   most specific node available; use `vibecomfy.code` as the generic fallback.
   Mark it editor-only unless runtime-backed, allow Canvas Apply if the intent
   is valid, and block Queue. Metadata is explicit: every shipped intent node
   carries `properties.vibecomfy_uid`, `properties.vibecomfy.kind`,
   `properties.vibecomfy.intent`, and typed `properties.vibecomfy.io.inputs` /
   `outputs`. `vibecomfy.code` source/spec payloads stay within 16 KiB, and
   `vibecomfy.loop` must declare a bounded `count` / `iterations` / `over`
   contract with no more than 128 iterations.
5. Does it require orchestration outside one graph? Represent that honestly as
   `vibecomfy.code` when an inspectable block is useful, or as a Python recipe /
   staged workflow plan outside the canvas. Defer `vibecomfy.workflowref` until
   there is a real staged-workflow model. Do not create a normal queueable graph
   that hides the multi-execution boundary.
6. If none of those is honest, reject with `agent_failure_context` explaining
   why the graph is unchanged and what the user can try next.

## Per-Turn Audit

Every `/vibecomfy/agent-edit` turn should write one canonical audit artifact,
even when the turn fails:

```text
out/editor_sessions/<session_id>/<turn_id>/audit.json
```

This is the file we use to deeply audit what happened after the fact. It should
be stable JSON, downloadable from the frontend, and complete enough to
reconstruct the turn without chasing scattered files.

The audit file should include:

- `schema_version`;
- `session_id`, `turn_id`, timestamps, and duration per stage;
- task text, graph size, node count, frontend version if provided;
- original UI JSON path, SHA-256 hash, byte count, and bounded embedded copy;
- generated Python-before path/hash and bounded embedded text;
- model request metadata: provider, model, temperature, message hashes, and
  prompt byte/token estimates;
- model response metadata: raw response path/hash, parsed message, parsed
  Python-after path/hash, and bounded embedded text;
- validation output: `ValidationReport`, schema-less warnings, hard errors;
- emit output: candidate UI JSON path/hash, change report, felt report, refusal
  details if any;
- intent-node output: for every `vibecomfy.*` node, uid, kind, status,
  bounded/redacted code or spec, spec hash, typed I/O, validation result,
  runtime-backed flag, and lowered evidence if it lowered to native nodes;
- orchestration output: stage list, artifact-carrying edges, whether the turn
  represents a single prompt, and why it could not be lowered if applicable;
- rejection output: non-DAG classification, fallback offered, fallback node
  uids if any, suggested alternatives, and retry-safety;
- API response envelope returned to the browser;
- acceptance state: `candidate`, `accepted`, `rejected`, or `unknown`;
- redaction metadata and any audit write warnings.

The full raw model request and full raw model response should be written to
turn-scoped files and referenced by hash from `audit.json`. Inline previews are
for readability only; they are not the audit source of truth.

The audit should also include the named apply-safety gates, frontend action
evidence for accept/reject/apply, and acceptance state transitions. A future
tamper-evidence layer may add a previous-audit hash chain and server-side
signature, but S1 should at least make the schema versioned and deterministic.

It must not leak API keys, authorization headers, raw environment variables, or
unbounded payloads. Large fields should be represented by path, hash, byte
count, and a truncated preview.

Bounded embedded copies should have a concrete cap. Default target: inline a
field only when its serialized value is at most 4096 bytes; otherwise include
`path`, `sha256`, `byte_count`, and a 512-character preview. Redacted values
should be replaced with `"<REDACTED>"`, and the audit should record which
redaction categories were applied.

Frontend requirements:

- show "Download audit JSON" in both success and failure modals;
- expose session id, turn id, and audit path/url in the debug disclosure;
- allow downloading the audit without applying the graph;
- surface an `audit_error` warning if the backend could not write the audit
  artifact.

## Frontend work

The frontend does not need a Python editor.

It does need a real text-to-graph product surface, not only the current proof
modal. The user should be able to stay in ComfyUI, make repeated requests, see
what changed, understand failures, download audits, and undo without hunting
through developer logs.

Required frontend capabilities:

1. **Persistent entry point:** keep the command/menu item, but open a reusable
   VibeComfy panel or durable modal that supports multiple turns instead of
   one throwaway prompt.
2. **Task composer:** textarea, submit button, keyboard shortcut, disabled
   state while running, clear empty-task validation, and a way to cancel/close
   without losing the current graph.
3. **Current graph snapshot:** serialize the latest browser graph at submit
   time. Follow-up turns must use the graph that is actually on the canvas, not
   a stale session candidate.
4. **Progress state:** show the turn as pending, with stage labels when the
   backend exposes them. Prevent double-submits for the same turn.
5. **Success summary:** show the agent message, compact changed-node summary,
   warnings, and whether Canvas Apply and Queue are allowed.
6. **Failure communication:** show `agent_failure_context.explanation`,
   retry-safety, suggested repair, and graph-unchanged status. A failure should
   feel like an agent explaining what went wrong, not a JSON exception.
7. **Candidate preview:** before Apply, show a textual/structured diff and
   affected stable uids. Do not call `app.loadGraphData()` just to preview:
   it replaces the real canvas. If visual preview is required, make it an
   explicit destructive-preview action that snapshots the current graph and can
   immediately restore it.
8. **Safe Apply:** enable Apply only when `ok && canvas_apply_allowed`; after
   Apply, push the previous graph onto a local "Undo Last Apply" stack and
   update accepted-state bookkeeping.
9. **Cancel / reject:** let the user dismiss a candidate without changing the
   canvas. Rejected candidates must not silently become the next baseline.
10. **Undo:** provide a visible Undo for the last applied graph change. This can
   be browser-local for v1, but it must work immediately after Apply.
11. **Turn history:** show at least the current session's turns with status:
    pending, applyable candidate, applied, rejected, failed. Each row should
    expose message, warnings, and audit download.
12. **Audit download:** show "Download audit JSON" on every turn, including
    failed turns, using the backend `audit.download_url` or a generated blob
    fallback if the backend returns the audit payload directly.
13. **Debug disclosure:** expose session id, turn id, artifact paths, raw
    report, and audit path/url without making debug data the primary UX.
14. **Toast/status integration:** success, failure, apply, reject, undo, and
    audit-download failures should surface through ComfyUI's toast/status
    affordances when available.
15. **Native Queue coordination:** if the current graph is not queueable, the
    panel and the native Queue path should make that status clear and prevent a
    confusing raw queue failure where possible.
16. **Frontend error boundaries:** serialization errors, network errors,
    malformed backend responses, and `app.loadGraphData()` failures should
    render in the panel with audit/debug context where possible.
17. **Accessibility and layout:** the panel should be keyboard usable, avoid
    covering critical canvas controls unnecessarily, and keep long messages,
    warnings, and node ids readable without overflowing.
18. **Browser tests:** Playwright coverage should verify command registration,
    task submission, progress state, success Apply, non-applyable failure,
    Undo, turn history, and audit download.

Frontend decisions (frozen for S1/S2 implementation):

- **Primary surface:** persistent right side panel, not durable modal. The panel
  anchors to the ComfyUI canvas edge and resists dismissal. A thin toggle tab
  along the right edge opens and closes it without blocking the canvas.
- **Turn history:** collapsed by default with the current turn always visible.
  Historical turns expand on click; the current/latest turn stays open.
- **Pre-Apply preview:** structured diff only for v1. No destructive canvas
  preview (replace-then-restore) unless explicitly invoked later with a
  "Preview on canvas" button that snapshots the current graph first and
  restores it on preview dismiss.
- **Apply semantics:** `graph.clear()` + `graph.configure()` with
  snapshot/restore and undo bracketing. Before Apply, the previous graph is
  serialized onto a local undo stack. Apply clears the canvas graph and loads
  the candidate. Undo restores from the undo stack. See
  `docs/python_on_the_graph.md:351` for the snapshot/restore pattern.
- **Native Queue coordination:** the extension intercepts the Queue action
  where possible and warns or blocks when the current graph is not queueable
  (editor-only intent nodes present, schema confidence below `schema_confident`,
  unresolved `widget_N` payloads, or the candidate was never accepted). The
  panel surface also displays a non-dismissible Queue status row when the graph
  is non-queueable.
- **Keyboard:**
  - `Enter` inserts a newline in the task textarea.
  - `Cmd/Ctrl-Enter` submits the task.
  - `Esc` closes the candidate review (rejects if not yet applied) and returns
    focus to the canvas.
  - Undo uses the existing local undo affordance (not a custom keybinding).
- **Mobile/small-window:** desktop-first for v1. The panel collapses below
  900px viewport width; below that breakpoint the extension is inactive and
  the menu item is disabled. Mobile is not supported for v1.

**Node highlight visual values (frozen):**

| Disposition | Label | CSS class | Border | Background tint |
|---|---|---|---|---|
| Added | `Added` | `vc-agent-added` | `#22c55e` | `rgba(34,197,94,0.10)` |
| Edited | `Edited` | `vc-agent-edited` | `#f59e0b` | `rgba(245,158,11,0.12)` |
| Removed | `Removed` | `vc-agent-removed` | `#ef4444` | `rgba(239,68,68,0.10)` |
| Editor-only | `Editor-only` | `vc-agent-editor-only` | `#6366f1` | `rgba(99,102,241,0.10)` |

Removed nodes are rendered only in the diff/review panel, not on the live
canvas, unless an explicit destructive preview is later implemented.

Mandatory browser tests before viability:

- success path enables Apply and calls `app.loadGraphData()` with the returned
  graph;
- failure path shows `agent_failure_context`, disables Apply, and leaves the
  canvas unchanged;
- Undo restores the pre-Apply serialized graph;
- network and malformed-response errors render recoverable panel states;
- audit download works for both success and failure turns;
- two sequential turns show correct statuses in turn history;
- stale response or mismatched baseline is rejected or clearly warned.
- canvas-dirty during pending turn blocks Apply or requires explicit overwrite;
- rapid double-submit creates one in-flight request;
- editor-only intent nodes visibly block Queue.
- real ComfyUI smoke: extension loads in a running ComfyUI instance, opens the
  panel, talks to a stub backend, and can apply a tiny returned graph without
  JavaScript errors.

## Backend implementation plan

1. Stabilize the API envelope with `ok`, `stage`, `kind`,
   `canvas_apply_allowed`, `queue_allowed`, `summary`, `report`, `session_id`,
   and `turn_id`.
2. Split the handler into explicit stages:
   `ingest`, `convert`, `agent`, `load_python`, `validate`, `emit`, `summarize`.
3. Add agent-visible failure context and retry guidance for each classified
   failure stage.
4. Add named apply-safety gates before returning a candidate graph.
5. Make session storage turn-based:
   `out/editor_sessions/<session_id>/<turn_id>/...`.
6. Preserve accepted-state separately from candidate-state.
7. Add a follow-up mode where the submitted browser graph is authoritative and
   latest accepted graph/Python is context only when hashes match.
8. Add atomic writes for all artifacts.
9. Add suspicious-code checks before loading edited Python.
10. Add per-turn `audit.json` writing, redaction, and download route.
11. Replace the proof frontend modal with the durable text-to-graph panel,
    including turn history, safe Apply, Undo, failure communication, and audit
    download.
12. Add tests for each failure stage, session continuation, and audit artifact
    creation on success and failure.
13. Add a real ComfyUI/browser integration check once a local ComfyUI test
    harness is available.

Backend safety gates before Apply can ever be enabled:

- remove any trust bypass that treats model-generated Python as
  `user_confirmed` without inspection;
- run a pre-load suspicious-code check on the generated Python before
  `load_scratchpad()`;
- run `edited_wf.validate(schema_provider=...)` and derive
  `canvas_apply_allowed` from validation, UI fidelity, state match, and hard
  emit/refusal status;
- classify `RefusedEmit`, `EditorAheadError`, validation failures, malformed
  model JSON, network failures, and oversized graphs distinctly;
- reject, lower, or represent custom code/control-flow requests before Queue.
  Editor-valid `vibecomfy.*` code/loop/branch intent nodes may be
  canvas-applyable when their metadata is valid and UI-safe, but they are not
  queueable unless a concrete runtime and validation contract exists for them;
- when using an editable intent node as a fallback, surface its code/spec in the
  frontend and audit artifact, and block queue/apply paths that would treat it
  as an ordinary ComfyUI node;
- write a turn-scoped audit artifact on both success and failure.

## Sequencing

This is bigger than one implementation pass. The work should be staged so each
step leaves the product more truthful and safer than before.

### Sprint 0 — Contract Freeze

Goal: make the target unambiguous before touching more code.

Deliver:

- Python loading derisk spike with a written keep/kill decision for
  model-edited Python vs structured IR patch;
- final API envelope for success and failure;
- final meanings for `canvas_apply_allowed`, `queue_allowed`, and legacy
  `apply_allowed`;
- accepted / rejected / unknown turn-state model;
- baseline/hash/idempotency primitives and stale-response behavior;
- named apply-safety gates and UI-fidelity contract;
- closed failure enums with retry/action semantics;
- audit schema v1, including full raw request/response artifact references;
- Arnold-only provider/settings contract, including optional route overrides,
  DeepSeek-only pasted key storage, local Claude/Codex auth detection through
  Arnold, and Claude route warning/acknowledgement semantics;
- frontend UX wireframe: panel shape, turn row, success card, failure card,
  pre-Apply diff, post-Apply canvas highlight, audit download, Undo, native
  Queue coordination, and special-node visual language.

Done when: the doc has no open naming ambiguity around the five key pairs.
All five are resolved:

1. **Apply vs Queue** — `canvas_apply_allowed` (load into editor) vs
   `queue_allowed` (send to execution), defined in Apply-Safety Gates,
   API shape, and frozen frontend decisions.
2. **candidate vs accepted** — candidate is a proposed graph; accepted
   is an explicitly confirmed baseline, defined in Accept/Reject and
   Baseline and Concurrency.
3. **current canvas vs session state** — the submitted browser graph is
   the source of truth; backend accepted state is advisory context only
   when hashes match, defined in Baseline and Concurrency.
4. **editor-valid vs queueable** — editor-valid intent nodes are safe to
   inspect on canvas but block Queue; queueable requires no unresolved
   `vibecomfy.*` intents and schema-confident validation, defined in
   Intent Validation and Queueability.
5. **model-authored Python trust boundary** — model output is loaded as
   `agent_generated` through the restricted AST-gated loader, never as
   `user_confirmed`; defined in Python Loading Derisk Spike, backend
   loop, and the frozen provenance contract.

### Sprint 1 — Apply-Safe Backend Spine

Goal: make the backend unable to return unsafe candidates as applyable.

Deliver:

- stage-based handler: `ingest`, `convert`, `agent_response`, `load_python`,
  `validate`, `emit`, `summarize`, `audit`;
- structured failure envelope for every stage;
- turn-scoped directories;
- atomic turn allocation and idempotency record shape;
- explicit `accept` / `reject` endpoints and accepted-state pointer;
- per-turn `audit.json` on success and failure;
- full raw model request/response artifacts referenced by audit hash;
- suspicious-code pre-scan before loading model-generated Python;
- `agent_generated` scratchpad provenance, not `user_confirmed`;
- explicit named validation/apply-safety gates;
- UI-fidelity diagnostics for positions, groups, notes, reroutes, subgraphs,
  properties, model values, and unresolved `widget_N` payloads;
- Arnold adapter seam plus status endpoint. Settings/key persistence can stay
  minimal in S1 unless it is needed to test the backend path;
- Arnold adapter boundary using `resolve_runtime_provider(...)` followed by
  `AIAgent` in constrained single-turn/no-tool mode;
- `canvas_apply_allowed` / `queue_allowed` derivation;
- tests for malformed model JSON, load failure, validation failure, emit
  refusal, audit write, explicit accept/reject, and successful turn.

Defer: polished frontend, special intent-node rendering, runtime-backed loops.

Done when: a backend-only test can prove bad candidates never come back as
applyable, and every turn has a downloadable audit file path.

### Sprint 2 — Durable Frontend Panel

Goal: replace the throwaway modal with the real text-to-graph surface.

Deliver:

- persistent panel or durable modal;
- Agent Settings UI for Arnold route selection, DeepSeek-only API key entry,
  model choice, save, test status, and Claude warning acknowledgement, without
  storing raw keys in browser persistence;
- submit-time graph serialization;
- `client_graph_hash`, `baseline_turn_id`, and `idempotency_key` in every
  request, even if some backend behavior is hardened later;
- progress state and double-submit prevention;
- success card with changed-node summary;
- failure card with `user_facing_message`, retry guidance, and a debug
  disclosure for `agent_failure_context`;
- pre-Apply structured diff/affected-node preview, without destructively
  loading the candidate graph; post-Apply changed-node feedback on the canvas;
- apply-time dirty-canvas guard for user edits while the agent is running;
- native Queue blocking/warning when the current graph is not queueable;
- safe Canvas Apply and local Undo;
- Reject / dismiss candidate;
- turn history;
- audit download;
- Playwright tests with a fake backend for success, failure, undo, audit, turn
  history, stale response, and network error.

Defer: special node inline editing unless needed for the first user flow.

Done when: the user can run multiple turns in one session without losing track
of what happened, and failure never mutates the canvas.

### Sprint 3 — State Protocol Hardening

Goal: harden the browser/backend state protocol after the mandatory
accept/reject and hash primitives are already present in S1/S2.

Deliver:

- backend enforcement of baseline hash and `baseline_turn_id` checks;
- backend idempotency replay/conflict behavior;
- conflict handling for concurrent turns;
- audit state transitions: `candidate`, `accepted`, `rejected`, `unknown`;
- tests for stale responses, rejected candidate not becoming baseline, and
  manual canvas edits between turns.

Done when: the backend never confuses a rejected candidate with the graph the
user is actually editing.

### Sprint 4 — Editable Intent Nodes, Editor-Only

Goal: handle non-DAG requests visibly without pretending they are queueable.

Deliver:

- metadata contract for `vibecomfy.code`, `vibecomfy.loop`,
  and deferred future shapes. Do not ship `vibecomfy.workflowref` in this
  sprint;
- intent validation: known kind, typed I/O, bounded code/spec, stable uid,
  forbidden-operation checks;
- real registered editor-only ComfyUI node classes for shipped intent nodes, so
  `app.loadGraphData()` can load them predictably;
- frontend rendering: badge, inline code/spec view, queue-blocked explanation,
  intent diff, audit inclusion;
- agent policy: create lowerable loop/code metadata for bounded loops and fixed
  batches, create the most specific intent node available, fall back to
  `vibecomfy.code`, propose a staged recipe, or reject;
- tests proving editor-valid intent nodes can be applied to canvas but block
  Queue.

Defer: executing `vibecomfy.*` nodes. This sprint is about honest
representation and manual editability.

Done when: a request like "loop this over these five seeds" becomes a visible
editor-only lowerable loop/code node with Queue blocked and audit captured.
S5 is what turns that lowerable representation into repeated native graph
structure.

### Sprint 5 — Static Lowering

Goal: make the simplest intent nodes executable by lowering them to ordinary
ComfyUI DAGs.

Deliver:

- bounded loop unroll to repeated native nodes / subgraph;
- intent metadata preserved for round-trip reconstruction;
- lowered evidence in audit;
- validation after lowering;
- frontend presentation of "lowered -> N native nodes";
- tests for static seed sweep and bounded prompt batch.

Done when: known-bounded loops can become queueable without a runtime custom
node, and the canvas makes the repeated executions visible.

### Sprint 6 — Runtime-Backed Intent Nodes

Goal: only after the editor-only and static-lowering stories are solid, add
actual runtime support for dynamic constructs.

Deliver only if still needed:

- concrete runtime implementation for selected `vibecomfy.*` node kind;
- schema/object_info representation;
- queueability validation;
- sandbox/security model for code execution if `vibecomfy.code` is included;
- tests against real ComfyUI queue behavior.

This is not a prerequisite for the first maximal viable text-to-graph product.
The maximal viable product can be excellent with editor-only intent nodes plus
static lowering, as long as it is honest about Queue.

### Recommended Megaplan Shape

If this becomes an actual megaplan run, do not cram all six sprints into one
plan. Use an epic/chain:

1. Contract Freeze + Backend Spine.
2. Frontend Panel + State Protocol.
3. Editable Intent Nodes + Static Lowering.
4. Runtime-backed intent nodes only if the earlier product proves the need.

Profile recommendation:

- Sprint 1: `all-codex/full/medium` or `partnered/full/medium @codex` because
  API/state/safety sequencing matters.
- Sprint 2: `partnered/full/medium @codex` because UX and browser integration
  need judgment but implementation is local.
- Sprint 3: `partnered/full/medium @codex` because stale-state bugs are subtle.
- Sprint 4+: `premium/full/high` only if implementing runtime-backed code nodes
  or sandboxed execution. Editor-only intent nodes and static lowering should
  not need apex-level process.

## Viability Bar

This is shippable as a maximal viable product when:

- a user can open a graph, type a request, preview the result, and apply it;
- failures never mutate the canvas;
- failures are explained in a way the agent can reason about and communicate;
- bad Python or invalid workflows are blocked before Apply;
- follow-up turns operate on the accepted latest graph;
- every turn writes a downloadable `audit.json` that lets us deeply debug the
  turn;
- the frontend has a durable multi-turn surface with safe Apply, Cancel, Undo,
  failure explanations, turn history, and audit downloads;
- the browser test and backend tests cover success and failure paths.

Until those are true, the feature is a working proof path, not the complete
text-to-graph product.
