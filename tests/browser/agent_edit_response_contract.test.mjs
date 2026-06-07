import test from "node:test";
import assert from "node:assert/strict";

import {
  PUBLIC_OUTCOME_KINDS,
  normalizeAgentEditResponse,
  readCandidate,
  readCandidateGraph,
  readEligibility,
  readLatestCandidate,
  readOutcome,
  readRebaselineRecovery,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract.js";

test("PUBLIC_OUTCOME_KINDS stays the closed public contract", () => {
  assert.deepEqual(PUBLIC_OUTCOME_KINDS, [
    "candidate",
    "noop",
    "clarify",
    "error",
  ]);
});

test("normalizeAgentEditResponse preserves public candidate payloads and exposes camelCase readers", () => {
  const raw = {
    ok: true,
    message: "Candidate ready.",
    outcome: { kind: "candidate", changes: [{ uid: "ksampler", field_path: "steps" }] },
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
    },
    candidate_graph_hash: "candidate-hash",
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      message: "Ready to apply.",
      warnings: [],
    },
    latest_candidate: {
      ok: true,
      outcome: { kind: "candidate", changes: [] },
      graph: { nodes: [{ id: 2, type: "SaveImage" }], links: [] },
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.equal(normalized.raw, raw);
  assert.equal(normalized.outcome.kind, "candidate");
  assert.deepEqual(normalized.candidateGraph, raw.candidate.graph);
  assert.equal(normalized.candidateGraphHash, "candidate-hash");
  assert.deepEqual(normalized.eligibility, raw.apply_eligibility);
  assert.equal(normalized.latestCandidate?.outcome.kind, "candidate");
  assert.deepEqual(readOutcome(raw, { endpoint: "submit" }), normalized.outcome);
  assert.deepEqual(readCandidateGraph(raw, { endpoint: "submit" }), raw.candidate.graph);
  assert.deepEqual(readEligibility(raw, { endpoint: "submit" }), raw.apply_eligibility);
  assert.equal(readLatestCandidate(raw, { endpoint: "submit" })?.outcome.kind, "candidate");
});

test("normalizeAgentEditResponse infers legacy candidate outcome from direct graph payloads", () => {
  const raw = {
    ok: true,
    message: "Applied the requested edit.",
    graph: { nodes: [{ id: 5, type: "PreviewImage" }], links: [] },
    apply_allowed: true,
    canvas_apply_allowed: true,
    queue_allowed: true,
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.equal(normalized.outcome.kind, "candidate");
  assert.deepEqual(normalized.candidateGraph, raw.graph);
  assert.deepEqual(normalized.candidate, { graph: raw.graph });
  assert.equal(normalized.eligibility?.reason, "applyable");
});

test("normalizeAgentEditResponse infers legacy noop outcome and suppresses candidate restoration", () => {
  const raw = {
    ok: true,
    message: "No edits needed.",
    graph: { nodes: [{ id: 7, type: "SaveImage" }], links: [] },
    graph_unchanged: true,
    apply_allowed: false,
    canvas_apply_allowed: false,
    queue_allowed: false,
    apply_eligibility: {
      applyable: false,
      reason: "no_candidate",
      message: "No candidate is available to apply.",
      warnings: [],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit/chat" });

  assert.deepEqual(normalized.outcome, {
    kind: "noop",
    reason: "No edits needed.",
  });
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
});

test("normalizeAgentEditResponse infers legacy clarify outcome and preserves clarification metadata", () => {
  const raw = {
    ok: true,
    message: "Need clarification.",
    clarification_required: true,
    clarification_message: "Should I move the save node before the preview node?",
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.deepEqual(normalized.outcome, {
    kind: "clarify",
    question: "Should I move the save node before the preview node?",
    clarification: {
      message: "Should I move the save node before the preview node?",
    },
  });
});

test("normalizeAgentEditResponse infers legacy error outcomes and normalizes nested stale recovery", () => {
  const raw = {
    ok: false,
    message: "Stage accept blocked the agent edit.",
    stage: "accept",
    failure_kind: "StaleStateMismatch",
    retryable: false,
    next_action: "resubmit from the current canvas",
    graph_unchanged: true,
    agent_failure_context: {
      issues: [
        {
          code: "stale_state_mismatch",
          rebaseline_recovery: {
            action: "rebaseline",
            endpoint: "/vibecomfy/agent-edit/rebaseline",
            reason: "stale_state_recovery",
            last_known_baseline_graph_hash: "baseline-before",
          },
        },
      ],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit/accept" });

  assert.equal(normalized.outcome.kind, "error");
  assert.equal(normalized.outcome.failureKind, "StaleStateMismatch");
  assert.equal(normalized.outcome.stage, "accept");
  assert.deepEqual(normalized.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    lastKnownBaselineGraphHash: "baseline-before",
  });
  assert.deepEqual(readRebaselineRecovery(raw, { endpoint: "accept" }), normalized.rebaselineRecovery);
});

test("normalizeAgentEditResponse maps internal edit outcomes onto public candidate", () => {
  const normalized = normalizeAgentEditResponse({
    ok: true,
    outcome: {
      kind: "edit",
      changes: [{ uid: "ksampler", field_path: "steps", old: 20, new: 26 }],
    },
    graph: { nodes: [{ id: 9, type: "KSampler" }], links: [] },
  });

  assert.deepEqual(normalized.outcome, {
    kind: "candidate",
    changes: [{ uid: "ksampler", field_path: "steps", old: 20, new: 26 }],
  });
});

test("normalizeAgentEditResponse maps internal edit+clarify outcomes to candidate while preserving clarification", () => {
  const normalized = normalizeAgentEditResponse({
    ok: true,
    outcome: {
      kind: "edit+clarify",
      question: "Keep the previous seed?",
      changes: [],
    },
    graph: { nodes: [{ id: 10, type: "KSamplerAdvanced" }], links: [] },
  });

  assert.deepEqual(normalized.outcome, {
    kind: "candidate",
    changes: [],
    question: "Keep the previous seed?",
    clarification: {
      message: "Keep the previous seed?",
    },
  });
});

test("normalizeAgentEditResponse rejects missing outcomes when legacy inference is disabled", () => {
  assert.throws(
    () => normalizeAgentEditResponse(
      {
        ok: true,
        graph: { nodes: [{ id: 12, type: "SaveImage" }], links: [] },
      },
      { allowLegacy: false, endpoint: "/strict" },
    ),
    /missing outcome/i,
  );
});

// ── snake_case recovery normalization (explicit field mapping) ──────────
test("normalizeAgentEditResponse normalizes snake_case recovery fields to camelCase", () => {
  const raw = {
    ok: false,
    message: "Stale state mismatch on submit.",
    outcome: { kind: "error", failure_kind: "StaleStateMismatch" },
    rebaseline_recovery: {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "stale_state_recovery",
      last_known_baseline_graph_hash: "abc123",
      submit_graph_hash: "def456",
      submit_structural_graph_hash: "struct789",
      client_graph_hash: "client111",
      client_structural_graph_hash: "client-struct222",
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });

  assert.equal(normalized.outcome.kind, "error");
  assert.deepEqual(normalized.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    lastKnownBaselineGraphHash: "abc123",
    submitGraphHash: "def456",
    submitStructuralGraphHash: "struct789",
    clientGraphHash: "client111",
    clientStructuralGraphHash: "client-struct222",
  });
  // Verify raw payload is preserved unmodified
  assert.equal(normalized.raw, raw);
  assert.equal(normalized.raw.rebaseline_recovery.last_known_baseline_graph_hash, "abc123");
});

// ── recovery extraction from all supported positions ───────────────────
test("extractRebaselineRecovery finds recovery at top-level camelCase", () => {
  const raw = {
    ok: false,
    outcome: { kind: "error", failure_kind: "StaleStateMismatch" },
    rebaselineRecovery: {
      action: "rebaseline",
      endpoint: "/rebaseline",
      reason: "stale",
      lastKnownBaselineGraphHash: "top-camel",
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/accept" });
  assert.deepEqual(normalized.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/rebaseline",
    reason: "stale",
    lastKnownBaselineGraphHash: "top-camel",
  });
});

test("extractRebaselineRecovery finds recovery inside outcome.rebaseline_recovery", () => {
  const raw = {
    ok: false,
    outcome: {
      kind: "error",
      failure_kind: "StaleStateMismatch",
      rebaseline_recovery: {
        action: "rebaseline",
        endpoint: "/rebaseline",
        reason: "stale_outcome",
        last_known_baseline_graph_hash: "outcome-level",
      },
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.rebaselineRecovery.lastKnownBaselineGraphHash, "outcome-level");
  assert.equal(normalized.rebaselineRecovery.reason, "stale_outcome");
});

test("extractRebaselineRecovery finds recovery inside agent_failure_context.issues", () => {
  const raw = {
    ok: false,
    outcome: { kind: "error", failure_kind: "StaleStateMismatch" },
    agent_failure_context: {
      explanation: "Scoped accept verification failed.",
      issues: [
        {
          code: "scoped_conflict",
          detail: "Node 2 prompt drifted after submit.",
          rebaseline_recovery: {
            action: "rebaseline",
            endpoint: "/rebaseline",
            reason: "scoped_accept_conflict",
            submit_graph_hash: "submit-hash",
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
    submitGraphHash: "submit-hash",
  });
});

test("extractRebaselineRecovery finds recovery inside debug.failure.agent_failure_context", () => {
  const raw = {
    ok: false,
    outcome: { kind: "error", failure_kind: "StaleStateMismatch" },
    debug: {
      failure: {
        agent_failure_context: {
          issues: [
            {
              code: "stale_state_mismatch",
              rebaseline_recovery: {
                action: "rebaseline",
                endpoint: "/rebaseline",
                reason: "debug_stale",
                last_known_baseline_graph_hash: "debug-hash",
              },
            },
          ],
        },
      },
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/accept" });
  assert.deepEqual(normalized.rebaselineRecovery, {
    action: "rebaseline",
    endpoint: "/rebaseline",
    reason: "debug_stale",
    lastKnownBaselineGraphHash: "debug-hash",
  });
});

test("extractRebaselineRecovery prefers top-level recovery over nested sources", () => {
  const raw = {
    ok: false,
    outcome: { kind: "error" },
    rebaselineRecovery: {
      action: "rebaseline",
      endpoint: "/top",
      reason: "top_priority",
      lastKnownBaselineGraphHash: "top-hash",
    },
    agent_failure_context: {
      issues: [
        {
          code: "stale",
          rebaseline_recovery: {
            action: "rebaseline",
            endpoint: "/nested",
            reason: "nested_ignored",
            last_known_baseline_graph_hash: "nested-hash",
          },
        },
      ],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.rebaselineRecovery.lastKnownBaselineGraphHash, "top-hash");
});

// ── readCandidate cached-reader exposure ───────────────────────────────
test("readCandidate returns the normalized candidate envelope", () => {
  const raw = {
    ok: true,
    candidate: {
      graph: { nodes: [{ id: 20, type: "PreviewImage" }], links: [] },
      metadata: { created: "2025-01-01" },
    },
    outcome: { kind: "candidate", changes: [] },
  };

  const candidate = readCandidate(raw, { endpoint: "/submit" });
  assert.ok(candidate);
  assert.deepEqual(candidate.graph, raw.candidate.graph);
  assert.equal(candidate.metadata.created, "2025-01-01");

  // Re-read returns a structurally equal (though not reference-equal) envelope
  const second = readCandidate(raw, { endpoint: "/submit" });
  assert.deepEqual(candidate, second);
});

// ── public explicit-outcome kinds (no legacy inference) ────────────────
test("normalizeAgentEditResponse handles explicit public noop outcome", () => {
  const raw = {
    ok: true,
    message: "No changes requested.",
    outcome: { kind: "noop", reason: "graph unchanged" },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/chat" });
  assert.equal(normalized.outcome.kind, "noop");
  assert.equal(normalized.outcome.reason, "graph unchanged");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
});

test("normalizeAgentEditResponse handles explicit public clarify outcome with question", () => {
  const raw = {
    ok: true,
    outcome: {
      kind: "clarify",
      question: "Should I replace the sampler?",
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.outcome.kind, "clarify");
  assert.equal(normalized.outcome.question, "Should I replace the sampler?");
  assert.deepEqual(normalized.outcome.clarification, {
    message: "Should I replace the sampler?",
  });
});

test("normalizeAgentEditResponse handles explicit public error outcome with embedded failure hints", () => {
  const raw = {
    ok: false,
    stage: "submit",
    outcome: {
      kind: "error",
      failureKind: "BadRequest",
      stage: "submit",
      retryable: false,
      nextAction: "Check your prompt.",
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.outcome.kind, "error");
  assert.equal(normalized.outcome.failureKind, "BadRequest");
  assert.equal(normalized.outcome.stage, "submit");
  assert.equal(normalized.outcome.retryable, false);
  assert.equal(normalized.outcome.nextAction, "Check your prompt.");
});

// ── message normalization through the contract ─────────────────────────
test("normalizeAgentEditResponse normalizes embedded messages array", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate", changes: [] },
    candidate: {
      graph: { nodes: [{ id: 30, type: "KSampler" }], links: [] },
    },
    messages: [
      {
        role: "user",
        text: "Add a preview node.",
        turn_id: "turn-1",
        session_id: "sess-abc",
        entry_type: "prompt",
        timestamp: "2025-06-01T12:00:00Z",
      },
      {
        role: "agent",
        text: "Added PreviewImage node.",
        turn_id: "turn-1",
        session_id: "sess-abc",
        entry_type: "response",
        timestamp: "2025-06-01T12:00:01Z",
        response: {
          ok: true,
          outcome: { kind: "candidate", changes: [{ uid: "preview", field_path: "type" }] },
          candidate: { graph: { nodes: [{ id: 31, type: "PreviewImage" }], links: [] } },
        },
      },
      {
        role: "agent",
        text: "No changes needed.",
        turn_id: "turn-2",
        session_id: "sess-abc",
        entry_type: "response",
        timestamp: "2025-06-01T12:01:00Z",
        outcome: { kind: "noop", reason: "graph unchanged" },
      },
    ],
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/chat" });
  assert.ok(Array.isArray(normalized.messages));
  assert.equal(normalized.messages.length, 3);

  const [userMsg, agentMsg, noopMsg] = normalized.messages;
  assert.equal(userMsg.role, "user");
  assert.equal(userMsg.text, "Add a preview node.");
  assert.equal(userMsg.turnId, "turn-1");
  assert.equal(userMsg.outcome, null);

  assert.equal(agentMsg.role, "agent");
  assert.equal(agentMsg.outcome.kind, "candidate");
  assert.equal(agentMsg.response.outcome.kind, "candidate");
  assert.equal(agentMsg.response.candidateGraph.nodes[0].type, "PreviewImage");

  assert.equal(noopMsg.role, "agent");
  assert.equal(noopMsg.outcome.kind, "noop");
  assert.equal(noopMsg.outcome.reason, "graph unchanged");
});

// ── idempotent double-normalization ────────────────────────────────────
test("normalizeAgentEditResponse is idempotent (double-normalize returns same result)", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate", changes: [{ uid: "n1", field_path: "cfg" }] },
    candidate: { graph: { nodes: [{ id: 40, type: "CLIPTextEncode" }], links: [] } },
    apply_eligibility: { applyable: true, reason: "applyable", message: "Ready.", warnings: [] },
  };

  const first = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  const second = normalizeAgentEditResponse(first, { endpoint: "/submit" });

  // Second pass returns the marker-bearing object unchanged
  assert.equal(first, second);
  assert.equal(first.outcome.kind, "candidate");
  assert.equal(second.outcome.kind, "candidate");
});
