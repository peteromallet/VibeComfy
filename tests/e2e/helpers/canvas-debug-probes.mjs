// ── Playwright helpers: canvas / debug probes ──────────────────────────────
// Reusable across all VibeComfy real-browser specs. No screenshot or
// pixel-diff assertions.
//
// Probes through:
//   - window.app.canvas.graph         (live LiteGraph instance)
//   - window.__vibecomfyPanelDebug()  (debug snapshot)
//   - Overlay / debug state on app and runtime singletons

/**
 * @typedef {Object} CanvasGraphProbe
 * @property {boolean} available
 * @property {number} nodeCount
 * @property {number} linkCount
 * @property {string[]} nodeTypes
 * @property {string[]} nodeUids
 * @property {Object|null} serialized - result of graph.serialize() if available
 */

/**
 * @typedef {Object} PanelDebugProbe
 * @property {string|null} panelId
 * @property {number} panelsCreated
 * @property {string|null} phase
 * @property {{kind: string|null, ready: boolean, reason: string|null}} readiness
 * @property {string|null} sessionId
 * @property {string|null} turnId
 * @property {number} messageCount
 * @property {number} visibleMessageCount
 * @property {string[]} dirtySections
 * @property {boolean} flushPending
 * @property {number} flushCount
 * @property {string|null} mountMode
 * @property {boolean} mountedCheck
 */

/**
 * @typedef {Object} OverlayProbe
 * @property {boolean} previewInstalled - whether __vibecomfyAgentPreviewOverlayInstalled
 * @property {boolean} hasOverlayDraw - whether __vibecomfyAgentPreviewOverlayDraw is a function
 * @property {string|null} previewInstallStrategy
 * @property {boolean} previewDegraded
 * @property {string|null} previewDetail
 * @property {string|null} overlayDrawModelCacheKey
 */

/**
 * @typedef {Object} AppProbe
 * @property {boolean} appExists
 * @property {boolean} graphExists
 * @property {boolean} canvasExists
 * @property {boolean} extensionManagerExists
 * @property {CanvasGraphProbe} graph
 * @property {OverlayProbe} overlay
 */

// ── Graph probes ───────────────────────────────────────────────────────────

/**
 * Probe `window.app.canvas.graph` for live LiteGraph state.
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<CanvasGraphProbe>}
 */
export async function probeCanvasGraph(page) {
  return page.evaluate(() => {
    const graph = window.app?.canvas?.graph;

    if (!graph) {
      return {
        available: false,
        nodeCount: 0,
        linkCount: 0,
        nodeTypes: [],
        nodeUids: [],
        serialized: null,
      };
    }

    const nodes = Array.isArray(graph._nodes)
      ? graph._nodes
      : Array.isArray(graph.nodes)
        ? graph.nodes
        : [];

    const links = graph.links;
    let linkCount = 0;
    if (Array.isArray(links)) {
      linkCount = links.length;
    } else if (links && typeof links === "object") {
      linkCount = Object.keys(links).length;
    }

    const nodeTypes = [];
    const nodeUids = [];
    for (const node of nodes) {
      if (node?.type) {
        nodeTypes.push(node.type);
      }
      const uid =
        node?.properties?.vibecomfy_uid ||
        node?.properties?.uid ||
        node?.uid ||
        node?.id;
      if (uid != null) {
        nodeUids.push(String(uid));
      }
    }

    let serialized = null;
    if (typeof graph.serialize === "function") {
      try {
        serialized = graph.serialize();
      } catch (_e) {
        // Best-effort: serialization may fail.
      }
    }

    return {
      available: true,
      nodeCount: nodes.length,
      linkCount,
      nodeTypes,
      nodeUids,
      serialized,
    };
  });
}

// ── Panel debug probes ─────────────────────────────────────────────────────

/**
 * Call `window.__vibecomfyPanelDebug()` and return the full debug snapshot.
 * Returns null if the debug hook is not installed.
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<PanelDebugProbe|null>}
 */
export async function probePanelDebug(page) {
  return page.evaluate(() => {
    if (typeof window.__vibecomfyPanelDebug !== "function") {
      return null;
    }
    try {
      const debug = window.__vibecomfyPanelDebug();
      if (!debug) {
        return null;
      }
      return {
        panelId: debug.panelId ?? null,
        panelsCreated: debug.panelsCreated ?? 0,
        phase: debug.phase ?? null,
        readiness: {
          kind: debug.readiness?.kind ?? null,
          ready: debug.readiness?.ready ?? false,
          reason: debug.readiness?.reason ?? null,
        },
        sessionId: debug.sessionId ?? null,
        turnId: debug.turnId ?? null,
        baselineTurnId: debug.baselineTurnId ?? null,
        messageCount: debug.messageCount ?? 0,
        visibleMessageCount: debug.visibleMessageCount ?? 0,
        dirtySections: Array.isArray(debug.dirtySections)
          ? [...debug.dirtySections]
          : [],
        flushPending: debug.flushPending ?? false,
        flushCount: debug.flushCount ?? 0,
        lastFlushReason: debug.lastFlushReason ?? null,
        mountMode: debug.mountMode ?? null,
        mountedCheck: debug.mountedCheck ?? false,
        lastThreadRender: debug.lastThreadRender ?? null,
        lastNoticeRender: debug.lastNoticeRender ?? null,
        renderCounts: debug.renderCounts ?? {},
        renderErrors: debug.renderErrors ?? [],
        epochs: debug.epochs ?? {},
      };
    } catch (_e) {
      return null;
    }
  });
}

/**
 * Wait for the debug hook to report a specific phase.
 *
 * @param {import("@playwright/test").Page} page
 * @param {string} phase - e.g. "IDLE", "AWAITING_REVIEW", "SUBMITTING"
 * @param {{ timeout?: number }} [options]
 */
export async function waitForPanelPhase(page, phase, { timeout = 30_000 } = {}) {
  await page.waitForFunction(
    (expectedPhase) => {
      if (typeof window.__vibecomfyPanelDebug !== "function") {
        return false;
      }
      const debug = window.__vibecomfyPanelDebug();
      return debug && debug.phase === expectedPhase;
    },
    phase,
    { timeout },
  );
}

/**
 * Wait for the debug hook to indicate readiness (ready=true).
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ timeout?: number }} [options]
 */
export async function waitForPanelReadiness(page, { timeout = 30_000 } = {}) {
  await page.waitForFunction(
    () => {
      if (typeof window.__vibecomfyPanelDebug !== "function") {
        return false;
      }
      const debug = window.__vibecomfyPanelDebug();
      return debug && debug.readiness && debug.readiness.ready === true;
    },
    null,
    { timeout },
  );
}

// ── Overlay probes ─────────────────────────────────────────────────────────

/**
 * Probe the preview overlay state from the app global and runtime singleton.
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<OverlayProbe>}
 */
export async function probeOverlayState(page) {
  return page.evaluate(() => {
    const app = window.app;
    const installed = !!app?.__vibecomfyAgentPreviewOverlayInstalled;
    const hasOverlayDraw =
      typeof app?.__vibecomfyAgentPreviewOverlayDraw === "function";

    // Read runtime singleton for overlay draw model cache.
    let overlayKey = null;
    try {
      const record = window.__vibecomfyAgentPanelSingleton;
      if (record?.runtime?._overlayDrawModelCache) {
        overlayKey = record.runtime._overlayDrawModelCache.key ?? null;
      }
    } catch (_e) {
      // Best-effort.
    }

    // Read preview foreground install report.
    let installStrategy = null;
    let previewDegraded = false;
    let previewDetail = null;
    try {
      const record = window.__vibecomfyAgentPanelSingleton;
      const report = record?.runtime?._previewForegroundInstallReport;
      if (report) {
        installStrategy = report.strategy ?? null;
        previewDegraded = report.degraded ?? false;
        previewDetail = report.detail ?? null;
      }
    } catch (_e) {
      // Best-effort.
    }

    return {
      previewInstalled: installed,
      hasOverlayDraw,
      previewInstallStrategy: installStrategy,
      previewDegraded,
      previewDetail,
      overlayDrawModelCacheKey: overlayKey,
    };
  });
}

// ── App-level probes ───────────────────────────────────────────────────────

/**
 * Full app-level probe aggregating graph, overlay, and debug state.
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<AppProbe>}
 */
export async function probeApp(page) {
  const [graph, overlay] = await Promise.all([
    probeCanvasGraph(page),
    probeOverlayState(page),
  ]);

  return page.evaluate(
    ({ graphAvailable, overlayState }) => {
      const app = window.app;
      return {
        appExists: !!app,
        graphExists: !!app?.canvas?.graph,
        canvasExists: !!app?.canvas,
        extensionManagerExists: !!app?.extensionManager,
        graph: {
          available: graphAvailable,
          nodeCount: 0,
          linkCount: 0,
          nodeTypes: [],
          nodeUids: [],
          serialized: null,
        },
        overlay: overlayState,
      };
    },
    { graphAvailable: graph.available, overlayState: overlay },
  );
}

/**
 * Wait for `window.app.canvas.graph` to become available and initialized.
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ timeout?: number }} [options]
 */
export async function waitForAppGraph(page, { timeout = 30_000 } = {}) {
  await page.waitForFunction(
    () => {
      const graph = window.app?.canvas?.graph;
      if (!graph) return false;
      const nodes = Array.isArray(graph._nodes)
        ? graph._nodes
        : Array.isArray(graph.nodes)
          ? graph.nodes
          : [];
      return nodes.length > 0;
    },
    null,
    { timeout },
  );
}

// ── Serialization helpers ──────────────────────────────────────────────────

/**
 * Serialize the current live graph via `app.canvas.graph.serialize()`.
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<Object|null>}
 */
export async function serializeLiveGraph(page) {
  return page.evaluate(() => {
    const graph = window.app?.canvas?.graph;
    if (!graph || typeof graph.serialize !== "function") {
      return null;
    }
    try {
      return graph.serialize();
    } catch (_e) {
      return null;
    }
  });
}

/**
 * Return the count of live graph nodes or -1 if unavailable.
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<number>}
 */
export async function liveNodeCount(page) {
  return page.evaluate(() => {
    const graph = window.app?.canvas?.graph;
    if (!graph) return -1;
    const nodes = Array.isArray(graph._nodes)
      ? graph._nodes
      : Array.isArray(graph.nodes)
        ? graph.nodes
        : [];
    return nodes.length;
  });
}
