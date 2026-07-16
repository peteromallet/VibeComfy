import assert from "node:assert/strict";
import test from "node:test";

import {
  auditLandedMutationPlan,
  boundedBrowserTransactionError,
  normalizeCandidateTransaction,
  resolvePreparedMutationPlan,
  transactionAllows,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_transaction.js";

function transaction(state = "candidate_ready", overrides = {}) {
  const operations = [
    {
      op: "add_node",
      scope_path: "",
      class_type: "ImageScale",
      uid: "n1",
      node_id: "n1",
    },
    { op: "upsert_link", from: ["", "n1", "IMAGE"], to: ["", "12", "images"] },
  ];
  const projectionRef = {
    kind: "projection_ref_v1",
    projection: "structural_v1",
    digest: "a".repeat(64),
  };
  const authority = {
    contract_version: "candidate_authority_v1",
    transaction_id: "tx-1",
    candidate_id: "candidate-1",
    workflow_id: "123e4567-e89b-12d3-a456-426614174000",
    scope: { kind: "root", path: "" },
    session_id: "s1",
    turn_id: "0001",
    operation: { delta_contract: "delta_v1", wire_version: "2.0.0", ops: operations },
    operation_family: "structural",
    precondition: projectionRef,
    postcondition: projectionRef,
    rollback_projection: "structural_v1",
    restoration_strategy: {
      contract_version: "inverse_delta_v1",
      digest: "b".repeat(64),
      payload: [],
    },
    plan_hash: "plan-1",
    authority_receipt_contract_version: "authority_receipt_v2",
    authority_receipt_delta_schema: "2.0.0",
    authority_receipt_digest: "c".repeat(64),
  };
  const preparedAuthority = state === "prepared"
    ? {
        ...authority,
        contract_version: "prepared_authority_v1",
        generation: 1,
        lease_nonce: "lease-1",
      }
    : null;
  return {
    contract_version: "candidate_transaction_v2",
    state,
    candidate_authority: authority,
    prepared_authority: preparedAuthority,
    resume_state: null,
    session_id: "s1",
    turn_id: "0001",
    plan_hash: "plan-1",
    generation: state === "prepared" ? 1 : null,
    lease_nonce: state === "prepared" ? "lease-1" : null,
    plan: {
      schema_version: "2.0.0",
      delta_ops_envelope: {
        schema_version: "2.0.0",
        ops: operations,
      },
      delta_hash: "delta-1",
      op_count: 2,
      schema_provenance: {},
    },
    hashes: {
      candidate_graph_hash: "candidate-full",
      candidate_structural_graph_hash: "candidate-structural",
      authority_receipt_hash: "c".repeat(64),
    },
    authority: {
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
    },
    available_actions: state === "candidate_ready" ? ["apply", "reject"] : ["rollback"],
    terminal: false,
    last_error: null,
    ...overrides,
  };
}

test("candidate transaction vocabulary is the action authority", () => {
  const ready = normalizeCandidateTransaction(transaction());
  assert.equal(transactionAllows(ready, "apply"), true);
  assert.equal(transactionAllows(ready, "rollback"), false);
  assert.equal(normalizeCandidateTransaction({ state: "candidate_ready" }), null);
  assert.equal(
    normalizeCandidateTransaction(transaction("prepared", { available_actions: ["apply"] })),
    null,
  );
});

test("Prepare must return the exact persisted mutation plan", () => {
  const ready = transaction();
  const prepared = transaction("prepared");
  const resolved = resolvePreparedMutationPlan(ready, prepared);
  assert.equal(resolved.deltaHash, "delta-1");
  assert.equal(resolved.deltaOps.length, 2);

  const changed = transaction("prepared");
  changed.plan.delta_ops_envelope.ops[1].to = ["", "74", "images"];
  assert.throws(
    () => resolvePreparedMutationPlan(ready, changed),
    /operations differ/,
  );
});

test("versioned layout verification must match between candidate and prepare", () => {
  const layoutVerification = {
    contract_version: "layout_verification_v1",
    projection: "browser_layout_v1",
    candidate_layout_graph_hash: "a".repeat(64),
  };
  const ready = transaction("candidate_ready", {
    authority: {
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "layout_structural_noop",
      layout_verification: layoutVerification,
    },
  });
  const prepared = transaction("prepared", {
    authority: {
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "layout_structural_noop",
      layout_verification: layoutVerification,
    },
  });
  assert.equal(
    resolvePreparedMutationPlan(ready, prepared).layoutVerification.projection,
    "browser_layout_v1",
  );

  prepared.authority.layout_verification = {
    ...layoutVerification,
    candidate_layout_graph_hash: "b".repeat(64),
  };
  assert.throws(
    () => resolvePreparedMutationPlan(ready, prepared),
    /layout verification contract differs/,
  );
});

test("unknown layout verification contracts fail closed", () => {
  const malformed = transaction("candidate_ready", {
    authority: {
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "layout_structural_noop",
      layout_verification: {
        contract_version: "layout_verification_v999",
        projection: "browser_layout_v1",
        candidate_layout_graph_hash: "a".repeat(64),
      },
    },
  });
  assert.equal(normalizeCandidateTransaction(malformed), null);
});

test("landed plan rejects missing, reordered, or invented provenance", () => {
  const ops = transaction().plan.delta_ops_envelope.ops;
  assert.deepEqual(
    auditLandedMutationPlan(ops, [
      { op: "add_node", source_op_index: 0, source_op_kind: "add_node" },
      {
        op: "upsert_link",
        source_op_index: 0,
        source_op_kind: "add_node",
        derivedFromAddNode: true,
      },
      { op: "upsert_link", source_op_index: 1, source_op_kind: "upsert_link" },
    ]).covered_op_indexes,
    [0, 1],
  );
  assert.throws(
    () => auditLandedMutationPlan(ops, [
      { op: "add_node", source_op_index: 0, source_op_kind: "add_node" },
    ]),
    /did not land/,
  );
  assert.throws(
    () => auditLandedMutationPlan(ops, [
      { op: "remove_node", source_op_index: 0, source_op_kind: "add_node" },
      { op: "upsert_link", source_op_index: 1, source_op_kind: "upsert_link" },
    ]),
    /differs/,
  );
  assert.throws(
    () => auditLandedMutationPlan(ops, [
      { op: "upsert_link", source_op_index: 1, source_op_kind: "upsert_link" },
      { op: "add_node", source_op_index: 0, source_op_kind: "add_node" },
    ]),
    /order differs/,
  );
});

test("browser transaction failures preserve only bounded stack evidence", () => {
  const error = new Error("x".repeat(3000));
  error.stack = Array.from({ length: 20 }, (_, index) => `line-${index}-${"y".repeat(600)}`).join("\n");
  const diagnostic = boundedBrowserTransactionError(error, "canvas_apply", {
    resumeState: "prepared",
  });
  assert.equal(diagnostic.message.length, 2048);
  assert.equal(diagnostic.stack.length, 8);
  assert.equal(diagnostic.stack.every((line) => line.length <= 512), true);
  assert.equal(diagnostic.resume_state, "prepared");
});
