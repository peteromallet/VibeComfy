import test from "node:test";
import assert from "node:assert/strict";
import { Worker } from "node:worker_threads";

const TAB_WORKER_URL = new URL(
  "./helpers/scope_resolver_tab_worker.mjs",
  import.meta.url,
);

function runIsolatedTab(graph) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(TAB_WORKER_URL, { workerData: { graph } });
    worker.once("message", (message) => {
      if (message?.error) {
        reject(new Error(message.error));
        return;
      }
      resolve(message);
    });
    worker.once("error", reject);
    worker.once("exit", (code) => {
      if (code !== 0) {
        reject(new Error(`isolated tab worker exited with code ${code}`));
      }
    });
  });
}

// ── Global mocks ──────────────────────────────────────────────────────────

let _mocksInstalled = false;

function installMocks() {
  if (_mocksInstalled) return;
  _mocksInstalled = true;

  // localStorage fake
  const lsStore = new Map();
  globalThis.localStorage = {
    getItem(key) {
      const val = lsStore.get(String(key));
      return val === undefined ? null : val;
    },
    setItem(key, value) {
      lsStore.set(String(key), String(value));
    },
    removeItem(key) {
      lsStore.delete(String(key));
    },
    _clear() {
      lsStore.clear();
    },
    _dump() {
      return Object.fromEntries(lsStore);
    },
  };

  // sessionStorage fake
  const ssStore = new Map();
  globalThis.sessionStorage = {
    getItem(key) {
      const val = ssStore.get(String(key));
      return val === undefined ? null : val;
    },
    setItem(key, value) {
      ssStore.set(String(key), String(value));
    },
    removeItem(key) {
      ssStore.delete(String(key));
    },
    _clear() {
      ssStore.clear();
    },
    _dump() {
      return Object.fromEntries(ssStore);
    },
  };

  // No crypto.subtle needed — scope_resolver.js uses synchronous FNV-1a hashing.
}

function resetStorage() {
  if (globalThis.localStorage?._clear) globalThis.localStorage._clear();
  if (globalThis.sessionStorage?._clear) globalThis.sessionStorage._clear();
}

// ── Dynamic import ────────────────────────────────────────────────────────

async function loadResolver() {
  installMocks();
  const url = new URL(
    "../../vibecomfy/comfy_nodes/web/scope_resolver.js",
    import.meta.url,
  ).href;
  return await import(`${url}?t=${Date.now()}`);
}

// ── Test graph factories ──────────────────────────────────────────────────

function baseGraph() {
  return {
    nodes: [
      { id: 1, type: "CheckpointLoaderSimple", properties: {}, widgets_values: ["v1-5-pruned.ckpt"] },
      { id: 2, type: "CLIPTextEncode", properties: {}, widgets_values: ["a cat"] },
      { id: 3, type: "EmptyLatentImage", properties: {}, widgets_values: [512, 512, 1] },
      { id: 4, type: "KSampler", properties: {}, widgets_values: [123456789, 20, 7.5, "euler", "normal", 1] },
      { id: 5, type: "VAEDecode", properties: {}, widgets_values: [] },
      { id: 6, type: "SaveImage", properties: {}, widgets_values: ["ComfyUI"] },
    ],
    links: [
      [1, 1, 0, 2, 0, "MODEL"],
      [2, 2, 0, 4, 1, "CONDITIONING"],
      [3, 3, 0, 4, 0, "LATENT"],
      [4, 4, 0, 5, 0, "LATENT"],
      [5, 5, 0, 6, 0, "IMAGE"],
    ],
  };
}

function singleNodeGraph() {
  return {
    nodes: [{ id: 1, type: "SaveImage", properties: {}, widgets_values: ["output"] }],
    links: [],
  };
}

function emptyGraph() {
  return { nodes: [], links: [] };
}

// ── Tests: Fingerprint stability ──────────────────────────────────────────

test("fingerprint is stable for identical graphs", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = baseGraph();

  assert.equal(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint is stable across repeated calls", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const graph = baseGraph();
  const fp1 = computeStructuralGraphFingerprint(graph);
  const fp2 = computeStructuralGraphFingerprint(graph);
  const fp3 = computeStructuralGraphFingerprint(graph);

  assert.equal(fp1, fp2);
  assert.equal(fp2, fp3);
});

test("fingerprint is hex string of correct length", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const fp = computeStructuralGraphFingerprint(baseGraph());
  assert.equal(typeof fp, "string");
  assert.match(fp, /^[0-9a-f]{16}$/);
});

// ── Tests: Widget value churn insensitivity ────────────────────────────────

test("fingerprint is insensitive to node position changes", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[0].pos = [100, 200];
  g2.nodes[1].pos = [500, 800];

  assert.equal(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint is insensitive to node color/boxcolor/bgcolor changes", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[0].color = "#ff0000";
  g2.nodes[0].bgcolor = "#00ff00";
  g2.nodes[0].boxcolor = "#0000ff";

  assert.equal(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint is insensitive to node size changes", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[0].size = [300, 400];
  g2.nodes[1].size = [500, 200];

  assert.equal(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint is insensitive to widget value churn (prompt text change)", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[1].widgets_values = ["a completely different prompt"];

  assert.equal(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint is insensitive to widget value churn (seed change)", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[3].widgets_values = [999999999, 20, 7.5, "euler", "normal", 1];

  assert.equal(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint is insensitive to extra properties on nodes", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[0].properties = { extra: "data", nested: { deep: true } };

  assert.equal(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

// ── Tests: Node ID sensitivity ────────────────────────────────────────────

test("fingerprint changes when node IDs differ", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[0].id = 99;

  assert.notEqual(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint changes when a node is added", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes.push({ id: 7, type: "PreviewImage", properties: {}, widgets_values: [] });

  assert.notEqual(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint changes when a node is removed", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes = g2.nodes.slice(0, 3); // keep only first 3 nodes

  assert.notEqual(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

// ── Tests: Type sensitivity ───────────────────────────────────────────────

test("fingerprint changes when node type changes", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[3].type = "KSamplerAdvanced";

  assert.notEqual(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint changes when node mode changes", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[0].mode = 4; // mute mode

  assert.notEqual(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

// ── Tests: Link topology sensitivity ──────────────────────────────────────

test("fingerprint changes when a link is added", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  // Add a new link: node 1 output 0 → node 5 input 1
  g2.links.push([1, 1, 0, 5, 1, "MODEL"]);

  assert.notEqual(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint changes when a link is removed", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.links = g2.links.slice(0, 3); // remove last two links

  assert.notEqual(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint changes when link source changes", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.links[0] = [1, 1, 0, 3, 0, "MODEL"]; // changed target from 2 to 3

  assert.notEqual(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

test("fingerprint changes when link type changes", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.links[0] = [1, 1, 0, 2, 0, "CLIP"];

  assert.notEqual(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

// ── Tests: Empty graph handling ───────────────────────────────────────────

test("fingerprint handles empty graph (no nodes)", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const fp = computeStructuralGraphFingerprint(emptyGraph());
  assert.equal(typeof fp, "string");
  assert.match(fp, /^[0-9a-f]{16}$/);
});

test("fingerprint handles null/undefined graph gracefully", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  // Should not throw
  const fp1 = computeStructuralGraphFingerprint(null);
  const fp2 = computeStructuralGraphFingerprint(undefined);
  assert.equal(typeof fp1, "string");
  assert.equal(typeof fp2, "string");
  assert.equal(fp1, fp2); // Both null/undefined produce same fingerprint
});

// ── Tests: computeScopeId ─────────────────────────────────────────────────

test("computeScopeId produces valid scope id for non-empty graph", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId } = mod;

  const scopeId = computeScopeId(baseGraph());
  assert.equal(typeof scopeId, "string");
  // Format: <tab-nonce>:<fingerprint>
  assert.match(scopeId, /^[a-z0-9]+-[a-z0-9]+:[0-9a-f]{16}$/);
});

test("computeScopeId returns same scope for same graph in same tab", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId } = mod;

  const g1 = baseGraph();
  const g2 = baseGraph();
  assert.equal(computeScopeId(g1), computeScopeId(g2));
});

test("computeScopeId returns different scope for different graphs in same tab", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId } = mod;

  const g1 = baseGraph();
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  g2.nodes[0].id = 999;

  assert.notEqual(computeScopeId(g1), computeScopeId(g2));
});

test("computeScopeId returns null for empty graph", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId } = mod;

  assert.equal(computeScopeId(emptyGraph()), null);
  assert.equal(computeScopeId({ nodes: [], links: [] }), null);
});

test("computeScopeId uses workflow id to scope empty Comfy workflow tabs", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId } = mod;

  const empty = { nodes: [], links: [] };
  const scopeA = computeScopeId(empty, { workflowId: "workflow-window-a" });
  const scopeB = computeScopeId(empty, { workflowId: "workflow-window-b" });

  assert.equal(typeof scopeA, "string");
  assert.equal(typeof scopeB, "string");
  assert.notEqual(scopeA, scopeB);
  assert.match(scopeA, /^[a-z0-9]+-[a-z0-9]+:workflow-window-a$/);
});

test("computeScopeId separates identical graphs in different Comfy workflow tabs", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId } = mod;

  const graph = baseGraph();
  const scopeA = computeScopeId(graph, { workflowId: "workflow-window-a" });
  const scopeB = computeScopeId(graph, { workflowId: "workflow-window-b" });

  assert.notEqual(scopeA, scopeB);
  assert.notEqual(scopeA, computeScopeId(graph));
});

test("computeScopeId keeps one identified workflow scoped across structural edits", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId, computeStructuralGraphFingerprint } = mod;

  const before = emptyGraph();
  const after = baseGraph();
  const workflowId = "workflow-window-stable";

  assert.notEqual(
    computeStructuralGraphFingerprint(before),
    computeStructuralGraphFingerprint(after),
  );
  assert.equal(
    computeScopeId(before, { workflowId }),
    computeScopeId(after, { workflowId }),
  );
});

// ── Tests: captureInitialScopeId ──────────────────────────────────────────

test("captureInitialScopeId treats structural edits to an identified workflow as the same scope", async () => {
  resetStorage();
  const mod = await loadResolver();
  const workflowId = "workflow-window-stable";

  const before = mod.captureInitialScopeId(emptyGraph(), { workflowId });
  const after = mod.captureInitialScopeId(baseGraph(), { workflowId });

  assert.equal(before.isNew, true);
  assert.equal(after.isNew, false);
  assert.equal(after.scopeId, before.scopeId);
  assert.notEqual(after.fingerprint, before.fingerprint);
});

test("captureInitialScopeId migrates the current fingerprint-qualified session binding", async () => {
  resetStorage();
  const mod = await loadResolver();
  const graph = baseGraph();
  const workflowId = "workflow-window-upgrade";
  const stableScopeId = mod.computeScopeId(graph, { workflowId });
  const fingerprint = mod.computeStructuralGraphFingerprint(graph);
  globalThis.sessionStorage.setItem(
    `vibecomfy_scope_session:${stableScopeId}:${fingerprint}`,
    "session-before-stable-scope",
  );

  mod.captureInitialScopeId(graph, { workflowId });

  assert.equal(
    globalThis.sessionStorage.getItem(`vibecomfy_scope_session:${stableScopeId}`),
    "session-before-stable-scope",
  );
});

test("captureInitialScopeId returns scope info with isNew=true on first call", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { captureInitialScopeId } = mod;

  const result = captureInitialScopeId(baseGraph());
  assert.ok(result);
  assert.equal(typeof result.scopeId, "string");
  assert.equal(typeof result.fingerprint, "string");
  assert.equal(result.isNew, true);
});

test("captureInitialScopeId returns isNew=false on second call with same graph", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { captureInitialScopeId } = mod;

  const graph = baseGraph();
  const r1 = captureInitialScopeId(graph);
  assert.equal(r1.isNew, true);

  const r2 = captureInitialScopeId(graph);
  assert.equal(r2.isNew, false);
  assert.equal(r2.scopeId, r1.scopeId);
  assert.equal(r2.fingerprint, r1.fingerprint);
});

test("captureInitialScopeId returns null for empty graph", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { captureInitialScopeId } = mod;

  assert.equal(captureInitialScopeId(emptyGraph()), null);
  assert.equal(captureInitialScopeId({ nodes: [], links: [] }), null);
});

test("captureInitialScopeId with forceRefresh bypasses cache", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { captureInitialScopeId, computeScopeId } = mod;

  const graph = baseGraph();

  // First call — new scope
  const r1 = captureInitialScopeId(graph);
  assert.equal(r1.isNew, true);

  // Second call — cached
  const r2 = captureInitialScopeId(graph);
  assert.equal(r2.isNew, false);
  assert.equal(r2.scopeId, r1.scopeId);

  // Force refresh — should return isNew=true but same scope id
  const r3 = captureInitialScopeId(graph, { forceRefresh: true });
  assert.equal(r3.isNew, true);
  assert.equal(r3.scopeId, r1.scopeId); // same graph → same scope
  assert.equal(r3.fingerprint, r1.fingerprint);
});

// ── Tests: Graph replacement / workflow-load simulation ────────────────────

test("graph replacement (load new workflow) produces new scope", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { captureInitialScopeId } = mod;

  // Initial workflow
  const g1 = baseGraph();
  const r1 = captureInitialScopeId(g1);
  assert.equal(r1.isNew, true);

  // Load a completely different workflow
  const g2 = {
    nodes: [
      { id: 10, type: "LoadImage", properties: {}, widgets_values: ["input.png"] },
      { id: 20, type: "ImageBlend", properties: {}, widgets_values: [] },
    ],
    links: [[1, 10, 0, 20, 0, "IMAGE"]],
  };
  const r2 = captureInitialScopeId(g2);
  assert.equal(r2.isNew, true);
  assert.notEqual(r2.scopeId, r1.scopeId);

  // Reload the original workflow
  const r3 = captureInitialScopeId(g1);
  assert.equal(r3.isNew, false); // cached from first call
  assert.equal(r3.scopeId, r1.scopeId);
});

test("workflow open simulation: same graph re-opened gets same scope", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { captureInitialScopeId } = mod;

  const graph = baseGraph();

  // Open workflow first time
  const r1 = captureInitialScopeId(graph);
  assert.equal(r1.isNew, true);

  // Simulate re-open (same graph)
  const r2 = captureInitialScopeId(graph);
  assert.equal(r2.isNew, false);
  assert.equal(r2.scopeId, r1.scopeId);
  assert.equal(r2.fingerprint, r1.fingerprint);
});

// ── Tests: Duplicate-tab scope divergence ─────────────────────────────────

test("duplicate-tab: same graph in different tabs gets different scope ids", async () => {
  const graph = baseGraph();
  const [tab1, tab2] = await Promise.all([
    runIsolatedTab(graph),
    runIsolatedTab(graph),
  ]);

  // Real worker realms model browser tabs: each has independent module state
  // and sessionStorage, so the tab nonces and scopes must diverge.
  assert.notEqual(tab1.nonce, tab2.nonce);
  assert.notEqual(tab1.first.scopeId, tab2.first.scopeId);

  // But fingerprints should be the same (same graph structure)
  assert.equal(tab1.first.fingerprint, tab2.first.fingerprint);
});

test("duplicate-tab: each tab maintains independent scope sessions", async () => {
  const graph = baseGraph();
  const [tab1, tab2] = await Promise.all([
    runIsolatedTab(graph),
    runIsolatedTab(graph),
  ]);

  assert.notEqual(tab1.nonce, tab2.nonce);
  assert.notEqual(tab1.first.scopeId, tab2.first.scopeId);

  // Each realm gets a stable scope and session binding on repeated access.
  for (const tab of [tab1, tab2]) {
    assert.equal(tab.first.scopeId, tab.second.scopeId);
    assert.equal(tab.first.isNew, true);
    assert.equal(tab.second.isNew, false);
    assert.equal(tab.sessionId, `session:${tab.nonce}`);
  }
});

test("duplicate-tab: different fingerprints produce different scopes even with tab isolation", async () => {
  // Tab 1 with graph A
  resetStorage();
  const mod1 = await loadResolver();
  const graphA = baseGraph();
  const r1 = mod1.captureInitialScopeId(graphA);
  const fp1 = r1.fingerprint;

  // Same tab with graph B
  const graphB = JSON.parse(JSON.stringify(baseGraph()));
  graphB.nodes[0].id = 777;
  const r2 = mod1.captureInitialScopeId(graphB);
  const fp2 = r2.fingerprint;

  assert.notEqual(fp1, fp2);
  assert.notEqual(r1.scopeId, r2.scopeId);
});

// ── Tests: Single node graph ──────────────────────────────────────────────

test("single node graph produces valid scope", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId, captureInitialScopeId, computeStructuralGraphFingerprint } = mod;

  const graph = singleNodeGraph();
  const scopeId = computeScopeId(graph);
  assert.ok(scopeId);

  const result = captureInitialScopeId(graph);
  assert.ok(result);
  assert.equal(result.isNew, true);
  assert.equal(result.scopeId, scopeId);

  const fp = computeStructuralGraphFingerprint(graph);
  assert.match(fp, /^[0-9a-f]{16}$/);
});

// ── Tests: Fingerprint determinism across serialization ────────────────────

test("fingerprint survives JSON round-trip", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const original = baseGraph();
  const serialized = JSON.stringify(original);
  const deserialized = JSON.parse(serialized);

  assert.equal(
    computeStructuralGraphFingerprint(original),
    computeStructuralGraphFingerprint(deserialized),
  );
});

test("fingerprint is insensitive to object key ordering", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  // Same logical graph, different key order in JSON
  const g1 = {
    nodes: [{ id: 5, type: "VAEDecode" }],
    links: [],
  };
  const g2 = {
    links: [],
    nodes: [{ type: "VAEDecode", id: 5 }],
  };

  assert.equal(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

// ── Tests: Graph with object-form links ───────────────────────────────────

test("fingerprint handles object-form links (not just arrays)", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = baseGraph(); // array-form links
  const g2 = JSON.parse(JSON.stringify(baseGraph()));
  // Convert links to object form
  g2.links = g2.links.map((link) => ({
    id: link[0],
    origin_id: link[1],
    origin_slot: link[2],
    target_id: link[3],
    target_slot: link[4],
    type: link[5],
  }));

  assert.equal(computeStructuralGraphFingerprint(g1), computeStructuralGraphFingerprint(g2));
});

// ── Tests: Node class sensitivity (vibecomfy intent nodes) ─────────────────

test("fingerprint changes when vibecomfy intent node class differs", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeStructuralGraphFingerprint } = mod;

  const g1 = {
    nodes: [{ id: 1, type: "vibecomfy.code", properties: {}, widgets_values: [] }],
    links: [],
  };
  const g2 = {
    nodes: [{ id: 1, type: "vibecomfy.exec", properties: {}, widgets_values: [] }],
    links: [],
  };
  const g3 = {
    nodes: [{ id: 1, type: "vibecomfy.loop", properties: {}, widgets_values: [] }],
    links: [],
  };

  const fp1 = computeStructuralGraphFingerprint(g1);
  const fp2 = computeStructuralGraphFingerprint(g2);
  const fp3 = computeStructuralGraphFingerprint(g3);

  assert.notEqual(fp1, fp2);
  assert.notEqual(fp1, fp3);
  assert.notEqual(fp2, fp3);
});

// ── Tests: scope id format validation ─────────────────────────────────────

test("scopeId contains only safe characters", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId } = mod;

  const scopeId = computeScopeId(baseGraph());
  // Should only contain lowercase hex digits, hyphens, and colons
  assert.match(scopeId, /^[a-z0-9\-:]+$/);
});

test("different single-node graphs produce different scope ids", async () => {
  resetStorage();
  const mod = await loadResolver();
  const { computeScopeId } = mod;

  const g1 = { nodes: [{ id: 1, type: "LoadImage" }], links: [] };
  const g2 = { nodes: [{ id: 1, type: "SaveImage" }], links: [] };
  const g3 = { nodes: [{ id: 2, type: "LoadImage" }], links: [] };

  const s1 = computeScopeId(g1);
  const s2 = computeScopeId(g2);
  const s3 = computeScopeId(g3);

  assert.notEqual(s1, s2); // Different types
  assert.notEqual(s2, s3); // Different IDs
  assert.notEqual(s1, s3); // Different IDs
});
