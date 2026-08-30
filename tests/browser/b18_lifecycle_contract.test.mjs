import assert from "node:assert/strict";
import test from "node:test";

import { createAgentPreviewCache } from "../../vibecomfy/comfy_nodes/web/agent_preview_cache.js";
import {
  executionEventTurnEntry,
  mergeBatchTurnEntry,
} from "../../vibecomfy/comfy_nodes/web/agent_turn_reducer.js";
import { reduceAgentActivityFeed } from "../../vibecomfy/comfy_nodes/web/agent_turn_feed.js";

function makeFeedActivity(overrides = {}) {
  return Object.freeze({
    session_id: "b18-session",
    turn_id: "b18-turn",
    turn_number: 1,
    status: "in_progress",
    headline: "Working...",
    ...overrides,
  });
}

test("B18 storage-disabled scope identity is stable for the module lifetime", async () => {
  delete globalThis.sessionStorage;
  delete globalThis.localStorage;
  const resolver = await import(
    `../../vibecomfy/comfy_nodes/web/scope_resolver.js?b18-disabled=${Date.now()}`,
  );
  const graph = { nodes: [{ id: 1, type: "SaveImage" }], links: [] };

  const first = resolver.computeScopeId(graph);
  const second = resolver.computeScopeId(graph);
  assert.equal(first, second);
  assert.match(first, /^[a-z0-9]+-[a-z0-9]+:[0-9a-f]{16}$/);
});

test("B18 snapshots use JSON clone semantics and preserve __proto__ data", async () => {
  const {
    saveScopeSnapshot,
    restoreScopeSnapshot,
    forgetScopeSnapshot,
  } = await import("../../vibecomfy/comfy_nodes/web/panel_runtime.js");
  const scopeId = `b18-snapshot-${Date.now()}`;
  const state = JSON.parse(
    '{"__proto__":{"safe":true},"nested":{"value":1},"undoStack":["canvas"]}',
  );
  const panel = { state };

  saveScopeSnapshot(scopeId, panel);
  state.nested.value = 99;
  state.undoStack.push("new-canvas-entry");
  Object.defineProperty(state, "__proto__", {
    value: { safe: false }, enumerable: true, writable: true, configurable: true,
  });

  assert.equal(restoreScopeSnapshot(scopeId, panel), true);
  assert.equal(Object.prototype.hasOwnProperty.call(state, "__proto__"), true);
  assert.deepEqual(state.__proto__, { safe: true });
  assert.equal(state.nested.value, 1);
  assert.deepEqual(state.undoStack, ["canvas", "new-canvas-entry"]);
  assert.equal(Object.prototype.safe, undefined);

  const cyclic = { state: { cycle: null } };
  cyclic.state.cycle = cyclic.state;
  assert.throws(() => saveScopeSnapshot(`${scopeId}-cycle`, cyclic), TypeError);
  forgetScopeSnapshot(scopeId);
});

test("B18 candidate-only scope switches exclude live callback state", async () => {
  const { createAgentEditState, transition } = await import(
    "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js",
  );
  const {
    getAgentPanelRuntime,
    forgetScopeSnapshot,
  } = await import("../../vibecomfy/comfy_nodes/web/panel_runtime.js");
  const runtime = getAgentPanelRuntime();
  const cases = [
    {
      name: "refresh hook",
      state: { chooseEngineRefresh: () => {} },
    },
    {
      name: "navigate hook",
      state: { chooseEngineNavigateTo: () => {} },
    },
    {
      name: "both choose-engine hooks",
      state: {
        chooseEngineRefresh: () => {},
        chooseEngineNavigateTo: () => {},
      },
    },
    {
      name: "refresh hook with submit in flight",
      state: { chooseEngineRefresh: () => {}, inFlightSubmit: Promise.resolve() },
    },
    {
      name: "navigate hook with apply in flight",
      state: { chooseEngineNavigateTo: () => {}, inFlightApply: Promise.resolve() },
    },
    {
      name: "both hooks with rebaseline in flight",
      state: {
        chooseEngineRefresh: () => {},
        chooseEngineNavigateTo: () => {},
        inFlightRebaseline: Promise.resolve(),
      },
    },
  ];

  for (const [index, testCase] of cases.entries()) {
    const departingScopeId = `b18-candidate-only-${Date.now()}-${index}`;
    const arrivingScopeId = `${departingScopeId}-next`;
    const panel = {
      state: {
        ...createAgentEditState(),
        chatScopeId: departingScopeId,
        candidateGraph: { nodes: [{ id: index + 1 }], links: [] },
        candidateGraphHash: `candidate-${index}`,
        // A future live hook must be protected by the generic guard as well.
        liveCandidateHook: () => {},
        ...testCase.state,
      },
    };

    assert.doesNotThrow(
      () => transition(panel, "SCOPE_SWITCH", {
        scopeId: arrivingScopeId,
        fingerprint: `fingerprint-${index}`,
      }),
      testCase.name,
    );

    const snapshot = runtime._scopeSnapshots.get(departingScopeId);
    assert.ok(snapshot, `${testCase.name}: departing snapshot exists`);
    assert.equal(Object.hasOwn(snapshot, "chooseEngineRefresh"), false);
    assert.equal(Object.hasOwn(snapshot, "chooseEngineNavigateTo"), false);
    assert.equal(Object.hasOwn(snapshot, "liveCandidateHook"), false);
    assert.deepEqual(snapshot.candidateGraph, {
      nodes: [{ id: index + 1 }],
      links: [],
    });
    assert.equal(snapshot.candidateGraphHash, `candidate-${index}`);
    assert.equal(snapshot.inFlightSubmit, null);
    assert.equal(snapshot.inFlightApply, null);
    assert.equal(snapshot.inFlightRebaseline, null);
    forgetScopeSnapshot(departingScopeId);
  }
});

test("B18 preview exceptions return a typed failure instead of an empty diff", () => {
  const panel = {
    state: {
      candidateGraphHash: "candidate-hash",
      sessionId: "session",
      turnId: "turn",
    },
  };
  const cache = createAgentPreviewCache({
    app: null,
    canonicalJsonString: () => "signature",
    captureLiveCanvasRevision: () => 1,
    compactNetFieldChanges: () => [],
    computePreviewDiffFacade: () => {
      throw new Error("facade should not run");
    },
    createIntentGraphAdapter: () => ({ capture: () => ({ ok: true, data: { graph: {} } }) }),
    currentAgentPanel: () => panel,
    getLiveGraph: () => ({ nodes: [], links: [] }),
    getLiveGraphNodes: () => [],
    getUid: () => null,
    prepareCandidateGraphForPanel: () => {
      throw new Error("hostile candidate");
    },
    readWidgetValues: () => [],
    safePreviewLogDetail: (error) => error.message,
  });

  const failure = cache.computePreviewDiff({ nodes: [] }, {});
  assert.deepEqual(failure, {
    ok: false,
    kind: "PreviewError",
    failure_kind: "PreviewError",
    stage: "preview",
    message: "Unable to compute preview diff.",
  });
  assert.equal(Object.hasOwn(failure, "edited"), false);
});

test("B18 durable status cannot default to done or erase terminal state", () => {
  const missing = executionEventTurnEntry({
    session_id: "session",
    turn_id: "turn-missing",
    message: "still working",
  });
  assert.equal(missing.status, "unknown");

  const explicitUnknown = executionEventTurnEntry({
    entry_type: "durable",
    session_id: "session",
    turn_id: "turn-unknown",
    status: "mystery",
  });
  assert.equal(explicitUnknown.status, "mystery");

  const merged = mergeBatchTurnEntry(
    { entry_type: "batch", status: "done", source_priority: 1, turn_number: 1 },
    { entry_type: "batch", status: "unknown", source_priority: 2, turn_number: 1 },
  );
  assert.equal(merged.status, "done");

  const mergedProgress = mergeBatchTurnEntry(
    { entry_type: "batch", status: "done", source_priority: 1, turn_number: 1 },
    { entry_type: "batch", status: "in_progress", source_priority: 2, turn_number: 1 },
  );
  assert.equal(mergedProgress.status, "done");
});

test("B18 feed rejects unknown, blank, and missing HTTP statuses over every terminal variant", () => {
  for (const terminalStatus of ["done", "clarify", "budget_exhausted", "error"]) {
    const feed = [makeFeedActivity({ status: terminalStatus })];
    const missingStatus = makeFeedActivity({ headline: "Invalid replacement" });
    const { status: _missingStatus, ...missingStatusActivity } = missingStatus;

    for (const incoming of [
      makeFeedActivity({ status: "garbage", headline: "Invalid replacement" }),
      makeFeedActivity({ status: "", headline: "Invalid replacement" }),
      missingStatusActivity,
    ]) {
      const result = reduceAgentActivityFeed(
        feed,
        incoming,
        { source: "http" },
      );
      assert.equal(result, feed, `${terminalStatus} must reject ${JSON.stringify(incoming)}`);
      assert.equal(result[0].status, terminalStatus);
      assert.equal(result[0].headline, "Working...");
    }
  }
});

test("B18 feed preserves known HTTP authority, including in_progress and error", () => {
  for (const status of ["progress", "in_progress", "done", "clarify", "budget_exhausted", "error"]) {
    const feed = [makeFeedActivity({ status: "done" })];
    const result = reduceAgentActivityFeed(
      feed,
      makeFeedActivity({ status, headline: `HTTP ${status}` }),
      { source: "http" },
    );
    assert.equal(result.length, 1);
    assert.equal(result[0].status, status);
    assert.equal(result[0].headline, `HTTP ${status}`);
  }
});

test("B18 feed keeps terminal state against websocket non-terminal statuses", () => {
  for (const terminalStatus of ["done", "clarify", "budget_exhausted", "error"]) {
    const feed = [makeFeedActivity({ status: terminalStatus })];
    const result = reduceAgentActivityFeed(
      feed,
      makeFeedActivity({ status: "in_progress", headline: "Websocket still working" }),
      { source: "websocket" },
    );
    assert.equal(result, feed, `${terminalStatus} must reject websocket in_progress`);
    assert.equal(result[0].status, terminalStatus);
  }
});
