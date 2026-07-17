import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

import {
  LAYOUT_OPERATION_CONTRACT_V1,
  LAYOUT_OPERATION_OP_NAMES,
  LAYOUT_OPERATION_WIRE_VERSION,
  LayoutOperationError,
  assertLayoutOperationEnvelope,
  computeLayoutOperationDigest,
  normalizeLayoutOperationV1,
} from "../../vibecomfy/comfy_nodes/web/layout_operation_v1.js";
import { buildStructuralGraphProjection } from "../../vibecomfy/comfy_nodes/web/projection_registry_v1.js";
import { sha256Hex } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const fixturePath = path.join(root, "tests/fixtures/agent_edit/layout_operation_golden_v1.json");
const GOLDEN = JSON.parse(await readFile(fixturePath, "utf8"));
const a664Path = path.join(root, "tests/fixtures/agent_edit/a66422e6_layout_regression.json");

function envelope(ops, overrides = {}) {
  const base = {
    contract_version: LAYOUT_OPERATION_CONTRACT_V1,
    wire_version: LAYOUT_OPERATION_WIRE_VERSION,
    ops,
  };
  if ("digest" in overrides) {
    base.digest = overrides.digest;
    delete overrides.digest;
  } else {
    base.digest = computeLayoutOperationDigest(ops);
  }
  return { ...base, ...overrides };
}

function assertCode(fn, expectedCode) {
  assert.throws(fn, (error) => {
    if (!(error instanceof LayoutOperationError)) {
      return false;
    }
    assert.equal(error.code, expectedCode, `expected ${expectedCode}, got ${error.code}`);
    return true;
  });
}

test("layout_operation golden positive cases produce pinned digests", () => {
  for (const caseItem of GOLDEN.cases) {
    const normalized = normalizeLayoutOperationV1(envelope(caseItem.ops));
    assert.equal(
      normalized.digest,
      caseItem.expected_digest,
      `digest mismatch for ${caseItem.id}`,
    );
    assert.equal(
      computeLayoutOperationDigest(caseItem.ops),
      caseItem.expected_digest,
      `computeLayoutOperationDigest mismatch for ${caseItem.id}`,
    );
  }
});

test("layout_operation op names are exactly four", () => {
  assert.deepEqual([...LAYOUT_OPERATION_OP_NAMES], [
    "set_node_geometry",
    "add_group",
    "set_group_geometry",
    "remove_group",
  ]);
  assert.equal(LAYOUT_OPERATION_CONTRACT_V1, "layout_operation_v1");
  assert.equal(LAYOUT_OPERATION_WIRE_VERSION, "1.0.0");
});

test("layout_operation numeric normalisation produces JS-compatible preimages", () => {
  const byId = Object.fromEntries(GOLDEN.parity_cases.map((c) => [c.id, c]));
  const floatNegZero = byId.numeric_normalize_float_and_negzero.expected_digest;
  const exponent = byId.numeric_normalize_exponent.expected_digest;
  const plainInt = byId.numeric_normalize_plain_int.expected_digest;
  // [1.0, -0.0] and [1, 0] must collapse to the SAME canonical spelling.
  assert.equal(floatNegZero, plainInt);
  // [1e2, 200] is distinct geometry.
  assert.notEqual(exponent, plainInt);
  for (const caseItem of GOLDEN.parity_cases) {
    assert.equal(computeLayoutOperationDigest(caseItem.ops), caseItem.expected_digest);
  }
});

test("layout_operation a66422e6 regression anchor pins three separate digests", async () => {
  const raw = await readFile(a664Path);
  const anchor = GOLDEN.a66422e6_anchor;
  // (1) fixture-integrity (informational)
  const integrity = anchor.fixture_integrity_raw_file;
  assert.equal(integrity.domain, "fixture_integrity_raw_file");
  assert.equal(integrity.informational, true);
  assert.equal(createHash("sha256").update(raw).digest("hex"), integrity.sha256);
  assert.equal(raw.length, integrity.byte_length);
  // (2) structural witness
  const fx = JSON.parse(raw.toString("utf8"));
  assert.equal(
    sha256Hex(buildStructuralGraphProjection(fx.original)),
    anchor.structural_witness_v1.expected_digest,
  );
  assert.equal(anchor.structural_witness_v1.domain, "structural_witness_v1");
  // (3) layout-operation derived case is a separate golden entry.
  const derived = GOLDEN.cases.find((c) => c.id === "a66422e6-derived-candidate-groups");
  assert.equal(computeLayoutOperationDigest(derived.ops), derived.expected_digest);
  assert.notEqual(derived.expected_digest, integrity.sha256);
  assert.notEqual(derived.expected_digest, anchor.structural_witness_v1.expected_digest);
});

test("layout_operation negative cases fail closed with exact codes", () => {
  for (const caseItem of GOLDEN.negative_cases) {
    const env = caseItem.envelope ? { ...caseItem.envelope } : envelope(caseItem.ops, { digest: "0".repeat(64) });
    assertCode(() => assertLayoutOperationEnvelope(env), caseItem.expected_code);
  }
});

test("layout_operation unknown contract version fails closed", () => {
  const env = envelope([]);
  env.contract_version = "layout_operation_v9";
  assertCode(() => assertLayoutOperationEnvelope(env), "unknown_contract");
});

test("layout_operation duplicate identity within a class fails closed", () => {
  const ops = [
    { op: "set_node_geometry", uid: "dup", pos: [1, 2] },
    { op: "set_node_geometry", uid: "dup", pos: [3, 4] },
  ];
  assertCode(() => computeLayoutOperationDigest(ops), "duplicate_identity");
});

test("layout_operation cross-class same id is allowed", () => {
  const ops = [
    { op: "add_group", id: "g", bounding: [1, 2, 3, 4], title: "T", color: null },
    { op: "set_group_geometry", id: "g", title: "T2" },
    { op: "remove_group", id: "g" },
  ];
  assert.ok(computeLayoutOperationDigest(ops));
});

test("layout_operation non-finite geometry fails closed (JS inline)", () => {
  // NaN / Infinity are valid JS runtime values (not loadable from JSON), so
  // these are defined inline rather than in the shared golden.
  const nanEnv = envelope([{ op: "set_node_geometry", uid: "n", pos: [NaN, 2] }], { digest: "0".repeat(64) });
  assertCode(() => assertLayoutOperationEnvelope(nanEnv), "non_finite_geometry");
  const infEnv = envelope([{ op: "set_node_geometry", uid: "n", pos: [1, Infinity] }], { digest: "0".repeat(64) });
  assertCode(() => assertLayoutOperationEnvelope(infEnv), "non_finite_geometry");
});

test("layout_operation boolean and unsafe-integer geometry fail with non_canonical_number (cross-language)", () => {
  // Boolean in a numeric position and integers outside ±(2^53-1) have no
  // canonical spelling both languages agree on.  JS must reject with the SAME
  // diagnostic as Python (non_canonical_number), not a generic geometry code.
  const geo = (x) => envelope(
    [{ op: "set_node_geometry", uid: "n", pos: [x, 2] }],
    { digest: "0".repeat(64) },
  );
  // Boolean — JS does not subclass Boolean from Number, but it must still
  // surface non_canonical_number (parity with Python's bool rejection).
  assertCode(() => assertLayoutOperationEnvelope(geo(true)), "non_canonical_number");
  // +2^53 — exactly representable double but exceeds the safe integer range.
  assertCode(() => assertLayoutOperationEnvelope(geo(Math.pow(2, 53))), "non_canonical_number");
  // -2^53.
  assertCode(() => assertLayoutOperationEnvelope(geo(-Math.pow(2, 53))), "non_canonical_number");
  // 2^60 — JS Number's shortest round-trippable spelling ("...500") differs
  // from the exact decimal Python emits ("...476"), so it is non-canonical.
  assertCode(() => assertLayoutOperationEnvelope(geo(Math.pow(2, 60))), "non_canonical_number");
});

test("layout_operation safe-integer boundary (2^53-1) remains canonical (cross-language)", () => {
  // Number.MAX_SAFE_INTEGER is the largest safe int and must be accepted with
  // an identical digest on both sides (golden parity case
  // numeric_normalize_safe_integer_boundary).
  const byId = Object.fromEntries(GOLDEN.parity_cases.map((c) => [c.id, c]));
  const boundary = byId.numeric_normalize_safe_integer_boundary;
  assert.equal(
    computeLayoutOperationDigest(boundary.ops),
    boundary.expected_digest,
  );
});
