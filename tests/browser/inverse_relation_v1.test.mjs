// Inverse-relation parity tests (§3.2 / §5.1).
//
// Loads the same golden fixture as the Python test and asserts every positive
// case passes and every negative case throws the exact expected diagnostic code.

import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  assertInverseRelation,
  digest,
  forwardOperationDigest,
} from "../../vibecomfy/comfy_nodes/web/prepared_authority_v1.js";
import { sha256Hex } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const fixture = JSON.parse(
  await readFile(path.join(root, "tests/fixtures/agent_edit/inverse_relation_golden_v1.json"), "utf8"),
);

function runCase(case_) {
  if (case_.expected === "ok") {
    assertInverseRelation(case_.forward_ops, case_.inverse_ops, case_.family);
    return;
  }
  assert.throws(
    () => assertInverseRelation(case_.forward_ops, case_.inverse_ops, case_.family),
    (error) => {
      assert.equal(error.code, case_.expected_code, `${case_.id}: expected ${case_.expected_code}, got ${error.code}`);
      return true;
    },
    `${case_.id}: expected to throw`,
  );
}

test("inverse-relation golden: structural cases", () => {
  for (const case_ of fixture.structural_cases) runCase(case_);
});

test("inverse-relation golden: layout cases", () => {
  for (const case_ of fixture.layout_cases) runCase(case_);
});

test("empty forward and inverse is valid", () => {
  assertInverseRelation([], [], "structural");
});

test("empty inverse with forward is unrelated", () => {
  assert.throws(
    () => assertInverseRelation(
      [{ op: "set_node_field", target: ["", "uid-1", "f"], value: "n" }],
      [],
      "structural",
    ),
    (error) => error.code === "inverse_unrelated",
  );
});

test("unrelated inverse shares no identity", () => {
  assert.throws(
    () => assertInverseRelation(
      [{ op: "set_node_field", target: ["", "uid-A", "f"], value: "n" }],
      [{ op: "set_node_field", target: ["", "uid-B", "f"], value: "o" }],
      "structural",
    ),
    (error) => error.code === "inverse_identity_unbound",
  );
});

const REWIRE_FORWARD = [
  { op: "remove_link", to: ["", "dst-1", "images"] },
  { op: "upsert_link", from: ["", "src-new", "IMAGE"], to: ["", "dst-1", "images"] },
];
const REWIRE_INVERSE = [
  { op: "remove_link", to: ["", "dst-1", "images"] },
  { op: "upsert_link", from: ["", "src-old", "IMAGE"], to: ["", "dst-1", "images"] },
];
const REWIRE_WITNESSES = [
  { from: ["", "src-old", "IMAGE"], to: ["", "dst-1", "images"] },
];

function v2Restoration({
  forwardOps = REWIRE_FORWARD,
  inverseOps = REWIRE_INVERSE,
  witnesses = REWIRE_WITNESSES,
  forwardDigest = null,
} = {}) {
  const payload = {
    ops: inverseOps,
    forward_operation_digest: forwardDigest || forwardOperationDigest(forwardOps),
    prior_link_witnesses: witnesses,
  };
  return {
    contract_version: "inverse_delta_v2",
    payload,
    digest: sha256Hex({ contract_version: "inverse_delta_v2", payload }),
  };
}

test("inverse_delta_v2 binds exact rewire prior state", () => {
  assert.equal(
    forwardOperationDigest(REWIRE_FORWARD),
    "65f6700bb89c271b2a454a08abd2088c247f927a631dbaca63bb843c97d01e0d",
  );
  digest(v2Restoration(), { family: "structural", forwardOps: REWIRE_FORWARD });
});

test("inverse_delta_v2 requires exact remove_link witness coverage", () => {
  assert.throws(
    () => digest(v2Restoration({ witnesses: [] }), { family: "structural", forwardOps: REWIRE_FORWARD }),
    (error) => error.code === "inverse_missing_prior_state",
  );
});

test("inverse_delta_v2 rejects wrong prior source", () => {
  const witnesses = [{ from: ["", "wrong", "IMAGE"], to: ["", "dst-1", "images"] }];
  assert.throws(
    () => digest(v2Restoration({ witnesses }), { family: "structural", forwardOps: REWIRE_FORWARD }),
    (error) => error.code === "inverse_missing_prior_state",
  );
});

test("inverse_delta_v2 rejects forward digest transplant", () => {
  const forwardDigest = forwardOperationDigest([
    { op: "remove_link", to: ["", "other-dst", "images"] },
  ]);
  assert.throws(
    () => digest(v2Restoration({ forwardDigest }), { family: "structural", forwardOps: REWIRE_FORWARD }),
    (error) => error.code === "forward_operation_digest_mismatch",
  );
});

test("inverse_delta_v2 outer digest binds witness payload", () => {
  const restoration = v2Restoration();
  restoration.payload.prior_link_witnesses = [];
  assert.throws(
    () => digest(restoration, { family: "structural", forwardOps: REWIRE_FORWARD }),
    (error) => error.code === "restoration_digest_mismatch",
  );
});
