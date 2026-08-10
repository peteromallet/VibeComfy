// deep_plain.js — Deep structural clone with recursion-stack cycle guard
//
// Semantics are pinned by `tests/browser/deep_plain.test.mjs` (T-028 spec, S8
// Family-A manual recursion):
//
//   1. Deep-copies plain objects/arrays recursively (map/entries semantics:
//      own enumerable string keys only).
//   2. Passes through primitives, null, undefined, functions, and symbol
//      VALUES unchanged.
//   3. Drops symbol KEYS and non-enumerable/prototype properties
//      (prototypes discarded — output objects use Object.prototype).
//   4. Does NOT preserve repeated references: the same object appearing
//      twice is re-cloned into two distinct copies.
//   5. Cycles throw TypeError. A recursion-stack WeakSet tracks only the
//      current ancestor chain (add on enter, remove on unwind), so sibling
//      repeats are re-cloned while true back-edges throw.
//   6. Output is a plain, immutable-free structural copy — no freezing.
//
// Keep this module dependency-free and directly loadable by ComfyUI's browser
// runtime (no Node builtins, no DOM, no external imports).

// ── Helpers ─────────────────────────────────────────────────────────────────

// Recurse with an explicit recursion-stack WeakSet. `stack` holds exactly the
// ancestors of the value currently being cloned; `delete` on unwind (via
// `finally`) restores the stack so a sibling reference to the same object is
// seen as a fresh occurrence, not a cycle.
function _deepClone(value, stack) {
  // Pass through everything that is not an object: primitives, null,
  // undefined, functions, and symbol values.
  if (value === null || typeof value !== "object") {
    return value;
  }

  if (stack.has(value)) {
    throw new TypeError("deep_plain: cyclic reference detected");
  }

  stack.add(value);
  try {
    const out = Array.isArray(value) ? new Array(value.length) : {};
    // Own enumerable string keys: symbol keys, non-enumerable properties, and
    // inherited members are all excluded by Object.keys. Keys are copied with
    // defineProperty (not plain assignment) so an own data key named
    // `__proto__` — e.g. produced by JSON.parse of a `{"__proto__": ...}`
    // member — is preserved as an own key instead of mutating the clone's
    // prototype and being lost. Data-key descriptors match assignment.
    for (const key of Object.keys(value)) {
      Object.defineProperty(out, key, {
        value: _deepClone(value[key], stack),
        enumerable: true,
        writable: true,
        configurable: true,
      });
    }
    return out;
  } finally {
    stack.delete(value);
  }
}

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * Deep structural copy of a plain object/array graph.
 *
 * - Objects/arrays are recursively cloned via their own enumerable string
 *   entries; output objects have `Object.prototype`, output arrays have
 *   `Array.prototype`.
 * - Primitives, null, undefined, functions, and symbol values pass through
 *   unchanged.
 * - Symbol keys, non-enumerable properties, and prototype/inherited members
 *   are dropped.
 * - Repeated references are NOT preserved: each occurrence is re-cloned into
 *   a distinct copy.
 * - A genuine cycle (a back-edge to an ancestor currently on the recursion
 *   stack) throws `TypeError`.
 *
 * @param {*} value Value to clone.
 * @returns {*} Structural copy of `value`.
 */
export function deep_plain(value) {
  return _deepClone(value, new WeakSet());
}
