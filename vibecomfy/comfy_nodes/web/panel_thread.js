import { getAgentPanelRuntime } from "./panel_runtime.js";
import { renderMarkdown } from "./markdown.js";
import {
  formatActivityHeadline,
  formatOutcomeCounts,
  formatStatementAction,
  isSubstantiveStatement,
} from "./agent_turn_feed.js";
import {
  readApplyCandidate,
  readFieldChanges,
  readStageSnapshot,
  routeAllowsApplyAffordances,
  projectResponseDetail,
  selectResponseDetails,
  selectTranscriptMessages,
} from "./agent_edit_response_contract.js";
import { routeStatusState } from "./agent_status_poller.js";

const THREAD_WINDOW_SIZE = 30;
const THREAD_NEAR_BOTTOM_TOLERANCE_PX = 120;
const RATING_WIDGET_CLEAR_DELAY_MS = 2400;
const RATING_WIDGET_EXPIRY_MS = 120000;
const RATING_PACK_SHARE_DEFAULT_LS_KEY = "vibecomfy_pack_share_default";
const RATING_WIDGET_DISABLED_LS_KEY = "vibecomfy_rating_widget_disabled";

export function collectThreadMessageEntries(panel, deps = {}) {
  const { messageStableKey } = deps;
  const threadMessages = selectTranscriptMessages(panel);
  // selectTranscriptMessages already projects the local synthetic transaction
  // message alongside the durable backend transcript.  Do not append it a
  // second time here: a prepare rejection must have exactly one actionable
  // bubble, including across rehydrate and scheduled renders.
  return threadMessages.map((msg, index) => ({
    msg,
    index,
    key: typeof messageStableKey === "function" ? messageStableKey(msg, index) : String(index),
  }));
}

export function computeThreadDisplayEntries(panel, threadEntries, deps = {}) {
  const { ensureThreadRenderState } = deps;
  const threadState = typeof ensureThreadRenderState === "function"
    ? ensureThreadRenderState(panel)
    : panel?.threadState;
  if (threadState?.expandedOlder || threadEntries.length <= THREAD_WINDOW_SIZE) {
    return {
      displayEntries: threadEntries,
      hiddenCount: 0,
    };
  }
  return {
    displayEntries: threadEntries.slice(-THREAD_WINDOW_SIZE),
    hiddenCount: Math.max(0, threadEntries.length - THREAD_WINDOW_SIZE),
  };
}

export function renderThreadSection(panel, deps = {}) {
  const {
    ensureThreadRenderState,
    recordAgentPanelRenderCount,
    RENDER_SECTIONS,
  } = deps;
  if (typeof recordAgentPanelRenderCount === "function") {
    recordAgentPanelRenderCount(panel, RENDER_SECTIONS?.THREAD || "thread");
  }
  const threadState = typeof ensureThreadRenderState === "function"
    ? ensureThreadRenderState(panel)
    : panel?.threadState;

  // Capture the auto-scroll decision before any DOM mutation so it faithfully
  // reflects the user's scroll position at the moment rendering started.
  const shouldAutoScroll =
    Boolean(threadState?.forceScrollOnNextRender)
    || isChatThreadNearBottom(panel);

  // renderHistory mutates the chat DOM (bubble reconciliation); it captures
  // its own scroll decision internally for that path and returns whether
  // messages were rendered.
  renderHistory(panel, deps);
  renderActivityRows(panel, deps);

  if (shouldAutoScroll) {
    scrollChatThreadToBottom(panel);
  }
}

export function recordThreadRender(runtimePayload) {
  const runtime = getAgentPanelRuntime();
  runtime._lastThreadRender = runtimePayload;
  return runtime._lastThreadRender;
}

function _readSelectorOrNull(selector, value, options = {}) {
  try {
    return selector(value, options);
  } catch (_error) {
    return null;
  }
}

function isPendingAgentMessage(message) {
  return Boolean(message?.pending_response === true || message?.executor_pending === true);
}

function stageSnapshotForRender(message, detailSnapshot = null) {
  const candidates = [
    detailSnapshot?.stageSnapshot,
    detailSnapshot?.debugPayload?.stageSnapshot,
    message?.stageSnapshot,
    message?.stage_snapshot,
    message?.response,
    message,
  ];
  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== "object") {
      continue;
    }
    const snapshot = _readSelectorOrNull(readStageSnapshot, candidate, { allowLegacy: false });
    if (snapshot) {
      return snapshot;
    }
  }
  return null;
}

function applyCandidateSourceFromPanel(panel) {
  const graph = panel?.state?.candidateGraph;
  if (!graph || typeof graph !== "object") {
    return null;
  }
  return {
    outcome: { kind: "candidate" },
    candidate: {
      state: "candidate",
      graph,
      graphHash: panel.state.candidateGraphHash,
      structuralGraphHash: panel.state.structuralGraphHash,
      baselineGraphHash: panel.state.baselineGraphHash,
      submitGraphHash: panel.state.submitGraphHash,
      submitStructuralGraphHash: panel.state.submitStructuralGraphHash,
    },
    eligibility: panel.state.applyEligibility,
    turnIdentity: {
      sessionId: panel.state.sessionId,
      turnId: panel.state.turnId,
    },
  };
}

function applyCandidateForRender(panel, message = null, detailSnapshot = null) {
  const sources = [
    message?.response,
    message,
    detailSnapshot?.response,
    detailSnapshot?.debugPayload?.response,
    applyCandidateSourceFromPanel(panel),
  ];
  for (const source of sources) {
    if (!source || typeof source !== "object") {
      continue;
    }
    const candidate = _readSelectorOrNull(readApplyCandidate, source, { allowLegacy: false });
    if (candidate) {
      return candidate;
    }
  }
  return null;
}

function fieldChangesForRender(message, detailSnapshot = null) {
  if (Array.isArray(detailSnapshot?.changes)) {
    return detailSnapshot.changes;
  }
  const snapshotChanges = detailSnapshot?.fieldChanges;
  if (snapshotChanges && (typeof snapshotChanges === "object" || Array.isArray(snapshotChanges))) {
    return snapshotChanges;
  }
  const sources = [
    message?.response,
    message,
    detailSnapshot?.response,
    detailSnapshot?.debugPayload?.response,
  ];
  for (const source of sources) {
    if (!source || typeof source !== "object") {
      continue;
    }
    const changes = _readSelectorOrNull(readFieldChanges, source, { allowLegacy: false });
    if (changes?.all?.length) {
      return changes;
    }
  }
  return null;
}

function allFieldChangesForRender(message, detailSnapshot = null) {
  const fieldChanges = fieldChangesForRender(message, detailSnapshot);
  if (Array.isArray(fieldChanges)) {
    return fieldChanges;
  }
  if (!fieldChanges || typeof fieldChanges !== "object") {
    return [];
  }
  if (Array.isArray(fieldChanges.all)) {
    return fieldChanges.all;
  }
  const directChanges = Array.isArray(fieldChanges.directChanges) ? fieldChanges.directChanges : [];
  const outcomeChanges = Array.isArray(fieldChanges.outcomeChanges) ? fieldChanges.outcomeChanges : [];
  const batchTurnChanges = Array.isArray(fieldChanges.batchTurnChanges)
    ? fieldChanges.batchTurnChanges.flatMap((turn) => {
      if (Array.isArray(turn?.changes)) {
        return turn.changes;
      }
      return turn && typeof turn === "object" ? [turn] : [];
    })
    : [];
  return directChanges.concat(outcomeChanges, batchTurnChanges);
}

function responseDetailForMessage(panel, message = null, snapshot = null) {
  const turnId =
    (typeof message?.turn_id === "string" && message.turn_id)
    || (typeof message?.detail_turn_id === "string" && message.detail_turn_id)
    || (typeof snapshot?.turn?.turnId === "string" && snapshot.turn.turnId)
    || (typeof snapshot?.turn_id === "string" && snapshot.turn_id)
    || null;
  if (!turnId) {
    return null;
  }
  const details = selectResponseDetails(panel);
  const detailKey = panel?.state?.compartmentIndexes?.responseDetailsByTurnId?.[turnId] || turnId;
  return details?.[detailKey]
    || details?.[turnId]
    || projectResponseDetail(message?.response || message)
    || null;
}

export function normalDetailSnapshotForRender(detail) {
  if (!detail || typeof detail !== "object") {
    return null;
  }
  const outcomeSummary =
    (typeof detail.outcome?.summary === "string" && detail.outcome.summary)
    || (typeof detail.outcome?.question === "string" && detail.outcome.question)
    || null;
  return {
    turn_id: detail.turn?.turnId || null,
    phase: detail.turn?.status || detail.outcome?.kind || null,
    message: outcomeSummary,
    candidateGraphPresent: Boolean(detail.candidateGraphPresent ?? detail.candidate?.graphHash),
    candidateReport: detail.candidate?.report || null,
    applyEligibility: detail.eligibility || null,
    changes: Array.isArray(detail.changes) ? detail.changes : [],
    changeDetails: changeDetailsFromResponseDetail(detail),
    progress: detail.progress || null,
    lastAppliedChanges: detail.lastAppliedChanges || null,
    queueDisplay: detail.queueDisplay || null,
    failure: detail.outcome?.kind === "error"
      ? {
          kind: "Error",
          message: outcomeSummary || "The agent could not complete the turn.",
        }
      : null,
    clarification: detail.outcome?.kind === "clarify" && outcomeSummary
      ? { message: outcomeSummary }
      : null,
  };
}

function changeDetailsFromResponseDetail(detail) {
  if (!detail || typeof detail !== "object") {
    return null;
  }
  const changes = Array.isArray(detail.changes) ? detail.changes : [];
  if (!changes.length) {
    return null;
  }
  const summary =
    (typeof detail.outcome?.summary === "string" && detail.outcome.summary)
    || (typeof detail.outcome?.question === "string" && detail.outcome.question)
    || null;
  return {
    landed_operation_count: changes.length,
    operations: changes.map((change) => ({
      uid: change.uid,
      field_path: change.fieldPath || change.field_path,
      old: Object.prototype.hasOwnProperty.call(change, "old") ? change.old : undefined,
      new: Object.prototype.hasOwnProperty.call(change, "new") ? change.new : undefined,
      summary: change.fieldPath || change.field_path
        ? `${change.fieldPath || change.field_path} changed`
        : "field changed",
    })),
    done_summary: summary,
  };
}

function routeStatusForRender(panel) {
  return routeStatusState(panel);
}

function routeAllowsCandidateDetail(panel, message, detailSnapshot, actionState) {
  if (applyCandidateForRender(panel, message, detailSnapshot)) {
    return true;
  }
  const routeStatus = routeStatusForRender(panel);
  const route = routeStatus?.selectedRoute || routeStatus?.requestedRoute || null;
  return routeAllowsApplyAffordances(route) || actionState?.visible === true;
}

export function changeDetailsForMessage(panel, message, snapshot = null, deps = {}) {
  const responseDetail = responseDetailForMessage(panel, message, snapshot);
  const safeChangeDetails = changeDetailsFromResponseDetail(responseDetail);
  if (safeChangeDetails) {
    return safeChangeDetails;
  }
  if (snapshot?.changeDetails && typeof snapshot.changeDetails === "object" && snapshot?.debugPayload == null) {
    return snapshot.changeDetails;
  }
  return panel?.state?.changeDetails || null;
}

export function createBubbleDetailSection(title, deps = {}) {
  const { el } = deps;
  const section = el("div");
  Object.assign(section.style, {
    display: "grid",
    gap: "4px",
    minWidth: "0",
    maxWidth: "100%",
  });
  const heading = el("div", title);
  Object.assign(heading.style, {
    fontSize: "10px",
    fontWeight: "700",
    color: "#6b7080",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  });
  const body = el("div");
  Object.assign(body.style, {
    display: "grid",
    gap: "4px",
    minWidth: "0",
  });
  section.appendChild(heading);
  section.appendChild(body);
  return { section, body };
}

export function appendCandidateDetail(body, panel, message = null, snapshot = null, deps = {}) {
  const {
    PANEL_STATE,
    appendCodeLine,
    appendTextLine,
    applyAgentCandidate,
    button,
    candidateActionState,
    collectDiffRows,
    collectQueueIssues,
    createDetails,
    el,
    getBackendStageInfo,
    muted,
    rejectAgentCandidate,
    setButtonEmphasis,
  } = deps;
  const normalDetailMode = Boolean(snapshot);
  const actionState = candidateActionState(panel, message, snapshot);
  const candidateGraphPresent = actionState.visible
    || (!message && !snapshot && Boolean(panel.state.candidateGraph));
  const phase = snapshot?.phase || panel.state.phase;
  const clarification = snapshot?.clarification || panel.state.clarification;
  if (!candidateGraphPresent) {
    if (phase === PANEL_STATE.CLARIFY && clarification?.message) {
      const q = el("div", "\u2753 The agent needs your input:");
      q.style.color = "#ffc107";
      q.style.fontWeight = "600";
      body.appendChild(q);
      const msg = el("div", clarification.message);
      msg.style.whiteSpace = "pre-wrap";
      msg.style.color = "#edf2f7";
      msg.style.borderLeft = "2px solid #ffc107";
      msg.style.paddingLeft = "8px";
      msg.style.margin = "4px 0";
      body.appendChild(msg);
      body.appendChild(muted("Answer in the prompt box above and submit - it continues this session."));
      return;
    }
    const feedback = snapshot?.lastAppliedChanges || panel.state.lastAppliedChanges;
    if (feedback?.items?.length) {
      appendTextLine(
        body,
        feedback.mode === "visual"
          ? "Applied candidate feedback: changed nodes were highlighted on the canvas temporarily."
          : "Applied candidate feedback: changed nodes listed here because live node lookup was unavailable.",
        feedback.mode === "visual" ? "#9ed0ff" : "#ffb86c",
      );
      for (const item of feedback.items) {
        const rowNode = el("div", item.label);
        rowNode.style.color = item.color;
        rowNode.style.borderLeft = `2px solid ${item.color}`;
        rowNode.style.paddingLeft = "8px";
        body.appendChild(rowNode);
      }
      if (feedback.unresolved?.length && feedback.mode === "visual") {
        body.appendChild(createDetails("panel fallback for unresolved nodes", feedback.unresolved));
      }
      return;
    }
    return;
  }
  const debugPayload = normalDetailMode ? null : (snapshot?.debugPayload || panel.state.debugPayload);
  const stageInfo = debugPayload ? getBackendStageInfo(debugPayload) : null;
  if (!normalDetailMode && stageInfo) {
    appendTextLine(
      body,
      `backend stage: ${stageInfo.stage || "unknown"}${stageInfo.progress != null ? ` (${stageInfo.progress})` : ""}`,
      "#9ed0ff",
    );
  }
  const candidateMessage = snapshot?.message || message?.text || panel.state.message;
  if (candidateMessage) {
    const msg = el("div", candidateMessage);
    msg.style.whiteSpace = "pre-wrap";
    msg.style.color = "#edf2f7";
    body.appendChild(msg);
  }
  const eligibility = actionState.eligibility;
  if (!normalDetailMode) {
    const canvasApplyAllowed = snapshot?.canvasApplyAllowed ?? panel.state.canvasApplyAllowed;
    const queueAllowed = snapshot?.queueAllowed ?? panel.state.queueAllowed;
    appendTextLine(body, `canvas_apply_allowed=${String(canvasApplyAllowed)}`, canvasApplyAllowed ? "#4caf50" : "#ffb86c");
    appendTextLine(body, `queue_allowed=${String(queueAllowed)}`, queueAllowed ? "#4caf50" : "#ffb86c");
  }
  appendTextLine(body, `apply_eligibility=${eligibility.reason}`, eligibility.applyable ? "#4caf50" : "#ffb86c");
  if (eligibility.message) {
    appendTextLine(body, eligibility.message, "#9ed0ff");
  }
  if (actionState.visible) {
    const controlsRow = el("div");
    controlsRow.dataset.vibecomfyCandidateControls = "1";
    Object.assign(controlsRow.style, {
      display: "flex",
      flexWrap: "wrap",
      gap: "6px",
      alignItems: "center",
      marginTop: "2px",
    });

    const applyBtn = button("Apply", () => applyAgentCandidate(panel));
    applyBtn.dataset.vibecomfyCandidateAction = "apply";
    applyBtn.dataset.vibecomfyCandidateTurnId = actionState.turnId || "";
    applyBtn.disabled = actionState.applyDisabled;
    applyBtn.style.fontSize = "11px";
    applyBtn.style.padding = "4px 8px";
    setButtonEmphasis(applyBtn, actionState.active || panel.state.phase === PANEL_STATE.APPLYING, "primary");
    controlsRow.appendChild(applyBtn);

    const rejectBtn = button("Reject", () => rejectAgentCandidate(panel));
    rejectBtn.dataset.vibecomfyCandidateAction = "reject";
    rejectBtn.dataset.vibecomfyCandidateTurnId = actionState.turnId || "";
    rejectBtn.disabled = actionState.rejectDisabled;
    rejectBtn.style.fontSize = "11px";
    rejectBtn.style.padding = "4px 8px";
    setButtonEmphasis(rejectBtn, actionState.active || panel.state.phase === PANEL_STATE.APPLYING, "danger");
    controlsRow.appendChild(rejectBtn);

    const stateLabel = el(
      "span",
      actionState.active
        ? (eligibility.applyable ? "latest" : eligibility.reason)
        : eligibility.reason,
    );
    stateLabel.dataset.vibecomfyCandidateReason = eligibility.reason || "";
    stateLabel.dataset.vibecomfyCandidateTurnId = actionState.turnId || "";
    Object.assign(stateLabel.style, {
      fontSize: "10px",
      color: eligibility.applyable ? "#4caf50" : "#ffb86c",
      textTransform: "uppercase",
      letterSpacing: "0.04em",
      fontWeight: "700",
    });
    controlsRow.appendChild(stateLabel);

    body.appendChild(controlsRow);
    if (actionState.blockerMessage && actionState.blockerMessage !== eligibility.message) {
      appendTextLine(body, actionState.blockerMessage, "#9ed0ff");
    }
  }
  const report = snapshot?.candidateReport || (!normalDetailMode ? (message?.report || panel.state.candidateReport) : null);
  const queueIssueReport = report;
  const rows = collectDiffRows(report);
  if (!rows.length) {
    body.appendChild(muted("Candidate returned without report rows."));
  }
  for (const item of rows) {
    const rowNode = el("div", item.text);
    rowNode.style.color = item.color;
    rowNode.style.borderLeft = `2px solid ${item.color}`;
    rowNode.style.paddingLeft = "8px";
    if (item.title) {
      rowNode.title = item.title;
    }
    body.appendChild(rowNode);
  }
  const affected = {
    preserved: rows.filter((item) => item.text.startsWith("preserved:")).length,
    edited: rows.filter((item) => item.text.startsWith("edited:") || item.text.startsWith("changed_node:")).length,
    added: rows.filter((item) => item.text.startsWith("new_auto_placed:") || item.text.startsWith("added_node:") || item.text.startsWith("added_link:")).length,
    removed: rows.filter((item) => item.text.startsWith("removed:") || item.text.startsWith("removed_named:") || item.text.startsWith("removed_node:") || item.text.startsWith("removed_link:")).length,
    helpers: rows.filter((item) => item.text.startsWith("stripped_helper:") || item.text.startsWith("virtual_wires_degraded:")).length,
    lowered: rows.filter((item) => item.text.startsWith("lowered:")).length,
  };
  body.appendChild(createDetails("affected node preview", affected));
  const issues = collectQueueIssues(queueIssueReport);
  if (issues.length) {
    for (const issue of issues) {
      appendTextLine(body, `${issue.code}: ${issue.message}`, issue.severity === "error" ? "#ffb86c" : "#9ed0ff");
      if (!normalDetailMode && issue.detail && Object.keys(issue.detail).length) {
        body.appendChild(createDetails("queue blocker detail", issue.detail));
      }
    }
  }
  const artifacts = debugPayload?.artifacts;
  if (!normalDetailMode && artifacts && typeof artifacts === "object") {
    for (const [name, value] of Object.entries(artifacts)) {
      appendCodeLine(body, `${name}: ${value}`);
    }
  }
  const auditRef = !normalDetailMode ? (snapshot?.auditRef || panel.state.auditRef) : null;
  if (auditRef?.path) {
    appendCodeLine(body, `audit: ${auditRef.path}`, "#9ed0ff");
  }
  if (!normalDetailMode) {
    body.appendChild(createDetails("raw report", report || {}));
  }
}

export function appendFailureDetail(body, panel, snapshot = null, deps = {}) {
  const {
    appendCodeLine,
    appendTextLine,
    createDetails,
    getBackendStageInfo,
  } = deps;
  const normalDetailMode = Boolean(snapshot);
  const failure = snapshot?.failure || panel.state.failure;
  if (!failure) {
    return;
  }
  appendTextLine(body, `${failure.kind || "Error"} @ ${failure.stage || "unknown"}`, "#ffd6d6");
  appendTextLine(body, failure.user_facing_message || failure.message || failure.error || "Unknown failure", "#edf2f7");
  if (!normalDetailMode) {
    appendTextLine(body, `retryable=${String(Boolean(failure.retryable))} graph_unchanged=${String(Boolean(failure.graph_unchanged))}`, "#8d93a1");
    appendTextLine(body, `canvas_apply_allowed=${String(Boolean(failure.canvas_apply_allowed))} queue_allowed=${String(Boolean(failure.queue_allowed))}`, "#8d93a1");
  }
  const stageInfo = getBackendStageInfo(failure);
  if (!normalDetailMode && stageInfo) {
    appendTextLine(
      body,
      `backend stage: ${stageInfo.stage || "unknown"}${stageInfo.progress != null ? ` (${stageInfo.progress})` : ""}`,
      "#9ed0ff",
    );
  }
  if (!normalDetailMode && failure.next_action) {
    appendTextLine(body, `next: ${failure.next_action}`, "#8d93a1");
  }
  if (panel.state.rebaselinePending) {
    const pending = panel.state.rebaselinePending;
    const pendingLabel =
      panel.state.inFlightRebaseline
        ? `rebaseline pending: ${pending.reason} (in flight)`
        : pending.retryable
          ? `rebaseline pending: ${pending.reason} (retryable)`
          : `rebaseline pending: ${pending.reason}`;
    appendTextLine(body, pendingLabel, "#9ed0ff");
    if (pending.last_known_baseline_graph_hash) {
      appendCodeLine(body, `expected_baseline: ${pending.last_known_baseline_graph_hash}`, "#8d93a1");
    }
  }
  if (!normalDetailMode && (failure.session_id || failure.turn_id || failure.baseline_turn_id)) {
    appendTextLine(
      body,
      `session=${failure.session_id || "new"} turn=${failure.turn_id || "pending"} baseline=${failure.baseline_turn_id || "none"}`,
      "#8d93a1",
    );
  }
  if (!normalDetailMode && failure.audit_error) {
    appendTextLine(body, `audit_error: ${failure.audit_error}`, "#ffb86c");
  }
  const recovery = panel.state.rebaselineRecovery;
  if (recovery?.action === "rebaseline" && recovery.reason === "stale_state_recovery") {
    appendTextLine(body, "The current canvas can be promoted to the new baseline.", "#9ed0ff");
    if (recovery.last_known_baseline_graph_hash) {
      appendCodeLine(body, `expected_baseline: ${recovery.last_known_baseline_graph_hash}`, "#8d93a1");
    }
  }
  if (!normalDetailMode && failure.agent_failure_context && Object.keys(failure.agent_failure_context).length) {
    body.appendChild(createDetails("agent failure context", failure.agent_failure_context));
  }
  if (!normalDetailMode) {
    body.appendChild(createDetails("raw failure", failure));
  }
}

export function appendQueueDetail(body, panel, snapshot = null, deps = {}) {
  const {
    appendTextLine,
    collectQueueIssues,
    getQueueGuardStateForPanel,
  } = deps;
  const normalDetailMode = Boolean(snapshot);
  if (normalDetailMode) {
    const queueDisplay = snapshot?.queueDisplay;
    if (!queueDisplay || typeof queueDisplay !== "object") {
      return;
    }
    if (queueDisplay.message) {
      appendTextLine(body, queueDisplay.message, queueDisplay.state === "blocked" ? "#ffb86c" : "#4caf50");
    }
    if (Array.isArray(queueDisplay.issues) && queueDisplay.issues.length) {
      for (const issue of queueDisplay.issues) {
        appendTextLine(body, issue.message || issue.code || "Queue issue", issue.severity === "error" ? "#ffb86c" : "#9ed0ff");
      }
    }
    if (!queueDisplay.message && !queueDisplay.issues?.length && queueDisplay.reason) {
      appendTextLine(body, queueDisplay.reason, queueDisplay.state === "blocked" ? "#ffb86c" : "#8d93a1");
    }
    return;
  }
  const queueGuard = snapshot?.queueGuard || panel.state.queueGuard || getQueueGuardStateForPanel();
  const issues = collectQueueIssues(snapshot?.candidateReport || panel.state.candidateReport);
  if (queueGuard.fallbackWarning) {
    appendTextLine(body, queueGuard.fallbackWarning, "#ffb86c");
  }
  if (queueGuard.lastBlockNotice?.message && !normalDetailMode) {
    appendTextLine(body, queueGuard.lastBlockNotice.message, "#ff7f7f");
  }
  if (!normalDetailMode && queueGuard.hookInstalled) {
    appendTextLine(body, `native queue guard: active via ${queueGuard.hookPath}`, "#4caf50");
  } else if (!normalDetailMode) {
    appendTextLine(body, "native queue guard: panel warning fallback only", "#8d93a1");
  }
  const queueAllowed = snapshot?.queueAllowed ?? panel.state.queueAllowed;
  if (queueAllowed) {
    appendTextLine(body, "Queue-eligible candidate. Native queue path remains unchanged.", "#4caf50");
  } else if (issues.length) {
    for (const issue of issues) {
      appendTextLine(body, issue.message, "#ffb86c");
    }
  } else if (queueGuard.activeContext?.queueAllowed === false) {
    appendTextLine(body, `Applied turn ${queueGuard.activeContext.turnId || "unknown"} remains queue-blocked.`, "#ff7f7f");
  } else {
    appendTextLine(body, "Queue disabled in this proof shell. Candidate review remains local-only for now.", "#8d93a1");
  }
}

function bubbleDetailSignature(panel, msg, detailSnapshot) {
  const responseDetail = responseDetailForMessage(panel, msg, detailSnapshot);
  const normalDetail = normalDetailSnapshotForRender(responseDetail) || {};
  const detailSigParts = [
    responseDetail?.turn?.status || responseDetail?.outcome?.kind || "",
    responseDetail?.outcome?.summary || responseDetail?.outcome?.question || "",
    normalDetail?.changeDetails?.done_summary || "",
    String(allFieldChangesForRender(msg, normalDetail).length),
    msg?.turn_id || "",
    msg?.detail_turn_id || "",
    String(msg?.text || "").slice(0, 80),
  ];
  return detailSigParts.join("|");
}

function bubbleRenderSignature(panel, msg, deps = {}) {
  const { candidateActionState, latestAgentMessageKey, messageKey, messageSignature } = deps;
  const responseDetail = responseDetailForMessage(panel, msg, null);
  const normalDetail = normalDetailSnapshotForRender(responseDetail) || null;
  const actionState = typeof candidateActionState === "function"
    ? candidateActionState(panel, msg, normalDetail)
    : {};
  const applyCandidate = applyCandidateForRender(panel, msg, normalDetail);
  const responseId = ratingResponseIdForMessage(panel, msg);
  const ratingState = responseId ? getRatingResponseState(panel, responseId) : null;
  const signatureParts = [
    typeof messageSignature === "function" ? messageSignature(msg) : "",
    responseDetail?.turn?.status || responseDetail?.outcome?.kind || "",
    responseDetail?.outcome?.summary || responseDetail?.outcome?.question || "",
    normalDetail?.changeDetails?.done_summary || "",
    String(allFieldChangesForRender(msg, normalDetail).length),
    applyCandidate?.turnIdentity?.turnId || actionState.turnId || "",
    applyCandidate?.eligibility?.reason || actionState.eligibility?.reason || "",
    applyCandidate?.eligibility?.message || actionState.eligibility?.message || "",
    actionState.active ? "1" : "0",
    actionState.applyDisabled ? "1" : "0",
    actionState.rejectDisabled ? "1" : "0",
    deps.ratingHasLaterUserOrPending ? "rating-blocked-by-next-turn" : "",
    !deps.ratingHasLaterUserOrPending && String(messageKey || "") === String(latestAgentMessageKey || "") ? "rating-latest" : "",
    responseId || "",
    isRatingResponseSubmitted(panel, responseId) ? "rating-submitted" : "",
    Number.isFinite(ratingState?.rating) ? `rating-${ratingState.rating}` : "",
    ratingWidgetDisabled(panel, deps) ? "rating-disabled" : "",
    panel?.state?.turnId || "",
    isPendingAgentMessage(msg) ? "pending-response" : "",
    msg?.progress ? JSON.stringify(msg.progress) : "",
    msg?.progress_label || "",
  ];
  return signatureParts.join("|");
}

function safeStorageGet(key) {
  try {
    if (typeof localStorage === "undefined" || localStorage === null) {
      return null;
    }
    return localStorage.getItem(key);
  } catch (_error) {
    return null;
  }
}

function safeStorageSet(key, value) {
  try {
    if (typeof localStorage === "undefined" || localStorage === null) {
      return;
    }
    localStorage.setItem(key, value);
  } catch (_error) {
    // Best-effort persistence only.
  }
}

function storageBoolean(value) {
  return value === true || value === "1" || value === "true" || value === "yes";
}

function ratingPackShareDefault(deps = {}) {
  if (typeof deps.getPackShareDefault === "function") {
    return Boolean(deps.getPackShareDefault());
  }
  return storageBoolean(safeStorageGet(RATING_PACK_SHARE_DEFAULT_LS_KEY));
}

function persistRatingPackShareDefault(value, deps = {}) {
  if (typeof deps.setPackShareDefault === "function") {
    deps.setPackShareDefault(Boolean(value));
    return;
  }
  safeStorageSet(RATING_PACK_SHARE_DEFAULT_LS_KEY, value ? "1" : "0");
}

function ratingWidgetDisabled(panel, deps = {}) {
  if (typeof deps.isRatingWidgetDisabled === "function") {
    return Boolean(deps.isRatingWidgetDisabled(panel));
  }
  return storageBoolean(safeStorageGet(RATING_WIDGET_DISABLED_LS_KEY));
}

function ratingTurnIdForMessage(panel, message) {
  return (
    (typeof message?.turn_id === "string" && message.turn_id)
    || (typeof message?.detail_turn_id === "string" && message.detail_turn_id)
    || null
  );
}

function ratingResponseIdForMessage(panel, message) {
  const sessionId = typeof panel?.state?.sessionId === "string" && panel.state.sessionId
    ? panel.state.sessionId
    : null;
  const turnId = ratingTurnIdForMessage(panel, message);
  if (!sessionId || !turnId) {
    return null;
  }
  return `${sessionId}/${turnId}`;
}

function isRatingResponseSubmitted(panel, responseId) {
  if (!responseId) {
    return false;
  }
  const submitted = panel?.state?.ratingSubmittedResponseIds;
  if (submitted instanceof Set) {
    return submitted.has(responseId);
  }
  return Boolean(submitted && typeof submitted === "object" && submitted[responseId]);
}

function ensureRatingResponseStates(panel) {
  if (!panel?.state) {
    return {};
  }
  if (!panel.state.ratingResponseStates || typeof panel.state.ratingResponseStates !== "object") {
    panel.state.ratingResponseStates = {};
  }
  return panel.state.ratingResponseStates;
}

function getRatingResponseState(panel, responseId) {
  if (!panel?.state || !responseId) {
    return null;
  }
  const states = panel.state.ratingResponseStates;
  const state = states && typeof states === "object" ? states[responseId] : null;
  return state && typeof state === "object" ? state : null;
}

function updateRatingResponseState(panel, responseId, patch) {
  if (!panel?.state || !responseId || !patch || typeof patch !== "object") {
    return null;
  }
  const states = ensureRatingResponseStates(panel);
  const existing = states[responseId] && typeof states[responseId] === "object"
    ? states[responseId]
    : {};
  states[responseId] = { ...existing, ...patch };
  return states[responseId];
}

function markRatingResponseSubmitted(panel, responseId) {
  if (!panel?.state || !responseId) {
    return;
  }
  if (!panel.state.ratingSubmittedResponseIds || typeof panel.state.ratingSubmittedResponseIds !== "object") {
    panel.state.ratingSubmittedResponseIds = {};
  }
  panel.state.ratingSubmittedResponseIds[responseId] = true;
  updateRatingResponseState(panel, responseId, { submitted: true });
}

function renderExecutorProgressRow(msg, panel, deps = {}) {
  const { el } = deps;
  if (!isPendingAgentMessage(msg) || typeof el !== "function") {
    return null;
  }
  const progress = (msg.progress && typeof msg.progress === "object"
    ? msg.progress
    : null)
    || (panel?.state?.executorProgress && typeof panel.state.executorProgress === "object" ? panel.state.executorProgress : null)
    || {};
  const secondaryText = (typeof msg?.text === "string" && msg.text.trim())
    || (typeof msg.progress_label === "string" && msg.progress_label)
    || null;
  const steps = [
    ["Decide", progress.decide || "pending"],
    ["Research", progress.research || "pending"],
    ["Execute", progress.execute || "pending"],
    ["Review", progress.review || "pending"],
  ];
  const row = el("div");
  row.dataset.vibecomfyPhaseSource = "transcript";
  Object.assign(row.style, {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    marginTop: "0",
    flexWrap: "wrap",
    fontSize: "10px",
    color: "#8d93a1",
  });
  const colorFor = (status) => status === "active" ? "#ffd36f" : (status === "done" ? "#54c77a" : "#3b414c");
  const textColorFor = (status) => status === "active" ? "#fff4d6" : (status === "done" ? "#d7f2e1" : "#7f8794");
  for (let index = 0; index < steps.length; index += 1) {
    const [label, status] = steps[index];
    if (index > 0) {
      const divider = el("span", "->");
      divider.style.color = "#555c68";
      row.appendChild(divider);
    }
    const step = el("span");
    step.dataset.vibecomfyExecutorStage = label.toLowerCase();
    step.dataset.vibecomfyExecutorStatus = status;
    Object.assign(step.style, {
      display: "inline-flex",
      alignItems: "center",
      gap: "4px",
      color: textColorFor(status),
      fontWeight: status === "active" ? "700" : "500",
    });
    const dot = el("span");
    Object.assign(dot.style, {
      width: "6px",
      height: "6px",
      borderRadius: "50%",
      background: colorFor(status),
      boxShadow: status === "active" ? "0 0 0 3px rgba(255, 211, 111, 0.12)" : "none",
      flexShrink: "0",
    });
    step.appendChild(dot);
    step.appendChild(el("span", label));
    row.appendChild(step);
  }
  if (secondaryText) {
    const labelLine = el("div", secondaryText);
    labelLine.dataset.vibecomfyProgressSecondary = "1";
    Object.assign(labelLine.style, {
      flexBasis: "100%",
      fontSize: "11px",
      color: "#9aa3b2",
      marginTop: "3px",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
      maxWidth: "100%",
      fontWeight: "400",
    });
    row.appendChild(labelLine);
  }
  return row;
}

function ensureRatingTimers(panel) {
  if (!panel) {
    return {};
  }
  if (!panel.__vibecomfyRatingTimers || typeof panel.__vibecomfyRatingTimers !== "object") {
    panel.__vibecomfyRatingTimers = {};
  }
  return panel.__vibecomfyRatingTimers;
}

function clearRatingTimer(panel, responseId) {
  if (!panel || !responseId || !panel.__vibecomfyRatingTimers) {
    return;
  }
  const existing = panel.__vibecomfyRatingTimers[responseId];
  if (existing) {
    clearTimeout(existing);
    delete panel.__vibecomfyRatingTimers[responseId];
  }
}

function scheduleRatingNoticeClear(panel, responseId, element) {
  clearRatingTimer(panel, responseId);
  const timers = ensureRatingTimers(panel);
  timers[responseId] = setTimeout(() => {
    delete timers[responseId];
    if (!element?.isConnected) {
      return;
    }
    element.textContent = "";
    element.style.display = "none";
  }, RATING_WIDGET_CLEAR_DELAY_MS);
  if (typeof timers[responseId]?.unref === "function") {
    timers[responseId].unref();
  }
}

function ensureRatingExpiryTimers(panel) {
  if (!panel) {
    return {};
  }
  if (!panel.__vibecomfyRatingExpiryTimers || typeof panel.__vibecomfyRatingExpiryTimers !== "object") {
    panel.__vibecomfyRatingExpiryTimers = {};
  }
  return panel.__vibecomfyRatingExpiryTimers;
}

function clearRatingExpiryTimer(panel, responseId) {
  if (!panel || !responseId || !panel.__vibecomfyRatingExpiryTimers) {
    return;
  }
  const existing = panel.__vibecomfyRatingExpiryTimers[responseId];
  if (existing) {
    clearTimeout(existing);
    delete panel.__vibecomfyRatingExpiryTimers[responseId];
  }
}

function scheduleRatingExpiry(panel, responseId, element) {
  clearRatingExpiryTimer(panel, responseId);
  const timers = ensureRatingExpiryTimers(panel);
  timers[responseId] = setTimeout(() => {
    delete timers[responseId];
    if (!element?.isConnected) {
      return;
    }
    element.style.display = "none";
    element.textContent = "";
  }, RATING_WIDGET_EXPIRY_MS);
  if (typeof timers[responseId]?.unref === "function") {
    timers[responseId].unref();
  }
}

function latestAgentMessageKey(displayEntries) {
  let latestKey = null;
  for (const entry of displayEntries || []) {
    if (entry?.msg?.role === "agent") {
      latestKey = entry.key;
    }
  }
  return latestKey;
}

function hasLaterUserOrPendingMessage(displayEntries, messageKey) {
  let seenMessage = false;
  for (const entry of displayEntries || []) {
    if (String(entry?.key || "") === String(messageKey || "")) {
      seenMessage = true;
      continue;
    }
    if (!seenMessage) {
      continue;
    }
    const msg = entry?.msg;
    if (msg?.role === "user" || isPendingAgentMessage(msg)) {
      return true;
    }
  }
  return false;
}

function shouldRenderRatingWidget(panel, msg, messageKey, deps = {}) {
  if (msg?.role !== "agent") {
    return false;
  }
  if (isPendingAgentMessage(msg)) {
    return false;
  }
  if (String(messageKey || "") !== String(deps.latestAgentMessageKey || "")) {
    return false;
  }
  if (deps.ratingHasLaterUserOrPending) {
    return false;
  }
  if (ratingWidgetDisabled(panel, deps)) {
    return false;
  }
  const turnId = ratingTurnIdForMessage(panel, msg);
  if (!turnId) {
    return false;
  }
  const responseId = ratingResponseIdForMessage(panel, msg);
  return Boolean(responseId);
}

export function renderRatingWidget(panel, msg, deps = {}) {
  const { button, el, submitRating } = deps;
  if (typeof el !== "function" || typeof submitRating !== "function") {
    return null;
  }
  const responseId = ratingResponseIdForMessage(panel, msg);
  const sessionId = typeof panel?.state?.sessionId === "string" ? panel.state.sessionId : "";
  const turnId = ratingTurnIdForMessage(panel, msg) || "";
  if (!responseId || !sessionId || !turnId) {
    return null;
  }

  const root = el("div");
  root.dataset.vibecomfyRatingWidget = "1";
  root.dataset.vibecomfyResponseId = responseId;
  Object.assign(root.style, {
    alignSelf: "stretch",
    display: "grid",
    gap: "6px",
    marginTop: "6px",
    padding: "8px",
    border: "1px solid #2d3340",
    borderRadius: "6px",
    background: "#12151c",
    maxWidth: "100%",
    minWidth: "0",
  });

  const heading = el("div", "Rate this response");
  Object.assign(heading.style, {
    color: "#c4ccd6",
    fontSize: "10px",
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  });
  root.appendChild(heading);

  const ratingRow = el("div");
  ratingRow.dataset.vibecomfyRatingStep = "1";
  Object.assign(ratingRow.style, {
    display: "grid",
    gridTemplateColumns: "repeat(10, minmax(0, 1fr))",
    gap: "3px",
  });
  root.appendChild(ratingRow);

  const stepTwo = el("div");
  stepTwo.dataset.vibecomfyRatingStep = "2";
  Object.assign(stepTwo.style, {
    display: "none",
    gap: "6px",
  });

  const comment = document.createElement("textarea");
  comment.dataset.vibecomfyRatingComment = "1";
  comment.placeholder = "Optional note";
  Object.assign(comment.style, {
    width: "100%",
    minHeight: "54px",
    resize: "vertical",
    boxSizing: "border-box",
    background: "#0d0f14",
    color: "#edf2f7",
    border: "1px solid #343946",
    borderRadius: "5px",
    padding: "6px",
    fontFamily: "monospace",
    fontSize: "11px",
  });
  stepTwo.appendChild(comment);

  const packRow = el("label");
  Object.assign(packRow.style, {
    display: "flex",
    alignItems: "flex-start",
    gap: "6px",
    color: "#aeb6c4",
    fontSize: "11px",
  });
  const packCheckbox = document.createElement("input");
  packCheckbox.type = "checkbox";
  packCheckbox.checked = ratingPackShareDefault(deps);
  packCheckbox.dataset.vibecomfyRatingPackShared = "1";
  packCheckbox.onchange = () => {
    persistRatingPackShareDefault(packCheckbox.checked, deps);
  };
  Object.assign(packCheckbox.style, {
    marginTop: "1px",
    flexShrink: 0,
  });
  packRow.appendChild(packCheckbox);

  const packLabelStack = el("div");
  Object.assign(packLabelStack.style, {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  });
  const packLabelPrimary = el("span", "Share my debug pack");
  Object.assign(packLabelPrimary.style, {
    color: "#c4ccd6",
    fontWeight: "500",
  });
  const packLabelSecondary = el(
    "span",
    "This will share your anonymised workflow + turn publicly for us and others to learn from & improve.",
  );
  Object.assign(packLabelSecondary.style, {
    color: "#8d93a1",
    fontSize: "10px",
    lineHeight: "1.35",
  });
  packLabelStack.appendChild(packLabelPrimary);
  packLabelStack.appendChild(packLabelSecondary);
  packRow.appendChild(packLabelStack);
  stepTwo.appendChild(packRow);

  const submitRow = el("div");
  Object.assign(submitRow.style, {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  });
  const reportIssueButton = typeof button === "function"
    ? button("Report issue", () => {})
    : el("button", "Report issue");
  reportIssueButton.dataset.vibecomfyRatingReportIssue = "1";
  Object.assign(reportIssueButton.style, {
    display: "none",
    padding: "4px 8px",
    fontSize: "11px",
  });
  reportIssueButton.onclick = () => {
    if (typeof deps.showIssueModal === "function") {
      deps.showIssueModal(panel);
    }
  };
  submitRow.appendChild(reportIssueButton);

  const submitButton = typeof button === "function"
    ? button("Submit rating", () => {})
    : el("button", "Submit rating");
  submitButton.dataset.vibecomfyRatingSubmit = "1";
  Object.assign(submitButton.style, {
    padding: "4px 8px",
    fontSize: "11px",
  });
  const status = el("div");
  status.dataset.vibecomfyRatingStatus = "1";
  Object.assign(status.style, {
    display: "none",
    color: "#8d93a1",
    fontSize: "10px",
    minWidth: "0",
    overflowWrap: "anywhere",
  });
  submitRow.appendChild(submitButton);
  submitRow.appendChild(status);
  stepTwo.appendChild(submitRow);
  root.appendChild(stepTwo);

  let selectedRating = null;
  const ratingButtons = [];
  const setSelectedRating = (rating) => {
    selectedRating = rating;
    updateRatingResponseState(panel, responseId, { rating });
    clearRatingExpiryTimer(panel, responseId);
    stepTwo.style.display = "grid";
    reportIssueButton.style.display = rating < 5 ? "inline-block" : "none";
    for (const entry of ratingButtons) {
      entry.button.dataset.selected = entry.rating === rating ? "1" : "0";
      entry.button.style.background = entry.rating === rating ? "#27466f" : "#1a1d25";
      entry.button.style.borderColor = entry.rating === rating ? "#7db6ff" : "#343946";
      entry.button.style.color = entry.rating === rating ? "#ffffff" : "#c4ccd6";
    }
    scrollChatThreadToBottom(panel);
  };
  for (let rating = 1; rating <= 10; rating += 1) {
    const ratingButton = typeof button === "function"
      ? button(String(rating), () => setSelectedRating(rating))
      : el("button", String(rating));
    ratingButton.dataset.vibecomfyRatingValue = String(rating);
    ratingButton.onclick = () => setSelectedRating(rating);
    Object.assign(ratingButton.style, {
      minWidth: "0",
      padding: "4px 0",
      fontSize: "10px",
      lineHeight: "1.2",
      background: "#1a1d25",
      borderColor: "#343946",
      color: "#c4ccd6",
    });
    ratingButtons.push({ rating, button: ratingButton });
    ratingRow.appendChild(ratingButton);
  }

  const existingRatingState = getRatingResponseState(panel, responseId);
  if (Number.isFinite(existingRatingState?.rating)) {
    setSelectedRating(existingRatingState.rating);
  }
  if (existingRatingState?.submitted || isRatingResponseSubmitted(panel, responseId)) {
    submitButton.disabled = true;
    status.style.display = "block";
    status.style.color = "#8d93a1";
    status.textContent = "Rating applied.";
    clearRatingExpiryTimer(panel, responseId);
  } else {
    scheduleRatingExpiry(panel, responseId, root);
  }

  submitButton.onclick = async () => {
    if (!selectedRating || submitButton.disabled) {
      return;
    }
    clearRatingTimer(panel, responseId);
    clearRatingExpiryTimer(panel, responseId);
    submitButton.disabled = true;
    status.style.display = "block";
    status.style.color = "#8d93a1";
    status.textContent = "Submitting...";
    const result = await submitRating(panel, {
      rating: selectedRating,
      comment: comment.value || null,
      pack_shared: packCheckbox.checked,
      pack_comment: null,
      response_id: responseId,
      session_id: sessionId,
      turn_id: turnId,
    });
    if (!root.isConnected) {
      return;
    }
    if (result?.ok) {
      updateRatingResponseState(panel, responseId, { rating: selectedRating, submitted: true });
      markRatingResponseSubmitted(panel, responseId);
      clearRatingTimer(panel, responseId);
      clearRatingExpiryTimer(panel, responseId);
      submitButton.disabled = true;
      status.style.display = "block";
      status.style.color = "#8d93a1";
      status.textContent = "Rating applied.";
      scrollChatThreadToBottom(panel);
      return;
    }
    submitButton.disabled = false;
    status.style.color = "#ffb86c";
    status.textContent = result?.detail || result?.error || "Could not submit rating.";
    scheduleRatingNoticeClear(panel, responseId, status);
  };

  return root;
}

function appendTurnMeta(target, panel, message, snapshot = null, deps = {}) {
  const { appendTextLine, el } = deps;
  const turnId = typeof message?.turn_id === "string" && message.turn_id ? message.turn_id : snapshot?.turn_id;
  if (turnId) {
    appendTextLine(target, `turn: ${turnId}`, "#8d93a1");
  }

  const allChanges = allFieldChangesForRender(message, snapshot);
  if (allChanges.length > 0) {
    appendTextLine(target, allChanges.map(function (change) {
      const fieldPath = typeof change?.fieldPath === "string"
        ? change.fieldPath
        : (typeof change?.field_path === "string" ? change.field_path : "");
      if (!fieldPath) {
        return "";
      }
      const nextValue =
        typeof change.newValue !== "undefined"
          ? change.newValue
          : typeof change.new_value !== "undefined"
            ? change.new_value
            : change.new;
      return `${fieldPath}${typeof nextValue !== "undefined" ? ` -> ${String(nextValue).slice(0, 40)}` : ""}`;
    }).filter(Boolean).join("; "), "#c4ccd6");
  }

  if (panel.state.chatDetailJsonPath && turnId) {
    const detailLink = el("a", "view response ->");
    detailLink.href = `/vibecomfy/agent-edit/session-json?session_id=${encodeURIComponent(panel.state.sessionId || "")}`;
    detailLink.target = "_blank";
    detailLink.rel = "noopener";
    Object.assign(detailLink.style, {
      color: "#9ed0ff",
      textDecoration: "none",
    });
    target.appendChild(detailLink);
  }
}

export function populateAgentBubbleDetail(target, panel, message, snapshot = null, deps = {}) {
  const {
    appendCandidateDetail,
    appendFailureDetail,
    appendQueueDetail,
    appendTextLine,
    changeDetailsForMessage,
    clearNode,
    createBubbleDetailSection,
    createDetails,
    el,
  } = deps;
  clearNode(target);

  const responseDetail = responseDetailForMessage(panel, message, snapshot);
  const normalSnapshot = normalDetailSnapshotForRender(responseDetail);
  const ordinarySnapshot = normalSnapshot || null;
  const actionState = typeof deps.candidateActionState === "function"
    ? deps.candidateActionState(panel, message, ordinarySnapshot)
    : null;
  const allowsApply = routeAllowsCandidateDetail(panel, message, ordinarySnapshot, actionState);

  const isExecutorMessage = isPendingAgentMessage(message) || message?.source === "agent-edit";
  if (!isExecutorMessage) {
    const metaSection = createBubbleDetailSection("Turn");
    appendTurnMeta(metaSection.body, panel, message, ordinarySnapshot, { appendTextLine, el });
    target.appendChild(metaSection.section);
  }

  const changeDetails =
    ordinarySnapshot?.changeDetails
    || (typeof changeDetailsForMessage === "function"
      ? changeDetailsForMessage(panel, message, ordinarySnapshot)
      : null);
  if (changeDetails) {
    const changesSection = createBubbleDetailSection("Changes");
    const count = Number.isFinite(changeDetails.landed_operation_count)
      ? changeDetails.landed_operation_count
      : (Array.isArray(changeDetails.operations) ? changeDetails.operations.length : 0);
    appendTextLine(changesSection.body, `${count} operation${count === 1 ? "" : "s"}`, "#c4ccd6");
    if (changeDetails.done_summary) {
      appendTextLine(changesSection.body, changeDetails.done_summary, "#9ed0ff");
    }
    if (Array.isArray(changeDetails.operations) && changeDetails.operations.length) {
      const opList = el("div");
      Object.assign(opList.style, {
        display: "grid",
        gap: "3px",
        minWidth: "0",
      });
      for (const op of changeDetails.operations) {
        appendTextLine(opList, op?.summary || `${op?.field_path || "field"} changed`, "#b9ffcc");
      }
      changesSection.body.appendChild(opList);
    }
    target.appendChild(changesSection.section);
  }

  if (ordinarySnapshot?.progress && typeof ordinarySnapshot.progress === "object") {
    const progressSection = createBubbleDetailSection("Progress");
    const progress = ordinarySnapshot.progress;
    const headline = typeof progress.headline === "string" && progress.headline
      ? progress.headline
      : (typeof message?.progress_label === "string" ? message.progress_label : "");
    if (headline) {
      appendTextLine(progressSection.body, headline, "#9ed0ff");
    }
    const stages = ["decide", "research", "execute", "review"]
      .filter((key) => typeof progress[key] === "string" && progress[key])
      .map((key) => `${key}: ${progress[key]}`);
    if (stages.length) {
      appendTextLine(progressSection.body, stages.join("; "), "#c4ccd6");
    }
    if (progressSection.body.children.length) {
      target.appendChild(progressSection.section);
    }
  }

  // Legacy fallback: pending websocket progress messages may carry a
  // canonical_activity snapshot. Render its safe details (per-action rows,
  // counts, diagnostics) when the normalized response detail has no equivalent
  // statement-level progress to display.
  if (isPendingAgentMessage(message) && message?.canonical_activity && !ordinarySnapshot?.progress) {
    _renderCanonicalDetails(target, message.canonical_activity, deps);
  }

  // Candidate section: only for applyable routes (revise/adapt/legacy-aliases)
  if (allowsApply) {
    const candidateSection = createBubbleDetailSection("Candidate");
    appendCandidateDetail(candidateSection.body, panel, message, ordinarySnapshot);
    if (candidateSection.body.children.length) {
      target.appendChild(candidateSection.section);
    }
  }

  // Applied-node feedback is shown on the applied turn bubble even when the
  // route is no longer applyable. Fallback to panel state when the bubble's
  // own snapshot does not carry the applied feedback (e.g. after rehydrate).
  const appliedFeedback = ordinarySnapshot?.lastAppliedChanges || panel.state.lastAppliedChanges || null;
  if (appliedFeedback?.items?.length) {
    const feedbackSection = createBubbleDetailSection("Feedback");
    appendCandidateDetail(feedbackSection.body, panel, message, ordinarySnapshot);
    if (feedbackSection.body.children.length) {
      target.appendChild(feedbackSection.section);
    }
  }

  const failureSection = createBubbleDetailSection("Failure");
  appendFailureDetail(failureSection.body, panel, ordinarySnapshot);
  if (failureSection.body.children.length) {
    target.appendChild(failureSection.section);
  }

  const queueSection = createBubbleDetailSection("Queue");
  appendQueueDetail(queueSection.body, panel, ordinarySnapshot);
  if (queueSection.body.children.length) {
    target.appendChild(queueSection.section);
  }
}

export function renderChatBubbleNode(bubble, panel, msg, messageKey, messageIndex, deps = {}) {
  const {
    candidateActionState,
    clearNode,
    el,
    ensureThreadRenderState,
  } = deps;
  clearNode(bubble);
  bubble.dataset.vibecomfyMessageKey = messageKey;
  const isUser = msg.role === "user";
  Object.assign(bubble.style, {
    display: "flex",
    flexDirection: "column",
    alignItems: isUser ? "flex-end" : "flex-start",
    marginBottom: "6px",
    maxWidth: "100%",
    minWidth: "0",
  });

  const label = el("span", isUser ? "You" : "VibeComfy");
  Object.assign(label.style, {
    fontSize: "9px",
    fontWeight: "700",
    color: isUser ? "#74A7FF" : "#FF8A1A",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: "2px",
  });
  bubble.appendChild(label);

  const isPendingResponse = isPendingAgentMessage(msg);
  const bubbleText = isPendingResponse ? "" : String(msg.text || "");
  const text = renderMarkdown(panel.document || document, bubbleText);
  Object.assign(text.style, {
    fontSize: "12px",
    color: isUser ? "#d8dce3" : "#d8dce3",
    background: isUser ? "#1e2129" : "#1e2129",
    borderLeft: isUser ? "none" : "2px solid #ff7a00",
    padding: "6px 10px",
    borderRadius: isUser ? "10px 10px 3px 10px" : "3px 10px 10px 3px",
    maxWidth: "92%",
    wordBreak: "break-word",
    overflowWrap: "anywhere",
    whiteSpace: "normal",
    lineHeight: "1.4",
    minWidth: "0",
  });
  const progressRow = renderExecutorProgressRow(msg, panel, { el });
  if (progressRow) {
    text.appendChild(progressRow);
  }
  bubble.appendChild(text);

  // Relative timestamp below the speech bubble, bottom-aligned to the bubble's
  // side, mirroring the activity-row "just now" styling. Stamped server-side
  // from the turn directory's mtime (read_chat_history); absent on messages
  // that predate that field, in which case we simply render no time line.
  const tsRel = _formatRelativeTime(msg.timestamp);
  let tsLine = null;
  if (tsRel) {
    tsLine = el("div", tsRel);
    Object.assign(tsLine.style, {
      fontSize: "9px",
      color: "#6b7080",
      marginTop: "2px",
      textAlign: "right",
      alignSelf: isUser ? "flex-end" : "flex-start",
    });
    tsLine.title = msg.timestamp;
  }

  if (isUser) {
    if (tsLine) {
      bubble.appendChild(tsLine);
    }
    return;
  }

  const detailTurnKey =
    typeof msg.turn_id === "string" && msg.turn_id
      ? `turn:${msg.turn_id}`
      : (typeof msg.detail_turn_id === "string" && msg.detail_turn_id
        ? `turn:${msg.detail_turn_id}:failure:${messageKey || messageIndex}`
        : `agent:${messageKey || messageIndex}:${String(msg.text || "").slice(0, 24)}`);
  const responseDetail = responseDetailForMessage(panel, msg, null);
  const detailSnapshot = normalDetailSnapshotForRender(responseDetail);
  const detailSignature = bubbleDetailSignature(panel, msg, detailSnapshot);
  const detailRow = el("div");
  Object.assign(detailRow.style, {
    marginTop: "3px",
    fontSize: "10px",
    maxWidth: "100%",
    minWidth: "0",
    overflowWrap: "anywhere",
  });

  const detailToggle = el("span", "\u25b6 details");
  detailToggle.dataset.vibecomfyBubbleDetailToggle = "1";
  detailToggle.dataset.vibecomfyBubbleDetailTurnKey = detailTurnKey;
  Object.assign(detailToggle.style, {
    // Match the relative-time line: same font size and muted color.
    fontSize: "9px",
    color: "#6b7080",
    cursor: "pointer",
    userSelect: "none",
  });

  const detailBody = el("div");
  Object.assign(detailBody.style, {
    display: "none",
    marginTop: "4px",
    padding: "6px 8px",
    background: "#0d0f14",
    border: "1px solid #282a32",
    borderRadius: "4px",
    fontSize: "10px",
    color: "#8d93a1",
    gridTemplateColumns: "minmax(0, 1fr)",
    gap: "4px 8px",
    alignItems: "baseline",
    maxWidth: "100%",
    minWidth: "0",
    maxHeight: "360px",
    overflow: "auto",
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  });

  const threadState = ensureThreadRenderState(panel);
  if (!threadState.bubbleDetailSignatures) {
    threadState.bubbleDetailSignatures = {};
  }

  let detailShown = !!panel.state.expandedBubbleTurnKeys?.[detailTurnKey];
  const needsPopulate = detailShown && (
    !threadState.bubbleDetailSignatures[detailTurnKey]
    || threadState.bubbleDetailSignatures[detailTurnKey] !== detailSignature
  );

  if (needsPopulate) {
    populateAgentBubbleDetail(detailBody, panel, msg, detailSnapshot, deps);
    threadState.bubbleDetailSignatures[detailTurnKey] = detailSignature;
  } else if (
    !detailShown
    && threadState.bubbleDetailSignatures[detailTurnKey]
    && threadState.bubbleDetailSignatures[detailTurnKey] !== detailSignature
  ) {
    delete threadState.bubbleDetailSignatures[detailTurnKey];
  }

  detailToggle.textContent = detailShown ? "\u25bc details" : "\u25b6 details";
  detailBody.style.display = detailShown ? "grid" : "none";

  detailToggle.onclick = function () {
    detailShown = !detailShown;
    if (!panel.state.expandedBubbleTurnKeys || typeof panel.state.expandedBubbleTurnKeys !== "object") {
      panel.state.expandedBubbleTurnKeys = {};
    }
    if (detailShown) {
      panel.state.expandedBubbleTurnKeys[detailTurnKey] = true;
    } else {
      delete panel.state.expandedBubbleTurnKeys[detailTurnKey];
    }
    detailToggle.textContent = detailShown ? "\u25bc details" : "\u25b6 details";
    detailBody.style.display = detailShown ? "grid" : "none";

    if (detailShown) {
      const liveThreadState = ensureThreadRenderState(panel);
      if (!liveThreadState.bubbleDetailSignatures) {
        liveThreadState.bubbleDetailSignatures = {};
      }
      if (
        !liveThreadState.bubbleDetailSignatures[detailTurnKey]
        || liveThreadState.bubbleDetailSignatures[detailTurnKey] !== detailSignature
      ) {
        populateAgentBubbleDetail(detailBody, panel, msg, detailSnapshot, deps);
        liveThreadState.bubbleDetailSignatures[detailTurnKey] = detailSignature;
      }
      // Scroll the freshly-expanded detail pane into full view (it usually opens
      // below the fold). Use the thread's own scroll container (panel.thread, the
      // same one scrollChatThreadToBottom drives) — a DOM ancestor-walk lands on the
      // wrong element. Wait two frames so the grid has laid out first; guard the
      // DOM APIs the jsdom test harness doesn't implement.
      const bringExpandedDetailIntoView = function () {
        try {
          const container = panel?.thread;
          if (!container || typeof detailRow.getBoundingClientRect !== "function"
            || typeof container.getBoundingClientRect !== "function") {
            return;
          }
          const rowRect = detailRow.getBoundingClientRect();
          const boxRect = container.getBoundingClientRect();
          let delta;
          if (rowRect.height <= boxRect.height) {
            // Fits: scroll DOWN just enough to reveal the bottom (top stays in view).
            delta = rowRect.bottom - boxRect.bottom;
            if (delta < 0) delta = 0;
          } else {
            // Taller than the viewport: align the top; the pane has its own scroll.
            delta = rowRect.top - boxRect.top;
          }
          if (Math.abs(delta) > 1) {
            const nextTop = container.scrollTop + delta;
            if (typeof container.scrollTo === "function") {
              container.scrollTo({ top: nextTop, behavior: "smooth" });
            } else {
              container.scrollTop = nextTop;
            }
          }
        } catch (_err) { /* no-op */ }
      };
      if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(function () { requestAnimationFrame(bringExpandedDetailIntoView); });
      } else {
        bringExpandedDetailIntoView();
      }
    }
  };

  // Lay the relative time and the "details" toggle on one full-width row below
  // the bubble: time on the bottom-left, details toggle pushed to the right
  // edge (marginLeft:auto keeps it right whether or not a time is present). The
  // expandable body drops below the row.
  detailRow.style.alignSelf = "stretch";
  detailRow.style.width = "100%";
  const detailHeader = el("div");
  Object.assign(detailHeader.style, {
    display: "flex",
    alignItems: "baseline",
    gap: "8px",
    width: "100%",
  });
  if (tsLine) {
    tsLine.style.alignSelf = "auto";
    tsLine.style.textAlign = "left";
    detailHeader.appendChild(tsLine);
  }
  detailToggle.style.marginLeft = "auto";
  detailHeader.appendChild(detailToggle);
  detailRow.appendChild(detailHeader);
  detailRow.appendChild(detailBody);
  bubble.appendChild(detailRow);

  if (shouldRenderRatingWidget(panel, msg, messageKey, deps)) {
    const ratingWidget = renderRatingWidget(panel, msg, deps);
    if (ratingWidget) {
      bubble.appendChild(ratingWidget);
    }
  }
}

export function reconcileChatBubbles(panel, messagesMount, displayEntries, deps = {}) {
  const {
    appendChildOnce,
    el,
    ensureThreadRenderState,
    messageSignature,
  } = deps;
  const threadState = ensureThreadRenderState(panel);
  const priorBubbleMap = {};
  const priorSignatures = threadState.signatures || {};
  const knownMountedNodes = new Set();

  // `bubbleMap` is a write-through cache keyed by `data-vibecomfy-message-key`.
  // The live DOM remains the source of truth: only mounted nodes survive reuse.
  for (const [key, bubbleEntry] of Object.entries(threadState.bubbleMap || {})) {
    if (bubbleEntry?.node?.parentNode !== messagesMount) {
      continue;
    }
    priorBubbleMap[key] = bubbleEntry;
    knownMountedNodes.add(bubbleEntry.node);
  }

  for (const child of Array.from(messagesMount?.children || [])) {
    const mountedKey = child?.dataset?.vibecomfyMessageKey;
    // A scheduled and an immediate lifecycle render may overlap before the
    // cache write-through below.  Reclaim a mounted bubble by its durable DOM
    // key so the same synthetic failure cannot be appended twice.
    if (typeof mountedKey === "string" && mountedKey && !priorBubbleMap[mountedKey]) {
      priorBubbleMap[mountedKey] = { node: child };
      knownMountedNodes.add(child);
    }
    if (!knownMountedNodes.has(child)) {
      messagesMount.removeChild(child);
    }
  }

  const nextBubbleMap = {};
  const nextSignatures = {};
  const nextKeyOrder = [];
  const latestAgentKey = latestAgentMessageKey(displayEntries);

  for (const entry of displayEntries) {
    const { msg, index, key } = entry;
    if (!msg || typeof msg !== "object" || !msg.role) {
      continue;
    }
    const ratingHasLaterUserOrPending = hasLaterUserOrPendingMessage(displayEntries, key);
    const signature = bubbleRenderSignature(panel, msg, {
      ...deps,
      latestAgentMessageKey: latestAgentKey,
      messageKey: key,
      ratingHasLaterUserOrPending,
      messageSignature,
    });
    let bubbleEntry = priorBubbleMap[key] || null;
    if (!bubbleEntry?.node) {
      bubbleEntry = { node: el("div") };
      renderChatBubbleNode(bubbleEntry.node, panel, msg, key, index, {
        ...deps,
        latestAgentMessageKey: latestAgentKey,
        ratingHasLaterUserOrPending,
      });
    } else if (priorSignatures[key] !== signature) {
      renderChatBubbleNode(bubbleEntry.node, panel, msg, key, index, {
        ...deps,
        latestAgentMessageKey: latestAgentKey,
        ratingHasLaterUserOrPending,
      });
    }
    nextBubbleMap[key] = bubbleEntry;
    nextSignatures[key] = signature;
    nextKeyOrder.push(key);
    appendChildOnce(messagesMount, bubbleEntry.node);
  }

  for (const [key, bubbleEntry] of Object.entries(priorBubbleMap)) {
    if (nextBubbleMap[key]) {
      continue;
    }
    const responseId = ratingResponseIdForMessage(panel, bubbleEntry?.msg);
    clearRatingTimer(panel, responseId);
    clearRatingExpiryTimer(panel, responseId);
    if (bubbleEntry?.node?.parentNode === messagesMount) {
      messagesMount.removeChild(bubbleEntry.node);
    }
  }

  // `signatures` is also write-through cache state: it mirrors the last render
  // content for each mounted bubble but never outranks the current DOM tree.
  threadState.renderedKeyOrder = nextKeyOrder;
  for (const entry of displayEntries) {
    if (nextBubbleMap[entry.key]) {
      nextBubbleMap[entry.key].msg = entry.msg;
    }
  }
  threadState.bubbleMap = nextBubbleMap;
  threadState.signatures = nextSignatures;
  threadState.lastVisibleKeySet = new Set(nextKeyOrder);
}

export function renderChatThread(panel, deps = {}) {
  const {
    clearNode,
    computeThreadDisplayEntries,
    ensureThreadRenderState,
    recordThreadRender: recordThreadRenderImpl,
    reconcileChatBubbles: reconcileChatBubblesImpl,
    collectThreadMessageEntries: collectThreadMessageEntriesImpl,
    el,
  } = deps;
  const body = panel.sections.chat;
  const { sessionRow, olderMount, messagesMount, emptyMount, activityMount } = ensureChatThreadMounts(body, { el, appendChildOnce: deps.appendChildOnce });
  if (activityMount) {
    activityMount.style.display = "none";
  }
  renderChatSessionLink(sessionRow, panel, { clearNode, el });

  const threadEntries = collectThreadMessageEntriesImpl(panel);
  if (!threadEntries.length) {
    recordThreadRenderImpl({
      panelId: panel?.panelId || null,
      messagesSeen: 0,
      branch: "picker",
      at: new Date().toISOString(),
    });
    renderShowEarlierMessages(panel, olderMount, 0, deps);
    clearNode(messagesMount);
    messagesMount.style.display = "none";
    const threadState = ensureThreadRenderState(panel);
    threadState.renderedKeyOrder = [];
    threadState.bubbleMap = {};
    threadState.forceScrollOnNextRender = true;
    threadState.signatures = {};
    threadState.lastVisibleKeySet = null;
    clearNode(emptyMount);
    if (panel.state.chatError) {
      const errEl = el("div", `Chat unavailable: ${panel.state.chatError}`);
      errEl.style.color = "#ffb86c";
      errEl.style.fontSize = "11px";
      emptyMount.appendChild(errEl);
    }
    renderWelcomeExamples(emptyMount, deps);
    emptyMount.style.display = "grid";
    return false;
  }

  emptyMount.style.display = "none";
  messagesMount.style.display = "grid";
  clearNode(emptyMount);
  const { displayEntries, hiddenCount } = computeThreadDisplayEntries(panel, threadEntries);
  recordThreadRenderImpl({
    panelId: panel?.panelId || null,
    messagesSeen: threadEntries.length,
    branch: "messages",
    at: new Date().toISOString(),
  });
  renderShowEarlierMessages(panel, olderMount, hiddenCount, deps);
  reconcileChatBubblesImpl(panel, messagesMount, displayEntries, deps);
  return true;
}

// ── Scroll-follow helpers ─────────────────────────────────────────────────

export function scrollChatThreadToBottom(panel) {
  const container = panel?.thread;
  if (!container) {
    return;
  }
  const target = Number.isFinite(container.scrollHeight)
    ? container.scrollHeight
    : Math.max(0, (container.children?.length || 0) * 100);
  container.scrollTop = target;
  container.dataset.vibecomfyScrolledToBottom = "1";
}

export function isChatThreadNearBottom(panel) {
  const container = panel?.thread;
  if (!container) {
    return true;
  }
  const scrollHeight = Number(container.scrollHeight);
  const clientHeight = Number(container.clientHeight);
  const scrollTop = Number(container.scrollTop);
  if (Number.isFinite(scrollHeight) && Number.isFinite(clientHeight) && Number.isFinite(scrollTop)) {
    const distanceFromBottom = scrollHeight - clientHeight - scrollTop;
    return distanceFromBottom <= THREAD_NEAR_BOTTOM_TOLERANCE_PX;
  }
  return container.dataset?.vibecomfyScrolledToBottom === "1";
}

// ── Chat thread mounts (reusable DOM scaffolding for the chat region) ────

function ensureChatThreadMounts(body, deps = {}) {
  const { el, appendChildOnce } = deps;
  const mounts = {
    sessionRow: [],
    olderMount: [],
    messagesMount: [],
    emptyMount: [],
    activityMount: [],
  };
  for (const child of Array.from(body.children || [])) {
    if (child?.dataset?.vibecomfyChatSessionRow === "1") {
      mounts.sessionRow.push(child);
    } else if (child?.dataset?.vibecomfyChatOlderMount === "1") {
      mounts.olderMount.push(child);
    } else if (child?.dataset?.vibecomfyChatMessages === "1") {
      mounts.messagesMount.push(child);
    } else if (child?.dataset?.vibecomfyChatEmpty === "1") {
      mounts.emptyMount.push(child);
    } else if (child?.dataset?.vibecomfyChatActivity === "1") {
      mounts.activityMount.push(child);
    }
  }
  let sessionRow = mounts.sessionRow[0] || null;
  let olderMount = mounts.olderMount[0] || null;
  let messagesMount = mounts.messagesMount[0] || null;
  let emptyMount = mounts.emptyMount[0] || null;
  let activityMount = mounts.activityMount[0] || null;
  for (const list of Object.values(mounts)) {
    for (const duplicate of list.slice(1)) {
      if (duplicate?.parentNode === body) {
        body.removeChild(duplicate);
      }
    }
  }
  Object.assign(body.style, {
    display: "flex",
    flexDirection: "column",
    flex: "1 1 auto",
    minHeight: "0",
  });
  if (!sessionRow) {
    sessionRow = el("div");
    sessionRow.dataset.vibecomfyChatSessionRow = "1";
    Object.assign(sessionRow.style, {
      display: "none",
      alignItems: "center",
      gap: "6px",
      marginBottom: "8px",
      paddingBottom: "6px",
      borderBottom: "1px solid #282a32",
      minWidth: "0",
      maxWidth: "100%",
    });
  }
  if (!messagesMount) {
    messagesMount = el("div");
    messagesMount.dataset.vibecomfyChatMessages = "1";
    Object.assign(messagesMount.style, {
      display: "grid",
      flex: "1 1 auto",
      gap: "6px",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
      minHeight: "100%",
      alignContent: "start",
      alignItems: "start",
    });
  }
  if (!emptyMount) {
    emptyMount = el("div");
    emptyMount.dataset.vibecomfyChatEmpty = "1";
    Object.assign(emptyMount.style, {
      display: "none",
      flex: "1 1 auto",
      gap: "6px",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
      minHeight: "100%",
      alignContent: "center",
      justifyItems: "center",
    });
  }
  if (!olderMount) {
    olderMount = el("div");
    olderMount.dataset.vibecomfyChatOlderMount = "1";
    Object.assign(olderMount.style, {
      display: "none",
      marginBottom: "6px",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
    });
  }
  if (!activityMount) {
    activityMount = el("div");
    activityMount.dataset.vibecomfyChatActivity = "1";
    Object.assign(activityMount.style, {
      display: "none",
      marginTop: "8px",
      paddingTop: "8px",
      borderTop: "1px solid #282a32",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
    });
  }
  sessionRow.dataset.vibecomfyChatSessionRow = "1";
  olderMount.dataset.vibecomfyChatOlderMount = "1";
  messagesMount.dataset.vibecomfyChatMessages = "1";
  activityMount.dataset.vibecomfyChatActivity = "1";
  emptyMount.dataset.vibecomfyChatEmpty = "1";
  messagesMount.style.flex = "1 1 auto";
  messagesMount.style.minHeight = "100%";
  messagesMount.style.minWidth = "0";
  messagesMount.style.alignContent = "start";
  messagesMount.style.alignItems = "start";
  emptyMount.style.flex = "1 1 auto";
  emptyMount.style.minHeight = "100%";
  emptyMount.style.minWidth = "0";
  appendChildOnce(body, sessionRow);
  appendChildOnce(body, olderMount);
  appendChildOnce(body, messagesMount);
  appendChildOnce(body, activityMount);
  appendChildOnce(body, emptyMount);
  return { sessionRow, olderMount, messagesMount, emptyMount, activityMount };
}

function renderChatSessionLink(sessionRow, panel, deps = {}) {
  const { clearNode } = deps;
  // The session path/link is intentionally not surfaced at the top of the chat.
  clearNode(sessionRow);
  sessionRow.style.display = "none";
}

function renderShowEarlierMessages(panel, olderMount, hiddenCount, deps = {}) {
  const { button, clearNode, ensureThreadRenderState, markAgentPanelDirty, renderAgentPanel, RENDER_SECTIONS } = deps;
  if (!olderMount) {
    return;
  }
  if (!Number.isFinite(hiddenCount) || hiddenCount <= 0) {
    clearNode(olderMount);
    olderMount.style.display = "none";
    return;
  }
  clearNode(olderMount);
  const showEarlierButton = button("Show earlier messages", () => {
    const threadState = ensureThreadRenderState(panel);
    if (threadState.expandedOlder) {
      return;
    }
    threadState.expandedOlder = true;
    markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
    renderAgentPanel(panel, { dirtySections: [RENDER_SECTIONS.THREAD] });
  });
  showEarlierButton.dataset.vibecomfyShowEarlierMessages = "1";
  showEarlierButton.title = `${hiddenCount} earlier message${hiddenCount === 1 ? "" : "s"} hidden`;
  Object.assign(showEarlierButton.style, {
    padding: "4px 8px",
    fontSize: "10px",
    lineHeight: "1.3",
  });
  olderMount.appendChild(showEarlierButton);
  olderMount.style.display = "block";
}

function renderWelcomeExamples(body, deps = {}) {
  const { currentAgentPanel, el } = deps;
  const welcome = el("div");
  Object.assign(welcome.style, {
    border: "1px solid #2d6fb5",
    borderRadius: "6px",
    background: "#111722",
    padding: "10px",
    display: "grid",
    gap: "6px",
  });
  const heading = el("div", "Try an example");
  Object.assign(heading.style, {
    fontSize: "11px",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#9da1ac",
    fontWeight: "600",
    marginBottom: "2px",
  });
  welcome.appendChild(heading);

  const examplePrompts = [
    "Add a code node that processes images with PIL",
    "Explain what's happening in this workflow in depth",
    "Make the prompts more specific",
    "Reorganise this workflow",
    "Improve this workflow so it's cleaner, more reliable, and easier to understand",
  ];
  for (const example of examplePrompts) {
    const row = el("div", example);
    Object.assign(row.style, {
      fontSize: "11px",
      color: "#9ed0ff",
      cursor: "pointer",
      padding: "4px 8px",
      borderRadius: "4px",
      background: "#0a1628",
      border: "1px solid #1e3355",
    });
    row.onclick = () => {
      const panel = currentAgentPanel();
      if (panel?.fields?.prompt) {
        panel.fields.prompt.value = example;
        panel.fields.prompt.focus();
      }
    };
    welcome.appendChild(row);
  }
  body.appendChild(welcome);
}

// ── Activity row rendering (live turn progress) ───────────────────────────

const VC_COLORS = Object.freeze({
  active: "#f47f18",
  success: "#4caf50",
  warning: "#ffc107",
  error: "#ff7f7f",
  muted: "#6b7080",
  pending: "#f47f18",
});

const DURABLE_STATUS_COLORS = Object.freeze({
  pending: "#ffd36f",
  candidate: "#7db6ff",
  applied: "#4caf50",
  rejected: "#ff7f7f",
  failed: "#ff8d8d",
});

function _statusColor(status) {
  return DURABLE_STATUS_COLORS[status] || VC_COLORS.muted;
}

function _truncateMessage(text, maxLen = 80) {
  if (typeof text !== "string" || !text) return null;
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return null;
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen - 1) + "\u2026" : cleaned;
}

function _statementBullet(stmt, index, deps = {}) {
  const { el } = deps;
  const row = el("div");
  Object.assign(row.style, {
    display: "flex",
    alignItems: "flex-start",
    gap: "4px",
    fontSize: "11px",
    lineHeight: "1.35",
    marginBottom: "2px",
  });

  const landed = stmt.landed;
  const ok = stmt.ok;
  const statusIcon = landed ? "\u2713" : (ok === false ? "\u2717" : "\u25cb");
  const statusColor = landed ? VC_COLORS.success : (ok === false ? VC_COLORS.error : VC_COLORS.muted);
  const badge = el("span", statusIcon);
  Object.assign(badge.style, {
    color: statusColor,
    fontWeight: "700",
    minWidth: "12px",
    textAlign: "center",
  });
  row.appendChild(badge);

  const actionLabel = formatStatementAction(stmt);
  const kindEl = el("span", `${actionLabel}${Number.isFinite(stmt.statement_index) ? ` #${stmt.statement_index}` : ""}`);
  kindEl.style.color = "#9da1ac";
  row.appendChild(kindEl);

  const targetText =
    (typeof stmt.field_path === "string" && stmt.field_path)
    || (typeof stmt.target === "string" && stmt.target)
    || (typeof stmt.target_field === "string" && stmt.target_field)
    || null;
  if (targetText) {
    const targetEl = el("span", targetText);
    targetEl.style.color = "#c4ccd6";
    targetEl.style.fontSize = "10px";
    targetEl.style.marginLeft = "2px";
    targetEl.style.overflowWrap = "anywhere";
    row.appendChild(targetEl);
  }

  if (Array.isArray(stmt.diagnostics) && stmt.diagnostics.length) {
    const firstDiag = stmt.diagnostics[0];
    if (firstDiag && typeof firstDiag === "object") {
      const code = typeof firstDiag.code === "string" ? firstDiag.code : "";
      const msg = typeof firstDiag.message === "string" ? firstDiag.message : "";
      const diagText = code && msg ? `${code}: ${msg}` : (code || msg);
      if (diagText) {
        const diagEl = el("span", _truncateMessage(diagText, 50) || diagText);
        diagEl.style.color = "#8d93a1";
        diagEl.style.fontSize = "10px";
        diagEl.style.marginLeft = "4px";
        row.appendChild(diagEl);
      }
    }
  }

  return row;
}

function _injectProgressPulseStyle(deps = {}) {
  const { getAgentPanelRuntime, el } = deps;
  const runtime = getAgentPanelRuntime();
  if (runtime._progressPulseInjected) return;
  runtime._progressPulseInjected = true;
  const style = el("style");
  style.textContent = `
    @keyframes vibecomfy-progress-pulse {
      0%, 100% { opacity: 0.35; }
      50% { opacity: 1; }
    }
    .vibecomfy-batch-progress-dot {
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #f47f18;
      animation: vibecomfy-progress-pulse 1.2s ease-in-out infinite;
      margin-right: 4px;
      vertical-align: middle;
    }
    @keyframes vibecomfy-working-dots {
      0%, 20% { content: ""; }
      40% { content: "."; }
      60% { content: ".."; }
      80%, 100% { content: "..."; }
    }
    .vibecomfy-working-dots::after {
      content: "";
      animation: vibecomfy-working-dots 1.4s steps(1, end) infinite;
      display: inline-block;
      width: 1.1em;
      text-align: left;
    }
  `;
  if (typeof document !== "undefined" && document?.head) {
    document.head.appendChild(style);
  }
}

// Format an ISO timestamp as a short relative string ("just now", "5 minutes
// ago", "3 hours ago", "2 days ago"). Returns null for missing/unparseable
// input so callers can skip the line entirely.
function _formatRelativeTime(iso) {
  if (typeof iso !== "string" || !iso) return null;
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return null;
  const diffMs = Date.now() - then;
  const sec = Math.floor(diffMs / 1000);
  if (sec < 45) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} minute${min === 1 ? "" : "s"} ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hour${hr === 1 ? "" : "s"} ago`;
  const day = Math.floor(hr / 24);
  return `${day} day${day === 1 ? "" : "s"} ago`;
}

// Render canonical activity details into the expanded view.
function _renderCanonicalDetails(container, canonical, deps = {}) {
  const { el } = deps;
  const details = canonical.details;
  if (!Array.isArray(details)) return;

  for (const detail of details) {
    if (!detail || typeof detail !== "object") continue;

    if (detail.kind === "statements") {
      const stmtsHeader = el("div", "Turn details:");
      stmtsHeader.style.fontSize = "10px";
      stmtsHeader.style.color = "#9da1ac";
      stmtsHeader.style.textTransform = "uppercase";
      stmtsHeader.style.letterSpacing = "0.04em";
      container.appendChild(stmtsHeader);
      const items = Array.isArray(detail.items) ? detail.items : [];
      for (let s = 0; s < items.length; s += 1) {
        const stmt = items[s];
        if (stmt && typeof stmt === "object") {
          container.appendChild(_statementBullet(stmt, s, deps));
        }
      }
      const shown = typeof detail.shown === "number" ? detail.shown : items.length;
      const total = typeof detail.total === "number" ? detail.total : shown;
      if (total > shown) {
        const moreLine = el("div", `+${total - shown} more statement${total - shown !== 1 ? "s" : ""}\u2026`);
        moreLine.style.fontSize = "10px";
        moreLine.style.color = "#8d93a1";
        moreLine.style.fontStyle = "italic";
        container.appendChild(moreLine);
      }
    }

    if (detail.kind === "counts") {
      const parts = [];
      if (typeof detail.total === "number" && detail.total > 0) parts.push(`${detail.total} statements`);
      if (typeof detail.landed_ops === "number" && detail.landed_ops > 0) parts.push(`${detail.landed_ops} landed`);
      if (detail.landed && typeof detail.landed === "number" && detail.landed > 0) parts.push(`${detail.landed} landed`);
      if (parts.length) {
        const countsLine = el("div", parts.join(" \u00b7 "));
        countsLine.style.fontSize = "10px";
        countsLine.style.color = "#8d93a1";
        container.appendChild(countsLine);
      }
    }

    if (detail.kind === "budget") {
      const budgetParts = [];
      if (typeof detail.remaining_batches === "number") budgetParts.push(`${detail.remaining_batches} turns left`);
      if (typeof detail.consecutive_errors === "number") budgetParts.push(`errors: ${detail.consecutive_errors}`);
      if (budgetParts.length) {
        const budgetLine = el("div", budgetParts.join(" \u00b7 "));
        budgetLine.style.fontSize = "10px";
        budgetLine.style.color = "#8d93a1";
        budgetLine.style.fontStyle = "italic";
        container.appendChild(budgetLine);
      }
    }

    if (detail.kind === "timing") {
      const timingParts = [];
      if (typeof detail.turn_elapsed_ms === "number") timingParts.push(`${(detail.turn_elapsed_ms / 1000).toFixed(1)}s`);
      if (typeof detail.model_elapsed_ms === "number") timingParts.push(`model ${(detail.model_elapsed_ms / 1000).toFixed(1)}s`);
      if (timingParts.length) {
        const timingLine = el("div", timingParts.join(" \u00b7 "));
        timingLine.style.fontSize = "10px";
        timingLine.style.color = "#8d93a1";
        container.appendChild(timingLine);
      }
    }
  }

  // Render diagnostics from canonical state (separate from details entries).
  if (Array.isArray(canonical.diagnostics) && canonical.diagnostics.length) {
    _renderDiagnostics(container, canonical.diagnostics, deps);
  }
}

// Shared diagnostics renderer used by both canonical and raw paths.
function _renderDiagnostics(container, diagnostics, deps = {}) {
  const { el } = deps;
  if (!Array.isArray(diagnostics) || !diagnostics.length) return;
  const diagHeader = el("div", "Diagnostics:");
  diagHeader.style.fontSize = "10px";
  diagHeader.style.color = "#9da1ac";
  diagHeader.style.textTransform = "uppercase";
  diagHeader.style.letterSpacing = "0.04em";
  container.appendChild(diagHeader);
  const maxDiags = Math.min(diagnostics.length, 5);
  for (let d = 0; d < maxDiags; d += 1) {
    const diag = diagnostics[d];
    if (diag && typeof diag === "object") {
      const code = typeof diag.code === "string" ? diag.code : "";
      const msg = typeof diag.message === "string" ? diag.message : "";
      const diagText = code && msg ? `${code}: ${msg}` : (code || msg);
      if (diagText) {
        const diagLine = el("div", diagText);
        diagLine.style.fontSize = "10px";
        diagLine.style.color = "#8d93a1";
        container.appendChild(diagLine);
      }
    }
  }
}

function _renderDurableTurnRow(body, panel, entry, index, deps = {}) {
  const { appendTextLine, button, el, downloadTurnAudit } = deps;
  const turnCard = el("div");
  turnCard.style.borderLeft = "3px solid #f47f18";
  turnCard.style.paddingLeft = "8px";
  turnCard.style.marginBottom = "8px";
  turnCard.style.display = "grid";
  turnCard.style.gap = "4px";

  // A pending durable row is the in-flight placeholder shown while a turn is
  // working — animate it (pulsing dot + "WORKING…" with cycling dots) so it
  // reads as live progress instead of a static "PENDING" badge.
  const isPending = entry.status === "pending";
  if (isPending) {
    _injectProgressPulseStyle(deps);
  }
  const statusColor = isPending ? (DURABLE_STATUS_COLORS.pending || "#f47f18") : _statusColor(entry.status);

  const headerRow = el("div");
  headerRow.style.display = "flex";
  headerRow.style.justifyContent = "space-between";
  headerRow.style.alignItems = "center";
  headerRow.style.gap = "8px";

  const statusGroup = el("div");
  statusGroup.style.display = "flex";
  statusGroup.style.alignItems = "center";
  if (isPending) {
    const dot = el("span");
    dot.className = "vibecomfy-batch-progress-dot";
    dot.style.background = statusColor;
    statusGroup.appendChild(dot);
  }

  const statusBadge = el("span", isPending ? "in progress" : (entry.status || "unknown"));
  statusBadge.style.color = statusColor;
  statusBadge.style.fontWeight = "700";
  statusBadge.style.textTransform = "uppercase";
  statusBadge.style.fontSize = "10px";
  statusBadge.style.letterSpacing = "0.05em";
  statusGroup.appendChild(statusBadge);
  headerRow.appendChild(statusGroup);

  const downloadBtn = button("Audit \u2193", () => downloadTurnAudit(panel, index));
  downloadBtn.style.fontSize = "10px";
  downloadBtn.style.padding = "3px 6px";
  headerRow.appendChild(downloadBtn);

  turnCard.appendChild(headerRow);

  if (entry.turn_id && !isPending) {
    appendTextLine(turnCard, `turn ${entry.turn_id}`, "#8d93a1");
  }
  // While a turn is in progress the user's own message bubble is shown directly
  // above this row, so echoing entry.task here just repeats it. Only show the
  // task on terminal rows, where it identifies which past turn the row is.
  if (entry.task && !isPending) {
    appendTextLine(turnCard, entry.task, "#edf2f7");
  }
  if (entry.failure_kind) {
    appendTextLine(turnCard, `${entry.failure_kind}${entry.failure_stage ? ` @ ${entry.failure_stage}` : ""}`, "#ffb86c");
  }
  // Skip the "Submitting: <task>" message — it just echoes entry.task shown
  // above, so it reads as a duplicate. Real messages (errors) still render.
  const isSubmittingEcho = typeof entry.message === "string"
    && /^\s*submitting:/i.test(entry.message);
  if (entry.message && !isSubmittingEcho) {
    appendTextLine(turnCard, entry.message, "#9da1ac");
  }
  const relTime = _formatRelativeTime(entry.timestamp);
  if (relTime) {
    const timeLine = el("div", relTime);
    timeLine.style.fontSize = "9px";
    timeLine.style.color = "#6b7080";
    timeLine.style.textAlign = "right";
    timeLine.title = entry.timestamp; // exact timestamp on hover
    turnCard.appendChild(timeLine);
  }

  body.appendChild(turnCard);
}

export function populateActivityRows(body, _panel, _opts = {}, deps = {}) {
  const { clearNode } = deps;
  if (typeof clearNode === "function") {
    clearNode(body);
  } else if (body) {
    body.textContent = "";
  }
}

function renderActivityRows(panel, deps = {}) {
  const mount = panel?.sections?.history;
  if (!mount) {
    return;
  }
  const hasPendingResponse = selectTranscriptMessages(panel).some((message) => (
    message?.role === "agent"
    && isPendingAgentMessage(message)
  ));
  if (hasPendingResponse) {
    deps.clearNode?.(mount);
    mount.style.display = "none";
    if (mount.parentNode?.className === "vibecomfy-agent-panel-region") {
      mount.parentNode.style.display = "none";
    }
    return;
  }
  populateActivityRows(mount, panel, {}, deps);
  const hasContent = mount.children.length > 0;
  mount.style.display = hasContent ? "" : "none";
  if (mount.parentNode?.className === "vibecomfy-agent-panel-region") {
    mount.parentNode.style.display = hasContent ? "" : "none";
  }
}

// ── History rendering (bubble list + activity + scroll-follow) ────────────

function renderHistory(panel, deps = {}) {
  const { ensureThreadRenderState } = deps;
  const threadState = ensureThreadRenderState(panel);

  // Capture the auto-scroll decision BEFORE any DOM mutation from
  // renderChatThread (bubble reconciliation). This preserves whether
  // the user was scrolled near the bottom at the moment rendering started.
  const shouldAutoScroll = Boolean(threadState.forceScrollOnNextRender) || isChatThreadNearBottom(panel);

  const hasMessages = renderChatThread(panel, deps);

  if (hasMessages && shouldAutoScroll) {
    scrollChatThreadToBottom(panel);
    threadState.forceScrollOnNextRender = false;
  } else if (panel?.thread) {
    panel.thread.dataset.vibecomfyScrolledToBottom = "0";
  }
}
