import test from "node:test";
import assert from "node:assert/strict";

import {
  PANEL_STATE,
  LIFECYCLE_STATE_FIELDS,
  RENDER_SECTIONS,
  createAgentEditState,
  transition,
  normalizeObligationDirtySections,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

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
  assert.equal(state.applyEligibility, null);
  assert.equal(state.applyEligibilityWarning, null);
  assert.equal(state.applyEligibilityWarningKey, null);
  assert.equal(state.changeDetails, null);
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

// ── LIFECYCLE_STATE_FIELDS ──────────────────────────────────────────────────

test("LIFECYCLE_STATE_FIELDS exports frozen array with 39 field names", () => {
  assert.ok(Object.isFrozen(LIFECYCLE_STATE_FIELDS));
  assert.equal(LIFECYCLE_STATE_FIELDS.length, 39);

  // Spot-check key categories
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("phase"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("sessionId"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("turnId"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("baselineTurnId"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("baselineGraphHash"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("candidateGraph"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("candidateGraphHash"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("candidateReport"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("message"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("failure"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("clarification"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("applyAllowed"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("applyEligibility"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("queueAllowed"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("canvasApplyAllowed"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("inFlightSubmit"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("submitEpoch"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("inFlightApply"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("rebaselinePending"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("lastSubmit"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("lastAppliedChanges"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("changeDetails"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("chatRehydrateEpoch"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("chatRehydrateCommittedEpoch"));
  assert.ok(LIFECYCLE_STATE_FIELDS.includes("syntheticAgentMessage"));

  // No duplicates
  assert.equal(new Set(LIFECYCLE_STATE_FIELDS).size, 39);
});

// ── createAgentEditState ────────────────────────────────────────────────────

test("createAgentEditState initializes all 39 lifecycle fields to defaults", () => {
  const state = createAgentEditState();

  // Every field from LIFECYCLE_STATE_FIELDS must exist on the returned object
  for (const field of LIFECYCLE_STATE_FIELDS) {
    assert.ok(
      Object.prototype.hasOwnProperty.call(state, field),
      `state.${field} must be own property`,
    );
  }

  // No extra own keys beyond the 39 fields
  const ownKeys = Object.keys(state);
  assert.equal(ownKeys.length, 39);

  // Phase default
  assert.equal(state.phase, PANEL_STATE.IDLE);

  // Session / turn identity
  assert.equal(state.sessionId, null);
  assert.equal(state.turnId, null);

  // Baseline defaults
  assertBaselineDefaults(state);

  // Candidate review defaults
  assertCandidateDefaults(state);

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

  assert.equal(b.phase, PANEL_STATE.IDLE);
  assert.equal(b.baselineTurnId, null);
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
  assert.equal(panel.state.syntheticAgentMessage, null);
  assert.equal(panel.state.lastAppliedChanges, null);
  assert.equal(panel.state.lastSubmitFieldChanges, null);
  assert.deepEqual(panel.state.lastSubmit, { task: "replace node" });
  assert.deepEqual(panel.state.debugPayload, { submit: "payload" });
  assertCandidateDefaults(panel.state);
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
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
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
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

  assert.deepEqual(obligations, { render: true, refreshQueueGuard: true });
  assert.equal(panel.state.submitEpoch, 5);
  assert.equal(panel.state.submitAbortController, null);
  assert.equal(panel.state.inFlightSubmit, null);
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
    queueGuardClear: true,
    refreshQueueGuard: true,
    forgetSession: true,
    focusPrompt: true,
  });
  assert.equal(panel.state.submitEpoch, 8);
  assert.equal(panel.state.chatRehydrateEpoch, 12);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.sessionId, null);
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

test("CHAT_REHYDRATE_SUCCESS stores normalized chat payload and persists confirmed session id", () => {
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
  assert.deepEqual(panel.state.chatMessages, messages);
  assert.equal(panel.state.chatLoaded, true);
  assert.equal(panel.state.chatError, null);
  assert.equal(panel.state.chatSessionPath, "out/editor_sessions/sess-123/");
  assert.equal(panel.state.chatDetailJsonPath, "out/editor_sessions/sess-123/session.json");
  assert.equal(panel.state.sessionId, "sess-123");
  assert.deepEqual(panel.state.failure, { code: "KeepFailure" });
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
    dirtySections: STATUS_AND_DEVELOPER_DIRTY_SECTIONS,
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

test("CHAT_REHYDRATE_NO_SESSION clears only thread-visible chat state and leaves metadata clean", () => {
  const panel = makePanel({
    sessionId: "sess-live",
    chatRehydrateEpoch: 4,
    chatMessages: [{ role: "user", text: "old" }],
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

  assert.deepEqual(retryable, { render: true, queueGuardClear: false, refreshQueueGuard: false });
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

  assert.deepEqual(authoritative, { render: true, queueGuardClear: true, refreshQueueGuard: true });
  assert.equal(authoritativePanel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(authoritativePanel.state.failure, authoritativeFailure);
  assert.deepEqual(authoritativePanel.state.applyEligibility, disabledApplyEligibility);
  assert.equal(authoritativePanel.state.applyAllowed, false);
  assert.equal(authoritativePanel.state.canvasApplyAllowed, false);
  assert.equal(authoritativePanel.state.queueAllowed, false);
  assert.deepEqual(authoritativePanel.state.auditRef, { path: "reject-audit.json" });
  assert.equal(authoritativePanel.state.baselineTurnId, "0001");
  assert.equal(authoritativePanel.state.baselineGraphHash, "base-after-reject");
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

  assert.deepEqual(canvas, { render: true });
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
  assert.equal(panel.state.message, "Candidate accepted and applied locally.");
  assert.deepEqual(panel.state.debugPayload, {
    accepted,
    undo_stack_depth: 1,
  });
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
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
    chatMessages: [{ role: "agent", text: "stale" }],
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
  assert.deepEqual(panel.state.chatMessages, []);
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
  });
  assert.equal(panel.state.baselineGraphHash, "baseline-new");
  assert.equal(panel.state.baselineSource, "rebaseline");
  assert.equal(panel.state.baselineRebaselineId, "rebaseline-0001");
  assert.equal(panel.state.rebaselinePending, null);
  assert.equal(panel.state.rebaselineRecovery, null);
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

  assert.deepEqual(obligations, { render: true, queueGuardClear: true, refreshQueueGuard: true });
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

  assert.deepEqual(acceptObligations, { render: true, queueGuardClear: true, refreshQueueGuard: true });
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
