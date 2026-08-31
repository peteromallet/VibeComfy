// Sole browser owner of graph projection semantics.
//
// `graph_projection.js`, `field_registry_v1.js`, and
// `identity_contract_v1.js` are compatibility facades. Field selection,
// native normalization, graph identity, ordering, and projection hashing live
// here so browser authority cannot acquire a second interpretation.
import {
  canonicalJsonString,
  canonicalSessionJsonString,
  compareCanonicalSessionJson,
  sha256Hex,
  canonicalizeContractNumeric,
} from "./canonical_hash.js";
import { LAYOUT_VERIFICATION_PROJECTION } from "./layout_verification_contract.js";
import { assertRootGraphV1 } from "./root_scope_v1.js";

export const PROJECTION_REGISTRY_V1 = "projection_registry_v1";
export const FIELD_REGISTRY_V1 = "field_registry_v1";
export const IDENTITY_CONTRACT_V1 = "identity_contract_v1";

export const FIELD_CATEGORY = Object.freeze({
  EXECUTION_SEMANTIC: "execution_semantic",
  LAYOUT_SEMANTIC: "layout_semantic",
  NATIVE_DEFAULTED: "native_defaulted",
  DERIVED_NATIVE: "derived_native",
  OPAQUE_EXTENSION: "opaque_extension",
  UNSUPPORTED: "unsupported",
});

const FIELD_RULES_V1 = Object.freeze({
  "node.vibecomfy_uid": FIELD_CATEGORY.DERIVED_NATIVE,
  "node.id": FIELD_CATEGORY.DERIVED_NATIVE,
  "node.type": FIELD_CATEGORY.EXECUTION_SEMANTIC,
  "node.mode": FIELD_CATEGORY.NATIVE_DEFAULTED,
  "node.fields": FIELD_CATEGORY.EXECUTION_SEMANTIC,
  "node.widgets_values": FIELD_CATEGORY.EXECUTION_SEMANTIC,
  "node.inputs": FIELD_CATEGORY.DERIVED_NATIVE,
  "node.outputs": FIELD_CATEGORY.DERIVED_NATIVE,
  "node.properties": FIELD_CATEGORY.DERIVED_NATIVE,
  "node.flags": FIELD_CATEGORY.DERIVED_NATIVE,
  "node.order": FIELD_CATEGORY.DERIVED_NATIVE,
  // ComfyUI serializes the expanded/collapsed state of advanced widgets on
  // native nodes. It is host UI metadata, not workflow execution state.
  "node.showAdvanced": FIELD_CATEGORY.DERIVED_NATIVE,
  "node.color": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "node.bgcolor": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "node.boxcolor": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "node.shape": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "node.pos": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "node.size": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "node.title": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "node.extensions": FIELD_CATEGORY.OPAQUE_EXTENSION,
  "group.vibecomfy_group_id": FIELD_CATEGORY.DERIVED_NATIVE,
  "group.id": FIELD_CATEGORY.DERIVED_NATIVE,
  "group.scope_path": FIELD_CATEGORY.DERIVED_NATIVE,
  "group.flags": FIELD_CATEGORY.DERIVED_NATIVE,
  "group.font_size": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "group.title": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "group.bounding": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "group.color": FIELD_CATEGORY.LAYOUT_SEMANTIC,
  "group.nodes": FIELD_CATEGORY.LAYOUT_SEMANTIC,
});

export function classifyFieldV1({ entity, path, nodeType = null }) {
  if (entity === "node" && nodeType === "vibecomfy.exec" && path === "widgets_values.io") {
    return FIELD_CATEGORY.DERIVED_NATIVE;
  }
  // Core LoadImage has one execution-semantic input (`image`). ComfyUI's
  // image_upload metadata expands into additional serialized frontend widget
  // carriers (currently the literal `"image"`). Those values are native UI
  // materialization, not workflow semantics, and must not become transaction
  // authority merely because the browser factory injected them.
  if (entity === "node" && nodeType === "LoadImage" && /^widgets_values\.[1-9]\d*$/.test(path)) {
    return FIELD_CATEGORY.DERIVED_NATIVE;
  }
  return FIELD_RULES_V1[`${entity}.${path}`] || FIELD_CATEGORY.UNSUPPORTED;
}

export function assertSupportedFieldsV1(entity, value, nodeType = null) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`${entity} must be an object.`);
  }
  for (const key of Object.keys(value)) {
    if (classifyFieldV1({ entity, path: key, nodeType }) === FIELD_CATEGORY.UNSUPPORTED) {
      const error = new Error(`Unsupported ${entity} field ${key}.`);
      error.code = "unsupported_field";
      throw error;
    }
  }
}

export function registryRulesV1() {
  return { ...FIELD_RULES_V1 };
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function requiredIdentity(value, name) {
  if (typeof value !== "string" || !value) {
    const error = new Error(`Missing stable ${name}.`);
    error.code = "missing_identity";
    throw error;
  }
  return value;
}

export function workflowIdentityV1(value) {
  if (typeof value !== "string" || !UUID.test(value)) {
    const error = new Error("workflow_id must be a stable Comfy workflow UUID.");
    error.code = "invalid_workflow_identity";
    throw error;
  }
  return value;
}

export function nodeIdentityV1(node) {
  return requiredIdentity(
    node?.vibecomfy_uid ?? node?.properties?.vibecomfy_uid,
    "node vibecomfy_uid",
  );
}

export function groupIdentityV1(group) {
  return requiredIdentity(
    group?.vibecomfy_group_id ?? group?.id,
    "group stable id",
  );
}

export function issuedIdentityV1(value, kind) {
  return requiredIdentity(value, kind);
}

export function linkIdentityV1(link) {
  return {
    from: {
      node_uid: requiredIdentity(link?.from?.node_uid, "link source node"),
      port: requiredIdentity(link?.from?.port, "link source port"),
    },
    to: {
      node_uid: requiredIdentity(link?.to?.node_uid, "link target node"),
      port: requiredIdentity(link?.to?.port, "link target port"),
    },
  };
}

export function stableNodeIdentityOrNullV1(node) {
  try {
    return nodeIdentityV1(node);
  } catch (_error) {
    return null;
  }
}

export function stableGroupIdentityOrNullV1(group) {
  try {
    return groupIdentityV1(group);
  } catch (_error) {
    return null;
  }
}

/**
 * Build stable cross-graph node indexes.
 *
 * Native node IDs are used only inside this owner to locate the candidate's
 * explicit stable UID for an unstamped live serialization. They never escape
 * as identity and are never accepted when the candidate itself lacks a UID.
 */
export function crossGraphNodeIdentityIndexV1(liveGraph, candidateGraph) {
  const candidateNodes = Array.isArray(candidateGraph?.nodes) ? candidateGraph.nodes : [];
  const liveNodes = Array.isArray(liveGraph?.nodes) ? liveGraph.nodes : [];
  const candidateUidByNativeId = new Map();
  const candidateByUid = new Map();
  for (const node of candidateNodes) {
    const uid = stableNodeIdentityOrNullV1(node);
    if (!uid) continue;
    candidateByUid.set(uid, node);
    if (node?.id != null) candidateUidByNativeId.set(String(node.id), uid);
  }
  const liveByUid = new Map();
  for (const node of liveNodes) {
    const explicitUid = stableNodeIdentityOrNullV1(node);
    const locatedUid = explicitUid || (
      node?.id != null ? candidateUidByNativeId.get(String(node.id)) : null
    );
    if (locatedUid) liveByUid.set(locatedUid, node);
  }
  return {
    candidateNodes,
    liveNodes,
    candidateUidByNativeId,
    candidateByUid,
    liveByUid,
  };
}

function previewLinkPartsV1(link) {
  if (Array.isArray(link) && link.length >= 6) {
    return {
      originId: link[1], originSlot: link[2], targetId: link[3], targetSlot: link[4],
    };
  }
  if (Array.isArray(link) && link.length >= 4) {
    return {
      originId: link[0], originSlot: link[1], targetId: link[2], targetSlot: link[3],
    };
  }
  if (link && typeof link === "object") {
    return {
      originId: link.origin_id,
      originSlot: link.origin_slot,
      targetId: link.target_id,
      targetSlot: link.target_slot,
    };
  }
  return null;
}

/**
 * Normalize serialized links for preview comparison using only stable node
 * UIDs and named ports. Unsupported/missing port names are omitted rather than
 * promoted into numeric pseudo-identities.
 */
export function stablePreviewLinkMapV1(graph, uidByNativeId = new Map()) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const nodeByNativeId = new Map(
    nodes
      .filter((node) => node?.id != null)
      .map((node) => [String(node.id), node]),
  );
  const graphUidByNativeId = new Map();
  for (const node of nodes) {
    if (node?.id == null) continue;
    const uid = stableNodeIdentityOrNullV1(node) || uidByNativeId.get(String(node.id));
    if (uid) graphUidByNativeId.set(String(node.id), uid);
  }
  const rawLinks = Array.isArray(graph?.links)
    ? graph.links
    : graph?.links && typeof graph.links === "object" ? Object.values(graph.links) : [];
  const result = new Map();
  for (const rawLink of rawLinks) {
    const link = previewLinkPartsV1(rawLink);
    if (!link || !Number.isInteger(Number(link.originSlot)) || !Number.isInteger(Number(link.targetSlot))) continue;
    const fromUid = graphUidByNativeId.get(String(link.originId));
    const toUid = graphUidByNativeId.get(String(link.targetId));
    const fromNode = nodeByNativeId.get(String(link.originId));
    const toNode = nodeByNativeId.get(String(link.targetId));
    const fromPort = fromNode?.outputs?.[Number(link.originSlot)]?.name;
    const toPort = toNode?.inputs?.[Number(link.targetSlot)]?.name;
    if (!fromUid || !toUid || typeof fromPort !== "string" || !fromPort || typeof toPort !== "string" || !toPort) continue;
    const physical = `${fromUid}::#${Number(link.originSlot)}->${toUid}::#${Number(link.targetSlot)}`;
    result.set(physical, `${fromUid}::${fromPort}->${toUid}::${toPort}`);
  }
  return result;
}

function nativePortName(node, direction, slot, preferredName) {
  const sockets = direction === "from" ? node?.outputs : node?.inputs;
  if (!Array.isArray(sockets)) {
    return requiredIdentity(null, `link ${direction} port`);
  }
  if (typeof preferredName === "string" && preferredName) {
    const named = sockets.find((socket) => socket && socket.name === preferredName);
    if (named) return preferredName;
  }
  if (typeof slot === "string" && slot) {
    const named = sockets.find((socket) => socket && socket.name === slot);
    if (named) return slot;
  }
  if (Number.isInteger(slot) && slot >= 0 && slot < sockets.length) {
    const name = sockets[slot]?.name;
    if (typeof name === "string") return name;
  }
  return requiredIdentity(null, `link ${direction} port`);
}

function graphLinkIdentitiesV1(graph, nodes) {
  const byNativeId = new Map();
  for (const node of nodes) {
    if (node?.id != null) byNativeId.set(nativeNodeIdentityKey(node.id), node);
  }
  return (Array.isArray(graph.links) ? graph.links : []).map((link) => {
    if (link && !Array.isArray(link) && link.from && link.to) return linkIdentityV1(link);
    let originId;
    let originSlot;
    let targetId;
    let targetSlot;
    if (Array.isArray(link) && link.length === 6) {
      [, originId, originSlot, targetId, targetSlot] = link;
    } else if (link && typeof link === "object") {
      originId = link.origin_id;
      originSlot = link.origin_slot;
      targetId = link.target_id;
      targetSlot = link.target_slot;
    } else {
      const error = new Error("link must be a stable endpoint object or native six-tuple.");
      error.code = "malformed_link";
      throw error;
    }
    let origin;
    let target;
    try {
      origin = byNativeId.get(nativeNodeIdentityKey(originId));
      target = byNativeId.get(nativeNodeIdentityKey(targetId));
    } catch (_error) {
      origin = target = null;
    }
    return {
      from: {
        node_uid: nodeIdentityV1(origin),
        port: nativePortName(origin, "from", originSlot),
      },
      to: {
        node_uid: nodeIdentityV1(target),
        port: nativePortName(target, "to", targetSlot),
      },
    };
  });
}

export const PROJECTIONS_V1 = Object.freeze({
  structural_v1: { name: "structural_v1", allowed: true },
  layout_v1: { name: "layout_v1", allowed: true },
  workflow_v1: {
    name: "workflow_v1",
    allowed: false,
    reason: "forbidden_forward_agent_edit",
  },
});

export function projectionSpecV1(name) {
  const spec = PROJECTIONS_V1[name];
  if (!spec) {
    const error = new Error(`Unknown projection ${name}.`);
    error.code = "unknown_projection_version";
    throw error;
  }
  return spec;
}

export function assertForwardProjectionV1(name) {
  const spec = projectionSpecV1(name);
  if (!spec.allowed) {
    const error = new Error(`${name} is forbidden for forward Agent Edit.`);
    error.code = "forbidden_projection";
    throw error;
  }
  return spec;
}

function normalizeProjectionWidgetValue(value) {
  if (Array.isArray(value)) return value.map(normalizeProjectionWidgetValue);
  if (value && typeof value === "object") {
    const normalized = {};
    for (const key of Object.keys(value).filter((item) => !isPreviewLikeKey(item)).sort()) {
      normalized[key] = normalizeProjectionWidgetValue(value[key]);
    }
    return normalized;
  }
  return value;
}

export function normalizeDerivedWidgetFieldsV1(node, normalize = normalizeProjectionWidgetValue) {
  const values = node?.widgets_values ?? [];
  if (node?.type === "LoadImage" && Array.isArray(values)) {
    return values
      .filter((_entry, index) => classifyFieldV1({
        entity: "node",
        path: `widgets_values.${index}`,
        nodeType: node.type,
      }) !== FIELD_CATEGORY.DERIVED_NATIVE)
      .map(normalize);
  }
  if (node?.type !== "vibecomfy.exec") return normalize(values);
  if (Array.isArray(values)) {
    return values.filter((_entry, index) => index !== 1).map(normalize);
  }
  if (values && typeof values === "object") {
    return Object.fromEntries(
      Object.entries(values)
        .filter(([key]) => classifyFieldV1({
          entity: "node",
          path: `widgets_values.${key}`,
          nodeType: node.type,
        }) !== FIELD_CATEGORY.DERIVED_NATIVE)
        .map(([key, value]) => [key, normalize(value)]),
    );
  }
  return normalize(values);
}

function cleanWidgets(node) {
  if (node?.widgets_values == null) return {};
  const normalized = normalizeDerivedWidgetFieldsV1(node, normalizeProjectionWidgetValue);
  // LiteGraph omits widgets_values entirely for some zero-widget nodes while
  // generated candidates explicitly carry []. Both serialize the same node.
  if (Array.isArray(normalized) && normalized.length === 0) return {};
  return normalized;
}

function structuralNodeV1(node) {
  assertSupportedFieldsV1("node", node, node?.type);
  const result = {
    uid: nodeIdentityV1(node),
    type: typeof node.type === "string" ? node.type : null,
    mode: node.mode == null ? 0 : node.mode,
    fields: node.fields == null ? {} : node.fields,
    widgets_values: cleanWidgets(node),
  };
  if (node.extensions != null) result.extensions = node.extensions;
  return result;
}

function layoutNodeV1(node) {
  assertSupportedFieldsV1("node", node, node?.type);
  return {
    uid: nodeIdentityV1(node),
    pos: Array.isArray(node.pos) ? node.pos.slice(0, 2) : null,
    size: Array.isArray(node.size) ? node.size.slice(0, 2) : null,
  };
}

function layoutGroupV1(group) {
  assertSupportedFieldsV1("group", group);
  return {
    id: groupIdentityV1(group),
    bounding: Array.isArray(group.bounding) ? group.bounding.slice(0, 4) : null,
    color: group.color ?? null,
    title: group.title ?? null,
  };
}

function sortByCanonicalProjectionJson(items) {
  return items.sort((leftValue, rightValue) => {
    const left = canonicalJsonString(leftValue);
    const right = canonicalJsonString(rightValue);
    return left < right ? -1 : left > right ? 1 : 0;
  });
}

function projectionMalformedGraph(message) {
  const error = new Error(message);
  error.code = "malformed_graph";
  return error;
}

function nativeNodeIdentityKey(value) {
  if (typeof value === "string") return value;
  if (typeof value === "boolean") {
    const error = new Error("Native node id must not be boolean.");
    error.code = "non_canonical_number";
    throw error;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value) || !Number.isInteger(value)) {
      const error = new Error("Native node id must be a finite integer.");
      error.code = "non_canonical_number";
      throw error;
    }
    if (!Number.isSafeInteger(value)) {
      const error = new Error("Native node id exceeds the JS safe integer range.");
      error.code = "non_canonical_number";
      throw error;
    }
    return String(value);
  }
  throw projectionMalformedGraph("Native node id must be a string or number.");
}

function validateProjectionContainers(graph, projection) {
  const nodes = Object.hasOwn(graph, "nodes") ? graph.nodes : [];
  if (!Array.isArray(nodes)) throw projectionMalformedGraph("nodes must be a list.");
  if (projection === "structural_v1") {
    const links = Object.hasOwn(graph, "links") ? graph.links : [];
    if (!Array.isArray(links)) throw projectionMalformedGraph("links must be a list.");
  }
  if (projection === "layout_v1") {
    const groups = Object.hasOwn(graph, "groups") ? graph.groups : [];
    if (!Array.isArray(groups)) throw projectionMalformedGraph("groups must be a list.");
  }
  return nodes;
}

function validateProjectionNodeIdentities(nodes) {
  const stableUids = new Set();
  const nativeIds = new Set();
  for (const node of nodes) {
    if (!node || typeof node !== "object" || Array.isArray(node)) {
      throw projectionMalformedGraph("node must be an object.");
    }
    const uid = nodeIdentityV1(node);
    if (stableUids.has(uid)) {
      const error = new Error("Duplicate stable node identity.");
      error.code = "duplicate_identity";
      throw error;
    }
    stableUids.add(uid);
    if (node.id != null) {
      const nativeId = nativeNodeIdentityKey(node.id);
      if (nativeIds.has(nativeId)) {
        const error = new Error("Duplicate native node identity.");
        error.code = "duplicate_identity";
        throw error;
      }
      nativeIds.add(nativeId);
    }
  }
}

export function projectGraphV1(graph, projection) {
  projectionSpecV1(projection);
  assertForwardProjectionV1(projection);
  assertRootGraphV1(graph);
  if (Array.isArray(graph)) throw projectionMalformedGraph("graph must be an object.");
  const nodes = validateProjectionContainers(graph, projection);
  validateProjectionNodeIdentities(nodes);
  if (projection === "structural_v1") {
    return {
      projection,
      nodes: sortByCanonicalProjectionJson(nodes.map(structuralNodeV1)),
      links: sortByCanonicalProjectionJson(
        graphLinkIdentitiesV1(graph, nodes),
      ),
    };
  }
  if (projection === "layout_v1") {
    return {
      projection,
      nodes: sortByCanonicalProjectionJson(nodes.map(layoutNodeV1)),
      groups: sortByCanonicalProjectionJson(
        (Array.isArray(graph.groups) ? graph.groups : []).map(layoutGroupV1),
      ),
    };
  }
  throw new Error("workflow_v1 is forbidden.");
}

export function projectionReferenceV1(graph, projection) {
  const canonical = projectGraphV1(graph, projection);
  return {
    kind: "projection_ref_v1",
    projection,
    digest: sha256Hex(canonical),
    canonical,
  };
}

export function assertProjectionReferenceV1(value, { expected = null } = {}) {
  if (
    !value
    || value.kind !== "projection_ref_v1"
    || typeof value.projection !== "string"
    || typeof value.digest !== "string"
    || !/^[0-9a-f]{64}$/.test(value.digest)
  ) {
    const error = new Error("Expected typed projection reference.");
    error.code = "invalid_projection_reference";
    throw error;
  }
  projectionSpecV1(value.projection);
  if (expected && value.projection !== expected) {
    const error = new Error("Projection family mismatch.");
    error.code = "projection_family_mismatch";
    throw error;
  }
  if (Object.hasOwn(value, "canonical")) {
    if (!value.canonical || value.canonical.projection !== value.projection) {
      const error = new Error("Projection evidence has the wrong canonical family.");
      error.code = "projection_canonical_mismatch";
      throw error;
    }
    if (sha256Hex(value.canonical) !== value.digest) {
      const error = new Error("Projection evidence digest does not bind its canonical payload.");
      error.code = "projection_digest_mismatch";
      throw error;
    }
  }
  return value;
}

function projectionReferenceMatches(actual, expected, { requireCanonical = false } = {}) {
  if (!actual || actual.kind !== expected.kind
    || actual.projection !== expected.projection
    || actual.digest !== expected.digest) {
    return false;
  }
  if (requireCanonical && !Object.hasOwn(actual, "canonical")) return false;
  if (Object.hasOwn(actual, "canonical")) {
    try {
      return canonicalJsonString(actual.canonical) === canonicalJsonString(expected.canonical);
    } catch (_error) {
      return false;
    }
  }
  return true;
}

/**
 * Verify the transaction projection claims against the terminal's candidate.
 * The precondition's canonical projection is the source witness; the
 * transaction's submit structural hash is bound to that witness (or the
 * layout transaction's structural precondition witness).  Layout hashes are
 * compatibility projections and are recomputed from the published graph.
 */
export function validateTerminalTransactionProjectionBinding(transaction, candidateGraph) {
  if (!transaction || typeof transaction !== "object" || Array.isArray(transaction)
    || !candidateGraph || typeof candidateGraph !== "object" || Array.isArray(candidateGraph)) {
    return { valid: false, reason: "invalid_terminal_projection_boundary" };
  }
  const candidateAuthority = transaction.candidate_authority;
  const hashes = transaction.hashes;
  const authority = transaction.authority;
  if (!candidateAuthority || typeof candidateAuthority !== "object" || Array.isArray(candidateAuthority)
    || !hashes || typeof hashes !== "object" || Array.isArray(hashes)
    || !authority || typeof authority !== "object" || Array.isArray(authority)) {
    return { valid: false, reason: "invalid_terminal_projection_boundary" };
  }
  const projection = candidateAuthority.operation_family === "layout" ? "layout_v1" : "structural_v1";
  let expectedPostcondition;
  try {
    expectedPostcondition = projectionReferenceV1(candidateGraph, projection);
  } catch (_error) {
    return { valid: false, reason: "candidate_transaction_postcondition_unavailable" };
  }
  if (!projectionReferenceMatches(candidateAuthority.postcondition, expectedPostcondition)) {
    return { valid: false, reason: "candidate_transaction_postcondition_mismatch" };
  }

  const precondition = candidateAuthority.precondition;
  try {
    assertProjectionReferenceV1(precondition, { expected: projection });
  } catch (_error) {
    return { valid: false, reason: "candidate_transaction_precondition_mismatch" };
  }
  if (!projectionReferenceMatches(precondition, precondition, { requireCanonical: true })) {
    return { valid: false, reason: "candidate_transaction_precondition_mismatch" };
  }

  let expectedSubmitStructuralHash = precondition.compatibility_digest;
  if (projection === "layout_v1") {
    const structuralWitness = candidateAuthority.structural_witness;
    let expectedStructuralPostcondition;
    try {
      assertProjectionReferenceV1(structuralWitness, { expected: "structural_v1" });
      expectedStructuralPostcondition = projectionReferenceV1(candidateGraph, "structural_v1");
    } catch (_error) {
      return { valid: false, reason: "candidate_transaction_structural_witness_mismatch" };
    }
    if (!projectionReferenceMatches(structuralWitness, structuralWitness, { requireCanonical: true })
      || !projectionReferenceMatches(structuralWitness, expectedStructuralPostcondition)
      || structuralWitness.precondition_digest !== structuralWitness.digest
      || structuralWitness.postcondition_digest !== structuralWitness.digest) {
      return { valid: false, reason: "candidate_transaction_structural_witness_mismatch" };
    }
    if (structuralWitness.compatibility_digest !== precondition.compatibility_digest) {
      return { valid: false, reason: "candidate_transaction_submit_structural_hash_mismatch" };
    }
  }
  if (typeof expectedSubmitStructuralHash !== "string"
    || !/^[0-9a-f]{64}$/.test(expectedSubmitStructuralHash)
    || hashes.submit_structural_graph_hash !== expectedSubmitStructuralHash) {
    return { valid: false, reason: "candidate_transaction_submit_structural_hash_mismatch" };
  }

  if (candidateAuthority.operation_family === "layout") {
    const layoutHash = hashes.candidate_layout_graph_hash;
    const layoutVerification = authority.layout_verification;
    if (layoutHash != null || layoutVerification != null) {
      let expectedLayoutHash;
      try {
        expectedLayoutHash = sha256Hex(buildLayoutGraphProjection(candidateGraph));
      } catch (_error) {
        expectedLayoutHash = null;
      }
      if (expectedLayoutHash == null
        || (layoutHash != null && layoutHash !== expectedLayoutHash)
        || (layoutVerification != null && (!layoutVerification || typeof layoutVerification !== "object"
          || Array.isArray(layoutVerification)
          || layoutVerification.contract_version !== "layout_verification_v1"
          || layoutVerification.projection !== "browser_layout_v1"
          || layoutVerification.candidate_layout_graph_hash !== expectedLayoutHash))) {
        return { valid: false, reason: "candidate_transaction_layout_hash_mismatch" };
      }
    }
  }
  return { valid: true, reason: "ok" };
}

// M0 layout-preview compatibility profile. The preview module re-exports
// these APIs, but identity, field selection, ordering, and hashing stay here.
export function computeMutationPlanHash(planProjection) {
  if (!planProjection || Array.isArray(planProjection) || typeof planProjection !== "object") {
    return "";
  }
  return sha256Hex(planProjection);
}

export function computeCanvasProjectionHash(canvasProjection) {
  if (!canvasProjection || Array.isArray(canvasProjection) || typeof canvasProjection !== "object") {
    return "";
  }
  return sha256Hex(canvasProjection);
}

export function extractCanvasProjection(candidateGraph) {
  const nodes = Array.isArray(candidateGraph?.nodes) ? candidateGraph.nodes : [];
  const groups = Array.isArray(candidateGraph?.groups) ? candidateGraph.groups : [];
  const extra = candidateGraph?.extra && typeof candidateGraph.extra === "object"
    ? candidateGraph.extra
    : {};
  const entries = {};
  for (const node of nodes) {
    let uid;
    try {
      uid = nodeIdentityV1(node);
    } catch (_error) {
      continue;
    }
    const entry = {};
    if (Array.isArray(node.pos) && node.pos.length >= 2) {
      entry.pos = [Number(node.pos[0]), Number(node.pos[1])];
    } else if (Array.isArray(node?.properties?.pos) && node.properties.pos.length >= 2) {
      entry.pos = [Number(node.properties.pos[0]), Number(node.properties.pos[1])];
    }
    if (node.size && (Array.isArray(node.size) ? node.size.length >= 2 : true)) {
      entry.size = Array.isArray(node.size)
        ? [Number(node.size[0]), Number(node.size[1])]
        : node.size;
    }
    if (node.flags && typeof node.flags === "object") entry.flags = { ...node.flags };
    if (typeof node.color === "string") entry.color = node.color;
    if (typeof node.bgcolor === "string") entry.bgcolor = node.bgcolor;
    if (node.mode != null) entry.mode = node.mode;
    if (node.order != null) entry.order = node.order;
    entries[uid] = entry;
  }
  const canvasGroups = groups.map((group) => {
    const value = {};
    if (typeof group.title === "string") value.title = group.title;
    const raw = group?.bounding || group?._bounding;
    if (raw) {
      const bounds = [
        Number(raw[0] ?? 0), Number(raw[1] ?? 0),
        Number(raw[2] ?? 0), Number(raw[3] ?? 0),
      ];
      if (bounds.every(Number.isFinite)) value.bounding = bounds;
    }
    if (typeof group.color === "string") value.color = group.color;
    if (group.font_size != null) value.font_size = group.font_size;
    if (group.locked != null) value.locked = Boolean(group.locked);
    return value;
  }).filter((group) => Object.keys(group).length > 0);
  const projection = { entries };
  if (canvasGroups.length > 0) projection.groups = canvasGroups;
  if (Object.keys(extra).length > 0) projection.extra = extra;
  return projection;
}

// -------------------------------------------------------------------------
// Compatibility projection profile
// -------------------------------------------------------------------------
// These exports preserve the M0 browser/session hash shape while all of its
// semantics remain owned here. They are not candidate_transaction_v2 typed
// authority; new authority uses projectGraphV1/projectionReferenceV1 above.

function naturalNodeIdKey(value) {
  const text = String(value ?? "");
  if (/^-?\d+$/.test(text)) return { kind: 0, value: Number.parseInt(text, 10) };
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
  if (Array.isArray(value)) return value.map(normalizeStructuralWidgetValue);
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
  return normalizeDerivedWidgetFieldsV1(node, normalizeStructuralWidgetValue);
}

function socketNames(sockets) {
  return Array.isArray(sockets)
    ? sockets.map((socket) => (socket && typeof socket === "object" ? socket.name ?? null : null))
    : [];
}

function slotName(names, slot) {
  if (Number.isInteger(slot) && slot >= 0 && slot < names.length) return names[slot] ?? null;
  return slot ?? null;
}

export function buildStructuralGraphProjection(graph) {
  if (!graph || typeof graph !== "object") return { nodes: [], links: [] };
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

export function findUnsupportedNestedLayoutScopes(graph) {
  const unsupported = [];
  if (!graph || typeof graph !== "object") return unsupported;
  if (
    graph.definitions
    && typeof graph.definitions === "object"
    && !Array.isArray(graph.definitions)
    && Object.keys(graph.definitions).length > 0
  ) unsupported.push({ scope_path: "definitions", reason: "nested_definitions" });
  for (const group of Array.isArray(graph.groups) ? graph.groups : []) {
    if (group && typeof group === "object" && String(group.scope_path ?? "") !== "") {
      unsupported.push({ scope_path: String(group.scope_path), reason: "nested_group" });
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

function layoutVector(value, length) {
  return Array.isArray(value) && value.length >= length ? value.slice(0, length) : null;
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
