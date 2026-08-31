// authority_factory.mjs — shared browser-test authority factory.
//
// Constructs valid strict candidate_transaction_v2, candidate_authority_v1,
// and prepared_authority_v1 values USING canonical production owners/functions
// for canonical digests, inverse/restoration relation, mutation materialization
// and layout operation bindings.
//
// Does NOT duplicate digest algorithms in test code.  Every digest is computed
// through the production modules (sha256Hex, canonicalizeContractNumeric,
// projectionReferenceV1, computeLayoutOperationDigest,
// computeMutationMaterializationDigest).
//
// Callers may override any field via `overrides` to intentionally construct
// malformed negatives.  The factory produces valid fixtures by default.

import { sha256Hex, canonicalizeContractNumeric } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";
import {
  buildLayoutGraphProjection,
  buildStructuralGraphProjection,
  projectionReferenceV1,
} from "../../vibecomfy/comfy_nodes/web/projection_registry_v1.js";
import { computeLayoutOperationDigest } from "../../vibecomfy/comfy_nodes/web/layout_operation_v1.js";
import { computeMutationMaterializationDigest } from "../../vibecomfy/comfy_nodes/web/mutation_materialization_v1.js";

const DEFAULT_WORKFLOW_ID = "123e4567-e89b-12d3-a456-426614174000";
const HEX64 = /^[0-9a-f]{64}$/;

// ── Delta op normalization ───────────────────────────────────────────────────
//
// Canonical delta ops have `scope_path: ""` and `target` arrays starting with
// the empty-string scope.  This helper normalises test-authored ops that may
// still carry `"nodes"` as the scope segment (legacy hand-written form) into
// the canonical shape used by production.
function _normalizeDeltaOp(op) {
  const normalized = structuredClone(op);
  // Normalize target scope segments.
  for (const field of ["target", "from", "to"]) {
    const value = normalized[field];
    if (Array.isArray(value) && value[0] === "nodes") {
      normalized[field] = ["", ...value.slice(1)];
    }
  }
  // Flatten set_node_field targets beyond 3 elements.
  if (
    normalized.op === "set_node_field" &&
    Array.isArray(normalized.target) &&
    normalized.target.length > 3
  ) {
    normalized.target = [
      normalized.target[0],
      normalized.target[1],
      normalized.target.slice(2).join("."),
    ];
  }
  // Canonicalize remove_node target.
  if (normalized.op === "remove_node" && !Array.isArray(normalized.target)) {
    normalized.target = [
      normalized.scope_path || "",
      String(normalized.uid ?? normalized.node_id),
    ];
    delete normalized.uid;
    delete normalized.node_id;
  }
  // Canonicalize set_mode target.
  if (normalized.op === "set_mode" && !Array.isArray(normalized.target)) {
    normalized.target = [
      normalized.scope_path || "",
      String(normalized.uid ?? normalized.node_id),
    ];
    delete normalized.uid;
    delete normalized.node_id;
  }
  return normalized;
}

function normalizeDeltaOps(ops) {
  if (!Array.isArray(ops)) return [];
  // Normalize each op into the canonical shape, preserving the exact op list
  // and order.  A canonical rewire (remove_link + upsert_link at the same `to`)
  // is a valid two-op pair: the production inverse-relation identity now
  // distinguishes link ops by op class, so both ops survive here unchanged.
  return ops.map(_normalizeDeltaOp);
}

// ── Inverse op generation ────────────────────────────────────────────────────
//
// Auto-generates a valid inverse op for each forward op such that
// `assertInverseRelation` passes.  The inverse carries a distinct prior-state
// value (never the forward value) so the self-inverse guard is satisfied.
// This is intentionally synthetic — it satisfies the contract without requiring
// the test to supply actual prior state.

export function makeInverseOp(forwardOp) {
  const op = forwardOp.op;
  if (op === "add_node") {
    const uid = forwardOp.uid;
    return { op: "remove_node", target: ["", uid] };
  }
  if (op === "remove_node") {
    const uid =
      (Array.isArray(forwardOp.target) && forwardOp.target.length > 1
        ? forwardOp.target[1]
        : null) || forwardOp.uid || "unknown";
    return {
      op: "add_node",
      scope_path: "",
      uid,
      node_id: String(uid),
      class_type: "SaveImage",
      fields: {},
      inputs: {},
    };
  }
  if (op === "set_node_field") {
    const fwdValue = forwardOp.value;
    const inverseValue =
      typeof fwdValue === "number"
        ? fwdValue === 0
          ? 1
          : 0
        : typeof fwdValue === "string"
          ? fwdValue + "-prior"
          : fwdValue === true
            ? false
            : fwdValue === false
              ? true
              : "prior-value";
    return {
      op: "set_node_field",
      target: [...forwardOp.target],
      value: inverseValue,
    };
  }
  if (op === "set_mode") {
    return {
      op: "set_mode",
      target: [...forwardOp.target],
      mode: forwardOp.mode === 0 ? 4 : 0,
    };
  }
  if (op === "upsert_link") {
    return { op: "remove_link", to: [...(forwardOp.to || [])] };
  }
  if (op === "remove_link") {
    return {
      op: "upsert_link",
      from: forwardOp.from && forwardOp.from.length > 0
        ? [...forwardOp.from]
        : ["", "unknown", "out"],
      to: [...(forwardOp.to || [])],
    };
  }
  // Layout ops
  if (op === "set_node_geometry") {
    const fwdPos = forwardOp.pos || [0, 0];
    return {
      op: "set_node_geometry",
      uid: forwardOp.uid,
      pos: [fwdPos[0] + 100, fwdPos[1] + 100],
      ...(forwardOp.size ? { size: [(forwardOp.size[0] || 200) + 10, (forwardOp.size[1] || 100) + 10] } : {}),
    };
  }
  if (op === "add_group") {
    return { op: "remove_group", id: forwardOp.id };
  }
  if (op === "remove_group") {
    return {
      op: "add_group",
      id: forwardOp.id,
      bounding: [0, 0, 100, 100],
      title: "restored-group",
      color: null,
    };
  }
  if (op === "set_group_geometry") {
    return {
      op: "set_group_geometry",
      id: forwardOp.id,
      bounding: [50, 50, 150, 150],
    };
  }
  // Fallback: mirror as a set_node_field with different value (will pass inverse if the forward has one)
  return {
    op: "set_node_field",
    target: ["", "unknown", "f"],
    value: "fallback-prior",
  };
}

export function makeInverseOps(forwardOps) {
  return (Array.isArray(forwardOps) ? forwardOps : []).map(makeInverseOp);
}

// ── Materialization envelope ─────────────────────────────────────────────────

function _addNodeIndices(ops) {
  const indices = [];
  for (let i = 0; i < ops.length; i++) {
    if (ops[i] && ops[i].op === "add_node") indices.push(i);
  }
  return indices;
}

function _makeMaterializationEnvelope(accompanyingOps) {
  const addIdx = _addNodeIndices(accompanyingOps);
  if (addIdx.length === 0) return null;
  const entries = addIdx.map((i) => ({ source_op_index: i, kind: "add_node" }));
  const mat = {
    contract_version: "mutation_materialization_v1",
    wire_version: "1.0.0",
    entries,
  };
  mat.digest = computeMutationMaterializationDigest(entries, accompanyingOps);
  return mat;
}

// ── Layout operation envelope ────────────────────────────────────────────────

function _makeLayoutOperationEnvelope(layoutOps) {
  if (!layoutOps || layoutOps.length === 0) return null;
  const envelope = {
    contract_version: "layout_operation_v1",
    wire_version: "1.0.0",
    ops: layoutOps,
  };
  envelope.digest = computeLayoutOperationDigest(layoutOps);
  return envelope;
}

// ── Projection references ────────────────────────────────────────────────────

function _emptyGraph() {
  return { nodes: [], links: [] };
}

function _ref(projection, digest) {
  return { kind: "projection_ref_v1", projection, digest };
}

// ── Restoration strategy ─────────────────────────────────────────────────────

export function makeInverseDeltaRestoration(inverseOps) {
  const payload = { ops: inverseOps };
  // If the inverse has add_node ops, add materialization.
  const mat = _makeMaterializationEnvelope(inverseOps);
  if (mat) {
    payload.mutation_materialization = mat;
    payload.mutation_materialization_digest = mat.digest;
  }
  const normalizedPayload = canonicalizeContractNumeric(payload, {
    finiteErrorCode: "non_finite_materialization",
  });
  const digest = sha256Hex({
    contract_version: "inverse_delta_v1",
    payload: normalizedPayload,
  });
  return {
    contract_version: "inverse_delta_v1",
    digest,
    payload,
  };
}

export function makeInverseLayoutOperationRestoration(inverseLayoutOps) {
  const layoutOp = _makeLayoutOperationEnvelope(inverseLayoutOps);
  const payload = {
    layout_operation: layoutOp,
    layout_operation_digest: layoutOp.digest,
  };
  const normalizedPayload = canonicalizeContractNumeric(payload, {
    finiteErrorCode: "non_finite_geometry",
  });
  const digest = sha256Hex({
    contract_version: "inverse_layout_operation_v1",
    payload: normalizedPayload,
  });
  return {
    contract_version: "inverse_layout_operation_v1",
    digest,
    payload,
  };
}

// ── Main factory ─────────────────────────────────────────────────────────────

/**
 * Build a valid candidate_transaction_v2 with canonical production digests.
 *
 * Required:
 *   sessionId  — session identity string
 *   planHash   — plan identity string
 *
 * Operations:
 *   deltaOps   — array of canonical delta ops (default: [])
 *   family     — "structural" (default) or "layout"
 *   layoutOps  — array of layout ops (required when family === "layout")
 *
 * Graph refs (for projection precondition/postcondition digests):
 *   preconditionGraph — graph before ops (default: empty graph)
 *   postconditionGraph — graph after ops (default: same as preconditionGraph)
 *
 * State:
 *   state      — transaction state (default: "candidate_ready")
 *   generation — positive int (required for prepared+ states)
 *   leaseNonce — string (required for prepared+ states)
 *
 * Overrides:
 *   overrides  — applied last to the returned transaction object; use to
 *                intentionally construct malformed negatives
 */
export function makeValidCandidateTransactionV2({
  sessionId,
  turnId = "0001",
  planHash,
  deltaOps: rawDeltaOps = [],
  family = "structural",
  layoutOps = null,
  preconditionGraph = null,
  postconditionGraph = null,
  state = "candidate_ready",
  generation = null,
  leaseNonce = null,
  workflowId = DEFAULT_WORKFLOW_ID,
  verificationKind = "delta_replay",
  overrides = {},
}) {
  if (!sessionId) throw new Error("sessionId is required");
  if (!planHash) throw new Error("planHash is required");

  const deltaOps = normalizeDeltaOps(rawDeltaOps);
  const isLayout = family === "layout";
  const isPrepared = ["prepared", "canvas_verified", "finalized", "rollback_complete", "superseded"].includes(state);

  // ── Projection references ────────────────────────────────────────────────
  const projection = isLayout ? "layout_v1" : "structural_v1";
  const preGraph = preconditionGraph || _emptyGraph();
  const postGraph = postconditionGraph || preGraph;

  let preconditionDigest;
  let postconditionDigest;
  let candidateGraphHash;
  let candidateStructuralGraphHash;
  let candidateLayoutGraphHash;
  let submitStructuralGraphHash;
  let preconditionReference;
  let postconditionReference;

  try {
    const preRef = projectionReferenceV1(preGraph, projection);
    const compatibilityPreconditionHash = sha256Hex(
      buildStructuralGraphProjection(preGraph),
    );
    preconditionReference = {
      ...preRef,
      compatibility_digest: compatibilityPreconditionHash,
    };
    preconditionDigest = preRef.digest;
    if (!isLayout) {
      candidateStructuralGraphHash = preRef.digest;
      const structRef = projectionReferenceV1(preGraph, "structural_v1");
      if (structRef.digest !== preRef.digest) {
        candidateStructuralGraphHash = structRef.digest;
      }
    }
    const postRef = projectionReferenceV1(postGraph, projection);
    postconditionReference = postRef;
    postconditionDigest = postRef.digest;
    candidateGraphHash = postRef.digest;
    if (!isLayout) {
      const structPostRef = projectionReferenceV1(postGraph, "structural_v1");
      candidateStructuralGraphHash = structPostRef.digest;
    }
    if (isLayout) {
      const layoutPreRef = projectionReferenceV1(preGraph, "layout_v1");
      preconditionDigest = layoutPreRef.digest;
      candidateLayoutGraphHash = projectionReferenceV1(postGraph, "layout_v1").digest;
      candidateStructuralGraphHash = projectionReferenceV1(postGraph, "structural_v1").digest;
    }
    submitStructuralGraphHash = compatibilityPreconditionHash;
  } catch (_err) {
    // Fallback: use the graph as-is for digest computation if projection fails
    // (e.g., the graph doesn't have vibecomfy_uid properties).
    // Use sha256Hex directly on the graph — this is a fallback for test graphs
    // that aren't fully compliant projection inputs.
    const preDigest = sha256Hex(preGraph);
    const postDigest = sha256Hex(postGraph);
    preconditionDigest = preDigest;
    postconditionDigest = postDigest;
    candidateGraphHash = postDigest;
    candidateStructuralGraphHash = postDigest;
    submitStructuralGraphHash = preDigest;
    preconditionReference = { ..._ref(projection, preDigest), compatibility_digest: preDigest };
    postconditionReference = _ref(projection, postDigest);
    if (isLayout) {
      candidateLayoutGraphHash = postDigest;
    }
  }

  // ── Operation ─────────────────────────────────────────────────────────────
  const structuralOps = isLayout ? [] : deltaOps;
  const acceptedBatch = structuralOps.map((op) => ({ op }));
  const batchDigest = sha256Hex({ schema_version: "2.0.0", ops: structuralOps });
  /** @type {Record<string, unknown>} */
  const operation = {
    delta_contract: "delta_v1",
    wire_version: "2.0.0",
    accepted_batch_digest: batchDigest,
  };

  let resolvedLayoutOps = null;
  if (isLayout) {
    resolvedLayoutOps = layoutOps || [{ op: "set_node_geometry", uid: "node-1", pos: [10, 20] }];
    const layoutEnv = _makeLayoutOperationEnvelope(resolvedLayoutOps);
    operation.layout_operation = layoutEnv;
    operation.layout_operation_digest = layoutEnv.digest;
  } else {
    const mat = _makeMaterializationEnvelope(deltaOps);
    if (mat) {
      operation.mutation_materialization = mat;
      operation.mutation_materialization_digest = mat.digest;
    }
  }

  // ── Restoration strategy ──────────────────────────────────────────────────
  const forwardOpsForInverse = isLayout ? resolvedLayoutOps : deltaOps;
  const inverseOps = makeInverseOps(forwardOpsForInverse);
  const restoration = isLayout
    ? makeInverseLayoutOperationRestoration(inverseOps)
    : makeInverseDeltaRestoration(inverseOps);

  // ── Candidate authority ───────────────────────────────────────────────────
  /** @type {Record<string, unknown>} */
  const candidateAuthority = {
    contract_version: "candidate_authority_v1",
    transaction_id: `tx-${planHash}`,
    candidate_id: `candidate-${planHash}`,
    workflow_id: workflowId,
    scope: { kind: "root", path: "" },
    session_id: sessionId,
    turn_id: turnId,
    operation,
    operation_family: family,
    precondition: preconditionReference,
    postcondition: postconditionReference,
    rollback_projection: projection,
    restoration_strategy: restoration,
    plan_hash: planHash,
    authority_receipt_contract_version: "authority_receipt_v2",
    authority_receipt_delta_schema: "2.0.0",
    authority_receipt_digest: "c".repeat(64),
  };

  if (isLayout) {
    const structuralPre = projectionReferenceV1(preGraph, "structural_v1");
    const structuralPost = projectionReferenceV1(postGraph, "structural_v1");
    candidateAuthority.structural_witness = {
      ...structuralPre,
      compatibility_digest: sha256Hex(buildStructuralGraphProjection(preGraph)),
      precondition_digest: structuralPre.digest,
      postcondition_digest: structuralPost.digest,
    };
  }

  // ── Prepared authority ────────────────────────────────────────────────────
  let preparedAuthority = null;
  if (isPrepared) {
    const gen = generation ?? 1;
    const nonce = leaseNonce || `${planHash}-lease`;
    preparedAuthority = {
      ...structuredClone(candidateAuthority),
      contract_version: "prepared_authority_v1",
      generation: gen,
      lease_nonce: nonce,
    };
  }

  // ── Available actions ─────────────────────────────────────────────────────
  const resolvedActions =
    state === "candidate_ready"
      ? ["apply", "reject"]
      : state === "prepared"
        ? ["rollback"]
        : state === "canvas_verified"
          ? ["finalize", "rollback"]
          : [];

  // ── Assemble transaction ──────────────────────────────────────────────────
  /** @type {Record<string, unknown>} */
  const transaction = {
    contract_version: "candidate_transaction_v2",
    state,
    resume_state: null,
    session_id: sessionId,
    turn_id: turnId,
    plan_hash: planHash,
    generation: isPrepared ? (generation ?? 1) : null,
    lease_nonce: isPrepared ? (leaseNonce || `${planHash}-lease`) : null,
    plan: {
      schema_version: "2.0.0",
      accepted_batch: acceptedBatch,
      // Test-only dual-write for fixtures that still read the archived envelope
      // shape. Live validators consume accepted_batch only.
      delta_ops_envelope: {
        schema_version: "2.0.0",
        ops: deltaOps,
      },
      delta_hash: `${planHash}-delta`,
      op_count: deltaOps.length,
      schema_provenance: {},
    },
    hashes: {
      submit_graph_hash: "submit-full-hash",
      submit_structural_graph_hash: submitStructuralGraphHash,
      candidate_graph_hash: candidateGraphHash,
      candidate_structural_graph_hash: candidateStructuralGraphHash,
      authority_receipt_hash: "c".repeat(64),
      ...(isLayout ? { candidate_layout_graph_hash: candidateLayoutGraphHash } : {}),
    },
    authority: {
      replay_ok: true,
      candidate_matches: true,
      verification_kind: verificationKind,
    },
    candidate_authority: candidateAuthority,
    prepared_authority: preparedAuthority,
    available_actions: resolvedActions,
    terminal: ["finalized", "discarded", "rollback_complete", "superseded"].includes(
      state,
    ),
    last_error: null,
    ...overrides,
  };

  return transaction;
}

/**
 * Convenience: build a valid candidate_transaction_v2 and bind hashes from
 * the extension module's graph state.  Use this when the test has a live
 * harness with an actual graph on the canvas.
 */
export function bindTransactionHashes(extensionModule, transaction, graph, preconditionGraph = null) {
  const liveGraph = globalThis.__VIBECOMFY_BROWSER_APP__?.canvas?.graph?.serialize?.();
  const evidencePreconditionGraph = preconditionGraph || liveGraph || graph;
  const typedPreconditionHash = projectionReferenceV1(evidencePreconditionGraph, "structural_v1").digest;
  const typedStructuralHash = projectionReferenceV1(graph, "structural_v1").digest;
  const compatibilityPreconditionHash = sha256Hex(
    buildStructuralGraphProjection(evidencePreconditionGraph),
  );
  const compatibilityStructuralHash = sha256Hex(buildStructuralGraphProjection(graph));
  const compatibilityLayoutHash = sha256Hex(buildLayoutGraphProjection(graph));
  transaction.hashes.submit_structural_graph_hash = compatibilityPreconditionHash;
  transaction.hashes.candidate_structural_graph_hash = compatibilityStructuralHash;
  transaction.hashes.candidate_layout_graph_hash = compatibilityLayoutHash;

  for (const authority of [transaction.candidate_authority, transaction.prepared_authority]) {
    if (!authority) continue;
    const authorityProjection =
      authority.operation_family === "layout" ? "layout_v1" : "structural_v1";
    authority.precondition = {
      ...projectionReferenceV1(evidencePreconditionGraph, authorityProjection),
      compatibility_digest: compatibilityPreconditionHash,
    };
    authority.postcondition = projectionReferenceV1(graph, authorityProjection);
    if (authority.structural_witness) {
      authority.structural_witness = {
        ...projectionReferenceV1(evidencePreconditionGraph, "structural_v1"),
        compatibility_digest: compatibilityPreconditionHash,
        precondition_digest: typedPreconditionHash,
        postcondition_digest: typedStructuralHash,
      };
    }
  }
  if (transaction.authority?.verification_kind === "layout_structural_noop") {
    transaction.authority.layout_verification = {
      contract_version: "layout_verification_v1",
      projection: "browser_layout_v1",
      candidate_layout_graph_hash: compatibilityLayoutHash,
    };
  }
}

export default {
  makeValidCandidateTransactionV2,
  makeInverseOp,
  makeInverseOps,
  makeInverseDeltaRestoration,
  makeInverseLayoutOperationRestoration,
  bindTransactionHashes,
  normalizeDeltaOps,
};
