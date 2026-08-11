import test from "node:test";
import assert from "node:assert/strict";

import { createBrowserHarness } from "./harness.mjs";
import {
  PANEL_STATE,
  RENDER_SECTIONS,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";
// The exact clone used by the replay-capture path: captureReplayBaseline
// imports this module as clonePlainData and clones chatMessages,
// transcriptMessages, candidateGraph, candidateReport, changeDetails, and the
// rest through it.  It is dependency-free (no Node builtins / DOM), so it is
// imported directly here to pin its cycle contract (T-033 / S8).
import { jsonClone } from "../../vibecomfy/comfy_nodes/web/json_clone.js";

const LS_AGENTIC_REPLAY_ENABLED = "vibecomfy_agentic_replay_enabled";

function waitFor(predicate, { attempts = 50 } = {}) {
  return new Promise((resolve, reject) => {
    let index = 0;
    function tick() {
      if (predicate()) {
        resolve();
        return;
      }
      if (index >= attempts) {
        reject(new Error("waitFor timed out"));
        return;
      }
      index += 1;
      setTimeout(tick, 0);
    }
    tick();
  });
}

function makeRunsResponse() {
  return {
    status: 200,
    body: {
      ok: true,
      runs: [
        { run_id: "run_2026", label: "Run 2026" },
        { run_id: "run_2025", label: "Run 2025" },
      ],
    },
  };
}

function makeTestsResponse() {
  return {
    status: 200,
    body: {
      ok: true,
      tests: [
        { test_id: "test_alpha", label: "Test Alpha" },
        { test_id: "test_beta", label: "Test Beta" },
      ],
    },
  };
}

function makeReplayScenario(overrides = {}) {
  return {
    status: 200,
    body: {
      ok: true,
      run_id: "run_2026",
      test_id: "test_alpha",
      query: "Add a reroute node between the sampler and save image",
      reply: "I inserted the reroute node and kept the existing flow intact.",
      original_graph: {
        nodes: [{ id: 1, type: "Sampler", properties: { vibecomfy_uid: "sampler-1" } }],
        links: [],
      },
      candidate_graph: {
        nodes: [
          { id: 1, type: "Sampler", properties: { vibecomfy_uid: "sampler-1" } },
          { id: 2, type: "Reroute", properties: { vibecomfy_uid: "reroute-2" } },
        ],
        links: [],
      },
      change_details: {
        summary: "Inserted a reroute node.",
        statements: [{ op_kind: "add_node", message: "Added Reroute node" }],
      },
      response_details: {
        turn_id: "turn-replay-1",
        summary: "Visible frontend detail",
      },
      eligibility: {
        applyable: true,
        reason: "applyable",
        warnings: [],
      },
      session_id: "session-replay-1",
      turn_id: "turn-replay-1",
      stages: [
        { id: "sent", label: "Sent" },
        { id: "thinking", label: "Thinking" },
        { id: "ready_to_apply", label: "Ready to apply" },
        { id: "applied", label: "Applied" },
      ],
      ...overrides,
    },
  };
}

function makePanelState(overrides = {}) {
  return {
    phase: PANEL_STATE.IDLE,
    sessionId: null,
    turnId: null,
    baselineTurnId: null,
    chatScopeId: null,
    chatScopeFingerprint: null,
    candidateScopeId: null,
    submittingScopeId: null,
    candidateGraph: null,
    candidateGraphHash: null,
    candidateReport: null,
    serverSubmitGraphHash: null,
    message: null,
    failure: null,
    clarification: null,
    applyAllowed: false,
    applyEligibility: null,
    canvasApplyAllowed: false,
    queueAllowed: false,
    auditRef: null,
    debugPayload: null,
    inFlightSubmit: false,
    submitAbortController: null,
    submitEpoch: null,
    inFlightApply: false,
    inFlightRebaseline: false,
    rebaselinePending: false,
    rebaselineRecovery: null,
    lastSubmit: null,
    lastAppliedChanges: null,
    lastSubmitFieldChanges: null,
    changeDetails: null,
    chatMessages: [],
    transcriptMessages: [],
    responseDetails: {},
    executionEvents: [],
    auditArtifacts: [],
    debugDiagnostics: {},
    compartmentIndexes: {
      responseDetailsByTurnId: {},
      executionEventsByKey: {},
      auditArtifactsByTurnId: {},
    },
    chatRehydrateEpoch: 0,
    chatRehydrateCommittedEpoch: 0,
    syntheticAgentMessage: null,
    deltaOps: null,
    expandedBubbleTurnKeys: {},
    ...overrides,
  };
}

function keyEvent(key) {
  return {
    type: "keydown",
    key,
    cancelable: true,
    defaultPrevented: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
    stopPropagation() {},
  };
}

test("disabled replay install returns null and emits no UI or network traffic", async () => {
  const harness = await createBrowserHarness();
  try {
    const replay = await harness.loadAgenticReplay();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const panel = { shell, state: makePanelState() };
    const controls = replay.installAgenticReplay(panel, { headerRight });

    assert.equal(controls, null, "installAgenticReplay should return null when disabled");
    assert.equal(shell.children.length, 0, "disabled replay should not mount toolbar DOM");
    assert.equal(headerRight.children.length, 0, "disabled replay should not mount toggle button");
    assert.equal(harness.requests.length, 0, "disabled replay should not fetch any endpoints");
  } finally {
    await harness.dispose();
  }
});

test("replay selectors, stage projection, reverse navigation, and clear cleanup stay in sync", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agentic-replay/runs": makeRunsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests": makeTestsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests/test_alpha": makeReplayScenario(),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_AGENTIC_REPLAY_ENABLED, "1");
    const replay = await harness.loadAgenticReplay();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const originalGraphCalls = [];
    const candidateGraphCalls = [];
    const scheduledRenders = [];
    const panel = {
      shell,
      state: makePanelState({
        phase: PANEL_STATE.AWAITING_REVIEW,
        chatMessages: [{ role: "agent", text: "stale message" }],
        transcriptMessages: [{ role: "agent", text: "stale transcript" }],
        candidateGraph: { nodes: [{ id: 99 }], links: [] },
        candidateBaselineGraph: { nodes: [{ id: 98 }], links: [] },
        candidateReport: { stale: true },
        applyAllowed: true,
        applyEligibility: { applyable: false, reason: "stale" },
        canvasApplyAllowed: true,
        queueAllowed: true,
        failure: { message: "stale failure" },
        clarification: { question: "stale clarification" },
        responseDetails: { stale: true },
        changeDetails: { summary: "stale change details" },
        lastAppliedChanges: { summary: "stale applied changes" },
        expandedBubbleTurnKeys: { "turn:stale": true },
        __demoMode: true,
      }),
    };
    const controls = replay.installAgenticReplay(panel, {
      headerRight,
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: () => {},
        scheduleRenderAgentPanel: (reason, activePanel, sections) => {
          scheduledRenders.push({ reason, activePanel, sections });
        },
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
      applyReplayOriginalGraph(graph) {
        originalGraphCalls.push(graph);
      },
      applyReplayGraphCandidate(graph) {
        candidateGraphCalls.push(graph);
      },
    });

    await waitFor(() => controls.runSelect.children.length > 1);
    assert.equal(headerRight.children.length, 1, "toggle mounts in the header");
    assert.ok(
      harness.requests.some((request) => request.url === "/vibecomfy/agentic-replay/runs"),
      "install should load the replay runs list",
    );

    controls.runSelect.value = "run_2026";
    controls.runSelect.dispatchEvent({ type: "change", target: controls.runSelect });
    await waitFor(() => controls.testSelect.children.length > 1);

    assert.ok(
      harness.requests.some(
        (request) => request.url === "/vibecomfy/agentic-replay/runs/run_2026/tests",
      ),
      "run selection should load the run's tests",
    );

    controls.testSelect.value = "test_alpha";
    controls.testSelect.dispatchEvent({ type: "change", target: controls.testSelect });
    assert.equal(controls.loadButton.disabled, false, "load enables once both selectors are chosen");

    controls.loadButton.click();
    await waitFor(() => controls.stageLabel.textContent === "1/4 — Sent");

    assert.deepEqual(
      controls._getStages().map((stage) => stage.id),
      ["sent", "thinking", "ready_to_apply", "applied"],
      "replay navigation follows the backend-returned stage list",
    );
    assert.equal(originalGraphCalls.length, 1, "sent restores the original graph");
    assert.equal(candidateGraphCalls.length, 0, "candidate apply has not run yet");
    assert.deepEqual(panel.state.chatMessages.map((message) => message.role), ["user"]);
    assert.deepEqual(panel.state.transcriptMessages, panel.state.chatMessages, "thread mirrors chat");
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "sent is an idle panel state");
    assert.equal(panel.state.candidateGraph, null, "sent clears stale candidate data");
    assert.equal(panel.state.applyEligibility, null, "sent clears stale apply eligibility");
    assert.equal(
      panel.state.responseDetails?.["turn-replay-1"]?.turn?.turnId,
      "turn-replay-1",
      "sent projects replay transcript details through the canonical compartment",
    );
    assert.equal(panel.state.failure, null, "sent clears stale failures");
    assert.equal(panel.state.changeDetails, null, "sent clears stale change details");
    assert.equal(
      panel.state.lastAppliedChanges?.summary,
      "stale applied changes",
      "sent preserves baseline applied-change metadata until replay exit",
    );
    assert.deepEqual(
      panel.state.expandedBubbleTurnKeys,
      { "turn:stale": true },
      "sent preserves thread-owned expansion state instead of mutating it",
    );
    assert.equal(panel.state.__demoMode, undefined, "sent is not in demo mode");
    assert.equal(panel.state._replay?.stage, "sent", "sent records the active replay stage");

    controls.toolbar.dispatchEvent(keyEvent("ArrowRight"));
    assert.equal(controls.stageLabel.textContent, "2/4 — Thinking");
    assert.equal(originalGraphCalls.length, 2, "thinking keeps the original graph on the canvas");
    assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING, "thinking uses submitting phase");
    assert.equal(panel.state.chatMessages.length, 2, "thinking adds a pending agent bubble");
    assert.equal(panel.state.chatMessages[1].pending_response, true, "thinking agent bubble is pending");
    assert.equal(panel.state.candidateGraph, null, "thinking does not leak candidate state");
    assert.equal(panel.state.applyEligibility, null, "thinking clears apply eligibility");
    assert.equal(panel.state.__demoMode, undefined, "thinking remains outside demo mode");
    assert.equal(panel.state._replay?.stage, "thinking", "thinking updates replay bookkeeping");

    controls.nextButton.click();
    assert.equal(controls.stageLabel.textContent, "3/4 — Ready to apply");
    assert.equal(originalGraphCalls.length, 3, "ready-to-apply keeps the original graph visible");
    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "ready-to-apply restores review state");
    assert.deepEqual(panel.state.candidateGraph, makeReplayScenario().body.candidate_graph);
    assert.equal(panel.state.applyAllowed, false, "replay candidate carries no production Apply authority");
    assert.equal(panel.state.canvasApplyAllowed, false, "replay candidate cannot authorize canvas Apply");
    assert.equal(
      panel.state.responseDetails?.["turn-replay-1"]?.turn?.turnId,
      "turn-replay-1",
      "ready-to-apply keeps canonical response details for the active turn",
    );
    assert.equal(panel.state.changeDetails?.summary, "Inserted a reroute node.");
    assert.equal(panel.state.__demoMode, true, "candidate-visible stages enter demo mode");
    assert.equal(panel.state._replay?.stage, "ready_to_apply", "ready-to-apply updates replay bookkeeping");

    controls.toolbar.dispatchEvent(keyEvent("ArrowRight"));
    assert.equal(controls.stageLabel.textContent, "4/4 — Applied");
    assert.equal(candidateGraphCalls.length, 1, "applied uses the candidate-graph callback");
    assert.equal(
      panel.state.phase,
      PANEL_STATE.AWAITING_REVIEW,
      "applied without a resolved apply result remains a visualization-only candidate state",
    );
    assert.equal(panel.state.applyAllowed, false, "visualization-only replay remains non-authoritative");
    assert.equal(panel.state.canvasApplyAllowed, false, "visualization-only replay cannot authorize canvas Apply");
    assert.equal(panel.state.__demoMode, true, "applied remains in demo mode until clear");
    assert.equal(panel.state.lastAppliedChanges, null, "applied does not reflect apply success without fixture evidence");

    controls.prevButton.click();
    assert.equal(controls.stageLabel.textContent, "3/4 — Ready to apply");
    assert.equal(originalGraphCalls.length, 4, "reverse navigation restores the original graph");
    assert.equal(panel.state.lastAppliedChanges, null, "reverse navigation rebuilds from baseline before replaying commits");
    assert.equal(panel.state.__demoMode, true, "reverse navigation keeps demo mode for review stage");

    controls.toolbar.dispatchEvent(keyEvent("ArrowLeft"));
    assert.equal(controls.stageLabel.textContent, "2/4 — Thinking");
    assert.equal(originalGraphCalls.length, 5, "reverse navigation keeps restoring the original graph");
    assert.equal(panel.state.candidateGraph, null, "thinking clears candidate graph after reverse navigation");
    assert.equal(panel.state.applyEligibility, null, "thinking clears eligibility after reverse navigation");
    assert.equal(panel.state.__demoMode, undefined, "thinking drops demo mode after reverse navigation");

    controls.clearButton.click();
    assert.equal(originalGraphCalls.length, 6, "clear restores the original graph snapshot");
    assert.equal(controls._getReplayActive(), false, "clear exits replay mode");
    assert.equal(controls.stageLabel.textContent, "", "clear removes the stage label");
    assert.equal(controls.prevButton.disabled, true, "clear disables reverse navigation");
    assert.equal(controls.nextButton.disabled, true, "clear disables forward navigation");
    assert.deepEqual(
      panel.state.chatMessages,
      [{ role: "agent", text: "stale message" }],
      "clear restores the pre-replay thread messages",
    );
    assert.deepEqual(
      panel.state.transcriptMessages,
      [{ role: "agent", text: "stale transcript" }],
      "clear restores the pre-replay transcript baseline exactly",
    );
    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "clear restores the panel phase");
    assert.deepEqual(panel.state.candidateGraph, { nodes: [{ id: 99 }], links: [] }, "clear restores candidate graph");
    assert.deepEqual(
      panel.state.candidateBaselineGraph,
      { nodes: [{ id: 98 }], links: [] },
      "clear restores candidate baseline graph",
    );
    assert.deepEqual(
      panel.state.applyEligibility,
      { applyable: false, reason: "stale" },
      "clear restores replay baseline eligibility state",
    );
    assert.equal(panel.state.__demoMode, true, "clear restores demo metadata from baseline");
    assert.equal(panel.state._replay, undefined, "clear removes replay bookkeeping");
    assert.equal(panel.state.changeDetails?.summary, "stale change details", "clear restores baseline change details");
    assert.equal(
      panel.state.lastAppliedChanges?.summary,
      "stale applied changes",
      "clear restores baseline applied-change metadata",
    );
    assert.equal(
      scheduledRenders.at(-1)?.reason,
      "agentic-replay-clear",
      "clear schedules a cleanup render",
    );
    assert.ok(
      scheduledRenders.every(
        ({ activePanel, sections }) =>
          activePanel === panel
          && sections.includes(RENDER_SECTIONS.THREAD)
          && sections.includes(RENDER_SECTIONS.META)
          && !sections.includes(RENDER_SECTIONS.CANDIDATE),
      ),
      "replay renders stay scoped to valid active-panel sections",
    );
  } finally {
    await harness.dispose();
  }
});

test("replay navigation honors pruned backend stage lists", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agentic-replay/runs": makeRunsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests": makeTestsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests/test_alpha": makeReplayScenario({
        stages: [
          { id: "ready_to_apply", label: "Ready to apply" },
          { id: "applied", label: "Applied" },
        ],
      }),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_AGENTIC_REPLAY_ENABLED, "1");
    const replay = await harness.loadAgenticReplay();
    const shell = harness.document.createElement("div");
    const panel = { shell, state: makePanelState() };
    const controls = replay.installAgenticReplay(panel, {
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: () => {},
        scheduleRenderAgentPanel: () => {},
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
      applyReplayOriginalGraph() {},
      applyReplayGraphCandidate() {},
    });

    await waitFor(() => controls.runSelect.children.length > 1);
    controls.runSelect.value = "run_2026";
    controls.runSelect.dispatchEvent({ type: "change", target: controls.runSelect });
    await waitFor(() => controls.testSelect.children.length > 1);
    controls.testSelect.value = "test_alpha";
    controls.testSelect.dispatchEvent({ type: "change", target: controls.testSelect });

    controls.loadButton.click();
    await waitFor(() => controls.stageLabel.textContent === "1/2 — Ready to apply");

    assert.deepEqual(
      controls._getStages().map((stage) => stage.id),
      ["ready_to_apply", "applied"],
      "replay should use the backend-pruned stages verbatim",
    );
    assert.equal(controls.prevButton.disabled, true, "first pruned stage disables previous navigation");
    assert.equal(controls.nextButton.disabled, false, "second pruned stage remains reachable");

    controls.nextButton.click();
    assert.equal(controls.stageLabel.textContent, "2/2 — Applied");
    assert.equal(controls.nextButton.disabled, true, "last pruned stage disables forward navigation");
  } finally {
    await harness.dispose();
  }
});

test("replay applied stage reflects apply only when fixture carries a resolved apply result", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agentic-replay/runs": makeRunsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests": makeTestsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests/test_alpha": makeReplayScenario({
        stages: [
          { id: "ready_to_apply", label: "Ready to apply" },
          { id: "applied", label: "Applied" },
        ],
        apply_result: {
          ok: true,
          action: "accept",
          session_id: "session-replay-1",
          turn_id: "turn-replay-1",
          baseline_turn_id: "turn-replay-1",
          baseline_graph_hash: "accepted-hash",
        },
        last_applied_changes: { summary: "Replay fixture accepted the candidate." },
      }),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_AGENTIC_REPLAY_ENABLED, "1");
    const replay = await harness.loadAgenticReplay();
    const shell = harness.document.createElement("div");
    const panel = { shell, state: makePanelState() };
    const controls = replay.installAgenticReplay(panel, {
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: () => {},
        scheduleRenderAgentPanel: () => {},
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
      applyReplayOriginalGraph() {},
      applyReplayGraphCandidate() {},
    });

    await waitFor(() => controls.runSelect.children.length > 1);
    controls.runSelect.value = "run_2026";
    controls.runSelect.dispatchEvent({ type: "change", target: controls.runSelect });
    await waitFor(() => controls.testSelect.children.length > 1);
    controls.testSelect.value = "test_alpha";
    controls.testSelect.dispatchEvent({ type: "change", target: controls.testSelect });

    controls.loadButton.click();
    await waitFor(() => controls.stageLabel.textContent === "1/2 — Ready to apply");
    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);

    controls.nextButton.click();
    assert.equal(controls.stageLabel.textContent, "2/2 — Applied");
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "resolved apply fixtures may use apply reflection");
    assert.equal(panel.state.applyAllowed, false, "resolved apply clears apply actions");
    assert.equal(panel.state.canvasApplyAllowed, false, "resolved apply clears canvas apply actions");
    assert.equal(panel.state.lastAppliedChanges?.summary, "Replay fixture accepted the candidate.");

    controls.prevButton.click();
    assert.equal(controls.stageLabel.textContent, "1/2 — Ready to apply");
    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "reverse navigation rebuilds before the apply commit");
    assert.equal(panel.state.lastAppliedChanges, null, "reverse navigation drops resolved apply metadata");
  } finally {
    await harness.dispose();
  }
});

// ── T12: Concurrency — replay must not corrupt in-flight production state ──
// A production submit/apply that is mid-flight (SUBMITTING, inFlightSubmit,
// submitEpoch set) owns the panel.state lifecycle surface.  Replay navigation
// may visualize a recorded scenario but must NEVER overwrite the production
// submit epoch/flag or POST to any production accept/reject/submit route.

test("replay navigation cannot corrupt in-flight production submit state and posts no production routes", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agentic-replay/runs": makeRunsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests": makeTestsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests/test_alpha": makeReplayScenario(),
      // Production routes must never be reached from replay navigation.
      "/vibecomfy/agent-edit/accept": { status: 500, body: { ok: false, error: "should not be reached" } },
      "/vibecomfy/agent-edit/reject": { status: 500, body: { ok: false, error: "should not be reached" } },
    },
  });
  try {
    globalThis.localStorage.setItem(LS_AGENTIC_REPLAY_ENABLED, "1");
    const replay = await harness.loadAgenticReplay();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const originalGraphCalls = [];
    const candidateGraphCalls = [];
    // Production submit is IN FLIGHT: the lifecycle surface is owned by the
    // production authority with a real submit epoch and in-flight flag.
    const panel = {
      shell,
      state: makePanelState({
        phase: PANEL_STATE.SUBMITTING,
        inFlightSubmit: true,
        submitEpoch: "prod-epoch-concurrency",
        sessionId: "sess-prod-inflight",
        turnId: "turn-prod-inflight",
        chatMessages: [{ role: "user", text: "production submit in flight" }],
      }),
    };
    const controls = replay.installAgenticReplay(panel, {
      headerRight,
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: () => {},
        scheduleRenderAgentPanel: () => {},
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
      applyReplayOriginalGraph(graph) {
        originalGraphCalls.push(graph);
      },
      applyReplayGraphCandidate(graph) {
        candidateGraphCalls.push(graph);
      },
    });

    await waitFor(() => controls.runSelect.children.length > 1);
    controls.runSelect.value = "run_2026";
    controls.runSelect.dispatchEvent({ type: "change", target: controls.runSelect });
    await waitFor(() => controls.testSelect.children.length > 1);
    controls.testSelect.value = "test_alpha";
    controls.testSelect.dispatchEvent({ type: "change", target: controls.testSelect });
    await waitFor(() => controls.loadButton.disabled === false);
    controls.loadButton.click();
    // Give replay's async navigation a chance to run without asserting on a
    // specific stage (the in-flight guard may legitimately refuse activation).
    await new Promise((resolve) => setTimeout(resolve, 30));

    // CONCURRENCY INVARIANT: the production submit epoch and in-flight flag
    // survive replay interaction regardless of whether replay activated.
    assert.equal(panel.state.submitEpoch, "prod-epoch-concurrency", "production submit epoch not corrupted by replay");
    assert.equal(panel.state.inFlightSubmit, true, "in-flight submit flag not cleared by replay");

    // NO-POST INVARIANT: replay never calls production accept/reject routes.
    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/agent-edit/accept"),
      "replay must not POST /agent-edit/accept",
    );
    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/agent-edit/reject"),
      "replay must not POST /agent-edit/reject",
    );
    // The production submit user message must survive replay interaction.
    assert.ok(
      panel.state.chatMessages.some((m) => m.text === "production submit in flight"),
      "in-flight production chat message survives replay interaction",
    );
  } finally {
    await harness.dispose();
  }
});

// ── Family B (T-031): replay baseline JSON clone pins ─────────────────────
// captureReplayBaseline / applyReplayStageVisualization clone panel state and
// scenario graphs through JSON round-trip (clonePlainData + the lifecycle
// baseline-restore clone). These tests pin the undefined/function-loss
// semantics T-032 must preserve when the JSON clones are migrated.

test("replay baseline JSON clone drops undefined and function members from restored state and stage graphs", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agentic-replay/runs": makeRunsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests": makeTestsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests/test_alpha": makeReplayScenario({
        candidate_graph: {
          nodes: [
            { id: 1, type: "Sampler", properties: { vibecomfy_uid: "sampler-1", fn: () => {} } },
            { id: 2, type: "Reroute", properties: { vibecomfy_uid: "reroute-2", ephemeral: undefined } },
          ],
          links: [],
        },
      }),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_AGENTIC_REPLAY_ENABLED, "1");
    const replay = await harness.loadAgenticReplay();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const candidateGraphCalls = [];
    const panel = {
      shell,
      state: makePanelState({
        phase: PANEL_STATE.AWAITING_REVIEW,
        chatMessages: [
          { role: "user", text: "stale message", ephemeral: undefined, callback: () => {} },
        ],
        transcriptMessages: [
          { role: "user", text: "stale transcript", ephemeral: undefined, callback: () => {} },
        ],
        candidateGraph: { nodes: [{ id: 99, fn: () => {} }], links: [] },
        candidateReport: { stale: true, nested: { fn: () => {} } },
        responseDetails: { stale: true },
        changeDetails: { summary: "stale change details", note: undefined, helper: () => {} },
        lastAppliedChanges: { summary: "stale applied changes" },
      }),
    };
    const controls = replay.installAgenticReplay(panel, {
      headerRight,
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: () => {},
        scheduleRenderAgentPanel: () => {},
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
      applyReplayOriginalGraph() {},
      applyReplayGraphCandidate(graph) {
        candidateGraphCalls.push(graph);
      },
    });

    await waitFor(() => controls.runSelect.children.length > 1);
    controls.runSelect.value = "run_2026";
    controls.runSelect.dispatchEvent({ type: "change", target: controls.runSelect });
    await waitFor(() => controls.testSelect.children.length > 1);
    controls.testSelect.value = "test_alpha";
    controls.testSelect.dispatchEvent({ type: "change", target: controls.testSelect });
    controls.loadButton.click();
    await waitFor(() => controls.stageLabel.textContent === "1/4 — Sent");

    // Navigate to the applied stage: the candidate graph handed to the canvas
    // is a clonePlainData output of the scenario payload, so its function and
    // undefined members must be gone before the graph ever reaches the canvas.
    controls.nextButton.click();
    controls.nextButton.click();
    controls.nextButton.click();
    await waitFor(() => controls.stageLabel.textContent === "4/4 — Applied");
    assert.equal(candidateGraphCalls.length, 1, "applied stage applies the cloned candidate graph");
    const appliedGraph = candidateGraphCalls[0];
    assert.equal(
      Object.prototype.hasOwnProperty.call(appliedGraph.nodes[0].properties, "fn"),
      false,
      "function member dropped from stage-applied candidate graph",
    );
    assert.equal(
      Object.prototype.hasOwnProperty.call(appliedGraph.nodes[1].properties, "ephemeral"),
      false,
      "undefined member dropped from stage-applied candidate graph",
    );

    // Clear restores the pre-replay baseline, which was captured through
    // clonePlainData: undefined and function members must not reappear.
    controls.clearButton.click();
    assert.deepEqual(
      panel.state.chatMessages,
      [{ role: "user", text: "stale message" }],
      "restored chat baseline drops undefined/function members",
    );
    assert.deepEqual(
      panel.state.transcriptMessages,
      [{ role: "user", text: "stale transcript" }],
      "restored transcript baseline drops undefined/function members",
    );
    assert.deepEqual(
      panel.state.candidateGraph,
      { nodes: [{ id: 99 }], links: [] },
      "restored candidate graph drops function members",
    );
    assert.deepEqual(
      panel.state.candidateReport,
      { stale: true, nested: {} },
      "restored candidate report drops nested function members",
    );
    assert.deepEqual(
      panel.state.changeDetails,
      { summary: "stale change details" },
      "restored change details drop undefined/function members",
    );
    assert.deepEqual(
      panel.state.lastAppliedChanges,
      { summary: "stale applied changes" },
      "restored applied-change metadata survives the clone",
    );
  } finally {
    await harness.dispose();
  }
});

// ── T-033 (S8): replay snapshot independence + cycle pins ──────────────────
// captureReplayBaseline clones chatMessages / transcriptMessages /
// candidateGraph / candidateReport / changeDetails (and every other object
// field) through clonePlainData — the shared JSON-family clone json_clone.js.
// S8 requires snapshots to NEITHER alias NOR silently accept cycles:
//   1. A captured snapshot must be structurally independent of the live panel
//      state: mutating the source after capture must not change the snapshot,
//      and mutating the snapshot must not change the source.
//   2. Cyclic input must not be silently accepted: JSON.stringify throws on a
//      cycle, so the JSON-family clone used by the replay path must throw
//      (TypeError/RangeError) rather than alias the source.  jsonClone's
//      legacy catch-and-return-original fallback violates this — the cycle
//      test below pins the REQUIRED throwing behavior and is expected to fail
//      until jsonClone is fixed (S8 re-dispatch).

function makeSnapshotFixture() {
  return {
    chatMessages: [
      { role: "user", text: "alpha", meta: { depth: 1, tags: ["a"] } },
      { role: "agent", text: "beta", meta: { depth: 2, tags: ["b"] } },
    ],
    transcriptMessages: [{ role: "user", text: "t-alpha", meta: { depth: 1 } }],
    candidateGraph: {
      nodes: [{ id: 1, type: "Sampler", properties: { vibecomfy_uid: "sampler-1" } }],
      links: [],
    },
    candidateReport: { ok: true, nested: { counts: { added: 1 } } },
    changeDetails: { summary: "sum", statements: [{ op_kind: "add_node", message: "m1" }] },
  };
}

test("replay baseline capture is independent of live panel state — post-capture source mutation does not leak into the snapshot", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agentic-replay/runs": makeRunsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests": makeTestsResponse(),
      "/vibecomfy/agentic-replay/runs/run_2026/tests/test_alpha": makeReplayScenario(),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_AGENTIC_REPLAY_ENABLED, "1");
    const replay = await harness.loadAgenticReplay();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const panel = {
      shell,
      state: makePanelState({
        phase: PANEL_STATE.AWAITING_REVIEW,
        ...makeSnapshotFixture(),
      }),
    };
    // Keep references to the exact source objects captureReplayBaseline
    // clones at load time, so we can mutate them AFTER the capture.
    const sourceChat = panel.state.chatMessages;
    const sourceTranscript = panel.state.transcriptMessages;
    const sourceGraph = panel.state.candidateGraph;
    const sourceReport = panel.state.candidateReport;
    const sourceChange = panel.state.changeDetails;

    const controls = replay.installAgenticReplay(panel, {
      headerRight,
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: () => {},
        scheduleRenderAgentPanel: () => {},
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
    });

    await waitFor(() => controls.runSelect.children.length > 1);
    controls.runSelect.value = "run_2026";
    controls.runSelect.dispatchEvent({ type: "change", target: controls.runSelect });
    await waitFor(() => controls.testSelect.children.length > 1);
    controls.testSelect.value = "test_alpha";
    controls.testSelect.dispatchEvent({ type: "change", target: controls.testSelect });
    controls.loadButton.click();
    await waitFor(() => controls.stageLabel.textContent === "1/4 — Sent");

    // The baseline snapshot was captured during load (captureReplayBaseline).
    // Mutate every SOURCE object deeply, at multiple nesting levels: an
    // aliased snapshot would observe these edits at restore time.
    sourceChat.push({ role: "user", text: "post-capture", meta: { depth: 9 } });
    sourceChat[0].meta.depth = 999;
    sourceChat[0].meta.tags.push("leaked");
    sourceTranscript[0].meta.depth = 555;
    sourceGraph.nodes.push({ id: 777, type: "Leaked" });
    sourceGraph.nodes[0].properties.vibecomfy_uid = "mutated";
    sourceReport.nested.counts.added = 424242;
    sourceChange.statements.push({ op_kind: "leak", message: "leaked" });

    // Clear restores the captured baseline: post-capture source mutations
    // must not appear, at any nesting level.
    controls.clearButton.click();
    assert.deepEqual(
      panel.state.chatMessages,
      [
        { role: "user", text: "alpha", meta: { depth: 1, tags: ["a"] } },
        { role: "agent", text: "beta", meta: { depth: 2, tags: ["b"] } },
      ],
      "restored chatMessages snapshot ignores post-capture source mutation (deep)",
    );
    assert.deepEqual(
      panel.state.transcriptMessages,
      [{ role: "user", text: "t-alpha", meta: { depth: 1 } }],
      "restored transcriptMessages snapshot ignores post-capture source mutation",
    );
    assert.deepEqual(
      panel.state.candidateGraph,
      {
        nodes: [{ id: 1, type: "Sampler", properties: { vibecomfy_uid: "sampler-1" } }],
        links: [],
      },
      "restored candidateGraph snapshot ignores post-capture source mutation",
    );
    assert.deepEqual(
      panel.state.candidateReport,
      { ok: true, nested: { counts: { added: 1 } } },
      "restored candidateReport snapshot ignores post-capture source mutation (deep)",
    );
    assert.deepEqual(
      panel.state.changeDetails,
      { summary: "sum", statements: [{ op_kind: "add_node", message: "m1" }] },
      "restored changeDetails snapshot ignores post-capture source mutation",
    );
  } finally {
    await harness.dispose();
  }
});

test("replay JSON clone (jsonClone) is structurally independent in both directions at multiple nesting levels", () => {
  // Direction 1: mutating the SOURCE after capture must not change the snapshot.
  const sourceA = makeSnapshotFixture();
  const snapshotA = jsonClone(sourceA);
  sourceA.chatMessages[0].meta.depth = 999;
  sourceA.chatMessages[0].meta.tags.push("leaked");
  sourceA.chatMessages.push({ role: "user", text: "post-capture" });
  sourceA.candidateGraph.nodes.push({ id: 777 });
  sourceA.candidateReport.nested.counts.added = 424242;
  sourceA.changeDetails.statements.push({ op_kind: "leak" });
  assert.deepEqual(
    snapshotA,
    makeSnapshotFixture(),
    "mutating the source after capture never leaks into the snapshot (deep)",
  );

  // Direction 2: mutating the SNAPSHOT must not change the source.
  const sourceB = makeSnapshotFixture();
  const snapshotB = jsonClone(sourceB);
  snapshotB.chatMessages[0].meta.depth = 999;
  snapshotB.chatMessages[0].meta.tags.push("snapshot-only");
  snapshotB.chatMessages.push({ role: "agent", text: "snapshot-only" });
  snapshotB.candidateGraph.nodes[0].properties.vibecomfy_uid = "mutated";
  snapshotB.candidateGraph.nodes.push({ id: 777 });
  snapshotB.candidateReport.nested.counts.added = 424242;
  snapshotB.changeDetails.statements[0].message = "mutated";
  snapshotB.changeDetails.statements.push({ op_kind: "snapshot-only" });
  assert.deepEqual(
    sourceB,
    makeSnapshotFixture(),
    "mutating the snapshot never leaks into the source (deep)",
  );
});

test("replay JSON clone (jsonClone) throws on cyclic input instead of silently aliasing the source", () => {
  // S8: snapshots must NEITHER alias NOR silently accept cycles.  The JSON
  // family clone used by the replay path is a native JSON round-trip, which
  // throws TypeError on a cycle — an aliased snapshot would mean the capture
  // silently accepted a cyclic structure and pinned the source object.
  const cyclicThroughArray = { chatMessages: [{ role: "user", text: "alpha" }] };
  cyclicThroughArray.chatMessages.push(cyclicThroughArray);
  assert.throws(
    () => jsonClone(cyclicThroughArray),
    (err) => err instanceof TypeError || err instanceof RangeError,
    "jsonClone must throw on a cycle routed through an array element, never alias the source",
  );

  const selfReferential = {};
  selfReferential.self = selfReferential;
  assert.throws(
    () => jsonClone(selfReferential),
    (err) => err instanceof TypeError || err instanceof RangeError,
    "jsonClone must throw on a self-referential object, never alias the source",
  );
});
