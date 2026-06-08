import { test, expect } from "@playwright/test";
import {
  installFailureCapture,
  collectUnhandledPageErrors,
  waitForLauncher,
  openPanelViaLauncher,
  closePanel,
  isPanelOpen,
  waitForPanelFlush,
  probePanelDebug,
} from "../helpers/index.mjs";

const SESSION_ID = "panel_lifecycle_seed";
const LAST_AGENT_TEXT = "Lifecycle agent 16";
const SUBMIT_PROMPT = "Bypass the video VAE decode node and instead wire the video save node's images input directly from whatever feeds the decode.";
const OPEN_TIMEOUT = { timeout: 30_000 };

test.use({
  viewport: { width: 1280, height: 520 },
});

async function navigateToComfyUI(page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("canvas#graph-canvas", { timeout: 60_000 });
  await page.waitForTimeout(1_000);
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

async function seedActiveSession(page, sessionId = SESSION_ID) {
  await page.evaluate((value) => {
    window.localStorage.setItem("vibecomfy_active_session_id", value);
  }, sessionId);
}

async function openRehydratedPanel(page) {
  await seedActiveSession(page, SESSION_ID);
  await waitForLauncher(page, OPEN_TIMEOUT);
  const panelRoot = await openPanelViaLauncher(page, OPEN_TIMEOUT);
  await waitForPanelFlush(page, { timeout: 30_000 });
  await page.waitForFunction(
    (expectedSessionId) => {
      if (typeof window.__vibecomfyPanelDebug !== "function") return false;
      const debug = window.__vibecomfyPanelDebug();
      return (
        debug
        && debug.sessionId === expectedSessionId
        && debug.messageCount === 32
        && debug.visibleMessageCount === 30
        && debug.flushPending === false
      );
    },
    SESSION_ID,
    { timeout: 30_000 },
  );
  return panelRoot;
}

async function readMessageKeys(page) {
  return page.evaluate(() => Array.from(
    document.querySelectorAll("[data-vibecomfy-message-key]"),
    (node) => node.dataset.vibecomfyMessageKey,
  ));
}

async function readThreadMetrics(page) {
  return page.evaluate(() => {
    const thread = document.querySelector('[data-vibecomfy-agent-thread="1"]');
    const bubbles = Array.from(document.querySelectorAll("[data-vibecomfy-message-key]"));
    const newest = bubbles[bubbles.length - 1] || null;
    const threadRect = thread?.getBoundingClientRect() || null;
    const newestRect = newest?.getBoundingClientRect() || null;
    const newestVisible = Boolean(
      threadRect
      && newestRect
      && newestRect.top >= threadRect.top - 1
      && newestRect.bottom <= threadRect.bottom + 1,
    );
    return {
      exists: Boolean(thread),
      scrollTop: thread ? thread.scrollTop : 0,
      scrollHeight: thread ? thread.scrollHeight : 0,
      clientHeight: thread ? thread.clientHeight : 0,
      scrolledToBottom: thread?.dataset?.vibecomfyScrolledToBottom || null,
      newestVisible,
      newestText: newest ? newest.textContent || "" : "",
      showEarlierTitle: document.querySelector('[data-vibecomfy-chat-older-mount="1"] button')?.title || null,
    };
  });
}

async function scrollThread(page, scrollTop) {
  await page.evaluate((value) => {
    const thread = document.querySelector('[data-vibecomfy-agent-thread="1"]');
    if (thread) {
      thread.scrollTop = value;
      thread.dataset.vibecomfyScrolledToBottom = "0";
    }
  }, scrollTop);
}

test.describe("Agent Panel Lifecycle", () => {
  let capture;

  test.beforeEach(async ({ page }) => {
    capture = installFailureCapture(page);
  });

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== "skipped") {
      await assertCleanBrowser(page, capture);
    }
  });

  test("rehydrates a multi-message session, keeps newest visible, and does not duplicate after reopen", async ({ page }) => {
    await navigateToComfyUI(page);
    await openRehydratedPanel(page);

    const debug = await probePanelDebug(page);
    expect(debug?.sessionId).toBe(SESSION_ID);
    expect(debug?.messageCount).toBe(32);
    expect(debug?.visibleMessageCount).toBe(30);

    const firstKeys = await readMessageKeys(page);
    expect(firstKeys).toHaveLength(30);
    expect(new Set(firstKeys).size).toBe(firstKeys.length);

    const metrics = await readThreadMetrics(page);
    expect(metrics.exists).toBe(true);
    expect(metrics.scrolledToBottom).toBe("1");
    expect(metrics.newestVisible).toBe(true);
    expect(metrics.newestText).toContain(LAST_AGENT_TEXT);
    expect(metrics.showEarlierTitle).toBe("2 earlier messages hidden");

    await closePanel(page);
    expect(await isPanelOpen(page)).toBe(false);

    await openPanelViaLauncher(page, OPEN_TIMEOUT);
    await waitForPanelFlush(page, { timeout: 30_000 });
    await page.waitForFunction(
      (expectedSessionId) => {
        if (typeof window.__vibecomfyPanelDebug !== "function") return false;
        const debug = window.__vibecomfyPanelDebug();
        return debug && debug.sessionId === expectedSessionId && debug.messageCount === 32;
      },
      SESSION_ID,
      { timeout: 30_000 },
    );

    const reopenedKeys = await readMessageKeys(page);
    expect(reopenedKeys).toHaveLength(30);
    expect(new Set(reopenedKeys).size).toBe(reopenedKeys.length);
    expect(reopenedKeys).toEqual(firstKeys);

    const reopenedMetrics = await readThreadMetrics(page);
    expect(reopenedMetrics.newestVisible).toBe(true);
    expect(reopenedMetrics.newestText).toContain(LAST_AGENT_TEXT);
  });

  test("preserves scroll position when scrolled up during a non-submit lifecycle rerender", async ({ page }) => {
    await navigateToComfyUI(page);
    await openRehydratedPanel(page);

    const threadBefore = await readThreadMetrics(page);
    expect(threadBefore.scrollHeight).toBeGreaterThan(threadBefore.clientHeight);

    await scrollThread(page, 48);
    const manuallyScrolled = await readThreadMetrics(page);
    expect(manuallyScrolled.scrollTop).toBeGreaterThan(0);
    expect(manuallyScrolled.scrolledToBottom).toBe("0");

    const showEarlierButton = page.locator('[data-vibecomfy-chat-older-mount="1"] button');
    await expect(showEarlierButton).toBeVisible();
    await showEarlierButton.click();
    await waitForPanelFlush(page, { timeout: 30_000 });

    const threadAfter = await readThreadMetrics(page);
    expect(threadAfter.scrollTop).toBeGreaterThanOrEqual(manuallyScrolled.scrollTop - 2);
    const debug = await probePanelDebug(page);
    expect(debug?.messageCount).toBe(32);
    expect(debug?.visibleMessageCount).toBe(32);
  });

  test("submit jumps back to the newest message after the user has scrolled up", async ({ page }) => {
    await navigateToComfyUI(page);
    const panelRoot = await openRehydratedPanel(page);
    const submitButton = panelRoot.locator("#vibecomfy-agent-panel-submit");
    await submitButton.waitFor({ state: "visible", timeout: 30_000 });
    await expect(submitButton).toBeEnabled();

    await scrollThread(page, 0);
    const beforeSubmit = await readThreadMetrics(page);
    expect(beforeSubmit.scrolledToBottom).toBe("0");

    await panelRoot.locator("#vibecomfy-agent-panel-prompt").fill(SUBMIT_PROMPT);
    await submitButton.click();

    await page.waitForFunction(
      (baselineCount) => {
        if (typeof window.__vibecomfyPanelDebug !== "function") return false;
        const debug = window.__vibecomfyPanelDebug();
        return debug && debug.phase !== "SUBMITTING" && debug.messageCount > baselineCount;
      },
      32,
      { timeout: 60_000 },
    );
    await waitForPanelFlush(page, { timeout: 60_000 });
    await expect(panelRoot.getByText("Bypass the video VAE decode node", { exact: false })).toBeVisible();

    const afterSubmit = await readThreadMetrics(page);

    expect(afterSubmit.scrollTop).toBeGreaterThan(beforeSubmit.scrollTop);
    expect(afterSubmit.scrolledToBottom).toBe("1");
    expect(afterSubmit.newestVisible).toBe(true);

    const debug = await probePanelDebug(page);
    expect(debug?.phase).not.toBe("SUBMITTING");
    expect(debug?.messageCount).toBeGreaterThan(32);
  });
});
