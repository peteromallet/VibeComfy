// executor_progress.js — Browser-safe ESM normalizer for vibecomfy.executor.phase events
//
// Exports pure helpers that validate and normalize websocket payloads emitted
// for executor phase transitions, plus the executor progress snapshot shape
// used in panel state.  No Node, filesystem, or test-only dependencies.

// ── Internal helpers ────────────────────────────────────────────────────────

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asString(value) {
  return typeof value === "string" ? value : null;
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

// ── Phase taxonomy ──────────────────────────────────────────────────────────

export const EXECUTOR_PHASES = Object.freeze([
  "classify",
  "research",
  "implement",
  "reply",
]);

export const EXECUTOR_PHASE_STATUSES = Object.freeze([
  "start",
  "progress",
  "skipped",
  "done",
  "error",
]);

// ── Progress snapshot fields ────────────────────────────────────────────────

export const EXECUTOR_PROGRESS_STAGES = Object.freeze([
  "decide",
  "research",
  "execute",
  "review",
]);

export const EXECUTOR_PROGRESS_VALUES = Object.freeze([
  "pending",
  "active",
  "done",
]);

export const EXECUTOR_INTENTS = Object.freeze([
  "edit",
  "research",
  "explain_graph",
  "respond",
]);

const EXECUTOR_ROUTES = Object.freeze([
  "direct_edit",
  "inspect",
  "inspect_only",
  "revise",
  "adapt",
  "asset_lookup",
  "diagnose_repair",
  "subgraph_preview",
  "precedent_research",
  "clarify",
]);

const EXECUTOR_TASKS = Object.freeze([
  "edit_graph",
  "inspect_graph",
  "revise_graph",
  "adapt_graph",
  "find_assets",
  "diagnose",
  "preview_subgraph",
  "research_precedent",
  "respond",
  "research_nodes",
]);

/**
 * All four progress stages must be present with one of the canonical values
 * for the snapshot to be considered valid.
 */
const REQUIRED_PROGRESS_STAGES = new Set(EXECUTOR_PROGRESS_STAGES);
const VALID_PROGRESS_VALUES = new Set(EXECUTOR_PROGRESS_VALUES);
const VALID_EXECUTOR_ROUTES = new Set(EXECUTOR_ROUTES);
const VALID_EXECUTOR_TASKS = new Set(EXECUTOR_TASKS);

function normalizeAllowedString(value, allowedValues) {
  const normalized = typeof value === "string" ? value.trim().toLowerCase() : "";
  return normalized && allowedValues.has(normalized) ? normalized : null;
}

function executorRouteLabel(route) {
  if (route === "direct_edit") return "Direct edit";
  if (route === "inspect") return "Inspect graph";
  if (route === "inspect_only") return "Inspect graph";
  if (route === "revise") return "Revise graph";
  if (route === "adapt") return "Adapt graph";
  if (route === "asset_lookup") return "Look up assets";
  if (route === "diagnose_repair") return "Diagnose and repair";
  if (route === "subgraph_preview") return "Preview subgraph";
  if (route === "precedent_research") return "Research precedents";
  if (route === "clarify") return "Ask for clarification";
  return null;
}

// ── Normalizers ─────────────────────────────────────────────────────────────

/**
 * Normalize a raw vibecomfy.executor.phase websocket event payload.
 *
 * Accepts both the direct payload and the event detail wrapper.
 * Returns a frozen normalized object, or null if the payload is invalid.
 *
 * @param {*} raw - raw websocket event or event.detail
 * @returns {object|null} frozen normalized payload, or null
 */
export function normalizeExecutorPhasePayload(raw) {
  // Accept event.detail style or direct payload
  const payload = isObject(raw?.detail) ? raw.detail : raw;
  if (!isObject(payload)) {
    return null;
  }

  const phase = asString(payload.phase);
  if (!phase || !EXECUTOR_PHASES.includes(phase.toLowerCase())) {
    return null;
  }
  const intent = asString(payload.intent);
  const route = normalizeAllowedString(payload.route, VALID_EXECUTOR_ROUTES);
  const task = normalizeAllowedString(payload.task, VALID_EXECUTOR_TASKS);

  const normalized = compactObject({
    // Phase (required)
    phase: phase.toLowerCase(),

    // Status (default to "start" per the existing handler)
    status: (asString(payload.status) || "start").toLowerCase(),

    // Session identity (optional — may not be present on first event)
    session_id: asString(payload.session_id),

    // Executor identity
    executor_id: asString(payload.executor_id),

    // Timing
    emitted_at: asString(payload.emitted_at),

    // Classify decision metadata (optional; emitted once the decision exists)
    plan_summary: asString(payload.plan_summary),
    intent: intent && EXECUTOR_INTENTS.includes(intent) ? intent : null,
    route,
    task,
  });

  return Object.freeze(normalized);
}

export function executorDecisionLabel(normalized) {
  if (!isObject(normalized) || normalized.phase !== "classify") {
    return null;
  }
  const summary = typeof normalized.plan_summary === "string"
    ? normalized.plan_summary.trim()
    : "";
  if (summary) {
    return `Deciding: ${summary}`;
  }
  const route = typeof normalized.route === "string"
    ? normalized.route
    : "";
  const routeLabel = executorRouteLabel(route);
  if (routeLabel) {
    return `Deciding: ${routeLabel}`;
  }
  const intent = typeof normalized.intent === "string"
    ? normalized.intent
    : "";
  if (intent === "edit") {
    return "Deciding: Edit the graph.";
  }
  if (intent === "research") {
    return "Deciding: Research relevant context before replying.";
  }
  if (intent === "explain_graph") {
    return "Deciding: Inspect the attached graph and explain it.";
  }
  if (intent === "respond") {
    return "Deciding: Reply to the request.";
  }
  return null;
}

/**
 * Extract a payload from a websocket event argument.
 *
 * @param {*} event - websocket event or plain payload
 * @returns {object|null} the raw payload object, or null
 */
export function extractExecutorPhasePayload(event) {
  if (isObject(event?.detail)) {
    return event.detail;
  }
  return isObject(event) ? event : null;
}

/**
 * Normalize an executor progress snapshot (the shape stored in panel.state.executorProgress).
 *
 * Returns a frozen object with all four stages set to canonical values,
 * or null if the input is invalid.
 *
 * @param {*} raw - raw progress snapshot
 * @returns {object|null} frozen normalized progress, or null
 */
export function normalizeExecutorProgressSnapshot(raw) {
  if (!isObject(raw)) {
    return null;
  }

  const decide = asString(raw.decide);
  const research = asString(raw.research);
  const execute = asString(raw.execute);
  const review = asString(raw.review);

  if (
    !decide || !VALID_PROGRESS_VALUES.has(decide)
    || !research || !VALID_PROGRESS_VALUES.has(research)
    || !execute || !VALID_PROGRESS_VALUES.has(execute)
    || !review || !VALID_PROGRESS_VALUES.has(review)
  ) {
    return null;
  }

  return Object.freeze(compactObject({
    decide,
    research,
    execute,
    review,
    route: normalizeAllowedString(raw.route, VALID_EXECUTOR_ROUTES),
    task: normalizeAllowedString(raw.task, VALID_EXECUTOR_TASKS),
  }));
}

/**
 * Create an executor progress snapshot with explicit stage values.
 * Missing stages default to "pending".
 *
 * @param {object} [overrides] - partial stage values
 * @returns {object} frozen progress snapshot
 */
export function createExecutorProgressSnapshot(overrides = {}) {
  const snapshot = compactObject({
    decide: EXECUTOR_PROGRESS_VALUES.includes(overrides.decide) ? overrides.decide : "pending",
    research: EXECUTOR_PROGRESS_VALUES.includes(overrides.research) ? overrides.research : "pending",
    execute: EXECUTOR_PROGRESS_VALUES.includes(overrides.execute) ? overrides.execute : "pending",
    review: EXECUTOR_PROGRESS_VALUES.includes(overrides.review) ? overrides.review : "pending",
    route: normalizeAllowedString(overrides.route, VALID_EXECUTOR_ROUTES),
    task: normalizeAllowedString(overrides.task, VALID_EXECUTOR_TASKS),
  });
  return Object.freeze(snapshot);
}

/**
 * Derive a progress snapshot from a normalized executor phase payload.
 * Returns a frozen progress snapshot, or null if the phase is unrecognized.
 *
 * Mirrors the logic in progressFromExecutorPhaseEvent in vibecomfy_roundtrip.js.
 */
export function progressFromExecutorPhase(normalized) {
  if (!isObject(normalized)) {
    return null;
  }
  const phase = String(normalized.phase || "").toLowerCase();
  const status = String(normalized.status || "start").toLowerCase();
  const extras = {
    route: normalizeAllowedString(normalized.route, VALID_EXECUTOR_ROUTES),
    task: normalizeAllowedString(normalized.task, VALID_EXECUTOR_TASKS),
  };

  if (status === "done") {
    if (phase === "classify") {
      return createExecutorProgressSnapshot({
        decide: "done",
        research: "pending",
        execute: "pending",
        review: "pending",
        ...extras,
      });
    }
    if (phase === "research") {
      return createExecutorProgressSnapshot({
        decide: "done",
        research: "done",
        execute: "pending",
        review: "pending",
        ...extras,
      });
    }
    if (phase === "implement") {
      return createExecutorProgressSnapshot({
        decide: "done",
        research: "done",
        execute: "done",
        review: "pending",
        ...extras,
      });
    }
    if (phase === "reply") {
      return createExecutorProgressSnapshot({
        decide: "done",
        research: "done",
        execute: "done",
        review: "done",
        ...extras,
      });
    }
  }

  // Skipped phases
  if (status === "skipped") {
    if (phase === "research") {
      return createExecutorProgressSnapshot({
        decide: "done",
        research: "pending",
        execute: "pending",
        review: "pending",
        ...extras,
      });
    }
    if (phase === "implement") {
      return createExecutorProgressSnapshot({
        decide: "done",
        research: "done",
        execute: "pending",
        review: "pending",
        ...extras,
      });
    }
    // classify skipped means the executor skipped classification entirely
    if (phase === "classify") {
      return createExecutorProgressSnapshot({
        decide: "pending",
        research: "pending",
        execute: "pending",
        review: "pending",
        ...extras,
      });
    }
  }

  // Active phases
  if (phase === "classify") {
    return createExecutorProgressSnapshot({
      decide: "active",
      research: "pending",
      execute: "pending",
      review: "pending",
      ...extras,
    });
  }
  if (phase === "research") {
    return createExecutorProgressSnapshot({
      decide: "done",
      research: "active",
      execute: "pending",
      review: "pending",
      ...extras,
    });
  }
  if (phase === "implement") {
    return createExecutorProgressSnapshot({
      decide: "done",
      research: "done",
      execute: "active",
      review: "pending",
      ...extras,
    });
  }
  if (phase === "reply") {
    return createExecutorProgressSnapshot({
      decide: "done",
      research: "done",
      execute: "done",
      review: "active",
      ...extras,
    });
  }

  return null;
}

/**
 * Convert a normalized executor phase payload into a canonical phase_progress
 * snapshot compatible with deriveAgentActivityState.phase_progress.
 *
 * This is the compatibility bridge between legacy executor phase events
 * (vibecomfy.executor.phase) and the canonical agent-activity model. When
 * agent-turn activity is active, executor phase events flow through this
 * function to update panel.state.executorProgress without creating an
 * independent rendering branch.
 *
 * @param {object|null} normalized - normalized executor phase payload
 * @returns {object|null} frozen { decide, research, execute, review } or null
 */
export function executorPhaseToCanonicalProgress(normalized) {
  return progressFromExecutorPhase(normalized);
}

/**
 * Check whether all four progress stages are "done".
 */
export function isExecutorProgressComplete(snapshot) {
  const norm = normalizeExecutorProgressSnapshot(snapshot);
  if (!norm) {
    return false;
  }
  return norm.decide === "done"
    && norm.research === "done"
    && norm.execute === "done"
    && norm.review === "done";
}

/**
 * Derive a human-readable label for an executor progress snapshot.
 */
export function executorProgressLabel(snapshot) {
  const norm = normalizeExecutorProgressSnapshot(snapshot);
  if (!norm) {
    return "Unknown";
  }
  if (norm.decide === "active") {
    return executorRouteLabel(norm.route) || "Decide";
  }
  if (norm.research === "active") return "Research";
  if (norm.execute === "active") return "Execute";
  if (norm.review === "active") return "Review";
  if (isExecutorProgressComplete(norm)) return "Complete";
  return "Pending";
}

export {
  isObject,
  asString,
  compactObject,
};
