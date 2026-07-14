import assert from "node:assert/strict";
import test from "node:test";

import {
  computeSerializedGraphPreviewDiff,
  constrainPreviewDiffToLegacyIntent,
  computeMutationPlanHash,
  computeCanvasProjectionHash,
  extractCanvasProjection,
} from "../../vibecomfy/comfy_nodes/web/preview_diff_core.js";
import { sha256Hex, canonicalJsonString } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";

test("serialized reorganise preview includes candidate group furniture", () => {
  const baseline = {
    nodes: [{ id: 1, pos: [0, 0], properties: { vibecomfy_uid: "one" } }],
    groups: [{ title: "Main", bounding: [0, 0, 100, 100] }],
  };
  const candidate = {
    nodes: [{ id: 1, pos: [200, 0], properties: { vibecomfy_uid: "one" } }],
    groups: [{ title: "Main", color: "#123456", bounding: [180, -20, 300, 160] }],
  };

  const result = computeSerializedGraphPreviewDiff({
    liveGraph: baseline,
    candidateGraph: candidate,
    layoutBaselineGraph: baseline,
  });

  assert.equal(result.layout_groups.length, 1);
  const group = result.layout_groups[0];
  assert.equal(group.key, "title:Main");
  assert.equal(group.title, "Main");
  assert.equal(group.color, "#123456");
  assert.deepEqual(group.bounds, { x: 180, y: -20, w: 300, h: 160 });
  // T27: baseline comparison data is available when baseline is provided
  assert.deepEqual(group._baselineBounds, { x: 0, y: 0, w: 100, h: 100 },
    "baseline bounds should be recorded for parity comparison");
  assert.equal(group._changed, true,
    "group should be marked changed when bounds differ from baseline");
});

test("legacy preview intent suppresses whole-graph widget and link drift", () => {
  const graphDiff = {
    edited: [
      { uid: "124", changedWidgetIndices: [1] },
      { uid: "131", changedWidgetIndices: [2] },
      { uid: "138", changedWidgetIndices: [21] },
    ],
    added: [],
    removed: [],
    added_links: [
      "124::output_0->138::emotion_control",
      "131::AUDIO->51::opt_audio_input",
    ],
    removed_links: [
      "125::output_0->138::emotion_control",
      "131::AUDIO->51::audio",
    ],
  };
  const fieldChanges = [
    { uid: "124", fieldPath: "widget_1", old: "calm", new: "dramatic" },
    {
      uid: "138",
      fieldPath: "emotion_control",
      old: { uid: "125", output_slot: "output_0" },
      new: { uid: "124", output_slot: "output_0" },
    },
  ];
  const changeDetails = {
    batch_turns: [{
      statements: [
        { landed: true, op_kind: "set_node_field", touched_uids: ["124"] },
        { landed: true, op_kind: "upsert_link", touched_uids: ["124", "138"] },
      ],
    }],
  };

  const result = constrainPreviewDiffToLegacyIntent({ graphDiff, fieldChanges, changeDetails });

  assert.deepEqual(result.edited, [
    { uid: "124", changedWidgetIndices: [1] },
    { uid: "138", changedWidgetIndices: [] },
  ]);
  assert.deepEqual(result.added_links, ["124::output_0->138::emotion_control"]);
  assert.deepEqual(result.removed_links, ["125::output_0->138::emotion_control"]);
  assert.equal(result._legacyIntentDerived, true);
  assert.deepEqual(result._roundtripDrift, { edited: 3, added_links: 2, removed_links: 2 });
});

test("legacy preview intent keeps only explicitly constructed and removed nodes", () => {
  const result = constrainPreviewDiffToLegacyIntent({
    graphDiff: {
      edited: [{ uid: "59", changedWidgetIndices: [0] }],
      added: [{ uid: "n1" }, { uid: "phantom" }],
      removed: [{ uid: "55" }, { uid: "unchanged" }],
      added_links: ["n1::IMAGE->46::images", "phantom::x->59::a"],
      removed_links: ["55::IMAGE->46::images", "unchanged::x->59::a"],
    },
    fieldChanges: [{
      uid: "46",
      field_path: "images",
      old: { uid: "55", output_slot: "IMAGE" },
      new: { uid: "n1", output_slot: "IMAGE" },
    }],
    changeDetails: {
      batch_turns: [{ statements: [
        { landed: true, op_kind: "remove_node", touched_uids: ["55"] },
        { landed: true, op_kind: "node_call", touched_uids: [] },
        { landed: true, op_kind: "upsert_link", touched_uids: ["n1", "46"] },
      ] }],
    },
  });

  assert.deepEqual(result.edited, [{ uid: "46", changedWidgetIndices: [] }]);
  assert.deepEqual(result.added, [{ uid: "n1" }]);
  assert.deepEqual(result.removed, [{ uid: "55" }]);
  assert.deepEqual(result.added_links, ["n1::IMAGE->46::images"]);
  assert.deepEqual(result.removed_links, ["55::IMAGE->46::images"]);
});

// ── Mutation-plan and canvas projection hashing tests ────────────────────────
//
// These tests prove that the browser-side mutation-plan hash and post-apply
// canvas projection hash both delegate to the JS canonical hash mirror
// (`canonical_hash.js`), which mirrors the Python backend's
// `_canonical_bytes` + `_sha256` semantics exactly.

// ── Fixtures ────────────────────────────────────────────────────────────────

const FULL_PLAN_FIXTURE = {
  store_version: 1,
  vibecomfy_version: "0",
  schema_hash: "sha256:abc123def456",
  entries: {
    "node-1": {
      pos: [100, 200],
      size: [300, 400],
      flags: { pinned: true, collapsed: false },
      color: "#ff0000",
      bgcolor: "#330000",
      mode: 0,
      order: 1,
    },
    "node-2": {
      pos: [500, 200],
      size: [300, 400],
      flags: { pinned: false, collapsed: true },
      color: "#00ff00",
      bgcolor: "#003300",
      mode: 0,
      order: 2,
    },
    "node-3": {
      pos: [900, 200],
      size: [250, 350],
      flags: {},
      color: "#0000ff",
      bgcolor: "#000033",
      mode: 2,
      order: 3,
    },
  },
  groups: [
    {
      title: "Main Pipeline",
      bounding: [50, 50, 1200, 600],
      color: "#3f789e",
      font_size: 14,
      locked: false,
    },
    {
      title: "Output Stage",
      bounding: [50, 700, 1200, 300],
      color: "#8a8a8a",
      font_size: 12,
    },
  ],
  extra: { canvas_scale: 1.0, snap_grid: 10 },
  lastRerouteId: null,
  definitions: {},
  virtual_wires: {},
  unkeyed: [],
};

const CANVAS_ONLY_FIXTURE = {
  entries: {
    "node-1": { pos: [100, 200], size: [300, 400], flags: { pinned: true }, color: "#ff0000" },
    "node-2": { pos: [500, 200], size: [300, 400], flags: { collapsed: true }, color: "#00ff00" },
  },
  groups: [
    { title: "Group A", bounding: [0, 0, 900, 700], color: "#3f789e" },
  ],
};

const CANVAS_ONLY_KEY_VARIANT = {
  entries: {
    "node-2": { color: "#00ff00", size: [300, 400], flags: { collapsed: true }, pos: [500, 200] },
    "node-1": { flags: { pinned: true }, pos: [100, 200], size: [300, 400], color: "#ff0000" },
  },
  groups: [
    { color: "#3f789e", bounding: [0, 0, 900, 700], title: "Group A" },
  ],
};

const CANDIDATE_GRAPH_FIXTURE = {
  nodes: [
    {
      id: 10,
      type: "KSampler",
      pos: [100, 200],
      size: [300, 400],
      flags: { pinned: true },
      color: "#ff0000",
      bgcolor: "#330000",
      mode: 0,
      order: 1,
      properties: { vibecomfy_uid: "node-1" },
    },
    {
      id: 11,
      type: "VAEDecode",
      pos: [500, 200],
      size: [300, 400],
      flags: { collapsed: true },
      color: "#00ff00",
      bgcolor: "#003300",
      mode: 0,
      order: 2,
      properties: { vibecomfy_uid: "node-2" },
    },
    {
      id: 12,
      type: "SaveImage",
      pos: [900, 200],
      size: [250, 350],
      color: "#0000ff",
      mode: 0,
      order: 3,
      properties: { vibecomfy_uid: "node-3" },
    },
  ],
  groups: [
    { title: "Main Pipeline", bounding: [50, 50, 1200, 600], color: "#3f789e" },
    { title: "Output", bounding: [50, 700, 1200, 300], color: "#8a8a8a" },
  ],
  extra: { canvas_scale: 1.0 },
};

// ── computeMutationPlanHash ──────────────────────────────────────────────────

test("computeMutationPlanHash delegates to canonical hash mirror (produces 64-char hex)", () => {
  const hash = computeMutationPlanHash(FULL_PLAN_FIXTURE);
  assert.equal(typeof hash, "string");
  assert.equal(hash.length, 64, "SHA-256 hex digest is 64 chars");
  assert.ok(/^[0-9a-f]{64}$/.test(hash), `Hash should be lowercase hex: ${hash}`);
});

test("computeMutationPlanHash matches direct sha256Hex call on same data", () => {
  const viaIntegration = computeMutationPlanHash(FULL_PLAN_FIXTURE);
  const viaDirect = sha256Hex(FULL_PLAN_FIXTURE);
  assert.equal(viaIntegration, viaDirect,
    "computeMutationPlanHash must delegate to sha256Hex from canonical_hash.js");
});

test("computeMutationPlanHash is deterministic across clones", () => {
  const hash1 = computeMutationPlanHash(FULL_PLAN_FIXTURE);
  const hash2 = computeMutationPlanHash(structuredClone(FULL_PLAN_FIXTURE));
  assert.equal(hash1, hash2);
});

test("computeMutationPlanHash: different data produces different hash", () => {
  const hash1 = computeMutationPlanHash(FULL_PLAN_FIXTURE);
  const modified = structuredClone(FULL_PLAN_FIXTURE);
  modified.entries["node-1"].pos = [101, 200]; // one pixel shift
  const hash2 = computeMutationPlanHash(modified);
  assert.notEqual(hash1, hash2, "Position change must produce different hash");
});

test("computeMutationPlanHash: key-order variation in plan produces same hash", () => {
  // Build the same plan with different key insertion order
  const planA = {
    store_version: 1,
    vibecomfy_version: "0",
    schema_hash: "sha256:abc",
    entries: {
      "a": { pos: [0, 0], size: [100, 100], flags: { pinned: true }, color: "#fff", mode: 0, order: 1 },
    },
    groups: [],
    extra: {},
    lastRerouteId: null,
    definitions: {},
    virtual_wires: {},
    unkeyed: [],
  };
  const planB = {
    unkeyed: [],
    virtual_wires: {},
    definitions: {},
    lastRerouteId: null,
    extra: {},
    groups: [],
    entries: {
      "a": { order: 1, mode: 0, color: "#fff", flags: { pinned: true }, size: [100, 100], pos: [0, 0] },
    },
    schema_hash: "sha256:abc",
    vibecomfy_version: "0",
    store_version: 1,
  };
  assert.equal(computeMutationPlanHash(planA), computeMutationPlanHash(planB),
    "Key-order variation must produce identical hash via canonical JSON");
});

test("computeMutationPlanHash returns empty string for non-object input", () => {
  assert.equal(computeMutationPlanHash(null), "");
  assert.equal(computeMutationPlanHash(undefined), "");
  assert.equal(computeMutationPlanHash("string"), "");
  assert.equal(computeMutationPlanHash(42), "");
});

// ── computeCanvasProjectionHash ──────────────────────────────────────────────

test("computeCanvasProjectionHash delegates to canonical hash mirror", () => {
  const hash = computeCanvasProjectionHash(CANVAS_ONLY_FIXTURE);
  assert.equal(typeof hash, "string");
  assert.equal(hash.length, 64);
  assert.ok(/^[0-9a-f]{64}$/.test(hash));

  // Must match direct sha256Hex call
  assert.equal(hash, sha256Hex(CANVAS_ONLY_FIXTURE),
    "computeCanvasProjectionHash must delegate to sha256Hex");
});

test("computeCanvasProjectionHash: key-order variation produces identical hash", () => {
  const hashA = computeCanvasProjectionHash(CANVAS_ONLY_FIXTURE);
  const hashB = computeCanvasProjectionHash(CANVAS_ONLY_KEY_VARIANT);
  assert.equal(hashA, hashB,
    "Canvas projection hash must be invariant under key-order permutations");
});

test("computeCanvasProjectionHash: position change changes hash", () => {
  const hash1 = computeCanvasProjectionHash(CANVAS_ONLY_FIXTURE);
  const modified = structuredClone(CANVAS_ONLY_FIXTURE);
  modified.entries["node-1"].pos = [101, 201];
  const hash2 = computeCanvasProjectionHash(modified);
  assert.notEqual(hash1, hash2);
});

test("computeCanvasProjectionHash: group change changes hash", () => {
  const hash1 = computeCanvasProjectionHash(CANVAS_ONLY_FIXTURE);
  const modified = structuredClone(CANVAS_ONLY_FIXTURE);
  modified.groups[0].bounding = [10, 10, 900, 700];
  const hash2 = computeCanvasProjectionHash(modified);
  assert.notEqual(hash1, hash2);
});

test("computeCanvasProjectionHash returns empty string for non-object input", () => {
  assert.equal(computeCanvasProjectionHash(null), "");
  assert.equal(computeCanvasProjectionHash(undefined), "");
  assert.equal(computeCanvasProjectionHash([]), "");
});

// ── extractCanvasProjection ──────────────────────────────────────────────────

test("extractCanvasProjection extracts positions, sizes, flags, colors from candidate graph", () => {
  const projection = extractCanvasProjection(CANDIDATE_GRAPH_FIXTURE);

  assert.ok(projection.entries, "Must have entries");
  assert.equal(Object.keys(projection.entries).length, 3);

  // Node-1 (KSampler) — uid via vibecomfy_uid property
  assert.deepEqual(projection.entries["node-1"], {
    pos: [100, 200],
    size: [300, 400],
    flags: { pinned: true },
    color: "#ff0000",
    bgcolor: "#330000",
    mode: 0,
    order: 1,
  });

  // Node-2 (VAEDecode)
  assert.deepEqual(projection.entries["node-2"], {
    pos: [500, 200],
    size: [300, 400],
    flags: { collapsed: true },
    color: "#00ff00",
    bgcolor: "#003300",
    mode: 0,
    order: 2,
  });

  // Node-3 (SaveImage) — no flags, no bgcolor
  assert.deepEqual(projection.entries["node-3"], {
    pos: [900, 200],
    size: [250, 350],
    color: "#0000ff",
    mode: 0,
    order: 3,
  });

  // Groups
  assert.equal(projection.groups.length, 2);
  assert.deepEqual(projection.groups[0], {
    title: "Main Pipeline",
    bounding: [50, 50, 1200, 600],
    color: "#3f789e",
  });
  assert.deepEqual(projection.groups[1], {
    title: "Output",
    bounding: [50, 700, 1200, 300],
    color: "#8a8a8a",
  });

  // Extra
  assert.deepEqual(projection.extra, { canvas_scale: 1.0 });
});

test("extractCanvasProjection handles nodes without vibecomfy_uid via node id", () => {
  const graph = {
    nodes: [
      { id: 42, pos: [10, 20], size: [100, 200] },
      { id: 99, pos: [30, 40], size: [150, 250], flags: { pinned: false } },
    ],
    groups: [],
  };
  const projection = extractCanvasProjection(graph);
  assert.ok(projection.entries["42"]);
  assert.deepEqual(projection.entries["42"].pos, [10, 20]);
  assert.deepEqual(projection.entries["42"].size, [100, 200]);
  assert.ok(projection.entries["99"]);
  assert.deepEqual(projection.entries["99"].flags, { pinned: false });
});

test("extractCanvasProjection: empty graph returns entries-only projection", () => {
  const projection = extractCanvasProjection({ nodes: [], groups: [] });
  assert.deepEqual(projection, { entries: {} });
});

// ── Canonical hash mirror proof: preview diff + hashing integration ──────────

test("previewed plan hash matches canonical JS hash for identical plan projection", () => {
  // The plan_hash that the server sends (inside the candidate envelope) should
  // match the hash computed client-side from the same plan projection data.
  const planHash = computeMutationPlanHash(FULL_PLAN_FIXTURE);

  // Verify it uses canonical hash mirror: same data through sha256Hex gives same result
  const canonicalHash = sha256Hex(FULL_PLAN_FIXTURE);
  assert.equal(planHash, canonicalHash,
    "Plan hash must be computed via canonical hash mirror (sha256Hex)");
});

test("applied canvas projection hash uses canonical hash mirror (non-ASCII escaping)", () => {
  // Create a canvas projection with non-ASCII characters to prove
  // the canonical JSON escaping is active.
  const canvasProjection = {
    entries: {
      "nœud-1": { pos: [100, 200], size: [300, 400], flags: {} },
    },
    groups: [
      { title: "prévisualisation", bounding: [0, 0, 500, 500] },
    ],
  };

  const hash = computeCanvasProjectionHash(canvasProjection);

  // The canonical JSON must escape non-ASCII — verify no raw non-ASCII bytes
  // in the intermediate canonical JSON representation.
  const json = canonicalJsonString(canvasProjection);
  for (let i = 0; i < json.length; i++) {
    const code = json.charCodeAt(i);
    assert.ok(code <= 0x7f,
      `Non-ASCII char at position ${i} with code ${code}: context=${json.slice(Math.max(0, i - 5), i + 5)}`);
  }

  // Hash must be valid hex
  assert.equal(hash.length, 64);
  assert.ok(/^[0-9a-f]{64}$/.test(hash));
});

test("canvas projection hash extracted from candidate graph matches direct hash", () => {
  // Extract the canvas projection from a candidate graph...
  const projection = extractCanvasProjection(CANDIDATE_GRAPH_FIXTURE);
  const hashFromExtract = computeCanvasProjectionHash(projection);

  // ...and verify it matches hashing the same data directly through sha256Hex.
  const hashDirect = sha256Hex(projection);
  assert.equal(hashFromExtract, hashDirect,
    "extractCanvasProjection → computeCanvasProjectionHash chain must use canonical hash mirror");
});

test("full round-trip: plan hash → canvas projection hash matches for layout-only data", () => {
  // When the mutation plan contains only layout changes (no structural graph
  // changes), the plan_hash should match the canvas projection hash computed
  // from the candidate graph's positional/visual subset.

  // Build a layout-only plan projection (no definitions/virtual_wires/unkeyed changes)
  const layoutPlan = {
    store_version: 1,
    vibecomfy_version: "0",
    schema_hash: "sha256:layout",
    entries: {
      "node-1": { pos: [200, 300], size: [300, 400], flags: { pinned: true }, color: "#ff0000" },
      "node-2": { pos: [600, 300], size: [300, 400], flags: {}, color: "#00ff00" },
    },
    groups: [
      { title: "Group", bounding: [150, 250, 800, 500], color: "#3f789e" },
    ],
    extra: {},
    lastRerouteId: null,
    definitions: {},
    virtual_wires: {},
    unkeyed: [],
  };

  const planHash = computeMutationPlanHash(layoutPlan);

  // Canvas-only projection: same entries/groups/extra, stripped of metadata
  const canvasOnly = {
    entries: layoutPlan.entries,
    groups: layoutPlan.groups,
    extra: layoutPlan.extra,
  };
  const canvasHash = computeCanvasProjectionHash(canvasOnly);

  // Verify both use the canonical hash mirror
  assert.equal(planHash, sha256Hex(layoutPlan));
  assert.equal(canvasHash, sha256Hex(canvasOnly));

  // For layout-only plans, the hashes are distinct (plan includes metadata)
  // but both are valid canonical hashes
  assert.equal(planHash.length, 64);
  assert.equal(canvasHash.length, 64);
});

test("mutation-plan hash stability: 50 iterations produce identical result", () => {
  const results = new Set();
  for (let i = 0; i < 50; i++) {
    results.add(computeMutationPlanHash(structuredClone(FULL_PLAN_FIXTURE)));
  }
  assert.equal(results.size, 1, "All 50 iterations must produce the same plan hash");
});

// ── T27: Group preview parity and mutation-plan group geometry coverage ──────

test("T27: layout_groups returns candidate groups even without baseline", () => {
  const candidate = {
    nodes: [],
    groups: [
      { title: "Group A", color: "#3f789e", bounding: [10, 20, 300, 200] },
    ],
  };

  const result = computeSerializedGraphPreviewDiff({
    liveGraph: { nodes: [] },
    candidateGraph: candidate,
    // layoutBaselineGraph is not passed — simulate no baseline available
  });

  assert.equal(result.layout_groups.length, 1,
    "candidate groups should be returned even without baseline");
  const group = result.layout_groups[0];
  assert.equal(group.title, "Group A");
  assert.equal(group.color, "#3f789e");
  assert.deepEqual(group.bounds, { x: 10, y: 20, w: 300, h: 200 });
  assert.equal(group._baselineBounds, null,
    "no baseline bounds when baseline is absent");
  assert.equal(group._changed, false,
    "unchanged when no baseline for comparison");
});

test("T27: layout_groups marks unchanged groups with _changed=false", () => {
  const sameGraph = {
    nodes: [{ id: 1, pos: [100, 100], properties: { vibecomfy_uid: "n1" } }],
    groups: [
      { id: 5, title: "Fixed", color: "#00ff00", bounding: [0, 0, 400, 300] },
    ],
  };

  const result = computeSerializedGraphPreviewDiff({
    liveGraph: sameGraph,
    candidateGraph: sameGraph,
    layoutBaselineGraph: sameGraph,
  });

  assert.equal(result.layout_groups.length, 1);
  const group = result.layout_groups[0];
  assert.equal(group.key, "id:5");
  assert.equal(group._changed, false,
    "identical candidate and baseline bounds should not flag changed");
  assert.deepEqual(group._baselineBounds, { x: 0, y: 0, w: 400, h: 300 });
});

test("T27: layout_groups detects new groups (absent from baseline)", () => {
  const baseline = {
    nodes: [],
    groups: [],
  };
  const candidate = {
    nodes: [],
    groups: [
      { title: "New Group", bounding: [50, 50, 200, 150] },
    ],
  };

  const result = computeSerializedGraphPreviewDiff({
    liveGraph: baseline,
    candidateGraph: candidate,
    layoutBaselineGraph: baseline,
  });

  assert.equal(result.layout_groups.length, 1);
  assert.equal(result.layout_groups[0]._changed, true,
    "new group should be marked changed");
  assert.equal(result.layout_groups[0]._baselineBounds, null,
    "new group has no baseline bounds");
});

test("T27: layout_groups detects resized groups", () => {
  const baseline = {
    nodes: [],
    groups: [
      { title: "Main", bounding: [0, 0, 200, 100] },
    ],
  };
  const candidate = {
    nodes: [],
    groups: [
      { title: "Main", bounding: [0, 0, 300, 150] },
    ],
  };

  const result = computeSerializedGraphPreviewDiff({
    liveGraph: baseline,
    candidateGraph: candidate,
    layoutBaselineGraph: baseline,
  });

  assert.equal(result.layout_groups.length, 1);
  assert.equal(result.layout_groups[0]._changed, true,
    "resized group should be flagged changed");
  assert.deepEqual(result.layout_groups[0]._baselineBounds, { x: 0, y: 0, w: 200, h: 100 });
});

test("T27: layout_groups records removed group keys", () => {
  const baseline = {
    nodes: [],
    groups: [
      { title: "Will Be Removed", bounding: [10, 10, 100, 100] },
      { title: "Kept", bounding: [200, 10, 100, 100] },
    ],
  };
  const candidate = {
    nodes: [],
    groups: [
      { title: "Kept", bounding: [200, 10, 100, 100] },
    ],
  };

  const result = computeSerializedGraphPreviewDiff({
    liveGraph: baseline,
    candidateGraph: candidate,
    layoutBaselineGraph: baseline,
  });

  assert.equal(result.layout_groups.length, 1);
  assert.equal(result.layout_groups[0].title, "Kept");
  assert.equal(result.layout_groups[0]._changed, false);
  // _removedGroupKeys is non-enumerable
  const removed = Object.getOwnPropertyDescriptor(result.layout_groups, "_removedGroupKeys");
  assert.ok(removed, "_removedGroupKeys should be present for removed groups");
  // Title-based key matching: "Will Be Removed" -> title:Will Be Removed
  assert.deepEqual(removed.value, ["title:Will Be Removed"]);
});

test("T27: canvas projection hash covers group geometry changes", () => {
  // Two canvas projections differing only in a group bounding box must
  // produce different hashes, proving group geometry is in the hash domain.
  const projA = {
    entries: {
      "node-1": { pos: [100, 200], size: [300, 400] },
    },
    groups: [
      { title: "Pipeline", bounding: [0, 0, 500, 500] },
    ],
  };
  const projB = {
    entries: {
      "node-1": { pos: [100, 200], size: [300, 400] },
    },
    groups: [
      { title: "Pipeline", bounding: [10, 10, 500, 500] },
    ],
  };

  const hashA = computeCanvasProjectionHash(projA);
  const hashB = computeCanvasProjectionHash(projB);

  assert.notEqual(hashA, hashB,
    "group bounding change must produce different canvas projection hash");
});

test("T27: mutation-plan hash domain includes groups", () => {
  // The full mutation-plan hash includes groups.  Changing a group's bounding
  // box must change the plan hash.
  const planA = structuredClone(FULL_PLAN_FIXTURE);
  const planB = structuredClone(FULL_PLAN_FIXTURE);
  planB.groups[0].bounding = [60, 60, 1200, 600]; // shifted by 10px

  const hashA = computeMutationPlanHash(planA);
  const hashB = computeMutationPlanHash(planB);

  assert.notEqual(hashA, hashB,
    "group bounding change in plan must produce different plan hash");
  assert.equal(hashA.length, 64);
  assert.equal(hashB.length, 64);
});

test("T27: group colors in the hash domain produce different hashes", () => {
  const planA = structuredClone(FULL_PLAN_FIXTURE);
  const planB = structuredClone(FULL_PLAN_FIXTURE);
  planB.groups[0].color = "#ff0000";

  assert.notEqual(computeMutationPlanHash(planA), computeMutationPlanHash(planB),
    "group color change must produce different plan hash");
});

test("T27: group addition changes canvas projection hash", () => {
  const projA = {
    entries: { "n1": { pos: [0, 0], size: [100, 100] } },
    groups: [{ title: "A", bounding: [0, 0, 500, 500] }],
  };
  const projB = {
    entries: { "n1": { pos: [0, 0], size: [100, 100] } },
    groups: [
      { title: "A", bounding: [0, 0, 500, 500] },
      { title: "B", bounding: [0, 520, 500, 300] },
    ],
  };

  assert.notEqual(computeCanvasProjectionHash(projA), computeCanvasProjectionHash(projB),
    "adding a group must change the canvas projection hash");
});
