// Pure serialized-graph preview diff shared by the live review overlay and the
// demo preview gallery. It deliberately has no app/panel/global canvas access.

import {
  computeCanvasProjectionHash,
  computeMutationPlanHash,
  crossGraphNodeIdentityIndexV1,
  extractCanvasProjection,
  stableGroupIdentityOrNullV1,
  stablePreviewLinkMapV1,
} from "./projection_registry_v1.js";

export {
  computeCanvasProjectionHash,
  computeMutationPlanHash,
  extractCanvasProjection,
} from "./projection_registry_v1.js";

export function previewFailure() {
  return {
    ok: false,
    kind: "PreviewError",
    failure_kind: "PreviewError",
    stage: "preview",
    message: "Unable to compute preview diff.",
  };
}

function values(node) {
  return Array.isArray(node?.widgets_values) ? node.widgets_values : [];
}

function sameValue(left, right) {
  return Object.is(left, right) || JSON.stringify(left) === JSON.stringify(right);
}

function parseDisplayLink(key) {
  const match = /^(.+?)::(.+?)->(.+?)::(.+)$/.exec(String(key || ""));
  return match ? { fromUid: match[1], fromPort: match[2], toUid: match[3], toPort: match[4] } : null;
}

function normalizedFieldChanges(fieldChanges) {
  return (Array.isArray(fieldChanges) ? fieldChanges : [])
    .map((change) => ({
      ...change,
      uid: change?.uid != null ? String(change.uid) : null,
      fieldPath: change?.fieldPath || change?.field_path || null,
    }))
    .filter((change) => change.uid && change.fieldPath);
}

function isLinkValue(value) {
  return Boolean(
    value
    && typeof value === "object"
    && !Array.isArray(value)
    && value.uid != null
    && (value.output_slot != null || value.outputSlot != null),
  );
}

function linkTouchesUid(key, uid) {
  const parsed = parseDisplayLink(key);
  return Boolean(parsed && (parsed.fromUid === uid || parsed.toUid === uid));
}

/**
 * Constrain a legacy full-graph diff to the mutations the edit engine says
 * actually landed. Older archived turns do not contain canonical delta_ops,
 * and their regenerated candidate UI can rewrite unrelated widget arrays and
 * port metadata. Those differences are useful diagnostics, but are not user
 * intent and must not become review highlights.
 */
export function constrainPreviewDiffToLegacyIntent({
  graphDiff,
  fieldChanges = [],
  changeDetails = null,
} = {}) {
  const raw = graphDiff || {};
  const fields = normalizedFieldChanges(fieldChanges);
  const batchTurns = Array.isArray(changeDetails?.batch_turns) ? changeDetails.batch_turns : [];
  const landedStatements = batchTurns.flatMap((turn) => (
    Array.isArray(turn?.statements) ? turn.statements : []
  )).filter((statement) => statement?.landed === true);
  const mutatingStatements = landedStatements.filter((statement) => [
    "set_node_field",
    "set_mode",
    "upsert_link",
    "remove_link",
    "add_node",
    "node_call",
    "remove_node",
  ].includes(statement?.op_kind));

  if (fields.length === 0 && mutatingStatements.length === 0) {
    return { ...raw, _legacyIntentDerived: false };
  }

  const addedRaw = Array.isArray(raw.added) ? raw.added : [];
  const removedRaw = Array.isArray(raw.removed) ? raw.removed : [];
  const nodeCallCount = mutatingStatements.filter((statement) => (
    statement.op_kind === "node_call" || statement.op_kind === "add_node"
  )).length;
  const explicitlyRemovedUids = new Set(mutatingStatements
    .filter((statement) => statement.op_kind === "remove_node")
    .flatMap((statement) => Array.isArray(statement.touched_uids) ? statement.touched_uids : [])
    .map(String));

  // New-node statements in legacy transcripts did not consistently report
  // their generated uid, so the graph's new nodes are accepted only up to the
  // number of explicit constructors that landed. Removals do carry their uid.
  const added = nodeCallCount > 0 ? addedRaw.slice(0, nodeCallCount) : [];
  const removed = explicitlyRemovedUids.size > 0
    ? removedRaw.filter((entry) => explicitlyRemovedUids.has(String(entry?.uid)))
    : [];
  const structuralUids = new Set([
    ...added.map((entry) => String(entry?.uid)),
    ...removed.map((entry) => String(entry?.uid)),
  ].filter(Boolean));
  const linkFields = fields.filter((field) => isLinkValue(field.old) || isLinkValue(field.new));
  const rawLinks = [
    ...(Array.isArray(raw.added_links) ? raw.added_links : []),
    ...(Array.isArray(raw.removed_links) ? raw.removed_links : []),
  ];
  const exactLinkFields = new Set(linkFields.filter((field) => rawLinks.some((key) => {
    const parsed = parseDisplayLink(key);
    return parsed?.toUid === field.uid && parsed?.toPort === field.fieldPath;
  })).map((field) => `${field.uid}::${field.fieldPath}`));
  const keepLink = (key) => (
    linkFields.some((field) => {
      const parsed = parseDisplayLink(key);
      if (parsed?.toUid !== field.uid) return false;
      return !exactLinkFields.has(`${field.uid}::${field.fieldPath}`)
        || parsed.toPort === field.fieldPath;
    })
    || [...structuralUids].some((uid) => linkTouchesUid(key, uid))
  );

  const editedByUid = new Map();
  for (const field of fields) {
    if (structuralUids.has(field.uid)) continue;
    let entry = editedByUid.get(field.uid);
    if (!entry) {
      entry = { uid: field.uid, changedWidgetIndices: [] };
      editedByUid.set(field.uid, entry);
    }
    const widgetMatch = /^(?:widget_|widgets(?:_values)?\.)(\d+)$/.exec(String(field.fieldPath));
    if (widgetMatch) {
      const widgetIndex = Number(widgetMatch[1]);
      if (!entry.changedWidgetIndices.includes(widgetIndex)) entry.changedWidgetIndices.push(widgetIndex);
    }
  }

  return {
    ...raw,
    edited: [...editedByUid.values()],
    added,
    removed,
    added_links: (Array.isArray(raw.added_links) ? raw.added_links : []).filter(keepLink),
    removed_links: (Array.isArray(raw.removed_links) ? raw.removed_links : []).filter(keepLink),
    _legacyIntentDerived: true,
    _roundtripDrift: {
      edited: Array.isArray(raw.edited) ? raw.edited.length : 0,
      added_links: Array.isArray(raw.added_links) ? raw.added_links.length : 0,
      removed_links: Array.isArray(raw.removed_links) ? raw.removed_links.length : 0,
    },
  };
}

function promoteChangedLinkTargets(edited, addedLinks, removedLinks, liveByUid, candidateByUid) {
  const sourcesByTarget = (links) => {
    const grouped = new Map();
    for (const key of links) {
      const parsed = parseDisplayLink(key);
      if (!parsed) continue;
      const target = `${parsed.toUid}::${parsed.toPort}`;
      if (!grouped.has(target)) grouped.set(target, { uid: parsed.toUid, sources: new Set() });
      grouped.get(target).sources.add(`${parsed.fromUid}::${parsed.fromPort}`);
    }
    return grouped;
  };
  const added = sourcesByTarget(addedLinks);
  const removed = sourcesByTarget(removedLinks);
  const editedByUid = new Map(edited.map((entry) => [entry.uid, entry]));
  for (const target of new Set([...added.keys(), ...removed.keys()])) {
    const a = added.get(target);
    const r = removed.get(target);
    const uid = a?.uid || r?.uid;
    if (!uid || !liveByUid.has(uid) || !candidateByUid.has(uid)) continue;
    const aSources = a?.sources || new Set();
    const rSources = r?.sources || new Set();
    const same = aSources.size === rSources.size && [...aSources].every((source) => rSources.has(source));
    if (!same && !editedByUid.has(uid)) {
      const entry = { uid, changedWidgetIndices: [] };
      editedByUid.set(uid, entry);
      edited.push(entry);
    }
  }
}

function layoutMoves(baselineGraph, candidateGraph) {
  if (!baselineGraph) return [];
  const index = crossGraphNodeIdentityIndexV1(baselineGraph, candidateGraph);
  const baseline = index.liveByUid;
  const candidate = index.candidateByUid;
  const result = [];
  for (const [uid, before] of baseline) {
    const after = candidate.get(uid);
    if (!after) continue;
    const beforePos = [Number(before?.pos?.[0] ?? 0), Number(before?.pos?.[1] ?? 0)];
    const afterPos = [Number(after?.pos?.[0] ?? 0), Number(after?.pos?.[1] ?? 0)];
    const beforeSize = [Number(before?.size?.[0] ?? 200), Number(before?.size?.[1] ?? 100)];
    const afterSize = [Number(after?.size?.[0] ?? 200), Number(after?.size?.[1] ?? 100)];
    const dx = afterPos[0] - beforePos[0];
    const dy = afterPos[1] - beforePos[1];
    const dw = afterSize[0] - beforeSize[0];
    const dh = afterSize[1] - beforeSize[1];
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5 && Math.abs(dw) < 0.5 && Math.abs(dh) < 0.5) continue;
    result.push({
      uid,
      class_type: after?.type || after?.class_type || before?.type || before?.class_type || null,
      before: { x: beforePos[0], y: beforePos[1], w: beforeSize[0], h: beforeSize[1] },
      after: { x: afterPos[0], y: afterPos[1], w: afterSize[0], h: afterSize[1] },
      dx,
      dy,
      resized: Math.abs(dw) >= 0.5 || Math.abs(dh) >= 0.5,
    });
  }
  return result;
}

/**
 * Extract a group's bounding box from its serialized representation.
 *
 * ComfyUI represents group bounds as [x, y, width, height] stored under
 * `bounding` or `_bounding`.  Returns null when the group has no valid
 * bounding box (missing, non-finite, or non-positive dimensions).
 *
 * @param {object} group  serialized group object
 * @returns {{x: number, y: number, w: number, h: number} | null}
 */
function readGroupBounds(group) {
  const raw = group?.bounding || group?._bounding;
  if (!raw) return null;
  const x = Number(raw[0]);
  const y = Number(raw[1]);
  const w = Number(raw[2]);
  const h = Number(raw[3]);
  if (![x, y, w, h].every(Number.isFinite) || w <= 0 || h <= 0) return null;
  return { x, y, w, h };
}

/**
 * Build a Map of group layout keys to their bounds for a given graph.
 *
 * @param {object} graph  serialized graph with optional `.groups` array
 * @returns {Map<string, {x: number, y: number, w: number, h: number}>}
 */
function baselineGroupBoundsMap(graph) {
  const result = new Map();
  const groups = Array.isArray(graph?.groups) ? graph.groups : [];
  for (let i = 0; i < groups.length; i += 1) {
    const bounds = readGroupBounds(groups[i]);
    if (bounds) {
      const key = stableGroupIdentityOrNullV1(groups[i]);
      if (key) result.set(key, bounds);
    }
  }
  return result;
}

/**
 * Compare two group bounding boxes for equality within a half-pixel tolerance.
 *
 * @param {object} left   {x, y, w, h}
 * @param {object} right  {x, y, w, h}
 * @returns {boolean}
 */
function groupBoundsEqual(left, right) {
  return (
    Math.abs(left.x - right.x) < 0.5
    && Math.abs(left.y - right.y) < 0.5
    && Math.abs(left.w - right.w) < 0.5
    && Math.abs(left.h - right.h) < 0.5
  );
}

/**
 * Collect layout-group entries from the exact candidate patch, with optional
 * baseline comparison data for group geometry parity.
 *
 * The function always renders from the candidate patch — the authoritative
 * representation of the proposed layout.  When a baseline graph is provided,
 * each returned entry also carries `_baselineBounds` (the baseline group
 * bounds for the same key, or null when the group is new) and `_changed`
 * (true when the candidate and baseline bounds differ).
 *
 * Groups present in the baseline but absent from the candidate are listed
 * under `_removedGroupKeys` (an array of layout keys), so the overlay can
 * render them as removed.
 *
 * The return value is a plain Array for backward compatibility with all
 * existing consumers that iterate `layout_groups`.
 *
 * @param {object|null} baselineGraph   serialized baseline graph (live canvas)
 * @param {object}      candidateGraph  serialized candidate graph (patch)
 * @returns {Array<{key: string, title: string, color: string|null, bounds: {x,y,w,h}, _baselineBounds?: {x,y,w,h}|null, _changed?: boolean}>}
 */
function layoutGroups(baselineGraph, candidateGraph) {
  const candidateGroups = Array.isArray(candidateGraph?.groups) ? candidateGraph.groups : [];

  // Always extract candidate groups from the exact candidate patch —
  // even when no baseline is available for comparison.
  const entries = [];
  const candidateKeys = new Set();
  for (let i = 0; i < candidateGroups.length; i += 1) {
    const group = candidateGroups[i];
    const bounds = readGroupBounds(group);
    if (!bounds) continue;
    const key = stableGroupIdentityOrNullV1(group);
    if (!key) continue;
    candidateKeys.add(key);
    entries.push({
      key,
      title: typeof group?.title === "string" ? group.title : "Group",
      color: typeof group?.color === "string" ? group.color : null,
      bounds,
      _baselineBounds: null,
      _changed: false,
    });
  }

  // When a baseline is available, compare against applied group geometry.
  if (baselineGraph) {
    const baselineMap = baselineGroupBoundsMap(baselineGraph);
    const removedGroupKeys = [];
    for (const [key] of baselineMap) {
      if (!candidateKeys.has(key)) {
        removedGroupKeys.push(key);
      }
    }
    for (const entry of entries) {
      const baselineBounds = baselineMap.get(entry.key) || null;
      entry._baselineBounds = baselineBounds;
      entry._changed = baselineBounds ? !groupBoundsEqual(entry.bounds, baselineBounds) : true;
    }
    if (removedGroupKeys.length > 0) {
      // Attach removed-group keys as a non-enumerable sentinel so the overlay
      // can optionally render removed-group indicators, but standard array
      // iteration does not accidentally treat them as entries.
      Object.defineProperty(entries, "_removedGroupKeys", {
        value: removedGroupKeys,
        writable: false,
        enumerable: false,
        configurable: false,
      });
    }
  }

  return entries;
}

export function computeSerializedGraphPreviewDiff({
  liveGraph,
  candidateGraph,
  fieldChanges = [],
  layoutBaselineGraph = null,
} = {}) {
  const { candidateUidByNativeId, candidateByUid, liveByUid } = crossGraphNodeIdentityIndexV1(
    liveGraph,
    candidateGraph,
  );
  const edited = [];
  for (const [uid, liveNode] of liveByUid) {
    const candidateNode = candidateByUid.get(uid);
    if (!candidateNode) continue;
    const liveValues = values(liveNode);
    const candidateValues = values(candidateNode);
    const changedWidgetIndices = [];
    for (let index = 0; index < Math.max(liveValues.length, candidateValues.length); index += 1) {
      if (!sameValue(liveValues[index], candidateValues[index])) changedWidgetIndices.push(index);
    }
    if (changedWidgetIndices.length) edited.push({ uid, changedWidgetIndices });
  }
  const added = [];
  for (const [uid, node] of candidateByUid) {
    if (liveByUid.has(uid)) continue;
    added.push({
      uid,
      class_type: node?.type || node?.class_type || null,
      unwiredRequiredInputs: (Array.isArray(node?.inputs) ? node.inputs : [])
        .filter((input) => !input?.link && !input?.widget)
        .map((input) => input?.name || null)
        .filter(Boolean),
    });
  }
  const removed = [];
  for (const [uid, node] of liveByUid) {
    if (!candidateByUid.has(uid)) removed.push({ uid, class_type: node?.type || node?.class_type || null });
  }
  const liveLinks = stablePreviewLinkMapV1(liveGraph, candidateUidByNativeId);
  const candidateLinks = stablePreviewLinkMapV1(candidateGraph, candidateUidByNativeId);
  const added_links = [...candidateLinks].filter(([physical]) => !liveLinks.has(physical)).map(([, display]) => display);
  const removed_links = [...liveLinks].filter(([physical]) => !candidateLinks.has(physical)).map(([, display]) => display);
  promoteChangedLinkTargets(edited, added_links, removed_links, liveByUid, candidateByUid);

  const edited_fields = [];
  const seenFields = new Set();
  for (const change of Array.isArray(fieldChanges) ? fieldChanges : []) {
    const uid = change?.uid ? String(change.uid) : null;
    const fieldPath = change?.fieldPath || change?.field_path || null;
    if (!uid || !fieldPath || (!liveByUid.has(uid) && !candidateByUid.has(uid))) continue;
    const key = `${uid}::${fieldPath}`;
    if (seenFields.has(key)) continue;
    seenFields.add(key);
    const raw = change?.new;
    const newValue = raw == null ? (raw === null ? "null" : null)
      : typeof raw === "object" ? (Array.isArray(raw) ? "[…]" : "{…}") : String(raw);
    edited_fields.push({ uid, field_path: fieldPath, new_value: newValue });
  }

  return {
    edited,
    edited_fields,
    added,
    removed,
    layout_moved: layoutMoves(layoutBaselineGraph, candidateGraph),
    layout_groups: layoutGroups(layoutBaselineGraph, candidateGraph),
    unresolved: [],
    added_links,
    removed_links,
  };
}

// ── Browser-side mutation-plan and canvas projection hashing ─────────────────
//
// The functions below are the browser-side authority for computing the
// mutation-plan hash and the post-apply canvas projection hash.  They
// delegate to `sha256Hex` from `canonical_hash.js`, which mirrors the
// Python backend's `_canonical_bytes` + `_sha256` semantics exactly:
// recursive key-sorting, compact separators, ASCII-safe escaping, and
// string fallback for non-JSON-serializable values.
//
// All lifecycle consumers (preview, apply, verify) MUST use these
// functions so that browser-side hashes match the Python backend
// byte-for-byte for equivalent plan / canvas data.

/**
 * Compute the SHA-256 hex digest of a mutation-plan projection using the JS
 * canonical hash mirror.
 *
 * The `planProjection` object should mirror the Python
 * `LayoutCandidatePatch.__post_init__` projection fields:
 *
 *   - store_version  (number)
 *   - vibecomfy_version (string)
 *   - schema_hash    (string)
 *   - entries        (object: node-id → {pos, size, flags, color, ...})
 *   - groups         (array of {title, bounding, color, ...})
 *   - extra          (object)
 *   - lastRerouteId  (any)
 *   - definitions    (object)
 *   - virtual_wires  (object)
 *   - unkeyed        (array)
 *
 * Only the fields present in the projection are hashed; callers may pass a
 * subset when computing a partial hash (e.g. canvas-only projection).
 *
 * @param {object} planProjection
 * @returns {string} 64-character lowercase hex digest
 */
/**
 * Compute the SHA-256 hex digest of a post-apply serialized canvas projection.
 *
 * A canvas projection is the visual / positional subset of the mutation plan:
 * node positions, sizes, flags, colors, group bounding boxes, titles, colors,
 * and any extra canvas-level metadata.  Structural graph data (links, widget
 * values) that is NOT part of the canvas arrangement should be excluded so
 * that the canvas hash is stable under layout-only reorganise passes.
 *
 * The canonical shape mirrors the entries + groups + extra subset of the
 * full mutation-plan projection:
 *
 *   {
 *     entries: { [nodeId]: { pos, size, flags, color, bgcolor, mode, order } },
 *     groups:  [{ title, bounding, color, font_size, locked }],
 *     extra:   { ... }
 *   }
 *
 * @param {object} canvasProjection
 * @returns {string} 64-character lowercase hex digest
 */
/**
 * Extract the canvas-only projection from a candidate graph whose nodes carry
 * position / size / flags / color furniture.  This is the subset signed by the
 * plan_hash when structural graph changes are absent (layout-only reorganise).
 *
 * @param {object} candidateGraph  serialized graph with `.nodes`, `.groups`,
 *                                 and optionally `.extra`.
 * @returns {object} canvas projection suitable for `computeCanvasProjectionHash`
 */
