const PUBLIC_OUTCOME_KINDS = Object.freeze([
  "candidate",
  "noop",
  "clarify",
  "error",
]);

const CANONICAL_EXECUTOR_ROUTES = Object.freeze([
  "clarify",
  "inspect",
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
  const rebaselineRecovery = extractRebaselineRecovery(raw);
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
    route: CANONICAL_EXECUTOR_ROUTES.includes(raw.route) ? raw.route : null,
    reply: asString(raw.reply) || asString(raw.message),
    evidence: isObject(raw.evidence) || Array.isArray(raw.evidence) ? clonePlainData(raw.evidence) : null,
    outcome,
    candidateGraph,
    candidate: normalizeCandidateEnvelope(raw, candidateGraph),
    candidateGraphHash:
      asString(raw.candidateGraphHash) || asString(raw.candidate_graph_hash),
    eligibility,
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

export {
  PUBLIC_OUTCOME_KINDS,
  extractRebaselineRecovery,
  normalizeRebaselineRecovery,
};
