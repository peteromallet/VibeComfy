import test from "node:test";
import assert from "node:assert/strict";

import {
  PUBLIC_OUTCOME_KINDS,
  DIAGNOSTIC_DETAIL_KEYS,
  adaptLegacyAgentEditResponse,
  normalizeAgentEditResponse,
  normalizeCanonicalAgentEditResponse,
  outcomeRequiresCustomNodes,
  readApplyCandidate,
  readCandidate,
  readCandidateGraph,
  readCustomNodeResolution,
  readEligibility,
  readFieldChanges,
  readLatestCandidate,
  readOutcome,
  readRebaselineRecovery,
  readStageSnapshot,
  readTurnIdentity,
  readUserFailure,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract.js";

import {
  COMPLETION_PROOF_STATES,
  COMPLETION_PROOF_DOMAINS,
  OBLIGATION_KINDS,
  OBLIGATION_STATUSES,
  OBLIGATION_SEVERITIES,
  DELTA_DIAGNOSTIC_CORRUPTED,
  DELTA_DIAGNOSTIC_TRUNCATED,
  DELTA_DIAGNOSTIC_ABSENT,
  DELTA_DIAGNOSTIC_REPLAY_MISMATCH,
  DELTA_DIAGNOSTIC_CODES,
  PLAN_OBLIGATION_STATES,
  isValidProofState,
  isValidProofDomain,
  isValidObligationKind,
  isValidObligationStatus,
  isValidObligationSeverity,
  readDeltaEnvelope,
  readIdempotencyKey,
  readObligationArtifacts,
  isNonApplyableClarify,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js";
import { sha256Hex, sha256HexFromString } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";
import {
  buildLayoutGraphProjection,
  structuralGraphProjectionJson,
} from "../../vibecomfy/comfy_nodes/web/projection_registry_v1.js";
import { makeValidCandidateTransactionV2 } from "./authority_factory.mjs";

const FORBIDDEN_NORMAL_PATH_KEYS = new Set([
  "executor_pending",
  "apply_allowed",
  "canvas_apply_allowed",
  "applyAllowed",
  "canvasApplyAllowed",
  "queue_allowed",
  "queueAllowed",
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
    "candidate_transaction",
    "noop",
    "clarify",
    "error",
    "requires_custom_nodes",
  ]);
});

test("normalizeAgentEditResponse preserves requires_custom_nodes resolver evidence", () => {
  const raw = {
    ok: true,
    route: "requires_custom_nodes",
    message: "Custom nodes are required.",
    outcome: {
      kind: "requires_custom_nodes",
      candidates: [
        {
          pack: { slug: "ComfyUI-VideoHelperSuite", source: "comfyui-manager" },
          expected_classes: ["VHS_VideoCombine"],
          validation_mode: "class_validatable",
          evidence: [
            {
              source: "custom-node-map",
              matched_classes: ["VHS_VideoCombine"],
            },
          ],
          warnings: [],
          stable_install_hash: "hash-vhs",
        },
        {
          pack: { slug: "ComfyUI-AnimateDiff-Evolved", source: "comfyui-manager" },
          expected_classes: [],
          validation_mode: "evidence_only",
          evidence: [{ source: "custom-node-list", matched_classes: [] }],
          warnings: ["No concrete class evidence."],
          stable_install_hash: "hash-ade",
        },
      ],
      warnings: ["Install requires explicit confirmation."],
    },
    candidate: { graph: { nodes: [{ id: 1 }], links: [] } },
    apply_eligible: true,
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "submit" });
  const evidence = readCustomNodeResolution(normalized, { allowLegacy: false });

  assert.equal(normalized.route, "requires_custom_nodes");
  assert.equal(normalized.outcome.kind, "requires_custom_nodes");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
  assert.equal(evidence.candidates.length, 2);
  assert.deepEqual(evidence.candidates[0].expectedClasses, ["VHS_VideoCombine"]);
  assert.equal(evidence.candidates[0].validationMode, "class_validatable");
  assert.equal(evidence.candidates[0].stableInstallHash, "hash-vhs");
  assert.equal(evidence.candidates[1].validationMode, "evidence_only");
  assert.deepEqual(evidence.candidates[1].warnings, ["No concrete class evidence."]);
  assert.deepEqual(evidence.warnings, ["Install requires explicit confirmation."]);
});

test("outcomeRequiresCustomNodes recognizes only the public custom-node outcome", () => {
  assert.equal(outcomeRequiresCustomNodes({ kind: "requires_custom_nodes" }), true);
  assert.equal(outcomeRequiresCustomNodes({ kind: "candidate" }), false);
  assert.equal(outcomeRequiresCustomNodes(null), false);
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

// ─────────────────────────────────────────────────────────────────────────────
// T11 — Projection-leak contract for the normalized response projection.
//
// The normalized projection exposes a curated surface (outcome, candidateGraph,
// eligibility, turnIdentity, message, report, ...). Raw/internal fields that
// must never surface as first-class projection fields (raw graph payloads,
// debug payloads, provider diagnostics, model/system prompts, audit paths, and
// live LiteGraph objects) are tested here. They may travel inside `normalized.raw`
// (the explicit raw mirror kept for diagnostics), but must NOT be hoisted onto
// the curated projection fields themselves.
// ─────────────────────────────────────────────────────────────────────────────

const LEAK_FORBIDDEN_KEYS = [
  "raw_graph",
  "rawGraph",
  "debug_payload",
  "debugPayload",
  "provider_diagnostics",
  "providerDiagnostics",
  "model_prompt",
  "modelPrompt",
  "system_prompt",
  "systemPrompt",
  "audit_path",
  "auditPath",
  "live_litegraph",
  "liveLitegraph",
];

const LEAK_FORBIDDEN_REGEX =
  /(?:raw_?graph|debug_?payload|provider_?diagnostics|model_?prompt|system_?prompt|audit_?path|live_?litegraph)/i;

function collectLeakKeys(value, path = "$", acc = []) {
  if (value === null || value === undefined || typeof value !== "object") {
    return acc;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => collectLeakKeys(entry, `${path}[${index}]`, acc));
    return acc;
  }
  for (const [key, entry] of Object.entries(value)) {
    const keyPath = `${path}.${key}`;
    if (LEAK_FORBIDDEN_KEYS.includes(key) || LEAK_FORBIDDEN_REGEX.test(key)) {
      acc.push(keyPath);
    }
    collectLeakKeys(entry, keyPath, acc);
  }
  return acc;
}

// The curated projection surface (every field normalizeAgentEditResponse
// deliberately exposes). Forbidden raw payloads must never appear here.
const CURATED_PROJECTION_FIELDS = [
  "ok",
  "exists",
  "message",
  "route",
  "agentEditProtocol",
  "reply",
  "evidence",
  "outcome",
  "customNodeResolution",
  "candidateGraph",
  "candidate",
  "candidateGraphHash",
  "terminalState",
  "terminalReason",
  "authorityReceipt",
  "eligibility",
  "turnIdentity",
  "stageSnapshots",
  "fieldChanges",
  "diagnostics",
  "applyEligible",
  "noCandidateReason",
  "applyAllowed",
  "canvasApplyAllowed",
  "queueAllowed",
  "graphUnchanged",
  "report",
  "auditRef",
  "debug",
  "failureKind",
  "retryable",
  "runtimeDependencies",
  "nextAction",
  "clarificationRequired",
  "clarificationMessage",
  "rebaselineRecovery",
  "sessionId",
  "turnId",
  "baselineTurnId",
  "baselineGraphHash",
  "baselineGraphHashKind",
  "baselineGraphHashVersion",
  "baselineSource",
  "baselineRebaselineId",
  "baselineGraphSourcePath",
  "submitGraphHash",
  "clientGraphHash",
  "clientStructuralGraphHash",
  "latestCandidate",
  "candidateTransaction",
  "legacyMigration",
  "messages",
  "sessionPath",
  "sessionPathResolved",
  "detailJsonPath",
  "detailJsonPathResolved",
];

test("normalized projection surface stays closed: no unexpected top-level keys beyond raw/endpoint/marker", () => {
  const raw = {
    ok: true,
    message: "Candidate ready.",
    outcome: { kind: "candidate" },
    candidate: { graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] } },
    candidate_graph_hash: "gh",
    apply_eligibility: { applyable: true, reason: "applyable", message: "ok", warnings: [] },
  };
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  const allowedTop = new Set([
    ...CURATED_PROJECTION_FIELDS,
    "raw", // explicit raw mirror
    "endpoint",
    "__agentEditResponseNormalized", // NORMALIZED_RESPONSE_MARKER
  ]);
  for (const key of Object.keys(normalized)) {
    assert.ok(
      allowedTop.has(key),
      `normalized projection gained an unexpected top-level key "${key}" — extend CURATED_PROJECTION_FIELDS if intentional`,
    );
  }
});

test("normalized curated projection fields never carry forbidden raw/debug/provider/prompt/audit/litegraph payloads", () => {
  const raw = {
    ok: true,
    message: "Candidate ready.",
    outcome: { kind: "candidate" },
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
      graph_hash: "gh-leak",
    },
    candidate_graph_hash: "gh-leak",
    apply_eligibility: { applyable: true, reason: "applyable", message: "ok", warnings: [] },
    // Forbidden raw payloads that must NOT be hoisted onto curated projection:
    raw_graph: { nodes: [{ id: 99, type: "LATENT" }], links: [] },
    debug_payload: { internal_trace: "secret" },
    provider_diagnostics: { tokens_in: 1, model_id: "secret-model" },
    model: "secret-model",
    model_prompt: "hidden model prompt",
    system_prompt: "hidden system prompt",
    audit_path: "/secret/audit/turn.json",
    live_litegraph: { __lgNode: true },
  };
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });

  for (const field of CURATED_PROJECTION_FIELDS) {
    const value = normalized[field];
    const leaks = collectLeakKeys(value, `$.${field}`);
    assert.equal(
      leaks.length,
      0,
      `curated projection field "${field}" leaked forbidden payload at: ${JSON.stringify(leaks.slice(0, 3))}`,
    );
  }
});

test("normalized candidateGraph projection never aliases the forbidden raw_graph payload", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate" },
    candidate: { graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] } },
    candidate_graph_hash: "gh",
    raw_graph: { nodes: [{ id: 99, type: "LATENT" }], links: [] },
    apply_eligibility: { applyable: true, reason: "applyable", message: "ok", warnings: [] },
  };
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.ok(normalized.candidateGraph, "candidateGraph must be projected");
  assert.notDeepEqual(
    normalized.candidateGraph,
    raw.raw_graph,
    "candidateGraph must not alias the forbidden raw_graph payload",
  );
  assert.deepEqual(
    normalized.candidateGraph,
    raw.candidate.graph,
    "candidateGraph must equal the canonical candidate.graph",
  );
});

test("readCandidateGraph/readEligibility/readTurnIdentity do not surface forbidden raw payloads", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate" },
    candidate: {
      graph: { nodes: [{ id: 7, type: "VAEDecode" }], links: [] },
      graph_hash: "gh-read",
      turn_identity: { session_id: "s1", turn_id: "t1" },
    },
    apply_eligibility: { applyable: true, reason: "applyable", message: "ok", warnings: [] },
    raw_graph: { nodes: [{ id: 99, type: "LATENT" }], links: [] },
    debug_payload: { secret: true },
    provider_diagnostics: { tokens: 5 },
    system_prompt: "secret",
    audit_path: "/secret",
  };
  const graph = readCandidateGraph(raw, { endpoint: "/submit" });
  assert.deepEqual(graph, raw.candidate.graph);
  assert.notDeepEqual(graph, raw.raw_graph, "readCandidateGraph must not surface raw_graph");

  const eligibility = readEligibility(raw, { endpoint: "/submit" });
  const eligLeaks = collectLeakKeys(eligibility, "$.eligibility");
  assert.equal(eligLeaks.length, 0, "readEligibility must not surface forbidden payloads");

  const identity = readTurnIdentity(raw, { endpoint: "/submit" });
  const idLeaks = collectLeakKeys(identity, "$.turnIdentity");
  assert.equal(idLeaks.length, 0, "readTurnIdentity must not surface forbidden payloads");
});

test("normalizeCanonicalAgentEditResponse keeps the curated projection leak-free for a candidate", () => {
  const raw = {
    ok: true,
    message: "Canonical candidate.",
    outcome: { kind: "candidate" },
    candidate: {
      graph: { nodes: [{ id: 3, type: "CLIPTextEncode" }], links: [] },
      graph_hash: "canonical-gh",
      turn_identity: { session_id: "cs1", turn_id: "ct1" },
    },
    apply_eligibility: { applyable: true, reason: "applyable", message: "ok", warnings: [] },
    raw_graph: { nodes: [{ id: 99 }], links: [] },
    debug_payload: { secret: true },
    provider_diagnostics: { tokens: 9 },
    model: "secret",
    system_prompt: "secret",
    audit_path: "/secret",
  };
  const normalized = normalizeCanonicalAgentEditResponse(raw, { endpoint: "/submit" });
  for (const field of CURATED_PROJECTION_FIELDS) {
    const leaks = collectLeakKeys(normalized[field], `$.${field}`);
    assert.equal(
      leaks.length,
      0,
      `canonical projection field "${field}" leaked forbidden payload: ${JSON.stringify(leaks.slice(0, 3))}`,
    );
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// T10 — Curated diagnostics normalization with capped enum choices / valid_fields
// ─────────────────────────────────────────────────────────────────────────────

test("DIAGNOSTIC_DETAIL_KEYS stays the closed public contract", () => {
  assert.deepEqual(DIAGNOSTIC_DETAIL_KEYS, [
    "choices",
    "valid_fields",
    "available_slots",
  ]);
});

test("normalizeAgentEditResponse surfaces safe diagnostics from outcome.diagnostics", () => {
  const raw = {
    ok: false,
    outcome: {
      kind: "error",
      diagnostics: [
        {
          code: "unknown_field",
          severity: "error",
          message: "Field \"bogus\" is not recognized.",
          detail: {
            valid_fields: ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
            input: "bogus",
          },
        },
      ],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.ok(Array.isArray(normalized.diagnostics), "diagnostics must be an array");
  assert.equal(normalized.diagnostics.length, 1);

  const diag = normalized.diagnostics[0];
  assert.equal(diag.code, "unknown_field");
  assert.equal(diag.severity, "error");
  assert.equal(diag.message, "Field \"bogus\" is not recognized.");
  assert.ok(diag.detail, "detail must be present");
  assert.deepEqual(diag.detail.valid_fields, [
    "seed", "steps", "cfg", "sampler_name", "scheduler", "denoise",
  ]);
  // Raw debug payloads must never be hoisted into diagnostics.
  assert.equal(Object.prototype.hasOwnProperty.call(diag.detail, "input"), false);
});

test("normalizeAgentEditResponse surfaces safe diagnostics from top-level diagnostics array", () => {
  const raw = {
    ok: false,
    outcome: { kind: "error" },
    diagnostics: [
      {
        code: "value_not_in_enum",
        severity: "warning",
        message: "\"nonexistent_sampler\" is not a valid sampler_name.",
        detail: {
          choices: ["euler", "euler_ancestral", "heun", "dpmpp_2m", "dpmpp_sde", "lcm", "uni_pc", "ddim"],
          value: "nonexistent_sampler",
        },
      },
    ],
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.diagnostics.length, 1);

  const diag = normalized.diagnostics[0];
  assert.equal(diag.code, "value_not_in_enum");
  assert.equal(diag.severity, "warning");
  assert.deepEqual(diag.detail.choices, [
    "euler", "euler_ancestral", "heun", "dpmpp_2m", "dpmpp_sde", "lcm", "uni_pc", "ddim",
  ]);
  // Raw detail value (the rejected input) must never be hoisted.
  assert.equal(Object.prototype.hasOwnProperty.call(diag.detail, "value"), false);
});

test("normalizeAgentEditResponse caps diagnostic detail lists at DIAGNOSTIC_LIST_CAP", () => {
  const manyChoices = Array.from({ length: 15 }, (_, i) => `choice_${i}`);
  const raw = {
    ok: false,
    outcome: { kind: "error" },
    diagnostics: [
      {
        code: "value_not_in_enum",
        message: "Bad value.",
        detail: { choices: manyChoices },
      },
    ],
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  const diag = normalized.diagnostics[0];
  assert.ok(Array.isArray(diag.detail.choices));
  assert.ok(diag.detail.choices.length <= 8, "choices must be capped at 8");
  assert.deepEqual(diag.detail.choices, manyChoices.slice(0, 8));
});

test("normalizeAgentEditResponse collects diagnostics from stageSnapshots[].issues[]", () => {
  const raw = {
    ok: false,
    outcome: { kind: "error" },
    debug: {
      stage_snapshots: [
        {
          stage: "queue_validate",
          ok: false,
          blocking: true,
          issues: [
            {
              code: "queue_blocked",
              severity: "error",
              message: "Queue validation blocked.",
              detail: { available_slots: ["seed", "steps"] },
            },
          ],
        },
      ],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.diagnostics.length, 1);
  assert.equal(normalized.diagnostics[0].code, "queue_blocked");
  assert.deepEqual(normalized.diagnostics[0].detail.available_slots, ["seed", "steps"]);
});

test("normalizeAgentEditResponse collects diagnostics from change_details batch turns", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate" },
    change_details: {
      batch_turns: [
        {
          turn_number: 1,
          diagnostics: [
            {
              code: "value_not_in_enum",
              message: "Invalid sampler.",
              detail: { choices: ["euler", "heun"] },
            },
          ],
        },
        {
          turn_number: 2,
          diagnostics: [
            {
              code: "unknown_field",
              message: "Unknown field.",
              detail: { valid_fields: ["cfg", "steps"] },
            },
          ],
        },
      ],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.diagnostics.length, 2);
  // First batch turn diagnostic (value_not_in_enum with choices)
  assert.equal(normalized.diagnostics[0].code, "value_not_in_enum");
  assert.deepEqual(normalized.diagnostics[0].detail.choices, ["euler", "heun"]);
  // Second batch turn diagnostic (unknown_field with valid_fields)
  assert.equal(normalized.diagnostics[1].code, "unknown_field");
  assert.deepEqual(normalized.diagnostics[1].detail.valid_fields, ["cfg", "steps"]);
});

test("normalizeAgentEditResponse deduplicates diagnostics by code+message fingerprint", () => {
  const raw = {
    ok: false,
    outcome: {
      kind: "error",
      diagnostics: [
        { code: "value_not_in_enum", message: "Invalid sampler.", detail: { choices: ["euler"] } },
      ],
    },
    diagnostics: [
      { code: "value_not_in_enum", message: "Invalid sampler.", detail: { choices: ["euler"] } },
    ],
    debug: {
      stage_snapshots: [
        {
          stage: "plan",
          issues: [
            { code: "value_not_in_enum", message: "Invalid sampler." },
          ],
        },
      ],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  // All three sources carry the same code+message — only one entry survives.
  assert.equal(normalized.diagnostics.length, 1);
  assert.equal(normalized.diagnostics[0].code, "value_not_in_enum");
});

test("normalizeAgentEditResponse returns null diagnostics when no source has issues", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate" },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.diagnostics, null);
});

test("normalizeAgentEditResponse diagnostics never leak raw debug/provider payloads", () => {
  const raw = {
    ok: false,
    outcome: {
      kind: "error",
      diagnostics: [
        {
          code: "value_not_in_enum",
          message: "Bad enum.",
          detail: {
            choices: ["a", "b"],
            // Forbidden keys that must NOT surface:
            raw_error: "provider token secret",
            debug_payload: { internal_trace: "secret" },
            provider_diagnostics: { model: "secret-model" },
            system_prompt: "secret system prompt",
            model_prompt: "hidden",
            input: "rejected_value",
            value: "rejected_value",
          },
        },
      ],
    },
    debug: {
      stage_snapshots: [
        {
          stage: "plan",
          issues: [
            {
              code: "unknown_field",
              message: "Unknown field.",
              detail: {
                valid_fields: ["steps"],
                raw_graph: { secret: true },
                debug_payload: { trace: "leak" },
              },
            },
          ],
        },
      ],
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.diagnostics.length, 2);

  for (const diag of normalized.diagnostics) {
    assert.ok(diag.code, "every diagnostic must have a code");
    // Verify only whitelisted detail keys survive.
    if (diag.detail) {
      for (const key of Object.keys(diag.detail)) {
        assert.ok(
          DIAGNOSTIC_DETAIL_KEYS.includes(key),
          `diagnostic detail key "${key}" is not in DIAGNOSTIC_DETAIL_KEYS`,
        );
      }
    }
  }

  // Stringify and scan: raw debug/provider terms must not appear anywhere in diagnostics.
  const diagJson = JSON.stringify(normalized.diagnostics);
  const forbiddenTerms = [
    "raw_error", "debug_payload", "provider_diagnostics",
    "system_prompt", "model_prompt", "raw_graph",
  ];
  for (const term of forbiddenTerms) {
    assert.equal(
      diagJson.includes(term),
      false,
      `diagnostics must not contain forbidden term "${term}"`,
    );
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// T16 — Browser contract parity: cumulative delta, proofs, obligations,
//       authority receipts, idempotency, malformed delta, non-applyable clarify.
//
// These tests consume Python-generated/fixture contract shapes without
// reimplementing Python semantics.  The JS generated module provides
// vocabulary constants and lightweight read helpers; the browser-side
// agent_edit_response_contract.js layers camelCase adaptation on top.
// ─────────────────────────────────────────────────────────────────────────────

// ── Completion proof vocabulary ─────────────────────────────────────────

test("COMPLETION_PROOF_STATES matches Python four-state vocabulary", () => {
  assert.deepEqual(COMPLETION_PROOF_STATES, [
    "pass",
    "fail",
    "not_run",
    "unknown",
  ]);
  // Missing proof is never success — "unknown" is the fail-closed default.
  assert.equal(isValidProofState("pass"), true);
  assert.equal(isValidProofState("fail"), true);
  assert.equal(isValidProofState("not_run"), true);
  assert.equal(isValidProofState("unknown"), true);
  assert.equal(isValidProofState("success"), false);
  assert.equal(isValidProofState(null), false);
  assert.equal(isValidProofState(undefined), false);
});

test("COMPLETION_PROOF_DOMAINS matches Python four-domain contract", () => {
  assert.deepEqual(COMPLETION_PROOF_DOMAINS, [
    "transformation_safety",
    "graph_validity",
    "task_satisfaction",
    "runtime_readiness",
  ]);
  for (const domain of COMPLETION_PROOF_DOMAINS) {
    assert.equal(isValidProofDomain(domain), true, `${domain} must be valid`);
  }
  assert.equal(isValidProofDomain("bogus"), false);
  assert.equal(isValidProofDomain(""), false);
});

// ── Obligation ledger vocabulary ────────────────────────────────────────

test("OBLIGATION_KINDS matches Python seven-kind contract", () => {
  assert.deepEqual(OBLIGATION_KINDS, [
    "class_present",
    "class_absent",
    "value_match",
    "edge_exists",
    "terminal_output_domain",
    "scope_preserved",
    "obligation_declared",
  ]);
  for (const kind of OBLIGATION_KINDS) {
    assert.equal(isValidObligationKind(kind), true);
  }
  assert.equal(isValidObligationKind("bogus"), false);
});

test("OBLIGATION_STATUSES matches Python five-status contract", () => {
  assert.deepEqual(OBLIGATION_STATUSES, [
    "satisfied",
    "unsatisfied",
    "unknown",
    "not_evaluated",
    "unsupported",
  ]);
  for (const status of OBLIGATION_STATUSES) {
    assert.equal(isValidObligationStatus(status), true);
  }
  assert.equal(isValidObligationStatus("pass"), false);
  assert.equal(isValidObligationStatus("fail"), false);
});

test("OBLIGATION_SEVERITIES matches Python three-severity contract", () => {
  assert.deepEqual(OBLIGATION_SEVERITIES, [
    "required",
    "recommended",
    "optional",
  ]);
  for (const severity of OBLIGATION_SEVERITIES) {
    assert.equal(isValidObligationSeverity(severity), true);
  }
  assert.equal(isValidObligationSeverity("mandatory"), false);
});

test("PLAN_OBLIGATION_STATES matches Python three-state contract", () => {
  assert.deepEqual(PLAN_OBLIGATION_STATES, [
    "not_required",
    "required_supported",
    "required_unsupported",
  ]);
});

// ── Delta diagnostic codes ──────────────────────────────────────────────

test("DELTA_DIAGNOSTIC_CODES includes malformed, corrupted, truncated, absent, replay mismatch", () => {
  assert.equal(DELTA_DIAGNOSTIC_CORRUPTED, "corrupted_delta");
  assert.equal(DELTA_DIAGNOSTIC_TRUNCATED, "truncated_delta");
  assert.equal(DELTA_DIAGNOSTIC_ABSENT, "absent_delta");
  assert.equal(DELTA_DIAGNOSTIC_REPLAY_MISMATCH, "replay_mismatch");

  assert.deepEqual(DELTA_DIAGNOSTIC_CODES, [
    "malformed_delta",
    "legacy_delta_shape",
    "unsupported_scoped_apply",
    "corrupted_delta",
    "truncated_delta",
    "absent_delta",
    "replay_mismatch",
  ]);
});

// ── Cumulative delta envelope consumption ───────────────────────────────

test("readDeltaEnvelope extracts ops from accepted_batch", () => {
  const fixture = {
    ok: true,
    outcome: { kind: "candidate" },
    accepted_batch: [
      { op: { op: "set_node_field", target: ["", "n1", "widgets.steps"], value: 28 } },
      { op: { op: "add_node", scope_path: "", uid: "u-new", node_id: "99", class_type: "PreviewImage", fields: {}, inputs: {} } },
    ],
  };

  const envelope = readDeltaEnvelope(fixture);
  assert.ok(envelope, "delta envelope must be present");
  assert.equal(envelope.schema_version, "2.0.0");
  assert.equal(envelope.ops.length, 2);
  assert.equal(envelope.ops[0].op, "set_node_field");
  assert.equal(envelope.ops[1].op, "add_node");
});

test("readDeltaEnvelope returns null when accepted_batch is absent", () => {
  assert.equal(readDeltaEnvelope({ ok: true }), null);
  assert.equal(readDeltaEnvelope({ accepted_batch: null }), null);
  assert.equal(readDeltaEnvelope({ delta_ops_envelope: null }), null);
  assert.equal(readDeltaEnvelope(null), null);
});

test("readDeltaEnvelope returns empty ops when accepted_batch statements have no object op", () => {
  const envelope = readDeltaEnvelope({
    accepted_batch: [{ not_an_op: true }, { op: "not-object" }],
  });
  assert.ok(envelope);
  assert.equal(envelope.schema_version, "2.0.0");
  assert.deepEqual(envelope.ops, []);
});

// ── Idempotency key passthrough ─────────────────────────────────────────

test("readIdempotencyKey extracts key from top-level snake_case", () => {
  assert.equal(readIdempotencyKey({ idempotency_key: "idem-abc" }), "idem-abc");
});

test("readIdempotencyKey extracts key from top-level camelCase", () => {
  assert.equal(readIdempotencyKey({ idempotencyKey: "idem-xyz" }), "idem-xyz");
});

test("readIdempotencyKey extracts key from candidate.turn_identity", () => {
  assert.equal(
    readIdempotencyKey({
      candidate: { turn_identity: { idempotency_key: "idem-cand" } },
    }),
    "idem-cand",
  );
});

test("readIdempotencyKey extracts key from debug.turn_identity", () => {
  assert.equal(
    readIdempotencyKey({
      debug: { turn_identity: { idempotency_key: "idem-debug" } },
    }),
    "idem-debug",
  );
});

test("readIdempotencyKey prefers top-level over nested sources", () => {
  assert.equal(
    readIdempotencyKey({
      idempotency_key: "idem-top",
      candidate: { turn_identity: { idempotency_key: "idem-nested" } },
    }),
    "idem-top",
  );
});

test("readIdempotencyKey returns null when absent", () => {
  assert.equal(readIdempotencyKey({ ok: true }), null);
  assert.equal(readIdempotencyKey(null), null);
});

// ── Obligation / task satisfaction artifact consumption ─────────────────

test("readObligationArtifacts returns both task_satisfaction and obligation_ledger", () => {
  const fixture = {
    ok: true,
    task_satisfaction: [
      { check: "execution_plan", status: "pass", satisfaction: "pass", description: "Plan ok." },
    ],
    obligation_ledger: {
      obligations: [
        {
          kind: "class_present",
          status: "satisfied",
          severity: "required",
          description: "KSampler required",
        },
      ],
      aggregate_status: "satisfied",
    },
  };

  const artifacts = readObligationArtifacts(fixture);
  assert.ok(artifacts);
  assert.equal(artifacts.task_satisfaction.length, 1);
  assert.equal(artifacts.task_satisfaction[0].check, "execution_plan");
  assert.equal(artifacts.obligation_ledger.obligations.length, 1);
  assert.equal(artifacts.obligation_ledger.obligations[0].kind, "class_present");
});

test("readObligationArtifacts returns null when neither field is present", () => {
  assert.equal(readObligationArtifacts({ ok: true }), null);
  assert.equal(readObligationArtifacts(null), null);
});

test("readObligationArtifacts returns only task_satisfaction when obligation_ledger absent", () => {
  const artifacts = readObligationArtifacts({
    task_satisfaction: [{ check: "plan", status: "fail" }],
  });
  assert.ok(artifacts);
  assert.equal(artifacts.task_satisfaction.length, 1);
  assert.equal(artifacts.obligation_ledger, null);
});

// ── Non-applyable clarify detection ─────────────────────────────────────

test("isNonApplyableClarify returns true for pure clarify without candidate payloads", () => {
  const fixture = {
    ok: true,
    outcome: { kind: "clarify", question: "Which node?" },
    clarification_required: true,
    message: "Which node should I use?",
    graph_unchanged: true,
    apply_allowed: false,
    canvas_apply_allowed: false,
    queue_allowed: false,
  };

  assert.equal(isNonApplyableClarify(fixture), true);
});

test("isNonApplyableClarify rejects clarify with candidate payload present", () => {
  // A clarify that leaks a candidate graph is not non-applyable clarify.
  assert.equal(
    isNonApplyableClarify({
      ok: true,
      outcome: { kind: "clarify", question: "Keep the seed?" },
      clarification_required: true,
      candidate: { graph: { nodes: [{ id: 1 }], links: [] } },
    }),
    false,
  );

  assert.equal(
    isNonApplyableClarify({
      ok: true,
      outcome: { kind: "clarify" },
      clarification_required: true,
      graph: { nodes: [{ id: 1 }], links: [] },
    }),
    false,
  );
});

test("isNonApplyableClarify rejects when clarification_required is not true", () => {
  assert.equal(
    isNonApplyableClarify({
      ok: true,
      outcome: { kind: "clarify", question: "Which?" },
    }),
    false,
  );
});

test("isNonApplyableClarify rejects non-clarify outcomes", () => {
  assert.equal(isNonApplyableClarify({ outcome: { kind: "candidate" } }), false);
  assert.equal(isNonApplyableClarify({ outcome: { kind: "noop" } }), false);
  assert.equal(isNonApplyableClarify({ outcome: { kind: "error" } }), false);
});

test("isNonApplyableClarify rejects null/non-object", () => {
  assert.equal(isNonApplyableClarify(null), false);
  assert.equal(isNonApplyableClarify("string"), false);
});

// ── Non-applyable clarify obligation contract through normalization ─────

test("normalizeAgentEditResponse preserves non-applyable clarify obligations without leaking candidate", () => {
  const raw = {
    ok: true,
    message: "Which audio source should I use?",
    outcome: {
      kind: "clarify",
      question: "Which audio source should I use?",
    },
    clarification_required: true,
    clarification_message: "Which audio source should I use?",
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
    task_satisfaction: [
      { check: "execution_plan", status: "not_evaluated", satisfaction: "not_evaluated", description: "Not applicable for clarify." },
    ],
    obligation_ledger: {
      obligations: [
        {
          kind: "class_present",
          status: "not_evaluated",
          severity: "required",
          description: "Audio source node required before edit can proceed.",
        },
      ],
      aggregate_status: "not_evaluated",
    },
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/vibecomfy/agent-edit" });

  assert.equal(normalized.outcome.kind, "clarify");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
  assert.equal(normalized.canvasApplyAllowed, false);
  assert.equal(normalized.applyAllowed, false);
  assert.equal(normalized.queueAllowed, false);
  assert.equal(normalized.graphUnchanged, true);

  // Obligation artifacts must be readable through generated helpers.
  const obligationArtifacts = readObligationArtifacts(normalized.raw);
  assert.ok(obligationArtifacts, "obligation artifacts must be readable from raw");
  assert.equal(obligationArtifacts.task_satisfaction.length, 1);
  assert.equal(obligationArtifacts.task_satisfaction[0].satisfaction, "not_evaluated");
  assert.equal(obligationArtifacts.obligation_ledger.obligations.length, 1);
  assert.equal(obligationArtifacts.obligation_ledger.obligations[0].kind, "class_present");
  assert.equal(obligationArtifacts.obligation_ledger.aggregate_status, "not_evaluated");

  // Non-applyable clarify detection works through generated helper.
  assert.equal(isNonApplyableClarify(normalized.raw), true);
});

// ── Authority receipt hash references in fixture responses ──────────────

test("generated read helpers consume authority receipt hash fields from fixture", () => {
  // Authority receipt hashes are persisted under authority/ namespace
  // and referenced via session state.  Browser tests verify that the
  // hash fields present in the response contract are consumable.
  const fixture = {
    ok: true,
    outcome: { kind: "candidate" },
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
      graph_hash: "candidate-graph-hash",
      submit_graph_hash: "submit-graph-hash",
    },
    candidate_graph_hash: "candidate-graph-hash",
    submit_graph_hash: "submit-graph-hash",
    idempotency_key: "idem-auth-001",
    accepted_batch: [
      { op: { op: "set_node_field", target: ["", "n", "w"], value: 1 } },
    ],
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      message: "Ready.",
      warnings: [],
    },
  };

  const envelope = readDeltaEnvelope(fixture);
  assert.equal(envelope.schema_version, "2.0.0");
  assert.equal(envelope.ops.length, 1);
  assert.equal(readIdempotencyKey(fixture), "idem-auth-001");

  const normalized = normalizeAgentEditResponse(fixture, { endpoint: "/submit" });
  assert.equal(normalized.outcome.kind, "candidate");
  assert.equal(normalized.candidateGraphHash, "candidate-graph-hash");
  assert.equal(normalized.submitGraphHash, "submit-graph-hash");
});

// ── Malformed delta evidence in response fixtures ───────────────────────

test("readDeltaEnvelope returns null for archived delta_ops_envelope without accepted_batch", () => {
  const envelope = readDeltaEnvelope({
    delta_ops_envelope: { ops: [] },
  });
  assert.equal(envelope, null);
});

test("readDeltaEnvelope returns null for archived envelope with null ops", () => {
  const envelope = readDeltaEnvelope({
    delta_ops_envelope: { schema_version: "2.0.0", ops: null },
  });
  assert.equal(envelope, null);
});

test("normalizeAgentEditResponse does not crash on malformed delta evidence in debug", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate" },
    candidate: { graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] } },
    candidate_graph_hash: "gh",
    apply_eligibility: { applyable: true, reason: "applyable", message: "ok", warnings: [] },
    debug: {
      delta_evidence: {
        delta_evidence_valid: false,
        delta_evidence_code: "corrupted_delta",
        delta_evidence_detail: { reason: "truncated envelope" },
      },
    },
  };

  // Must not throw — malformed evidence is diagnostic, not fatal to normalization.
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(normalized.outcome.kind, "candidate");
  assert.ok(normalized.debug, "debug must be preserved");
});

// ── Cumulative delta across batch turns ─────────────────────────────────

test("readDeltaEnvelope reads cumulative multi-turn delta from accepted_batch", () => {
  const fixture = {
    ok: true,
    outcome: { kind: "candidate" },
    accepted_batch: [
      { op: { op: "set_node_field", target: ["", "n1", "widgets.seed"], value: 42 } },
      { op: { op: "set_mode", target: ["", "n2"], mode: 4 } },
      { op: { op: "add_node", scope_path: "", uid: "n3", node_id: "3", class_type: "SaveImage", fields: {}, inputs: {} } },
      { op: { op: "upsert_link", from: ["", "n1", "IMAGE"], to: ["", "n3", "images"] } },
    ],
  };

  const envelope = readDeltaEnvelope(fixture);
  assert.ok(envelope);
  assert.equal(envelope.schema_version, "2.0.0");
  assert.equal(envelope.ops.length, 4);
  // Verify ops are in order (cumulative across turns).
  assert.equal(envelope.ops[0].op, "set_node_field");
  assert.equal(envelope.ops[2].op, "add_node");
});

// ── Idempotency key in durable executor responses ───────────────────────

test("normalizeAgentEditResponse surfaces idempotency key from turn identity", () => {
  const raw = {
    ok: true,
    outcome: { kind: "candidate", changes: [] },
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
      turn_identity: {
        session_id: "sess-1",
        turn_id: "turn-1",
        idempotency_key: "idem-durable-001",
      },
    },
    apply_eligibility: { applyable: true, reason: "applyable", message: "Ready.", warnings: [] },
    idempotency_key: "idem-durable-001",
  };

  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/submit" });
  assert.equal(readIdempotencyKey(normalized.raw), "idem-durable-001");
  assert.equal(normalized.turnIdentity?.idempotencyKey, "idem-durable-001");
});

test("terminal authority rejection remains typed and non-applyable in browser projection", () => {
  const normalized = normalizeAgentEditResponse({
    ok: false,
    route: "revise",
    terminal_state: "authority_rejected",
    terminal_reason: "authority_replay_mismatch",
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      replay_ok: false,
      candidate_matches: false,
      candidate_hash: "rejected-hash",
    },
    candidate_transaction: makeValidCandidateTransactionV2({
      sessionId: "s",
      turnId: "t",
      planHash: "rejected-plan",
    }),
    candidate: { graph: { nodes: [{ id: 1 }], links: [] } },
    candidate_graph: { nodes: [{ id: 1 }], links: [] },
    report: { nested: { candidateGraph: { forged: true } } },
    evidence: { nested: { acceptedDelta: [{ forged: true }] } },
    failure: { nested: { candidateTransaction: { forged: true } } },
    apply_eligible: true,
    apply_allowed: true,
    canvas_apply_allowed: true,
    queue_allowed: true,
    outcome: { kind: "candidate" },
  }, { endpoint: "/submit" });

  assert.equal(normalized.terminalState, "authority_rejected");
  assert.equal(normalized.terminalReason, "authority_replay_mismatch");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.candidate, null);
  assert.equal(normalized.outcome.kind, "error");
  assert.equal(normalized.applyEligible, false);
  assert.equal(normalized.eligibility.applyable, false);
  assert.equal(normalized.candidateTransaction, null);
  assert.equal(normalized.raw.candidateTransaction, undefined);
  assert.deepEqual(normalized.report, { nested: {} });
  assert.deepEqual(normalized.evidence, { nested: {} });
  assert.deepEqual(normalized.raw.failure, { nested: {} });
  assert.equal(normalized.authorityReceipt.candidate_hash, "rejected-hash");
});

test("browser projection demotes an applied terminal with an unbound receipt", () => {
  const graph = { nodes: [{ id: 1 }], links: [] };
  const normalized = normalizeAgentEditResponse({
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    accepted_batch: [],
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: "0".repeat(64),
      accepted_batch_digest: "1".repeat(64),
      cumulative_delta_hash: "1".repeat(64),
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
      op_count: 1,
    },
  }, { endpoint: "/submit" });

  assert.equal(normalized.terminalState, "undetermined");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.outcome.kind, "error");
  assert.equal(normalized.applyEligible, false);
});

test("browser projection rejects replay-derived candidate hash and error contradictions", () => {
  const graph = { nodes: [{ id: 1 }], links: [] };
  const normalized = normalizeAgentEditResponse({
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    accepted_batch: [{ op: { op: "set_node_field" } }],
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: "0".repeat(64),
      accepted_batch_digest: "1".repeat(64),
      cumulative_delta_hash: "1".repeat(64),
      replay_ok: true,
      candidate_matches: true,
      replay: {
        replay_ok: true,
        candidate_matches: true,
        verification_kind: "delta_replay",
        op_count: 1,
        error: "tampered",
        persisted_candidate_hash: "b".repeat(64),
        recomputed_candidate_hash: "b".repeat(64),
      },
    },
  });
  assert.equal(normalized.terminalState, "undetermined");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.applyEligible, false);
});

test("browser projection rejects camelCase hash and conflicting graph carriers", () => {
  const graph = { nodes: [{ id: 1 }], links: [] };
  const otherGraph = { nodes: [{ id: 2 }], links: [] };
  const normalized = normalizeAgentEditResponse({
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    graph: otherGraph,
    candidateGraphHash: "b".repeat(64),
    accepted_batch: [{ op: { op: "set_node_field" } }],
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: "0".repeat(64),
      accepted_batch_digest: "1".repeat(64),
      cumulative_delta_hash: "1".repeat(64),
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
      op_count: 1,
    },
  });
  assert.equal(normalized.terminalState, "undetermined");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.applyEligible, false);
});

test("browser projection rejects non-object applied graph carriers", () => {
  const graph = { nodes: [{ id: 1 }], links: [] };
  const acceptedBatch = [{ op: { op: "set_node_field" } }];
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: acceptedBatch }));
  const receipt = {
    contract_version: "authority_receipt_v2",
    schema_version: "2.0.0",
    session_id: "s",
    turn_id: "t",
    submit_graph_hash: "a".repeat(64),
    candidate_hash: sha256Hex(graph),
    accepted_batch_digest: deltaDigest,
    cumulative_delta_hash: deltaDigest,
    replay_ok: true,
    candidate_matches: true,
    verification_kind: "delta_replay",
    op_count: 1,
  };
  for (const malformed of [
    { graph: "forged" },
    { candidateTransaction: { graph: "bad" } },
    { candidate: "bad" },
  ]) {
    const normalized = normalizeAgentEditResponse({
      ok: true,
      route: "revise",
      terminal_state: "applied",
      session_id: "s",
      turn_id: "t",
      candidate: { graph },
      accepted_batch: acceptedBatch,
      outcome: { kind: "candidate" },
      apply_eligible: true,
      authority_receipt: receipt,
      ...malformed,
    });
    assert.equal(normalized.terminalState, "undetermined");
    assert.equal(normalized.candidateGraph, null);
    assert.equal(normalized.applyEligible, false);
    assert.equal(normalized.outcome.kind, "error");
  }
});

test("browser projection rejects a conflicting acceptedBatch alias", () => {
  const graph = { nodes: [{ id: 1 }], links: [] };
  const acceptedBatch = [{ op: { op: "set_node_field" } }];
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: acceptedBatch }));
  const normalized = normalizeAgentEditResponse({
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    accepted_batch: acceptedBatch,
    acceptedBatch: [{ op: { op: "forged" } }],
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: sha256Hex(graph),
      authority_receipt_digest: "a".repeat(64),
      accepted_batch_digest: deltaDigest,
      cumulative_delta_hash: deltaDigest,
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
      op_count: 1,
    },
  });
  assert.equal(normalized.terminalState, "undetermined");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.applyEligible, false);
  assert.equal(normalized.outcome.kind, "error");
});

test("browser projection validates structural graph hash aliases against the graph", () => {
  const graph = {
    nodes: [{ id: 1, type: "KSampler", vibecomfy_uid: "n1", inputs: [], outputs: [] }],
    links: [],
  };
  const acceptedBatch = [{ op: { op: "set_node_field" } }];
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: acceptedBatch }));
  const normalized = normalizeAgentEditResponse({
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    accepted_batch: acceptedBatch,
    candidateStructuralGraphHash: "f".repeat(64),
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: sha256Hex(graph),
      authority_receipt_digest: "a".repeat(64),
      accepted_batch_digest: deltaDigest,
      cumulative_delta_hash: deltaDigest,
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
      op_count: 1,
    },
  });
  assert.equal(normalized.terminalState, "undetermined");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.applyEligible, false);
});

test("browser terminal alias matrix rejects unbound applied aliases", () => {
  const graph = { nodes: [{ id: 1 }], links: [] };
  const acceptedBatch = [{ op: { op: "set_node_field" } }];
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: acceptedBatch }));
  const base = {
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    accepted_batch: acceptedBatch,
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: sha256Hex(graph),
      accepted_batch_digest: deltaDigest,
      cumulative_delta_hash: deltaDigest,
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
      op_count: 1,
    },
  };
  const aliases = [
    ["candidate_hash", "b".repeat(64)],
    ["candidateHash", "b".repeat(64)],
    ["accepted_delta", [{ op: { op: "forged" } }]],
    ["acceptedDelta", [{ op: { op: "forged" } }]],
    ["delta", [{ op: { op: "forged" } }]],
    ["candidateTransaction", { state: "candidate" }],
    ["candidate_transaction", { state: "candidate" }],
    ["candidateTransaction", { graph: { nodes: [] } }],
    ["applyAllowed", false],
    ["canvasApplyAllowed", false],
    ["queueAllowed", false],
    ["applyEligibility", { applyable: false }],
  ];
  for (const [key, value] of aliases) {
    const normalized = normalizeAgentEditResponse({ ...base, [key]: value });
    assert.equal(normalized.terminalState, "undetermined", key);
    assert.equal(normalized.candidateGraph, null, key);
    assert.equal(normalized.applyEligible, false, key);
    assert.equal(normalized.outcome.kind, "error", key);
  }
});

test("browser accepts a valid graphless candidate_transaction_v2 aggregate", () => {
  const graph = { nodes: [], links: [] };
  const transaction = makeValidCandidateTransactionV2({
    sessionId: "s",
    turnId: "t",
    planHash: "plan-v2",
    family: "layout",
    verificationKind: "layout_structural_noop",
  });
  const identitySeed = "s:t:plan-v2";
  transaction.candidate_authority.transaction_id = sha256HexFromString(`${identitySeed}:transaction`);
  transaction.candidate_authority.candidate_id = sha256HexFromString(`${identitySeed}:candidate`);
  transaction.hashes.candidate_graph_hash = sha256Hex(graph);
  transaction.hashes.candidate_structural_graph_hash = sha256HexFromString(structuralGraphProjectionJson(graph));
  transaction.hashes.submit_graph_hash = "a".repeat(64);
  transaction.hashes.candidate_layout_graph_hash = sha256Hex(buildLayoutGraphProjection(graph));
  const acceptedBatch = [];
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: acceptedBatch }));
  const workflowId = "123e4567-e89b-12d3-a456-426614174000";
  const normalized = normalizeAgentEditResponse({
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    candidate_transaction: transaction,
    workflow_id: workflowId,
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: sha256Hex(graph),
      authority_receipt_digest: "c".repeat(64),
      accepted_batch_digest: deltaDigest,
      cumulative_delta_hash: deltaDigest,
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "layout_structural_noop",
      op_count: 0,
    },
  });
  assert.equal(normalized.terminalState, "applied");
  assert.ok(normalized.candidateTransaction);
  assert.equal(normalized.applyEligible, true);
  assert.deepEqual(normalized.raw.accepted_batch, acceptedBatch);
});

test("browser binds layout postcondition and graph hash to the published candidate", () => {
  const preconditionGraph = {
    nodes: [{ id: 1, vibecomfy_uid: "node-1", type: "PreviewImage", pos: [0, 0], size: [200, 100] }],
    links: [],
  };
  const graph = {
    nodes: [{ id: 1, vibecomfy_uid: "node-1", type: "PreviewImage", pos: [300, 100], size: [200, 100] }],
    links: [],
  };
  const transaction = makeValidCandidateTransactionV2({
    sessionId: "s",
    turnId: "t",
    planHash: "layout-plan",
    family: "layout",
    verificationKind: "layout_structural_noop",
    preconditionGraph,
    postconditionGraph: graph,
  });
  const identitySeed = "s:t:layout-plan";
  transaction.candidate_authority.transaction_id = sha256HexFromString(`${identitySeed}:transaction`);
  transaction.candidate_authority.candidate_id = sha256HexFromString(`${identitySeed}:candidate`);
  transaction.hashes.candidate_graph_hash = sha256Hex(graph);
  transaction.hashes.candidate_structural_graph_hash = sha256HexFromString(structuralGraphProjectionJson(graph));
  transaction.hashes.submit_graph_hash = "a".repeat(64);
  const layoutHash = sha256Hex(buildLayoutGraphProjection(graph));
  transaction.hashes.candidate_layout_graph_hash = layoutHash;
  transaction.authority.layout_verification = {
    contract_version: "layout_verification_v1",
    projection: "browser_layout_v1",
    candidate_layout_graph_hash: layoutHash,
  };
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: [] }));
  const base = {
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    candidate_transaction: transaction,
    workflow_id: "123e4567-e89b-12d3-a456-426614174000",
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: sha256Hex(graph),
      authority_receipt_digest: "c".repeat(64),
      accepted_batch_digest: deltaDigest,
      cumulative_delta_hash: deltaDigest,
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "layout_structural_noop",
      op_count: 0,
    },
  };
  const valid = normalizeAgentEditResponse(structuredClone(base));
  assert.equal(valid.terminalState, "applied");
  assert.equal(valid.applyEligible, true);

  const forgedPostcondition = structuredClone(base);
  forgedPostcondition.candidate_transaction.candidate_authority.postcondition =
    forgedPostcondition.candidate_transaction.candidate_authority.precondition;
  let normalized = normalizeAgentEditResponse(forgedPostcondition);
  assert.equal(normalized.terminalState, "undetermined");
  assert.equal(normalized.applyEligible, false);
  assert.equal(normalized.candidateGraph, null);

  const forgedLayout = structuredClone(base);
  forgedLayout.candidate_transaction.hashes.candidate_layout_graph_hash = "f".repeat(64);
  forgedLayout.candidate_transaction.authority.layout_verification.candidate_layout_graph_hash = "f".repeat(64);
  normalized = normalizeAgentEditResponse(forgedLayout);
  assert.equal(normalized.terminalState, "undetermined");
  assert.equal(normalized.applyEligible, false);
  assert.equal(normalized.candidateGraph, null);
});

test("browser binds transaction hash and identity and rejects conflicting aliases", () => {
  const graph = { nodes: [], links: [] };
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: [] }));
  const workflowId = "123e4567-e89b-12d3-a456-426614174000";
  const baseReceipt = {
    contract_version: "authority_receipt_v2",
    schema_version: "2.0.0",
    session_id: "s",
    turn_id: "t",
    submit_graph_hash: "a".repeat(64),
    candidate_hash: sha256Hex(graph),
    authority_receipt_digest: "c".repeat(64),
    accepted_batch_digest: deltaDigest,
    cumulative_delta_hash: deltaDigest,
    replay_ok: true,
    candidate_matches: true,
    verification_kind: "layout_structural_noop",
    op_count: 0,
  };
  const validTransaction = () => {
    const transaction = makeValidCandidateTransactionV2({
      sessionId: "s",
      turnId: "t",
      planHash: "plan-v2",
      family: "layout",
      verificationKind: "layout_structural_noop",
    });
    const identitySeed = "s:t:plan-v2";
    transaction.candidate_authority.transaction_id = sha256HexFromString(`${identitySeed}:transaction`);
    transaction.candidate_authority.candidate_id = sha256HexFromString(`${identitySeed}:candidate`);
    transaction.hashes.candidate_graph_hash = sha256Hex(graph);
    transaction.hashes.candidate_structural_graph_hash = sha256HexFromString(structuralGraphProjectionJson(graph));
    transaction.hashes.submit_graph_hash = "a".repeat(64);
    return transaction;
  };
  const normalize = (transaction, aliases = {}, receipt = baseReceipt) => normalizeAgentEditResponse({
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    candidate_transaction: transaction,
    workflow_id: workflowId,
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: receipt,
    ...aliases,
  });

  for (const [index, mutate] of [
    (transaction) => { transaction.hashes.candidate_graph_hash = "f".repeat(64); },
    (transaction) => {
      transaction.session_id = "other";
      transaction.candidate_authority.session_id = "other";
    },
    (transaction) => {
      transaction.turn_id = "other";
      transaction.candidate_authority.turn_id = "other";
    },
    (transaction) => { transaction.candidate_authority.candidate_id = "forged"; },
    (transaction) => { transaction.candidate_authority.transaction_id = "forged"; },
    (transaction) => { transaction.plan_hash = "other-plan"; },
    (transaction) => { transaction.candidate_authority.plan_hash = "other-plan"; },
    (transaction) => { transaction.candidate_authority.workflow_id = "123e4567-e89b-12d3-a456-426614174001"; },
    (transaction) => { transaction.authority.replay_ok = false; },
    (transaction) => { transaction.authority.candidate_matches = false; },
    (transaction) => { transaction.authority.verification_kind = "delta_replay"; },
    (transaction) => { transaction.candidate_authority.authority_receipt_digest = "d".repeat(64); },
    (transaction) => { transaction.hashes.authority_receipt_hash = "d".repeat(64); },
    (transaction) => { transaction.hashes.candidate_structural_graph_hash = "d".repeat(64); },
    (transaction) => { transaction.hashes.submit_graph_hash = "d".repeat(64); },
  ].entries()) {
    const transaction = validTransaction();
    mutate(transaction);
    const normalized = normalize(transaction);
    assert.equal(normalized.terminalState, "undetermined", `mutation ${index}`);
    assert.equal(normalized.candidateGraph, null, `mutation ${index}`);
    assert.equal(normalized.applyEligible, false, `mutation ${index}`);
  }

  const receiptMismatch = normalize(validTransaction(), {}, {
    ...baseReceipt,
    candidate_hash: "e".repeat(64),
  });
  assert.equal(receiptMismatch.terminalState, "undetermined");
  assert.equal(receiptMismatch.candidateGraph, null);
  assert.equal(receiptMismatch.applyEligible, false);

  const first = validTransaction();
  const second = structuredClone(first);
  second.plan_hash = "other-plan";
  second.candidate_authority.plan_hash = "other-plan";
  const otherIdentitySeed = "s:t:other-plan";
  second.candidate_authority.transaction_id = sha256HexFromString(`${otherIdentitySeed}:transaction`);
  second.candidate_authority.candidate_id = sha256HexFromString(`${otherIdentitySeed}:candidate`);
  const conflicting = normalize(first, {
    candidate_transaction: first,
    candidateTransaction: second,
  });
  assert.equal(conflicting.terminalState, "undetermined");
  assert.equal(conflicting.candidateGraph, null);
  assert.equal(conflicting.applyEligible, false);
});

test("browser terminal rejects non-hex receipt hash shapes", () => {
  const graph = { nodes: [{ id: 1 }], links: [] };
  const acceptedBatch = [{ op: { op: "set_node_field" } }];
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: acceptedBatch }));
  const normalized = normalizeAgentEditResponse({
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    accepted_batch: acceptedBatch,
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "G".repeat(64),
      candidate_hash: sha256Hex(graph),
      accepted_batch_digest: deltaDigest,
      cumulative_delta_hash: deltaDigest,
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
      op_count: 1,
    },
  });
  assert.equal(normalized.terminalState, "undetermined");
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.applyEligible, false);
});

test("browser applied terminal requires a bound authority receipt digest without transaction", () => {
  const graph = { nodes: [{ id: 1 }], links: [] };
  const acceptedBatch = [{ op: { op: "set_node_field" } }];
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: acceptedBatch }));
  const base = {
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    accepted_batch: acceptedBatch,
    outcome: { kind: "candidate" },
    apply_eligible: true,
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: sha256Hex(graph),
      accepted_batch_digest: deltaDigest,
      cumulative_delta_hash: deltaDigest,
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
      op_count: 1,
      authority_receipt_digest: "a".repeat(64),
    },
  };
  const valid = normalizeAgentEditResponse(structuredClone(base));
  assert.equal(valid.terminalState, "applied");
  assert.equal(valid.applyEligible, true);
  assert.equal(valid.raw.authority_receipt.authority_receipt_digest, "a".repeat(64));

  for (const malformed of [null, 1, "ABC", "x", "a".repeat(63), "a".repeat(65)]) {
    const payload = structuredClone(base);
    payload.authority_receipt.authority_receipt_digest = malformed;
    const normalized = normalizeAgentEditResponse(payload);
    assert.equal(normalized.terminalState, "undetermined");
    assert.equal(normalized.applyEligible, false);
    assert.equal(normalized.candidateGraph, null);
    assert.equal(normalized.outcome.kind, "error");
  }

  const omitted = structuredClone(base);
  delete omitted.authority_receipt.authority_receipt_digest;
  const normalized = normalizeAgentEditResponse(omitted);
  assert.equal(normalized.terminalState, "undetermined");
  assert.equal(normalized.applyEligible, false);
  assert.equal(normalized.candidateGraph, null);
  assert.equal(normalized.outcome.kind, "error");
});

test("browser terminal alias matrix binds acceptedBatch alone and scrubs nested products", () => {
  const graph = { nodes: [{ id: 1 }], links: [] };
  const acceptedBatch = [{ op: { op: "set_node_field" } }];
  const deltaDigest = sha256Hex(readDeltaEnvelope({ accepted_batch: acceptedBatch }));
  const normalized = normalizeAgentEditResponse({
    ok: true,
    route: "revise",
    terminal_state: "applied",
    session_id: "s",
    turn_id: "t",
    candidate: { graph },
    acceptedBatch,
    outcome: { kind: "candidate" },
    apply_eligible: true,
    report: { nested: { candidateHash: "forged" } },
    evidence: { nested: { accepted_delta: [{ bad: true }] } },
    failure: { nested: { delta: [{ bad: true }] } },
    authority_receipt: {
      contract_version: "authority_receipt_v2",
      schema_version: "2.0.0",
      session_id: "s",
      turn_id: "t",
      submit_graph_hash: "a".repeat(64),
      candidate_hash: sha256Hex(graph),
      authority_receipt_digest: "a".repeat(64),
      accepted_batch_digest: deltaDigest,
      cumulative_delta_hash: deltaDigest,
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
      op_count: 1,
    },
  });
  assert.equal(normalized.terminalState, "applied");
  assert.deepEqual(normalized.raw.accepted_batch, acceptedBatch);
  assert.equal(normalized.raw.acceptedBatch, undefined);
  assert.deepEqual(normalized.raw.report, { nested: {} });
  assert.deepEqual(normalized.evidence, { nested: {} });
  assert.deepEqual(normalized.raw.failure, { nested: {} });
  assert.equal(normalized.applyEligible, true);
});
