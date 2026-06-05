// ── VibeComfy ComfyUI Adapter — Capability Detection & Harness Profiles ───
// M4a: Isolates frontend capability detection into one shared module.
// Consumers import detectCapabilities() and registerExtensionWithCapabilities()
// instead of inlining app.* checks. Existing hook semantics are NOT changed yet.
//
// Backend contract authority: vibecomfy/comfy_nodes/agent_contracts.py.
// Harness profiles describe the shape of the mock app/canvas/graph needed
// for browser tests to match supported / degraded / missing-hook ComfyUI builds.

// ── Supported frontend version ─────────────────────────────────────────────
const SUPPORTED_FRONTEND = "1.39.x";

// ── Capability shape ───────────────────────────────────────────────────────
// Each capability is { available: bool, detail: string, path: string | null }
// where `detail` explains why a capability is missing in degraded profiles.

/**
 * @typedef {Object} Capability
 * @property {boolean} available
 * @property {string} detail
 * @property {string|null} path — the hook/property path checked
 */

/**
 * @typedef {Object} AdapterCapabilities
 * @property {Capability} graphApply — can we clear/configure the live graph?
 * @property {Capability} previewForeground — can we hook canvas.onDrawForeground?
 * @property {Capability} queueGuard — can we wrap app.queuePrompt?
 * @property {string} frontendVersion — detected or reported frontend version
 * @property {string} frontendMajor — supported major version range
 * @property {boolean} supportsAll — convenience: all three capabilities available
 */

// ── Capability detection ───────────────────────────────────────────────────

/**
 * Detect graph-apply capability.
 * Requires live LiteGraph instance with clear() + configure().
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @returns {Capability}
 */
export function detectGraphApply(app) {
  const graph = app?.canvas?.graph;
  if (!graph) {
    return {
      available: false,
      detail: "No live LiteGraph instance on app.canvas.graph.",
      path: "app.canvas.graph",
    };
  }
  const hasClear = typeof graph.clear === "function";
  const hasConfigure = typeof graph.configure === "function";
  if (!hasClear || !hasConfigure) {
    const missing = [];
    if (!hasClear) missing.push("graph.clear");
    if (!hasConfigure) missing.push("graph.configure");
    return {
      available: false,
      detail: `Missing: ${missing.join(", ")}.`,
      path: "app.canvas.graph",
    };
  }
  return {
    available: true,
    detail: "Live graph supports in-place clear + configure.",
    path: "app.canvas.graph",
  };
}

/**
 * Return the live LiteGraph instance when present.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @returns {object|null}
 */
export function getLiveGraph(app) {
  return app?.canvas?.graph || null;
}

/**
 * Repaint the canvas after an in-place graph update.
 * graph.configure() mutates the data model but does not redraw on its own.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @param {object} [graph] — optional live graph reference
 */
export function repaintGraph(app, graph = getLiveGraph(app)) {
  if (typeof graph?.change === "function") graph.change();
  if (typeof graph?.setDirtyCanvas === "function") {
    graph.setDirtyCanvas(true, true);
  } else if (app?.canvas?.setDirty) {
    app.canvas.setDirty(true, true);
  }
  app?.canvas?.draw?.(true, true);
}

/**
 * Apply a candidate graph to the live LiteGraph instance via adapter APIs.
 * Callers can decorate the candidate before configure and re-decorate the live
 * nodes after configure while preserving clear-before-configure behavior.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @param {object} candidate — LiteGraph payload to apply
 * @param {object} [options]
 * @param {(candidate: object, graph: object) => void} [options.beforeConfigure]
 * @param {(graph: object, candidate: object) => void} [options.afterConfigure]
 * @param {boolean} [options.repaint=true]
 * @returns {{ graph: object, capability: Capability }}
 */
export function applyGraphCandidateInPlace(app, candidate, options = {}) {
  const capability = detectGraphApply(app);
  const graph = getLiveGraph(app);
  if (!capability.available || !graph) {
    const error = new Error("The live LiteGraph instance does not support in-place graph application.");
    error.code = "GRAPH_APPLY_UNAVAILABLE";
    error.capability = capability;
    throw error;
  }

  if (typeof options.beforeConfigure === "function") {
    options.beforeConfigure(candidate, graph);
  }
  graph.clear();
  graph.configure(candidate);
  if (typeof options.afterConfigure === "function") {
    options.afterConfigure(graph, candidate);
  }
  if (options.repaint !== false) {
    try {
      repaintGraph(app, graph);
    } catch (error) {
      // Best-effort: the candidate is already applied to the graph data.
      console.warn("[vibecomfy] post-apply canvas redraw failed (data applied):", error);
    }
  }
  return { graph, capability };
}

/**
 * Detect preview-foreground capability.
 * Requires instance-level app.canvas.onDrawForeground or a prototype hook.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @param {object} [windowObj] — globalThis.window (for LiteGraph prototype fallback)
 * @returns {Capability}
 */
export function detectPreviewForeground(app, windowObj) {
  const canvas = app?.canvas;
  if (!canvas) {
    return {
      available: false,
      detail: "No app.canvas instance available.",
      path: "app.canvas.onDrawForeground",
    };
  }

  const instanceFn = canvas.onDrawForeground;
  const hasInstance = typeof instanceFn === "function";

  const win = windowObj || (typeof window !== "undefined" ? window : null);
  const protoFn = win?.LiteGraph?.LGraphCanvas?.prototype?.onDrawForeground;
  const hasProto = typeof protoFn === "function";

  if (hasInstance || hasProto) {
    return {
      available: true,
      detail: hasInstance
        ? "Instance-level app.canvas.onDrawForeground available."
        : "Prototype-level onDrawForeground available (instance will be assigned by build).",
      path: hasInstance ? "app.canvas.onDrawForeground" : "LiteGraph.LGraphCanvas.prototype.onDrawForeground",
    };
  }

  return {
    available: false,
    detail: "No instance-level or prototype-level onDrawForeground hook found.",
    path: "app.canvas.onDrawForeground",
  };
}

/**
 * Install a preview-foreground overlay wrapper using adapter-owned lifecycle
 * hooks. Preferred path: intercept instance-level onDrawForeground assignment
 * so later ComfyUI rebinds stay wrapped without polling. If the property shape
 * cannot be intercepted, fall back to the legacy polling guard and report that
 * degraded mode to the caller.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @param {(ctx: object) => void} overlayDraw — draws the preview overlay
 * @param {object} [options]
 * @param {object} [options.windowObj] — globalThis.window for prototype fallback
 * @param {number} [options.pollIntervalMs=1000] — degraded fallback cadence
 * @returns {{ capability: Capability, strategy: string, polling: boolean, detail: string, cleanup: () => void }}
 */
export function installPreviewForegroundOverlay(app, overlayDraw, options = {}) {
  const capability = detectPreviewForeground(app, options.windowObj);
  if (!capability.available) {
    const error = new Error("No preview foreground hook is available for overlay installation.");
    error.code = "PREVIEW_FOREGROUND_UNAVAILABLE";
    error.capability = capability;
    throw error;
  }

  if (typeof overlayDraw !== "function") {
    throw new TypeError("overlayDraw must be a function");
  }

  const existingInstall = app?.__vibecomfyPreviewForegroundInstall;
  if (existingInstall?.overlayDraw === overlayDraw && typeof existingInstall.cleanup === "function") {
    return existingInstall.report;
  }
  if (typeof existingInstall?.cleanup === "function") {
    existingInstall.cleanup();
  }

  const canvas = app?.canvas;
  const pollIntervalMs = Number.isFinite(options.pollIntervalMs) && options.pollIntervalMs > 0
    ? options.pollIntervalMs
    : 1000;
  const win = options.windowObj || (typeof window !== "undefined" ? window : null);
  const protoFn = win?.LiteGraph?.LGraphCanvas?.prototype?.onDrawForeground;
  const initialDelegate = typeof canvas?.onDrawForeground === "function" ? canvas.onDrawForeground : null;

  let delegate = initialDelegate;
  const wrapper = function vibecomfyPreviewForegroundWrapper(ctx, ...args) {
    try {
      if (typeof delegate === "function" && delegate !== wrapper) {
        delegate.call(this, ctx, ...args);
      } else if (typeof protoFn === "function") {
        protoFn.call(this, ctx, ...args);
      }
    } catch (error) {
      console.warn("[vibecomfy] original onDrawForeground threw:", error);
    }
    overlayDraw.call(this, ctx);
  };
  wrapper.__vibecomfyOverlayWrapper = true;

  const installState = {
    overlayDraw,
    cleanup() {},
    report: null,
  };

  const ownDescriptor = canvas ? Object.getOwnPropertyDescriptor(canvas, "onDrawForeground") : null;
  const canInterceptProperty = !!canvas && (!ownDescriptor || ownDescriptor.configurable !== false);
  if (canInterceptProperty) {
    try {
      Object.defineProperty(canvas, "onDrawForeground", {
        configurable: true,
        enumerable: ownDescriptor ? ownDescriptor.enumerable !== false : true,
        get() {
          return wrapper;
        },
        set(nextValue) {
          delegate = typeof nextValue === "function" && nextValue !== wrapper ? nextValue : null;
        },
      });
      delegate = initialDelegate;
      const cleanup = () => {
        if (ownDescriptor) {
          Object.defineProperty(canvas, "onDrawForeground", ownDescriptor);
        } else {
          delete canvas.onDrawForeground;
        }
        if (app?.__vibecomfyPreviewForegroundInstall === installState) {
          delete app.__vibecomfyPreviewForegroundInstall;
        }
      };
      const report = {
        capability,
        strategy: "property-interceptor",
        polling: false,
        detail: "Installed an adapter-owned onDrawForeground interceptor on app.canvas.",
        cleanup,
      };
      installState.cleanup = cleanup;
      installState.report = report;
      app.__vibecomfyPreviewForegroundInstall = installState;
      return report;
    } catch (_error) {
      // Fall through to the reported polling fallback below.
    }
  }

  const ensurePatched = function ensurePreviewForegroundPatched() {
    const liveCanvas = app?.canvas;
    if (!liveCanvas) {
      return;
    }
    const current = liveCanvas.onDrawForeground;
    if (current && current.__vibecomfyOverlayWrapper) {
      return;
    }
    delegate = typeof current === "function" ? current : null;
    liveCanvas.onDrawForeground = wrapper;
  };
  ensurePatched();
  const intervalId = setInterval(ensurePatched, pollIntervalMs);
  const cleanup = () => {
    clearInterval(intervalId);
    if (app?.__vibecomfyPreviewForegroundInstall === installState) {
      delete app.__vibecomfyPreviewForegroundInstall;
    }
  };
  const report = {
    capability,
    strategy: "polling-fallback",
    polling: true,
    detail: "Fell back to polling because app.canvas.onDrawForeground could not be intercepted directly.",
    cleanup,
  };
  installState.cleanup = cleanup;
  installState.report = report;
  app.__vibecomfyPreviewForegroundInstall = installState;
  return report;
}

/**
 * Detect queue-guard capability.
 * Requires app.queuePrompt to be a function we can wrap.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @returns {Capability}
 */
export function detectQueueGuard(app) {
  if (!app) {
    return {
      available: false,
      detail: "No app global available.",
      path: "app.queuePrompt",
    };
  }
  if (typeof app.queuePrompt !== "function") {
    return {
      available: false,
      detail: "app.queuePrompt is not a function (queue guard unavailable).",
      path: "app.queuePrompt",
    };
  }
  return {
    available: true,
    detail: "app.queuePrompt is interceptable.",
    path: "app.queuePrompt",
  };
}

/**
 * Install a queue guard wrapper on app.queuePrompt using an adapter-owned
 * strategy. The wrapper calls through to the original unless the caller-supplied
 * `shouldBlock` callback returns a truthy block-info object, in which case the
 * wrapper returns null and delegates to the `onBlock` callback.
 *
 * When app.queuePrompt is not a function the returned report records the
 * degraded state; the caller is responsible for surfacing the missing-hook
 * fallback warning in the panel.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @param {object} [options]
 * @param {() => object|null} [options.shouldBlock] — return block-info when the
 *   current turn context should prevent queueing, or null to allow pass-through.
 * @param {(blockInfo: object) => void} [options.onBlock] — called when a queue
 *   prompt is blocked so the caller can record block notices and update the panel.
 * @returns {{
 *   capability: Capability,
 *   strategy: string,
 *   installed: boolean,
 *   path: string,
 *   original: Function|null,
 *   wrapper: Function|null,
 *   cleanup: () => void
 * }}
 */
export function installQueueGuard(app, options = {}) {
  const capability = detectQueueGuard(app);
  if (!capability.available) {
    return {
      capability,
      strategy: "unavailable",
      installed: false,
      path: "app.queuePrompt",
      original: null,
      wrapper: null,
      cleanup() {},
    };
  }

  const original = app.queuePrompt;
  const shouldBlock = typeof options.shouldBlock === "function" ? options.shouldBlock : null;
  const onBlock = typeof options.onBlock === "function" ? options.onBlock : null;

  const wrapper = function guardedQueuePrompt(...args) {
    if (shouldBlock) {
      const blockInfo = shouldBlock();
      if (blockInfo) {
        if (onBlock) {
          try {
            onBlock(blockInfo);
          } catch (_err) {
            // Best-effort: block notice recording is advisory.
          }
        }
        return null;
      }
    }
    return original.apply(this, args);
  };

  // Safe-install: verify the property is writable before replacing.
  try {
    app.queuePrompt = wrapper;
    app.queuePrompt = original;
  } catch (_error) {
    // Property is not writable; return degraded.
    return {
      capability: {
        available: false,
        detail: `app.queuePrompt is not safely writable: ${_error?.message || String(_error)}`,
        path: "app.queuePrompt",
      },
      strategy: "unavailable",
      installed: false,
      path: "app.queuePrompt",
      original,
      wrapper: null,
      cleanup() {},
    };
  }

  app.queuePrompt = wrapper;

  const cleanup = () => {
    if (app.queuePrompt === wrapper) {
      app.queuePrompt = original;
    }
  };

  return {
    capability,
    strategy: "wrapper",
    installed: true,
    path: "app.queuePrompt",
    original,
    wrapper,
    cleanup,
  };
}

/**
 * Run all capability detections and return a unified view.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @param {object} [windowObj] — globalThis.window for LiteGraph prototype fallback
 * @param {string} [frontendVersion] — version reported by /system_stats or similar
 * @returns {AdapterCapabilities}
 */
export function detectCapabilities(app, windowObj, frontendVersion) {
  const graphApply = detectGraphApply(app);
  const previewForeground = detectPreviewForeground(app, windowObj);
  const queueGuard = detectQueueGuard(app);

  const version = String(frontendVersion || "unknown").trim() || "unknown";
  const major = SUPPORTED_FRONTEND.split(".").slice(0, 2).join(".");

  return {
    graphApply,
    previewForeground,
    queueGuard,
    frontendVersion: version,
    frontendMajor: major,
    supportsAll: graphApply.available && previewForeground.available && queueGuard.available,
  };
}

// ── Extension registration with observability ──────────────────────────────

/**
 * Register a ComfyUI extension and report capability state to the console.
 * This wraps app.registerExtension() so every install logs what hooks are
 * available and any degradation warnings.
 *
 * SD2: registerExtension is treated as an entrypoint wrapper for observability,
 * not as a hook family alongside graph/canvas/queue hooks.
 *
 * @param {object} app — the ComfyUI app global
 * @param {object} extension — the extension definition (name, setup, etc.)
 * @param {object} [options]
 * @param {object} [options.capabilities] — pre-computed capabilities (avoids re-detection)
 * @param {boolean} [options.silent] — suppress console reporting
 * @returns {object} the capabilities snapshot used during registration
 */
export function registerExtensionWithCapabilities(app, extension, options = {}) {
  let capabilities = options.capabilities || detectCapabilities(app);

  // Normalize: if caller passed a raw profile capabilities object (just the
  // three hook checks without supportsAll / frontendVersion), fill in defaults.
  if (capabilities && typeof capabilities.supportsAll !== "boolean") {
    const ga = capabilities.graphApply?.available === true;
    const pf = capabilities.previewForeground?.available === true;
    const qg = capabilities.queueGuard?.available === true;
    capabilities = {
      graphApply: capabilities.graphApply || { available: false, detail: "not detected", path: null },
      previewForeground: capabilities.previewForeground || { available: false, detail: "not detected", path: null },
      queueGuard: capabilities.queueGuard || { available: false, detail: "not detected", path: null },
      frontendVersion: capabilities.frontendVersion || "unknown",
      frontendMajor: capabilities.frontendMajor || "1.39",
      supportsAll: ga && pf && qg,
    };
  }

  if (!options.silent) {
    const name = extension?.name || "unknown";
    const tag = `[vibecomfy:adapter] ${name}`;

    if (capabilities.supportsAll) {
      console.log(
        `${tag} installed on ComfyUI ${capabilities.frontendVersion} — ` +
        `all hooks available (graphApply, previewForeground, queueGuard).`,
      );
    } else {
      const missing = [];
      if (!capabilities.graphApply.available) missing.push(`graphApply: ${capabilities.graphApply.detail}`);
      if (!capabilities.previewForeground.available) missing.push(`previewForeground: ${capabilities.previewForeground.detail}`);
      if (!capabilities.queueGuard.available) missing.push(`queueGuard: ${capabilities.queueGuard.detail}`);

      console.warn(
        `${tag} installed on ComfyUI ${capabilities.frontendVersion} — ` +
        `DEGRADED. Missing capabilities:\n  ${missing.join("\n  ")}`,
      );
    }
  }

  // Store capabilities on the extension object for later introspection.
  if (extension && typeof extension === "object") {
    extension.__vibecomfyCapabilities = capabilities;
  }

  // Forward to the actual app.registerExtension.
  if (typeof app?.registerExtension === "function") {
    app.registerExtension(extension);
  }

  return capabilities;
}

// ── Harness profiles ───────────────────────────────────────────────────────
// These describe the mocked app/canvas/graph shape needed by the browser
// harness (tests/browser/harness.mjs) to simulate different ComfyUI builds.
// Harness authors use them as templates when constructing mock apps.

/**
 * Supported 1.39.x harness profile.
 *
 * Shape: app.canvas.graph with clear/configure, app.canvas.onDrawForeground
 * (instance-level, assignable), and app.queuePrompt (wrappable).
 *
 * Use this profile for the primary smoke-test build.
 */
export const HARNESS_PROFILE_SUPPORTED_139_X = Object.freeze({
  name: "supported-1.39.x",
  frontendVersion: "1.39.19",
  description:
    "Full 1.39.x ComfyUI build with graph clear/configure, " +
    "instance canvas.onDrawForeground, and app.queuePrompt.",
  capabilities: {
    graphApply: { available: true, detail: "graph.clear + graph.configure present", path: "app.canvas.graph" },
    previewForeground: { available: true, detail: "Instance canvas.onDrawForeground assignable", path: "app.canvas.onDrawForeground" },
    queueGuard: { available: true, detail: "app.queuePrompt is wrappable", path: "app.queuePrompt" },
  },
});

/**
 * Degraded / missing-hook harness profile.
 *
 * Shape: app.canvas.graph exists BUT one or more hooks are absent.
 * This simulates older ComfyUI builds or custom forks where the expected
 * API surface is incomplete.
 *
 * Variants:
 * - "missing-graph-apply": no graph.clear / graph.configure
 * - "missing-preview-foreground": no canvas.onDrawForeground at all
 * - "missing-queue-guard": no app.queuePrompt
 * - "missing-all": all three hooks absent
 */
export const HARNESS_PROFILE_DEGRADED = Object.freeze({
  name: "degraded-missing-hook",
  frontendVersion: "1.37.0",
  description:
    "Degraded ComfyUI build where one or more integration hooks are absent.",
  // Variant keys; harnesses pick one and configure the mock accordingly.
  variants: Object.freeze({
    "missing-graph-apply": {
      capabilities: {
        graphApply: { available: false, detail: "graph.clear + graph.configure missing", path: "app.canvas.graph" },
        previewForeground: { available: true, detail: "Instance canvas.onDrawForeground assignable", path: "app.canvas.onDrawForeground" },
        queueGuard: { available: true, detail: "app.queuePrompt is wrappable", path: "app.queuePrompt" },
      },
    },
    "missing-preview-foreground": {
      capabilities: {
        graphApply: { available: true, detail: "graph.clear + graph.configure present", path: "app.canvas.graph" },
        previewForeground: { available: false, detail: "No onDrawForeground hook found", path: "app.canvas.onDrawForeground" },
        queueGuard: { available: true, detail: "app.queuePrompt is wrappable", path: "app.queuePrompt" },
      },
    },
    "missing-queue-guard": {
      capabilities: {
        graphApply: { available: true, detail: "graph.clear + graph.configure present", path: "app.canvas.graph" },
        previewForeground: { available: true, detail: "Instance canvas.onDrawForeground assignable", path: "app.canvas.onDrawForeground" },
        queueGuard: { available: false, detail: "app.queuePrompt not a function", path: "app.queuePrompt" },
      },
    },
    "missing-all": {
      capabilities: {
        graphApply: { available: false, detail: "No live graph instance", path: "app.canvas.graph" },
        previewForeground: { available: false, detail: "No onDrawForeground hook found", path: "app.canvas.onDrawForeground" },
        queueGuard: { available: false, detail: "app.queuePrompt not a function", path: "app.queuePrompt" },
      },
    },
  }),
});

/**
 * Build a mock app from a harness profile and optional variant.
 * Returns { app, window } suitable for use with the browser harness.
 *
 * @param {object} profile — one of the HARNESS_PROFILE_* exports
 * @param {string} [variantKey] — variant key from HARNESS_PROFILE_DEGRADED.variants
 * @returns {{ app: object, window: object, capabilities: AdapterCapabilities }}
 */
export function buildMockAppFromProfile(profile, variantKey) {
  let capabilities;
  if (variantKey && profile?.variants?.[variantKey]) {
    capabilities = profile.variants[variantKey].capabilities;
  } else if (profile?.capabilities) {
    capabilities = profile.capabilities;
  } else {
    capabilities = profile?.variants?.["missing-all"]?.capabilities || {
      graphApply: { available: false, detail: "Unknown profile", path: null },
      previewForeground: { available: false, detail: "Unknown profile", path: null },
      queueGuard: { available: false, detail: "Unknown profile", path: null },
    };
  }

  const graph = {};

  if (capabilities.graphApply.available) {
    graph._nodes = [];
    graph.clear = function clear() { this._nodes = []; };
    graph.configure = function configure(data) { /* noop in mock */ };
  }

  const app = {
    canvas: {
      graph,
    },
  };

  if (capabilities.previewForeground.available) {
    // Instance-level hook — set to a function so capability detection
    // sees typeof === 'function'.
    app.canvas.onDrawForeground = function onDrawForeground(_ctx) { /* mock */ };
  }
  // For degraded preview, we simply omit onDrawForeground entirely.

  if (capabilities.queueGuard.available) {
    app.queuePrompt = function queuePrompt() {
      return { queued: true };
    };
  }
  // For degraded queue guard, we omit app.queuePrompt.

  const LiteGraphCanvas = function LiteGraphCanvas() {};

  const windowObj = {
    LiteGraph: { LGraphCanvas: LiteGraphCanvas },
  };

  return { app, window: windowObj, capabilities };
}
