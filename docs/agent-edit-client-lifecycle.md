# Agent-Edit Client Lifecycle Contract

This document defines the VibeComfy agent-edit panel's client-side lifecycle
contract. Every panel-state mutation for a listed transition flows through the
lifecycle store (`vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`); the
roundtrip module (`vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`) owns
HTTP, graph serialization, canvas mutation, DOM construction, and rendering.

Backend CAS is the single Apply authority. The client sends
`client_structural_graph_hash` only as a backend-parity diagnostic/snapshot in
submit and rebaseline payloads; it never blocks Apply locally.

---

## 1. Phase taxonomy

Every phase transition is driven by the public `outcome.kind` dispatched from a
normalized agent-edit response (see `docs/agent-edit-response-contract.md` for
the full public union of `candidate`, `noop`, `clarify`, `error`). The legacy
internal kinds `edit` and `edit+clarify` are normalized to `candidate` before
dispatch and are never surfaced as public lifecycle outcomes.

| Phase | Meaning | Driven by |
|---|---|---|
| `IDLE` | Shell open, ready for prompt entry | Entry, `noop` outcome, apply/reject success, stop/new-conversation |
| `SUBMITTING` | `POST /vibecomfy/agent-edit` in-flight | Submit start |
| `CLARIFY` | Agent asked a clarification question; no candidate to review | `clarify` outcome |
| `AWAITING_REVIEW` | Candidate received; Apply / Reject available | `candidate` outcome |
| `APPLYING` | Local in-place graph apply or reject in progress (proof-only) | Apply / reject start |
| `ERROR` | Request failed; failure region becomes primary | `error` outcome, preflight failures |

### 1.1 Entry events (not phases)

- **Panel open**: Commands, the edge launcher, and the ComfyUI sidebar-tab
  render callback must all enter through `openAgentPanel()` in
  `vibecomfy_roundtrip.js`. That gateway opens the existing panel shell,
  refreshes `/vibecomfy/agent/status`, starts chat rehydration when a stored
  session id exists, and repaints readiness-consuming regions.
- **Panel closed/reopened**: Re-fetches chat, restores candidate from
  `latest_candidate` only under backend eligibility, resets transient
  in-flight/per-panel state.
- **Page reload / rehydrate**: Runs chat rehydration with epoch gating;
  stale rehydrate responses must not mutate current state.

---

## 2. Lifecycle data ownership model

### 2.1 Store-owned lifecycle fields

These fields are mutated exclusively through the lifecycle store. No ad-hoc
`panel.state.X =` writes outside the store are permitted for these fields.

| Field | Type | Description |
|---|---|---|
| `phase` | `string` | Current `PANEL_STATE` value |
| `sessionId` | `string\|null` | Stable editor session id from backend |
| `turnId` | `string\|null` | Current turn id (e.g. `"0001"`) |
| `baselineTurnId` | `string\|null` | Last accepted turn id from backend |
| `baselineGraphHash` | `string\|null` | Backend CAS structural hash |
| `baselineGraphHashKind` | `string\|null` | Authority kind (always `"structural"` in product) |
| `baselineGraphHashVersion` | `number\|null` | Structural projection version |
| `baselineSource` | `"none"\|"turn"\|"rebaseline"` | Source of current baseline |
| `baselineRebaselineId` | `string\|null` | Rebaseline id when `baselineSource === "rebaseline"` |
| `baselineGraphSourcePath` | `string\|null` | Artifact path for projection drift healing |
| `candidateGraph` | `object\|null` | Candidate ComfyUI UI JSON from current response |
| `candidateGraphHash` | `string\|null` | Client-computed hash of candidate graph |
| `candidateReport` | `object\|null` | Change report from agent response |
| `serverSubmitGraphHash` | `string\|null` | Backend-computed submit hash |
| `message` | `string\|null` | Human-readable status/result message |
| `failure` | `object\|null` | Normalized failure envelope |
| `clarification` | `object\|null` | `{ message, turn_id, session_id }` — composer notice data |
| `applyAllowed` | `boolean` | Whether Apply is allowed (derived) |
| `applyEligibility` | `object\|null` | Canonical `ApplyEligibility` from eligibility derivation |
| `applyEligibilityWarning` | `string\|null` | Warning text for queue-blocked-but-applyable state |
| `applyEligibilityWarningKey` | `string\|null` | Stable key for warning dedup across renders |
| `queueAllowed` | `boolean` | Whether Queue is allowed |
| `canvasApplyAllowed` | `boolean` | Backend canvas-apply gate result |
| `auditRef` | `object\|null` | Audit artifact reference from backend |
| `debugPayload` | `any` | Debug metadata for developer panel |
| `inFlightSubmit` | `Promise\|null` | Currently executing submit promise |
| `submitAbortController` | `AbortController\|null` | Controller for aborting in-flight submit |
| `submitEpoch` | `number` | Monotonic counter for stale-response gating |
| `inFlightApply` | `Promise\|null` | Currently executing apply promise |
| `inFlightRebaseline` | `Promise\|null` | Currently executing rebaseline promise |
| `rebaselinePending` | `object\|null` | Pending rebaseline metadata before POST |
| `rebaselineRecovery` | `object\|null` | Recovery metadata from stale-state failure |
| `lastSubmit` | `object\|null` | `{ task, route, model, client_graph_hash, client_structural_graph_hash, client_live_canvas_token, idempotency_key }` |
| `lastAppliedChanges` | `array\|null` | Changed-node feedback from last apply |
| `lastSubmitFieldChanges` | `array\|null` | Normalized field changes from submit response |
| `changeDetails` | `object\|null` | Change detail metadata for preview overlay |
| `deltaOps` | `array\|null` | V2 mutation intent (normalized `delta_ops` from submit response); authoritative for scoped apply |
| `chatRehydrateEpoch` | `number` | Monotonic counter for stale rehydrate gating |
| `syntheticAgentMessage` | `object\|null` | Locally generated agent chat message |

### 2.2 Non-lifecycle fields (read by store handlers but write-owned elsewhere)

- `routeStatus`, `statusSnapshot`, `settingsMessage` — provider settings
- `queueGuard` — adapter-owned; read/set via `getQueueGuardStateForPanel()` / `setQueueGuardContext()`
- `previewEnabled`, `expandedTurnKeys`, `expandedBubbleTurnKeys`, `turnDetailSnapshots` — render/UI
- `history`, `turns`, `undoStack` — history metadata
- `chatMessages`, `chatLoaded`, `chatError`, `chatSessionPath`, `chatDetailJsonPath` — chat display

### 2.3 Side-effect ownership

| Concern | Owner |
|---|---|
| HTTP requests (`fetch`) | `vibecomfy_roundtrip.js` |
| Graph serialization (`app.canvas.graph.serialize()`) | `vibecomfy_roundtrip.js` |
| Canvas mutation — V1 whole-graph (`applyGraphInPlaceWithIntentDecoration`, `app.loadGraphData`) | `vibecomfy_roundtrip.js` |
| Canvas mutation — V2 scoped delta (`applyGraphDeltaInPlace`) | `vibecomfy_roundtrip.js` |
| Scoped pre-apply precondition recheck (`validateScopedCanvasPreconditions`) | `vibecomfy_roundtrip.js` |
| Scoped post-apply result verification (`verifyScopedCanvasResults`) | `vibecomfy_roundtrip.js` |
| Post-mutation rollback on verification failure | `vibecomfy_roundtrip.js` |
| DOM construction and rendering | `vibecomfy_roundtrip.js` |
| Live canvas token capture | `vibecomfy_roundtrip.js` |
| Queue guard context (`setQueueGuardContext`) | `vibecomfy_roundtrip.js` |
| `localStorage` persistence | `vibecomfy_roundtrip.js` |
| Chat rehydration (`_rehydrateChat`) | `vibecomfy_roundtrip.js` |
| `deltaOps` normalization and lifecycle clearing | `agent_edit_lifecycle.js` |
| State transitions and field authority | `agent_edit_lifecycle.js` |

---

## 3. Transition table

Each row names the event, source/destination phases, local invalidations,
backend obligations, epoch/race handling, render obligation, and the covering
browser smoke test.

### 3.1 Submit transitions

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| S1 | Submit start (readiness ok) | `IDLE`, `CLARIFY`, `ERROR` | `SUBMITTING` | Invalidate candidate, clear failure/lastAppliedChanges/lastSubmitFieldChanges/deltaOps/feedback visuals; set `lastSubmit`; push pending history | `POST /vibecomfy/agent-edit` (constructed by roundtrip) | Increment `submitEpoch`; abort controller stored | Repaint | "VibeComfy agent submit sends canonical graph hash, normalized route/model fields, idempotency key, and dedupes in-flight submits" |
| S2 | Submit readiness failure | Any | `ERROR` | Set failure/debugPayload from readiness state | None | — | Repaint | "VibeComfy blocks submit until status.ready is true and shows composer readiness text" |
| S3 | Submit missing task | `IDLE`, `CLARIFY`, `ERROR` | `ERROR` | Set failure `MissingTask` | None | — | Repaint | "VibeComfy blocks submit until status.ready is true and shows composer readiness text" |
| S4 | Submit serialize error | `SUBMITTING` | `ERROR` | Set failure `SerializeError` | None | Check `submitEpoch` stale-guard | Repaint | "VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses" |
| S5 | Submit network/backend failure | `SUBMITTING` | `ERROR` | Set failure, sync baseline, persist session, clear queue guard, push failure history/turn, snapshot turn detail; if the failure carries `rebaselineRecovery` (extracted by the response-contract boundary), store it for the stale recovery action | None | Check `submitEpoch` stale-guard; abort controller cleared in finally | Repaint; trigger `_rehydrateChat` | "VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses"; "VibeComfy stale-canvas submit failure renders Rebaseline & retry and auto-resubmits" |
| S6 | Submit abort (AbortError) | `SUBMITTING` | `IDLE` | Clear failure, set cancel message, push cancelled history/turn, set synthetic agent message | None (abort already signaled) | Check `submitEpoch` stale-guard; abort controller cleared in finally | Repaint | "Lifecycle C1 stop aborts the in-flight submit, leaves no candidate, and only shows Undo in the composer when available" |
| S7 | Submit stale epoch | `SUBMITTING` | (no change) | None | None | `submitEpoch` mismatch → return early | None | "Lifecycle C2 new conversation clears state and ignores late submit responses" (epoch gated) |

### 3.2 Submit response transitions

Every row dispatches on the public `outcome.kind` from the normalized response.
The legacy internal kinds `edit` and `edit+clarify` are normalized to `candidate`
before dispatch (see §3.2.1) and are never visible to transition handlers.

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| R1 | `clarify` outcome | `SUBMITTING` | `CLARIFY` | Set `clarification`, clear candidate, set phase CLARIFY, persist session, sync baseline, clear apply/gate fields, reconcile batch turns | None further (response already received) | Check `submitEpoch` stale-guard | Repaint; trigger `_rehydrateChat` | "VibeComfy renders a clarify turn as a question, not a no-op candidate" |
| R2 | `candidate` outcome | `SUBMITTING` | `AWAITING_REVIEW` | Set candidate graph/hash/report, eligibility, baseline sync, queue guard restore; if the candidate carries a `clarification` (legacy `edit+clarify` normalized to `candidate`), also set `clarification`; populate `deltaOps` via `normalizeDeltaOpsFromSubmit(result)` when the response carries `agent_edit_protocol == "v2_delta"`; structural drift on arrival is diagnostic only | None further | Check `submitEpoch` stale-guard; arrival snapshot for diagnostics | Repaint; trigger `_rehydrateChat` | "VibeComfy preserves Apply controls for edit+clarify candidates"; "VibeComfy does not use client structural hash drift as a local candidate blocker" |
| R3 | `noop` outcome | `SUBMITTING` | `IDLE` | Clear candidate and clarification, sync baseline, persist session, clear apply/gate fields, keep prompt available, reconcile batch turns | None further (response already received) | Check `submitEpoch` stale-guard | Repaint; trigger `_rehydrateChat` | "VibeComfy renders no-op edit turns without entering review" |
| R4 | `error` outcome (malformed) | `SUBMITTING` | `ERROR` | Set failure `MalformedResponse` | None | Check `submitEpoch` stale-guard | Repaint; trigger `_rehydrateChat` | "VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses" |
| R5 | `error` outcome (serialize) | `SUBMITTING` | `ERROR` | Set failure `SerializeError` with arrival context, sync baseline | None | Check `submitEpoch` stale-guard | Repaint | "VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses" |

#### 3.2.1 Legacy `edit+clarify` normalization

The internal outcome kind `edit+clarify` is normalized to public `candidate` by
`normalizeAgentEditResponse()` in `agent_edit_response_contract.js` before any
transition handler sees the response.  A `candidate` outcome that carries a
`clarification` field is functionally identical to the legacy `edit+clarify`:
the candidate graph is presented for review, Apply is enabled, and the
clarification question is displayed in the notice banner.  No transition handler
checks for `edit+clarify` — all handlers dispatch on `outcome.kind ===
'candidate'` and optionally read `outcome.clarification`.

### 3.3 Apply transitions

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| A1 | Apply preflight blocked (no candidate) | `AWAITING_REVIEW` | (return) | None — early return | None | — | None | "VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before in-place configure, and blocks failed accepts" |
| A2 | Apply preflight blocked (missing session/turn) | `AWAITING_REVIEW` | `ERROR` | Set failure `MissingRequiredField` | None | — | Repaint | "VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before in-place configure, and blocks failed accepts" |
| A3 | Apply preflight blocked (eligibility) | `AWAITING_REVIEW` | `ERROR` | Set failure with eligibility reason, clear preview | None | Canvas snapshot captured for diagnostic structural parity check only; `applyEligibility()` gates on canonical backend eligibility, not on the structural hash | Repaint | "VibeComfy disables Apply and warns when a candidate arrives without canonical eligibility" |
| A4 | Apply started | `AWAITING_REVIEW` | `APPLYING` | Set `inFlightApply`, clear failure, set debug payload with accept request (including `live_graph` serialized from `beforeApply.graph`); for V2, resolve `deltaOps` from accept echo or panel state | `POST /vibecomfy/agent-edit/accept` | — | Repaint | "VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before in-place configure, and blocks failed accepts" |
| A5 | Backend accept rejected | `APPLYING` | `ERROR` | Set failure, synthesize an agent failure bubble when the candidate turn already has an agent bubble, disable authoritative rejects as superseded, clear queue guard, sync baseline; if rejection carries or implies stale rebaseline recovery, store it | None further (rejection received) | — | Repaint all sections so thread, controls, and recovery notice stay in sync | "Lifecycle A5 backend accept rejected disables an applyable candidate"; "Accept-stage stale mismatch renders one failure bubble and rebaseline-retries the original task" |
| A6 | Stale canvas during accept (live token changed) | `APPLYING` | `ERROR` | Set failure `StaleStateMismatch`, synthesize failure bubble and stale rebaseline recovery, clear preview | None | `liveCanvasToken` comparison before canvas load | Repaint all sections | "VibeComfy v2 Apply blocks if the live canvas token changes after backend accept but before configure" |
| A7 | Local canvas-apply failure | `APPLYING` | `ERROR` | Set failure `CanvasApplyError`, synthesize failure bubble, attempt inverse-delta rollback to pre-apply snapshot (see §3.3.1); if rollback fails, preserve undo snapshot and attach rollback diagnostics | None | — | Repaint all sections | "VibeComfy surfaces network and malformed accept failures with retry guidance and without canvas mutation" |
| A8 | Apply success (V1 whole-graph or V2 scoped delta) | `APPLYING` | `IDLE` | Push undo stack entry, apply graph in place (whole-graph `applyGraphInPlaceWithIntentDecoration` for V1, scoped `applyGraphDeltaInPlace` for V2), perform post-apply verification (see §3.3.1), announce changed nodes (`Applied - N changes verified on canvas.` for V2), sync baseline, invalidate candidate, clear queue guard, push applied history/turn; emit `canvas_apply_verification` debug data | None further | `liveCanvasToken` passes pre-configure check | Repaint; toast | "VibeComfy in-place apply decorates intent nodes with persistent styling, typed labels, and read-only previews" |

#### 3.3.1 V2 scoped apply lifecycle

When the candidate carries `agent_edit_protocol == "v2_delta"` and
`panel.state.deltaOps` is populated, Apply follows a **scoped delta** path
instead of whole-graph replacement. The flow has four stages:

##### Stage 1 — Accept request

The current canvas (`beforeApply.graph`) is serialized into the accept
request's `live_graph` field. The backend performs scoped validation (see
`docs/agent-edit-contracts.md`) and returns `scoped_accept_verification` plus an
echoed `delta_ops` on success.

##### Stage 2 — Local pre-mutation recheck (`validateScopedCanvasPreconditions`)

After backend accept succeeds, the browser captures the current canvas again
(`currentBeforeLoad.graph`) and **re-validates the touched region locally**:

- For each `delta_op`, it resolves `actual_before` from the current canvas.
- It compares `actual_before` against `expected_old` (from the server's
  `scoped_accept_verification.entries[]`).
- If `actual_before` already equals `desired_new`, status is `already_applied`
  (not a conflict).
- If any entry status is `conflict`, the touched region changed between backend
  accept and local apply. The browser **refuses to mutate**, emits a
  `StaleStateMismatch` failure, synthesizes stale rebaseline recovery, and
  records the precheck entries in `canvas_apply_verification.local_precheck`.

This recheck catches in-flight touched-region races that whole-graph CAS cannot
detect (e.g. another user changed only the field the agent intended to edit).

##### Stage 3 — Scoped delta mutation (`applyGraphDeltaInPlace`)

If the local precheck passes, the browser calls `applyGraphDeltaInPlace` with
the resolved `deltaOps` and `candidateGraph` (for add-node and link payloads).
This mutates only the nodes, fields, modes, links, and ordering positions
referenced by the delta ops using live LiteGraph mutation primitives. Unrelated
nodes, fields, and positions are preserved. No `graph.clear()` or wholesale
`graph.configure()` call occurs.

##### Stage 4 — Post-mutation verification (`verifyScopedCanvasResults`)

After mutation, the browser re-reads each touched location and verifies
`actual_after == desired_new`. Results are recorded in
`canvas_apply_verification.local_postcheck`.

- **All pass**: The success message is `Applied - N changes verified on canvas.`
  (where N is the number of verified entries).
- **Any fail**: The browser attempts **inverse-delta rollback** — restoring the
  pre-apply graph snapshot for the touched region only, falling back to
  whole-graph restore if needed. It then emits a `CanvasApplyError` failure with
  rollback diagnostics (`canvas_apply_verification.rollback.restored`,
  `canvas_apply_verification.rollback.method`) and preserves undo snapshot
  availability.

##### `canvas_apply_verification` debug payload

The `debugPayload` for scoped Apply carries:

```json
{
  "canvas_apply_verification": {
    "scoped_accept_verification": { "ok": true, "entries": [...] },
    "local_precheck": { "ok": true, "entries": [...] },
    "local_postcheck": { "ok": true, "entries": [...] },
    "rollback": { "restored": false, "method": null }
  }
}
```

- `scoped_accept_verification` — the server's scoped validation result.
- `local_precheck` — the browser's pre-mutation recheck against the current canvas.
- `local_postcheck` — the browser's post-mutation verification of desired results.
- `rollback` — present only on rollback; `restored` indicates success, `method`
  is `"inverse_delta"` or `"whole_graph"`.

##### V1 fallback

When `deltaOps` is unavailable (V1 candidate or missing evidence), Apply falls
back to the existing whole-graph path (`applyGraphInPlaceWithIntentDecoration`).
The mode is recorded in `canvasApplyMeta.mode` (`"scoped_delta"` or
`"whole_graph"`).

### 3.4 Reject transitions

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| J1 | Reject started | `AWAITING_REVIEW` | `APPLYING` | Set debug payload with reject request, clear failure | `POST /vibecomfy/agent-edit/reject` | — | Repaint | (Covered within apply/reject test flows) |
| J2 | Reject failure | `APPLYING` | `ERROR` | Set failure, sync baseline, push failure history/turn | None further | — | Repaint | "VibeComfy surfaces network and malformed accept failures with retry guidance and without canvas mutation" |
| J3 | Reject success | `APPLYING` | `IDLE` | Push rejected history/turn, invalidate candidate, clear queue guard, sync baseline | None further | — | Repaint; toast | "Lifecycle J3 reject success leaves no applyable candidate" |

### 3.5 Rebaseline, undo, and stale recovery

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| B1 | Undo local restore | `IDLE` | `IDLE` | Pop undo graph, restore via `app.loadGraphData`, clear feedback/lastAppliedChanges/queue guard | `POST /vibecomfy/agent-edit/rebaseline` (reason: `"undo"`) | `inFlightRebaseline` guards against concurrent rebaselines | Repaint | (Covered in roundtrip smoke) |
| B2 | Undo rebaseline success | `IDLE` | `IDLE` | Pop undo stack, push undo history/turn, sync baseline from response | None further | — | Repaint | "Lifecycle B2/B5 rebaseline sync blocks submit while pending or in flight" |
| B3 | Undo rebaseline failure | `IDLE` | `ERROR` | Set failure, preserve undo stack | None | — | Repaint | (Covered in roundtrip smoke) |
| B4 | Stale recovery rebaseline start | `ERROR` | `IDLE` | Set recovery message, trigger rebaseline; on success resubmit; on failure set ERROR | `POST /vibecomfy/agent-edit/rebaseline` (reason: `"stale_state_recovery"`) | `inFlightRebaseline` guard | Repaint | "VibeComfy renders one stale-state recovery action, retries against updated evidence, and recovers through rebaseline resubmit and apply" |
| B5 | Rebaseline pending blocks submit | `IDLE`/`ERROR` | (submit aborted) | Submit returns in-flight rebaseline promise | None | `rebaselinePending` or `inFlightRebaseline` blocks `submitAgentEdit` | Repaint | "Lifecycle B2/B5 rebaseline sync blocks submit while pending or in flight" |

### 3.6 Stop, new conversation, and cleanup

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| C1 | Stop/abort submit | `SUBMITTING` | `IDLE` | Abort controller, clear in-flight submit, set cancel message, push cancelled history/turn, clear failure, refresh queue guard, set synthetic agent message | None (fetch already aborted) | Increment `submitEpoch` so late responses are ignored | Repaint | "Lifecycle C1 stop aborts the in-flight submit, leaves no candidate, and only shows Undo in the composer when available" |
| C2 | New conversation | Any | `IDLE` | Abort any in-flight submit, clear all candidate/failure/clarification/chat/session/baseline/history/undo/rebaseline/audit/deltaOps fields, increment both epochs, forget active session, clear queue guard | Never calls `/rebaseline` | Increment both `submitEpoch` and `chatRehydrateEpoch` so late responses are ignored | Repaint | "Lifecycle C2 new conversation clears state and ignores late submit responses" |

### 3.7 Entry events (panel reopen, page reload)

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| E0 | Panel open (command, launcher, or ComfyUI sidebar tab) | Entry | (restored) | Open existing shell; refresh provider readiness; re-fetch `/chat` when a stored session id exists; restore `latest_candidate` only under eligibility | `GET /vibecomfy/agent/status`; `GET /vibecomfy/agent-edit/chat` when stored session exists | `chatRehydrateEpoch` incremented; stale responses ignored; status retry/backoff owned by roundtrip | Repaint immediately, after status, and after rehydrate | "VibeComfy live sidebar tab mount dispatches status fetch and chat rehydrate" |
| E1 | Panel reopen (chat re-fetch) | Entry | (restored) | Re-fetch `/chat`, rehydrate messages and turns; restore `latest_candidate` only under eligibility | `GET /vibecomfy/agent-edit/chat`; status refresh is also re-run by `openAgentPanel()` | `chatRehydrateEpoch` incremented; stale responses ignored | Repaint after rehydrate | "VibeComfy agent panel re-fetches chat on reopen and localStorage persists across close/reopen" |
| E2 | Page reload / rehydrate | Entry | `IDLE` or `AWAITING_REVIEW` | Run chat rehydration; if `latest_candidate` exists with eligibility, restore via `restoreLatestCandidateFromChat` including `deltaOps` from `baseline.raw` | `GET /vibecomfy/agent-edit/chat` | `chatRehydrateEpoch` incremented; stale responses silently dropped | Repaint | "Lifecycle E2 page reload rehydrate restores the latest open candidate and Apply controls" |
| E3 | Stale rehydrate ignored | Any | (no change) | None (stale response silently dropped) | None | `chatRehydrateEpoch` mismatch | None | "Lifecycle E3 stale rehydrate responses after an epoch bump do not restore prior candidate state" |

### 3.8 Hand-edit and stale-canvas detection

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| H1 | Hand-edit detection at submit | `SUBMITTING` | `ERROR` on backend CAS mismatch | `client_structural_graph_hash` submitted for backend CAS comparison; stale failure stores `rebaselineRecovery` (extracted by the response-contract boundary) and renders `Rebaseline & retry` | Backend CAS rejects structural mismatch as `StaleStateMismatch`; recovery button calls `/rebaseline` with current canvas then resubmits the failed prompt | — | Repaint on failure and after recovery | "VibeComfy stale-canvas submit failure renders Rebaseline & retry and auto-resubmits" |
| H2 | Stale canvas at apply | `AWAITING_REVIEW` | `ERROR` | Diagnostic structural parity check (live structural hash vs `lastSubmit.client_structural_graph_hash`); `applyEligibility()` gates on canonical backend eligibility, not on the structural hash. Accept-stage stale failures use the same `Rebaseline & retry` flow as submit-stage stale failures; if the backend omits `rebaselineRecovery`, the client synthesizes the stale recovery descriptor from the live panel state and accept request. | Backend CAS via `POST /accept` | `liveCanvasToken` double-checked before configure | Repaint | "VibeComfy Apply relies on backend CAS to block structural drift even when the live canvas revision is unchanged"; "Accept-stage stale mismatch renders one failure bubble and rebaseline-retries the original task" |

### 3.9 Superseded candidate invalidation

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| X1 | Candidate superseded by backend rejection | `APPLYING`, `AWAITING_REVIEW` | `ERROR` | Set `applyEligibility` to `SUPERSEDED`, disable apply/canvas/queue | Backend accept/reject response carries authoritative rejection | — | Repaint | "VibeComfy historical superseded candidates keep their superseded Apply reason instead of degrading to not_latest" |
| X2 | Candidate superseded by new submit | `AWAITING_REVIEW` | `SUBMITTING` | `invalidateCandidateState()` called at submit start | New submit starts | New `submitEpoch` | Repaint | "VibeComfy bubble candidate controls only enable the latest canonical candidate and disable older candidates as not_latest" |

---

## 4. Obligations

### 4.1 Per-transition obligations

Every transition handler must:

1. **Validate preconditions**: Check the current phase and required fields
   before applying the transition.
2. **Apply state mutations atomically**: All lifecycle field writes for the
   transition happen together within the handler.
3. **Return a plain obligations object** (no side effects inside the store):
   - `render: true` — roundtrip must call `renderAgentPanel(panel)` to repaint
     the panel DOM.
   - `rehydrateChat: true` — roundtrip must trigger `_rehydrateChat()` followed
     by a render after the chat payload arrives. Required after submit responses
     that change chat-visible state (candidate or failure arrived).
   - `toast: "message"` — roundtrip should call `toast(message)`.
   - `fetch: { url, options }` — roundtrip must execute the HTTP request and
     feed the result back into the store. *Note: M2 will clean up the shape;
     M1 roundtrip still owns all fetch construction.*
   - `canvasAction: "applyGraphInPlace" | "loadGraphData" | ...` — roundtrip
     must perform the canvas mutation.
   - `queueGuardClear: true` — roundtrip must call `setQueueGuardContext(null)`.
   - `persistSession: sessionId` — roundtrip must persist the session id to
     `localStorage`.

### 4.2 Epoch/race obligations

- **`submitEpoch`**: Incremented at submit start and stop/abort. Every async
  continuation within a submit flow must check `isCurrentSubmit()` (epoch
  comparison) before mutating `panel.state`. Stale epochs must return without
  side effects.
- **`chatRehydrateEpoch`**: Incremented at new conversation and rehydrate
  start. Async rehydrate continuations must check the epoch before applying
  state. Stale responses must silently drop.
- **`inFlightSubmit`**: Deduplication guard — if non-null, `submitAgentEdit()`
  returns the existing promise. Cleared in `finally` when the submit promise
  settles.
- **`inFlightRebaseline`**: Deduplication guard — if non-null,
  `postAgentRebaseline()` returns the existing promise.
- **`submitAbortController`**: Stored during submit fetch construction; used
  by `stopAgentSubmit()` to abort and by stale-epoch checks to avoid clearing
  a newer controller.

### 4.3 Baseline sync obligation

After every backend response (submit success, failure, accept, reject,
rebaseline), `syncBaselineFromResponse(panel, payload)` must be called to
mirror the backend's authoritative baseline fields into the panel state. The
store owns this call site.

### 4.4 Candidate invalidation obligation

`invalidateCandidateState(panel)` must be called:
- At submit start (before entering SUBMITTING) — also clears `deltaOps`
- On `clarify` outcome (before setting clarification) — also clears `deltaOps`
- On `noop` outcome — also clears `deltaOps`
- On `candidate` outcome arrival (before setting new candidate) — `deltaOps`
  is replaced, not cleared
- On apply success (after canvas mutation)
- On reject success (after backend confirmation)
- On rebaseline success — also clears `deltaOps`
- On new conversation — also clears `deltaOps`

The store owns the call site; the roundtrip module's `invalidateCandidateState`
implementation handles repaint side effects (canvas `setDirtyCanvas`).

---

## 5. Epoch and race handling detail

### 5.1 Submit epoch protocol

```
submitAgentEdit():
  epoch = ++panel.state.submitEpoch
  isCurrentSubmit = () => panel.state.submitEpoch === epoch
  // ... all async continuations check isCurrentSubmit() ...
  fetch(...).then(result => {
    if (!isCurrentSubmit()) return  // stale, drop silently
    // ... apply result to state ...
  }).catch(err => {
    if (!isCurrentSubmit()) return  // stale, drop silently
    // ... apply error to state ...
  }).finally(() => {
    if (isCurrentSubmit() || panel.state.submitAbortController === controller)
      panel.state.submitAbortController = null
    panel.state.inFlightSubmit = null
  })
```

### 5.2 Chat rehydrate epoch protocol

```
_rehydrateChat(panel):
  requestEpoch = ++panel.state.chatRehydrateEpoch
  fetch(`/chat?session_id=...`).then(payload => {
    if (panel.state.chatRehydrateEpoch !== requestEpoch) return  // stale
    // ... apply chat state ...
  })
```

### 5.3 Late async response after new conversation

When `newAgentConversation()` increments both `submitEpoch` and
`chatRehydrateEpoch`, any in-flight submit or rehydrate continuations
will fail their epoch check and silently drop. No stale response can
pollute the fresh session.

---

## 6. Covering-test summary

| Transition row(s) | Test name |
|---|---|
| S1 (submit start) | "VibeComfy agent submit sends canonical graph hash, normalized route/model fields, idempotency key, and dedupes in-flight submits" |
| S2, S3 (readiness/missing-task) | "VibeComfy blocks submit until status.ready is true and shows composer readiness text" |
| S4, S5, R4, R5 (serialize/network/malformed failures) | "VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses" |
| S6, C1 (abort/stop) | "Lifecycle C1 stop aborts the in-flight submit, leaves no candidate, and only shows Undo in the composer when available" |
| R1 (`clarify` outcome) | "VibeComfy renders a clarify turn as a question, not a no-op candidate" |
| R2 (`candidate` outcome) | "VibeComfy preserves Apply controls for edit+clarify candidates"; "VibeComfy does not use client structural hash drift as a local candidate blocker" |
| H1 (stale submit recovery) | "VibeComfy stale-canvas submit failure renders Rebaseline & retry and auto-resubmits" |
| R3 (`noop` outcome) | "VibeComfy renders no-op edit turns without entering review" |
| A1–A4 (apply flow) | "VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before in-place configure, and blocks failed accepts" |
| A3 (missing eligibility) | "VibeComfy disables Apply and warns when a candidate arrives without canonical eligibility" |
| A5 (backend accept rejection) | "Lifecycle A5 backend accept rejected disables an applyable candidate"; "Accept-stage stale mismatch renders one failure bubble and rebaseline-retries the original task" |
| A6 (stale canvas) | "VibeComfy v2 Apply blocks if the live canvas token changes after backend accept but before configure" |
| A7, J2 (apply/reject failure surfaces) | "VibeComfy surfaces network and malformed accept failures with retry guidance and without canvas mutation" |
| A8 (apply success with decoration) | "VibeComfy in-place apply decorates intent nodes with persistent styling, typed labels, and read-only previews" |
| J3 (reject success) | "Lifecycle J3 reject success leaves no applyable candidate" |
| B1–B3, B5 (rebaseline/undo) | "Lifecycle B2/B5 rebaseline sync blocks submit while pending or in flight" |
| B4 (stale recovery) | "VibeComfy renders one stale-state recovery action, retries against updated evidence, and recovers through rebaseline resubmit and apply" |
| C2 (new conversation) | "Lifecycle C2 new conversation clears state and ignores late submit responses" |
| E1 (panel reopen) | "VibeComfy agent panel re-fetches chat on reopen and localStorage persists across close/reopen" |
| E2 (page reload restore) | "Lifecycle E2 page reload rehydrate restores the latest open candidate and Apply controls" |
| E3 (stale rehydrate) | "Lifecycle E3 stale rehydrate responses after an epoch bump do not restore prior candidate state" |
| H2 (backend CAS blocks structural drift) | "VibeComfy Apply relies on backend CAS to block structural drift even when the live canvas revision is unchanged" |
| X1 (superseded keeps reason) | "VibeComfy historical superseded candidates keep their superseded Apply reason instead of degrading to not_latest" |
| X2 (only latest canonical enabled) | "VibeComfy bubble candidate controls only enable the latest canonical candidate and disable older candidates as not_latest" |
| Clarify follow-up | "VibeComfy clarify questions render inline and follow-up submit continues the same session" |
| Failure bubble with user_facing_message | "VibeComfy failure bubble uses envelope user_facing_message for MalformedModelJSON" |
| Typed envelope reading | "VibeComfy reads typed candidate and eligibility envelopes without compatibility mirrors" |
| Raw apply booleans ignored | "VibeComfy ignores raw apply booleans when canonical eligibility authorizes Apply" |

---

## 7. Render obligation contract

The lifecycle store communicates render intent to `vibecomfy_roundtrip.js` through
a plain obligations object returned by `transition(panel, event, payload)`. Every
handler returns an object with the following contract:

### 7.1 Obligation keys

| Key | Type | Description |
|---|---|---|
| `render` | `boolean` | Whether `renderAgentPanel(panel)` must be called. Required on every obligation. |
| `dirtySections` | `string[]` | Scoped DOM regions that changed (see §8). Accumulated into the panel's pending dirty set when `render` is false; consumed on the next scheduled render. |
| `toast` | `string|null` | Message to display via `app.ui.toast()`. |
| `rehydrateChat` | `boolean` | Trigger `_rehydrateChat()` followed by a render after the chat payload arrives. |
| `invalidateCandidate` | `boolean` | Call `invalidateCandidateState(panel)` to clear candidate preview overlay and mark canvas dirty. |
| `persistSession` | `string|null` | Session id to write to `localStorage`. |
| `queueGuardClear` | `boolean` | Call `setQueueGuardContext(null)`. |
| `refreshQueueGuard` | `boolean` | Re-evaluate queue guard from current panel state. |
| `setQueueGuardContext` | `object` | `{ sessionId, turnId, queueAllowed }` payload for queue guard adapter. |
| `forgetSession` | `boolean` | Clear session from `localStorage`. |
| `focusPrompt` | `boolean` | Move focus to the composer prompt input. |
| `clearCandidatePreview` | `boolean` | Remove candidate preview overlay from canvas. |
| `clearChangedNodeFeedbackVisuals` | `boolean` | Remove changed-node highlight decorations. |

### 7.2 Render vs. no-render transitions

Transitions that return `render: false` but include `dirtySections` (e.g.
`REBASELINE_SUCCESS`, `CHAT_REHYDRATE_SUCCESS`, `CHAT_REHYDRATE_NO_SESSION`)
**accumulate** their dirty sections into the panel's pending dirty set (SD2).
The next transition that returns `render: true`, or the next scheduled render,
consumes the accumulated dirty sections so no visual change is lost.

Transitions that return `render: false` with no `dirtySections` (e.g.
`SUBMIT_IN_FLIGHT`, `APPLY_IN_FLIGHT`, `SUBMIT_FINALLY`) are pure
bookkeeping — they mutate lifecycle state with no visual consequence.

### 7.3 Obligation fulfillment

The roundtrip module owns all obligation fulfillment. The lifecycle store
never calls `fetch`, never touches the DOM, and never mutates the canvas.
It returns obligations; the roundtrip executor reads them and performs the
corresponding side effects.

---

## 8. `dirtySections` taxonomy and deterministic rules

### 8.0 Live debugging hook

The browser extension installs a cheap, scrubbed diagnostics hook for live
forensics:

```js
window.__vibecomfyPanelDebug()
```

It returns only panel lifecycle metadata:

```js
{
  phase,
  readiness: { kind, ready, reason },
  sessionId,
  turnId,
  baselineTurnId,
  messageCount,
  visibleMessageCount,
  dirtySections,
  mountMode,
  epochs: { status, chatRehydrate, chatRehydrateCommitted, submit },
}
```

The hook intentionally omits graph payloads, API keys, prompts beyond rendered
message counts, raw status snapshots, and debug payload bodies. `readiness` is
computed through the same helper that gates Submit and the composer notice;
`messageCount` / `visibleMessageCount` are computed through the same thread
collection and windowing helpers that decide whether the transcript or example
picker renders.

### 8.1 Section definitions

The `RENDER_SECTIONS` frozen export in `agent_edit_lifecycle.js` defines six
scoped DOM regions:

| Value | DOM region | Typical content |
|---|---|---|
| `META` | Status bar / metadata row | Phase badge, turn id, session id, baseline hash |
| `THREAD` | Chat message list | Chat bubbles, candidate previews, failure cards |
| `COMPOSER` | Prompt input area | Text input, route/model selectors, submit/stop/undo buttons |
| `NOTICE` | Clarification / message banner | Clarify question text, status message, eligibility warning |
| `SETTINGS` | Provider settings panel | Route status, model config, queue guard UI |
| `DEVELOPER` | Debug payload panel | Raw JSON debug view of `panel.state.debugPayload` |

### 8.2 Deterministic dirty-section rules

Each lifecycle handler assigns dirty sections based on **what state fields it
mutates**, not what the caller requests:

| Mutated field category | Dirty section |
|---|---|
| `phase`, `message`, `failure`, `clarification`, `applyAllowed`, `queueAllowed`, `canvasApplyAllowed`, `applyEligibility`, `applyEligibilityWarning` | `META` |
| Status fields (above) plus `debugPayload` | `META`, `COMPOSER`, `NOTICE`, `DEVELOPER` |
| `chatMessages`, `chatLoaded`, `chatError`, `chatSessionPath`, `chatDetailJsonPath` | `THREAD` |
| `sessionId` plus any thread mutation | `META`, `THREAD` |
| All lifecycle fields (INIT, NEW_CONVERSATION) | All six sections |

Pre-composed constant arrays (`STATUS_DIRTY_SECTIONS`, `STATUS_AND_DEVELOPER_DIRTY_SECTIONS`,
`THREAD_DIRTY_SECTIONS`, `META_AND_THREAD_DIRTY_SECTIONS`, `ALL_RENDER_DIRTY_SECTIONS`)
are frozen at module scope and reused by handlers to avoid per-call allocation.

### 8.3 Obligation normalization

`normalizeObligationDirtySections(obligations)` de-duplicates and validates
the `dirtySections` array in every obligations object returned by `transition()`:

1. **Null/undefined pass-through**: If `dirtySections` is absent, the obligation
   is returned unchanged.
2. **Type validation**: Throws if `dirtySections` is not an array, or if any
   element is not a string.
3. **Known-section validation**: Throws if any element is not a value in the
   frozen `RENDER_SECTIONS` map (e.g. `"META"`, `"THREAD"`).
4. **De-duplication**: Preserves first-occurrence order, removes duplicates.
5. **Key preservation**: `render` and all other obligation keys (e.g. `toast`,
   `invalidateCandidate`) pass through unchanged.

All internal handlers route through `_obligations()`, which calls
`normalizeObligationDirtySections` before returning.

---

## 9. Transitional bridge for non-lifecycle write-owned state

Several state fields used during agent-edit rendering are not yet migrated to
lifecycle store ownership (see §2.2). Until those fields are migrated, the
roundtrip module uses a **transitional bridge** to ensure dirty-section
accumulation covers mutations to these fields:

### 9.1 Non-lifecycle fields requiring bridge coverage

| Field group | Mutation sites | Dirty section required |
|---|---|---|
| `history`, `turns`, `undoStack` | Push/pop history entries in submit, apply, reject, rebaseline, undo flows | `META` |
| `chatMessages`, `chatLoaded`, `chatError`, `chatSessionPath`, `chatDetailJsonPath` | Chat rehydrate handlers (already covered — see §8.2) | `THREAD` |
| `routeStatus`, `statusSnapshot`, `settingsMessage` | Provider settings panel updates | `SETTINGS` |

### 9.2 Bridge mechanism

For each non-lifecycle mutation site, the roundtrip module calls
`markAgentPanelDirty(panel, sections)` to accumulate dirty sections into the
panel's pending dirty set. This is a **transitional** pattern — as fields are
migrated to lifecycle ownership, the lifecycle handlers will emit the
appropriate `dirtySections` directly and the bridge calls will be removed.

The bridge guarantees:
- No visual change is lost: the pending dirty set is consumed on the next
  `render: true` transition or scheduled render.
- No double-counting: `dirtySections` are de-duplicated in the pending set
  via the same `normalizeObligationDirtySections` rules.
- Panel-scoped isolation (SD1): the pending dirty set is stored per-panel,
  not module-global, preventing state leakage across panels or test fixtures.

### 9.3 Bridge lifecycle

1. **Planned**: Each non-lifecycle mutation site adds a `markAgentPanelDirty`
   call alongside the existing `renderAgentPanel` call.
2. **Transition**: The pending dirty set grows from both lifecycle handler
   `dirtySections` and bridge `markAgentPanelDirty` calls.
3. **End state**: When all fields are migrated to lifecycle ownership, bridge
   calls are removed. The pending dirty set is populated exclusively by
   lifecycle transition handlers.

---

## 10. Render-entry-point inventory (from T1 audit)

### 10.1 Direct `renderAgentPanel(panel)` call sites

| # | Line | Call site classification |
|---|---|---|
| 1 | L1540 | Initial-paint: panel creation in `openAgentEditPanel` |
| 2 | L2286 | User-interaction: `_onAgentEditComposerAction` |
| 3 | L2525 | Scheduled-executor: `_flushScheduledRender` |
| 4 | L2541 | Scheduled-executor: per-entry flush in `_flushScheduledRender` |
| 5 | L2585 | Panel-open: `_onAgentEditPanelOpen` |
| 6 | L5431 | Queue-guard: `_onQueueGuardChange` |
| 7 | L6233 | Settings-route: `_renderAgentEditSettingsPanel` |
| 8 | L6264 | Settings-provider: `_onAgentEditProviderSettingsChange` |
| 9 | L6374 | Lifecycle-gateway: `fulfillLifecycleTransitionObligations` primary path |
| 10 | L6392 | Guard-early-return: `fulfillLifecycleTransitionObligations` after `invalidateCandidate` |
| 11 | L6789 | Guard-early-return: `_applyAgentEdit` preflight path |
| 12 | L7130 | Submit-error: `_submitAgentEdit` error path |
| 13 | L7154 | Submit-flow: `_submitAgentEdit` start-of-submit path |
| 14 | L7202 | Rebaseline-error: `_postAgentRebaseline` error path |
| 15 | L7366 | Guard-early-return: `_rejectAgentEdit` preflight |
| 16 | L7410 | Guard-early-return: `_applyAgentEdit` after rejection |
| 17 | L7495 | Command-handler: `_handleAgentEditCommand` |

### 10.2 `scheduleRenderAgentPanel(reason, panel)` call sites

| # | Line | Reason | Context |
|---|---|---|---|
| 1 | L1566 | `"status"` | Status snapshot provider callback |
| 2 | L1655 | `"status"` | Route status provider callback |
| 3 | L2528 | (definition) | Function definition |
| 4 | L2581 | `"rehydrate"` | After chat rehydrate completion |
| 5 | L3239 | `"websocket"` | WebSocket message handler |
| 6 | L6385 | `"rehydrate"` | After `_rehydrateChat` in lifecycle gateway |

### 10.3 Dead/duplicate helpers

The T1 audit identified no dead helper functions. All `renderAgentPanel` and
`scheduleRenderAgentPanel` call sites are live and intentionally placed.
`invalidateCandidateState()` in `vibecomfy_roundtrip.js` is the canonical
candidate invalidation helper; it is called only from
`fulfillLifecycleTransitionObligations()` when the `invalidateCandidate`
obligation is present. No duplicate or dead candidate invalidation helpers exist.

---

## 11. A5 authoritative accept rejection

### 11.1 Transition: `ACCEPT_REJECTED`

The `_handleAcceptRejected(panel, payload)` handler processes backend accept
rejection (transition A5 in §3.3). The handler:

1. **Preserves candidate evidence**: Sets `panel.state.failure` to the rejection
   failure envelope, preserving the candidate context (turn id, session id,
   audit ref) for display and debugging. The `debugPayload` is set to include
   the failure envelope plus the accept request body for developer inspection.

2. **Disables apply eligibility on authoritative rejection**: When
   `payload.authoritativeBackendReject` is truthy (i.e. `Boolean(payload?.authoritativeBackendReject)`),
   the handler sets:
   - `applyEligibility` to `payload.disabledApplyEligibility` (typically `SUPERSEDED`)
   - `applyAllowed = false`
   - `canvasApplyAllowed = false`
   - `queueAllowed = false`

   This disables all Apply/Queue controls because the backend has
   authoritatively determined the candidate is no longer valid.

3. **Does NOT clear the candidate**: Unlike `_handleInvalidateCandidate`,
   `_handleAcceptRejected` preserves `candidateGraph` and related fields.
   The candidate evidence remains visible in the thread for historical
   review, but the Apply button is disabled because `applyAllowed` is false.

4. **Clears queue guard**: On authoritative rejection, `queueGuardClear` and
   `refreshQueueGuard` are both set to `true`.

5. **Syncs baseline**: Calls `_handleSyncBaseline(panel, failure)` to mirror
   any baseline fields in the rejection payload, and preserves `auditRef`.

### 11.2 Re-enabling eligibility

An existing transition (e.g. `OK_CANDIDATE_RESPONSE` from a new submit, or
`CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE`) clears the superseded state by
setting fresh `applyEligibility`, `applyAllowed`, and related fields. The
A5 handler itself does not provide a path to re-enable — it only disables.
Recovery from a superseded candidate requires a new submit or rehydrate
that produces a fresh eligible candidate.
