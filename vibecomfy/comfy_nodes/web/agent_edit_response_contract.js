const PUBLIC_OUTCOME_KINDS = Object.freeze([
  "candidate",
  "noop",
  "clarify",
  "requires_custom_nodes",
  "error",
]);

const CANONICAL_EXECUTOR_ROUTES = Object.freeze([
  "clarify",
  "inspect",
  "respond",
  "research",
  "requires_custom_nodes",
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

function freezePlainData(value) {
  if (Array.isArray(value)) {
    for (const entry of value) {
      freezePlainData(entry);
    }
    return Object.freeze(value);
  }
  if (isObject(value)) {
    for (const entry of Object.values(value)) {
      freezePlainData(entry);
    }
    return Object.freeze(value);
  }
  return value;
}

function frozenPlainClone(value) {
  return freezePlainData(clonePlainData(value));
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

function compactFrozenObject(value) {
  return freezePlainData(compactObject(value));
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

export function outcomeRequiresCustomNodes(outcome) {
  return Boolean(isObject(outcome) && outcome.kind === "requires_custom_nodes");
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

function normalizeCustomNodeCandidate(candidate) {
  if (!isObject(candidate)) {
    return null;
  }
  const packSource = isObject(candidate.pack) ? candidate.pack : candidate.ref;
  const evidence = Array.isArray(candidate.evidence) ? clonePlainData(candidate.evidence) : [];
  const warnings = Array.isArray(candidate.warnings)
    ? candidate.warnings.map((warning) => String(warning)).filter(Boolean)
    : [];
  return compactObject({
    pack: isObject(packSource) ? clonePlainData(packSource) : null,
    expectedClasses: Array.isArray(candidate.expected_classes)
      ? candidate.expected_classes.map((item) => String(item)).filter(Boolean)
      : Array.isArray(candidate.expectedClasses)
        ? candidate.expectedClasses.map((item) => String(item)).filter(Boolean)
        : [],
    validationMode:
      asString(candidate.validation_mode)
      || asString(candidate.validationMode)
      || "evidence_only",
    evidence,
    warnings,
    stableInstallHash:
      asString(candidate.stable_install_hash) || asString(candidate.stableInstallHash),
  });
}

function normalizeCustomNodeResolutionPayload(outcome) {
  if (!isObject(outcome) || outcome.kind !== "requires_custom_nodes") {
    return null;
  }
  const candidates = Array.isArray(outcome.candidates)
    ? outcome.candidates.map(normalizeCustomNodeCandidate).filter(Boolean)
    : [];
  return compactObject({
    kind: "requires_custom_nodes",
    candidates,
    warnings: Array.isArray(outcome.warnings)
      ? outcome.warnings.map((warning) => String(warning)).filter(Boolean)
      : [],
    query: asString(outcome.query),
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
    // respond / research / inspect / requires_custom_nodes are non-applyable routes.
    if (
      response.route === "respond"
      || response.route === "research"
      || response.route === "inspect"
      || response.route === "requires_custom_nodes"
    ) {
      return compactObject({
        kind: response.route === "requires_custom_nodes" ? "requires_custom_nodes" : "noop",
        candidates: Array.isArray(response.candidates) ? clonePlainData(response.candidates) : undefined,
        warnings: Array.isArray(response.warnings) ? clonePlainData(response.warnings) : undefined,
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
    customNodeResolution: normalizeCustomNodeResolutionPayload(outcome),
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

function projectionSource(value) {
  return value?.[NORMALIZED_RESPONSE_MARKER] === true ? value.raw || value : value;
}

function asSafeOutcomeSummary(raw, outcome = null) {
  return asString(outcome?.summary)
    || asString(outcome?.message)
    || asString(outcome?.reason)
    || asString(raw?.changeDetails?.done_summary)
    || asString(raw?.change_details?.done_summary)
    || asString(raw?.message)
    || asString(raw?.reply)
    || asString(raw?.text);
}

function projectProgress(raw) {
  return isObject(raw?.progress) ? frozenPlainClone(raw.progress) : null;
}

function projectTranscriptMessageObject(raw) {
  if (!isObject(raw)) {
    return null;
  }
  const turnIdentity = isObject(raw.turnIdentity)
    ? raw.turnIdentity
    : isObject(raw.turn_identity) ? raw.turn_identity : null;
  return compactFrozenObject({
    role: asString(raw.role) || asString(turnIdentity?.role),
    text: asString(raw.text) || asString(raw.message) || asString(raw.reply),
    turn_id: asString(raw.turn_id) || asString(raw.turnId)
      || asString(turnIdentity?.turn_id) || asString(turnIdentity?.turnId),
    session_id: asString(raw.session_id) || asString(raw.sessionId)
      || asString(turnIdentity?.session_id) || asString(turnIdentity?.sessionId),
    local_id: asString(raw.local_id) || asString(raw.localId),
    timestamp: asString(raw.timestamp),
    source: asString(raw.source),
    pending_response: raw.pending_response === true ? true : undefined,
    optimistic: raw.optimistic === true ? true : undefined,
    synthetic: raw.synthetic === true ? true : undefined,
    submit_epoch: Number.isFinite(raw.submit_epoch) ? raw.submit_epoch : undefined,
    progress: projectProgress(raw),
    progress_label: asString(raw.progress_label) || asString(raw.progressLabel),
    canonical_activity: isObject(raw.canonical_activity) ? frozenPlainClone(raw.canonical_activity) : undefined,
  });
}

/**
 * Project raw or rehydrated message data into normal renderer-safe transcript
 * state. This deliberately excludes debug, audit, raw payload, provider, and
 * batch diagnostics; those belong to explicit affordance selectors below.
 */
export function projectTranscriptMessage(value) {
  return projectTranscriptMessageObject(projectionSource(value));
}

function responseDetailChanges(raw) {
  if (Array.isArray(raw?.outcome?.changes)) {
    return frozenPlainClone(raw.outcome.changes);
  }
  if (Array.isArray(raw?.changes)) {
    return frozenPlainClone(raw.changes);
  }
  if (isObject(raw?.changes)) {
    const fieldChanges = raw.changes;
    const all = Array.isArray(fieldChanges.all)
      ? fieldChanges.all
      : [
          ...(Array.isArray(fieldChanges.directChanges) ? fieldChanges.directChanges : []),
          ...(Array.isArray(fieldChanges.outcomeChanges) ? fieldChanges.outcomeChanges : []),
          ...(Array.isArray(fieldChanges.legacyChanges) ? fieldChanges.legacyChanges : []),
          ...(Array.isArray(fieldChanges.batchTurnChanges)
            ? fieldChanges.batchTurnChanges.flatMap((turn) => Array.isArray(turn?.changes) ? turn.changes : [])
            : []),
        ];
    return frozenPlainClone(all);
  }
  const fieldChanges = readRawFieldChanges(raw);
  return frozenPlainClone(fieldChanges.all);
}

function safeCandidateReport(rawReport) {
  if (!isObject(rawReport)) {
    return null;
  }
  const contentEdits = rawReport.change?.content_edits;
  const safeContentEdits = {};
  if (isObject(contentEdits)) {
    for (const key of ["preserved", "edited", "new_auto_placed", "removed", "stripped_helpers"]) {
      if (Array.isArray(contentEdits[key])) {
        safeContentEdits[key] = contentEdits[key].map(asStringOrNumber).filter(Boolean);
      }
    }
    if (Array.isArray(contentEdits.removed_named)) {
      safeContentEdits.removed_named = contentEdits.removed_named
        .map((item) => isObject(item) ? compactObject({
          uid: asStringOrNumber(item.uid),
          class_type: asString(item.class_type) || asString(item.classType),
        }) : null)
        .filter(Boolean);
    }
    if (Array.isArray(contentEdits.virtual_wires_degraded)) {
      safeContentEdits.virtual_wires_degraded = contentEdits.virtual_wires_degraded
        .map((item) => isObject(item) ? compactObject({
          uid: asStringOrNumber(item.uid),
          node_id: asStringOrNumber(item.node_id) || asStringOrNumber(item.nodeId),
        }) : null)
        .filter(Boolean);
    }
  }
  const change = {};
  if (Object.keys(safeContentEdits).length) {
    change.content_edits = safeContentEdits;
  }
  if (Array.isArray(rawReport.change?.lowered)) {
    change.lowered = rawReport.change.lowered
      .map((item) => isObject(item) ? compactObject({
        uid: asStringOrNumber(item.uid) || asStringOrNumber(item.source_node_uid),
        lowered_native_count:
          Number.isFinite(item.lowered_native_count) ? item.lowered_native_count : undefined,
      }) : null)
      .filter(Boolean);
  }
  return Object.keys(change).length ? { change } : null;
}

function safeProjectedCandidateReport(source, candidate) {
  return safeCandidateReport(source.report)
    || safeCandidateReport(candidate?.report)
    || (isObject(source.turn) && isObject(candidate?.report) ? frozenPlainClone(candidate.report) : null);
}

function safeAppliedFeedbackItem(item) {
  if (!isObject(item)) {
    return null;
  }
  const projected = compactObject({
    uid: asStringOrNumber(item.uid),
    label: asString(item.label),
    color: asString(item.color),
    kind: asString(item.kind),
  });
  return Object.keys(projected).length ? projected : null;
}

function safeAppliedFeedbackUnresolvedItem(item) {
  if (typeof item === "string") {
    return item;
  }
  if (!isObject(item)) {
    return null;
  }
  const projected = compactObject({
    uid: asStringOrNumber(item.uid),
    label: asString(item.label),
    reason: asString(item.reason),
  });
  return Object.keys(projected).length ? projected : null;
}

function safeLastAppliedChanges(raw) {
  const source = isObject(raw?.lastAppliedChanges)
    ? raw.lastAppliedChanges
    : isObject(raw?.last_applied_changes) ? raw.last_applied_changes : null;
  if (!source) {
    return null;
  }
  const items = Array.isArray(source.items)
    ? source.items.map(safeAppliedFeedbackItem).filter(Boolean)
    : [];
  const unresolved = Array.isArray(source.unresolved)
    ? source.unresolved.map(safeAppliedFeedbackUnresolvedItem).filter(Boolean)
    : [];
  if (!items.length && !unresolved.length) {
    return null;
  }
  return compactFrozenObject({
    mode: asString(source.mode),
    items,
    unresolved,
  });
}

function safeQueueIssue(issue) {
  if (!isObject(issue)) {
    return null;
  }
  const projected = compactObject({
    code: asString(issue.code),
    message: asString(issue.message) || asString(issue.user_facing_message),
    severity: asString(issue.severity),
  });
  return Object.keys(projected).length ? projected : null;
}

function queueIssueCandidates(report) {
  if (!isObject(report)) {
    return [];
  }
  const queueValidateEvidence = report.gates?.queue_validate_ok?.evidence;
  return [
    ...(Array.isArray(report.queue_blockers) ? report.queue_blockers : []),
    ...(Array.isArray(report.diagnostics?.issues) ? report.diagnostics.issues : []),
    ...(Array.isArray(queueValidateEvidence?.blockers) ? queueValidateEvidence.blockers : []),
    ...(Array.isArray(queueValidateEvidence?.queue_blockers) ? queueValidateEvidence.queue_blockers : []),
  ];
}

function safeQueueIssuesFromReport(report) {
  return queueIssueCandidates(report).map(safeQueueIssue).filter(Boolean);
}

const INTENT_CLASS_TYPES = new Set(["vibecomfy.code", "vibecomfy.exec", "vibecomfy.loop"]);

function isIntentClassType(value) {
  return typeof value === "string" && INTENT_CLASS_TYPES.has(value);
}

function safeQueueIssuesFromGraphScan(report) {
  if (!isObject(report)) {
    return [];
  }
  const graphNodes = Array.isArray(report.graph?.nodes)
    ? report.graph.nodes
    : Array.isArray(report.nodes)
      ? report.nodes
      : [];
  const issues = [];
  for (const node of graphNodes) {
    const classType = node?.type || node?.class_type;
    if (isIntentClassType(classType)) {
      issues.push(safeQueueIssue({
        code: "intent_node_queue_blocker",
        message: `Node ${node?.id ?? "unknown"} (${classType}) is an editor-only intent node and cannot be queued until it is lowered.`,
        severity: "error",
      }));
    }
  }
  return issues.filter(Boolean);
}

function safeQueueDisplay(raw, projectedCandidateReport) {
  if (isObject(raw?.queueDisplay)) {
    const projectedIssues = Array.isArray(raw.queueDisplay.issues)
      ? raw.queueDisplay.issues.map(safeQueueIssue).filter(Boolean)
      : [];
    return compactFrozenObject({
      state: asString(raw.queueDisplay.state),
      reason: asString(raw.queueDisplay.reason),
      message: asString(raw.queueDisplay.message),
      issues: projectedIssues.length ? projectedIssues : undefined,
    });
  }

  let issues = safeQueueIssuesFromReport(raw.report);
  if (!issues.some((issue) => issue.code === "intent_node_queue_blocker")) {
    issues = issues.concat(safeQueueIssuesFromGraphScan(raw.report));
  }
  const queueState =
    asBooleanOrNull(raw.queueAllowed) ?? asBooleanOrNull(raw.queue_allowed);
  const eligibility = isObject(raw.eligibility)
    ? raw.eligibility
    : isObject(raw.applyEligibility) ? raw.applyEligibility
      : isObject(raw.apply_eligibility) ? raw.apply_eligibility : null;
  const state =
    queueState === true
      ? "eligible"
      : queueState === false || issues.length
        ? "blocked"
        : null;
  if (!state && !issues.length) {
    return null;
  }
  return compactFrozenObject({
    state,
    reason: asString(eligibility?.reason),
    message: asString(eligibility?.message),
    issues: issues.length ? issues : safeQueueIssuesFromReport(projectedCandidateReport),
  });
}

/**
 * Project raw response/message data into normal expanded-bubble detail state.
 * The projection keeps user-facing summaries, safe progress, candidate hashes,
 * and field-change summaries only; explicit debug/audit/report payloads are not
 * part of this normal surface.
 */
export function projectResponseDetail(value) {
  const source = projectionSource(value);
  if (!isObject(source)) {
    return null;
  }
  const outcome = isObject(source.outcome) ? source.outcome : null;
  const candidate = isObject(source.candidate) ? source.candidate : null;
  const projectedCandidateReport = safeProjectedCandidateReport(source, candidate);
  const candidateGraphHash =
    asString(candidate?.graphHash)
    || asString(candidate?.graph_hash)
    || asString(source.candidateGraphHash)
    || asString(source.candidate_graph_hash)
    || (isObject(candidate?.graph) || isObject(source.candidateGraph) || isObject(source.candidate_graph) || isObject(source.graph)
      ? "present"
      : null);
  return compactFrozenObject({
    turn: compactObject({
      turnId: asString(source.turn?.turnId) || asString(source.turnId) || asString(source.turn_id),
      sessionId: asString(source.turn?.sessionId) || asString(source.sessionId) || asString(source.session_id),
      status: asString(source.turn?.status) || asString(source.status) || asString(outcome?.kind),
    }),
    outcome: compactObject({
      kind: asString(outcome?.kind),
      summary: asSafeOutcomeSummary(source, outcome),
      question: asString(outcome?.question),
    }),
    changes: responseDetailChanges(source),
    progress: projectProgress(source),
    eligibility: isObject(source.eligibility) ? frozenPlainClone(source.eligibility)
      : isObject(source.applyEligibility) ? frozenPlainClone(source.applyEligibility)
        : isObject(source.apply_eligibility) ? frozenPlainClone(source.apply_eligibility)
          : null,
    candidate: candidateGraphHash ? compactObject({
      graphHash: candidateGraphHash,
      structuralGraphHash:
        asString(candidate?.structuralGraphHash) || asString(candidate?.structural_graph_hash),
      baselineGraphHash:
        asString(candidate?.baselineGraphHash) || asString(candidate?.baseline_graph_hash),
      report: projectedCandidateReport,
    }) : null,
    lastAppliedChanges: safeLastAppliedChanges(source),
    queueDisplay: safeQueueDisplay(source, projectedCandidateReport),
  });
}

function diagnosticReasoning(raw) {
  if (Array.isArray(raw?.report?.executor?.reasoning)) {
    return raw.report.executor.reasoning;
  }
  if (Array.isArray(raw?.reasoning)) {
    return raw.reasoning;
  }
  return [];
}

function providerDiagnostics(raw) {
  if (raw?.providerDiagnostics !== undefined) {
    return raw.providerDiagnostics;
  }
  if (raw?.provider_diagnostics !== undefined) {
    return raw.provider_diagnostics;
  }
  if (raw?.report?.providerDiagnostics !== undefined) {
    return raw.report.providerDiagnostics;
  }
  if (raw?.report?.provider_diagnostics !== undefined) {
    return raw.report.provider_diagnostics;
  }
  return [];
}

function debugPayload(raw) {
  return raw?.debugPayload || raw?.debug_payload || raw?.debug || null;
}

function batchTurns(raw) {
  return raw?.change_details?.batch_turns
    || raw?.changeDetails?.batchTurns
    || raw?.batch_turns
    || raw?.batchTurns
    || [];
}

function compactDiagnosticSummary(raw) {
  if (!isObject(raw)) {
    return null;
  }
  const summary = compactObject({
    session_id: asString(raw.session_id) || asString(raw.sessionId),
    turn_id: asString(raw.turn_id) || asString(raw.turnId),
    source: asString(raw.source),
    code: asString(raw.code),
    severity: asString(raw.severity),
    message: asString(raw.message),
    lifecycle: asString(raw.lifecycle),
    stage: asString(raw.stage),
    status: asString(raw.status),
    ok: asBooleanOrNull(raw.ok),
    queue_allowed: asBooleanOrNull(raw.queue_allowed) ?? asBooleanOrNull(raw.queueAllowed),
    candidate_nodes: Number.isFinite(raw.candidate_nodes) ? raw.candidate_nodes
      : Number.isFinite(raw.candidateNodes) ? raw.candidateNodes : null,
    landed_operation_count: Number.isFinite(raw.landed_operation_count) ? raw.landed_operation_count
      : Number.isFinite(raw.landedOperationCount) ? raw.landedOperationCount : null,
  });
  return Object.keys(summary).length ? freezePlainData(summary) : null;
}

/**
 * Project explicit diagnostic execution data. This surface may include
 * reasoning, provider diagnostics, debug payloads, and batch_turns because it is
 * consumed only by opt-in debug/report affordances.
 */
export function projectExecutionEvent(value) {
  const source = projectionSource(value);
  if (!isObject(source)) {
    return null;
  }
  const outcome = isObject(source.outcome) ? source.outcome : null;
  const diagnosticSummary = compactDiagnosticSummary(source);
  return compactFrozenObject({
    session_id: asString(source.session_id) || asString(source.sessionId),
    turn_id: asString(source.turn_id) || asString(source.turnId),
    status: asString(source.status) || asString(source.outcome?.kind),
    task: asString(source.task) || asString(source.prompt) || asString(source.query),
    message: asString(source.message) || asString(source.text) || asString(source.reply),
    outcome: outcome ? frozenPlainClone(outcome) : null,
    failure_kind: asString(source.failure_kind) || asString(source.failureKind) || asString(outcome?.failure_kind),
    failure_stage: asString(source.failure_stage) || asString(source.failureStage) || asString(outcome?.stage),
    done_summary: asString(source.done_summary) || asString(source.doneSummary),
    source: asString(source.source),
    code: asString(source.code),
    severity: asString(source.severity),
    lifecycle: asString(source.lifecycle),
    stage: asString(source.stage),
    ok: asBooleanOrNull(source.ok),
    queue_allowed: asBooleanOrNull(source.queue_allowed) ?? asBooleanOrNull(source.queueAllowed),
    candidate_nodes: Number.isFinite(source.candidate_nodes) ? source.candidate_nodes
      : Number.isFinite(source.candidateNodes) ? source.candidateNodes : null,
    landed_operation_count: Number.isFinite(source.landed_operation_count) ? source.landed_operation_count
      : Number.isFinite(source.landedOperationCount) ? source.landedOperationCount : null,
    diagnostics: Array.isArray(source.diagnostics)
      ? frozenPlainClone(source.diagnostics.map(compactDiagnosticSummary).filter(Boolean))
      : diagnosticSummary ? freezePlainData([diagnosticSummary]) : null,
    change_details: isObject(source.change_details) ? frozenPlainClone(source.change_details)
      : isObject(source.changeDetails) ? frozenPlainClone(source.changeDetails)
        : null,
    field_changes: Array.isArray(source.field_changes) ? frozenPlainClone(source.field_changes)
      : Array.isArray(source.fieldChanges) ? frozenPlainClone(source.fieldChanges)
        : null,
    reasoning: frozenPlainClone(diagnosticReasoning(source)),
    providerDiagnostics: frozenPlainClone(providerDiagnostics(source)),
    debugPayload: debugPayload(source) ? frozenPlainClone(debugPayload(source)) : null,
    batchTurns: frozenPlainClone(batchTurns(source)),
  });
}

/**
 * Project explicit audit artifact references. Audit paths and artifact paths
 * are intentionally excluded from normal transcript/detail projections.
 */
export function projectAuditArtifact(value) {
  const source = projectionSource(value);
  if (!isObject(source)) {
    return null;
  }
  const auditRef = source.auditRef || source.audit_ref || null;
  const artifactRefs = source.artifactRefs || source.artifact_refs || source.artifacts || [];
  return compactFrozenObject({
    session_id: asString(source.session_id) || asString(source.sessionId),
    turn_id: asString(source.turn_id) || asString(source.turnId),
    source: asString(source.source),
    sha256: asString(source.sha256),
    byte_count: Number.isFinite(source.byte_count) ? source.byte_count
      : Number.isFinite(source.byteCount) ? source.byteCount : null,
    preview: asString(source.preview),
    auditRef: auditRef ? frozenPlainClone(auditRef) : null,
    artifactRefs: frozenPlainClone(Array.isArray(artifactRefs) ? artifactRefs : []),
  });
}

function sourceHasDiagnosticEvent(source) {
  return Boolean(
    source?.change_details?.batch_turns
    || source?.changeDetails?.batchTurns
    || source?.batch_turns
    || source?.batchTurns
    || source?.debugPayload
    || source?.debug_payload
    || source?.debug
    || source?.providerDiagnostics
    || source?.provider_diagnostics
    || source?.report?.providerDiagnostics
    || source?.report?.provider_diagnostics
    || source?.report?.executor?.reasoning
    || source?.reasoning
    || source?.code
    || source?.severity
    || source?.stage
    || source?.lifecycle
    || Array.isArray(source?.diagnostics),
  );
}

function sourceHasAuditArtifact(source) {
  return Boolean(
    source?.auditRef
    || source?.audit_ref
    || source?.artifactRefs
    || source?.artifact_refs
    || source?.artifacts
    || source?.sha256
    || source?.byte_count
    || source?.byteCount
    || source?.preview,
  );
}

function withRehydrateEnvelopeSession(raw, entry) {
  if (!isObject(entry)) {
    return entry;
  }
  const sessionId = asString(raw?.session_id) || asString(raw?.sessionId);
  if (!sessionId || entry.session_id || entry.sessionId) {
    return entry;
  }
  return { ...entry, session_id: sessionId };
}

function messageNeedsSessionInjection(message) {
  if (!isObject(message)) {
    return false;
  }
  // Only durable transcript entries carry a turn identity. Injecting the
  // envelope session id on purely local/optimistic-looking messages (no turn
  // id) would change legacy assertions that expect exact projection of the
  // raw message fields.
  return Boolean(
    asString(message.turn_id)
    || asString(message.turnId)
    || asString(message.turn_identity?.turn_id)
    || asString(message.turnIdentity?.turnId),
  );
}

export function splitRehydrateProjectionInput(raw) {
  const messages = Array.isArray(raw?.messages) ? raw.messages : [];
  const diagnostics = Array.isArray(raw?.diagnostics) ? raw.diagnostics : [];
  const auditArtifacts = Array.isArray(raw?.audit_artifacts) ? raw.audit_artifacts
    : Array.isArray(raw?.auditArtifacts) ? raw.auditArtifacts : [];
  // Rehydrate payloads carry the authoritative session id at the envelope level.
  // Distribute it to durable messages so the transcript, response details, and
  // diagnostic/audit compartments all share identity without requiring every
  // nested object to repeat it.
  const messagesWithSession = messages.map((message) => (
    messageNeedsSessionInjection(message)
      ? withRehydrateEnvelopeSession(raw, message)
      : message
  ));
  return freezePlainData({
    normalTranscriptMessage: messagesWithSession.map(projectTranscriptMessage).filter(Boolean),
    normalResponseDetail: messagesWithSession.map(projectResponseDetail).filter(Boolean),
    explicitDiagnosticEvent: [
      ...messagesWithSession.filter(sourceHasDiagnosticEvent),
      ...diagnostics.map((entry) => withRehydrateEnvelopeSession(raw, entry)),
    ]
      .map(projectExecutionEvent)
      .filter(Boolean),
    explicitAuditArtifact: [
      ...messagesWithSession.filter(sourceHasAuditArtifact),
      ...auditArtifacts.map((entry) => withRehydrateEnvelopeSession(raw, entry)),
    ]
      .map(projectAuditArtifact)
      .filter(Boolean),
  });
}

function transcriptMessageAlreadyPresent(messages, synthetic) {
  if (!synthetic || !Array.isArray(messages)) {
    return false;
  }
  return messages.some((message) => (
    message?.role === synthetic.role
    && typeof message?.text === "string"
    && message.text === synthetic.text
    && (!synthetic.turn_id || message.turn_id === synthetic.turn_id)
  ));
}

function stateFromSource(source) {
  return source?.state && isObject(source.state) ? source.state : source;
}

export function selectSyntheticTranscriptMessage(source) {
  const state = stateFromSource(source);
  if (!isObject(state?.syntheticAgentMessage)) {
    return null;
  }
  const synthetic = projectTranscriptMessage(state.syntheticAgentMessage);
  const existing = Array.isArray(state.transcriptMessages) && state.transcriptMessages.length > 0
    ? state.transcriptMessages
    : Array.isArray(state.chatMessages) ? state.chatMessages : [];
  return transcriptMessageAlreadyPresent(existing, synthetic) ? null : synthetic;
}

export function selectTranscriptMessages(source) {
  const state = stateFromSource(source);
  const base = Array.isArray(state?.transcriptMessages) && state.transcriptMessages.length > 0
    ? state.transcriptMessages
    : Array.isArray(state?.chatMessages) ? state.chatMessages : Array.isArray(source) ? source : [];
  const projected = base.map(projectTranscriptMessage).filter(Boolean);
  const synthetic = selectSyntheticTranscriptMessage(state);
  if (synthetic) {
    projected.push(synthetic);
  }
  return freezePlainData(projected);
}

export function selectResponseDetails(source) {
  const state = stateFromSource(source);
  const details = state?.responseDetails;
  if (Array.isArray(details)) {
    return freezePlainData(details.map(projectResponseDetail).filter(Boolean));
  }
  if (isObject(details)) {
    const projected = {};
    for (const [key, detail] of Object.entries(details)) {
      const projection = projectResponseDetail(detail);
      if (projection) {
        projected[key] = projection;
      }
    }
    return freezePlainData(projected);
  }
  return freezePlainData({});
}

export function selectExecutionEvents(source) {
  const state = stateFromSource(source);
  const events = Array.isArray(state?.executionEvents) ? state.executionEvents : Array.isArray(source) ? source : [];
  return freezePlainData(events.map(projectExecutionEvent).filter(Boolean));
}

export function selectAuditArtifacts(source) {
  const state = stateFromSource(source);
  const artifacts = Array.isArray(state?.auditArtifacts) ? state.auditArtifacts : Array.isArray(source) ? source : [];
  return freezePlainData(artifacts.map(projectAuditArtifact).filter(Boolean));
}

function compactReportText(text, maxLen = 240) {
  if (typeof text !== "string") {
    return null;
  }
  const compact = text.replace(/\s+/g, " ").trim();
  if (!compact) {
    return null;
  }
  return compact.length > maxLen ? `${compact.slice(0, maxLen - 3)}...` : compact;
}

function statusFromOutcome(outcome) {
  const kind = isObject(outcome) ? asString(outcome.kind) : null;
  if (kind === "clarification" || kind === "clarify") {
    return "clarify";
  }
  if (kind === "noop" || kind === "candidate" || kind === "error") {
    return kind;
  }
  return kind || "done";
}

export function projectDiagnosticTurnSummary(entry, index = 0) {
  if (!isObject(entry)) {
    return null;
  }
  const outcome = isObject(entry.outcome) ? entry.outcome : null;
  return compactFrozenObject({
    label:
      asString(entry.turn_id)
      || (Number.isFinite(entry.turn_number) ? `turn ${entry.turn_number}` : `entry ${index + 1}`),
    status: compactReportText(asString(entry.status) || asString(entry.phase) || statusFromOutcome(outcome) || "unknown", 80),
    task: compactReportText(asString(entry.task) || asString(entry.prompt) || asString(entry.query)),
    outcome: compactReportText(
      asString(entry.done_summary)
      || asString(outcome?.reason)
      || asString(outcome?.clarification?.message)
      || asString(entry.message)
      || asString(outcome?.kind)
      || asString(entry.exit_mode),
    ),
    failure: compactReportText(
      asString(entry.failure_kind)
      || asString(entry.failure?.message)
      || asString(entry.failure?.error),
    ),
    changes: Array.isArray(entry.field_changes) ? frozenPlainClone(entry.field_changes)
      : Array.isArray(entry.changes) ? frozenPlainClone(entry.changes)
        : null,
    reasoning: Array.isArray(entry.reasoning) ? frozenPlainClone(entry.reasoning) : null,
  });
}

export function selectDiagnosticTurnSummaries(source, limit = 5) {
  const state = stateFromSource(source);
  let turns = Array.isArray(state?.executionEvents) && state.executionEvents.length
    ? state.executionEvents
    : Array.isArray(state?.turns) ? state.turns : [];
  return freezePlainData(
    turns.slice(0, limit).map(projectDiagnosticTurnSummary).filter(Boolean),
  );
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

export function readCustomNodeResolution(value, options) {
  return normalizeIfNeeded(value, options).customNodeResolution;
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
