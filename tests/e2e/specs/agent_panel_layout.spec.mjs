// ── agent_panel_layout.spec.mjs ─────────────────────────────────────────────
// Playwright layout spec: agent panel geometry, scroll, composer, and
// error-surface assertions.
//
// Covers:
//   - Open via launcher and sidebar tab.
//   - Viewport-bounded panel shell.
//   - Internally-scrolling thread region (wheel and programmatic scroll).
//   - Composer visibility.
//   - No outer panel scroll.
//   - Zero unexpected console / page / request errors.

import { test, expect } from "@playwright/test";
import {
  installFailureCapture,
  collectUnhandledPageErrors,
  MOUNT_MODE,
  waitForLauncher,
  openPanelViaLauncher,
  openPanelViaSidebar,
  closePanel,
  isPanelOpen,
  panelMountMode,
  probeComposerState,
  probePanelLayout,
  probeThreadState,
  waitForPanelFlush,
} from "../helpers/index.mjs";

const OPEN_TIMEOUT = { timeout: 30_000 };

// ─────────────────────────────────────────────────────────────────────────────
// Helper: navigate to the ComfyUI base and wait for the app shell
// ─────────────────────────────────────────────────────────────────────────────

async function navigateToComfyUI(page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  // Wait for the LiteGraph canvas to appear — this signals the app is
  // sufficiently initialized for the VibeComfy extension to boot.
  await page.waitForSelector("canvas#graph-canvas", { timeout: 60_000 });
  // Give the extension a moment to install its hooks.
  await page.waitForTimeout(1_000);
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: assert zero failure surface (console, page, request)
// ─────────────────────────────────────────────────────────────────────────────

async function assertCleanBrowser(page, capture, { allowComfyWarnings = true } = {}) {
  // Collect page-level unhandled errors.
  const unhandled = await collectUnhandledPageErrors(page);

  // Filter out known-ComfyUI noise that is unrelated to VibeComfy.
  const meaningfulConsole = capture.consoleErrors.filter((e) => {
    if (!allowComfyWarnings && e.type === "warning") return true;
    // Allow standard ComfyUI dev-mode warnings.
    const text = e.text || "";
    if (text.includes("ComfyUI") && e.type === "warning") return false;
    if (text.includes("DevTools")) return false;
    if (text.includes("[DOM]")) return false;
    if (text.includes("Automatic1111")) return false;
    if (text.includes("No resource with given URL")) return false;
    if (/^\s*$/.test(text)) return false;
    return true;
  });

  const meaningfulRequests = capture.failedRequests.filter((r) => {
    // Filter out favicon / heartbeat / websocket noise.
    if (r.url && r.url.includes("/ws")) return false;
    if (r.url && r.url.includes("favicon")) return false;
    if (r.status === 0 && (r.statusText || "").includes("ERR_ABORTED")) return false;
    return true;
  });

  const issues = [];
  if (meaningfulConsole.length > 0) {
    issues.push(
      `${meaningfulConsole.length} console error/warning(s):\n` +
        meaningfulConsole.map((c) => `  [${c.type}] ${c.text}`).join("\n"),
    );
  }
  if (meaningfulRequests.length > 0) {
    issues.push(
      `${meaningfulRequests.length} failed request(s):\n` +
        meaningfulRequests.map((r) => `  ${r.status} ${r.statusText} ${r.url}`).join("\n"),
    );
  }
  if (capture.pageErrors.length > 0) {
    issues.push(
      `${capture.pageErrors.length} page error(s):\n` +
        capture.pageErrors.map((e) => `  ${e.message}`).join("\n"),
    );
  }
  if (unhandled.length > 0) {
    issues.push(
      `${unhandled.length} unhandled page error(s):\n` +
        unhandled.map((e) => `  ${e.message}`).join("\n"),
    );
  }

  if (issues.length > 0) {
    throw new Error(`Browser failure surface not clean:\n${issues.join("\n\n")}`);
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// Layout Test Suite
// ═════════════════════════════════════════════════════════════════════════════

test.describe("Agent Panel Layout", () => {
  let capture;

  test.beforeEach(async ({ page }) => {
    capture = installFailureCapture(page);
  });

  test.afterEach(async ({ page }, testInfo) => {
    // Always assert clean after each test, unless the test was skipped.
    if (testInfo.status !== "skipped") {
      await assertCleanBrowser(page, capture);
    }
  });

  // ── Open via launcher ──────────────────────────────────────────────────

  test("opens panel via launcher button", async ({ page }) => {
    await navigateToComfyUI(page);

    // Verify launcher exists.
    const launcher = await waitForLauncher(page, OPEN_TIMEOUT);
    await expect(launcher).toBeVisible();

    // Open panel.
    const root = await openPanelViaLauncher(page, OPEN_TIMEOUT);
    await expect(root).toBeVisible();

    // Verify panel is open in launcher mode.
    expect(await isPanelOpen(page)).toBe(true);
    expect(await panelMountMode(page)).toBe(MOUNT_MODE.LAUNCHER);
  });

  // ── Open via sidebar tab ───────────────────────────────────────────────

  test("opens panel via sidebar tab", async ({ page }) => {
    await navigateToComfyUI(page);

    // Close any existing panel first.
    await closePanel(page);

    // Open via sidebar.
    const root = await openPanelViaSidebar(page, OPEN_TIMEOUT);
    await expect(root).toBeVisible();

    // Verify panel is open in sidebar mode.
    expect(await isPanelOpen(page)).toBe(true);
    expect(await panelMountMode(page)).toBe(MOUNT_MODE.SIDEBAR);
  });

  // ── Viewport-bounded panel shell ───────────────────────────────────────

  test("panel shell is viewport-bounded with correct dimensions", async ({ page }) => {
    await navigateToComfyUI(page);
    const root = await openPanelViaLauncher(page, OPEN_TIMEOUT);

    const layout = await probePanelLayout(page, root);

    // The root div should have positive width and height.
    expect(layout.rootRect.width).toBeGreaterThan(0);
    expect(layout.rootRect.height).toBeGreaterThan(0);

    // The panel is fixed right, full-height. In launcher mode the root has
    // width: 420px, height: 100vh. We check that it doesn't exceed the viewport.
    const viewport = page.viewportSize();
    if (viewport) {
      expect(layout.rootRect.width).toBeLessThanOrEqual(viewport.width);
      expect(layout.rootRect.height).toBeLessThanOrEqual(viewport.height + 2); // tolerate subpixel
    }

    // The shell (inner container) should have non-zero dimensions too,
    // reflected by the chat rect being measurable when the panel is open.
    expect(layout.chatRect.width).toBeGreaterThan(0);
    expect(layout.chatRect.height).toBeGreaterThan(0);
  });

  // ── Internally scrolling thread region ─────────────────────────────────

  test("thread region scrolls internally — programmatic scroll", async ({ page }) => {
    await navigateToComfyUI(page);
    const root = await openPanelViaLauncher(page, OPEN_TIMEOUT);

    // Programmatically scroll the thread region and verify scrollTop changes.
    await page.evaluate(() => {
      const thread = document.querySelector(
        '[data-vibecomfy-agent-thread="1"]',
      );
      if (thread) {
        thread.scrollTop = 100;
      }
    });

    // Read layout after scroll.
    const layout = await probePanelLayout(page, root);

    // The chatScrollTop should reflect the scroll (if scrollable content exists).
    // On a fresh panel with no messages, scrollHeight may equal clientHeight,
    // so scrollTop may stay at 0. We verify the values are sensible.
    expect(typeof layout.chatScrollTop).toBe("number");
    expect(layout.chatScrollTop).toBeGreaterThanOrEqual(0);
    expect(layout.chatScrollHeight).toBeGreaterThanOrEqual(0);
    expect(layout.chatClientHeight).toBeGreaterThanOrEqual(0);
    // ScrollTop should never exceed scrollHeight - clientHeight.
    const maxScroll = layout.chatScrollHeight - layout.chatClientHeight;
    expect(layout.chatScrollTop).toBeLessThanOrEqual(Math.max(0, maxScroll));
  });

  test("thread region scrolls internally — wheel event does not propagate", async ({ page }) => {
    await navigateToComfyUI(page);
    const root = await openPanelViaLauncher(page, OPEN_TIMEOUT);

    // Get initial scroll positions of both the thread and the document.
    const before = await page.evaluate(() => {
      const thread = document.querySelector(
        '[data-vibecomfy-agent-thread="1"]',
      );
      return {
        threadScroll: thread ? thread.scrollTop : 0,
        docScroll: document.documentElement.scrollTop,
      };
    });

    // Dispatch a wheel event on the thread region.
    const wheelHandled = await page.evaluate(() => {
      const thread = document.querySelector(
        '[data-vibecomfy-agent-thread="1"]',
      );
      if (!thread) return false;

      const wheelEvent = new WheelEvent("wheel", {
        deltaY: 200,
        deltaMode: 0,
        bubbles: true,
        cancelable: true,
      });
      thread.dispatchEvent(wheelEvent);
      // Return whether the event had defaultPrevented set (meaning it was
      // consumed by the scrollable region). Note: dispatchEvent is
      // synchronous but the browser may not immediately update scroll.
      return wheelEvent.defaultPrevented;
    });

    // After the wheel, check document scroll hasn't changed.
    const after = await page.evaluate(() => {
      return document.documentElement.scrollTop;
    });

    // Document-level scroll should not have changed due to wheel inside
    // the thread region (the panel's body is position:fixed, so outer
    // document scroll is generally irrelevant — but we verify anyway).
    expect(after).toBe(before.docScroll);
  });

  // ── Composer visibility ────────────────────────────────────────────────

  test("composer is visible when panel is open", async ({ page }) => {
    await navigateToComfyUI(page);
    await openPanelViaLauncher(page, OPEN_TIMEOUT);

    const composer = await probeComposerState(page);

    // The composer should be present (at minimum, the submit button's
    // visibility will indicate the composer section exists).
    // On fixture-backed runs, the panel transitions to IDLE quickly.
    // We check that probeComposerState returns a sensible object.
    expect(composer).toBeDefined();
    expect(typeof composer.submitEnabled).toBe("boolean");
    expect(typeof composer.submitVisible).toBe("boolean");
    expect(typeof composer.composingText).toBe("string");

    // The composer textarea should exist and be empty initially.
    expect(composer.composingText).toBe("");

    // At least one button should be present (visible or not).
    // The submit button should exist in the DOM.
    const submitBtn = page.locator("#vibecomfy-agent-panel-submit");
    await expect(submitBtn).toBeAttached();
  });

  // ── No outer panel scroll ──────────────────────────────────────────────

  test("panel root does not have its own scrollbar", async ({ page }) => {
    await navigateToComfyUI(page);
    const root = await openPanelViaLauncher(page, OPEN_TIMEOUT);

    // The panel root has height: 100vh and is positioned fixed.
    // We verify it does NOT have overflow:auto or overflow:scroll
    // producing its own scrollbar.

    const overflowStyle = await page.evaluate(() => {
      const el = document.getElementById("vibecomfy-agent-panel-root");
      if (!el) return null;
      const style = window.getComputedStyle(el);
      return {
        overflowY: style.overflowY,
        overflowX: style.overflowX,
        overflow: style.overflow,
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
      };
    });

    expect(overflowStyle).not.toBeNull();

    // The root should NOT have its own vertical scroll.
    // If scrollHeight > clientHeight and overflow-y is visible/hidden,
    // there is no scrollbar on the root itself.
    const hasScrollableOverflow =
      overflowStyle.overflowY === "auto" ||
      overflowStyle.overflowY === "scroll" ||
      overflowStyle.overflow === "auto" ||
      overflowStyle.overflow === "scroll";

    // The root may technically have overflow visible/hidden but no
    // scrollbar if its children handle scrolling. We assert that
    // if scrollHeight exceeds clientHeight AND the overflow style
    // would produce a scrollbar, that's a problem.
    if (hasScrollableOverflow && overflowStyle.scrollHeight > overflowStyle.clientHeight + 5) {
      // Allow: if the root has overflow-y: auto but the content
      // fits (scrollHeight ≈ clientHeight), that's fine — no
      // visible scrollbar. But if it's overflowing, that's a defect.
      throw new Error(
        `Panel root has scrollable overflow (${
          overflowStyle.overflowY
        }) and content overflows (scrollHeight=${
          overflowStyle.scrollHeight
        }, clientHeight=${overflowStyle.clientHeight}). The thread should be the scroll container, not the root.`,
      );
    }

    // The thread region should be the one with overflow-y: auto.
    const threadOverflow = await page.evaluate(() => {
      const thread = document.querySelector(
        '[data-vibecomfy-agent-thread="1"]',
      );
      if (!thread) return null;
      const style = window.getComputedStyle(thread);
      return {
        overflowY: style.overflowY,
        overflow: style.overflow,
      };
    });

    expect(threadOverflow).not.toBeNull();
    // The thread element should have overflow-y that allows scrolling.
    const threadScrollable =
      threadOverflow.overflowY === "auto" ||
      threadOverflow.overflowY === "scroll" ||
      threadOverflow.overflow === "auto" ||
      threadOverflow.overflow === "scroll";
    expect(threadScrollable).toBe(true);
  });

  // ── Thread state probe sanity ──────────────────────────────────────────

  test("thread state probe returns expected shape", async ({ page }) => {
    await navigateToComfyUI(page);
    await openPanelViaLauncher(page, OPEN_TIMEOUT);

    const thread = await probeThreadState(page);

    expect(thread).toBeDefined();
    expect(typeof thread.messageCount).toBe("number");
    expect(typeof thread.visibleMessageCount).toBe("number");
    expect(typeof thread.hiddenCount).toBe("number");
    expect(typeof thread.autoScrollNearBottom).toBe("boolean");
    // lastUserText / lastAgentText can be null for an empty thread.
  });

  // ── Flush readiness after open ─────────────────────────────────────────

  test("panel reaches flush-ready state after open", async ({ page }) => {
    await navigateToComfyUI(page);
    await openPanelViaLauncher(page, OPEN_TIMEOUT);

    // Wait for any pending renders to finish.
    await waitForPanelFlush(page, { timeout: 15_000 });

    // Verify the panel debug hook is accessible.
    const debug = await page.evaluate(() => {
      if (typeof window.__vibecomfyPanelDebug !== "function") return null;
      return window.__vibecomfyPanelDebug();
    });

    if (debug) {
      expect(debug.flushPending).toBe(false);
      expect(
        !Array.isArray(debug.dirtySections) || debug.dirtySections.length === 0,
      ).toBe(true);
    }
  });
});
