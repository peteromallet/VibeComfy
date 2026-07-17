// legacy_authority_migration.test.mjs — §M1.6 regression coverage.
//
// Proves the versioned legacy-persisted-authority migration at the load
// boundary without weakening v2 fail-closed validation. The four hard rules
// under test:
//
//   1. A VALID persisted legacy fixture (candidate_authority_v0_legacy) migrates
//      deterministically and Apply remains true for the resulting transaction.
//   2. The migrated output is an EXPLICIT candidate_authority_v1 that passes
//      strict validateCandidateAuthorityV1 byte-for-byte (digest bound).
//   3. A malformed CURRENT v2 authority (correct contract_version, wrong
//      restoration digest) stays fail-closed and CANNOT enter the legacy
//      migration path accidentally — it has no v0_legacy marker.
//   4. Unknown authority versions remain rejected by both the migrator and the
//      load boundary.

import test from "node:test";
import assert from "node:assert/strict";

import {
  CANDIDATE_AUTHORITY_V1,
  PREPARED_AUTHORITY_V1,
  CANDIDATE_AUTHORITY_V0_LEGACY,
  validateCandidateAuthorityV1,
  validatePreparedAuthorityV1,
  validateCandidateTransactionV2,
  migrateLegacyCandidateAuthorityV0Legacy,
} from "../../vibecomfy/comfy_nodes/web/prepared_authority_v1.js";
import {
  normalizeCandidateTransaction,
  transactionAllows,
  classifyCandidateTransactionBoundary,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_transaction.js";
import { sha256Hex } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";

const UUID = "123e4567-e89b-12d3-a456-426614174000";

// ── Legacy authority shape (models a persisted pre-strict-digest fixture) ────
//
// restoration_strategy.digest is intentionally a placeholder; the migrator
// recomputes it from {contract_version, payload}. Every other field already
// conforms to the v1 structural shape so strict validation binds after upgrade.

function legacyRestorationPayload() {
  return { ops: [] };
}

function legacyCandidateAuthority({
  restorationStrategyTag = "inverse_delta_v1",
  restorationPayload = legacyRestorationPayload(),
  restorationDigest = "b".repeat(64), // placeholder — migrator overwrites this
  ...overrides
} = {}) {
  return Object.freeze({
    contract_version: CANDIDATE_AUTHORITY_V0_LEGACY,
    transaction_id: "tx-legacy-001",
    candidate_id: "candidate-legacy-001",
    workflow_id: UUID,
    scope: Object.freeze({ kind: "root", path: "" }),
    session_id: "sess-legacy-001",
    turn_id: "turn-legacy-001",
    operation: Object.freeze({
      delta_contract: "delta_v1",
      wire_version: "2.0.0",
      ops: Object.freeze([]),
    }),
    operation_family: "structural",
    precondition: Object.freeze({
      kind: "projection_ref_v1",
      projection: "structural_v1",
      digest: "a".repeat(64),
    }),
    postcondition: Object.freeze({
      kind: "projection_ref_v1",
      projection: "structural_v1",
      digest: "a".repeat(64),
    }),
    rollback_projection: "structural_v1",
    restoration_strategy: Object.freeze({
      contract_version: restorationStrategyTag,
      digest: restorationDigest,
      payload: Object.freeze(restorationPayload),
    }),
    plan_hash: "plan-legacy-001",
    authority_receipt_contract_version: "authority_receipt_v2",
    authority_receipt_delta_schema: "2.0.0",
    authority_receipt_digest: "c".repeat(64),
    ...overrides,
  });
}

function legacyCandidateTransaction({ candidateAuthority = legacyCandidateAuthority() } = {}) {
  return Object.freeze({
    contract_version: "candidate_transaction_v2",
    state: "candidate_ready",
    candidate_authority: candidateAuthority,
    prepared_authority: null,
    session_id: "sess-legacy-001",
    turn_id: "turn-legacy-001",
    plan_hash: "plan-legacy-001",
    generation: 1,
    lease_nonce: "lease-legacy-001",
    plan: Object.freeze({
      schema_version: "2.0.0",
      delta_ops_envelope: Object.freeze({ schema_version: "2.0.0", ops: Object.freeze([]) }),
      delta_hash: "delta-legacy-001",
      op_count: 0,
      schema_provenance: Object.freeze({}),
    }),
    hashes: Object.freeze({
      submit_graph_hash: "sha256:submit-legacy-graph-hash",
      submit_structural_graph_hash: "sha256:submit-legacy-structural-hash",
      candidate_graph_hash: "sha256:candidate-legacy-graph-hash",
      candidate_structural_graph_hash: "sha256:candidate-legacy-structural-hash",
      authority_receipt_hash: "c".repeat(64),
    }),
    authority: Object.freeze({
      replay_ok: true,
      candidate_matches: true,
      verification_kind: "delta_replay",
    }),
    available_actions: Object.freeze(["apply", "reject"]),
    terminal: false,
    last_error: null,
  });
}

function expectedRestorationDigest(tag, payload) {
  return sha256Hex({ contract_version: tag, payload });
}

// ─────────────────────────────────────────────────────────────────────────────
// Rule 1 — valid legacy persisted fixture migrates deterministically; Apply true
// ─────────────────────────────────────────────────────────────────────────────

test("valid legacy v0_legacy authority migrates to candidate_authority_v1", () => {
  const legacy = legacyCandidateAuthority();
  const migrated = migrateLegacyCandidateAuthorityV0Legacy(legacy);

  assert.equal(migrated.contract_version, CANDIDATE_AUTHORITY_V1);
  // Deterministic: every non-migrated field passes through untouched.
  assert.equal(migrated.transaction_id, legacy.transaction_id);
  assert.equal(migrated.candidate_id, legacy.candidate_id);
  assert.equal(migrated.workflow_id, legacy.workflow_id);
  assert.equal(migrated.operation_family, legacy.operation_family);
  assert.equal(migrated.rollback_projection, legacy.rollback_projection);
  assert.equal(migrated.plan_hash, legacy.plan_hash);
  assert.deepEqual(migrated.operation, legacy.operation);
  assert.deepEqual(migrated.precondition, legacy.precondition);
  assert.deepEqual(migrated.postcondition, legacy.postcondition);
  // Restoration digest was recomputed; the placeholder is gone.
  const expected = expectedRestorationDigest(
    legacy.restoration_strategy.contract_version,
    legacy.restoration_strategy.payload,
  );
  assert.equal(migrated.restoration_strategy.digest, expected);
  assert.notEqual(migrated.restoration_strategy.digest, legacy.restoration_strategy.digest);
});

test("migration is deterministic: same input always yields same output", () => {
  const legacy = legacyCandidateAuthority();
  const first = migrateLegacyCandidateAuthorityV0Legacy(legacy);
  const second = migrateLegacyCandidateAuthorityV0Legacy(legacy);
  assert.deepEqual(first, second);
});

test("migration does not mutate the frozen persisted fixture", () => {
  const legacy = legacyCandidateAuthority();
  const originalDigest = legacy.restoration_strategy.digest;
  const originalVersion = legacy.contract_version;
  migrateLegacyCandidateAuthorityV0Legacy(legacy);
  assert.equal(legacy.contract_version, originalVersion);
  assert.equal(legacy.restoration_strategy.digest, originalDigest);
});

test("valid legacy fixture normalizes through the load boundary and Apply remains true", () => {
  const transaction = legacyCandidateTransaction();
  const normalized = normalizeCandidateTransaction(transaction);

  assert.ok(normalized, "valid legacy fixture must normalize (not fail-closed)");
  assert.equal(normalized.contract_version, "candidate_transaction_v2");
  // The inner authority is migrated to explicit candidate_authority_v1.
  assert.equal(
    normalized.candidate_authority.contract_version,
    CANDIDATE_AUTHORITY_V1,
  );
  assert.equal(normalized.state, "candidate_ready");
  // Apply remains true: the migrated v2 advertises apply/reject.
  assert.equal(transactionAllows(normalized, "apply"), true);
  assert.equal(transactionAllows(normalized, "reject"), true);
  assert.deepEqual([...normalized.available_actions], ["apply", "reject"]);
});

test("baseline_snapshot_v1 legacy restoration migrates via ref digest", () => {
  const ref = "original.ui.json";
  // baseline_snapshot_v1 uses ref, not payload — build it directly (the
  // legacyCandidateAuthority helper defaults to a payload-based strategy).
  const base = legacyCandidateAuthority();
  const legacy = {
    ...base,
    restoration_strategy: {
      contract_version: "baseline_snapshot_v1",
      digest: "b".repeat(64), // placeholder
      ref,
    },
  };
  const migrated = migrateLegacyCandidateAuthorityV0Legacy(legacy);
  assert.equal(
    migrated.restoration_strategy.digest,
    sha256Hex({ contract_version: "baseline_snapshot_v1", ref }),
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Rule 2 — migrated output is explicit current-version authority and passes
// strict validation
// ─────────────────────────────────────────────────────────────────────────────

test("migrated legacy authority passes strict validateCandidateAuthorityV1", () => {
  const legacy = legacyCandidateAuthority();
  const migrated = migrateLegacyCandidateAuthorityV0Legacy(legacy);
  // Strict validation recomputes restoration_strategy.digest and must match.
  const validated = validateCandidateAuthorityV1(migrated);
  assert.ok(validated);
  assert.equal(validated.contract_version, CANDIDATE_AUTHORITY_V1);
});

test("migrated legacy transaction passes strict validateCandidateTransactionV2", () => {
  const transaction = legacyCandidateTransaction();
  const normalized = normalizeCandidateTransaction(transaction);
  assert.ok(normalized);
  // The normalized envelope (post-migration) must pass strict v2 validation.
  assert.doesNotThrow(() => validateCandidateTransactionV2(normalized));
});

test("normalized legacy transaction's restoration digest matches strict recomputation", () => {
  const transaction = legacyCandidateTransaction();
  const normalized = normalizeCandidateTransaction(transaction);
  const restoration = normalized.candidate_authority.restoration_strategy;
  const expected = expectedRestorationDigest(
    restoration.contract_version,
    restoration.payload,
  );
  assert.equal(restoration.digest, expected);
});

// ─────────────────────────────────────────────────────────────────────────────
// Rule 3 — malformed CURRENT v2 stays fail-closed and cannot enter migration
// ─────────────────────────────────────────────────────────────────────────────

test("malformed current v1 authority (wrong digest) fails closed WITHOUT entering migration", () => {
  // Same structural shape as the legacy fixture, but contract_version is the
  // CURRENT candidate_authority_v1 (no v0_legacy marker). The wrong digest must
  // be caught by strict validation, not silently migrated.
  const currentMalformed = legacyCandidateAuthority();
  const asCurrentV1 = {
    ...currentMalformed,
    contract_version: CANDIDATE_AUTHORITY_V1,
    // restoration_strategy.digest is still the placeholder — wrong for v1.
  };

  // The migrator refuses it (wrong marker).
  assert.throws(
    () => migrateLegacyCandidateAuthorityV0Legacy(asCurrentV1),
    (error) => error.code === "unknown_authority_version",
  );

  // Strict validation rejects it.
  assert.throws(
    () => validateCandidateAuthorityV1(asCurrentV1),
    (error) => error.code === "restoration_digest_mismatch",
  );

  // The load boundary fail-closes.
  const transaction = legacyCandidateTransaction({
    candidateAuthority: asCurrentV1,
  });
  const normalized = normalizeCandidateTransaction(transaction);
  assert.equal(normalized, null, "malformed current v1 must normalize to null (fail-closed)");
});

test("malformed current v2 transaction with bad-digest authority is classified fail-closed", () => {
  const currentMalformed = legacyCandidateAuthority();
  const asCurrentV1 = { ...currentMalformed, contract_version: CANDIDATE_AUTHORITY_V1 };
  const transaction = legacyCandidateTransaction({ candidateAuthority: asCurrentV1 });

  const classification = classifyCandidateTransactionBoundary({
    candidate_transaction: transaction,
  });
  assert.equal(classification.classification, "invalid_v2_authority_fail_closed");
  assert.equal(classification.rollback_allowed, false);
  // No apply action escapes a malformed v2.
  assert.equal(classification.actions.includes("apply"), false);
});

test("structurally invalid v0_legacy (array restoration payload) fail-closes at the boundary", () => {
  // The legacy era must still carry a structurally valid restoration_strategy.
  // An array payload is NOT a valid legacy shape — migration throws and the
  // boundary returns null.
  const invalidLegacy = legacyCandidateAuthority({
    restorationPayload: "not-an-object",
  });
  // Force the payload to be an array (the original bug shape).
  const tampered = {
    ...invalidLegacy,
    restoration_strategy: {
      ...invalidLegacy.restoration_strategy,
      payload: [],
    },
  };
  assert.throws(
    () => migrateLegacyCandidateAuthorityV0Legacy(tampered),
    (error) => error.code === "malformed_legacy_authority",
  );
  const transaction = legacyCandidateTransaction({ candidateAuthority: tampered });
  assert.equal(normalizeCandidateTransaction(transaction), null);
});

test("v0_legacy with unknown restoration tag fail-closes", () => {
  const legacy = legacyCandidateAuthority({
    restorationStrategyTag: "inverse_delta_v99",
  });
  assert.throws(
    () => migrateLegacyCandidateAuthorityV0Legacy(legacy),
    (error) => error.code === "unknown_restoration_strategy",
  );
});

test("v0_legacy cannot claim the post-legacy inverse_delta_v2 contract", () => {
  const legacy = legacyCandidateAuthority({
    restorationStrategyTag: "inverse_delta_v2",
    restorationPayload: {
      ops: [],
      forward_operation_digest: "a".repeat(64),
      prior_link_witnesses: [],
    },
  });
  assert.throws(
    () => migrateLegacyCandidateAuthorityV0Legacy(legacy),
    (error) => error.code === "unknown_restoration_strategy",
  );
});

test("v0_legacy missing restoration_strategy fail-closes", () => {
  const legacy = legacyCandidateAuthority();
  const missing = { ...legacy };
  delete missing.restoration_strategy;
  assert.throws(
    () => migrateLegacyCandidateAuthorityV0Legacy(missing),
    (error) => error.code === "malformed_legacy_authority",
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Rule 4 — unknown versions remain rejected
// ─────────────────────────────────────────────────────────────────────────────

test("unknown authority version is rejected by the migrator", () => {
  const unknown = legacyCandidateAuthority({ ...{} });
  const asUnknown = { ...unknown, contract_version: "candidate_authority_v99" };
  assert.throws(
    () => migrateLegacyCandidateAuthorityV0Legacy(asUnknown),
    (error) => error.code === "unknown_authority_version",
  );
});

test("unknown outer transaction version is rejected at the load boundary", () => {
  const transaction = legacyCandidateTransaction();
  const unknownOuter = { ...transaction, contract_version: "candidate_transaction_v99" };
  assert.equal(normalizeCandidateTransaction(unknownOuter), null);
});

test("unknown outer transaction version is classified unsupported fail-closed", () => {
  const transaction = legacyCandidateTransaction();
  const unknownOuter = { ...transaction, contract_version: "candidate_transaction_v99" };
  const classification = classifyCandidateTransactionBoundary({
    candidate_transaction: unknownOuter,
  });
  assert.equal(classification.classification, "unsupported_authority_version_fail_closed");
  assert.equal(classification.rollback_allowed, false);
});

test("non-object legacy authority is rejected by the migrator", () => {
  assert.throws(
    () => migrateLegacyCandidateAuthorityV0Legacy(null),
    (error) => error.code === "malformed_legacy_authority",
  );
  assert.throws(
    () => migrateLegacyCandidateAuthorityV0Legacy("not-an-object"),
    (error) => error.code === "malformed_legacy_authority",
  );
  assert.throws(
    () => migrateLegacyCandidateAuthorityV0Legacy([]),
    (error) => error.code === "malformed_legacy_authority",
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Candidate + prepared transition through the load boundary
//
// A prepared-state transaction may carry a legacy candidate authority alongside
// a current v1 prepared authority. The candidate authority migrates
// deterministically; the prepared authority passes through strict v1 validation.
// ─────────────────────────────────────────────────────────────────────────────

function currentV1PreparedAuthority({
  restorationStrategyTag = "inverse_delta_v1",
  restorationPayload = legacyRestorationPayload(),
  generation = 7,
  leaseNonce = "lease-prepared-001",
  ...overrides
} = {}) {
  const validDigest = expectedRestorationDigest(restorationStrategyTag, restorationPayload);
  const base = legacyCandidateAuthority({
    restorationStrategyTag,
    restorationPayload,
    restorationDigest: validDigest,
  });
  return Object.freeze({
    ...base,
    contract_version: PREPARED_AUTHORITY_V1,
    generation,
    lease_nonce: leaseNonce,
    ...overrides,
  });
}

function preparedStateTransaction({
  candidateAuthority = legacyCandidateAuthority(),
  preparedAuthority = currentV1PreparedAuthority(),
  ...overrides
} = {}) {
  const base = legacyCandidateTransaction({ candidateAuthority });
  return Object.freeze({
    ...base,
    state: "prepared",
    prepared_authority: preparedAuthority,
    generation: preparedAuthority.generation,
    lease_nonce: preparedAuthority.lease_nonce,
    available_actions: Object.freeze(["rollback"]),
    ...overrides,
  });
}

test("prepared-state transaction with legacy candidate + current v1 prepared normalizes and rollback is available", () => {
  const transaction = preparedStateTransaction();
  const normalized = normalizeCandidateTransaction(transaction);
  assert.ok(normalized, "legacy candidate + v1 prepared must normalize (not fail-closed)");
  assert.equal(normalized.state, "prepared");
  assert.equal(normalized.candidate_authority.contract_version, CANDIDATE_AUTHORITY_V1);
  assert.equal(normalized.prepared_authority.contract_version, PREPARED_AUTHORITY_V1);
  // Rollback is the prepared-state action vocabulary.
  assert.equal(transactionAllows(normalized, "rollback"), true);
  assert.equal(transactionAllows(normalized, "apply"), false);
  assert.deepEqual([...normalized.available_actions], ["rollback"]);
});

test("prepared-state transaction with legacy candidate + v1 prepared passes strict validateCandidateTransactionV2", () => {
  const transaction = preparedStateTransaction();
  const normalized = normalizeCandidateTransaction(transaction);
  assert.ok(normalized);
  assert.doesNotThrow(() => validateCandidateTransactionV2(normalized));
});

test("prepared-state transaction with legacy candidate + v1 prepared does not mutate the frozen fixture", () => {
  const transaction = preparedStateTransaction();
  const originalCandidateVersion = transaction.candidate_authority.contract_version;
  const originalPreparedVersion = transaction.prepared_authority.contract_version;
  const originalDigest = transaction.prepared_authority.restoration_strategy.digest;
  normalizeCandidateTransaction(transaction);
  assert.equal(transaction.candidate_authority.contract_version, originalCandidateVersion);
  assert.equal(transaction.prepared_authority.contract_version, originalPreparedVersion);
  assert.equal(transaction.prepared_authority.restoration_strategy.digest, originalDigest);
});

test("prepared-state transaction with current v1 candidate + current v1 prepared passes through without migration", () => {
  // Both inners are already current v1 with valid digests. No migration needed;
  // strict v2 validation binds both directly.
  const validDigest = expectedRestorationDigest("inverse_delta_v1", legacyRestorationPayload());
  const currentCandidate = {
    ...legacyCandidateAuthority({ restorationDigest: validDigest }),
    contract_version: CANDIDATE_AUTHORITY_V1,
  };
  const currentPrepared = currentV1PreparedAuthority();
  const transaction = preparedStateTransaction({
    candidateAuthority: currentCandidate,
    preparedAuthority: currentPrepared,
  });
  const normalized = normalizeCandidateTransaction(transaction);
  assert.ok(normalized);
  assert.equal(normalized.candidate_authority.contract_version, CANDIDATE_AUTHORITY_V1);
  assert.equal(normalized.prepared_authority.contract_version, PREPARED_AUTHORITY_V1);
  assert.equal(normalized.candidate_authority.restoration_strategy.digest, validDigest);
  assert.equal(normalized.prepared_authority.restoration_strategy.digest, validDigest);
});

test("prepared-state transaction with legacy candidate + current v1 prepared migrates only the candidate inner", () => {
  const validDigest = expectedRestorationDigest("inverse_delta_v1", legacyRestorationPayload());
  const legacyCandidate = legacyCandidateAuthority();
  const currentPrepared = currentV1PreparedAuthority();
  const transaction = preparedStateTransaction({
    candidateAuthority: legacyCandidate,
    preparedAuthority: currentPrepared,
  });
  const normalized = normalizeCandidateTransaction(transaction);
  assert.ok(normalized);
  assert.equal(normalized.candidate_authority.contract_version, CANDIDATE_AUTHORITY_V1);
  assert.equal(normalized.prepared_authority.contract_version, PREPARED_AUTHORITY_V1);
  // The candidate digest was recomputed by the migrator to match the prepared.
  assert.equal(
    normalized.candidate_authority.restoration_strategy.digest,
    validDigest,
  );
  // The prepared digest was already valid and passed through.
  assert.equal(
    normalized.prepared_authority.restoration_strategy.digest,
    validDigest,
  );
});

test("malformed current v1 prepared authority (wrong digest) fail-closes the prepared-state transaction", () => {
  // Current v1 prepared authority with a deliberately wrong restoration digest.
  const malformedPrepared = {
    ...currentV1PreparedAuthority(),
    restoration_strategy: {
      ...currentV1PreparedAuthority().restoration_strategy,
      digest: "b".repeat(64), // wrong — not bound to payload
    },
  };
  const transaction = preparedStateTransaction({
    preparedAuthority: malformedPrepared,
  });
  assert.equal(normalizeCandidateTransaction(transaction), null);
  const classification = classifyCandidateTransactionBoundary({
    candidate_transaction: transaction,
  });
  assert.equal(classification.classification, "invalid_v2_authority_fail_closed");
  assert.equal(classification.rollback_allowed, false);
});

// ─────────────────────────────────────────────────────────────────────────────
// Candidate-ready transactions must not accept a prepared authority (current
// v1). The unexpected_prepared_authority guard is not bypassed.
// ─────────────────────────────────────────────────────────────────────────────

test("candidate-ready transaction carrying a malformed current v1 prepared authority fail-closes", () => {
  const transaction = legacyCandidateTransaction();
  // Force candidate_ready state but inject a prepared authority with wrong digest.
  const malformedPrepared = {
    ...currentV1PreparedAuthority(),
    restoration_strategy: {
      ...currentV1PreparedAuthority().restoration_strategy,
      digest: "b".repeat(64),
    },
  };
  const withMalformedPrepared = {
    ...transaction,
    state: "candidate_ready",
    prepared_authority: malformedPrepared,
    available_actions: Object.freeze(["apply", "reject"]),
  };
  assert.equal(normalizeCandidateTransaction(withMalformedPrepared), null);
  const classification = classifyCandidateTransactionBoundary({
    candidate_transaction: withMalformedPrepared,
  });
  assert.equal(classification.classification, "invalid_v2_authority_fail_closed");
  assert.equal(classification.actions.includes("apply"), false);
});

test("candidate-ready transaction carrying a valid current v1 prepared authority fail-closes", () => {
  const transaction = legacyCandidateTransaction();
  const currentPrepared = currentV1PreparedAuthority();
  const withCurrentPrepared = {
    ...transaction,
    state: "candidate_ready",
    prepared_authority: currentPrepared,
    available_actions: Object.freeze(["apply", "reject"]),
  };
  assert.equal(normalizeCandidateTransaction(withCurrentPrepared), null);
});
