// agent_edit_lifecycle.js — Client lifecycle contract + state authority
//
// This module owns every panel-state mutation for defined transitions.
// It performs ZERO HTTP/canvas/DOM side effects.
// All external data arrives via `payload`; all side effects are returned
// as plain obligations objects that `vibecomfy_roundtrip.js` fulfills.
//
// Backend CAS is the single Apply authority. The client sends
// `client_structural_graph_hash` only as a backend-parity diagnostic
// snapshot in submit/rebaseline payloads; it never blocks Apply locally.

import {
  readApplyCandidate,
  readCustomNodeResolution,
  readFieldChanges,
  readStageSnapshot,
  readTurnIdentity,
  projectAuditArtifact,
  projectExecutionEvent,
  projectResponseDetail,
  projectTranscriptMessage,
  splitRehydrateProjectionInput,
} from "./agent_edit_response_contract.js";

// ── T7: Runtime snapshot helpers for scope switching ─────────────────────
import {
  saveScopeSnapshot,
  restoreScopeSnapshot,
} from "./panel_runtime.js";

// ── T7: Canonical delta normalization ────────────────────────────────────
import {
  DELTA_DIAGNOSTIC_LEGACY_SHAPE,
  DELTA_DIAGNOSTIC_MALFORMED,
  DeltaDiagnosticError,
  classifyDeltaShape,
  normalizeDeltaOpsFromSubmitPayload,
} from "./canonical_delta.js";

// ── Phase taxonomy ─────────────────────────────────────────────────────────
export const PANEL_STATE = Object.freeze({
  IDLE: "IDLE",
  SUBMITTING: "SUBMITTING",
  CLARIFY: "CLARIFY",
  AWAITING_REVIEW: "AWAITING_REVIEW",
  APPLYING: "APPLYING",
  ERROR: "ERROR",
});

// ── Render section taxonomy ────────────────────────────────────────────────
// Each value identifies a scoped DOM region that the render gateway can
// selectively repaint. The obligation-normalization helper below validates
// and de-duplicates dirtySections arrays against this frozen map.
export const RENDER_SECTIONS = Object.freeze({
  META: "META",
  THREAD: "THREAD",
  COMPOSER: "COMPOSER",
  NOTICE: "NOTICE",
  SETTINGS: "SETTINGS",
  DEVELOPER: "DEVELOPER",
});

const ALL_RENDER_DIRTY_SECTIONS = Object.freeze(Object.values(RENDER_SECTIONS));
const STATUS_DIRTY_SECTIONS = Object.freeze([
  RENDER_SECTIONS.META,
  RENDER_SECTIONS.COMPOSER,
  RENDER_SECTIONS.NOTICE,
]);
const STATUS_AND_DEVELOPER_DIRTY_SECTIONS = Object.freeze([
  ...STATUS_DIRTY_SECTIONS,
  RENDER_SECTIONS.DEVELOPER,
]);
const REVIEW_DIRTY_SECTIONS = Object.freeze([
  RENDER_SECTIONS.META,
  RENDER_SECTIONS.THREAD,
  RENDER_SECTIONS.COMPOSER,
  RENDER_SECTIONS.NOTICE,
  RENDER_SECTIONS.DEVELOPER,
]);
const THREAD_DIRTY_SECTIONS = Object.freeze([RENDER_SECTIONS.THREAD]);
const META_AND_THREAD_DIRTY_SECTIONS = Object.freeze([
  RENDER_SECTIONS.META,
  RENDER_SECTIONS.THREAD,
]);

// ── Lifecycle event taxonomy ───────────────────────────────────────────────
// Foundation events (implemented in this file):
//   INIT                — no-op (state already created by createAgentEditState)
//   SYNC_BASELINE       — mirror authoritative baseline fields from payload
//   INVALIDATE_CANDIDATE — clear candidate review fields
//   (unknown)           — no-op, returns { render: false }
//
// Apply events:
//   APPLY_PREFLIGHT_BLOCKED,
//   APPLY_MISSING_FIELDS, APPLY_ELIGIBILITY_BLOCKED, APPLY_STARTED,
//   ACCEPT_REJECTED, STALE_CANVAS_APPLY, CANVAS_APPLY_FAILURE,
//   APPLY_SUCCESS
//
// Events implemented in later batches:
//   UNDO_LOCAL_RESTORE, UNDO_REBASELINE_SUCCESS, UNDO_REBASELINE_FAILURE,
//   STALE_RECOVERY_START, REBASELINE_BLOCKS_SUBMIT, STOP_ABORT,
//   NEW_CONVERSATION, PANEL_REOPEN, PAGE_RELOAD,
//   HAND_EDIT_DETECTION, STALE_CANVAS_DETECTION,
//   CANDIDATE_SUPERSEDED, CANDIDATE_SUPERSEDED_BY_SUBMIT

// ── Store-owned lifecycle fields ───────────────────────────────────────────
// These fields are mutated exclusively through the lifecycle store.
// No ad-hoc `panel.state.X =` writes outside the store are permitted.
export const LIFECYCLE_STATE_FIELDS = Object.freeze([
  // Phase
  "phase",

  // Session / turn identity
  "sessionId",
  "turnId",

  // ── T5: Scope identity (lifecycle-store-owned) ──────────────────────────
  // Per-workflow chat scope: the scope this panel is bound to.  Matched
  // against event payloads and candidate metadata to prevent cross-scope
  // data from mutating the visible panel state.
  "chatScopeId",
  // Structural fingerprint of the graph at scope-capture time, used to
  // detect canvas drift without relying on backend baseline hashes.
  "chatScopeFingerprint",
  // The scope id of the candidate currently displayed.  Cleared on
  // INVALIDATE_CANDIDATE, set on candidate arrival, and checked by the
  // overlay before drawing.
  "candidateScopeId",
  // The scope id under which the current submit was initiated.  Set on
  // SUBMIT_START, cleared on SUBMIT_FINALLY and NEW_CONVERSATION.
  "submittingScopeId",

  // Baseline authority (mirrored from backend CAS)
  "baselineTurnId",
  "baselineGraphHash",
  "baselineGraphHashKind",
  "baselineGraphHashVersion",
  "baselineSource",
  "baselineRebaselineId",
  "baselineGraphSourcePath",

  // Candidate review
  "candidateGraph",
  "candidateGraphHash",
  "candidateReport",
  "serverSubmitGraphHash",
  "customNodeResolution",
  "nodePackInstallStates",

  // Status / messaging
  "message",
  "failure",
  "clarification",

  // Apply eligibility (derived)
  "applyAllowed",
  "applyEligibility",
  "applyEligibilityWarning",
  "applyEligibilityWarningKey",

  // Gate booleans
  "queueAllowed",
  "canvasApplyAllowed",

  // Audit / debug
  "auditRef",
  "debugPayload",

  // In-flight guards
  "inFlightSubmit",
  "submitAbortController",
  "submitEpoch",
  "inFlightApply",
  "inFlightRebaseline",

  // Rebaseline state
  "rebaselinePending",
  "rebaselineRecovery",

  // Submit / apply metadata
  "lastSubmit",
  "lastAppliedChanges",
  "lastSubmitFieldChanges",
  "changeDetails",

  // Boundary compartments
  "transcriptMessages",
  "responseDetails",
  "executionEvents",
  "auditArtifacts",
  "debugDiagnostics",
  "compartmentIndexes",

  // Epoch
  "chatRehydrateEpoch",
  "chatRehydrateCommittedEpoch",

  // Synthetic chat
  "syntheticAgentMessage",

  // V2 delta ops (mutation intent from submit response)
  "deltaOps",
]);

// ── createAgentEditState ───────────────────────────────────────────────────
// Returns a plain object with every lifecycle field initialized to its
// default value. The caller (roundtrip.js) spreads this into panel.state
// alongside non-lifecycle fields (history, chat, UI flags, etc.).
export function createAgentStateCompartments() {
  return {
    transcriptMessages: [],
    responseDetails: {},
    executionEvents: [],
    auditArtifacts: [],
    debugDiagnostics: {},
    compartmentIndexes: {
      responseDetailsByTurnId: {},
      executionEventsByKey: {},
      auditArtifactsByTurnId: {},
    },
  };
}

export function createAgentEditState() {
  return {
    phase: PANEL_STATE.IDLE,

    // Session / turn identity
    sessionId: null,
    turnId: null,

    // ── T5: Scope identity ──────────────────────────────────────────────
    chatScopeId: null,
    chatScopeFingerprint: null,
    candidateScopeId: null,
    submittingScopeId: null,

    // Baseline authority
    baselineTurnId: null,
    baselineGraphHash: null,
    baselineGraphHashKind: null,
    baselineGraphHashVersion: null,
    baselineSource: "none",
    baselineRebaselineId: null,
    baselineGraphSourcePath: null,

    // Candidate review
    candidateGraph: null,
    candidateGraphHash: null,
    candidateReport: null,
    serverSubmitGraphHash: null,
    customNodeResolution: null,
    nodePackInstallStates: {},

    // Status / messaging
    message: null,
    failure: null,
    clarification: null,

    // Apply eligibility (derived)
    applyAllowed: false,
    applyEligibility: null,
    applyEligibilityWarning: null,
    applyEligibilityWarningKey: null,

    // Gate booleans
    queueAllowed: false,
    canvasApplyAllowed: false,

    // Audit / debug
    auditRef: null,
    debugPayload: null,

    // In-flight guards
    inFlightSubmit: null,
    submitAbortController: null,
    submitEpoch: 0,
    inFlightApply: null,
    inFlightRebaseline: null,

    // Rebaseline state
    rebaselinePending: null,
    rebaselineRecovery: null,

    // Submit / apply metadata
    lastSubmit: null,
    lastAppliedChanges: null,
    lastSubmitFieldChanges: null,
    changeDetails: null,

    // Boundary compartments. These are the future selector sources for normal
    // transcript/detail state and explicit execution/audit/debug data.
    ...createAgentStateCompartments(),

    // Epoch
    chatRehydrateEpoch: 0,
    chatRehydrateCommittedEpoch: 0,

    // Synthetic chat
    syntheticAgentMessage: null,

    // V2 delta ops (mutation intent from submit response)
    deltaOps: null,
  };
}

// ── transition ─────────────────────────────────────────────────────────────
// Applies a lifecycle event to the panel's state and returns a plain
// obligations object describing the side effects roundtrip must fulfill.
//
// Parameters:
//   panel   — the panel object (must have .state)
//   event   — lifecycle event name (string)
//   payload — event-specific data (object, optional)
//
// Returns:
//   { render: true|false, toast?: string, ... }
//
// Unknown events return { render: false } (no-op, no side effects).
export function transition(panel, event, payload = {}) {
  if (!panel || !panel.state) {
    return { render: false };
  }

  switch (event) {
    // ── Foundation: Initialization ──────────────────────────────────────
    // State is already created by createAgentEditState(); INIT is a
    // no-op that signals the caller should repaint.
    case "INIT":
      return _obligations({
        render: true,
        dirtySections: ALL_RENDER_DIRTY_SECTIONS,
      });

    case "RESTORE_LIFECYCLE_BASELINE":
      return _handleRestoreLifecycleBaseline(panel, payload);

    // ── Foundation: Baseline sync ───────────────────────────────────────
    // Mirror authoritative baseline fields from a backend response payload.
    // Called after every backend response (submit success, failure, accept,
    // reject, rebaseline).
    case "SYNC_BASELINE":
      return _handleSyncBaseline(panel, payload);

    // ── Foundation: Candidate invalidation ──────────────────────────────
    // Clear candidate review fields. Called at submit start, clarify-only
    // response, candidate arrival, apply/reject/rebaseline success,
    // and new conversation.
    case "INVALIDATE_CANDIDATE":
      return _handleInvalidateCandidate(panel, payload);

    // ── Submit flow ────────────────────────────────────────────────────
    case "SUBMIT_IN_FLIGHT":
      panel.state.inFlightSubmit = payload?.promise || null;
      return { render: false };

    case "SUBMIT_START":
      return _handleSubmitStart(panel, payload);

    case "SUBMIT_READINESS_FAILURE":
      return _handleSubmitReadinessFailure(panel, payload);

    case "SUBMIT_MISSING_TASK":
      return _handleSubmitFailure(panel, {
        ...payload,
        phase: PANEL_STATE.ERROR,
        failure: payload?.failure || null,
        debugPayload: payload?.debugPayload || payload?.failure || null,
      });

    case "SUBMIT_SERIALIZE_ERROR":
      return _handleSubmitFailure(panel, {
        ...payload,
        phase: PANEL_STATE.ERROR,
        failure: payload?.failure || null,
        debugPayload: payload?.debugPayload || payload?.failure || null,
      });

    case "SUBMIT_SCOPE_MISMATCH":
      // ── T11: Scope mismatch blocks submit ──────────────────────────
      return _handleSubmitFailure(panel, {
        ...payload,
        phase: PANEL_STATE.ERROR,
        failure: payload?.failure || null,
        debugPayload: payload?.debugPayload || payload?.failure || null,
      });

    case "SUBMIT_ABORT_CONTROLLER":
      panel.state.submitAbortController = payload?.controller || null;
      return { render: false };

    case "SUBMIT_STALE_EPOCH":
      return { render: false, stale: true };

    case "SUBMIT_ABORT":
      return _handleSubmitAbort(panel, payload);

    case "SUBMIT_NETWORK_FAILURE":
    case "SUBMIT_BACKEND_FAILURE":
      return _handleSubmitNetworkFailure(panel, payload);

    case "MALFORMED_CANDIDATE_RESPONSE":
      return _handleSubmitNetworkFailure(panel, payload);

    case "CLARIFY_ONLY_RESPONSE":
      return _handleClarifyOnlyResponse(panel, payload);

    case "NOOP_RESPONSE":
      return _handleNoopResponse(panel, payload);

    case "REQUIRES_CUSTOM_NODES_RESPONSE":
      return _handleRequiresCustomNodesResponse(panel, payload);

    case "NODE_PACK_INSTALL_STARTED":
      return _handleNodePackInstallStarted(panel, payload);

    case "NODE_PACK_INSTALL_SUCCEEDED":
      return _handleNodePackInstallFinished(panel, payload, { failed: false });

    case "NODE_PACK_INSTALL_FAILED":
      return _handleNodePackInstallFinished(panel, payload, { failed: true });

    case "ARRIVAL_SERIALIZE_FAILURE":
      return _handleArrivalSerializeFailure(panel, payload);

    case "OK_CANDIDATE_RESPONSE":
    case "EDIT_CLARIFY_RESPONSE":
      return _handleCandidateResponse(panel, payload);

    case "SUBMIT_FINALLY":
      return _handleSubmitFinally(panel, payload);

    // ── Stop / new conversation ────────────────────────────────────────
    case "STOP_ABORT":
      return _handleStopAbort(panel, payload);
    // ── New conversation ────────────────────────────────────────────────
    case "NEW_CONVERSATION":
      return _handleNewConversation(panel);

    // ── T5: Scope switch ─────────────────────────────────────────────────
    // Transitions the panel to a new workflow scope.  Scope identity fields
    // are updated; candidate is invalidated (it belongs to the old scope).
    case "SCOPE_SWITCH":
      return _handleScopeSwitch(panel, payload);

    // ── Chat rehydrate ────────────────────────────────────────────────
    case "CHAT_REHYDRATE_START":
      return _handleChatRehydrateStart(panel);

    case "CHAT_REHYDRATE_NO_SESSION":
      return _handleChatRehydrateNoSession(panel, payload);

    case "CHAT_REHYDRATE_MISSING_SESSION":
      return _handleChatRehydrateMissingSession(panel, payload);

    case "CHAT_REHYDRATE_SUCCESS":
      return _handleChatRehydrateSuccess(panel, payload);

    case "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE":
      return _handleChatRehydrateRestoreLatestCandidate(panel, payload);

    case "CHAT_REHYDRATE_FAILURE":
      return _handleChatRehydrateFailure(panel, payload);

    // ── Apply flow ───────────────────────────────────────────────────
    case "APPLY_PREFLIGHT_BLOCKED":
      return _handleApplyPreflightBlocked(panel, payload);

    case "APPLY_MISSING_FIELDS":
    case "APPLY_SERIALIZE_ERROR":
    case "APPLY_ELIGIBILITY_BLOCKED":
    case "APPLY_SCOPE_MISMATCH":
      return _handleApplyBlockedFailure(panel, payload);

    case "APPLY_IN_FLIGHT":
      panel.state.inFlightApply = payload?.promise || null;
      return { render: false };

    case "APPLY_STARTED":
      return _handleApplyStarted(panel, payload);

    case "ACCEPT_REJECTED":
      return _handleAcceptRejected(panel, payload);

    case "STALE_CANVAS_APPLY":
      return _handleStaleCanvasApply(panel, payload);

    case "CANVAS_APPLY_FAILURE":
      return _handleCanvasApplyFailure(panel, payload);

    case "APPLY_SUCCESS":
      return _handleApplySuccess(panel, payload);

    case "APPLY_FINALLY":
      if (payload?.clearInFlightApply) {
        panel.state.inFlightApply = null;
      }
      return { render: false };

    // ── Reject flow ────────────────────────────────────────────────────
    case "REJECT_STARTED":
      return _handleRejectStarted(panel, payload);

    case "REJECT_FAILURE":
      return _handleRejectFailure(panel, payload);

    case "REJECT_SUCCESS":
      return _handleRejectSuccess(panel, payload);

    // ── Rebaseline / stale recovery ───────────────────────────────────
    case "REBASELINE_IN_FLIGHT":
      panel.state.inFlightRebaseline = payload?.promise || null;
      return { render: false };

    case "REBASELINE_STARTED":
      return _handleRebaselineStarted(panel, payload);

    case "REBASELINE_SUCCESS":
      return _handleRebaselineSuccess(panel, payload);

    case "REBASELINE_FAILURE":
      return _handleRebaselineFailure(panel, payload);

    case "REBASELINE_FINALLY":
      if (payload?.clearInFlightRebaseline) {
        panel.state.inFlightRebaseline = null;
      }
      return { render: true };

    case "REBASELINE_RECOVERY_SYNC":
      return _handleRebaselineRecoverySync(panel, payload);

    case "STALE_RECOVERY_REBASELINE_QUEUED":
      return _handleStaleRecoveryRebaselineQueued(panel);

    case "STALE_RECOVERY_REBASELINE_SUCCESS":
      return _handleStaleRecoveryRebaselineSuccess(panel, payload);

    case "STALE_RECOVERY_REBASELINE_FAILURE":
      return _handleStaleRecoveryRebaselineFailure(panel, payload);

    // ── Undo flow ──────────────────────────────────────────────────────
    case "UNDO_LOCAL_RESTORE":
      return _handleUndoLocalRestore(panel, payload);

    case "UNDO_REBASELINE_SUCCESS":
      return _handleUndoRebaselineSuccess(panel, payload);

    case "UNDO_REBASELINE_FAILURE":
      return _handleUndoRebaselineFailure(panel, payload);

    // ── Unknown / no-op ─────────────────────────────────────────────────
    default:
      // Unrecognized event: no state mutation, no side effects.
      return { render: false };
  }
}

// ── normalizeObligationDirtySections ────────────────────────────────────────
// De-duplicates and validates `dirtySections` in an obligations object
// while preserving the `render` key and all other obligation keys.
//
// Returns a new obligations object (shallow copy) with a normalized
// `dirtySections` array. Throws for unknown render section names.
export function normalizeObligationDirtySections(obligations) {
  if (!obligations || typeof obligations !== "object") {
    return obligations;
  }

  const raw = obligations.dirtySections;
  if (raw === undefined || raw === null) {
    return obligations;
  }

  if (!Array.isArray(raw)) {
    throw new Error(
      `dirtySections must be an array, got ${typeof raw}`,
    );
  }

  const validSections = Object.values(RENDER_SECTIONS);
  const validSet = new Set(validSections);
  const seen = new Set();
  const normalized = [];

  for (let i = 0; i < raw.length; i++) {
    const section = raw[i];
    if (typeof section !== "string") {
      throw new Error(
        `dirtySections[${i}] must be a string, got ${typeof section}`,
      );
    }
    if (!validSet.has(section)) {
      throw new Error(
        `Unknown render section: "${section}". Valid sections: ${validSections.join(", ")}`,
      );
    }
    if (!seen.has(section)) {
      seen.add(section);
      normalized.push(section);
    }
  }

  return { ...obligations, dirtySections: normalized };
}

function _obligations({ render = false, dirtySections, ...extras } = {}) {
  const obligations = { render, ...extras };
  if (dirtySections !== undefined) {
    obligations.dirtySections = dirtySections;
  }
  return normalizeObligationDirtySections(obligations);
}

// ── normalizeDeltaOpsFromSubmit ────────────────────────────────────────────
// Extracts and normalizes delta ops from a V2 submit response.
//
// Canonical path (preferred): consumes ``delta_ops_envelope``
// (``{schema_version: "2.0.0", ops: [...]}``) produced by the backend
// persistence layer.  Each op is validated against the canonical contract
// (exactly six op types, add_node must carry ``uid`` and ``node_id``).
//
// Legacy bridge: falls back to ``delta_ops`` as a flat V2 array when the
// canonical envelope is absent.  Legacy wrapped mappings are rejected as
// ``legacy_delta_shape`` so consumers do not silently confuse audit metadata
// with canonical ops.
//
// Diagnostic codes are aligned with the Python backend:
//   - ``malformed_delta`` — structurally invalid envelope or op
//   - ``legacy_delta_shape`` — legacy wrapped mapping, must migrate
//   - ``missing_delta_ops`` — no delta payload present
//
// Returns a stable plain array of normalized delta-op objects (shallow-cloned,
// keys sorted), or ``null`` when absent/invalid.  When ``null`` is returned,
// a ``_deltaDiagnostic`` property is set on the result object (if mutable)
// so callers can surface the diagnostic code in the UI.
//
// This function is the single browser-side gate for delta ops before they
// reach preview, apply, and accept state.
export function normalizeDeltaOpsFromSubmit(result) {
  if (!result || typeof result !== "object") {
    return null;
  }

  // ── Canonical path: delta_ops_envelope with {schema_version, ops} ────
  try {
    const ops = normalizeDeltaOpsFromSubmitPayload(result);
    // Successfully normalized — clear any previous diagnostic.
    if (result && typeof result === "object") {
      delete result._deltaDiagnostic;
    }
    if (ops.length === 0) {
      // Backward compat: an empty legacy flat delta_ops array (length 0)
      // returns []; all-invalid entries after filtering returns null.
      const rawDeltaOps = result.delta_ops;
      if (Array.isArray(rawDeltaOps) && rawDeltaOps.length === 0) {
        return [];
      }
      return null;
    }
    return ops;
  } catch (err) {
    // Surface the diagnostic code on the result for UI consumers.
    if (err instanceof DeltaDiagnosticError) {
      if (result && typeof result === "object") {
        result._deltaDiagnostic = {
          code: err.code,
          message: err.message,
          detail: err.detail || {},
        };
      }
    } else {
      if (result && typeof result === "object") {
        result._deltaDiagnostic = {
          code: DELTA_DIAGNOSTIC_MALFORMED,
          message: err.message || "Unknown delta normalization error.",
          detail: {},
        };
      }
    }
    return null;
  }
}

// ── T10: Scope-aware event routing guard ───────────────────────────────────
// Pure predicate used by the websocket event handlers in vibecomfy_roundtrip.js
// to decide whether an incoming agent-turn or executor-phase event may mutate
// the visible singleton panel state or bind `panel.state.sessionId`.
//
// The caller (event handler) resolves the scoped session via
// resolveScopeSessionId(panel.state.chatScopeId) and passes it as
// `scopedSessionId`.  This function has zero storage or DOM dependencies
// so it can be unit-tested in Node.js.
//
// Returns true when the event is safe to process, false when it must be
// silently dropped.

/**
 * @param {object} panelState — panel.state (plain object with at minimum
 *   chatScopeId, phase, sessionId)
 * @param {string|null} eventSessionId — session_id carried by the event
 * @param {string|null} scopedSessionId — resolveScopeSessionId(chatScopeId)
 * @returns {boolean}
 */
export function eventSessionMatchesActiveScope(panelState, eventSessionId, scopedSessionId) {
  const chatScopeId = panelState?.chatScopeId;
  if (!chatScopeId) {
    // No scope tracking — accept all events (backward compatible).
    return true;
  }
  if (!eventSessionId) {
    // An event without a session_id cannot be validated against a scope.
    // Reject it when scope tracking is active to prevent un-scoped events
    // from mutating the panel.
    return false;
  }
  if (scopedSessionId) {
    // A session is already bound to this scope — the event must match it.
    return eventSessionId === scopedSessionId;
  }
  // No session bound to this scope yet — first allocation.
  // Allow only if the panel is in SUBMITTING phase (actively waiting for
  // the first turn response) OR if the panel has already bound the same
  // session in memory (e.g., from a previous rehydrate before scope tracking
  // was fully activated).
  const inMemorySession = panelState?.sessionId;
  if (inMemorySession) {
    return eventSessionId === inMemorySession;
  }
  return panelState?.phase === "SUBMITTING";
}

// ── Canonical reducer projections ──────────────────────────────────────────

function _strictSelectorRead(selector, source, options = {}) {
  if (!source || typeof source !== "object") {
    return null;
  }
  try {
    return selector(source, { allowLegacy: false, ...options });
  } catch (_error) {
    return null;
  }
}

function _canonicalSourceFromPayload(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  return payload.result || payload.response || payload.baseline || payload.raw || null;
}

function _readStageSnapshotForTransition(payload) {
  return _strictSelectorRead(readStageSnapshot, _canonicalSourceFromPayload(payload));
}

function _readDurableTurnIdentityForTransition(payload) {
  const source = _canonicalSourceFromPayload(payload);
  const identity = _strictSelectorRead(readTurnIdentity, source);
  if (identity) {
    return {
      sessionId:
        identity.sessionId
        || (typeof payload?.sessionId === "string" && payload.sessionId ? payload.sessionId : null),
      turnId:
        identity.turnId
        || (typeof payload?.turnId === "string" && payload.turnId ? payload.turnId : null),
      baselineTurnId:
        identity.baselineTurnId
        || (typeof payload?.baselineTurnId === "string" && payload.baselineTurnId
          ? payload.baselineTurnId
          : null),
      idempotencyKey:
        identity.idempotencyKey
        || (typeof payload?.idempotencyKey === "string" && payload.idempotencyKey
          ? payload.idempotencyKey
          : null),
    };
  }
  return {
    sessionId: typeof payload?.sessionId === "string" && payload.sessionId ? payload.sessionId : null,
    turnId: typeof payload?.turnId === "string" && payload.turnId ? payload.turnId : null,
    baselineTurnId:
      typeof payload?.baselineTurnId === "string" && payload.baselineTurnId
        ? payload.baselineTurnId
        : null,
    idempotencyKey:
      typeof payload?.idempotencyKey === "string" && payload.idempotencyKey
        ? payload.idempotencyKey
        : null,
  };
}

function _writeDurableTurnIdentity(panel, payload, { clearMissingTurn = true } = {}) {
  const identity = _readDurableTurnIdentityForTransition(payload);
  panel.state.sessionId = _stringOrCurrent(identity?.sessionId, panel.state.sessionId);
  if (identity?.turnId) {
    panel.state.turnId = identity.turnId;
  } else if (clearMissingTurn) {
    panel.state.turnId = null;
  }
  return identity;
}

function _readApplyCandidateForTransition(payload) {
  const source = _canonicalSourceFromPayload(payload);
  const candidate = _strictSelectorRead(readApplyCandidate, source);
  if (candidate) {
    return candidate;
  }
  const candidateGraph = payload?.candidateGraph;
  if (!candidateGraph || typeof candidateGraph !== "object") {
    return null;
  }
  const eligibility = payload?.applyEligibility && typeof payload.applyEligibility === "object"
    ? payload.applyEligibility
    : null;
  return {
    state: "candidate",
    graph: candidateGraph,
    graphHash:
      typeof payload?.candidateGraphHash === "string" && payload.candidateGraphHash
        ? payload.candidateGraphHash
        : null,
    candidateGraphHash:
      typeof payload?.candidateGraphHash === "string" && payload.candidateGraphHash
        ? payload.candidateGraphHash
        : null,
    submitGraphHash:
      typeof payload?.serverSubmitGraphHash === "string" && payload.serverSubmitGraphHash
        ? payload.serverSubmitGraphHash
        : null,
    eligibility,
    applyable: eligibility ? eligibility.applyable === true : payload?.applyAllowed === true,
    turnIdentity: _readDurableTurnIdentityForTransition(payload),
  };
}

function _readFieldChangesForTransition(payload) {
  const source = _canonicalSourceFromPayload(payload);
  const changes = _strictSelectorRead(readFieldChanges, source);
  if (changes && Array.isArray(changes.all) && changes.all.length > 0) {
    return changes;
  }
  if (payload?.lastSubmitFieldChanges) {
    return {
      directChanges: [],
      outcomeChanges: [],
      legacyChanges: [],
      batchTurnChanges: [],
      all: payload.lastSubmitFieldChanges,
    };
  }
  return changes || {
    directChanges: [],
    outcomeChanges: [],
    legacyChanges: [],
    batchTurnChanges: [],
    all: [],
  };
}

function _lastSubmitFieldChangesForTransition(payload) {
  if (payload?.lastSubmitFieldChanges) {
    return payload.lastSubmitFieldChanges;
  }
  const changes = _readFieldChangesForTransition(payload);
  return changes.all.length > 0 ? changes : null;
}

function _writeLatestCandidateTransition(panel, payload) {
  const candidate = _readApplyCandidateForTransition(payload);
  const candidateGraph = candidate?.graph || null;
  if (!candidateGraph || typeof candidateGraph !== "object") {
    return null;
  }

  const stageSnapshot = _readStageSnapshotForTransition(payload);
  const identity = _writeDurableTurnIdentity(panel, {
    ...payload,
    turnId: candidate?.turnIdentity?.turnId || payload?.turnId || null,
    sessionId: candidate?.turnIdentity?.sessionId || payload?.sessionId || null,
    baselineTurnId: candidate?.turnIdentity?.baselineTurnId || payload?.baselineTurnId || null,
  });
  const fieldChanges = _lastSubmitFieldChangesForTransition(payload);
  const applyEligibility = candidate?.eligibility || payload?.applyEligibility || null;
  const applyAllowed = Boolean(candidateGraph && applyEligibility?.applyable === true);

  panel.state.phase = PANEL_STATE.AWAITING_REVIEW;
  _handleSyncBaseline(panel, payload?.baseline || payload?.result || {});
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.candidateGraph = candidateGraph;
  panel.state.candidateGraphHash =
    candidate?.graphHash
    || candidate?.candidateGraphHash
    || (typeof payload?.candidateGraphHash === "string" ? payload.candidateGraphHash : null);
  panel.state.candidateReport = payload?.candidateReport || payload?.result?.report || null;
  panel.state.serverSubmitGraphHash =
    candidate?.submitGraphHash
    || (typeof payload?.serverSubmitGraphHash === "string" ? payload.serverSubmitGraphHash : null);
  // ── T5: Bind restored candidate to the current chat scope ──────────────
  panel.state.candidateScopeId = panel.state.submittingScopeId || panel.state.chatScopeId;
  panel.state.message = payload?.message || payload?.result?.message || null;
  panel.state.failure = null;
  panel.state.clarification = payload?.clarification || null;
  panel.state.applyEligibility = applyEligibility;
  panel.state.applyAllowed = applyAllowed;
  panel.state.canvasApplyAllowed = applyAllowed;
  panel.state.queueAllowed = Boolean(payload?.queueAllowed);
  panel.state.auditRef = payload?.auditRef || payload?.result?.audit_ref || panel.state.auditRef || null;
  panel.state.lastSubmitFieldChanges = fieldChanges;
  panel.state.changeDetails = payload?.changeDetails || null;
  panel.state.deltaOps = normalizeDeltaOpsFromSubmit(payload?.baseline?.raw || payload?.baseline || payload?.result || {});
  panel.state.debugPayload = payload?.debugPayload || null;
  if (stageSnapshot) {
    panel.state.debugPayload = {
      ...(panel.state.debugPayload || {}),
      stageSnapshot,
    };
  }
  return { candidate, identity, stageSnapshot };
}

// ── Internal handlers ──────────────────────────────────────────────────────

function _handleSyncBaseline(panel, payload) {
  if (!payload || typeof payload !== "object") {
    return { render: false };
  }

  const hadExplicitSource = Object.prototype.hasOwnProperty.call(payload, "baseline_source");

  if ("baseline_turn_id" in payload) {
    panel.state.baselineTurnId = typeof payload.baseline_turn_id === "string"
      ? payload.baseline_turn_id
      : null;
  }
  if ("baseline_graph_hash" in payload) {
    panel.state.baselineGraphHash = typeof payload.baseline_graph_hash === "string"
      ? payload.baseline_graph_hash
      : null;
  }
  if ("baseline_graph_hash_kind" in payload) {
    panel.state.baselineGraphHashKind = typeof payload.baseline_graph_hash_kind === "string"
      ? payload.baseline_graph_hash_kind
      : null;
  }
  if ("baseline_graph_hash_version" in payload) {
    panel.state.baselineGraphHashVersion = Number.isFinite(payload.baseline_graph_hash_version)
      ? payload.baseline_graph_hash_version
      : null;
  }
  if ("baseline_source" in payload) {
    panel.state.baselineSource = typeof payload.baseline_source === "string"
      ? payload.baseline_source
      : "none";
  }
  if ("baseline_rebaseline_id" in payload) {
    panel.state.baselineRebaselineId = typeof payload.baseline_rebaseline_id === "string"
      ? payload.baseline_rebaseline_id
      : null;
  }
  if ("baseline_graph_source_path" in payload) {
    panel.state.baselineGraphSourcePath = typeof payload.baseline_graph_source_path === "string"
      ? payload.baseline_graph_source_path
      : null;
  }

  // Infer baseline source when not explicitly provided.
  if (!hadExplicitSource && payload.action === "accept" && payload.ok === true) {
    panel.state.baselineSource = "turn";
    panel.state.baselineRebaselineId = null;
    panel.state.baselineGraphSourcePath = typeof payload.turn_id === "string"
      ? `turns/${payload.turn_id}/candidate.ui.json`
      : null;
  } else if (
    !hadExplicitSource
    && panel.state.baselineTurnId
    && typeof panel.state.baselineGraphHash === "string"
    && panel.state.baselineGraphHash
  ) {
    panel.state.baselineSource = "turn";
    panel.state.baselineRebaselineId = null;
    if (!panel.state.baselineGraphSourcePath) {
      panel.state.baselineGraphSourcePath = `turns/${panel.state.baselineTurnId}/candidate.ui.json`;
    }
  } else if (
    !hadExplicitSource
    && panel.state.baselineTurnId == null
    && typeof panel.state.baselineGraphHash === "string"
    && panel.state.baselineGraphHash
    && panel.state.baselineRebaselineId
  ) {
    panel.state.baselineSource = "rebaseline";
  } else if (
    !hadExplicitSource
    && panel.state.baselineTurnId == null
    && panel.state.baselineGraphHash == null
  ) {
    panel.state.baselineSource = "none";
    panel.state.baselineRebaselineId = null;
    panel.state.baselineGraphSourcePath = null;
  }

  _syncRebaselineRecovery(panel, payload);

  return { render: true };
}

function _handleInvalidateCandidate(panel, payload) {
  const repaint = payload && typeof payload === "object" && "repaint" in payload
    ? payload.repaint
    : true;

  // Clear candidate review fields
  panel.state.candidateGraph = null;
  panel.state.candidateGraphHash = null;
  panel.state.candidateReport = null;
  panel.state.serverSubmitGraphHash = null;
  panel.state.applyEligibility = null;
  panel.state.applyEligibilityWarning = null;
  panel.state.applyEligibilityWarningKey = null;
  panel.state.changeDetails = null;
  panel.state.customNodeResolution = null;

  // ── T5: Clear candidate scope identity ────────────────────────────────
  panel.state.candidateScopeId = null;

  // Clear V2 delta ops — mutation intent is invalidated with the candidate.
  panel.state.deltaOps = null;

  // Clear preview diff caches (these are transient keys that live on state
  // but are not lifecycle-owned; we clean them up here as the candidate
  // invalidation logically invalidates any preview derived from it).
  delete panel.state._previewDiff;
  delete panel.state._previewDiffGraphHash;
  delete panel.state._previewDiffCacheTag;

  return { render: repaint };
}

const LIFECYCLE_BASELINE_RESTORE_FIELDS = Object.freeze([
  "phase",
  "sessionId",
  "turnId",
  "baselineTurnId",
  "chatScopeId",
  "chatScopeFingerprint",
  "candidateScopeId",
  "submittingScopeId",
  "baselineGraphHash",
  "baselineGraphHashKind",
  "baselineGraphHashVersion",
  "baselineSource",
  "baselineRebaselineId",
  "baselineGraphSourcePath",
  "candidateGraph",
  "candidateGraphHash",
  "candidateReport",
  "serverSubmitGraphHash",
  "customNodeResolution",
  "nodePackInstallStates",
  "message",
  "failure",
  "clarification",
  "applyAllowed",
  "applyEligibility",
  "applyEligibilityWarning",
  "applyEligibilityWarningKey",
  "queueAllowed",
  "canvasApplyAllowed",
  "auditRef",
  "debugPayload",
  "inFlightSubmit",
  "submitAbortController",
  "submitEpoch",
  "inFlightApply",
  "inFlightRebaseline",
  "rebaselinePending",
  "rebaselineRecovery",
  "lastSubmit",
  "lastAppliedChanges",
  "lastSubmitFieldChanges",
  "changeDetails",
  "chatMessages",
  "transcriptMessages",
  "responseDetails",
  "executionEvents",
  "auditArtifacts",
  "debugDiagnostics",
  "compartmentIndexes",
  "chatRehydrateEpoch",
  "chatRehydrateCommittedEpoch",
  "syntheticAgentMessage",
  "deltaOps",
]);

function _cloneLifecycleBaselineValue(value) {
  if (value == null || typeof value !== "object") {
    return value;
  }
  try {
    return JSON.parse(JSON.stringify(value));
  } catch (_e) {
    return value;
  }
}

function _handleRestoreLifecycleBaseline(panel, payload) {
  const baseline = payload?.baseline && typeof payload.baseline === "object"
    ? payload.baseline
    : {};
  for (const field of LIFECYCLE_BASELINE_RESTORE_FIELDS) {
    if (Object.prototype.hasOwnProperty.call(baseline, field)) {
      panel.state[field] = _cloneLifecycleBaselineValue(baseline[field]);
    }
  }
  if (Object.prototype.hasOwnProperty.call(payload || {}, "debugPayload")) {
    panel.state.debugPayload = payload.debugPayload || null;
  }
  return _obligations({
    render: false,
    dirtySections: ALL_RENDER_DIRTY_SECTIONS,
    restored: true,
  });
}

function _handleSubmitStart(panel, payload) {
  const previousEpoch = Number.isFinite(panel.state.submitEpoch) ? panel.state.submitEpoch : 0;
  const submitEpoch = Number.isFinite(payload?.submitEpoch) ? payload.submitEpoch : previousEpoch + 1;
  panel.state.submitEpoch = submitEpoch;
  panel.state.phase = PANEL_STATE.SUBMITTING;
  panel.state.syntheticAgentMessage = null;
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.failure = null;
  panel.state.clarification = null;
  panel.state.lastAppliedChanges = null;
  panel.state.lastSubmitFieldChanges = null;
  panel.state.lastSubmit = payload?.lastSubmit || null;
  // ── T9: Stamp scope identity into debug payload so diagnostics always
  // trace back to the workflow that produced them.  Scope metadata is only
  // added when a scope is active — null scope values are not stamped.
  if (panel.state.chatScopeId) {
    panel.state.debugPayload = payload?.debugPayload
      ? { ...payload.debugPayload, _scopeId: panel.state.chatScopeId, _scopeFingerprint: panel.state.chatScopeFingerprint }
      : { _scopeId: panel.state.chatScopeId, _scopeFingerprint: panel.state.chatScopeFingerprint };
  } else {
    panel.state.debugPayload = payload?.debugPayload || null;
  }
  // ── T5: Capture submitting scope for candidate cross-check ─────────────
  panel.state.submittingScopeId = panel.state.chatScopeId;
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    submitEpoch,
    invalidateCandidate: true,
    clearChangedNodeFeedbackVisuals: true,
  });
}

function _handleSubmitReadinessFailure(panel, payload) {
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.failure = null;
  panel.state.debugPayload = payload?.debugPayload || null;
  return { render: true };
}

function _handleSubmitFailure(panel, payload) {
  panel.state.phase = payload?.phase || PANEL_STATE.ERROR;
  panel.state.failure = payload?.failure || null;
  panel.state.debugPayload = payload?.debugPayload || panel.state.failure || null;
  _recordExplicitLocalPayload(panel, panel.state.failure || panel.state.debugPayload, {
    debugPayload: panel.state.debugPayload,
  });
  return { render: true };
}

function _handleSubmitAbort(panel, payload) {
  panel.state.phase = PANEL_STATE.IDLE;
  panel.state.failure = null;
  panel.state.deltaOps = null;
  panel.state.message = payload?.message || "Request cancelled.";
  panel.state.syntheticAgentMessage = _projectSyntheticTranscriptMessage(payload?.syntheticAgentMessage || {
    role: "agent",
    text: panel.state.message,
    session_id: panel.state.sessionId || null,
    synthetic: true,
    local_id: `cancelled:${Date.now()}`,
  });
  panel.state.debugPayload = payload?.debugPayload || {
    cancelled: true,
    last_submit: panel.state.lastSubmit,
  };
  _recordExplicitLocalPayload(panel, {
    session_id: panel.state.sessionId || null,
    message: panel.state.message,
    debugPayload: panel.state.debugPayload,
    cancelled: true,
  }, { debugPayload: panel.state.debugPayload });
  return { render: true, refreshQueueGuard: true };
}

function _handleSubmitNetworkFailure(panel, payload) {
  const failure = payload?.failure || null;
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.failure = failure;
  panel.state.turnId = _stringOrCurrent(failure?.turn_id, panel.state.turnId);
  panel.state.sessionId = _stringOrCurrent(failure?.session_id, panel.state.sessionId);
  _handleSyncBaseline(panel, failure || {});
  _syncRebaselineRecovery(panel, failure || {});
  panel.state.auditRef = failure?.audit_ref || null;
  panel.state.syntheticAgentMessage = _projectSyntheticTranscriptMessage(payload?.syntheticAgentMessage);
  panel.state.debugPayload = payload?.debugPayload || {
    ...(failure || {}),
    last_submit: panel.state.lastSubmit,
  };
  _recordExplicitLocalPayload(panel, failure || panel.state.debugPayload, {
    debugPayload: panel.state.debugPayload,
  });
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: panel.state.sessionId || null,
    refreshQueueGuard: true,
    rehydrateChat: true,
  });
}

function _handleClarifyOnlyResponse(panel, payload) {
  const result = payload?.result || {};
  panel.state.phase = PANEL_STATE.CLARIFY;
  _writeDurableTurnIdentity(panel, payload);
  _handleSyncBaseline(panel, result);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.clarification = payload?.clarification || null;
  panel.state.message = payload?.message || panel.state.clarification?.message || null;
  panel.state.failure = null;
  panel.state.canvasApplyAllowed = false;
  panel.state.applyAllowed = false;
  panel.state.applyEligibility = null;
  panel.state.queueAllowed = false;
  panel.state.auditRef = payload?.auditRef || null;
  panel.state.lastSubmitFieldChanges = _lastSubmitFieldChangesForTransition(payload);
  panel.state.debugPayload = payload?.debugPayload || {
    ...result,
    last_submit: panel.state.lastSubmit,
  };
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: panel.state.sessionId || null,
    refreshQueueGuard: true,
    rehydrateChat: Boolean(panel.state.sessionId),
    invalidateCandidate: true,
  });
}

function _handleNoopResponse(panel, payload) {
  const result = payload?.result || {};
  panel.state.phase = PANEL_STATE.IDLE;
  _writeDurableTurnIdentity(panel, payload);
  _handleSyncBaseline(panel, result);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.clarification = null;
  panel.state.message = payload?.message || result.message || null;
  panel.state.failure = null;
  panel.state.canvasApplyAllowed = false;
  panel.state.applyAllowed = false;
  panel.state.applyEligibility = null;
  panel.state.queueAllowed = false;
  panel.state.auditRef = payload?.auditRef || null;
  panel.state.lastSubmitFieldChanges = _lastSubmitFieldChangesForTransition(payload);
  panel.state.changeDetails = payload?.changeDetails || null;
  panel.state.debugPayload = payload?.debugPayload || {
    ...result,
    last_submit: panel.state.lastSubmit,
  };
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: panel.state.sessionId || null,
    refreshQueueGuard: true,
    rehydrateChat: Boolean(panel.state.sessionId),
    invalidateCandidate: true,
  });
}

function _readCustomNodeResolutionForTransition(payload) {
  const sources = [
    payload?.result,
    payload?.response,
    payload?.debugPayload?.response,
    payload,
  ];
  for (const source of sources) {
    if (!source || typeof source !== "object") {
      continue;
    }
    try {
      const resolution = readCustomNodeResolution(source, { allowLegacy: true });
      if (resolution) {
        return resolution;
      }
    } catch (_err) {
      // Optional evidence only; raw payload remains available in debugPayload.
    }
  }
  return null;
}

function _installKeyForCandidate(candidate) {
  if (!candidate || typeof candidate !== "object") {
    return null;
  }
  if (typeof candidate.stableInstallHash === "string" && candidate.stableInstallHash) {
    return candidate.stableInstallHash;
  }
  if (typeof candidate.stable_install_hash === "string" && candidate.stable_install_hash) {
    return candidate.stable_install_hash;
  }
  const pack = candidate.pack && typeof candidate.pack === "object" ? candidate.pack : null;
  const slug = typeof pack?.slug === "string" && pack.slug
    ? pack.slug
    : (typeof pack?.name === "string" && pack.name ? pack.name : null);
  return slug ? `pack:${slug}` : null;
}

function _snakeCaseInstallCandidate(candidate) {
  if (!candidate || typeof candidate !== "object") {
    return null;
  }
  const expectedClasses = Array.isArray(candidate.expectedClasses)
    ? candidate.expectedClasses
    : (Array.isArray(candidate.expected_classes) ? candidate.expected_classes : []);
  return {
    pack: candidate.pack && typeof candidate.pack === "object" ? candidate.pack : {},
    expected_classes: expectedClasses.map((item) => String(item)).filter(Boolean),
    validation_mode: candidate.validationMode || candidate.validation_mode || "evidence_only",
    stable_install_hash: candidate.stableInstallHash || candidate.stable_install_hash || null,
  };
}

export function buildNodePackInstallRequest(candidate, { confirmed = true } = {}) {
  const installCandidate = _snakeCaseInstallCandidate(candidate);
  if (!installCandidate) {
    return null;
  }
  return {
    endpoint: "/vibecomfy/node-packs/install",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: {
      candidate: installCandidate,
      stable_install_hash: installCandidate.stable_install_hash,
      user_confirmed: confirmed === true,
    },
  };
}

function _handleRequiresCustomNodesResponse(panel, payload) {
  const result = payload?.result || {};
  panel.state.phase = PANEL_STATE.IDLE;
  _writeDurableTurnIdentity(panel, payload);
  _handleSyncBaseline(panel, result);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.customNodeResolution =
    payload?.customNodeResolution || _readCustomNodeResolutionForTransition(payload);
  panel.state.clarification = null;
  panel.state.message = payload?.message || result.message || result.reply || null;
  panel.state.failure = null;
  panel.state.canvasApplyAllowed = false;
  panel.state.applyAllowed = false;
  panel.state.applyEligibility = null;
  panel.state.queueAllowed = false;
  panel.state.auditRef = payload?.auditRef || null;
  panel.state.lastSubmitFieldChanges = _lastSubmitFieldChangesForTransition(payload);
  panel.state.changeDetails = payload?.changeDetails || null;
  panel.state.debugPayload = payload?.debugPayload || {
    ...result,
    customNodeResolution: panel.state.customNodeResolution,
    last_submit: panel.state.lastSubmit,
  };
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: panel.state.sessionId || null,
    refreshQueueGuard: true,
    rehydrateChat: Boolean(panel.state.sessionId),
    invalidateCandidate: true,
  });
}

function _ensureNodePackInstallStates(panel) {
  if (!panel.state.nodePackInstallStates || typeof panel.state.nodePackInstallStates !== "object") {
    panel.state.nodePackInstallStates = {};
  }
  return panel.state.nodePackInstallStates;
}

function _handleNodePackInstallStarted(panel, payload) {
  const candidate = payload?.candidate || null;
  const key = _installKeyForCandidate(candidate);
  const request = buildNodePackInstallRequest(candidate, { confirmed: payload?.confirmed !== false });
  if (!key || !request) {
    return _obligations({
      render: true,
      dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    });
  }
  const states = _ensureNodePackInstallStates(panel);
  states[key] = {
    status: "installing",
    installing: true,
    candidate,
    result: null,
    message: "Installing node pack...",
  };
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    nodePackInstallRequest: request,
    nodePackInstallKey: key,
  });
}

function _handleNodePackInstallFinished(panel, payload, { failed = false } = {}) {
  const candidate = payload?.candidate || null;
  const result = payload?.result && typeof payload.result === "object" ? payload.result : {};
  const key =
    payload?.installKey
    || _installKeyForCandidate(candidate)
    || _installKeyForCandidate(result?.candidate)
    || null;
  if (!key) {
    return _obligations({
      render: true,
      dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    });
  }
  const validationStatus =
    typeof result.validation_status === "string" && result.validation_status
      ? result.validation_status
      : null;
  const status = failed || result.ok === false
    ? "validation_failed"
    : (validationStatus || result.status || "installed");
  const validationSucceeded = status === "installed" && result.validated === true;
  if (validationSucceeded) {
    panel.state.customNodeResolution = null;
  }
  const states = _ensureNodePackInstallStates(panel);
  states[key] = {
    ...(states[key] || {}),
    status,
    installing: false,
    candidate: candidate || states[key]?.candidate || null,
    result,
    message:
      result.message
      || result.error
      || (status === "installed"
        ? "Node pack installed. Submit again to retry with local schemas."
        : "Node pack install finished."),
  };
  const obligations = {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
  };
  if (validationSucceeded) {
    obligations.focusPrompt = true;
    obligations.retryCustomNodeResolution = {
      reason: "node_pack_installed",
      expectedClasses: Array.isArray(result.expected_classes) ? [...result.expected_classes] : [],
    };
  }
  return _obligations(obligations);
}

function _handleArrivalSerializeFailure(panel, payload) {
  const result = payload?.result || {};
  panel.state.phase = PANEL_STATE.ERROR;
  _handleSyncBaseline(panel, result);
  panel.state.failure = payload?.failure || null;
  panel.state.debugPayload = payload?.debugPayload || {
    ...(panel.state.failure || {}),
    last_submit: panel.state.lastSubmit,
    response: result,
  };
  return { render: true };
}

function _handleCandidateResponse(panel, payload) {
  const result = payload?.result || {};
  panel.state.phase = PANEL_STATE.AWAITING_REVIEW;
  const projectedCandidate = _readApplyCandidateForTransition(payload);
  const projectedIdentity = projectedCandidate?.turnIdentity || _readDurableTurnIdentityForTransition(payload);

  // SD2: Applyable means durable. When a candidate response arrives but both
  // session_id and turn_id are absent in the raw response, the response is
  // malformed/non-applyable. Override eligibility to block Apply with
  // retry/debug guidance and prevent this path from being misclassified as
  // stale/rebaseline.
  // Check the raw response directly — panel.state may carry stale identity
  // from a previous turn via _stringOrCurrent.
  // Having at least one (session_id or turn_id) provides partial durable identity.
  const candidateGraph = projectedCandidate?.graph || payload?.candidateGraph || null;
  const hasDurableIdentity = Boolean(projectedIdentity?.sessionId || projectedIdentity?.turnId);
  const missingDurableEligibility =
    !hasDurableIdentity && candidateGraph && typeof candidateGraph === "object"
      ? {
          applyable: false,
          reason: "missing_durable_turn_metadata",
          message:
            "Candidate is missing durable session/turn metadata and cannot be applied. "
            + "Retry the submit or inspect the raw response in the debug panel.",
          warnings: ["missing_durable_turn_metadata"],
        }
      : null;

  _writeDurableTurnIdentity(panel, {
    ...payload,
    sessionId: projectedIdentity?.sessionId || null,
    turnId: projectedIdentity?.turnId || null,
  });
  _handleSyncBaseline(panel, result);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.candidateGraph = candidateGraph;
  panel.state.candidateGraphHash =
    projectedCandidate?.graphHash
    || projectedCandidate?.candidateGraphHash
    || (typeof payload?.candidateGraphHash === "string" ? payload.candidateGraphHash : null);
  panel.state.candidateReport = result.report || null;
  panel.state.serverSubmitGraphHash =
    projectedCandidate?.submitGraphHash
    || (typeof payload?.serverSubmitGraphHash === "string" ? payload.serverSubmitGraphHash : null);
  // ── T5: Bind candidate to the submitting scope ─────────────────────────
  panel.state.candidateScopeId = panel.state.submittingScopeId || panel.state.chatScopeId;
  panel.state.message = result.message || null;
  panel.state.failure = null;
  panel.state.clarification = payload?.clarification || null;
  panel.state.applyEligibility =
    missingDurableEligibility || projectedCandidate?.eligibility || payload?.applyEligibility || null;
  const candidateActionAllowed = Boolean(
    candidateGraph && panel.state.applyEligibility?.applyable === true,
  );
  panel.state.applyAllowed = missingDurableEligibility ? false : candidateActionAllowed;
  panel.state.canvasApplyAllowed = missingDurableEligibility ? false : candidateActionAllowed;
  panel.state.queueAllowed = Boolean(payload?.queueAllowed);
  panel.state.auditRef = payload?.auditRef || null;
  panel.state.lastSubmitFieldChanges = _lastSubmitFieldChangesForTransition(payload);
  panel.state.changeDetails = payload?.changeDetails || null;
  panel.state.deltaOps = normalizeDeltaOpsFromSubmit(result);
  panel.state.debugPayload = payload?.debugPayload || {
    ...result,
    last_submit: panel.state.lastSubmit,
    ...(missingDurableEligibility ? { debug_branch: "malformed_metadata" } : {}),
  };
  const stageSnapshot = _readStageSnapshotForTransition(payload);
  if (stageSnapshot) {
    panel.state.debugPayload = {
      ...(panel.state.debugPayload || {}),
      stageSnapshot,
    };
  }
  return _obligations({
    render: true,
    dirtySections: REVIEW_DIRTY_SECTIONS,
    persistSession: panel.state.sessionId || null,
    setQueueGuardContext: {
      sessionId: panel.state.sessionId,
      turnId: panel.state.turnId,
      queueAllowed: panel.state.queueAllowed,
    },
    refreshQueueGuard: true,
    rehydrateChat: Boolean(panel.state.sessionId),
    invalidateCandidate: true,
  });
}

function _handleSubmitFinally(panel, payload) {
  if (payload?.clearAbortController) {
    panel.state.submitAbortController = null;
  }
  if (payload?.clearInFlightSubmit) {
    panel.state.inFlightSubmit = null;
  }
  // ── T5: Clear submitting scope on submit finish ────────────────────────
  if (payload?.clearSubmittingScope !== false) {
    panel.state.submittingScopeId = null;
  }
  return { render: false };
}

function _handleStopAbort(panel, payload) {
  const previousEpoch = Number.isFinite(panel.state.submitEpoch) ? panel.state.submitEpoch : 0;
  panel.state.submitEpoch = previousEpoch + 1;
  panel.state.submitAbortController = null;
  panel.state.inFlightSubmit = null;
  panel.state.phase = PANEL_STATE.IDLE;
  panel.state.failure = null;
  panel.state.deltaOps = null;
  panel.state.message = payload?.message || "Request cancelled.";
  panel.state.syntheticAgentMessage = _projectSyntheticTranscriptMessage(payload?.syntheticAgentMessage || {
    role: "agent",
    text: panel.state.message,
    session_id: panel.state.sessionId || null,
    synthetic: true,
    local_id: `cancelled:${Date.now()}`,
  });
  panel.state.debugPayload = payload?.debugPayload || {
    cancelled: true,
    last_submit: panel.state.lastSubmit,
  };
  _recordExplicitLocalPayload(panel, {
    session_id: panel.state.sessionId || null,
    message: panel.state.message,
    debugPayload: panel.state.debugPayload,
    cancelled: true,
  }, { debugPayload: panel.state.debugPayload });
  return { render: true, refreshQueueGuard: true };
}

function _handleNewConversation(panel) {
  const nextSubmitEpoch = (Number.isFinite(panel.state.submitEpoch) ? panel.state.submitEpoch : 0) + 1;
  const nextChatRehydrateEpoch =
    (Number.isFinite(panel.state.chatRehydrateEpoch) ? panel.state.chatRehydrateEpoch : 0) + 1;
  // ── T9: Preserve scope identity — new conversation clears chat data
  // within the current scope but does not unbind from the workflow.
  // Scope B's saved state (in _scopeSnapshots) is untouched.
  const departingScopeId = panel.state.chatScopeId;
  const departingScopeFingerprint = panel.state.chatScopeFingerprint;
  _handleInvalidateCandidate(panel, { repaint: false });
  Object.assign(panel.state, createAgentEditState(), {
    submitEpoch: nextSubmitEpoch,
    chatRehydrateEpoch: nextChatRehydrateEpoch,
    // ── T9: Keep the panel bound to the same workflow scope ────────────
    chatScopeId: departingScopeId,
    chatScopeFingerprint: departingScopeFingerprint,
  });
  return _obligations({
    render: true,
    dirtySections: [
      RENDER_SECTIONS.THREAD,
      RENDER_SECTIONS.META,
      RENDER_SECTIONS.COMPOSER,
      RENDER_SECTIONS.NOTICE,
    ],
    invalidateCandidate: true,
    // ── T9: Clear queue guard for current scope only ────────────────────
    queueGuardClearScope: departingScopeId || null,
    refreshQueueGuard: true,
    forgetSession: true,
    focusPrompt: true,
    // ── T7: Clear scope snapshot when explicitly starting fresh ──────────
    forgetScope: departingScopeId || null,
  });
}

// ── T7: Scope switch ─────────────────────────────────────────────────────────
// Enhanced from T5 skeleton: now saves the departing scope's full panel state
// as a runtime snapshot, restores the arriving scope's snapshot (if one exists),
// preserves draft text, clears stale apply/undo affordances, and explicitly
// excludes undoStack from all snapshot operations (SD3).
function _handleScopeSwitch(panel, payload) {
  const oldScopeId = panel.state.chatScopeId;
  const scopeId = typeof payload?.scopeId === "string" && payload.scopeId
    ? payload.scopeId
    : null;
  const fingerprint = typeof payload?.fingerprint === "string" && payload.fingerprint
    ? payload.fingerprint
    : null;

  // ── T7: Save departing scope state ─────────────────────────────────────
  // Snapshot all current panel.state fields (except undoStack, DOM refs,
  // and ephemeral render state) keyed by the OLD scope id.  This preserves
  // chat messages, history, session identity, composer state, queue guard
  // state, diagnostics metadata, and all lifecycle fields so the user can
  // return to this workflow later and pick up where they left off.
  if (oldScopeId && oldScopeId !== scopeId) {
    saveScopeSnapshot(oldScopeId, panel);
  }

  // Invalidate the current candidate — it belongs to the old scope.
  _handleInvalidateCandidate(panel, { repaint: false });

  // Update scope identity from payload.
  panel.state.chatScopeId = scopeId;
  panel.state.chatScopeFingerprint = fingerprint;
  panel.state.candidateScopeId = null;
  panel.state.submittingScopeId = null;

  // Clear submit-in-flight state — any in-flight submit belongs to the old scope.
  panel.state.inFlightSubmit = null;
  panel.state.submitAbortController = null;
  panel.state.failure = null;
  panel.state.clarification = null;

  // ── T7: Restore arriving scope state (if snapshot exists) ──────────────
  // The snapshot restoration merges all saved fields back onto panel.state
  // while leaving undoStack untouched.  When no snapshot exists this is a
  // true fresh-scope transition — the lifecycle fields remain at their
  // post-switch defaults.
  const restored = scopeId ? restoreScopeSnapshot(scopeId, panel) : false;

  return _obligations({
    render: true,
    dirtySections: [
      RENDER_SECTIONS.THREAD,
      RENDER_SECTIONS.META,
      RENDER_SECTIONS.COMPOSER,
      RENDER_SECTIONS.NOTICE,
    ],
    invalidateCandidate: true,
    // ── T7: Clear undo affordances on scope switch ─────────────────────────
    // Undo entries belong to the workflow's canvas context (SD3).  After a
    // scope switch the visible panel must not offer undo for a different
    // workflow.  The undo stack itself survives on panel.state but the
    // affordances (button emphasis, menu entries) are reset.
    clearUndoAffordance: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    rehydrateChat: Boolean(scopeId),
    // ── T7: Flag indicating a draft prompt exists for the arriving scope ──
    // The obligation fulfiller reads the DOM prompt element and restores the
    // saved draft text when present.
    restoreScopeDraft: scopeId,
    // Metadata for the obligation fulfiller so it can save the departing
    // scope's draft before the DOM repaint clears the prompt box.
    departingScopeId: oldScopeId !== scopeId ? oldScopeId : null,
    restored,
  });
}

function _handleChatRehydrateStart(panel) {
  const requestEpoch =
    (Number.isFinite(panel.state.chatRehydrateEpoch) ? panel.state.chatRehydrateEpoch : 0) + 1;
  panel.state.chatRehydrateEpoch = requestEpoch;
  return { render: false, requestEpoch };
}

function _handleChatRehydrateNoSession(panel, payload) {
  if (_isStaleChatRehydrate(panel, payload?.requestEpoch)) {
    return { render: false, stale: true };
  }
  panel.state.chatMessages = [];
  Object.assign(panel.state, createAgentStateCompartments());
  panel.state.chatLoaded = false;
  panel.state.chatError = null;
  panel.state.chatSessionPath = null;
  panel.state.chatDetailJsonPath = null;
  panel.state.chatSessionPathResolved = null;
  panel.state.chatDetailJsonPathResolved = null;
  return _obligations({
    render: false,
    dirtySections: THREAD_DIRTY_SECTIONS,
  });
}

function _handleChatRehydrateMissingSession(panel, payload) {
  if (_isStaleChatRehydrate(panel, payload?.requestEpoch)) {
    return { render: false, stale: true };
  }
  const confirmedSessionId = typeof payload?.sessionId === "string" ? payload.sessionId : null;
  if (confirmedSessionId && panel.state.sessionId === confirmedSessionId) {
    panel.state.sessionId = null;
  }
  panel.state.chatMessages = [];
  Object.assign(panel.state, createAgentStateCompartments());
  panel.state.chatLoaded = true;
  panel.state.chatError = null;
  panel.state.chatSessionPath = null;
  panel.state.chatDetailJsonPath = null;
  panel.state.chatSessionPathResolved = null;
  panel.state.chatDetailJsonPathResolved = null;
  return _obligations({
    render: false,
    dirtySections: confirmedSessionId ? META_AND_THREAD_DIRTY_SECTIONS : THREAD_DIRTY_SECTIONS,
    forgetSession: true,
  });
}

function _handleChatRehydrateSuccess(panel, payload) {
  if (_isStaleChatRehydrate(panel, payload?.requestEpoch)) {
    const committedEpoch = Number.isFinite(panel.state.chatRehydrateCommittedEpoch)
      ? panel.state.chatRehydrateCommittedEpoch
      : 0;
    if (committedEpoch > payload?.requestEpoch) {
      return { render: false, stale: true };
    }
  }
  const ingested = ingestChatRehydratePayload(panel.state, payload);
  // Compatibility mirror contract: chatMessages mirrors only safe
  // TranscriptMessage output. Raw rehydrate detail is projection input for
  // responseDetails/executionEvents/auditArtifacts/debugDiagnostics below.
  // Delete the chatMessages mirror after normal consumers/tests use transcript
  // selectors and diagnostics/reporting no longer needs legacy transcript
  // fallback behavior.
  // Reconcile durable backend messages with any in-flight optimistic entries
  // (T9). When the panel is SUBMITTING, unmatched optimistic messages from the
  // current epoch are preserved after canonical messages; otherwise canonical
  // replaces wholesale (backward-compatible with existing behaviour).
  panel.state.chatMessages = ingested.chatMessages;
  panel.state.transcriptMessages = panel.state.chatMessages.slice();
  // Preserve locally-built Queue/detail compartments for turns the backend
  // rehydrate projection does not repopulate (e.g. queueAllowed/eligibility).
  // Merge per-turn: ingested fields win, but existing queueDisplay/candidate
  // compartments are kept when the rehydrate projection drops them.
  const existingResponseDetails = panel.state.responseDetails || {};
  const mergedResponseDetails = { ...existingResponseDetails, ...ingested.responseDetails };
  const PRESERVED_DETAIL_KEYS = ["queueDisplay", "candidate", "eligibility"];
  for (const turnId of Object.keys(ingested.responseDetails)) {
    const existingDetail = existingResponseDetails[turnId];
    const ingestedDetail = ingested.responseDetails[turnId];
    if (!existingDetail) {
      continue;
    }
    let mergedDetail = null;
    for (const key of PRESERVED_DETAIL_KEYS) {
      if (existingDetail?.[key] != null && ingestedDetail?.[key] == null) {
        mergedDetail ||= { ...ingestedDetail };
        mergedDetail[key] = existingDetail[key];
      }
    }
    if (mergedDetail) {
      mergedResponseDetails[turnId] = mergedDetail;
    }
  }
  panel.state.responseDetails = mergedResponseDetails;
  panel.state.executionEvents = ingested.executionEvents;
  panel.state.turns = ingested.turns;
  panel.state.auditArtifacts = ingested.auditArtifacts;
  panel.state.debugDiagnostics = ingested.debugDiagnostics;
  panel.state.compartmentIndexes = {
    ...(panel.state.compartmentIndexes || {}),
    ...ingested.compartmentIndexes,
    responseDetailsByTurnId: {
      ...(panel.state.compartmentIndexes?.responseDetailsByTurnId || {}),
      ...ingested.compartmentIndexes.responseDetailsByTurnId,
    },
  };
  panel.state.chatLoaded = true;
  panel.state.chatError = null;
  panel.state.chatSessionPath = typeof payload?.chatSessionPath === "string" ? payload.chatSessionPath : null;
  panel.state.chatDetailJsonPath = typeof payload?.chatDetailJsonPath === "string" ? payload.chatDetailJsonPath : null;
  panel.state.chatSessionPathResolved = typeof payload?.chatSessionPathResolved === "string" ? payload.chatSessionPathResolved : null;
  panel.state.chatDetailJsonPathResolved = typeof payload?.chatDetailJsonPathResolved === "string" ? payload.chatDetailJsonPathResolved : null;
  const sessionId = typeof payload?.sessionId === "string" && payload.sessionId ? payload.sessionId : null;
  if (sessionId) {
    panel.state.sessionId = sessionId;
  }
  const latestCandidate =
    payload?.latestCandidate && typeof payload.latestCandidate === "object"
      ? payload.latestCandidate
      : null;
  const latestCandidateIsReviewable = latestCandidate?.outcome?.kind === "candidate";
  const latestTurnId = typeof payload?.latestTurnId === "string" && payload.latestTurnId
    ? payload.latestTurnId
    : null;
  const currentCandidateTurnId = typeof panel.state.turnId === "string" && panel.state.turnId
    ? panel.state.turnId
    : null;
  const rehydrateCaughtUpToCandidate =
    !currentCandidateTurnId
    || (latestTurnId && latestTurnId >= currentCandidateTurnId);
  if (
    !latestCandidateIsReviewable
    && rehydrateCaughtUpToCandidate
    && panel.state.phase !== PANEL_STATE.SUBMITTING
    && panel.state.phase !== PANEL_STATE.APPLYING
  ) {
    _handleInvalidateCandidate(panel, { repaint: false });
    if (panel.state.phase === PANEL_STATE.AWAITING_REVIEW) {
      panel.state.phase = PANEL_STATE.IDLE;
    }
    panel.state.applyAllowed = false;
    panel.state.canvasApplyAllowed = false;
    panel.state.queueAllowed = false;
  }
  if (Number.isFinite(payload?.requestEpoch)) {
    panel.state.chatRehydrateCommittedEpoch = Math.max(
      Number.isFinite(panel.state.chatRehydrateCommittedEpoch) ? panel.state.chatRehydrateCommittedEpoch : 0,
      payload.requestEpoch,
    );
  }
  return _obligations({
    render: false,
    dirtySections: sessionId ? META_AND_THREAD_DIRTY_SECTIONS : THREAD_DIRTY_SECTIONS,
    persistSession: sessionId,
  });
}

function _turnIdFromResponseDetail(detail) {
  const turn = detail && typeof detail === "object" ? detail.turn : null;
  return typeof turn?.turnId === "string" && turn.turnId ? turn.turnId : null;
}

function _turnIdFromEvent(event) {
  return typeof event?.turn_id === "string" && event.turn_id ? event.turn_id : null;
}

function _turnIdFromAuditArtifact(artifact) {
  return typeof artifact?.turn_id === "string" && artifact.turn_id ? artifact.turn_id : null;
}

function _diagnosticEventKey(event, index) {
  const sessionId = typeof event?.session_id === "string" && event.session_id ? event.session_id : "session";
  const turnId = _turnIdFromEvent(event) || `entry-${index}`;
  return `${sessionId}:${turnId}:${index}`;
}

function _hasExplicitDebugRecord(event) {
  return Boolean(
    event?.debugPayload
    || (Array.isArray(event?.reasoning) && event.reasoning.length)
    || (Array.isArray(event?.diagnostics) && event.diagnostics.length)
    || (Array.isArray(event?.providerDiagnostics) && event.providerDiagnostics.length)
    || (
      event?.providerDiagnostics
      && typeof event.providerDiagnostics === "object"
      && !Array.isArray(event.providerDiagnostics)
      && Object.keys(event.providerDiagnostics).length
    )
    || (Array.isArray(event?.batchTurns) && event.batchTurns.length)
  );
}

function _indexResponseDetails(details) {
  const responseDetails = {};
  const responseDetailsByTurnId = {};
  details.forEach((detail, index) => {
    const key = _turnIdFromResponseDetail(detail) || `message-${index}`;
    responseDetails[key] = detail;
    if (_turnIdFromResponseDetail(detail)) {
      responseDetailsByTurnId[_turnIdFromResponseDetail(detail)] = key;
    }
  });
  return { responseDetails, responseDetailsByTurnId };
}

function _indexExecutionEvents(events) {
  const executionEventsByKey = {};
  events.forEach((event, index) => {
    executionEventsByKey[_diagnosticEventKey(event, index)] = index;
  });
  return executionEventsByKey;
}

function _indexAuditArtifacts(artifacts) {
  const auditArtifactsByTurnId = {};
  artifacts.forEach((artifact, index) => {
    const turnId = _turnIdFromAuditArtifact(artifact);
    if (turnId) {
      auditArtifactsByTurnId[turnId] = index;
    }
  });
  return auditArtifactsByTurnId;
}

function _stableTurnSessionId(value) {
  return typeof value === "string" && value ? value : "none";
}

function _batchTurnKey(sessionId, turnNumber) {
  return `batch:${_stableTurnSessionId(sessionId)}:${turnNumber}`;
}

function _durableTurnKey(entry) {
  const sessionId = _stableTurnSessionId(entry?.session_id);
  const status = entry?.status || "unknown";
  if (entry?.turn_id) {
    return `durable:${sessionId}:${entry.turn_id}:${status}`;
  }
  const fallback = entry?.timestamp || entry?.message || entry?.task || entry?.failure_kind || "pending";
  return `durable:${sessionId}:${status}:${fallback}`;
}

function _sortCompatibilityTurns(turns) {
  const durable = [];
  const batch = [];
  const other = [];
  for (const entry of Array.isArray(turns) ? turns : []) {
    if (entry?.entry_type === "durable") {
      durable.push(entry);
    } else if (entry?.entry_type === "batch") {
      batch.push(entry);
    } else {
      other.push(entry);
    }
  }
  batch.sort((left, right) => {
    const leftNumber = Number.isFinite(left?.turn_number) ? left.turn_number : -1;
    const rightNumber = Number.isFinite(right?.turn_number) ? right.turn_number : -1;
    return rightNumber - leftNumber;
  });
  return [...durable, ...batch, ...other].slice(0, 64);
}

function _compatibilityTurnsFromExecutionEvents(events) {
  const turns = [];
  for (const event of Array.isArray(events) ? events : []) {
    const sessionId = typeof event?.session_id === "string" && event.session_id ? event.session_id : null;
    const batchTurns = Array.isArray(event?.batchTurns) ? event.batchTurns : [];
    for (const batchTurn of batchTurns) {
      if (!batchTurn || typeof batchTurn !== "object") {
        continue;
      }
      const rawTurnNumber = batchTurn.turn_number;
      const turnNumber = Number.isInteger(rawTurnNumber)
        ? rawTurnNumber
        : (typeof rawTurnNumber === "number" && Number.isFinite(rawTurnNumber) ? Math.trunc(rawTurnNumber) : null);
      if (!sessionId || turnNumber == null) {
        continue;
      }
      const entry = {
        entry_type: "batch",
        turn_key: _batchTurnKey(sessionId, turnNumber),
        session_id: sessionId,
        turn_id: typeof batchTurn.turn_id === "string" && batchTurn.turn_id ? batchTurn.turn_id : event.turn_id || null,
        parent_turn_id: event.turn_id || null,
        turn_number: turnNumber,
        status:
          typeof batchTurn.status === "string" && batchTurn.status
            ? (batchTurn.status === "progress" ? "in_progress" : batchTurn.status)
            : (batchTurn.batch_ok === true ? "done" : "in_progress"),
        message: typeof batchTurn.message === "string" ? batchTurn.message : event.message || null,
        timestamp: typeof batchTurn.timestamp === "string" ? batchTurn.timestamp : null,
        clarification_required: false,
        clarification_message: null,
        batch_ok: typeof batchTurn.batch_ok === "boolean" ? batchTurn.batch_ok : null,
        statement_count: typeof batchTurn.statement_count === "number" && Number.isFinite(batchTurn.statement_count) ? batchTurn.statement_count : null,
        landed_op_count: typeof batchTurn.landed_op_count === "number" && Number.isFinite(batchTurn.landed_op_count) ? batchTurn.landed_op_count : null,
        statements: Array.isArray(batchTurn.statements) ? batchTurn.statements : null,
        diagnostics: Array.isArray(batchTurn.diagnostics) ? batchTurn.diagnostics : null,
        budget: batchTurn.budget && typeof batchTurn.budget === "object" ? batchTurn.budget : null,
        exit_mode: typeof batchTurn.exit_mode === "string" ? batchTurn.exit_mode : null,
        done_summary: typeof batchTurn.done_summary === "string" ? batchTurn.done_summary : null,
        audit_ref: batchTurn.audit_ref && typeof batchTurn.audit_ref === "object" ? batchTurn.audit_ref : null,
        raw_payload: batchTurn,
        source: "rehydrate",
        source_priority: 3,
        canonical_activity: null,
      };
      turns.push(entry);
    }
    if (!batchTurns.length && (event?.turn_id || event?.status || event?.message)) {
      const entry = {
        entry_type: "durable",
        status: event.status || "done",
        session_id: sessionId,
        turn_id: event.turn_id || null,
        baseline_turn_id: event.baseline_turn_id || null,
        task: event.task || null,
        timestamp: event.timestamp || null,
        failure_kind: event.failure_kind || null,
        failure_stage: event.failure_stage || null,
        message: event.message || null,
        audit_ref: event.auditRef || event.audit_ref || null,
        raw_payload: null,
      };
      entry.turn_key = _durableTurnKey(entry);
      turns.push(entry);
    }
  }
  return _sortCompatibilityTurns(turns);
}

function _ensureBoundaryCompartments(panel) {
  if (!panel?.state) {
    return;
  }
  if (!Array.isArray(panel.state.transcriptMessages)) {
    panel.state.transcriptMessages = [];
  }
  if (!panel.state.responseDetails || typeof panel.state.responseDetails !== "object") {
    panel.state.responseDetails = {};
  }
  if (!Array.isArray(panel.state.executionEvents)) {
    panel.state.executionEvents = [];
  }
  if (!Array.isArray(panel.state.auditArtifacts)) {
    panel.state.auditArtifacts = [];
  }
  if (!panel.state.debugDiagnostics || typeof panel.state.debugDiagnostics !== "object") {
    panel.state.debugDiagnostics = {};
  }
  if (!panel.state.compartmentIndexes || typeof panel.state.compartmentIndexes !== "object") {
    panel.state.compartmentIndexes = {};
  }
  panel.state.compartmentIndexes.responseDetailsByTurnId ||= {};
  panel.state.compartmentIndexes.executionEventsByKey ||= {};
  panel.state.compartmentIndexes.auditArtifactsByTurnId ||= {};
}

function _syncCompartmentIndexes(panel) {
  if (!panel?.state) {
    return;
  }
  panel.state.compartmentIndexes = {
    responseDetailsByTurnId: _indexResponseDetails(
      Object.values(panel.state.responseDetails || {}),
    ).responseDetailsByTurnId,
    executionEventsByKey: _indexExecutionEvents(panel.state.executionEvents || []),
    auditArtifactsByTurnId: _indexAuditArtifacts(panel.state.auditArtifacts || []),
  };
}

function _recordExplicitLocalPayload(panel, rawPayload, options = {}) {
  if (!rawPayload || typeof rawPayload !== "object") {
    return;
  }
  _ensureBoundaryCompartments(panel);
  const source = {
    ...rawPayload,
    debugPayload:
      options.debugPayload
      || rawPayload.debugPayload
      || rawPayload.debug_payload
      || rawPayload.debug
      || rawPayload,
  };
  const detail = projectResponseDetail(source);
  const detailTurnId = _turnIdFromResponseDetail(detail);
  if (detail && detailTurnId) {
    panel.state.responseDetails[detailTurnId] = detail;
  }
  const event = projectExecutionEvent(source);
  if (event) {
    panel.state.executionEvents.push(event);
    panel.state.debugDiagnostics.local = [
      ...(Array.isArray(panel.state.debugDiagnostics.local) ? panel.state.debugDiagnostics.local : []),
      {
        key: _diagnosticEventKey(event, panel.state.executionEvents.length - 1),
        session_id: event.session_id,
        turn_id: event.turn_id,
        debugPayload: event.debugPayload,
        reasoning: event.reasoning,
        providerDiagnostics: event.providerDiagnostics,
        batchTurns: event.batchTurns,
      },
    ];
  }
  const artifact = projectAuditArtifact(source);
  if (artifact?.auditRef || (Array.isArray(artifact?.artifactRefs) && artifact.artifactRefs.length)) {
    panel.state.auditArtifacts.push(artifact);
  }
  _syncCompartmentIndexes(panel);
}

function _projectSyntheticTranscriptMessage(message) {
  return projectTranscriptMessage(message);
}

export function ingestChatRehydratePayload(panelState, payload) {
  const rawMessages = Array.isArray(payload?.messages) ? payload.messages : [];
  const existingProjection = splitRehydrateProjectionInput({
    messages: Array.isArray(panelState?.chatMessages) ? panelState.chatMessages : [],
  });
  const rehydrateProjection = splitRehydrateProjectionInput({
    ...payload,
    messages: rawMessages,
  });
  const chatMessages = reconcileChatMessages(
    existingProjection.normalTranscriptMessage,
    rehydrateProjection.normalTranscriptMessage,
    panelState,
  );
  const { responseDetails, responseDetailsByTurnId } =
    _indexResponseDetails(rehydrateProjection.normalResponseDetail);
  const executionEvents = rehydrateProjection.explicitDiagnosticEvent.slice();
  const auditArtifacts = rehydrateProjection.explicitAuditArtifact.slice();
  const debugRecords = executionEvents
    .filter(_hasExplicitDebugRecord)
    .map((event, index) => ({
      key: _diagnosticEventKey(event, index),
      session_id: event.session_id,
      turn_id: event.turn_id,
      reasoning: event.reasoning,
      diagnostics: event.diagnostics,
      providerDiagnostics: event.providerDiagnostics,
      debugPayload: event.debugPayload,
      batchTurns: event.batchTurns,
    }));

  return {
    chatMessages,
    // Compatibility mirror contract: turns is derived from ExecutionEvent data
    // for diagnostic/audit compatibility. Delete after diagnostics, reports,
    // and tests consume execution selectors directly.
    turns: _compatibilityTurnsFromExecutionEvents(executionEvents),
    responseDetails,
    executionEvents,
    auditArtifacts,
    debugDiagnostics: {
      rehydrate: debugRecords,
    },
    compartmentIndexes: {
      responseDetailsByTurnId,
      executionEventsByKey: _indexExecutionEvents(executionEvents),
      auditArtifactsByTurnId: _indexAuditArtifacts(auditArtifacts),
    },
  };
}

function _handleChatRehydrateRestoreLatestCandidate(panel, payload) {
  if (
    panel.state.phase === PANEL_STATE.SUBMITTING
    || panel.state.phase === PANEL_STATE.APPLYING
  ) {
    return { render: false, skipped: true };
  }

  // ── T8: Scope boundary refusal ─────────────────────────────────────────
  // requestScopeId is the scope captured by _rehydrateChat at fetch-initiate
  // time.  If the visible panel has switched to a different scope while the
  // fetch was in flight (or between rehydrate and the caller's guard), refuse
  // to restore — a candidate from scope A must never populate scope B.
  if (typeof payload?.requestScopeId === "string" && payload.requestScopeId) {
    if (panel.state.chatScopeId !== payload.requestScopeId) {
      return { render: false, skipped: true, stale: true };
    }
  }

  // ── T8: Cross-session boundary refusal ─────────────────────────────────
  // When the candidate's session id is explicitly known and differs from the
  // panel's current session id (and both are set), the candidate belongs to
  // a different workflow's session and must not be restored into this scope.
  if (
    typeof payload?.candidateSessionId === "string" && payload.candidateSessionId
    && typeof panel.state.sessionId === "string" && panel.state.sessionId
    && panel.state.sessionId !== payload.candidateSessionId
  ) {
    return { render: false, skipped: true, stale: true };
  }

  const restored = _writeLatestCandidateTransition(panel, payload);
  if (!restored) {
    return { render: false, skipped: true };
  }

  return _obligations({
    render: false,
    dirtySections: REVIEW_DIRTY_SECTIONS,
    restored: true,
    invalidateCandidate: true,
    persistSession: panel.state.sessionId || null,
    setQueueGuardContext: {
      sessionId: panel.state.sessionId,
      turnId: panel.state.turnId,
      queueAllowed: panel.state.queueAllowed,
    },
    refreshQueueGuard: true,
  });
}

function _handleChatRehydrateFailure(panel, payload) {
  if (_isStaleChatRehydrate(panel, payload?.requestEpoch)) {
    return { render: false, stale: true };
  }
  // Preserve locally-built optimistic messages (including promoted pending
  // response bubbles) so a failed backend rehydrate does not wipe the thread.
  // Non-optimistic durable messages are cleared as before.
  panel.state.chatMessages = Array.isArray(panel.state.chatMessages)
    ? panel.state.chatMessages
      .filter((message) => message?.optimistic === true)
      .map(projectTranscriptMessage)
      .filter(Boolean)
    : [];
  panel.state.transcriptMessages = panel.state.chatMessages.slice();
  panel.state.chatLoaded = false;
  panel.state.chatError = payload?.chatError || null;
  panel.state.chatSessionPath = null;
  panel.state.chatDetailJsonPath = null;
  return _obligations({
    render: false,
    dirtySections: THREAD_DIRTY_SECTIONS,
  });
}

function _handleApplyPreflightBlocked(_panel, _payload) {
  return { render: false };
}

function _handleApplyBlockedFailure(panel, payload) {
  const shouldClear = Boolean(payload?.clearCandidatePreview);
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.failure = payload?.failure || null;
  if (shouldClear) {
    _handleInvalidateCandidate(panel, { repaint: false });
  }
  panel.state.debugPayload = payload?.debugPayload || panel.state.failure || null;
  return _obligations({
    render: true,
    dirtySections: STATUS_DIRTY_SECTIONS,
    invalidateCandidate: shouldClear,
    clearCandidatePreview: shouldClear,
  });
}

function _handleApplyStarted(panel, payload) {
  panel.state.phase = PANEL_STATE.APPLYING;
  panel.state.failure = null;
  panel.state.debugPayload = payload?.debugPayload || {
    applying_turn_id: panel.state.turnId,
    accept_request: payload?.acceptBody || null,
  };
  return { render: true };
}

function _handleAcceptRejected(panel, payload) {
  const failure = payload?.failure || null;
  const authoritativeBackendReject = Boolean(payload?.authoritativeBackendReject);
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.failure = failure;
  panel.state.syntheticAgentMessage = _projectSyntheticTranscriptMessage(payload?.syntheticAgentMessage);
  if (authoritativeBackendReject) {
    panel.state.applyEligibility = payload?.disabledApplyEligibility || null;
    panel.state.applyAllowed = false;
    panel.state.canvasApplyAllowed = false;
    panel.state.queueAllowed = false;
  }
  _handleSyncBaseline(panel, failure || {});
  _syncRebaselineRecovery(panel, payload);
  panel.state.auditRef = failure?.audit_ref || panel.state.auditRef;
  panel.state.debugPayload = payload?.debugPayload || {
    ...(failure || {}),
    accept_request: payload?.acceptBody || null,
  };
  return _obligations({
    render: true,
    queueGuardClear: authoritativeBackendReject,
    refreshQueueGuard: authoritativeBackendReject,
  });
}

function _handleStaleCanvasApply(panel, payload) {
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.failure = payload?.failure || null;
  panel.state.syntheticAgentMessage = _projectSyntheticTranscriptMessage(payload?.syntheticAgentMessage);
  _syncRebaselineRecovery(panel, payload);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.debugPayload = payload?.debugPayload || panel.state.failure || null;
  return _obligations({
    render: true,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
}

function _handleCanvasApplyFailure(panel, payload) {
  const failure = payload?.failure || null;
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.failure = failure;
  panel.state.syntheticAgentMessage = _projectSyntheticTranscriptMessage(payload?.syntheticAgentMessage);
  panel.state.auditRef = failure?.audit_ref || panel.state.auditRef;
  panel.state.debugPayload = payload?.debugPayload || {
    ...(failure || {}),
    accepted: payload?.accepted || null,
    undo_stack_depth: Number.isFinite(payload?.undoStackDepth) ? payload.undoStackDepth : null,
  };
  return _obligations({
    render: true,
  });
}

function _handleApplySuccess(panel, payload) {
  const accepted = payload?.accepted || {};
  panel.state.phase = PANEL_STATE.IDLE;
  _handleSyncBaseline(panel, accepted);
  panel.state.baselineTurnId = panel.state.baselineTurnId || panel.state.turnId || null;
  panel.state.auditRef = accepted.audit_ref || panel.state.auditRef;
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.message = null;
  panel.state.queueAllowed = false;
  panel.state.canvasApplyAllowed = false;
  panel.state.applyAllowed = false;
  panel.state.lastAppliedChanges = payload?.lastAppliedChanges || null;
  panel.state.debugPayload = payload?.debugPayload || {
    accepted,
    undo_stack_depth: Number.isFinite(payload?.undoStackDepth) ? payload.undoStackDepth : null,
  };
  return _obligations({
    render: true,
    dirtySections: [
      ...STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
      RENDER_SECTIONS.COMPOSER,
    ],
    invalidateCandidate: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    toast: payload?.toast || null,
  });
}

function _handleRejectStarted(panel, payload) {
  panel.state.phase = PANEL_STATE.APPLYING;
  panel.state.failure = null;
  panel.state.debugPayload = payload?.debugPayload || {
    rejecting_turn_id: panel.state.turnId,
    reject_request: payload?.rejectBody || null,
  };
  return { render: true };
}

function _handleRejectFailure(panel, payload) {
  const failure = payload?.failure || null;
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.failure = failure;
  _handleSyncBaseline(panel, failure || {});
  panel.state.auditRef = (failure && failure.audit_ref) || panel.state.auditRef;
  panel.state.debugPayload = payload?.debugPayload || {
    ...(failure || {}),
    reject_request: payload?.rejectBody || null,
  };
  return { render: true };
}

function _handleRejectSuccess(panel, payload) {
  const rejected = payload?.rejected || {};
  panel.state.phase = PANEL_STATE.IDLE;
  _handleSyncBaseline(panel, rejected);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.message = payload?.message || "Candidate rejected and cleared from the panel.";
  panel.state.failure = null;
  panel.state.auditRef = rejected.audit_ref || panel.state.auditRef;
  panel.state.queueAllowed = false;
  panel.state.canvasApplyAllowed = false;
  panel.state.applyAllowed = false;
  panel.state.debugPayload = payload?.debugPayload || {
    rejected,
    graph_unchanged: true,
  };
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    toast: payload?.toast || null,
  });
}

function _handleRebaselineStarted(panel, payload) {
  panel.state.rebaselinePending = payload?.rebaselinePending || null;
  return { render: true };
}

function _handleRebaselineSuccess(panel, payload) {
  const result = payload?.result || {};
  _handleSyncBaseline(panel, {
    ...result,
    rebaselineRecovery: null,
  });
  panel.state.auditRef = result.audit_ref || panel.state.auditRef;
  panel.state.rebaselinePending = null;
  panel.state.deltaOps = null;
  panel.state.debugPayload = payload?.debugPayload || {
    rebaseline_request: payload?.rebaselineRequest || null,
    rebaseline_response: result,
  };
  return _obligations({
    render: false,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
  });
}

function _handleRebaselineFailure(panel, payload) {
  const failure = payload?.failure || null;
  _handleSyncBaseline(panel, {
    ...(failure || {}),
    rebaselineRecovery:
      Object.prototype.hasOwnProperty.call(payload || {}, "rebaselineRecovery")
        ? payload.rebaselineRecovery
        : panel.state.rebaselineRecovery,
  });
  panel.state.rebaselinePending = {
    ...(panel.state.rebaselinePending || {}),
    ...(payload?.rebaselinePendingPatch || {}),
  };
  panel.state.auditRef = (failure && failure.audit_ref) || panel.state.auditRef;
  panel.state.debugPayload = payload?.debugPayload || {
    ...(failure || {}),
    rebaseline_request: payload?.rebaselineRequest || null,
  };
  return { render: false };
}

function _handleRebaselineRecoverySync(panel, payload) {
  _syncRebaselineRecovery(panel, payload);
  return { render: false };
}

function _handleStaleRecoveryRebaselineQueued(panel) {
  panel.state.phase = PANEL_STATE.IDLE;
  panel.state.message = "Current canvas queued for stale-state recovery rebaseline.";
  return { render: true };
}

function _handleStaleRecoveryRebaselineSuccess(panel, payload) {
  panel.state.phase = PANEL_STATE.IDLE;
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.failure = null;
  panel.state.rebaselineRecovery = null;
  panel.state.message = payload?.message || "Current canvas rebaselined. Resubmitting from this canvas...";
  panel.state.auditRef = payload?.auditRef || panel.state.auditRef;
  panel.state.debugPayload = payload?.debugPayload || null;
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    toast: payload?.toast || null,
  });
}

function _handleStaleRecoveryRebaselineFailure(panel, payload) {
  panel.state.rebaselineRecovery =
    Object.prototype.hasOwnProperty.call(payload || {}, "rebaselineRecovery")
      ? payload.rebaselineRecovery
      : panel.state.rebaselineRecovery;
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.message = payload?.message || "Current canvas rebaseline failed. Review the evidence and retry.";
  panel.state.debugPayload = payload?.debugPayload || panel.state.debugPayload || null;
  return { render: true };
}

function _handleUndoLocalRestore(panel, payload) {
  const previous = payload?.previous || null;
  panel.state.lastAppliedChanges = null;
  panel.state.phase = PANEL_STATE.IDLE;
  panel.state.failure = null;
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.message = payload?.message || "Previous graph restored locally. Rebaselining undo state...";
  panel.state.debugPayload = payload?.debugPayload || {
    undone_turn_id: previous?.turn_id || null,
    restored_graph_hash: previous?.client_graph_hash || null,
    undo_stack_depth: Number.isFinite(payload?.undoStackDepth) ? payload.undoStackDepth : null,
  };
  return _obligations({
    render: true,
    dirtySections: STATUS_DIRTY_SECTIONS,
    invalidateCandidate: true,
    clearChangedNodeFeedbackVisuals: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
  });
}

function _handleUndoRebaselineSuccess(panel, payload) {
  const previous = payload?.previous || null;
  const result = payload?.result || {};
  panel.state.phase = PANEL_STATE.IDLE;
  panel.state.failure = null;
  _handleSyncBaseline(panel, result);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.auditRef = result.audit_ref || panel.state.auditRef;
  panel.state.message = payload?.message || "Previous graph restored and rebaselined locally.";
  panel.state.debugPayload = payload?.debugPayload || {
    rebaseline_response: result,
    undone_turn_id: previous?.turn_id || null,
    restored_graph_hash: previous?.client_graph_hash || null,
    undo_stack_depth: Number.isFinite(payload?.undoStackDepth) ? payload.undoStackDepth : null,
  };
  if (Array.isArray(panel.state.undoStack) && panel.state.undoStack.length > 0) {
    panel.state.undoStack = panel.state.undoStack.slice(0, -1);
  }
  return _obligations({
    render: true,
    dirtySections: STATUS_DIRTY_SECTIONS,
    invalidateCandidate: true,
    refreshQueueGuard: true,
    toast: payload?.toast || null,
  });
}

function _handleUndoRebaselineFailure(panel, payload) {
  const previous = payload?.previous || null;
  const failure = payload?.failure || null;
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.failure = failure;
  panel.state.auditRef = failure?.audit_ref || panel.state.auditRef;
  _syncRebaselineRecovery(panel, {
    rebaselineRecovery:
      Object.prototype.hasOwnProperty.call(payload || {}, "rebaselineRecovery")
        ? payload.rebaselineRecovery
        : panel.state.rebaselineRecovery,
  });
  panel.state.message =
    payload?.message
    || "Previous graph restored locally, but the undo rebaseline failed. Retry Undo Rebaseline.";
  panel.state.debugPayload = payload?.debugPayload || {
    ...(panel.state.debugPayload || {}),
    undone_turn_id: previous?.turn_id || null,
    restored_graph_hash: previous?.client_graph_hash || null,
    undo_stack_depth: Number.isFinite(payload?.undoStackDepth) ? payload.undoStackDepth : null,
  };
  return { render: true };
}

function _syncRebaselineRecovery(panel, payload) {
  if (!payload || typeof payload !== "object") {
    return;
  }
  if (Object.prototype.hasOwnProperty.call(payload, "rebaselineRecovery")) {
    panel.state.rebaselineRecovery = payload.rebaselineRecovery || null;
  } else if (payload.clearRebaselineRecovery) {
    panel.state.rebaselineRecovery = null;
  } else {
    const recovery = _extractRebaselineRecovery(payload);
    if (recovery) {
      panel.state.rebaselineRecovery = recovery;
    }
  }
}

function _normalizeRebaselineRecovery(recovery) {
  if (!recovery || typeof recovery !== "object") {
    return null;
  }
  return {
    action: typeof recovery.action === "string" ? recovery.action : null,
    endpoint: typeof recovery.endpoint === "string" ? recovery.endpoint : null,
    reason: typeof recovery.reason === "string" ? recovery.reason : null,
    last_known_baseline_graph_hash:
      typeof recovery.last_known_baseline_graph_hash === "string"
        ? recovery.last_known_baseline_graph_hash
        : null,
    submit_graph_hash:
      typeof recovery.submit_graph_hash === "string" ? recovery.submit_graph_hash : null,
    submit_structural_graph_hash:
      typeof recovery.submit_structural_graph_hash === "string"
        ? recovery.submit_structural_graph_hash
        : null,
    client_graph_hash:
      typeof recovery.client_graph_hash === "string" ? recovery.client_graph_hash : null,
    client_structural_graph_hash:
      typeof recovery.client_structural_graph_hash === "string"
        ? recovery.client_structural_graph_hash
        : null,
  };
}

function _extractRebaselineRecovery(payload) {
  const topLevel = _normalizeRebaselineRecovery(payload?.rebaseline_recovery);
  if (topLevel) {
    return topLevel;
  }
  const issueSources = [
    payload?.agent_failure_context?.issues,
    payload?.outcome?.agent_failure_context?.issues,
    payload?.debug?.failure?.agent_failure_context?.issues,
  ];
  for (const issues of issueSources) {
    if (!Array.isArray(issues)) {
      continue;
    }
    for (const issue of issues) {
      const recovery = _normalizeRebaselineRecovery(issue?.rebaseline_recovery);
      if (recovery) {
        return recovery;
      }
    }
  }
  return null;
}

function _stringOrCurrent(value, current) {
  return typeof value === "string" && value ? value : current;
}

function _isStaleChatRehydrate(panel, requestEpoch) {
  return Number.isFinite(requestEpoch) && panel.state.chatRehydrateEpoch !== requestEpoch;
}

// ── Chat-message reconciliation (T9) ─────────────────────────────────────
// When durable chatMessages arrive from the backend during an active submit,
// we reconcile instead of wholesale-replacing: canonical messages are
// authoritative and come first; in-flight optimistic entries from the
// current submit epoch that have no canonical counterpart are preserved
// after the durable messages so the user sees their pending request.
// Outside of SUBMITTING, canonical replaces wholesale (current behaviour).

/**
 * Derive a stable key for a normalized TurnIdentity at the chat reconciliation
 * boundary. Internal lifecycle state should keep the structured identity.
 */
function _deriveTurnIdentityReconciliationKey(identity) {
  if (!identity || typeof identity !== "object") {
    return null;
  }
  const turnId = typeof identity.turnId === "string" && identity.turnId ? identity.turnId : null;
  const role = typeof identity.role === "string" && identity.role ? identity.role : null;
  return turnId && role ? `turn:${turnId}:${role}` : null;
}

/**
 * Derive a stable key for local optimistic entries at the chat reconciliation
 * boundary. Durable messages should use TurnIdentity-derived keys.
 */
function _deriveLocalChatMessageReconciliationKey(msg) {
  if (!msg || typeof msg !== "object") {
    return null;
  }
  const localId = typeof msg.local_id === "string" && msg.local_id ? msg.local_id : null;
  return localId ? `local:${localId}` : null;
}

function _readChatMessageTurnIdentity(msg) {
  if (!msg || typeof msg !== "object") {
    return null;
  }
  return _strictSelectorRead(readTurnIdentity, msg.turnIdentity)
    || _strictSelectorRead(readTurnIdentity, msg.turn_identity)
    || _strictSelectorRead(readTurnIdentity, msg);
}

function _chatMessageReconciliationKey(msg) {
  const identity = _readChatMessageTurnIdentity(msg);
  return _deriveTurnIdentityReconciliationKey(identity)
    || _deriveLocalChatMessageReconciliationKey(msg);
}

/**
 * Returns true when a message is an optimistic/in-flight frontend entry
 * (not yet confirmed by a durable backend response).
 */
function _isOptimisticMessage(msg) {
  return Boolean(
    msg && typeof msg === "object"
    && (msg.optimistic === true || msg.pending_response === true || msg.executor_pending === true),
  );
}

/**
 * Reconcile existing chatMessages with canonical (durable) messages from
 * the backend.
 *
 * - When the panel is NOT submitting, canonical is wholesale replacement.
 * - When the panel IS submitting, canonical messages come first; unmatched
 *   in-flight optimistic messages from the current submit epoch are
 *   preserved after the durable set.
 *
 * @param {Array} existing  — current panel.state.chatMessages
 * @param {Array} canonical — durable messages from backend rehydrate
 * @param {object} panelState — panel.state (for phase + submitEpoch)
 * @returns {Array} reconciled message array
 */
export function reconcileChatMessages(existing, canonical, panelState) {
  const safeExisting = Array.isArray(existing) ? existing : [];
  const safeCanonical = Array.isArray(canonical) ? canonical : [];

  // Outside of an active submit, canonical is the sole authority.
  if (!panelState || panelState.phase !== PANEL_STATE.SUBMITTING) {
    return safeCanonical.map((msg) => (msg && typeof msg === "object" ? { ...msg } : msg));
  }

  const currentEpoch = Number.isFinite(panelState.submitEpoch) ? panelState.submitEpoch : null;

  // Build a set of identity keys present in the canonical batch.
  const canonicalKeys = new Set();
  for (const msg of safeCanonical) {
    const key = _chatMessageReconciliationKey(msg);
    if (key) {
      canonicalKeys.add(key);
    }
  }

  // Start with durable messages (authoritative, ordered first).
  const result = safeCanonical.map((msg) => (msg && typeof msg === "object" ? { ...msg } : msg));

  // Append in-flight optimistic messages from the current epoch that have
  // no canonical counterpart. Stale optimistic entries (from a previous
  // epoch or cancelled submit) are dropped.
  for (const msg of safeExisting) {
    if (!_isOptimisticMessage(msg)) {
      continue;
    }
    // Only preserve in-flight entries belonging to the current submit epoch.
    if (currentEpoch !== null && msg.submit_epoch !== currentEpoch) {
      continue;
    }
    const key = _chatMessageReconciliationKey(msg);
    // If this optimistic entry has no durable identity we cannot safely
    // preserve it — skip to avoid ghost duplicates.
    if (!key) {
      continue;
    }
    if (!canonicalKeys.has(key)) {
      result.push(msg && typeof msg === "object" ? { ...msg } : msg);
    }
  }

  return result;
}
