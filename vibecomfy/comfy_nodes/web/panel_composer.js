import { getAgentPanelRuntime } from "./panel_runtime.js";

export function submitReadinessState(panel, deps = {}) {
  const { routeStatusState, ROUTE_STATUS_KIND } = deps;
  const routeStatus = typeof routeStatusState === "function"
    ? routeStatusState(panel)
    : { kind: ROUTE_STATUS_KIND?.LOADING };
  if (routeStatus.kind === ROUTE_STATUS_KIND?.LOADING) {
    return {
      ready: false,
      reason: routeStatus.kind,
      message: "Waiting for /vibecomfy/agent/status before enabling Submit.",
    };
  }
  if (routeStatus.kind === ROUTE_STATUS_KIND?.MISSING_OPTIONS) {
    return {
      ready: false,
      reason: routeStatus.kind,
      message: "Submit is disabled because /vibecomfy/agent/status returned no route_options.",
    };
  }
  if (routeStatus.kind === ROUTE_STATUS_KIND?.MALFORMED) {
    return {
      ready: false,
      reason: routeStatus.kind,
      message: "Submit is disabled because /vibecomfy/agent/status returned a malformed payload.",
    };
  }
  if (routeStatus.kind === ROUTE_STATUS_KIND?.UNAVAILABLE) {
    return {
      ready: false,
      reason: routeStatus.kind,
      message: "Submit is disabled because /vibecomfy/agent/status is unavailable.",
    };
  }
  const status = panel?.state?.statusSnapshot;
  if (!status || typeof status !== "object" || Array.isArray(status)) {
    return {
      ready: false,
      reason: "missing_status",
      message: "Submit is disabled until /vibecomfy/agent/status returns a valid ready=true payload.",
    };
  }
  if (status.ready === true) {
    return { ready: true, reason: "ready", message: "" };
  }
  const statusMessage =
    (typeof status.readiness_message === "string" && status.readiness_message.trim())
    || (typeof status.message === "string" && status.message.trim())
    || (typeof status.reason === "string" && status.reason.trim())
    || "";
  return {
    ready: false,
    reason: status.ready === false ? "not_ready" : "missing_ready",
    message: statusMessage || "Submit is disabled until /vibecomfy/agent/status returns ready=true.",
  };
}

export function syncComposerButtons(panel, { submitting = false, showUndo = false } = {}) {
  const row = panel?.composerButtons;
  if (!row) {
    return;
  }
  const orderedButtons = [
    panel.buttons.submit,
    panel.buttons.stop,
    panel.buttons.apply,
    panel.buttons.reject,
    panel.buttons.undo,
    panel.buttons.newConversation,
  ];
  for (const btn of orderedButtons) {
    if (btn.parentNode !== row) {
      row.appendChild(btn);
    }
  }
  panel.buttons.stop.style.display = submitting ? "inline-flex" : "none";
  panel.buttons.undo.style.display = showUndo ? "inline-flex" : "none";
}

export function renderComposerNotice(panel, readinessState, deps = {}) {
  const { PANEL_STATE, button, clearNode, el, rebaselineCurrentCanvas, setButtonEmphasis } = deps;
  const notice = panel?.sections?.composerNotice;
  if (!notice) {
    return;
  }
  const runtime = getAgentPanelRuntime();
  runtime.lastNoticeRender = {
    panelId: panel?.panelId || null,
    readySeen: Boolean(readinessState?.ready),
    at: new Date().toISOString(),
  };
  runtime._lastNoticeRender = runtime.lastNoticeRender;
  if (panel) {
    panel.lastNoticeRender = runtime.lastNoticeRender;
  }
  clearNode(notice);
  let hasContent = false;
  const recovery = panel.state.phase === PANEL_STATE.ERROR ? panel.state.rebaselineRecovery : null;
  if (recovery?.action === "rebaseline" && recovery.reason === "stale_state_recovery") {
    const heading = el("div", "Canvas changed");
    heading.style.color = "#ffb86c";
    heading.style.fontWeight = "700";
    heading.style.marginBottom = "4px";
    notice.appendChild(heading);
    const message = el("div", "Rebaseline from the current canvas and retry the edit in one step.");
    message.style.color = "#edf2f7";
    notice.appendChild(message);
    const actionRow = el("div");
    Object.assign(actionRow.style, {
      display: "flex",
      flexWrap: "wrap",
      gap: "6px",
      marginTop: "8px",
    });
    const recoveryButton = button("Rebaseline & retry", () => rebaselineCurrentCanvas(panel));
    recoveryButton.dataset.vibecomfyRecoveryAction = "stale-rebaseline-retry";
    recoveryButton.disabled = Boolean(panel.state.inFlightRebaseline);
    recoveryButton.style.fontSize = "12px";
    recoveryButton.style.padding = "6px 10px";
    setButtonEmphasis(recoveryButton, true, "primary");
    actionRow.appendChild(recoveryButton);
    notice.appendChild(actionRow);
    hasContent = true;
  }
  const clarification = panel?.state?.clarification;
  if (
    (panel.state.phase === PANEL_STATE.CLARIFY || panel.state.phase === PANEL_STATE.AWAITING_REVIEW)
    && clarification?.message
  ) {
    if (hasContent) {
      const divider = el("div");
      divider.style.height = "1px";
      divider.style.background = "#2a313c";
      divider.style.margin = "8px 0";
      notice.appendChild(divider);
    }
    const heading = el("div", "Reply in the prompt");
    heading.style.color = "#ffc107";
    heading.style.fontWeight = "700";
    heading.style.marginBottom = "4px";
    notice.appendChild(heading);
    const followUp = el("div", "Your answer continues this same session.");
    followUp.style.color = "#9da1ac";
    notice.appendChild(followUp);
    hasContent = true;
  }
  if (!readinessState.ready) {
    if (hasContent) {
      const divider = el("div");
      divider.style.height = "1px";
      divider.style.background = "#2a313c";
      divider.style.margin = "8px 0";
      notice.appendChild(divider);
    }
    const readinessLabel = el("div", "Send unavailable");
    readinessLabel.style.color = "#ffb86c";
    readinessLabel.style.fontWeight = "700";
    readinessLabel.style.marginBottom = "4px";
    notice.appendChild(readinessLabel);
    notice.appendChild(el("div", readinessState.message));
    hasContent = true;
  } else if (panel.state.phase === PANEL_STATE.SUBMITTING) {
    const submittingLabel = el("div", "Submitting edit request.");
    submittingLabel.style.color = "#ffd36f";
    submittingLabel.style.fontWeight = "700";
    notice.appendChild(submittingLabel);
    const stopHint = el("div", "Stop cancels this request locally and marks the visible turn cancelled.");
    stopHint.style.color = "#9da1ac";
    stopHint.style.marginTop = "4px";
    notice.appendChild(stopHint);
    hasContent = true;
  }
  notice.style.display = hasContent ? "block" : "none";
}

export function renderComposerActions(panel, deps = {}) {
  const {
    candidateActionState,
    recordAgentPanelRenderCount,
    routeStatusState,
    ROUTE_STATUS_KIND,
    RENDER_SECTIONS,
    setButtonEmphasis,
    syncComposerButtons: syncComposerButtonsImpl,
    submitReadinessState: submitReadinessStateImpl,
    PANEL_STATE,
  } = deps;
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.COMPOSER);
  const phase = panel.state.phase;
  const submitting = phase === PANEL_STATE.SUBMITTING;
  const reviewing = phase === PANEL_STATE.AWAITING_REVIEW;
  const applying = phase === PANEL_STATE.APPLYING;
  const canSubmit =
    phase === PANEL_STATE.IDLE
    || phase === PANEL_STATE.ERROR
    || phase === PANEL_STATE.CLARIFY
    || phase === PANEL_STATE.AWAITING_REVIEW;
  const actionState = candidateActionState(panel);
  const rebaselineReason = panel.state.rebaselinePending?.reason || null;
  const rebaselinePending = Boolean(panel.state.rebaselinePending || panel.state.inFlightRebaseline);
  const undoPending = rebaselineReason === "undo";
  const readinessState = submitReadinessStateImpl(panel, {
    routeStatusState,
    ROUTE_STATUS_KIND,
  });

  panel.buttons.submit.disabled =
    submitting
    || rebaselinePending
    || !canSubmit
    || !readinessState.ready;
  panel.buttons.submit.textContent = submitting ? "Submitting..." : "Submit";
  panel.buttons.stop.disabled = !submitting;
  panel.buttons.apply.disabled = actionState.applyDisabled;
  panel.buttons.reject.disabled = actionState.rejectDisabled;
  panel.buttons.undo.disabled =
    panel.state.undoStack.length < 1
    || submitting
    || applying
    || Boolean(panel.state.inFlightRebaseline)
    || (rebaselinePending && !undoPending);
  panel.buttons.undo.textContent =
    panel.state.inFlightRebaseline && undoPending
      ? "Undo Rebaseline..."
      : undoPending
        ? "Retry Undo Rebaseline"
        : "Undo Last Apply";
  panel.buttons.settingsSave.disabled =
    submitting
    || applying
    || routeStatusState(panel).kind !== ROUTE_STATUS_KIND.READY;
  panel.buttons.settingsTest.disabled = submitting || applying;
  panel.state.previewEnabled = !!(reviewing && panel.state.candidateGraph);

  syncComposerButtonsImpl(panel, {
    submitting,
    showUndo: panel.state.undoStack.length > 0,
  });

  setButtonEmphasis(panel.buttons.submit, (canSubmit && readinessState.ready) || submitting, "primary");
  if (canSubmit && !submitting) {
    panel.buttons.submit.style.display = "inline-flex";
    panel.buttons.submit.style.opacity = "1";
  }
  setButtonEmphasis(panel.buttons.stop, submitting, "danger");
  setButtonEmphasis(panel.buttons.apply, reviewing || applying, "primary");
  setButtonEmphasis(panel.buttons.reject, reviewing || applying, "danger");
  setButtonEmphasis(panel.buttons.undo, panel.state.undoStack.length > 0, "neutral");
  setButtonEmphasis(panel.buttons.close, true, "neutral");
  setButtonEmphasis(panel.buttons.settingsSave, true, "neutral");
  setButtonEmphasis(panel.buttons.settingsTest, true, "neutral");
}

export function renderComposerNoticeSection(panel, deps = {}) {
  const {
    recordAgentPanelRenderCount,
    renderComposerNotice: renderComposerNoticeImpl,
    submitReadinessState: submitReadinessStateImpl,
    routeStatusState,
    ROUTE_STATUS_KIND,
    RENDER_SECTIONS,
  } = deps;
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.NOTICE);
  renderComposerNoticeImpl(panel, submitReadinessStateImpl(panel, {
    routeStatusState,
    ROUTE_STATUS_KIND,
  }), deps);
}

// ── Settings popover rendering ────────────────────────────────────────────

function renderDeveloperSubsection(title, deps = {}) {
  const { el } = deps;
  const section = el("div");
  Object.assign(section.style, {
    border: "1px solid #282a32",
    borderRadius: "4px",
    padding: "6px",
    background: "#0d0f14",
  });
  const heading = el("div", title);
  Object.assign(heading.style, {
    fontSize: "10px",
    fontWeight: "700",
    color: "#9da1ac",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    marginBottom: "4px",
  });
  section.appendChild(heading);
  return section;
}

export function renderDeveloper(panel, deps = {}) {
  const {
    adapterCapabilitySnapshot,
    APPLY_ELIGIBILITY_REASON,
    clearNode,
    createDetails,
    el,
    getAgentPanelRuntime,
    getQueueGuardStateForPanel,
    scrubDebugPayload,
  } = deps;
  const body = panel?.sections?.developer;
  if (!body) {
    return;
  }
  clearNode(body);

  const caps = adapterCapabilitySnapshot();
  const devData = el("div");
  Object.assign(devData.style, {
    display: "grid",
    gap: "4px",
    fontSize: "10px",
    color: "#8d93a1",
    lineHeight: "1.4",
  });

  const adapterSection = renderDeveloperSubsection("Adapter Capabilities", deps);
  const capLines = [
    `graphApply: ${caps.graphApply.available ? "✓" : "✗"} (${caps.graphApply.detail})`,
    `previewForeground: ${caps.previewForeground.available ? "✓" : "✗"} (${caps.previewForeground.detail})`,
    caps.previewStrategy ? `preview strategy: ${caps.previewStrategy}${caps.previewPolling ? " (polling fallback)" : ""}` : null,
    `queueGuard: ${caps.queueGuard.available ? "✓" : "✗"} (${caps.queueGuard.detail})`,
    caps.queueGuard.fallbackWarning ? `queueGuard fallback: ${caps.queueGuard.fallbackWarning}` : null,
    `supportsAll: ${caps.supportsAll ? "yes" : "no"} (frontend ${caps.frontendVersion})`,
  ].filter(Boolean);
  for (const line of capLines) {
    const div = el("div", line);
    div.style.color = line.startsWith("graphApply: ✗") || line.startsWith("previewForeground: ✗") || line.startsWith("queueGuard: ✗") ? "#ff8d8d" : "#8d93a1";
    adapterSection.appendChild(div);
  }
  devData.appendChild(adapterSection);

  const qgSection = renderDeveloperSubsection("Queue Guard State", deps);
  const qgState = getQueueGuardStateForPanel();
  const runtime = getAgentPanelRuntime();
  const qgLines = [
    `hookInstalled: ${qgState.hookInstalled}`,
    `hookPath: ${qgState.hookPath || "none"}`,
    qgState.fallbackWarning ? `fallbackWarning: ${qgState.fallbackWarning}` : null,
    qgState.activeContext ? `activeContext: turn=${qgState.activeContext.turnId || "?"} queueAllowed=${qgState.activeContext.queueAllowed}` : "activeContext: none",
    qgState.lastBlockNotice ? `lastBlock: ${qgState.lastBlockNotice.at || "?"} — ${qgState.lastBlockNotice.message}` : "lastBlockNotice: none",
    `blockedTurnKeys: ${runtime.queueGuardBlockedTurnKeys.size}`,
  ].filter(Boolean);
  for (const line of qgLines) {
    qgSection.appendChild(el("div", line));
  }
  devData.appendChild(qgSection);

  const hashSection = renderDeveloperSubsection("Hashes", deps);
  const hashLines = [
    `baselineGraphHash: ${panel.state.baselineGraphHash || "none"}`,
    panel.state.baselineGraphHashKind ? `baselineGraphHashKind: ${panel.state.baselineGraphHashKind}` : null,
    panel.state.baselineGraphHashVersion != null ? `baselineGraphHashVersion: ${panel.state.baselineGraphHashVersion}` : null,
    `candidateGraphHash: ${panel.state.candidateGraphHash || "none"}`,
    `serverSubmitGraphHash: ${panel.state.serverSubmitGraphHash || "none"}`,
    panel.state.lastSubmit?.client_graph_hash ? `lastSubmit.client_graph_hash: ${panel.state.lastSubmit.client_graph_hash}` : null,
    panel.state.lastSubmit?.client_structural_graph_hash ? `lastSubmit.client_structural_graph_hash: ${panel.state.lastSubmit.client_structural_graph_hash}` : null,
  ].filter(Boolean);
  for (const line of hashLines) {
    hashSection.appendChild(el("div", line));
  }
  devData.appendChild(hashSection);

  const boolSection = renderDeveloperSubsection("Raw Booleans", deps);
  const boolLines = [
    `canvasApplyAllowed: ${panel.state.canvasApplyAllowed}`,
    `queueAllowed: ${panel.state.queueAllowed}`,
    `applyAllowed: ${panel.state.applyAllowed}`,
    `applyEligibility: ${JSON.stringify(panel.state.applyEligibility)}`,
    panel.state.applyEligibilityWarning ? `applyEligibilityWarning: ${JSON.stringify(panel.state.applyEligibilityWarning)}` : null,
  ].filter(Boolean);
  for (const line of boolLines) {
    boolSection.appendChild(el("div", line));
  }
  devData.appendChild(boolSection);

  if (panel.state.applyEligibilityWarning && panel.state.applyEligibilityWarning.reason === APPLY_ELIGIBILITY_REASON?.MISSING_CONTRACT) {
    const mcSection = renderDeveloperSubsection("Missing Contract", deps);
    mcSection.style.color = "#ffc107";
    mcSection.appendChild(el("div", `turn_id: ${panel.state.applyEligibilityWarning.turn_id || "?"}`));
    mcSection.appendChild(el("div", `message: ${panel.state.applyEligibilityWarning.message}`));
    if (panel.state.applyEligibilityWarning.candidate_graph_hash) {
      mcSection.appendChild(el("div", `candidate_graph_hash: ${panel.state.applyEligibilityWarning.candidate_graph_hash}`));
    }
    devData.appendChild(mcSection);
  }

  const rawSection = renderDeveloperSubsection("Raw JSON", deps);
  const statusSnapshot = scrubDebugPayload(panel.state.statusSnapshot);
  const debugPayload = scrubDebugPayload(panel.state.debugPayload);
  if (statusSnapshot || debugPayload) {
    if (statusSnapshot) {
      rawSection.appendChild(createDetails("Status snapshot", statusSnapshot));
    }
    if (debugPayload) {
      rawSection.appendChild(createDetails("Debug payload", debugPayload));
    }
    devData.appendChild(rawSection);
  }

  body.appendChild(devData);
  if (Object.prototype.hasOwnProperty.call(body, "textContent")) {
    const summaryText = [
      "Adapter Capabilities",
      ...capLines,
      "Queue Guard State",
      ...qgLines,
      "Raw Booleans",
      ...boolLines,
    ].join("\n");
    body.textContent = summaryText;
    if (body.parentNode && Object.prototype.hasOwnProperty.call(body.parentNode, "textContent")) {
      body.parentNode.textContent = summaryText;
    }
  }
}

export function renderSettings(panel, deps = {}) {
  const {
    clearCredentialInput,
    getPanelElementById,
    getRouteDescriptor,
    normalizeRoutePreference,
    PANEL_IDS,
    routeStatusState,
    ROUTE_STATUS_KIND,
    setVisible,
  } = deps;
  const routeStatus = routeStatusState(panel);
  const descriptor = getRouteDescriptor(panel);
  const controlsReady =
    Boolean(descriptor)
    && (
      routeStatus.kind === ROUTE_STATUS_KIND.READY
      || routeStatus.kind === ROUTE_STATUS_KIND.LOADING
    );
  const apiKeyVisible = descriptor && Boolean(descriptor.browser_api_key_allowed);
  panel.fields.route.disabled = !controlsReady;
  panel.fields.model.disabled = !controlsReady;
  setVisible(panel.fields.apiKey, apiKeyVisible, "");
  panel.fields.apiKey.placeholder = apiKeyVisible
    ? "DeepSeek API key"
    : "Browser API keys are not accepted for this route";
  if (!apiKeyVisible) {
    clearCredentialInput(panel);
  }

  const statusNode = getPanelElementById(panel, PANEL_IDS.settingsStatus);
  const guidanceNode = getPanelElementById(panel, PANEL_IDS.settingsGuidance);
  if (!statusNode || !guidanceNode) {
    return;
  }
  if (!controlsReady) {
    if (routeStatus.kind === ROUTE_STATUS_KIND.LOADING) {
      statusNode.textContent = panel.state.settingsMessage || "Loading route/model status…";
      guidanceNode.textContent = "Waiting for /vibecomfy/agent/status before enabling route/model controls.";
    } else if (routeStatus.kind === ROUTE_STATUS_KIND.MISSING_OPTIONS) {
      statusNode.textContent = panel.state.settingsMessage || "Status missing route options; route/model controls disabled.";
      guidanceNode.textContent = "The backend returned status without route_options. Check /vibecomfy/agent/status and retry.";
    } else if (routeStatus.kind === ROUTE_STATUS_KIND.MALFORMED) {
      statusNode.textContent = panel.state.settingsMessage || "Malformed status payload; route/model controls disabled.";
      guidanceNode.textContent = "The backend status payload is malformed. Fix /vibecomfy/agent/status and retry.";
    } else if (routeStatus.kind === ROUTE_STATUS_KIND.UNAVAILABLE) {
      statusNode.textContent = panel.state.settingsMessage || "Status unavailable.";
      guidanceNode.textContent = "Could not reach /vibecomfy/agent/status. Retry with Test Provider after restoring the backend.";
    } else {
      statusNode.textContent = panel.state.settingsMessage || "Route/model controls unavailable.";
      guidanceNode.textContent = "";
    }
    return;
  }

  const normalizedRoute = descriptor.normalized_route || normalizeRoutePreference(panel.fields.route.value);
  const providerAvailable = panel.state.statusSnapshot?.provider_available;
  const availability = providerAvailable === false ? "provider unavailable" : "provider ready";
  statusNode.textContent = panel.state.settingsMessage
    || `${descriptor.requested_route} → ${normalizedRoute} (${availability})`;
  guidanceNode.textContent = descriptor.guidance || "";
  if (descriptor.requested_route === "anthropic") {
    guidanceNode.textContent += "\nTODO(S0): Claude/Anthropic ToS acknowledgement placeholder.";
  }
}

export function renderSettingsSection(panel, deps = {}) {
  const { recordAgentPanelRenderCount, RENDER_SECTIONS } = deps;
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.SETTINGS);
  renderSettings(panel, deps);
}

export function renderDeveloperSection(panel, deps = {}) {
  const { recordAgentPanelRenderCount, RENDER_SECTIONS } = deps;
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.DEVELOPER);
  renderDeveloper(panel, deps);
}
