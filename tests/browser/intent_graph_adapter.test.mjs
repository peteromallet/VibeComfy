import test from "node:test";
import assert from "node:assert/strict";

import {
  INTENT_GRAPH_ADAPTER_V1,
  createIntentGraphAdapter,
} from "../../vibecomfy/comfy_nodes/web/intent_graph_adapter.js";

function makeGraph(overrides) {
  const base = {
    nodes: [
      {
        id: 1,
        type: "A",
        mode: 0,
        vibecomfy_uid: "uid-a",
        fields: {},
        widgets_values: [],
        inputs: [],
        outputs: [{ name: "OUT", links: [1] }],
      },
      {
        id: 2,
        type: "B",
        mode: 0,
        vibecomfy_uid: "uid-b",
        fields: {},
        widgets_values: [],
        inputs: [{ name: "IN", link: 1 }],
        outputs: [],
      },
    ],
    links: [[1, 1, 0, 2, 0, "VALUE"]],
  };
  const data = Object.assign({}, base, overrides || {});
  return {
    _nodes: [
      { live: true, id: 1 },
      { live: true, id: 2 },
    ],
    serialize() {
      return JSON.parse(JSON.stringify(data));
    },
    changeCalls: 0,
    change() {
      this.changeCalls += 1;
    },
    setDirtyCanvasCalls: 0,
    setDirtyCanvas(a, b) {
      this.setDirtyCanvasCalls += 1;
      this._dirtyArgs = [a, b];
    },
    drawCalls: 0,
  };
}

function makeCanvas(graph, overrides) {
  return Object.assign({
    graph,
    setDirtyCalls: 0,
    setDirty(a, b) {
      this.setDirtyCalls += 1;
      this._dirtyArgs = [a, b];
    },
    drawCalls: 0,
    draw(a, b) {
      this.drawCalls += 1;
      this._drawArgs = [a, b];
    },
  }, overrides || {});
}

function makeApp(graph, canvasOverrides) {
  const graphValue = graph === null ? null : (graph === undefined ? makeGraph() : graph);
  const canvas = makeCanvas(graphValue, canvasOverrides);
  return { canvas, graph: graphValue };
}

test("module contract version is exported and frozen", () => {
  assert.equal(INTENT_GRAPH_ADAPTER_V1, "intent_graph_adapter_v1");
});

test("importing and constructing the factory does not require browser globals", () => {
 const savedWindow = globalThis.window;
  const savedDocument = globalThis.document;
  delete globalThis.window;
  delete globalThis.document;
  try {
    const adapter = createIntentGraphAdapter(undefined);
    assert.equal(typeof adapter.capture, "function");
    const caps = adapter.capabilities();
    assert.equal(caps.ok, false);
    assert.equal(caps.diagnostic.code, "missing_live_graph");
  } finally {
    if (savedWindow !== undefined) globalThis.window = savedWindow;
    if (savedDocument !== undefined) globalThis.document = savedDocument;
  }
});

test("factory returns a frozen object that does not expose the live graph", () => {
  const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  assert.ok(Object.isFrozen(adapter));
  assert.equal(adapter.graph, undefined);
  const keys = Object.keys(adapter).sort();
  assert.deepEqual(keys, [
    "capabilities",
    "capture",
    "captureDrawSnapshot",
    "captureNormalized",
    "captureRevision",
    "contract_version",
    "enumerateNodes",
    "notifyRevision",
    "project",
    "projectionReference",
    "repaint",
  ]);
});

test("missing live graph is typed missing_live_graph", () => {
  const adapter = createIntentGraphAdapter({ canvas: {} });
  const result = adapter.capture();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "missing_live_graph");
  assert.equal(result.contract_version, INTENT_GRAPH_ADAPTER_V1);
  assert.equal(result.operation, "capture");
});

test("ambiguous distinct live graphs is typed ambiguous_live_graph", () => {
  const g1 = makeGraph();
  const g2 = makeGraph();
  const adapter = createIntentGraphAdapter({ canvas: { graph: g1 }, graph: g2 });
  const result = adapter.capture();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "ambiguous_live_graph");
});

test("identical graph references are deduplicated", () => {
  const graph = makeGraph();
  const adapter = createIntentGraphAdapter({ canvas: { graph }, graph });
  const result = adapter.capture();
  assert.equal(result.ok, true);
});

test("unknown scope contract fails before serialize", () => {
  const serializeCalls = { count: 0 };
  const graph = makeGraph();
  graph.serialize = function () {
    serializeCalls.count += 1;
    return { nodes: [] };
  };
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.capture({ scope_contract: "future_scope_v2" });
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "unsupported_scope");
  assert.equal(serializeCalls.count, 0);
});

test("unknown adapter contract fails before serialize", () => {
  const serializeCalls = { count: 0 };
  const graph = makeGraph();
  graph.serialize = function () {
    serializeCalls.count += 1;
    return { nodes: [] };
  };
  const adapter = createIntentGraphAdapter(makeApp(graph));
  const result = adapter.capture({ adapter_contract: "future_adapter_v2" });
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "unsupported_contract");
  assert.equal(serializeCalls.count, 0);
});

for (const [field, value, code] of [
  ["adapter_contract", null, "unsupported_contract"],
  ["adapter_contract", "", "unsupported_contract"],
  ["scope_contract", null, "unsupported_scope"],
  ["scope_contract", "", "unsupported_scope"],
  ["scope", null, "unsupported_scope"],
]) {
  test(`explicit ${field}=${JSON.stringify(value)} fails before serialize`, () => {
    const graph = makeGraph();
    let serializeCalls = 0;
    graph.serialize = () => {
      serializeCalls += 1;
      return { nodes: [] };
    };
    const result = createIntentGraphAdapter(makeApp(graph)).capture({ [field]: value });
    assert.equal(result.ok, false);
    assert.equal(result.diagnostic.code, code);
    assert.equal(serializeCalls, 0);
  });
}

test("non-root nested scope fails before serialize", () => {
  const serializeCalls = { count: 0 };
  const graph = makeGraph();
  graph.serialize = function () {
    serializeCalls.count += 1;
    return { nodes: [] };
  };
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const nestedScope = Object.freeze({ kind: "node", path: "uid-a" });
  const result = adapter.capture({ scope: nestedScope });
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "unsupported_scope");
  assert.equal(serializeCalls.count, 0);
});

test("capture is deeply frozen", () => {
  const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.capture();
  assert.equal(result.ok, true);
  assert.ok(Object.isFrozen(result));
  assert.ok(Object.isFrozen(result.data));
  assert.ok(Object.isFrozen(result.data.graph));
  assert.ok(Object.isFrozen(result.data.graph.nodes));
  assert.ok(Object.isFrozen(result.data.graph.nodes[0]));
  assert.ok(Object.isFrozen(result.data.graph.links));
});

test("capture is plain data and never exposes live graph objects", () => {
  const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.capture();
  const proto = Object.getPrototypeOf(result.data.graph);
  assert.equal(proto, Object.prototype);
});

test("capture clones; later mutation of serialize output does not affect envelope", () => {
  const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.capture();
  const before = JSON.stringify(result.data.graph.nodes);
  app.canvas.graph._nodes.push({ live: true, id: 3 });
  app.canvas.graph.serialize = () => ({ nodes: [{ id: 99 }] });
  const after = JSON.stringify(result.data.graph.nodes);
  assert.equal(after, before);
});

test("enumerateNodes returns frozen plain nodes and not live node objects", () => {
  const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.enumerateNodes();
  assert.equal(result.ok, true);
  assert.equal(result.operation, "enumerate_nodes");
  assert.ok(Object.isFrozen(result.data));
  assert.ok(Object.isFrozen(result.data.nodes));
  assert.ok(Object.isFrozen(result.data.nodes[0]));
  assert.equal(result.data.nodes.length, 2);
  const live = app.canvas.graph._nodes[0];
  assert.notEqual(result.data.nodes[0], live);
  assert.equal(result.data.nodes[0].vibecomfy_uid, "uid-a");
});

test("serialize throw is typed serialization_failed", () => {
  const graph = makeGraph();
  graph.serialize = function () {
    throw new Error("boom");
  };
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.capture();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "serialization_failed");
  assert.ok(!result.diagnostic.stack);
});

test("cyclic serialization output fails closed", () => {
  const graph = makeGraph();
  graph.serialize = function () {
    const cyclic = { nodes: [] };
    cyclic.self = cyclic;
    return cyclic;
  };
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.capture();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "serialization_failed");
});

test("diagnostic message and detail are bounded to 512 chars and have no stack", () => {
  const graph = makeGraph();
  const long = "x".repeat(5000);
  graph.serialize = function () {
    const err = new Error(long);
    err.detail = long;
    throw err;
  };
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.capture();
  assert.equal(result.ok, false);
  assert.ok(result.diagnostic.message.length <= 512);
  assert.ok(result.diagnostic.detail.length <= 512);
  assert.equal(result.diagnostic.stack, undefined);
});

test("capabilities reflect available primitives without leaking graph", () => {
 const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  const caps = adapter.capabilities();
  assert.equal(caps.ok, true);
  assert.equal(caps.data.serialize, true);
  assert.equal(caps.data.enumerate, true);
  assert.equal(caps.data.legacy_whole_graph_replace, false);
  assert.equal(caps.data.graph_apply.available, false);
  assert.equal(caps.data.delta_apply.available, false);
  assert.equal(caps.data.layout_apply.available, false);
  assert.equal(caps.data.revision, true);
  assert.equal(caps.data.dirty, true);
  assert.equal(caps.data.draw, true);
  assert.equal(caps.data.graph, undefined);
});

test("capabilities fail closed when graph is missing", () => {
  const adapter = createIntentGraphAdapter({ canvas: {} });
  const caps = adapter.capabilities();
  assert.equal(caps.ok, false);
  assert.equal(caps.diagnostic.code, "missing_live_graph");
});

test("notifyRevision calls change exactly once", () => {
  const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.notifyRevision();
  assert.equal(result.ok, true);
  assert.equal(result.operation, "notify_revision");
  assert.equal(app.canvas.graph.changeCalls, 1);
});

test("captureRevision returns a typed string without serializing", () => {
  const graph = makeGraph();
  let serializeCalls = 0;
  graph.serialize = () => {
    serializeCalls += 1;
    return { nodes: [] };
  };
  graph.getRevision = () => 42;
  const result = createIntentGraphAdapter(makeApp(graph)).captureRevision();
  assert.equal(result.ok, true);
  assert.equal(result.operation, "capture_revision");
  assert.equal(result.data.revision, "42");
  assert.equal(serializeCalls, 0);
});

test("captureRevision returns null when no native revision token exists", () => {
  const result = createIntentGraphAdapter(makeApp()).captureRevision();
  assert.equal(result.ok, true);
  assert.equal(result.data.revision, null);
});

test("notifyRevision without change primitive is revision_unavailable", () => {
  const graph = makeGraph();
  delete graph.change;
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.notifyRevision();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "revision_unavailable");
});

test("notifyRevision throwing is revision_failed", () => {
  const graph = makeGraph();
  graph.change = function () {
    throw new Error("nope");
  };
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.notifyRevision();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "revision_failed");
});

test("repaint prefers graph.setDirtyCanvas then canvas.draw once", () => {
  const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.repaint();
  assert.equal(result.ok, true);
  assert.equal(result.operation, "repaint");
  assert.equal(app.canvas.graph.setDirtyCanvasCalls, 1);
  assert.deepEqual(app.canvas.graph._dirtyArgs, [true, true]);
  assert.equal(app.canvas.setDirtyCalls, 0);
  assert.equal(app.canvas.drawCalls, 1);
  assert.deepEqual(app.canvas._drawArgs, [true, true]);
});

test("repaint falls back to canvas.setDirty when graph dirty is absent", () => {
  const graph = makeGraph();
  delete graph.setDirtyCanvas;
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.repaint();
  assert.equal(result.ok, true);
  assert.equal(app.canvas.setDirtyCalls, 1);
  assert.deepEqual(app.canvas._dirtyArgs, [true, true]);
  assert.equal(app.canvas.drawCalls, 1);
});

test("repaint is repaint_unavailable when no dirty or draw primitives exist", () => {
  const graph = makeGraph();
  delete graph.setDirtyCanvas;
  const app = makeApp(graph, { setDirty: undefined, draw: undefined });
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.repaint();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "repaint_unavailable");
});

test("repaint throw is repaint_failed", () => {
  const graph = makeGraph();
  graph.setDirtyCanvas = function () {
    throw new Error("dirty broke");
  };
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.repaint();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "repaint_failed");
});

test("project delegates to projectGraphV1 with frozen result", () => {
  const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  const projection = "structural_v1";
  const result = adapter.project(projection);
  assert.equal(result.ok, true);
  assert.ok(Object.isFrozen(result));
  assert.ok(Object.isFrozen(result.data));
  assert.equal(result.data.projection, "structural_v1");
  assert.equal(result.data.projected.projection, "structural_v1");
  assert.ok(Array.isArray(result.data.projected.nodes));
});

test("projectionReference delegates to projectionReferenceV1", () => {
  const app = makeApp();
  const adapter = createIntentGraphAdapter(app);
  const projection = "structural_v1";
  const result = adapter.projectionReference(projection);
  assert.equal(result.ok, true);
  assert.ok(Object.isFrozen(result.data));
  assert.equal(result.data.reference.kind, "projection_ref_v1");
  assert.equal(result.data.reference.projection, "structural_v1");
  assert.match(result.data.reference.digest, /^[0-9a-f]{64}$/);
});

test("unknown projection preserves its typed code and serializes zero times", () => {
  const graph = makeGraph();
  let serializeCalls = 0;
  graph.serialize = () => {
    serializeCalls += 1;
    return { nodes: [] };
  };
  const app = makeApp(graph);
  const adapter = createIntentGraphAdapter(app);
  const result = adapter.project("unsupported_kind");
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "unknown_projection_version");
  assert.equal(serializeCalls, 0);
});

test("forbidden projection preserves its typed code and serializes zero times", () => {
  const graph = makeGraph();
  let serializeCalls = 0;
  graph.serialize = () => {
    serializeCalls += 1;
    return { nodes: [] };
  };
  const result = createIntentGraphAdapter(makeApp(graph)).project("workflow_v1");
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "forbidden_projection");
  assert.equal(serializeCalls, 0);
});

test("projection preserves missing_identity instead of flattening it", () => {
  const graph = makeGraph({
    nodes: [{ id: 1, type: "A", mode: 0, fields: {}, inputs: [], outputs: [] }],
    links: [],
  });
  const result = createIntentGraphAdapter(makeApp(graph)).project("structural_v1");
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "missing_identity");
});

// ---------------------------------------------------------------------------
// Slice 3 focused cases: detached normalized capture, draw snapshot identity
// refusal matrix, and the exact eb45e dynamic-exec incident fixture.
// ---------------------------------------------------------------------------

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const eb45ePath = path.join(repoRoot, "tests", "fixtures", "agent_edit", "eb45e_dynamic_exec_v1.json");
const eb45eFixture = JSON.parse(readFileSync(eb45ePath, "utf8"));

// Build a live-graph shim whose serialize() returns a captured plain graph, so
// the adapter exercises the real capture boundary without touching live nodes.
function liveAppFromGraph(plainGraph) {
  const store = JSON.parse(JSON.stringify(plainGraph));
  const graph = {
    serialize() { return JSON.parse(JSON.stringify(store)); },
  };
  return { canvas: { graph }, graph };
}

test("eb45e fixture is reconstructed from the real incident, not a reduced graph", () => {
  assert.equal(eb45eFixture.contract, "eb45e_dynamic_exec_v1");
  assert.equal(eb45eFixture.provenance.session_id, "eb45e0ef50e146c6985417bf1449e96a");
  assert.deepEqual(eb45eFixture.provenance.source_files, [
    "original.ui.json",
    "candidate.ui.json",
    "messages.jsonl",
    "response.json",
    "narrative_context.json",
    "narrative_validation.json",
  ]);
  assert.ok(eb45eFixture.original.nodes.length >= 90, "original graph must be the full incident graph");
  assert.ok(eb45eFixture.candidate.nodes.length >= 90, "candidate graph must be the full incident graph");
  assert.equal(eb45eFixture.candidate.nodes.length, eb45eFixture.original.nodes.length + 1);
});

test("eb45e fixture provenance pins all four required source SHA-256 digests", () => {
  // The four required digests over the raw bytes of original, candidate,
  // messages, and response at acceptance. These pin the exact incident
  // artifacts the fixture was reconstructed from; any drift must be caught.
  const digests = eb45eFixture.provenance.source_digests;
  assert.ok(digests && typeof digests === "object");
  assert.deepEqual(Object.keys(digests).sort(), [
    "candidate.ui.json",
    "messages.jsonl",
    "original.ui.json",
    "response.json",
  ]);
  assert.equal(digests["original.ui.json"], "829fe306efb90413e2d5adbef60713dece62b1819f2bdca2a6f56a7f8c88926c");
  assert.equal(digests["candidate.ui.json"], "710c79865b320dc53f3e2824cd8df0f725382fc943170d0b1240cbcd06854e80");
  assert.equal(digests["messages.jsonl"], "982ef57b4cefb455cd899a17976a8af3273d6de70bd51e2d44d0a883242f68c3");
  assert.equal(digests["response.json"], "8830157f2c7ff14b1954500eb989734ce971a957dd2fe5dc9b1763c3ce0349e4");
  assert.equal(eb45eFixture.provenance.digest_algorithm, "sha256");
  assert.equal(eb45eFixture.provenance.digest_scope, "full source file bytes");
});

test("eb45e fixture embeds the small response outcome envelope without the 567KB body", () => {
  // response.json is ~567KB; only the decision-relevant outcome slice is
  // embedded. The full body is referenced by provenance.source_digests.
  const outcome = eb45eFixture.response_outcome;
  assert.ok(outcome && typeof outcome === "object");
  assert.equal(outcome.session_id, "eb45e0ef50e146c6985417bf1449e96a");
  assert.equal(outcome.turn_id, "0001");
  assert.equal(outcome.ok, true);
  assert.equal(outcome.route, "revise");
  assert.equal(outcome.contract_version, "agent_edit_turn_v2");
  assert.equal(outcome.agent_edit_protocol, "v2_delta");
  assert.ok(outcome.outcome && typeof outcome.outcome === "object");
  assert.equal(outcome.outcome.kind, "candidate");
  assert.ok(Array.isArray(outcome.outcome.changes));
  assert.ok(outcome.outcome.changes.some((change) => change.field_path === "images"));
  // The fixture must NOT embed the heavyweight response fields.
  assert.equal(eb45eFixture.response, undefined);
  assert.equal(eb45eFixture.response_body, undefined);
  assert.equal(eb45eFixture.full_response, undefined);
});

test("captureNormalized byte-preserves the full 98-node eb45e candidate graph detached and leaves the fixture unchanged", () => {
  // Deep-compare the entire detached captured graph (all nodes, links, groups,
  // and opaque top-level fields such as config/extra/id/last_link_id/last_node_id
  // /revision/version) against the full fixture candidate. This replaces an
  // earlier 3-node/2-link incident slice that could not prove whole-graph
  // fidelity and could not distinguish a faithful capture from one that
  // silently dropped opaque fields.
  const candidate = eb45eFixture.candidate;
  assert.equal(candidate.nodes.length, 98, "fixture candidate must carry the full 98-node incident graph");
  assert.equal(candidate.links.length, 77);
  assert.equal(candidate.groups.length, 17);

  const fixtureSnapshot = JSON.stringify(candidate);
  const adapter = createIntentGraphAdapter(liveAppFromGraph(candidate));
  const result = adapter.captureNormalized();
  assert.equal(result.ok, true, result.diagnostic?.detail);
  assert.equal(result.operation, "capture_normalized");

  // Minimal contract/version evidence tag only: no semantic exec descriptors,
  // no live_writes self-attestation, no native ids.
  assert.ok(Object.isFrozen(result.data.normalization));
  assert.equal(result.data.normalization.contract, "native_normalization_v1");
  assert.deepEqual(
    Object.keys(result.data.normalization).sort(),
    ["contract", "evidence"],
  );

  // The entire detached captured graph deep-compares to the fixture candidate,
  // including every node, link, group, and opaque top-level field. No field is
  // silently dropped or rewritten.
  assert.deepEqual(result.data.graph, candidate);

  // Detached evidence must not expose the live graph shim and is deeply frozen.
  assert.equal(result.data.graph.serialize, undefined);
  assert.ok(Object.isFrozen(result.data.graph));
  assert.ok(Object.isFrozen(result.data.graph.nodes));
  assert.ok(Object.isFrozen(result.data.graph.links));
  assert.ok(Object.isFrozen(result.data.graph.groups));

  // The fixture input is unchanged by the capture: no write reached it.
  assert.equal(JSON.stringify(candidate), fixtureSnapshot);
});

test("capture rejects an unknown native normalization contract before serializing", () => {
  let serializeCalls = 0;
  const graph = makeGraph();
  graph.serialize = () => { serializeCalls += 1; return { nodes: [] }; };
  const result = createIntentGraphAdapter(makeApp(graph))
    .capture({ native_normalization: "future_normalization_v2" });
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "unsupported_normalization");
  assert.equal(serializeCalls, 0);
});

test("repeated normalized capture is idempotent and leaves the live store unchanged", () => {
  // The adapter does not derive semantic exec descriptors; the normalized
  // capture is the complete detached graph plus a frozen minimal evidence tag.
  // Repeated capture over the same live store must be byte-identical and must
  // not mutate the store.
  const captured = {
    nodes: [
      { id: 1, type: "A", properties: { vibecomfy_uid: "uid-1" }, inputs: [], outputs: [] },
      {
        id: 2,
        type: "vibecomfy.exec",
        properties: { vibecomfy_uid: "uid-2" },
        widgets_values: ["src"],
        inputs: [],
        outputs: [],
      },
    ],
    links: [],
  };
  const storeBefore = JSON.stringify(captured);
  const adapter = createIntentGraphAdapter(liveAppFromGraph(captured));
  const first = adapter.captureNormalized();
  const second = adapter.captureNormalized();
  assert.equal(first.ok, true);
  assert.deepEqual(first.data.normalization, second.data.normalization);
  assert.deepEqual(first.data.graph, second.data.graph);
  // The live store backing the shim is untouched: S3 capture performs no write.
  assert.equal(JSON.stringify(captured), storeBefore);
});

test("captureDrawSnapshot refuses with missing_identity rather than silently omitting unstamped nodes/groups", () => {
  const captured = {
    nodes: [
      { id: 1, type: "A", properties: { vibecomfy_uid: "uid-a" }, pos: [10, 20], size: [100, 50], title: "A", color: "#fff" },
      { id: 2, type: "B", pos: [0, 0] }, // unstamped -> must trigger missing_identity
    ],
    groups: [
      { vibecomfy_group_id: "g1", bounding: [0, 0, 10, 10], title: "G1" },
      { title: "NoId" }, // unstamped -> must trigger missing_identity
    ],
    links: [],
  };
  const result = createIntentGraphAdapter(liveAppFromGraph(captured)).captureDrawSnapshot();
  assert.equal(result.ok, false);
  assert.equal(result.operation, "capture_draw_snapshot");
  assert.equal(result.diagnostic.code, "missing_identity");
  assert.match(result.diagnostic.detail, /1 node/);
  assert.match(result.diagnostic.detail, /1 group/);
});

test("captureDrawSnapshot returns frozen plain geometry keyed by stable UID when every node/group is stamped", () => {
  const captured = {
    nodes: [
      { id: 1, type: "A", properties: { vibecomfy_uid: "uid-a" }, pos: [10, 20], size: [100, 50], title: "A", color: "#fff" },
      { id: 2, type: "B", properties: { vibecomfy_uid: "uid-b" }, pos: [0, 0] },
    ],
    groups: [
      { vibecomfy_group_id: "g1", bounding: [0, 0, 10, 10], title: "G1" },
    ],
    links: [],
  };
  const result = createIntentGraphAdapter(liveAppFromGraph(captured)).captureDrawSnapshot();
  assert.equal(result.ok, true);
  assert.ok(Object.isFrozen(result.data.snapshot));
  assert.equal(result.data.snapshot.nodes.length, 2);
  assert.equal(result.data.snapshot.nodes[0].uid, "uid-a");
  assert.deepEqual(result.data.snapshot.nodes[0].pos, [10, 20]);
  assert.equal(result.data.snapshot.groups.length, 1);
  assert.equal(result.data.snapshot.groups[0].id, "g1");
});

test("captureDrawSnapshot keeps duplicate group titles with distinct IDs valid", () => {
  // Two groups sharing a title but carrying distinct stable ids remain valid;
  // identity is the stable id, not the human-readable title.
  const captured = {
    nodes: [
      { id: 1, type: "A", properties: { vibecomfy_uid: "uid-a" }, pos: [0, 0] },
    ],
    groups: [
      { vibecomfy_group_id: "g1", bounding: [0, 0, 1, 1], title: "Same" },
      { vibecomfy_group_id: "g2", bounding: [0, 0, 1, 1], title: "Same" },
    ],
    links: [],
  };
  const result = createIntentGraphAdapter(liveAppFromGraph(captured)).captureDrawSnapshot();
  assert.equal(result.ok, true);
  assert.equal(result.data.snapshot.groups.length, 2);
  assert.equal(result.data.snapshot.groups[0].title, "Same");
  assert.equal(result.data.snapshot.groups[1].title, "Same");
  assert.notEqual(result.data.snapshot.groups[0].id, result.data.snapshot.groups[1].id);
});

test("captureDrawSnapshot reports ambiguous_identity for duplicate node stable UIDs", () => {
  const captured = {
    nodes: [
      { id: 1, type: "A", properties: { vibecomfy_uid: "dup" }, pos: [0, 0] },
      { id: 2, type: "B", properties: { vibecomfy_uid: "dup" }, pos: [1, 1] },
    ],
    groups: [],
    links: [],
  };
  const result = createIntentGraphAdapter(liveAppFromGraph(captured)).captureDrawSnapshot();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "ambiguous_identity");
  assert.ok(result.diagnostic.detail.includes("dup"));
});

test("captureDrawSnapshot reports ambiguous_identity for duplicate group stable IDs", () => {
  const captured = {
    nodes: [
      { id: 1, type: "A", properties: { vibecomfy_uid: "uid-a" }, pos: [0, 0] },
    ],
    groups: [
      { vibecomfy_group_id: "dup", title: "G1" },
      { id: "dup", title: "G2" },
    ],
    links: [],
  };
  const result = createIntentGraphAdapter(liveAppFromGraph(captured)).captureDrawSnapshot();
  assert.equal(result.ok, false);
  assert.equal(result.diagnostic.code, "ambiguous_identity");
  assert.ok(result.diagnostic.detail.includes("dup"));
});

test("the seven reclassified mutation rows are classified as S4, not S3", () => {
  const ledger = JSON.parse(readFileSync(
    path.join(repoRoot, "tests", "fixtures", "agent_edit", "native_authority_ledger_v1.json"),
    "utf8",
  ));
  const reclassified = ["NGA-048", "NGA-050", "NGA-062", "NGA-067", "NGA-070", "NGA-072", "NGA-078"];
  for (const id of reclassified) {
    const row = ledger.rows.find((entry) => entry.id === id);
    assert.ok(row, `${id} must exist`);
    assert.equal(row.slice, "S4", `${id} must be reclassified to S4 (mutation/harness), not S3`);
    assert.equal(row.semantic_owner, "vibecomfy_roundtrip");
    assert.equal(row.support_status, "migration_debt");
    assert.ok(row.purpose.startsWith("S4 "), `${id} purpose must declare the S4 mutation reason`);
    // They must not be advertised as S3 native normalization.
    assert.notEqual(row.target_api, "nativeNormalization");
    assert.notEqual(row.target_api, "nativeNormalization.rebuildSockets");
    assert.notEqual(row.target_api, "nativeNormalization.widgets");
    assert.notEqual(row.target_api, "enumerateLinks");
  }
});
