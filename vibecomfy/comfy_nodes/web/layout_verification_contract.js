// Versioned authority contract for browser-realizable layout verification.

export const LAYOUT_VERIFICATION_CONTRACT_VERSION = "layout_verification_v1";
export const LAYOUT_VERIFICATION_PROJECTION = "browser_layout_v1";

export function normalizeLayoutVerification(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  if (value.contract_version !== LAYOUT_VERIFICATION_CONTRACT_VERSION) return null;
  if (value.projection !== LAYOUT_VERIFICATION_PROJECTION) return null;
  if (
    typeof value.candidate_layout_graph_hash !== "string"
    || !/^[0-9a-f]{64}$/.test(value.candidate_layout_graph_hash)
  ) {
    return null;
  }
  return Object.freeze({
    contract_version: LAYOUT_VERIFICATION_CONTRACT_VERSION,
    projection: LAYOUT_VERIFICATION_PROJECTION,
    candidate_layout_graph_hash: value.candidate_layout_graph_hash,
  });
}
