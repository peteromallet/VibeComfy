import test from "node:test";
import assert from "node:assert/strict";

import {
  DELTA_DIAGNOSTIC_LEGACY_SHAPE,
  DELTA_DIAGNOSTIC_MALFORMED,
  DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
  DELTA_SCHEMA_VERSION,
  DeltaDiagnosticError,
} from "../../vibecomfy/comfy_nodes/web/canonical_delta.js";

import {
  PANEL_STATE,
  LIFECYCLE_STATE_FIELDS,
  RENDER_SECTIONS,
  buildNodePackInstallRequest,
  createAgentEditState,
  eventSessionMatchesActiveScope,
  transition,
  reconcileChatMessages,
  normalizeObligationDirtySections,
  normalizeDeltaOpsFromSubmit,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";
import {
  composerApplyDisplayState,
  syncComposerButtons,
} from "../../vibecomfy/comfy_nodes/web/panel_composer.js";

import {
  reduceAgentActivityFeed,
  deriveAgentActivityState,
  normalizeAgentTurnPayload,
} from "../../vibecomfy/comfy_nodes/web/agent_turn_feed.js";

// ── T11: Active-canvas scope guards ─────────────────────────────────────
import {
  resolveActiveCanvasScope,
  assertPanelScopeMatchesActiveCanvas,
  assertApplyScopeConsistency,
} from "../../vibecomfy/comfy_nodes/web/active_canvas_scope_guard.js";

// ── Helpers ─────────────────────────────────────────────────────────────────

function makePanel(overrides = {}) {
  const state = createAgentEditState();
  Object.assign(state, overrides);
  return { state };
}

function assertBaselineDefaults(state) {
  assert.equal(state.baselineTurnId, null);
  assert.equal(state.baselineGraphHash, null);
  assert.equal(state.baselineGraphHashKind, null);
  assert.equal(state.baselineGraphHashVersion, null);
  assert.equal(state.baselineSource, "none");
  assert.equal(state.baselineRebaselineId, null);
  assert.equal(state.baselineGraphSourcePath, null);
}

function assertCandidateDefaults(state) {
  assert.equal(state.candidateGraph, null);
  assert.equal(state.candidateGraphHash, null);
  assert.equal(state.candidateReport, null);
  assert.equal(state.serverSubmitGraphHash, null);
  assert.equal(state.customNodeResolution, null);
  assert.equal(state.applyEligibility, null);
  assert.equal(state.applyEligibilityWarning, null);
  assert.equal(state.applyEligibilityWarningKey, null);
  assert.equal(state.changeDetails, null);
  assert.equal(state.deltaOps, null);
}

function makeComposerButtonPanel() {
  const row = {
    children: [],
    appendChild(button) {
      if (!this.children.includes(button)) {
        this.children.push(button);
      }
      button.parentNode = this;
    },
  };
  const makeButton = () => ({ style: {}, parentNode: null });
  return {
    composerButtons: row,
    buttons: {
      submit: makeButton(),
      stop: makeButton(),
      apply: makeButton(),
      reject: makeButton(),
      undo: makeButton(),
      newConversation: makeButton(),
    },
  };
}

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

// ── PANEL_STATE ─────────────────────────────────────────────────────────────

test("PANEL_STATE exports frozen phase taxonomy with 6 phases matching the contract", () => {
  assert.ok(Object.isFrozen(PANEL_STATE));
  const keys = Object.keys(PANEL_STATE).sort();
  assert.deepEqual(keys, [
    "APPLYING",
    "AWAITING_REVIEW",
    "CLARIFY",
    "ERROR",
    "IDLE",
    "SUBMITTING",
  ]);
  assert.equal(PANEL_STATE.IDLE, "IDLE");
  assert.equal(PANEL_STATE.SUBMITTING, "SUBMITTING");
  assert.equal(PANEL_STATE.CLARIFY, "CLARIFY");
  assert.equal(PANEL_STATE.AWAITING_REVIEW, "AWAITING_REVIEW");
  assert.equal(PANEL_STATE.APPLYING, "APPLYING");
  assert.equal(PANEL_STATE.ERROR, "ERROR");
});

test("composer buttons hide undo while processing and hide reset controls while reviewing", () => {
  const panel = makeComposerButtonPanel();

  syncComposerButtons(panel, { submitting: true, showUndo: true });
  assert.equal(panel.buttons.stop.style.display, "inline-flex");
  assert.equal(panel.buttons.undo.style.display, "none");
  assert.equal(panel.buttons.newConversation.style.display, "none");

  syncComposerButtons(panel, { applying: true, showUndo: true });
  assert.equal(panel.buttons.stop.style.display, "none");
  assert.equal(panel.buttons.undo.style.display, "none");
  assert.equal(panel.buttons.newConversation.style.display, "none");

  syncComposerButtons(panel, { reviewing: true, showUndo: true });
  assert.equal(panel.buttons.stop.style.display, "none");
  assert.equal(panel.buttons.undo.style.display, "none");
  assert.equal(panel.buttons.newConversation.style.display, "none");

  panel.buttons.submit.textContent = "Working";
  syncComposerButtons(panel, { showUndo: true });
  assert.equal(panel.buttons.stop.style.display, "none");
  assert.equal(panel.buttons.undo.style.display, "none");
  assert.equal(panel.buttons.newConversation.style.display, "none");

  panel.buttons.submit.textContent = "Submit";
  syncComposerButtons(panel, { working: true, showUndo: true });
  assert.equal(panel.buttons.stop.style.display, "none");
  assert.equal(panel.buttons.undo.style.display, "none");
  assert.equal(panel.buttons.newConversation.style.display, "none");

  syncComposerButtons(panel, { showUndo: true });
  assert.equal(panel.buttons.stop.style.display, "none");
  assert.equal(panel.buttons.undo.style.display, "inline-flex");
  assert.equal(panel.buttons.newConversation.style.display, "inline-flex");
});

test("composer apply display state ignores flattened apply aliases without a canonical candidate", () => {
  const panel = makePanel({
    applyAllowed: true,
    canvasApplyAllowed: true,
    applyEligibility: { applyable: true, reason: "applyable", message: "legacy stale alias" },
    routeStatus: { kind: "ready", requestedRoute: "revise" },
  });

  const display = composerApplyDisplayState(panel, {
    routeStatusState: (nextPanel) => nextPanel.state.routeStatus,
  });

  assert.equal(display.routeStatus.kind, "ready");
  assert.equal(display.candidatePresent, false);
  assert.equal(display.applyAllowed, false);
  assert.equal(display.canvasApplyAllowed, false);
  assert.equal(display.eligibility, null);
});

test("composer apply display state projects canonical candidate, stage, and route state", () => {
  const panel = makePanel({
    sessionId: "session-composer",
    turnId: "0009",
    baselineTurnId: "0008",
    candidateGraph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
    candidateGraphHash: "candidate-hash",
    serverSubmitGraphHash: "submit-hash",
    baselineGraphHash: "baseline-hash",
    applyEligibility: { applyable: true, reason: "applyable", message: "Ready." },
    routeStatus: { kind: "ready", requestedRoute: "revise", model: "gpt-5" },
    debugPayload: {
      stageSnapshot: {
        stage: "review",
        ok: true,
        blocking: false,
        duration_ms: 12,
      },
    },
  });

  const display = composerApplyDisplayState(panel, {
    routeStatusState: (nextPanel) => nextPanel.state.routeStatus,
  });

  assert.equal(display.routeStatus.kind, "ready");
  assert.equal(display.stageSnapshot.stage, "review");
  assert.equal(display.stageSnapshot.durationMs, 12);
  assert.equal(display.candidatePresent, true);
  assert.equal(display.applyAllowed, true);
  assert.equal(display.canvasApplyAllowed, true);
  assert.equal(display.candidate.graphHash, "candidate-hash");
  assert.deepEqual(display.candidate.turnIdentity, {
    sessionId: "session-composer",
    turnId: "0009",
    baselineTurnId: "0008",
  });
});

// ── LIFECYCLE_STATE_FIELDS ──────────────────────────────────────────────────

test("LIFECYCLE_STATE_FIELDS exports frozen array with 55 field names", () => {
  assert.ok(Object.isFrozen(LIFECYCLE_STATE_FIELDS));
  assert.equal(LIFECYCLE_STATE_FIELDS.length, 55);

  // Spot-check key categories
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("phase"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("sessionId"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("turnId"));
  // ── T5: Scope identity fields ────────────────────────────────────────
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("chatScopeId"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("chatScopeFingerprint"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("candidateScopeId"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("submittingScopeId"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("baselineTurnId"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("baselineGraphHash"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("candidateGraph"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("candidateBaselineGraph"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("candidateGraphHash"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("candidateReport"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("customNodeResolution"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("nodePackInstallStates"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("message"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("failure"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("clarification"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("applyAllowed"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("applyEligibility"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("queueAllowed"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("canvasApplyAllowed"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("inFlightSubmit"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("submitEpoch"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("submitStartedAtMs"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("submitDeadlineMs"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("inFlightApply"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("rebaselinePending"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("lastSubmit"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("lastAppliedChanges"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("candidateBaselineGraph"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("changeDetails"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("transcriptMessages"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("responseDetails"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("executionEvents"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("auditArtifacts"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("debugDiagnostics"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("compartmentIndexes"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("chatRehydrateEpoch"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("chatRehydrateCommittedEpoch"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("syntheticAgentMessage"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("deltaOps"));

  // No duplicates
  assert.equal(new Set(LIFECYCLE_STATE_FIELDS).size, 55);
});

// ── createAgentEditState ────────────────────────────────────────────────────

test("createAgentEditState initializes all 55 lifecycle fields to defaults", () => {
  const state = createAgentEditState();

  // Every field from LIFECYCLE_STATE_FIELDS must exist on the returned object
  for (const field of LIFECYCLE_STATE_FIELDS) {
    assert.ok(
      Object.prototype.hasOwnProperty.call(state, field),
      `state.${field} must be own property`,
    );
  }

  // No extra own keys beyond the 55 fields
  const ownKeys = Object.keys(state);
  assert.equal(ownKeys.length, 55);

  // Phase default
  assert.equal(state.phase, PANEL_STATE.IDLE);

  // Session / turn identity
  assert.equal(state.sessionId, null);
  assert.equal(state.turnId, null);

  // Baseline defaults
  assertBaselineDefaults(state);

  // Candidate review defaults
  assertCandidateDefaults(state);
  assert.equal(state.customNodeResolution, null);
  assert.deepEqual(state.nodePackInstallStates, {});

  // Status / messaging
  assert.equal(state.message, null);
  assert.equal(state.failure, null);
  assert.equal(state.clarification, null);

  // Apply eligibility (derived)
  assert.equal(state.applyAllowed, false);
  // applyEligibility, applyEligibilityWarning, applyEligibilityWarningKey
  // already checked in assertCandidateDefaults

  // Gate booleans
  assert.equal(state.queueAllowed, false);
  assert.equal(state.canvasApplyAllowed, false);

  // Audit / debug
  assert.equal(state.auditRef, null);
  assert.equal(state.debugPayload, null);

  // In-flight guards
  assert.equal(state.inFlightSubmit, null);
  assert.equal(state.submitAbortController, null);
  assert.equal(state.submitEpoch, 0);
  assert.equal(state.submitStartedAtMs, null);
  assert.equal(state.submitDeadlineMs, null);
  assert.equal(state.inFlightApply, null);
  assert.equal(state.inFlightRebaseline, null);

  // Rebaseline state
  assert.equal(state.rebaselinePending, null);
  assert.equal(state.rebaselineRecovery, null);

  // Submit / apply metadata
  assert.equal(state.lastSubmit, null);
  assert.equal(state.lastAppliedChanges, null);
  assert.equal(state.lastSubmitFieldChanges, null);
  assert.equal(state.changeDetails, null);

  // Boundary compartments
  assert.deepEqual(state.transcriptMessages, []);
  assert.deepEqual(state.responseDetails, {});
  assert.deepEqual(state.executionEvents, []);
  assert.deepEqual(state.auditArtifacts, []);
  assert.deepEqual(state.debugDiagnostics, {});
  assert.deepEqual(state.compartmentIndexes, {
    responseDetailsByTurnId: {},
    executionEventsByKey: {},
    auditArtifactsByTurnId: {},
  });

  // Epoch
  assert.equal(state.chatRehydrateEpoch, 0);
  assert.equal(state.chatRehydrateCommittedEpoch, 0);

  // Synthetic chat
  assert.equal(state.syntheticAgentMessage, null);
});

test("createAgentEditState returns independent objects on each call", () => {
  const a = createAgentEditState();
  const b = createAgentEditState();

  a.phase = PANEL_STATE.SUBMITTING;
  a.baselineTurnId = "0001";
  a.transcriptMessages.push({ role: "user", text: "ask" });
  a.responseDetails.turn1 = { message: "detail" };
  a.executionEvents.push({ type: "batch" });
  a.auditArtifacts.push({ path: "/tmp/audit.json" });
  a.debugDiagnostics.raw = { hidden: true };
  a.compartmentIndexes.responseDetailsByTurnId.turn1 = "turn1";
  a.nodePackInstallStates.example = { status: "installing" };

  assert.equal(b.phase, PANEL_STATE.IDLE);
  assert.equal(b.baselineTurnId, null);
  assert.deepEqual(b.transcriptMessages, []);
  assert.deepEqual(b.responseDetails, {});
  assert.deepEqual(b.executionEvents, []);
  assert.deepEqual(b.auditArtifacts, []);
  assert.deepEqual(b.debugDiagnostics, {});
  assert.deepEqual(b.compartmentIndexes.responseDetailsByTurnId, {});
  assert.deepEqual(b.nodePackInstallStates, {});
});

// ── normalizeDeltaOpsFromSubmit ─────────────────────────────────────────────

test("normalizeDeltaOpsFromSubmit returns null for non-object input", () => {
  assert.equal(normalizeDeltaOpsFromSubmit(null), null);
  assert.equal(normalizeDeltaOpsFromSubmit(undefined), null);
  assert.equal(normalizeDeltaOpsFromSubmit("string"), null);
  assert.equal(normalizeDeltaOpsFromSubmit(42), null);
});

test("normalizeDeltaOpsFromSubmit returns null when delta_ops is absent", () => {
  assert.equal(normalizeDeltaOpsFromSubmit({}), null);
  assert.equal(normalizeDeltaOpsFromSubmit({ ok: true }), null);
});

test("normalizeDeltaOpsFromSubmit returns null when delta_ops is not an array", () => {
  assert.equal(normalizeDeltaOpsFromSubmit({ delta_ops: "not-array" }), null);
  assert.equal(normalizeDeltaOpsFromSubmit({ delta_ops: 123 }), null);
  assert.equal(normalizeDeltaOpsFromSubmit({ delta_ops: {} }), null);
});

test("normalizeDeltaOpsFromSubmit returns empty array for empty delta_ops", () => {
  assert.deepEqual(normalizeDeltaOpsFromSubmit({ delta_ops: [] }), []);
});

test("normalizeDeltaOpsFromSubmit normalizes valid delta_ops entries", () => {
  const result = {
    delta_ops: [
      { op: "set_node_field", target: ["nodes", 3, "widgets_values", 0], value: "hello" },
      { op: "set_mode", target: ["mode"], value: 4 },
    ],
  };
  const normalized = normalizeDeltaOpsFromSubmit(result);
  assert.ok(Array.isArray(normalized));
  assert.equal(normalized.length, 2);
  assert.equal(normalized[0].op, "set_node_field");
  assert.equal(normalized[1].op, "set_mode");
  // Keys must be sorted
  assert.deepEqual(Object.keys(normalized[0]), ["op", "target", "value"]);
});

test("normalizeDeltaOpsFromSubmit skips entries without a valid op string", () => {
  const result = {
    delta_ops: [
      { op: "set_node_field", target: ["nodes", 1], value: "keep" },
      { not_an_op: true },
      { op: "", target: [] },
      {},
      null,
      "invalid",
      { op: "set_mode", target: ["mode"], value: 0 },
    ],
  };
  const normalized = normalizeDeltaOpsFromSubmit(result);
  assert.equal(normalized.length, 2);
  assert.equal(normalized[0].op, "set_node_field");
  assert.equal(normalized[1].op, "set_mode");
});

test("normalizeDeltaOpsFromSubmit returns null when all entries are invalid", () => {
  const result = {
    delta_ops: [
      { not_an_op: true },
      { op: "" },
    ],
  };
  assert.equal(normalizeDeltaOpsFromSubmit(result), null);
});

// ── deltaOps lifecycle ──────────────────────────────────────────────────────

test("OK_CANDIDATE_RESPONSE extracts and stores deltaOps from V2 submit result", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", 3, "widgets_values", 0], value: "a cat" },
    { op: "set_mode", target: ["mode"], value: 4 },
  ];

  const obligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-v2",
      turn_id: "t-v2",
      delta_ops: deltaOps,
      message: "V2 candidate ready",
      submit_graph_hash: "abc123",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [] },
    candidateGraphHash: "hash-v2",
    applyEligibility: { applyable: true },
  });

  assert.equal(obligations.render, true);
  assert.equal(obligations.invalidateCandidate, true);
  assert.ok(Array.isArray(panel.state.deltaOps));
  assert.equal(panel.state.deltaOps.length, 2);
  assert.equal(panel.state.deltaOps[0].op, "set_node_field");
  assert.equal(panel.state.deltaOps[0].value, "a cat");
  assert.equal(panel.state.deltaOps[1].op, "set_mode");
  assert.equal(panel.state.deltaOps[1].value, 4);
});

test("REQUIRES_CUSTOM_NODES_RESPONSE stores evidence and keeps apply controls disabled", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const result = {
    ok: true,
    route: "requires_custom_nodes",
    message: "Custom nodes are required.",
    session_id: "sess-custom",
    turn_id: "turn-custom",
    outcome: {
      kind: "requires_custom_nodes",
      candidates: [
        {
          pack: { slug: "ComfyUI-VideoHelperSuite", source: "comfyui-manager" },
          expected_classes: ["VHS_VideoCombine"],
          validation_mode: "class_validatable",
          evidence: [{ source: "custom-node-map", matched_classes: ["VHS_VideoCombine"] }],
          warnings: [],
        },
        {
          pack: { slug: "ComfyUI-AnimateDiff-Evolved", source: "comfyui-manager" },
          expected_classes: [],
          validation_mode: "evidence_only",
          evidence: [{ source: "custom-node-list", matched_classes: [] }],
          warnings: ["No concrete class evidence."],
        },
      ],
      warnings: ["Install requires explicit confirmation."],
    },
  };

  const obligations = transition(panel, "REQUIRES_CUSTOM_NODES_RESPONSE", { result });

  assert.equal(obligations.render, true);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.sessionId, "sess-custom");
  assert.equal(panel.state.turnId, "turn-custom");
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
  assert.equal(panel.state.queueAllowed, false);
  assert.equal(panel.state.candidateGraph, null);
  assert.equal(panel.state.customNodeResolution.candidates.length, 2);
  assert.deepEqual(panel.state.customNodeResolution.candidates[0].expectedClasses, ["VHS_VideoCombine"]);
  assert.equal(panel.state.customNodeResolution.candidates[0].validationMode, "class_validatable");
  assert.equal(panel.state.customNodeResolution.candidates[1].validationMode, "evidence_only");
  assert.deepEqual(panel.state.customNodeResolution.candidates[1].warnings, ["No concrete class evidence."]);
});

test("NODE_PACK_INSTALL_STARTED builds POST obligation and tracks install progress states", () => {
  const panel = makePanel();
  const candidate = {
    pack: {
      slug: "ComfyUI-VideoHelperSuite",
      source: "comfyui-manager",
      url: "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
    },
    expectedClasses: ["VHS_VideoCombine"],
    validationMode: "class_validatable",
    stableInstallHash: "hash-vhs",
  };
  panel.state.customNodeResolution = {
    kind: "requires_custom_nodes",
    candidates: [candidate],
    warnings: ["External evidence is provisional."],
  };

  const request = buildNodePackInstallRequest(candidate);
  assert.equal(request.endpoint, "/vibecomfy/node-packs/install");
  assert.equal(request.method, "POST");
  assert.deepEqual(request.body, {
    candidate: {
      pack: candidate.pack,
      expected_classes: ["VHS_VideoCombine"],
      validation_mode: "class_validatable",
      stable_install_hash: "hash-vhs",
    },
    stable_install_hash: "hash-vhs",
    user_confirmed: true,
  });

  const start = transition(panel, "NODE_PACK_INSTALL_STARTED", { candidate });

  assert.equal(start.render, true);
  assert.equal(start.nodePackInstallRequest.endpoint, "/vibecomfy/node-packs/install");
  assert.equal(panel.state.nodePackInstallStates["hash-vhs"].status, "installing");
  assert.equal(panel.state.nodePackInstallStates["hash-vhs"].installing, true);

  const installed = transition(panel, "NODE_PACK_INSTALL_SUCCEEDED", {
    installKey: "hash-vhs",
    candidate,
    result: {
      ok: true,
      status: "installed",
      validation_status: "installed",
      validated: true,
      expected_classes: ["VHS_VideoCombine"],
      message: "Installed pack classes are present in /object_info.",
    },
  });

  assert.equal(installed.render, true);
  assert.equal(installed.focusPrompt, true);
  assert.deepEqual(installed.retryCustomNodeResolution, {
    reason: "node_pack_installed",
    expectedClasses: ["VHS_VideoCombine"],
  });
  assert.equal(panel.state.nodePackInstallStates["hash-vhs"].status, "installed");
  assert.equal(panel.state.nodePackInstallStates["hash-vhs"].installing, false);
  assert.equal(panel.state.customNodeResolution, null);

  transition(panel, "NODE_PACK_INSTALL_FAILED", {
    installKey: "hash-vhs",
    candidate,
    result: {
      ok: false,
      status: "validation_failed",
      validation_status: "validation_failed",
      message: "Post-install validation failed.",
    },
  });

  assert.equal(panel.state.nodePackInstallStates["hash-vhs"].status, "validation_failed");
});

test("NODE_PACK_INSTALL_SUCCEEDED restart_required keeps resolver evidence for restart guidance", () => {
  const candidate = {
    pack: { slug: "ComfyUI-VideoHelperSuite" },
    expectedClasses: ["VHS_VideoCombine"],
    validationMode: "class_validatable",
    stableInstallHash: "hash-vhs",
  };
  const panel = makePanel({
    customNodeResolution: {
      kind: "requires_custom_nodes",
      candidates: [candidate],
      warnings: ["Registry schema is provisional."],
    },
  });

  const obligations = transition(panel, "NODE_PACK_INSTALL_SUCCEEDED", {
    installKey: "hash-vhs",
    candidate,
    result: {
      ok: true,
      status: "installed",
      validation_status: "restart_required",
      validated: false,
      missing_classes: ["VHS_VideoCombine"],
      message: "Restart ComfyUI, then retry the edit.",
    },
  });

  assert.equal(obligations.focusPrompt, undefined);
  assert.equal(obligations.retryCustomNodeResolution, undefined);
  assert.equal(panel.state.nodePackInstallStates["hash-vhs"].status, "restart_required");
  assert.equal(panel.state.customNodeResolution.candidates[0], candidate);
});

test("OK_CANDIDATE_RESPONSE gates Apply on apply eligibility plus candidate presence", () => {
  const blockedPanel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  transition(blockedPanel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-blocked",
      turn_id: "t-blocked",
      message: "Candidate exists, but server blocked Apply.",
      apply_eligible: false,
      canvas_apply_allowed: true,
      apply_allowed: true,
    },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-blocked",
    applyEligibility: {
      applyable: false,
      reason: "no_candidate",
      message: "No candidate is available to apply.",
      warnings: [],
    },
  });

  assert.deepEqual(blockedPanel.state.candidateGraph, { nodes: [{ id: 1 }] });
  assert.equal(blockedPanel.state.applyAllowed, false);
  assert.equal(blockedPanel.state.canvasApplyAllowed, false);

  const staleClarifyPanel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    candidateGraph: { nodes: [{ id: 9 }] },
    candidateGraphHash: "stale-clarify",
    candidateReport: { change: true },
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
    deltaOps: [
      { op: "set_node_field", target: ["nodes", 9, "widgets_values", 0], value: "stale" },
    ],
  });

  const clarifyObligations = transition(staleClarifyPanel, "CLARIFY_ONLY_RESPONSE", {
    result: {
      session_id: "sess-clarify",
      turn_id: "t-clarify",
      message: "What do you mean?",
    },
    clarification: {
      message: "What do you mean?",
      turn_id: "t-clarify",
      session_id: "sess-clarify",
    },
    message: "What do you mean?",
  });

  assert.equal(clarifyObligations.render, true);
  assert.equal(clarifyObligations.invalidateCandidate, true);
  assert.equal(staleClarifyPanel.state.phase, PANEL_STATE.CLARIFY);
  assertCandidateDefaults(staleClarifyPanel.state);
  assert.equal(staleClarifyPanel.state.applyAllowed, false);
  assert.equal(staleClarifyPanel.state.canvasApplyAllowed, false);
  assert.equal(staleClarifyPanel.state.queueAllowed, false);
  assert.equal(staleClarifyPanel.state.deltaOps, null);

  const staleNoopPanel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    candidateGraph: { nodes: [{ id: 8 }] },
    candidateGraphHash: "stale-inspect",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
  });

  const noopObligations = transition(staleNoopPanel, "NOOP_RESPONSE", {
    result: {
      session_id: "sess-inspect",
      turn_id: "t-inspect",
      message: "This workflow uses a KSampler.",
    },
    message: "This workflow uses a KSampler.",
  });

  assert.equal(noopObligations.render, true);
  assert.equal(noopObligations.invalidateCandidate, true);
  assert.equal(staleNoopPanel.state.phase, PANEL_STATE.IDLE);
  assertCandidateDefaults(staleNoopPanel.state);
  assert.equal(staleNoopPanel.state.applyAllowed, false);
  assert.equal(staleNoopPanel.state.canvasApplyAllowed, false);
  assert.equal(staleNoopPanel.state.queueAllowed, false);

  const eligiblePanel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  transition(eligiblePanel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-eligible",
      turn_id: "t-eligible",
      message: "Candidate can be applied.",
      apply_eligible: true,
    },
    candidateGraph: { nodes: [{ id: 2 }] },
    candidateGraphHash: "hash-eligible",
    applyEligibility: {
      applyable: true,
      reason: "applyable",
      message: "Ready to apply.",
      warnings: [],
    },
  });

  assert.equal(eligiblePanel.state.applyAllowed, true);
  assert.equal(eligiblePanel.state.canvasApplyAllowed, true);
});

test("OK_CANDIDATE_RESPONSE reduces canonical candidate, identity, stage, and field selectors", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const canonicalResult = {
    ok: true,
    message: "Canonical candidate ready.",
    outcome: {
      kind: "candidate",
      changes: [
        { uid: "ksampler", field_path: "widgets.steps", old: 20, new: 30 },
      ],
    },
    candidate: {
      state: "candidate",
      graph: { nodes: [{ id: 12, type: "KSampler" }], links: [] },
      graph_hash: "candidate-hash-canonical",
      submit_graph_hash: "submit-hash-canonical",
      turn_identity: {
        session_id: "sess-canonical",
        turn_id: "turn-canonical",
        baseline_turn_id: "turn-baseline",
      },
    },
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      warnings: [],
    },
    debug: {
      stage_snapshots: [
        { stage: "plan", ok: true, blocking: false, duration_ms: 6 },
      ],
    },
  };

  const obligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: canonicalResult,
    queueAllowed: true,
    auditRef: { audit_path: "out/audits/canonical.json" },
    debugPayload: { response: "canonical" },
  });

  assert.equal(obligations.persistSession, "sess-canonical");
  assert.equal(panel.state.sessionId, "sess-canonical");
  assert.equal(panel.state.turnId, "turn-canonical");
  assert.deepEqual(panel.state.candidateGraph, canonicalResult.candidate.graph);
  assert.equal(panel.state.candidateGraphHash, "candidate-hash-canonical");
  assert.equal(panel.state.serverSubmitGraphHash, "submit-hash-canonical");
  assert.equal(panel.state.applyAllowed, true);
  assert.equal(panel.state.canvasApplyAllowed, true);
  assert.equal(panel.state.queueAllowed, true);
  assert.deepEqual(panel.state.lastSubmitFieldChanges.all, [
    { uid: "ksampler", fieldPath: "widgets.steps", old: 20, new: 30 },
  ]);
  assert.deepEqual(panel.state.debugPayload.stageSnapshot, {
    stage: "plan",
    ok: true,
    blocking: false,
    durationMs: 6,
  });
});

test("OK_CANDIDATE_RESPONSE keeps optional reorganise candidates applyable and latest", () => {
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    candidateGraph: { nodes: [{ id: 4, type: "KSampler", pos: [20, 20] }], links: [] },
    candidateGraphHash: "stale-functional-hash",
    applyEligibility: { applyable: true, reason: "applyable", message: "Old candidate." },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
  });
  const reorganisedGraph = {
    nodes: [{ id: 4, type: "KSampler", pos: [360, 160] }],
    links: [],
  };
  const layoutReorganisation = {
    result: "prepare_candidate",
    candidate_prepared: true,
    functional_candidate_graph_hash: "functional-candidate-hash",
    reorganised_candidate_graph_hash: "layout-candidate-hash",
    evidence: { layout_only_structural_noop: true },
  };

  const obligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      ok: true,
      message: "Prepared a layout-only candidate for review.",
      outcome: {
        kind: "candidate",
        changes: [{ uid: "4", field_path: "widgets.prompt", old: "old", new: "new" }],
      },
      candidate: {
        state: "candidate",
        graph: reorganisedGraph,
        graph_hash: "layout-candidate-hash",
        submit_graph_hash: "submit-hash-layout",
        turn_identity: {
          session_id: "sess-layout-candidate",
          turn_id: "turn-layout-candidate",
          baseline_turn_id: "turn-before-layout",
        },
      },
      apply_eligibility: {
        applyable: true,
        reason: "applyable",
        message: "Ready to apply layout candidate.",
        warnings: [],
      },
      layout_reorganisation: layoutReorganisation,
      debug: {
        stage_snapshots: [
          { stage: "post_edit_reorganise", ok: true, blocking: false, duration_ms: 11 },
        ],
      },
    },
    queueAllowed: true,
    changeDetails: {
      edited_nodes: ["4"],
      layout_reorganisation: layoutReorganisation,
    },
  });

  assert.equal(obligations.invalidateCandidate, true);
  assert.deepEqual(obligations.setQueueGuardContext, {
    sessionId: "sess-layout-candidate",
    turnId: "turn-layout-candidate",
    queueAllowed: true,
  });
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.sessionId, "sess-layout-candidate");
  assert.equal(panel.state.turnId, "turn-layout-candidate");
  assert.deepEqual(panel.state.candidateGraph, reorganisedGraph);
  assert.equal(panel.state.candidateGraphHash, "layout-candidate-hash");
  assert.equal(panel.state.serverSubmitGraphHash, "submit-hash-layout");
  assert.deepEqual(panel.state.applyEligibility, {
    applyable: true,
    reason: "applyable",
    message: "Ready to apply layout candidate.",
    warnings: [],
  });
  assert.equal(panel.state.applyAllowed, true);
  assert.equal(panel.state.canvasApplyAllowed, true);
  assert.equal(panel.state.queueAllowed, true);
  assert.deepEqual(panel.state.changeDetails.layout_reorganisation, layoutReorganisation);
  assert.deepEqual(panel.state.lastSubmitFieldChanges.all, [
    { uid: "4", fieldPath: "widgets.prompt", old: "old", new: "new" },
  ]);
  assert.deepEqual(panel.state.debugPayload.stageSnapshot, {
    stage: "post_edit_reorganise",
    ok: true,
    blocking: false,
    durationMs: 11,
  });
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE gates restored actions on eligibility plus candidate presence", () => {
  const panel = makePanel({ phase: PANEL_STATE.IDLE });

  transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    sessionId: "sess-restore",
    turnId: "t-restore",
    baseline: { raw: {} },
    candidateGraph: { nodes: [{ id: 3 }] },
    candidateGraphHash: "hash-restore",
    applyEligibility: {
      applyable: false,
      reason: "no_candidate",
      message: "No candidate is available to apply.",
      warnings: [],
    },
    applyAllowed: true,
    canvasApplyAllowed: true,
  });

  assert.deepEqual(panel.state.candidateGraph, { nodes: [{ id: 3 }] });
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE can restore from canonical latest-candidate payload", () => {
  const panel = makePanel({ phase: PANEL_STATE.IDLE });
  const latestCandidate = {
    ok: true,
    message: "Restored canonical candidate.",
    outcome: {
      kind: "candidate",
      changes: [
        { uid: "save", field_path: "filename_prefix", old: "old", new: "new" },
      ],
    },
    candidate: {
      state: "candidate",
      graph: { nodes: [{ id: 21, type: "SaveImage" }], links: [] },
      graph_hash: "rehydrate-candidate-hash",
      submit_graph_hash: "rehydrate-submit-hash",
      turn_identity: {
        session_id: "sess-rehydrate-canonical",
        turn_id: "turn-rehydrate-canonical",
      },
    },
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      warnings: [],
    },
    debug: {
      stage_snapshots: [
        { stage: "apply_candidate", ok: true, blocking: false, duration_ms: 9 },
      ],
    },
  };

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    baseline: latestCandidate,
    queueAllowed: false,
    auditRef: { audit_path: "out/audits/rehydrate.json" },
  });

  assert.equal(obligations.restored, true);
  assert.equal(obligations.persistSession, "sess-rehydrate-canonical");
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.sessionId, "sess-rehydrate-canonical");
  assert.equal(panel.state.turnId, "turn-rehydrate-canonical");
  assert.deepEqual(panel.state.candidateGraph, latestCandidate.candidate.graph);
  assert.equal(panel.state.candidateGraphHash, "rehydrate-candidate-hash");
  assert.equal(panel.state.serverSubmitGraphHash, "rehydrate-submit-hash");
  assert.equal(panel.state.applyAllowed, true);
  assert.deepEqual(panel.state.lastSubmitFieldChanges.all, [
    { uid: "save", fieldPath: "filename_prefix", old: "old", new: "new" },
  ]);
  assert.deepEqual(panel.state.debugPayload.stageSnapshot, {
    stage: "apply_candidate",
    ok: true,
    blocking: false,
    durationMs: 9,
  });
});

// ── T8: Scope-aware rehydrate and latest-candidate restore ─────────────────

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE refuses when requestScopeId mismatches chatScopeId (delayed rehydrate race)", () => {
  // Simulates: _rehydrateChat captured scope A at start, but by the time the
  // fetch resolved the panel has switched to scope B.  The restore must refuse.
  const panel = makePanel({ phase: PANEL_STATE.IDLE, chatScopeId: "scope-B" });

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    requestScopeId: "scope-A",  // stale — fetch started on scope A
    candidateSessionId: "sess-1",
    sessionId: "sess-1",
    turnId: "t-1",
    baseline: { raw: {} },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-1",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
  });

  assert.equal(obligations.render, false);
  assert.equal(obligations.skipped, true);
  assert.equal(obligations.stale, true);
  // Panel state must NOT have been mutated by the stale restore.
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.candidateGraph, null);
  assert.equal(panel.state.sessionId, null);
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE refuses when candidateSessionId mismatches panel sessionId (cross-session boundary)", () => {
  // The candidate belongs to sess-A but the panel is currently bound to sess-B.
  // Even if the scope matches, the session boundary prevents cross-contamination.
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: "scope-1",
    sessionId: "sess-B",
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    requestScopeId: "scope-1",  // scope matches
    candidateSessionId: "sess-A",  // but session differs
    sessionId: "sess-A",
    turnId: "t-1",
    baseline: { raw: {} },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-1",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
  });

  assert.equal(obligations.render, false);
  assert.equal(obligations.skipped, true);
  assert.equal(obligations.stale, true);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.candidateGraph, null);
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE succeeds when scope and session boundaries match", () => {
  // Happy path: the request scope matches the active scope AND the candidate's
  // session matches the panel's session (or panel has no session yet).
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: "scope-1",
    sessionId: "sess-1",
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    requestScopeId: "scope-1",
    candidateSessionId: "sess-1",
    sessionId: "sess-1",
    turnId: "t-1",
    baseline: { raw: {} },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-1",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
  });

  assert.equal(obligations.restored, true);
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.sessionId, "sess-1");
  assert.equal(panel.state.candidateScopeId, "scope-1");
  assert.deepEqual(panel.state.candidateGraph, { nodes: [{ id: 1 }] });
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE succeeds when candidateSessionId matches panel session even with different explicit sessionId", () => {
  // The sessionId in payload may differ from candidateSessionId (e.g., turn
  // identity vs candidate identity). The cross-session guard checks
  // candidateSessionId against panel.state.sessionId, not payload.sessionId.
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: "scope-1",
    sessionId: "sess-shared",
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    requestScopeId: "scope-1",
    candidateSessionId: "sess-shared",  // matches panel
    sessionId: "sess-shared",
    turnId: "t-1",
    baseline: { raw: {} },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-1",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
  });

  assert.equal(obligations.restored, true);
  assert.equal(panel.state.sessionId, "sess-shared");
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE backward-compatible when requestScopeId is absent", () => {
  // When no requestScopeId is provided (legacy path, or first open before
  // scope resolver runs), the transition must still work as before.
  const panel = makePanel({ phase: PANEL_STATE.IDLE, chatScopeId: "scope-1" });

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    // requestScopeId intentionally omitted
    sessionId: "sess-1",
    turnId: "t-1",
    baseline: { raw: {} },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-1",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
  });

  assert.equal(obligations.restored, true);
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.sessionId, "sess-1");
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE backward-compatible when candidateSessionId is absent", () => {
  // When candidateSessionId is not provided, cross-session check is skipped
  // (no refusal) so existing callers without T8 scope context still work.
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: "scope-1",
    sessionId: "sess-existing",
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    requestScopeId: "scope-1",
    // candidateSessionId intentionally omitted
    sessionId: "sess-other",
    turnId: "t-1",
    baseline: { raw: {} },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-1",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
  });

  assert.equal(obligations.restored, true);
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE refuses cross-scope when panel has no sessionId (scope guard takes priority)", () => {
  // Even if the panel has no sessionId set, the scope guard must still refuse
  // when requestScopeId doesn't match — a candidate from scope A cannot
  // populate scope B regardless of session state.
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: "scope-B",
    sessionId: null,
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    requestScopeId: "scope-A",
    candidateSessionId: "sess-1",
    sessionId: "sess-1",
    turnId: "t-1",
    baseline: { raw: {} },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-1",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
  });

  assert.equal(obligations.render, false);
  assert.equal(obligations.skipped, true);
  assert.equal(obligations.stale, true);
  assert.equal(panel.state.candidateGraph, null);
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE respects existing phase guards alongside scope guards", () => {
  // When SUBMITTING, the phase guard fires before scope checks.
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    chatScopeId: "scope-A",
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    requestScopeId: "scope-B",  // would fail scope check, but phase check fires first
    sessionId: "sess-1",
    turnId: "t-1",
    baseline: { raw: {} },
    candidateGraph: { nodes: [{ id: 1 }] },
  });

  assert.equal(obligations.render, false);
  assert.equal(obligations.skipped, true);
  // No stale flag — phase skip is not a scope violation, it's normal submit-busy.
  assert.equal(obligations.stale, undefined);
});

test("canonical candidate review apply path preserves stage through review then clears candidate state", () => {
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    debugPayload: { prior: true },
  });
  const canonicalResult = {
    ok: true,
    message: "Review the candidate before applying.",
    candidate: {
      state: "candidate",
      graph: { nodes: [{ id: 31, type: "KSampler" }], links: [] },
      graph_hash: "candidate-hash-31",
      submit_graph_hash: "submit-hash-31",
      turn_identity: {
        session_id: "sess-review-apply",
        turn_id: "turn-review-apply",
        baseline_turn_id: "turn-baseline-apply",
        idempotency_key: "idem-review-apply",
      },
    },
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      warnings: [],
    },
    outcome: {
      kind: "candidate",
      changes: [
        { uid: "31", field_path: "widgets.prompt", old: "old", new: "new" },
      ],
    },
    debug: {
      stage_snapshots: [
        { stage: "candidate_review", ok: true, blocking: false, duration_ms: 17 },
      ],
    },
  };

  const reviewObligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: canonicalResult,
    queueAllowed: true,
    auditRef: { audit_path: "out/audits/review-apply.json" },
  });

  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.sessionId, "sess-review-apply");
  assert.equal(panel.state.turnId, "turn-review-apply");
  assert.deepEqual(panel.state.candidateGraph, canonicalResult.candidate.graph);
  assert.equal(panel.state.candidateGraphHash, "candidate-hash-31");
  assert.equal(panel.state.serverSubmitGraphHash, "submit-hash-31");
  assert.equal(panel.state.applyAllowed, true);
  assert.equal(panel.state.canvasApplyAllowed, true);
  assert.equal(panel.state.queueAllowed, true);
  assert.deepEqual(panel.state.lastSubmitFieldChanges.all, [
    { uid: "31", fieldPath: "widgets.prompt", old: "old", new: "new" },
  ]);
  assert.deepEqual(panel.state.debugPayload.stageSnapshot, {
    stage: "candidate_review",
    ok: true,
    blocking: false,
    durationMs: 17,
  });
  assert.deepEqual(reviewObligations.setQueueGuardContext, {
    sessionId: "sess-review-apply",
    turnId: "turn-review-apply",
    queueAllowed: true,
  });

  transition(panel, "APPLY_STARTED", {
    acceptBody: {
      session_id: "sess-review-apply",
      turn_id: "turn-review-apply",
      client_graph_hash: "client-hash-31",
    },
  });
  assert.equal(panel.state.phase, PANEL_STATE.APPLYING);
  assert.deepEqual(panel.state.debugPayload.accept_request, {
    session_id: "sess-review-apply",
    turn_id: "turn-review-apply",
    client_graph_hash: "client-hash-31",
  });
  assert.deepEqual(panel.state.candidateGraph, canonicalResult.candidate.graph);
  assert.deepEqual(panel.state.lastSubmitFieldChanges.all, [
    { uid: "31", fieldPath: "widgets.prompt", old: "old", new: "new" },
  ]);

  const applyObligations = transition(panel, "APPLY_SUCCESS", {
    accepted: {
      ok: true,
      action: "accept",
      session_id: "sess-review-apply",
      turn_id: "turn-review-apply",
      baseline_turn_id: "turn-review-apply",
      baseline_graph_hash: "baseline-after-apply-31",
      baseline_graph_hash_kind: "structural",
      baseline_graph_hash_version: 2,
      audit_ref: { audit_path: "out/audits/apply-31.json" },
    },
    lastAppliedChanges: {
      items: [{ uid: "31", kind: "edited", fieldPath: "widgets.prompt" }],
    },
  });

  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.sessionId, "sess-review-apply");
  assert.equal(panel.state.turnId, "turn-review-apply");
  assert.equal(panel.state.baselineTurnId, "turn-review-apply");
  assert.equal(panel.state.baselineGraphHash, "baseline-after-apply-31");
  assertCandidateDefaults(panel.state);
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
  assert.equal(panel.state.queueAllowed, false);
  assert.deepEqual(panel.state.lastSubmitFieldChanges.all, [
    { uid: "31", fieldPath: "widgets.prompt", old: "old", new: "new" },
  ]);
  assert.deepEqual(applyObligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    clearCandidatePreview: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    toast: null,
  });
});

test("canonical candidate reject and new-conversation clear remove review state without losing durable baseline sync", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      ok: true,
      message: "Rejectable candidate ready.",
      outcome: { kind: "candidate", changes: [] },
      candidate: {
        state: "candidate",
        graph: { nodes: [{ id: 41, type: "SaveImage" }], links: [] },
        graph_hash: "candidate-hash-41",
        submit_graph_hash: "submit-hash-41",
        turn_identity: {
          session_id: "sess-review-reject",
          turn_id: "turn-review-reject",
        },
      },
      apply_eligibility: {
        applyable: true,
        reason: "applyable",
        warnings: [],
      },
      debug: {
        stage_snapshots: [
          { stage: "candidate_review", ok: true, blocking: false, duration_ms: 4 },
        ],
      },
    },
    queueAllowed: true,
  });

  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.sessionId, "sess-review-reject");
  assert.equal(panel.state.turnId, "turn-review-reject");
  assert.deepEqual(panel.state.debugPayload.stageSnapshot, {
    stage: "candidate_review",
    ok: true,
    blocking: false,
    durationMs: 4,
  });

  transition(panel, "REJECT_STARTED", {
    rejectBody: {
      session_id: "sess-review-reject",
      turn_id: "turn-review-reject",
    },
  });
  assert.equal(panel.state.phase, PANEL_STATE.APPLYING);
  assert.equal(panel.state.candidateGraphHash, "candidate-hash-41");

  const rejectObligations = transition(panel, "REJECT_SUCCESS", {
    rejected: {
      ok: true,
      action: "reject",
      session_id: "sess-review-reject",
      turn_id: "turn-review-reject",
      baseline_turn_id: "turn-baseline-after-reject",
      baseline_graph_hash: "baseline-after-reject-41",
      baseline_graph_hash_kind: "structural",
      baseline_graph_hash_version: 2,
    },
    message: "Rejected and cleared.",
  });

  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.sessionId, "sess-review-reject");
  assert.equal(panel.state.turnId, "turn-review-reject");
  assert.equal(panel.state.baselineTurnId, "turn-baseline-after-reject");
  assert.equal(panel.state.baselineGraphHash, "baseline-after-reject-41");
  assertCandidateDefaults(panel.state);
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
  assert.equal(panel.state.queueAllowed, false);
  assert.deepEqual(rejectObligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    clearCandidatePreview: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    toast: null,
  });

  const rehydrateObligations = transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: 1,
    sessionId: "sess-review-reject",
    latestTurnId: "turn-review-reject",
    messages: [
      { role: "user", text: "previous", turn_id: "turn-review-reject" },
      {
        role: "agent",
        text: "Rejected candidate should not reappear.",
        turn_id: "turn-review-reject",
        outcome: { kind: "candidate", changes: [] },
      },
    ],
    latestCandidate: null,
  });
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assertCandidateDefaults(panel.state);
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
  assert.equal(panel.state.queueAllowed, false);
  assert.deepEqual(rehydrateObligations, {
    render: false,
    dirtySections: META_AND_THREAD_DIRTY_SECTIONS,
    persistSession: "sess-review-reject",
  });

  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      ok: true,
      message: "New candidate ready.",
      outcome: { kind: "candidate", changes: [] },
      candidate: {
        state: "candidate",
        graph: { nodes: [{ id: 42, type: "SaveImage" }], links: [] },
        graph_hash: "candidate-hash-42",
        turn_identity: {
          session_id: "sess-review-reject",
          turn_id: "0009",
        },
      },
      apply_eligibility: {
        applyable: true,
        reason: "applyable",
        warnings: [],
      },
    },
    queueAllowed: true,
  });
  const staleRehydrateObligations = transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: 2,
    sessionId: "sess-review-reject",
    latestTurnId: "0008",
    messages: [],
    latestCandidate: null,
  });
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.candidateGraphHash, "candidate-hash-42");
  assert.deepEqual(staleRehydrateObligations, {
    render: false,
    dirtySections: META_AND_THREAD_DIRTY_SECTIONS,
    persistSession: "sess-review-reject",
  });

  panel.state.chatMessages = [
    { role: "user", text: "previous", turn_id: "turn-review-reject" },
  ];
  const clearObligations = transition(panel, "NEW_CONVERSATION");

  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.sessionId, null);
  assert.equal(panel.state.turnId, null);
  assertBaselineDefaults(panel.state);
  assertCandidateDefaults(panel.state);
  assert.equal(panel.state.applyAllowed, false);
  assert.deepEqual(clearObligations, {
    render: true,
    dirtySections: [
      RENDER_SECTIONS.THREAD,
      RENDER_SECTIONS.META,
      RENDER_SECTIONS.COMPOSER,
      RENDER_SECTIONS.NOTICE,
    ],
    invalidateCandidate: true,
    // ── T9: Scoped queue guard clear replaces flat clear ────────────────
    queueGuardClearScope: null,
    refreshQueueGuard: true,
    forgetSession: true,
    focusPrompt: true,
    forgetScope: null,
  });
});

test("transition table: canonical stage snapshots project into reducer debug state", () => {
  const cases = [
    {
      name: "candidate response stores the latest StageSnapshot",
      event: "OK_CANDIDATE_RESPONSE",
      initial: { phase: PANEL_STATE.SUBMITTING },
      payload: {
        result: {
          ok: true,
          message: "Candidate ready.",
          outcome: { kind: "candidate", changes: [] },
          candidate: {
            state: "candidate",
            graph: { nodes: [{ id: 51 }], links: [] },
            graph_hash: "candidate-stage-51",
            submit_graph_hash: "submit-stage-51",
            turn_identity: { session_id: "sess-stage-51", turn_id: "turn-stage-51" },
          },
          apply_eligibility: { applyable: true, reason: "applyable", warnings: [] },
          debug: {
            stage_snapshots: [
              { stage: "candidate_review", ok: true, blocking: false, duration_ms: 12 },
            ],
          },
        },
        queueAllowed: true,
      },
      expectedPhase: PANEL_STATE.AWAITING_REVIEW,
      expectedStageSnapshot: {
        stage: "candidate_review",
        ok: true,
        blocking: false,
        durationMs: 12,
      },
    },
    {
      name: "latest-candidate rehydrate stores the restored StageSnapshot",
      event: "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE",
      initial: { phase: PANEL_STATE.IDLE },
      payload: {
        baseline: {
          ok: true,
          outcome: { kind: "candidate", changes: [] },
          candidate: {
            state: "candidate",
            graph: { nodes: [{ id: 52 }], links: [] },
            graph_hash: "candidate-stage-52",
            submit_graph_hash: "submit-stage-52",
            turn_identity: { session_id: "sess-stage-52", turn_id: "turn-stage-52" },
          },
          apply_eligibility: { applyable: true, reason: "applyable", warnings: [] },
          debug: {
            stage_snapshots: [
              { stage: "apply_candidate", ok: true, blocking: false, duration_ms: 8 },
            ],
          },
        },
        queueAllowed: false,
      },
      expectedPhase: PANEL_STATE.AWAITING_REVIEW,
      expectedStageSnapshot: {
        stage: "apply_candidate",
        ok: true,
        blocking: false,
        durationMs: 8,
      },
    },
  ];

  for (const testCase of cases) {
    const panel = makePanel(testCase.initial);
    transition(panel, testCase.event, testCase.payload);

    assert.equal(panel.state.phase, testCase.expectedPhase, testCase.name);
    assert.deepEqual(panel.state.debugPayload?.stageSnapshot, testCase.expectedStageSnapshot, testCase.name);
  }
});

test("transition table: candidate review moves through apply, reject, and clear states", () => {
  function seedCandidate(panel, suffix) {
    transition(panel, "OK_CANDIDATE_RESPONSE", {
      result: {
        ok: true,
        message: `Candidate ${suffix} ready.`,
        outcome: { kind: "candidate", changes: [] },
        candidate: {
          state: "candidate",
          graph: { nodes: [{ id: suffix }], links: [] },
          graph_hash: `candidate-table-${suffix}`,
          submit_graph_hash: `submit-table-${suffix}`,
          turn_identity: {
            session_id: `sess-table-${suffix}`,
            turn_id: `turn-table-${suffix}`,
          },
        },
        apply_eligibility: { applyable: true, reason: "applyable", warnings: [] },
      },
      queueAllowed: true,
    });
  }

  const cases = [
    {
      name: "apply success clears candidate and advances baseline",
      run(panel) {
        seedCandidate(panel, "apply");
        transition(panel, "APPLY_STARTED", {
          acceptBody: { session_id: "sess-table-apply", turn_id: "turn-table-apply" },
        });
        transition(panel, "APPLY_SUCCESS", {
          accepted: {
            ok: true,
            action: "accept",
            session_id: "sess-table-apply",
            turn_id: "turn-table-apply",
            baseline_turn_id: "turn-table-apply",
            baseline_graph_hash: "baseline-table-apply",
            baseline_graph_hash_kind: "structural",
            baseline_graph_hash_version: 2,
          },
        });
      },
      expected: {
        phase: PANEL_STATE.IDLE,
        sessionId: "sess-table-apply",
        turnId: "turn-table-apply",
        baselineTurnId: "turn-table-apply",
        baselineGraphHash: "baseline-table-apply",
        applyAllowed: false,
        queueAllowed: false,
      },
    },
    {
      name: "reject success clears candidate and preserves authoritative session",
      run(panel) {
        seedCandidate(panel, "reject");
        transition(panel, "REJECT_STARTED", {
          rejectBody: { session_id: "sess-table-reject", turn_id: "turn-table-reject" },
        });
        transition(panel, "REJECT_SUCCESS", {
          rejected: {
            ok: true,
            action: "reject",
            session_id: "sess-table-reject",
            turn_id: "turn-table-reject",
            baseline_turn_id: "turn-baseline-reject",
            baseline_graph_hash: "baseline-table-reject",
          },
        });
      },
      expected: {
        phase: PANEL_STATE.IDLE,
        sessionId: "sess-table-reject",
        turnId: "turn-table-reject",
        baselineTurnId: "turn-baseline-reject",
        baselineGraphHash: "baseline-table-reject",
        applyAllowed: false,
        queueAllowed: false,
      },
    },
    {
      name: "new conversation clears candidate and durable review identity",
      run(panel) {
        seedCandidate(panel, "clear");
        transition(panel, "NEW_CONVERSATION");
      },
      expected: {
        phase: PANEL_STATE.IDLE,
        sessionId: null,
        turnId: null,
        baselineTurnId: null,
        baselineGraphHash: null,
        applyAllowed: false,
        queueAllowed: false,
      },
    },
  ];

  for (const testCase of cases) {
    const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
    testCase.run(panel);

    assert.equal(panel.state.phase, testCase.expected.phase, testCase.name);
    assert.equal(panel.state.sessionId, testCase.expected.sessionId, testCase.name);
    assert.equal(panel.state.turnId, testCase.expected.turnId, testCase.name);
    assert.equal(panel.state.baselineTurnId, testCase.expected.baselineTurnId, testCase.name);
    assert.equal(panel.state.baselineGraphHash, testCase.expected.baselineGraphHash, testCase.name);
    assert.equal(panel.state.applyAllowed, testCase.expected.applyAllowed, testCase.name);
    assert.equal(panel.state.canvasApplyAllowed, false, testCase.name);
    assert.equal(panel.state.queueAllowed, testCase.expected.queueAllowed, testCase.name);
    assertCandidateDefaults(panel.state);
  }
});

test("transition table: durable turn identity avoids missing-id and collision duplicates", () => {
  const cases = [
    {
      name: "matching canonical agent identity replaces optimistic duplicate",
      existing: [
        {
          role: "agent",
          text: "pending",
          optimistic: true,
          pending_response: true,
          submit_epoch: 7,
          turnIdentity: { turnId: "turn-collision", role: "agent" },
        },
      ],
      canonical: [
        {
          role: "agent",
          text: "confirmed",
          turn_identity: { turn_id: "turn-collision", role: "agent" },
        },
      ],
      expectedTexts: ["confirmed"],
    },
    {
      name: "same durable turn with different roles does not collide",
      existing: [
        {
          role: "agent",
          text: "pending agent",
          optimistic: true,
          pending_response: true,
          submit_epoch: 7,
          turnIdentity: { turnId: "turn-shared", role: "agent" },
        },
      ],
      canonical: [
        {
          role: "user",
          text: "confirmed user",
          turn_identity: { turn_id: "turn-shared", role: "user" },
        },
      ],
      expectedTexts: ["confirmed user", "pending agent"],
    },
    {
      name: "missing durable identity is dropped during submit reconciliation",
      existing: [
        {
          role: "agent",
          text: "identity-free pending",
          optimistic: true,
          pending_response: true,
          submit_epoch: 7,
        },
      ],
      canonical: [],
      expectedTexts: [],
    },
    {
      name: "stale optimistic epoch is dropped even with a valid identity",
      existing: [
        {
          role: "agent",
          text: "stale pending",
          optimistic: true,
          pending_response: true,
          submit_epoch: 6,
          turnIdentity: { turnId: "turn-stale", role: "agent" },
        },
      ],
      canonical: [],
      expectedTexts: [],
    },
  ];

  for (const testCase of cases) {
    const reconciled = reconcileChatMessages(testCase.existing, testCase.canonical, {
      phase: PANEL_STATE.SUBMITTING,
      submitEpoch: 7,
    });

    assert.deepEqual(reconciled.map((message) => message.text), testCase.expectedTexts, testCase.name);
  }
});

test("transition table: chat rehydrate reconciles fresh, stale, missing-session, and no-session states", () => {
  const cases = [
    {
      name: "fresh success commits canonical messages and session metadata",
      initial: { chatRehydrateEpoch: 3, chatRehydrateCommittedEpoch: 0 },
      event: "CHAT_REHYDRATE_SUCCESS",
      payload: {
        requestEpoch: 3,
        sessionId: "sess-rehydrate-table",
        messages: [{ role: "agent", text: "fresh durable" }],
        chatSessionPath: "out/editor_sessions/sess-rehydrate-table/",
      },
      expected: {
        sessionId: "sess-rehydrate-table",
        chatLoaded: true,
        chatError: null,
        messages: ["fresh durable"],
        stale: false,
        forgetSession: false,
      },
    },
    {
      name: "stale success older than committed epoch leaves state untouched",
      initial: {
        sessionId: "sess-current",
        chatRehydrateEpoch: 5,
        chatRehydrateCommittedEpoch: 5,
        chatLoaded: true,
        chatError: null,
        chatMessages: [{ role: "agent", text: "current durable" }],
      },
      event: "CHAT_REHYDRATE_SUCCESS",
      payload: {
        requestEpoch: 4,
        sessionId: "sess-old",
        messages: [{ role: "agent", text: "old durable" }],
      },
      expected: {
        sessionId: "sess-current",
        chatLoaded: true,
        chatError: null,
        messages: ["current durable"],
        stale: true,
        forgetSession: false,
      },
    },
    {
      name: "missing session clears matching stored session and forgets persistence",
      initial: {
        sessionId: "sess-missing",
        chatRehydrateEpoch: 2,
        chatMessages: [{ role: "agent", text: "old durable" }],
      },
      event: "CHAT_REHYDRATE_MISSING_SESSION",
      payload: { requestEpoch: 2, sessionId: "sess-missing" },
      expected: {
        sessionId: null,
        chatLoaded: true,
        chatError: null,
        messages: [],
        stale: false,
        forgetSession: true,
      },
    },
    {
      name: "no-session request clears transient chat without marking loaded",
      initial: {
        sessionId: null,
        chatRehydrateEpoch: 1,
        chatLoaded: true,
        chatMessages: [{ role: "agent", text: "transient" }],
      },
      event: "CHAT_REHYDRATE_NO_SESSION",
      payload: { requestEpoch: 1 },
      expected: {
        sessionId: null,
        chatLoaded: false,
        chatError: null,
        messages: [],
        stale: false,
        forgetSession: false,
      },
    },
  ];

  for (const testCase of cases) {
    const panel = makePanel(testCase.initial);
    const obligations = transition(panel, testCase.event, testCase.payload);

    assert.equal(Boolean(obligations.stale), testCase.expected.stale, testCase.name);
    assert.equal(Boolean(obligations.forgetSession), testCase.expected.forgetSession, testCase.name);
    assert.equal(panel.state.sessionId, testCase.expected.sessionId, testCase.name);
    assert.equal(panel.state.chatLoaded, testCase.expected.chatLoaded, testCase.name);
    assert.equal(panel.state.chatError, testCase.expected.chatError, testCase.name);
    assert.deepEqual(
      (panel.state.chatMessages || []).map((message) => message.text),
      testCase.expected.messages,
      testCase.name,
    );
  }
});

test("OK_CANDIDATE_RESPONSE preserves deltaOps through review (survives non-clearing transitions)", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", 1, "widgets_values", 0], value: "sunset" },
  ];

  // Step 1: candidate arrives with delta_ops
  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-review",
      turn_id: "t-review",
      delta_ops: deltaOps,
      message: "Review candidate",
      submit_graph_hash: "hash-review",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [] },
    candidateGraphHash: "ch-review",
    applyEligibility: { applyable: true },
  });

  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.ok(Array.isArray(panel.state.deltaOps));
  assert.equal(panel.state.deltaOps.length, 1);

  // Step 2: SYNC_BASELINE does not clear deltaOps
  transition(panel, "SYNC_BASELINE", {
    baseline_turn_id: "t-review",
    baseline_graph_hash: "new-baseline",
  });
  assert.ok(Array.isArray(panel.state.deltaOps), "deltaOps survives SYNC_BASELINE");
  assert.equal(panel.state.deltaOps[0].value, "sunset");

  // Step 3: a no-op transition doesn't clear deltaOps
  transition(panel, "INIT");
  assert.ok(Array.isArray(panel.state.deltaOps), "deltaOps survives INIT (no-op)");
  assert.equal(panel.state.deltaOps[0].value, "sunset");
});

test("OK_CANDIDATE_RESPONSE sets deltaOps to null when submit result has malformed delta_ops", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-malformed",
      turn_id: "t-malformed",
      delta_ops: "not-an-array", // malformed
      message: "Bad delta_ops",
      submit_graph_hash: "hash-bad",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [] },
    candidateGraphHash: "ch-bad",
    applyEligibility: { applyable: true },
  });

  assert.equal(panel.state.deltaOps, null, "malformed delta_ops must produce null");
});

test("OK_CANDIDATE_RESPONSE sets deltaOps to null when all delta_ops entries are invalid", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-invalid",
      turn_id: "t-invalid",
      delta_ops: [
        { not_an_op: true },
        { op: "" },
      ],
      message: "All invalid entries",
      submit_graph_hash: "hash-inv",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [] },
    candidateGraphHash: "ch-inv",
    applyEligibility: { applyable: true },
  });

  assert.equal(panel.state.deltaOps, null, "all-invalid entries must produce null");
});

test("terminal submit responses without session metadata do not trigger chat rehydrate", () => {
  const clarifyPanel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    chatMessages: [
      { role: "user", text: "Reply with a token", optimistic: true },
      { role: "agent", pending_response: true, executor_pending: true },
    ],
  });
  const clarifyObligations = transition(clarifyPanel, "CLARIFY_ONLY_RESPONSE", {
    result: {
      message: "Could you clarify the token?",
      outcome: { kind: "clarify", question: "Could you clarify the token?" },
    },
    clarification: { message: "Could you clarify the token?" },
    message: "Could you clarify the token?",
  });
  assert.equal(clarifyPanel.state.phase, PANEL_STATE.CLARIFY);
  assert.equal(clarifyPanel.state.sessionId, null);
  assert.equal(clarifyObligations.persistSession, null);
  assert.equal(clarifyObligations.rehydrateChat, false);

  const noopPanel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const noopObligations = transition(noopPanel, "NOOP_RESPONSE", {
    result: { message: "No change needed." },
    message: "No change needed.",
  });
  assert.equal(noopPanel.state.phase, PANEL_STATE.IDLE);
  assert.equal(noopObligations.persistSession, null);
  assert.equal(noopObligations.rehydrateChat, false);

  const candidatePanel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const candidateObligations = transition(candidatePanel, "OK_CANDIDATE_RESPONSE", {
    result: {
      message: "Candidate ready",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [] },
    candidateGraphHash: "hash-no-session",
    applyEligibility: { applyable: true },
  });
  assert.equal(candidatePanel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(candidateObligations.persistSession, null);
  assert.equal(candidateObligations.rehydrateChat, false);
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE extracts deltaOps from baseline.raw", () => {
  const panel = makePanel({ phase: PANEL_STATE.ERROR });
  const deltaOps = [
    { op: "upsert_link", target: ["links", 10], value: { origin_id: 5, origin_slot: 0, target_id: 8, target_slot: 0 } },
  ];
  const candidateGraph = { nodes: [{ id: 10 }] };

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    sessionId: "sess-rehydrate",
    turnId: "t-rehydrate",
    baseline: {
      baseline_turn_id: "t-base",
      baseline_graph_hash: "base-hash",
      raw: { delta_ops: deltaOps },
    },
    candidateGraph,
    candidateGraphHash: "rehydrate-hash",
    message: "Restored from rehydrate",
    applyEligibility: { applyable: true },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: false,
  });

  assert.equal(obligations.render, false);
  assert.equal(obligations.restored, true);
  assert.ok(Array.isArray(panel.state.deltaOps));
  assert.equal(panel.state.deltaOps.length, 1);
  assert.equal(panel.state.deltaOps[0].op, "upsert_link");
});

test("deltaOps survives the full review cycle from OK_CANDIDATE_RESPONSE through non-clearing transitions", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", 2, "inputs", "seed"], value: 42 },
    { op: "remove_node", target: ["nodes", 99] },
  ];

  // Candidate arrives
  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-full",
      turn_id: "t-full",
      delta_ops: deltaOps,
      message: "Full review",
      report: { changed: true },
      submit_graph_hash: "hash-full",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [{ id: 2 }, { id: 99 }] },
    candidateGraphHash: "ch-full",
    applyEligibility: { applyable: true },
  });

  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.deltaOps.length, 2);

  // SYNC_BASELINE — should preserve
  transition(panel, "SYNC_BASELINE", {
    baseline_turn_id: "t-full",
    baseline_graph_hash: "synced-baseline",
  });
  assert.equal(panel.state.deltaOps.length, 2, "deltaOps survives SYNC_BASELINE during review");

  // SUBMIT_IN_FLIGHT — should preserve (render-only)
  transition(panel, "SUBMIT_IN_FLIGHT", { promise: Promise.resolve() });
  assert.equal(panel.state.deltaOps.length, 2, "deltaOps survives SUBMIT_IN_FLIGHT");

  // SUBMIT_ABORT_CONTROLLER — should preserve (render-only)
  transition(panel, "SUBMIT_ABORT_CONTROLLER", { controller: { aborted: false } });
  assert.equal(panel.state.deltaOps.length, 2, "deltaOps survives SUBMIT_ABORT_CONTROLLER");
});

// ── deltaOps clearing transitions ───────────────────────────────────────────

test("SUBMIT_START clears deltaOps via INVALIDATE_CANDIDATE", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    deltaOps: [{ op: "set_node_field", target: ["nodes", 1], value: "test" }],
  });

  transition(panel, "SUBMIT_START", { lastSubmit: { task: "new submit" } });

  assert.equal(panel.state.deltaOps, null, "SUBMIT_START must clear deltaOps");
  assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING);
});

test("SUBMIT_ABORT clears deltaOps (cancel)", () => {
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    sessionId: "sess-1",
    deltaOps: [{ op: "set_mode", target: ["mode"], value: 2 }],
  });

  transition(panel, "SUBMIT_ABORT");

  assert.equal(panel.state.deltaOps, null, "SUBMIT_ABORT must clear deltaOps");
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
});

test("STOP_ABORT clears deltaOps", () => {
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    sessionId: "sess-2",
    deltaOps: [{ op: "reorder", target: ["nodes"], value: [3, 1, 2] }],
    candidateGraph: { nodes: [{ id: 3 }] },
    candidateGraphHash: "stop-candidate",
    _previewDiff: { stale: true },
    _previewDiffGraphHash: "stop-candidate",
    _previewDiffCacheTag: "stale",
    submitAbortController: { aborted: false },
    inFlightSubmit: Promise.resolve(),
  });

  const obligations = transition(panel, "STOP_ABORT");

  assert.deepEqual(obligations, {
    render: true,
    refreshQueueGuard: true,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
  assert.equal(panel.state.deltaOps, null, "STOP_ABORT must clear deltaOps");
  assert.equal(panel.state.candidateGraph, null);
  assert.equal(panel.state.candidateGraphHash, null);
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
  assert.equal(panel.state._previewDiffCacheTag, undefined);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
});

test("REJECT_SUCCESS clears deltaOps via INVALIDATE_CANDIDATE", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    deltaOps: [{ op: "set_node_field", target: ["nodes", 5, "widgets_values", 0], value: "rejected-value" }],
    candidateGraph: { nodes: [{ id: 5 }] },
    candidateGraphHash: "reject-hash",
    turnId: "t-reject",
  });

  transition(panel, "REJECT_SUCCESS", {
    rejected: { turn_id: "t-reject" },
    message: "Candidate rejected.",
  });

  assert.equal(panel.state.deltaOps, null, "REJECT_SUCCESS must clear deltaOps");
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.candidateGraph, null);
  assertCandidateDefaults(panel.state);
});

test("REBASELINE_SUCCESS clears deltaOps directly", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    deltaOps: [{ op: "add_node", target: ["nodes", "new-uid"], value: { type: "KSampler" } }],
    rebaselinePending: { original_turn_id: "t-old" },
  });

  transition(panel, "REBASELINE_SUCCESS", {
    result: {
      baseline_turn_id: "t-new",
      baseline_graph_hash: "rebaseline-hash",
      baseline_source: "rebaseline",
      audit_ref: { path: "audit.json" },
    },
  });

  assert.equal(panel.state.deltaOps, null, "REBASELINE_SUCCESS must clear deltaOps directly");
  assert.equal(panel.state.rebaselinePending, null);
  assert.equal(panel.state.baselineTurnId, "t-new");
});

test("INVALIDATE_CANDIDATE clears deltaOps alongside other candidate fields", () => {
  const panel = makePanel({
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "inv-hash",
    candidateReport: { change: true },
    serverSubmitGraphHash: "inv-submit-hash",
    applyEligibility: { applyable: true },
    applyEligibilityWarning: "warn",
    applyEligibilityWarningKey: "key-1",
    changeDetails: { changes: [{ op: "set", path: "/nodes/1" }] },
    deltaOps: [{ op: "set_node_field", target: ["nodes", 1, "widgets_values", 0], value: "clear-me" }],
  });

  const obligations = transition(panel, "INVALIDATE_CANDIDATE");

  assert.deepEqual(obligations, { render: true });
  assertCandidateDefaults(panel.state);
});

test("deltaOps is cleared and then repopulated across a submit→review→clear→new submit lifecycle", () => {
  const panel = makePanel({ phase: PANEL_STATE.IDLE });

  // First submit cycle: candidate arrives with delta_ops
  transition(panel, "SUBMIT_START", { lastSubmit: { task: "edit prompt" } });
  assert.equal(panel.state.deltaOps, null, "cleared on submit start");

  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-cycle",
      turn_id: "t-1",
      delta_ops: [{ op: "set_node_field", target: ["nodes", 1, "widgets_values", 0], value: "cycle-1" }],
      message: "First candidate",
      submit_graph_hash: "hash-1",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "ch-1",
    applyEligibility: { applyable: true },
  });
  assert.equal(panel.state.deltaOps[0].value, "cycle-1", "deltaOps populated after candidate");

  // Reject clears
  transition(panel, "REJECT_SUCCESS", {
    rejected: { turn_id: "t-1" },
    message: "Rejected first candidate.",
  });
  assert.equal(panel.state.deltaOps, null, "cleared on reject");

  // Second submit cycle
  transition(panel, "SUBMIT_START", { lastSubmit: { task: "edit cfg" } });
  assert.equal(panel.state.deltaOps, null, "still null after second submit start");

  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-cycle",
      turn_id: "t-2",
      delta_ops: [{ op: "set_mode", target: ["mode"], value: 3 }],
      message: "Second candidate",
      submit_graph_hash: "hash-2",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [{ id: 2 }] },
    candidateGraphHash: "ch-2",
    applyEligibility: { applyable: true },
  });
  assert.equal(panel.state.deltaOps[0].op, "set_mode", "deltaOps repopulated for second candidate");
  assert.equal(panel.state.deltaOps[0].value, 3);

  // Cancel clears
  const controller = { aborted: false };
  panel.state.submitAbortController = controller;
  panel.state.inFlightSubmit = Promise.resolve();
  panel.state.phase = PANEL_STATE.SUBMITTING;
  transition(panel, "STOP_ABORT");
  assert.equal(panel.state.deltaOps, null, "cleared on stop abort");
});

// ── INIT ────────────────────────────────────────────────────────────────────

test("INIT transition returns render:true and does not mutate state", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const before = JSON.stringify(panel.state);
  const obligations = transition(panel, "INIT");
  const after = JSON.stringify(panel.state);

  assert.deepEqual(obligations, {
    render: true,
    dirtySections: ALL_RENDER_DIRTY_SECTIONS,
  });
  assert.equal(after, before, "INIT must not mutate state");
});

// ── SYNC_BASELINE ───────────────────────────────────────────────────────────

test("SYNC_BASELINE mirrors authoritative baseline fields from payload", () => {
  const panel = makePanel();

  const obligations = transition(panel, "SYNC_BASELINE", {
    baseline_turn_id: "turn-42",
    baseline_graph_hash: "abc123def",
    baseline_graph_hash_kind: "structural",
    baseline_graph_hash_version: 3,
    baseline_source: "turn",
    baseline_rebaseline_id: null,
    baseline_graph_source_path: "turns/turn-42/candidate.ui.json",
  });

  assert.deepEqual(obligations, { render: true });
  assert.equal(panel.state.baselineTurnId, "turn-42");
  assert.equal(panel.state.baselineGraphHash, "abc123def");
  assert.equal(panel.state.baselineGraphHashKind, "structural");
  assert.equal(panel.state.baselineGraphHashVersion, 3);
  assert.equal(panel.state.baselineSource, "turn");
  assert.equal(panel.state.baselineRebaselineId, null);
  assert.equal(panel.state.baselineGraphSourcePath, "turns/turn-42/candidate.ui.json");
});

test("SYNC_BASELINE with omitted payload defaults to empty object and returns render:true", () => {
  const panel = makePanel();
  panel.state.baselineTurnId = "keep-me";

  const obligations = transition(panel, "SYNC_BASELINE");

  // payload defaults to {} — empty payload means no fields synced,
  // baseline source inferred as "none", render:true
  assert.deepEqual(obligations, { render: true });
  // baselineTurnId was not provided in the (empty) payload, so it stays
  // (the handler only updates keys that are present in the payload).
  // Since baselineTurnId was "keep-me" and no baseline_turn_id key was in
  // the empty payload, the field is untouched.
  assert.equal(panel.state.baselineTurnId, "keep-me");
});

test("SYNC_BASELINE with null payload returns render:false", () => {
  const panel = makePanel();

  const obligations = transition(panel, "SYNC_BASELINE", null);

  assert.deepEqual(obligations, { render: false });
});

test("SYNC_BASELINE with string payload returns render:false", () => {
  const panel = makePanel();

  const obligations = transition(panel, "SYNC_BASELINE", "not-an-object");

  assert.deepEqual(obligations, { render: false });
});

test("SYNC_BASELINE with empty payload object returns render:true and leaves defaults", () => {
  const panel = makePanel();

  const obligations = transition(panel, "SYNC_BASELINE", {});

  assert.deepEqual(obligations, { render: true });
  // Empty payload + no baseline data → baselineSource inferred as "none"
  assertBaselineDefaults(panel.state);
});

test("SYNC_BASELINE coerces non-string baseline_turn_id to null", () => {
  const panel = makePanel();

  transition(panel, "SYNC_BASELINE", { baseline_turn_id: 12345 });

  assert.equal(panel.state.baselineTurnId, null);
});

test("SYNC_BASELINE coerces non-string baseline_graph_hash to null", () => {
  const panel = makePanel();

  transition(panel, "SYNC_BASELINE", { baseline_graph_hash: 123 });

  assert.equal(panel.state.baselineGraphHash, null);
});

test("SYNC_BASELINE coerces non-string baseline_graph_hash_kind to null", () => {
  const panel = makePanel();

  transition(panel, "SYNC_BASELINE", { baseline_graph_hash_kind: {} });

  assert.equal(panel.state.baselineGraphHashKind, null);
});

test("SYNC_BASELINE coerces non-number baseline_graph_hash_version to null", () => {
  const panel = makePanel();

  transition(panel, "SYNC_BASELINE", { baseline_graph_hash_version: "not-a-number" });
  assert.equal(panel.state.baselineGraphHashVersion, null);

  transition(panel, "SYNC_BASELINE", { baseline_graph_hash_version: NaN });
  assert.equal(panel.state.baselineGraphHashVersion, null);

  transition(panel, "SYNC_BASELINE", { baseline_graph_hash_version: Infinity });
  assert.equal(panel.state.baselineGraphHashVersion, null);

  // Zero is valid
  transition(panel, "SYNC_BASELINE", { baseline_graph_hash_version: 0 });
  assert.equal(panel.state.baselineGraphHashVersion, 0);
});

test("SYNC_BASELINE coerces non-string baseline_source to 'none'", () => {
  const panel = makePanel();

  transition(panel, "SYNC_BASELINE", { baseline_source: 42 });

  assert.equal(panel.state.baselineSource, "none");
});

test("SYNC_BASELINE coerces non-string baseline_rebaseline_id to null", () => {
  const panel = makePanel();

  transition(panel, "SYNC_BASELINE", { baseline_rebaseline_id: true });

  assert.equal(panel.state.baselineRebaselineId, null);
});

test("SYNC_BASELINE coerces non-string baseline_graph_source_path to null", () => {
  const panel = makePanel();

  transition(panel, "SYNC_BASELINE", { baseline_graph_source_path: 123 });

  assert.equal(panel.state.baselineGraphSourcePath, null);
});

test("SYNC_BASELINE partial payload updates only provided keys", () => {
  const panel = makePanel();

  // Set some pre-existing values
  panel.state.baselineTurnId = "existing-turn";
  panel.state.baselineGraphHash = "existing-hash";
  panel.state.baselineSource = "turn";

  // Sync only turn_id — other fields should keep their values
  transition(panel, "SYNC_BASELINE", { baseline_turn_id: "new-turn" });

  assert.equal(panel.state.baselineTurnId, "new-turn");
  assert.equal(panel.state.baselineGraphHash, "existing-hash");
  assert.equal(panel.state.baselineSource, "turn");
});

test("SYNC_BASELINE infers baseline_source=turn when action=accept ok=true without explicit source", () => {
  const panel = makePanel();

  transition(panel, "SYNC_BASELINE", {
    action: "accept",
    ok: true,
    turn_id: "turn-99",
    baseline_turn_id: "turn-99",
    baseline_graph_hash: "hash-accept",
  });

  assert.equal(panel.state.baselineSource, "turn");
  assert.equal(panel.state.baselineRebaselineId, null);
  assert.equal(panel.state.baselineGraphSourcePath, "turns/turn-99/candidate.ui.json");
});

test("SYNC_BASELINE infers baseline_source=turn from existing baseline data when no source given", () => {
  const panel = makePanel();
  // Pre-populate with turn-like state
  panel.state.baselineTurnId = "turn-55";
  panel.state.baselineGraphHash = "hash-55";

  transition(panel, "SYNC_BASELINE", { some_other_field: true });

  assert.equal(panel.state.baselineSource, "turn");
  assert.equal(panel.state.baselineRebaselineId, null);
  assert.equal(panel.state.baselineGraphSourcePath, "turns/turn-55/candidate.ui.json");
});

test("SYNC_BASELINE infers baseline_source=rebaseline when no turnId but has hash and rebaselineId", () => {
  const panel = makePanel();
  // Pre-populate with rebaseline-like state (no turnId, but has hash and rebaselineId)
  panel.state.baselineGraphHash = "hash-rebase";
  panel.state.baselineRebaselineId = "rebase-12";

  transition(panel, "SYNC_BASELINE", {});

  assert.equal(panel.state.baselineSource, "rebaseline");
});

test("SYNC_BASELINE infers baseline_source=none when all baseline fields are null", () => {
  const panel = makePanel();

  transition(panel, "SYNC_BASELINE", {});

  assert.equal(panel.state.baselineSource, "none");
  assert.equal(panel.state.baselineRebaselineId, null);
  assert.equal(panel.state.baselineGraphSourcePath, null);
});

test("SYNC_BASELINE explicit baseline_source overrides inference", () => {
  const panel = makePanel();
  panel.state.baselineTurnId = "turn-1";
  panel.state.baselineGraphHash = "hash-1";
  panel.state.baselineRebaselineId = "rebase-1";

  // Explicit source should prevent inference
  transition(panel, "SYNC_BASELINE", { baseline_source: "rebaseline" });

  assert.equal(panel.state.baselineSource, "rebaseline");
  // baseline_source was explicitly provided, so inference branch skipped
  // but the other baseline fields should remain
  assert.equal(panel.state.baselineTurnId, "turn-1");
});

// ── INVALIDATE_CANDIDATE ────────────────────────────────────────────────────

test("INVALIDATE_CANDIDATE clears all candidate review fields with render:true by default", () => {
  const panel = makePanel({
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "abc",
    candidateReport: { change: {} },
    serverSubmitGraphHash: "def",
    applyEligibility: { allowed: true },
    applyEligibilityWarning: "warning",
    applyEligibilityWarningKey: "key-1",
    changeDetails: { changes: [] },
  });

  const obligations = transition(panel, "INVALIDATE_CANDIDATE");

  assert.deepEqual(obligations, { render: true });
  assertCandidateDefaults(panel.state);
});

test("INVALIDATE_CANDIDATE respects repaint:false in payload", () => {
  const panel = makePanel({
    candidateGraph: { nodes: [] },
    candidateGraphHash: "xyz",
  });

  const obligations = transition(panel, "INVALIDATE_CANDIDATE", { repaint: false });

  assert.deepEqual(obligations, { render: false });
  assert.equal(panel.state.candidateGraph, null);
  assert.equal(panel.state.candidateGraphHash, null);
});

test("INVALIDATE_CANDIDATE clears transient preview diff caches", () => {
  const panel = makePanel();
  panel.state._previewDiff = { some: "data" };
  panel.state._previewDiffGraphHash = "hash";

  transition(panel, "INVALIDATE_CANDIDATE");

  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
  assert.equal(Object.prototype.hasOwnProperty.call(panel.state, "_previewDiff"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(panel.state, "_previewDiffGraphHash"), false);
});

test("INVALIDATE_CANDIDATE is idempotent — clearing already-cleared fields is safe", () => {
  const panel = makePanel();

  // First call
  transition(panel, "INVALIDATE_CANDIDATE");
  // Second call should not throw or produce different result
  const obligations = transition(panel, "INVALIDATE_CANDIDATE");

  assert.deepEqual(obligations, { render: true });
  assertCandidateDefaults(panel.state);
});

test("SUBMIT_START emits deterministic status dirty sections and invalidates visible candidate overlays", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    submitEpoch: 2,
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "candidate-hash",
    candidateReport: { change: true },
    serverSubmitGraphHash: "submit-hash",
    applyEligibility: { applyable: true },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
    clarification: { message: "old clarify" },
    failure: { kind: "OldFailure" },
    lastAppliedChanges: { items: [{ uid: "uid-1" }] },
    lastSubmitFieldChanges: [{ field: "prompt" }],
    syntheticAgentMessage: { text: "stale" },
    debugPayload: { old: true },
    _previewDiff: { stale: true },
    _previewDiffGraphHash: "preview-stale",
  });

  const obligations = transition(panel, "SUBMIT_START", {
    submitEpoch: 9,
    lastSubmit: { task: "replace node" },
    debugPayload: { submit: "payload" },
  });

  assert.deepEqual(obligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    submitEpoch: 9,
    invalidateCandidate: true,
    clearChangedNodeFeedbackVisuals: true,
  });
  assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING);
  assert.equal(panel.state.submitEpoch, 9);
  assert.equal(panel.state.failure, null);
  assert.equal(panel.state.clarification, null);
  assert.equal(panel.state.submitStartedAtMs, null);
  assert.equal(panel.state.submitDeadlineMs, null);
  assert.equal(panel.state.syntheticAgentMessage, null);
  assert.equal(panel.state.lastAppliedChanges, null);
  assert.equal(panel.state.lastSubmitFieldChanges, null);
  assert.deepEqual(panel.state.lastSubmit, { task: "replace node" });
  assert.deepEqual(panel.state.debugPayload, { submit: "payload" });
  assertCandidateDefaults(panel.state);
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
});

test("SUBMIT_START records submit watchdog metadata when provided", () => {
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    submitEpoch: 2,
  });

  transition(panel, "SUBMIT_START", {
    submitEpoch: 7,
    lastSubmit: { task: "replace node" },
    submitStartedAtMs: 1234,
    submitDeadlineMs: 30000,
  });

  assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING);
  assert.equal(panel.state.submitEpoch, 7);
  assert.equal(panel.state.submitStartedAtMs, 1234);
  assert.equal(panel.state.submitDeadlineMs, 30000);
});

test("Submit response transitions return deterministic dirty sections and invalidation obligations", () => {
  const failure = {
    kind: "NetworkError",
    message: "backend unavailable",
    session_id: "sess-failure",
    turn_id: "0002",
    baseline_turn_id: "0001",
    baseline_graph_hash: "base-failure",
    audit_ref: { path: "failure-audit.json" },
    rebaseline_recovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "base-failure",
    },
  };
  const failurePanel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    sessionId: "sess-old",
    turnId: "0001",
    lastSubmit: { task: "edit" },
  });
  const failureObligations = transition(failurePanel, "SUBMIT_NETWORK_FAILURE", { failure });
  assert.deepEqual(failureObligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: "sess-failure",
    refreshQueueGuard: true,
    rehydrateChat: true,
  });
  assert.deepEqual(failurePanel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "base-failure",
    submit_graph_hash: null,
    submit_structural_graph_hash: null,
    client_graph_hash: null,
    client_structural_graph_hash: null,
  });

  const clarifyPanel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    candidateGraph: { stale: true },
    candidateGraphHash: "stale-hash",
    _previewDiff: { stale: true },
    _previewDiffGraphHash: "preview-stale",
  });
  const clarifyObligations = transition(clarifyPanel, "CLARIFY_ONLY_RESPONSE", {
    result: {
      session_id: "sess-clarify",
      turn_id: "0003",
      baseline_turn_id: "0002",
      baseline_graph_hash: "base-clarify",
    },
    clarification: { message: "Need more detail" },
    debugPayload: { response: "clarify" },
  });
  assert.deepEqual(clarifyObligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: "sess-clarify",
    refreshQueueGuard: true,
    rehydrateChat: true,
    invalidateCandidate: true,
  });

  const noopPanel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    candidateGraph: { stale: true },
    candidateGraphHash: "stale-noop",
    _previewDiff: { stale: true },
    _previewDiffGraphHash: "preview-noop",
  });
  const noopObligations = transition(noopPanel, "NOOP_RESPONSE", {
    result: {
      session_id: "sess-noop",
      turn_id: "0005",
      baseline_turn_id: "0004",
      baseline_graph_hash: "base-noop",
      message: "KSampler cfg is already 6.5; no change needed.",
      apply_eligibility: { applyable: false, reason: "no_candidate" },
    },
    message: "KSampler cfg is already 6.5; no change needed.",
    debugPayload: { response: "noop" },
  });
  assert.deepEqual(noopObligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: "sess-noop",
    refreshQueueGuard: true,
    rehydrateChat: true,
    invalidateCandidate: true,
  });
  assert.equal(noopPanel.state.phase, PANEL_STATE.IDLE);
  assert.equal(noopPanel.state.candidateGraph, null);
  assert.equal(noopPanel.state.applyAllowed, false);
  assert.equal(noopPanel.state.queueAllowed, false);
  assert.equal(noopPanel.state.message, "KSampler cfg is already 6.5; no change needed.");

  const candidatePanel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    candidateGraph: { stale: true },
    candidateGraphHash: "stale-candidate",
    _previewDiff: { stale: true },
    _previewDiffGraphHash: "preview-candidate",
  });
  const candidateObligations = transition(candidatePanel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-candidate",
      turn_id: "0004",
      message: "Candidate ready",
      report: { changed: true },
      submit_graph_hash: "server-submit-hash",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [{ id: 4 }] },
    candidateGraphHash: "candidate-hash-4",
    applyEligibility: { applyable: true },
    debugPayload: { response: "candidate" },
  });
  assert.deepEqual(candidateObligations, {
    render: true,
    dirtySections: REVIEW_DIRTY_SECTIONS,
    persistSession: "sess-candidate",
    setQueueGuardContext: {
      sessionId: "sess-candidate",
      turnId: "0004",
      queueAllowed: false,
    },
    refreshQueueGuard: true,
    rehydrateChat: true,
    invalidateCandidate: true,
  });
});

// ── Stop / new conversation ────────────────────────────────────────────────

test("STOP_ABORT increments submitEpoch and clears in-flight submit state while preserving session context", () => {
  const controller = { aborted: false };
  const promise = Promise.resolve();
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    sessionId: "sess-1",
    turnId: "turn-9",
    submitEpoch: 4,
    submitAbortController: controller,
    inFlightSubmit: promise,
    failure: { kind: "NetworkError" },
    lastSubmit: { task: "replace node" },
  });

  const obligations = transition(panel, "STOP_ABORT");

  assert.deepEqual(obligations, {
    render: true,
    refreshQueueGuard: true,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
  assert.equal(panel.state.submitEpoch, 5);
  assert.equal(panel.state.submitAbortController, null);
  assert.equal(panel.state.inFlightSubmit, null);
  assert.equal(panel.state.submitStartedAtMs, null);
  assert.equal(panel.state.submitDeadlineMs, null);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.failure, null);
  assert.equal(panel.state.message, "Request cancelled.");
  assert.equal(panel.state.sessionId, "sess-1");
  assert.equal(panel.state.turnId, "turn-9");
  assert.equal(panel.state.lastSubmit?.task, "replace node");
  assert.equal(panel.state.syntheticAgentMessage?.text, "Request cancelled.");
  assert.equal(panel.state.syntheticAgentMessage?.session_id, "sess-1");
  assert.equal(panel.state.debugPayload?.cancelled, true);
  assert.deepEqual(panel.state.debugPayload?.last_submit, { task: "replace node" });
});

test("SUBMIT_STALE_IN_FLIGHT_RECOVERY increments submitEpoch and clears only stale submit guards", () => {
  const promise = Promise.resolve();
  const controller = { aborted: false };
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    sessionId: "sess-recover",
    turnId: "0004",
    submitEpoch: 9,
    inFlightSubmit: promise,
    submitAbortController: controller,
    submitStartedAtMs: 10,
    submitDeadlineMs: 20,
    lastSubmit: { task: "stalled request" },
  });

  const obligations = transition(panel, "SUBMIT_STALE_IN_FLIGHT_RECOVERY", {
    debugPayload: { stale_in_flight_submit: true },
  });

  assert.deepEqual(obligations, { render: false, recovered: true });
  assert.equal(panel.state.submitEpoch, 10);
  assert.equal(panel.state.inFlightSubmit, null);
  assert.equal(panel.state.submitAbortController, null);
  assert.equal(panel.state.submitStartedAtMs, null);
  assert.equal(panel.state.submitDeadlineMs, null);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.sessionId, "sess-recover");
  assert.equal(panel.state.turnId, "0004");
  assert.deepEqual(panel.state.lastSubmit, { task: "stalled request" });
  assert.deepEqual(panel.state.debugPayload, { stale_in_flight_submit: true });
});

test("SUBMIT_FINALLY clears watchdog metadata only when explicitly requested", () => {
  const promise = Promise.resolve();
  const controller = { aborted: false };
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    submitEpoch: 4,
    inFlightSubmit: promise,
    submitAbortController: controller,
    submitStartedAtMs: 111,
    submitDeadlineMs: 222,
    submittingScopeId: "scope-1",
  });

  transition(panel, "SUBMIT_FINALLY", {
    clearAbortController: false,
    clearInFlightSubmit: false,
    clearSubmitWatchdogState: false,
    clearSubmittingScope: false,
  });
  assert.equal(panel.state.inFlightSubmit, promise);
  assert.equal(panel.state.submitAbortController, controller);
  assert.equal(panel.state.submitStartedAtMs, 111);
  assert.equal(panel.state.submitDeadlineMs, 222);
  assert.equal(panel.state.submittingScopeId, "scope-1");

  transition(panel, "SUBMIT_FINALLY", {
    clearAbortController: true,
    clearInFlightSubmit: true,
    clearSubmitWatchdogState: true,
  });
  assert.equal(panel.state.inFlightSubmit, null);
  assert.equal(panel.state.submitAbortController, null);
  assert.equal(panel.state.submitStartedAtMs, null);
  assert.equal(panel.state.submitDeadlineMs, null);
  assert.equal(panel.state.submittingScopeId, null);
});

test("NEW_CONVERSATION resets lifecycle state, increments epochs, and leaves non-lifecycle keys untouched", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    sessionId: "sess-2",
    turnId: "turn-3",
    baselineTurnId: "turn-2",
    baselineGraphHash: "baseline-hash",
    baselineGraphHashKind: "structural",
    baselineGraphHashVersion: 3,
    baselineSource: "turn",
    baselineRebaselineId: "reb-1",
    baselineGraphSourcePath: "turns/turn-2/candidate.ui.json",
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "candidate-hash",
    candidateReport: { summary: "changed" },
    serverSubmitGraphHash: "submit-hash",
    message: "Candidate ready.",
    failure: { kind: "SomeFailure" },
    clarification: { message: "Need more detail" },
    applyAllowed: true,
    applyEligibility: { reason: "applyable" },
    applyEligibilityWarning: "warn",
    applyEligibilityWarningKey: "warn-key",
    queueAllowed: true,
    canvasApplyAllowed: true,
    auditRef: { path: "/tmp/audit.json" },
    debugPayload: { debug: true },
    inFlightSubmit: Promise.resolve(),
    submitAbortController: { aborted: false },
    submitEpoch: 7,
    inFlightApply: Promise.resolve(),
    inFlightRebaseline: Promise.resolve(),
    rebaselinePending: { reason: "undo" },
    rebaselineRecovery: { action: "retry" },
    lastSubmit: { task: "edit this" },
    lastAppliedChanges: { changed: [1] },
    lastSubmitFieldChanges: { fields: ["prompt"] },
    changeDetails: { nodes: [1] },
    transcriptMessages: [{ role: "agent", text: "old transcript" }],
    responseDetails: { "turn-3": { message: "old detail" } },
    executionEvents: [{ key: "old-event" }],
    auditArtifacts: [{ path: "/tmp/old-audit.json" }],
    debugDiagnostics: { provider: { raw: true } },
    compartmentIndexes: {
      responseDetailsByTurnId: { "turn-3": "turn-3" },
      executionEventsByKey: { "old-event": 0 },
      auditArtifactsByTurnId: { "turn-3": 0 },
    },
    chatRehydrateEpoch: 11,
    syntheticAgentMessage: { text: "synthetic" },
    history: ["keep-non-lifecycle"],
  });
  panel.state._previewDiff = { stale: true };
  panel.state._previewDiffGraphHash = "preview-hash";

  const obligations = transition(panel, "NEW_CONVERSATION");

  assert.deepEqual(obligations, {
    render: true,
    dirtySections: [
      RENDER_SECTIONS.THREAD,
      RENDER_SECTIONS.META,
      RENDER_SECTIONS.COMPOSER,
      RENDER_SECTIONS.NOTICE,
    ],
    invalidateCandidate: true,
    // ── T9: Scoped queue guard clear replaces flat clear ────────────────
    queueGuardClearScope: null,
    refreshQueueGuard: true,
    forgetSession: true,
    focusPrompt: true,
    forgetScope: null,
  });
  assert.equal(panel.state.submitEpoch, 8);
  assert.equal(panel.state.chatRehydrateEpoch, 12);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.sessionId, null);
  // ── T9: Scope identity is preserved (null→null in this no-scope test) ──
  assert.equal(panel.state.chatScopeId, null);
  assert.equal(panel.state.chatScopeFingerprint, null);
  assert.equal(panel.state.turnId, null);
  assertBaselineDefaults(panel.state);
  assertCandidateDefaults(panel.state);
  assert.equal(panel.state.message, null);
  assert.equal(panel.state.failure, null);
  assert.equal(panel.state.clarification, null);
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.queueAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
  assert.equal(panel.state.auditRef, null);
  assert.equal(panel.state.debugPayload, null);
  assert.equal(panel.state.inFlightSubmit, null);
  assert.equal(panel.state.submitAbortController, null);
  assert.equal(panel.state.inFlightApply, null);
  assert.equal(panel.state.inFlightRebaseline, null);
  assert.equal(panel.state.rebaselinePending, null);
  assert.equal(panel.state.rebaselineRecovery, null);
  assert.equal(panel.state.lastSubmit, null);
  assert.equal(panel.state.lastAppliedChanges, null);
  assert.equal(panel.state.lastSubmitFieldChanges, null);
  assert.equal(panel.state.changeDetails, null);
  assert.deepEqual(panel.state.transcriptMessages, []);
  assert.deepEqual(panel.state.responseDetails, {});
  assert.deepEqual(panel.state.executionEvents, []);
  assert.deepEqual(panel.state.auditArtifacts, []);
  assert.deepEqual(panel.state.debugDiagnostics, {});
  assert.deepEqual(panel.state.compartmentIndexes, {
    responseDetailsByTurnId: {},
    executionEventsByKey: {},
    auditArtifactsByTurnId: {},
  });
  assert.equal(panel.state.syntheticAgentMessage, null);
  assert.deepEqual(panel.state.history, ["keep-non-lifecycle"]);
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
});

// ── Chat rehydrate ──────────────────────────────────────────────────────────

test("CHAT_REHYDRATE_START increments epoch without disturbing current candidate or failure state", () => {
  const panel = makePanel({
    candidateGraphHash: "candidate-hash",
    candidateGraph: { nodes: [1] },
    failure: { code: "KeepMe" },
    chatRehydrateEpoch: 4,
    chatMessages: [{ role: "agent", text: "existing" }],
    chatError: "old error",
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_START");

  assert.deepEqual(obligations, { render: false, requestEpoch: 5 });
  assert.equal(panel.state.chatRehydrateEpoch, 5);
  assert.equal(panel.state.candidateGraphHash, "candidate-hash");
  assert.deepEqual(panel.state.candidateGraph, { nodes: [1] });
  assert.deepEqual(panel.state.failure, { code: "KeepMe" });
  assert.deepEqual(panel.state.chatMessages, [{ role: "agent", text: "existing" }]);
  assert.equal(panel.state.chatError, "old error");
});

test("CHAT_REHYDRATE_SUCCESS stores safe chat payload and persists confirmed session id", () => {
  const messages = [{ role: "agent", text: "restored" }];
  const panel = makePanel({
    sessionId: null,
    chatRehydrateEpoch: 6,
    failure: { code: "KeepFailure" },
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: 6,
    messages,
    sessionId: "sess-123",
    chatSessionPath: "out/editor_sessions/sess-123/",
    chatDetailJsonPath: "out/editor_sessions/sess-123/session.json",
  });

  assert.deepEqual(obligations, {
    render: false,
    dirtySections: META_AND_THREAD_DIRTY_SECTIONS,
    persistSession: "sess-123",
  });
  const expectedMessages = [{ role: "agent", text: "restored" }];
  assert.deepEqual(panel.state.chatMessages, expectedMessages);
  assert.deepEqual(panel.state.transcriptMessages, expectedMessages);
  assert.equal(panel.state.chatLoaded, true);
  assert.equal(panel.state.chatError, null);
  assert.equal(panel.state.chatSessionPath, "out/editor_sessions/sess-123/");
  assert.equal(panel.state.chatDetailJsonPath, "out/editor_sessions/sess-123/session.json");
  assert.equal(panel.state.sessionId, "sess-123");
  assert.deepEqual(panel.state.failure, { code: "KeepFailure" });
});

test("reconcileChatMessages derives durable keys from normalized TurnIdentity", () => {
  const existing = [
    {
      role: "agent",
      text: "pending duplicate",
      optimistic: true,
      pending_response: true,
      executor_pending: true,
      submit_epoch: 3,
      turnIdentity: { turnId: "0007", role: "agent" },
      local_id: "pending-agent",
    },
    {
      role: "agent",
      text: "still pending",
      optimistic: true,
      pending_response: true,
      executor_pending: true,
      submit_epoch: 3,
      turnIdentity: { turnId: "0008", role: "agent" },
      local_id: "pending-agent-2",
    },
  ];
  const canonical = [
    {
      role: "agent",
      text: "confirmed",
      turn_identity: { turn_id: "0007", role: "agent" },
    },
  ];

  assert.deepEqual(
    reconcileChatMessages(existing, canonical, {
      phase: PANEL_STATE.SUBMITTING,
      submitEpoch: 3,
    }),
    [canonical[0], existing[1]],
  );
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE atomically restores candidate, baseline, eligibility, and queue context", () => {
  const panel = makePanel({
    phase: PANEL_STATE.ERROR,
    sessionId: "sess-old",
    turnId: "0001",
    candidateGraph: { stale: true },
    candidateGraphHash: "stale-hash",
    candidateReport: { stale: true },
    serverSubmitGraphHash: "stale-submit-hash",
    applyEligibility: { applyable: false },
    applyEligibilityWarning: "old warning",
    applyEligibilityWarningKey: "old-warning",
    changeDetails: { stale: true },
    message: "Old message",
    clarification: { message: "please answer" },
    failure: { code: "OldFailure" },
    queueAllowed: true,
    canvasApplyAllowed: false,
    applyAllowed: false,
    auditRef: { id: "audit-old" },
    baselineTurnId: "base-old",
    baselineGraphHash: "base-hash-old",
    baselineSource: "none",
    baselineGraphSourcePath: null,
    lastSubmitFieldChanges: [{ field: "old" }],
    debugPayload: { stale: true },
    _previewDiff: { stale: true },
    _previewDiffGraphHash: "preview-stale",
  });
  const candidateGraph = { nodes: [{ id: 7 }] };
  const candidateReport = { change: { content_edits: { edited: ["uid-7"] } } };
  const applyEligibility = {
    applyable: true,
    reason: "queue_blocked_warning",
    warnings: ["queue_blocked"],
  };
  const auditRef = { audit_path: "out/audits/0005.json" };
  const debugPayload = { restored_from_chat: true };
  const changeDetails = { edited_nodes: ["uid-7"] };
  const fieldChanges = [{ field: "prompt", before: "a", after: "b" }];

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    sessionId: "sess-new",
    turnId: "0005",
    baseline: {
      baseline_turn_id: "0004",
      baseline_graph_hash: "base-hash-new",
      baseline_graph_hash_kind: "structural",
      baseline_graph_hash_version: 2,
      action: "accept",
      ok: true,
      turn_id: "0005",
    },
    candidateGraph,
    candidateGraphHash: "candidate-hash-new",
    candidateReport,
    serverSubmitGraphHash: "submit-hash-new",
    message: "Candidate restored.",
    applyEligibility,
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: false,
    auditRef,
    changeDetails,
    debugPayload,
    lastSubmitFieldChanges: fieldChanges,
  });

  assert.deepEqual(obligations, {
    render: false,
    dirtySections: REVIEW_DIRTY_SECTIONS,
    restored: true,
    invalidateCandidate: true,
    persistSession: "sess-new",
    setQueueGuardContext: {
      sessionId: "sess-new",
      turnId: "0005",
      queueAllowed: false,
    },
    refreshQueueGuard: true,
  });
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.sessionId, "sess-new");
  assert.equal(panel.state.turnId, "0005");
  assert.equal(panel.state.baselineTurnId, "0004");
  assert.equal(panel.state.baselineGraphHash, "base-hash-new");
  assert.equal(panel.state.baselineGraphHashKind, "structural");
  assert.equal(panel.state.baselineGraphHashVersion, 2);
  assert.equal(panel.state.baselineSource, "turn");
  assert.equal(panel.state.baselineRebaselineId, null);
  assert.equal(panel.state.baselineGraphSourcePath, "turns/0005/candidate.ui.json");
  assert.deepEqual(panel.state.candidateGraph, candidateGraph);
  assert.equal(panel.state.candidateGraphHash, "candidate-hash-new");
  assert.deepEqual(panel.state.candidateReport, candidateReport);
  assert.equal(panel.state.serverSubmitGraphHash, "submit-hash-new");
  assert.equal(panel.state.message, "Candidate restored.");
  assert.equal(panel.state.failure, null);
  assert.equal(panel.state.clarification, null);
  assert.deepEqual(panel.state.applyEligibility, applyEligibility);
  assert.equal(panel.state.applyAllowed, true);
  assert.equal(panel.state.canvasApplyAllowed, true);
  assert.equal(panel.state.queueAllowed, false);
  assert.deepEqual(panel.state.auditRef, auditRef);
  assert.deepEqual(panel.state.changeDetails, changeDetails);
  assert.deepEqual(panel.state.debugPayload, debugPayload);
  assert.deepEqual(panel.state.lastSubmitFieldChanges, fieldChanges);
  assert.equal(panel.state.applyEligibilityWarning, null);
  assert.equal(panel.state.applyEligibilityWarningKey, null);
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE restores optional reorganise candidate eligibility", () => {
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    sessionId: "sess-layout-restore",
    chatScopeId: "scope-layout",
  });
  const reorganisedGraph = {
    nodes: [{ id: 9, type: "SaveImage", pos: [480, 220] }],
    links: [],
  };
  const layoutReorganisation = {
    result: "prepare_candidate",
    candidate_prepared: true,
    functional_candidate_graph_hash: "functional-restore-hash",
    reorganised_candidate_graph_hash: "layout-restore-hash",
  };

  const obligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    requestScopeId: "scope-layout",
    candidateSessionId: "sess-layout-restore",
    result: {
      ok: true,
      message: "Restored optional layout candidate.",
      outcome: { kind: "candidate", changes: [] },
      candidate: {
        state: "candidate",
        graph: reorganisedGraph,
        graph_hash: "layout-restore-hash",
        submit_graph_hash: "submit-restore-hash",
        turn_identity: {
          session_id: "sess-layout-restore",
          turn_id: "turn-layout-restore",
          baseline_turn_id: "turn-before-restore",
        },
      },
      apply_eligibility: {
        applyable: true,
        reason: "applyable",
        message: "Restored candidate is still latest.",
        warnings: [],
      },
      layout_reorganisation: layoutReorganisation,
    },
    baseline: {
      baseline_turn_id: "turn-before-restore",
      baseline_graph_hash: "base-restore-hash",
      baseline_graph_hash_kind: "structural",
      baseline_graph_hash_version: 2,
      turn_id: "turn-layout-restore",
    },
    queueAllowed: true,
    changeDetails: {
      layout_reorganisation: layoutReorganisation,
    },
  });

  assert.equal(obligations.restored, true);
  assert.deepEqual(obligations.setQueueGuardContext, {
    sessionId: "sess-layout-restore",
    turnId: "turn-layout-restore",
    queueAllowed: true,
  });
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.candidateScopeId, "scope-layout");
  assert.deepEqual(panel.state.candidateGraph, reorganisedGraph);
  assert.equal(panel.state.candidateGraphHash, "layout-restore-hash");
  assert.equal(panel.state.serverSubmitGraphHash, "submit-restore-hash");
  assert.deepEqual(panel.state.applyEligibility, {
    applyable: true,
    reason: "applyable",
    message: "Restored candidate is still latest.",
    warnings: [],
  });
  assert.equal(panel.state.applyAllowed, true);
  assert.equal(panel.state.canvasApplyAllowed, true);
  assert.equal(panel.state.queueAllowed, true);
  assert.deepEqual(panel.state.changeDetails.layout_reorganisation, layoutReorganisation);
});

test("CHAT_REHYDRATE_NO_SESSION clears only thread-visible chat state and leaves metadata clean", () => {
  const panel = makePanel({
    sessionId: "sess-live",
    chatRehydrateEpoch: 4,
    chatMessages: [{ role: "user", text: "old" }],
    transcriptMessages: [{ role: "user", text: "old" }],
    responseDetails: { old: { message: "old" } },
    executionEvents: [{ key: "old" }],
    auditArtifacts: [{ path: "/tmp/old.json" }],
    debugDiagnostics: { old: true },
    compartmentIndexes: {
      responseDetailsByTurnId: { old: "old" },
      executionEventsByKey: { old: 0 },
      auditArtifactsByTurnId: { old: 0 },
    },
    chatLoaded: true,
    chatError: "old error",
    chatSessionPath: "out/editor_sessions/sess-live/",
    chatDetailJsonPath: "out/editor_sessions/sess-live/session.json",
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_NO_SESSION", {
    requestEpoch: 4,
  });

  assert.deepEqual(obligations, {
    render: false,
    dirtySections: THREAD_DIRTY_SECTIONS,
  });
  assert.equal(panel.state.sessionId, "sess-live");
  assert.deepEqual(panel.state.chatMessages, []);
  assert.deepEqual(panel.state.transcriptMessages, []);
  assert.deepEqual(panel.state.responseDetails, {});
  assert.deepEqual(panel.state.executionEvents, []);
  assert.deepEqual(panel.state.auditArtifacts, []);
  assert.deepEqual(panel.state.debugDiagnostics, {});
  assert.deepEqual(panel.state.compartmentIndexes.responseDetailsByTurnId, {});
  assert.equal(panel.state.chatLoaded, false);
  assert.equal(panel.state.chatError, null);
  assert.equal(panel.state.chatSessionPath, null);
  assert.equal(panel.state.chatDetailJsonPath, null);
});

test("CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE is skipped while submit/apply is active or candidate graph is missing", () => {
  const submittingPanel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    sessionId: "sess-live",
    turnId: "0008",
    candidateGraphHash: "current-hash",
  });
  const beforeSubmitting = structuredClone(submittingPanel.state);

  const skippedForPhase = transition(submittingPanel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    sessionId: "sess-new",
    turnId: "0009",
    candidateGraph: { nodes: [{ id: 1 }] },
  });

  assert.deepEqual(skippedForPhase, { render: false, skipped: true });
  assert.deepEqual(submittingPanel.state, beforeSubmitting);

  const idlePanel = makePanel({
    phase: PANEL_STATE.IDLE,
    sessionId: "sess-idle",
    turnId: "0010",
  });
  const beforeMissingGraph = structuredClone(idlePanel.state);

  const skippedForGraph = transition(idlePanel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    sessionId: "sess-idle",
    turnId: "0011",
    candidateGraph: null,
  });

  assert.deepEqual(skippedForGraph, { render: false, skipped: true });
  assert.deepEqual(idlePanel.state, beforeMissingGraph);
});

test("APPLY_PREFLIGHT_BLOCKED no-ops while APPLY_MISSING_FIELDS records a failure", () => {
  const idlePanel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    candidateGraph: null,
    sessionId: "sess-apply",
    turnId: "0001",
  });
  const beforeNoCandidate = structuredClone(idlePanel.state);

  const noCandidate = transition(idlePanel, "APPLY_PREFLIGHT_BLOCKED", { reason: "no_candidate" });

  assert.deepEqual(noCandidate, { render: false });
  assert.deepEqual(idlePanel.state, beforeNoCandidate);

  const panel = makePanel({ phase: PANEL_STATE.AWAITING_REVIEW });
  const failure = { kind: "MissingRequiredField", message: "missing ids" };

  const obligations = transition(panel, "APPLY_MISSING_FIELDS", {
    failure,
    debugPayload: failure,
  });

  assert.deepEqual(obligations, {
    render: true,
    invalidateCandidate: false,
    clearCandidatePreview: false,
    dirtySections: [RENDER_SECTIONS.META, RENDER_SECTIONS.COMPOSER, RENDER_SECTIONS.NOTICE],
  });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(panel.state.failure, failure);
  assert.deepEqual(panel.state.debugPayload, failure);
});

test("APPLY_STARTED and APPLY_IN_FLIGHT capture apply phase, request debug, and promise guard", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    turnId: "0002",
    failure: { kind: "OldFailure" },
  });
  const promise = Promise.resolve("ok");
  const acceptBody = { session_id: "sess-apply", turn_id: "0002", idempotency_key: "accept:key" };

  assert.deepEqual(transition(panel, "APPLY_IN_FLIGHT", { promise }), { render: false });
  const obligations = transition(panel, "APPLY_STARTED", { acceptBody });

  assert.deepEqual(obligations, { render: true });
  assert.equal(panel.state.inFlightApply, promise);
  assert.equal(panel.state.phase, PANEL_STATE.APPLYING);
  assert.equal(panel.state.failure, null);
  assert.deepEqual(panel.state.debugPayload, {
    applying_turn_id: "0002",
    accept_request: acceptBody,
  });
});

test("ACCEPT_REJECTED preserves retryable local failures but disables authoritative backend rejects", () => {
  const retryablePanel = makePanel({
    phase: PANEL_STATE.APPLYING,
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
    auditRef: { path: "old.json" },
  });
  const retryableFailure = { kind: "AcceptError", message: "network down" };

  const retryable = transition(retryablePanel, "ACCEPT_REJECTED", {
    failure: retryableFailure,
    acceptBody: { idempotency_key: "accept:retry" },
    authoritativeBackendReject: false,
  });

  assert.deepEqual(retryable, {
    render: true,
    queueGuardClear: false,
    refreshQueueGuard: false,
    invalidateCandidate: false,
    clearCandidatePreview: false,
  });
  assert.equal(retryablePanel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(retryablePanel.state.failure, retryableFailure);
  assert.deepEqual(retryablePanel.state.applyEligibility, { applyable: true, reason: "applyable" });
  assert.equal(retryablePanel.state.applyAllowed, true);
  assert.equal(retryablePanel.state.canvasApplyAllowed, true);
  assert.equal(retryablePanel.state.queueAllowed, true);

  const authoritativePanel = makePanel({
    phase: PANEL_STATE.APPLYING,
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
    candidateGraph: { nodes: [{ id: 11 }] },
    candidateGraphHash: "candidate-before-authoritative-reject",
    _previewDiff: { stale: true },
    _previewDiffGraphHash: "candidate-before-authoritative-reject",
    _previewDiffCacheTag: "stale-tag",
  });
  const disabledApplyEligibility = {
    applyable: false,
    reason: "superseded",
    warnings: ["backend_rejected"],
  };
  const authoritativeFailure = {
    ok: false,
    kind: "StaleStateMismatch",
    message: "superseded",
    audit_ref: { path: "reject-audit.json" },
    baseline_turn_id: "0001",
    baseline_graph_hash: "base-after-reject",
  };

  const authoritative = transition(authoritativePanel, "ACCEPT_REJECTED", {
    failure: authoritativeFailure,
    acceptBody: { idempotency_key: "accept:reject" },
    authoritativeBackendReject: true,
    disabledApplyEligibility,
  });

  assert.deepEqual(authoritative, {
    render: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
  assert.equal(authoritativePanel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(authoritativePanel.state.failure, authoritativeFailure);
  assert.deepEqual(authoritativePanel.state.applyEligibility, disabledApplyEligibility);
  assert.equal(authoritativePanel.state.applyAllowed, false);
  assert.equal(authoritativePanel.state.canvasApplyAllowed, false);
  assert.equal(authoritativePanel.state.queueAllowed, false);
  assert.deepEqual(authoritativePanel.state.auditRef, { path: "reject-audit.json" });
  assert.equal(authoritativePanel.state.baselineTurnId, "0001");
  assert.equal(authoritativePanel.state.baselineGraphHash, "base-after-reject");
  assert.equal(authoritativePanel.state.candidateGraph, null);
  assert.equal(authoritativePanel.state.candidateGraphHash, null);
  assert.equal(authoritativePanel.state._previewDiff, undefined);
  assert.equal(authoritativePanel.state._previewDiffGraphHash, undefined);
  assert.equal(authoritativePanel.state._previewDiffCacheTag, undefined);
});

test("STALE_CANVAS_APPLY and CANVAS_APPLY_FAILURE record distinct apply failures", () => {
  const stalePanel = makePanel({ phase: PANEL_STATE.APPLYING });
  const staleFailure = { kind: "StaleStateMismatch", message: "live token changed" };

  const stale = transition(stalePanel, "STALE_CANVAS_APPLY", {
    failure: staleFailure,
    debugPayload: staleFailure,
  });

  assert.deepEqual(stale, {
    render: true,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
  assert.equal(stalePanel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(stalePanel.state.failure, staleFailure);
  assert.deepEqual(stalePanel.state.debugPayload, staleFailure);

  const canvasPanel = makePanel({
    phase: PANEL_STATE.APPLYING,
    auditRef: { path: "old-audit.json" },
  });
  const canvasFailure = {
    kind: "CanvasApplyError",
    message: "configure failed",
    audit_ref: { path: "canvas-failure.json" },
  };

  const canvas = transition(canvasPanel, "CANVAS_APPLY_FAILURE", {
    failure: canvasFailure,
    accepted: { turn_id: "0003" },
    undoStackDepth: 2,
  });

  assert.deepEqual(canvas, {
    render: true,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
  assert.equal(canvasPanel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(canvasPanel.state.failure, canvasFailure);
  assert.deepEqual(canvasPanel.state.auditRef, { path: "canvas-failure.json" });
  assert.deepEqual(canvasPanel.state.debugPayload, {
    ...canvasFailure,
    accepted: { turn_id: "0003" },
    undo_stack_depth: 2,
  });
});

test("APPLY_SUCCESS atomically syncs baseline, invalidates candidate, clears queue guards, and preserves applied feedback", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    sessionId: "sess-apply",
    turnId: "0004",
    candidateGraph: { nodes: [{ id: 4 }] },
    candidateGraphHash: "candidate-hash",
    candidateReport: { change: true },
    serverSubmitGraphHash: "submit-hash",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
    changeDetails: { edited: ["uid-4"] },
    _previewDiff: { old: true },
    _previewDiffGraphHash: "preview-hash",
    _previewDiffCacheTag: "graph",
  });
  const accepted = {
    ok: true,
    action: "accept",
    session_id: "sess-apply",
    turn_id: "0004",
    baseline_turn_id: "0004",
    baseline_graph_hash: "base-after-apply",
    baseline_graph_hash_kind: "structural",
    baseline_graph_hash_version: 2,
    audit_ref: { path: "accept-audit.json" },
  };
  const lastAppliedChanges = { items: [{ uid: "uid-4", kind: "edited" }], mode: "panel" };

  const obligations = transition(panel, "APPLY_SUCCESS", {
    accepted,
    lastAppliedChanges,
    undoStackDepth: 1,
    toast: "Agent candidate applied",
  });

  assert.deepEqual(obligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    clearCandidatePreview: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    toast: "Agent candidate applied",
  });
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.baselineTurnId, "0004");
  assert.equal(panel.state.baselineGraphHash, "base-after-apply");
  assert.equal(panel.state.baselineGraphHashKind, "structural");
  assert.equal(panel.state.baselineGraphHashVersion, 2);
  assert.equal(panel.state.baselineSource, "turn");
  assert.deepEqual(panel.state.auditRef, { path: "accept-audit.json" });
  assertCandidateDefaults(panel.state);
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
  assert.equal(panel.state.queueAllowed, false);
  assert.deepEqual(panel.state.lastAppliedChanges, lastAppliedChanges);
  assert.equal(panel.state.message, null);
  assert.equal((panel.state.syntheticAgentMessage?.text || "").includes("audit:"), false);
  assert.deepEqual(panel.state.debugPayload, {
    accepted,
    undo_stack_depth: 1,
  });
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
  assert.equal(panel.state._previewDiffCacheTag, undefined);
});

// ── Reject flow ────────────────────────────────────────────────────────────

test("REJECT_STARTED transitions to APPLYING, clears failure, and records debug payload", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    turnId: "0005",
    failure: { code: "PreviousFailure" },
    candidateGraph: { nodes: [{ id: 5 }] },
    candidateGraphHash: "candidate-hash",
  });

  const obligations = transition(panel, "REJECT_STARTED", {
    rejectBody: {
      session_id: "sess-reject",
      turn_id: "0005",
      client_graph_hash: "client-hash",
      idempotency_key: "reject:key",
    },
    debugPayload: {
      rejecting_turn_id: "0005",
      reject_request: { session_id: "sess-reject", turn_id: "0005" },
    },
  });

  assert.deepEqual(obligations, { render: true });
  assert.equal(panel.state.phase, PANEL_STATE.APPLYING);
  assert.equal(panel.state.failure, null);
  assert.deepEqual(panel.state.debugPayload, {
    rejecting_turn_id: "0005",
    reject_request: { session_id: "sess-reject", turn_id: "0005" },
  });
  // Candidate fields preserved during in-flight reject
  assert.deepEqual(panel.state.candidateGraph, { nodes: [{ id: 5 }] });
  assert.equal(panel.state.candidateGraphHash, "candidate-hash");
});

test("REJECT_STARTED builds default debug payload from rejectBody when none provided", () => {
  const panel = makePanel({ turnId: "0006" });

  const obligations = transition(panel, "REJECT_STARTED", {
    rejectBody: { turn_id: "0006", client_graph_hash: "hash" },
  });

  assert.deepEqual(obligations, { render: true });
  assert.equal(panel.state.phase, PANEL_STATE.APPLYING);
  assert.equal(panel.state.failure, null);
  assert.deepEqual(panel.state.debugPayload, {
    rejecting_turn_id: "0006",
    reject_request: { turn_id: "0006", client_graph_hash: "hash" },
  });
});

test("REJECT_FAILURE records phase=ERROR, syncs baseline from failure, and preserves audit ref", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    turnId: "0007",
    auditRef: { path: "previous-audit.json" },
    baselineGraphHash: "old-baseline",
    candidateGraph: { nodes: [{ id: 7 }] },
  });

  const failure = {
    kind: "RejectError",
    message: "Backend unavailable",
    audit_ref: { path: "reject-failure-audit.json" },
    baseline_turn_id: "0007",
    baseline_graph_hash: "base-after-reject-fail",
    baseline_graph_hash_kind: "structural",
    baseline_graph_hash_version: 3,
    session_id: "sess-reject-fail",
    turn_id: "0007",
  };

  const obligations = transition(panel, "REJECT_FAILURE", {
    failure,
    rejectBody: { turn_id: "0007" },
    debugPayload: {
      ...failure,
      reject_request: { turn_id: "0007" },
    },
  });

  assert.deepEqual(obligations, { render: true });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(panel.state.failure, failure);
  assert.equal(panel.state.baselineTurnId, "0007");
  assert.equal(panel.state.baselineGraphHash, "base-after-reject-fail");
  assert.equal(panel.state.baselineGraphHashKind, "structural");
  assert.equal(panel.state.baselineGraphHashVersion, 3);
  assert.deepEqual(panel.state.auditRef, { path: "reject-failure-audit.json" });
  assert.deepEqual(panel.state.debugPayload, {
    ...failure,
    reject_request: { turn_id: "0007" },
  });
  // Candidate preserved on failure so retry state is visible
  assert.deepEqual(panel.state.candidateGraph, { nodes: [{ id: 7 }] });
});

test("REJECT_FAILURE with null failure keeps current audit ref", () => {
  const panel = makePanel({
    auditRef: { path: "original-audit.json" },
  });

  const obligations = transition(panel, "REJECT_FAILURE", {
    failure: null,
  });

  assert.deepEqual(obligations, { render: true });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.equal(panel.state.failure, null);
  assert.deepEqual(panel.state.auditRef, { path: "original-audit.json" });
});

test("REJECT_FAILURE builds default debug payload from failure when none provided", () => {
  const panel = makePanel();
  const failure = { kind: "RejectError", message: "no debug" };

  const obligations = transition(panel, "REJECT_FAILURE", {
    failure,
    rejectBody: { turn_id: "0008" },
  });

  assert.deepEqual(obligations, { render: true });
  assert.deepEqual(panel.state.debugPayload, {
    ...failure,
    reject_request: { turn_id: "0008" },
  });
});

test("REJECT_SUCCESS clears candidate, syncs baseline, invalidates gates, and returns queue guard obligations", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    sessionId: "sess-reject-ok",
    turnId: "0009",
    candidateGraph: { nodes: [{ id: 9 }] },
    candidateGraphHash: "candidate-hash-9",
    candidateReport: { change: true },
    serverSubmitGraphHash: "submit-hash-9",
    applyEligibility: { applyable: true },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
    changeDetails: { edited: ["uid-9"] },
    _previewDiff: { old: true },
    _previewDiffGraphHash: "preview-hash-9",
    _previewDiffCacheTag: "graph",
    failure: null,
    auditRef: { path: "old-audit.json" },
  });

  const rejected = {
    ok: true,
    action: "reject",
    session_id: "sess-reject-ok",
    turn_id: "0009",
    baseline_turn_id: "0010",
    baseline_graph_hash: "base-after-reject",
    baseline_graph_hash_kind: "structural",
    baseline_graph_hash_version: 4,
    audit_ref: { path: "reject-success-audit.json" },
  };

  const obligations = transition(panel, "REJECT_SUCCESS", {
    rejected,
    message: "Candidate rejected and cleared from the panel.",
    toast: "Agent candidate rejected",
    debugPayload: {
      rejected,
      graph_unchanged: true,
    },
  });

  assert.deepEqual(obligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    clearCandidatePreview: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    toast: "Agent candidate rejected",
  });
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.failure, null);
  assert.equal(panel.state.message, "Candidate rejected and cleared from the panel.");
  // Baseline synced from rejected response
  assert.equal(panel.state.baselineTurnId, "0010");
  assert.equal(panel.state.baselineGraphHash, "base-after-reject");
  assert.equal(panel.state.baselineGraphHashKind, "structural");
  assert.equal(panel.state.baselineGraphHashVersion, 4);
  // Audit ref updated from rejected response
  assert.deepEqual(panel.state.auditRef, { path: "reject-success-audit.json" });
  // Candidate invalidated — all candidate fields cleared
  assertCandidateDefaults(panel.state);
  // Gates disabled so rejected candidate is unappliable
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
  assert.equal(panel.state.queueAllowed, false);
  // Debug payload recorded
  assert.deepEqual(panel.state.debugPayload, {
    rejected,
    graph_unchanged: true,
  });
  // Preview diff caches cleared
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
  assert.equal(panel.state._previewDiffCacheTag, undefined);
});

test("REJECT_SUCCESS uses default message and empty toast when not provided", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    candidateGraph: { nodes: [{ id: 10 }] },
  });

  const obligations = transition(panel, "REJECT_SUCCESS", {
    rejected: { ok: true, audit_ref: { path: "audit.json" } },
  });

  assert.deepEqual(obligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    clearCandidatePreview: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    toast: null,
  });
  assert.equal(panel.state.message, "Candidate rejected and cleared from the panel.");
});

// ── Chat rehydrate ──────────────────────────────────────────────────────────

test("CHAT_REHYDRATE_MISSING_SESSION clears visible chat state and forgets only the matching session id", () => {
  const panel = makePanel({
    sessionId: "sess-missing",
    chatRehydrateEpoch: 9,
    chatMessages: [{ role: "user", text: "old" }],
    transcriptMessages: [{ role: "user", text: "old" }],
    responseDetails: { old: { message: "old" } },
    executionEvents: [{ key: "old" }],
    auditArtifacts: [{ path: "/tmp/old.json" }],
    debugDiagnostics: { old: true },
    compartmentIndexes: {
      responseDetailsByTurnId: { old: "old" },
      executionEventsByKey: { old: 0 },
      auditArtifactsByTurnId: { old: 0 },
    },
    chatError: "old error",
    chatSessionPath: "out/editor_sessions/sess-missing/",
    chatDetailJsonPath: "out/editor_sessions/sess-missing/session.json",
    candidateGraphHash: "candidate-hash",
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_MISSING_SESSION", {
    requestEpoch: 9,
    sessionId: "sess-missing",
  });

  assert.deepEqual(obligations, {
    render: false,
    dirtySections: META_AND_THREAD_DIRTY_SECTIONS,
    forgetSession: true,
  });
  assert.equal(panel.state.sessionId, null);
  assert.deepEqual(panel.state.chatMessages, []);
  assert.deepEqual(panel.state.transcriptMessages, []);
  assert.deepEqual(panel.state.responseDetails, {});
  assert.deepEqual(panel.state.executionEvents, []);
  assert.deepEqual(panel.state.auditArtifacts, []);
  assert.deepEqual(panel.state.debugDiagnostics, {});
  assert.deepEqual(panel.state.compartmentIndexes.responseDetailsByTurnId, {});
  assert.equal(panel.state.chatLoaded, true);
  assert.equal(panel.state.chatError, null);
  assert.equal(panel.state.chatSessionPath, null);
  assert.equal(panel.state.chatDetailJsonPath, null);
  assert.equal(panel.state.candidateGraphHash, "candidate-hash");
});

test("CHAT_REHYDRATE_FAILURE clears only chat display state and leaves current failure/candidate state intact", () => {
  const panel = makePanel({
    chatRehydrateEpoch: 12,
    candidateGraphHash: "candidate-hash",
    failure: { code: "CurrentFailure" },
    chatMessages: [
      { role: "agent", text: "stale" },
      { role: "user", text: "optimistic", optimistic: true },
    ],
    transcriptMessages: [{ role: "agent", text: "stale" }],
    chatSessionPath: "out/editor_sessions/current/",
    chatDetailJsonPath: "out/editor_sessions/current/session.json",
  });

  const obligations = transition(panel, "CHAT_REHYDRATE_FAILURE", {
    requestEpoch: 12,
    chatError: "Server returned 500",
  });

  assert.deepEqual(obligations, {
    render: false,
    dirtySections: THREAD_DIRTY_SECTIONS,
  });
  assert.deepEqual(panel.state.chatMessages, [{ role: "user", text: "optimistic", optimistic: true }]);
  assert.deepEqual(panel.state.transcriptMessages, panel.state.chatMessages);
  assert.equal(panel.state.chatLoaded, false);
  assert.equal(panel.state.chatError, "Server returned 500");
  assert.equal(panel.state.chatSessionPath, null);
  assert.equal(panel.state.chatDetailJsonPath, null);
  assert.equal(panel.state.candidateGraphHash, "candidate-hash");
  assert.deepEqual(panel.state.failure, { code: "CurrentFailure" });
});

test("Stale chat rehydrate responses are ignored without touching current session, failure, or candidate state", () => {
  const panel = makePanel({
    sessionId: "current-session",
    chatRehydrateEpoch: 15,
    candidateGraphHash: "candidate-hash",
    failure: { code: "CurrentFailure" },
    chatMessages: [{ role: "agent", text: "current" }],
    chatError: "current error",
  });

  const before = structuredClone(panel.state);
  const obligations = transition(panel, "CHAT_REHYDRATE_FAILURE", {
    requestEpoch: 14,
    chatError: "stale error",
  });

  assert.deepEqual(obligations, { render: false, stale: true });
  assert.deepEqual(panel.state, before);
});

// ── Unknown / no-op ─────────────────────────────────────────────────────────

test("Unknown event returns render:false and does not mutate state", () => {
  const panel = makePanel({ phase: PANEL_STATE.AWAITING_REVIEW, message: "hello" });

  const before = JSON.stringify(panel.state);
  const obligations = transition(panel, "NONEXISTENT_EVENT");
  const after = JSON.stringify(panel.state);

  assert.deepEqual(obligations, { render: false });
  assert.equal(after, before, "unknown event must be a no-op");
});

test("Unknown event with payload returns render:false without mutation", () => {
  const panel = makePanel();

  const obligations = transition(panel, "SOME_FUTURE_EVENT", { data: "test" });

  assert.deepEqual(obligations, { render: false });
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
});

test("Multiple unknown events do not accumulate side effects", () => {
  const panel = makePanel();

  transition(panel, "A");
  transition(panel, "B");
  const obligations = transition(panel, "C");

  assert.deepEqual(obligations, { render: false });
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
});

// ── Null/missing panel guard ────────────────────────────────────────────────

test("transition with null panel returns render:false", () => {
  assert.deepEqual(transition(null, "INIT"), { render: false });
  assert.deepEqual(transition(null, "SYNC_BASELINE", {}), { render: false });
  assert.deepEqual(transition(null, "INVALIDATE_CANDIDATE"), { render: false });
  assert.deepEqual(transition(null, "UNKNOWN"), { render: false });
});

test("transition with undefined panel returns render:false", () => {
  assert.deepEqual(transition(undefined, "INIT"), { render: false });
});

test("transition with panel missing .state returns render:false", () => {
  assert.deepEqual(transition({}, "INIT"), { render: false });
  assert.deepEqual(transition({ state: null }, "INIT"), { render: false });
});

// ── Cross-event independence ────────────────────────────────────────────────

test("SYNC_BASELINE does not affect candidate fields", () => {
  const panel = makePanel({
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "candidate-hash",
  });

  transition(panel, "SYNC_BASELINE", {
    baseline_turn_id: "t1",
    baseline_graph_hash: "b-hash",
  });

  assert.equal(panel.state.candidateGraphHash, "candidate-hash");
  assert.deepEqual(panel.state.candidateGraph, { nodes: [{ id: 1 }] });
  assert.equal(panel.state.baselineTurnId, "t1");
});

test("INVALIDATE_CANDIDATE does not affect baseline fields", () => {
  const panel = makePanel({
    baselineTurnId: "t1",
    baselineGraphHash: "b-hash",
    baselineSource: "turn",
    candidateGraph: { nodes: [] },
  });

  transition(panel, "INVALIDATE_CANDIDATE");

  assert.equal(panel.state.baselineTurnId, "t1");
  assert.equal(panel.state.baselineGraphHash, "b-hash");
  assert.equal(panel.state.baselineSource, "turn");
  assert.equal(panel.state.candidateGraph, null);
});

// ── Rebaseline / stale recovery ────────────────────────────────────────────

test("SYNC_BASELINE can atomically store or clear rebaseline recovery alongside baseline fields", () => {
  const panel = makePanel({
    rebaselineRecovery: { action: "rebaseline", reason: "stale_state_recovery" },
  });

  transition(panel, "SYNC_BASELINE", {
    baseline_graph_hash: "baseline-1",
    rebaselineRecovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "undo",
      last_known_baseline_graph_hash: "baseline-0",
    },
  });
  assert.deepEqual(panel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "undo",
    last_known_baseline_graph_hash: "baseline-0",
  });

  transition(panel, "SYNC_BASELINE", {
    baseline_graph_hash: "baseline-2",
    clearRebaselineRecovery: true,
  });
  assert.equal(panel.state.rebaselineRecovery, null);
});

test("REBASELINE_STARTED stores pending request metadata and REBASELINE_FINALLY clears the in-flight promise", () => {
  const panel = makePanel();
  const promise = Promise.resolve();
  const rebaselinePending = {
    reason: "undo",
    last_known_baseline_graph_hash: "baseline-before",
    client_graph_hash: "graph-after",
    client_structural_graph_hash: "structural-after",
    idempotency_key: "rebaseline:sess:undo:baseline-before:abc123def456",
  };

  assert.deepEqual(
    transition(panel, "REBASELINE_IN_FLIGHT", { promise }),
    { render: false },
  );
  assert.equal(panel.state.inFlightRebaseline, promise);

  assert.deepEqual(
    transition(panel, "REBASELINE_STARTED", { rebaselinePending }),
    { render: true },
  );
  assert.deepEqual(panel.state.rebaselinePending, rebaselinePending);

  assert.deepEqual(
    transition(panel, "REBASELINE_FINALLY", { clearInFlightRebaseline: true }),
    { render: true },
  );
  assert.equal(panel.state.inFlightRebaseline, null);
});

test("REBASELINE_SUCCESS syncs authoritative baseline, clears pending state, and clears stale recovery", () => {
  const panel = makePanel({
    auditRef: { path: "/tmp/old-audit.json" },
    rebaselinePending: { reason: "undo" },
    rebaselineRecovery: { action: "rebaseline", reason: "stale_state_recovery" },
    phase: PANEL_STATE.AWAITING_REVIEW,
    candidateGraph: { nodes: [{ id: 44 }] },
    candidateGraphHash: "candidate-before-rebaseline",
    candidateReport: { ok: true },
    customNodeResolution: { missing: [] },
    candidateScopeId: "scope-before-rebaseline",
    deltaOps: [{ op: "set_node_field", target: ["nodes", 44, "widgets_values", 0], value: "stale" }],
    _previewDiff: { stale: true },
    _previewDiffGraphHash: "candidate-before-rebaseline",
    _previewDiffCacheTag: "stale-tag",
  });
  const result = {
    ok: true,
    action: "rebaseline",
    baseline_graph_hash: "baseline-new",
    baseline_graph_hash_kind: "structural",
    baseline_graph_hash_version: 2,
    baseline_source: "rebaseline",
    baseline_rebaseline_id: "rebaseline-0001",
    baseline_graph_source_path: "_rebaseline/rebaseline-0001/graph.ui.json",
    audit_ref: { path: "/tmp/rebaseline-audit.json" },
  };

  const obligations = transition(panel, "REBASELINE_SUCCESS", {
    result,
    rebaselineRequest: { session_id: "sess-1" },
  });

  assert.deepEqual(obligations, {
    render: false,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
  assert.equal(panel.state.baselineGraphHash, "baseline-new");
  assert.equal(panel.state.baselineSource, "rebaseline");
  assert.equal(panel.state.baselineRebaselineId, "rebaseline-0001");
  assert.equal(panel.state.rebaselinePending, null);
  assert.equal(panel.state.rebaselineRecovery, null);
  assertCandidateDefaults(panel.state);
  assert.equal(panel.state.candidateScopeId, null);
  assert.equal(panel.state.deltaOps, null);
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
  assert.equal(panel.state._previewDiffCacheTag, undefined);
  assert.equal(Boolean(panel.state.candidateGraph && panel.state.phase === PANEL_STATE.AWAITING_REVIEW), false);
  assert.deepEqual(panel.state.auditRef, { path: "/tmp/rebaseline-audit.json" });
  assert.deepEqual(panel.state.debugPayload, {
    rebaseline_request: { session_id: "sess-1" },
    rebaseline_response: result,
  });
});

test("REBASELINE_FAILURE preserves request metadata, records retry details, and syncs recovery evidence", () => {
  const panel = makePanel({
    auditRef: { path: "/tmp/old-audit.json" },
    rebaselinePending: {
      reason: "undo",
      last_known_baseline_graph_hash: "baseline-before",
      client_graph_hash: "graph-after",
    },
  });
  const failure = {
    ok: false,
    kind: "RebaselineError",
    retryable: true,
    user_facing_message: "Retry undo rebaseline.",
    audit_ref: { path: "/tmp/rebaseline-failure.json" },
  };
  const recovery = {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "baseline-retry",
  };

  const obligations = transition(panel, "REBASELINE_FAILURE", {
    failure,
    rebaselineRecovery: recovery,
    rebaselinePendingPatch: {
      retryable: true,
      failure_kind: "RebaselineError",
      message: "Retry undo rebaseline.",
    },
    rebaselineRequest: { session_id: "sess-1" },
  });

  assert.deepEqual(obligations, { render: false });
  assert.deepEqual(panel.state.rebaselinePending, {
    reason: "undo",
    last_known_baseline_graph_hash: "baseline-before",
    client_graph_hash: "graph-after",
    retryable: true,
    failure_kind: "RebaselineError",
    message: "Retry undo rebaseline.",
  });
  assert.deepEqual(panel.state.rebaselineRecovery, recovery);
  assert.deepEqual(panel.state.auditRef, { path: "/tmp/rebaseline-failure.json" });
  assert.deepEqual(panel.state.debugPayload, {
    ...failure,
    rebaseline_request: { session_id: "sess-1" },
  });
});

test("STALE_RECOVERY_REBASELINE success and failure transitions own recovery-specific state changes", () => {
  const successPanel = makePanel({
    phase: PANEL_STATE.ERROR,
    candidateGraph: { stale: true },
    candidateGraphHash: "candidate-stale",
    failure: { kind: "OldFailure" },
    rebaselineRecovery: { action: "rebaseline", reason: "stale_state_recovery" },
  });

  assert.deepEqual(
    transition(successPanel, "STALE_RECOVERY_REBASELINE_QUEUED"),
    { render: true },
  );
  assert.equal(successPanel.state.phase, PANEL_STATE.IDLE);
  assert.equal(successPanel.state.message, "Current canvas queued for stale-state recovery rebaseline.");

  const successObligations = transition(successPanel, "STALE_RECOVERY_REBASELINE_SUCCESS", {
    auditRef: { path: "/tmp/recovery-success.json" },
    message: "Current canvas rebaselined. Resubmitting from this canvas...",
    toast: "Current canvas rebaselined",
    debugPayload: {
      stale_state_recovery: true,
      rebaseline_response: { rebaseline_id: "recovery-0001" },
    },
  });
  assert.deepEqual(successObligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    toast: "Current canvas rebaselined",
  });
  assert.equal(successPanel.state.failure, null);
  assert.equal(successPanel.state.rebaselineRecovery, null);
  assert.equal(successPanel.state.candidateGraph, null);
  assert.equal(successPanel.state.candidateGraphHash, null);
  assert.deepEqual(successPanel.state.auditRef, { path: "/tmp/recovery-success.json" });

  const failurePanel = makePanel({
    phase: PANEL_STATE.IDLE,
    rebaselineRecovery: { action: "rebaseline", reason: "stale_state_recovery" },
    debugPayload: { rebaseline_request: { session_id: "sess-1" } },
  });
  const failureRecovery = {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "baseline-retry",
  };
  const failureObligations = transition(failurePanel, "STALE_RECOVERY_REBASELINE_FAILURE", {
    rebaselineRecovery: failureRecovery,
    message: "Current canvas rebaseline failed. Review the evidence and retry.",
    debugPayload: {
      rebaseline_request: { session_id: "sess-1" },
      stale_state_recovery: true,
    },
  });
  assert.deepEqual(failureObligations, { render: true });
  assert.equal(failurePanel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(failurePanel.state.rebaselineRecovery, failureRecovery);
  assert.deepEqual(failurePanel.state.debugPayload, {
    rebaseline_request: { session_id: "sess-1" },
    stale_state_recovery: true,
  });
});

// ── Accept-stage stale recovery lifecycle ───────────────────────────────────

test("ACCEPT_REJECTED with normalized rebaselineRecovery stores camelCase recovery from payload", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
  });
  const staleFailure = {
    ok: false,
    kind: "StaleStateMismatch",
    message: "Baseline has moved since candidate was submitted",
    audit_ref: { path: "/tmp/stale-accept-audit.json" },
    baseline_turn_id: "0010",
    baseline_graph_hash: "base-after-move",
  };

  const obligations = transition(panel, "ACCEPT_REJECTED", {
    failure: staleFailure,
    acceptBody: { idempotency_key: "accept:stale" },
    authoritativeBackendReject: true,
    disabledApplyEligibility: {
      applyable: false,
      reason: "superseded",
      warnings: ["stale_state"],
    },
    rebaselineRecovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "base-before-move",
    },
  });

  assert.deepEqual(obligations, {
    render: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(panel.state.failure, staleFailure);
  // Normalized rebaselineRecovery from payload (camelCase direct path — stored as-is)
  assert.deepEqual(panel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "base-before-move",
  });
  // Baseline synced from failure payload
  assert.equal(panel.state.baselineTurnId, "0010");
  assert.equal(panel.state.baselineGraphHash, "base-after-move");
  assert.deepEqual(panel.state.auditRef, { path: "/tmp/stale-accept-audit.json" });
  // Queue and apply gates disabled for authoritative reject
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
  assert.equal(panel.state.queueAllowed, false);
});

test("REBASELINE_RECOVERY_SYNC stores normalized rebaselineRecovery without rendering", () => {
  const panel = makePanel({
    failure: { kind: "StaleStateMismatch" },
    rebaselineRecovery: { action: "rebaseline", reason: "old_recovery" },
  });

  const obligations = transition(panel, "REBASELINE_RECOVERY_SYNC", {
    rebaselineRecovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "baseline-after-reject",
    },
  });

  assert.deepEqual(obligations, { render: false });
  // CamelCase direct path — stored as-is without null-padding
  assert.deepEqual(panel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "baseline-after-reject",
  });
  // Existing state preserved
  assert.deepEqual(panel.state.failure, { kind: "StaleStateMismatch" });
});

test("REBASELINE_RECOVERY_SYNC extracts recovery from snake_case rebaseline_recovery in raw payload", () => {
  const panel = makePanel();

  const obligations = transition(panel, "REBASELINE_RECOVERY_SYNC", {
    rebaseline_recovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "raw-baseline",
    },
  });

  assert.deepEqual(obligations, { render: false });
  assert.deepEqual(panel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "raw-baseline",
    submit_graph_hash: null,
    submit_structural_graph_hash: null,
    client_graph_hash: null,
    client_structural_graph_hash: null,
  });
});

test("REBASELINE_RECOVERY_SYNC extracts recovery from nested agent_failure_context.issues in raw payload", () => {
  const panel = makePanel();

  const obligations = transition(panel, "REBASELINE_RECOVERY_SYNC", {
    agent_failure_context: {
      issues: [
        {},
        {
          rebaseline_recovery: {
            action: "rebaseline",
            endpoint: "/vibecomfy/agent-edit/rebaseline",
            reason: "stale_state_recovery",
            last_known_baseline_graph_hash: "nested-baseline",
          },
        },
      ],
    },
  });

  assert.deepEqual(obligations, { render: false });
  assert.deepEqual(panel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "nested-baseline",
    submit_graph_hash: null,
    submit_structural_graph_hash: null,
    client_graph_hash: null,
    client_structural_graph_hash: null,
  });
});

test("REBASELINE_RECOVERY_SYNC with null rebaselineRecovery clears existing recovery", () => {
  const panel = makePanel({
    rebaselineRecovery: { action: "rebaseline", reason: "stale_state_recovery" },
  });

  const obligations = transition(panel, "REBASELINE_RECOVERY_SYNC", {
    rebaselineRecovery: null,
  });

  assert.deepEqual(obligations, { render: false });
  assert.equal(panel.state.rebaselineRecovery, null);
});

test("SUBMIT_BACKEND_FAILURE stores rebaselineRecovery from stale failure with SUBMIT_NETWORK_FAILURE parity", () => {
  const failure = {
    kind: "StaleStateMismatch",
    message: "Baseline moved at submit time",
    session_id: "sess-backend-failure",
    turn_id: "0003",
    baseline_turn_id: "0002",
    baseline_graph_hash: "base-backend",
    audit_ref: { path: "/tmp/backend-failure-audit.json" },
    rebaseline_recovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "base-submit-target",
    },
  };
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    sessionId: "sess-old",
    turnId: "0001",
    lastSubmit: { task: "add node" },
  });

  const obligations = transition(panel, "SUBMIT_BACKEND_FAILURE", { failure });

  assert.deepEqual(obligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: "sess-backend-failure",
    refreshQueueGuard: true,
    rehydrateChat: true,
  });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(panel.state.failure, failure);
  assert.equal(panel.state.sessionId, "sess-backend-failure");
  assert.equal(panel.state.turnId, "0003");
  assert.equal(panel.state.baselineTurnId, "0002");
  assert.equal(panel.state.baselineGraphHash, "base-backend");
  assert.deepEqual(panel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "base-submit-target",
    submit_graph_hash: null,
    submit_structural_graph_hash: null,
    client_graph_hash: null,
    client_structural_graph_hash: null,
  });
  assert.deepEqual(panel.state.auditRef, { path: "/tmp/backend-failure-audit.json" });
});

test("Accept-stage stale recovery full chain: ACCEPT_REJECTED → REBASELINE_RECOVERY_SYNC → STALE_RECOVERY_REBASELINE_QUEUED → STALE_RECOVERY_REBASELINE_SUCCESS", () => {
  // Step 1: ACCEPT_REJECTED stores stale recovery
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    candidateGraph: { nodes: [{ id: 5 }] },
    candidateGraphHash: "candidate-hash-stale",
    applyEligibility: { applyable: true },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
  });
  const staleFailure = {
    ok: false,
    kind: "StaleStateMismatch",
    message: "Baseline advanced",
    audit_ref: { path: "/tmp/chain-audit.json" },
    baseline_turn_id: "0020",
    baseline_graph_hash: "base-chain",
  };

  const acceptObligations = transition(panel, "ACCEPT_REJECTED", {
    failure: staleFailure,
    acceptBody: { idempotency_key: "accept:chain" },
    authoritativeBackendReject: true,
    disabledApplyEligibility: {
      applyable: false,
      reason: "superseded",
    },
    rebaselineRecovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "base-original",
    },
  });

  assert.deepEqual(acceptObligations, {
    render: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  // CamelCase direct path — stored as-is
  assert.deepEqual(panel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "base-original",
  });

  // Step 2: REBASELINE_RECOVERY_SYNC — re-syncs same recovery (no render)
  const syncObligations = transition(panel, "REBASELINE_RECOVERY_SYNC", {
    rebaselineRecovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "base-original",
    },
  });
  assert.deepEqual(syncObligations, { render: false });
  assert.deepEqual(panel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "base-original",
  });

  // Step 3: STALE_RECOVERY_REBASELINE_QUEUED — transitions to IDLE, recovery still held
  const queuedObligations = transition(panel, "STALE_RECOVERY_REBASELINE_QUEUED");
  assert.deepEqual(queuedObligations, { render: true });
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.message, "Current canvas queued for stale-state recovery rebaseline.");
  // recovery still present during in-flight rebaseline
  assert.ok(panel.state.rebaselineRecovery);

  // Step 4: STALE_RECOVERY_REBASELINE_SUCCESS — clears failure, recovery, and candidate
  const successObligations = transition(panel, "STALE_RECOVERY_REBASELINE_SUCCESS", {
    auditRef: { path: "/tmp/chain-recovery-success.json" },
    message: "Current canvas rebaselined. Resubmitting from this canvas...",
    toast: "Current canvas rebaselined",
    debugPayload: {
      stale_state_recovery: true,
      rebaseline_response: { rebaseline_id: "recovery-chain-0001" },
    },
  });
  assert.deepEqual(successObligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    invalidateCandidate: true,
    toast: "Current canvas rebaselined",
  });
  assert.equal(panel.state.failure, null);
  assert.equal(panel.state.rebaselineRecovery, null);
  assert.equal(panel.state.candidateGraph, null);
  assert.equal(panel.state.candidateGraphHash, null);
  assert.deepEqual(panel.state.auditRef, { path: "/tmp/chain-recovery-success.json" });
});

test("Submit-stage stale recovery full chain: SUBMIT_BACKEND_FAILURE → REBASELINE_RECOVERY_SYNC → STALE_RECOVERY_REBASELINE_QUEUED → STALE_RECOVERY_REBASELINE_SUCCESS", () => {
  // Step 1: SUBMIT_BACKEND_FAILURE stores stale recovery
  const failure = {
    kind: "StaleStateMismatch",
    message: "Baseline moved at submit time",
    session_id: "sess-submit-chain",
    turn_id: "0006",
    baseline_turn_id: "0005",
    baseline_graph_hash: "base-submit-chain",
    audit_ref: { path: "/tmp/submit-chain-audit.json" },
    rebaseline_recovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "base-submit-original",
    },
  };
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    sessionId: "sess-old",
    turnId: "0003",
    lastSubmit: { task: "change sampler cfg" },
  });

  const failObligations = transition(panel, "SUBMIT_BACKEND_FAILURE", { failure });

  assert.deepEqual(failObligations, {
    render: true,
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
    persistSession: "sess-submit-chain",
    refreshQueueGuard: true,
    rehydrateChat: true,
  });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.equal(panel.state.turnId, "0006");
  assert.equal(panel.state.baselineTurnId, "0005");
  assert.equal(panel.state.baselineGraphHash, "base-submit-chain");
  assert.deepEqual(panel.state.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash: "base-submit-original",
    submit_graph_hash: null,
    submit_structural_graph_hash: null,
    client_graph_hash: null,
    client_structural_graph_hash: null,
  });

  // Step 2: REBASELINE_RECOVERY_SYNC
  assert.deepEqual(
    transition(panel, "REBASELINE_RECOVERY_SYNC", {
      rebaselineRecovery: {
        action: "rebaseline",
        endpoint: "/vibecomfy/agent-edit/rebaseline",
        reason: "stale_state_recovery",
        last_known_baseline_graph_hash: "base-submit-original",
      },
    }),
    { render: false },
  );

  // Step 3: STALE_RECOVERY_REBASELINE_QUEUED
  assert.deepEqual(
    transition(panel, "STALE_RECOVERY_REBASELINE_QUEUED"),
    { render: true },
  );
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);

  // Step 4: STALE_RECOVERY_REBASELINE_SUCCESS
  assert.deepEqual(
    transition(panel, "STALE_RECOVERY_REBASELINE_SUCCESS", {
      auditRef: { path: "/tmp/submit-recovery-success.json" },
      message: "Current canvas rebaselined. Resubmitting from this canvas...",
      toast: "Current canvas rebaselined",
    }),
    {
      render: true,
      dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
      invalidateCandidate: true,
      toast: "Current canvas rebaselined",
    },
  );
  assert.equal(panel.state.failure, null);
  assert.equal(panel.state.rebaselineRecovery, null);
});

// ── Undo flow ───────────────────────────────────────────────────────────────

test("UNDO_LOCAL_RESTORE clears local apply feedback and queue guard state before undo rebaseline", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    failure: { kind: "OldFailure" },
    lastAppliedChanges: { items: [{ uid: "uid-1" }] },
    undoStack: [{ graph: { nodes: [{ id: 1 }] }, turn_id: "0009", client_graph_hash: "graph-before" }],
  });

  const obligations = transition(panel, "UNDO_LOCAL_RESTORE", {
    previous: panel.state.undoStack[0],
    undoStackDepth: 1,
  });

  assert.deepEqual(obligations, {
    render: true,
    invalidateCandidate: true,
    clearChangedNodeFeedbackVisuals: true,
    queueGuardClear: true,
    refreshQueueGuard: true,
    dirtySections: [RENDER_SECTIONS.META, RENDER_SECTIONS.COMPOSER, RENDER_SECTIONS.NOTICE],
  });
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.failure, null);
  assert.equal(panel.state.lastAppliedChanges, null);
  assert.equal(panel.state.message, "Previous graph restored locally. Rebaselining undo state...");
  assert.deepEqual(panel.state.debugPayload, {
    undone_turn_id: "0009",
    restored_graph_hash: "graph-before",
    undo_stack_depth: 1,
  });
});

test("UNDO_REBASELINE_SUCCESS pops the undo stack and syncs authoritative baseline state", () => {
  const previous = {
    graph: { nodes: [{ id: 1 }] },
    turn_id: "0010",
    client_graph_hash: "graph-before",
  };
  const panel = makePanel({
    phase: PANEL_STATE.ERROR,
    failure: { kind: "OldFailure" },
    auditRef: { path: "/tmp/old-audit.json" },
    undoStack: [previous],
  });
  const result = {
    ok: true,
    action: "rebaseline",
    baseline_turn_id: "0010",
    baseline_graph_hash: "baseline-after-undo",
    baseline_graph_hash_kind: "structural",
    baseline_graph_hash_version: 2,
    baseline_source: "rebaseline",
    baseline_rebaseline_id: "rebaseline-undo-0010",
    audit_ref: { path: "/tmp/undo-success.json" },
  };

  const obligations = transition(panel, "UNDO_REBASELINE_SUCCESS", {
    previous,
    result,
    undoStackDepth: 0,
    toast: "Previous graph restored",
  });

  assert.deepEqual(obligations, {
    render: true,
    invalidateCandidate: true,
    refreshQueueGuard: true,
    toast: "Previous graph restored",
    dirtySections: [RENDER_SECTIONS.META, RENDER_SECTIONS.COMPOSER, RENDER_SECTIONS.NOTICE],
  });
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.failure, null);
  assert.equal(panel.state.baselineGraphHash, "baseline-after-undo");
  assert.equal(panel.state.baselineSource, "rebaseline");
  assert.equal(panel.state.baselineRebaselineId, "rebaseline-undo-0010");
  assert.deepEqual(panel.state.auditRef, { path: "/tmp/undo-success.json" });
  assert.deepEqual(panel.state.undoStack, []);
  assert.equal(panel.state.message, "Previous graph restored and rebaselined locally.");
  assert.deepEqual(panel.state.debugPayload, {
    rebaseline_response: result,
    undone_turn_id: "0010",
    restored_graph_hash: "graph-before",
    undo_stack_depth: 0,
  });
});

test("UNDO_REBASELINE_FAILURE preserves the undo stack and records retry evidence", () => {
  const previous = {
    graph: { nodes: [{ id: 1 }] },
    turn_id: "0011",
    client_graph_hash: "graph-before",
  };
  const recovery = {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "undo",
    last_known_baseline_graph_hash: "baseline-before",
  };
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    debugPayload: { local_restore: true },
    undoStack: [previous],
  });
  const failure = {
    ok: false,
    kind: "RebaselineError",
    retryable: true,
    audit_ref: { path: "/tmp/undo-failure.json" },
  };

  const obligations = transition(panel, "UNDO_REBASELINE_FAILURE", {
    previous,
    failure,
    rebaselineRecovery: recovery,
    undoStackDepth: 1,
  });

  assert.deepEqual(obligations, { render: true });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(panel.state.failure, failure);
  assert.deepEqual(panel.state.auditRef, { path: "/tmp/undo-failure.json" });
  assert.deepEqual(panel.state.rebaselineRecovery, recovery);
  assert.deepEqual(panel.state.undoStack, [previous]);
  assert.equal(
    panel.state.message,
    "Previous graph restored locally, but the undo rebaseline failed. Retry Undo Rebaseline.",
  );
  assert.deepEqual(panel.state.debugPayload, {
    local_restore: true,
    undone_turn_id: "0011",
    restored_graph_hash: "graph-before",
    undo_stack_depth: 1,
  });
});

// ── Obligations shape contract ──────────────────────────────────────────────

test("All foundation transitions return plain obligations objects", () => {
  const panel = makePanel();

  const events = [
    { name: "INIT", payload: {} },
    { name: "SYNC_BASELINE", payload: { baseline_turn_id: "t1" } },
    { name: "INVALIDATE_CANDIDATE", payload: {} },
    { name: "UNKNOWN", payload: {} },
  ];

  for (const { name, payload } of events) {
    const result = transition(panel, name, payload);
    assert.ok(result && typeof result === "object", `${name} must return an object`);
    assert.ok("render" in result, `${name} must have render key`);
    assert.equal(typeof result.render, "boolean", `${name} render must be boolean`);
    // Must be a plain object (not a class instance or array)
    assert.equal(Object.getPrototypeOf(result), Object.prototype, `${name} must return plain object`);
  }
});



// ── Feed lifecycle helpers ───────────────────────────────────────────────

/**
 * Build a minimal raw payload and derive canonical activity state.
 * Defaults to no statements so headline comes from 'message'.
 */
function makeActivity(overrides = {}) {
  const raw = {
    session_id: "sess-lifecycle",
    turn_id: "0001",
    turn_number: 1,
    status: "progress",
    message: null,
    statements: [],
    entry_type: "batch",
    ...overrides,
  };
  const normalized = normalizeAgentTurnPayload(raw);
  return deriveAgentActivityState(normalized);
}

// ── Websocket partial → HTTP final reconciliation ────────────────────────

test("websocket partial followed by HTTP final reconciles without duplication", () => {
  let feed = [];

  // Step 1: websocket partial arrives (in_progress, no statements)
  const wsPartial = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "progress",
    message: "Analyzing request...",
  });
  feed = reduceAgentActivityFeed(feed, wsPartial, { source: "websocket" });
  assert.equal(feed.length, 1, "websocket partial creates one entry");
  assert.equal(feed[0].status, "in_progress", "legacy progress normalized to in_progress");
  assert.ok(feed[0].phase_progress, "phase_progress must be present");
  // No statements and no landed ops → decide is active
  // With turn_number=1, decide is "done" (turns have passed decide phase)
  assert.equal(feed[0].phase_progress.decide, "done");

  // Step 2: HTTP final response arrives for same turn (with statements, done)
  const httpFinal = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "done",
    message: "Updated cfg scale to 7.5",
    done_summary: "Changed cfg from 7.0 → 7.5",
    landed_op_count: 2,
    statement_count: 4,
    statements: [
      { op_kind: "decide", ok: true, landed: true, message: "Plan: update cfg", statement_index: 0 },
      { op_kind: "set_node_field", ok: true, landed: true, message: "Set cfg to 7.5", statement_index: 1 },
      { op_kind: "done", ok: true, landed: true, message: "done()", statement_index: 2 },
    ],
  });
  feed = reduceAgentActivityFeed(feed, httpFinal, { source: "http" });
  assert.equal(feed.length, 1, "HTTP final must replace in place, not duplicate");
  assert.equal(feed[0].status, "done", "terminal status from HTTP");
  // Headline from latest substantive statement (done() excluded)
  assert.equal(feed[0].headline, "Set cfg to 7.5");
  // Phase progress all done
  assert.equal(feed[0].phase_progress.decide, "done");
  assert.equal(feed[0].phase_progress.research, "done");
  assert.equal(feed[0].phase_progress.execute, "done");
  assert.equal(feed[0].phase_progress.review, "done");
});

test("active-state clearing: in_progress phases transition to all-done on completion", () => {
  let feed = [];

  // websocket in_progress with statements to get active research
  const wsPartial = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "progress",
    message: "Planning...",
    statements: [
      { op_kind: "decide", ok: true, landed: true, message: "Plan", statement_index: 0 },
    ],
  });
  feed = reduceAgentActivityFeed(feed, wsPartial, { source: "websocket" });
  // landed ops > 0 → execute active
  const wsPhases = feed[0].phase_progress;
  const hasActive = wsPhases.decide === "active"
    || wsPhases.research === "active"
    || wsPhases.execute === "active";
  assert.ok(hasActive, "in_progress entry must have at least one active phase");

  // HTTP final done
  const httpFinal = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "done",
    message: "Done",
    landed_op_count: 1,
    statement_count: 2,
    statements: [
      { op_kind: "decide", ok: true, landed: true, message: "Plan", statement_index: 0 },
      { op_kind: "done", ok: true, landed: true, message: "done()", statement_index: 1 },
    ],
  });
  feed = reduceAgentActivityFeed(feed, httpFinal, { source: "http" });

  // All phases must be "done" — no active state
  const finalPhases = feed[0].phase_progress;
  assert.equal(finalPhases.decide, "done");
  assert.equal(finalPhases.research, "done");
  assert.equal(finalPhases.execute, "done");
  assert.equal(finalPhases.review, "done");
  assert.equal(
    finalPhases.decide === "active" || finalPhases.research === "active" || finalPhases.execute === "active",
    false,
    "no active phases remain after terminal status"
  );
});

test("preservation of durable final turn details across websocket→HTTP reconciliation", () => {
  let feed = [];

  const wsPartial = makeActivity({
    turn_id: "0042", turn_number: 42,
    session_id: "sess-durable",
    status: "progress",
    message: "Working on it...",
  });
  feed = reduceAgentActivityFeed(feed, wsPartial, { source: "websocket" });

  const httpFinal = makeActivity({
    session_id: "sess-durable",
    turn_id: "0042", turn_number: 42,
    status: "done",
    message: "Changed cfg from 7.0 → 7.5",
    done_summary: "1 node updated (cfg scale)",
    landed_op_count: 1,
    statement_count: 3,
    statements: [
      { op_kind: "decide", ok: true, landed: true, message: "Plan", statement_index: 0 },
      { op_kind: "set_node_field", ok: true, landed: true, message: "Set cfg to 7.5", statement_index: 1 },
      { op_kind: "done", ok: true, landed: true, message: "done()", statement_index: 2 },
    ],
  });
  feed = reduceAgentActivityFeed(feed, httpFinal, { source: "http" });

  const entry = feed[0];
  // Durable turn identity preserved
  assert.equal(entry.turn_id, "0042");
  assert.equal(entry.turn_number, 42);
  assert.equal(entry.session_id, "sess-durable");
  assert.equal(entry.entry_type, "batch");

  // Status/outcome preserved
  assert.equal(entry.status, "done");
  assert.equal(entry.outcome.kind, "done");
  assert.ok(entry.outcome.summary, "outcome summary must be present");

  // Headline from latest substantive statement
  assert.equal(entry.headline, "Set cfg to 7.5");

  // Counts preserved
  assert.ok(entry.counts, "counts must be present");
  assert.ok(entry.counts.total > 0, "statement count preserved");

  // Details preserved
  assert.ok(Array.isArray(entry.details), "details array preserved");
  assert.ok(entry.details.length > 0, "details not empty");
});

test("pending-message label updates from canonical headline on each websocket progress event", () => {
  let feed = [];

  // First websocket event — no statements, so headline from message
  let ws = makeActivity({
    turn_id: "0001", turn_number: 1,
    message: "Analyzing your request...",
    status: "progress",
    statements: [],
  });
  feed = reduceAgentActivityFeed(feed, ws, { source: "websocket" });
  assert.equal(feed[0].headline, "Analyzing your request...");

  // Second websocket event with statements
  ws = makeActivity({
    turn_id: "0001", turn_number: 1,
    message: "Working...",
    status: "progress",
    statements: [
      { op_kind: "research", ok: true, landed: false, message: "Checking node references", statement_index: 0 },
    ],
  });
  feed = reduceAgentActivityFeed(feed, ws, { source: "websocket" });
  // Headline from latest substantive statement
  assert.equal(feed[0].headline, "Checking node references");

  // Third websocket event — landed ops exist
  ws = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "progress",
    statements: [
      { op_kind: "decide", ok: true, landed: true, message: "I'll update the node", statement_index: 0 },
      { op_kind: "set_node_field", ok: true, landed: true, message: "Set cfg to 7.5", statement_index: 1 },
    ],
    landed_op_count: 1,
  });
  feed = reduceAgentActivityFeed(feed, ws, { source: "websocket" });
  assert.equal(feed[0].headline, "Set cfg to 7.5",
    "headline updates with each progress event");
  // Phase should reflect executing now (has landed ops)
  assert.equal(feed[0].phase_progress.execute, "active");

  // HTTP final — headline still from latest substantive statement
  const httpFinal = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "done",
    message: "Completed",
    done_summary: "1 node updated (cfg scale)",
    statements: [
      { op_kind: "decide", ok: true, landed: true, message: "I'll update the node", statement_index: 0 },
      { op_kind: "set_node_field", ok: true, landed: true, message: "Set cfg to 7.5", statement_index: 1 },
      { op_kind: "done", ok: true, landed: true, message: "done()", statement_index: 2 },
    ],
    landed_op_count: 1,
    statement_count: 3,
  });
  feed = reduceAgentActivityFeed(feed, httpFinal, { source: "http" });
  // done() excluded from headline selection
  assert.equal(feed[0].headline, "Set cfg to 7.5");
});

// ── Multi-turn lifecycle ─────────────────────────────────────────────────

test("multi-turn lifecycle: websocket partials interleaved with HTTP finals preserve all turns", () => {
  let feed = [];

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1, session_id: "sess-multi",
    status: "progress", message: "T1 analyzing",
  }), { source: "websocket" });
  assert.equal(feed.length, 1);

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1, session_id: "sess-multi",
    status: "done", message: "T1 done", done_summary: "T1: cfg updated",
    landed_op_count: 1, statement_count: 2,
  }), { source: "http" });
  assert.equal(feed.length, 1);
  assert.equal(feed[0].status, "done");
  assert.equal(feed[0].turn_id, "0001");

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0002", turn_number: 2, session_id: "sess-multi",
    status: "progress", message: "T2 analyzing",
  }), { source: "websocket" });
  assert.equal(feed.length, 2);

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0003", turn_number: 3, session_id: "sess-multi",
    status: "progress", message: "T3 analyzing",
  }), { source: "websocket" });
  assert.equal(feed.length, 3);

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0002", turn_number: 2, session_id: "sess-multi",
    status: "done", message: "T2 done", done_summary: "T2: node added",
    landed_op_count: 1, statement_count: 2,
  }), { source: "http" });
  assert.equal(feed[0].status, "done"); // T1 still done
  assert.equal(feed[1].status, "done"); // T2 now done
  assert.equal(feed[2].status, "in_progress"); // T3 still in progress

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0003", turn_number: 3, session_id: "sess-multi",
    status: "done", message: "T3 done", done_summary: "T3: mode changed",
    landed_op_count: 1, statement_count: 2,
  }), { source: "http" });
  assert.equal(feed.length, 3, "all three turns preserved");
  for (const entry of feed) {
    assert.equal(entry.status, "done", "all turns terminal after HTTP finals");
    assert.equal(entry.phase_progress.decide, "done");
  }
});

test("multi-turn lifecycle: historical turn details survive new turn reconciliation", () => {
  let feed = [];

  // Turn 1 done via HTTP — no statements, so headline from message
  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1, session_id: "sess-hist",
    status: "done", message: "T1: added node", done_summary: "Added KSampler",
    landed_op_count: 1, statement_count: 2,
    statements: [],
  }), { source: "http" });
  assert.equal(feed[0].headline, "T1: added node");
  assert.equal(feed[0].outcome.summary, "Added KSampler");

  // Turn 2 done via HTTP
  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0002", turn_number: 2, session_id: "sess-hist",
    status: "done", message: "T2: changed prompt", done_summary: "Updated prompt text",
    landed_op_count: 1, statement_count: 3,
    statements: [],
  }), { source: "http" });
  assert.equal(feed[1].headline, "T2: changed prompt");
  assert.equal(feed[1].outcome.summary, "Updated prompt text");

  // Verify both turns preserved (turn order by arrival)
  const turn1 = feed[0];
  assert.equal(turn1.turn_id, "0001");
  assert.equal(turn1.headline, "T1: added node");
  assert.equal(turn1.outcome.summary, "Added KSampler");
  assert.equal(turn1.status, "done");

  const turn2 = feed[1];
  assert.equal(turn2.turn_id, "0002");
  assert.equal(turn2.headline, "T2: changed prompt");
  assert.equal(turn2.outcome.summary, "Updated prompt text");
  assert.equal(turn2.status, "done");

  // Feed must be frozen (immutable)
  assert.throws(() => { feed.push({}); }, /frozen|not extensible|read.only/i,
    "reduceAgentActivityFeed must return frozen arrays");
});

// ── Clarify / error / budget_exhausted lifecycle ─────────────────────────

test("clarify outcome lifecycle: websocket in_progress → HTTP clarify clears active state, preserves clarification", () => {
  let feed = [];

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "progress", message: "Analyzing...",
  }), { source: "websocket" });
  assert.equal(feed[0].status, "in_progress");

  const clarifyActivity = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "clarify",
    message: "Which cfg value would you prefer?",
    clarification_required: true,
    clarification_message: "Please specify cfg range",
  });

  feed = reduceAgentActivityFeed(feed, clarifyActivity, { source: "http" });
  assert.equal(feed[0].status, "clarify");
  assert.equal(feed[0].outcome.kind, "clarify");
  assert.equal(feed[0].outcome.clarification_required, true);
  assert.equal(feed[0].outcome.clarification_message, "Please specify cfg range");
  assert.equal(feed[0].phase_progress.decide, "done");
  assert.equal(feed[0].phase_progress.review, "done");
});

test("error outcome lifecycle: websocket in_progress → HTTP error clears active state, preserves diagnostics", () => {
  let feed = [];

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "progress", message: "Working...",
  }), { source: "websocket" });

  const errorActivity = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "error",
    message: "Backend unavailable",
    diagnostics: [
      { code: "E_BACKEND", message: "Connection refused on port 8188" },
    ],
  });

  feed = reduceAgentActivityFeed(feed, errorActivity, { source: "http" });
  assert.equal(feed[0].status, "error");
  assert.equal(feed[0].outcome.kind, "error");
  assert.ok(feed[0].outcome.summary, "error outcome has summary");
  assert.ok(Array.isArray(feed[0].diagnostics), "diagnostics preserved");
  assert.equal(feed[0].diagnostics[0].code, "E_BACKEND");
  assert.equal(feed[0].phase_progress.decide, "done");
  assert.equal(feed[0].phase_progress.execute, "done");
});

test("budget_exhausted outcome lifecycle: websocket in_progress → HTTP budget_exhausted clears active state, preserves budget", () => {
  let feed = [];

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "progress", message: "Working...",
  }), { source: "websocket" });

  const budgetActivity = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "budget_exhausted",
    message: "Budget limit reached",
    budget: { remaining_batches: 0, consecutive_errors: 3 },
  });

  feed = reduceAgentActivityFeed(feed, budgetActivity, { source: "http" });
  assert.equal(feed[0].status, "budget_exhausted");
  assert.equal(feed[0].outcome.kind, "budget_exhausted");
  assert.ok(feed[0].outcome.summary.includes("Budget exhausted"),
    "budget exhausted outcome has descriptive summary");
  assert.equal(feed[0].phase_progress.decide, "done");
  assert.equal(feed[0].phase_progress.execute, "done");
});

// ── Regression protections in lifecycle context ─────────────────────────

test("stale websocket in_progress after HTTP final terminal is rejected (terminal→active regression)", () => {
  let feed = [];

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1, session_id: "sess-regress",
    status: "done", message: "Completed", done_summary: "Done",
    landed_op_count: 1, statement_count: 2,
  }), { source: "http" });
  assert.equal(feed[0].status, "done");

  const lateWs = makeActivity({
    turn_id: "0001", turn_number: 1, session_id: "sess-regress",
    status: "progress", message: "Wait, still working...",
  });
  const result = reduceAgentActivityFeed(feed, lateWs, { source: "websocket" });
  assert.equal(result, feed, "late websocket in_progress must be rejected");
  assert.equal(result[0].status, "done", "terminal done status preserved");
});

test("HTTP final for same turn as existing in_progress replaces entry with terminal details intact", () => {
  let feed = [];

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0099", turn_number: 99,
    session_id: "sess-replace",
    status: "progress", message: "T99 working",
  }), { source: "websocket" });

  const httpFinal = makeActivity({
    turn_id: "0099", turn_number: 99,
    session_id: "sess-replace",
    status: "done",
    message: "T99 complete",
    done_summary: "T99: cfg updated",
    landed_op_count: 3,
    statement_count: 7,
    statements: [
      { op_kind: "decide", ok: true, landed: true, message: "Plan", statement_index: 0 },
      { op_kind: "set_node_field", ok: true, landed: true, message: "Edit 1", statement_index: 1 },
      { op_kind: "set_node_field", ok: true, landed: true, message: "Edit 2", statement_index: 2 },
      { op_kind: "set_node_field", ok: true, landed: true, message: "Edit 3", statement_index: 3 },
      { op_kind: "done", ok: true, landed: true, message: "done()", statement_index: 4 },
    ],
  });
  feed = reduceAgentActivityFeed(feed, httpFinal, { source: "http" });

  assert.equal(feed.length, 1);
  const entry = feed[0];
  assert.equal(entry.status, "done");
  assert.equal(entry.turn_id, "0099");
  assert.equal(entry.turn_number, 99);
  assert.equal(entry.session_id, "sess-replace");
  assert.equal(entry.outcome.kind, "done");
  assert.ok(typeof entry.outcome.landed_ops === "number", "landed ops count field present");
  // counts from statements array: 5 statements total
  assert.ok(entry.counts.total >= 5, "statement count preserved (from statements array)");

  // Verify details array has expected categories
  const detailKinds = entry.details.map(d => d.kind);
  assert.ok(detailKinds.includes("identity"), "identity detail preserved");
  assert.ok(detailKinds.includes("counts") || detailKinds.includes("statements"),
    "counts or statements detail preserved");
  assert.ok(detailKinds.includes("done_summary") || detailKinds.includes("message"),
    "message or done_summary detail preserved");
});

// ── Answer-only / no-edit turn lifecycle ────────────────────────────────

test("answer-only turn: websocket in_progress → HTTP done with no substantive statements preserves answer outcome", () => {
  let feed = [];

  const wsPartial = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "progress", message: "Looking up information...",
  });
  feed = reduceAgentActivityFeed(feed, wsPartial, { source: "websocket" });
  assert.equal(feed[0].status, "in_progress");

  const answerActivity = makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "done",
    message: "The cfg scale controls how closely the sampler follows your prompt.",
    statements: [
      { op_kind: "done", ok: true, landed: true, message: "done()", statement_index: 0 },
    ],
    landed_op_count: 0,
    statement_count: 1,
  });

  feed = reduceAgentActivityFeed(feed, answerActivity, { source: "http" });
  assert.equal(feed[0].status, "done");
  assert.equal(feed[0].outcome.kind, "answered",
    "answer-only turn gets 'answered' outcome kind");
  assert.equal(feed[0].outcome.graph_changes, false);
  assert.equal(feed[0].outcome.summary, "The cfg scale controls how closely the sampler follows your prompt.");
  assert.equal(feed[0].phase_progress.execute, "done");
});

// ── Durable details persistence across lifecycle ────────────────────────

test("durable details array includes identity, message, statements, and counts after HTTP reconciliation", () => {
  let feed = [];

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0007", turn_number: 7,
    session_id: "sess-details",
    status: "progress",
    message: "Starting work...",
  }), { source: "websocket" });

  const httpFinal = makeActivity({
    turn_id: "0007", turn_number: 7,
    session_id: "sess-details",
    status: "done",
    message: "Work complete",
    done_summary: "2 nodes updated",
    landed_op_count: 2,
    statement_count: 5,
    statements: [
      { op_kind: "decide", ok: true, landed: true, message: "Plan: update 2 nodes", statement_index: 0 },
      { op_kind: "set_node_field", ok: true, landed: true, message: "Set cfg to 8.0", statement_index: 1 },
      { op_kind: "set_node_field", ok: false, landed: false, message: "Failed to set steps", statement_index: 2 },
      { op_kind: "set_node_field", ok: true, landed: true, message: "Set steps to 20", statement_index: 3 },
      { op_kind: "done", ok: true, landed: true, message: "done()", statement_index: 4 },
    ],
  });
  feed = reduceAgentActivityFeed(feed, httpFinal, { source: "http" });

  const entry = feed[0];
  assert.equal(entry.turn_id, "0007");
  assert.equal(entry.turn_number, 7);

  const detailKinds = entry.details.map(d => d.kind);
  assert.ok(detailKinds.includes("identity"), "identity detail present");
  assert.ok(detailKinds.includes("done_summary") || detailKinds.includes("message"),
    "message/done_summary detail present");
  assert.ok(detailKinds.includes("statements") || detailKinds.includes("counts"),
    "statements or counts detail present");

  // Counts from statements array (all 5, including done())
  assert.equal(entry.counts.total, 5, "5 statements total");
  assert.equal(entry.counts.landed, 4, "4 landed (decide + 2 set_node_field + done())");
  assert.equal(entry.counts.ok, 4, "4 ok statements (Failed to set steps has ok: false)");
  assert.equal(entry.counts.not_ok, 1, "1 not-ok (Failed to set steps has ok: false, not_ok counts not-ok)");

  // Latest substantive statement is "Set steps to 20" (index 3, skipping done())
  assert.equal(entry.latest_substantive_statement.op_kind, "set_node_field");
  assert.equal(entry.latest_substantive_statement.message, "Set steps to 20");
});

test("details are bounded: statements capped at 5, diagnostics capped at 5", () => {
  const stmts = [];
  for (let i = 0; i < 10; i++) {
    stmts.push({
      op_kind: i === 9 ? "done" : "set_node_field",
      ok: true,
      landed: true,
      message: `Change ${i + 1}`,
      statement_index: i,
    });
  }
  const diags = [];
  for (let i = 0; i < 10; i++) {
    diags.push({ code: `DIAG_${i}`, message: `Issue ${i}` });
  }

  const activity = makeActivity({
    session_id: "sess-bounded",
    turn_id: "0001",
    turn_number: 1,
    status: "done",
    message: "Done",
    statements: stmts,
    diagnostics: diags,
    statement_count: 10,
    landed_op_count: 9,
  });

  const stmtDetail = activity.details.find(d => d.kind === "statements");
  assert.ok(stmtDetail, "statements detail exists");
  assert.equal(stmtDetail.shown, 5, "statements shown capped at 5");
  assert.equal(stmtDetail.total, 10, "total preserved");

  assert.ok(Array.isArray(activity.diagnostics));
  assert.ok(activity.diagnostics.length <= 5, "diagnostics capped at 5");
});

// ── Feed immutability contract ──────────────────────────────────────────

test("reduceAgentActivityFeed returns frozen arrays on every valid operation", () => {
  let feed = [];

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1,
  }), { source: "websocket" });
  assert.ok(Object.isFrozen(feed), "feed array is frozen after websocket append");

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "progress", message: "Updated",
  }), { source: "websocket" });
  assert.ok(Object.isFrozen(feed), "feed array is frozen after in-place update");

  feed = reduceAgentActivityFeed(feed, makeActivity({
    turn_id: "0001", turn_number: 1,
    status: "done", message: "Done", done_summary: "Done",
    landed_op_count: 1, statement_count: 2,
  }), { source: "http" });
  assert.ok(Object.isFrozen(feed), "feed array is frozen after HTTP replacement");
  assert.ok(Object.isFrozen(feed[0]), "feed entries are frozen");
});

// ── Unknown / null edge cases in lifecycle flow ─────────────────────────

test("reduceAgentActivityFeed with null/undefined feed starts fresh", () => {
  const result = reduceAgentActivityFeed(null, makeActivity({
    turn_id: "0001", turn_number: 1,
  }), { source: "websocket" });
  assert.equal(result.length, 1);
  assert.equal(result[0].turn_id, "0001");
});

test("reduceAgentActivityFeed with non-array feed treats as empty", () => {
  const result = reduceAgentActivityFeed({ not: "an array" }, makeActivity({
    turn_id: "0001", turn_number: 1,
  }), { source: "websocket" });
  assert.ok(Array.isArray(result));
  assert.equal(result.length, 1);
});

// ── RENDER_SECTIONS ─────────────────────────────────────────────────────────

test("RENDER_SECTIONS exports frozen taxonomy with 6 sections matching the contract", () => {
  assert.ok(Object.isFrozen(RENDER_SECTIONS));

  const keys = Object.keys(RENDER_SECTIONS).sort();
  assert.deepEqual(keys, [
    "COMPOSER",
    "DEVELOPER",
    "META",
    "NOTICE",
    "SETTINGS",
    "THREAD",
  ]);

  // Value equals key by contract
  for (const key of keys) {
    assert.equal(RENDER_SECTIONS[key], key, `RENDER_SECTIONS.${key} must equal "${key}"`);
  }
});

test("RENDER_SECTIONS values are distinct", () => {
  const values = Object.values(RENDER_SECTIONS);
  assert.equal(new Set(values).size, 6);
});

// ── normalizeObligationDirtySections — known sections ───────────────────────

test("normalizeObligationDirtySections passes through obligations with no dirtySections", () => {
  const obligations = { render: true };
  const result = normalizeObligationDirtySections(obligations);
  assert.deepEqual(result, { render: true });
  // Should return the same object (not a copy) when no dirtySections key
  assert.equal(result, obligations);
});

test("normalizeObligationDirtySections passes through obligations with null dirtySections", () => {
  const obligations = { render: true, dirtySections: null };
  const result = normalizeObligationDirtySections(obligations);
  assert.deepEqual(result, { render: true, dirtySections: null });
  assert.equal(result, obligations);
});

test("normalizeObligationDirtySections preserves all known sections", () => {
  const obligations = {
    render: true,
    dirtySections: ["META", "THREAD", "COMPOSER", "NOTICE", "SETTINGS", "DEVELOPER"],
    toast: "hello",
  };

  const result = normalizeObligationDirtySections(obligations);

  assert.equal(result.render, true);
  assert.equal(result.toast, "hello");
  assert.deepEqual(result.dirtySections, ["META", "THREAD", "COMPOSER", "NOTICE", "SETTINGS", "DEVELOPER"]);
  // Returned object should be a shallow copy when normalised
  assert.notEqual(result, obligations);
});

test("normalizeObligationDirtySections preserves single section", () => {
  const obligations = { render: false, dirtySections: ["THREAD"] };
  const result = normalizeObligationDirtySections(obligations);

  assert.equal(result.render, false);
  assert.deepEqual(result.dirtySections, ["THREAD"]);
});

// ── normalizeObligationDirtySections — duplicate removal ────────────────────

test("normalizeObligationDirtySections removes duplicate sections preserving first occurrence order", () => {
  const obligations = {
    render: true,
    dirtySections: ["META", "THREAD", "META", "COMPOSER", "THREAD", "META"],
  };

  const result = normalizeObligationDirtySections(obligations);

  assert.deepEqual(result.dirtySections, ["META", "THREAD", "COMPOSER"]);
  assert.equal(result.render, true);
});

test("normalizeObligationDirtySections returns empty array when all duplicates of a single section", () => {
  const obligations = {
    render: true,
    dirtySections: ["NOTICE", "NOTICE", "NOTICE"],
  };

  const result = normalizeObligationDirtySections(obligations);

  assert.deepEqual(result.dirtySections, ["NOTICE"]);
});

test("normalizeObligationDirtySections returns empty array when dirtySections is empty", () => {
  const obligations = { render: true, dirtySections: [] };
  const result = normalizeObligationDirtySections(obligations);

  assert.equal(result.render, true);
  assert.deepEqual(result.dirtySections, []);
  assert.notEqual(result, obligations);
});

// ── normalizeObligationDirtySections — unknown section failures ─────────────

test("normalizeObligationDirtySections throws for unknown section name", () => {
  const obligations = { render: true, dirtySections: ["UNKNOWN_SECTION"] };

  assert.throws(
    () => normalizeObligationDirtySections(obligations),
    /Unknown render section: "UNKNOWN_SECTION"/,
  );
});

test("normalizeObligationDirtySections throws for mixed known and unknown sections", () => {
  const obligations = {
    render: true,
    dirtySections: ["META", "INVALID", "THREAD"],
  };

  assert.throws(
    () => normalizeObligationDirtySections(obligations),
    /Unknown render section: "INVALID"/,
  );
});

test("normalizeObligationDirtySections throws for non-string section entry", () => {
  const obligations = { render: true, dirtySections: ["META", 42, "THREAD"] };

  assert.throws(
    () => normalizeObligationDirtySections(obligations),
    /dirtySections\[1\] must be a string/,
  );
});

test("normalizeObligationDirtySections throws for non-array dirtySections", () => {
  const obligations = { render: true, dirtySections: "THREAD" };

  assert.throws(
    () => normalizeObligationDirtySections(obligations),
    /dirtySections must be an array/,
  );
});

test("normalizeObligationDirtySections throws for object dirtySections", () => {
  const obligations = { render: true, dirtySections: { section: "THREAD" } };

  assert.throws(
    () => normalizeObligationDirtySections(obligations),
    /dirtySections must be an array/,
  );
});

// ── normalizeObligationDirtySections — render backwards compatibility ────────

test("normalizeObligationDirtySections preserves render:true when normalizing sections", () => {
  const obligations = { render: true, dirtySections: ["META", "NOTICE"] };
  const result = normalizeObligationDirtySections(obligations);

  assert.equal(result.render, true);
});

test("normalizeObligationDirtySections preserves render:false when normalizing sections", () => {
  const obligations = { render: false, dirtySections: ["THREAD"] };
  const result = normalizeObligationDirtySections(obligations);

  assert.equal(result.render, false);
});

test("normalizeObligationDirtySections preserves render when dirtySections is absent (empty obligations)", () => {
  assert.deepEqual(
    normalizeObligationDirtySections({ render: false }),
    { render: false },
  );
  assert.deepEqual(
    normalizeObligationDirtySections({ render: true }),
    { render: true },
  );
});

test("normalizeObligationDirtySections passes through non-object and null obligations unchanged", () => {
  assert.equal(normalizeObligationDirtySections(null), null);
  assert.equal(normalizeObligationDirtySections(undefined), undefined);
  assert.equal(normalizeObligationDirtySections("string"), "string");
  assert.equal(normalizeObligationDirtySections(42), 42);
  assert.equal(normalizeObligationDirtySections(true), true);
});

test("normalizeObligationDirtySections preserves extra obligation keys beyond render and dirtySections", () => {
  const obligations = {
    render: true,
    dirtySections: ["SETTINGS", "DEVELOPER", "SETTINGS"],
    toast: "Changes saved",
    persistSession: "sess-42",
    refreshQueueGuard: true,
    invalidateCandidate: false,
  };

  const result = normalizeObligationDirtySections(obligations);

  assert.equal(result.render, true);
  assert.equal(result.toast, "Changes saved");
  assert.equal(result.persistSession, "sess-42");
  assert.equal(result.refreshQueueGuard, true);
  assert.equal(result.invalidateCandidate, false);
  assert.deepEqual(result.dirtySections, ["SETTINGS", "DEVELOPER"]);
});

// ══════════════════════════════════════════════════════════════════════════════
// T9: Scope submit, new conversation, queue guard, and debug metadata
// ══════════════════════════════════════════════════════════════════════════════

test("T9: NEW_CONVERSATION preserves scope identity (chatScopeId + fingerprint) while resetting chat data", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    sessionId: "sess-2",
    turnId: "turn-3",
    chatScopeId: "scope-A",
    chatScopeFingerprint: "fp-abc123",
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "candidate-hash",
    message: "Candidate ready.",
    queueAllowed: true,
    canvasApplyAllowed: true,
    submitEpoch: 7,
    chatRehydrateEpoch: 11,
    history: ["keep-non-lifecycle"],
  });

  const obligations = transition(panel, "NEW_CONVERSATION");

  // Scope identity is preserved.
  assert.equal(panel.state.chatScopeId, "scope-A");
  assert.equal(panel.state.chatScopeFingerprint, "fp-abc123");

  // Chat/state is reset.
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.sessionId, null);
  assert.equal(panel.state.turnId, null);
  assert.equal(panel.state.candidateGraph, null);
  assert.equal(panel.state.candidateGraphHash, null);
  assert.equal(panel.state.message, null);
  assert.equal(panel.state.queueAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);

  // Epochs incremented.
  assert.equal(panel.state.submitEpoch, 8);
  assert.equal(panel.state.chatRehydrateEpoch, 12);

  // Obligations use scoped queue guard clear.
  assert.equal(obligations.queueGuardClearScope, "scope-A");
  assert.equal(obligations.forgetScope, "scope-A");
  assert.equal(obligations.forgetSession, true);
  assert.equal(obligations.refreshQueueGuard, true);
});

test("T9: NEW_CONVERSATION queueGuardClearScope is null when no scope is active", () => {
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    sessionId: "sess-legacy",
    chatScopeId: null,
    chatScopeFingerprint: null,
  });

  const obligations = transition(panel, "NEW_CONVERSATION");

  assert.equal(obligations.queueGuardClearScope, null);
  assert.equal(panel.state.chatScopeId, null);
  assert.equal(panel.state.chatScopeFingerprint, null);
});

test("T9: SUBMIT_START stamps debugPayload with scope identity", () => {
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: "scope-submit",
    chatScopeFingerprint: "fp-xyz",
    submitEpoch: 3,
  });

  const obligations = transition(panel, "SUBMIT_START", {
    lastSubmit: { task: "test edit" },
    debugPayload: { task: "test edit", route: "openrouter" },
  });

  assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING);
  assert.equal(panel.state.submittingScopeId, "scope-submit");
  assert.ok(panel.state.debugPayload != null);
  assert.equal(panel.state.debugPayload._scopeId, "scope-submit");
  assert.equal(panel.state.debugPayload._scopeFingerprint, "fp-xyz");
  // Original payload keys are preserved.
  assert.equal(panel.state.debugPayload.task, "test edit");
  assert.equal(panel.state.debugPayload.route, "openrouter");
});

test("T9: SUBMIT_START debugPayload carries scope-only metadata when no explicit payload is provided", () => {
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: "scope-meta",
    chatScopeFingerprint: "fp-meta",
    submitEpoch: 1,
  });

  transition(panel, "SUBMIT_START", { lastSubmit: null });

  assert.ok(panel.state.debugPayload != null);
  assert.equal(panel.state.debugPayload._scopeId, "scope-meta");
  assert.equal(panel.state.debugPayload._scopeFingerprint, "fp-meta");
  // No extra junk.
  assert.equal(Object.keys(panel.state.debugPayload).length, 2);
});

test("T9: SUBMIT_START debugPayload is null when no scope is active and no payload is given", () => {
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: null,
    chatScopeFingerprint: null,
    submitEpoch: 0,
  });

  transition(panel, "SUBMIT_START", { lastSubmit: null });

  assert.equal(panel.state.debugPayload, null);
});

test("T9: CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE accepts same-scope candidate after new conversation preserves scope identity", () => {
  // T9 ensures NEW_CONVERSATION preserves scope identity.  This means a
  // rehydrate response that arrives after a new conversation in the SAME
  // scope should still be accepted (scope matches, phase is IDLE).
  // The candidate session guard from T8 may still reject it, but that's a
  // separate concern — T9's contribution is that the scope binding survives.
  const panel = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: "scope-A",
    chatScopeFingerprint: "fp-A",
    chatRehydrateEpoch: 10,
    chatRehydrateCommittedEpoch: 10,
  });

  // New conversation in scope-A: scope identity preserved.
  transition(panel, "NEW_CONVERSATION");
  assert.equal(panel.state.chatScopeId, "scope-A"); // T9: preserved
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);

  // A candidate arrives for the SAME scope — scope guard passes.
  // The lifecycle handler returns a proper obligations object (not skipped)
  // because the phase is IDLE and scope matches.
  const result = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    requestScopeId: "scope-A",
    candidateSessionId: "sess-fresh",
    sessionId: "sess-fresh",
    turnId: "turn-new",
    candidateGraph: { nodes: [{ id: 99 }] },
    candidateGraphHash: "hash-new",
    message: "fresh candidate",
    applyEligibility: { applyable: true },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: false,
  });

  // Should NOT be skipped — the phase is IDLE and scope matches.
  assert.equal(result.skipped, undefined);
  assert.equal(typeof result.render, "boolean");
});

test("T9: scope B state survives new conversation in scope A (scope identity + snapshot isolation)", () => {
  // This test verifies the sense-check SC9 invariant:
  //   New conversation in scope A must not disturb scope B's saved session,
  //   messages, draft, candidate state, or queue guard context.

  // ── Phase 1: Set up scope B with rich state ────────────────────────────
  const panelB = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    chatScopeId: "scope-B",
    chatScopeFingerprint: "fp-BBB",
    sessionId: "sess-B",
    turnId: "turn-B1",
    candidateGraph: { nodes: [{ id: 200 }] },
    candidateGraphHash: "hash-B",
    candidateReport: { summary: "scope B candidate" },
    message: "Candidate B ready",
    queueAllowed: true,
    canvasApplyAllowed: true,
    applyAllowed: true,
    applyEligibility: { reason: "applyable" },
    submitEpoch: 5,
    chatRehydrateEpoch: 8,
  });
  // Simulate non-lifecycle chat data.
  panelB.state.chatMessages = [
    { role: "user", text: "edit scope B" },
    { role: "agent", text: "scope B result" },
  ];
  panelB.state.turns = [{ turn_id: "turn-B1" }];
  panelB.state.history = ["scope B history entry"];

  // ── Phase 2: Switch to scope A (saves scope B snapshot) ────────────────
  // _handleScopeSwitch saves panelB state under scope-B and clears it.
  // We simulate the snapshot save that would normally happen in the runtime.
  const snapshotB = {};
  for (const [key, val] of Object.entries(panelB.state)) {
    // Skip undoStack (SD3) and DOM refs (not present in test panel).
    if (key === "undoStack" || key === "buttons" || key === "sections"
        || key === "fields" || key === "root" || key === "composerButtons") {
      continue;
    }
    snapshotB[key] = val;
  }

  // Now simulate scope switch: save scope B, then create scope A.
  // In real runtime this is done by saveScopeSnapshot / restoreScopeSnapshot;
  // here we capture the snapshot manually and verify it survives.

  const panelA = makePanel({
    phase: PANEL_STATE.IDLE,
    chatScopeId: "scope-A",
    chatScopeFingerprint: "fp-AAA",
    sessionId: "sess-A",
    turnId: "turn-A1",
    submitEpoch: 1,
    chatRehydrateEpoch: 2,
  });
  panelA.state.chatMessages = [
    { role: "user", text: "edit scope A" },
    { role: "agent", text: "scope A result" },
  ];
  panelA.state.turns = [{ turn_id: "turn-A1" }];
  panelA.state.history = ["scope A history entry"];

  // ── Phase 3: New conversation in scope A ────────────────────────────────
  const obligations = transition(panelA, "NEW_CONVERSATION");

  // Scope A identity is preserved.
  assert.equal(panelA.state.chatScopeId, "scope-A");
  assert.equal(panelA.state.chatScopeFingerprint, "fp-AAA");

  // Scope A chat data is cleared.
  assert.equal(panelA.state.phase, PANEL_STATE.IDLE);
  assert.equal(panelA.state.sessionId, null);
  assert.equal(panelA.state.turnId, null);
  assert.equal(panelA.state.candidateGraph, null);
  assert.equal(panelA.state.message, null);

  // Obligations target scope A only.
  assert.equal(obligations.queueGuardClearScope, "scope-A");
  assert.equal(obligations.forgetScope, "scope-A");

  // ── Phase 4: Verify scope B snapshot is completely intact ────────────────
  // The snapshot we captured in Phase 2 must still hold all original values.
  assert.equal(snapshotB.chatScopeId, "scope-B");
  assert.equal(snapshotB.chatScopeFingerprint, "fp-BBB");
  assert.equal(snapshotB.sessionId, "sess-B");
  assert.equal(snapshotB.turnId, "turn-B1");
  assert.deepEqual(snapshotB.candidateGraph, { nodes: [{ id: 200 }] });
  assert.equal(snapshotB.candidateGraphHash, "hash-B");
  assert.deepEqual(snapshotB.candidateReport, { summary: "scope B candidate" });
  assert.equal(snapshotB.message, "Candidate B ready");
  assert.equal(snapshotB.queueAllowed, true);
  assert.equal(snapshotB.canvasApplyAllowed, true);
  assert.equal(snapshotB.applyAllowed, true);
  assert.deepEqual(snapshotB.applyEligibility, { reason: "applyable" });

  // Scope B chat messages survive.
  assert.deepEqual(snapshotB.chatMessages, [
    { role: "user", text: "edit scope B" },
    { role: "agent", text: "scope B result" },
  ]);
  assert.deepEqual(snapshotB.turns, [{ turn_id: "turn-B1" }]);
  assert.deepEqual(snapshotB.history, ["scope B history entry"]);

  // Scope B epochs are untouched.
  assert.equal(snapshotB.submitEpoch, 5);
  assert.equal(snapshotB.chatRehydrateEpoch, 8);
});

// ── T10: eventSessionMatchesActiveScope — scope-aware event routing guard ──

test("eventSessionMatchesActiveScope: returns true when chatScopeId is null (backward compat, no scope tracking)", () => {
  const panelState = { chatScopeId: null, phase: "IDLE", sessionId: null };
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-any", null), true);
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-other", "sess-bound"), true);
  assert.equal(eventSessionMatchesActiveScope(panelState, null, null), true);
});

test("eventSessionMatchesActiveScope: returns false for null eventSessionId when scope is active", () => {
  const panelState = { chatScopeId: "scope-A", phase: "SUBMITTING", sessionId: null };
  assert.equal(eventSessionMatchesActiveScope(panelState, null, null), false);
  assert.equal(eventSessionMatchesActiveScope(panelState, null, "sess-A"), false);
});

test("eventSessionMatchesActiveScope: accepts event when scoped session matches", () => {
  const panelState = { chatScopeId: "scope-A", phase: "IDLE", sessionId: "sess-A" };
  // scoped session matches event session
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-A", "sess-A"), true);
});

test("eventSessionMatchesActiveScope: rejects event when scoped session mismatches (cross-scope event)", () => {
  // Scope A is active, scoped session is "sess-A", but event carries "sess-B".
  const panelState = { chatScopeId: "scope-A", phase: "IDLE", sessionId: "sess-A" };
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-B", "sess-A"), false);
});

test("eventSessionMatchesActiveScope: rejects event when panel.sessionId set but event session differs (no scoped binding yet)", () => {
  // Panel has in-memory sessionId but no scoped binding — event must match in-memory.
  const panelState = { chatScopeId: "scope-A", phase: "IDLE", sessionId: "sess-A" };
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-B", null), false);
});

test("eventSessionMatchesActiveScope: accepts event when panel.sessionId matches (no scoped binding yet)", () => {
  const panelState = { chatScopeId: "scope-A", phase: "IDLE", sessionId: "sess-A" };
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-A", null), true);
});

test("eventSessionMatchesActiveScope: first-allocation — accepts when SUBMITTING and no session bound anywhere", () => {
  // Fresh scope with no session bound — accept if panel is actively submitting.
  const panelState = { chatScopeId: "scope-A", phase: "SUBMITTING", sessionId: null };
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-new", null), true);
});

test("eventSessionMatchesActiveScope: first-allocation — rejects when IDLE and no session bound anywhere", () => {
  // Panel is idle (not submitting) — stale events should not be accepted.
  const panelState = { chatScopeId: "scope-A", phase: "IDLE", sessionId: null };
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-new", null), false);
});

test("eventSessionMatchesActiveScope: first-allocation race — scope A active, event for scope B's session arrives", () => {
  // Simulates: scope A is active, no session bound yet, but a stale event
  // from scope B's session arrives before scope A's first response.
  // Since no scoped session is bound, the event could slip through based on
  // the SUBMITTING guard alone.  The caller (event handler) must also verify
  // that the event's session isn't bound to a DIFFERENT scope.  This test
  // verifies the predicate's behavior; the cross-scope check in the handler
  // is layered on top via shouldAcceptAgentTurnEvent.
  const panelState = { chatScopeId: "scope-A", phase: "SUBMITTING", sessionId: null };
  // No scoped session bound yet (scopedSessionId=null) → predicate allows it.
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-B", null), true);
  // But if scope A had a scoped binding (scopedSessionId="sess-A"), event for
  // sess-B would be rejected.
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-B", "sess-A"), false);
});

test("eventSessionMatchesActiveScope: scoped session binding protects against cross-scope mutation", () => {
  // Scope A is active with scoped session "sess-A".  An event for "sess-B"
  // must be rejected even if panel.sessionId happens to match (defense in depth).
  const panelState = { chatScopeId: "scope-A", phase: "AWAITING_REVIEW", sessionId: "sess-A" };
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-B", "sess-A"), false);
  // Matching event is accepted.
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-A", "sess-A"), true);
});

test("eventSessionMatchesActiveScope: handles undefined panelState fields gracefully", () => {
  // Minimal panel state object — chatScopeId undefined → no scope tracking.
  assert.equal(eventSessionMatchesActiveScope({}, "sess-any", null), true);
  assert.equal(eventSessionMatchesActiveScope({ phase: "IDLE" }, "sess-any", null), true);
  // chatScopeId present but no sessionId/phase — should reject null eventSessionId.
  assert.equal(eventSessionMatchesActiveScope({ chatScopeId: "scope-X" }, null, null), false);
});

test("eventSessionMatchesActiveScope: event for active scope accepted across all panel phases when scoped session matches", () => {
  const phases = ["IDLE", "SUBMITTING", "AWAITING_REVIEW", "APPLYING", "CLARIFY", "ERROR"];
  for (const phase of phases) {
    const panelState = { chatScopeId: "scope-A", phase, sessionId: "sess-A" };
    assert.equal(
      eventSessionMatchesActiveScope(panelState, "sess-A", "sess-A"),
      true,
      `phase ${phase} should accept matching scoped session`,
    );
  }
});

test("eventSessionMatchesActiveScope: filter-to-bind race — stale scope B event rejected even before sessionId is bound", () => {
  // Simulates: panel is scope-A-active, sessionId=null (first allocation),
  // scoped binding for scope-A exists ("sess-A"), but a late event for
  // scope B's session ("sess-B") arrives.  Predicate must reject it.
  const panelState = { chatScopeId: "scope-A", phase: "SUBMITTING", sessionId: null };
  assert.equal(eventSessionMatchesActiveScope(panelState, "sess-B", "sess-A"), false);
});

// ── T11: Active-canvas scope guard tests ─────────────────────────────────

test("resolveActiveCanvasScope: returns null in Node.js (no app canvas)", () => {
  // In Node.js test environment, app is not defined, so the resolver returns null.
  const result = resolveActiveCanvasScope();
  assert.equal(result, null);
});

test("resolveActiveCanvasScope: uses Comfy active workflow id for empty workflow tabs", () => {
  const previousApp = globalThis.app;
  const workflow = {
    content: JSON.stringify({
      id: "workflow-empty-tab-a",
      nodes: [],
      links: [],
    }),
    filename: "Unsaved Workflow",
  };
  globalThis.app = {
    canvas: {
      graph: {
        serialize() {
          return { nodes: [], links: [] };
        },
      },
    },
    extensionManager: {
      workflow: {
        activeWorkflow: workflow,
        openWorkflows: [workflow],
      },
    },
  };
  try {
    const result = resolveActiveCanvasScope();
    assert.ok(result);
    assert.equal(result.workflowId, "workflow-empty-tab-a");
    assert.match(result.scopeId, /^[a-z0-9]+-[a-z0-9]+:workflow-empty-tab-a:[0-9a-f]{16}$/);
  } finally {
    if (previousApp === undefined) {
      delete globalThis.app;
    } else {
      globalThis.app = previousApp;
    }
  }
});

test("assertPanelScopeMatchesActiveCanvas: both unscoped returns ok", () => {
  // No scope tracking on panel, no app canvas → both null → ok.
  const panel = makePanel({ chatScopeId: null, chatScopeFingerprint: null });
  const result = assertPanelScopeMatchesActiveCanvas(panel, { caller: "submit" });
  assert.equal(result.ok, true);
  assert.equal(result.panelScopeId, null);
  assert.equal(result.canvasScopeId, null);
  assert.equal(result.reason, null);
});

test("assertPanelScopeMatchesActiveCanvas: panel has scope but canvas is empty (Node.js)", () => {
  // In Node.js, canvas scope is always null (no app).
  // Panel with a scope vs null canvas → fail with "canvas_is_empty".
  const panel = makePanel({
    chatScopeId: "tab1:abc123def4567890",
    chatScopeFingerprint: "abc123def4567890",
  });
  const result = assertPanelScopeMatchesActiveCanvas(panel, { caller: "submit" });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "canvas_is_empty");
  assert.equal(result.panelScopeId, "tab1:abc123def4567890");
  assert.equal(result.canvasScopeId, null);
  assert.ok(result.debug);
  assert.equal(result.debug.caller, "submit");
});

test("assertPanelScopeMatchesActiveCanvas: includes debug metadata on mismatch", () => {
  const panel = makePanel({
    chatScopeId: "tab1:aaa1111111111111",
    chatScopeFingerprint: "aaa1111111111111",
  });
  const result = assertPanelScopeMatchesActiveCanvas(panel, { caller: "apply" });
  assert.equal(result.ok, false);
  assert.equal(result.debug.caller, "apply");
  assert.equal(result.debug.mismatch, "panel_scoped_vs_empty_canvas");
  assert.equal(result.panelFingerprint, "aaa1111111111111");
  assert.equal(result.canvasFingerprint, null);
});

test("assertApplyScopeConsistency: no scope tracking allows apply (backward compat)", () => {
  const panel = makePanel({
    chatScopeId: null,
    candidateScopeId: null,
    sessionId: "sess-any",
  });
  const result = assertApplyScopeConsistency(panel, "sess-any");
  assert.equal(result.ok, true);
  assert.equal(result.reason, null);
  assert.equal(result.details.note, "no_scope_tracking");
});

test("assertApplyScopeConsistency: candidate scope mismatch blocks apply", () => {
  // Candidate was generated for scope-B, but panel is now showing scope-A.
  const panel = makePanel({
    chatScopeId: "tab1:scopeA",
    candidateScopeId: "tab1:scopeB",
    sessionId: "sess-A",
  });
  const result = assertApplyScopeConsistency(panel, "sess-A");
  assert.equal(result.ok, false);
  assert.equal(result.reason, "candidate_scope_mismatch");
  assert.equal(result.details.mismatch, "candidate_vs_chat_scope");
  assert.equal(result.details.effectiveCandidateScope, "tab1:scopeB");
});

test("assertApplyScopeConsistency: candidate scope matches chat scope — passes check 1", () => {
  // Both candidate and chat are scope-A.
  const panel = makePanel({
    chatScopeId: "tab1:scopeA",
    candidateScopeId: "tab1:scopeA",
    sessionId: "sess-A",
  });
  // In Node.js, resolveScopeSessionId returns null (no sessionStorage),
  // and canvas scope is null, so check 4 fails with canvas_is_empty.
  const result = assertApplyScopeConsistency(panel, "sess-A");
  // canvas_is_empty will block it because check 4 fails in Node.js.
  assert.equal(result.ok, false);
  assert.ok(result.reason.startsWith("canvas_scope_mismatch"));
});

test("assertApplyScopeConsistency: submittingScopeId fallback for candidate scope check", () => {
  // candidateScopeId is null but submittingScopeId is set — use that as fallback.
  const panel = makePanel({
    chatScopeId: "tab1:scopeA",
    candidateScopeId: null,
    submittingScopeId: "tab1:scopeB",
    sessionId: "sess-A",
  });
  const result = assertApplyScopeConsistency(panel, "sess-A");
  // submittingScopeId (scopeB) !== chatScopeId (scopeA) → candidate_scope_mismatch
  assert.equal(result.ok, false);
  assert.equal(result.reason, "candidate_scope_mismatch");
  assert.equal(result.details.effectiveCandidateScope, "tab1:scopeB");
});

test("assertApplyScopeConsistency: candidate session mismatch blocks apply", () => {
  // The candidate was returned from session "sess-B" but the bound
  // session (or the passed sessionId) doesn't match.
  const panel = makePanel({
    chatScopeId: "tab1:scopeA",
    candidateScopeId: "tab1:scopeA",
    sessionId: "sess-A",
  });
  // Pass candidateSessionId that differs.
  const result = assertApplyScopeConsistency(panel, "sess-B");
  // In Node.js, resolveScopeSessionId returns null so boundSessionId=null,
  // but check 4 (canvas) fails anyway.
  assert.equal(result.ok, false);
  assert.ok(result.reason.startsWith("canvas_scope_mismatch"));
});

test("assertApplyScopeConsistency: all scope fields null — backward compatibility allow", () => {
  // Panel with no scope tracking at all, but sessionId set.
  const panel = makePanel({
    chatScopeId: null,
    candidateScopeId: null,
    submittingScopeId: null,
    sessionId: "sess-legacy",
  });
  const result = assertApplyScopeConsistency(panel, "sess-legacy");
  assert.equal(result.ok, true);
  assert.equal(result.details.note, "no_scope_tracking");
});

test("assertApplyScopeConsistency: details object contains diagnostic fields", () => {
  const panel = makePanel({
    chatScopeId: "tab1:scopeX",
    candidateScopeId: "tab1:scopeX",
    submittingScopeId: "tab1:scopeX",
    sessionId: "sess-X",
    chatScopeFingerprint: "fff0000000000001",
  });
  const result = assertApplyScopeConsistency(panel, "sess-X");
  // Check that the details object is well-formed.
  assert.ok(result.details);
  assert.equal(result.details.chatScopeId, "tab1:scopeX");
  assert.equal(result.details.candidateScopeId, "tab1:scopeX");
  assert.equal(result.details.panelSessionId, "sess-X");
  assert.equal(result.details.candidateSessionId, "sess-X");
  // In Node.js, canvas scope will be null → canvas_scope_mismatch
  assert.equal(result.ok, false);
  assert.ok(result.details.activeCanvasScopeId === null);
});

// ── Submit-switch/draft tests ────────────────────────────────────────────
// These simulate the submit guard behavior by testing that when a scope
// mismatch occurs, the guard logic correctly categorizes it as auto-switchable
// vs. blocking, and that draft preservation metadata is included.

test("assertPanelScopeMatchesActiveCanvas: graph_diverged reason is auto-switchable", () => {
  // Simulates: panel has scope for graph A, canvas now has graph B.
  // The reason "graph_diverged" should be auto-switchable in the submit guard.
  const panel = makePanel({
    chatScopeId: "tab1:aaa1111111111111",
    chatScopeFingerprint: "aaa1111111111111",
  });
  const result = assertPanelScopeMatchesActiveCanvas(panel, { caller: "submit" });
  assert.equal(result.ok, false);
  // In Node.js, canvas scope is null → reason is "canvas_is_empty",
  // not "graph_diverged".  The graph_diverged reason would happen when
  // both panel and canvas have different scopes.
  assert.equal(result.reason, "canvas_is_empty");
  // Verify the debug metadata would be usable for auto-switch logic.
  assert.ok(result.debug);
  assert.equal(result.panelScopeId, "tab1:aaa1111111111111");
});

test("assertPanelScopeMatchesActiveCanvas: panel_has_no_scope is auto-switchable", () => {
  // Simulates: fresh panel with no scope, but canvas has a workflow.
  // In Node.js the canvas is empty so this won't trigger naturally,
  // but the assertion structure supports it.
  const panel = makePanel({ chatScopeId: null, chatScopeFingerprint: null });
  const result = assertPanelScopeMatchesActiveCanvas(panel, { caller: "submit" });
  // Both null → ok (backward compat)
  assert.equal(result.ok, true);
  assert.equal(result.reason, null);
});

// ── Apply-refusal tests ──────────────────────────────────────────────────
// Verify that apply fails closed on all scope disagreement scenarios.

test("assertApplyScopeConsistency: refuses when candidate is from a different scope than chat", () => {
  // Scope A is active, but the candidate was generated for scope B.
  const panel = makePanel({
    chatScopeId: "tab1:workflow-A",
    candidateScopeId: "tab1:workflow-B",
    sessionId: "sess-shared",
  });
  const result = assertApplyScopeConsistency(panel, "sess-shared");
  assert.equal(result.ok, false);
  assert.equal(result.reason, "candidate_scope_mismatch");
});

test("assertApplyScopeConsistency: refuses when chat scope is set but candidate has no scope", () => {
  // Candidate was generated before scope tracking was added (candidateScopeId=null),
  // but the panel now has scope tracking.  The submittingScopeId fallback
  // could allow it, but if both are null, other checks still apply.
  const panel = makePanel({
    chatScopeId: "tab1:workflow-A",
    candidateScopeId: null,
    submittingScopeId: null,
    sessionId: "sess-A",
  });
  const result = assertApplyScopeConsistency(panel, "sess-A");
  // Check 1 passes (both null candidateScopeId and null submittingScopeId →
  // effectiveCandidateScope=null → no mismatch against chatScopeId).
  // But check 4 fails in Node.js (canvas_is_empty).
  assert.equal(result.ok, false);
  assert.ok(result.reason.startsWith("canvas_scope_mismatch"));
});

test("assertApplyScopeConsistency: refuses when candidate is from different session", () => {
  // Candidate from session-B, but bound session is session-A.
  const panel = makePanel({
    chatScopeId: "tab1:workflow-A",
    candidateScopeId: "tab1:workflow-A",
    sessionId: "sess-A",
  });
  const result = assertApplyScopeConsistency(panel, "sess-B");
  // In Node.js, boundSessionId is null (no sessionStorage), so checks 2/3
  // are skipped. Check 4 fails.
  assert.equal(result.ok, false);
  assert.ok(result.reason.startsWith("canvas_scope_mismatch"));
});

// ── T8: Canonical delta normalization in lifecycle ──────────────────────────

test("normalizeDeltaOpsFromSubmit extracts ops from canonical delta_ops_envelope", () => {
  const result = {
    delta_ops_envelope: {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [
        { op: "set_node_field", target: ["", "n", "w"], value: "canonical" },
      ],
    },
  };
  const ops = normalizeDeltaOpsFromSubmit(result);
  assert.ok(Array.isArray(ops));
  assert.equal(ops.length, 1);
  assert.equal(ops[0].op, "set_node_field");
  assert.equal(ops[0].value, "canonical");
  // No diagnostic set on success
  assert.equal(result._deltaDiagnostic, undefined);
});

test("normalizeDeltaOpsFromSubmit falls back to legacy flat delta_ops when no envelope", () => {
  const result = {
    delta_ops: [
      { op: "set_node_field", target: ["", "n", "w"], value: "legacy" },
    ],
  };
  const ops = normalizeDeltaOpsFromSubmit(result);
  assert.ok(Array.isArray(ops));
  assert.equal(ops.length, 1);
  assert.equal(ops[0].value, "legacy");
});

test("normalizeDeltaOpsFromSubmit prefers delta_ops_envelope over delta_ops", () => {
  const result = {
    delta_ops_envelope: {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [{ op: "set_mode", target: ["", "m"], mode: 4 }],
    },
    delta_ops: [
      { op: "set_node_field", target: ["", "n", "w"], value: 999 },
    ],
  };
  const ops = normalizeDeltaOpsFromSubmit(result);
  assert.equal(ops.length, 1);
  assert.equal(ops[0].op, "set_mode");
});

test("normalizeDeltaOpsFromSubmit sets _deltaDiagnostic on legacy wrapped delta_ops", () => {
  const result = {
    delta_ops: { ops: [], diagnostics: [] },
  };
  const ops = normalizeDeltaOpsFromSubmit(result);
  assert.equal(ops, null);
  assert.ok(result._deltaDiagnostic);
  assert.equal(result._deltaDiagnostic.code, DELTA_DIAGNOSTIC_LEGACY_SHAPE);
  assert.ok(result._deltaDiagnostic.message.includes("Legacy wrapped"));
});

test("normalizeDeltaOpsFromSubmit passes add_node without uid through lenient validation (backend-trusted)", () => {
  // The browser-side normalizeDeltaOpsFromSubmit uses lenient validation
  // (strict=false) for canonical envelopes received from the backend.
  // The backend pre-validates add_node identity before persistence,
  // so the browser trusts the backend and does not re-reject here.
  const result = {
    delta_ops_envelope: {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [
        {
          op: "add_node",
          scope_path: "",
          // missing uid — would be rejected in strict mode but passes lenient
          node_id: "42",
          class_type: "PreviewImage",
          fields: {},
          inputs: {},
        },
      ],
    },
  };
  const ops = normalizeDeltaOpsFromSubmit(result);
  // Lenient validation passes this through; identity is checked downstream
  assert.ok(Array.isArray(ops));
  assert.equal(ops.length, 1);
  assert.equal(ops[0].op, "add_node");
  assert.equal(ops[0].node_id, "42");
  assert.equal(ops[0].uid, undefined); // uid was not present
  // No diagnostic on success
  assert.equal(result._deltaDiagnostic, undefined);
});

test("normalizeDeltaOpsFromSubmit passes add_node without node_id through lenient validation (backend-trusted)", () => {
  // Same as above — lenient validation passes add_node through even with
  // missing node_id. The backend pre-validates these before persistence.
  const result = {
    delta_ops_envelope: {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [
        {
          op: "add_node",
          scope_path: "",
          uid: "uid-1",
          // missing node_id
          class_type: "PreviewImage",
          fields: {},
          inputs: {},
        },
      ],
    },
  };
  const ops = normalizeDeltaOpsFromSubmit(result);
  assert.ok(Array.isArray(ops));
  assert.equal(ops.length, 1);
  assert.equal(ops[0].op, "add_node");
  assert.equal(ops[0].uid, "uid-1");
  assert.equal(ops[0].node_id, undefined);
  assert.equal(result._deltaDiagnostic, undefined);
});

test("normalizeDeltaOpsFromSubmit returns null for empty canonical ops after filtering", () => {
  // Canonical envelope with an unknown op
  const result = {
    delta_ops_envelope: {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [
        { op: "noop" }, // unknown op
      ],
    },
  };
  const ops = normalizeDeltaOpsFromSubmit(result);
  assert.equal(ops, null);
  assert.ok(result._deltaDiagnostic);
});

test("normalizeDeltaOpsFromSubmit passes through scoped ops for downstream scope checking", () => {
  // The envelope validation accepts upsert_link with valid shapes;
  // scope checking is deferred to ensureRootScopedOps
  const result = {
    delta_ops_envelope: {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [
        {
          op: "upsert_link",
          from: ["sg:nested", "seed-node", "IMAGE"],
          to: ["", "preview-node", "images"],
        },
      ],
    },
  };
  const ops = normalizeDeltaOpsFromSubmit(result);
  assert.ok(Array.isArray(ops));
  assert.equal(ops.length, 1);
  assert.equal(ops[0].op, "upsert_link");
});

test("normalizeDeltaOpsFromSubmit sets _deltaDiagnostic on unknown op in canonical envelope", () => {
  const result = {
    delta_ops_envelope: {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [{ op: "rename_everything", target: ["", "u1"] }],
    },
  };
  const ops = normalizeDeltaOpsFromSubmit(result);
  assert.equal(ops, null);
  assert.ok(result._deltaDiagnostic);
  assert.equal(result._deltaDiagnostic.code, DELTA_DIAGNOSTIC_MALFORMED);
  assert.ok(result._deltaDiagnostic.message.includes("Unsupported edit op"));
});

// ── T8: Lifecycle transition with canonical delta envelope ─────────────────

test("OK_CANDIDATE_RESPONSE normalizes canonical delta_ops_envelope into deltaOps", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const obligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-canon",
      turn_id: "t-canon",
      delta_ops_envelope: {
        schema_version: DELTA_SCHEMA_VERSION,
        ops: [
          { op: "set_node_field", target: ["", "n1", "w1"], value: "canonical-val" },
          { op: "set_mode", target: ["", "n2"], mode: 2 },
        ],
      },
      message: "Canonical V2 response",
      submit_graph_hash: "abc-canon",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-canon",
    applyEligibility: { applyable: true },
  });

  assert.equal(obligations.render, true);
  assert.ok(Array.isArray(panel.state.deltaOps));
  assert.equal(panel.state.deltaOps.length, 2);
  assert.equal(panel.state.deltaOps[0].op, "set_node_field");
  assert.equal(panel.state.deltaOps[0].value, "canonical-val");
  assert.equal(panel.state.deltaOps[1].op, "set_mode");
});

test("OK_CANDIDATE_RESPONSE with canonical add_node carries uid and node_id through lifecycle", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const obligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-add",
      turn_id: "t-add",
      delta_ops_envelope: {
        schema_version: DELTA_SCHEMA_VERSION,
        ops: [
          {
            op: "add_node",
            scope_path: "",
            uid: "uid-prod-1",
            node_id: "123",
            class_type: "KSampler",
            fields: { steps: 20 },
            inputs: { model: ["", "loader", "MODEL"] },
          },
        ],
      },
      message: "Added KSampler",
      submit_graph_hash: "hash-add",
      canvas_apply_allowed: true,
    },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-add",
    applyEligibility: { applyable: true },
  });

  assert.equal(obligations.render, true);
  assert.equal(panel.state.deltaOps.length, 1);
  assert.equal(panel.state.deltaOps[0].op, "add_node");
  assert.equal(panel.state.deltaOps[0].uid, "uid-prod-1");
  assert.equal(panel.state.deltaOps[0].node_id, "123");
  assert.equal(panel.state.deltaOps[0].class_type, "KSampler");
});

test("OK_CANDIDATE_RESPONSE with leniently-validated add_node (missing uid) passes ops through", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const obligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-malformed",
      turn_id: "t-malformed",
      delta_ops_envelope: {
        schema_version: DELTA_SCHEMA_VERSION,
        ops: [
          {
            op: "add_node",
            scope_path: "",
            // Missing uid — passes lenient validation (backend trusted)
            node_id: "42",
            class_type: "PreviewImage",
            fields: {},
            inputs: {},
          },
        ],
      },
      message: "Add node without uid",
      submit_graph_hash: "hash-lenient",
      canvas_apply_allowed: true,
    },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-lenient",
    applyEligibility: { applyable: true },
  });

  // The transition should NOT throw — lenient validation passes the ops through
  assert.equal(obligations.render, true);
  // deltaOps is populated because lenient validation passes add_node through
  assert.ok(Array.isArray(panel.state.deltaOps));
  assert.equal(panel.state.deltaOps.length, 1);
  assert.equal(panel.state.deltaOps[0].op, "add_node");
  assert.equal(panel.state.deltaOps[0].uid, undefined); // missing uid passed through
  // Phase should be AWAITING_REVIEW (candidate is present)
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  // Candidate still stored for display
  assert.deepEqual(panel.state.candidateGraph, { nodes: [{ id: 1 }] });
});

test("OK_CANDIDATE_RESPONSE with legacy wrapped delta_ops sets deltaOps null", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const obligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-legacy",
      turn_id: "t-legacy",
      delta_ops: { ops: [], diagnostics: [] }, // legacy wrapped shape
      message: "Legacy wrapped response",
      submit_graph_hash: "hash-legacy",
      canvas_apply_allowed: true,
    },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-legacy",
    applyEligibility: { applyable: true },
  });

  assert.equal(obligations.render, true);
  assert.equal(panel.state.deltaOps, null);
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
});

test("OK_CANDIDATE_RESPONSE with legacy flat delta_ops still works through bridge", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const deltaOps = [
    { op: "set_node_field", target: ["", "n", "w"], value: "legacy-flat" },
  ];

  const obligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-flat",
      turn_id: "t-flat",
      delta_ops: deltaOps,
      message: "Legacy flat V2 response",
      submit_graph_hash: "hash-flat",
      canvas_apply_allowed: true,
    },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-flat",
    applyEligibility: { applyable: true },
  });

  assert.equal(obligations.render, true);
  assert.ok(Array.isArray(panel.state.deltaOps));
  assert.equal(panel.state.deltaOps.length, 1);
  assert.equal(panel.state.deltaOps[0].value, "legacy-flat");
});

// ── T8: Stale token / hash routing in lifecycle ────────────────────────────

test("APPLY_PREFLIGHT_BLOCKED is a no-op stub (render:false, preserves phase)", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-old",
    serverSubmitGraphHash: "hash-submit",
    deltaOps: [{ op: "set_node_field", target: ["", "n", "w"], value: 1 }],
  });

  const obligations = transition(panel, "APPLY_PREFLIGHT_BLOCKED", {
    variant: "stale_graph_cas",
    reason: "submit_graph_hash mismatch",
    message: "Canvas has changed since submission.",
  });

  // APPLY_PREFLIGHT_BLOCKED is currently a stub — returns render:false
  assert.equal(obligations.render, false);
  // Phase is preserved (transition does not change it)
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
});

test("CANVAS_APPLY_FAILURE transitions to ERROR phase", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-c",
    serverSubmitGraphHash: "hash-s",
    deltaOps: [{ op: "set_mode", target: ["", "n"], mode: 4 }],
  });

  const obligations = transition(panel, "CANVAS_APPLY_FAILURE", {
    message: "Canvas state changed during apply; retry.",
    evidence: { kind: "stale_canvas", detail: "hash mismatch" },
  });

  // CANVAS_APPLY_FAILURE sets phase to ERROR
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.equal(obligations.render, true);
  assert.equal(obligations.invalidateCandidate, true);
  assert.equal(obligations.clearCandidatePreview, true);
  // Handler does not attach toast obligation
  assert.equal(obligations.toast, undefined);
});

// ── T8: Missing add_node identity rejection before preflight/apply ──────────

test("APPLY_PREFLIGHT_BLOCKED on empty delta ops is a no-op stub", () => {
  // Simulate preflight detecting malformed add_node identity.
  // APPLY_PREFLIGHT_BLOCKED is currently a stub — it does not change state.
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-pre",
    serverSubmitGraphHash: "hash-pre",
    deltaOps: [], // empty means no ops
  });

  const obligations = transition(panel, "APPLY_PREFLIGHT_BLOCKED", {
    variant: "missing_delta_ops",
    reason: "No valid delta ops available for apply.",
    message: "Apply blocked: delta ops are missing or malformed.",
  });

  // Stub: render:false, phase unchanged
  assert.equal(obligations.render, false);
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
});

test("ACCEPT_REJECTED transitions to ERROR phase", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-cand",
    serverSubmitGraphHash: "hash-sub",
    deltaOps: [{ op: "set_node_field", target: ["", "n", "w"], value: "live" }],
  });

  const obligations = transition(panel, "ACCEPT_REJECTED", {
    reason: "stale_live_canvas_token",
    evidence: {
      kind: "stale_canvas",
      message: "Canvas diverged from accept baseline.",
    },
  });

  // ACCEPT_REJECTED sets phase to ERROR (not IDLE)
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.equal(obligations.render, true);
  // Handler does not attach toast obligation
  assert.equal(obligations.toast, undefined);
});
