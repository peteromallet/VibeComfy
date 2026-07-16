import test from "node:test";
import assert from "node:assert/strict";

import * as candidateActions from "../../vibecomfy/comfy_nodes/web/agent_candidate_actions.js";
import { projectionReferenceV1 } from "../../vibecomfy/comfy_nodes/web/projection_registry_v1.js";

const {
  APPLY_ELIGIBILITY_REASON,
  applyEligibility,
  disabledApplyEligibility,
  normalizeApplyEligibility,
  candidateGraphPresentForBubble,
  candidateActionState,
} = candidateActions;

function candidateTransaction(state = "candidate_ready") {
  const operations = [];
  const projection = projectionReferenceV1({ nodes: [], links: [] }, "structural_v1");
  const authorityReceiptDigest = "c".repeat(64);
  const candidateAuthority = {
    contract_version: "candidate_authority_v1",
    transaction_id: "transaction-1",
    candidate_id: "candidate-1",
    workflow_id: "123e4567-e89b-12d3-a456-426614174000",
    scope: { kind: "root", path: "" },
    session_id: "session-1",
    turn_id: "0002",
    operation: {
      delta_contract: "delta_v1",
      wire_version: "2.0.0",
      ops: operations,
    },
    operation_family: "structural",
    precondition: projection,
    postcondition: projection,
    rollback_projection: "structural_v1",
    restoration_strategy: {
      contract_version: "inverse_delta_v1",
      digest: "b".repeat(64),
      payload: [],
    },
    plan_hash: "plan-1",
    authority_receipt_contract_version: "authority_receipt_v2",
    authority_receipt_delta_schema: "2.0.0",
    authority_receipt_digest: authorityReceiptDigest,
  };
  return {
    contract_version: "candidate_transaction_v2",
    state,
    candidate_authority: candidateAuthority,
    prepared_authority: null,
    resume_state: null,
    session_id: "session-1",
    turn_id: "0002",
    plan_hash: "plan-1",
    generation: null,
    lease_nonce: null,
    plan: {
      schema_version: "2.0.0",
      delta_ops_envelope: { schema_version: "2.0.0", ops: operations },
      delta_hash: "delta-1",
      op_count: operations.length,
      schema_provenance: {},
    },
    hashes: {
      candidate_graph_hash: projection.digest,
      candidate_structural_graph_hash: projection.digest,
      authority_receipt_hash: authorityReceiptDigest,
    },
    authority: { replay_ok: true, candidate_matches: true, verification_kind: "delta_replay" },
    available_actions: ["apply", "reject"],
    terminal: false,
    last_error: null,
  };
}

test("agent_candidate_actions exposes the candidate action owner API", () => {
  assert.deepEqual(Object.keys(candidateActions).sort(), [
    "APPLY_ELIGIBILITY_REASON",
    "applyEligibility",
    "candidateActionState",
    "candidateGraphPresentForBubble",
    "disabledApplyEligibility",
    "normalizeApplyEligibility",
  ].sort());
});

test("applyEligibility preserves canonical active eligibility behavior", () => {
  const panel = {
    state: {
      candidateGraph: { nodes: [] },
      candidateTransaction: candidateTransaction(),
      applyEligibility: {
        applyable: true,
        reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
        message: "Ready.",
        warnings: ["copied"],
      },
      applyEligibilityWarning: { stale: true },
      applyEligibilityWarningKey: "stale",
    },
  };

  const eligibility = applyEligibility(panel);

  assert.deepEqual(eligibility, {
    applyable: true,
    reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
    message: "Ready.",
    warnings: ["copied"],
  });
  assert.equal(panel.state.applyEligibilityWarning, null);
  assert.equal(panel.state.applyEligibilityWarningKey, null);
  assert.notEqual(eligibility.warnings, panel.state.applyEligibility.warnings);
});

test("candidateActionState keeps active and historical candidate semantics", () => {
  const panel = {
    state: {
      phase: "AWAITING_REVIEW",
      candidateGraph: { nodes: [] },
      candidateTransaction: candidateTransaction(),
      turnId: "0002",
      applyEligibility: {
        applyable: true,
        reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
        message: "Ready.",
        warnings: [],
      },
    },
  };

  assert.deepEqual(candidateActionState(panel), {
    visible: true,
    active: true,
    turnId: "0002",
    eligibility: {
      applyable: true,
      reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
      message: "Ready.",
      warnings: [],
    },
    blockerMessage: "",
    applyDisabled: false,
    rejectDisabled: false,
  });

  assert.deepEqual(
    candidateActionState(
      panel,
      { turn_id: "0001", candidateGraph: { nodes: [] } },
      {
        applyEligibility: {
          applyable: false,
          reason: APPLY_ELIGIBILITY_REASON.SUPERSEDED,
          message: "Already replaced.",
          warnings: ["superseded"],
        },
      },
    ).eligibility,
    {
      applyable: false,
      reason: APPLY_ELIGIBILITY_REASON.MISSING_CONTRACT,
      message: "Candidate transaction authority is missing. Apply and Reject are disabled until the session is reconciled.",
      warnings: ["missing_contract"],
    },
  );

  const staleHistorical = candidateActionState(panel, { turn_id: "0001", candidateGraph: { nodes: [] } });
  assert.equal(staleHistorical.active, false);
  assert.equal(staleHistorical.eligibility.reason, APPLY_ELIGIBILITY_REASON.MISSING_CONTRACT);
  assert.equal(staleHistorical.applyDisabled, true);
  assert.equal(staleHistorical.rejectDisabled, true);
});

test("candidateActionState suspends stale candidate actions while durable authority rehydrates", () => {
  const panel = {
    state: {
      phase: "AWAITING_REVIEW",
      chatRehydratePending: true,
      candidateGraph: { nodes: [] },
      turnId: "0001",
      applyEligibility: {
        applyable: true,
        reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
        message: "Previously ready.",
        warnings: [],
      },
    },
  };

  const state = candidateActionState(panel);
  assert.equal(state.visible, true);
  assert.equal(state.active, true);
  assert.equal(state.applyDisabled, true);
  assert.equal(state.rejectDisabled, true);
  assert.equal(state.blockerMessage, "Checking whether this candidate is still available.");
});

test("candidateActionState preserves optional reorganise candidate eligibility and stale history", () => {
  const panel = {
    state: {
      phase: "AWAITING_REVIEW",
      candidateGraph: { nodes: [{ id: 3, type: "KSampler", pos: [320, 160] }], links: [] },
      candidateGraphHash: "layout-candidate-hash",
      candidateTransaction: candidateTransaction(),
      turnId: "0003",
      applyEligibility: {
        applyable: true,
        reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
        message: "Ready to apply layout candidate.",
        warnings: [],
      },
      changeDetails: {
        layout_reorganisation: {
          result: "prepare_candidate",
          candidate_prepared: true,
          functional_candidate_graph_hash: "functional-candidate-hash",
          reorganised_candidate_graph_hash: "layout-candidate-hash",
        },
      },
    },
  };
  const activeMessage = {
    turn_id: "0003",
    candidate: {
      graph: { nodes: [{ id: 3, type: "KSampler", pos: [320, 160] }], links: [] },
    },
    response: {
      layout_reorganisation: {
        result: "prepare_candidate",
        candidate_prepared: true,
      },
    },
  };

  const activeState = candidateActionState(panel, activeMessage, {
    applyEligibility: {
      applyable: false,
      reason: APPLY_ELIGIBILITY_REASON.NOT_LATEST,
      message: "Stale projected detail should not override active panel state.",
      warnings: ["not_latest"],
    },
  });

  assert.equal(activeState.visible, true);
  assert.equal(activeState.active, true);
  assert.equal(activeState.turnId, "0003");
  assert.equal(activeState.applyDisabled, false);
  assert.equal(activeState.rejectDisabled, false);
  assert.deepEqual(activeState.eligibility, {
    applyable: true,
    reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
    message: "Ready to apply layout candidate.",
    warnings: [],
  });

  const staleFunctionalCandidate = candidateActionState(
    panel,
    {
      turn_id: "0002",
      candidate: {
        graph: { nodes: [{ id: 3, type: "KSampler", pos: [20, 20] }], links: [] },
      },
      response: {
        layout_reorganisation: {
          result: "prepare_candidate",
          functional_candidate_graph_hash: "functional-candidate-hash",
          reorganised_candidate_graph_hash: "layout-candidate-hash",
        },
      },
    },
    {
      applyEligibility: {
        applyable: true,
        reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
        message: "Historical functional candidate was applyable before reorganisation.",
        warnings: [],
      },
    },
  );

  assert.equal(staleFunctionalCandidate.visible, true);
  assert.equal(staleFunctionalCandidate.active, false);
  assert.equal(staleFunctionalCandidate.eligibility.reason, APPLY_ELIGIBILITY_REASON.MISSING_CONTRACT);
  assert.equal(staleFunctionalCandidate.applyDisabled, true);
  assert.equal(staleFunctionalCandidate.rejectDisabled, true);

  const supersededLayoutCandidate = candidateActionState(
    panel,
    { turn_id: "0001", candidateGraph: { nodes: [{ id: 1 }] } },
    {
      applyEligibility: {
        applyable: false,
        reason: APPLY_ELIGIBILITY_REASON.SUPERSEDED,
        message: "This layout candidate was rejected.",
        warnings: ["superseded"],
      },
    },
  );

  assert.equal(supersededLayoutCandidate.active, false);
  assert.deepEqual(supersededLayoutCandidate.eligibility, {
    applyable: false,
    reason: APPLY_ELIGIBILITY_REASON.MISSING_CONTRACT,
    message: "Candidate transaction authority is missing. Apply and Reject are disabled until the session is reconciled.",
    warnings: ["missing_contract"],
  });
  assert.equal(supersededLayoutCandidate.applyDisabled, true);
  assert.equal(supersededLayoutCandidate.rejectDisabled, true);
});

test("disabledApplyEligibility and no-candidate action states remain immutable payload builders", () => {
  const warnings = ["server_blocked"];
  const disabled = disabledApplyEligibility(
    APPLY_ELIGIBILITY_REASON.SERVER_BLOCKED,
    "Blocked.",
    warnings,
  );
  warnings.push("mutated");

  assert.deepEqual(disabled, {
    applyable: false,
    reason: APPLY_ELIGIBILITY_REASON.SERVER_BLOCKED,
    message: "Blocked.",
    warnings: ["server_blocked"],
  });

  assert.deepEqual(candidateActionState({ state: { phase: "IDLE" } }), {
    visible: false,
    active: false,
    turnId: null,
    eligibility: {
      applyable: false,
      reason: APPLY_ELIGIBILITY_REASON.NO_CANDIDATE,
      message: "No candidate is available to apply.",
      warnings: [],
    },
    applyDisabled: true,
    rejectDisabled: true,
  });
});

test("exported helper APIs preserve normalization and bubble candidate detection", () => {
  const warnings = ["copied"];
  const normalized = normalizeApplyEligibility({
    applyable: true,
    reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
    message: "Ready.",
    warnings,
  });
  warnings.push("mutated");

  assert.deepEqual(normalized, {
    applyable: true,
    reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
    message: "Ready.",
    warnings: ["copied"],
  });
  assert.equal(normalizeApplyEligibility({ reason: "unknown" }), null);
  assert.equal(candidateGraphPresentForBubble({ candidateGraph: { nodes: [] } }), true);
  assert.equal(candidateGraphPresentForBubble({}, { candidateGraphPresent: false }), false);
});
