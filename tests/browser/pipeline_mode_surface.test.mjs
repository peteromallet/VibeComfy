import test from "node:test";
import assert from "node:assert/strict";

import {
  createSubmitFlow,
  normalizePipelineMode,
} from "../../vibecomfy/comfy_nodes/web/agent_submit_flow.js";
import { createBrowserHarness } from "./harness.mjs";

function waitFor(predicate, timeoutMs = 3000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      if (predicate()) return resolve();
      if (Date.now() - started > timeoutMs) return reject(new Error("timed out"));
      setTimeout(poll, 5);
    };
    poll();
  });
}

test("browser mode normalizer keeps aliases at the boundary", () => {
  assert.equal(normalizePipelineMode(undefined), "staged");
  assert.equal(normalizePipelineMode("full"), "staged");
  assert.equal(normalizePipelineMode("two_step"), "threaded");
  assert.equal(normalizePipelineMode(" THREADED "), "threaded");
  assert.equal(normalizePipelineMode("unknown"), "staged");
});

test("submit body always emits a canonical mode", () => {
  const flow = createSubmitFlow({
    submitWatchdogDepsState: {},
    submitActivityByPanel: new WeakMap(),
    pendingTransactionSnapshotByPanel: new WeakMap(),
    readOnDemandSchemasSetting: () => false,
    api: { clientId: "client" },
  });
  const body = flow.buildSubmitBody(
    {
      graph: { nodes: [], links: [] },
      route: "auto",
      pipelineMode: "two_step",
      graphHash: "full",
      structuralHash: "structural",
      liveCanvasToken: "live:1",
      idempotencyKey: "idempotent",
    },
    "edit",
    { state: {} },
  );

  assert.equal(body.pipeline_mode, "threaded");
});

test("panel exposes staged/threaded selection, persists it, and submits it", async () => {
  let submitBody = null;
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: {
            auto: {
              requested_route: "auto",
              normalized_route: "arnold",
              browser_api_key_allowed: false,
            },
          },
        },
      },
      "/vibecomfy/agent-executor": async ({ options }) => {
        submitBody = JSON.parse(options.body);
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "pipeline-session",
            turn_id: "0000",
            baseline_turn_id: null,
            outcome: { kind: "noop", reason: "done" },
            graph_unchanged: true,
            canvas_apply_allowed: false,
            apply_allowed: false,
            queue_allowed: false,
            message: "done",
          },
        };
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const mode = harness.document.getElementById("vibecomfy-agent-panel-pipeline-mode");
    assert.deepEqual(mode.children.map((option) => option.value), ["staged", "threaded"]);
    assert.equal(mode.value, "staged");

    mode.value = "threaded";
    mode.onchange();
    assert.equal(globalThis.localStorage.getItem("vibecomfy_agent_pipeline_mode"), "threaded");

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "edit it";
    await harness.document.getElementById("vibecomfy-agent-panel-submit").click();
    await waitFor(() => submitBody !== null);
    assert.equal(submitBody.pipeline_mode, "threaded");
  } finally {
    await harness.dispose();
  }
});

test("chat rehydration restores the session's canonical mode", async () => {
  const sessionId = "rehydrate-mode-session";
  const chatUrl = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(sessionId)}`;
  const harness = await createBrowserHarness({
    responses: {
      [chatUrl]: {
        status: 200,
        body: {
          ok: true,
          exists: true,
          session_id: sessionId,
          pipeline_mode: "threaded",
          latest_turn_id: null,
          messages: [],
          latest_candidate: null,
          latest_turn_lifecycle: null,
        },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: {
            auto: {
              requested_route: "auto",
              normalized_route: "arnold",
              browser_api_key_allowed: false,
            },
          },
        },
      },
    },
  });

  try {
    globalThis.localStorage.setItem("vibecomfy_active_session_id", sessionId);
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrl));
    await waitFor(() => (
      harness.document.getElementById("vibecomfy-agent-panel-pipeline-mode")?.value
        === "threaded"
    ));

    assert.equal(
      globalThis.localStorage.getItem("vibecomfy_agent_pipeline_mode"),
      "threaded",
    );
  } finally {
    await harness.dispose();
  }
});
