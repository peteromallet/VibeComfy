import test from "node:test";
import assert from "node:assert/strict";

import { createBrowserHarness } from "./harness.mjs";
import {
  PANEL_STATE,
  RENDER_SECTIONS,
  createAgentEditState,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

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
    ...createAgentEditState(),
    chatMessages: [],
    transcriptMessages: [],
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
        chatMessages: [{ role: "agent", text: "stale message" }],
        transcriptMessages: [{ role: "agent", text: "stale transcript" }],
        candidateGraph: { nodes: [{ id: 99 }], links: [] },
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
        createAgentEditState,
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
    assert.deepEqual(panel.state.responseDetails, {}, "sent clears stale response details");
    assert.equal(panel.state.failure, null, "sent clears stale failures");
    assert.equal(panel.state.changeDetails, null, "sent clears stale change details");
    assert.equal(panel.state.lastAppliedChanges, null, "sent clears stale applied-change state");
    assert.deepEqual(panel.state.expandedBubbleTurnKeys, {}, "sent resets replay-owned detail expansion");
    assert.equal(panel.state.__demoMode, undefined, "sent is not in demo mode");
    assert.equal(panel.state._replay?.stage, "sent", "sent records the active replay stage");

    controls.toolbar.dispatchEvent(keyEvent("ArrowRight"));
    assert.equal(controls.stageLabel.textContent, "2/4 — Thinking");
    assert.equal(originalGraphCalls.length, 2, "thinking keeps the original graph on the canvas");
    assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING, "thinking uses submitting phase");
    assert.equal(panel.state.chatMessages.length, 2, "thinking adds a pending agent bubble");
    assert.equal(panel.state.chatMessages[1].pending_response, true, "thinking agent bubble is pending");
    assert.equal(panel.state.chatMessages[1].executor_pending, true, "thinking agent bubble marks executor pending");
    assert.equal(panel.state.pending_response, true, "thinking state exposes pending response");
    assert.equal(panel.state.executor_pending, true, "thinking state exposes executor pending");
    assert.equal(panel.state.candidateGraph, null, "thinking does not leak candidate state");
    assert.equal(panel.state.applyEligibility, null, "thinking clears apply eligibility");
    assert.equal(panel.state.__demoMode, undefined, "thinking remains outside demo mode");
    assert.equal(panel.state._replay?.stage, "thinking", "thinking updates replay bookkeeping");

    controls.nextButton.click();
    assert.equal(controls.stageLabel.textContent, "3/4 — Ready to apply");
    assert.equal(originalGraphCalls.length, 3, "ready-to-apply keeps the original graph visible");
    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "ready-to-apply restores review state");
    assert.deepEqual(panel.state.candidateGraph, makeReplayScenario().body.candidate_graph);
    assert.equal(panel.state.applyAllowed, true, "ready-to-apply exposes apply action");
    assert.equal(panel.state.canvasApplyAllowed, true, "ready-to-apply exposes canvas apply");
    assert.deepEqual(panel.state.responseDetails, makeReplayScenario().body.response_details);
    assert.equal(panel.state.changeDetails?.summary, "Inserted a reroute node.");
    assert.equal(panel.state.__demoMode, true, "candidate-visible stages enter demo mode");
    assert.equal(panel.state._replay?.stage, "ready_to_apply", "ready-to-apply updates replay bookkeeping");

    controls.toolbar.dispatchEvent(keyEvent("ArrowRight"));
    assert.equal(controls.stageLabel.textContent, "4/4 — Applied");
    assert.equal(candidateGraphCalls.length, 1, "applied uses the candidate-graph callback");
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "applied returns to idle phase");
    assert.equal(panel.state.applyAllowed, false, "applied disables apply action");
    assert.equal(panel.state.canvasApplyAllowed, false, "applied disables canvas apply action");
    assert.equal(panel.state.__demoMode, true, "applied remains in demo mode until clear");
    assert.equal(panel.state.lastAppliedChanges?.summary, "Inserted a reroute node.");

    controls.prevButton.click();
    assert.equal(controls.stageLabel.textContent, "3/4 — Ready to apply");
    assert.equal(originalGraphCalls.length, 4, "reverse navigation restores the original graph");
    assert.equal(panel.state.lastAppliedChanges, null, "reverse navigation clears applied-only state");
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
    assert.deepEqual(panel.state.chatMessages, [], "clear removes replay thread messages");
    assert.deepEqual(panel.state.transcriptMessages, [], "clear removes replay transcript messages");
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "clear resets the panel phase");
    assert.equal(panel.state.candidateGraph, null, "clear removes replay candidate graph");
    assert.equal(panel.state.applyEligibility, null, "clear removes replay eligibility state");
    assert.equal(panel.state.__demoMode, undefined, "clear removes demo mode");
    assert.equal(panel.state._replay, undefined, "clear removes replay bookkeeping");
    assert.equal(panel.state.lastAppliedChanges, null, "clear removes applied replay metadata");
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
          && sections.includes(RENDER_SECTIONS.CANDIDATE),
      ),
      "replay renders stay scoped to the active panel thread/candidate sections",
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
        createAgentEditState,
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
