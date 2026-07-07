// canonical_delta.js — Browser-side canonical delta normalization
//
// Mirrors the Python backend's canonical V2 delta contract defined in
// `vibecomfy/porting/edit/ops.py`.  The canonical persisted/runtime-facing
// contract is ``{schema_version: "2.0.0", ops: [...]}`` with exactly six
// supported op kinds.
//
// This module is the single browser-side authority for delta normalisation.
// All lifecycle consumers (preview, apply, accept) must receive ops that have
// been normalised through this module.
//
// Legacy handling is explicit:
//   - Flat V2 op arrays are only accepted via the `allowLegacyList` bridge.
//   - Legacy wrapped mappings are rejected as `legacy_delta_shape` so consumers
//     do not silently confuse audit metadata with canonical ops.

// ── Constants (aligned with Python backend) ─────────────────────────────────

export const DELTA_SCHEMA_VERSION = "2.0.0";

export const DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta";
export const DELTA_DIAGNOSTIC_LEGACY_SHAPE = "legacy_delta_shape";
export const DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY = "unsupported_scoped_apply";

export const CANONICAL_DELTA_OP_NAMES = Object.freeze([
  "set_node_field",
  "set_mode",
  "add_node",
  "upsert_link",
  "remove_node",
  "remove_link",
]);

const _CANONICAL_ENVELOPE_KEYS = Object.freeze(
  new Set(["schema_version", "ops"]),
);

const _LEGACY_WRAPPER_KEYS = Object.freeze(
  new Set([
    "automatic_link_removals",
    "delta",
    "delta_ops",
    "diagnostics",
    "guard_result",
    "normalize",
    "ops",
    "re_stitches",
  ]),
);

// ── Helpers ─────────────────────────────────────────────────────────────────

function _isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function _isNonEmptyString(value) {
  return typeof value === "string" && value.length > 0;
}

/**
 * Stable shallow clone with sorted keys for deterministic shape.
 * @param {object} obj
 * @returns {object}
 */
function _stableClone(obj) {
  const keys = Object.keys(obj).sort();
  const clone = /** @type {object} */ ({});
  for (const key of keys) {
    clone[key] = obj[key];
  }
  return clone;
}

/**
 * Deep-clone plain JSON-compatible data.
 * @param {*} value
 * @returns {*}
 */
function _clonePlainData(value) {
  if (Array.isArray(value)) {
    return value.map(_clonePlainData);
  }
  if (_isObject(value)) {
    const clone = /** @type {object} */ ({});
    for (const [key, entry] of Object.entries(value)) {
      clone[key] = _clonePlainData(entry);
    }
    return clone;
  }
  return value;
}

/**
 * Freeze plain JSON-compatible data deeply.
 * @param {*} value
 * @returns {*}
 */
function _freezePlainData(value) {
  if (Array.isArray(value)) {
    for (const entry of value) {
      _freezePlainData(entry);
    }
    return Object.freeze(value);
  }
  if (_isObject(value)) {
    for (const entry of Object.values(value)) {
      _freezePlainData(entry);
    }
    return Object.freeze(value);
  }
  return value;
}

// ── Validation ──────────────────────────────────────────────────────────────

/**
 * Lenient validation for legacy flat V2 op arrays.  Only checks that the
 * entry has a non-empty string ``op`` and that the op kind is one of the
 * six canonical names.  All other fields are passed through as-is with
 * sorted keys for deterministic shape.
 *
 * @param {object} entry
 * @param {number} index
 * @returns {object}
 */
function _validateLegacyFlatOp(entry, index) {
  if (!_isObject(entry)) {
    throw new DeltaDiagnosticError(
      `delta op at index ${index} must be an object.`,
      DELTA_DIAGNOSTIC_MALFORMED,
      { index },
    );
  }

  const opName = entry.op;
  if (!_isNonEmptyString(opName)) {
    throw new DeltaDiagnosticError(
      `delta op at index ${index} must have a non-empty string "op" field.`,
      DELTA_DIAGNOSTIC_MALFORMED,
      { index, op: opName },
    );
  }

  if (!CANONICAL_DELTA_OP_NAMES.includes(opName)) {
    throw new DeltaDiagnosticError(
      `Unsupported edit op "${opName}" at index ${index}. Expected one of: ${CANONICAL_DELTA_OP_NAMES.join(", ")}.`,
      DELTA_DIAGNOSTIC_MALFORMED,
      { index, op: opName },
    );
  }

  return _stableClone(entry);
}

/**
 * Strict validation for canonical envelope ops (backend-aligned).
 * Validates structural constraints for each op type.
 *
 * @param {object} entry
 * @param {number} index
 * @returns {object}
 */
function _validateCanonicalOpStrict(entry, index) {
  if (!_isObject(entry)) {
    throw new DeltaDiagnosticError(
      `delta op at index ${index} must be an object.`,
      DELTA_DIAGNOSTIC_MALFORMED,
      { index },
    );
  }

  const opName = entry.op;
  if (!_isNonEmptyString(opName)) {
    throw new DeltaDiagnosticError(
      `delta op at index ${index} must have a non-empty string "op" field.`,
      DELTA_DIAGNOSTIC_MALFORMED,
      { index, op: opName },
    );
  }

  if (!CANONICAL_DELTA_OP_NAMES.includes(opName)) {
    throw new DeltaDiagnosticError(
      `Unsupported edit op "${opName}" at index ${index}. Expected one of: ${CANONICAL_DELTA_OP_NAMES.join(", ")}.`,
      DELTA_DIAGNOSTIC_MALFORMED,
      { index, op: opName },
    );
  }

  // Per-op structural validations (aligned with Python backend)
  switch (opName) {
    case "set_node_field": {
      if (!Array.isArray(entry.target) || entry.target.length < 2) {
        throw new DeltaDiagnosticError(
          `set_node_field at index ${index} must have a "target" array of length >= 2.`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName },
        );
      }
      if (!("value" in entry)) {
        throw new DeltaDiagnosticError(
          `set_node_field at index ${index} must have a "value" field.`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName },
        );
      }
      break;
    }

    case "set_mode": {
      if (!Array.isArray(entry.target) || entry.target.length < 2) {
        throw new DeltaDiagnosticError(
          `set_mode at index ${index} must have a "target" array of length >= 2.`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName },
        );
      }
      if (![0, 2, 4].includes(entry.mode)) {
        throw new DeltaDiagnosticError(
          `set_mode at index ${index} must have "mode" one of: 0, 2, 4.`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName },
        );
      }
      break;
    }

    case "add_node": {
      if (!_isNonEmptyString(entry.uid)) {
        throw new DeltaDiagnosticError(
          `add_node at index ${index} must have a non-empty string "uid".`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName, field: "uid" },
        );
      }
      if (!_isNonEmptyString(entry.node_id)) {
        throw new DeltaDiagnosticError(
          `add_node at index ${index} must have a non-empty string "node_id".`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName, field: "node_id" },
        );
      }
      if (!_isNonEmptyString(entry.class_type)) {
        throw new DeltaDiagnosticError(
          `add_node at index ${index} must have a non-empty string "class_type".`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName, field: "class_type" },
        );
      }
      break;
    }

    case "upsert_link": {
      if (!Array.isArray(entry.from) || entry.from.length < 3) {
        throw new DeltaDiagnosticError(
          `upsert_link at index ${index} must have a "from" array of length >= 3.`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName },
        );
      }
      if (!Array.isArray(entry.to) || entry.to.length < 3) {
        throw new DeltaDiagnosticError(
          `upsert_link at index ${index} must have a "to" array of length >= 3.`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName },
        );
      }
      break;
    }

    case "remove_node": {
      if (!Array.isArray(entry.target) || entry.target.length < 2) {
        throw new DeltaDiagnosticError(
          `remove_node at index ${index} must have a "target" array of length >= 2.`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName },
        );
      }
      break;
    }

    case "remove_link": {
      const hasId = "id" in entry && entry.id != null;
      const hasTo = "to" in entry && entry.to != null;
      if (!hasId && !hasTo) {
        throw new DeltaDiagnosticError(
          `remove_link at index ${index} requires either "id" or "to".`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName },
        );
      }
      if (hasId && hasTo) {
        throw new DeltaDiagnosticError(
          `remove_link at index ${index} accepts only one of "id" or "to".`,
          DELTA_DIAGNOSTIC_MALFORMED,
          { index, op: opName },
        );
      }
      break;
    }

    default:
      break;
  }

  return _stableClone(entry);
}

// ── DeltaDiagnosticError ────────────────────────────────────────────────────

export class DeltaDiagnosticError extends Error {
  constructor(message, code, detail = {}) {
    super(message);
    this.name = "DeltaDiagnosticError";
    this.code = code || DELTA_DIAGNOSTIC_MALFORMED;
    this.detail = detail || {};
  }
}

// ── Shape classification ────────────────────────────────────────────────────

export function classifyDeltaShape(payload) {
  if (!_isObject(payload)) {
    return {
      shape: "missing",
      code: "missing_turn_response",
      detail: {},
    };
  }

  const envelope = payload.delta_ops_envelope;
  if (_isObject(envelope)) {
    const ops = envelope.ops;
    if (Array.isArray(ops)) {
      return {
        shape: "canonical",
        code: "canonical_delta_ops",
        detail: { schema_version: envelope.schema_version || null },
      };
    }
    return {
      shape: "canonical",
      code: "canonical_envelope_malformed_ops",
      detail: { ops_type: typeof ops },
    };
  }

  const deltaOps = payload.delta_ops;
  if (Array.isArray(deltaOps)) {
    return {
      shape: "legacy_flat",
      code: "legacy_delta_ops_flat",
      detail: {},
    };
  }

  if (_isObject(deltaOps)) {
    const legacyKeys = Object.keys(deltaOps)
      .filter((k) => _LEGACY_WRAPPER_KEYS.has(k))
      .sort();
    return {
      shape: "legacy_wrapped",
      code: DELTA_DIAGNOSTIC_LEGACY_SHAPE,
      detail: { keys: legacyKeys },
    };
  }

  return {
    shape: "missing",
    code: "missing_delta_ops",
    detail: {},
  };
}

// ── Normalisation ───────────────────────────────────────────────────────────

export function normalizeDeltaEnvelope(payload, options = {}) {
  const { allowLegacyList = false, strict = false } = options;

  if (_isObject(payload)) {
    const data = /** @type {object} */ (payload);

    // Detect and reject legacy wrapped shapes.
    if ("delta_ops" in data) {
      const legacyKeys = Object.keys(data)
        .filter((k) => _LEGACY_WRAPPER_KEYS.has(k))
        .sort();
      throw new DeltaDiagnosticError(
        "Legacy wrapped delta shapes under `delta_ops` are not canonical V2 envelopes.",
        DELTA_DIAGNOSTIC_LEGACY_SHAPE,
        { keys: legacyKeys },
      );
    }

    const hasSchemaVersion = "schema_version" in data;
    const hasOps = "ops" in data;

    if (hasOps && !hasSchemaVersion) {
      const legacyKeys = Object.keys(data)
        .filter((k) => _LEGACY_WRAPPER_KEYS.has(k))
        .sort();
      throw new DeltaDiagnosticError(
        "Legacy wrapped delta shapes must be migrated to `{schema_version, ops}`.",
        DELTA_DIAGNOSTIC_LEGACY_SHAPE,
        { keys: legacyKeys },
      );
    }

    if (!hasSchemaVersion && !hasOps) {
      const extras = Object.keys(data).sort();
      throw new DeltaDiagnosticError(
        "Canonical delta envelopes must be objects with `schema_version` and `ops`.",
        DELTA_DIAGNOSTIC_MALFORMED,
        { keys: extras },
      );
    }

    // Reject extra keys beyond the canonical two.
    const extras = Object.keys(data).filter(
      (key) => !_CANONICAL_ENVELOPE_KEYS.has(key),
    );
    if (extras.length > 0) {
      if (extras.some((key) => _LEGACY_WRAPPER_KEYS.has(key))) {
        throw new DeltaDiagnosticError(
          "Legacy wrapped delta metadata is not part of the canonical V2 envelope.",
          DELTA_DIAGNOSTIC_LEGACY_SHAPE,
          { keys: extras.sort() },
        );
      }
      throw new DeltaDiagnosticError(
        "Canonical delta envelopes only accept `schema_version` and `ops`.",
        DELTA_DIAGNOSTIC_MALFORMED,
        { keys: extras.sort() },
      );
    }

    const schemaVersion = data.schema_version;
    if (schemaVersion !== DELTA_SCHEMA_VERSION) {
      throw new DeltaDiagnosticError(
        `Unsupported delta schema_version "${schemaVersion}".`,
        DELTA_DIAGNOSTIC_MALFORMED,
        { schema_version: schemaVersion },
      );
    }

    const ops = data.ops;
    if (!Array.isArray(ops)) {
      throw new DeltaDiagnosticError(
        "Canonical delta envelope `ops` must be an array.",
        DELTA_DIAGNOSTIC_MALFORMED,
        {},
      );
    }

    // Canonical envelopes use strict validation.
    const validateFn = strict ? _validateCanonicalOpStrict : _validateLegacyFlatOp;
    const normalizedOps = [];
    for (let i = 0; i < ops.length; i++) {
      normalizedOps.push(validateFn(ops[i], i));
    }

    return {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: _freezePlainData(normalizedOps),
    };
  }

  // Legacy flat V2 op array bridge
  if (Array.isArray(payload)) {
    if (!allowLegacyList) {
      throw new DeltaDiagnosticError(
        "Flat V2 delta op arrays are a legacy bridge; wrap them in `{schema_version, ops}`.",
        DELTA_DIAGNOSTIC_LEGACY_SHAPE,
        {},
      );
    }
    // Legacy flat arrays use lenient validation with skip-on-invalid.
    const normalizedOps = [];
    for (let i = 0; i < payload.length; i++) {
      try {
        normalizedOps.push(_validateLegacyFlatOp(payload[i], i));
      } catch (_err) {
        // Skip invalid entries in legacy flat arrays — backward compat.
        continue;
      }
    }
    return {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: _freezePlainData(normalizedOps),
    };
  }

  throw new DeltaDiagnosticError(
    "Canonical delta envelopes must be an object or op list.",
    DELTA_DIAGNOSTIC_MALFORMED,
    {},
  );
}

export function normalizeDeltaOpsFromSubmitPayload(payload) {
  const shape = classifyDeltaShape(payload);

  if (shape.shape === "canonical") {
    try {
      // Canonical envelopes: lenient validation (backend already validated).
      const envelope = normalizeDeltaEnvelope(payload.delta_ops_envelope, {
        strict: false,
      });
      return envelope.ops;
    } catch (err) {
      if (err instanceof DeltaDiagnosticError) {
        throw err;
      }
      throw new DeltaDiagnosticError(
        `Failed to normalize canonical delta envelope: ${err.message}`,
        DELTA_DIAGNOSTIC_MALFORMED,
        { cause: err.message },
      );
    }
  }

  if (shape.shape === "legacy_flat") {
    try {
      // Legacy flat arrays use the lenient bridge.
      const envelope = normalizeDeltaEnvelope(payload.delta_ops, {
        allowLegacyList: true,
      });
      return envelope.ops;
    } catch (err) {
      if (err instanceof DeltaDiagnosticError) {
        throw err;
      }
      throw new DeltaDiagnosticError(
        `Failed to normalize legacy flat delta ops: ${err.message}`,
        DELTA_DIAGNOSTIC_MALFORMED,
        { cause: err.message },
      );
    }
  }

  if (shape.shape === "legacy_wrapped") {
    throw new DeltaDiagnosticError(
      "Legacy wrapped delta shapes are not supported. Migrate to `{schema_version, ops}`.",
      DELTA_DIAGNOSTIC_LEGACY_SHAPE,
      shape.detail,
    );
  }

  throw new DeltaDiagnosticError(
    "No delta ops found in submit response.",
    shape.code || "missing_delta_ops",
    shape.detail,
  );
}

export function ensureRootScopedOps(ops) {
  for (const op of ops) {
    const scopedPaths = [];

    if (
      op.op === "set_node_field" ||
      op.op === "set_mode" ||
      op.op === "remove_node"
    ) {
      if (Array.isArray(op.target) && op.target.length >= 2) {
        scopedPaths.push(op.target[0] || "");
      }
    } else if (op.op === "add_node") {
      scopedPaths.push(op.scope_path || "");
    } else if (op.op === "upsert_link") {
      if (Array.isArray(op.from) && op.from.length >= 1) {
        scopedPaths.push(op.from[0] || "");
      }
      if (Array.isArray(op.to) && op.to.length >= 1) {
        scopedPaths.push(op.to[0] || "");
      }
    } else if (
      op.op === "remove_link" &&
      Array.isArray(op.to) &&
      op.to.length >= 1
    ) {
      scopedPaths.push(op.to[0] || "");
    }

    const bad = [
      ...new Set(scopedPaths.filter((p) => p && p.length > 0)),
    ].sort();
    if (bad.length > 0) {
      throw new DeltaDiagnosticError(
        "Non-root scoped apply is unsupported for canonical delta consumers.",
        DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
        { scope_paths: bad, op: op.op },
      );
    }
  }
}

export default {
  DELTA_SCHEMA_VERSION,
  DELTA_DIAGNOSTIC_MALFORMED,
  DELTA_DIAGNOSTIC_LEGACY_SHAPE,
  DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
  CANONICAL_DELTA_OP_NAMES,
  DeltaDiagnosticError,
  classifyDeltaShape,
  normalizeDeltaEnvelope,
  normalizeDeltaOpsFromSubmitPayload,
  ensureRootScopedOps,
};
