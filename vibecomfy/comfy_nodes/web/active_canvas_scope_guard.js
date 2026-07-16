// ── T11: Active-canvas scope guards for submit/apply ──────────────────────
// These functions protect graph capture and candidate application by verifying
// that the panel's chat scope, the bound session, the latest candidate session,
// and the active ComfyUI canvas scope are all in agreement.
//
// resolveActiveCanvasScope()   — compute scope from the live canvas graph
// assertPanelScopeMatchesActiveCanvas() — fail-closed comparison with debug metadata
// assertApplyScopeConsistency() — multi-factor apply guard (fail-closed, no auto-switch)

import {
  computeScopeId,
  computeStructuralGraphFingerprint,
} from "./scope_resolver.js";

import {
  resolveScopeSessionId,
} from "./scoped_session_storage.js";
import { createIntentGraphAdapter } from "./intent_graph_adapter.js";

const WORKFLOW_UUID_V1 = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function stableWorkflowUuid(value) {
  return typeof value === "string" && WORKFLOW_UUID_V1.test(value.trim())
    ? value.trim()
    : null;
}

function activeWorkflowWindowUuid() {
  const workflow = typeof app !== "undefined"
    ? app?.extensionManager?.workflow?.activeWorkflow
    : null;
  if (!workflow || typeof workflow !== "object") {
    return null;
  }
  const directCandidates = [
    workflow.id,
    workflow.workflowId,
    workflow.workflow_id,
    workflow.uuid,
  ];
  for (const candidate of directCandidates) {
    const workflowUuid = stableWorkflowUuid(candidate);
    if (workflowUuid) return workflowUuid;
  }
  if (typeof workflow.content === "string" && workflow.content.trim()) {
    try {
      const parsed = JSON.parse(workflow.content);
      for (const candidate of [parsed?.id, parsed?.workflow_id, parsed?.uuid]) {
        const workflowUuid = stableWorkflowUuid(candidate);
        if (workflowUuid) return workflowUuid;
      }
    } catch (_e) {
      return null;
    }
  }
  return null;
}

/**
 * Return the only workflow identity that may authorize new v2 issuance.
 * Persisted scope metadata is accepted for harnesses/refresh recovery where
 * ComfyUI has not yet reattached the active workflow object. Human labels,
 * paths, filenames and open-tab indexes are deliberately never consulted.
 */
export function resolveActiveWorkflowUuid() {
  const active = activeWorkflowWindowUuid();
  if (active) return active;
  const workflowManager = typeof app !== "undefined"
    ? app?.extensionManager?.workflow
    : null;
  const persistedCandidates = [
    workflowManager?.activeWorkflow?.vibecomfyScopeMetadata?.workflow_id,
    workflowManager?.vibecomfyScopeMetadata?.workflow_id,
  ];
  for (const candidate of persistedCandidates) {
    const workflowUuid = stableWorkflowUuid(candidate);
    if (workflowUuid) return workflowUuid;
  }
  return null;
}

/**
 * resolveActiveCanvasScope()
 *
 * Computes the per-workflow-window chat scope identity from the current
 * ComfyUI canvas graph through the canonical intent-graph adapter.
 *
 * Returns { scopeId, fingerprint } or null when the canvas is empty.
 */
export function resolveActiveCanvasScope() {
  if (typeof app === "undefined") {
    return null;
  }
  try {
    const capture = createIntentGraphAdapter(app).capture();
    if (!capture.ok) {
      return null;
    }
    const graph = capture.data.graph;
    if (!graph || typeof graph !== "object") {
      return null;
    }
    const workflowId = activeWorkflowWindowUuid();
    const scopeId = computeScopeId(graph, { workflowId });
    if (!scopeId) {
      return null;
    }
    const fingerprint = computeStructuralGraphFingerprint(graph);
    return { scopeId, fingerprint, workflowId: workflowId || null };
  } catch (_e) {
    return null;
  }
}

/**
 * assertPanelScopeMatchesActiveCanvas(panel, [opts])
 *
 * Compares the panel's tracked chat scope against the active canvas scope.
 * Returns a structured result with debug metadata so callers (submit/apply)
 * can emit rich diagnostics and make fail-closed decisions.
 *
 * @param {object} panel       — Agent panel with panel.state
 * @param {object} [opts]
 * @param {string} [opts.caller] — "submit" or "apply" for debug tagging
 * @returns {{ ok: boolean, panelScopeId: string|null, canvasScopeId: string|null,
 *             panelFingerprint: string|null, canvasFingerprint: string|null,
 *             reason: string|null, debug: object|null }}
 */
export function assertPanelScopeMatchesActiveCanvas(panel, { caller = "submit" } = {}) {
  const panelScopeId = panel?.state?.chatScopeId || null;
  const panelFingerprint = panel?.state?.chatScopeFingerprint || null;

  const canvas = resolveActiveCanvasScope();
  const canvasScopeId = canvas?.scopeId || null;
  const canvasFingerprint = canvas?.fingerprint || null;

  // ── No scope tracking active ──────────────────────────────────────────
  if (!panelScopeId && !canvasScopeId) {
    return {
      ok: true,
      panelScopeId: null,
      canvasScopeId: null,
      panelFingerprint: null,
      canvasFingerprint: null,
      reason: null,
      debug: { note: "no_scope_tracking" },
    };
  }

  // ── Panel has no scope but canvas does ────────────────────────────────
  if (!panelScopeId && canvasScopeId) {
    return {
      ok: false,
      panelScopeId: null,
      canvasScopeId,
      panelFingerprint: null,
      canvasFingerprint,
      reason: "panel_has_no_scope",
      debug: {
        caller,
        mismatch: "panel_unscoped_vs_canvas_scoped",
        canvasScopeId,
        canvasFingerprint,
      },
    };
  }

  // ── Panel has scope but canvas doesn't (empty canvas after workflow close) ──
  if (panelScopeId && !canvasScopeId) {
    return {
      ok: false,
      panelScopeId,
      canvasScopeId: null,
      panelFingerprint,
      canvasFingerprint: null,
      reason: "canvas_is_empty",
      debug: {
        caller,
        mismatch: "panel_scoped_vs_empty_canvas",
        panelScopeId,
        panelFingerprint,
      },
    };
  }

  // ── Both have scopes — compare fingerprints ──────────────────────────
  // Compare tab-nonce:structural-fingerprint parts: the tab-nonce part
  // (before the first colon) must match for the same tab, and the
  // structural fingerprint must match for the same workflow.
  if (canvasScopeId === panelScopeId) {
    return {
      ok: true,
      panelScopeId,
      canvasScopeId,
      panelFingerprint,
      canvasFingerprint,
      reason: null,
      debug: { caller, match: "exact" },
    };
  }

  // ── Mismatch detected ─────────────────────────────────────────────────
  // Parse scope ids to surface which part diverged.
  const panelParts = panelScopeId.split(":");
  const canvasParts = canvasScopeId.split(":");
  const tabMatch = panelParts[0] === canvasParts[0];
  const fpMatch = panelFingerprint === canvasFingerprint
    || (panelParts.length >= 2 && canvasParts.length >= 2 && panelParts.slice(1).join(":") === canvasParts.slice(1).join(":"));

  return {
    ok: false,
    panelScopeId,
    canvasScopeId,
    panelFingerprint,
    canvasFingerprint,
    reason: fpMatch ? "tab_diverged" : "graph_diverged",
    debug: {
      caller,
      mismatch: fpMatch ? "same_graph_different_tab" : "different_graph",
      tabMatch,
      fingerprintMatch: fpMatch,
      panelScopeId,
      canvasScopeId,
      panelFingerprint,
      canvasFingerprint,
    },
  };
}

/**
 * assertApplyScopeConsistency(panel, candidateSessionId)
 *
 * Multi-factor apply guard that checks all scope/session consistency before
 * a candidate can be applied to the canvas.  Fails closed on any disagreement.
 *
 * Checks:
 *   1. candidateScopeId === chatScopeId          (candidate belongs to this scope)
 *   2. bound session === panel.sessionId         (session binding is intact)
 *   3. candidate session === bound session       (candidate from current session)
 *   4. chat scope === active canvas scope        (canvas hasn't changed underneath)
 *
 * Returns a structured result — ok=false with reason when any check fails.
 * Never auto-switches scope; the caller must decide how to handle a refusal.
 *
 * @param {object} panel           — Agent panel with panel.state
 * @param {string|null} candidateSessionId — session_id from the latest candidate
 * @returns {{ ok: boolean, reason: string|null, details: object|null }}
 */
export function assertApplyScopeConsistency(panel, candidateSessionId = null) {
  const chatScopeId = panel?.state?.chatScopeId || null;
  const candidateScopeId = panel?.state?.candidateScopeId || null;
  const submittingScopeId = panel?.state?.submittingScopeId || null;
  const panelSessionId = panel?.state?.sessionId || null;

  const details = {
    chatScopeId,
    candidateScopeId,
    submittingScopeId,
    panelSessionId,
    candidateSessionId: candidateSessionId || null,
    boundSessionId: null, // filled below
    activeCanvasScopeId: null,
  };

  // ── No scope tracking active — allow (backward compat) ────────────────
  if (!chatScopeId) {
    return { ok: true, reason: null, details: { ...details, note: "no_scope_tracking" } };
  }

  // ── Check 1: candidate scope === chat scope ───────────────────────────
  // The candidate was generated for a specific scope.  If the panel's
  // active scope has changed since then, the candidate does not belong to
  // the currently visible workflow.
  // Use submittingScopeId as fallback — the transition from SUBMITTING to
  // AWAITING_REVIEW may not have set candidateScopeId yet.
  const effectiveCandidateScope = candidateScopeId || submittingScopeId || null;
  if (effectiveCandidateScope && effectiveCandidateScope !== chatScopeId) {
    return {
      ok: false,
      reason: "candidate_scope_mismatch",
      details: {
        ...details,
        mismatch: "candidate_vs_chat_scope",
        effectiveCandidateScope,
        chatScopeId,
      },
    };
  }

  // ── Check 2: bound session === panel.sessionId ────────────────────────
  // Resolve the scoped session for the active chat scope.
  const boundSessionId = resolveScopeSessionId(chatScopeId);
  details.boundSessionId = boundSessionId || null;

  if (boundSessionId && panelSessionId && boundSessionId !== panelSessionId) {
    return {
      ok: false,
      reason: "bound_session_mismatch",
      details: {
        ...details,
        mismatch: "bound_vs_panel_session",
        boundSessionId,
        panelSessionId,
        chatScopeId,
      },
    };
  }

  // ── Check 3: candidate session === bound session ──────────────────────
  // The candidate was returned from a specific session.  If the bound
  // session for this scope has changed (e.g., new conversation), the
  // candidate is stale.
  if (candidateSessionId && boundSessionId && candidateSessionId !== boundSessionId) {
    return {
      ok: false,
      reason: "candidate_session_mismatch",
      details: {
        ...details,
        mismatch: "candidate_vs_bound_session",
        candidateSessionId,
        boundSessionId,
      },
    };
  }

  // If no bound session yet but candidate has one, allow — first allocation.
  // If no candidate session, skip this check.

  // ── Check 4: chat scope === active canvas scope ───────────────────────
  const canvasAssertion = assertPanelScopeMatchesActiveCanvas(panel, { caller: "apply" });
  details.activeCanvasScopeId = canvasAssertion.canvasScopeId;

  if (!canvasAssertion.ok) {
    return {
      ok: false,
      reason: `canvas_scope_mismatch:${canvasAssertion.reason || "unknown"}`,
      details: {
        ...details,
        canvasAssertion,
        mismatch: "chat_vs_canvas_scope",
      },
    };
  }

  // ── All checks passed ─────────────────────────────────────────────────
  return { ok: true, reason: null, details };
}
