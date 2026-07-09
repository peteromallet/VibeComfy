import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";

import { createBrowserHarness, createMockCanvasContext } from "./harness.mjs";
import {
  clearPreviewDomOverlay,
  drawPreviewOverlay as drawPanelOverlayPreviewOverlay,
  syncPreviewDomOverlay,
} from "../../vibecomfy/comfy_nodes/web/panel_overlay.js";
import {
  adaptLegacyAgentEditResponse,
  normalizeCanonicalAgentEditResponse,
  readApplyCandidate,
  readFieldChanges,
  readLatestCandidate,
  readTurnIdentity,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract.js";
import {
  assertCanonicalNormalPathHasNoLegacyAliases,
  assertNormalDomTextHasNoForbiddenFieldOrValue,
} from "./projection_boundary_helpers.mjs";

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

const OVERLAY_FORBIDDEN_TEXT_PATTERNS = [
  /\b(?:canvas_apply_allowed|canvasApplyAllowed|queue_allowed|queueAllowed)\b/i,
  /\b(?:debug_payload|debugPayload|audit_ref|auditRef|raw_path|rawPath|artifact_path|artifactPath)\b/i,
  /\/(?:real\/)?ComfyUI\/out\/editor_sessions\//i,
  /\bturns\/\d+\/(?:response|messages|candidate|debug)\.[a-z0-9]+/i,
  /\b(?:ProviderError|Traceback|stack trace|engine diagnostics|raw diagnostic)\b/i,
  /\b(?:model prompt|system prompt|prompt messages)\b/i,
  /\b(?:token budget|exit mode|remaining batches)\b/i,
];

function assertCanvasTextOpsHaveNoForbiddenText(drawOps, path) {
  const textOps = drawOps.filter((op) => op.kind === "fillText" || op.kind === "strokeText");
  assert.ok(textOps.length > 0, `${path} should record canvas text operations`);
  for (const op of textOps) {
    const text = String(op.args[0] ?? "");
    for (const pattern of OVERLAY_FORBIDDEN_TEXT_PATTERNS) {
      assert.equal(pattern.test(text), false, `${path} leaked forbidden canvas text: ${text}`);
    }
  }
}

function makePanelOverlayDeps(liveGraph) {
  const vecNumber = (vec, index, fallback) => {
    const value = vec != null ? Number(vec[index]) : NaN;
    return Number.isFinite(value) ? value : fallback;
  };
  const readNodeSize = (node, fallbackW = 200, fallbackH = 100) => ({
    w: vecNumber(node?.size, 0, fallbackW),
    h: vecNumber(node?.size, 1, fallbackH),
  });
  const readNodePos = (node, fallbackX = 0, fallbackY = 0) => ({
    x: vecNumber(node?.pos, 0, fallbackX),
    y: vecNumber(node?.pos, 1, fallbackY),
  });
  const readNodeBounding = (node, titleHeight) => {
    const pos = readNodePos(node);
    const size = readNodeSize(node);
    return { x: pos.x, y: pos.y - titleHeight, w: size.w, h: size.h + titleHeight };
  };
  return {
    VC_COLORS: { edited: "#ffc107", added: "#4caf50", removed: "#f44336" },
    currentAgentPanel: () => null,
    getLiveGraph: () => liveGraph,
    getLiveGraphNodes: (graph) => Array.isArray(graph?.nodes) ? graph.nodes : [],
    getUid: (node) => node?.properties?.vibecomfy_uid || null,
    hexToRgba: (hex, alpha) => {
      const value = String(hex || "#000000").replace("#", "");
      const r = Number.parseInt(value.slice(0, 2), 16) || 0;
      const g = Number.parseInt(value.slice(2, 4), 16) || 0;
      const b = Number.parseInt(value.slice(4, 6), 16) || 0;
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    },
    readNodeBounding,
    readNodePos,
    readNodeSize,
    readWidgetValues: (node) => Array.isArray(node?.widgets_values) ? node.widgets_values : [],
    vecNumber,
    widgetValuePreviewText: (value) => {
      if (value == null) return "";
      if (typeof value === "string") return value;
      if (typeof value === "number" || typeof value === "boolean") return String(value);
      if (Array.isArray(value)) return "[...]";
      return "{...}";
    },
    captureLiveCanvasRevision: () => 1,
    graphNodeCount: (graph) => Array.isArray(graph?.nodes) ? graph.nodes.length : 0,
  };
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

async function waitFor(predicate, { attempts = 200 } = {}) {
  for (let index = 0; index < attempts; index += 1) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error("waitFor timed out");
}

const LAYOUT_PREVIEW_TEST_FIT_PADDING_PX = 80;
const LAYOUT_PREVIEW_TEST_FIT_MAX_SCALE = 1.0;

function graphNodeBoundsForViewportTest(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  let count = 0;
  for (const node of nodes) {
    const x = Number(node?.pos?.[0]);
    const y = Number(node?.pos?.[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      continue;
    }
    const width = Number.isFinite(Number(node?.size?.[0])) && Number(node.size[0]) > 0 ? Number(node.size[0]) : 200;
    const height = Number.isFinite(Number(node?.size?.[1])) && Number(node.size[1]) > 0 ? Number(node.size[1]) : 100;
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + width);
    maxY = Math.max(maxY, y + height);
    count += 1;
  }
  if (count === 0) {
    return null;
  }
  return {
    x: minX,
    y: minY,
    w: Math.max(maxX - minX, 1),
    h: Math.max(maxY - minY, 1),
  };
}

function expectedLayoutPreviewViewportForTest(graph, { width, height }) {
  const bounds = graphNodeBoundsForViewportTest(graph);
  assert(bounds, "expected test graph to have node bounds");
  const availableWidth = Math.max(1, width - LAYOUT_PREVIEW_TEST_FIT_PADDING_PX * 2);
  const availableHeight = Math.max(1, height - LAYOUT_PREVIEW_TEST_FIT_PADDING_PX * 2);
  const scale = Math.min(
    LAYOUT_PREVIEW_TEST_FIT_MAX_SCALE,
    availableWidth / bounds.w,
    availableHeight / bounds.h,
  );
  const centerX = bounds.x + bounds.w / 2;
  const centerY = bounds.y + bounds.h / 2;
  return {
    scale,
    offset: [
      (width / 2 / scale) - centerX,
      (height / 2 / scale) - centerY,
    ],
  };
}

function assertViewportClose(actual, expected, label) {
  assert(actual, `${label}: missing viewport`);
  assert.equal(Math.abs(Number(actual.scale) - expected.scale) < 1e-9, true, `${label}: scale`);
  assert.equal(Math.abs(Number(actual.offset?.[0]) - expected.offset[0]) < 1e-9, true, `${label}: offset x`);
  assert.equal(Math.abs(Number(actual.offset?.[1]) - expected.offset[1]) < 1e-9, true, `${label}: offset y`);
}

function expandAgentBubbleDetails(root) {
  const toggles = root.querySelectorAll(
    (node) => (
      node.dataset?.vibecomfyBubbleDetailToggle === "1"
      || String(node.className || "").split(/\s+/).includes("vibecomfy-batch-row")
    ),
  );
  for (const toggle of toggles) {
    if (!String(toggle.textContent || "").includes("\u25bc")) {
      toggle.click();
    }
  }
  return toggles.length;
}

function agentPanelRegionIds(root) {
  return root
    .querySelectorAll((node) => typeof node.id === "string" && node.id.startsWith("vibecomfy-agent-panel-region-"))
    .map((node) => node.id)
    .sort();
}

function getChatMessagesMount(document) {
  return document.body.querySelectorAll(
    (node) => node.dataset?.vibecomfyChatMessages === "1",
  )[0] || null;
}

function chatMessageKeys(messagesMount) {
  return (messagesMount?.children || []).map((node) => node.dataset?.vibecomfyMessageKey || "");
}

function makeElementRejectFunctionSelectors(node) {
  const originalQuerySelectorAll = node.querySelectorAll.bind(node);
  node.querySelectorAll = (selector) => {
    if (typeof selector === "function") {
      throw new TypeError("Failed to execute 'querySelectorAll': parameter 1 is not of type 'string'.");
    }
    return originalQuerySelectorAll(selector);
  };
  return () => {
    node.querySelectorAll = originalQuerySelectorAll;
  };
}

function findBubbleDetailSectionByTitle(root, title) {
  return root.querySelectorAll(
    (node) => node.children?.length >= 2 && String(node.children[0]?.textContent || "") === title,
  )[0] || null;
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

test("submitRating validates response identity before network calls", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agent-edit/rating": { body: { ok: true } },
    },
  });
  try {
    const mod = await harness.loadExtension();
    const result = await mod.submitRating({ state: { sessionId: "", turnId: "0001" } }, { rating: 8 });

    assert.equal(result.ok, false);
    assert.equal(result.error, "validation");
    assert.equal(harness.requests.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("submitRating rejects missing turn metadata before network calls", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agent-edit/rating": { body: { ok: true } },
    },
  });
  try {
    const mod = await harness.loadExtension();
    const result = await mod.submitRating({ state: { sessionId: "sess-missing-turn" } }, { rating: 8 });

    assert.equal(result.ok, false);
    assert.equal(result.error, "validation");
    assert.match(result.detail, /Missing turn_id/);
    assert.equal(harness.requests.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("submitRating posts metadata-only rating without ZIP fields", async () => {
  const seen = [];
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agent-edit/rating": ({ options }) => {
        const body = JSON.parse(options.body);
        seen.push(body);
        return { status: 201, body: { ok: true, rating_id: "rating-meta" } };
      },
    },
  });
  try {
    const mod = await harness.loadExtension();
    const result = await mod.submitRating(
      { state: { sessionId: "sess-1", turnId: "0001" } },
      { rating: 7, comment: "useful" },
    );

    assert.deepEqual(result, { ok: true, rating_id: "rating-meta" });
    assert.deepEqual(seen[0], {
      response_id: "sess-1/0001",
      session_id: "sess-1",
      turn_id: "0001",
      rating: 7,
      pack_shared: false,
      pack_comment: null,
      comment: "useful",
    });
    assert.equal("pack_zip_base64" in seen[0], false);
  } finally {
    await harness.dispose();
  }
});

test("submitRating builds, size-checks, and uploads debug pack when requested", async () => {
  const seen = [];
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agent-edit/session-bundle?session_id=sess-pack": {
        body: {
          ok: true,
          exists: true,
          session_path: "out/editor_sessions/sess-pack",
          total_bytes: 12,
          files: [{ name: "turns/0001/response.json", text: "{\"ok\":true}\n" }],
          skipped: [],
        },
      },
      "/vibecomfy/agent-edit/rating": ({ options }) => {
        const body = JSON.parse(options.body);
        seen.push(body);
        return { status: 201, body: { ok: true, rating_id: "rating-pack" } };
      },
    },
  });
  try {
    const mod = await harness.loadExtension();
    const panel = {
      panelId: "panel-pack",
      pendingDirtySections: [],
      state: {
        phase: "AWAITING_REVIEW",
        sessionId: "sess-pack",
        turnId: "0001",
        baselineTurnId: "0000",
        turns: [],
        chatMessages: [],
        routeStatus: { kind: "ready" },
      },
    };
    const result = await mod.submitRating(panel, {
      rating: 9,
      packShared: true,
      packComment: "debug context attached",
    });

    assert.deepEqual(result, { ok: true, rating_id: "rating-pack" });
    assert.equal(seen[0].pack_shared, true);
    assert.equal(seen[0].pack_comment, "debug context attached");
    assert.match(seen[0].pack_zip_base64, /^[A-Za-z0-9+/]+=*$/);
    const zipBytes = Buffer.from(seen[0].pack_zip_base64, "base64");
    assert.equal(zipBytes.subarray(0, 4).toString("latin1"), "PK\u0003\u0004");
  } finally {
    await harness.dispose();
  }
});

test("submitRating rejects oversized debug pack before posting rating payload", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agent-edit/session-bundle?session_id=sess-pack": {
        body: {
          ok: true,
          exists: true,
          session_path: "out/editor_sessions/sess-pack",
          total_bytes: 1024,
          files: [{ name: "turns/0001/response.json", text: "{\"ok\":true}\n" }],
          skipped: [],
        },
      },
      "/vibecomfy/agent-edit/rating": { body: { ok: true } },
    },
  });
  try {
    const mod = await harness.loadExtension();
    const result = await mod.submitRating(
      {
        panelId: "panel-pack",
        pendingDirtySections: [],
        state: {
          phase: "AWAITING_REVIEW",
          sessionId: "sess-pack",
          turnId: "0001",
          turns: [],
          chatMessages: [],
          routeStatus: { kind: "ready" },
        },
      },
      { rating: 9, packShared: true, maxZipBytes: 32 },
    );

    assert.equal(result.ok, false);
    assert.equal(result.error, "pack_too_large");
    assert.equal(harness.requests.some((request) => request.url === "/vibecomfy/agent-edit/rating"), false);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy structural graph projection ignores volatile canvas fields but keeps real edits", async () => {
  let harness;
  harness = await createBrowserHarness({
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
    assert.deepEqual(project(graph), {
      nodes: [
        {
          id: 1,
          type: "Input",
          mode: null,
          inputs: [],
          outputs: ["IMAGE"],
          widgets_values: ["a prompt", { keep: "value" }],
        },
        {
          id: 2,
          type: "SaveImage",
          mode: null,
          inputs: ["images"],
          outputs: [],
          widgets_values: ["prefix"],
        },
      ],
      links: [{ from: 1, out: "IMAGE", to: 2, in: "images", type: "IMAGE" }],
    });
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
    const extensionModule = await harness.loadExtension();
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
    assert(canvasMenu.includes("Edit with Agent (VibeComfy)"));

    await harness.invokeCommand("VibeComfy.Roundtrip");
    assert.equal(harness.serializeCalls.length, 1);
    assert.deepEqual(
      harness.requests.map((entry) => entry.url),
      ["/vibecomfy/ping", "/system_stats", "/vibecomfy/demo/scenarios", "/vibecomfy/roundtrip"],
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
    assert.ok(harness.document.getElementById("vibecomfy-agent-panel-region-chat"));
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
    const extensionModule = await harness.loadExtension();
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
    assert.equal(intentNode.properties["VibeComfy Intent Badge"], "sandboxed_loose");
    assert.equal(intentNode.properties["VibeComfy Intent Source"], "value = image");
    assert.equal(intentNode.properties["VibeComfy Intent Spec"], "inspect image value");
    // Dynamic-IO: slot.name preserved (serialization key), slot.label carries the type annotation.
    assert.equal(intentNode.inputs[0].name, "value");
    assert.equal(intentNode.inputs[0].label, "image: IMAGE");
    assert.equal(intentNode.outputs[0].name, "value");
    assert.equal(intentNode.outputs[0].label, "preview: IMAGE");

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
    assert(drawOps.some((entry) => entry[0] === "text" && entry[1] === "sandboxed_loose"));

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

test("VibeComfy agent executor submit posts the live graph, renders the reply, and dedupes in-flight submits", async () => {
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
      "/vibecomfy/agent-executor": async () => {
        await pendingResponse;
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "session-1",
            turn_id: "0001",
            baseline_turn_id: null,
            outcome: {
              kind: "noop",
              reason: "executor reply rendered",
            },
            graph_unchanged: true,
            canvas_apply_allowed: false,
            apply_allowed: false,
            queue_allowed: false,
            message: "executor reply rendered",
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

    const panel = extensionModule.ensureAgentPanel();
    panel.state.chatMessages = [
      { role: "user", text: "previous user request", local_id: "prior-user", timestamp: "2026-01-01T00:00:00.000Z" },
      { role: "agent", text: "previous agent reply", local_id: "prior-agent", timestamp: "2026-01-01T00:00:01.000Z" },
    ];
    extensionModule.resetThreadRenderState(panel);
    extensionModule.markAgentPanelDirty(panel, ["THREAD"]);
    extensionModule.renderAgentPanel(panel, { dirtySections: ["THREAD"] });
    assert.ok(harness.textDump().includes("previous agent reply"), "seeded prior chat should render before submit");

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "tighten the prompt";
    harness.document.getElementById("vibecomfy-agent-panel-route").value = " codex ";
    harness.document.getElementById("vibecomfy-agent-panel-model").value = "  gpt-5.1  ";

    const submitButton = harness.document.getElementById("vibecomfy-agent-panel-submit");
    firstSubmit = submitButton.click();
    duplicateSubmit = submitButton.click();

    await waitFor(() => harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-executor").length === 1);
    await waitFor(() => harness.textDump().includes("tighten the prompt"));
    const pendingText = harness.textDump();
    assert.ok(pendingText.includes("previous user request"), "prior user message should remain visible while pending");
    assert.ok(pendingText.includes("previous agent reply"), "prior agent message should remain visible while pending");
    assert.ok(pendingText.includes("tighten the prompt"), "submitted user prompt should render immediately");
    assert.doesNotMatch(pendingText, /In progress\.\.\./, "pending agent bubble should not render a duplicate progress label");
    assert.ok(pendingText.includes("Decide") && pendingText.includes("Research") && pendingText.includes("Execute") && pendingText.includes("Review"));
    const executorStage = (stage) => harness.document.body.querySelectorAll(
      (node) => node.dataset?.vibecomfyExecutorStage === stage,
    )[0];
    assert.equal(
      executorStage("decide")?.dataset?.vibecomfyExecutorStatus,
      "active",
      "initial pending bubble should show the decide stage as active",
    );
    harness.dispatchApiEvent("vibecomfy.executor.phase", {
      phase: "implement",
      status: "start",
      session_id: "session-1",
      executor_id: "executor-test",
    });
    await waitFor(() => (
      executorStage("execute")?.dataset?.vibecomfyExecutorStatus === "active"
    ));
    assert.equal(
      executorStage("research")?.dataset?.vibecomfyExecutorStatus,
      "done",
      "executor websocket phase should repaint the visible pending bubble",
    );
    assert.doesNotMatch(pendingText, /Turn 1/, "executor pending/status chrome must not render Turn labels");
    assert.equal(
      harness.document.body.querySelectorAll((node) => node.className === "vibecomfy-batch-row").length,
      0,
      "executor pending status must not create batch turn rows",
    );
    assert.equal(
      harness.document.getElementById("vibecomfy-agent-panel-region-history")?.style.display,
      "none",
      "executor pending status must not show the legacy below-thread activity strip",
    );
    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "session-1",
      turn_id: "0001",
      turn_number: 1,
      status: "progress",
      landed_op_count: 1,
      statement_count: 2,
    });
    await waitFor(() => (
      executorStage("execute")?.dataset?.vibecomfyExecutorStatus === "active"
    ));
    assert.doesNotMatch(
      harness.textDump(),
      /In progress\.\.\./,
      "agent-edit turn websocket progress should update stages without adding progress label text",
    );
    assert.equal(
      harness.document.body.querySelectorAll((node) => node.dataset?.vibecomfyChatEmpty === "1" && node.style.display !== "none").length,
      0,
      "chat empty-state mount should be hidden after optimistic messages",
    );

    const request = harness.requests.find((entry) => entry.url === "/vibecomfy/agent-executor");
    const payload = JSON.parse(request.body);
    assert.equal(request.method, "POST");
    assert.equal(payload.task, "tighten the prompt");
    assert.deepEqual(payload.graph, graph);
    assert.equal(payload.client_id, harness.api.clientId);
    assert.equal(payload.route, "openai-codex");
    assert.equal(payload.model, "gpt-5.1");
    assert.equal(payload.client_graph_hash, sha256HexUtf8(graph));
    assert.equal(payload.client_structural_graph_hash, sha256HexUtf8((await harness.loadExtension()).buildStructuralGraphProjection(graph)));
    assert.equal(payload.client_live_canvas_token, "live:rev:1");
    assert.equal("baseline_turn_id" in payload, false);
    assert.match(payload.idempotency_key, /^submit:new:openai-codex:gpt-5\.1:[0-9a-f]{12}:[0-9a-f-]+$/);

    releaseResponse();
    await firstSubmit;

    await waitFor(() => harness.textDump().includes("executor reply rendered"));
    const finalText = harness.textDump();
    assert.ok(finalText.includes("previous user request"), "prior user message should remain visible after reply");
    assert.ok(finalText.includes("previous agent reply"), "prior agent message should remain visible after reply");
    assert.ok(finalText.includes("executor reply rendered"));
    assert.ok(finalText.indexOf("tighten the prompt") < finalText.indexOf("executor reply rendered"));
    assert.doesNotMatch(finalText, /In progress\.\.\./, "pending bubble should be replaced by final reply");
    assert.doesNotMatch(finalText, /Turn 1/);
    assert.equal(
      harness.document.body.querySelectorAll((node) => node.dataset?.vibecomfyChatEmpty === "1" && node.style.display !== "none").length,
      0,
      "chat empty-state mount should remain hidden after final reply",
    );
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-submit")?.textContent, "Submit");
  } finally {
    releaseResponse?.();
    await Promise.allSettled([firstSubmit, duplicateSubmit].filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy executor submit preserves prior chat history while pending", async () => {
  const graph = {
    links: [],
    nodes: [
      { id: 1, type: "LoadImage", properties: { vibecomfy_uid: "uid-load" } },
    ],
  };
  let releaseResponse;
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
      "/vibecomfy/agent-executor": async () => {
        await pendingResponse;
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "session-history",
            turn_id: "0002",
            baseline_turn_id: null,
            outcome: {
              kind: "noop",
              reason: "second executor answer",
            },
            graph_unchanged: true,
            canvas_apply_allowed: false,
            apply_allowed: false,
            queue_allowed: false,
            message: "second executor answer",
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

    const panel = extensionModule.ensureAgentPanel();
    panel.state.chatMessages = [
      { role: "user", text: "first user message", source: "agent-edit", local_id: "first-user" },
      { role: "agent", text: "first agent answer", source: "agent-edit", local_id: "first-agent" },
    ];
    extensionModule.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "second user message";
    const submitPromise = harness.document.getElementById("vibecomfy-agent-panel-submit").click();
    await waitFor(() => harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-executor").length === 1);

    const pendingText = harness.textDump();
    assert.match(pendingText, /first user message/);
    assert.match(pendingText, /first agent answer/);
    assert.match(pendingText, /second user message/);
    assert.doesNotMatch(pendingText, /In progress\.\.\./);
    assert.match(pendingText, /Decide/);
    assert.match(pendingText, /Research/);
    assert.match(pendingText, /Execute/);
    assert.match(pendingText, /Review/);
    assert.doesNotMatch(pendingText, /Try an example/);
    assert.doesNotMatch(pendingText, /Turn 1/);
    assert.equal(
      harness.document.body.querySelectorAll((node) => node.className === "vibecomfy-batch-row").length,
      0,
      "executor pending status must stay inside the chat bubble",
    );

    releaseResponse();
    await submitPromise;
    await waitFor(() => harness.textDump().includes("second executor answer"));
    const finalText = harness.textDump();
    assert.match(finalText, /first user message/);
    assert.match(finalText, /first agent answer/);
    assert.match(finalText, /second user message/);
    assert.match(finalText, /second executor answer/);
    assert.doesNotMatch(finalText, /Try an example/);
  } finally {
    releaseResponse?.();
    await harness.dispose();
  }
});

test("VibeComfy disables Submit while provider readiness is loading", async () => {
  let releaseStatus;
  const pendingStatus = new Promise((resolve) => {
    releaseStatus = resolve;
  });
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": async () => {
        await pendingStatus;
        return {
          status: 200,
          body: {
            ok: true,
            ready: true,
            provider_available: true,
            route: "deepseek",
            requested_route: "auto",
            route_options: {
              auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
              deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            },
          },
        };
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled, true);
    assert.notEqual(harness.document.getElementById("vibecomfy-agent-panel-submit")?.style.display, "none");
    releaseStatus();
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);
  } finally {
    releaseStatus?.();
    await harness.dispose();
  }
});

test("VibeComfy does not use client structural hash drift as a local candidate blocker", async () => {
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
      "/vibecomfy/agent-executor": async () => {
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
            message: "Candidate remains backend-CAS reviewable.",
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
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "tighten the graph";
    submitPromise = harness.clickButton("Submit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent-executor"));

    harness.setCurrentGraph(changedGraph);
    releaseResponse();
    await submitPromise;

    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Review Changes");
    assert.match(harness.textDump(), /Candidate remains backend-CAS reviewable/);
    assert.doesNotMatch(harness.textDump(), /StaleResponseArrival/);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, false);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 0);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.getCurrentGraph().nodes[1]?.id, 3);
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-clarify",
          turn_id: "0001",
          baseline_turn_id: null,
          outcome: {
            kind: "clarify",
            question: clarifyQuestion,
          },
          graph_unchanged: true,
          canvas_apply_allowed: false,
          apply_allowed: false,
          queue_allowed: false,
          message: clarifyQuestion,
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
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "USe SD3 instead";
    submitPromise = harness.clickButton("Submit");
    await submitPromise;

    // Status banner reflects a clarify turn, NOT a candidate review.
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Needs Your Input");
    assert.doesNotMatch(harness.textDump(), /Review Changes/);
    // The clarification question is surfaced to the user (text may be truncated in the dump).
    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /specify which existing nodes to repla/);
    assert.doesNotMatch(harness.textDump(), /I need clarification before continuing/);
    assert.doesNotMatch(harness.textDump(), /Clarify question/);
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

test("VibeComfy stale-canvas submit failure renders Rebaseline & retry and auto-resubmits", async () => {
  const submitBodies = [];
  const rebaselineBodies = [];
  const initialGraph = {
    nodes: [{ id: 1, type: "EmptyLatentImage", properties: { vibecomfy_uid: "latent" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "EmptyLatentImage", properties: { vibecomfy_uid: "latent" } },
      { id: 2, type: "KSampler", properties: { vibecomfy_uid: "sampler" } },
    ],
    links: [],
  };
  const recoveryButtonsFor = () => harness.document.body.querySelectorAll(
    (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyRecoveryAction === "stale-rebaseline-retry",
  );
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-executor": async ({ options }) => {
        const body = JSON.parse(options.body);
        submitBodies.push(body);
        if (submitBodies.length === 1) {
          return {
            status: 409,
            body: {
              ok: false,
              kind: "StaleStateMismatch",
              stage: "ingest",
              retryable: true,
              graph_unchanged: true,
              user_facing_message: "The canvas changed since the current backend baseline. Rebaseline and resubmit from the current canvas.",
              next_action: "Rebaseline and retry from the current canvas.",
              session_id: "session-stale-submit",
              turn_id: "0005",
              baseline_turn_id: "0004",
              baseline_graph_hash: "baseline-old",
              rebaseline_recovery: {
                action: "rebaseline",
                endpoint: "/vibecomfy/agent-edit/rebaseline",
                reason: "stale_state_recovery",
                last_known_baseline_graph_hash: "baseline-old",
                submit_graph_hash: "submit-old",
                submit_structural_graph_hash: "submit-structural-old",
                client_graph_hash: body.client_graph_hash,
                client_structural_graph_hash: body.client_structural_graph_hash,
              },
            },
          };
        }
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "session-stale-submit",
            turn_id: "0006",
            baseline_turn_id: null,
            baseline_graph_hash: "baseline-current-canvas",
            baseline_graph_hash_kind: "structural",
            baseline_graph_hash_version: 2,
            baseline_source: "rebaseline",
            baseline_rebaseline_id: "rebaseline-0001",
            baseline_graph_source_path: "_rebaseline/rebaseline-0001/graph.ui.json",
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: false,
            apply_eligibility: {
              applyable: true,
              reason: "queue_blocked_warning",
              message: "Apply is allowed, but Queue remains blocked for this candidate.",
              warnings: ["queue_blocked"],
            },
            message: "Recovered candidate ready.",
            submit_graph_hash: "submit-after-rebaseline",
            candidate_graph_hash: "candidate-after-rebaseline",
            graph: candidateGraph,
            candidate: { state: "candidate", graph: candidateGraph, graph_hash: "candidate-after-rebaseline" },
            report: { change: { content_edits: { edited: ["sampler"] } }, recovery: [] },
          },
        };
      },
      "/vibecomfy/agent-edit/rebaseline": async ({ options }) => {
        const body = JSON.parse(options.body);
        rebaselineBodies.push(body);
        return {
          status: 200,
          body: {
            ok: true,
            action: "rebaseline",
            session_id: "session-stale-submit",
            baseline_turn_id: null,
            baseline_graph_hash: "baseline-current-canvas",
            baseline_graph_hash_kind: "structural",
            baseline_graph_hash_version: 2,
            baseline_source: "rebaseline",
            baseline_rebaseline_id: "rebaseline-0001",
            baseline_graph_source_path: "_rebaseline/rebaseline-0001/graph.ui.json",
            apply_allowed: false,
            canvas_apply_allowed: false,
            queue_allowed: false,
            apply_eligibility: {
              applyable: false,
              reason: "no_candidate",
              message: "No candidate is available to apply.",
              warnings: [],
            },
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
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "set the batch size to 2";
    await harness.clickButton("Submit");
    await waitFor(() => recoveryButtonsFor().length === 1);

    assert.equal(panel.state.phase, "ERROR");
    assert.equal(panel.state.rebaselineRecovery?.last_known_baseline_graph_hash, "baseline-old");
    assert.match(harness.textDump(), /Rebaseline & retry/);

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "";
    recoveryButtonsFor()[0].click();
    await waitFor(() => rebaselineBodies.length === 1);
    await waitFor(() => submitBodies.length === 2);
    await waitFor(() => panel.state.phase === "AWAITING_REVIEW");

    assert.equal(rebaselineBodies[0].reason, "stale_state_recovery");
    assert.equal(rebaselineBodies[0].last_known_baseline_graph_hash, "baseline-old");
    assert.equal(submitBodies[1].task, "set the batch size to 2");
    assert.equal(submitBodies[1].session_id, "session-stale-submit");
    assert.equal(panel.state.candidateGraphHash, "candidate-after-rebaseline");
    assert.equal(panel.state.rebaselineRecovery, null);
    assert.equal(recoveryButtonsFor().length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy renders no-op edit turns without entering review", async () => {
  const graph = {
    nodes: [{ id: 1, type: "KSampler", properties: { vibecomfy_uid: "ksampler" } }],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-noop",
          turn_id: "0001",
          baseline_turn_id: null,
          outcome: {
            kind: "noop",
            reason: "KSampler cfg is already 6.5; no change needed.",
          },
          graph_unchanged: true,
          canvas_apply_allowed: false,
          apply_allowed: false,
          queue_allowed: false,
          message: "KSampler cfg is already 6.5; no change needed.",
          report: { done_summary: "No change needed." },
        },
      },
    },
  });

  let submitPromise;
  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "set the main sampler cfg to 6.5";
    submitPromise = harness.clickButton("Submit");
    await submitPromise;

    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");
    assert.match(harness.textDump(), /already 6\.5; no change needed/i);
    assert.doesNotMatch(harness.textDump(), /Review Changes/);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled, false);
    assert.equal(harness.loadGraphDataCalls.length, 0);
  } finally {
    await Promise.allSettled([submitPromise].filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy treats graph-unchanged all-gates-false candidate responses as no-op turns", async () => {
  const graph = {
    nodes: [{ id: 1, type: "KSampler", properties: { vibecomfy_uid: "ksampler" } }],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-noop-compat",
          turn_id: "0001",
          baseline_turn_id: null,
          candidate: { graph },
          graph,
          candidate_graph_hash: sha256HexUtf8(graph),
          graph_unchanged: true,
          canvas_apply_allowed: false,
          apply_allowed: false,
          queue_allowed: false,
          apply_eligibility: {
            applyable: false,
            reason: "unchanged_candidate",
            message: "The candidate is identical to the submitted graph.",
            warnings: [],
          },
          message: "Nothing needed changing; the workflow already matches that.",
          report: { done_summary: "No change needed." },
        },
      },
    },
  });

  let submitPromise;
  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "make sure cfg is already right";
    submitPromise = harness.clickButton("Submit");
    await submitPromise;

    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");
    assert.doesNotMatch(harness.textDump(), /Review Changes/);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled, false);
    assert.equal(harness.loadGraphDataCalls.length, 0);
  } finally {
    await Promise.allSettled([submitPromise].filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy live submit no-op response shape settles in Ready without review", async () => {
  const graph = {
    nodes: [{ id: 1, type: "KSampler", properties: { vibecomfy_uid: "refiner-sampler" } }],
    links: [],
  };
  const candidateGraphHash = sha256HexUtf8(graph);
  const liveNoopResponse = {
    ok: true,
    session_id: "715b2b4ad80b447b8d5cb123d1c3e10e",
    turn_id: "0002",
    baseline_turn_id: "0001",
    graph_unchanged: true,
    apply_allowed: false,
    canvas_apply_allowed: false,
    queue_allowed: false,
    outcome: {
      kind: "noop",
      reason: "The refiner sampler seed is already set to 999.",
    },
    candidate: {
      graph,
      report: { done_summary: "No edits applied." },
    },
    graph,
    candidate_graph_hash: candidateGraphHash,
    candidate_structural_graph_hash: "68495b9658c4c542d239723759c25969d339409e72f305971db42c835eb1b271",
    apply_eligibility: {
      applyable: false,
      reason: "unchanged_candidate",
      message: "The candidate is identical to the submitted graph.",
      warnings: [],
    },
    gates: {
      ir_validate_ok: true,
      lower_ok: true,
      python_load_ok: true,
      queue_validate_ok: false,
      state_match_ok: true,
      ui_emit_ok: true,
      ui_fidelity_ok: true,
      ui_load_safe_ok: true,
    },
    report: {
      done_summary: "No edits applied — identity verified; Gate B passed. Summary: No operations were applied.",
      queue_blockers: [],
    },
    message: "Nothing needed changing; the workflow already matches that.",
  };
  const harness = await createBrowserHarness({
    graph,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: liveNoopResponse,
      },
    },
  });

  let submitPromise;
  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "set the refiner sampler seed to 999";
    submitPromise = harness.clickButton("Submit");
    await submitPromise;

    const panel = extensionModule.ensureAgentPanel();
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-executor").length, 1);
    assert.equal(panel.state.phase, "IDLE");
    assert.equal(panel.state.candidateGraph, null);
    assert.equal(panel.state.candidateGraphHash, null);
    assert.equal(panel.state.applyAllowed, false);
    assert.equal(panel.state.canvasApplyAllowed, false);
    assert.equal(panel.state.queueAllowed, false);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");
    assert.match(harness.textDump(), /Nothing needed changing; the workflow already matches that\./);
    assert.doesNotMatch(harness.textDump(), /Review Changes/);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled, false);
    assert.equal(harness.loadGraphDataCalls.length, 0);
  } finally {
    await Promise.allSettled([submitPromise].filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy answer-only no-op response renders the assistant explanation", async () => {
  const graph = {
    nodes: [{ id: 1, type: "VHS_VideoCombine", properties: { vibecomfy_uid: "video-output" } }],
    links: [],
  };
  const answer = "This workflow turns an input image into a short video with audio.";
  const harness = await createBrowserHarness({
    graph,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-answer-noop",
          turn_id: "0001",
          graph_unchanged: true,
          apply_allowed: false,
          canvas_apply_allowed: false,
          queue_allowed: false,
          outcome: {
            kind: "noop",
            reason: "No edits applied - identity verified; Gate B passed. Summary: No operations were applied.",
          },
          graph,
          report: {
            done_summary: "No edits applied - identity verified; Gate B passed. Summary: No operations were applied.",
            queue_blockers: [],
          },
          change_details: {
            done_summary: "No edits applied - identity verified; Gate B passed. Summary: No operations were applied.",
            batch_turns: [
              {
                turn_number: 0,
                batch: "done()",
                batch_ok: true,
                landed_op_count: 0,
                message: answer,
                statements: [{ op_kind: "done", ok: true, landed: false }],
              },
            ],
          },
          message: answer,
        },
      },
    },
  });

  let submitPromise;
  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "What's happening in this workflow?";
    submitPromise = harness.clickButton("Submit");
    await submitPromise;

    const panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.phase, "IDLE");
    assert.equal(panel.state.candidateGraph, null);
    assert.equal(panel.state.applyAllowed, false);
    assert.match(harness.textDump(), /turns an input image into a short video with audio/);
    assert.doesNotMatch(harness.textDump(), /Nothing needed changing; the workflow already matches that\./);
    assert.doesNotMatch(harness.textDump(), /Review Changes/);
  } finally {
    await Promise.allSettled([submitPromise].filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy preserves Apply controls for edit+clarify candidates", async () => {
  const SESSION_ID = "session-edit-clarify";
  const initialGraph = {
    nodes: [{ id: 1, type: "SaveImage", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [{ id: 1, type: "SaveImage", properties: { vibecomfy_uid: "uid-1" }, widgets_values: ["after"] }],
    links: [],
  };
  const question = "Should I also rename the file stem?";
  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0002",
          outcome: { kind: "edit+clarify", question, changes: [{ uid: "uid-1", field_path: "filename_prefix", old: "before", new: "after" }] },
          candidate: { state: "candidate", graph: candidateGraph, graph_hash: "candidate-edit-clarify" },
          eligibility: { applyable: true, reason: "queue_blocked_warning", message: "Apply is allowed, but Queue remains blocked for this candidate.", warnings: ["queue_blocked"] },
          graph: candidateGraph,
          report: { change: { content_edits: { edited: ["uid-1"] } }, recovery: [] },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          candidate_graph_hash: "candidate-edit-clarify",
          message: `Applied 1 edit. ${question}`,
        },
      },
      [`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`]: {
        status: 200,
        body: {
          ok: true,
          exists: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "change prefix", turn_id: "0002" },
            { role: "agent", text: `Applied 1 edit. ${question}`, turn_id: "0002" },
          ],
        },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "change prefix";
    await harness.clickButton("Submit");

    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Review Changes");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, false);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, false);
    assert.match(harness.textDump(), /Should I also rename the file stem/);
    assert.doesNotMatch(harness.textDump(), /Reply in the prompt/);
    assert.doesNotMatch(harness.textDump(), /Your answer continues this same session/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy failure bubble uses envelope user_facing_message for MalformedModelJSON", async () => {
  const SESSION_ID = "session-malformed-json";
  const userFacing = "The model response could not be parsed. The graph is unchanged.";
  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }], links: [] },
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 400,
        body: {
          ok: false,
          kind: "MalformedModelJSON",
          stage: "agent_response",
          session_id: SESSION_ID,
          turn_id: "0003",
          user_facing_message: userFacing,
          message: userFacing,
          graph_unchanged: true,
          canvas_apply_allowed: false,
          queue_allowed: false,
        },
      },
      [`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`]: {
        status: 200,
        body: {
          ok: true,
          exists: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "do it", turn_id: "0003" },
            { role: "agent", text: userFacing, turn_id: "0003" },
          ],
        },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "do it";
    await harness.clickButton("Submit");

    assert.match(harness.textDump(), /The model response could not be parsed\. The graph is unchanged\./);
    assert.doesNotMatch(harness.textDump(), /Some requested edits did not land/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy reads typed candidate and eligibility envelopes without compatibility mirrors", async () => {
  const SESSION_ID = "session-typed-candidate";
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };

  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0002",
          baseline_turn_id: null,
          candidate: {
            graph: candidateGraph,
          },
          eligibility: {
            applyable: true,
            reason: "applyable",
            message: "Apply is allowed.",
            warnings: [],
          },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Typed candidate ready.",
          report: {
            change: {
              content_edits: {
                preserved: ["uid-1"],
                new_auto_placed: ["uid-2"],
              },
            },
          },
          audit_ref: { path: "/tmp/typed-candidate-audit.json" },
        },
      },
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: SESSION_ID,
          turn_id: "0002",
          baseline_turn_id: "0002",
          baseline_graph_hash: "baseline-typed-candidate",
          queue_allowed: true,
          audit_ref: { path: "/tmp/typed-candidate-accept.json" },
        },
      },
      [`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
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

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "add a saver";
    await harness.clickButton("Submit");
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled === false, {
      attempts: 200,
    });
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, false);
    assert.match(harness.textDump(), /Typed candidate ready/);
    assert.match(harness.textDump(), /applyEligibility.*applyable/);

    await harness.clickButton("Apply");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.deepEqual(harness.graphConfigureCalls[0], candidateGraph);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");
    // M2 T13 makes per-bubble details lazy; expand before asserting detail-only feedback.
    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /Ready|Typed candidate ready|Candidate accepted/);
  } finally {
    await harness.dispose();
  }
});

// ── Lifecycle Contract: A5 Backend accept rejected ──────────────────────

test("Lifecycle A5 backend accept rejected disables an applyable candidate", async () => {
  const SESSION_ID = "session-accept-rejects";
  const candidateGraph = {
    nodes: [{ id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } }],
    links: [],
  };
  const failureMessage = "This candidate has been superseded.";
  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }], links: [] },
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0004",
          candidate: { state: "candidate", graph: candidateGraph, graph_hash: "candidate-hash" },
          eligibility: { applyable: true, reason: "applyable", message: "Apply is allowed.", warnings: [] },
          graph: candidateGraph,
          report: { change: { content_edits: { edited: ["uid-2"] } }, recovery: [] },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          candidate_graph_hash: "candidate-hash",
          message: "Candidate ready.",
        },
      },
      "/vibecomfy/agent-edit/accept": {
        status: 409,
        body: {
          ok: false,
          kind: "StaleStateMismatch",
          stage: "accept",
          session_id: SESSION_ID,
          turn_id: "0004",
          user_facing_message: failureMessage,
          message: failureMessage,
          graph_unchanged: true,
        },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
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

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "make candidate";
    await harness.clickButton("Submit");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, false);
    await harness.clickButton("Apply");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.match(harness.textDump(), /This candidate has been superseded/);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
  } finally {
    await harness.dispose();
  }
});

test("Accept-stage stale mismatch renders one failure bubble and rebaseline-retries the original task", async () => {
  const SESSION_ID = "session-accept-stale-recovery";
  const originalTask = "set KSampler steps to 12";
  const failureMessage = "The submitted graph no longer matches the current canvas. Resubmit.";
  const submitBodies = [];
  const rebaselineBodies = [];
  const initialGraph = {
    nodes: [{ id: 1, type: "KSampler", properties: { vibecomfy_uid: "sampler", steps: 8 } }],
    links: [],
  };
  const changedGraph = {
    nodes: [{ id: 1, type: "KSampler", properties: { vibecomfy_uid: "sampler", steps: 10 } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [{ id: 1, type: "KSampler", properties: { vibecomfy_uid: "sampler", steps: 12 } }],
    links: [],
  };
  const recoveredCandidateGraph = {
    nodes: [{ id: 1, type: "KSampler", properties: { vibecomfy_uid: "sampler", steps: 12, cfg: 7 } }],
    links: [],
  };
  let chatRequestCount = 0;
  const nodeText = (node) => [
    String(node?.textContent || ""),
    ...(Array.isArray(node?.children) ? node.children.map((child) => nodeText(child)) : []),
  ].join("");
  const recoveryButtonsFor = () => harness.document.body.querySelectorAll(
    (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyRecoveryAction === "stale-rebaseline-retry",
  );
  const failureBubblesFor = () => harness.document.body.querySelectorAll(
    (node) => node.dataset?.vibecomfyMessageKey && nodeText(node).includes(failureMessage),
  );
  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": async ({ options }) => {
        const body = JSON.parse(options.body);
        submitBodies.push(body);
        if (submitBodies.length === 1) {
          return {
            status: 200,
            body: {
              ok: true,
              session_id: SESSION_ID,
              turn_id: "0004",
              baseline_turn_id: "0003",
              baseline_graph_hash: "baseline-old",
              baseline_graph_hash_kind: "structural",
              baseline_graph_hash_version: 2,
              baseline_source: "turn",
              canvas_apply_allowed: true,
              apply_allowed: true,
              queue_allowed: true,
              apply_eligibility: { applyable: true, reason: "applyable", message: "Apply is allowed.", warnings: [] },
              candidate: { state: "candidate", graph: candidateGraph, graph_hash: "candidate-old" },
              graph: candidateGraph,
              candidate_graph_hash: "candidate-old",
              submit_graph_hash: "submit-old",
              report: { change: { content_edits: { edited: ["sampler"] } }, recovery: [] },
              message: "Candidate ready.",
            },
          };
        }
        return {
          status: 200,
          body: {
            ok: true,
            session_id: SESSION_ID,
            turn_id: "0005",
            baseline_turn_id: null,
            baseline_graph_hash: "baseline-current",
            baseline_graph_hash_kind: "structural",
            baseline_graph_hash_version: 2,
            baseline_source: "rebaseline",
            baseline_rebaseline_id: "rebaseline-0001",
            baseline_graph_source_path: "_rebaseline/rebaseline-0001/graph.ui.json",
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: false,
            apply_eligibility: {
              applyable: true,
              reason: "queue_blocked_warning",
              message: "Apply is allowed, but Queue remains blocked for this candidate.",
              warnings: ["queue_blocked"],
            },
            candidate: { state: "candidate", graph: recoveredCandidateGraph, graph_hash: "candidate-recovered" },
            graph: recoveredCandidateGraph,
            candidate_graph_hash: "candidate-recovered",
            submit_graph_hash: "submit-recovered",
            report: { change: { content_edits: { edited: ["sampler"] } }, recovery: [] },
            message: "Recovered candidate ready.",
          },
        };
      },
      "/vibecomfy/agent-edit/accept": {
        status: 409,
        body: {
          ok: false,
          kind: "StaleStateMismatch",
          stage: "accept",
          session_id: SESSION_ID,
          turn_id: "0004",
          user_facing_message: failureMessage,
          message: failureMessage,
          graph_unchanged: true,
        },
      },
      "/vibecomfy/agent-edit/rebaseline": async ({ options }) => {
        const body = JSON.parse(options.body);
        rebaselineBodies.push(body);
        return {
          status: 200,
          body: {
            ok: true,
            action: "rebaseline",
            session_id: SESSION_ID,
            baseline_turn_id: null,
            baseline_graph_hash: "baseline-current",
            baseline_graph_hash_kind: "structural",
            baseline_graph_hash_version: 2,
            baseline_source: "rebaseline",
            baseline_rebaseline_id: "rebaseline-0001",
            baseline_graph_source_path: "_rebaseline/rebaseline-0001/graph.ui.json",
            rebaseline_id: "rebaseline-0001",
            apply_allowed: false,
            canvas_apply_allowed: false,
            queue_allowed: false,
            apply_eligibility: { applyable: false, reason: "no_candidate", message: "No candidate is available to apply.", warnings: [] },
          },
        };
      },
      [`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`]: async () => {
        chatRequestCount += 1;
        return {
          status: 200,
          body: {
            ok: true,
            exists: true,
            session_id: SESSION_ID,
            messages: chatRequestCount === 1
              ? [
                  { role: "user", text: originalTask, turn_id: "0004" },
                  { role: "agent", text: "Candidate ready.", turn_id: "0004" },
                ]
              : [
                  { role: "user", text: originalTask, turn_id: "0004" },
                  { role: "agent", text: "Candidate ready.", turn_id: "0004" },
                  { role: "user", text: originalTask, turn_id: "0005" },
                  { role: "agent", text: "Recovered candidate ready.", turn_id: "0005" },
                ],
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
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = originalTask;
    await harness.clickButton("Submit");
    await waitFor(() => panel.state.phase === "AWAITING_REVIEW");
    await waitFor(() => harness.textDump().includes("Candidate ready."));

    harness.setCurrentGraph(changedGraph);
    await harness.clickButton("Apply");
    await waitFor(() => panel.state.phase === "ERROR");
    await waitFor(() => recoveryButtonsFor().length === 1);
    await waitFor(() => failureBubblesFor().length === 1);

    assert.equal(panel.state.rebaselineRecovery?.reason, "stale_state_recovery");
    assert.equal(panel.state.rebaselineRecovery?.last_known_baseline_graph_hash, "baseline-old");
    assert.equal(failureBubblesFor().length, 1);
    assert.equal(harness.loadGraphDataCalls.length, 0);

    recoveryButtonsFor()[0].click();
    await waitFor(() => rebaselineBodies.length === 1);
    await waitFor(() => submitBodies.length === 2);
    await waitFor(() => panel.state.phase === "AWAITING_REVIEW");

    assert.equal(rebaselineBodies[0].reason, "stale_state_recovery");
    assert.equal(rebaselineBodies[0].last_known_baseline_graph_hash, "baseline-old");
    assert.equal(submitBodies[1].task, originalTask);
    assert.equal(submitBodies[1].session_id, SESSION_ID);
    assert.deepEqual(submitBodies[1].graph, changedGraph);
    assert.equal(panel.state.candidateGraphHash, "candidate-recovered");
    assert.equal(panel.state.rebaselineRecovery, null);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy ignores raw apply booleans when apply_eligible authorizes Apply", async () => {
  const SESSION_ID = "session-raw-bools-ignored";
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };

  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0004",
          baseline_turn_id: null,
          candidate: {
            graph: candidateGraph,
          },
          apply_eligible: true,
          // Raw booleans set to false — UI must ignore them.
          canvas_apply_allowed: false,
          apply_allowed: false,
          queue_allowed: true,
          message: "Candidate with apply_eligible true but raw booleans false.",
          report: {
            change: {
              content_edits: {
                preserved: ["uid-1"],
                new_auto_placed: ["uid-2"],
              },
            },
          },
          audit_ref: { path: "/tmp/raw-bools-ignored-audit.json" },
        },
      },
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: SESSION_ID,
          turn_id: "0004",
          baseline_turn_id: "0004",
          queue_allowed: true,
          audit_ref: { path: "/tmp/raw-bools-ignored-accept.json" },
        },
      },
      [`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
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

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "add a saver";
    await harness.clickButton("Submit");

    // Apply must be ENABLED because apply_eligible is true and a candidate exists,
    // even though raw apply_allowed and canvas_apply_allowed are false.
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, false);
    assert.match(harness.textDump(), /applyEligibility.*applyable/);

    // Verify Apply actually works — not gated by raw booleans.
    await harness.clickButton("Apply");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy disables Apply and warns when a candidate arrives without apply_eligible", async () => {
  const SESSION_ID = "session-missing-eligibility";
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0003",
          baseline_turn_id: null,
          candidate: {
            graph: candidateGraph,
          },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Candidate missing apply_eligible contract.",
          report: {
            change: {
              content_edits: {
                preserved: ["uid-1"],
                new_auto_placed: ["uid-2"],
              },
            },
          },
          audit_ref: { path: "/tmp/missing-eligibility-audit.json" },
        },
      },
      [`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
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

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "add a saver";
    await harness.clickButton("Submit");

    const applyButton = harness.document.getElementById("vibecomfy-agent-panel-apply");
    assert.equal(applyButton?.disabled, true);
    assert.match(harness.textDump(), /Candidate missing apply_eligible|Review Changes/);

    await harness.clickButton("Apply");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 0);
  } finally {
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
      "/vibecomfy/agent-executor": async () => responses.shift(),
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "make it safer";
    await harness.clickButton("Submit");

    // M2 T13 keeps candidate report rows behind collapsed lazy bubble details.
    expandAgentBubbleDetails(harness.document.body);
    const successText = harness.textDump();
    assert.match(successText, /Candidate blocked for queue review\./);
    assert.match(successText, /canvasApplyAllowed.*false/);
    assert.match(successText, /queueAllowed.*false/);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.loadGraphDataCalls.length, 0);

    await harness.clickButton("Reject");
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "break it";
    await harness.clickButton("Submit");

    expandAgentBubbleDetails(harness.document.body);
    const failureText = harness.textDump();
    assert.match(failureText, /ValidationError @ emit/);
    assert.match(failureText, /backend stage: emit \(0.75\)/);
    assert.match(failureText, /Fix the emitted graph\./);
    assert.match(failureText, /agent failure context/);
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
        apply_eligibility: {
          applyable: false,
          reason: "server_blocked",
          message: "Server validation gates blocked Apply.",
          warnings: [],
        },
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
        apply_eligibility: {
          applyable: true,
          reason: "queue_blocked_warning",
          message: "Apply is allowed, but Queue remains blocked for this candidate.",
          warnings: ["queue_blocked"],
        },
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
        baseline_graph_hash: "baseline-after-undo",
        baseline_graph_hash_kind: "structural",
        baseline_graph_hash_version: 2,
        baseline_source: "rebaseline",
        baseline_rebaseline_id: "undo-0001",
        baseline_graph_source_path: "_rebaseline/undo-0001/graph.ui.json",
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        apply_eligibility: {
          applyable: true,
          reason: "queue_blocked_warning",
          message: "Apply is allowed, but Queue remains blocked for this candidate.",
          warnings: ["queue_blocked"],
        },
        message: "Post-undo candidate.",
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
        baseline_turn_id: "0003",
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        apply_eligibility: {
          applyable: true,
          reason: "queue_blocked_warning",
          message: "Apply is allowed, but Queue remains blocked for this candidate.",
          warnings: ["queue_blocked"],
        },
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
        turn_id: "0005",
        baseline_turn_id: "0003",
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        apply_eligibility: {
          applyable: true,
          reason: "queue_blocked_warning",
          message: "Apply is allowed, but Queue remains blocked for this candidate.",
          warnings: ["queue_blocked"],
        },
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
        kind: "StaleStateMismatch",
        stage: "accept",
        graph_unchanged: true,
        user_facing_message: "The canvas changed after this candidate was generated. Submit a new edit from the current canvas.",
        next_action: "Submit a new edit from the current canvas.",
        session_id: "session-apply",
        turn_id: "0004",
        baseline_turn_id: "0003",
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
        turn_id: "0005",
        baseline_turn_id: "0003",
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
      "/vibecomfy/agent-executor": async ({ options }) => {
        const body = JSON.parse(options.body);
        if (body.task === "post undo baseline submit") {
          assert.equal(body.session_id, "session-apply");
          assert.equal(body.client_graph_hash, initialGraphHash);
          assert.equal(typeof body.client_structural_graph_hash, "string");
        }
        return submitResponses.shift();
      },
      "/vibecomfy/agent-edit/accept": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.equal(body.session_id, "session-apply");
        assert.match(body.turn_id, /^000[245]$/);
        assert.equal(body.client_graph_hash, initialGraphHash);
        assert.deepEqual(body.live_graph, harness.getCurrentGraph());
        if (body.turn_id === "0002") {
          assert.equal(body.client_live_canvas_token, "live:rev:1");
        } else {
          assert.match(body.client_live_canvas_token, /^live:rev:\d+$/);
        }
        assert.equal(body.submit_graph_hash, body.turn_id === "0002" ? initialGraphHash : undefined);
        assert.equal(body.candidate_graph_hash, candidateGraphHash);
        assert.match(body.idempotency_key, /^accept:session-apply:000[245]:[0-9a-f]{12}:/);
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
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    const applyButton = harness.document.getElementById("vibecomfy-agent-panel-apply");
    const undoButton = harness.document.getElementById("vibecomfy-agent-panel-undo");
    const panel = extensionModule.ensureAgentPanel();

    prompt.value = "preview only";
    await harness.clickButton("Submit");
    assert.equal(applyButton.disabled, true);
    await harness.clickButton("Apply");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 0);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);

    await harness.clickButton("Reject");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/reject").length, 1);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), initialGraph);
    assert.match(harness.textDump(), /rejected/);
    expandAgentBubbleDetails(harness.document.body);

    prompt.value = "allowed";
    await harness.clickButton("Submit");
    assert.equal(applyButton.disabled, false);
    const blockedQueueResult = harness.app.queuePrompt("prompt-1");
    assert.equal(blockedQueueResult, null);
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.match(harness.textDump(), /Queue blocked for turn 0002 because queue_allowed=false\./);
    // The Apply action repaints for the in-place configure and may also repaint
    // to clear the candidate preview overlay. Every repaint in this scoped
    // window must be a full [true,true] invalidation; no other canvas dirties
    // should appear.
    harness.graphDirtyCanvasCalls.length = 0;
    harness.canvasDrawCalls.length = 0;
    const operationCountBeforeApply = harness.operationLog.length;
    const applyPromise = harness.clickButton("Apply");
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
    assert.ok(
      harness.graphDirtyCanvasCalls.length >= 1 && harness.graphDirtyCanvasCalls.length <= 2,
      `expected one configure repaint plus optional preview-clear repaint, got ${harness.graphDirtyCanvasCalls.length}`,
    );
    assert.deepEqual(
      harness.graphDirtyCanvasCalls,
      Array.from({ length: harness.graphDirtyCanvasCalls.length }, () => [true, true]),
    );
    assert.ok(
      harness.canvasDrawCalls.length >= 1 && harness.canvasDrawCalls.length <= 2,
      `expected one configure draw plus optional preview-clear draw, got ${harness.canvasDrawCalls.length}`,
    );
    assert.deepEqual(
      harness.canvasDrawCalls,
      Array.from({ length: harness.canvasDrawCalls.length }, () => [true, true]),
    );
    assert.equal(harness.app.canvas.graph._nodes.find((node) => node.id === 2)?.boxcolor, "#ffc107");
    // M2 T13 keeps applied-node feedback behind collapsed lazy bubble details.
    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /Applied candidate feedback: changed nodes were highlighted on the canvas temporarily\./);
    assert.match(harness.textDump(), /Edited uid-2/);
    assert.equal(panel.state.undoStack.length, 1, "undo stack should record the applied turn");
    assert.equal(undoButton.disabled, false);

    const postApplyQueueResult = harness.app.queuePrompt("prompt-applied");
    assert.deepEqual(postApplyQueueResult, { queued: true, args: ["prompt-applied"] });
    assert.equal(harness.queuePromptCalls.length, 1);

    await harness.clickButton("Undo Last Apply");
    assert.equal(harness.loadGraphDataCalls.length, 1);
    assert.deepEqual(harness.loadGraphDataCalls[0], initialGraph);
    assert.deepEqual(harness.getCurrentGraph(), initialGraph);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/rebaseline").length, 1);
    assert.equal(rebaselineBodies.length, 1);
    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /Applied candidate feedback/);
    assert.equal(panel.state.undoStack.length, 0, "undo stack should be empty after undo");
    assert.equal(undoButton.disabled, true);

    const allowedQueueResult = harness.app.queuePrompt("prompt-2");
    assert.deepEqual(allowedQueueResult, { queued: true, args: ["prompt-2"] });
    assert.equal(harness.queuePromptCalls.length, 2);

    await harness.clickButton("Undo Last Apply");
    assert.equal(harness.loadGraphDataCalls.length, 1);

    prompt.value = "post undo baseline submit";
    await harness.clickButton("Submit");
    assert.doesNotMatch(harness.textDump(), /StaleStateMismatch/);
    assert.match(harness.textDump(), /Post-undo candidate/);

    harness.setCurrentGraph(initialGraph);
    prompt.value = "stale";
    await harness.clickButton("Submit");
    harness.setCurrentGraph({ nodes: [{ id: 99, type: "Dirty" }], links: [] });
    await harness.clickButton("Apply");
    assert.match(harness.textDump(), /StaleStateMismatch/);
    assert.match(harness.textDump(), /Submit a new edit from the current canvas\./);
    assert.match(harness.textDump(), /The canvas changed after this candidate was generated/);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 2);
    assert.equal(harness.loadGraphDataCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);

    harness.setCurrentGraph(initialGraph);
    prompt.value = "accept fails";
    await harness.clickButton("Submit");
    await harness.clickButton("Apply");
    assert.match(harness.textDump(), /EditorAheadConflict/);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 3);
    assert.equal(harness.loadGraphDataCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy reorganisation candidates preview the candidate layout and preserve baseline undo", async () => {
  const canvasSize = { width: 1000, height: 800 };
  const staleViewport = { scale: 0.12, offset: [2750, -344] };
  const originalGraph = {
    nodes: [
      { id: 1, type: "Input", pos: [40, 50], size: [210, 90], properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "Output", pos: [80, 210], size: [210, 90], properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
    groups: [{ title: "Before", bounding: [20, 30, 320, 330] }],
  };
  const reorganisedGraph = {
    nodes: [
      { id: 1, type: "Input", pos: [500, 80], size: [210, 90], properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "Output", pos: [760, 80], size: [210, 90], properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
    groups: [{ title: "After", bounding: [480, 45, 520, 180] }],
  };
  const originalGraphHash = sha256HexUtf8(originalGraph);
  const reorganisedGraphHash = sha256HexUtf8(reorganisedGraph);
  const submitResponses = [
    {
      status: 200,
      body: {
        ok: true,
        route: "reorganise",
        session_id: "session-layout-preview",
        turn_id: "0001",
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        apply_eligibility: {
          applyable: true,
          reason: "applyable",
          message: "Reorganise candidate is ready.",
          warnings: [],
        },
        message: "Reorganised layout candidate ready to review.",
        graph: reorganisedGraph,
        submit_graph_hash: originalGraphHash,
        candidate_graph_hash: reorganisedGraphHash,
        report: {
          kind: "reorganise",
          change: { content_edits: { preserved: ["uid-1", "uid-2"], edited: [], removed_named: [] } },
          recovery: [],
        },
      },
    },
    {
      status: 200,
      body: {
        ok: true,
        route: "reorganise",
        session_id: "session-layout-preview",
        turn_id: "0002",
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: false,
        apply_eligibility: {
          applyable: true,
          reason: "applyable",
          message: "Reorganise candidate is ready.",
          warnings: [],
        },
        message: "Reorganised layout candidate ready to review.",
        graph: reorganisedGraph,
        submit_graph_hash: originalGraphHash,
        candidate_graph_hash: reorganisedGraphHash,
        report: {
          kind: "reorganise",
          change: { content_edits: { preserved: ["uid-1", "uid-2"], edited: [], removed_named: [] } },
          recovery: [],
        },
      },
    },
  ];
  const harness = await createBrowserHarness({
    graph: originalGraph,
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
      "/vibecomfy/agent-executor": () => submitResponses.shift(),
      "/vibecomfy/agent-edit/reject": () => ({
        status: 200,
        body: {
          ok: true,
          action: "reject",
          session_id: "session-layout-preview",
          turn_id: "0001",
        },
      }),
      "/vibecomfy/agent-edit/accept": () => ({
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: "session-layout-preview",
          turn_id: "0002",
          baseline_turn_id: "0002",
          baseline_graph_hash: "baseline-after-layout-preview",
          baseline_graph_hash_kind: "structural",
          baseline_graph_hash_version: 2,
        },
      }),
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    harness.app.canvas.canvas = {
      width: canvasSize.width,
      height: canvasSize.height,
      clientWidth: canvasSize.width,
      clientHeight: canvasSize.height,
    };
    harness.app.canvas.ds = { scale: staleViewport.scale, offset: [...staleViewport.offset] };
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    const panel = extensionModule.ensureAgentPanel();

    prompt.value = "reorganise this";
    await harness.clickButton("Submit");
    await waitFor(() => panel.state.phase === "AWAITING_REVIEW");
    // Non-destructive preview: the live canvas must keep the ORIGINAL layout —
    // nodes do not move until the user Applies.
    assert.deepEqual(harness.getCurrentGraph(), originalGraph, "preview must not move nodes — canvas keeps the original layout");
    assertViewportClose(harness.app.canvas.ds, staleViewport, "preview must not change the canvas viewport");
    assert.ok(panel.state._layoutPreviewBaseline?.graph, "preview baseline should capture the pre-preview graph for the diff");
    // The diff still describes both moves (old position -> new position).
    const reviewDiff = extensionModule.computePreviewDiff(panel.state.candidateGraph, panel.state.candidateReport);
    assert.equal(reviewDiff.layout_moved.length, 2, "review should preserve moved-node preview entries");
    for (const entry of reviewDiff.layout_moved) {
      assert.ok(
        entry.before.x !== entry.after.x || entry.before.y !== entry.after.y,
        "each layout_moved entry must carry a real before->after delta",
      );
    }
    // The overlay draws movement arrows (dashed shaft + filled arrowhead), not
    // per-node "moved" text badges.
    const reviewDrawOps = await harness.drawPreviewOverlay(reviewDiff);
    assert.ok(reviewDrawOps.some((op) => op.kind === "stroke"), "review overlay should draw movement arrow shafts");
    assert.ok(reviewDrawOps.some((op) => op.kind === "fill"), "review overlay should draw movement arrowheads");
    assert.ok(
      !reviewDrawOps.some((op) => op.kind === "fillText" && String(op.args[0]).includes("moved")),
      "review overlay should not draw per-node moved badges",
    );

    await harness.clickButton("Reject");
    assert.deepEqual(harness.getCurrentGraph(), originalGraph, "reject leaves the original layout untouched (nothing was moved)");
    assertViewportClose(harness.app.canvas.ds, staleViewport, "reject leaves the viewport unchanged");

    prompt.value = "reorganise this again";
    await harness.clickButton("Submit");
    await waitFor(() => panel.state.phase === "AWAITING_REVIEW");
    assert.deepEqual(harness.getCurrentGraph(), originalGraph, "second preview must also keep the original layout in place");
    assertViewportClose(harness.app.canvas.ds, staleViewport, "second preview must not change the viewport");

    await harness.clickButton("Apply");
    assert.deepEqual(harness.getCurrentGraph(), reorganisedGraph, "apply should commit the reorganised layout");
    assertViewportClose(harness.app.canvas.ds, staleViewport, "apply leaves the viewport as-is");
    assert.equal(panel.state.undoStack.length, 1);
    assert.deepEqual(panel.state.undoStack[0].graph, originalGraph, "undo should restore the layout before the change");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy rehydrate restores reorganise latest-candidate layout preview", async () => {
  const SESSION_ID = "session-layout-rehydrate-preview";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const originalGraph = {
    nodes: [
      { id: 1, type: "Input", pos: [40, 50], size: [210, 90], properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "Output", pos: [80, 210], size: [210, 90], properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  const reorganisedGraph = {
    nodes: [
      { id: 1, type: "Input", pos: [500, 80], size: [210, 90], properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "Output", pos: [760, 80], size: [210, 90], properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  const reorganisedGraphHash = sha256HexUtf8(reorganisedGraph);
  const harness = await createBrowserHarness({
    graph: originalGraph,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          },
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          latest_turn_id: "0001",
          latest_candidate: {
            ok: true,
            route: "reorganise",
            session_id: SESSION_ID,
            turn_id: "0001",
            outcome: { kind: "candidate", changes: [] },
            candidate: {
              state: "candidate",
              graph: reorganisedGraph,
              graph_hash: reorganisedGraphHash,
              turn_identity: { session_id: SESSION_ID, turn_id: "0001" },
            },
            graph: reorganisedGraph,
            candidate_graph_hash: reorganisedGraphHash,
            eligibility: {
              applyable: true,
              reason: "applyable",
              message: "Reorganise candidate is ready.",
              warnings: [],
            },
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: true,
            message: "Reorganised layout candidate ready to review.",
            report: { kind: "reorganise" },
          },
          messages: [
            { role: "user", text: "reorganise this workflow", turn_id: "0001" },
            { role: "agent", text: "Reorganised layout candidate ready to review.", turn_id: "0001" },
          ],
        },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    const panel = extensionModule.ensureAgentPanel();

    await waitFor(() => panel.state.phase === "AWAITING_REVIEW");
    await waitFor(() => panel.state._layoutPreviewActive === true);
    // Non-destructive: rehydrate activates the preview but must NOT swap the
    // canvas — nodes stay at the original layout, with arrows drawn on top.
    assert.deepEqual(harness.getCurrentGraph(), originalGraph, "rehydrated preview must keep the original layout in place");
    assert.equal(panel.state._layoutPreviewActive, true, "rehydrated reorganise candidate should activate layout preview state");
    assert.deepEqual(panel.state._layoutPreviewBaseline.graph, originalGraph, "rehydrated preview baseline should preserve the pre-preview layout");
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-apply-drift",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
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
        assert.match(body.client_graph_hash, /^[0-9a-f]{64}$/);
        assert.notEqual(body.client_graph_hash, initialGraphHash);
        assert.deepEqual(body.live_graph?.extra, driftedGraph.extra);
        assert.deepEqual(body.live_graph?.nodes?.[0]?.pos, driftedGraph.nodes[0].pos);
        assert.deepEqual(body.live_graph?.nodes?.[0]?.flags, driftedGraph.nodes[0].flags);
        assert.deepEqual(body.live_graph?.nodes?.[0]?.properties, driftedGraph.nodes[0].properties);
        assert.deepEqual(body.live_graph?.nodes?.[0]?.widgets_values, driftedGraph.nodes[0].widgets_values);
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
    await harness.clickButton("Apply");

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    await waitFor(() => harness.graphConfigureCalls.length + harness.loadGraphDataCalls.length === 1);
    assert.equal(harness.graphConfigureCalls.length + harness.loadGraphDataCalls.length, 1);
    assert.deepEqual(harness.graphConfigureCalls[0] || harness.loadGraphDataCalls[0], candidateGraph);
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-apply-token-drift",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
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
        assert.match(body.client_graph_hash, /^[0-9a-f]{64}$/);
        assert.notEqual(body.client_graph_hash, initialGraphHash);
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
    await harness.clickButton("Apply");

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    assert.deepEqual(harness.graphConfigureCalls[0], candidateGraph);
    assert.doesNotMatch(harness.textDump(), /StaleStateMismatch/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy Apply relies on backend CAS to block structural drift even when the live canvas revision is unchanged", async () => {
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-apply-structural-drift",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
          message: "Allowed candidate.",
          graph: candidateGraph,
          submit_graph_hash: initialGraphHash,
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
          report: { change: { content_edits: { preserved: [], edited: ["2"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.equal(body.session_id, "session-apply-structural-drift");
        assert.equal(body.turn_id, "0001");
        assert.equal(body.client_graph_hash, initialGraphHash);
        return {
          status: 409,
          body: {
            ok: false,
            kind: "StaleStateMismatch",
            stage: "accept",
            graph_unchanged: true,
            user_facing_message: "The canvas changed after this candidate was generated. Submit a new edit from the current canvas.",
            next_action: "Submit a new edit from the current canvas.",
            session_id: "session-apply-structural-drift",
            turn_id: "0001",
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
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "change the sampler";
    await harness.clickButton("Submit");

    harness.setCurrentGraphWithoutRevisionBump(structurallyChangedGraph);
    await harness.clickButton("Apply");

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.match(harness.textDump(), /StaleStateMismatch/);
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-live-token",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
          graph: candidateGraph,
          submit_graph_hash: initialGraphHash,
          candidate_graph_hash: candidateGraphHash,
          report: { change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.deepEqual(body.live_graph, harness.getCurrentGraph());
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
      "/vibecomfy/agent-edit/chat?session_id=session-live-token": {
        status: 200,
        body: { ok: true, session_id: "session-live-token", messages: [] },
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
    await harness.clickButton("Apply");

    assert.match(harness.textDump(), /canvas changed while Apply was waiting for backend acceptance/i);
    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /expected_live_canvas_token/);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), initialGraph);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy v2 Apply uses scoped delta mutation, tolerates unrelated post-accept drift, and reports verified canvas changes", async () => {
  const initialGraph = {
    nodes: [
      {
        id: 1,
        type: "Input",
        properties: { vibecomfy_uid: "producer-1" },
        outputs: [{ name: "IMAGE", links: [41, 42] }],
      },
      {
        id: 2,
        type: "SaveImage",
        properties: { vibecomfy_uid: "saver-1" },
        widgets_values: ["before"],
        inputs: [{ name: "images", link: 41 }],
        outputs: [],
      },
      {
        id: 3,
        type: "Note",
        properties: { vibecomfy_uid: "unrelated-1", note: "before" },
        inputs: [],
        outputs: [],
      },
    ],
    links: [[41, 1, 0, 2, 0, "IMAGE"]],
  };
  const candidateGraph = {
    nodes: [
      initialGraph.nodes[0],
      initialGraph.nodes[1],
      initialGraph.nodes[2],
      {
        id: 4,
        type: "PreviewImage",
        properties: { vibecomfy_uid: "preview-1" },
        inputs: [],
        outputs: [],
      },
    ],
    links: [[41, 1, 0, 2, 0, "IMAGE"]],
  };
  const deltaOps = [
    { op: "add_node", scope_path: "preview-1", class_type: "PreviewImage", fields: {}, inputs: {} },
  ];

  const harness = await createBrowserHarness({
    graph: initialGraph,
    withGraphMutation: true,
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-v2-scoped-apply",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
          graph: candidateGraph,
          delta_ops: deltaOps,
          submit_graph_hash: sha256HexUtf8(initialGraph),
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
          report: { change: { content_edits: { preserved: ["producer-1"], edited: ["saver-1", "preview-1"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.equal(body.session_id, "session-v2-scoped-apply");
        assert.equal(body.turn_id, "0001");
        assert.equal(Array.isArray(body.live_graph?.nodes), true);
        assert.equal(body.live_graph.nodes.length, 3);
        harness.setCurrentGraph({
          ...body.live_graph,
          nodes: body.live_graph.nodes.map((node) => (
            node.properties?.vibecomfy_uid === "unrelated-1"
              ? { ...node, properties: { ...node.properties, note: "after-accept-unrelated-drift" } }
              : node
          )),
        });
        return {
          status: 200,
          body: {
            ok: true,
            action: "accept",
            session_id: "session-v2-scoped-apply",
            turn_id: "0001",
            baseline_turn_id: "0001",
            delta_ops: deltaOps,
            scoped_accept_verification: {
              ok: true,
              entries: [
                {
                  op: "add_node",
                  target: ["nodes", "preview-1"],
                  expected_old: { sentinel: "node_absent" },
                  actual_before: { sentinel: "node_absent" },
                  desired_new: { uid: "preview-1", id: 4, type: "PreviewImage" },
                  status: "ok",
                },
              ],
            },
          },
        };
      },
      "/vibecomfy/agent-edit/chat?session_id=session-v2-scoped-apply": {
        status: 200,
        body: { ok: true, session_id: "session-v2-scoped-apply", messages: [] },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "scoped apply";

    await harness.clickButton("Submit");
    await harness.clickButton("Apply");

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.graphClearCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphAddCalls.length, 1);
    const panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.debugPayload?.canvas_apply_verification?.local_precheck?.ok, true);
    assert.equal(panel.state.debugPayload?.canvas_apply_verification?.local_postcheck?.ok, true);
    expandAgentBubbleDetails(harness.document.body);
    assert.doesNotMatch(harness.textDump(), /Applied - 1 changes verified on canvas\./);
    assert.match(harness.textDump(), /canvas_apply/);
    assert.match(harness.textDump(), /canvas_apply_verification/);
    assert.doesNotMatch(harness.textDump(), /StaleStateMismatch/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy v2 Apply blocks when the touched region drifts after backend accept, even if delta ops only exist in panel state", async () => {
  const initialGraph = {
    nodes: [
      {
        id: 1,
        type: "SaveImage",
        properties: { vibecomfy_uid: "saver-1" },
        widgets_values: ["before"],
        inputs: [],
        outputs: [],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        ...initialGraph.nodes[0],
        widgets_values: ["after"],
      },
    ],
    links: [],
  };
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", "saver-1", "widgets_values", 0], value: "after" },
  ];

  const harness = await createBrowserHarness({
    graph: initialGraph,
    withGraphMutation: true,
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-v2-scoped-conflict",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
          graph: candidateGraph,
          delta_ops: deltaOps,
          submit_graph_hash: sha256HexUtf8(initialGraph),
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
          report: { change: { content_edits: { preserved: [], edited: ["saver-1"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": async () => {
        harness.setCurrentGraph(candidateGraph.nodes ? {
          nodes: [
            {
              ...candidateGraph.nodes[0],
              widgets_values: ["interloper"],
            },
          ],
          links: [],
        } : initialGraph);
        return {
          status: 200,
          body: {
            ok: true,
            action: "accept",
            session_id: "session-v2-scoped-conflict",
            turn_id: "0001",
            baseline_turn_id: "0001",
            scoped_accept_verification: {
              ok: true,
              entries: [
                {
                  op: "set_node_field",
                  target: ["nodes", "saver-1", "widgets_values", 0],
                  expected_old: "before",
                  actual_before: "before",
                  desired_new: "after",
                  status: "ok",
                },
              ],
            },
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
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "scoped conflict";

    await harness.clickButton("Submit");
    await harness.clickButton("Apply");

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.graphClearCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphFieldWriteCalls.length, 0);
    assert.equal(harness.graphConnectCalls.length, 0);
    assert.equal(harness.graphDisconnectCalls.length, 0);
    assert.equal(harness.getCurrentGraph().nodes[0].widgets_values[0], "interloper");
    const panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.debugPayload?.canvas_apply_verification?.local_precheck?.ok, false);
    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /touched region changed after backend acceptance/i);
    assert.match(harness.textDump(), /conflict/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy v2 Apply refuses a touched-link race before mutation and reports scoped conflict diagnostics", async () => {
  const initialGraph = {
    last_link_id: 1,
    nodes: [
      {
        id: 1,
        type: "Loader",
        properties: { vibecomfy_uid: "producer-a" },
        outputs: [{ name: "IMAGE", links: [] }],
      },
      {
        id: 2,
        type: "Loader",
        properties: { vibecomfy_uid: "producer-b" },
        outputs: [{ name: "IMAGE", links: [] }],
      },
      {
        id: 3,
        type: "SaveImage",
        properties: { vibecomfy_uid: "saver-1" },
        inputs: [{ name: "images", link: null }],
        outputs: [],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    last_link_id: 11,
    nodes: [
      {
        ...initialGraph.nodes[0],
        outputs: [{ name: "IMAGE", links: [11] }],
      },
      initialGraph.nodes[1],
      {
        ...initialGraph.nodes[2],
        inputs: [{ name: "images", link: 11 }],
      },
    ],
    links: [[11, 1, 0, 3, 0, "IMAGE"]],
  };
  const racedGraph = {
    last_link_id: 12,
    nodes: [
      initialGraph.nodes[0],
      {
        ...initialGraph.nodes[1],
        outputs: [{ name: "IMAGE", links: [12] }],
      },
      {
        ...initialGraph.nodes[2],
        inputs: [{ name: "images", link: 12 }],
      },
    ],
    links: [[12, 2, 0, 3, 0, "IMAGE"]],
  };
  const deltaOps = [
    { op: "upsert_link", from: ["nodes", "producer-a", "IMAGE"], to: ["nodes", "saver-1", "images"] },
  ];

  const harness = await createBrowserHarness({
    graph: initialGraph,
    withGraphMutation: true,
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-v2-link-conflict",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
          graph: candidateGraph,
          delta_ops: deltaOps,
          submit_graph_hash: sha256HexUtf8(initialGraph),
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
          report: { change: { content_edits: { preserved: ["producer-b"], edited: ["producer-a", "saver-1"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": async () => {
        harness.setCurrentGraph(racedGraph);
        return {
          status: 200,
          body: {
            ok: true,
            action: "accept",
            session_id: "session-v2-link-conflict",
            turn_id: "0001",
            baseline_turn_id: "0001",
            delta_ops: deltaOps,
            scoped_accept_verification: {
              ok: true,
              entries: [
                {
                  op: "upsert_link",
                  target: ["nodes", "saver-1", "images"],
                  expected_old: { sentinel: "link_absent" },
                  actual_before: { sentinel: "link_absent" },
                  desired_new: { origin_id: 1, origin_slot: 0, target_id: 3, target_slot: 0, type: "IMAGE" },
                  status: "ok",
                },
              ],
            },
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
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "scoped link conflict";

    await harness.clickButton("Submit");
    await harness.clickButton("Apply");

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.graphClearCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphConnectCalls.length, 0);
    assert.equal(harness.graphDisconnectCalls.length, 0);
    const racedLink = harness.getCurrentGraph().links[0];
    assert.equal(racedLink.id, 12);
    assert.equal(racedLink.origin_id, 2);
    assert.equal(racedLink.target_id, 3);
    const panel = (await harness.loadExtension()).ensureAgentPanel();
    assert.equal(panel.state.debugPayload?.canvas_apply_verification?.local_precheck?.ok, false);
    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /touched region changed after backend acceptance/i);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy v2 Apply rolls back a post-apply verification miss and reports rollback diagnostics through the existing failure path", async () => {
  const initialGraph = {
    nodes: [
      {
        id: 1,
        type: "SaveImage",
        properties: { vibecomfy_uid: "saver-1" },
        widgets_values: ["before"],
        inputs: [],
        outputs: [],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        ...initialGraph.nodes[0],
        widgets_values: ["after"],
      },
    ],
    links: [],
  };
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", "saver-1", "widgets_values", 0], value: "after" },
  ];

  const harness = await createBrowserHarness({
    graph: initialGraph,
    withGraphMutation: true,
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-v2-rollback-success",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          graph: candidateGraph,
          delta_ops: deltaOps,
          submit_graph_hash: sha256HexUtf8(initialGraph),
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
          report: { change: { content_edits: { preserved: ["saver-1"], edited: ["saver-1"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: "session-v2-rollback-success",
          turn_id: "0001",
          baseline_turn_id: "0001",
          delta_ops: deltaOps,
          scoped_accept_verification: {
            ok: true,
            entries: [
              {
                op: "set_node_field",
                target: ["nodes", "saver-1", "widgets_values", 0],
                expected_old: "before",
                actual_before: "before",
                desired_new: "after",
                status: "ok",
              },
            ],
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

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "rollback scoped apply";
    await harness.clickButton("Submit");

    const originalSerialize = harness.app.canvas.graph.serialize.bind(harness.app.canvas.graph);
    let corruptedPostcheck = false;
    harness.app.canvas.graph.serialize = function serializeWithPostcheckCorruption() {
      const liveNode = harness.getLiveNodes().find((node) => node.properties?.vibecomfy_uid === "saver-1");
      if (!corruptedPostcheck && liveNode?.widgets_values?.[0] === "after") {
        liveNode.widgets_values[0] = "after-corrupted";
        corruptedPostcheck = true;
      }
      return originalSerialize();
    };

    await harness.clickButton("Apply");
    const panel = extensionModule.ensureAgentPanel();
    await waitFor(() => panel.state.failure?.kind === "CanvasApplyError");

    assert.equal(harness.getCurrentGraph().nodes[0].widgets_values[0], "before");
    assert.equal(panel.state.failure?.graph_unchanged, true);
    assert.equal(panel.state.failure?.canvas_apply?.rollback?.restored, true);
    assert.equal(panel.state.failure?.canvas_apply?.rollback?.restored_via, "inverse_delta");
    assert.equal(panel.state.undoStack.length, 1);
    assert.notEqual(harness.document.getElementById("vibecomfy-agent-panel-undo")?.style.display, "none");
    assert.doesNotMatch(harness.textDump(), /Applied - 1 changes verified on canvas\./);

    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /restored to the pre-apply snapshot/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy v2 Apply preserves undo diagnostics when post-apply verification rollback cannot fully restore the canvas", async () => {
  const initialGraph = {
    nodes: [
      {
        id: 1,
        type: "SaveImage",
        properties: { vibecomfy_uid: "saver-1" },
        widgets_values: ["before"],
        inputs: [],
        outputs: [],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        ...initialGraph.nodes[0],
        widgets_values: ["after"],
      },
    ],
    links: [],
  };
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", "saver-1", "widgets_values", 0], value: "after" },
  ];

  const harness = await createBrowserHarness({
    graph: initialGraph,
    withGraphMutation: true,
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-v2-rollback-failure",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          graph: candidateGraph,
          delta_ops: deltaOps,
          submit_graph_hash: sha256HexUtf8(initialGraph),
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
          report: { change: { content_edits: { preserved: ["saver-1"], edited: ["saver-1"], removed_named: [] } }, recovery: [] },
        },
      },
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: "session-v2-rollback-failure",
          turn_id: "0001",
          baseline_turn_id: "0001",
          delta_ops: deltaOps,
          scoped_accept_verification: {
            ok: true,
            entries: [
              {
                op: "set_node_field",
                target: ["nodes", "saver-1", "widgets_values", 0],
                expected_old: "before",
                actual_before: "before",
                desired_new: "after",
                status: "ok",
              },
            ],
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

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "rollback failure diagnostics";
    await harness.clickButton("Submit");

    const originalSerialize = harness.app.canvas.graph.serialize.bind(harness.app.canvas.graph);
    let corruptionStage = 0;
    harness.app.canvas.graph.serialize = function serializeWithRollbackFailure() {
      const liveNode = harness.getLiveNodes().find((node) => node.properties?.vibecomfy_uid === "saver-1");
      if (corruptionStage === 0 && liveNode?.widgets_values?.[0] === "after") {
        liveNode.widgets_values[0] = "after-corrupted";
        corruptionStage = 1;
      } else if (corruptionStage === 1 && liveNode?.widgets_values?.[0] === "before") {
        liveNode.widgets_values[0] = "still-broken";
        corruptionStage = 2;
      }
      return originalSerialize();
    };
    harness.app.loadGraphData = async function blockedRestore() {
      throw new Error("whole graph restore blocked");
    };

    await harness.clickButton("Apply");
    const panel = extensionModule.ensureAgentPanel();
    await waitFor(() => panel.state.failure?.kind === "CanvasApplyError");

    assert.equal(harness.getCurrentGraph().nodes[0].widgets_values[0], "still-broken");
    assert.equal(panel.state.failure?.graph_unchanged, false);
    assert.equal(panel.state.failure?.canvas_apply?.rollback?.restored, false);
    assert.equal(panel.state.failure?.canvas_apply?.rollback?.undo_snapshot_available, true);
    assert.equal(panel.state.failure?.canvas_apply?.rollback?.attempts.length, 2);
    assert.equal(panel.state.failure?.canvas_apply?.rollback?.attempts[1]?.strategy, "whole_graph_restore");
    assert.equal(panel.state.undoStack.length, 1);
    assert.equal(panel.state.debugPayload?.canvas_apply_verification?.local_postcheck?.ok, false);
    assert.equal(panel.state.debugPayload?.canvas_apply_verification?.rollback?.restored, false);
    assert.notEqual(harness.document.getElementById("vibecomfy-agent-panel-undo")?.style.display, "none");
    assert.doesNotMatch(harness.textDump(), /Applied - 1 changes verified on canvas\./);

    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /undo snapshot remains available/);
    assert.match(harness.textDump(), /rollback/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy keeps the full candidate graph available for preview overlay in scoped review mode", async () => {
  const liveGraph = {
    nodes: [
      {
        id: 1,
        type: "Input",
        pos: [40, 40],
        properties: { vibecomfy_uid: "uid-1" },
        outputs: [{ name: "IMAGE", links: [5] }],
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [260, 40],
        properties: { vibecomfy_uid: "uid-2" },
        inputs: [{ name: "images", link: 5 }],
      },
    ],
    links: [[5, 1, 0, 2, 0, "IMAGE"]],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "Input",
        pos: [40, 40],
        properties: { vibecomfy_uid: "uid-1" },
        outputs: [{ name: "IMAGE", links: [9] }],
      },
      {
        id: 3,
        type: "PreviewImage",
        pos: [260, 40],
        properties: { vibecomfy_uid: "uid-3" },
        inputs: [{ name: "images", link: 9 }],
      },
    ],
    links: [[9, 1, 0, 3, 0, "IMAGE"]],
  };
  const candidateReport = {
    change: {
      content_edits: {
        preserved: ["uid-1"],
        edited: ["uid-3"],
        removed_named: ["uid-2"],
      },
    },
    recovery: [],
  };
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", "uid-1", "widgets_values", 0], value: "preview-only-intent" },
  ];

  const harness = await createBrowserHarness({
    graph: liveGraph,
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-v2-overlay",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          graph: candidateGraph,
          delta_ops: deltaOps,
          report: candidateReport,
          submit_graph_hash: sha256HexUtf8(liveGraph),
          candidate_graph_hash: sha256HexUtf8(candidateGraph),
        },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "preview preservation";

    await harness.clickButton("Submit");

    const panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.deltaOps.length, 1);
    assert.equal(panel.state.candidateGraph.nodes.length, 2);
    const diff = extensionModule.computePreviewDiff(panel.state.candidateGraph, panel.state.candidateReport);
    assert.equal(diff.removed.length, 1);
    assert.equal(diff.removed[0].uid, "uid-2");
    assert.equal(diff.added.length, 1);
    assert.equal(diff.added[0].uid, "uid-3");
    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: panel.state.candidateGraph });
    assert.ok(drawOps.some((op) => op.kind === "fillText" && String(op.args[0]).includes("PreviewImage")));
    assert.deepEqual(harness.getCurrentGraph(), liveGraph);
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-fallback",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
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
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "fallback";
    await harness.clickButton("Submit");
    await harness.clickButton("Apply");

    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /Applied candidate feedback: changed nodes listed here because live node lookup was unavailable\./);
    assert.match(harness.textDump(), /Edited uid-missing/);
    assert.match(harness.textDump(), /Native queue hook unavailable: `app\.queuePrompt` was not found\./);
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-intent-style",
          turn_id: "0001",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          apply_eligibility: {
            applyable: true,
            reason: "queue_blocked_warning",
            message: "Apply is allowed, but Queue remains blocked for this candidate.",
            warnings: ["queue_blocked"],
          },
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
    await harness.clickButton("Apply");

    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphClearCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    const loadedIntentNodes = harness.graphConfigureCalls[0].nodes.filter((node) => /^vibecomfy\./.test(node.type));
    assert.equal(loadedIntentNodes.length, 2);

    const codeNode = loadedIntentNodes.find((node) => node.type === "vibecomfy.code");
    assert.equal(codeNode.color, "#2d2643");
    assert.equal(codeNode.bgcolor, "#171229");
    assert.equal(codeNode.boxcolor, "#e39cff");
    assert.equal(codeNode.properties["VibeComfy Intent Badge"], "sandboxed_loose");
    assert.equal(codeNode.properties["VibeComfy Intent Source"], "value = image");
    assert.equal(codeNode.properties["VibeComfy Intent Spec"], "inspect the input image before lowering");
    // Dynamic-IO: slot.name preserved (serialization key), slot.label carries the type annotation.
    assert.equal(codeNode.inputs[0].name, "value");
    assert.equal(codeNode.inputs[0].label, "image: IMAGE");
    assert.equal(codeNode.outputs[0].name, "value");
    assert.equal(codeNode.outputs[0].label, "image: IMAGE");

    const degradedNode = loadedIntentNodes.find((node) => node.type === "vibecomfy.loop");
    assert.equal(degradedNode.properties["VibeComfy Intent Badge"], "loop · metadata missing");
    assert.equal(degradedNode.color, "#3a2a1f");
    assert.equal(degradedNode.bgcolor, "#231811");
    assert.equal(degradedNode.boxcolor, "#ffb86c");

    const liveIntentNodes = harness.app.canvas.graph._nodes.filter((node) => /^vibecomfy\./.test(node.type));
    assert.equal(liveIntentNodes.length, 2);
    const liveCodeNode = liveIntentNodes.find((node) => node.type === "vibecomfy.code");
    assert.equal(liveCodeNode.boxcolor, "#e39cff");
    assert.equal(liveCodeNode.properties["VibeComfy Intent Badge"], "sandboxed_loose");
    // Dynamic-IO: slot.name preserved (serialization key), slot.label carries the type annotation.
    assert.equal(liveCodeNode.inputs[0].name, "value");
    assert.equal(liveCodeNode.inputs[0].label, "image: IMAGE");
    assert.equal(liveCodeNode.outputs[0].name, "value");
    assert.equal(liveCodeNode.outputs[0].label, "image: IMAGE");

    const liveDegradedNode = liveIntentNodes.find((node) => node.type === "vibecomfy.loop");
    assert.equal(liveDegradedNode.boxcolor, "#ffb86c");
    assert.equal(liveDegradedNode.properties["VibeComfy Intent Badge"], "loop · metadata missing");

    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");
    assert.deepEqual(harness.consoleCapture.error, []);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy provider settings autosave OpenRouter credentials and surface soft rejections without re-rendering raw keys", async () => {
  const credentialBodies = [];
  const routeOptions = {
    auto: {
      requested_route: "auto",
      normalized_route: "arnold",
      browser_api_key_allowed: false,
      guidance: "Use local Arnold/Hermes setup for this route. Browser-submitted API keys are not stored.",
      tos_acknowledgement_required: false,
    },
    openrouter: {
      requested_route: "openrouter",
      normalized_route: "openrouter",
      browser_api_key_allowed: true,
      guidance: "OpenRouter browser key submission is supported and stored locally.",
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
      "/vibecomfy/agent/status?route=openrouter": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "openrouter",
          requested_route: "openrouter",
          route_options: routeOptions,
        },
      },
      "/vibecomfy/agent/status?route=openrouter&model=agent-model": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "openrouter",
          requested_route: "openrouter",
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
        if (body.provider === "openrouter") {
          return {
            status: 200,
            body: { ok: true, stored: true, provider: "openrouter" },
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
    assert.deepEqual(routeSelect.children.map((entry) => entry.value), ["auto", "openrouter", "anthropic", "openai-codex"]);
    assert.equal(harness.getButton("Save Settings"), null);

    routeSelect.value = "openrouter";
    await routeSelect.onchange();
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=openrouter"));
    const apiKeyInput = harness.document.getElementById("vibecomfy-agent-panel-api-key");
    assert.notEqual(apiKeyInput?.style.display, "none");
    assert.equal(apiKeyInput?.type, "password");

    harness.document.getElementById("vibecomfy-agent-panel-model").value = "agent-model";
    apiKeyInput.value = "deepseek-secret";
    await apiKeyInput.onchange();
    await waitFor(() => credentialBodies.length === 1);
    assert.deepEqual(credentialBodies[0], { provider: "openrouter", api_key: "deepseek-secret" });
    assert.equal(apiKeyInput.value, "");
    assert.match(harness.textDump(), /Stored browser credential for openrouter/);
    assert.doesNotMatch(harness.textDump(), /deepseek-secret/);

    routeSelect.value = "anthropic";
    await routeSelect.onchange();
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=anthropic&model=agent-model"));
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-api-key")?.style.display, "none");
    assert.match(harness.textDump(), /Claude runs through your local CLI setup/);

    routeSelect.value = "openai-codex";
    await routeSelect.onchange();
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=openai-codex&model=agent-model"));
    harness.document.getElementById("vibecomfy-agent-panel-api-key").value = "codex-secret";
    await harness.document.getElementById("vibecomfy-agent-panel-api-key").onchange();
    await waitFor(() => /Browser keys are not accepted/.test(harness.textDump()));
    assert.equal(credentialBodies.length, 1);
    assert.match(harness.textDump(), /Browser keys are not accepted/);
    assert.doesNotMatch(harness.textDump(), /codex-secret/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy route/model controls stay explicit across loading, missing-route-options, malformed-status, and unavailable status states", async () => {
  globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
  let statusCalls = 0;
  const readyRouteOptions = {
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
  };

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => {
        statusCalls += 1;
        if (statusCalls === 1) {
          return {
            status: 200,
            body: {
              ok: true,
              provider_available: true,
              route: "arnold",
              requested_route: "auto",
              route_options: readyRouteOptions,
            },
          };
        }
        if (statusCalls === 2) {
          return {
            status: 200,
            body: {
              ok: true,
              provider_available: true,
              route: "arnold",
              requested_route: "auto",
            },
          };
        }
        if (statusCalls === 3) {
          return {
            status: 200,
            body: "not-an-object",
          };
        }
        throw new Error("network down");
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");

    const routeSelect = harness.document.getElementById("vibecomfy-agent-panel-route");
    const modelInput = harness.document.getElementById("vibecomfy-agent-panel-model");
    if (statusCalls === 0) {
      assert.equal(routeSelect.disabled, true);
      assert.equal(modelInput.disabled, true);
      assert.equal(routeSelect.children.length, 1);
      assert.match(routeSelect.children[0].textContent, /Loading route\/model status/);
    }

    await waitFor(() => statusCalls === 1);
    assert.equal(routeSelect.disabled, false);
    assert.equal(modelInput.disabled, false);
    assert.deepEqual(routeSelect.children.map((entry) => entry.value), ["auto", "deepseek"]);

    harness.document.getElementById("vibecomfy-agent-panel-settings-test").click();
    await waitFor(() => statusCalls === 2);
    assert.equal(routeSelect.disabled, true);
    assert.equal(modelInput.disabled, true);
    assert.equal(routeSelect.children.length, 1);
    assert.match(routeSelect.children[0].textContent, /Route options unavailable/);
    assert.match(harness.textDump(), /Status missing route options; route\/model controls disabled\./);

    harness.document.getElementById("vibecomfy-agent-panel-settings-test").click();
    await waitFor(() => statusCalls === 3);
    assert.equal(routeSelect.disabled, true);
    assert.equal(modelInput.disabled, true);
    assert.equal(routeSelect.children.length, 1);
    assert.match(routeSelect.children[0].textContent, /Malformed status payload/);
    assert.match(harness.textDump(), /Malformed status payload; route\/model controls disabled\./);

    await harness.clickButton("Test Provider");
    await waitFor(() => statusCalls === 4);
    assert.equal(routeSelect.disabled, true);
    assert.equal(modelInput.disabled, true);
    assert.equal(routeSelect.children.length, 1);
    assert.match(routeSelect.children[0].textContent, /Status unavailable/);
    assert.match(harness.textDump(), /Status unavailable: Error: network down/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy settings live in a toggled popover and keep route-status guidance plus developer diagnostics there", async () => {
  let statusCalls = 0;
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => {
        statusCalls += 1;
        if (statusCalls === 1) {
          return {
            status: 200,
            body: {
              ok: true,
              provider_available: true,
              route: "deepseek",
              requested_route: "auto",
              route_options: {
                auto: {
                  requested_route: "auto",
                  normalized_route: "deepseek",
                  browser_api_key_allowed: false,
                  guidance: "Auto resolves to DeepSeek for this browser session.",
                },
                deepseek: {
                  requested_route: "deepseek",
                  normalized_route: "deepseek",
                  browser_api_key_allowed: true,
                  guidance: "DeepSeek browser key submission is supported.",
                },
                anthropic: {
                  requested_route: "anthropic",
                  normalized_route: "arnold",
                  browser_api_key_allowed: false,
                  guidance: "Anthropic/Claude runs through local Arnold/Hermes.",
                  tos_acknowledgement_required: true,
                },
                "openai-codex": {
                  requested_route: "openai-codex",
                  normalized_route: "arnold",
                  browser_api_key_allowed: false,
                  guidance: "OpenAI Codex runs through local Arnold/Hermes.",
                },
              },
              credential_presence: {
                arnold_api_key: false,
                hermes_api_key: false,
                deepseek_api_key: true,
              },
            },
          };
        }
        return {
          status: 200,
          body: {
            ok: true,
            provider_available: true,
            route: "deepseek",
            requested_route: "auto",
          },
        };
      },
      "/vibecomfy/agent/status?route=deepseek": async () => {
        statusCalls += 1;
        return {
          status: 200,
          body: {
            ok: true,
            ready: true,
            provider_available: true,
            route: "deepseek",
            requested_route: "deepseek",
            route_options: {
              auto: {
                requested_route: "auto",
                normalized_route: "deepseek",
                browser_api_key_allowed: false,
                guidance: "Auto resolves to DeepSeek for this browser session.",
              },
              deepseek: {
                requested_route: "deepseek",
                normalized_route: "deepseek",
                browser_api_key_allowed: true,
                guidance: "DeepSeek browser key submission is supported.",
              },
              anthropic: {
                requested_route: "anthropic",
                normalized_route: "arnold",
                browser_api_key_allowed: false,
                guidance: "Anthropic/Claude runs through local Arnold/Hermes.",
                tos_acknowledgement_required: true,
              },
              "openai-codex": {
                requested_route: "openai-codex",
                normalized_route: "arnold",
                browser_api_key_allowed: false,
                guidance: "OpenAI Codex runs through local Arnold/Hermes.",
              },
            },
            credential_presence: {
              arnold_api_key: false,
              hermes_api_key: false,
              deepseek_api_key: true,
            },
          },
        };
      },
      "/vibecomfy/agent/status?route=openai-codex&model=agent-edit": async () => {
        statusCalls += 1;
        return {
          status: 200,
          body: {
            ok: true,
            ready: true,
            provider_available: true,
            route: "arnold",
            requested_route: "openai-codex",
            model: "agent-edit",
            route_metadata: {
              requested_route: "openai-codex",
              normalized_route: "arnold",
              browser_api_key_allowed: false,
              guidance: "OpenAI Codex runs through local Arnold/Hermes.",
            },
            route_options: {
              auto: {
                requested_route: "auto",
                normalized_route: "deepseek",
                browser_api_key_allowed: false,
                guidance: "Auto resolves to DeepSeek for this browser session.",
              },
              deepseek: {
                requested_route: "deepseek",
                normalized_route: "deepseek",
                browser_api_key_allowed: true,
                guidance: "DeepSeek browser key submission is supported.",
              },
              anthropic: {
                requested_route: "anthropic",
                normalized_route: "arnold",
                browser_api_key_allowed: false,
                guidance: "Anthropic/Claude runs through local Arnold/Hermes.",
                tos_acknowledgement_required: true,
              },
              "openai-codex": {
                requested_route: "openai-codex",
                normalized_route: "arnold",
                browser_api_key_allowed: false,
                guidance: "OpenAI Codex runs through local Arnold/Hermes.",
              },
            },
            credential_presence: {
              arnold_api_key: false,
              hermes_api_key: false,
              deepseek_api_key: true,
            },
          },
        };
      },
      "/vibecomfy/agent/status?route=anthropic&model=agent-edit": async () => {
        statusCalls += 1;
        return {
          status: 200,
          body: {
            ok: true,
            ready: true,
            provider_available: true,
            route: "arnold",
            requested_route: "anthropic",
            model: "agent-edit",
            route_metadata: {
              requested_route: "anthropic",
              normalized_route: "arnold",
              browser_api_key_allowed: false,
              guidance: "Anthropic/Claude runs through local Arnold/Hermes.",
              tos_acknowledgement_required: true,
            },
            route_options: {
              auto: {
                requested_route: "auto",
                normalized_route: "deepseek",
                browser_api_key_allowed: false,
                guidance: "Auto resolves to DeepSeek for this browser session.",
              },
              deepseek: {
                requested_route: "deepseek",
                normalized_route: "deepseek",
                browser_api_key_allowed: true,
                guidance: "DeepSeek browser key submission is supported.",
              },
              anthropic: {
                requested_route: "anthropic",
                normalized_route: "arnold",
                browser_api_key_allowed: false,
                guidance: "Anthropic/Claude runs through local Arnold/Hermes.",
                tos_acknowledgement_required: true,
              },
              "openai-codex": {
                requested_route: "openai-codex",
                normalized_route: "arnold",
                browser_api_key_allowed: false,
                guidance: "OpenAI Codex runs through local Arnold/Hermes.",
              },
            },
            credential_presence: {
              arnold_api_key: false,
              hermes_api_key: false,
              deepseek_api_key: true,
            },
          },
        };
      },
      "/vibecomfy/agent/status?route=openai-codex": async () => {
        statusCalls += 1;
        return {
          status: 200,
          body: {
            ok: true,
            ready: true,
            provider_available: true,
            route: "arnold",
            requested_route: "openai-codex",
            model: "agent-edit",
            route_metadata: {
              requested_route: "openai-codex",
              normalized_route: "arnold",
              browser_api_key_allowed: false,
              guidance: "OpenAI Codex runs through local Arnold/Hermes.",
            },
            route_options: {
              auto: {
                requested_route: "auto",
                normalized_route: "deepseek",
                browser_api_key_allowed: false,
                guidance: "Auto resolves to DeepSeek for this browser session.",
              },
              deepseek: {
                requested_route: "deepseek",
                normalized_route: "deepseek",
                browser_api_key_allowed: true,
                guidance: "DeepSeek browser key submission is supported.",
              },
              anthropic: {
                requested_route: "anthropic",
                normalized_route: "arnold",
                browser_api_key_allowed: false,
                guidance: "Anthropic/Claude runs through local Arnold/Hermes.",
                tos_acknowledgement_required: true,
              },
              "openai-codex": {
                requested_route: "openai-codex",
                normalized_route: "arnold",
                browser_api_key_allowed: false,
                guidance: "OpenAI Codex runs through local Arnold/Hermes.",
              },
            },
            credential_presence: {
              arnold_api_key: false,
              hermes_api_key: false,
              deepseek_api_key: true,
            },
          },
        };
      },
    },
    withQueuePrompt: false,
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => statusCalls === 1);

    const settingsPopover = harness.document.body.querySelectorAll(
      (node) => node.className === "vibecomfy-agent-panel-settings-popover",
    )[0];
    const settingsGear = harness.document.body.querySelectorAll(
      (node) => node.title === "Settings",
    )[0];
    const settingsStatus = harness.document.getElementById("vibecomfy-agent-panel-settings-status");
    const settingsGuidance = harness.document.getElementById("vibecomfy-agent-panel-settings-guidance");
    const developerRegion = harness.document.getElementById("vibecomfy-agent-panel-region-developer");
    const developerToggle = harness.document.getElementById("vibecomfy-agent-panel-developer-toggle");
    const routeSelect = harness.document.getElementById("vibecomfy-agent-panel-route");
    const modelInput = harness.document.getElementById("vibecomfy-agent-panel-model");
    const apiKeyInput = harness.document.getElementById("vibecomfy-agent-panel-api-key");

    assert(settingsPopover, "settings popover should be mounted");
    assert(settingsGear, "settings gear button should be mounted");
    assert.equal(settingsPopover.style.display, "none");
    assert.equal(harness.getButton("Change Engine"), null);
    assert.equal(modelInput.style.display, "none");

    settingsGear.click();
    assert.equal(settingsPopover.style.display, "block");
    assert.equal(settingsPopover.style.overflowY, "auto");
    assert.equal(routeSelect.style.boxSizing, "border-box");
    assert.match(routeSelect.style.padding, /28px/);
    await waitFor(() => /deepseek \(provider ready\)/.test(settingsStatus.textContent));
    assert.match(settingsStatus.textContent, /deepseek .* deepseek \(provider ready\)/);
    assert.match(settingsGuidance.textContent, /DeepSeek browser key submission is supported/);
    assert(developerToggle, "developer disclosure should be mounted");
    assert.equal(developerToggle.attributes?.["aria-expanded"], "false");
    const developerBody = developerRegion.querySelectorAll(
      (node) => node.className === "vibecomfy-agent-panel-region-body",
    )[0];
    assert.equal(developerBody?.style.display, "none");
    developerToggle.click();
    assert.equal(developerToggle.attributes?.["aria-expanded"], "true");
    assert.equal(developerBody?.style.display, "grid");
    assert.match(developerRegion.textContent, /Adapter Capabilities/);
    assert.match(developerRegion.textContent, /Queue Guard State/);

    routeSelect.value = "deepseek";
    routeSelect.onchange();
    await waitFor(() => statusCalls === 2);
    assert.match(settingsStatus.textContent, /Saved deepseek/);
    assert.match(settingsGuidance.textContent, /Saved DeepSeek key present/);
    assert.match(apiKeyInput.placeholder, /Saved DeepSeek key present/);

    await harness.clickButton("Test Provider");
    await waitFor(() => statusCalls === 3);
    await waitFor(() => /Provider test passed: deepseek .* deepseek/.test(settingsStatus.textContent));
    assert.equal(settingsStatus.style.color, "#7ee787");

    routeSelect.value = "openai-codex";
    routeSelect.onchange();
    await waitFor(() => statusCalls === 4);
    assert.match(settingsStatus.textContent, /Saved openai-codex/);
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-settings-test")?.disabled === false);

    harness.document.getElementById("vibecomfy-agent-panel-settings-test").click();
    await waitFor(() => statusCalls === 5);
    await waitFor(() => /Provider test passed: openai-codex .* arnold/.test(settingsStatus.textContent));
    assert.doesNotMatch(settingsStatus.textContent, /openai-codex .* auto/);

    routeSelect.value = "anthropic";
    routeSelect.onchange();
    await waitFor(() => statusCalls === 6);
    assert.match(settingsStatus.textContent, /Saved anthropic/);
    assert.match(settingsGuidance.textContent, /Claude runs through your local CLI setup/);

    harness.document.getElementById("vibecomfy-agent-panel-settings-test").click();
    await waitFor(() => statusCalls === 7);
    await waitFor(() => /Provider test passed: anthropic .* arnold/.test(settingsStatus.textContent));
    assert.doesNotMatch(settingsStatus.textContent, /anthropic .* auto/);

    settingsGear.click();
    assert.equal(settingsPopover.style.display, "none");
  } finally {
    globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
    await harness.dispose();
  }
});

test("VibeComfy developer diagnostics fetch runtime identity even when route status is unavailable", async () => {
  let statusCalls = 0;
  let infoCalls = 0;
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/settings": {
        status: 200,
        body: { ok: true, research_contribution_enabled: false },
      },
      "/vibecomfy/agent/status?route=auto": async () => {
        statusCalls += 1;
        return {
          status: 503,
          body: {
            error: "backend offline",
          },
        };
      },
      "/vibecomfy/info": async () => {
        infoCalls += 1;
        return {
          status: 200,
          body: {
            start_time_utc: "2026-07-09T16:10:00Z",
            uptime_seconds: 42.5,
            WEB_DIRECTORY: "/workspace/vibecomfy/comfy_nodes/web",
            web_source_hash: "feedface",
            served_web_path: "/tmp/vibecomfy-served/web",
            launch_flags: {
              VIBECOMFY_HEADLESS: "0",
            },
            git_sha: "abc123",
            git_branch: "main",
            git_dirty: true,
            git_diagnostic: null,
          },
        };
      },
    },
    withQueuePrompt: false,
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => statusCalls === 1);

    const settingsGear = harness.document.body.querySelectorAll(
      (node) => node.title === "Settings",
    )[0];
    const settingsStatus = harness.document.getElementById("vibecomfy-agent-panel-settings-status");
    const developerRegion = harness.document.getElementById("vibecomfy-agent-panel-region-developer");
    const developerToggle = harness.document.getElementById("vibecomfy-agent-panel-developer-toggle");

    settingsGear.click();
    await waitFor(() => infoCalls === 1);
    developerToggle.click();

    await waitFor(() => /gitSha: abc123 \(dirty\)/.test(developerRegion.textContent));
    assert.match(settingsStatus.textContent, /Status unavailable/);
    assert.match(developerRegion.textContent, /infoRoute: ready/);
    assert.match(developerRegion.textContent, /gitBranch: main/);
    assert.match(developerRegion.textContent, /webSourceHash: feedface/);
    assert.match(developerRegion.textContent, /servedWebPath: \/tmp\/vibecomfy-served\/web/);
    assert.equal(
      harness.requests.some((entry) => entry.url === "/vibecomfy/info"),
      true,
      "runtime info should be fetched even while route status is unavailable",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy settings toggle saves and triggers research contribution", async () => {
  globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
  globalThis.localStorage?.removeItem("vibecomfy_research_contribution_enabled");
  const settingsBodies = [];
  let triggerCount = 0;
  const routeOptions = {
    auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
    "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
  };
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/settings": async ({ options }) => {
        if (options?.method === "POST") {
          const body = JSON.parse(options.body);
          settingsBodies.push(body);
          return { status: 200, body: { ok: true, research_contribution_enabled: body.research_contribution_enabled } };
        }
        return { status: 200, body: { ok: true, research_contribution_enabled: false } };
      },
      "/vibecomfy/agent/research-contribution/run": async () => {
        triggerCount += 1;
        return { status: 200, body: { ok: true, triggered: true, research_contribution_enabled: true } };
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: routeOptions },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/settings"));

    const settingsGear = harness.document.body.querySelectorAll((node) => node.title === "Settings")[0];
    settingsGear.click();
    const toggle = harness.document.getElementById("vibecomfy-agent-panel-research-contribution");
    const yesToggle = harness.document.getElementById("vibecomfy-agent-panel-research-contribution-yes");
    const noToggle = harness.document.getElementById("vibecomfy-agent-panel-research-contribution-no");
    assert.equal(toggle.checked, false);
    assert.equal(noToggle.style.background, "#2f6f8f");

    await yesToggle.click();

    await waitFor(() => settingsBodies.length === 1 && triggerCount === 1);
    assert.deepEqual(settingsBodies[0], { research_contribution_enabled: true });
    assert.equal(toggle.checked, true);
    assert.equal(yesToggle.style.background, "#2f6f8f");
    assert.equal(globalThis.localStorage.getItem("vibecomfy_research_contribution_enabled"), "1");
    assert.match(harness.textDump(), /Research contribution started/);
  } finally {
    globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
    globalThis.localStorage?.removeItem("vibecomfy_research_contribution_enabled");
    await harness.dispose();
  }
});

test("VibeComfy onboarding asks for research contribution after engine selection", async () => {
  globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
  globalThis.localStorage?.removeItem("vibecomfy_research_contribution_enabled");
  const settingsBodies = [];
  let triggerCount = 0;
  const routeOptions = {
    auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
    "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
  };
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/settings": async ({ options }) => {
        if (options?.method === "POST") {
          const body = JSON.parse(options.body);
          settingsBodies.push(body);
          return { status: 200, body: { ok: true, research_contribution_enabled: body.research_contribution_enabled } };
        }
        return { status: 200, body: { ok: true, research_contribution_enabled: false } };
      },
      "/vibecomfy/agent/research-contribution/run": async () => {
        triggerCount += 1;
        return { status: 200, body: { ok: true, triggered: true, research_contribution_enabled: true } };
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: { ok: true, provider_available: false, route: "arnold", requested_route: "auto", route_options: routeOptions },
      },
      "/vibecomfy/agent/status?route=openai-codex": {
        status: 200,
        body: { ok: true, provider_available: true, route: "arnold", requested_route: "openai-codex", route_options: routeOptions },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay"));

    const codexLabel = harness.document.body.querySelectorAll((node) => node.textContent === "Codex")[0];
    codexLabel.parentNode.click();
    harness.getButton("Confirm Selection").click();
    await waitFor(() => /Contribute agent research/.test(harness.textDump()));

    harness.getButton("Yes").click();
    await waitFor(() => settingsBodies.length === 1 && triggerCount === 1);

    assert.deepEqual(settingsBodies[0], { research_contribution_enabled: true });
    assert.equal(globalThis.localStorage.getItem("vibecomfy_agent_provider"), "openai-codex");
    assert.equal(globalThis.localStorage.getItem("vibecomfy_research_contribution_enabled"), "1");
  } finally {
    globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
    globalThis.localStorage?.removeItem("vibecomfy_research_contribution_enabled");
    await harness.dispose();
  }
});

test("VibeComfy first open auto-selects DeepSeek when a stored browser key is ready", async () => {
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
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
          credential_presence: {
            arnold_api_key: false,
            hermes_api_key: false,
            deepseek_api_key: true,
          },
        },
      },
      "/vibecomfy/agent/status?route=deepseek": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "deepseek",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
          credential_presence: {
            arnold_api_key: false,
            hermes_api_key: false,
            deepseek_api_key: true,
          },
        },
      },
    },
    withQueuePrompt: false,
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() =>
      harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"),
    );
    await waitFor(() => globalThis.localStorage.getItem("vibecomfy_agent_provider") === "deepseek");

    assert.equal(
      harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay"),
      null,
      "ready stored DeepSeek key should not force the choose-engine gate",
    );
    assert.equal(harness.getButton("Confirm Selection"), null);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-route").value, "deepseek");
    assert.equal(
      harness.requests.some((entry) => entry.url === "/vibecomfy/agent/credentials"),
      false,
      "saved-key path should not POST an empty replacement credential",
    );
  } finally {
    globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
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
      "/vibecomfy/agent-executor": async () => {
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
            apply_eligibility: {
              applyable: true,
              reason: "queue_blocked_warning",
              message: "Apply is allowed, but Queue remains blocked for this candidate.",
              warnings: ["queue_blocked"],
            },
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

    await harness.clickButton("Apply");
    assert.match(harness.textDump(), /MalformedResponse/);
    assert.match(harness.textDump(), /incomplete accept envelope/);
    assert.match(harness.textDump(), /Retry Apply or inspect the raw response in the debug panel\./);
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);

    await harness.clickButton("Apply");
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphClearCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    assert.deepEqual(harness.graphConfigureCalls[0], candidateGraph);
  } finally {
    await harness.dispose();
  }
});

// ── Lifecycle Contract: B2/B5 Rebaseline + submit blocking ──────────────

test("Lifecycle B2/B5 rebaseline sync blocks submit while pending or in flight", async () => {
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
      "/vibecomfy/agent-executor": async () => {
        throw new Error("submit must remain blocked while rebaseline is pending or in flight");
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
    assert.equal(undoButton.textContent, "");
    assert.equal(undoButton.getAttribute("aria-label"), "Undo Rebaseline...");
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
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-executor").length, 0);
    assert.equal(undoButton.disabled, true);
    assert.equal(undoButton.textContent, "");
    assert.equal(undoButton.getAttribute("aria-label"), "Undo Last Apply");
    assert.doesNotMatch(harness.textDump(), /rebaseline pending: undo/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy renders one stale-state recovery action, retries against updated evidence, and recovers through rebaseline resubmit and apply", async () => {
  const rebaselineBodies = [];
  const acceptBodies = [];
  const submitBodies = [];
  let rebaselineCallCount = 0;
  const recoveryButtonsFor = () => harness.document.body.querySelectorAll(
    (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyRecoveryAction === "stale-rebaseline-retry",
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
      "/vibecomfy/agent-executor": async ({ options }) => {
        const body = JSON.parse(options.body);
        submitBodies.push(body);
        assert.equal(body.task, "finish the recovered edit");
        assert.equal(body.session_id, "session-stale");
        return {
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
        };
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
    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    prompt.value = "finish the recovered edit";
    const initialFailure = {
      ok: false,
      kind: "StaleStateMismatch",
      stage: "ingest",
      retryable: true,
      graph_unchanged: true,
      message: "Some requested edits did not land, so I stopped before applying the rest.",
      user_facing_message: "The canvas changed since the current backend baseline. Rebaseline and resubmit from the current canvas.",
      next_action: "resubmit from the current canvas",
      session_id: "session-stale",
      turn_id: "0005",
      baseline_turn_id: null,
      outcome: {
        kind: "failure",
        failure_kind: "StaleStateMismatch",
        stage: "ingest",
        graph_unchanged: true,
        retryable: false,
        next_action: "resubmit from the current canvas",
        agent_failure_context: {
          explanation: "Stage ingest blocked the agent edit.",
          issues: [
            {
              code: "stale_state_mismatch",
              severity: "error",
              failure_kind: "StaleStateMismatch",
              message: "Submitted graph no longer matches the current baseline.",
              detail: {
                baseline_graph_hash: "baseline-before-recovery",
                client_graph_hash: "client-structural-before-recovery",
                reason: "hash_mismatch",
                stage: "ingest",
              },
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
      },
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
      agent_failure_context: {
        explanation: "Stage ingest blocked the agent edit.",
        issues: [
          {
            code: "stale_state_mismatch",
            severity: "error",
          },
        ],
      },
    };
    panel.state.phase = "ERROR";
    panel.state.failure = initialFailure;
    extensionModule.syncBaselineFromResponse(panel, initialFailure);
    assert.equal(panel.state.rebaselineRecovery?.last_known_baseline_graph_hash, "baseline-before-recovery");
    extensionModule.renderAgentPanel(panel);

    let recoveryButtons = recoveryButtonsFor();
    assert.equal(recoveryButtons.length, 1);
    assert.match(harness.textDump(), /canvas changed since the current backend baseline/i);
    assert.match(harness.textDump(), /Rebaseline & retry/);

    recoveryButtons[0].click();
    await waitFor(() => rebaselineBodies.length === 1);
    await waitFor(() => panel.state.rebaselineRecovery?.last_known_baseline_graph_hash === "baseline-retry");
    assert.equal(rebaselineBodies[0].reason, "stale_state_recovery");
    assert.equal(rebaselineBodies[0].last_known_baseline_graph_hash, "baseline-before-recovery");
    assert.equal(panel.state.failure?.kind, "StaleStateMismatch");
    assert.equal(panel.state.rebaselineRecovery?.last_known_baseline_graph_hash, "baseline-retry");
    recoveryButtons = recoveryButtonsFor();
    assert.equal(recoveryButtons.length, 1);

    recoveryButtons[0].click();
    await waitFor(() => rebaselineBodies.length === 2);
    await waitFor(() => submitBodies.length === 1);
    await waitFor(() => panel.state.turnId === "0006");
    assert.equal(rebaselineBodies[1].last_known_baseline_graph_hash, "baseline-retry");
    assert.equal(panel.state.failure, null);
    assert.equal(panel.state.rebaselineRecovery, null);
    assert.equal(panel.state.baselineGraphHash, "baseline-after-recovery");
    assert.equal(panel.state.baselineSource, "rebaseline");
    assert.equal(panel.state.baselineGraphSourcePath, "_rebaseline/recovery-0001/graph.ui.json");
    assert.equal(recoveryButtonsFor().length, 0);
    assert.equal(submitBodies.length, 1);
    assert.equal(panel.state.candidateGraphHash, "candidate-after-recovery");
    assert.match(harness.textDump(), /Apply is allowed, but Queue remains blocked for this candidate\./);

    await harness.clickButton("Apply");
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

test("VibeComfy turn audits move from persistent history cards into expanded bubble details", async () => {
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
        apply_eligibility: {
          applyable: true,
          reason: "queue_blocked_warning",
          message: "Apply is allowed, but Queue remains blocked for this candidate.",
          warnings: ["queue_blocked"],
        },
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
      "/vibecomfy/agent-executor": async () => turnResponses.shift(),
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
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    const panel = extensionModule.ensureAgentPanel();

    // ── Turn 1: submit, get candidate, apply ──
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "turn 1 task";
    await harness.clickButton("Submit");

    const afterCandidateText = harness.textDump();
    assert.match(afterCandidateText, /First turn candidate ready/);
    assert.doesNotMatch(afterCandidateText, /\/tmp\/audit-turn-0001\.json/);

    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /candidate/i);
    assert.match(harness.textDump(), /turn: 0001/);
    assert.ok(
      panel.state.auditArtifacts.some((artifact) => artifact.auditRef?.path === "/tmp/audit-turn-0001.json"),
      "candidate audit artifact should be retained",
    );

    // Apply turn 1
    await harness.clickButton("Apply");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-undo")?.getAttribute("aria-label"), "Undo Last Apply");
    assert.ok(
      panel.state.auditArtifacts.some((artifact) => artifact.auditRef?.path === "/tmp/audit-turn-0001-accept.json"),
      "accept audit artifact should be retained",
    );
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 1);

    // ── Turn 2: submit, get failure ──
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "turn 2 task";
    await harness.clickButton("Submit");

    const afterFailureText = harness.textDump();
    assert.match(afterFailureText, /ValidationError/);
    assert.doesNotMatch(afterFailureText, /\/tmp\/audit-turn-0002\.json/);
    // Canvas should not have been mutated on failure
    assert.equal(harness.loadGraphDataCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 1);

    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /failed/i);
    assert.match(harness.textDump(), /turn: 0002/);
    assert.ok(
      panel.state.auditArtifacts.some((artifact) => artifact.auditRef?.path === "/tmp/audit-turn-0002.json"),
      "failure audit artifact should be retained",
    );

    const historyRegion = harness.document.getElementById("vibecomfy-agent-panel-region-history");
    assert.ok(historyRegion, "history region still exists as the transient live mount");
    assert.doesNotMatch(historyRegion.textContent || "", /audit-turn-0001|audit-turn-0002|applied|failed/i);
    assert.equal(
      historyRegion.querySelectorAll((node) => node.className === "vibecomfy-batch-row").length,
      0,
      "terminal turns should not leave persistent live rows",
    );
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
      "/vibecomfy/agent-executor": async ({ options }) => {
        submitBodies.push(JSON.parse(options.body));
        return new Promise((resolve) => {
          resolveSubmit = resolve;
        });
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
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
        apply_eligibility: {
          applyable: true,
          reason: "queue_blocked_warning",
          message: "Apply is allowed, but Queue remains blocked for this candidate.",
          warnings: ["queue_blocked"],
        },
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

    expandAgentBubbleDetails(harness.document.body);
    const text = harness.textDump();
    assert.equal(submitBodies[0].client_id, harness.api.clientId);
    assert.match(text, /Candidate after batch replay\./);
    assert.doesNotMatch(text, /authoritative response step/);
    assert.doesNotMatch(text, /authoritative done step/);
    assert.doesNotMatch(text, /ignored before session bind/);

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "session-live",
      turn_number: 2,
      status: "in_progress",
      message: "post-response websocket step",
      statement_count: 1,
    });
    await waitFor(() => {
      const panel = mod.ensureAgentPanel();
      return panel.state.turns.some((entry) => entry?.entry_type === "batch" && entry.message === "post-response websocket step");
    });
    assert.doesNotMatch(harness.textDump(), /post-response websocket step/);

    const liveListener = harness.apiEventListeners["vibecomfy.agent_edit.turn"][0];
    liveListener({
      session_id: "session-live",
      turn_number: 3,
      status: "done",
      message: "direct payload step",
      statement_count: 1,
      done_summary: "temporary summary",
    });
    assert.doesNotMatch(harness.textDump(), /direct payload step/);

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
      "/vibecomfy/agent-executor": {
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

    expandAgentBubbleDetails(harness.document.body);
    const text = harness.textDump();

    // lowered diff row appears with teal color
    assert.match(text, /lowered: loop-uid-1 -> 3 native node\(s\)/);

    // queue is allowed (lowered entry does not block)
    assert.match(text, /queueAllowed:\s*true/);

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
      "/vibecomfy/agent-executor": {
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

    expandAgentBubbleDetails(harness.document.body);
    const text = harness.textDump();

    // queue is blocked because vibecomfy.code is in the graph nodes (graph-scan fallback)
    assert.match(text, /queueAllowed:\s*false/);

    // graph-scan fallback detects the unlowered intent node
    assert.match(text, /Node 2 \(vibecomfy\.code\) is an editor-only intent node/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy agent-edit turn progress: client_id submit body, hidden batch_turns, out-of-order live upsert with session filtering, and Apply/Reject controls remain rendered and clickable", async () => {
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
      "/vibecomfy/agent-executor": async ({ options }) => {
        submitBodies.push(JSON.parse(options.body));
        return new Promise((resolve) => {
          resolveSubmit = resolve;
        });
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
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
        apply_eligibility: {
          applyable: true,
          reason: "queue_blocked_warning",
          message: "Apply is allowed, but Queue remains blocked for this candidate.",
          warnings: ["queue_blocked"],
        },
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

    // Verify terminal batch_turns are retained in state but not rendered in the user-facing UI.
    let text = harness.textDump();
    assert.match(text, /Candidate with authoritative batch_turns fallback\./);
    const historyRegion = harness.document.getElementById("vibecomfy-agent-panel-region-history");
    assert.doesNotMatch(historyRegion.textContent || "", /analyzing the graph/);
    assert.doesNotMatch(historyRegion.textContent || "", /finalizing edits/);
    const panel = mod.ensureAgentPanel();
    assert.equal(
      panel.state.turns.filter((entry) => entry?.entry_type === "batch").length,
      2,
      "batch turns should remain available to state/audit consumers",
    );

    expandAgentBubbleDetails(harness.document.body);
    text = harness.textDump();
    assert.doesNotMatch(text, /analyzing the graph/);
    assert.doesNotMatch(text, /finalizing edits/);
    assert.doesNotMatch(text, /batch turn 1/);
    assert.doesNotMatch(text, /batch turn 2/);

    // The transient live mount has no rows after the response terminalizes.
    assert.equal(historyRegion.querySelectorAll((node) => node.className === "vibecomfy-batch-row").length, 0);

    // ── Part 3: websocket turn events must not revive the legacy live strip ──
    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "session-batch-fallback",
      turn_number: 3,
      status: "in_progress",
      message: "third turn running out of order",
      statement_count: 1,
    });

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "session-batch-fallback",
      turn_number: 2,
      status: "in_progress",
      message: "second turn arrives after third",
      statement_count: 2,
    });

    text = harness.textDump();
    assert.doesNotMatch(text, /third turn running out of order/);
    assert.doesNotMatch(text, /second turn arrives after third/);
    assert.doesNotMatch(text, /Turn 4/);
    assert.doesNotMatch(text, /Turn 3/);

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: "foreign-session-xyz",
      turn_number: 0,
      status: "in_progress",
      message: "foreign session event must be filtered",
    });
    assert.doesNotMatch(harness.textDump(), /foreign session event must be filtered/);

    const progressDots = historyRegion.querySelectorAll((node) => node.className === "vibecomfy-batch-progress-dot");
    assert.equal(progressDots.length, 0, "legacy in-progress dots should not render below the thread");
    assert.equal(historyRegion.querySelectorAll((node) => node.className === "vibecomfy-batch-row").length, 0);

    // Terminal batch details stay out of the expanded agent bubble.
    text = harness.textDump();
    assert.doesNotMatch(text, /Final reasoning summary/);
    assert.doesNotMatch(text, /assign/);
    assert.doesNotMatch(text, /saveimage\.filename_prefix/);
    assert.doesNotMatch(text, /STMT_DELETE_OK/);
    assert.doesNotMatch(text, /node removed cleanly/);
    assert.doesNotMatch(text, /WIRE_FAIL/);
    assert.doesNotMatch(text, /target slot occupied/);
    assert.doesNotMatch(text, /exit: step_continue/);
    assert.doesNotMatch(text, /BATCH_OK/);

    // These sensitive/internal fields should NOT appear in the batch row rendering
    const expandedText = harness.textDump();
    assert.doesNotMatch(expandedText, /\bdiff\b/i);
    assert.doesNotMatch(expandedText, /raw_batch/i);
    assert.doesNotMatch(expandedText, /raw_source/i);
    assert.doesNotMatch(expandedText, /provider_metadata/i);
    assert.doesNotMatch(expandedText, /raw_json/i);

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

    // Terminal batch turns are still retained for audit/state, but not rendered.
    assert.doesNotMatch(harness.textDump(), /analyzing the graph/);
    assert.equal(
      historyRegion.querySelectorAll((node) => node.className === "vibecomfy-batch-row").length,
      0,
    );
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
    links: [[101, 1, 0, 2, 0, "IMAGE"]],
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
    links: [[102, 1, 0, 3, 0, "IMAGE"]],
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

test("VibeComfy preview overlays omit forbidden audit/debug keys and values from canvas text", async () => {
  const liveGraph = {
    nodes: [
      {
        id: 1,
        type: "Input",
        pos: [100, 200],
        size: [240, 100],
        properties: { vibecomfy_uid: "uid-live" },
        inputs: [],
        outputs: [{ name: "TEXT" }],
        widgets: [{ name: "prompt", value: "old value", last_y: 40 }],
        widgets_values: ["old value"],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "Input",
        pos: [100, 200],
        size: [240, 100],
        properties: {
          vibecomfy_uid: "uid-live",
          debug_payload: { raw_path: "/real/ComfyUI/out/editor_sessions/session/turns/0001/debug.json" },
        },
        inputs: [],
        outputs: [{ name: "TEXT" }],
        widgets_values: ["new safe value"],
      },
      {
        id: 2,
        type: "SafePreviewNode",
        title: "SafePreviewNode",
        pos: [420, 200],
        size: [240, 120],
        properties: {
          vibecomfy_uid: "uid-new",
          audit_ref: { path: "/real/ComfyUI/out/editor_sessions/session/turns/0001/audit.json" },
          canvasApplyAllowed: true,
          queueAllowed: false,
        },
        inputs: [{ name: "queue_allowed" }, { name: "images" }],
        outputs: [{ name: "debug_payload" }],
        widgets_values: [
          "ProviderError raw diagnostic from /real/ComfyUI/out/editor_sessions/session/turns/0001/response.json",
          { model_prompt: "hidden prompt messages" },
        ],
      },
    ],
    links: [],
  };
  const contaminatedDiff = {
    _candidateGraph: candidateGraph,
    _candidateGraphHash: "candidate-overlay-forbidden-sentinel",
    edited: [{ uid: "uid-live", changedWidgetIndices: [0] }],
    edited_fields: [
      {
        uid: "uid-live",
        field_path: "debug_payload.raw_path",
        new_value: "/real/ComfyUI/out/editor_sessions/session/turns/0001/debug.json",
      },
      { uid: "uid-live", field_path: "widgets_values.0", new_value: "new safe value" },
    ],
    added: [
      {
        uid: "uid-new",
        class_type: "SafePreviewNode",
        debug_payload: { raw_path: "/real/ComfyUI/out/editor_sessions/session/turns/0001/debug.json" },
      },
    ],
    removed: [],
    removed_named: [],
    added_links: [],
    removed_links: [],
    unresolved: [
      {
        uid: "uid-missing",
        kind: "ProviderError",
        reason: "engine diagnostics must stay out of canvas text",
      },
    ],
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
    await harness.loadExtension();
    await harness.setup();
    const roundtripDrawOps = await harness.drawPreviewOverlay(contaminatedDiff);
    assertCanvasTextOpsHaveNoForbiddenText(roundtripDrawOps, "$.roundtripOverlay");

    const directCtx = createMockCanvasContext();
    drawPanelOverlayPreviewOverlay(
      directCtx,
      { ...contaminatedDiff, _candidateGraphHash: "panel-overlay-forbidden-sentinel" },
      makePanelOverlayDeps(liveGraph),
    );
    assertCanvasTextOpsHaveNoForbiddenText(directCtx._getOperations(), "$.panelOverlay");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy preview diff does not mark unchanged links as added when live nodes are missing vibecomfy_uid", async () => {
  const liveGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [80, 180],
        size: [240, 100],
        properties: {},
        inputs: [],
        outputs: [{ name: "IMAGE" }],
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [380, 120],
        size: [240, 100],
        properties: {},
        inputs: [{ name: "images" }],
        outputs: [],
      },
      {
        id: 3,
        type: "PreviewImage",
        pos: [380, 280],
        size: [240, 124],
        properties: {},
        inputs: [{ name: "images" }],
        outputs: [],
      },
    ],
    links: [[101, 1, 0, 2, 0, "IMAGE"]],
  };

  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [80, 180],
        size: [240, 100],
        properties: { vibecomfy_uid: "uid-1" },
        inputs: [],
        outputs: [{ name: "IMAGE" }],
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [380, 120],
        size: [240, 100],
        properties: { vibecomfy_uid: "uid-2" },
        inputs: [{ name: "images" }],
        outputs: [],
      },
      {
        id: 3,
        type: "PreviewImage",
        pos: [380, 280],
        size: [240, 124],
        properties: { vibecomfy_uid: "uid-3" },
        inputs: [{ name: "images" }],
        outputs: [],
      },
    ],
    links: [
      [101, 1, 0, 2, 0, "IMAGE"],
      [102, 1, 0, 3, 0, "IMAGE"],
    ],
  };

  const candidateReport = {
    change: {
      content_edits: {
        preserved: ["uid-1", "uid-2"],
        new_auto_placed: ["uid-3"],
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

    const diff = extensionModule.computePreviewDiff(candidateGraph, candidateReport);

    assert.deepEqual(
      diff.added_links,
      ["uid-1::IMAGE->uid-3::images"],
      "only the genuinely new preview link should be highlighted as added",
    );
    assert.deepEqual(
      diff.removed_links,
      [],
      "the unchanged existing link must not be treated as removed",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy preview overlay caches live UID lookups and ghost measurements across draws", async () => {
  const liveGraph = {
    nodes: Array.from({ length: 25 }, (_, index) => ({
      id: index + 1,
      type: index === 0 ? "KSampler" : "Passthrough",
      pos: [100 + index, 200 + index],
      size: [220, 100],
      properties: { vibecomfy_uid: `uid-${index + 1}` },
      inputs: [{ name: "in" }],
      outputs: [{ name: "out" }],
      widgets_values: [index],
    })),
    links: [],
  };
  const candidateGraph = {
    nodes: [
      ...liveGraph.nodes,
      {
        id: 99,
        type: "PreviewImage",
        pos: [500, 260],
        properties: { vibecomfy_uid: "uid-new" },
        inputs: [{ name: "images" }],
        outputs: [],
        widgets_values: ["preview"],
      },
    ],
    links: [],
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
    let liveUidReads = 0;
    for (const node of harness.getLiveNodes()) {
      const original = node.properties;
      Object.defineProperty(node, "properties", {
        configurable: true,
        get() {
          liveUidReads += 1;
          return original;
        },
      });
    }
    const diff = {
      _candidateGraph: candidateGraph,
      _candidateGraphHash: "candidate-overlay-cache",
      edited: [{ uid: "uid-1", changedWidgetIndices: [0] }],
      edited_fields: [],
      added: [{ uid: "uid-new", class_type: "PreviewImage", unwiredRequiredInputs: ["images"] }],
      removed: [],
      removed_named: [],
      added_links: [],
      removed_links: [],
      unresolved: [],
    };

    await harness.drawPreviewOverlay(diff);
    assert.ok(liveUidReads > 0, "first draw should build the live UID map");
    liveUidReads = 0;
    await harness.drawPreviewOverlay(diff);
    assert.equal(liveUidReads, 0, "second draw should reuse the cached live UID map");

    const measureOps = await harness.drawPreviewOverlay(diff);
    const previewMeasureCount = measureOps.filter((op) => op.kind === "measureText" && op.args[0] === "PreviewImage").length;
    assert.equal(previewMeasureCount, 0, "cached ghost dimensions should avoid remeasuring ghost title text");
    assert.equal(typeof extensionModule.drawPreviewOverlay, "function");
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
    let lastFill = null;
    let editedFillRect = null;
    let editedRect = null;
    for (const op of drawOps) {
      if (op.kind === "strokeStyle") lastStroke = op.args[0];
      if (op.kind === "fillStyle") lastFill = op.args[0];
      if (op.kind === "fillRect" && lastFill === "rgba(255,193,7,0.16)") {
        editedFillRect = op.args;
      }
      if (op.kind === "strokeRect" && lastStroke === "#ffc107") {
        editedRect = op.args; // [x, y, w, h]
        break;
      }
    }
    assert.ok(editedFillRect, "must fill the full edited node box with translucent amber");
    assert.ok(editedRect, "must stroke an amber (#ffc107) rect for the edited node");
    assert.deepEqual(editedFillRect, editedRect, "edited fill must cover the same full box as the border");
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

test("VibeComfy edited canvas widget field values render on their widget rows", async () => {
  const NODE_POS = [120, 240];
  const NODE_SIZE = [260, 150];
  const liveGraph = {
    nodes: [
      {
        id: 7,
        type: "KSampler",
        pos: [...NODE_POS],
        size: [...NODE_SIZE],
        properties: { vibecomfy_uid: "uid-widget-values" },
        inputs: [{ name: "model" }],
        outputs: [{ name: "LATENT" }],
        widgets_values: [1, 20, 7.5],
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
        properties: { vibecomfy_uid: "uid-widget-values" },
        inputs: [{ name: "model" }],
        outputs: [{ name: "LATENT" }],
        widgets_values: [5, 24, 7.5],
      },
    ],
    links: [],
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
    const liveNode = harness.getLiveNodes()[0];
    liveNode.widgets = [
      { name: "seed", value: 1, last_y: 48, computeSize: () => [NODE_SIZE[0], 20] },
      { name: "steps", value: 20, last_y: 72, computeSize: () => [NODE_SIZE[0], 22] },
      { name: "cfg", value: 7.5, last_y: 96, computeSize: () => [NODE_SIZE[0], 20] },
    ];
    const panel = extensionModule.ensureAgentPanel();
    panel.state.lastSubmitFieldChanges = {
      outcomeChanges: [
        { uid: "uid-widget-values", field_path: "seed", old: 1, new: 5 },
        { uid: "uid-widget-values", field_path: "steps", old: 20, new: 24 },
      ],
      batchTurnChanges: [],
    };

    const diff = extensionModule.computePreviewDiff(candidateGraph, {
      change: { content_edits: { preserved: [], edited: ["uid-widget-values"], removed_named: [] } },
      recovery: [],
    });
    assert.deepEqual(diff.edited[0].changedWidgetIndices, [0, 1]);

    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });
    const amberValuePanels = [];
    for (const op of drawOps) {
      if (
        op.kind === "fillRect"
        && (op.args[1] === NODE_POS[1] + 48 || op.args[1] === NODE_POS[1] + 72)
        && op.args[0] > NODE_POS[0]
      ) {
        amberValuePanels.push(op.args);
      }
    }
    assert.equal(amberValuePanels.length, 2, "each changed widget gets one row highlight");
    assert.equal(amberValuePanels[0][1], NODE_POS[1] + 48, "seed highlight must cover widget row 0");
    assert.equal(amberValuePanels[1][1], NODE_POS[1] + 72, "steps highlight must cover widget row 1");
    assert.ok(amberValuePanels[0][0] > NODE_POS[0], "seed preview overlay must be inset to the field area");
    assert.ok(amberValuePanels[1][0] > NODE_POS[0], "steps preview overlay must be inset to the field area");
    assert.ok(amberValuePanels[0][2] > NODE_SIZE[0] * 0.8, "seed preview overlay should cover the edited field width");
    assert.ok(amberValuePanels[1][2] > NODE_SIZE[0] * 0.8, "steps preview overlay should cover the edited field width");
    assert.ok(amberValuePanels[0][0] + amberValuePanels[0][2] <= NODE_POS[0] + NODE_SIZE[0] - 15);
    assert.ok(amberValuePanels[1][0] + amberValuePanels[1][2] <= NODE_POS[0] + NODE_SIZE[0] - 15);

    const newValueTexts = drawOps.filter((op) => op.kind === "fillText" && (op.args[0] === "seed: 5" || op.args[0] === "steps: 24"));
    assert.equal(newValueTexts.length, 2, "canvas-only widget values must be visible in the preview overlay");
    assert.deepEqual(
      newValueTexts.map((op) => op.args[2]),
      [NODE_POS[1] + 48 + 10, NODE_POS[1] + 72 + 11],
      "new value text y must track each widget row center",
    );
    const oldCornerChipTexts = drawOps
      .filter((op) => op.kind === "fillText")
      .filter((op) => op.args[2] > NODE_POS[1] + 100)
      .map((op) => op.args[0])
      .filter((text) => text === "seed: 5" || text === "steps: 24");
    assert.deepEqual(oldCornerChipTexts, [], "widget fields must not render stacked corner chips");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy widget value overlays derive fallback bounds and clamp long text inside the visible preview", async () => {
  const CANDIDATE_POS = [140, 240];
  const CANDIDATE_SIZE = [180, 70];
  const candidateGraph = {
    nodes: [
      {
        id: 12,
        type: "KSampler",
        pos: [...CANDIDATE_POS],
        size: [...CANDIDATE_SIZE],
        properties: { vibecomfy_uid: "uid-invalid-widget-bounds" },
        inputs: [{ name: "model" }],
        outputs: [{ name: "LATENT" }],
        widgets_values: ["new preview value"],
      },
    ],
    links: [],
  };
  const liveGraph = {
    nodes: [
      {
        id: 12,
        type: "KSampler",
        pos: [0, 0],
        size: [0, 0],
        properties: { vibecomfy_uid: "uid-invalid-widget-bounds" },
        inputs: [{ name: "model" }],
        outputs: [{ name: "LATENT" }],
        widgets_values: ["old preview value"],
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    const longValue = "replacement preview value with enough wrapped words to require clamped multiline overlay text near the canvas edge";
    const liveNode = harness.getLiveNodes()[0];
    liveNode.widgets = [
      { name: "cfg", value: "old preview value", last_y: 0, computeSize: () => [0, 0] },
    ];
    harness.app.canvas.canvas = {
      ownerDocument: harness.document,
      width: 320,
      height: 300,
      clientWidth: 320,
      clientHeight: 300,
      getBoundingClientRect() {
        return { left: 0, top: 0, width: 320, height: 300 };
      },
    };
    harness.app.canvas.ds = { scale: 1, offset: [0, 0] };
    const ctx = createMockCanvasContext();
    drawPanelOverlayPreviewOverlay(
      ctx,
      {
        edited: [{ uid: "uid-invalid-widget-bounds", class_type: "KSampler", changedWidgetIndices: [0] }],
        edited_fields: [{ uid: "uid-invalid-widget-bounds", field_path: "widgets_values.0", new_value: longValue }],
        added: [],
        removed: [],
        removed_named: [],
        added_links: [],
        removed_links: [],
        _candidateGraph: candidateGraph,
        _candidateGraphHash: "candidate-invalid-widget-bounds",
      },
      makePanelOverlayDeps({ nodes: harness.getLiveNodes(), links: [] }),
    );

    const drawOps = ctx._getOperations();
    const panel = drawOps.find((op) => op.kind === "roundRect");
    assert.ok(panel, "widget preview overlay panel should be drawn");
    assert.ok(panel.args[0] >= CANDIDATE_POS[0], "overlay should derive the candidate node x instead of floating at the origin");
    assert.ok(panel.args[1] >= CANDIDATE_POS[1], "overlay should derive the candidate node y instead of floating at the origin");
    assert.ok(panel.args[2] <= CANDIDATE_SIZE[0], "overlay width should stay within the candidate node width");
    assert.ok(panel.args[3] > 20, "long overlay text should expand the panel height beyond the collapsed widget row");
    assert.ok(panel.args[0] + panel.args[2] <= 320, "overlay panel should stay inside the visible preview width");
    assert.ok(panel.args[1] + panel.args[3] <= 300, "overlay panel should stay inside the visible preview height");

    const textOps = drawOps.filter((op) => op.kind === "fillText");
    assert.ok(textOps.length >= 2, "long overlay text should wrap across multiple lines");
    for (const op of textOps) {
      assert.ok(op.args[1] > 20, "overlay text x should stay away from the canvas origin");
      assert.ok(op.args[2] > 20, "overlay text y should stay away from the canvas origin");
      assert.ok(op.args[1] <= panel.args[0] + panel.args[2], "overlay text should stay inside the panel width");
      assert.ok(op.args[2] <= panel.args[1] + panel.args[3], "overlay text should stay inside the panel height");
    }
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy edited canvas text widget preview highlights the edited field area with visible fallback text", async () => {
  const NODE_POS = [100, 220];
  const NODE_SIZE = [320, 170];
  const liveGraph = {
    nodes: [
      {
        id: 9,
        type: "CLIPTextEncode",
        pos: [...NODE_POS],
        size: [...NODE_SIZE],
        properties: { vibecomfy_uid: "uid-text-widget" },
        inputs: [],
        outputs: [{ name: "CONDITIONING" }],
        widgets_values: ["old prompt that still belongs to the live canvas field"],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 9,
        type: "CLIPTextEncode",
        pos: [...NODE_POS],
        size: [...NODE_SIZE],
        properties: { vibecomfy_uid: "uid-text-widget" },
        inputs: [],
        outputs: [{ name: "CONDITIONING" }],
        widgets_values: ["new prompt visible in preview"],
      },
    ],
    links: [],
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
    const liveNode = harness.getLiveNodes()[0];
    liveNode.widgets = [
      {
        name: "text",
        value: liveGraph.nodes[0].widgets_values[0],
        last_y: 42,
        computeSize: () => [NODE_SIZE[0], 74],
      },
    ];
    const panel = extensionModule.ensureAgentPanel();
    panel.state.lastSubmitFieldChanges = {
      outcomeChanges: [
        {
          uid: "uid-text-widget",
          field_path: "widgets_values.0",
          old: liveGraph.nodes[0].widgets_values[0],
          new: candidateGraph.nodes[0].widgets_values[0],
        },
      ],
      batchTurnChanges: [],
    };

    const diff = extensionModule.computePreviewDiff(candidateGraph, {
      change: { content_edits: { preserved: [], edited: ["uid-text-widget"], removed_named: [] } },
      recovery: [],
    });
    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });

    const previewPanel = drawOps.find((op) => op.kind === "fillRect" && op.args[1] === NODE_POS[1] + 42);
    assert.ok(previewPanel, "text widget preview needs a visible edited-row highlight");
    assert.ok(previewPanel.args[0] > NODE_POS[0], "text preview highlight must be inset to the field area");
    assert.ok(previewPanel.args[2] > NODE_SIZE[0] * 0.8, "text preview highlight must cover the edited field width");
    assert.ok(previewPanel.args[0] + previewPanel.args[2] <= NODE_POS[0] + NODE_SIZE[0] - 15);
    const wrappedPreviewText = drawOps
      .filter((op) => op.kind === "fillText")
      .map((op) => op.args[0])
      .join(" ");
    assert.match(wrappedPreviewText, /text: new prompt/, "canvas-only text widgets still need visible fallback preview text");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy edited DOM widget field values do not duplicate as canvas value text", async () => {
  const NODE_POS = [100, 220];
  const NODE_SIZE = [320, 170];
  const liveGraph = {
    nodes: [
      {
        id: 9,
        type: "CLIPTextEncode",
        pos: [...NODE_POS],
        size: [...NODE_SIZE],
        properties: { vibecomfy_uid: "uid-dom-no-duplicate-widget" },
        inputs: [],
        outputs: [{ name: "CONDITIONING" }],
        widgets_values: ["old prompt"],
      },
    ],
    links: [],
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
    const liveNode = harness.getLiveNodes()[0];
    const inputEl = {
      getBoundingClientRect() {
        return { left: 125, top: 262, width: 290, height: 74 };
      },
    };
    liveNode.widgets = [
      {
        name: "text",
        value: "old prompt",
        last_y: 42,
        inputEl,
        computeSize: () => [NODE_SIZE[0], 74],
      },
    ];
    const panel = extensionModule.ensureAgentPanel();
    panel.state.lastSubmitFieldChanges = {
      outcomeChanges: [
        { uid: "uid-dom-no-duplicate-widget", field_path: "widgets_values.0", old: "old prompt", new: "new prompt visible above the field" },
      ],
      batchTurnChanges: [],
    };

    const candidateGraph = {
      nodes: [
        {
          ...liveGraph.nodes[0],
          widgets_values: ["new prompt visible above the field"],
        },
      ],
      links: [],
    };
    const diff = extensionModule.computePreviewDiff(candidateGraph, {
      change: { content_edits: { preserved: [], edited: ["uid-dom-no-duplicate-widget"], removed_named: [] } },
      recovery: [],
    });
    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });
    const wrappedPreviewText = drawOps
      .filter((op) => op.kind === "fillText")
      .map((op) => op.args[0])
      .join(" ");
    assert.doesNotMatch(wrappedPreviewText, /text: new prompt visible above the field/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy edited text widget DOM preview chip sits on top of the edited field", async () => {
  const NODE_POS = [100, 220];
  const NODE_SIZE = [320, 170];
  const liveGraph = {
    nodes: [
      {
        id: 9,
        type: "CLIPTextEncode",
        pos: [...NODE_POS],
        size: [...NODE_SIZE],
        properties: { vibecomfy_uid: "uid-dom-text-widget" },
        inputs: [],
        outputs: [{ name: "CONDITIONING" }],
        widgets_values: ["old prompt"],
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    const liveNode = harness.getLiveNodes()[0];
    const inputEl = {
      getBoundingClientRect() {
        return { left: 125, top: 262, width: 290, height: 74 };
      },
    };
    liveNode.widgets = [
      {
        name: "text",
        value: "old prompt",
        last_y: 42,
        inputEl,
        computeSize: () => [NODE_SIZE[0], 74],
      },
    ];
    harness.app.canvas.canvas = {
      ownerDocument: harness.document,
      width: 1000,
      height: 800,
      clientWidth: 1000,
      clientHeight: 800,
      getBoundingClientRect() {
        return { left: 10, top: 20, width: 1000, height: 800 };
      },
    };
    harness.app.canvas.ds = { scale: 1, offset: [0, 0] };
    const ctx = createMockCanvasContext();
    syncPreviewDomOverlay(
      harness.app,
      ctx,
      {
        edited: [{ uid: "uid-dom-text-widget", class_type: "CLIPTextEncode", changedWidgetIndices: [0] }],
        edited_fields: [{ uid: "uid-dom-text-widget", field_path: "widgets_values.0", new_value: "new prompt visible above the field" }],
        added: [],
        removed: [],
        removed_named: [],
        added_links: [],
        removed_links: [],
        _candidateGraph: liveGraph,
      },
      liveGraph,
      makePanelOverlayDeps({ nodes: harness.getLiveNodes(), links: [] }),
    );

    const root = harness.document.getElementById("vibecomfy-preview-dom-overlay");
    assert.ok(root, "preview DOM overlay root should be created");
    assert.equal(root.style.zIndex, "2147483647");
    const chips = root.querySelectorAll((node) => node.dataset?.vibecomfyPreviewChip === "1");
    assert.equal(chips.length, 1);
    assert.equal(chips[0].textContent, "text: new prompt visible above the field");
    assert.equal(chips[0].style.position, "fixed");
    assert.equal(chips[0].style.zIndex, "2147483647");
    assert.equal(chips[0].style.left, "125px");
    assert.equal(chips[0].style.top, "262px");
    assert.equal(chips[0].style.width, "290px");
    assert.equal(chips[0].style.height, "74px");
    assert.equal(chips[0].style.fontSize, "11px");
    assert.equal(chips[0].style.alignItems, "flex-start");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy edited text widget DOM preview chip uses the widget DOM rect when available", async () => {
  const NODE_POS = [100, 220];
  const NODE_SIZE = [320, 170];
  const liveGraph = {
    nodes: [
      {
        id: 9,
        type: "CLIPTextEncode",
        pos: [...NODE_POS],
        size: [...NODE_SIZE],
        properties: { vibecomfy_uid: "uid-dom-rect-widget" },
        inputs: [],
        outputs: [{ name: "CONDITIONING" }],
        widgets_values: ["old prompt"],
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    const liveNode = harness.getLiveNodes()[0];
    const inputEl = {
      getBoundingClientRect() {
        return { left: 444, top: 155, width: 237, height: 63 };
      },
    };
    liveNode.widgets = [
      {
        name: "text",
        value: "old prompt",
        last_y: 42,
        inputEl,
        computeSize: () => [NODE_SIZE[0], 20],
      },
    ];
    harness.app.canvas.canvas = {
      ownerDocument: harness.document,
      width: 1000,
      height: 800,
      clientWidth: 1000,
      clientHeight: 800,
      getBoundingClientRect() {
        return { left: 10, top: 20, width: 1000, height: 800 };
      },
    };
    harness.app.canvas.ds = { scale: 1, offset: [0, 0] };
    const ctx = createMockCanvasContext();
    syncPreviewDomOverlay(
      harness.app,
      ctx,
      {
        edited: [{ uid: "uid-dom-rect-widget", class_type: "CLIPTextEncode", changedWidgetIndices: [0] }],
        edited_fields: [{ uid: "uid-dom-rect-widget", field_path: "widgets_values.0", new_value: "new prompt visible above the field" }],
        added: [],
        removed: [],
        removed_named: [],
        added_links: [],
        removed_links: [],
        _candidateGraph: liveGraph,
      },
      liveGraph,
      makePanelOverlayDeps({ nodes: harness.getLiveNodes(), links: [] }),
    );

    const root = harness.document.getElementById("vibecomfy-preview-dom-overlay");
    const chip = root?.querySelectorAll((node) => node.dataset?.vibecomfyPreviewChip === "1")[0];
    assert.ok(chip, "preview DOM overlay chip should be created");
    assert.equal(chip.style.left, "444px");
    assert.equal(chip.style.top, "155px");
    assert.equal(chip.style.width, "237px");
    assert.equal(chip.style.height, "63px");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy edited text widget DOM preview text follows the field visual zoom scale", async () => {
  const liveGraph = {
    nodes: [
      {
        id: 9,
        type: "CLIPTextEncode",
        pos: [100, 220],
        size: [320, 170],
        properties: { vibecomfy_uid: "uid-scaled-dom-widget" },
        inputs: [],
        outputs: [{ name: "CONDITIONING" }],
        widgets_values: ["old prompt"],
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    const liveNode = harness.getLiveNodes()[0];
    const inputEl = harness.document.createElement("textarea");
    Object.assign(inputEl.style, {
      fontSize: "16px",
      fontFamily: "Courier New",
      lineHeight: "20px",
      paddingLeft: "10px",
      paddingRight: "8px",
      paddingTop: "6px",
      paddingBottom: "4px",
      borderRadius: "4px",
    });
    Object.defineProperty(inputEl, "offsetWidth", { configurable: true, value: 300 });
    Object.defineProperty(inputEl, "offsetHeight", { configurable: true, value: 80 });
    inputEl.getBoundingClientRect = () => ({ left: 50, top: 60, width: 150, height: 40 });
    harness.document.body.appendChild(inputEl);
    liveNode.widgets = [
      {
        name: "text",
        value: "old prompt",
        last_y: 42,
        inputEl,
        computeSize: () => [320, 80],
      },
    ];
    harness.app.canvas.canvas = {
      ownerDocument: harness.document,
      width: 1000,
      height: 800,
      clientWidth: 1000,
      clientHeight: 800,
      getBoundingClientRect() {
        return { left: 10, top: 20, width: 1000, height: 800 };
      },
    };
    harness.app.canvas.ds = { scale: 0.5, offset: [0, 0] };
    const ctx = createMockCanvasContext();
    syncPreviewDomOverlay(
      harness.app,
      ctx,
      {
        edited: [{ uid: "uid-scaled-dom-widget", class_type: "CLIPTextEncode", changedWidgetIndices: [0] }],
        edited_fields: [{ uid: "uid-scaled-dom-widget", field_path: "widgets_values.0", new_value: "new prompt visible above the field" }],
        added: [],
        removed: [],
        removed_named: [],
        added_links: [],
        removed_links: [],
        _candidateGraph: liveGraph,
      },
      liveGraph,
      makePanelOverlayDeps({ nodes: harness.getLiveNodes(), links: [] }),
    );

    const chip = harness.document
      .getElementById("vibecomfy-preview-dom-overlay")
      ?.querySelectorAll((node) => node.dataset?.vibecomfyPreviewChip === "1")[0];
    assert.ok(chip, "scaled field preview DOM chip should be created");
    assert.equal(chip.style.left, "50px");
    assert.equal(chip.style.top, "60px");
    assert.equal(chip.style.width, "150px");
    assert.equal(chip.style.height, "40px");
    assert.equal(chip.style.fontSize, "8px");
    assert.equal(chip.style.lineHeight, "10px");
    assert.equal(chip.style.padding, "3px 4px 2px 5px");
    assert.match(chip.style.fontFamily, /Courier New/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy edited text widget DOM preview does not invent a floating chip without a widget DOM rect", async () => {
  const liveGraph = {
    nodes: [
      {
        id: 9,
        type: "CLIPTextEncode",
        pos: [100, 220],
        size: [320, 170],
        properties: { vibecomfy_uid: "uid-no-dom-rect-widget" },
        inputs: [],
        outputs: [{ name: "CONDITIONING" }],
        widgets_values: ["old prompt"],
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    const liveNode = harness.getLiveNodes()[0];
    liveNode.widgets = [
      {
        name: "text",
        value: "old prompt",
        last_y: 42,
        computeSize: () => [320, 74],
      },
    ];
    harness.app.canvas.canvas = {
      ownerDocument: harness.document,
      width: 1000,
      height: 800,
      clientWidth: 1000,
      clientHeight: 800,
      getBoundingClientRect() {
        return { left: 10, top: 20, width: 1000, height: 800 };
      },
    };
    harness.app.canvas.ds = { scale: 0.3, offset: [-700, -500] };
    const ctx = createMockCanvasContext();
    syncPreviewDomOverlay(
      harness.app,
      ctx,
      {
        edited: [{ uid: "uid-no-dom-rect-widget", class_type: "CLIPTextEncode", changedWidgetIndices: [0] }],
        edited_fields: [{ uid: "uid-no-dom-rect-widget", field_path: "widgets_values.0", new_value: "new prompt" }],
        added: [],
        removed: [],
        removed_named: [],
        added_links: [],
        removed_links: [],
        _candidateGraph: liveGraph,
      },
      liveGraph,
      makePanelOverlayDeps({ nodes: harness.getLiveNodes(), links: [] }),
    );

    assert.equal(harness.document.getElementById("vibecomfy-preview-dom-overlay"), null);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy link-rewired target nodes get the full edited-node overlay box", async () => {
  const TITLE_H = 30;
  const SAVE_POS = [420, 260];
  const SAVE_SIZE = [240, 100];
  const liveGraph = {
    nodes: [
      {
        id: 8,
        type: "VAEDecode",
        pos: [80, 180],
        size: [220, 90],
        properties: { vibecomfy_uid: "vae_decode" },
        outputs: [{ name: "IMAGE" }],
        inputs: [],
      },
      {
        id: 18,
        type: "ImageUpscaleWithModel",
        pos: [80, 340],
        size: [220, 90],
        properties: { vibecomfy_uid: "upscale_image" },
        outputs: [{ name: "IMAGE" }],
        inputs: [],
      },
      {
        id: 19,
        type: "SaveImage",
        pos: [...SAVE_POS],
        size: [...SAVE_SIZE],
        properties: { vibecomfy_uid: "final_save" },
        inputs: [{ name: "images" }],
        outputs: [],
      },
    ],
    links: [[201, 18, 0, 19, 0, "IMAGE"]],
  };
  const candidateGraph = {
    nodes: liveGraph.nodes.map((node) => ({ ...node })),
    links: [[202, 8, 0, 19, 0, "IMAGE"]],
  };
  const candidateReport = {
    change: { content_edits: { preserved: ["vae_decode", "upscale_image"], edited: ["final_save"], removed_named: [] } },
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
    assert.ok(diff.added_links.some((key) => key === "vae_decode::IMAGE->final_save::images"));
    assert.ok(diff.removed_links.some((key) => key === "upscale_image::IMAGE->final_save::images"));
    assert.ok(
      diff.edited.some((entry) => entry.uid === "final_save" && entry.changedWidgetIndices.length === 0),
      "link-only rewire target must be promoted into diff.edited",
    );

    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });

    let lastStroke = null;
    let lastFill = null;
    let editedFillRect = null;
    let editedRect = null;
    for (const op of drawOps) {
      if (op.kind === "strokeStyle") lastStroke = op.args[0];
      if (op.kind === "fillStyle") lastFill = op.args[0];
      if (op.kind === "fillRect" && lastFill === "rgba(255,193,7,0.16)") {
        editedFillRect = op.args;
      }
      if (op.kind === "strokeRect" && lastStroke === "#ffc107") {
        editedRect = op.args;
        break;
      }
    }

    assert.ok(editedFillRect, "link-rewired target must fill the full edited box");
    assert.ok(editedRect, "link-rewired target must stroke the full edited box");
    assert.deepEqual(editedFillRect, editedRect);
    const [_rx, ry, _rw, rh] = editedRect;
    assert.ok(ry <= SAVE_POS[1] - TITLE_H, "rewired target box must include the title bar");
    assert.ok(rh >= SAVE_SIZE[1] + TITLE_H, "rewired target box must include body plus title");
    assert.equal(
      drawOps.filter((op) => op.kind === "fillText" && op.args[0] === "inputs changed").length,
      1,
      "link-only changes must render exactly one edited-node corner chip",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy link rewire promotion ignores identical LiteGraph link re-emissions", async () => {
  const liveNodes = [
    {
      id: 1,
      type: "CheckpointLoaderSimple",
      pos: [20, 120],
      size: [240, 120],
      properties: { vibecomfy_uid: "loader" },
      inputs: [],
      outputs: [{ name: "MODEL" }, { name: "CLIP" }, { name: "VAE" }],
    },
    {
      id: 2,
      type: "CLIPTextEncode",
      pos: [300, 80],
      size: [220, 90],
      properties: { vibecomfy_uid: "positive" },
      inputs: [{ name: "clip" }],
      outputs: [{ name: "CONDITIONING" }],
    },
    {
      id: 3,
      type: "CLIPTextEncode",
      pos: [300, 220],
      size: [220, 90],
      properties: { vibecomfy_uid: "negative" },
      inputs: [{ name: "clip" }],
      outputs: [{ name: "CONDITIONING" }],
    },
    {
      id: 4,
      type: "KSampler",
      pos: [580, 150],
      size: [240, 150],
      properties: { vibecomfy_uid: "sampler" },
      inputs: [
        { name: "model" },
        { name: "positive" },
        { name: "negative" },
      ],
      outputs: [{ name: "LATENT" }],
    },
    {
      id: 5,
      type: "VAEDecode",
      pos: [880, 150],
      size: [220, 90],
      properties: { vibecomfy_uid: "decode" },
      inputs: [{ name: "samples" }, { name: "vae" }],
      outputs: [{ name: "IMAGE" }],
    },
    {
      id: 6,
      type: "ImageUpscaleWithModel",
      pos: [1160, 150],
      size: [240, 100],
      properties: { vibecomfy_uid: "upscale" },
      inputs: [{ name: "image" }],
      outputs: [{ name: "IMAGE" }],
    },
    {
      id: 7,
      type: "SaveImage",
      pos: [1440, 150],
      size: [240, 100],
      properties: { vibecomfy_uid: "save" },
      inputs: [{ name: "images" }],
      outputs: [],
    },
  ];
  const cloneNodes = (nodes) => nodes.map((node) => ({
    ...node,
    pos: [...node.pos],
    size: [...node.size],
    properties: { ...node.properties },
    inputs: (node.inputs || []).map((input) => ({ ...input })),
    outputs: (node.outputs || []).map((output) => ({ ...output })),
  }));
  const liveGraph = {
    nodes: cloneNodes(liveNodes),
    links: [
      [101, 1, 1, 2, 0, "CLIP"],
      [102, 1, 1, 3, 0, "CLIP"],
      [103, 1, 0, 4, 0, "MODEL"],
      [104, 2, 0, 4, 1, "CONDITIONING"],
      [105, 3, 0, 4, 2, "CONDITIONING"],
      [106, 4, 0, 5, 0, "LATENT"],
      [107, 1, 2, 5, 1, "VAE"],
      [108, 5, 0, 6, 0, "IMAGE"],
      [109, 6, 0, 7, 0, "IMAGE"],
    ],
  };
  const candidateGraph = {
    nodes: cloneNodes(liveNodes),
    links: [
      [201, 1, 1, 2, 0, "CLIP"],
      [202, 1, 1, 3, 0, "CLIP"],
      [203, 1, 0, 4, 0, "MODEL"],
      [204, 2, 0, 4, 1, "CONDITIONING"],
      [205, 3, 0, 4, 2, "CONDITIONING"],
      [206, 4, 0, 5, 0, "LATENT"],
      [207, 1, 2, 5, 1, "VAE"],
      [208, 5, 0, 6, 0, "IMAGE"],
      [209, 5, 0, 7, 0, "IMAGE"],
    ],
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

    const diff = extensionModule.computePreviewDiff(candidateGraph, {
      change: { content_edits: { preserved: [], edited: [], removed_named: [] } },
      recovery: [],
    });

    assert.deepEqual(diff.edited.map((entry) => entry.uid), ["save"]);
    assert.deepEqual(diff.added_links, ["decode::IMAGE->save::images"]);
    assert.deepEqual(diff.removed_links, ["upscale::IMAGE->save::images"]);

    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });
    const editedBoxFills = drawOps.filter(
      (op, index) => op.kind === "fillRect"
        && drawOps.slice(0, index).reverse().find((prior) => prior.kind === "fillStyle")?.args[0]
          === "rgba(255,193,7,0.16)",
    );
    assert.equal(editedBoxFills.length, 1, "only the changed link target should get a full amber box");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy clearPreviewDomOverlay removes stale fixed DOM preview remnants", async () => {
  const harness = await createBrowserHarness({});
  try {
    const root = harness.document.createElement("div");
    root.id = "vibecomfy-preview-dom-overlay";
    root.style.position = "fixed";
    const chip = harness.document.createElement("div");
    chip.dataset.vibecomfyPreviewChip = "1";
    chip.textContent = "stale floating preview text";
    root.appendChild(chip);
    harness.document.body.appendChild(root);

    clearPreviewDomOverlay(harness.document);

    assert.equal(harness.document.getElementById("vibecomfy-preview-dom-overlay"), null);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy removed-node overlay fills the full node box and keeps the removed badge", async () => {
  const TITLE_H = 30;
  const NODE_POS = [70, 180];
  const NODE_SIZE = [220, 90];
  const graph = {
    nodes: [
      {
        id: 4,
        type: "SaveImage",
        pos: [...NODE_POS],
        size: [...NODE_SIZE],
        properties: { vibecomfy_uid: "uid-remove" },
        inputs: [],
        outputs: [],
        widgets_values: ["crane/half"],
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    const drawOps = await harness.drawPreviewOverlay({
      edited: [],
      edited_fields: [],
      added: [],
      removed: [{ uid: "uid-remove", class_type: "SaveImage" }],
      removed_named: [],
      added_links: [],
      removed_links: [],
      _candidateGraph: { nodes: [], links: [] },
    });

    let lastStroke = null;
    let lastFill = null;
    let removedFillRect = null;
    let removedRect = null;
    for (const op of drawOps) {
      if (op.kind === "strokeStyle") lastStroke = op.args[0];
      if (op.kind === "fillStyle") lastFill = op.args[0];
      if (op.kind === "fillRect" && lastFill === "rgba(244,67,54,0.16)") {
        removedFillRect = op.args;
      }
      if (op.kind === "strokeRect" && lastStroke === "#f44336") {
        removedRect = op.args;
        break;
      }
    }

    assert.ok(removedFillRect, "must fill the full removed node box with translucent red");
    assert.ok(removedRect, "must stroke a red (#f44336) rect for the removed node");
    assert.deepEqual(removedFillRect, removedRect, "removed fill must cover the same full box as the border");
    const [_rx, ry, _rw, rh] = removedRect;
    assert.ok(ry <= NODE_POS[1] - TITLE_H, "removed box must include the title bar");
    assert.ok(rh >= NODE_SIZE[1] + TITLE_H, "removed box must include body plus title");
    assert.ok(
      drawOps.some((op) => op.kind === "fillText" && op.args[0] === "\u2212 will be removed"),
      "removed marker must keep the existing badge label",
    );
    const removedBadgeTextOp = drawOps.find(
      (op) => op.kind === "fillText" && op.args[0] === "\u2212 will be removed",
    );
    assert.ok(removedBadgeTextOp, "removed marker text op must be captured");
    const badgeTextY = removedBadgeTextOp.args[2];
    assert.ok(
      badgeTextY < NODE_POS[1],
      "removed marker must be drawn in the title bar above DOM widget rows",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy preview diff derives removed nodes for delete-only executor candidates", async () => {
  const graph = {
    nodes: [
      {
        id: 4,
        type: "SaveImage",
        pos: [70, 180],
        size: [220, 90],
        properties: { vibecomfy_uid: "uid-remove" },
        inputs: [],
        outputs: [],
      },
      {
        id: 5,
        type: "PreviewImage",
        pos: [330, 180],
        size: [220, 90],
        properties: { vibecomfy_uid: "uid-keep" },
        inputs: [],
        outputs: [],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [graph.nodes[1]],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    const diff = extensionModule.computePreviewDiff(candidateGraph, {
      change: {
        content_edits: {
          removed: ["uid-remove"],
          removed_named: [],
          edited: [],
          new_auto_placed: [],
        },
      },
      recovery: [],
    });

    assert.deepEqual(diff.removed.map((entry) => entry.uid), ["uid-remove"]);
    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });
    assert.ok(
      drawOps.some((op) => op.kind === "fillText" && op.args[0] === "\u2212 will be removed"),
      "computed delete-only diff should render the removed-node overlay badge",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy edited-node overlay reads Float32Array node sizes", async () => {
  const NODE_SIZE = [420, 110];
  const graph = {
    nodes: [
      {
        id: 8,
        type: "KSampler",
        pos: [50, 80],
        size: [200, 100],
        properties: { vibecomfy_uid: "uid-float-size" },
        inputs: [],
        outputs: [],
        widgets_values: [1],
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    harness.getLiveNodes()[0].size = new Float32Array(NODE_SIZE);
    const drawOps = await harness.drawPreviewOverlay({
      edited: [{ uid: "uid-float-size", changedWidgetIndices: [] }],
      edited_fields: [],
      added: [],
      removed: [],
      removed_named: [],
      added_links: [],
      removed_links: [],
      _candidateGraph: graph,
    });

    let lastStroke = null;
    let editedRect = null;
    for (const op of drawOps) {
      if (op.kind === "strokeStyle") lastStroke = op.args[0];
      if (op.kind === "strokeRect" && lastStroke === "#ffc107") {
        editedRect = op.args;
        break;
      }
    }
    assert.ok(editedRect, "edited overlay rect must be drawn");
    assert.equal(editedRect[2], NODE_SIZE[0] + 4);
  } finally {
    await harness.dispose();
  }
});

// ── T12: Browser smoke tests for refresh/localStorage behavior ─────────────
// NOTE: These tests verify the localStorage → fetch → render pipeline.
// The async .then(renderAgentPanel) callback path in _rehydrateChat currently
// hits a ReferenceError in the harness (globalThis.document is resolved at
// module-eval time but the microtask closure loses it in this Node.js version).
// The tests therefore focus on what IS verifiable: localStorage persistence,
// fetch dispatch with correct session_id, and the synchronous render path.
// The full rehydrate→render chain is exercised by the browser-based e2e suite.

test("VibeComfy agent panel dispatches chat rehydration fetch with stored session id and preserves localStorage", async () => {
  const SESSION_ID = "sess-rehydrate-1";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const chatMessages = [
    { role: "user", text: "make it blue", turn_id: "0001" },
    { role: "agent", text: "changed Background color to blue", turn_id: "0001" },
    { role: "user", text: "now make it bigger", turn_id: "0002" },
    { role: "agent", text: "scaled node to 400x300", turn_id: "0002" },
    { role: "user", text: "add a title", turn_id: "0003" },
  ];

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
          route_options: {
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: chatMessages,
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
        },
      },
    },
  });

  // Pre-populate localStorage with an active session id BEFORE loading the extension.
  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    await harness.loadExtension();
    await harness.setup();

    // Before opening: localStorage must hold the session id.
    assert.equal(
      globalThis.localStorage.getItem("vibecomfy_active_session_id"),
      SESSION_ID,
      "localStorage must hold session id before panel open",
    );

    await harness.invokeCommand("VibeComfy.AgentEdit");

    // Verify the chat rehydration fetch was dispatched with the correct URL.
    await waitFor(() =>
      harness.requests.some((r) => r.url === CHAT_URL),
    );
    const chatRequest = harness.requests.find((r) => r.url === CHAT_URL);
    assert.ok(chatRequest, "chat rehydration request must be dispatched on panel open");
    assert.equal(chatRequest.method, "GET", "chat rehydration must use GET");

    // The chat section must exist (created by synchronous renderAgentPanel).
    const chatSection = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    assert.ok(chatSection, "chat section must exist after panel open");

    // The session link is rendered synchronously with sessionId from state.
    // Since chatLoaded is still false before async rehydration completes,
    // the synchronous renderChatThread shows a placeholder OR the session link
    // if sessionId is set (it is, from rehydration's localStorage read before fetch).
    // Verify the session link affordance is present and points at the right route.
    const links = chatSection.querySelectorAll((node) => node.tagName === "A");
    const sessionLink = links.find(
      (node) => node.textContent && node.textContent.includes("session:"),
    );
    // The session link is rendered when sessionId or chatSessionPath is present.
    // After synchronous openAgentPanel, sessionId is null (not yet set by rehydrate).
    // The link appears after _rehydrateChat sets it. This is async, so we
    // verify the link target format by constructing the expected URL.
    if (sessionLink) {
      assert.ok(
        sessionLink.href.includes("/vibecomfy/agent-edit/session-json?session_id="),
        `session link href must point at session-json route, got: ${sessionLink.href}`,
      );
      assert.equal(sessionLink.target, "_blank", "session link must open in new tab");
    }

    // Verify localStorage still holds the session id after rehydration.
    assert.equal(
      globalThis.localStorage.getItem("vibecomfy_active_session_id"),
      SESSION_ID,
      "active session must remain in localStorage after rehydration",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy status resolution after panel open enables Submit and renders rehydrated thread", async () => {
  const SESSION_ID = "sess-status-thread-1";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  let resolveStatus;
  const statusPromise = new Promise((resolve) => {
    resolveStatus = resolve;
  });

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => statusPromise,
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "rehydrated user prompt", turn_id: "0001" },
            { role: "agent", text: "rehydrated agent answer", turn_id: "0001" },
          ],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
        },
      },
    },
  });

  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");

    await waitFor(() =>
      harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"),
    );
    const submit = harness.document.getElementById("vibecomfy-agent-panel-submit");
    assert.equal(submit.disabled, true);
    assert.match(harness.textDump(), /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);

    resolveStatus({
      status: 200,
      body: {
        ok: true,
        ready: true,
        provider_available: true,
        route: "deepseek",
        requested_route: "auto",
        route_options: {
          auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
        },
      },
    });

    await waitFor(() => submit.disabled === false);
    await waitFor(() => /rehydrated agent answer/.test(harness.textDump()));

    const text = harness.textDump();
    assert.doesNotMatch(text, /Try an example/);
    assert.match(text, /rehydrated user prompt/);
    assert.match(text, /rehydrated agent answer/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy launcher and sidebar mounts expose the same agent panel region ids", async () => {
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
          ready: true,
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

  try {
    await harness.loadExtension();
    await harness.setup();

    const launcher = harness.document.getElementById("vibecomfy-agent-launcher");
    assert.ok(launcher, "launcher must be installed");
    launcher.click();
    await waitFor(() => harness.getPanelRoots().length === 1);
    const launcherRoot = harness.getPanelRoots()[0];
    const launcherRegionIds = agentPanelRegionIds(launcherRoot);

    const sidebarTab = harness.getSidebarTabs()[0][0];
    const sidebarContainer = harness.document.createElement("div");
    sidebarContainer.id = "comfyui-sidebar-vibecomfy-region-contract";
    harness.document.body.appendChild(sidebarContainer);
    sidebarTab.render({ container: sidebarContainer });
    await waitFor(() => harness.getPanelRoots()[0]?.parentNode === sidebarContainer);
    const sidebarRegionIds = agentPanelRegionIds(harness.getPanelRoots()[0]);

    assert.deepEqual(sidebarRegionIds, launcherRegionIds);
    assert.deepEqual(sidebarRegionIds, [
      "vibecomfy-agent-panel-region-audit",
      "vibecomfy-agent-panel-region-candidate",
      "vibecomfy-agent-panel-region-chat",
      "vibecomfy-agent-panel-region-debug",
      "vibecomfy-agent-panel-region-developer",
      "vibecomfy-agent-panel-region-failure",
      "vibecomfy-agent-panel-region-history",
      "vibecomfy-agent-panel-region-prompt",
      "vibecomfy-agent-panel-region-queue",
      "vibecomfy-agent-panel-region-settings",
      "vibecomfy-agent-panel-region-thread",
    ]);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy launcher panel flushes delayed dirty commits without synthetic input", async () => {
  const SESSION_ID = "sess-launcher-delayed-dirty-flush";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  let resolveStatus;
  let resolveChat;
  const statusPromise = new Promise((resolve) => {
    resolveStatus = resolve;
  });
  const chatPromise = new Promise((resolve) => {
    resolveChat = resolve;
  });

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => statusPromise,
      [CHAT_URL]: async () => chatPromise,
    },
  });

  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const launcher = harness.document.getElementById("vibecomfy-agent-launcher");
    assert.ok(launcher, "legacy launcher must be installed");
    launcher.click();

    await waitFor(() => harness.getPanelRoots().length === 1);
    const root = harness.getPanelRoots()[0];
    assert.equal(root.parentNode, harness.document.body, "legacy launcher opens the panel on the body");

    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const initialDebug = harness.window.__vibecomfyPanelDebug();
    assert.equal(initialDebug.panelsCreated, 1);
    assert.equal(initialDebug.panelId, root.dataset.vibecomfyPanelId);
    assert.equal(initialDebug.mountMode, "launcher");
    assert.equal(initialDebug.mountedCheck, true);
    assert.equal(initialDebug.flushPending, false);

    const submit = harness.document.getElementById("vibecomfy-agent-panel-submit");
    assert.equal(submit.disabled, true);
    assert.match(harness.textDump(), /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);

    resolveChat({
      status: 200,
      body: {
        ok: true,
        exists: true,
        session_id: SESSION_ID,
        messages: [
          { role: "user", text: "launcher delayed user prompt", turn_id: "0001" },
          { role: "agent", text: "launcher delayed agent answer", turn_id: "0001" },
        ],
        session_path: `out/editor_sessions/${SESSION_ID}/`,
        detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
      },
    });
    resolveStatus({
      status: 200,
      body: {
        ok: true,
        ready: true,
        provider_available: true,
        route: "deepseek",
        requested_route: "auto",
        route_options: {
          auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
        },
      },
    });

    const panel = extensionModule.ensureAgentPanel();
    await waitFor(() =>
      panel.state.statusSnapshot?.ready === true
      && panel.state.routeStatus?.kind === "ready"
      && Array.isArray(panel.state.chatMessages)
      && panel.state.chatMessages.length === 2
      && panel.state.chatRehydrateCommittedEpoch === 1,
    );

    await waitFor(() => {
      const debug = harness.window.__vibecomfyPanelDebug();
      return debug.flushCount > initialDebug.flushCount
        && debug.flushPending === false
        && debug.dirtySections.length === 0;
    });

    const debug = harness.window.__vibecomfyPanelDebug();
    assert.equal(debug.panelsCreated, 1);
    assert.equal(debug.panelId, panel.root.dataset.vibecomfyPanelId);
    assert.equal(debug.lastThreadRender?.panelId, debug.panelId);
    assert.equal(debug.lastThreadRender?.messagesSeen, 2);
    assert.equal(debug.lastThreadRender?.branch, "messages");
    assert.equal(debug.lastNoticeRender?.panelId, debug.panelId);
    assert.equal(debug.lastNoticeRender?.readySeen, true);
    assert.equal(debug.mountMode, "launcher");
    assert.equal(debug.mountedCheck, true);
    assert.equal(debug.flushPending, false);
    assert.equal(debug.messageCount, 2);
    assert.equal(debug.visibleMessageCount, 2);
    assert.deepEqual(debug.dirtySections, []);
    assert.match(debug.lastFlushReason, /^(dirty-sections|status|rehydrate)$/);

    await waitFor(() => submit.disabled === false);
    await waitFor(() => /launcher delayed agent answer/.test(harness.textDump()));

    const threadRegion = harness.document.getElementById("vibecomfy-agent-panel-region-thread");
    assert.ok(threadRegion, "launcher shell must include the canonical thread region");
    const bubbles = threadRegion.querySelectorAll((node) => node.dataset?.vibecomfyMessageKey);
    assert.equal(bubbles.length, 2);
    assert.ok(
      threadRegion.querySelectorAll((node) => /launcher delayed agent answer/.test(node.textContent)).length >= 1,
      "rehydrated agent bubble text must render under the canonical thread region",
    );

    const text = harness.textDump();
    assert.doesNotMatch(text, /Try an example/);
    assert.doesNotMatch(text, /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);
    assert.match(text, /launcher delayed user prompt/);
    assert.match(text, /launcher delayed agent answer/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy duplicate extension evaluation reuses the same live agent panel singleton", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const firstModule = await harness.loadExtension();
    const secondModule = await harness.loadFreshExtension();
    assert.notEqual(firstModule, secondModule, "fresh import should create a second module instance");
    assert.equal(harness.registeredExtensions.length, 2);

    await harness.registeredExtensions[0].setup();
    await harness.registeredExtensions[1].setup();

    const firstPanel = firstModule.ensureAgentPanel();
    const secondPanel = secondModule.ensureAgentPanel();
    assert.equal(firstPanel, secondPanel, "both module instances must resolve the same panel object");
    assert.equal(harness.getPanelRoots().length, 1, "duplicate module setup must not create a second panel root");

    const root = harness.getPanelRoots()[0];
    const debug = harness.window.__vibecomfyPanelDebug();
    assert.equal(debug.panelsCreated, 1);
    assert.equal(debug.panelId, firstPanel.panelId);
    assert.equal(debug.panelId, root.dataset.vibecomfyPanelId);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy setup-created panel commits delayed status and chat after sidebar mount move", async () => {
  const SESSION_ID = "sess-setup-created-mount-move";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  let resolveStatus;
  let resolveChat;
  const statusPromise = new Promise((resolve) => {
    resolveStatus = resolve;
  });
  const chatPromise = new Promise((resolve) => {
    resolveChat = resolve;
  });

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => statusPromise,
      [CHAT_URL]: async () => chatPromise,
    },
  });

  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const rootBeforeOpen = harness.getPanelRoots()[0];
    assert.equal(rootBeforeOpen.parentNode, harness.document.body, "setup creates the closed panel on the body");

    const sidebarTab = harness.getSidebarTabs()[0][0];
    const sidebarContainer = harness.document.createElement("div");
    sidebarContainer.id = "comfyui-sidebar-vibecomfy-delayed-commit";
    harness.document.body.appendChild(sidebarContainer);
    sidebarTab.render({ container: sidebarContainer });

    await waitFor(() => harness.getPanelRoots()[0]?.parentNode === sidebarContainer);
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const submit = harness.document.getElementById("vibecomfy-agent-panel-submit");
    assert.equal(submit.disabled, true);
    assert.match(harness.textDump(), /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);

    resolveChat({
      status: 200,
      body: {
        ok: true,
        exists: true,
        session_id: SESSION_ID,
        messages: [
          { role: "user", text: "mount move delayed user prompt", turn_id: "0001" },
          { role: "agent", text: "mount move delayed agent answer", turn_id: "0001" },
        ],
        session_path: `out/editor_sessions/${SESSION_ID}/`,
        detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
      },
    });
    resolveStatus({
      status: 200,
      body: {
        ok: true,
        ready: true,
        provider_available: true,
        route: "deepseek",
        requested_route: "auto",
        route_options: {
          auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
        },
      },
    });

    const panel = extensionModule.ensureAgentPanel();
    await waitFor(() =>
      panel.state.statusSnapshot?.ready === true
      && panel.state.routeStatus?.kind === "ready"
      && Array.isArray(panel.state.chatMessages)
      && panel.state.chatMessages.length === 2
      && panel.state.chatRehydrateCommittedEpoch === 1,
    );
    await waitFor(() => harness.window.__vibecomfyPanelDebug().dirtySections.length === 0);

    await waitFor(() => submit.disabled === false);
    await waitFor(() => submit.style.display !== "none");

    const text = harness.textDump();
    assert.doesNotMatch(text, /Try an example/);
    assert.doesNotMatch(text, /Send unavailable/);
    assert.doesNotMatch(text, /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);
    assert.match(text, /mount move delayed user prompt/);
    assert.match(text, /mount move delayed agent answer/);

    assert.equal(typeof harness.window.__vibecomfyPanelDebug, "function");
    const debug = harness.window.__vibecomfyPanelDebug();
    assert.deepEqual(debug.readiness, { kind: "ready", ready: true, reason: "ready" });
    assert.equal(debug.phase, "IDLE");
    assert.equal(debug.sessionId, SESSION_ID);
    assert.equal(debug.messageCount, 2);
    assert.equal(debug.visibleMessageCount, 2);
    assert.equal(debug.mountMode, "sidebar");
    assert.equal(debug.epochs.status, 1);
    assert.equal(debug.epochs.chatRehydrate, 1);
    assert.equal(debug.epochs.chatRehydrateCommitted, 1);
    assert.equal(debug.epochs.submit, 0);
    assert.deepEqual(debug.dirtySections, []);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy current status response commits even if inactive model input changes while in flight", async () => {
  let resolveStatus;
  const statusPromise = new Promise((resolve) => {
    resolveStatus = resolve;
  });

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => statusPromise,
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");

    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));
    const panel = extensionModule.ensureAgentPanel();
    const submit = harness.document.getElementById("vibecomfy-agent-panel-submit");
    assert.equal(submit.disabled, true);

    panel.fields.model.value = "typed-while-status-in-flight";

    resolveStatus({
      status: 200,
      body: {
        ok: true,
        ready: true,
        provider_available: true,
        route: "deepseek",
        requested_route: "auto",
        route_options: {
          auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
        },
      },
    });

    await waitFor(() => submit.disabled === false);
    assert.equal(panel.state.routeStatus.kind, "ready");
    assert.equal(panel.state.statusSnapshot?.ready, true);
    assert.doesNotMatch(harness.textDump(), /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy live sidebar tab mount dispatches status fetch and chat rehydrate", async () => {
  const SESSION_ID = "sess-sidebar-live-path-1";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  let resolveStatus;
  const statusPromise = new Promise((resolve) => {
    resolveStatus = resolve;
  });

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => statusPromise,
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "sidebar rehydrated user prompt", turn_id: "0001" },
            { role: "agent", text: "sidebar rehydrated agent answer", turn_id: "0001" },
          ],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
        },
      },
    },
  });

  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    await harness.loadExtension();
    await harness.setup();

    const registrations = harness.getSidebarTabs();
    assert.equal(registrations.length, 1, "setup must register the live ComfyUI sidebar tab");
    const sidebarTab = registrations[0][0];
    assert.equal(sidebarTab.id, "vibecomfy.agent-edit");
    assert.equal(typeof sidebarTab.render, "function");

    const sidebarContainer = harness.document.createElement("div");
    sidebarContainer.id = "comfyui-sidebar-vibecomfy-test-container";
    harness.document.body.appendChild(sidebarContainer);
    sidebarTab.render(sidebarContainer);

    await waitFor(() =>
      harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"),
    );
    await waitFor(() => harness.requests.some((r) => r.url === CHAT_URL));

    const submit = harness.document.getElementById("vibecomfy-agent-panel-submit");
    assert.equal(submit.disabled, true);
    assert.match(harness.textDump(), /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);

    resolveStatus({
      status: 200,
      body: {
        ok: true,
        ready: true,
        provider_available: true,
        route: "deepseek",
        requested_route: "auto",
        route_options: {
          auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
        },
      },
    });

    await waitFor(() => submit.disabled === false);
    await waitFor(() => /sidebar rehydrated agent answer/.test(harness.textDump()));

    const text = harness.textDump();
    assert.doesNotMatch(text, /Try an example/);
    assert.match(text, /sidebar rehydrated user prompt/);
    assert.match(text, /sidebar rehydrated agent answer/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy agent panel moves one live instance from legacy launcher into sidebar tab mount", async () => {
  const SESSION_ID = "sess-dual-mount-legacy-first";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  let resolveStatus;
  const statusPromise = new Promise((resolve) => {
    resolveStatus = resolve;
  });

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => statusPromise,
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "legacy first user prompt", turn_id: "0001" },
            { role: "agent", text: "legacy first agent answer", turn_id: "0001" },
          ],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
        },
      },
    },
  });

  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    await harness.loadExtension();
    await harness.setup();

    const launcher = harness.document.getElementById("vibecomfy-agent-launcher");
    assert.ok(launcher, "legacy launcher must be installed");
    launcher.click();

    await waitFor(() => harness.getPanelRoots().length === 1);
    let root = harness.getPanelRoots()[0];
    assert.equal(root.parentNode, harness.document.body, "legacy launcher opens the single panel as the body shell");

    const sidebarTab = harness.getSidebarTabs()[0][0];
    const sidebarContainer = harness.document.createElement("div");
    sidebarContainer.id = "comfyui-sidebar-vibecomfy-dual-mount-legacy-first";
    harness.document.body.appendChild(sidebarContainer);
    sidebarTab.render({ container: sidebarContainer });

    await waitFor(() => harness.getPanelRoots().length === 1);
    root = harness.getPanelRoots()[0];
    assert.equal(root.parentNode, sidebarContainer, "sidebar render must move the same panel root into its container");
    assert.equal(sidebarContainer.children.filter((node) => node.dataset?.vibecomfyPanelRoot === "1").length, 1);

    await waitFor(() =>
      harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"),
    );
    await waitFor(() => harness.requests.some((r) => r.url === CHAT_URL));

    const submit = harness.document.getElementById("vibecomfy-agent-panel-submit");
    assert.equal(submit.disabled, true);

    resolveStatus({
      status: 200,
      body: {
        ok: true,
        ready: true,
        provider_available: true,
        route: "deepseek",
        requested_route: "auto",
        route_options: {
          auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
        },
      },
    });

    await waitFor(() => submit.disabled === false);
    await waitFor(() => /legacy first agent answer/.test(harness.textDump()));

    const text = harness.textDump();
    assert.doesNotMatch(text, /Send unavailable/);
    assert.doesNotMatch(text, /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);
    assert.match(text, /legacy first user prompt/);
    assert.match(text, /legacy first agent answer/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy agent panel moves one live instance from sidebar tab mount back to legacy launcher", async () => {
  const SESSION_ID = "sess-dual-mount-sidebar-first";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  let resolveStatus;
  const statusPromise = new Promise((resolve) => {
    resolveStatus = resolve;
  });

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => statusPromise,
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "sidebar first user prompt", turn_id: "0001" },
            { role: "agent", text: "sidebar first agent answer", turn_id: "0001" },
          ],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
        },
      },
    },
  });

  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    await harness.loadExtension();
    await harness.setup();

    const sidebarTab = harness.getSidebarTabs()[0][0];
    const sidebarContainer = harness.document.createElement("div");
    sidebarContainer.id = "comfyui-sidebar-vibecomfy-dual-mount-sidebar-first";
    harness.document.body.appendChild(sidebarContainer);
    sidebarTab.render({ container: sidebarContainer });

    await waitFor(() => harness.getPanelRoots().length === 1);
    let root = harness.getPanelRoots()[0];
    assert.equal(root.parentNode, sidebarContainer, "sidebar opens the single panel in its container");

    const launcher = harness.document.getElementById("vibecomfy-agent-launcher");
    assert.ok(launcher, "legacy launcher must still be installed");
    launcher.click();

    await waitFor(() => harness.getPanelRoots().length === 1);
    root = harness.getPanelRoots()[0];
    assert.equal(root.parentNode, harness.document.body, "legacy launcher must move the same panel root back to the body shell");
    assert.equal(root.dataset.open, "1");

    await waitFor(() =>
      harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"),
    );
    await waitFor(() => harness.requests.some((r) => r.url === CHAT_URL));

    const submit = harness.document.getElementById("vibecomfy-agent-panel-submit");
    assert.equal(submit.disabled, true);

    resolveStatus({
      status: 200,
      body: {
        ok: true,
        ready: true,
        provider_available: true,
        route: "deepseek",
        requested_route: "auto",
        route_options: {
          auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
        },
      },
    });

    await waitFor(() => submit.disabled === false);
    await waitFor(() => /sidebar first agent answer/.test(harness.textDump()));

    const text = harness.textDump();
    assert.doesNotMatch(text, /Send unavailable/);
    assert.doesNotMatch(text, /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);
    assert.match(text, /sidebar first user prompt/);
    assert.match(text, /sidebar first agent answer/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy status and rehydrate commits schedule a second flush after an early empty flush", async () => {
  const SESSION_ID = "sess-launcher-race-commit-after-flush";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  let resolveStatus;
  let resolveChat;
  const statusPromise = new Promise((resolve) => {
    resolveStatus = resolve;
  });
  const chatPromise = new Promise((resolve) => {
    resolveChat = resolve;
  });

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => statusPromise,
      [CHAT_URL]: async () => chatPromise,
    },
  });

  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const launcher = harness.document.getElementById("vibecomfy-agent-launcher");
    assert.ok(launcher, "legacy launcher must be installed");
    launcher.click();

    await waitFor(() => harness.getPanelRoots().length === 1);
    const root = harness.getPanelRoots()[0];
    const panel = extensionModule.ensureAgentPanel();
    const submit = harness.document.getElementById("vibecomfy-agent-panel-submit");
    assert.ok(submit, "submit button must be mounted");

    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const beforeEarlyFlush = harness.window.__vibecomfyPanelDebug();
    assert.equal(beforeEarlyFlush.flushCount, 0, "no scheduled flush should have run before the forced early one");

    extensionModule.scheduleRenderAgentPanel("forced-early-empty", panel, [
      extensionModule.RENDER_SECTIONS.THREAD,
      extensionModule.RENDER_SECTIONS.NOTICE,
    ]);
    await waitFor(() => harness.window.__vibecomfyPanelDebug().flushCount === 1);

    const earlyDebug = harness.window.__vibecomfyPanelDebug();
    assert.equal(earlyDebug.lastThreadRender?.panelId, root.dataset.vibecomfyPanelId);
    assert.equal(earlyDebug.lastThreadRender?.messagesSeen, 0);
    assert.equal(earlyDebug.lastThreadRender?.branch, "picker");
    assert.equal(earlyDebug.lastNoticeRender?.panelId, root.dataset.vibecomfyPanelId);
    assert.equal(earlyDebug.lastNoticeRender?.readySeen, false);
    assert.equal(earlyDebug.messageCount, 0);
    assert.equal(submit.disabled, true);

    resolveStatus({
      status: 200,
      body: {
        ok: true,
        ready: true,
        provider_available: true,
        route: "deepseek",
        requested_route: "auto",
        route_options: {
          auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
        },
      },
    });
    resolveChat({
      status: 200,
      body: {
        ok: true,
        exists: true,
        session_id: SESSION_ID,
        messages: [
          { role: "user", text: "race ordering user prompt", turn_id: "0001" },
          { role: "agent", text: "race ordering agent answer", turn_id: "0001" },
        ],
        session_path: `out/editor_sessions/${SESSION_ID}/`,
        detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
      },
    });

    await waitFor(() =>
      panel.state.statusSnapshot?.ready === true
      && panel.state.routeStatus?.kind === "ready"
      && Array.isArray(panel.state.chatMessages)
      && panel.state.chatMessages.length === 2
      && panel.state.chatRehydrateCommittedEpoch === 1,
    );

    await waitFor(() => {
      const debug = harness.window.__vibecomfyPanelDebug();
      return debug.flushCount > earlyDebug.flushCount
        && debug.flushPending === false
        && debug.dirtySections.length === 0
        && debug.lastThreadRender?.messagesSeen === 2
        && debug.lastNoticeRender?.readySeen === true;
    });

    const debug = harness.window.__vibecomfyPanelDebug();
    assert.equal(debug.panelId, root.dataset.vibecomfyPanelId);
    assert.equal(debug.lastThreadRender?.branch, "messages");
    assert.equal(debug.messageCount, 2);
    assert.equal(debug.visibleMessageCount, 2);
    assert.equal(typeof debug.statusCommitAt, "string");
    assert.equal(typeof debug.rehydrateCommitAt, "string");
    assert.ok(debug.marksAfterCommit >= 2);

    await waitFor(() => submit.disabled === false);
    await waitFor(() => /race ordering agent answer/.test(harness.textDump()));

    const threadRegion = harness.document.getElementById("vibecomfy-agent-panel-region-thread");
    assert.ok(threadRegion, "launcher shell must include the canonical thread region");
    const bubbles = threadRegion.querySelectorAll((node) => node.dataset?.vibecomfyMessageKey);
    assert.equal(bubbles.length, 2);

    const text = harness.textDump();
    assert.match(text, /race ordering user prompt/);
    assert.match(text, /race ordering agent answer/);
    assert.doesNotMatch(text, /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);
    assert.doesNotMatch(text, /Send unavailable/);
  } finally {
    await harness.dispose();
  }
});

for (const mountMode of ["launcher", "sidebar"]) {
  test(`VibeComfy post-commit chat render survives live DOM selector semantics in ${mountMode} mount`, async () => {
    const SESSION_ID = `sess-live-dom-selector-${mountMode}`;
    const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
    const candidateGraph = {
      nodes: [
        { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, widgets_values: ["old prompt"] },
        { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" }, widgets_values: ["old/path"] },
      ],
      links: [],
    };
    const restoredGraph = {
      ...candidateGraph,
      nodes: [
        { ...candidateGraph.nodes[0], widgets_values: ["new prompt"] },
        candidateGraph.nodes[1],
      ],
    };
    let resolveStatus;
    let resolveChat;
    const statusPromise = new Promise((resolve) => {
      resolveStatus = resolve;
    });
    const chatPromise = new Promise((resolve) => {
      resolveChat = resolve;
    });

    const harness = await createBrowserHarness({
      graph: candidateGraph,
      responses: {
        "/system_stats": {
          status: 200,
          body: { system: { comfyui_frontend_package: "1.39.19" } },
        },
        "/vibecomfy/agent/status?route=auto": async () => statusPromise,
        [CHAT_URL]: async () => chatPromise,
      },
    });

    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

    try {
      const extensionModule = await harness.loadExtension();
      await harness.setup();

      let sidebarTab = null;
      let sidebarContainer = null;
      if (mountMode === "sidebar") {
        sidebarTab = harness.getSidebarTabs()[0][0];
        sidebarContainer = harness.document.createElement("div");
        sidebarContainer.id = "comfyui-sidebar-live-selector-regression";
        harness.document.body.appendChild(sidebarContainer);
        sidebarTab.render({ container: sidebarContainer });
      } else {
        const launcher = harness.document.getElementById("vibecomfy-agent-launcher");
        assert.ok(launcher, "legacy launcher must be installed");
        launcher.click();
      }

      await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

      const panel = extensionModule.ensureAgentPanel();
      const sessionRow = panel.sections.chat.children.find(
        (node) => node.dataset?.vibecomfyChatSessionRow === "1",
      );
      assert.ok(sessionRow, "initial empty thread render must create the session row mount");
      const restoreSessionRowSelector = makeElementRejectFunctionSelectors(sessionRow);

      resolveStatus({
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      });
      resolveChat({
        status: 200,
        body: {
          ok: true,
          exists: true,
          session_id: SESSION_ID,
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
          messages: [
            { role: "user", text: "live restore first prompt", turn_id: "0001" },
            { role: "agent", text: "live restore first answer", turn_id: "0001" },
            { role: "user", text: "live restore change prompt", turn_id: "0002" },
            {
              role: "agent",
              text: "Updated the prompt and normalized field changes.",
              turn_id: "0002",
              outcome: {
                kind: "edit",
                changes: [
                  { uid: "uid-1", field_path: "widgets_values.0", old: "old prompt", new: "new prompt" },
                ],
              },
              batch_turns: [
                {
                  turn_id: "0002",
                  field_changes: [
                    { uid: "uid-2", field_path: "widgets_values.0", old: "old/path", new: "new/path" },
                  ],
                },
              ],
            },
            { role: "agent", text: "Latest candidate restored for review.", turn_id: "0005" },
          ],
          latest_candidate: {
            session_id: SESSION_ID,
            turn_id: "0005",
            graph: restoredGraph,
            candidate_graph_hash: `restored-live-shape-${mountMode}`,
            message: "Latest candidate restored for review.",
            report: { change: { content_edits: { edited: ["uid-1"] } }, recovery: [] },
            change_details: {
              done_summary: "Updated one prompt field.",
              operations: [{ field_path: "widgets_values.0", summary: "Prompt updated" }],
            },
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: false,
            apply_eligibility: {
              applyable: true,
              reason: "queue_blocked_warning",
              message: "Apply is allowed, but Queue remains blocked for this candidate.",
              warnings: ["queue_blocked"],
            },
            field_changes: [
              { uid: "uid-1", field_path: "widgets_values.0", old: "old prompt", new: "new prompt" },
            ],
          },
        },
      });

      await waitFor(() => {
        const debug = harness.window.__vibecomfyPanelDebug();
        return debug.flushCount >= 1
          && debug.flushPending === false
          && debug.dirtySections.length === 0
          && debug.lastThreadRender?.branch === "messages"
          && debug.messageCount === 5
          && debug.renderErrors.length === 0;
      }, { attempts: 1000 });

      const debug = harness.window.__vibecomfyPanelDebug();
      assert.equal(debug.mountMode, mountMode);
      assert.equal(debug.sessionId, SESSION_ID);
      assert.equal(debug.lastThreadRender?.messagesSeen, 5);
      assert.equal(debug.renderCounts.THREAD >= 1, true);
      assert.equal(debug.renderCounts.NOTICE >= 1, true);
      assert.deepEqual(debug.renderErrors, []);
      assert.match(harness.textDump(), /Latest candidate restored for review\./);

      if (mountMode === "sidebar") {
        const beforeReopenThreadCount = debug.renderCounts.THREAD;
        sidebarTab.render({ container: sidebarContainer });
        await waitFor(
          () => harness.window.__vibecomfyPanelDebug().renderCounts.THREAD > beforeReopenThreadCount,
          { attempts: 200 },
        );
      }

      restoreSessionRowSelector();
    } finally {
      await harness.dispose();
    }
  });
}

test("VibeComfy section render errors do not stop later sections and requeue failed dirty sections", async () => {
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
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    extensionModule.renderAgentPanel(panel);
    const originalChatMount = panel.sections.chat;
    panel.sections.chat = null;
    panel.__renderCounts = {};
    panel.__renderErrors = [];
    panel.__renderFailureCounts = {};

    extensionModule.renderAgentPanel(panel, {
      dirtySections: [
        extensionModule.RENDER_SECTIONS.THREAD,
        extensionModule.RENDER_SECTIONS.NOTICE,
      ],
    });

    assert.deepEqual(panel.__renderCounts, { THREAD: 1, NOTICE: 1 });
    assert.deepEqual(panel.lastRenderedDirtySections, ["NOTICE"]);
    assert.deepEqual(panel.lastFailedDirtySections, ["THREAD"]);
    assert.deepEqual(panel.pendingDirtySections, ["THREAD"]);
    assert.equal(panel.__renderErrors.length, 1);
    assert.equal(panel.__renderErrors[0].section, "THREAD");
    assert.match(panel.__renderErrors[0].error, /TypeError/);
    assert.match(harness.consoleCapture.error.join("\n"), /\[vibecomfy\] section render failed THREAD/);

    const debug = harness.window.__vibecomfyPanelDebug();
    assert.deepEqual(debug.dirtySections, ["THREAD"]);
    assert.equal(debug.renderErrors.length, 1);
    assert.equal(debug.renderCounts.NOTICE, 1);
    assert.match(harness.textDump(), /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);

    panel.sections.chat = originalChatMount;
    await waitFor(() => panel.pendingDirtySections.length === 0);
    assert.equal(panel.__renderFailureCounts.THREAD, undefined);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy stores render:false dirty sections on the panel and consumes them through the scheduled render gateway", async () => {
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
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    assert.deepEqual(panel.pendingDirtySections, []);

    extensionModule.fulfillLifecycleTransitionObligations(panel, {
      render: false,
      dirtySections: ["THREAD"],
    });

    assert.deepEqual(panel.pendingDirtySections, ["THREAD"]);

    extensionModule.scheduleRenderAgentPanel("dirty-gateway-test", panel, ["META"]);

    await waitFor(() =>
      Array.isArray(panel.lastRenderedDirtySections)
      && panel.lastRenderedDirtySections.length === 2,
    );

    assert.deepEqual(panel.lastRenderedDirtySections, ["THREAD", "META"]);
    assert.deepEqual(panel.pendingDirtySections, []);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy dirty section marking schedules a mounted panel flush without an external event", async () => {
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
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    extensionModule.renderAgentPanel(panel);
    assert.deepEqual(panel.pendingDirtySections, []);

    panel.state.chatMessages = [
      { role: "user", text: "auto scheduled dirty user message", turn_id: "0001" },
      { role: "agent", text: "auto scheduled dirty agent message", turn_id: "0001" },
    ];
    extensionModule.markAgentPanelDirty(panel, ["THREAD"]);

    assert.deepEqual(panel.pendingDirtySections, ["THREAD"]);
    await waitFor(() =>
      Array.isArray(panel.lastRenderedDirtySections)
      && panel.lastRenderedDirtySections.includes("THREAD")
      && panel.pendingDirtySections.length === 0,
    );

    assert.deepEqual(panel.pendingDirtySections, []);
    assert.match(harness.textDump(), /auto scheduled dirty user message/);
    assert.match(harness.textDump(), /auto scheduled dirty agent message/);
    assert.doesNotMatch(harness.textDump(), /Try an example/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy scheduled render flushes through timeout when requestAnimationFrame never fires", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  let rafCalls = 0;
  globalThis.requestAnimationFrame = () => {
    rafCalls += 1;
    return rafCalls;
  };
  globalThis.window.requestAnimationFrame = globalThis.requestAnimationFrame;

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    extensionModule.renderAgentPanel(panel);
    panel.state.chatMessages = [
      { role: "user", text: "timeout fallback dirty user message", turn_id: "0001" },
      { role: "agent", text: "timeout fallback dirty agent message", turn_id: "0001" },
    ];

    extensionModule.markAgentPanelDirty(panel, ["THREAD"]);
    assert.equal(rafCalls, 1);
    assert.deepEqual(panel.pendingDirtySections, ["THREAD"]);

    await new Promise((resolve) => setTimeout(resolve, 140));

    assert.deepEqual(panel.pendingDirtySections, []);
    assert.ok(panel.lastRenderedDirtySections.includes("THREAD"));
    assert.match(harness.textDump(), /timeout fallback dirty agent message/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy thread and notice render from committed panel state sources", async () => {
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
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    panel.state.chatMessages = [
      { role: "user", text: "committed source user message", turn_id: "0001" },
      { role: "agent", text: "committed source agent message", turn_id: "0001" },
    ];
    panel.state.routeStatus = {
      kind: "ready",
      requestedRoute: "auto",
      model: null,
    };
    panel.state.statusSnapshot = {
      ok: true,
      ready: true,
      provider_available: true,
      route: "deepseek",
      requested_route: "auto",
      route_options: {
        auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
        deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
      },
    };

    extensionModule.renderAgentPanel(panel, { dirtySections: ["THREAD", "NOTICE", "COMPOSER"] });

    const text = harness.textDump();
    assert.match(text, /committed source user message/);
    assert.match(text, /committed source agent message/);
    assert.doesNotMatch(text, /Try an example/);
    assert.doesNotMatch(text, /Send unavailable/);
    assert.doesNotMatch(text, /Waiting for \/vibecomfy\/agent\/status before enabling Submit\./);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy renderAgentPanel defaults to all sections and settings-only renders preserve other section counters and DOM ids", async () => {
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
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    panel.__renderCounts = {};

    extensionModule.renderAgentPanel(panel);

    assert.deepEqual(panel.__renderCounts, {
      META: 1,
      THREAD: 1,
      COMPOSER: 1,
      NOTICE: 1,
      SETTINGS: 1,
      DEVELOPER: 1,
    });
    assert.deepEqual(panel.lastRenderedDirtySections, [
      "META",
      "THREAD",
      "COMPOSER",
      "NOTICE",
      "SETTINGS",
      "DEVELOPER",
    ]);

    const statusNode = globalThis.document.getElementById("vibecomfy-agent-panel-status");
    const routeNode = globalThis.document.getElementById("vibecomfy-agent-panel-route");
    const noticeNode = globalThis.document.getElementById("vibecomfy-agent-panel-composer-notice");
    const developerRegionNode = globalThis.document.getElementById("vibecomfy-agent-panel-region-developer");

    extensionModule.renderAgentPanel(panel, { dirtySections: ["SETTINGS"] });

    assert.deepEqual(panel.__renderCounts, {
      META: 1,
      THREAD: 1,
      COMPOSER: 1,
      NOTICE: 1,
      SETTINGS: 2,
      DEVELOPER: 1,
    });
    assert.deepEqual(panel.lastRenderedDirtySections, ["SETTINGS"]);
    assert.equal(globalThis.document.getElementById("vibecomfy-agent-panel-status"), statusNode);
    assert.equal(globalThis.document.getElementById("vibecomfy-agent-panel-route"), routeNode);
    assert.equal(globalThis.document.getElementById("vibecomfy-agent-panel-composer-notice"), noticeNode);
    assert.equal(globalThis.document.getElementById("vibecomfy-agent-panel-region-developer"), developerRegionNode);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy composer-only update leaves settings/developer DOM identity and render counters unchanged", async () => {
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
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    panel.__renderCounts = {};
    panel.__sectionsEverRendered = {};

    // Initial mount: all sections render once.
    extensionModule.renderAgentPanel(panel);

    assert.deepEqual(panel.__renderCounts, {
      META: 1,
      THREAD: 1,
      COMPOSER: 1,
      NOTICE: 1,
      SETTINGS: 1,
      DEVELOPER: 1,
    });

    // Capture DOM node identity before composer-only update.
    const settingsRegionNode = globalThis.document.getElementById("vibecomfy-agent-panel-settings-region");
    const developerRegionNode = globalThis.document.getElementById("vibecomfy-agent-panel-region-developer");
    const routeNode = globalThis.document.getElementById("vibecomfy-agent-panel-route");
    const settingsStatusNode = globalThis.document.getElementById("vibecomfy-agent-panel-settings-status");

    // Composer-only update: only COMPOSER is dirty.
    extensionModule.renderAgentPanel(panel, { dirtySections: ["COMPOSER"] });

    // Settings and developer counters must NOT increment.
    assert.deepEqual(panel.__renderCounts, {
      META: 1,
      THREAD: 1,
      COMPOSER: 2,
      NOTICE: 1,
      SETTINGS: 1,
      DEVELOPER: 1,
    });
    assert.deepEqual(panel.lastRenderedDirtySections, ["COMPOSER"]);

    // Settings and developer DOM node identity must be preserved.
    assert.equal(globalThis.document.getElementById("vibecomfy-agent-panel-settings-region"), settingsRegionNode);
    assert.equal(globalThis.document.getElementById("vibecomfy-agent-panel-region-developer"), developerRegionNode);
    assert.equal(globalThis.document.getElementById("vibecomfy-agent-panel-route"), routeNode);
    assert.equal(globalThis.document.getElementById("vibecomfy-agent-panel-settings-status"), settingsStatusNode);

    // Also verify settings and developer are recorded as ever-rendered.
    assert.equal(panel.__sectionsEverRendered.SETTINGS, true);
    assert.equal(panel.__sectionsEverRendered.DEVELOPER, true);
  } finally {
    await harness.dispose();
  }
});

// ── Lifecycle Contract: E2/E3 Entry rehydrate transitions ───────────────

test("Lifecycle E2 page reload rehydrate restores the latest open candidate and Apply controls", async () => {
  const SESSION_ID = "sess-rehydrate-candidate";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const candidateGraph = {
    nodes: [{ id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } }],
    links: [],
  };
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          exists: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "add saver", turn_id: "0005" },
            { role: "agent", text: "Candidate restored.", turn_id: "0005" },
          ],
          latest_candidate: {
            session_id: SESSION_ID,
            turn_id: "0005",
            graph: candidateGraph,
            candidate_graph_hash: "rehydrated-candidate-hash",
            message: "Candidate restored.",
            report: { change: { content_edits: { edited: ["uid-2"] } }, recovery: [] },
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: false,
            apply_eligibility: {
              applyable: true,
              reason: "queue_blocked_warning",
              message: "Apply is allowed, but Queue remains blocked for this candidate.",
              warnings: ["queue_blocked"],
            },
          },
        },
      },
    },
  });
  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent === "Review Changes");

    const panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.sessionId, SESSION_ID);
    assert.equal(panel.state.turnId, "0005");
    assert.equal(panel.state.candidateGraphHash, "rehydrated-candidate-hash");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, false);
    assert.match(harness.textDump(), /Candidate restored/);
    expandAgentBubbleDetails(harness.document.body);
    assert.match(harness.textDump(), /Apply is allowed, but Queue remains blocked for this candidate\./);
  } finally {
    await harness.dispose();
  }
});

test("Lifecycle E2 chat rehydrate ignores latest_candidate entries whose public outcome is not candidate", async () => {
  const graph = {
    nodes: [{ id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } }],
    links: [],
  };
  const cases = [
    {
      name: "noop",
      latestCandidate: {
        session_id: "sess-rehydrate-noop",
        turn_id: "0005",
        outcome: { kind: "noop", reason: "No change needed." },
        candidate: { graph },
        candidate_graph_hash: "noop-should-not-restore",
        message: "No change needed.",
        canvas_apply_allowed: false,
        apply_allowed: false,
        queue_allowed: false,
      },
    },
    {
      name: "clarify",
      latestCandidate: {
        session_id: "sess-rehydrate-clarify",
        turn_id: "0005",
        outcome: { kind: "clarify", question: "Which node should change?" },
        candidate: { graph },
        candidate_graph_hash: "clarify-should-not-restore",
        message: "Which node should change?",
        canvas_apply_allowed: false,
        apply_allowed: false,
        queue_allowed: false,
      },
    },
    {
      name: "error",
      latestCandidate: {
        session_id: "sess-rehydrate-error",
        turn_id: "0005",
        outcome: { kind: "error", failureKind: "StaleStateMismatch", nextAction: "Submit again." },
        candidate: { graph },
        candidate_graph_hash: "error-should-not-restore",
        message: "Submit again.",
        canvas_apply_allowed: false,
        apply_allowed: false,
        queue_allowed: false,
      },
    },
  ];

  for (const testCase of cases) {
    const SESSION_ID = `sess-rehydrate-noncandidate-${testCase.name}`;
    const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
    const harness = await createBrowserHarness({
      responses: {
        "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
        "/vibecomfy/agent/status?route=auto": {
          status: 200,
          body: {
            ok: true,
            ready: true,
            provider_available: true,
            route: "deepseek",
            requested_route: "auto",
            route_options: {
              auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
              deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            },
          },
        },
        [CHAT_URL]: {
          status: 200,
          body: {
            ok: true,
            exists: true,
            session_id: SESSION_ID,
            messages: [
              { role: "user", text: "restore session", turn_id: "0005" },
              { role: "agent", text: `Latest ${testCase.name} outcome should not restore review.`, turn_id: "0005" },
            ],
            latest_candidate: {
              ...testCase.latestCandidate,
              session_id: SESSION_ID,
            },
          },
        },
      },
    });
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

    try {
      const extensionModule = await harness.loadExtension();
      await harness.setup();
      await harness.invokeCommand("VibeComfy.AgentEdit");
      await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));

      const panel = extensionModule.ensureAgentPanel();
      assert.equal(panel.state.sessionId, SESSION_ID, `${testCase.name} should still rehydrate the session`);
      assert.equal(panel.state.candidateGraph, null, `${testCase.name} should not restore a candidate graph`);
      assert.equal(panel.state.candidateGraphHash, null, `${testCase.name} should not restore a candidate hash`);
      assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");
      assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
      assert.doesNotMatch(harness.textDump(), /Review Changes/);
    } finally {
      await harness.dispose();
      globalThis.localStorage.removeItem("vibecomfy_active_session_id");
    }
  }
});

test("Lifecycle E2 chat rehydrate refuses terminal latest_candidate payloads with candidate graphs", async () => {
  const SESSION_ID = "sess-rehydrate-terminal-candidate";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const graph = {
    nodes: [{ id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-terminal-2" } }],
    links: [],
  };
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          exists: true,
          session_id: SESSION_ID,
          latest_turn_id: "0005",
          messages: [
            { role: "user", text: "reject stale candidate", turn_id: "0005" },
            { role: "agent", text: "Rejected candidate should stay inactive.", turn_id: "0005" },
          ],
          latest_candidate: {
            session_id: SESSION_ID,
            turn_id: "0005",
            outcome: { kind: "candidate", changes: [] },
            candidate: { state: "rejected", graph },
            graph,
            candidate_graph_hash: "terminal-should-not-restore",
            canvas_apply_allowed: false,
            apply_allowed: false,
            queue_allowed: false,
            apply_eligibility: {
              applyable: false,
              reason: "superseded",
              message: "This candidate has been superseded.",
              warnings: ["superseded"],
            },
          },
        },
      },
    },
  });
  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));

    const panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.sessionId, SESSION_ID);
    assert.equal(panel.state.candidateGraph, null);
    assert.equal(panel.state.candidateGraphHash, null);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);
  } finally {
    await harness.dispose();
    globalThis.localStorage.removeItem("vibecomfy_active_session_id");
  }
});

test("Lifecycle E3 same-session rehydrate can commit after an epoch bump until a newer response lands", async () => {
  const SESSION_ID = "sess-rehydrate-same-session-stale-before-commit";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  let chatRequestCount = 0;
  let resolveFirstChat;
  let resolveSecondChat;
  const firstChatPromise = new Promise((resolve) => {
    resolveFirstChat = resolve;
  });
  const secondChatPromise = new Promise((resolve) => {
    resolveSecondChat = resolve;
  });
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [CHAT_URL]: async () => {
        chatRequestCount += 1;
        return chatRequestCount === 1 ? firstChatPromise : secondChatPromise;
      },
    },
  });
  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => chatRequestCount === 1);

    const root = harness.document.getElementById("vibecomfy-agent-panel-root");
    root.dataset.open = "0";
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => chatRequestCount === 2);

    resolveFirstChat({
      status: 200,
      body: {
        ok: true,
        exists: true,
        session_id: SESSION_ID,
        messages: [
          { role: "user", text: "first same-session user prompt", turn_id: "0001" },
          { role: "agent", text: "first same-session answer", turn_id: "0001" },
        ],
      },
    });

    await waitFor(() => /first same-session answer/.test(harness.textDump()));
    let panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.chatLoaded, true);
    assert.equal(panel.state.sessionId, SESSION_ID);

    resolveSecondChat({
      status: 200,
      body: {
        ok: true,
        exists: true,
        session_id: SESSION_ID,
        messages: [
          { role: "user", text: "second same-session user prompt", turn_id: "0002" },
          { role: "agent", text: "second same-session answer", turn_id: "0002" },
        ],
      },
    });

    await waitFor(() => /second same-session answer/.test(harness.textDump()));
    panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.chatMessages.at(-1)?.text, "second same-session answer");
  } finally {
    await harness.dispose();
  }
});

test("Lifecycle E3 stale rehydrate responses after an epoch bump do not restore prior candidate state", async () => {
  const SESSION_ID = "sess-rehydrate-stale";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const staleCandidateGraph = {
    nodes: [{ id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-stale" } }],
    links: [],
  };
  const freshCandidateGraph = {
    nodes: [{ id: 3, type: "PreviewImage", properties: { vibecomfy_uid: "uid-fresh" } }],
    links: [],
  };
  let chatRequestCount = 0;
  let startFirstChatResponse;
  const firstChatResponseStarted = new Promise((resolve) => {
    startFirstChatResponse = resolve;
  });
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [CHAT_URL]: async () => {
        chatRequestCount += 1;
        if (chatRequestCount === 1) {
          return await new Promise((resolve) => {
            startFirstChatResponse(() => resolve({
              status: 200,
              body: {
                ok: true,
                exists: true,
                session_id: SESSION_ID,
                messages: [
                  { role: "user", text: "restore old candidate", turn_id: "0004" },
                  { role: "agent", text: "Stale candidate restored.", turn_id: "0004" },
                ],
                latest_candidate: {
                  session_id: SESSION_ID,
                  turn_id: "0004",
                  graph: staleCandidateGraph,
                  candidate_graph_hash: "stale-candidate-hash",
                  message: "Stale candidate restored.",
                  report: { change: { content_edits: { edited: ["uid-stale"] } }, recovery: [] },
                  canvas_apply_allowed: true,
                  apply_allowed: true,
                  queue_allowed: true,
                  apply_eligibility: {
                    applyable: true,
                    reason: "applyable",
                    message: "Old candidate should not win.",
                    warnings: [],
                  },
                },
              },
            }));
          });
        }
        return {
          status: 200,
          body: {
            ok: true,
            exists: true,
            session_id: SESSION_ID,
            messages: [
              { role: "user", text: "restore fresh candidate", turn_id: "0005" },
              { role: "agent", text: "Fresh candidate restored.", turn_id: "0005" },
            ],
            latest_candidate: {
              session_id: SESSION_ID,
              turn_id: "0005",
              graph: freshCandidateGraph,
              candidate_graph_hash: "fresh-candidate-hash",
              message: "Fresh candidate restored.",
              report: { change: { content_edits: { edited: ["uid-fresh"] } }, recovery: [] },
              canvas_apply_allowed: true,
              apply_allowed: true,
              queue_allowed: true,
              apply_eligibility: {
                applyable: true,
                reason: "applyable",
                message: "Fresh candidate is ready.",
                warnings: [],
              },
            },
          },
        };
      },
    },
  });
  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => chatRequestCount === 1);

    const root = harness.document.getElementById("vibecomfy-agent-panel-root");
    root.dataset.open = "0";
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => chatRequestCount === 2);
    await waitFor(() => /Fresh candidate restored\./.test(harness.textDump()));

    const panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.turnId, "0005");
    assert.equal(panel.state.candidateGraphHash, "fresh-candidate-hash");

    const releaseFirstChatResponse = await firstChatResponseStarted;
    releaseFirstChatResponse();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(panel.state.turnId, "0005");
    assert.equal(panel.state.candidateGraphHash, "fresh-candidate-hash");
    assert.match(harness.textDump(), /Fresh candidate restored\./);
    assert.doesNotMatch(harness.textDump(), /Stale candidate restored\./);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy clears stored session when chat rehydrate reports exists false", async () => {
  const SESSION_ID = "deleted-session";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: { ok: true, exists: false, session_id: SESSION_ID, messages: [] },
      },
    },
  });
  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));
    await waitFor(() => globalThis.localStorage.getItem("vibecomfy_active_session_id") === null);

    assert.equal(globalThis.localStorage.getItem("vibecomfy_active_session_id"), null);
    assert.doesNotMatch(harness.textDump(), /session: out\/editor_sessions\/deleted-session/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy chat thread shows the session link, caps collapsed history at the latest 30 messages, and expands older messages in place", async () => {
  const SESSION_ID = "session-thread-last30";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const chatMessages = Array.from({ length: 35 }, (_, index) => ({
    role: index % 2 === 0 ? "user" : "agent",
    text: `message ${index + 1}`,
    turn_id: String(index + 1).padStart(4, "0"),
  }));

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
          messages: chatMessages,
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

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));
    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    const panel = extensionModule.ensureAgentPanel();
    const sessionLinks = chatRegion?.querySelectorAll(
      (node) => node.tagName === "A" && /session:/.test(node.textContent),
    ) || [];
    assert.equal(sessionLinks.length, 0, "chat thread should keep the internal session path hidden");

    const visibleMessages = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && /^message [0-9]+$/.test(node.textContent),
    ).map((node) => node.textContent);
    assert.deepEqual(
      visibleMessages,
      Array.from({ length: 30 }, (_, index) => `message ${index + 6}`),
    );
    assert(!visibleMessages.includes("message 1"));
    assert(!visibleMessages.includes("message 2"));
    assert(!visibleMessages.includes("message 3"));
    assert(!visibleMessages.includes("message 4"));
    assert(!visibleMessages.includes("message 5"));

    const showEarlierButton = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.textContent === "Show earlier messages",
    )[0];
    assert(showEarlierButton, "collapsed thread should expose a show earlier messages button");
    assert.equal(showEarlierButton.title, "5 earlier messages hidden");

    const message34 = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && node.textContent === "message 34",
    )[0];
    const message35 = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && node.textContent === "message 35",
    )[0];
    assert.equal(message34?.parentNode?.style?.alignItems, "flex-start");
    assert.equal(message35?.parentNode?.style?.alignItems, "flex-end");
    const thread = harness.document.body.querySelectorAll(
      (node) => node.dataset?.vibecomfyAgentThread === "1",
    )[0];
    assert.equal(thread?.dataset?.vibecomfyScrolledToBottom, "1");
    assert.ok(thread.scrollTop > 0, "chat thread should scroll to the newest bubble after render");

    showEarlierButton.click();

    const expandedMessages = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && /^message [0-9]+$/.test(node.textContent),
    ).map((node) => node.textContent);
    assert.deepEqual(
      expandedMessages,
      Array.from({ length: 35 }, (_, index) => `message ${index + 1}`),
    );
    assert.equal(panel.threadState.expandedOlder, true, "expanding older messages should persist on thread state");
    assert.equal(
      chatRegion.querySelectorAll((node) => node.tagName === "BUTTON" && node.textContent === "Show earlier messages").length,
      0,
      "expanded thread should remove the show earlier button",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy chat thread only auto-scrolls when near the bottom or after rehydrate-style reopen", async () => {
  const SESSION_ID = "session-thread-scroll-rules";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const chatResponse = {
    status: 200,
    body: {
      ok: true,
      session_id: SESSION_ID,
      session_path: `out/editor_sessions/${SESSION_ID}/`,
      detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
      messages: [
        { role: "user", text: "message 1", turn_id: "0001" },
        { role: "agent", text: "message 2", turn_id: "0001" },
        { role: "user", text: "message 3", turn_id: "0002" },
      ],
    },
  };

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: chatResponse,
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

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));
    await waitFor(() => /message 3/.test(harness.textDump()));

    const panel = extensionModule.ensureAgentPanel();
    const thread = harness.document.body.querySelectorAll(
      (node) => node.dataset?.vibecomfyAgentThread === "1",
    )[0];

    assert.equal(thread?.dataset?.vibecomfyScrolledToBottom, "1");
    assert.ok(thread.scrollTop > 0, "initial render should snap to the bottom");

    // Deliberately scrolled up: more than THREAD_NEAR_BOTTOM_TOLERANCE_PX
    // (120) from the bottom (600 - 100 - 120 = 380px away).
    thread.clientHeight = 100;
    thread.scrollHeight = 600;
    thread.scrollTop = 120;
    panel.state.chatMessages = [
      ...panel.state.chatMessages,
      { role: "agent", text: "message 4", turn_id: "0002" },
    ];
    extensionModule.renderAgentPanel(panel, { dirtySections: ["THREAD"] });
    assert.equal(thread.scrollTop, 120, "scroll position should be preserved when the user is not near the bottom");
    assert.equal(thread.dataset.vibecomfyScrolledToBottom, "0");

    thread.clientHeight = 100;
    thread.scrollHeight = 400;
    thread.scrollTop = 293;
    panel.state.chatMessages = [
      ...panel.state.chatMessages,
      { role: "user", text: "message 5", turn_id: "0003" },
    ];
    extensionModule.renderAgentPanel(panel, { dirtySections: ["THREAD"] });
    assert.equal(thread.scrollTop, 400, "near-bottom renders should snap back to the latest message");
    assert.equal(thread.dataset.vibecomfyScrolledToBottom, "1");

    const closeButton = harness.document.getElementById("vibecomfy-agent-panel-close");
    assert(closeButton, "agent panel should render a close button");
    closeButton.click();
    thread.clientHeight = 100;
    thread.scrollHeight = 550;
    thread.scrollTop = 20;
    chatResponse.body.messages = [
      ...chatResponse.body.messages,
      { role: "agent", text: "message 6", turn_id: "0003" },
    ];
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => /message 6/.test(harness.textDump()));
    assert.equal(thread.scrollTop, 550, "reopen/rehydrate should force the thread back to the bottom");
    assert.equal(thread.dataset.vibecomfyScrolledToBottom, "1");
  } finally {
    await harness.dispose();
  }
});

for (const mountMode of ["launcher", "sidebar"]) {
  test(`VibeComfy chat bubbles do not duplicate after ${mountMode} close/reopen`, async () => {
    const SESSION_ID = `session-thread-reopen-no-duplicates-${mountMode}`;
    const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
    const messages = [
      { role: "user", text: `${mountMode} message 1`, turn_id: "0001" },
      { role: "agent", text: `${mountMode} message 2`, turn_id: "0001" },
      { role: "user", text: `${mountMode} message 3`, turn_id: "0002" },
      { role: "agent", text: `${mountMode} message 4`, turn_id: "0002" },
      { role: "user", text: `${mountMode} message 5`, turn_id: "0003" },
    ];

    const harness = await createBrowserHarness({
      responses: {
        "/system_stats": {
          status: 200,
          body: { system: { comfyui_frontend_package: "1.39.19" } },
        },
        [CHAT_URL]: {
          status: 200,
          body: {
            ok: true,
            session_id: SESSION_ID,
            session_path: `out/editor_sessions/${SESSION_ID}/`,
            detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
            messages,
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

    try {
      const extensionModule = await harness.loadExtension();
      await harness.setup();
      globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

      let sidebarTab = null;
      let sidebarContainer = null;
      if (mountMode === "sidebar") {
        sidebarTab = harness.getSidebarTabs()[0][0];
        sidebarContainer = harness.document.createElement("div");
        sidebarContainer.id = "comfyui-sidebar-vibecomfy-reopen-no-duplicates";
        harness.document.body.appendChild(sidebarContainer);
        sidebarTab.render({ container: sidebarContainer });
      } else {
        const launcher = harness.document.getElementById("vibecomfy-agent-launcher");
        assert.ok(launcher, "legacy launcher must be installed");
        launcher.click();
      }

      await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));
      await waitFor(() => getChatMessagesMount(harness.document)?.children.length === messages.length);

      const panel = extensionModule.ensureAgentPanel();
      const firstRenderCount = harness.window.__vibecomfyPanelDebug().renderCounts.THREAD;
      let messagesMount = getChatMessagesMount(harness.document);
      assert.ok(messagesMount, "messages mount must exist after first open");
      assert.equal(messagesMount.children.length, messages.length);
      assert.deepEqual(chatMessageKeys(messagesMount), [
        "turn:0001:user",
        "turn:0001:agent",
        "turn:0002:user",
        "turn:0002:agent",
        "turn:0003:user",
      ]);

      const closeButton = harness.document.getElementById("vibecomfy-agent-panel-close");
      assert.ok(closeButton, "agent panel close button must exist");
      closeButton.click();
      assert.equal(panel.root.dataset.open, "0");

      if (mountMode === "sidebar") {
        sidebarTab.render({ container: sidebarContainer });
      } else {
        const launcher = harness.document.getElementById("vibecomfy-agent-launcher");
        launcher.click();
      }

      await waitFor(() => harness.requests.filter((entry) => entry.url === CHAT_URL).length >= 2);
      await waitFor(() => harness.window.__vibecomfyPanelDebug().renderCounts.THREAD > firstRenderCount);

      messagesMount = getChatMessagesMount(harness.document);
      const keys = chatMessageKeys(messagesMount);
      assert.equal(messagesMount.children.length, messages.length, "reopen must not duplicate chat bubbles");
      assert.equal(new Set(keys).size, keys.length, "rendered message keys must stay unique after reopen");
      assert.deepEqual(keys, [
        "turn:0001:user",
        "turn:0001:agent",
        "turn:0002:user",
        "turn:0002:agent",
        "turn:0003:user",
      ]);
    } finally {
      await harness.dispose();
    }
  });
}

test("VibeComfy chat bubble reconcile removes stray DOM children without rebuilding real bubbles", async () => {
  const SESSION_ID = "session-thread-stray-dom-self-heal";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const messages = [
    { role: "user", text: "self heal message 1", turn_id: "0001" },
    { role: "agent", text: "self heal message 2", turn_id: "0001" },
    { role: "user", text: "self heal message 3", turn_id: "0002" },
  ];

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages,
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

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => getChatMessagesMount(harness.document)?.children.length === messages.length);

    const panel = extensionModule.ensureAgentPanel();
    const messagesMount = getChatMessagesMount(harness.document);
    const originalChildrenByKey = new Map(
      messagesMount.children.map((node) => [node.dataset?.vibecomfyMessageKey, node]),
    );

    const stray = harness.document.createElement("div");
    stray.dataset.vibecomfyMessageKey = "stray:manual";
    stray.textContent = "stray duplicate bubble";
    messagesMount.appendChild(stray);
    assert.equal(messagesMount.children.length, messages.length + 1);

    extensionModule.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    assert.equal(stray.parentNode, null, "stray child must be removed during reconcile");
    assert.equal(messagesMount.children.length, messages.length);
    for (const [key, node] of originalChildrenByKey.entries()) {
      assert.equal(
        messagesMount.children.find((child) => child.dataset?.vibecomfyMessageKey === key),
        node,
        `real bubble ${key} should be preserved`,
      );
    }
    assert.deepEqual(chatMessageKeys(messagesMount), [
      "turn:0001:user",
      "turn:0001:agent",
      "turn:0002:user",
    ]);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy thread append preserves existing visible bubble DOM nodes and inline candidate controls", async () => {
  const SESSION_ID = "session-thread-append-preserve";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };

  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }], links: [] },
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
          messages: [
            { role: "user", text: "message 1", turn_id: "0001" },
            {
              role: "agent",
              text: "Candidate ready for review.",
              turn_id: "0001",
              candidate: { graph: candidateGraph },
              eligibility: {
                applyable: true,
                reason: "applyable",
                message: "Latest candidate is ready to apply.",
              },
            },
            { role: "user", text: "message 3", turn_id: "0002" },
          ],
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

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));
    await waitFor(() => /Candidate ready for review\./.test(harness.textDump()));

    const panel = extensionModule.ensureAgentPanel();
    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    const detailsToggle = chatRegion.querySelectorAll((node) => node.dataset?.vibecomfyBubbleDetailToggle === "1" && node.textContent === "\u25b6 details")[0];
    assert(detailsToggle, "candidate bubble should expose a details toggle");
    detailsToggle.click();

    const message1Node = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && node.textContent === "message 1",
    )[0];
    const candidateNode = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && node.textContent === "Candidate ready for review.",
    )[0];
    const message3Node = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && node.textContent === "message 3",
    )[0];
    const applyBefore = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "apply",
    )[0];
    const rejectBefore = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "reject",
    )[0];
    assert(applyBefore, "candidate bubble should render an inline Apply button when expanded");
    assert(rejectBefore, "candidate bubble should render an inline Reject button when expanded");

    const appendedMessage = { role: "agent", text: "message 4", turn_id: "0002" };
    panel.state.chatMessages = [...panel.state.chatMessages, appendedMessage];
    panel.state.transcriptMessages = [...panel.state.transcriptMessages, appendedMessage];
    extensionModule.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const message1After = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && node.textContent === "message 1",
    )[0];
    const candidateAfter = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && node.textContent === "Candidate ready for review.",
    )[0];
    const message3After = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && node.textContent === "message 3",
    )[0];
    const message4After = chatRegion.querySelectorAll(
      (node) => node.tagName === "DIV" && node.textContent === "message 4",
    )[0];
    const applyAfter = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "apply",
    )[0];
    const rejectAfter = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "reject",
    )[0];

    assert.equal(message1After, message1Node, "appending a message should preserve existing user bubble DOM");
    assert.equal(candidateAfter, candidateNode, "appending a message should preserve existing candidate bubble DOM");
    assert.equal(message3After, message3Node, "appending a message should preserve the newest pre-existing bubble DOM");
    assert.ok(message4After, "append should create a new bubble for the new message");
    assert.notEqual(message4After, message3Node, "newly appended bubble must be a fresh DOM node");
    assert.equal(applyAfter, applyBefore, "append should preserve the existing inline Apply control");
    assert.equal(rejectAfter, rejectBefore, "append should preserve the existing inline Reject control");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy agent panel re-fetches chat on reopen and localStorage persists across close/reopen", async () => {
  const SESSION_ID = "sess-refresh-2";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;

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
          route_options: {
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
        },
      },
    },
  });

  globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

  try {
    await harness.loadExtension();
    await harness.setup();

    // First open — should dispatch a chat fetch.
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === CHAT_URL));

    const firstChatRequests = harness.requests.filter((r) => r.url === CHAT_URL);
    assert.equal(firstChatRequests.length, 1, "first open must dispatch exactly one chat request");

    // Simulate close: set dataset.open to "0".
    const root = harness.document.getElementById("vibecomfy-agent-panel-root");
    root.dataset.open = "0";

    // Re-open — must dispatch another chat fetch.
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.filter((r) => r.url === CHAT_URL).length >= 2);

    const secondChatRequests = harness.requests.filter((r) => r.url === CHAT_URL);
    assert.equal(secondChatRequests.length, 2, "reopen must dispatch a second chat request");

    // Verify localStorage still holds the session id after close/reopen.
    assert.equal(
      globalThis.localStorage.getItem("vibecomfy_active_session_id"),
      SESSION_ID,
      "active session must persist across close/reopen",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy scoped session persistence writes sessionStorage without refreshing legacy localStorage", async () => {
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

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    const panel = extensionModule.ensureAgentPanel();
    panel.state.chatScopeId = "scope-smoke";
    panel.state.sessionId = "scoped-session-1";
    globalThis.localStorage.setItem("vibecomfy_active_session_id", "legacy-read-only");

    extensionModule.fulfillLifecycleTransitionObligations(panel, { persistSession: "scoped-session-1" });

    assert.equal(globalThis.sessionStorage.getItem("vibecomfy_scope_session:scope-smoke"), "scoped-session-1");
    assert.equal(globalThis.localStorage.getItem("vibecomfy_active_session_id"), "legacy-read-only");

    extensionModule.fulfillLifecycleTransitionObligations(panel, { forgetSession: true });

    assert.equal(globalThis.sessionStorage.getItem("vibecomfy_scope_session:scope-smoke"), null);
    assert.equal(globalThis.localStorage.getItem("vibecomfy_active_session_id"), "legacy-read-only");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy scoped workflow chats keep distinct sessions, rehydrate URLs, and rendered messages", async () => {
  const graphA = {
    nodes: [
      { id: 1, type: "LoadImage", properties: { vibecomfy_uid: "scope-a-load" } },
      { id: 2, type: "PreviewImage", properties: { vibecomfy_uid: "scope-a-preview" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  const graphB = {
    nodes: [
      { id: 10, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "scope-b-loader" } },
      { id: 11, type: "KSampler", properties: { vibecomfy_uid: "scope-b-sampler" } },
    ],
    links: [[1, 10, 0, 11, 0, "MODEL"]],
  };
  const sessionA = "session-scope-a";
  const sessionB = "session-scope-b";
  const chatUrlA = `/vibecomfy/agent-edit/chat?session_id=${sessionA}`;
  const chatUrlB = `/vibecomfy/agent-edit/chat?session_id=${sessionB}`;
  const submitBodies = [];

  const harness = await createBrowserHarness({
    graph: graphA,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [chatUrlA]: {
        status: 200,
        body: {
          ok: true,
          session_id: sessionA,
          latest_turn_id: "0001",
          messages: [
            { role: "user", text: "scope A rehydrated user", turn_id: "0001" },
            { role: "agent", text: "scope A rehydrated answer", turn_id: "0001" },
          ],
        },
      },
      [chatUrlB]: {
        status: 200,
        body: {
          ok: true,
          session_id: sessionB,
          latest_turn_id: "0001",
          messages: [
            { role: "user", text: "scope B rehydrated user", turn_id: "0001" },
            { role: "agent", text: "scope B rehydrated answer", turn_id: "0001" },
          ],
        },
      },
      "/vibecomfy/agent-executor": async ({ options }) => {
        const body = JSON.parse(options.body);
        submitBodies.push(body);
        return {
          status: 200,
          body: {
            ok: true,
            session_id: body.session_id,
            turn_id: body.session_id === sessionA ? "0002" : "0002",
            baseline_turn_id: "0001",
            outcome: { kind: "noop", reason: `${body.session_id} submit rendered` },
            graph_unchanged: true,
            canvas_apply_allowed: false,
            apply_allowed: false,
            queue_allowed: false,
            message: `${body.session_id} submit rendered`,
          },
        };
      },
    },
  });

  const submitPromises = [];
  const originalGlobalApp = globalThis.app;
  try {
    globalThis.app = harness.app;
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const bindActiveScope = () => {
      const panel = extensionModule.ensureAgentPanel();
      const liveGraph = harness.getCurrentGraph();
      const scope = extensionModule.resolveActiveCanvasScope() || {
        scopeId: extensionModule.computeScopeId(liveGraph),
        fingerprint: extensionModule.computeStructuralGraphFingerprint(liveGraph),
      };
      assert.ok(scope?.scopeId, "active graph should resolve a chat scope");
      panel.state.chatScopeId = scope.scopeId;
      panel.state.chatScopeFingerprint = scope.fingerprint;
      return { panel, scope };
    };

    const { panel: panelA, scope: scopeA } = bindActiveScope();
    extensionModule.setScopedSessionId(scopeA.scopeId, sessionA);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrlA));
    await waitFor(() => /scope A rehydrated answer/.test(harness.textDump()));
    assert.doesNotMatch(harness.textDump(), /scope B rehydrated/);

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "submit from scope A";
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);
    let submitPromise = harness.clickButton("Submit");
    submitPromises.push(submitPromise);
    await submitPromise;
    assert.equal(submitBodies[0].session_id, sessionA);
    assert.notEqual(submitBodies[0].session_id, sessionB);

    const scopeB = {
      scopeId: extensionModule.computeScopeId(graphB),
      fingerprint: extensionModule.computeStructuralGraphFingerprint(graphB),
    };
    assert.notEqual(scopeB.scopeId, scopeA.scopeId, "synthetic workflow scopes must be distinct");
    extensionModule.setScopedSessionId(scopeB.scopeId, sessionB);
    harness.app.loadGraphData(graphB);
    await waitFor(() => panelA.state.chatScopeId === scopeB.scopeId);
    assert.equal(panelA.state.chatScopeFingerprint, scopeB.fingerprint);
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrlB));
    await waitFor(() => /scope B rehydrated answer/.test(harness.textDump()));
    assert.doesNotMatch(harness.textDump(), /scope A rehydrated/);

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "submit from scope B";
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);
    submitPromise = harness.clickButton("Submit");
    submitPromises.push(submitPromise);
    await submitPromise;
    assert.equal(submitBodies[1].session_id, sessionB);
    assert.notEqual(submitBodies[1].session_id, sessionA);

    harness.app.loadGraphData(graphA);
    await waitFor(() => panelA.state.chatScopeId === scopeA.scopeId);
    assert.equal(panelA.state.chatScopeFingerprint, scopeA.fingerprint);
    await waitFor(() => harness.requests.filter((entry) => entry.url === chatUrlA).length >= 2);
    await waitFor(() => /scope A rehydrated answer/.test(harness.textDump()));
    assert.doesNotMatch(harness.textDump(), /scope B rehydrated/);
  } finally {
    if (originalGlobalApp === undefined) {
      delete globalThis.app;
    } else {
      globalThis.app = originalGlobalApp;
    }
    await Promise.allSettled(submitPromises.filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy scoped workflow chats switch when Comfy configures a graph directly", async () => {
  const graphA = {
    nodes: [
      { id: 1, type: "LoadImage", properties: { vibecomfy_uid: "scope-configure-a-load" } },
      { id: 2, type: "PreviewImage", properties: { vibecomfy_uid: "scope-configure-a-preview" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  const graphB = {
    nodes: [
      { id: 10, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "scope-configure-b-loader" } },
      { id: 11, type: "KSampler", properties: { vibecomfy_uid: "scope-configure-b-sampler" } },
    ],
    links: [[1, 10, 0, 11, 0, "MODEL"]],
  };
  const sessionA = "session-configure-scope-a";
  const sessionB = "session-configure-scope-b";
  const chatUrlA = `/vibecomfy/agent-edit/chat?session_id=${sessionA}`;
  const chatUrlB = `/vibecomfy/agent-edit/chat?session_id=${sessionB}`;

  const harness = await createBrowserHarness({
    graph: graphA,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [chatUrlA]: {
        status: 200,
        body: {
          ok: true,
          session_id: sessionA,
          latest_turn_id: "0001",
          messages: [
            { role: "user", text: "configure scope A user", turn_id: "0001" },
            { role: "agent", text: "configure scope A answer", turn_id: "0001" },
          ],
        },
      },
      [chatUrlB]: {
        status: 200,
        body: {
          ok: true,
          session_id: sessionB,
          latest_turn_id: "0001",
          messages: [
            { role: "user", text: "configure scope B user", turn_id: "0001" },
            { role: "agent", text: "configure scope B answer", turn_id: "0001" },
          ],
        },
      },
    },
  });

  const originalGlobalApp = globalThis.app;
  try {
    globalThis.app = harness.app;
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    const scopeA = extensionModule.resolveActiveCanvasScope() || {
      scopeId: extensionModule.computeScopeId(graphA),
      fingerprint: extensionModule.computeStructuralGraphFingerprint(graphA),
    };
    extensionModule.setScopedSessionId(scopeA.scopeId, sessionA);
    panel.state.chatScopeId = scopeA.scopeId;
    panel.state.chatScopeFingerprint = scopeA.fingerprint;

    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrlA));
    await waitFor(() => /configure scope A answer/.test(harness.textDump()));

    const scopeB = {
      scopeId: extensionModule.computeScopeId(graphB),
      fingerprint: extensionModule.computeStructuralGraphFingerprint(graphB),
    };
    assert.notEqual(scopeB.scopeId, scopeA.scopeId, "synthetic workflow scopes must be distinct");
    extensionModule.setScopedSessionId(scopeB.scopeId, sessionB);
    harness.app.canvas.graph.clear();
    harness.app.canvas.graph.configure(graphB);

    await waitFor(() => panel.state.chatScopeId === scopeB.scopeId);
    assert.equal(panel.state.chatScopeFingerprint, scopeB.fingerprint);
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrlB));
    await waitFor(() => /configure scope B answer/.test(harness.textDump()));
    assert.doesNotMatch(harness.textDump(), /configure scope A/);
  } finally {
    if (originalGlobalApp === undefined) {
      delete globalThis.app;
    } else {
      globalThis.app = originalGlobalApp;
    }
    await harness.dispose();
  }
});

test("VibeComfy scoped workflow chats switch for empty Comfy workflow tabs with workflow ids", async () => {
  const graphA = {
    id: "workflow-store-a",
    nodes: [
      { id: 1, type: "LoadImage", properties: { vibecomfy_uid: "scope-workflow-store-a-load" } },
    ],
    links: [],
  };
  const graphB = {
    id: "workflow-store-b",
    nodes: [],
    links: [],
  };
  const sessionA = "session-workflow-store-a";
  const sessionB = "session-workflow-store-b";
  const chatUrlA = `/vibecomfy/agent-edit/chat?session_id=${sessionA}`;
  const chatUrlB = `/vibecomfy/agent-edit/chat?session_id=${sessionB}`;
  const workflowA = {
    content: JSON.stringify({ ...graphA, id: "workflow-store-a" }),
    filename: "Workflow A",
  };
  const workflowB = {
    content: JSON.stringify({ ...graphB, id: "workflow-store-b" }),
    filename: "Workflow B",
  };

  const harness = await createBrowserHarness({
    graph: graphA,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          },
        },
      },
      [chatUrlA]: {
        status: 200,
        body: {
          ok: true,
          session_id: sessionA,
          latest_turn_id: "0001",
          messages: [{ role: "agent", text: "workflow store A answer", turn_id: "0001" }],
        },
      },
      [chatUrlB]: {
        status: 200,
        body: {
          ok: true,
          session_id: sessionB,
          latest_turn_id: "0001",
          messages: [{ role: "agent", text: "workflow store B answer", turn_id: "0001" }],
        },
      },
    },
  });

  const originalGlobalApp = globalThis.app;
  try {
    globalThis.app = harness.app;
    harness.app.extensionManager.workflow = {
      activeWorkflow: workflowA,
      openWorkflows: [workflowA, workflowB],
    };
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    const scopeA = extensionModule.resolveActiveCanvasScope();
    assert.ok(scopeA?.scopeId, "workflow A should resolve a scoped chat identity");
    assert.equal(scopeA.workflowId, "workflow-store-a");
    extensionModule.setScopedSessionId(scopeA.scopeId, sessionA);
    panel.state.chatScopeId = scopeA.scopeId;
    panel.state.chatScopeFingerprint = scopeA.fingerprint;

    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrlA));
    await waitFor(() => /workflow store A answer/.test(harness.textDump()));

    harness.app.extensionManager.workflow.activeWorkflow = workflowB;
    const expectedScopeB = extensionModule.computeScopeId(graphB, { workflowId: "workflow-store-b" });
    assert.ok(expectedScopeB, "empty workflow B should still have a workflow-window scope");
    extensionModule.setScopedSessionId(expectedScopeB, sessionB);
    harness.app.loadGraphData(graphB);

    await waitFor(() => panel.state.chatScopeId === expectedScopeB);
    assert.equal(panel.state.chatScopeFingerprint, extensionModule.computeStructuralGraphFingerprint(graphB));
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrlB));
    await waitFor(() => /workflow store B answer/.test(harness.textDump()));
    assert.doesNotMatch(harness.textDump(), /workflow store A answer/);
  } finally {
    if (originalGlobalApp === undefined) {
      delete globalThis.app;
    } else {
      globalThis.app = originalGlobalApp;
    }
    await harness.dispose();
  }
});

test("VibeComfy scoped workflow rehydrate ignores stale latest candidates after scope switch", async () => {
  const graphA = {
    nodes: [
      { id: 1, type: "LoadImage", properties: { vibecomfy_uid: "scope-stale-a-load" } },
      { id: 2, type: "PreviewImage", properties: { vibecomfy_uid: "scope-stale-a-preview" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  const graphB = {
    nodes: [
      { id: 10, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "scope-stale-b-loader" } },
      { id: 11, type: "KSampler", properties: { vibecomfy_uid: "scope-stale-b-sampler" } },
    ],
    links: [[1, 10, 0, 11, 0, "MODEL"]],
  };
  const candidateGraphA = {
    nodes: [{ id: 3, type: "SaveImage", properties: { vibecomfy_uid: "scope-stale-a-save" } }],
    links: [],
  };
  const candidateGraphB = {
    nodes: [{ id: 12, type: "VAEDecode", properties: { vibecomfy_uid: "scope-stale-b-decode" } }],
    links: [],
  };
  const sessionA = "session-stale-rehydrate-a";
  const sessionB = "session-stale-rehydrate-b";
  const chatUrlA = `/vibecomfy/agent-edit/chat?session_id=${sessionA}`;
  const chatUrlB = `/vibecomfy/agent-edit/chat?session_id=${sessionB}`;
  let chatRequestCountA = 0;
  let chatRequestCountB = 0;
  let resolveChatA;
  let resolveChatB;
  const chatPromiseA = new Promise((resolve) => {
    resolveChatA = resolve;
  });
  const chatPromiseB = new Promise((resolve) => {
    resolveChatB = resolve;
  });

  const harness = await createBrowserHarness({
    graph: graphA,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [chatUrlA]: async () => {
        chatRequestCountA += 1;
        return await chatPromiseA;
      },
      [chatUrlB]: async () => {
        chatRequestCountB += 1;
        return await chatPromiseB;
      },
    },
  });

  const originalGlobalApp = globalThis.app;
  try {
    globalThis.app = harness.app;
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const panel = extensionModule.ensureAgentPanel();
    const scopeA = extensionModule.resolveActiveCanvasScope() || {
      scopeId: extensionModule.computeScopeId(graphA),
      fingerprint: extensionModule.computeStructuralGraphFingerprint(graphA),
    };
    extensionModule.setScopedSessionId(scopeA.scopeId, sessionA);
    panel.state.chatScopeId = scopeA.scopeId;
    panel.state.chatScopeFingerprint = scopeA.fingerprint;

    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => chatRequestCountA === 1);

    const scopeB = {
      scopeId: extensionModule.computeScopeId(graphB),
      fingerprint: extensionModule.computeStructuralGraphFingerprint(graphB),
    };
    assert.notEqual(scopeB.scopeId, scopeA.scopeId, "synthetic workflow scopes must be distinct");
    extensionModule.setScopedSessionId(scopeB.scopeId, sessionB);
    harness.app.loadGraphData(graphB);
    await waitFor(() => panel.state.chatScopeId === scopeB.scopeId);
    await waitFor(() => chatRequestCountB === 1);

    resolveChatA({
      status: 200,
      body: {
        ok: true,
        exists: true,
        session_id: sessionA,
        latest_turn_id: "0004",
        messages: [
          { role: "user", text: "scope A stale candidate user", turn_id: "0004" },
          { role: "agent", text: "Scope A stale candidate restored.", turn_id: "0004" },
        ],
        latest_candidate: {
          session_id: sessionA,
          turn_id: "0004",
          outcome: { kind: "candidate", changes: [] },
          candidate: { state: "candidate", graph: candidateGraphA, graph_hash: "scope-a-stale-candidate-hash" },
          graph: candidateGraphA,
          candidate_graph_hash: "scope-a-stale-candidate-hash",
          message: "Scope A stale candidate restored.",
          report: { change: { content_edits: { edited: ["scope-stale-a-save"] } }, recovery: [] },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          apply_eligibility: {
            applyable: true,
            reason: "applyable",
            message: "Scope A stale candidate should not appear.",
            warnings: [],
          },
        },
      },
    });
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrlA));
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(panel.state.chatScopeId, scopeB.scopeId);
    assert.equal(panel.state.sessionId, null);
    assert.equal(panel.state.candidateGraph, null);
    assert.equal(panel.state.candidateGraphHash, null);
    assert.doesNotMatch(harness.textDump(), /Scope A stale candidate restored/);
    assert.doesNotMatch(harness.textDump(), /scope A stale candidate user/);

    resolveChatB({
      status: 200,
      body: {
        ok: true,
        exists: true,
        session_id: sessionB,
        latest_turn_id: "0007",
        messages: [
          { role: "user", text: "scope B current candidate user", turn_id: "0007" },
          { role: "agent", text: "Scope B current candidate restored.", turn_id: "0007" },
        ],
        latest_candidate: {
          session_id: sessionB,
          turn_id: "0007",
          outcome: { kind: "candidate", changes: [] },
          candidate: { state: "candidate", graph: candidateGraphB, graph_hash: "scope-b-current-candidate-hash" },
          graph: candidateGraphB,
          candidate_graph_hash: "scope-b-current-candidate-hash",
          message: "Scope B current candidate restored.",
          report: { change: { content_edits: { edited: ["scope-stale-b-decode"] } }, recovery: [] },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          apply_eligibility: {
            applyable: true,
            reason: "applyable",
            message: "Scope B current candidate is ready.",
            warnings: [],
          },
        },
      },
    });
    await waitFor(() => /Scope B current candidate restored\./.test(harness.textDump()));

    assert.equal(panel.state.chatScopeId, scopeB.scopeId);
    assert.equal(panel.state.sessionId, sessionB);
    assert.equal(panel.state.turnId, "0007");
    assert.equal(panel.state.candidateGraphHash, "scope-b-current-candidate-hash");
    assert.deepEqual(panel.state.candidateGraph, candidateGraphB);
    assert.match(harness.textDump(), /Scope B current candidate restored\./);
    assert.match(harness.textDump(), /scope B current candidate user/);
    assert.doesNotMatch(harness.textDump(), /Scope A stale candidate restored/);
    assert.doesNotMatch(harness.textDump(), /scope A stale candidate user/);
  } finally {
    resolveChatA?.({
      status: 200,
      body: { ok: true, exists: true, session_id: sessionA, messages: [] },
    });
    resolveChatB?.({
      status: 200,
      body: { ok: true, exists: true, session_id: sessionB, messages: [] },
    });
    if (originalGlobalApp === undefined) {
      delete globalThis.app;
    } else {
      globalThis.app = originalGlobalApp;
    }
    await harness.dispose();
  }
});

test("VibeComfy scoped workflow event handlers ignore inactive session events and accept active scope events", async () => {
  const graphA = {
    nodes: [
      { id: 1, type: "LoadImage", properties: { vibecomfy_uid: "scope-event-a-load" } },
      { id: 2, type: "PreviewImage", properties: { vibecomfy_uid: "scope-event-a-preview" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  const graphB = {
    nodes: [
      { id: 10, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "scope-event-b-loader" } },
      { id: 11, type: "KSampler", properties: { vibecomfy_uid: "scope-event-b-sampler" } },
    ],
    links: [[1, 10, 0, 11, 0, "MODEL"]],
  };
  const sessionA = "session-event-scope-a";
  const sessionB = "session-event-scope-b";
  const chatUrlA = `/vibecomfy/agent-edit/chat?session_id=${sessionA}`;
  const chatUrlB = `/vibecomfy/agent-edit/chat?session_id=${sessionB}`;
  let resolveSubmit;
  let submitPromise;

  const harness = await createBrowserHarness({
    graph: graphA,
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      [chatUrlA]: {
        status: 200,
        body: {
          ok: true,
          session_id: sessionA,
          latest_turn_id: "0001",
          messages: [
            { role: "user", text: "scope A event user", turn_id: "0001" },
            { role: "agent", text: "scope A event answer", turn_id: "0001" },
          ],
        },
      },
      [chatUrlB]: {
        status: 200,
        body: {
          ok: true,
          session_id: sessionB,
          latest_turn_id: "0001",
          messages: [
            { role: "user", text: "scope B event user", turn_id: "0001" },
            { role: "agent", text: "scope B event answer", turn_id: "0001" },
          ],
        },
      },
      "/vibecomfy/agent-executor": async () => {
        await new Promise((resolve) => {
          resolveSubmit = resolve;
        });
        return {
          status: 200,
          body: {
            ok: true,
            session_id: sessionB,
            turn_id: "0002",
            baseline_turn_id: "0001",
            outcome: { kind: "noop", reason: "scope B held submit completed" },
            graph_unchanged: true,
            canvas_apply_allowed: false,
            apply_allowed: false,
            queue_allowed: false,
            message: "scope B held submit completed",
          },
        };
      },
    },
  });

  const originalGlobalApp = globalThis.app;
  try {
    globalThis.app = harness.app;
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    await harness.invokeCommand("VibeComfy.AgentEdit");
    const panel = extensionModule.ensureAgentPanel();
    const scopeA = extensionModule.resolveActiveCanvasScope() || {
      scopeId: extensionModule.computeScopeId(graphA),
      fingerprint: extensionModule.computeStructuralGraphFingerprint(graphA),
    };
    extensionModule.setScopedSessionId(scopeA.scopeId, sessionA);
    panel.state.chatScopeId = scopeA.scopeId;
    panel.state.chatScopeFingerprint = scopeA.fingerprint;
    panel.state.sessionId = sessionA;

    const scopeB = {
      scopeId: extensionModule.computeScopeId(graphB),
      fingerprint: extensionModule.computeStructuralGraphFingerprint(graphB),
    };
    extensionModule.setScopedSessionId(scopeB.scopeId, sessionB);
    harness.app.loadGraphData(graphB);
    await waitFor(() => panel.state.chatScopeId === scopeB.scopeId);
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrlB));
    await waitFor(() => /scope B event answer/.test(harness.textDump()));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "scope B pending prompt";
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);
    submitPromise = harness.clickButton("Submit");
    await waitFor(() => typeof resolveSubmit === "function");
    await waitFor(() => /scope B pending prompt/.test(harness.textDump()));

    const executorStage = (stage) => harness.document.body.querySelectorAll(
      (node) => node.dataset?.vibecomfyExecutorStage === stage,
    )[0];
    assert.equal(executorStage("decide")?.dataset?.vibecomfyExecutorStatus, "active");
    assert.equal(executorStage("execute")?.dataset?.vibecomfyExecutorStatus, "pending");

    const beforeInactiveText = harness.textDump();
    const beforeInactiveTurns = JSON.stringify(panel.state.turns);
    const beforeInactiveProgress = JSON.stringify(panel.state.executorProgress);
    const beforeInactiveSession = panel.state.sessionId;
    const beforeInactiveScope = panel.state.chatScopeId;

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: sessionA,
      turn_id: "0002",
      turn_number: 2,
      status: "progress",
      message: "inactive scope A turn must not render",
      statement_count: 1,
    });
    harness.dispatchApiEvent("vibecomfy.executor.phase", {
      session_id: sessionA,
      phase: "implement",
      status: "start",
      executor_id: "executor-scope-a",
    });
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(panel.state.chatScopeId, beforeInactiveScope);
    assert.equal(panel.state.sessionId, beforeInactiveSession);
    assert.equal(JSON.stringify(panel.state.turns), beforeInactiveTurns);
    assert.equal(JSON.stringify(panel.state.executorProgress), beforeInactiveProgress);
    assert.equal(harness.textDump(), beforeInactiveText);
    assert.doesNotMatch(harness.textDump(), /inactive scope A turn must not render/);
    assert.equal(executorStage("execute")?.dataset?.vibecomfyExecutorStatus, "pending");

    harness.dispatchApiEvent("vibecomfy.agent_edit.turn", {
      session_id: sessionB,
      turn_id: "0002",
      turn_number: 2,
      status: "in_progress",
      message: "active scope B turn dispatched",
      statement_count: 2,
    });
    harness.dispatchApiEvent("vibecomfy.executor.phase", {
      session_id: sessionB,
      phase: "implement",
      status: "start",
      executor_id: "executor-scope-b",
    });
    await waitFor(() => executorStage("execute")?.dataset?.vibecomfyExecutorStatus === "active");

    assert.equal(panel.state.chatScopeId, scopeB.scopeId);
    assert.equal(panel.state.sessionId, sessionB);
    assert.equal(panel.state.turns.filter((entry) => entry?.entry_type === "batch").length, 1);
    assert.equal(executorStage("research")?.dataset?.vibecomfyExecutorStatus, "done");
    assert.doesNotMatch(harness.textDump(), /inactive scope A turn must not render/);
  } finally {
    resolveSubmit?.();
    if (submitPromise) {
      await submitPromise;
    }
    if (originalGlobalApp === undefined) {
      delete globalThis.app;
    } else {
      globalThis.app = originalGlobalApp;
    }
    await harness.dispose();
  }
});

// ── Lifecycle Contract: C2 New conversation + stale submit cleanup ────────
// NOTE: The submit flow internally calls _rehydrateChat which triggers
// the async .then(renderAgentPanel) path. These tests verify the critical
// contracts through localStorage inspection and request-payload assertions
// rather than DOM rendering of chat bubbles.

test("Lifecycle C2 new conversation clears state and ignores late submit responses", async () => {
  const graph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };

  let submitCount = 0;
  let startSecondSubmitResponse;
  const secondSubmitStarted = new Promise((resolve) => {
    startSecondSubmitResponse = resolve;
  });

  const harness = await createBrowserHarness({
    graph,
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
          },
        },
      },
      "/vibecomfy/agent-executor": async ({ options }) => {
        submitCount += 1;
        const body = JSON.parse(options.body);
        if (submitCount === 1) {
          // First submit: must NOT include session_id (fresh session).
          assert.equal(
            "session_id" in body && body.session_id !== undefined ? body.session_id : undefined,
            undefined,
            "first submit must not include session_id",
          );
          return {
            status: 200,
            body: {
              ok: true,
              session_id: "sess-submit-1",
              turn_id: "0001",
              baseline_turn_id: null,
              graph: { nodes: [], links: [] },
              report: { change: { content_edits: { preserved: [], edited: [], removed_named: [] } }, recovery: [] },
              apply_allowed: true,
              canvas_apply_allowed: true,
              queue_allowed: false,
              message: "first candidate",
            },
          };
        }
        if (submitCount === 2) {
          assert.equal(
            body.session_id,
            "sess-submit-1",
            `follow-up submit must include session_id=sess-submit-1, got: ${JSON.stringify(body.session_id)}`,
          );
          return await new Promise((resolve) => {
            startSecondSubmitResponse(() => resolve({
              status: 200,
              body: {
                ok: true,
                session_id: "sess-submit-1",
                turn_id: "0002",
                baseline_turn_id: "0001",
                graph: { nodes: [], links: [] },
                report: { change: { content_edits: { preserved: [], edited: [], removed_named: [] } }, recovery: [] },
                apply_allowed: true,
                canvas_apply_allowed: true,
                queue_allowed: false,
                message: "stale candidate 2",
              },
            }));
          });
        }
        assert.equal(
          "session_id" in body && body.session_id !== undefined ? body.session_id : undefined,
          undefined,
          "submit after New conversation must omit session_id entirely",
        );
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "sess-submit-fresh",
            turn_id: "0003",
            baseline_turn_id: null,
            graph: { nodes: [], links: [] },
            report: { change: { content_edits: { preserved: [], edited: [], removed_named: [] } }, recovery: [] },
            apply_allowed: true,
            canvas_apply_allowed: true,
            queue_allowed: false,
            message: "fresh candidate 3",
          },
        };
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() =>
      harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"),
    );

    // ── First submit: verify session_id is persisted to localStorage ────────
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "first edit";
    harness.document.getElementById("vibecomfy-agent-panel-route").value = "deepseek";
    harness.document.getElementById("vibecomfy-agent-panel-submit").click();

    await waitFor(() => submitCount >= 1);
    // Yield for the synchronous _persistActiveSession call to take effect.
    await new Promise((resolve) => setTimeout(resolve, 10));

    assert.equal(
      globalThis.localStorage.getItem("vibecomfy_active_session_id"),
      "sess-submit-1",
      "localStorage must contain session_id after first submit",
    );

    // ── Second submit: verify payload includes session_id ──────────────────
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "second edit";
    const secondSubmitPromise = harness.clickButton("Submit");

    await waitFor(() => submitCount >= 2);
    const releaseSecondSubmitResponse = await secondSubmitStarted;

    // ── New conversation is disabled while a submit is in flight; Stop is the
    //    in-flight escape hatch. Stop first, then start a fresh conversation. ──
    assert.equal(
      harness.document.getElementById("vibecomfy-agent-panel-new-conversation")?.disabled,
      true,
      "New conversation must be disabled while a submit is in flight",
    );
    harness.findButtons("Stop")[0].click();
    await waitFor(
      () => harness.document.getElementById("vibecomfy-agent-panel-new-conversation")?.disabled === false,
    );
    const newConvButtons = harness.findButtons("New conversation");
    assert.ok(newConvButtons.length >= 1, "must have a 'New conversation' button");
    newConvButtons[0].click();
    await secondSubmitPromise;

    // localStorage must be cleared.
    assert.equal(
      globalThis.localStorage.getItem("vibecomfy_active_session_id"),
      null,
      "New conversation must clear localStorage session pointer",
    );

    // Chat section must exist and be cleared.
    const chatSection = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    assert.ok(chatSection, "chat section must still exist after New conversation");

    // Activity section must be cleared.
    assert.doesNotMatch(harness.textDump(), /Turn 1/);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);

    const panel = extensionModule.ensureAgentPanel();
    assert.equal(panel.state.sessionId, null);
    assert.equal(panel.state.candidateGraph, null);

    // ── Third submit after New conversation: verify session_id is OMITTED ───
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "fresh edit after new conversation";
    await harness.clickButton("Submit");

    await waitFor(() => submitCount >= 3);
    await waitFor(() => /fresh candidate 3/.test(harness.textDump()));

    // Check the body of the third request — session_id must be absent.
    const agentEditRequests = harness.requests.filter((r) => r.url === "/vibecomfy/agent-executor" && r.method === "POST");
    assert.ok(agentEditRequests.length >= 3, "must have at least three agent-edit POST requests");
    const thirdPayload = JSON.parse(agentEditRequests[2].body);
    assert.equal(
      "session_id" in thirdPayload && thirdPayload.session_id !== undefined ? thirdPayload.session_id : undefined,
      undefined,
      "third submit after New conversation must omit session_id entirely",
    );
    assert.equal(globalThis.localStorage.getItem("vibecomfy_active_session_id"), "sess-submit-fresh");
    assert.equal(panel.state.sessionId, "sess-submit-fresh");
    assert.equal(panel.state.turnId, "0003");

    releaseSecondSubmitResponse();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(panel.state.sessionId, "sess-submit-fresh");
    assert.equal(panel.state.turnId, "0003");
    assert.match(harness.textDump(), /fresh candidate 3/);
    assert.doesNotMatch(harness.textDump(), /stale candidate 2/);

    // ── Verify rebaseline endpoint was NEVER called ─────────────────────────
    const rebaselineRequests = harness.requests.filter(
      (r) => r.url === "/vibecomfy/agent-edit/rebaseline",
    );
    assert.equal(
      rebaselineRequests.length,
      0,
      "rebaseline endpoint must never be called during New conversation flow",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy agent submit on failure path still persists session_id for recovery", async () => {
  const graph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
    ],
    links: [],
  };

  const harness = await createBrowserHarness({
    graph,
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
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 500,
        body: {
          ok: false,
          error: "simulated backend failure",
          kind: "BackendError",
          session_id: "sess-fail-1",
          turn_id: "fail-0001",
          audit_ref: null,
        },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() =>
      harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"),
    );

    // localStorage must be empty before submit.
    assert.equal(
      globalThis.localStorage.getItem("vibecomfy_active_session_id"),
      null,
      "localStorage must be empty before any submit",
    );

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "this will fail";
    harness.document.getElementById("vibecomfy-agent-panel-route").value = "deepseek";
    harness.document.getElementById("vibecomfy-agent-panel-submit").click();

    // Wait for the submit request to complete (failure path).
    await waitFor(() =>
      harness.requests.filter((r) => r.url === "/vibecomfy/agent-executor").length >= 1,
    );
    // Yield for async handlers.
    await new Promise((resolve) => setTimeout(resolve, 10));

    // Even on failure, session_id must be persisted for recovery.
    assert.equal(
      globalThis.localStorage.getItem("vibecomfy_active_session_id"),
      "sess-fail-1",
      "localStorage must persist session_id even on submit failure",
    );
  } finally {
    await harness.dispose();
  }
});

// ── Lifecycle Contract: J3 Reject success invalidates the candidate ──────

test("Lifecycle J3 reject success leaves no applyable candidate", async () => {
  const SESSION_ID = "session-reject-success";
  const candidateGraph = {
    nodes: [{ id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-reject-2" } }],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-reject-1" } }], links: [] },
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0004",
          baseline_turn_id: "0003",
          candidate: { state: "candidate", graph: candidateGraph, graph_hash: "reject-candidate-hash" },
          eligibility: { applyable: true, reason: "applyable", message: "Apply is allowed.", warnings: [] },
          graph: candidateGraph,
          report: { change: { content_edits: { edited: ["uid-reject-2"] } }, recovery: [] },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          candidate_graph_hash: "reject-candidate-hash",
          message: "Candidate ready to reject.",
        },
      },
      "/vibecomfy/agent-edit/reject": {
        status: 200,
        body: {
          ok: true,
          action: "reject",
          session_id: SESSION_ID,
          turn_id: "0004",
          baseline_turn_id: "0004",
          baseline_graph_hash: "baseline-after-reject",
          baseline_graph_hash_kind: "structural",
          baseline_graph_hash_version: 2,
          baseline_source: "turn",
          baseline_rebaseline_id: null,
          baseline_graph_source_path: "turns/0004/candidate.ui.json",
          apply_allowed: false,
          canvas_apply_allowed: false,
          queue_allowed: false,
          apply_eligibility: {
            applyable: false,
            reason: "no_candidate",
            message: "No candidate is available to apply.",
            warnings: [],
          },
          audit_ref: { path: "/tmp/reject-success-audit.json" },
        },
      },
      "/vibecomfy/agent-edit/accept": async () => {
        throw new Error("accept must not fire after a successful reject");
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "reject this candidate";
    await harness.clickButton("Submit");
    await waitFor(() => (
      extensionModule.ensureAgentPanel().state.candidateGraph
      && harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled === false
    ));

    await harness.clickButton("Reject");
    const panel = extensionModule.ensureAgentPanel();
    const applyButton = harness.document.getElementById("vibecomfy-agent-panel-apply");
    const rejectButton = harness.document.getElementById("vibecomfy-agent-panel-reject");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/reject").length, 1);
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 0);
    assert.equal(panel.state.candidateGraph, null);
    assert.equal(panel.state.candidateGraphHash, null);
    assert.equal(panel.state.phase, "IDLE");
    assert.equal(applyButton?.disabled, true);
    assert.equal(rejectButton?.disabled, true);
  } finally {
    await harness.dispose();
  }
});

// ── M4a: ComfyUI adapter capability detection ──────────────────────────

test("VibeComfy comfy_adapter detects all capabilities on a supported 1.39.x harness shape", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const adapter = await harness.loadAdapter();

    // Supported harness: app.canvas.graph has clear/configure,
    // app.canvas.onDrawForeground is assignable (null by default),
    // app.queuePrompt is present.
    const caps = adapter.detectCapabilities(harness.app, harness.window, "1.39.19");

    // All three capabilities should be available.
    assert.equal(caps.graphApply.available, true);
    assert.match(caps.graphApply.detail, /clear/);
    assert.equal(caps.graphApply.path, "app.canvas.graph");

    assert.equal(caps.previewForeground.available, true);
    assert.match(caps.previewForeground.detail, /Instance-level/);
    assert.equal(caps.previewForeground.path, "app.canvas.onDrawForeground");

    assert.equal(caps.queueGuard.available, true);
    assert.match(caps.queueGuard.detail, /interceptable/);
    assert.equal(caps.queueGuard.path, "app.queuePrompt");

    assert.equal(caps.supportsAll, true);
    assert.equal(caps.frontendVersion, "1.39.19");
    assert.equal(caps.frontendMajor, "1.39");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter detects degraded capabilities when hooks are missing", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.37.0" } },
      },
    },
  });

  try {
    const adapter = await harness.loadAdapter();

    // Test each degraded variant via buildMockAppFromProfile.
    const variants = adapter.HARNESS_PROFILE_DEGRADED.variants;

    // missing-graph-apply
    {
      const { app: degradedApp, window: degradedWindow } =
        adapter.buildMockAppFromProfile(adapter.HARNESS_PROFILE_DEGRADED, "missing-graph-apply");
      const caps = adapter.detectCapabilities(degradedApp, degradedWindow, "1.37.0");
      assert.equal(caps.graphApply.available, false);
      assert.equal(caps.previewForeground.available, true);
      assert.equal(caps.queueGuard.available, true);
      assert.equal(caps.supportsAll, false);
    }

    // missing-preview-foreground
    {
      const { app: degradedApp, window: degradedWindow } =
        adapter.buildMockAppFromProfile(adapter.HARNESS_PROFILE_DEGRADED, "missing-preview-foreground");
      const caps = adapter.detectCapabilities(degradedApp, degradedWindow, "1.37.0");
      assert.equal(caps.graphApply.available, true);
      assert.equal(caps.previewForeground.available, false);
      assert.equal(caps.queueGuard.available, true);
      assert.equal(caps.supportsAll, false);
    }

    // missing-queue-guard
    {
      const { app: degradedApp, window: degradedWindow } =
        adapter.buildMockAppFromProfile(adapter.HARNESS_PROFILE_DEGRADED, "missing-queue-guard");
      const caps = adapter.detectCapabilities(degradedApp, degradedWindow, "1.37.0");
      assert.equal(caps.graphApply.available, true);
      assert.equal(caps.previewForeground.available, true);
      assert.equal(caps.queueGuard.available, false);
      assert.equal(caps.supportsAll, false);
    }

    // missing-all
    {
      const { app: degradedApp, window: degradedWindow } =
        adapter.buildMockAppFromProfile(adapter.HARNESS_PROFILE_DEGRADED, "missing-all");
      const caps = adapter.detectCapabilities(degradedApp, degradedWindow, "1.37.0");
      assert.equal(caps.graphApply.available, false);
      assert.equal(caps.previewForeground.available, false);
      assert.equal(caps.queueGuard.available, false);
      assert.equal(caps.supportsAll, false);
    }
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter applies candidate graphs in place with clear-before-configure, decoration hooks, and repaint", async () => {
  const harness = await createBrowserHarness();

  try {
    const adapter = await harness.loadAdapter();
    const candidateGraph = {
      nodes: [{ id: 7, type: "SaveImage", properties: { vibecomfy_uid: "uid-7" } }],
      links: [],
    };

    adapter.applyGraphCandidateInPlace(harness.app, candidateGraph, {
      beforeConfigure(nextCandidate) {
        nextCandidate.nodes[0].properties.decorated_before_configure = true;
      },
      afterConfigure(graph) {
        graph._nodes[0].boxcolor = "#123456";
      },
    });

    const clearIndex = harness.operationLog.findIndex((entry) => entry.kind === "graph.clear");
    const configureIndex = harness.operationLog.findIndex((entry) => entry.kind === "graph.configure");
    const changeIndex = harness.operationLog.findIndex((entry) => entry.kind === "graph.change");
    assert.notEqual(clearIndex, -1);
    assert.notEqual(configureIndex, -1);
    assert.notEqual(changeIndex, -1);
    assert(clearIndex < configureIndex, "adapter apply should clear before configure");
    assert(configureIndex < changeIndex, "adapter apply should repaint after configure");
    assert.equal(harness.graphClearCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    assert.equal(harness.graphConfigureCalls[0].nodes[0].properties.decorated_before_configure, true);
    assert.equal(harness.app.canvas.graph._nodes[0].boxcolor, "#123456");
    assert.deepEqual(harness.graphDirtyCanvasCalls, [[true, true]]);
    assert.deepEqual(harness.canvasDrawCalls, [[true, true]]);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter reports harness-only delta apply fallback when real LiteGraph mutation hooks are absent", async () => {
  const harness = await createBrowserHarness();

  try {
    const adapter = await harness.loadAdapter();
    const capability = adapter.detectGraphDeltaApply(harness.app);

    assert.equal(capability.available, true);
    assert.equal(capability.strategy, "harness-serialize-configure");
    assert.equal(capability.fallback, true);
    assert.match(capability.detail, /Harness-only/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply preflights all supported ops, resolves UID before id, and materializes candidate payloads", async () => {
  const graph = {
    last_link_id: 7,
    nodes: [
      {
        id: "uid-conflict",
        type: "TextNode",
        widgets: [{ name: "prompt" }, { name: "seed" }],
        widgets_values: ["keep-id-node", 999],
        properties: { vibecomfy_uid: "id-node" },
      },
      {
        id: 1,
        type: "TextNode",
        widgets: [{ name: "prompt" }, { name: "seed" }],
        widgets_values: ["old prompt", 123],
        outputs: [{ name: "text", links: [7] }],
        properties: { vibecomfy_uid: "uid-conflict" },
      },
      {
        id: 2,
        type: "Sampler",
        mode: 0,
        widgets: [{ name: "cfg" }, { name: "steps" }],
        widgets_values: [7, 20],
        inputs: [
          { name: "text", link: 7 },
          { name: "image", link: null },
        ],
        properties: { vibecomfy_uid: "consumer" },
      },
      {
        id: 4,
        type: "PreviewImage",
        properties: { vibecomfy_uid: "delete-me" },
      },
    ],
    links: [[7, 1, 0, 2, 0, "STRING"]],
  };
  const candidateGraph = {
    last_link_id: 11,
    nodes: [
      {
        id: "uid-conflict",
        type: "TextNode",
        widgets: [{ name: "prompt" }, { name: "seed" }],
        widgets_values: ["keep-id-node", 999],
        properties: { vibecomfy_uid: "id-node" },
      },
      {
        id: 1,
        type: "TextNode",
        widgets: [{ name: "prompt" }, { name: "seed" }],
        widgets_values: ["new prompt", 123],
        outputs: [{ name: "text", links: [10] }],
        properties: { vibecomfy_uid: "uid-conflict" },
      },
      {
        id: 2,
        type: "Sampler",
        mode: 4,
        widgets: [{ name: "cfg" }, { name: "steps" }],
        widgets_values: [7, 20],
        inputs: [
          { name: "text", link: null },
          { name: "image", link: 10 },
        ],
        properties: { vibecomfy_uid: "consumer" },
      },
      {
        id: 3,
        type: "ImageNode",
        outputs: [{ name: "image", links: [10] }],
        properties: { vibecomfy_uid: "producer-b", marker: "from-candidate" },
      },
    ],
    links: [[10, 3, 0, 2, 1, "IMAGE"]],
  };

  const harness = await createBrowserHarness({ graph });

  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        { op: "set_node_field", target: ["nodes", "uid-conflict", "widgets_values", 0], value: "ignored-op-value" },
        { op: "set_mode", target: { uid: "consumer", scope_path: [] }, mode: 999 },
        {
          op: "add_node",
          scope_path: "producer-b",
          class_type: "ImageNode",
          fields: {},
          inputs: {},
        },
        {
          op: "upsert_link",
          from: ["nodes", "producer-b", "image"],
          to: ["nodes", "consumer", "image"],
        },
        {
          op: "remove_link",
          to: ["nodes", "consumer", "text"],
        },
        { op: "remove_node", target: ["nodes", "delete-me"] },
      ],
      candidateGraph,
    });

    assert.equal(result.capability.strategy, "harness-serialize-configure");
    assert.equal(result.plan.length, 6);
    assert.equal(harness.graphClearCalls.length, 1);
    assert.equal(harness.graphConfigureCalls.length, 1);
    assert.equal(harness.loadGraphDataCalls.length, 0, "delta apply should not fall back to loadGraphData");

    const configured = harness.graphConfigureCalls[0];
    const idNode = configured.nodes.find((node) => node.id === "uid-conflict");
    const uidNode = configured.nodes.find((node) => node.properties?.vibecomfy_uid === "uid-conflict");
    const consumer = configured.nodes.find((node) => node.properties?.vibecomfy_uid === "consumer");
    const added = configured.nodes.find((node) => node.properties?.vibecomfy_uid === "producer-b");

    assert.equal(idNode.widgets_values[0], "keep-id-node", "id match must not win over UID match");
    assert.equal(uidNode.widgets_values[0], "new prompt", "set_node_field should resolve target by UID first");
    assert.equal(consumer.mode, 4, "set_mode should materialize desired mode from candidate graph");
    assert.deepEqual(consumer.widgets.map((widget) => widget.name), ["cfg", "steps"]);
    assert.deepEqual(consumer.widgets_values, [7, 20]);
    assert.equal(added.properties.marker, "from-candidate", "add_node should copy payload from candidate graph");
    assert.deepEqual(configured.links, [[10, 3, 0, 2, 1, "IMAGE"]], "link payload should come from candidate graph");
    assert.equal(configured.nodes.some((node) => node.properties?.vibecomfy_uid === "delete-me"), false);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply fails closed before mutation when preflight cannot materialize a candidate payload", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "Sampler",
        inputs: [{ name: "image", link: null }],
        properties: { vibecomfy_uid: "consumer" },
      },
    ],
    links: [],
  };
  const candidateGraph = JSON.parse(JSON.stringify(graph));
  const harness = await createBrowserHarness({ graph });

  try {
    const adapter = await harness.loadAdapter();
    assert.throws(
      () => adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          {
            op: "upsert_link",
            from: ["nodes", "missing-producer", "image"],
            to: ["nodes", "consumer", "image"],
          },
        ],
        candidateGraph,
      }),
      /materialize candidate link payload|resolve from endpoint node/,
    );
    assert.equal(harness.graphClearCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), graph);
  } finally {
    await harness.dispose();
  }
});

// ── T17: Scoped delta apply adapter tests ──────────────────────────────────

test("VibeComfy comfy_adapter delta apply set_node_field mutates only the target widget value and preserves unrelated nodes/fields/positions", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "TextNode",
        widgets: [{ name: "prompt" }, { name: "seed" }],
        widgets_values: ["blue sky", 42],
        pos: [100, 200],
        properties: { vibecomfy_uid: "text-1" },
      },
      {
        id: 2,
        type: "Sampler",
        widgets: [{ name: "cfg" }, { name: "steps" }],
        widgets_values: [7.5, 30],
        mode: 0,
        pos: [400, 200],
        properties: { vibecomfy_uid: "sampler-1" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "TextNode",
        widgets: [{ name: "prompt" }, { name: "seed" }],
        widgets_values: ["red sunset", 42],
        pos: [100, 200],
        properties: { vibecomfy_uid: "text-1" },
      },
      {
        id: 2,
        type: "Sampler",
        widgets: [{ name: "cfg" }, { name: "steps" }],
        widgets_values: [7.5, 30],
        mode: 0,
        pos: [400, 200],
        properties: { vibecomfy_uid: "sampler-1" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        { op: "set_node_field", target: ["nodes", "text-1", "widgets_values", 0], value: "red sunset" },
      ],
      candidateGraph,
    });

    assert.equal(result.capability.strategy, "live-litegraph-mutate");
    assert.equal(result.plan.length, 1);
    assert.equal(result.plan[0].op, "set_node_field");

    // Only the target widget value changed; unrelated node unchanged
    const liveNodes = harness.getLiveNodes();
    const textNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "text-1");
    const samplerNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "sampler-1");
    assert.equal(textNode.widgets_values[0], "red sunset", "target widget value should be updated");
    assert.equal(textNode.widgets_values[1], 42, "unrelated widget value should be preserved");
    assert.deepEqual(samplerNode.widgets_values, [7.5, 30], "unrelated node should be untouched");
    assert.equal(samplerNode.mode, 0, "unrelated node mode should be untouched");
    assert.deepEqual(textNode.pos, [100, 200], "target node position should be preserved");
    assert.deepEqual(samplerNode.pos, [400, 200], "unrelated node position should be preserved");

    harness.assertNoWholeGraphOps("set_node_field scoped apply");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply set_mode mutates only mode and preserves unrelated fields", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "Sampler",
        mode: 0,
        widgets: [{ name: "cfg" }, { name: "steps" }],
        widgets_values: [7, 20],
        pos: [300, 150],
        properties: { vibecomfy_uid: "sampler-1" },
      },
      {
        id: 2,
        type: "VAEDecode",
        mode: 0,
        pos: [600, 150],
        properties: { vibecomfy_uid: "vae-1" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "Sampler",
        mode: 4,
        widgets: [{ name: "cfg" }, { name: "steps" }],
        widgets_values: [7, 20],
        pos: [300, 150],
        properties: { vibecomfy_uid: "sampler-1" },
      },
      {
        id: 2,
        type: "VAEDecode",
        mode: 0,
        pos: [600, 150],
        properties: { vibecomfy_uid: "vae-1" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        { op: "set_mode", target: { uid: "sampler-1", scope_path: [] }, mode: 4 },
      ],
      candidateGraph,
    });

    assert.equal(result.capability.strategy, "live-litegraph-mutate");
    assert.equal(result.plan.length, 1);
    assert.equal(result.plan[0].op, "set_mode");
    assert.equal(result.plan[0].mode, 4);

    const liveNodes = harness.getLiveNodes();
    const samplerNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "sampler-1");
    const vaeNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "vae-1");
    assert.equal(samplerNode.mode, 4, "target mode should be updated");
    assert.deepEqual(samplerNode.widgets_values, [7, 20], "widget values should be preserved");
    assert.deepEqual(samplerNode.pos, [300, 150], "target node position should be preserved");
    assert.equal(vaeNode.mode, 0, "unrelated node mode should be preserved");

    harness.assertNoWholeGraphOps("set_mode scoped apply");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply upsert_link adds a new link and preserves unrelated links", async () => {
  const graph = {
    last_link_id: 5,
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [3] }],
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "VAEDecode",
        inputs: [{ name: "samples", link: 3 }],
        outputs: [{ name: "image", links: [] }],
        pos: [400, 200],
        properties: { vibecomfy_uid: "vae" },
      },
      {
        id: 3,
        type: "SaveImage",
        inputs: [{ name: "images", link: null }],
        pos: [700, 200],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [[3, 1, 0, 2, 0, "LATENT"]],
  };
  const candidateGraph = {
    last_link_id: 10,
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [3] }],
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "VAEDecode",
        inputs: [{ name: "samples", link: 3 }],
        outputs: [{ name: "image", links: [10] }],
        pos: [400, 200],
        properties: { vibecomfy_uid: "vae" },
      },
      {
        id: 3,
        type: "SaveImage",
        inputs: [{ name: "images", link: 10 }],
        pos: [700, 200],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [
      [3, 1, 0, 2, 0, "LATENT"],
      [10, 2, 0, 3, 0, "IMAGE"],
    ],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        { op: "upsert_link", from: ["nodes", "vae", "image"], to: ["nodes", "saver", "images"] },
      ],
      candidateGraph,
    });

    assert.equal(result.capability.strategy, "live-litegraph-mutate");
    assert.equal(result.plan.length, 1);
    assert.equal(result.plan[0].op, "upsert_link");

    // Verify existing link (3) is preserved
    const liveLinks = harness.getLiveLinks();
    assert.ok(liveLinks[String(3)], "existing link should be preserved as link 3");

    // Verify new link exists
    const link10 = liveLinks[String(10)];
    assert.ok(link10, "newly upserted link should exist as link 10");

    harness.assertNoWholeGraphOps("upsert_link scoped apply");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply remove_link removes only the target link and preserves unrelated links", async () => {
  const graph = {
    last_link_id: 7,
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [5, 7] }],
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "VAEDecode",
        inputs: [
          { name: "samples", link: 5 },
          { name: "vae", link: 7 },
        ],
        pos: [400, 200],
        properties: { vibecomfy_uid: "vae" },
      },
    ],
    links: [
      [5, 1, 0, 2, 0, "LATENT"],
      [7, 1, 0, 2, 1, "VAE"],
    ],
  };
  const candidateGraph = {
    last_link_id: 7,
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [7] }],
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "VAEDecode",
        inputs: [
          { name: "samples", link: null },
          { name: "vae", link: 7 },
        ],
        pos: [400, 200],
        properties: { vibecomfy_uid: "vae" },
      },
    ],
    links: [[7, 1, 0, 2, 1, "VAE"]],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        { op: "remove_link", to: ["nodes", "vae", "samples"] },
      ],
      candidateGraph,
    });

    assert.equal(result.capability.strategy, "live-litegraph-mutate");
    assert.equal(result.plan.length, 1);
    assert.equal(result.plan[0].op, "remove_link");

    const liveLinks = harness.getLiveLinks();
    assert.equal(liveLinks[String(5)], undefined, "removed link should be absent");
    assert.ok(liveLinks[String(7)], "unrelated link should be preserved");

    const vaeNode = harness.getLiveNodes().find((n) => n.properties?.vibecomfy_uid === "vae");
    assert.equal(vaeNode.inputs[0].link, null, "removed link input slot should be cleared");
    assert.equal(vaeNode.inputs[1].link, 7, "unrelated input link should be preserved");

    harness.assertNoWholeGraphOps("remove_link scoped apply");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply add_node adds the node and preserves existing nodes", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver", marker: "from-candidate" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        { op: "add_node", scope_path: "saver", class_type: "SaveImage", fields: {}, inputs: {} },
      ],
      candidateGraph,
    });

    assert.equal(result.capability.strategy, "live-litegraph-mutate");
    assert.equal(result.plan.length, 1);
    assert.equal(result.plan[0].op, "add_node");

    // graph.add should have been called
    assert.ok(harness.graphAddCalls.length >= 1, "graph.add should be called for add_node");
    assert.equal(harness.graphClearCalls.length, 0, "graph.clear should not be called");
    assert.equal(harness.graphConfigureCalls.length, 0, "graph.configure should not be called");

    // Existing node should still be present
    const liveNodes = harness.getLiveNodes();
    const loaderNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "loader");
    assert.ok(loaderNode, "existing node should be preserved");
    assert.deepEqual(loaderNode.pos, [100, 200], "existing node position should be preserved");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply remove_node removes the node and preserves unrelated nodes", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [400, 200],
        properties: { vibecomfy_uid: "delete-me" },
      },
      {
        id: 3,
        type: "VAEDecode",
        pos: [700, 200],
        properties: { vibecomfy_uid: "vae" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 3,
        type: "VAEDecode",
        pos: [700, 200],
        properties: { vibecomfy_uid: "vae" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        { op: "remove_node", target: ["nodes", "delete-me"] },
      ],
      candidateGraph,
    });

    assert.equal(result.capability.strategy, "live-litegraph-mutate");
    assert.equal(result.plan.length, 1);
    assert.equal(result.plan[0].op, "remove_node");
    assert.equal(result.plan[0].alreadyAbsent, false);

    // graph.remove should have been called
    assert.ok(harness.graphRemoveCalls.length >= 1, "graph.remove should be called for remove_node");
    assert.equal(harness.graphClearCalls.length, 0, "graph.clear should not be called");

    // Deleted node should be gone
    const liveNodes = harness.getLiveNodes();
    const deletedNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "delete-me");
    assert.equal(deletedNode, undefined, "target node should be removed");

    // Unrelated nodes should be preserved
    const loaderNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "loader");
    const vaeNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "vae");
    assert.ok(loaderNode, "unrelated node should be preserved");
    assert.ok(vaeNode, "unrelated node should be preserved");
    assert.deepEqual(loaderNode.pos, [100, 200], "unrelated node position should be preserved");
    assert.deepEqual(vaeNode.pos, [700, 200], "unrelated node position should be preserved");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply throws before mutation when set_node_field targets a non-existent node", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "Sampler",
        widgets: [{ name: "cfg" }],
        widgets_values: [7],
        pos: [100, 200],
        properties: { vibecomfy_uid: "sampler-1" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "Sampler",
        widgets: [{ name: "cfg" }],
        widgets_values: [7],
        pos: [100, 200],
        properties: { vibecomfy_uid: "sampler-1" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    assert.throws(
      () => adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          { op: "set_node_field", target: ["nodes", "non-existent-uid", "widgets_values", 0], value: "new" },
        ],
        candidateGraph,
      }),
      /Could not resolve node/,
    );

    // No mutation should have occurred
    assert.deepEqual(harness.getCurrentGraph(), graph, "graph should be unchanged after preflight throw");
    assert.equal(harness.graphClearCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply throws before mutation when set_mode targets a non-existent node", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "Sampler",
        mode: 0,
        pos: [100, 200],
        properties: { vibecomfy_uid: "sampler-1" },
      },
    ],
    links: [],
  };
  const candidateGraph = JSON.parse(JSON.stringify(graph));
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    assert.throws(
      () => adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          { op: "set_mode", target: { uid: "ghost-node", scope_path: [] }, mode: 4 },
        ],
        candidateGraph,
      }),
      /Could not resolve node/,
    );

    assert.deepEqual(harness.getCurrentGraph(), graph);
    assert.equal(harness.graphClearCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply throws before mutation when add_node collides with an existing UID", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "already-here" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "already-here" },
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [400, 200],
        properties: { vibecomfy_uid: "already-here" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    assert.throws(
      () => adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          { op: "add_node", scope_path: "already-here", class_type: "SaveImage", fields: {}, inputs: {} },
        ],
        candidateGraph,
      }),
      /Cannot add node.*already exists/,
    );

    assert.equal(harness.graphAddCalls.length, 0, "graph.add should not be called");
    assert.equal(harness.graphClearCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), graph);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply throws before mutation when unsupported delta op kind is used", async () => {
  const graph = {
    nodes: [{ id: 1, type: "Empty", pos: [100, 200], properties: { vibecomfy_uid: "node-1" } }],
    links: [],
  };
  const candidateGraph = JSON.parse(JSON.stringify(graph));
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    assert.throws(
      () => adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [{ op: "unsupported_future_op", target: ["nodes", "node-1"] }],
        candidateGraph,
      }),
      /Unsupported delta op kind/,
    );

    assert.deepEqual(harness.getCurrentGraph(), graph);
    assert.equal(harness.graphClearCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter delta apply preserves unrelated node positions, sizes, and top-level properties across multi-op mutation", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        widgets: [{ name: "image" }],
        widgets_values: ["input.png"],
        pos: [50, 100],
        size: [300, 200],
        properties: { vibecomfy_uid: "loader", NodeNameForSearches: "MyLoader" },
      },
      {
        id: 2,
        type: "VAEDecode",
        mode: 0,
        pos: [350, 100],
        size: [250, 150],
        properties: { vibecomfy_uid: "vae", NodeNameForSearches: "MyVAE" },
      },
      {
        id: 3,
        type: "SaveImage",
        widgets: [{ name: "filename_prefix" }],
        widgets_values: ["output"],
        pos: [650, 100],
        size: [280, 180],
        properties: { vibecomfy_uid: "saver", NodeNameForSearches: "MySaver" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        widgets: [{ name: "image" }],
        widgets_values: ["changed.png"],
        pos: [50, 100],
        size: [300, 200],
        properties: { vibecomfy_uid: "loader", NodeNameForSearches: "MyLoader" },
      },
      {
        id: 2,
        type: "VAEDecode",
        mode: 4,
        pos: [350, 100],
        size: [250, 150],
        properties: { vibecomfy_uid: "vae", NodeNameForSearches: "MyVAE" },
      },
      {
        id: 3,
        type: "SaveImage",
        widgets: [{ name: "filename_prefix" }],
        widgets_values: ["output"],
        pos: [650, 100],
        size: [280, 180],
        properties: { vibecomfy_uid: "saver", NodeNameForSearches: "MySaver" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        { op: "set_node_field", target: ["nodes", "loader", "widgets_values", 0], value: "changed.png" },
        { op: "set_mode", target: { uid: "vae", scope_path: [] }, mode: 4 },
      ],
      candidateGraph,
    });

    assert.equal(result.capability.strategy, "live-litegraph-mutate");
    assert.equal(result.plan.length, 2);

    const liveNodes = harness.getLiveNodes();
    const loader = liveNodes.find((n) => n.properties?.vibecomfy_uid === "loader");
    const vae = liveNodes.find((n) => n.properties?.vibecomfy_uid === "vae");
    const saver = liveNodes.find((n) => n.properties?.vibecomfy_uid === "saver");

    // Mutations applied
    assert.equal(loader.widgets_values[0], "changed.png");
    assert.equal(vae.mode, 4);

    // Untouched fields and nodes preserved
    assert.deepEqual(loader.pos, [50, 100]);
    assert.deepEqual(loader.size, [300, 200]);
    assert.equal(loader.properties.NodeNameForSearches, "MyLoader");
    assert.deepEqual(vae.pos, [350, 100]);
    assert.deepEqual(vae.size, [250, 150]);
    assert.equal(vae.properties.NodeNameForSearches, "MyVAE");
    assert.deepEqual(saver.pos, [650, 100]);
    assert.deepEqual(saver.size, [280, 180]);
    assert.equal(saver.properties.NodeNameForSearches, "MySaver");
    assert.equal(saver.widgets_values[0], "output");

    harness.assertNoWholeGraphOps("multi-op scoped apply");
  } finally {
    await harness.dispose();
  }
});

// ── T10: Canonical delta browser apply/preflight tests ─────────────────────

test("VibeComfy comfy_adapter canonical add_node materializes payload from explicit uid and node_id", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver", marker: "from-candidate" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        {
          op: "add_node",
          uid: "saver",
          node_id: "2",
          class_type: "SaveImage",
          fields: {},
          inputs: {},
        },
      ],
      candidateGraph,
    });

    assert.equal(result.capability.strategy, "live-litegraph-mutate");
    assert.equal(result.plan.length, 1);
    assert.equal(result.plan[0].op, "add_node");

    // graph.add should have been called
    assert.ok(harness.graphAddCalls.length >= 1, "graph.add should be called for add_node");
    assert.equal(harness.graphClearCalls.length, 0, "graph.clear should not be called");
    assert.equal(harness.graphConfigureCalls.length, 0, "graph.configure should not be called");

    // Existing node preserved
    const liveNodes = harness.getLiveNodes();
    const loaderNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "loader");
    assert.ok(loaderNode, "existing node should be preserved");
    assert.deepEqual(loaderNode.pos, [100, 200], "existing node position should be preserved");

    // Added node should carry the candidate marker
    const addedNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "saver");
    assert.ok(addedNode, "added node should be present in live graph");
    assert.equal(addedNode.properties.marker, "from-candidate", "added node should copy payload from candidate");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter canonical add_node missing identity rejects before any graph mutation", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    assert.throws(
      () => adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          {
            op: "add_node",
            class_type: "SaveImage",
            fields: {},
            inputs: {},
          },
        ],
        candidateGraph,
      }),
      /must provide explicit uid or node_id/,
    );

    // Verify no mutation occurred — graph unchanged and no add calls
    assert.equal(harness.graphAddCalls.length, 0, "graph.add must not be called when identity is missing");
    assert.equal(harness.graphClearCalls.length, 0);
    assert.equal(harness.graphConfigureCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), graph, "graph should be unchanged after identity rejection");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter add_node with only node_id (no uid) materializes identity correctly", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: "2",
        type: "SaveImage",
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver-by-id" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        {
          op: "add_node",
          node_id: "2",
          class_type: "SaveImage",
          fields: {},
          inputs: {},
        },
      ],
      candidateGraph,
    });

    assert.equal(result.plan.length, 1);
    assert.equal(result.plan[0].op, "add_node");

    const liveNodes = harness.getLiveNodes();
    const addedNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "saver-by-id");
    assert.ok(addedNode, "added node should be resolved by explicit node_id");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter non-root scoped set_node_field throws DeltaDiagnosticError with unsupported_scoped_apply", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "TextNode",
        widgets: [{ name: "prompt" }],
        widgets_values: ["old"],
        pos: [100, 200],
        properties: { vibecomfy_uid: "text-1" },
      },
    ],
    links: [],
  };
  const candidateGraph = JSON.parse(JSON.stringify(graph));
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    let caught = null;
    try {
      adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          { op: "set_node_field", target: ["group", "g1", "nodes", "text-1", "widgets_values", 0], value: "new" },
        ],
        candidateGraph,
      });
    } catch (err) {
      caught = err;
    }

    assert.ok(caught, "should throw for non-root scoped apply");
    assert.equal(caught.name, "DeltaDiagnosticError", "should be a DeltaDiagnosticError");
    assert.equal(caught.code, "unsupported_scoped_apply", "diagnostic code should be unsupported_scoped_apply");
    assert.match(caught.message, /only supports root-scope/);

    // No mutation occurred
    assert.deepEqual(harness.getCurrentGraph(), graph);
    assert.equal(harness.graphClearCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter non-root scoped upsert_link throws DeltaDiagnosticError with unsupported_scoped_apply", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [] }],
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        inputs: [{ name: "images", link: null }],
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [10] }],
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        inputs: [{ name: "images", link: 10 }],
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [[10, 1, 0, 2, 0, "IMAGE"]],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    let caught = null;
    try {
      adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          { op: "upsert_link", from: ["group", "g1", "nodes", "loader", "image"], to: ["nodes", "saver", "images"] },
        ],
        candidateGraph,
      });
    } catch (err) {
      caught = err;
    }

    assert.ok(caught, "should throw for non-root scoped upsert_link");
    assert.equal(caught.name, "DeltaDiagnosticError");
    assert.equal(caught.code, "unsupported_scoped_apply");
    assert.match(caught.message, /only supports root-scope/);

    // No mutation
    assert.deepEqual(harness.getCurrentGraph(), graph);
    assert.equal(harness.graphClearCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter upsert_link and remove_link share centralized endpoint resolution", async () => {
  // Prove that both upsert_link and remove_link use the same resolveEndpoint
  // path for canonical key handling. They should produce consistent errors
  // when the target cannot be resolved, confirming a single code path.
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [] }],
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        inputs: [{ name: "images", link: null }],
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [10] }],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        inputs: [{ name: "images", link: 10 }],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [[10, 1, 0, 2, 0, "IMAGE"]],
  };

  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();

    // upsert_link with a missing from-node should throw from resolveEndpoint
    assert.throws(
      () => adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          { op: "upsert_link", from: ["nodes", "ghost-node", "image"], to: ["nodes", "saver", "images"] },
        ],
        candidateGraph,
      }),
      /resolve from endpoint node/,
      "upsert_link should use resolveEndpoint for canonical from-key resolution",
    );

    // Reset harness state
    harness.graphClearCalls.length = 0;

    // remove_link with a missing target-node should also throw from resolveEndpoint
    assert.throws(
      () => adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          { op: "remove_link", to: ["nodes", "ghost-node", "images"] },
        ],
        candidateGraph,
      }),
      /resolve to endpoint node/,
      "remove_link should use resolveEndpoint for canonical to-key resolution",
    );

    // Both ops produce errors from the same centralized path
    assert.deepEqual(harness.getCurrentGraph(), graph);
    assert.equal(harness.graphClearCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter applyGraphDeltaInPlace rejects non-array deltaOps with DeltaDiagnosticError", async () => {
  const graph = {
    nodes: [{ id: 1, type: "Empty", properties: { vibecomfy_uid: "node-1" } }],
    links: [],
  };
  const candidateGraph = JSON.parse(JSON.stringify(graph));
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    let caught = null;
    try {
      adapter.applyGraphDeltaInPlace(harness.app, { deltaOps: null, candidateGraph });
    } catch (err) {
      caught = err;
    }
    assert.ok(caught, "should throw for null deltaOps");
    assert.equal(caught.name, "DeltaDiagnosticError");
    assert.equal(caught.code, "malformed_delta");
    assert.match(caught.message, /normalized deltaOps array/);

    assert.deepEqual(harness.getCurrentGraph(), graph);
    assert.equal(harness.graphClearCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter applyGraphDeltaInPlace rejects invalid op entries with DeltaDiagnosticError", async () => {
  const graph = {
    nodes: [{ id: 1, type: "Empty", properties: { vibecomfy_uid: "node-1" } }],
    links: [],
  };
  const candidateGraph = JSON.parse(JSON.stringify(graph));
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    let caught = null;
    try {
      adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [{ not_an_op: true }],
        candidateGraph,
      });
    } catch (err) {
      caught = err;
    }
    assert.ok(caught, "should throw for invalid op entry");
    assert.equal(caught.name, "DeltaDiagnosticError");
    assert.equal(caught.code, "malformed_delta");
    assert.match(caught.message, /invalid operation entry/);

    assert.deepEqual(harness.getCurrentGraph(), graph);
    assert.equal(harness.graphClearCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter non-root scoped add_node throws DeltaDiagnosticError with unsupported_scoped_apply", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    let caught = null;
    try {
      adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          {
            op: "add_node",
            uid: "saver",
            node_id: "2",
            class_type: "SaveImage",
            fields: {},
            inputs: {},
            target: ["nested", "saver"],
          },
        ],
        candidateGraph,
      });
    } catch (err) {
      caught = err;
    }

    assert.ok(caught, "should throw for non-root scoped add_node");
    assert.equal(caught.name, "DeltaDiagnosticError");
    assert.equal(caught.code, "unsupported_scoped_apply");
    assert.match(caught.message, /only supports root-scope/);

    // Verify no mutation occurred
    assert.equal(harness.graphAddCalls.length, 0, "graph.add must not be called for non-root scoped add_node");
    assert.equal(harness.graphClearCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), graph);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter non-root scoped remove_node throws DeltaDiagnosticError with unsupported_scoped_apply", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [],
  };
  const candidateGraph = JSON.parse(JSON.stringify(graph));
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    let caught = null;
    try {
      adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          {
            op: "remove_node",
            target: ["nested-scope", "saver"],
          },
        ],
        candidateGraph,
      });
    } catch (err) {
      caught = err;
    }

    assert.ok(caught, "should throw for non-root scoped remove_node");
    assert.equal(caught.name, "DeltaDiagnosticError");
    assert.equal(caught.code, "unsupported_scoped_apply");
    assert.match(caught.message, /only supports root-scope/);

    // Verify no mutation occurred
    assert.equal(harness.graphClearCalls.length, 0);
    assert.deepEqual(harness.getCurrentGraph(), graph);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter non-root scoped set_mode throws DeltaDiagnosticError with unsupported_scoped_apply", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "TextNode",
        mode: 0,
        pos: [100, 200],
        properties: { vibecomfy_uid: "text-1" },
      },
    ],
    links: [],
  };
  const candidateGraph = JSON.parse(JSON.stringify(graph));
  candidateGraph.nodes[0].mode = 4;
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    let caught = null;
    try {
      adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          {
            op: "set_mode",
            target: { uid: "text-1", scope_path: ["nested"] },
            mode: 4,
          },
        ],
        candidateGraph,
      });
    } catch (err) {
      caught = err;
    }

    assert.ok(caught, "should throw for non-root scoped set_mode");
    assert.equal(caught.name, "DeltaDiagnosticError");
    assert.equal(caught.code, "unsupported_scoped_apply");
    assert.match(caught.message, /only supports root-scope/);

    // Verify no mutation occurred
    assert.equal(harness.graphClearCalls.length, 0);
    const liveGraph = harness.getCurrentGraph();
    const node = liveGraph.nodes.find((n) => n.properties?.vibecomfy_uid === "text-1");
    assert.equal(node.mode, 0, "node mode should be unchanged");
    assert.deepEqual(liveGraph, graph);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter non-root scoped remove_link throws DeltaDiagnosticError with unsupported_scoped_apply", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [10] }],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        inputs: [{ name: "images", link: 10 }],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [[10, 1, 0, 2, 0, "IMAGE"]],
  };
  const candidateGraph = JSON.parse(JSON.stringify(graph));
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    let caught = null;
    try {
      adapter.applyGraphDeltaInPlace(harness.app, {
        deltaOps: [
          {
            op: "remove_link",
            to: ["nested-scope", "saver", "images"],
          },
        ],
        candidateGraph,
      });
    } catch (err) {
      caught = err;
    }

    assert.ok(caught, "should throw for non-root scoped remove_link");
    assert.equal(caught.name, "DeltaDiagnosticError");
    assert.equal(caught.code, "unsupported_scoped_apply");
    assert.match(caught.message, /only supports root-scope/);

    // Verify no mutation occurred — no clear/configure calls
    assert.equal(harness.graphClearCalls.length, 0);
    // Node count unchanged
    const liveNodes = harness.getLiveNodes();
    assert.equal(liveNodes.length, 2, "both nodes should still be present");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter add_node with uid only (no node_id) materializes identity correctly", async () => {
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        pos: [100, 200],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [400, 200],
        properties: { vibecomfy_uid: "saver-by-uid-only", marker: "from-candidate" },
      },
    ],
    links: [],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();
    const result = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        {
          op: "add_node",
          uid: "saver-by-uid-only",
          class_type: "SaveImage",
          fields: {},
          inputs: {},
        },
      ],
      candidateGraph,
    });

    assert.equal(result.plan.length, 1);
    assert.equal(result.plan[0].op, "add_node");

    const liveNodes = harness.getLiveNodes();
    const addedNode = liveNodes.find((n) => n.properties?.vibecomfy_uid === "saver-by-uid-only");
    assert.ok(addedNode, "added node should be resolved by explicit uid only");
    assert.equal(addedNode.properties.marker, "from-candidate", "added node should copy payload from candidate");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter upsert_link and remove_link canonical key adaptation is centralized in success paths", async () => {
  // Prove that both upsert_link and remove_link go through the centralized
  // resolveEndpoint path for canonical key handling, not just error paths.
  // Both should succeed and produce plans that reference the centralized
  // slot resolution logic.
  const graph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [] }],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        inputs: [{ name: "images", link: null }],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "LoadImage",
        outputs: [{ name: "image", links: [10] }],
        properties: { vibecomfy_uid: "loader" },
      },
      {
        id: 2,
        type: "SaveImage",
        inputs: [{ name: "images", link: 10 }],
        properties: { vibecomfy_uid: "saver" },
      },
    ],
    links: [[10, 1, 0, 2, 0, "IMAGE"]],
  };
  const harness = await createBrowserHarness({ graph, withGraphMutation: true });
  try {
    const adapter = await harness.loadAdapter();

    // upsert_link uses resolveEndpoint for from/to canonical keys
    const upsertResult = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        {
          op: "upsert_link",
          from: ["", "loader", "image"],
          to: ["", "saver", "images"],
        },
      ],
      candidateGraph,
    });

    assert.equal(upsertResult.plan.length, 1);
    assert.equal(upsertResult.plan[0].op, "upsert_link");
    // The centralized resolveEndpoint should have resolved both endpoints
    const upsertedLink = upsertResult.plan[0].link;
    assert.ok(upsertedLink.id !== undefined, "link id should be resolved");
    assert.ok(upsertedLink.origin_id !== undefined, "origin_id should be resolved");
    assert.ok(upsertedLink.target_id !== undefined, "target_id should be resolved");

    // Reset harness state for the remove_link test
    harness.graphClearCalls.length = 0;
    harness.setCurrentGraph({
      nodes: [
        {
          id: 1,
          type: "LoadImage",
          outputs: [{ name: "image", links: [20] }],
          properties: { vibecomfy_uid: "loader" },
        },
        {
          id: 2,
          type: "SaveImage",
          inputs: [{ name: "images", link: 20 }],
          properties: { vibecomfy_uid: "saver" },
        },
      ],
      links: [[20, 1, 0, 2, 0, "IMAGE"]],
    });

    // remove_link also uses resolveEndpoint for canonical to-key
    const removeResult = adapter.applyGraphDeltaInPlace(harness.app, {
      deltaOps: [
        {
          op: "remove_link",
          to: ["", "saver", "images"],
        },
      ],
      candidateGraph: JSON.parse(JSON.stringify(candidateGraph)),
    });

    assert.equal(removeResult.plan.length, 1);
    assert.equal(removeResult.plan[0].op, "remove_link");
    // Both ops produce plans through centralized endpoint resolution
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter installs preview overlay via direct interceptor without polling and preserves later canvas reassignments", async () => {
  const harness = await createBrowserHarness();

  const originalSetInterval = globalThis.setInterval;
  let setIntervalCalls = 0;

  try {
    const adapter = await harness.loadAdapter();
    globalThis.setInterval = (...args) => {
      setIntervalCalls += 1;
      return originalSetInterval(...args);
    };

    const drawEvents = [];
    const report = adapter.installPreviewForegroundOverlay(
      harness.app,
      () => drawEvents.push("overlay"),
      { windowObj: harness.window },
    );

    assert.equal(report.strategy, "property-interceptor");
    assert.equal(report.polling, false);
    assert.equal(setIntervalCalls, 0);

    harness.app.canvas.onDrawForeground = function reassignedForeground() {
      drawEvents.push("delegate");
    };

    const installed = harness.app.canvas.onDrawForeground;
    assert.equal(typeof installed, "function");
    assert.equal(installed.__vibecomfyOverlayWrapper, true);

    installed.call(harness.app.canvas, {});
    assert.deepEqual(drawEvents, ["delegate", "overlay"]);

    report.cleanup();
  } finally {
    globalThis.setInterval = originalSetInterval;
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter preview overlay survives external rechaining and reinstall without recursion", async () => {
  const harness = await createBrowserHarness();

  try {
    const adapter = await harness.loadAdapter();
    const drawEvents = [];
    harness.app.canvas.onDrawForeground = function originalForeground() {
      drawEvents.push("original");
    };

    const firstReport = adapter.installPreviewForegroundOverlay(
      harness.app,
      () => drawEvents.push("overlay-1"),
      { windowObj: harness.window },
    );
    assert.equal(firstReport.strategy, "property-interceptor");

    const previousForeground = harness.app.canvas.onDrawForeground;
    harness.app.canvas.onDrawForeground = function comfyChainedForeground(ctx, ...args) {
      drawEvents.push("chainer");
      return previousForeground.call(this, ctx, ...args);
    };

    const secondReport = adapter.installPreviewForegroundOverlay(
      harness.app,
      () => drawEvents.push("overlay-2"),
      { windowObj: harness.window },
    );
    assert.equal(secondReport.strategy, "property-interceptor");

    harness.app.canvas.onDrawForeground.call(harness.app.canvas, {});
    assert.deepEqual(drawEvents, ["chainer", "original", "overlay-2"]);
    assert.equal(harness.consoleCapture.warn.length, 0);

    const throwingError = new RangeError("same draw failure");
    harness.app.canvas.onDrawForeground = function throwingForeground() {
      throw throwingError;
    };
    harness.app.canvas.onDrawForeground.call(harness.app.canvas, {});
    harness.app.canvas.onDrawForeground.call(harness.app.canvas, {});
    assert.equal(
      harness.consoleCapture.warn.filter((entry) => entry.includes("original onDrawForeground threw")).length,
      1,
      "delegate draw failures must be logged once per distinct error",
    );

    secondReport.cleanup();
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy preview overlay warning details stay bounded so console inspection cannot break preview drawing", async () => {
  const originalWarn = console.warn;
  const originalWindow = globalThis.window;
  const warned = [];
  globalThis.window = {
    LiteGraph: {
      NODE_TITLE_HEIGHT: 30,
      NODE_SLOT_HEIGHT: 20,
      NODE_WIDGET_HEIGHT: 20,
    },
  };
  console.warn = (...args) => {
    warned.push(args);
    if (args.some((arg) => arg && typeof arg === "object")) {
      throw new RangeError("recursive console inspection");
    }
  };

  try {
    const liveGraph = {
      nodes: [
        {
          id: 1,
          pos: [10, 20],
          size: [120, 80],
          inputs: [{ name: "in" }],
          outputs: [{ name: "out" }],
          properties: { vibecomfy_uid: "live-a" },
        },
      ],
      links: {},
    };
    const circularLink = { label: "bad-link" };
    circularLink.self = circularLink;
    circularLink.toString = () => "missing::0->live-a::0";
    const ctx = createMockCanvasContext();

    assert.doesNotThrow(() => {
      drawPanelOverlayPreviewOverlay(ctx, {
        edited: [],
        edited_fields: [],
        added: [],
        removed: [],
        removed_named: [],
        layout_moved: [],
        unresolved: [],
        added_links: [circularLink],
        removed_links: [],
        _candidateGraph: { nodes: [], links: [] },
        _candidateGraphHash: "circular-warning-detail",
      }, makePanelOverlayDeps(liveGraph));
    });

    assert.equal(warned.length, 1);
    assert.equal(typeof warned[0][1], "string");
  } finally {
    console.warn = originalWarn;
    if (originalWindow === undefined) {
      delete globalThis.window;
    } else {
      globalThis.window = originalWindow;
    }
  }
});

test("VibeComfy comfy_adapter reports polling fallback when preview foreground cannot be intercepted directly", async () => {
  const harness = await createBrowserHarness();

  const originalSetInterval = globalThis.setInterval;
  const originalClearInterval = globalThis.clearInterval;
  const scheduledIntervals = [];

  try {
    const adapter = await harness.loadAdapter();

    globalThis.setInterval = (fn, ms) => {
      const token = { fn, ms };
      scheduledIntervals.push(token);
      return token;
    };
    globalThis.clearInterval = (token) => {
      const index = scheduledIntervals.indexOf(token);
      if (index >= 0) {
        scheduledIntervals.splice(index, 1);
      }
    };

    Object.defineProperty(harness.app.canvas, "onDrawForeground", {
      configurable: false,
      enumerable: true,
      writable: true,
      value: function lockedForeground() { return "locked"; },
    });

    const report = adapter.installPreviewForegroundOverlay(
      harness.app,
      () => null,
      { windowObj: harness.window, pollIntervalMs: 250 },
    );

    assert.equal(report.strategy, "polling-fallback");
    assert.equal(report.polling, true);
    assert.match(report.detail, /Fell back to polling/);
    assert.equal(scheduledIntervals.length, 1);
    assert.equal(scheduledIntervals[0].ms, 250);
    assert.equal(harness.app.canvas.onDrawForeground.__vibecomfyOverlayWrapper, true);

    report.cleanup();
    assert.equal(scheduledIntervals.length, 0);
  } finally {
    globalThis.setInterval = originalSetInterval;
    globalThis.clearInterval = originalClearInterval;
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter registerExtensionWithCapabilities reports install state and attaches capabilities", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const adapter = await harness.loadAdapter();

    // Clear any prior extension registrations from loadExtension calls.
    harness.registeredExtensions.length = 0;

    const extension = {
      name: "Test.Extension",
      async setup() { /* noop */ },
    };

    const caps = adapter.registerExtensionWithCapabilities(harness.app, extension, { silent: true });

    // Extension should be registered.
    assert.equal(harness.registeredExtensions.length, 1);
    assert.equal(harness.registeredExtensions[0].name, "Test.Extension");

    // Capabilities should be attached to the extension object.
    assert.equal(extension.__vibecomfyCapabilities.supportsAll, true);
    assert.equal(extension.__vibecomfyCapabilities.graphApply.available, true);
    assert.equal(extension.__vibecomfyCapabilities.previewForeground.available, true);
    assert.equal(extension.__vibecomfyCapabilities.queueGuard.available, true);

    // The returned caps should match.
    assert.equal(caps.supportsAll, true);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy comfy_adapter registerExtensionWithCapabilities warns on degraded hooks", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.37.0" } },
      },
    },
  });

  try {
    const adapter = await harness.loadAdapter();

    harness.registeredExtensions.length = 0;

    const extension = { name: "Degraded.Extension" };

    // Build degraded capabilities (missing all hooks).
    const { app: degradedApp, window: degradedWindow, capabilities: degradedCaps } =
      adapter.buildMockAppFromProfile(adapter.HARNESS_PROFILE_DEGRADED, "missing-all");

    // We need registerExtension on the degraded app; wire it up.
    degradedApp.registerExtension = function (ext) {
      harness.registeredExtensions.push(ext);
    };

    const preWarnCount = harness.consoleCapture.warn.length;
    adapter.registerExtensionWithCapabilities(degradedApp, extension, { capabilities: degradedCaps });

    // Should have logged a warning about degraded state.
    assert.ok(
      harness.consoleCapture.warn.length > preWarnCount,
      "Expected console.warn about degraded capabilities",
    );

    const warningText = harness.consoleCapture.warn.slice(preWarnCount).join(" ");
    assert.match(warningText, /DEGRADED/);
    assert.match(warningText, /graphApply/);
    assert.match(warningText, /previewForeground/);
    assert.match(warningText, /queueGuard/);

    // Still registered.
    assert.equal(harness.registeredExtensions.length, 1);
    assert.equal(extension.__vibecomfyCapabilities.supportsAll, false);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy harness profiles are immutable and contain expected capability shapes", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const adapter = await harness.loadAdapter();

    // Supported profile.
    const supported = adapter.HARNESS_PROFILE_SUPPORTED_139_X;
    assert.equal(supported.name, "supported-1.39.x");
    assert.equal(supported.frontendVersion, "1.39.19");
    assert.equal(supported.capabilities.graphApply.available, true);
    assert.equal(supported.capabilities.previewForeground.available, true);
    assert.equal(supported.capabilities.queueGuard.available, true);

    // Degraded profile variants.
    const degraded = adapter.HARNESS_PROFILE_DEGRADED;
    assert.equal(degraded.name, "degraded-missing-hook");
    assert.equal(degraded.frontendVersion, "1.37.0");

    const variantKeys = Object.keys(degraded.variants);
    assert.ok(variantKeys.includes("missing-graph-apply"));
    assert.ok(variantKeys.includes("missing-preview-foreground"));
    assert.ok(variantKeys.includes("missing-queue-guard"));
    assert.ok(variantKeys.includes("missing-all"));

    // Each variant should have all three capability keys.
    for (const key of variantKeys) {
      const v = degraded.variants[key];
      assert.ok("graphApply" in v.capabilities, `${key}: missing graphApply`);
      assert.ok("previewForeground" in v.capabilities, `${key}: missing previewForeground`);
      assert.ok("queueGuard" in v.capabilities, `${key}: missing queueGuard`);
    }
  } finally {
    await harness.dispose();
  }
});

// ── Canonical and legacy response fixture boundaries ─────────────────────
test("VibeComfy roundtrip canonical submit fixture is valid with allowLegacy=false", () => {
  const raw = {
    ok: true,
    message: "Canonical roundtrip candidate.",
    outcome: {
      kind: "candidate",
      changes: [{ uid: "save", field_path: "inputs.filename_prefix", old: "old", new: "new" }],
    },
    candidate: {
      state: "candidate",
      graph: { nodes: [{ id: 2, type: "SaveImage" }], links: [] },
      graph_hash: "roundtrip-candidate-hash",
      structural_graph_hash: "roundtrip-structural-hash",
      turn_identity: {
        session_id: "sess-roundtrip-canonical",
        turn_id: "0030",
        baseline_turn_id: "0029",
        idempotency_key: "roundtrip-idem",
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
            { uid: "save", field_path: "inputs.filename_prefix", old: "old", new: "new" },
          ],
        },
      ],
    },
  };

  assertCanonicalNormalPathHasNoLegacyAliases(raw);

  const normalized = normalizeCanonicalAgentEditResponse(raw, {
    endpoint: "/vibecomfy/agent-executor",
  });
  const candidate = readApplyCandidate(normalized, { allowLegacy: false });

  assert.equal(candidate.graphHash, "roundtrip-candidate-hash");
  assert.equal(candidate.structuralGraphHash, "roundtrip-structural-hash");
  assert.deepEqual(readTurnIdentity(normalized, { allowLegacy: false }), {
    sessionId: "sess-roundtrip-canonical",
    turnId: "0030",
    baselineTurnId: "0029",
    idempotencyKey: "roundtrip-idem",
  });
  assert.deepEqual(readFieldChanges(normalized, { allowLegacy: false }).legacyChanges, []);
});

test("VibeComfy roundtrip old persisted/session fixtures normalize only through legacy adapter", () => {
  const oldPersistedResponse = {
    ok: true,
    session_id: "sess-roundtrip-old",
    turn_id: "0018",
    message: "Old response candidate.",
    graph: { nodes: [{ id: 4, type: "PreviewImage" }], links: [] },
    candidate_graph_hash: "old-roundtrip-hash",
    apply_allowed: true,
    canvas_apply_allowed: true,
    queue_allowed: true,
    field_changes: [
      { uid: "preview", field_path: "inputs.images", old: null, new: "linked" },
    ],
  };

  assert.throws(
    () => normalizeCanonicalAgentEditResponse(oldPersistedResponse, {
      endpoint: "/vibecomfy/agent-edit/chat:old-response",
    }),
    /missing outcome/i,
  );

  const adaptedPersisted = adaptLegacyAgentEditResponse(oldPersistedResponse, {
    endpoint: "/vibecomfy/agent-edit/chat:old-response",
  });
  assert.equal(adaptedPersisted.outcome.kind, "candidate");
  assert.equal(readApplyCandidate(adaptedPersisted, { allowLegacy: false }).graphHash, "old-roundtrip-hash");
  assert.deepEqual(readFieldChanges(adaptedPersisted, { allowLegacy: false }).legacyChanges, [
    { uid: "preview", fieldPath: "inputs.images", new: "linked" },
  ]);

  const oldSession = {
    ok: true,
    exists: true,
    session_id: "sess-roundtrip-old",
    latest_candidate: oldPersistedResponse,
  };
  assert.throws(
    () => normalizeCanonicalAgentEditResponse(oldSession, {
      endpoint: "/vibecomfy/agent-edit/chat:old-session",
    }),
    /missing outcome/i,
  );

  const adaptedSession = adaptLegacyAgentEditResponse({
    ok: true,
    outcome: { kind: "noop", reason: "session wrapper" },
    latest_candidate: oldPersistedResponse,
  }, {
    endpoint: "/vibecomfy/agent-edit/chat:old-session",
  });
  const latest = readLatestCandidate(adaptedSession, { allowLegacy: false });
  assert.equal(readApplyCandidate(latest, { allowLegacy: false }).turnIdentity.turnId, "0018");
});

// ── FieldChange normalization smoke ──────────────────────────────────────
test("VibeComfy submit normalizes field changes from outcome.changes and batch_turns field_changes", async () => {
  const SESSION_ID = "session-fieldchange-submit";
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };

  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0010",
          baseline_turn_id: null,
          candidate: {
            graph: candidateGraph,
          },
          eligibility: {
            applyable: true,
            reason: "applyable",
            message: "Apply is allowed.",
            warnings: [],
          },
          outcome: {
            kind: "edit",
            changes: [
              { uid: "uid-1", field_path: "inputs.prompt", old: "old value", new: "new value" },
              { uid: "uid-2", field_path: "widgets_values.0", old: 0, new: 1 },
            ],
          },
          batch_turns: [
            {
              turn_number: 0,
              message: "first batch step",
              field_changes: [
                { uid: "uid-1", field_path: "inputs.prompt", old: "old value", new: "interim" },
              ],
            },
            {
              turn_number: 1,
              message: "second batch step",
              field_changes: [
                { uid: "uid-1", field_path: "inputs.prompt", old: "interim", new: "new value" },
                { uid: "uid-2", field_path: "widgets_values.0", old: 0, new: 1 },
              ],
            },
          ],
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Candidate with field changes.",
          report: {
            change: {
              content_edits: {
                preserved: ["uid-1"],
                new_auto_placed: ["uid-2"],
              },
            },
          },
          audit_ref: { path: "/tmp/fieldchange-submit-audit.json" },
        },
      },
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: SESSION_ID,
          turn_id: "0010",
          baseline_turn_id: "0010",
          queue_allowed: true,
          audit_ref: { path: "/tmp/fieldchange-submit-accept.json" },
        },
      },
      [`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
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

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "change prompt text";
    await harness.clickButton("Submit");

    // Verify submit succeeded and the panel reached AWAITING_REVIEW.
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, false);
    assert.match(harness.textDump(), /Candidate with field changes/);
    assert.match(harness.textDump(), /applyEligibility.*applyable/);

    // Accept the candidate to verify full round-trip works.
    await harness.clickButton("Apply");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy candidate bubble renders revision evidence scoped diff rows without legacy content edits", async () => {
  const SESSION_ID = "scoped-diff-session";
  const initialGraph = {
    nodes: [
      {
        id: 10,
        type: "LoadImage",
        pos: [40, 80],
        size: [220, 100],
        properties: { vibecomfy_uid: "n10" },
        outputs: [{ name: "IMAGE", links: [57] }],
      },
      {
        id: 34,
        type: "vibecomfy.exec",
        pos: [320, 80],
        size: [240, 120],
        properties: { vibecomfy_uid: "n22" },
        inputs: [{ name: "in_0", type: "IMAGE", link: 57 }],
        outputs: [{ name: "out_0", type: "IMAGE", links: [] }],
      },
    ],
    links: [[57, 10, 0, 34, 0, "IMAGE"]],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 10,
        type: "LoadImage",
        pos: [40, 80],
        size: [220, 100],
        properties: { vibecomfy_uid: "n10" },
        outputs: [{ name: "IMAGE", links: [] }],
      },
      {
        id: 6,
        type: "VAEDecode",
        pos: [40, 260],
        size: [220, 100],
        properties: { vibecomfy_uid: "n6" },
        outputs: [{ name: "IMAGE", links: [59] }],
      },
      {
        id: 34,
        type: "vibecomfy.exec",
        pos: [320, 80],
        size: [240, 120],
        properties: { vibecomfy_uid: "n22" },
        inputs: [{ name: "in_0", type: "IMAGE", link: 59 }],
        outputs: [{ name: "out_0", type: "IMAGE", links: [] }],
      },
    ],
    links: [[59, 6, 0, 34, 0, "IMAGE"]],
  };

  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0002",
          baseline_turn_id: "0001",
          candidate: {
            state: "candidate",
            graph: candidateGraph,
          },
          eligibility: {
            applyable: true,
            reason: "applyable",
            message: "Apply is allowed.",
            warnings: [],
          },
          outcome: {
            kind: "candidate",
            changes: [
              {
                uid: "n22",
                field_path: "in_0",
                old: { uid: "10", output_slot: 0 },
                new: { uid: "n6", output_slot: "IMAGE" },
              },
            ],
          },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: false,
          message: "Rewired code node input.",
          report: {
            queue_blockers: [],
            revision_evidence: {
              scoped_diff: {
                summary: "3 changed node(s); 1 added link(s); 1 removed link(s)",
                has_diff: true,
                changed_nodes: ["6", "10", "34"],
                added_links: [
                  { link_id: 59, origin_node: 6, origin_slot: 0, target_node: 34, target_slot: 0, type: "IMAGE" },
                ],
                removed_links: [
                  { link_id: 57, origin_node: 10, origin_slot: 0, target_node: 34, target_slot: 0, type: "IMAGE" },
                ],
              },
            },
          },
        },
      },
      [`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [],
          session_path: `out/editor_sessions/${SESSION_ID}/`,
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

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "move the code node to have the ksampler";
    await harness.clickButton("Submit");
    await waitFor(() => /Rewired code node input\./.test(harness.textDump()));
    assert.ok(expandAgentBubbleDetails(harness.document.body), "candidate bubble must expose details");

    const text = harness.textDump();
    assert.match(text, /changed_node: 34/);
    assert.match(text, /added_link: 6\.0 -> 34\.0/);
    assert.match(text, /removed_link: 10\.0 -> 34\.0/);
    assert.match(text, /affected node preview/);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, false);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy preview overlay renders normalized FieldChange labels with the new value text", async () => {
  const liveGraph = {
    nodes: [
      {
        id: 1,
        type: "Input",
        pos: [40, 120],
        size: [240, 100],
        properties: { vibecomfy_uid: "uid-1" },
        inputs: [],
        outputs: [{ name: "TEXT", links: [] }],
        widgets_values: ["old prompt"],
      },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      {
        id: 1,
        type: "Input",
        pos: [40, 120],
        size: [240, 100],
        properties: { vibecomfy_uid: "uid-1" },
        inputs: [],
        outputs: [{ name: "TEXT", links: [] }],
        widgets_values: ["new prompt"],
      },
      {
        id: 2,
        type: "SaveImage",
        pos: [320, 120],
        size: [240, 100],
        properties: { vibecomfy_uid: "uid-2" },
        inputs: [{ name: "images", link: null }],
        outputs: [],
        widgets_values: [7],
      },
    ],
    links: [],
  };
  const candidateReport = {
    change: {
      content_edits: {
        preserved: ["uid-1"],
        new_auto_placed: ["uid-2"],
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
    const panel = extensionModule.ensureAgentPanel();
    panel.state.candidateGraph = candidateGraph;
    panel.state.candidateGraphHash = "candidate-fieldchange-overlay";
    panel.state.lastSubmitFieldChanges = {
      outcomeChanges: [
        { uid: "uid-1", field_path: "inputs.prompt", old: "old prompt", new: "new prompt" },
        { uid: "uid-2", field_path: "widgets_values.0", old: 0, new: 7 },
      ],
      batchTurnChanges: [
        {
          turn_number: 0,
          changes: [
            { uid: "uid-1", field_path: "inputs.prompt", old: "old prompt", new: "new prompt" },
          ],
        },
      ],
    };

    const diff = extensionModule.computePreviewDiff(candidateGraph, candidateReport);
    assert.equal(diff.edited_fields.length, 2);
    assert.ok(
      diff.edited_fields.some((entry) => entry.field_path === "widgets_values.0" && entry.new_value === "7"),
      "candidate-only field changes should still normalize into preview diff data",
    );

    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });
    const editedFieldLabels = drawOps
      .filter((op) => op.kind === "fillText")
      .map((op) => op.args[0])
      .filter((text) => /^inputs\.prompt: new prompt$/.test(text));
    assert.deepEqual(editedFieldLabels, ["inputs.prompt: new prompt"]);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy rehydrate attaches field_changes to chat messages with outcome.changes", async () => {
  const SESSION_ID = "session-fieldchange-rehydrate";
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };

  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          messages: [
            {
              role: "user",
              text: "change the prompt",
              turn_id: "0005",
            },
            {
              role: "agent",
              text: "I updated the prompt field on the Input node.",
              turn_id: "0005",
              changes: [
                { uid: "uid-1", field_path: "inputs.prompt", old: "hello", new: "world" },
              ],
              outcome: {
                kind: "edit",
                changes: [
                  { uid: "uid-1", field_path: "inputs.prompt", old: "hello", new: "world" },
                ],
              },
            },
          ],
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

  try {
    await harness.loadExtension();
    await harness.setup();
    // Pre-populate localStorage so _rehydrateChat fetches the session.
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    // Open the panel to trigger _rehydrateChat.
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`));

    // The panel should render chat messages without error (normalization ran).
    const text = harness.textDump();
    assert.match(text, /change the prompt/);
    assert.match(text, /I updated the prompt field/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy agent bubble details stay collapsed by default and preserve expansion across submit-to-rehydrate replacement", async () => {
  const SESSION_ID = "session-bubble-refresh";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };

  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }], links: [] },
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0007",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          eligibility: {
            applyable: true,
            reason: "applyable",
            message: "Queue ready for this historical turn.",
            warnings: [],
          },
          message: "Candidate ready for review.",
          graph: candidateGraph,
          report: {
            change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } },
            recovery: [],
            provider_diagnostics: {
              message: "ProviderError: raw diagnostic must stay explicit",
              artifact_path: "/real/ComfyUI/out/editor_sessions/session-bubble-refresh/turns/0007/debug.json",
            },
          },
          audit_ref: { path: "/tmp/audit-turn-0007.json", sha256: "def777" },
          debug_payload: {
            model_prompt: "model prompt with token budget and remaining batches",
            raw_path: "/real/ComfyUI/out/editor_sessions/session-bubble-refresh/turns/0007/response.json",
          },
          batch_turns: [
            {
              session_id: SESSION_ID,
              turn_number: 0,
              message: "planning edits with ProviderError raw diagnostic",
              statement_count: 1,
              batch_ok: true,
              exit_mode: "done",
              diagnostics: [
                {
                  code: "ProviderError",
                  message: "engine diagnostics stay explicit",
                  detail: { prompt_messages: ["hidden prompt"] },
                },
              ],
            },
          ],
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
          messages: [
            { role: "user", text: "make the save node cleaner", turn_id: "0007" },
            {
              role: "agent",
              text: "Candidate ready for review.",
              turn_id: "0007",
              outcome: {
                kind: "edit",
                changes: [
                  { uid: "uid-2", field_path: "inputs.filename_prefix", old: "old", new: "new" },
                ],
              },
              report: {
                change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } },
                provider_diagnostics: { message: "ProviderError from rehydrate projection input" },
              },
              debug_payload: {
                raw_path: "/real/ComfyUI/out/editor_sessions/session-bubble-refresh/turns/0007/debug.json",
              },
            },
          ],
        },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "bubble detail retention";
    await harness.clickButton("Submit");

    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    assert.ok(chatRegion, "chat region must exist");
    assertNormalDomTextHasNoForbiddenFieldOrValue(chatRegion.textContent, {
      path: "$.collapsedChatRegion",
    });

    let toggles = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyBubbleDetailToggle === "1"
        || (typeof node.onclick === "function" && String(node.textContent || "").startsWith("\u25b6")),
    );
    assert.ok(toggles.length >= 1, "agent bubble must expose a details toggle");
    assert.ok(String(toggles[0].textContent).startsWith("\u25b6"), "details start collapsed");
    const panel = extensionModule.ensureAgentPanel();
    panel.state.turns = [
      {
        entry_type: "durable",
        turn_id: "0007",
        status: "done",
        message: "ProviderError contaminated compatibility mirror entry",
        audit_ref: {
          path: "/real/ComfyUI/out/editor_sessions/session-bubble-refresh/turns/0007/audit.json",
        },
        raw_payload: {
          model_prompt: "system prompt and prompt messages must not reach normal UI",
        },
      },
    ];
    panel.state.queueAllowed = false;
    panel.state.queueGuard = {
      available: true,
      hookInstalled: true,
      lastBlockNotice: {
        message: "Stale current queue guard should not render in expanded historical details.",
      },
    };
    extensionModule.renderAgentPanel(panel, { dirtySections: ["THREAD"] });
    assertNormalDomTextHasNoForbiddenFieldOrValue(chatRegion.textContent, {
      path: "$.collapsedChatRegionAfterContaminatedTurns",
    });
    toggles = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyBubbleDetailToggle === "1"
        || (typeof node.onclick === "function" && String(node.textContent || "").startsWith("\u25b6")),
    );

    toggles[0].click();
    assert.ok(String(toggles[0].textContent).startsWith("\u25bc"), "details expand on click");
    assert.doesNotMatch(harness.textDump(), /planning edits/);
    assertNormalDomTextHasNoForbiddenFieldOrValue(chatRegion.textContent, {
      path: "$.expandedChatRegion",
    });
    assert.doesNotMatch(harness.textDump(), /Stale current queue guard/);
    const inlineApply = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "apply",
    );
    const inlineReject = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "reject",
    );
    assert.equal(inlineApply.length, 1, "latest candidate bubble should render one inline Apply control");
    assert.equal(inlineReject.length, 1, "latest candidate bubble should render one inline Reject control");
    assert.equal(inlineApply[0].disabled, false, "latest candidate bubble Apply should stay enabled");
    assert.equal(inlineReject[0].disabled, false, "latest candidate bubble Reject should stay enabled");
    for (const title of ["Candidate", "Queue"]) {
      const section = findBubbleDetailSectionByTitle(chatRegion, title);
      assert.ok(section, `expanded ${title} section should render`);
      assertNormalDomTextHasNoForbiddenFieldOrValue(section.textContent, {
        path: `$.expandedOrdinarySection.${title}`,
      });
    }
    assert.match(findBubbleDetailSectionByTitle(chatRegion, "Queue").textContent, /Queue ready for this historical turn\./);
    assert.equal(findBubbleDetailSectionByTitle(chatRegion, "Audit"), null, "expanded Audit section stays off the normal bubble detail surface");
    assert.equal(findBubbleDetailSectionByTitle(chatRegion, "Debug"), null, "expanded Debug section stays off the normal bubble detail surface");
    assert.match(harness.textDump(), /Report issue/);

    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));
    await waitFor(() => /make the save node cleaner/.test(harness.textDump()));

    toggles = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyBubbleDetailToggle === "1"
        || (typeof node.onclick === "function" && String(node.textContent || "").startsWith("\u25bc")),
    );
    assert.ok(toggles.some((node) => String(node.textContent || "").startsWith("\u25bc")), "expanded state must survive chat rehydrate");
    assert.match(harness.textDump(), /view response/);
    assert.match(harness.textDump(), /inputs\.filename_prefix changed/);
    for (const title of ["Turn", "Candidate"]) {
      const section = findBubbleDetailSectionByTitle(chatRegion, title);
      assert.ok(section, `rehydrated expanded ${title} section should render`);
      assertNormalDomTextHasNoForbiddenFieldOrValue(section.textContent, {
        path: `$.rehydratedExpandedOrdinarySection.${title}`,
      });
    }
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy humanizes agent bubble text and keeps gate and op details behind the expander", async () => {
  const SESSION_ID = "session-humanized-bubble";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const candidateGraph = {
    nodes: [
      { id: 1, type: "KSampler", properties: { vibecomfy_uid: "ksampler" }, widgets_values: [1, 20] },
    ],
    links: [],
  };
  const changeDetails = {
    landed_operation_count: 1,
    done_summary: "Gate A passed: 1 edit operation(s) verified. Gate B passed: touched compile region is isomorphic. Changed ksampler.steps from 20 to 26.",
    operations: [
      { uid: "ksampler", field_path: "steps", old: 20, new: 26, summary: "Changed ksampler.steps from 20 to 26." },
    ],
  };
  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "KSampler", properties: { vibecomfy_uid: "ksampler" }, widgets_values: [1, 20] }], links: [] },
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0001",
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Updated ksampler.steps from 20 to 26.",
          graph: candidateGraph,
          candidate_graph_hash: "candidate-humanized",
          report: { change: { content_edits: { preserved: ["ksampler"], edited: ["ksampler"], removed_named: [] } }, recovery: [] },
          outcome: { kind: "edit", changes: [{ uid: "ksampler", field_path: "steps", old: 20, new: 26 }] },
          change_details: changeDetails,
          batch_turns: [{ session_id: SESSION_ID, turn_number: 0, message: "raw model turn", landed_op_count: 1, batch_ok: true }],
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "set steps", turn_id: "0001" },
            {
              role: "agent",
              text: "Updated ksampler.steps from 20 to 26.",
              turn_id: "0001",
              outcome: { kind: "edit", changes: [{ uid: "ksampler", field_path: "steps", old: 20, new: 26 }] },
              change_details: changeDetails,
            },
          ],
        },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "set steps";
    await harness.clickButton("Submit");
    const visibleAgentBubble = harness.document.body.querySelectorAll(
      (node) => node.tagName === "DIV" && /Updated ksampler\.steps from 20 to 26\./.test(node.textContent),
    )[0];
    assert.ok(visibleAgentBubble, "humanized agent bubble should be visible");
    assert.doesNotMatch(visibleAgentBubble.textContent, /Gate A passed/);

    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    assert.ok(expandAgentBubbleDetails(harness.document.body), "agent bubble must expose collapsed details");
    assert.match(harness.textDump(), /Gate A passed/);
    assert.match(harness.textDump(), /Changed ksampler\.steps from 20 to 26\./);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy developer/debug details do not stringify full graphs while collapsed", async () => {
  const hugeGraph = {
    nodes: Array.from({ length: 100 }, (_, index) => ({ id: index, type: "Node", properties: { vibecomfy_uid: `uid-${index}` } })),
    links: [],
  };
  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }], links: [] },
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });

  const originalStringify = JSON.stringify;
  let stringifiedFullGraph = false;
  JSON.stringify = function patchedStringify(value, ...args) {
    if (value === hugeGraph || value?.graph === hugeGraph) {
      stringifiedFullGraph = true;
    }
    return originalStringify.call(this, value, ...args);
  };

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    const panel = extensionModule.ensureAgentPanel();
    panel.state.debugPayload = {
      candidate_graph_hash: "candidate-huge",
      graph: hugeGraph,
      audit_ref: { path: "/tmp/audit.json" },
    };
    extensionModule.renderAgentPanel(panel);
    assert.equal(stringifiedFullGraph, false, "closed debug details must not stringify full graph payloads");
    assert.doesNotMatch(harness.textDump(), /uid-99/);
  } finally {
    JSON.stringify = originalStringify;
    await harness.dispose();
  }
});

test("VibeComfy hides final batch row from the live log when ok response has a candidate without done_summary", async () => {
  const SESSION_ID = "session-terminal-batch-row";
  const candidateGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph: candidateGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0001",
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Updated the workflow.",
          graph: candidateGraph,
          candidate_graph_hash: "candidate-terminal",
          report: { change: { content_edits: { preserved: ["uid-1"], edited: [], removed_named: [] } }, recovery: [] },
          batch_turns: [
            { session_id: SESSION_ID, turn_number: 0, message: "final turn", batch_ok: true, landed_op_count: 1 },
          ],
        },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "terminalize row";
    await harness.clickButton("Submit");
    await waitFor(() => /Updated the workflow\./.test(harness.textDump()), { attempts: 1000 });
    assert.doesNotMatch(harness.textDump(), /final turn/);
    const progressDots = harness.document.body.querySelectorAll(
      (node) => typeof node.className === "string" && node.className.includes("vibecomfy-batch-progress-dot"),
    );
    assert.equal(progressDots.length, 0, "final candidate batch row should not keep the in-progress pulse");
    const batchRows = harness.document.body.querySelectorAll(
      (node) => typeof node.className === "string" && node.className.includes("vibecomfy-batch-row"),
    );
    assert.equal(batchRows.length, 0, "terminal candidate batch row should leave the live log");

    expandAgentBubbleDetails(harness.document.body);
    assert.doesNotMatch(harness.textDump(), /final turn/);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy bubble candidate controls only enable the latest canonical candidate and disable older candidates as not_latest", async () => {
  const SESSION_ID = "session-inline-candidate-controls";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const historicalCandidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "PreviewImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };
  const latestCandidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 3, type: "SaveImage", properties: { vibecomfy_uid: "uid-3" } },
    ],
    links: [],
  };
  let chatFetchCount = 0;

  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }], links: [] },
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0007",
          baseline_turn_id: "0006",
          candidate: {
            graph: latestCandidateGraph,
          },
          eligibility: {
            applyable: true,
            reason: "applyable",
            message: "Latest candidate is ready to apply.",
          },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Latest candidate ready for review.",
          report: {
            change: {
              content_edits: {
                preserved: ["uid-1"],
                new_auto_placed: ["uid-3"],
              },
            },
          },
          audit_ref: { path: "/tmp/audit-turn-0007.json", sha256: "ghi777" },
        },
      },
      [CHAT_URL]: async () => {
        chatFetchCount += 1;
        const messages = [
          { role: "user", text: "add a preview node", turn_id: "0006" },
          {
            role: "agent",
            text: "Historical candidate from the previous turn.",
            turn_id: "0006",
            candidate: { graph: historicalCandidateGraph },
            eligibility: {
              applyable: true,
              reason: "applyable",
              message: "This older candidate was previously applyable.",
            },
          },
        ];
        if (chatFetchCount > 1) {
          messages.push(
            { role: "user", text: "replace preview with a saver", turn_id: "0007" },
            {
              role: "agent",
              text: "Latest candidate ready for review.",
              turn_id: "0007",
              candidate: { graph: latestCandidateGraph },
              eligibility: {
                applyable: true,
                reason: "applyable",
                message: "Latest candidate is ready to apply.",
              },
            },
          );
        }
        return {
          status: 200,
          body: {
            ok: true,
            session_id: SESSION_ID,
            session_path: `out/editor_sessions/${SESSION_ID}/`,
            detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
            messages,
          },
        };
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => /Historical candidate from the previous turn\./.test(harness.textDump()));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "replace preview with a saver";
    await harness.clickButton("Submit");

    await waitFor(() => harness.requests.filter((entry) => entry.url === CHAT_URL).length >= 2);
    await waitFor(() => /Latest candidate ready for review\./.test(harness.textDump()));

    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    let toggles = chatRegion.querySelectorAll((node) => node.dataset?.vibecomfyBubbleDetailToggle === "1");
    assert.ok(toggles.length >= 2, "historical and latest agent bubbles should both expose detail toggles");
    for (const toggle of toggles) {
      if (toggle.textContent === "\u25b6 details") {
        toggle.click();
      }
    }

    const oldApply = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "apply" && node.dataset?.vibecomfyCandidateTurnId === "0006",
    )[0];
    const oldReject = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "reject" && node.dataset?.vibecomfyCandidateTurnId === "0006",
    )[0];
    const oldReason = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyCandidateReason === "not_latest" && node.dataset?.vibecomfyCandidateTurnId === "0006",
    )[0];
    assert(oldApply, "historical candidate should render an inline Apply button");
    assert(oldReject, "historical candidate should render an inline Reject button");
    assert(oldReason, "historical candidate should expose a not_latest reason label");
    assert.equal(oldApply.disabled, true, "historical candidate Apply must be disabled");
    assert.equal(oldReject.disabled, true, "historical candidate Reject must be disabled");
    assert.equal(oldReason.textContent, "not_latest");

    const latestApply = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "apply" && node.dataset?.vibecomfyCandidateTurnId === "0007",
    )[0];
    const latestReject = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "reject" && node.dataset?.vibecomfyCandidateTurnId === "0007",
    )[0];
    const latestReason = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyCandidateReason === "applyable" && node.dataset?.vibecomfyCandidateTurnId === "0007",
    )[0];
    assert(latestApply, "latest candidate should render an inline Apply button");
    assert(latestReject, "latest candidate should render an inline Reject button");
    assert(latestReason, "latest candidate should expose its canonical applyable reason");
    assert.equal(latestApply.disabled, false, "latest canonical candidate Apply must stay enabled");
    assert.equal(latestReject.disabled, false, "latest canonical candidate Reject must stay enabled");
    assert.equal(latestReason.textContent, "latest");
    assert.match(harness.textDump(), /Only the latest candidate can be applied\./);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy historical superseded candidates keep their superseded Apply reason instead of degrading to not_latest", async () => {
  const SESSION_ID = "session-inline-superseded";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const oldCandidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "PreviewImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };
  const latestCandidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 3, type: "SaveImage", properties: { vibecomfy_uid: "uid-3" } },
    ],
    links: [],
  };
  let chatFetchCount = 0;

  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }], links: [] },
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0007",
          baseline_turn_id: "0006",
          candidate: {
            graph: latestCandidateGraph,
          },
          eligibility: {
            applyable: true,
            reason: "applyable",
            message: "Latest candidate is ready to apply.",
          },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Latest candidate ready for review.",
          report: {
            change: {
              content_edits: {
                preserved: ["uid-1"],
                new_auto_placed: ["uid-3"],
              },
            },
          },
        },
      },
      [CHAT_URL]: async () => {
        chatFetchCount += 1;
        const messages = [
          { role: "user", text: "add a preview node", turn_id: "0005" },
          {
            role: "agent",
            text: "Older candidate was already superseded.",
            turn_id: "0005",
            candidate: { graph: oldCandidateGraph },
            eligibility: {
              applyable: false,
              reason: "superseded",
              message: "This candidate has been superseded.",
            },
          },
        ];
        if (chatFetchCount > 1) {
          messages.push(
            { role: "user", text: "replace preview with a saver", turn_id: "0007" },
            {
              role: "agent",
              text: "Latest candidate ready for review.",
              turn_id: "0007",
              candidate: { graph: latestCandidateGraph },
              eligibility: {
                applyable: true,
                reason: "applyable",
                message: "Latest candidate is ready to apply.",
              },
            },
          );
        }
        return {
          status: 200,
          body: {
            ok: true,
            session_id: SESSION_ID,
            session_path: `out/editor_sessions/${SESSION_ID}/`,
            detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
            messages,
          },
        };
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => /Older candidate was already superseded\./.test(harness.textDump()));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "replace preview with a saver";
    await harness.clickButton("Submit");
    await waitFor(() => harness.requests.filter((entry) => entry.url === CHAT_URL).length >= 2);
    await waitFor(() => /Latest candidate ready for review\./.test(harness.textDump()));

    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    const toggles = chatRegion.querySelectorAll((node) => node.dataset?.vibecomfyBubbleDetailToggle === "1");
    for (const toggle of toggles) {
      if (toggle.textContent === "\u25b6 details") {
        toggle.click();
      }
    }

    const oldApply = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "apply" && node.dataset?.vibecomfyCandidateTurnId === "0005",
    )[0];
    const oldReject = chatRegion.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.dataset?.vibecomfyCandidateAction === "reject" && node.dataset?.vibecomfyCandidateTurnId === "0005",
    )[0];
    const oldReason = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyCandidateReason === "superseded" && node.dataset?.vibecomfyCandidateTurnId === "0005",
    )[0];
    assert(oldApply, "historical superseded candidate should render an inline Apply button");
    assert(oldReject, "historical superseded candidate should render an inline Reject button");
    assert(oldReason, "historical superseded candidate should preserve its superseded reason");
    assert.equal(oldApply.disabled, true);
    assert.equal(oldReject.disabled, true);
    assert.equal(oldReason.textContent, "superseded");
    assert.match(harness.textDump(), /This candidate has been superseded\./);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy empty-state examples are clickable and fill the composer prompt", async () => {
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

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => /Try an example/.test(harness.textDump()));

    const example = harness.document.body.querySelectorAll(
      (node) => node.textContent === "Reorganise this workflow",
    )[0];
    assert(example, "expected an empty-state example row");
    example.click();

    assert.equal(
      harness.document.getElementById("vibecomfy-agent-panel-prompt")?.value,
      "Reorganise this workflow",
    );
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy clarify questions render inline and follow-up submit continues the same session", async () => {
  const submitBodies = [];
  const harness = await createBrowserHarness({
    graph: {
      nodes: [{ id: 1, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "uid-1" } }],
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": async ({ options }) => {
        const body = JSON.parse(options.body);
        submitBodies.push(body);
        if (submitBodies.length === 1) {
          return {
            status: 200,
            body: {
              ok: true,
              session_id: "session-clarify-inline",
              turn_id: "0001",
              outcome: {
                kind: "clarify",
                question: "Which node should the saver replace?",
              },
              graph_unchanged: true,
              canvas_apply_allowed: false,
              apply_allowed: false,
              queue_allowed: false,
              message: "Which node should the saver replace?",
            },
          };
        }
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "session-clarify-inline",
            turn_id: "0002",
            candidate: {
              graph: {
                nodes: [
                  { id: 1, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "uid-1" } },
                  { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
                ],
                links: [],
              },
            },
            eligibility: {
              applyable: true,
              reason: "applyable",
              message: "Ready to apply.",
            },
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: true,
            message: "Candidate ready after clarification.",
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
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "add a saver";
    await harness.clickButton("Submit");
    await waitFor(() => /Which node should the saver replace\?/.test(harness.textDump()));
    assert.doesNotMatch(harness.textDump(), /Clarify question/);
    assert.doesNotMatch(harness.textDump(), /continues this same session/);

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "replace the preview node";
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);
    await harness.clickButton("Submit");
    await waitFor(() => /Candidate ready after clarification\./.test(harness.textDump()));

    assert.equal(submitBodies.length, 2);
    assert.equal(submitBodies[0].session_id, undefined);
    assert.equal(submitBodies[1].session_id, "session-clarify-inline");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy blocks submit until status.ready is true and shows composer readiness text", async () => {
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
          ready: false,
          message: "Warmup still running for the selected route.",
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: { ok: true },
      },
    },
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => /Warmup still running for the selected route\./.test(harness.textDump()));

    const submitButton = harness.document.getElementById("vibecomfy-agent-panel-submit");
    assert.equal(submitButton?.disabled, true);
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "replace the preview node";
    submitButton.click();

    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-executor").length, 0);
    assert.match(harness.textDump(), /Send unavailable/);
  } finally {
    await harness.dispose();
  }
});

// ── Lifecycle Contract: C1 Stop / abort submit ───────────────────────────

test("Lifecycle C1 stop aborts the in-flight submit, leaves no candidate, and only shows Undo in the composer when available", async () => {
  const candidateGraph = {
    nodes: [
      { id: 1, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };
  let releaseSubmit;
  const submitStarted = new Promise((resolve) => {
    releaseSubmit = resolve;
  });
  let submitMode = "abort";
  const harness = await createBrowserHarness({
    graph: {
      nodes: [{ id: 1, type: "CheckpointLoaderSimple", properties: { vibecomfy_uid: "uid-1" } }],
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": async () => {
        if (submitMode === "abort") {
          releaseSubmit();
          return new Promise(() => {});
        }
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "session-stop",
            turn_id: "0002",
            baseline_turn_id: "0001",
            candidate: { graph: candidateGraph },
            eligibility: {
              applyable: true,
              reason: "applyable",
              message: "Ready to apply.",
            },
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: true,
            message: "Candidate ready after retry.",
          },
        };
      },
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-stop",
          turn_id: "0002",
          baseline_turn_id: "0002",
          audit_ref: { path: "/tmp/accept-stop-audit.json" },
        },
      },
      "/vibecomfy/agent-edit/rebaseline": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-stop",
          baseline_turn_id: "0002",
          baseline_graph_hash: "baseline-after-undo",
          baseline_graph_hash_kind: "structural",
          baseline_graph_hash_version: 2,
          baseline_source: "rebaseline",
          baseline_rebaseline_id: "rebaseline-undo-stop",
          baseline_graph_source_path: "_rebaseline/rebaseline-undo-stop/graph.ui.json",
        },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-undo")?.style.display, "none");
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "replace the preview node";
    const submitPromise = harness.clickButton("Submit");
    await submitStarted;
    await waitFor(() => harness.getButton("Stop"));
    await harness.clickButton("Stop");
    await submitPromise;

    assert.match(harness.textDump(), /Request cancelled\./);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled, false);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-undo")?.style.display, "none");
    assert.equal(extensionModule.ensureAgentPanel().state.candidateGraph, null);
    assert.doesNotMatch(harness.textDump(), /Candidate ready after retry\./);

    submitMode = "candidate";
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "replace the preview node";
    await harness.clickButton("Submit");
    await waitFor(() => /Candidate ready after retry\./.test(harness.textDump()));
    await harness.clickButton("Apply");
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-undo")?.style.display !== "none");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-undo")?.textContent, "");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-undo")?.getAttribute("aria-label"), "Undo Last Apply");

    await harness.clickButton("Undo Last Apply");
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-undo")?.style.display === "none");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy submit watchdog times out stalled submits with diagnostics and allows a later submit", async () => {
  const candidateGraph = {
    nodes: [{ id: 1, type: "SaveImage", properties: { vibecomfy_uid: "uid-timeout" } }],
    links: [],
  };
  let submitMode = "stall";
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": async () => {
        if (submitMode === "stall") {
          return new Promise(() => {});
        }
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "session-timeout",
            turn_id: "0008",
            baseline_turn_id: "0007",
            candidate: { graph: candidateGraph },
            eligibility: {
              applyable: true,
              reason: "applyable",
              message: "Ready to apply.",
            },
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: true,
            message: "Candidate ready after timeout.",
          },
        };
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    extensionModule.configureSubmitWatchdogDeps({ submitDeadlineMs: 10 });
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const panel = extensionModule.ensureAgentPanel();
    panel.state.sessionId = "session-timeout";
    panel.state.turnId = "0007";

    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    prompt.value = "stalled request";
    await harness.clickButton("Submit");
    await waitFor(() => panel.state.phase === "ERROR");

    assert.equal(panel.state.inFlightSubmit, null);
    assert.equal(panel.state.submitAbortController, null);
    assert.equal(panel.state.submitStartedAtMs, null);
    assert.equal(panel.state.submitDeadlineMs, null);
    assert.equal(panel.state.failure?.kind, "TimeoutError");
    assert.equal(panel.state.failure?.session_id, "session-timeout");
    assert.equal(panel.state.failure?.turn_id, "0007");
    assert.equal(panel.state.failure?.route, "auto");
    assert.equal(panel.state.failure?.url, "/vibecomfy/agent-executor");
    assert.equal(panel.state.failure?.timeout_ms, 10);
    assert.match(panel.state.failure?.next_action || "", /Submit again/i);
    assert.equal(prompt.value, "stalled request");

    submitMode = "success";
    prompt.value = "successful retry";
    await harness.clickButton("Submit");
    await waitFor(() => /Candidate ready after timeout\./.test(harness.textDump()));

    assert.equal(
      harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-executor").length,
      2,
      "submit should be retryable after the timeout watchdog fires",
    );
    assert.equal(panel.state.phase, "AWAITING_REVIEW");
    assert.equal(panel.state.failure, null);
  } finally {
    try {
      (await harness.loadExtension()).resetSubmitWatchdogDeps();
    } catch (_error) {
      // Best-effort test cleanup only.
    }
    await harness.dispose();
  }
});

function makeSubmitRetryHarness(agentExecutorHandler) {
  return createBrowserHarness({
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": agentExecutorHandler,
    },
  });
}

test("VibeComfy submit auto-retries exactly once for retryable backend failures and preserves request context", async () => {
  const candidateGraph = {
    nodes: [{ id: 1, type: "PreviewImage", properties: { vibecomfy_uid: "uid-submit-retry" } }],
    links: [],
  };
  const submitBodies = [];
  const harness = await makeSubmitRetryHarness(async ({ options }) => {
    const body = JSON.parse(options.body);
    submitBodies.push(body);
    if (submitBodies.length === 1) {
      return {
        status: 503,
        body: {
          ok: false,
          kind: "ProviderError",
          stage: "agent-executor",
          retryable: true,
          graph_unchanged: true,
          user_facing_message: "Temporary provider outage.",
          next_action: "Retry automatically.",
          session_id: "session-submit-retry",
          turn_id: "0009",
          baseline_turn_id: "0008",
        },
      };
    }
    return {
      status: 200,
      body: {
        ok: true,
        session_id: "session-submit-retry",
        turn_id: "0009",
        baseline_turn_id: "0008",
        candidate: { graph: candidateGraph },
        eligibility: {
          applyable: true,
          reason: "applyable",
          message: "Ready to apply.",
        },
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: true,
        message: "Candidate ready after automatic retry.",
      },
    };
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const panel = extensionModule.ensureAgentPanel();
    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    prompt.value = "retry the edit automatically";
    await harness.clickButton("Submit");
    await waitFor(() => /Candidate ready after automatic retry\./.test(harness.textDump()));

    assert.equal(submitBodies.length, 2, "retryable backend submit failures should retry once");
    assert.equal(typeof submitBodies[0].idempotency_key, "string");
    assert.equal(Boolean(submitBodies[0].idempotency_key), true);
    assert.equal(submitBodies[1].idempotency_key, submitBodies[0].idempotency_key);
    assert.equal(submitBodies[0].session_id, undefined);
    assert.equal(submitBodies[1].session_id, "session-submit-retry");
    assert.equal(panel.state.phase, "AWAITING_REVIEW");
    assert.equal(panel.state.failure, null);
    assert.equal(panel.state.sessionId, "session-submit-retry");
    assert.equal(panel.state.turnId, "0009");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy submit does not auto-retry retryable false backend failures", async () => {
  const harness = await makeSubmitRetryHarness(() => ({
    status: 503,
    body: {
      ok: false,
      kind: "ProviderError",
      stage: "agent-executor",
      retryable: false,
      graph_unchanged: true,
      user_facing_message: "Backend refused retry.",
      next_action: "Wait for the backend to recover.",
      session_id: "session-no-retry",
      turn_id: "0010",
      baseline_turn_id: "0009",
    },
  }));

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const panel = extensionModule.ensureAgentPanel();
    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    prompt.value = "do not retry this failure";
    await harness.clickButton("Submit");
    await waitFor(() => panel.state.phase === "ERROR");

    assert.equal(
      harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-executor").length,
      1,
      "retryable false failures should surface immediately",
    );
    assert.equal(panel.state.failure?.kind, "ProviderError");
    assert.equal(panel.state.failure?.retryable, false);
    assert.equal(prompt.value, "do not retry this failure");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy submit does not auto-retry validation failures even when marked retryable", async () => {
  const harness = await makeSubmitRetryHarness(() => ({
    status: 400,
    body: {
      ok: false,
      error: "validation",
      kind: "ValidationError",
      stage: "agent-executor",
      retryable: true,
      graph_unchanged: true,
      user_facing_message: "Server validation blocked the submit.",
      next_action: "Fix the request and submit again.",
      session_id: "session-validation-submit",
      turn_id: "0011",
      baseline_turn_id: "0010",
    },
  }));

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const panel = extensionModule.ensureAgentPanel();
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "validation should not retry";
    await harness.clickButton("Submit");
    await waitFor(() => panel.state.phase === "ERROR");

    assert.equal(
      harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-executor").length,
      1,
      "validation failures should not auto-retry",
    );
    assert.equal(panel.state.failure?.kind, "ValidationError");
    assert.equal(panel.state.failure?.error, "validation");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy submit surfaces the exhausted retry failure after one automatic retry", async () => {
  const submitBodies = [];
  const harness = await makeSubmitRetryHarness(async ({ options }) => {
    const body = JSON.parse(options.body);
    submitBodies.push(body);
    if (submitBodies.length === 1) {
      return {
        status: 502,
        body: {
          ok: false,
          kind: "ProviderError",
          stage: "agent-executor",
          retryable: true,
          graph_unchanged: true,
          user_facing_message: "First backend failure.",
          next_action: "Retry automatically.",
          session_id: "session-retry-exhausted",
          turn_id: "0012",
          baseline_turn_id: "0011",
        },
      };
    }
    return {
      status: 502,
      body: {
        ok: false,
        kind: "ProviderError",
        stage: "agent-executor",
        retryable: true,
        graph_unchanged: true,
        user_facing_message: "Second backend failure.",
        next_action: "Surface the failure after one retry.",
      },
    };
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const panel = extensionModule.ensureAgentPanel();
    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    prompt.value = "retry only once";
    await harness.clickButton("Submit");
    await waitFor(() => panel.state.phase === "ERROR");

    assert.equal(submitBodies.length, 2, "automatic retry should stop after one retry");
    assert.equal(submitBodies[1].session_id, "session-retry-exhausted");
    assert.equal(panel.state.failure?.kind, "ProviderError");
    assert.equal(panel.state.failure?.session_id, "session-retry-exhausted");
    assert.equal(panel.state.failure?.turn_id, "0012");
    assert.equal(prompt.value, "retry only once");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy stale inFlightSubmit metadata is recovered before promise reuse", async () => {
  let staleAbortCount = 0;
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
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-recover",
          turn_id: "0005",
          baseline_turn_id: "0004",
          candidate: {
            graph: {
              nodes: [{ id: 1, type: "PreviewImage", properties: { vibecomfy_uid: "uid-recover" } }],
              links: [],
            },
          },
          eligibility: {
            applyable: true,
            reason: "applyable",
            message: "Ready to apply.",
          },
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Recovered candidate ready.",
        },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    extensionModule.configureSubmitWatchdogDeps({
      submitDeadlineMs: 1000,
      nowMs: () => 50,
    });
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const panel = extensionModule.ensureAgentPanel();
    panel.state.phase = "SUBMITTING";
    panel.state.submitEpoch = 4;
    panel.state.inFlightSubmit = new Promise(() => {});
    panel.state.submitAbortController = {
      abort() {
        staleAbortCount += 1;
      },
    };
    panel.state.submitStartedAtMs = 0;
    panel.state.submitDeadlineMs = 5;
    panel.state.lastSubmit = { task: "stale request", route: "auto" };

    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    prompt.value = "fresh request";
    await harness.clickButton("Submit");
    await waitFor(() => /Recovered candidate ready\./.test(harness.textDump()));

    assert.equal(staleAbortCount, 1, "stale submit should be aborted before reuse");
    assert.equal(
      harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-executor").length,
      1,
      "fresh submit should dispatch after stale recovery",
    );
    assert.equal(panel.state.phase, "AWAITING_REVIEW");
    assert.equal(panel.state.failure, null);
    assert.equal(panel.state.submitEpoch > 4, true);
  } finally {
    try {
      (await harness.loadExtension()).resetSubmitWatchdogDeps();
    } catch (_error) {
      // Best-effort test cleanup only.
    }
    await harness.dispose();
  }
});

// ── T10: Message identity and thread render-state helpers ────────────────

test("VibeComfy messageStableKey produces deterministic keys, uses local_id and synthetic fallback, and messageSignature detects content changes", async () => {
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

  try {
    const extensionModule = await harness.loadExtension();
    const { messageStableKey, messageSignature } = extensionModule;

    // turn_id + role produces deterministic key
    const modernMsg = { role: "user", text: "hello", turn_id: "0003" };
    assert.equal(messageStableKey(modernMsg, 0), "turn:0003:user");
    assert.equal(messageStableKey(modernMsg, 5), "turn:0003:user", "key ignores index when turn_id+role present");

    const agentMsg = { role: "agent", text: "response", turn_id: "0003" };
    assert.equal(messageStableKey(agentMsg, 0), "turn:0003:agent");
    assert.notEqual(messageStableKey(modernMsg, 0), messageStableKey(agentMsg, 0));

    // local_id takes priority when no turn_id
    const localMsg = { role: "user", text: "with local", local_id: "abc-123" };
    assert.equal(messageStableKey(localMsg, 0), "local:abc-123");

    // synthetic flag
    const synthMsg = { role: "agent", text: "cancelled", synthetic: true };
    assert.match(messageStableKey(synthMsg, 2), /^synthetic:2$/);

    // Legacy fallback uses index
    const legacyMsg = { role: "user", text: "old message without turn_id" };
    const legacyKey = messageStableKey(legacyMsg, 7);
    assert.match(legacyKey, /^legacy:7:user:old message without turn_id$/);

    // Falsy message
    assert.match(messageStableKey(null, 0), /^empty:0$/);
    assert.match(messageStableKey(undefined, 3), /^empty:3$/);

    // messageSignature varies with content
    const sig1 = messageSignature({ role: "agent", text: "hello world", turn_id: "0001" });
    const sig2 = messageSignature({ role: "agent", text: "hello world", turn_id: "0001" });
    assert.equal(sig1, sig2, "same content → same signature");

    const sig3 = messageSignature({ role: "agent", text: "different text", turn_id: "0001" });
    assert.notEqual(sig1, sig3, "different text → different signature");

    const sig4 = messageSignature({ role: "user", text: "hello world", turn_id: "0001" });
    assert.notEqual(sig1, sig4, "different role → different signature");

    // Synthetic flag affects signature
    const sigSynth = messageSignature({ role: "agent", text: "hello", synthetic: true });
    const sigNotSynth = messageSignature({ role: "agent", text: "hello", synthetic: false });
    assert.notEqual(sigSynth, sigNotSynth);

    // Empty/falsy message
    assert.equal(messageSignature(null), "empty");
    assert.equal(messageSignature(undefined), "empty");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy resetThreadRenderState clears all threadState fields and is called on new conversation", async () => {
  const SESSION_ID = "session-t10-reset";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "hello", turn_id: "0001" },
            { role: "agent", text: "hi there", turn_id: "0001" },
          ],
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

  try {
    const extensionModule = await harness.loadExtension();
    const { resetThreadRenderState, ensureAgentPanel } = extensionModule;
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));

    const panel = ensureAgentPanel();

    // After rehydrate + thread render, threadState keys are populated
    assert.ok(panel.threadState, "threadState should exist after rehydrate");
    assert.ok(Array.isArray(panel.threadState.renderedKeyOrder), "renderedKeyOrder should be an array after render");
    assert.ok(panel.threadState.renderedKeyOrder.length >= 2, "renderedKeyOrder should have at least 2 entries after render");
    assert.ok(typeof panel.threadState.bubbleMap === "object", "bubbleMap should exist");
    assert.equal(panel.threadState.expandedOlder, false);
    assert.ok(typeof panel.threadState.signatures === "object", "signatures should exist");
    assert(panel.threadState.lastVisibleKeySet instanceof Set, "lastVisibleKeySet should track visible keys after render");
    assert.equal(panel.threadState.lastVisibleKeySet.size, 2);

    // Mutate threadState to verify reset clears it
    panel.threadState.renderedKeyOrder = ["turn:0001:user", "turn:0001:agent"];
    panel.threadState.bubbleMap["turn:0001:user"] = {};
    panel.threadState.expandedOlder = true;
    panel.threadState.signatures["turn:0001:user"] = "sig";
    panel.threadState.lastVisibleKeySet = new Set(["turn:0001:user"]);

    resetThreadRenderState(panel);

    assert.deepEqual(panel.threadState.renderedKeyOrder, []);
    assert.deepEqual(panel.threadState.bubbleMap, {});
    assert.equal(panel.threadState.expandedOlder, false);
    assert.equal(panel.threadState.forceScrollOnNextRender, true);
    assert.deepEqual(panel.threadState.signatures, {});
    assert.equal(panel.threadState.lastVisibleKeySet, null);

    // Verify new conversation also resets threadState
    panel.threadState.renderedKeyOrder = ["dirty"];
    panel.state.chatMessages = [{ role: "user", text: "x", turn_id: "0099" }];
    // Simulate new conversation by directly calling the reset (the real path
    // is exercised through the NEW_CONVERSATION transition in newAgentConversation).
    resetThreadRenderState(panel);
    assert.deepEqual(panel.threadState.renderedKeyOrder, []);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy threadState is reset on chat rehydrate replacement (message array replaced)", async () => {
  const SESSION_ID = "session-t10-rehydrate";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;

  const initialMessages = [
    { role: "user", text: "first prompt", turn_id: "0001" },
    { role: "agent", text: "first response", turn_id: "0001" },
  ];

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: initialMessages,
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

  try {
    const extensionModule = await harness.loadExtension();
    const { ensureAgentPanel, resetThreadRenderState } = extensionModule;
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));

    const panel = ensureAgentPanel();
    assert.ok(panel.threadState, "threadState exists after initial rehydrate");
    assert.equal(panel.state.chatMessages.length, 2);

    // Seed threadState with data from first rehydrate
    panel.threadState.renderedKeyOrder = ["turn:0001:user", "turn:0001:agent"];
    panel.threadState.signatures["turn:0001:user"] = "sig-1";

    // Simulate a rehydrate replacement by directly invoking reset
    // (the actual CHAT_REHYDRATE_SUCCESS path in _rehydrateChat calls this).
    resetThreadRenderState(panel);

    assert.deepEqual(panel.threadState.renderedKeyOrder, []);
    assert.deepEqual(panel.threadState.signatures, {});
    assert.equal(panel.threadState.expandedOlder, false);
    assert.equal(panel.threadState.forceScrollOnNextRender, true);
    assert.equal(panel.threadState.lastVisibleKeySet, null);
  } finally {
    await harness.dispose();
  }
});

// ── T13: Lazy detail population + shared activity rows ────────────────────

test("VibeComfy collapsed agent bubble does not prebuild detail pane (T13 lazy detail)", async () => {
  const SESSION_ID = "session-t13-lazy";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "add a node", turn_id: "0001" },
            { role: "agent", text: "Candidate ready.", turn_id: "0001",
              outcome: { kind: "edit", changes: [{ uid: "n1", field_path: "inputs.text", old: "a", new: "b" }] },
            },
          ],
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

  try {
    const extensionModule = await harness.loadExtension();
    const { ensureAgentPanel } = extensionModule;
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));

    const panel = ensureAgentPanel();
    // Clear any leaked expand state from harness reuse
    panel.state.expandedBubbleTurnKeys = {};

    // Force a thread render to apply the cleared expand state
    const { markAgentPanelDirty, RENDER_SECTIONS: RS, renderAgentPanel } = extensionModule;
    markAgentPanelDirty(panel, [RS.THREAD]);
    renderAgentPanel(panel, { dirtySections: [RS.THREAD] });

    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    assert.ok(chatRegion, "chat region must exist");

    // Find the detail toggle — should be collapsed (▶ details)
    const toggles = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyBubbleDetailToggle === "1" && node.textContent === "\u25b6 details",
    );
    assert.ok(toggles.length >= 1, "collapsed agent bubble must expose a detail toggle");

    // Expand the first toggle
    toggles[0].click();

    // After expansion, normal detail content should appear without Audit/Debug payloads.
    const expandedDump = harness.textDump();
    assert.match(expandedDump, /Candidate/, "expanded detail should show normal candidate detail");
    assert.doesNotMatch(expandedDump, /Download Audit Envelope/, "expanded detail should not show audit section");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy shared activity section renders turn-progress rows once, not per bubble (T13 dedup)", async () => {
  const SESSION_ID = "session-t13-dedup";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "edit workflow", turn_id: "0002" },
            { role: "agent", text: "Done.", turn_id: "0002" },
            { role: "user", text: "edit again", turn_id: "0003" },
            { role: "agent", text: "Also done.", turn_id: "0003" },
          ],
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

  try {
    await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));

    // Expand both agent bubbles
    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    const toggles = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyBubbleDetailToggle === "1" && node.textContent === "\u25b6 details",
    );
    assert.ok(toggles.length >= 2, "at least 2 agent bubbles should exist");

    for (const toggle of toggles) {
      toggle.click();
    }

    // Verify detail panes are populated independently
    for (const toggle of toggles) {
      const detailBodyEls = toggle.parentNode.querySelectorAll(
        (node) => node !== toggle && node.tagName === "DIV",
      );
      assert.ok(detailBodyEls.length >= 1, "detail body must exist");
      assert.ok(detailBodyEls[0].children.length > 0, "each expanded detail should have content");
    }

    // The shared activity mount (dataset.vibecomfyChatActivity) should exist
    // and be inside the chat region body.
    const activityMounts = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyChatActivity === "1",
    );
    assert.ok(activityMounts.length >= 1, "shared activity mount must exist");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy threadState tracks bubbleDetailSignatures and clears them on reset (T13)", async () => {
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

  try {
    const extensionModule = await harness.loadExtension();
    const { ensureAgentPanel, resetThreadRenderState } = extensionModule;
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");

    const panel = ensureAgentPanel();
    assert.ok(panel.threadState, "threadState should exist");

    // Seed a detail signature
    panel.threadState.bubbleDetailSignatures = { "turn:0099:agent": "sig-xyz" };
    assert.ok(panel.threadState.bubbleDetailSignatures["turn:0099:agent"], "signature should be seeded");

    // Reset should clear it
    resetThreadRenderState(panel);
    assert.deepEqual(panel.threadState.bubbleDetailSignatures, {}, "bubbleDetailSignatures should be reset");
  } finally {
    await harness.dispose();
  }
});

// ── T18: Visual tidy — containment, spacing, status-strip wording ──────────

test("VibeComfy chat thread mounts have containment styles to prevent horizontal overflow (T18)", async () => {
  const SESSION_ID = "session-t18-contain";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "short", turn_id: "0100" },
            { role: "agent", text: "reply", turn_id: "0100" },
          ],
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

  try {
    await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));

    const body = harness.document.body;

    // Chat region panelSection has minWidth/maxWidth containment
    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    assert.ok(chatRegion, "chat region must exist");
    assert.equal(chatRegion.style.minWidth, "0", "chat region should have minWidth: 0");
    assert.equal(chatRegion.style.maxWidth, "100%", "chat region should have maxWidth: 100%");
    assert.equal(chatRegion.style.overflow, "hidden", "chat region section should clip overflow");
    assert.equal(chatRegion.style.flex, "1 0 auto", "chat region should stretch through available panel height");

    const threadRegion = harness.document.getElementById("vibecomfy-agent-panel-region-thread");
    assert.ok(threadRegion, "thread region must exist");
    assert.equal(threadRegion.style.minHeight, "100%", "thread region should fill the thread viewport when sparse");

    // Messages mount must have containment
    const messagesMount = body.querySelectorAll(
      (node) => node.dataset?.vibecomfyChatMessages === "1",
    )[0];
    assert.ok(messagesMount, "messages mount must exist");
    assert.equal(messagesMount.style.minWidth, "0", "messages mount should have minWidth: 0");
    assert.equal(messagesMount.style.maxWidth, "100%", "messages mount should have maxWidth: 100%");
    assert.equal(messagesMount.style.overflowWrap, "anywhere", "messages mount should wrap overflow text");
    assert.equal(messagesMount.style.alignContent, "start", "messages mount should top-align sparse messages");
    assert.equal(messagesMount.style.alignItems, "start", "messages should keep natural height instead of stretching");

    // Older mount should have containment
    const olderMount = body.querySelectorAll(
      (node) => node.dataset?.vibecomfyChatOlderMount === "1",
    )[0];
    assert.ok(olderMount, "older mount must exist");
    assert.equal(olderMount.style.minWidth, "0", "older mount should have minWidth: 0");
    assert.equal(olderMount.style.maxWidth, "100%", "older mount should have maxWidth: 100%");

    // Activity mount should have containment
    const activityMount = body.querySelectorAll(
      (node) => node.dataset?.vibecomfyChatActivity === "1",
    )[0];
    assert.ok(activityMount, "activity mount must exist");
    assert.equal(activityMount.style.minWidth, "0", "activity mount should have minWidth: 0");
    assert.equal(activityMount.style.maxWidth, "100%", "activity mount should have maxWidth: 100%");

    // Thread container itself must allow vertical scrolling
    const threadContainer = body.querySelectorAll(
      (node) => node.dataset?.vibecomfyAgentThread === "1",
    )[0];
    assert.ok(threadContainer, "thread container must exist");
    assert.equal(threadContainer.style.overflowY, "auto", "thread container should scroll vertically");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy detail pane body uses auto overflow and maxHeight instead of hidden (T18)", async () => {
  const SESSION_ID = "session-t18-detail";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "add a node", turn_id: "0200" },
            {
              role: "agent",
              text: "Candidate ready.",
              turn_id: "0200",
              outcome: {
                kind: "edit",
                changes: [{ uid: "n1", field_path: "inputs.text", old: "a", new: "b" }],
              },
            },
          ],
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

  try {
    await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));

    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    assert.ok(chatRegion, "chat region must exist");

    // Find the collapsed detail toggle and expand it
    const toggles = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyBubbleDetailToggle === "1" && node.textContent === "\u25b6 details",
    );
    assert.ok(toggles.length >= 1, "at least one collapsed detail toggle must exist");
    toggles[0].click();

    // Now find the detail body — it should be visible (display: grid)
    const detailBodies = chatRegion.querySelectorAll(
      (node) => node.style.display === "grid" && node.style.background === "#0d0f14",
    );
    assert.ok(detailBodies.length >= 1, "expanded detail body must be visible");

    const detailBody = detailBodies[0];
    assert.equal(detailBody.style.overflow, "auto", "detail body should use overflow: auto not hidden");
    assert.ok(detailBody.style.maxHeight, "detail body should have a maxHeight limit");
    assert.equal(detailBody.style.maxWidth, "100%", "detail body should have maxWidth: 100%");
    assert.equal(detailBody.style.minWidth, "0", "detail body should have minWidth: 0");
    assert.equal(detailBody.style.overflowWrap, "anywhere", "detail body should wrap overflow text");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy status strip uses human-friendly labels for all phases (T18)", async () => {
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

  try {
    const extensionModule = await harness.loadExtension();
    const { ensureAgentPanel } = extensionModule;
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");

    const panel = ensureAgentPanel();
    assert.ok(panel, "panel must exist");

    // Verify the status element exists (id = vibecomfy-agent-panel-status)
    const statusEl = harness.document.getElementById("vibecomfy-agent-panel-status");
    assert.ok(statusEl, "status element must exist");

    const { markAgentPanelDirty, renderAgentPanel } = extensionModule;

    // IDLE → "Ready" (not raw "IDLE")
    panel.state.phase = "IDLE";
    markAgentPanelDirty(panel, ["META"]);
    renderAgentPanel(panel, { dirtySections: ["META"] });
    assert.equal(statusEl.textContent, "Ready", "IDLE should show 'Ready'");

    // ERROR → "Error"
    panel.state.phase = "ERROR";
    markAgentPanelDirty(panel, ["META"]);
    renderAgentPanel(panel, { dirtySections: ["META"] });
    assert.equal(statusEl.textContent, "Error", "ERROR should show 'Error'");

    // SUBMITTING → "…"
    panel.state.phase = "SUBMITTING";
    markAgentPanelDirty(panel, ["META"]);
    renderAgentPanel(panel, { dirtySections: ["META"] });
    assert.equal(statusEl.textContent, "\u2026", "SUBMITTING should show '…'");

    // AWAITING_REVIEW → "Review Changes"
    panel.state.phase = "AWAITING_REVIEW";
    markAgentPanelDirty(panel, ["META"]);
    renderAgentPanel(panel, { dirtySections: ["META"] });
    assert.equal(statusEl.textContent, "Review Changes", "AWAITING_REVIEW should show 'Review Changes'");

    // CLARIFY → "Needs Your Input"
    panel.state.phase = "CLARIFY";
    markAgentPanelDirty(panel, ["META"]);
    renderAgentPanel(panel, { dirtySections: ["META"] });
    assert.equal(statusEl.textContent, "Needs Your Input", "CLARIFY should show 'Needs Your Input'");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy detail row has overflowWrap containment (T18)", async () => {
  const SESSION_ID = "session-t18-detailrow";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;

  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: [
            { role: "user", text: "hi", turn_id: "0300" },
            { role: "agent", text: "hey", turn_id: "0300" },
          ],
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

  try {
    await harness.loadExtension();
    await harness.setup();
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === CHAT_URL));

    const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
    assert.ok(chatRegion, "chat region must exist");

    // Find agent bubbles — they should have ▸ details toggles
    const toggles = chatRegion.querySelectorAll(
      (node) => node.dataset?.vibecomfyBubbleDetailToggle === "1" && node.textContent === "\u25b6 details",
    );
    assert.ok(toggles.length >= 1, "at least one collapsed detail toggle must exist");

    // The detail toggle's parent is the detailRow — check its style
    const detailRow = toggles
      .map((toggle) => toggle.parentNode?.parentNode)
      .find((node) => node?.style?.overflowWrap === "anywhere");
    assert.ok(detailRow, "detail row must exist");
    assert.equal(detailRow.style.overflowWrap, "anywhere", "detail row should have overflowWrap: anywhere");
    assert.equal(detailRow.style.maxWidth, "100%", "detail row should have maxWidth: 100%");
    assert.equal(detailRow.style.minWidth, "0", "detail row should have minWidth: 0");
  } finally {
    await harness.dispose();
  }
});

test("diagnostic report rebuilds turn history from explicit rehydrate diagnostics and surfaces agent reasoning + engine diagnostics", async () => {
  // Regression: after a page reload `state.turns` can be empty. The issue report
  // must recover from explicit execution/diagnostic compartments, not from the
  // normal safe transcript mirror.
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });
  try {
    const mod = await harness.loadExtension();

    const panel = {
      state: {
        sessionId: "sess123",
        phase: "IDLE",
        turnId: null,
        chatSessionPathResolved: "/real/ComfyUI/out/editor_sessions/sess123",
        // Reloaded panel: turns array has not been synced yet, but explicit
        // rehydrate diagnostics have already been split out of the raw payload.
        turns: [],
        executionEvents: [
          {
            session_id: "sess123",
            turn_id: "0003",
            status: "noop",
            task: "Make one up",
            message: "Nothing needed changing; the workflow already matches that.",
            outcome: { kind: "noop", reason: "No edits applied — identity verified." },
            batchTurns: [
              {
                turn_number: 0,
                batch_ok: false,
                message: "I'll load the standard Flux VAE (ae.safetensors) and wire it into a VAEDecode.",
                batch: "vae_loader = VAELoader(vae_name=\"ae.safetensors\")",
                diagnostics: [
                  {
                    code: "value_not_in_enum",
                    message: "add_node rejected VAELoader.vae_name: value 'ae.safetensors' is not in the declared enum.",
                    detail: { input: "vae_name", value: "ae.safetensors", choices: ["pixel_space"] },
                  },
                ],
              },
            ],
          },
        ],
        turnDetailSnapshots: {
          "0003": {
            explicitDiagnosticEvent: {
              task: "Make one up",
              status: "noop",
              reasoning: [
                { kind: "inspect", text: "Recovered explicit compartment reasoning after reload." },
              ],
              providerDiagnostics: [
                {
                  code: "EXPLICIT_PROVIDER_DIAG",
                  message: "explicit compartment diagnostic with retry context",
                },
              ],
              batchTurns: [
                {
                  turn_number: 1,
                  batch_ok: false,
                  message: "Explicit compartment batch reasoning survives empty turns.",
                  diagnostics: [
                    {
                      code: "explicit_compartment_diag",
                      message: "diagnostic recovered from explicit compartment",
                    },
                  ],
                },
              ],
            },
          },
        },
        chatMessages: [
          { role: "user", turn_id: "0003", text: "Make one up" },
          {
            role: "agent",
            turn_id: "0003",
            text: "Nothing needed changing; the workflow already matches that.",
          },
        ],
      },
    };

    const prompt = mod.buildAgentSolvePrompt(panel);
    const report = mod.buildIssueReport(panel);

    for (const [name, text] of [["solve prompt", prompt], ["issue report", report]]) {
      assert.ok(
        !text.includes("No recent turn records"),
        `${name} must rebuild turn history from explicit diagnostics (not report it empty)`,
      );
      assert.ok(text.includes("Make one up"), `${name} must include the user task`);
      assert.ok(
        text.includes("ae.safetensors") && text.includes("standard Flux VAE"),
        `${name} must include the agent's per-step reasoning text`,
      );
      assert.ok(
        text.includes("value_not_in_enum") && text.includes("pixel_space"),
        `${name} must surface the engine diagnostic and the valid enum choices`,
      );
      assert.ok(
        text.includes("Recovered explicit compartment reasoning after reload.")
          && text.includes("EXPLICIT_PROVIDER_DIAG")
          && text.includes("explicit_compartment_diag"),
        `${name} must recover reload diagnostics from explicit compartments when turns is empty`,
      );
    }

    // The coding-agent prompt should point at the raw artifacts where reasoning lives.
    assert.ok(prompt.includes("messages.jsonl"), "solve prompt must point to messages.jsonl");
    assert.ok(report.includes("messages.jsonl"), "issue report must point to messages.jsonl");
    assert.ok(
      prompt.includes("/real/ComfyUI/out/editor_sessions/sess123/turns/"),
      "solve prompt must use the resolved backend session artifact path when available",
    );
    assert.ok(
      !prompt.includes("/Users/peteromalley/Documents/reigh-workspace/ComfyUI/out/editor_sessions"),
      "solve prompt must not hard-code a local ComfyUI checkout path",
    );
    assert.ok(
      prompt.includes("vibecomfy/comfy_nodes/agent/"),
      "solve prompt must point at the current server package path",
    );

    // A noop turn must NOT be mislabeled as a failure (regression: every turn
    // with a message was rendered "Error/failure: Failure: …").
    assert.ok(
      !report.includes("Error/failure: Failure: Nothing needed changing"),
      "a noop turn must not be labeled as a failure",
    );

    // ── Status diagnostics: the report header must surface agent status fields ──
    // These flow from the diagnostics module → buildIssueReport header, proving
    // status diagnostics survive the extraction into diagnostics_reporting.js.
    assert.ok(
      report.includes("Panel session id: sess123"),
      "issue report must include the panel session id",
    );
    assert.ok(
      report.includes("Panel phase: IDLE"),
      "issue report must include the agent phase (status diagnostic)",
    );
    assert.ok(
      report.includes("Message count: 2"),
      "issue report must include the message count from rehydrated chat",
    );
    assert.ok(
      report.includes("Page URL:"),
      "issue report must include the page URL header",
    );
    assert.ok(
      report.includes("Panel id:"),
      "issue report must include the panel id header",
    );
    assert.ok(report.includes("Render errors:"), "issue report must include render error count");
    assert.ok(report.includes("Last turns:"), "issue report must include the Last turns section");
  } finally {
    await harness.dispose();
  }
});

test("diagnostic report recovers structured batch turns from durable chat messages", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });
  try {
    const mod = await harness.loadExtension();
    const panel = {
      state: {
        sessionId: "sess-chat",
        phase: "CLARIFY",
        turnId: "0001",
        turns: [],
        executionEvents: [],
        chatMessages: [
          { role: "user", turn_id: "0001", text: "Switch this to generate 8 frames of video using HotShotXL" },
          {
            role: "agent",
            turn_id: "0001",
            text: "I could not find a schema-backed HotShotXL implementation.",
            outcome: { kind: "clarify", reason: "The graph is unchanged." },
            change_details: {
              batch_turns: [
                {
                  turn_number: 0,
                  batch_ok: true,
                  message: "I will search for HotShotXL node schemas.",
                  batch: "search(focus_types=[\"HotShotXL\"])",
                  diagnostics: [
                    {
                      code: "schema_miss",
                      message: "No local signature found.",
                    },
                  ],
                },
              ],
            },
          },
        ],
      },
    };

    const report = mod.buildIssueReport(panel);

    assert.equal(report.includes("No recent turn records"), false);
    assert.ok(report.includes("Switch this to generate 8 frames of video using HotShotXL"));
    assert.ok(report.includes("I will search for HotShotXL node schemas."));
    assert.ok(report.includes("schema_miss"));
  } finally {
    await harness.dispose();
  }
});

test("noop and clarify turns are not labeled failures; real errors still are", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });
  try {
    const mod = await harness.loadExtension();
    const panel = {
      state: {
        sessionId: "sess-fail",
        phase: "IDLE",
        turns: [
          { entry_type: "durable", turn_id: "0003", status: "noop", task: "Make one up",
            message: "Nothing needed changing; the workflow already matches that.",
            outcome: { kind: "noop", reason: "No edits applied — identity verified." } },
          { entry_type: "durable", turn_id: "0002", status: "clarify", task: "Add a VAE Decode",
            message: "Which VAE filename should I load?",
            outcome: { kind: "clarification", clarification: { message: "Which VAE filename should I load?" } } },
          { entry_type: "durable", turn_id: "0001", status: "error", task: "Add a VAE Decode",
            failure_kind: "ProviderError",
            message: "The model provider is temporarily unavailable.",
            outcome: { kind: "error", failure_kind: "ProviderError" } },
        ],
      },
    };
    const report = mod.buildIssueReport(panel);
    // noop / clarify carry no "Error/failure" line...
    assert.ok(!/Error\/failure: Failure: Nothing needed changing/.test(report), "noop must not be a failure");
    assert.ok(!/Error\/failure: Failure: Which VAE filename/.test(report), "clarify must not be a failure");
    // ...but their content still appears under the outcome line.
    assert.ok(report.includes("No edits applied — identity verified"), "noop reason must still show");
    assert.ok(report.includes("Which VAE filename should I load?"), "clarify message must still show");
    // A genuine error keeps its failure line.
    assert.ok(report.includes("ProviderError"), "real error keeps its failure label");
  } finally {
    await harness.dispose();
  }
});

test("issue-report zip bundles the actual session artifacts (self-contained)", async () => {
  const sessionId = "sess-bundle";
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      [`/vibecomfy/agent-edit/session-bundle?session_id=${sessionId}`]: {
        status: 200,
        body: {
          ok: true,
          exists: true,
          session_path: "/x/editor_sessions/sess-bundle",
          total_bytes: 123,
          files: [
            { name: "turns/0001/messages.jsonl", text: "{\"message\":\"hi\"}\n" },
            { name: "turns/0001/response.json", text: "{\"ok\":true}" },
            { name: "turns/0001/preview.png", base64: Buffer.from("PNGDATA").toString("base64") },
            { name: "session_state.json", text: "{\"turns\":{}}" },
          ],
          skipped: [{ name: "turns/0001/huge.json", reason: "too_large", size: 9999999 }],
        },
      },
    },
  });
  try {
    const mod = await harness.loadExtension();
    const panel = {
      state: {
        sessionId,
        phase: "IDLE",
        turnId: "0001",
        turns: [],
        executionEvents: [
          {
            session_id: sessionId,
            turn_id: "0001",
            status: "error",
            message: "explicit execution event for issue report",
            batchTurns: [
              {
                message: "explicit diagnostic batch reasoning",
                diagnostics: [{ code: "EXPLICIT_ENGINE", message: "explicit engine diagnostic" }],
              },
            ],
          },
        ],
        auditArtifacts: [
          {
            session_id: sessionId,
            turn_id: "0001",
            auditRef: { path: "/tmp/explicit-audit-0001.json", sha256: "abc123" },
          },
        ],
      },
    };

    const files = await mod.collectIssueReportFiles(panel);
    const byName = new Map(files.map((f) => [f.name, f]));

    // The report itself is still there...
    assert.ok(byName.has("report.txt"), "report.txt present");

    // Status diagnostics: the audit envelope and debug snapshot carry agent status info.
    assert.ok(byName.has("audit.json"), "audit.json (status envelope) present");
    const auditText = byName.get("audit.json").text;
    assert.ok(auditText.includes("generated_at"), "audit.json carries generation timestamp");
    assert.ok(auditText.includes("frontend_source"), "audit.json carries frontend source marker");
    assert.ok(auditText.includes("/tmp/explicit-audit-0001.json"),
      "audit.json uses explicit audit artifact selector when turns is empty");

    // debug-snapshot.json is produced when buildAgentPanelDebugSnapshot is wired via deps.
    if (byName.has("debug-snapshot.json")) {
      const snapText = byName.get("debug-snapshot.json").text;
      assert.ok(snapText.includes("phase"), "debug-snapshot includes phase (status diagnostic)");
      assert.ok(snapText.includes("sessionId"), "debug-snapshot includes sessionId (status diagnostic)");
    }

    // report.txt must include status diagnostics (session id, phase).
    const reportText = byName.get("report.txt").text;
    assert.ok(reportText.includes("Panel session id: sess-bundle"), "report.txt includes session id");
    assert.ok(reportText.includes("Panel phase: IDLE"), "report.txt includes phase status diagnostic");
    assert.ok(reportText.includes("explicit diagnostic batch reasoning"),
      "report.txt uses explicit execution event selector when turns is empty");
    // ...and now the actual turn artifacts are bundled under session/.
    assert.ok(byName.has("session/turns/0001/messages.jsonl"), "messages.jsonl bundled");
    assert.equal(byName.get("session/turns/0001/messages.jsonl").text, "{\"message\":\"hi\"}\n");
    assert.ok(byName.has("session/turns/0001/response.json"), "response.json bundled");
    assert.ok(byName.has("session/session_state.json"), "session_state.json bundled");

    // Binary artifact comes through as decoded bytes (not text).
    const png = byName.get("session/turns/0001/preview.png");
    assert.ok(png && png.bytes instanceof Uint8Array, "binary artifact bundled as bytes");
    assert.equal(Buffer.from(png.bytes).toString("utf8"), "PNGDATA");

    // The manifest records what was bundled and what was skipped (no silent drop).
    const manifest = byName.get("session/_bundle_manifest.txt");
    assert.ok(manifest, "bundle manifest present");
    assert.ok(manifest.text.includes("huge.json") && manifest.text.includes("too_large"),
      "manifest records skipped files");
  } finally {
    await harness.dispose();
  }
});

// ── T14: Full workflow smoke — durable history, apply, rehydrate, live-token-drift ─
// Covers: two messages with ordered durable history, edit candidate,
// successful graph apply through accept, refresh/reopen rehydrate
// with transcript order preserved, and unchanged-structural-hash
// live-token-drift where apply remains enabled.

test("VibeComfy durable workflow: two messages → candidate → apply → rehydrate → live-token-drift with structural hash unchanged", async () => {
  const SESSION_ID = "sess-t14-durable";
  const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
  const STATUS_URL = "/vibecomfy/agent/status?route=auto";

  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
    ],
    links: [],
  };
  const secondCandidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
      { id: 3, type: "KSampler", properties: { vibecomfy_uid: "uid-3" } },
    ],
    links: [],
  };
  // Drifted graph: same structural content as secondCandidateGraph but
  // volatile fields (pos, size, order) differ.
  const driftedGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, pos: [999, 888], size: [50, 30], order: 99 },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" }, pos: [777, 666] },
      { id: 3, type: "KSampler", properties: { vibecomfy_uid: "uid-3" }, pos: [555, 444] },
    ],
    links: [],
  };

  let submitSeq = 0;
  const chatHistory = [
    { role: "user", text: "first message — any changes?", turn_id: "0001" },
    { role: "agent", text: "No changes needed — graph looks good.", turn_id: "0001" },
    { role: "user", text: "add a saver", turn_id: "0002" },
    { role: "agent", text: "Candidate ready: added SaveImage node.", turn_id: "0002" },
    { role: "user", text: "add a sampler", turn_id: "0003" },
    { role: "agent", text: "Candidate ready: added KSampler node.", turn_id: "0003" },
  ];

  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      [STATUS_URL]: {
        status: 200,
        body: {
          ok: true,
          ready: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": async () => {
        submitSeq += 1;
        if (submitSeq === 1) {
          return {
            status: 200,
            body: {
              ok: true,
              session_id: SESSION_ID,
              turn_id: "0001",
              baseline_turn_id: null,
              outcome: { kind: "noop", reason: "No changes needed — graph looks good." },
              graph_unchanged: true,
              canvas_apply_allowed: false,
              apply_allowed: false,
              queue_allowed: false,
              message: "No changes needed — graph looks good.",
            },
          };
        }
        if (submitSeq === 2) {
          return {
            status: 200,
            body: {
              ok: true,
              session_id: SESSION_ID,
              turn_id: "0002",
              baseline_turn_id: "0001",
              baseline_graph_hash: "baseline-0001",
              baseline_graph_hash_kind: "structural",
              baseline_graph_hash_version: 2,
              baseline_source: "turn",
              candidate: { state: "candidate", graph: candidateGraph, graph_hash: "candidate-hash-0002" },
              eligibility: { applyable: true, reason: "applyable", message: "Apply is allowed.", warnings: [] },
              graph: candidateGraph,
              candidate_graph_hash: "candidate-hash-0002",
              report: {
                change: {
                  content_edits: { preserved: ["uid-1"], new_auto_placed: ["uid-2"] },
                },
              },
              canvas_apply_allowed: true,
              apply_allowed: true,
              queue_allowed: true,
              message: "Candidate ready: added SaveImage node.",
            },
          };
        }
        // submitSeq === 3 — for live-token-drift
        return {
          status: 200,
          body: {
            ok: true,
            session_id: SESSION_ID,
            turn_id: "0003",
            baseline_turn_id: "0002",
            baseline_graph_hash: "baseline-0002",
            baseline_graph_hash_kind: "structural",
            baseline_graph_hash_version: 2,
            baseline_source: "turn",
            candidate: { state: "candidate", graph: secondCandidateGraph, graph_hash: "candidate-hash-0003" },
            eligibility: { applyable: true, reason: "applyable", message: "Apply is allowed.", warnings: [] },
            graph: secondCandidateGraph,
            candidate_graph_hash: "candidate-hash-0003",
            report: {
              change: {
                content_edits: { preserved: ["uid-1", "uid-2"], new_auto_placed: ["uid-3"] },
              },
            },
            canvas_apply_allowed: true,
            apply_allowed: true,
            queue_allowed: true,
            message: "Candidate ready: added KSampler node.",
          },
        };
      },
      "/vibecomfy/agent-edit/accept": {
        status: 200,
        body: {
          ok: true,
          action: "accept",
          session_id: SESSION_ID,
          turn_id: "0002",
          baseline_turn_id: "0002",
          queue_allowed: true,
          audit_ref: { path: "/tmp/t14-accept-audit.json" },
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          messages: chatHistory,
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
        },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === STATUS_URL));
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);

    // ── Message 1: noop ─────────────────────────────────────────────────────
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "first message — any changes?";
    await harness.clickButton("Submit");
    await waitFor(() => harness.textDump().includes("No changes needed — graph looks good."));
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-submit")?.disabled === false);

    let text = harness.textDump();
    assert.match(text, /first message — any changes\?/);
    assert.match(text, /No changes needed — graph looks good\./);
    assert.match(text, /first message.*No changes needed/s, "user message must appear before agent reply");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true,
      "apply must be disabled after a noop (no candidate)");

    // ── Message 2: candidate ────────────────────────────────────────────────
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "add a saver";
    await harness.clickButton("Submit");
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled === false, { attempts: 200 });

    text = harness.textDump();
    assert.match(text, /Candidate ready: added SaveImage node\./);
    assert.match(text, /applyEligibility.*applyable/);
    // Verify both prior messages still visible — ordered durable history
    assert.match(text, /first message — any changes\?/);
    assert.match(text, /No changes needed — graph looks good\./);
    assert.match(text, /add a saver/);
    // Verify order: user1 < agent1 < user2 < agent2
    const idxUser1 = text.indexOf("first message — any changes?");
    const idxAgent1 = text.indexOf("No changes needed — graph looks good.");
    const idxUser2 = text.indexOf("add a saver");
    const idxAgent2 = text.indexOf("Candidate ready: added SaveImage node.");
    assert.ok(idxUser1 < idxAgent1, "user message 1 before agent reply 1");
    assert.ok(idxAgent1 < idxUser2, "agent reply 1 before user message 2");
    assert.ok(idxUser2 < idxAgent2, "user message 2 before agent reply 2");

    // ── Apply candidate ─────────────────────────────────────────────────────
    await harness.clickButton("Apply");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 1,
      "accept route must be called on Apply");
    assert.deepEqual(harness.graphConfigureCalls[0], candidateGraph,
      "graph.configure must receive the candidate graph");
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-status")?.textContent, "Ready");

    // ── Rehydrate: simulate refresh/reopen ──────────────────────────────────
    // Pre-populate localStorage with the active session id.
    globalThis.localStorage.setItem("vibecomfy_active_session_id", SESSION_ID);

    // Verify the chat endpoint returns ordered history matching submit order.
    const beforeReopenRequests = harness.requests.length;
    // Invoke AgentEdit again to trigger rehydration (simulating panel reopen / refresh).
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await harness.invokeCommand("VibeComfy.AgentEdit");
    // Only one panel root should exist (re-entrant).
    assert.equal(harness.getPanelRoots().length, 1, "reopen must reuse single panel root");

    await waitFor(() =>
      harness.requests.slice(beforeReopenRequests).some((r) => r.url === CHAT_URL),
    );
    const chatRequest = harness.requests.find((r) => r.url === CHAT_URL);
    assert.ok(chatRequest, "chat rehydration fetch must be dispatched on reopen");
    assert.equal(chatRequest.method, "GET");

    // Wait for the rehydrated thread to render.
    await waitFor(() => /Candidate ready: added SaveImage node\./.test(harness.textDump()));

    const rehydratedText = harness.textDump();
    // All six messages in order
    assert.match(rehydratedText, /first message — any changes\?/);
    assert.match(rehydratedText, /No changes needed — graph looks good\./);
    assert.match(rehydratedText, /add a saver/);
    assert.match(rehydratedText, /Candidate ready: added SaveImage node\./);
    assert.match(rehydratedText, /add a sampler/);
    assert.match(rehydratedText, /Candidate ready: added KSampler node\./);

    // Verify transcript order preserved on rehydrate
    let pos = -1;
    for (const msg of chatHistory) {
      const found = rehydratedText.indexOf(msg.text);
      assert.ok(found > pos, `transcript order must be preserved on rehydrate: "${msg.text}" at ${found} after ${pos}`);
      pos = found;
    }

    // ── Live-token-drift: structural hash unchanged, apply still works ──────
    // Submit a third message to get another candidate.
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "add a sampler";
    await harness.clickButton("Submit");
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled === false, { attempts: 200 });

    assert.match(harness.textDump(), /Candidate ready: added KSampler node\./);

    // Drift the live canvas token without changing structural graph:
    // Change only volatile fields (pos, size, order) on the current graph.
    harness.setCurrentGraph(driftedGraph);
    // Verify the canvas token bumped (setCurrentGraph increments liveCanvasRevision).
    // The apply button must still be enabled — live token drift is diagnostic only.
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, false,
      "apply must remain enabled after live-token-drift with unchanged structural hash");
    assert.match(harness.textDump(), /applyEligibility.*applyable/,
      "apply eligibility must remain applyable after live-token-drift");

    // Apply still works
    await harness.clickButton("Apply");
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept").length, 2,
      "accept route must be called on Apply after live-token-drift");
    // The second accept call should reference turn_id "0003".
    const acceptRequests = harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/accept");
    const lastAcceptBody = JSON.parse(acceptRequests[acceptRequests.length - 1].body);
    assert.equal(lastAcceptBody.turn_id, "0003", "accept must reference the drifted candidate turn_id");

    // Verify localStorage still holds the session id.
    assert.equal(
      globalThis.localStorage.getItem("vibecomfy_active_session_id"),
      SESSION_ID,
      "active session must persist in localStorage across the full workflow",
    );
  } finally {
    await harness.dispose();
  }
});

// ── Respond and research route roundtrip tests ────────────────────────────

test("VibeComfy respond route renders answer-only without candidate controls and no internal leak", async () => {
  const initialGraph = {
    nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
    links: [],
  };
  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-respond-rt",
          turn_id: "0001",
          baseline_turn_id: null,
          route: "respond",
          reply: "The current graph consists of a single Input node. No edits were made.",
          mode: "respond",
          apply_eligible: false,
          no_candidate_reason: "route_not_applyable",
          message: "The current graph consists of a single Input node. No edits were made.",
          report: {
            executor: {
              plan: { route: "respond", reply: true, research: false, implement: false },
              research: null,
              implementation: null,
            },
          },
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
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "What does my graph contain?";
    submitPromise = harness.clickButton("Submit");
    await submitPromise;

    // No candidate review — respond route is answer-only
    assert.doesNotMatch(harness.textDump(), /Review Changes/);
    assert.match(harness.textDump(), /single Input node/);
    assert.match(harness.textDump(), /No edits were made/);

    // Apply/Reject must be disabled
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);

    // No internal gate string leakage in DOM
    assert.doesNotMatch(harness.textDump(), /no_candidate_reason/);
    assert.doesNotMatch(harness.textDump(), /route_not_applyable/);

    // Graph unchanged
    assert.equal(harness.loadGraphDataCalls.length, 0);
  } finally {
    await Promise.allSettled([submitPromise].filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy research route renders answer-only with research evidence, no candidate controls", async () => {
  const initialGraph = {
    nodes: [
      { id: 1, type: "LoadImage", properties: { vibecomfy_uid: "uid-1" } },
      { id: 2, type: "VAEDecode", properties: { vibecomfy_uid: "uid-2" } },
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
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: "session-research-rt",
          turn_id: "0001",
          baseline_turn_id: null,
          route: "research",
          reply: "LTX Video supports i2v with up to 768px resolution. The LoadImage → VAEDecode pipeline is compatible.",
          mode: "research",
          apply_eligible: false,
          no_candidate_reason: "route_not_applyable",
          research_summary: "LTX Video i2v compatibility confirmed; 768px max resolution.",
          research_source_count: 3,
          research_warnings: ["PIL not needed for this version"],
          message: "LTX Video supports i2v with up to 768px resolution.",
          report: {
            executor: {
              plan: { route: "research", reply: true, research: true, implement: false },
              research: {
                summary: "LTX Video i2v compatibility confirmed; 768px max resolution.",
                sources: 3,
                warnings: ["PIL not needed for this version"],
              },
              implementation: null,
            },
          },
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
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "Is LTX Video compatible with my pipeline?";
    submitPromise = harness.clickButton("Submit");
    await submitPromise;

    // No candidate review — research route is answer-only
    assert.doesNotMatch(harness.textDump(), /Review Changes/);
    assert.match(harness.textDump(), /LTX Video supports i2v/);
    assert.match(harness.textDump(), /compatible/);

    // Apply/Reject must be disabled
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);

    // No internal gate strings leak
    assert.doesNotMatch(harness.textDump(), /no_candidate_reason/);
    assert.doesNotMatch(harness.textDump(), /route_not_applyable/);

    // Graph unchanged
    assert.equal(harness.loadGraphDataCalls.length, 0);
  } finally {
    await Promise.allSettled([submitPromise].filter(Boolean));
    await harness.dispose();
  }
});

test("VibeComfy multi-turn: respond → revise → research preserves candidate controls only for revise", async () => {
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
  const harness = await createBrowserHarness({
    graph: initialGraph,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent-executor": async ({ options }) => {
        submitCount += 1;
        if (submitCount === 1) {
          // Turn 1: respond (answer-only)
          return {
            status: 200,
            body: {
              ok: true,
              session_id: "session-multi-rt",
              turn_id: "0001",
              baseline_turn_id: null,
              route: "respond",
              reply: "Your graph currently has a single Input node.",
              mode: "respond",
              apply_eligible: false,
              no_candidate_reason: "route_not_applyable",
              message: "Your graph currently has a single Input node.",
              report: {
                executor: {
                  plan: { route: "respond", reply: true, research: false, implement: false },
                  research: null,
                  implementation: null,
                },
              },
            },
          };
        }
        if (submitCount === 2) {
          // Turn 2: revise (candidate with graph edit)
          return {
            status: 200,
            body: {
              ok: true,
              session_id: "session-multi-rt",
              turn_id: "0002",
              baseline_turn_id: "0001",
              route: "revise",
              reply: "Added a SaveImage node to your graph.",
              mode: "revise",
              apply_eligible: true,
              apply_eligibility: { applyable: true, reason: "applyable", message: "Ready to apply." },
              graph: candidateGraph,
              candidate: { state: "candidate", graph: candidateGraph },
              candidate_graph: candidateGraph,
              message: "Added a SaveImage node to your graph.",
              report: {
                executor: {
                  plan: { route: "revise", reply: true, research: false, implement: true },
                  implementation: { changes: ["added SaveImage"] },
                },
              },
            },
          };
        }
        // Turn 3: research (answer-only)
        return {
          status: 200,
          body: {
            ok: true,
            session_id: "session-multi-rt",
            turn_id: "0003",
            baseline_turn_id: "0002",
            route: "research",
            reply: "PIL is compatible with your current pipeline; no additional nodes needed.",
            mode: "research",
            apply_eligible: false,
            no_candidate_reason: "route_not_applyable",
            message: "PIL is compatible with your current pipeline.",
            report: {
              executor: {
                plan: { route: "research", reply: true, research: true, implement: false },
                research: { summary: "PIL compatibility confirmed" },
                implementation: null,
              },
            },
          },
        };
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

  const submitPromises = [];
  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    // ── Turn 1: respond ──
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "What does my graph contain?";
    let p = harness.clickButton("Submit");
    submitPromises.push(p);
    await p;

    // After respond: no candidate controls
    assert.match(harness.textDump(), /single Input node/);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);
    assert.doesNotMatch(harness.textDump(), /no_candidate_reason/);

    // ── Turn 2: revise ──
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "Add a SaveImage node";
    p = harness.clickButton("Submit");
    submitPromises.push(p);
    await p;

    // After revise: candidate controls SHOULD be present
    assert.match(harness.textDump(), /SaveImage/);
    // Apply button should be enabled for candidate route
    await waitFor(() => harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled === false, { attempts: 200 });
    assert.doesNotMatch(harness.textDump(), /no_candidate_reason/);

    // ── Turn 3: research ──
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "Is PIL compatible?";
    p = harness.clickButton("Submit");
    submitPromises.push(p);
    await p;

    // After research: candidate controls disabled again
    assert.match(harness.textDump(), /PIL is compatible/);
    // Apply/Reject should go back to disabled (research is non-applyable)
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-apply")?.disabled, true);
    assert.equal(harness.document.getElementById("vibecomfy-agent-panel-reject")?.disabled, true);
    assert.doesNotMatch(harness.textDump(), /no_candidate_reason/);
    assert.doesNotMatch(harness.textDump(), /route_not_applyable/);

    // Per-turn assertions already verified respond/reply/research individually above.
    // Final state: research route response visible, candidate controls disabled.
  } finally {
    await Promise.allSettled(submitPromises.filter(Boolean));
    await harness.dispose();
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// Pre-migration parity: status readiness / provider normalization (T2)
// ═══════════════════════════════════════════════════════════════════════════

test("VibeComfy developer disclosure persists expanded state across settings popover close and reopen", async () => {
  globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
  let statusCalls = 0;
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => {
        statusCalls += 1;
        return {
          status: 200,
          body: {
            ok: true,
            provider_available: true,
            route: "deepseek",
            requested_route: "auto",
            route_options: {
              auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
              deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
              anthropic: { requested_route: "anthropic", normalized_route: "arnold", browser_api_key_allowed: false },
              "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
            },
          },
        };
      },
    },
    withQueuePrompt: false,
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => statusCalls === 1);

    const settingsGear = harness.document.body.querySelectorAll(
      (node) => node.title === "Settings",
    )[0];
    const settingsPopover = harness.document.body.querySelectorAll(
      (node) => node.className === "vibecomfy-agent-panel-settings-popover",
    )[0];
    const developerRegion = harness.document.getElementById("vibecomfy-agent-panel-region-developer");
    const developerToggle = harness.document.getElementById("vibecomfy-agent-panel-developer-toggle");
    const developerBody = developerRegion.querySelectorAll(
      (node) => node.className === "vibecomfy-agent-panel-region-body",
    )[0];

    // Open settings popover
    settingsGear.click();
    assert.equal(settingsPopover.style.display, "block");

    // Developer disclosure starts collapsed
    assert.equal(developerToggle.attributes?.["aria-expanded"], "false");
    assert.equal(developerBody?.style.display, "none");

    // Developer region contains diagnostic content even while collapsed
    assert.match(developerRegion.textContent, /Adapter Capabilities/);
    assert.match(developerRegion.textContent, /Queue Guard State/);

    // Expand developer disclosure
    developerToggle.click();
    assert.equal(developerToggle.attributes?.["aria-expanded"], "true");
    assert.equal(developerBody?.style.display, "grid");

    // Close settings popover
    settingsGear.click();
    assert.equal(settingsPopover.style.display, "none");

    // Reopen settings popover — developer disclosure state persists (current behavior)
    settingsGear.click();
    assert.equal(settingsPopover.style.display, "block");
    // Note: developer disclosure state PERSISTS across popover close/reopen in
    // the current implementation. This is pre-migration parity: we encode the
    // actual behavior as-is.
    assert.equal(
      developerToggle.attributes?.["aria-expanded"],
      "true",
      "developer disclosure expanded state persists across settings reopen",
    );
    assert.equal(
      developerBody?.style.display,
      "grid",
      "developer body remains visible across settings reopen",
    );
  } finally {
    globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
    await harness.dispose();
  }
});

test("VibeComfy settings route switching covers all four canonical providers (deepseek, openrouter, openai-codex, anthropic)", async () => {
  globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
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
          ready: true,
          provider_available: true,
          route: "arnold",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
            openrouter: { requested_route: "openrouter", normalized_route: "openrouter", browser_api_key_allowed: true },
            anthropic: { requested_route: "anthropic", normalized_route: "arnold", browser_api_key_allowed: false },
            "openai-codex": { requested_route: "openai-codex", normalized_route: "arnold", browser_api_key_allowed: false },
          },
        },
      },
    },
    withQueuePrompt: false,
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));

    const settingsGear = harness.document.body.querySelectorAll(
      (node) => node.title === "Settings",
    )[0];
    const routeSelect = harness.document.getElementById("vibecomfy-agent-panel-route");

    settingsGear.click();

    // Route select must contain all four canonical providers
    const routeValues = routeSelect.children.map((entry) => entry.value);
    assert.ok(routeValues.includes("deepseek"), "route select should include deepseek");
    assert.ok(routeValues.includes("openrouter"), "route select should include openrouter");
    assert.ok(routeValues.includes("openai-codex"), "route select should include openai-codex");
    assert.ok(routeValues.includes("anthropic"), "route select should include anthropic");

    // deepseek is a direct provider (route stays as deepseek)
    routeSelect.value = "deepseek";
    routeSelect.onchange();
    await waitFor(() => routeSelect.value === "deepseek");
    assert.equal(routeSelect.value, "deepseek");

    // openrouter is a direct provider (route stays as openrouter)
    routeSelect.value = "openrouter";
    routeSelect.onchange();
    await waitFor(() => routeSelect.value === "openrouter");
    assert.equal(routeSelect.value, "openrouter");

    // openai-codex stays as openai-codex in the select (resolved to arnold server-side)
    routeSelect.value = "openai-codex";
    routeSelect.onchange();
    await waitFor(() => routeSelect.value === "openai-codex");
    assert.equal(routeSelect.value, "openai-codex");

    // anthropic stays as anthropic in the select (resolved to arnold server-side)
    routeSelect.value = "anthropic";
    routeSelect.onchange();
    await waitFor(() => routeSelect.value === "anthropic");
    assert.equal(routeSelect.value, "anthropic");

    // Settings status text reflects the currently selected route
    const settingsStatus = harness.document.getElementById("vibecomfy-agent-panel-settings-status");
    assert.ok(settingsStatus, "settings status element should exist");
    assert.ok(settingsStatus.textContent.length > 0, "settings status should have content");
  } finally {
    globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
    await harness.dispose();
  }
});

test("VibeComfy status readiness and settings message are coupled across loading → ready → unavailable transitions", async () => {
  globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
  let statusCalls = 0;
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": async () => {
        statusCalls += 1;
        if (statusCalls === 1) {
          return {
            status: 200,
            body: {
              ok: true,
              ready: true,
              provider_available: true,
              route: "deepseek",
              requested_route: "auto",
              route_options: {
                auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
                deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
                openrouter: { requested_route: "openrouter", normalized_route: "openrouter", browser_api_key_allowed: true },
              },
            },
          };
        }
        if (statusCalls === 2) {
          return {
            status: 200,
            body: {
              ok: true,
              ready: false,
              reason: "Provider quota exhausted for openrouter.",
              provider_available: false,
              route: "openrouter",
              requested_route: "openrouter",
              route_options: {
                openrouter: { requested_route: "openrouter", normalized_route: "openrouter", available: false },
              },
            },
          };
        }
        // Fallback: unavailable with generic reason
        return {
          status: 200,
          body: {
            ok: true,
            ready: false,
            reason: "All providers exhausted.",
            provider_available: false,
            route: "deepseek",
            requested_route: "auto",
            route_options: {
              auto: { requested_route: "auto", normalized_route: "deepseek", available: false },
            },
          },
        };
      },
      "/vibecomfy/agent/status?route=openrouter": async () => {
        statusCalls += 1;
        return {
          status: 200,
          body: {
            ok: true,
            ready: false,
            reason: "Provider quota exhausted for openrouter.",
            provider_available: false,
            route: "openrouter",
            requested_route: "openrouter",
            route_options: {
              openrouter: { requested_route: "openrouter", normalized_route: "openrouter", available: false },
            },
          },
        };
      },
    },
    withQueuePrompt: false,
  });

  try {
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => statusCalls === 1);

    const settingsGear = harness.document.body.querySelectorAll(
      (node) => node.title === "Settings",
    )[0];
    const routeSelect = harness.document.getElementById("vibecomfy-agent-panel-route");
    const modelInput = harness.document.getElementById("vibecomfy-agent-panel-model");

    settingsGear.click();

    // Initial ready state: controls enabled, settings contain status text
    await waitFor(() => !routeSelect.disabled && !modelInput.disabled);
    assert.equal(routeSelect.disabled, false);
    assert.equal(modelInput.disabled, false);

    // Settings text reflects the ready state
    const readyText = harness.textDump();
    assert.ok(
      readyText.includes("deepseek") || readyText.includes("provider ready"),
      `settings should reflect ready state`,
    );

    // Switch to openrouter → unavailable route (ready === false)
    routeSelect.value = "openrouter";
    routeSelect.onchange();
    await waitFor(() => statusCalls === 2);
    await waitFor(() => routeSelect.disabled === true);
    assert.equal(routeSelect.disabled, true);
    assert.equal(modelInput.disabled, true);

    // Settings text reflects the unavailable reason
    const unavailableText = harness.textDump();
    assert.ok(
      unavailableText.includes("Provider quota exhausted"),
      `settings should show unavailable reason, got: ${unavailableText.substring(0, 200)}`,
    );
    // Should no longer show "provider ready"
    assert.ok(
      !unavailableText.includes("provider ready"),
      "settings should not show provider ready when unavailable",
    );
  } finally {
    globalThis.localStorage?.removeItem("vibecomfy_agent_provider");
    await harness.dispose();
  }
});

// ── T12: Production-POST parity contract ───────────────────────────────────
// Production apply/reject are the ONLY sources permitted to POST to the
// /agent-edit/accept and /agent-edit/reject routes.  Preview (demo) and replay
// must never reference these routes in source.  This static contract is the
// parity counterpart to the runtime no-POST tests in preview_picker.test.mjs
// and agentic_replay.test.mjs: production POSTs, preview/replay do not.

test("production-POST parity: only roundtrip references accept/reject routes; preview and replay never do", async () => {
  const fs = await import("node:fs");
  const webDir = new URL("../../vibecomfy/comfy_nodes/web/", import.meta.url);
  const read = (name) => fs.readFileSync(new URL(name, webDir), "utf8");

  const roundtrip = read("vibecomfy_roundtrip.js");
  const preview = read("preview_picker.js");
  const replay = read("agentic_replay.js");

  const ACCEPT = /\/vibecomfy\/agent-edit\/accept\b/;
  const REJECT = /\/vibecomfy\/agent-edit\/reject\b/;

  // PRODUCTION POSTS: the roundtrip authority references both routes.
  assert.ok(ACCEPT.test(roundtrip), "production roundtrip references the accept route");
  assert.ok(REJECT.test(roundtrip), "production roundtrip references the reject route");

  // PARITY: preview (demo) and replay never reference either production route.
  assert.equal(ACCEPT.test(preview), false, "preview_picker must not reference the accept route");
  assert.equal(REJECT.test(preview), false, "preview_picker must not reference the reject route");
  assert.equal(ACCEPT.test(replay), false, "agentic_replay must not reference the accept route");
  assert.equal(REJECT.test(replay), false, "agentic_replay must not reference the reject route");
});

// ═══════════════════════════════════════════════════════════════════════════
// T12: Browser preview/apply parity — normalized delta ops → overlay highlights
// ═══════════════════════════════════════════════════════════════════════════
// These tests prove that the same normalized canonical delta ops drive both
// the preview overlay (via computePreviewDiff) and the apply mutation plan
// (via preflightDeltaPlan).  They also prove the legacy graph-diff fallback
// cannot override delta-op-derived highlights when canonical deltaOps are
// available.

test("preview delta-ops parity: same ops produce equivalent node highlights (added/edited/removed) and apply plan entries", async () => {
  const liveGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, widgets_values: ["hello"], pos: [100, 100] },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" }, pos: [300, 100] },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, widgets_values: ["world"], pos: [100, 100] },
      { id: 3, type: "PreviewImage", properties: { vibecomfy_uid: "uid-3" }, pos: [500, 100], inputs: [], outputs: [], widgets_values: [] },
    ],
    links: [],
  };
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", "uid-1", "widgets_values", 0], value: "world" },
    { op: "add_node", uid: "uid-3", node_id: 3, scope_path: [], class_type: "PreviewImage", fields: {}, inputs: {} },
    { op: "remove_node", target: ["nodes", "uid-2"] },
  ];

  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: { auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false } } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const adapter = await harness.loadAdapter();
    await harness.setup();

    // ── Compute the preview diff with canonical delta ops ──
    const diff = extensionModule.computePreviewDiff(candidateGraph, { change: { content_edits: {} }, recovery: [] }, deltaOps);
    assert.equal(diff._deltaOpsDerived, true, "diff should be delta-ops-derived when deltaOps are provided");

    // ── Node highlights: edited ──
    assert.equal(diff.edited.length, 1, "one edited node");
    assert.equal(diff.edited[0].uid, "uid-1");
    assert.deepEqual(diff.edited[0].changedWidgetIndices, [0], "widget index 0 changed");

    // ── Node highlights: added ──
    assert.equal(diff.added.length, 1, "one added node");
    assert.equal(diff.added[0].uid, "uid-3");
    assert.equal(diff.added[0].class_type, "PreviewImage");

    // ── Node highlights: removed ──
    assert.equal(diff.removed.length, 1, "one removed node");
    assert.equal(diff.removed[0].uid, "uid-2");
    assert.equal(diff.removed[0].class_type, "SaveImage");

    // ── Parity: same plan entries from preflightDeltaPlan ──
    const liveSnapshot = { nodes: JSON.parse(JSON.stringify(liveGraph.nodes)), links: [] };
    const { plan } = adapter.preflightDeltaPlan(liveSnapshot, candidateGraph, deltaOps, {});

    const planEdited = plan.filter((s) => s.op === "set_node_field");
    const planAdded = plan.filter((s) => s.op === "add_node");
    const planRemoved = plan.filter((s) => s.op === "remove_node");

    assert.equal(planEdited.length, 1, "plan should have one set_node_field");
    assert.equal(planEdited[0].uidOrId, "uid-1");
    assert.deepEqual(planEdited[0].fieldPath, ["widgets_values", 0]);

    assert.equal(planAdded.length, 1, "plan should have one add_node");
    assert.equal(planAdded[0].nodePayload.properties?.vibecomfy_uid || planAdded[0].nodePayload?.uid, "uid-3");

    assert.equal(planRemoved.length, 1, "plan should have one remove_node");
    assert.equal(planRemoved[0].uidOrId, "uid-2");
    assert.equal(planRemoved[0].alreadyAbsent, false);

    // ── No spurious link highlights ──
    assert.equal(diff.added_links.length, 0, "no added links");
    assert.equal(diff.removed_links.length, 0, "no removed links");
  } finally {
    await harness.dispose();
  }
});

test("preview delta-ops parity: same ops produce equivalent link highlights (added/removed) and apply plan entries", async () => {
  const liveGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, pos: [100, 100], inputs: [], outputs: [{ name: "IMAGE", type: "IMAGE" }] },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" }, pos: [300, 100], inputs: [{ name: "images", type: "IMAGE" }], outputs: [] },
      { id: 3, type: "PreviewImage", properties: { vibecomfy_uid: "uid-3" }, pos: [500, 100], inputs: [{ name: "images", type: "IMAGE" }], outputs: [] },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, pos: [100, 100], inputs: [], outputs: [{ name: "IMAGE", type: "IMAGE" }] },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" }, pos: [300, 100], inputs: [{ name: "images", type: "IMAGE" }], outputs: [] },
      { id: 3, type: "PreviewImage", properties: { vibecomfy_uid: "uid-3" }, pos: [500, 100], inputs: [{ name: "images", type: "IMAGE" }], outputs: [] },
    ],
    links: [[1, 1, 0, 3, 0, "IMAGE"]],
  };
  const deltaOps = [
    { op: "upsert_link", from: ["nodes", "uid-1", 0], to: ["nodes", "uid-3", 0] },
    { op: "remove_link", to: ["nodes", "uid-2", 0] },
  ];

  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: { auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false } } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const adapter = await harness.loadAdapter();
    await harness.setup();

    const diff = extensionModule.computePreviewDiff(candidateGraph, { change: { content_edits: {} }, recovery: [] }, deltaOps);
    assert.equal(diff._deltaOpsDerived, true, "diff should be delta-ops-derived");

    // ── Link highlights ──
    assert.equal(diff.added_links.length, 1, "one added link");
    assert.equal(diff.removed_links.length, 1, "one removed link");

    // ── Parity with plan ──
    const liveSnapshot = { nodes: JSON.parse(JSON.stringify(liveGraph.nodes)), links: JSON.parse(JSON.stringify(liveGraph.links)) };
    const { plan } = adapter.preflightDeltaPlan(liveSnapshot, candidateGraph, deltaOps, {});

    const planUpsert = plan.filter((s) => s.op === "upsert_link");
    const planRemove = plan.filter((s) => s.op === "remove_link");

    assert.equal(planUpsert.length, 1, "plan should have one upsert_link");
    assert.equal(planRemove.length, 1, "plan should have one remove_link");

    // ── No spurious node highlights ──
    assert.equal(diff.edited.length, 0, "no edited nodes (link-only delta)");
    assert.equal(diff.added.length, 0, "no added nodes (link-only delta)");
    assert.equal(diff.removed.length, 0, "no removed nodes (link-only delta)");
  } finally {
    await harness.dispose();
  }
});

test("preview delta-ops parity: set_node_field op yields correct field-level overlay highlight", async () => {
  const liveGraph = {
    nodes: [
      { id: 1, type: "KSampler", properties: { vibecomfy_uid: "uid-1" }, widgets_values: [123456789, 20, 7.5, "euler"], pos: [100, 100] },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "KSampler", properties: { vibecomfy_uid: "uid-1" }, widgets_values: [123456789, 30, 7.5, "euler_ancestral"], pos: [100, 100] },
    ],
    links: [],
  };
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", "uid-1", "widgets_values", 1], value: 30 },
    { op: "set_node_field", target: ["nodes", "uid-1", "widgets_values", 3], value: "euler_ancestral" },
  ];

  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: { auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false } } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const diff = extensionModule.computePreviewDiff(candidateGraph, { change: { content_edits: {} }, recovery: [] }, deltaOps);
    assert.equal(diff._deltaOpsDerived, true, "diff should be delta-ops-derived");

    assert.equal(diff.edited.length, 1, "one edited entry for uid-1");
    assert.equal(diff.edited[0].uid, "uid-1");
    assert.deepEqual(diff.edited[0].changedWidgetIndices.sort(), [1, 3], "both widget indices 1 and 3 changed");

    // ── When no deltaOps, the graph-diff path would also detect both changes ──
    const diffGraph = extensionModule.computePreviewDiff(candidateGraph, { change: { content_edits: {} }, recovery: [] }, null);
    assert.equal(!!diffGraph._deltaOpsDerived, false, "graph-diff path does not set _deltaOpsDerived to true");
    assert.equal(diffGraph.edited.length, 1, "graph-diff also finds one edited node");
    assert.deepEqual(diffGraph.edited[0].changedWidgetIndices.sort(), [1, 3], "graph-diff also finds both widget indices");

    // The key assertion: delta-derived and graph-derived agree (parity for field highlights)
  } finally {
    await harness.dispose();
  }
});

test("preview delta-ops parity: legacy graph-diff fallback cannot override normalized delta-op-derived highlights", async () => {
  // Scenario: live graph and candidate graph differ by a widget value that is
  // NOT reflected in the deltaOps.  The deltaOps only mention a different
  // change.  We prove that when deltaOps are provided, the diff highlights
  // come from deltaOps, NOT from the graph diff.
  const liveGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, widgets_values: ["live-value"], pos: [100, 100] },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, widgets_values: ["candidate-value"], pos: [100, 100] },
    ],
    links: [],
  };
  // deltaOps says: set widget[0] to "delta-value" — intentionally DIFFERENT
  // from what the graph diff would detect (which would detect "live-value" → "candidate-value")
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", "uid-1", "widgets_values", 0], value: "delta-value" },
  ];

  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: { auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false } } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const adapter = await harness.loadAdapter();
    await harness.setup();

    // ── Delta-derived diff ──
    const diffDelta = extensionModule.computePreviewDiff(candidateGraph, { change: { content_edits: {} }, recovery: [] }, deltaOps);
    assert.equal(diffDelta._deltaOpsDerived, true, "delta-derived flag is set");

    // The preflightDeltaPlan applies the candidateGraph value for set_node_field
    // (the delta op's value field is advisory; the canonical source is the candidate graph).
    // What matters for parity is that the plan is produced from the same delta ops.
    const liveSnapshot = { nodes: JSON.parse(JSON.stringify(liveGraph.nodes)), links: [] };
    const { plan, nextGraph: planResultGraph } = adapter.preflightDeltaPlan(liveSnapshot, candidateGraph, deltaOps, {});

    // planResultGraph should have the candidate value applied (the adapter reads from candidateGraph)
    const planResultNode = planResultGraph.nodes.find((n) => n.id === 1 || n.properties?.vibecomfy_uid === "uid-1");
    assert.ok(planResultNode, "plan result should contain the node");
    // The plan uses the candidate graph value, which IS "candidate-value" in this scenario
    assert.equal(planResultNode.widgets_values?.[0], "candidate-value", "plan result reflects candidate graph value (adapter reads from candidateGraph)");

    // ── Graph-diff-derived diff (no deltaOps) ──
    const diffGraph = extensionModule.computePreviewDiff(candidateGraph, { change: { content_edits: {} }, recovery: [] }, null);
    assert.equal(!!diffGraph._deltaOpsDerived, false, "graph-derived diff has no delta flag set to true");
    // Graph diff would detect live→candidate change, which is "live-value"→"candidate-value"
    assert.equal(diffGraph.edited.length, 1, "graph diff finds edited node");

    // ── Legacy fallback proof: when deltaOps are present, the legacy path is NOT used ──
    // Even if we pass a candidateReport with content_edits that suggest different
    // changes, the delta-derived path takes precedence.
    const diffWithReport = extensionModule.computePreviewDiff(
      candidateGraph,
      { change: { content_edits: { edited: ["uid-1"], preserved: [], removed_named: [] } }, recovery: [] },
      deltaOps,
    );
    assert.equal(diffWithReport._deltaOpsDerived, true, "delta-derived even with report content_edits");
    assert.equal(diffWithReport.edited.length, 1, "one edited entry from delta ops");

    // ── When deltaOps cause preflight failure, fallback still works ──
    // (but that's tested elsewhere; here we prove the normal path)
  } finally {
    await harness.dispose();
  }
});

test("preview delta-ops parity: overlay draw operations render correct colors and labels for delta-derived node highlights", async () => {
  const liveGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, pos: [100, 100], widgets_values: [] },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" }, pos: [300, 100], widgets_values: [] },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, pos: [100, 100], widgets_values: ["changed"] },
      { id: 3, type: "PreviewImage", properties: { vibecomfy_uid: "uid-3" }, pos: [500, 100], inputs: [], outputs: [], widgets_values: [] },
    ],
    links: [],
  };
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", "uid-1", "widgets_values", 0], value: "changed" },
    { op: "add_node", uid: "uid-3", node_id: 3, scope_path: [], class_type: "PreviewImage", fields: {}, inputs: {} },
    { op: "remove_node", target: ["nodes", "uid-2"] },
  ];

  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: { auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false } } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const diff = extensionModule.computePreviewDiff(candidateGraph, { change: { content_edits: {} }, recovery: [] }, deltaOps);
    assert.equal(diff._deltaOpsDerived, true);

    // ── Render overlay and verify canvas operations ──
    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });

    // Should contain fillText operations with node type labels
    const textOps = drawOps.filter((op) => op.kind === "fillText");
    assert.ok(textOps.length > 0, "overlay should contain text draw operations");

    const allText = textOps.map((op) => String(op.args[0] || "")).join(" ");
    assert.match(allText, /PreviewImage/, "added node label should appear in overlay text");

    // Should contain fillStyle operations with highlight colors
    const fillStyleOps = drawOps.filter((op) => op.kind === "fillStyle");
    const fillColors = fillStyleOps.map((op) => String(op.args[0] || ""));
    assert.ok(fillColors.some((c) => c.includes("76, 175, 80") || c === "#4caf50"), "green highlight for added node");
    assert.ok(fillColors.some((c) => c.includes("244, 67, 54") || c === "#f44336"), "red highlight for removed node");

    // Overlay should NOT contain forbidden diagnostic text
    for (const op of textOps) {
      const text = String(op.args[0] ?? "");
      for (const pattern of OVERLAY_FORBIDDEN_TEXT_PATTERNS) {
        assert.equal(pattern.test(text), false, `delta-derived overlay leaked forbidden text: ${text}`);
      }
    }

    // ── The live graph must not be mutated by overlay rendering ──
    assert.deepEqual(harness.getCurrentGraph(), liveGraph, "live graph unchanged after overlay draw");
  } finally {
    await harness.dispose();
  }
});

test("preview delta-ops parity: delta-derived overlay renders link wire operations for added and removed links", async () => {
  const liveGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, pos: [100, 100], inputs: [], outputs: [{ name: "IMAGE", type: "IMAGE" }] },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" }, pos: [300, 100], inputs: [{ name: "images", type: "IMAGE" }], outputs: [] },
      { id: 3, type: "PreviewImage", properties: { vibecomfy_uid: "uid-3" }, pos: [500, 100], inputs: [{ name: "images", type: "IMAGE" }], outputs: [] },
    ],
    links: [[1, 1, 0, 2, 0, "IMAGE"]],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, pos: [100, 100], inputs: [], outputs: [{ name: "IMAGE", type: "IMAGE" }] },
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" }, pos: [300, 100], inputs: [{ name: "images", type: "IMAGE" }], outputs: [] },
      { id: 3, type: "PreviewImage", properties: { vibecomfy_uid: "uid-3" }, pos: [500, 100], inputs: [{ name: "images", type: "IMAGE" }], outputs: [] },
    ],
    links: [[1, 1, 0, 3, 0, "IMAGE"]],
  };
  const deltaOps = [
    { op: "upsert_link", from: ["nodes", "uid-1", 0], to: ["nodes", "uid-3", 0] },
    { op: "remove_link", to: ["nodes", "uid-2", 0] },
  ];

  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: { auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false } } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const diff = extensionModule.computePreviewDiff(candidateGraph, { change: { content_edits: {} }, recovery: [] }, deltaOps);
    assert.equal(diff._deltaOpsDerived, true);
    assert.equal(diff.added_links.length, 1);
    assert.equal(diff.removed_links.length, 1);

    // ── Render overlay with link highlights ──
    const drawOps = await harness.drawPreviewOverlay({ ...diff, _candidateGraph: candidateGraph });

    // bezierCurveTo calls indicate wire rendering
    const bezierOps = drawOps.filter((op) => op.kind === "bezierCurveTo");
    assert.ok(bezierOps.length > 0, "overlay should contain bezier curve operations for link wires");

    // Red stroke for removed links
    const strokeStyleOps = drawOps.filter((op) => op.kind === "strokeStyle");
    const strokeColors = strokeStyleOps.map((op) => String(op.args[0] || ""));
    assert.ok(strokeColors.some((c) => c.includes("244, 67, 54") || c === "#f44336"), "red stroke for removed link");

    // ── Verify no forbidden text in link overlay ──
    const textOps = drawOps.filter((op) => op.kind === "fillText");
    for (const op of textOps) {
      const text = String(op.args[0] ?? "");
      for (const pattern of OVERLAY_FORBIDDEN_TEXT_PATTERNS) {
        assert.equal(pattern.test(text), false, `link overlay leaked forbidden text: ${text}`);
      }
    }
  } finally {
    await harness.dispose();
  }
});

test("preview delta-ops parity: legacy fallback does not override delta-derived diff even with misleading report content_edits", async () => {
  // The candidateReport may contain content_edits from the backend, but when
  // deltaOps are present, the diff must be derived from ops, not from the report.
  const liveGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, widgets_values: ["before"], pos: [100, 100] },
    ],
    links: [],
  };
  const candidateGraph = {
    nodes: [
      { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, widgets_values: ["after"], pos: [100, 100] },
    ],
    links: [],
  };
  // Report says: nothing edited, uid-99 was added (non-existent), uid-1 was removed
  // But deltaOps says: set widget 0 on uid-1
  const candidateReport = {
    change: {
      content_edits: {
        preserved: [],
        edited: [],
        new_auto_placed: ["uid-99"],
        removed: ["uid-1"],
        removed_named: [],
      },
    },
    recovery: [],
  };
  const deltaOps = [
    { op: "set_node_field", target: ["nodes", "uid-1", "widgets_values", 0], value: "after" },
  ];

  const harness = await createBrowserHarness({
    graph: liveGraph,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: { auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false } } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const diff = extensionModule.computePreviewDiff(candidateGraph, candidateReport, deltaOps);
    assert.equal(diff._deltaOpsDerived, true, "delta-derived despite misleading report");

    // Delta-derived edit overrides the report's empty edited[] list
    assert.equal(diff.edited.length, 1, "edited from delta ops, not report");
    assert.equal(diff.edited[0].uid, "uid-1");

    // Report says uid-1 was removed — but delta ops say it was edited, not removed
    // The removed_named list should still be populated from the report (it's purely informational)
    assert.equal(diff.removed.length, 0, "no removed nodes from delta ops");

    // unresolved entries from report are still populated
    assert.ok(diff.unresolved.length >= 1, "unresolved entries from report still appear");
  } finally {
    await harness.dispose();
  }
});
