import test from "node:test";
import assert from "node:assert/strict";

import {
  hasPendingAgentPanelFlush,
  scheduleRenderAgentPanel,
  setRenderGateway,
} from "../../vibecomfy/comfy_nodes/web/panel_scheduler.js";
import {
  setCurrentAgentPanel,
} from "../../vibecomfy/comfy_nodes/web/panel_runtime.js";

function panel(id, scope, epoch = 1) {
  return {
    panelId: id,
    root: { isConnected: true },
    pendingDirtySections: [],
    state: { chatScopeId: scope, scopeActivationEpoch: epoch },
  };
}

async function withManualFrames(run) {
  const originals = {
    window: globalThis.window,
    document: globalThis.document,
    requestAnimationFrame: globalThis.requestAnimationFrame,
    cancelAnimationFrame: globalThis.cancelAnimationFrame,
    setTimeout: globalThis.setTimeout,
    clearTimeout: globalThis.clearTimeout,
  };
  const frames = [];
  const cancelled = new Set();
  globalThis.window = {};
  globalThis.document = {};
  globalThis.requestAnimationFrame = (callback) => {
    frames.push(callback);
    return frames.length;
  };
  globalThis.cancelAnimationFrame = (id) => cancelled.add(id);
  // Do not let the fallback timer race the manually controlled frame.
  globalThis.setTimeout = () => 1000;
  globalThis.clearTimeout = () => {};
  try {
    await run({ frames, cancelled });
  } finally {
    setRenderGateway(null);
    setCurrentAgentPanel(null);
    for (const [key, value] of Object.entries(originals)) {
      if (value === undefined) delete globalThis[key];
      else globalThis[key] = value;
    }
  }
}

test("late frame from a replaced panel cannot render or satisfy the replacement panel flush", async () => {
  await withManualFrames(async ({ frames, cancelled }) => {
    const rendered = [];
    const first = panel("panel-a", "workflow-a");
    const second = panel("panel-b", "workflow-b");
    setRenderGateway((owner) => rendered.push(owner.panelId));

    setCurrentAgentPanel(first);
    scheduleRenderAgentPanel("first-panel", first, ["THREAD"]);
    const staleFrame = frames[0];
    assert.equal(hasPendingAgentPanelFlush(first), true);

    setCurrentAgentPanel(second);
    scheduleRenderAgentPanel("second-panel", second, ["NOTICE"]);
    const currentFrame = frames[1];
    assert.equal(cancelled.has(1), true, "replacement revokes the old frame");
    assert.equal(hasPendingAgentPanelFlush(first), false);
    assert.equal(hasPendingAgentPanelFlush(second), true);

    staleFrame();
    assert.deepEqual(rendered, []);
    assert.equal(second.__renderFlushCount || 0, 0);
    assert.equal(hasPendingAgentPanelFlush(second), true);

    currentFrame();
    assert.deepEqual(rendered, ["panel-b"]);
    assert.equal(first.__renderFlushCount || 0, 0);
    assert.equal(second.__renderFlushCount, 1);
    assert.equal(hasPendingAgentPanelFlush(second), false);
  });
});

test("late frame from a departed workflow activation cannot flush the new activation", async () => {
  await withManualFrames(async ({ frames, cancelled }) => {
    const rendered = [];
    const sharedPanel = panel("panel-singleton", "workflow-a", 4);
    setRenderGateway((owner) => rendered.push({
      scope: owner.state.chatScopeId,
      epoch: owner.state.scopeActivationEpoch,
    }));

    setCurrentAgentPanel(sharedPanel);
    scheduleRenderAgentPanel("workflow-a", sharedPanel, ["THREAD"]);
    const staleFrame = frames[0];

    sharedPanel.state.chatScopeId = "workflow-b";
    sharedPanel.state.scopeActivationEpoch = 5;
    scheduleRenderAgentPanel("workflow-b", sharedPanel, ["THREAD", "NOTICE"]);
    const currentFrame = frames[1];
    assert.equal(cancelled.has(1), true, "scope activation revokes the old frame");

    staleFrame();
    assert.deepEqual(rendered, []);
    assert.equal(sharedPanel.__renderFlushCount || 0, 0);

    currentFrame();
    assert.deepEqual(rendered, [{ scope: "workflow-b", epoch: 5 }]);
    assert.equal(sharedPanel.__renderFlushCount, 1);
    assert.equal(sharedPanel.__lastRenderFlushReason, "workflow-b");
  });
});
