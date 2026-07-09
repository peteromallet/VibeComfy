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

/**
 * @typedef {Object} Canvas2DRecord
 * @property {string} kind
 * @property {{id: string|null, width: number|null, height: number|null}} canvas
 * @property {number|null} x
 * @property {number|null} y
 * @property {number|null} w
 * @property {number|null} h
 * @property {number|null} radius
 * @property {string|null} text
 * @property {number|null} maxWidth
 * @property {number|null} measuredWidth
 * @property {string|null} font
 * @property {string|null} textAlign
 * @property {string|null} textBaseline
 * @property {string|null} fillStyle
 * @property {string|null} strokeStyle
 * @property {number|null} lineWidth
 * @property {number} sequence
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

// ── Canvas2D draw-call recorder ────────────────────────────────────────────

/**
 * Install an opt-in Canvas2D recorder on the page and clear existing records.
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ canvasId?: string|null }} [options]
 */
export async function installCanvas2DRecorder(page, { canvasId = "graph-canvas" } = {}) {
  return page.evaluate(({ canvasId: requestedCanvasId }) => {
    const proto = window.CanvasRenderingContext2D?.prototype;
    if (!proto) {
      return {
        installed: false,
        reason: "CanvasRenderingContext2D is unavailable.",
      };
    }

    const toFiniteNumber = (value) => {
      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    };

    const toStyleString = (value) => {
      if (value == null) return null;
      if (typeof value === "string") return value;
      try {
        return String(value);
      } catch (_error) {
        return null;
      }
    };

    let recorder = window.__vibecomfyCanvas2DRecorder;
    if (!recorder || recorder.installed !== true) {
      recorder = {
        installed: true,
        enabled: false,
        canvasId: null,
        maxRecords: 2_000,
        records: [],
        sequence: 0,
        originals: {},
      };

      const shouldRecord = (ctx) => {
        if (!recorder.enabled) {
          return false;
        }
        const canvas = ctx?.canvas || null;
        if (!canvas) {
          return false;
        }
        if (typeof recorder.canvasId === "string" && recorder.canvasId) {
          return (canvas.id || null) === recorder.canvasId;
        }
        return true;
      };

      const canvasSnapshot = (ctx) => {
        const canvas = ctx?.canvas || null;
        return {
          id: canvas?.id || null,
          width: toFiniteNumber(canvas?.width),
          height: toFiniteNumber(canvas?.height),
        };
      };

      const pushRecord = (ctx, kind, payload) => {
        if (!shouldRecord(ctx)) {
          return;
        }
        recorder.sequence += 1;
        recorder.records.push({
          kind,
          canvas: canvasSnapshot(ctx),
          x: toFiniteNumber(payload?.x),
          y: toFiniteNumber(payload?.y),
          w: toFiniteNumber(payload?.w),
          h: toFiniteNumber(payload?.h),
          radius: toFiniteNumber(payload?.radius),
          text: typeof payload?.text === "string" ? payload.text : null,
          maxWidth: toFiniteNumber(payload?.maxWidth),
          measuredWidth: toFiniteNumber(payload?.measuredWidth),
          font: typeof payload?.font === "string" ? payload.font : null,
          textAlign: typeof payload?.textAlign === "string" ? payload.textAlign : null,
          textBaseline: typeof payload?.textBaseline === "string" ? payload.textBaseline : null,
          fillStyle: toStyleString(payload?.fillStyle),
          strokeStyle: toStyleString(payload?.strokeStyle),
          lineWidth: toFiniteNumber(payload?.lineWidth),
          sequence: recorder.sequence,
        });
        if (recorder.records.length > recorder.maxRecords) {
          recorder.records.splice(0, recorder.records.length - recorder.maxRecords);
        }
      };

      const wrap = (name, factory) => {
        if (typeof proto[name] !== "function") {
          return;
        }
        recorder.originals[name] = proto[name];
        proto[name] = factory(proto[name]);
      };

      wrap("measureText", (original) => function measureTextRecorder(...args) {
        const result = original.apply(this, args);
        pushRecord(this, "measureText", {
          text: String(args[0] ?? ""),
          measuredWidth: result?.width,
          font: this.font || null,
          textAlign: this.textAlign || null,
          textBaseline: this.textBaseline || null,
        });
        return result;
      });

      const wrapText = (name) => {
        wrap(name, (original) => function textRecorder(...args) {
          const text = String(args[0] ?? "");
          let measuredWidth = null;
          const measureTextOriginal = recorder.originals.measureText;
          if (typeof measureTextOriginal === "function") {
            try {
              measuredWidth = measureTextOriginal.call(this, text)?.width ?? null;
            } catch (_error) {
              measuredWidth = null;
            }
          }
          pushRecord(this, name, {
            text,
            x: args[1],
            y: args[2],
            maxWidth: args.length > 3 ? args[3] : null,
            measuredWidth,
            font: this.font || null,
            textAlign: this.textAlign || null,
            textBaseline: this.textBaseline || null,
            fillStyle: this.fillStyle,
            strokeStyle: this.strokeStyle,
            lineWidth: this.lineWidth,
          });
          return original.apply(this, args);
        });
      };

      wrapText("fillText");
      wrapText("strokeText");

      const wrapRect = (name) => {
        wrap(name, (original) => function rectRecorder(...args) {
          pushRecord(this, name, {
            x: args[0],
            y: args[1],
            w: args[2],
            h: args[3],
            radius: name === "roundRect" ? args[4] : null,
            fillStyle: this.fillStyle,
            strokeStyle: this.strokeStyle,
            lineWidth: this.lineWidth,
          });
          return original.apply(this, args);
        });
      };

      wrapRect("fillRect");
      wrapRect("strokeRect");
      wrapRect("rect");
      wrapRect("roundRect");

      window.__vibecomfyCanvas2DRecorder = recorder;
    }

    recorder.canvasId =
      typeof requestedCanvasId === "string" && requestedCanvasId
        ? requestedCanvasId
        : null;
    recorder.enabled = true;
    recorder.sequence = 0;
    recorder.records.length = 0;

    return {
      installed: true,
      enabled: recorder.enabled,
      canvasId: recorder.canvasId,
      maxRecords: recorder.maxRecords,
    };
  }, { canvasId: canvasId ?? null });
}

/**
 * Clear all recorded Canvas2D draw calls.
 *
 * @param {import("@playwright/test").Page} page
 */
export async function clearCanvas2DRecorder(page) {
  await page.evaluate(() => {
    const recorder = window.__vibecomfyCanvas2DRecorder;
    if (recorder?.records) {
      recorder.records.length = 0;
      recorder.sequence = 0;
    }
  });
}

/**
 * Read recorded Canvas2D draw calls from the page.
 *
 * @param {import("@playwright/test").Page} page
 * @param {{ clear?: boolean }} [options]
 * @returns {Promise<{installed: boolean, enabled?: boolean, canvasId?: string|null, recordCount: number, records: Canvas2DRecord[]}>}
 */
export async function readCanvas2DRecorder(page, { clear = false } = {}) {
  return page.evaluate(({ shouldClear }) => {
    const recorder = window.__vibecomfyCanvas2DRecorder;
    if (!recorder || recorder.installed !== true) {
      return {
        installed: false,
        recordCount: 0,
        records: [],
      };
    }
    const records = recorder.records.map((record) => ({
      ...record,
      canvas: record?.canvas ? { ...record.canvas } : null,
    }));
    if (shouldClear) {
      recorder.records.length = 0;
      recorder.sequence = 0;
    }
    return {
      installed: true,
      enabled: recorder.enabled === true,
      canvasId: recorder.canvasId || null,
      recordCount: records.length,
      records,
    };
  }, { shouldClear: clear === true });
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
