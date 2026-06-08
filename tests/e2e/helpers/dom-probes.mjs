// ── Playwright helpers: DOM layout / scroll / composer probes ─────────────
// Reusable across all VibeComfy real-browser specs. No screenshot or
// pixel-diff assertions.

/**
 * @typedef {Object} ComposerState
 * @property {boolean} submitEnabled
 * @property {boolean} submitVisible
 * @property {boolean} stopEnabled
 * @property {boolean} stopVisible
 * @property {boolean} applyEnabled
 * @property {boolean} applyVisible
 * @property {boolean} rejectEnabled
 * @property {boolean} rejectVisible
 * @property {boolean} undoEnabled
 * @property {boolean} undoVisible
 * @property {string} submitLabel
 * @property {string} undoLabel
 * @property {string|null} noticeText
 * @property {boolean} noticeVisible
 * @property {string} composingText
 */

/**
 * @typedef {Object} ThreadState
 * @property {number} messageCount
 * @property {number} visibleMessageCount
 * @property {number} hiddenCount
 * @property {string|null} lastUserText
 * @property {string|null} lastAgentText
 * @property {boolean} autoScrollNearBottom
 */

/**
 * @typedef {Object} PanelLayout
 * @property {{width: number, height: number}} rootRect
 * @property {{width: number, height: number}} chatRect
 * @property {number} chatScrollTop
 * @property {number} chatScrollHeight
 * @property {number} chatClientHeight
 * @property {{width: number, height: number}} composerRect
 */

// ── Composer probes ────────────────────────────────────────────────────────

/**
 * Read the current composer button states from the agent panel DOM.
 *
 * @param {import("@playwright/test").Page} page
 * @param {import("@playwright/test").Locator} [panelRoot] - optional cached root locator
 * @returns {Promise<ComposerState>}
 */
export async function probeComposerState(page, panelRoot = null) {
  const root = panelRoot || page.locator("#vibecomfy-agent-panel-root");

  return page.evaluate(() => {
    const root = document.getElementById("vibecomfy-agent-panel-root");
    if (!root) {
      return {
        submitEnabled: false,
        submitVisible: false,
        stopEnabled: false,
        stopVisible: false,
        applyEnabled: false,
        applyVisible: false,
        rejectEnabled: false,
        rejectVisible: false,
        undoEnabled: false,
        undoVisible: false,
        submitLabel: "",
        undoLabel: "",
        noticeText: null,
        noticeVisible: false,
        composingText: "",
      };
    }

    const getButton = (sel) => root.querySelector(sel);
    const submit = getButton('[data-vibecomfy-action="submit"]');
    const stop = getButton('[data-vibecomfy-action="stop"]');
    const apply = getButton('[data-vibecomfy-action="apply"]');
    const reject = getButton('[data-vibecomfy-action="reject"]');
    const undo = getButton('[data-vibecomfy-action="undo"]');

    const notice = root.querySelector("[data-vibecomfy-composer-notice]");
    const textarea = root.querySelector(
      'textarea[data-vibecomfy-composer], textarea[id*="composer"], textarea',
    );

    return {
      submitEnabled: submit ? !submit.disabled : false,
      submitVisible: submit ? submit.style.display !== "none" : false,
      stopEnabled: stop ? !stop.disabled : false,
      stopVisible: stop ? stop.style.display !== "none" : false,
      applyEnabled: apply ? !apply.disabled : false,
      applyVisible: apply ? apply.style.display !== "none" : false,
      rejectEnabled: reject ? !reject.disabled : false,
      rejectVisible: reject ? reject.style.display !== "none" : false,
      undoEnabled: undo ? !undo.disabled : false,
      undoVisible: undo ? undo.style.display !== "none" : false,
      submitLabel: submit ? submit.textContent || "" : "",
      undoLabel: undo ? undo.textContent || "" : "",
      noticeText: notice ? notice.textContent?.trim() || null : null,
      noticeVisible: notice ? notice.style.display !== "none" : false,
      composingText: textarea ? textarea.value || "" : "",
    };
  });
}

/**
 * Type into the composer textarea and wait for the value to settle.
 *
 * @param {import("@playwright/test").Page} page
 * @param {string} text
 * @param {import("@playwright/test").Locator} [panelRoot]
 */
export async function composeText(page, text, panelRoot = null) {
  const root = panelRoot || page.locator("#vibecomfy-agent-panel-root");
  const textarea = root.locator(
    'textarea[data-vibecomfy-composer], textarea[id*="composer"], textarea',
  );
  await textarea.fill(text);
}

/**
 * Click a composer button by data-vibecomfy-action attribute.
 *
 * @param {import("@playwright/test").Page} page
 * @param {"submit"|"stop"|"apply"|"reject"|"undo"} action
 * @param {import("@playwright/test").Locator} [panelRoot]
 */
export async function clickComposerButton(page, action, panelRoot = null) {
  const root = panelRoot || page.locator("#vibecomfy-agent-panel-root");
  const btn = root.locator(`[data-vibecomfy-action="${action}"]`);
  await btn.click();
}

// ── Thread probes ──────────────────────────────────────────────────────────

/**
 * Read thread state from the agent panel thread DOM.
 *
 * @param {import("@playwright/test").Page} page
 * @param {import("@playwright/test").Locator} [panelRoot]
 * @returns {Promise<ThreadState>}
 */
export async function probeThreadState(page, panelRoot = null) {
  const root = panelRoot || page.locator("#vibecomfy-agent-panel-root");

  return page.evaluate(() => {
    const root = document.getElementById("vibecomfy-agent-panel-root");
    if (!root) {
      return {
        messageCount: 0,
        visibleMessageCount: 0,
        hiddenCount: 0,
        lastUserText: null,
        lastAgentText: null,
        autoScrollNearBottom: false,
      };
    }

    const chatBody = root.querySelector(
      "[data-vibecomfy-chat-body], [data-vibecomfy-chat]",
    );
    const bubbles = root.querySelectorAll("[data-vibecomfy-message-key]");

    let lastUserText = null;
    let lastAgentText = null;
    for (const bubble of bubbles) {
      const label = bubble.querySelector("span");
      const textDiv = bubble.querySelector("div");
      if (!label || !textDiv) continue;
      if (label.textContent === "You") {
        lastUserText = textDiv.textContent?.trim() || null;
      } else if (label.textContent === "Agent") {
        lastAgentText = textDiv.textContent?.trim() || null;
      }
    }

    // Count hidden entries
    const showEarlier = root.querySelector("[data-vibecomfy-show-earlier]");
    let hiddenCount = 0;
    if (showEarlier) {
      const match = showEarlier.textContent?.match(/(\d+)/);
      if (match) {
        hiddenCount = Number(match[1]) || 0;
      }
    }

    const scrollEl = chatBody || root;
    const nearBottom =
      scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight < 120;

    return {
      messageCount: bubbles.length,
      visibleMessageCount: bubbles.length,
      hiddenCount,
      lastUserText,
      lastAgentText,
      autoScrollNearBottom: nearBottom,
    };
  });
}

// ── Layout probes ──────────────────────────────────────────────────────────

/**
 * Read DOM geometry for the agent panel root and its sections.
 *
 * @param {import("@playwright/test").Page} page
 * @param {import("@playwright/test").Locator} [panelRoot]
 * @returns {Promise<PanelLayout>}
 */
export async function probePanelLayout(page, panelRoot = null) {
  const root = panelRoot || page.locator("#vibecomfy-agent-panel-root");

  return page.evaluate(() => {
    const root = document.getElementById("vibecomfy-agent-panel-root");
    const zeroRect = { width: 0, height: 0 };
    if (!root) {
      return {
        rootRect: zeroRect,
        chatRect: zeroRect,
        chatScrollTop: 0,
        chatScrollHeight: 0,
        chatClientHeight: 0,
        composerRect: zeroRect,
      };
    }

    const rootRect = root.getBoundingClientRect();
    const chatEl =
      root.querySelector("[data-vibecomfy-chat-body]") ||
      root.querySelector("[data-vibecomfy-chat]") ||
      root;
    const chatRect = chatEl.getBoundingClientRect();
    const composerEl = root.querySelector(
      "[data-vibecomfy-composer-section]",
    );

    return {
      rootRect: { width: rootRect.width, height: rootRect.height },
      chatRect: { width: chatRect.width, height: chatRect.height },
      chatScrollTop: chatEl.scrollTop || 0,
      chatScrollHeight: chatEl.scrollHeight || 0,
      chatClientHeight: chatEl.clientHeight || 0,
      composerRect: composerEl
        ? {
            width: composerEl.getBoundingClientRect().width,
            height: composerEl.getBoundingClientRect().height,
          }
        : zeroRect,
    };
  });
}

// ── Visibility helpers ─────────────────────────────────────────────────────

/**
 * Wait for the submit button to become enabled and visible.
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ timeout?: number }} [options]
 * @param {import("@playwright/test").Locator} [panelRoot]
 */
export async function waitForSubmitReady(page, { timeout = 30_000 } = {}, panelRoot = null) {
  const root = panelRoot || page.locator("#vibecomfy-agent-panel-root");
  const submit = root.locator('[data-vibecomfy-action="submit"]');

  await submit.waitFor({ state: "visible", timeout });
  await page.waitForFunction(
    () => {
      const btn = document.querySelector(
        '#vibecomfy-agent-panel-root [data-vibecomfy-action="submit"]',
      );
      return btn && !btn.disabled && btn.style.display !== "none";
    },
    null,
    { timeout },
  );
}

/**
 * Wait for pending flushes to complete (dirtySections is empty, flushPending is false).
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ timeout?: number }} [options]
 */
export async function waitForPanelFlush(page, { timeout = 15_000 } = {}) {
  await page.waitForFunction(
    () => {
      if (typeof window.__vibecomfyPanelDebug !== "function") {
        return true; // Debug hook not installed yet — nothing to flush.
      }
      const debug = window.__vibecomfyPanelDebug();
      return (
        debug.flushPending === false &&
        (!Array.isArray(debug.dirtySections) || debug.dirtySections.length === 0)
      );
    },
    null,
    { timeout },
  );
}
