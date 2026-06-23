import test from "node:test";
import assert from "node:assert/strict";

import {
  PUBLIC_OUTCOME_KINDS,
  adaptLegacyAgentEditResponse,
  normalizeAgentEditResponse,
  normalizeCanonicalAgentEditResponse,
  readApplyCandidate,
  readCandidate,
  readCandidateGraph,
  readEligibility,
  readFieldChanges,
  readLatestCandidate,
  readOutcome,
  readRebaselineRecovery,
  readStageSnapshot,
  readTurnIdentity,
  readUserFailure,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract.js";

const FORBIDDEN_NORMAL_PATH_KEYS = new Set([
  "executor_pending",
  "apply_allowed",
  "canvas_apply_allowed",
  "applyAllowed",
  "canvasApplyAllowed",
]);

function assertCanonicalNormalPathHasNoLegacyAliases(value, path = "$") {
  if (!value || typeof value !== "object") {
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => {
      assertCanonicalNormalPathHasNoLegacyAliases(entry, `${path}[${index}]`);
    });
    return;
  }

  for (const [key, entry] of Object.entries(value)) {
    const keyPath = `${path}.${key}`;
    assert.equal(
      FORBIDDEN_NORMAL_PATH_KEYS.has(key),
      false,
      `canonical normal-path payload must not carry legacy alias ${keyPath}`,
    );
    assert.equal(
      key === "field_changes" && !/\.change_details\.batch_turns\[\d+\]\.field_changes$/.test(keyPath),
      false,
      `canonical normal-path payload must not carry old field-change dictionary ${keyPath}`,
    );
    assertCanonicalNormalPathHasNoLegacyAliases(entry, keyPath);
  }
}

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

test("frontend canonical selectors project stable candidate, identity, stage, and field-change views", () => {
  const raw = {
    ok: true,
    message: "Candidate ready.",
    outcome: {
      kind: "candidate",
      changes: [{ uid: "ksampler", field_path: "widgets.steps", old: 20, new: 28 }],
    },
    candidate: {
      state: "candidate",
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
      graph_hash: "graph-hash",
      structural_graph_hash: "struct-hash",
      baseline_graph_hash: "baseline-hash",
      submit_graph_hash: "submit-hash",
      submit_structural_graph_hash: "submit-struct-hash",
      turn_identity: {
        session_id: "sess-1",
        turn_id: "turn-1",
        baseline_turn_id: "turn-0",
        idempotency_key: "idem-1",
      },
    },
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      message: "Ready to apply.",
      warnings: [],
    },
    change_details: {
      batch_turns: [
        {
          turn_number: 2,
          field_changes: [{ uid: "save", field_path: "filename_prefix", old: "old", new: "new" }],
        },
      ],
    },
    debug: {
      stage_snapshots: [
        { stage: "lower", ok: true, blocking: false, duration_ms: 12, gates: { lower_ok: true } },
        { stage: "queue_validate", ok: true, blocking: false, duration_ms: 8 },
      ],
    },
  };

  const candidate = readApplyCandidate(raw, { allowLegacy: false, endpoint: "/submit" });
  assert.deepEqual(candidate, {
    state: "candidate",
    graph: raw.candidate.graph,
    graphHash: "graph-hash",
    structuralGraphHash: "struct-hash",
    baselineGraphHash: "baseline-hash",
    submitGraphHash: "submit-hash",
    submitStructuralGraphHash: "submit-struct-hash",
    eligibility: raw.apply_eligibility,
    applyable: true,
    turnIdentity: {
      sessionId: "sess-1",
      turnId: "turn-1",
      baselineTurnId: "turn-0",
      idempotencyKey: "idem-1",
    },
  });
  assert.deepEqual(readTurnIdentity(raw, { allowLegacy: false }), candidate.turnIdentity);
  assert.deepEqual(readStageSnapshot(raw, { allowLegacy: false }), {
    stage: "queue_validate",
    ok: true,
    blocking: false,
    durationMs: 8,
  });
  assert.deepEqual(readStageSnapshot(raw, { allowLegacy: false, stage: "lower" }), {
    stage: "lower",
    ok: true,
    blocking: false,
    durationMs: 12,
    gates: { lower_ok: true },
  });
  assert.deepEqual(readFieldChanges(raw, { allowLegacy: false }), {
    directChanges: [],
    outcomeChanges: [{ uid: "ksampler", fieldPath: "widgets.steps", old: 20, new: 28 }],
    legacyChanges: [],
    batchTurnChanges: [
      {
        turnNumber: 2,
        changes: [{ uid: "save", fieldPath: "filename_prefix", old: "old", new: "new" }],
      },
    ],
    all: [
      { uid: "ksampler", fieldPath: "widgets.steps", old: 20, new: 28 },
      { uid: "save", fieldPath: "filename_prefix", old: "old", new: "new" },
    ],
  });
});

test("allowLegacy=false accepts canonical-only persisted candidate fixtures", () => {
  const canonicalPersisted = {
    ok: true,
    message: "Canonical candidate restored.",
    outcome: {
      kind: "candidate",
      changes: [{ uid: "save", field_path: "inputs.filename_prefix", old: "old", new: "new" }],
    },
    candidate: {
      state: "candidate",
      graph: { nodes: [{ id: 7, type: "SaveImage" }], links: [] },
      graph_hash: "canonical-candidate-hash",
      turn_identity: {
        session_id: "sess-canonical-persisted",
        turn_id: "0012",
        baseline_turn_id: "0011",
        idempotency_key: "idem-0012",
      },
    },
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      message: "Ready to apply.",
      warnings: [],
    },
    change_details: {
      batch_turns: [
        {
          turn_number: 0,
          field_changes: [
            { uid: "save", field_path: "inputs.filename_prefix", old: "old", new: "new" },
          ],
        },
      ],
    },
    debug: {
      stage_snapshots: [
        { stage: "queue_validate", ok: true, blocking: false, duration_ms: 3 },
      ],
    },
  };

  assertCanonicalNormalPathHasNoLegacyAliases(canonicalPersisted);

  const normalized = normalizeCanonicalAgentEditResponse(canonicalPersisted, {
    endpoint: "/fixture/canonical-persisted",
  });
  const candidate = readApplyCandidate(normalized, { allowLegacy: false });

  assert.equal(normalized.outcome.kind, "candidate");
  assert.equal(candidate.graphHash, "canonical-candidate-hash");
  assert.deepEqual(candidate.turnIdentity, {
    sessionId: "sess-canonical-persisted",
    turnId: "0012",
    baselineTurnId: "0011",
    idempotencyKey: "idem-0012",
  });
  assert.deepEqual(readStageSnapshot(normalized, { allowLegacy: false }), {
    stage: "queue_validate",
    ok: true,
    blocking: false,
    durationMs: 3,
  });
  assert.deepEqual(readFieldChanges(normalized, { allowLegacy: false }).legacyChanges, []);
  assert.deepEqual(readFieldChanges(normalized, { allowLegacy: false }).all, [
    { uid: "save", fieldPath: "inputs.filename_prefix", old: "old", new: "new" },
    { uid: "save", fieldPath: "inputs.filename_prefix", old: "old", new: "new" },
  ]);
});

test("old persisted candidate fixtures require the explicit legacy adapter", () => {
  const oldPersisted = {
    ok: true,
    message: "Old persisted candidate restored.",
    session_id: "sess-old-persisted",
    turn_id: "0009",
    graph: { nodes: [{ id: 9, type: "PreviewImage" }], links: [] },
    candidate_graph_hash: "old-candidate-hash",
    apply_allowed: true,
    canvas_apply_allowed: true,
    queue_allowed: true,
    field_changes: [
      { uid: "preview", field_path: "inputs.images", old: null, new: "linked" },
    ],
  };

  assert.throws(
    () => normalizeCanonicalAgentEditResponse(oldPersisted, { endpoint: "/fixture/old-persisted" }),
    /missing outcome/i,
  );

  const adapted = adaptLegacyAgentEditResponse(oldPersisted, { endpoint: "/fixture/old-persisted" });
  const candidate = readApplyCandidate(adapted, { allowLegacy: false });

  assert.equal(adapted.outcome.kind, "candidate");
  assert.equal(candidate.graphHash, "old-candidate-hash");
  assert.deepEqual(readTurnIdentity(adapted, { allowLegacy: false }), {
    sessionId: "sess-old-persisted",
    turnId: "0009",
  });
  assert.deepEqual(readFieldChanges(adapted, { allowLegacy: false }).legacyChanges, [
    { uid: "preview", fieldPath: "inputs.images", new: "linked" },
  ]);
});

test("frontend contract selectors cover strict canonical, legacy adapter, and absent sections", () => {
  const canonicalOnly = {
    ok: true,
    message: "Candidate ready.",
    outcome: {
      kind: "candidate",
      changes: [
        { uid: "ksampler", field_path: "widgets.cfg", old: 7, new: 8 },
        { uid: "", field_path: "widgets.seed", old: 1, new: 2 },
      ],
    },
    candidate: {
      state: "candidate",
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
      graph_hash: "candidate-hash",
      turn_identity: {
        session_id: "sess-canonical",
        turn_id: 17,
      },
    },
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      message: "Ready to apply.",
      warnings: [],
    },
    debug: {
      stage_snapshots: [
        { stage: "plan", ok: true, blocking: false, duration_ms: 4 },
      ],
    },
  };

  const canonicalCandidate = readApplyCandidate(canonicalOnly, { allowLegacy: false });
  assert.equal(canonicalCandidate.graphHash, "candidate-hash");
  assert.deepEqual(canonicalCandidate.turnIdentity, {
    sessionId: "sess-canonical",
    turnId: "17",
  });
  assert.deepEqual(readStageSnapshot(canonicalOnly, { allowLegacy: false }), {
    stage: "plan",
    ok: true,
    blocking: false,
    durationMs: 4,
  });
  assert.deepEqual(readFieldChanges(canonicalOnly, { allowLegacy: false }).all, [
    { uid: "ksampler", fieldPath: "widgets.cfg", old: 7, new: 8 },
  ]);
  assert.equal(readUserFailure(canonicalOnly, { allowLegacy: false }), null);

  const legacyAdapterInput = {
    ok: true,
    message: "Legacy candidate ready.",
    graph: { nodes: [{ id: 2, type: "SaveImage" }], links: [] },
    apply_allowed: true,
    canvas_apply_allowed: true,
    queue_allowed: true,
    field_changes: [
      { uid: "save", field_path: "filename_prefix", old: "old", new: "new" },
    ],
    session_id: "sess-legacy",
    turn_id: "turn-legacy",
  };

  assert.throws(
    () => readApplyCandidate(legacyAdapterInput, { allowLegacy: false, endpoint: "/strict" }),
    /missing outcome/i,
  );
  const adaptedLegacy = adaptLegacyAgentEditResponse(legacyAdapterInput, { endpoint: "/compat" });
  assert.deepEqual(readApplyCandidate(adaptedLegacy)?.graph, legacyAdapterInput.graph);
  assert.deepEqual(readTurnIdentity(adaptedLegacy), {
    sessionId: "sess-legacy",
    turnId: "turn-legacy",
  });
  assert.deepEqual(readFieldChanges(adaptedLegacy).legacyChanges, [
    { uid: "save", fieldPath: "filename_prefix", old: "old", new: "new" },
  ]);
  assert.equal(readStageSnapshot(adaptedLegacy), null);

  const canonicalWithoutOptionalSections = {
    ok: true,
    message: "No candidate.",
    outcome: { kind: "noop", reason: "nothing changed" },
  };
  assert.equal(readApplyCandidate(canonicalWithoutOptionalSections, { allowLegacy: false }), null);
  assert.equal(readTurnIdentity(canonicalWithoutOptionalSections, { allowLegacy: false }), null);
  assert.equal(readStageSnapshot(canonicalWithoutOptionalSections, { allowLegacy: false }), null);
  assert.deepEqual(readFieldChanges(canonicalWithoutOptionalSections, { allowLegacy: false }).all, []);
});

test("user failure selector exposes sanitized public failure without debug raw detail", () => {
  const raw = {
    ok: false,
    message: "The provider is unavailable.",
    outcome: {
      kind: "error",
      failure_kind: "ProviderError",
      stage: "provider",
      next_action: "Try again after provider recovery.",
      retryable: true,
      agent_failure_context: {
        issues: [{ code: "provider_error", message: "Provider unavailable." }],
      },
    },
    debug: {
      failure: {
        raw_error: "provider token secret should stay debug-only",
      },
    },
  };

  const failure = readUserFailure(raw, { allowLegacy: false, endpoint: "/submit" });

  assert.deepEqual(failure, {
    kind: "error",
    failureKind: "ProviderError",
    stage: "provider",
    message: "The provider is unavailable.",
    nextAction: "Try again after provider recovery.",
    retryable: true,
    agentFailureContext: {
      issues: [{ code: "provider_error", message: "Provider unavailable." }],
    },
  });
  assert.equal(JSON.stringify(failure).includes("token secret"), false);
});

test("legacy response adaptation is explicit and canonical strict mode rejects legacy inference", () => {
  const legacy = {
    ok: true,
    graph: { nodes: [{ id: 1, type: "PreviewImage" }], links: [] },
    apply_allowed: true,
    canvas_apply_allowed: true,
  };

  assert.throws(
    () => normalizeCanonicalAgentEditResponse(legacy, { endpoint: "/strict" }),
    /missing outcome/i,
  );
  const adapted = adaptLegacyAgentEditResponse(legacy, { endpoint: "/compat" });
  assert.equal(adapted.outcome.kind, "candidate");
  assert.deepEqual(readApplyCandidate(adapted)?.graph, legacy.graph);
});

test("normalizeAgentEditResponse accepts canonical executor candidate envelope", () => {
  const raw = {
    ok: true,
    route: "revise",
    reply: "**Ready** to apply.",
    evidence: { touched: ["ksampler"] },
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
    },
    apply_eligible: true,
    no_candidate_reason: null,
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-executor" });

  assert.equal(normalized.route, "revise");
  assert.equal(normalized.reply, "**Ready** to apply.");
  assert.deepEqual(normalized.evidence, raw.evidence);
  assert.equal(normalized.outcome.kind, "candidate");
  assert.equal(normalized.applyEligible, true);
  assert.equal(normalized.applyAllowed, true);
  assert.equal(normalized.canvasApplyAllowed, true);
  assert.deepEqual(normalized.eligibility, {
    applyable: true,
    reason: "applyable",
    message: "Ready to apply.",
    warnings: [],
  });
  assert.deepEqual(normalized.candidateGraph, raw.candidate.graph);
});

test("normalizeAgentEditResponse gates executor candidates on apply_eligible plus candidate presence", () => {
  const blockedRaw = {
    ok: true,
    route: "revise",
    reply: "A graph was returned, but the backend marked it non-applyable.",
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
    },
    apply_eligible: false,
    no_candidate_reason: "candidate failed validation",
  };

  const blocked = normalizeAgentEditResponse(blockedRaw, { endpoint: "/vibecomfy/agent-executor" });

  assert.equal(blocked.outcome.kind, "noop");
  assert.equal(blocked.applyEligible, false);
  assert.equal(blocked.applyAllowed, false);
  assert.equal(blocked.canvasApplyAllowed, false);
  assert.equal(blocked.candidateGraph, null);
  assert.equal(blocked.candidate, null);
  assert.deepEqual(blocked.eligibility, {
    applyable: false,
    reason: "no_candidate",
    message: "candidate failed validation",
    warnings: [],
  });

  const eligibleRaw = {
    ok: true,
    route: "adapt",
    reply: "Adapted the graph.",
    candidate: {
      graph: { nodes: [{ id: 2, type: "PreviewImage" }], links: [] },
    },
    apply_eligible: true,
  };

  const eligible = normalizeAgentEditResponse(eligibleRaw, { endpoint: "/vibecomfy/agent-executor" });

  assert.equal(eligible.outcome.kind, "candidate");
  assert.equal(eligible.applyEligible, true);
  assert.equal(eligible.applyAllowed, true);
  assert.equal(eligible.canvasApplyAllowed, true);
  assert.deepEqual(eligible.candidateGraph, eligibleRaw.candidate.graph);
});

test("normalizeAgentEditResponse keeps canonical no-candidate envelopes non-applyable", () => {
  const raw = {
    ok: true,
    route: "inspect",
    reply: "This workflow uses one sampler.",
    evidence: ["saw_sampler"],
    candidate: null,
    apply_eligible: false,
    no_candidate_reason: "inspect turns do not produce candidates",
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-executor" });

  assert.equal(normalized.route, "inspect");
  assert.equal(normalized.outcome.kind, "noop");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
  assert.equal(normalized.applyEligible, false);
  assert.equal(normalized.applyAllowed, false);
  assert.equal(normalized.canvasApplyAllowed, false);
  assert.equal(normalized.noCandidateReason, "inspect turns do not produce candidates");
  assert.deepEqual(normalized.eligibility, {
    applyable: false,
    reason: "no_candidate",
    message: "inspect turns do not produce candidates",
    warnings: [],
  });
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

test("normalizeAgentEditResponse does not treat clarify diagnostic graphs as candidates", () => {
  const raw = {
    ok: true,
    message: "Which audio source should I use?",
    clarification_required: true,
    clarification_message: "Which audio source should I use?",
    graph_unchanged: true,
    graph: { nodes: [{ id: 7, type: "TextGenerateLTX2Prompt" }], links: [[1, 2, 0, 7, 3, "AUDIO"]] },
    candidate: null,
    candidate_graph_hash: "submitted-graph-hash",
    apply_eligibility: {
      applyable: false,
      reason: "no_candidate",
      message: "No candidate is available to apply.",
      warnings: [],
    },
    apply_allowed: false,
    canvas_apply_allowed: false,
    queue_allowed: false,
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.equal(normalized.outcome.kind, "clarify");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
});

test("normalizeAgentEditResponse does not expose candidateGraph for explicit non-candidate outcomes", () => {
  const raw = {
    ok: true,
    message: "Need clarification.",
    outcome: {
      kind: "clarify",
      question: "Where should the audio be connected?",
    },
    graph: { nodes: [{ id: 8, type: "LoadAudio" }], links: [] },
    candidate_graph: { nodes: [{ id: 9, type: "LoadAudio" }], links: [] },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.equal(normalized.outcome.kind, "clarify");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
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

// ── inspect / pure clarify no-candidate / no-Apply normalization ──

test("normalizeAgentEditResponse handles inspect noop with explicit no-candidate contract", () => {
  const raw = {
    ok: true,
    route: "inspect",
    message: "Graph inspection complete.",
    outcome: {
      kind: "noop",
      reason: "graph inspection complete — no edits requested",
    },
    graph: {
      nodes: [{ id: 1, type: "KSampler" }, { id: 2, type: "SaveImage" }],
      links: [[1, 1, 0, 2, 0, "IMAGE"]],
    },
    candidate: null,
    candidate_graph: null,
    graph_unchanged: true,
    canvas_apply_allowed: false,
    apply_allowed: false,
    queue_allowed: false,
    apply_eligibility: {
      applyable: false,
      reason: "no_candidate",
      message: "No candidate is available to apply.",
      warnings: [],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.equal(normalized.outcome.kind, "noop");
  assert.equal(normalized.outcome.reason, "graph inspection complete — no edits requested");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
  assert.equal(normalized.canvasApplyAllowed, false);
  assert.equal(normalized.applyAllowed, false);
  assert.equal(normalized.queueAllowed, false);
  assert.equal(normalized.graphUnchanged, true);
  assert.deepEqual(normalized.eligibility, {
    applyable: false,
    reason: "no_candidate",
    message: "No candidate is available to apply.",
    warnings: [],
  });
});

test("normalizeAgentEditResponse handles pure clarify with explicit no-candidate eligibility", () => {
  const raw = {
    ok: true,
    message: "Which audio source should I use?",
    outcome: {
      kind: "clarify",
      question: "Which audio source should I use?",
    },
    graph: {
      nodes: [{ id: 7, type: "LoadAudio" }],
      links: [],
    },
    candidate: null,
    candidate_graph: null,
    graph_unchanged: true,
    canvas_apply_allowed: false,
    apply_allowed: false,
    queue_allowed: false,
    apply_eligibility: {
      applyable: false,
      reason: "no_candidate",
      message: "No candidate is available to apply.",
      warnings: [],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.equal(normalized.outcome.kind, "clarify");
  assert.equal(normalized.outcome.question, "Which audio source should I use?");
  assert.deepEqual(normalized.outcome.clarification, {
    message: "Which audio source should I use?",
  });
  // Must not expose candidate
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
  // Apply must be blocked
  assert.equal(normalized.canvasApplyAllowed, false);
  assert.equal(normalized.applyAllowed, false);
  assert.equal(normalized.queueAllowed, false);
  assert.equal(normalized.graphUnchanged, true);
  // Eligibility must reflect no_candidate
  assert.deepEqual(normalized.eligibility, {
    applyable: false,
    reason: "no_candidate",
    message: "No candidate is available to apply.",
    warnings: [],
  });
});

test("readCandidateGraph returns null for non-candidate outcome even with graph present", () => {
  const raw = {
    ok: true,
    outcome: { kind: "noop", reason: "inspection only" },
    graph: { nodes: [{ id: 8, type: "PreviewImage" }], links: [] },
    candidate_graph: { nodes: [{ id: 9, type: "Note" }], links: [] },
  };

  const graph = readCandidateGraph(raw, { endpoint: "/submit" });
  assert.equal(graph, null, "non-candidate outcome must yield null candidateGraph");
});

test("readCandidate returns null for non-candidate outcome even with candidate payload", () => {
  const raw = {
    ok: true,
    outcome: { kind: "clarify", question: "Which node?" },
    candidate: {
      graph: { nodes: [{ id: 10, type: "KSampler" }], links: [] },
      metadata: { created: "2025-01-01" },
    },
  };

  const candidate = readCandidate(raw, { endpoint: "/submit" });
  assert.equal(candidate, null, "clarify outcome must yield null candidate");
});

test("normalizeAgentEditResponse preserves apply eligibility for valid candidate with gate context", () => {
  const raw = {
    ok: true,
    message: "Candidate ready.",
    outcome: {
      kind: "candidate",
      changes: [{ uid: "ksampler", field_path: "steps", old: 20, new: 26 }],
    },
    candidate: {
      graph: { nodes: [{ id: 11, type: "KSampler" }], links: [] },
    },
    candidate_graph_hash: "candidate-hash-valid",
    canvas_apply_allowed: true,
    apply_allowed: true,
    queue_allowed: false,
    apply_eligibility: {
      applyable: true,
      reason: "queue_blocked_warning",
      message: "Apply is allowed, but Queue remains blocked for this candidate.",
      warnings: ["queue_blocked"],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.equal(normalized.outcome.kind, "candidate");
  assert.ok(normalized.candidateGraph, "candidate graph must be present for candidate outcome");
  assert.ok(normalized.candidate, "candidate envelope must be present");
  assert.deepEqual(normalized.eligibility, {
    applyable: true,
    reason: "queue_blocked_warning",
    message: "Apply is allowed, but Queue remains blocked for this candidate.",
    warnings: ["queue_blocked"],
  });
  assert.equal(normalized.canvasApplyAllowed, true);
  assert.equal(normalized.applyAllowed, true);
  assert.equal(normalized.queueAllowed, false);
});

test("normalizeAgentEditResponse handles revise candidate with full apply eligibility", () => {
  const raw = {
    ok: true,
    route: "revise",
    message: "Applied the requested edit.",
    outcome: {
      kind: "candidate",
      changes: [{ uid: "node-1", field_path: "widgets.seed", old: 7, new: 42 }],
    },
    graph: { nodes: [{ id: 12, type: "KSampler" }], links: [] },
    candidate_graph_hash: "hash-direct-edit",
    apply_eligible: true,
    canvas_apply_allowed: true,
    apply_allowed: true,
    queue_allowed: true,
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      message: "Ready to apply.",
      warnings: [],
    },
    change_focus: "Focused change",
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.equal(normalized.outcome.kind, "candidate");
  assert.equal(normalized.outcome.changes.length, 1);
  assert.equal(normalized.outcome.changes[0].uid, "node-1");
  assert.ok(normalized.candidateGraph, "candidate graph must be present");
  assert.ok(normalized.candidate, "candidate envelope must be present");
  assert.deepEqual(normalized.eligibility, {
    applyable: true,
    reason: "applyable",
    message: "Ready to apply.",
    warnings: [],
  });
  assert.equal(normalized.canvasApplyAllowed, true);
  assert.equal(normalized.applyAllowed, true);
  assert.equal(normalized.queueAllowed, true);
});
