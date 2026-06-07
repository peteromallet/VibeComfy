import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const EXTENSION_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "vibecomfy_roundtrip.js");
const LIFECYCLE_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agent_edit_lifecycle.js");
const ADAPTER_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "comfy_adapter.js");
const RESPONSE_CONTRACT_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agent_edit_response_contract.js");

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

// ── Mock canvas context with draw-operation capture (T5) ──────────────────
export function createMockCanvasContext() {
  const operations = [];
  let _strokeStyle = "#000000";
  let _fillStyle = "#000000";
  let _lineWidth = 1;
  let _font = "12px Arial, sans-serif";
  let _textBaseline = "alphabetic";
  let _textAlign = "start";
  let _lineDash = [];
  let _saveDepth = 0;

  function _op(kind, ...args) {
    operations.push({ kind, args });
  }

  const ctx = {
    _getOperations() { return operations; },
    _reset() { operations.length = 0; },

    save() { _saveDepth += 1; _op("save"); },
    restore() { _saveDepth = Math.max(0, _saveDepth - 1); _op("restore"); },

    get strokeStyle() { return _strokeStyle; },
    set strokeStyle(v) { _strokeStyle = String(v || "#000000"); _op("strokeStyle", _strokeStyle); },

    get fillStyle() { return _fillStyle; },
    set fillStyle(v) { _fillStyle = String(v || "#000000"); _op("fillStyle", _fillStyle); },

    get lineWidth() { return _lineWidth; },
    set lineWidth(v) { _lineWidth = Number(v) || 1; _op("lineWidth", _lineWidth); },

    get font() { return _font; },
    set font(v) { _font = String(v || ""); _op("font", _font); },

    get textBaseline() { return _textBaseline; },
    set textBaseline(v) { _textBaseline = String(v || "alphabetic"); _op("textBaseline", _textBaseline); },

    get textAlign() { return _textAlign; },
    set textAlign(v) { _textAlign = String(v || "start"); _op("textAlign", _textAlign); },

    setLineDash(arr) { _lineDash = Array.isArray(arr) ? [...arr] : []; _op("setLineDash", _lineDash); },

    beginPath() { _op("beginPath"); },
    rect(x, y, w, h) { _op("rect", Number(x) || 0, Number(y) || 0, Number(w) || 0, Number(h) || 0); },
    roundRect(x, y, w, h, r) { _op("roundRect", Number(x) || 0, Number(y) || 0, Number(w) || 0, Number(h) || 0, Number(r) || 0); },
    moveTo(x, y) { _op("moveTo", Number(x) || 0, Number(y) || 0); },
    bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x, y) {
      _op("bezierCurveTo", Number(cp1x) || 0, Number(cp1y) || 0, Number(cp2x) || 0, Number(cp2y) || 0, Number(x) || 0, Number(y) || 0);
    },
    clip() { _op("clip"); },
    stroke() { _op("stroke"); },
    fill() { _op("fill"); },
    fillText(text, x, y) { _op("fillText", String(text || ""), Number(x) || 0, Number(y) || 0); },
    strokeRect(x, y, w, h) { _op("strokeRect", Number(x) || 0, Number(y) || 0, Number(w) || 0, Number(h) || 0); },
    fillRect(x, y, w, h) { _op("fillRect", Number(x) || 0, Number(y) || 0, Number(w) || 0, Number(h) || 0); },
    arc(x, y, r, startAngle, endAngle) {
      _op("arc", Number(x) || 0, Number(y) || 0, Number(r) || 0, Number(startAngle) || 0, Number(endAngle) || 0);
    },

    measureText(text) {
      _op("measureText", String(text || ""));
      return { width: String(text || "").length * 6.5 };
    },
  };

  return ctx;
}

class FakeElement {
  constructor(ownerDocument, tagName) {
    this.ownerDocument = ownerDocument;
    this.tagName = String(tagName).toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.style = {};
    this.dataset = {};
    this.attributes = {};
    this.title = "";
    this.placeholder = "";
    this.value = "";
    this.disabled = false;
    this.onclick = null;
    this.textContent = "";
    this.id = "";
    this.eventListeners = {};
  }

  get isConnected() {
    if (this === this.ownerDocument.body || this === this.ownerDocument.head) {
      return true;
    }
    return Boolean(this.parentNode?.isConnected);
  }

  appendChild(child) {
    if (child.parentNode && child.parentNode !== this) {
      child.parentNode.removeChild(child);
    } else if (child.parentNode === this) {
      this.removeChild(child);
    }
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  removeChild(child) {
    const index = this.children.indexOf(child);
    if (index >= 0) {
      this.children.splice(index, 1);
      child.parentNode = null;
    }
    return child;
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.removeChild(this);
    }
  }

  focus() {
    this.ownerDocument.activeElement = this;
  }

  addEventListener(type, listener) {
    if (!this.eventListeners[type]) {
      this.eventListeners[type] = [];
    }
    this.eventListeners[type].push(listener);
  }

  removeEventListener(type, listener) {
    const listeners = this.eventListeners[type] || [];
    this.eventListeners[type] = listeners.filter((entry) => entry !== listener);
  }

  click() {
    if (this.disabled) {
      return undefined;
    }
    const listeners = this.eventListeners.click || [];
    for (const listener of listeners) {
      listener.call(this, { type: "click", target: this });
    }
    if (typeof this.onclick === "function") {
      return this.onclick();
    }
    return undefined;
  }

  _matchesSelector(selector) {
    if (typeof selector !== "string") {
      return false;
    }
    const trimmed = selector.trim();
    if (!trimmed) {
      return false;
    }
    if (trimmed.startsWith("#")) {
      return this.id === trimmed.slice(1);
    }
    if (trimmed.startsWith(".")) {
      const className = String(this.attributes.class || this.className || "");
      return className.split(/\s+/).includes(trimmed.slice(1));
    }
    const attrMatch = trimmed.match(/^\[([^=\]]+)(?:=(["']?)(.*?)\2)?\]$/);
    if (attrMatch) {
      const name = attrMatch[1];
      const expected = attrMatch[3];
      const actual = name.startsWith("data-")
        ? this.dataset[name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())]
        : this.attributes[name];
      return expected === undefined ? actual !== undefined : String(actual) === expected;
    }
    return this.tagName === trimmed.toUpperCase();
  }

  querySelectorAll(predicate) {
    const matcher = typeof predicate === "function"
      ? predicate
      : (node) => node?._matchesSelector?.(predicate);
    const matches = [];
    const visit = (node) => {
      if (matcher(node)) {
        matches.push(node);
      }
      for (const child of node.children) {
        visit(child);
      }
    };
    visit(this);
    return matches;
  }
}

class FakeDocument {
  constructor() {
    this.head = new FakeElement(this, "head");
    this.body = new FakeElement(this, "body");
  }

  createElement(tagName) {
    return new FakeElement(this, tagName);
  }

  getElementById(id) {
    return this.body.querySelectorAll((node) => node.id === id)[0] || null;
  }
}

function makeResponse(status, body) {
  let normalizedBody = clone(body);
  if (
    normalizedBody
    && typeof normalizedBody === "object"
    && !Array.isArray(normalizedBody)
    && "route_options" in normalizedBody
    && !("ready" in normalizedBody)
  ) {
    normalizedBody.ready = true;
  }
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return clone(normalizedBody);
    },
    async text() {
      return JSON.stringify(normalizedBody);
    },
  };
}

export async function createBrowserHarness({
  graph,
  responses = {},
  withQueuePrompt = true,
} = {}) {
  const document = new FakeDocument();
  const requests = [];
  const operationLog = [];
  const consoleCapture = { log: [], warn: [], error: [] };
  const loadGraphDataCalls = [];
  const graphClearCalls = [];
  const graphConfigureCalls = [];
  const graphChangeCalls = [];
  const graphDirtyCanvasCalls = [];
  const canvasDrawCalls = [];
  const queuePromptCalls = [];
  const serializeCalls = [];
  const toasts = [];
  const registeredExtensions = [];
  const registeredSidebarTabs = [];
  let liveCanvasRevision = 1;
  let currentGraph = clone(
    graph || {
      nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
      links: [],
    },
  );

  var TITLE_H = (globalThis.window?.LiteGraph?.NODE_TITLE_HEIGHT) || 30;
  var SLOT_H = (globalThis.window?.LiteGraph?.NODE_SLOT_HEIGHT) || 20;

  function _buildLiveLinkMap(linksArray) {
    var map = {};
    if (Array.isArray(linksArray)) {
      for (var _li = 0; _li < linksArray.length; _li += 1) {
        var link = linksArray[_li];
        if (Array.isArray(link)) {
          map[_li] = link;
        } else if (link && typeof link === 'object') {
          map[_li] = link;
        }
      }
    }
    return map;
  }

  function syncLiveGraphNodes() {
    app.canvas.graph._vibecomfyLiveCanvasToken = `rev:${liveCanvasRevision}`;
    app.canvas.graph.links = _buildLiveLinkMap(currentGraph?.links);
    app.canvas.graph._nodes = (currentGraph?.nodes || []).map((node) => ({
      id: node.id,
      type: node.type,
      properties: clone(node.properties || {}),
      inputs: clone(node.inputs || []),
      outputs: clone(node.outputs || []),
      pos: Array.isArray(node.pos) ? [...node.pos] : [0, 0],
      size: Array.isArray(node.size) ? [...node.size] : [200, 100],
      getConnectionPos(isInput, slotIndex) {
        var nx = (Array.isArray(node.pos) ? node.pos[0] : 0) || 0;
        var ny = (Array.isArray(node.pos) ? node.pos[1] : 0) || 0;
        var nw = Array.isArray(node.size) ? (node.size[0] || 200) : 200;
        if (isInput) return [nx, ny + TITLE_H + slotIndex * SLOT_H + SLOT_H / 2];
        return [nx + nw, ny + TITLE_H + slotIndex * SLOT_H + SLOT_H / 2];
      },
    }));
  }

  const app = {
    canvas: {
      // Instance-level onDrawForeground — ComfyUI 1.39.x assigns a function
      // at build time. Capability detection checks typeof === 'function'.
      onDrawForeground: function onDrawForeground(_ctx) { /* ComfyUI default */ },
      graph: {
        serialize() {
          const snapshot = clone(currentGraph);
          serializeCalls.push(snapshot);
          return snapshot;
        },
        _nodes: [],
        clear() {
          graphClearCalls.push(clone(currentGraph));
          operationLog.push({ kind: "graph.clear" });
          liveCanvasRevision += 1;
          currentGraph = { nodes: [], links: [] };
          syncLiveGraphNodes();
        },
        configure(nextGraph) {
          const snapshot = clone(nextGraph);
          graphConfigureCalls.push(snapshot);
          operationLog.push({ kind: "graph.configure", graph: snapshot });
          liveCanvasRevision += 1;
          currentGraph = snapshot;
          syncLiveGraphNodes();
        },
        change() {
          graphChangeCalls.push(clone(currentGraph));
          operationLog.push({ kind: "graph.change" });
        },
        setDirtyCanvas(fg, bg) {
          graphDirtyCanvasCalls.push([fg, bg]);
          operationLog.push({ kind: "graph.setDirtyCanvas", fg, bg });
        },
      },
      draw(fg, bg) {
        canvasDrawCalls.push([fg, bg]);
        operationLog.push({ kind: "canvas.draw", fg, bg });
      },
    },
    extensionManager: {
      toast: {
        add(entry) {
          toasts.push(clone(entry));
        },
      },
      registerSidebarTab(...args) {
        registeredSidebarTabs.push(args);
        operationLog.push({ kind: "extensionManager.registerSidebarTab", args: args.map((arg) => typeof arg) });
      },
    },
    registerExtension(extension) {
      registeredExtensions.push(extension);
    },
    loadGraphData(nextGraph) {
      const snapshot = clone(nextGraph);
      loadGraphDataCalls.push(snapshot);
      operationLog.push({ kind: "loadGraphData", graph: snapshot });
      liveCanvasRevision += 1;
      currentGraph = snapshot;
      syncLiveGraphNodes();
    },
  };
  if (withQueuePrompt) {
    app.queuePrompt = (...args) => {
      queuePromptCalls.push(args);
      return { queued: true, args: clone(args) };
    };
  }
  syncLiveGraphNodes();

  const LiteGraphCanvas = function LiteGraphCanvas() {};
  LiteGraphCanvas.prototype.getCanvasMenuOptions = function getCanvasMenuOptions() {
    return [{ content: "Original", callback: () => null }];
  };

  const fetchImpl = async (url, options = {}) => {
    const key = String(url);
    requests.push({
      url: key,
      method: options.method || "GET",
      headers: clone(options.headers || {}),
      body: options.body,
    });
    operationLog.push({ kind: "request", url: key, method: options.method || "GET" });
    const entry = responses[key];
    if (entry instanceof Error) {
      throw entry;
    }
    if (entry == null) {
      operationLog.push({ kind: "response", url: key, status: 404 });
      return makeResponse(404, { error: `No mock for ${key}` });
    }
    if (options.signal?.aborted) {
      const abortError = new Error("The operation was aborted.");
      abortError.name = "AbortError";
      throw abortError;
    }
    const withAbort = (promise) => new Promise((resolve, reject) => {
      let settled = false;
      const cleanup = () => {
        if (options.signal) {
          options.signal.removeEventListener("abort", onAbort);
        }
      };
      const onAbort = () => {
        if (settled) {
          return;
        }
        settled = true;
        cleanup();
        const abortError = new Error("The operation was aborted.");
        abortError.name = "AbortError";
        reject(abortError);
      };
      if (options.signal) {
        options.signal.addEventListener("abort", onAbort);
      }
      Promise.resolve(promise).then((value) => {
        if (settled) {
          return;
        }
        settled = true;
        cleanup();
        resolve(value);
      }, (error) => {
        if (settled) {
          return;
        }
        settled = true;
        cleanup();
        reject(error);
      });
    });
    if (typeof entry === "function") {
      const value = await withAbort(entry({
        url: key,
        options: { ...clone(options), signal: options.signal },
      }));
      operationLog.push({ kind: "response", url: key, status: value.status || 200 });
      return makeResponse(value.status || 200, value.body);
    }
    operationLog.push({ kind: "response", url: key, status: entry.status || 200 });
    return makeResponse(entry.status || 200, entry.body);
  };

  const tempRoot = await mkdtemp(path.join(os.tmpdir(), "vibecomfy-browser-"));
  const comfyRoot = path.join(tempRoot, "comfy");
  const webRoot = path.join(comfyRoot, "custom_nodes", "web");
  const scriptsRoot = path.join(comfyRoot, "scripts");
  await mkdir(webRoot, { recursive: true });
  await mkdir(scriptsRoot, { recursive: true });
  await writeFile(path.join(comfyRoot, "package.json"), '{ "type": "module" }\n');
  await writeFile(path.join(scriptsRoot, "app.js"), "export const app = globalThis.__VIBECOMFY_BROWSER_APP__;\n");
  await writeFile(path.join(scriptsRoot, "api.js"), "export const api = globalThis.__VIBECOMFY_BROWSER_API__;\n");
  await writeFile(path.join(webRoot, "vibecomfy_roundtrip.js"), await readFile(EXTENSION_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agent_edit_lifecycle.js"), await readFile(LIFECYCLE_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "comfy_adapter.js"), await readFile(ADAPTER_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agent_edit_response_contract.js"), await readFile(RESPONSE_CONTRACT_SOURCE, "utf8"));

  const apiEventListeners = {};
  const mockApi = {
    clientId: `test-client-${Date.now()}`,
    addEventListener(event, listener) {
      if (!apiEventListeners[event]) {
        apiEventListeners[event] = [];
      }
      apiEventListeners[event].push(listener);
    },
    removeEventListener(event, listener) {
      const listeners = apiEventListeners[event] || [];
      apiEventListeners[event] = listeners.filter((entry) => entry !== listener);
    },
  };

  function dispatchApiEvent(event, data) {
    const listeners = apiEventListeners[event] || [];
    const detail = data != null ? { detail: data } : {};
    for (const listener of listeners) {
      try {
        listener(detail);
      } catch (_err) {
        // Best-effort: event listener errors must not break dispatch.
      }
    }
  }

  const originalDocument = globalThis.document;
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  const originalConsole = globalThis.console;
  const originalURL = globalThis.URL;
  const originalRequestAnimationFrame = globalThis.requestAnimationFrame;
  const originalCancelAnimationFrame = globalThis.cancelAnimationFrame;
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  const originalApp = globalThis.__VIBECOMFY_BROWSER_APP__;
  const originalApi = globalThis.__VIBECOMFY_BROWSER_API__;
  const hadCrypto = "crypto" in globalThis;

  const blobUrls = [];
  globalThis.URL = {
    createObjectURL(_blob) {
      const url = `blob:mock-${blobUrls.length}`;
      blobUrls.push(url);
      return url;
    },
    revokeObjectURL(url) {
      const idx = blobUrls.indexOf(url);
      if (idx >= 0) {
        blobUrls.splice(idx, 1);
      }
    },
  };

  globalThis.document = document;
  globalThis.window = { document, LiteGraph: { LGraphCanvas: LiteGraphCanvas } };
  globalThis.fetch = fetchImpl;
  globalThis.__VIBECOMFY_BROWSER_APP__ = app;
  globalThis.__VIBECOMFY_BROWSER_API__ = mockApi;
  if (!hadCrypto) {
    globalThis.crypto = (await import("node:crypto")).webcrypto;
  }
  // ── localStorage fake (used by frontend session persistence) ─────────
  const _localStorageStore = new Map();
  globalThis.localStorage = {
    getItem(key) {
      const val = _localStorageStore.get(String(key));
      return val === undefined ? null : val;
    },
    setItem(key, value) {
      _localStorageStore.set(String(key), String(value));
    },
    removeItem(key) {
      _localStorageStore.delete(String(key));
    },
    clear() {
      _localStorageStore.clear();
    },
    get length() {
      return _localStorageStore.size;
    },
    key(index) {
      const keys = [..._localStorageStore.keys()];
      return keys[index] || null;
    },
    // Expose store for test assertions.
    _dump() {
      return Object.fromEntries(_localStorageStore);
    },
  };
  globalThis.console = {
    ...originalConsole,
    log: (...args) => consoleCapture.log.push(args.map(String).join(" ")),
    warn: (...args) => consoleCapture.warn.push(args.map(String).join(" ")),
    error: (...args) => consoleCapture.error.push(args.map(String).join(" ")),
  };

  let importedModule = null;

  async function loadExtension() {
    if (importedModule) {
      return importedModule;
    }
    const target = pathToFileURL(path.join(webRoot, "vibecomfy_roundtrip.js")).href;
    importedModule = await import(`${target}?t=${Date.now()}`);
    return importedModule;
  }

  function getExtension() {
    assert.equal(registeredExtensions.length, 1, "expected one registered extension");
    return registeredExtensions[0];
  }

  function findButtons(label) {
    return document.body.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.textContent === label,
    );
  }

  return {
    app,
    api: mockApi,
    apiEventListeners,
    dispatchApiEvent,
    document,
    window: globalThis.window,
    requests,
    operationLog,
    consoleCapture,
    loadGraphDataCalls,
    graphClearCalls,
    graphConfigureCalls,
    graphChangeCalls,
    graphDirtyCanvasCalls,
    canvasDrawCalls,
    queuePromptCalls,
    serializeCalls,
    toasts,
    registeredExtensions,
    registeredSidebarTabs,
    async loadExtension() {
      return loadExtension();
    },
    async loadFreshExtension() {
      const target = pathToFileURL(path.join(webRoot, "vibecomfy_roundtrip.js")).href;
      return import(`${target}?fresh=${Date.now()}-${Math.random()}`);
    },
    async loadAdapter() {
      const target = pathToFileURL(path.join(webRoot, "comfy_adapter.js")).href;
      return import(`${target}?t=${Date.now()}`);
    },
    async setup() {
      const extension = getExtension();
      if (typeof extension.setup === "function") {
        await extension.setup();
      }
      return extension;
    },
    getExtension,
    getMenuCommands() {
      return getExtension().menuCommands || [];
    },
    getSidebarTabs() {
      return registeredSidebarTabs;
    },
    getCommands() {
      return getExtension().commands || [];
    },
    async invokeCommand(id) {
      const command = this.getCommands().find((entry) => entry.id === id);
      assert(command, `missing command ${id}`);
      return command.function();
    },
    findButtons(label) {
      return findButtons(label);
    },
    getButton(label) {
      return findButtons(label)[0] || null;
    },
    clickButton(label) {
      const button = findButtons(label)[0];
      assert(button, `missing button ${label}`);
      return button.click();
    },
    getPanelRoots() {
      return document.body.querySelectorAll(
        (node) => node.dataset?.vibecomfyPanelRoot === "1",
      );
    },
    getCanvasMenuOptions() {
      const canvas = new LiteGraphCanvas();
      return canvas.getCanvasMenuOptions();
    },
    textDump() {
      return document.body.querySelectorAll(() => true).map((node) => node.textContent).join("\n");
    },
    setCurrentGraph(nextGraph) {
      liveCanvasRevision += 1;
      currentGraph = clone(nextGraph);
      syncLiveGraphNodes();
    },
    setCurrentGraphWithoutRevisionBump(nextGraph) {
      currentGraph = clone(nextGraph);
      syncLiveGraphNodes();
    },
    bumpLiveCanvasToken() {
      liveCanvasRevision += 1;
      syncLiveGraphNodes();
    },
    getCurrentGraph() {
      return clone(currentGraph);
    },
    async drawPreviewOverlay(diff) {
      const mod = await loadExtension();
      const ctx = createMockCanvasContext();
      try {
        mod.drawPreviewOverlay(ctx, diff);
      } catch (e) {
        consoleCapture.warn.push(`[harness] drawPreviewOverlay threw: ${e}`);
      }
      return ctx._getOperations();
    },
    getLiveNodes() {
      return app.canvas.graph._nodes;
    },
    async dispose() {
      if (originalDocument === undefined) delete globalThis.document;
      else globalThis.document = originalDocument;
      if (originalWindow === undefined) delete globalThis.window;
      else globalThis.window = originalWindow;
      if (originalFetch === undefined) delete globalThis.fetch;
      else globalThis.fetch = originalFetch;
      if (originalURL === undefined) delete globalThis.URL;
      else globalThis.URL = originalURL;
      if (originalRequestAnimationFrame === undefined) delete globalThis.requestAnimationFrame;
      else globalThis.requestAnimationFrame = originalRequestAnimationFrame;
      if (originalCancelAnimationFrame === undefined) delete globalThis.cancelAnimationFrame;
      else globalThis.cancelAnimationFrame = originalCancelAnimationFrame;
      if (originalSetTimeout === undefined) delete globalThis.setTimeout;
      else globalThis.setTimeout = originalSetTimeout;
      if (originalClearTimeout === undefined) delete globalThis.clearTimeout;
      else globalThis.clearTimeout = originalClearTimeout;
      if (originalApp === undefined) delete globalThis.__VIBECOMFY_BROWSER_APP__;
      else globalThis.__VIBECOMFY_BROWSER_APP__ = originalApp;
      if (originalApi === undefined) delete globalThis.__VIBECOMFY_BROWSER_API__;
      else globalThis.__VIBECOMFY_BROWSER_API__ = originalApi;
      if (!hadCrypto) delete globalThis.crypto;
      globalThis.console = originalConsole;
      await rm(tempRoot, { recursive: true, force: true });
    },
  };
}
