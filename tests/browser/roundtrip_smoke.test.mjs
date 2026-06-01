import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";

import { createBrowserHarness } from "./harness.mjs";

function canonicalizeJsonValue(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => canonicalizeJsonValue(entry));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entryValue]) => [key, canonicalizeJsonValue(entryValue)]),
    );
  }
  return value;
}

function sha256HexUtf8(value) {
  return crypto.createHash("sha256").update(JSON.stringify(canonicalizeJsonValue(value)), "utf8").digest("hex");
}

async function waitFor(predicate, { attempts = 50 } = {}) {
  for (let index = 0; index < attempts; index += 1) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error("waitFor timed out");
}

test("VibeComfy browser harness loads the extension, captures commands, loadGraphData, and reuses one persistent right-side panel root", async () => {
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };

  const harness = await createBrowserHarness({
    graph: {
      nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
      links: [],
    },
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/roundtrip": {
        status: 200,
        body: {
          graph: candidateGraph,
          report: {
            change: {
              content_edits: {
                preserved: ["uid-1"],
                edited: [],
                removed_named: [],
              },
            },
            recovery: [],
            felt: { ok: true },
          },
          version: 1,
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
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            anthropic: { requested_route: "anthropic", normalized_route: "arnold", browser_api_key_allowed: false, tos_acknowledgement_required: true },
            "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
          },
        },
      },
    },
  });

  let firstSubmit;
  let duplicateSubmit;
  try {
    await harness.loadExtension();
    const extension = harness.getExtension();
    assert.equal(extension.name, "VibeComfy.Roundtrip");
    assert.equal(harness.getCommands().length, 2);
    assert.deepEqual(harness.getMenuCommands(), [
      {
        path: ["Extensions", "VibeComfy"],
        commands: ["VibeComfy.Roundtrip", "VibeComfy.AgentEdit"],
      },
    ]);

    await harness.setup();
    const canvasMenu = harness.getCanvasMenuOptions().map((entry) => entry.content);
    assert(canvasMenu.includes("Round-trip (VibeComfy)"));
    assert(canvasMenu.includes("Edit with DeepSeek (VibeComfy)"));

    await harness.invokeCommand("VibeComfy.Roundtrip");
    assert.equal(harness.serializeCalls.length, 1);
    assert.deepEqual(
      harness.requests.map((entry) => entry.url),
      ["/system_stats", "/vibecomfy/roundtrip"],
    );

    harness.clickButton("Apply");
    assert.equal(harness.loadGraphDataCalls.length, 1);
    assert.deepEqual(harness.loadGraphDataCalls[0], candidateGraph);

    await harness.invokeCommand("VibeComfy.AgentEdit");
    await harness.invokeCommand("VibeComfy.AgentEdit");
    assert.equal(harness.getPanelRoots().length, 1);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-root")?.dataset.open, "1");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-shell")?.tagName, "DIV");
    assert.ok(harness.document.getElementById("vibecomfy-agent-panel-region-prompt"));
    assert.ok(harness.document.getElementById("vibecomfy-agent-panel-region-settings"));
    assert.ok(harness.document.getElementById("vibecomfy-agent-panel-region-history"));
    assert.ok(harness.document.getElementById("vibecomfy-agent-panel-region-candidate"));
    assert.ok(harness.document.getElementById("vibecomfy-agent-panel-region-failure"));
    assert.ok(harness.document.getElementById("vibecomfy-agent-panel-region-queue"));
    assert.ok(harness.document.getElementById("vibecomfy-agent-panel-region-audit"));
    assert.ok(harness.document.getElementById("vibecomfy-agent-panel-region-debug"));
    assert.deepEqual(harness.consoleCapture.error, []);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy agent submit sends canonical graph hash, normalized route/model fields, idempotency key, and dedupes in-flight submits", async () => {
  const graph = {
    links: [],
    nodes: [
      {
        type: "SaveImage",
        id: 2,
        properties: { z: 2, a: 1, vibecomfy_uid: "uid-2" },
        widgets_values: [{ beta: 2, alpha: 1 }],
      },
      {
        id: 1,
        type: "Input",
        properties: { vibecomfy_uid: "uid-1", nested: { y: 2, x: 1 } },
      },
    ],
    meta: { zeta: true, alpha: { d: 4, c: 3 } },
  };

  let releaseResponse;
  let firstSubmit;
  let duplicateSubmit;
  const pendingResponse = new Promise((resolve) => {
    releaseResponse = resolve;
  });

  const harness = await createBrowserHarness({
    graph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent-edit": async () => {
        await pendingResponse;
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "session-1",
            turn_id: "0001",
            baseline_turn_id: null,
            graph: { nodes: [], links: [] },
            report: { change: { content_edits: { preserved: [], edited: [], removed_named: [] } }, recovery: [] },
            apply_allowed: true,
            canvas_apply_allowed: true,
            queue_allowed: false,
            message: "candidate ready",
          },
        };
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            anthropic: { requested_route: "anthropic", normalized_route: "arnold", browser_api_key_allowed: false, tos_acknowledgement_required: true },
            "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
          },
        },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "tighten the prompt";
    harness.document.getElementById("vibecomfy-agent-panel-route").value = " codex ";
    harness.document.getElementById("vibecomfy-agent-panel-model").value = "  gpt-5.1  ";

    const submitButton = harness.document.getElementById("vibecomfy-agent-panel-submit");
    firstSubmit = submitButton.click();
    duplicateSubmit = submitButton.click();

    await waitFor(() => harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit").length === 1);

    const request = harness.requests.find((entry) => entry.url === "/vibecomfy/agent-edit");
    const payload = JSON.parse(request.body);
    assert.deepEqual(payload.graph, graph);
    assert.equal(payload.route, "openai-codex");
    assert.equal(payload.model, "gpt-5.1");
    assert.equal(payload.client_graph_hash, sha256HexUtf8(graph));
    assert.equal("baseline_turn_id" in payload, false);
    assert.match(
      payload.idempotency_key,
      /^submit:new:openai-codex:gpt-5\.1:[0-9a-f]{12}:[0-9a-f-]+$/,
    );

    releaseResponse();
    await firstSubmit;

    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "AWAITING_REVIEW");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-submit")?.textContent, "Submit");
  } finally {
    releaseResponse?.();
    await Promise.allSettled([firstSubmit, duplicateSubmit].filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy agent panel renders rich candidate and failure states without mutating the canvas on failed or malformed responses", async () => {
  const responses = [
    {
      status: 200,
      body: {
        ok: true,
        session_id: "session-2",
        turn_id: "0003",
        baseline_turn_id: "0002",
        canvas_apply_allowed: false,
        apply_allowed: false,
        queue_allowed: false,
        message: "Candidate blocked for queue review.",
        graph: {
          nodes: [
            { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
            { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-3" } },
          ],
          links: [],
        },
        report: {
          change: {
            content_edits: {
              preserved: ["uid-1"],
              edited: ["uid-2"],
              new_auto_placed: ["uid-3"],
              removed: ["uid-7"],
              removed_named: [{ uid: "uid-9", class_type: "SaveImage" }],
              virtual_wires_degraded: [{ uid: "uid-vw", detail: "degraded" }],
              stripped_helpers: ["helper-1"],
            },
          },
          recovery: [
            {
              node_id: "77",
              class_type: "SchemaLessNode",
              schema_less: true,
              provider: "object_info",
              confidence: 0.1,
              diagnostic: "missing schema",
            },
          ],
        },
        artifacts: {
          python: "/tmp/after.py",
          candidate_ui: "/tmp/candidate.ui.json",
        },
        audit_ref: {
          path: "/tmp/audit.json",
          sha256: "abc123",
        },
      },
    },
    {
      status: 400,
      body: {
        ok: false,
        kind: "ValidationError",
        stage: "emit",
        progress: 0.75,
        retryable: true,
        graph_unchanged: true,
        user_facing_message: "Validation failed.",
        next_action: "Fix the emitted graph.",
        agent_failure_context: { explanation: "missing input", field: "images" },
        canvas_apply_allowed: false,
        queue_allowed: false,
        audit_ref: { path: "/tmp/failure-audit.json" },
      },
    },
    {
      status: 200,
      body: {
        ok: true,
        message: "incomplete",
      },
    },
  ];

  const harness = await createBrowserHarness({
    graph: {
      nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
      links: [],
    },
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            anthropic: { requested_route: "anthropic", normalized_route: "arnold", browser_api_key_allowed: false, tos_acknowledgement_required: true },
            "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-edit": async () => responses.shift(),
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "make it safer";
    await harness.clickButton("Submit");

    const successText = harness.textDump();
    assert.match(successText, /Candidate blocked for queue review\./);
    assert.match(successText, /canvas_apply_allowed=false/);
    assert.match(successText, /queue_allowed=false/);
    assert.match(successText, /preserved: uid-1/);
    assert.match(successText, /edited: uid-2/);
    assert.match(successText, /new_auto_placed: uid-3/);
    assert.match(successText, /removed_named: uid-9 \(SaveImage\)/);
    assert.match(successText, /stripped_helper: helper-1/);
    assert.match(successText, /schema_less_queue_blocker/);
    assert.match(successText, /python: \/tmp\/after\.py/);
    assert.match(successText, /audit: \/tmp\/audit\.json/);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.loadGraphDataCalls.length, 0);

    await harness.clickButton("Reject Candidate");
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "break it";
    await harness.clickButton("Submit");

    const failureText = harness.textDump();
    assert.match(failureText, /ValidationError @ emit/);
    assert.match(failureText, /backend stage: emit \(0.75\)/);
    assert.match(failureText, /Fix the emitted graph\./);
    assert.match(failureText, /agent failure context/);
    assert.match(failureText, /failure-audit\.json/);
    assert.equal(harness.loadGraphDataCalls.length, 0);

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "malformed response";
    await harness.clickButton("Submit");
    assert.match(harness.textDump(), /MalformedResponse/);
    assert.equal(harness.loadGraphDataCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before loading, and blocks failed accepts", async () => {
  const initialGraph = {
    extra: { ds: { scale: 1.25 }, reroutes: [{ id: "r1", pos: [4, 8] }] },
    groups: [{ title: "seed", bounding: [10, 20, 30, 40], color: "#333333" }],
    config: { links_ontop: true },
    nodes: [{ id: 1, type: "Input", pos: [100, 200], size: [320, 80], properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  const submitResponses = [
    {
      status: 200,
      body: {
        ok: true,
        session_id: "session-apply",
        turn_id: "0001",
        baseline_turn_id: null,
        canvas_apply_allowed: false,
        apply_allowed: true,
        queue_allowed: false,
        message: "Preview only.",
        graph: candidateGraph,
        report: { change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } }, recovery: [] },
        audit_ref: { path: "/tmp/preview-audit.json" },
      },
    },
    {
      status: 200,
      body: {
        ok: true,
        session_id: "session-apply",
        turn_id: "0002",
        baseline_turn_id: null,
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        message: "Allowed candidate.",
        graph: candidateGraph,
        report: { change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } }, recovery: [] },
        audit_ref: { path: "/tmp/allowed-audit.json" },
      },
    },
    {
      status: 200,
      body: {
        ok: true,
        session_id: "session-apply",
        turn_id: "0003",
        baseline_turn_id: "0002",
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        message: "Stale candidate.",
        graph: candidateGraph,
        report: { change: { content_edits: { preserved: ["uid-1"], edited: [], removed_named: [] } }, recovery: [] },
      },
    },
    {
      status: 200,
      body: {
        ok: true,
        session_id: "session-apply",
        turn_id: "0004",
        baseline_turn_id: "0002",
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        message: "Backend will reject accept.",
        graph: candidateGraph,
        report: { change: { content_edits: { preserved: ["uid-1"], edited: [], removed_named: [] } }, recovery: [] },
      },
    },
  ];
  const acceptResponses = [
    {
      status: 200,
      body: {
        ok: true,
        action: "accept",
        session_id: "session-apply",
        turn_id: "0002",
        baseline_turn_id: "0002",
        audit_ref: { path: "/tmp/accept-audit.json" },
      },
    },
    {
      status: 409,
      body: {
        ok: false,
        kind: "EditorAheadConflict",
        stage: "accept",
        graph_unchanged: true,
        user_facing_message: "Accept rejected.",
        session_id: "session-apply",
        turn_id: "0004",
        baseline_turn_id: "0002",
      },
    },
  ];
  const rejectResponses = [
    {
      status: 200,
      body: {
        ok: true,
        action: "reject",
        session_id: "session-apply",
        turn_id: "0001",
        baseline_turn_id: null,
        audit_ref: { path: "/tmp/reject-audit.json" },
      },
    },
  ];

  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            anthropic: { requested_route: "anthropic", normalized_route: "arnold", browser_api_key_allowed: false, tos_acknowledgement_required: true },
            "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-edit": async () => submitResponses.shift(),
      "/vibecomfy/agent-edit/accept": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.equal(body.session_id, "session-apply");
        assert.match(body.turn_id, /^000[24]$/);
        assert.equal(body.client_graph_hash, sha256HexUtf8(initialGraph));
        assert.match(body.idempotency_key, /^accept:session-apply:000[24]:[0-9a-f]{12}:/);
        return acceptResponses.shift();
      },
      "/vibecomfy/agent-edit/reject": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.equal(body.session_id, "session-apply");
        assert.equal(body.turn_id, "0001");
        assert.equal(body.client_graph_hash, sha256HexUtf8(initialGraph));
        assert.match(body.idempotency_key, /^reject:session-apply:0001:[0-9a-f]{12}:/);
        return rejectResponses.shift();
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    const applyButton = harness.document.getElementById("vibecomfy-agent-panel-apply");
    const undoButton = harness.document.getElementById("vibecomfy-agent-panel-undo");

    prompt.value = "preview only";
    await harness.clickButton("Submit");
    assert.equal(applyButton.disabled, true);
    await harness.clickButton("Apply Candidate");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 0);
    assert.equal(harness.loadGraphDataCalls.length, 0);

    await harness.clickButton("Reject Candidate");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/reject").length, 1);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), initialGraph);
    assert.match(harness.textDump(), /rejected/);
    assert.match(harness.textDump(), /\/tmp\/reject-audit\.json/);

    prompt.value = "allowed";
    await harness.clickButton("Submit");
    assert.equal(applyButton.disabled, false);
    const operationCountBeforeApply = harness.operationLog.length;
    const applyPromise = harness.clickButton("Apply Candidate");
    await applyPromise;
    const acceptIndex = harness.requests.findIndex((entry) => entry.url === "/vibecomfy/agent-edit/accept");
    assert.notEqual(acceptIndex, -1);
    const applyEvents = harness.operationLog.slice(operationCountBeforeApply);
    const acceptResponseIndex = applyEvents.findIndex((entry) => entry.kind === "response" && entry.url === "/vibecomfy/agent-edit/accept" && entry.status === 200);
    const loadIndex = applyEvents.findIndex((entry) => entry.kind === "loadGraphData");
    assert.notEqual(acceptResponseIndex, -1);
    assert.notEqual(loadIndex, -1);
    assert(acceptResponseIndex < loadIndex, "accept response should be recorded before app.loadGraphData()");
    assert.equal(harness.loadGraphDataCalls.length, 1);
    assert.deepEqual(harness.loadGraphDataCalls[0], candidateGraph);
    assert.equal(harness.app.canvas.graph._nodes.find((node) => node.id === 2)?.boxcolor, "#ffc107");
    assert.match(harness.textDump(), /Applied candidate feedback: changed nodes were highlighted on the canvas temporarily\./);
    assert.match(harness.textDump(), /Edited uid-2/);
    assert.match(harness.textDump(), /undo_stack_depth/);
    assert.equal(undoButton.disabled, false);

    const blockedQueueResult = harness.app.queuePrompt("prompt-1");
    assert.equal(blockedQueueResult, null);
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.match(harness.textDump(), /Queue blocked for turn 0002 because queue_allowed=false\./);

    await harness.clickButton("Undo Last Apply");
    assert.equal(harness.loadGraphDataCalls.length, 2);
    assert.deepEqual(harness.loadGraphDataCalls[1], initialGraph);
    assert.deepEqual(harness.getCurrentGraph(), initialGraph);
    assert.match(harness.textDump(), /undone_turn_id/);
    assert.match(harness.textDump(), /"0002"/);
    assert.match(harness.textDump(), /undo_stack_depth/);
    assert.equal(undoButton.disabled, true);

    const allowedQueueResult = harness.app.queuePrompt("prompt-2");
    assert.deepEqual(allowedQueueResult, { queued: true, args: ["prompt-2"] });
    assert.equal(harness.queuePromptCalls.length, 1);

    await harness.clickButton("Undo Last Apply");
    assert.equal(harness.loadGraphDataCalls.length, 2);

    harness.setCurrentGraph(initialGraph);
    prompt.value = "stale";
    await harness.clickButton("Submit");
    harness.setCurrentGraph({ nodes: [{ id: 99, type: "Dirty" }], links: [] });
    await harness.clickButton("Apply Candidate");
    assert.match(harness.textDump(), /The canvas changed after this candidate was generated/);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.loadGraphDataCalls.length, 2);

    harness.setCurrentGraph(initialGraph);
    prompt.value = "accept fails";
    await harness.clickButton("Submit");
    await harness.clickButton("Apply Candidate");
    assert.match(harness.textDump(), /EditorAheadConflict/);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 2);
    assert.equal(harness.loadGraphDataCalls.length, 2);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy falls back to panel-only changed-node and queue warnings when live node lookup or a safe native queue hook is unavailable", async () => {
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: {} }],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: {} },
      { id: 2, type: "SaveImage", properties: {} },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };

  const harness = await createBrowserHarness({
    graph: initialGraph,
    withQueuePrompt: false,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            anthropic: { requested_route: "anthropic", normalized_route: "arnold", browser_api_key_allowed: false, tos_acknowledgement_required: true },
            "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-edit": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-fallback",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          message: "Fallback candidate.",
          graph: candidateGraph,
          report: { change: { content_edits: { preserved: [], edited: ["uid-missing"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: "session-fallback",
          turn_id: "0001",
          baseline_turn_id: "0001",
        },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "fallback";
    await harness.clickButton("Submit");
    await harness.clickButton("Apply Candidate");

    assert.match(harness.textDump(), /Applied candidate feedback: changed nodes listed here because live node lookup was unavailable\./);
    assert.match(harness.textDump(), /Edited uid-missing/);
    assert.match(harness.textDump(), /Native queue hook unavailable: `app\.queuePrompt` was not found\./);
    assert.match(harness.textDump(), /native queue guard: panel warning fallback only/);
    assert.equal(harness.consoleCapture.warn.filter((line) => line.includes("queue guard fallback active")).length, 1);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy provider settings normalize routes, use DeepSeek-only password entry, and surface soft rejections without re-rendering raw keys", async () => {
  const credentialBodies = [];
  const routeOptions = {
    auto: {
      requested_route: "auto",
      normalized_route: "arnold",
      browser_api_key_allowed: false,
      guidance: "Use local Arnold/Hermes setup for this route. Browser-submitted API keys are not stored.",
      tos_acknowledgement_required: false,
    },
    deepseek: {
      requested_route: "deepseek",
      normalized_route: "deepseek",
      browser_api_key_allowed: true,
      guidance: "DeepSeek browser key submission is supported and stored locally.",
      tos_acknowledgement_required: false,
    },
    anthropic: {
      requested_route: "anthropic",
      normalized_route: "arnold",
      browser_api_key_allowed: false,
      guidance: "Anthropic/Claude runs through local Arnold/Hermes. Browser keys are not accepted.",
      tos_acknowledgement_required: true,
    },
    "openai-codex": {
      requested_route: "openai-codex",
      normalized_route: "arnold",
      browser_api_key_allowed: false,
      guidance: "OpenAI Codex runs through local Arnold/Hermes. Browser keys are not accepted.",
      tos_acknowledgement_required: false,
    },
  };

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: routeOptions,
        },
      },
      "/vibecomfy/agent/status?route=deepseek": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "deepseek",
          route_options: routeOptions,
        },
      },
      "/vibecomfy/agent/status?route=deepseek&model=agent-model": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "deepseek",
          model: "agent-model",
          route_options: routeOptions,
        },
      },
      "/vibecomfy/agent/status?route=anthropic&model=agent-model": {
        status: 200,
        body: {
          ok: false,
          provider_available: false,
          route: "arnold",
          requested_route: "anthropic",
          model: "agent-model",
          route_options: routeOptions,
        },
      },
      "/vibecomfy/agent/status?route=openai-codex&model=agent-model": {
        status: 200,
        body: {
          ok: false,
          provider_available: false,
          route: "arnold",
          requested_route: "openai-codex",
          model: "agent-model",
          route_options: routeOptions,
        },
      },
      "/vibecomfy/agent/credentials": async ({ options }) => {
        const body = JSON.parse(options.body);
        credentialBodies.push(body);
        if (body.provider === "deepseek") {
          return {
            status: 200,
            body: { ok: true, stored: true, provider: "deepseek" },
          };
        }
        return {
          status: 200,
          body: {
            ok: true,
            stored: false,
            provider: "arnold",
            requested_route: body.provider,
            reason: "OpenAI Codex runs through local Arnold/Hermes. Browser keys are not accepted.",
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

    const routeSelect = harness.document.getElementById("vibecomfy-agent-panel-route");
    assert.deepEqual(routeSelect.children.map((entry) => entry.value), ["auto", "deepseek", "anthropic", "openai-codex"]);

    routeSelect.value = "deepseek";
    routeSelect.onchange();
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=deepseek"));
    const apiKeyInput = harness.document.getElementById("vibecomfy-agent-panel-api-key");
    assert.notEqual(apiKeyInput?.style.display, "none");
    assert.equal(apiKeyInput?.type, "password");

    harness.document.getElementById("vibecomfy-agent-panel-model").value = "agent-model";
    apiKeyInput.value = "deepseek-secret";
    await harness.clickButton("Save Settings");
    await waitFor(() => credentialBodies.length === 1);
    assert.deepEqual(credentialBodies[0], { provider: "deepseek", api_key: "deepseek-secret" });
    assert.equal(apiKeyInput.value, "");
    assert.doesNotMatch(harness.textDump(), /deepseek-secret/);

    routeSelect.value = "anthropic";
    routeSelect.onchange();
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=anthropic&model=agent-model"));
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-api-key")?.style.display, "none");
    assert.match(harness.textDump(), /TODO\(S0\): Claude\/Anthropic ToS acknowledgement placeholder\./);

    routeSelect.value = "openai-codex";
    routeSelect.onchange();
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=openai-codex&model=agent-model"));
    harness.document.getElementById("vibecomfy-agent-panel-api-key").value = "codex-secret";
    await harness.clickButton("Save Settings");
    await waitFor(() => credentialBodies.length === 2);
    assert.deepEqual(credentialBodies[1], { provider: "openai-codex", api_key: "codex-secret" });
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-api-key").value, "");
    assert.match(harness.textDump(), /Browser keys are not accepted/);
    assert.doesNotMatch(harness.textDump(), /codex-secret/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy surfaces network and malformed accept failures with retry guidance and without canvas mutation", async () => {
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  let submitCount = 0;
  let acceptCount = 0;

  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            anthropic: { requested_route: "anthropic", normalized_route: "arnold", browser_api_key_allowed: false, tos_acknowledgement_required: true },
            "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-edit": async () => {
        submitCount += 1;
        if (submitCount === 1) {
          throw new Error("connect ECONNREFUSED 127.0.0.1:8188");
        }
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "session-network",
            turn_id: "0001",
            baseline_turn_id: null,
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: false,
            message: "Candidate after retry.",
            graph: candidateGraph,
            report: { change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } }, recovery: [] },
            audit_ref: { path: "/tmp/network-turn.json" },
          },
        };
      },
      "/vibecomfy/agent-edit/accept": async () => {
        acceptCount += 1;
        return {
          status: 200,
          body: acceptCount === 1
            ? { ok: true }
            : {
                ok: true,
                action: "accept",
                session_id: "session-network",
                turn_id: "0001",
                baseline_turn_id: "0001",
                audit_ref: { path: "/tmp/network-accept.json" },
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

    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    const submitButton = harness.document.getElementById("vibecomfy-agent-panel-submit");
    const applyButton = harness.document.getElementById("vibecomfy-agent-panel-apply");

    prompt.value = "retry me";
    await harness.clickButton("Submit");
    assert.match(harness.textDump(), /NetworkError/);
    assert.match(harness.textDump(), /Retry once the local ComfyUI backend responds again\./);
    assert.equal(submitButton.disabled, false);
    assert.equal(harness.loadGraphDataCalls.length, 0);

    await harness.clickButton("Submit");
    assert.match(harness.textDump(), /Candidate after retry\./);
    assert.equal(applyButton.disabled, false);

    await harness.clickButton("Apply Candidate");
    assert.match(harness.textDump(), /MalformedResponse/);
    assert.match(harness.textDump(), /incomplete accept envelope/);
    assert.match(harness.textDump(), /Retry Apply or inspect the raw response in the debug panel\./);
    assert.equal(harness.loadGraphDataCalls.length, 0);

    await harness.clickButton("Apply Candidate");
    assert.equal(harness.loadGraphDataCalls.length, 1);
    assert.deepEqual(harness.loadGraphDataCalls[0], candidateGraph);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy turn history tracks pending/candidate/applied/rejected/failed statuses across multiple turns and provides audit download buttons for both success and failure turns", async () => {
  const turnResponses = [
    // Turn 1: successful candidate
    {
      status: 200,
      body: {
        ok: true,
        session_id: "session-1",
        turn_id: "0001",
        baseline_turn_id: null,
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        message: "First turn candidate ready.",
        graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-a" } }], links: [] },
        report: { change: { content_edits: { preserved: ["uid-a"], edited: [], removed_named: [] } }, recovery: [] },
        audit_ref: { path: "/tmp/audit-turn-0001.json", sha256: "abc111" },
      },
    },
    // Turn 2: failure
    {
      status: 400,
      body: {
        ok: false,
        kind: "ValidationError",
        stage: "emit",
        retryable: true,
        graph_unchanged: true,
        user_facing_message: "Validation failed for turn 2.",
        next_action: "Fix inputs",
        session_id: "session-1",
        turn_id: "0002",
        baseline_turn_id: "0001",
        canvas_apply_allowed: false,
        queue_allowed: false,
        audit_ref: { path: "/tmp/audit-turn-0002.json" },
        agent_failure_context: { explanation: "bad input" },
      },
    },
  ];

  const harness = await createBrowserHarness({
    graph: {
      nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
      links: [],
    },
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            anthropic: { requested_route: "anthropic", normalized_route: "arnold", browser_api_key_allowed: false, tos_acknowledgement_required: true },
            "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-edit": async () => turnResponses.shift(),
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: "session-1",
          turn_id: "0001",
          baseline_turn_id: "0001",
          audit_ref: { path: "/tmp/audit-turn-0001-accept.json", sha256: "abc222" },
        },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    // ── Turn 1: submit, get candidate, apply ──
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "turn 1 task";
    await harness.clickButton("Submit");

    const afterCandidateText = harness.textDump();
    assert.match(afterCandidateText, /First turn candidate ready/);
    assert.match(afterCandidateText, /candidate/i);
    assert.match(afterCandidateText, /turn 0001/);
    assert.match(afterCandidateText, /\/tmp\/audit-turn-0001\.json/);
    // Should have an Audit download button in history for this turn
    assert.match(afterCandidateText, /Audit ↓/);

    // Apply turn 1
    await harness.clickButton("Apply Candidate");
    const afterApplyText = harness.textDump();
    assert.match(afterApplyText, /applied/i);
    assert.equal(harness.loadGraphDataCalls.length, 1);

    // ── Turn 2: submit, get failure ──
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "turn 2 task";
    await harness.clickButton("Submit");

    const afterFailureText = harness.textDump();
    assert.match(afterFailureText, /ValidationError/);
    assert.match(afterFailureText, /failed/i);
    assert.match(afterFailureText, /turn 0002/);
    assert.match(afterFailureText, /\/tmp\/audit-turn-0002\.json/);
    // Canvas should not have been mutated on failure
    assert.equal(harness.loadGraphDataCalls.length, 1);

    // History should contain both turns
    // (check for both applied and failed status badges)
    assert.match(afterFailureText, /applied/i);
    assert.match(afterFailureText, /failed/i);

    // Audit region should have a download button
    assert.match(harness.textDump(), /Download Audit Envelope/);
  } finally {
    await harness.dispose();
  }
});
