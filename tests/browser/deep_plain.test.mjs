// ── T-028: deep_plain semantics spec (S8) ───────────────────────────────────
// This file SPECIFIES the semantics that vibecomfy/comfy_nodes/web/deep_plain.js
// (T-029) must implement. The module does not exist yet, so this suite fails
// with a module-not-found import error until T-029 lands — that import failure
// is the expected, only failure pre-T-029.
//
// T-029 CONTRACT (pinned here): W/deep_plain.js MUST export a named function
// `deep_plain(value)` implementing Family-A manual recursive semantics:
//   1. Deep-copies plain objects/arrays recursively (map/entries semantics).
//   2. Passes through primitives, null, undefined, functions, and symbol
//      VALUES unchanged.
//   3. Drops symbol KEYS and non-enumerable/prototype properties
//      (prototypes discarded).
//   4. Does NOT preserve repeated references: the same object appearing
//      twice is re-cloned into two distinct copies.
//   5. Cycles throw TypeError (recursion-stack WeakSet: add on enter,
//      remove on unwind — sibling repeats are NOT cycles).
//   6. Output is a plain, immutable-free structural copy. Tests assert clone
//      identity/independence only — they do NOT depend on whether the
//      implementation also freezes.
import test from "node:test";
import assert from "node:assert/strict";

import { deep_plain } from "../../vibecomfy/comfy_nodes/web/deep_plain.js";

// ── 1. Recursive deep copy (map/entries semantics) ─────────────────────────

test("deep_plain deep-copies nested plain objects and arrays recursively", () => {
  const source = {
    name: "root",
    nested: { list: [1, { two: 2 }, [3, { four: 4 }]] },
    empty: {},
    arr: [],
  };
  const copy = deep_plain(source);

  // Content is structurally identical…
  assert.deepEqual(copy, source);
  // …but every level is a distinct object, not an alias.
  assert.notEqual(copy, source);
  assert.notEqual(copy.nested, source.nested);
  assert.notEqual(copy.nested.list, source.nested.list);
  assert.notEqual(copy.nested.list[1], source.nested.list[1]);
  assert.notEqual(copy.nested.list[2], source.nested.list[2]);
  assert.notEqual(copy.nested.list[2][1], source.nested.list[2][1]);
  assert.notEqual(copy.empty, source.empty);
  assert.notEqual(copy.arr, source.arr);
  assert.ok(Array.isArray(copy.nested.list));
  assert.ok(Array.isArray(copy.arr));
});

test("deep_plain clone is independent of the source (later source mutation does not leak in)", () => {
  const source = { nested: { list: [{ v: 1 }] } };
  const copy = deep_plain(source);

  source.nested.list[0].v = 100;
  source.nested.list.push({ v: 2 });
  source.nested.extra = "added";

  assert.deepEqual(copy, { nested: { list: [{ v: 1 }] } });
});

// ── 2. Special values pass through unchanged ────────────────────────────────

test("deep_plain returns primitives, null, undefined, functions and symbols unchanged at top level", () => {
  const fn = () => 1;
  const sym = Symbol("top-level-symbol");
  assert.equal(deep_plain(undefined), undefined);
  assert.equal(deep_plain(null), null);
  assert.equal(deep_plain(7), 7);
  assert.equal(deep_plain(-1.5), -1.5);
  assert.equal(deep_plain(10n), 10n);
  assert.equal(deep_plain("text"), "text");
  assert.equal(deep_plain(false), false);
  assert.equal(deep_plain(fn), fn);
  assert.equal(deep_plain(sym), sym);
});

test("deep_plain passes primitives, null, undefined, functions and symbol values through nested objects unchanged", () => {
  const fn = function named() {};
  const sym = Symbol("value-symbol");
  const source = {
    str: "text",
    num: 42,
    neg: -1.5,
    big: 10n,
    bool: false,
    nul: null,
    undef: undefined,
    fn,
    symValue: sym,
  };
  const copy = deep_plain(source);

  assert.deepEqual(copy, source);
  assert.equal(copy.str, "text");
  assert.equal(copy.num, 42);
  assert.equal(copy.neg, -1.5);
  assert.equal(copy.big, 10n);
  assert.equal(copy.bool, false);
  assert.equal(copy.nul, null);
  assert.equal(copy.undef, undefined);
  assert.equal(copy.fn, fn);
  assert.equal(copy.symValue, sym);
});

test("deep_plain passes special values through arrays unchanged", () => {
  const fn = () => "f";
  const sym = Symbol("array-symbol");
  const arr = [undefined, null, 0, "", fn, sym];
  const copy = deep_plain(arr);

  assert.deepEqual(copy, arr);
  assert.equal(copy[0], undefined);
  assert.equal(copy[1], null);
  assert.equal(copy[2], 0);
  assert.equal(copy[3], "");
  assert.equal(copy[4], fn);
  assert.equal(copy[5], sym);
  assert.notEqual(copy, arr);
});

// ── 3. Symbol keys, non-enumerable and prototype properties dropped ────────

test("deep_plain drops symbol keys", () => {
  const symKey = Symbol("hidden-key");
  const source = { visible: 1, [symKey]: "hidden" };
  const copy = deep_plain(source);

  assert.deepEqual(copy, { visible: 1 });
  assert.deepEqual(Object.keys(copy), ["visible"]);
  assert.ok(!Object.prototype.hasOwnProperty.call(copy, symKey));
  assert.ok(!(symKey in copy));
});

test("deep_plain drops symbol keys in nested objects too", () => {
  const symKey = Symbol("nested-key");
  const source = { outer: { keep: "yes", [symKey]: "drop" } };
  const copy = deep_plain(source);

  assert.deepEqual(copy, { outer: { keep: "yes" } });
  assert.ok(!Object.prototype.hasOwnProperty.call(copy.outer, symKey));
});

test("deep_plain drops non-enumerable properties", () => {
  const source = { own: 1 };
  Object.defineProperty(source, "hidden", {
    value: 2,
    enumerable: false,
    writable: true,
    configurable: true,
  });
  const copy = deep_plain(source);

  assert.deepEqual(copy, { own: 1 });
  assert.ok(!Object.prototype.hasOwnProperty.call(copy, "hidden"));
  assert.ok(!("hidden" in copy));
});

test("deep_plain discards prototypes (inherited properties are dropped, output is plain)", () => {
  const proto = { inherited: "from-proto" };
  const source = Object.create(proto);
  source.own = 1;
  const copy = deep_plain(source);

  assert.deepEqual(copy, { own: 1 });
  assert.ok(!("inherited" in copy));
  assert.ok(!Object.prototype.hasOwnProperty.call(copy, "inherited"));
  assert.equal(Object.getPrototypeOf(copy), Object.prototype);
});

// ── 4. Repeated references are NOT preserved (re-cloned) ───────────────────

test("deep_plain re-clones the same object appearing twice in an object", () => {
  const shared = { value: 1 };
  const source = { first: shared, second: shared };
  const copy = deep_plain(source);

  assert.deepEqual(copy, { first: { value: 1 }, second: { value: 1 } });
  assert.notEqual(copy.first, copy.second);
  assert.notEqual(copy.first, shared);
  assert.notEqual(copy.second, shared);
});

test("deep_plain re-clones the same object appearing twice in an array (no throw, distinct copies)", () => {
  // Sibling repeats are NOT cycles: the recursion-stack WeakSet must only
  // fire on back-edges to an ancestor, so this must succeed with two copies.
  const shared = { x: 1 };
  const copy = deep_plain([shared, shared]);

  assert.deepEqual(copy, [{ x: 1 }, { x: 1 }]);
  assert.notEqual(copy[0], copy[1]);
  assert.notEqual(copy[0], shared);
  assert.notEqual(copy[1], shared);
});

// ── 5. Cycles throw TypeError (recursion-stack WeakSet guard) ──────────────

test("deep_plain throws TypeError on a self-referential object cycle", () => {
  const source = {};
  source.self = source;
  assert.throws(() => deep_plain(source), TypeError);
});

test("deep_plain throws TypeError on a deep back-edge cycle", () => {
  const source = { a: { b: {} } };
  source.a.b.back = source;
  assert.throws(() => deep_plain(source), TypeError);
});

test("deep_plain throws TypeError on a cycle inside an array", () => {
  const arr = [];
  arr.push(arr);
  assert.throws(() => deep_plain(arr), TypeError);
});

test("deep_plain throws TypeError on a cycle nested under a value that passed through", () => {
  const source = { fn: () => 1, nested: {} };
  source.nested.self = source.nested;
  assert.throws(() => deep_plain(source), TypeError);
});

// ── 6. Plain, immutable-free structural copy (identity/independence only) ──

test("deep_plain output is a plain structural copy (prototypes are the plain defaults)", () => {
  const source = {
    nested: { list: [{ v: 1 }] },
    dateLike: { t: 1 },
  };
  const copy = deep_plain(source);

  assert.equal(Object.getPrototypeOf(copy), Object.prototype);
  assert.equal(Object.getPrototypeOf(copy.nested), Object.prototype);
  assert.equal(Object.getPrototypeOf(copy.nested.list), Array.prototype);
  assert.equal(Object.getPrototypeOf(copy.nested.list[0]), Object.prototype);
  assert.equal(Object.getPrototypeOf(copy.dateLike), Object.prototype);
  assert.deepEqual(copy, source);
});

test("deep_plain does not alias the source at any level (identity independence only, no freeze dependence)", () => {
  const source = { a: [1, { b: 2 }] };
  const copy = deep_plain(source);

  assert.notEqual(copy, source);
  assert.notEqual(copy.a, source.a);
  assert.notEqual(copy.a[1], source.a[1]);
  // Mutating the SOURCE must never affect the already-produced clone.
  source.a[1].b = 99;
  assert.equal(copy.a[1].b, 2);
});
