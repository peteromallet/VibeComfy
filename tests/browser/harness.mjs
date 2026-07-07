import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const EXTENSION_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "vibecomfy_roundtrip.js");
const PANEL_RUNTIME_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "panel_runtime.js");
const PANEL_SCHEDULER_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "panel_scheduler.js");
const PANEL_THREAD_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "panel_thread.js");
const PANEL_OVERLAY_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "panel_overlay.js");
const PANEL_COMPOSER_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "panel_composer.js");
const LIFECYCLE_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agent_edit_lifecycle.js");
const LIFECYCLE_COMMIT_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agent_lifecycle_commit.js");
const NODE_PACK_INSTALLER_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agent_edit_node_pack_installer.js");
const ADAPTER_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "comfy_adapter.js");
const RESPONSE_CONTRACT_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agent_edit_response_contract.js");
const DIAGNOSTICS_REPORTING_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "diagnostics_reporting.js");
const EXECUTOR_PROGRESS_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "executor_progress.js");
const AGENT_TURN_FEED_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agent_turn_feed.js");
const AGENT_STATUS_POLLER_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agent_status_poller.js");
const AGENT_CANDIDATE_ACTIONS_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agent_candidate_actions.js");
const ACTIVE_CANVAS_SCOPE_GUARD_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "active_canvas_scope_guard.js");
const SCOPE_RESOLVER_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "scope_resolver.js");
const SCOPED_SESSION_STORAGE_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "scoped_session_storage.js");
const MARKDOWN_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "markdown.js");
const PREVIEW_PICKER_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "preview_picker.js");
const AGENTIC_REPLAY_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "agentic_replay.js");
const CANONICAL_DELTA_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "canonical_delta.js");

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
    this._textContent = "";
    this.id = "";
    this.eventListeners = {};
  }

  get textContent() {
    if (this.children.length > 0) {
      return this.children.map((child) => (child == null ? "" : String(child.textContent || ""))).join("");
    }
    return this._textContent;
  }

  set textContent(value) {
    this._textContent = String(value == null ? "" : value);
    this.children.length = 0;
  }

  get isConnected() {
    if (this === this.ownerDocument.body || this === this.ownerDocument.head) {
      return true;
    }
    return Boolean(this.parentNode?.isConnected);
  }

  get options() {
    return this.children;
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

  remove(index) {
    if (typeof index === "number") {
      const child = this.children[index];
      if (child) {
        this.removeChild(child);
      }
      return;
    }
    if (this.parentNode) {
      this.parentNode.removeChild(this);
    }
  }

  setAttribute(name, value) {
    const normalizedName = String(name || "");
    const normalizedValue = String(value == null ? "" : value);
    this.attributes[normalizedName] = normalizedValue;
    if (normalizedName === "id") {
      this.id = normalizedValue;
    } else if (normalizedName === "class") {
      this.className = normalizedValue;
    } else if (normalizedName === "title") {
      this.title = normalizedValue;
    } else if (normalizedName.startsWith("data-")) {
      this.dataset[normalizedName.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = normalizedValue;
    }
  }

  getAttribute(name) {
    const normalizedName = String(name || "");
    if (normalizedName === "id") {
      return this.id || null;
    }
    if (normalizedName === "title") {
      return this.title || null;
    }
    if (normalizedName.startsWith("data-")) {
      const value = this.dataset[normalizedName.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())];
      return value == null ? null : String(value);
    }
    return Object.prototype.hasOwnProperty.call(this.attributes, normalizedName)
      ? this.attributes[normalizedName]
      : null;
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

  dispatchEvent(event) {
    if (!event || typeof event !== "object") {
      return true;
    }
    const listeners = this.eventListeners[event.type] || [];
    for (const listener of listeners) {
      listener.call(this, event);
    }
    return !event.cancelable || event.defaultPrevented !== true;
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

  createElementNS(_namespace, tagName) {
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
    headers: {
      get(name) {
        return String(name || "").toLowerCase() === "content-type"
          ? "application/json"
          : null;
      },
    },
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
  withGraphMutation = false,
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
  const graphAddCalls = [];
  const graphRemoveCalls = [];
  const graphConnectCalls = [];
  const graphDisconnectCalls = [];
  const graphFieldWriteCalls = [];
  const graphModeWriteCalls = [];
  const graphReorderWriteCalls = [];
  let liveCanvasRevision = 1;
  let currentGraph = clone(
    graph || {
      nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
      links: [],
    },
  );

  var TITLE_H = (globalThis.window?.LiteGraph?.NODE_TITLE_HEIGHT) || 30;
  var SLOT_H = (globalThis.window?.LiteGraph?.NODE_SLOT_HEIGHT) || 20;

  function _decorateLiveLinkRecord(link) {
    var record;
    if (Array.isArray(link)) {
      record = {
        id: link[0],
        origin_id: link[1],
        origin_slot: Number(link[2]),
        target_id: link[3],
        target_slot: Number(link[4]),
        type: link.length > 5 ? link[5] : null,
      };
    } else if (link && typeof link === "object") {
      record = {
        id: link.id,
        origin_id: link.origin_id,
        origin_slot: Number(link.origin_slot),
        target_id: link.target_id,
        target_slot: Number(link.target_slot),
        type: link.type ?? null,
      };
    } else {
      return null;
    }
    if (typeof record.asSerialisable !== "function") {
      Object.defineProperty(record, "asSerialisable", {
        enumerable: false,
        configurable: true,
        value() {
          return [
            this.id,
            this.origin_id,
            this.origin_slot,
            this.target_id,
            this.target_slot,
            this.type,
          ];
        },
      });
    }
    if (typeof record.serialize !== "function") {
      Object.defineProperty(record, "serialize", {
        enumerable: false,
        configurable: true,
        value() {
          return this.asSerialisable();
        },
      });
    }
    if (typeof record.disconnect !== "function") {
      Object.defineProperty(record, "disconnect", {
        enumerable: false,
        configurable: true,
        value(network) {
          if (!network) {
            return;
          }
          if (network.links && typeof network.links === "object" && !Array.isArray(network.links)) {
            delete network.links[String(this.id)];
          }
        },
      });
    }
    return record;
  }

  function _buildLiveLinkMap(linksArray) {
    var map = {};
    if (Array.isArray(linksArray)) {
      for (var _li = 0; _li < linksArray.length; _li += 1) {
        var link = linksArray[_li];
        var record = _decorateLiveLinkRecord(link);
        if (!record) continue;
        var linkId = record.id ?? _li;
        map[String(linkId)] = record;
      }
    }
    return map;
  }

  function _buildLiveNode(node) {
    return {
      id: node.id,
      type: node.type,
      properties: clone(node.properties || {}),
      inputs: clone(node.inputs || []),
      outputs: clone(node.outputs || []),
      widgets: clone(node.widgets || null),
      widgets_values: clone(node.widgets_values || null),
      mode: node.mode !== undefined ? node.mode : undefined,
      pos: Array.isArray(node.pos) ? [...node.pos] : [0, 0],
      size: Array.isArray(node.size) ? [...node.size] : [200, 100],
      getConnectionPos(isInput, slotIndex) {
        var nx = (Array.isArray(node.pos) ? node.pos[0] : 0) || 0;
        var ny = (Array.isArray(node.pos) ? node.pos[1] : 0) || 0;
        var nw = Array.isArray(node.size) ? (node.size[0] || 200) : 200;
        if (isInput) return [nx, ny + TITLE_H + slotIndex * SLOT_H + SLOT_H / 2];
        return [nx + nw, ny + TITLE_H + slotIndex * SLOT_H + SLOT_H / 2];
      },
      __vibecomfyOriginal: clone(node),
    };
  }

  function _resetGraphLinks(sourceLinks) {
    app.canvas.graph.links = _buildLiveLinkMap(sourceLinks);
  }

  function _initGraphLinks(sourceLinks) {
    var links = app.canvas.graph.links;
    if (!links || typeof links !== "object" || Array.isArray(links)) {
      links = _buildLiveLinkMap(sourceLinks);
      app.canvas.graph.links = links;
    }
    return links;
  }

  function syncLiveGraphNodes() {
    app.canvas.graph._vibecomfyLiveCanvasToken = `rev:${liveCanvasRevision}`;
    _initGraphLinks(currentGraph?.links);
    app.canvas.graph._nodes = (currentGraph?.nodes || []).map(_buildLiveNode);
  }

  function _serializeLiveGraphState() {
    var snapshot = clone(currentGraph || {});
    var priorNodes = Array.isArray(currentGraph?.nodes) ? currentGraph.nodes : [];
    var priorByUid = new Map();
    var priorById = new Map();
    for (var _pi = 0; _pi < priorNodes.length; _pi += 1) {
      var priorNode = priorNodes[_pi];
      var priorUid = priorNode?.properties?.vibecomfy_uid ?? priorNode?.uid ?? priorNode?.id ?? null;
      if (priorUid !== null && priorUid !== undefined) {
        priorByUid.set(String(priorUid), priorNode);
      }
      if (priorNode?.id !== null && priorNode?.id !== undefined) {
        priorById.set(String(priorNode.id), priorNode);
      }
    }
    snapshot.nodes = (app.canvas.graph._nodes || []).map((node) => {
      var uid = node?.properties?.vibecomfy_uid ?? node?.uid ?? node?.id ?? null;
      var prior = (uid !== null && uid !== undefined ? priorByUid.get(String(uid)) : null) || priorById.get(String(node.id)) || null;
      var originalShape = node?.__vibecomfyOriginal && typeof node.__vibecomfyOriginal === "object"
        ? node.__vibecomfyOriginal
        : {};
      var serialized = clone(prior || originalShape || {});
      serialized.id = node.id;
      serialized.type = node.type;
      serialized.properties = clone(node.properties || {});
      if (Object.prototype.hasOwnProperty.call(serialized, "inputs")) serialized.inputs = clone(node.inputs || []);
      if (Object.prototype.hasOwnProperty.call(serialized, "outputs")) serialized.outputs = clone(node.outputs || []);
      if (Object.prototype.hasOwnProperty.call(serialized, "widgets")) serialized.widgets = clone(node.widgets || null);
      if (Object.prototype.hasOwnProperty.call(serialized, "widgets_values")) serialized.widgets_values = clone(node.widgets_values || null);
      if (node.mode !== undefined || Object.prototype.hasOwnProperty.call(serialized, "mode")) serialized.mode = node.mode;
      if (Array.isArray(node.pos) || Array.isArray(serialized.pos)) serialized.pos = Array.isArray(node.pos) ? [...node.pos] : [0, 0];
      if (Object.prototype.hasOwnProperty.call(serialized, "size")) serialized.size = Array.isArray(node.size) ? [...node.size] : [200, 100];
      if (node.boxcolor !== undefined || Object.prototype.hasOwnProperty.call(serialized, "boxcolor")) serialized.boxcolor = node.boxcolor;
      if (node.bgcolor !== undefined || Object.prototype.hasOwnProperty.call(serialized, "bgcolor")) serialized.bgcolor = node.bgcolor;
      if (node.color !== undefined || Object.prototype.hasOwnProperty.call(serialized, "color")) serialized.color = node.color;
      return serialized;
    });
    var liveLinks = app.canvas.graph.links;
    if (liveLinks && typeof liveLinks === "object" && !Array.isArray(liveLinks)) {
      snapshot.links = Object.values(liveLinks).map((link) => clone(link));
    } else {
      snapshot.links = clone(snapshot.links || []);
    }
    currentGraph = clone(snapshot);
    return snapshot;
  }

  const app = {
    __vibecomfyAllowDeltaSerializeConfigureFallback: true,
    canvas: {
      // Instance-level onDrawForeground — ComfyUI 1.39.x assigns a function
      // at build time. Capability detection checks typeof === 'function'.
      onDrawForeground: function onDrawForeground(_ctx) { /* ComfyUI default */ },
      graph: {
        serialize() {
          const snapshot = withGraphMutation ? _serializeLiveGraphState() : clone(currentGraph);
          serializeCalls.push(snapshot);
          return snapshot;
        },
        _nodes: [],
        clear() {
          graphClearCalls.push(clone(currentGraph));
          operationLog.push({ kind: "graph.clear" });
          liveCanvasRevision += 1;
          currentGraph = { nodes: [], links: [] };
          _resetGraphLinks([]);
          syncLiveGraphNodes();
        },
        configure(nextGraph) {
          const snapshot = clone(nextGraph);
          graphConfigureCalls.push(snapshot);
          operationLog.push({ kind: "graph.configure", graph: snapshot });
          liveCanvasRevision += 1;
          currentGraph = snapshot;
          _resetGraphLinks(snapshot?.links);
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
        add(node) {
          if (!withGraphMutation) {
            throw new Error("graph.add is not available; set withGraphMutation=true on createBrowserHarness.");
          }
          if (!node || typeof node !== "object") {
            throw new Error("graph.add requires a valid node object.");
          }
          graphAddCalls.push(clone(node));
          operationLog.push({ kind: "graph.add", nodeId: node.id, type: node.type });
          app.canvas.graph._nodes.push(node);
        },
        remove(node) {
          if (!withGraphMutation) {
            throw new Error("graph.remove is not available; set withGraphMutation=true on createBrowserHarness.");
          }
          if (!node || typeof node !== "object") {
            throw new Error("graph.remove requires a valid node object.");
          }
          const nodeId = node.id;
          const index = app.canvas.graph._nodes.indexOf(node);
          if (index < 0) {
            // Node not found; still log for diagnostics.
            operationLog.push({ kind: "graph.remove", nodeId, alreadyAbsent: true });
            return;
          }
          var links = app.canvas.graph.links;
          var nodes = app.canvas.graph._nodes;
          if (Array.isArray(node.inputs)) {
            for (var _ii = 0; _ii < node.inputs.length; _ii += 1) {
              var input = node.inputs[_ii];
              if (input?.link == null) continue;
              var incomingLink = links?.[String(input.link)] || null;
              if (!incomingLink || typeof incomingLink.disconnect !== "function") {
                throw new TypeError("a.disconnect is not a function");
              }
              var sourceNode = nodes.find((entry) => String(entry?.id) === String(incomingLink.origin_id));
              var sourceOutput = Array.isArray(sourceNode?.outputs) ? sourceNode.outputs[incomingLink.origin_slot] : null;
              if (Array.isArray(sourceOutput?.links)) {
                sourceOutput.links = sourceOutput.links.filter((entry) => String(entry) !== String(incomingLink.id));
                if (!sourceOutput.links.length) {
                  sourceOutput.links = null;
                }
              }
              input.link = null;
              incomingLink.disconnect(app.canvas.graph, "output");
            }
          }
          if (Array.isArray(node.outputs)) {
            for (var _oi = 0; _oi < node.outputs.length; _oi += 1) {
              var output = node.outputs[_oi];
              var outputLinks = Array.isArray(output?.links) ? output.links.slice() : [];
              for (var _li = 0; _li < outputLinks.length; _li += 1) {
                var linkId = outputLinks[_li];
                var outgoingLink = links?.[String(linkId)] || null;
                if (!outgoingLink || typeof outgoingLink.disconnect !== "function") {
                  throw new TypeError("a.disconnect is not a function");
                }
                var targetNode = nodes.find((entry) => String(entry?.id) === String(outgoingLink.target_id));
                var targetInput = Array.isArray(targetNode?.inputs) ? targetNode.inputs[outgoingLink.target_slot] : null;
                if (targetInput) {
                  targetInput.link = null;
                }
                outgoingLink.disconnect(app.canvas.graph);
              }
              output.links = null;
            }
          }
          app.canvas.graph._nodes.splice(index, 1);
          graphRemoveCalls.push(clone(node));
          operationLog.push({ kind: "graph.remove", nodeId });
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
      _resetGraphLinks(snapshot?.links);
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

  const LiteGraphFactory = withGraphMutation ? {
    createNode(type) {
      if (typeof type !== "string" || !type) {
        return null;
      }
      return _buildLiveNode({ id: Date.now() + Math.random(), type, properties: {}, inputs: [], outputs: [], pos: [0, 0], size: [200, 100] });
    },
  } : null;

  const fetchImpl = async (url, options = {}) => {
    let key = String(url);
    const deferRequestLog = key.startsWith("/vibecomfy/agent-edit/chat?");
    const logRequest = () => {
      requests.push({
        url: key,
        method: options.method || "GET",
        headers: clone(options.headers || {}),
        body: options.body,
      });
      operationLog.push({ kind: "request", url: key, method: options.method || "GET" });
    };
    if (!deferRequestLog) {
      logRequest();
    }
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
      if (deferRequestLog) {
        logRequest();
      }
      operationLog.push({ kind: "response", url: key, status: value.status || 200 });
      return makeResponse(value.status || 200, value.body);
    }
    if (deferRequestLog) {
      logRequest();
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
  await writeFile(path.join(webRoot, "panel_runtime.js"), await readFile(PANEL_RUNTIME_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "panel_scheduler.js"), await readFile(PANEL_SCHEDULER_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "panel_thread.js"), await readFile(PANEL_THREAD_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "panel_overlay.js"), await readFile(PANEL_OVERLAY_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "panel_composer.js"), await readFile(PANEL_COMPOSER_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agent_edit_lifecycle.js"), await readFile(LIFECYCLE_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agent_lifecycle_commit.js"), await readFile(LIFECYCLE_COMMIT_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agent_edit_node_pack_installer.js"), await readFile(NODE_PACK_INSTALLER_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "comfy_adapter.js"), await readFile(ADAPTER_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agent_edit_response_contract.js"), await readFile(RESPONSE_CONTRACT_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "diagnostics_reporting.js"), await readFile(DIAGNOSTICS_REPORTING_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "executor_progress.js"), await readFile(EXECUTOR_PROGRESS_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agent_turn_feed.js"), await readFile(AGENT_TURN_FEED_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agent_status_poller.js"), await readFile(AGENT_STATUS_POLLER_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agent_candidate_actions.js"), await readFile(AGENT_CANDIDATE_ACTIONS_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "active_canvas_scope_guard.js"), await readFile(ACTIVE_CANVAS_SCOPE_GUARD_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "scope_resolver.js"), await readFile(SCOPE_RESOLVER_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "scoped_session_storage.js"), await readFile(SCOPED_SESSION_STORAGE_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "markdown.js"), await readFile(MARKDOWN_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "preview_picker.js"), await readFile(PREVIEW_PICKER_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "agentic_replay.js"), await readFile(AGENTIC_REPLAY_SOURCE, "utf8"));
  await writeFile(path.join(webRoot, "canonical_delta.js"), await readFile(CANONICAL_DELTA_SOURCE, "utf8"));

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
  const originalComfyAPI = globalThis.window?.comfyAPI;
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
  globalThis.window = {
    document,
    LiteGraph: withGraphMutation
      ? { LGraphCanvas: LiteGraphCanvas, createNode: LiteGraphFactory.createNode.bind(LiteGraphFactory) }
      : { LGraphCanvas: LiteGraphCanvas },
  };
  globalThis.fetch = fetchImpl;
  globalThis.__VIBECOMFY_BROWSER_APP__ = app;
  globalThis.__VIBECOMFY_BROWSER_API__ = mockApi;
  globalThis.window.comfyAPI = {
    app: { app },
    api: { api: mockApi },
  };
  globalThis.window.__VIBECOMFY_ENABLE_LEGACY_CHAT_REHYDRATE__ = true;
  if (!hadCrypto) {
    globalThis.crypto = (await import("node:crypto")).webcrypto;
  }
  // ── Storage fakes (used by frontend session persistence) ─────────────
  const makeStorage = () => {
    const store = new Map();
    return {
      getItem(key) {
        const val = store.get(String(key));
        return val === undefined ? null : val;
      },
      setItem(key, value) {
        store.set(String(key), String(value));
      },
      removeItem(key) {
        store.delete(String(key));
      },
      clear() {
        store.clear();
      },
      get length() {
        return store.size;
      },
      key(index) {
        const keys = [...store.keys()];
        return keys[index] || null;
      },
      // Expose store for test assertions.
      _dump() {
        return Object.fromEntries(store);
      },
    };
  };
  globalThis.localStorage = makeStorage();
  globalThis.sessionStorage = makeStorage();
  globalThis.window.localStorage = globalThis.localStorage;
  globalThis.window.sessionStorage = globalThis.sessionStorage;
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
    const buttons = document.body.querySelectorAll(
      (node) => node.tagName === "BUTTON"
        && (
          node.textContent === label
          || node.getAttribute?.("aria-label") === label
          || node.title === label
        ),
    );
    const agentPanelOpen = document.getElementById("vibecomfy-agent-panel-root")?.dataset?.open === "1";
    return buttons.slice().sort((left, right) => {
      const leftHidden = left.style?.display === "none" ? 1 : 0;
      const rightHidden = right.style?.display === "none" ? 1 : 0;
      if (leftHidden !== rightHidden) {
        return leftHidden - rightHidden;
      }
      const leftDisabled = left.disabled ? 1 : 0;
      const rightDisabled = right.disabled ? 1 : 0;
      if (leftDisabled !== rightDisabled) {
        return leftDisabled - rightDisabled;
      }
      const leftAgentPanel = String(left.id || "").startsWith("vibecomfy-agent-panel-") ? 1 : 0;
      const rightAgentPanel = String(right.id || "").startsWith("vibecomfy-agent-panel-") ? 1 : 0;
      return agentPanelOpen
        ? rightAgentPanel - leftAgentPanel
        : leftAgentPanel - rightAgentPanel;
    });
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
    graphAddCalls,
    graphRemoveCalls,
    graphConnectCalls,
    graphDisconnectCalls,
    graphFieldWriteCalls,
    graphModeWriteCalls,
    graphReorderWriteCalls,
    withGraphMutation,
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
    async loadPreviewPicker() {
      const target = pathToFileURL(path.join(webRoot, "preview_picker.js")).href;
      return import(`${target}?t=${Date.now()}`);
    },
    async loadAgenticReplay() {
      const target = pathToFileURL(path.join(webRoot, "agentic_replay.js")).href;
      return import(`${target}?t=${Date.now()}`);
    },
    async loadPanelRuntime() {
      const target = pathToFileURL(path.join(webRoot, "panel_runtime.js")).href;
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
      const result = command.function();
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
      return result;
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
      _resetGraphLinks(currentGraph?.links);
      syncLiveGraphNodes();
    },
    setCurrentGraphWithoutRevisionBump(nextGraph) {
      currentGraph = clone(nextGraph);
      _resetGraphLinks(currentGraph?.links);
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
    getLiveLinks() {
      return app.canvas.graph.links;
    },
    recordFieldWrite(nodeUid, fieldPath, value) {
      var entry = { nodeUid, fieldPath: [...fieldPath], value: clone(value), timestamp: Date.now() };
      graphFieldWriteCalls.push(entry);
      operationLog.push({ kind: "graph.fieldWrite", nodeUid, fieldPath: [...fieldPath] });
      return entry;
    },
    recordModeWrite(nodeUid, mode) {
      var entry = { nodeUid, mode, timestamp: Date.now() };
      graphModeWriteCalls.push(entry);
      operationLog.push({ kind: "graph.modeWrite", nodeUid, mode });
      return entry;
    },
    recordReorderWrite(nodeUid, axis, order) {
      var entry = { nodeUid, axis, order: Array.isArray(order) ? [...order] : order, timestamp: Date.now() };
      graphReorderWriteCalls.push(entry);
      operationLog.push({ kind: "graph.reorderWrite", nodeUid, axis });
      return entry;
    },
    recordConnect(sourceNodeId, sourceSlot, targetNodeId, targetSlot, linkType) {
      var entry = { sourceNodeId, sourceSlot, targetNodeId, targetSlot, linkType: linkType ?? null, timestamp: Date.now() };
      graphConnectCalls.push(entry);
      operationLog.push({ kind: "graph.connect", sourceNodeId, sourceSlot, targetNodeId, targetSlot });
      return entry;
    },
    recordDisconnect(linkId) {
      var entry = { linkId, timestamp: Date.now() };
      graphDisconnectCalls.push(entry);
      operationLog.push({ kind: "graph.disconnect", linkId });
      return entry;
    },
    assertNoGraphClearOrConfigure(msg) {
      var label = msg || "Scoped V2 apply must not call graph.clear() or graph.configure()";
      assert.equal(graphClearCalls.length, 0, `${label}: graph.clear() was called ${graphClearCalls.length} time(s)`);
      assert.equal(graphConfigureCalls.length, 0, `${label}: graph.configure() was called ${graphConfigureCalls.length} time(s)`);
    },
    assertNoWholeGraphOps(msg) {
      var label = msg || "Scoped V2 apply must not use wholesale graph operations";
      this.assertNoGraphClearOrConfigure(label);
      assert.equal(loadGraphDataCalls.length, 0, `${label}: loadGraphData was called ${loadGraphDataCalls.length} time(s)`);
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
      if (globalThis.window && originalComfyAPI !== undefined) {
        globalThis.window.comfyAPI = originalComfyAPI;
      } else if (globalThis.window) {
        delete globalThis.window.comfyAPI;
      }
      if (!hadCrypto) delete globalThis.crypto;
      globalThis.console = originalConsole;
      await rm(tempRoot, { recursive: true, force: true });
    },
  };
}
