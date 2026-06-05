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

| Phase | Meaning |
|---|---|
| `IDLE` | Shell open, ready for prompt entry |
| `SUBMITTING` | `POST /vibecomfy/agent-edit` in-flight |
| `CLARIFY` | Agent asked a clarification question; no candidate to review |
| `AWAITING_REVIEW` | Candidate received; Apply / Reject available |
| `APPLYING` | Local in-place graph apply or reject in progress (proof-only) |
| `ERROR` | Request failed; failure region becomes primary |

### 1.1 Entry events (not phases)

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
| Canvas mutation (`applyGraphInPlaceWithIntentDecoration`, `app.loadGraphData`) | `vibecomfy_roundtrip.js` |
| DOM construction and rendering | `vibecomfy_roundtrip.js` |
| Live canvas token capture | `vibecomfy_roundtrip.js` |
| Queue guard context (`setQueueGuardContext`) | `vibecomfy_roundtrip.js` |
| `localStorage` persistence | `vibecomfy_roundtrip.js` |
| Chat rehydration (`_rehydrateChat`) | `vibecomfy_roundtrip.js` |
| State transitions and field authority | `agent_edit_lifecycle.js` |

---

## 3. Transition table

Each row names the event, source/destination phases, local invalidations,
backend obligations, epoch/race handling, render obligation, and the covering
browser smoke test.

### 3.1 Submit transitions

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| S1 | Submit start (readiness ok) | `IDLE`, `CLARIFY`, `ERROR` | `SUBMITTING` | Invalidate candidate, clear failure/lastAppliedChanges/lastSubmitFieldChanges/feedback visuals; set `lastSubmit`; push pending history | `POST /vibecomfy/agent-edit` (constructed by roundtrip) | Increment `submitEpoch`; abort controller stored | Repaint | "VibeComfy agent submit sends canonical graph hash, normalized route/model fields, idempotency key, and dedupes in-flight submits" |
| S2 | Submit readiness failure | Any | `ERROR` | Set failure/debugPayload from readiness state | None | — | Repaint | "VibeComfy blocks submit until status.ready is true and shows composer readiness text" |
| S3 | Submit missing task | `IDLE`, `CLARIFY`, `ERROR` | `ERROR` | Set failure `MissingTask` | None | — | Repaint | "VibeComfy blocks submit until status.ready is true and shows composer readiness text" |
| S4 | Submit serialize error | `SUBMITTING` | `ERROR` | Set failure `SerializeError` | None | Check `submitEpoch` stale-guard | Repaint | "VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses" |
| S5 | Submit network/backend failure | `SUBMITTING` | `ERROR` | Set failure, sync baseline, persist session, clear queue guard, push failure history/turn, snapshot turn detail | None | Check `submitEpoch` stale-guard; abort controller cleared in finally | Repaint; trigger `_rehydrateChat` | "VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses" |
| S6 | Submit abort (AbortError) | `SUBMITTING` | `IDLE` | Clear failure, set cancel message, push cancelled history/turn, set synthetic agent message | None (abort already signaled) | Check `submitEpoch` stale-guard; abort controller cleared in finally | Repaint | "Lifecycle C1 stop aborts the in-flight submit, leaves no candidate, and only shows Undo in the composer when available" |
| S7 | Submit stale epoch | `SUBMITTING` | (no change) | None | None | `submitEpoch` mismatch → return early | None | "Lifecycle C2 new conversation clears state and ignores late submit responses" (epoch gated) |

### 3.2 Submit response transitions

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| R1 | Clarify-only response | `SUBMITTING` | `CLARIFY` | Set `clarification`, clear candidate, set phase CLARIFY, persist session, sync baseline, clear apply/gate fields, reconcile batch turns | None further (response already received) | Check `submitEpoch` stale-guard | Repaint; trigger `_rehydrateChat` | "VibeComfy renders a clarify turn as a question, not a no-op candidate" |
| R2 | Edit+clarify response | `SUBMITTING` | `AWAITING_REVIEW` | Set candidate graph/hash/report, eligibility, `clarification`, baseline sync, queue guard restore | None further | Check `submitEpoch` stale-guard; arrival snapshot for diagnostics | Repaint; trigger `_rehydrateChat` | "VibeComfy preserves Apply controls for edit+clarify candidates" |
| R3 | Ok candidate response | `SUBMITTING` | `AWAITING_REVIEW` | Set candidate graph/hash/report, eligibility, baseline sync, queue guard restore; structural drift on arrival is diagnostic only | None further | Check `submitEpoch` stale-guard; arrival snapshot for diagnostics | Repaint; trigger `_rehydrateChat` | "VibeComfy does not use client structural hash drift as a local candidate blocker" |
| R4 | Malformed candidate response | `SUBMITTING` | `ERROR` | Set failure `MalformedResponse` | None | Check `submitEpoch` stale-guard | Repaint; trigger `_rehydrateChat` | "VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses" |
| R5 | Arrival serialize failure | `SUBMITTING` | `ERROR` | Set failure `SerializeError` with arrival context, sync baseline | None | Check `submitEpoch` stale-guard | Repaint | "VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses" |

### 3.3 Apply transitions

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| A1 | Apply preflight blocked (no candidate) | `AWAITING_REVIEW` | (return) | None — early return | None | — | None | "VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before in-place configure, and blocks failed accepts" |
| A2 | Apply preflight blocked (missing session/turn) | `AWAITING_REVIEW` | `ERROR` | Set failure `MissingRequiredField` | None | — | Repaint | "VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before in-place configure, and blocks failed accepts" |
| A3 | Apply preflight blocked (eligibility) | `AWAITING_REVIEW` | `ERROR` | Set failure with eligibility reason, clear preview | None | Canvas snapshot captured for diagnostic structural parity check only; `applyEligibility()` gates on canonical backend eligibility, not on the structural hash | Repaint | "VibeComfy disables Apply and warns when a candidate arrives without canonical eligibility" |
| A4 | Apply started | `AWAITING_REVIEW` | `APPLYING` | Set `inFlightApply`, clear failure, set debug payload with accept request | `POST /vibecomfy/agent-edit/accept` | — | Repaint | "VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before in-place configure, and blocks failed accepts" |
| A5 | Backend accept rejected | `APPLYING` | `ERROR` | Set failure, disable candidate as superseded, clear queue guard, sync baseline | None further (rejection received) | — | Repaint | "Lifecycle A5 backend accept rejected disables an applyable candidate" |
| A6 | Stale canvas during accept (live token changed) | `APPLYING` | `ERROR` | Set failure `StaleStateMismatch`, clear preview | None | `liveCanvasToken` comparison before canvas load | Repaint | "VibeComfy v2 Apply blocks if the live canvas token changes after backend accept but before configure" |
| A7 | Local canvas-apply failure | `APPLYING` | `ERROR` | Set failure `CanvasApplyError` | None | — | Repaint | "VibeComfy surfaces network and malformed accept failures with retry guidance and without canvas mutation" |
| A8 | Apply success | `APPLYING` | `IDLE` | Push undo stack entry, apply graph in place, announce changed nodes, sync baseline, invalidate candidate, clear queue guard, push applied history/turn | None further | `liveCanvasToken` passes pre-configure check | Repaint; toast | "VibeComfy in-place apply decorates intent nodes with persistent styling, typed labels, and read-only previews" |

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
| C2 | New conversation | Any | `IDLE` | Abort any in-flight submit, clear all candidate/failure/clarification/chat/session/baseline/history/undo/rebaseline/audit fields, increment both epochs, forget active session, clear queue guard | Never calls `/rebaseline` | Increment both `submitEpoch` and `chatRehydrateEpoch` so late responses are ignored | Repaint | "Lifecycle C2 new conversation clears state and ignores late submit responses" |

### 3.7 Entry events (panel reopen, page reload)

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| E1 | Panel reopen (chat re-fetch) | Entry | (restored) | Re-fetch `/chat`, rehydrate messages and turns; restore `latest_candidate` only under eligibility | `GET /vibecomfy/agent-edit/chat` | `chatRehydrateEpoch` incremented; stale responses ignored | Repaint after rehydrate | "VibeComfy agent panel re-fetches chat on reopen and localStorage persists across close/reopen" |
| E2 | Page reload / rehydrate | Entry | `IDLE` or `AWAITING_REVIEW` | Run chat rehydration; if `latest_candidate` exists with eligibility, restore via `restoreLatestCandidateFromChat` | `GET /vibecomfy/agent-edit/chat` | `chatRehydrateEpoch` incremented; stale responses silently dropped | Repaint | "Lifecycle E2 page reload rehydrate restores the latest open candidate and Apply controls" |
| E3 | Stale rehydrate ignored | Any | (no change) | None (stale response silently dropped) | None | `chatRehydrateEpoch` mismatch | None | "Lifecycle E3 stale rehydrate responses after an epoch bump do not restore prior candidate state" |

### 3.8 Hand-edit and stale-canvas detection

| # | Event | From | To | Local invalidations | Backend obligation | Epoch/race | Render | Covering test |
|---|---|---|---|---|---|---|---|---|
| H1 | Hand-edit detection at submit | `SUBMITTING` | (diagnostic only) | `client_structural_graph_hash` submitted for backend CAS comparison | Backend CAS rejects structural mismatch as `StaleStateMismatch` | — | None (diagnostic) | "VibeComfy does not use client structural hash drift as a local candidate blocker" |
| H2 | Stale canvas at apply | `AWAITING_REVIEW` | `ERROR` | Diagnostic structural parity check (live structural hash vs `lastSubmit.client_structural_graph_hash`); `applyEligibility()` gates on canonical backend eligibility, not on the structural hash | Backend CAS via `POST /accept` | `liveCanvasToken` double-checked before configure | Repaint | "VibeComfy Apply relies on backend CAS to block structural drift even when the live canvas revision is unchanged" |

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
- At submit start (before entering SUBMITTING)
- On clarify-only response (before setting clarification)
- On candidate arrival (before setting new candidate)
- On apply success (after canvas mutation)
- On reject success (after backend confirmation)
- On rebaseline success
- On new conversation

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
| R1 (clarify-only) | "VibeComfy renders a clarify turn as a question, not a no-op candidate" |
| R2 (edit+clarify) | "VibeComfy preserves Apply controls for edit+clarify candidates" |
| R3, H1 (ok candidate, no local structural block) | "VibeComfy does not use client structural hash drift as a local candidate blocker" |
| A1–A4 (apply flow) | "VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before in-place configure, and blocks failed accepts" |
| A3 (missing eligibility) | "VibeComfy disables Apply and warns when a candidate arrives without canonical eligibility" |
| A5 (backend accept rejection) | "Lifecycle A5 backend accept rejected disables an applyable candidate" |
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
