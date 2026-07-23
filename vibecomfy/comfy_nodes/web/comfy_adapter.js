// ── VibeComfy ComfyUI Adapter — Capability Detection & Harness Profiles ───
// M4a: Isolates frontend capability detection into one shared module.
// Consumers import detectCapabilities() and registerExtensionWithCapabilities()
// instead of inlining app.* checks. Existing hook semantics are NOT changed yet.
//
// Backend contract authority: vibecomfy/comfy_nodes/agent_contracts.py.
// Harness profiles describe the shape of the mock app/canvas/graph needed
// for browser tests to match supported / degraded / missing-hook ComfyUI builds.
//
// Canonical delta contract: This module now requires that delta ops passed to
// preflightDeltaPlan() and applyGraphDeltaInPlace() are normalized canonical
// ops (the six supported op types in CANONICAL_DELTA_OP_NAMES).  Non-root scoped
// apply is classified as unsupported_scoped_apply.  Added nodes are materialized
// from explicit uid/node_id rather than inferred from scope_path.

// ── Canonical delta constants (aligned with canonical_delta.js) ─────────────

import { decodeNodeFieldPathV1 } from "./canonical_delta.js";
import { canonicalJsonString } from "./canonical_hash.js";
import {
  createIntentGraphAdapter,
  HARNESS_DELTA_APPLY_FALLBACK_MARKER,
} from "./intent_graph_adapter.js";

/** Canonical V2 delta schema version. */
const DELTA_SCHEMA_VERSION = "2.0.0";

/** Diagnostic code: non-root scoped apply is unsupported in the browser adapter. */
const DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY = "unsupported_scoped_apply";

/** The six canonical delta op types. */
const CANONICAL_DELTA_OP_NAMES = Object.freeze([
  "set_node_field",
  "set_mode",
  "add_node",
  "upsert_link",
  "remove_node",
  "remove_link",
]);

/**
 * Structured diagnostic error for delta contract violations.
 * Mirrors the DeltaDiagnosticError in canonical_delta.js.
 */
class DeltaDiagnosticError extends Error {
  constructor(message, code, detail = {}) {
    super(message);
    this.name = "DeltaDiagnosticError";
    this.code = code || "malformed_delta";
    this.detail = detail || {};
  }
}

// ── Supported frontend version ─────────────────────────────────────────────
const SUPPORTED_FRONTEND = "1.39.x";
let inOverlayDraw = false;

function safeAdapterLogDetail(value) {
  if (value == null) {
    return "";
  }
  if (typeof value === "string") {
    return value.length > 500 ? `${value.slice(0, 497)}...` : value;
  }
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }
  if (value instanceof Error) {
    const name = typeof value.name === "string" && value.name ? value.name : "Error";
    const message = typeof value.message === "string" ? value.message : "";
    return message ? `${name}: ${message}` : name;
  }
  if (Array.isArray(value)) {
    return `[array length=${value.length}]`;
  }
  if (typeof value === "object") {
    let keys = [];
    try {
      keys = Object.keys(value).slice(0, 6);
    } catch (_e) {
      keys = [];
    }
    const ctor = typeof value.constructor?.name === "string" && value.constructor.name
      ? value.constructor.name
      : "Object";
    return keys.length ? `[${ctor} keys=${keys.join(",")}]` : `[${ctor}]`;
  }
  return typeof value;
}

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
function detectGraphApply(app) {
  return graphCapability(app, "graph_apply");
}

function graphCapability(app, name) {
  const result = createIntentGraphAdapter(app).capabilities();
  if (result.ok && result.data?.[name]) {
    return result.data[name];
  }
  return {
    available: false,
    detail: result.diagnostic?.message || `Graph capability ${name} is unavailable.`,
    path: `intent_graph_adapter.${name}`,
    strategy: null,
    fallback: false,
  };
}

/**
 * Return the live LiteGraph instance when present.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @returns {object|null}
 */
function getLiveGraph(app) {
  return app?.canvas?.graph || null;
}

/**
 * Repaint the canvas after an in-place graph update.
 * graph.configure() mutates the data model but does not redraw on its own.
 *
 * @param {object} app — the ComfyUI app global (or mock)
 * @param {object} [graph] — optional live graph reference
 */
function repaintGraph(app, graph = getLiveGraph(app)) {
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
      console.warn("[vibecomfy] post-apply canvas redraw failed (data applied):", safeAdapterLogDetail(error));
    }
  }
  return { graph, capability };
}

export { HARNESS_DELTA_APPLY_FALLBACK_MARKER };

function cloneJson(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function canonicalNodeUid(node) {
  if (!node || typeof node !== "object") {
    return null;
  }
  const properties = node.properties && typeof node.properties === "object" ? node.properties : null;
  const candidates = [
    properties?.vibecomfy_uid,
    properties?.uid,
    node.vibecomfy_uid,
    node.uid,
    node.id,
  ];
  for (const candidate of candidates) {
    if (candidate === null || candidate === undefined) {
      continue;
    }
    const normalized = String(candidate).trim();
    if (normalized) {
      return normalized;
    }
  }
  return null;
}

function buildGraphIndex(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const byUid = new Map();
  const byId = new Map();
  for (const node of nodes) {
    const uid = canonicalNodeUid(node);
    if (uid && !byUid.has(uid)) {
      byUid.set(uid, node);
    }
    if (node?.id !== null && node?.id !== undefined) {
      const idKey = String(node.id);
      if (!byId.has(idKey)) {
        byId.set(idKey, node);
      }
    }
  }
  return { byUid, byId };
}

function normalizeScopePath(value) {
  if (Array.isArray(value)) {
    return value
      .filter((entry) => entry !== "" && entry !== "nodes" && entry !== null && entry !== undefined)
      .map((entry) => String(entry));
  }
  if (value === "" || value === "nodes" || value === null || value === undefined) {
    return [];
  }
  return [String(value)];
}

function parseNodeTarget(target) {
  if (Array.isArray(target)) {
    const [scopeRaw, uidOrId, ...rest] = target;
    return {
      scopePath: normalizeScopePath(scopeRaw),
      uidOrId: uidOrId === null || uidOrId === undefined ? null : String(uidOrId),
      rest,
    };
  }
  if (target && typeof target === "object") {
    return {
      scopePath: normalizeScopePath(target.scope_path),
      uidOrId: target.uid !== null && target.uid !== undefined
        ? String(target.uid)
        : (target.id !== null && target.id !== undefined ? String(target.id) : null),
      rest: [],
    };
  }
  if (target === null || target === undefined) {
    return { scopePath: [], uidOrId: null, rest: [] };
  }
  return { scopePath: [], uidOrId: String(target), rest: [] };
}

function requireRootScope(parsed, opKind) {
  if (parsed.scopePath.length > 0) {
    throw new DeltaDiagnosticError(
      `${opKind} only supports root-scope graph edits in the browser adapter.`,
      DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
      { op: opKind, scope_path: parsed.scopePath },
    );
  }
}

function resolveNodeFromIndex(index, uidOrId) {
  if (uidOrId === null || uidOrId === undefined || uidOrId === "") {
    return null;
  }
  const asString = String(uidOrId);
  return index.byUid.get(asString) || index.byId.get(asString) || null;
}

function resolveNodeFromGraph(graph, uidOrId) {
  return resolveNodeFromIndex(buildGraphIndex(graph), uidOrId);
}

function findSlotIndex(slots, ref, fallbackKey = "name") {
  if (!Array.isArray(slots)) {
    return -1;
  }
  if (typeof ref === "number" && Number.isInteger(ref)) {
    return ref >= 0 && ref < slots.length ? ref : -1;
  }
  const normalized = String(ref);
  for (let index = 0; index < slots.length; index += 1) {
    const slot = slots[index];
    if (String(slot?.[fallbackKey]) === normalized || String(slot?.label) === normalized) {
      return index;
    }
    if (String(index) === normalized) {
      return index;
    }
  }
  return -1;
}

function findWidgetFieldIndex(node, ref, referenceNode = null) {
  const directIndex = findSlotIndex(node?.widgets, ref, "name");
  if (directIndex >= 0) {
    return directIndex;
  }
  // A live native node is the only trustworthy carrier map when ComfyUI adds
  // auxiliary widgets that are serialized in widgets_values but do not have a
  // corresponding input descriptor (for example KSampler's
  // control_after_generate widget). Its widget order is the serialization
  // order, so use it before attempting the descriptor-only fallback.
  const referenceIndex = findSlotIndex(referenceNode?.widgets, ref, "name");
  if (referenceIndex >= 0) {
    return referenceIndex;
  }
  // Serialized ComfyUI graphs normally omit the live `widgets` array. Their
  // input slots retain widget descriptors, while widgets_values contains only
  // widget-backed inputs (not linked sockets). This ordinal is safe only when
  // every serialized widget has a descriptor; otherwise hidden/auxiliary
  // widgets make the mapping ambiguous and we must fail closed.
  const normalized = String(ref);
  const inputs = Array.isArray(node?.inputs) ? node.inputs : [];
  const describedWidgetCount = inputs.filter((input) => Boolean(input?.widget)).length;
  if (
    Array.isArray(node?.widgets_values)
    && describedWidgetCount !== node.widgets_values.length
  ) {
    return -1;
  }
  let widgetIndex = 0;
  for (const input of inputs) {
    const descriptor = input?.widget;
    if (!descriptor) {
      continue;
    }
    const names = [
      descriptor && typeof descriptor === "object" ? descriptor.name : descriptor,
      input?.name,
      input?.label,
      input?.localized_name,
    ];
    if (names.some((name) => name !== null && name !== undefined && String(name) === normalized)) {
      return widgetIndex;
    }
    widgetIndex += 1;
  }
  return -1;
}

function getWidgetFieldValue(node, index) {
  if (index < 0) {
    return undefined;
  }
  if (Array.isArray(node?.widgets_values) && index < node.widgets_values.length) {
    return node.widgets_values[index];
  }
  return Array.isArray(node?.widgets) ? node.widgets[index]?.value : undefined;
}

function setWidgetFieldValue(node, index, value) {
  if (index < 0) {
    return false;
  }
  const cloned = cloneJson(value);
  let resolved = false;
  if (Array.isArray(node?.widgets) && node.widgets[index]) {
    node.widgets[index].value = cloned;
    resolved = true;
  }
  if (Array.isArray(node?.widgets_values) && index < node.widgets_values.length) {
    node.widgets_values[index] = cloned;
    resolved = true;
  }
  return resolved;
}

function getNodeFieldValue(node, path, { referenceNode = null } = {}) {
  if (!Array.isArray(path) || path.length === 0) {
    return undefined;
  }
  const [head, ...rest] = path;
  if (head === "widgets_values") {
    const index = Number(rest[0]);
    return getWidgetFieldValue(node, index);
  }
  if (head === "widgets") {
    const index = findSlotIndex(node.widgets, rest[0], "name");
    if (index < 0) {
      return undefined;
    }
    if (rest.length === 1) {
      return node.widgets[index];
    }
    return node.widgets?.[index]?.[rest[1]];
  }
  if (head === "inputs" || head === "outputs") {
    const slots = Array.isArray(node[head]) ? node[head] : [];
    const index = findSlotIndex(slots, rest[0], "name");
    if (index < 0) {
      return undefined;
    }
    if (rest.length === 1) {
      return slots[index];
    }
    return slots[index]?.[rest[1]];
  }
  if (rest.length === 0) {
    const widgetIndex = findWidgetFieldIndex(node, head, referenceNode);
    if (widgetIndex >= 0) {
      return getWidgetFieldValue(node, widgetIndex);
    }
    return undefined;
  }
  let cursor = node;
  const segments = [head, ...rest];
  for (const segment of segments) {
    if (!cursor || typeof cursor !== "object") {
      return undefined;
    }
    cursor = cursor[segment];
  }
  return cursor;
}

function setNodeFieldValue(node, path, value, { referenceNode = null } = {}) {
  if (!Array.isArray(path) || path.length === 0) {
    throw new Error("set_node_field target is missing a field path.");
  }
  const [head, ...rest] = path;
  if (head === "widgets_values") {
    const index = Number(rest[0]);
    if (!Number.isInteger(index) || index < 0 || !setWidgetFieldValue(node, index, value)) {
      throw new Error("Cannot resolve widgets_values target on live node.");
    }
    return;
  }
  if (head === "widgets") {
    const index = findSlotIndex(node.widgets, rest[0], "name");
    if (index < 0 || rest.length < 2) {
      throw new Error("Cannot resolve widgets target on live node.");
    }
    node.widgets[index][rest[1]] = cloneJson(value);
    return;
  }
  if (head === "inputs" || head === "outputs") {
    const slots = Array.isArray(node[head]) ? node[head] : null;
    const index = findSlotIndex(slots, rest[0], "name");
    if (!slots || index < 0 || rest.length < 2) {
      throw new Error(`Cannot resolve ${head} target on live node.`);
    }
    slots[index][rest[1]] = cloneJson(value);
    return;
  }
  if (rest.length === 0) {
    const widgetIndex = findWidgetFieldIndex(node, head, referenceNode);
    if (widgetIndex >= 0) {
      if (!setWidgetFieldValue(node, widgetIndex, value)) {
        throw new Error(`Cannot resolve named widget target ${String(head)} on live node.`);
      }
      return;
    }
    throw new DeltaDiagnosticError(
      `Cannot resolve semantic field ${String(head)} to a live node widget.`,
      "unresolved_node_field",
      { field_path: String(head), node_type: node?.type ?? null },
    );
  }
  let cursor = node;
  const segments = [head, ...rest];
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index];
    if (!cursor[segment] || typeof cursor[segment] !== "object") {
      cursor[segment] = {};
    }
    cursor = cursor[segment];
  }
  cursor[segments[segments.length - 1]] = cloneJson(value);
}

/**
 * Centralized transitional link key mapping.
 *
 * LiteGraph serialized links can appear in two shapes:
 *   - Legacy array:  [id, origin_id, origin_slot, target_id, target_slot, type]
 *   - Object/map:    {id, origin_id, origin_slot, target_id, target_slot, type}
 *
 * This function normalizes either shape into a consistent object form.
 * All link-consuming code paths (iterateLinkRecords, findCandidateLinkForOp,
 * findExistingLinkByTarget, upsertLinkInSerializedGraph, removeLinkFromSerializedGraph,
 * removeLiveLink, upsertLiveLink) go through this single normalization entry point.
 *
 * @param {Array|object|null} raw
 * @returns {{id, origin_id, origin_slot, target_id, target_slot, type, raw}|null}
 */
function normalizeLinkRecord(raw) {
  if (Array.isArray(raw)) {
    return {
      id: raw[0],
      origin_id: raw[1],
      origin_slot: raw[2],
      target_id: raw[3],
      target_slot: raw[4],
      type: raw[5],
      raw,
    };
  }
  if (raw && typeof raw === "object") {
    return {
      id: raw.id,
      origin_id: raw.origin_id,
      origin_slot: raw.origin_slot,
      target_id: raw.target_id,
      target_slot: raw.target_slot,
      type: raw.type,
      raw,
    };
  }
  return null;
}

function iterateLinkRecords(graph) {
  const records = [];
  const links = graph?.links;
  if (Array.isArray(links)) {
    for (const entry of links) {
      const normalized = normalizeLinkRecord(entry);
      if (normalized) {
        records.push(normalized);
      }
    }
    return records;
  }
  if (links && typeof links === "object") {
    for (const entry of Object.values(links)) {
      const normalized = normalizeLinkRecord(entry);
      if (normalized) {
        records.push(normalized);
      }
    }
  }
  return records;
}

function linkShapeForGraph(graph, link) {
  const prefersArray = Array.isArray(graph?.links) || graph?.links === undefined;
  if (prefersArray) {
    return [
      link.id,
      link.origin_id,
      link.origin_slot,
      link.target_id,
      link.target_slot,
      link.type ?? null,
    ];
  }
  return {
    id: link.id,
    origin_id: link.origin_id,
    origin_slot: link.origin_slot,
    target_id: link.target_id,
    target_slot: link.target_slot,
    type: link.type ?? null,
  };
}

function slotNameOrIndex(slot, index) {
  if (typeof slot?.name === "string" && slot.name) {
    return slot.name;
  }
  return index;
}

function resolveEndpoint(graph, ref, direction) {
  if (!Array.isArray(ref) || ref.length < 3) {
    throw new Error(`Invalid ${direction} endpoint reference.`);
  }
  const parsed = parseNodeTarget(ref.slice(0, 2));
  requireRootScope(parsed, `${direction}_link`);
  const node = resolveNodeFromGraph(graph, parsed.uidOrId);
  if (!node) {
    throw new Error(`Could not resolve ${direction} endpoint node ${parsed.uidOrId}.`);
  }
  const slots = direction === "from" ? node.outputs : node.inputs;
  const slotIndex = findSlotIndex(slots, ref[2], "name");
  if (slotIndex < 0) {
    throw new Error(`Could not resolve ${direction} endpoint slot ${String(ref[2])}.`);
  }
  return {
    node,
    nodeId: node.id,
    uid: canonicalNodeUid(node),
    slotIndex,
    slotName: slotNameOrIndex(slots?.[slotIndex], slotIndex),
  };
}

function findCandidateLinkForOp(candidateGraph, op) {
  const to = op?.to || op?.target;
  const from = op?.from;
  let desiredTarget = null;
  let desiredSource = null;
  if (to) {
    desiredTarget = resolveEndpoint(candidateGraph, to, "to");
  }
  if (from) {
    desiredSource = resolveEndpoint(candidateGraph, from, "from");
  }
  const links = iterateLinkRecords(candidateGraph);
  for (const link of links) {
    if (!link) {
      continue;
    }
    if (
      desiredTarget
      && (String(link.target_id) !== String(desiredTarget.nodeId) || Number(link.target_slot) !== desiredTarget.slotIndex)
    ) {
      continue;
    }
    if (
      desiredSource
      && (String(link.origin_id) !== String(desiredSource.nodeId) || Number(link.origin_slot) !== desiredSource.slotIndex)
    ) {
      continue;
    }
    const candidateIndex = buildGraphIndex(candidateGraph);
    const sourceNode = resolveNodeFromIndex(candidateIndex, String(link.origin_id));
    const targetNode = resolveNodeFromIndex(candidateIndex, String(link.target_id));
    return {
      id: link.id,
      origin_id: link.origin_id,
      origin_slot: link.origin_slot,
      origin_slot_name: slotNameOrIndex(sourceNode?.outputs?.[link.origin_slot], link.origin_slot),
      target_id: link.target_id,
      target_slot: link.target_slot,
      target_slot_name: slotNameOrIndex(targetNode?.inputs?.[link.target_slot], link.target_slot),
      type: link.type ?? null,
    };
  }
  throw new Error("Could not materialize candidate link payload from candidateGraph.");
}

function findExistingLinkByTarget(graph, targetNodeId, targetSlot) {
  const links = iterateLinkRecords(graph);
  return links.find(
    (link) => String(link.target_id) === String(targetNodeId) && Number(link.target_slot) === Number(targetSlot),
  ) || null;
}

function removeLinkFromSerializedGraph(graph, linkId) {
  const links = iterateLinkRecords(graph).filter((link) => String(link.id) !== String(linkId));
  graph.links = Array.isArray(graph.links)
    ? links.map((link) => linkShapeForGraph(graph, link))
    : Object.fromEntries(links.map((link) => [String(link.id), linkShapeForGraph(graph, link)]));
  const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  for (const node of nodes) {
    if (Array.isArray(node.inputs)) {
      for (const input of node.inputs) {
        if (String(input?.link) === String(linkId)) {
          input.link = null;
        }
      }
    }
    if (Array.isArray(node.outputs)) {
      for (const output of node.outputs) {
        if (Array.isArray(output?.links)) {
          output.links = output.links.filter((entry) => String(entry) !== String(linkId));
        }
      }
    }
  }
}

function upsertLinkInSerializedGraph(graph, link) {
  const prior = findExistingLinkByTarget(graph, link.target_id, link.target_slot);
  if (prior) {
    removeLinkFromSerializedGraph(graph, prior.id);
  }
  const normalizedLinks = iterateLinkRecords(graph);
  normalizedLinks.push({ ...link });
  graph.links = Array.isArray(graph.links)
    ? normalizedLinks.map((entry) => linkShapeForGraph(graph, entry))
    : Object.fromEntries(normalizedLinks.map((entry) => [String(entry.id), linkShapeForGraph(graph, entry)]));
  const index = buildGraphIndex(graph);
  const sourceNode = resolveNodeFromIndex(index, String(link.origin_id));
  const targetNode = resolveNodeFromIndex(index, String(link.target_id));
  if (!sourceNode || !targetNode) {
    throw new Error("Could not resolve source or target node while applying link payload.");
  }
  const output = Array.isArray(sourceNode.outputs) ? sourceNode.outputs[link.origin_slot] : null;
  if (!output || !Array.isArray(output.links)) {
    if (output) {
      output.links = [];
    }
  }
  if (output && !output.links.includes(link.id)) {
    output.links.push(link.id);
  }
  const input = Array.isArray(targetNode.inputs) ? targetNode.inputs[link.target_slot] : null;
  if (!input) {
    throw new Error("Could not resolve target input slot while applying link payload.");
  }
  input.link = link.id;
}

function materializeAddNodePayload(candidateGraph, op) {
  // Prefer explicit uid / node_id from canonical add_node ops.
  // Fall back to scope_path for legacy flat op shapes that lack explicit identity.
  const explicitUid = typeof op?.uid === "string" && op.uid ? op.uid : null;
  const explicitNodeId = typeof op?.node_id === "string" && op.node_id ? op.node_id : null;
  const scopePath =
    op?.scope_path !== null && op?.scope_path !== undefined ? String(op.scope_path) : "";

  const parsed = parseNodeTarget(
    op?.target
      ?? [Array.isArray(op?.scope_path) ? op.scope_path : "", explicitUid ?? explicitNodeId ?? scopePath],
  );
  requireRootScope(parsed, "add_node");

  // Prefer explicit uid, then explicit node_id, then scope_path / parsed fallback.
  const lookupKey = explicitUid || explicitNodeId || scopePath || parsed.uidOrId || null;
  if (!lookupKey) {
    throw new Error(
      "Cannot materialize added node: add_node op must provide explicit uid or node_id.",
    );
  }

  const candidateNode = resolveNodeFromGraph(candidateGraph, lookupKey);
  if (!candidateNode) {
    throw new Error(`Could not materialize added node ${String(lookupKey)} from candidateGraph.`);
  }
  return cloneJson(candidateNode);
}

function withoutSerializedLinkReferences(nodePayload) {
  const payload = cloneJson(nodePayload);
  if (Array.isArray(payload?.inputs)) {
    for (const input of payload.inputs) {
      if (input && typeof input === "object") input.link = null;
    }
  }
  if (Array.isArray(payload?.outputs)) {
    for (const output of payload.outputs) {
      if (output && typeof output === "object") output.links = null;
    }
  }
  return payload;
}

function appendCandidateLinksForAddedNodes(workingGraph, candidateGraph, plan) {
  const addedSteps = plan.filter((step) => step.op === "add_node");
  const addedIds = new Set(addedSteps.map((step) => String(step.nodePayload.id)));
  if (addedIds.size === 0) return;
  const links = iterateLinkRecords(candidateGraph)
    .filter((link) => addedIds.has(String(link.origin_id)) || addedIds.has(String(link.target_id)))
    .sort((a, b) => Number(a.id) - Number(b.id));
  for (const link of links) {
    const candidateIndex = buildGraphIndex(candidateGraph);
    const sourceNode = resolveNodeFromIndex(candidateIndex, String(link.origin_id));
    const targetNode = resolveNodeFromIndex(candidateIndex, String(link.target_id));
    const namedLink = {
      ...link,
      origin_slot_name: slotNameOrIndex(sourceNode?.outputs?.[link.origin_slot], link.origin_slot),
      target_slot_name: slotNameOrIndex(targetNode?.inputs?.[link.target_slot], link.target_slot),
    };
    // An add_node carries input intent in the canonical contract. Materialize
    // those edges explicitly so native LiteGraph nodes are never configured
    // with link ids that are absent from graph.links.
    upsertLinkInSerializedGraph(workingGraph, link);
    const alreadyPlanned = plan.some((step) => step.op === "upsert_link"
      && String(step.link?.origin_id) === String(link.origin_id)
      && Number(step.link?.origin_slot) === Number(link.origin_slot)
      && String(step.link?.target_id) === String(link.target_id)
      && Number(step.link?.target_slot) === Number(link.target_slot));
    if (!alreadyPlanned) {
      // Attribute a derived edge to the latest persisted add_node needed for
      // that edge. This guarantees every endpoint exists before the edge is
      // executed while preserving monotonic persisted-op provenance.
      const sourceStep = addedSteps
        .filter(
          (step) => String(step.nodePayload.id) === String(link.origin_id)
            || String(step.nodePayload.id) === String(link.target_id),
        )
        .sort((left, right) => right.source_op_index - left.source_op_index)[0];
      plan.push({
        op: "upsert_link",
        link: namedLink,
        derivedFromAddNode: true,
        source_op_index: sourceStep?.source_op_index ?? null,
        source_op_kind: "add_node",
      });
    }
  }
}

function resolveLiteGraph(app) {
  return app?.LiteGraph
    || app?.canvas?.LiteGraph
    || globalThis?.LiteGraph
    || globalThis?.window?.LiteGraph
    || null;
}

function resolveFactory(app) {
  const liteGraph = resolveLiteGraph(app);
  return typeof liteGraph?.createNode === "function" ? liteGraph.createNode.bind(liteGraph) : null;
}

function registryDependencyForType(options, classType) {
  const dependencies = Array.isArray(options?.runtimeDependencies)
    ? options.runtimeDependencies
    : [];
  const dependency = dependencies.find(
    (entry) => entry && entry.class_type === classType,
  ) || null;
  if (dependency?.availability !== "registry_resolvable") {
    return null;
  }
  // "registry_resolvable" is permission only when the backend supplied
  // concrete resolver evidence for this exact class.  A bare label must not
  // turn arbitrary model output into a browser node.
  const candidates = Array.isArray(dependency.resolver_candidates)
    ? dependency.resolver_candidates
    : [];
  // The backend has already bound this dependency record to class_type and
  // resolved ambiguity.  Do not reinterpret provider-specific class lists in
  // the browser: evidence-only Comfy Registry receipts intentionally may have
  // no expected_classes.  Require the durable resolver receipt fields instead.
  const evidenced = candidates.some((candidate) => (
    typeof candidate?.stable_install_hash === "string"
    && candidate.stable_install_hash.length > 0
    && candidate?.pack
    && typeof candidate.pack === "object"
    && typeof candidate.pack.source === "string"
    && candidate.pack.source.length > 0
  ));
  return evidenced ? dependency : null;
}

function placeholderSerialization(node, candidatePayload) {
  const payload = cloneJson(candidatePayload);
  for (const key of [
    "id",
    "type",
    "pos",
    "size",
    "flags",
    "order",
    "mode",
    "properties",
    "inputs",
    "outputs",
    "widgets_values",
  ]) {
    if (node[key] !== undefined) {
      payload[key] = (key === "pos" || key === "size") && node[key]?.length >= 2
        ? [Number(node[key][0]), Number(node[key][1])]
        : cloneJson(node[key]);
    }
  }
  return payload;
}

function materializeRegistryPlaceholder(app, payload, dependency) {
  const liteGraph = resolveLiteGraph(app);
  const NodeBase = liteGraph?.LGraphNode
    || globalThis?.LGraphNode
    || globalThis?.window?.LGraphNode
    || null;
  if (typeof NodeBase !== "function") {
    throw new Error(
      `Registry-backed node ${JSON.stringify(payload?.type)} is not installed and this LiteGraph build exposes no generic LGraphNode constructor.`,
    );
  }
  const node = new NodeBase(payload?.title || payload?.type || "Missing custom node");
  if (!node || typeof node !== "object") {
    throw new Error(`Could not materialize registry-backed placeholder for ${JSON.stringify(payload?.type)}.`);
  }

  const cleanPayload = cloneJson(payload);
  if (typeof node.configure === "function") {
    node.configure(cleanPayload);
  } else {
    Object.assign(node, cleanPayload);
  }
  // A generic node has no registered Comfy constructor to build its ports or
  // widgets.  The candidate snapshot is the typed authority for review, so
  // reproduce those carriers exactly and keep link ids clear until explicit
  // upsert_link operations run.
  node.id = cleanPayload.id;
  node.type = cleanPayload.type;
  node.pos = cloneJson(cleanPayload.pos || [0, 0]);
  node.size = cloneJson(cleanPayload.size || [320, 180]);
  node.flags = cloneJson(cleanPayload.flags || {});
  node.order = cleanPayload.order;
  node.mode = cleanPayload.mode;
  node.properties = cloneJson(cleanPayload.properties || {});
  node.inputs = cloneJson(cleanPayload.inputs || []);
  node.outputs = cloneJson(cleanPayload.outputs || []);
  node.widgets_values = cloneJson(cleanPayload.widgets_values || []);
  if (node.__vibecomfyOriginal && typeof node.__vibecomfyOriginal === "object") {
    node.__vibecomfyOriginal = cloneJson(cleanPayload);
  }
  Object.defineProperties(node, {
    __vibecomfyRegistryPlaceholder: {
      configurable: true,
      enumerable: false,
      value: true,
    },
    __vibecomfyRegistryDependency: {
      configurable: true,
      enumerable: false,
      value: cloneJson(dependency),
    },
    serialize: {
      configurable: true,
      enumerable: false,
      value() {
        return placeholderSerialization(this, cleanPayload);
      },
    },
  });
  return node;
}

function prepareLiveAddNodes(app, plan, options) {
  const factory = resolveFactory(app);
  const prepared = new Map();
  for (const step of plan) {
    if (step.op !== "add_node") continue;
    const classType = step.nodePayload?.type;
    let node = typeof factory === "function" ? factory(classType) : null;
    if (!node) {
      const dependency = registryDependencyForType(options, classType);
      if (!dependency) {
        throw new Error(
          `LiteGraph.createNode(${JSON.stringify(classType)}) returned no node and the class has no exact registry resolution evidence.`,
        );
      }
      node = materializeRegistryPlaceholder(app, step.nodePayload, dependency);
    }
    prepared.set(step, node);
  }
  return prepared;
}

function positivePair(value) {
  if (!Array.isArray(value) && !(value && typeof value.length === "number")) {
    return null;
  }
  const w = Number(value[0]);
  const h = Number(value[1]);
  return Number.isFinite(w) && Number.isFinite(h) && w > 0 && h > 0 ? { w, h } : null;
}

function serializedNodeSize(node) {
  return positivePair(node?.size) || { w: 320, h: 180 };
}

/**
 * Ask the installed LiteGraph node class how large it really is.  This must
 * run in the browser: object_info describes inputs, but custom widgets and
 * Comfy extensions determine their final rendered height client-side.
 */
function measureNativeNodePayload(factory, payload) {
  if (typeof factory !== "function" || !payload?.type) {
    return null;
  }
  try {
    const node = factory(payload.type);
    if (!node) return null;
    if (typeof node.configure === "function") {
      node.configure(cloneJson(payload));
    } else {
      Object.assign(node, cloneJson(payload));
    }
    let size = positivePair(node.size) || serializedNodeSize(payload);
    let measured = false;
    if (typeof node.computeSize === "function") {
      const computed = positivePair(node.computeSize());
      if (computed) {
        size = { w: Math.max(size.w, computed.w), h: Math.max(size.h, computed.h) };
        measured = true;
      }
    }
    if (typeof node.getBounding === "function") {
      const bounds = node.getBounding();
      const width = Number(bounds?.[2]);
      const height = Number(bounds?.[3]);
      const titleHeight = Number(globalThis?.LiteGraph?.NODE_TITLE_HEIGHT) || 30;
      if (Number.isFinite(width) && width > 0) size.w = Math.max(size.w, width);
      // LiteGraph bounds include the title, while serialized node.size does not.
      if (Number.isFinite(height) && height > titleHeight) {
        size.h = Math.max(size.h, height - titleHeight);
        measured = true;
      }
    }
    return measured ? size : null;
  } catch (_error) {
    // A malformed extension node must never block review; retain server geometry.
    return null;
  }
}

function rectanglesOverlap(a, b) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

/**
 * Project a server candidate onto the actual installed node widgets before it
 * is previewed or applied.  Only newly-added nodes are moved: existing canvas
 * nodes remain authoritative obstacles.  The server candidate itself and its
 * hash remain untouched by returning a clone.
 */
export function projectCandidateGraphToRuntimeLayout(app, candidateGraph) {
  const projected = cloneJson(candidateGraph);
  if (!projected || !Array.isArray(projected.nodes)) return projected;

  const graph = getLiveGraph(app);
  const live = liveNodeIndex(graph);
  const factory = resolveFactory(app);
  const entries = projected.nodes.map((node, index) => {
    const uid = canonicalNodeUid(node);
    const liveNode = (uid && live.byUid.get(uid)) || live.byId.get(String(node?.id));
    // Existing nodes are drawn from the live canvas by the overlay and must
    // remain byte-identical to the server candidate for review/CAS.  Only a
    // newly created node needs browser-native measurement.
    const measuredNative = liveNode ? null : measureNativeNodePayload(factory, node);
    const measured = measuredNative || serializedNodeSize(node);
    if (measuredNative) {
      node.size = [Math.ceil(measured.w), Math.ceil(measured.h)];
    }
    return {
      node,
      index,
      isNew: !liveNode,
      measured: Boolean(measuredNative),
      rect: { x: Number(node?.pos?.[0]) || 0, y: Number(node?.pos?.[1]) || 0, w: measured.w, h: measured.h },
    };
  });

  // No browser-native measurement means this runtime cannot improve on the
  // server candidate.  Crucially, preserve its exact payload/hash shape.
  if (!entries.some((entry) => entry.measured)) return projected;

  // Stable top-to-bottom ordering retains the backend's intended topology.
  const placed = [];
  for (const entry of [...entries].sort((a, b) => a.rect.y - b.rect.y || a.rect.x - b.rect.x || a.index - b.index)) {
    if (entry.isNew) {
      let moved = true;
      while (moved) {
        moved = false;
        for (const obstacle of placed) {
          if (!rectanglesOverlap(entry.rect, obstacle.rect)) continue;
          entry.rect.y = obstacle.rect.y + obstacle.rect.h + 24;
          moved = true;
        }
      }
      if (entry.rect.y !== (Number(entry.node?.pos?.[1]) || 0)) {
        entry.node.pos = [Math.round(entry.rect.x), Math.round(entry.rect.y)];
      }
    }
    placed.push(entry);
  }
  return projected;
}

function liveNodeIndex(graph) {
  const byUid = new Map();
  const byId = new Map();
  const nodes = Array.isArray(graph?._nodes) ? graph._nodes : [];
  for (const node of nodes) {
    const uid = canonicalNodeUid(node);
    if (uid && !byUid.has(uid)) {
      byUid.set(uid, node);
    }
    if (node?.id !== null && node?.id !== undefined) {
      const idKey = String(node.id);
      if (!byId.has(idKey)) {
        byId.set(idKey, node);
      }
    }
  }
  return { byUid, byId };
}

function resolveLiveNode(graph, uidOrId) {
  const index = liveNodeIndex(graph);
  return resolveNodeFromIndex(index, uidOrId);
}

function liveLinkEntries(graph) {
  const links = graph?.links;
  if (Array.isArray(links)) {
    return links;
  }
  // Current LiteGraph exposes a Proxy-wrapped Map<LLink>. Its entries are not
  // enumerable object properties, so Object.values() silently loses every
  // link. Prefer the Map API whenever it is present.
  if (links && typeof links.values === "function") {
    return Array.from(links.values());
  }
  if (links && typeof links === "object") {
    return Object.values(links);
  }
  return [];
}

function liveLinkMapSet(graph, link) {
  if (graph?.links && typeof graph.links.set === "function") {
    throw new Error(
      "Live LiteGraph Map links must be created through the native node.connect() API.",
    );
  }
  if (!graph.links || typeof graph.links !== "object" || Array.isArray(graph.links)) {
    graph.links = {};
  }
  graph.links[String(link.id)] = link;
}

function liveLinkMapDelete(graph, linkId) {
  if (Array.isArray(graph?.links)) {
    graph.links = graph.links.filter((entry) => String(normalizeLinkRecord(entry)?.id) !== String(linkId));
    return;
  }
  if (graph?.links && typeof graph.links.delete === "function") {
    graph.links.delete(linkId);
    graph.links.delete(String(linkId));
    return;
  }
  if (graph?.links && typeof graph.links === "object") {
    delete graph.links[String(linkId)];
  }
}

function removeLiveLink(graph, linkId) {
  const normalizedLinks = liveLinkEntries(graph).map((entry) => normalizeLinkRecord(entry)).filter(Boolean);
  const target = normalizedLinks.find((entry) => String(entry.id) === String(linkId));
  if (!target) {
    return;
  }
  // Native removal owns all Map<LLink>, node-slot, reroute, and graph revision
  // bookkeeping. Manually deleting a modern LLink leaves those indexes split.
  if (typeof graph?.removeLink === "function") {
    graph.removeLink(target.id);
    return;
  }
  const sourceNode = resolveLiveNode(graph, String(target.origin_id));
  const targetNode = resolveLiveNode(graph, String(target.target_id));
  if (sourceNode?.outputs?.[target.origin_slot]?.links) {
    sourceNode.outputs[target.origin_slot].links = sourceNode.outputs[target.origin_slot].links
      .filter((entry) => String(entry) !== String(linkId));
  }
  if (targetNode?.inputs?.[target.target_slot]) {
    targetNode.inputs[target.target_slot].link = null;
  }
  liveLinkMapDelete(graph, linkId);
}

function upsertLiveLink(graph, link) {
  const sourceNode = resolveLiveNode(graph, String(link.origin_id));
  const targetNode = resolveLiveNode(graph, String(link.target_id));
  if (!sourceNode || !targetNode) {
    throw new Error("Could not resolve live nodes for link mutation.");
  }
  const originSlot = typeof link.origin_slot_name === "string"
    ? findSlotIndex(sourceNode.outputs, link.origin_slot_name, "name")
    : Number(link.origin_slot);
  const targetSlot = typeof link.target_slot_name === "string"
    ? findSlotIndex(targetNode.inputs, link.target_slot_name, "name")
    : Number(link.target_slot);
  if (originSlot < 0 || targetSlot < 0) {
    throw new Error(
      `Could not resolve live named slots for link mutation: ${String(link.origin_slot_name)} -> ${String(link.target_slot_name)}.`,
    );
  }
  const prior = liveLinkEntries(graph)
    .map((entry) => normalizeLinkRecord(entry))
    .find((entry) => entry && String(entry.target_id) === String(link.target_id) && Number(entry.target_slot) === targetSlot);
  if (prior) {
    removeLiveLink(graph, prior.id);
  }
  const output = Array.isArray(sourceNode.outputs) ? sourceNode.outputs[originSlot] : null;
  const input = Array.isArray(targetNode.inputs) ? targetNode.inputs[targetSlot] : null;
  if (!output || !input) {
    throw new Error("Could not resolve live slots for link mutation.");
  }
  // Modern LiteGraph stores class instances in a Proxy-wrapped Map. A plain
  // object inserted into graph.links makes the next graph.serialize() crash at
  // LLink.serialize(). Let LiteGraph construct and register the link itself;
  // structural transaction authority intentionally does not depend on link ids.
  if (typeof sourceNode.connect === "function") {
    const connected = sourceNode.connect(originSlot, targetNode, targetSlot);
    if (connected === false || connected == null) {
      throw new Error(
        `LiteGraph node.connect() did not create ${String(link.origin_slot_name ?? originSlot)} -> ${String(link.target_slot_name ?? targetSlot)}.`,
      );
    }
    return;
  }
  if (graph?.links && typeof graph.links.set === "function") {
    throw new Error("Modern LiteGraph link mutation requires node.connect().");
  }
  if (!Array.isArray(output.links)) {
    output.links = [];
  }
  if (!output.links.includes(link.id)) {
    output.links.push(link.id);
  }
  input.link = link.id;
  liveLinkMapSet(graph, { ...link });
}

function decorateCandidateNodePayload(options, nodePayload, context) {
  if (typeof options?.decorateCandidateNodePayload === "function") {
    options.decorateCandidateNodePayload(nodePayload, context);
  }
}

function decorateLiveNode(options, liveNode, context) {
  if (typeof options?.decorateLiveNode === "function") {
    options.decorateLiveNode(liveNode, context);
  }
}

/**
 * Verify that the candidate graph is consistent with the delta ops before
 * preflighting.  Checks that nodes referenced by add_node ops can be found in
 * the candidate graph and that link endpoints are resolvable.
 *
 * @param {object} candidateGraph
 * @param {Array<object>} deltaOps — normalized canonical ops
 * @throws {DeltaDiagnosticError|Error} on consistency violations
 */
function verifyCandidateGraphConsistency(candidateGraph, deltaOps) {
  const candidateIndex = buildGraphIndex(candidateGraph);

  for (let i = 0; i < deltaOps.length; i++) {
    const op = deltaOps[i];
    const opKind = op.op;

    if (opKind === "add_node") {
      const uid = typeof op.uid === "string" && op.uid ? op.uid : null;
      const nodeId = typeof op.node_id === "string" && op.node_id ? op.node_id : null;
      const lookupKey = uid || nodeId || null;
      if (!lookupKey) {
        continue; // identity will be resolved at apply time
      }
      const candidateNode = resolveNodeFromIndex(candidateIndex, lookupKey);
      if (!candidateNode) {
        throw new Error(
          `Candidate graph consistency failure: add_node op at index ${i} references ` +
          `node "${lookupKey}" which is absent from the candidate graph.`,
        );
      }
    }

    if (opKind === "upsert_link") {
      const fromRef = op.from;
      const toRef = op.to;
      if (Array.isArray(fromRef) && fromRef.length >= 2) {
        const fromParsed = parseNodeTarget(fromRef.slice(0, 2));
        if (fromParsed.uidOrId) {
          const fromNode = resolveNodeFromIndex(candidateIndex, fromParsed.uidOrId);
          if (!fromNode) {
            throw new Error(
              `Candidate graph consistency failure: upsert_link at index ${i} ` +
              `references source node "${fromParsed.uidOrId}" absent from candidate graph.`,
            );
          }
        }
      }
      if (Array.isArray(toRef) && toRef.length >= 2) {
        const toParsed = parseNodeTarget(toRef.slice(0, 2));
        if (toParsed.uidOrId) {
          const toNode = resolveNodeFromIndex(candidateIndex, toParsed.uidOrId);
          if (!toNode) {
            throw new Error(
              `Candidate graph consistency failure: upsert_link at index ${i} ` +
              `references target node "${toParsed.uidOrId}" absent from candidate graph.`,
            );
          }
        }
      }
    }
  }
}

export function preflightDeltaPlan(liveGraphSnapshot, candidateGraph, deltaOps, options = {}) {
  if (!Array.isArray(deltaOps)) {
    throw new Error("deltaOps must be an array.");
  }
  if (!candidateGraph || typeof candidateGraph !== "object") {
    throw new Error("candidateGraph must be an object.");
  }

  // Validate that all ops are canonical before preflighting.
  for (let i = 0; i < deltaOps.length; i++) {
    const op = deltaOps[i];
    if (!op || typeof op !== "object" || typeof op.op !== "string") {
      throw new Error("deltaOps contains an invalid operation entry.");
    }
    if (!CANONICAL_DELTA_OP_NAMES.includes(op.op)) {
      throw new DeltaDiagnosticError(
        `Unsupported delta op kind ${op.op} at index ${i}. Expected one of: ${CANONICAL_DELTA_OP_NAMES.join(", ")}.`,
        "malformed_delta",
        { index: i, op: op.op },
      );
    }
  }

  const workingGraph = cloneJson(liveGraphSnapshot) || { nodes: [], links: [] };
  const plan = [];
  for (let sourceOpIndex = 0; sourceOpIndex < deltaOps.length; sourceOpIndex += 1) {
    const op = deltaOps[sourceOpIndex];
    const opKind = op.op;
    const authority = { source_op_index: sourceOpIndex, source_op_kind: opKind };
    if (opKind === "set_node_field") {
      const parsed = parseNodeTarget(op.target);
      requireRootScope(parsed, opKind);
      const node = resolveNodeFromGraph(workingGraph, parsed.uidOrId);
      if (!node) {
        throw new Error(`Could not resolve node ${String(parsed.uidOrId)} for set_node_field.`);
      }
      const fieldPath = decodeNodeFieldPathV1(parsed.rest);
      const referenceNode = typeof options.widgetReferenceNodeFor === "function"
        ? options.widgetReferenceNodeFor(parsed.uidOrId)
        : null;
      const desiredValue = getNodeFieldValue(
        resolveNodeFromGraph(candidateGraph, parsed.uidOrId) || node,
        fieldPath,
        { referenceNode },
      );
      if (desiredValue === undefined) {
        throw new DeltaDiagnosticError(
          `Could not resolve set_node_field ${fieldPath.join(".")} on the candidate node.`,
          "unresolved_node_field",
          { uid: parsed.uidOrId, field_path: fieldPath.join(".") },
        );
      }
      if (canonicalJsonString(desiredValue) !== canonicalJsonString(op.value)) {
        throw new DeltaDiagnosticError(
          `Candidate value for ${fieldPath.join(".")} disagrees with canonical delta authority.`,
          "candidate_delta_value_mismatch",
          { uid: parsed.uidOrId, field_path: fieldPath.join(".") },
        );
      }
      setNodeFieldValue(node, fieldPath, desiredValue, { referenceNode });
      plan.push({ op: opKind, uidOrId: parsed.uidOrId, fieldPath, value: cloneJson(desiredValue), ...authority });
      continue;
    }
    if (opKind === "set_mode") {
      const parsed = parseNodeTarget(op.target);
      requireRootScope(parsed, opKind);
      const node = resolveNodeFromGraph(workingGraph, parsed.uidOrId);
      const candidateNode = resolveNodeFromGraph(candidateGraph, parsed.uidOrId);
      if (!node || !candidateNode) {
        throw new Error(`Could not resolve node ${String(parsed.uidOrId)} for set_mode.`);
      }
      node.mode = candidateNode.mode ?? op.mode ?? op.value;
      plan.push({ op: opKind, uidOrId: parsed.uidOrId, mode: node.mode, ...authority });
      continue;
    }
    if (opKind === "upsert_link") {
      const link = findCandidateLinkForOp(candidateGraph, op);
      upsertLinkInSerializedGraph(workingGraph, link);
      plan.push({ op: opKind, link: cloneJson(link), ...authority });
      continue;
    }
    if (opKind === "remove_link") {
      const targetRef = op.to || op.target;
      const target = resolveEndpoint(workingGraph, targetRef, "to");
      const existing = findExistingLinkByTarget(workingGraph, target.nodeId, target.slotIndex);
      if (!existing) {
        plan.push({ op: opKind, linkId: null, targetUidOrId: target.uid || String(target.nodeId), targetSlot: target.slotIndex, ...authority });
        continue;
      }
      removeLinkFromSerializedGraph(workingGraph, existing.id);
      plan.push({ op: opKind, linkId: existing.id, targetUidOrId: target.uid || String(target.nodeId), targetSlot: target.slotIndex, ...authority });
      continue;
    }
    if (opKind === "add_node") {
      const nodePayload = materializeAddNodePayload(candidateGraph, op);
      decorateCandidateNodePayload(options, nodePayload, { op });
      const existing = resolveNodeFromGraph(workingGraph, canonicalNodeUid(nodePayload) || String(nodePayload.id));
      if (existing) {
        throw new Error(`Cannot add node ${canonicalNodeUid(nodePayload) || nodePayload.id}; it already exists.`);
      }
      if (!Array.isArray(workingGraph.nodes)) {
        workingGraph.nodes = [];
      }
      workingGraph.nodes.push(nodePayload);
      // Links are applied as explicit follow-up operations once every endpoint
      // exists. Passing candidate link ids into native configure() first can
      // corrupt LiteGraph's link index (and has caused recursive failures).
      plan.push({ op: opKind, nodePayload: withoutSerializedLinkReferences(nodePayload), ...authority });
      continue;
    }
    if (opKind === "remove_node") {
      // Canonical root-scope remove_node operations carry the same explicit
      // uid/node_id authority as add_node.  Do not silently treat that shape
      // as an absent node merely because it omits the legacy `target` tuple.
      const explicitUid = typeof op.uid === "string" && op.uid ? op.uid : null;
      const explicitNodeId = typeof op.node_id === "string" && op.node_id ? op.node_id : null;
      const parsed = parseNodeTarget(
        op.target
          ?? [Array.isArray(op.scope_path) ? op.scope_path : (op.scope_path ?? ""), explicitUid ?? explicitNodeId],
      );
      requireRootScope(parsed, opKind);
      const node = resolveNodeFromGraph(workingGraph, parsed.uidOrId);
      if (!node) {
        plan.push({ op: opKind, uidOrId: parsed.uidOrId, alreadyAbsent: true, ...authority });
        continue;
      }
      const linkRecords = iterateLinkRecords(workingGraph).filter(
        (link) => String(link.origin_id) === String(node.id) || String(link.target_id) === String(node.id),
      );
      for (const link of linkRecords) {
        removeLinkFromSerializedGraph(workingGraph, link.id);
      }
      workingGraph.nodes = workingGraph.nodes.filter((entry) => entry !== node);
      plan.push({ op: opKind, uidOrId: parsed.uidOrId, alreadyAbsent: false, ...authority });
      continue;
    }
    throw new Error(`Unsupported delta op kind ${opKind}.`);
  }

  appendCandidateLinksForAddedNodes(workingGraph, candidateGraph, plan);
  // Derived link materialization belongs to the add_node operation that
  // authored it.  appendCandidateLinksForAddedNodes runs after every
  // explicit op so all endpoints are known; restore persisted operation
  // order before execution/audit while keeping the primary step first.
  plan.sort((left, right) => {
    const sourceOrder = left.source_op_index - right.source_op_index;
    if (sourceOrder !== 0) return sourceOrder;
    return Number(left.derivedFromAddNode === true) - Number(right.derivedFromAddNode === true);
  });

  // Verify candidate graph consistency with the delta ops after planning.
  verifyCandidateGraphConsistency(candidateGraph, deltaOps);

  return { plan, nextGraph: workingGraph };
}

function applyPreflightPlanLive(app, capability, plan, options = {}, preparedAddNodes = new Map()) {
  const graph = getLiveGraph(app);
  if (!graph) {
    throw new Error("No live LiteGraph instance available.");
  }
  for (const step of plan) {
    if (step.op === "set_node_field") {
      const liveNode = resolveLiveNode(graph, step.uidOrId);
      if (!liveNode) {
        throw new Error(`Could not resolve live node ${String(step.uidOrId)}.`);
      }
      setNodeFieldValue(liveNode, step.fieldPath, step.value);
      decorateLiveNode(options, liveNode, { op: step });
      continue;
    }
    if (step.op === "set_mode") {
      const liveNode = resolveLiveNode(graph, step.uidOrId);
      if (!liveNode) {
        throw new Error(`Could not resolve live node ${String(step.uidOrId)}.`);
      }
      liveNode.mode = step.mode;
      decorateLiveNode(options, liveNode, { op: step });
      continue;
    }
    if (step.op === "upsert_link") {
      upsertLiveLink(graph, step.link);
      continue;
    }
    if (step.op === "remove_link") {
      if (step.linkId !== null && step.linkId !== undefined) {
        removeLiveLink(graph, step.linkId);
      }
      continue;
    }
    if (step.op === "add_node") {
      if (typeof graph.add !== "function") {
        throw new Error("Live delta apply cannot add nodes without graph.add().");
      }
      const liveNode = preparedAddNodes.get(step) || null;
      if (!liveNode) {
        throw new Error(`Live add-node preflight did not prepare ${JSON.stringify(step.nodePayload.type)}.`);
      }
      graph.add(liveNode);
      if (liveNode.__vibecomfyRegistryPlaceholder !== true && typeof liveNode.configure === "function") {
        liveNode.configure(step.nodePayload);
      } else if (liveNode.__vibecomfyRegistryPlaceholder !== true) {
        Object.assign(liveNode, cloneJson(step.nodePayload));
      }
      decorateLiveNode(options, liveNode, { op: step, capability });
      continue;
    }
    if (step.op === "remove_node") {
      if (step.alreadyAbsent) {
        continue;
      }
      if (typeof graph.remove !== "function") {
        throw new Error("Live delta apply cannot remove nodes without graph.remove().");
      }
      const liveNode = resolveLiveNode(graph, step.uidOrId);
      if (!liveNode) {
        continue;
      }
      const connectedLinks = liveLinkEntries(graph).map((entry) => normalizeLinkRecord(entry)).filter(
        (link) => link && (String(link.origin_id) === String(liveNode.id) || String(link.target_id) === String(liveNode.id)),
      );
      for (const link of connectedLinks) {
        removeLiveLink(graph, link.id);
      }
      graph.remove(liveNode);
      continue;
    }
  }
  return graph;
}

function detectGraphDeltaApply(app) {
  return graphCapability(app, "delta_apply");
}

export function applyGraphDeltaInPlace(app, { deltaOps, candidateGraph }, options = {}) {
  const capability = detectGraphDeltaApply(app);
  const graph = getLiveGraph(app);
  if (!capability.available || !graph) {
    const error = new Error("The live LiteGraph instance does not support scoped in-place delta application.");
    error.code = "GRAPH_DELTA_APPLY_UNAVAILABLE";
    error.capability = capability;
    throw error;
  }

  // Require normalized canonical ops before proceeding.
  if (!Array.isArray(deltaOps)) {
    throw new DeltaDiagnosticError(
      "applyGraphDeltaInPlace requires a normalized deltaOps array.",
      "malformed_delta",
      {},
    );
  }
  for (let i = 0; i < deltaOps.length; i++) {
    const op = deltaOps[i];
    if (!op || typeof op !== "object" || typeof op.op !== "string") {
      throw new DeltaDiagnosticError(
        "deltaOps contains an invalid operation entry.",
        "malformed_delta",
        { index: i },
      );
    }
    if (!CANONICAL_DELTA_OP_NAMES.includes(op.op)) {
      throw new DeltaDiagnosticError(
        `Unsupported delta op kind ${op.op} at index ${i}. Expected one of: ${CANONICAL_DELTA_OP_NAMES.join(", ")}.`,
        "malformed_delta",
        { index: i, op: op.op },
      );
    }
  }

  const liveSnapshot = typeof graph.serialize === "function"
    ? graph.serialize()
    : null;
  if (!liveSnapshot || typeof liveSnapshot !== "object") {
    throw new Error("Could not serialize the live graph for delta preflight.");
  }

  let plan;
  let nextGraph;
  let preparedAddNodes;
  try {
    ({ plan, nextGraph } = preflightDeltaPlan(liveSnapshot, candidateGraph, deltaOps, {
      ...options,
      widgetReferenceNodeFor: options.widgetReferenceNodeFor
        || ((uidOrId) => resolveLiveNode(graph, uidOrId)),
    }));
    preparedAddNodes = capability.strategy === "harness-serialize-configure"
      ? new Map()
      : prepareLiveAddNodes(app, plan, options);
  } catch (error) {
    // Preflight is side-effect free. Mark that boundary explicitly so the
    // transaction controller rolls back the server lease without running an
    // inverse mutation against a canvas that was never changed.
    if (error && typeof error === "object") {
      error.canvasMutationStarted = false;
    }
    throw error;
  }
  if (capability.strategy === "harness-serialize-configure") {
    graph.clear();
    graph.configure(nextGraph);
    if (Array.isArray(plan)) {
      for (const step of plan) {
        if (step.op === "add_node") {
          const liveNode = resolveLiveNode(graph, canonicalNodeUid(step.nodePayload) || String(step.nodePayload.id));
          if (liveNode) {
            decorateLiveNode(options, liveNode, { op: step, capability });
          }
        }
      }
    }
  } else {
    applyPreflightPlanLive(app, capability, plan, options, preparedAddNodes);
  }

  if (options.repaint !== false) {
    repaintGraph(app, graph);
  }
  return { graph, capability, plan, nextGraph };
}

function serializedGroupKey(group) {
  if (group?.id === null || group?.id === undefined || String(group.id) === "") {
    const error = new Error("Layout group is missing a stable id.");
    error.code = "LAYOUT_GROUP_ID_REQUIRED";
    throw error;
  }
  return `id:${String(group.id)}`;
}

function configureLiveGroup(group, serialized) {
  const payload = cloneJson(serialized);
  group.id = payload.id;
  if (typeof group?.configure === "function") {
    group.configure(payload);
    group.id = payload.id;
    return;
  }
  group.id = payload.id ?? group.id;
  group.title = payload.title || "Group";
  group.color = payload.color;
  group.flags = cloneJson(payload.flags || {});
  const bounding = Array.isArray(payload.bounding) ? payload.bounding : null;
  if (!bounding || bounding.length < 4) {
    throw new Error(`Layout group ${String(group.title)} is missing canonical bounding geometry.`);
  }
  if (group?._bounding && typeof group._bounding.set === "function") {
    group._bounding.set(bounding);
  } else {
    group.pos = [bounding[0], bounding[1]];
    group.size = [bounding[2], bounding[3]];
    group.bounding = bounding.slice(0, 4);
  }
}

function setLiveNodeGeometry(liveNode, candidateNode) {
  const pos = Array.isArray(candidateNode?.pos) ? candidateNode.pos : null;
  const size = Array.isArray(candidateNode?.size) ? candidateNode.size : null;
  if (!pos || pos.length < 2 || !size || size.length < 2) {
    throw new Error(`Layout candidate node ${String(candidateNode?.id)} is missing position or size.`);
  }
  if (Array.isArray(liveNode.pos)) {
    liveNode.pos[0] = pos[0];
    liveNode.pos[1] = pos[1];
  } else {
    liveNode.pos = pos.slice(0, 2);
  }
  if (typeof liveNode.setSize === "function") {
    liveNode.setSize(size.slice(0, 2));
  } else if (Array.isArray(liveNode.size)) {
    liveNode.size[0] = size[0];
    liveNode.size[1] = size[1];
  } else {
    liveNode.size = size.slice(0, 2);
  }
}

function detectGraphLayoutApply(app) {
  return graphCapability(app, "layout_apply");
}

/**
 * Apply an authority-verified layout candidate without configuring the graph.
 * Only node position/size and native group objects may change; nodes, widgets,
 * modes, and links retain their live object identity.
 */
export function applyGraphLayoutInPlace(app, { candidateGraph }, options = {}) {
  const graph = getLiveGraph(app);
  const capability = detectGraphLayoutApply(app);
  if (!capability.available || !graph) {
    const error = new Error("The live LiteGraph instance does not support authoritative in-place layout application.");
    error.code = "GRAPH_LAYOUT_APPLY_UNAVAILABLE";
    error.capability = capability;
    throw error;
  }
  if (!candidateGraph || typeof candidateGraph !== "object") {
    throw new Error("candidateGraph must be an object.");
  }
  const definitions = candidateGraph.definitions;
  if (
    definitions
    && typeof definitions === "object"
    && !Array.isArray(definitions)
    && Object.keys(definitions).length > 0
  ) {
    const error = new Error("Nested-scope layout application is not supported.");
    error.code = "UNSUPPORTED_NESTED_LAYOUT_SCOPE";
    throw error;
  }
  for (const group of Array.isArray(candidateGraph.groups) ? candidateGraph.groups : []) {
    if (String(group?.scope_path ?? "") !== "") {
      const error = new Error("Nested-scope layout groups are not supported.");
      error.code = "UNSUPPORTED_NESTED_LAYOUT_SCOPE";
      throw error;
    }
  }

  const liveSnapshot = graph.serialize();
  const liveNodes = Array.isArray(liveSnapshot?.nodes) ? liveSnapshot.nodes : [];
  const candidateNodes = Array.isArray(candidateGraph.nodes) ? candidateGraph.nodes : [];
  const liveKeys = liveNodes.map((node) => canonicalNodeUid(node) || `id:${String(node?.id)}`);
  const candidateKeys = candidateNodes.map((node) => canonicalNodeUid(node) || `id:${String(node?.id)}`);
  if (
    liveKeys.length !== candidateKeys.length
    || liveKeys.some((key) => !candidateKeys.includes(key))
    || candidateKeys.some((key) => !liveKeys.includes(key))
  ) {
    throw new Error("Layout candidate node identities differ from the live graph.");
  }

  const candidateByKey = new Map(candidateNodes.map((node) => [
    canonicalNodeUid(node) || `id:${String(node?.id)}`,
    node,
  ]));
  const plan = [];
  for (const liveNode of graph._nodes) {
    const key = canonicalNodeUid(liveNode) || `id:${String(liveNode?.id)}`;
    const candidateNode = candidateByKey.get(key);
    if (!candidateNode) throw new Error(`Could not resolve live layout node ${key}.`);
    const before = {
      pos: Array.isArray(liveNode.pos) ? liveNode.pos.slice(0, 2) : null,
      size: Array.isArray(liveNode.size) ? liveNode.size.slice(0, 2) : null,
    };
    setLiveNodeGeometry(liveNode, candidateNode);
    plan.push({
      op: "set_node_geometry",
      uidOrId: key,
      before,
      after: { pos: candidateNode.pos.slice(0, 2), size: candidateNode.size.slice(0, 2) },
    });
  }

  const candidateGroups = Array.isArray(candidateGraph.groups) ? candidateGraph.groups : [];
  const liveGroups = graph._groups.slice();
  const liveByKey = new Map(liveGroups.map((group) => [serializedGroupKey(
    typeof group.serialize === "function" ? group.serialize() : group,
  ), group]));
  const nextGroups = [];
  for (let index = 0; index < candidateGroups.length; index += 1) {
    const serialized = candidateGroups[index];
    const key = serializedGroupKey(serialized);
    let group = liveByKey.get(key) || null;
    if (group) {
      liveByKey.delete(key);
    } else {
      const GroupCtor = liveGroups.find((entry) => entry?.constructor && entry.constructor !== Object)?.constructor
        || globalThis.LiteGraph?.LGraphGroup
        || globalThis.window?.LiteGraph?.LGraphGroup;
      if (typeof GroupCtor !== "function") {
        throw new Error(`Cannot create layout group ${key}; LGraphGroup constructor is unavailable.`);
      }
      group = new GroupCtor(serialized.title, serialized.id);
      graph.add(group, true);
    }
    configureLiveGroup(group, serialized);
    nextGroups.push(group);
  }
  for (const obsolete of liveByKey.values()) {
    graph.remove(obsolete);
  }
  graph._groups.splice(0, graph._groups.length, ...nextGroups);
  for (const group of nextGroups) {
    if (typeof group.recomputeInsideNodes === "function") group.recomputeInsideNodes();
  }
  plan.push({ op: "replace_layout_groups", count: nextGroups.length });

  if (typeof graph.change === "function") graph.change();
  if (options.repaint !== false) repaintGraph(app, graph);
  return { graph, capability, plan };
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

  const canvas = app?.canvas;
  const pollIntervalMs = Number.isFinite(options.pollIntervalMs) && options.pollIntervalMs > 0
    ? options.pollIntervalMs
    : 1000;
  const win = options.windowObj || (typeof window !== "undefined" ? window : null);
  const protoFn = win?.LiteGraph?.LGraphCanvas?.prototype?.onDrawForeground;
  const initialDelegate = typeof canvas?.onDrawForeground === "function" ? canvas.onDrawForeground : null;
  const loggedErrorKeys = new Set();

  const errorKey = (scope, error) => {
    const name = error?.name || "Error";
    const message = error?.message || String(error);
    return `${scope}:${name}:${message}`;
  };

  const warnOnce = (scope, label, error) => {
    const key = errorKey(scope, error);
    if (loggedErrorKeys.has(key)) {
      return;
    }
    loggedErrorKeys.add(key);
    console.warn(label, safeAdapterLogDetail(error));
  };

  const wrapperInChain = (fn) => {
    const seen = new Set();
    let cursor = typeof fn === "function" ? fn : null;
    while (cursor && !seen.has(cursor)) {
      if (cursor.__vibecomfyOverlayWrapper) {
        return cursor;
      }
      seen.add(cursor);
      cursor = typeof cursor.__vibecomfyOriginal === "function"
        ? cursor.__vibecomfyOriginal
        : null;
    }
    return null;
  };

  const existingInstall = app?.__vibecomfyPreviewForegroundInstall;
  if (existingInstall?.canvas === canvas && typeof existingInstall.setOverlayDraw === "function") {
    existingInstall.setOverlayDraw(overlayDraw);
    return existingInstall.report;
  }
  if (existingInstall?.canvas !== canvas && typeof existingInstall?.cleanup === "function") {
    existingInstall.cleanup();
  }

  const currentWrapper = wrapperInChain(initialDelegate);
  if (currentWrapper) {
    if (typeof currentWrapper.__vibecomfySetOverlayDraw === "function") {
      currentWrapper.__vibecomfySetOverlayDraw(overlayDraw);
    }
    app.__vibecomfyPreviewForegroundDraw = overlayDraw;
    const cleanup = () => {
      if (app?.__vibecomfyPreviewForegroundInstall === installState) {
        delete app.__vibecomfyPreviewForegroundInstall;
      }
    };
    const report = {
      capability,
      strategy: "existing-wrapper",
      polling: false,
      detail: "Reused an existing VibeComfy onDrawForeground wrapper already present in the callback chain.",
      cleanup,
    };
    const installState = {
      canvas,
      overlayDraw,
      setOverlayDraw(nextOverlayDraw) {
        this.overlayDraw = nextOverlayDraw;
        if (typeof currentWrapper.__vibecomfySetOverlayDraw === "function") {
          currentWrapper.__vibecomfySetOverlayDraw(nextOverlayDraw);
        }
        app.__vibecomfyPreviewForegroundDraw = nextOverlayDraw;
      },
      cleanup,
      report,
    };
    app.__vibecomfyPreviewForegroundInstall = installState;
    return report;
  }

  let delegate = initialDelegate;
  let reentrantDelegate = null;
  let activeOverlayDraw = overlayDraw;
  const wrapper = function vibecomfyPreviewForegroundWrapper(ctx, ...args) {
    if (inOverlayDraw) {
      if (typeof reentrantDelegate === "function" && reentrantDelegate !== wrapper) {
        try {
          reentrantDelegate.call(this, ctx, ...args);
        } catch (error) {
          warnOnce("reentrant-delegate", "[vibecomfy] original onDrawForeground threw:", error);
        }
      }
      return;
    }
    inOverlayDraw = true;
    try {
      if (typeof delegate === "function" && delegate !== wrapper) {
        delegate.call(this, ctx, ...args);
      } else if (typeof protoFn === "function") {
        protoFn.call(this, ctx, ...args);
      }
    } catch (error) {
      warnOnce("delegate", "[vibecomfy] original onDrawForeground threw:", error);
    }
    try {
      activeOverlayDraw.call(this, ctx);
    } catch (error) {
      warnOnce("overlay", "[vibecomfy] preview overlay draw threw:", error);
    } finally {
      inOverlayDraw = false;
    }
  };
  wrapper.__vibecomfyOverlayWrapper = true;
  wrapper.__vibecomfyOriginal = delegate;
  wrapper.__vibecomfySetOverlayDraw = (nextOverlayDraw) => {
    activeOverlayDraw = nextOverlayDraw;
    app.__vibecomfyPreviewForegroundDraw = nextOverlayDraw;
  };
  wrapper.__vibecomfySetOriginal = (nextDelegate) => {
    if (typeof nextDelegate !== "function" || nextDelegate === wrapper) {
      delegate = null;
      reentrantDelegate = null;
      wrapper.__vibecomfyOriginal = delegate;
      wrapper.__vibecomfyReentrantOriginal = reentrantDelegate;
      return;
    }
    const previousDelegate = delegate;
    const previousReentrantDelegate = reentrantDelegate;
    delegate = nextDelegate;
    reentrantDelegate = previousReentrantDelegate || previousDelegate || null;
    wrapper.__vibecomfyOriginal = delegate;
    wrapper.__vibecomfyReentrantOriginal = reentrantDelegate;
  };
  app.__vibecomfyPreviewForegroundDraw = overlayDraw;

  const installState = {
    canvas,
    overlayDraw,
    setOverlayDraw(nextOverlayDraw) {
      this.overlayDraw = nextOverlayDraw;
      wrapper.__vibecomfySetOverlayDraw(nextOverlayDraw);
    },
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
          wrapper.__vibecomfySetOriginal(nextValue);
        },
      });
      wrapper.__vibecomfySetOriginal(initialDelegate);
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
    if (wrapperInChain(current)) {
      return;
    }
    wrapper.__vibecomfySetOriginal(current);
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
 * @param {(args: any[]) => void} [options.normalize] — called before the
 *   original queuePrompt with the same arguments so the caller can normalize
 *   exec-node typed IO in the serialized graph before it hits the backend.
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

  const existingInstall = app?.__vibecomfyQueueGuardInstall;
  if (existingInstall?.installed && typeof existingInstall.wrapper === "function") {
    return existingInstall;
  }

  const original = app.queuePrompt;
  const shouldBlock = typeof options.shouldBlock === "function" ? options.shouldBlock : null;
  const onBlock = typeof options.onBlock === "function" ? options.onBlock : null;
  const normalize = typeof options.normalize === "function" ? options.normalize : null;

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
    if (normalize) {
      try {
        normalize(...args);
      } catch (_err) {
        // Best-effort: normalization failures must not block queueing.
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
    if (app?.__vibecomfyQueueGuardInstall === report) {
      delete app.__vibecomfyQueueGuardInstall;
    }
  };

  const report = {
    capability,
    strategy: "wrapper",
    installed: true,
    path: "app.queuePrompt",
    original,
    wrapper,
    cleanup,
  };
  app.__vibecomfyQueueGuardInstall = report;
  return report;
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
  const graphResult = createIntentGraphAdapter(app).capabilities();
  const graph = graphResult.ok ? graphResult.data : null;
  const graphApply = graph?.graph_apply || detectGraphApply(app);
  const previewForeground = detectPreviewForeground(app, windowObj);
  const queueGuard = detectQueueGuard(app);

  const version = String(frontendVersion || "unknown").trim() || "unknown";
  const major = SUPPORTED_FRONTEND.split(".").slice(0, 2).join(".");

  return {
    graph,
    graphDiagnostic: graphResult.ok ? null : graphResult.diagnostic,
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
