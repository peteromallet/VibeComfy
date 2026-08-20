import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { FIELD_CATEGORY, assertForwardProjectionV1, assertProjectionReferenceV1, buildStructuralGraphProjection, classifyFieldV1, projectGraphV1, projectionReferenceV1, projectionSpecV1 } from "../../vibecomfy/comfy_nodes/web/projection_registry_v1.js";
import { canonicalJsonString } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";
import { validateCandidateTransactionV2, validatePreparedAuthorityV1, acceptedBatchDigest } from "../../vibecomfy/comfy_nodes/web/prepared_authority_v1.js";
import { normalizeDeltaV1 } from "../../vibecomfy/comfy_nodes/web/canonical_delta.js";
import { computeLayoutOperationDigest } from "../../vibecomfy/comfy_nodes/web/layout_operation_v1.js";
import { computeMutationMaterializationDigest } from "../../vibecomfy/comfy_nodes/web/mutation_materialization_v1.js";
import { sha256Hex, canonicalizeContractNumeric } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";
import { classifyLegacyMigrationV1 } from "../../vibecomfy/comfy_nodes/web/legacy_migration_v1.js";
import { isLegacyUndoCacheEntryV1, isNonAuthoritativeUndoCacheV1, validateJournalDurableV1 } from "../../vibecomfy/comfy_nodes/web/journal_durable_v1.js";
import { classifyCandidateTransactionBoundary } from "../../vibecomfy/comfy_nodes/web/agent_edit_transaction.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const corpus = JSON.parse(await readFile(path.join(root, "tests/fixtures/agent_edit/m1_projection_golden_v1.json"), "utf8"));
const UUID = "123e4567-e89b-12d3-a456-426614174000";
const ref = (projection) => ({ kind: "projection_ref_v1", projection, digest: "a".repeat(64) });

function _baselineRefRestoration() {
  const refTag = "original.ui.json";
  return {
    contract_version: "baseline_snapshot_v1",
    digest: sha256Hex({ contract_version: "baseline_snapshot_v1", ref: refTag }),
    ref: refTag,
  };
}

function _addNodeIndices(ops) {
  const indices = [];
  for (let i = 0; i < ops.length; i++) {
    if (ops[i] && ops[i].op === "add_node") indices.push(i);
  }
  return indices;
}

function _acceptedBatchFor(ops) {
  return ops.map((op) => ({ op }));
}

function authority(family = "structural") {
  const projection = family === "layout" ? "layout_v1" : "structural_v1";
  let operation;
  let ops;
  if (family === "layout") {
    ops = [];
    const layoutOps = [{ op: "set_node_geometry", uid: "node-1", pos: [10, 20] }];
    const layoutEnv = {
      contract_version: "layout_operation_v1",
      wire_version: "1.0.0",
      ops: layoutOps,
    };
    layoutEnv.digest = computeLayoutOperationDigest(layoutOps);
    operation = {
      delta_contract: "delta_v1", wire_version: "2.0.0",
      accepted_batch_digest: acceptedBatchDigest(_acceptedBatchFor(ops)),
      layout_operation: layoutEnv,
      layout_operation_digest: layoutEnv.digest,
    };
  } else {
    ops = corpus.delta_ops;
    operation = {
      delta_contract: "delta_v1", wire_version: "2.0.0",
      accepted_batch_digest: acceptedBatchDigest(_acceptedBatchFor(ops)),
    };
    const addIndices = _addNodeIndices(ops);
    if (addIndices.length > 0) {
      const entries = addIndices.map((i) => ({ source_op_index: i, kind: "add_node" }));
      const mat = {
        contract_version: "mutation_materialization_v1",
        wire_version: "1.0.0",
        entries,
      };
      mat.digest = computeMutationMaterializationDigest(entries, ops);
      operation.mutation_materialization = mat;
      operation.mutation_materialization_digest = mat.digest;
    }
  }
  authority.lastBatch = _acceptedBatchFor(ops);
  const value = {
    contract_version: "prepared_authority_v1",
    transaction_id: "tx-1", candidate_id: "candidate-1", workflow_id: UUID,
    scope: { kind: "root", path: "" }, session_id: "session-1", turn_id: "turn-1",
    operation,
    operation_family: family, precondition: ref(projection), postcondition: ref(projection),
    rollback_projection: projection, restoration_strategy: _baselineRefRestoration(),
    plan_hash: "plan-1", generation: 1, lease_nonce: "nonce-1",
    authority_receipt_contract_version: "authority_receipt_v2",
    authority_receipt_delta_schema: "2.0.0",
    authority_receipt_digest: "d".repeat(64),
  };
  if (family === "layout") value.structural_witness = { ...ref("structural_v1"), precondition_digest: "c".repeat(64), postcondition_digest: "c".repeat(64) };
  return value;
}

test("M1 browser and Python consume one golden projection corpus", () => {
  for (const item of corpus.projection_cases) {
    if (item.error) { assert.throws(() => projectGraphV1(item.graph, item.projection), (error) => error.code === item.error); continue; }
    const projected = projectGraphV1(item.graph, item.projection);
    assert.deepEqual(projected, item.expected);
    if (item.canonical) assert.equal(canonicalJsonString(projected), item.canonical);
    assert.equal(projectionReferenceV1(item.graph, item.projection).digest, item.digest);
  }
});
test("native advanced-widget visibility is excluded from typed projections", () => {
  const graph = structuredClone(corpus.projection_cases[0].graph);
  graph.nodes[0].showAdvanced = true;
  assert.equal(
    classifyFieldV1({ entity: "node", path: "showAdvanced", nodeType: graph.nodes[0].type }),
    FIELD_CATEGORY.DERIVED_NATIVE,
  );
  assert.deepEqual(
    projectGraphV1(graph, "structural_v1"),
    projectGraphV1(corpus.projection_cases[0].graph, "structural_v1"),
  );
  assert.deepEqual(
    projectGraphV1(graph, "layout_v1"),
    projectGraphV1(corpus.projection_cases[0].graph, "layout_v1"),
  );
});
test("zero-widget nodes normalize omitted, null, object, and array encodings", () => {
  const baseline = structuredClone(corpus.projection_cases[0].graph);
  const digest = (widgetsValues, present = true) => {
    const graph = structuredClone(baseline);
    if (present) graph.nodes[0].widgets_values = widgetsValues;
    else delete graph.nodes[0].widgets_values;
    return projectionReferenceV1(graph, "structural_v1").digest;
  };
  assert.equal(digest([], true), digest({}, true));
  assert.equal(digest(null, true), digest({}, true));
  assert.equal(digest(undefined, false), digest({}, true));
});
test("LoadImage typed projection excludes frontend-injected upload widget carriers", () => {
  const semantic = {
    nodes: [{
      id: 8,
      type: "LoadImage",
      mode: 0,
      properties: { vibecomfy_uid: "n8" },
      widgets_values: ["example.png"],
    }],
    links: [],
  };
  const native = structuredClone(semantic);
  native.nodes[0].widgets_values = ["example.png", "image"];
  assert.equal(
    classifyFieldV1({ entity: "node", path: "widgets_values.1", nodeType: "LoadImage" }),
    FIELD_CATEGORY.DERIVED_NATIVE,
  );
  assert.deepEqual(projectGraphV1(native, "structural_v1"), projectGraphV1(semantic, "structural_v1"));
  assert.equal(
    projectionReferenceV1(native, "structural_v1").digest,
    projectionReferenceV1(semantic, "structural_v1").digest,
  );
  assert.deepEqual(
    buildStructuralGraphProjection(native),
    buildStructuralGraphProjection(semantic),
  );
});
test("strict delta, prepared authority, layout witness, legacy and undo policies", () => {
  assert.equal(normalizeDeltaV1({ delta_contract: "delta_v1", wire_version: "2.0.0", ops: corpus.delta_ops }).ops.length, 6);
  for (const malformed of corpus.malformed_delta_ops) {
    assert.throws(
      () => normalizeDeltaV1({ delta_contract: "delta_v1", wire_version: "2.0.0", ops: [malformed.op] }),
      (error) => error.code === malformed.code,
    );
  }
  const value = validatePreparedAuthorityV1(authority(), { accepted_batch: authority.lastBatch }); assert.ok(Object.isFrozen(value)); assert.throws(() => { value.generation = 2; }, TypeError);
  const prepared = authority(); const candidate = structuredClone(prepared); delete candidate.generation; delete candidate.lease_nonce; candidate.contract_version = "candidate_authority_v1";
  assert.ok(validateCandidateTransactionV2({ contract_version: "candidate_transaction_v2", state: "prepared", candidate_authority: candidate, prepared_authority: prepared, plan: { accepted_batch: authority.lastBatch } }));
  assert.throws(() => validateCandidateTransactionV2({ contract_version: "candidate_transaction_v2", prepared_authority: prepared }), (error) => error.code === "missing_candidate_authority");
  assert.throws(() => normalizeDeltaV1({ delta_contract: "delta_v1", wire_version: "9.0.0", ops: [] }));
  const wrongVersion = authority(); wrongVersion.contract_version = "prepared_authority_v9"; assert.throws(() => validatePreparedAuthorityV1(wrongVersion, { accepted_batch: authority.lastBatch }), (error) => error.code === "unknown_authority_version");
  const missingReceiptVersion = authority(); delete missingReceiptVersion.authority_receipt_contract_version; assert.throws(() => validatePreparedAuthorityV1(missingReceiptVersion, { accepted_batch: authority.lastBatch }), (error) => error.code === "unknown_authority_receipt_version");
  const badReceiptDigest = authority(); badReceiptDigest.authority_receipt_digest = "ABC"; assert.throws(() => validatePreparedAuthorityV1(badReceiptDigest, { accepted_batch: authority.lastBatch }), (error) => error.code === "invalid_authority_receipt_digest");
  assert.throws(() => projectionSpecV1(corpus.error_versions.projection)); assert.throws(() => assertForwardProjectionV1(corpus.error_versions.forbidden_projection));
  const bad = authority("layout"); bad.structural_witness.postcondition_digest = "d".repeat(64); assert.throws(() => validatePreparedAuthorityV1(bad, { accepted_batch: authority.lastBatch }), (error) => error.code === "layout_structural_witness_mismatch");
  assert.equal(classifyLegacyMigrationV1({ contract_version: "candidate_transaction_v1", state: "prepared" }).classification, "legacy_prepared_nonresumable");
  assert.equal(classifyCandidateTransactionBoundary({ candidate_transaction: { contract_version: "candidate_transaction_v2" } }).classification, "invalid_v2_authority_fail_closed");
  assert.equal(classifyCandidateTransactionBoundary({ candidate_transaction: { contract_version: "candidate_transaction_v99" } }).classification, "unsupported_authority_version_fail_closed");
  assert.ok(isNonAuthoritativeUndoCacheV1({ undoStack: [] }));
  assert.equal(isLegacyUndoCacheEntryV1({ graph: {} }), false);
  assert.ok(isLegacyUndoCacheEntryV1({ contract_version: "legacy_undo_cache_entry_v1", graph: {} }));
  assert.ok(validateJournalDurableV1({ contract_version: "journal_durable_v1", state: "finalized", workflow_id: UUID, baseline: { structural_hash_before: "a".repeat(64), structural_hash_after: "b".repeat(64) }, identity_fence: { transaction_id: "tx", candidate_id: "candidate", plan_hash: "plan", generation: 1, lease_nonce: "nonce" }, inverse_or_restore: { contract_version: "inverse_delta_v1", digest: "c".repeat(64), payload: [] } }));
});
test("M1 static authority guardrails keep identity and projection ownership explicit", async () => {
  const source = await readFile(path.join(root, "vibecomfy/comfy_nodes/web/projection_registry_v1.js"), "utf8");
  assert.ok(source.includes("forbidden_forward_agent_edit"));
  const nodeIdentityBody = source.match(/export function nodeIdentityV1\(node\)\s*\{([\s\S]*?)\n\}/)?.[1] || "";
  const groupIdentityBody = source.match(/export function groupIdentityV1\(group\)\s*\{([\s\S]*?)\n\}/)?.[1] || "";
  assert.equal(nodeIdentityBody.includes("node?.id"), false);
  assert.equal(groupIdentityBody.includes("group?.title"), false);
  const graphFacade = await readFile(path.join(root, "vibecomfy/comfy_nodes/web/graph_projection.js"), "utf8");
  assert.equal(/\bfunction\s+/.test(graphFacade), false);
  assert.equal(graphFacade.includes("node.id"), false);
  assert.equal(graphFacade.includes("group.title"), false);
  const identityFacade = await readFile(path.join(root, "vibecomfy/comfy_nodes/web/identity_contract_v1.js"), "utf8");
  assert.equal(/\bfunction\s+/.test(identityFacade), false);
  const prepared = await readFile(path.join(root, "vibecomfy/comfy_nodes/web/prepared_authority_v1.js"), "utf8");
  assert.equal(prepared.includes('|| "delta_replay"'), false);
  const roundtrip = await readFile(path.join(root, "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js"), "utf8");
  assert.equal(roundtrip.includes("undoStack.push"), false, "v2/production code must not publish browser Undo authority");

  const webRoot = path.join(root, "vibecomfy/comfy_nodes/web");
  const { readdir } = await import("node:fs/promises");
  const allowedProjectionLiteralOwners = new Set([
    "projection_registry_v1.js",
    "prepared_authority_v1.js",
    "vibecomfy_roundtrip.js",
  ]);
  const duplicateOwnerPatterns = [
    /function\s+naturalNodeIdKey\s*\(/,
    /function\s+normalizeStructuralWidgetValue\s*\(/,
    /function\s+normalizeNodeStructuralWidgetValues\s*\(/,
    /function\s+layoutVector\s*\(/,
    /function\s+buildStructuralGraphProjection\s*\(/,
    /function\s+buildLayoutGraphProjection\s*\(/,
    /function\s+computeMutationPlanHash\s*\(/,
    /function\s+computeCanvasProjectionHash\s*\(/,
    /function\s+extractCanvasProjection\s*\(/,
    /function\s+nodesByIdentity\s*\(/,
    /function\s+linkMaps\s*\(/,
    /function\s+nodeLayoutKey\s*\(/,
    /function\s+groupLayoutKey\s*\(/,
    /function\s+collectLayoutMovesFromBaseline\s*\(/,
    /function\s+collectLayoutGroupsFromCandidate\s*\(/,
  ];
  for (const name of await readdir(webRoot)) {
    if (!name.endsWith(".js")) continue;
    const text = await readFile(path.join(webRoot, name), "utf8");
    if (["structural_v1", "layout_v1", "workflow_v1"].some((projection) => text.includes(`"${projection}"`))) {
      assert.ok(allowedProjectionLiteralOwners.has(name), `projection literal escaped its owner/adapter: ${name}`);
    }
    if (name !== "projection_registry_v1.js") {
      for (const pattern of duplicateOwnerPatterns) {
        assert.doesNotMatch(text, pattern, `duplicate projection semantics outside registry: ${name}`);
      }
    }
  }
  for (const name of ["preview_diff_core.js", "vibecomfy_roundtrip.js", "panel_overlay.js"]) {
    const text = await readFile(path.join(webRoot, name), "utf8");
    assert.equal(text.includes("`title:${"), false, `title identity fallback escaped registry: ${name}`);
    assert.equal(text.includes("`index:${"), false, `index identity fallback escaped registry: ${name}`);
    assert.doesNotMatch(
      text,
      /(?:uid|key)\s*=\s*[^;\n]*\?\.id\s*!=\s*null\s*\?\s*String\(/,
      `native id identity fallback escaped registry: ${name}`,
    );
    assert.doesNotMatch(
      text,
      /(?:candidateUidById|candidateUidByNativeId)\s*=\s*new\s+Map\s*\(/,
      `native-id cross-graph identity map escaped registry: ${name}`,
    );
    assert.doesNotMatch(
      text,
      /\?\.name\s*\|\|\s*String\([^)]*(?:slot|Slot)/,
      `numeric port identity fallback escaped registry: ${name}`,
    );
  }
});

test("typed projection references bind embedded canonical evidence", () => {
  const reference = projectionReferenceV1(corpus.projection_cases[0].graph, "structural_v1");
  assert.ok(assertProjectionReferenceV1(reference, { expected: "structural_v1" }));
  reference.canonical.projection = "layout_v1";
  assert.throws(
    () => assertProjectionReferenceV1(reference, { expected: "structural_v1" }),
    (error) => error.code === "projection_canonical_mismatch",
  );
  const tampered = projectionReferenceV1(corpus.projection_cases[0].graph, "structural_v1");
  tampered.canonical.nodes[0].mode = 999;
  assert.throws(
    () => assertProjectionReferenceV1(tampered, { expected: "structural_v1" }),
    (error) => error.code === "projection_digest_mismatch",
  );
});

// ── C0 authority binding: compensation + fail-closed (§3.4 / §5.3) ──────────

function _compensationEnvelope(auth, { ref = "compensation.json", digestOverride = null } = {}) {
  const fence = {
    transaction_id: auth.transaction_id,
    candidate_id: auth.candidate_id,
    plan_hash: auth.plan_hash,
    lease_nonce: auth.lease_nonce,
    generation: auth.generation,
    pre_projection_digest: auth.precondition.digest,
    post_projection_digest: auth.postcondition.digest,
  };
  const normalizedFence = canonicalizeContractNumeric(fence, { finiteErrorCode: "non_finite_materialization" });
  let digestVal = sha256Hex({
    contract_version: "baseline_snapshot_v1",
    wire_version: "1.0.0",
    ref,
    fence: normalizedFence,
  });
  if (digestOverride !== null) digestVal = digestOverride;
  return { contract_version: "baseline_snapshot_v1", wire_version: "1.0.0", ref, fence, digest: digestVal };
}

test("candidate authority rejects restoration_strategy_compensation", () => {
  const prepared = authority();
  const candidate = structuredClone(prepared);
  delete candidate.generation; delete candidate.lease_nonce;
  candidate.contract_version = "candidate_authority_v1";
  candidate.restoration_strategy_compensation = _compensationEnvelope(prepared);
  assert.throws(
    () => validateCandidateTransactionV2({ contract_version: "candidate_transaction_v2", state: "candidate_ready", candidate_authority: candidate, plan: { accepted_batch: authority.lastBatch } }),
    (error) => error.code === "candidate_compensation_forbidden",
  );
});

test("prepared authority without compensation is valid", () => {
  const prepared = authority();
  const candidate = structuredClone(prepared);
  delete candidate.generation; delete candidate.lease_nonce;
  candidate.contract_version = "candidate_authority_v1";
  assert.ok(validateCandidateTransactionV2({ contract_version: "candidate_transaction_v2", state: "prepared", candidate_authority: candidate, prepared_authority: prepared, plan: { accepted_batch: authority.lastBatch } }));
});

test("prepared authority with valid compensation is valid", () => {
  const prepared = authority();
  prepared.restoration_strategy_compensation = _compensationEnvelope(prepared);
  const candidate = structuredClone(prepared);
  delete candidate.generation; delete candidate.lease_nonce;
  delete candidate.restoration_strategy_compensation;
  candidate.contract_version = "candidate_authority_v1";
  assert.ok(validateCandidateTransactionV2({ contract_version: "candidate_transaction_v2", state: "prepared", candidate_authority: candidate, prepared_authority: prepared, plan: { accepted_batch: authority.lastBatch } }));
});

test("compensation fence unbound fails closed", () => {
  const prepared = authority();
  const other = authority(); other.transaction_id = "different";
  prepared.restoration_strategy_compensation = _compensationEnvelope(other);
  const candidate = structuredClone(prepared);
  delete candidate.generation; delete candidate.lease_nonce;
  delete candidate.restoration_strategy_compensation;
  candidate.contract_version = "candidate_authority_v1";
  assert.throws(
    () => validateCandidateTransactionV2({ contract_version: "candidate_transaction_v2", state: "prepared", candidate_authority: candidate, prepared_authority: prepared, plan: { accepted_batch: authority.lastBatch } }),
    (error) => error.code === "compensation_fence_unbound",
  );
});

test("compensation digest mismatch fails closed", () => {
  const prepared = authority();
  prepared.restoration_strategy_compensation = _compensationEnvelope(prepared, { digestOverride: "0".repeat(64) });
  const candidate = structuredClone(prepared);
  delete candidate.generation; delete candidate.lease_nonce;
  delete candidate.restoration_strategy_compensation;
  candidate.contract_version = "candidate_authority_v1";
  assert.throws(
    () => validateCandidateTransactionV2({ contract_version: "candidate_transaction_v2", state: "prepared", candidate_authority: candidate, prepared_authority: prepared, plan: { accepted_batch: authority.lastBatch } }),
    (error) => error.code === "compensation_digest_mismatch",
  );
});

test("structural family with add_node missing materialization fails closed", () => {
  const value = authority();
  delete value.operation.mutation_materialization;
  delete value.operation.mutation_materialization_digest;
  assert.throws(() => validatePreparedAuthorityV1(value, { accepted_batch: authority.lastBatch }), (error) => error.code === "missing_materialization");
});

test("layout family missing layout_operation fails closed", () => {
  const value = authority("layout");
  delete value.operation.layout_operation;
  delete value.operation.layout_operation_digest;
  assert.throws(() => validatePreparedAuthorityV1(value, { accepted_batch: authority.lastBatch }), (error) => error.code === "missing_layout_operation");
});

test("persisted operation.ops is rejected; accepted_batch is the durable Δ", () => {
  const value = authority();
  value.operation.ops = corpus.delta_ops;
  assert.throws(
    () => validatePreparedAuthorityV1(value, { accepted_batch: authority.lastBatch }),
    (error) => error.code === "durable_delta_ops_copy",
  );
});

test("C0 ownership: new contract modules have no candidateGraph and no second hash owner", async () => {
  const webRoot = path.join(root, "vibecomfy", "comfy_nodes", "web");
  for (const name of ["layout_operation_v1.js", "mutation_materialization_v1.js"]) {
    const text = await readFile(path.join(webRoot, name), "utf8");
    assert.equal(text.includes("candidateGraph"), false, `${name} must not reference candidateGraph`);
    assert.equal(text.includes("candidate_graph"), false, `${name} must not reference candidate_graph`);
    assert.doesNotMatch(text, /function\s+canonicalizeContractNumeric\s*\(/, `${name} must not define its own normalizer`);
  }
});

test("Sol B2-R4 repro: Python _transaction() fixture validates in the browser", () => {
  const python = process.env.VIBECOMFY_PYTHON
    || "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/bin/python";
  const script = [
    "import json",
    "from vibecomfy.comfy_nodes.agent.candidate_transaction import build_candidate_transaction, content_hash",
    "from vibecomfy.comfy_nodes.agent.layout_operation_v1 import compute_layout_operation_digest",
    "ops = [{\"op\": \"set_node_geometry\", \"uid\": \"node-1\", \"pos\": [300, 100]}]",
    "digest = compute_layout_operation_digest(ops)",
    "layout = {\"contract_version\": \"layout_operation_v1\", \"wire_version\": \"1.0.0\", \"ops\": ops, \"digest\": digest}",
    "submit = {\"nodes\": [{\"vibecomfy_uid\": \"node-1\", \"type\": \"PreviewImage\", \"pos\": [0, 0], \"size\": [200, 100]}], \"links\": [], \"groups\": []}",
    "candidate = {**submit, \"nodes\": [{**submit[\"nodes\"][0], \"pos\": [300, 100]}]}",
    "tx = build_candidate_transaction(",
    "    workflow_id=\"123e4567-e89b-12d3-a456-426614174000\", session_id=\"session\", turn_id=\"0001\", plan_hash=\"plan\",",
    "    submit_graph=submit, candidate_graph=candidate, accepted_batch=[],",
    "    delta_hash=content_hash({\"schema_version\": \"2.0.0\", \"ops\": []}),",
    "    submit_graph_hash=\"submit\", submit_structural_graph_hash=\"submit-structural\",",
    "    candidate_graph_hash=\"candidate\", candidate_structural_graph_hash=\"candidate-structural\",",
    "    candidate_layout_graph_hash=None, authority_receipt_hash=\"a\" * 64, schema_witness={},",
    "    replay_ok=True, candidate_matches=True, applyable=True, verification_kind=\"layout_structural_noop\",",
    "    layout_operation_envelope=layout, state=\"candidate_ready\",",
    ")",
    "print(json.dumps(tx))",
  ].join("\n");
  const result = spawnSync(python, ["-c", script], {
    encoding: "utf8",
    cwd: root,
    env: { ...process.env, PYTHONPATH: root },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const tx = JSON.parse(result.stdout);
  assert.equal(Object.hasOwn(tx.candidate_authority.operation, "ops"), false);
  assert.match(tx.candidate_authority.operation.accepted_batch_digest, /^[0-9a-f]{64}$/);
  assert.ok(Array.isArray(tx.plan.accepted_batch));
  assert.deepEqual(
    Object.keys(tx.candidate_authority.operation).sort(),
    ["accepted_batch_digest", "delta_contract", "layout_operation", "layout_operation_digest", "wire_version"],
  );
  assert.ok(Object.hasOwn(tx.plan, "accepted_batch"));
  assert.doesNotThrow(() => validateCandidateTransactionV2(tx));
});
