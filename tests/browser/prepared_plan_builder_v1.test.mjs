// prepared_plan_builder_v1.test.mjs — C1 zero-native-call proof for the private
// pure plan builder (§6.3, §6.6 step 11, §7.2).
//
// For every §4 fail-closed row relevant to C1 plus the positive cases, this
// test calls buildPreparedPlan(preparedAuthority) and asserts:
//   - every externally-owned harness sentinel count is EXACTLY zero (read from
//     the harness, never from the builder return value);
//   - the builder return value carries ONLY {ok, plan|diagnostic} — no
//     sentinelCounts / proof counters (Gate #4);
//   - positive cases yield a deeply-frozen plan derived solely from the
//     prepared authority, with the already-bound restoration/compensation
//     digests re-validated by recomputation (never generated, never executed);
//   - negative cases yield {ok:false, diagnostic:{code}} with the exact §4 code
//     and all sentinels still zero.

import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { buildPreparedPlan } from "../../vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs";
import { sha256Hex, canonicalizeContractNumeric } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";
import { computeLayoutOperationDigest } from "../../vibecomfy/comfy_nodes/web/layout_operation_v1.js";
import { computeMutationMaterializationDigest } from "../../vibecomfy/comfy_nodes/web/mutation_materialization_v1.js";
import { createSentinelGraph } from "./harness.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const corpus = JSON.parse(
  await readFile(path.join(root, "tests/fixtures/agent_edit/m1_projection_golden_v1.json"), "utf8"),
);

const UUID = "123e4567-e89b-12d3-a456-426614174000";
const ref = (projection) => ({ kind: "projection_ref_v1", projection, digest: "a".repeat(64) });

// ── Authority construction helpers (mirror m1_contracts parity suite) ─────────

function _baselineRefRestoration() {
  const refTag = "original.ui.json";
  return {
    contract_version: "baseline_snapshot_v1",
    digest: sha256Hex({ contract_version: "baseline_snapshot_v1", ref: refTag }),
    ref: refTag,
  };
}

function _addNodeIndices(ops) {
  const out = [];
  for (let i = 0; i < ops.length; i += 1) if (ops[i] && ops[i].op === "add_node") out.push(i);
  return out;
}

function _materializationEnvelope(accompanyingOps) {
  const addIdx = _addNodeIndices(accompanyingOps);
  if (addIdx.length === 0) return null;
  const entries = addIdx.map((i) => ({ source_op_index: i, kind: "add_node" }));
  const mat = { contract_version: "mutation_materialization_v1", wire_version: "1.0.0", entries };
  mat.digest = computeMutationMaterializationDigest(entries, accompanyingOps);
  return mat;
}

function _inverseDeltaRestoration(inverseOps) {
  const payload = { ops: inverseOps };
  const mat = _materializationEnvelope(inverseOps);
  if (mat) {
    payload.mutation_materialization = mat;
    payload.mutation_materialization_digest = mat.digest;
  }
  const normalizedPayload = canonicalizeContractNumeric(payload, {
    finiteErrorCode: "non_finite_materialization",
  });
  const digestVal = sha256Hex({ contract_version: "inverse_delta_v1", payload: normalizedPayload });
  return { contract_version: "inverse_delta_v1", digest: digestVal, payload };
}

function _compensationEnvelope(auth, { digestOverride = null } = {}) {
  const fence = {
    transaction_id: auth.transaction_id,
    candidate_id: auth.candidate_id,
    plan_hash: auth.plan_hash,
    lease_nonce: auth.lease_nonce,
    generation: auth.generation,
    pre_projection_digest: auth.precondition.digest,
    post_projection_digest: auth.postcondition.digest,
  };
  const normalizedFence = canonicalizeContractNumeric(fence, {
    finiteErrorCode: "non_finite_materialization",
  });
  let digestVal = sha256Hex({
    contract_version: "baseline_snapshot_v1",
    wire_version: "1.0.0",
    ref: "compensation.json",
    fence: normalizedFence,
  });
  if (digestOverride !== null) digestVal = digestOverride;
  return {
    contract_version: "baseline_snapshot_v1",
    wire_version: "1.0.0",
    ref: "compensation.json",
    fence,
    digest: digestVal,
  };
}

function makeAuthority({
  family = "structural",
  ops = null,
  layoutOps = null,
  restoration = null,
  compensation = null,
  structuralWitnessMismatch = false,
} = {}) {
  const projection = family === "layout" ? "layout_v1" : "structural_v1";
  let operation;
  if (family === "layout") {
    const lops = layoutOps ?? [{ op: "set_node_geometry", uid: "node-1", pos: [10, 20] }];
    const layoutEnv = { contract_version: "layout_operation_v1", wire_version: "1.0.0", ops: lops };
    layoutEnv.digest = computeLayoutOperationDigest(lops);
    operation = {
      delta_contract: "delta_v1",
      wire_version: "2.0.0",
      ops: [],
      layout_operation: layoutEnv,
      layout_operation_digest: layoutEnv.digest,
    };
  } else {
    const useOps = ops ?? corpus.delta_ops;
    operation = { delta_contract: "delta_v1", wire_version: "2.0.0", ops: useOps };
    const mat = _materializationEnvelope(useOps);
    if (mat) {
      operation.mutation_materialization = mat;
      operation.mutation_materialization_digest = mat.digest;
    }
  }
  const value = {
    contract_version: "prepared_authority_v1",
    transaction_id: "tx-1",
    candidate_id: "candidate-1",
    workflow_id: UUID,
    scope: { kind: "root", path: "" },
    session_id: "session-1",
    turn_id: "turn-1",
    operation,
    operation_family: family,
    precondition: ref(projection),
    postcondition: ref(projection),
    rollback_projection: projection,
    restoration_strategy: restoration ?? _baselineRefRestoration(),
    plan_hash: "plan-1",
    generation: 1,
    lease_nonce: "nonce-1",
    authority_receipt_contract_version: "authority_receipt_v2",
    authority_receipt_delta_schema: "2.0.0",
    authority_receipt_digest: "d".repeat(64),
  };
  if (family === "layout") {
    const pre = "c".repeat(64);
    const post = structuralWitnessMismatch ? "e".repeat(64) : pre;
    value.structural_witness = { ...ref("structural_v1"), precondition_digest: pre, postcondition_digest: post };
  }
  if (compensation) value.restoration_strategy_compensation = compensation;
  return value;
}

// ── Test harness: every case resets + reads the EXTERNAL sentinel counters ──

function runCase(authority) {
  const sentinel = createSentinelGraph();
  sentinel.reset();
  const result = buildPreparedPlan(authority);
  const counts = sentinel.snapshot();
  return { result, counts };
}

function assertAllSentinelsZero(counts) {
  for (const [key, value] of Object.entries(counts)) {
    assert.equal(value, 0, `native sentinel "${key}" must remain zero (got ${value})`);
  }
}

function assertNoSelfAttestation(result) {
  assert.equal(Object.prototype.hasOwnProperty.call(result, "sentinelCounts"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(result, "nativeCounts"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(result, "proof"), false);
  if (result.ok && result.plan) {
    assert.equal(Object.prototype.hasOwnProperty.call(result.plan, "sentinelCounts"), false);
  }
}

function assertDeepFrozen(value, label = "plan") {
  const visit = (v) => {
    if (v === null || typeof v !== "object") return;
    assert.equal(Object.isFrozen(v), true, `${label} must be deeply frozen`);
    if (Array.isArray(v)) {
      for (const item of v) visit(item);
    } else {
      for (const k of Object.keys(v)) visit(v[k]);
    }
  };
  visit(value);
}

// ── Positive cases ───────────────────────────────────────────────────────────

test("structural prepared authority with add_node builds a frozen zero-native plan", () => {
  const authority = makeAuthority();
  const { result, counts } = runCase(authority);

  assertAllSentinelsZero(counts);
  assertNoSelfAttestation(result);

  assert.equal(result.ok, true);
  assert.equal(result.plan.contract_version, "prepared_plan_v1");
  assertDeepFrozen(result.plan);

  // Intended primitives are derived solely from the authority's operation.ops.
  assert.equal(result.plan.operation_family, "structural");
  const expectedKinds = corpus.delta_ops.map((op) => op.op);
  const actualKinds = result.plan.intended_primitives.map((p) => p.kind);
  assert.deepEqual(actualKinds, expectedKinds);

  // The add_node primitive binds the matching materialization entry's index.
  const addIdx = corpus.delta_ops.findIndex((op) => op.op === "add_node");
  const addPrimitive = result.plan.intended_primitives[addIdx];
  assert.equal(addPrimitive.kind, "add_node");
  assert.equal(addPrimitive.uid, corpus.delta_ops[addIdx].uid);
  assert.equal(addPrimitive.node_id, corpus.delta_ops[addIdx].node_id);
  assert.equal(addPrimitive.materialization_entry.source_op_index, addIdx);

  // Restoration digest re-derived by recomputation and bound.
  assert.equal(result.plan.restoration.contract_version, "baseline_snapshot_v1");
  assert.equal(result.plan.restoration.bound, true);
  assert.equal(
    result.plan.restoration.recomputed_digest,
    authority.restoration_strategy.digest,
  );

  // Compensation absent.
  assert.equal(result.plan.compensation.present, false);
});

test("structural authority without add_node builds a plan with no materialization binding", () => {
  const ops = [
    { op: "set_node_field", target: ["", "n1", "f"], value: 2 },
    { op: "set_mode", target: ["", "n1"], mode: 4 },
    { op: "upsert_link", from: ["", "a", "out"], to: ["", "b", "in"] },
    { op: "remove_link", to: ["", "b", "in"] },
    { op: "remove_node", target: ["", "old"] },
  ];
  const authority = makeAuthority({ ops });
  const { result, counts } = runCase(authority);

  assertAllSentinelsZero(counts);
  assert.equal(result.ok, true);
  assertDeepFrozen(result.plan);
  assert.deepEqual(
    result.plan.intended_primitives.map((p) => p.kind),
    ["set_node_field", "set_mode", "upsert_link", "remove_link", "remove_node"],
  );
  // remove_node primitive carries the stable target uid, never a native id.
  assert.equal(result.plan.intended_primitives[4].target_uid, "old");
});

test("layout prepared authority builds a frozen zero-native plan over layout ops", () => {
  const layoutOps = [
    { op: "set_node_geometry", uid: "n1", pos: [1, 2] },
    { op: "add_group", id: "g1", bounding: [0, 0, 100, 100], title: "G", color: "#abc" },
    { op: "remove_group", id: "g2" },
  ];
  const authority = makeAuthority({ family: "layout", layoutOps });
  const { result, counts } = runCase(authority);

  assertAllSentinelsZero(counts);
  assertNoSelfAttestation(result);
  assert.equal(result.ok, true);
  assertDeepFrozen(result.plan);
  assert.equal(result.plan.operation_family, "layout");
  assert.deepEqual(
    result.plan.intended_primitives.map((p) => p.kind),
    ["set_node_geometry", "add_group", "remove_group"],
  );
  assert.equal(result.plan.intended_primitives[1].id, "g1");
});

test("inverse_delta_v1 payload restoration is re-validated (correct inverse)", () => {
  const forwardOps = [{ op: "set_node_field", target: ["", "n1", "f"], value: 2 }];
  const inverseOps = [{ op: "set_node_field", target: ["", "n1", "f"], value: 1 }];
  const authority = makeAuthority({ ops: forwardOps, restoration: _inverseDeltaRestoration(inverseOps) });
  const { result, counts } = runCase(authority);

  assertAllSentinelsZero(counts);
  assert.equal(result.ok, true);
  assert.equal(result.plan.restoration.contract_version, "inverse_delta_v1");
  assert.equal(result.plan.restoration.bound, true);
});

test("remove_node forward with add_node inverse + inverse materialization re-validates", () => {
  const forwardOps = [{ op: "remove_node", target: ["", "old"] }];
  const inverseOps = [
    { op: "add_node", scope_path: "", uid: "old", node_id: "5", class_type: "T", fields: {}, inputs: {} },
  ];
  const authority = makeAuthority({ ops: forwardOps, restoration: _inverseDeltaRestoration(inverseOps) });
  const { result, counts } = runCase(authority);

  assertAllSentinelsZero(counts);
  assert.equal(result.ok, true);
  assert.equal(result.plan.restoration.contract_version, "inverse_delta_v1");
  assert.equal(result.plan.restoration.bound, true);
});

test("optional compensation slot is re-validated by recomputation when present", () => {
  const authority = makeAuthority();
  authority.restoration_strategy_compensation = _compensationEnvelope(authority);
  const { result, counts } = runCase(authority);

  assertAllSentinelsZero(counts);
  assertNoSelfAttestation(result);
  assert.equal(result.ok, true);
  assert.equal(result.plan.compensation.present, true);
  assert.equal(result.plan.compensation.contract_version, "baseline_snapshot_v1");
  assert.equal(result.plan.compensation.bound, true);
});

test("plan is derived solely from prepared authority and independent of later mutation", () => {
  const authority = makeAuthority();
  const { result } = runCase(authority);
  assert.equal(result.ok, true);
  const planSnapshot = JSON.stringify(result.plan);

  // Mutate the input authority after the plan is built; the frozen plan must
  // be unaffected (deep freeze + derivation from a clone).
  authority.plan_hash = "mutated";
  authority.operation.ops = [];
  assert.equal(JSON.stringify(result.plan), planSnapshot);
  assert.equal(result.plan.authority_receipt.plan_hash, "plan-1");
});

test("the builder never trips a sentinel even when one is globally installed", () => {
  // Install the sentinel graph as the global app/LiteGraph surface so that an
  // impure builder reaching for a native primitive would trip.  The pure
  // builder takes prepared authority only and never touches it.
  const sentinel = createSentinelGraph();
  const prevApp = globalThis.app;
  const prevLiteGraph = globalThis.LiteGraph;
  globalThis.app = sentinel.app;
  globalThis.LiteGraph = sentinel.LiteGraph;
  try {
    sentinel.reset();
    const result = buildPreparedPlan(makeAuthority());
    assert.equal(result.ok, true);
    sentinel.assertAllZero("builder must not reach the globally installed sentinel");
    assertNoSelfAttestation(result);
  } finally {
    if (prevApp === undefined) delete globalThis.app;
    else globalThis.app = prevApp;
    if (prevLiteGraph === undefined) delete globalThis.LiteGraph;
    else globalThis.LiteGraph = prevLiteGraph;
  }
});

// ── Fail-closed rows (§4) — every code asserted, every sentinel still zero ───

function assertFail(authority, expectedCode) {
  const { result, counts } = runCase(authority);
  assertAllSentinelsZero(counts);
  assert.equal(result.ok, false);
  assert.equal(Object.prototype.hasOwnProperty.call(result, "plan"), false);
  assert.equal(result.diagnostic.code, expectedCode);
  assertNoSelfAttestation(result);
  return result;
}

test("unknown authority version fails closed", () => {
  const authority = makeAuthority();
  authority.contract_version = "prepared_authority_v9";
  assertFail(authority, "unknown_authority_version");
});

test("layout family with non-empty structural ops fails closed", () => {
  const layoutEnv = {
    contract_version: "layout_operation_v1",
    wire_version: "1.0.0",
    ops: [{ op: "set_node_geometry", uid: "n1", pos: [1, 2] }],
  };
  layoutEnv.digest = computeLayoutOperationDigest(layoutEnv.ops);
  const authority = makeAuthority({ family: "layout", layoutOps: [{ op: "set_node_geometry", uid: "n1", pos: [1, 2] }] });
  // Inject a non-empty structural op to trip the family rule.
  authority.operation.ops = [{ op: "set_node_field", target: ["", "n1", "f"], value: 1 }];
  assertFail(authority, "layout_family_requires_empty_structural_ops");
});

test("layout family missing layout_operation fails closed", () => {
  const authority = makeAuthority({ family: "layout" });
  delete authority.operation.layout_operation;
  delete authority.operation.layout_operation_digest;
  assertFail(authority, "missing_layout_operation");
});

test("structural family with add_node missing materialization fails closed", () => {
  const authority = makeAuthority();
  delete authority.operation.mutation_materialization;
  delete authority.operation.mutation_materialization_digest;
  assertFail(authority, "missing_materialization");
});

test("structural family without add_node carrying materialization fails closed", () => {
  const ops = [{ op: "set_node_field", target: ["", "n1", "f"], value: 2 }];
  const authority = makeAuthority({ ops });
  const mat = _materializationEnvelope([{ op: "add_node", scope_path: "", uid: "x", node_id: "1", class_type: "T", fields: {}, inputs: {} }]);
  authority.operation.mutation_materialization = mat;
  authority.operation.mutation_materialization_digest = mat.digest;
  assertFail(authority, "unexpected_materialization");
});

test("structural family carrying layout_operation fails closed", () => {
  const authority = makeAuthority();
  const layoutEnv = {
    contract_version: "layout_operation_v1",
    wire_version: "1.0.0",
    ops: [{ op: "set_node_geometry", uid: "n1", pos: [1, 2] }],
  };
  layoutEnv.digest = computeLayoutOperationDigest(layoutEnv.ops);
  authority.operation.layout_operation = layoutEnv;
  authority.operation.layout_operation_digest = layoutEnv.digest;
  assertFail(authority, "unexpected_layout_operation");
});

test("layout operation digest mismatch fails closed", () => {
  const authority = makeAuthority({ family: "layout" });
  authority.operation.layout_operation_digest = "0".repeat(64);
  assertFail(authority, "layout_operation_digest_mismatch");
});

test("mutation materialization digest mismatch fails closed", () => {
  const authority = makeAuthority();
  authority.operation.mutation_materialization_digest = "0".repeat(64);
  assertFail(authority, "mutation_materialization_digest_mismatch");
});

test("layout structural witness pre!=post fails closed", () => {
  const authority = makeAuthority({ family: "layout", structuralWitnessMismatch: true });
  assertFail(authority, "layout_structural_witness_mismatch");
});

test("restoration digest mismatch (tampered) fails closed", () => {
  const authority = makeAuthority();
  authority.restoration_strategy.digest = "0".repeat(64);
  assertFail(authority, "restoration_digest_mismatch");
});

test("unknown restoration strategy tag fails closed", () => {
  const authority = makeAuthority();
  authority.restoration_strategy = { contract_version: "mystery_v1", digest: "0".repeat(64), ref: "x" };
  assertFail(authority, "unknown_restoration_strategy");
});

test("malformed restoration payload (payload + ref both present) fails closed", () => {
  const authority = makeAuthority();
  authority.restoration_strategy = {
    contract_version: "inverse_delta_v1",
    digest: "0".repeat(64),
    payload: { ops: [] },
    ref: "x",
  };
  assertFail(authority, "malformed_restoration_payload");
});

test("compensation digest mismatch fails closed", () => {
  const authority = makeAuthority();
  authority.restoration_strategy_compensation = _compensationEnvelope(authority, { digestOverride: "0".repeat(64) });
  assertFail(authority, "compensation_digest_mismatch");
});

test("compensation fence unbound fails closed", () => {
  const authority = makeAuthority();
  const other = makeAuthority();
  other.transaction_id = "different";
  authority.restoration_strategy_compensation = _compensationEnvelope(other);
  assertFail(authority, "compensation_fence_unbound");
});

test("malformed restoration compensation (missing fence key) fails closed", () => {
  const authority = makeAuthority();
  const comp = _compensationEnvelope(authority);
  delete comp.fence.generation;
  authority.restoration_strategy_compensation = comp;
  assertFail(authority, "malformed_restoration_compensation");
});

// ── §3.2 inverse-relation failures (re-validated, never generated) ───────────

test("self-inverse (forward value cloned as inverse) fails closed", () => {
  const forwardOps = [{ op: "set_node_field", target: ["", "n1", "f"], value: 2 }];
  const inverseOps = [{ op: "set_node_field", target: ["", "n1", "f"], value: 2 }];
  const authority = makeAuthority({ ops: forwardOps, restoration: _inverseDeltaRestoration(inverseOps) });
  assertFail(authority, "invalid_inverse_strategy");
});

test("inverse coverage gap fails closed", () => {
  const forwardOps = [
    { op: "set_node_field", target: ["", "n1", "f"], value: 2 },
    { op: "set_node_field", target: ["", "n2", "g"], value: 3 },
  ];
  const inverseOps = [{ op: "set_node_field", target: ["", "n1", "f"], value: 1 }];
  const authority = makeAuthority({ ops: forwardOps, restoration: _inverseDeltaRestoration(inverseOps) });
  assertFail(authority, "inverse_coverage_gap");
});

test("inverse identity unbound fails closed", () => {
  const forwardOps = [{ op: "set_node_field", target: ["", "n1", "f"], value: 2 }];
  const inverseOps = [{ op: "set_node_field", target: ["", "n3", "f"], value: 1 }];
  const authority = makeAuthority({ ops: forwardOps, restoration: _inverseDeltaRestoration(inverseOps) });
  assertFail(authority, "inverse_identity_unbound");
});

test("inverse class mismatch fails closed", () => {
  // Forward add_node uid "x"; inverse is add_node (same identity, wrong class —
  // the mandated inverse of add_node is remove_node).
  const forwardOps = [
    { op: "add_node", scope_path: "", uid: "x", node_id: "1", class_type: "T", fields: {}, inputs: {} },
  ];
  const inverseOps = [
    { op: "add_node", scope_path: "", uid: "x", node_id: "1", class_type: "T", fields: {}, inputs: {} },
  ];
  const authority = makeAuthority({ ops: forwardOps, restoration: _inverseDeltaRestoration(inverseOps) });
  assertFail(authority, "inverse_class_mismatch");
});

test("restoration family mismatch fails closed", () => {
  // Structural forward ops but a layout-tagged inverse payload.
  const forwardOps = [{ op: "set_node_field", target: ["", "n1", "f"], value: 2 }];
  const inverseOps = [{ op: "set_node_field", target: ["", "n1", "f"], value: 1 }];
  const rest = _inverseDeltaRestoration(inverseOps);
  // Re-tag as inverse_layout_operation_v1 while keeping a structural family.
  rest.contract_version = "inverse_layout_operation_v1";
  const normalized = canonicalizeContractNumeric(rest.payload, { finiteErrorCode: "non_finite_materialization" });
  rest.digest = sha256Hex({ contract_version: "inverse_layout_operation_v1", payload: normalized });
  const authority = makeAuthority({ ops: forwardOps, restoration: rest });
  assertFail(authority, "restoration_family_mismatch");
});
