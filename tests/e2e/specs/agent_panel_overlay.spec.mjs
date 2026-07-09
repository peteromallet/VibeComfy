// BROWSER/UI E2E TESTS.
//
// ── agent_panel_overlay.spec.mjs ─────────────────────────────────────────────
// Playwright overlay regression coverage using Canvas2D draw-call recording.
//
// Covers:
//   - Overlay preview installs after submit + AWAITING_REVIEW.
//   - Widget-value overlay text is drawn inside the expected widget/node bounds.
//   - Overlay panel/text stays away from the canvas origin and inside the
//     visible preview surface.
//   - A newer submit replaces the preview state and removes stale overlay text.
//   - Zero unexpected console / page / request errors.

import { readFile } from "node:fs/promises";
import { test, expect } from "@playwright/test";
import {
  installFailureCapture,
  collectUnhandledPageErrors,
  waitForLauncher,
  openPanelViaLauncher,
  waitForPanelFlush,
  probePanelDebug,
  probeOverlayState,
  installCanvas2DRecorder,
  clearCanvas2DRecorder,
  readCanvas2DRecorder,
} from "../helpers/index.mjs";

const OPEN_TIMEOUT = { timeout: 30_000 };
const FIRST_SUBMIT_PROMPT = "Raise the KSampler cfg value to the first overlay sentinel.";
const SECOND_SUBMIT_PROMPT = "Replace the preview with the second overlay sentinel cfg value.";
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
const TARGET_NODE_UID = "sample";
const TARGET_WIDGET_INDEX = 3;
const FIRST_WIDGET_VALUE = 17.25;
const SECOND_WIDGET_VALUE = 4.5;
const BASE_GRAPH = JSON.parse(
  await readFile(
    new URL("../../fixtures/reorganise/simple_text_to_image.json", import.meta.url),
    "utf8",
  ),
);

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function candidateGraphWithWidgetValue(widgetValue) {
  const graph = cloneJson(BASE_GRAPH);
  graph.nodes = graph.nodes.map((node) => {
    if (node?.properties?.vibecomfy_uid !== TARGET_NODE_UID) {
      return node;
    }
    const nextValues = Array.isArray(node.widgets_values)
      ? [...node.widgets_values]
      : [];
    nextValues[TARGET_WIDGET_INDEX] = widgetValue;
    return {
      ...node,
      widgets_values: nextValues,
    };
  });
  return graph;
}

function candidateResponse({
  sessionId,
  turnId,
  message,
  candidateGraph,
  candidateGraphHash,
  oldValue,
  newValue,
}) {
  const changes = [
    {
      uid: TARGET_NODE_UID,
      field_path: `widgets_values.${TARGET_WIDGET_INDEX}`,
      old: oldValue,
      new: newValue,
    },
  ];
  return {
    ok: true,
    route: "revise",
    session_id: sessionId,
    turn_id: turnId,
    baseline_turn_id: "0000",
    message,
    reply: message,
    outcome: {
      kind: "candidate",
      changes,
    },
    changes,
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
    audit_ref: { audit_path: `turns/${turnId}/audit.json` },
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
    const liveGraph = window.app?.canvas?.graph;
    if (!liveGraph) {
      throw new Error("LiteGraph instance is unavailable.");
    }
    if (typeof liveGraph.clear === "function") {
      liveGraph.clear();
    }
    if (typeof liveGraph.configure === "function") {
      liveGraph.configure(graphPayload);
    } else {
      throw new Error("LiteGraph graph.configure() is unavailable.");
    }
    if (typeof liveGraph.setDirtyCanvas === "function") {
      liveGraph.setDirtyCanvas(true, true);
    }
    if (typeof window.app?.canvas?.setDirty === "function") {
      window.app.canvas.setDirty(true, true);
    }
  }, graph);
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
    if (entry.url && entry.url.includes("/api/view?type=input&filename=")) return false;
    if (entry.url && entry.url.includes("api.comfy.org/comfy-nodes/")) return false;
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

async function submitAndWaitForReview(page, prompt, expectedTurnId) {
  const composer = page.getByRole("textbox", { name: "Describe the workflow change..." });
  const submitButton = page.getByRole("button", { name: "Submit", exact: true });
  await composer.fill(prompt, { force: true });
  await Promise.all([
    page.waitForFunction(
      (turnId) => {
        const debug = typeof window.__vibecomfyPanelDebug === "function"
          ? window.__vibecomfyPanelDebug()
          : null;
        return debug && debug.phase === "AWAITING_REVIEW" && debug.turnId === turnId;
      },
      expectedTurnId,
      { timeout: 30_000 },
    ),
    submitButton.click({ force: true }),
  ]);
  await waitForPanelFlush(page, { timeout: 30_000 });
}

async function readTargetWidgetGeometry(page) {
  return page.evaluate(({ targetNodeUid, targetWidgetIndex }) => {
    const app = window.app;
    const graph = app?.canvas?.graph;
    const canvas = app?.canvas?.canvas || app?.canvas?.canvasEl || app?.canvas?.el || null;
    const scale = Number.isFinite(app?.canvas?.ds?.scale) && app.canvas.ds.scale > 0
      ? app.canvas.ds.scale
      : 1;
    const offset = Array.isArray(app?.canvas?.ds?.offset) ? app.canvas.ds.offset : [0, 0];
    const offsetX = Number.isFinite(offset[0]) ? offset[0] : 0;
    const offsetY = Number.isFinite(offset[1]) ? offset[1] : 0;
    const nodes = Array.isArray(graph?._nodes)
      ? graph._nodes
      : Array.isArray(graph?.nodes)
        ? graph.nodes
        : [];
    const node = nodes.find((candidate) => candidate?.properties?.vibecomfy_uid === targetNodeUid);
    if (!node) {
      return null;
    }
    const TITLE_H = (window.LiteGraph && window.LiteGraph.NODE_TITLE_HEIGHT) || 30;
    const SLOT_H = (window.LiteGraph && window.LiteGraph.NODE_SLOT_HEIGHT) || 20;
    const WIDGET_H = (window.LiteGraph && window.LiteGraph.NODE_WIDGET_HEIGHT) || 20;
    const pos = [
      Number.isFinite(Number(node?.pos?.[0])) ? Number(node.pos[0]) : 0,
      Number.isFinite(Number(node?.pos?.[1])) ? Number(node.pos[1]) : 0,
    ];
    const size = [
      Number.isFinite(Number(node?.size?.[0])) ? Number(node.size[0]) : 200,
      Number.isFinite(Number(node?.size?.[1])) ? Number(node.size[1]) : 100,
    ];
    const widgets = Array.isArray(node.widgets) ? node.widgets : [];
    const widget = widgets[targetWidgetIndex] || null;
    const slotRows = Math.max(
      Array.isArray(node.inputs) ? node.inputs.length : 0,
      Array.isArray(node.outputs) ? node.outputs.length : 0,
    );
    const computedRowsTop = pos[1] + slotRows * SLOT_H;
    let rowTop = computedRowsTop + targetWidgetIndex * WIDGET_H;
    let rowH = WIDGET_H;
    if (widget && typeof widget.last_y === "number") {
      rowTop = pos[1] + widget.last_y;
      if (typeof widget.computeSize === "function") {
        try {
          const computed = widget.computeSize(size[0]);
          if (computed && Number.isFinite(Number(computed[1])) && Number(computed[1]) > 0) {
            rowH = Number(computed[1]);
          }
        } catch (_error) {}
      }
    }
    const marginX = Math.min(15, Math.max(4, size[0] * 0.08));
    let fieldX = pos[0] + marginX;
    let fieldW = Math.max(8, size[0] - marginX * 2);
    const explicitX = Number(widget && (widget.input_x ?? widget.inputX ?? widget.field_x ?? widget.fieldX ?? widget.value_x ?? widget.valueX));
    const explicitW = Number(widget && (widget.input_width ?? widget.inputWidth ?? widget.field_width ?? widget.fieldWidth ?? widget.value_width ?? widget.valueWidth));
    if (Number.isFinite(explicitX)) {
      fieldX = pos[0] + explicitX;
    }
    if (Number.isFinite(explicitW) && explicitW > 0) {
      fieldW = explicitW;
    }
    const minX = pos[0];
    const maxRight = pos[0] + size[0];
    fieldX = Math.max(minX, Math.min(fieldX, maxRight - 4));
    fieldW = Math.max(4, Math.min(fieldW, maxRight - fieldX));

    return {
      widgetName: widget && typeof widget.name === "string" ? widget.name : `widget_${targetWidgetIndex}`,
      nodeBounds: {
        x: pos[0],
        y: pos[1] - TITLE_H,
        w: size[0],
        h: size[1] + TITLE_H,
      },
      widgetBounds: {
        x: fieldX,
        y: rowTop,
        w: fieldW,
        h: rowH,
      },
      previewBounds: {
        x: -offsetX,
        y: -offsetY,
        w: (Number(canvas?.width) || 0) / scale,
        h: (Number(canvas?.height) || 0) / scale,
      },
    };
  }, {
    targetNodeUid: TARGET_NODE_UID,
    targetWidgetIndex: TARGET_WIDGET_INDEX,
  });
}

async function forceOverlayRedraw(page) {
  await page.evaluate(() => {
    const graph = window.app?.canvas?.graph;
    if (graph && typeof graph.setDirtyCanvas === "function") {
      graph.setDirtyCanvas(true, true);
    }
    if (window.app?.canvas && typeof window.app.canvas.setDirty === "function") {
      window.app.canvas.setDirty(true, true);
    }
  });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function captureOverlayRecords(page, expectedToken) {
  await clearCanvas2DRecorder(page);
  await forceOverlayRedraw(page);
  await page.waitForFunction(
    (token) => {
      const recorder = window.__vibecomfyCanvas2DRecorder;
      if (!recorder || !Array.isArray(recorder.records)) {
        return false;
      }
      return recorder.records.some((entry) => {
        if ((entry?.kind !== "fillText" && entry?.kind !== "strokeText") || typeof entry?.text !== "string") {
          return false;
        }
        return entry.text.includes(token);
      });
    },
    String(expectedToken),
    { timeout: 15_000 },
  );
  return readCanvas2DRecorder(page);
}

function fontPx(font) {
  const match = /(\d+(?:\.\d+)?)px/.exec(String(font || ""));
  return match ? Number(match[1]) : 11;
}

function textBox(record) {
  const width = Number(record?.measuredWidth) || 0;
  const lineHeight = fontPx(record?.font) * 1.25;
  let left = Number(record?.x) || 0;
  if (record?.textAlign === "right") {
    left -= width;
  } else if (record?.textAlign === "center") {
    left -= width / 2;
  }
  let top = (Number(record?.y) || 0) - fontPx(record?.font);
  if (record?.textBaseline === "top") {
    top = Number(record?.y) || 0;
  } else if (record?.textBaseline === "middle") {
    top = (Number(record?.y) || 0) - lineHeight / 2;
  }
  return {
    left,
    top,
    right: left + width,
    bottom: top + lineHeight,
  };
}

function boundsInside(inner, outer, tolerance = 2) {
  return (
    inner.x >= outer.x - tolerance
    && inner.y >= outer.y - tolerance
    && inner.x + inner.w <= outer.x + outer.w + tolerance
    && inner.y + inner.h <= outer.y + outer.h + tolerance
  );
}

function boxInside(box, outer, tolerance = 2) {
  return (
    box.left >= outer.x - tolerance
    && box.top >= outer.y - tolerance
    && box.right <= outer.x + outer.w + tolerance
    && box.bottom <= outer.y + outer.h + tolerance
  );
}

function findWidgetPanelRecord(records, widgetBounds) {
  const candidates = records
    .filter((record) => (
      (record.kind === "roundRect" || record.kind === "fillRect" || record.kind === "strokeRect")
      && Number.isFinite(record.x)
      && Number.isFinite(record.y)
      && Number.isFinite(record.w)
      && Number.isFinite(record.h)
      && record.w > 0
      && record.h > 0
      && Math.abs(record.x - widgetBounds.x) <= 3
      && Math.abs(record.y - widgetBounds.y) <= 3
      && Math.abs(record.w - widgetBounds.w) <= 3
      && Math.abs(record.h - widgetBounds.h) <= 3
    ))
    .sort((left, right) => {
      const kindRank = (value) => {
        if (value.kind === "roundRect") return 0;
        if (value.kind === "fillRect") return 1;
        return 2;
      };
      return kindRank(left) - kindRank(right);
    });
  expect(candidates.length).toBeGreaterThan(0);
  return candidates[0];
}

function assertOverlayAnchoring(snapshot, geometry, expectedValue, staleValue = null) {
  expect(snapshot.installed).toBe(true);
  expect(snapshot.recordCount).toBeGreaterThan(0);

  const panelRecord = findWidgetPanelRecord(snapshot.records, geometry.widgetBounds);
  const panelBounds = {
    x: panelRecord.x,
    y: panelRecord.y,
    w: panelRecord.w,
    h: panelRecord.h,
  };

  expect(panelBounds.x).toBeGreaterThan(20);
  expect(panelBounds.y).toBeGreaterThan(20);
  expect(boundsInside(panelBounds, geometry.widgetBounds)).toBe(true);
  expect(boundsInside(panelBounds, geometry.nodeBounds)).toBe(true);
  expect(boundsInside(panelBounds, geometry.previewBounds, 4)).toBe(true);

  const panelTextRecords = snapshot.records.filter((record) => {
    if ((record.kind !== "fillText" && record.kind !== "strokeText") || !record.text) {
      return false;
    }
    const box = textBox(record);
    return boxInside(box, panelBounds, 2);
  });

  expect(panelTextRecords.length).toBeGreaterThan(0);
  expect(panelTextRecords.some((record) => record.text.includes(String(expectedValue)))).toBe(true);
  if (staleValue != null) {
    expect(panelTextRecords.some((record) => record.text.includes(String(staleValue)))).toBe(false);
  }

  for (const record of panelTextRecords) {
    const box = textBox(record);
    expect(box.left).toBeGreaterThan(20);
    expect(box.top).toBeGreaterThan(20);
    expect(boxInside(box, panelBounds, 2)).toBe(true);
    expect(boxInside(box, geometry.widgetBounds, 2)).toBe(true);
    expect(boxInside(box, geometry.nodeBounds, 2)).toBe(true);
    expect(boxInside(box, geometry.previewBounds, 4)).toBe(true);
  }
}

test.describe("Agent Panel Overlay", () => {
  let capture;

  test.beforeEach(async ({ page }) => {
    capture = installFailureCapture(page);
  });

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== "skipped") {
      await assertCleanBrowser(page, capture);
    }
  });

  test("draw-call recorder keeps widget overlay text anchored and replaces stale preview text after a newer submit", async ({ page }) => {
    const submitBodies = [];
    const responses = [
      candidateResponse({
        sessionId: "overlay-session",
        turnId: "0001",
        message: "Prepared the first cfg overlay preview.",
        candidateGraph: candidateGraphWithWidgetValue(FIRST_WIDGET_VALUE),
        candidateGraphHash: "overlay-candidate-0001",
        oldValue: 7,
        newValue: FIRST_WIDGET_VALUE,
      }),
      candidateResponse({
        sessionId: "overlay-session",
        turnId: "0002",
        message: "Prepared the replacement cfg overlay preview.",
        candidateGraph: candidateGraphWithWidgetValue(SECOND_WIDGET_VALUE),
        candidateGraphHash: "overlay-candidate-0002",
        oldValue: FIRST_WIDGET_VALUE,
        newValue: SECOND_WIDGET_VALUE,
      }),
    ];

    await installReadyStatusRoute(page);
    await page.route("**/vibecomfy/agent-executor", async (route, request) => {
      const nextResponse = responses.shift();
      expect(nextResponse).toBeTruthy();
      submitBodies.push(request.method() === "POST" ? await request.postDataJSON() : {});
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(nextResponse),
      });
    });

    await navigateToComfyUI(page);
    await waitForLauncher(page, OPEN_TIMEOUT);
    await openPanelViaLauncher(page, OPEN_TIMEOUT);
    await waitForPanelFlush(page, { timeout: 30_000 });
    await dismissTemplatesDialog(page);
    await loadFixtureGraph(page);
    await waitForPanelFlush(page, { timeout: 30_000 });
    await installCanvas2DRecorder(page);

    await submitAndWaitForReview(page, FIRST_SUBMIT_PROMPT, "0001");

    const firstDebug = await probePanelDebug(page);
    expect(firstDebug?.phase).toBe("AWAITING_REVIEW");
    expect(firstDebug?.turnId).toBe("0001");

    const overlay = await probeOverlayState(page);
    expect(overlay.previewInstalled).toBe(true);
    expect(overlay.hasOverlayDraw).toBe(true);

    const firstGeometry = await readTargetWidgetGeometry(page);
    expect(firstGeometry).not.toBeNull();

    const firstSnapshot = await captureOverlayRecords(page, String(FIRST_WIDGET_VALUE));
    assertOverlayAnchoring(firstSnapshot, firstGeometry, FIRST_WIDGET_VALUE);

    await submitAndWaitForReview(page, SECOND_SUBMIT_PROMPT, "0002");

    const secondDebug = await probePanelDebug(page);
    expect(secondDebug?.phase).toBe("AWAITING_REVIEW");
    expect(secondDebug?.turnId).toBe("0002");

    const secondGeometry = await readTargetWidgetGeometry(page);
    expect(secondGeometry).not.toBeNull();

    const secondSnapshot = await captureOverlayRecords(page, String(SECOND_WIDGET_VALUE));
    assertOverlayAnchoring(secondSnapshot, secondGeometry, SECOND_WIDGET_VALUE, FIRST_WIDGET_VALUE);
    expect(
      secondSnapshot.records.some((record) => (
        (record.kind === "fillText" || record.kind === "strokeText")
        && typeof record.text === "string"
        && record.text.includes(String(FIRST_WIDGET_VALUE))
      )),
    ).toBe(false);

    expect(submitBodies).toHaveLength(2);
    expect(submitBodies[0]?.task).toBe(FIRST_SUBMIT_PROMPT);
    expect(submitBodies[1]?.task).toBe(SECOND_SUBMIT_PROMPT);
  });
});
