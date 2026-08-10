// json_clone.js — Shared JSON round-trip clone (Family B, S8/S11)
//
// The single shared implementation for the JSON-family clone sites that used
// to duplicate `JSON.parse(JSON.stringify(...))` per module (agentic_replay,
// preview_picker, vibecomfy_roundtrip). Semantics are pinned by the T-031
// tests (agentic_replay / preview_picker / roundtrip_smoke / dynamic_io_smoke)
// and preserved unchanged by T-032:
//
//   1. null/undefined pass through unchanged.
//   2. Everything else is cloned via JSON round-trip: undefined and function
//      members are DROPPED (JSON.stringify omits them from objects; array
//      holes/undefined elements become null), symbol keys and non-enumerable
//      properties are dropped, prototypes are discarded.
//   3. A serialization failure (e.g. a cyclic reference or BigInt) THROWS a
//      TypeError — the clone never aliases the source. This matches
//      deep_plain.js, which also throws TypeError on cycles.
//
// This module is dependency-free and directly loadable by ComfyUI's browser
// runtime (no Node builtins, no DOM, no external imports), mirroring
// deep_plain.js.

/**
 * Deep JSON round-trip copy of a plain object/array graph.
 *
 * - null/undefined are returned unchanged.
 * - Values are serialized through JSON: undefined and function members are
 *   dropped, symbol keys and non-enumerable properties are dropped, and
 *   output prototypes are `Object.prototype`/`Array.prototype`.
 * - If serialization throws (e.g. a cyclic reference or BigInt), the native
 *   TypeError propagates — the clone never aliases the source.
 *
 * @param {*} value Value to clone.
 * @returns {*} JSON round-trip copy of `value`.
 * @throws {TypeError} If `value` cannot be serialized (e.g. cyclic reference
 *   or BigInt).
 */
export function jsonClone(value) {
  if (value == null) {
    return value;
  }
  return JSON.parse(JSON.stringify(value));
}
