const PUBLIC_OUTCOME_KINDS = Object.freeze([
  "candidate",
  "noop",
  "clarify",
  "error",
]);

const CANONICAL_EXECUTOR_ROUTES = Object.freeze([
  "clarify",
  "inspect",
  "respond",
  "research",
  "revise",
  "adapt",
]);

const INTERNAL_OUTCOME_KIND_MAP = Object.freeze({
  edit: "candidate",
  "edit+clarify": "candidate",
});

const FAILURE_HINT_KEYS = Object.freeze([
  "agent_failure_context",
  "failureKind",
  "failure_kind",
  "nextAction",
  "next_action",
  "retryable",
]);

const NORMALIZED_RESPONSE_MARKER = "__agentEditResponseNormalized";

/** Routes that are allowed to carry Apply / candidate / review / rebaseline
 * affordances in the browser UI.  All other routes render as normal
 * assistant messages with no editing controls. */
const APPLYABLE_ROUTES = Object.freeze(new Set(["revise", "adapt"]));

/**
 * Return true when `route` permits Apply / candidate / review / rebaseline
 * affordances in the browser UI.  Non-applyable routes (clarify, respond,
 * inspect, research) render as normal assistant messages.
 */
export function routeAllowsApplyAffordances(route) {
  if (typeof route !== "string") return false;
  return APPLYABLE_ROUTES.has(route.trim().toLowerCase());
}

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asString(value) {
  return typeof value === "string" ? value : null;
}

function asTrimmedString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function asBooleanOrNull(value) {
  return typeof value === "boolean" ? value : null;
}

function clonePlainData(value) {
  if (Array.isArray(value)) {
    return value.map(clonePlainData);
  }
  if (isObject(value)) {
    const clone = {};
    for (const [key, entry] of Object.entries(value)) {
      clone[key] = clonePlainData(entry);
    }
    return clone;
  }
  return value;
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

function asStringOrNumber(value) {
  if (typeof value === "string" && value) {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function hasFailureHints(response) {
  return FAILURE_HINT_KEYS.some((key) => Object.prototype.hasOwnProperty.call(response, key));
}

function responseHasCandidatePayload(response) {
  if (!isObject(response)) {
    return false;
  }
  return isObject(response.candidate)
    || isObject(response.candidate_graph)
    || isObject(response.graph);
}

function hasCanonicalExecutorEnvelope(response) {
  return isObject(response)
    && CANONICAL_EXECUTOR_ROUTES.includes(response.route)
    && (
      Object.prototype.hasOwnProperty.call(response, "reply")
      || Object.prototype.hasOwnProperty.call(response, "evidence")
      || Object.prototype.hasOwnProperty.call(response, "apply_eligible")
      || Object.prototype.hasOwnProperty.call(response, "no_candidate_reason")
    );
}

function resultHasNoCandidateEligibility(response) {
  const legacyEligibility = isObject(response.apply_eligibility) ? response.apply_eligibility : null;
  const normalizedEligibility = isObject(response.eligibility) ? response.eligibility : null;
  return response.candidate === null
    || response.candidate_graph === null
    || response.apply_eligible === false
    || typeof response.no_candidate_reason === "string"
    || legacyEligibility?.reason === "no_candidate"
    || normalizedEligibility?.reason === "no_candidate";
}

function resultLooksLikeNoopResponse(response) {
  if (!isObject(response)) {
    return false;
  }
  if (response.outcome?.kind === "noop") {
    return true;
  }
  return response.graph_unchanged === true
    && response.apply_allowed === false
    && response.canvas_apply_allowed === false
    && response.queue_allowed === false;
}

function clarificationPayload(question) {
  const text = asTrimmedString(question);
  if (!text) {
    return {};
  }
  return {
    question: text,
    clarification: { message: text },
  };
}

function normalizeRebaselineRecovery(recovery) {
  if (!isObject(recovery)) {
    return null;
  }
  return compactObject({
    action: asString(recovery.action),
    endpoint: asString(recovery.endpoint),
    reason: asString(recovery.reason),
    lastKnownBaselineGraphHash:
      asString(recovery.lastKnownBaselineGraphHash)
      || asString(recovery.last_known_baseline_graph_hash),
    submitGraphHash: asString(recovery.submitGraphHash) || asString(recovery.submit_graph_hash),
    submitStructuralGraphHash:
      asString(recovery.submitStructuralGraphHash)
      || asString(recovery.submit_structural_graph_hash),
    clientGraphHash: asString(recovery.clientGraphHash) || asString(recovery.client_graph_hash),
    clientStructuralGraphHash:
      asString(recovery.clientStructuralGraphHash)
      || asString(recovery.client_structural_graph_hash),
  });
}

function extractRebaselineRecovery(response) {
  if (!isObject(response)) {
    return null;
  }
  const directSources = [
    response.rebaselineRecovery,
    response.rebaseline_recovery,
    response.outcome?.rebaselineRecovery,
    response.outcome?.rebaseline_recovery,
  ];
  for (const source of directSources) {
    const recovery = normalizeRebaselineRecovery(source);
    if (recovery) {
      return recovery;
    }
  }

  const contexts = [
    response.agent_failure_context,
    response.agentFailureContext,
    response.outcome?.agent_failure_context,
    response.outcome?.agentFailureContext,
    response.debug?.failure?.agent_failure_context,
    response.debug?.failure?.agentFailureContext,
  ];
  for (const context of contexts) {
    const issues = context?.issues;
    if (!Array.isArray(issues)) {
      continue;
    }
    for (const issue of issues) {
      const recovery = normalizeRebaselineRecovery(
        issue?.rebaselineRecovery || issue?.rebaseline_recovery,
      );
      if (recovery) {
        return recovery;
      }
    }
  }
  return null;
}

function publicErrorOutcomeFromResponse(response, { defaultStage = null } = {}) {
  const failureKind =
    asString(response.failureKind)
    || asString(response.failure_kind)
    || (asString(response.kind) && response.kind !== "error" ? response.kind : null);
  const payload = compactObject({
    kind: "error",
    failureKind,
    stage: asString(response.stage) || defaultStage,
    retryable: asBooleanOrNull(response.retryable),
    nextAction: asString(response.nextAction) || asString(response.next_action),
    graphUnchanged:
      asBooleanOrNull(response.graphUnchanged) ?? asBooleanOrNull(response.graph_unchanged),
  });
  const failureContext = response.agentFailureContext || response.agent_failure_context;
  if (isObject(failureContext)) {
    payload.agentFailureContext = clonePlainData(failureContext);
  }
  const recovery = extractRebaselineRecovery(response);
  if (recovery) {
    payload.rebaselineRecovery = recovery;
  }
  return payload;
}

function normalizePublicOutcome(rawOutcome, response, { allowLegacy, endpoint }) {
  const outcome = clonePlainData(rawOutcome);
  const kind = asString(outcome.kind);
  if (!kind) {
    throw new Error(
      `Agent edit response${endpoint ? ` for ${endpoint}` : ""} is missing outcome.kind.`,
    );
  }

  if (PUBLIC_OUTCOME_KINDS.includes(kind)) {
    if (kind === "error") {
      const errorOutcome = {
        ...outcome,
        kind: "error",
      };
      if (!errorOutcome.rebaselineRecovery) {
        const recovery = extractRebaselineRecovery(response);
        if (recovery) {
          errorOutcome.rebaselineRecovery = recovery;
        }
      } else {
        errorOutcome.rebaselineRecovery = normalizeRebaselineRecovery(errorOutcome.rebaselineRecovery);
      }
      if (isObject(errorOutcome.agent_failure_context) && !errorOutcome.agentFailureContext) {
        errorOutcome.agentFailureContext = clonePlainData(errorOutcome.agent_failure_context);
      }
      return errorOutcome;
    }
    if (kind === "clarify") {
      return {
        ...outcome,
        kind,
        ...clarificationPayload(outcome.question),
      };
    }
    return outcome;
  }

  if (kind === "failure") {
    return publicErrorOutcomeFromResponse(
      {
        ...response,
        ...outcome,
      },
      { defaultStage: asString(outcome.stage) },
    );
  }

  if (kind === "budget") {
    const publicKind = responseHasCandidatePayload(response) ? "candidate" : "noop";
    return compactObject({
      kind: publicKind,
      budgetExhausted: true,
      reason: asTrimmedString(outcome.reason),
      changes: publicKind === "candidate" && Array.isArray(outcome.changes)
        ? clonePlainData(outcome.changes)
        : undefined,
    });
  }

  if (INTERNAL_OUTCOME_KIND_MAP[kind] === "candidate") {
    return {
      kind: "candidate",
      changes: Array.isArray(outcome.changes) ? clonePlainData(outcome.changes) : [],
      ...clarificationPayload(outcome.question),
    };
  }

  if (!allowLegacy) {
    throw new Error(
      `Agent edit response${endpoint ? ` for ${endpoint}` : ""} has unsupported outcome.kind ${JSON.stringify(kind)}.`,
    );
  }

  return publicErrorOutcomeFromResponse(
    {
      ...response,
      kind,
      failureKind: kind,
    },
    { defaultStage: asString(response.stage) },
  );
}

function inferLegacyOutcome(response, { endpoint }) {
  if (!isObject(response)) {
    return null;
  }
  if (response.ok === false || hasFailureHints(response)) {
    return publicErrorOutcomeFromResponse(response, { defaultStage: asString(response.stage) });
  }
  if (hasCanonicalExecutorEnvelope(response)) {
    if (response.route === "clarify") {
      return {
        kind: "clarify",
        ...clarificationPayload(response.reply || response.message),
      };
    }
    // respond / research / inspect are answer-only routes — never candidate
    if (response.route === "respond" || response.route === "research" || response.route === "inspect") {
      return compactObject({
        kind: "noop",
        reason: asTrimmedString(response.reply)
          || asTrimmedString(response.message)
          || "Answer-only route",
      });
    }
    if (response.apply_eligible === true && responseHasCandidatePayload(response)) {
      return {
        kind: "candidate",
        changes: Array.isArray(response.changes) ? clonePlainData(response.changes) : [],
      };
    }
    return compactObject({
      kind: "noop",
      reason: asTrimmedString(response.no_candidate_reason)
        || asTrimmedString(response.reply)
        || asTrimmedString(response.message),
    });
  }
  const clarificationQuestion =
    asTrimmedString(response.clarificationMessage) || asTrimmedString(response.clarification_message);
  if (response.clarification_required === true || response.clarificationRequired === true || clarificationQuestion) {
    return {
      kind: "clarify",
      ...clarificationPayload(clarificationQuestion),
    };
  }
  if (
    response.graph_unchanged === true
    && (resultHasNoCandidateEligibility(response) || resultLooksLikeNoopResponse(response))
  ) {
    return compactObject({
      kind: "noop",
      reason: asTrimmedString(response.message),
    });
  }
  if (responseHasCandidatePayload(response)) {
    return {
      kind: "candidate",
      changes: Array.isArray(response.changes) ? clonePlainData(response.changes) : [],
    };
  }
  throw new Error(
    `Agent edit response${endpoint ? ` for ${endpoint}` : ""} is missing outcome and could not be inferred.`,
  );
}

function hasMissingDurableMetadata(response) {
  if (!isObject(response)) {
    return true;
  }
  const sessionId = asString(response.sessionId) || asString(response.session_id);
  const turnId = asString(response.turnId) || asString(response.turn_id);
  // SD2: both session_id and turn_id must be absent for malformed/non-applyable.
  // Having at least one provides partial durable identity.
  return !sessionId && !turnId;
}

function normalizeEligibility(response, candidateGraph) {
  if (!isObject(response)) {
    return null;
  }
  if (isObject(response.eligibility)) {
    return clonePlainData(response.eligibility);
  }
  if (isObject(response.apply_eligibility)) {
    return clonePlainData(response.apply_eligibility);
  }
  if (typeof response.apply_eligible === "boolean") {
    return {
      applyable: response.apply_eligible,
      reason: response.apply_eligible ? "applyable" : "no_candidate",
      message: response.apply_eligible
        ? "Ready to apply."
        : asTrimmedString(response.no_candidate_reason) || "No candidate is available to apply.",
      warnings: [],
    };
  }
  if (
    !isObject(response.candidate)
    && !isObject(response.eligibility)
    && !isObject(response.apply_eligibility)
    && isObject(candidateGraph)
    && (
      typeof response.apply_allowed === "boolean"
      || typeof response.canvas_apply_allowed === "boolean"
      || typeof response.queue_allowed === "boolean"
    )
  ) {
    const applyable = response.apply_allowed !== false && response.canvas_apply_allowed !== false;
    if (applyable) {
      const queueAllowed = response.queue_allowed !== false;
      return {
        applyable: true,
        reason: queueAllowed ? "applyable" : "queue_blocked_warning",
        message: queueAllowed
          ? "Ready to apply."
          : "Apply is allowed, but Queue remains blocked for this candidate.",
        warnings: queueAllowed ? [] : ["queue_blocked"],
      };
    }
    return {
      applyable: false,
      reason: "server_blocked",
      message: "Apply is blocked by the compatibility response.",
      warnings: ["server_blocked"],
    };
  }

  // SD2: A candidate graph present without durable turn metadata is
  // malformed/non-applyable, never stale/rebaseline. Suppress Apply and
  // guide the user towards retry or debug inspection.
  if (isObject(candidateGraph) && hasMissingDurableMetadata(response)) {
    return {
      applyable: false,
      reason: "missing_durable_turn_metadata",
      message:
        "Candidate is missing durable session/turn metadata and cannot be applied. "
        + "Retry the submit or inspect the raw response in the debug panel.",
      warnings: ["missing_durable_turn_metadata"],
    };
  }

  return null;
}

function normalizeCandidateGraph(response, outcome) {
  if (!isObject(response)) {
    return null;
  }
  if (outcome?.kind !== "candidate") {
    return null;
  }
  const typedGraph = response.candidate?.graph;
  if (isObject(typedGraph)) {
    return typedGraph;
  }
  if (isObject(response.candidateGraph)) {
    return response.candidateGraph;
  }
  if (isObject(response.candidate_graph)) {
    return response.candidate_graph;
  }
  if (
    response.graph_unchanged === true
    && (resultHasNoCandidateEligibility(response) || resultLooksLikeNoopResponse(response))
  ) {
    return null;
  }
  if (isObject(response.graph)) {
    return response.graph;
  }
  return null;
}

function normalizeCandidateEnvelope(response, candidateGraph) {
  if (!isObject(candidateGraph)) {
    return null;
  }
  if (isObject(response.candidate)) {
    const candidate = clonePlainData(response.candidate);
    if (!isObject(candidate.graph)) {
      candidate.graph = candidateGraph;
    }
    return candidate;
  }
  return {
    graph: candidateGraph,
  };
}

function normalizeTurnIdentityPayload(identity) {
  if (!isObject(identity)) {
    return null;
  }
  const sessionId = asString(identity.sessionId) || asString(identity.session_id);
  const turnId = asStringOrNumber(identity.turnId) || asStringOrNumber(identity.turn_id);
  const baselineTurnId =
    asStringOrNumber(identity.baselineTurnId) || asStringOrNumber(identity.baseline_turn_id);
  const idempotencyKey =
    asString(identity.idempotencyKey) || asString(identity.idempotency_key);
  const role = asString(identity.role);
  const entryType = asString(identity.entryType) || asString(identity.entry_type);
  if (!sessionId && !turnId && !baselineTurnId && !idempotencyKey && !role && !entryType) {
    return null;
  }
  return compactObject({
    sessionId,
    turnId,
    baselineTurnId,
    idempotencyKey,
    role,
    entryType,
  });
}

function turnIdentitySources(response) {
  return [
    response?.turnIdentity,
    response?.turn_identity,
    response?.candidate?.turnIdentity,
    response?.candidate?.turn_identity,
    response?.debug?.turnIdentity,
    response?.debug?.turn_identity,
    isObject(response)
      ? {
        session_id: response.session_id,
        sessionId: response.sessionId,
        turn_id: response.turn_id,
        turnId: response.turnId,
        baseline_turn_id: response.baseline_turn_id,
        baselineTurnId: response.baselineTurnId,
        idempotency_key: response.idempotency_key,
        idempotencyKey: response.idempotencyKey,
        role: response.role,
        entry_type: response.entry_type,
        entryType: response.entryType,
      }
      : null,
  ];
}

function normalizeStageSnapshotPayload(snapshot) {
  if (!isObject(snapshot)) {
    return null;
  }
  const stage = asString(snapshot.stage);
  if (!stage) {
    return null;
  }
  return compactObject({
    stage,
    ok: asBooleanOrNull(snapshot.ok),
    blocking: asBooleanOrNull(snapshot.blocking),
    durationMs: typeof snapshot.durationMs === "number"
      ? snapshot.durationMs
      : typeof snapshot.duration_ms === "number" ? snapshot.duration_ms : null,
    gates: isObject(snapshot.gates) ? clonePlainData(snapshot.gates) : null,
    artifacts: Array.isArray(snapshot.artifacts) ? clonePlainData(snapshot.artifacts) : null,
    issues: Array.isArray(snapshot.issues) ? clonePlainData(snapshot.issues) : null,
    value: Object.prototype.hasOwnProperty.call(snapshot, "value")
      ? clonePlainData(snapshot.value)
      : null,
  });
}

function normalizeFieldChangePayload(change) {
  if (!isObject(change)) {
    return null;
  }
  const uid = asStringOrNumber(change.uid);
  const fieldPath = asString(change.fieldPath) || asString(change.field_path);
  if (!uid || !fieldPath) {
    return null;
  }
  return compactObject({
    uid,
    fieldPath,
    old: Object.prototype.hasOwnProperty.call(change, "old") ? clonePlainData(change.old) : undefined,
    new: Object.prototype.hasOwnProperty.call(change, "new") ? clonePlainData(change.new) : undefined,
  });
}

function normalizeFieldChangeList(changes) {
  if (!Array.isArray(changes)) {
    return [];
  }
  const normalized = [];
  for (const change of changes) {
    const fieldChange = normalizeFieldChangePayload(change);
    if (fieldChange) {
      normalized.push(fieldChange);
    }
  }
  return normalized;
}

function readRawFieldChanges(raw) {
  const outcomeChanges = normalizeFieldChangeList(raw?.outcome?.changes);
  const directChanges = normalizeFieldChangeList(raw?.changes);
  const legacyChanges = normalizeFieldChangeList(raw?.field_changes);
  const batchTurnChanges = [];
  const batchTurns = raw?.change_details?.batch_turns || raw?.changeDetails?.batchTurns || raw?.batch_turns;
  if (Array.isArray(batchTurns)) {
    for (const turn of batchTurns) {
      if (!isObject(turn)) {
        continue;
      }
      const changes = normalizeFieldChangeList(turn.field_changes || turn.fieldChanges);
      batchTurnChanges.push({
        turnNumber: typeof turn.turn_number === "number"
          ? turn.turn_number
          : typeof turn.turnNumber === "number" ? turn.turnNumber : null,
        changes,
      });
    }
  }
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

function normalizePublicRoute(rawRoute, outcome) {
  if (CANONICAL_EXECUTOR_ROUTES.includes(rawRoute)) {
    return rawRoute;
  }
  if (outcome?.kind === "candidate") {
    return "revise";
  }
  if (outcome?.kind === "clarify") {
    return "clarify";
  }
  return null;
}

function normalizeMessage(message, options) {
  if (!isObject(message)) {
    return message;
  }
  const response = isObject(message.response)
    ? normalizeAgentEditResponse(message.response, {
      ...options,
      endpoint: options.endpoint ? `${options.endpoint}:message-response` : "message-response",
    })
    : null;
  const normalized = {
    raw: message,
    role: asString(message.role),
    text: asString(message.text),
    turnId: asString(message.turnId) || asString(message.turn_id),
    sessionId: asString(message.sessionId) || asString(message.session_id),
    entryType: asString(message.entryType) || asString(message.entry_type),
    timestamp: asString(message.timestamp),
    response,
    outcome: response?.outcome || (isObject(message.outcome)
      ? normalizePublicOutcome(message.outcome, message, options)
      : null),
  };
  return normalized;
}

export function normalizeAgentEditResponse(raw, { endpoint = null, allowLegacy = true } = {}) {
  if (raw?.[NORMALIZED_RESPONSE_MARKER] === true) {
    return raw;
  }
  if (!isObject(raw)) {
    throw new Error(
      `Agent edit response${endpoint ? ` for ${endpoint}` : ""} must be an object.`,
    );
  }

  const outcome = isObject(raw.outcome)
    ? normalizePublicOutcome(raw.outcome, raw, { allowLegacy, endpoint })
    : allowLegacy
      ? inferLegacyOutcome(raw, { endpoint })
      : (() => {
        throw new Error(
          `Agent edit response${endpoint ? ` for ${endpoint}` : ""} is missing outcome.`,
        );
      })();

  const candidateGraph = normalizeCandidateGraph(raw, outcome);
  const eligibility = normalizeEligibility(raw, candidateGraph);
  const rawRebaselineRecovery = extractRebaselineRecovery(raw);

  // SD2: Applyable means durable. A candidate missing both session_id and
  // turn_id is malformed/non-applyable, never stale/rebaseline. Prevent
  // rebaselineRecovery from being created so the UI never offers
  // "Rebaseline & retry" actions for these responses.
  // Eligibility override (disabling Apply) is handled by the lifecycle layer
  // when it detects a candidate response without durable identity.
  const rebaselineRecovery =
    isObject(candidateGraph) && hasMissingDurableMetadata(raw)
      ? null
      : rawRebaselineRecovery;

  const latestCandidate = isObject(raw.latestCandidate) || isObject(raw.latest_candidate)
    ? normalizeAgentEditResponse(raw.latestCandidate || raw.latest_candidate, {
      endpoint: endpoint ? `${endpoint}:latest_candidate` : "latest_candidate",
      allowLegacy,
    })
    : null;

  const normalized = {
    [NORMALIZED_RESPONSE_MARKER]: true,
    raw,
    endpoint,
    ok: asBooleanOrNull(raw.ok),
    exists: asBooleanOrNull(raw.exists),
    message: asString(raw.message) || asString(raw.reply),
    route: normalizePublicRoute(raw.route, outcome),
    reply: asString(raw.reply) || asString(raw.message),
    evidence: isObject(raw.evidence) || Array.isArray(raw.evidence) ? clonePlainData(raw.evidence) : null,
    outcome,
    candidateGraph,
    candidate: normalizeCandidateEnvelope(raw, candidateGraph),
    candidateGraphHash:
      asString(raw.candidateGraphHash) || asString(raw.candidate_graph_hash),
    eligibility,
    turnIdentity: null,
    stageSnapshots: Array.isArray(raw.stageSnapshots)
      ? raw.stageSnapshots.map(normalizeStageSnapshotPayload).filter(Boolean)
      : Array.isArray(raw.stage_snapshots)
        ? raw.stage_snapshots.map(normalizeStageSnapshotPayload).filter(Boolean)
        : Array.isArray(raw.debug?.stageSnapshots)
          ? raw.debug.stageSnapshots.map(normalizeStageSnapshotPayload).filter(Boolean)
          : Array.isArray(raw.debug?.stage_snapshots)
            ? raw.debug.stage_snapshots.map(normalizeStageSnapshotPayload).filter(Boolean)
            : null,
    fieldChanges: readRawFieldChanges(raw),
    applyEligible:
      asBooleanOrNull(raw.applyEligible)
      ?? asBooleanOrNull(raw.apply_eligible)
      ?? (eligibility ? eligibility.applyable === true : null),
    noCandidateReason:
      asString(raw.noCandidateReason) || asString(raw.no_candidate_reason),
    applyAllowed:
      asBooleanOrNull(raw.applyAllowed)
      ?? asBooleanOrNull(raw.apply_allowed)
      ?? asBooleanOrNull(raw.apply_eligible),
    canvasApplyAllowed:
      asBooleanOrNull(raw.canvasApplyAllowed)
      ?? asBooleanOrNull(raw.canvas_apply_allowed)
      ?? asBooleanOrNull(raw.apply_eligible),
    queueAllowed:
      asBooleanOrNull(raw.queueAllowed) ?? asBooleanOrNull(raw.queue_allowed),
    graphUnchanged:
      asBooleanOrNull(raw.graphUnchanged) ?? asBooleanOrNull(raw.graph_unchanged),
    report: isObject(raw.report) ? clonePlainData(raw.report) : null,
    auditRef: isObject(raw.auditRef) ? clonePlainData(raw.auditRef)
      : isObject(raw.audit_ref) ? clonePlainData(raw.audit_ref)
        : null,
    debug: isObject(raw.debug) ? clonePlainData(raw.debug) : null,
    failureKind: asString(raw.failureKind) || asString(raw.failure_kind),
    retryable: asBooleanOrNull(raw.retryable),
    nextAction: asString(raw.nextAction) || asString(raw.next_action),
    clarificationRequired:
      asBooleanOrNull(raw.clarificationRequired) ?? asBooleanOrNull(raw.clarification_required),
    clarificationMessage:
      asString(raw.clarificationMessage) || asString(raw.clarification_message),
    rebaselineRecovery,
    sessionId: asString(raw.sessionId) || asString(raw.session_id),
    turnId: asString(raw.turnId) || asString(raw.turn_id),
    baselineTurnId: asString(raw.baselineTurnId) || asString(raw.baseline_turn_id),
    baselineGraphHash:
      asString(raw.baselineGraphHash) || asString(raw.baseline_graph_hash),
    baselineGraphHashKind:
      asString(raw.baselineGraphHashKind) || asString(raw.baseline_graph_hash_kind),
    baselineGraphHashVersion:
      raw.baselineGraphHashVersion ?? raw.baseline_graph_hash_version ?? null,
    baselineSource: asString(raw.baselineSource) || asString(raw.baseline_source),
    baselineRebaselineId:
      asString(raw.baselineRebaselineId) || asString(raw.baseline_rebaseline_id),
    baselineGraphSourcePath:
      asString(raw.baselineGraphSourcePath) || asString(raw.baseline_graph_source_path),
    submitGraphHash: asString(raw.submitGraphHash) || asString(raw.submit_graph_hash),
    clientGraphHash: asString(raw.clientGraphHash) || asString(raw.client_graph_hash),
    clientStructuralGraphHash:
      asString(raw.clientStructuralGraphHash) || asString(raw.client_structural_graph_hash),
    latestCandidate,
    messages: Array.isArray(raw.messages)
      ? raw.messages.map((message) => normalizeMessage(message, { endpoint, allowLegacy }))
      : null,
    sessionPath: asString(raw.sessionPath) || asString(raw.session_path),
    sessionPathResolved:
      asString(raw.sessionPathResolved) || asString(raw.session_path_resolved),
    detailJsonPath: asString(raw.detailJsonPath) || asString(raw.detail_json_path),
    detailJsonPathResolved:
      asString(raw.detailJsonPathResolved) || asString(raw.detail_json_path_resolved),
  };
  for (const identity of turnIdentitySources(raw)) {
    normalized.turnIdentity = normalizeTurnIdentityPayload(identity);
    if (normalized.turnIdentity) {
      break;
    }
  }

  return normalized;
}

function normalizeIfNeeded(value, options) {
  return value?.[NORMALIZED_RESPONSE_MARKER] === true
    ? value
    : normalizeAgentEditResponse(value, options);
}

export function readOutcome(value, options) {
  return normalizeIfNeeded(value, options).outcome;
}

export function readCandidate(value, options) {
  return normalizeIfNeeded(value, options).candidate;
}

export function readCandidateGraph(value, options) {
  return normalizeIfNeeded(value, options).candidateGraph;
}

export function readEligibility(value, options) {
  return normalizeIfNeeded(value, options).eligibility;
}

export function readRebaselineRecovery(value, options) {
  return normalizeIfNeeded(value, options).rebaselineRecovery;
}

export function readLatestCandidate(value, options) {
  return normalizeIfNeeded(value, options).latestCandidate;
}

/**
 * Normalize a canonical StageSnapshot from a response or raw snapshot.
 *
 * When passed a response with multiple snapshots, the latest snapshot is used
 * by default; pass { stage } or { index } to select a specific entry.
 */
export function readStageSnapshot(value, options = {}) {
  if (isObject(value) && asString(value.stage)) {
    return normalizeStageSnapshotPayload(value);
  }
  const normalized = normalizeIfNeeded(value, options);
  const snapshots = Array.isArray(normalized.stageSnapshots) ? normalized.stageSnapshots : [];
  if (options.stage) {
    return snapshots.find((snapshot) => snapshot.stage === options.stage) || null;
  }
  const index = typeof options.index === "number" ? options.index : snapshots.length - 1;
  return index >= 0 && index < snapshots.length ? snapshots[index] : null;
}

export function readTurnIdentity(value, options) {
  if (isObject(value) && (
    Object.prototype.hasOwnProperty.call(value, "session_id")
    || Object.prototype.hasOwnProperty.call(value, "sessionId")
    || Object.prototype.hasOwnProperty.call(value, "turn_id")
    || Object.prototype.hasOwnProperty.call(value, "turnId")
  )) {
    const direct = normalizeTurnIdentityPayload(value);
    if (direct) {
      return direct;
    }
  }
  return normalizeIfNeeded(value, options).turnIdentity;
}

export function readApplyCandidate(value, options) {
  const normalized = normalizeIfNeeded(value, options);
  const candidate = normalized.candidate;
  if (!isObject(candidate) || !isObject(normalized.candidateGraph)) {
    return null;
  }
  const identity = readTurnIdentity(normalized);
  return compactObject({
    state: asString(candidate.state) || "candidate",
    graph: normalized.candidateGraph,
    graphHash:
      asString(candidate.graphHash)
      || asString(candidate.graph_hash)
      || normalized.candidateGraphHash,
    structuralGraphHash:
      asString(candidate.structuralGraphHash) || asString(candidate.structural_graph_hash),
    baselineGraphHash:
      asString(candidate.baselineGraphHash)
      || asString(candidate.baseline_graph_hash)
      || normalized.baselineGraphHash,
    submitGraphHash:
      asString(candidate.submitGraphHash)
      || asString(candidate.submit_graph_hash)
      || normalized.submitGraphHash,
    submitStructuralGraphHash:
      asString(candidate.submitStructuralGraphHash) || asString(candidate.submit_structural_graph_hash),
    candidateGraphHash: normalized.candidateGraphHash,
    eligibility: isObject(normalized.eligibility) ? clonePlainData(normalized.eligibility) : null,
    applyable: normalized.eligibility
      ? normalized.eligibility.applyable === true
      : normalized.applyEligible === true,
    turnIdentity: identity,
  });
}

export function readFieldChanges(value, options) {
  if (isObject(value) && value?.[NORMALIZED_RESPONSE_MARKER] !== true) {
    const rawChanges = readRawFieldChanges(value);
    if (rawChanges.all.length > 0) {
      return rawChanges;
    }
  }
  return normalizeIfNeeded(value, options).fieldChanges;
}

export function readUserFailure(value, options) {
  const normalized = normalizeIfNeeded(value, options);
  if (normalized.outcome?.kind !== "error") {
    return null;
  }
  return compactObject({
    kind: "error",
    failureKind:
      asString(normalized.outcome.failureKind)
      || asString(normalized.outcome.failure_kind)
      || normalized.failureKind,
    stage: asString(normalized.outcome.stage),
    message: normalized.message,
    nextAction:
      asString(normalized.outcome.nextAction)
      || asString(normalized.outcome.next_action)
      || normalized.nextAction,
    retryable:
      asBooleanOrNull(normalized.outcome.retryable) ?? normalized.retryable,
    graphUnchanged:
      asBooleanOrNull(normalized.outcome.graphUnchanged)
      ?? asBooleanOrNull(normalized.outcome.graph_unchanged)
      ?? normalized.graphUnchanged,
    agentFailureContext:
      isObject(normalized.outcome.agentFailureContext)
        ? clonePlainData(normalized.outcome.agentFailureContext)
        : isObject(normalized.outcome.agent_failure_context)
          ? clonePlainData(normalized.outcome.agent_failure_context)
          : null,
    rebaselineRecovery: normalized.rebaselineRecovery,
  });
}

export function adaptLegacyAgentEditResponse(raw, options = {}) {
  return normalizeAgentEditResponse(raw, { ...options, allowLegacy: true });
}

export function normalizeCanonicalAgentEditResponse(raw, options = {}) {
  return normalizeAgentEditResponse(raw, { ...options, allowLegacy: false });
}

export {
  PUBLIC_OUTCOME_KINDS,
  extractRebaselineRecovery,
  normalizeRebaselineRecovery,
};
