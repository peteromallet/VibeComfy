// agent_turn_reducer.js — Pure turn projection and reduction helpers
//
// This module owns stable turn keys, execution-event projections, outcome
// classification, defensive response selectors, and batch-turn normalization.
// It has no panel, lifecycle, DOM, app, transport, or rendering dependencies.

import {
  readFieldChanges,
  readTurnIdentity,
} from "./agent_edit_response_contract.js";
import { jsonClone as clonePlainData } from "./json_clone.js";

const PANEL_TURN_LIMIT = 64;
const BATCH_SOURCE_PRIORITY = {
  websocket: 1,
  response: 2,
};
const BATCH_TERMINAL_STATUSES = new Set(["clarify", "done", "budget_exhausted"]);

export function stableTurnSessionId(value) {
  return typeof value === "string" && value ? value : "none";
}

export function batchTurnKey(sessionId, turnNumber) {
  return `batch:${stableTurnSessionId(sessionId)}:${turnNumber}`;
}

export function durableTurnKey(entry) {
  const sessionId = stableTurnSessionId(entry?.session_id);
  const status = entry?.status || "unknown";
  if (entry?.turn_id) {
    return `durable:${sessionId}:${entry.turn_id}:${status}`;
  }
  const fallback =
    entry?.timestamp
    || entry?.message
    || entry?.task
    || entry?.failure_kind
    || "pending";
  return `durable:${sessionId}:${status}:${fallback}`;
}

export function sortPanelTurns(turns) {
  const durable = [];
  const batch = [];
  const other = [];
  for (const entry of Array.isArray(turns) ? turns : []) {
    if (entry?.entry_type === "durable") {
      durable.push(entry);
    } else if (entry?.entry_type === "batch") {
      batch.push(entry);
    } else {
      other.push(entry);
    }
  }
  batch.sort((left, right) => {
    const leftNumber = Number.isFinite(left?.turn_number) ? left.turn_number : -1;
    const rightNumber = Number.isFinite(right?.turn_number) ? right.turn_number : -1;
    return rightNumber - leftNumber;
  });
  return [...durable, ...batch, ...other].slice(0, PANEL_TURN_LIMIT);
}

export function executionEventKeyForTurn(entry, index = null) {
  if (entry?.turn_key) {
    return `turn:${entry.turn_key}`;
  }
  if (entry?.entry_type === "batch") {
    return `turn:${batchTurnKey(entry.session_id, entry.turn_number)}`;
  }
  if (entry?.entry_type === "durable") {
    return `turn:${durableTurnKey(entry)}`;
  }
  const sessionId = stableTurnSessionId(entry?.session_id);
  const turnId = entry?.turn_id || `entry-${index ?? "new"}`;
  return `event:${sessionId}:${turnId}:${index ?? "new"}`;
}

export function executionEventTurnEntry(event) {
  if (!event || typeof event !== "object") {
    return null;
  }
  if (event.mirror === false) {
    return null;
  }
  if (event.turnEntry && typeof event.turnEntry === "object") {
    return clonePlainData(event.turnEntry);
  }
  if (event.entry_type === "batch" || event.entry_type === "durable") {
    return clonePlainData(event);
  }
  if (Array.isArray(event.batchTurns) && event.batchTurns.length) {
    return null;
  }
  if (!event.turn_id && !event.status && !event.message) {
    return null;
  }
  const entry = {
    entry_type: "durable",
    status: event.status || "done",
    session_id: event.session_id || null,
    turn_id: event.turn_id || null,
    baseline_turn_id: event.baseline_turn_id || null,
    task: event.task || null,
    timestamp: event.timestamp || null,
    failure_kind: event.failure_kind || null,
    failure_stage: event.failure_stage || null,
    message: event.message || null,
    audit_ref: event.audit_ref || event.auditRef || null,
    raw_payload: event.raw_payload || null,
  };
  entry.turn_key = durableTurnKey(entry);
  return entry;
}

export function outcomeRequiresClarification(outcome) {
  if (!outcome || typeof outcome !== "object") {
    return false;
  }
  return outcome.kind === "clarify";
}

export function outcomeIsNoop(outcome) {
  return Boolean(outcome && typeof outcome === "object" && outcome.kind === "noop");
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

export function readRoundtripTurnIdentity(source, options = {}) {
  if (!source || typeof source !== "object") {
    return null;
  }
  try {
    return readTurnIdentity(source, { allowLegacy: false, ...options });
  } catch (_e) {
    return null;
  }
}

export function readRoundtripFieldChanges(source, options = {}) {
  if (!source || typeof source !== "object") {
    return null;
  }
  try {
    return readFieldChanges(source, { allowLegacy: false, ...options });
  } catch (_e) {
    return null;
  }
}

export function normalizeBatchTurn(payload, { source = "response", sessionId = null, status = null, parentTurnId = null, canonicalActivity = null } = {}) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const resolvedSessionId =
    typeof payload.session_id === "string" && payload.session_id
      ? payload.session_id
      : (typeof sessionId === "string" && sessionId ? sessionId : null);
  const rawTurnNumber = payload.turn_number;
  const turnNumber =
    Number.isInteger(rawTurnNumber)
      ? rawTurnNumber
      : (typeof rawTurnNumber === "number" && Number.isFinite(rawTurnNumber)
        ? Math.trunc(rawTurnNumber)
        : null);
  if (!resolvedSessionId || turnNumber == null) {
    return null;
  }
  const outcome = payload.outcome && typeof payload.outcome === "object" ? payload.outcome : null;
  const normalizedStatus =
    status
    || (typeof payload.status === "string" && payload.status === "progress" ? "in_progress" : null)
    || (typeof payload.status === "string" && payload.status)
    || (outcomeRequiresClarification(outcome) ? "clarify" : "in_progress");
  const clarificationMessage = clarificationMessageFromOutcome(outcome);
  return {
    entry_type: "batch",
    turn_key: batchTurnKey(resolvedSessionId, turnNumber),
    session_id: resolvedSessionId,
    turn_id: typeof payload.turn_id === "string" && payload.turn_id ? payload.turn_id : null,
    parent_turn_id:
      typeof payload.parent_turn_id === "string" && payload.parent_turn_id
        ? payload.parent_turn_id
        : (typeof parentTurnId === "string" && parentTurnId ? parentTurnId : null),
    turn_number: turnNumber,
    status: normalizedStatus,
    message: typeof payload.message === "string" ? payload.message : null,
    timestamp: typeof payload.timestamp === "string" ? payload.timestamp : null,
    clarification_required: outcomeRequiresClarification(outcome),
    clarification_message: clarificationMessage,
    batch_ok: typeof payload.batch_ok === "boolean" ? payload.batch_ok : null,
    statement_count:
      typeof payload.statement_count === "number" && Number.isFinite(payload.statement_count)
        ? payload.statement_count
        : null,
    landed_op_count:
      typeof payload.landed_op_count === "number" && Number.isFinite(payload.landed_op_count)
        ? payload.landed_op_count
        : null,
    statements: Array.isArray(payload.statements) ? payload.statements : null,
    diagnostics: Array.isArray(payload.diagnostics) ? payload.diagnostics : null,
    budget: payload.budget && typeof payload.budget === "object" ? payload.budget : null,
    exit_mode: typeof payload.exit_mode === "string" ? payload.exit_mode : null,
    done_summary: typeof payload.done_summary === "string" ? payload.done_summary : null,
    audit_ref: payload.audit_ref && typeof payload.audit_ref === "object" ? payload.audit_ref : null,
    raw_payload: source === "response" ? payload : null,
    source,
    source_priority: BATCH_SOURCE_PRIORITY[source] || 0,
    canonical_activity: canonicalActivity,
  };
}

export function mergeBatchTurnEntry(existing, incoming) {
  if (!existing) {
    return incoming;
  }
  const existingPriority = existing.source_priority || 0;
  const incomingPriority = incoming.source_priority || 0;
  const keepExistingStatus =
    existingPriority > incomingPriority
    && BATCH_TERMINAL_STATUSES.has(existing.status)
    && !BATCH_TERMINAL_STATUSES.has(incoming.status);
  return {
    ...existing,
    ...incoming,
    status: keepExistingStatus ? existing.status : incoming.status,
    statements:
      Array.isArray(incoming.statements) && incoming.statements.length
        ? incoming.statements
        : (Array.isArray(existing.statements) ? existing.statements : null),
    diagnostics:
      Array.isArray(incoming.diagnostics) && incoming.diagnostics.length
        ? incoming.diagnostics
        : (Array.isArray(existing.diagnostics) ? existing.diagnostics : null),
    budget:
      incoming.budget && typeof incoming.budget === "object"
        ? incoming.budget
        : (existing.budget && typeof existing.budget === "object" ? existing.budget : null),
    raw_payload: incoming.raw_payload || existing.raw_payload || null,
    source_priority: Math.max(existingPriority, incomingPriority),
    // Preserve canonical activity state from the higher-priority source.
    canonical_activity: incoming.canonical_activity || existing.canonical_activity || null,
  };
}
