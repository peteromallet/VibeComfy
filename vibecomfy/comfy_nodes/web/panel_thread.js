import { getAgentPanelRuntime } from "./panel_runtime.js";

const THREAD_WINDOW_SIZE = 30;
const THREAD_NEAR_BOTTOM_TOLERANCE_PX = 120;

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
  const detailSigParts = [
    detailSnapshot?.phase || "",
    detailSnapshot?.message || "",
    detailSnapshot?.auditRef?.path || "",
    detailSnapshot?.changeDetails?.done_summary || msg?.change_details?.done_summary || "",
    Array.isArray(detailSnapshot?.fieldChanges) ? String(detailSnapshot.fieldChanges.length) : "",
    Array.isArray(msg?.field_changes) ? String(msg.field_changes.length) : "",
    msg?.turn_id || "",
    msg?.detail_turn_id || "",
    String(msg?.text || "").slice(0, 80),
  ];
  return detailSigParts.join("|");
}

function bubbleRenderSignature(panel, msg, deps = {}) {
  const { candidateActionState, detailSnapshotForMessage, messageSignature } = deps;
  const snapshot = typeof detailSnapshotForMessage === "function"
    ? detailSnapshotForMessage(panel, msg)
    : null;
  const actionState = typeof candidateActionState === "function"
    ? candidateActionState(panel, msg, snapshot)
    : {};
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
  ];
  return signatureParts.join("|");
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

  const metaSection = createBubbleDetailSection("Turn");
  appendTurnMeta(metaSection.body, panel, message, snapshot, { appendTextLine, el });
  target.appendChild(metaSection.section);

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

  const label = el("span", isUser ? "You" : "Agent");
  Object.assign(label.style, {
    fontSize: "9px",
    fontWeight: "700",
    color: isUser ? "#7db6ff" : "#02d4b3",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: "2px",
  });
  bubble.appendChild(label);

  const text = el("div", String(msg.text || ""));
  Object.assign(text.style, {
    fontSize: "12px",
    color: isUser ? "#d1d6e0" : "#c4ccd6",
    background: isUser ? "#1a2436" : "#0f2a26",
    padding: "6px 10px",
    borderRadius: isUser ? "10px 10px 3px 10px" : "10px 10px 10px 3px",
    maxWidth: "92%",
    wordBreak: "break-word",
    overflowWrap: "anywhere",
    whiteSpace: "pre-wrap",
    lineHeight: "1.4",
    minWidth: "0",
  });
  bubble.appendChild(text);

  if (isUser) {
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
    color: "#8d93a1",
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
    }
  };

  detailRow.appendChild(detailToggle);
  detailRow.appendChild(detailBody);
  bubble.appendChild(detailRow);
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

  for (const entry of displayEntries) {
    const { msg, index, key } = entry;
    if (!msg || typeof msg !== "object" || !msg.role) {
      continue;
    }
    const signature = bubbleRenderSignature(panel, msg, {
      ...deps,
      messageSignature,
    });
    let bubbleEntry = priorBubbleMap[key] || null;
    if (!bubbleEntry?.node) {
      bubbleEntry = { node: el("div") };
      renderChatBubbleNode(bubbleEntry.node, panel, msg, key, index, deps);
    } else if (priorSignatures[key] !== signature) {
      renderChatBubbleNode(bubbleEntry.node, panel, msg, key, index, deps);
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
    if (bubbleEntry?.node?.parentNode === messagesMount) {
      messagesMount.removeChild(bubbleEntry.node);
    }
  }

  // `signatures` is also write-through cache state: it mirrors the last render
  // content for each mounted bubble but never outranks the current DOM tree.
  threadState.renderedKeyOrder = nextKeyOrder;
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
      gap: "6px",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
    });
  }
  if (!emptyMount) {
    emptyMount = el("div");
    emptyMount.dataset.vibecomfyChatEmpty = "1";
    Object.assign(emptyMount.style, {
      display: "none",
      gap: "6px",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
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
  appendChildOnce(body, sessionRow);
  appendChildOnce(body, olderMount);
  appendChildOnce(body, messagesMount);
  appendChildOnce(body, activityMount);
  appendChildOnce(body, emptyMount);
  return { sessionRow, olderMount, messagesMount, emptyMount, activityMount };
}

function renderChatSessionLink(sessionRow, panel, deps = {}) {
  const { clearNode, el } = deps;
  const sessionLabel = panel?.state?.chatSessionPath || (panel?.state?.sessionId ? `out/editor_sessions/${panel.state.sessionId}` : null);
  if (!sessionLabel) {
    clearNode(sessionRow);
    sessionRow.style.display = "none";
    return;
  }
  const href = `/vibecomfy/agent-edit/session-json?session_id=${encodeURIComponent(panel.state.sessionId || "")}`;
  let link = sessionRow.querySelectorAll("a")[0] || null;
  if (!link) {
    clearNode(sessionRow);
    link = el("a");
    link.target = "_blank";
    link.rel = "noopener";
    Object.assign(link.style, {
      color: "#9ed0ff",
      fontSize: "10px",
      fontFamily: "monospace",
      textDecoration: "none",
      cursor: "pointer",
      minWidth: "0",
      overflowWrap: "anywhere",
      wordBreak: "break-word",
    });
    sessionRow.appendChild(link);
  }
  link.textContent = `session: ${sessionLabel}`;
  link.href = href;
  sessionRow.style.display = "flex";
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
  active: "#3d8bfd",
  success: "#4caf50",
  warning: "#ffc107",
  error: "#ff7f7f",
  muted: "#6b7080",
  pending: "#02d4b3",
});

const BATCH_STATUS_COLORS = Object.freeze({
  in_progress: "#3d8bfd",
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

  const kind = typeof stmt.op_kind === "string" && stmt.op_kind ? stmt.op_kind : "stmt";
  const kindEl = el("span", `${kind}${Number.isFinite(stmt.statement_index) ? ` #${stmt.statement_index}` : ""}`);
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
      parts.push(`budget: ${entry.budget.remaining_batches} left`);
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
      background: #3d8bfd;
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
  `;
  if (typeof document !== "undefined" && document?.head) {
    document.head.appendChild(style);
  }
}

function _renderBatchTurnRow(body, panel, entry, index, deps = {}) {
  const { button, el, downloadTurnAudit } = deps;
  const turnKey = entry.turn_key;
  const expanded = !!(panel.state.expandedTurnKeys && panel.state.expandedTurnKeys[turnKey]);
  const isInProgress = entry.status === "in_progress";
  const statusColor = _statusColor(entry.status);
  const turnLabel = Number.isFinite(entry.turn_number)
    ? `Turn ${entry.turn_number + 1}`
    : (typeof entry.turn_id === "string" && entry.turn_id ? `turn ${entry.turn_id}` : "batch turn");

  const row = el("div");
  row.className = "vibecomfy-batch-row";
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

  const statusEl = el("span", entry.status || "unknown");
  Object.assign(statusEl.style, {
    color: statusColor,
    fontSize: "9px",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    fontWeight: "600",
  });
  collapsedLine.appendChild(statusEl);

  const shortMsg = _truncateMessage(
    entry.status === "done"
      ? (
        entry.done_summary && entry.message && entry.done_summary !== entry.message
          ? `${entry.done_summary} ${entry.message}`
          : (entry.done_summary || entry.message)
      )
      : (entry.message || entry.done_summary),
    80,
  );
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

  const chevron = el("span", expanded ? "\u25bc" : "\u25b6");
  chevron.style.color = "#8d93a1";
  chevron.style.fontSize = "9px";
  collapsedLine.appendChild(chevron);

  row.appendChild(collapsedLine);

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

    const summary = _safeSummaryText(entry);
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

    const stmts = Array.isArray(entry.statements) ? entry.statements : [];
    const showStmts = stmts.slice(0, BATCH_STATEMENT_CAP);
    const moreCount = stmts.length - BATCH_STATEMENT_CAP;
    if (showStmts.length) {
      const stmtsHeader = el("div", "Statements:");
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

    const footer = _renderOutcomeFooter(entry, deps);
    if (footer) {
      expandedBox.appendChild(footer);
    }

    if (Array.isArray(entry.diagnostics) && entry.diagnostics.length) {
      const diagHeader = el("div", "Diagnostics:");
      diagHeader.style.fontSize = "10px";
      diagHeader.style.color = "#9da1ac";
      diagHeader.style.textTransform = "uppercase";
      diagHeader.style.letterSpacing = "0.04em";
      expandedBox.appendChild(diagHeader);
      const maxDiags = Math.min(entry.diagnostics.length, 5);
      for (let d = 0; d < maxDiags; d += 1) {
        const diag = entry.diagnostics[d];
        if (diag && typeof diag === "object") {
          const code = typeof diag.code === "string" ? diag.code : "";
          const msg = typeof diag.message === "string" ? diag.message : "";
          const diagText = code && msg ? `${code}: ${msg}` : (code || msg);
          if (diagText) {
            const diagLine = el("div", diagText);
            diagLine.style.fontSize = "10px";
            diagLine.style.color = "#8d93a1";
            expandedBox.appendChild(diagLine);
          }
        }
      }
    }

    if (typeof entry.timestamp === "string" && entry.timestamp) {
      const tsLine = el("div", entry.timestamp);
      tsLine.style.fontSize = "9px";
      tsLine.style.color = "#6b7080";
      expandedBox.appendChild(tsLine);
    }

    row.appendChild(expandedBox);
  }

  body.appendChild(row);
}

function _renderDurableTurnRow(body, panel, entry, index, deps = {}) {
  const { appendCodeLine, appendTextLine, button, el, downloadTurnAudit } = deps;
  const turnCard = el("div");
  turnCard.style.borderLeft = "3px solid #3d8bfd";
  turnCard.style.paddingLeft = "8px";
  turnCard.style.marginBottom = "8px";
  turnCard.style.display = "grid";
  turnCard.style.gap = "4px";

  const statusColor = _statusColor(entry.status);

  const headerRow = el("div");
  headerRow.style.display = "flex";
  headerRow.style.justifyContent = "space-between";
  headerRow.style.alignItems = "center";
  headerRow.style.gap = "8px";

  const statusBadge = el("span", entry.status || "unknown");
  statusBadge.style.color = statusColor;
  statusBadge.style.fontWeight = "700";
  statusBadge.style.textTransform = "uppercase";
  statusBadge.style.fontSize = "10px";
  statusBadge.style.letterSpacing = "0.05em";
  headerRow.appendChild(statusBadge);

  const downloadBtn = button("Audit \u2193", () => downloadTurnAudit(panel, index));
  downloadBtn.style.fontSize = "10px";
  downloadBtn.style.padding = "3px 6px";
  headerRow.appendChild(downloadBtn);

  turnCard.appendChild(headerRow);

  if (entry.turn_id) {
    appendTextLine(turnCard, `turn ${entry.turn_id}`, "#8d93a1");
  }
  if (entry.task) {
    appendTextLine(turnCard, entry.task, "#edf2f7");
  }
  if (entry.failure_kind) {
    appendTextLine(turnCard, `${entry.failure_kind}${entry.failure_stage ? ` @ ${entry.failure_stage}` : ""}`, "#ffb86c");
  }
  if (entry.message) {
    appendTextLine(turnCard, entry.message, "#9da1ac");
  }
  if (entry.audit_ref?.path) {
    appendCodeLine(turnCard, `audit: ${entry.audit_ref.path}`, "#9ed0ff");
  }
  if (entry.timestamp) {
    appendTextLine(turnCard, entry.timestamp, "#8d93a1");
  }

  body.appendChild(turnCard);
}

export function populateActivityRows(body, panel, opts = {}, deps = {}) {
  _injectProgressPulseStyle(deps);
  const { clearNode } = deps;
  const { sessionId = null } = opts;
  clearNode(body);

  const relevantTurns = Array.isArray(panel?.state?.turns)
    ? panel.state.turns.filter((entry) => {
      if (!entry) {
        return false;
      }
      if (sessionId && entry.session_id && entry.session_id !== sessionId) {
        return false;
      }
      return isLiveActivityTurn(entry);
    })
    : [];

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
