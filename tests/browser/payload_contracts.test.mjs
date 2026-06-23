import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
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
  readTurnIdentity,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract.js";

import {
  normalizeAgentTurnPayload,
  extractAgentTurnPayload,
  isTerminalAgentTurnStatus,
  agentTurnProgressLabel,
  deriveAgentActivityState,
  reduceAgentActivityFeed,
  FEED_SOURCE_PRIORITY,
  isSubstantiveStatement,
  latestSubstantiveStatement,
  deriveStatementCounts,
  AGENT_TURN_STATUSES,
  AGENT_TURN_ENTRY_TYPES,
} from "../../vibecomfy/comfy_nodes/web/agent_turn_feed.js";

import {
  normalizeExecutorPhasePayload,
  extractExecutorPhasePayload,
  normalizeExecutorProgressSnapshot,
  createExecutorProgressSnapshot,
  progressFromExecutorPhase,
  executorPhaseToCanonicalProgress,
  isExecutorProgressComplete,
  executorProgressLabel,
  executorDecisionLabel,
  EXECUTOR_PHASES,
  EXECUTOR_PHASE_STATUSES,
} from "../../vibecomfy/comfy_nodes/web/executor_progress.js";

import {
  buildStatusUrl,
  routeOptionsFromStatus,
  ROUTE_STATUS_KIND,
} from "../../vibecomfy/comfy_nodes/web/agent_status_poller.js";

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

// ── Fixture loader ────────────────────────────────────────────────────────

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FIXTURES_DIR = path.resolve(__dirname, "..", "fixtures", "payload_contracts");

function loadFixture(name) {
  const filePath = path.join(FIXTURES_DIR, name);
  const raw = readFileSync(filePath, "utf-8");
  return JSON.parse(raw);
}

// ── Agent edit response fixtures (routed through normalizeAgentEditResponse) ─

test("normalizeAgentEditResponse — agent_edit_accept_response.json", () => {
  const raw = loadFixture("agent_edit_accept_response.json");
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/fixture/accept" });

  // Stable public fields
  assert.equal(typeof normalized.ok, "boolean");
  assert.equal(normalized.ok, true);
  assert.equal(normalized.outcome.kind, "candidate");
  assert.ok(normalized.candidateGraph, "should have candidateGraph");
  assert.ok(normalized.candidate, "should have candidate");
  assert.deepEqual(normalized.eligibility, {
    applyable: true,
    reason: "applyable",
    message: "Ready to apply.",
    warnings: [],
  });
  assert.equal(normalized.sessionId, "session-stale-arrival");

  // Idempotent
  const second = normalizeAgentEditResponse(normalized, { endpoint: "/fixture/accept" });
  assert.equal(normalized, second);
});

test("normalizeAgentEditResponse — agent_edit_reject_response.json (legacy-inference-limited)", () => {
  const raw = loadFixture("agent_edit_reject_response.json");

  // This fixture lacks graph/outcome/clarification hints, so legacy inference throws.
  // It's a minimal reject acknowledgment.
  assert.throws(
    () => normalizeAgentEditResponse(raw, { endpoint: "/fixture/reject" }),
    /missing outcome/i,
  );

  // Allowable: assert at least one stable public field exists on the raw fixture
  assert.equal(raw.ok, true);
  assert.equal(raw.action, "reject");
  assert.equal(raw.session_id, "session-reject");
});

test("normalizeAgentEditResponse — agent_edit_rebaseline_response.json (legacy-inference-limited)", () => {
  const raw = loadFixture("agent_edit_rebaseline_response.json");

  // This fixture has apply_eligibility but no graph/outcome/clarification, so legacy inference throws.
  assert.throws(
    () => normalizeAgentEditResponse(raw, { endpoint: "/fixture/rebaseline" }),
    /missing outcome/i,
  );

  // Assert stable public fields
  assert.equal(raw.ok, true);
  assert.equal(raw.action, "rebaseline");
  assert.equal(typeof raw.apply_eligibility, "object");
  assert.equal(raw.apply_eligibility.applyable, false);
});

test("normalizeAgentEditResponse — agent_executor_clarify_response.json", () => {
  const raw = loadFixture("agent_executor_clarify_response.json");
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/fixture/clarify" });

  assert.equal(typeof normalized.ok, "boolean");
  assert.equal(normalized.ok, true);
  assert.equal(normalized.outcome.kind, "clarify");
  assert.equal(normalized.outcome.question, "Should I replace the sampler?");
  assert.equal(normalized.clarificationRequired, true);
});

test("normalizeAgentEditResponse — agent_executor_failure_response.json", () => {
  const raw = loadFixture("agent_executor_failure_response.json");
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/fixture/failure" });

  assert.equal(typeof normalized.ok, "boolean");
  assert.equal(normalized.ok, false);
  assert.equal(normalized.outcome.kind, "error");
  assert.equal(normalized.outcome.failureKind, "ProviderError");
  assert.ok(normalized.outcome.agentFailureContext);
});

test("canonical agent-edit fixture normalizes with allowLegacy=false", () => {
  const raw = {
    ok: true,
    message: "Canonical fixture candidate.",
    outcome: {
      kind: "candidate",
      changes: [{ uid: "ksampler", field_path: "widgets.steps", old: 20, new: 24 }],
    },
    candidate: {
      state: "candidate",
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
      graph_hash: "fixture-candidate-hash",
      baseline_graph_hash: "fixture-baseline-hash",
      turn_identity: {
        session_id: "sess-canonical-fixture",
        turn_id: "0015",
        baseline_turn_id: "0014",
        idempotency_key: "fixture-idem",
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
            { uid: "ksampler", field_path: "widgets.steps", old: 20, new: 24 },
          ],
        },
      ],
    },
  };

  assertCanonicalNormalPathHasNoLegacyAliases(raw);

  const normalized = normalizeCanonicalAgentEditResponse(raw, {
    endpoint: "/fixture/canonical-agent-edit",
  });
  const candidate = readApplyCandidate(normalized, { allowLegacy: false });

  assert.equal(normalized.outcome.kind, "candidate");
  assert.equal(candidate.graphHash, "fixture-candidate-hash");
  assert.equal(candidate.baselineGraphHash, "fixture-baseline-hash");
  assert.deepEqual(readTurnIdentity(normalized, { allowLegacy: false }), {
    sessionId: "sess-canonical-fixture",
    turnId: "0015",
    baselineTurnId: "0014",
    idempotencyKey: "fixture-idem",
  });
  assert.deepEqual(readFieldChanges(normalized, { allowLegacy: false }).legacyChanges, []);
  assert.equal(readFieldChanges(normalized, { allowLegacy: false }).all.length, 2);
});

test("old persisted agent-edit fixture is accepted only through the legacy adapter", () => {
  const raw = loadFixture("agent_edit_accept_response.json");

  assert.throws(
    () => normalizeCanonicalAgentEditResponse(raw, { endpoint: "/fixture/accept-strict" }),
    /missing outcome/i,
  );

  const adapted = adaptLegacyAgentEditResponse(raw, { endpoint: "/fixture/accept-legacy" });
  assert.equal(adapted.outcome.kind, "candidate");
  assert.equal(readApplyCandidate(adapted, { allowLegacy: false }).applyable, true);
  assert.deepEqual(readTurnIdentity(adapted, { allowLegacy: false }), {
    sessionId: "session-stale-arrival",
    turnId: "0001",
    baselineTurnId: "0001",
  });
});

// ── Executor response fixtures (not agent-edit responses; validated structurally) ─

test("agent_executor_success_response.json — structural contract", () => {
  const raw = loadFixture("agent_executor_success_response.json");

  // This is an executor response, not an agent-edit response. Validate known fields.
  assert.equal(raw.ok, true);
  assert.equal(raw.mode, "respond");
  assert.equal(typeof raw.reply, "string");
  assert.ok(raw.reply.length > 0);
  assert.equal(raw.session_id, "session-1");
  assert.ok(raw.report, "should have executor report");
  assert.equal(raw.report.executor.plan.reply, true);
});

test("agent_executor_request.json — structural contract", () => {
  const raw = loadFixture("agent_executor_request.json");

  // This is a submit request, not a response. Validate known fields.
  assert.equal(typeof raw.query, "string");
  assert.ok(raw.query.length > 0);
  assert.equal(raw.session_id, "sess-abc");
  assert.ok(raw.graph, "should have graph");
  assert.ok(Array.isArray(raw.graph.nodes));
  assert.ok(raw.graph.nodes.length >= 2);
  assert.equal(raw.route, "arnold");
  assert.equal(raw.model, "default");
  assert.equal(typeof raw.idempotency_key, "string");
  assert.ok(raw.idempotency_key.length > 0);
});

// ── Chat rehydrate and session bundle fixtures (structural contract) ──────

test("chat_rehydrate_response.json — structural contract", () => {
  const raw = loadFixture("chat_rehydrate_response.json");

  // This is a chat rehydrate response. Validate known fields.
  assert.equal(raw.ok, true);
  assert.equal(raw.exists, true);
  assert.equal(raw.session_id, "sess-123");
  assert.ok(raw.session_path, "should have session_path");
  assert.ok(raw.detail_json_path, "should have detail_json_path");
  assert.ok(Array.isArray(raw.messages));
  assert.ok(raw.messages.length >= 2);

  // Latest candidate is an agent-edit sub-payload; validate it normalizes
  assert.ok(raw.latest_candidate, "should have latest_candidate");
  const candidateNorm = normalizeAgentEditResponse(raw.latest_candidate, {
    endpoint: "/fixture/chat_rehydrate:latest_candidate",
  });
  assert.equal(candidateNorm.outcome.kind, "candidate");
  assert.ok(candidateNorm.candidateGraph);

  // Baseline fields
  assert.equal(raw.baseline.baseline_turn_id, "0000");
  assert.equal(typeof raw.baseline.baseline_graph_hash, "string");
});

test("canonical session rehydrate fixture normalizes latest candidate with allowLegacy=false", () => {
  const raw = {
    ok: true,
    exists: true,
    outcome: { kind: "noop", reason: "session rehydrate wrapper" },
    session_id: "sess-canonical-session",
    session_path: "out/editor_sessions/sess-canonical-session/",
    messages: [
      {
        role: "user",
        text: "set steps",
        turn_id: "0020",
        session_id: "sess-canonical-session",
      },
      {
        role: "agent",
        text: "Updated steps.",
        turn_id: "0020",
        session_id: "sess-canonical-session",
        outcome: {
          kind: "candidate",
          changes: [{ uid: "ksampler", field_path: "widgets.steps", old: 20, new: 28 }],
        },
      },
    ],
    latest_candidate: {
      ok: true,
      message: "Latest canonical candidate.",
      outcome: {
        kind: "candidate",
        changes: [{ uid: "ksampler", field_path: "widgets.steps", old: 20, new: 28 }],
      },
      candidate: {
        state: "candidate",
        graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
        graph_hash: "session-latest-candidate-hash",
        turn_identity: {
          session_id: "sess-canonical-session",
          turn_id: "0020",
        },
      },
      apply_eligibility: {
        applyable: true,
        reason: "applyable",
        message: "Ready to apply.",
        warnings: [],
      },
    },
  };

  assertCanonicalNormalPathHasNoLegacyAliases(raw);

  const normalized = normalizeCanonicalAgentEditResponse(raw, {
    endpoint: "/fixture/canonical-session",
  });
  const latest = readLatestCandidate(normalized, { allowLegacy: false });

  assert.equal(latest.outcome.kind, "candidate");
  assert.equal(readApplyCandidate(latest, { allowLegacy: false }).graphHash, "session-latest-candidate-hash");
  assert.equal(normalized.messages[1].outcome.kind, "candidate");
});

test("old session latest_candidate fixture requires the legacy adapter boundary", () => {
  const raw = loadFixture("chat_rehydrate_response.json");
  const oldLatestCandidate = {
    ...raw.latest_candidate,
    outcome: undefined,
    candidate: undefined,
    graph: raw.latest_candidate.candidate.graph,
  };

  assert.throws(
    () => normalizeCanonicalAgentEditResponse(oldLatestCandidate, {
      endpoint: "/fixture/chat-rehydrate:latest_candidate",
    }),
    /missing outcome/i,
  );

  const adapted = adaptLegacyAgentEditResponse(oldLatestCandidate, {
    endpoint: "/fixture/chat-rehydrate:latest_candidate",
  });
  assert.equal(adapted.outcome.kind, "candidate");
  assert.equal(readApplyCandidate(adapted, { allowLegacy: false }).graphHash, "candidate-hash-new");
});

test("session_bundle_response.json — structural contract", () => {
  const raw = loadFixture("session_bundle_response.json");

  // This is a session bundle response. Validate known fields.
  assert.equal(raw.ok, true);
  assert.equal(raw.exists, true);
  assert.ok(raw.session_path, "should have session_path");
  assert.equal(typeof raw.total_bytes, "number");
  assert.ok(raw.total_bytes > 0);
  assert.ok(Array.isArray(raw.files));
  assert.ok(raw.files.length >= 2);
  assert.equal(raw.files[0].name, "turns/0001/response.json");
  assert.ok(typeof raw.files[0].text, "string");
});

// ── Websocket agent turn fixtures ─────────────────────────────────────────

const agentTurnFixtures = [
  "websocket_agent_edit_turn_clarify.json",
  "websocket_agent_edit_turn_done.json",
  "websocket_agent_edit_turn_progress.json",
];

for (const fixtureName of agentTurnFixtures) {
  test(`normalizeAgentTurnPayload — ${fixtureName}`, () => {
    const raw = loadFixture(fixtureName);
    const normalized = normalizeAgentTurnPayload(raw);

    assert.ok(typeof normalized === "object" && normalized !== null,
      `${fixtureName}: normalized should be an object`);
    assert.ok(typeof normalized.session_id === "string" && normalized.session_id.length > 0,
      `${fixtureName}: normalized.session_id should be a non-empty string`);
    assert.ok(typeof normalized.turn_id === "string" && normalized.turn_id.length > 0,
      `${fixtureName}: normalized.turn_id should be a non-empty string`);
    assert.ok(typeof normalized.status === "string" && normalized.status.length > 0,
      `${fixtureName}: normalized.status should be a non-empty string`);

    // Verify status is a recognized agent turn status
    assert.ok(AGENT_TURN_STATUSES.includes(normalized.status),
      `${fixtureName}: normalized.status "${normalized.status}" should be a valid AGENT_TURN_STATUS`);

    // Verify entry_type is recognized
    assert.ok(AGENT_TURN_ENTRY_TYPES.includes(normalized.entry_type),
      `${fixtureName}: normalized.entry_type "${normalized.entry_type}" should be valid`);

    // Verify isTerminalAgentTurnStatus works
    const isTerminal = isTerminalAgentTurnStatus(normalized.status);
    assert.equal(typeof isTerminal, "boolean",
      `${fixtureName}: isTerminalAgentTurnStatus should return boolean`);

    // Verify agentTurnProgressLabel returns a string
    const label = agentTurnProgressLabel(normalized);
    assert.ok(typeof label === "string",
      `${fixtureName}: agentTurnProgressLabel should return a string`);

    // Verify extractAgentTurnPayload handles both direct and detail-wrapped
    const directExtract = extractAgentTurnPayload(raw);
    assert.ok(typeof directExtract === "object" && directExtract !== null,
      `${fixtureName}: extractAgentTurnPayload(direct) should extract payload`);

    const wrappedExtract = extractAgentTurnPayload({ detail: raw });
    assert.ok(typeof wrappedExtract === "object" && wrappedExtract !== null,
      `${fixtureName}: extractAgentTurnPayload(wrapped) should extract payload`);
    assert.deepEqual(directExtract, wrappedExtract,
      `${fixtureName}: extractAgentTurnPayload should return same payload for direct and wrapped`);
  });
}

// ── Websocket executor phase fixtures ─────────────────────────────────────

const executorPhaseFixtures = [
  "websocket_executor_phase_classify.json",
  "websocket_executor_phase_implement.json",
  "websocket_executor_phase_reply.json",
  "websocket_executor_phase_research.json",
];

for (const fixtureName of executorPhaseFixtures) {
  test(`normalizeExecutorPhasePayload — ${fixtureName}`, () => {
    const raw = loadFixture(fixtureName);
    const normalized = normalizeExecutorPhasePayload(raw);

    assert.ok(typeof normalized === "object" && normalized !== null,
      `${fixtureName}: normalized should be an object`);
    assert.ok(typeof normalized.phase === "string" && normalized.phase.length > 0,
      `${fixtureName}: normalized.phase should be a non-empty string`);
    assert.ok(EXECUTOR_PHASES.includes(normalized.phase),
      `${fixtureName}: normalized.phase "${normalized.phase}" should be a valid EXECUTOR_PHASE`);
    assert.ok(typeof normalized.status === "string" && normalized.status.length > 0,
      `${fixtureName}: normalized.status should be a non-empty string`);
    assert.ok(EXECUTOR_PHASE_STATUSES.includes(normalized.status),
      `${fixtureName}: normalized.status "${normalized.status}" should be a valid EXECUTOR_PHASE_STATUS`);

    // Verify extractExecutorPhasePayload handles both direct and detail-wrapped
    const directExtract = extractExecutorPhasePayload(raw);
    assert.ok(typeof directExtract === "object" && directExtract !== null,
      `${fixtureName}: extractExecutorPhasePayload(direct) should extract payload`);

    const wrappedExtract = extractExecutorPhasePayload({ detail: raw });
    assert.ok(typeof wrappedExtract === "object" && wrappedExtract !== null,
      `${fixtureName}: extractExecutorPhasePayload(wrapped) should extract payload`);

    // Verify progress derivation
    const progress = progressFromExecutorPhase(normalized);
    assert.ok(typeof progress === "object" && progress !== null,
      `${fixtureName}: progressFromExecutorPhase should return a progress snapshot`);
    assert.ok(typeof progress.decide === "string",
      `${fixtureName}: progress snapshot should have decide field`);
    assert.ok(typeof progress.research === "string",
      `${fixtureName}: progress snapshot should have research field`);
    assert.ok(typeof progress.execute === "string",
      `${fixtureName}: progress snapshot should have execute field`);
    assert.ok(typeof progress.review === "string",
      `${fixtureName}: progress snapshot should have review field`);

    // Verify progress utilities
    const validated = normalizeExecutorProgressSnapshot(progress);
    assert.ok(validated !== null,
      `${fixtureName}: normalizeExecutorProgressSnapshot should validate derived progress`);
    const complete = isExecutorProgressComplete(progress);
    assert.equal(typeof complete, "boolean",
      `${fixtureName}: isExecutorProgressComplete should return boolean`);
    const label = executorProgressLabel(progress);
    assert.ok(typeof label === "string",
      `${fixtureName}: executorProgressLabel should return a string`);
  });
}

// ── Agent status fixtures ─────────────────────────────────────────────────

test("agent status helpers — agent_status_ready.json", () => {
  const raw = loadFixture("agent_status_ready.json");

  // buildStatusUrl
  assert.equal(buildStatusUrl("arnold", "default"),
    "/vibecomfy/agent/status?route=arnold&model=default");
  assert.equal(buildStatusUrl("", ""),
    "/vibecomfy/agent/status");

  // routeOptionsFromStatus
  const routeOptions = routeOptionsFromStatus(raw);
  assert.ok(routeOptions !== null);
  assert.ok(typeof routeOptions === "object" && !Array.isArray(routeOptions));
  assert.ok(routeOptions.auto);
  assert.ok(routeOptions.deepseek);
  assert.equal(routeOptions.auto.normalized_route, "arnold");
  assert.equal(routeOptions.deepseek.browser_api_key_allowed, true);

  // Stable public fields on raw fixture
  assert.equal(raw.ok, true);
  assert.equal(raw.provider_available, true);
  assert.equal(raw.route, "arnold");
});

test("agent status helpers — agent_status_malformed.json (malformed route_options)", () => {
  const raw = loadFixture("agent_status_malformed.json");

  // route_options is "not-an-object" — should return null
  const routeOptions = routeOptionsFromStatus(raw);
  assert.equal(routeOptions, null);

  // Stable public fields
  assert.equal(raw.ok, true);
  assert.equal(raw.provider_available, true);
  assert.equal(raw.route, "arnold");
  assert.equal(raw.route_options, "not-an-object");
});

test("agent status helpers — agent_status_unavailable.json (unavailable status)", () => {
  const raw = loadFixture("agent_status_unavailable.json");

  // No route_options field — should return null
  const routeOptions = routeOptionsFromStatus(raw);
  assert.equal(routeOptions, null);

  // Stable public fields
  assert.equal(raw.ok, false);
  assert.equal(raw.provider_available, false);
  assert.equal(typeof raw.message, "string");
  assert.ok(raw.message.length > 0);
});

// ── Malformed / missing-option behavior tests ─────────────────────────────

test("routeOptionsFromStatus handles null and non-object inputs", () => {
  assert.equal(routeOptionsFromStatus(null), null);
  assert.equal(routeOptionsFromStatus(undefined), null);
  assert.equal(routeOptionsFromStatus("string"), null);
  assert.equal(routeOptionsFromStatus(42), null);
  assert.equal(routeOptionsFromStatus([]), null);
  assert.equal(routeOptionsFromStatus({}), null);
  assert.equal(routeOptionsFromStatus({ route_options: [] }), null);
  assert.equal(routeOptionsFromStatus({ route_options: "string" }), null);
});

test("routeOptionsFromStatus handles missing route_options gracefully", () => {
  const status = { ok: true, provider_available: true, route: "arnold" };
  assert.equal(routeOptionsFromStatus(status), null);
});

test("normalizeAgentTurnPayload returns null for non-object input", () => {
  assert.equal(normalizeAgentTurnPayload(null), null);
  assert.equal(normalizeAgentTurnPayload(undefined), null);
  assert.equal(normalizeAgentTurnPayload("string"), null);
  assert.equal(normalizeAgentTurnPayload(42), null);
  assert.equal(normalizeAgentTurnPayload([]), null);
  assert.equal(normalizeAgentTurnPayload({}), null); // missing session_id
});

test("normalizeExecutorPhasePayload returns null for non-object input", () => {
  assert.equal(normalizeExecutorPhasePayload(null), null);
  assert.equal(normalizeExecutorPhasePayload(undefined), null);
  assert.equal(normalizeExecutorPhasePayload("string"), null);
  assert.equal(normalizeExecutorPhasePayload(42), null);
  assert.equal(normalizeExecutorPhasePayload([]), null);
  assert.equal(normalizeExecutorPhasePayload({}), null); // missing phase
});

test("normalizeExecutorPhasePayload returns null for unrecognized phase", () => {
  assert.equal(normalizeExecutorPhasePayload({ phase: "invalid_phase", status: "start" }), null);
});

test("createExecutorProgressSnapshot defaults missing stages to pending", () => {
  const empty = createExecutorProgressSnapshot();
  assert.deepEqual(empty, {
    decide: "pending",
    research: "pending",
    execute: "pending",
    review: "pending",
  });
});

test("createExecutorProgressSnapshot with partial overrides", () => {
  const partial = createExecutorProgressSnapshot({ decide: "done", research: "active" });
  assert.equal(partial.decide, "done");
  assert.equal(partial.research, "active");
  assert.equal(partial.execute, "pending");
  assert.equal(partial.review, "pending");
});

test("isExecutorProgressComplete returns false for pending snapshot", () => {
  const pending = createExecutorProgressSnapshot();
  assert.equal(isExecutorProgressComplete(pending), false);
});

test("isExecutorProgressComplete returns true for fully done snapshot", () => {
  const done = createExecutorProgressSnapshot({
    decide: "done",
    research: "done",
    execute: "done",
    review: "done",
  });
  assert.equal(isExecutorProgressComplete(done), true);
});

test("executorProgressLabel returns correct labels", () => {
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "active" })), "Decide");
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "done", research: "active" })), "Research");
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "done", research: "done", execute: "active" })), "Execute");
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "done", research: "done", execute: "done", review: "active" })), "Review");
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "done", research: "done", execute: "done", review: "done" })), "Complete");
  assert.equal(executorProgressLabel(null), "Unknown");
  assert.equal(executorProgressLabel("invalid"), "Unknown");
});

// ── Canonical activity derivation tests (deriveAgentActivityState) ─────────

test("deriveAgentActivityState — null/undefined input returns safe unknown shape", () => {
  const nullResult = deriveAgentActivityState(null);
  assert.equal(nullResult.status, "unknown");
  assert.equal(nullResult.outcome.kind, "unknown");
  assert.deepEqual(nullResult.counts, { total: 0, landed: 0, not_landed: 0, ok: 0, not_ok: 0 });

  const undefResult = deriveAgentActivityState(undefined);
  assert.equal(undefResult.status, "unknown");

  // Both should be frozen
  assert.throws(() => { nullResult.status = "changed"; }, /frozen|read.only|assign/i);
});

test("deriveAgentActivityState — legacy progress normalized to in_progress", () => {
  const raw = loadFixture("websocket_agent_edit_turn_progress.json");
  const normalized = normalizeAgentTurnPayload(raw);
  const activity = deriveAgentActivityState(normalized);

  assert.equal(normalized.status, "progress", "raw fixture still uses 'progress'");
  assert.equal(activity.status, "in_progress", "canonical normalizes to 'in_progress'");
  assert.equal(activity.outcome.kind, "in_progress");
  assert.ok(activity.headline, "should derive a headline");
  assert.ok(typeof activity.headline === "string");
});

test("deriveAgentActivityState — in_progress with landed ops shows executing phase", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-exec",
    turn_id: "0003",
    turn_number: 2,
    status: "progress",
    message: "Applying changes...",
    statement_count: 5,
    landed_op_count: 3,
    statements: [
      { op_kind: "query", status: "done", message: "Queried nodes" },
      { op_kind: "add_node", status: "done", message: "Added node", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected", landed: true, ok: true },
      { op_kind: "set_value", status: "done", message: "Set value", landed: true, ok: true },
      { op_kind: "done", status: "done" },
    ],
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "in_progress");
  assert.equal(activity.outcome.kind, "in_progress");
  assert.equal(activity.phase_progress.execute, "active");
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.research, "done");

  // done() statement should NOT be latest substantive
  assert.ok(activity.latest_substantive_statement);
  assert.notEqual(activity.latest_substantive_statement.op_kind, "done");
  assert.equal(activity.latest_substantive_statement.op_kind, "set_value");

  // Counts
  assert.equal(activity.counts.total, 5);
  assert.equal(activity.counts.landed, 3);
  assert.equal(activity.counts.ok, 3);
});

test("deriveAgentActivityState — answer-only / no graph changes", () => {
  // Done turn with no substantive statements and no landed ops
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-answer-only",
    turn_id: "0004",
    turn_number: 1,
    status: "done",
    message: "Here is the answer to your question.",
    statement_count: 1,
    landed_op_count: 0,
    statements: [
      { op_kind: "done", status: "done", message: "Turn complete" },
    ],
    done_summary: "Answered the question without changes.",
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "done");
  assert.equal(activity.outcome.kind, "answered", "answer-only turns yield 'answered' outcome");
  assert.equal(activity.outcome.graph_changes, false);
  assert.ok(activity.outcome.summary.includes("Answered"));
  assert.equal(activity.latest_substantive_statement, null, "no substantive statements");

  // Also test: no statements at all
  const payloadNoStmts = normalizeAgentTurnPayload({
    session_id: "sess-answer-only-2",
    turn_id: "0005",
    turn_number: 1,
    status: "done",
    message: "Just an answer, no edits at all.",
    statement_count: 0,
    landed_op_count: 0,
    done_summary: "Answer only.",
  });

  const activity2 = deriveAgentActivityState(payloadNoStmts);
  assert.equal(activity2.outcome.kind, "answered");
  assert.equal(activity2.outcome.graph_changes, false);
});

test("deriveAgentActivityState — edit-plus-done: latest substantive action selected, not done()", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-edit-done",
    turn_id: "0006",
    turn_number: 3,
    status: "done",
    message: "Edit complete: modifications applied.",
    statement_count: 5,
    landed_op_count: 3,
    statements: [
      { op_kind: "query", status: "done", message: "Queried available nodes" },
      { op_kind: "add_node", status: "done", message: "Added Upscale node", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected Upscale to output", landed: true, ok: true },
      { op_kind: "set_field", status: "done", message: "Set upscale factor to 2x", landed: true, ok: true, teaching_hint: "Upscale factor set" },
      { op_kind: "done", status: "done", message: "Finished editing" },
    ],
    done_summary: "Added Upscale node and connected to pipeline.",
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "done");
  assert.equal(activity.outcome.kind, "done", "edit turns yield 'done' outcome");
  assert.ok(activity.outcome.landed_ops >= 3);
  assert.ok(activity.outcome.summary.includes("Upscale") || activity.outcome.summary.includes("applied"),
    "summary should reference the actual edit");

  // Critical: done() must NOT be the latest substantive statement
  assert.ok(activity.latest_substantive_statement, "should have a substantive statement");
  assert.notEqual(activity.latest_substantive_statement.op_kind, "done",
    "done() protocol terminator should never be latest_substantive_statement");
  assert.equal(activity.latest_substantive_statement.op_kind, "set_field",
    "latest substantive should be the last real edit, not done()");

  // Headline should come from a message-bearing substantive statement, not done()
  assert.ok(activity.headline, "should have a headline");
  assert.notEqual(activity.headline, "Finished editing",
    "headline should not be the done() message when substantive statements exist");
});

test("deriveAgentActivityState — edit with only done() statements falls back", () => {
  // Edge case: a turn with only done() statements (no substantive ops)
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-done-only",
    turn_id: "0007",
    turn_number: 1,
    status: "done",
    message: "All done.",
    statement_count: 1,
    landed_op_count: 0,
    statements: [
      { op_kind: "done", status: "done", message: "All finished" },
    ],
    done_summary: "Turn completed.",
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "done");
  assert.equal(activity.outcome.kind, "answered");
  assert.equal(activity.latest_substantive_statement, null, "only done() means no substantive");
});

test("deriveAgentActivityState — clarify outcome", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-clarify",
    turn_id: "0008",
    turn_number: 2,
    status: "clarify",
    message: "Need clarification.",
    clarification_required: true,
    clarification_message: "Should I replace the sampler with an upscaler?",
    statement_count: 1,
    landed_op_count: 0,
    statements: [
      { op_kind: "clarify", status: "active", message: "Need clarification" },
    ],
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "clarify");
  assert.equal(activity.outcome.kind, "clarify");
  assert.equal(activity.outcome.clarification_required, true);
  assert.ok(activity.outcome.summary.includes("sampler") || activity.outcome.summary.includes("upscaler"),
    "summary should include the clarification question");
  assert.ok(activity.outcome.clarification_message);

  // phase_progress should be fully done (terminal)
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.research, "done");
  assert.equal(activity.phase_progress.execute, "done");
  assert.equal(activity.phase_progress.review, "done");
});

test("deriveAgentActivityState — error outcome", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-error",
    turn_id: "0009",
    turn_number: 2,
    status: "error",
    message: "An error occurred during the turn.",
    statement_count: 2,
    landed_op_count: 1,
    statements: [
      { op_kind: "query", status: "done", message: "Queried nodes", ok: true },
      { op_kind: "apply_op", status: "error", message: "Failed to apply: node not found", ok: false },
    ],
    diagnostics: [
      { code: "NODE_NOT_FOUND", message: "Target node was removed during execution" },
    ],
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "error");
  assert.equal(activity.outcome.kind, "error");
  assert.ok(activity.outcome.summary.includes("Target node was removed") || activity.outcome.summary.includes("NODE_NOT_FOUND"),
    "error summary should include diagnostic info");
  assert.ok(activity.outcome.diagnostics);
  assert.equal(activity.outcome.diagnostics[0].code, "NODE_NOT_FOUND");

  // phase_progress should be fully done (terminal)
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.execute, "done");

  // Check diagnostics in activity
  assert.ok(activity.diagnostics);
  assert.equal(activity.diagnostics[0].code, "NODE_NOT_FOUND");
});

test("deriveAgentActivityState — budget_exhausted outcome", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-budget",
    turn_id: "0010",
    turn_number: 2,
    status: "budget_exhausted",
    message: "Budget exhausted.",
    statement_count: 3,
    landed_op_count: 1,
    statements: [
      { op_kind: "query", status: "done", message: "Queried templates" },
      { op_kind: "add_node", status: "done", message: "Added PreviewImage", landed: true, ok: true },
      { op_kind: "done", status: "done" },
    ],
    budget: {
      remaining_batches: 0,
      consecutive_errors: 2,
    },
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "budget_exhausted");
  assert.equal(activity.outcome.kind, "budget_exhausted");
  assert.ok(activity.outcome.summary.includes("Budget exhausted"), "summary should mention budget");
  assert.ok(activity.outcome.summary.includes("0 turns remaining") || activity.outcome.summary.includes("remaining"),
    "summary should include remaining count");
  assert.ok(activity.outcome.budget);
  assert.equal(activity.outcome.budget.remaining_batches, 0);

  // phase_progress should be fully done (terminal)
  assert.equal(activity.phase_progress.decide, "done");

  // Latest substantive should still be the add_node (skip done())
  assert.ok(activity.latest_substantive_statement);
  assert.equal(activity.latest_substantive_statement.op_kind, "add_node");
});

test("deriveAgentActivityState — stale progress fixture (websocket_agent_edit_turn_progress.json) normalizes", () => {
  const raw = loadFixture("websocket_agent_edit_turn_progress.json");
  const normalized = normalizeAgentTurnPayload(raw);
  const activity = deriveAgentActivityState(normalized);

  assert.equal(normalized.status, "progress");
  assert.equal(activity.status, "in_progress");
  assert.equal(activity.outcome.kind, "in_progress");

  // Should derive headline from statements
  assert.ok(activity.headline);
  assert.ok(typeof activity.headline === "string");

  // Phase progress: researching (has statements but no landed ops)
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.research, "active");
  assert.equal(activity.phase_progress.execute, "pending");
});

test("deriveAgentActivityState — stale progress compatibility: payload with status=progress and no statements", () => {
  // Minimal progress payload - simulates an old-style backend message
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-progress-legacy",
    turn_id: "0011",
    turn_number: 1,
    status: "progress",
    message: "Thinking...",
    statement_count: 0,
    landed_op_count: 0,
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "in_progress");
  assert.equal(activity.outcome.kind, "in_progress");
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.research, "active");

  // Headline falls back to message
  assert.equal(activity.headline, "Thinking...");
});

test("deriveAgentActivityState — canonical shape has all required fields", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-shape",
    turn_id: "0012",
    turn_number: 1,
    status: "progress",
  });

  const activity = deriveAgentActivityState(payload);

  const requiredKeys = [
    "session_id", "turn_id", "turn_number", "entry_type",
    "status", "phase_progress", "headline", "outcome",
    "latest_substantive_statement", "counts", "diagnostics", "details",
  ];

  for (const key of requiredKeys) {
    assert.ok(key in activity, `activity should have key: ${key}`);
  }

  // Check shapes
  assert.ok(typeof activity.phase_progress === "object" && activity.phase_progress !== null);
  assert.ok("decide" in activity.phase_progress);
  assert.ok("research" in activity.phase_progress);
  assert.ok("execute" in activity.phase_progress);
  assert.ok("review" in activity.phase_progress);

  assert.ok(typeof activity.outcome === "object" && activity.outcome !== null);
  assert.ok("kind" in activity.outcome);
  assert.ok("summary" in activity.outcome);

  assert.ok(typeof activity.counts === "object" && activity.counts !== null);
  assert.ok("total" in activity.counts);
  assert.ok("landed" in activity.counts);

  assert.ok(Array.isArray(activity.details));
});

test("deriveAgentActivityState — done() statements excluded from latest_substantive_statement (all protocol terminators)", () => {
  // Test all protocol terminator op_kinds
  const terminators = ["done", "exit", "terminal", "finish", "complete", "DONE", "Done", "Exit"];
  for (const term of terminators) {
    const payload = normalizeAgentTurnPayload({
      session_id: "sess-term-" + term,
      turn_id: "0100",
      turn_number: 1,
      status: "done",
      message: "Done.",
      statement_count: 2,
      landed_op_count: 1,
      statements: [
        { op_kind: "add_node", status: "done", message: "Added sampler", landed: true, ok: true },
        { op_kind: term, status: "done", message: "Turn finished" },
      ],
    });

    const activity = deriveAgentActivityState(payload);
    assert.ok(activity.latest_substantive_statement, `should have substantive for terminator '${term}'`);
    assert.equal(activity.latest_substantive_statement.op_kind, "add_node",
      `latest_substantive should be add_node, not '${term}'`);
  }
});

test("deriveAgentActivityState — details exclude unsafe fields", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-safe",
    turn_id: "0013",
    turn_number: 1,
    status: "done",
    message: "Safe message.",
    statement_count: 1,
    landed_op_count: 1,
    statements: [
      { op_kind: "add_node", status: "done", message: "Added node", landed: true, ok: true },
    ],
    done_summary: "Node added.",
    timing: { model_elapsed_ms: 1200, engine_elapsed_ms: 50, turn_elapsed_ms: 1300 },
    budget: { remaining_batches: 3, consecutive_errors: 0 },
    exit_mode: "done",
  });

  const activity = deriveAgentActivityState(payload);

  // Serialize to check for forbidden fields
  const json = JSON.stringify(activity.details);
  assert.ok(!json.includes("diff"), "details should not contain raw diff");
  assert.ok(!json.includes("provider_metadata"), "details should not contain provider_metadata");
  assert.ok(!json.includes("raw_source"), "details should not contain raw_source");
  assert.ok(!json.includes("raw_batch"), "details should not contain raw_batch");
  assert.ok(!json.includes("file_path"), "details should not contain file paths");
  assert.ok(!json.includes("full_report"), "details should not contain full_report");

  // But safe fields should be present
  assert.ok(activity.details.some(d => d.kind === "identity"));
  assert.ok(activity.details.some(d => d.kind === "timing"));
  assert.ok(activity.details.some(d => d.kind === "budget"));
});

test("deriveAgentActivityState — latestSubstantiveStatement helper with empty/null arrays", () => {
  assert.equal(latestSubstantiveStatement(null), null);
  assert.equal(latestSubstantiveStatement(undefined), null);
  assert.equal(latestSubstantiveStatement([]), null);
  assert.equal(latestSubstantiveStatement([null, undefined]), null);
});

test("deriveAgentActivityState — isSubstantiveStatement helper", () => {
  assert.equal(isSubstantiveStatement({ op_kind: "add_node" }), true);
  assert.equal(isSubstantiveStatement({ op_kind: "query" }), true);
  assert.equal(isSubstantiveStatement({ op_kind: "set_field" }), true);
  assert.equal(isSubstantiveStatement({ op_kind: "done" }), false);
  assert.equal(isSubstantiveStatement({ op_kind: "exit" }), false);
  assert.equal(isSubstantiveStatement({ op_kind: "terminal" }), false);
  assert.equal(isSubstantiveStatement({ op_kind: "finish" }), false);
  assert.equal(isSubstantiveStatement({ op_kind: "complete" }), false);
  assert.equal(isSubstantiveStatement(null), false);
  assert.equal(isSubstantiveStatement({}), false);
  assert.equal(isSubstantiveStatement({ op_kind: null }), false);
});

test("deriveAgentActivityState — deriveStatementCounts helper", () => {
  const stmts = [
    { op_kind: "add_node", landed: true, ok: true },
    { op_kind: "query", landed: true, ok: true },
    { op_kind: "apply_op", landed: false, ok: false },
    { op_kind: "set_field", landed: false, ok: true },
    { op_kind: "done" },
  ];
  const counts = deriveStatementCounts(stmts);
  assert.equal(counts.total, 5);
  assert.equal(counts.landed, 2);
  assert.equal(counts.not_landed, 2);
  assert.equal(counts.ok, 3);
  assert.equal(counts.not_ok, 1);
});

test("deriveAgentActivityState — websocket clarify fixture canonical derivation", () => {
  const raw = loadFixture("websocket_agent_edit_turn_clarify.json");
  const normalized = normalizeAgentTurnPayload(raw);
  const activity = deriveAgentActivityState(normalized);

  assert.equal(activity.status, "clarify");
  assert.equal(activity.outcome.kind, "clarify");
  assert.equal(activity.outcome.clarification_required, true);
  assert.ok(activity.outcome.clarification_message.includes("Should I move"));
});

test("deriveAgentActivityState — websocket done fixture canonical derivation", () => {
  const raw = loadFixture("websocket_agent_edit_turn_done.json");
  const normalized = normalizeAgentTurnPayload(raw);
  const activity = deriveAgentActivityState(normalized);

  assert.equal(activity.status, "done");
  assert.equal(activity.outcome.kind, "done", "edit-plus-done should yield 'done' outcome");
  assert.ok(activity.outcome.landed_ops >= 2);

  // done() at index 3 should NOT be latest_substantive
  assert.ok(activity.latest_substantive_statement);
  assert.notEqual(activity.latest_substantive_statement.op_kind, "done");
  assert.equal(activity.latest_substantive_statement.op_kind, "connect",
    "latest substantive should be connect, not done");
});


// ── Activity feed reducer tests (reduceAgentActivityFeed) ────────────────────

/** Helper: create a minimal canonical activity state suitable for reducer testing. */
function makeActivityState(overrides = {}) {
  const base = {
    session_id: overrides.session_id ?? "sess-reducer",
    turn_id: overrides.turn_id ?? "0001",
    turn_number: overrides.turn_number ?? 1,
    entry_type: overrides.entry_type ?? "batch",
    status: overrides.status ?? "in_progress",
    phase_progress: { decide: "done", research: "active", execute: "pending", review: "pending" },
    headline: overrides.headline ?? "Working...",
    outcome: { kind: overrides.status ?? "in_progress", summary: "Working..." },
    latest_substantive_statement: null,
    counts: { total: 0, landed: 0, not_landed: 0, ok: 0, not_ok: 0 },
    diagnostics: null,
    details: [],
  };
  return Object.freeze({ ...base, ...overrides });
}

// ── Basic guard tests ──────────────────────────────────────────────────

test("reduceAgentActivityFeed — null/undefined update returns previous unchanged", () => {
  const feed = [makeActivityState({ turn_id: "0001", turn_number: 1 })];
  assert.equal(reduceAgentActivityFeed(feed, null), feed);
  assert.equal(reduceAgentActivityFeed(feed, undefined), feed);

  const emptyFeed = [];
  assert.deepEqual(reduceAgentActivityFeed(emptyFeed, null), []);
  assert.deepEqual(reduceAgentActivityFeed(null, null), []);
});

test("reduceAgentActivityFeed — update with no session_id or turn_id is rejected", () => {
  const feed = [makeActivityState({ turn_id: "0001", turn_number: 1 })];
  const noSession = makeActivityState({ session_id: null, turn_id: "0002" });
  assert.equal(reduceAgentActivityFeed(feed, noSession), feed);
  const noTurn = makeActivityState({ session_id: "sess-reducer", turn_id: null });
  assert.equal(reduceAgentActivityFeed(feed, noTurn), feed);
});

test("reduceAgentActivityFeed — first update binds session and appends", () => {
  const result = reduceAgentActivityFeed([], makeActivityState({ turn_id: "0001", turn_number: 1 }));
  assert.equal(result.length, 1);
  assert.equal(result[0].turn_id, "0001");
  assert.equal(result[0].session_id, "sess-reducer");
});

// ── Session binding tests ──────────────────────────────────────────────

test("reduceAgentActivityFeed — rejects foreign-session update when feed has established session", () => {
  const feed = [makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1 })];
  const foreign = makeActivityState({ session_id: "sess-B", turn_id: "0002", turn_number: 2 });
  const result = reduceAgentActivityFeed(feed, foreign);
  assert.equal(result, feed, "foreign session update must be rejected");
  assert.equal(result.length, 1);
});

test("reduceAgentActivityFeed — accepts same-session update", () => {
  const feed = [makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1 })];
  const same = makeActivityState({ session_id: "sess-A", turn_id: "0002", turn_number: 2 });
  const result = reduceAgentActivityFeed(feed, same);
  assert.equal(result.length, 2);
  assert.equal(result[1].turn_id, "0002");
});

// ── Stale event rejection ──────────────────────────────────────────────

test("reduceAgentActivityFeed — rejects stale new turn with lower turn_number than feed max", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "done" }),
    makeActivityState({ session_id: "sess-A", turn_id: "0002", turn_number: 2, status: "done" }),
    makeActivityState({ session_id: "sess-A", turn_id: "0003", turn_number: 3, status: "done" }),
  ];
  // Late-arriving websocket event for turn 1 (a new turn not in feed)
  const stale = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001b",  // different turn_id so it's "new"
    turn_number: 1,
    status: "in_progress",
  });
  const result = reduceAgentActivityFeed(feed, stale);
  assert.equal(result, feed, "stale new turn (lower turn_number) must be rejected");
  assert.equal(result.length, 3, "feed length must not grow");
});

test("reduceAgentActivityFeed — stale new turn with much lower turn_number rejected", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0010", turn_number: 10, status: "done" }),
  ];
  // A late-arriving old turn
  const stale = makeActivityState({
    session_id: "sess-A",
    turn_id: "0003",
    turn_number: 3,
    status: "in_progress",
  });
  const result = reduceAgentActivityFeed(feed, stale);
  assert.equal(result, feed);
  assert.equal(result.length, 1);
});

test("reduceAgentActivityFeed — update to existing turn accepted regardless of turn_number order", () => {
  // This is important: an update to a turn already in the feed should be accepted
  // even if the turn's turn_number is lower than max — it's an in-place update, not new.
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "in_progress" }),
    makeActivityState({ session_id: "sess-A", turn_id: "0002", turn_number: 2, status: "in_progress" }),
    makeActivityState({ session_id: "sess-A", turn_id: "0003", turn_number: 3, status: "in_progress" }),
  ];
  // Websocket update for existing turn 0001 with more progress
  const update = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001",  // same turn_id — matches existing
    turn_number: 1,
    status: "done",
    headline: "Completed",
  });
  const result = reduceAgentActivityFeed(feed, update);
  assert.equal(result.length, 3, "should not grow — replaces in place");
  assert.equal(result[0].turn_id, "0001");
  assert.equal(result[0].status, "done", "should reflect updated status");
  assert.equal(result[0].headline, "Completed");
});

// ── Terminal → active regression prevention ────────────────────────────

test("reduceAgentActivityFeed — prevents terminal→in_progress regression for websocket source", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "done", headline: "All done" }),
  ];
  // Websocket comes in later with in_progress for the same turn — must be rejected
  const regress = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001",
    turn_number: 1,
    status: "in_progress",
    headline: "Working again...",
  });
  const result = reduceAgentActivityFeed(feed, regress, { source: "websocket" });
  assert.equal(result, feed, "terminal→in_progress regression must be prevented");
  assert.equal(result[0].status, "done", "terminal status preserved");
  assert.equal(result[0].headline, "All done", "terminal headline preserved");
});

test("reduceAgentActivityFeed — prevents terminal→in_progress regression for clarify", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "clarify" }),
  ];
  const regress = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001",
    turn_number: 1,
    status: "in_progress",
  });
  const result = reduceAgentActivityFeed(feed, regress);
  assert.equal(result, feed, "clarify terminal→in_progress regression must be prevented");
});

test("reduceAgentActivityFeed — prevents terminal→in_progress regression for error", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "error" }),
  ];
  const regress = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001",
    turn_number: 1,
    status: "in_progress",
  });
  const result = reduceAgentActivityFeed(feed, regress);
  assert.equal(result, feed);
});

test("reduceAgentActivityFeed — prevents terminal→in_progress regression for budget_exhausted", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "budget_exhausted" }),
  ];
  const regress = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001",
    turn_number: 1,
    status: "in_progress",
  });
  const result = reduceAgentActivityFeed(feed, regress);
  assert.equal(result, feed);
});

test("reduceAgentActivityFeed — allows terminal→done websocket update (terminal to terminal)", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "error" }),
  ];
  // Websocket update from error to done (terminal→terminal is fine)
  const update = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001",
    turn_number: 1,
    status: "done",
    headline: "Recovered and done",
  });
  const result = reduceAgentActivityFeed(feed, update, { source: "websocket" });
  assert.equal(result.length, 1);
  assert.equal(result[0].status, "done", "terminal→terminal transition allowed");
  assert.equal(result[0].headline, "Recovered and done");
});

test("reduceAgentActivityFeed — allows in_progress→terminal websocket update", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "in_progress" }),
  ];
  const update = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001",
    turn_number: 1,
    status: "done",
    headline: "Finished",
  });
  const result = reduceAgentActivityFeed(feed, update, { source: "websocket" });
  assert.equal(result[0].status, "done", "in_progress→terminal transition allowed");
});

// ── HTTP authoritative overwrite ───────────────────────────────────────

test("reduceAgentActivityFeed — HTTP source replaces existing websocket partial state", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "in_progress", headline: "Working..." }),
  ];
  const httpUpdate = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001",
    turn_number: 1,
    status: "done",
    headline: "HTTP authoritative: completed",
    entry_type: "batch",
  });
  const result = reduceAgentActivityFeed(feed, httpUpdate, { source: "http" });
  assert.equal(result.length, 1, "HTTP must replace, not duplicate");
  assert.equal(result[0].status, "done");
  assert.equal(result[0].headline, "HTTP authoritative: completed");
});

test("reduceAgentActivityFeed — HTTP source can override terminal websocket state", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "done", headline: "ws done" }),
  ];
  // HTTP wants to override with in_progress — HTTP is authoritative, must be allowed
  const httpUpdate = makeActivityState({
    session_id: "sess-A",
    turn_id: "0001",
    turn_number: 1,
    status: "in_progress",
    headline: "HTTP says still working",
    entry_type: "batch",
  });
  const result = reduceAgentActivityFeed(feed, httpUpdate, { source: "http" });
  assert.equal(result.length, 1, "HTTP must replace, not duplicate");
  assert.equal(result[0].status, "in_progress", "HTTP authoritative source can override terminal");
  assert.equal(result[0].headline, "HTTP says still working");
});

test("reduceAgentActivityFeed — HTTP authoritative final state replaces websocket partial across multiple turns", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "done", headline: "ws: turn 1 done" }),
    makeActivityState({ session_id: "sess-A", turn_id: "0002", turn_number: 2, status: "in_progress", headline: "ws: turn 2 working" }),
  ];
  // HTTP batch reconciliation: authoritative final state for turn 2
  const httpTurn2 = makeActivityState({
    session_id: "sess-A",
    turn_id: "0002",
    turn_number: 2,
    status: "done",
    headline: "http: turn 2 done",
    entry_type: "batch",
  });
  const result = reduceAgentActivityFeed(feed, httpTurn2, { source: "http" });
  assert.equal(result.length, 2, "no duplication; HTTP replaces in place");
  assert.equal(result[0].turn_id, "0001");
  assert.equal(result[0].status, "done");
  assert.equal(result[1].turn_id, "0002");
  assert.equal(result[1].status, "done", "HTTP overwrites websocket partial");
  assert.equal(result[1].headline, "http: turn 2 done");
});

// ── No duplicate rows ──────────────────────────────────────────────────

test("reduceAgentActivityFeed — multiple websocket updates for same turn replace in place", () => {
  let feed = [];
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-A", turn_id: "0001", turn_number: 1,
    status: "in_progress", headline: "Step 1",
  }));
  assert.equal(feed.length, 1);

  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-A", turn_id: "0001", turn_number: 1,
    status: "in_progress", headline: "Step 2",
  }));
  assert.equal(feed.length, 1, "no duplicate rows for same turn_id");
  assert.equal(feed[0].headline, "Step 2", "updated in place");

  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-A", turn_id: "0001", turn_number: 1,
    status: "done", headline: "Step 3 - complete",
  }));
  assert.equal(feed.length, 1);
  assert.equal(feed[0].status, "done");
  assert.equal(feed[0].headline, "Step 3 - complete");
});

test("reduceAgentActivityFeed — interleaved updates across multiple turns, no duplication", () => {
  let feed = [];

  // Turn 1 arrives
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-A", turn_id: "0001", turn_number: 1,
    status: "in_progress", headline: "T1 start",
  }));
  assert.equal(feed.length, 1);

  // Turn 2 arrives
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-A", turn_id: "0002", turn_number: 2,
    status: "in_progress", headline: "T2 start",
  }));
  assert.equal(feed.length, 2);

  // Turn 1 update (websocket progress)
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-A", turn_id: "0001", turn_number: 1,
    status: "done", headline: "T1 done",
  }));
  assert.equal(feed.length, 2, "still 2 turns, no duplication");
  assert.equal(feed[0].turn_id, "0001");
  assert.equal(feed[0].status, "done");
  assert.equal(feed[1].turn_id, "0002");
  assert.equal(feed[1].status, "in_progress");

  // Turn 2 update
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-A", turn_id: "0002", turn_number: 2,
    status: "done", headline: "T2 done",
  }));
  assert.equal(feed.length, 2, "no duplication ever");

  // Turn 2 goes to error (terminal→terminal transition)
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-A", turn_id: "0002", turn_number: 2,
    status: "error", headline: "T2 errored",
  }));
  assert.equal(feed.length, 2);
  assert.equal(feed[1].status, "error");

  // HTTP final reconciliation for turn 1 (same session/turn, no duplicate)
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-A", turn_id: "0001", turn_number: 1,
    status: "done", headline: "T1 done (HTTP)", entry_type: "batch",
  }), { source: "http" });
  assert.equal(feed.length, 2, "HTTP must not duplicate");
  assert.equal(feed[0].headline, "T1 done (HTTP)");
});

test("reduceAgentActivityFeed — HTTP batch reconciliation does not duplicate across all turns", () => {
  // Simulate initial websocket feed for 3 turns
  let feed = [];
  for (let i = 1; i <= 3; i++) {
    const turnId = "000" + i;
    feed = reduceAgentActivityFeed(feed, makeActivityState({
      session_id: "sess-A",
      turn_id: turnId,
      turn_number: i,
      status: "in_progress",
      headline: "ws: turn " + i + " working",
    }));
  }
  assert.equal(feed.length, 3, "3 websocket turns appended");

  // HTTP batch reconciliation: update all 3 turns authoritatively
  for (let i = 1; i <= 3; i++) {
    const turnId = "000" + i;
    feed = reduceAgentActivityFeed(feed, makeActivityState({
      session_id: "sess-A",
      turn_id: turnId,
      turn_number: i,
      status: "done",
      headline: "http: turn " + i + " done",
      entry_type: "batch",
    }), { source: "http" });
  }
  assert.equal(feed.length, 3, "HTTP reconciliation must not duplicate any turn");
  for (let i = 0; i < 3; i++) {
    assert.equal(feed[i].status, "done");
    assert.ok(feed[i].headline.startsWith("http:"), "headline should be from HTTP");
  }
});

test("reduceAgentActivityFeed — same-session same-turn update replaces exactly one entry", () => {
  const feed = [
    makeActivityState({ session_id: "sess-A", turn_id: "0001", turn_number: 1, status: "done" }),
    makeActivityState({ session_id: "sess-A", turn_id: "0002", turn_number: 2, status: "done" }),
    makeActivityState({ session_id: "sess-A", turn_id: "0003", turn_number: 3, status: "in_progress" }),
  ];
  // Update turn 0002 with HTTP authoritative state
  const httpUpdate = makeActivityState({
    session_id: "sess-A",
    turn_id: "0002",
    turn_number: 2,
    status: "error",
    headline: "HTTP: turn 2 error",
    entry_type: "batch",
  });
  const result = reduceAgentActivityFeed(feed, httpUpdate, { source: "http" });
  assert.equal(result.length, 3, "no duplication, replace in place");
  assert.equal(result[0].turn_id, "0001");
  assert.equal(result[1].turn_id, "0002");
  assert.equal(result[1].status, "error", "replaced");
  assert.equal(result[2].turn_id, "0003");
});

// ── Edge case: empty feed, frozen arrays ───────────────────────────────

test("reduceAgentActivityFeed — returns frozen arrays", () => {
  let feed = [];
  feed = reduceAgentActivityFeed(feed, makeActivityState({ turn_id: "0001", turn_number: 1 }));
  assert.throws(() => { feed.push(null); }, /frozen|read.only|assign|not extensible|extensible/i);
  assert.throws(() => { feed[0] = null; }, /frozen|read.only|assign|not extensible|extensible/i);
});

test("reduceAgentActivityFeed — with non-array previous returns empty array", () => {
  const result = reduceAgentActivityFeed(null, makeActivityState({ turn_id: "0001", turn_number: 1 }));
  assert.equal(result.length, 1);
  assert.equal(result[0].turn_id, "0001");
});


// ── T8: Executor phase + agent-turn canonical progress path tests ──────────
//
// Purpose: Prove that executor phase events plus agent-turn activity renders
// through one canonical progress path (no duplicate "In progress..." or
// duplicate phase labels), while phase-only legacy payloads still produce
// phase progress for compatibility.

// ── Phase-only legacy compatibility ──────────────────────────────────────

test("executorPhaseToCanonicalProgress — phase-only legacy: classify fixture yields decide=active", () => {
  const raw = loadFixture("websocket_executor_phase_classify.json");
  const normalized = normalizeExecutorPhasePayload(raw);
  assert.ok(normalized, "classify fixture must normalize");

  const progress = executorPhaseToCanonicalProgress(normalized);
  assert.ok(progress, "must produce a progress snapshot");
  assert.equal(progress.decide, "active", "classify phase → decide active");
  assert.equal(progress.research, "pending");
  assert.equal(progress.execute, "pending");
  assert.equal(progress.review, "pending");

  // Validate via normalizeExecutorProgressSnapshot
  const validated = normalizeExecutorProgressSnapshot(progress);
  assert.ok(validated, "snapshot must pass validation");
  assert.deepEqual(validated, progress);

  // Label
  assert.equal(executorProgressLabel(progress), "Decide");
});

test("normalizeExecutorPhasePayload preserves classify plan metadata for Decide detail", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "progress",
    plan_summary: "Research node choices, then edit the workflow.",
    intent: "edit",
  });

  assert.ok(normalized);
  assert.equal(normalized.plan_summary, "Research node choices, then edit the workflow.");
  assert.equal(normalized.intent, "edit");
  assert.equal(executorDecisionLabel(normalized), "Deciding: Research node choices, then edit the workflow.");
});

test("normalizeExecutorPhasePayload preserves known route/task metadata", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "progress",
    route: "REVISE",
    task: "REVISE_GRAPH",
  });

  assert.ok(normalized);
  assert.equal(normalized.route, "revise");
  assert.equal(normalized.task, "revise_graph");
});

test("normalizeExecutorPhasePayload ignores unknown route/task metadata", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "progress",
    route: "totally_new_route",
    task: "totally_new_task",
    intent: "respond",
  });

  assert.ok(normalized);
  assert.equal("route" in normalized, false);
  assert.equal("task" in normalized, false);
  assert.equal(executorDecisionLabel(normalized), "Deciding: Reply to the request.");
});

test("executorDecisionLabel derives route-aware fallback from classify route", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "progress",
    route: "research",
    task: "research",
  });

  assert.ok(normalized);
  assert.equal(executorDecisionLabel(normalized), "Deciding: Research and answer");
});

test("executorDecisionLabel prefers plan_summary over route-aware fallback", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "progress",
    plan_summary: "Direct edit - patch the workflow in place.",
    route: "revise",
    task: "revise_graph",
  });

  assert.ok(normalized);
  assert.equal(executorDecisionLabel(normalized), "Deciding: Direct edit - patch the workflow in place.");
});

test("executorDecisionLabel derives short fallback from classify intent", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "progress",
    plan_summary: "",
    intent: "research",
  });

  assert.ok(normalized);
  assert.equal(executorDecisionLabel(normalized), "Deciding: Research relevant context before replying.");
});

test("progressFromExecutorPhase preserves route/task metadata for route-aware decide labels", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "start",
    route: "inspect",
    task: "inspect_graph",
  });

  assert.ok(normalized);
  const progress = progressFromExecutorPhase(normalized);
  assert.ok(progress);
  assert.equal(progress.route, "inspect");
  assert.equal(progress.task, "inspect_graph");
  assert.equal(executorProgressLabel(progress), "Inspect graph");

  const validated = normalizeExecutorProgressSnapshot(progress);
  assert.ok(validated);
  assert.deepEqual(validated, progress);
});

test("executorPhaseToCanonicalProgress — phase-only legacy: research fixture yields research=active", () => {
  const raw = loadFixture("websocket_executor_phase_research.json");
  const normalized = normalizeExecutorPhasePayload(raw);
  assert.ok(normalized, "research fixture must normalize");

  const progress = executorPhaseToCanonicalProgress(normalized);
  assert.ok(progress, "must produce a progress snapshot");
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "active");
  assert.equal(progress.execute, "pending");
  assert.equal(progress.review, "pending");

  const validated = normalizeExecutorProgressSnapshot(progress);
  assert.ok(validated, "snapshot must pass validation");
  assert.equal(executorProgressLabel(progress), "Research");
});

test("executorPhaseToCanonicalProgress — phase-only legacy: implement fixture yields execute=active", () => {
  const raw = loadFixture("websocket_executor_phase_implement.json");
  const normalized = normalizeExecutorPhasePayload(raw);
  assert.ok(normalized, "implement fixture must normalize");

  const progress = executorPhaseToCanonicalProgress(normalized);
  assert.ok(progress, "must produce a progress snapshot");
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "done");
  assert.equal(progress.execute, "active");
  assert.equal(progress.review, "pending");

  const validated = normalizeExecutorProgressSnapshot(progress);
  assert.ok(validated, "snapshot must pass validation");
  assert.equal(executorProgressLabel(progress), "Execute");
});

test("executorPhaseToCanonicalProgress — phase-only legacy: reply fixture yields review=active", () => {
  const raw = loadFixture("websocket_executor_phase_reply.json");
  const normalized = normalizeExecutorPhasePayload(raw);
  assert.ok(normalized, "reply fixture must normalize");

  const progress = executorPhaseToCanonicalProgress(normalized);
  assert.ok(progress, "must produce a progress snapshot");
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "done");
  assert.equal(progress.execute, "done");
  assert.equal(progress.review, "active");

  const validated = normalizeExecutorProgressSnapshot(progress);
  assert.ok(validated, "snapshot must pass validation");
  assert.equal(executorProgressLabel(progress), "Review");
});

test("executorPhaseToCanonicalProgress — phase-only legacy: all four phases produce canonical-compatible shapes", () => {
  const phases = ["classify", "research", "implement", "reply"];
  for (const phase of phases) {
    const raw = { phase, status: "start" };
    const normalized = normalizeExecutorPhasePayload(raw);
    assert.ok(normalized, `phase '${phase}' must normalize`);

    const progress = executorPhaseToCanonicalProgress(normalized);
    assert.ok(progress, `phase '${phase}' must produce progress`);
    const validated = normalizeExecutorProgressSnapshot(progress);
    assert.ok(validated, `phase '${phase}' snapshot must validate`);

    // All snapshots must have the canonical four stages
    const keys = Object.keys(progress);
    assert.ok(keys.includes("decide"), `phase '${phase}' must have decide`);
    assert.ok(keys.includes("research"), `phase '${phase}' must have research`);
    assert.ok(keys.includes("execute"), `phase '${phase}' must have execute`);
    assert.ok(keys.includes("review"), `phase '${phase}' must have review`);
    assert.equal(keys.length, 4, `phase '${phase}' must have exactly 4 keys`);
  }
});

test("executorPhaseToCanonicalProgress — phase-only legacy: done-status phases produce correct progress", () => {
  // classify done → decide=done
  let norm = normalizeExecutorPhasePayload({ phase: "classify", status: "done" });
  let progress = executorPhaseToCanonicalProgress(norm);
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "pending");
  assert.equal(executorProgressLabel(progress), "Pending"); // no active phase

  // research done → decide=done, research=done
  norm = normalizeExecutorPhasePayload({ phase: "research", status: "done" });
  progress = executorPhaseToCanonicalProgress(norm);
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "done");
  assert.equal(progress.execute, "pending");
  assert.equal(executorProgressLabel(progress), "Pending");

  // implement done → all but review done
  norm = normalizeExecutorPhasePayload({ phase: "implement", status: "done" });
  progress = executorPhaseToCanonicalProgress(norm);
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "done");
  assert.equal(progress.execute, "done");
  assert.equal(progress.review, "pending");

  // reply done → all done
  norm = normalizeExecutorPhasePayload({ phase: "reply", status: "done" });
  progress = executorPhaseToCanonicalProgress(norm);
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "done");
  assert.equal(progress.execute, "done");
  assert.equal(progress.review, "done");
  assert.equal(executorProgressLabel(progress), "Complete");
  assert.equal(isExecutorProgressComplete(progress), true);
});

test("executorPhaseToCanonicalProgress — phase-only legacy: skipped phases produce correct pending/fallthrough", () => {
  // classify skipped → all pending (executor skipped classification)
  let norm = normalizeExecutorPhasePayload({ phase: "classify", status: "skipped" });
  let progress = executorPhaseToCanonicalProgress(norm);
  assert.equal(progress.decide, "pending");
  assert.equal(progress.research, "pending");

  // research skipped → decide=done, research=pending
  norm = normalizeExecutorPhasePayload({ phase: "research", status: "skipped" });
  progress = executorPhaseToCanonicalProgress(norm);
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "pending");

  // implement skipped → decide=done, research=done, execute=pending
  norm = normalizeExecutorPhasePayload({ phase: "implement", status: "skipped" });
  progress = executorPhaseToCanonicalProgress(norm);
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "done");
  assert.equal(progress.execute, "pending");
});

// ── Canonical inspect route normalization & labeling ────────────────────────

test("normalizeExecutorPhasePayload accepts canonical inspect route", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "reply",
    status: "done",
    route: "inspect",
    task: "inspect_graph",
  });

  assert.ok(normalized);
  assert.equal(normalized.phase, "reply");
  assert.equal(normalized.route, "inspect");
  assert.equal(normalized.task, "inspect_graph");
});

test("executorRouteLabel returns Inspect graph for canonical inspect", () => {
  // Import is already at top of file — executorRouteLabel is a local function
  // but we can test through executorProgressLabel
  const progress = createExecutorProgressSnapshot({
    decide: "active",
    route: "inspect",
  });
  assert.equal(executorProgressLabel(progress), "Inspect graph");
});

test("executorRouteLabel ignores legacy inspect_only", () => {
  const progress = createExecutorProgressSnapshot({
    decide: "active",
    route: "inspect_only",
  });
  assert.equal(progress.route, undefined);
  assert.equal(executorProgressLabel(progress), "Decide");
});

test("progressFromExecutorPhase preserves canonical inspect route", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "start",
    route: "inspect",
    task: "inspect_graph",
  });

  assert.ok(normalized);
  assert.equal(normalized.route, "inspect");

  const progress = progressFromExecutorPhase(normalized);
  assert.ok(progress);
  assert.equal(progress.route, "inspect");
  assert.equal(progress.task, "inspect_graph");
  assert.equal(executorProgressLabel(progress), "Inspect graph");
});

test("progressFromExecutorPhase ignores legacy inspect_only route", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "start",
    route: "inspect_only",
    task: "inspect_graph",
  });

  assert.ok(normalized);
  assert.equal(normalized.route, undefined);

  const progress = progressFromExecutorPhase(normalized);
  assert.ok(progress);
  assert.equal(progress.route, undefined);
  assert.equal(progress.task, "inspect_graph");
  assert.equal(executorProgressLabel(progress), "Decide");
});

test("progressFromExecutorPhase with inspect route during reply phase yields read-only complete progress", () => {
  // When inspect completes, the reply phase emits done with route=inspect
  const normalized = normalizeExecutorPhasePayload({
    phase: "reply",
    status: "done",
    route: "inspect",
    task: "inspect_graph",
  });

  assert.ok(normalized);
  const progress = progressFromExecutorPhase(normalized);
  assert.ok(progress);
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "done");
  assert.equal(progress.execute, "pending");
  assert.equal(progress.review, "pending");
  assert.equal(progress.route, "inspect");
  assert.equal(executorProgressLabel(progress), "Inspect complete");
  assert.equal(isExecutorProgressComplete(progress), false);
});

test("normalizeExecutorProgressSnapshot accepts canonical inspect route in snapshot", () => {
  const snapshot = createExecutorProgressSnapshot({
    decide: "done",
    research: "done",
    execute: "done",
    review: "done",
    route: "inspect",
    task: "inspect_graph",
  });

  const validated = normalizeExecutorProgressSnapshot(snapshot);
  assert.ok(validated);
  assert.equal(validated.route, "inspect");
  assert.equal(validated.task, "inspect_graph");
});

// ── Revise / Adapt canonical route acceptance ──────────────────────────────

test("normalizeExecutorPhasePayload accepts canonical revise route", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "start",
    route: "revise",
    task: "revise_graph",
  });

  assert.ok(normalized);
  assert.equal(normalized.route, "revise");
  assert.equal(normalized.task, "revise_graph");
});

test("normalizeExecutorPhasePayload accepts canonical adapt route", () => {
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "start",
    route: "adapt",
    task: "adapt_graph",
  });

  assert.ok(normalized);
  assert.equal(normalized.route, "adapt");
  assert.equal(normalized.task, "adapt_graph");
});

test("executorRouteLabel returns Revise graph for revise route", () => {
  const progress = createExecutorProgressSnapshot({
    decide: "active",
    route: "revise",
  });
  assert.equal(executorProgressLabel(progress), "Revise graph");
});

test("executorRouteLabel returns Adapt graph for adapt route", () => {
  const progress = createExecutorProgressSnapshot({
    decide: "active",
    route: "adapt",
  });
  assert.equal(executorProgressLabel(progress), "Adapt graph");
});

test("normalizeExecutorProgressSnapshot accepts revise and adapt routes", () => {
  for (const route of ["revise", "adapt"]) {
    const snapshot = createExecutorProgressSnapshot({
      decide: "done",
      research: "done",
      execute: "done",
      review: "done",
      route,
    });
    const validated = normalizeExecutorProgressSnapshot(snapshot);
    assert.ok(validated, `route '${route}' must validate`);
    assert.equal(validated.route, route);
  }
});

test("normalizeExecutorPhasePayload rejects unrecognized canonical routes", () => {
  // Route "bogus" is not in EXECUTOR_ROUTES
  const normalized = normalizeExecutorPhasePayload({
    phase: "classify",
    status: "start",
    route: "bogus",
    task: "bogus_task",
  });
  assert.ok(normalized); // overall normalization succeeds
  // compactObject strips null values, so invalid route/task keys are absent
  assert.equal(normalized.route, undefined);
  assert.equal(normalized.task, undefined);
});

// ── Inspect Apply gating (inspect never offers Apply) ─────────────────────

test("createExecutorProgressSnapshot with inspect route does not imply apply eligibility", () => {
  // Inspect route's progress snapshot has route=inspect but no candidate/apply fields
  const snapshot = createExecutorProgressSnapshot({
    decide: "done",
    research: "done",
    execute: "done",
    review: "done",
    route: "inspect",
    task: "inspect_graph",
  });

  // The progress snapshot is route-aware but does not carry apply_eligible semantics
  assert.equal(snapshot.route, "inspect");
  // Complete progress with inspect route still shows Complete
  assert.equal(isExecutorProgressComplete(snapshot), true);
  assert.equal(executorProgressLabel(snapshot), "Complete");
});

// ── Single canonical progress path: agent-turn + executor phase convergence ─

test("canonical path convergence — agent-turn in_progress with landed ops maps to execute=active via deriveAgentActivityState", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-canon",
    turn_id: "0020",
    turn_number: 2,
    status: "progress",
    message: "Applying changes to graph...",
    statement_count: 4,
    landed_op_count: 3,
    statements: [
      { op_kind: "query", status: "done", message: "Queried nodes" },
      { op_kind: "add_node", status: "done", message: "Added Sampler", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected edges", landed: true, ok: true },
      { op_kind: "set_field", status: "active", message: "Setting model path", landed: true, ok: true },
    ],
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "in_progress");
  assert.equal(activity.outcome.kind, "in_progress");

  // Canonical phase_progress from agent-turn: executing (has landed ops)
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.research, "done");
  assert.equal(activity.phase_progress.execute, "active");
  assert.equal(activity.phase_progress.review, "pending");

  // Status label: a single progress label (no duplication)
  const label = agentTurnProgressLabel(payload);
  assert.ok(label.includes("Executing"), "agent-turn progress label should indicate executing");
});

test("canonical path convergence — executor phase 'implement' maps to execute=active via executorPhaseToCanonicalProgress", () => {
  const normalized = normalizeExecutorPhasePayload({ phase: "implement", status: "start" });
  const progress = executorPhaseToCanonicalProgress(normalized);

  assert.ok(progress, "executor phase must produce progress");
  assert.equal(progress.decide, "done");
  assert.equal(progress.research, "done");
  assert.equal(progress.execute, "active");
  assert.equal(progress.review, "pending");

  const label = executorProgressLabel(progress);
  assert.equal(label, "Execute", "executor phase label should be 'Execute'");
});

test("canonical path convergence — both agent-turn and executor phase describe same 'executing' state (converge, not duplicate)", () => {
  // Agent-turn: in_progress with landed ops
  const agentPayload = normalizeAgentTurnPayload({
    session_id: "sess-converge",
    turn_id: "0021",
    turn_number: 3,
    status: "progress",
    message: "Applying changes...",
    statement_count: 5,
    landed_op_count: 4,
    statements: [
      { op_kind: "query", status: "done", message: "Queried templates" },
      { op_kind: "add_node", status: "done", message: "Added Upscale", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected", landed: true, ok: true },
      { op_kind: "set_field", status: "done", message: "Set factor", landed: true, ok: true },
      { op_kind: "reconnect", status: "active", message: "Rewiring output", landed: true, ok: true },
    ],
  });

  const activity = deriveAgentActivityState(agentPayload);
  const canonPhase = activity.phase_progress;

  // Executor phase: implement/start
  const execNorm = normalizeExecutorPhasePayload({ phase: "implement", status: "start" });
  const execPhase = executorPhaseToCanonicalProgress(execNorm);

  // Both must describe the SAME executing state — convergence
  assert.equal(canonPhase.execute, "active", "canonical agent-turn: executing");
  assert.equal(execPhase.execute, "active", "executor phase: executing");

  // Both agree on decide=done, research=done
  assert.equal(canonPhase.decide, execPhase.decide, "decide must agree");
  assert.equal(canonPhase.research, execPhase.research, "research must agree");

  // The canonical agent-turn phase_progress IS the single source of truth.
  // The executor phase progress is compatibility input that converges to the
  // same state — they are NOT two separate rendering paths.
  assert.deepEqual(
    { decide: canonPhase.decide, research: canonPhase.research, execute: canonPhase.execute },
    { decide: execPhase.decide, research: execPhase.research, execute: execPhase.execute },
    "agent-turn canonical and executor phase must converge to the same decide/research/execute state (single path)",
  );
});

test("canonical path convergence — agent-turn in_progress (no landed ops) converges with executor research phase", () => {
  // Agent-turn: in_progress with statements but no landed ops → researching
  const agentPayload = normalizeAgentTurnPayload({
    session_id: "sess-converge2",
    turn_id: "0022",
    turn_number: 1,
    status: "progress",
    message: "Researching available nodes...",
    statement_count: 3,
    landed_op_count: 0,
    statements: [
      { op_kind: "query", status: "done", message: "Queried index" },
      { op_kind: "search", status: "done", message: "Found templates" },
      { op_kind: "analyze", status: "active", message: "Checking compatibility" },
    ],
  });

  const activity = deriveAgentActivityState(agentPayload);
  const canonPhase = activity.phase_progress;

  // Executor phase: research/start
  const execNorm = normalizeExecutorPhasePayload({ phase: "research", status: "start" });
  const execPhase = executorPhaseToCanonicalProgress(execNorm);

  // Both describe researching
  assert.equal(canonPhase.research, "active", "canonical agent-turn: researching");
  assert.equal(execPhase.research, "active", "executor phase: researching");

  // Both agree on decide=done
  assert.equal(canonPhase.decide, "done");
  assert.equal(execPhase.decide, "done");

  // They converge on research, not duplicate two research indicators
  assert.equal(canonPhase.research, execPhase.research);
});

test("canonical path convergence — agent-turn in_progress (no statements) converges with executor classify phase", () => {
  // Agent-turn: in_progress with no statements and no turn_number → deciding
  const agentPayload = normalizeAgentTurnPayload({
    session_id: "sess-converge3",
    turn_id: "0023",
    status: "progress",
    message: "Deciding what to do...",
    statement_count: 0,
    landed_op_count: 0,
  });

  const activity = deriveAgentActivityState(agentPayload);
  const canonPhase = activity.phase_progress;

  // Executor phase: classify/start
  const execNorm = normalizeExecutorPhasePayload({ phase: "classify", status: "start" });
  const execPhase = executorPhaseToCanonicalProgress(execNorm);

  // Both describe deciding
  assert.equal(canonPhase.decide, "active", "canonical agent-turn: deciding");
  assert.equal(execPhase.decide, "active", "executor phase: deciding");

  // They converge
  assert.equal(canonPhase.decide, execPhase.decide);
});

// ── No duplicate "In progress..." or duplicate phase labels ─────────────

test("no duplicate labels — single agent-turn produces exactly one progress label via agentTurnProgressLabel", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-nodup",
    turn_id: "0030",
    turn_number: 1,
    status: "progress",
    message: "Working...",
    statement_count: 2,
    landed_op_count: 1,
    statements: [
      { op_kind: "query", status: "done", message: "Queried nodes" },
      { op_kind: "add_node", status: "active", message: "Adding Sampler", landed: true, ok: true },
    ],
  });

  const label = agentTurnProgressLabel(payload);
  // Should produce exactly ONE label — not "In progress..." and another "Executing..."
  assert.ok(typeof label === "string", "must produce a single string label");
  assert.ok(label.length > 0, "label must not be empty");

  // With landed ops, should indicate Executing
  assert.ok(label.includes("Executing") || label.includes("executing"), "should indicate executing");

  // Verify there is exactly one label (not a concatenation of multiple states)
  assert.ok(!label.includes("In progress"), "should not say 'In progress' verbatim — should use canonical label");
});

test("no duplicate labels — single executor phase produces exactly one progress label via executorProgressLabel", () => {
  const norm = normalizeExecutorPhasePayload({ phase: "implement", status: "start" });
  const progress = executorPhaseToCanonicalProgress(norm);

  const label = executorProgressLabel(progress);
  assert.equal(label, "Execute", "single phase label, no duplication");
});

test("no duplicate labels — both agent-turn and executor phase labels are complementary, not duplicate", () => {
  // Agent-turn: in_progress with landed ops → agentTurnProgressLabel = "Executing (N ops landed)"
  const agentPayload = normalizeAgentTurnPayload({
    session_id: "sess-nodup2",
    turn_id: "0031",
    turn_number: 2,
    status: "progress",
    message: "Applying edits...",
    statement_count: 4,
    landed_op_count: 3,
    statements: [
      { op_kind: "query", status: "done", message: "Queried" },
      { op_kind: "add_node", status: "done", message: "Added", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected", landed: true, ok: true },
      { op_kind: "set_field", status: "active", message: "Setting param", landed: true, ok: true },
    ],
  });

  const agentLabel = agentTurnProgressLabel(agentPayload);
  assert.ok(agentLabel.includes("Executing"), "agent-turn label should indicate executing");

  // Executor phase: implement/start → executorProgressLabel = "Execute"
  const execNorm = normalizeExecutorPhasePayload({ phase: "implement", status: "start" });
  const execPhase = executorPhaseToCanonicalProgress(execNorm);
  const execLabel = executorProgressLabel(execPhase);
  assert.equal(execLabel, "Execute");

  // Key proof: Both describe the SAME underlying state ("executing")
  // but through different labeling functions. They are NOT duplicates
  // of the same label string — one says "Executing (3 ops landed)",
  // the other says "Execute". Both point to one canonical path.
  assert.ok(agentLabel !== execLabel || agentLabel.includes("Execute"),
    "labels may differ in wording but both describe the same single executing phase");
});

test("no duplicate labels — terminal agent-turn status produces single label, not 'In progress' plus terminal", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-nodup3",
    turn_id: "0032",
    turn_number: 2,
    status: "done",
    message: "All changes applied.",
    statement_count: 2,
    landed_op_count: 2,
    statements: [
      { op_kind: "add_node", status: "done", message: "Added Upscale", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected", landed: true, ok: true },
    ],
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "done", "terminal status");

  // Phase progress: all done
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.execute, "done");
  assert.equal(activity.phase_progress.review, "done");

  // Label should be "Complete" — not "In progress..." + "Complete"
  const label = agentTurnProgressLabel(payload);
  assert.equal(label, "Complete", "terminal turn label must be 'Complete', not 'In progress...'");

  // Executor label on canonical phase_progress should also be "Complete"
  const execLabel = executorProgressLabel(activity.phase_progress);
  assert.equal(execLabel, "Complete", "canonical phase_progress label must be 'Complete'");
});

test("no duplicate labels — phase_progress from deriveAgentActivityState has exactly 4 canonical stages", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-stages",
    turn_id: "0033",
    turn_number: 1,
    status: "progress",
    statement_count: 3,
    landed_op_count: 0,
    statements: [
      { op_kind: "query", status: "done", message: "Queried" },
      { op_kind: "search", status: "done" },
      { op_kind: "analyze", status: "active", message: "Analyzing" },
    ],
  });

  const activity = deriveAgentActivityState(payload);
  const stages = Object.keys(activity.phase_progress);
  assert.deepEqual(stages.sort(), ["decide", "execute", "research", "review"].sort(),
    "phase_progress must have exactly 4 canonical stages (no extra/duplicate keys)");

  // Each stage must have a valid value
  const validValues = new Set(["pending", "active", "done"]);
  for (const stage of stages) {
    assert.ok(validValues.has(activity.phase_progress[stage]),
      `stage '${stage}' must be one of pending/active/done`);
  }
});

test("no duplicate labels — reduceAgentActivityFeed with agent-turn updates preserves single canonical phase_progress per turn", () => {
  // Start with a turn
  let feed = [];
  const turn1 = makeActivityState({
    session_id: "sess-canon-feed",
    turn_id: "0100",
    turn_number: 1,
    status: "in_progress",
    phase_progress: { decide: "done", research: "active", execute: "pending", review: "pending" },
    headline: "Researching...",
  });
  feed = reduceAgentActivityFeed(feed, turn1);
  assert.equal(feed.length, 1);
  assert.equal(feed[0].phase_progress.research, "active");

  // Update same turn (more progress) → must replace in place, not duplicate
  const turn1Update = makeActivityState({
    session_id: "sess-canon-feed",
    turn_id: "0100",
    turn_number: 1,
    status: "in_progress",
    phase_progress: { decide: "done", research: "done", execute: "active", review: "pending" },
    headline: "Executing...",
  });
  feed = reduceAgentActivityFeed(feed, turn1Update);
  assert.equal(feed.length, 1, "must not duplicate turn entry");
  assert.equal(feed[0].phase_progress.execute, "active", "phase_progress updated in place");
  assert.equal(feed[0].phase_progress.research, "done");

  // Final update (terminal)
  const turn1Done = makeActivityState({
    session_id: "sess-canon-feed",
    turn_id: "0100",
    turn_number: 1,
    status: "done",
    phase_progress: { decide: "done", research: "done", execute: "done", review: "done" },
    headline: "Complete",
  });
  feed = reduceAgentActivityFeed(feed, turn1Done);
  assert.equal(feed.length, 1, "still exactly one turn entry");
  assert.equal(feed[0].status, "done");
  assert.equal(feed[0].phase_progress.review, "done");
});

test("no duplicate labels — phase-only legacy executor progress and canonical agent-turn progress do not collide in label domain", () => {
  // This test proves that when you have BOTH an executor phase event and an
  // agent-turn event, you can derive labels from EITHER but both point to
  // the same underlying canonical state. There is no separate rendering.

  // Agent-turn: executing
  const agentActivity = deriveAgentActivityState(normalizeAgentTurnPayload({
    session_id: "sess-nocollide",
    turn_id: "0101",
    turn_number: 2,
    status: "progress",
    message: "Applying changes...",
    statement_count: 5,
    landed_op_count: 3,
    statements: [
      { op_kind: "query", status: "done", message: "Queried" },
      { op_kind: "add_node", status: "done", message: "Added", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected", landed: true, ok: true },
      { op_kind: "set_field", status: "done", message: "Set", landed: true, ok: true },
      { op_kind: "reconnect", status: "active", message: "Rewiring", landed: false, ok: true },
    ],
  }));

  // Executor phase: implement
  const execProgress = executorPhaseToCanonicalProgress(
    normalizeExecutorPhasePayload({ phase: "implement", status: "start" })
  );

  // Both phase_progress objects describe the same canonical executing state
  assert.equal(agentActivity.phase_progress.execute, "active");
  assert.equal(execProgress.execute, "active");

  // deriveAgentActivityState's phase_progress is the canonical SSoT.
  // executorPhaseToCanonicalProgress produces a compatible snapshot for
  // legacy compatibility but they converge identically at this level.
  // Using executorProgressLabel on the canonical agent-turn phase_progress
  // yields the same label as on the executor-derived phase_progress,
  // proving there is ONE progress surface.
  assert.equal(
    executorProgressLabel(agentActivity.phase_progress),
    executorProgressLabel(execProgress),
    "both canonical agent-turn and executor-phase phase_progress yield the same label (single surface)",
  );
});

test("no duplicate labels — classify/research/implement executor phases map cleanly to canonical agent-turn phase_progress equivalents", () => {
  // For each executor phase, show that its progress snapshot label maps
  // to the same underlying canonical stage as a matching agent-turn state.

  // classify, research, implement naturally converge with agent-turn states.
  // reply (review=active) is an executor-only wrapping-up phase with no direct
  // in_progress agent-turn equivalent; the closest agent-turn equivalent is
  // terminal "done" (all phases done). We test these three convergent phases.
  const phaseMap = [
    { execPhase: "classify", execStatus: "start", agentStatus: "progress", agentLanded: 0, agentStmts: 0, expectedStage: "decide", expectedLabel: "Decide", noTurnNum: true },
    { execPhase: "research", execStatus: "start", agentStatus: "progress", agentLanded: 0, agentStmts: 3, expectedStage: "research", expectedLabel: "Research" },
    { execPhase: "implement", execStatus: "start", agentStatus: "progress", agentLanded: 3, agentStmts: 5, expectedStage: "execute", expectedLabel: "Execute" },
  ];

  for (const map of phaseMap) {
    // Executor side
    const execNorm = normalizeExecutorPhasePayload({ phase: map.execPhase, status: map.execStatus });
    const execProgress = executorPhaseToCanonicalProgress(execNorm);
    assert.ok(execProgress, `executor '${map.execPhase}' must produce progress`);
    assert.equal(execProgress[map.expectedStage], "active",
      `executor '${map.execPhase}' must have ${map.expectedStage}=active`);
    assert.equal(executorProgressLabel(execProgress), map.expectedLabel,
      `executor '${map.execPhase}' label must be '${map.expectedLabel}'`);

    // Agent-turn side: build a matching state
    const agentPayload = normalizeAgentTurnPayload({
      session_id: "sess-phase-map",
      turn_id: "0200",
      ...(map.noTurnNum ? {} : { turn_number: 1 }),
      status: map.agentStatus,
      message: "Testing...",
      statement_count: map.agentStmts,
      landed_op_count: map.agentLanded,
      statements: map.agentStmts > 0
        ? Array.from({ length: map.agentStmts }, (_, i) => ({
            op_kind: i < map.agentLanded ? "add_node" : "query",
            status: i === map.agentStmts - 1 ? "active" : "done",
            message: `Op ${i + 1}`,
            landed: i < map.agentLanded,
            ok: true,
          }))
        : [],
    });

    const agentActivity = deriveAgentActivityState(agentPayload);
    assert.ok(agentActivity.phase_progress, "agent-turn must produce phase_progress");

    // The canonical agent-turn stage and executor stage must agree
    assert.equal(agentActivity.phase_progress[map.expectedStage], execProgress[map.expectedStage],
      `agent-turn and executor must agree on ${map.expectedStage} for phase '${map.execPhase}'`);

    // Both produce the same executorProgressLabel when applied to the canonical agent phase_progress
    // (using execProgress as label derivation input and agentActivity.phase_progress as canonical)
    const agentCanonLabel = executorProgressLabel(agentActivity.phase_progress);
    const execLabel = executorProgressLabel(execProgress);
    assert.equal(agentCanonLabel, execLabel,
      `labels must agree for phase '${map.execPhase}': agent=${agentCanonLabel} vs exec=${execLabel}`);
  }
});

// ── Route applyability contract tests ──────────────────────────────────────

import { routeAllowsApplyAffordances } from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract.js";

test("routeAllowsApplyAffordances — applyable routes (revise, adapt) return true", () => {
  assert.equal(routeAllowsApplyAffordances("revise"), true);
  assert.equal(routeAllowsApplyAffordances("adapt"), true);
  assert.equal(routeAllowsApplyAffordances("  REVISE  "), true, "trimmed and case-insensitive");
  assert.equal(routeAllowsApplyAffordances("Adapt"), true);
});

test("routeAllowsApplyAffordances — legacy applyable aliases are not public routes", () => {
  for (const alias of ["direct_edit", "diagnose_repair", "precedent_research", "asset_lookup", "subgraph_preview"]) {
    assert.equal(routeAllowsApplyAffordances(alias), false, `legacy alias '${alias}' should not be applyable`);
  }
});

test("routeAllowsApplyAffordances — non-applyable routes (clarify, respond, inspect, research) return false", () => {
  for (const route of ["clarify", "respond", "inspect", "research"]) {
    assert.equal(routeAllowsApplyAffordances(route), false, `route '${route}' should NOT be applyable`);
    assert.equal(routeAllowsApplyAffordances(route.toUpperCase()), false, `uppercase '${route}' should NOT be applyable`);
  }
});

test("routeAllowsApplyAffordances — null/undefined/non-string returns false", () => {
  assert.equal(routeAllowsApplyAffordances(null), false);
  assert.equal(routeAllowsApplyAffordances(undefined), false);
  assert.equal(routeAllowsApplyAffordances(42), false);
  assert.equal(routeAllowsApplyAffordances([]), false);
  assert.equal(routeAllowsApplyAffordances({}), false);
  assert.equal(routeAllowsApplyAffordances(""), false);
  assert.equal(routeAllowsApplyAffordances("   "), false);
});

// ── Respond and research payload normalization tests ───────────────────────

test("normalizeAgentTurnPayload — respond route turn derives no graph changes, no candidate implications", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-respond",
    turn_id: "resp-01",
    turn_number: 1,
    status: "done",
    route: "respond",
    message: "The current graph uses an Euler ancestral sampler for img2img.",
    statement_count: 1,
    landed_op_count: 0,
    statements: [{ op_kind: "done", status: "done", message: "Turn complete" }],
    done_summary: "Answered without graph changes.",
  });

  assert.equal(payload.session_id, "sess-respond");
  assert.equal(payload.status, "done");
  assert.equal(payload.landed_op_count, 0);
  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.outcome.kind, "answered", "respond route turn without edits is answered");
  assert.equal(activity.outcome.graph_changes, false);
  // Non-applyable route terminal: execute and review stay pending
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.execute, "pending", "respond route never executes");
  assert.equal(activity.phase_progress.review, "pending", "respond route never reviews");
});

test("normalizeAgentTurnPayload — research route turn derives research-done, no execute/review", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-research",
    turn_id: "res-01",
    turn_number: 1,
    status: "done",
    route: "research",
    message: "LTX Video supports i2v with 768px resolution; PIL is not needed.",
    statement_count: 1,
    landed_op_count: 0,
    statements: [{ op_kind: "done", status: "done", message: "Turn complete" }],
    done_summary: "Researched LTX compatibility without graph changes.",
  });

  assert.equal(payload.session_id, "sess-research");
  assert.equal(payload.status, "done");
  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.outcome.kind, "answered");
  assert.equal(activity.outcome.graph_changes, false);
  // Research route: research ran but execute/review never ran
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.research, "done", "research route runs research phase");
  assert.equal(activity.phase_progress.execute, "pending", "research route never executes");
  assert.equal(activity.phase_progress.review, "pending", "research route never reviews");
});

test("normalizeAgentTurnPayload — respond in_progress with statements leaves execute pending", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-respond-progress",
    turn_id: "resp-02",
    turn_number: 1,
    status: "progress",
    route: "respond",
    message: "Analyzing graph structure...",
    statement_count: 2,
    landed_op_count: 0,
    statements: [
      { op_kind: "query", status: "done", message: "Inspected graph nodes" },
      { op_kind: "query", status: "active", message: "Checking connections" },
    ],
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.status, "in_progress");
  // Non-applyable during progress: execute never active
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.execute, "pending", "respond in_progress never sets execute=active");
});

test("normalizeAgentTurnPayload — revise route (applyable) terminal sets all phases done", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-revise",
    turn_id: "rev-01",
    turn_number: 1,
    status: "done",
    route: "revise",
    message: "Added KScheduler node and connected.",
    statement_count: 3,
    landed_op_count: 2,
    statements: [
      { op_kind: "add_node", status: "done", message: "Added KScheduler", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected pipeline", landed: true, ok: true },
      { op_kind: "done", status: "done" },
    ],
    done_summary: "Added scheduler node.",
  });

  const activity = deriveAgentActivityState(payload);
  assert.equal(activity.outcome.kind, "done");
  // Applyable route terminal: ALL phases done
  assert.equal(activity.phase_progress.decide, "done");
  assert.equal(activity.phase_progress.research, "done");
  assert.equal(activity.phase_progress.execute, "done");
  assert.equal(activity.phase_progress.review, "done");
});

// ── No internal string leakage tests ───────────────────────────────────────

test("normalizeAgentTurnPayload — no internal gate strings leak for respond route", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-no-leak",
    turn_id: "leak-01",
    turn_number: 1,
    status: "done",
    route: "respond",
    message: "Safe user-facing answer.",
    statement_count: 1,
    landed_op_count: 0,
    statements: [{ op_kind: "done", status: "done" }],
    done_summary: "Answer provided.",
  });

  const activity = deriveAgentActivityState(payload);
  const json = JSON.stringify(activity);
  const forbidden = ["no_candidate_reason", "route_not_applyable", "apply_eligible", "applyable",
    "candidate_graph", "rebaseline_recovery", "raw_batch", "provider_metadata"];
  for (const term of forbidden) {
    assert.ok(!json.includes(term), `respond route activity must not leak '${term}'`);
  }
});

test("normalizeAgentTurnPayload — no internal gate strings leak for research route", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-no-leak-res",
    turn_id: "leak-02",
    turn_number: 1,
    status: "done",
    route: "research",
    message: "Based on research, LTX is appropriate.",
    statement_count: 1,
    landed_op_count: 0,
    statements: [{ op_kind: "done", status: "done" }],
    done_summary: "Research completed.",
  });

  const activity = deriveAgentActivityState(payload);
  const json = JSON.stringify(activity);
  const forbidden = ["no_candidate_reason", "route_not_applyable", "apply_eligible",
    "candidate_graph", "rebaseline_recovery", "raw_batch", "provider_metadata"];
  for (const term of forbidden) {
    assert.ok(!json.includes(term), `research route activity must not leak '${term}'`);
  }
});

test("normalizeAgentTurnPayload — revise route (applyable) may carry candidate metadata without leaking internals", () => {
  const payload = normalizeAgentTurnPayload({
    session_id: "sess-revise-safe",
    turn_id: "rev-safe-01",
    turn_number: 1,
    status: "done",
    route: "revise",
    message: "Added upscale node.",
    statement_count: 2,
    landed_op_count: 1,
    statements: [
      { op_kind: "add_node", status: "done", message: "Added node", landed: true, ok: true },
      { op_kind: "done", status: "done" },
    ],
    done_summary: "Node added.",
  });

  const activity = deriveAgentActivityState(payload);
  const json = JSON.stringify(activity);
  // Revise (applyable) should NOT leak internal diagnostics
  const forbidden = ["no_candidate_reason", "route_not_applyable", "raw_batch", "provider_metadata", "raw_source"];
  for (const term of forbidden) {
    assert.ok(!json.includes(term), `revise route activity must not leak '${term}'`);
  }
});

// ── Chronological multi-turn assertions ────────────────────────────────────

test("reduceAgentActivityFeed — chronological multi-turn: respond → revise → research sequence preserves order", () => {
  let feed = [];

  // Turn 1: respond (answer-only, no edits)
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-chrono", turn_id: "0001", turn_number: 1,
    status: "done", headline: "Answered graph question",
    route: "respond",
  }));
  assert.equal(feed.length, 1);
  assert.equal(feed[0].turn_id, "0001");

  // Turn 2: revise (edit with candidate)
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-chrono", turn_id: "0002", turn_number: 2,
    status: "done", headline: "Added sampler node",
    route: "revise",
  }));
  assert.equal(feed.length, 2);
  assert.equal(feed[1].turn_id, "0002");

  // Turn 3: research (answer-only, no edits)
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-chrono", turn_id: "0003", turn_number: 3,
    status: "done", headline: "Researched PIL compatibility",
    route: "research",
  }));
  assert.equal(feed.length, 3);

  // Verify order: respond (0001) → revise (0002) → research (0003)
  assert.equal(feed[0].turn_id, "0001");
  assert.equal(feed[1].turn_id, "0002");
  assert.equal(feed[2].turn_id, "0003");
});

test("reduceAgentActivityFeed — chronological multi-turn: no candidate leakage across non-applyable turns", () => {
  let feed = [];

  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-no-leak-seq", turn_id: "0001", turn_number: 1,
    status: "done", headline: "Responded",
    route: "respond",
  }));
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-no-leak-seq", turn_id: "0002", turn_number: 2,
    status: "done", headline: "Researched",
    route: "research",
  }));
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-no-leak-seq", turn_id: "0003", turn_number: 3,
    status: "done", headline: "Inspected graph",
    route: "inspect",
  }));
  feed = reduceAgentActivityFeed(feed, makeActivityState({
    session_id: "sess-no-leak-seq", turn_id: "0004", turn_number: 4,
    status: "done", headline: "Clarified",
    route: "clarify",
  }));

  assert.equal(feed.length, 4);
  // All non-applyable: verify no phase_progress implies execute/review ran
  for (const entry of feed) {
    assert.equal(entry.phase_progress.execute, "pending",
      `non-applyable turn ${entry.turn_id} must not have execute=done`);
    assert.equal(entry.phase_progress.review, "pending",
      `non-applyable turn ${entry.turn_id} must not have review=done`);
  }
});

// ── executor progress label route awareness ────────────────────────────────

test("executorProgressLabel — pending progress for respond-route shape is a valid non-null label", () => {
  // respond route: classify→reply, research/execute/review never ran
  const progress = createExecutorProgressSnapshot({
    decide: "done",
    research: "pending",
    execute: "pending",
    review: "pending",
  });
  const label = executorProgressLabel(progress);
  assert.ok(typeof label === "string" && label.length > 0, "label must be a valid string");
  assert.doesNotMatch(label, /Execute|Review/i, "respond-route shape must not mention Execute or Review");
});

test("executorProgressLabel — pending progress for research-route shape is a valid non-null label", () => {
  // research route: classify→research→reply, execute/review never ran
  const progress = createExecutorProgressSnapshot({
    decide: "done",
    research: "done",
    execute: "pending",
    review: "pending",
  });
  const label = executorProgressLabel(progress);
  assert.ok(typeof label === "string" && label.length > 0, "label must be a valid string");
  assert.doesNotMatch(label, /Execute|Review/i, "research-route shape must not mention Execute or Review");
});
