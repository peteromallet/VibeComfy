import test from "node:test";
import assert from "node:assert/strict";

import { createBrowserHarness } from "./harness.mjs";
import {
  PANEL_STATE,
  RENDER_SECTIONS,
  transition,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

const LS_DEMO_PICKER_ENABLED = "vibecomfy_demo_picker_enabled";

function waitFor(predicate, { attempts = 50, label = "condition" } = {}) {
  return new Promise((resolve, reject) => {
    let index = 0;
    function tick() {
      if (predicate()) {
        resolve();
        return;
      }
      if (index >= attempts) {
        reject(new Error(`waitFor timed out: ${label}`));
        return;
      }
      index += 1;
      setTimeout(tick, 0);
    }
    tick();
  });
}

function makeScenarioResponse(overrides = {}) {
  return {
    status: 200,
    body: {
      ok: true,
      scenario: {
        id: "demo_a",
        title: "Demo A",
        query: "Add a demo node",
      },
      original_graph: {
        nodes: [{ id: 1, type: "Input", pos: [100, 200], properties: { vibecomfy_uid: "uid-1" } }],
        links: [],
      },
      candidate_graph: {
        nodes: [
          { id: 1, type: "Input", pos: [100, 200], properties: { vibecomfy_uid: "uid-1" } },
          { id: 2, type: "Output", pos: [2400, 200], properties: { vibecomfy_uid: "uid-2" } },
        ],
        links: [],
      },
      agent_reply: "I added a demo node for you.",
      session_id: "demo-sess-a",
      turn_id: "demo-turn-a",
      candidate_graph_hash: "server-canonical-candidate-hash",
      eligibility: { applyable: true, reason: "applyable" },
      outcome: {
        kind: "candidate",
        changes: [{ uid: "uid-1", field_path: "seed", old: 1, new: 5 }],
      },
      change_details: {
        summary: "Added a demo output node.",
        statements: [{ op_kind: "add_node", message: "Added Output node" }],
        batch_turns: [
          {
            turn_number: 1,
            field_changes: [
              {
                uid: "uid-1",
                title: "Input",
                field_path: "seed",
                old: 1,
                new: 5,
              },
            ],
          },
        ],
      },
      ...overrides,
    },
  };
}

function makeScenarioList() {
  return {
    status: 200,
    body: {
      ok: true,
      scenarios: [
        { id: "demo_a", title: "Demo A" },
        { id: "demo_b", title: "Demo B" },
      ],
    },
  };
}

function makeStatusResponse() {
  return {
    status: 200,
    body: {
      ready: true,
      requested_route: "auto",
      route: "auto",
      provider_available: true,
      route_options: {
        auto: { label: "Auto", models: [] },
        deepseek: { label: "DeepSeek", models: [] },
      },
    },
  };
}

function makePanelState() {
  return {
    chatMessages: [],
    transcriptMessages: [],
    expandedBubbleTurnKeys: {},
    responseDetails: {},
    undoStack: [],
    history: [],
  };
}

// ── Isolation tests for the preview picker module ───────────────────────────

test("disabled picker returns null and emits no UI or network traffic", async () => {
  const harness = await createBrowserHarness();
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "0");
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const result = picker.installPreviewPicker({ shell });
    assert.equal(result, null, "installPreviewPicker should return null when disabled");
    assert.equal(shell.children.length, 0, "picker should not mount DOM when disabled");
    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/demo/scenarios"),
      "disabled picker should not fetch scenarios",
    );
  } finally {
    await harness.dispose();
  }
});

test("enabled picker fetches the scenario list and renders the toolbar", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/demo/scenarios": makeScenarioList(),
    },
  });
  try {
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const controls = picker.installPreviewPicker({ shell }, { headerRight });
    assert.ok(controls, "installPreviewPicker should return controls when enabled");
    await waitFor(() => controls.select.children.length > 1);

    assert.ok(
      harness.requests.some((r) => r.url === "/vibecomfy/demo/scenarios"),
      "enabled picker should fetch /vibecomfy/demo/scenarios",
    );
    assert.equal(controls.select.children[0].value, "", "first option is placeholder");
    assert.equal(controls.select.children[1].value, "demo_a", "second option is demo_a");
    assert.equal(controls.select.children[2].value, "demo_b", "third option is demo_b");
    assert.equal(headerRight.children.length, 1, "toggle button is placed in headerRight");
    assert.equal(headerRight.children[0].textContent, "▦ Demo", "toggle button label");
    assert.equal(controls.container.style.display, "flex", "picker toolbar starts visible");
  } finally {
    await harness.dispose();
  }
});

test("server-disabled picker leaves no visible UI even when browser preference allows it", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/demo/scenarios": { status: 404, body: { ok: false, error: "Not found" } },
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const controls = picker.installPreviewPicker({ shell }, { headerRight });
    assert.ok(controls, "installer still returns a controller for deterministic tests");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/demo/scenarios"));

    assert.equal(controls.mounted, false, "server-disabled picker should not mount controls");
    assert.equal(shell.children.length, 0, "server-disabled picker should not mount toolbar DOM");
    assert.equal(headerRight.children.length, 0, "server-disabled picker should not mount toggle");
    assert.equal(
      controls.container.parentNode,
      null,
      "detached container should not leave a visible error shell",
    );
  } finally {
    await harness.dispose();
  }
});

test("Load & Play stages demo replay from before-send to review", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_a": makeScenarioResponse(),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const appliedGraphs = [];
    const scheduledRenders = [];
    const canvasDraws = [];
    const fulfilledObligations = [];
    const threadRenderResets = [];
    const fittedGraphs = [];
    const panel = {
      shell,
      state: makePanelState(),
    };
    Object.assign(panel.state, {
      sessionId: "production-session-before-demo",
      turnId: "production-turn-before-demo",
      baselineTurnId: "production-baseline-turn",
      baselineGraphHash: "production-baseline-hash",
      baselineGraphHashKind: "canonical_graph_v1",
      baselineGraphHashVersion: 1,
      baselineSource: "server",
    });
    const repaintGraph = {
      ...(harness.app.graph || {}),
      setDirtyCanvas: (...args) => canvasDraws.push({ method: "setDirtyCanvas", args }),
    };
    const demoDs = { scale: 0.8, offset: [10, -20] };
    const appWithCanvasRepaintProbe = {
      ...harness.app,
      graph: repaintGraph,
      canvas: {
        ...(harness.app.canvas || {}),
        ds: demoDs,
        graph: repaintGraph,
        setDirty: (...args) => canvasDraws.push({ method: "setDirty", args }),
        draw: (...args) => canvasDraws.push({ method: "draw", args }),
      },
    };
    const controls = picker.installPreviewPicker(panel, {
      headerRight,
      helpers: {
        app: appWithCanvasRepaintProbe,
        applyGraphCandidateInPlace: (appArg, graph, opts) => {
          appliedGraphs.push({
            app: appArg,
            graph: JSON.parse(JSON.stringify(graph)),
            opts,
          });
          if (Array.isArray(graph?.nodes?.[0]?.pos)) {
            graph.nodes[0].pos = [10, 10];
          }
          // Configure hooks are allowed to be hostile to viewport state; the
          // picker must restore the camera around every graph replacement.
          demoDs.scale = 9;
          demoDs.offset[0] = 999;
          demoDs.offset[1] = 999;
        },
        captureCanvasViewportSnapshot: () => ({
          path: "canvas.ds",
          scale: demoDs.scale,
          offset: [...demoDs.offset],
        }),
        restoreCanvasViewportSnapshot: (snapshot) => {
          demoDs.scale = snapshot.scale;
          demoDs.offset[0] = snapshot.offset[0];
          demoDs.offset[1] = snapshot.offset[1];
          return true;
        },
        scheduleRenderAgentPanel: (reason, p, sections) => {
          scheduledRenders.push({ reason, panel: p, sections });
        },
        fulfillLifecycleTransitionObligations: (p, obligations) => {
          fulfilledObligations.push({ panel: p, obligations: { ...obligations } });
        },
        fenceChatRehydrateForDemo: (p) => {
          const obligations = transition(p, "CHAT_REHYDRATE_START");
          return obligations.requestEpoch;
        },
        resetThreadRenderState: (p) => {
          threadRenderResets.push(p.state.__demoStage);
          p.threadState = { renderedKeyOrder: [] };
        },
        fitCanvasViewportToGraphPayload: (graph) => {
          fittedGraphs.push(JSON.parse(JSON.stringify(graph)));
          demoDs.scale = 0.5;
          demoDs.offset[0] = 120;
          demoDs.offset[1] = -75;
          return true;
        },
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
    });
    await waitFor(() => controls.select.children.length > 1);

    controls.select.value = "demo_a";
    controls.select.dispatchEvent({ type: "change", target: controls.select });
    assert.equal(controls.loadButton.disabled, false, "load button enabled after selection");

    controls.loadButton.click();
    await waitFor(() => controls.loadButton.textContent === "Reload" && !controls.loadButton.disabled);

    assert.equal(appliedGraphs.length, 1, "original graph was applied to the canvas");
    assert.equal(appliedGraphs[0].graph.nodes.length, 1, "original graph has one node");
    assert.equal(panel.state.__demoStage, "before_send", "first stage is before_send");
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "before_send is idle");
    assert.equal(panel.state.chatMessages.length, 0, "before_send has no transcript yet");
    assert.equal(panel.state.candidateGraph, null, "before_send has no candidate");
    assert.equal(
      panel.state.sessionId,
      "production-session-before-demo",
      "before-send never exposes synthetic identity to production submit state",
    );
    assert.deepEqual(threadRenderResets, ["before_send"], "full transcript replacement resets bubble cache");
    assert.ok(
      fulfilledObligations.some((entry) => entry.obligations.clearCandidatePreview === true),
      "before_send lifecycle reset fulfills preview-clear obligations",
    );
    assert.equal(controls.prevButton.disabled, true, "cannot go back from first stage");
    assert.equal(controls.nextButton.disabled, false, "can advance from first stage");
    assert.equal(fittedGraphs.length, 1, "scenario chooses its camera exactly once");
    assert.deepEqual(
      fittedGraphs[0].nodes.map((node) => node.properties.vibecomfy_uid),
      ["uid-1", "uid-1", "uid-2"],
      "initial camera covers the semantic before/after region",
    );
    assert.deepEqual(demoDs, { scale: 0.5, offset: [120, -75] });

    controls.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "sent_loading");
    assert.equal(appliedGraphs[1].graph.nodes[0].pos[0], 100, "sent stage applies a fresh original graph clone");
    assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING, "sent_loading shows loading state");
    assert.equal(panel.state.chatMessages.length, 1, "sent_loading only shows user message");
    assert.equal(panel.state.chatMessages[0].role, "user", "sent_loading message is from user");
    assert.equal(panel.state.chatMessages[0].text, "Add a demo node", "user message text is query");
    assert.equal(panel.state.candidateGraph, null, "sent_loading has no candidate yet");
    assert.deepEqual(
      threadRenderResets,
      ["before_send", "sent_loading"],
      "each staged transcript replacement resets bubble cache",
    );
    assert.ok(
      fulfilledObligations.some((entry) => entry.obligations.invalidateCandidate === true),
      "sent_loading submit transition fulfills candidate invalidation obligations",
    );

    controls.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "ready_to_apply");
    assert.equal(appliedGraphs[2].graph.nodes[0].pos[0], 100, "review stage applies a fresh original graph clone");

    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "phase is AWAITING_REVIEW");
    assert.equal(panel.state.__demoMode, true, "__demoMode flag is set");
    assert.equal(panel.state.sessionId, "demo-sess-a", "session id populated");
    assert.equal(panel.state.turnId, "demo-turn-a", "turn id populated");
    assert.ok(panel.state.candidateGraph, "candidate graph populated");
    assert.equal(panel.state.candidateGraph.nodes.length, 2, "preview authority is the actual candidate graph");
    assert.equal(
      panel.state.candidateGraphHash,
      "server-canonical-candidate-hash",
      "demo preserves the bundled canonical candidate hash instead of inventing a browser hash",
    );
    assert.equal(panel.state.previewEnabled, true, "review stage visibly enables the candidate diff");
    assert.equal(
      appliedGraphs.at(-1).graph.nodes.length,
      1,
      "non-layout review keeps the original canvas under the candidate overlay",
    );
    assert.deepEqual(
      fittedGraphs.at(-1).nodes.map((node) => node.properties.vibecomfy_uid),
      ["uid-1", "uid-1", "uid-2"],
      "review retains the initial semantic before/after framing",
    );
    assert.equal(fittedGraphs.length, 1, "review does not move the camera");
    assert.deepEqual(demoDs, { scale: 0.5, offset: [120, -75] });
    assert.equal(panel.state.applyAllowed, false, "demo eligibility cannot replace transaction authority");
    assert.equal(panel.state.canvasApplyAllowed, false, "demo candidate cannot authorize production canvas Apply");
    assert.equal(panel.state.queueAllowed, false, "queue stays disabled for demo");
    assert.equal(panel.state.applyEligibility?.reason, "applyable", "eligibility reason stored");
    assert.ok(
      fulfilledObligations.at(-1)?.obligations.invalidateCandidate === true,
      "ready_to_apply candidate transition fulfills overlay invalidation obligations",
    );
    assert.ok(
      fulfilledObligations.every((entry) => !Object.hasOwn(entry.obligations, "persistSession")),
      "demo lifecycle never persists synthetic session identity",
    );
    assert.ok(
      fulfilledObligations.every((entry) => !Object.hasOwn(entry.obligations, "rehydrateChat")),
      "demo lifecycle never starts production chat rehydrate",
    );
    assert.ok(
      fulfilledObligations.every((entry) => !Object.hasOwn(entry.obligations, "setQueueGuardContext")),
      "demo lifecycle never installs synthetic queue authority",
    );
    assert.ok(
      fulfilledObligations.every((entry) => !Object.hasOwn(entry.obligations, "refreshQueueGuard")),
      "demo lifecycle never refreshes production queue authority",
    );
    assert.equal(
      panel.state.expandedBubbleTurnKeys["turn:demo-turn-a"],
      undefined,
      "agent bubble details stay collapsed at preview stage",
    );

    assert.equal(panel.state.chatMessages.length, 2, "two transcript messages");
    assert.equal(panel.state.chatMessages[0].role, "user", "first message is from user");
    assert.equal(panel.state.chatMessages[0].text, "Add a demo node", "user message text is query");
    assert.equal(panel.state.chatMessages[1].role, "agent", "second message is from agent");
    assert.equal(
      panel.state.chatMessages[1].text,
      "I added a demo node for you.",
      "agent message text is reply",
    );
    assert.deepEqual(panel.state.transcriptMessages, panel.state.chatMessages, "transcript mirrors chat");
    assert.equal(panel.state.changeDetails.summary, "Added a demo output node.", "change details stored");
    assert.equal(
      panel.state.lastSubmitFieldChanges.batchTurnChanges[0].changes[0].uid,
      "uid-1",
      "demo change_details feeds normalized preview field changes",
    );
    assert.equal(
      panel.state.lastSubmitFieldChanges.outcomeChanges[0].fieldPath,
      "seed",
      "demo outcome changes use the same canonical field-change projection as live submit",
    );
    assert.equal(
      panel.state.responseDetails["demo-turn-a"].changes[0].field_path,
      "seed",
      "demo agent bubble receives the same projected semantic changes as live rehydrate",
    );
    await waitFor(
      () => canvasDraws.some((entry) => entry.method === "draw"),
      { label: "preview overlay repaint" },
    );

    assert.equal(scheduledRenders.at(-1).reason, "demo-picker");
    assert.ok(scheduledRenders.at(-1).sections.includes(RENDER_SECTIONS.THREAD));
    assert.ok(scheduledRenders.at(-1).sections.includes(RENDER_SECTIONS.COMPOSER));
    assert.ok(scheduledRenders.at(-1).sections.includes(RENDER_SECTIONS.NOTICE));

    const staleProductionResult = transition(panel, "CHAT_REHYDRATE_SUCCESS", {
      requestEpoch: panel.state.chatRehydrateEpoch - 1,
      messages: [{ role: "agent", text: "late production transcript" }],
      sessionId: "production-session",
    });
    assert.equal(staleProductionResult.stale, true, "late production rehydrate is fenced");
    assert.equal(panel.state.__demoStage, "ready_to_apply", "late rehydrate cannot move demo cursor");
    assert.equal(panel.state.chatMessages[1].text, "I added a demo node for you.");

    const applyResolutionCountBefore = fulfilledObligations.filter(
      (entry) => entry.obligations.clearCandidatePreview === true,
    ).length;
    demoDs.scale = 0.72;
    demoDs.offset[0] = -44;
    demoDs.offset[1] = 91;
    controls.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "applied");
    const applyResolutionCountAfter = fulfilledObligations.filter(
      (entry) => entry.obligations.clearCandidatePreview === true,
    ).length;
    assert.equal(
      applyResolutionCountAfter,
      applyResolutionCountBefore + 1,
      "applied stage resolves the candidate exactly once",
    );
    assert.equal(panel.state.previewEnabled, false, "applied stage clears the candidate preview");
    assert.equal(panel.state.chatMessages.length, 2, "applied stage preserves the staged transcript");
    assert.equal(panel.state.chatMessages[1].text, "I added a demo node for you.");
    assert.equal(panel.state.__demoStageIndex, 3, "applied stage cursor remains authoritative");
    assert.equal(
      panel.state.sessionId,
      "production-session-before-demo",
      "applied stage restores the real production session",
    );
    assert.equal(
      panel.state.turnId,
      "production-turn-before-demo",
      "applied demo turn cannot become production authority",
    );
    assert.equal(
      panel.state.baselineTurnId,
      "production-baseline-turn",
      "applied stage restores the real production baseline fence",
    );
    assert.equal(panel.state.baselineGraphHash, "production-baseline-hash");
    assert.equal(fittedGraphs.length, 1, "applied stage does not move the camera");
    assert.deepEqual(
      demoDs,
      { scale: 0.72, offset: [-44, 91] },
      "applied preserves the user's latest manual pan and zoom",
    );

    controls.prevButton.click();
    await waitFor(() => panel.state.__demoStage === "ready_to_apply");
    assert.equal(panel.state.previewEnabled, true, "back navigation restores the actual candidate preview");
    assert.equal(panel.state.chatMessages.length, 2, "back navigation preserves the review transcript");
    assert.equal(panel.state.__demoStageIndex, 2, "review cursor survives shared lifecycle commits");
    assert.equal(fittedGraphs.length, 1, "back navigation does not move the camera");
    assert.deepEqual(demoDs, { scale: 0.72, offset: [-44, 91] });
  } finally {
    await harness.dispose();
  }
});

test("Load & Play shows reorganise candidate layout during review", async () => {
  const originalGraph = {
    nodes: [{ id: 1, type: "Input", pos: [100, 200], properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [{ id: 1, type: "Input", pos: [500, 80], properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_a": makeScenarioResponse({
        original_graph: originalGraph,
        candidate_graph: candidateGraph,
        report: { kind: "reorganise" },
      }),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const appliedGraphs = [];
    const panel = { shell, state: makePanelState() };
    const controls = picker.installPreviewPicker(panel, {
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: (_appArg, graph) => {
          appliedGraphs.push(JSON.parse(JSON.stringify(graph)));
        },
        scheduleRenderAgentPanel: () => {},
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
    });
    await waitFor(() => controls.select.children.length > 1);

    controls.select.value = "demo_a";
    controls.select.dispatchEvent({ type: "change", target: controls.select });
    controls.loadButton.click();
    await waitFor(() => panel.state.__demoStage === "before_send");
    controls.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "sent_loading");
    controls.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "ready_to_apply");

    assert.deepEqual(appliedGraphs.at(-1), candidateGraph, "reorganise review should apply the candidate layout");
  } finally {
    await harness.dispose();
  }
});

test("non-applyable eligibility disables apply/canvasApply while keeping details collapsed", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_b": makeScenarioResponse({
        id: "demo_b",
        eligibility: { applyable: false, reason: "server_blocked", message: "Blocked by server" },
      }),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const panel = { shell, state: makePanelState() };
    const controls = picker.installPreviewPicker(panel, {
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: () => {},
        scheduleRenderAgentPanel: () => {},
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
    });
    await waitFor(() => controls.select.children.length > 1);

    controls.select.value = "demo_b";
    controls.select.dispatchEvent({ type: "change", target: controls.select });
    controls.loadButton.click();
    await waitFor(() => controls.loadButton.textContent === "Reload");
    controls.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "sent_loading");
    controls.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "ready_to_apply");

    assert.equal(panel.state.applyAllowed, false, "apply disallowed");
    assert.equal(panel.state.canvasApplyAllowed, false, "canvas apply disallowed");
    assert.equal(panel.state.applyEligibility?.reason, "server_blocked", "eligibility reason preserved");
    assert.equal(
      panel.state.expandedBubbleTurnKeys["turn:demo-turn-a"],
      undefined,
      "blocked preview details stay collapsed",
    );
  } finally {
    await harness.dispose();
  }
});

// ── End-to-end demo Apply/Reject no-post behavior ───────────────────────────

test("demo Apply and Reject do not POST to the backend accept/reject routes", async () => {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/vibecomfy/ping": { status: 200, body: "pong" },
      "/vibecomfy/agent/status?route=auto": makeStatusResponse(),
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_a": makeScenarioResponse(),
      "/vibecomfy/agent-edit/accept": { status: 500, body: { ok: false, error: "should not be reached" } },
      "/vibecomfy/agent-edit/reject": { status: 500, body: { ok: false, error: "should not be reached" } },
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    await harness.loadExtension();
    await harness.invokeCommand("VibeComfy.AgentEdit");

    const runtime = await harness.loadPanelRuntime();
    const panel = runtime.currentAgentPanel();
    assert.ok(panel, "panel is open");
    assert.ok(panel.previewPicker, "preview picker is installed on the panel");

    await waitFor(() => panel.previewPicker.select.children.length > 1, { label: "integrated scenario options" });
    panel.previewPicker.select.value = "demo_a";
    panel.previewPicker.select.dispatchEvent({ type: "change", target: panel.previewPicker.select });
    panel.previewPicker.loadButton.click();
    await waitFor(() => panel.previewPicker.loadButton.textContent === "Reload", { label: "integrated first load" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "sent_loading", { label: "integrated first sent_loading" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "ready_to_apply", { label: "integrated first ready_to_apply" });

    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "panel is in review state");
    assert.equal(panel.state.__demoMode, true, "panel is in demo mode");
    assert.ok(
      !harness.requests.some((r) => r.url.includes("/vibecomfy/agent-edit/chat?session_id=demo-sess-a")),
      "demo terminal commit must not rehydrate its synthetic session",
    );

    // The button click handler does not consult the disabled attribute; ensure the
    // button itself is enabled to confirm the UI considers the action available.
    panel.buttons.apply.disabled = false;
    panel.buttons.reject.disabled = false;

    // Count requests before clicking Apply.
    const preApplyCount = harness.requests.length;
    panel.buttons.apply.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/agent-edit/accept"),
      "demo Apply must not POST /vibecomfy/agent-edit/accept",
    );
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "demo Apply transitions to IDLE");
    assert.equal(panel.state.__demoStage, "applied", "demo Apply advances to applied stage");
    assert.equal(panel.state.__demoMode, false, "__demoMode is disabled after demo Apply");

    // Restore demo state to exercise Reject on the same panel.
    Object.assign(panel.state, {
      sessionId: "production-session-before-reject",
      turnId: "production-turn-before-reject",
      baselineTurnId: "production-baseline-before-reject",
    });
    panel.previewPicker.loadButton.click();
    await waitFor(() => panel.state.__demoStage === "before_send", { label: "integrated second load reset" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "sent_loading", { label: "integrated second sent_loading" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "ready_to_apply", { label: "integrated second ready_to_apply" });
    assert.equal(panel.state.__demoMode, true, "demo mode restored after replay reaches review");

    panel.buttons.apply.disabled = false;
    panel.buttons.reject.disabled = false;
    panel.buttons.reject.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/agent-edit/reject"),
      "demo Reject must not POST /vibecomfy/agent-edit/reject",
    );
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "demo Reject transitions to IDLE");
    assert.equal(panel.state.__demoMode, undefined, "__demoMode is cleared after demo Reject");
    assert.equal(
      panel.state.sessionId,
      "production-session-before-reject",
      "demo Reject restores the pre-demo production session",
    );
    assert.equal(panel.state.turnId, "production-turn-before-reject");
    assert.equal(panel.state.baselineTurnId, "production-baseline-before-reject");
  } finally {
    await harness.dispose();
  }
});

// ── T12: Concurrency, scope, and no-production-impersonation regressions ────
// Preview (demo) must never impersonate a production turn: it carries no
// production-only submit hash, never POSTs to accept/reject, and stays flagged
// as non-production (__demoMode).  These invariants hold even when the demo
// panel shares the same panel.state surface as the production authority.

test("demo candidate never impersonates production — no submit hash, no accept POST on Apply", async () => {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/vibecomfy/ping": { status: 200, body: "pong" },
      "/vibecomfy/agent/status?route=auto": makeStatusResponse(),
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_a": makeScenarioResponse(),
      "/vibecomfy/agent-edit/accept": { status: 500, body: { ok: false, error: "should not be reached" } },
      "/vibecomfy/agent-edit/reject": { status: 500, body: { ok: false, error: "should not be reached" } },
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    await harness.loadExtension();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    const runtime = await harness.loadPanelRuntime();
    const panel = runtime.currentAgentPanel();
    assert.ok(panel, "panel is open");
    assert.ok(panel.previewPicker, "preview picker is installed on the panel");

    await waitFor(() => panel.previewPicker.select.children.length > 1, { label: "scenario options" });
    panel.previewPicker.select.value = "demo_a";
    panel.previewPicker.select.dispatchEvent({ type: "change", target: panel.previewPicker.select });
    panel.previewPicker.loadButton.click();
    await waitFor(() => panel.state.__demoStage === "before_send", { label: "before_send" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "sent_loading", { label: "sent_loading" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "ready_to_apply", { label: "ready_to_apply" });

    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "demo reaches review");
    // serverSubmitGraphHash is minted ONLY by a real server submit.  Preview
    // must leave it null so the demo candidate cannot be mistaken for a
    // production-accepted turn or bypass CAS/staleness checks.
    assert.equal(panel.state.serverSubmitGraphHash, null, "demo candidate has no production submit hash");
    assert.equal(panel.state.__demoMode, true, "demo candidate is flagged as non-production");
    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/agent-edit/accept"),
      "reaching demo review must not POST accept",
    );

    panel.buttons.apply.disabled = false;
    const preApplyRequestCount = harness.requests.length;
    panel.buttons.apply.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/agent-edit/accept"),
      "demo Apply must not POST accept",
    );
    assert.equal(harness.requests.length, preApplyRequestCount, "demo Apply emits no new network traffic");
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "demo Apply settles to IDLE");
    assert.equal(panel.state.__demoMode, false, "demo Apply clears demo mode");
    assert.equal(panel.state.serverSubmitGraphHash, null, "demo Apply leaves no production submit hash");
  } finally {
    await harness.dispose();
  }
});

// ── T12: Demo Apply respects the active canvas scope ───────────────────────
// handleDemoApply consults the same assertApplyScopeConsistency guard as the
// production apply authority.  When the active chat scope does not match the
// candidate's scope, demo apply must be refused locally: no POST, no graph
// mutation, and the demo stage must not advance to "applied".

test("demo Apply is blocked when the candidate scope mismatches the active chat scope", async () => {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/vibecomfy/ping": { status: 200, body: "pong" },
      "/vibecomfy/agent/status?route=auto": makeStatusResponse(),
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_a": makeScenarioResponse(),
      "/vibecomfy/agent-edit/accept": { status: 500, body: { ok: false, error: "should not be reached" } },
      "/vibecomfy/agent-edit/reject": { status: 500, body: { ok: false, error: "should not be reached" } },
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    await harness.loadExtension();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    const runtime = await harness.loadPanelRuntime();
    const panel = runtime.currentAgentPanel();
    assert.ok(panel, "panel is open");

    await waitFor(() => panel.previewPicker.select.children.length > 1, { label: "scope scenario options" });
    panel.previewPicker.select.value = "demo_a";
    panel.previewPicker.select.dispatchEvent({ type: "change", target: panel.previewPicker.select });
    panel.previewPicker.loadButton.click();
    await waitFor(() => panel.state.__demoStage === "before_send", { label: "scope before_send" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "sent_loading", { label: "scope sent_loading" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "ready_to_apply", { label: "scope ready_to_apply" });
    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "demo reaches review");

    // Inject a scope mismatch: the candidate belongs to a different workflow
    // tab than the active chat scope.  assertApplyScopeConsistency must refuse.
    panel.state.chatScopeId = "scope-active-chat";
    panel.state.candidateScopeId = "scope-other-candidate";
    panel.state.submittingScopeId = "scope-active-chat";

    panel.buttons.apply.disabled = false;
    panel.buttons.apply.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    // SCOPE-RESPECT INVARIANT: demo apply must NOT advance to "applied" and
    // must NOT POST accept when the scope mismatches.
    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/agent-edit/accept"),
      "scope-mismatched demo Apply must not POST accept",
    );
    assert.notEqual(
      panel.state.__demoStage,
      "applied",
      "scope-mismatched demo Apply must not advance to the applied stage",
    );
  } finally {
    await harness.dispose();
  }
});

// ── Demo picker must be inert by default and never mask a real edit ────────
// A staged demo leaves panel.state.__demoMode set, which routes Apply/Reject
// to the demo handlers. clearActiveDemo() tears that down so a real edit
// (submitAgentEdit calls it first) is never intercepted by lingering demo
// state. It must also be a safe no-op when no demo is staged.

test("clearActiveDemo tears down a staged demo and restores production identity", async () => {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/vibecomfy/ping": { status: 200, body: "pong" },
      "/vibecomfy/agent/status?route=auto": makeStatusResponse(),
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_a": makeScenarioResponse(),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    await harness.loadExtension();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    const runtime = await harness.loadPanelRuntime();
    const panel = runtime.currentAgentPanel();
    assert.ok(panel?.previewPicker, "preview picker is installed");

    // Establish production identity BEFORE the demo so teardown can restore it.
    Object.assign(panel.state, {
      sessionId: "prod-session",
      turnId: "prod-turn",
      baselineTurnId: "prod-baseline",
    });

    // Stage a demo to ready_to_apply — this is the bug condition (__demoMode
    // lingering and masking a later real edit).
    await waitFor(() => panel.previewPicker.select.children.length > 1, { label: "scenario options" });
    panel.previewPicker.select.value = "demo_a";
    panel.previewPicker.select.dispatchEvent({ type: "change", target: panel.previewPicker.select });
    panel.previewPicker.loadButton.click();
    await waitFor(() => panel.state.__demoStage === "before_send", { label: "before_send" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "sent_loading", { label: "sent_loading" });
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "ready_to_apply", { label: "ready_to_apply" });
    assert.equal(panel.state.__demoMode, true, "demo is staged in demo mode");
    assert.equal(panel.state.previewEnabled, true, "demo review leaves the preview overlay on");

    // Tear it down the way submitAgentEdit does.
    const toreDown = panel.previewPicker.clearActiveDemo(panel);
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(toreDown, true, "clearActiveDemo reports it tore down an active demo");
    assert.equal(panel.state.__demoMode, undefined, "__demoMode is cleared so Apply/Reject no longer route to the demo");
    assert.equal(panel.state.previewEnabled, false, "preview overlay is disabled");
    assert.equal(panel.previewPicker.select.value, "", "picker returns to its default 'no demo' selection");
    assert.equal(panel.state.sessionId, "prod-session", "production session id is restored");
    assert.equal(panel.state.turnId, "prod-turn", "production turn id is restored");
    assert.equal(panel.state.baselineTurnId, "prod-baseline", "production baseline is restored");

    // A second call is a safe no-op: nothing to tear down, no identity mutation.
    const idleCall = panel.previewPicker.clearActiveDemo(panel);
    assert.equal(idleCall, false, "clearActiveDemo is a no-op when no demo is staged");
    assert.equal(panel.state.sessionId, "prod-session", "no-op call does not touch production identity");
  } finally {
    await harness.dispose();
  }
});

// ── Family B (T-031): demo scenario JSON clone pins ───────────────────────
// makeMessage / stagePayload / loadScenarioById route scenario fields and
// graphs through clonePlainData (JSON round-trip). These tests pin the
// undefined/function-loss semantics T-032 must preserve when the JSON clones
// are migrated to shared clone code.

test("Family B: demo scenario clones drop undefined and function members from agent message and loaded graphs", async () => {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/vibecomfy/ping": { status: 200, body: "pong" },
      "/vibecomfy/agent/status?route=auto": makeStatusResponse(),
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_a": makeScenarioResponse({
        outcome: { kind: "candidate", changes: [], callback: () => {}, ephemeral: undefined },
        change_details: {
          summary: "Added a demo output node.",
          statements: [],
          note: undefined,
          helper: () => {},
          nested: { fn: () => {} },
        },
        eligibility: { applyable: true, reason: "applyable", note: undefined, helper: () => {} },
        report: { change: {}, note: undefined, helper: () => {} },
        original_graph: {
          nodes: [
            { id: 1, type: "Input", pos: [100, 200], properties: { vibecomfy_uid: "uid-1", fn: () => {}, ephemeral: undefined } },
          ],
          links: [],
        },
        candidate_graph: {
          nodes: [
            { id: 1, type: "Input", pos: [100, 200], properties: { vibecomfy_uid: "uid-1" } },
            { id: 2, type: "Output", pos: [2400, 200], properties: { vibecomfy_uid: "uid-2", fn: () => {}, ephemeral: undefined } },
          ],
          links: [],
        },
      }),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    await harness.loadExtension();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    const runtime = await harness.loadPanelRuntime();
    const panel = runtime.currentAgentPanel();
    assert.ok(panel?.previewPicker, "preview picker is installed");

    await waitFor(() => panel.previewPicker.select.children.length > 1, { label: "scenario options" });
    const loaded = await panel.previewPicker.loadScenarioById("demo_a", { readyToApply: true });
    assert.ok(loaded, "scenario loads through to review");

    // loadedScenario graphs are clonePlainData outputs of the raw scenario:
    // undefined/function members in the payload never reach the staged graphs.
    assert.equal(
      Object.prototype.hasOwnProperty.call(loaded.original_graph.nodes[0].properties, "fn"),
      false,
      "function member dropped from loaded original graph",
    );
    assert.equal(
      Object.prototype.hasOwnProperty.call(loaded.original_graph.nodes[0].properties, "ephemeral"),
      false,
      "undefined member dropped from loaded original graph",
    );
    assert.equal(
      Object.prototype.hasOwnProperty.call(loaded.candidate_graph.nodes[1].properties, "fn"),
      false,
      "function member dropped from loaded candidate graph",
    );
    assert.equal(
      Object.prototype.hasOwnProperty.call(loaded.candidate_graph.nodes[1].properties, "ephemeral"),
      false,
      "undefined member dropped from loaded candidate graph",
    );
    assert.equal(loaded.candidate_graph.nodes[1].properties.vibecomfy_uid, "uid-2", "data members survive the clone");

    // The staged candidate graph on panel state is the same clonePlainData
    // output (loadedScenario.candidate_graph): undefined/function members are
    // gone, data members survive.
    assert.ok(panel.state.candidateGraph, "panel carries the staged candidate graph");
    assert.equal(
      Object.prototype.hasOwnProperty.call(panel.state.candidateGraph.nodes[1].properties, "fn"),
      false,
      "function member dropped from staged candidate graph",
    );
    assert.equal(
      Object.prototype.hasOwnProperty.call(panel.state.candidateGraph.nodes[1].properties, "ephemeral"),
      false,
      "undefined member dropped from staged candidate graph",
    );
    assert.equal(panel.state.candidateGraph.nodes[1].properties.vibecomfy_uid, "uid-2", "candidate uid survives the clone");

    // The applied stage applies the candidate through replaceDemoGraphPreservingViewport's
    // clonePlainData (preview_picker.js): the canvas must never receive the
    // function/undefined members from the scenario payload.
    panel.previewPicker.nextButton.click();
    await waitFor(() => panel.state.__demoStage === "applied", { label: "applied" });
    const canvasNodes = harness.getLiveNodes();
    const appliedCandidate = canvasNodes.find((node) => node.properties?.vibecomfy_uid === "uid-2");
    assert.ok(appliedCandidate, "candidate node applied to the canvas");
    assert.equal(
      Object.prototype.hasOwnProperty.call(appliedCandidate.properties, "fn"),
      false,
      "function member dropped before canvas apply",
    );
    assert.equal(
      Object.prototype.hasOwnProperty.call(appliedCandidate.properties, "ephemeral"),
      false,
      "undefined member dropped before canvas apply",
    );
  } finally {
    await harness.dispose();
  }
});
