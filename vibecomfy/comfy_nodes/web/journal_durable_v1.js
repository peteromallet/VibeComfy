import { workflowIdentityV1 } from "./projection_registry_v1.js";

export const JOURNAL_DURABLE_V1 = "journal_durable_v1";
export const LEGACY_UNDO_CACHE_ENTRY_V1 = "legacy_undo_cache_entry_v1";
const HEX64 = /^[0-9a-f]{64}$/;

export function validateJournalDurableV1(record) {
  const baseline = record?.baseline;
  const fence = record?.identity_fence;
  const restoration = record?.inverse_or_restore;
  const valid = record?.contract_version === JOURNAL_DURABLE_V1
    && record?.state === "finalized"
    && baseline && typeof baseline === "object"
    && HEX64.test(baseline.structural_hash_before || "")
    && HEX64.test(baseline.structural_hash_after || "")
    && fence && typeof fence === "object"
    && ["transaction_id", "candidate_id", "plan_hash", "lease_nonce"]
      .every((key) => typeof fence[key] === "string" && fence[key])
    && Number.isInteger(fence.generation) && fence.generation > 0
    && restoration && typeof restoration === "object"
    && typeof restoration.contract_version === "string"
    && HEX64.test(restoration.digest || "")
    && (Object.hasOwn(restoration, "ref") || Object.hasOwn(restoration, "payload"));
  try {
    workflowIdentityV1(record?.workflow_id);
  } catch (_error) {
    throw invalidJournal();
  }
  if (!valid) throw invalidJournal();
  return Object.freeze(JSON.parse(JSON.stringify(record)));
}

function invalidJournal() {
  const error = new Error("Finalized journal must own durable inverse/restore authority and baseline identity fence.");
  error.code = "invalid_journal_durable";
  return error;
}
export function isAuthoritativeUndoV1(value) { return Boolean(value?.contract_version === JOURNAL_DURABLE_V1); }
export function isLegacyUndoCacheEntryV1(value) {
  return Boolean(
    value?.contract_version === LEGACY_UNDO_CACHE_ENTRY_V1
    && value?.graph
    && typeof value.graph === "object"
    && !isAuthoritativeUndoV1(value),
  );
}
export function isNonAuthoritativeUndoCacheV1(value) {
  return Boolean(
    value
    && Array.isArray(value.undoStack)
    && value.undoStack.every(isLegacyUndoCacheEntryV1)
    && !isAuthoritativeUndoV1(value),
  );
}
