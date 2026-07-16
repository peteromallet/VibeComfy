import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { assertForwardProjectionV1, assertProjectionReferenceV1, projectGraphV1, projectionReferenceV1, projectionSpecV1 } from "../../vibecomfy/comfy_nodes/web/projection_registry_v1.js";
import { canonicalJsonString } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";
import { validateCandidateTransactionV2, validatePreparedAuthorityV1 } from "../../vibecomfy/comfy_nodes/web/prepared_authority_v1.js";
import { normalizeDeltaV1 } from "../../vibecomfy/comfy_nodes/web/canonical_delta.js";
import { classifyLegacyMigrationV1 } from "../../vibecomfy/comfy_nodes/web/legacy_migration_v1.js";
import { isLegacyUndoCacheEntryV1, isNonAuthoritativeUndoCacheV1, validateJournalDurableV1 } from "../../vibecomfy/comfy_nodes/web/journal_durable_v1.js";
import { classifyCandidateTransactionBoundary } from "../../vibecomfy/comfy_nodes/web/agent_edit_transaction.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const corpus = JSON.parse(await readFile(path.join(root, "tests/fixtures/agent_edit/m1_projection_golden_v1.json"), "utf8"));
const UUID = "123e4567-e89b-12d3-a456-426614174000";
const ref = (projection) => ({ kind: "projection_ref_v1", projection, digest: "a".repeat(64) });
function authority(family = "structural") { const projection = family === "layout" ? "layout_v1" : "structural_v1"; const value = { contract_version: "prepared_authority_v1", transaction_id: "tx-1", candidate_id: "candidate-1", workflow_id: UUID, scope: { kind: "root", path: "" }, session_id: "session-1", turn_id: "turn-1", operation: { delta_contract: "delta_v1", wire_version: "2.0.0", ops: corpus.delta_ops }, operation_family: family, precondition: ref(projection), postcondition: ref(projection), rollback_projection: projection, restoration_strategy: { contract_version: "inverse_delta_v1", digest: "b".repeat(64), payload: [] }, plan_hash: "plan-1", generation: 1, lease_nonce: "nonce-1", authority_receipt_contract_version: "authority_receipt_v2", authority_receipt_delta_schema: "2.0.0", authority_receipt_digest: "d".repeat(64) }; if (family === "layout") value.structural_witness = { ...ref("structural_v1"), precondition_digest: "c".repeat(64), postcondition_digest: "c".repeat(64) }; return value; }

test("M1 browser and Python consume one golden projection corpus", () => {
  for (const item of corpus.projection_cases) {
    if (item.error) { assert.throws(() => projectGraphV1(item.graph, item.projection), (error) => error.code === item.error); continue; }
    const projected = projectGraphV1(item.graph, item.projection);
    assert.deepEqual(projected, item.expected);
    if (item.canonical) assert.equal(canonicalJsonString(projected), item.canonical);
    assert.equal(projectionReferenceV1(item.graph, item.projection).digest, item.digest);
  }
});
test("strict delta, prepared authority, layout witness, legacy and undo policies", () => {
  assert.equal(normalizeDeltaV1({ delta_contract: "delta_v1", wire_version: "2.0.0", ops: corpus.delta_ops }).ops.length, 6);
  for (const malformed of corpus.malformed_delta_ops) {
    assert.throws(
      () => normalizeDeltaV1({ delta_contract: "delta_v1", wire_version: "2.0.0", ops: [malformed.op] }),
      (error) => error.code === malformed.code,
    );
  }
  const value = validatePreparedAuthorityV1(authority()); assert.ok(Object.isFrozen(value)); assert.throws(() => { value.generation = 2; }, TypeError);
  const prepared = authority(); const candidate = structuredClone(prepared); delete candidate.generation; delete candidate.lease_nonce; candidate.contract_version = "candidate_authority_v1";
  assert.ok(validateCandidateTransactionV2({ contract_version: "candidate_transaction_v2", state: "prepared", candidate_authority: candidate, prepared_authority: prepared }));
  assert.throws(() => validateCandidateTransactionV2({ contract_version: "candidate_transaction_v2", prepared_authority: prepared }), (error) => error.code === "missing_candidate_authority");
  assert.throws(() => normalizeDeltaV1({ delta_contract: "delta_v1", wire_version: "9.0.0", ops: [] }));
  const wrongVersion = authority(); wrongVersion.contract_version = "prepared_authority_v9"; assert.throws(() => validatePreparedAuthorityV1(wrongVersion), (error) => error.code === "unknown_authority_version");
  const missingReceiptVersion = authority(); delete missingReceiptVersion.authority_receipt_contract_version; assert.throws(() => validatePreparedAuthorityV1(missingReceiptVersion), (error) => error.code === "unknown_authority_receipt_version");
  const badReceiptDigest = authority(); badReceiptDigest.authority_receipt_digest = "ABC"; assert.throws(() => validatePreparedAuthorityV1(badReceiptDigest), (error) => error.code === "invalid_authority_receipt_digest");
  assert.throws(() => projectionSpecV1(corpus.error_versions.projection)); assert.throws(() => assertForwardProjectionV1(corpus.error_versions.forbidden_projection));
  const bad = authority("layout"); bad.structural_witness.postcondition_digest = "d".repeat(64); assert.throws(() => validatePreparedAuthorityV1(bad), (error) => error.code === "layout_structural_witness_mismatch");
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
  const fieldFacade = await readFile(path.join(root, "vibecomfy/comfy_nodes/web/field_registry_v1.js"), "utf8");
  const identityFacade = await readFile(path.join(root, "vibecomfy/comfy_nodes/web/identity_contract_v1.js"), "utf8");
  assert.equal(/\bfunction\s+/.test(fieldFacade), false);
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
