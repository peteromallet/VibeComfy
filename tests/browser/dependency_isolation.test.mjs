import test from "node:test";
import assert from "node:assert/strict";

import { createDiagnosticsReporting } from "../../vibecomfy/comfy_nodes/web/diagnostics_reporting.js";
import { createSubmitFlowDeps } from "../../vibecomfy/comfy_nodes/web/agent_flow_deps.js";
import {
  scheduleRenderAgentPanel,
  setRenderGateway,
} from "../../vibecomfy/comfy_nodes/web/panel_scheduler.js";

test("diagnostics consumers cannot overwrite each other's download dependency", () => {
  const firstDownloads = [];
  const secondDownloads = [];
  const first = createDiagnosticsReporting({
    downloadBlob: (_blob, filename) => firstDownloads.push(filename),
  });
  const second = createDiagnosticsReporting({
    downloadBlob: (_blob, filename) => secondDownloads.push(filename),
  });
  const turn = { turn_id: "turn-1", status: "accepted" };

  second.downloadTurnAuditEntry(turn);
  first.downloadTurnAuditEntry(turn);

  assert.deepEqual(firstDownloads, ["vibecomfy-audit-accepted-turn-1.json"]);
  assert.deepEqual(secondDownloads, ["vibecomfy-audit-accepted-turn-1.json"]);
});

test("submit-flow consumers cannot overwrite each other's watchdog state or panel maps", () => {
  const first = createSubmitFlowDeps({ submitDeadlineMs: 111 });
  const second = createSubmitFlowDeps({ submitDeadlineMs: 222 });
  const panel = {};

  second.configureSubmitWatchdogDeps({ submitDeadlineMs: 333 });
  first.submitActivityByPanel.set(panel, { submitEpoch: 1 });

  assert.equal(first.configureSubmitWatchdogDeps().submitDeadlineMs, 111);
  assert.equal(second.configureSubmitWatchdogDeps().submitDeadlineMs, 333);
  assert.deepEqual(first.submitActivityByPanel.get(panel), { submitEpoch: 1 });
  assert.equal(second.submitActivityByPanel.has(panel), false);
});

function schedulerRuntime(panel) {
  return {
    agentPanel: panel,
    renderDirtyAgentPanelSections: null,
    _cancelScheduledAgentPanelRender: null,
    _scheduledAgentPanelRender: null,
    _scheduledAgentPanelRenders: [],
    _scheduledAgentPanelRenderQueued: false,
    _agentPanelRenderScheduleGeneration: 0,
  };
}

test("render gateways are runtime-scoped across two panel consumers", () => {
  const originals = {
    document: globalThis.document,
    requestAnimationFrame: globalThis.requestAnimationFrame,
    cancelAnimationFrame: globalThis.cancelAnimationFrame,
    setTimeout: globalThis.setTimeout,
    clearTimeout: globalThis.clearTimeout,
  };
  const frames = [];
  globalThis.document = {};
  globalThis.requestAnimationFrame = (callback) => {
    frames.push(callback);
    return frames.length;
  };
  globalThis.cancelAnimationFrame = () => {};
  globalThis.setTimeout = () => 1000;
  globalThis.clearTimeout = () => {};

  try {
    const rendered = [];
    const firstPanel = {
      panelId: "first",
      root: { isConnected: true },
      pendingDirtySections: [],
      state: { chatScopeId: "scope-first", scopeActivationEpoch: 1 },
    };
    const secondPanel = {
      panelId: "second",
      root: { isConnected: true },
      pendingDirtySections: [],
      state: { chatScopeId: "scope-second", scopeActivationEpoch: 1 },
    };
    const firstRuntime = schedulerRuntime(firstPanel);
    const secondRuntime = schedulerRuntime(secondPanel);
    firstPanel.__agentPanelRuntime = firstRuntime;
    secondPanel.__agentPanelRuntime = secondRuntime;

    setRenderGateway((panel) => rendered.push(`first:${panel.panelId}`), firstRuntime);
    setRenderGateway((panel) => rendered.push(`second:${panel.panelId}`), secondRuntime);
    scheduleRenderAgentPanel("first", firstPanel, ["THREAD"]);
    scheduleRenderAgentPanel("second", secondPanel, ["NOTICE"]);
    frames[0]();
    frames[1]();

    assert.deepEqual(rendered, ["first:first", "second:second"]);
  } finally {
    for (const [key, value] of Object.entries(originals)) {
      if (value === undefined) delete globalThis[key];
      else globalThis[key] = value;
    }
  }
});
