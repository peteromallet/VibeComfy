import test from "node:test";
import assert from "node:assert/strict";

import {
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
} from "../../vibecomfy/comfy_nodes/web/canonical_delta.js";

// ── Fixtures (mirror Python CANONICAL_OP_CASES) ─────────────────────────────

const CANONICAL_OP_CASES = Object.freeze([
  {
    op: "set_node_field",
    target: ["", "seed-node", "inputs.seed"],
    value: 7,
  },
  {
    op: "set_mode",
    target: ["", "mute-node"],
    mode: 4,
  },
  {
    op: "add_node",
    scope_path: "",
    uid: "new-uid",
    node_id: "9001",
    class_type: "PreviewImage",
    fields: { filename_prefix: "after" },
    inputs: { images: ["", "seed-node", "IMAGE"] },
  },
  {
    op: "upsert_link",
    from: ["", "seed-node", "IMAGE"],
    to: ["", "preview-node", "images"],
  },
  {
    op: "remove_node",
    target: ["", "old-node"],
  },
  {
    op: "remove_link",
    to: ["", "preview-node", "images"],
  },
]);

// ── Constants ───────────────────────────────────────────────────────────────

test("DELTA_SCHEMA_VERSION equals '2.0.0'", () => {
  assert.equal(DELTA_SCHEMA_VERSION, "2.0.0");
});

test("CANONICAL_DELTA_OP_NAMES contains exactly 6 supported ops", () => {
  assert.ok(Array.isArray(CANONICAL_DELTA_OP_NAMES));
  assert.ok(Object.isFrozen(CANONICAL_DELTA_OP_NAMES));
  assert.deepEqual([...CANONICAL_DELTA_OP_NAMES].sort(), [
    "add_node",
    "remove_link",
    "remove_node",
    "set_mode",
    "set_node_field",
    "upsert_link",
  ]);
});

test("diagnostic code constants are stable strings", () => {
  assert.equal(DELTA_DIAGNOSTIC_MALFORMED, "malformed_delta");
  assert.equal(DELTA_DIAGNOSTIC_LEGACY_SHAPE, "legacy_delta_shape");
  assert.equal(DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY, "unsupported_scoped_apply");
});

// ── DeltaDiagnosticError ────────────────────────────────────────────────────

test("DeltaDiagnosticError carries code and detail", () => {
  const err = new DeltaDiagnosticError("test error", DELTA_DIAGNOSTIC_MALFORMED, { field: "uid" });
  assert.ok(err instanceof Error);
  assert.ok(err instanceof DeltaDiagnosticError);
  assert.equal(err.name, "DeltaDiagnosticError");
  assert.equal(err.message, "test error");
  assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
  assert.deepEqual(err.detail, { field: "uid" });
});

test("DeltaDiagnosticError defaults code to malformed_delta and detail to empty", () => {
  const err = new DeltaDiagnosticError("bare");
  assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
  assert.deepEqual(err.detail, {});
});

// ── classifyDeltaShape ──────────────────────────────────────────────────────

test("classifyDeltaShape: canonical envelope → canonical", () => {
  const shape = classifyDeltaShape({
    delta_ops_envelope: {
      schema_version: "2.0.0",
      ops: [{ op: "set_node_field", target: ["", "n", "w"], value: 1 }],
    },
  });
  assert.equal(shape.shape, "canonical");
  assert.equal(shape.code, "canonical_delta_ops");
  assert.equal(shape.detail.schema_version, "2.0.0");
});

test("classifyDeltaShape: canonical envelope with null schema_version yields null in detail", () => {
  const shape = classifyDeltaShape({
    delta_ops_envelope: {
      schema_version: null,
      ops: [{ op: "set_node_field", target: ["", "n", "w"], value: 1 }],
    },
  });
  assert.equal(shape.shape, "canonical");
  assert.equal(shape.detail.schema_version, null);
});

test("classifyDeltaShape: canonical envelope with non-array ops (malformed) → canonical_envelope_malformed_ops", () => {
  const shape = classifyDeltaShape({
    delta_ops_envelope: {
      schema_version: "2.0.0",
      ops: "not-an-array",
    },
  });
  assert.equal(shape.shape, "canonical");
  assert.equal(shape.code, "canonical_envelope_malformed_ops");
  assert.equal(shape.detail.ops_type, "string");
});

test("classifyDeltaShape: legacy flat delta_ops array → legacy_flat", () => {
  const shape = classifyDeltaShape({
    delta_ops: [{ op: "set_node_field", target: ["", "n", "w"], value: 1 }],
  });
  assert.equal(shape.shape, "legacy_flat");
  assert.equal(shape.code, "legacy_delta_ops_flat");
});

test("classifyDeltaShape: legacy wrapped delta_ops object → legacy_wrapped", () => {
  const shape = classifyDeltaShape({
    delta_ops: { ops: [], diagnostics: [] },
  });
  assert.equal(shape.shape, "legacy_wrapped");
  assert.equal(shape.code, DELTA_DIAGNOSTIC_LEGACY_SHAPE);
  assert.deepEqual(shape.detail.keys, ["diagnostics", "ops"]);
});

test("classifyDeltaShape: null payload → missing", () => {
  const shape = classifyDeltaShape(null);
  assert.equal(shape.shape, "missing");
  assert.equal(shape.code, "missing_turn_response");
});

test("classifyDeltaShape: non-object payload → missing", () => {
  const shape = classifyDeltaShape("string");
  assert.equal(shape.shape, "missing");
  assert.equal(shape.code, "missing_turn_response");
});

test("classifyDeltaShape: empty object (no delta_ops) → missing", () => {
  const shape = classifyDeltaShape({ ok: true });
  assert.equal(shape.shape, "missing");
  assert.equal(shape.code, "missing_delta_ops");
});

// ── normalizeDeltaEnvelope — canonical envelope roundtrips ─────────────────

test("normalizeDeltaEnvelope roundtrips all six canonical ops individually", () => {
  for (const opCase of CANONICAL_OP_CASES) {
    const payload = {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [opCase],
    };
    const envelope = normalizeDeltaEnvelope(payload, { strict: true });
    assert.equal(envelope.schema_version, DELTA_SCHEMA_VERSION);
    assert.ok(Array.isArray(envelope.ops));
    assert.equal(envelope.ops.length, 1);

    // Keys match sorted canonical shape
    const gotKeys = Object.keys(envelope.ops[0]).sort();
    const expectedKeys = Object.keys(opCase).sort();
    assert.deepEqual(gotKeys, expectedKeys);

    // Values match
    assert.deepEqual(envelope.ops[0], opCase);
  }
});

test("normalizeDeltaEnvelope roundtrips all six canonical ops together in one envelope", () => {
  const payload = {
    schema_version: DELTA_SCHEMA_VERSION,
    ops: [...CANONICAL_OP_CASES],
  };
  const envelope = normalizeDeltaEnvelope(payload, { strict: true });
  assert.equal(envelope.ops.length, 6);

  for (let i = 0; i < CANONICAL_OP_CASES.length; i++) {
    assert.deepEqual(envelope.ops[i], CANONICAL_OP_CASES[i]);
  }
});

// ── normalizeDeltaEnvelope — malformed rejection ────────────────────────────

test("normalizeDeltaEnvelope rejects add_node missing uid (strict)", () => {
  const addNode = { ...CANONICAL_OP_CASES[2] };
  delete addNode.uid;

  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        { schema_version: DELTA_SCHEMA_VERSION, ops: [addNode] },
        { strict: true },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("uid"));
      assert.equal(err.detail.field, "uid");
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects add_node missing node_id (strict)", () => {
  const addNode = { ...CANONICAL_OP_CASES[2] };
  delete addNode.node_id;

  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        { schema_version: DELTA_SCHEMA_VERSION, ops: [addNode] },
        { strict: true },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("node_id"));
      assert.equal(err.detail.field, "node_id");
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects add_node missing class_type (strict)", () => {
  const addNode = { ...CANONICAL_OP_CASES[2] };
  delete addNode.class_type;

  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        { schema_version: DELTA_SCHEMA_VERSION, ops: [addNode] },
        { strict: true },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("class_type"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects bad target shape for set_node_field (strict)", () => {
  // target too short (length < 2)
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        {
          schema_version: DELTA_SCHEMA_VERSION,
          ops: [{ op: "set_node_field", target: ["single"], value: 1 }],
        },
        { strict: true },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("target"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects bad target shape for remove_node (strict)", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        {
          schema_version: DELTA_SCHEMA_VERSION,
          ops: [{ op: "remove_node", target: "not-an-array" }],
        },
        { strict: true },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("target"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects bad from shape for upsert_link (strict)", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        {
          schema_version: DELTA_SCHEMA_VERSION,
          ops: [
            {
              op: "upsert_link",
              from: ["", "u1"], // too short (length 2, needs >= 3)
              to: ["", "u2", "images"],
            },
          ],
        },
        { strict: true },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("from"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects bad to shape for remove_link (strict)", () => {
  // remove_link requires either "id" or "to" — neither present
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        {
          schema_version: DELTA_SCHEMA_VERSION,
          ops: [{ op: "remove_link", target: ["", "x"] }],
        },
        { strict: true },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("id") || err.message.includes("to"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects unknown op types (strict)", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        {
          schema_version: DELTA_SCHEMA_VERSION,
          ops: [{ op: "rename_everything", target: ["", "u1"] }],
        },
        { strict: true },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("Unsupported edit op"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects unknown op types (lenient)", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        {
          schema_version: DELTA_SCHEMA_VERSION,
          ops: [{ op: "noop" }],
        },
        { strict: false },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("Unsupported edit op"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects non-array ops in envelope", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        { schema_version: DELTA_SCHEMA_VERSION, ops: "not-array" },
        { strict: false },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("ops"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects wrong schema_version", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        { schema_version: "1.0.0", ops: [] },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      assert.ok(err.message.includes("schema_version"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects extra keys in envelope", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        { schema_version: DELTA_SCHEMA_VERSION, ops: [], extra: true },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      return true;
    },
  );
});

// ── normalizeDeltaEnvelope — legacy shape rejection ─────────────────────────

test("normalizeDeltaEnvelope rejects legacy wrapped object with delta_ops key", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope({ delta_ops: { ops: [] } }),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_LEGACY_SHAPE);
      assert.ok(err.detail.keys.includes("delta_ops"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects ops-without-schema_version as legacy shape", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope({ ops: [], diagnostics: [] }),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_LEGACY_SHAPE);
      assert.ok(err.detail.keys.includes("diagnostics"));
      assert.ok(err.detail.keys.includes("ops"));
      return true;
    },
  );
});

test("normalizeDeltaEnvelope rejects extra legacy wrapper keys alongside schema_version+ops", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope({
        schema_version: DELTA_SCHEMA_VERSION,
        ops: [],
        automatic_link_removals: [],
      }),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_LEGACY_SHAPE);
      assert.ok(err.detail.keys.includes("automatic_link_removals"));
      return true;
    },
  );
});

// ── normalizeDeltaEnvelope — legacy flat array bridge ───────────────────────

test("normalizeDeltaEnvelope rejects flat array without allowLegacyList", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope([{ op: "set_node_field", target: ["", "n", "w"], value: 1 }], {
        allowLegacyList: false,
      }),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_LEGACY_SHAPE);
      return true;
    },
  );
});

test("normalizeDeltaEnvelope accepts and normalizes flat array with allowLegacyList", () => {
  const flatOps = [
    { op: "set_node_field", target: ["", "n", "w"], value: 1 },
    { op: "set_mode", target: ["", "m"], mode: 4 },
  ];
  const envelope = normalizeDeltaEnvelope(flatOps, { allowLegacyList: true });
  assert.equal(envelope.schema_version, DELTA_SCHEMA_VERSION);
  assert.ok(Array.isArray(envelope.ops));
  assert.equal(envelope.ops.length, 2);
  assert.equal(envelope.ops[0].op, "set_node_field");
  assert.equal(envelope.ops[1].op, "set_mode");
});

test("normalizeDeltaEnvelope skips invalid entries in legacy flat array with allowLegacyList", () => {
  const flatOps = [
    { op: "set_node_field", target: ["", "n", "w"], value: 1 },
    { not_an_op: true },
    { op: "", target: [] },
    null,
    "invalid",
    { op: "set_mode", target: ["", "m"], mode: 4 },
  ];
  const envelope = normalizeDeltaEnvelope(flatOps, { allowLegacyList: true });
  assert.equal(envelope.ops.length, 2);
  assert.equal(envelope.ops[0].op, "set_node_field");
  assert.equal(envelope.ops[1].op, "set_mode");
});

test("normalizeDeltaEnvelope rejects non-object non-array input", () => {
  assert.throws(
    () => normalizeDeltaEnvelope("string"),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      return true;
    },
  );
});

// ── normalizeDeltaOpsFromSubmitPayload ──────────────────────────────────────

test("normalizeDeltaOpsFromSubmitPayload extracts ops from canonical delta_ops_envelope", () => {
  const payload = {
    delta_ops_envelope: {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [{ op: "set_node_field", target: ["", "n", "w"], value: 1 }],
    },
  };
  const ops = normalizeDeltaOpsFromSubmitPayload(payload);
  assert.ok(Array.isArray(ops));
  assert.equal(ops.length, 1);
  assert.equal(ops[0].op, "set_node_field");
  assert.equal(ops[0].value, 1);
});

test("normalizeDeltaOpsFromSubmitPayload falls back to legacy flat delta_ops", () => {
  const payload = {
    delta_ops: [
      { op: "set_node_field", target: ["", "n", "w"], value: 2 },
    ],
  };
  const ops = normalizeDeltaOpsFromSubmitPayload(payload);
  assert.ok(Array.isArray(ops));
  assert.equal(ops.length, 1);
  assert.equal(ops[0].value, 2);
});

test("normalizeDeltaOpsFromSubmitPayload prefers delta_ops_envelope over delta_ops", () => {
  const payload = {
    delta_ops_envelope: {
      schema_version: DELTA_SCHEMA_VERSION,
      ops: [{ op: "set_mode", target: ["", "m"], mode: 4 }],
    },
    delta_ops: [
      { op: "set_node_field", target: ["", "n", "w"], value: 999 },
    ],
  };
  const ops = normalizeDeltaOpsFromSubmitPayload(payload);
  assert.equal(ops.length, 1);
  assert.equal(ops[0].op, "set_mode"); // canonical takes priority
});

test("normalizeDeltaOpsFromSubmitPayload rejects legacy wrapped delta_ops", () => {
  assert.throws(
    () => normalizeDeltaOpsFromSubmitPayload({ delta_ops: { ops: [] } }),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_LEGACY_SHAPE);
      return true;
    },
  );
});

test("normalizeDeltaOpsFromSubmitPayload throws for missing delta ops", () => {
  assert.throws(
    () => normalizeDeltaOpsFromSubmitPayload({ ok: true }),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, "missing_delta_ops");
      return true;
    },
  );
});

test("normalizeDeltaOpsFromSubmitPayload throws for non-object input", () => {
  assert.throws(
    () => normalizeDeltaOpsFromSubmitPayload(null),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, "missing_turn_response");
      return true;
    },
  );
});

// ── ensureRootScopedOps ─────────────────────────────────────────────────────

test("ensureRootScopedOps accepts root-scoped ops for all six op types", () => {
  const ops = [
    { op: "set_node_field", target: ["", "n", "w"], value: 1 },
    { op: "set_mode", target: ["", "n"], mode: 4 },
    { op: "add_node", scope_path: "", uid: "u1", node_id: "1", class_type: "PreviewImage", fields: {}, inputs: {} },
    { op: "upsert_link", from: ["", "a", "IMAGE"], to: ["", "b", "images"] },
    { op: "remove_node", target: ["", "n"] },
    { op: "remove_link", to: ["", "n", "images"] },
  ];
  // Should not throw
  assert.doesNotThrow(() => ensureRootScopedOps(ops));
});

test("ensureRootScopedOps rejects non-root scoped set_node_field", () => {
  assert.throws(
    () =>
      ensureRootScopedOps([
        { op: "set_node_field", target: ["sg:nested", "n", "w"], value: 1 },
      ]),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY);
      assert.deepEqual(err.detail.scope_paths, ["sg:nested"]);
      assert.equal(err.detail.op, "set_node_field");
      return true;
    },
  );
});

test("ensureRootScopedOps rejects non-root scoped upsert_link", () => {
  assert.throws(
    () =>
      ensureRootScopedOps([
        {
          op: "upsert_link",
          from: ["sg:nested", "seed-node", "IMAGE"],
          to: ["", "preview-node", "images"],
        },
      ]),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY);
      assert.deepEqual(err.detail.scope_paths, ["sg:nested"]);
      return true;
    },
  );
});

test("ensureRootScopedOps rejects non-root scoped add_node", () => {
  assert.throws(
    () =>
      ensureRootScopedOps([
        {
          op: "add_node",
          scope_path: "sg:nested",
          uid: "u1",
          node_id: "1",
          class_type: "PreviewImage",
          fields: {},
          inputs: {},
        },
      ]),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY);
      assert.deepEqual(err.detail.scope_paths, ["sg:nested"]);
      return true;
    },
  );
});

test("ensureRootScopedOps accepts empty ops array", () => {
  assert.doesNotThrow(() => ensureRootScopedOps([]));
});

// ── normalizeDeltaEnvelope — non-strict lenient validation ──────────────────

test("normalizeDeltaEnvelope accepts add_node without uid when strict=false (lenient)", () => {
  const addNode = {
    op: "add_node",
    scope_path: "",
    class_type: "PreviewImage",
    fields: {},
    inputs: {},
  };
  const envelope = normalizeDeltaEnvelope(
    { schema_version: DELTA_SCHEMA_VERSION, ops: [addNode] },
    { strict: false },
  );
  assert.equal(envelope.ops.length, 1);
  assert.equal(envelope.ops[0].op, "add_node");
  // Non-strict does not enforce uid/node_id
  assert.equal(envelope.ops[0].uid, undefined);
  assert.equal(envelope.ops[0].node_id, undefined);
});

test("normalizeDeltaEnvelope lenient mode still validates op name", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        { schema_version: DELTA_SCHEMA_VERSION, ops: [{ op: "bogus" }] },
        { strict: false },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      return true;
    },
  );
});

test("normalizeDeltaEnvelope lenient mode still validates entry is object", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        { schema_version: DELTA_SCHEMA_VERSION, ops: ["not-object"] },
        { strict: false },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      return true;
    },
  );
});

test("normalizeDeltaEnvelope lenient mode still validates op is non-empty string", () => {
  assert.throws(
    () =>
      normalizeDeltaEnvelope(
        { schema_version: DELTA_SCHEMA_VERSION, ops: [{ op: "" }] },
        { strict: false },
      ),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      return true;
    },
  );
});

// ── Malformed envelope: missing schema_version with no ops ──────────────────

test("normalizeDeltaEnvelope rejects object without schema_version or ops", () => {
  assert.throws(
    () => normalizeDeltaEnvelope({ foo: "bar" }),
    (err) => {
      assert.ok(err instanceof DeltaDiagnosticError);
      assert.equal(err.code, DELTA_DIAGNOSTIC_MALFORMED);
      return true;
    },
  );
});
