// ── Playwright helpers: agent panel open via launcher & sidebar paths ──────
// Reusable across all VibeComfy real-browser specs. No screenshot or
// pixel-diff assertions.

/**
 * Panel mount modes mirroring AGENT_PANEL_MOUNT_MODE in the extension.
 * @readonly
 */
export const MOUNT_MODE = Object.freeze({
  LAUNCHER: "launcher",
  SIDEBAR: "sidebar",
});

/**
 * Known panel DOM IDs (mirrors PANEL_IDS in vibecomfy_roundtrip.js).
 * @readonly
 */
export const PANEL_IDS = Object.freeze({
  root: "vibecomfy-agent-panel-root",
  launcher: "vibecomfy-agent-launcher",
});

/**
 * Known panel dataset keys.
 * @readonly
 */
export const PANEL_DATASET = Object.freeze({
  open: "open",
  panelId: "vibecomfyPanelId",
  lastCommand: "lastCommand",
  mountMode: "mountMode",
});

/**
 * Wait for the agent panel root to appear in the DOM.
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ timeout?: number }} [options]
 * @returns {Promise<import("@playwright/test").Locator>}
 */
export async function waitForPanelRoot(page, { timeout = 15_000 } = {}) {
  const root = page.locator(`#${PANEL_IDS.root}`);
  await root.waitFor({ state: "attached", timeout });
  return root;
}

/**
 * Wait for the launcher button to appear in the DOM.
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ timeout?: number }} [options]
 * @returns {Promise<import("@playwright/test").Locator>}
 */
export async function waitForLauncher(page, { timeout = 15_000 } = {}) {
  const launcher = page.locator(`#${PANEL_IDS.launcher}`);
  await launcher.waitFor({ state: "attached", timeout });
  return launcher;
}

/**
 * Open the agent panel via the launcher button (toggles open/closed).
 *
 * After clicking, waits for the panel root to have data-open="1" and the
 * mount mode to be "launcher".
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ timeout?: number }} [options]
 * @returns {Promise<import("@playwright/test").Locator>} the panel root
 */
export async function openPanelViaLauncher(page, { timeout = 15_000 } = {}) {
  const launcher = await waitForLauncher(page, { timeout });

  // Only click if the panel is not already open in launcher mode.
  const root = page.locator(`#${PANEL_IDS.root}`);
  const isOpen = await root.getAttribute(`data-${PANEL_DATASET.open}`);
  const mountMode = await root.getAttribute(`data-${PANEL_DATASET.mountMode}`);

  if (isOpen === "1" && mountMode === MOUNT_MODE.LAUNCHER) {
    return root;
  }

  await launcher.click();

  // Wait for the panel to transition to open state.
  await root.waitFor({
    state: "attached",
    timeout,
  });
  await page.waitForFunction(
    ({ rootId, openAttr }) => {
      const el = document.getElementById(rootId);
      return el && el.dataset[openAttr] === "1";
    },
    { rootId: PANEL_IDS.root, openAttr: PANEL_DATASET.open },
    { timeout },
  );

  return root;
}

/**
 * Open the agent panel via the sidebar tab.
 *
 * Attempts to find and click the VibeComfy Agent sidebar tab. This works
 * only when the extension has registered AGENT_SIDEBAR_TAB_ID.
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ timeout?: number }} [options]
 * @returns {Promise<import("@playwright/test").Locator>} the panel root
 */
export async function openPanelViaSidebar(page, { timeout = 15_000 } = {}) {
  // The sidebar tab is registered with id "vibecomfy.agent-edit".
  // Different ComfyUI frontend builds render the tab differently, so we
  // try multiple selector strategies.
  const sidebarSelectors = [
    `[data-tab-id="vibecomfy.agent-edit"]`,
    `[data-sidebar-tab="vibecomfy.agent-edit"]`,
    `#vibecomfy\\.agent-edit`,
    `.sidebar-tab[data-id="vibecomfy.agent-edit"]`,
  ];

  let clicked = false;
  for (const selector of sidebarSelectors) {
    const tab = page.locator(selector);
    if (await tab.count() > 0) {
      await tab.first().click();
      clicked = true;
      break;
    }
  }

  if (!clicked) {
    // Fallback: try to find any element containing "VibeComfy Agent" text
    // within the sidebar region.
    const textMatch = page.locator(
      '.comfy-sidebar [title*="VibeComfy"], .comfy-sidebar [title*="Agent"]',
    );
    const count = await textMatch.count();
    if (count > 0) {
      await textMatch.first().click();
      clicked = true;
    }
  }

  if (!clicked) {
    throw new Error(
      "Could not find the VibeComfy Agent sidebar tab. The extension may not have registered it yet.",
    );
  }

  // Wait for the panel root to appear inside the sidebar container.
  const root = page.locator(`#${PANEL_IDS.root}`);
  await root.waitFor({ state: "attached", timeout });

  await page.waitForFunction(
    ({ rootId, openAttr }) => {
      const el = document.getElementById(rootId);
      return el && el.dataset[openAttr] === "1";
    },
    { rootId: PANEL_IDS.root, openAttr: PANEL_DATASET.open },
    { timeout },
  );

  return root;
}

/**
 * Close the agent panel if it is currently open.
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ timeout?: number }} [options]
 */
export async function closePanel(page, { timeout = 5_000 } = {}) {
  const root = page.locator(`#${PANEL_IDS.root}`);
  const isOpen = await root.getAttribute(`data-${PANEL_DATASET.open}`);
  if (isOpen !== "1") {
    return;
  }

  // Try the close button inside the panel first.
  const closeBtn = root.locator("[data-vibecomfy-close]");
  if ((await closeBtn.count()) > 0) {
    await closeBtn.click();
  } else {
    // Fallback: click the launcher button to toggle.
    const launcher = page.locator(`#${PANEL_IDS.launcher}`);
    if ((await launcher.count()) > 0) {
      await launcher.click();
    }
  }

  await page.waitForFunction(
    ({ rootId, openAttr }) => {
      const el = document.getElementById(rootId);
      return !el || el.dataset[openAttr] !== "1";
    },
    { rootId: PANEL_IDS.root, openAttr: PANEL_DATASET.open },
    { timeout },
  ).catch(() => {
    // Panel may already be closed; ignore timeout.
  });
}

/**
 * Check whether the agent panel is currently open.
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<boolean>}
 */
export async function isPanelOpen(page) {
  const root = page.locator(`#${PANEL_IDS.root}`);
  if ((await root.count()) === 0) {
    return false;
  }
  const open = await root.getAttribute(`data-${PANEL_DATASET.open}`);
  return open === "1";
}

/**
 * Get the current panel mount mode from the DOM.
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<string|null>}
 */
export async function panelMountMode(page) {
  const root = page.locator(`#${PANEL_IDS.root}`);
  if ((await root.count()) === 0) {
    return null;
  }
  return root.getAttribute(`data-${PANEL_DATASET.mountMode}`);
}
