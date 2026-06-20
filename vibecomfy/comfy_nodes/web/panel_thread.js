import { getAgentPanelRuntime } from "./panel_runtime.js";
import { renderMarkdown } from "./markdown.js";
import {
  formatActivityHeadline,
  formatOutcomeCounts,
  formatStatementAction,
  isSubstantiveStatement,
} from "./agent_turn_feed.js";

const THREAD_WINDOW_SIZE = 30;
const THREAD_NEAR_BOTTOM_TOLERANCE_PX = 120;
const RATING_WIDGET_CLEAR_DELAY_MS = 2400;
const RATING_WIDGET_EXPIRY_MS = 120000;
const RATING_PACK_SHARE_DEFAULT_LS_KEY = "vibecomfy_pack_share_default";
const RATING_WIDGET_DISABLED_LS_KEY = "vibecomfy_rating_widget_disabled";

export function collectThreadMessageEntries(panel, deps = {}) {
  const { buildSyntheticAgentMessage, messageStableKey } = deps;
  const threadMessages = Array.isArray(panel?.state?.chatMessages)
    ? panel.state.chatMessages.slice()
    : [];
  const syntheticAgentMessage = typeof buildSyntheticAgentMessage === "function"
    ? buildSyntheticAgentMessage(panel)
    : null;
  if (syntheticAgentMessage) {
    threadMessages.push(syntheticAgentMessage);
  }
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
  runtime.lastThreadRender = runtimePayload;
  runtime._lastThreadRender = runtimePayload;
  return runtime.lastThreadRender;
}

function bubbleDetailSignature(msg, detailSnapshot) {
  const canonicalDetails = Array.isArray(msg?.canonical_activity?.details)
    ? String(msg.canonical_activity.details.length)
    : "";
  const canonicalDiagnostics = Array.isArray(msg?.canonical_activity?.diagnostics)
    ? String(msg.canonical_activity.diagnostics.length)
    : "";
  const detailSigParts = [
    detailSnapshot?.phase || "",
    detailSnapshot?.message || "",
    detailSnapshot?.auditRef?.path || "",
    detailSnapshot?.changeDetails?.done_summary || msg?.change_details?.done_summary || "",
    Array.isArray(detailSnapshot?.fieldChanges) ? String(detailSnapshot.fieldChanges.length) : "",
    Array.isArray(msg?.field_changes) ? String(msg.field_changes.length) : "",
    canonicalDetails,
    canonicalDiagnostics,
    msg?.turn_id || "",
    msg?.detail_turn_id || "",
    String(msg?.text || "").slice(0, 80),
  ];
  return detailSigParts.join("|");
}

function bubbleRenderSignature(panel, msg, deps = {}) {
  const { candidateActionState, detailSnapshotForMessage, latestAgentMessageKey, messageKey, messageSignature } = deps;
  const snapshot = typeof detailSnapshotForMessage === "function"
    ? detailSnapshotForMessage(panel, msg)
    : null;
  const actionState = typeof candidateActionState === "function"
    ? candidateActionState(panel, msg, snapshot)
    : {};
  const responseId = ratingResponseIdForMessage(panel, msg);
  const ratingState = responseId ? getRatingResponseState(panel, responseId) : null;
  const signatureParts = [
    typeof messageSignature === "function" ? messageSignature(msg) : "",
    snapshot?.phase || "",
    snapshot?.message || "",
    snapshot?.auditRef?.path || "",
    snapshot?.changeDetails?.done_summary || msg?.change_details?.done_summary || "",
    Array.isArray(snapshot?.fieldChanges) ? String(snapshot.fieldChanges.length) : "",
    Array.isArray(msg?.field_changes) ? String(msg.field_changes.length) : "",
    actionState.turnId || "",
    actionState.eligibility?.reason || "",
    actionState.eligibility?.message || "",
    actionState.active ? "1" : "0",
    actionState.applyDisabled ? "1" : "0",
    actionState.rejectDisabled ? "1" : "0",
    String(messageKey || "") === String(latestAgentMessageKey || "") ? "rating-latest" : "",
    deps.ratingHasLaterUserOrPending ? "rating-blocked-by-next-turn" : "",
    responseId || "",
    isRatingResponseSubmitted(panel, responseId) ? "rating-submitted" : "",
    Number.isFinite(ratingState?.rating) ? `rating-${ratingState.rating}` : "",
    ratingWidgetDisabled(panel, deps) ? "rating-disabled" : "",
    panel?.state?.turnId || "",
    (msg?.pending_response || msg?.executor_pending) ? "pending-response" : "",
    msg?.progress ? JSON.stringify(msg.progress) : "",
    msg?.progress_label || "",
    Array.isArray(msg?.canonical_activity?.details) ? String(msg.canonical_activity.details.length) : "",
    Array.isArray(msg?.canonical_activity?.diagnostics) ? String(msg.canonical_activity.diagnostics.length) : "",
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
  if (!(msg?.pending_response || msg?.executor_pending) || typeof el !== "function") {
    return null;
  }
  // Prefer canonical activity phase_progress from the message (set by
  // updatePendingResponseProgress in vibecomfy_roundtrip.js), then fall
  // back to panel.state.executorProgress which is also derived from
  // canonical activity state.
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
  row.dataset.vibecomfyPhaseSource = "canonical";
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
    if (
      msg?.role === "user"
      || msg?.pending_response === true
      || msg?.executor_pending === true
    ) {
      return true;
    }
  }
  return false;
}

function shouldRenderRatingWidget(panel, msg, messageKey, deps = {}) {
  if (msg?.role !== "agent") {
    return false;
  }
  if (msg?.pending_response || msg?.executor_pending) {
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

  const fieldChanges = message?.field_changes || snapshot?.fieldChanges;
  if (fieldChanges && typeof fieldChanges === "object") {
    const directChanges = Array.isArray(fieldChanges.directChanges) ? fieldChanges.directChanges : [];
    const outcomeChanges = Array.isArray(fieldChanges.outcomeChanges) ? fieldChanges.outcomeChanges : [];
    const batchTurnChanges = Array.isArray(fieldChanges.batchTurnChanges) ? fieldChanges.batchTurnChanges : [];
    const allChanges = directChanges.concat(outcomeChanges, batchTurnChanges);
    if (allChanges.length > 0) {
      appendTextLine(target, allChanges.map(function (change) {
        if (!change || typeof change.field_path !== "string") {
          return "";
        }
        const nextValue =
          typeof change.new_value !== "undefined"
            ? change.new_value
            : change.new;
        return `${change.field_path}${typeof nextValue !== "undefined" ? ` -> ${String(nextValue).slice(0, 40)}` : ""}`;
      }).filter(Boolean).join("; "), "#c4ccd6");
    }
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
    appendAuditDetail,
    appendCandidateDetail,
    appendDebugDetail,
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

  const isExecutorMessage = message?.pending_response === true || message?.executor_pending === true || message?.source === "agent-edit";
  if (!isExecutorMessage) {
    const metaSection = createBubbleDetailSection("Turn");
    appendTurnMeta(metaSection.body, panel, message, snapshot, { appendTextLine, el });
    target.appendChild(metaSection.section);
  }

  const changeDetails = changeDetailsForMessage(panel, message, snapshot);
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
    changesSection.body.appendChild(createDetails("full change details", changeDetails));
    target.appendChild(changesSection.section);
  }

  const canonicalActivity = message?.canonical_activity && typeof message.canonical_activity === "object"
    ? message.canonical_activity
    : null;
  if (
    canonicalActivity
    && (
      (Array.isArray(canonicalActivity.details) && canonicalActivity.details.length)
      || (Array.isArray(canonicalActivity.diagnostics) && canonicalActivity.diagnostics.length)
    )
  ) {
    const activitySection = createBubbleDetailSection("Progress");
    _renderCanonicalDetails(activitySection.body, canonicalActivity, deps);
    if (activitySection.body.children.length) {
      target.appendChild(activitySection.section);
    }
  }

  const candidateSection = createBubbleDetailSection("Candidate");
  appendCandidateDetail(candidateSection.body, panel, message, snapshot);
  if (candidateSection.body.children.length) {
    target.appendChild(candidateSection.section);
  }

  const failureSection = createBubbleDetailSection("Failure");
  appendFailureDetail(failureSection.body, panel, snapshot);
  if (failureSection.body.children.length) {
    target.appendChild(failureSection.section);
  }

  const queueSection = createBubbleDetailSection("Queue");
  appendQueueDetail(queueSection.body, panel, snapshot);
  if (queueSection.body.children.length) {
    target.appendChild(queueSection.section);
  }

  const auditSection = createBubbleDetailSection("Audit");
  appendAuditDetail(auditSection.body, panel, message, snapshot);
  if (auditSection.body.children.length) {
    target.appendChild(auditSection.section);
  }

  const debugSection = createBubbleDetailSection("Debug");
  appendDebugDetail(debugSection.body, panel, snapshot);
  if (debugSection.body.children.length) {
    target.appendChild(debugSection.section);
  }
}

export function renderChatBubbleNode(bubble, panel, msg, messageKey, messageIndex, deps = {}) {
  const {
    candidateActionState,
    clearNode,
    detailSnapshotForMessage,
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

  const isPendingResponse = msg?.pending_response === true || msg?.executor_pending === true;
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
  const detailSnapshot = typeof detailSnapshotForMessage === "function"
    ? detailSnapshotForMessage(panel, msg)
    : null;
  const detailSignature = bubbleDetailSignature(msg, detailSnapshot);
  const detailRow = el("div");
  Object.assign(detailRow.style, {
    marginTop: "3px",
    fontSize: "10px",
    maxWidth: "100%",
    minWidth: "0",
    overflowWrap: "anywhere",
  });

  const detailToggle = el("span", "\u25b6 details");
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
    const lastThreadRender = recordThreadRenderImpl({
      panelId: panel?.panelId || null,
      messagesSeen: 0,
      branch: "picker",
      at: new Date().toISOString(),
    });
    if (panel) {
      panel.lastThreadRender = lastThreadRender;
    }
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
  const lastThreadRender = recordThreadRenderImpl({
    panelId: panel?.panelId || null,
    messagesSeen: threadEntries.length,
    branch: "messages",
    at: new Date().toISOString(),
  });
  if (panel) {
    panel.lastThreadRender = lastThreadRender;
  }
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
    "Connect the output of LoadImage to a PreviewImage node",
    "Replace the CLIPTextEncode prompt text with something new",
    "Add a VAE Decode after the sampler output",
    "Wire the model output into a SaveImage node",
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

const BATCH_STATUS_COLORS = Object.freeze({
  in_progress: "#f47f18",
  progress: "#f47f18",
  clarify: "#ffc107",
  done: "#4caf50",
  budget_exhausted: "#ffc107",
});

const DURABLE_STATUS_COLORS = Object.freeze({
  pending: "#ffd36f",
  candidate: "#7db6ff",
  applied: "#4caf50",
  rejected: "#ff7f7f",
  failed: "#ff8d8d",
});

function _statusColor(status) {
  return DURABLE_STATUS_COLORS[status] || BATCH_STATUS_COLORS[status] || VC_COLORS.muted;
}

const ACTIVITY_TERMINAL_STATUSES = new Set([
  "applied",
  "budget_exhausted",
  "cancelled",
  "candidate",
  "clarify",
  "done",
  "error",
  "failed",
  "noop",
  "rejected",
  "undone",
]);

function isLiveActivityTurn(entry) {
  if (!entry || typeof entry !== "object") {
    return false;
  }
  const status = typeof entry.status === "string" && entry.status ? entry.status : null;
  if (!status || ACTIVITY_TERMINAL_STATUSES.has(status)) {
    return false;
  }
  return entry.entry_type === "batch" || entry.entry_type === "durable";
}

function _truncateMessage(text, maxLen = 80) {
  if (typeof text !== "string" || !text) return null;
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return null;
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen - 1) + "\u2026" : cleaned;
}

function _safeSummaryText(entry) {
  if (typeof entry.done_summary === "string" && entry.done_summary.trim()) {
    return entry.done_summary.trim();
  }
  if (typeof entry.clarification_message === "string" && entry.clarification_message.trim()) {
    return entry.clarification_message.trim();
  }
  const hints = [];
  if (Array.isArray(entry.statements)) {
    for (const stmt of entry.statements) {
      if (stmt && typeof stmt.teaching_hint === "string" && stmt.teaching_hint.trim()) {
        hints.push(stmt.teaching_hint.trim());
      }
    }
  }
  return hints.length ? hints.join(" | ") : null;
}

const BATCH_STATEMENT_CAP = 5;

function _batchTurnDisplayStatus(entry) {
  const status = typeof entry?.status === "string" ? entry.status : "";
  // Answer-only / no-graph-changes turns display as "answered" rather than
  // the generic "turn done" so users can distinguish edit turns from
  // terminal information-only responses.
  if (status === "done" && _isAnswerOnlyTurn(entry)) {
    return "answered";
  }
  if (status === "done") {
    return "turn done";
  }
  if (status === "clarify") {
    return "needs input";
  }
  if (status === "budget_exhausted") {
    return "stopped";
  }
  if (status === "in_progress" || status === "progress") {
    return "working";
  }
  return status || "working";
}

function _latestLiveBatchTurn(panel, sessionId = null) {
  const turns = Array.isArray(panel?.state?.turns) ? panel.state.turns : [];
  const currentSessionId =
    (typeof sessionId === "string" && sessionId)
    || (typeof panel?.state?.sessionId === "string" && panel.state.sessionId)
    || null;
  for (const entry of turns) {
    if (entry?.entry_type !== "batch") {
      continue;
    }
    if (currentSessionId && entry.session_id && entry.session_id !== currentSessionId) {
      continue;
    }
    if (ACTIVITY_TERMINAL_STATUSES.has(entry.status)) {
      continue;
    }
    return entry;
  }
  return null;
}

function _compactStatementStatus(stmt) {
  if (!stmt || typeof stmt !== "object") {
    return null;
  }
  const source = _truncateMessage(
    typeof stmt.source === "string" && stmt.source ? stmt.source : null,
    96,
  );
  const diagnostics = Array.isArray(stmt.diagnostics) ? stmt.diagnostics : [];
  let result = null;
  if (diagnostics.length) {
    const first = diagnostics[0];
    if (first && typeof first === "object") {
      result = _truncateMessage(first.message || first.code || null, 80);
    }
  } else if (stmt?.detail && typeof stmt.detail === "object") {
    const queryOutput = typeof stmt.detail.query_output === "string" ? stmt.detail.query_output.trim() : "";
    if (stmt.op_kind === "query" && !queryOutput) {
      result = "no matches";
    }
  }
  if (!result) {
    // Protocol terminators (done(), exit, etc.) are never "not landed" —
    // they signal turn completion, not a failed graph operation.
    if (!isSubstantiveStatement(stmt)) {
      result = null;
    } else if (stmt.landed === true) {
      result = "landed";
    } else if (stmt.ok === false) {
      result = "failed";
    } else if (stmt.landed === false) {
      result = "not landed";
    }
  }
  return { source, result };
}

function _renderLiveTurnSummary(panel, entry, deps = {}) {
  const { el } = deps;
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const turnKey = entry.turn_key;
  const expanded = !!(turnKey && panelStateExpanded(panel, entry));
  // Prefer canonical activity when available; fall back to raw entry.
  const canonical = entry.canonical_activity && typeof entry.canonical_activity === "object"
    ? entry.canonical_activity
    : null;
  const statusColor = _statusColor(entry.status);
  const turnLabel = Number.isFinite(entry.turn_number)
    ? `Turn ${entry.turn_number + 1}`
    : "Turn";

  const box = el("div");
  Object.assign(box.style, {
    display: "grid",
    gap: "4px",
    padding: "5px 6px",
    borderLeft: "2px solid #282a32",
    background: "#151820",
    cursor: "pointer",
  });
  box.onclick = function (event) {
    event.stopPropagation();
    toggleExpandedTurnKey(panel, entry, deps);
  };

  const header = el("div");
  Object.assign(header.style, {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    fontSize: "12px",
  });
  const chevron = el("span", expanded ? "\u25bc" : "\u25b6");
  chevron.style.color = "#8d93a1";
  chevron.style.fontSize = "9px";
  header.appendChild(chevron);
  const label = el("span", turnLabel);
  label.style.color = statusColor;
  label.style.fontWeight = "700";
  header.appendChild(label);
  box.appendChild(header);

  if (!expanded) {
    return box;
  }

  // Use canonical activity for latest action + summary when available.
  let latestSource = null;
  let latestResult = null;
  if (canonical && canonical.latest_substantive_statement && typeof canonical.latest_substantive_statement === "object") {
    const lss = canonical.latest_substantive_statement;
    latestSource = typeof lss.source === "string" ? lss.source : (typeof lss.message === "string" ? lss.message : null);
    if (lss.landed === true) latestResult = "landed";
    else if (lss.ok === false) latestResult = "failed";
    else if (lss.landed === false) latestResult = "not landed";
  } else {
    const statements = Array.isArray(entry.statements) ? entry.statements : [];
    const latestStatement = statements.length ? statements[statements.length - 1] : null;
    const statementStatus = _compactStatementStatus(latestStatement);
    latestSource = statementStatus?.source || null;
    latestResult = statementStatus?.result || null;
  }

  // Answer-only / no-graph-changes turns: override the result so done()
  // protocol statements never leak "not landed" in live summary rows.
  if (canonical && canonical.outcome && typeof canonical.outcome === "object") {
    const outcomeKind = canonical.outcome.kind;
    if (outcomeKind === "answered") {
      latestResult = null; // outcome summary already describes this
    }
  }

  if (latestSource) {
    const sourceLine = el("div", `latest: ${latestSource}`);
    sourceLine.style.fontSize = "11px";
    sourceLine.style.color = "#c4ccd6";
    sourceLine.style.overflowWrap = "anywhere";
    box.appendChild(sourceLine);
  }
  const active = entry.status === "in_progress" || entry.status === "progress";
  if (!active && latestResult) {
    const resultLine = el("div", `status: ${latestResult}`);
    resultLine.style.fontSize = "10px";
    resultLine.style.color = "#8d93a1";
    box.appendChild(resultLine);
  }
  // Use canonical outcome summary when available.
  let summary = null;
  if (canonical && canonical.outcome && typeof canonical.outcome === "object" && typeof canonical.outcome.summary === "string") {
    summary = canonical.outcome.summary;
  } else {
    summary = _safeSummaryText(entry);
  }
  if (summary) {
    const summaryLine = el("div", summary);
    summaryLine.style.fontSize = "11px";
    summaryLine.style.color = "#c4ccd6";
    summaryLine.style.whiteSpace = "pre-wrap";
    summaryLine.style.wordBreak = "break-word";
    box.appendChild(summaryLine);
  }
  // Render statement details from canonical when available.
  if (canonical && Array.isArray(canonical.details) && canonical.details.length) {
    // Extract statements-kind details entry for inline rendering
    for (const detail of canonical.details) {
      if (detail && detail.kind === "statements" && Array.isArray(detail.items)) {
        const stmtsHeader = el("div", "Turn details:");
        stmtsHeader.style.fontSize = "10px";
        stmtsHeader.style.color = "#9da1ac";
        stmtsHeader.style.textTransform = "uppercase";
        stmtsHeader.style.letterSpacing = "0.04em";
        box.appendChild(stmtsHeader);
        const items = detail.items;
        for (let s = 0; s < items.length; s += 1) {
          const stmt = items[s];
          if (stmt && typeof stmt === "object") {
            box.appendChild(_statementBullet(stmt, s, deps));
          }
        }
        break;
      }
    }
  } else {
    const rawStatements = Array.isArray(entry.statements) ? entry.statements : [];
    const showStmts = rawStatements.slice(0, BATCH_STATEMENT_CAP);
    if (showStmts.length) {
      const stmtsHeader = el("div", "Turn details:");
      stmtsHeader.style.fontSize = "10px";
      stmtsHeader.style.color = "#9da1ac";
      stmtsHeader.style.textTransform = "uppercase";
      stmtsHeader.style.letterSpacing = "0.04em";
      box.appendChild(stmtsHeader);
      for (let index = 0; index < showStmts.length; index += 1) {
        box.appendChild(_statementBullet(showStmts[index], index, deps));
      }
    }
  }
  return box;
}

function panelStateExpanded(panel, entry) {
  const turnKey = entry?.turn_key;
  return Boolean(turnKey && panel?.state?.expandedTurnKeys?.[turnKey]);
}

function toggleExpandedTurnKey(panel, entry, deps = {}) {
  const turnKey = entry?.turn_key;
  if (!panel?.state || !turnKey) {
    return;
  }
  if (!panel.state.expandedTurnKeys || typeof panel.state.expandedTurnKeys !== "object") {
    panel.state.expandedTurnKeys = {};
  }
  if (panel.state.expandedTurnKeys[turnKey]) {
    delete panel.state.expandedTurnKeys[turnKey];
  } else {
    panel.state.expandedTurnKeys[turnKey] = true;
  }
  renderHistory(panel, deps);
  renderActivityRows(panel, deps);
}

// ── Answer-only / no-graph-changes display helpers ─────────────────────

/**
 * Determine whether a batch turn entry represents an answer-only (no graph
 * changes) outcome, preferring the canonical derivation.
 */
function _isAnswerOnlyTurn(entry) {
  if (!entry || typeof entry !== "object") return false;
  const canonical = entry.canonical_activity;
  if (canonical && typeof canonical === "object") {
    const outcomeKind = canonical.outcome && typeof canonical.outcome === "object"
      ? canonical.outcome.kind
      : null;
    if (outcomeKind === "answered") return true;
  }
  return false;
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

function _renderOutcomeFooter(entry, deps = {}) {
  const { el } = deps;
  const parts = [];
  if (typeof entry.exit_mode === "string" && entry.exit_mode) {
    parts.push(`exit: ${entry.exit_mode}`);
  }
  if (entry.budget && typeof entry.budget === "object") {
    if (Number.isFinite(entry.budget.remaining_batches)) {
      parts.push(`${entry.budget.remaining_batches} turn${entry.budget.remaining_batches === 1 ? "" : "s"} left`);
    } else if (Number.isFinite(entry.budget.consecutive_errors)) {
      parts.push(`errors: ${entry.budget.consecutive_errors}`);
    }
  }
  if (typeof entry.batch_ok === "boolean") {
    parts.push(entry.batch_ok ? "ok" : "not ok");
  }
  if (!parts.length) return null;
  const footer = el("div", parts.join(" \u00b7 "));
  Object.assign(footer.style, {
    fontSize: "10px",
    color: "#8d93a1",
    marginTop: "4px",
    fontStyle: "italic",
  });
  return footer;
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
    .vibecomfy-batch-row {
      cursor: pointer;
      user-select: none;
      transition: background 0.15s;
    }
    .vibecomfy-batch-row:hover {
      background: #1a1d24;
    }
    .vibecomfy-batch-expanded {
      margin-top: 4px;
      padding-left: 4px;
      border-left: 2px solid #282a32;
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

function _renderBatchTurnRow(body, panel, entry, index, deps = {}) {
  const { button, el, downloadTurnAudit } = deps;
  const turnKey = entry.turn_key;
  const expanded = !!(panel.state.expandedTurnKeys && panel.state.expandedTurnKeys[turnKey]);
  // ── Canonical activity state (preferred over raw entry fields) ───────
  const canonical = entry.canonical_activity && typeof entry.canonical_activity === "object"
    ? entry.canonical_activity
    : null;
  const status = typeof entry.status === "string" ? entry.status : "unknown";
  const isInProgress = status === "in_progress" || status === "progress";
  const statusColor = _statusColor(status);
  const turnLabel = Number.isFinite(entry.turn_number)
    ? `Turn ${entry.turn_number + 1}`
    : (typeof entry.turn_id === "string" && entry.turn_id ? `turn ${entry.turn_id}` : "turn");

  const row = el("div");
  row.className = "vibecomfy-batch-row";
  row.dataset.vibecomfyActivitySource = canonical ? "canonical" : "raw";
  Object.assign(row.style, {
    borderLeft: `3px solid ${statusColor}`,
    paddingLeft: "8px",
    marginBottom: "6px",
    display: "grid",
    gap: "3px",
  });
  row.onclick = function () {
    if (!panel.state.expandedTurnKeys || typeof panel.state.expandedTurnKeys !== "object") {
      panel.state.expandedTurnKeys = {};
    }
    if (panel.state.expandedTurnKeys[turnKey]) {
      delete panel.state.expandedTurnKeys[turnKey];
    } else {
      panel.state.expandedTurnKeys[turnKey] = true;
    }
    renderHistory(panel, deps);
    renderActivityRows(panel, deps);
  };

  // ── Collapsed view (always visible) ──────────────────────────────────
  const collapsedLine = el("div");
  Object.assign(collapsedLine.style, {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    flexWrap: "wrap",
    fontSize: "12px",
  });

  if (isInProgress) {
    const dot = el("span");
    dot.className = "vibecomfy-batch-progress-dot";
    collapsedLine.appendChild(dot);
  }

  const labelEl = el("span", turnLabel);
  labelEl.style.color = statusColor;
  labelEl.style.fontWeight = "700";
  collapsedLine.appendChild(labelEl);

  const statusEl = el("span", _batchTurnDisplayStatus(entry));
  Object.assign(statusEl.style, {
    color: statusColor,
    fontSize: "9px",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    fontWeight: "600",
  });
  collapsedLine.appendChild(statusEl);

  // Use canonical formatting helpers for the short message.
  const shortMsg = _truncateMessage(formatActivityHeadline(canonical, entry), 80);
  if (shortMsg) {
    const msgEl = el("span", shortMsg);
    msgEl.style.color = "#9da1ac";
    msgEl.style.fontSize = "11px";
    msgEl.style.flex = "1 1 auto";
    msgEl.style.minWidth = "0";
    msgEl.style.overflow = "hidden";
    msgEl.style.textOverflow = "ellipsis";
    msgEl.style.whiteSpace = "nowrap";
    collapsedLine.appendChild(msgEl);
  }

  // Determine a "latest" source/action line from canonical or raw data.
  let latestSource = null;
  if (canonical && canonical.latest_substantive_statement && typeof canonical.latest_substantive_statement === "object") {
    const lss = canonical.latest_substantive_statement;
    latestSource = _truncateMessage(
      typeof lss.source === "string" ? lss.source : (typeof lss.message === "string" ? lss.message : null),
      96,
    );
  }
  if (!latestSource) {
    // Answer-only turns: skip the raw-statement fallback when there is no
    // substantive statement — the headline + outcome counts already convey
    // the result; echoing the done() statement source is noise.
    if (!_isAnswerOnlyTurn(entry)) {
      const rawStatements = Array.isArray(entry.statements) ? entry.statements : [];
      const rawLatest = rawStatements.length ? rawStatements[rawStatements.length - 1] : null;
      latestSource = _truncateMessage(
        typeof rawLatest?.source === "string" ? rawLatest.source : null,
        96,
      );
    }
  }
  const chevron = el("span", expanded ? "\u25bc" : "\u25b6");
  chevron.style.color = "#8d93a1";
  chevron.style.fontSize = "9px";
  collapsedLine.appendChild(chevron);

  row.appendChild(collapsedLine);
  if (latestSource) {
    const latestEl = el("div", `latest: ${latestSource}`);
    Object.assign(latestEl.style, {
      color: "#c4ccd6",
      fontSize: "11px",
      overflowWrap: "anywhere",
      paddingLeft: isInProgress ? "16px" : "0",
    });
    row.appendChild(latestEl);
  }

  // ── Expanded view ────────────────────────────────────────────────────
  if (expanded) {
    const expandedBox = el("div");
    expandedBox.className = "vibecomfy-batch-expanded";
    Object.assign(expandedBox.style, {
      display: "grid",
      gap: "4px",
      marginTop: "3px",
    });

    const auditBtnRow = el("div");
    Object.assign(auditBtnRow.style, {
      display: "flex",
      justifyContent: "flex-end",
    });
    const auditBtn = button("Audit \u2193", (e) => {
      e.stopPropagation();
      downloadTurnAudit(panel, index);
    });
    auditBtn.style.fontSize = "10px";
    auditBtn.style.padding = "2px 5px";
    auditBtnRow.appendChild(auditBtn);
    expandedBox.appendChild(auditBtnRow);

    // Use canonical outcome summary when available; fall back to raw entry.
    let summary = null;
    if (canonical && canonical.outcome && typeof canonical.outcome === "object" && typeof canonical.outcome.summary === "string") {
      summary = canonical.outcome.summary;
    } else {
      summary = _safeSummaryText(entry);
    }
    if (summary) {
      const reasoningRow = el("div");
      const reasoningToggle = el("span", "\u25b6 Reasoning");
      Object.assign(reasoningToggle.style, {
        color: "#9ed0ff",
        fontSize: "11px",
        cursor: "pointer",
        userSelect: "none",
      });
      let reasoningShown = false;
      const reasoningBody = el("div");
      Object.assign(reasoningBody.style, {
        display: "none",
        fontSize: "11px",
        color: "#c4ccd6",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        marginTop: "2px",
        paddingLeft: "12px",
        borderLeft: "2px solid #282a32",
      });
      reasoningBody.textContent = summary;
      reasoningToggle.onclick = function (e) {
        e.stopPropagation();
        reasoningShown = !reasoningShown;
        reasoningToggle.textContent = reasoningShown ? "\u25bc Reasoning" : "\u25b6 Reasoning";
        reasoningBody.style.display = reasoningShown ? "block" : "none";
      };
      reasoningRow.appendChild(reasoningToggle);
      reasoningRow.appendChild(reasoningBody);
      expandedBox.appendChild(reasoningRow);
    }

    // Outcome counts line
    const outcomeCountsText = formatOutcomeCounts(canonical, entry);
    if (outcomeCountsText) {
      const countsLine = el("div", outcomeCountsText);
      Object.assign(countsLine.style, {
        fontSize: "10px",
        color: "#8d93a1",
        marginTop: "2px",
      });
      expandedBox.appendChild(countsLine);
    }

    // Render expanded details from canonical activity when available.
    if (canonical && Array.isArray(canonical.details) && canonical.details.length) {
      _renderCanonicalDetails(expandedBox, canonical, deps);
    } else {
      // Fallback: raw entry statements + diagnostics
      const rawStatements = Array.isArray(entry.statements) ? entry.statements : [];
      const showStmts = rawStatements.slice(0, BATCH_STATEMENT_CAP);
      const moreCount = rawStatements.length - BATCH_STATEMENT_CAP;
      if (showStmts.length) {
        const stmtsHeader = el("div", "Turn details:");
        stmtsHeader.style.fontSize = "10px";
        stmtsHeader.style.color = "#9da1ac";
        stmtsHeader.style.textTransform = "uppercase";
        stmtsHeader.style.letterSpacing = "0.04em";
        expandedBox.appendChild(stmtsHeader);
        for (let s = 0; s < showStmts.length; s += 1) {
          expandedBox.appendChild(_statementBullet(showStmts[s], s, deps));
        }
        if (moreCount > 0) {
          const moreLine = el("div", `+${moreCount} more statement${moreCount !== 1 ? "s" : ""}\u2026`);
          moreLine.style.fontSize = "10px";
          moreLine.style.color = "#8d93a1";
          moreLine.style.fontStyle = "italic";
          expandedBox.appendChild(moreLine);
        }
      } else if (Number.isFinite(entry.statement_count) && entry.statement_count > 0) {
        const stmtsNote = el("div", `${entry.statement_count} statement${entry.statement_count !== 1 ? "s" : ""} (details unavailable)`);
        stmtsNote.style.fontSize = "10px";
        stmtsNote.style.color = "#8d93a1";
        expandedBox.appendChild(stmtsNote);
      }

      if (Array.isArray(entry.diagnostics) && entry.diagnostics.length) {
        _renderDiagnostics(expandedBox, entry.diagnostics, deps);
      }
    }

    const footer = _renderOutcomeFooter(entry, deps);
    if (footer) {
      expandedBox.appendChild(footer);
    }


    const tsRel = _formatRelativeTime(entry.timestamp);
    if (tsRel) {
      const tsLine = el("div", tsRel);
      tsLine.style.fontSize = "9px";
      tsLine.style.color = "#6b7080";
      tsLine.style.textAlign = "right";
      tsLine.title = entry.timestamp;
      expandedBox.appendChild(tsLine);
    }

    row.appendChild(expandedBox);
  }

  body.appendChild(row);
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
  const { appendCodeLine, appendTextLine, button, el, downloadTurnAudit } = deps;
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
  if (isPending) {
    const liveSummary = _renderLiveTurnSummary(
      panel,
      _latestLiveBatchTurn(panel, entry.session_id),
      deps,
    );
    if (liveSummary) {
      turnCard.appendChild(liveSummary);
    }
  }
  if (entry.audit_ref?.path) {
    appendCodeLine(turnCard, `audit: ${entry.audit_ref.path}`, "#9ed0ff");
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

export function populateActivityRows(body, panel, opts = {}, deps = {}) {
  _injectProgressPulseStyle(deps);
  const { clearNode } = deps;
  const { sessionId = null } = opts;
  clearNode(body);

  const hasPendingDurable = Array.isArray(panel?.state?.turns)
    ? panel.state.turns.some((entry) => (
      entry?.entry_type === "durable"
      && entry.status === "pending"
      && (!sessionId || !entry.session_id || entry.session_id === sessionId)
    ))
    : false;
  const relevantTurns = Array.isArray(panel?.state?.turns)
    ? panel.state.turns.filter((entry) => {
      if (!entry) {
        return false;
      }
      if (sessionId && entry.session_id && entry.session_id !== sessionId) {
        return false;
      }
      if (hasPendingDurable && entry.entry_type === "batch") {
        return false;
      }
      return isLiveActivityTurn(entry);
    })
    : [];
  // Render every live batch turn; upserts are already deduplicated by turn_key
  // in upsertBatchTurn, and sortPanelTurns keeps them newest-first.

  for (let index = 0; index < relevantTurns.length; index += 1) {
    const entry = relevantTurns[index];
    if (entry.entry_type === "batch") {
      _renderBatchTurnRow(body, panel, entry, index, deps);
    } else {
      _renderDurableTurnRow(body, panel, entry, index, deps);
    }
  }
}

function renderActivityRows(panel, deps = {}) {
  const mount = panel?.sections?.history;
  if (!mount) {
    return;
  }
  const hasPendingResponse = Array.isArray(panel?.state?.chatMessages)
    && panel.state.chatMessages.some((message) => (
      message?.role === "agent"
      && (message.pending_response === true || message.executor_pending === true)
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
