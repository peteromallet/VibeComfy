export const APPLY_ELIGIBILITY_REASON = Object.freeze({
  APPLYABLE: "applyable",
  NO_CANDIDATE: "no_candidate",
  MISSING_CONTRACT: "missing_contract",
  MISSING_DURABLE_TURN_METADATA: "missing_durable_turn_metadata",
  NOT_LATEST: "not_latest",
  SUPERSEDED: "superseded",
  SERVER_BLOCKED: "server_blocked",
  STALE_CANVAS: "stale_canvas",
  QUEUE_BLOCKED_WARNING: "queue_blocked_warning",
  REHYDRATING: "rehydrating",
});

const PANEL_PHASE = Object.freeze({
  SUBMITTING: "SUBMITTING",
  APPLYING: "APPLYING",
});

export function normalizeApplyEligibility(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  if (!Object.values(APPLY_ELIGIBILITY_REASON).includes(payload.reason)) {
    return null;
  }
  return {
    applyable: payload.applyable !== false,
    reason: payload.reason,
    message: typeof payload.message === "string" ? payload.message : "",
    warnings: Array.isArray(payload.warnings) ? payload.warnings.slice() : [],
  };
}

function noCandidateApplyEligibility() {
  return {
    applyable: false,
    reason: APPLY_ELIGIBILITY_REASON.NO_CANDIDATE,
    message: "No candidate is available to apply.",
    warnings: [],
  };
}

function ensureMissingEligibilityWarning(panel, detail) {
  if (!panel?.state) {
    console.warn(`[vibecomfy] ${detail.message}`);
    return;
  }
  const warningKey = [
    detail.reason,
    panel.state.turnId || "no-turn",
    panel.state.candidateGraphHash || "no-candidate-hash",
  ].join(":");
  if (panel.state.applyEligibilityWarningKey === warningKey) {
    return;
  }
  panel.state.applyEligibilityWarningKey = warningKey;
  panel.state.applyEligibilityWarning = detail;
  panel.state.debugPayload = {
    ...(panel.state.debugPayload && typeof panel.state.debugPayload === "object"
      ? panel.state.debugPayload
      : {}),
    apply_eligibility_warning: detail,
  };
  console.warn(`[vibecomfy] ${detail.message}`);
}

function missingContractApplyEligibility(panel, detail = {}, options = {}) {
  const message = typeof detail.message === "string" && detail.message
    ? detail.message
    : "Backend response omitted canonical eligibility for this candidate. Apply is disabled until the contract is present.";
  if (options.missingContractAsNull === true) {
    return null;
  }
  const warning = {
    reason: APPLY_ELIGIBILITY_REASON.MISSING_CONTRACT,
    message,
    turn_id: panel?.state?.turnId || null,
    candidate_graph_hash: panel?.state?.candidateGraphHash || null,
  };
  ensureMissingEligibilityWarning(panel, warning);
  return {
    applyable: false,
    reason: APPLY_ELIGIBILITY_REASON.MISSING_CONTRACT,
    message,
    warnings: ["missing_contract"],
  };
}

export function applyEligibility(panel, liveCanvasSnapshot = null, options = {}) {
  if (!panel?.state?.candidateGraph) {
    return noCandidateApplyEligibility();
  }
  const canonicalEligibility = normalizeApplyEligibility(panel.state.applyEligibility);
  if (canonicalEligibility) {
    panel.state.applyEligibilityWarning = null;
    panel.state.applyEligibilityWarningKey = null;
    return canonicalEligibility;
  }
  return missingContractApplyEligibility(panel, {}, options);
}

export function disabledApplyEligibility(reason, message, warnings = []) {
  return {
    applyable: false,
    reason,
    message: typeof message === "string" ? message : "",
    warnings: Array.isArray(warnings) ? warnings.slice() : [],
  };
}

function candidateTurnId(message, snapshot = null) {
  if (typeof snapshot?.turn_id === "string" && snapshot.turn_id) {
    return snapshot.turn_id;
  }
  if (typeof message?.turn_id === "string" && message.turn_id) {
    return message.turn_id;
  }
  return null;
}

export function candidateGraphPresentForBubble(message, snapshot = null) {
  if (snapshot && Object.prototype.hasOwnProperty.call(snapshot, "candidateGraphPresent")) {
    return Boolean(snapshot.candidateGraphPresent);
  }
  const candidateGraph = message?.candidateGraph
    || message?.candidate?.graph
    || message?.response?.candidateGraph
    || message?.response?.candidate?.graph
    || null;
  return Boolean(candidateGraph && typeof candidateGraph === "object");
}

function snapshotEligibilityForBubble(message, snapshot = null) {
  const normalizedSnapshot = normalizeApplyEligibility(snapshot?.applyEligibility);
  if (normalizedSnapshot) {
    return normalizedSnapshot;
  }
  const normalizedMessage = normalizeApplyEligibility(
    message?.eligibility
      || message?.response?.eligibility
      || message?.apply_eligibility
      || message?.response?.apply_eligibility
      || null,
  );
  if (normalizedMessage) {
    return normalizedMessage;
  }
  return null;
}

export function candidateActionState(panel, message = null, snapshot = null) {
  const submitting = panel?.state?.phase === PANEL_PHASE.SUBMITTING;
  const applying = panel?.state?.phase === PANEL_PHASE.APPLYING;
  const rehydrating = panel?.state?.chatRehydratePending === true;
  const activeTurnId =
    panel?.state?.candidateGraph && typeof panel.state.turnId === "string" && panel.state.turnId
      ? panel.state.turnId
      : null;
  const turnId = candidateTurnId(message, snapshot) || activeTurnId;
  const candidatePresent = message || snapshot
    ? candidateGraphPresentForBubble(message, snapshot)
    : Boolean(panel?.state?.candidateGraph);

  if (!candidatePresent) {
    return {
      visible: false,
      active: false,
      turnId,
      eligibility: noCandidateApplyEligibility(),
      applyDisabled: true,
      rejectDisabled: true,
    };
  }

  const active =
    !message && !snapshot
      ? Boolean(candidatePresent && activeTurnId)
      : Boolean(activeTurnId && turnId && activeTurnId === turnId);
  let eligibility;
  if (!message && !snapshot) {
    eligibility = applyEligibility(panel);
  } else if (active) {
    eligibility = applyEligibility(panel);
  } else {
    const historicalEligibility = snapshotEligibilityForBubble(message, snapshot);
    if (historicalEligibility?.reason === APPLY_ELIGIBILITY_REASON.SUPERSEDED) {
      eligibility = historicalEligibility;
    } else {
      eligibility = disabledApplyEligibility(
        APPLY_ELIGIBILITY_REASON.NOT_LATEST,
        "Only the latest candidate can be applied.",
        ["not_latest"],
      );
    }
  }

  const blockerMessage =
    rehydrating
      ? "Checking whether this candidate is still available."
      : !eligibility.applyable
      ? (eligibility.message || (Array.isArray(eligibility.warnings) ? eligibility.warnings[0] : "") || "")
      : "";

  return {
    visible: true,
    active,
    turnId,
    eligibility,
    blockerMessage,
    applyDisabled: rehydrating || applying || !active || !eligibility.applyable,
    rejectDisabled: rehydrating || submitting || applying || !active,
  };
}
