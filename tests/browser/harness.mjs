import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WEB_SOURCE_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");

// ── Staged web modules — single source of truth ───────────────────────────
//
// Every ComfyUI web module copied into the temp custom_nodes root MUST appear
// here.  `verifyStagedDependencyClosure` (below) walks each entry's relative
// ESM imports recursively and fails the harness with a precise diagnostic if a
// transitive dependency is missing from this list — preventing the
// ERR_MODULE_NOT_FOUND that occurs when a staged module imports a sibling the
// harness never copied (e.g. layout_operation_v1.js / mutation_materialization_v1.js
// pulled in transitively via prepared_authority_v1.js).
export const STAGED_WEB_MODULES = [
  "vibecomfy_roundtrip.js",
  "roundtrip_extension.js",
  "panel_runtime.js",
  "panel_scheduler.js",
  "panel_thread.js",
  "panel_overlay.js",
  "panel_composer.js",
  "agent_edit_lifecycle.js",
  "agent_lifecycle_commit.js",
  "agent_edit_node_pack_installer.js",
  "comfy_adapter.js",
  "intent_graph_adapter.js",
  "agent_edit_response_contract.js",
  "agent_edit_response_contract_generated.js",
  "agent_edit_transaction.js",
  "diagnostics_reporting.js",
  "executor_progress.js",
  "agent_turn_feed.js",
  "agent_turn_reducer.js",
  "agent_status_poller.js",
  "agent_apply_flow.js",
  "agent_flow_deps.js",
  "agent_preview_cache.js",
  "agent_rebaseline_undo.js",
  "agent_submit_flow.js",
  "agent_candidate_actions.js",
  "active_canvas_scope_guard.js",
  "scope_resolver.js",
  "scoped_session_storage.js",
  "markdown.js",
  "preview_picker.js",
  "preview_diff_core.js",
  "agentic_replay.js",
  "canonical_delta.js",
  "canonical_hash.js",
  "deep_plain.js",
  "json_clone.js",
  "graph_projection.js",
  "layout_verification_contract.js",
  "root_scope_v1.js",
  "identity_contract_v1.js",
  "projection_registry_v1.js",
  "prepared_authority_v1.js",
  "layout_operation_v1.js",
  "mutation_materialization_v1.js",
  "legacy_migration_v1.js",
  "journal_durable_v1.js",
  "_intent_graph_receipt_core.mjs",
  "_prepared_plan_builder_v1.mjs",
];

// Relative imports that intentionally escape the web module directory.  They
// resolve against the temp comfyRoot (staged under comfyRoot/scripts by the
// harness) rather than the web root.  Any ../ import NOT listed here is a
// configuration error and is reported by the closure guard.
export const ALLOWED_EXTERNAL_RELATIVE_IMPORTS = new Set([
  "../../scripts/app.js",
  "../../scripts/api.js",
]);

// Bare (non-relative) ESM specifiers permitted in staged web modules.  Kept
// explicit so an accidental native/runtime/npm dependency is surfaced
// immediately rather than failing opaquely at module-load time.
export const ALLOWED_BARE_IMPORTS = new Set([
  // (none currently — the staged web modules are dependency-free pure JS)
]);

function _stripJsComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|\n)\s*\/\/[^\n]*/g, "$1");
}

// Plausible module specifier (npm-style or scoped).  Used to filter out regex
// false positives (e.g. `from "..."` matched inside arbitrary code) when
// collecting *bare* specifiers.  Relative specifiers are matched precisely via
// the `\.{1,2}/` anchor, so they never produce false positives.
const _PLAUSIBLE_BARE_SPEC_RE = /^[a-zA-Z@][\w@./-]*$/;

// Collect ESM import specifiers from module source, split into relative and
// bare sets.  Mirrors the comment-strip + relative-from regex strategy proven
// by the ownership-static tests; dynamic import() and side-effect import are
// also covered.
export function _collectImportSpecifiers(src) {
  const stripped = _stripJsComments(src);
  const relative = new Set();
  const bare = new Set();
  const record = (spec) => {
    if (spec.startsWith(".")) relative.add(spec);
    else if (_PLAUSIBLE_BARE_SPEC_RE.test(spec)) bare.add(spec);
  };
  let m;
  // import {…} from "spec"  /  export {…} from "spec"
  const fromRe = /\bfrom\s*["'`]([^"'`]+)["'`]/g;
  while ((m = fromRe.exec(stripped))) record(m[1]);
  // dynamic import("spec")
  const dynRe = /\bimport\s*\(\s*["'`]([^"'`]+)["'`]\s*\)/g;
  while ((m = dynRe.exec(stripped))) record(m[1]);
  // side-effect import "spec"
  const sideRe = /\bimport\s+["'`]([^"'`]+)["'`]/g;
  while ((m = sideRe.exec(stripped))) record(m[1]);
  return { relative: [...relative], bare: [...bare] };
}

// Resolve a relative specifier (./ or ../) against the web source root to a
// staged module name, tolerating extensionless specifiers.  Returns null when
// the specifier escapes the web root (a ../ import) — those are handled by the
// external allowlist.
function _resolveWebModuleName(spec, knownNames) {
  if (spec.startsWith("..") || spec.startsWith("/")) return null;
  const norm = spec.replace(/^\.\//, "");
  const candidates = [norm];
  if (!/\.(js|mjs)$/.test(norm)) candidates.push(`${norm}.js`, `${norm}.mjs`);
  for (const candidate of candidates) {
    if (knownNames.has(candidate)) return candidate;
  }
  return candidates[0]; // best guess for a precise missing-module diagnostic
}

/**
 * Walk the transitive closure of relative ESM imports starting from EVERY
 * staged entry module and verify each resolved dependency is itself staged.
 * Relative imports that escape the web root must be in the external allowlist;
 * bare (non-relative) imports must be in the bare allowlist.
 *
 * Returns { ok, errors } where each error carries a precise `kind` and
 * human-readable `message`:
 *   - "missing-source": a staged module has no source file
 *   - "missing-staged-module": a relative import resolves to a file not staged
 *   - "undeclared-external-import": a ../ import is not allowlisted
 *   - "undeclared-bare-import": a bare import is not allowlisted
 */
export async function verifyStagedDependencyClosure({
  webSourceRoot,
  stagedModuleNames,
  allowedExternalRelative = ALLOWED_EXTERNAL_RELATIVE_IMPORTS,
  allowedBareImports = ALLOWED_BARE_IMPORTS,
}) {
  const stagedSet = new Set(stagedModuleNames);
  const errors = [];
  const visited = new Set();

  async function readSource(name) {
    try {
      return await readFile(path.join(webSourceRoot, name), "utf8");
    } catch (_err) {
      return null;
    }
  }

  for (const entry of stagedModuleNames) {
    const stack = [entry];
    while (stack.length) {
      const current = stack.pop();
      if (visited.has(current)) continue;
      visited.add(current);
      const src = await readSource(current);
      if (src == null) {
        errors.push({
          entry,
          module: current,
          kind: "missing-source",
          message:
            `staged module "${current}" has no source file under ${webSourceRoot}; ` +
            `restore the source or remove it from STAGED_WEB_MODULES`,
        });
        continue;
      }
      const { relative, bare } = _collectImportSpecifiers(src);
      for (const specifier of bare) {
        if (!allowedBareImports.has(specifier)) {
          errors.push({
            entry,
            module: current,
            kind: "undeclared-bare-import",
            specifier,
            message:
              `"${current}" imports bare specifier "${specifier}" which is not in ` +
              `ALLOWED_BARE_IMPORTS; add it explicitly or remove the import`,
          });
        }
      }
      for (const specifier of relative) {
        const resolved = _resolveWebModuleName(specifier, stagedSet);
        if (resolved == null) {
          if (!allowedExternalRelative.has(specifier)) {
            errors.push({
              entry,
              module: current,
              kind: "undeclared-external-import",
              specifier,
              message:
                `"${current}" imports external relative "${specifier}" which is not in ` +
                `ALLOWED_EXTERNAL_RELATIVE_IMPORTS; stage it under the web root or allowlist it`,
            });
          }
          continue;
        }
        if (!stagedSet.has(resolved)) {
          errors.push({
            entry,
            module: current,
            kind: "missing-staged-module",
            specifier,
            resolved,
            message:
              `staged module "${current}" imports "${specifier}" (resolves to "${resolved}") ` +
              `but "${resolved}" is not in STAGED_WEB_MODULES; add it to the manifest ` +
              `to avoid ERR_MODULE_NOT_FOUND`,
          });
          continue;
        }
        if (!visited.has(resolved)) stack.push(resolved);
      }
    }
  }
  return { ok: errors.length === 0, errors };
}

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
  enableVibeComfySidebarTab = true,
  workflowId = "123e4567-e89b-12d3-a456-426614174000",
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
    const liveNode = {
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
    // Modern LiteGraph owns link creation through the source node.  Model
    // that contract in the browser harness instead of falling through to the
    // adapter's legacy plain-object link path: callers must receive a real
    // link record and both endpoint slots must be kept in sync.
    if (withGraphMutation) {
      liveNode.connect = function connect(sourceSlot, targetNode, targetSlot) {
        const graph = app?.canvas?.graph;
        const output = Array.isArray(this.outputs) ? this.outputs[Number(sourceSlot)] : null;
        const input = Array.isArray(targetNode?.inputs) ? targetNode.inputs[Number(targetSlot)] : null;
        if (!graph || !output || !input) {
          return null;
        }
        if (input.link != null && typeof graph.removeLink === "function") {
          graph.removeLink(input.link);
        }
        const existingIds = Object.values(graph.links || {})
          .map((entry) => Number(entry?.id))
          .filter(Number.isFinite);
        const declaredLastId = Number(currentGraph?.last_link_id);
        const linkId = Math.max(
          Number.isFinite(declaredLastId) ? declaredLastId + 1 : 1,
          existingIds.length ? Math.max(...existingIds) + 1 : 1,
        );
        const link = _decorateLiveLinkRecord({
          id: linkId,
          origin_id: this.id,
          origin_slot: Number(sourceSlot),
          target_id: targetNode.id,
          target_slot: Number(targetSlot),
          type: output.type ?? input.type ?? null,
        });
        graph.links[String(linkId)] = link;
        if (!Array.isArray(output.links)) output.links = [];
        output.links.push(linkId);
        input.link = linkId;
        if (currentGraph && typeof currentGraph === "object") {
          currentGraph.last_link_id = linkId;
        }
        const entry = {
          sourceNodeId: this.id,
          sourceSlot: Number(sourceSlot),
          targetNodeId: targetNode.id,
          targetSlot: Number(targetSlot),
          linkType: link.type,
          timestamp: Date.now(),
        };
        graphConnectCalls.push(entry);
        operationLog.push({ kind: "graph.connect", ...entry });
        return link;
      };
    }
    return liveNode;
  }

  class FakeGraphGroup {
    constructor(title = "Group", id = undefined) {
      this.__isGraphGroup = true;
      this.id = id;
      this.title = title;
      this.bounding = [0, 0, 140, 80];
      this.color = undefined;
      this.font_size = undefined;
      this.flags = {};
    }

    configure(serialized = {}) {
      if (serialized.id !== undefined) this.id = serialized.id;
      this.title = serialized.title || "Group";
      this.bounding = clone(serialized.bounding || [0, 0, 140, 80]);
      this.color = serialized.color;
      this.font_size = serialized.font_size;
      this.flags = clone(serialized.flags || {});
    }

    serialize() {
      const serialized = {
        title: this.title,
        bounding: clone(this.bounding),
      };
      if (this.id !== undefined) serialized.id = this.id;
      if (this.color !== undefined) serialized.color = this.color;
      if (this.font_size !== undefined) serialized.font_size = this.font_size;
      if (this.flags && Object.keys(this.flags).length) serialized.flags = clone(this.flags);
      return serialized;
    }

    recomputeInsideNodes() {}
  }

  function _buildLiveGroup(group) {
    const live = new FakeGraphGroup(group?.title, group?.id);
    live.configure(group || {});
    return live;
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
    app.canvas.graph._groups = (currentGraph?.groups || []).map(_buildLiveGroup);
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
      // Native LiteGraph factories create widget state before a serialized
      // candidate payload is configured onto the new node. Preserve the live
      // value even when the factory's minimal original shape omitted the key.
      if (node.widgets_values != null || Object.prototype.hasOwnProperty.call(serialized, "widgets_values")) {
        serialized.widgets_values = clone(node.widgets_values || null);
      }
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
      snapshot.links = Object.values(liveLinks).map((link) => clone(
        typeof link?.serialize === "function" ? link.serialize() : link,
      ));
    } else {
      snapshot.links = clone(snapshot.links || []);
    }
    if (Object.prototype.hasOwnProperty.call(currentGraph || {}, "groups") || app.canvas.graph._groups.length > 0) {
      snapshot.groups = (app.canvas.graph._groups || []).map((group) => clone(
        typeof group?.serialize === "function" ? group.serialize() : group,
      ));
    } else {
      delete snapshot.groups;
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
        _groups: [],
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
        removeLink(linkId) {
          const link = this.links?.[String(linkId)] || null;
          if (!link) return false;
          const sourceNode = this._nodes.find((entry) => String(entry?.id) === String(link.origin_id));
          const targetNode = this._nodes.find((entry) => String(entry?.id) === String(link.target_id));
          const output = Array.isArray(sourceNode?.outputs) ? sourceNode.outputs[link.origin_slot] : null;
          const input = Array.isArray(targetNode?.inputs) ? targetNode.inputs[link.target_slot] : null;
          if (Array.isArray(output?.links)) {
            output.links = output.links.filter((entry) => String(entry) !== String(link.id));
            if (!output.links.length) output.links = null;
          }
          if (input && String(input.link) === String(link.id)) input.link = null;
          delete this.links[String(link.id)];
          const entry = { linkId: link.id, timestamp: Date.now() };
          graphDisconnectCalls.push(entry);
          operationLog.push({ kind: "graph.disconnect", ...entry });
          return true;
        },
        add(node) {
          if (!withGraphMutation) {
            throw new Error("graph.add is not available; set withGraphMutation=true on createBrowserHarness.");
          }
          if (!node || typeof node !== "object") {
            throw new Error("graph.add requires a valid node object.");
          }
          graphAddCalls.push(clone(node));
          if (node.__isGraphGroup === true) {
            operationLog.push({ kind: "graph.addGroup", title: node.title });
            app.canvas.graph._groups.push(node);
            return;
          }
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
          if (node.__isGraphGroup === true) {
            const groupIndex = app.canvas.graph._groups.indexOf(node);
            if (groupIndex >= 0) app.canvas.graph._groups.splice(groupIndex, 1);
            graphRemoveCalls.push(clone(node));
            operationLog.push({ kind: "graph.removeGroup", title: node.title });
            return;
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
      workflow: workflowId ? {
        activeWorkflow: null,
        openWorkflows: [],
        vibecomfyScopeMetadata: { workflow_id: workflowId },
      } : undefined,
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
  const HarnessLGraphNode = withGraphMutation
    ? function HarnessLGraphNode(title) {
        const node = LiteGraphFactory.createNode("__vibecomfy_placeholder__");
        node.title = title;
        return node;
      }
    : null;

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
  // Stage every declared web module into the temp custom_nodes web root.
  // `STAGED_WEB_MODULES` is the single source of truth; the closure guard
  // invoked just below verifies no transitive dependency is missing.
  for (const moduleName of STAGED_WEB_MODULES) {
    await writeFile(
      path.join(webRoot, moduleName),
      await readFile(path.join(WEB_SOURCE_ROOT, moduleName), "utf8"),
    );
  }
  // ── Transitive dependency-closure guard ─────────────────────────────────
  // Verify every staged module's relative ESM imports resolve to another
  // staged module (or an allowlisted external path).  Fails fast with a
  // precise diagnostic rather than ERR_MODULE_NOT_FOUND at module-load time.
  const stagedClosure = await verifyStagedDependencyClosure({
    webSourceRoot: WEB_SOURCE_ROOT,
    stagedModuleNames: STAGED_WEB_MODULES,
  });
  assert.equal(
    stagedClosure.ok,
    true,
    `browser harness staged-module dependency closure is incomplete:\n${stagedClosure.errors
      .map((err) => `  - [${err.kind}] ${err.message}`)
      .join("\n")}`,
  );

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
  const originalGlobalApp = globalThis.app;
  const originalApp = globalThis.__VIBECOMFY_BROWSER_APP__;
  const originalApi = globalThis.__VIBECOMFY_BROWSER_API__;
  const originalSidebarTabFlag = globalThis.__VIBECOMFY_ENABLE_SIDEBAR_TAB__;
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
      ? {
          LGraphCanvas: LiteGraphCanvas,
          LGraphGroup: FakeGraphGroup,
          LGraphNode: HarnessLGraphNode,
          createNode: LiteGraphFactory.createNode.bind(LiteGraphFactory),
        }
      : { LGraphCanvas: LiteGraphCanvas },
  };
  globalThis.fetch = fetchImpl;
  // The scope guard reads Comfy's browser-global `app`, while the extension
  // itself imports the complete app object. Expose persisted workflow metadata
  // by default without inventing an active canvas scope; scope-focused tests
  // explicitly install the full harness app when they model tab switching.
  globalThis.app = { extensionManager: app.extensionManager };
  globalThis.__VIBECOMFY_BROWSER_APP__ = app;
  globalThis.__VIBECOMFY_BROWSER_API__ = mockApi;
  globalThis.__VIBECOMFY_ENABLE_SIDEBAR_TAB__ = enableVibeComfySidebarTab;
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
    async loadIntentGraphAdapter() {
      const target = pathToFileURL(path.join(webRoot, "intent_graph_adapter.js")).href;
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
    getLiveGroups() {
      return app.canvas.graph._groups;
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
      if (originalGlobalApp === undefined) delete globalThis.app;
      else globalThis.app = originalGlobalApp;
      if (originalApp === undefined) delete globalThis.__VIBECOMFY_BROWSER_APP__;
      else globalThis.__VIBECOMFY_BROWSER_APP__ = originalApp;
      if (originalApi === undefined) delete globalThis.__VIBECOMFY_BROWSER_API__;
      else globalThis.__VIBECOMFY_BROWSER_API__ = originalApi;
      if (originalSidebarTabFlag === undefined) delete globalThis.__VIBECOMFY_ENABLE_SIDEBAR_TAB__;
      else globalThis.__VIBECOMFY_ENABLE_SIDEBAR_TAB__ = originalSidebarTabFlag;
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

// ── C1: externally-owned sentinel instrumentation (§6.3 line 2, §6.6 step 10) ─
//
// A throwaway instrumented graph/app/canvas/LiteGraph whose every named native
// primitive boundary is wrapped by a sentinel.  Each sentinel increments a
// counter held BY THE HARNESS (never by any subject under test) and throws a
// sentinel marker, so a subject that reached a native primitive could not
// silently proceed.  The counters are owned, reset, and read here — entirely
// outside any plan builder.  This module performs NO native graph write: the
// sentinels only trip (and the subjects under test in C1 never reach them).
//
// The instrumented object exists so the zero-native-call proof is produced
// EXTERNALLY: the test resets the harness counters, invokes the (pure) plan
// builder, then reads the counters back from the harness and asserts every one
// is exactly zero.  The subject cannot import, mutate, or return these
// counters (Gate #4).  The named boundaries cover every future
// factory/configure/add/remove/connect/unlink/widget/mode/socket/group/
// geometry/repaint/serialize path without making C1 execute any of them.

export const SENTINEL_NATIVE_BOUNDARY_KEYS = Object.freeze([
  "factory_createNode",
  "graph_configure",
  "graph_clear",
  "node_add",
  "node_remove",
  "link_connect",
  "link_disconnect",
  "widget_write",
  "mode_write",
  "socket_repair",
  "group_construct",
  "group_configure",
  "group_add",
  "group_remove",
  "geometry_assign",
  "repaint",
  "serialize",
  "graph_change",
]);

export const SENTINEL_MARKER_CODE = "SENTINEL_NATIVE_PRIMITIVE_CALLED";

export function createSentinelGraph() {
  const counters = {};
  for (const key of SENTINEL_NATIVE_BOUNDARY_KEYS) counters[key] = 0;

  function trip(name) {
    counters[name] = counters[name] + 1;
    const err = new Error(`sentinel native primitive boundary reached: ${name}`);
    err.code = SENTINEL_MARKER_CODE;
    err.boundary = name;
    throw err;
  }

  // Native widget/value write boundary.
  const sentinelWidget = {
    name: null,
    value: undefined,
    set value(v) { trip("widget_write"); },
    setValue() { trip("widget_write"); },
    callback() { trip("widget_write"); },
  };

  // Native node mutation boundaries (factory-constructed node stand-in).
  const sentinelNode = {
    id: 0,
    type: "SentinelNode",
    pos: [0, 0],
    size: [210, 100],
    mode: 0,
    properties: {},
    widgets: [],
    widgets_values: [],
    inputs: [],
    outputs: [],
    setProperty(_name, _value) { trip("widget_write"); },
    setMode(_mode) { trip("mode_write"); },
    setWidgetValue(_value) { trip("widget_write"); },
    setPos(_pos) { trip("geometry_assign"); },
    setSize(_size) { trip("geometry_assign"); },
    connect(_target, _slot) { trip("link_connect"); },
    disconnectInput(_slot) { trip("link_disconnect"); },
    repairSocket() { trip("socket_repair"); },
    serialize() { trip("serialize"); },
  };

  // Native group boundaries.
  const sentinelGroup = {
    id: 0,
    title: "SentinelGroup",
    bounding: [0, 0, 0, 0],
    color: null,
    recomputeInsideNodes() { trip("group_configure"); },
    setBounding(_box) { trip("group_configure"); },
    configure(_data) { trip("group_configure"); },
  };

  // Native LiteGraph factory boundary.
  const sentinelLiteGraph = {
    createNode(_type) { trip("factory_createNode"); return sentinelNode; },
    createGroup() { trip("group_construct"); return sentinelGroup; },
    NODE_TITLE_HEIGHT: 30,
    NODE_SLOT_HEIGHT: 20,
  };

  // Native graph mutation boundaries.
  const sentinelGraph = {
    _nodes: [],
    _groups: [],
    links: [],
    last_node_id: 0,
    last_link_id: 0,
    add(_node) { trip("node_add"); },
    remove(_node) { trip("node_remove"); },
    connect(_from, _to) { trip("link_connect"); },
    disconnect(_id) { trip("link_disconnect"); },
    removeLink(_id) { trip("link_disconnect"); },
    configure(_data) { trip("graph_configure"); },
    clear() { trip("graph_clear"); },
    serialize() { trip("serialize"); },
    setDirtyCanvas(_fg, _bg) { trip("repaint"); },
    change() { trip("graph_change"); },
    getNodeById(_id) { return null; },
    addGroup(_group) { trip("group_add"); },
    removeGroup(_group) { trip("group_remove"); },
    getGroup(_id) { return null; },
  };

  // Native repaint boundaries (canvas).
  const sentinelCanvas = {
    setDirty(_fg, _bg) { trip("repaint"); },
    draw(_fg, _bg) { trip("repaint"); },
    canvas: { width: 0, height: 0, getContext() { return null; } },
  };

  // Native app aggregator (the object adapters receive).
  const sentinelApp = {
    canvas: sentinelCanvas,
    graph: sentinelGraph,
    LiteGraph: sentinelLiteGraph,
    // Harness-only capability marker kept as a plain string so the harness
    // does not import intent_graph_adapter.js; a real adapter reads the same
    // literal.  C1 never drives the adapter, so this never trips a primitive.
    __vibecomfyAllowDeltaSerializeConfigureFallback: true,
  };

  function reset() {
    for (const key of SENTINEL_NATIVE_BOUNDARY_KEYS) counters[key] = 0;
  }

  function snapshot() {
    const out = {};
    for (const key of SENTINEL_NATIVE_BOUNDARY_KEYS) out[key] = counters[key];
    return Object.freeze(out);
  }

  function assertAllZero(message) {
    const label = message || "expected every native sentinel boundary to remain zero";
    for (const key of SENTINEL_NATIVE_BOUNDARY_KEYS) {
      assert.equal(
        counters[key],
        0,
        `${label}: native primitive "${key}" was reached ${counters[key]} time(s)`,
      );
    }
  }

  return Object.freeze({
    graph: sentinelGraph,
    app: sentinelApp,
    canvas: sentinelCanvas,
    LiteGraph: sentinelLiteGraph,
    node: sentinelNode,
    group: sentinelGroup,
    widget: sentinelWidget,
    counters,
    boundaryKeys: SENTINEL_NATIVE_BOUNDARY_KEYS,
    markerCode: SENTINEL_MARKER_CODE,
    reset,
    snapshot,
    assertAllZero,
  });
}
