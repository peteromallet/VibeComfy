// BROWSER/UI E2E TESTS.
//
import { readFile } from "node:fs/promises";
import { test, expect } from "@playwright/test";
import {
  installFailureCapture,
  collectUnhandledPageErrors,
  waitForLauncher,
  openPanelViaLauncher,
  waitForPanelFlush,
  probePanelDebug,
} from "../helpers/index.mjs";

const OPEN_TIMEOUT = { timeout: 30_000 };
const REORGANISE_PROMPT = "/reorganise_comfy_workflow";
const FUNCTIONAL_EDIT_PROMPT = "Change the prompt to a brighter cabin scene.";

const BASE_GRAPH = JSON.parse(
  await readFile(
    new URL("../../fixtures/reorganise/simple_text_to_image.json", import.meta.url),
    "utf8",
  ),
);

const READY_STATUS = {
  ok: true,
  ready: true,
  provider_available: true,
  route: "deepseek",
  requested_route: "auto",
  route_options: {
    auto: {
      requested_route: "auto",
      normalized_route: "deepseek",
      browser_api_key_allowed: false,
    },
    deepseek: {
      requested_route: "deepseek",
      normalized_route: "deepseek",
      browser_api_key_allowed: true,
    },
  },
};

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function layoutCandidateGraph() {
  const graph = cloneJson(BASE_GRAPH);
  graph.nodes = graph.nodes.map((node, index) => ({
    ...node,
    pos: [
      640 + (index % 3) * 460,
      120 + Math.floor(index / 3) * 260,
    ],
  }));
  return graph;
}

function functionalCandidateGraph() {
  const graph = cloneJson(BASE_GRAPH);
  graph.nodes = graph.nodes.map((node) => {
    if (node?.properties?.vibecomfy_uid !== "prompt") {
      return node;
    }
    return {
      ...node,
      widgets_values: ["a bright cabin scene with crisp morning light"],
    };
  });
  return graph;
}

function candidateResponse({
  sessionId,
  turnId,
  route,
  message,
  candidateGraph,
  candidateGraphHash,
  layoutReorganisation = null,
}) {
  const response = {
    ok: true,
    route,
    session_id: sessionId,
    turn_id: turnId,
    baseline_turn_id: "0000",
    message,
    reply: message,
    outcome: {
      kind: "candidate",
      changes: [],
    },
    candidate: {
      state: "candidate",
      graph: candidateGraph,
      graph_hash: candidateGraphHash,
      turn_identity: {
        session_id: sessionId,
        turn_id: turnId,
        baseline_turn_id: "0000",
      },
    },
    candidate_graph: candidateGraph,
    candidate_graph_hash: candidateGraphHash,
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      message: "Ready to apply.",
      warnings: [],
    },
    apply_eligible: true,
    apply_allowed: true,
    canvas_apply_allowed: true,
    queue_allowed: true,
    change_details: {},
    audit_ref: { audit_path: `turns/${turnId}/audit.json` },
  };
  if (layoutReorganisation) {
    response.layout_reorganisation = layoutReorganisation;
    response.change_details.layout_reorganisation = layoutReorganisation;
  }
  return response;
}

function acceptResponse(sessionId, turnId) {
  return {
    ok: true,
    action: "accept",
    session_id: sessionId,
    turn_id: turnId,
    baseline_turn_id: turnId,
    baseline_graph_hash: `baseline-after-${turnId}`,
    baseline_graph_hash_kind: "structural",
    baseline_graph_hash_version: 1,
    baseline_source: "candidate",
    baseline_graph_source_path: `turns/${turnId}/candidate.ui.json`,
    audit_ref: { audit_path: `turns/${turnId}/accept.audit.json` },
    message: "Candidate accepted.",
  };
}

async function installReadyStatusRoute(page) {
  await page.route("**/vibecomfy/agent/status**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(READY_STATUS),
    });
  });
}

async function navigateToComfyUI(page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("canvas#graph-canvas", { timeout: 60_000 });
  await page.waitForTimeout(1_000);
}

async function dismissTemplatesDialog(page) {
  const dialog = page.getByRole("dialog");
  if (await dialog.count()) {
    await page.keyboard.press("Escape").catch(() => {});
    const closeDialog = page.getByRole("button", { name: "Close dialog" });
    if (await closeDialog.isVisible().catch(() => false)) {
      await closeDialog.click({ force: true }).catch(() => {});
    }
    await dialog.first().waitFor({ state: "hidden", timeout: 5_000 }).catch(() => {});
  }
}

async function loadFixtureGraph(page, graph = BASE_GRAPH) {
  await page.evaluate((graphPayload) => {
    const graph = window.app?.canvas?.graph;
    if (!graph) {
      throw new Error("LiteGraph instance is unavailable.");
    }
    if (typeof graph.clear === "function") {
      graph.clear();
    }
    if (typeof graph.configure !== "function") {
      throw new Error("LiteGraph graph.configure() is unavailable.");
    }
    graph.configure(graphPayload);
    if (typeof graph.setDirtyCanvas === "function") {
      graph.setDirtyCanvas(true, true);
    }
    if (typeof window.app?.graph?.setDirtyCanvas === "function") {
      window.app.graph.setDirtyCanvas(true, true);
    }
  }, graph);
}

async function readNodePositions(page) {
  return page.evaluate(() => {
    const graph = window.app?.canvas?.graph;
    const nodes = Array.isArray(graph?._nodes)
      ? graph._nodes
      : Array.isArray(graph?.nodes)
        ? graph.nodes
        : [];
    return Object.fromEntries(nodes.map((node) => [
      String(node?.properties?.vibecomfy_uid || node?.id),
      Array.isArray(node?.pos) ? [Number(node.pos[0]), Number(node.pos[1])] : null,
    ]));
  });
}

async function readPanelState(page) {
  return page.evaluate(() => {
    const panel = window.__vibecomfyAgentPanelSingleton?.runtime?.agentPanel;
    const state = panel?.state || {};
    return {
      phase: state.phase || null,
      sessionId: state.sessionId || null,
      turnId: state.turnId || null,
      candidateGraphHash: state.candidateGraphHash || null,
      candidateNodeCount: Array.isArray(state.candidateGraph?.nodes)
        ? state.candidateGraph.nodes.length
        : 0,
      applyEligibility: state.applyEligibility || null,
      changeDetails: state.changeDetails || null,
      candidatePositions: Object.fromEntries(
        (Array.isArray(state.candidateGraph?.nodes) ? state.candidateGraph.nodes : []).map((node) => [
          String(node?.properties?.vibecomfy_uid || node?.id),
          Array.isArray(node?.pos) ? [Number(node.pos[0]), Number(node.pos[1])] : null,
        ]),
      ),
    };
  });
}

async function submitPrompt(page, prompt) {
  const composer = page.getByRole("textbox", { name: "Describe the workflow change..." });
  const submitButton = page.getByRole("button", { name: "Submit", exact: true });
  await composer.fill(prompt, { force: true });
  await Promise.all([
    page.waitForFunction(
      () => {
        const debug = typeof window.__vibecomfyPanelDebug === "function"
          ? window.__vibecomfyPanelDebug()
          : null;
        return debug && debug.phase === "SUBMITTING";
      },
      null,
      { timeout: 30_000 },
    ),
    submitButton.click({ force: true }),
  ]);
  await page.waitForFunction(
    () => {
      const debug = typeof window.__vibecomfyPanelDebug === "function"
        ? window.__vibecomfyPanelDebug()
        : null;
      return debug && debug.phase === "AWAITING_REVIEW" && !!debug.turnId;
    },
    null,
    { timeout: 30_000 },
  );
  await waitForPanelFlush(page, { timeout: 30_000 });
}

async function expandLastAgentBubble(page) {
  const lastAgentBubble = page.locator('[data-vibecomfy-message-key]:has(span:text-is("VibeComfy"))').last();
  await expect(lastAgentBubble).toBeVisible();
  await lastAgentBubble.locator("span", { hasText: "details" }).click();
  return lastAgentBubble;
}

async function openReadyPanelWithFixture(page) {
  await installReadyStatusRoute(page);
  await navigateToComfyUI(page);
  await waitForLauncher(page, OPEN_TIMEOUT);
  await openPanelViaLauncher(page, OPEN_TIMEOUT);
  await waitForPanelFlush(page, { timeout: 30_000 });
  await page.waitForFunction(
    () => {
      const debug = typeof window.__vibecomfyPanelDebug === "function"
        ? window.__vibecomfyPanelDebug()
        : null;
      return debug && debug.readiness?.ready === true && debug.flushPending === false;
    },
    null,
    { timeout: 30_000 },
  );
  await dismissTemplatesDialog(page);
  await loadFixtureGraph(page);
}

async function assertCleanBrowser(page, capture, { allowComfyWarnings = true } = {}) {
  const unhandled = await collectUnhandledPageErrors(page);
  const meaningfulConsole = capture.consoleErrors.filter((entry) => {
    if (!allowComfyWarnings && entry.type === "warning") return true;
    const text = entry.text || "";
    if (text.includes("ComfyUI") && entry.type === "warning") return false;
    if (text.includes("DevTools")) return false;
    if (text.includes("[DOM]")) return false;
    if (text.includes("Automatic1111")) return false;
    if (text.includes("No resource with given URL")) return false;
    if (text.includes("Failed to load resource: the server responded with a status of 404")) return false;
    if (text.includes("ComfyApp graph accessed before initialization")) return false;
    if (text.includes("[MaskEditor] ComfyApp.open_maskeditor is deprecated")) return false;
    if (text.includes("VibeComfy: frontend version unknown outside supported range")) return false;
    if (/^\s*$/.test(text)) return false;
    return true;
  });
  const meaningfulRequests = capture.failedRequests.filter((entry) => {
    if (entry.url && entry.url.includes("/ws")) return false;
    if (entry.url && entry.url.includes("favicon")) return false;
    if (entry.url && entry.url.includes("/api/userdata/user.css")) return false;
    if (entry.url && /\/user\.css$/.test(entry.url)) return false;
    if (entry.url && entry.url.includes("/api/userdata?dir=workflows")) return false;
    if (entry.url && entry.url.includes("/api/userdata?dir=subgraphs")) return false;
    if (entry.url && entry.url.includes("/api/userdata/comfy.templates.json")) return false;
    if (entry.status === 0 && (entry.statusText || "").includes("ERR_ABORTED")) return false;
    return true;
  });

  const issues = [];
  if (meaningfulConsole.length > 0) {
    issues.push(
      `${meaningfulConsole.length} console issue(s):\n`
      + meaningfulConsole.map((entry) => `  [${entry.type}] ${entry.text}`).join("\n"),
    );
  }
  if (meaningfulRequests.length > 0) {
    issues.push(
      `${meaningfulRequests.length} failed request(s):\n`
      + meaningfulRequests.map((entry) => `  ${entry.status} ${entry.statusText} ${entry.url}`).join("\n"),
    );
  }
  if (capture.pageErrors.length > 0) {
    issues.push(
      `${capture.pageErrors.length} page error(s):\n`
      + capture.pageErrors.map((entry) => `  ${entry.message}`).join("\n"),
    );
  }
  if (unhandled.length > 0) {
    issues.push(
      `${unhandled.length} unhandled page error(s):\n`
      + unhandled.map((entry) => `  ${entry.message}`).join("\n"),
    );
  }
  if (issues.length > 0) {
    throw new Error(`Browser failure surface not clean:\n${issues.join("\n\n")}`);
  }
}

test.describe("Agent Panel Reorganise", () => {
  let capture;

  test.beforeEach(async ({ page }) => {
    capture = installFailureCapture(page);
  });

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== "skipped") {
      await assertCleanBrowser(page, capture);
    }
  });

  test("explicit reorganise returns an applyable layout candidate and Apply changes live node positions", async ({ page }) => {
    const sessionId = "e2e-reorganise-explicit";
    const turnId = "0001";
    const candidateGraph = layoutCandidateGraph();
    const response = candidateResponse({
      sessionId,
      turnId,
      route: "reorganise",
      message: "Prepared a layout-only reorganise candidate.",
      candidateGraph,
      candidateGraphHash: "layout-candidate-hash-e2e",
      layoutReorganisation: {
        result: "prepare_candidate",
        candidate_prepared: true,
        suggested_command: REORGANISE_PROMPT,
        functional_candidate_graph_hash: null,
        reorganised_candidate_graph_hash: "layout-candidate-hash-e2e",
        evidence: { layout_only_structural_noop: true },
      },
    });

    await page.route("**/vibecomfy/agent-executor", async (route, request) => {
      const body = request.method() === "POST" ? await request.postDataJSON() : {};
      expect(body.task).toBe(REORGANISE_PROMPT);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(response),
      });
    });
    await page.route("**/vibecomfy/agent-edit/accept", async (route, request) => {
      const body = request.method() === "POST" ? await request.postDataJSON() : {};
      expect(body.session_id).toBe(sessionId);
      expect(body.turn_id).toBe(turnId);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(acceptResponse(sessionId, turnId)),
      });
    });

    await openReadyPanelWithFixture(page);
    const beforePositions = await readNodePositions(page);
    await submitPrompt(page, REORGANISE_PROMPT);

    const state = await readPanelState(page);
    expect(state.phase).toBe("AWAITING_REVIEW");
    expect(state.candidateGraphHash).toBe("layout-candidate-hash-e2e");
    expect(state.applyEligibility).toMatchObject({
      applyable: true,
      reason: "applyable",
    });
    expect(state.changeDetails?.layout_reorganisation).toMatchObject({
      result: "prepare_candidate",
      candidate_prepared: true,
    });

    const lastAgentBubble = await expandLastAgentBubble(page);
    await expect(lastAgentBubble).toContainText("layout-only reorganise candidate");
    const applyAction = lastAgentBubble.locator('[data-vibecomfy-candidate-action="apply"]');
    await expect(applyAction).toBeVisible();
    await expect(applyAction).toBeEnabled();

    await applyAction.click();
    await page.waitForFunction(
      () => {
        const debug = typeof window.__vibecomfyPanelDebug === "function"
          ? window.__vibecomfyPanelDebug()
          : null;
        return debug && debug.phase === "IDLE" && debug.flushPending === false;
      },
      null,
      { timeout: 30_000 },
    );
    await waitForPanelFlush(page, { timeout: 30_000 });

    const afterPositions = await readNodePositions(page);
    expect(afterPositions.checkpoint).toEqual(candidateGraph.nodes[0].pos);
    expect(afterPositions.checkpoint).not.toEqual(beforePositions.checkpoint);

    const debug = await probePanelDebug(page);
    expect(debug?.phase).toBe("IDLE");
  });

  test("main-flow functional edit surfaces suggestion-only reorganise advice without replacing the functional candidate", async ({ page }) => {
    const sessionId = "e2e-reorganise-suggest";
    const turnId = "0002";
    const candidateGraph = functionalCandidateGraph();
    const response = candidateResponse({
      sessionId,
      turnId,
      route: "revise",
      message: `Updated the prompt. The canvas may be easier to review after ${REORGANISE_PROMPT}.`,
      candidateGraph,
      candidateGraphHash: "functional-candidate-hash-e2e",
      layoutReorganisation: {
        result: "offer_reorganisation",
        candidate_prepared: false,
        suggested_command: REORGANISE_PROMPT,
        functional_candidate_graph_hash: "functional-candidate-hash-e2e",
        evidence: {
          layout_only_structural_noop: true,
          reason_codes: ["branch_edit_layout_pressure"],
        },
      },
    });

    await page.route("**/vibecomfy/agent-executor", async (route, request) => {
      const body = request.method() === "POST" ? await request.postDataJSON() : {};
      expect(body.task).toBe(FUNCTIONAL_EDIT_PROMPT);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(response),
      });
    });

    await openReadyPanelWithFixture(page);
    const livePositionsBefore = await readNodePositions(page);
    await submitPrompt(page, FUNCTIONAL_EDIT_PROMPT);

    const state = await readPanelState(page);
    expect(state.phase).toBe("AWAITING_REVIEW");
    expect(state.candidateGraphHash).toBe("functional-candidate-hash-e2e");
    expect(state.candidateNodeCount).toBe(BASE_GRAPH.nodes.length);
    expect(state.changeDetails?.layout_reorganisation).toMatchObject({
      result: "offer_reorganisation",
      candidate_prepared: false,
      functional_candidate_graph_hash: "functional-candidate-hash-e2e",
      suggested_command: REORGANISE_PROMPT,
    });
    expect(state.changeDetails?.layout_reorganisation?.reorganised_candidate_graph_hash).toBeUndefined();
    expect(state.candidatePositions).toEqual(livePositionsBefore);

    const lastAgentBubble = await expandLastAgentBubble(page);
    await expect(lastAgentBubble).toContainText(REORGANISE_PROMPT);
    const applyAction = lastAgentBubble.locator('[data-vibecomfy-candidate-action="apply"]');
    await expect(applyAction).toBeVisible();
    await expect(applyAction).toBeEnabled();

    const livePositionsAfter = await readNodePositions(page);
    expect(livePositionsAfter).toEqual(livePositionsBefore);
  });
});
