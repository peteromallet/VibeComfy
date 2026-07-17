import {
  ROOT_SCOPE_V1,
  ROOT_SCOPE,
  assertRootScopeV1,
} from "./root_scope_v1.js";
import {
  assertForwardProjectionV1,
  projectGraphV1,
  projectionSpecV1,
  projectionReferenceV1,
  nodeIdentityV1,
  groupIdentityV1,
} from "./projection_registry_v1.js";

export const INTENT_GRAPH_ADAPTER_V1 = "intent_graph_adapter_v1";
export const HARNESS_DELTA_APPLY_FALLBACK_MARKER =
  "__vibecomfyAllowDeltaSerializeConfigureFallback";
export const NATIVE_NORMALIZATION_V1 = "native_normalization_v1";

const MAX_BOUND = 512;

function bound(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.slice(0, MAX_BOUND);
  try {
    const text = JSON.stringify(value);
    return typeof text === "string" ? text.slice(0, MAX_BOUND) : String(text).slice(0, MAX_BOUND);
  } catch (_err) {
    return String(value).slice(0, MAX_BOUND);
  }
}

export const DIAGNOSTIC_CODES = Object.freeze({
  UNSUPPORTED_CONTRACT: "unsupported_contract",
  UNSUPPORTED_SCOPE: "unsupported_scope",
  MISSING_LIVE_GRAPH: "missing_live_graph",
  AMBIGUOUS_LIVE_GRAPH: "ambiguous_live_graph",
  SERIALIZATION_FAILED: "serialization_failed",
  REVISION_UNAVAILABLE: "revision_unavailable",
  REVISION_FAILED: "revision_failed",
  REPAINT_UNAVAILABLE: "repaint_unavailable",
  REPAINT_FAILED: "repaint_failed",
  PROJECTION_FAILED: "projection_failed",
  // Slice 3 identity / normalization diagnostics. Identity validity and field
  // meaning stay owned by projection_registry_v1.js; the adapter only emits
  // these typed refusals at its boundary.
  MISSING_IDENTITY: "missing_identity",
  AMBIGUOUS_IDENTITY: "ambiguous_identity",
  UNSUPPORTED_NORMALIZATION: "unsupported_normalization",
});

const hasOwn = (value, key) => Object.prototype.hasOwnProperty.call(value, key);

function isPlain(value) {
  if (value === null) return true;
  const t = typeof value;
  if (t !== "object") return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function deepClonePlain(value) {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    const out = [];
    for (let i = 0; i < value.length; i++) {
      out[i] = deepClonePlain(value[i]);
    }
    return out;
  }
  // Non-plain object → treat as serialization failure boundary.
  if (!isPlain(value)) {
    const err = new Error("non-plain serialization output");
    err.code = "serialization_failed";
    throw err;
  }
  const out = {};
  for (const key of Object.keys(value)) {
    out[key] = deepClonePlain(value[key]);
  }
  return out;
}

function deepFreeze(value) {
  if (value === null || typeof value !== "object") return value;
  Object.freeze(value);
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) deepFreeze(value[i]);
    return value;
  }
  for (const key of Object.keys(value)) deepFreeze(value[key]);
  return value;
}

function envelope(ok, payload, meta) {
  const out = {
    contract_version: INTENT_GRAPH_ADAPTER_V1,
    ok,
  };
  if (ok) {
    out.data = payload;
  } else {
    out.diagnostic = {
      code: payload.code,
      message: bound(payload.message),
      detail: bound(payload.detail ?? ""),
    };
  }
  if (meta && meta.scope !== undefined) out.scope = meta.scope;
  if (meta && meta.scope_contract !== undefined) out.scope_contract = meta.scope_contract;
  if (meta && meta.operation !== undefined) out.operation = meta.operation;
  return deepFreeze(out);
}

function resolveScope(options) {
  if (options === null || (options !== undefined && (
    typeof options !== "object" || Array.isArray(options)
  ))) {
    const err = new Error("adapter options must be an object when provided");
    err.code = "unsupported_contract";
    throw err;
  }
  const opts = options ?? {};
  const adapter_contract = hasOwn(opts, "adapter_contract")
    ? opts.adapter_contract
    : INTENT_GRAPH_ADAPTER_V1;
  if (adapter_contract !== INTENT_GRAPH_ADAPTER_V1) {
    const err = new Error("unsupported adapter contract");
    err.code = "unsupported_contract";
    throw err;
  }
  const scope_contract = hasOwn(opts, "scope_contract")
    ? opts.scope_contract
    : ROOT_SCOPE_V1;
  if (scope_contract !== ROOT_SCOPE_V1) {
    const err = new Error("unsupported scope contract");
    err.code = "unsupported_scope";
    throw err;
  }
  const scope = hasOwn(opts, "scope") ? opts.scope : ROOT_SCOPE;
  return { scope: assertRootScopeV1(scope), scope_contract };
}

function nodeFactoryAvailable(app) {
  const liteGraph = app?.LiteGraph
    || app?.canvas?.LiteGraph
    || globalThis?.LiteGraph
    || globalThis?.window?.LiteGraph
    || null;
  return typeof liteGraph?.createNode === "function";
}

function graphApplyCapability(graph) {
  const available = typeof graph.clear === "function" && typeof graph.configure === "function";
  return {
    available,
    detail: available
      ? "Live graph supports in-place clear + configure."
      : "Live graph is missing clear/configure.",
    path: "intent_graph_adapter.graph_apply",
    strategy: available ? "legacy-whole-graph-replace" : null,
  };
}

function deltaApplyCapability(app, graph) {
  const liveAvailable = typeof graph.serialize === "function"
    && Array.isArray(graph._nodes)
    && typeof graph.add === "function"
    && typeof graph.remove === "function"
    && nodeFactoryAvailable(app);
  if (liveAvailable) {
    return {
      available: true,
      detail: "Live graph supports serialized preflight plus LiteGraph add/remove mutation.",
      path: "intent_graph_adapter.delta_apply",
      strategy: "live-litegraph-mutate",
      fallback: false,
    };
  }
  const harnessFallback = app?.[HARNESS_DELTA_APPLY_FALLBACK_MARKER] === true
    && typeof graph.serialize === "function"
    && typeof graph.clear === "function"
    && typeof graph.configure === "function";
  return {
    available: harnessFallback,
    detail: harnessFallback
      ? "Harness-only serialize/mutate/configure fallback enabled by explicit marker."
      : "Missing LiteGraph mutation hooks for delta apply.",
    path: "intent_graph_adapter.delta_apply",
    strategy: harnessFallback ? "harness-serialize-configure" : null,
    fallback: harnessFallback,
  };
}

function layoutApplyCapability(graph) {
  const available = typeof graph.serialize === "function"
    && Array.isArray(graph._nodes)
    && Array.isArray(graph._groups)
    && typeof graph.add === "function"
    && typeof graph.remove === "function";
  return {
    available,
    detail: available
      ? "Live graph supports geometry/group-only in-place mutation."
      : "Layout apply requires serialized live nodes, native groups, and graph add/remove hooks.",
    path: "intent_graph_adapter.layout_apply",
    strategy: available ? "live-layout-mutate" : null,
    fallback: false,
  };
}

function resolveCandidates(app) {
  const candidates = [];
  const seen = new WeakSet();
  function consider(value) {
    if (value === null || typeof value !== "object") return;
    if (seen.has(value)) return;
    seen.add(value);
    candidates.push(value);
  }
  consider(app?.canvas?.graph);
  consider(app?.graph);
  return candidates;
}

function withGraph(app, operation, options, fn) {
  let scopeCtx;
  try {
    scopeCtx = { ...resolveScope(options), operation };
  } catch (error) {
    return envelope(false, {
      code: error?.code === "unsupported_contract"
        ? DIAGNOSTIC_CODES.UNSUPPORTED_CONTRACT
        : DIAGNOSTIC_CODES.UNSUPPORTED_SCOPE,
      message: error?.code === "unsupported_contract"
        ? "unsupported intent graph adapter contract"
        : "unsupported Agent Edit scope",
      detail: error?.message || error?.code || "unsupported_scope",
    }, { operation });
  }
  const candidates = resolveCandidates(app);
  if (candidates.length === 0) {
    return envelope(false, {
      code: DIAGNOSTIC_CODES.MISSING_LIVE_GRAPH,
      message: "no live graph available",
      detail: "app.canvas.graph and app.graph are both absent",
    }, scopeCtx);
  }
  if (candidates.length > 1) {
    return envelope(false, {
      code: DIAGNOSTIC_CODES.AMBIGUOUS_LIVE_GRAPH,
      message: "multiple distinct live graphs available",
      detail: "resolved " + candidates.length + " distinct graph references",
    }, scopeCtx);
  }
  return fn(candidates[0], scopeCtx);
}

function captureSerialized(graph) {
  let serialized;
  try {
    serialized = graph.serialize();
  } catch (err) {
    const wrapped = new Error("graph.serialize threw");
    wrapped.code = DIAGNOSTIC_CODES.SERIALIZATION_FAILED;
    wrapped.cause = err;
    throw wrapped;
  }
  if (serialized === null || typeof serialized !== "object") {
    const err = new Error("non-object serialization output");
    err.code = DIAGNOSTIC_CODES.SERIALIZATION_FAILED;
    throw err;
  }
  // JSON round-trip guards against cycles; plain-only deep clone also rejects
  // non-plain shapes that would leak live references.
  let jsonText;
  try {
    jsonText = JSON.stringify(serialized);
  } catch (err) {
    const wrapped = new Error("serialization output is not JSON-safe");
    wrapped.code = DIAGNOSTIC_CODES.SERIALIZATION_FAILED;
    wrapped.cause = err;
    throw wrapped;
  }
  if (typeof jsonText !== "string") {
    const err = new Error("cyclic or non-string serialization output");
    err.code = DIAGNOSTIC_CODES.SERIALIZATION_FAILED;
    throw err;
  }
  let parsed;
  try {
    parsed = JSON.parse(jsonText);
  } catch (err) {
    const wrapped = new Error("serialization output failed to parse");
    wrapped.code = DIAGNOSTIC_CODES.SERIALIZATION_FAILED;
    wrapped.cause = err;
    throw wrapped;
  }
  return deepClonePlain(parsed);
}

function captureEnvelope(graph, scopeCtx) {
  try {
    const clone = captureSerialized(graph);
    return envelope(true, { graph: clone }, scopeCtx);
  } catch (err) {
    return envelope(false, {
      code: DIAGNOSTIC_CODES.SERIALIZATION_FAILED,
      message: "graph serialization failed",
      detail: err && err.message ? err.message : "serialization_failed",
    }, scopeCtx);
  }
}

// ---------------------------------------------------------------------------
// Slice 3 detached capture evidence.
//
// This module exposes only preparatory observational evidence. Slice 3 is NOT
// closed: the seven reclassified S4 mutation/harness rows (NGA-048/050/062/
// 067/070/072/078 in vibecomfy_roundtrip.js) implement the private
// live-normalization bridge whose coupling makes full S3 closure atomic with
// Slice 4. No partial "S3 complete" claim is implied by these helpers.
//
// Every routine below operates on already-captured, detached plain data. It
// performs NO live writes and publishes NO live node/link/group/factory/slot.
// Semantic exec io/widget/socket normalization and stable identity validity,
// field meaning, ordering, and hashing stay owned by
// projection_registry_v1.js. The adapter does not derive semantic exec
// descriptors, does not hand-pick between `properties.vibecomfy.io` and
// `widgets_values[1]`, and does not self-attest a live-write count it cannot
// prove. The normalized capture only validates the requested contract and
// attaches a minimal contract/version evidence tag to the detached graph.
//
// Historical live exec hydration, widget assignment, link sanitation, socket
// splicing, and graph-link-store replacement are S4 mutation/harness behavior
// and are NOT performed here.
// ---------------------------------------------------------------------------

function normalizeOptionV1(options) {
  const opts = options ?? {};
  const requested = hasOwn(opts, "native_normalization")
    ? opts.native_normalization
    : null;
  if (requested === null || requested === undefined) {
    return null;
  }
  if (requested !== NATIVE_NORMALIZATION_V1) {
    const err = new Error("unsupported native normalization contract");
    err.code = "unsupported_normalization";
    throw err;
  }
  return NATIVE_NORMALIZATION_V1;
}

// Minimal, frozen contract/version evidence tag attached to a normalized
// detached capture. It declares only which normalization contract the
// capture honors and that the evidence is the detached serialized graph. It
// carries no semantic exec descriptors, no native ids, and no live-write
// count: those authorities stay with projection_registry_v1.js and the S4
// live-normalization bridge.
function nativeNormalizationEvidenceTag() {
  return Object.freeze({
    contract: NATIVE_NORMALIZATION_V1,
    evidence: "detached_serialized_graph_only",
  });
}

function drawSnapshotFromCaptured(captured) {
  const nodes = Array.isArray(captured?.nodes) ? captured.nodes : [];
  const groups = Array.isArray(captured?.groups) ? captured.groups : [];
  const seenNodeUids = new Set();
  const seenGroupIds = new Set();
  const ambiguousNodeUids = [];
  const ambiguousGroupIds = [];
  let missingNodeCount = 0;
  let missingGroupCount = 0;
  const nodeGeometry = [];
  for (const node of nodes) {
    let stableUid;
    try {
      stableUid = nodeIdentityV1(node);
    } catch (_err) {
      stableUid = null;
    }
    if (stableUid === null) {
      // Unstamped node geometry cannot be keyed by stable UID. The caller MUST
      // refuse with `missing_identity` rather than silently omitting it.
      missingNodeCount += 1;
      continue;
    }
    if (seenNodeUids.has(stableUid)) {
      if (!ambiguousNodeUids.includes(stableUid)) ambiguousNodeUids.push(stableUid);
      continue;
    }
    seenNodeUids.add(stableUid);
    nodeGeometry.push({
      uid: stableUid,
      pos: Array.isArray(node?.pos) ? node.pos.slice(0, 2) : null,
      size: Array.isArray(node?.size) ? node.size.slice(0, 2) : null,
      title: typeof node?.title === "string" ? node.title : null,
      color: node?.color ?? null,
      bgcolor: node?.bgcolor ?? null,
    });
  }
  const groupGeometry = [];
  for (const group of groups) {
    let stableId;
    try {
      stableId = groupIdentityV1(group);
    } catch (_err) {
      stableId = null;
    }
    if (stableId === null) {
      missingGroupCount += 1;
      continue;
    }
    if (seenGroupIds.has(stableId)) {
      if (!ambiguousGroupIds.includes(stableId)) ambiguousGroupIds.push(stableId);
      continue;
    }
    seenGroupIds.add(stableId);
    // Duplicate titles with distinct IDs remain valid: identity is the stable
    // id, not the human-readable title.
    groupGeometry.push({
      id: stableId,
      bounding: Array.isArray(group?.bounding) ? group.bounding.slice(0, 4) : null,
      title: typeof group?.title === "string" ? group.title : null,
      color: group?.color ?? null,
    });
  }
  return {
    snapshot: { nodes: nodeGeometry, groups: groupGeometry },
    ambiguous_node_uids: ambiguousNodeUids,
    ambiguous_group_ids: ambiguousGroupIds,
    missing_node_count: missingNodeCount,
    missing_group_count: missingGroupCount,
  };
}

function retagFailure(result, operation) {
  if (result.ok) return result;
  return envelope(false, result.diagnostic, {
    scope: result.scope,
    scope_contract: result.scope_contract,
    operation,
  });
}

export function createIntentGraphAdapter(app) {
  function capture(options) {
    let normalizationContract;
    try {
      normalizationContract = normalizeOptionV1(options);
    } catch (error) {
      return envelope(false, {
        code: DIAGNOSTIC_CODES.UNSUPPORTED_NORMALIZATION,
        message: "unsupported native normalization contract",
        detail: error?.message || "unsupported_normalization",
      }, { operation: "capture" });
    }
    const result = withGraph(app, "capture", options, (graph, scopeCtx) =>
      captureEnvelope(graph, scopeCtx)
    );
    if (!result.ok) return result;
    if (normalizationContract === null) return result;
    // Normalized capture: validate the requested contract and attach a minimal,
    // frozen contract/version evidence tag to the complete detached serialized
    // graph. The adapter performs no live write and derives no semantic exec
    // io/widget descriptors; that authority stays with
    // projection_registry_v1.js and the S4 live-normalization bridge.
    const payload = {
      graph: result.data.graph,
      normalization: nativeNormalizationEvidenceTag(),
    };
    return envelope(true, payload, {
      operation: "capture",
      scope: result.scope,
      scope_contract: result.scope_contract,
    });
  }

  function captureNormalized(options) {
    const withOption = { ...(options ?? {}), native_normalization: NATIVE_NORMALIZATION_V1 };
    const result = capture(withOption);
    if (!result.ok) return retagFailure(result, "capture_normalized");
    return envelope(true, result.data, {
      operation: "capture_normalized",
      scope: result.scope,
      scope_contract: result.scope_contract,
    });
  }

  function captureDrawSnapshot(options) {
    const result = capture(options);
    if (!result.ok) return retagFailure(result, "capture_draw_snapshot");
    const analysis = drawSnapshotFromCaptured(result.data.graph);
    const ctx = {
      operation: "capture_draw_snapshot",
      scope: result.scope,
      scope_contract: result.scope_contract,
    };
    if (analysis.ambiguous_node_uids.length > 0 || analysis.ambiguous_group_ids.length > 0) {
      const parts = [];
      if (analysis.ambiguous_node_uids.length) {
        parts.push(`node uids: ${analysis.ambiguous_node_uids.join(", ")}`);
      }
      if (analysis.ambiguous_group_ids.length) {
        parts.push(`group ids: ${analysis.ambiguous_group_ids.join(", ")}`);
      }
      return envelope(false, {
        code: DIAGNOSTIC_CODES.AMBIGUOUS_IDENTITY,
        message: "duplicate stable identity in captured graph draw snapshot",
        detail: `ambiguous ${parts.join("; ")}`,
      }, ctx);
    }
    if (analysis.missing_node_count > 0 || analysis.missing_group_count > 0) {
      const parts = [];
      if (analysis.missing_node_count) parts.push(`${analysis.missing_node_count} node(s)`);
      if (analysis.missing_group_count) parts.push(`${analysis.missing_group_count} group(s)`);
      return envelope(false, {
        code: DIAGNOSTIC_CODES.MISSING_IDENTITY,
        message: "captured graph draw snapshot has unstamped node/group geometry",
        detail: `${parts.join(" and ")} lack a stable identity; refusing per S3 identity contract`,
      }, ctx);
    }
    return envelope(true, { snapshot: analysis.snapshot }, ctx);
  }

  function enumerateNodes(options) {
    const result = capture(options);
    if (!result.ok) return retagFailure(result, "enumerate_nodes");
    const nodesValue = result.data.graph && result.data.graph.nodes;
    const nodes = Array.isArray(nodesValue) ? nodesValue : [];
    return envelope(true, { nodes: deepClonePlain(nodes) }, {
      scope: result.scope,
      scope_contract: result.scope_contract,
      operation: "enumerate_nodes",
    });
  }

  function capabilities(options) {
    return withGraph(app, "capabilities", options, (graph, scopeCtx) => {
      const canvas = app?.canvas;
      const graph_apply = graphApplyCapability(graph);
      return envelope(true, {
        serialize: typeof graph.serialize === "function",
        enumerate: typeof graph.serialize === "function",
        legacy_whole_graph_replace: graph_apply.available,
        graph_apply,
        delta_apply: deltaApplyCapability(app, graph),
        layout_apply: layoutApplyCapability(graph),
        revision: typeof graph.change === "function",
        dirty: typeof graph.setDirtyCanvas === "function" ||
          (canvas !== null && typeof canvas === "object" &&
            typeof canvas.setDirty === "function"),
        draw: canvas !== null && typeof canvas === "object" &&
          typeof canvas.draw === "function",
      }, scopeCtx);
    });
  }

  function captureRevision(options) {
    return withGraph(app, "capture_revision", options, (graph, scopeCtx) => {
      const revision = graph?.getRevision?.()
        ?? graph?.revision
        ?? graph?._vibecomfyLiveCanvasToken
        ?? graph?._vibecomfy_live_canvas_token
        ?? graph?._version
        ?? graph?._revision
        ?? null;
      return envelope(true, {
        revision: revision == null ? null : String(revision),
      }, scopeCtx);
    });
  }

  function notifyRevision(options) {
    return withGraph(app, "notify_revision", options, (graph, scopeCtx) => {
      if (typeof graph.change !== "function") {
        return envelope(false, {
          code: DIAGNOSTIC_CODES.REVISION_UNAVAILABLE,
          message: "graph.change is not available",
          detail: "revision primitive missing",
        }, scopeCtx);
      }
      try {
        graph.change();
      } catch (err) {
        return envelope(false, {
          code: DIAGNOSTIC_CODES.REVISION_FAILED,
          message: "graph.change threw",
          detail: err && err.message ? err.message : "revision_failed",
        }, scopeCtx);
      }
      return envelope(true, { revised: true }, scopeCtx);
    });
  }

  function repaint(options) {
    return withGraph(app, "repaint", options, (graph, scopeCtx) => {
      const canvas = app?.canvas;
      const hasGraphDirty = typeof graph.setDirtyCanvas === "function";
      const hasCanvasDirty = canvas !== null && typeof canvas === "object" &&
        typeof canvas.setDirty === "function";
      const hasDraw = canvas !== null && typeof canvas === "object" &&
        typeof canvas.draw === "function";
      if (!hasGraphDirty && !hasCanvasDirty && !hasDraw) {
        return envelope(false, {
          code: DIAGNOSTIC_CODES.REPAINT_UNAVAILABLE,
          message: "no dirty or draw primitive available",
          detail: "graph.setDirtyCanvas, canvas.setDirty, and canvas.draw absent",
        }, scopeCtx);
      }
      try {
        if (hasGraphDirty) {
          graph.setDirtyCanvas(true, true);
        } else if (hasCanvasDirty) {
          canvas.setDirty(true, true);
        }
        if (hasDraw) {
          canvas.draw(true, true);
        }
      } catch (err) {
        return envelope(false, {
          code: DIAGNOSTIC_CODES.REPAINT_FAILED,
          message: "repaint primitive threw",
          detail: err && err.message ? err.message : "repaint_failed",
        }, scopeCtx);
      }
      return envelope(true, { repainted: true }, scopeCtx);
    });
  }

  function project(projection, options) {
    let scopeCtx;
    try {
      scopeCtx = { ...resolveScope(options), operation: "project" };
      projectionSpecV1(projection);
      assertForwardProjectionV1(projection);
    } catch (err) {
      return envelope(false, {
        code: err?.code || DIAGNOSTIC_CODES.PROJECTION_FAILED,
        message: "projection validation failed",
        detail: err?.message || err?.code || "projection_failed",
      }, scopeCtx || { operation: "project" });
    }
    const captured = capture(options);
    if (!captured.ok) return retagFailure(captured, "project");
    try {
      const projected = projectGraphV1(captured.data.graph, projection);
      return envelope(true, {
        projection: deepClonePlain(projection),
        projected: deepClonePlain(projected),
      }, scopeCtx);
    } catch (err) {
      return envelope(false, {
        code: err?.code || DIAGNOSTIC_CODES.PROJECTION_FAILED,
        message: "projection failed",
        detail: err && err.message ? err.message : "projection_failed",
      }, scopeCtx);
    }
  }

  function projectionReference(projection, options) {
    let scopeCtx;
    try {
      scopeCtx = { ...resolveScope(options), operation: "projection_reference" };
      projectionSpecV1(projection);
      assertForwardProjectionV1(projection);
    } catch (err) {
      return envelope(false, {
        code: err?.code || DIAGNOSTIC_CODES.PROJECTION_FAILED,
        message: "projection reference validation failed",
        detail: err?.message || err?.code || "projection_failed",
      }, scopeCtx || { operation: "projection_reference" });
    }
    const captured = capture(options);
    if (!captured.ok) return retagFailure(captured, "projection_reference");
    try {
      const reference = projectionReferenceV1(captured.data.graph, projection);
      return envelope(true, {
        projection: deepClonePlain(projection),
        reference: deepClonePlain(reference),
      }, scopeCtx);
    } catch (err) {
      return envelope(false, {
        code: err?.code || DIAGNOSTIC_CODES.PROJECTION_FAILED,
        message: "projection reference failed",
        detail: err && err.message ? err.message : "projection_failed",
      }, scopeCtx);
    }
  }

  return Object.freeze({
    contract_version: INTENT_GRAPH_ADAPTER_V1,
    capture,
    captureNormalized,
    captureDrawSnapshot,
    enumerateNodes,
    capabilities,
    captureRevision,
    notifyRevision,
    repaint,
    project,
    projectionReference,
  });
}

export default createIntentGraphAdapter;
