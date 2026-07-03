import test from "node:test";
import assert from "node:assert/strict";

import * as candidateActions from "../../vibecomfy/comfy_nodes/web/agent_candidate_actions.js";

const {
  APPLY_ELIGIBILITY_REASON,
  applyEligibility,
  disabledApplyEligibility,
  normalizeApplyEligibility,
  candidateGraphPresentForBubble,
  candidateActionState,
} = candidateActions;

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
      reason: APPLY_ELIGIBILITY_REASON.SUPERSEDED,
      message: "Already replaced.",
      warnings: ["superseded"],
    },
  );

  const staleHistorical = candidateActionState(panel, { turn_id: "0001", candidateGraph: { nodes: [] } });
  assert.equal(staleHistorical.active, false);
  assert.equal(staleHistorical.eligibility.reason, APPLY_ELIGIBILITY_REASON.NOT_LATEST);
  assert.equal(staleHistorical.applyDisabled, true);
  assert.equal(staleHistorical.rejectDisabled, true);
});

test("candidateActionState preserves optional reorganise candidate eligibility and stale history", () => {
  const panel = {
    state: {
      phase: "AWAITING_REVIEW",
      candidateGraph: { nodes: [{ id: 3, type: "KSampler", pos: [320, 160] }], links: [] },
      candidateGraphHash: "layout-candidate-hash",
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
  assert.equal(staleFunctionalCandidate.eligibility.reason, APPLY_ELIGIBILITY_REASON.NOT_LATEST);
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
    reason: APPLY_ELIGIBILITY_REASON.SUPERSEDED,
    message: "This layout candidate was rejected.",
    warnings: ["superseded"],
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
