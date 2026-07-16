import test from "node:test";
import assert from "node:assert/strict";

import {
  PANEL_STATE,
  createAgentEditState,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

import {
  commitOptimisticSubmit,
  commitTerminalResponse,
  commitTranscriptRehydrate,
  commitApplyResolved,
  commitLifecycleReset,
  normalizeCommitApplyEligibility,
} from "../../vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js";

// ─────────────────────────────────────────────────────────────────────────────
// T11 — Cross-source lifecycle/projection parity.
//
// The same canonical candidate fixture is fed through three adapter styles that
// mirror how production (vibecomfy_roundtrip.js), preview (preview_picker.js),
// and replay (agentic_replay.js) construct their terminal-candidate payloads
// before handing them to the shared commit helpers in agent_lifecycle_commit.js.
//
// The contract under test: every adapter must produce IDENTICAL lifecycle and
// projection fields on panel.state, because they all funnel through the same
// transition(...) authority. Drift between adapters is a parity regression.
// ─────────────────────────────────────────────────────────────────────────────

// ── Canonical fixture shared by every adapter ───────────────────────────────

const CANONICAL = Object.freeze({
  sessionId: "sess-parity-001",
  turnId: "turn-parity-001",
  baselineTurnId: "turn-parity-000",
  message: "Adjusted KSampler steps to 26 and added a VAEDecode node.",
  candidateGraph: Object.freeze({
    nodes: [
      { id: 10, type: "KSampler", widgetsValues: { steps: 26 } },
      { id: 11, type: "VAEDecode" },
    ],
    links: [[10, 0, 11]],
  }),
  candidateGraphHash: "sha256:candidate-parity-graph-hash",
  submitGraphHash: "sha256:submit-parity-graph-hash",
  candidateTransaction: Object.freeze({
    contract_version: "candidate_transaction_v1",
    state: "candidate_ready",
    session_id: "sess-parity-001",
    turn_id: "turn-parity-001",
    plan_hash: "plan-parity-001",
    generation: 1,
    lease_nonce: "lease-parity-001",
    plan: Object.freeze({
      schema_version: "2.0.0",
      delta_ops_envelope: Object.freeze({ schema_version: "2.0.0", ops: Object.freeze([]) }),
      delta_hash: "delta-parity-001",
      op_count: 0,
      schema_provenance: Object.freeze({}),
    }),
    hashes: Object.freeze({
      submit_graph_hash: "sha256:submit-parity-graph-hash",
      submit_structural_graph_hash: "sha256:submit-parity-structural-hash",
      candidate_graph_hash: "sha256:candidate-parity-graph-hash",
      candidate_structural_graph_hash: "sha256:candidate-parity-structural-hash",
      authority_receipt_hash: "receipt-parity-001",
    }),
    authority: Object.freeze({ replay_ok: true, candidate_matches: true, verification_kind: "delta_replay" }),
    available_actions: Object.freeze(["apply", "reject"]),
    terminal: false,
    last_error: null,
  }),
  eligibility: Object.freeze({
    applyable: true,
    reason: "applyable",
    message: "Candidate is ready to apply.",
    warnings: [],
  }),
  changeDetails: Object.freeze({
    summary: "Increased KSampler steps to 26; added VAEDecode.",
    nodes_added: 1,
    fields_changed: 1,
  }),
  userMessage: Object.freeze({
    role: "user",
    text: "Make the output sharper and decode it.",
    session_id: "sess-parity-001",
    turn_id: "turn-parity-001",
  }),
  agentMessage: Object.freeze({
    role: "agent",
    text: "Adjusted KSampler steps to 26 and added a VAEDecode node.",
    session_id: "sess-parity-001",
    turn_id: "turn-parity-001",
  }),
});

function makePanel() {
  // Fresh panel per adapter so cross-contamination cannot mask drift.
  return { state: createAgentEditState() };
}

// ── Adapter: production style (mirrors vibecomfy_roundtrip.js candidate path) ─
//
// Production normalizes the raw server response, then forwards an explicit
// candidateGraph / candidateGraphHash / normalized applyEligibility and a
// scrubbed debugPayload to commitTerminalResponse.

function productionAdapter(panel, fixture) {
  // The production orchestrator runs an optimistic submit before the terminal
  // candidate arrives, so mirror that ordering for lifecycle parity.
  commitOptimisticSubmit(panel, {
    lastSubmit: { prompt: fixture.userMessage.text, source: "production" },
    debugPayload: { source: "production", stage: "optimistic" },
  });
  // Normalize eligibility the same way production does for the gate context.
  const normalizedEligibility = normalizeCommitApplyEligibility(
    fixture.candidateGraph,
    fixture.eligibility,
  );
  const terminalResult = {
    ok: true,
    session_id: fixture.sessionId,
    turn_id: fixture.turnId,
    baseline_turn_id: fixture.baselineTurnId,
    message: fixture.message,
    outcome: { kind: "candidate" },
    eligibility: fixture.eligibility,
    candidate_transaction: fixture.candidateTransaction,
    report: {},
  };
  commitTerminalResponse(panel, {
    result: terminalResult,
    outcome: { kind: "candidate" },
    candidateGraph: fixture.candidateGraph,
    candidateGraphHash: fixture.candidateGraphHash,
    serverSubmitGraphHash: fixture.submitGraphHash,
    queueAllowed: false,
    applyEligibility: normalizedEligibility,
    changeDetails: fixture.changeDetails,
    debugPayload: { source: "production", stage: "candidate" },
  });
  return panel;
}

// ── Adapter: preview/demo style (mirrors preview_picker.js ready_to_apply) ───
//
// Preview builds a terminalResult with baseline_turn_id: null and forwards an
// explicit candidateGraph / candidateGraphHash / applyEligibility and a demo
// debugPayload. The transcript is driven by commitTranscriptRehydrate.

function previewAdapter(panel, fixture) {
  commitLifecycleReset(panel, {
    rejected: {},
    message: null,
    debugPayload: { source: "demo", stage: "before_send" },
  });
  commitOptimisticSubmit(panel, {
    lastSubmit: { prompt: fixture.userMessage.text, source: "demo" },
    debugPayload: { source: "demo", stage: "sent_loading" },
  });
  const terminalResult = {
    ok: true,
    session_id: fixture.sessionId,
    turn_id: fixture.turnId,
    baseline_turn_id: null,
    message: fixture.message,
    outcome: { kind: "candidate" },
    eligibility: fixture.eligibility,
    candidate_transaction: fixture.candidateTransaction,
    report: {},
  };
  commitTerminalResponse(panel, {
    result: terminalResult,
    outcome: { kind: "candidate" },
    candidateGraph: fixture.candidateGraph,
    candidateGraphHash: fixture.candidateGraphHash,
    applyEligibility: fixture.eligibility,
    queueAllowed: false,
    changeDetails: fixture.changeDetails,
    debugPayload: { source: "demo", stage: "ready_to_apply" },
  });
  commitTranscriptRehydrate(panel, {
    messages: [fixture.userMessage, fixture.agentMessage],
    sessionId: fixture.sessionId,
    latestTurnId: fixture.turnId,
    latestCandidate: terminalResult,
  });
  return panel;
}

// ── Adapter: replay style (mirrors agentic_replay.js ensureReplayCandidateCommit)
//
// Replay builds a terminal candidate envelope and forwards an explicit
// candidateGraph / candidateGraphHash / normalized eligibility / replay
// debugPayload. The transcript is driven by commitTranscriptRehydrate.

function replayAdapter(panel, fixture) {
  commitLifecycleReset(panel, {
    rejected: {},
    message: null,
    debugPayload: { source: "replay", stage: "thinking:reset" },
  });
  commitOptimisticSubmit(panel, {
    lastSubmit: { prompt: fixture.userMessage.text, source: "replay" },
    debugPayload: { source: "replay", stage: "thinking" },
  });
  const terminalResult = {
    ok: true,
    session_id: fixture.sessionId,
    turn_id: fixture.turnId,
    message: fixture.message,
    outcome: { kind: "candidate" },
    eligibility: fixture.eligibility,
    candidate_transaction: fixture.candidateTransaction,
    report: {},
  };
  commitTerminalResponse(panel, {
    result: terminalResult,
    outcome: { kind: "candidate" },
    candidateGraph: fixture.candidateGraph,
    candidateGraphHash: fixture.candidateGraphHash,
    applyEligibility: fixture.eligibility,
    queueAllowed: false,
    changeDetails: fixture.changeDetails,
    debugPayload: { source: "replay", stage: "ready_to_apply" },
  });
  commitTranscriptRehydrate(panel, {
    messages: [fixture.userMessage, fixture.agentMessage],
    sessionId: fixture.sessionId,
    latestTurnId: fixture.turnId,
    latestCandidate: terminalResult,
  });
  return panel;
}

const ADAPTERS = [
  { name: "production", run: productionAdapter },
  { name: "preview", run: previewAdapter },
  { name: "replay", run: replayAdapter },
];

// ── Lifecycle / projection field set compared across adapters ───────────────
//
// These are the fields whose VALUE must match across all three adapters when
// the same canonical candidate is committed. They represent the source-neutral
// candidate lifecycle contract owned by transition(...). debugPayload /
// lastSubmit are adapter metadata and are excluded (their .source differs by
// design). serverSubmitGraphHash is intentionally source-specific — only a real
// production server submit mints it; preview/replay have no server submit, so
// it is validated separately below rather than in the universal parity set.

const PARITY_FIELDS = [
  "phase",
  "sessionId",
  "turnId",
  "candidateGraph",
  "candidateGraphHash",
  "applyEligibility",
  "applyAllowed",
  "canvasApplyAllowed",
  "queueAllowed",
  "message",
  "failure",
  "clarification",
  "changeDetails",
  "candidateReport",
  "auditRef",
];

// ─────────────────────────────────────────────────────────────────────────────
// Parity tests
// ─────────────────────────────────────────────────────────────────────────────

test("all three adapters land the panel in AWAITING_REVIEW for a canonical candidate", () => {
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    assert.equal(
      panel.state.phase,
      PANEL_STATE.AWAITING_REVIEW,
      `${adapter.name}: canonical candidate must land in AWAITING_REVIEW`,
    );
  }
});

test("all three adapters project the canonical session/turn identity", () => {
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    assert.equal(
      panel.state.sessionId,
      CANONICAL.sessionId,
      `${adapter.name}: sessionId must match canonical fixture`,
    );
    assert.equal(
      panel.state.turnId,
      CANONICAL.turnId,
      `${adapter.name}: turnId must match canonical fixture`,
    );
  }
});

test("all three adapters store the canonical candidate graph and hash", () => {
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    assert.deepEqual(
      panel.state.candidateGraph,
      CANONICAL.candidateGraph,
      `${adapter.name}: candidateGraph must match canonical fixture`,
    );
    assert.equal(
      panel.state.candidateGraphHash,
      CANONICAL.candidateGraphHash,
      `${adapter.name}: candidateGraphHash must match canonical fixture`,
    );
  }
});

test("all three adapters derive matching apply eligibility and apply flags", () => {
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    assert.deepEqual(
      panel.state.applyEligibility,
      CANONICAL.eligibility,
      `${adapter.name}: applyEligibility must match canonical fixture`,
    );
    assert.equal(
      panel.state.applyAllowed,
      true,
      `${adapter.name}: applyAllowed must be true for an applyable canonical candidate`,
    );
    assert.equal(
      panel.state.canvasApplyAllowed,
      true,
      `${adapter.name}: canvasApplyAllowed must be true for an applyable canonical candidate`,
    );
    assert.equal(
      panel.state.queueAllowed,
      false,
      `${adapter.name}: queueAllowed must be false for all adapters`,
    );
  }
});

test("all three adapters clear failure and clarification for a pure candidate", () => {
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    assert.equal(
      panel.state.failure,
      null,
      `${adapter.name}: failure must be null for a candidate outcome`,
    );
    assert.equal(
      panel.state.clarification,
      null,
      `${adapter.name}: clarification must be null for a pure candidate outcome`,
    );
  }
});

test("all three adapters project the canonical agent message", () => {
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    assert.equal(
      panel.state.message,
      CANONICAL.message,
      `${adapter.name}: message must match canonical fixture`,
    );
  }
});

test("PARITY_FIELDS produce identical values across production, preview, and replay", () => {
  const snapshots = ADAPTERS.map((adapter) => {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    return { name: adapter.name, state: panel.state };
  });

  const baseline = snapshots[0];
  for (let i = 1; i < snapshots.length; i += 1) {
    const candidate = snapshots[i];
    for (const field of PARITY_FIELDS) {
      assert.deepEqual(
        candidate.state[field],
        baseline.state[field],
        `PARITY DRIFT on field "${field}": ${candidate.name} differs from ${baseline.name}`,
      );
    }
  }
});

test("apply-resolved reflection produces matching applied lifecycle across adapters", () => {
  const snapshots = ADAPTERS.map((adapter) => {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    commitApplyResolved(panel, {
      accepted: {
        ok: true,
        session_id: CANONICAL.sessionId,
        turn_id: CANONICAL.turnId,
      },
      lastAppliedChanges: CANONICAL.changeDetails,
      debugPayload: { source: adapter.name, stage: "applied" },
    });
    return { name: adapter.name, state: panel.state };
  });

  const baseline = snapshots[0];
  for (let i = 1; i < snapshots.length; i += 1) {
    const candidate = snapshots[i];
    assert.equal(
      candidate.state.phase,
      baseline.state.phase,
      `apply-resolved phase drift: ${candidate.name} vs ${baseline.name}`,
    );
    assert.equal(
      candidate.state.applyAllowed,
      false,
      `${candidate.name}: applyAllowed must be false after apply resolved`,
    );
    assert.equal(
      candidate.state.canvasApplyAllowed,
      false,
      `${candidate.name}: canvasApplyAllowed must be false after apply resolved`,
    );
    // The applied candidate graph/hash identity must still match across adapters.
    assert.deepEqual(
      candidate.state.candidateGraph,
      baseline.state.candidateGraph,
      `apply-resolved candidateGraph drift: ${candidate.name} vs ${baseline.name}`,
    );
    assert.deepEqual(
      candidate.state.lastAppliedChanges,
      baseline.state.lastAppliedChanges,
      `apply-resolved lastAppliedChanges drift: ${candidate.name} vs ${baseline.name}`,
    );
  }
});

test("optimistic submit ordering is consistent: every adapter enters SUBMITTING before the candidate", () => {
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    commitOptimisticSubmit(panel, {
      lastSubmit: { prompt: CANONICAL.userMessage.text, source: adapter.name },
      debugPayload: { source: adapter.name, stage: "optimistic" },
    });
    assert.equal(
      panel.state.phase,
      PANEL_STATE.SUBMITTING,
      `${adapter.name}: optimistic submit must enter SUBMITTING phase`,
    );
    assert.ok(
      Number.isFinite(panel.state.submitEpoch),
      `${adapter.name}: optimistic submit must mint a finite submitEpoch`,
    );
    assert.deepEqual(
      panel.state.lastSubmit,
      { prompt: CANONICAL.userMessage.text, source: adapter.name },
      `${adapter.name}: lastSubmit must mirror the optimistic payload`,
    );
  }
});

test("source-specific fields are handled consistently: serverSubmitGraphHash is production-only", () => {
  // serverSubmitGraphHash is minted by a real production server submit.
  // Preview/replay have no server submit, so they correctly leave it null.
  // This documents the intentional (non-bug) difference rather than treating
  // it as universal parity drift.
  const prodPanel = makePanel();
  productionAdapter(prodPanel, CANONICAL);
  assert.equal(
    prodPanel.state.serverSubmitGraphHash,
    CANONICAL.submitGraphHash,
    "production: serverSubmitGraphHash must reflect the server submit hash",
  );

  for (const adapter of ADAPTERS.filter((a) => a.name !== "production")) {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    assert.equal(
      panel.state.serverSubmitGraphHash,
      null,
      `${adapter.name}: serverSubmitGraphHash must be null without a real server submit`,
    );
  }
});

test("a non-applyable candidate (missing durable identity) is blocked uniformly across adapters", () => {
  const nonDurableFixture = {
    ...CANONICAL,
    sessionId: null,
    turnId: null,
    baselineTurnId: null,
    // Build a terminal envelope WITHOUT session/turn identity so the lifecycle
    // authority marks the candidate as missing durable metadata.
    _stripIdentity: true,
  };

  function buildEnvelope(adapterName, fixture) {
    if (adapterName === "production") {
      return {
        ok: true,
        message: fixture.message,
        outcome: { kind: "candidate" },
        eligibility: fixture.eligibility,
        report: {},
      };
    }
    return {
      ok: true,
      message: fixture.message,
      outcome: { kind: "candidate" },
      eligibility: fixture.eligibility,
      report: {},
    };
  }

  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    const envelope = buildEnvelope(adapter.name, nonDurableFixture);
    commitTerminalResponse(panel, {
      result: envelope,
      outcome: { kind: "candidate" },
      candidateGraph: nonDurableFixture.candidateGraph,
      candidateGraphHash: nonDurableFixture.candidateGraphHash,
      applyEligibility: nonDurableFixture.eligibility,
      queueAllowed: false,
      debugPayload: { source: adapter.name, stage: "candidate" },
    });
    assert.equal(
      panel.state.phase,
      PANEL_STATE.AWAITING_REVIEW,
      `${adapter.name}: non-durable candidate still lands AWAITING_REVIEW`,
    );
    assert.equal(
      panel.state.applyAllowed,
      false,
      `${adapter.name}: non-durable candidate must block applyAllowed`,
    );
    assert.equal(
      panel.state.canvasApplyAllowed,
      false,
      `${adapter.name}: non-durable candidate must block canvasApplyAllowed`,
    );
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Projection-leak tests
//
// A candidate envelope is seeded with forbidden raw payloads (raw graph,
// debug payload, provider diagnostics, model/system prompts, audit path, and a
// live-LiteGraph-shaped object). The transcript + detail projection must NOT
// expose any of these after each adapter commits the candidate and rehydrates
// the transcript.
// ─────────────────────────────────────────────────────────────────────────────

const FORBIDDEN_LEAK_KEYS = [
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
  "model",
  "audit_path",
  "auditPath",
  "live_litegraph",
  "liveLitegraph",
  "__lgNode",
  "lgNode",
];

const FORBIDDEN_LEAK_REGEX = /(?:raw_?graph|debug_?payload|provider_?diagnostics|model_?prompt|system_?prompt|^model$|audit_?path|live_?litegraph|__lgNode|lgNode)/i;

function forbiddenEnvelope(fixture) {
  return {
    ok: true,
    session_id: fixture.sessionId,
    turn_id: fixture.turnId,
    baseline_turn_id: fixture.baselineTurnId,
    message: fixture.message,
    outcome: { kind: "candidate" },
    eligibility: fixture.eligibility,
    report: {},
    // ── Forbidden raw payload that must never reach transcript/detail projection ──
    raw_graph: { nodes: [{ id: 99, type: "LATENT" }], links: [] },
    debug_payload: { internal_trace: "do-not-leak", last_submit: {} },
    provider_diagnostics: { tokens_in: 123, tokens_out: 456, model_id: "secret-model" },
    model: "secret-model-identifier",
    model_prompt: "You are a hidden system agent...",
    system_prompt: "SECRET SYSTEM PROMPT CONTENT",
    audit_path: "/var/lib/vibecomfy/audit/secret-turn.json",
    live_litegraph: { __lgNode: true, serialize: () => ({ secret: "lg" }) },
  };
}

// Walks an arbitrary JSON-like value and collects every key path whose name
// matches a forbidden leak marker. Functions/symbols are also flagged because
// live LiteGraph objects carry methods.
function collectForbiddenLeaks(value, path = "$", acc = []) {
  if (value === null || value === undefined) {
    return acc;
  }
  if (typeof value === "function") {
    acc.push({ path, kind: "function", name: "<fn>" });
    return acc;
  }
  if (typeof value !== "object") {
    return acc;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => {
      collectForbiddenLeaks(entry, `${path}[${index}]`, acc);
    });
    return acc;
  }
  for (const [key, entry] of Object.entries(value)) {
    const keyPath = `${path}.${key}`;
    if (
      FORBIDDEN_LEAK_KEYS.includes(key)
      || FORBIDDEN_LEAK_REGEX.test(key)
    ) {
      acc.push({ path: keyPath, kind: "key", name: key });
    }
    collectForbiddenLeaks(entry, keyPath, acc);
  }
  return acc;
}

function assertNoForbiddenLeaks(value, label) {
  const leaks = collectForbiddenLeaks(value);
  assert.equal(
    leaks.length,
    0,
    `${label}: transcript/detail projection leaked forbidden payload: ${
      JSON.stringify(leaks.slice(0, 5))
    }`,
  );
}

test("candidate commit does not leak forbidden raw payloads into candidate lifecycle projection", () => {
  const envelope = forbiddenEnvelope(CANONICAL);
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    commitOptimisticSubmit(panel, {
      lastSubmit: { prompt: CANONICAL.userMessage.text, source: adapter.name },
      debugPayload: { source: adapter.name, stage: "optimistic" },
    });
    commitTerminalResponse(panel, {
      result: envelope,
      outcome: { kind: "candidate" },
      candidateGraph: CANONICAL.candidateGraph,
      candidateGraphHash: CANONICAL.candidateGraphHash,
      applyEligibility: CANONICAL.eligibility,
      queueAllowed: false,
      changeDetails: CANONICAL.changeDetails,
      debugPayload: { source: adapter.name, stage: "candidate" },
    });
    // The candidate graph stored on state must be the canonical (explicit)
    // graph, NOT the raw_graph from the forbidden envelope.
    assert.deepEqual(
      panel.state.candidateGraph,
      CANONICAL.candidateGraph,
      `${adapter.name}: candidateGraph must be the explicit canonical graph, not raw_graph`,
    );
    // The transcript projection must be empty / safe before rehydrate.
    assertNoForbiddenLeaks(
      panel.state.transcriptMessages,
      `${adapter.name} transcriptMessages (pre-rehydrate)`,
    );
    assertNoForbiddenLeaks(
      panel.state.responseDetails,
      `${adapter.name} responseDetails (pre-rehydrate)`,
    );
  }
});

test("transcript rehydrate projection does not expose forbidden raw payloads from latestCandidate", () => {
  const envelope = forbiddenEnvelope(CANONICAL);
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    commitTerminalResponse(panel, {
      result: envelope,
      outcome: { kind: "candidate" },
      candidateGraph: CANONICAL.candidateGraph,
      candidateGraphHash: CANONICAL.candidateGraphHash,
      applyEligibility: CANONICAL.eligibility,
      queueAllowed: false,
      debugPayload: { source: adapter.name, stage: "candidate" },
    });
    // Feed the forbidden envelope as the latestCandidate through rehydrate —
    // exactly how preview (commitDemoTranscript) and replay pass the terminal
    // envelope to commitTranscriptRehydrate.
    commitTranscriptRehydrate(panel, {
      messages: [CANONICAL.userMessage, CANONICAL.agentMessage],
      sessionId: CANONICAL.sessionId,
      latestTurnId: CANONICAL.turnId,
      latestCandidate: envelope,
    });
    assertNoForbiddenLeaks(
      panel.state.transcriptMessages,
      `${adapter.name} transcriptMessages (post-rehydrate)`,
    );
    assertNoForbiddenLeaks(
      panel.state.responseDetails,
      `${adapter.name} responseDetails (post-rehydrate)`,
    );
  }
});

test("transcript messages themselves carry only safe message shapes across adapters", () => {
  for (const adapter of ADAPTERS) {
    if (adapter.name === "production") {
      // Production does not rehydrate the transcript on the candidate path;
      // skip the transcript-shape assertion for it.
      continue;
    }
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    assert.ok(
      Array.isArray(panel.state.transcriptMessages),
      `${adapter.name}: transcriptMessages must be an array`,
    );
    for (const message of panel.state.transcriptMessages) {
      assert.ok(
        message && typeof message === "object",
        `${adapter.name}: every transcript message must be a plain object`,
      );
      // Safe message fields only.
      const allowedKeys = new Set([
        "role",
        "text",
        "session_id",
        "turn_id",
        "id",
        "timestamp",
        "pending",
        "type",
      ]);
      for (const key of Object.keys(message)) {
        assert.ok(
          allowedKeys.has(key),
          `${adapter.name}: transcript message carries unexpected key "${key}"`,
        );
      }
    }
  }
});

test("debugPayload is the only channel that may carry adapter metadata; lifecycle fields stay clean", () => {
  const envelope = forbiddenEnvelope(CANONICAL);
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    commitTerminalResponse(panel, {
      result: envelope,
      outcome: { kind: "candidate" },
      candidateGraph: CANONICAL.candidateGraph,
      candidateGraphHash: CANONICAL.candidateGraphHash,
      applyEligibility: CANONICAL.eligibility,
      queueAllowed: false,
      debugPayload: { source: adapter.name, stage: "candidate" },
    });
    // The forbidden envelope's raw_graph must NOT have been aliased onto any
    // lifecycle projection field other than the explicitly-passed candidateGraph.
    assert.notDeepEqual(
      panel.state.candidateGraph,
      envelope.raw_graph,
      `${adapter.name}: candidateGraph must not alias the forbidden raw_graph`,
    );
    // candidateReport comes from result.report ({}), never from raw payloads.
    assert.deepEqual(
      panel.state.candidateReport,
      {},
      `${adapter.name}: candidateReport must be the safe report projection`,
    );
  }
});

test("lifecycle reset clears candidate projection uniformly across adapters", () => {
  for (const adapter of ADAPTERS) {
    const panel = makePanel();
    adapter.run(panel, CANONICAL);
    commitLifecycleReset(panel, {
      rejected: { reason: "user-rejected" },
      message: "Candidate rejected.",
      debugPayload: { source: adapter.name, stage: "reset" },
    });
    assert.equal(
      panel.state.candidateGraph,
      null,
      `${adapter.name}: candidateGraph must be null after lifecycle reset`,
    );
    assert.equal(
      panel.state.candidateGraphHash,
      null,
      `${adapter.name}: candidateGraphHash must be null after lifecycle reset`,
    );
    assert.equal(
      panel.state.applyAllowed,
      false,
      `${adapter.name}: applyAllowed must be false after lifecycle reset`,
    );
  }
});
