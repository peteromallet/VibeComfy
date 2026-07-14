// canonical_hash.js — Browser-side deterministic canonical JSON and SHA-256
//
// Mirrors the Python backend's _canonical_bytes / _sha256 defined in
// `vibecomfy/porting/reorganise/orchestrate.py`:
//
//   def _canonical_bytes(value: Any) -> bytes:
//       return json.dumps(
//           _freeze_jsonish(value),
//           sort_keys=True,
//           separators=(",", ":"),
//           ensure_ascii=True,
//           default=str,
//       ).encode("utf-8")
//
//   def _sha256(value: Any) -> str:
//       return hashlib.sha256(_canonical_bytes(value)).hexdigest()
//
// This module is the single browser-side authority for canonical JSON hashing.
// All lifecycle consumers (preview, apply, verify) must produce hashes that
// match the Python backend byte-for-byte for equivalent plan/canvas data.

import crypto from "node:crypto";

// ── Helpers ─────────────────────────────────────────────────────────────────

function _isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function _isPlainObject(value) {
  if (!_isObject(value)) return false;
  // Exclude Map, Set, Date, RegExp, etc. — only plain {} or Object.create(null)
  const proto = Object.getPrototypeOf(value);
  return proto === null || proto === Object.prototype;
}

// ── ASCII escaping (mirrors Python json.dumps ensure_ascii=True) ────────────

/**
 * Escape non-ASCII characters in a string to \\uXXXX sequences.
 * Characters with code points above U+FFFF are split into surrogate pairs.
 * @param {string} str
 * @returns {string}
 */
function _escapeNonAscii(str) {
  let result = "";
  for (let i = 0; i < str.length; i++) {
    const code = str.charCodeAt(i);
    if (code <= 0x7f) {
      result += str.charAt(i);
    } else if (code >= 0xd800 && code <= 0xdfff) {
      // Surrogate pair — emit both halves as \\uXXXX
      result += "\\u" + code.toString(16).padStart(4, "0");
    } else {
      result += "\\u" + code.toString(16).padStart(4, "0");
    }
  }
  return result;
}

// ── JSON.stringify with ensure_ascii=True ───────────────────────────────────

/**
 * JSON.stringify with sorted keys, compact separators, ASCII-safe escaping,
 * and string fallback for non-serializable values.
 *
 * Mirrors Python: json.dumps(value, sort_keys=True, separators=(",", ":"),
 *                              ensure_ascii=True, default=str)
 *
 * @param {*} value
 * @returns {string}
 */
function _stringifyAsciiSafe(value) {
  const raw = JSON.stringify(
    value,
    function _replacer(_key, val) {
      if (typeof val === "bigint") return String(val);
      if (typeof val === "function") return String(val);
      if (typeof val === "symbol") return String(val);
      if (typeof val === "undefined") return "undefined";
      if (val instanceof Date) return val.toISOString();
      if (val instanceof RegExp) return String(val);
      return val;
    },
  );
  // JSON.stringify already uses compact separators by default.
  // Now escape non-ASCII characters.
  return _escapeNonAscii(raw);
}

// ── Canonicalization (mirrors _freeze_jsonish) ──────────────────────────────

/**
 * Recursively canonicalize a JSON-compatible value to match Python's
 * _freeze_jsonish semantics:
 *   - Plain objects get sorted keys with stringified key names
 *   - Arrays are recursively processed
 *   - Maps become plain objects with sorted, stringified keys
 *   - Sets become sorted arrays
 *   - Primitives pass through unchanged
 *
 * @param {*} value
 * @returns {*}
 */
export function canonicalizeJsonLike(value) {
  if (value === null || value === undefined) return value;

  if (Array.isArray(value)) {
    return value.map((entry) => canonicalizeJsonLike(entry));
  }

  if (value instanceof Map) {
    const entries = [...value.entries()].map(
      ([k, v]) => [String(k), canonicalizeJsonLike(v)],
    );
    entries.sort(([a], [b]) => {
      if (a < b) return -1;
      if (a > b) return 1;
      return 0;
    });
    const result = /** @type {object} */ ({});
    for (const [key, val] of entries) {
      result[key] = val;
    }
    return result;
  }

  if (value instanceof Set) {
    const items = [...value].map((entry) => canonicalizeJsonLike(entry));
    // Sort for determinism — strings and numbers compare naturally
    items.sort((a, b) => {
      const sa = typeof a === "string" ? a : JSON.stringify(a);
      const sb = typeof b === "string" ? b : JSON.stringify(b);
      if (sa < sb) return -1;
      if (sa > sb) return 1;
      return 0;
    });
    return items;
  }

  if (_isPlainObject(value)) {
    const keys = Object.keys(value).sort();
    const result = /** @type {object} */ ({});
    for (const key of keys) {
      result[String(key)] = canonicalizeJsonLike(value[key]);
    }
    return result;
  }

  // Non-plain objects (Date, RegExp, custom classes) — convert to string
  // via the same fallback path as Python's default=str.
  if (typeof value === "object") {
    try {
      return String(value);
    } catch {
      return "[object]";
    }
  }

  return value;
}

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * Produce the exact canonical JSON string that Python's _canonical_bytes would
 * produce before UTF-8 encoding.
 *
 * Semantics:
 *   - Recursively sorts all object keys
 *   - Compact separators (no whitespace after , or :)
 *   - Non-ASCII characters escaped as \\uXXXX
 *   - Non-JSON-serializable values fall back to String(value)
 *
 * @param {*} value
 * @returns {string}
 */
export function canonicalJsonString(value) {
  const canonical = canonicalizeJsonLike(value);
  return _stringifyAsciiSafe(canonical);
}

/**
 * Produce the canonical UTF-8 bytes that Python's _canonical_bytes would
 * return.
 *
 * @param {*} value
 * @returns {Uint8Array}
 */
export function canonicalJsonBytes(value) {
  const str = canonicalJsonString(value);
  return new TextEncoder().encode(str);
}

/**
 * Compute the SHA-256 hex digest of the canonical JSON representation.
 * Mirrors Python's _sha256(value) = hashlib.sha256(_canonical_bytes(value)).hexdigest()
 *
 * @param {*} value
 * @returns {string}
 */
export function sha256Hex(value) {
  const str = canonicalJsonString(value);
  return crypto.createHash("sha256").update(str, "utf8").digest("hex");
}

/**
 * Compute the SHA-256 hex digest of canonical JSON bytes from a raw buffer.
 * Utility for when the caller already has the canonical JSON string.
 *
 * @param {string} canonicalJson
 * @returns {string}
 */
export function sha256HexFromString(canonicalJson) {
  return crypto.createHash("sha256").update(canonicalJson, "utf8").digest("hex");
}
