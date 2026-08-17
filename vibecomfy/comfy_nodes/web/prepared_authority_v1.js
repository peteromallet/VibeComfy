// prepared_authority_v1.js — sole JS prepared-authority validator.
//
// Mirrors the Python owner (projection_registry_v1.py).  Validates candidate
// and prepared authority envelopes, including the C0 cross-language contract
// binding (layout_operation_v1, mutation_materialization_v1), the closed
// restoration_strategy tag set with inverse-relation checking, and the
// prepare-owned optional restoration_strategy_compensation slot (§3.4).
//
// This is the SOLE JS authority validator.  No second owner; the restoration
// shape check and the inverse-relation check live here alongside the existing
// digest() code path.  Hashing identity is the shared leaf canonical_hash.js.

import { assertRootScopeV1 } from "./root_scope_v1.js";
import { issuedIdentityV1, workflowIdentityV1 } from "./identity_contract_v1.js";
import { assertForwardProjectionV1, assertProjectionReferenceV1 } from "./projection_registry_v1.js";
import { normalizeDeltaEnvelope, ensureRootScopedOps, DELTA_SCHEMA_VERSION } from "./canonical_delta.js";
import { sha256Hex, canonicalizeContractNumeric } from "./canonical_hash.js";
import { assertLayoutOperationEnvelope } from "./layout_operation_v1.js";
import { assertMutationMaterializationEnvelope } from "./mutation_materialization_v1.js";

export const PREPARED_AUTHORITY_V1 = "prepared_authority_v1";
export const CANDIDATE_AUTHORITY_V1 = "candidate_authority_v1";
export const CANDIDATE_TRANSACTION_V2 = "candidate_transaction_v2";
export const AUTHORITY_RECEIPT_CONTRACT_VERSION="authority_receipt_v2";

// §M1.6 — Legacy persisted authority compatibility.
//
// `candidate_authority_v0_legacy` is the explicit, versioned marker for a
// persisted candidate authority from a pre-strict-digest deployment. Such an
// envelope carries the v1 structural shape but its `restoration_strategy.digest`
// was not bound (the legacy era did not verify it). The load-boundary migrator
// (`migrateLegacyCandidateAuthorityV0Legacy`) is the SOLE path that upgrades a
// v0_legacy envelope to a strict `candidate_authority_v1`: it recomputes the
// restoration digest from the actual payload/ref and leaves every other field
// untouched for `validateCandidateAuthorityV1` to bind.
//
// Malformed current v1/v2 authorities NEVER carry this marker, so they cannot
// enter the migration path — they fail-closed directly in the strict validator.
// Unknown versions are rejected by both the migrator and the validators.
export const CANDIDATE_AUTHORITY_V0_LEGACY = "candidate_authority_v0_legacy";

export const RESTORATION_STRATEGY_TAGS = new Set([
  "inverse_delta_v1",
  "inverse_delta_v2",
  "inverse_layout_operation_v1",
  "baseline_snapshot_v1",
]);
const LEGACY_RESTORATION_STRATEGY_TAGS = new Set([
  "inverse_delta_v1",
  "inverse_layout_operation_v1",
  "baseline_snapshot_v1",
]);
export const RESTORATION_COMPENSATION_CONTRACT_V1 = "baseline_snapshot_v1";
export const RESTORATION_COMPENSATION_WIRE_VERSION = "1.0.0";

const _HEX64 = /^[0-9a-f]{64}$/;
const _FENCE_KEYS = new Set([
  "transaction_id", "candidate_id", "plan_hash", "lease_nonce",
  "generation", "pre_projection_digest", "post_projection_digest",
]);

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function freeze(value) { if (value && typeof value === "object") { Object.values(value).forEach(freeze); Object.freeze(value); } return value; }
function _isPlainObject(value) { return Boolean(value) && typeof value === "object" && !Array.isArray(value); }
function _fail(message, code, detail = {}) { const e = new Error(message); e.code = code; e.detail = detail; return e; }

// ── Inverse-relation contract (§3.2) ─────────────────────────────────────────

function _linkTo(op) {
  const to = op && op.to;
  if (Array.isArray(to)) return JSON.stringify(to);
  return null;
}

// Forward uniqueness identity for a link op: (op class, destination `to`).
//
// A ComfyUI input (`to`) holds exactly one inbound link, so `to` is the stable
// endpoint.  But a canonical rewire is `remove_link(to=X)` followed by
// `upsert_link(from=new, to=X)` — two distinct causal ops at the same `to`.
// Including the op class in the identity keeps both ops (the rewire is valid)
// while still rejecting a true duplicate: two `upsert_link`s to the same `to`,
// or two `remove_link`s of the same `to`, collide on `(op, to)`.
//
// Canonical `remove_link` carries only `to` (no `from`): the prior source it
// disconnects is restored by the inverse `upsert_link`, not recorded here.
function _linkForwardKey(linkOpName, op) {
  return JSON.stringify(["link", linkOpName, _linkTo(op)]);
}

function _deltaOpIdentity(op) {
  const name = op && op.op;
  if (name === "set_node_field") {
    const target = op.target;
    return JSON.stringify(["set_node_field", ...(Array.isArray(target) ? target.slice(1) : [])]);
  }
  if (name === "set_mode") {
    const target = op.target;
    return JSON.stringify(["set_mode", Array.isArray(target) && target.length > 1 ? target[1] : null]);
  }
  if (name === "add_node") return JSON.stringify(["node", op.uid]);
  if (name === "remove_node") {
    const target = op.target;
    return JSON.stringify(["node", Array.isArray(target) && target.length > 1 ? target[1] : null]);
  }
  if (name === "upsert_link" || name === "remove_link") return _linkForwardKey(name, op);
  if (name === "set_node_geometry") return JSON.stringify(["set_node_geometry", op.uid]);
  if (name === "add_group") return JSON.stringify(["group", op.id]);
  if (name === "set_group_geometry") return JSON.stringify(["set_group_geometry", op.id]);
  if (name === "remove_group") return JSON.stringify(["group", op.id]);
  return JSON.stringify([name || "", null]);
}

function _mandatedInverseClass(forwardName) {
  switch (forwardName) {
    case "set_node_field": return new Set(["set_node_field"]);
    case "set_mode": return new Set(["set_mode"]);
    case "add_node": return new Set(["remove_node"]);
    case "remove_node": return new Set(["add_node"]);
    case "upsert_link": return new Set(["remove_link", "upsert_link"]);
    case "remove_link": return new Set(["upsert_link"]);
    case "set_node_geometry": return new Set(["set_node_geometry"]);
    case "add_group": return new Set(["remove_group"]);
    case "set_group_geometry": return new Set(["set_group_geometry"]);
    case "remove_group": return new Set(["add_group"]);
    default: return new Set();
  }
}

function _inverseBindableForwardKeys(inv, forwardById) {
  const name = inv && inv.op;
  if (name === "remove_link" || name === "upsert_link") {
    const keys = [];
    for (const forwardName of ["upsert_link", "remove_link"]) {
      const key = _linkForwardKey(forwardName, inv);
      if (forwardById.has(key) && _mandatedInverseClass(forwardName).has(name)) keys.push(key);
    }
    return keys;
  }
  const key = _deltaOpIdentity(inv);
  const forward = forwardById.get(key);
  return forward && _mandatedInverseClass(forward.op).has(name) ? [key] : [];
}

function _forwardKeysAtLocus(inv, forwardById) {
  if (inv && (inv.op === "remove_link" || inv.op === "upsert_link")) {
    return ["upsert_link", "remove_link"]
      .map((name) => _linkForwardKey(name, inv))
      .filter((key) => forwardById.has(key));
  }
  const key = _deltaOpIdentity(inv);
  return forwardById.has(key) ? [key] : [];
}

function _completeMatchings(adjacency, forwardCount) {
  const used = new Set();
  const assignments = [];
  function visit(index, current) {
    if (assignments.length > 1) return;
    if (index === adjacency.length) {
      if (used.size === forwardCount) assignments.push([...current]);
      return;
    }
    for (const key of adjacency[index]) {
      if (used.has(key)) continue;
      used.add(key);
      current.push(key);
      visit(index + 1, current);
      current.pop();
      used.delete(key);
    }
  }
  visit(0, []);
  return assignments;
}

function _rootEndpoint(value) {
  return Array.isArray(value) && value.length === 3 && value[0] === "" &&
    typeof value[1] === "string" && value[1].length > 0 &&
    typeof value[2] === "string" && value[2].length > 0;
}

function _dictWithoutOp(op) {
  const result = {};
  for (const [k, v] of Object.entries(op)) { if (k !== "op") result[k] = v; }
  return result;
}

function _checkPriorStateBinding(forwardName, forwardOp, inverseOp) {
  if (forwardName === "set_node_field") {
    if (JSON.stringify(inverseOp.value) === JSON.stringify(forwardOp.value)) {
      throw _fail("Inverse set_node_field carries the forward value, not the prior value", "invalid_inverse_strategy");
    }
  } else if (forwardName === "set_mode") {
    if (inverseOp.mode === forwardOp.mode) {
      throw _fail("Inverse set_mode carries the forward mode, not the prior mode", "invalid_inverse_strategy");
    }
  } else if (forwardName === "add_node") {
    const target = inverseOp.target;
    if (!Array.isArray(target) || target.length < 2 || target[1] !== forwardOp.uid) {
      throw _fail("Inverse remove_node does not bind the added uid", "inverse_missing_prior_state");
    }
  } else if (forwardName === "remove_node") {
    const target = forwardOp.target;
    const forwardUid = Array.isArray(target) && target.length > 1 ? target[1] : null;
    if (inverseOp.uid !== forwardUid) {
      throw _fail("Inverse add_node does not bind the removed uid", "inverse_missing_prior_state");
    }
  } else if (forwardName === "upsert_link") {
    if (inverseOp.op === "remove_link") {
      if (_linkTo(inverseOp) !== _linkTo(forwardOp)) {
        throw _fail("Inverse remove_link endpoint mismatch", "inverse_missing_prior_state");
      }
    }
  } else if (forwardName === "remove_link") {
    if (_linkTo(inverseOp) !== _linkTo(forwardOp)) {
      throw _fail("Inverse upsert_link endpoint mismatch", "inverse_missing_prior_state");
    }
  } else if (forwardName === "set_node_geometry" || forwardName === "set_group_geometry") {
    if (JSON.stringify(_dictWithoutOp(forwardOp)) === JSON.stringify(_dictWithoutOp(inverseOp))) {
      throw _fail("Inverse geometry op is a verbatim clone of the forward op", "invalid_inverse_strategy");
    }
  }
}

export function assertInverseRelation(forwardOps, inverseOps, family, { priorLinkWitnesses = null } = {}) {
  const forward = Array.isArray(forwardOps) ? forwardOps : [];
  const inverse = Array.isArray(inverseOps) ? inverseOps : [];
  const forwardById = new Map();
  for (const op of forward) {
    if (!_isPlainObject(op)) continue;
    const identity = _deltaOpIdentity(op);
    if (forwardById.has(identity)) {
      throw _fail("Duplicate forward identity in delta", "duplicate_identity");
    }
    forwardById.set(identity, op);
  }
  for (const inv of inverse) {
    if (!_isPlainObject(inv)) {
      throw _fail("Inverse op is not an object", "inverse_missing_prior_state");
    }
  }
  if (inverse.length === 0 && forward.length > 0) {
    throw _fail("Inverse shares no identity with forward", "inverse_unrelated");
  }
  const adjacency = inverse.map((inv) => _inverseBindableForwardKeys(inv, forwardById));
  const matches = _completeMatchings(adjacency, forwardById.size);
  if (matches.length === 0) {
    for (let i = 0; i < inverse.length; i += 1) {
      if (adjacency[i].length !== 0) continue;
      if (_forwardKeysAtLocus(inverse[i], forwardById).length > 0) {
        throw _fail("Inverse class is not mandated at its forward locus", "inverse_class_mismatch");
      }
      if (forwardById.size === 0) throw _fail("Inverse shares no identity with forward", "inverse_unrelated");
      throw _fail("Inverse op identity is not bound to any forward op", "inverse_identity_unbound");
    }
    throw _fail("Forward op has no matching inverse", "inverse_coverage_gap");
  }
  if (matches.length > 1) {
    throw _fail("Inverse relation admits multiple complete matchings", "inverse_multiple_match");
  }
  const witnessByTo = new Map();
  if (priorLinkWitnesses !== null) {
    for (const witness of priorLinkWitnesses) witnessByTo.set(JSON.stringify(witness.to), witness);
  }
  for (let i = 0; i < inverse.length; i += 1) {
    const forwardOp = forwardById.get(matches[0][i]);
    const inverseOp = inverse[i];
    _checkPriorStateBinding(forwardOp.op, forwardOp, inverseOp);
    if (forwardOp.op === "remove_link" && priorLinkWitnesses !== null) {
      const witness = witnessByTo.get(JSON.stringify(forwardOp.to));
      if (!witness || JSON.stringify(witness.from) !== JSON.stringify(inverseOp.from) ||
          JSON.stringify(witness.to) !== JSON.stringify(inverseOp.to)) {
        throw _fail("Inverse upsert_link does not match prior-link witness", "inverse_missing_prior_state");
      }
    }
  }
}

export function forwardOperationDigest(forwardOps) {
  const envelope = normalizeDeltaEnvelope(
    { schema_version: DELTA_SCHEMA_VERSION, ops: forwardOps },
    { strict: true },
  );
  ensureRootScopedOps(envelope.ops);
  return sha256Hex(canonicalizeContractNumeric({
    delta_contract: "delta_v1",
    wire_version: DELTA_SCHEMA_VERSION,
    ops: envelope.ops,
  }, { finiteErrorCode: "non_finite_materialization" }));
}

// ── Restoration strategy (mandatory slot, closed tag set) ────────────────────

export function digest(value, { family = null, forwardOps = null } = {}) {
  if (!_isPlainObject(value)) {
    throw _fail("Restoration strategy must be an object", "malformed_restoration_payload");
  }
  const tag = value.contract_version;
  if (!RESTORATION_STRATEGY_TAGS.has(tag)) {
    throw _fail("Unknown restoration strategy tag", "unknown_restoration_strategy");
  }
  const hasPayload = Object.prototype.hasOwnProperty.call(value, "payload");
  const hasRef = Object.prototype.hasOwnProperty.call(value, "ref");
  if (hasPayload && hasRef) {
    throw _fail("Restoration payload and ref are mutually exclusive", "malformed_restoration_payload");
  }
  if (!hasPayload && !hasRef) {
    throw _fail("Restoration requires payload or ref", "malformed_restoration_payload");
  }
  if (typeof value.digest !== "string" || !_HEX64.test(value.digest)) {
    throw _fail("Restoration digest must be hex64", "malformed_restoration_payload");
  }
  if (tag === "baseline_snapshot_v1") {
    if (!hasRef) {
      throw _fail("baseline_snapshot_v1 restoration must use ref", "malformed_restoration_payload");
    }
    const ref = value.ref;
    if (typeof ref !== "string" || ref.length === 0) {
      throw _fail("baseline_snapshot_v1 ref must be a non-empty string", "malformed_restoration_payload");
    }
    const expected = sha256Hex({ contract_version: tag, ref });
    if (value.digest !== expected) {
      throw _fail("Restoration digest mismatch", "restoration_digest_mismatch");
    }
    return value;
  }
  // Payload-tagged inverse restoration.
  if (!hasPayload) {
    throw _fail("inverse restoration must use payload", "malformed_restoration_payload");
  }
  if (family !== null) {
    const allowedTags = family === "layout"
      ? new Set(["inverse_layout_operation_v1"])
      : new Set(["inverse_delta_v1", "inverse_delta_v2"]);
    if (!allowedTags.has(tag)) {
      throw _fail("Restoration family mismatch", "restoration_family_mismatch");
    }
  }
  const payload = value.payload;
  if (!_isPlainObject(payload)) {
    throw _fail("Restoration payload must be an object", "malformed_restoration_payload");
  }
  const normalizedPayload = canonicalizeContractNumeric(payload, { finiteErrorCode: "non_finite_materialization" });
  const expected = sha256Hex({ contract_version: tag, payload: normalizedPayload });
  if (value.digest !== expected) {
    throw _fail("Restoration digest mismatch", "restoration_digest_mismatch");
  }
  _validateRestorationPayload(tag, payload, family, forwardOps);
  return value;
}

function _validateRestorationPayload(tag, payload, family, forwardOps) {
  if (tag === "inverse_delta_v1" || tag === "inverse_delta_v2") {
    const isV2 = tag === "inverse_delta_v2";
    const allowed = new Set(["ops", "mutation_materialization", "mutation_materialization_digest"]);
    if (isV2) {
      allowed.add("forward_operation_digest");
      allowed.add("prior_link_witnesses");
    }
    const extras = Object.keys(payload).filter((k) => !allowed.has(k)).sort();
    if (extras.length > 0) {
      throw _fail(`${tag} payload has extra keys`, "malformed_restoration_payload");
    }
    const ops = payload.ops;
    if (!Array.isArray(ops)) {
      throw _fail(`${tag} payload requires ops`, "malformed_restoration_payload");
    }
    const envelope = normalizeDeltaEnvelope({ schema_version: DELTA_SCHEMA_VERSION, ops }, { strict: true });
    ensureRootScopedOps(envelope.ops);
    const hasAddNode = ops.some((o) => _isPlainObject(o) && o.op === "add_node");
    const hasMat = Object.prototype.hasOwnProperty.call(payload, "mutation_materialization");
    const hasMatDigest = Object.prototype.hasOwnProperty.call(payload, "mutation_materialization_digest");
    if (hasMat !== hasMatDigest) {
      throw _fail("mutation_materialization presence parity violated", "malformed_restoration_payload");
    }
    if (hasAddNode && !hasMat) {
      throw _fail("add_node inverse requires materialization", "malformed_restoration_payload");
    }
    if (!hasAddNode && hasMat) {
      throw _fail("materialization without add_node inverse", "malformed_restoration_payload");
    }
    if (hasMat) {
      const mat = payload.mutation_materialization;
      assertMutationMaterializationEnvelope(mat, { accompanyingOps: ops });
      if (payload.mutation_materialization_digest !== mat.digest) {
        throw _fail("mutation_materialization_digest mismatch", "restoration_digest_mismatch");
      }
    }
    let witnesses = null;
    if (isV2) {
      if (typeof payload.forward_operation_digest !== "string" || !_HEX64.test(payload.forward_operation_digest)) {
        throw _fail("forward_operation_digest must be hex64", "malformed_restoration_payload");
      }
      if (!Array.isArray(payload.prior_link_witnesses)) {
        throw _fail("prior_link_witnesses must be an array", "malformed_restoration_payload");
      }
      witnesses = payload.prior_link_witnesses;
      const witnessDestinations = new Set();
      for (const witness of witnesses) {
        if (!_isPlainObject(witness) || Object.keys(witness).sort().join(",") !== "from,to" ||
            !_rootEndpoint(witness.from) || !_rootEndpoint(witness.to)) {
          throw _fail("prior-link witness must be exactly {from,to} root endpoints", "malformed_restoration_payload");
        }
        const destination = JSON.stringify(witness.to);
        if (witnessDestinations.has(destination)) {
          throw _fail("duplicate prior-link witness destination", "malformed_restoration_payload");
        }
        witnessDestinations.add(destination);
      }
    }
    if (family !== null && forwardOps !== null) {
      if (isV2 && payload.forward_operation_digest !== forwardOperationDigest(forwardOps)) {
        throw _fail("forward_operation_digest mismatch", "forward_operation_digest_mismatch");
      }
      if (isV2) {
        const removeDestinations = new Set(
          forwardOps.filter((op) => _isPlainObject(op) && op.op === "remove_link")
            .map((op) => JSON.stringify(op.to)),
        );
        const witnessDestinations = new Set(witnesses.map((witness) => JSON.stringify(witness.to)));
        if (removeDestinations.size !== witnessDestinations.size ||
            [...removeDestinations].some((destination) => !witnessDestinations.has(destination))) {
          throw _fail("prior-link witnesses do not exactly cover forward remove_link ops", "inverse_missing_prior_state");
        }
      }
      assertInverseRelation(forwardOps, ops, family, { priorLinkWitnesses: witnesses });
    }
  } else if (tag === "inverse_layout_operation_v1") {
    const allowed = new Set(["layout_operation", "layout_operation_digest"]);
    const extras = Object.keys(payload).filter((k) => !allowed.has(k)).sort();
    if (extras.length > 0) {
      throw _fail("inverse_layout_operation_v1 payload has extra keys", "malformed_restoration_payload");
    }
    const layout = payload.layout_operation;
    if (!_isPlainObject(layout)) {
      throw _fail("inverse_layout_operation_v1 requires layout_operation", "malformed_restoration_payload");
    }
    assertLayoutOperationEnvelope(layout);
    if (payload.layout_operation_digest !== layout.digest) {
      throw _fail("layout_operation_digest mismatch", "restoration_digest_mismatch");
    }
  }
}

// ── Compensation slot (prepare-owned optional, §3.4) ────────────────────────

export function digestCompensation(value, authority) {
  if (!_isPlainObject(value)) {
    throw _fail("restoration_strategy_compensation must be an object", "malformed_restoration_compensation");
  }
  const extras = Object.keys(value).filter((k) => !["contract_version", "wire_version", "ref", "fence", "digest"].includes(k)).sort();
  if (extras.length > 0) {
    throw _fail("restoration_strategy_compensation has extra keys", "malformed_restoration_compensation");
  }
  if (value.contract_version !== RESTORATION_COMPENSATION_CONTRACT_V1) {
    throw _fail("compensation must use baseline_snapshot_v1", "unknown_restoration_strategy");
  }
  if (value.wire_version !== RESTORATION_COMPENSATION_WIRE_VERSION) {
    throw _fail("compensation wire version mismatch", "unsupported_wire_version");
  }
  const ref = value.ref;
  if (typeof ref !== "string" || ref.length === 0) {
    throw _fail("compensation ref must be a non-empty string", "malformed_restoration_compensation");
  }
  const fence = value.fence;
  if (!_isPlainObject(fence)) {
    throw _fail("compensation fence must be an object", "malformed_restoration_compensation");
  }
  const fenceExtras = Object.keys(fence).filter((k) => !_FENCE_KEYS.has(k)).sort();
  const fenceMissing = [..._FENCE_KEYS].filter((k) => !Object.prototype.hasOwnProperty.call(fence, k)).sort();
  if (fenceExtras.length > 0 || fenceMissing.length > 0) {
    throw _fail("compensation fence key set is not closed", "malformed_restoration_compensation");
  }
  if (!Number.isInteger(fence.generation) || fence.generation <= 0) {
    throw _fail("compensation generation must be a positive int", "malformed_restoration_compensation");
  }
  for (const key of ["transaction_id", "candidate_id", "plan_hash", "lease_nonce"]) {
    if (typeof fence[key] !== "string" || fence[key].length === 0) {
      throw _fail(`compensation fence ${key} must be non-empty string`, "malformed_restoration_compensation");
    }
  }
  for (const key of ["pre_projection_digest", "post_projection_digest"]) {
    if (typeof fence[key] !== "string" || !_HEX64.test(fence[key])) {
      throw _fail(`compensation fence ${key} must be hex64`, "malformed_restoration_compensation");
    }
  }
  // Fence binding: every value must equal the enclosing prepared authority.
  const precondition = _isPlainObject(authority.precondition) ? authority.precondition : {};
  const postcondition = _isPlainObject(authority.postcondition) ? authority.postcondition : {};
  const bindings = {
    transaction_id: authority.transaction_id,
    candidate_id: authority.candidate_id,
    plan_hash: authority.plan_hash,
    lease_nonce: authority.lease_nonce,
    generation: authority.generation,
    pre_projection_digest: precondition.digest,
    post_projection_digest: postcondition.digest,
  };
  for (const [key, expected] of Object.entries(bindings)) {
    if (fence[key] !== expected) {
      throw _fail("compensation fence is not bound to this authority", "compensation_fence_unbound");
    }
  }
  // Digest (separate from restoration_strategy.digest).
  const normalizedFence = canonicalizeContractNumeric(fence, { finiteErrorCode: "non_finite_materialization" });
  const expectedDigest = sha256Hex({
    contract_version: RESTORATION_COMPENSATION_CONTRACT_V1,
    wire_version: RESTORATION_COMPENSATION_WIRE_VERSION,
    ref,
    fence: normalizedFence,
  });
  if (typeof value.digest !== "string" || value.digest !== expectedDigest) {
    throw _fail("compensation digest mismatch", "compensation_digest_mismatch");
  }
  return value;
}

export function assertRestorationStrategyCompensation(value, authority) {
  return digestCompensation(value, authority);
}

// ── Sole durable Δ: plan.accepted_batch + operation.accepted_batch_digest ────
//
// Forward ops are derived from plan.accepted_batch[*].op. operation.ops is a
// deleted durable copy and is rejected on current envelopes.

export function forwardOpsFromAcceptedBatch(acceptedBatch) {
  if (!Array.isArray(acceptedBatch)) return [];
  const ops = [];
  for (const statement of acceptedBatch) {
    if (_isPlainObject(statement) && _isPlainObject(statement.op)) {
      ops.push(statement.op);
    }
  }
  return ops;
}

export function acceptedBatchDigest(acceptedBatch) {
  return sha256Hex({
    schema_version: "2.0.0",
    ops: forwardOpsFromAcceptedBatch(acceptedBatch),
  });
}

// ── Family contract binding (§1.5 / §2.5) ────────────────────────────────────

function _bindFamilyContracts(raw, family, forwardOps) {
  const operation = raw.operation;
  const ops = Array.isArray(forwardOps) ? forwardOps : [];
  if (family === "layout") {
    if (ops.length > 0) {
      throw _fail("Layout family requires empty structural ops", "layout_family_requires_empty_structural_ops");
    }
    const layout = operation.layout_operation;
    if (layout === undefined || layout === null) {
      throw _fail("Layout family requires layout_operation", "missing_layout_operation");
    }
    assertLayoutOperationEnvelope(layout);
    if (operation.layout_operation_digest !== layout.digest) {
      throw _fail("layout_operation_digest mismatch", "layout_operation_digest_mismatch");
    }
    if (Object.prototype.hasOwnProperty.call(operation, "mutation_materialization")) {
      throw _fail("Layout family must not carry mutation_materialization", "unexpected_materialization");
    }
  } else { // structural
    if (Object.prototype.hasOwnProperty.call(operation, "layout_operation")) {
      throw _fail("Structural family must not carry layout_operation", "unexpected_layout_operation");
    }
    const hasAddNode = (Array.isArray(ops) ? ops : []).some((o) => _isPlainObject(o) && o.op === "add_node");
    const hasMat = Object.prototype.hasOwnProperty.call(operation, "mutation_materialization");
    if (hasAddNode && !hasMat) {
      throw _fail("Structural family with add_node requires mutation_materialization", "missing_materialization");
    }
    if (!hasAddNode && hasMat) {
      throw _fail("Structural family without add_node must not carry mutation_materialization", "unexpected_materialization");
    }
    if (hasMat) {
      const mat = operation.mutation_materialization;
      assertMutationMaterializationEnvelope(mat, { accompanyingOps: ops });
      if (operation.mutation_materialization_digest !== mat.digest) {
        throw _fail("mutation_materialization_digest mismatch", "mutation_materialization_digest_mismatch");
      }
    }
  }
}

// ── Common authority validator ───────────────────────────────────────────────

function validateAuthorityCommon(raw, contract, options = {}) {
  if (!raw || raw.contract_version !== contract) { throw _fail("Unsupported authority version.", "unknown_authority_version"); }
  ["transaction_id", "candidate_id", "session_id", "turn_id", "plan_hash"].forEach((key) => issuedIdentityV1(raw[key], key)); workflowIdentityV1(raw.workflow_id); assertRootScopeV1(raw.scope);
  if (raw.authority_receipt_contract_version !== AUTHORITY_RECEIPT_CONTRACT_VERSION) { throw _fail("Authority receipt contract version must be explicit.", "unknown_authority_receipt_version"); }
  if (raw.authority_receipt_delta_schema !== DELTA_SCHEMA_VERSION) { throw _fail("Authority receipt delta schema must match delta_v1.", "authority_receipt_delta_schema_mismatch"); }
  if (typeof raw.authority_receipt_digest !== "string" || !/^[0-9a-f]{64}$/.test(raw.authority_receipt_digest)) { throw _fail("Authority receipt digest must be exact lowercase SHA-256.", "invalid_authority_receipt_digest"); }
  const operation = raw.operation;
  if (!operation || operation.delta_contract !== "delta_v1" || operation.wire_version !== DELTA_SCHEMA_VERSION) { throw _fail("Operation must explicitly bind delta_v1 to wire 2.0.0.", "invalid_delta_contract"); }
  if (Object.prototype.hasOwnProperty.call(operation, "ops")) { throw _fail("operation must not persist ops; accepted_batch is the durable Δ", "durable_delta_ops_copy"); }
  const batchDigest = operation.accepted_batch_digest;
  if (typeof batchDigest !== "string" || !_HEX64.test(batchDigest)) { throw _fail("Operation must reference accepted_batch by digest", "invalid_delta_contract"); }
  const accepted_batch = options.accepted_batch;
  const forwardOps = forwardOpsFromAcceptedBatch(accepted_batch);
  if (accepted_batch !== undefined && accepted_batch !== null) {
    if (batchDigest !== acceptedBatchDigest(accepted_batch)) { throw _fail("accepted_batch_digest does not match plan.accepted_batch", "accepted_batch_digest_mismatch"); }
    const envelope = normalizeDeltaEnvelope({ schema_version: operation.wire_version, ops: forwardOps }, { strict: true }); ensureRootScopedOps(envelope.ops);
  }
  if (!["structural", "layout"].includes(raw.operation_family)) { throw _fail("Unknown operation family.", "unknown_operation_family"); }
  const expected = raw.operation_family === "layout" ? "layout_v1" : "structural_v1"; assertForwardProjectionV1(expected); assertProjectionReferenceV1(raw.precondition, { expected }); assertProjectionReferenceV1(raw.postcondition, { expected });
  if (raw.rollback_projection !== expected) { throw _fail("Rollback projection must equal forward projection family.", "rollback_projection_mismatch"); }
  if (raw.operation_family === "layout") { const structural = raw.structural_witness; assertProjectionReferenceV1(structural, { expected: "structural_v1" }); if (structural.precondition_digest !== structural.postcondition_digest) { throw _fail("Layout requires structural no-op witness.", "layout_structural_witness_mismatch"); } }
  _bindFamilyContracts(raw, raw.operation_family, forwardOps);
  digest(raw.restoration_strategy, { family: raw.operation_family, forwardOps });
  // Prepare-owned optional compensation slot: validated only on prepared authority.
  if (Object.prototype.hasOwnProperty.call(raw, "restoration_strategy_compensation") && raw.contract_version === PREPARED_AUTHORITY_V1) {
    digestCompensation(raw.restoration_strategy_compensation, raw);
  }
  return raw;
}

export function validateCandidateAuthorityV1(raw, options = {}) {
  validateAuthorityCommon(raw, CANDIDATE_AUTHORITY_V1, options);
  if (Object.hasOwn(raw, "generation") || Object.hasOwn(raw, "lease_nonce")) { throw _fail("Candidate authority cannot infer prepare identity.", "unexpected_prepare_identity"); }
  if (Object.hasOwn(raw, "restoration_strategy_compensation")) { throw _fail("Candidate authority may not carry restoration_strategy_compensation.", "candidate_compensation_forbidden"); }
  return freeze(clone({ ...raw, operation: { ...raw.operation } }));
}

export function validatePreparedAuthorityV1(raw, options = {}) {
  validateAuthorityCommon(raw, PREPARED_AUTHORITY_V1, options);
  issuedIdentityV1(raw.lease_nonce, "lease_nonce");
  if (!Number.isInteger(raw.generation) || raw.generation <= 0) { throw _fail("generation must be positive.", "invalid_generation"); }
  return freeze(clone({ ...raw, operation: { ...raw.operation } }));
}

// Transition-equality key set (§6.5): every standard key is deep-compared.
// restoration_strategy_compensation is the sole prepare-owned additive key.
const _TRANSITION_KEYS = [
  "transaction_id", "candidate_id", "session_id", "turn_id", "plan_hash", "workflow_id",
  "scope", "operation", "operation_family", "precondition", "postcondition",
  "rollback_projection", "restoration_strategy", "authority_receipt_contract_version",
  "authority_receipt_delta_schema", "authority_receipt_digest",
];

export function validateCandidateTransactionV2(value) {
  if (!value || value.contract_version !== CANDIDATE_TRANSACTION_V2) { throw _fail("Unsupported candidate transaction version.", "unsupported_candidate_transaction"); }
  if (!value.candidate_authority) { throw _fail("candidate_transaction_v2 requires candidate_authority_v1.", "missing_candidate_authority"); }
  const accepted_batch = _isPlainObject(value.plan) ? value.plan.accepted_batch : undefined;
  const candidate = validateCandidateAuthorityV1(value.candidate_authority, { accepted_batch });
  const preparedStates = new Set(["prepared", "canvas_verified", "finalized", "rollback_complete", "superseded"]);
  if (["candidate_ready", "recoverable_error", "discarded"].includes(value.state)) { if (value.prepared_authority != null) { throw _fail("Unprepared transaction carries prepared authority.", "unexpected_prepared_authority"); } return candidate; }
  if (!preparedStates.has(value.state)) { throw _fail("Unknown candidate transaction state.", "invalid_candidate_transaction_state"); }
  const prepared = validatePreparedAuthorityV1(value.prepared_authority, { accepted_batch });
  for (const key of _TRANSITION_KEYS) {
    if (JSON.stringify(prepared[key]) !== JSON.stringify(candidate[key])) {
      throw _fail("Prepared authority changed candidate-time authority.", "prepared_authority_transition_mismatch");
    }
  }
  // restoration_strategy_compensation: sole prepare-owned additive key.
  // Candidate presence is forbidden (caught above); prepared absence is legal;
  // prepared presence must be a valid envelope (validated by validatePreparedAuthorityV1).
  const candidateHasComp = Object.prototype.hasOwnProperty.call(candidate, "restoration_strategy_compensation");
  const preparedHasComp = Object.prototype.hasOwnProperty.call(prepared, "restoration_strategy_compensation");
  if (candidateHasComp) {
    throw _fail("Candidate authority carries restoration_strategy_compensation.", "candidate_compensation_forbidden");
  }
  if (preparedHasComp && prepared.restoration_strategy_compensation === null) {
    throw _fail("restoration_strategy_compensation may not be null.", "malformed_restoration_compensation");
  }
  return prepared;
}

// ── §M1.6: Legacy persisted authority migration ─────────────────────────────
//
// Sole load-boundary upgrade from a `candidate_authority_v0_legacy` persisted
// envelope to a strict `candidate_authority_v1`. The legacy era did not bind
// `restoration_strategy.digest`; the migrator recomputes it from the actual
// payload/ref so the resulting v1 passes `validateCandidateAuthorityV1`
// byte-for-byte. No other field is reinterpreted, stripped, or defaulted —
// every remaining field is subsequently bound by the strict validator.
//
// Hard rules (these are what keep v2 fail-closed validation intact):
//   * Only an explicit `candidate_authority_v0_legacy` marker enters this path.
//   * A malformed legacy shape (missing/typed restoration_strategy, unknown
//     restoration tag, non-object inverse payload, non-string ref) throws — it
//     is NOT rehabilitated. The caller treats a throw as fail-closed.
//   * Malformed current v1/v2 authorities never carry the v0_legacy marker, so
//     they cannot reach this code; they fail-closed in the strict validator.

function _recomputeRestorationDigestLegacy(restoration) {
  const tag = restoration.contract_version;
  if (!LEGACY_RESTORATION_STRATEGY_TAGS.has(tag)) {
    throw _fail("Legacy restoration_strategy carries an unknown tag.", "unknown_restoration_strategy");
  }
  const hasPayload = Object.prototype.hasOwnProperty.call(restoration, "payload");
  const hasRef = Object.prototype.hasOwnProperty.call(restoration, "ref");
  if (hasPayload && hasRef) {
    throw _fail("Legacy restoration payload and ref are mutually exclusive.", "malformed_legacy_authority");
  }
  if (!hasPayload && !hasRef) {
    throw _fail("Legacy restoration requires payload or ref.", "malformed_legacy_authority");
  }
  if (tag === "baseline_snapshot_v1") {
    if (!hasRef) {
      throw _fail("Legacy baseline_snapshot_v1 restoration must use ref.", "malformed_legacy_authority");
    }
    if (typeof restoration.ref !== "string" || restoration.ref.length === 0) {
      throw _fail("Legacy baseline_snapshot_v1 ref must be a non-empty string.", "malformed_legacy_authority");
    }
    return sha256Hex({ contract_version: tag, ref: restoration.ref });
  }
  // inverse_delta_v1 / inverse_layout_operation_v1 carry a payload object.
  if (!hasPayload) {
    throw _fail("Legacy inverse restoration must use payload.", "malformed_legacy_authority");
  }
  if (!_isPlainObject(restoration.payload)) {
    throw _fail("Legacy inverse restoration payload must be an object.", "malformed_legacy_authority");
  }
  const normalizedPayload = canonicalizeContractNumeric(restoration.payload, {
    finiteErrorCode: "non_finite_materialization",
  });
  return sha256Hex({ contract_version: tag, payload: normalizedPayload });
}

export function migrateLegacyCandidateAuthorityV0Legacy(raw) {
  if (!_isPlainObject(raw)) {
    throw _fail("Legacy authority must be an object.", "malformed_legacy_authority");
  }
  if (raw.contract_version !== CANDIDATE_AUTHORITY_V0_LEGACY) {
    throw _fail("Not a candidate_authority_v0_legacy envelope.", "unknown_authority_version");
  }
  const restoration = raw.restoration_strategy;
  if (!_isPlainObject(restoration)) {
    throw _fail("Legacy authority requires a restoration_strategy object.", "malformed_legacy_authority");
  }
  const recomputedDigest = _recomputeRestorationDigestLegacy(restoration);
  // Shallow-clone so a frozen persisted fixture is never mutated in place; the
  // only mutation is the contract_version upgrade and the digest recomputation.
  return {
    ...raw,
    contract_version: CANDIDATE_AUTHORITY_V1,
    restoration_strategy: { ...restoration, digest: recomputedDigest },
  };
}
