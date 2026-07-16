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
