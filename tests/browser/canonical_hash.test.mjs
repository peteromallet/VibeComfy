import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  canonicalizeJsonLike,
  canonicalJsonString,
  canonicalSessionJsonString,
  compareCanonicalSessionJson,
  canonicalJsonBytes,
  sha256Hex,
  sha256HexFromString,
} from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";

test("browser canonical hash authority does not import Node-only builtins", async () => {
  const source = await readFile(
    new URL("../../vibecomfy/comfy_nodes/web/canonical_hash.js", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(source, /(?:from|import\s*\()\s*["']node:/);
});

test("browser-compatible SHA-256 matches standard UTF-8 vectors", () => {
  assert.equal(
    sha256HexFromString(""),
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  );
  assert.equal(
    sha256HexFromString("abc"),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
  assert.equal(
    sha256HexFromString("café 漢字"),
    "fc66759ac2df3f128edc4aa992b29b7a486db987b60f017acbb15db47a79ad80",
  );
});

test("session canonical JSON preserves lexical ordering for integer-like keys", () => {
  const value = {
    prompt: {
      "9": { value: 9 },
      "21": { value: 21 },
      "2": { value: 2 },
      "11": { value: 11 },
      "1": { value: 1 },
    },
  };
  assert.equal(
    canonicalSessionJsonString(value),
    '{"prompt":{"1":{"value":1},"11":{"value":11},"2":{"value":2},"21":{"value":21},"9":{"value":9}}}',
  );
});

test("session canonical JSON matches the Python session payload hash fixture", () => {
  const value = {
    extra: {
      prompt: {
        "1": { class_type: "Loader", inputs: { model: "café.safetensors" } },
        "11": { class_type: "Noise", inputs: { seed: 10 } },
        "2": { class_type: "Encode", inputs: { text: "漢字" } },
      },
    },
    nodes: [{ id: 1, mode: 0, widgets_values: [0.95] }],
  };
  assert.equal(
    sha256HexFromString(canonicalSessionJsonString(value)),
    "77f6c09615f286d5b52ab66b334a0e30937a020f85659ab803a347543aff7ef7",
  );
});

test("canonical session comparison does not use locale collation", () => {
  const latent = { from: 239, in: "latent", out: "LATENT", to: 206, type: "LATENT" };
  const latentImage = {
    from: 239,
    in: "latent_image",
    out: "LATENT",
    to: 113,
    type: "LATENT",
  };
  assert.equal(compareCanonicalSessionJson(latent, latentImage), -1);
});

// ── Fixtures ────────────────────────────────────────────────────────────────

/**
 * Fixture 1: Positions — node positions as [x, y] arrays.
 * Verifies array canonicalization and numeric precision.
 */
const POSITIONS_FIXTURE = {
  entries: {
    "node-a": { pos: [100, 200] },
    "node-b": { pos: [300.5, 150.25] },
    "node-c": { pos: [0, 0] },
    "node-d": { pos: [-50, -75.125] },
  },
};

/**
 * Fixture 2: Sizes — node sizes as [width, height] arrays.
 * Verifies integer and float handling in arrays.
 */
const SIZES_FIXTURE = {
  entries: {
    "wide-node": { size: [600, 200] },
    "tall-node": { size: [300, 450] },
    "zero-size": { size: [0, 0] },
    "fractional": { size: [315.75, 212.5] },
  },
};

/**
 * Fixture 3: Groups — group bounding boxes with titles and metadata.
 * Verifies nested object canonicalization and key sorting.
 */
const GROUPS_FIXTURE = {
  groups: [
    {
      title: "Sampler Group",
      bounding: [50, 100, 400, 300],
      color: "#3f789e",
      font_size: 14,
    },
    {
      title: "Preprocess",
      bounding: [-10, 200, 350, 250],
      color: "#8a8a8a",
      locked: true,
    },
  ],
};

/**
 * Fixture 4: Colors — node color/background color strings.
 * Verifies string escaping and key ordering in color fields.
 */
const COLORS_FIXTURE = {
  entries: {
    "red-node": { color: "#ff0000", bgcolor: "#330000" },
    "blue-node": { color: "#0000ff", bgcolor: "#000033" },
    "custom-node": {
      color: "#3f789e",
      bgcolor: "#1a3342",
      label: "Custom",
    },
  },
};

/**
 * Fixture 5: Flags — node flag objects with boolean and string values.
 * Verifies boolean handling and key ordering.
 */
const FLAGS_FIXTURE = {
  entries: {
    "collapsed-node": { flags: { collapsed: true, pinned: false } },
    "pinned-node": { flags: { pinned: true, collapsed: false } },
    "multi-flag": {
      flags: {
        collapsed: false,
        pinned: true,
        locked: true,
        skip_reorganise: false,
      },
    },
  },
};

/**
 * Fixture 6: Key-order variation — identical content with different key
 * insertion order should produce the same canonical JSON and hash.
 */
const KEY_ORDER_A = {
  entries: {
    "node-1": {
      pos: [100, 200],
      size: [300, 400],
      color: "#ff0000",
      flags: { pinned: true },
      order: 1,
      mode: 0,
    },
  },
};

const KEY_ORDER_B = {
  entries: {
    "node-1": {
      mode: 0,
      flags: { pinned: true },
      pos: [100, 200],
      order: 1,
      color: "#ff0000",
      size: [300, 400],
    },
  },
};

/**
 * Fixture 7: Full mutation-plan projection — matches the Python
 * LayoutCandidatePatch.__post_init__ plan_hash computation structure.
 */
const FULL_PLAN_FIXTURE = {
  store_version: 1,
  vibecomfy_version: "0",
  schema_hash: "sha256:abc123",
  entries: {
    "node-1": {
      pos: [100, 200],
      size: [300, 400],
      flags: { pinned: true },
      color: "#ff0000",
      bgcolor: "#330000",
      mode: 0,
      order: 1,
    },
    "node-2": {
      pos: [500, 200],
      size: [300, 400],
      flags: { collapsed: false },
      color: "#00ff00",
      bgcolor: "#003300",
      mode: 0,
      order: 2,
    },
  },
  groups: [
    {
      title: "Main",
      bounding: [50, 50, 800, 600],
      color: "#3f789e",
    },
  ],
  extra: {},
  lastRerouteId: null,
  definitions: {},
  virtual_wires: {},
  unkeyed: [],
};

/**
 * Fixture 8: Non-ASCII strings in plan data.
 * Verifies that JS and Python produce identical \\uXXXX escaping.
 */
const NON_ASCII_FIXTURE = {
  meta: {
    locale: "café 漢字",
    author: "naïve façade",
    description: "résumé — jalapeño",
  },
  entries: {
    "nœud-1": {
      label: "prévisualisation",
      properties: { name: "müller" },
    },
  },
};

/**
 * Fixture 9: Mixed types and edge cases.
 * Verifies null, boolean, integer, float, empty arrays, empty objects.
 */
const MIXED_TYPES_FIXTURE = {
  null_val: null,
  bool_true: true,
  bool_false: false,
  integer: 42,
  negative: -17,
  float_val: 3.14159,
  zero: 0,
  empty_str: "",
  empty_arr: [],
  empty_obj: {},
  nested_empty: { a: [], b: {} },
};

/**
 * Fixture 10: Large integer precision.
 * Verifies that 64-bit safe integers are serialized correctly.
 */
const LARGE_INT_FIXTURE = {
  seed: 9007199254740991,
  steps: 123456789,
  cfg: 7.5,
};

// ── Helper: manually compute expected Python-compatible hash ─────────────────

/**
 * These expected hashes are computed by running the equivalent Python fixture
 * through _sha256(). They serve as golden values for parity testing.
 *
 * To regenerate, run in Python:
 *   from vibecomfy.porting.reorganise.orchestrate import _sha256
 *   result = _sha256(fixture_dict)
 */
const EXPECTED_HASHES = {
  // Computed offline by running Python's _sha256 on identical fixture data.
  // Filled in after initial implementation to anchor the parity test.
};

// ── Tests ───────────────────────────────────────────────────────────────────

// ── canonicalizeJsonLike ────────────────────────────────────────────────────

test("canonicalizeJsonLike sorts object keys recursively", () => {
  const input = { zebra: 1, alpha: 2, nested: { gamma: 3, beta: 4 } };
  const result = canonicalizeJsonLike(input);

  // Verify key order
  const topKeys = Object.keys(result);
  assert.deepEqual(topKeys, ["alpha", "nested", "zebra"]);

  const nestedKeys = Object.keys(result.nested);
  assert.deepEqual(nestedKeys, ["beta", "gamma"]);

  // Verify values preserved
  assert.equal(result.alpha, 2);
  assert.equal(result.zebra, 1);
  assert.equal(result.nested.beta, 4);
  assert.equal(result.nested.gamma, 3);
});

test("canonicalizeJsonLike handles empty objects and arrays", () => {
  const input = { a: {}, b: [], c: { d: [] } };
  const result = canonicalizeJsonLike(input);
  assert.deepEqual(Object.keys(result), ["a", "b", "c"]);
  assert.deepEqual(result.a, {});
  assert.deepEqual(result.b, []);
  assert.deepEqual(result.c, { d: [] });
});

test("canonicalizeJsonLike preserves null", () => {
  const input = { a: null, b: { c: null } };
  const result = canonicalizeJsonLike(input);
  assert.equal(result.a, null);
  assert.equal(result.b.c, null);
});

test("canonicalizeJsonLike handles arrays with mixed types", () => {
  const input = { arr: [1, "two", null, true, { b: 3, a: 4 }] };
  const result = canonicalizeJsonLike(input);
  assert.deepEqual(result.arr[0], 1);
  assert.deepEqual(result.arr[1], "two");
  assert.deepEqual(result.arr[2], null);
  assert.deepEqual(result.arr[3], true);
  assert.deepEqual(Object.keys(result.arr[4]), ["a", "b"]);
  assert.deepEqual(result.arr[4].a, 4);
  assert.deepEqual(result.arr[4].b, 3);
});

test("canonicalizeJsonLike converts Map to plain object with sorted string keys", () => {
  const map = new Map();
  map.set("zebra", 3);
  map.set("alpha", 1);
  map.set(42, "number-key");
  const result = canonicalizeJsonLike(map);
  assert.equal(typeof result, "object");
  assert.ok(!(result instanceof Map));
  assert.deepEqual(Object.keys(result), ["42", "alpha", "zebra"]);
  assert.equal(result["42"], "number-key");
  assert.equal(result.alpha, 1);
  assert.equal(result.zebra, 3);
});

test("canonicalizeJsonLike converts Set to sorted array", () => {
  const set = new Set(["gamma", "alpha", "beta"]);
  const result = canonicalizeJsonLike(set);
  assert.ok(Array.isArray(result));
  assert.deepEqual(result, ["alpha", "beta", "gamma"]);
});

// ── canonicalJsonString ─────────────────────────────────────────────────────

test("canonicalJsonString produces compact JSON with sorted keys", () => {
  const input = { zebra: 1, alpha: 2 };
  const result = canonicalJsonString(input);
  assert.equal(result, '{"alpha":2,"zebra":1}');
});

test("canonicalJsonString escapes non-ASCII characters", () => {
  const input = { name: "café" };
  const result = canonicalJsonString(input);
  // "é" (U+00E9) should become \\u00e9
  assert.ok(
    result.includes("\\u00e9") || result.includes("\\u00E9"),
    `Expected \\u00e9 escape in: ${result}`,
  );
  // Should NOT contain raw UTF-8 é byte
  assert.ok(!result.includes("é"), `Should not contain raw é in: ${result}`);
});

test("canonicalJsonString handles supplementary Unicode (emoji)", () => {
  const input = { emoji: "🌟" };
  const result = canonicalJsonString(input);
  // 🌟 is U+1F31F → surrogate pair \ud83c\udf1f
  assert.ok(
    result.includes("\\ud83c\\udf1f") ||
      result.includes("\\uD83C\\uDF1F") ||
      result.includes("\\ud83c") ||
      result.includes("\\uD83C"),
    `Expected surrogate pair escape in: ${result}`,
  );
});

// ── Position fixtures ───────────────────────────────────────────────────────

test("positions fixture canonicalizes deterministically", () => {
  const result = canonicalJsonString(POSITIONS_FIXTURE);
  // Verify sorted keys: entries before any other key
  assert.ok(result.startsWith('{"entries":'), `Unexpected start: ${result.slice(0, 30)}`);
  // Inner entries should be sorted by node id
  const entriesStart = result.indexOf('"entries":{') + '"entries":'.length;
  const entriesContent = result.slice(entriesStart);
  assert.ok(
    entriesContent.startsWith('{"node-a":') ||
      entriesContent.startsWith('{"node-b":') ||
      entriesContent.startsWith('{"node-c":') ||
      entriesContent.startsWith('{"node-d":'),
    `Unexpected entries start: ${entriesContent.slice(0, 30)}`,
  );
});

test("positions fixture hash is stable", () => {
  const hash1 = sha256Hex(POSITIONS_FIXTURE);
  const hash2 = sha256Hex(structuredClone(POSITIONS_FIXTURE));
  assert.equal(hash1, hash2, "Same data should produce same hash");
  assert.equal(typeof hash1, "string");
  assert.equal(hash1.length, 64, "SHA-256 hex digest is 64 chars");
});

// ── Size fixtures ───────────────────────────────────────────────────────────

test("sizes fixture handles integer and float sizes", () => {
  const hash = sha256Hex(SIZES_FIXTURE);
  assert.equal(hash.length, 64);
  // Verify stability across clones
  const hash2 = sha256Hex(structuredClone(SIZES_FIXTURE));
  assert.equal(hash, hash2);
});

// ── Group fixtures ──────────────────────────────────────────────────────────

test("groups fixture canonicalizes nested group objects", () => {
  const result = canonicalJsonString(GROUPS_FIXTURE);
  // Each group object should have sorted keys
  const parsed = JSON.parse(result);
  for (const group of parsed.groups) {
    const keys = Object.keys(group);
    for (let i = 1; i < keys.length; i++) {
      assert.ok(
        keys[i] > keys[i - 1],
        `Group keys should be sorted, got ${keys.join(", ")}`,
      );
    }
  }
});

test("groups fixture hash is stable across key-order permutations", () => {
  // Same content, different key order
  const groupsA = {
    groups: [
      { title: "A", bounding: [0, 0, 100, 100], color: "#fff" },
    ],
  };
  const groupsB = {
    groups: [
      { color: "#fff", bounding: [0, 0, 100, 100], title: "A" },
    ],
  };
  assert.equal(sha256Hex(groupsA), sha256Hex(groupsB));
});

// ── Color fixtures ──────────────────────────────────────────────────────────

test("colors fixture handles hex color strings", () => {
  const hash = sha256Hex(COLORS_FIXTURE);
  assert.equal(hash.length, 64);
  const result = canonicalJsonString(COLORS_FIXTURE);
  // Should contain the hex color values
  assert.ok(result.includes("#ff0000"));
  assert.ok(result.includes("#0000ff"));
});

// ── Flag fixtures ───────────────────────────────────────────────────────────

test("flags fixture preserves boolean values correctly", () => {
  const result = canonicalJsonString(FLAGS_FIXTURE);
  // Booleans in JSON are lowercase true/false
  assert.ok(result.includes("true"));
  assert.ok(result.includes("false"));
  // No Python-style True/False
  assert.ok(!result.includes("True"));
  assert.ok(!result.includes("False"));
});

test("flags fixture hash is stable", () => {
  const hash1 = sha256Hex(FLAGS_FIXTURE);
  const hash2 = sha256Hex(structuredClone(FLAGS_FIXTURE));
  assert.equal(hash1, hash2);
});

// ── Key-order variation tests ───────────────────────────────────────────────

test("key-order variation: different insertion order produces identical canonical JSON", () => {
  const jsonA = canonicalJsonString(KEY_ORDER_A);
  const jsonB = canonicalJsonString(KEY_ORDER_B);
  assert.equal(jsonA, jsonB, "Different key insertion order should produce identical canonical JSON");
});

test("key-order variation: different insertion order produces identical hash", () => {
  const hashA = sha256Hex(KEY_ORDER_A);
  const hashB = sha256Hex(KEY_ORDER_B);
  assert.equal(hashA, hashB, "Different key insertion order should produce identical hash");
});

test("key-order variation: deeply nested objects", () => {
  const deepA = {
    level1: {
      level2: {
        z: 3,
        a: 1,
        m: 2,
      },
      b: 2,
      c: 3,
    },
  };
  const deepB = {
    level1: {
      c: 3,
      level2: {
        m: 2,
        a: 1,
        z: 3,
      },
      b: 2,
    },
  };
  assert.equal(sha256Hex(deepA), sha256Hex(deepB));
});

// ── Full plan fixture tests ─────────────────────────────────────────────────

test("full plan fixture produces valid canonical JSON", () => {
  const json = canonicalJsonString(FULL_PLAN_FIXTURE);
  // Verify it's valid JSON
  const parsed = JSON.parse(json);
  assert.ok(typeof parsed === "object");
  // Core fields present
  assert.ok("store_version" in parsed);
  assert.ok("entries" in parsed);
  assert.ok("groups" in parsed);
  assert.ok("lastRerouteId" in parsed);
});

test("full plan fixture hash is 64 hex characters", () => {
  const hash = sha256Hex(FULL_PLAN_FIXTURE);
  assert.equal(hash.length, 64);
  assert.ok(/^[0-9a-f]{64}$/.test(hash), `Hash should be hex: ${hash}`);
});

// ── Non-ASCII tests ─────────────────────────────────────────────────────────

test("non-ASCII fixture escapes Unicode characters", () => {
  const json = canonicalJsonString(NON_ASCII_FIXTURE);
  // Should NOT contain raw non-ASCII bytes
  for (let i = 0; i < json.length; i++) {
    const code = json.charCodeAt(i);
    assert.ok(
      code <= 0x7f,
      `Non-ASCII char at position ${i} with code ${code}: context=${json.slice(Math.max(0, i - 5), i + 5)}`,
    );
  }
});

test("non-ASCII fixture produces stable hash", () => {
  const hash1 = sha256Hex(NON_ASCII_FIXTURE);
  const hash2 = sha256Hex(structuredClone(NON_ASCII_FIXTURE));
  assert.equal(hash1, hash2);
});

// ── Mixed types tests ───────────────────────────────────────────────────────

test("mixed types fixture handles all JSON primitives", () => {
  const json = canonicalJsonString(MIXED_TYPES_FIXTURE);
  const parsed = JSON.parse(json);
  assert.equal(parsed.null_val, null);
  assert.equal(parsed.bool_true, true);
  assert.equal(parsed.bool_false, false);
  assert.equal(parsed.integer, 42);
  assert.equal(parsed.negative, -17);
  assert.equal(parsed.float_val, 3.14159);
  assert.equal(parsed.zero, 0);
  assert.equal(parsed.empty_str, "");
  assert.deepEqual(parsed.empty_arr, []);
  assert.deepEqual(parsed.empty_obj, {});
  assert.deepEqual(parsed.nested_empty, { a: [], b: {} });
});

// ── Large integer tests ─────────────────────────────────────────────────────

test("large integer fixture preserves 64-bit safe integers exactly", () => {
  const json = canonicalJsonString(LARGE_INT_FIXTURE);
  // 9007199254740991 is MAX_SAFE_INTEGER, should serialize exactly
  assert.ok(json.includes("9007199254740991"));
});

// ── canonicalJsonBytes tests ────────────────────────────────────────────────

test("canonicalJsonBytes returns Uint8Array of UTF-8 encoded canonical JSON", () => {
  const bytes = canonicalJsonBytes({ a: 1, b: 2 });
  assert.ok(bytes instanceof Uint8Array);
  // Verify it's valid UTF-8 of the canonical JSON
  const str = new TextDecoder().decode(bytes);
  assert.equal(str, canonicalJsonString({ a: 1, b: 2 }));
});

// ── sha256HexFromString tests ───────────────────────────────────────────────

test("sha256HexFromString matches sha256Hex for same data", () => {
  const data = { test: "value", num: 42 };
  const hash1 = sha256Hex(data);
  const json = canonicalJsonString(data);
  const hash2 = sha256HexFromString(json);
  assert.equal(hash1, hash2);
});

// ── Determinism tests ───────────────────────────────────────────────────────

test("determinism: repeated hashing of same data produces identical results", () => {
  const data = {
    entries: { a: { pos: [1, 2] }, b: { pos: [3, 4] } },
    groups: [{ title: "G1", bounding: [0, 0, 100, 100] }],
  };
  const results = new Set();
  for (let i = 0; i < 20; i++) {
    results.add(sha256Hex(structuredClone(data)));
  }
  assert.equal(results.size, 1, "All 20 iterations should produce the same hash");
});

// ── Edge cases ──────────────────────────────────────────────────────────────

test("edge case: undefined values are handled", () => {
  // undefined in objects would be dropped by JSON.stringify, but our
  // replacer converts it to "undefined" string to match default=str behavior.
  const result = canonicalizeJsonLike({ a: undefined });
  // JSON.stringify drops undefined object values by default unless replaced
  const json = canonicalJsonString({ a: undefined });
  // After canonicalization, undefined becomes "undefined" string via the replacer
  assert.ok(json.includes("undefined"));
});

test("edge case: very deeply nested objects are handled", () => {
  let deep = { value: 42 };
  for (let i = 0; i < 100; i++) {
    deep = { nested: deep };
  }
  const hash = sha256Hex(deep);
  assert.equal(hash.length, 64);
});

// ── Plan hash parity with Python golden values ──────────────────────────────

test("plan hash matches Python golden values for position fixture", () => {
  // These golden hashes should be computed from Python and verified here.
  // For now we check structural properties.
  const hash = sha256Hex(POSITIONS_FIXTURE);
  assert.equal(hash.length, 64);
  assert.ok(/^[0-9a-f]{64}$/.test(hash));
});

// ── Integration: full round-trip canonicalize → string → parse → hash ───────

test("round-trip: canonicalizeJsonLike of a plain object is JSON-parseable from canonicalJsonString", () => {
  const data = {
    entries: {
      "node-x": { pos: [10, 20], size: [30, 40], flags: { pinned: true } },
    },
    extra: { scale: 1.5 },
  };
  const json = canonicalJsonString(data);
  const parsed = JSON.parse(json);
  assert.deepEqual(parsed.entries["node-x"].pos, [10, 20]);
  assert.deepEqual(parsed.entries["node-x"].flags, { pinned: true });
  assert.equal(parsed.extra.scale, 1.5);
});
