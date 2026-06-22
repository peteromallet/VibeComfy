// agent_turn_feed.js — Browser-safe ESM normalizer for vibecomfy.agent_edit.turn events
//
// Exports pure helpers that validate and normalize websocket payloads emitted by
// the backend _agent_edit_turn_event_payload / _ws_send("vibecomfy.agent_edit.turn", ...)
// contract.  No Node, filesystem, or test-only dependencies.

// ── Internal helpers ────────────────────────────────────────────────────────

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asString(value) {
  return typeof value === "string" ? value : null;
}

function asBoolean(value) {
  return typeof value === "boolean" ? value : null;
}

function asFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asInteger(value) {
  return Number.isInteger(value) ? value : null;
}

function asStringArray(value) {
  return Array.isArray(value) ? value.filter((entry) => typeof entry === "string") : null;
}

function compactObject(value) {
  const compact = {};
  for (const [key, entry] of Object.entries(value)) {
    if (entry !== null && entry !== undefined) {
      compact[key] = entry;
    }
  }
  return compact;
}

// ── Constants ───────────────────────────────────────────────────────────────

export const AGENT_TURN_STATUSES = Object.freeze([
  "progress",
  "done",
  "clarify",
  "budget_exhausted",
  "error",
]);

export const BATCH_TERMINAL_STATUSES = new Set(["done", "clarify", "budget_exhausted", "error"]);

export const AGENT_TURN_ENTRY_TYPES = Object.freeze(["batch", "durable"]);

// ── Statement summary normalization ─────────────────────────────────────────

/**
 * Normalize a single batch statement entry.
 * Returns a sorted-key object with compact safe fields or null.
 */
function normalizeStatement(entry) {
  if (!isObject(entry)) {
    return null;
  }
  const opKind = asString(entry.op_kind) || asString(entry.kind) || asString(entry.op);
  if (!opKind) {
    return null;
  }
  return compactObject({
    // Core identity
    op_kind: opKind,
    status: asString(entry.status) || "unknown",
    message: asString(entry.message),
    // Compact safe fields from backend _brief_batch_statements contract
    statement_index: asInteger(entry.statement_index),
    ok: asBoolean(entry.ok),
    landed: asBoolean(entry.landed),
    teaching_hint: asString(entry.teaching_hint),
    dependency_cause: asString(entry.dependency_cause),
    // Node/field identifiers (compact, safe)
    source: asString(entry.source),
    target: asString(entry.target),
    field_path: asString(entry.field_path),
    target_node_id: asString(entry.target_node_id),
    // Compact diagnostics (code + message only, capped at 5)
    diagnostics: normalizeDiagnostics(entry.diagnostics),
    // Touched uids (capped at 10)
    touched_uids: asStringArray(entry.touched_uids)?.slice(0, 10),
  });
}

/**
 * Normalize an array of statement entries. Skips invalid entries.
 */
function normalizeStatements(raw) {
  if (!Array.isArray(raw)) {
    return null;
  }
  const normalized = [];
  for (const entry of raw) {
    const norm = normalizeStatement(entry);
    if (norm) {
      normalized.push(norm);
    }
  }
  return normalized.length > 0 ? Object.freeze(normalized) : null;
}

// ── Diagnostic entry normalization ──────────────────────────────────────────

/**
 * Normalize a single diagnostic entry to { code, message }.
 */
function normalizeDiagnostic(entry) {
  if (!isObject(entry)) {
    return null;
  }
  const code = asString(entry.code);
  if (!code) {
    return null;
  }
  return compactObject({
    code,
    message: asString(entry.message),
  });
}

/**
 * Normalize an array of diagnostic entries. Skips invalid entries.
 * Caps at 5 entries (backend contract limit).
 */
function normalizeDiagnostics(raw) {
  if (!Array.isArray(raw)) {
    return null;
  }
  const normalized = [];
  for (const entry of raw) {
    const norm = normalizeDiagnostic(entry);
    if (norm) {
      normalized.push(norm);
    }
  }
  return normalized.length > 0 ? Object.freeze(normalized.slice(0, 5)) : null;
}

// ── Timing normalization ────────────────────────────────────────────────────

function normalizeTiming(raw) {
  if (!isObject(raw)) {
    return null;
  }
  return compactObject({
    model_elapsed_ms: asFiniteNumber(raw.model_elapsed_ms),
    engine_elapsed_ms: asFiniteNumber(raw.engine_elapsed_ms),
    turn_elapsed_ms: asFiniteNumber(raw.turn_elapsed_ms),
  });
}

// ── Budget normalization ────────────────────────────────────────────────────

function normalizeBudget(raw) {
  if (!isObject(raw)) {
    return null;
  }
  return compactObject({
    remaining_batches: asInteger(raw.remaining_batches),
    consecutive_errors: asInteger(raw.consecutive_errors),
  });
}

// ── Main normalizer ─────────────────────────────────────────────────────────

/**
 * Normalize a raw vibecomfy.agent_edit.turn websocket event payload.
 *
 * Accepts both the direct payload and the event detail wrapper.
 * Returns a frozen normalized object with only validated fields,
 * or null if the payload is not a valid agent turn event.
 *
 * @param {*} raw - raw websocket event or event.detail
 * @returns {object|null} frozen normalized payload, or null
 */
export function normalizeAgentTurnPayload(raw) {
  // Accept event.detail style or direct payload
  const payload = isObject(raw?.detail) ? raw.detail : raw;
  if (!isObject(payload)) {
    return null;
  }

  const sessionId = asString(payload.session_id);
  if (!sessionId) {
    return null;
  }

  const status = asString(payload.status) || "progress";
  const entryType = asString(payload.entry_type) || "batch";

  const normalized = compactObject({
    // Identity (required)
    session_id: sessionId,
    turn_id: asString(payload.turn_id),
    turn_number: asInteger(payload.turn_number),

    // Status
    entry_type: entryType,
    status,

    // Timing
    emitted_at: asString(payload.emitted_at),

    // User-facing message (truncated to 500 chars per contract)
    message: payload.message && typeof payload.message === "string"
      ? payload.message.slice(0, 500)
      : null,

    // Clarification
    clarification_required: asBoolean(payload.clarification_required),
    clarification_message: payload.clarification_message && typeof payload.clarification_message === "string"
      ? payload.clarification_message.slice(0, 500)
      : null,

    // Batch progress
    batch_ok: asBoolean(payload.batch_ok),
    statement_count: asInteger(payload.statement_count),
    landed_op_count: asInteger(payload.landed_op_count),

    // Statements
    statements: normalizeStatements(payload.statements),

    // Diagnostics
    diagnostics: normalizeDiagnostics(payload.diagnostics),

    // Exit mode / done summary
    exit_mode: asString(payload.exit_mode),
    done_summary: payload.done_summary && typeof payload.done_summary === "string"
      ? payload.done_summary.slice(0, 500)
      : null,

    // Budget snapshot
    budget: normalizeBudget(payload.budget),

    // Timing
    timing: normalizeTiming(payload.timing),
  });

  return Object.freeze(normalized);
}

/**
 * Extract a payload from a websocket event argument.
 * Handles CustomEvent-like objects (event.detail) and plain objects.
 *
 * @param {*} event - websocket event or plain payload
 * @returns {object|null} the raw payload object, or null
 */
export function extractAgentTurnPayload(event) {
  if (isObject(event?.detail)) {
    return event.detail;
  }
  return isObject(event) ? event : null;
}

/**
 * Check whether an agent turn status is terminal.
 */
export function isTerminalAgentTurnStatus(status) {
  return BATCH_TERMINAL_STATUSES.has(String(status || "").toLowerCase());
}

/**
 * Derive a human-readable progress label from a normalized agent turn payload.
 */
export function agentTurnProgressLabel(normalized) {
  if (!isObject(normalized)) {
    return "Unknown";
  }
  const status = normalized.status || "progress";
  if (status === "done") {
    return "Complete";
  }
  if (status === "clarify") {
    return "Needs Clarification";
  }
  if (status === "budget_exhausted") {
    return "Budget Exhausted";
  }
  if (status === "error") {
    return "Turn Error";
  }
  // "progress"
  const landed = normalized.landed_op_count;
  if (typeof landed === "number" && landed > 0) {
    return `Executing (${landed} ops landed)`;
  }
  const turnNum = normalized.turn_number;
  if (typeof turnNum === "number" && turnNum > 0) {
    return `Researching (turn ${turnNum})`;
  }
  return "Deciding";
}

// ── Canonical activity derivation ───────────────────────────────────────────

/**
 * Protocol statement op_kind values that are terminators (not substantive
 * actions). These must never be chosen as the visible latest action when a
 * substantive statement exists.
 */
const PROTOCOL_TERMINATOR_OPS = new Set(["done", "exit", "terminal", "finish", "complete"]);

/**
 * Whether a statement is a substantive action (not a protocol terminator).
 */
function isSubstantiveStatement(stmt) {
  if (!stmt || typeof stmt !== "object") {
    return false;
  }
  const opKind = asString(stmt.op_kind);
  if (!opKind) {
    return false;
  }
  return !PROTOCOL_TERMINATOR_OPS.has(opKind.toLowerCase());
}

/**
 * Find the latest substantive (non-done()) statement from an array.
 * Returns the last statement where op_kind is not a protocol terminator,
 * or null if none exist.
 */
function latestSubstantiveStatement(statements) {
  if (!Array.isArray(statements) || !statements.length) {
    return null;
  }
  for (let i = statements.length - 1; i >= 0; i -= 1) {
    if (isSubstantiveStatement(statements[i])) {
      return statements[i];
    }
  }
  return null;
}

/**
 * Derive counts from statements array.
 */
function deriveStatementCounts(statements) {
  const counts = {
    total: 0,
    landed: 0,
    not_landed: 0,
    ok: 0,
    not_ok: 0,
  };
  if (!Array.isArray(statements)) {
    return counts;
  }
  for (const stmt of statements) {
    if (!stmt || typeof stmt !== "object") {
      continue;
    }
    counts.total += 1;
    if (stmt.landed === true) {
      counts.landed += 1;
    } else if (stmt.landed === false) {
      counts.not_landed += 1;
    }
    if (stmt.ok === true) {
      counts.ok += 1;
    } else if (stmt.ok === false) {
      counts.not_ok += 1;
    }
  }
  return counts;
}

/**
 * Derive a canonical activity state from a normalized agent turn payload.
 *
 * Accepts both normalized websocket payloads (from normalizeAgentTurnPayload)
 * and normalized batch turn entries (from normalizeBatchTurn in vibecomfy_roundtrip.js).
 * The input shape is flexible: it handles the compact normalized fields plus
 * additional fields that may be present on batch turn entries.
 *
 * Produces one canonical shape for websocket events and HTTP batch turns:
 *   - Normalizes legacy "progress" to "in_progress"
 *   - Derives phase_progress from statements/progress
 *   - Derives headline from latest substantive non-done() statement
 *   - Derives outcome semantics from status
 *   - Derives counts from statements
 *   - Packages diagnostics
 *   - Provides bounded safe details
 *
 * @param {object|null} normalized - normalized agent turn payload or batch turn entry
 * @returns {object} frozen canonical activity state
 */
export function deriveAgentActivityState(normalized) {
  if (!isObject(normalized)) {
    return Object.freeze({
      session_id: null,
      turn_id: null,
      turn_number: null,
      entry_type: null,
      status: "unknown",
      phase_progress: null,
      headline: null,
      outcome: { kind: "unknown", summary: null },
      latest_substantive_statement: null,
      counts: { total: 0, landed: 0, not_landed: 0, ok: 0, not_ok: 0 },
      diagnostics: null,
      details: null,
    });
  }

  const sessionId = asString(normalized.session_id);
  const turnId = asString(normalized.turn_id);
  const turnNumber = asInteger(normalized.turn_number);
  const entryType = asString(normalized.entry_type) || "batch";

  // ── Status normalization: legacy "progress" → "in_progress" ──────────
  let rawStatus = asString(normalized.status) || "progress";
  let status = rawStatus.toLowerCase();
  if (status === "progress") {
    status = "in_progress";
  }

  // ── Statements ────────────────────────────────────────────────────────
  const statements = Array.isArray(normalized.statements)
    ? normalized.statements
    : [];

  // ── Latest substantive statement (skip done() terminators) ────────────
  const latestSub = latestSubstantiveStatement(statements);

  // ── Headline derivation ───────────────────────────────────────────────
  // Walk statements backward to find the latest substantive statement
  // that carries a visible message (not just a silent op_kind).
  let headline = null;
  if (statements.length > 0) {
    for (let i = statements.length - 1; i >= 0; i -= 1) {
      const stmt = statements[i];
      if (!isSubstantiveStatement(stmt)) continue;
      const msg = asString(stmt.message)
        || asString(stmt.teaching_hint)
        || asString(stmt.source)
        || null;
      if (msg) {
        headline = msg;
        break;
      }
    }
    // If no substantive statement had a message, try any statement with a message
    if (!headline) {
      for (let i = statements.length - 1; i >= 0; i -= 1) {
        const stmt = statements[i];
        const msg = asString(stmt.message) || asString(stmt.teaching_hint) || null;
        if (msg) {
          headline = msg;
          break;
        }
      }
    }
  }
  // Fall back to turn-level message if no statement message
  if (!headline) {
    headline = asString(normalized.message)
      || asString(normalized.done_summary)
      || null;
  }

  // ── Outcome semantics ─────────────────────────────────────────────────
  const outcome = deriveOutcome(normalized, status, statements, latestSub);

  // ── Phase progress derivation ─────────────────────────────────────────
  const phaseProgress = derivePhaseProgress(normalized, status, statements, latestSub);

  // ── Counts ────────────────────────────────────────────────────────────
  const counts = deriveStatementCounts(statements);
  // Augment with turn-level counts if statement-level counts are sparse
  if (counts.total === 0) {
    const stmtCount = asInteger(normalized.statement_count);
    if (typeof stmtCount === "number" && stmtCount > 0) {
      counts.total = stmtCount;
    }
    const landedCount = asInteger(normalized.landed_op_count);
    if (typeof landedCount === "number" && landedCount > 0) {
      counts.landed = landedCount;
    }
  }

  // ── Diagnostics ───────────────────────────────────────────────────────
  const diagnostics = Array.isArray(normalized.diagnostics)
    ? normalized.diagnostics.slice(0, 5)
    : null;

  // ── Safe details (bounded, for expanded view) ─────────────────────────
  const details = buildSafeDetails(normalized, status, statements, latestSub, counts, diagnostics);

  return Object.freeze({
    session_id: sessionId,
    turn_id: turnId,
    turn_number: turnNumber,
    entry_type: entryType,
    status,
    phase_progress: phaseProgress,
    headline,
    outcome,
    latest_substantive_statement: latestSub,
    counts: Object.freeze(counts),
    diagnostics: diagnostics ? Object.freeze(diagnostics) : null,
    details: Object.freeze(details),
  });
}

/**
 * Derive outcome semantics from the normalized payload and derived state.
 */
function deriveOutcome(normalized, status, statements, latestSub) {
  const kind = status;

  let summary = null;

  if (status === "clarify" || normalized.clarification_required === true) {
    summary = asString(normalized.clarification_message)
      || asString(normalized.message)
      || "Clarification needed";
    return Object.freeze({
      kind: "clarify",
      summary,
      clarification_message: asString(normalized.clarification_message),
      clarification_required: true,
    });
  }

  if (status === "error") {
    const firstDiag = Array.isArray(normalized.diagnostics) && normalized.diagnostics[0];
    summary = (firstDiag && typeof firstDiag === "object"
      ? (asString(firstDiag.message) || asString(firstDiag.code))
      : null)
      || asString(normalized.message)
      || "An error occurred";
    return Object.freeze({
      kind: "error",
      summary,
      diagnostics: Array.isArray(normalized.diagnostics) ? normalized.diagnostics.slice(0, 5) : null,
    });
  }

  if (status === "budget_exhausted") {
    const budget = normalized.budget;
    const remaining = (budget && typeof budget === "object")
      ? asInteger(budget.remaining_batches)
      : null;
    summary = `Budget exhausted${typeof remaining === "number" ? ` (${remaining} turns remaining)` : ""}`;
    return Object.freeze({
      kind: "budget_exhausted",
      summary,
      budget: budget || null,
    });
  }

  if (status === "done") {
    // Check if this is an answer-only / noop turn (no substantive statements)
    const hasSubstantive = latestSub !== null;
    const hasStatements = statements.length > 0;
    const landedCount = (typeof normalized.landed_op_count === "number" && normalized.landed_op_count > 0)
      ? normalized.landed_op_count
      : 0;

    if (!hasSubstantive && !landedCount) {
      // Answer-only / no-edit turn
      summary = asString(normalized.done_summary)
        || asString(normalized.message)
        || "Answered";
      return Object.freeze({
        kind: "answered",
        summary,
        graph_changes: false,
        done_summary: asString(normalized.done_summary),
      });
    }

    // Edit turn completed
    summary = asString(normalized.done_summary)
      || asString(normalized.message)
      || (landedCount > 0 ? `${landedCount} change${landedCount !== 1 ? "s" : ""} applied` : "Completed");
    return Object.freeze({
      kind: "done",
      summary,
      landed_ops: landedCount,
      statement_count: statements.length || asInteger(normalized.statement_count) || 0,
      done_summary: asString(normalized.done_summary),
    });
  }

  // in_progress
  if (latestSub) {
    summary = asString(latestSub.message)
      || asString(latestSub.teaching_hint)
      || asString(normalized.message)
      || "Working...";
  } else {
    summary = asString(normalized.message) || "Working...";
  }

  const landedCount = typeof normalized.landed_op_count === "number" && normalized.landed_op_count > 0
    ? normalized.landed_op_count
    : 0;

  return Object.freeze({
    kind: "in_progress",
    summary,
    landed_ops: landedCount,
    statement_count: statements.length || asInteger(normalized.statement_count) || 0,
  });
}

/**
 * Derive a phase_progress snapshot compatible with executor progress shape.
 * Uses the Decide → Research → Execute → Review framework.
 */
function derivePhaseProgress(normalized, status, statements, latestSub) {
  const isTerminal = status === "done" || status === "clarify" || status === "budget_exhausted" || status === "error";

  if (isTerminal) {
    return Object.freeze({
      decide: status === "error" ? "done" : "done",
      research: "done",
      execute: "done",
      review: "done",
    });
  }

  // in_progress — derive from statements and counts
  const landedCount = typeof normalized.landed_op_count === "number" && normalized.landed_op_count > 0
    ? normalized.landed_op_count
    : 0;
  const stmtCount = statements.length || asInteger(normalized.statement_count) || 0;
  const turnNum = asInteger(normalized.turn_number) || 0;

  if (landedCount > 0) {
    return Object.freeze({
      decide: "done",
      research: "done",
      execute: "active",
      review: "pending",
    });
  }

  if (stmtCount > 0 || turnNum > 0) {
    return Object.freeze({
      decide: "done",
      research: "active",
      execute: "pending",
      review: "pending",
    });
  }

  return Object.freeze({
    decide: "active",
    research: "pending",
    execute: "pending",
    review: "pending",
  });
}

/**
 * Build bounded safe details for expanded view.
 * Excludes raw diffs, provider metadata, full reports, file paths.
 */
function buildSafeDetails(normalized, status, statements, latestSub, counts, diagnostics) {
  const detailEntries = [];

  // Turn identity
  const turnId = asString(normalized.turn_id);
  const turnNumber = asInteger(normalized.turn_number);
  if (turnId || typeof turnNumber === "number") {
    const ident = {};
    if (turnId) ident.turn_id = turnId;
    if (typeof turnNumber === "number") ident.turn_number = turnNumber;
    detailEntries.push({ kind: "identity", ...ident });
  }

  // User-facing message
  const message = asString(normalized.message);
  if (message) {
    detailEntries.push({ kind: "message", text: message.slice(0, 500) });
  }

  // Done summary
  const doneSummary = asString(normalized.done_summary);
  if (doneSummary) {
    detailEntries.push({ kind: "done_summary", text: doneSummary.slice(0, 500) });
  }

  // Clarification
  if (normalized.clarification_required === true) {
    detailEntries.push({
      kind: "clarification",
      required: true,
      message: asString(normalized.clarification_message) || null,
    });
  }

  // Per-statement details (bounded, safe fields only)
  if (statements.length > 0) {
    const stmtDetails = [];
    const cap = Math.min(statements.length, 5);
    for (let i = 0; i < cap; i += 1) {
      const stmt = statements[i];
      if (!stmt || typeof stmt !== "object") continue;
      const safe = compactObject({
        index: asInteger(stmt.statement_index) ?? i,
        op_kind: asString(stmt.op_kind),
        ok: asBoolean(stmt.ok),
        landed: asBoolean(stmt.landed),
        message: asString(stmt.message),
        teaching_hint: asString(stmt.teaching_hint),
        source: asString(stmt.source),
        target: asString(stmt.target),
      });
      if (Object.keys(safe).length > 0) {
        stmtDetails.push(safe);
      }
    }
    if (stmtDetails.length > 0) {
      detailEntries.push({
        kind: "statements",
        shown: stmtDetails.length,
        total: statements.length,
        items: stmtDetails,
      });
    }
  }

  // Counts summary
  if (counts.total > 0 || typeof normalized.landed_op_count === "number" || typeof normalized.statement_count === "number") {
    detailEntries.push({
      kind: "counts",
      ...counts,
      landed_ops: asInteger(normalized.landed_op_count),
      statement_count: asInteger(normalized.statement_count),
    });
  }

  // Budget
  const budget = normalized.budget;
  if (budget && typeof budget === "object") {
    detailEntries.push({
      kind: "budget",
      remaining_batches: asInteger(budget.remaining_batches),
      consecutive_errors: asInteger(budget.consecutive_errors),
    });
  }

  // Exit mode
  const exitMode = asString(normalized.exit_mode);
  if (exitMode) {
    detailEntries.push({ kind: "exit_mode", mode: exitMode });
  }

  // Timing
  const timing = normalized.timing;
  if (timing && typeof timing === "object") {
    detailEntries.push({
      kind: "timing",
      model_elapsed_ms: asFiniteNumber(timing.model_elapsed_ms),
      engine_elapsed_ms: asFiniteNumber(timing.engine_elapsed_ms),
      turn_elapsed_ms: asFiniteNumber(timing.turn_elapsed_ms),
    });
  }

  return detailEntries;
}

// ── Activity formatting helpers ────────────────────────────────────────────

/**
 * Format a single statement into a concise human-readable action label.
 * Covers query/search, lint, edits, dropped, failed, and generic cases.
 * Returns a short, safe string — never raw diffs, provider metadata,
 * full reports, or file paths.
 *
 * @param {object|null} stmt - normalized statement entry
 * @returns {string} action label, never null
 */
export function formatStatementAction(stmt) {
  if (!stmt || typeof stmt !== "object") {
    return "Unknown";
  }

  const opKind = typeof stmt.op_kind === "string" ? stmt.op_kind : "action";
  const landed = stmt.landed;
  const ok = stmt.ok;
  const message = typeof stmt.message === "string" ? stmt.message : null;
  const teachingHint = typeof stmt.teaching_hint === "string" ? stmt.teaching_hint : null;

  // ── Query / search ──────────────────────────────────────────────────
  if (opKind === "query" || opKind === "search") {
    // Check for "no matches" via detail.query_output
    if (stmt.detail && typeof stmt.detail === "object") {
      const queryOutput = typeof stmt.detail.query_output === "string"
        ? stmt.detail.query_output.trim()
        : "";
      if (!queryOutput) {
        return "No matches";
      }
    }
    if (landed === true) {
      return "Found results";
    }
    if (teachingHint) {
      const short = teachingHint.length > 60
        ? teachingHint.slice(0, 57) + "..."
        : teachingHint;
      return "Search: " + short;
    }
    if (message) {
      const short = message.length > 60
        ? message.slice(0, 57) + "..."
        : message;
      return "Search: " + short;
    }
    return "Searching...";
  }

  // ── Lint / validate ─────────────────────────────────────────────────
  if (opKind === "lint" || opKind === "validate" || opKind === "check") {
    if (ok === false) {
      return "Lint: issues found";
    }
    if (landed === false) {
      return "Lint: dropped";
    }
    return "Lint: passed";
  }

  // ── Status-driven: dropped / failed take priority over action kind ──
  if (landed === false) {
    return "Dropped";
  }
  if (ok === false) {
    return "Failed";
  }

  // ── Humanize the op_kind into a verb phrase ─────────────────────────
  const actionLabel = _humanizeOpKind(opKind);

  // ── Attach a short target/source when available (bounded) ───────────
  const target = _safeShortTarget(stmt);
  if (target) {
    return actionLabel + " " + target;
  }

  if (teachingHint) {
    const short = teachingHint.length > 50
      ? teachingHint.slice(0, 47) + "..."
      : teachingHint;
    return actionLabel + ": " + short;
  }

  return actionLabel;
}

/**
 * Format outcome counts from canonical activity state or raw entry.
 * Covers noop/answer-only, in_progress, done, clarify, error, budget_exhausted.
 *
 * @param {object|null} canonical - canonical activity state (from deriveAgentActivityState)
 * @param {object|null} entry - raw batch turn entry (fallback)
 * @returns {string} formatted counts string
 */
export function formatOutcomeCounts(canonical, entry) {
  const parts = [];

  // Use canonical counts when available
  if (canonical && typeof canonical === "object") {
    const outcome = canonical.outcome;
    if (outcome && typeof outcome === "object") {
      const kind = typeof outcome.kind === "string" ? outcome.kind : null;

      // noop / answer-only
      if (kind === "answered") {
        if (outcome.graph_changes === false) {
          return "Answer only — no graph changes";
        }
        return "Answered";
      }

      // clarify
      if (kind === "clarify") {
        return "Clarification needed";
      }

      // error
      if (kind === "error") {
        const diags = Array.isArray(canonical.diagnostics)
          ? canonical.diagnostics
          : (Array.isArray(outcome.diagnostics) ? outcome.diagnostics : []);
        if (diags.length) {
          return "Error: " + diags.length + " diagnostic" + (diags.length !== 1 ? "s" : "");
        }
        return "Error";
      }

      // budget_exhausted
      if (kind === "budget_exhausted") {
        const budget = outcome.budget;
        if (budget && typeof budget.remaining_batches === "number") {
          return "Budget exhausted (" + budget.remaining_batches + " turns left)";
        }
        return "Budget exhausted";
      }

      // done (multi-turn edit completed)
      if (kind === "done") {
        if (typeof outcome.landed_ops === "number" && outcome.landed_ops > 0) {
          parts.push(outcome.landed_ops + " change" + (outcome.landed_ops !== 1 ? "s" : "") + " applied");
        }
        if (typeof outcome.statement_count === "number" && outcome.statement_count > 0) {
          parts.push(outcome.statement_count + " statement" + (outcome.statement_count !== 1 ? "s" : ""));
        }
        if (parts.length) return parts.join(" \u00b7 ");
        return "Completed";
      }
    }

    // Fallback: use canonical.counts
    const counts = canonical.counts;
    if (counts && typeof counts === "object") {
      if (counts.total > 0) {
        parts.push(counts.total + " statement" + (counts.total !== 1 ? "s" : ""));
      }
      if (counts.landed > 0) {
        parts.push(counts.landed + " applied");
      }
      if (counts.not_ok > 0) {
        parts.push(counts.not_ok + " failed");
      }
      if (counts.not_landed > 0) {
        parts.push(counts.not_landed + " dropped");
      }
    }
  }

  // Fallback to raw entry
  if (!parts.length && entry && typeof entry === "object") {
    const stmtCount = typeof entry.statement_count === "number" ? entry.statement_count : 0;
    const landedCount = typeof entry.landed_op_count === "number" ? entry.landed_op_count : 0;
    if (stmtCount > 0) parts.push(stmtCount + " statement" + (stmtCount !== 1 ? "s" : ""));
    if (landedCount > 0) parts.push(landedCount + " applied");
  }

  return parts.length ? parts.join(" \u00b7 ") : "In progress...";
}

/**
 * Format an activity headline for display in the activity row.
 * Prefers canonical headline, then outcome summary, then safe summary text.
 * Bounded to 100 chars to keep live rows compact.
 * Never includes raw diffs, provider metadata, full reports, or file paths.
 *
 * @param {object|null} canonical - canonical activity state
 * @param {object|null} entry - raw batch turn entry (fallback)
 * @returns {string} headline string
 */
export function formatActivityHeadline(canonical, entry) {
  const maxLen = 100;

  // 1. Canonical headline (best choice — already derived from latest substantive)
  if (canonical && typeof canonical === "object") {
    if (typeof canonical.headline === "string" && canonical.headline) {
      return _safeBounded(canonical.headline, maxLen);
    }
    // 2. Outcome summary
    if (canonical.outcome && typeof canonical.outcome === "object") {
      const summary = canonical.outcome.summary;
      if (typeof summary === "string" && summary) {
        return _safeBounded(summary, maxLen);
      }
    }
  }

  // 3. Raw entry fallback
  if (entry && typeof entry === "object") {
    // Prefer done_summary for terminal turns, message for in-progress
    const msg = typeof entry.done_summary === "string" && entry.done_summary
      ? entry.done_summary
      : (typeof entry.message === "string" && entry.message
        ? entry.message
        : null);
    if (msg) {
      return _safeBounded(msg, maxLen);
    }
    // Clarification message
    if (typeof entry.clarification_message === "string" && entry.clarification_message) {
      return _safeBounded(entry.clarification_message, maxLen);
    }
  }

  return "Working...";
}

// ── Internal formatting helpers ─────────────────────────────────────────────

/**
 * Map op_kind values to human-readable verb phrases.
 */
function _humanizeOpKind(opKind) {
  const LABELS = {
    add_node: "Added node",
    remove_node: "Removed node",
    connect: "Connected",
    disconnect: "Disconnected",
    set_value: "Set value",
    set_field: "Set field",
    update_field: "Updated field",
    apply_op: "Applied",
    query: "Queried",
    search: "Searched",
    lint: "Linted",
    validate: "Validated",
    check: "Checked",
    create: "Created",
    delete: "Deleted",
    move: "Moved",
    rename: "Renamed",
    configure: "Configured",
    edit: "Edited",
  };
  return LABELS[opKind] || opKind.replace(/_/g, " ");
}

/**
 * Extract a short, safe target identifier from a statement.
 * Returns at most a field_path or target node id — never full file paths.
 */
function _safeShortTarget(stmt) {
  const fieldPath = typeof stmt.field_path === "string" ? stmt.field_path : null;
  if (fieldPath && fieldPath.length <= 60) {
    return '"' + fieldPath + '"';
  }
  const target = typeof stmt.target === "string" ? stmt.target : null;
  if (target && target.length <= 40) {
    return target;
  }
  const targetNodeId = typeof stmt.target_node_id === "string" ? stmt.target_node_id : null;
  if (targetNodeId && targetNodeId.length <= 40) {
    return targetNodeId;
  }
  return null;
}

/**
 * Bound a string to maxLen, adding ellipsis if truncated.
 * Collapses whitespace first.
 */
function _safeBounded(text, maxLen) {
  if (typeof text !== "string" || !text) return "Working...";
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return "Working...";
  if (cleaned.length <= maxLen) return cleaned;
  return cleaned.slice(0, maxLen - 1) + "\u2026";
}


// ── Exports ─────────────────────────────────────────────────────────────────

// Derivation helpers (internal, exposed for testing)
export {
  isSubstantiveStatement,
  latestSubstantiveStatement,
  deriveStatementCounts,
};

export {
  isObject,
  asString,
  asBoolean,
  asFiniteNumber,
  asInteger,
  asStringArray,
  compactObject,
  normalizeStatement,
  normalizeStatements,
  normalizeDiagnostic,
  normalizeDiagnostics,
  normalizeTiming,
  normalizeBudget,
};

// ── Activity feed reducer ───────────────────────────────────────────────────

/**
 * Source priority for reconciliation. Higher priority sources can overwrite
 * lower-priority ones for the same session/turn.
 */
export const FEED_SOURCE_PRIORITY = Object.freeze({
  websocket: 0,
  http: 1,
});

/**
 * Reduce an activity feed (array of canonical activity states) with an
 * incoming update. Implements merge-semantics for active/latest turn state:
 *
 * - Rejects clearly stale updates (older turn_number than existing feed entries
 *   for the same session, or turn_number gap > 1 without the intervening turn
 *   being present).
 * - Rejects updates whose session_id does not match the feed's established
 *   session (unless the feed is empty — first bind).
 * - Prevents terminal→active regressions: if a feed entry for the same turn_id
 *   is terminal (done/clarify/error/budget_exhausted) and the incoming update
 *   is in_progress, the terminal entry is preserved and the update is rejected
 *   (unless the update source is 'http', which carries authoritative final
 *   state).
 * - Allows final HTTP batch-turn reconciliation to authoritatively replace
 *   websocket partial rows for the same session/turn without duplication.
 *   HTTP updates always replace matching entries and set the turn status to
 *   the authoritative value.
 *
 * @param {Array<object>|null} previous - frozen array of canonical activity states
 * @param {object|null} update - single canonical activity state (from deriveAgentActivityState)
 * @param {object} [options]
 * @param {'websocket'|'http'} [options.source='websocket'] - update source
 * @returns {Array<object>} new frozen array (or previous if update rejected)
 */
export function reduceAgentActivityFeed(previous, update, options = {}) {
  const source = options.source || "websocket";
  const sourcePriority = FEED_SOURCE_PRIORITY[source] ?? 0;

  // Null/undefined guard: return previous unchanged
  if (!isObject(update)) {
    return Array.isArray(previous) ? previous : [];
  }

  const prevFeed = Array.isArray(previous) ? previous : [];
  const updateTurnId = asString(update.turn_id);
  const updateSessionId = asString(update.session_id);
  const updateTurnNumber = asInteger(update.turn_number);
  const updateStatus = asString(update.status) || "unknown";

  // If update has no identity fields, reject
  if (!updateSessionId || !updateTurnId) {
    return prevFeed;
  }

  // ── Session binding ──────────────────────────────────────────────────
  // If feed is non-empty, reject updates from a different session.
  if (prevFeed.length > 0) {
    const feedSessionId = asString(prevFeed[0].session_id);
    const hasOtherSession = prevFeed.some(
      (entry) => isObject(entry) && asString(entry.session_id) !== feedSessionId
    );
    // If feed has mixed sessions, we can't establish a single binding;
    // accept the update if it matches ANY session in the feed.
    if (hasOtherSession) {
      const matchesAny = prevFeed.some(
        (entry) => isObject(entry) && asString(entry.session_id) === updateSessionId
      );
      if (!matchesAny) {
        return prevFeed;
      }
    } else if (feedSessionId && feedSessionId !== updateSessionId) {
      // Feed has a single established session; reject foreign updates
      return prevFeed;
    }
  }

  // ── Staleness check ──────────────────────────────────────────────────
  // If the feed contains entries with higher turn_numbers for the same session,
  // this update is stale (late-arriving websocket message for an old turn).
  const maxTurnNumber = prevFeed.reduce((max, entry) => {
    if (!isObject(entry)) return max;
    const entrySessionId = asString(entry.session_id);
    const entryTurnNumber = asInteger(entry.turn_number);
    if (entrySessionId === updateSessionId && typeof entryTurnNumber === "number" && entryTurnNumber > max) {
      return entryTurnNumber;
    }
    return max;
  }, -1);

  // ── Find existing entry for the same turn ────────────────────────────
  const existingIndex = prevFeed.findIndex((entry) => {
    if (!isObject(entry)) return false;
    return asString(entry.turn_id) === updateTurnId
      && asString(entry.session_id) === updateSessionId;
  });

  // ── Terminal→active regression prevention ────────────────────────────
  if (existingIndex >= 0) {
    const existing = prevFeed[existingIndex];
    const existingStatus = asString(existing.status) || "unknown";

    if (BATCH_TERMINAL_STATUSES.has(existingStatus) && updateStatus === "in_progress") {
      // Terminal states cannot regress to active.
      // HTTP source is authoritative and can override even terminal states.
      if (source !== "http") {
        return prevFeed;
      }
    }

    // ── HTTP authoritative replacement ──────────────────────────────────
    if (source === "http") {
      // HTTP data authoritatively replaces matching websocket partial state
      const nextFeed = prevFeed.slice();
      nextFeed[existingIndex] = update;
      return Object.freeze(nextFeed);
    }

    // ── Websocket partial update: replace existing entry ────────────────
    // Websocket updates carry newer partial data; replace the existing entry
    // (terminal→active check already passed above).
    const nextFeed = prevFeed.slice();
    nextFeed[existingIndex] = update;
    return Object.freeze(nextFeed);
  }

  // ── Staleness check for new turns ───────────────────────────────────
  // Only reject new turns (not already in feed) that have a lower turn_number
  // than the current max — these are late-arriving events for stale turns.
  if (typeof updateTurnNumber === "number" && maxTurnNumber >= 0 && updateTurnNumber < maxTurnNumber) {
    // Update is for an older turn than what we already have — reject as stale
    return prevFeed;
  }

  // ── New turn: append ─────────────────────────────────────────────────
  const nextFeed = prevFeed.slice();
  nextFeed.push(update);
  return Object.freeze(nextFeed);
}
