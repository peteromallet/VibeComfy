// agent_lifecycle_commit.js — Source-agnostic lifecycle commit facade
//
// This module is a THIN, source-agnostic commit layer that sits on top of two
// existing pure authorities:
//
//   * `transition(panel, event, payload)` from `agent_edit_lifecycle.js` — the
//     single panel-state reducer. It owns every state mutation and returns a
//     plain obligations object describing the render/dirty work the caller must
//     perform afterwards.
//   * the response-contract selectors (`readOutcome`, `readTurnIdentity`,
//     `readApplyCandidate`, `readFieldChanges`, `readCustomNodeResolution`,
//     `outcomeRequiresCustomNodes`) from `agent_edit_response_contract.js` —
//     pure projections of a canonical agent-edit response envelope into the
//     concrete values each transition expects.
//
// Production, preview, and replay all feed CANONICAL envelopes here; the helpers
// project them identically and delegate to `transition(...)`. The reducer stays
// the only lifecycle authority, so this module does not introduce a parallel
// lifecycle reducer (North Star: eliminate parallel preview/replay reducers).
//
// HARD CONTRACT — this module performs NO side effects of its own. It MUST NOT:
//   * fetch / POST (transport),
//   * touch the canvas, overlay, or DOM,
//   * read/write history, storage, or scroll,
//   * perform CAS or accept/reject decisions,
//   * branch on whether the source is production, demo/preview, or replay.
// Every helper returns the PLAIN obligations object produced by `transition(...)`
// (plus lifecycle state already mutated by the reducer). Callers — the source
// orchestrators in `vibecomfy_roundtrip.js` and the future preview/replay
// adapters — own all side effects (canvas apply, layout preview, history push,
// render, scoped storage, etc.).

import { transition } from "./agent_edit_lifecycle.js";
import {
  readOutcome,
  readTurnIdentity,
  readApplyCandidate,
  readFieldChanges,
  readCustomNodeResolution,
  outcomeRequiresCustomNodes,
} from "./agent_edit_response_contract.js";
import { applyEligibility } from "./agent_candidate_actions.js";

// ---------------------------------------------------------------------------
// Pure projection utilities (response-contract selectors wrapped defensively).
// Exported so preview/replay fixture adapters can reuse the same projection the
// commit helpers use, keeping the source-agnostic contract in one place.
// ---------------------------------------------------------------------------

function _safeRead(readFn, source, options) {
  if (!source || typeof source !== "object") {
    return null;
  }
  try {
    return readFn(source, options);
  } catch (_e) {
    return null;
  }
}

/** Read durable turn identity (session/turn/baseline ids) from a canonical envelope. */
export function readCommitTurnIdentity(source, options = {}) {
  return _safeRead(readTurnIdentity, source, { allowLegacy: false, ...options });
}

/** Read the apply-candidate projection (graph, eligibility, hashes) from a canonical envelope. */
export function readCommitApplyCandidate(source, options = {}) {
  return _safeRead(readApplyCandidate, source, { allowLegacy: false, ...options });
}

/** Read normalized field-changes from a canonical envelope. */
export function readCommitFieldChanges(source, options = {}) {
  return _safeRead(readFieldChanges, source, { allowLegacy: false, ...options });
}

/** Read the canonical outcome from a canonical envelope. */
export function readCommitOutcome(source, options = {}) {
  return _safeRead(readOutcome, source, options);
}

/** Read the custom-node resolution projection from a canonical envelope. */
export function readCommitCustomNodeResolution(source, options = {}) {
  return _safeRead(readCustomNodeResolution, source, options);
}

function _normalizeFieldChangeList(list) {
  if (!Array.isArray(list)) {
    return [];
  }
  return list
    .map((change) => (change && typeof change === "object" ? change : null))
    .filter((change) => change !== null);
}

/**
 * Project the submit/response field-changes selector output into the canonical
 * `{ directChanges, outcomeChanges, legacyChanges, batchTurnChanges, all }`
 * shape consumed by the lifecycle reducer.
 */
export function normalizeCommitFieldChangesFromSubmit(result, options = {}) {
  if (!result || typeof result !== "object") {
    return {
      directChanges: [],
      outcomeChanges: [],
      legacyChanges: [],
      batchTurnChanges: [],
      all: [],
    };
  }
  const selectorChanges = readCommitFieldChanges(result, {
    endpoint: options.endpoint || "submit:field-changes",
  });
  if (!selectorChanges) {
    return {
      directChanges: [],
      outcomeChanges: [],
      legacyChanges: [],
      batchTurnChanges: [],
      all: [],
    };
  }
  const directChanges = _normalizeFieldChangeList(selectorChanges.directChanges);
  const outcomeChanges = _normalizeFieldChangeList(selectorChanges.outcomeChanges);
  const legacyChanges = _normalizeFieldChangeList(selectorChanges.legacyChanges);
  const batchTurnChanges = Array.isArray(selectorChanges.batchTurnChanges)
    ? selectorChanges.batchTurnChanges.map((turn) => ({
        turn_number:
          turn && typeof turn === "object" && typeof turn.turnNumber === "number"
            ? turn.turnNumber
            : null,
        changes: _normalizeFieldChangeList(turn && turn.changes),
      }))
    : [];
  return {
    directChanges,
    outcomeChanges,
    legacyChanges,
    batchTurnChanges,
    all: [
      ...directChanges,
      ...outcomeChanges,
      ...legacyChanges,
      ...batchTurnChanges.flatMap((turn) => turn.changes),
    ],
  };
}

/**
 * Normalize the apply-eligibility contract for a candidate graph, mirroring the
 * reducer's expected `applyEligibility` value. Uses a throwaway pseudo-panel so
 * no real panel state is mutated as a side effect.
 */
export function normalizeCommitApplyEligibility(candidateGraph, eligibility) {
  return applyEligibility(
    {
      state: {
        candidateGraph: candidateGraph || null,
        applyEligibility: eligibility || null,
      },
    },
    null,
    { missingContractAsNull: true },
  );
}

// ---------------------------------------------------------------------------
// Pure outcome predicates.
//
// These mirror the small, source-agnostic predicates currently living privately
// in `vibecomfy_roundtrip.js`. They are duplicated here (rather than imported)
// because importing the roundtrip orchestrator would pull transport/canvas
// side effects into this module. Keeping them local preserves the "no side
// effects / no source branching" contract while still selecting the correct
// transition event deterministically from a canonical outcome.
// ---------------------------------------------------------------------------

function _outcomeKindIs(outcome, kind) {
  return Boolean(outcome && typeof outcome === "object" && outcome.kind === kind);
}

export function outcomeRequiresClarification(outcome) {
  return _outcomeKindIs(outcome, "clarify");
}

export function outcomeIsNoop(outcome) {
  return _outcomeKindIs(outcome, "noop");
}

export function clarificationMessageFromOutcome(outcome, fallbackMessage = null) {
  if (!outcome || typeof outcome !== "object") {
    return fallbackMessage;
  }
  if (typeof outcome.question === "string" && outcome.question.trim()) {
    return outcome.question.trim();
  }
  return fallbackMessage;
}

export function outcomeHasClarificationPrompt(outcome) {
  return typeof clarificationMessageFromOutcome(outcome) === "string";
}

/**
 * Classify a canonical outcome into the discrete terminal kind this module
 * dispatches on. Returns one of:
 *   "clarify_only" | "requires_custom_nodes" | "noop"
 *   | "candidate" | "edit_clarify" | "error"
 *
 * `candidateGraph` is required to distinguish a real candidate arrival from a
 * clarify-only turn (an outcome may carry `kind: "clarify"` AND a candidate
 * graph, in which case the turn lands a candidate while surfacing a question).
 */
export function classifyCommitOutcome(outcome, candidateGraph) {
  if (outcomeRequiresCustomNodes(outcome)) {
    return "requires_custom_nodes";
  }
  if (outcomeRequiresClarification(outcome) && !candidateGraph) {
    return "clarify_only";
  }
  if (outcomeIsNoop(outcome)) {
    return "noop";
  }
  if (candidateGraph && typeof candidateGraph === "object") {
    return outcomeHasClarificationPrompt(outcome) ? "edit_clarify" : "candidate";
  }
  return "error";
}

/**
 * Resolve the candidate graph hash from, in priority order: an explicit caller
 * override, the apply-candidate projection's reported hash, or null. The raw
 * sha256 fallback lives in the orchestrator (it depends on private helpers and
 * async hashing); callers that need exact parity may pass `candidateGraphHash`.
 */
export function resolveCommitCandidateGraphHash(applyCandidate, explicitHash = null) {
  if (typeof explicitHash === "string" && explicitHash) {
    return explicitHash;
  }
  if (applyCandidate && typeof applyCandidate === "object") {
    if (typeof applyCandidate.candidateGraphHash === "string" && applyCandidate.candidateGraphHash) {
      return applyCandidate.candidateGraphHash;
    }
    if (typeof applyCandidate.graphHash === "string" && applyCandidate.graphHash) {
      return applyCandidate.graphHash;
    }
  }
  return null;
}

function _coerceDebugPayload(value) {
  if (value && typeof value === "object") {
    return value;
  }
  return {};
}

function _submitEpochPayload(payload) {
  return Number.isFinite(payload?.submitEpoch)
    ? { submitEpoch: Number(payload.submitEpoch) }
    : {};
}

// ---------------------------------------------------------------------------
// Commit helpers. Each one projects a canonical envelope and delegates to
// `transition(...)`, returning the plain obligations object.
// ---------------------------------------------------------------------------

/**
 * Commit the optimistic submit phase (move to SUBMITTING, record lastSubmit,
 * mint a submit epoch). This wraps the `SUBMIT_START` transition.
 *
 * The orchestrator owns transport (the actual fetch), abort-controller
 * registration (`SUBMIT_ABORT_CONTROLLER`), and `SUBMIT_IN_FLIGHT`; this helper
 * only commits the optimistic panel state.
 *
 * @param {object} panel - the agent panel (mutated by the reducer only).
 * @param {object} payload - `{ lastSubmit?, debugPayload?, submitEpoch? }`.
 * @returns {object} plain obligations from `transition(...)`, including
 *   `submitEpoch` when the reducer mints one.
 */
export function commitOptimisticSubmit(panel, payload = {}) {
  return transition(panel, "SUBMIT_START", {
    lastSubmit: payload.lastSubmit || null,
    debugPayload: _coerceDebugPayload(payload.debugPayload),
    ..._submitEpochPayload(payload),
  });
}

/**
 * Commit a terminal agent-edit response. This is the source-agnostic dispatcher
 * over the success-class terminal outcomes (clarify-only, requires-custom-nodes,
 * noop, candidate, edit-clarify) plus the explicit error/failure path.
 *
 * It projects the canonical `result` envelope via the response-contract
 * selectors, classifies the outcome, and fires exactly one of:
 *   CLARIFY_ONLY_RESPONSE | REQUIRES_CUSTOM_NODES_RESPONSE | NOOP_RESPONSE
 *   | OK_CANDIDATE_RESPONSE | EDIT_CLARIFY_RESPONSE
 *   | SUBMIT_NETWORK_FAILURE (when `payload.failure` is provided, or when the
 *     envelope cannot be classified into any success terminal).
 *
 * The orchestrator keeps ALL side effects: arrival canvas snapshot, layout
 * preview activation, history/turn-status push, pending-message promotion,
 * batch-turn reconciliation, render, and dirty scheduling. This helper returns
 * the plain obligations for the orchestrator to fulfill.
 *
 * @param {object} panel - the agent panel.
 * @param {object} payload - canonical commit envelope:
 *   - {object} [result] - canonical response envelope (`.raw` unwrapped first).
 *   - {object} [outcome] - pre-read outcome (otherwise projected from `result`).
 *   - {object} [failure] - explicit failure object → error terminal.
 *   - {string} [syntheticAgentMessage] - optional synthetic message for errors.
 *   - {object} [candidateGraph] - prepared candidate graph override (callers
 *     that decorate/clone graphs pass this for exact parity; otherwise the
 *     apply-candidate projection's graph is used).
 *   - {string} [candidateGraphHash] - explicit graph-hash override.
 *   - {object} [debugPayload] - merged into the transition debug payload.
 *   - {string} [message] / {string} [auditRef] - message/audit overrides.
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitTerminalResponse(panel, payload = {}) {
  const result = payload.result || null;
  const raw = (result && (result.raw || result)) || null;
  const selectorSource =
    result && typeof result === "object"
      ? result
      : raw;
  const explicitFailure = payload.failure || null;

  // ── Explicit error/failure terminal ──────────────────────────────────
  if (explicitFailure) {
    return transition(panel, "SUBMIT_NETWORK_FAILURE", {
      ..._submitEpochPayload(payload),
      failure: explicitFailure,
      syntheticAgentMessage: payload.syntheticAgentMessage || null,
      debugPayload: {
        ...explicitFailure,
        ...(panel && panel.state ? { last_submit: panel.state.lastSubmit } : {}),
        ..._coerceDebugPayload(payload.debugPayload),
      },
    });
  }

  const outcome = payload.outcome || readCommitOutcome(selectorSource) || null;
  const turnIdentity = readCommitTurnIdentity(selectorSource, { endpoint: "submit:identity" });
  const applyCandidate = readCommitApplyCandidate(selectorSource, { endpoint: "submit:candidate" });
  const candidateGraph =
    payload.candidateGraph !== undefined
      ? payload.candidateGraph
      : (applyCandidate && applyCandidate.graph) || null;
  const sessionId = (turnIdentity && turnIdentity.sessionId) || null;
  const turnId = (turnIdentity && turnIdentity.turnId) || null;
  const baselineTurnId = (turnIdentity && turnIdentity.baselineTurnId) || null;
  const auditRef = payload.auditRef !== undefined ? payload.auditRef : (result && result.auditRef) || null;
  const fallbackMessage =
    typeof result?.message === "string" && result.message.trim()
      ? result.message.trim()
      : null;
  const lastSubmitFieldChanges =
    payload.lastSubmitFieldChanges !== undefined
      ? payload.lastSubmitFieldChanges
      : normalizeCommitFieldChangesFromSubmit(selectorSource);
  // Callers that already clone/decorate change_details (e.g. the production
  // roundtrip orchestrator) may pass the prepared value to avoid an uncloned
  // reference aliasing the response envelope inside lifecycle state.
  const changeDetails =
    payload.changeDetails !== undefined
      ? payload.changeDetails
      : (raw && raw.change_details && typeof raw.change_details === "object"
        ? raw.change_details
        : null);

  const kind = classifyCommitOutcome(outcome, candidateGraph);

  switch (kind) {
    case "clarify_only": {
      const clarifyMessage =
        clarificationMessageFromOutcome(outcome, fallbackMessage) ||
        fallbackMessage ||
        "The agent needs clarification before it can edit the graph.";
      const clarification = {
        message: clarifyMessage,
        turn_id: turnId,
        session_id: sessionId,
      };
      return transition(panel, "CLARIFY_ONLY_RESPONSE", {
        ..._submitEpochPayload(payload),
        result: raw || result,
        sessionId,
        turnId,
        baselineTurnId,
        auditRef,
        clarification,
        message: clarifyMessage,
        lastSubmitFieldChanges,
        debugPayload: {
          ...(raw || result || {}),
          ...(panel && panel.state ? { last_submit: panel.state.lastSubmit } : {}),
          ..._coerceDebugPayload(payload.debugPayload),
        },
      });
    }

    case "requires_custom_nodes": {
      const customNodeMessage =
        fallbackMessage ||
        (typeof result?.reply === "string" && result.reply.trim()
          ? result.reply.trim()
          : "VibeComfy could not confirm automatic installation for this edit.");
      const customNodeResolution =
        payload.customNodeResolution !== undefined
          ? payload.customNodeResolution
          : readCommitCustomNodeResolution(raw, {
            endpoint: "submit:custom-nodes",
          });
      return transition(panel, "REQUIRES_CUSTOM_NODES_RESPONSE", {
        ..._submitEpochPayload(payload),
        result: raw || result,
        sessionId,
        turnId,
        baselineTurnId,
        auditRef,
        message: payload.message || customNodeMessage,
        customNodeResolution,
        debugPayload: {
          ...(raw || result || {}),
          customNodeResolution,
          ...(panel && panel.state ? { last_submit: panel.state.lastSubmit } : {}),
          ..._coerceDebugPayload(payload.debugPayload),
        },
      });
    }

    case "noop": {
      const noopMessage =
        payload.message ||
        fallbackMessage ||
        (outcome && typeof outcome.reason === "string" && outcome.reason.trim()
          ? outcome.reason.trim()
          : "No change needed.");
      return transition(panel, "NOOP_RESPONSE", {
        ..._submitEpochPayload(payload),
        result: raw || result,
        sessionId,
        turnId,
        baselineTurnId,
        auditRef,
        message: noopMessage,
        lastSubmitFieldChanges,
        changeDetails,
        debugPayload: {
          ...(raw || result || {}),
          ...(panel && panel.state ? { last_submit: panel.state.lastSubmit } : {}),
          ..._coerceDebugPayload(payload.debugPayload),
        },
      });
    }

    case "candidate":
    case "edit_clarify": {
      const normalizedEligibility = normalizeCommitApplyEligibility(
        candidateGraph,
        payload.applyEligibility !== undefined
          ? payload.applyEligibility
          : (applyCandidate && applyCandidate.eligibility) || null,
      );
      const candidateGraphHash = resolveCommitCandidateGraphHash(
        applyCandidate,
        payload.candidateGraphHash,
      );
      const clarification =
        kind === "edit_clarify"
          ? {
              message: clarificationMessageFromOutcome(outcome, (result && result.message) || null),
              turn_id: turnId,
              session_id: sessionId,
            }
          : null;
      return transition(
        panel,
        kind === "edit_clarify" ? "EDIT_CLARIFY_RESPONSE" : "OK_CANDIDATE_RESPONSE",
        {
          ..._submitEpochPayload(payload),
          result: raw || result,
          sessionId,
          turnId,
          baselineTurnId,
          candidateGraph,
          candidateGraphHash,
          serverSubmitGraphHash:
            payload.serverSubmitGraphHash !== undefined
              ? payload.serverSubmitGraphHash
              : (applyCandidate && applyCandidate.submitGraphHash) || null,
          queueAllowed:
            payload.queueAllowed !== undefined
              ? Boolean(payload.queueAllowed)
              : Boolean(result && result.queueAllowed),
          auditRef,
          clarification,
          applyEligibility: normalizedEligibility,
          lastSubmitFieldChanges,
          changeDetails,
          debugPayload: _coerceDebugPayload(payload.debugPayload),
        },
      );
    }

    case "error":
    default: {
      // Unclassifiable success envelope with no candidate graph and no explicit
      // failure → treat as a malformed terminal. The orchestrator may pass an
      // explicit `failure` for richer diagnostics; otherwise a minimal plain
      // failure object is synthesized (no transport/error-utility imports here).
      const failure =
        explicitFailure || {
          ok: false,
          kind: "MalformedResponse",
          message:
            payload.message ||
            fallbackMessage ||
            "The agent response could not be interpreted as an editable candidate.",
          graph_unchanged: true,
          retryable: false,
        };
      return transition(panel, "SUBMIT_NETWORK_FAILURE", {
        ..._submitEpochPayload(payload),
        failure,
        syntheticAgentMessage: payload.syntheticAgentMessage || null,
        debugPayload: {
          ...failure,
          ...(raw || {}),
          ...(panel && panel.state ? { last_submit: panel.state.lastSubmit } : {}),
          ..._coerceDebugPayload(payload.debugPayload),
        },
      });
    }
  }
}

/**
 * Commit a successful chat transcript rehydrate. Wraps `CHAT_REHYDRATE_SUCCESS`.
 *
 * The orchestrator owns transport (fetch chat detail), scoped-storage writes,
 * thread render-state reset, latest-candidate restore, and render. This helper
 * commits only the canonical transcript projection + rehydrate obligations.
 *
 * @param {object} panel - the agent panel.
 * @param {object} payload - `{ requestEpoch, messages, chatSessionPath?,
 *   chatDetailJsonPath?, chatSessionPathResolved?, chatDetailJsonPathResolved?,
 *   sessionId?, latestTurnId?, latestCandidate? }`.
 * @returns {object} plain obligations from `transition(...)` (may include
 *   `stale: true` when the request epoch is superseded).
 */
export function commitTranscriptRehydrate(panel, payload = {}) {
  return transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    requestEpoch: payload.requestEpoch,
    messages: payload.messages,
    chatSessionPath: payload.sessionPath,
    chatDetailJsonPath: payload.detailJsonPath,
    chatSessionPathResolved: payload.sessionPathResolved,
    chatDetailJsonPathResolved: payload.detailJsonPathResolved,
    sessionId: payload.sessionId,
    latestTurnId: payload.latestTurnId,
    latestCandidate: payload.latestCandidate,
  });
}

/**
 * Commit the restoration of the latest candidate discovered during rehydrate.
 * Wraps `CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE`.
 *
 * The caller projects the latest-candidate envelope via the response-contract
 * selectors (or the exported `readCommitApplyCandidate` /
 * `readCommitTurnIdentity` helpers) and passes the concrete values; this helper
 * only commits the restore obligations. Scope/cross-session boundary refusal
 * is enforced by the reducer via `requestScopeId` / `candidateSessionId`.
 *
 * @param {object} panel - the agent panel.
 * @param {object} payload - see the transition handler for the full field set;
 *   key fields: `requestScopeId`, `candidateSessionId`, `sessionId`, `turnId`,
 *   `baselineTurnId`, `baseline`, `candidateGraph`, `candidateGraphHash`,
 *   `candidateReport`, `serverSubmitGraphHash`, `message`, `applyEligibility`,
 *   `applyAllowed`, `canvasApplyAllowed`, `queueAllowed`, `auditRef`,
 *   `changeDetails`, `debugPayload`, `lastSubmitFieldChanges`.
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitLatestCandidateRestore(panel, payload = {}) {
  return transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", payload);
}

/**
 * Commit an apply-resolved reflection (a candidate was accepted and the baseline
 * advanced). Wraps `APPLY_SUCCESS`.
 *
 * The orchestrator owns transport (the accept POST / CAS decision), canvas
 * apply, layout-preview clearing, undo stack, and render. This helper only
 * commits the post-apply panel state.
 *
 * @param {object} panel - the agent panel.
 * @param {object} payload - `{ accepted, lastAppliedChanges?, toast?,
 *   undoStackDepth?, debugPayload? }`.
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitApplyResolved(panel, payload = {}) {
  return transition(panel, "APPLY_SUCCESS", {
    accepted: payload.accepted,
    ...(payload.lastAppliedChanges !== undefined ? { lastAppliedChanges: payload.lastAppliedChanges } : {}),
    ...(payload.undoStackDepth !== undefined ? { undoStackDepth: payload.undoStackDepth } : {}),
    ...(payload.toast !== undefined ? { toast: payload.toast } : {}),
    ...(payload.debugPayload !== undefined ? { debugPayload: payload.debugPayload } : {}),
  });
}

/**
 * Restore a previously captured lifecycle baseline allowlist.
 *
 * This is used by source adapters that need deterministic navigation over
 * already-captured lifecycle state. The reducer owns the field writes; callers
 * still own source metadata, graph visualization, rendering, and transport.
 *
 * @param {object} panel - the agent panel.
 * @param {object} payload - `{ baseline, debugPayload? }`.
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitLifecycleBaselineRestore(panel, payload = {}) {
  return transition(panel, "RESTORE_LIFECYCLE_BASELINE", {
    baseline: payload.baseline || null,
    ...(payload.debugPayload !== undefined ? { debugPayload: payload.debugPayload } : {}),
  });
}

/**
 * Commit a lifecycle reset: discard the current candidate, clear review/apply
 * flags, and return the panel to idle. Wraps `REJECT_SUCCESS`.
 *
 * Per the migration plan this helper is for completed local/demo reset outcomes
 * where no production POST is involved; production reject routing (which also
 * performs a rebaseline-recovery sync) is wired by the production orchestrator.
 * This helper performs only the panel-state reset and returns plain obligations.
 *
 * @param {object} panel - the agent panel.
 * @param {object} payload - `{ rejected, message?, toast?, debugPayload? }`.
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitLifecycleReset(panel, payload = {}) {
  return transition(panel, "REJECT_SUCCESS", {
    rejected: payload.rejected,
    ...(payload.message !== undefined ? { message: payload.message } : {}),
    ...(payload.toast !== undefined ? { toast: payload.toast } : {}),
    ...(payload.debugPayload !== undefined ? { debugPayload: payload.debugPayload } : {}),
  });
}

// ── T24: Transaction lifecycle commit helpers ──────────────────────────────

/**
 * Commit the prepare-started phase.  Records the mutation plan hash, generation,
 * and lease nonce before the server CAS prepare call.
 *
 * @param {object} panel
 * @param {object} payload - `{ mutationPlanHash?, planHash?, generation?,
 *   leaseNonce?, turnId?, sessionId?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitPrepareStarted(panel, payload = {}) {
  return transition(panel, "PREPARE_STARTED", payload);
}

/**
 * Commit a successful server prepare.  Records the prepared receipt (CAS without
 * baseline advance).
 *
 * @param {object} panel
 * @param {object} payload - `{ receipt?, preparedReceipt?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitPrepareSuccess(panel, payload = {}) {
  return transition(panel, "PREPARE_SUCCESS", payload);
}

/**
 * Commit a failed server prepare.
 *
 * @param {object} panel
 * @param {object} payload - `{ failure?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitPrepareFailure(panel, payload = {}) {
  return transition(panel, "PREPARE_FAILURE", payload);
}

/**
 * Commit the start of canvas hash verification after apply.
 *
 * @param {object} panel
 * @param {object} payload - `{ debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitVerifyCanvasStarted(panel, payload = {}) {
  return transition(panel, "VERIFY_CANVAS_STARTED", payload);
}

/**
 * Commit successful canvas hash verification.  Records the verified receipt.
 *
 * @param {object} panel
 * @param {object} payload - `{ receipt?, verifiedReceipt?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitVerifyCanvasSuccess(panel, payload = {}) {
  return transition(panel, "VERIFY_CANVAS_SUCCESS", payload);
}

/**
 * Commit failed canvas hash verification.
 *
 * @param {object} panel
 * @param {object} payload - `{ failure?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitVerifyCanvasFailure(panel, payload = {}) {
  return transition(panel, "VERIFY_CANVAS_FAILURE", payload);
}

/**
 * Commit the start of server finalize.
 *
 * @param {object} panel
 * @param {object} payload - `{ debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitFinalizeStarted(panel, payload = {}) {
  return transition(panel, "FINALIZE_STARTED", payload);
}

/**
 * Commit a successful server finalize.  Records the finalized receipt,
 * advances the baseline, and clears the candidate.
 *
 * @param {object} panel
 * @param {object} payload - `{ receipt?, finalizedReceipt?, accepted?,
 *   lastAppliedChanges?, undoStackDepth?, toast?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitFinalizeSuccess(panel, payload = {}) {
  return transition(panel, "FINALIZE_SUCCESS", {
    receipt: payload.receipt || payload.finalizedReceipt || null,
    accepted: payload.accepted || payload.receipt || null,
    ...(payload.candidateTransaction !== undefined
      ? { candidateTransaction: payload.candidateTransaction }
      : {}),
    ...(payload.lastAppliedChanges !== undefined ? { lastAppliedChanges: payload.lastAppliedChanges } : {}),
    ...(payload.undoStackDepth !== undefined ? { undoStackDepth: payload.undoStackDepth } : {}),
    ...(payload.toast !== undefined ? { toast: payload.toast } : {}),
    ...(payload.debugPayload !== undefined ? { debugPayload: payload.debugPayload } : {}),
  });
}

/**
 * Commit a failed server finalize.
 *
 * @param {object} panel
 * @param {object} payload - `{ failure?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitFinalizeFailure(panel, payload = {}) {
  return transition(panel, "FINALIZE_FAILURE", payload);
}

/**
 * Commit the start of server rollback.
 *
 * @param {object} panel
 * @param {object} payload - `{ debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitRollbackStarted(panel, payload = {}) {
  return transition(panel, "ROLLBACK_STARTED", payload);
}

/**
 * Commit a successful server rollback.  Records the rollback receipt and clears
 * the candidate.
 *
 * @param {object} panel
 * @param {object} payload - `{ receipt?, rollbackReceipt?, message?,
 *   toast?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitRollbackSuccess(panel, payload = {}) {
  return transition(panel, "ROLLBACK_SUCCESS", {
    receipt: payload.receipt || payload.rollbackReceipt || null,
    ...(payload.candidateTransaction !== undefined
      ? { candidateTransaction: payload.candidateTransaction }
      : {}),
    ...(payload.message !== undefined ? { message: payload.message } : {}),
    ...(payload.toast !== undefined ? { toast: payload.toast } : {}),
    ...(payload.debugPayload !== undefined ? { debugPayload: payload.debugPayload } : {}),
  });
}

/**
 * Commit a failed server rollback.
 *
 * @param {object} panel
 * @param {object} payload - `{ failure?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitRollbackFailure(panel, payload = {}) {
  return transition(panel, "ROLLBACK_FAILURE", payload);
}

/**
 * Commit reconciliation of durable receipts from the server (reload recovery).
 *
 * @param {object} panel
 * @param {object} payload - `{ receipts?, debugPayload? }`
 * @returns {object} plain obligations from `transition(...)`.
 */
export function commitReconcileReceipts(panel, payload = {}) {
  return transition(panel, "RECONCILE_RECEIPTS", {
    receipts: payload.receipts || null,
    ...(payload.debugPayload !== undefined ? { debugPayload: payload.debugPayload } : {}),
  });
}
