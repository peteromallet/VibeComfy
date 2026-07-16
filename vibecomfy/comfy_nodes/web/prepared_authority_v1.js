import { assertRootScopeV1 } from "./root_scope_v1.js";
import { issuedIdentityV1, workflowIdentityV1 } from "./identity_contract_v1.js";
import { assertForwardProjectionV1, assertProjectionReferenceV1 } from "./projection_registry_v1.js";
import { normalizeDeltaEnvelope, ensureRootScopedOps, DELTA_SCHEMA_VERSION } from "./canonical_delta.js";
export const PREPARED_AUTHORITY_V1 = "prepared_authority_v1";
export const CANDIDATE_AUTHORITY_V1 = "candidate_authority_v1";
export const CANDIDATE_TRANSACTION_V2 = "candidate_transaction_v2";
export const AUTHORITY_RECEIPT_CONTRACT_VERSION = "authority_receipt_v2";
function clone(value) { return JSON.parse(JSON.stringify(value)); }
function freeze(value) { if (value && typeof value === "object") { Object.values(value).forEach(freeze); Object.freeze(value); } return value; }
function digest(value) { if (!value || typeof value !== "object" || typeof value.contract_version !== "string" || (!value.payload && !value.ref) || typeof value.digest !== "string" || !/^[0-9a-f]{64}$/.test(value.digest)) { const e = new Error("Restoration strategy requires version, digest, and payload or ref."); e.code = "invalid_restoration_strategy"; throw e; } return value; }
function validateAuthorityCommon(raw, contract) {
  if (!raw || raw.contract_version !== contract) { const e = new Error("Unsupported authority version."); e.code = "unknown_authority_version"; throw e; }
  ["transaction_id", "candidate_id", "session_id", "turn_id", "plan_hash"].forEach((key) => issuedIdentityV1(raw[key], key)); workflowIdentityV1(raw.workflow_id); assertRootScopeV1(raw.scope);
  if (raw.authority_receipt_contract_version !== AUTHORITY_RECEIPT_CONTRACT_VERSION) { const e = new Error("Authority receipt contract version must be explicit."); e.code = "unknown_authority_receipt_version"; throw e; }
  if (raw.authority_receipt_delta_schema !== DELTA_SCHEMA_VERSION) { const e = new Error("Authority receipt delta schema must match delta_v1."); e.code = "authority_receipt_delta_schema_mismatch"; throw e; }
  if (typeof raw.authority_receipt_digest !== "string" || !/^[0-9a-f]{64}$/.test(raw.authority_receipt_digest)) { const e = new Error("Authority receipt digest must be exact lowercase SHA-256."); e.code = "invalid_authority_receipt_digest"; throw e; }
  if (!raw.operation || raw.operation.delta_contract !== "delta_v1" || raw.operation.wire_version !== DELTA_SCHEMA_VERSION || !Array.isArray(raw.operation.ops)) { const e = new Error("Operation must explicitly bind delta_v1 to wire 2.0.0."); e.code = "invalid_delta_contract"; throw e; }
  const envelope = normalizeDeltaEnvelope({ schema_version: raw.operation.wire_version, ops: raw.operation.ops }, { strict: true }); ensureRootScopedOps(envelope.ops);
  if (!["structural", "layout"].includes(raw.operation_family)) { const e = new Error("Unknown operation family."); e.code = "unknown_operation_family"; throw e; }
  const expected = raw.operation_family === "layout" ? "layout_v1" : "structural_v1"; assertForwardProjectionV1(expected); assertProjectionReferenceV1(raw.precondition, { expected }); assertProjectionReferenceV1(raw.postcondition, { expected });
  if (raw.rollback_projection !== expected) { const e = new Error("Rollback projection must equal forward projection family."); e.code = "rollback_projection_mismatch"; throw e; }
  if (raw.operation_family === "layout") { const structural = raw.structural_witness; assertProjectionReferenceV1(structural, { expected: "structural_v1" }); if (structural.precondition_digest !== structural.postcondition_digest) { const e = new Error("Layout requires structural no-op witness."); e.code = "layout_structural_witness_mismatch"; throw e; } }
  digest(raw.restoration_strategy); return raw;
}
export function validateCandidateAuthorityV1(raw) { validateAuthorityCommon(raw, CANDIDATE_AUTHORITY_V1); if (Object.hasOwn(raw, "generation") || Object.hasOwn(raw, "lease_nonce")) { const e = new Error("Candidate authority cannot infer prepare identity."); e.code = "unexpected_prepare_identity"; throw e; } return freeze(clone({ ...raw, operation: { ...raw.operation } })); }
export function validatePreparedAuthorityV1(raw) { validateAuthorityCommon(raw, PREPARED_AUTHORITY_V1); issuedIdentityV1(raw.lease_nonce, "lease_nonce"); if (!Number.isInteger(raw.generation) || raw.generation <= 0) { const e = new Error("generation must be positive."); e.code = "invalid_generation"; throw e; } return freeze(clone({ ...raw, operation: { ...raw.operation } })); }
export function validateCandidateTransactionV2(value) {
  if (!value || value.contract_version !== CANDIDATE_TRANSACTION_V2) { const e = new Error("Unsupported candidate transaction version."); e.code = "unsupported_candidate_transaction"; throw e; }
  if (!value.candidate_authority) { const e = new Error("candidate_transaction_v2 requires candidate_authority_v1."); e.code = "missing_candidate_authority"; throw e; }
  const candidate = validateCandidateAuthorityV1(value.candidate_authority);
  const preparedStates = new Set(["prepared", "canvas_verified", "finalized", "rollback_complete", "superseded"]);
  if (["candidate_ready", "recoverable_error", "discarded"].includes(value.state)) { if (value.prepared_authority != null) { const e = new Error("Unprepared transaction carries prepared authority."); e.code = "unexpected_prepared_authority"; throw e; } return candidate; }
  if (!preparedStates.has(value.state)) { const e = new Error("Unknown candidate transaction state."); e.code = "invalid_candidate_transaction_state"; throw e; }
  const prepared = validatePreparedAuthorityV1(value.prepared_authority);
  ["transaction_id", "candidate_id", "session_id", "turn_id", "plan_hash", "workflow_id", "scope", "operation", "operation_family", "precondition", "postcondition", "rollback_projection", "restoration_strategy", "authority_receipt_contract_version", "authority_receipt_delta_schema", "authority_receipt_digest"].forEach((key) => { if (JSON.stringify(prepared[key]) !== JSON.stringify(candidate[key])) { const e = new Error("Prepared authority changed candidate-time authority."); e.code = "prepared_authority_transition_mismatch"; throw e; } });
  return prepared;
}
