// graph_projection.js — canonical browser projections shared by session
// authority, workflow scopes, Apply verification, and rollback recovery.

import {
  canonicalSessionJsonString,
  compareCanonicalSessionJson,
} from "./canonical_hash.js";
import {
  LAYOUT_VERIFICATION_PROJECTION,
} from "./layout_verification_contract.js";

function naturalNodeIdKey(value) {
  const text = String(value ?? "");
  if (/^-?\d+$/.test(text)) {
    return { kind: 0, value: Number.parseInt(text, 10) };
  }
  return { kind: 1, value: text };
}

function compareNaturalNodeIds(left, right) {
  const leftKey = naturalNodeIdKey(left);
  const rightKey = naturalNodeIdKey(right);
  if (leftKey.kind !== rightKey.kind) return leftKey.kind - rightKey.kind;
  if (leftKey.value < rightKey.value) return -1;
  if (leftKey.value > rightKey.value) return 1;
  return 0;
}

function isPreviewLikeKey(key) {
  return /(?:^|_)(?:video)?preview(?:_|$)/i.test(String(key || ""));
}

function normalizeStructuralWidgetValue(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => normalizeStructuralWidgetValue(entry));
  }
  if (value && typeof value === "object") {
    const fields = {};
    for (const key of Object.keys(value).filter((item) => !isPreviewLikeKey(item)).sort()) {
      fields[key] = normalizeStructuralWidgetValue(value[key]);
    }
    return fields;
  }
  return value;
}

function normalizeNodeStructuralWidgetValues(node) {
  const values = node?.widgets_values ?? [];
  if (node?.type !== "vibecomfy.exec") {
    return normalizeStructuralWidgetValue(values);
  }
  if (Array.isArray(values)) {
    return values
      .filter((_entry, index) => index !== 1)
      .map((entry) => normalizeStructuralWidgetValue(entry));
  }
  if (values && typeof values === "object") {
    const fields = {};
    for (const key of Object.keys(values).filter((item) => item !== "io" && !isPreviewLikeKey(item)).sort()) {
      fields[key] = normalizeStructuralWidgetValue(values[key]);
    }
    return fields;
  }
  return normalizeStructuralWidgetValue(values);
}

function socketNames(sockets) {
  return Array.isArray(sockets)
    ? sockets.map((socket) => (socket && typeof socket === "object" ? socket.name ?? null : null))
    : [];
}

function slotName(names, slot) {
  if (Number.isInteger(slot) && slot >= 0 && slot < names.length) {
    return names[slot] ?? null;
  }
  return slot ?? null;
}

export function buildStructuralGraphProjection(graph) {
  if (!graph || typeof graph !== "object") {
    return { nodes: [], links: [] };
  }
  const rawNodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const inputNames = new Map();
  const outputNames = new Map();
  for (const node of rawNodes) {
    if (!node || typeof node !== "object") continue;
    inputNames.set(node.id ?? null, socketNames(node.inputs));
    outputNames.set(node.id ?? null, socketNames(node.outputs));
  }
  const nodes = rawNodes.map((rawNode) => {
    const node = rawNode && typeof rawNode === "object" ? rawNode : {};
    return {
      id: node.id ?? null,
      type: node.type ?? null,
      mode: node.mode == null ? 0 : node.mode,
      inputs: (Array.isArray(node.inputs) ? node.inputs : [])
        .filter((input) => input && input.link != null && input.name != null)
        .map((input) => String(input.name))
        .sort(),
      outputs: (Array.isArray(node.outputs) ? node.outputs : [])
        .filter((output) => output && output.name != null
          && (Array.isArray(output.links) ? output.links.length > 0 : Boolean(output.links)))
        .map((output) => String(output.name))
        .sort(),
      widgets_values: normalizeNodeStructuralWidgetValues(node),
    };
  });
  nodes.sort((left, right) => compareNaturalNodeIds(left.id, right.id)
    || (String(left.type ?? "") < String(right.type ?? "") ? -1
      : String(left.type ?? "") > String(right.type ?? "") ? 1 : 0));

  const links = (Array.isArray(graph.links) ? graph.links : [])
    .map((link) => {
      let originId;
      let originSlot;
      let targetId;
      let targetSlot;
      let linkType;
      if (Array.isArray(link) && link.length >= 6) {
        [, originId, originSlot, targetId, targetSlot, linkType] = link;
      } else if (link && typeof link === "object") {
        originId = link.origin_id;
        originSlot = link.origin_slot;
        targetId = link.target_id;
        targetSlot = link.target_slot;
        linkType = link.type;
      } else {
        return null;
      }
      return {
        from: originId ?? null,
        out: slotName(outputNames.get(originId ?? null) ?? [], originSlot),
        to: targetId ?? null,
        in: slotName(inputNames.get(targetId ?? null) ?? [], targetSlot),
        type: linkType ?? null,
      };
    })
    .filter((link) => link != null);
  links.sort(compareCanonicalSessionJson);
  return { nodes, links };
}

function layoutVector(value, length) {
  return Array.isArray(value) && value.length >= length ? value.slice(0, length) : null;
}

export function findUnsupportedNestedLayoutScopes(graph) {
  const unsupported = [];
  if (!graph || typeof graph !== "object") return unsupported;
  if (
    graph.definitions
    && typeof graph.definitions === "object"
    && !Array.isArray(graph.definitions)
    && Object.keys(graph.definitions).length > 0
  ) {
    unsupported.push({ scope_path: "definitions", reason: "nested_definitions" });
  }
  for (const group of Array.isArray(graph.groups) ? graph.groups : []) {
    if (group && typeof group === "object" && String(group.scope_path ?? "") !== "") {
      unsupported.push({
        scope_path: String(group.scope_path),
        reason: "nested_group",
      });
    }
  }
  return unsupported;
}

export function assertRootScopeLayoutGraph(graph) {
  const unsupported = findUnsupportedNestedLayoutScopes(graph);
  if (unsupported.length === 0) return;
  const error = new Error("Nested-scope layout application is not supported by the browser adapter.");
  error.code = "UNSUPPORTED_NESTED_LAYOUT_SCOPE";
  error.unsupported_scopes = unsupported;
  throw error;
}

export function buildLayoutGraphProjection(graph) {
  if (!graph || typeof graph !== "object") {
    return { contract_version: LAYOUT_VERIFICATION_PROJECTION, nodes: [], groups: [] };
  }
  assertRootScopeLayoutGraph(graph);
  const nodes = (Array.isArray(graph.nodes) ? graph.nodes : [])
    .filter((node) => node && typeof node === "object")
    .map((node) => ({
      id: node.id ?? null,
      pos: layoutVector(node.pos, 2),
      size: layoutVector(node.size, 2),
    }));
  nodes.sort((left, right) => compareNaturalNodeIds(left.id, right.id));
  const groups = (Array.isArray(graph.groups) ? graph.groups : [])
    .filter((group) => group && typeof group === "object")
    .map((group) => ({
      id: group.id ?? null,
      scope_path: String(group.scope_path ?? ""),
      title: group.title ?? null,
      bounding: layoutVector(group.bounding, 4),
      color: group.color ?? null,
    }));
  groups.sort((left, right) => compareCanonicalSessionJson(left.id, right.id));
  return { contract_version: LAYOUT_VERIFICATION_PROJECTION, nodes, groups };
}

export function structuralGraphProjectionJson(graph) {
  return canonicalSessionJsonString(buildStructuralGraphProjection(graph));
}

export function layoutGraphProjectionJson(graph) {
  return canonicalSessionJsonString(buildLayoutGraphProjection(graph));
}
