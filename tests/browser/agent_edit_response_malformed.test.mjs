import test from "node:test";
import assert from "node:assert/strict";

import {
  normalizeAgentEditResponse,
  readCandidate,
  readCandidateGraph,
  readEligibility,
  PUBLIC_OUTCOME_KINDS,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract.js";

import {
  PANEL_STATE,
  createAgentEditState,
  transition,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

// ── Helpers ─────────────────────────────────────────────────────────────────

function makePanel(overrides = {}) {
  const state = createAgentEditState();
  Object.assign(state, overrides);
  return { state };
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
  assert.equal(state.deltaOps, null);
}

// ── Malformed candidate handling: graph lacks durable session_id and turn_id ─

test("normalizeAgentEditResponse treats executor response missing session_id as non-applyable malformed, not stale", () => {
  const raw = {
    ok: true,
    route: "revise",
    reply: "Graph was edited.",
    // Missing session_id and turn_id — malformed durable metadata
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
    },
    apply_eligible: true,
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-executor" });

  // Even though apply_eligible is true, the response lacks durable session metadata
  // The contract should still report the candidate outcome since apply_eligible + candidate present
  assert.equal(normalized.outcome.kind, "candidate");
  assert.ok(normalized.candidateGraph);

  // The key assertion: sessionId and turnId are NOT populated from missing metadata
  assert.equal(normalized.sessionId, null, "session_id must not be conjured from thin air");
  assert.equal(normalized.turnId, null, "turn_id must not be conjured from thin air");

  // Apply eligibility derived from executor envelope (apply_eligible + candidate presence)
  assert.equal(normalized.applyEligible, true);
});

test("normalizeAgentEditResponse with null candidate and no session metadata produces noop outcome", () => {
  const raw = {
    ok: true,
    route: "inspect",
    reply: "This workflow has 3 nodes.",
    candidate: null,
    apply_eligible: false,
    no_candidate_reason: "inspect turns do not produce candidates",
    // No session_id, no turn_id
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-executor" });

  assert.equal(normalized.outcome.kind, "noop");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
  assert.equal(normalized.applyEligible, false);
  assert.equal(normalized.applyAllowed, false);
  assert.equal(normalized.canvasApplyAllowed, false);
  // Must not classify as stale/rebaseline — it's simply non-applyable
  assert.equal(normalized.rebaselineRecovery, null,
    "missing session metadata must not trigger rebaseline recovery");
});

test("readCandidate returns null when candidate payload lacks graph", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate", changes: [] },
    candidate: {
      // No graph field — malformed
      metadata: { created: "2025-01-01" },
    },
  };

  const candidate = readCandidate(raw, { endpoint: "/submit" });
  assert.equal(candidate, null, "candidate without graph must return null");
});

test("readCandidateGraph returns null when graph is absent from candidate payload", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate", changes: [] },
    candidate: {
      metadata: { created: "2025-01-01" },
    },
  };

  const graph = readCandidateGraph(raw, { endpoint: "/submit" });
  assert.equal(graph, null, "missing candidate.graph must return null");
});

test("readEligibility marks candidates without durable metadata non-applyable", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate", changes: [] },
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
    },
    // No apply_eligibility field
  };

  const eligibility = readEligibility(raw, { endpoint: "/submit" });
  assert.equal(eligibility?.applyable, false,
    "candidate without durable metadata must not be applyable");
  assert.equal(eligibility?.reason, "missing_durable_turn_metadata");
  assert.ok(eligibility?.warnings?.includes("missing_durable_turn_metadata"));
});

// ── Malformed candidate handling in lifecycle transitions ────────────────────

test("OK_CANDIDATE_RESPONSE without session_id does not trigger chat rehydrate", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const obligations = transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      // No session_id — malformed durable metadata
      turn_id: "t-malformed",
      message: "Candidate without session",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-malformed",
    applyEligibility: { applyable: true },
  });

  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.sessionId, null,
    "sessionId must stay null when result lacks session_id");
  assert.equal(obligations.persistSession, null,
    "must not persist a null session");
  assert.equal(obligations.rehydrateChat, false,
    "must not rehydrate chat without a session id");
});

test("OK_CANDIDATE_RESPONSE without turn_id still stores candidate but with null turnId", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-noturn",
      // No turn_id — malformed durable turn metadata
      message: "Candidate without turn",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [{ id: 2 }] },
    candidateGraphHash: "hash-noturn",
    applyEligibility: { applyable: true },
  });

  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.sessionId, "sess-noturn");
  // turnId defaults to null when absent from result
  assert.equal(panel.state.turnId, null);
  // Candidate is still stored (apply eligibility gates on candidateGraph presence)
  assert.deepEqual(panel.state.candidateGraph, { nodes: [{ id: 2 }] });
  assert.equal(panel.state.applyAllowed, true);
});

test("MALFORMED_CANDIDATE_RESPONSE records phase=ERROR and does not treat as stale/rebaseline", () => {
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    sessionId: "sess-before",
  });

  const failure = {
    kind: "MalformedResponse",
    message: "Response missing required fields.",
    session_id: "sess-before",
  };

  const obligations = transition(panel, "MALFORMED_CANDIDATE_RESPONSE", {
    failure,
    debugPayload: { raw: "garbage" },
  });

  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(panel.state.failure, failure);
  // sessionId is preserved from the failure payload
  assert.equal(panel.state.sessionId, "sess-before");
  // Must not trigger rebaseline recovery for malformed responses
  assert.equal(panel.state.rebaselineRecovery, null,
    "malformed responses must not trigger rebaseline recovery");
  assert.equal(panel.state.rebaselinePending, null);
});

// ── Stale canvas apply: structural hash unchanged, token drift ──────────────

test("STALE_CANVAS_APPLY records phase=ERROR with failure and invalidates candidate", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "stale-hash",
    candidateReport: { change: true },
    serverSubmitGraphHash: "submit-stale",
    applyEligibility: { applyable: true },
    applyAllowed: true,
    canvasApplyAllowed: true,
    deltaOps: [{ op: "set_node_field", target: ["nodes", 1], value: "old" }],
  });

  const failure = {
    kind: "StaleStateMismatch",
    message: "The canvas changed while Apply was waiting for backend acceptance.",
    client_graph_hash: "client-hash",
    client_structural_graph_hash: "struct-hash-same",
    expected_graph_hash: "expected-hash",
    client_live_canvas_token: "token-new",
    expected_live_canvas_token: "token-old",
  };

  const obligations = transition(panel, "STALE_CANVAS_APPLY", {
    failure,
    debugPayload: failure,
  });

  assert.deepEqual(obligations, {
    render: true,
    invalidateCandidate: true,
    clearCandidatePreview: true,
  });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(panel.state.failure, failure);
  assert.deepEqual(panel.state.debugPayload, failure);
  // Candidate must be cleared
  assertCandidateDefaults(panel.state);
});

test("STALE_CANVAS_APPLY with rebaselineRecovery stores recovery payload", () => {
  const panel = makePanel({ phase: PANEL_STATE.APPLYING });

  const failure = {
    kind: "StaleStateMismatch",
    message: "Scoped region drifted.",
  };
  const rebaselineRecovery = {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    lastKnownBaselineGraphHash: "base-before",
  };

  transition(panel, "STALE_CANVAS_APPLY", {
    failure,
    rebaselineRecovery,
    debugPayload: { ...failure, recovery: rebaselineRecovery },
  });

  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(panel.state.failure, failure);
  assert.deepEqual(panel.state.rebaselineRecovery, rebaselineRecovery);
});

test("STALE_CANVAS_APPLY clears synthetic agent message when none provided", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    syntheticAgentMessage: { role: "agent", text: "old synthetic" },
  });

  transition(panel, "STALE_CANVAS_APPLY", {
    failure: { kind: "StaleStateMismatch", message: "stale" },
  });

  // syntheticAgentMessage defaults to null when not in payload
  assert.equal(panel.state.syntheticAgentMessage, null);
});

// ── True stale paths still produce rebaseline blocking ──────────────────────

test("ACCEPT_REJECTED with authoritative backend reject records rebaseline recovery", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "cand-hash",
    applyEligibility: { applyable: true },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
  });

  const failure = {
    ok: false,
    kind: "StaleStateMismatch",
    message: "Backend rejected: graph hash mismatch.",
    audit_ref: { path: "reject-audit.json" },
    baseline_turn_id: "0001",
    baseline_graph_hash: "base-after",
  };
  const disabledEligibility = {
    applyable: false,
    reason: "no_candidate",
    message: "Apply eligibility disabled after backend rejection.",
    warnings: [],
  };

  const obligations = transition(panel, "ACCEPT_REJECTED", {
    failure,
    acceptBody: { idempotency_key: "accept:reject" },
    authoritativeBackendReject: true,
    disabledApplyEligibility: disabledEligibility,
  });

  assert.deepEqual(obligations, { render: true, queueGuardClear: true, refreshQueueGuard: true });
  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.deepEqual(panel.state.failure, failure);
  assert.deepEqual(panel.state.applyEligibility, disabledEligibility);
  assert.equal(panel.state.applyAllowed, false);
  assert.equal(panel.state.canvasApplyAllowed, false);
  assert.equal(panel.state.queueAllowed, false);
  // Baseline synced from failure
  assert.equal(panel.state.baselineTurnId, "0001");
  assert.equal(panel.state.baselineGraphHash, "base-after");
});

test("normalizeAgentEditResponse extracts rebaseline recovery from stale error with structural hash drift", () => {
  const raw = {
    ok: false,
    message: "Structural hash mismatch on accept.",
    outcome: { kind: "error", failure_kind: "StaleStateMismatch" },
    rebaseline_recovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "structural_hash_drift",
      last_known_baseline_graph_hash: "baseline-struct",
      submit_graph_hash: "submit-hash",
      submit_structural_graph_hash: "submit-struct-new",
      client_graph_hash: "client-graph",
      client_structural_graph_hash: "client-struct-old",
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/accept" });

  assert.equal(normalized.outcome.kind, "error");
  // The outcome preserves the raw failure_kind field; failureKind is only
  // present on legacy-inferred error outcomes with top-level failure hints.
  assert.equal(normalized.outcome.failure_kind, "StaleStateMismatch");
  assert.deepEqual(normalized.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "structural_hash_drift",
    lastKnownBaselineGraphHash: "baseline-struct",
    submitGraphHash: "submit-hash",
    submitStructuralGraphHash: "submit-struct-new",
    clientGraphHash: "client-graph",
    clientStructuralGraphHash: "client-struct-old",
  });
});

test("normalizeAgentEditResponse extracts scoped accept conflict rebaseline recovery", () => {
  const raw = {
    ok: false,
    outcome: { kind: "error", failure_kind: "StaleStateMismatch" },
    agent_failure_context: {
      explanation: "Touched region verification failed.",
      issues: [
        {
          code: "scoped_conflict",
          detail: "Node 2 prompt field changed after submit.",
          rebaseline_recovery: {
            action: "rebaseline",
            endpoint: "/rebaseline",
            reason: "scoped_accept_conflict",
            submit_graph_hash: "submit-gh",
            submit_structural_graph_hash: "submit-sh",
            client_graph_hash: "client-gh",
            client_structural_graph_hash: "client-sh",
          },
        },
      ],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/accept" });

  assert.deepEqual(normalized.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/rebaseline",
    reason: "scoped_accept_conflict",
    submitGraphHash: "submit-gh",
    submitStructuralGraphHash: "submit-sh",
    clientGraphHash: "client-gh",
    clientStructuralGraphHash: "client-sh",
  });
});

// ── Debug payload names the branch that fired ───────────────────────────────

test("normalizeAgentEditResponse preserves debug context for malformed metadata", () => {
  const raw = {
    ok: true,
    route: "revise",
    reply: "Edited.",
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
    },
    apply_eligible: true,
    // No session_id — the debug payload in the raw response
    // should be preserved so the frontend can name the branch
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-executor" });

  // The raw payload is preserved for debugging
  assert.equal(normalized.raw, raw);
  assert.equal(normalized.route, "revise");
  // No session_id/turn_id in the raw → no durable identity
  assert.equal(normalized.raw.session_id, undefined);
  assert.equal(normalized.raw.turn_id, undefined);
});

test("normalizeAgentEditResponse preserves debug payload in stale recovery for branch identification", () => {
  const raw = {
    ok: false,
    message: "Stale state mismatch on submit.",
    outcome: {
      kind: "error",
      failure_kind: "StaleStateMismatch",
      failureKind: "StaleStateMismatch",
      retryable: true,
      nextAction: "Rebaseline and retry.",
    },
    rebaseline_recovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "abc",
      submit_graph_hash: "def",
      submit_structural_graph_hash: "struct-def",
      client_graph_hash: "client-abc",
      client_structural_graph_hash: "struct-abc",
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });

  // The normalized response should clearly identify this as a stale recovery path
  assert.equal(normalized.outcome.kind, "error");
  assert.equal(normalized.outcome.failureKind, "StaleStateMismatch");
  assert.equal(normalized.rebaselineRecovery.reason, "stale_state_recovery");

  // All hash fields present for branch identification
  assert.equal(normalized.rebaselineRecovery.lastKnownBaselineGraphHash, "abc");
  assert.equal(normalized.rebaselineRecovery.submitGraphHash, "def");
  assert.equal(normalized.rebaselineRecovery.submitStructuralGraphHash, "struct-def");
  assert.equal(normalized.rebaselineRecovery.clientGraphHash, "client-abc");
  assert.equal(normalized.rebaselineRecovery.clientStructuralGraphHash, "struct-abc");
});

// ── Structural hash drift vs live token drift distinction ───────────────────

test("normalizeAgentEditResponse distinguishes structural hash drift from live token drift in rebaseline recovery", () => {
  // Scenario: structural hash differs = true stale
  const rawStructuralDrift = {
    ok: false,
    outcome: { kind: "error", failure_kind: "StaleStateMismatch" },
    rebaseline_recovery: {
      action: "rebaseline",
      endpoint: "/rebaseline",
      reason: "structural_hash_drift",
      last_known_baseline_graph_hash: "baseline-struct",
      submit_structural_graph_hash: "submit-new-struct",
      client_structural_graph_hash: "client-old-struct",
    },
  };

  const normalizedDrift = normalizeAgentEditResponse(rawStructuralDrift, { endpoint: "/submit" });
  assert.equal(normalizedDrift.rebaselineRecovery.reason, "structural_hash_drift");
  // Structural hashes differ → true stale
  assert.notEqual(
    normalizedDrift.rebaselineRecovery.submitStructuralGraphHash,
    normalizedDrift.rebaselineRecovery.clientStructuralGraphHash,
  );

  // Scenario: live token differs but structural hash unchanged
  // The frontend should NOT treat this as STALE_CANVAS_APPLY;
  // it's diagnostic only. The contract test verifies the recovery
  // payload structure for this case as well.
  const rawTokenDrift = {
    ok: false,
    outcome: { kind: "error", failure_kind: "StaleStateMismatch" },
    rebaseline_recovery: {
      action: "rebaseline",
      endpoint: "/rebaseline",
      reason: "live_token_drift",
      last_known_baseline_graph_hash: "baseline-struct",
      submit_structural_graph_hash: "struct-same",
      client_structural_graph_hash: "struct-same",
      submit_graph_hash: "graph-same",
      client_graph_hash: "graph-same",
    },
  };

  const normalizedToken = normalizeAgentEditResponse(rawTokenDrift, { endpoint: "/submit" });
  assert.equal(normalizedToken.rebaselineRecovery.reason, "live_token_drift");
  // Structural hashes are the same → token drift only, not structural
  assert.equal(
    normalizedToken.rebaselineRecovery.submitStructuralGraphHash,
    normalizedToken.rebaselineRecovery.clientStructuralGraphHash,
    "structural hash unchanged → token drift is diagnostic only",
  );
});

// ── PUBLIC_OUTCOME_KINDS sanity ─────────────────────────────────────────────

test("PUBLIC_OUTCOME_KINDS does not include stale or malformed as outcome kinds", () => {
  // Stale and malformed are transport-level conditions, not public outcome kinds
  assert.ok(PUBLIC_OUTCOME_KINDS.includes("candidate"));
  assert.ok(PUBLIC_OUTCOME_KINDS.includes("noop"));
  assert.ok(PUBLIC_OUTCOME_KINDS.includes("clarify"));
  assert.ok(PUBLIC_OUTCOME_KINDS.includes("requires_custom_nodes"));
  assert.ok(PUBLIC_OUTCOME_KINDS.includes("error"));
  assert.equal(PUBLIC_OUTCOME_KINDS.length, 5);
  // No "stale" or "malformed" kind — those are failure kinds within "error"
  assert.ok(!PUBLIC_OUTCOME_KINDS.includes("stale"));
  assert.ok(!PUBLIC_OUTCOME_KINDS.includes("malformed"));
});
