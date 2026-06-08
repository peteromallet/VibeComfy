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
const SUBMIT_PROMPT =
  "Add a 2x ImageScaleBy upscale step immediately after the video VAE decode";
const BROWSER_VAL_FIXTURE = JSON.parse(
  await readFile(
    new URL("../../fixtures/editor_sessions/e0b4f2df7b4da808/request.json", import.meta.url),
    "utf8",
  ),
);

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

async function loadFixtureGraph(page) {
  await page.evaluate((graphPayload) => {
    const graph = window.app?.canvas?.graph;
    if (!graph) {
      throw new Error("LiteGraph instance is unavailable.");
    }
    if (typeof graph.clear === "function") {
      graph.clear();
    }
    if (typeof graph.configure === "function") {
      graph.configure(graphPayload);
    } else {
      throw new Error("LiteGraph graph.configure() is unavailable.");
    }
    if (typeof graph.setDirtyCanvas === "function") {
      graph.setDirtyCanvas(true, true);
    }
    if (typeof window.app?.graph?.setDirtyCanvas === "function") {
      window.app.graph.setDirtyCanvas(true, true);
    }
  }, BROWSER_VAL_FIXTURE.graph);
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
    if (text.includes("[vibecomfy] computePreviewDiff") && text.includes("unresolvable link endpoint")) return false;
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

async function readCanvasScaleNodes(page) {
  return page.evaluate(() => {
    const graph = window.app?.canvas?.graph;
    const nodes = Array.isArray(graph?._nodes)
      ? graph._nodes
      : Array.isArray(graph?.nodes)
        ? graph.nodes
        : [];
    return nodes
      .filter((node) => node?.type === "ImageScaleBy")
      .map((node) => ({
        id: node?.id ?? null,
        uid: node?.properties?.vibecomfy_uid ?? null,
        widgetValues: Array.isArray(node?.widgets_values)
          ? [...node.widgets_values]
          : Array.isArray(node?.widgets)
            ? node.widgets.map((widget) => widget?.value)
            : [],
      }));
  });
}

test.describe("Agent Panel Turn", () => {
  let capture;

  test.beforeEach(async ({ page }) => {
    capture = installFailureCapture(page);
  });

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== "skipped") {
      await assertCleanBrowser(page, capture);
    }
  });

  test("submits a fixture-backed turn, shows and clears progress, exposes candidate audit affordances, and applies live widget changes", async ({ page }) => {
    await navigateToComfyUI(page);
    await waitForLauncher(page, OPEN_TIMEOUT);
    await openPanelViaLauncher(page, OPEN_TIMEOUT);
    await waitForPanelFlush(page, { timeout: 30_000 });
    await dismissTemplatesDialog(page);
    await loadFixtureGraph(page);
    await waitForPanelFlush(page, { timeout: 30_000 });

    const composer = page.getByRole("textbox", { name: "Describe the workflow change..." });
    const submitButton = page.getByRole("button", { name: "Submit", exact: true });

    const beforeScaleNodes = await readCanvasScaleNodes(page);

    let delayedSubmitSeen = false;
    await page.route("**/vibecomfy/agent-edit", async (route, request) => {
      if (!delayedSubmitSeen && request.method() === "POST") {
        delayedSubmitSeen = true;
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
      await route.continue();
    });

    await composer.fill(SUBMIT_PROMPT, { force: true });
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

    const historyMount = page.locator("#vibecomfy-agent-panel-region-history");
    await expect(historyMount).toBeVisible({ timeout: 30_000 });
    await expect(historyMount).toContainText(/pending/i, { timeout: 30_000 });

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
    await page.waitForFunction(
      () => {
        const mount = document.getElementById("vibecomfy-agent-panel-region-history");
        return !mount || (mount.textContent || "").trim() === "";
      },
      null,
      { timeout: 30_000 },
    );

    const debug = await probePanelDebug(page);
    expect(debug?.phase).toBe("AWAITING_REVIEW");
    expect(debug?.turnId).toBeTruthy();

    const lastAgentBubble = page.locator('[data-vibecomfy-message-key]:has(span:text-is("Agent"))').last();
    await expect(lastAgentBubble).toBeVisible();
    await lastAgentBubble.locator("span", { hasText: "details" }).click();

    await expect(lastAgentBubble.getByText("Candidate", { exact: true })).toBeVisible();
    await expect(lastAgentBubble.getByText("Audit", { exact: true })).toBeVisible();
    await expect(lastAgentBubble.locator('[data-vibecomfy-candidate-action="apply"]')).toBeVisible();
    await expect(lastAgentBubble.locator('[data-vibecomfy-candidate-action="reject"]')).toBeVisible();
    await expect(lastAgentBubble.getByText("affected node preview")).toBeVisible();
    const auditButton = lastAgentBubble.getByRole("button", { name: /Audit/ }).first();
    await expect(auditButton).toBeVisible();

    await Promise.all([
      page.waitForEvent("download"),
      auditButton.click(),
    ]);

    await lastAgentBubble.locator('[data-vibecomfy-candidate-action="apply"]').click();
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

    const afterScaleNodes = await readCanvasScaleNodes(page);
    expect(afterScaleNodes.length).toBe(beforeScaleNodes.length + 1);
    const addedScaleNode = afterScaleNodes.find((node) => node.uid === "n1")
      || afterScaleNodes.find((node) => (
        Array.isArray(node.widgetValues)
        && node.widgetValues.includes("nearest-exact")
        && node.widgetValues.includes(2)
      ));
    expect(addedScaleNode).toBeTruthy();
    expect(addedScaleNode.widgetValues).toContain("nearest-exact");
    expect(addedScaleNode.widgetValues).toContain(2);

  });
});
