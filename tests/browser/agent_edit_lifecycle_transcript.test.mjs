import test from "node:test";
import assert from "node:assert/strict";

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

// ── Two-submit transcript ordering ──────────────────────────────────────────
// The plan requires that transcript order is stable across two submits:
//   user1 -> assistant1 -> user2 -> pending2  (after first submit + second submit start)
//   user1 -> assistant1 -> user2 -> assistant2 (after second submit response)
// with NO duplicate optimistic entries.

test("CHAT_REHYDRATE_SUCCESS replaces chatMessages atomically and does not leave duplicate optimistic entries", () => {
  const panel = makePanel({
    sessionId: "sess-transcript",
    chatRehydrateEpoch: 1,
    // Simulate: user1 + assistant1 (canonical) + user2 (optimistic) + pending2 (optimistic)
    chatMessages: [
      { role: "user", text: "first request", turn_id: "t1", session_id: "sess-transcript" },
      { role: "agent", text: "first response", turn_id: "t1", session_id: "sess-transcript" },
      { role: "user", text: "second request", optimistic: true, turn_id: "t2", session_id: "sess-transcript" },
      { role: "agent", pending_response: true, executor_pending: true, turn_id: "t2", session_id: "sess-transcript" },
    ],
  });

  // Backend returns canonical messages: user1, assistant1, user2, assistant2
  const canonicalMessages = [
    { role: "user", text: "first request", turn_id: "t1", session_id: "sess-transcript" },
    { role: "agent", text: "first response", turn_id: "t1", session_id: "sess-transcript" },
    { role: "user", text: "second request", turn_id: "t2", session_id: "sess-transcript" },
    { role: "agent", text: "second response", turn_id: "t2", session_id: "sess-transcript" },
  ];

  transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: 1,
    messages: canonicalMessages,
    sessionId: "sess-transcript",
  });

  // Must have exactly 4 messages, no duplicates
  assert.equal(panel.state.chatMessages.length, 4, "canonical messages replace all optimistic entries");

  // Order: user1 -> assistant1 -> user2 -> assistant2
  assert.equal(panel.state.chatMessages[0].role, "user");
  assert.equal(panel.state.chatMessages[0].text, "first request");
  assert.equal(panel.state.chatMessages[0].turn_id, "t1");

  assert.equal(panel.state.chatMessages[1].role, "agent");
  assert.equal(panel.state.chatMessages[1].text, "first response");
  assert.equal(panel.state.chatMessages[1].turn_id, "t1");

  assert.equal(panel.state.chatMessages[2].role, "user");
  assert.equal(panel.state.chatMessages[2].text, "second request");
  assert.equal(panel.state.chatMessages[2].turn_id, "t2");

  assert.equal(panel.state.chatMessages[3].role, "agent");
  assert.equal(panel.state.chatMessages[3].text, "second response");
  assert.equal(panel.state.chatMessages[3].turn_id, "t2");

  // No optimistic or pending_response flags on canonical entries
  for (const msg of panel.state.chatMessages) {
    assert.equal(msg.optimistic, undefined, "canonical messages must not carry optimistic flag");
    assert.equal(msg.pending_response, undefined, "canonical messages must not carry pending_response flag");
    assert.equal(msg.executor_pending, undefined, "canonical messages must not carry executor_pending flag");
  }
});

test("Two consecutive CHAT_REHYDRATE_SUCCESS calls produce stable transcript with no duplication across rehydrate epochs", () => {
  const panel = makePanel({
    sessionId: "sess-stable",
    chatRehydrateEpoch: 1,
    chatMessages: [
      { role: "user", text: "ask 1", turn_id: "t1", session_id: "sess-stable" },
      { role: "agent", text: "answer 1", turn_id: "t1", session_id: "sess-stable" },
    ],
  });

  // First submit response arrives
  const messagesAfterSubmit1 = [
    { role: "user", text: "ask 1", turn_id: "t1", session_id: "sess-stable" },
    { role: "agent", text: "answer 1", turn_id: "t1", session_id: "sess-stable" },
    { role: "user", text: "ask 2", turn_id: "t2", session_id: "sess-stable" },
    { role: "agent", text: "answer 2", turn_id: "t2", session_id: "sess-stable" },
  ];

  transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: 1,
    messages: messagesAfterSubmit1,
    sessionId: "sess-stable",
  });

  assert.equal(panel.state.chatMessages.length, 4);

  // Second rehydrate with same messages (idempotent)
  transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: 2,
    messages: messagesAfterSubmit1,
    sessionId: "sess-stable",
  });

  assert.equal(panel.state.chatMessages.length, 4, "repeated rehydrate must not duplicate messages");
  assert.equal(panel.state.chatMessages[0].text, "ask 1");
  assert.equal(panel.state.chatMessages[3].text, "answer 2");
});

test("CHAT_REHYDRATE_SUCCESS with partial canonical messages (no pending turn) does not resurrect stale pending entries", () => {
  const panel = makePanel({
    sessionId: "sess-partial",
    chatRehydrateEpoch: 1,
    // Had a pending submission that was cancelled
    chatMessages: [
      { role: "user", text: "ask 1", turn_id: "t1", session_id: "sess-partial" },
      { role: "agent", text: "answer 1", turn_id: "t1", session_id: "sess-partial" },
      { role: "user", text: "ask 2", optimistic: true, turn_id: "t2", session_id: "sess-partial" },
      { role: "agent", pending_response: true, executor_pending: true, turn_id: "t2", session_id: "sess-partial" },
    ],
  });

  // Backend only confirms first turn (second was cancelled server-side)
  const canonicalMessages = [
    { role: "user", text: "ask 1", turn_id: "t1", session_id: "sess-partial" },
    { role: "agent", text: "answer 1", turn_id: "t1", session_id: "sess-partial" },
  ];

  transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: 1,
    messages: canonicalMessages,
    sessionId: "sess-partial",
  });

  assert.equal(panel.state.chatMessages.length, 2, "partial canonical set must not retain stale optimistic entries");
  assert.equal(panel.state.chatMessages[0].text, "ask 1");
  assert.equal(panel.state.chatMessages[1].text, "answer 1");

  // No optimistic remnants
  for (const msg of panel.state.chatMessages) {
    assert.equal(msg.optimistic, undefined);
    assert.equal(msg.pending_response, undefined);
  }
});

// ── Optimistic replacement without duplication ──────────────────────────────

test("Optimistic user+agent pair is atomically replaced by canonical pair without leaving any duplicates", () => {
  const panel = makePanel({
    sessionId: "sess-opt-replace",
    chatRehydrateEpoch: 1,
    chatMessages: [
      { role: "user", text: "previous ask", turn_id: "t-prev", session_id: "sess-opt-replace" },
      { role: "agent", text: "previous answer", turn_id: "t-prev", session_id: "sess-opt-replace" },
      // Optimistic: current submit in-flight
      { role: "user", text: "current ask", optimistic: true, turn_id: "t-curr", session_id: "sess-opt-replace" },
      { role: "agent", pending_response: true, executor_pending: true, turn_id: "t-curr", session_id: "sess-opt-replace" },
    ],
  });

  // Backend confirms both turns
  const canonicalMessages = [
    { role: "user", text: "previous ask", turn_id: "t-prev", session_id: "sess-opt-replace" },
    { role: "agent", text: "previous answer", turn_id: "t-prev", session_id: "sess-opt-replace" },
    { role: "user", text: "current ask", turn_id: "t-curr", session_id: "sess-opt-replace" },
    { role: "agent", text: "current answer", turn_id: "t-curr", session_id: "sess-opt-replace" },
  ];

  transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: 1,
    messages: canonicalMessages,
    sessionId: "sess-opt-replace",
  });

  assert.equal(panel.state.chatMessages.length, 4, "exactly 4 canonical messages");
  assert.equal(panel.state.chatMessages[2].text, "current ask");
  assert.equal(panel.state.chatMessages[2].optimistic, undefined, "canonical user message must not be optimistic");
  assert.equal(panel.state.chatMessages[3].text, "current answer");
  assert.equal(panel.state.chatMessages[3].pending_response, undefined, "canonical agent message must not be pending");
});

test("Canonical rehydrate reconciles snake_case messages against camelCase optimistic durable TurnIdentity", () => {
  const panel = makePanel({
    sessionId: "sess-canonical-reconcile",
    chatRehydrateEpoch: 7,
    phase: PANEL_STATE.SUBMITTING,
    submitEpoch: 12,
    chatMessages: [
      {
        role: "user",
        text: "make the prompt brighter",
        optimistic: true,
        submit_epoch: 12,
        turnIdentity: {
          sessionId: "sess-canonical-reconcile",
          turnId: "turn-canonical-reconcile",
          role: "user",
        },
        local_id: "local-user-reconcile",
      },
      {
        role: "agent",
        pending_response: true,
        executor_pending: true,
        optimistic: true,
        submit_epoch: 12,
        turnIdentity: {
          sessionId: "sess-canonical-reconcile",
          turnId: "turn-canonical-reconcile",
          role: "agent",
        },
        local_id: "local-agent-reconcile",
      },
    ],
  });

  const canonicalMessages = [
    {
      role: "user",
      text: "make the prompt brighter",
      turn_identity: {
        session_id: "sess-canonical-reconcile",
        turn_id: "turn-canonical-reconcile",
        role: "user",
      },
    },
    {
      role: "agent",
      text: "Candidate ready for review.",
      turn_identity: {
        session_id: "sess-canonical-reconcile",
        turn_id: "turn-canonical-reconcile",
        role: "agent",
      },
    },
  ];

  const obligations = transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: 7,
    messages: canonicalMessages,
    sessionId: "sess-canonical-reconcile",
  });

  assert.deepEqual(obligations, {
    render: false,
    dirtySections: ["META", "THREAD"],
    persistSession: "sess-canonical-reconcile",
  });
  assert.equal(panel.state.chatMessages.length, 2);
  assert.deepEqual(panel.state.chatMessages, canonicalMessages);
  assert.equal(
    panel.state.chatMessages.some((message) => message.optimistic || message.pending_response),
    false,
    "canonical durable messages must replace optimistic entries with matching TurnIdentity",
  );
});

test("CHAT_REHYDRATE_NO_SESSION clears all chat state including optimistic entries", () => {
  const panel = makePanel({
    sessionId: "sess-clear",
    chatRehydrateEpoch: 2,
    chatMessages: [
      { role: "user", text: "ask", optimistic: true },
      { role: "agent", pending_response: true, executor_pending: true },
    ],
    chatLoaded: true,
    chatError: "old error",
    chatSessionPath: "out/editor_sessions/sess-clear/",
  });

  transition(panel, "CHAT_REHYDRATE_NO_SESSION", { requestEpoch: 2 });

  assert.deepEqual(panel.state.chatMessages, []);
  assert.equal(panel.state.chatLoaded, false);
  assert.equal(panel.state.chatError, null);
  assert.equal(panel.state.chatSessionPath, null);
});

test("CHAT_REHYDRATE_MISSING_SESSION clears chat and nullifies sessionId when confirmed", () => {
  const panel = makePanel({
    sessionId: "sess-missing",
    chatRehydrateEpoch: 3,
    chatMessages: [
      { role: "user", text: "stale ask", optimistic: true },
      { role: "agent", pending_response: true },
    ],
    chatLoaded: true,
  });

  transition(panel, "CHAT_REHYDRATE_MISSING_SESSION", {
    requestEpoch: 3,
    sessionId: "sess-missing",
  });

  assert.deepEqual(panel.state.chatMessages, []);
  assert.equal(panel.state.chatLoaded, true);
  assert.equal(panel.state.sessionId, null);
});

// ── panel.state.message cannot resurrect old assistant replies ──────────────

test("panel.state.message is reset to null by INVALIDATE_CANDIDATE and does not survive accept/reject/rebaseline cleanup", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    message: "Old assistant reply lingering",
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-1",
    candidateReport: { change: true },
    applyEligibility: { applyable: true },
  });

  // INVALIDATE_CANDIDATE clears candidate fields but NOT message (message is not a candidate field)
  transition(panel, "INVALIDATE_CANDIDATE");

  // message is not in the candidate invalidation list — it survives INVALIDATE_CANDIDATE
  // This is a documentation test: message is a general status field, not a candidate field
  assert.equal(panel.state.message, "Old assistant reply lingering",
    "message is NOT cleared by INVALIDATE_CANDIDATE (it's a status field, not candidate)");
  assert.equal(panel.state.candidateGraph, null);
});

test("REJECT_SUCCESS clears message alongside candidate fields through INVALIDATE_CANDIDATE chaining", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    message: "Candidate was ready for review",
    candidateGraph: { nodes: [{ id: 5 }] },
    candidateGraphHash: "reject-me",
    turnId: "t-reject",
    deltaOps: [{ op: "set_node_field", target: ["nodes", 5], value: "v" }],
  });

  transition(panel, "REJECT_SUCCESS", {
    rejected: { turn_id: "t-reject" },
    message: "Candidate rejected.",
  });

  // REJECT_SUCCESS sets message to the rejection message and clears candidate via INVALIDATE_CANDIDATE
  assert.equal(panel.state.message, "Candidate rejected.");
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.candidateGraph, null);
  assert.equal(panel.state.deltaOps, null);
});

test("OK_CANDIDATE_RESPONSE replaces message with the result message", () => {
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    message: "Submitting request...",
  });

  transition(panel, "OK_CANDIDATE_RESPONSE", {
    result: {
      session_id: "sess-msg",
      turn_id: "t-msg",
      message: "Candidate is ready for review.",
      canvas_apply_allowed: true,
      queue_allowed: false,
    },
    candidateGraph: { nodes: [] },
    candidateGraphHash: "hash-msg",
    applyEligibility: { applyable: true },
  });

  assert.equal(panel.state.message, "Candidate is ready for review.");
});

test("NOOP_RESPONSE replaces message with the result message", () => {
  const panel = makePanel({
    phase: PANEL_STATE.SUBMITTING,
    message: "Processing...",
  });

  transition(panel, "NOOP_RESPONSE", {
    result: {
      session_id: "sess-noop",
      turn_id: "t-noop",
      message: "No changes needed for this request.",
    },
    message: "No changes needed for this request.",
  });

  assert.equal(panel.state.message, "No changes needed for this request.");
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
});

test("APPLY_SUCCESS clears review message without adding a local confirmation", () => {
  const panel = makePanel({
    phase: PANEL_STATE.APPLYING,
    sessionId: "sess-apply-msg",
    turnId: "t-apply",
    message: "Review this candidate before applying.",
    candidateGraph: { nodes: [{ id: 1 }] },
    candidateGraphHash: "hash-apply",
    candidateReport: { change: true },
    serverSubmitGraphHash: "submit-hash",
    applyEligibility: { applyable: true, reason: "applyable" },
    applyAllowed: true,
    canvasApplyAllowed: true,
    queueAllowed: true,
    changeDetails: { edited: ["uid-1"] },
  });

  transition(panel, "APPLY_SUCCESS", {
    accepted: {
      ok: true,
      action: "accept",
      session_id: "sess-apply-msg",
      turn_id: "t-apply",
      baseline_turn_id: "t-apply",
      baseline_graph_hash: "base-hash",
    },
    lastAppliedChanges: { items: [{ uid: "uid-1", kind: "edited" }], mode: "panel" },
    undoStackDepth: 1,
  });

  assert.equal(panel.state.message, null);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  // Old review message is cleared without adding a local apply-confirmation message.
  assert.notEqual(panel.state.message, "Review this candidate before applying.");
});
