// intent_graph_receipt_core.test.mjs — C2a receipt-core boundary tests.
//
// Exercises the private intent-graph receipt core factory across the full fence
// matrix: success with a real canonical prepared authority, closed/exact fence
// rejection (missing/extra/mismatched each dimension), epoch independence, forged
// and cross-instance receipts, graph switch, nested-scope-before-acquisition,
// resolver/precondition failure, deep freeze/detachment, no native reference
// leakage, and zero mutation-spy calls.

import test from "node:test";
import assert from "node:assert/strict";

import * as intentGraphReceiptCore from "../../vibecomfy/comfy_nodes/web/_intent_graph_receipt_core.mjs";
const { createIntentGraphReceiptCore } = intentGraphReceiptCore;
import { forwardOperationDigest } from "../../vibecomfy/comfy_nodes/web/prepared_authority_v1.js";
import { makeValidCandidateTransactionV2 } from "./authority_factory.mjs";

// ── Canonical prepared-authority fixture ─────────────────────────────────────

const PREPARED = makeValidCandidateTransactionV2({
  sessionId: "sess-receipt",
  planHash: "plan-receipt",
  state: "prepared",
  deltaOps: [{ op: "set_node_field", target: ["", "node-1", "seed"], value: 12345 }],
}).prepared_authority;

const OPERATION_DIGEST = forwardOperationDigest(PREPARED.operation.ops);
const RESTORATION_DIGEST = PREPARED.restoration_strategy.digest;

// A canonical, valid, externally-minted fence bound to PREPARED.
function baseFence(overrides = {}) {
  return {
    panel_id: "panel-1",
    workflow_id: PREPARED.workflow_id,
    scope: { kind: "root", path: "" },
    scope_contract: "root_scope_v1",
    scope_activation_epoch: 100,
    apply_epoch: 200,
    transaction_id: PREPARED.transaction_id,
    candidate_id: PREPARED.candidate_id,
    plan_hash: PREPARED.plan_hash,
    operation_digest: OPERATION_DIGEST,
    restoration_digest: RESTORATION_DIGEST,
    lease_nonce: PREPARED.lease_nonce,
    generation: PREPARED.generation,
    ...overrides,
  };
}

// A graph carrying a mutation spy. The core must leave `mutationCount` at 0.
function makeGraph(id = "graph-1") {
  const graph = { __id: id, nodes: [], links: [] };
  graph.mutationCount = 0;
  for (const name of [
    "addNode", "removeNode", "setNodeField", "setMode", "addLink", "removeLink",
    "configure", "serialize", "deserialize", "repaint",
  ]) {
    graph[name] = () => { graph.mutationCount += 1; };
  }
  return graph;
}

// Build a fresh core + dependency harness. Each callback records what the core
// exercised so tests can assert on it (e.g. acquireGraph never called for
// nested-scope rejection, mutationCount stays 0, etc.).
function makeHarness({ graph = makeGraph(), liveFence = baseFence(), precondition = { structural_hash: "a".repeat(64), revision: 7 }, resolver } = {}) {
  const calls = { readFence: 0, acquireGraph: 0, capturePrecondition: 0, resolveNativeBindings: 0 };
  const privateState = { __private: true, lease: "lease-private" };
  const detachedEvidence = {
    bindings_contract: "native_bindings_v1",
    intended_primitive_count: 1,
    descriptor: { sealed: true },
  };
  const deps = {
    readFence() {
      calls.readFence += 1;
      return liveFence;
    },
    acquireGraph(_app) {
      calls.acquireGraph += 1;
      return graph;
    },
    capturePrecondition(_graph, _authority, _plan) {
      calls.capturePrecondition += 1;
      return precondition;
    },
    resolveNativeBindings(_args) {
      calls.resolveNativeBindings += 1;
      return resolver ? resolver() : { privateState, detachedEvidence };
    },
  };
  const core = createIntentGraphReceiptCore({ __app: true }, deps);
  return { core, deps, calls, graph, liveFence, privateState, detachedEvidence };
}

// Reject if value is or contains any live object reference.
function assertNoLiveReferences(value, live, label, seen = new WeakSet()) {
  if (value === null || typeof value !== "object") return;
  if (value === live) {
    assert.fail(`${label} leaked a live object reference`);
  }
  if (seen.has(value)) return;
  seen.add(value);
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) assertNoLiveReferences(value[i], live, `${label}[${i}]`, seen);
  } else {
    for (const key of Object.keys(value)) assertNoLiveReferences(value[key], live, `${label}.${key}`, seen);
  }
}

// ── Positive path ────────────────────────────────────────────────────────────

test("preflight succeeds with a real valid prepared authority and asserts current", () => {
  const { core, calls, graph, privateState } = makeHarness();
  const fence = baseFence();
  const { receipt, evidence } = core.preflightPrepared(PREPARED, fence);

  assert.equal(receipt.contract_version, "intent_graph_receipt_core_v1");
  assert.ok(Object.isFrozen(receipt));
  assert.ok(Object.isFrozen(evidence));
  assert.deepEqual(evidence.authority_receipt.transaction_id, PREPARED.transaction_id);
  assert.deepEqual(evidence.fence.transaction_id, fence.transaction_id);
  assert.deepEqual(evidence.native.intended_primitive_count, 1);

  // Every callback exercised exactly once; no graph mutation.
  assert.equal(calls.acquireGraph, 1);
  assert.equal(calls.capturePrecondition, 1);
  assert.equal(calls.resolveNativeBindings, 1);
  assert.equal(graph.mutationCount, 0);

  // Fence-current on the same instance succeeds.
  const current = core.assertFenceCurrent(receipt);
  assert.ok(Object.isFrozen(current.evidence));
  assert.deepEqual(current.evidence.fence.transaction_id, fence.transaction_id);
  assert.equal(graph.mutationCount, 0);

  // privateState never leaks through either evidence path.
  assertNoLiveReferences(evidence, privateState, "evidence");
  assertNoLiveReferences(current.evidence, privateState, "current.evidence");
});

// ── Closed/exact fence: missing keys ─────────────────────────────────────────

test("rejects each missing fence key", () => {
  for (const key of Object.keys(baseFence())) {
    const { core } = makeHarness();
    const fence = baseFence();
    delete fence[key];
    assert.throws(
      () => core.preflightPrepared(PREPARED, fence),
      (err) => err.code === "missing_fence_key" && err.detail.key === key,
      `expected missing_fence_key for ${key}`,
    );
  }
});

// ── Closed/exact fence: extra/unknown keys ───────────────────────────────────

test("rejects unknown/extra fence keys", () => {
  for (const extra of ["extra_field", "candidate_graph_hash", "whole_graph"]) {
    const { core } = makeHarness();
    const fence = baseFence({ [extra]: "x" });
    assert.throws(
      () => core.preflightPrepared(PREPARED, fence),
      (err) => err.code === "unknown_fence_key" && err.detail.key === extra,
      `expected unknown_fence_key for ${extra}`,
    );
  }
});

// ── Authority-bound dimension mismatches ─────────────────────────────────────

test("rejects each mismatched authority-bound fence dimension", () => {
  const boundOverrides = {
    workflow_id: "00000000-0000-0000-0000-000000000000",
    scope: { kind: "root", path: " " },
    transaction_id: "tx-other",
    candidate_id: "candidate-other",
    plan_hash: "plan-other",
    lease_nonce: "lease-other",
    generation: 999,
    operation_digest: "0".repeat(64),
    restoration_digest: "1".repeat(64),
  };
  for (const [key, value] of Object.entries(boundOverrides)) {
    const { core } = makeHarness();
    const fence = baseFence({ [key]: value });
    assert.throws(
      () => core.preflightPrepared(PREPARED, fence),
      key === "scope"
        ? (err) => err.code === "nested_scope"
        : (err) => err.code === "fence_dimension_mismatch" && err.detail.key === key,
      `expected ${key === "scope" ? "nested_scope" : "fence_dimension_mismatch"} for ${key}`,
    );
  }
});

// ── Live fence mismatch on every dimension ───────────────────────────────────

test("rejects each mismatched live-fence dimension", () => {
  // apply_epoch and scope_activation_epoch are externally-only (no authority
  // binding), so they reach the live-fence comparison and fail there.
  const liveOverrides = {
    panel_id: "panel-other",
    scope_contract: "other_contract",
    scope_activation_epoch: 999,
    apply_epoch: 888,
    workflow_id: "00000000-0000-0000-0000-000000000000",
    transaction_id: "tx-other",
    candidate_id: "candidate-other",
    plan_hash: "plan-other",
    lease_nonce: "lease-other",
    generation: 7,
    operation_digest: "0".repeat(64),
    restoration_digest: "1".repeat(64),
  };
  for (const [key, value] of Object.entries(liveOverrides)) {
    const liveFence = baseFence({ [key]: value });
    const { core } = makeHarness({ liveFence });
    const fence = baseFence();
    assert.throws(
      () => core.preflightPrepared(PREPARED, fence),
      (err) => err.code === "live_fence_mismatch" && err.detail.key === key,
      `expected live_fence_mismatch for ${key}`,
    );
  }
});

// ── Epoch independence ───────────────────────────────────────────────────────

test("apply_epoch and scope_activation_epoch are independent and may differ from each other", () => {
  // They carry distinct values, both matching the live fence — success.
  const liveFence = baseFence({ scope_activation_epoch: 100, apply_epoch: 200 });
  const { core } = makeHarness({ liveFence });
  const fence = baseFence({ scope_activation_epoch: 100, apply_epoch: 200 });
  const { receipt } = core.preflightPrepared(PREPARED, fence);
  assert.ok(receipt);
});

// ── Forged receipt ───────────────────────────────────────────────────────────

test("assertFenceCurrent rejects a forged receipt", () => {
  const { core } = makeHarness();
  assert.throws(
    () => core.assertFenceCurrent({ contract_version: "intent_graph_receipt_core_v1" }),
    (err) => err.code === "forged_receipt",
  );
  assert.throws(
    () => core.assertFenceCurrent(null),
    (err) => err.code === "forged_receipt",
  );
});

// ── Cross-instance receipt ───────────────────────────────────────────────────

test("assertFenceCurrent rejects a receipt minted by another instance", () => {
  const harnessA = makeHarness();
  const harnessB = makeHarness();
  const { receipt } = harnessA.core.preflightPrepared(PREPARED, baseFence());
  assert.throws(
    () => harnessB.core.assertFenceCurrent(receipt),
    (err) => err.code === "forged_receipt",
  );
});

// ── Graph switch ─────────────────────────────────────────────────────────────

test("assertFenceCurrent rejects when the live graph reference has switched", () => {
  let primary = makeGraph("g-primary");
  let switched = makeGraph("g-switched");
  let useSwitched = false;
  const calls = { readFence: 0, acquireGraph: 0, capturePrecondition: 0, resolveNativeBindings: 0 };
  const deps = {
    readFence() { calls.readFence += 1; return baseFence(); },
    acquireGraph() { calls.acquireGraph += 1; return useSwitched ? switched : primary; },
    capturePrecondition() { calls.capturePrecondition += 1; return { structural_hash: "a".repeat(64), revision: 1 }; },
    resolveNativeBindings() { calls.resolveNativeBindings += 1; return { privateState: { p: 1 }, detachedEvidence: { ok: true } }; },
  };
  const core = createIntentGraphReceiptCore({ app: true }, deps);
  const { receipt } = core.preflightPrepared(PREPARED, baseFence());
  useSwitched = true;
  assert.throws(
    () => core.assertFenceCurrent(receipt),
    (err) => err.code === "graph_switched",
  );
});

// ── Nested scope rejected before acquisition ─────────────────────────────────

test("rejects nested scope before graph acquisition", () => {
  const { core, calls } = makeHarness();
  const fence = baseFence({ scope: { kind: "nested", path: "child" } });
  assert.throws(
    () => core.preflightPrepared(PREPARED, fence),
    (err) => err.code === "nested_scope",
  );
  // acquireGraph must NOT have run: nested scope dies at fence-shape validation.
  assert.equal(calls.acquireGraph, 0);
});

// ── Precondition failure (live / cyclic evidence) ────────────────────────────

test("rejects non-detachable precondition evidence (live object, cyclic)", () => {
  // Live object (the graph itself) — not plain-detachable.
  const graph = makeGraph();
  const liveObj = graph;
  {
    const { core } = makeHarness({ graph, precondition: liveObj });
    assert.throws(
      () => core.preflightPrepared(PREPARED, baseFence()),
      (err) => err.code === "live_object_in_evidence",
    );
  }
  // Cyclic evidence.
  const cyclic = { a: 1 };
  cyclic.self = cyclic;
  {
    const { core } = makeHarness({ precondition: cyclic });
    assert.throws(
      () => core.preflightPrepared(PREPARED, baseFence()),
      (err) => err.code === "cyclic_evidence",
    );
  }
});

// ── Resolver failure ─────────────────────────────────────────────────────────

test("rejects malformed resolver output", () => {
  // Missing detachedEvidence.
  {
    const { core } = makeHarness({ resolver: () => ({ privateState: { p: 1 } }) });
    assert.throws(
      () => core.preflightPrepared(PREPARED, baseFence()),
      (err) => err.code === "invalid_resolver_output",
    );
  }
  // privateState === detachedEvidence (not distinct).
  {
    const shared = { x: 1 };
    const { core } = makeHarness({ resolver: () => ({ privateState: shared, detachedEvidence: shared }) });
    assert.throws(
      () => core.preflightPrepared(PREPARED, baseFence()),
      (err) => err.code === "invalid_resolver_output",
    );
  }
  // detachedEvidence is a live (non-detachable) object.
  {
    const graph = makeGraph();
    const { core } = makeHarness({ graph, resolver: () => ({ privateState: { p: 1 }, detachedEvidence: graph }) });
    assert.throws(
      () => core.preflightPrepared(PREPARED, baseFence()),
      (err) => err.code === "live_object_in_evidence",
    );
  }
});

// ── Deep freeze / detachment ─────────────────────────────────────────────────

test("returned evidence is deeply frozen and detached from source", () => {
  const sourcePrecondition = { structural_hash: "a".repeat(64), nested: { revision: 3 } };
  const sourceEvidence = { bindings: [{ k: 1 }] };
  const { core } = makeHarness({
    precondition: sourcePrecondition,
    resolver: () => ({ privateState: { p: 1 }, detachedEvidence: sourceEvidence }),
  });
  const { evidence } = core.preflightPrepared(PREPARED, baseFence());

  function assertDeeplyFrozen(value, seen = new WeakSet()) {
    if (value === null || typeof value !== "object") return;
    assert.ok(Object.isFrozen(value), "expected frozen");
    if (seen.has(value)) return;
    seen.add(value);
    if (Array.isArray(value)) {
      for (let i = 0; i < value.length; i += 1) assertDeeplyFrozen(value[i], seen);
    } else {
      for (const key of Object.keys(value)) assertDeeplyFrozen(value[key], seen);
    }
  }
  assertDeeplyFrozen(evidence);

  // Mutating the source after preflight must NOT affect the returned evidence.
  sourcePrecondition.nested.revision = 999;
  sourceEvidence.bindings.push({ k: 2 });
  assert.equal(evidence.precondition.nested.revision, 3);
  assert.equal(evidence.native.bindings.length, 1);

  // Writes into the frozen evidence are rejected.
  assert.throws(() => { evidence.fence.transaction_id = "x"; }, TypeError);
  assert.throws(() => { evidence.precondition.nested.revision = 1; }, TypeError);
});

// ── No native reference leakage ──────────────────────────────────────────────

test("returned evidence leaks no graph, privateState, or live-fence reference", () => {
  const graph = makeGraph();
  const liveFence = baseFence();
  const privateState = { secret: "p" };
  const { core } = makeHarness({
    graph,
    liveFence,
    resolver: () => ({ privateState, detachedEvidence: { ok: true } }),
  });
  const fence = baseFence();
  const { evidence } = core.preflightPrepared(PREPARED, fence);

  assertNoLiveReferences(evidence, graph, "evidence");
  assertNoLiveReferences(evidence, privateState, "evidence");
  assertNoLiveReferences(evidence, liveFence, "evidence");
  // The externally-minted fence object itself must not be retained verbatim.
  assert.notEqual(evidence.fence, fence);
});

// ── Zero mutation-spy calls ──────────────────────────────────────────────────

test("the core never invokes a graph mutation primitive", () => {
  const graph = makeGraph();
  const { core } = makeHarness({ graph });
  const { receipt } = core.preflightPrepared(PREPARED, baseFence());
  core.assertFenceCurrent(receipt);
  core.assertFenceCurrent(receipt);
  assert.equal(graph.mutationCount, 0, "core must perform zero native writes");
});

// ── Missing dependency is rejected at factory time ───────────────────────────

test("factory rejects missing or non-function dependencies", () => {
  assert.throws(
    () => createIntentGraphReceiptCore({}, { readFence: () => ({}), acquireGraph: () => ({}), capturePrecondition: () => ({}) }),
    (err) => err.code === "missing_dependency" && err.detail.name === "resolveNativeBindings",
  );
});

// ── Group 1: wrong-type fence values + wrong-type preflight inputs ────────────
//
// Table-driven: every one of the 13 closed fence dimensions is fed a clearly
// invalid type/value.  Additionally, the two preflightPrepared positional
// inputs (preparedAuthority, externallyMintedFence) are fed wrong-type values.
// Every case must produce a typed diagnostic AND must not reach graph
// acquisition, native resolution, or any mutation — the contract promises
// pre-acquisition rejection.

test("wrong-type fence values and preflight inputs reject before acquisition", () => {
  const wrongTypeTable = [
    // ── 13 closed fence dimensions ──
    { label: "panel_id",              override: { panel_id: 123 },                expectedCode: "invalid_fence_field", detailKey: "panel_id" },
    { label: "workflow_id",           override: { workflow_id: 42 },              expectedCode: "invalid_fence_field", detailKey: "workflow_id" },
    { label: "scope (non-object)",    override: { scope: "root" },                expectedCode: "nested_scope",        detailKey: "scope" },
    { label: "scope_contract",        override: { scope_contract: 99 },           expectedCode: "invalid_fence_field", detailKey: "scope_contract" },
    { label: "scope_activation_epoch",override: { scope_activation_epoch: "100" },expectedCode: "invalid_fence_field", detailKey: "scope_activation_epoch" },
    { label: "apply_epoch",           override: { apply_epoch: -1 },              expectedCode: "invalid_fence_field", detailKey: "apply_epoch" },
    { label: "transaction_id",        override: { transaction_id: true },         expectedCode: "invalid_fence_field", detailKey: "transaction_id" },
    { label: "candidate_id",          override: { candidate_id: [] },             expectedCode: "invalid_fence_field", detailKey: "candidate_id" },
    { label: "plan_hash",             override: { plan_hash: {} },                expectedCode: "invalid_fence_field", detailKey: "plan_hash" },
    { label: "operation_digest",      override: { operation_digest: "not-a-hex" },expectedCode: "invalid_fence_field", detailKey: "operation_digest" },
    { label: "restoration_digest",    override: { restoration_digest: 999 },      expectedCode: "invalid_fence_field", detailKey: "restoration_digest" },
    { label: "lease_nonce",           override: { lease_nonce: 456 },             expectedCode: "invalid_fence_field", detailKey: "lease_nonce" },
    { label: "generation",            override: { generation: "999" },            expectedCode: "invalid_fence_field", detailKey: "generation" },
  ];

  for (const { label, override, expectedCode, detailKey } of wrongTypeTable) {
    const { core, calls, graph } = makeHarness();
    const fence = baseFence(override);
    assert.throws(
      () => core.preflightPrepared(PREPARED, fence),
      (err) => {
        if (err.code !== expectedCode) return false;
        if (detailKey && err.detail?.key !== detailKey) return false;
        return true;
      },
      `[${label}] expected ${expectedCode}${detailKey ? ` with key ${detailKey}` : ""}`,
    );
    // Pre-acquisition rejection: acquireGraph, resolveNativeBindings must NOT run.
    assert.equal(calls.acquireGraph, 0, `[${label}] acquireGraph must be 0`);
    assert.equal(calls.resolveNativeBindings, 0, `[${label}] resolveNativeBindings must be 0`);
    assert.equal(graph.mutationCount, 0, `[${label}] mutationCount must be 0`);
  }
});

test("wrong-type preparedAuthority and externallyMintedFence reject before acquisition", () => {
  const preflightInputTable = [
    { label: "preparedAuthority null",   authority: null,       fence: baseFence(), expectedCode: "invalid_authority" },
    { label: "preparedAuthority number", authority: 42,         fence: baseFence(), expectedCode: "invalid_authority" },
    { label: "preparedAuthority string", authority: "bad",      fence: baseFence(), expectedCode: "invalid_authority" },
    { label: "externallyMintedFence null",   authority: PREPARED, fence: null,       expectedCode: "invalid_fence_shape" },
    { label: "externallyMintedFence number", authority: PREPARED, fence: 123,        expectedCode: "invalid_fence_shape" },
    { label: "externallyMintedFence array",  authority: PREPARED, fence: [],         expectedCode: "invalid_fence_shape" },
  ];

  for (const { label, authority, fence, expectedCode } of preflightInputTable) {
    const { core, calls, graph } = makeHarness();
    assert.throws(
      () => core.preflightPrepared(authority, fence),
      (err) => err.code === expectedCode,
      `[${label}] expected ${expectedCode}`,
    );
    assert.equal(calls.acquireGraph, 0, `[${label}] acquireGraph must be 0`);
    assert.equal(calls.resolveNativeBindings, 0, `[${label}] resolveNativeBindings must be 0`);
    assert.equal(graph.mutationCount, 0, `[${label}] mutationCount must be 0`);
  }
});

// ── Group 2: temporal stale-after-mint coverage for every fence dimension ─────
//
// For each of the 13 independent fence dimensions: mint a receipt successfully
// with a valid live fence, then alter exactly that one live-fence dimension to
// another shape-valid value (plausible but different), then assert that
// assertFenceCurrent rejects with live_fence_mismatch naming that key and does
// not mutate the graph.
//
// For scope the contract only permits { kind: "root", path: "" } as a valid
// root_scope_v1 value per assertRootScopeV1.  The stale scope used here
// ({ kind: "root", path: "/other" }) is a different kind:"root" value that
// exercises the live_fence_mismatch path for the scope dimension; it is not
// itself a valid root_scope_v1, but assertFenceCurrent does not re-validate
// scope shape — it only compares equality against the stored fence.

test("stale live-fence dimension after mint rejects with live_fence_mismatch per key", () => {
  const staleTable = [
    { key: "panel_id",               staleValue: "panel-stale" },
    { key: "workflow_id",            staleValue: "00000000-0000-0000-0000-000000000001" },
    // scope: use a different root-kind value; see doc comment above.
    { key: "scope",                  staleValue: { kind: "root", path: "/other" } },
    { key: "scope_contract",         staleValue: "root_scope_v1_stale" },
    { key: "scope_activation_epoch", staleValue: 101 },
    { key: "apply_epoch",            staleValue: 201 },
    { key: "transaction_id",         staleValue: "tx-plan-receipt-stale" },
    { key: "candidate_id",           staleValue: "candidate-plan-receipt-stale" },
    { key: "plan_hash",              staleValue: "plan-receipt-stale" },
    { key: "operation_digest",       staleValue: "0".repeat(64) },
    { key: "restoration_digest",     staleValue: "1".repeat(64) },
    { key: "lease_nonce",            staleValue: "plan-receipt-lease-stale" },
    { key: "generation",             staleValue: 999 },
  ];

  for (const { key, staleValue } of staleTable) {
    // Fresh harness: live fence matches the externally-minted fence exactly.
    const { core, graph, liveFence } = makeHarness();
    const fence = baseFence();
    const { receipt } = core.preflightPrepared(PREPARED, fence);

    // Alter exactly this one dimension on the live fence.
    liveFence[key] = staleValue;
    // (graph.mutationCount already verified at 0 by the positive-path test.)

    assert.throws(
      () => core.assertFenceCurrent(receipt),
      (err) => err.code === "live_fence_mismatch" && err.detail?.key === key,
      `[${key}] expected live_fence_mismatch`,
    );

    // assertFenceCurrent must perform zero native writes.
    assert.equal(graph.mutationCount, 0, `[${key}] mutationCount must be 0`);
  }
});

// ── Module namespace export assertion ─────────────────────────────────────────

test("module namespace exports exactly createIntentGraphReceiptCore", () => {
  assert.deepEqual(Object.keys(intentGraphReceiptCore).sort(), ["createIntentGraphReceiptCore"]);
});
