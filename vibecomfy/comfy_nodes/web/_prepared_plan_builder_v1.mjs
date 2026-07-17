// _prepared_plan_builder_v1.mjs — PRIVATE pure preflight/plan proof (C1).
//
// C1 checkpoint: a pure, prepared-authority-only module that validates a bound
// prepared authority via the directly-imported C0 contract asserters and the
// shared canonical hash, then builds and deeply freezes a pure description of
// the INTENDED native primitives.  It is a proof module, not an executor:
//
//   - Takes PREPARED AUTHORITY ONLY as its sole argument.  No dependency
//     injection of asserters/hash (Gate #4 + #8): the hashing identity is fixed
//     at import time by importing `canonical_hash.js` / the C0 contract modules
//     by name.
//   - Imports ONLY pure contract modules: `prepared_authority_v1.js`,
//     `layout_operation_v1.js`, `mutation_materialization_v1.js`,
//     `canonical_hash.js`.  It does NOT import `comfy_adapter.js`,
//     `intent_graph_adapter.js`, LiteGraph, the DOM, or anything that can touch
//     a runtime graph.  Purity is enforced OUTSIDE this module by the
//     externally-owned harness sentinels and the static import-reachability
//     test (§6.3, §6.6, §7.2) — never by self-attestation.
//   - It re-validates the already-bound `restoration_strategy` digest by
//     recomputation and re-runs the §3.2 inverse-relation check (via
//     `digest()`); it re-validates the optional
//     `restoration_strategy_compensation` digest if present.  It does NOT
//     generate an inverse from live state and does NOT execute, write,
//     repaint, or serialize any primitive.
//
// Return contract:
//   buildPreparedPlan(preparedAuthority)
//     -> { ok: true,  plan: Frozen<PlanShape> }
//      | { ok: false, diagnostic: { code, detail } }
//
// The return value carries ONLY `{ok, plan|diagnostic}`.  It never carries
// `sentinelCounts`, proof counters, or any self-attested zero-native evidence
// (Gate #4).  Zero-native-call evidence is produced and asserted entirely
// outside this module.

import {
  validatePreparedAuthorityV1,
  digest as _revalidateRestoration,
  digestCompensation as _revalidateCompensation,
} from "./prepared_authority_v1.js";
import {
  assertLayoutOperationEnvelope,
} from "./layout_operation_v1.js";
import {
  assertMutationMaterializationEnvelope,
} from "./mutation_materialization_v1.js";
import { sha256Hex, canonicalizeContractNumeric } from "./canonical_hash.js";

export const PREPARED_PLAN_CONTRACT_V1 = "prepared_plan_v1";

const _ALLOWED_DELTA_OPS = new Set([
  "add_node",
  "remove_node",
  "set_node_field",
  "set_mode",
  "upsert_link",
  "remove_link",
]);

function _isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function _deepFreeze(value) {
  if (value === null || typeof value !== "object") return value;
  if (Object.isFrozen(value)) {
    // Still recurse so nested children are frozen too.
    if (Array.isArray(value)) {
      for (let i = 0; i < value.length; i += 1) _deepFreeze(value[i]);
    } else {
      for (const key of Object.keys(value)) _deepFreeze(value[key]);
    }
    return value;
  }
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) _deepFreeze(value[i]);
    Object.freeze(value);
    return value;
  }
  for (const key of Object.keys(value)) _deepFreeze(value[key]);
  Object.freeze(value);
  return value;
}

function _fail(code, detail) {
  return { ok: false, diagnostic: { code: code || "unknown_error", detail: detail || {} } };
}

// ── Recompute the bound digests by independent recomputation (§7.2 #3) ───────
// These mirror the validator's preimage exactly.  They are recomputed here so
// the plan's restoration/compensation evidence is DERIVED by recomputation,
// never copied from the authority's stored digest.

function _recomputeRestorationDigest(strategy) {
  if (!_isPlainObject(strategy)) {
    throw Object.assign(new Error("restoration_strategy must be an object"), {
      code: "malformed_restoration_payload",
    });
  }
  if (strategy.contract_version === "baseline_snapshot_v1") {
    return sha256Hex({ contract_version: strategy.contract_version, ref: strategy.ref });
  }
  const normalizedPayload = canonicalizeContractNumeric(strategy.payload, {
    finiteErrorCode: "non_finite_materialization",
  });
  return sha256Hex({ contract_version: strategy.contract_version, payload: normalizedPayload });
}

function _recomputeCompensationDigest(compensation) {
  const normalizedFence = canonicalizeContractNumeric(compensation.fence, {
    finiteErrorCode: "non_finite_materialization",
  });
  return sha256Hex({
    contract_version: compensation.contract_version,
    wire_version: compensation.wire_version,
    ref: compensation.ref,
    fence: normalizedFence,
  });
}

// ── Intended-primitive derivation (pure description, never executed) ─────────

function _endpoint(ref) {
  // delta endpoint ref shape: ["", uid, port] (root-scoped).
  if (!Array.isArray(ref)) return null;
  return { node_uid: ref[1] ?? null, port: ref[2] ?? null };
}

function _structuralIntendedPrimitives(operation) {
  const ops = Array.isArray(operation.ops) ? operation.ops : [];
  const materialization = operation.mutation_materialization;
  const entriesByIndex = new Map();
  if (_isPlainObject(materialization) && Array.isArray(materialization.entries)) {
    for (const entry of materialization.entries) {
      if (_isPlainObject(entry)) entriesByIndex.set(entry.source_op_index, entry);
    }
  }
  return ops.map((op, index) => {
    if (!_isPlainObject(op) || !_ALLOWED_DELTA_OPS.has(op.op)) {
      // Should be unreachable: validatePreparedAuthorityV1 already enforced
      // strict root-scoped canonical ops.  Surface defensively rather than
      // synthesize a primitive.
      return { kind: "unknown_op", op_index: index };
    }
    switch (op.op) {
      case "add_node": {
        const entry = entriesByIndex.has(index) ? entriesByIndex.get(index) : null;
        const primitive = {
          kind: "add_node",
          op_index: index,
          uid: op.uid,
          node_id: op.node_id,
          class_type: op.class_type,
          fields: op.fields,
          inputs: op.inputs,
          materialization_entry: entry,
        };
        return primitive;
      }
      case "remove_node": {
        const target = Array.isArray(op.target) ? op.target : [];
        return {
          kind: "remove_node",
          op_index: index,
          target_uid: target.length > 1 ? target[1] : null,
        };
      }
      case "set_node_field": {
        const target = Array.isArray(op.target) ? op.target : [];
        return {
          kind: "set_node_field",
          op_index: index,
          target_uid: target.length > 1 ? target[1] : null,
          field_path: target.length > 2 ? target[2] : null,
          value: op.value,
        };
      }
      case "set_mode": {
        const target = Array.isArray(op.target) ? op.target : [];
        return {
          kind: "set_mode",
          op_index: index,
          target_uid: target.length > 1 ? target[1] : null,
          mode: op.mode,
        };
      }
      case "upsert_link": {
        return {
          kind: "upsert_link",
          op_index: index,
          from: _endpoint(op.from),
          to: _endpoint(op.to),
        };
      }
      case "remove_link": {
        return {
          kind: "remove_link",
          op_index: index,
          to: _endpoint(op.to),
        };
      }
      default:
        return { kind: "unknown_op", op_index: index };
    }
  });
}

function _layoutIntendedPrimitives(layoutEnvelope) {
  const ops = Array.isArray(layoutEnvelope.ops) ? layoutEnvelope.ops : [];
  return ops.map((op, index) => {
    switch (op.op) {
      case "set_node_geometry": {
        const primitive = {
          kind: "set_node_geometry",
          op_index: index,
          uid: op.uid,
          pos: op.pos,
        };
        if (Object.prototype.hasOwnProperty.call(op, "size")) primitive.size = op.size;
        return primitive;
      }
      case "add_group":
        return {
          kind: "add_group",
          op_index: index,
          id: op.id,
          bounding: op.bounding,
          title: op.title,
          color: op.color,
        };
      case "set_group_geometry": {
        const primitive = { kind: "set_group_geometry", op_index: index, id: op.id };
        for (const field of ["bounding", "title", "color"]) {
          if (Object.prototype.hasOwnProperty.call(op, field)) primitive[field] = op[field];
        }
        return primitive;
      }
      case "remove_group":
        return { kind: "remove_group", op_index: index, id: op.id };
      default:
        return { kind: "unknown_op", op_index: index };
    }
  });
}

// ── Public pure entry point ─────────────────────────────────────────────────

export function buildPreparedPlan(preparedAuthority) {
  // 1. Validate the prepared authority via the directly-imported sole JS
  //    authority validator (which itself calls the layout/materialization
  //    asserters, the restoration `digest()` — including the §3.2 inverse
  //    relation check — and the compensation validator).  This enforces every
  //    §4 fail-closed row relevant to C1 before any plan is built.
  let validated;
  try {
    validated = validatePreparedAuthorityV1(preparedAuthority);
  } catch (error) {
    return _fail(error && error.code, error && error.detail);
  }

  try {
    const operationFamily = validated.operation_family;
    const operation = validated.operation;

    // 2. Independently re-assert the bound contract envelopes via the
    //    directly-imported C0 asserters, capturing the NORMALIZED envelopes so
    //    the intended primitives are derived from validated contract data, not
    //    raw input.  (These are idempotent re-assertions; the authority
    //    validator already passed them — this step proves the plan is derived
    //    from the validated contracts directly.)
    let layoutEnvelope = null;
    let materializationEnvelope = null;
    if (operationFamily === "layout") {
      layoutEnvelope = assertLayoutOperationEnvelope(operation.layout_operation);
    } else if (operationFamily === "structural") {
      const ops = Array.isArray(operation.ops) ? operation.ops : [];
      const hasAddNode = ops.some((op) => _isPlainObject(op) && op.op === "add_node");
      if (hasAddNode) {
        materializationEnvelope = assertMutationMaterializationEnvelope(
          operation.mutation_materialization,
          { accompanyingOps: ops },
        );
      }
    }

    // 3. Re-validate the already-bound restoration digest by independent
    //    recomputation and re-run the §3.2 inverse-relation check via
    //    `digest()` (re-validation, NOT generation from live state).
    _revalidateRestoration(validated.restoration_strategy, {
      family: operationFamily,
      forwardOps: operation.ops,
    });
    const recomputedRestorationDigest = _recomputeRestorationDigest(
      validated.restoration_strategy,
    );
    if (recomputedRestorationDigest !== validated.restoration_strategy.digest) {
      return _fail("restoration_digest_mismatch", {
        bound: validated.restoration_strategy.digest,
        recomputed: recomputedRestorationDigest,
      });
    }

    // 4. Re-validate the optional compensation digest if present (re-validation
    //    only; never executes a compensation restore).
    const compensationPresent = Object.prototype.hasOwnProperty.call(
      validated,
      "restoration_strategy_compensation",
    );
    let compensationEvidence = { present: false };
    if (compensationPresent) {
      const compensation = validated.restoration_strategy_compensation;
      _revalidateCompensation(compensation, validated);
      const recomputedCompensationDigest = _recomputeCompensationDigest(compensation);
      if (recomputedCompensationDigest !== compensation.digest) {
        return _fail("compensation_digest_mismatch", {
          bound: compensation.digest,
          recomputed: recomputedCompensationDigest,
        });
      }
      compensationEvidence = {
        present: true,
        contract_version: compensation.contract_version,
        recomputed_digest: recomputedCompensationDigest,
        bound: true,
      };
    }

    // 5. Derive the pure intended-primitive description from the validated
    //    authority ONLY.  Never executed.
    let intendedPrimitives;
    if (operationFamily === "layout") {
      intendedPrimitives = _layoutIntendedPrimitives(layoutEnvelope);
    } else {
      intendedPrimitives = _structuralIntendedPrimitives(operation);
    }

    const plan = {
      contract_version: PREPARED_PLAN_CONTRACT_V1,
      authority_receipt: {
        transaction_id: validated.transaction_id,
        candidate_id: validated.candidate_id,
        plan_hash: validated.plan_hash,
        generation: validated.generation,
        lease_nonce: validated.lease_nonce,
        workflow_id: validated.workflow_id,
      },
      operation_family: operationFamily,
      intended_primitives: intendedPrimitives,
      restoration: {
        contract_version: validated.restoration_strategy.contract_version,
        recomputed_digest: recomputedRestorationDigest,
        bound: true,
      },
      compensation: compensationEvidence,
    };

    return { ok: true, plan: _deepFreeze(plan) };
  } catch (error) {
    return _fail(error && error.code, error && error.detail);
  }
}

export default { PREPARED_PLAN_CONTRACT_V1, buildPreparedPlan };
