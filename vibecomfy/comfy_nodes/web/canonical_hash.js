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

// ── Helpers ─────────────────────────────────────────────────────────────────

// Keep this module directly loadable by ComfyUI's browser runtime.  A Node
// builtin import here prevents the entire VibeComfy extension entrypoint from
// evaluating, so the synchronous hash API uses a small SHA-256 implementation
// over UTF-8 bytes instead of `node:crypto`.  Web Crypto is intentionally not
// used because `crypto.subtle.digest()` is asynchronous and these helpers are
// consumed synchronously by preview/apply verification.
const _SHA256_INITIAL = Object.freeze([
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
]);

const _SHA256_CONSTANTS = Object.freeze([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function _rotateRight(value, bits) {
  return (value >>> bits) | (value << (32 - bits));
}

function _sha256HexUtf8(text) {
  const bytes = new TextEncoder().encode(String(text));
  const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;

  const bitLength = bytes.length * 8;
  const paddedView = new DataView(padded.buffer);
  paddedView.setUint32(paddedLength - 8, Math.floor(bitLength / 0x100000000), false);
  paddedView.setUint32(paddedLength - 4, bitLength >>> 0, false);

  const state = _SHA256_INITIAL.slice();
  const words = new Uint32Array(64);
  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      words[index] = paddedView.getUint32(offset + index * 4, false);
    }
    for (let index = 16; index < 64; index += 1) {
      const prior15 = words[index - 15];
      const prior2 = words[index - 2];
      const sigma0 = _rotateRight(prior15, 7) ^ _rotateRight(prior15, 18) ^ (prior15 >>> 3);
      const sigma1 = _rotateRight(prior2, 17) ^ _rotateRight(prior2, 19) ^ (prior2 >>> 10);
      words[index] = (words[index - 16] + sigma0 + words[index - 7] + sigma1) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = state;
    for (let index = 0; index < 64; index += 1) {
      const choice = (e & f) ^ (~e & g);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const sum0 = _rotateRight(a, 2) ^ _rotateRight(a, 13) ^ _rotateRight(a, 22);
      const sum1 = _rotateRight(e, 6) ^ _rotateRight(e, 11) ^ _rotateRight(e, 25);
      const temp1 = (h + sum1 + choice + _SHA256_CONSTANTS[index] + words[index]) >>> 0;
      const temp2 = (sum0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }

    state[0] = (state[0] + a) >>> 0;
    state[1] = (state[1] + b) >>> 0;
    state[2] = (state[2] + c) >>> 0;
    state[3] = (state[3] + d) >>> 0;
    state[4] = (state[4] + e) >>> 0;
    state[5] = (state[5] + f) >>> 0;
    state[6] = (state[6] + g) >>> 0;
    state[7] = (state[7] + h) >>> 0;
  }

  return state.map((word) => word.toString(16).padStart(8, "0")).join("");
}

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

function _stringifyUtf8Safe(value) {
  return JSON.stringify(
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
}

function _compareCanonicalKeys(left, right) {
  if (left < right) return -1;
  if (left > right) return 1;
  return 0;
}

function _serializeCanonical(value, { ensureAscii }) {
  if (Array.isArray(value)) {
    return `[${value.map((entry) => _serializeCanonical(entry, { ensureAscii })).join(",")}]`;
  }
  if (_isPlainObject(value)) {
    return `{${Object.keys(value)
      .sort(_compareCanonicalKeys)
      .map((key) => {
        const encodedKey = ensureAscii
          ? _stringifyAsciiSafe(key)
          : _stringifyUtf8Safe(key);
        return `${encodedKey}:${_serializeCanonical(value[key], { ensureAscii })}`;
      })
      .join(",")}}`;
  }
  return ensureAscii ? _stringifyAsciiSafe(value) : _stringifyUtf8Safe(value);
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
  return _serializeCanonical(canonical, { ensureAscii: true });
}

/**
 * Canonical JSON used by agent-edit session authority. This is a serialization
 * profile of the one browser owner, not an independent canonicalizer.
 */
export function canonicalSessionJsonString(value) {
  const canonical = canonicalizeJsonLike(value);
  return _serializeCanonical(canonical, { ensureAscii: false });
}

export function compareCanonicalSessionJson(left, right) {
  return _compareCanonicalKeys(
    canonicalSessionJsonString(left),
    canonicalSessionJsonString(right),
  );
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
  return _sha256HexUtf8(str);
}

/**
 * Compute the SHA-256 hex digest of canonical JSON bytes from a raw buffer.
 * Utility for when the caller already has the canonical JSON string.
 *
 * @param {string} canonicalJson
 * @returns {string}
 */
export function sha256HexFromString(canonicalJson) {
  return _sha256HexUtf8(canonicalJson);
}

// ── Cross-language numeric normaliser (§0.3.1) ──────────────────────────────

// Maximum exactly-representable integer in IEEE-754 double (2**53 - 1).  JS
// ``Number`` values whose magnitude exceeds this cannot round-trip through
// Python's arbitrary-precision ``int``, so they are rejected as non-canonical
// rather than silently serialised to divergent bytes.
const _JS_SAFE_INTEGER_MAX = 9007199254740991;
const _NON_CANONICAL_NUMBER = "non_canonical_number";

/**
 * Normalise numeric values to the spelling JavaScript's ``JSON.stringify``
 * already emits, so that the shared hash produces a byte-identical preimage on
 * both sides.
 *
 * This is a *value* preprocessor: it recursively walks plain objects (by
 * value) and arrays (by element) and, for every leaf:
 *
 *   - finite safe-integer ``number`` -> returned unchanged
 *     (``JSON.stringify`` is already canonical: ``1``, ``1.5``, ``100``).
 *   - ``NaN`` / ``Infinity`` / ``-Infinity`` -> throws the caller-supplied
 *     ``finiteErrorCode`` (e.g. ``"non_finite_geometry"`` or
 *     ``"non_finite_materialization"``).
 *   - ``boolean`` -> returned unchanged when ``allowBool`` is true; otherwise
 *     rejected with ``non_canonical_number`` (mirrors Python's ``allow_bool``
 *     handling even though JS does not subclass ``Boolean`` from ``Number``).
 *   - finite ``number`` that is integer-valued but outside the JS safe integer
 *     range (``abs(n) > 2**53 - 1``) -> rejected with ``non_canonical_number``
 *     (the shortest round-trippable spelling differs from the exact decimal
 *     Python would emit, so the two sides cannot agree on bytes).
 *
 * It does NOT sort keys, emit JSON text, or compute a digest — the hashing
 * identity remains ``sha256Hex`` / ``canonicalJsonString``.  This mirrors the
 * Python leaf's ``canonicalize_contract_numeric``; both sides run it before
 * hashing so integer-valued floats (``1.0``), ``-0.0``, and exponents
 * (``1e2``) collapse to the same canonical spelling.
 *
 * @param {*} value
 * @param {{ finiteErrorCode?: string, allowBool?: boolean }} [options]
 * @returns {*}
 */
export function canonicalizeContractNumeric(value, options = {}) {
  const finiteErrorCode = options.finiteErrorCode || "non_finite_number";
  const allowBool = options.allowBool === true;
  return _normalizeNumericJs(value, finiteErrorCode, allowBool);
}

function _normalizeNumericJs(value, finiteErrorCode, allowBool) {
  if (Array.isArray(value)) {
    return value.map((entry) => _normalizeNumericJs(entry, finiteErrorCode, allowBool));
  }
  if (_isPlainObject(value)) {
    const result = /** @type {object} */ ({});
    for (const [key, entry] of Object.entries(value)) {
      result[key] = _normalizeNumericJs(entry, finiteErrorCode, allowBool);
    }
    return result;
  }
  if (typeof value === "boolean") {
    if (allowBool) {
      return value;
    }
    // JS does not subclass Boolean from Number; reject explicitly so the
    // default diagnostic remains symmetric with Python's ``allow_bool=False``.
    const error = new Error("Boolean is not a canonical numeric value");
    error.code = _NON_CANONICAL_NUMBER;
    throw error;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      const error = new Error(
        `Non-finite numeric value is not canonical (${finiteErrorCode}).`,
      );
      error.code = finiteErrorCode;
      throw error;
    }
    if (Number.isInteger(value) && !Number.isSafeInteger(value)) {
      // Outside ±(2**53 - 1) the shortest round-trippable JS spelling can
      // diverge from the exact decimal Python emits (e.g. 2**60 serialises as
      // "...476" in Python but "...500" in JS).  Reject so both sides agree.
      const error = new Error(
        "Integer value exceeds the JS safe integer range",
      );
      error.code = _NON_CANONICAL_NUMBER;
      throw error;
    }
    return value;
  }
  return value;
}
