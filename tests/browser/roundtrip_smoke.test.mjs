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

const CANONICAL_HASH_PAYLOADS = [
  {
    graph: {
      meta: { locale: "café 漢字", seed: 9007199254740991, cfg: 7.5 },
      nodes: [
        {
          id: 2,
          type: "SaveImage",
          widgets_values: [{ beta: 2, alpha: 1 }, ["frame-1", { z: 3, a: 2 }]],
          properties: { vibecomfy_uid: "uid-2", nested: { zeta: 2, alpha: 1 } },
        },
        {
          id: 1,
          type: "Input",
          properties: { vibecomfy_uid: "uid-1", prompt: "naïve façade" },
        },
      ],
      links: [[1, 1, 0, 2, 0, "IMAGE"]],
    },
  },
  {
    graph: {
      links: [],
      nodes: [
        {
          id: 4,
          type: "KSampler",
          widgets_values: [123456789, 20, 0.125, "euler"],
          properties: { vibecomfy_uid: "uid-4", labels: ["ä", "ß", "ç"] },
        },
      ],
      extras: {
        sorted_key_edge_case: { zebra: 1, alpha: 2, middle: { omega: 9, beta: 3 } },
      },
    },
  },
  {
    graph: {
      nodes: [
        {
          id: 7,
          type: "PreviewImage",
          properties: { vibecomfy_uid: "uid-7", floats: [0.5, 1.25, 2.75] },
        },
      ],
      links: [],
      audit: {
        reviewer: { notes: ["résumé", "jalapeño"], accepted: false },
        history: [{ turn_id: "0001", state: "candidate" }, { turn_id: "0002", state: "unknown" }],
      },
    },
  },
];

async function waitFor(predicate, { attempts = 50 } = {}) {
  for (let index = 0; index < attempts; index += 1) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error("waitFor timed out");
}

test("VibeComfy browser canonical hash helper sorts object keys while preserving array order", () => {
  for (const payload of CANONICAL_HASH_PAYLOADS) {
    assert.match(sha256HexUtf8(payload), /^[0-9a-f]{64}$/);
  }

  const sameGraphDifferentKeyOrder = {
    graph: {
      links: [[1, 1, 0, 2, 0, "IMAGE"]],
      meta: { cfg: 7.5, seed: 9007199254740991, locale: "café 漢字" },
      nodes: [
        {
          type: "SaveImage",
          id: 2,
          properties: { nested: { alpha: 1, zeta: 2 }, vibecomfy_uid: "uid-2" },
          widgets_values: [{ alpha: 1, beta: 2 }, ["frame-1", { a: 2, z: 3 }]],
        },
        {
          type: "Input",
          id: 1,
          properties: { prompt: "naïve façade", vibecomfy_uid: "uid-1" },
        },
      ],
    },
  };
  const arrayOrderChanged = {
    graph: {
      meta: { locale: "café 漢字", seed: 9007199254740991, cfg: 7.5 },
      nodes: [
        {
          id: 2,
          type: "SaveImage",
          widgets_values: [["frame-1", { z: 3, a: 2 }], { beta: 2, alpha: 1 }],
          properties: { vibecomfy_uid: "uid-2", nested: { zeta: 2, alpha: 1 } },
        },
        {
          id: 1,
          type: "Input",
          properties: { vibecomfy_uid: "uid-1", prompt: "naïve façade" },
        },
      ],
      links: [[1, 1, 0, 2, 0, "IMAGE"]],
    },
  };

  assert.equal(sha256HexUtf8(CANONICAL_HASH_PAYLOADS[0]), sha256HexUtf8(sameGraphDifferentKeyOrder));
  assert.notEqual(sha256HexUtf8(CANONICAL_HASH_PAYLOADS[0]), sha256HexUtf8(arrayOrderChanged));
});

test("VibeComfy structural graph projection ignores volatile canvas fields but keeps real edits", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const graph = {
      extra: { ds: { scale: 0.5, offset: [20, 40] } },
      groups: [{ title: "decor", bounding: [1, 2, 3, 4] }],
      nodes: [
        {
          id: 1,
          type: "Input",
          pos: [100, 200],
          size: [300, 80],
          flags: { collapsed: true },
          order: 4,
          properties: { prompt: "volatile property" },
          widgets_values: ["a prompt", { videopreview: { frame: 12 }, keep: "value" }],
          inputs: [{ name: "seed", link: null }],
          outputs: [{ name: "IMAGE", links: [9] }],
        },
        {
          id: 2,
          type: "SaveImage",
          pos: [300, 200],
          widgets_values: ["prefix"],
          inputs: [{ name: "images", link: 9 }],
          outputs: [],
        },
      ],
      links: [[9, 1, 0, 2, 0, "IMAGE"]],
    };
    const volatileDrift = {
      ...graph,
      extra: { ds: { scale: 2.0, offset: [400, 100] } },
      groups: [{ title: "decor", bounding: [9, 8, 7, 6] }],
      nodes: [
        {
          ...graph.nodes[0],
          pos: [999, 888],
          size: [10, 20],
          flags: {},
          order: 1,
          properties: { prompt: "changed volatile property" },
          widgets_values: ["a prompt", { videopreview: { frame: 99 }, keep: "value" }],
        },
        { ...graph.nodes[1], pos: [111, 222] },
      ],
    };
    const widgetChanged = {
      ...volatileDrift,
      nodes: [
        { ...volatileDrift.nodes[0], widgets_values: ["different prompt", { keep: "value" }] },
        volatileDrift.nodes[1],
      ],
    };
    const rewired = {
      ...volatileDrift,
      nodes: [
        volatileDrift.nodes[0],
        { ...volatileDrift.nodes[1], inputs: [{ name: "images", link: null }] },
      ],
      links: [],
    };

    const project = extensionModule.buildStructuralGraphProjection;
    assert.deepEqual(project(graph), project(volatileDrift));
    assert.notDeepEqual(project(graph), project(widgetChanged));
    assert.notDeepEqual(project(graph), project(rewired));
  } finally {
    await harness.dispose();
  }
});

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

test("VibeComfy beforeRegisterNodeDef decorates intent node prototypes and degrades safely on malformed metadata", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    await harness.loadExtension();
    const extension = harness.getExtension();
    assert.equal(typeof extension.beforeRegisterNodeDef, "function");

    const nodeType = { prototype: {} };
    await extension.beforeRegisterNodeDef(nodeType, { name: "vibecomfy.code" });

    const intentNode = {
      type: "vibecomfy.code",
      size: [240, 90],
      properties: {
        vibecomfy_uid: "intent-1",
        vibecomfy: {
          kind: "code",
          intent: {
            source: "value = image",
            spec: "inspect image value",
          },
          io: {
            inputs: [["image", "IMAGE"]],
            outputs: [["preview", "IMAGE"]],
          },
        },
      },
      inputs: [{ name: "value" }],
      outputs: [{ name: "value" }],
    };

    nodeType.prototype.onNodeCreated.call(intentNode);
    assert.equal(intentNode.color, "#2d2643");
    assert.equal(intentNode.bgcolor, "#171229");
    assert.equal(intentNode.boxcolor, "#e39cff");
    assert.equal(intentNode.properties["VibeComfy Intent Badge"], "code · editor-only");
    assert.equal(intentNode.properties["VibeComfy Intent Source"], "value = image");
    assert.equal(intentNode.properties["VibeComfy Intent Spec"], "inspect image value");
    assert.equal(intentNode.inputs[0].name, "image: IMAGE");
    assert.equal(intentNode.outputs[0].name, "preview: IMAGE");

    const drawOps = [];
    const ctx = {
      save() {},
      restore() {},
      fillRect(...args) {
        drawOps.push(["rect", ...args]);
      },
      fillText(text, ...args) {
        drawOps.push(["text", text, ...args]);
      },
    };
    nodeType.prototype.onDrawForeground.call(intentNode, ctx);
    assert(drawOps.some((entry) => entry[0] === "text" && entry[1] === "code · editor-only"));

    const degradedNode = {
      type: "vibecomfy.code",
      size: [240, 90],
      properties: {},
      inputs: [{ name: "value" }],
      outputs: [{ name: "value" }],
    };
    nodeType.prototype.onNodeCreated.call(degradedNode);
    assert.equal(degradedNode.properties["VibeComfy Intent Badge"], "code · metadata missing");
    assert.equal(degradedNode.boxcolor, "#ffb86c");
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
    const extensionModule = await harness.loadExtension();
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
    assert.equal(
      payload.client_structural_graph_hash,
      sha256HexUtf8(extensionModule.buildStructuralGraphProjection(graph)),
    );
    assert.equal(payload.client_live_canvas_token, "live:rev:1");
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

test("VibeComfy blocks stale response arrivals before review and leaves candidate state untouched", async () => {
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const changedGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 3, type: "SaveImage", properties: { vibecomfy_uid: "uid-3" } },
    ],
    links: [[1, 1, 0, 3, 0, "IMAGE"]],
  };
  let releaseResponse;
  const pendingResponse = new Promise((resolve) => {
    releaseResponse = resolve;
  });

  const harness = await createBrowserHarness({
    graph: initialGraph,
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
            session_id: "session-stale-arrival",
            turn_id: "0001",
            baseline_turn_id: null,
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: false,
            message: "Candidate should be blocked before review.",
            graph: { nodes: [{ id: 9, type: "PreviewImage", properties: { vibecomfy_uid: "uid-9" } }], links: [] },
            report: { change: { content_edits: { preserved: ["uid-1"], edited: ["uid-9"], removed_named: [] } }, recovery: [] },
            audit_ref: { path: "/tmp/stale-arrival-audit.json" },
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

  let submitPromise;
  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "tighten the graph";
    submitPromise = harness.clickButton("Submit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent-edit"));

    harness.setCurrentGraph(changedGraph);
    releaseResponse();
    await submitPromise;

    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "ERROR");
    assert.match(harness.textDump(), /StaleResponseArrival/);
    assert.match(harness.textDump(), /Submit a new edit from the current canvas\./);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 0);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.getCurrentGraph().nodes[1]?.id, 3);
    assert.doesNotMatch(harness.textDump(), /AWAITING_REVIEW/);
  } finally {
    releaseResponse?.();
    await Promise.allSettled([submitPromise].filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy renders a clarify turn as a question, not a no-op candidate", async () => {
  const initialGraph = {
    nodes: [{ id: 1, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const clarifyQuestion = "Please provide the current graph nodes or specify which existing nodes to replace with SD3 equivalents.";
  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent-edit": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-clarify",
          turn_id: "0001",
          baseline_turn_id: null,
          // The backend honestly reports: no edits landed, graph unchanged,
          // nothing applyable, and a clarification question.
          clarification_required: true,
          graph_unchanged: true,
          canvas_apply_allowed: false,
          apply_allowed: false,
          queue_allowed: false,
          message: clarifyQuestion,
          // The backend still echoes the (unchanged) graph in the envelope; the
          // frontend must NOT treat that as a candidate to apply.
          graph: { nodes: [{ id: 1, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "uid-1" } }], links: [] },
          report: { clarification_required: true },
          audit_ref: { path: "/tmp/clarify-audit.json" },
        },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  let submitPromise;
  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "USe SD3 instead";
    submitPromise = harness.clickButton("Submit");
    await submitPromise;

    // Status banner reflects a clarify turn, NOT a candidate review.
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "NEEDS YOUR INPUT");
    assert.doesNotMatch(harness.textDump(), /AWAITING_REVIEW/);
    // The clarification question is surfaced to the user.
    assert.match(harness.textDump(), /replace with SD3 equivalents/);
    // No candidate exists, so Apply/Reject must stay disabled (the original no-op bug
    // was an enabled-looking "Apply Candidate" over a byte-identical graph).
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);
    // The prompt stays open for the answer (Submit re-enabled), and no graph was mutated.
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled, false);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 0);
  } finally {
    await Promise.allSettled([submitPromise].filter(Boolean));
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
          queue_blockers: [
            {
              code: "intent_node_queue_blocker",
              severity: "error",
              message: "Backend says the code intent must be lowered before Queue.",
              detail: {
                node_id: "88",
                class_type: "vibecomfy.code",
                kind: "code",
                uid: "intent-backend",
                diagnostic: "backend owns this queue blocker payload",
              },
            },
          ],
          recovery: [
            {
              node_id: "88",
              class_type: "vibecomfy.code",
              kind: "code",
              uid: "intent-recovery",
              diagnostic: "recovery should not replace backend issue text",
            },
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
    assert.match(successText, /intent_node_queue_blocker: Backend says the code intent must be lowered before Queue\./);
    assert.match(successText, /backend owns this queue blocker payload/);
    assert.doesNotMatch(successText, /Node 88 \(vibecomfy\.code\) is an editor-only intent node/);
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

test("VibeComfy Apply requires explicit canvas allowance, rechecks canvas hash, accepts the turn before in-place configure, and blocks failed accepts", async () => {
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
  const initialGraphHash = sha256HexUtf8(initialGraph);
  const candidateGraphHash = sha256HexUtf8(candidateGraph);
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
        submit_graph_hash: initialGraphHash,
        candidate_graph_hash: candidateGraphHash,
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
        baseline_graph_hash: "baseline-after-apply",
        baseline_graph_hash_kind: "structural",
        baseline_graph_hash_version: 2,
        baseline_source: "turn",
        baseline_rebaseline_id: null,
        baseline_graph_source_path: "turns/0002/candidate.ui.json",
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
  const rebaselineBodies = [];
  const rebaselineResponses = [
    {
      status: 200,
      body: {
        ok: true,
        action: "rebaseline",
        session_id: "session-apply",
        baseline_turn_id: null,
        baseline_graph_hash: "baseline-after-undo",
        baseline_graph_hash_kind: "structural",
        baseline_graph_hash_version: 2,
        baseline_source: "rebaseline",
        baseline_rebaseline_id: "undo-0001",
        baseline_graph_source_path: "_rebaseline/undo-0001/graph.ui.json",
        rebaseline_id: "undo-0001",
        apply_allowed: false,
        canvas_apply_allowed: false,
        queue_allowed: false,
        apply_eligibility: {
          applyable: false,
          reason: "no_candidate",
          message: "No candidate is available to apply.",
          warnings: [],
        },
        audit_ref: { path: "/tmp/rebaseline-undo-audit.json" },
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
        assert.equal(body.client_graph_hash, initialGraphHash);
        if (body.turn_id === "0002") {
          assert.equal(body.client_live_canvas_token, "live:rev:1");
        } else {
          assert.match(body.client_live_canvas_token, /^live:rev:\d+$/);
        }
        assert.equal(body.submit_graph_hash, body.turn_id === "0002" ? initialGraphHash : undefined);
        assert.equal(body.candidate_graph_hash, candidateGraphHash);
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
      "/vibecomfy/agent-edit/rebaseline": async ({ options }) => {
        const body = JSON.parse(options.body);
        rebaselineBodies.push(body);
        assert.equal(body.session_id, "session-apply");
        assert.equal(body.reason, "undo");
        assert.equal(body.last_known_baseline_graph_hash, "baseline-after-apply");
        assert.equal(body.client_graph_hash, initialGraphHash);
        assert.match(body.idempotency_key, /^rebaseline:session-apply:undo:baseline-aft:[0-9a-f]{12}$/);
        return rebaselineResponses.shift();
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
    assert.equal(harness.graphConfigureCalls.length, 0);

    await harness.clickButton("Reject Candidate");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/reject").length, 1);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), initialGraph);
    assert.match(harness.textDump(), /rejected/);
    assert.match(harness.textDump(), /\/tmp\/reject-audit\.json/);

    prompt.value = "allowed";
    await harness.clickButton("Submit");
    assert.equal(applyButton.disabled, false);
    // The always-on candidate preview overlay must be cleared from the canvas
    // whenever a candidate is invalidated (the earlier reject + this re-submit),
    // which legitimately repaints via invalidateCandidateState -> setDirtyCanvas.
    // Those repaints are not what the redraw-count assertion below checks. Scope
    // the dirty/draw assertion to the Apply action itself so it still proves
    // "in-place configure triggers exactly one [true,true] repaint" while
    // tolerating the legitimate overlay-clearing repaints from invalidation.
    harness.graphDirtyCanvasCalls.length = 0;
    harness.canvasDrawCalls.length = 0;
    const operationCountBeforeApply = harness.operationLog.length;
    const applyPromise = harness.clickButton("Apply Candidate");
    await applyPromise;
    const acceptIndex = harness.requests.findIndex((entry) => entry.url === "/vibecomfy/agent-edit/accept");
    assert.notEqual(acceptIndex, -1);
    const applyEvents = harness.operationLog.slice(operationCountBeforeApply);
    const acceptResponseIndex = applyEvents.findIndex((entry) => entry.kind === "response" && entry.url === "/vibecomfy/agent-edit/accept" && entry.status === 200);
    const clearIndex = applyEvents.findIndex((entry) => entry.kind === "graph.clear");
    const configureIndex = applyEvents.findIndex((entry) => entry.kind === "graph.configure");
    const loadIndex = applyEvents.findIndex((entry) => entry.kind === "loadGraphData");
    assert.notEqual(acceptResponseIndex, -1);
    assert.notEqual(clearIndex, -1);
    assert.notEqual(configureIndex, -1);
    assert.equal(loadIndex, -1);
    assert(acceptResponseIndex < clearIndex, "accept response should be recorded before graph.clear()");
    assert(clearIndex < configureIndex, "graph.clear() should run before graph.configure()");
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphClearCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    assert.deepEqual(harness.graphConfigureCalls[0], candidateGraph);
    assert.equal(harness.graphChangeCalls.length, 1);
    assert.deepEqual(harness.graphDirtyCanvasCalls, [[true, true]]);
    assert.deepEqual(harness.canvasDrawCalls, [[true, true]]);
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
    assert.equal(harness.loadGraphDataCalls.length, 1);
    assert.deepEqual(harness.loadGraphDataCalls[0], initialGraph);
    assert.deepEqual(harness.getCurrentGraph(), initialGraph);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/rebaseline").length, 1);
    assert.equal(rebaselineBodies.length, 1);
    assert.match(harness.textDump(), /undone_turn_id/);
    assert.match(harness.textDump(), /"0002"/);
    assert.match(harness.textDump(), /undo_stack_depth/);
    assert.match(harness.textDump(), /rebaseline_response/);
    assert.equal(undoButton.disabled, true);

    const allowedQueueResult = harness.app.queuePrompt("prompt-2");
    assert.deepEqual(allowedQueueResult, { queued: true, args: ["prompt-2"] });
    assert.equal(harness.queuePromptCalls.length, 1);

    await harness.clickButton("Undo Last Apply");
    assert.equal(harness.loadGraphDataCalls.length, 1);

    harness.setCurrentGraph(initialGraph);
    prompt.value = "stale";
    await harness.clickButton("Submit");
    harness.setCurrentGraph({ nodes: [{ id: 99, type: "Dirty" }], links: [] });
    await harness.clickButton("Apply Candidate");
    assert.match(harness.textDump(), /StaleStateMismatch/);
    assert.match(harness.textDump(), /Submit a new edit from the current canvas\./);
    assert.match(harness.textDump(), /The canvas changed after this candidate was generated/);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.loadGraphDataCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);

    harness.setCurrentGraph(initialGraph);
    prompt.value = "accept fails";
    await harness.clickButton("Submit");
    await harness.clickButton("Apply Candidate");
    assert.match(harness.textDump(), /EditorAheadConflict/);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 2);
    assert.equal(harness.loadGraphDataCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy Apply allows nonstructural serialize drift when the live canvas revision is unchanged", async () => {
  const initialGraph = {
    extra: { ds: { scale: 1.0 } },
    nodes: [
      {
        id: 1,
        type: "VHS_VideoCombine",
        pos: [100, 200],
        flags: { collapsed: true },
        properties: { transient: "submit" },
        widgets_values: ["prefix", { videopreview: { frame: 1, url: "/view/a" }, keep: "same" }],
        inputs: [{ name: "images", link: null }],
        outputs: [{ name: "IMAGE", links: [] }],
      },
    ],
    links: [],
  };
  const driftedGraph = {
    extra: { ds: { scale: 1.5, offset: [20, 30] } },
    nodes: [
      {
        ...initialGraph.nodes[0],
        pos: [999, 888],
        flags: {},
        properties: { transient: "apply" },
        widgets_values: ["prefix", { videopreview: { frame: 99, url: "/view/b" }, keep: "same" }],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [{ id: 2, type: "SaveImage", widgets_values: ["after"], inputs: [], outputs: [] }],
    links: [],
  };
  const initialGraphHash = sha256HexUtf8(initialGraph);
  assert.notEqual(sha256HexUtf8(driftedGraph), initialGraphHash);

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
          },
        },
      },
      "/vibecomfy/agent-edit": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-apply-drift",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          message: "Allowed candidate.",
          graph: candidateGraph,
          submit_graph_hash: initialGraphHash,
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
          report: { change: { content_edits: { preserved: [], edited: ["2"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.equal(body.session_id, "session-apply-drift");
        assert.equal(body.turn_id, "0001");
        assert.equal(body.client_graph_hash, initialGraphHash);
        assert.equal(body.client_live_canvas_token, "live:rev:1");
        assert.equal(body.submit_graph_hash, initialGraphHash);
        assert.equal(body.candidate_graph_hash, sha256HexUtf8(candidateGraph));
        return {
          status: 200,
          body: {
            ok: true,
            action: "accept",
            session_id: "session-apply-drift",
            turn_id: "0001",
            baseline_turn_id: "0001",
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
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "remove the second pass";
    await harness.clickButton("Submit");

    harness.setCurrentGraphWithoutRevisionBump(driftedGraph);
    await harness.clickButton("Apply Candidate");

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    assert.deepEqual(harness.graphConfigureCalls[0], candidateGraph);
    assert.doesNotMatch(harness.textDump(), /StaleStateMismatch/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy Apply allows nonstructural drift even after the live canvas token changes", async () => {
  const initialGraph = {
    extra: { ds: { scale: 1.0 } },
    nodes: [
      {
        id: 1,
        type: "VHS_VideoCombine",
        pos: [100, 200],
        flags: { collapsed: true },
        properties: { transient: "submit" },
        widgets_values: ["prefix", { videopreview: { frame: 1, url: "/view/a" }, keep: "same" }],
        inputs: [{ name: "images", link: null }],
        outputs: [{ name: "IMAGE", links: [] }],
      },
    ],
    links: [],
  };
  const driftedGraph = {
    extra: { ds: { scale: 1.5, offset: [20, 30] } },
    nodes: [
      {
        ...initialGraph.nodes[0],
        pos: [999, 888],
        flags: {},
        properties: { transient: "apply" },
        widgets_values: ["prefix", { videopreview: { frame: 99, url: "/view/b" }, keep: "same" }],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [{ id: 2, type: "SaveImage", widgets_values: ["after"], inputs: [], outputs: [] }],
    links: [],
  };
  const initialGraphHash = sha256HexUtf8(initialGraph);

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
          },
        },
      },
      "/vibecomfy/agent-edit": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-apply-token-drift",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          message: "Allowed candidate.",
          graph: candidateGraph,
          submit_graph_hash: initialGraphHash,
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
          report: { change: { content_edits: { preserved: [], edited: ["2"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.equal(body.session_id, "session-apply-token-drift");
        assert.equal(body.turn_id, "0001");
        assert.equal(body.client_graph_hash, initialGraphHash);
        assert.equal(body.client_live_canvas_token, "live:rev:2");
        return {
          status: 200,
          body: {
            ok: true,
            action: "accept",
            session_id: "session-apply-token-drift",
            turn_id: "0001",
            baseline_turn_id: "0001",
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
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "remove the second pass";
    await harness.clickButton("Submit");

    harness.setCurrentGraph(driftedGraph);
    await harness.clickButton("Apply Candidate");

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    assert.deepEqual(harness.graphConfigureCalls[0], candidateGraph);
    assert.doesNotMatch(harness.textDump(), /StaleStateMismatch/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy Apply blocks structural drift even when the live canvas revision is unchanged", async () => {
  const initialGraph = {
    nodes: [
      {
        id: 1,
        type: "KSampler",
        widgets_values: [11, 20, 7.5, "euler"],
        inputs: [],
        outputs: [],
      },
    ],
    links: [],
  };
  const structurallyChangedGraph = {
    nodes: [
      {
        ...initialGraph.nodes[0],
        widgets_values: [99, 20, 7.5, "euler"],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [{ id: 2, type: "SaveImage", widgets_values: ["after"], inputs: [], outputs: [] }],
    links: [],
  };
  const initialGraphHash = sha256HexUtf8(initialGraph);

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
          },
        },
      },
      "/vibecomfy/agent-edit": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-apply-structural-drift",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          message: "Allowed candidate.",
          graph: candidateGraph,
          submit_graph_hash: initialGraphHash,
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
          report: { change: { content_edits: { preserved: [], edited: ["2"], removed_named: [] } }, recovery: [] },
        },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "change the sampler";
    await harness.clickButton("Submit");

    harness.setCurrentGraphWithoutRevisionBump(structurallyChangedGraph);
    await harness.clickButton("Apply Candidate");

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.match(harness.textDump(), /StaleStateMismatch/);
    assert.match(harness.textDump(), /expected_structural_graph_hash/);
    assert.match(harness.textDump(), /The canvas changed after this candidate was generated/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy v2 Apply blocks if the live canvas token changes after backend accept but before configure", async () => {
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
  const initialGraphHash = sha256HexUtf8(initialGraph);
  const candidateGraphHash = sha256HexUtf8(candidateGraph);
  let harness;
  harness = await createBrowserHarness({
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
          },
        },
      },
      "/vibecomfy/agent-edit": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-live-token",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          graph: candidateGraph,
          submit_graph_hash: initialGraphHash,
          candidate_graph_hash: candidateGraphHash,
          report: { change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.equal(body.submit_graph_hash, initialGraphHash);
        assert.equal(body.candidate_graph_hash, candidateGraphHash);
        assert.equal(body.client_live_canvas_token, "live:rev:1");
        harness.bumpLiveCanvasToken();
        return {
          status: 200,
          body: {
            ok: true,
            action: "accept",
            session_id: "session-live-token",
            turn_id: "0001",
            baseline_turn_id: "0001",
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
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "token race";

    await harness.clickButton("Submit");
    await harness.clickButton("Apply Candidate");

    assert.match(harness.textDump(), /canvas changed while Apply was waiting for backend acceptance/i);
    assert.match(harness.textDump(), /expected_live_canvas_token/);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), initialGraph);
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
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.deepEqual(harness.graphConfigureCalls[0], candidateGraph);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy in-place apply decorates intent nodes with persistent styling, typed labels, and read-only previews", async () => {
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      {
        id: 2,
        type: "vibecomfy.code",
        properties: {
          vibecomfy_uid: "intent-code-1",
          vibecomfy: {
            kind: "code",
            intent: {
              source: "value = image",
              spec: "inspect the input image before lowering",
            },
            io: {
              inputs: [["image", "IMAGE"]],
              outputs: [["image", "IMAGE"]],
            },
          },
        },
        inputs: [{ name: "value" }],
        outputs: [{ name: "value" }],
      },
      {
        id: 3,
        type: "vibecomfy.loop",
        properties: {
          vibecomfy_uid: "intent-loop-1",
        },
        inputs: [{ name: "value" }],
        outputs: [{ name: "value" }],
      },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };

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
      "/vibecomfy/agent-edit": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-intent-style",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          message: "Styled intent candidate.",
          graph: candidateGraph,
          report: { change: { content_edits: { preserved: ["uid-1"], edited: [], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: "session-intent-style",
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

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "style the intent nodes";
    await harness.clickButton("Submit");
    await harness.clickButton("Apply Candidate");

    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphClearCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    const loadedIntentNodes = harness.graphConfigureCalls[0].nodes.filter((node) => /^vibecomfy\./.test(node.type));
    assert.equal(loadedIntentNodes.length, 2);

    const codeNode = loadedIntentNodes.find((node) => node.type === "vibecomfy.code");
    assert.equal(codeNode.color, "#2d2643");
    assert.equal(codeNode.bgcolor, "#171229");
    assert.equal(codeNode.boxcolor, "#e39cff");
    assert.equal(codeNode.properties["VibeComfy Intent Badge"], "code · editor-only");
    assert.equal(codeNode.properties["VibeComfy Intent Source"], "value = image");
    assert.equal(codeNode.properties["VibeComfy Intent Spec"], "inspect the input image before lowering");
    assert.equal(codeNode.inputs[0].name, "image: IMAGE");
    assert.equal(codeNode.outputs[0].name, "image: IMAGE");

    const degradedNode = loadedIntentNodes.find((node) => node.type === "vibecomfy.loop");
    assert.equal(degradedNode.properties["VibeComfy Intent Badge"], "loop · metadata missing");
    assert.equal(degradedNode.color, "#3a2a1f");
    assert.equal(degradedNode.bgcolor, "#231811");
    assert.equal(degradedNode.boxcolor, "#ffb86c");

    const liveIntentNodes = harness.app.canvas.graph._nodes.filter((node) => /^vibecomfy\./.test(node.type));
    assert.equal(liveIntentNodes.length, 2);
    const liveCodeNode = liveIntentNodes.find((node) => node.type === "vibecomfy.code");
    assert.equal(liveCodeNode.boxcolor, "#e39cff");
    assert.equal(liveCodeNode.properties["VibeComfy Intent Badge"], "code · editor-only");
    assert.equal(liveCodeNode.inputs[0].name, "image: IMAGE");
    assert.equal(liveCodeNode.outputs[0].name, "image: IMAGE");

    const liveDegradedNode = liveIntentNodes.find((node) => node.type === "vibecomfy.loop");
    assert.equal(liveDegradedNode.boxcolor, "#ffb86c");
    assert.equal(liveDegradedNode.properties["VibeComfy Intent Badge"], "loop · metadata missing");

    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "IDLE");
    assert.deepEqual(harness.consoleCapture.error, []);
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
    assert.equal(harness.graphConfigureCalls.length, 0);

    await harness.clickButton("Apply Candidate");
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphClearCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    assert.deepEqual(harness.graphConfigureCalls[0], candidateGraph);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy syncs authoritative baseline state from responses and blocks Submit while rebaseline is pending or in flight", async () => {
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const rebaselineBodies = [];
  let rebaselineCallCount = 0;
  let releaseFirstRebaseline = null;

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
      "/vibecomfy/agent-edit/rebaseline": async ({ options }) => {
        rebaselineCallCount += 1;
        rebaselineBodies.push(JSON.parse(options.body));
        if (rebaselineCallCount === 1) {
          return await new Promise((resolve) => {
            releaseFirstRebaseline = () => resolve({
              status: 409,
              body: {
                ok: false,
                kind: "StaleStateMismatch",
                retryable: true,
                graph_unchanged: true,
                next_action: "Retry the rebaseline request.",
                session_id: "session-rebaseline",
                baseline_turn_id: "0004",
                baseline_graph_hash: "baseline-before",
                baseline_graph_hash_kind: "structural",
                baseline_graph_hash_version: 2,
                baseline_source: "turn",
              },
            });
          });
        }
        return {
          status: 200,
          body: {
            ok: true,
            action: "rebaseline",
            session_id: "session-rebaseline",
            baseline_turn_id: null,
            baseline_graph_hash: "baseline-after",
            baseline_graph_hash_kind: "structural",
            baseline_graph_hash_version: 2,
            baseline_source: "rebaseline",
            baseline_rebaseline_id: "0001",
            baseline_graph_source_path: "_rebaseline/0001/graph.ui.json",
            rebaseline_id: "0001",
            apply_allowed: false,
            canvas_apply_allowed: false,
            queue_allowed: false,
            apply_eligibility: {
              applyable: false,
              reason: "no_candidate",
              message: "No candidate is available to apply.",
              warnings: [],
            },
            audit_ref: { path: "/tmp/rebaseline-success.json" },
          },
        };
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const panel = extensionModule.ensureAgentPanel();
    panel.state.sessionId = "session-rebaseline";
    extensionModule.syncBaselineFromResponse(panel, {
      baseline_turn_id: "0004",
      baseline_graph_hash: "baseline-before",
      baseline_graph_hash_kind: "structural",
      baseline_graph_hash_version: 2,
      baseline_source: "turn",
      baseline_rebaseline_id: null,
      baseline_graph_source_path: "turns/0004/candidate.ui.json",
    });

    panel.state.rebaselinePending = { reason: "undo" };
    extensionModule.renderAgentPanel(panel);

    const submitButton = harness.document.getElementById("vibecomfy-agent-panel-submit");
    const undoButton = harness.document.getElementById("vibecomfy-agent-panel-undo");
    assert.equal(submitButton.disabled, true);

    const firstAttempt = extensionModule.postAgentRebaseline(panel, { reason: "undo" });
    await waitFor(() => rebaselineBodies.length === 1);
    assert.equal(submitButton.disabled, true);
    assert.equal(undoButton.disabled, true);
    assert.equal(undoButton.textContent, "Undo Rebaseline...");
    assert.equal(panel.state.inFlightRebaseline instanceof Promise, true);
    assert.equal(rebaselineBodies[0].last_known_baseline_graph_hash, "baseline-before");
    assert.equal(panel.state.rebaselinePending?.reason, "undo");

    releaseFirstRebaseline();

    let firstFailure = null;
    try {
      await firstAttempt;
    } catch (error) {
      firstFailure = error;
    }
    assert.equal(firstFailure?.kind, "StaleStateMismatch");
    assert.equal(submitButton.disabled, true);
    assert.equal(panel.state.baselineGraphHash, "baseline-before");
    assert.equal(panel.state.rebaselinePending?.reason, "undo");
    assert.equal(panel.state.rebaselinePending?.retryable, true);

    const secondResult = await extensionModule.postAgentRebaseline(panel, { reason: "undo" });
    assert.equal(secondResult.rebaseline_id, "0001");
    assert.equal(rebaselineBodies[1].idempotency_key, rebaselineBodies[0].idempotency_key);
    assert.equal(panel.state.baselineTurnId, null);
    assert.equal(panel.state.baselineGraphHash, "baseline-after");
    assert.equal(panel.state.baselineGraphHashKind, "structural");
    assert.equal(panel.state.baselineGraphHashVersion, 2);
    assert.equal(panel.state.baselineSource, "rebaseline");
    assert.equal(panel.state.baselineRebaselineId, "0001");
    assert.equal(panel.state.baselineGraphSourcePath, "_rebaseline/0001/graph.ui.json");
    assert.equal(panel.state.rebaselinePending, null);
    assert.equal(panel.state.inFlightRebaseline, null);
    assert.equal(submitButton.disabled, false);
    assert.equal(undoButton.disabled, true);
    assert.equal(undoButton.textContent, "Undo Last Apply");
    assert.doesNotMatch(harness.textDump(), /rebaseline pending: undo/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy renders one stale-state recovery action, retries against updated evidence, and recovers through rebaseline resubmit and apply", async () => {
  const rebaselineBodies = [];
  const acceptBodies = [];
  let rebaselineCallCount = 0;
  const recoveryButtonsFor = (panel) => panel.sections.failure.querySelectorAll(
    (node) => node.tagName === "BUTTON" && node.textContent === "Rebaseline Current Canvas",
  );
  const harness = await createBrowserHarness({
    graph: {
      nodes: [
        { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-recover-1", prompt: "recover me" } },
      ],
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
          },
        },
      },
      "/vibecomfy/agent-edit": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-stale",
          turn_id: "0006",
          baseline_turn_id: null,
          baseline_graph_hash: "baseline-after-recovery",
          baseline_graph_hash_kind: "structural",
          baseline_graph_hash_version: 2,
          baseline_source: "rebaseline",
          baseline_rebaseline_id: "recovery-0001",
          baseline_graph_source_path: "_rebaseline/recovery-0001/graph.ui.json",
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
          message: "Recovered candidate ready to apply.",
          submit_graph_hash: "submit-after-recovery",
          candidate_graph_hash: "candidate-after-recovery",
          graph: {
            nodes: [
              { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-recover-1", prompt: "recover me again" } },
              { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-recover-2" } },
            ],
            links: [[1, 1, 0, 2, 0, "IMAGE"]],
          },
          report: {
            change: { content_edits: { preserved: ["uid-recover-1"], edited: ["uid-recover-2"], removed_named: [] } },
            recovery: [],
          },
        },
      },
      "/vibecomfy/agent-edit/accept": async ({ options }) => {
        const body = JSON.parse(options.body);
        acceptBodies.push(body);
        return {
          status: 200,
          body: {
            ok: true,
            action: "accept",
            session_id: "session-stale",
            turn_id: "0006",
            baseline_turn_id: "0006",
            baseline_graph_hash: "baseline-after-apply",
            baseline_graph_hash_kind: "structural",
            baseline_graph_hash_version: 2,
            baseline_source: "turn",
            baseline_rebaseline_id: null,
            baseline_graph_source_path: "turns/0006/candidate.ui.json",
            apply_allowed: false,
            canvas_apply_allowed: false,
            queue_allowed: false,
            apply_eligibility: {
              applyable: false,
              reason: "superseded",
              message: "This candidate has been superseded.",
              warnings: [],
            },
          },
        };
      },
      "/vibecomfy/agent-edit/rebaseline": async ({ options }) => {
        rebaselineCallCount += 1;
        const body = JSON.parse(options.body);
        rebaselineBodies.push(body);
        if (rebaselineCallCount === 1) {
          return {
            status: 409,
            body: {
              ok: false,
              kind: "StaleStateMismatch",
              stage: "rebaseline",
              retryable: true,
              graph_unchanged: true,
              user_facing_message: "Baseline moved again before the rebaseline landed.",
              next_action: "Retry the recovery action against the new baseline.",
              session_id: "session-stale",
              baseline_turn_id: null,
              rebaseline_recovery: {
                action: "rebaseline",
                endpoint: "/vibecomfy/agent-edit/rebaseline",
                reason: "stale_state_recovery",
                last_known_baseline_graph_hash: "baseline-retry",
                submit_graph_hash: "submit-retry",
                submit_structural_graph_hash: "submit-structural-retry",
                client_graph_hash: body.client_graph_hash,
                client_structural_graph_hash: body.client_structural_graph_hash,
              },
              agent_failure_context: {
                issues: [
                  {
                    code: "stale_state_mismatch",
                    severity: "error",
                    detail: {
                      expected_structural_graph_hash: "baseline-retry",
                      actual_structural_graph_hash: "baseline-old",
                    },
                  },
                ],
              },
            },
          };
        }
        return {
          status: 200,
          body: {
            ok: true,
            action: "rebaseline",
            session_id: "session-stale",
            baseline_turn_id: null,
            baseline_graph_hash: "baseline-after-recovery",
            baseline_graph_hash_kind: "structural",
            baseline_graph_hash_version: 2,
            baseline_source: "rebaseline",
            baseline_rebaseline_id: "recovery-0001",
            baseline_graph_source_path: "_rebaseline/recovery-0001/graph.ui.json",
            rebaseline_id: "recovery-0001",
            apply_allowed: false,
            canvas_apply_allowed: false,
            queue_allowed: false,
            apply_eligibility: {
              applyable: false,
              reason: "no_candidate",
              message: "No candidate is available to apply.",
              warnings: [],
            },
            audit_ref: { path: "/tmp/rebaseline-recovery-success.json" },
          },
        };
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const panel = extensionModule.ensureAgentPanel();
    panel.state.sessionId = "session-stale";
    panel.state.turnId = "0005";
    panel.state.candidateGraph = { nodes: [{ id: 9, type: "Candidate" }], links: [] };
    const initialFailure = {
      ok: false,
      kind: "StaleStateMismatch",
      stage: "ingest",
      retryable: true,
      graph_unchanged: true,
      user_facing_message: "Submitted graph no longer matches the current baseline.",
      next_action: "Rebaseline the current canvas or resubmit.",
      session_id: "session-stale",
      turn_id: "0005",
      baseline_turn_id: null,
      agent_failure_context: {
        issues: [
          {
            code: "stale_state_mismatch",
            severity: "error",
            rebaseline_recovery: {
              action: "rebaseline",
              endpoint: "/vibecomfy/agent-edit/rebaseline",
              reason: "stale_state_recovery",
              last_known_baseline_graph_hash: "baseline-before-recovery",
              submit_graph_hash: "submit-before-recovery",
              submit_structural_graph_hash: "submit-structural-before-recovery",
              client_graph_hash: "client-before-recovery",
              client_structural_graph_hash: "client-structural-before-recovery",
            },
          },
        ],
      },
    };
    panel.state.failure = initialFailure;
    extensionModule.syncBaselineFromResponse(panel, initialFailure);
    assert.equal(panel.state.rebaselineRecovery?.last_known_baseline_graph_hash, "baseline-before-recovery");
    extensionModule.renderAgentPanel(panel);

    let recoveryButtons = recoveryButtonsFor(panel);
    assert.equal(recoveryButtons.length, 1);

    recoveryButtons[0].click();
    await waitFor(() => rebaselineBodies.length === 1);
    await waitFor(() => panel.state.rebaselineRecovery?.last_known_baseline_graph_hash === "baseline-retry");
    assert.equal(rebaselineBodies[0].reason, "stale_state_recovery");
    assert.equal(rebaselineBodies[0].last_known_baseline_graph_hash, "baseline-before-recovery");
    assert.equal(panel.state.failure?.kind, "StaleStateMismatch");
    assert.equal(panel.state.rebaselineRecovery?.last_known_baseline_graph_hash, "baseline-retry");
    recoveryButtons = recoveryButtonsFor(panel);
    assert.equal(recoveryButtons.length, 1);

    recoveryButtons[0].click();
    await waitFor(() => rebaselineBodies.length === 2);
    await waitFor(() => panel.state.failure === null);
    assert.equal(rebaselineBodies[1].last_known_baseline_graph_hash, "baseline-retry");
    assert.equal(panel.state.failure, null);
    assert.equal(panel.state.candidateGraph, null);
    assert.equal(panel.state.rebaselineRecovery, null);
    assert.equal(panel.state.baselineGraphHash, "baseline-after-recovery");
    assert.equal(panel.state.baselineSource, "rebaseline");
    assert.equal(panel.state.baselineGraphSourcePath, "_rebaseline/recovery-0001/graph.ui.json");
    assert.equal(panel.state.message, "Current canvas rebaselined. Submit again from this canvas.");
    assert.equal(recoveryButtonsFor(panel).length, 0);

    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    prompt.value = "finish the recovered edit";
    await harness.clickButton("Submit");
    assert.equal(panel.state.turnId, "0006");
    assert.equal(panel.state.candidateGraphHash, "candidate-after-recovery");
    assert.match(harness.textDump(), /Apply is allowed, but Queue remains blocked for this candidate\./);

    await harness.clickButton("Apply Candidate");
    assert.equal(acceptBodies.length, 1);
    assert.equal(acceptBodies[0].session_id, "session-stale");
    assert.equal(acceptBodies[0].turn_id, "0006");
    assert.equal(panel.state.baselineTurnId, "0006");
    assert.equal(panel.state.baselineGraphHash, "baseline-after-apply");
    assert.equal(panel.state.baselineSource, "turn");
    assert.equal(panel.state.baselineRebaselineId, null);
    assert.equal(panel.state.baselineGraphSourcePath, "turns/0006/candidate.ui.json");
    assert.equal(panel.state.candidateGraph, null);
    assert.equal(harness.graphConfigureCalls.length, 1);
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
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 1);

    // ── Turn 2: submit, get failure ──
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "turn 2 task";
    await harness.clickButton("Submit");

    const afterFailureText = harness.textDump();
    assert.match(afterFailureText, /ValidationError/);
    assert.match(afterFailureText, /failed/i);
    assert.match(afterFailureText, /turn 0002/);
    assert.match(afterFailureText, /\/tmp\/audit-turn-0002\.json/);
    // Canvas should not have been mutated on failure
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 1);

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

test("VibeComfy agent turn websocket listener ignores closed or foreign sessions and reconciles authoritative batch_turns from the submit response", async () => {
  let resolveSubmit;
  const submitBodies = [];
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
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
      "/vibecomfy/agent-edit": async ({ options }) => {
        submitBodies.push(JSON.parse(options.body));
        return new Promise((resolve) => {
          resolveSubmit = resolve;
        });
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    assert.equal(harness.apiEventListeners["vibecomfy.agent_edit.turn"]?.length || 0, 1);

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "closed-session",
      turn_number: 0,
      status: "in_progress",
      message: "ignored while closed",
    });

    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    assert.doesNotMatch(harness.textDump(), /ignored while closed/);

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "live batch turn";
    const submitPromise = harness.clickButton("Submit");
    await waitFor(() => typeof resolveSubmit === "function");

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "other-session",
      turn_number: 0,
      status: "in_progress",
      message: "foreign session turn",
    });
    assert.doesNotMatch(harness.textDump(), /foreign session turn/);

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "session-live",
      turn_number: 0,
      status: "in_progress",
      message: "ignored before session bind",
      statement_count: 1,
    });
    assert.doesNotMatch(harness.textDump(), /ignored before session bind/);

    resolveSubmit({
      status: 200,
      body: {
        ok: true,
        session_id: "session-live",
        turn_id: "0001",
        baseline_turn_id: null,
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        message: "Candidate after batch replay.",
        graph: candidateGraph,
        report: { change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } }, recovery: [] },
        done_summary: "Authoritative summary.",
        batch_turns: [
          {
            session_id: "session-live",
            turn_number: 0,
            message: "authoritative response step",
            statement_count: 2,
            batch_ok: true,
            statements: [{ op_kind: "assign", target: "saveimage.filename_prefix" }],
          },
          {
            session_id: "session-live",
            turn_number: 1,
            message: "authoritative done step",
            statement_count: 1,
            statements: [{ op_kind: "done" }],
          },
        ],
      },
    });
    await submitPromise;

    const text = harness.textDump();
    assert.equal(submitBodies[0].client_id, harness.api.clientId);
    assert.match(text, /Candidate after batch replay\./);
    assert.match(text, /authoritative response step/);
    assert.match(text, /authoritative done step/);
    assert.doesNotMatch(text, /ignored before session bind/);

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "session-live",
      turn_number: 2,
      status: "in_progress",
      message: "post-response websocket step",
      statement_count: 1,
    });
    await waitFor(() => /post-response websocket step/.test(harness.textDump()));

    const liveListener = harness.apiEventListeners["vibecomfy.agent_edit.turn"][0];
    liveListener({
      session_id: "session-live",
      turn_number: 3,
      status: "done",
      message: "direct payload step",
      statement_count: 1,
      done_summary: "temporary summary",
    });
    await waitFor(() => /direct payload step/.test(harness.textDump()));

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "wrong-after-bind",
      turn_number: 4,
      status: "done",
      message: "ignored after session bind",
    });
    assert.doesNotMatch(harness.textDump(), /ignored after session bind/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy lowered recovery entries are informational and do not block queue, while graph-scan fallback still blocks unlowered intent nodes", async () => {
  const loweredCandidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "KSampler", properties: { vibecomfy_uid: "uid-ks" } },
      { id: 3, type: "SaveImage", properties: { vibecomfy_uid: "uid-si" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };

  const harness = await createBrowserHarness({
    graph: {
      nodes: [
        { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
        { id: 99, type: "vibecomfy.loop", properties: { vibecomfy_uid: "loop-uid-1" } },
      ],
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
      "/vibecomfy/agent-edit": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-lowered",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Lowered candidate with informational recovery entries.",
          graph: loweredCandidateGraph,
          report: {
            change: {
              content_edits: {
                preserved: ["uid-1"],
                edited: [],
                new_auto_placed: ["uid-ks", "uid-si"],
                removed: ["loop-uid-1"],
                removed_named: [],
              },
              lowered: [
                {
                  node_id: "99",
                  class_type: "vibecomfy.loop",
                  kind: "loop",
                  uid: "loop-uid-1",
                  lowered: true,
                  lowered_native_count: 3,
                  source_node_uid: "loop-uid-1",
                },
              ],
            },
            recovery: [
              {
                node_id: "99",
                class_type: "vibecomfy.loop",
                kind: "loop",
                uid: "loop-uid-1",
                lowered: true,
                runtime_backed: false,
                provider: "static_lowering",
                confidence: 1.0,
                diagnostic: "statically lowered to 3 native node(s)",
                lowered_native_count: 3,
              },
            ],
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

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "lower a loop";
    await harness.clickButton("Submit");

    const text = harness.textDump();

    // lowered diff row appears with teal color
    assert.match(text, /lowered: loop-uid-1 -> 3 native node\(s\)/);

    // queue is allowed (lowered entry does not block)
    assert.match(text, /queue_allowed=true/);

    // no intent_node_queue_blocker from the lowered recovery entry
    assert.doesNotMatch(text, /Node 99 \(vibecomfy\.loop\) is an editor-only intent node/);

    // affected preview includes lowered count
    assert.match(text, /"lowered": 1/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy graph-scan fallback still blocks unlowered intent nodes like vibecomfy.code", async () => {
  const candidateGraphWithCodeIntent = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "vibecomfy.code", properties: { vibecomfy_uid: "code-uid-1" } },
      { id: 3, type: "SaveImage", properties: { vibecomfy_uid: "uid-si" } },
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
          session_id: "session-code-intent",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          message: "Candidate with unlowered code intent in graph.",
          graph: candidateGraphWithCodeIntent,
          report: {
            change: {
              content_edits: {
                preserved: ["uid-1"],
                edited: [],
                new_auto_placed: ["code-uid-1", "uid-si"],
                removed_named: [],
              },
              lowered: [],
            },
            recovery: [],
            graph: candidateGraphWithCodeIntent,
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

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "add a code intent";
    await harness.clickButton("Submit");

    const text = harness.textDump();

    // queue is blocked because vibecomfy.code is in the graph nodes (graph-scan fallback)
    assert.match(text, /queue_allowed=false/);

    // graph-scan fallback detects the unlowered intent node
    assert.match(text, /Node 2 \(vibecomfy\.code\) is an editor-only intent node/);
    assert.match(text, /intent_node_queue_blocker/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy agent-edit turn progress: client_id submit body, batch_turns fallback rendering, out-of-order live upsert with session filtering, expand/collapse diagnostics with landed count, no raw diff/source/audit paths in details, and Apply/Reject controls remain rendered and clickable after batch turns", async () => {
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };

  let resolveSubmit;
  const submitBodies = [];

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
      "/vibecomfy/agent-edit": async ({ options }) => {
        submitBodies.push(JSON.parse(options.body));
        return new Promise((resolve) => {
          resolveSubmit = resolve;
        });
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();

    // ── Part 1: client_id is sent in submit body ──────────────────────
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "batch turn progress";
    const submitPromise = harness.clickButton("Submit");
    await waitFor(() => typeof resolveSubmit === "function");

    assert.equal(submitBodies.length, 1);
    assert.equal(submitBodies[0].client_id, harness.api.clientId);
    assert(typeof submitBodies[0].client_id === "string" && submitBodies[0].client_id.length > 0);

    // ── Part 2: batch_turns fallback renders without any websocket events ──
    resolveSubmit({
      status: 200,
      body: {
        ok: true,
        session_id: "session-batch-fallback",
        turn_id: "0001",
        baseline_turn_id: null,
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        message: "Candidate with authoritative batch_turns fallback.",
        graph: candidateGraph,
        report: { change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } }, recovery: [] },
        done_summary: "Final reasoning summary for the batch REPL.",
        batch_turns: [
          {
            session_id: "session-batch-fallback",
            turn_number: 0,
            message: "analyzing the graph for editable nodes and connections",
            statement_count: 3,
            batch_ok: true,
            statements: [
              { op_kind: "assign", target: "saveimage.filename_prefix", landed: true, statement_index: 0 },
              { op_kind: "delete", target: "unused_node", landed: true, ok: true, statement_index: 1, diagnostics: [{ code: "STMT_DELETE_OK", message: "node removed cleanly" }] },
              { op_kind: "connect", target: "IMAGE link", landed: false, ok: false, statement_index: 2, diagnostics: [{ code: "WIRE_FAIL", message: "target slot occupied" }] },
            ],
            exit_mode: "step_continue",
            budget: { remaining_batches: 4, total_used: 1 },
          },
          {
            session_id: "session-batch-fallback",
            turn_number: 1,
            message: "finalizing edits and validating the graph",
            statement_count: 2,
            statements: [
              { op_kind: "validate", landed: true, statement_index: 0 },
              { op_kind: "done", landed: true, statement_index: 1, diagnostics: [{ code: "DONE", message: "batch completed successfully" }] },
            ],
            batch_ok: true,
            exit_mode: "done",
            budget: { remaining_batches: 3, total_used: 2 },
            diagnostics: [{ code: "BATCH_OK", message: "all turns succeeded" }],
          },
        ],
      },
    });
    await submitPromise;

    // Verify batch_turns rendered from the response without any websocket events
    let text = harness.textDump();
    assert.match(text, /Candidate with authoritative batch_turns fallback\./);
    assert.match(text, /analyzing the graph/);
    assert.match(text, /finalizing edits/);
    assert.match(text, /Turn 1/);
    assert.match(text, /Turn 2/);

    // Collapsed view shows truncated messages and status color
    const historyRegion = harness.document.getElementById("vibecomfy-agent-panel-region-history");
    const batchRows = historyRegion.querySelectorAll((node) => node.className === "vibecomfy-batch-row");
    assert.equal(batchRows.length, 2);

    // Status colors are set via borderLeft
    assert(batchRows[0].style.borderLeft && batchRows[0].style.borderLeft.includes("#"));
    assert(batchRows[1].style.borderLeft && batchRows[1].style.borderLeft.includes("#"));

    // ── Part 3: out-of-order websocket events and session filtering ──
    // Dispatch turn 3 out of order (before turn 2 via websocket)
    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "session-batch-fallback",
      turn_number: 3,
      status: "in_progress",
      message: "third turn running out of order",
      statement_count: 1,
    });
    await waitFor(() => /third turn running out of order/.test(harness.textDump()));

    // Now dispatch turn 2 (should upsert into position, newest first among batch rows)
    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "session-batch-fallback",
      turn_number: 2,
      status: "in_progress",
      message: "second turn arrives after third",
      statement_count: 2,
    });
    await waitFor(() => /second turn arrives after third/.test(harness.textDump()));

    text = harness.textDump();
    assert.match(text, /Turn 4/);  // turn_number 3 → "Turn 4"
    assert.match(text, /Turn 3/);  // turn_number 2 → "Turn 3"
    // Verify newest-first ordering: Turn 4 text appears before Turn 3
    const turn4Index = text.indexOf("Turn 4");
    const turn3Index = text.indexOf("Turn 3");
    assert(turn4Index < turn3Index, "Turn 4 (newest) should appear before Turn 3 in sorted order");

    // Session filtering: dispatch event for a different session (should be ignored)
    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "foreign-session-xyz",
      turn_number: 0,
      status: "in_progress",
      message: "foreign session event must be filtered",
    });
    assert.doesNotMatch(harness.textDump(), /foreign session event must be filtered/);

    // In-progress dot indicator is present on Turn 3 (in_progress status)
    const progressDots = historyRegion.querySelectorAll((node) => node.className === "vibecomfy-batch-progress-dot");
    assert(progressDots.length >= 1, "in_progress dot should be rendered");

    // ── Part 4: expand/collapse with statement diagnostics and landed count ──
    // Re-query batch rows fresh because the DOM was re-rendered by websocket dispatches.
    // Batch rows are sorted newest-first: Turn 4, Turn 3, Turn 2, Turn 1.
    // Turn 1 (turn_number=0) is the last row and has the statements + diagnostics.
    let freshRows = historyRegion.querySelectorAll((node) => node.className === "vibecomfy-batch-row");
    assert(freshRows.length >= 4, "should have at least 4 batch rows after live events");
    let turn1Row = freshRows[freshRows.length - 1];
    turn1Row.click();
    await waitFor(() => {
      const expanded = harness.document.body.querySelectorAll((node) => node.className === "vibecomfy-batch-expanded");
      return expanded.length >= 1;
    });

    text = harness.textDump();
    // Statement bullets with landed ✓ badges
    assert.match(text, /assign/);
    assert.match(text, /saveimage\.filename_prefix/);
    // Landed badge icon ✓ (checkmark) present
    assert.match(text, /\u2713/);
    // Failed badge icon ✗ present for the failed statement
    assert.match(text, /\u2717/);
    // Statement diagnostics
    assert.match(text, /STMT_DELETE_OK/);
    assert.match(text, /node removed cleanly/);
    assert.match(text, /WIRE_FAIL/);
    assert.match(text, /target slot occupied/);
    // Outcome footer (Turn 1 has "exit: step_continue · budget: 4 left · ok")
    assert.match(text, /exit: step_continue/);
    assert.match(text, /budget: 4 left/);
    // Reasoning toggle text
    assert.match(text, /Final reasoning summary/);

    // ── Part 5: absence of raw diff/source/audit paths in batch details ──
    // Also verify the collapsed Turn 2 row has the expected outcome when expanded.
    // Expand Turn 2 (freshRows[freshRows.length - 2]) to verify its footer and diagnostics
    let turn2Row = freshRows[freshRows.length - 2];
    turn2Row.click();
    await waitFor(() => {
      const expanded = harness.document.body.querySelectorAll((node) => node.className === "vibecomfy-batch-expanded");
      return expanded.length >= 2;
    });
    text = harness.textDump();
    assert.match(text, /exit: done/);
    // Turn-level diagnostics from Turn 2
    assert.match(text, /BATCH_OK/);
    assert.match(text, /all turns succeeded/);

    // These sensitive/internal fields should NOT appear in the batch row rendering
    const expandedText = harness.textDump();
    assert.doesNotMatch(expandedText, /\bdiff\b/i);
    assert.doesNotMatch(expandedText, /raw_batch/i);
    assert.doesNotMatch(expandedText, /raw_source/i);
    assert.doesNotMatch(expandedText, /provider_metadata/i);
    assert.doesNotMatch(expandedText, /raw_json/i);

    // Click both rows again to collapse
    turn1Row.click();
    turn2Row.click();
    await waitFor(() => {
      const expanded = harness.document.body.querySelectorAll((node) => node.className === "vibecomfy-batch-expanded");
      return expanded.length === 0;
    });

    // ── Part 6: Apply/Reject controls remain rendered and clickable after batch turns ──
    const applyButton = harness.document.getElementById("vibecomfy-agent-panel-apply");
    const rejectButton = harness.document.getElementById("vibecomfy-agent-panel-reject");
    const undoButton = harness.document.getElementById("vibecomfy-agent-panel-undo");
    assert(applyButton, "Apply button should exist");
    assert(rejectButton, "Reject button should exist");
    assert(undoButton, "Undo button should exist");
    assert.equal(applyButton.disabled, false, "Apply button should be enabled");
    assert.equal(rejectButton.disabled, false, "Reject button should be enabled");
    assert.match(applyButton.textContent, /Apply/);
    assert.match(rejectButton.textContent, /Reject/);

    // After all operations, batch turns are still visible in history
    assert.match(harness.textDump(), /analyzing the graph/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy preview diff computes named-port link deltas and drawPreviewOverlay renders ghost nodes with wire beziers, badges, and text without mutating the live graph", async () => {
  const liveGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        size: [240, 100],
        properties: { vibecomfy_uid: "uid-1" },
        inputs: [],
        outputs: [{ name: "IMAGE" }],
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [400, 200],
        size: [240, 100],
        properties: { vibecomfy_uid: "uid-2" },
        inputs: [{ name: "images" }],
        outputs: [],
      },
    ],
    links: [[1, 0, 2, 0, "IMAGE"]],
  };

  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        size: [240, 100],
        properties: { vibecomfy_uid: "uid-1" },
        inputs: [],
        outputs: [{ name: "IMAGE" }],
      },
      {
        id: 3,
        type: "PreviewImage",
        pos: [400, 200],
        size: [240, 124],
        properties: { vibecomfy_uid: "uid-3" },
        inputs: [{ name: "images" }],
        outputs: [],
        widgets_values: ["preview_val"],
      },
    ],
    links: [[1, 0, 3, 0, "IMAGE"]],
  };

  const candidateReport = {
    change: {
      content_edits: {
        preserved: ["uid-1"],
        edited: [],
        removed_named: [],
      },
    },
    recovery: [],
  };

  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    // Capture the live graph state before preview rendering
    const liveGraphBefore = harness.getCurrentGraph();
    const liveNodesBefore = harness.getLiveNodes().map((n) => ({
      id: n.id,
      type: n.type,
      pos: [...n.pos],
    }));

    // ── Compute the preview diff ──────────────────────────────────────
    const diff = extensionModule.computePreviewDiff(candidateGraph, candidateReport);

    // Assert diff shape has all required keys
    assert.ok(Array.isArray(diff.added_links), "added_links must be an array");
    assert.ok(Array.isArray(diff.removed_links), "removed_links must be an array");
    assert.ok(Array.isArray(diff.added), "added must be an array");
    assert.ok(Array.isArray(diff.removed), "removed must be an array");
    assert.ok(Array.isArray(diff.edited), "edited must be an array");
    assert.ok(Array.isArray(diff.removed_named), "removed_named must be an array");
    assert.ok(Array.isArray(diff.unresolved), "unresolved must be an array");

    // ── Assert added_links keyed by endpoint UID + port name ──────────
    assert.equal(diff.added_links.length, 1, "one added link expected");
    assert.match(
      diff.added_links[0],
      /^uid-1::IMAGE->uid-3::images$/,
      "added link key format: fromUid::fromPortName->toUid::toPortName",
    );

    // ── Assert removed_links keyed by endpoint UID + port name ────────
    assert.equal(diff.removed_links.length, 1, "one removed link expected");
    assert.match(
      diff.removed_links[0],
      /^uid-1::IMAGE->uid-2::images$/,
      "removed link key format: fromUid::fromPortName->toUid::toPortName",
    );

    // ── Assert added/removed node entries ────────────────────────────
    assert.equal(diff.added.length, 1);
    assert.equal(diff.added[0].uid, "uid-3");
    assert.equal(diff.added[0].class_type, "PreviewImage");
    assert.equal(diff.removed.length, 1);
    assert.equal(diff.removed[0].uid, "uid-2");
    assert.equal(diff.removed[0].class_type, "SaveImage");

    // ── Draw the preview overlay and capture canvas operations ────────
    // Embed the candidate graph so drawPreviewOverlay can render ghosts/wires
    // without depending on the module-scoped agentPanel state.
    const diffWithCandidate = { ...diff, _candidateGraph: candidateGraph };
    const drawOps = await harness.drawPreviewOverlay(diffWithCandidate);

    // Helper: find ops of a given kind
    const opsByKind = (kind) => drawOps.filter((op) => op.kind === kind);

    // ── Solid green added bezier ────────────────────────────────────
    // The wire drawing path sets strokeStyle to '#4caf50' (green) and
    // calls beginPath → moveTo → bezierCurveTo → stroke with no dash.
    const greenStrokeStyles = opsByKind("strokeStyle").filter(
      (op) => op.args[0] === "#4caf50",
    );
    assert.ok(greenStrokeStyles.length > 0, "green (#4caf50) strokeStyle must be set for added bezier");

    // Look for a solid (non-dashed) bezier drawn after green style
    let foundSolidGreenBezier = false;
    let lastStrokeStyle = null;
    let lastLineDash = null;
    for (const op of drawOps) {
      if (op.kind === "strokeStyle") lastStrokeStyle = op.args[0];
      if (op.kind === "setLineDash") lastLineDash = op.args[0];
      if (
        op.kind === "bezierCurveTo" &&
        lastStrokeStyle === "#4caf50" &&
        Array.isArray(lastLineDash) &&
        lastLineDash.length === 0
      ) {
        foundSolidGreenBezier = true;
        break;
      }
    }
    assert.ok(foundSolidGreenBezier, "must contain a solid green bezierCurveTo");

    // ── Dashed red removed bezier ───────────────────────────────────
    const redStrokeStyles = opsByKind("strokeStyle").filter(
      (op) => op.args[0] === "#f44336",
    );
    assert.ok(redStrokeStyles.length > 0, "red (#f44336) strokeStyle must be set for removed bezier");

    let foundDashedRedBezier = false;
    lastStrokeStyle = null;
    lastLineDash = null;
    for (const op of drawOps) {
      if (op.kind === "strokeStyle") lastStrokeStyle = op.args[0];
      if (op.kind === "setLineDash") lastLineDash = op.args[0];
      if (
        op.kind === "bezierCurveTo" &&
        lastStrokeStyle === "#f44336" &&
        Array.isArray(lastLineDash) &&
        lastLineDash.length === 2 &&
        lastLineDash[0] === 8 &&
        lastLineDash[1] === 4
      ) {
        foundDashedRedBezier = true;
        break;
      }
    }
    assert.ok(foundDashedRedBezier, "must contain a dashed red bezierCurveTo with [8,4] dash");

    // ── Ghost title text ────────────────────────────────────────────
    const titleTextOps = opsByKind("fillText").filter(
      (op) => op.args[0] === "PreviewImage",
    );
    assert.ok(titleTextOps.length > 0, "must contain ghost title fillText('PreviewImage', ...)");

    // ── At least one widget value text ──────────────────────────────
    const widgetTextOps = opsByKind("fillText").filter(
      (op) => op.args[0] === "preview_val",
    );
    assert.ok(widgetTextOps.length > 0, "must contain widget value fillText('preview_val', ...)");

    // ── Bottom-right badge drawing: "+ new" ─────────────────────────
    const newBadgeOps = opsByKind("fillText").filter(
      (op) => op.args[0] === "+ new",
    );
    assert.ok(newBadgeOps.length > 0, "must contain badge fillText('+ new', ...)");

    // The badge also has a fillRect with green background
    const badgeFillRects = opsByKind("fillRect").filter(
      () => true,
    );
    assert.ok(badgeFillRects.length > 0, "must contain fillRect for badge background");

    // ── Preview rendering does NOT mutate the live graph ────────────
    const liveGraphAfter = harness.getCurrentGraph();
    assert.deepEqual(liveGraphAfter, liveGraphBefore, "live graph must not change after preview rendering");

    const liveNodesAfter = harness.getLiveNodes().map((n) => ({
      id: n.id,
      type: n.type,
      pos: [...n.pos],
    }));
    assert.deepEqual(liveNodesAfter, liveNodesBefore, "live nodes must not change after preview rendering");

    // Canvas configure/clear/loadGraphData should NOT have been called
    assert.equal(harness.graphConfigureCalls.length, 0, "graph.configure must not be called during preview");
    assert.equal(harness.loadGraphDataCalls.length, 0, "loadGraphData must not be called during preview");
    assert.equal(harness.graphClearCalls.length, 0, "graph.clear must not be called during preview");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy edited-node overlay box encloses the title bar (LiteGraph pos[1] is body-top, title sits above)", async () => {
  // In LiteGraph node.pos[1] is the top of the BODY; the title bar is drawn
  // ABOVE it and node.size excludes the title. The amber edited-node box must
  // therefore start at pos[1] - NODE_TITLE_HEIGHT and be size[1] + TITLE_HEIGHT
  // tall, or it clips the title ("the box doesn't go around the whole item").
  const TITLE_H = 30; // LiteGraph.NODE_TITLE_HEIGHT in this frontend build
  const NODE_POS = [120, 240];
  const NODE_SIZE = [260, 120];

  const liveGraph = {
    nodes: [
      {
        id: 7,
        type: "KSampler",
        pos: [...NODE_POS],
        size: [...NODE_SIZE],
        properties: { vibecomfy_uid: "uid-edit" },
        inputs: [{ name: "model" }],
        outputs: [{ name: "LATENT" }],
        widgets_values: [42, "fixed"],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 7,
        type: "KSampler",
        pos: [...NODE_POS],
        size: [...NODE_SIZE],
        properties: { vibecomfy_uid: "uid-edit" },
        inputs: [{ name: "model" }],
        outputs: [{ name: "LATENT" }],
        widgets_values: [99, "fixed"], // first widget value changed
      },
    ],
    links: [],
  };
  const candidateReport = {
    change: { content_edits: { preserved: [], edited: ["uid-edit"], removed_named: [] } },
    recovery: [],
  };

  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const diff = extensionModule.computePreviewDiff(candidateGraph, candidateReport);
    assert.equal(diff.edited.length, 1, "one edited node expected");
    assert.equal(diff.edited[0].uid, "uid-edit");
    assert.ok(
      diff.edited[0].changedWidgetIndices.includes(0),
      "the changed first widget must be flagged",
    );

    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });

    // Find the amber (#ffc107) edited box: a strokeStyle set followed by strokeRect.
    let lastStroke = null;
    let editedRect = null;
    for (const op of drawOps) {
      if (op.kind === "strokeStyle") lastStroke = op.args[0];
      if (op.kind === "strokeRect" && lastStroke === "#ffc107") {
        editedRect = op.args; // [x, y, w, h]
        break;
      }
    }
    assert.ok(editedRect, "must stroke an amber (#ffc107) rect for the edited node");
    const [rx, ry, rw, rh] = editedRect;
    // Top edge must be at or above pos[1] - TITLE_H (encloses the title bar).
    assert.ok(
      ry <= NODE_POS[1] - TITLE_H,
      `box top ${ry} must sit at/above body-top-minus-title ${NODE_POS[1] - TITLE_H}`,
    );
    // Height must cover body + title (not just the body).
    assert.ok(
      rh >= NODE_SIZE[1] + TITLE_H,
      `box height ${rh} must cover body+title (>= ${NODE_SIZE[1] + TITLE_H})`,
    );
    // And the box bottom must reach the body bottom.
    assert.ok(ry + rh >= NODE_POS[1] + NODE_SIZE[1], "box must reach the body bottom");
    // Width tracks the node width.
    assert.ok(rw >= NODE_SIZE[0], "box width must cover the node width");
  } finally {
    await harness.dispose();
  }
});
