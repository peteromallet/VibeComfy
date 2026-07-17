import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

import {
  MATERIALIZATION_KINDS,
  MUTATION_MATERIALIZATION_CONTRACT_V1,
  MUTATION_MATERIALIZATION_WIRE_VERSION,
  MutationMaterializationError,
  assertMutationMaterializationEnvelope,
  computeMutationMaterializationDigest,
  normalizeMutationMaterializationV1,
} from "../../vibecomfy/comfy_nodes/web/mutation_materialization_v1.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const GOLDEN = JSON.parse(
  await readFile(path.join(root, "tests/fixtures/agent_edit/mutation_materialization_golden_v1.json"), "utf8"),
);

function envelope(entries, accompanyingOps, digestOverride) {
  const digest = digestOverride ?? computeMutationMaterializationDigest(entries, accompanyingOps);
  return {
    contract_version: MUTATION_MATERIALIZATION_CONTRACT_V1,
    wire_version: MUTATION_MATERIALIZATION_WIRE_VERSION,
    entries,
    digest,
  };
}

function assertCode(fn, expectedCode) {
  assert.throws(fn, (error) => {
    if (!(error instanceof MutationMaterializationError)) return false;
    assert.equal(error.code, expectedCode, `expected ${expectedCode}, got ${error.code}`);
    return true;
  });
}

test("mutation_materialization golden positive cases produce pinned digests", () => {
  for (const c of GOLDEN.cases) {
    const normalized = normalizeMutationMaterializationV1(
      envelope(c.entries, c.accompanying_ops),
      { accompanyingOps: c.accompanying_ops },
    );
    assert.equal(normalized.digest, c.expected_digest, `digest mismatch for ${c.id}`);
    assert.equal(
      computeMutationMaterializationDigest(c.entries, c.accompanying_ops),
      c.expected_digest,
    );
  }
});

test("mutation_materialization kind is a singleton {add_node}", () => {
  assert.deepEqual([...MATERIALIZATION_KINDS], ["add_node"]);
  assert.equal(MUTATION_MATERIALIZATION_CONTRACT_V1, "mutation_materialization_v1");
  assert.equal(MUTATION_MATERIALIZATION_WIRE_VERSION, "1.0.0");
});

test("mutation_materialization numeric normalisation parity", () => {
  const byId = Object.fromEntries(GOLDEN.parity_cases.map((c) => [c.id, c]));
  assert.equal(
    byId.numeric_normalize_float_negzero.expected_digest,
    byId.numeric_normalize_plain_int.expected_digest,
  );
  for (const c of GOLDEN.parity_cases) {
    assert.equal(computeMutationMaterializationDigest(c.entries, c.accompanying_ops), c.expected_digest);
  }
});

test("mutation_materialization rebind detection fails closed with bound-ops detail", () => {
  const c = GOLDEN.rebind_case;
  const env = envelope(c.entries, c.accompanying_ops_original);
  assert.throws(
    () => assertMutationMaterializationEnvelope(env, { accompanyingOps: c.accompanying_ops_rebind }),
    (error) => {
      assert.equal(error.code, "mutation_materialization_digest_mismatch");
      assert.equal(error.detail.accompanying_ops_bound, true);
      return true;
    },
  );
});

test("mutation_materialization vibecomfy.exec dynamic-IO object widgets pass through", () => {
  const c = GOLDEN.cases.find((x) => x.id === "exec_widgets_object_dynamic_io");
  const normalized = assertMutationMaterializationEnvelope(
    envelope(c.entries, c.accompanying_ops),
    { accompanyingOps: c.accompanying_ops },
  );
  assert.deepEqual(normalized.entries[0].widgets_values.io, { rebuilt: true });
});

test("mutation_materialization negative cases fail closed with exact codes", () => {
  for (const c of GOLDEN.negative_cases) {
    const digest = c.envelope_digest ?? "0".repeat(64);
    const env = envelope(c.entries, c.accompanying_ops, digest);
    assertCode(
      () => assertMutationMaterializationEnvelope(env, { accompanyingOps: c.accompanying_ops }),
      c.expected_code,
    );
  }
});

test("mutation_materialization unknown contract version fails closed", () => {
  const add = GOLDEN.add_node_template;
  const env = envelope([{ source_op_index: 0, kind: "add_node" }], [add]);
  env.contract_version = "mutation_materialization_v9";
  assertCode(
    () => assertMutationMaterializationEnvelope(env, { accompanyingOps: [add] }),
    "unknown_contract",
  );
});

test("mutation_materialization non-finite geometry fails closed (JS inline)", () => {
  const add = GOLDEN.add_node_template;
  const nanEnv = envelope([{ source_op_index: 0, kind: "add_node", pos: [NaN, 2] }], [add], "0".repeat(64));
  assertCode(
    () => assertMutationMaterializationEnvelope(nanEnv, { accompanyingOps: [add] }),
    "non_finite_materialization",
  );
});

test("mutation_materialization boolean and unsafe-integer geometry fail with non_canonical_number (cross-language)", () => {
  const add = GOLDEN.add_node_template;
  const geo = (x) => envelope(
    [{ source_op_index: 0, kind: "add_node", pos: [x, 2] }],
    [add],
    "0".repeat(64),
  );
  // Boolean in geometry — parity with Python's bool rejection.
  assertCode(
    () => assertMutationMaterializationEnvelope(geo(true), { accompanyingOps: [add] }),
    "non_canonical_number",
  );
  // +2^53 — exactly representable double but exceeds the safe integer range.
  assertCode(
    () => assertMutationMaterializationEnvelope(geo(Math.pow(2, 53)), { accompanyingOps: [add] }),
    "non_canonical_number",
  );
  // -2^53.
  assertCode(
    () => assertMutationMaterializationEnvelope(geo(-Math.pow(2, 53)), { accompanyingOps: [add] }),
    "non_canonical_number",
  );
  // 2^60 — JS Number's shortest round-trippable spelling differs from the
  // exact decimal Python emits, so it is non-canonical.
  assertCode(
    () => assertMutationMaterializationEnvelope(geo(Math.pow(2, 60)), { accompanyingOps: [add] }),
    "non_canonical_number",
  );
});

test("mutation_materialization safe-integer boundary (2^53-1) remains canonical (cross-language)", () => {
  const byId = Object.fromEntries(GOLDEN.parity_cases.map((c) => [c.id, c]));
  const boundary = byId.numeric_normalize_safe_integer_boundary;
  assert.equal(
    computeMutationMaterializationDigest(boundary.entries, boundary.accompanying_ops),
    boundary.expected_digest,
  );
});
