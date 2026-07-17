// layout_operation_v1.js — closed four-op layout grammar (JS owner)
//
// Cross-language contract for root-scoped, stable-ID-only layout operations.
// Identity is NEVER title, native id, position, class, or array index: it is
// the stable `uid` (nodes) / `id` (groups).  Duplicate titles are valid and
// remain distinct.
//
// Envelope (frozen, identical JS + Python):
//   {
//     contract_version: "layout_operation_v1",
//     wire_version: "1.0.0",
//     ops: [ <LayoutOp>, ... ],
//     digest: "<64-hex>"
//   }
//
// The four ops form a closed grammar:
//   set_node_geometry  — {op, uid, pos} (size optional)
//   add_group          — {op, id, bounding, title, color}
//   set_group_geometry — {op, id} plus >=1 changed value from the add_group
//                        field set (bounding / title / color)
//   remove_group       — {op, id}
//
// Every numeric component of pos / size / bounding is normalised through
// `canonicalizeContractNumeric` (finite error code "non_finite_geometry")
// before any geometry check.  Hashing identity is the shared leaf
// `canonical_hash.js` (`sha256Hex`).  No second hash owner, no second
// canonicaliser.

import {
  sha256Hex,
  canonicalizeContractNumeric,
} from "./canonical_hash.js";

export const LAYOUT_OPERATION_CONTRACT_V1 = "layout_operation_v1";
export const LAYOUT_OPERATION_WIRE_VERSION = "1.0.0";
export const LAYOUT_OPERATION_OP_NAMES = Object.freeze([
  "set_node_geometry",
  "add_group",
  "set_group_geometry",
  "remove_group",
]);

const _ENVELOPE_KEYS = new Set([
  "contract_version",
  "wire_version",
  "ops",
  "digest",
]);

const _SET_NODE_GEOMETRY_KEYS = new Set(["op", "uid", "pos", "size"]);
const _ADD_GROUP_KEYS = new Set(["op", "id", "bounding", "title", "color"]);
const _SET_GROUP_GEOMETRY_KEYS = new Set([
  "op",
  "id",
  "bounding",
  "title",
  "color",
]);
const _REMOVE_GROUP_KEYS = new Set(["op", "id"]);
const _GROUP_CHANGEABLE_KEYS = ["bounding", "title", "color"];

export class LayoutOperationError extends Error {
  constructor(message, code, detail = {}) {
    super(message);
    this.name = "LayoutOperationError";
    this.code = code || "malformed_layout_operation";
    this.detail = detail || {};
  }
}

function _fail(message, code, detail = {}) {
  return new LayoutOperationError(message, code, detail);
}

function _isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function _isNonEmptyString(value) {
  return typeof value === "string" && value.length > 0;
}

function _requireNonEmptyStr(value, name) {
  if (!_isNonEmptyString(value)) {
    throw _fail(`Missing stable ${name}`, "missing_identity", { field: name });
  }
  return value;
}

function _geometryVector(value, length, field) {
  let normalized;
  try {
    normalized = canonicalizeContractNumeric(value, {
      finiteErrorCode: "non_finite_geometry",
    });
  } catch (error) {
    // The shared normaliser throws a base Error carrying the diagnostic code;
    // surface it as this module's typed error with the same code.
    throw _fail(error.message || "Non-finite numeric value", error.code || "non_finite_geometry", { field });
  }
  if (!Array.isArray(normalized) || normalized.length !== length) {
    throw _fail(`${field} must be a list of ${length} finite numbers`, "malformed_layout_op", { field });
  }
  for (const component of normalized) {
    if (typeof component !== "number") {
      throw _fail(`${field} must contain finite numbers`, "malformed_layout_op", { field });
    }
  }
  return normalized;
}

function _rejectUnknownKeys(raw, allowed, opName) {
  const extras = Object.keys(raw)
    .filter((key) => !allowed.has(key))
    .sort();
  if (extras.length > 0) {
    throw _fail(`Unknown layout op key(s): ${extras.join(", ")}`, "malformed_layout_op", {
      keys: extras,
      op: opName,
    });
  }
}

function _normalizeLayoutOp(raw) {
  if (!_isPlainObject(raw)) {
    throw _fail("layout op must be an object", "malformed_layout_op");
  }
  const opName = raw.op;
  if (!_isNonEmptyString(opName)) {
    throw _fail('layout op must have a non-empty string "op"', "malformed_layout_op");
  }
  if (!LAYOUT_OPERATION_OP_NAMES.includes(opName)) {
    throw _fail(`Unsupported layout op "${opName}"`, "unsupported_layout_op", { op: opName });
  }

  if (opName === "set_node_geometry") {
    _rejectUnknownKeys(raw, _SET_NODE_GEOMETRY_KEYS, opName);
    const uid = _requireNonEmptyStr(raw.uid, "node uid");
    const pos = _geometryVector(raw.pos, 2, "pos");
    const result = { op: opName, uid, pos };
    if (Object.prototype.hasOwnProperty.call(raw, "size") && raw.size != null) {
      result.size = _geometryVector(raw.size, 2, "size");
    }
    return result;
  }

  if (opName === "add_group") {
    _rejectUnknownKeys(raw, _ADD_GROUP_KEYS, opName);
    const id = _requireNonEmptyStr(raw.id, "group id");
    const bounding = _geometryVector(raw.bounding, 4, "bounding");
    if (typeof raw.title !== "string") {
      throw _fail("add_group title must be a string", "malformed_layout_op", { field: "title" });
    }
    if (raw.color != null && typeof raw.color !== "string") {
      throw _fail("add_group color must be a string or null", "malformed_layout_op", { field: "color" });
    }
    return { op: opName, id, bounding, title: raw.title, color: raw.color ?? null };
  }

  if (opName === "set_group_geometry") {
    _rejectUnknownKeys(raw, _SET_GROUP_GEOMETRY_KEYS, opName);
    const id = _requireNonEmptyStr(raw.id, "group id");
    const changed = _GROUP_CHANGEABLE_KEYS.filter((key) => Object.prototype.hasOwnProperty.call(raw, key));
    if (changed.length === 0) {
      throw _fail(
        "set_group_geometry must change at least one of bounding/title/color",
        "malformed_layout_op",
      );
    }
    const result = { op: opName, id };
    if (Object.prototype.hasOwnProperty.call(raw, "bounding")) {
      result.bounding = _geometryVector(raw.bounding, 4, "bounding");
    }
    if (Object.prototype.hasOwnProperty.call(raw, "title")) {
      if (typeof raw.title !== "string") {
        throw _fail("set_group_geometry title must be a string", "malformed_layout_op", { field: "title" });
      }
      result.title = raw.title;
    }
    if (Object.prototype.hasOwnProperty.call(raw, "color")) {
      if (raw.color != null && typeof raw.color !== "string") {
        throw _fail("set_group_geometry color must be a string or null", "malformed_layout_op", { field: "color" });
      }
      result.color = raw.color ?? null;
    }
    return result;
  }

  // remove_group
  _rejectUnknownKeys(raw, _REMOVE_GROUP_KEYS, opName);
  const id = _requireNonEmptyStr(raw.id, "group id");
  return { op: opName, id };
}

function _identityForOp(normalized) {
  return normalized.op === "set_node_geometry" ? normalized.uid : normalized.id;
}

function _normalizeOps(rawOps) {
  if (!Array.isArray(rawOps)) {
    throw _fail("layout ops must be an array", "malformed_layout_operation");
  }
  const normalizedOps = rawOps.map((op) => _normalizeLayoutOp(op));
  const seen = new Set();
  for (const op of normalizedOps) {
    const key = `${op.op}\u0000${_identityForOp(op)}`;
    if (seen.has(key)) {
      throw _fail(`Duplicate layout identity for op ${JSON.stringify(op.op)}`, "duplicate_identity", {
        op: op.op,
        identity: _identityForOp(op),
      });
    }
    seen.add(key);
  }
  return normalizedOps;
}

export function computeLayoutOperationDigest(ops) {
  const normalizedOps = _normalizeOps(ops);
  return sha256Hex({
    contract_version: LAYOUT_OPERATION_CONTRACT_V1,
    wire_version: LAYOUT_OPERATION_WIRE_VERSION,
    ops: normalizedOps,
  });
}

export function normalizeLayoutOperationV1(envelope) {
  if (!_isPlainObject(envelope)) {
    throw _fail("layout operation envelope must be an object", "malformed_layout_operation");
  }
  const extras = Object.keys(envelope)
    .filter((key) => !_ENVELOPE_KEYS.has(key))
    .sort();
  if (extras.length > 0) {
    throw _fail(`Unknown layout operation envelope key(s): ${extras.join(", ")}`, "malformed_layout_operation", { keys: extras });
  }
  if (envelope.contract_version !== LAYOUT_OPERATION_CONTRACT_V1) {
    throw _fail("Unknown layout operation contract version", "unknown_contract");
  }
  if (envelope.wire_version !== LAYOUT_OPERATION_WIRE_VERSION) {
    throw _fail("Unsupported layout operation wire version", "unsupported_wire_version");
  }
  const normalizedOps = _normalizeOps(envelope.ops);
  const digest = sha256Hex({
    contract_version: LAYOUT_OPERATION_CONTRACT_V1,
    wire_version: LAYOUT_OPERATION_WIRE_VERSION,
    ops: normalizedOps,
  });
  return Object.freeze({
    contract_version: LAYOUT_OPERATION_CONTRACT_V1,
    wire_version: LAYOUT_OPERATION_WIRE_VERSION,
    ops: Object.freeze(normalizedOps),
    digest,
  });
}

export function assertLayoutOperationEnvelope(value) {
  const normalized = normalizeLayoutOperationV1(value);
  if (!_isPlainObject(value)) {
    throw _fail("layout operation envelope must be an object", "malformed_layout_operation");
  }
  if (value.digest !== normalized.digest) {
    throw _fail("Layout operation digest mismatch", "layout_operation_digest_mismatch");
  }
  return normalized;
}

export default {
  LAYOUT_OPERATION_CONTRACT_V1,
  LAYOUT_OPERATION_WIRE_VERSION,
  LAYOUT_OPERATION_OP_NAMES,
  LayoutOperationError,
  computeLayoutOperationDigest,
  normalizeLayoutOperationV1,
  assertLayoutOperationEnvelope,
};
