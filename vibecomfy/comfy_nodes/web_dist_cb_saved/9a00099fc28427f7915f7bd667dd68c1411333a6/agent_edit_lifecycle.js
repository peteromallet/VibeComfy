// agent_edit_lifecycle.js — Client lifecycle contract + state authority
//
// This module owns every panel-state mutation for defined transitions.
// It has ZERO imports and performs ZERO HTTP/canvas/DOM side effects.
// All external data arrives via `payload`; all side effects are returned
// as plain obligations objects that `vibecomfy_roundtrip.js` fulfills.
//
// Backend CAS is the single Apply authority. The client sends
// `client_structural_graph_hash` only as a backend-parity diagnostic
// snapshot in submit/rebaseline payloads; it never blocks Apply locally.

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
export function createAgentEditState() {
  return {
    phase: PANEL_STATE.IDLE,

    // Session / turn identity
    sessionId: null,
    turnId: null,

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

    case "NEW_CONVERSATION":
      return _handleNewConversation(panel);

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
// Extracts and normalizes ``delta_ops`` from a V2 submit response.
// Returns a stable plain array of normalized delta-op objects (shallow-cloned,
// keys sorted), or ``null`` when absent/invalid.
//
// The backend places ``delta_ops`` as a top-level JSON array in the V2
// submit response when ``agent_edit_protocol == "v2_delta"``.  Each entry is
// a plain dict with at least ``op`` and ``target`` string keys.
export function normalizeDeltaOpsFromSubmit(result) {
  if (!result || typeof result !== "object") {
    return null;
  }

  const raw = result.delta_ops;
  if (!Array.isArray(raw)) {
    return null;
  }

  if (raw.length === 0) {
    return [];
  }

  const normalized = [];
  for (let i = 0; i < raw.length; i++) {
    const entry = raw[i];
    if (!entry || typeof entry !== "object" || typeof entry.op !== "string" || !entry.op) {
      continue;
    }
    // Shallow-clone with sorted keys for deterministic shape.
    const keys = Object.keys(entry).sort();
    const clone = {};
    for (const k of keys) {
      clone[k] = entry[k];
    }
    normalized.push(clone);
  }

  return normalized.length > 0 ? normalized : null;
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

  // Clear V2 delta ops — mutation intent is invalidated with the candidate.
  panel.state.deltaOps = null;

  // Clear preview diff caches (these are transient keys that live on state
  // but are not lifecycle-owned; we clean them up here as the candidate
  // invalidation logically invalidates any preview derived from it).
  delete panel.state._previewDiff;
  delete panel.state._previewDiffGraphHash;

  return { render: repaint };
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
  panel.state.debugPayload = payload?.debugPayload || null;
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
  return { render: true };
}

function _handleSubmitAbort(panel, payload) {
  panel.state.phase = PANEL_STATE.IDLE;
  panel.state.failure = null;
  panel.state.deltaOps = null;
  panel.state.message = payload?.message || "Request cancelled.";
  panel.state.syntheticAgentMessage = payload?.syntheticAgentMessage || {
    role: "agent",
    text: panel.state.message,
    session_id: panel.state.sessionId || null,
    synthetic: true,
    local_id: `cancelled:${Date.now()}`,
  };
  panel.state.debugPayload = payload?.debugPayload || {
    cancelled: true,
    last_submit: panel.state.lastSubmit,
  };
  return { render: true, refreshQueueGuard: true };
}

function _handleSubmitNetworkFailure(panel, payload) {
  const failure = payload?.failure || null;
  panel.state.phase = PANEL_STATE.ERROR;
  panel.state.failure = failure;
  panel.state.turnId = _stringOrCurrent(failure?.turn_id, panel.state.turnId);
  panel.state.sessionId = _stringOrCurrent(failure?.session_id, panel.state.sessionId);
  _handleSyncBaseline(panel, failure || {});
  panel.state.auditRef = failure?.audit_ref || null;
  panel.state.debugPayload = payload?.debugPayload || {
    ...(failure || {}),
    last_submit: panel.state.lastSubmit,
  };
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
  panel.state.sessionId = _stringOrCurrent(result.session_id, panel.state.sessionId);
  panel.state.turnId = typeof result.turn_id === "string" ? result.turn_id : null;
  _handleSyncBaseline(panel, result);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.clarification = payload?.clarification || null;
  panel.state.message = payload?.message || panel.state.clarification?.message || null;
  panel.state.failure = null;
  panel.state.canvasApplyAllowed = false;
  panel.state.applyAllowed = false;
  panel.state.applyEligibility = null;
  panel.state.queueAllowed = false;
  panel.state.auditRef = result.audit_ref || null;
  panel.state.lastSubmitFieldChanges = payload?.lastSubmitFieldChanges || null;
  panel.state.debugPayload = payload?.debugPayload || {
    ...result,
    last_submit: panel.state.lastSubmit,
  };
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: panel.state.sessionId || null,
    refreshQueueGuard: true,
    rehydrateChat: true,
    invalidateCandidate: true,
  });
}

function _handleNoopResponse(panel, payload) {
  const result = payload?.result || {};
  panel.state.phase = PANEL_STATE.IDLE;
  panel.state.sessionId = _stringOrCurrent(result.session_id, panel.state.sessionId);
  panel.state.turnId = typeof result.turn_id === "string" ? result.turn_id : null;
  _handleSyncBaseline(panel, result);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.clarification = null;
  panel.state.message = payload?.message || result.message || null;
  panel.state.failure = null;
  panel.state.canvasApplyAllowed = false;
  panel.state.applyAllowed = false;
  panel.state.applyEligibility = null;
  panel.state.queueAllowed = false;
  panel.state.auditRef = result.audit_ref || null;
  panel.state.lastSubmitFieldChanges = payload?.lastSubmitFieldChanges || null;
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
    rehydrateChat: true,
    invalidateCandidate: true,
  });
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

function _candidateActionAllowed(payload, result) {
  const candidateGraph = payload?.candidateGraph;
  const hasCandidate = Boolean(candidateGraph && typeof candidateGraph === "object");
  const eligibility = payload?.applyEligibility;
  if (eligibility && typeof eligibility === "object") {
    return hasCandidate && eligibility.applyable === true;
  }
  return hasCandidate
    && result.apply_eligible === true
    && result.apply_allowed !== false
    && result.canvas_apply_allowed !== false;
}

function _handleCandidateResponse(panel, payload) {
  const result = payload?.result || {};
  const candidateActionAllowed = _candidateActionAllowed(payload, result);
  panel.state.phase = PANEL_STATE.AWAITING_REVIEW;
  panel.state.sessionId = _stringOrCurrent(result.session_id, panel.state.sessionId);
  panel.state.turnId = typeof result.turn_id === "string" ? result.turn_id : null;
  _handleSyncBaseline(panel, result);
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.candidateGraph = payload?.candidateGraph || null;
  panel.state.candidateGraphHash = typeof payload?.candidateGraphHash === "string" ? payload.candidateGraphHash : null;
  panel.state.candidateReport = result.report || null;
  panel.state.serverSubmitGraphHash = typeof result.submit_graph_hash === "string" ? result.submit_graph_hash : null;
  panel.state.message = result.message || null;
  panel.state.failure = null;
  panel.state.clarification = payload?.clarification || null;
  panel.state.applyEligibility = payload?.applyEligibility || null;
  panel.state.applyAllowed = candidateActionAllowed;
  panel.state.canvasApplyAllowed = candidateActionAllowed;
  panel.state.queueAllowed = Boolean(result.queue_allowed);
  panel.state.auditRef = result.audit_ref || null;
  panel.state.lastSubmitFieldChanges = payload?.lastSubmitFieldChanges || null;
  panel.state.changeDetails = payload?.changeDetails || null;
  panel.state.deltaOps = normalizeDeltaOpsFromSubmit(result);
  panel.state.debugPayload = payload?.debugPayload || {
    ...result,
    last_submit: panel.state.lastSubmit,
  };
  return _obligations({
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: panel.state.sessionId || null,
    setQueueGuardContext: {
      sessionId: panel.state.sessionId,
      turnId: panel.state.turnId,
      queueAllowed: panel.state.queueAllowed,
    },
    refreshQueueGuard: true,
    rehydrateChat: true,
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
  panel.state.syntheticAgentMessage = payload?.syntheticAgentMessage || {
    role: "agent",
    text: panel.state.message,
    session_id: panel.state.sessionId || null,
    synthetic: true,
    local_id: `cancelled:${Date.now()}`,
  };
  panel.state.debugPayload = payload?.debugPayload || {
    cancelled: true,
    last_submit: panel.state.lastSubmit,
  };
  return { render: true, refreshQueueGuard: true };
}

function _handleNewConversation(panel) {
  const nextSubmitEpoch = (Number.isFinite(panel.state.submitEpoch) ? panel.state.submitEpoch : 0) + 1;
  const nextChatRehydrateEpoch =
    (Number.isFinite(panel.state.chatRehydrateEpoch) ? panel.state.chatRehydrateEpoch : 0) + 1;
  _handleInvalidateCandidate(panel, { repaint: false });
  Object.assign(panel.state, createAgentEditState(), {
    submitEpoch: nextSubmitEpoch,
    chatRehydrateEpoch: nextChatRehydrateEpoch,
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
    queueGuardClear: true,
    refreshQueueGuard: true,
    forgetSession: true,
    focusPrompt: true,
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
  panel.state.chatMessages = Array.isArray(payload?.messages) ? payload.messages : [];
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

function _handleChatRehydrateRestoreLatestCandidate(panel, payload) {
  if (
    panel.state.phase === PANEL_STATE.SUBMITTING
    || panel.state.phase === PANEL_STATE.APPLYING
  ) {
    return { render: false, skipped: true };
  }

  const candidateGraph = payload?.candidateGraph;
  if (!candidateGraph || typeof candidateGraph !== "object") {
    return { render: false, skipped: true };
  }

  panel.state.phase = PANEL_STATE.AWAITING_REVIEW;
  panel.state.sessionId = _stringOrCurrent(payload?.sessionId, panel.state.sessionId);
  panel.state.turnId = typeof payload?.turnId === "string" ? payload.turnId : panel.state.turnId;
  _handleSyncBaseline(panel, payload?.baseline || {});
  _handleInvalidateCandidate(panel, { repaint: false });
  panel.state.candidateGraph = candidateGraph;
  panel.state.candidateGraphHash =
    typeof payload?.candidateGraphHash === "string" ? payload.candidateGraphHash : null;
  panel.state.candidateReport = payload?.candidateReport || null;
  panel.state.serverSubmitGraphHash =
    typeof payload?.serverSubmitGraphHash === "string" ? payload.serverSubmitGraphHash : null;
  panel.state.message = payload?.message || null;
  panel.state.failure = null;
  panel.state.clarification = null;
  panel.state.applyEligibility = payload?.applyEligibility || null;
  panel.state.applyAllowed = _candidateActionAllowed(payload, {
    apply_eligible: payload?.applyAllowed === true,
    apply_allowed: payload?.applyAllowed,
    canvas_apply_allowed: payload?.canvasApplyAllowed,
  });
  panel.state.canvasApplyAllowed = panel.state.applyAllowed;
  panel.state.queueAllowed = Boolean(payload?.queueAllowed);
  panel.state.auditRef = payload?.auditRef || panel.state.auditRef || null;
  panel.state.lastSubmitFieldChanges = payload?.lastSubmitFieldChanges || null;
  panel.state.changeDetails = payload?.changeDetails || null;
  panel.state.deltaOps = normalizeDeltaOpsFromSubmit(payload?.baseline?.raw || payload?.baseline || {});
  panel.state.debugPayload = payload?.debugPayload || null;
  return _obligations({
    render: false,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
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
  panel.state.chatMessages = [];
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
  panel.state.syntheticAgentMessage = payload?.syntheticAgentMessage || null;
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
  panel.state.syntheticAgentMessage = payload?.syntheticAgentMessage || null;
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
  panel.state.syntheticAgentMessage = payload?.syntheticAgentMessage || null;
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
  panel.state.message = payload?.message || "Candidate accepted and applied locally.";
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
