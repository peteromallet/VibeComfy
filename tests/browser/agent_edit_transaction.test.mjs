import assert from "node:assert/strict";
import test from "node:test";

import {
  auditLandedMutationPlan,
  boundedBrowserTransactionError,
  normalizeCandidateTransaction,
  transactionAllowsRejectOrFailClosedDiscard,
  resolvePreparedMutationPlan,
  transactionAllows,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_transaction.js";

test("malformed V2 authority remains rejectable but never applyable", () => {
  const malformed = transaction();
  malformed.candidate_authority.workflow_id = "not-a-workflow-uuid";
  const normalized = normalizeCandidateTransaction(malformed);

  assert.equal(normalized, null);
  assert.equal(transactionAllowsRejectOrFailClosedDiscard(normalized, {
    rawTransaction: malformed,
    agentEditProtocol: "v2_delta",
    candidatePresent: true,
  }), true);
  assert.equal(transactionAllowsRejectOrFailClosedDiscard(normalized, {
    rawTransaction: malformed,
    agentEditProtocol: "v2_delta",
    candidatePresent: false,
  }), false);
});

import { makeValidCandidateTransactionV2 } from "./authority_factory.mjs";

const DEFAULT_OPS = [
  {
    op: "add_node",
    scope_path: "",
    class_type: "ImageScale",
    uid: "n1",
    node_id: "n1",
  },
  { op: "upsert_link", from: ["", "n1", "IMAGE"], to: ["", "12", "images"] },
];

function transaction(state = "candidate_ready", overrides = {}) {
  return makeValidCandidateTransactionV2({
    sessionId: "s1",
    turnId: "0001",
    planHash: "plan-1",
    deltaOps: DEFAULT_OPS,
    state,
    generation: state === "prepared" ? 1 : undefined,
    leaseNonce: state === "prepared" ? "lease-1" : undefined,
    overrides,
  });
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
  assert.equal(resolved.deltaHash, "plan-1-delta");
  assert.equal(resolved.deltaOps.length, 2);

  const changedOps = structuredClone(DEFAULT_OPS);
  changedOps[1].to = ["", "74", "images"];
  const changed = makeValidCandidateTransactionV2({
    sessionId: "s1",
    turnId: "0001",
    planHash: "plan-1",
    deltaOps: changedOps,
    state: "prepared",
    generation: 1,
    leaseNonce: "lease-1",
  });
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
