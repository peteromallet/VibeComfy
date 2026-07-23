import fs from "node:fs/promises";
import path from "node:path";
import { test, expect } from "@playwright/test";
import { openPanelViaLauncher, waitForLauncher, waitForPanelFlush } from "../helpers/index.mjs";

const ENABLED = process.env.VIBECOMFY_DEMO_PICKER === "1";
const REPO_ROOT = process.env.REPO_ROOT || path.resolve(import.meta.dirname, "..", "..", "..");
const OUTPUT_ROOT = process.env.VIBECOMFY_DEMO_PREVIEW_OUT
  || path.join(REPO_ROOT, "out", "demo_preview_visuals");
const SCENARIO_FILTER = process.env.VIBECOMFY_DEMO_SCENARIO || "";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderContactSheet(records) {
  const cards = records.map((record) => {
    const diff = record.diagnostics?.previewDiff || {};
    const counts = [
      `${diff.edited?.length || 0} edited`,
      `${diff.added?.length || 0} added`,
      `${diff.removed?.length || 0} removed`,
      `${diff.addedLinks?.length || 0} links added`,
      `${diff.removedLinks?.length || 0} links removed`,
    ].join(" · ");
    const error = record.error
      ? `<pre class="error">${escapeHtml(record.error)}</pre>`
      : "";
    return `<article>
      <h2>${escapeHtml(record.title)}</h2>
      <p><code>${escapeHtml(record.id)}</code> · ${escapeHtml(counts)}</p>
      <a href="${encodeURIComponent(record.screenshot)}"><img loading="lazy" src="${encodeURIComponent(record.screenshot)}" alt="${escapeHtml(record.title)} actual preview"></a>
      <p><a href="${encodeURIComponent(record.rawScreenshot)}">Open the untouched initial viewport</a></p>
      ${error}
    </article>`;
  }).join("\n");
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>VibeComfy actual demo previews</title>
<style>
body{margin:0;padding:24px;background:#0d0f13;color:#edf2f7;font:14px system-ui,sans-serif}
h1{margin:0 0 8px} .summary{color:#aab2c0;margin-bottom:24px}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:20px}
article{background:#171920;border:1px solid #30333d;border-radius:10px;padding:14px;min-width:0}
h2{font-size:16px;margin:0 0 6px} p{color:#aab2c0;margin:0 0 10px}
img{display:block;width:100%;height:auto;border-radius:6px;background:#08090b}
.error{white-space:pre-wrap;color:#ff9999;background:#281517;padding:10px;border-radius:5px}
</style></head><body>
<h1>VibeComfy actual preview-mode captures</h1>
<p class="summary">${records.length} scenarios. Each image is a full browser viewport captured from the real ComfyUI page in <code>AWAITING_REVIEW</code>, after the production overlay settled.</p>
<main>${cards}</main></body></html>`;
}

async function waitForActualPreview(page, scenarioId) {
  await page.waitForFunction((id) => {
    const debug = typeof window.__vibecomfyPanelDebug === "function"
      ? window.__vibecomfyPanelDebug()
      : null;
    return debug?.phase === "AWAITING_REVIEW"
      && debug?.demoStage === "ready_to_apply"
      && debug?.demoScenarioId === id
      && debug?.flushPending === false;
  }, scenarioId, { timeout: 30_000 });

  await page.waitForFunction(() => {
    const debug = window.__vibecomfyPanelDebug?.();
    const cache = window.__vibecomfyAgentPanelSingleton?.runtime?._overlayDrawModelCache;
    if (!debug?.previewDiff || !cache?.key) return false;
    const fieldCount = Array.isArray(debug.previewDiff.editedFields)
      ? debug.previewDiff.editedFields.length
      : 0;
    if (fieldCount === 0) return true;
    const receipt = debug.previewDomProjection;
    return Number(receipt?.attemptedFields || 0) >= fieldCount
      && Number(receipt?.projectedFields || 0)
        + (Array.isArray(receipt?.skippedFields) ? receipt.skippedFields.length : 0)
        >= fieldCount;
  }, null, { timeout: 15_000 });
  await waitForPanelFlush(page, { timeout: 15_000 });
}

async function dismissStartupDialogs(page) {
  const dialog = page.getByRole("dialog");
  if (await dialog.count()) {
    await page.keyboard.press("Escape").catch(() => {});
    const close = page.getByRole("button", { name: "Close dialog" });
    if (await close.isVisible().catch(() => false)) {
      await close.click({ force: true }).catch(() => {});
    }
    await dialog.first().waitFor({ state: "hidden", timeout: 5_000 }).catch(() => {});
  }
  const gettingStarted = page.getByText("Getting Started", { exact: true });
  if (await gettingStarted.isVisible().catch(() => false)) {
    const templateLabels = page.getByText("Templates", { exact: true });
    for (let index = (await templateLabels.count()) - 1; index >= 0; index -= 1) {
      const label = templateLabels.nth(index);
      const toggle = label.locator("xpath=ancestor-or-self::button[1]");
      if (await toggle.count()) {
        await toggle.click({ force: true }).catch(() => {});
        if (!await gettingStarted.isVisible().catch(() => false)) break;
      }
    }
  }
  await expect(gettingStarted).toBeHidden({ timeout: 5_000 });
}

async function readDiagnostics(page) {
  return page.evaluate(() => {
    const debug = window.__vibecomfyPanelDebug?.() || null;
    const runtime = window.__vibecomfyAgentPanelSingleton?.runtime;
    const panel = runtime?.agentPanel;
    const graph = window.app?.canvas?.graph;
    const canvas = window.app?.canvas;
    const canvasElement = canvas?.canvas || canvas?.canvasEl || canvas?.el;
    const chips = Array.from(document.querySelectorAll("[data-vibecomfy-preview-chip]"))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          text: element.textContent || "",
          rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
        };
      });
    const editedWidgets = [];
    for (const edited of debug?.previewDiff?.edited || []) {
      const node = Array.isArray(graph?._nodes)
        ? graph._nodes.find((candidate) => String(
          candidate?.properties?.vibecomfy_uid ?? candidate?.id ?? "",
        ) === String(edited?.uid ?? ""))
        : null;
      for (const index of edited?.changedWidgetIndices || []) {
        const widget = node?.widgets?.[index];
        const domCandidates = [
          ["inputEl", widget?.inputEl],
          ["inputElement", widget?.inputElement],
          ["textarea", widget?.textarea],
          ["element", widget?.element],
          ["domElement", widget?.domElement],
          ["el", widget?.el],
        ].filter(([, element]) => element && typeof element.getBoundingClientRect === "function")
          .map(([key, element]) => {
            const rect = element.getBoundingClientRect();
            return {
              key,
              tag: element.tagName || element.nodeName || null,
              connected: Boolean(element.isConnected),
              rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
            };
          });
        editedWidgets.push({
          uid: String(edited?.uid ?? ""),
          index,
          nodeType: node?.type || null,
          nodePos: Array.from(node?.pos || []),
          nodeSize: Array.from(node?.size || []),
          widgetName: widget?.name || null,
          widgetType: widget?.type || null,
          keys: widget && typeof widget === "object" ? Object.keys(widget).sort() : [],
          domCandidates,
          allNodeWidgets: Array.isArray(node?.widgets) ? node.widgets.map((entry, widgetIndex) => ({
            index: widgetIndex,
            name: entry?.name || null,
            type: entry?.type || null,
            lastY: Number.isFinite(entry?.last_y) ? entry.last_y : null,
            y: Number.isFinite(entry?.y) ? entry.y : null,
            hidden: Boolean(entry?.hidden),
            value: typeof entry?.value === "string" ? entry.value.slice(0, 120) : entry?.value ?? null,
          })) : [],
        });
      }
    }
    const affectedIds = new Set([
      ...(debug?.previewDiff?.added || []),
      ...(debug?.previewDiff?.removed || []),
      ...(debug?.previewDiff?.edited || []).map((entry) => entry?.uid),
    ].filter((uid) => uid != null).map(String));
    const liveByUid = new Map((Array.isArray(graph?._nodes) ? graph._nodes : []).map((node) => [
      String(node?.properties?.vibecomfy_uid ?? node?.id ?? ""),
      node,
    ]));
    const candidateByUid = new Map((
      Array.isArray(panel?.state?.candidateGraph?.nodes) ? panel.state.candidateGraph.nodes : []
    ).map((node) => [
      String(node?.properties?.vibecomfy_uid ?? node?.id ?? ""),
      node,
    ]));
    const canvasRect = canvasElement?.getBoundingClientRect?.() || {
      left: 0,
      top: 0,
      right: canvasElement?.width || 0,
      bottom: canvasElement?.height || 0,
    };
    const scale = Number(canvas?.ds?.scale || 1);
    const offset = Array.isArray(canvas?.ds?.offset) ? canvas.ds.offset : [0, 0];
    const affectedViewport = Array.from(affectedIds).map((uid) => {
      const node = candidateByUid.get(uid) || liveByUid.get(uid);
      const pos = Array.isArray(node?.pos) ? node.pos : [node?.pos?.[0], node?.pos?.[1]];
      const size = Array.isArray(node?.size) ? node.size : [node?.size?.[0], node?.size?.[1]];
      const left = canvasRect.left + (Number(pos?.[0] || 0) + Number(offset[0] || 0)) * scale;
      const top = canvasRect.top + (Number(pos?.[1] || 0) + Number(offset[1] || 0)) * scale;
      const right = left + Number(size?.[0] || 200) * scale;
      const bottom = top + Number(size?.[1] || 100) * scale;
      return {
        uid,
        rect: { left, top, right, bottom },
        intersectsViewport: right > canvasRect.left
          && left < canvasRect.right
          && bottom > canvasRect.top
          && top < canvasRect.bottom,
      };
    });
    return {
      ...debug,
      liveGraph: {
        nodes: Array.isArray(graph?._nodes) ? graph._nodes.length : null,
        links: graph?.links && typeof graph.links === "object" ? Object.keys(graph.links).length : null,
      },
      candidateNodes: Array.isArray(panel?.state?.candidateGraph?.nodes)
        ? panel.state.candidateGraph.nodes.length
        : null,
      overlayModelKey: runtime?._overlayDrawModelCache?.key || null,
      canvasGeometry: {
        rect: {
          left: canvasRect.left,
          top: canvasRect.top,
          width: canvasRect.width,
          height: canvasRect.height,
          right: canvasRect.right,
          bottom: canvasRect.bottom,
        },
        backingWidth: canvasElement?.width || null,
        backingHeight: canvasElement?.height || null,
        scale,
        offset,
        canvasTag: canvasElement?.tagName || null,
      },
      previewChips: chips,
      editedWidgets,
      affectedViewport,
    };
  });
}

test("@demo-preview capture every actual demo review state", async ({ page, request }) => {
  test.skip(!ENABLED, "Run with VIBECOMFY_DEMO_PICKER=1 (npm run capture:demo-previews)");
  test.setTimeout(10 * 60_000);

  await fs.rm(OUTPUT_ROOT, { recursive: true, force: true });
  await fs.mkdir(OUTPUT_ROOT, { recursive: true });

  const consoleIssues = [];
  const pageErrors = [];
  const failedRequests = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleIssues.push({ type: message.type(), text: message.text() });
    }
  });
  page.on("pageerror", (error) => pageErrors.push(String(error?.stack || error)));
  page.on("requestfailed", (failed) => failedRequests.push({
    url: failed.url(),
    error: failed.failure()?.errorText || "request failed",
  }));

  await page.addInitScript(() => localStorage.setItem("vibecomfy_demo_picker_enabled", "1"));
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("canvas#graph-canvas", { timeout: 60_000 });
  await page.waitForTimeout(1_000);
  await dismissStartupDialogs(page);
  await waitForLauncher(page, { timeout: 60_000 });
  await openPanelViaLauncher(page, { timeout: 30_000 });

  const manifestResponse = await request.get("/vibecomfy/demo/scenarios");
  expect(manifestResponse.ok()).toBeTruthy();
  const manifest = await manifestResponse.json();
  expect(Array.isArray(manifest.scenarios)).toBeTruthy();
  expect(manifest.scenarios.length).toBeGreaterThan(0);

  await page.waitForFunction((count) => {
    const picker = window.__vibecomfyAgentPanelSingleton?.runtime?.agentPanel?.previewPicker;
    return picker?.mounted === true && picker?.select?.options?.length === count + 1;
  }, manifest.scenarios.length, { timeout: 30_000 });

  const records = [];
  const scenarios = SCENARIO_FILTER
    ? manifest.scenarios.filter((scenario) => scenario.id === SCENARIO_FILTER)
    : manifest.scenarios;
  expect(scenarios.length).toBeGreaterThan(0);
  for (const scenario of scenarios) {
    const issueOffsets = {
      console: consoleIssues.length,
      page: pageErrors.length,
      requests: failedRequests.length,
    };
    const screenshot = `${scenario.id}.fitted.png`;
    const rawScreenshot = `${scenario.id}.raw.png`;
    const record = { id: scenario.id, title: scenario.title || scenario.id, screenshot, rawScreenshot };
    try {
      const loaded = await page.evaluate(async (id) => {
        const picker = window.__vibecomfyAgentPanelSingleton?.runtime?.agentPanel?.previewPicker;
        if (!picker) throw new Error("Demo picker controller is unavailable");
        return Boolean(await picker.loadScenarioById(id, { readyToApply: true }));
      }, scenario.id);
      if (!loaded) throw new Error("Demo picker returned no scenario");
      await dismissStartupDialogs(page);
      await waitForActualPreview(page, scenario.id);
      record.diagnostics = await readDiagnostics(page);
      if (scenario.id === "qwen_face_distortion_wrong_slot") {
        const chipText = record.diagnostics.previewChips.map((chip) => chip.text);
        expect(chipText).toContain("upscale_method: bicubic");
        expect(chipText).toContain("cfg: 4.5");
      }
      await page.screenshot({ path: path.join(OUTPUT_ROOT, rawScreenshot), fullPage: false });
    } catch (error) {
      record.error = String(error?.stack || error);
      record.diagnostics = await readDiagnostics(page).catch(() => null);
    }
    await page.screenshot({ path: path.join(OUTPUT_ROOT, screenshot), fullPage: false });
    record.browserIssues = {
      console: consoleIssues.slice(issueOffsets.console),
      pageErrors: pageErrors.slice(issueOffsets.page),
      failedRequests: failedRequests.slice(issueOffsets.requests),
    };
    records.push(record);
  }

  await fs.writeFile(
    path.join(OUTPUT_ROOT, "diagnostics.json"),
    `${JSON.stringify({ generatedAt: new Date().toISOString(), records }, null, 2)}\n`,
    "utf8",
  );
  await fs.writeFile(path.join(OUTPUT_ROOT, "index.html"), renderContactSheet(records), "utf8");

  const failures = records.filter((record) => {
    const issueText = JSON.stringify(record.browserIssues || {});
    const hiddenAffected = record.diagnostics?.affectedViewport
      ?.filter((entry) => !entry.intersectsViewport) || [];
    return record.error
      || hiddenAffected.length > 0
      || /RangeError|Maximum call stack size exceeded/i.test(issueText);
  });
  const tripoRefine = records.find((record) => record.id === "triporefine_stage_add");
  if (tripoRefine) {
    expect(
      tripoRefine.diagnostics?.previewDiff?.added,
      "TripoRefine demo must visibly retain its landed add-node operation",
    ).toContain("n1");
  }
  expect(failures, `Visual capture failures; inspect ${path.join(OUTPUT_ROOT, "index.html")}`).toEqual([]);
});
