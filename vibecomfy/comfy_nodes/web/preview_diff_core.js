// Pure serialized-graph preview diff shared by the live review overlay and the
// demo preview gallery. It deliberately has no app/panel/global canvas access.

function uidOf(node) {
  return node?.properties?.vibecomfy_uid || null;
}

function nodesByIdentity(liveGraph, candidateGraph) {
  const candidateNodes = Array.isArray(candidateGraph?.nodes) ? candidateGraph.nodes : [];
  const liveNodes = Array.isArray(liveGraph?.nodes) ? liveGraph.nodes : [];
  const candidateUidById = new Map();
  const candidateByUid = new Map();
  for (const node of candidateNodes) {
    const uid = uidOf(node) || (node?.id != null ? String(node.id) : null);
    if (!uid) continue;
    candidateByUid.set(uid, node);
    if (node.id != null) candidateUidById.set(String(node.id), uid);
  }
  const liveByUid = new Map();
  for (const node of liveNodes) {
    const uid = uidOf(node)
      || (node?.id != null ? candidateUidById.get(String(node.id)) || String(node.id) : null);
    if (uid) liveByUid.set(uid, node);
  }
  return { candidateNodes, liveNodes, candidateUidById, candidateByUid, liveByUid };
}

function values(node) {
  return Array.isArray(node?.widgets_values) ? node.widgets_values : [];
}

function sameValue(left, right) {
  return Object.is(left, right) || JSON.stringify(left) === JSON.stringify(right);
}

function parseLink(link) {
  const leadingId = Array.isArray(link) && link.length >= 6;
  return {
    originId: Array.isArray(link) ? link[leadingId ? 1 : 0] : link?.origin_id,
    originSlot: Array.isArray(link) ? link[leadingId ? 2 : 1] : link?.origin_slot,
    targetId: Array.isArray(link) ? link[leadingId ? 3 : 2] : link?.target_id,
    targetSlot: Array.isArray(link) ? link[leadingId ? 4 : 3] : link?.target_slot,
  };
}

function linkMaps(graph, uidById) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const nodeById = new Map(nodes.filter((node) => node?.id != null).map((node) => [String(node.id), node]));
  const graphUidById = new Map();
  for (const node of nodes) {
    if (node?.id == null) continue;
    graphUidById.set(String(node.id), uidOf(node) || uidById.get(String(node.id)) || String(node.id));
  }
  const rawLinks = Array.isArray(graph?.links)
    ? graph.links
    : graph?.links && typeof graph.links === "object" ? Object.values(graph.links) : [];
  const result = new Map();
  for (const rawLink of rawLinks) {
    const link = parseLink(rawLink);
    const fromUid = graphUidById.get(String(link.originId));
    const toUid = graphUidById.get(String(link.targetId));
    if (!fromUid || !toUid || link.originSlot == null || link.targetSlot == null) continue;
    const fromNode = nodeById.get(String(link.originId));
    const toNode = nodeById.get(String(link.targetId));
    const fromName = fromNode?.outputs?.[link.originSlot]?.name || String(link.originSlot);
    const toName = toNode?.inputs?.[link.targetSlot]?.name || String(link.targetSlot);
    const physical = `${fromUid}::#${link.originSlot}->${toUid}::#${link.targetSlot}`;
    result.set(physical, `${fromUid}::${fromName}->${toUid}::${toName}`);
  }
  return result;
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
  const baseline = nodesByIdentity(baselineGraph, candidateGraph).liveByUid;
  const candidate = nodesByIdentity(baselineGraph, candidateGraph).candidateByUid;
  const result = [];
  for (const [uid, before] of baseline) {
    const after = candidate.get(uid);
    if (!after || !Array.isArray(before?.pos) || !Array.isArray(after?.pos)) continue;
    if (Number(before.pos[0]) !== Number(after.pos[0]) || Number(before.pos[1]) !== Number(after.pos[1])) {
      result.push({ uid, from: [Number(before.pos[0]), Number(before.pos[1])], to: [Number(after.pos[0]), Number(after.pos[1])] });
    }
  }
  return result;
}

function layoutGroups(baselineGraph, candidateGraph) {
  if (!baselineGraph) return [];
  return (Array.isArray(candidateGraph?.groups) ? candidateGraph.groups : [])
    .map((group, index) => {
      const raw = group?.bounding || group?._bounding;
      const bounds = Array.from({ length: 4 }, (_unused, coordinate) => Number(raw?.[coordinate]));
      if (!raw || !bounds.every(Number.isFinite) || bounds[2] <= 0 || bounds[3] <= 0) return null;
      return {
        key: group?.id != null ? `id:${String(group.id)}` : `index:${index}`,
        title: typeof group?.title === "string" ? group.title : "Group",
        color: typeof group?.color === "string" ? group.color : null,
        bounds: { x: bounds[0], y: bounds[1], w: bounds[2], h: bounds[3] },
      };
    })
    .filter(Boolean);
}

export function computeSerializedGraphPreviewDiff({
  liveGraph,
  candidateGraph,
  fieldChanges = [],
  layoutBaselineGraph = null,
} = {}) {
  const { candidateUidById, candidateByUid, liveByUid } = nodesByIdentity(liveGraph, candidateGraph);
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
  const liveLinks = linkMaps(liveGraph, candidateUidById);
  const candidateLinks = linkMaps(candidateGraph, candidateUidById);
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
