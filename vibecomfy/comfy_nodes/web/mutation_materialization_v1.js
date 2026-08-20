// mutation_materialization_v1.js — bound add_node construction payload (JS owner)
//
// A materialization envelope accompanies ONE delta envelope — either the
// forward ops derived from plan.accepted_batch or an inverse
// restoration_strategy.payload.ops. Each entry binds exactly one add_node op
// in that accompanying envelope and carries only native construction data
// NOT already authoritative in the op.
//
// Envelope (frozen, identical JS + Python):
//   { contract_version, wire_version, entries: [...], digest }
//
// Entry (closed keys; widgets_values/pos/size/opaque optional):
//   { source_op_index, kind: "add_node", widgets_values?, pos?, size?, opaque? }
//
// No implicit links, no candidate-graph source, no remove_node_inverse kind.
//
// digest folds in sha256Hex(accompanyingOps) so re-binding is detectable:
//   digest = sha256Hex({ contract_version, wire_version,
//                        entries: <sorted by source_op_index>,
//                        accompanying_ops_digest: sha256Hex(accompanyingOps) })
//
// Hashing identity is the shared leaf canonical_hash.js (sha256Hex).  No second
// hash owner.

import { sha256Hex, canonicalizeContractNumeric } from "./canonical_hash.js";

export const MUTATION_MATERIALIZATION_CONTRACT_V1 = "mutation_materialization_v1";
export const MUTATION_MATERIALIZATION_WIRE_VERSION = "1.0.0";
export const MATERIALIZATION_KINDS = Object.freeze(["add_node"]);

const _ENVELOPE_KEYS = new Set(["contract_version", "wire_version", "entries", "digest"]);
const _ENTRY_KEYS = new Set(["source_op_index", "kind", "widgets_values", "pos", "size", "opaque"]);
const _FORBIDDEN_ENTRY_KEYS = new Set(["links", "inputs", "fields", "uid", "node_id", "class_type"]);

export class MutationMaterializationError extends Error {
  constructor(message, code, detail = {}) {
    super(message);
    this.name = "MutationMaterializationError";
    this.code = code || "malformed_materialization";
    this.detail = detail || {};
  }
}

function _fail(message, code, detail = {}) {
  return new MutationMaterializationError(message, code, detail);
}

function _isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function _cloneJsonish(value) {
  if (Array.isArray(value)) return value.map(_cloneJsonish);
  if (_isPlainObject(value)) {
    const result = {};
    for (const [key, entry] of Object.entries(value)) result[key] = _cloneJsonish(entry);
    return result;
  }
  return value;
}

function _geoVector(value, length, field) {
  let normalized;
  try {
    normalized = canonicalizeContractNumeric(value, { finiteErrorCode: "non_finite_materialization" });
  } catch (error) {
    throw _fail(error.message || "Non-finite numeric value", error.code || "non_finite_materialization", { field });
  }
  if (!Array.isArray(normalized) || normalized.length !== length) {
    throw _fail(`${field} must be a list of ${length} finite numbers`, "malformed_materialization_entry", { field });
  }
  for (const component of normalized) {
    if (typeof component !== "number") {
      throw _fail(`${field} must contain finite numbers`, "malformed_materialization_entry", { field });
    }
  }
  return normalized;
}

function _normalizeEntry(raw) {
  if (!_isPlainObject(raw)) {
    throw _fail("materialization entry must be an object", "malformed_materialization_entry");
  }
  const keys = Object.keys(raw);
  const forbidden = keys.filter((k) => _FORBIDDEN_ENTRY_KEYS.has(k)).sort();
  if (forbidden.length > 0) {
    throw _fail(`materialization entry carries forbidden key(s): ${forbidden.join(", ")}`, "malformed_materialization_entry", { keys: forbidden });
  }
  const extras = keys.filter((k) => !_ENTRY_KEYS.has(k)).sort();
  if (extras.length > 0) {
    throw _fail(`Unknown materialization entry key(s): ${extras.join(", ")}`, "malformed_materialization_entry", { keys: extras });
  }
  if (!Object.prototype.hasOwnProperty.call(raw, "source_op_index")) {
    throw _fail("materialization entry requires source_op_index", "malformed_materialization_entry", { field: "source_op_index" });
  }
  if (!MATERIALIZATION_KINDS.includes(raw.kind)) {
    throw _fail(`Unsupported materialization kind ${JSON.stringify(raw.kind)}`, "unsupported_materialization_kind", { kind: raw.kind });
  }
  const result = { source_op_index: raw.source_op_index, kind: "add_node" };
  if (Object.prototype.hasOwnProperty.call(raw, "widgets_values")) {
    const wv = raw.widgets_values;
    if (wv === null) {
      throw _fail("widgets_values may not be null (absent or a value)", "malformed_materialization_entry", { field: "widgets_values" });
    }
    if (!Array.isArray(wv) && !_isPlainObject(wv)) {
      throw _fail("widgets_values must be an array (or object for vibecomfy.exec)", "malformed_materialization_entry", { field: "widgets_values" });
    }
    result.widgets_values = _cloneJsonish(wv);
  }
  if (Object.prototype.hasOwnProperty.call(raw, "pos") && raw.pos != null) {
    result.pos = _geoVector(raw.pos, 2, "pos");
  }
  if (Object.prototype.hasOwnProperty.call(raw, "size") && raw.size != null) {
    result.size = _geoVector(raw.size, 2, "size");
  }
  if (Object.prototype.hasOwnProperty.call(raw, "opaque") && raw.opaque != null) {
    if (!_isPlainObject(raw.opaque)) {
      throw _fail("opaque must be a JSON object", "malformed_materialization_entry", { field: "opaque" });
    }
    result.opaque = _cloneJsonish(raw.opaque);
  }
  return result;
}

function _normalizeEntries(rawEntries) {
  if (!Array.isArray(rawEntries)) {
    throw _fail("materialization entries must be an array", "malformed_materialization");
  }
  return rawEntries.map(_normalizeEntry);
}

function _accompanyingOpsDigest(accompanyingOps) {
  let normalizedOps;
  try {
    normalizedOps = canonicalizeContractNumeric(accompanyingOps, {
      finiteErrorCode: "non_finite_materialization",
      allowBool: true,
    });
  } catch (error) {
    throw _fail(error.message || "Non-finite numeric value", error.code || "non_finite_materialization");
  }
  return sha256Hex(normalizedOps);
}

export function computeMutationMaterializationDigest(entries, accompanyingOps) {
  const normalizedEntries = _normalizeEntries(entries);
  const preimage = {
    contract_version: MUTATION_MATERIALIZATION_CONTRACT_V1,
    wire_version: MUTATION_MATERIALIZATION_WIRE_VERSION,
    entries: normalizedEntries.slice().sort((a, b) => a.source_op_index - b.source_op_index),
    accompanying_ops_digest: _accompanyingOpsDigest(accompanyingOps),
  };
  return sha256Hex(preimage);
}

export function normalizeMutationMaterializationV1(envelope, { accompanyingOps } = {}) {
  if (!_isPlainObject(envelope)) {
    throw _fail("materialization envelope must be an object", "malformed_materialization");
  }
  const extras = Object.keys(envelope).filter((k) => !_ENVELOPE_KEYS.has(k)).sort();
  if (extras.length > 0) {
    throw _fail(`Unknown materialization envelope key(s): ${extras.join(", ")}`, "malformed_materialization", { keys: extras });
  }
  if (envelope.contract_version !== MUTATION_MATERIALIZATION_CONTRACT_V1) {
    throw _fail("Unknown materialization contract version", "unknown_contract");
  }
  if (envelope.wire_version !== MUTATION_MATERIALIZATION_WIRE_VERSION) {
    throw _fail("Unsupported materialization wire version", "unsupported_wire_version");
  }
  const normalizedEntries = _normalizeEntries(envelope.entries);
  const preimage = {
    contract_version: MUTATION_MATERIALIZATION_CONTRACT_V1,
    wire_version: MUTATION_MATERIALIZATION_WIRE_VERSION,
    entries: normalizedEntries.slice().sort((a, b) => a.source_op_index - b.source_op_index),
    accompanying_ops_digest: _accompanyingOpsDigest(accompanyingOps),
  };
  return Object.freeze({
    contract_version: MUTATION_MATERIALIZATION_CONTRACT_V1,
    wire_version: MUTATION_MATERIALIZATION_WIRE_VERSION,
    entries: Object.freeze(preimage.entries),
    digest: sha256Hex(preimage),
  });
}

function _validateAccompanyingOps(accompanyingOps) {
  if (!Array.isArray(accompanyingOps) || accompanyingOps.length === 0) {
    throw _fail("accompanyingOps must be a non-empty array of canonical delta ops", "malformed_materialization");
  }
  for (const item of accompanyingOps) {
    if (!_isPlainObject(item) || typeof item.op !== "string") {
      throw _fail("accompanyingOps must be canonical delta ops", "malformed_materialization");
    }
  }
  return accompanyingOps;
}

export function assertMutationMaterializationEnvelope(envelope, { accompanyingOps } = {}) {
  const ops = _validateAccompanyingOps(accompanyingOps);
  const normalized = normalizeMutationMaterializationV1(envelope, { accompanyingOps });
  const entries = normalized.entries;

  const addNodeIndices = new Set();
  ops.forEach((op, i) => { if (op.op === "add_node") addNodeIndices.add(i); });

  // Collision detection (Gate #2 / §2.4).
  const indexCounts = new Map();
  for (const entry of entries) {
    indexCounts.set(entry.source_op_index, (indexCounts.get(entry.source_op_index) || 0) + 1);
  }
  for (const [value, count] of [...indexCounts.entries()].sort((a, b) => Number(a[0]) - Number(b[0]))) {
    if (count < 2) continue;
    if (addNodeIndices.has(value)) {
      throw _fail(`Surplus materialization entry for add_node at index ${value}`, "unreferenced_materialization_entry", { source_op_index: value });
    }
    throw _fail(`Duplicate materialization source_op_index ${value}`, "duplicate_materialization_source_op", { source_op_index: value });
  }

  // Range + kind + widgets_values class-type pin per entry.
  for (const entry of entries) {
    const idx = entry.source_op_index;
    if (!Number.isInteger(idx) || idx < 0 || idx >= ops.length) {
      throw _fail(`materialization source_op_index ${idx} out of range`, "materialization_source_op_index_out_of_range", { source_op_index: idx });
    }
    const op = ops[idx];
    if (op.op !== "add_node") {
      throw _fail(`materialization source_op_index ${idx} is not an add_node`, "materialization_source_op_kind_mismatch", { source_op_index: idx, op_kind: op.op });
    }
    if (Object.prototype.hasOwnProperty.call(entry, "widgets_values")) {
      const classType = op.class_type;
      const wv = entry.widgets_values;
      if (classType === "vibecomfy.exec") {
        if (!Array.isArray(wv) && !_isPlainObject(wv)) {
          throw _fail("vibecomfy.exec widgets_values must be array or object", "malformed_materialization_entry", { field: "widgets_values" });
        }
      } else if (!Array.isArray(wv)) {
        throw _fail("widgets_values must be an array for non-vibecomfy.exec nodes", "malformed_materialization_entry", { field: "widgets_values" });
      }
    }
  }

  // Coverage.
  const entryIndices = new Set(entries.map((e) => e.source_op_index));
  for (const index of [...addNodeIndices].sort((a, b) => a - b)) {
    if (!entryIndices.has(index)) {
      throw _fail(`add_node at index ${index} has no materialization entry`, "missing_materialization_entry", { source_op_index: index });
    }
  }

  // Digest.
  const claimed = _isPlainObject(envelope) ? envelope.digest : undefined;
  if (claimed !== normalized.digest) {
    throw _fail("mutation materialization digest mismatch", "mutation_materialization_digest_mismatch", { accompanying_ops_bound: true });
  }
  return normalized;
}

export default {
  MUTATION_MATERIALIZATION_CONTRACT_V1,
  MUTATION_MATERIALIZATION_WIRE_VERSION,
  MATERIALIZATION_KINDS,
  MutationMaterializationError,
  computeMutationMaterializationDigest,
  normalizeMutationMaterializationV1,
  assertMutationMaterializationEnvelope,
};
