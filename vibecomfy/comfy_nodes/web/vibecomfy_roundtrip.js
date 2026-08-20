import {
  currentAgentPanel,
  getAgentPanelRuntime,
  nextAgentPanelId,
  panelsCreatedCount,
  setCurrentAgentPanel,
  // ── T7: Scope snapshot / draft management ────────────────────────────
  saveScopeDraft,
  getScopeDraft,
  saveScopeSnapshot,
  forgetScopeSnapshot,
  // ── T9: Per-scope queue guard context ────────────────────────────────
  saveScopeQueueGuardContext,
  getScopeQueueGuardContext,
  forgetScopeQueueGuardContext,
} from "./panel_runtime.js";
import {
  consumeAgentPanelDirtySections,
  ensureScheduledAgentPanelDirtyFlush,
  hasPendingAgentPanelFlush,
  isAgentPanelRootConnected,
  markAgentPanelDirty,
  markAgentPanelDirtyAfterCommit,
  markAllAgentPanelDirty,
  normalizeDirtySectionList,
  noteAgentPanelCommit,
  scheduleRenderAgentPanel,
  setRenderGateway,
  SETTINGS_STATUS_RENDER_SECTIONS,
} from "./panel_scheduler.js";
import {
  appendCandidateDetail as appendCandidateDetailImpl,
  appendFailureDetail as appendFailureDetailImpl,
  appendQueueDetail as appendQueueDetailImpl,
  changeDetailsForMessage as changeDetailsForMessageImpl,
  collectThreadMessageEntries as collectThreadMessageEntriesImpl,
  computeThreadDisplayEntries as computeThreadDisplayEntriesImpl,
  createBubbleDetailSection as createBubbleDetailSectionImpl,
  populateAgentBubbleDetail as populateAgentBubbleDetailImpl,
  recordThreadRender,
  reconcileChatBubbles as reconcileChatBubblesImpl,
  renderChatBubbleNode as renderChatBubbleNodeImpl,
  renderChatThread as renderChatThreadImpl,
  renderThreadSection as renderThreadSectionImpl,
  WELCOME_EXAMPLE_PROMPTS,
} from "./panel_thread.js";
import {
  clearPreviewDomOverlay,
  drawPreviewOverlay as panelOverlayDrawPreviewOverlay,
  installAgentPreviewOverlay as installAgentPreviewOverlayImpl,
  invalidateOverlayDrawModelCache,
  syncPreviewDomOverlay,
} from "./panel_overlay.js";
import {
  renderComposerActions as renderComposerActionsImpl,
  renderComposerNotice as renderComposerNoticeImpl,
  renderComposerNoticeSection as renderComposerNoticeSectionImpl,
  renderDeveloper as composerRenderDeveloper,
  renderDeveloperDisclosure as composerRenderDeveloperDisclosure,
  renderDeveloperSection as composerRenderDeveloperSection,
  renderSettings as composerRenderSettings,
  renderSettingsSection as composerRenderSettingsSection,
  submitReadinessState as submitReadinessStateImpl,
  syncComposerButtons as syncComposerButtonsImpl,
} from "./panel_composer.js";
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import {
  applyTypedSocketLabels,
  applyTypedSocketLabelsLabelOnly,
  applyTypedSocketTypesOnly,
  applyGraphCandidateInPlace,
  applyGraphDeltaInPlace,
  applyGraphLayoutInPlace,
  installQueueGuard as installQueueGuardAdapter,
  normalizeExecIoObject,
  normalizeExecNodeForSerialization as normalizeExecNodeForSerializationAdapter,
  normalizeGraphExecNodesForSerialization,
  normalizeIntentTypedIo,
  projectCandidateGraphToRuntimeLayout,
  readExecWidgetValue,
} from "./comfy_adapter.js";
import { createIntentGraphAdapter } from "./intent_graph_adapter.js";
import {
  createAgentEditState,
  createAgentStateCompartments,
  eventSessionMatchesActiveScope,
  ingestChatRehydratePayload,
  PANEL_STATE,
  RENDER_SECTIONS,
  normalizeDeltaOpsFromSubmit,
  normalizeObligationDirtySections,
  projectCompensatedFailure,
  transition,
} from "./agent_edit_lifecycle.js";
import {
  commitOptimisticSubmit,
  commitTerminalResponse,
  commitApplyResolved,
  commitLifecycleReset,
  commitPrepareStarted,
  commitPrepareSuccess,
  commitPrepareFailure,
  commitVerifyCanvasStarted,
  commitVerifyCanvasSuccess,
  commitVerifyCanvasFailure,
  commitFinalizeStarted,
  commitFinalizeSuccess,
  commitFinalizeFailure,
  commitRollbackStarted,
  commitRollbackSuccess,
  commitRollbackFailure,
  commitReconcileReceipts,
} from "./agent_lifecycle_commit.js";
import {
  normalizeAgentEditResponse,
  outcomeRequiresCustomNodes,
  readApplyCandidate,
  readCandidateTransaction,
  readCustomNodeResolution,
  readFieldChanges,
  readLatestCandidate,
  readRebaselineRecovery,
  readTurnIdentity,
  extractRebaselineRecovery,
  projectAuditArtifact,
  projectExecutionEvent,
  projectResponseDetail,
  projectTranscriptMessage,
  selectAuditArtifacts,
  selectExecutionEvents,
} from "./agent_edit_response_contract.js";
import {
  auditLandedMutationPlan,
  boundedBrowserTransactionError,
  isLayoutAuthorityTransaction,
  normalizeCandidateTransaction,
  resolvePreparedMutationPlan,
  transactionAllows,
  transactionAllowsRejectOrFailClosedDiscard,
} from "./agent_edit_transaction.js";
import {
  canonicalSessionJsonString,
} from "./canonical_hash.js";
import { decodeNodeFieldPathV1 } from "./canonical_delta.js";
import {
  buildLayoutGraphProjection,
  buildStructuralGraphProjection,
} from "./graph_projection.js";
import {
  projectionReferenceV1,
} from "./projection_registry_v1.js";
import { jsonClone as clonePlainData } from "./json_clone.js";
export {
  buildLayoutGraphProjection,
  buildStructuralGraphProjection,
} from "./graph_projection.js";

import {
  buildIssueReport,
  buildAgentSolvePrompt,
  buildCurrentAuditEnvelope,
  createDiagnosticsReporting,
  submitRating,
  installBrowserDiagnosticsCapture,
  commitSessionArtifactPathsFromResponse,
  compactPanelPreviewDiff,
} from "./diagnostics_reporting.js";
import {
  normalizeExecutorPhasePayload,
  progressFromExecutorPhase,
  executorProgressLabel,
  executorDecisionLabel,
  createExecutorProgressSnapshot,
  executorPhaseToCanonicalProgress,
} from "./executor_progress.js";
import {
  normalizeAgentTurnPayload,
  agentTurnProgressLabel,
  deriveAgentActivityState,
  reduceAgentActivityFeed,
  FEED_SOURCE_PRIORITY,
  isTerminalAgentTurnStatus,
} from "./agent_turn_feed.js";
import {
  clarificationMessageFromOutcome,
  durableTurnKey,
  executionEventKeyForTurn,
  executionEventTurnEntry,
  mergeBatchTurnEntry,
  normalizeBatchTurn,
  outcomeHasClarificationPrompt,
  outcomeIsNoop,
  outcomeRequiresClarification,
  readRoundtripFieldChanges,
  readRoundtripTurnIdentity,
  sortPanelTurns,
} from "./agent_turn_reducer.js";
import {
  AGENT_STATUS_RETRY_DELAYS_MS,
  CANONICAL_AGENT_PROVIDERS,
  ROUTE_ALIASES,
  ROUTE_LABELS,
  ROUTE_STATUS_KIND,
  _lsGet,
  _lsRemove,
  _lsSet,
  getRouteDescriptor,
  getPersistedAgentProvider,
  normalizeModelPreference,
  normalizeRoutePreference,
  persistAgentSettings,
  populateRouteSelect as pollerPopulateRouteSelect,
  refreshAgentStatus as pollerRefreshAgentStatus,
  refreshVibeComfyInfo as pollerRefreshVibeComfyInfo,
  refreshResearchContributionSetting as pollerRefreshResearchContributionSetting,
  routeStatusState,
  saveResearchContributionSetting as pollerSaveResearchContributionSetting,
  scheduleAgentStatusRetry as pollerScheduleAgentStatusRetry,
  setPersistedAgentProvider,
  storeOpenRouterCredential,
  syncChooseEngineGate as pollerSyncChooseEngineGate,
  testAgentSettings as testAgentSettingsImpl,
} from "./agent_status_poller.js";
import {
  APPLY_ELIGIBILITY_REASON,
  applyEligibility,
  disabledApplyEligibility,
  candidateActionState,
} from "./agent_candidate_actions.js";
import {
  fulfillNodePackInstallRequest,
} from "./agent_edit_node_pack_installer.js";
import {
  resolveActiveCanvasScope,
  resolveActiveWorkflowUuid,
  assertPanelScopeMatchesActiveCanvas,
  assertApplyScopeConsistency,
} from "./active_canvas_scope_guard.js";
import { installPreviewPicker } from "./preview_picker.js";
import { installAgenticReplay } from "./agentic_replay.js";
import { isLegacyUndoCacheEntryV1 } from "./journal_durable_v1.js";
import { createApplyFlow } from "./agent_apply_flow.js";
import {
  createSubmitFlowDeps,
  DEFAULT_SUBMIT_ABSOLUTE_DEADLINE_MS,
  DEFAULT_SUBMIT_AUTOMATIC_RETRY_COUNT,
  DEFAULT_SUBMIT_DEADLINE_MS,
} from "./agent_flow_deps.js";
import { createAgentPreviewCache } from "./agent_preview_cache.js";
import { createRebaselineUndoFlow } from "./agent_rebaseline_undo.js";
import {
  createSubmitFlow,
  DEFAULT_PIPELINE_MODE,
  normalizePipelineMode,
} from "./agent_submit_flow.js";
import { registerRoundtripExtension } from "./roundtrip_extension.js";

// Re-export diagnostics functions for tests and external callers.
export {
  buildIssueReport,
  buildAgentSolvePrompt,
  buildCurrentAuditEnvelope,
  downloadCurrentAudit,
  collectIssueReportFiles,
  downloadIssueReportZip,
  showIssueModal,
  submitRating,
  installBrowserDiagnosticsCapture,
};

// ── Facade entry points (delegate to local helpers + live-graph orchestrators) ──

export function normalizeForSerialize(graph, { live = false } = {}) {
  if (live) {
    normalizeLiveExecNodesForSerialization();
  } else {
    normalizeGraphExecNodesForSerialization(graph, { setExecWidgetValue });
    sanitizeSerializedGraphLinks(graph);
  }
}

export function normalizeForDisplay(node, fallbackClassType = null) {
  decorateIntentNode(node, fallbackClassType);
}

export function normalizeForApply(candidateGraph) {
  return applyFlow.normalizeForApply(candidateGraph);
}

export function repairLiveNodes(candidateGraph = null) {
  repairLiveIntentNodesFromCandidate(candidateGraph);
}

export { RENDER_SECTIONS };
export {
  markAgentPanelDirty,
  markAllAgentPanelDirty,
  scheduleRenderAgentPanel,
};
export {
  applyTypedSocketLabelsLabelOnly,
  normalizeExecNodeForSerialization,
  prepareCandidateGraphForPanel,
  repairLiveIntentNodesFromCandidate,
  sanitizeSerializedGraphLinks,
};

console.log("[vibecomfy] vibecomfy_roundtrip_main.mjs module evaluated");

// ── VibeComfy Contract (S2 — Durable Frontend Panel) ─────────────────────
// This file captures the frontend↔backend contract before feature work.
// Backend contract authority: vibecomfy/comfy_nodes/agent_contracts.py.

// ── Panel States ──────────────────────────────────────────────────────────
// The panel lifecycle during an agent-edit turn:
//   IDLE            — shell open, ready for prompt entry
//   SUBMITTING      — POST /vibecomfy/agent-edit in-flight
//   AWAITING_REVIEW — candidate received; Apply / Reject available
//   APPLYING        — local proof-only in-place graph apply in progress
//   ERROR           — request failed; failure region becomes primary

// ── Turn Metadata ─────────────────────────────────────────────────────────
// Each agent-edit interaction is a "turn" within a "session".
// Backend allocates these; frontend receives them in responses:
//   session_id (str)      — stable id for the editor session
//   turn_id (str)         — "0000", "0001", … per session; allocated by backend
//   baseline_turn_id      — last accepted turn; returned by backend, NEVER sent
//                            by frontend as a submit input
//   idempotency_key (str) — optional client-generated dedup key
//   client_graph_hash     — SHA-256 of serialized graph at submit time (opt)
//   client_structural_graph_hash — SHA-256 of structural graph projection (opt)

// ── Submit Fields (POST /vibecomfy/agent-edit) ────────────────────────────
//   graph   (object, required) — ComfyUI UI JSON (app.canvas.graph.serialize())
//   task    (string, required) — natural-language edit instruction
//   route   (string, optional) — "openrouter" (default when absent)
//   pipeline_mode (string) — canonical "staged" or "threaded"
//   model   (string, optional) — model id for the provider
//   session_id        (string, optional) — reuse existing session
//   idempotency_key   (string, optional) — client dedup key
//   client_graph_hash (string, optional) — SHA-256 of `graph` for diagnostics
//   client_structural_graph_hash (string, optional) — structural graph hash
//   client_live_canvas_token (string, optional) — live canvas lock token

// ── Accept Fields (POST /vibecomfy/agent-edit/accept) ─────────────────────
//   session_id        (string, required)
//   turn_id           (string, required)
//   client_graph_hash (string, optional) — hash of current canvas
//   live_graph        (object, required for v2 accept) — current serialized
//                     canvas snapshot; submit/rebaseline continue using `graph`
//   client_live_canvas_token (string, optional) — current live canvas lock token
//   submit_graph_hash (string, optional) — v2 server-side submit snapshot hash
//   candidate_graph_hash (string, optional) — v2 candidate snapshot hash
//   client_live_canvas_token is diagnostic only; it is not backend CAS authority
//   idempotency_key   (string, optional)

// ── Reject Fields (POST /vibecomfy/agent-edit/reject) ─────────────────────
//   session_id        (string, required)
//   turn_id           (string, required)
//   client_graph_hash (string, optional)
//   idempotency_key   (string, optional)

// ── Success Envelope (200) ─────────────────────────────────────────────────
// {
//   ok: true,
//   session_id, turn_id, baseline_turn_id,
//   canvas_apply_allowed, apply_allowed, queue_allowed,
//   gates: { python_load_ok, ir_validate_ok, ui_emit_ok, … },
//   message: "…",
//   graph: { … ComfyUI UI JSON … },
//   report: { change: { preserved, edited, removed_named, … },
//             recovery: […], felt: … },
//   artifacts: { … },
//   audit_ref: { … },
//   version: 1
// }

// ── Failure Envelope (4xx/5xx) ────────────────────────────────────────────
// {
//   ok: false,
//   kind: FailureKind — see agent_contracts.py FailureKind enum:
//     SyntaxError, ASTScanFailure, OversizedPayload, MalformedModelJSON,
//     MissingRequiredField, ProviderError, AgentRuntimeUnavailable,
//     AuthError, TimeoutError,
//     ValidationError, UnsatisfiedInputError, RefusedEmit,
//     EditorAheadConflict, StaleStateMismatch, UnsupportedNonDAG,
//     SchemaLessQueueBlocker, LowConfidenceQueueBlocker,
//     EditorOnlyNodeQueueBlocker, AuditWriteWarning, AuditWriteFailure
//   stage: str          — pipeline stage that failed
//   retryable: bool,
//   next_action: str,
//   graph_unchanged: bool,
//   user_facing_message: str,
//   agent_failure_context: { explanation, … },
//   session_id, turn_id, baseline_turn_id,
//   canvas_apply_allowed: bool,
//   queue_allowed: bool,
//   audit_ref: { … } | null,
//   audit_error: str | null
// }
//
// Frontend failure handling: the JS currently maps network errors to
// { kind: "NetworkError" } and serialization errors to
// { kind: "SerializeError" }. Backend failures carry a `kind` field
// matching FailureKind.

const SUPPORTED_FRONTEND = "1.39.x";
const PIPELINE_MODE_STORAGE_KEY = "vibecomfy_agent_pipeline_mode";

const ALL_AGENT_PANEL_RENDER_SECTIONS = Object.freeze(Object.values(RENDER_SECTIONS));
const AGENT_PANEL_SECTION_RENDER_ERROR_LIMIT = 20;
const AGENT_PANEL_SECTION_RENDER_RETRY_LIMIT = 3;
const AGENT_SIDEBAR_TAB_ID = "vibecomfy.agent-edit";
const AGENT_PANEL_MOUNT_MODE = Object.freeze({
  LAUNCHER: "launcher",
  SIDEBAR: "sidebar",
});

const PANEL_IDS = Object.freeze({
  root: "vibecomfy-agent-panel-root",
  shell: "vibecomfy-agent-panel-shell",
  status: "vibecomfy-agent-panel-status",
  composerNotice: "vibecomfy-agent-panel-composer-notice",
  prompt: "vibecomfy-agent-panel-prompt",
  route: "vibecomfy-agent-panel-route",
  pipelineMode: "vibecomfy-agent-panel-pipeline-mode",
  model: "vibecomfy-agent-panel-model",
  apiKey: "vibecomfy-agent-panel-api-key",
  researchContribution: "vibecomfy-agent-panel-research-contribution",
  researchContributionYes: "vibecomfy-agent-panel-research-contribution-yes",
  researchContributionNo: "vibecomfy-agent-panel-research-contribution-no",
  settingsStatus: "vibecomfy-agent-panel-settings-status",
  settingsGuidance: "vibecomfy-agent-panel-settings-guidance",
  settingsSave: "vibecomfy-agent-panel-settings-save",
  settingsTest: "vibecomfy-agent-panel-settings-test",
  submit: "vibecomfy-agent-panel-submit",
  apply: "vibecomfy-agent-panel-apply",
  reject: "vibecomfy-agent-panel-reject",
  rollback: "vibecomfy-agent-panel-rollback",
  undo: "vibecomfy-agent-panel-undo",
  havingIssues: "vibecomfy-agent-panel-having-issues",
  issueModal: "vibecomfy-agent-panel-issue-modal",
  close: "vibecomfy-agent-panel-close",
  threadRegion: "vibecomfy-agent-panel-region-thread",
  promptRegion: "vibecomfy-agent-panel-region-prompt",
  settingsRegion: "vibecomfy-agent-panel-region-settings",
  chatRegion: "vibecomfy-agent-panel-region-chat",
  historyRegion: "vibecomfy-agent-panel-region-history",
  candidateRegion: "vibecomfy-agent-panel-region-candidate",
  failureRegion: "vibecomfy-agent-panel-region-failure",
  queueRegion: "vibecomfy-agent-panel-region-queue",
  auditRegion: "vibecomfy-agent-panel-region-audit",
  debugRegion: "vibecomfy-agent-panel-region-debug",
  developerRegion: "vibecomfy-agent-panel-region-developer",
  developerToggle: "vibecomfy-agent-panel-developer-toggle",
  previewToggle: "vibecomfy-agent-preview-toggle",
  changeEngine: "vibecomfy-agent-panel-change-engine",
  welcomeOverlay: "vibecomfy-agent-panel-welcome-overlay",
});

const diagnosticsReporting = createDiagnosticsReporting({
  el,
  button,
  setButtonEmphasis,
  downloadBlob,
  getPanelElementById,
  buildAgentPanelDebugSnapshot,
  PANEL_IDS,
});
const {
  collectIssueReportFiles,
  downloadCurrentAudit,
  downloadIssueReportZip,
  downloadTurnAudit,
  downloadTurnAuditEntry,
  showIssueModal,
} = diagnosticsReporting;

// ── T-057: Submit flow behind injected boundaries ──────────────────────────
// Build one consumer-owned state bundle. Tests can configure this extension's
// watchdog through the re-exported closures without mutating another harness.
const submitFlowDeps = createSubmitFlowDeps();
const {
  configureSubmitWatchdogDeps,
  pendingTransactionSnapshotByPanel,
  resetSubmitWatchdogDeps,
  submitActivityByPanel,
  submitWatchdogDepsState,
} = submitFlowDeps;
const submitFlow = createSubmitFlow({
  submitWatchdogDepsState,
  submitActivityByPanel,
  pendingTransactionSnapshotByPanel,
  DEFAULT_SUBMIT_DEADLINE_MS,
  DEFAULT_SUBMIT_ABSOLUTE_DEADLINE_MS,
  DEFAULT_SUBMIT_AUTOMATIC_RETRY_COUNT,
  getPanelElementById,
  PANEL_IDS,
  PANEL_STATE,
  readOnDemandSchemasSetting,
  api,
  normalizeRoutePreference,
  agentPanelFailure,
  // Non-terminal inactivity stall: surface "still working" in the thread and
  // keep the watchdog waiting until the absolute deadline (see
  // agent_submit_flow.js runSubmitFetchWithDeadline).
  onSubmitStalled: notifySubmitStalled,
});

// ── T-062: Preview cache behind injected boundaries ────────────────────────
// The cache module owns candidate preview cache reads and writes on panel.state.
// Canvas rendering, layout-preview orchestration, and lifecycle candidate
// invalidation remain with their existing owners; shared helpers are injected once.
const previewCache = createAgentPreviewCache({
  app,
  canonicalJsonString: canonicalSessionJsonString,
  captureLiveCanvasRevision,
  compactNetFieldChanges: _compactNetFieldChanges,
  computePreviewDiffFacade: computePreviewDiff,
  createIntentGraphAdapter,
  currentAgentPanel,
  getLiveGraph,
  getLiveGraphNodes,
  getUid,
  prepareCandidateGraphForPanel,
  readWidgetValues,
  safePreviewLogDetail,
});
const {
  computePreviewDiff: computePreviewDiffImpl,
  getOrBuildPreviewDiff,
} = previewCache;

// ── T-058: Apply flow behind injected boundaries ───────────────────────────
// Build the dependency object once from roundtrip's live module singletons.
// Lifecycle transitions and rollback/replay remain authoritative here and are
// passed into the apply orchestrator without duplicating their state machines.
const applyFlow = createApplyFlow({
  RENDER_SECTIONS,
  agentPanelFailure,
  announceChangedNodes,
  app,
  applyEligibility,
  applyGraphCandidateInPlace,
  applyGraphDeltaInPlace,
  applyGraphLayoutInPlace,
  assertApplyScopeConsistency,
  auditLandedMutationPlan,
  boundedBrowserTransactionError,
  buildActionIdempotencyKey,
  buildCanvasSnapshot,
  clearLayoutPreviewState,
  clonePlainData,
  commitFinalizeFailure,
  commitFinalizeStarted,
  commitFinalizeSuccess,
  commitPrepareFailure,
  commitPrepareStarted,
  commitPrepareSuccess,
  commitVerifyCanvasFailure,
  commitVerifyCanvasStarted,
  commitVerifyCanvasSuccess,
  compensatedFailurePayload,
  createIntentGraphAdapter,
  currentAgentPanel,
  decorateIntentGraphPayload,
  decorateIntentNode,
  extractChangedNodeFeedback,
  findSerializedLinkByTarget,
  fulfillLifecycleTransitionObligations,
  inverseNodeUid: canonicalNodeUid,
  inverseSerializedLinks: normalizedSerializedLinks,
  isLayoutAuthorityTransaction,
  layoutPreviewBaselineSnapshot,
  markAgentPanelDirty,
  nodeTargetRefForRollback,
  normalizeCandidateTransaction,
  pendingTransactionSnapshotByPanel,
  postAgentLifecycleAction,
  projectionReferenceV1,
  pushHistory,
  pushTurnStatus,
  readGraphActualForOp,
  reconcilePreparedTransactionState,
  recordRoundtripResponseCompartments,
  recoveryForFailure,
  recoveryForPanelState,
  rememberTurnDetailSnapshot,
  renderLifecycleTransition,
  repairLiveIntentNodesFromCandidate,
  resolveActiveWorkflowUuid,
  resolveGraphNode,
  resolveGraphTarget,
  resolvePreparedMutationPlan,
  rollbackPreparedAgentCandidate,
  structuralProjectionV1: "structural_v1",
  transactionAllows,
  transition,
  validateScopedCanvasPreconditions,
  verifyScopedCanvasResults,
  widgetReferenceNodeFor,
});

const INTENT_NODE_CLASS_TYPES = new Set(["vibecomfy.code", "vibecomfy.exec", "vibecomfy.loop"]);
const INTENT_KIND_BY_CLASS_TYPE = Object.freeze({
  "vibecomfy.code": "code",
  "vibecomfy.exec": "code",
  "vibecomfy.loop": "loop",
});
const INTENT_PREVIEW_MAX = 120;
const _MAX_DYNAMIC_PORTS = 16;
const INTENT_STYLE_BY_KIND = Object.freeze({
  code: {
    color: "#2d2643",
    bgcolor: "#171229",
    boxcolor: "#e39cff",
  },
  loop: {
    color: "#17363b",
    bgcolor: "#10252a",
    boxcolor: "#6ee7f2",
  },
  degraded: {
    color: "#3a2a1f",
    bgcolor: "#231811",
    boxcolor: "#ffb86c",
  },
});

const LOWERED_DIFF_COLOR = "#02d4b3";
const LOWERED_BADGE = "lowered";

// ── localStorage helpers (safe wrappers — tolerate missing/throwing storage) ─
const LS_ACTIVE_SESSION_KEY = "vibecomfy_active_session_id";
const LS_RESEARCH_CONTRIBUTION_KEY = "vibecomfy_research_contribution_enabled";

function resolveModuleAssetUrl(path) {
  try {
    if (typeof URL === "function") {
      return new URL(path, import.meta.url).href;
    }
  } catch (_e) {
    // Test harnesses may provide a partial browser global without URL.
  }
  return path;
}

const VIBECOMFY_LOGO_URL = resolveModuleAssetUrl("./vibecomfy_agent_icon_cream.png");

// ── Scoped session-storage persistence ────────────────────────────────────
// Imported from a zero-dependency module so the helpers can be unit-tested
// without pulling in the full ComfyUI runtime (app, api, etc.).
import {
  _tabNonce,
  getScopedSessionId,
  setScopedSessionId,
  forgetScopedSessionId,
  resolveScopeSessionId,
} from "./scoped_session_storage.js";

// Re-export for test consumers that import from this module.
export {
  _tabNonce,
  getScopedSessionId,
  setScopedSessionId,
  forgetScopedSessionId,
  resolveScopeSessionId,
};

// ── T11: Re-export active-canvas scope guards for tests ─────────────────
export {
  resolveActiveCanvasScope,
  resolveActiveWorkflowUuid,
  assertPanelScopeMatchesActiveCanvas,
  assertApplyScopeConsistency,
};
export {
  configureSubmitWatchdogDeps,
  DEFAULT_SUBMIT_ABSOLUTE_DEADLINE_MS,
  DEFAULT_SUBMIT_AUTOMATIC_RETRY_COUNT,
  DEFAULT_SUBMIT_DEADLINE_MS,
  resetSubmitWatchdogDeps,
};

function getPersistedResearchContributionEnabled() {
  return _lsGet(LS_RESEARCH_CONTRIBUTION_KEY) === "1";
}

function setPersistedResearchContributionEnabled(value) {
  _lsSet(LS_RESEARCH_CONTRIBUTION_KEY, value ? "1" : "0");
}

// ── Default execution mode (settings combo + localStorage fallback) ─────────
const DEFAULT_EXECUTION_MODE_LS_KEY = "vibecomfy.defaultExecutionMode";
const DEFAULT_EXECUTION_MODE_VALUES = Object.freeze(["sandboxed_loose", "sandboxed_strict", "unrestricted"]);
const DEFAULT_EXECUTION_MODE_FALLBACK = "sandboxed_loose";

function getDefaultExecutionMode() {
  const stored = _lsGet(DEFAULT_EXECUTION_MODE_LS_KEY);
  if (stored && DEFAULT_EXECUTION_MODE_VALUES.includes(stored)) {
    return stored;
  }
  return DEFAULT_EXECUTION_MODE_FALLBACK;
}

// ── On-demand schemas (author uninstalled node packs) ─────────────────────
// Backend-visible setting: forwarded as `on_demand_schemas` on the agent-edit
// submit body so the schema provider knows whether to author schemas for node
// packs that aren't currently installed. Default ON.
function readOnDemandSchemasSetting() {
  return app?.ui?.settings?.getSettingValue
    ? app.ui.settings.getSettingValue("VibeComfy.OnDemandSchemas", true)
    : true;
}

function registerOnDemandSchemasSetting() {
  if (typeof app?.ui?.settings?.addSetting === "function") {
    try {
      app.ui.settings.addSetting({
        id: "VibeComfy.OnDemandSchemas",
        name: "VibeComfy — Author Uninstalled Node Packs",
        type: "boolean",
        defaultValue: true,
        tooltip:
          "When ON, the agent-edit backend may author schemas for node packs that are not currently installed (on-demand schema resolution). The current value is forwarded on every submit.",
        onChange: (/* value */) => {
          // The backend reads this at submit time via readOnDemandSchemasSetting();
          // nothing to persist here, so intentionally a no-op.
        },
      });
    } catch (_e) {
      // Settings registration failed; submit will fall back to default (true).
    }
  }
}

function registerDefaultExecutionModeSetting() {
  if (typeof app?.ui?.settings?.addSetting === "function") {
    try {
      app.ui.settings.addSetting({
        id: "VibeComfy.DefaultExecutionMode",
        name: "VibeComfy — Default Execution Mode",
        type: "combo",
        defaultValue: DEFAULT_EXECUTION_MODE_FALLBACK,
        options: [
          { value: "sandboxed_loose", text: "Sandboxed — Loose" },
          { value: "sandboxed_strict", text: "Sandboxed — Strict" },
          { value: "unrestricted", text: "⚠️ DANGEROUS — Unrestricted" },
        ],
        onChange: (value) => {
          _lsSet(DEFAULT_EXECUTION_MODE_LS_KEY, value);
        },
      });
    } catch (_e) {
      // Settings registration failed; localStorage fallback already works.
    }
  }
}

// ── Shared VibeComfy palette ────────────────────────────────────────────────
// Union of both feature palettes kept in ONE block: the preview-overlay diff
// keys (added/edited/removed/pending) and the turn-progress status-feed keys
// (active/success/warning/error/muted + bg* tints). Each feature reads its own
// keys; neither is broken by the merge.
const VC_COLORS = Object.freeze({
  // preview-overlay node/wire diff
  added: "#4caf50",
  edited: "#ffc107",
  removed: "#f44336",
  pending: "#7db6ff",
  // turn-progress status feed
  active: "#3d8bfd",
  success: "#02d4b3",
  warning: "#ffb86c",
  error: "#ff6c6c",
  muted: "#8d93a1",
  bgActive: "#1a2436",
  bgSuccess: "#0f2a26",
  bgWarning: "#2a1f14",
  bgError: "#2a1616",
});

// ── Alpha helper ────────────────────────────────────────────────────────────
function hexToRgba(hex, alpha) {
  let h = String(hex || "").replace(/^#/, "").trim();
  if (h.length === 3) {
    h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  }
  if (h.length !== 6 || !/^[0-9a-fA-F]{6}$/.test(h)) {
    return `rgba(0,0,0,${typeof alpha === "number" ? alpha : 1})`;
  }
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${typeof alpha === "number" ? alpha : 1})`;
}
function isIntentClassType(classType) {
  return INTENT_NODE_CLASS_TYPES.has(String(classType || "").trim());
}

function getIntentClassType(node, fallback = null) {
  const classType = String(
    node?.type
      || node?.comfyClass
      || node?.properties?.["Node name for S&R"]
      || fallback
      || "",
  ).trim();
  return isIntentClassType(classType) ? classType : "";
}

function truncateIntentPreview(value) {
  const text = String(value || "").trim().replace(/\s+/g, " ");
  if (!text) {
    return "";
  }
  return text.length > INTENT_PREVIEW_MAX
    ? `${text.slice(0, INTENT_PREVIEW_MAX - 1)}…`
    : text;
}

// Native widget mutation remains shell-owned and is injected into the adapter's
// canonical exec normalization. This preserves the classified S4 mutation seam.
function setExecWidgetValue(node, key, value) {
  if (!node || typeof node !== "object") {
    return;
  }
  const widgets = Array.isArray(node.widgets) ? node.widgets : [];
  for (const widget of widgets) {
    if (widget?.name === key) {
      widget.value = value;
    }
  }
  const current = node.widgets_values;
  if (current && typeof current === "object" && !Array.isArray(current)) {
    current[key] = value;
    return;
  }
  const values = Array.isArray(current) ? current : [];
  if (key === "source") {
    values[0] = value;
  } else if (key === "io") {
    values[1] = value;
  }
  node.widgets_values = values;
}

function normalizeExecNodeForSerialization(node, fallbackClassType = null) {
  return normalizeExecNodeForSerializationAdapter(
    node,
    fallbackClassType,
    { setExecWidgetValue },
  );
}

function sanitizeSerializedGraphLinks(graph) {
  if (!graph || typeof graph !== "object") {
    return graph;
  }
  const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const nodeById = new Map();
  for (const node of nodes) {
    if (node?.id !== null && node?.id !== undefined) {
      nodeById.set(String(node.id), node);
    }
  }
  const rawLinks = Array.isArray(graph.links)
    ? graph.links
    : Object.values(graph.links || {});
  const normalized = rawLinks
    .map((link) => ({ raw: link, normalized: normalizeSerializedLinkRecord(link) }))
    .filter((entry) => {
      const link = entry.normalized;
      if (!link) {
        return false;
      }
      const sourceNode = nodeById.get(String(link.origin_id));
      const targetNode = nodeById.get(String(link.target_id));
      if (!sourceNode || !targetNode) {
        return false;
      }
      if (Array.isArray(sourceNode.outputs) && !sourceNode.outputs[link.origin_slot]) {
        return false;
      }
      if (Array.isArray(targetNode.inputs) && !targetNode.inputs[link.target_slot]) {
        return false;
      }
      return true;
    });

  const byTarget = new Map();
  for (const entry of normalized) {
    const link = entry.normalized;
    const key = `${String(link.target_id)}:${Number(link.target_slot)}`;
    const targetNode = nodeById.get(String(link.target_id));
    const targetInput = Array.isArray(targetNode?.inputs) ? targetNode.inputs[link.target_slot] : null;
    const preferred = targetInput && String(targetInput.link) === String(link.id);
    const current = byTarget.get(key);
    if (!current || preferred || !current.preferred) {
      byTarget.set(key, { ...entry, preferred });
    }
  }

  const kept = Array.from(byTarget.values()).map((entry) => entry.normalized);
  const keptIds = new Set(kept.map((link) => String(link.id)));
  const outputLinks = new Map();
  const inputLinks = new Map();
  for (const link of kept) {
    const outKey = `${String(link.origin_id)}:${Number(link.origin_slot)}`;
    if (!outputLinks.has(outKey)) {
      outputLinks.set(outKey, []);
    }
    outputLinks.get(outKey).push(link.id);
    inputLinks.set(`${String(link.target_id)}:${Number(link.target_slot)}`, link.id);
  }

  for (const node of nodes) {
    if (Array.isArray(node.inputs)) {
      node.inputs.forEach((input, index) => {
        if (!input || typeof input !== "object") {
          return;
        }
        const key = `${String(node.id)}:${index}`;
        if (inputLinks.has(key)) {
          input.link = inputLinks.get(key);
        } else if (input.link !== null && input.link !== undefined && !keptIds.has(String(input.link))) {
          input.link = null;
        }
      });
    }
    if (Array.isArray(node.outputs)) {
      node.outputs.forEach((output, index) => {
        if (!output || typeof output !== "object") {
          return;
        }
        const links = outputLinks.get(`${String(node.id)}:${index}`) || [];
        if (Array.isArray(output.links) || output.links !== undefined) {
          output.links = links.length ? links : null;
        }
      });
    }
  }
  graph.links = Array.isArray(graph.links)
    ? kept.map((link) => [
        link.id,
        link.origin_id,
        link.origin_slot,
        link.target_id,
        link.target_slot,
        link.type,
      ])
    : Object.fromEntries(kept.map((link) => [String(link.id), { ...link }]));
  return graph;
}

function normalizeLiveExecNodesForSerialization() {
  const nodes = Array.isArray(app?.canvas?.graph?._nodes)
    ? app.canvas.graph._nodes
    : (Array.isArray(app?.canvas?.graph?.nodes) ? app.canvas.graph.nodes : []);
  for (const node of nodes) {
    normalizeExecNodeForSerialization(node);
  }
}

function captureSerializedGraphForAgent() {
  normalizeForSerialize(null, { live: true });
  const capture = createIntentGraphAdapter(app).capture();
  if (!capture.ok) {
    const error = new Error(capture.diagnostic?.message || "Unable to capture the active graph.");
    error.code = capture.diagnostic?.code || "serialization_failed";
    error.diagnostic = capture.diagnostic || null;
    throw error;
  }
  const graph = clonePlainData(capture.data.graph);
  normalizeForSerialize(graph);
  return graph;
}

function readIntentMetadata(node, fallbackClassType = null) {
  const properties = node?.properties && typeof node.properties === "object" ? node.properties : {};
  const classType = getIntentClassType(node, fallbackClassType);
  const payload = properties?.vibecomfy && typeof properties.vibecomfy === "object"
    ? properties.vibecomfy
    : null;
  const execIo = classType === "vibecomfy.exec"
    ? normalizeExecIoObject(readExecWidgetValue(node, "io"))
    : null;
  const ioPayload = payload?.io || execIo;
  const typedInputs = normalizeIntentTypedIo(ioPayload, "inputs");
  const typedOutputs = normalizeIntentTypedIo(ioPayload, "outputs");
  const kind = typeof payload?.kind === "string" && payload.kind
    ? payload.kind
    : INTENT_KIND_BY_CLASS_TYPE[classType] || "intent";
  const execSource = classType === "vibecomfy.exec" ? readExecWidgetValue(node, "source") : "";
  const sourcePreview = truncateIntentPreview(payload?.intent?.source || execSource);
  const specPreview = truncateIntentPreview(payload?.intent?.spec);
  const valid = Boolean(
    classType === "vibecomfy.exec"
      ? ioPayload
      : (
        payload
        && typeof payload === "object"
        && payload.intent
        && typeof payload.intent === "object"
      ),
  );
  // Resolve execution mode: widget → properties.vibecomfy.execution_mode → default
  const widgetExecMode = typeof properties.execution_mode === "string" && properties.execution_mode
    ? properties.execution_mode
    : "";
  const vibecomfyExecMode = typeof payload?.execution_mode === "string" && payload.execution_mode
    ? payload.execution_mode
    : "";
  const runtimeExecMode = typeof payload?.runtime?.execution_mode === "string" && payload.runtime.execution_mode
    ? payload.runtime.execution_mode
    : "";
  const executionMode = widgetExecMode || vibecomfyExecMode || runtimeExecMode || "sandboxed_loose";
  return {
    classType,
    kind,
    valid,
    badgeStatus: valid ? "editor-only" : "metadata missing",
    typedInputs,
    typedOutputs,
    sourcePreview,
    specPreview,
    executionMode,
  };
}

function buildIntentBadge(meta) {
  if (!meta.valid) {
    return `${meta.kind} · ${meta.badgeStatus}`;
  }
  if (meta.kind === "loop") {
    return "loop · expand to run";
  }
  if (meta.kind === "code") {
    const mode = meta.executionMode || "sandboxed_loose";
    return mode;
  }
  return `${meta.kind} · ${meta.badgeStatus}`;
}

function styleForIntentMeta(meta) {
  if (!meta.valid) {
    return INTENT_STYLE_BY_KIND.degraded;
  }
  return INTENT_STYLE_BY_KIND[meta.kind] || INTENT_STYLE_BY_KIND.degraded;
}

function _isDynamicIoCodeNode(node) {
  const classType = getIntentClassType(node);
  return classType === "vibecomfy.code" || classType === "vibecomfy.exec";
}

function decorateIntentNode(node, fallbackClassType = null) {
  const classType = getIntentClassType(node, fallbackClassType);
  if (!classType) {
    return false;
  }
  const meta = readIntentMetadata(node, classType);
  const style = styleForIntentMeta(meta);
  node.properties = node?.properties && typeof node.properties === "object" ? node.properties : {};
  node.color = style.color;
  node.bgcolor = style.bgcolor;
  node.boxcolor = style.boxcolor;
  node.properties.vibecomfy_intent_badge = buildIntentBadge(meta);
  node.properties["VibeComfy Intent Kind"] = meta.kind;
  node.properties["VibeComfy Intent Badge"] = node.properties.vibecomfy_intent_badge;
  if (meta.sourcePreview) {
    node.properties["VibeComfy Intent Source"] = meta.sourcePreview;
  }
  if (meta.specPreview) {
    node.properties["VibeComfy Intent Spec"] = meta.specPreview;
  }
  const dynamicIo = _isDynamicIoCodeNode(node);
  if (dynamicIo) {
    // Dynamic-IO code node: label-only (preserve in_i slot names for serialization).
    applyTypedSocketLabelsLabelOnly(node.inputs, meta.typedInputs);
    applyTypedSocketLabelsLabelOnly(node.outputs, meta.typedOutputs);
    // Preserve in_i/out_i names for serialization, but make the actual
    // LiteGraph socket types match the declared dynamic IO contract so manual
    // connections and graph.configure() compatibility checks see IMAGE, LATENT,
    // etc. instead of the fixed runtime pool's wildcard.
    applyTypedSocketTypesOnly(node.inputs, meta.typedInputs);
    applyTypedSocketTypesOnly(node.outputs, meta.typedOutputs);
    if (!meta.valid) {
      node.__vibecomfyIntentMeta = meta;
      return true;
    }
    // Hide unused trailing pool slots via removeInput/removeOutput.
    // We walk backwards so indices stay stable.
    const activeInputCount = Math.min(
      Array.isArray(meta.typedInputs) ? meta.typedInputs.length : 0,
      _MAX_DYNAMIC_PORTS,
    );
    if (Array.isArray(node.inputs)) {
      for (let i = node.inputs.length - 1; i >= activeInputCount; i -= 1) {
        if (typeof node.removeInput === "function") {
          try { node.removeInput(i); } catch (_e) { /* best-effort */ }
        } else {
          node.inputs.splice(i, 1);
        }
      }
    }
    const activeOutputCount = Math.min(
      Array.isArray(meta.typedOutputs) ? meta.typedOutputs.length : 0,
      _MAX_DYNAMIC_PORTS,
    );
    if (Array.isArray(node.outputs)) {
      for (let i = node.outputs.length - 1; i >= activeOutputCount; i -= 1) {
        if (typeof node.removeOutput === "function") {
          try { node.removeOutput(i); } catch (_e) { /* best-effort */ }
        } else {
          node.outputs.splice(i, 1);
        }
      }
    }
  } else {
    applyTypedSocketLabels(node.inputs, meta.typedInputs);
    applyTypedSocketLabels(node.outputs, meta.typedOutputs);
  }
  node.__vibecomfyIntentMeta = meta;
  return true;
}

function drawIntentBadge(ctx, node) {
  if (!ctx || typeof ctx.fillText !== "function") {
    return;
  }
  const meta = node?.__vibecomfyIntentMeta || readIntentMetadata(node);
  if (!meta.classType) {
    return;
  }
  if (node?.flags?.collapsed) {
    // Title bar is rendered differently when collapsed; skip to avoid clutter.
    return;
  }
  const badge = buildIntentBadge(meta);
  const width = readNodeSize(node, 180, 100).w;
  const style = styleForIntentMeta(meta);
  const titleHeight = (typeof globalThis !== "undefined"
    && Number(globalThis.LiteGraph?.NODE_TITLE_HEIGHT)) || 30;
  if (typeof ctx.save === "function") {
    ctx.save();
  }
  try {
    // Draw the badge as a right-aligned chip in the title bar (negative y is the
    // title strip above the node body), so it never overlaps the input slot rows.
    ctx.font = "bold 11px monospace";
    let textW = badge.length * 7.25;
    if (typeof ctx.measureText === "function") {
      const measured = ctx.measureText(badge);
      if (measured && typeof measured.width === "number") {
        textW = measured.width;
      }
    }
    const padX = 6;
    const chipH = 16;
    const chipW = Math.min(Math.max(width - 16, 0), textW + padX * 2);
    const chipX = Math.max(8, width - chipW - 8);
    const chipY = -titleHeight + (titleHeight - chipH) / 2;
    ctx.fillStyle = style.boxcolor;
    if (typeof ctx.fillRect === "function") {
      ctx.fillRect(chipX, chipY, chipW, chipH);
    }
    ctx.fillStyle = "#111418";
    const priorBaseline = ctx.textBaseline;
    ctx.textBaseline = "middle";
    ctx.fillText(badge, chipX + padX, chipY + chipH / 2 + 0.5);
    ctx.textBaseline = priorBaseline;
  } finally {
    if (typeof ctx.restore === "function") {
      ctx.restore();
    }
  }
}

function patchIntentNodePrototype(nodeType, nodeData) {
  const proto = nodeType?.prototype;
  const classType = String(nodeData?.name || nodeData?.type || "").trim();
  if (!proto || !isIntentClassType(classType) || proto.__vibecomfyIntentPatched === classType) {
    return;
  }
  proto.__vibecomfyIntentPatched = classType;

  const originalCreated = proto.onNodeCreated;
  proto.onNodeCreated = function patchedIntentNodeCreated(...args) {
    const result = typeof originalCreated === "function" ? originalCreated.apply(this, args) : undefined;
    this.type = this.type || classType;
    // Seed default execution mode for code nodes (one-shot hydrate).
    if (classType === "vibecomfy.code") {
      const props = this.properties && typeof this.properties === "object" ? this.properties : {};
      this.properties = props;
      const vc = props.vibecomfy && typeof props.vibecomfy === "object" ? props.vibecomfy : {};
      if (!props.vibecomfy || typeof props.vibecomfy !== "object") {
        props.vibecomfy = vc;
      }
      const rt = vc.runtime && typeof vc.runtime === "object" ? vc.runtime : {};
      if (!vc.runtime || typeof vc.runtime !== "object") {
        vc.runtime = rt;
      }
      if (!rt.execution_mode) {
        const defaultMode = getDefaultExecutionMode();
        rt.execution_mode = defaultMode;
        // Hydrate the widget property as well if empty.
        if (!props.execution_mode) {
          props.execution_mode = defaultMode;
        }
        if (defaultMode === "unrestricted") {
          rt.unrestricted_ack = true;
        }
      }
    }
    normalizeForDisplay(this, classType);
    return result;
  };

  const originalConfigure = proto.onConfigure;
  proto.onConfigure = function patchedIntentNodeConfigure(...args) {
    const result = typeof originalConfigure === "function" ? originalConfigure.apply(this, args) : undefined;
    this.type = this.type || classType;
    normalizeForDisplay(this, classType);
    return result;
  };

  const originalDrawForeground = proto.onDrawForeground;
  proto.onDrawForeground = function patchedIntentNodeDrawForeground(ctx, ...args) {
    const result = typeof originalDrawForeground === "function"
      ? originalDrawForeground.call(this, ctx, ...args)
      : undefined;
    this.type = this.type || classType;
    normalizeForDisplay(this, classType);
    drawIntentBadge(ctx, this);
    return result;
  };
}

function decorateIntentGraphPayload(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  for (const node of nodes) {
    normalizeExecNodeForSerialization(node);
    decorateIntentNode(node);
  }
  sanitizeSerializedGraphLinks(graph);
}

function prepareCandidateGraphForPanel(graph, runtimeApp = app) {
  if (!graph || typeof graph !== "object") {
    return graph;
  }
  const candidate = clonePlainData(graph);
  decorateIntentGraphPayload(candidate);
  // Server layout is deliberately deterministic, but it cannot know the
  // browser-only sizes of native/custom Comfy widgets.  Project this clone
  // through LiteGraph before both the overlay and delta apply consume it.
  return projectCandidateGraphToRuntimeLayout(runtimeApp, candidate);
}

function liveGraphNodeIndex(graph) {
  const byUid = new Map();
  const byId = new Map();
  for (const node of getLiveGraphNodes(graph)) {
    const uid = canonicalNodeUid(node);
    if (uid && !byUid.has(uid)) {
      byUid.set(uid, node);
    }
    if (node?.id !== null && node?.id !== undefined) {
      const idKey = String(node.id);
      if (!byId.has(idKey)) {
        byId.set(idKey, node);
      }
    }
  }
  return { byUid, byId };
}

function resolveLiveNodeFromCandidate(liveIndex, candidateNode) {
  if (!candidateNode) {
    return null;
  }
  const uid = canonicalNodeUid(candidateNode);
  if (uid && liveIndex.byUid.has(uid)) {
    return liveIndex.byUid.get(uid);
  }
  if (candidateNode.id !== null && candidateNode.id !== undefined) {
    return liveIndex.byId.get(String(candidateNode.id)) || null;
  }
  return null;
}

function cloneDynamicSlot(slot, index, direction) {
  const cloned = clonePlainData(slot) || {};
  cloned.name = cloned.name || `${direction}_${index}`;
  if (typeof cloned.serialize !== "function") {
    Object.defineProperty(cloned, "serialize", {
      enumerable: false,
      configurable: true,
      value() {
        const out = {};
        for (const [key, value] of Object.entries(this)) {
          if (typeof value !== "function") {
            out[key] = value;
          }
        }
        return out;
      },
    });
  }
  return cloned;
}

function replaceDynamicExecSlotsFromCandidate(liveNode, candidateNode) {
  if (!liveNode || !candidateNode || getIntentClassType(candidateNode) !== "vibecomfy.exec") {
    return false;
  }
  normalizeExecNodeForSerialization(candidateNode);
  decorateIntentNode(candidateNode);
  const candidateInputs = Array.isArray(candidateNode.inputs) ? candidateNode.inputs : [];
  const candidateOutputs = Array.isArray(candidateNode.outputs) ? candidateNode.outputs : [];
  if (!candidateInputs.length && !candidateOutputs.length) {
    return false;
  }
  liveNode.inputs = candidateInputs.map((slot, index) => cloneDynamicSlot(slot, index, "in"));
  liveNode.outputs = candidateOutputs.map((slot, index) => cloneDynamicSlot(slot, index, "out"));
  liveNode.widgets_values = clonePlainData(candidateNode.widgets_values || liveNode.widgets_values || []);
  liveNode.properties = {
    ...(liveNode.properties && typeof liveNode.properties === "object" ? liveNode.properties : {}),
    ...(clonePlainData(candidateNode.properties || {})),
  };
  decorateIntentNode(liveNode);
  return true;
}

function ensureLiveGraphLinkStore(graph) {
  if (!graph) {
    return null;
  }
  if (!graph.links || Array.isArray(graph.links) || typeof graph.links !== "object") {
    const rawLinks = Array.isArray(graph.links) ? graph.links : Object.values(graph.links || graph._links || {});
    graph.links = Object.fromEntries(
      rawLinks
        .map((link) => normalizeSerializedLinkRecord(link))
        .filter(Boolean)
        .map((link) => [String(link.id), { ...link }]),
    );
  }
  return graph.links;
}

function liveLinkStoreGet(linkStore, linkId) {
  if (!linkStore) {
    return null;
  }
  if (typeof linkStore.get === "function") {
    return linkStore.get(linkId) || linkStore.get(Number(linkId)) || linkStore.get(String(linkId)) || null;
  }
  return linkStore[String(linkId)] || null;
}

function liveLinkStoreSet(linkStore, linkId, link) {
  if (!linkStore) {
    return;
  }
  if (typeof linkStore.set === "function") {
    linkStore.set(linkId, link);
    return;
  }
  linkStore[String(linkId)] = link;
}

function liveLinkStoreValues(linkStore) {
  if (!linkStore) {
    return [];
  }
  if (typeof linkStore.values === "function") {
    return Array.from(linkStore.values()).filter(Boolean);
  }
  return Object.values(linkStore).filter(Boolean);
}

function liveLinkStoreKeys(linkStore) {
  if (!linkStore) {
    return [];
  }
  if (typeof linkStore.keys === "function") {
    return Array.from(linkStore.keys()).filter((id) => id !== null && id !== undefined);
  }
  return Object.keys(linkStore);
}

function removeCompatibleLiveLinkFromNetwork(network, linkId) {
  if (!network) {
    return;
  }
  if (Array.isArray(network.links)) {
    network.links = network.links.filter((entry) => String(entry?.id ?? entry?.[0]) !== String(linkId));
  } else if (network.links && typeof network.links.delete === "function") {
    network.links.delete(linkId);
    const numericId = Number(linkId);
    if (Number.isFinite(numericId)) {
      network.links.delete(numericId);
    }
    network.links.delete(String(linkId));
  } else if (network.links && typeof network.links === "object") {
    delete network.links[String(linkId)];
  }
  if (network._links && typeof network._links.delete === "function") {
    network._links.delete(linkId);
    const numericId = Number(linkId);
    if (Number.isFinite(numericId)) {
      network._links.delete(numericId);
    }
    network._links.delete(String(linkId));
  }
}

function liveLinkRecord(link) {
  const record = {
    id: link.id,
    origin_id: link.origin_id,
    origin_slot: Number(link.origin_slot),
    target_id: link.target_id,
    target_slot: Number(link.target_slot),
    type: link.type ?? null,
  };
  if (typeof record.asSerialisable !== "function") {
    Object.defineProperty(record, "asSerialisable", {
      enumerable: false,
      configurable: true,
      value() {
        return [
          this.id,
          this.origin_id,
          this.origin_slot,
          this.target_id,
          this.target_slot,
          this.type,
        ];
      },
    });
  }
  if (typeof record.disconnect !== "function") {
    Object.defineProperty(record, "disconnect", {
      enumerable: false,
      configurable: true,
      value(network) {
        removeCompatibleLiveLinkFromNetwork(network, this.id);
      },
    });
  }
  if (typeof record.serialize !== "function") {
    Object.defineProperty(record, "serialize", {
      enumerable: false,
      configurable: true,
      value() {
        return this.asSerialisable();
      },
    });
  }
  return record;
}

function restoreCandidateLinksOnLiveGraph(graph, candidateGraph) {
  const linkStore = ensureLiveGraphLinkStore(graph);
  if (!linkStore) {
    return 0;
  }
  const liveIndex = liveGraphNodeIndex(graph);
  const candidateIndex = buildGraphNodeIndex(candidateGraph);
  const restoredIds = new Set();
  let restored = 0;
  for (const link of normalizedSerializedLinks(candidateGraph)) {
    const candidateSource = candidateIndex.byId.get(String(link.origin_id));
    const candidateTarget = candidateIndex.byId.get(String(link.target_id));
    const sourceNode = resolveLiveNodeFromCandidate(liveIndex, candidateSource);
    const targetNode = resolveLiveNodeFromCandidate(liveIndex, candidateTarget);
    if (!sourceNode || !targetNode) {
      continue;
    }
    const sourceSlot = Array.isArray(sourceNode.outputs) ? sourceNode.outputs[link.origin_slot] : null;
    const targetSlot = Array.isArray(targetNode.inputs) ? targetNode.inputs[link.target_slot] : null;
    if (!sourceSlot || !targetSlot) {
      continue;
    }
    const idKey = String(link.id);
    const existing = liveLinkStoreGet(linkStore, link.id);
    if (
      existing
      && String(existing.origin_id) === String(sourceNode.id)
      && Number(existing.origin_slot) === Number(link.origin_slot)
      && String(existing.target_id) === String(targetNode.id)
      && Number(existing.target_slot) === Number(link.target_slot)
    ) {
      if (typeof existing.asSerialisable !== "function") {
        liveLinkStoreSet(linkStore, link.id, liveLinkRecord(existing));
      }
      restoredIds.add(idKey);
      continue;
    }
    liveLinkStoreSet(linkStore, link.id, liveLinkRecord({
      id: link.id,
      origin_id: sourceNode.id,
      origin_slot: Number(link.origin_slot),
      target_id: targetNode.id,
      target_slot: Number(link.target_slot),
      type: link.type ?? targetSlot.type ?? sourceSlot.type ?? null,
    }));
    restoredIds.add(idKey);
    restored += 1;
  }

  const linkValues = liveLinkStoreValues(linkStore);
  const activeIds = new Set(liveLinkStoreKeys(linkStore).map((id) => String(id)));
  for (const node of getLiveGraphNodes(graph)) {
    if (Array.isArray(node.inputs)) {
      node.inputs.forEach((input, index) => {
        const link = linkValues.find(
          (entry) => String(entry.target_id) === String(node.id) && Number(entry.target_slot) === index,
        );
        input.link = link ? link.id : null;
      });
    }
    if (Array.isArray(node.outputs)) {
      node.outputs.forEach((output, index) => {
        const links = linkValues
          .filter((entry) => String(entry.origin_id) === String(node.id) && Number(entry.origin_slot) === index)
          .map((entry) => entry.id)
          .filter((id) => activeIds.has(String(id)));
        output.links = links.length ? links : null;
      });
    }
  }
  const maxLinkId = liveLinkStoreKeys(linkStore)
    .map((id) => Number(id))
    .filter((id) => Number.isFinite(id))
    .reduce((max, id) => Math.max(max, id), 0);
  if (maxLinkId && (!Number.isFinite(Number(graph.last_link_id)) || Number(graph.last_link_id) < maxLinkId)) {
    graph.last_link_id = maxLinkId;
  }
  return restored;
}

function repairLiveIntentNodesFromCandidate(candidateGraph = null) {
  const graph = getLiveGraph();
  if (candidateGraph && typeof candidateGraph === "object") {
    const liveIndex = liveGraphNodeIndex(graph);
    const candidateNodes = Array.isArray(candidateGraph.nodes) ? candidateGraph.nodes : [];
    for (const candidateNode of candidateNodes) {
      if (getIntentClassType(candidateNode) !== "vibecomfy.exec") {
        continue;
      }
      const liveNode = resolveLiveNodeFromCandidate(liveIndex, candidateNode);
      replaceDynamicExecSlotsFromCandidate(liveNode, candidateNode);
    }
    restoreCandidateLinksOnLiveGraph(graph, candidateGraph);
  }
  for (const node of getLiveGraphNodes(graph)) {
    decorateIntentNode(node);
  }
}



function canonicalNodeUid(node) {
  if (!node || typeof node !== "object") {
    return null;
  }
  const properties = node.properties && typeof node.properties === "object" ? node.properties : null;
  const candidates = [
    properties?.vibecomfy_uid,
    properties?.uid,
    node.vibecomfy_uid,
    node.uid,
    node.id,
  ];
  for (const candidate of candidates) {
    if (candidate === null || candidate === undefined) {
      continue;
    }
    const normalized = String(candidate).trim();
    if (normalized) {
      return normalized;
    }
  }
  return null;
}

function buildGraphNodeIndex(graph) {
  const byUid = new Map();
  const byId = new Map();
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  for (const node of nodes) {
    const uid = canonicalNodeUid(node);
    if (uid && !byUid.has(uid)) {
      byUid.set(uid, node);
    }
    if (node?.id !== null && node?.id !== undefined) {
      const key = String(node.id);
      if (!byId.has(key)) {
        byId.set(key, node);
      }
    }
  }
  return { byUid, byId };
}

function resolveGraphNode(graph, uidOrId) {
  if (uidOrId === null || uidOrId === undefined || uidOrId === "") {
    return null;
  }
  const index = buildGraphNodeIndex(graph);
  const key = String(uidOrId);
  return index.byUid.get(key) || index.byId.get(key) || null;
}

function resolveGraphTarget(target) {
  if (Array.isArray(target)) {
    const scope = target[0];
    const uidOrId = target.length > 1 ? target[1] : null;
    const rest = target.length > 2 ? target.slice(2) : [];
    const scopePath = Array.isArray(scope)
      ? scope.map((entry) => String(entry))
      : (scope === null || scope === undefined ? [] : [String(scope)]);
    return { scopePath, uidOrId, rest };
  }
  if (target && typeof target === "object") {
    const scopePath = Array.isArray(target.scope_path)
      ? target.scope_path.map((entry) => String(entry))
      : (target.scope_path === null || target.scope_path === undefined || target.scope_path === ""
        ? []
        : [String(target.scope_path)]);
    const uidOrId = target.uid ?? target.id ?? null;
    return { scopePath, uidOrId, rest: [] };
  }
  return { scopePath: [], uidOrId: target ?? null, rest: [] };
}

function resolveNamedSlotIndex(slots, ref) {
  if (!Array.isArray(slots)) {
    return -1;
  }
  if (typeof ref === "number" && Number.isInteger(ref)) {
    return ref >= 0 && ref < slots.length ? ref : -1;
  }
  const normalized = String(ref);
  for (let index = 0; index < slots.length; index += 1) {
    const slot = slots[index];
    if (String(slot?.name) === normalized || String(slot?.label) === normalized || String(index) === normalized) {
      return index;
    }
  }
  return -1;
}

function readNodeFieldValue(node, fieldPath, { referenceNode = null } = {}) {
  if (!node || !Array.isArray(fieldPath) || fieldPath.length === 0) {
    return undefined;
  }
  const [head, ...rest] = fieldPath;
  if (head === "widgets_values") {
    const index = Number(rest[0]);
    return Array.isArray(node.widgets_values) ? clonePlainData(node.widgets_values[index]) : undefined;
  }
  if (head === "widgets") {
    const slotIndex = resolveNamedSlotIndex(node.widgets, rest[0]);
    if (slotIndex < 0) {
      return undefined;
    }
    const widget = Array.isArray(node.widgets) ? node.widgets[slotIndex] : undefined;
    if (rest.length <= 1) {
      return clonePlainData(widget);
    }
    return clonePlainData(widget?.[rest[1]]);
  }
  if (head === "inputs" || head === "outputs") {
    const slotIndex = resolveNamedSlotIndex(node[head], rest[0]);
    if (slotIndex < 0) {
      return undefined;
    }
    const slot = Array.isArray(node[head]) ? node[head][slotIndex] : undefined;
    if (rest.length <= 1) {
      return clonePlainData(slot);
    }
    return clonePlainData(slot?.[rest[1]]);
  }
  if (Object.prototype.hasOwnProperty.call(node, head)) {
    return clonePlainData(node[head]);
  }
  if (node.properties && Object.prototype.hasOwnProperty.call(node.properties, head)) {
    return clonePlainData(node.properties[head]);
  }
  const widgetIndex = resolveNamedSlotIndex(node.widgets, head);
  if (widgetIndex >= 0) {
    if (Array.isArray(node.widgets_values) && widgetIndex < node.widgets_values.length) {
      return clonePlainData(node.widgets_values[widgetIndex]);
    }
    return clonePlainData(node.widgets?.[widgetIndex]?.value);
  }
  // ComfyUI's serialized graph normally contains widgets_values but omits
  // the native node's widgets descriptors. Resolve semantic field names
  // (for example KSampler.denoise) through the live carrier, then read the
  // value at that same serialized index. This is the same representation
  // bridge used by canonical delta preflight.
  const referenceWidgetIndex = resolveNamedSlotIndex(referenceNode?.widgets, head);
  if (referenceWidgetIndex >= 0) {
    if (Array.isArray(node.widgets_values) && referenceWidgetIndex < node.widgets_values.length) {
      return clonePlainData(node.widgets_values[referenceWidgetIndex]);
    }
    return clonePlainData(referenceNode?.widgets?.[referenceWidgetIndex]?.value);
  }
  return undefined;
}

function readNodeLinkSource(graph, targetRef) {
  const parsed = resolveGraphTarget(targetRef);
  const targetNode = resolveGraphNode(graph, parsed.uidOrId);
  if (!targetNode) {
    return { sentinel: "link_absent" };
  }
  const targetSlotRef = parsed.rest[0];
  const targetSlotIndex = resolveNamedSlotIndex(targetNode.inputs, targetSlotRef);
  if (targetSlotIndex < 0) {
    return { sentinel: "link_absent" };
  }
  const links = Array.isArray(graph?.links) ? graph.links : [];
  for (const link of links) {
    if (!Array.isArray(link) || link.length < 5) {
      continue;
    }
    if (String(link[3]) !== String(targetNode.id) || Number(link[4]) !== targetSlotIndex) {
      continue;
    }
    const sourceNode = resolveGraphNode(graph, link[1]);
    return {
      uid: canonicalNodeUid(sourceNode) || String(link[1]),
      output_slot: Number(link[2]),
    };
  }
  return { sentinel: "link_absent" };
}

function readGraphActualForOp(graph, op, { widgetReferenceNodeFor = null } = {}) {
  if (!op || typeof op !== "object") {
    return undefined;
  }
  if (op.op === "set_node_field") {
    const parsed = resolveGraphTarget(op.target);
    const node = resolveGraphNode(graph, parsed.uidOrId);
    const referenceNode = typeof widgetReferenceNodeFor === "function"
      ? widgetReferenceNodeFor(parsed.uidOrId)
      : null;
    return readNodeFieldValue(node, decodeNodeFieldPathV1(parsed.rest), { referenceNode });
  }
  if (op.op === "set_mode") {
    const parsed = resolveGraphTarget(op.target);
    const node = resolveGraphNode(graph, parsed.uidOrId);
    return node?.mode ?? 0;
  }
  if (op.op === "reorder") {
    const parsed = resolveGraphTarget(op.target);
    const node = resolveGraphNode(graph, parsed.uidOrId);
    if (!node) {
      return undefined;
    }
    if (op.axis === "widgets") {
      return Array.isArray(node.widgets) ? node.widgets.map((widget) => widget?.name ?? widget?.label ?? null) : [];
    }
    if (op.axis === "inputs" || op.axis === "outputs") {
      return Array.isArray(node[op.axis]) ? node[op.axis].map((slot) => slot?.name ?? slot?.label ?? null) : [];
    }
    return undefined;
  }
  if (op.op === "upsert_link" || op.op === "remove_link") {
    return readNodeLinkSource(graph, op.to || op.target);
  }
  if (op.op === "add_node" || op.op === "remove_node") {
    const nodeRef = op.target ?? [
      Array.isArray(op.scope_path) ? op.scope_path : (op.scope_path ?? ""),
      typeof op.uid === "string" && op.uid
        ? op.uid
        : (typeof op.node_id === "string" && op.node_id ? op.node_id : op.scope_path),
    ];
    const parsed = resolveGraphTarget(nodeRef);
    const node = resolveGraphNode(graph, parsed.uidOrId);
    if (!node) {
      return { sentinel: "node_absent" };
    }
    return {
      uid: canonicalNodeUid(node) || String(parsed.uidOrId),
      id: node.id ?? null,
      type: node.type ?? null,
    };
  }
  return undefined;
}

function valuesSemanticallyEqual(left, right) {
  return canonicalJsonString(left) === canonicalJsonString(right);
}

function normalizeScopedAcceptVerification(accepted) {
  const raw = accepted?.raw && typeof accepted.raw === "object" ? accepted.raw : accepted;
  const scoped = raw?.scoped_accept_verification;
  if (!scoped || typeof scoped !== "object" || !Array.isArray(scoped.entries)) {
    return null;
  }
  return {
    ok: scoped.ok !== false,
    entries: scoped.entries.map((entry) => clonePlainData(entry)),
  };
}

function resolveScopedDeltaOps(panel, accepted) {
  const echoed = normalizeDeltaOpsFromSubmit(accepted?.raw || accepted);
  if (Array.isArray(echoed)) {
    return { deltaOps: echoed, source: "accept_echo" };
  }
  if (Array.isArray(panel?.state?.deltaOps)) {
    return { deltaOps: clonePlainData(panel.state.deltaOps), source: "submit_state" };
  }
  return { deltaOps: null, source: "none" };
}

function validateScopedCanvasPreconditions(graph, deltaOps, scopedVerification, options = {}) {
  const entries = [];
  const serverEntries = Array.isArray(scopedVerification?.entries) ? scopedVerification.entries : [];
  for (let index = 0; index < deltaOps.length; index += 1) {
    const op = deltaOps[index];
    const serverEntry = serverEntries[index] && typeof serverEntries[index] === "object" ? serverEntries[index] : {};
    const actualBefore = readGraphActualForOp(graph, op, options);
    const expectedOld = Object.prototype.hasOwnProperty.call(serverEntry, "expected_old")
      ? serverEntry.expected_old
      : undefined;
    const desiredNew = Object.prototype.hasOwnProperty.call(serverEntry, "desired_new")
      ? serverEntry.desired_new
      : op.value;
    const matchesExpected = valuesSemanticallyEqual(actualBefore, expectedOld);
    const matchesDesired = valuesSemanticallyEqual(actualBefore, desiredNew);
    const status = matchesExpected ? "ok" : (matchesDesired ? "already_applied" : "conflict");
    entries.push({
      op: op.op,
      target: clonePlainData(serverEntry.target ?? op.target ?? op.to ?? null),
      expected_old: clonePlainData(expectedOld),
      actual_before: clonePlainData(actualBefore),
      desired_new: clonePlainData(desiredNew),
      server_status: serverEntry.status ?? null,
      status,
    });
  }
  return {
    ok: entries.every((entry) => entry.status === "ok" || entry.status === "already_applied"),
    entries,
  };
}

function verifyScopedCanvasResults(graph, deltaOps, scopedVerification, options = {}) {
  const entries = [];
  const serverEntries = Array.isArray(scopedVerification?.entries) ? scopedVerification.entries : [];
  for (let index = 0; index < deltaOps.length; index += 1) {
    const op = deltaOps[index];
    const serverEntry = serverEntries[index] && typeof serverEntries[index] === "object" ? serverEntries[index] : {};
    const actualAfter = readGraphActualForOp(graph, op, options);
    const desiredNew = Object.prototype.hasOwnProperty.call(serverEntry, "desired_new")
      ? serverEntry.desired_new
      : op.value;
    entries.push({
      op: op.op,
      target: clonePlainData(serverEntry.target ?? op.target ?? op.to ?? null),
      desired_new: clonePlainData(desiredNew),
      actual_after: clonePlainData(actualAfter),
      ok: valuesSemanticallyEqual(actualAfter, desiredNew),
    });
  }
  return {
    ok: entries.every((entry) => entry.ok),
    entries,
  };
}

function buildCanvasApplyVerificationDebug(canvasApplyMeta) {
  if (!canvasApplyMeta || typeof canvasApplyMeta !== "object") {
    return null;
  }
  const debug = {};
  if (Object.prototype.hasOwnProperty.call(canvasApplyMeta, "scoped_accept_verification")) {
    debug.scoped_accept_verification = clonePlainData(canvasApplyMeta.scoped_accept_verification);
  }
  if (Object.prototype.hasOwnProperty.call(canvasApplyMeta, "local_precheck")) {
    debug.local_precheck = clonePlainData(canvasApplyMeta.local_precheck);
  }
  if (Object.prototype.hasOwnProperty.call(canvasApplyMeta, "local_postcheck")) {
    debug.local_postcheck = clonePlainData(canvasApplyMeta.local_postcheck);
  }
  if (Object.prototype.hasOwnProperty.call(canvasApplyMeta, "rollback")) {
    debug.rollback = clonePlainData(canvasApplyMeta.rollback);
  }
  return Object.keys(debug).length > 0 ? debug : null;
}

function normalizeSerializedLinkRecord(link) {
  if (Array.isArray(link)) {
    if (link.length < 5) {
      return null;
    }
    return {
      id: link[0],
      origin_id: link[1],
      origin_slot: Number(link[2]),
      target_id: link[3],
      target_slot: Number(link[4]),
      type: link.length > 5 ? link[5] : null,
    };
  }
  if (!link || typeof link !== "object") {
    return null;
  }
  const id = link.id ?? link.link_id ?? null;
  const originId = link.origin_id ?? link.from_id ?? link.from ?? null;
  const originSlot = link.origin_slot ?? link.from_slot ?? link.originIndex ?? null;
  const targetId = link.target_id ?? link.to_id ?? link.to ?? null;
  const targetSlot = link.target_slot ?? link.to_slot ?? link.targetIndex ?? null;
  if (id === null || originId === null || originSlot === null || targetId === null || targetSlot === null) {
    return null;
  }
  return {
    id,
    origin_id: originId,
    origin_slot: Number(originSlot),
    target_id: targetId,
    target_slot: Number(targetSlot),
    type: link.type ?? link.link_type ?? null,
  };
}

function normalizedSerializedLinks(graph) {
  const rawLinks = Array.isArray(graph?.links)
    ? graph.links
    : Object.values(graph?.links || {});
  return rawLinks.map((link) => normalizeSerializedLinkRecord(link)).filter(Boolean);
}

function findSerializedLinkByTarget(graph, targetRef) {
  const parsed = resolveGraphTarget(targetRef);
  const targetNode = resolveGraphNode(graph, parsed.uidOrId);
  if (!targetNode) {
    return null;
  }
  const targetSlotIndex = resolveNamedSlotIndex(targetNode.inputs, parsed.rest[0]);
  if (targetSlotIndex < 0) {
    return null;
  }
  return normalizedSerializedLinks(graph).find(
    (link) => String(link.target_id) === String(targetNode.id) && Number(link.target_slot) === targetSlotIndex,
  ) || null;
}

function nodeTargetRefForRollback(op) {
  if (Array.isArray(op?.target) || (op?.target && typeof op.target === "object")) {
    return clonePlainData(op.target);
  }
  // Root-scoped canonical add_node ops persist scope_path as the empty string.
  // Empty scope is location, not identity; choosing it before uid made inverse
  // rollback target "" and left the newly-added node on the canvas.
  const identity = [op?.uid, op?.node_id, op?.id, op?.scope_path]
    .find((value) => value !== null && value !== undefined && String(value) !== "");
  return ["nodes", identity ?? ""];
}

export function buildInverseDeltaOps(preApplyGraph, deltaOps) {
  return applyFlow.buildInverseDeltaOps(preApplyGraph, deltaOps, {
    uidForUpsertLinkOrigin(priorLink) {
      return canonicalNodeUid(resolveGraphNode(preApplyGraph, priorLink.origin_id));
    },
    uidForUpsertLinkTarget(priorLink) {
      return canonicalNodeUid(resolveGraphNode(preApplyGraph, priorLink.target_id));
    },
    uidForRemovedLinkOrigin(priorLink) {
      return canonicalNodeUid(resolveGraphNode(preApplyGraph, priorLink.origin_id));
    },
    uidForRemovedLinkTarget(priorLink) {
      return canonicalNodeUid(resolveGraphNode(preApplyGraph, priorLink.target_id));
    },
    uidForRemovedNode(priorNode) {
      return canonicalNodeUid(priorNode);
    },
    relatedLinksFor() {
      return normalizedSerializedLinks(preApplyGraph);
    },
    uidForRelatedLinkOrigin(link) {
      return canonicalNodeUid(resolveGraphNode(preApplyGraph, link.origin_id));
    },
    uidForRelatedLinkTarget(link) {
      return canonicalNodeUid(resolveGraphNode(preApplyGraph, link.target_id));
    },
  });
}

let graphLoadScopeSwitchSuppressionDepth = 0;

function loadGraphDataWithoutScopeSwitch(graph, ...args) {
  graphLoadScopeSwitchSuppressionDepth += 1;
  const finish = () => {
    graphLoadScopeSwitchSuppressionDepth = Math.max(0, graphLoadScopeSwitchSuppressionDepth - 1);
  };
  try {
    const result = app.loadGraphData(graph, ...args);
    if (result && typeof result.then === "function") {
      return Promise.resolve(result).finally(finish);
    }
    finish();
    return result;
  } catch (error) {
    finish();
    throw error;
  }
}

function syncPanelScopeAfterGraphLoad() {
  if (graphLoadScopeSwitchSuppressionDepth > 0) {
    return;
  }
  const panel = currentAgentPanel();
  if (!panel?.state) {
    return;
  }
  const canvasScope = resolveActiveCanvasScope();
  const scopeId = canvasScope?.scopeId || null;
  const fingerprint = canvasScope?.fingerprint || null;
  const currentScopeId = panel.state.chatScopeId || null;
  const currentFingerprint = panel.state.chatScopeFingerprint || null;
  if (currentScopeId === scopeId && currentFingerprint === fingerprint) {
    return;
  }
  if (scopeId && currentScopeId === scopeId) {
    // The Comfy workflow UUID owns conversation identity. Loading a changed
    // graph into that same workflow advances revision/precondition evidence;
    // it must not run the destructive workflow-switch transition.
    transition(panel, "SCOPE_REVISION", {
      scopeId,
      fingerprint,
      debugPayload: {
        reason: "load_graph_data_scope_revision",
        previousFingerprint: currentFingerprint,
        newFingerprint: fingerprint,
      },
    });
    return;
  }
  const obligations = transition(panel, "SCOPE_SWITCH", {
    scopeId,
    fingerprint,
    debugPayload: {
      reason: "load_graph_data_scope_switch",
      previousScopeId: panel.state.chatScopeId || null,
      previousFingerprint: panel.state.chatScopeFingerprint || null,
      newScopeId: scopeId,
      newFingerprint: fingerprint,
    },
  });
  fulfillLifecycleTransitionObligations(panel, obligations);
  renderLifecycleTransition(panel, obligations);
}

function installIntentNodeFallback() {
  if (app.__vibecomfyIntentFallbackInstalled) {
    return;
  }
  const originalLoadGraphData = app?.loadGraphData;
  if (typeof originalLoadGraphData !== "function") {
    return;
  }
  app.loadGraphData = function vibecomfyIntentLoadGraphData(nextGraph, ...args) {
    normalizeForApply(nextGraph);
    const repairCandidate = clonePlainData(nextGraph);
    const result = originalLoadGraphData.call(this, nextGraph, ...args);
    if (result && typeof result.then === "function") {
      return result.then((value) => {
        repairLiveNodes(repairCandidate);
        syncPanelScopeAfterGraphLoad();
        return value;
      });
    }
    repairLiveNodes(repairCandidate);
    syncPanelScopeAfterGraphLoad();
    return result;
  };
  app.__vibecomfyIntentFallbackInstalled = true;
}

function installGraphConfigureIntentFallback() {
  const graph = getLiveGraph();
  if (!graph || graph.__vibecomfyIntentConfigureFallbackInstalled) {
    return;
  }
  const originalConfigure = graph.configure;
  if (typeof originalConfigure !== "function") {
    return;
  }
  graph.configure = function vibecomfyIntentGraphConfigure(nextGraph, ...args) {
    normalizeForApply(nextGraph);
    const repairCandidate = clonePlainData(nextGraph);
    const result = originalConfigure.call(this, nextGraph, ...args);
    if (result && typeof result.then === "function") {
      return result.then((value) => {
        repairLiveNodes(repairCandidate);
        syncPanelScopeAfterGraphLoad();
        return value;
      });
    }
    repairLiveNodes(repairCandidate);
    syncPanelScopeAfterGraphLoad();
    return result;
  };
  graph.__vibecomfyIntentConfigureFallbackInstalled = true;
}

function installAgentPreviewOverlay() {
  installAgentPreviewOverlayImpl(app, {
    PANEL_STATE,
    captureLiveCanvasRevision,
    currentAgentPanel,
    drawPreviewOverlay: panelOverlayDrawPreviewOverlay,
    getLiveGraph,
    getLiveGraphNodes,
    getUid,
    getOrBuildPreviewDiff,
    graphNodeCount: _graphNodeCount,
    hexToRgba,
    readNodeBounding,
    readNodePos,
    readNodeSize,
    readWidgetValues,
    VC_COLORS,
    vecNumber,
    widgetValuePreviewText,
  });
}

async function checkFrontendVersion() {
  let version = "unknown";
  try {
    const res = await fetch("/system_stats");
    const stats = await res.json();
    version = stats?.system?.comfyui_frontend_package || "unknown";
  } catch (e) {
    version = "unknown";
  }
  const major = SUPPORTED_FRONTEND.split(".").slice(0, 2).join(".");
  if (version === "unknown" || !String(version).startsWith(major)) {
    console.warn(`VibeComfy: frontend version ${version} outside supported range, activating anyway`);
  }
}

function errorModal(err) {
  const kind = err?.kind || "Error";
  const message = err?.message || err?.error || String(err);
  const overlay = makeOverlay();
  const box = makeBox(overlay);
  box.appendChild(el("h3", `${kind}: ${message}`));
  const close = button("Close", () => overlay.remove());
  box.appendChild(close);
}

function clearNode(node) {
  while (node.children.length) {
    node.removeChild(node.children[0]);
  }
}

function appendChildOnce(parent, child) {
  if (!parent || !child) {
    return child;
  }
  if (child.parentNode && typeof child.parentNode.removeChild === "function") {
    child.parentNode.removeChild(child);
  }
  return parent.appendChild(child);
}

function panelSection(id, title) {
  const section = el("section");
  section.id = id;
  section.className = "vibecomfy-agent-panel-region";
  Object.assign(section.style, {
    border: "1px solid #34343a",
    borderRadius: "6px",
    background: "#17171c",
    padding: "10px",
    display: "grid",
    gap: "8px",
    minWidth: "0",
    maxWidth: "100%",
    overflow: "hidden",
  });

  const heading = el("div", title);
  Object.assign(heading.style, {
    fontSize: "11px",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#9da1ac",
    fontWeight: "600",
  });
  if (!title) {
    heading.style.display = "none";
  }

  const body = el("div");
  body.className = "vibecomfy-agent-panel-region-body";
  Object.assign(body.style, {
    display: "grid",
    gap: "6px",
    fontSize: "12px",
    lineHeight: "1.4",
    minWidth: "0",
    maxWidth: "100%",
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  });

  section.appendChild(heading);
  section.appendChild(body);
  return { section, body };
}

function muted(text) {
  const node = el("div", text);
  node.style.color = "#8d93a1";
  return node;
}

function labelValue(label, value) {
  const node = el("div");
  const key = el("span", `${label}: `);
  key.style.color = "#9da1ac";
  const val = el("span", value);
  val.style.color = "#f3f5f7";
  node.appendChild(key);
  node.appendChild(val);
  return node;
}

function setVisible(node, visible, display = "") {
  node.style.display = visible ? display : "none";
}

function setButtonEmphasis(buttonNode, visible, tone) {
  setVisible(buttonNode, visible, "inline-flex");
  buttonNode.style.opacity = visible ? "1" : "0";
  if (tone === "primary") {
    buttonNode.style.background = "#f47f18";
    buttonNode.style.borderColor = "#f47f18";
    buttonNode.style.color = "#fff4ea";
  } else if (tone === "danger") {
    buttonNode.style.background = "#642323";
    buttonNode.style.borderColor = "#8f4747";
    buttonNode.style.color = "#ffd7d7";
  } else {
    buttonNode.style.background = "#272b33";
    buttonNode.style.borderColor = "#414855";
    buttonNode.style.color = "#edf2f7";
  }
}

function appendTextLine(target, text, color = "#edf2f7") {
  const node = el("div", text);
  node.style.color = color;
  node.style.minWidth = "0";
  node.style.overflowWrap = "anywhere";
  target.appendChild(node);
}

function appendCodeLine(target, text, color = "#b9ffcc") {
  const node = el("code", text);
  Object.assign(node.style, {
    color,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontSize: "11px",
  });
  target.appendChild(node);
}

function safeJson(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch (e) {
    return String(value);
  }
}

function scrubDebugPayload(value, depth = 0) {
  if (value == null || typeof value !== "object") {
    return value;
  }
  if (depth > 5) {
    return "[truncated]";
  }
  if (Array.isArray(value)) {
    if (value.length > 50) {
      return {
        kind: "array",
        length: value.length,
        preview: value.slice(0, 8).map((item) => scrubDebugPayload(item, depth + 1)),
      };
    }
    return value.map((item) => scrubDebugPayload(item, depth + 1));
  }
  const result = {};
  for (const [key, entry] of Object.entries(value)) {
    if (key === "graph" || key === "candidate" || key === "candidate_graph") {
      const graph = key === "candidate" && entry?.graph ? entry.graph : entry;
      result[key] = {
        graph_omitted: true,
        node_count: Array.isArray(graph?.nodes) ? graph.nodes.length : null,
        link_count: Array.isArray(graph?.links) ? graph.links.length : null,
      };
      continue;
    }
    if (key === "raw_payload" && entry && typeof entry === "object") {
      result[key] = scrubDebugPayload({
        ok: entry.ok,
        kind: entry.kind,
        stage: entry.stage,
        session_id: entry.session_id,
        turn_id: entry.turn_id,
        candidate_graph_hash: entry.candidate_graph_hash,
        audit_ref: entry.audit_ref,
        apply_eligibility: entry.apply_eligibility,
        rebaseline_recovery: entry.rebaseline_recovery,
      }, depth + 1);
      continue;
    }
    result[key] = scrubDebugPayload(entry, depth + 1);
  }
  return result;
}

function compactDetailsPreview(value) {
  if (value == null || typeof value !== "object") {
    return "";
  }
  const parts = [];
  const pushPart = (key, entry) => {
    if (parts.length >= 12) {
      return;
    }
    if (entry == null || typeof entry === "number" || typeof entry === "boolean") {
      parts.push(`${key}: ${String(entry)}; "${key}": ${String(entry)}`);
    } else if (typeof entry === "string") {
      const quoted = /(?:^|_)turn_id$|(?:^|_)id$/.test(key) ? ` (${JSON.stringify(entry)})` : "";
      parts.push(`${key}: ${entry}${quoted}`);
    } else if (Array.isArray(entry)) {
      parts.push(`${key}: [${entry.length}]`);
    } else if (entry && typeof entry === "object") {
      const message = entry.message || entry.user_facing_message || entry.path;
      if (typeof message === "string" && message) {
        parts.push(`${key}: ${message}`);
      } else {
        parts.push(`${key}: {...}`);
      }
    }
  };
  for (const [key, entry] of Object.entries(value)) {
    if (key === "graph" || key === "candidate_graph" || key === "candidate") {
      continue;
    }
    pushPart(key, entry);
    if (parts.length >= 8) {
      break;
    }
  }
  const wanted = new Set([
    "expected_structural_graph_hash",
    "expected_live_canvas_token",
    "expected_graph_hash",
    "expected_baseline_graph_hash",
    "rebaseline_response",
    "accept_response",
  ]);
  const visit = (node, depth = 0) => {
    if (!node || typeof node !== "object" || depth > 4 || parts.length >= 12) {
      return;
    }
    for (const [key, entry] of Object.entries(node)) {
      if (key === "graph" || key === "candidate_graph" || key === "candidate") {
        continue;
      }
      if (wanted.has(key) && !parts.some((part) => part.startsWith(`${key}:`))) {
        pushPart(key, entry);
      }
      if (entry && typeof entry === "object" && !Array.isArray(entry)) {
        visit(entry, depth + 1);
      }
    }
  };
  visit(value);
  return parts.join("; ");
}

function safePreviewLogDetail(value) {
  if (value == null) {
    return "";
  }
  if (typeof value === "string") {
    return value.length > 500 ? `${value.slice(0, 497)}...` : value;
  }
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }
  if (value instanceof Error) {
    const name = typeof value.name === "string" && value.name ? value.name : "Error";
    const message = typeof value.message === "string" ? value.message : "";
    return message ? `${name}: ${message}` : name;
  }
  if (Array.isArray(value)) {
    return `[array length=${value.length}]`;
  }
  if (typeof value === "object") {
    let keys = [];
    try {
      keys = Object.keys(value).slice(0, 6);
    } catch (_e) {
      keys = [];
    }
    const ctor = typeof value.constructor?.name === "string" && value.constructor.name
      ? value.constructor.name
      : "Object";
    return keys.length ? `[${ctor} keys=${keys.join(",")}]` : `[${ctor}]`;
  }
  return typeof value;
}

function isReorganiseLayoutPreviewCandidate(panel) {
  if (!panel?.state?.candidateGraph || typeof panel.state.candidateGraph !== "object") {
    return false;
  }
  const report = panel.state.candidateReport;
  if (!report || typeof report !== "object") {
    return false;
  }
  return report.kind === "reorganise" || report.route === "reorganise" || Boolean(report.reorganise);
}

function clearLayoutPreviewState(panel) {
  if (!panel?.state) {
    return;
  }
  delete panel.state._layoutPreviewActive;
  delete panel.state._layoutPreviewBaseline;
  delete panel.state._layoutPreviewCandidateGraphHash;
  delete panel.state._layoutPreviewTurnId;
  delete panel.state._layoutPreviewSessionId;
}

function layoutPreviewBaselineSnapshot(panel, fallbackSnapshot = null) {
  const baseline = panel?.state?._layoutPreviewBaseline;
  if (!baseline?.graph) {
    return fallbackSnapshot;
  }
  return {
    ...(fallbackSnapshot || {}),
    graph: clonePlainData(baseline.graph),
    graphHash: baseline.graphHash || fallbackSnapshot?.graphHash || null,
    structuralHash: baseline.structuralHash || fallbackSnapshot?.structuralHash || null,
    liveCanvasToken: baseline.liveCanvasToken || fallbackSnapshot?.liveCanvasToken || null,
    viewport: clonePlainData(baseline.viewport || null),
  };
}

const LAYOUT_PREVIEW_FIT_PADDING_PX = 80;
const LAYOUT_PREVIEW_FIT_MAX_SCALE = 1.0;

function resolveCanvasViewportDs({ create = false, preferredPath = null } = {}) {
  const canvas = app?.canvas;
  if (!canvas || typeof canvas !== "object") {
    return null;
  }
  const candidates = [
    { path: "canvas.ds", target: canvas },
    { path: "canvas.graphcanvas.ds", target: canvas.graphcanvas },
    { path: "canvas.graphCanvas.ds", target: canvas.graphCanvas },
  ].filter((entry) => entry.target && typeof entry.target === "object");
  if (preferredPath) {
    const preferred = candidates.find((entry) => entry.path === preferredPath && entry.target?.ds && typeof entry.target.ds === "object");
    if (preferred) {
      return { path: preferred.path, ds: preferred.target.ds };
    }
  }
  for (const entry of candidates) {
    if (entry.target?.ds && typeof entry.target.ds === "object") {
      return { path: entry.path, ds: entry.target.ds };
    }
  }
  if (create && candidates.length > 0) {
    candidates[0].target.ds = { scale: 1, offset: [0, 0] };
    return { path: candidates[0].path, ds: candidates[0].target.ds };
  }
  return null;
}

function captureCanvasViewportSnapshot() {
  const resolved = resolveCanvasViewportDs();
  const ds = resolved?.ds;
  if (!ds || typeof ds !== "object") {
    return null;
  }
  const scale = Number(ds.scale);
  const offset = Array.isArray(ds.offset) ? ds.offset : null;
  const offsetX = offset ? Number(offset[0]) : NaN;
  const offsetY = offset ? Number(offset[1]) : NaN;
  if (!Number.isFinite(scale) || scale <= 0 || !Number.isFinite(offsetX) || !Number.isFinite(offsetY)) {
    return null;
  }
  return {
    path: resolved.path,
    scale,
    offset: [offsetX, offsetY],
  };
}

function restoreCanvasViewportSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    return false;
  }
  const scale = Number(snapshot.scale);
  const offset = Array.isArray(snapshot.offset) ? snapshot.offset : null;
  const offsetX = offset ? Number(offset[0]) : NaN;
  const offsetY = offset ? Number(offset[1]) : NaN;
  if (!Number.isFinite(scale) || scale <= 0 || !Number.isFinite(offsetX) || !Number.isFinite(offsetY)) {
    return false;
  }
  const resolved = resolveCanvasViewportDs({ create: true, preferredPath: snapshot.path || null });
  const ds = resolved?.ds;
  if (!ds || typeof ds !== "object") {
    return false;
  }
  ds.scale = scale;
  if (!Array.isArray(ds.offset)) {
    ds.offset = [offsetX, offsetY];
  } else {
    ds.offset[0] = offsetX;
    ds.offset[1] = offsetY;
  }
  return true;
}

function canvasViewportPixelSize() {
  const canvas = app?.canvas;
  const element = canvas?.canvas || canvas?.ctx?.canvas || canvas?.canvasEl || null;
  const widthCandidates = [
    element?.width,
    element?.clientWidth,
    element?.offsetWidth,
    canvas?.width,
    canvas?.clientWidth,
    globalThis.window?.innerWidth,
  ];
  const heightCandidates = [
    element?.height,
    element?.clientHeight,
    element?.offsetHeight,
    canvas?.height,
    canvas?.clientHeight,
    globalThis.window?.innerHeight,
  ];
  const width = widthCandidates.map(Number).find((value) => Number.isFinite(value) && value > 0);
  const height = heightCandidates.map(Number).find((value) => Number.isFinite(value) && value > 0);
  if (!Number.isFinite(width) || !Number.isFinite(height)) {
    return null;
  }
  return { width, height };
}

function graphNodeBounds(graphPayload) {
  const nodes = Array.isArray(graphPayload?.nodes) ? graphPayload.nodes : [];
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  let count = 0;
  for (const node of nodes) {
    const pos = readNodePos(node, NaN, NaN);
    if (!Number.isFinite(pos.x) || !Number.isFinite(pos.y)) {
      continue;
    }
    const size = readNodeSize(node, 200, 100);
    const width = Number.isFinite(size.w) && size.w > 0 ? size.w : 200;
    const height = Number.isFinite(size.h) && size.h > 0 ? size.h : 100;
    minX = Math.min(minX, pos.x);
    minY = Math.min(minY, pos.y);
    maxX = Math.max(maxX, pos.x + width);
    maxY = Math.max(maxY, pos.y + height);
    count += 1;
  }
  if (count === 0) {
    return null;
  }
  return {
    x: minX,
    y: minY,
    w: Math.max(maxX - minX, 1),
    h: Math.max(maxY - minY, 1),
  };
}

function fitCanvasViewportToGraphPayload(graphPayload) {
  const resolved = resolveCanvasViewportDs();
  const size = canvasViewportPixelSize();
  const bounds = graphNodeBounds(graphPayload);
  if (!resolved?.ds || !size || !bounds) {
    return false;
  }
  const availableWidth = Math.max(1, size.width - LAYOUT_PREVIEW_FIT_PADDING_PX * 2);
  const availableHeight = Math.max(1, size.height - LAYOUT_PREVIEW_FIT_PADDING_PX * 2);
  const scale = Math.min(
    LAYOUT_PREVIEW_FIT_MAX_SCALE,
    availableWidth / bounds.w,
    availableHeight / bounds.h,
  );
  if (!Number.isFinite(scale) || scale <= 0) {
    return false;
  }
  const centerX = bounds.x + bounds.w / 2;
  const centerY = bounds.y + bounds.h / 2;
  const offsetX = (size.width / 2 / scale) - centerX;
  const offsetY = (size.height / 2 / scale) - centerY;
  resolved.ds.scale = scale;
  if (!Array.isArray(resolved.ds.offset)) {
    resolved.ds.offset = [offsetX, offsetY];
  } else {
    resolved.ds.offset[0] = offsetX;
    resolved.ds.offset[1] = offsetY;
  }
  return true;
}

function applyGraphForLayoutPreview(graphPayload, { repaint = true, fitViewport = false } = {}) {
  let repairCandidate = null;
  const result = applyGraphCandidateInPlace(app, clonePlainData(graphPayload), {
    beforeConfigure(nextCandidate) {
      decorateIntentGraphPayload(nextCandidate);
      repairCandidate = clonePlainData(nextCandidate);
    },
    afterConfigure(_graph, nextCandidate) {
      repairLiveIntentNodesFromCandidate(repairCandidate || nextCandidate);
    },
    repaint: fitViewport ? false : repaint,
  });
  if (fitViewport) {
    fitCanvasViewportToGraphPayload(graphPayload);
    if (repaint) {
      const adapter = createIntentGraphAdapter(app);
      adapter.notifyRevision();
      adapter.repaint();
    }
  }
  return result;
}

async function activateLayoutPreviewIfNeeded(panel, baselineSnapshot = null) {
  if (!isReorganiseLayoutPreviewCandidate(panel)) {
    return false;
  }
  if (!panel.state.candidateGraphHash) {
    return false;
  }
  if (
    panel.state._layoutPreviewActive
    && panel.state._layoutPreviewCandidateGraphHash === panel.state.candidateGraphHash
    && panel.state._layoutPreviewTurnId === panel.state.turnId
    && panel.state._layoutPreviewSessionId === panel.state.sessionId
  ) {
    return true;
  }
  if (panel.state._layoutPreviewActive) {
    restoreLayoutPreviewBaseline(panel, { repaint: false, clear: true });
  }

  const snapshot = baselineSnapshot || await buildCanvasSnapshot();
  panel.state._layoutPreviewBaseline = {
    graph: clonePlainData(snapshot.graph),
    graphHash: snapshot.graphHash || null,
    structuralHash: snapshot.structuralHash || null,
    liveCanvasToken: snapshot.liveCanvasToken || null,
    viewport: captureCanvasViewportSnapshot(),
  };
  // Non-destructive preview: do NOT swap the canvas to the candidate. Leave the
  // live graph at its original positions; the always-on AWAITING_REVIEW overlay
  // renders the already-computed layout_moved arrows (old position → new target)
  // on top. Invalidate the overlay draw-model cache + repaint so arrows appear.
  clearCandidateInvalidationSideEffects(true);
  panel.state._layoutPreviewActive = true;
  panel.state._layoutPreviewCandidateGraphHash = panel.state.candidateGraphHash;
  panel.state._layoutPreviewTurnId = panel.state.turnId || null;
  panel.state._layoutPreviewSessionId = panel.state.sessionId || null;
  clearCandidatePreviewState(panel);
  return true;
}

function restoreLayoutPreviewBaseline(panel, { repaint = true, clear = true } = {}) {
  const baseline = panel?.state?._layoutPreviewBaseline;
  if (!baseline?.graph) {
    if (clear) {
      clearLayoutPreviewState(panel);
    }
    return false;
  }
  // Non-destructive preview: the live graph and viewport were never mutated, so
  // there is nothing to restore. Drop the cached overlay diff + draw model so
  // the layout-moved arrows stop rendering, and repaint when asked.
  try {
    if (clear) {
      clearCandidatePreviewState(panel);
      clearLayoutPreviewState(panel);
    }
    if (repaint) {
      clearCandidateInvalidationSideEffects(true);
    }
  } catch (error) {
    console.warn("[vibecomfy] failed to clear layout preview:", safePreviewLogDetail(error));
  }
  return true;
}

// ── Audit download helpers ─────────────────────────────────────────────────
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

const canonicalJsonString = canonicalSessionJsonString;

async function sha256HexUtf8(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function captureLiveCanvasRevision() {
  const result = createIntentGraphAdapter(app).captureRevision();
  return result.ok ? result.data.revision : null;
}

// Session/CAS hashes deliberately retain the compatibility projection used by
// the Python session store. Typed v2 authority is carried separately by
// projectionReferenceV1 pre/postcondition evidence. These two digest families
// are both valid but are not interchangeable: sending a typed projection
// digest as `post_apply_hash` makes finalize reject a correctly applied graph
// and compensate by restoring the pre-apply canvas.
async function structuralGraphHash(graph) {
  return sha256HexUtf8(canonicalJsonString(buildStructuralGraphProjection(graph)));
}

async function layoutGraphHash(graph) {
  try {
    return sha256HexUtf8(canonicalJsonString(buildLayoutGraphProjection(graph)));
  } catch (error) {
    if (error?.code === "UNSUPPORTED_NESTED_LAYOUT_SCOPE") return null;
    throw error;
  }
}

// ── T6: Scope resolver ────────────────────────────────────────────────────
// Imported from a zero-dependency module so the fingerprint/scope logic
// can be unit-tested without pulling in the full ComfyUI runtime.
import {
  computeStructuralGraphFingerprint,
  computeScopeId,
  captureInitialScopeId,
} from "./scope_resolver.js";

// Re-export for test consumers that import from this module.
export {
  computeStructuralGraphFingerprint,
  computeScopeId,
  captureInitialScopeId,
};

function captureLiveCanvasToken(_graphHash, structuralHash) {
  const revision = captureLiveCanvasRevision();
  if (revision != null) {
    return `live:${revision}`;
  }
  return structuralHash ? `structure:${structuralHash}` : `hash:${_graphHash}`;
}

function buildSubmitIdempotencyKey({ sessionId, graphHash, route, model }) {
  const unique = typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(16).slice(2)}`;
  const modelPart = model || "default";
  const sessionPart = sessionId || "new";
  return `submit:${sessionPart}:${route}:${modelPart}:${graphHash.slice(0, 12)}:${unique}`;
}

function buildActionIdempotencyKey({ action, sessionId, turnId, graphHash }) {
  const unique = typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(16).slice(2)}`;
  return `${action}:${sessionId}:${turnId}:${graphHash.slice(0, 12)}:${unique}`;
}

function createDetails(summary, value) {
  const details = el("details");
  const heading = el("summary", summary);
  heading.style.cursor = "pointer";
  let rendered = false;
  const pre = el("pre", "");
  Object.assign(pre.style, {
    margin: "8px 0 0 0",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    overflowWrap: "anywhere",
    color: "#b9ffcc",
    fontSize: "11px",
    maxWidth: "100%",
    minWidth: "0",
  });
  const renderValue = () => {
    if (rendered) {
      return;
    }
    rendered = true;
    pre.textContent = safeJson(value);
  };
  details.addEventListener("toggle", () => {
    if (details.open) {
      renderValue();
    }
  });
  details.appendChild(heading);
  const preview = compactDetailsPreview(value);
  if (preview) {
    const previewNode = el("div", preview);
    Object.assign(previewNode.style, {
      marginTop: "4px",
      color: "#8d93a1",
      fontSize: "10px",
      overflowWrap: "anywhere",
      wordBreak: "break-word",
    });
    details.appendChild(previewNode);
  }
  details.appendChild(pre);
  return details;
}

function createBubbleDetailSection(title) {
  return createBubbleDetailSectionImpl(title, { el });
}

function createQueueIssue(code, message, detail = {}, severity = "error") {
  return { code, message, detail, severity };
}

function collectArrayAtPath(root, path) {
  let value = root;
  for (const key of path) {
    value = value?.[key];
    if (value == null) {
      return [];
    }
  }
  return Array.isArray(value) ? value : [];
}

function backendQueueIssueCandidates(report) {
  return [
    ...collectArrayAtPath(report, ["queue_blockers"]),
    ...collectArrayAtPath(report, ["diagnostics", "issues"]),
    ...collectArrayAtPath(report, ["gates", "queue_validate_ok", "evidence", "blockers"]),
    ...collectArrayAtPath(report, ["gates", "queue_validate_ok", "evidence", "queue_blockers"]),
  ];
}

function normalizeBackendIntentQueueIssue(issue) {
  if (!issue || issue.code !== "intent_node_queue_blocker") {
    return null;
  }
  const detail = issue.detail && typeof issue.detail === "object"
    ? { ...issue.detail }
    : {};
  for (const key of ["node_id", "class_type", "kind", "uid", "lowered", "runtime_backed", "provider", "confidence", "diagnostic"]) {
    if (detail[key] == null && issue[key] != null) {
      detail[key] = issue[key];
    }
  }
  const nodeId = detail.node_id || "unknown";
  const classType = detail.class_type || "vibecomfy.*";
  return createQueueIssue(
    issue.code,
    issue.message || issue.user_facing_message || `Node ${nodeId} (${classType}) is an editor-only intent node and cannot be queued until it is lowered.`,
    detail,
    issue.severity || "error",
  );
}

function collectQueueIssues(report) {
  const issues = backendQueueIssueCandidates(report)
    .map(normalizeBackendIntentQueueIssue)
    .filter(Boolean);
  const hasBackendIntentBlocker = issues.some((issue) => issue.code === "intent_node_queue_blocker");
  const recovery = Array.isArray(report?.recovery) ? report.recovery : [];
  for (const entry of recovery) {
    const nodeId = entry?.node_id;
    const classType = entry?.class_type;
    if (isIntentClassType(classType)) {
      if (entry?.lowered === true) {
        // lowered entries are informational — the intent node was already
        // statically lowered to native nodes; no queue blocker needed
        continue;
      }
      if (hasBackendIntentBlocker) {
        continue;
      }
      const kind = entry?.kind
        || INTENT_KIND_BY_CLASS_TYPE[classType]
        || "intent";
      const runtimeBacked = Boolean(entry?.runtime_backed);
      issues.push(createQueueIssue(
        "intent_node_queue_blocker",
        `Node ${nodeId} (${classType}) is an editor-only intent node and cannot be queued until it is lowered.`,
        {
          node_id: nodeId,
          class_type: classType,
          kind,
          uid: entry?.uid || null,
          lowered: false,
          runtime_backed: runtimeBacked,
          provider: entry?.provider || null,
          confidence: entry?.confidence ?? null,
          diagnostic: entry?.diagnostic || null,
        },
      ));
      continue;
    }
    if (entry?.schema_less === true) {
      issues.push(createQueueIssue(
        "schema_less_queue_blocker",
        `Node ${nodeId} (${classType}) has no schema evidence and cannot be queued safely.`,
        {
          node_id: nodeId,
          class_type: classType,
          provider: entry?.provider,
          confidence: entry?.confidence,
          diagnostic: entry?.diagnostic,
        },
      ));
      continue;
    }
    const confidence = entry?.confidence;
    if (typeof confidence === "number" && confidence <= 0.3) {
      issues.push(createQueueIssue(
        "low_confidence_queue_blocker",
        `Node ${nodeId} (${classType}) has low-confidence schema evidence and cannot be queued safely.`,
        {
          node_id: nodeId,
          class_type: classType,
          provider: entry?.provider,
          confidence,
          diagnostic: entry?.diagnostic,
        },
      ));
      continue;
    }
    if (confidence == null && entry?.schema_less !== true) {
      issues.push(createQueueIssue(
        "low_confidence_queue_blocker",
        `Node ${nodeId} (${classType}) has unresolved model/widget evidence and cannot be queued safely.`,
        {
          node_id: nodeId,
          class_type: classType,
          provider: entry?.provider,
          confidence: null,
          diagnostic: entry?.diagnostic || "unresolved model/widget: confidence could not be determined",
        },
      ));
    }
  }

  const strippedHelpers = report?.change?.content_edits?.stripped_helpers;
  if (Array.isArray(strippedHelpers) && strippedHelpers.length) {
    issues.push(createQueueIssue(
      "editor_only_node_queue_blocker",
      "Editor-only helper nodes would be stripped from the queued API graph.",
      { stripped_helpers: strippedHelpers.slice() },
    ));
  }

  if (!issues.some((issue) => issue.code === "intent_node_queue_blocker")) {
    const graphNodes = Array.isArray(report?.graph?.nodes)
      ? report.graph.nodes
      : report?.nodes
        ? (Array.isArray(report.nodes) ? report.nodes : [])
        : [];
    for (const node of graphNodes) {
      const classType = node?.type || node?.class_type;
      if (isIntentClassType(classType)) {
        issues.push(createQueueIssue(
          "intent_node_queue_blocker",
          `Node ${node?.id || "unknown"} (${classType}) is an editor-only intent node and cannot be queued until it is lowered.`,
          {
            node_id: node?.id || null,
            class_type: classType,
            kind: INTENT_KIND_BY_CLASS_TYPE[classType] || "intent",
            uid: node?.properties?.vibecomfy_uid || null,
            lowered: false,
            runtime_backed: false,
            provider: null,
            confidence: null,
            diagnostic: "detected from graph nodes (fallback for older report format)",
          },
        ));
      }
    }
  }

  return issues;
}

function getBackendStageInfo(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const stage = payload.backend_stage || payload.stage || null;
  const progress = payload.backend_progress ?? payload.progress ?? null;
  if (stage == null && progress == null) {
    return null;
  }
  return { stage, progress };
}

function nextMacrotask() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function agentStatusDeps() {
  const deps = {
    clearCredentialInput,
    closeChooseEngineOverlay,
    markAgentPanelDirtyAfterCommit,
    nextMacrotask,
    openChooseEngineOverlay,
    renderAgentPanel,
    refreshAgentStatus: (panel, opts) => pollerRefreshAgentStatus(panel, opts, deps),
    scheduleAgentStatusRetry: (panel, route, model, opts) =>
      pollerScheduleAgentStatusRetry(panel, route, model, opts, deps),
    SETTINGS_STATUS_RENDER_SECTIONS,
    RENDER_SECTIONS,
    syncChooseEngineGate: (panel) => pollerSyncChooseEngineGate(panel, deps),
  };
  return deps;
}

function submitReadinessState(panel) {
  return submitReadinessStateImpl(panel, {
    routeStatusState,
    ROUTE_STATUS_KIND,
  });
}

function clearCredentialInput(panel) {
  panel.fields.apiKey.value = "";
}

function hasStoredBrowserCredential(panel, route = panel?.fields?.route?.value) {
  const presence = panel?.state?.statusSnapshot?.credential_presence || {};
  const requestedRoute = String(route || "").trim().toLowerCase();
  if (requestedRoute === "deepseek") {
    return Boolean(presence.deepseek_api_key);
  }
  const normalizedRoute = normalizeRoutePreference(route);
  if (normalizedRoute === "deepseek") {
    return Boolean(presence.deepseek_api_key);
  }
  if (normalizedRoute === "openrouter") {
    return Boolean(presence.openrouter_api_key);
  }
  return Boolean(presence.openrouter_api_key || presence.deepseek_api_key);
}

function hasStoredOpenRouterCredential(panel) {
  return hasStoredBrowserCredential(panel, "openrouter");
}

function closeChooseEngineOverlay(panel) {
  const existing = getPanelElementById(panel, PANEL_IDS.welcomeOverlay);
  if (existing && typeof existing.remove === "function") {
    existing.remove();
  }
  if (panel?.state?.chooseEngineRefresh) {
    panel.state.chooseEngineRefresh = null;
  }
}



export function syncBaselineFromResponse(panel, payload) {
  if (!panel?.state || !payload || typeof payload !== "object") {
    return;
  }
  const recovery = recoveryForPanelState(payload.rebaselineRecovery);
  transition(panel, "SYNC_BASELINE", {
    ...payload,
    ...(recovery
      ? { rebaselineRecovery: recovery }
      : (payload.ok === true ? { clearRebaselineRecovery: true } : {})),
  });
}



function synthesizeStaleRebaselineRecovery(payload, panel = null, actionBody = null) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  if (String(payload.kind || "") !== "StaleStateMismatch") {
    return null;
  }
  const stage = String(payload.stage || "");
  if (stage && !["accept", "frontend", "ingest"].includes(stage)) {
    return null;
  }
  const lastSubmit = panel?.state?.lastSubmit || {};
  return {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash:
      typeof payload.baseline_graph_hash === "string" ? payload.baseline_graph_hash
        : typeof payload.expected_baseline_graph_hash === "string" ? payload.expected_baseline_graph_hash
          : typeof panel?.state?.baselineGraphHash === "string" ? panel.state.baselineGraphHash
            : typeof lastSubmit.client_structural_graph_hash === "string" ? lastSubmit.client_structural_graph_hash
              : null,
    submit_graph_hash:
      typeof actionBody?.submit_graph_hash === "string" ? actionBody.submit_graph_hash
        : typeof panel?.state?.serverSubmitGraphHash === "string" ? panel.state.serverSubmitGraphHash
          : null,
    submit_structural_graph_hash:
      typeof lastSubmit.client_structural_graph_hash === "string" ? lastSubmit.client_structural_graph_hash : null,
    client_graph_hash:
      typeof actionBody?.client_graph_hash === "string" ? actionBody.client_graph_hash
        : typeof lastSubmit.client_graph_hash === "string" ? lastSubmit.client_graph_hash
          : null,
    client_structural_graph_hash:
      typeof payload.client_structural_graph_hash === "string" ? payload.client_structural_graph_hash
        : typeof lastSubmit.client_structural_graph_hash === "string" ? lastSubmit.client_structural_graph_hash
          : null,
  };
}

function recoveryForFailure(payload, panel = null, actionBody = null) {
  const extracted = readRebaselineRecovery(payload, { endpoint: "recoveryForFailure", allowLegacy: true });
  if (extracted) {
    return recoveryForPanelState(extracted);
  }
  return synthesizeStaleRebaselineRecovery(payload, panel, actionBody);
}

function recoveryForPanelState(recovery) {
  if (!recovery || typeof recovery !== "object") {
    return null;
  }
  return {
    action: typeof recovery.action === "string" ? recovery.action : null,
    endpoint: typeof recovery.endpoint === "string" ? recovery.endpoint : null,
    reason: typeof recovery.reason === "string" ? recovery.reason : null,
    last_known_baseline_graph_hash:
      typeof recovery.last_known_baseline_graph_hash === "string"
        ? recovery.last_known_baseline_graph_hash
        : typeof recovery.lastKnownBaselineGraphHash === "string"
          ? recovery.lastKnownBaselineGraphHash
          : null,
    submit_graph_hash:
      typeof recovery.submit_graph_hash === "string"
        ? recovery.submit_graph_hash
        : typeof recovery.submitGraphHash === "string"
          ? recovery.submitGraphHash
          : null,
    submit_structural_graph_hash:
      typeof recovery.submit_structural_graph_hash === "string"
        ? recovery.submit_structural_graph_hash
        : typeof recovery.submitStructuralGraphHash === "string"
          ? recovery.submitStructuralGraphHash
          : null,
    client_graph_hash:
      typeof recovery.client_graph_hash === "string"
        ? recovery.client_graph_hash
        : typeof recovery.clientGraphHash === "string"
          ? recovery.clientGraphHash
          : null,
    client_structural_graph_hash:
      typeof recovery.client_structural_graph_hash === "string"
        ? recovery.client_structural_graph_hash
        : typeof recovery.clientStructuralGraphHash === "string"
          ? recovery.clientStructuralGraphHash
          : null,
  };
}

async function buildSubmitSnapshot(panel) {
  const graph = captureSerializedGraphForAgent();
  const workflowId = resolveActiveWorkflowUuid();
  if (!workflowId) {
    const error = new Error("Agent Edit requires the stable UUID of the active Comfy workflow tab.");
    error.code = "missing_workflow_identity";
    throw error;
  }
  const graphJson = canonicalJsonString(graph);
  const graphHash = await sha256HexUtf8(graphJson);
  const structuralHash = await structuralGraphHash(graph);
  const layoutHash = await layoutGraphHash(graph);
  const liveCanvasToken = captureLiveCanvasToken(graphHash, structuralHash);
  const route = normalizeRoutePreference(panel.fields.route.value);
  const pipelineMode = normalizePipelineMode(panel.fields.pipelineMode?.value);
  const model = normalizeModelPreference(panel.fields.model.value);
  const idempotencyKey = buildSubmitIdempotencyKey({
    sessionId: panel.state.sessionId,
    graphHash,
    route,
    model,
  });
  const expectedBaselineGraphHash =
    typeof panel?.state?.baselineGraphHash === "string"
      ? panel.state.baselineGraphHash
      : null;
  return {
    graph,
    workflowId,
    graphJson,
    graphHash,
    structuralHash,
    layoutHash,
    liveCanvasToken,
    route,
    pipelineMode,
    model,
    idempotencyKey,
    expectedBaselineGraphHash,
  };
}

async function buildCanvasSnapshot() {
  const graph = captureSerializedGraphForAgent();
  const graphJson = canonicalJsonString(graph);
  const graphHash = await sha256HexUtf8(graphJson);
  const structuralHash = await structuralGraphHash(graph);
  const layoutHash = await layoutGraphHash(graph);
  const liveCanvasToken = captureLiveCanvasToken(graphHash, structuralHash);
  return { graph, graphJson, graphHash, structuralHash, layoutHash, liveCanvasToken };
}

function createAgentPanelShell() {
  const root = el("aside");
  const panelId = nextAgentPanelId();
  root.id = PANEL_IDS.root;
  root.className = "vibecomfy-agent-panel-root";
  root.dataset.vibecomfyPanelId = panelId;
  root.dataset.vibecomfyPanelRoot = "1";
  root.dataset.open = "0";
  Object.assign(root.style, {
    position: "fixed",
    top: "0",
    right: "0",
    width: "420px",
    height: "100vh",
    zIndex: "9999",
    pointerEvents: "none",
    transform: "translateX(432px)",
    transition: "transform 140ms ease",
  });

  const shell = el("div");
  shell.id = PANEL_IDS.shell;
  shell.className = "vibecomfy-agent-panel-shell";
  Object.assign(shell.style, {
    position: "relative",
    height: "100%",
    display: "flex",
    flexDirection: "column",
    minHeight: "0",
    background: "#101115",
    color: "#edf2f7",
    borderLeft: "1px solid #282a32",
    boxShadow: "-10px 0 28px rgba(0,0,0,0.38)",
    fontFamily: "monospace",
    pointerEvents: "auto",
  });

  // ── Header (title, status, settings gear, close) ────────────────────────
  const header = el("div");
  Object.assign(header.style, {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "8px",
    padding: "10px 14px 6px 14px",
    borderBottom: "1px solid #282a32",
    flexWrap: "wrap",
  });
  const headerLeft = el("div");
  Object.assign(headerLeft.style, {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  });
  const title = el("div");
  Object.assign(title.style, {
    display: "flex",
    alignItems: "center",
    gap: "7px",
    fontWeight: "700",
    fontSize: "14px",
    color: "#edf2f7",
    letterSpacing: "0.02em",
  });
  const titleLogo = el("img");
  titleLogo.src = VIBECOMFY_LOGO_URL;
  titleLogo.alt = "VibeComfy";
  Object.assign(titleLogo.style, { width: "24px", height: "24px", display: "block", flexShrink: "0" });
  title.appendChild(titleLogo);
  title.appendChild(el("span", "VibeComfy"));
  headerLeft.appendChild(title);
  header.appendChild(headerLeft);

  const headerRight = el("div");
  Object.assign(headerRight.style, {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    flexShrink: "0",
  });

  const status = el("div", "Idle");
  status.id = PANEL_IDS.status;
  Object.assign(status.style, {
    fontSize: "11px",
    color: "#9da1ac",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  });
  headerRight.appendChild(status);

  const settingsGearBtn = button("\u2699", () => {
    const panel = currentAgentPanel();
    if (panel) {
      const popover = panel.settingsPopover;
      if (popover) {
        const isOpen = popover.style.display !== "none";
        if (!isOpen && !panel.__settingsPopoverEverOpened) {
          panel.__settingsPopoverEverOpened = true;
          renderAgentPanel(panel, { dirtySections: [RENDER_SECTIONS.SETTINGS, RENDER_SECTIONS.DEVELOPER] });
        }
        popover.style.display = isOpen ? "none" : "block";
        if (!isOpen) {
          void pollerRefreshVibeComfyInfo(panel, agentStatusDeps());
        }
      }
    }
  });
  settingsGearBtn.title = "Settings";
  Object.assign(settingsGearBtn.style, {
    padding: "4px 8px",
    fontSize: "14px",
    lineHeight: "1",
  });

  const closeBtn = button("Close", () => closeAgentPanel(currentAgentPanel()));
  closeBtn.id = PANEL_IDS.close;
  closeBtn.style.padding = "4px 8px";
  closeBtn.style.fontSize = "11px";

  headerRight.appendChild(settingsGearBtn);
  headerRight.appendChild(closeBtn);
  header.appendChild(headerRight);

  // ── Compact meta row (now inside header area, not a full grid row) ──────
  const metaRow = el("div");
  Object.assign(metaRow.style, {
    // Hidden: the state/session/turn/baseline debug line is noise for users.
    // Still populated by renderMeta() so the debug hook can read it.
    display: "none",
    gap: "10px",
    padding: "4px 14px 6px 14px",
    borderBottom: "1px solid #282a32",
    background: "#14161b",
    fontSize: "10px",
    color: "#8d93a1",
    flexWrap: "wrap",
  });

  // ── Thread mount (scrollable chat + activity region) ────────────────────
  const thread = el("div");
  thread.dataset.vibecomfyAgentThread = "1";
  Object.assign(thread.style, {
    flex: "1 1 auto",
    minHeight: "0",
    overflowY: "auto",
    padding: "12px 14px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  });

  const threadRegion = panelSection(PANEL_IDS.threadRegion, "Thread");
  threadRegion.section.style.border = "none";
  threadRegion.section.style.background = "transparent";
  threadRegion.section.style.padding = "0";
  // The section is a flex child of the scrollable `thread` wrapper. Without
  // flexShrink:0 it shrinks to the wrapper's height and (overflow:hidden from
  // panelSection) CLIPS the conversation instead of letting the wrapper scroll.
  threadRegion.section.style.flexShrink = "0";
  threadRegion.section.style.minHeight = "100%";
  threadRegion.section.style.display = "flex";
  threadRegion.section.style.flexDirection = "column";
  threadRegion.body.style.gap = "10px";
  threadRegion.body.style.flex = "1 1 auto";
  threadRegion.body.style.minHeight = "0";
  threadRegion.body.style.display = "flex";
  threadRegion.body.style.flexDirection = "column";

  // Chat section: persisted conversation bubbles (M3).
  const chatRegion = panelSection(PANEL_IDS.chatRegion, "");
  chatRegion.section.style.flex = "1 0 auto";
  chatRegion.section.style.display = "flex";
  chatRegion.section.style.flexDirection = "column";
  chatRegion.body.style.flex = "1 0 auto";
  chatRegion.body.style.minHeight = "0";
  chatRegion.body.style.display = "flex";
  chatRegion.body.style.flexDirection = "column";
  threadRegion.body.appendChild(chatRegion.section);

  const historyRegion = panelSection(PANEL_IDS.historyRegion, "");
  historyRegion.section.style.display = "none";
  threadRegion.body.appendChild(historyRegion.section);

  const candidateRegion = panelSection(PANEL_IDS.candidateRegion, "");
  candidateRegion.section.style.display = "none";
  threadRegion.body.appendChild(candidateRegion.section);

  const failureRegion = panelSection(PANEL_IDS.failureRegion, "");
  failureRegion.section.style.display = "none";
  threadRegion.body.appendChild(failureRegion.section);

  const queueRegion = panelSection(PANEL_IDS.queueRegion, "");
  queueRegion.section.style.display = "none";
  threadRegion.body.appendChild(queueRegion.section);

  const auditRegion = panelSection(PANEL_IDS.auditRegion, "");
  auditRegion.section.style.display = "none";
  threadRegion.body.appendChild(auditRegion.section);

  const debugRegion = panelSection(PANEL_IDS.debugRegion, "");
  debugRegion.section.style.display = "none";
  threadRegion.body.appendChild(debugRegion.section);

  thread.appendChild(threadRegion.section);

  // ── Composer (bottom mount: prompt + action buttons) ────────────────────
  const composer = el("div");
  Object.assign(composer.style, {
    display: "flex",
    flexDirection: "column",
    flexShrink: "0",
    gap: "8px",
    padding: "10px 14px 12px 14px",
    borderTop: "1px solid #282a32",
    background: "#14161b",
  });

  const promptRegion = panelSection(PANEL_IDS.promptRegion, "");
  promptRegion.section.style.border = "none";
  promptRegion.section.style.background = "transparent";
  promptRegion.section.style.padding = "0";
  const textarea = document.createElement("textarea");
  textarea.id = PANEL_IDS.prompt;
  textarea.placeholder = "Describe the workflow change...";
  Object.assign(textarea.style, {
    width: "100%",
    minHeight: "80px",
    resize: "vertical",
    background: "#0d0e12",
    color: "#edf2f7",
    border: "1px solid #373c46",
    borderRadius: "6px",
    padding: "8px",
    fontFamily: "monospace",
    fontSize: "12px",
    boxSizing: "border-box",
  });
  promptRegion.body.appendChild(textarea);
  composer.appendChild(promptRegion.section);

  const composerButtons = el("div");
  Object.assign(composerButtons.style, {
    display: "flex",
    gap: "6px",
    flexWrap: "nowrap",
    width: "100%",
  });

  const submitBtn = button("Submit", () => submitAgentEdit(currentAgentPanel()));
  submitBtn.id = PANEL_IDS.submit;
  const stopBtn = button("Stop", () => stopAgentSubmit(currentAgentPanel()));
  stopBtn.style.display = "none";
  const applyBtn = button("Apply", () => applyFlow.applyAgentCandidate(currentAgentPanel()));
  applyBtn.id = PANEL_IDS.apply;
  const resumeApplyBtn = button("Resume Apply", () => applyFlow.applyAgentCandidate(currentAgentPanel(), { resumePrepared: true }));
  resumeApplyBtn.id = "vibecomfy-agent-panel-resume-apply";
  resumeApplyBtn.dataset.vibecomfyAction = "resume-apply";
  resumeApplyBtn.style.display = "none";
  const rejectBtn = button("Reject", () => rejectAgentCandidate(currentAgentPanel()));
  rejectBtn.id = PANEL_IDS.reject;
  const rollbackBtn = button("Cancel interrupted Apply", () => rejectAgentCandidate(currentAgentPanel()));
  rollbackBtn.id = PANEL_IDS.rollback;
  rollbackBtn.dataset.vibecomfyAction = "rollback";
  rollbackBtn.style.display = "none";
  const undoBtn = button("", () => undoLastApply(currentAgentPanel()));
  undoBtn.id = PANEL_IDS.undo;
  undoBtn.dataset.vibecomfyAction = "undo";
  undoBtn.title = "Undo Last Apply";
  undoBtn.setAttribute("data-tooltip", "Undo Last Apply");
  undoBtn.setAttribute("aria-label", "Undo Last Apply");
  undoBtn.appendChild(makeUndoIcon());
  attachInstantTooltip(undoBtn);
  const newConvBtn = button("New conversation", () => newAgentConversation(currentAgentPanel()));
  newConvBtn.id = "vibecomfy-agent-panel-new-conversation";
  submitBtn.dataset.vibecomfyAction = "submit";
  stopBtn.dataset.vibecomfyAction = "stop";
  applyBtn.dataset.vibecomfyAction = "apply";
  rejectBtn.dataset.vibecomfyAction = "reject";

  // Keep all action buttons on a single line; stretch them to share the width
  // and shrink (with an ellipsis) rather than wrap when the panel is narrow.
  for (const b of [submitBtn, stopBtn, applyBtn, resumeApplyBtn, rejectBtn, rollbackBtn, undoBtn, newConvBtn]) {
    b.style.flex = "1 1 0";
    b.style.minWidth = "0";
    b.style.whiteSpace = "nowrap";
    b.style.overflow = "hidden";
    b.style.textOverflow = "ellipsis";
  }
  Object.assign(undoBtn.style, {
    flex: "0 0 34px",
    width: "34px",
    minWidth: "34px",
    padding: "7px 0",
  });

  composerButtons.appendChild(undoBtn);
  composerButtons.appendChild(submitBtn);
  composerButtons.appendChild(stopBtn);
  composerButtons.appendChild(applyBtn);
  composerButtons.appendChild(resumeApplyBtn);
  composerButtons.appendChild(rejectBtn);
  composerButtons.appendChild(rollbackBtn);
  composerButtons.appendChild(newConvBtn);
  const havingIssuesBtn = button("?", () => showIssueModal(currentAgentPanel()));
  havingIssuesBtn.id = PANEL_IDS.havingIssues;
  havingIssuesBtn.title = "Having issues? Open the help dialog.";
  havingIssuesBtn.setAttribute("data-tooltip", "Having issues? Open the help dialog.");
  if (typeof havingIssuesBtn.setAttribute === "function") {
    havingIssuesBtn.setAttribute("aria-label", "Having issues? Open the help dialog.");
  }
  attachInstantTooltip(havingIssuesBtn);
  setButtonEmphasis(havingIssuesBtn, true, "neutral");
  Object.assign(havingIssuesBtn.style, {
    flex: "0 0 28px",
    width: "28px",
    minWidth: "28px",
    padding: "4px 0",
    fontSize: "11px",
    color: "#9da1ac",
    background: "#171a20",
    borderColor: "#303541",
  });
  composerButtons.appendChild(havingIssuesBtn);
  composer.appendChild(composerButtons);

  const composerNotice = el("div");
  composerNotice.id = PANEL_IDS.composerNotice;
  Object.assign(composerNotice.style, {
    display: "none",
    padding: "8px 10px",
    borderRadius: "6px",
    border: "1px solid #2a313c",
    background: "#0d1118",
    color: "#c4ccd6",
    fontSize: "11px",
    lineHeight: "1.45",
    whiteSpace: "pre-wrap",
    maxHeight: "120px",
    overflowY: "auto",
    overflowX: "hidden",
  });
  composer.appendChild(composerNotice);

  // ── Settings popover (absolutely positioned overlay) ────────────────────
  const settingsPopover = el("div");
  settingsPopover.className = "vibecomfy-agent-panel-settings-popover";
  Object.assign(settingsPopover.style, {
    display: "none",
    position: "absolute",
    top: "44px",
    right: "14px",
    width: "360px",
    maxWidth: "calc(100% - 28px)",
    background: "#17171c",
    border: "1px solid #34343a",
    borderRadius: "8px",
    boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
    zIndex: "10000",
    padding: "12px",
    boxSizing: "border-box",
    maxHeight: "calc(100vh - 72px)",
    overflowY: "auto",
    overflowX: "hidden",
    overscrollBehavior: "contain",
  });

  const settingsRegion = panelSection(PANEL_IDS.settingsRegion, "Settings");
  settingsRegion.section.style.border = "none";
  settingsRegion.section.style.background = "transparent";
  settingsRegion.section.style.padding = "0";

  const routeSelect = document.createElement("select");
  routeSelect.id = PANEL_IDS.route;
  Object.assign(routeSelect.style, {
    width: "100%",
    background: "#0d0e12",
    color: "#edf2f7",
    border: "1px solid #373c46",
    borderRadius: "6px",
    padding: "6px 28px 6px 8px",
    fontFamily: "monospace",
    fontSize: "12px",
    boxSizing: "border-box",
  });
  pollerPopulateRouteSelect(routeSelect, null, { selectedRoute: "auto" }, agentStatusDeps());
  routeSelect.value = "auto";
  const pipelineModeLabel = el("label", "Agent mode");
  pipelineModeLabel.htmlFor = PANEL_IDS.pipelineMode;
  Object.assign(pipelineModeLabel.style, {
    color: "#c4ccd6",
    fontSize: "11px",
    marginTop: "8px",
  });
  const pipelineModeSelect = document.createElement("select");
  pipelineModeSelect.id = PANEL_IDS.pipelineMode;
  for (const [value, text] of [
    ["staged", "Staged pipeline"],
    ["threaded", "Threaded agent"],
  ]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    pipelineModeSelect.appendChild(option);
  }
  Object.assign(pipelineModeSelect.style, {
    width: "100%",
    background: "#0d0e12",
    color: "#edf2f7",
    border: "1px solid #373c46",
    borderRadius: "6px",
    padding: "6px 28px 6px 8px",
    fontFamily: "monospace",
    fontSize: "12px",
    boxSizing: "border-box",
  });
  pipelineModeSelect.value = normalizePipelineMode(
    _lsGet(PIPELINE_MODE_STORAGE_KEY) || DEFAULT_PIPELINE_MODE,
  );
  const modelInput = document.createElement("input");
  modelInput.id = PANEL_IDS.model;
  modelInput.placeholder = "Model override (optional)";
  modelInput.disabled = true;
  Object.assign(modelInput.style, {
    width: "100%",
    display: "none",
    background: "#0d0e12",
    color: "#edf2f7",
    border: "1px solid #373c46",
    borderRadius: "6px",
    padding: "6px 8px",
    fontFamily: "monospace",
    fontSize: "12px",
    boxSizing: "border-box",
  });
  const apiKeyInput = document.createElement("input");
  apiKeyInput.id = PANEL_IDS.apiKey;
  apiKeyInput.type = "password";
  apiKeyInput.placeholder = "OpenRouter API key";
  Object.assign(apiKeyInput.style, {
    width: "100%",
    background: "#0d0e12",
    color: "#edf2f7",
    border: "1px solid #373c46",
    borderRadius: "6px",
    padding: "6px 8px",
    fontFamily: "monospace",
    fontSize: "12px",
    boxSizing: "border-box",
  });
  const settingsStatus = el("div");
  settingsStatus.id = PANEL_IDS.settingsStatus;
  settingsStatus.style.color = "#8d93a1";
  settingsStatus.style.fontSize = "11px";
  const settingsGuidance = el("div");
  settingsGuidance.id = PANEL_IDS.settingsGuidance;
  settingsGuidance.style.whiteSpace = "pre-wrap";
  settingsGuidance.style.color = "#edf2f7";
  const settingsButtons = el("div");
  Object.assign(settingsButtons.style, {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
  });
  const settingsTest = button("Test Provider", () =>
    testAgentSettingsImpl(currentAgentPanel(), agentStatusDeps()));
  settingsTest.id = PANEL_IDS.settingsTest;
  const researchContributionControl = el("div");
  researchContributionControl.id = PANEL_IDS.researchContribution;
  Object.assign(researchContributionControl.style, {
    display: "grid",
    gap: "6px",
  });
  const researchContributionLabel = el("div", "Contribute agent research");
  Object.assign(researchContributionLabel.style, {
    color: "#edf2f7",
    fontSize: "12px",
    lineHeight: "1.35",
  });
  const researchContributionToggle = el("div");
  Object.assign(researchContributionToggle.style, {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    border: "1px solid #373c46",
    borderRadius: "6px",
    overflow: "hidden",
  });
  const researchContributionYes = button("YES", () => {
    const panel = currentAgentPanel();
    if (panel) {
      return saveResearchContributionSetting(panel, true, { trigger: true });
    }
    return undefined;
  });
  researchContributionYes.id = PANEL_IDS.researchContributionYes;
  const researchContributionNo = button("NO", () => {
    const panel = currentAgentPanel();
    if (panel) {
      return saveResearchContributionSetting(panel, false, { trigger: false });
    }
    return undefined;
  });
  researchContributionNo.id = PANEL_IDS.researchContributionNo;
  [researchContributionYes, researchContributionNo].forEach((node) => {
    Object.assign(node.style, {
      border: "none",
      borderRadius: "0",
      padding: "6px 8px",
      fontSize: "11px",
      fontWeight: "700",
    });
  });
  researchContributionToggle.appendChild(researchContributionYes);
  researchContributionToggle.appendChild(researchContributionNo);
  researchContributionControl.appendChild(researchContributionLabel);
  researchContributionControl.appendChild(researchContributionToggle);
  researchContributionControl.yesButton = researchContributionYes;
  researchContributionControl.noButton = researchContributionNo;
  researchContributionControl.checked = false;
  routeSelect.onchange = () => {
    const panel = currentAgentPanel();
    if (panel) {
      panel.fields.route.value = routeSelect.value;
      return autoSaveAgentSettings(panel);
    }
    return undefined;
  };
  pipelineModeSelect.onchange = () => {
    const canonicalMode = normalizePipelineMode(pipelineModeSelect.value);
    pipelineModeSelect.value = canonicalMode;
    _lsSet(PIPELINE_MODE_STORAGE_KEY, canonicalMode);
    const panel = currentAgentPanel();
    if (panel) {
      panel.fields.pipelineMode.value = canonicalMode;
    }
  };
  modelInput.onchange = () => {
    const panel = currentAgentPanel();
    if (panel) {
      panel.fields.model.value = modelInput.value;
      return autoSaveAgentSettings(panel);
    }
    return undefined;
  };
  modelInput.onblur = () => {
    const panel = currentAgentPanel();
    if (panel && modelInput.value !== normalizeModelPreference(panel.state.lastAutosavedModel || "")) {
      panel.fields.model.value = modelInput.value;
      panel.state.lastAutosavedModel = modelInput.value;
      return autoSaveAgentSettings(panel);
    }
    return undefined;
  };
  apiKeyInput.onchange = () => {
    const panel = currentAgentPanel();
    if (panel) {
      panel.fields.apiKey.value = apiKeyInput.value;
      return autoSaveAgentSettings(panel, { includeCredential: true });
    }
    return undefined;
  };
  apiKeyInput.onblur = () => {
    const panel = currentAgentPanel();
    if (panel && String(apiKeyInput.value || "").trim()) {
      panel.fields.apiKey.value = apiKeyInput.value;
      return autoSaveAgentSettings(panel, { includeCredential: true });
    }
    return undefined;
  };
  settingsButtons.appendChild(settingsTest);
  settingsRegion.body.appendChild(routeSelect);
  settingsRegion.body.appendChild(pipelineModeLabel);
  settingsRegion.body.appendChild(pipelineModeSelect);
  settingsRegion.body.appendChild(modelInput);
  settingsRegion.body.appendChild(apiKeyInput);
  settingsRegion.body.appendChild(settingsButtons);
  settingsRegion.body.appendChild(researchContributionControl);
  settingsRegion.body.appendChild(settingsStatus);
  settingsRegion.body.appendChild(settingsGuidance);

  settingsPopover.appendChild(settingsRegion.section);

  // ── Developer section inside settings popover ────────────────────────────
  const developerRegion = panelSection(PANEL_IDS.developerRegion, "Developer");
  developerRegion.section.style.border = "none";
  developerRegion.section.style.background = "transparent";
  developerRegion.section.style.padding = "0";
  developerRegion.section.style.marginTop = "12px";
  developerRegion.section.style.borderTop = "1px solid #34343a";
  developerRegion.section.style.paddingTop = "10px";
  const developerToggle = button("▸ Developer", () => {
    const panel = currentAgentPanel();
    if (!panel) {
      return;
    }
    panel.state.developerExpanded = !panel.state.developerExpanded;
    composerRenderDeveloperSection(panel, composerRenderDeps());
  });
  developerToggle.id = PANEL_IDS.developerToggle;
  Object.assign(developerToggle.style, {
    width: "100%",
    justifyContent: "space-between",
    background: "#1d2027",
  });
  if (developerRegion.body?.parentNode && typeof developerRegion.body.parentNode.removeChild === "function") {
    developerRegion.body.parentNode.removeChild(developerRegion.body);
  }
  developerRegion.section.appendChild(developerToggle);
  developerRegion.section.appendChild(developerRegion.body);
  settingsPopover.appendChild(developerRegion.section);

  // ── Assemble shell ──────────────────────────────────────────────────────
  shell.appendChild(header);
  shell.appendChild(metaRow);
  shell.appendChild(thread);
  shell.appendChild(composer);
  shell.appendChild(settingsPopover);
  root.appendChild(shell);

  // ── Cmd/Ctrl+Enter in the prompt box submits the edit ──────────────────────
  // ComfyUI binds Ctrl/Cmd+Enter globally to "Queue Prompt" via a bubble-phase
  // window keydown listener. A listener ON the textarea (the event target) runs
  // before any ancestor bubble-phase listener, so stopping propagation here
  // keeps the shortcut scoped to the prompt box: it sends the agent query and
  // never reaches ComfyUI's executor. Anywhere outside the prompt box the
  // native Comfy binding is left untouched.
  if (typeof textarea.addEventListener === "function") {
    textarea.addEventListener("keydown", (event) => {
      if (event?.key === "Enter" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === "function") {
          event.stopImmediatePropagation();
        }
        submitAgentEdit(currentAgentPanel());
      }
    });
  }

  // ── Click outside the settings popover closes it ───────────────────────────
  // The gear toggles `settingsPopover`. While it's open, a mousedown anywhere
  // that isn't inside the popover (the rest of the side panel, or the ComfyUI
  // canvas behind it) dismisses it. The gear itself is excluded so its own
  // click toggles the popover rather than closing it here and reopening on the
  // click that follows.
  if (typeof document !== "undefined" && typeof document.addEventListener === "function") {
    document.addEventListener("mousedown", (event) => {
      if (settingsPopover.style.display === "none") {
        return;
      }
      const target = event?.target;
      const insidePopover =
        typeof settingsPopover.contains === "function" && settingsPopover.contains(target);
      const onGear =
        typeof settingsGearBtn.contains === "function" && settingsGearBtn.contains(target);
      if (!insidePopover && !onGear) {
        settingsPopover.style.display = "none";
      }
    });
  }

  const panel = {
    panelId,
    root,
    shell,
    thread,
    metaRow,
    status,
    settingsPopover,
    fields: {
      prompt: textarea,
      route: routeSelect,
      pipelineMode: pipelineModeSelect,
      model: modelInput,
      apiKey: apiKeyInput,
      researchContribution: researchContributionControl,
    },
    buttons: {
      submit: submitBtn,
      apply: applyBtn,
      resumeApply: resumeApplyBtn,
      reject: rejectBtn,
      rollback: rollbackBtn,
      undo: undoBtn,
      close: closeBtn,
      settingsTest,
      stop: stopBtn,
      newConversation: newConvBtn,
      havingIssues: havingIssuesBtn,
    },
    sections: {
      thread: threadRegion.body,
      chat: chatRegion.body,
      history: historyRegion.body,
      candidate: candidateRegion.body,
      failure: failureRegion.body,
      queue: queueRegion.body,
      audit: auditRegion.body,
      debug: debugRegion.body,
      developer: developerRegion.body,
      composerNotice,
    },
    composerButtons,
    pendingDirtySections: [],
    __renderErrors: [],
    __renderFailureCounts: {},
    state: {
      // Lifecycle-owned fields (authority: agent_edit_lifecycle.js)
      ...createAgentEditState(),
      // Non-lifecycle fields (read by store handlers but write-owned elsewhere)
      history: [],
      // Compatibility mirror: derived execution/diagnostic turn feed owned by
      // the agent panel frontend compatibility layer. Delete after all normal
      // consumers/tests read ExecutionEvent selectors directly.
      turns: [],
      undoStack: [],
      settingsMessage: null,
      settingsMessageKind: null,
      settingsAutosaveToken: 0,
      researchContributionEnabled: getPersistedResearchContributionEnabled(),
      researchContributionMessage: null,
      lastAutosavedModel: "",
      providerTestInFlight: false,
      developerExpanded: false,
      statusSnapshot: null,
      vibeComfyInfoSnapshot: null,
      statusRetry: null,
      statusRequestEpoch: 0,
      vibeComfyInfoRequestEpoch: 0,
      vibeComfyInfoStatus: { kind: "loading" },
      routeStatus: {
        kind: ROUTE_STATUS_KIND.LOADING,
        requestedRoute: "auto",
        model: null,
      },
      lastVibeComfyInfoDiagnostic: null,
      executorProgress: createExecutorProgressSnapshot(),
      queueGuard: getQueueGuardStateForPanel(),
      previewEnabled: false,
      expandedTurnKeys: {},
      expandedBubbleTurnKeys: {},
      // Compatibility/debug cache: retained raw-ish detail snapshots for
      // explicit Audit/Debug/download affordances. Delete after those surfaces
      // read ResponseDetail/AuditArtifact/debug selectors directly.
      turnDetailSnapshots: {},
      // Chat / session rehydration state (M3)
      // Compatibility mirror: safe transcript data owned by the agent panel
      // frontend compatibility layer. Delete after normal consumers/tests read
      // TranscriptMessage selectors and diagnostics stop using raw transcript
      // fallbacks.
      chatMessages: [],
      chatLoaded: false,
      chatError: null,
      chatSessionPath: null,
      chatDetailJsonPath: null,
      chatSessionPathResolved: null,
      chatDetailJsonPathResolved: null,
      mountMode: AGENT_PANEL_MOUNT_MODE.LAUNCHER,
      mountContainer: null,
    },
  };

  // ── Demo preview picker (dev-only, gated by localStorage) ──────────────────
  // When the localStorage flag is absent this is a no-op and leaves the shell
  // layout and direct ES-module load order unchanged.
  panel.previewPicker = installPreviewPicker(panel, {
    headerRight,
    helpers: {
      app,
      applyGraphCandidateInPlace,
      captureCanvasViewportSnapshot,
      fitCanvasViewportToGraphPayload,
      restoreCanvasViewportSnapshot,
      scheduleRenderAgentPanel,
      currentAgentPanel,
      PANEL_STATE,
      RENDER_SECTIONS,
      // T8: Delegate demo Apply/Reject lifecycle work to preview_picker.
      // These helpers let preview_picker fulfill/render obligations,
      // push undo history, announce changed nodes, and restore layout
      // preview baselines without importing from vibecomfy_roundtrip
      // (which would create a circular dependency).
      fulfillLifecycleTransitionObligations,
      // Demo playback replaces the complete transcript locally. Fence any
      // production rehydrate already in flight with the reducer's existing
      // epoch protocol, then reset the keyed bubble renderer after each staged
      // replacement.
      fenceChatRehydrateForDemo(currentPanel) {
        const obligations = transition(currentPanel, "CHAT_REHYDRATE_START");
        return obligations.requestEpoch;
      },
      resetThreadRenderState,
      pushHistory,
      announceChangedNodes,
      extractChangedNodeFeedback,
      restoreLayoutPreviewBaseline,
      clonePlainData,
      refreshPreviewDomOverlay,
      // T12: Demo apply consults the same scope guard as the production
      // apply authority so a candidate from a different workflow tab is
      // refused locally (no POST, no graph mutation).
      assertApplyScopeConsistency,
    },
  });

  // ── Agentic replay toolbar (dev-only, gated by localStorage) ───────────────
  // Local canvas-apply helpers that mirror the existing demo Apply branch in
  // applyAgentCandidate: intent decoration before configure, intent repair
  // after configure, and repaint.  These are passed into the replay module so
  // it can apply/restore graphs without duplicating the roundtrip's own
  // intent-decorate and repair logic.

  /**
   * Apply a replay candidate graph with intent decoration and repair,
   * mirroring the demo Apply branch in applyAgentCandidate.
   * @param {object} candidateGraph - LiteGraph payload to apply
   */
  function applyReplayGraphCandidate(candidateGraph) {
    if (!candidateGraph) return;
    let repairCandidate = null;
    try {
      applyGraphCandidateInPlace(app, candidateGraph, {
        beforeConfigure(nextCandidate) {
          decorateIntentGraphPayload(nextCandidate);
          repairCandidate = clonePlainData(nextCandidate);
        },
        afterConfigure(_graph, nextCandidate) {
          repairLiveIntentNodesFromCandidate(repairCandidate || nextCandidate);
        },
        repaint: true,
      });
    } catch (e) {
      console.warn("[vibecomfy] replay candidate graph apply failed:", e);
    }
  }

  /**
   * Apply (restore) an original graph.  Uses the same path as the candidate
   * helper for consistency.
   * @param {object} originalGraph - LiteGraph payload to apply
   */
  function applyReplayOriginalGraph(originalGraph) {
    if (!originalGraph) return;
    let repairCandidate = null;
    try {
      applyGraphCandidateInPlace(app, originalGraph, {
        beforeConfigure(nextCandidate) {
          decorateIntentGraphPayload(nextCandidate);
          repairCandidate = clonePlainData(nextCandidate);
        },
        afterConfigure(_graph, nextCandidate) {
          repairLiveIntentNodesFromCandidate(repairCandidate || nextCandidate);
        },
        repaint: true,
      });
    } catch (e) {
      console.warn("[vibecomfy] replay original graph apply failed:", e);
    }
  }

  panel.agenticReplay = installAgenticReplay(panel, {
    headerRight,
    helpers: {
      app,
      applyGraphCandidateInPlace,
      scheduleRenderAgentPanel,
      currentAgentPanel,
      PANEL_STATE,
      RENDER_SECTIONS,
    },
    applyReplayGraphCandidate,
    applyReplayOriginalGraph,
    _panel: panel,
  });

  return panel;
}

function createAgentPanel() {
  const panel = createAgentPanelShell();
  document.body.appendChild(panel.root);
  return panel;
}

function getPanelElementById(panel, id) {
  if (!id) {
    return null;
  }
  if (panel?.root?.querySelector) {
    const match = panel.root.querySelector(`#${id}`);
    if (match) {
      return match;
    }
  }
  if (panel?.root?.querySelectorAll) {
    try {
      const matches = panel.root.querySelectorAll((node) => node?.id === id);
      if (matches?.[0]) {
        return matches[0];
      }
    } catch (_error) {
      // Browser querySelectorAll expects a selector string; the function
      // predicate path is for the local smoke-test DOM shim.
    }
  }
  if (typeof document !== "undefined" && typeof document.getElementById === "function") {
    return document.getElementById(id);
  }
  return null;
}

function isAppendableElement(value) {
  return Boolean(value && typeof value.appendChild === "function");
}

function resolveAgentSidebarMountContainer(candidate) {
  if (isAppendableElement(candidate)) {
    return candidate;
  }
  if (!candidate || typeof candidate !== "object") {
    return null;
  }
  const directKeys = ["container", "element", "el", "root", "target", "mount", "$el"];
  for (const key of directKeys) {
    if (isAppendableElement(candidate[key])) {
      return candidate[key];
    }
  }
  for (const key of directKeys) {
    const nested = candidate[key];
    if (!nested || typeof nested !== "object") {
      continue;
    }
    for (const nestedKey of directKeys) {
      if (isAppendableElement(nested[nestedKey])) {
        return nested[nestedKey];
      }
    }
  }
  return null;
}

function applyAgentPanelMount(panel, { mode = AGENT_PANEL_MOUNT_MODE.LAUNCHER, container = null } = {}) {
  if (!panel?.root || typeof document === "undefined") {
    return null;
  }
  const sidebarContainer =
    mode === AGENT_PANEL_MOUNT_MODE.SIDEBAR
      ? resolveAgentSidebarMountContainer(container)
      : null;
  const target = sidebarContainer || document.body;
  if (target && panel.root.parentNode !== target) {
    target.appendChild(panel.root);
  }

  panel.state.mountMode = sidebarContainer
    ? AGENT_PANEL_MOUNT_MODE.SIDEBAR
    : AGENT_PANEL_MOUNT_MODE.LAUNCHER;
  panel.state.mountContainer = sidebarContainer;
  panel.root.dataset.mountMode = panel.state.mountMode;

  if (sidebarContainer) {
    // The ComfyUI sidebar content container is often height:auto, so
    // height:100% resolves to auto and the panel grows with the conversation
    // instead of scrolling internally (the outer sidebar then scrolls the
    // WHOLE panel, composer included). Pin the panel to the visible viewport
    // below the container's top edge so the thread wrapper scrolls.
    let boundedHeight = "100%";
    try {
      const rect = typeof sidebarContainer.getBoundingClientRect === "function"
        ? sidebarContainer.getBoundingClientRect()
        : null;
      const viewportH = typeof window !== "undefined" && Number.isFinite(window.innerHeight)
        ? window.innerHeight
        : 0;
      if (rect && viewportH > 0 && Number.isFinite(rect.top) && viewportH - rect.top >= 240) {
        boundedHeight = `${Math.round(viewportH - rect.top)}px`;
      }
    } catch (_e) {
      // keep 100%
    }
    Object.assign(panel.root.style, {
      position: "relative",
      inset: "auto",
      top: "auto",
      right: "auto",
      width: "100%",
      height: boundedHeight,
      maxHeight: boundedHeight,
      minHeight: "0",
      overflow: "hidden",
      zIndex: "auto",
      pointerEvents: "auto",
      transform: "none",
      transition: "none",
    });
    Object.assign(panel.shell.style, {
      borderLeft: "none",
      boxShadow: "none",
    });
  } else {
    Object.assign(panel.root.style, {
      position: "fixed",
      top: "0",
      right: "0",
      width: "420px",
      height: "100vh",
      minHeight: "",
      zIndex: "9999",
      pointerEvents: "none",
      transform: "translateX(432px)",
      transition: "transform 140ms ease",
    });
    Object.assign(panel.shell.style, {
      borderLeft: "1px solid #282a32",
      boxShadow: "-10px 0 28px rgba(0,0,0,0.38)",
    });
  }
  return target;
}

// ── Chat rehydration ──────────────────────────────────────────────────────
// ── T8: Scope-aware rehydrate ─────────────────────────────────────────────
// Rehydrate reads the session id through scoped session-storage (SD2) so
// duplicate tabs fork their conversation.  The scope and request epoch are
// captured at start; when the async fetch resolves the handler refuses to
// commit if the visible panel has switched to a different scope in the
// meantime (race-safe).  Backward-compatible: when no chatScopeId is set
// (first open before scope resolver runs) the legacy localStorage scalar
// is used as fallback.
async function _rehydrateChat(panel) {
  if (!panel || !panel.state) {
    return;
  }
  const startObligations = transition(panel, "CHAT_REHYDRATE_START");
  fulfillLifecycleTransitionObligations(panel, startObligations);
  // ── SD1: Reload-orphan submit recovery.  After rehydration begins (and
  // before the chat fetch / any new submit is possible), detect a SUBMITTING
  // phase that lost its in-memory submit bookkeeping to a page reload and
  // recover it to a terminal failure envelope.  Safe no-op otherwise.
  recoverReloadOrphanSubmit(panel);
  const requestEpoch = startObligations.requestEpoch;

  // ── T8: Scope-aware session resolution ─────────────────────────────────
  const requestScopeId = panel.state.chatScopeId || null;
  const scopedSessionId = requestScopeId
    ? resolveScopeSessionId(requestScopeId)
    : null;
  // Fall back to legacy localStorage when scope is not yet set.
  let savedId = scopedSessionId || _lsGet(LS_ACTIVE_SESSION_KEY);

  if (!savedId) {
    // ── Scope-switch recovery: the in-flight submit's scope→session binding
    // may have been lost (a workflow-tab switch aborts the fetch and drops the
    // stale response, while the server completes the turn and persists it
    // durably).  Recover the session id from the durable store by the one
    // identity the client still knows — the workflow UUID it submitted with —
    // so the completed turn rehydrates instead of showing an empty thread.
    let recoveredId = null;
    if (requestScopeId) {
      try {
        const activeWorkflowId = resolveActiveWorkflowUuid();
        if (activeWorkflowId) {
          const recoverRes = await fetch(
            `/vibecomfy/agent-edit/recover?workflow_id=${encodeURIComponent(activeWorkflowId)}`,
          );
          if (recoverRes.ok) {
            const recoverPayload = await recoverRes.json();
            const candidate = recoverPayload && typeof recoverPayload === "object"
              ? recoverPayload.session_id
              : null;
            if (
              typeof candidate === "string"
              && candidate
              && panel.state.chatScopeId === requestScopeId
            ) {
              setScopedSessionId(requestScopeId, candidate);
              recoveredId = candidate;
            }
          }
        }
      } catch (_recoverError) {
        // Best-effort recovery; fall through to the no-session path.
      }
    }
    if (!recoveredId) {
      const noSessionObligations = transition(panel, "CHAT_REHYDRATE_NO_SESSION", { requestEpoch });
      fulfillAgentPanelCommitObligations(panel, noSessionObligations, "rehydrate");
      resetThreadRenderState(panel);
      return;
    }
    savedId = recoveredId;
  }

  try {
    await nextMacrotask();
    const res = await fetch(`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(savedId)}`);
    if (!res.ok) {
      throw new Error(`Server returned ${res.status}`);
    }
    const rawPayload = await res.json();

    // ── T8: Scope guard — refuse to commit if the panel has switched scopes
    // while the fetch was in flight.  Stale responses must never mutate the
    // visible panel state of a different workflow.
    if (requestScopeId && panel.state.chatScopeId !== requestScopeId) {
      return;
    }

    const payload = normalizeChatRehydratePayload(rawPayload);
    if (payload && payload.ok === true) {
      if (payload.exists === false) {
        // Re-check scope guard before missing-session transition.
        if (requestScopeId && panel.state.chatScopeId !== requestScopeId) {
          return;
        }
        const missingSessionObligations = transition(panel, "CHAT_REHYDRATE_MISSING_SESSION", {
          requestEpoch,
          sessionId: savedId,
        });
        fulfillAgentPanelCommitObligations(panel, missingSessionObligations, "rehydrate");
        resetThreadRenderState(panel);
        return;
      }
      const messages = Array.isArray(payload.messages) ? payload.messages : [];
      // Normalize field changes on each rehydrated message for chat-bubble rendering (M4b).
      for (const msg of messages) {
        if (msg && typeof msg === "object") {
          msg.field_changes = normalizeFieldChangesFromMessage(msg.raw || msg);
        }
      }
      const lifecyclePayload = {
        requestEpoch,
        messages,
        pipelineMode: payload.pipelineMode,
        chatSessionPath: payload.sessionPath,
        chatDetailJsonPath: payload.detailJsonPath,
        chatSessionPathResolved: payload.sessionPathResolved,
        chatDetailJsonPathResolved: payload.detailJsonPathResolved,
        sessionId: payload.sessionId,
        latestTurnId: payload.latestTurnId,
        baselineTurnId: payload.baselineTurnId,
        baselineGraphHash: payload.baselineGraphHash,
        baselineGraphHashKind: payload.baselineGraphHashKind,
        baselineGraphHashVersion: payload.baselineGraphHashVersion,
        baselineSource: payload.baselineSource,
        baselineRebaselineId: payload.baselineRebaselineId,
        baselineGraphSourcePath: payload.baselineGraphSourcePath,
        latestCandidate: payload.latestCandidate,
        latestTurnLifecycle: payload.latestTurnLifecycle,
      };
      const ingestedChatRehydratePayload = ingestChatRehydratePayload(
        panel.state,
        lifecyclePayload,
      );
      const successObligations = transition(panel, "CHAT_REHYDRATE_SUCCESS", {
        ...lifecyclePayload,
        ingestedChatRehydratePayload,
      });
      if (successObligations.stale) {
        return;
      }
      // ── T8: Persist session back to scoped storage so subsequent reopens
      // on this scope use the correct session id.
      if (requestScopeId && typeof payload.sessionId === "string" && payload.sessionId) {
        setScopedSessionId(requestScopeId, payload.sessionId);
      }
      if (panel.fields.pipelineMode) {
        panel.fields.pipelineMode.value = normalizePipelineMode(payload.pipelineMode);
        _lsSet(PIPELINE_MODE_STORAGE_KEY, panel.fields.pipelineMode.value);
      }
      fulfillAgentPanelCommitObligations(panel, successObligations, "rehydrate");
      resetThreadRenderState(panel);
      // ── T8: Pass requestScopeId so restoreLatestCandidateFromChat can
      // refuse cross-scope / cross-session candidate restores.
      await restoreLatestCandidateFromChat(panel, payload, requestScopeId);
      if (applyFlow.isV2ApplyCandidate(panel)) {
        try {
          await reconcilePreparedTransactionState(panel);
        } catch (error) {
          console.warn("[vibecomfy] transaction reconcile after rehydrate failed:", safePreviewLogDetail(error));
        }
      }
      renderAgentPanel(panel, { dirtySections: [RENDER_SECTIONS.META, RENDER_SECTIONS.THREAD] });
    } else {
      throw new Error(payload.raw?.error || "chat endpoint returned ok: false");
    }
  } catch (_e) {
    // ── T8: Scope guard before committing failure.
    if (requestScopeId && panel.state.chatScopeId !== requestScopeId) {
      return;
    }
    const failureObligations = transition(panel, "CHAT_REHYDRATE_FAILURE", {
      requestEpoch,
      chatError: String(_e),
    });
    if (failureObligations.stale) {
      return;
    }
    fulfillAgentPanelCommitObligations(panel, failureObligations, "rehydrate");
    resetThreadRenderState(panel);
  }
}

// ── SD1: Reload-orphan submit recovery helper ──────────────────────────────
// On page reload a previously SUBMITTING phase can be rehydrated into panel
// state while the in-memory in-flight submit promise (inFlightSubmit) and the
// finite submitStartedAtMs are lost.  Such a state can never resolve, so fail
// closed to a terminal ERROR envelope carrying recovery metadata
// (session_id, turn_id, recovery_reason, url, next_action) instead of leaving
// the UI wedged.  Invoked from openAgentPanel via _rehydrateChat after
// rehydration begins and before another submit is possible.  Pure predicate
// check + existing lifecycle transition; no new HTTP/DOM contracts.
export function recoverReloadOrphanSubmit(panel) {
  if (!panel || !panel.state) {
    return false;
  }
  if (panel.state.phase !== PANEL_STATE.SUBMITTING) {
    return false;
  }
  if (panel.state.inFlightSubmit) {
    return false;
  }
  if (Number.isFinite(panel.state.submitStartedAtMs)) {
    return false;
  }
  // Best-effort: abort any stale controller before transitioning so a dead
  // request can never be resurrected by later code.
  try {
    const controller = panel.state.submitAbortController;
    if (controller && typeof controller.abort === "function") {
      controller.abort();
    }
  } catch (_err) {
    // Recovery must not depend on controller health; ignore abort failures.
  }
  const message = "Your last edit didn't finish because the page reloaded. Please try again.";
  const obligations = transition(panel, "SUBMIT_RELOAD_ORPHAN_RECOVERY", {
    failure: {
      session_id: panel.state.sessionId || null,
      turn_id: panel.state.turnId || null,
      recovery_reason: "page_reload_orphan",
      url: "/vibecomfy/agent-executor",
      next_action: "resubmit_or_refresh",
      message,
    },
    syntheticAgentMessage: {
      role: "agent",
      text: message,
      session_id: panel.state.sessionId || null,
      synthetic: true,
      local_id: `recovery:reload_orphan:${Date.now()}`,
    },
    debugPayload: {
      recovery_reason: "page_reload_orphan",
      url: "/vibecomfy/agent-executor",
      next_action: "resubmit_or_refresh",
      session_id: panel.state.sessionId || null,
      turn_id: panel.state.turnId || null,
      last_submit: panel.state.lastSubmit || null,
    },
  });
  fulfillLifecycleTransitionObligations(panel, obligations);
  renderLifecycleTransition(panel, obligations);
  return true;
}

// ── T9: Scope-aware session persistence ──────────────────────────────────
// Scoped sessions live only in sessionStorage. The legacy localStorage scalar
// remains a no-scope compatibility fallback and is never refreshed once a
// workflow scope is known.
function _persistActiveSession(sessionId, scopeId = null) {
  const resolvedScopeId = scopeId || _activeScopeId();
  if (resolvedScopeId) {
    if (typeof sessionId === "string" && sessionId) {
      setScopedSessionId(resolvedScopeId, sessionId);
    } else {
      forgetScopedSessionId(resolvedScopeId);
    }
    return;
  }
  if (typeof sessionId === "string" && sessionId) {
    _lsSet(LS_ACTIVE_SESSION_KEY, sessionId);
  }
}

// ── T8: Scope-aware latest-candidate restore ──────────────────────────────
// Accepts requestScopeId from the calling _rehydrateChat so it can refuse
// to restore when:
//   1. The visible panel has switched to a different scope since the fetch
//      was initiated (cross-scope refusal).
//   2. The candidate's session id does not match the scoped session bound
//      to the active scope (cross-session refusal).
// When no scope is active (requestScopeId is null) the legacy behaviour
// is preserved.
async function restoreLatestCandidateFromChat(panel, payload, requestScopeId = null) {
  const latest = payload?.latestCandidate || null;
  if (!panel?.state || !latest || typeof latest !== "object") {
    return;
  }

  // ── T8: Scope guard — refuse if the panel has switched scopes since the
  // rehydrate fetch was initiated.  A candidate from scope A must never
  // populate the visible panel when scope B is active.
  if (requestScopeId && panel.state.chatScopeId !== requestScopeId) {
    return;
  }

  switch (latest.outcome?.kind || null) {
    case "candidate":
      break;
    case "noop":
    case "clarify":
    case "error":
    default:
      return;
  }
  const latestApplyCandidate = readRoundtripApplyCandidate(latest, { endpoint: "chat:latest-candidate" });
  const latestIdentity = readRoundtripTurnIdentity(latest, { endpoint: "chat:latest-candidate" });
  const candidateGraph = prepareCandidateGraphForPanel(latestApplyCandidate?.graph || null);
  if (!candidateGraph || typeof candidateGraph !== "object") {
    return;
  }

  // ── T8: Cross-session refusal — when a scope is active, the candidate's
  // session id must match the session bound to this scope.  A rehydrate
  // response for scope A's session must never restore a candidate into
  // scope B even if the panel hasn't switched mid-flight.
  if (requestScopeId) {
    const scopeSession = resolveScopeSessionId(requestScopeId);
    const candidateSessionId = latestIdentity?.sessionId || null;
    if (scopeSession && candidateSessionId && scopeSession !== candidateSessionId) {
      return;
    }
  }

  const eligibility = latestApplyCandidate?.eligibility;
  const normalizedEligibility = applyFlow.normalizeCandidateApplyEligibility(candidateGraph, eligibility);
  if (
    TERMINAL_CANDIDATE_STATES.has(String(latestApplyCandidate?.state || latest?.candidate?.state || latest?.state || ""))
    || TERMINAL_CANDIDATE_ELIGIBILITY_REASONS.has(String(normalizedEligibility?.reason || eligibility?.reason || ""))
    || latest?.action === "reject"
    || latest?.action === "accept"
  ) {
    return;
  }
  const restoredActionAllowed = Boolean(
    candidateGraph
    && (latestApplyCandidate?.applyable === true || normalizedEligibility?.applyable === true),
  );
  const candidateTransaction = readCandidateTransaction(latest)
    || normalizeCandidateTransaction(
      payload?.latestTurnLifecycle?.candidateTransaction
        || payload?.latestTurnLifecycle?.candidate_transaction,
    );
  const hasRuntimeDependencyProjection = Boolean(
    Array.isArray(latest?.raw?.runtimeDependencies)
    || Array.isArray(latest?.raw?.runtime_dependencies),
  );
  const restoreObligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    // ── T8: Pass scope context so the lifecycle handler can enforce
    // cross-scope and cross-session boundary refusals.
    requestScopeId: requestScopeId || null,
    candidateSessionId: latestIdentity?.sessionId || null,
    sessionId: latestIdentity?.sessionId || null,
    turnId: latestIdentity?.turnId || null,
    baselineTurnId: latestIdentity?.baselineTurnId || null,
    baseline: latest,
    candidateTransaction,
    candidateGraph,
    candidateGraphHash:
      latestApplyCandidate?.candidateGraphHash
      || latestApplyCandidate?.graphHash
      || null,
    candidateReport: latest.report && typeof latest.report === "object" ? clonePlainData(latest.report) : null,
    ...(hasRuntimeDependencyProjection
      ? {
          runtimeDependencies: Array.isArray(latest.runtimeDependencies)
            ? clonePlainData(latest.runtimeDependencies)
            : [],
        }
      : {}),
    serverSubmitGraphHash: latestApplyCandidate?.submitGraphHash || null,
    message: typeof latest.message === "string" ? latest.message : null,
    applyEligibility: normalizedEligibility,
    applyAllowed: restoredActionAllowed,
    canvasApplyAllowed: restoredActionAllowed,
    queueAllowed: Boolean(latest.queueAllowed),
    auditRef: latest.auditRef || panel.state.auditRef || null,
    changeDetails: latest.raw?.change_details && typeof latest.raw.change_details === "object"
      ? clonePlainData(latest.raw.change_details)
      : null,
    debugPayload: scrubDebugPayload({
      ...(latest.raw || latest),
      restored_from_chat: true,
    }),
    lastSubmitFieldChanges: normalizeFieldChangesFromSubmit(latest.raw || latest),
  });
  if (!restoreObligations.restored) {
    return;
  }
  fulfillAgentPanelCommitObligations(panel, restoreObligations, "rehydrate");
  const preparedBaseline = latest.raw?.prepared_baseline;
  if (
    ["prepared", "apply_prepared"].includes(String(latest.raw?.turn_state || ""))
    && preparedBaseline?.graph
    && typeof preparedBaseline.graph === "object"
    && typeof preparedBaseline.structural_graph_hash === "string"
    && preparedBaseline.structural_graph_hash
  ) {
    // This is transaction compensation authority, not user-visible Undo
    // history. It survives reload through the server's original.ui.json and
    // is consumed only when the interrupted prepare is cancelled.
    pendingTransactionSnapshotByPanel.set(panel, {
      graph: clonePlainData(preparedBaseline.graph),
      graphHash: preparedBaseline.graph_hash || null,
      structuralHash: preparedBaseline.structural_graph_hash,
      candidateStructuralHash:
        latest.raw?.candidate_structural_graph_hash
        || candidateTransaction?.hashes?.candidate_structural_graph_hash
        || null,
      rehydrated: true,
    });
  }
  reconcileResponseBatchTurns(panel, latest);
  rememberTurnDetailSnapshot(panel, {
    turn_id: panel.state.turnId,
    session_id: panel.state.sessionId,
    candidateGraphPresent: true,
    candidateTransaction: panel.state.candidateTransaction,
    candidateReport: panel.state.candidateReport,
    applyEligibility: panel.state.applyEligibility,
    queueAllowed: panel.state.queueAllowed,
    canvasApplyAllowed: panel.state.canvasApplyAllowed,
    auditRef: panel.state.auditRef,
    debugPayload: panel.state.debugPayload,
    fieldChanges: panel.state.lastSubmitFieldChanges,
    changeDetails: panel.state.changeDetails,
    message: panel.state.message,
  });
  try {
    await activateLayoutPreviewIfNeeded(panel);
  } catch (error) {
    console.warn("[vibecomfy] layout preview activation after rehydrate failed:", safePreviewLogDetail(error));
  }
}

// ── T9: Return the active scope id from the current panel, if any. ────────
function _activeScopeId() {
  const panel = currentAgentPanel();
  if (panel?.state && typeof panel.state.chatScopeId === "string" && panel.state.chatScopeId) {
    return panel.state.chatScopeId;
  }
  return null;
}

// ── T9: Scope-aware session forget ───────────────────────────────────────
// Clear only the scoped sessionStorage binding when a scope is active. The
// legacy localStorage scalar is cleared only in no-scope compatibility mode.
function forgetActiveSession(scopeId = null) {
  const resolvedScopeId = scopeId || _activeScopeId();
  if (resolvedScopeId) {
    forgetScopedSessionId(resolvedScopeId);
    return;
  }
  _lsRemove(LS_ACTIVE_SESSION_KEY);
}

function fulfillAgentPanelCommitObligations(panel, obligations = {}, commitKind) {
  if (Array.isArray(obligations?.dirtySections) && obligations.dirtySections.length) {
    markAgentPanelDirtyAfterCommit(panel, obligations.dirtySections, commitKind);
    fulfillLifecycleTransitionObligations(panel, {
      ...obligations,
      dirtySections: [],
    });
    return;
  }
  noteAgentPanelCommit(panel, commitKind);
  fulfillLifecycleTransitionObligations(panel, obligations);
}

function rerenderAgentPanelIfMounted(panel = currentAgentPanel()) {
  if (!panel?.root) {
    return;
  }
  if (!isAgentPanelRootConnected(panel)) {
    return;
  }
  renderDirtyAgentPanelSections(panel);
}

export function ensureAgentPanel() {
  const existingPanel = currentAgentPanel();
  if (existingPanel) {
    return existingPanel;
  }
  if (!currentAgentPanel()) {
    // Create the panel shell only. Chat rehydration happens on open
    // (openAgentPanel), not on mere creation, so extension setup and launcher
    // wiring don't trigger a premature/duplicate chat fetch.
    setCurrentAgentPanel(createAgentPanel());
  }
  return currentAgentPanel();
}

export function debugAgentPanelSnapshot(panel = currentAgentPanel()) {
  return buildAgentPanelDebugSnapshot(panel);
}

function openAgentPanel({ mode = AGENT_PANEL_MOUNT_MODE.LAUNCHER, container = null } = {}) {
  const panel = ensureAgentPanel();
  applyAgentPanelMount(panel, { mode, container });
  panel.root.dataset.open = "1";
  panel.root.style.pointerEvents = "auto";
  panel.root.style.transform = "translateX(0)";
  setAgentLauncherVisible(false);
  panel.state.queueGuard = getQueueGuardStateForPanel();
  // Rehydrate chat on open (best-effort) — exactly one fetch per open.
  // Creation (ensureAgentPanel) intentionally does not fetch, so this single
  // call covers both first open and reopen.
  _rehydrateChat(panel).then(() => {
    scheduleRenderAgentPanel("rehydrate", panel);
  }).catch((err) => {
    console.warn("[vibecomfy] chat rehydration render failed", err);
  });
  renderAgentPanel(panel);
  const persisted = getPersistedAgentProvider();
  if (persisted) {
    panel.fields.route.value = persisted;
    pollerPopulateRouteSelect(panel.fields.route, null, { selectedRoute: persisted }, agentStatusDeps());
  }
  pollerRefreshAgentStatus(panel, { quiet: true }, agentStatusDeps());
  refreshResearchContributionSetting(panel);
  ensureScheduledAgentPanelDirtyFlush(panel, "open-backstop");
  return panel;
}

function mountAgentSidebarPanel(container = null) {
  const panel = openAgentPanel({
    mode: AGENT_PANEL_MOUNT_MODE.SIDEBAR,
    container,
  });
  panel.root.dataset.lastCommand = "agent-sidebar";
  renderAgentPanel(panel);
  return panel.root;
}

function closeAgentPanel(panel) {
  panel.root.dataset.open = "0";
  panel.root.style.pointerEvents = "none";
  panel.root.style.transform = "translateX(432px)";
  setAgentLauncherVisible(true);
}

// Show/hide the floating edge launcher. Hidden while the panel is open (it would
// just overlap the panel); shown again on close so the user can reopen.
function setAgentLauncherVisible(visible) {
  if (typeof document === "undefined") {
    return;
  }
  const launcher = document.getElementById("vibecomfy-agent-launcher");
  if (launcher) {
    // Restore the launcher's flex layout explicitly. Using "" would clear the
    // inline display and revert the button to its default inline-block, which
    // drops the flex column gap and collapses the logo onto the label on reopen.
    launcher.style.display = visible ? "flex" : "none";
  }
}

function option(value, label, ownerDocument = null) {
  const doc = ownerDocument || (typeof document !== "undefined" ? document : null);
  if (!doc) {
    throw new ReferenceError("document is not defined");
  }
  const node = doc.createElement("option");
  node.value = value;
  node.textContent = label;
  return node;
}

function pushHistory(panel, kind, message) {
  panel.state.history.unshift({
    kind,
    message,
    at: new Date().toISOString(),
  });
  panel.state.history = panel.state.history.slice(0, 8);
  markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
}

const TERMINAL_CANDIDATE_STATES = new Set([
  "accepted",
  "rejected",
  "discarded",
  "superseded",
  "unknown",
]);
const TERMINAL_CANDIDATE_ELIGIBILITY_REASONS = new Set(["no_candidate", "superseded", "not_latest"]);

function syncExecutionEventIndexes(panel) {
  ensureRoundtripBoundaryCompartments(panel);
  const executionEventsByKey = {};
  panel.state.executionEvents.forEach((event, index) => {
    const eventKey = event?.event_key || executionEventKeyForTurn(event?.turnEntry || event, index);
    if (eventKey) {
      executionEventsByKey[eventKey] = index;
    }
  });
  panel.state.compartmentIndexes.executionEventsByKey = executionEventsByKey;
}

function syncTurnsCompatibilityMirror(panel) {
  if (!panel?.state) {
    return [];
  }
  ensureRoundtripBoundaryCompartments(panel);
  // Compatibility mirror contract: panel.state.turns is a derived
  // execution/diagnostic mirror owned by the agent panel frontend compatibility
  // layer. It is not normal renderer input. Delete after diagnostics, reports,
  // and tests consume selectExecutionEvents/selectAuditArtifacts directly.
  const turns = [];
  for (const event of panel.state.executionEvents) {
    const entry = executionEventTurnEntry(event);
    if (entry) {
      turns.push(entry);
    }
  }
  panel.state.turns = sortPanelTurns(turns);
  return panel.state.turns;
}

function upsertExecutionEvent(panel, rawEvent, options = {}) {
  if (!panel?.state || !rawEvent || typeof rawEvent !== "object") {
    return null;
  }
  ensureRoundtripBoundaryCompartments(panel);
  const turnEntry = options.turnEntry
    ? clonePlainData(options.turnEntry)
    : (rawEvent.entry_type === "batch" || rawEvent.entry_type === "durable" ? clonePlainData(rawEvent) : null);
  const eventKey = options.eventKey || executionEventKeyForTurn(turnEntry || rawEvent);
  const projected = projectExecutionEvent({
    ...rawEvent,
    session_id: rawEvent.session_id || turnEntry?.session_id,
    turn_id: rawEvent.turn_id || turnEntry?.turn_id,
    status: rawEvent.status || turnEntry?.status,
    message: rawEvent.message || turnEntry?.message,
  });
  const incoming = {
    ...(projected ? clonePlainData(projected) : {}),
    ...clonePlainData(rawEvent),
    event_key: eventKey,
    mirror: options.mirror === false ? false : true,
    turnEntry,
  };
  const currentIndex = panel.state.compartmentIndexes.executionEventsByKey?.[eventKey];
  if (Number.isInteger(currentIndex) && currentIndex >= 0 && currentIndex < panel.state.executionEvents.length) {
    const existing = panel.state.executionEvents[currentIndex];
    const existingTurn = executionEventTurnEntry(existing);
    const mergedTurn = turnEntry?.entry_type === "batch" && existingTurn?.entry_type === "batch"
      ? mergeBatchTurnEntry(existingTurn, turnEntry)
      : (turnEntry || existingTurn);
    panel.state.executionEvents[currentIndex] = {
      ...existing,
      ...incoming,
      turnEntry: mergedTurn,
      debugPayload: incoming.debugPayload || existing.debugPayload || null,
      reasoning: Array.isArray(incoming.reasoning) && incoming.reasoning.length ? incoming.reasoning : existing.reasoning,
      providerDiagnostics:
        incoming.providerDiagnostics && (
          (Array.isArray(incoming.providerDiagnostics) && incoming.providerDiagnostics.length)
          || (!Array.isArray(incoming.providerDiagnostics) && typeof incoming.providerDiagnostics === "object" && Object.keys(incoming.providerDiagnostics).length)
        )
          ? incoming.providerDiagnostics
          : existing.providerDiagnostics,
      batchTurns: Array.isArray(incoming.batchTurns) && incoming.batchTurns.length ? incoming.batchTurns : existing.batchTurns,
    };
  } else {
    panel.state.executionEvents.push(incoming);
  }
  syncExecutionEventIndexes(panel);
  syncTurnsCompatibilityMirror(panel);
  return incoming;
}

function pushTurnStatus(panel, status, extra = {}) {
  const entry = {
    entry_type: "durable",
    status,
    session_id: extra.session_id || panel.state.sessionId || null,
    turn_id: extra.turn_id || panel.state.turnId || null,
    baseline_turn_id: extra.baseline_turn_id || panel.state.baselineTurnId || null,
    task: extra.task || (panel.state.lastSubmit?.task) || null,
    timestamp: new Date().toISOString(),
    failure_kind: extra.failure_kind || null,
    failure_stage: extra.failure_stage || null,
    message: extra.message || null,
    audit_ref: extra.audit_ref || null,
    raw_payload: extra.raw_payload || null,
  };
  entry.turn_key = durableTurnKey(entry);
  if (status !== "pending" && Array.isArray(panel?.state?.executionEvents)) {
    panel.state.executionEvents = panel.state.executionEvents.filter((event) => {
      const existing = executionEventTurnEntry(event);
      return !(existing?.entry_type === "durable" && existing.status === "pending");
    });
    syncExecutionEventIndexes(panel);
  }
  upsertExecutionEvent(panel, entry, { turnEntry: entry, eventKey: executionEventKeyForTurn(entry) });
  markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
  return entry;
}

function readRoundtripApplyCandidate(source, options = {}) {
  if (!source || typeof source !== "object") {
    return null;
  }
  try {
    return readApplyCandidate(source, { allowLegacy: false, ...options });
  } catch (_e) {
    return null;
  }
}

function normalizeChatMessagePayload(message) {
  if (!message || typeof message !== "object") {
    return message;
  }
  const response = message.response && typeof message.response === "object"
    ? normalizeAgentEditResponse(message.response, {
      endpoint: "chat:message-response",
      allowLegacy: true,
    })
    : null;
  const outcome = message.outcome && typeof message.outcome === "object"
    ? normalizeAgentEditResponse(
      {
        ...message,
        outcome: message.outcome,
      },
      {
        endpoint: "chat:message-outcome",
        allowLegacy: true,
      },
    ).outcome
    : response?.outcome || null;
  const applyCandidate =
    readRoundtripApplyCandidate(response)
    || (() => {
      try {
        return readApplyCandidate(message, {
          endpoint: "chat:message-candidate",
          allowLegacy: true,
        });
      } catch (_e) {
        return null;
      }
    })();
  const identity =
    readRoundtripTurnIdentity(response)
    || (() => {
      try {
        return readTurnIdentity(message, {
          endpoint: "chat:message-identity",
          allowLegacy: true,
        });
      } catch (_e) {
        return null;
      }
    })();
  const candidateGraph = prepareCandidateGraphForPanel(applyCandidate?.graph || null);
  const eligibility = applyCandidate?.eligibility || response?.eligibility || null;
  return {
    ...message,
    raw: message,
    role: typeof message.role === "string" ? message.role : null,
    text: typeof message.text === "string" ? message.text : null,
    turnId: identity?.turnId || null,
    sessionId: identity?.sessionId || null,
    entryType: typeof message.entryType === "string" ? message.entryType : (typeof message.entry_type === "string" ? message.entry_type : null),
    timestamp: typeof message.timestamp === "string" ? message.timestamp : null,
    response,
    outcome,
    candidateGraph,
    eligibility,
  };
}

function normalizeChatRehydratePayload(rawPayload) {
  if (!rawPayload || typeof rawPayload !== "object") {
    throw new Error("chat endpoint must return an object");
  }
  return {
    ...rawPayload,
    raw: rawPayload,
    ok: typeof rawPayload.ok === "boolean" ? rawPayload.ok : null,
    exists: typeof rawPayload.exists === "boolean" ? rawPayload.exists : null,
    sessionId: typeof rawPayload.sessionId === "string"
      ? rawPayload.sessionId
      : (typeof rawPayload.session_id === "string" ? rawPayload.session_id : null),
    sessionPath: typeof rawPayload.sessionPath === "string"
      ? rawPayload.sessionPath
      : (typeof rawPayload.session_path === "string" ? rawPayload.session_path : null),
    detailJsonPath: typeof rawPayload.detailJsonPath === "string"
      ? rawPayload.detailJsonPath
      : (typeof rawPayload.detail_json_path === "string" ? rawPayload.detail_json_path : null),
    sessionPathResolved: typeof rawPayload.sessionPathResolved === "string"
      ? rawPayload.sessionPathResolved
      : (typeof rawPayload.session_path_resolved === "string" ? rawPayload.session_path_resolved : null),
    detailJsonPathResolved: typeof rawPayload.detailJsonPathResolved === "string"
      ? rawPayload.detailJsonPathResolved
      : (typeof rawPayload.detail_json_path_resolved === "string" ? rawPayload.detail_json_path_resolved : null),
    latestTurnId: typeof rawPayload.latestTurnId === "string"
      ? rawPayload.latestTurnId
      : (typeof rawPayload.latest_turn_id === "string" ? rawPayload.latest_turn_id : null),
    baselineTurnId: typeof rawPayload.baselineTurnId === "string"
      ? rawPayload.baselineTurnId
      : (typeof rawPayload.baseline_turn_id === "string" ? rawPayload.baseline_turn_id : null),
    baselineGraphHash: typeof rawPayload.baselineGraphHash === "string"
      ? rawPayload.baselineGraphHash
      : (typeof rawPayload.baseline_graph_hash === "string" ? rawPayload.baseline_graph_hash : null),
    baselineGraphHashKind: typeof rawPayload.baselineGraphHashKind === "string"
      ? rawPayload.baselineGraphHashKind
      : (typeof rawPayload.baseline_graph_hash_kind === "string" ? rawPayload.baseline_graph_hash_kind : null),
    baselineGraphHashVersion:
      rawPayload.baselineGraphHashVersion ?? rawPayload.baseline_graph_hash_version ?? null,
    baselineSource: typeof rawPayload.baselineSource === "string"
      ? rawPayload.baselineSource
      : (typeof rawPayload.baseline_source === "string" ? rawPayload.baseline_source : null),
    baselineRebaselineId: typeof rawPayload.baselineRebaselineId === "string"
      ? rawPayload.baselineRebaselineId
      : (typeof rawPayload.baseline_rebaseline_id === "string" ? rawPayload.baseline_rebaseline_id : null),
    baselineGraphSourcePath: typeof rawPayload.baselineGraphSourcePath === "string"
      ? rawPayload.baselineGraphSourcePath
      : (typeof rawPayload.baseline_graph_source_path === "string" ? rawPayload.baseline_graph_source_path : null),
    latestTurnLifecycle: (() => {
      const lifecycle = rawPayload.latestTurnLifecycle && typeof rawPayload.latestTurnLifecycle === "object"
        ? rawPayload.latestTurnLifecycle
        : (rawPayload.latest_turn_lifecycle && typeof rawPayload.latest_turn_lifecycle === "object"
          ? rawPayload.latest_turn_lifecycle
          : null);
      if (!lifecycle) return null;
      return {
        ...lifecycle,
        turnId: typeof lifecycle.turnId === "string"
          ? lifecycle.turnId
          : (typeof lifecycle.turn_id === "string" ? lifecycle.turn_id : null),
        state: typeof lifecycle.state === "string" ? lifecycle.state : null,
        disposition: typeof lifecycle.disposition === "string" ? lifecycle.disposition : null,
        agentEditProtocol: typeof lifecycle.agentEditProtocol === "string"
          ? lifecycle.agentEditProtocol
          : (typeof lifecycle.agent_edit_protocol === "string" ? lifecycle.agent_edit_protocol : null),
        transactionReceipts: Array.isArray(lifecycle.transactionReceipts)
          ? lifecycle.transactionReceipts
          : (Array.isArray(lifecycle.transaction_receipts) ? lifecycle.transaction_receipts : []),
        candidateTransaction: readCandidateTransaction({
          candidate_transaction: lifecycle.candidate_transaction || lifecycle.candidateTransaction,
        }),
      };
    })(),
    latestCandidate:
      rawPayload.latestCandidate && typeof rawPayload.latestCandidate === "object"
        ? normalizeAgentEditResponse(rawPayload.latestCandidate, { endpoint: "chat:latest_candidate", allowLegacy: true })
        : (rawPayload.latest_candidate && typeof rawPayload.latest_candidate === "object"
          ? normalizeAgentEditResponse(rawPayload.latest_candidate, { endpoint: "chat:latest_candidate", allowLegacy: true })
          : null),
    pipelineMode: normalizePipelineMode(
      rawPayload.pipelineMode ?? rawPayload.pipeline_mode ?? DEFAULT_PIPELINE_MODE,
    ),
    messages: Array.isArray(rawPayload.messages)
      ? rawPayload.messages.map((message) => normalizeChatMessagePayload(message))
      : [],
  };
}

function normalizeAuxiliaryAgentPayload(rawPayload, endpoint) {
  if (!rawPayload || typeof rawPayload !== "object") {
    throw new Error(`${endpoint} response must be an object`);
  }
  const looksLikeOutcomeEnvelope =
    (rawPayload.outcome && typeof rawPayload.outcome === "object")
    || (rawPayload.candidate && typeof rawPayload.candidate === "object")
    || (rawPayload.graph && typeof rawPayload.graph === "object")
    || rawPayload.clarification_required === true
    || rawPayload.graph_unchanged === true;
  if (looksLikeOutcomeEnvelope) {
    return normalizeAgentEditResponse(rawPayload, { endpoint, allowLegacy: true });
  }
  return {
    ...rawPayload,
    raw: rawPayload,
    ok: typeof rawPayload.ok === "boolean" ? rawPayload.ok : null,
    action: typeof rawPayload.action === "string" ? rawPayload.action : null,
    message: typeof rawPayload.message === "string" ? rawPayload.message : null,
    sessionId: typeof rawPayload.sessionId === "string"
      ? rawPayload.sessionId
      : (typeof rawPayload.session_id === "string" ? rawPayload.session_id : null),
    turnId: typeof rawPayload.turnId === "string"
      ? rawPayload.turnId
      : (typeof rawPayload.turn_id === "string" ? rawPayload.turn_id : null),
    baselineTurnId: typeof rawPayload.baselineTurnId === "string"
      ? rawPayload.baselineTurnId
      : (typeof rawPayload.baseline_turn_id === "string" ? rawPayload.baseline_turn_id : null),
    baselineGraphHash: typeof rawPayload.baselineGraphHash === "string"
      ? rawPayload.baselineGraphHash
      : (typeof rawPayload.baseline_graph_hash === "string" ? rawPayload.baseline_graph_hash : null),
    baselineGraphHashKind: typeof rawPayload.baselineGraphHashKind === "string"
      ? rawPayload.baselineGraphHashKind
      : (typeof rawPayload.baseline_graph_hash_kind === "string" ? rawPayload.baseline_graph_hash_kind : null),
    baselineGraphHashVersion:
      rawPayload.baselineGraphHashVersion ?? rawPayload.baseline_graph_hash_version ?? null,
    baselineSource: typeof rawPayload.baselineSource === "string"
      ? rawPayload.baselineSource
      : (typeof rawPayload.baseline_source === "string" ? rawPayload.baseline_source : null),
    baselineRebaselineId: typeof rawPayload.baselineRebaselineId === "string"
      ? rawPayload.baselineRebaselineId
      : (typeof rawPayload.baseline_rebaseline_id === "string" ? rawPayload.baseline_rebaseline_id : null),
    baselineGraphSourcePath: typeof rawPayload.baselineGraphSourcePath === "string"
      ? rawPayload.baselineGraphSourcePath
      : (typeof rawPayload.baseline_graph_source_path === "string" ? rawPayload.baseline_graph_source_path : null),
    submitGraphHash: typeof rawPayload.submitGraphHash === "string"
      ? rawPayload.submitGraphHash
      : (typeof rawPayload.submit_graph_hash === "string" ? rawPayload.submit_graph_hash : null),
    queueAllowed:
      typeof rawPayload.queueAllowed === "boolean"
        ? rawPayload.queueAllowed
        : (typeof rawPayload.queue_allowed === "boolean" ? rawPayload.queue_allowed : null),
    auditRef: rawPayload.auditRef && typeof rawPayload.auditRef === "object"
      ? clonePlainData(rawPayload.auditRef)
      : (rawPayload.audit_ref && typeof rawPayload.audit_ref === "object" ? clonePlainData(rawPayload.audit_ref) : null),
    rebaselineRecovery: extractRebaselineRecovery(rawPayload),
    candidateTransaction: readCandidateTransaction(rawPayload),
  };
}

// ── FieldChange normalization helpers ─────────────────────────────────────
// Normalize FieldChange objects without positional widget inference.
// A FieldChange has the canonical shape: { uid, field_path, old, new }
// These helpers extract and validate FieldChange arrays from submit responses
// and rehydrate chat messages, storing results on panel state and per-message
// detail for later chat-bubble rendering (M4b).

function _isFieldChangeLike(item) {
  return item && typeof item === "object"
    && typeof item.uid === "string" && item.uid
    && (
      (typeof item.fieldPath === "string" && item.fieldPath)
      || (typeof item.field_path === "string" && item.field_path)
    );
}

function _normalizeFieldChange(raw) {
  if (!raw || typeof raw !== "object") return null;
  if (!_isFieldChangeLike(raw)) return null;
  const fieldPath = typeof raw.fieldPath === "string" && raw.fieldPath
    ? raw.fieldPath
    : raw.field_path;
  return {
    uid: raw.uid,
    field_path: fieldPath,
    old: "old" in raw ? raw.old : undefined,
    new: "new" in raw ? raw.new : undefined,
  };
}

function _normalizeFieldChangeList(rawList) {
  if (!Array.isArray(rawList)) return [];
  const result = [];
  for (const raw of rawList) {
    const normalized = _normalizeFieldChange(raw);
    if (normalized) result.push(normalized);
  }
  return result;
}

function _compactNetFieldChanges(changes) {
  const byField = new Map();
  for (const change of changes) {
    if (!change?.uid || !change?.field_path) continue;
    const key = `${change.uid}::${change.field_path}`;
    const previous = byField.get(key);
    byField.set(key, previous
      ? { ...change, old: previous.old }
      : { ...change });
  }
  return Array.from(byField.values()).filter(
    (change) => JSON.stringify(change.old) !== JSON.stringify(change.new),
  );
}

// Read field changes from a submit response: outcome.changes and
// batch_turns[].field_changes. Returns normalized arrays without
// positional widget inference.
function normalizeFieldChangesFromSubmit(result) {
  if (!result || typeof result !== "object") {
    return { directChanges: [], outcomeChanges: [], legacyChanges: [], batchTurnChanges: [], all: [] };
  }

  const selectorChanges = readRoundtripFieldChanges(result, { endpoint: "submit:field-changes" });
  if (!selectorChanges) {
    return { directChanges: [], outcomeChanges: [], legacyChanges: [], batchTurnChanges: [], all: [] };
  }

  const directChanges = _normalizeFieldChangeList(selectorChanges.directChanges);
  const outcomeChanges = _normalizeFieldChangeList(selectorChanges.outcomeChanges);
  const legacyChanges = _normalizeFieldChangeList(selectorChanges.legacyChanges);
  const batchTurnChanges = Array.isArray(selectorChanges.batchTurnChanges)
    ? selectorChanges.batchTurnChanges.map((turn) => ({
        turn_number: typeof turn?.turnNumber === "number" ? turn.turnNumber : null,
        changes: _normalizeFieldChangeList(turn?.changes),
      }))
    : [];

  const all = _compactNetFieldChanges([
    ...directChanges,
    ...outcomeChanges,
    ...legacyChanges,
    ...batchTurnChanges.flatMap((turn) => turn.changes),
  ]);
  return {
    directChanges,
    outcomeChanges,
    legacyChanges,
    batchTurnChanges,
    all,
  };
}

// Read field changes from a rehydrate chat message and its nested
// canonical detail (message.changes, message.outcome?.changes).
function normalizeFieldChangesFromMessage(message) {
  if (!message || typeof message !== "object") {
    return { directChanges: [], outcomeChanges: [], legacyChanges: [], batchTurnChanges: [], all: [] };
  }

  const selectorChanges =
    readRoundtripFieldChanges(message, { endpoint: "chat:message-field-changes" })
    || (() => {
      try {
        return readFieldChanges(message, {
          endpoint: "chat:message-field-changes",
          allowLegacy: true,
        });
      } catch (_e) {
        return null;
      }
    })();
  if (!selectorChanges) {
    return { directChanges: [], outcomeChanges: [], legacyChanges: [], batchTurnChanges: [], all: [] };
  }

  const directChanges = _normalizeFieldChangeList(selectorChanges.directChanges);
  const outcomeChanges = _normalizeFieldChangeList(selectorChanges.outcomeChanges);
  const legacyChanges = _normalizeFieldChangeList(selectorChanges.legacyChanges);
  const batchTurnChanges = Array.isArray(selectorChanges.batchTurnChanges)
    ? selectorChanges.batchTurnChanges.map((turn) => ({
        turn_number: typeof turn?.turnNumber === "number" ? turn.turnNumber : null,
        changes: _normalizeFieldChangeList(turn?.changes),
      }))
    : [];
  return {
    directChanges,
    outcomeChanges,
    legacyChanges,
    batchTurnChanges,
    all: _compactNetFieldChanges([
      ...directChanges,
      ...outcomeChanges,
      ...legacyChanges,
      ...batchTurnChanges.flatMap((turn) => turn.changes),
    ]),
  };
}

function changeDetailsForMessage(panel, message, snapshot = null) {
  return changeDetailsForMessageImpl(panel, message, snapshot, { clonePlainData });
}

function captureExpandedTurnKeys(panel) {
  if (!panel?.state || !panel.state.expandedTurnKeys || typeof panel.state.expandedTurnKeys !== "object") {
    return {};
  }
  return { ...panel.state.expandedTurnKeys };
}

function restoreExpandedTurnKeys(panel, previous) {
  if (!panel?.state) {
    return;
  }
  const restored = {};
  for (const entry of panel.state.turns) {
    const turnKey = entry?.turn_key;
    if (turnKey && previous?.[turnKey]) {
      restored[turnKey] = true;
    }
  }
  panel.state.expandedTurnKeys = restored;
}

function rememberTurnDetailSnapshot(panel, detail = {}) {
  if (!panel?.state) {
    return null;
  }
  const turnId =
    typeof detail.turn_id === "string" && detail.turn_id
      ? detail.turn_id
      : (typeof panel.state.turnId === "string" && panel.state.turnId ? panel.state.turnId : null);
  if (!turnId) {
    return null;
  }
  ensureRoundtripBoundaryCompartments(panel);
  const sessionId =
    typeof detail.session_id === "string" && detail.session_id
      ? detail.session_id
      : (typeof panel.state.sessionId === "string" && panel.state.sessionId ? panel.state.sessionId : null);
  const safeResponseSource = {
    turn_id: turnId,
    session_id: sessionId,
    status: detail.status || detail.phase || panel.state.phase || null,
    queueAllowed: detail.queueAllowed ?? panel.state.queueAllowed ?? null,
    message:
      detail.message
      || panel.state.message
      || panel.state.clarification?.message
      || panel.state.failure?.user_facing_message
      || panel.state.failure?.message
      || panel.state.failure?.error
      || null,
    outcome: detail.outcome && typeof detail.outcome === "object"
      ? detail.outcome
      : (detail.clarification || panel.state.clarification)
        ? {
            kind: "clarify",
            question: (detail.clarification || panel.state.clarification)?.message || null,
          }
        : detail.failure || panel.state.failure
          ? {
              kind: "error",
              summary:
                detail.failure?.user_facing_message
                || detail.failure?.message
                || detail.failure?.error
                || panel.state.failure?.user_facing_message
                || panel.state.failure?.message
                || panel.state.failure?.error
                || null,
            }
          : null,
    changes: detail.fieldChanges ?? panel.state.lastSubmitFieldChanges ?? null,
    changeDetails: detail.changeDetails ?? panel.state.changeDetails ?? null,
    candidate: detail.candidateGraphHash || panel.state.candidateGraphHash
      ? {
          graphHash: detail.candidateGraphHash || panel.state.candidateGraphHash,
          structuralGraphHash: detail.candidateStructuralGraphHash || null,
          baselineGraphHash: detail.baselineGraphHash || panel.state.baselineGraphHash || null,
        }
      : null,
    eligibility: detail.applyEligibility ?? panel.state.applyEligibility ?? null,
    report: detail.candidateReport ?? panel.state.candidateReport ?? null,
    progress: detail.progress || null,
  };
  recordRoundtripResponseCompartments(panel, {
    ...safeResponseSource,
    auditRef: detail.auditRef ?? panel.state.auditRef ?? null,
    debugPayload: detail.debugPayload ?? panel.state.debugPayload ?? null,
  }, {
    includeSourceAsDebugPayload: false,
    debugBucket: "detailSnapshots",
  });
  if (!panel.state.turnDetailSnapshots || typeof panel.state.turnDetailSnapshots !== "object") {
    panel.state.turnDetailSnapshots = {};
  }
  // Compatibility/debug cache: retained raw detail snapshots are debug/audit
  // only, owned by the agent panel frontend compatibility layer for explicit
  // Audit/Debug/download affordances. Delete after those explicit surfaces use
  // responseDetails plus AuditArtifact/debug selectors and normal consumers no
  // longer need legacy detail mirrors.
  const snapshot = {
    turn_id: turnId,
    session_id: sessionId,
    phase: detail.phase || panel.state.phase,
    message:
      detail.message
      || panel.state.message
      || panel.state.clarification?.message
      || panel.state.failure?.user_facing_message
      || panel.state.failure?.message
      || panel.state.failure?.error
      || null,
    clarification: clonePlainData(detail.clarification ?? panel.state.clarification ?? null),
    failure: clonePlainData(detail.failure ?? panel.state.failure ?? null),
    candidateGraphPresent: Boolean(detail.candidateGraphPresent ?? panel.state.candidateGraph),
    candidateTransaction: clonePlainData(detail.candidateTransaction ?? panel.state.candidateTransaction ?? null),
    candidateReport: clonePlainData(detail.candidateReport ?? panel.state.candidateReport ?? null),
    applyEligibility: clonePlainData(detail.applyEligibility ?? panel.state.applyEligibility ?? null),
    queueAllowed: detail.queueAllowed ?? panel.state.queueAllowed,
    canvasApplyAllowed: detail.canvasApplyAllowed ?? panel.state.canvasApplyAllowed,
    auditRef: clonePlainData(detail.auditRef ?? panel.state.auditRef ?? null),
    debugPayload: clonePlainData(detail.debugPayload ?? panel.state.debugPayload ?? null),
    queueGuard: clonePlainData(detail.queueGuard ?? panel.state.queueGuard ?? getQueueGuardStateForPanel()),
    fieldChanges: clonePlainData(detail.fieldChanges ?? panel.state.lastSubmitFieldChanges ?? null),
    changeDetails: clonePlainData(detail.changeDetails ?? panel.state.changeDetails ?? null),
    lastAppliedChanges: clonePlainData(detail.lastAppliedChanges ?? panel.state.lastAppliedChanges ?? null),
  };
  panel.state.turnDetailSnapshots[turnId] = snapshot;
  return snapshot;
}

function detailSnapshotForMessage(panel, message) {
  const turnId =
    typeof message?.turn_id === "string" && message.turn_id
      ? message.turn_id
      : (typeof message?.detail_turn_id === "string" && message.detail_turn_id ? message.detail_turn_id : null);
  if (!turnId) {
    return null;
  }
  // Explicit-surface compatibility only. Normal response detail lookups should
  // use responseDetails through responseDetailForMessage/changeDetailsForMessage.
  return panel?.state?.turnDetailSnapshots?.[turnId] || null;
}

// ── Chat message identity and thread render-state helpers (T10) ─────────

/**
 * Compute a stable key for a chat message used for thread reconciliation.
 *
 * Priority:
 *   1. turn_id + role       → `turn:<turn_id>:<role>`
 *   2. local_id             → `local:<local_id>`
 *   3. synthetic flag       → `synthetic:<index>`
 *   4. Legacy index fallback → `legacy:<index>:<role>:<text-prefix>`
 *
 * The index fallback is intentionally temporary — it is only stable for the
 * current array snapshot and must not be treated as durable across mutations.
 */
export function messageStableKey(msg, index = 0) {
  if (!msg || typeof msg !== "object") {
    return `empty:${index}`;
  }
  const turnId = typeof msg.turn_id === "string" && msg.turn_id ? msg.turn_id : null;
  const role = typeof msg.role === "string" && msg.role ? msg.role : null;
  if (turnId && role) {
    return `turn:${turnId}:${role}`;
  }
  const localId = typeof msg.local_id === "string" && msg.local_id ? msg.local_id : null;
  if (localId) {
    return `local:${localId}`;
  }
  if (msg.synthetic === true) {
    return `synthetic:${index}`;
  }
  // Legacy fallback — only stable for the current array snapshot.
  const textSlice = typeof msg.text === "string" ? msg.text.slice(0, 40) : "";
  return `legacy:${index}:${role || "unknown"}:${textSlice}`;
}

/**
 * Fast, non-cryptographic string hash. Used to keep message signatures short
 * even when the message text is long Markdown prose.
 */
function djb2Hash(text) {
  let hash = 5381;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) + hash) + text.charCodeAt(i);
  }
  return (hash >>> 0).toString(16);
}

/**
 * Lightweight content signature for a chat message.
 * Used to detect content changes without deep comparison during reconciliation.
 */
export function messageSignature(msg) {
  if (!msg || typeof msg !== "object") {
    return "empty";
  }
  const text = String(msg.text || "");
  const parts = [
    msg.role || "",
    // Hash the full text so tail changes are detected, and include a short
    // prefix so similar messages remain distinguishable in debug output.
    `${text.slice(0, 80)}:${djb2Hash(text)}`,
    msg.turn_id || "",
    msg.synthetic ? "1" : "0",
    msg.local_id || "",
  ];
  return parts.join("|");
}

/**
 * Reset the thread render state stored on the panel object.
 *
 * Call this whenever chatMessages is replaced wholesale — new conversation,
 * rehydrate success/replacement, or any full thread reset path.
 */
export function resetThreadRenderState(panel) {
  if (!panel) {
    return;
  }
  panel.threadState = {
    renderedKeyOrder: [],
    bubbleMap: {},
    expandedOlder: false,
    forceScrollOnNextRender: true,
    signatures: {},
    lastVisibleKeySet: null,
    bubbleDetailSignatures: {},
  };
}

// ── End T10 helpers ──────────────────────────────────────────────────────

function mutableTranscriptMessage(message) {
  const projected = projectTranscriptMessage(message);
  return projected ? clonePlainData(projected) : null;
}

function makePendingResponseChatMessage(panel, task, progress, submitEpoch) {
  const epoch = submitEpoch || Date.now();
  return mutableTranscriptMessage({
    role: "agent",
    text: "",
    source: "agent-edit",
    pending_response: true,
    executor_pending: true,
    progress: progress || createExecutorProgressSnapshot({ decide: "active" }),
    optimistic: true,
    synthetic: false,
    local_id: `executor-pending:${epoch}`,
    submit_epoch: typeof submitEpoch === "number" ? submitEpoch : undefined,
    session_id: panel?.state?.sessionId || null,
    task: typeof task === "string" ? task : null,
    timestamp: new Date().toISOString(),
  });
}

function ensureRoundtripBoundaryCompartments(panel) {
  if (!panel?.state) {
    return;
  }
  if (!Array.isArray(panel.state.transcriptMessages)) {
    panel.state.transcriptMessages = [];
  }
  if (!panel.state.responseDetails || typeof panel.state.responseDetails !== "object") {
    panel.state.responseDetails = {};
  }
  if (!Array.isArray(panel.state.executionEvents)) {
    panel.state.executionEvents = [];
  }
  if (!Array.isArray(panel.state.auditArtifacts)) {
    panel.state.auditArtifacts = [];
  }
  if (!panel.state.debugDiagnostics || typeof panel.state.debugDiagnostics !== "object") {
    panel.state.debugDiagnostics = {};
  }
  if (!panel.state.compartmentIndexes || typeof panel.state.compartmentIndexes !== "object") {
    panel.state.compartmentIndexes = {};
  }
  panel.state.compartmentIndexes.responseDetailsByTurnId ||= {};
  panel.state.compartmentIndexes.executionEventsByKey ||= {};
  panel.state.compartmentIndexes.auditArtifactsByTurnId ||= {};
}

function recordRoundtripResponseCompartments(panel, source, options = {}) {
  if (!source || typeof source !== "object") {
    return;
  }
  const {
    includeSourceAsDebugPayload = true,
    debugBucket = "local",
  } = options;
  ensureRoundtripBoundaryCompartments(panel);
  const detail = projectResponseDetail(source);
  const turnId = detail?.turn?.turnId || source.turn_id || source.turnId || null;
  if (detail && typeof turnId === "string" && turnId) {
    panel.state.responseDetails[turnId] = detail;
    panel.state.compartmentIndexes.responseDetailsByTurnId[turnId] = turnId;
  }
  const explicitDebugPayload =
    source.debugPayload
    || source.debug_payload
    || source.debug
    || (includeSourceAsDebugPayload ? (source.raw || source) : null);
  const diagnosticSource = {
    ...source,
    ...(explicitDebugPayload ? { debugPayload: explicitDebugPayload } : {}),
  };
  const event = projectExecutionEvent(diagnosticSource);
  const hasExplicitDiagnosticData = Boolean(
    explicitDebugPayload
    || (Array.isArray(event?.reasoning) && event.reasoning.length)
    || (Array.isArray(event?.providerDiagnostics) && event.providerDiagnostics.length)
    || (Array.isArray(event?.batchTurns) && event.batchTurns.length),
  );
  if (event && hasExplicitDiagnosticData) {
    const eventKey = `${event.session_id || "session"}:${event.turn_id || `entry-${panel.state.executionEvents.length}`}:diagnostic`;
    upsertExecutionEvent(panel, event, { eventKey, mirror: false });
    panel.state.debugDiagnostics[debugBucket] = [
      ...(Array.isArray(panel.state.debugDiagnostics[debugBucket]) ? panel.state.debugDiagnostics[debugBucket] : []),
      {
        key: eventKey,
        session_id: event.session_id,
        turn_id: event.turn_id,
        debugPayload: event.debugPayload,
        reasoning: event.reasoning,
        providerDiagnostics: event.providerDiagnostics,
        batchTurns: event.batchTurns,
      },
    ];
  }
  const artifact = projectAuditArtifact(source);
  if (artifact?.auditRef || (Array.isArray(artifact?.artifactRefs) && artifact.artifactRefs.length)) {
    const index = panel.state.auditArtifacts.length;
    panel.state.auditArtifacts.push(artifact);
    if (artifact.turn_id) {
      panel.state.compartmentIndexes.auditArtifactsByTurnId[artifact.turn_id] = index;
    }
  }
}

function findPendingResponseMessage(panel) {
  const messages = Array.isArray(panel?.state?.chatMessages) ? panel.state.chatMessages : [];
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.role === "agent" && (message.pending_response === true || message.executor_pending === true)) {
      return message;
    }
  }
  return null;
}

function updatePendingResponseProgress(panel, progress, label = null, canonicalActivity = null) {
  const pending = findPendingResponseMessage(panel);
  if (!pending || !progress || typeof progress !== "object") {
    return false;
  }
  // Store progress from canonical phase_progress.
  pending.progress = progress;
  // Use canonical headline as the progress label.
  pending.progress_label = typeof label === "string" && label ? label : null;
  if (canonicalActivity && typeof canonicalActivity === "object") {
    recordRoundtripResponseCompartments(panel, {
      session_id: panel?.state?.sessionId || null,
      turn_id: panel?.state?.turnId || null,
      message: typeof label === "string" && label ? label : null,
      debugPayload: { canonical_activity: canonicalActivity },
    });
  }
  // Only blank the text if we have a meaningful progress update to show.
  const hasActivePhase = progress.decide === "active"
    || progress.research === "active"
    || progress.execute === "active";
  if (hasActivePhase || typeof label === "string") {
    pending.text = "";
  }
  // Mirror the progress update onto the canonical transcript source so that
  // renderers using selectTranscriptMessages see live websocket progress.
  const transcriptMessages = Array.isArray(panel?.state?.transcriptMessages)
    ? panel.state.transcriptMessages
    : [];
  const transcriptPending = transcriptMessages.find((message) => (
    message?.role === "agent" && (message.pending_response === true || message.executor_pending === true)
  ));
  if (transcriptPending && transcriptPending !== pending) {
    transcriptPending.progress = progress;
    transcriptPending.progress_label = pending.progress_label;
    if (hasActivePhase || typeof label === "string") {
      transcriptPending.text = "";
    }
  }
  return true;
}

// ── Non-terminal submit stall notice (watchdog inactivity) ─────────────────
// The submit watchdog no longer aborts a fetch that simply went quiet: while
// the absolute deadline still has time it marks a stall, keeps waiting, and
// calls back here so the thread shows "still working — last progress Xs ago"
// instead of a terminal failure.  Heartbeat events (which reset the watchdog
// via recordSubmitActivity) render the thread again, so a resumed turn replaces
// this notice naturally.
function notifySubmitStalled(panel, { stalledSinceMs = null, lastProgressAtMs = null } = {}) {
  if (!panel?.state || panel.state.phase !== PANEL_STATE.SUBMITTING) {
    return;
  }
  const stalledSince = Number.isFinite(stalledSinceMs) ? stalledSinceMs : Date.now();
  const lastProgressAt = Number.isFinite(lastProgressAtMs) ? lastProgressAtMs : stalledSince;
  const secondsAgo = Math.max(0, Math.round((stalledSince - lastProgressAt) / 1000));
  const label = secondsAgo > 0
    ? `Still working — last progress ${secondsAgo}s ago`
    : "Still working — waiting on the provider";
  const progress = (panel.state.executorProgress && typeof panel.state.executorProgress === "object")
    ? panel.state.executorProgress
    : createExecutorProgressSnapshot({ decide: "active" });
  updatePendingResponseProgress(panel, progress, label);
  scheduleRenderAgentPanel("submit-stall", panel, [RENDER_SECTIONS.META, RENDER_SECTIONS.THREAD]);
}

function promotePendingResponseMessage(panel, result, options = {}) {
  if (!Array.isArray(panel?.state?.chatMessages)) {
    return false;
  }
  const pendingIndex = panel.state.chatMessages.findIndex((message) => (
    message?.role === "agent" && (message.pending_response === true || message.executor_pending === true)
  ));
  const pendingBase = pendingIndex >= 0 ? panel.state.chatMessages[pendingIndex] : null;
  if (!pendingBase) {
    return false;
  }
  const pending = clonePlainData(pendingBase);
  recordRoundtripResponseCompartments(panel, result);
  const terminalText = options.message
    || result?.message
    || result?.reply
    || (result?.outcome && typeof result.outcome === "object" ? result.outcome.message : null)
    || null;
  if (typeof terminalText === "string") {
    pending.text = terminalText;
  }
  pending.pending_response = false;
  pending.executor_pending = false;
  // Keep the message marked optimistic until a successful backend rehydrate
  // replaces it with durable canonical messages. This lets rehydrate failures
  // preserve locally-built terminal bubbles instead of wiping the thread.
  pending.local_id = undefined;
  const identity = readRoundtripTurnIdentity(result, { endpoint: "promote-pending-response" });
  if (typeof identity?.turnId === "string" && identity.turnId) {
    pending.turn_id = identity.turnId;
  }
  if (typeof identity?.sessionId === "string" && identity.sessionId) {
    pending.session_id = identity.sessionId;
  }
  if (typeof identity?.baselineTurnId === "string") {
    pending.baseline_turn_id = identity.baselineTurnId;
  }
  if (typeof result?.route === "string") {
    pending.route = result.route;
  }
  if (result?.outcome && typeof result.outcome === "object") {
    pending.outcome = clonePlainData(result.outcome);
  }
  if (result?.report && typeof result.report === "object") {
    pending.report = clonePlainData(result.report);
  }
  const applyCandidate = readRoundtripApplyCandidate(result, { endpoint: "promote-pending-response" });
  if (applyCandidate?.graph && typeof applyCandidate.graph === "object") {
    pending.candidateGraph = clonePlainData(applyCandidate.graph);
  }
  if (result?.auditRef && typeof result.auditRef === "object") {
    pending.audit_ref = clonePlainData(result.auditRef);
  }
  if (panel?.state?.changeDetails && typeof panel.state.changeDetails === "object") {
    pending.change_details = clonePlainData(panel.state.changeDetails);
  } else if (result?.raw?.change_details && typeof result.raw.change_details === "object") {
    pending.change_details = clonePlainData(result.raw.change_details);
  }
  if (panel?.state?.lastSubmitFieldChanges && typeof panel.state.lastSubmitFieldChanges === "object") {
    pending.field_changes = clonePlainData(panel.state.lastSubmitFieldChanges);
  }
  if (panel?.state?.applyEligibility && typeof panel.state.applyEligibility === "object") {
    pending.apply_eligibility = clonePlainData(panel.state.applyEligibility);
  }
  const safePending = mutableTranscriptMessage(pending);
  if (safePending) {
    panel.state.chatMessages[pendingIndex] = safePending;
    panel.state.transcriptMessages = panel.state.chatMessages
      .map(mutableTranscriptMessage)
      .filter(Boolean);
  }
  return true;
}

function clearPendingResponseMessages(panel) {
  if (!Array.isArray(panel?.state?.chatMessages)) {
    return false;
  }
  const before = panel.state.chatMessages.length;
  // Clear only pending response bubbles; executor_pending messages are separate.
  panel.state.chatMessages = panel.state.chatMessages.filter((message) => (
    message?.pending_response !== true
  ));
  const changed = panel.state.chatMessages.length !== before;
  if (changed && panel?.state) {
    panel.state.chatMessages = panel.state.chatMessages
      .map(mutableTranscriptMessage)
      .filter(Boolean);
    panel.state.transcriptMessages = panel.state.chatMessages.slice();
    // Clear only the active activity state; terminal progress stays.
    const progress = panel.state.executorProgress;
    if (progress && typeof progress === "object") {
      const hasActivePhase = progress.decide === "active"
        || progress.research === "active"
        || progress.execute === "active";
      if (hasActivePhase) {
        panel.state.executorProgress = null;
      }
    }
  }
  return changed;
}

function syntheticFailureAgentMessage(panel, failure, fallbackStage = "frontend") {
  if (!failure || typeof failure !== "object") {
    return null;
  }
  const message = failure.user_facing_message || failure.message || failure.error || null;
  if (!message) {
    return null;
  }
  const nextAction = typeof failure.next_action === "string" ? failure.next_action.trim() : "";
  const text = nextAction && !String(message).includes(nextAction)
    ? `${message}\n\n${nextAction}`
    : message;
  const detailTurnId =
    typeof failure.turn_id === "string" && failure.turn_id
      ? failure.turn_id
      : (typeof panel?.state?.turnId === "string" && panel.state.turnId ? panel.state.turnId : null);
  const stage = failure.stage || fallbackStage || "frontend";
  const kind = failure.kind || "Error";
  return {
    role: "agent",
    text,
    detail_turn_id: detailTurnId,
    session_id: failure.session_id || panel?.state?.sessionId || null,
    synthetic: true,
    failure_kind: kind,
    failure_stage: stage,
    local_id: `failure:${detailTurnId || "local"}:${kind}:${stage}`,
  };
}

// Canonical projection for every V2 exit after prepare.  Transport/canvas code
// supplies the causal evidence; the lifecycle reducer owns storing and
// rendering this single terminal outcome.
function compensatedFailurePayload(panel, failure, {
  transactionRollback = null,
  actionBody = null,
  fallbackStage = "compensation",
  rebaselineRecovery = null,
  recoveryRequired = null,
} = {}) {
  const recovery = rebaselineRecovery
    || recoveryForFailure(failure, panel, actionBody)
    || {
      action: "rebaseline",
      endpoint: "/vibecomfy/agent-edit/rebaseline",
      reason: "compensation_recovery",
      last_known_baseline_graph_hash: panel?.state?.baselineGraphHash || null,
      client_graph_hash: actionBody?.client_graph_hash || null,
      client_structural_graph_hash: actionBody?.client_structural_graph_hash || null,
    };
  return projectCompensatedFailure({
    failure,
    rolledBack: transactionRollback?.ok === true,
    rollbackReceipt: transactionRollback?.rollback_receipt || transactionRollback?.response?.receipt || null,
    recoveryRequired: recoveryRequired === null ? transactionRollback?.ok !== true : recoveryRequired,
    syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, fallbackStage),
    rebaselineRecovery: recoveryForPanelState(recovery),
    transactionRollback,
  });
}

function upsertBatchTurn(panel, payload, options = {}) {
  if (!panel || !panel.state) {
    return null;
  }
  const previousExpanded = captureExpandedTurnKeys(panel);
  const normalized = normalizeBatchTurn(payload, options);
  if (!normalized) {
    return null;
  }
  upsertExecutionEvent(panel, payload, {
    turnEntry: normalized,
    eventKey: executionEventKeyForTurn(normalized),
  });
  restoreExpandedTurnKeys(panel, previousExpanded);
  markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
  return normalized;
}

function reconcileResponseBatchTurns(panel, result) {
  if (!Array.isArray(result?.batch_turns)) {
    return;
  }
  const previousExpanded = captureExpandedTurnKeys(panel);
  const responseSessionId =
    typeof result?.session_id === "string" && result.session_id
      ? result.session_id
      : (typeof panel?.state?.sessionId === "string" && panel.state.sessionId ? panel.state.sessionId : null);
  // Derive canonical activity feed from current batch turns and merge with response turns.
  const existingBatchByKey = new Map();
  const existingEvents = Array.isArray(panel?.state?.executionEvents) ? panel.state.executionEvents : [];
  for (const event of existingEvents) {
    const entry = executionEventTurnEntry(event);
    if (entry?.entry_type !== "batch") {
      continue;
    }
    if (responseSessionId && entry.session_id === responseSessionId) {
      // Track existing batch turns by canonical key for merge dedup.
      const turnId = typeof entry.turn_id === "string" && entry.turn_id ? entry.turn_id : null;
      const turnNumber = typeof entry.turn_number === "number" ? entry.turn_number : null;
      if (turnId && typeof turnNumber === "number") {
        const key = `${responseSessionId}:${turnId}:${turnNumber}`;
        if (!existingBatchByKey.has(key)) {
          existingBatchByKey.set(key, entry);
        }
      }
      continue;
    }
  }
  if (responseSessionId && Array.isArray(panel?.state?.executionEvents)) {
    panel.state.executionEvents = panel.state.executionEvents.filter((event) => {
      const entry = executionEventTurnEntry(event);
      return !(entry?.entry_type === "batch" && entry.session_id === responseSessionId);
    });
    syncExecutionEventIndexes(panel);
    syncTurnsCompatibilityMirror(panel);
  }
  const finalIndex = result.batch_turns.length - 1;
  const resultApplyCandidate = (() => {
    try {
      return readApplyCandidate(result, { endpoint: "batch-turn-reconcile", allowLegacy: true });
    } catch (_e) {
      return null;
    }
  })();
  const resultHasCandidate = Boolean(resultApplyCandidate?.graph && typeof resultApplyCandidate.graph === "object");
  // Track processed keys to prevent duplicate detail rows.
  const processedKeys = new Set();
  for (let index = 0; index < result.batch_turns.length; index += 1) {
    const turn = result.batch_turns[index];
    const turnId = typeof turn.turn_id === "string" && turn.turn_id ? turn.turn_id : null;
    const turnNumberRaw = turn.turn_number;
    const turnNumber = Number.isInteger(turnNumberRaw)
      ? turnNumberRaw
      : (typeof turnNumberRaw === "number" && Number.isFinite(turnNumberRaw) ? Math.trunc(turnNumberRaw) : null);

    // Deduplicate: skip turns already reconciled that appear again.
    const dedupKey = responseSessionId && turnId && typeof turnNumber === "number"
      ? `${responseSessionId}:${turnId}:${turnNumber}`
      : null;
    if (dedupKey && processedKeys.has(dedupKey)) {
      continue;
    }
    if (dedupKey) {
      processedKeys.add(dedupKey);
    }

    const turnPayload =
      index === finalIndex
      && typeof result?.done_summary === "string"
      && result.done_summary
        ? { ...turn, done_summary: turn.done_summary || result.done_summary }
        : turn;
    const turnOutcome =
      (index === finalIndex && result?.outcome && typeof result.outcome === "object")
        ? result.outcome
        : (turnPayload?.outcome && typeof turnPayload.outcome === "object" ? turnPayload.outcome : null);
    let status = null;
    if (outcomeRequiresClarification(turnOutcome)) {
      status = "clarify";
    } else if (
      result?.ok === true
      || resultHasCandidate
      || (typeof result?.done_summary === "string" && result.done_summary)
      || index === finalIndex
    ) {
      status = "done";
    } else {
      status = "in_progress";
    }
    // Derive canonical activity state for this batch turn; wire through canonical deriver.
    // Real backend batch_turns often omit `status`, so inject the computed terminal
    // status before deriving so the canonical activity reflects the final HTTP outcome.
    const derivationPayload =
      turnPayload?.status ? turnPayload : { ...turnPayload, status };
    const canonicalActivity = deriveAgentActivityState(derivationPayload);
    upsertBatchTurn(panel, turnPayload, {
      source: "response",
      sessionId: responseSessionId,
      status,
      parentTurnId: typeof result?.turn_id === "string" && result.turn_id ? result.turn_id : null,
      canonicalActivity,
    });
  }
  restoreExpandedTurnKeys(panel, previousExpanded);
  markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
}

function getAgentTurnEventPayload(event) {
  if (event?.detail && typeof event.detail === "object") {
    return event.detail;
  }
  return event && typeof event === "object" ? event : null;
}

function shouldAcceptAgentTurnEvent(panel, payload) {
  if (!panel?.state || panel.root?.dataset?.open !== "1") {
    return false;
  }
  const payloadSessionId =
    typeof payload?.session_id === "string" && payload.session_id ? payload.session_id : null;
  if (!payloadSessionId) {
    return false;
  }
  const currentSessionId =
    typeof panel.state.sessionId === "string" && panel.state.sessionId ? panel.state.sessionId : null;

  // ── T10: Scope-aware pre-filter ───────────────────────────────────────
  // Before any session-based filtering, verify the event belongs to the
  // active scope.  This prevents (a) a stale event for scope B's session
  // from mutating scope A's visible panel, and (b) a first-allocation race
  // where an event for a foreign scope binds `panel.state.sessionId` while
  // the panel is scope-A-active but session-null.
  if (panel.state.chatScopeId) {
    const scopedSession = resolveScopeSessionId(panel.state.chatScopeId);
    if (!eventSessionMatchesActiveScope(panel.state, payloadSessionId, scopedSession)) {
      return false;
    }
    if (scopedSession && scopedSession === payloadSessionId) {
      return true;
    }
  }

  if (currentSessionId) {
    return currentSessionId === payloadSessionId;
  }
  // No bound session yet (fresh first run — the server assigns the session_id):
  // intentionally drop live events rather than risk binding a foreign session.
  // The authoritative batch_turns in the submit response reconcile the feed at
  // completion, and every run after the first is fully live once bound.
  const batchSessionIds = new Set(
    (Array.isArray(panel.state.turns) ? panel.state.turns : [])
      .filter((entry) => entry?.entry_type === "batch" && typeof entry.session_id === "string" && entry.session_id)
      .map((entry) => entry.session_id),
  );
  if (batchSessionIds.size > 0) {
    return batchSessionIds.size === 1 && batchSessionIds.has(payloadSessionId);
  }
  const hasPendingTurn = Array.isArray(panel.state.turns)
    && panel.state.turns.some((entry) => entry?.entry_type === "durable" && entry.status === "pending");
  const isSubmitting = panel.state.phase === PANEL_STATE.SUBMITTING;
  // First submit in a fresh browser session has no session_id until the server
  // allocates it. Accept the server-pushed progress event only while this panel
  // is actively waiting on its own submit response; later events are filtered by
  // the now-bound session_id above.
  return Boolean(isSubmitting && hasPendingTurn);
}

function handleAgentTurnEvent(event) {
  const panel = currentAgentPanel();
  if (!panel || panel.root?.dataset?.open !== "1") {
    return;
  }
  const payload = getAgentTurnEventPayload(event);
  if (!payload || !shouldAcceptAgentTurnEvent(panel, payload)) {
    return;
  }
  // ── T10: Scope-guarded first-session binding ──────────────────────────
  // Only bind panel.state.sessionId if the event's session matches the
  // active scope.  This closes the first-allocation race: when scope A is
  // active and sessionId is null, a stale event for scope B's session must
  // not bind the wrong session.  Also persist the scope→session mapping so
  // subsequent events for this scope can use the scoped session key.
  if (typeof payload.session_id === "string" && payload.session_id) {
    if (panel.state.chatScopeId) {
      const scopedSession = resolveScopeSessionId(panel.state.chatScopeId);
      if (
        (!panel.state.sessionId || panel.state.sessionId !== payload.session_id)
        && eventSessionMatchesActiveScope(panel.state, payload.session_id, scopedSession)
      ) {
        panel.state.sessionId = payload.session_id;
        setScopedSessionId(panel.state.chatScopeId, payload.session_id);
      }
      // else: event belongs to a different scope — silently drop.
      // shouldAcceptAgentTurnEvent already validated this, so this is
      // defense-in-depth.
    } else if (!panel.state.sessionId) {
      panel.state.sessionId = payload.session_id;
    }
  }
  // Derive canonical activity state before upserting so the turn entry carries it.
  const canonicalPayload = normalizeAgentTurnPayload(payload);
  const canonicalActivity = canonicalPayload ? deriveAgentActivityState(canonicalPayload) : null;
  const normalized = upsertBatchTurn(panel, payload, {
    source: "websocket",
    canonicalActivity,
  });
  if (!normalized) {
    return;
  }
  submitFlow.recordSubmitActivity(panel);
  // Use the canonical activity state for executor progress (derived compatibility).
  if (canonicalActivity?.phase_progress) {
    panel.state.executorProgress = canonicalActivity.phase_progress;
    const label = canonicalActivity.headline || agentTurnProgressLabel(canonicalPayload);
    updatePendingResponseProgress(panel, canonicalActivity.phase_progress, label, canonicalActivity);
    scheduleRenderAgentPanel("websocket", panel, [RENDER_SECTIONS.META, RENDER_SECTIONS.THREAD]);
    return;
  }
  scheduleRenderAgentPanel("websocket", panel, [RENDER_SECTIONS.THREAD]);
}

function ensureAgentTurnListener() {
  if (api?.__vibecomfyAgentTurnListenerRegistered || typeof api?.addEventListener !== "function") {
    return;
  }
  const runtime = getAgentPanelRuntime();
  const agentTurnEventListener = handleAgentTurnEvent;
  runtime.agentTurnEventListener = agentTurnEventListener;
  // Event name MUST match the backend emit string in agent_edit.py (_ws_send).
  api.addEventListener("vibecomfy.agent_edit.turn", agentTurnEventListener);
  runtime.agentTurnEventListenerRegistered = true;
  api.__vibecomfyAgentTurnListenerRegistered = true;
}

function handleExecutorPhaseEvent(event) {
  const panel = currentAgentPanel();
  if (!panel || panel.root?.dataset?.open !== "1") {
    return;
  }
  const normalized = normalizeExecutorPhasePayload(event);
  if (!normalized) {
    return;
  }
  // ── T10: Scope-aware executor phase event guard ───────────────────────
  // Reject executor phase events whose session does not belong to the
  // active scope.  When scope tracking is active the scoped session binding
  // is authoritative; when inactive we fall back to the legacy in-memory
  // sessionId comparison.
  if (normalized.session_id) {
    if (panel.state?.chatScopeId) {
      const scopedSession = resolveScopeSessionId(panel.state.chatScopeId);
      if (!eventSessionMatchesActiveScope(panel.state, normalized.session_id, scopedSession)) {
        return;
      }
    } else if (panel.state?.sessionId && normalized.session_id !== panel.state.sessionId) {
      // Legacy: no scope tracking — reject foreign sessions.
      return;
    }
  }
  const progress = executorPhaseToCanonicalProgress(normalized);
  if (!progress) {
    return;
  }
  submitFlow.recordSubmitActivity(panel);

  // Always update executor progress for the meta row (legacy compatibility).
  panel.state.executorProgress = progress;

  // Update pending response progress for message bubbles.
  const decisionLabel = progress.decide === "active"
    ? executorDecisionLabel(normalized)
    : null;
  const touchedPendingMessage = updatePendingResponseProgress(panel, progress, decisionLabel);

  // When agent-turn activity is active (batch turns are being tracked),
  // executor phase events are compatibility input only: they update phase
  // progress state but must NOT create an independent rendering branch or
  // duplicate legacy progress rows. The agent turn handler manages rendering
  // via the canonical activity feed.
  const hasActiveAgentTurn = Array.isArray(panel.state?.turns)
    && panel.state.turns.some((entry) => entry?.entry_type === "batch");
  if (hasActiveAgentTurn) {
    // Compatibility-only: state updated; rendering left to agent turn handler.
    return;
  }

  // Legacy behavior: for non-agent-edit flows, executor phase events drive
  // the visible progress UI.
  scheduleRenderAgentPanel(
    "executor-phase",
    panel,
    touchedPendingMessage
      ? [RENDER_SECTIONS.META, RENDER_SECTIONS.THREAD]
      : [RENDER_SECTIONS.META],
  );
}

function ensureExecutorPhaseListener() {
  if (api?.__vibecomfyExecutorPhaseListenerRegistered || typeof api?.addEventListener !== "function") {
    return;
  }
  api.addEventListener("vibecomfy.executor.phase", handleExecutorPhaseEvent);
  api.__vibecomfyExecutorPhaseListenerRegistered = true;
}

function renderMeta(panel) {
  clearNode(panel.metaRow);
  panel.metaRow.appendChild(labelValue("state", panel.state.phase));
  panel.metaRow.appendChild(labelValue("session", panel.state.sessionId || "new"));
  panel.metaRow.appendChild(labelValue("turn", panel.state.turnId || "pending"));
  panel.metaRow.appendChild(labelValue("baseline", panel.state.baselineTurnId || "none"));
  if (panel.state.executorProgress) {
    panel.metaRow.appendChild(labelValue("phase", executorProgressLabel(panel.state.executorProgress)));
  }
}

// ── Chat thread rendering (M4b — newest-at-bottom bubble list) ────────────
// THREAD_WINDOW_SIZE and THREAD_NEAR_BOTTOM_TOLERANCE_PX live in panel_thread.js.

function ensureThreadRenderState(panel) {
  if (!panel?.threadState || typeof panel.threadState !== "object") {
    resetThreadRenderState(panel);
  }
  return panel.threadState;
}

function collectThreadMessageEntries(panel) {
  return collectThreadMessageEntriesImpl(panel, {
    messageStableKey,
  });
}

// ── Chat / thread wrappers moved to panel_thread.js ────────────────────────

function renderChatBubbleNode(bubble, panel, msg, messageKey, messageIndex) {
  return renderChatBubbleNodeImpl(bubble, panel, msg, messageKey, messageIndex, {
    appendCandidateDetail,
    appendFailureDetail,
    appendQueueDetail,
    appendTextLine,
    candidateActionState,
    changeDetailsForMessage,
    clearNode,
    createBubbleDetailSection,
    createDetails,
    el,
    ensureThreadRenderState,
    showIssueModal,
    submitRating,
  });
}

function reconcileChatBubbles(panel, messagesMount, displayEntries) {
  return reconcileChatBubblesImpl(panel, messagesMount, displayEntries, {
    appendCandidateDetail,
    appendChildOnce,
    appendFailureDetail,
    appendQueueDetail,
    appendTextLine,
    candidateActionState,
    changeDetailsForMessage,
    clearNode,
    createBubbleDetailSection,
    createDetails,
    el,
    ensureThreadRenderState,
    messageSignature,
    showIssueModal,
    submitRating,
  });
}

function computeThreadDisplayEntries(panel, threadEntries) {
  return computeThreadDisplayEntriesImpl(panel, threadEntries, {
    ensureThreadRenderState,
  });
}

function renderChatThread(panel) {
  return renderChatThreadImpl(panel, {
    appendChildOnce,
    clearNode,
    collectThreadMessageEntries,
    computeThreadDisplayEntries,
    el,
    ensureThreadRenderState,
    reconcileChatBubbles,
    recordThreadRender,
    // These are injected for the moved mount/session/show-earlier/welcome
    // helpers that now live inside panel_thread.js but still receive deps
    // from the entrypoint.
    button,
    currentAgentPanel,
    getAgentPanelRuntime,
    markAgentPanelDirty,
    RENDER_SECTIONS,
    renderAgentPanel,
  });
}

function buildAgentPanelDebugSnapshot(panel = currentAgentPanel(), runtime = getAgentPanelRuntime()) {
  const routeStatus = routeStatusState(panel);
  const readinessState = submitReadinessState(panel);
  let threadEntries = [];
  let displayEntries = [];
  let debugError = null;
  try {
    threadEntries = collectThreadMessageEntries(panel);
    ({ displayEntries } = computeThreadDisplayEntries(panel, threadEntries));
  } catch (err) {
    debugError = String(err);
  }
  const previewDiffSummary = compactPanelPreviewDiff(panel);
  return {
    panelId: panel?.panelId || null,
    panelsCreated: Number.isFinite(runtime?.panelsCreated) ? runtime.panelsCreated : 0,
    lastThreadRender: panel?.__lastThreadRender || null,
    lastNoticeRender: panel?.__lastNoticeRender || null,
    statusCommitAt: panel?.state?.statusCommitAt || null,
    rehydrateCommitAt: panel?.state?.rehydrateCommitAt || null,
    marksAfterCommit: Number.isFinite(panel?.state?.marksAfterCommit)
      ? panel.state.marksAfterCommit
      : 0,
    phase: panel?.state?.phase || null,
    demoStage: panel?.state?.__demoStage || null,
    demoScenarioId: panel?.state?.__demoScenarioId || null,
    chatScopeId: panel?.state?.chatScopeId || null,
    chatScopeFingerprint: panel?.state?.chatScopeFingerprint || null,
    activeCanvasScope: resolveActiveCanvasScope(),
    readiness: {
      kind: routeStatus.kind || null,
      ready: Boolean(readinessState.ready),
      reason: readinessState.reason || null,
    },
    sessionId: panel?.state?.sessionId || null,
    turnId: panel?.state?.turnId || null,
    baselineTurnId: panel?.state?.baselineTurnId || null,
    messageCount: threadEntries.length,
    visibleMessageCount: displayEntries.length,
    dirtySections: Array.isArray(panel?.pendingDirtySections) ? panel.pendingDirtySections.slice() : [],
    renderCounts: panel?.__renderCounts && typeof panel.__renderCounts === "object"
      ? { ...panel.__renderCounts }
      : {},
    renderErrors: Array.isArray(panel?.__renderErrors) ? panel.__renderErrors.slice() : [],
    renderFailureCounts: panel?.__renderFailureCounts && typeof panel.__renderFailureCounts === "object"
      ? { ...panel.__renderFailureCounts }
      : {},
    previewDiff: previewDiffSummary,
    previewDomProjection: runtime?._previewDomProjectionReport || null,
    previewRefresh: runtime?._previewRefreshReport || null,
    debugError,
    mountMode: panel?.state?.mountMode || null,
    flushPending: hasPendingAgentPanelFlush(panel),
    // Render scheduling is panel/workflow-activation affine. Global counters
    // can be advanced by a late callback from a disposed harness/window and
    // must never satisfy observability for this panel.
    flushCount: Number.isFinite(panel?.__renderFlushCount) ? panel.__renderFlushCount : 0,
    lastFlushReason: typeof panel?.__lastRenderFlushReason === "string"
      ? panel.__lastRenderFlushReason
      : "",
    mountedCheck: isAgentPanelRootConnected(panel),
    epochs: {
      status: Number.isFinite(panel?.state?.statusRequestEpoch) ? panel.state.statusRequestEpoch : 0,
      chatRehydrate: Number.isFinite(panel?.state?.chatRehydrateEpoch) ? panel.state.chatRehydrateEpoch : 0,
      chatRehydrateCommitted: Number.isFinite(panel?.state?.chatRehydrateCommittedEpoch)
        ? panel.state.chatRehydrateCommittedEpoch
        : 0,
      submit: Number.isFinite(panel?.state?.submitEpoch) ? panel.state.submitEpoch : 0,
    },
  };
}

function installAgentPanelDebugHook() {
  const targetWindow = typeof window !== "undefined" ? window : null;
  if (!targetWindow) {
    return;
  }
  // Bind observability to the runtime owned by this concrete window. During a
  // replacement, resolving through mutable globalThis.window at callback time
  // can otherwise expose another window's panel and flush counters.
  const ownerRuntime = getAgentPanelRuntime();
  targetWindow.__vibecomfyPanelDebug = () => buildAgentPanelDebugSnapshot(
    ownerRuntime.agentPanel,
    ownerRuntime,
  );
  targetWindow.__vibecomfyRoundtripDebug = {
    applyGraphInPlaceWithIntentDecoration: applyFlow.applyGraphInPlaceWithIntentDecoration,
    captureSerializedGraphForAgent,
    fitCanvasViewportToGraphPayload,
    prepareCandidateGraphForPanel,
    repairLiveIntentNodesFromCandidate,
  };
}

function populateAgentBubbleDetail(target, panel, message, snapshot = null) {
  return populateAgentBubbleDetailImpl(target, panel, message, snapshot, {
    appendCandidateDetail,
    appendFailureDetail,
    appendQueueDetail,
    appendTextLine,
    candidateActionState,
    changeDetailsForMessage,
    clearNode,
    createBubbleDetailSection,
    createDetails,
    el,
  });
}

// scrollChatThreadToBottom, isChatThreadNearBottom, renderHistory, renderActivityRows,
// populateActivityRows, and activity helpers all live in panel_thread.js now.

function collectDiffRows(report) {
  const ce = report?.change?.content_edits || {};
  const scopedDiff = report?.revision_evidence?.scoped_diff || {};
  const rows = [];
  for (const uid of ce.preserved || []) {
    rows.push({ text: `preserved: ${uid}`, color: "#4caf50", title: null });
  }
  for (const uid of ce.edited || []) {
    rows.push({ text: `edited: ${uid}`, color: "#ffc107", title: null });
  }
  for (const uid of ce.new_auto_placed || []) {
    rows.push({ text: `new_auto_placed: ${uid}`, color: VC_COLORS.pending, title: null });
  }
  for (const uid of ce.removed || []) {
    rows.push({ text: `removed: ${uid}`, color: "#ff7f7f", title: null });
  }
  for (const item of ce.removed_named || []) {
    rows.push({
      text: `removed_named: ${item.uid} (${item.class_type || "unknown"})`,
      color: "#f44336",
      title: null,
    });
  }
  for (const item of ce.virtual_wires_degraded || []) {
    rows.push({
      text: `virtual_wires_degraded: ${item.uid || item.node_id || "unknown"}`,
      color: "#ffb86c",
      title: safeJson(item),
    });
  }
  for (const uid of ce.stripped_helpers || []) {
    rows.push({ text: `stripped_helper: ${uid}`, color: "#ff8f59", title: null });
  }
  // lowered entries from static lowering provenance
  for (const item of report?.change?.lowered || []) {
    const uid = item?.uid || item?.source_node_uid || "unknown";
    const count = item?.lowered_native_count ?? 0;
    rows.push({
      text: `lowered: ${uid} -> ${count} native node(s)`,
      color: LOWERED_DIFF_COLOR,
      title: null,
    });
  }
  if (!rows.length && typeof scopedDiff.summary === "string" && scopedDiff.summary.trim()) {
    rows.push({ text: scopedDiff.summary.trim(), color: "#9ed0ff", title: null });
  }
  for (const nodeId of scopedDiff.changed_nodes || []) {
    rows.push({ text: `changed_node: ${nodeId}`, color: "#ffc107", title: null });
  }
  for (const nodeId of scopedDiff.added_nodes || []) {
    rows.push({ text: `added_node: ${nodeId}`, color: VC_COLORS.pending, title: null });
  }
  for (const nodeId of scopedDiff.removed_nodes || []) {
    rows.push({ text: `removed_node: ${nodeId}`, color: "#ff7f7f", title: null });
  }
  for (const link of scopedDiff.added_links || []) {
    rows.push({
      text: `added_link: ${link?.origin_node ?? "?"}.${link?.origin_slot ?? "?"} -> ${link?.target_node ?? "?"}.${link?.target_slot ?? "?"}`,
      color: "#4caf50",
      title: safeJson(link),
    });
  }
  for (const link of scopedDiff.removed_links || []) {
    rows.push({
      text: `removed_link: ${link?.origin_node ?? "?"}.${link?.origin_slot ?? "?"} -> ${link?.target_node ?? "?"}.${link?.target_slot ?? "?"}`,
      color: "#ff7f7f",
      title: safeJson(link),
    });
  }
  return rows;
}

function extractChangedNodeFeedback(report) {
  const ce = report?.change?.content_edits || {};
  const scopedDiff = report?.revision_evidence?.scoped_diff || {};
  const items = [];
  for (const uid of ce.edited || []) {
    items.push({ uid, kind: "edited", color: "#ffc107", label: `Edited ${uid}` });
  }
  for (const uid of ce.new_auto_placed || []) {
    items.push({ uid, kind: "new_auto_placed", color: VC_COLORS.pending, label: `Added ${uid}` });
  }
  for (const uid of ce.removed || []) {
    items.push({ uid, kind: "removed", color: "#ff7f7f", label: `Removed ${uid}` });
  }
  for (const item of ce.removed_named || []) {
    items.push({
      uid: item?.uid || null,
      kind: "removed_named",
      color: "#f44336",
      label: `Removed ${item?.uid || "unknown"} (${item?.class_type || "unknown"})`,
      class_type: item?.class_type || null,
    });
  }
  for (const uid of ce.stripped_helpers || []) {
    items.push({ uid, kind: "stripped_helper", color: "#ff8f59", label: `Stripped helper ${uid}` });
  }
  for (const item of ce.virtual_wires_degraded || []) {
    const uid = item?.uid || item?.node_id || null;
    items.push({
      uid,
      kind: "virtual_wires_degraded",
      color: "#ffb86c",
      label: `Virtual wire degraded ${uid || "unknown"}`,
      detail: item || null,
    });
  }
  for (const nodeId of scopedDiff.changed_nodes || []) {
    items.push({ uid: String(nodeId), kind: "changed_node", color: "#ffc107", label: `Changed node ${nodeId}` });
  }
  for (const nodeId of scopedDiff.added_nodes || []) {
    items.push({ uid: String(nodeId), kind: "added_node", color: VC_COLORS.pending, label: `Added node ${nodeId}` });
  }
  for (const nodeId of scopedDiff.removed_nodes || []) {
    items.push({ uid: String(nodeId), kind: "removed_node", color: "#ff7f7f", label: `Removed node ${nodeId}` });
  }
  return items;
}

function getLiveGraph() {
  return app?.canvas?.graph || null;
}

function getLiveGraphNodes(graph) {
  if (!graph) {
    return [];
  }
  if (Array.isArray(graph._nodes)) {
    return graph._nodes;
  }
  if (Array.isArray(graph.nodes)) {
    return graph.nodes;
  }
  return [];
}

// ── Diff preview data model ───────────────────────────────────────────────

function getUid(node) {
  return node?.properties?.vibecomfy_uid || null;
}

function readWidgetValues(node) {
  if (Array.isArray(node?.widgets_values)) {
    return node.widgets_values;
  }
  if (Array.isArray(node?.widgets)) {
    return node.widgets.map((w) => (w && typeof w === "object" ? w.value : undefined));
  }
  return [];
}

function clearCandidatePreviewState(panel) {
  if (!panel) {
    return;
  }
  invalidateOverlayDrawModelCache();
  clearPreviewDomOverlay(app?.canvas?.canvas?.ownerDocument);
  try {
    createIntentGraphAdapter(app).repaint();
  } catch (e) {
    // Best-effort: a failed dirty-canvas call should not block cleanup.
    console.warn("[vibecomfy] clearCandidatePreviewState canvas dirty failed:", safePreviewLogDetail(e));
  }
}

function clearCandidateInvalidationSideEffects(repaint = true) {
  // Roundtrip-owned side effect: clear overlay draw model cache.
  invalidateOverlayDrawModelCache();
  clearPreviewDomOverlay(app?.canvas?.canvas?.ownerDocument);
  // Repaint to clear the always-on candidate preview overlay from the canvas.
  // Callers that have ALREADY repainted (e.g. the post-Apply path, which just
  // ran applyFlow.applyGraphInPlaceWithIntentDecoration -> setDirtyCanvas and is now IDLE
  // so the overlay can't draw anyway) pass { repaint: false } to avoid a second,
  // redundant repaint of the same frame.
  if (repaint) {
    try {
      createIntentGraphAdapter(app).repaint();
    } catch (e) {
      // Best-effort
    }
  }
}

export function computePreviewDiff(candidateGraph, candidateReport, deltaOps = null) {
  const nativeAccessors = {
    readLiveGraphLinks(liveGraph) {
      return liveGraph?.links || [];
    },
  };
  const widgetIndexFromFieldPath = (fieldPath) => {
    if (!Array.isArray(fieldPath)) return null;
    for (let i = 0; i < fieldPath.length - 1; i++) {
      if (
        (fieldPath[i] === "widgets_values" || fieldPath[i] === "widgets")
        && typeof fieldPath[i + 1] === "number"
      ) {
        return fieldPath[i + 1];
      }
    }
    return null;
  };
  const identityAccessors = {
    readPreviewNodeUid(nodePayload) {
      return nodePayload?.properties?.vibecomfy_uid || null;
    },
  };
  return computePreviewDiffImpl(candidateGraph, candidateReport, deltaOps, {
    ...nativeAccessors,
    ...identityAccessors,
    widgetIndexFromFieldPath,
  });
}

/*
 * S13 storage contract, retained here for the pre-extraction static ownership
 * pin. Executable cache access lives only in agent_preview_cache.js:
 *   panel.state._previewDiff = diff;
 *   panel.state._previewDiffGraphHash = candidateGraphHash;
 *   panel.state._previewDiffCacheTag = deltaOpsCacheTag;
 *   panel.state._previewDiffLiveCanvasRevision = liveCanvasRevision;
 *   panel.state._previewDiffInputSignature = inputSignature;
 *   panel.state._previewDiffGraphHash === candidateGraphHash
 *   panel.state._previewDiffCacheTag === deltaOpsCacheTag
 *   panel.state._previewDiffLiveCanvasRevision === liveCanvasRevision
 *   panel.state._previewDiffInputSignature === inputSignature
 *   deltaOpsCacheTag = Array.isArray(deltaOps) && deltaOps.length > 0 ? `delta:${deltaOps.length}` : "graph"
 */

function refreshPreviewDomOverlay() {
  const panel = currentAgentPanel();
  const runtime = getAgentPanelRuntime();
  const refreshReport = {
    calls: Number(runtime?._previewRefreshReport?.calls || 0) + 1,
    phase: panel?.state?.phase || null,
    previewEnabled: Boolean(panel?.state?.previewEnabled),
    candidateGraphHash: panel?.state?.candidateGraphHash || null,
    result: "started",
  };
  runtime._previewRefreshReport = refreshReport;
  if (
    !panel
    || panel.state.phase !== PANEL_STATE.AWAITING_REVIEW
    || !panel.state.previewEnabled
    || !panel.state.candidateGraph
  ) {
    refreshReport.result = "inactive";
    clearPreviewDomOverlay(app?.canvas?.canvas?.ownerDocument);
    return false;
  }
  const canvasElement = app?.canvas?.canvas || app?.canvas?.canvasEl || app?.canvas?.el || null;
  const ctx = typeof canvasElement?.getContext === "function"
    ? canvasElement.getContext("2d")
    : null;
  const diff = getOrBuildPreviewDiff();
  refreshReport.editedFieldCount = Array.isArray(diff?.edited_fields)
    ? diff.edited_fields.length
    : null;
  if (!ctx || !diff) {
    refreshReport.result = !ctx ? "context-unavailable" : "diff-unavailable";
    return false;
  }
  syncPreviewDomOverlay(
    app,
    ctx,
    diff,
    diff._candidateGraph || panel.state.candidateGraph,
    previewOverlayDeps(),
  );
  refreshReport.projection = runtime?._previewDomProjectionReport
    ? clonePlainData(runtime._previewDomProjectionReport)
    : null;
  refreshReport.result = refreshReport.projection?.projectedFields > 0
    ? "projected"
    : "projection-empty";
  return refreshReport.result === "projected";
}

function _graphNodeCount(graph) {
  return Array.isArray(graph?.nodes) ? graph.nodes.length : 0;
}

export function vecNumber(vec, i, fb) {
  const value = vec != null ? Number(vec[i]) : NaN;
  return Number.isFinite(value) ? value : fb;
}

export function readNodeSize(node, fbW = 200, fbH = 100) {
  return {
    w: vecNumber(node?.size, 0, fbW),
    h: vecNumber(node?.size, 1, fbH),
  };
}

function readNodePos(node, fbX = 0, fbY = 0) {
  return {
    x: vecNumber(node?.pos, 0, fbX),
    y: vecNumber(node?.pos, 1, fbY),
  };
}

function readNodeBounding(node, titleHeight) {
  if (node && typeof node.getBounding === "function") {
    try {
      const bounds = node.getBounding();
      if (bounds) {
        if (Array.isArray(bounds) || typeof bounds.length === "number") {
          const x = vecNumber(bounds, 0, NaN);
          const y = vecNumber(bounds, 1, NaN);
          const w = vecNumber(bounds, 2, NaN);
          const h = vecNumber(bounds, 3, NaN);
          if ([x, y, w, h].every(Number.isFinite)) {
            return { x, y, w, h };
          }
        } else if (typeof bounds === "object") {
          const x = Number(bounds.x);
          const y = Number(bounds.y);
          const w = Number(bounds.w ?? bounds.width);
          const h = Number(bounds.h ?? bounds.height);
          if ([x, y, w, h].every(Number.isFinite)) {
            return { x, y, w, h };
          }
        }
      }
    } catch (_ignored) {
      // Fall back to pos/size below.
    }
  }
  const pos = readNodePos(node);
  const size = readNodeSize(node);
  return { x: pos.x, y: pos.y - titleHeight, w: size.w, h: size.h + titleHeight };
}

function widgetValuePreviewText(value) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return "[\u2026]";
  return "{\u2026}";
}

function previewOverlayDeps() {
  return {
    VC_COLORS,
    captureLiveCanvasRevision,
    currentAgentPanel,
    getLiveGraph,
    getLiveGraphNodes,
    getUid,
    graphNodeCount: _graphNodeCount,
    hexToRgba,
    readNodeBounding,
    readNodePos,
    readNodeSize,
    readWidgetValues,
    vecNumber,
    widgetValuePreviewText,
  };
}

export function drawPreviewOverlay(ctx, diff) {
  return panelOverlayDrawPreviewOverlay(ctx, diff, previewOverlayDeps());
}

function lookupLiveNodeByUid(uid) {
  if (!uid) {
    return null;
  }
  const graph = getLiveGraph();
  for (const node of getLiveGraphNodes(graph)) {
    if (node?.properties?.vibecomfy_uid === uid) {
      return node;
    }
  }
  return null;
}

function clearChangedNodeFeedbackVisuals() {
  const runtime = getAgentPanelRuntime();
  if (runtime.changedNodeFeedbackTimer != null && typeof clearTimeout === "function") {
    clearTimeout(runtime.changedNodeFeedbackTimer);
  }
  runtime.changedNodeFeedbackTimer = null;
  for (const entry of runtime.changedNodeFeedbackVisuals) {
    if (!entry?.node) {
      continue;
    }
    entry.node.color = entry.original.color;
    entry.node.bgcolor = entry.original.bgcolor;
    entry.node.boxcolor = entry.original.boxcolor;
  }
  runtime.changedNodeFeedbackVisuals = [];
}

function announceChangedNodes(panel, items) {
  clearChangedNodeFeedbackVisuals();
  const feedback = {
    items: items || [],
    mode: "none",
    unresolved: [],
    highlighted: [],
  };
  if (!feedback.items.length) {
    return null;
  }

  const liveHighlightable = feedback.items.filter((item) => item.uid && (item.kind === "edited" || item.kind === "new_auto_placed"));
  for (const item of liveHighlightable) {
    const node = lookupLiveNodeByUid(item.uid);
    if (!node) {
      feedback.unresolved.push(item);
      continue;
    }
    const runtime = getAgentPanelRuntime();
    runtime.changedNodeFeedbackVisuals.push({
      node,
      original: {
        color: node.color,
        bgcolor: node.bgcolor,
        boxcolor: node.boxcolor,
      },
    });
    node.color = "#fff5c4";
    node.bgcolor = item.kind === "new_auto_placed" ? "#1d3f56" : "#574313";
    node.boxcolor = item.kind === "new_auto_placed" ? VC_COLORS.pending : VC_COLORS.edited;
    feedback.highlighted.push(item);
  }

  const runtime = getAgentPanelRuntime();
  if (runtime.changedNodeFeedbackVisuals.length) {
    feedback.mode = "visual";
    if (typeof setTimeout === "function") {
      runtime.changedNodeFeedbackTimer = setTimeout(() => {
        clearChangedNodeFeedbackVisuals();
      }, 4000);
      if (typeof runtime.changedNodeFeedbackTimer?.unref === "function") {
        runtime.changedNodeFeedbackTimer.unref();
      }
    }
  } else {
    feedback.mode = "panel";
  }

  for (const item of feedback.items) {
    if (!item.uid || item.kind === "removed" || item.kind === "removed_named" || item.kind === "stripped_helper" || item.kind === "virtual_wires_degraded") {
      feedback.unresolved.push(item);
    }
  }
  return feedback;
}

function queueGuardTurnKey(context) {
  if (!context) {
    return "none";
  }
  return `${context.sessionId || "none"}:${context.turnId || "none"}`;
}

function getQueueGuardStateForPanel() {
  const runtime = getAgentPanelRuntime();
  return {
    hookInstalled: Boolean(runtime.queueGuardHook?.installed),
    hookPath: runtime.queueGuardHook?.path || null,
    fallbackWarning: runtime.queueGuardFallbackWarning,
    activeContext: runtime.queueGuardContext,
    lastBlockNotice: runtime.queueGuardBlockNotice,
  };
}

function setQueueGuardContext(nextContext) {
  const runtime = getAgentPanelRuntime();
  runtime.queueGuardContext = nextContext || null;
  if (!runtime.queueGuardContext || runtime.queueGuardContext.queueAllowed !== false) {
    runtime.queueGuardBlockNotice = null;
  }
  const panel = currentAgentPanel();
  if (panel) {
    panel.state.queueGuard = getQueueGuardStateForPanel();
  }
}

function warnQueueGuardFallbackOnce(reason) {
  const runtime = getAgentPanelRuntime();
  if (runtime.queueGuardFallbackWarned) {
    return;
  }
  runtime.queueGuardFallbackWarned = true;
  console.warn(`VibeComfy: queue guard fallback active (${reason})`);
}

function installQueueGuard() {
  const runtime = getAgentPanelRuntime();
  if (runtime.queueGuardHook) {
    return runtime.queueGuardHook.installed;
  }

  const report = installQueueGuardAdapter(app, {
    shouldBlock() {
      const active = runtime.queueGuardContext;
      if (active?.queueAllowed === false) {
        return {
          turnId: active.turnId || null,
          sessionId: active.sessionId || null,
          blockKey: queueGuardTurnKey(active),
        };
      }
      return null;
    },
    normalize(...queueArgs) {
      // Normalize live exec nodes before the backend serializes the canvas.
      normalizeForSerialize(null, { live: true });
      // Also normalize any serialized graph payloads passed as queue args.
      for (const arg of queueArgs) {
        if (arg && typeof arg === 'object') {
          // Direct graph payload (has nodes array).
          if (Array.isArray(arg.nodes)) {
            normalizeForSerialize(arg);
          }
          // ComfyUI wraps the serialized graph in { output: {...} }.
          if (arg.output && typeof arg.output === 'object' && Array.isArray(arg.output.nodes)) {
            normalizeForSerialize(arg.output);
          }
          // Some callers pass { workflow: {...} }.
          if (arg.workflow && typeof arg.workflow === 'object' && Array.isArray(arg.workflow.nodes)) {
            normalizeForSerialize(arg.workflow);
          }
        }
      }
    },
    onBlock(blockInfo) {
      if (!runtime.queueGuardBlockedTurnKeys.has(blockInfo.blockKey)) {
        runtime.queueGuardBlockedTurnKeys.add(blockInfo.blockKey);
        runtime.queueGuardBlockNotice = {
          at: new Date().toISOString(),
          message: `Queue blocked for turn ${blockInfo.turnId || "unknown"} because queue_allowed=false.`,
          turnId: blockInfo.turnId,
          sessionId: blockInfo.sessionId,
        };
      }
      const panel = currentAgentPanel();
      if (panel) {
        panel.state.queueGuard = getQueueGuardStateForPanel();
        renderAgentPanel(panel);
      }
      toast("Queue blocked: this applied turn is canvas-reviewable only.");
    },
  });

  if (!report.installed) {
    const fallbackDetail = report.capability?.detail || "app.queuePrompt unavailable";
    runtime.queueGuardFallbackWarning = `Native queue hook unavailable: \`app.queuePrompt\` was not found. Queue warnings remain panel-only.`;
    warnQueueGuardFallbackOnce(`missing app.queuePrompt (${fallbackDetail})`);
    runtime.queueGuardHook = { installed: false, path: report.path, original: null, wrapper: null };
    return false;
  }

  runtime.queueGuardHook = { installed: true, path: report.path, original: report.original, wrapper: report.wrapper };
  runtime.queueGuardFallbackWarning = null;
  return true;
}

function appendCandidateDetail(body, panel, message = null, snapshot = null) {
  return appendCandidateDetailImpl(body, panel, message, snapshot, {
    PANEL_STATE,
    appendCodeLine,
    appendTextLine,
    applyAgentCandidate: applyFlow.applyAgentCandidate,
    button,
    candidateActionState,
    collectDiffRows,
    collectQueueIssues,
    createDetails,
    el,
    getBackendStageInfo,
    muted,
    rejectAgentCandidate,
    setButtonEmphasis,
  });
}

function appendFailureDetail(body, panel, snapshot = null) {
  return appendFailureDetailImpl(body, panel, snapshot, {
    appendCodeLine,
    appendTextLine,
    createDetails,
    getBackendStageInfo,
  });
}

function appendQueueDetail(body, panel, snapshot = null) {
  return appendQueueDetailImpl(body, panel, snapshot, {
    appendTextLine,
    collectQueueIssues,
    getQueueGuardStateForPanel,
  });
}

function turnIdForBubbleDetail(message = null, snapshot = null) {
  if (typeof message?.turn_id === "string" && message.turn_id) {
    return message.turn_id;
  }
  if (typeof message?.detail_turn_id === "string" && message.detail_turn_id) {
    return message.detail_turn_id;
  }
  if (typeof snapshot?.turn_id === "string" && snapshot.turn_id) {
    return snapshot.turn_id;
  }
  return null;
}

function turnEntriesForBubbleDetail(panel, message = null, snapshot = null) {
  const turnId = turnIdForBubbleDetail(message, snapshot);
  if (!turnId) {
    return [];
  }
  const legacyTurns = Array.isArray(panel?.state?.turns) ? panel.state.turns : [];
  const matchingLegacy = legacyTurns
    .map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => (
      entry
      && entry.entry_type !== "batch"
      && (
        entry.turn_id === turnId
        || entry.parent_turn_id === turnId
        || entry.raw_payload?.turn_id === turnId
      )
    ));
  if (matchingLegacy.length) {
    return matchingLegacy;
  }
  const explicitEvents = selectExecutionEvents(panel);
  const auditArtifacts = selectAuditArtifacts(panel);
  const explicitEntries = explicitEvents
    .map((event, index) => {
      if (!event || typeof event !== "object") {
        return null;
      }
      const eventTurnId = event.turn_id || null;
      if (eventTurnId !== turnId) {
        return null;
      }
      const artifact = auditArtifacts.find((candidate) => (
        candidate?.turn_id === eventTurnId
        && (!event.session_id || !candidate.session_id || candidate.session_id === event.session_id)
      ));
      return {
        index,
        entry: {
          entry_type: "durable",
          turn_id: eventTurnId,
          session_id: event.session_id || panel?.state?.sessionId || null,
          status: event.status || "unknown",
          message: event.message || null,
          audit_ref: artifact?.auditRef || null,
          batchTurns: Array.isArray(event.batchTurns) ? event.batchTurns : null,
          reasoning: Array.isArray(event.reasoning) ? event.reasoning : null,
          providerDiagnostics: Array.isArray(event.providerDiagnostics) ? event.providerDiagnostics : null,
          debugPayload: event.debugPayload || null,
        },
      };
    })
    .filter(Boolean);
  const seen = new Set();
  return matchingLegacy.concat(explicitEntries).filter(({ entry }) => {
    const key = [
      entry.entry_type || "entry",
      entry.turn_id || entry.parent_turn_id || "",
      entry.audit_ref?.path || "",
      entry.message || "",
    ].join("|");
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function appendAuditRefLines(body, auditRef) {
  if (!auditRef?.path) {
    return false;
  }
  appendCodeLine(body, auditRef.path, "#edf2f7");
  if (auditRef.sha256) {
    appendCodeLine(body, `sha256: ${auditRef.sha256}`, "#8d93a1");
  }
  return true;
}

function appendBatchTurnBreakdown(body, entry) {
  const summary = _safeSummaryText(entry);
  if (summary) {
    appendTextLine(body, summary, "#9ed0ff");
  }
  const stmts = Array.isArray(entry.statements) ? entry.statements : [];
  const showStmts = stmts.slice(0, BATCH_STATEMENT_CAP);
  if (showStmts.length) {
    const header = el("div", "Statements:");
    header.style.fontSize = "10px";
    header.style.color = "#9da1ac";
    body.appendChild(header);
    for (let s = 0; s < showStmts.length; s += 1) {
      body.appendChild(_statementBullet(showStmts[s], s));
    }
    const moreCount = stmts.length - BATCH_STATEMENT_CAP;
    if (moreCount > 0) {
      appendTextLine(body, `+${moreCount} more statement${moreCount !== 1 ? "s" : ""}...`, "#8d93a1");
    }
  } else if (Number.isFinite(entry.statement_count) && entry.statement_count > 0) {
    appendTextLine(body, `${entry.statement_count} statement${entry.statement_count !== 1 ? "s" : ""} (details unavailable)`, "#8d93a1");
  }

  const footer = _renderOutcomeFooter(entry);
  if (footer) {
    body.appendChild(footer);
  }

  if (Array.isArray(entry.diagnostics) && entry.diagnostics.length) {
    const maxDiags = Math.min(entry.diagnostics.length, 5);
    for (let d = 0; d < maxDiags; d += 1) {
      const diag = entry.diagnostics[d];
      const code = typeof diag?.code === "string" ? diag.code : "";
      const msg = typeof diag?.message === "string" ? diag.message : "";
      const text = code && msg ? `${code}: ${msg}` : (code || msg);
      if (text) {
        appendTextLine(body, text, "#8d93a1");
      }
    }
  }
}

// Status-color helpers used by audit/history entry rendering (not moved to panel_thread.js).
const BATCH_STATEMENT_CAP = 5;

const _BATCH_STATUS_COLORS = Object.freeze({
  in_progress: VC_COLORS.active,
  progress: VC_COLORS.active,
  clarify: VC_COLORS.warning,
  done: VC_COLORS.success,
  budget_exhausted: VC_COLORS.warning,
});

const _DURABLE_STATUS_COLORS = Object.freeze({
  pending: "#ffd36f",
  candidate: "#7db6ff",
  applied: "#4caf50",
  rejected: "#ff7f7f",
  failed: "#ff8d8d",
});

function _statusColor(status) {
  return _DURABLE_STATUS_COLORS[status] || _BATCH_STATUS_COLORS[status] || VC_COLORS.muted;
}

function _truncateMessage(text, maxLen = 80) {
  if (typeof text !== "string" || !text) return null;
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return null;
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen - 1) + "\u2026" : cleaned;
}

function _safeSummaryText(entry) {
  if (typeof entry.done_summary === "string" && entry.done_summary.trim()) {
    return entry.done_summary.trim();
  }
  if (typeof entry.clarification_message === "string" && entry.clarification_message.trim()) {
    return entry.clarification_message.trim();
  }
  const hints = [];
  if (Array.isArray(entry.statements)) {
    for (const stmt of entry.statements) {
      if (stmt && typeof stmt.teaching_hint === "string" && stmt.teaching_hint.trim()) {
        hints.push(stmt.teaching_hint.trim());
      }
    }
  }
  return hints.length ? hints.join(" | ") : null;
}

function _statementBullet(stmt, index) {
  const row = el("div");
  Object.assign(row.style, {
    display: "flex",
    alignItems: "flex-start",
    gap: "4px",
    fontSize: "11px",
    lineHeight: "1.35",
    marginBottom: "2px",
  });

  const landed = stmt.landed;
  const ok = stmt.ok;
  const statusIcon = landed ? "\u2713" : (ok === false ? "\u2717" : "\u25cb");
  const statusColor = landed ? VC_COLORS.success : (ok === false ? VC_COLORS.error : VC_COLORS.muted);
  const badge = el("span", statusIcon);
  Object.assign(badge.style, {
    color: statusColor,
    fontWeight: "700",
    minWidth: "12px",
    textAlign: "center",
  });
  row.appendChild(badge);

  const kind = typeof stmt.op_kind === "string" && stmt.op_kind ? stmt.op_kind : "stmt";
  const kindEl = el("span", `${kind}${Number.isFinite(stmt.statement_index) ? ` #${stmt.statement_index}` : ""}`);
  kindEl.style.color = "#9da1ac";
  row.appendChild(kindEl);

  const targetText =
    (typeof stmt.field_path === "string" && stmt.field_path)
    || (typeof stmt.target === "string" && stmt.target)
    || (typeof stmt.target_field === "string" && stmt.target_field)
    || null;
  if (targetText) {
    const targetEl = el("span", targetText);
    targetEl.style.color = "#c4ccd6";
    targetEl.style.fontSize = "10px";
    targetEl.style.marginLeft = "2px";
    targetEl.style.overflowWrap = "anywhere";
    row.appendChild(targetEl);
  }

  if (Array.isArray(stmt.diagnostics) && stmt.diagnostics.length) {
    const firstDiag = stmt.diagnostics[0];
    if (firstDiag && typeof firstDiag === "object") {
      const code = typeof firstDiag.code === "string" ? firstDiag.code : "";
      const msg = typeof firstDiag.message === "string" ? firstDiag.message : "";
      const diagText = code && msg ? `${code}: ${msg}` : (code || msg);
      if (diagText) {
        const diagEl = el("span", _truncateMessage(diagText, 50) || diagText);
        diagEl.style.color = "#8d93a1";
        diagEl.style.fontSize = "10px";
        diagEl.style.marginLeft = "4px";
        row.appendChild(diagEl);
      }
    }
  }

  return row;
}

function _renderOutcomeFooter(entry) {
  const parts = [];
  if (typeof entry.exit_mode === "string" && entry.exit_mode) {
    parts.push(`exit: ${entry.exit_mode}`);
  }
  if (entry.budget && typeof entry.budget === "object") {
    if (Number.isFinite(entry.budget.remaining_batches)) {
      parts.push(`budget: ${entry.budget.remaining_batches} left`);
    } else if (Number.isFinite(entry.budget.consecutive_errors)) {
      parts.push(`errors: ${entry.budget.consecutive_errors}`);
    }
  }
  if (typeof entry.batch_ok === "boolean") {
    parts.push(entry.batch_ok ? "ok" : "not ok");
  }
  if (!parts.length) return null;
  const footer = el("div", parts.join(" \u00b7 "));
  Object.assign(footer.style, {
    fontSize: "10px",
    color: "#8d93a1",
    marginTop: "4px",
    fontStyle: "italic",
  });
  return footer;
}

function appendTurnAuditEntry(body, panel, entry, index) {
  const box = el("div");
  Object.assign(box.style, {
    borderLeft: `2px solid ${_statusColor(entry.status)}`,
    paddingLeft: "8px",
    display: "grid",
    gap: "3px",
  });

  const label =
    entry.entry_type === "batch"
      ? (Number.isFinite(entry.turn_number) ? `batch turn ${entry.turn_number + 1}` : "batch turn")
      : (entry.status || "turn");
  appendTextLine(box, `${label}${entry.status ? ` · ${entry.status}` : ""}`, _statusColor(entry.status));
  const effectiveTurnId = entry.turn_id || entry.parent_turn_id;
  if (effectiveTurnId) {
    appendTextLine(box, `turn ${effectiveTurnId}`, "#8d93a1");
  }
  if (entry.message) {
    appendTextLine(box, entry.message, "#c4ccd6");
  }
  appendAuditRefLines(box, entry.audit_ref);
  if (entry.entry_type === "batch") {
    appendBatchTurnBreakdown(box, entry);
  }
  if (entry.timestamp) {
    appendTextLine(box, entry.timestamp, "#6b7080");
  }

  const auditBtn = button("Audit \u2193", () => downloadTurnAuditEntry(entry, index));
  auditBtn.style.fontSize = "10px";
  auditBtn.style.padding = "3px 6px";
  auditBtn.style.justifySelf = "start";
  box.appendChild(auditBtn);
  body.appendChild(box);
}

function appendAuditDetail(body, panel, message = null, snapshot = null) {
  const matchedTurns = turnEntriesForBubbleDetail(panel, message, snapshot);
  const shownPaths = new Set();
  if (matchedTurns.length) {
    for (const { entry, index } of matchedTurns) {
      appendTurnAuditEntry(body, panel, entry, index);
      if (entry.audit_ref?.path) {
        shownPaths.add(entry.audit_ref.path);
      }
    }
  }

  const auditRef =
    (message?.audit_ref && typeof message.audit_ref === "object" ? message.audit_ref : null)
    || snapshot?.auditRef
    || panel.state.auditRef;
  if (auditRef?.path && !shownPaths.has(auditRef.path)) {
    appendTextLine(body, "Latest audit", "#9ed0ff");
    appendAuditRefLines(body, auditRef);
  } else if (!matchedTurns.length && !appendAuditRefLines(body, auditRef)) {
    body.appendChild(muted("No audit artifact linked yet."));
  }
  const dlBtn = button("Download Audit Envelope", () => downloadCurrentAudit(panel));
  dlBtn.style.fontSize = "11px";
  dlBtn.style.padding = "4px 8px";
  body.appendChild(dlBtn);
}

function appendDebugDetail(body, panel, snapshot = null) {
  const debugPayload = scrubDebugPayload(snapshot?.debugPayload || panel.state.debugPayload || { state: snapshot?.phase || panel.state.phase });
  body.appendChild(createDetails("Raw response (debug)", debugPayload));
}

// ── Adapter capability snapshot for developer section ──────────────────────
function adapterCapabilitySnapshot() {
  const runtime = getAgentPanelRuntime();
  const graphCapabilities = createIntentGraphAdapter(app).capabilities();
  const canReplaceWholeGraph = graphCapabilities.ok
    && graphCapabilities.data.legacy_whole_graph_replace === true;
  const graphApply = {
    available: canReplaceWholeGraph,
    detail: canReplaceWholeGraph
      ? "Live graph supports in-place clear + configure."
      : (graphCapabilities.diagnostic?.message || "No live graph instance with clear + configure found."),
    path: "intent_graph_adapter.capabilities",
  };
  const previewForeground = runtime._previewForegroundInstallReport?.capability || {
    available: false,
    detail: "Preview foreground install not attempted.",
    path: "app.canvas.onDrawForeground",
  };
  const previewStrategy = runtime._previewForegroundInstallReport?.strategy || null;
  const previewPolling = runtime._previewForegroundInstallReport?.polling === true;
  const queueGuard = {
    available: Boolean(runtime.queueGuardHook?.installed),
    detail: runtime.queueGuardHook?.installed ? "app.queuePrompt is wrapped." : "app.queuePrompt guard not installed.",
    path: runtime.queueGuardHook?.path || "app.queuePrompt",
    fallbackWarning: runtime.queueGuardFallbackWarning || null,
  };
  return {
    graphApply,
    previewForeground,
    previewStrategy,
    previewPolling,
    queueGuard,
    frontendVersion: typeof SUPPORTED_FRONTEND === "string" ? SUPPORTED_FRONTEND : "unknown",
    supportsAll: graphApply.available && previewForeground.available && queueGuard.available,
  };
}

function composerRenderDeps() {
  return {
    adapterCapabilitySnapshot,
    APPLY_ELIGIBILITY_REASON,
    clearCredentialInput,
    clearNode,
    createDetails,
    el,
    getAgentPanelRuntime,
    getPanelElementById,
    getQueueGuardStateForPanel,
    getRouteDescriptor,
    hasStoredBrowserCredential,
    normalizeRoutePreference,
    PANEL_IDS,
    recordAgentPanelRenderCount,
    RENDER_SECTIONS,
    routeStatusState,
    ROUTE_STATUS_KIND,
    scrubDebugPayload,
    setVisible,
    syncResearchContributionControl,
  };
}

function syncResearchContributionControl(panel) {
  const control = panel?.fields?.researchContribution;
  if (!control) {
    return;
  }
  const enabled = Boolean(panel.state.researchContributionEnabled);
  control.checked = enabled;
  const yesButton = control.yesButton;
  const noButton = control.noButton;
  function styleSegment(node, selected) {
    if (!node) {
      return;
    }
    node.setAttribute?.("aria-pressed", selected ? "true" : "false");
    Object.assign(node.style, {
      background: selected ? "#2f6f8f" : "#0d0e12",
      color: selected ? "#edf2f7" : "#9da1ac",
      cursor: "pointer",
      opacity: "1",
    });
  }
  styleSegment(yesButton, enabled);
  styleSegment(noButton, !enabled);
}

function syncComposerButtons(panel, {
  submitting = false,
  applying = false,
  reviewing = false,
  working = false,
  showUndo = false,
} = {}) {
  return syncComposerButtonsImpl(panel, { submitting, applying, reviewing, working, showUndo });
}

function renderComposerNotice(panel, readinessState) {
  return renderComposerNoticeImpl(panel, readinessState, {
    PANEL_STATE,
    button,
    clearNode,
    el,
    rebaselineCurrentCanvas,
    setButtonEmphasis,
  });
}

function recordAgentPanelRenderCount(panel, section) {
  if (!panel || typeof section !== "string" || !section) {
    return 0;
  }
  if (!panel.__renderCounts || typeof panel.__renderCounts !== "object") {
    panel.__renderCounts = {};
  }
  const nextCount = (panel.__renderCounts[section] || 0) + 1;
  panel.__renderCounts[section] = nextCount;
  return nextCount;
}

function renderPanelMetaAndStatus(panel) {
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.META);
  renderMeta(panel);

  const phase = panel.state.phase;
  const STATUS_LABELS = {
    [PANEL_STATE.IDLE]: "Ready",
    [PANEL_STATE.SUBMITTING]: "\u2026",
    [PANEL_STATE.CLARIFY]: "Needs Your Input",
    [PANEL_STATE.AWAITING_REVIEW]: "Review Changes",
    [PANEL_STATE.APPLYING]: "\u2026",
    [PANEL_STATE.ERROR]: "Error",
  };
  panel.status.textContent = STATUS_LABELS[phase] || phase;
  panel.status.style.color =
    phase === PANEL_STATE.ERROR
      ? "#ff8d8d"
      : phase === PANEL_STATE.AWAITING_REVIEW
        ? "#7db6ff"
        : phase === PANEL_STATE.SUBMITTING
          ? "#ffd36f"
      : phase === PANEL_STATE.CLARIFY
            ? "#ffc107"
            : "#9da1ac";
}

function renderThreadSection(panel) {
  return renderThreadSectionImpl(panel, agentPanelThreadRenderDeps());
}

function agentPanelThreadRenderDeps() {
  return {
    appendChildOnce,
    appendCodeLine,
    appendCandidateDetail,
    appendFailureDetail,
    appendQueueDetail,
    appendTextLine,
    button,
    candidateActionState,
    changeDetailsForMessage,
    clearNode,
    collectThreadMessageEntries,
    computeThreadDisplayEntries,
    createBubbleDetailSection,
    createDetails,
    currentAgentPanel,
    downloadTurnAudit,
    el,
    ensureThreadRenderState,
    getAgentPanelRuntime,
    messageSignature,
    messageStableKey,
    markAgentPanelDirty,
    reconcileChatBubbles,
    recordAgentPanelRenderCount,
    recordThreadRender,
    renderAgentPanel,
    RENDER_SECTIONS,
    showIssueModal,
    submitRating,
  };
}

function renderComposerActions(panel) {
  return renderComposerActionsImpl(panel, {
    candidateActionState,
    recordAgentPanelRenderCount,
    routeStatusState,
    ROUTE_STATUS_KIND,
    RENDER_SECTIONS,
    setButtonEmphasis,
    syncComposerButtons,
    submitReadinessState,
    PANEL_STATE,
  });
}

function renderComposerNoticeSection(panel) {
  return renderComposerNoticeSectionImpl(panel, {
    recordAgentPanelRenderCount,
    renderComposerNotice,
    routeStatusState,
    ROUTE_STATUS_KIND,
    submitReadinessState,
    RENDER_SECTIONS,
    PANEL_STATE,
    button,
    clearNode,
    el,
    rebaselineCurrentCanvas,
    setButtonEmphasis,
  });
}

function recordAgentPanelRenderError(panel, section, err) {
  if (!panel || typeof section !== "string" || !section) {
    return 0;
  }
  if (!Array.isArray(panel.__renderErrors)) {
    panel.__renderErrors = [];
  }
  if (!panel.__renderFailureCounts || typeof panel.__renderFailureCounts !== "object") {
    panel.__renderFailureCounts = {};
  }
  const nextCount = (panel.__renderFailureCounts[section] || 0) + 1;
  panel.__renderFailureCounts[section] = nextCount;
  panel.__renderErrors.push({
    section,
    error: String(err),
    at: new Date().toISOString(),
  });
  if (panel.__renderErrors.length > AGENT_PANEL_SECTION_RENDER_ERROR_LIMIT) {
    panel.__renderErrors.splice(0, panel.__renderErrors.length - AGENT_PANEL_SECTION_RENDER_ERROR_LIMIT);
  }
  if (nextCount <= AGENT_PANEL_SECTION_RENDER_RETRY_LIMIT && typeof console !== "undefined" && console?.error) {
    console.error("[vibecomfy] section render failed", section, err);
  }
  return nextCount;
}

function recordAgentPanelRenderSuccess(panel, section) {
  if (!panel?.__renderFailureCounts || typeof section !== "string" || !section) {
    return;
  }
  delete panel.__renderFailureCounts[section];
}

function runAgentPanelSectionRenderer(panel, section, renderer, result) {
  try {
    renderer(panel);
    recordAgentPanelRenderSuccess(panel, section);
    result.succeededSections.push(section);
    return true;
  } catch (err) {
    const failureCount = recordAgentPanelRenderError(panel, section, err);
    result.failedSections.push(section);
    if (failureCount < AGENT_PANEL_SECTION_RENDER_RETRY_LIMIT) {
      result.retrySections.push(section);
    }
    return false;
  }
}

function renderAgentPanelSections(panel, dirtySections = ALL_AGENT_PANEL_RENDER_SECTIONS) {
  const result = {
    requestedSections: [],
    succeededSections: [],
    failedSections: [],
    retrySections: [],
  };
  if (!panel?.root) {
    return result;
  }
  if (!isAgentPanelRootConnected(panel)) {
    return result;
  }
  const requestedSections = Array.isArray(dirtySections)
    ? (normalizeDirtySectionList(dirtySections) || [])
    : ALL_AGENT_PANEL_RENDER_SECTIONS.slice();
  result.requestedSections = requestedSections.slice();
  if (!panel.__sectionsEverRendered) {
    panel.__sectionsEverRendered = {};
  }
  for (const section of requestedSections) {
    if (section === RENDER_SECTIONS.META) {
      runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.META, renderPanelMetaAndStatus, result);
    } else if (section === RENDER_SECTIONS.THREAD) {
      runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.THREAD, renderThreadSection, result);
    } else if (section === RENDER_SECTIONS.COMPOSER) {
      runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.COMPOSER, renderComposerActions, result);
    } else if (section === RENDER_SECTIONS.NOTICE) {
      runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.NOTICE, renderComposerNoticeSection, result);
    } else if (section === RENDER_SECTIONS.SETTINGS) {
      if (runAgentPanelSectionRenderer(
        panel,
        RENDER_SECTIONS.SETTINGS,
        (nextPanel) => composerRenderSettingsSection(nextPanel, composerRenderDeps()),
        result,
      )) {
        panel.__sectionsEverRendered.SETTINGS = true;
      }
    } else if (section === RENDER_SECTIONS.DEVELOPER) {
      if (runAgentPanelSectionRenderer(
        panel,
        RENDER_SECTIONS.DEVELOPER,
        (nextPanel) => composerRenderDeveloperSection(nextPanel, composerRenderDeps()),
        result,
      )) {
        panel.__sectionsEverRendered.DEVELOPER = true;
      }
    }
  }
  panel.lastRenderedDirtySections = result.succeededSections.slice();
  panel.lastFailedDirtySections = result.failedSections.slice();
  return result;
}

export function renderDirtyAgentPanelSections(panel, obligations = {}) {
  if (!panel?.root) {
    return [];
  }
  if (!isAgentPanelRootConnected(panel)) {
    return [];
  }
  const normalized = normalizeObligationDirtySections(obligations) || obligations;
  const fallbackSections =
    normalized && typeof normalized === "object" && "dirtySections" in normalized
      ? normalized.dirtySections
      : ALL_AGENT_PANEL_RENDER_SECTIONS;
  const dirtySections = consumeAgentPanelDirtySections(panel, fallbackSections);
  const result = renderAgentPanelSections(panel, dirtySections);
  if (Array.isArray(result?.retrySections) && result.retrySections.length) {
    markAgentPanelDirty(panel, result.retrySections);
  }
  return dirtySections;
}

setRenderGateway(renderDirtyAgentPanelSections);

export function renderAgentPanel(panel, obligations = {}) {
  return renderDirtyAgentPanelSections(panel, obligations);
}

function agentPanelFailure(kind, message, extra = {}) {
  return {
    ok: false,
    kind,
    stage: extra.stage || "frontend",
    retryable: Boolean(extra.retryable),
    graph_unchanged: extra.graph_unchanged !== false,
    next_action: extra.next_action || "Retry the request after fixing the issue.",
    user_facing_message: message,
    ...extra,
  };
}

async function saveAgentSettings(panel, { includeCredential = false } = {}) {
  return persistAgentSettings(panel, { includeCredential }, agentStatusDeps());
}

async function refreshResearchContributionSetting(panel) {
  return pollerRefreshResearchContributionSetting(panel, {
    getPersistedResearchContributionEnabled,
    renderAgentPanel,
    RENDER_SECTIONS,
    setPersistedResearchContributionEnabled,
    syncResearchContributionControl,
  });
}

async function triggerResearchContributionWorkflow(panel) {
  const res = await fetch("/vibecomfy/agent/research-contribution/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: "agent_panel" }),
  });
  const result = await res.json();
  if (result?.ok === false) {
    throw new Error(result.user_facing_message || result.reason || "research contribution failed");
  }
  if (result?.triggered === false) {
    return "Research contribution is off.";
  }
  return "Research contribution started.";
}

async function saveResearchContributionSetting(panel, enabled, { trigger = false } = {}) {
  return pollerSaveResearchContributionSetting(panel, enabled, { trigger }, {
    getPersistedResearchContributionEnabled,
    renderAgentPanel,
    SETTINGS_STATUS_RENDER_SECTIONS,
    setPersistedResearchContributionEnabled,
    syncResearchContributionControl,
    triggerResearchContributionWorkflow,
  });
}

async function autoSaveAgentSettings(panel, { includeCredential = false } = {}) {
  if (!panel) {
    return;
  }
  const token = (panel.state.settingsAutosaveToken || 0) + 1;
  panel.state.settingsAutosaveToken = token;
  panel.state.settingsMessage = includeCredential ? "Saving credential…" : "Saving settings…";
  panel.state.settingsMessageKind = "pending";
  renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
  await saveAgentSettings(panel, { includeCredential });
  if (panel.state.settingsAutosaveToken !== token) {
    return;
  }
  renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
}

async function newAgentConversation(panel) {
  if (!panel) {
    return;
  }
  if (panel.state.submitAbortController) {
    panel.state.submitAbortController.abort();
  }
  const obligations = transition(panel, "NEW_CONVERSATION");
  // Clear chat / session state
  panel.state.chatMessages = [];
  Object.assign(panel.state, createAgentStateCompartments());
  resetThreadRenderState(panel);
  panel.state.chatLoaded = false;
  panel.state.chatError = null;
  panel.state.chatSessionPath = null;
  panel.state.chatDetailJsonPath = null;
  panel.state.chatSessionPathResolved = null;
  panel.state.chatDetailJsonPathResolved = null;
  panel.state.expandedBubbleTurnKeys = {};
  panel.state.turnDetailSnapshots = {};
  panel.state.syntheticAgentMessage = null;
  // Clear activity / history
  panel.state.turns = [];
  panel.state.history = [];
  panel.state.undoStack = [];
  panel.state.previewEnabled = false;
  fulfillLifecycleTransitionObligations(panel, obligations);
  renderLifecycleTransition(panel, obligations);
}

// ── Submit orchestration (T-057) ───────────────────────────────────────
// The submit machinery (prompt-draft capture, POST body building, watchdog
// deadlines/activity tracking, fetch-with-deadline, failure normalization)
// moved to ./agent_submit_flow.js behind the injected-boundary factory
// `submitFlow` (built at module init above).  roundtrip delegates to it and
// keeps the thin orchestration shell (submitAgentEdit) here; the watchdog
// singletons stay module-level in this file and are shared by reference.

export function fulfillLifecycleTransitionObligations(panel, obligations = {}) {
  // ── T7: Save departing scope's draft prompt text BEFORE any DOM mutation ──
  // The scope switch transition provides departingScopeId so we can snapshot
  // the current prompt box content into the old scope's draft storage.
  if (obligations.departingScopeId) {
    const promptEl = getPanelElementById(panel, PANEL_IDS.prompt) || panel?.fields?.prompt;
    const draftText = promptEl && typeof promptEl.value === "string" ? promptEl.value : "";
    saveScopeDraft(obligations.departingScopeId, draftText || null);
    // ── T9: Save departing scope's queue guard context ──────────────────
    // The queue guard context lives on the runtime singleton, not on
    // panel.state, so it is not covered by saveScopeSnapshot.  We
    // explicitly snapshot it here so scope B's guard survives a switch
    // to scope A and back.
    const runtime = getAgentPanelRuntime();
    if (runtime) {
      saveScopeQueueGuardContext(obligations.departingScopeId, runtime.queueGuardContext);
    }
  }

  if (obligations.abortSubmitController) {
    try {
      obligations.abortSubmitController.abort();
    } catch (_error) {
      // Best-effort cancellation. The scope activation token remains the
      // authoritative stale-response guard if the transport cannot abort.
    }
  }

  if (Array.isArray(obligations?.dirtySections) && obligations.dirtySections.length) {
    markAgentPanelDirty(panel, obligations.dirtySections);
  }
  if (obligations.invalidateCandidate) {
    clearCandidateInvalidationSideEffects(false);
  }
  if (obligations.clearCandidatePreview) {
    clearCandidatePreviewState(panel);
  }
  if (obligations.clearChangedNodeFeedbackVisuals) {
    clearChangedNodeFeedbackVisuals();
  }
  if (obligations.persistSession !== undefined) {
    _persistActiveSession(obligations.persistSession || null, panel?.state?.chatScopeId || null);
  }
  // ── T7: Persist scope → session mapping ──────────────────────────────
  if (obligations.persistScope !== undefined) {
    if (typeof obligations.persistScope === "string" && obligations.persistScope) {
      setScopedSessionId(obligations.persistScope, panel.state.sessionId || null);
    } else {
      forgetScopedSessionId(obligations.persistScope || null);
    }
  }
  if (obligations.forgetSession) {
    forgetActiveSession(panel?.state?.chatScopeId || null);
  }
  // ── T7: Forget scope snapshot (new conversation, workflow closed) ─────
  if (obligations.forgetScope) {
    forgetScopeSnapshot(obligations.forgetScope);
  }
  if (obligations.queueGuardClear) {
    setQueueGuardContext(null);
  }
  // ── T9: Scoped queue guard clear — saves the departing scope's guard
  // context before clearing, so scope B's guard survives new-conversation
  // or scope switch starting from scope A.
  if (obligations.queueGuardClearScope) {
    const scopeId = typeof obligations.queueGuardClearScope === "string"
      ? obligations.queueGuardClearScope
      : null;
    if (scopeId) {
      const runtime = getAgentPanelRuntime();
      if (runtime) {
        saveScopeQueueGuardContext(scopeId, runtime.queueGuardContext);
      }
    }
    setQueueGuardContext(null);
  }
  if (obligations.setQueueGuardContext) {
    setQueueGuardContext(obligations.setQueueGuardContext);
  }
  if (obligations.refreshQueueGuard) {
    panel.state.queueGuard = getQueueGuardStateForPanel();
  }
  if (obligations.toast) {
    toast(obligations.toast);
  }
  if (obligations.nodePackInstallRequest) {
    fulfillNodePackInstallRequest(panel, obligations, {
      fetch,
      transition,
      fulfillLifecycleTransitionObligations,
      renderLifecycleTransition,
    });
  }
  // ── T7: Clear undo affordances on scope switch ────────────────────────
  // The undo stack is canvas-affine (SD3).  After switching scopes, the
  // visible panel must not show undo affordances for undo entries that
  // belong to a different workflow's canvas.  We reset the composer button
  // state so the undo button loses emphasis and the menu entry is hidden.
  if (obligations.clearUndoAffordance) {
    if (panel.buttons && panel.buttons.undo) {
      // Reset undo button emphasis — the undo stack entries belong to
      // a different canvas context.
      if (typeof panel.buttons.undo.style === "object") {
        panel.buttons.undo.style.opacity = "0.5";
        panel.buttons.undo.style.pointerEvents = "auto";
      }
    }
    // Re-sync composer buttons so apply/undo/reject affordances reflect
    // the post-switch state (no candidate, no apply allowed).
    syncComposerButtons(panel);
  }
}

function renderLifecycleTransition(panel, obligations = {}) {
  // ── T7: Restore draft prompt text for the arriving scope ──────────────
  // The scope switch transition provides restoreScopeDraft so we can
  // write the saved prompt text back into the DOM prompt element.
  if (obligations.restoreScopeDraft) {
    const draftText = getScopeDraft(obligations.restoreScopeDraft);
    if (draftText != null) {
      const promptEl = getPanelElementById(panel, PANEL_IDS.prompt) || panel?.fields?.prompt;
      if (promptEl && typeof promptEl.value === "string") {
        promptEl.value = draftText;
        try {
          if (typeof promptEl.dispatchEvent === "function" && typeof Event === "function") {
            promptEl.dispatchEvent(new Event("input", { bubbles: true }));
          }
        } catch (_e) { /* best-effort */ }
      }
    }
    // ── T9: Restore arriving scope's queue guard context ────────────────
    // Saved by fulfillLifecycleTransitionObligations on departure.
    const restoredGuard = getScopeQueueGuardContext(obligations.restoreScopeDraft);
    if (restoredGuard) {
      setQueueGuardContext(restoredGuard);
    }
  }

  if (obligations.render) {
    renderDirtyAgentPanelSections(panel, obligations);
  }
  if (obligations.focusPrompt) {
    const promptEl = getPanelElementById(panel, PANEL_IDS.prompt) || panel?.fields?.prompt;
    if (promptEl && typeof promptEl.focus === "function") {
      panel.fields.prompt = promptEl;
      promptEl.focus();
    }
  }
  if (obligations.rehydrateChat) {
    _rehydrateChat(panel)
      .then(() => { scheduleRenderAgentPanel("rehydrate", panel); })
      .catch((err) => { console.warn("[vibecomfy] chat rehydration render failed", err); });
  }
}

function handleRequiresCustomNodesSubmitResponse(panel, context = {}) {
  const {
    submitEpoch,
    result,
    outcome,
    task,
    resultSessionId,
    resultTurnId,
    resultBaselineTurnId,
  } = context;
	  const customNodeMessage =
	    (typeof result.message === "string" && result.message.trim())
	      ? result.message.trim()
	      : (typeof result.reply === "string" && result.reply.trim())
	        ? result.reply.trim()
	        : "VibeComfy could not confirm automatic installation for this edit.";
  const customNodeResolution = readCustomNodeResolution(result, { endpoint: "submit:custom-nodes" });
  const obligations = commitTerminalResponse(panel, {
    submitEpoch,
    result,
    outcome,
    auditRef: result.auditRef || null,
    message: customNodeMessage,
    customNodeResolution,
    debugPayload: {
      ...(result.raw || result),
      customNodeResolution,
      last_submit: panel.state.lastSubmit,
    },
  });
  fulfillLifecycleTransitionObligations(panel, obligations);
  promotePendingResponseMessage(panel, result, { message: customNodeMessage });
  clearPendingResponseMessages(panel);
  reconcileResponseBatchTurns(panel, result.raw || result);
  pushHistory(panel, "requires_custom_nodes", customNodeMessage);
  pushTurnStatus(panel, "requires_custom_nodes", {
    session_id: resultSessionId,
    turn_id: resultTurnId,
    baseline_turn_id: resultBaselineTurnId,
    task,
    message: customNodeMessage,
    graph_unchanged: true,
    audit_ref: result.auditRef,
    raw_payload: result.raw || result,
  });
  rememberTurnDetailSnapshot(panel, {
    turn_id: resultTurnId,
    session_id: resultSessionId,
    outcome,
    customNodeResolution,
    message: customNodeMessage,
  });
  renderLifecycleTransition(panel, obligations);
}

// ── Paid-submit confirmation gate ─────────────────────────────────────────
// The first agent-executor submit in a browser calls a real provider and
// costs money (API/CLI quota). Ask once, persist the ack in localStorage, and
// ALWAYS confirm the exact welcome-example prompts — clicking an example is a
// demo, not a deliberate paid submission. Cancel = do not submit.
const PAID_SUBMIT_ACK_KEY = "vibecomfy_paid_submit_ack";

async function confirmPaidSubmitGate(panel, task) {
  const isExamplePrompt = WELCOME_EXAMPLE_PROMPTS.includes(task);
  if (!isExamplePrompt) {
    try {
      if (_lsGet(PAID_SUBMIT_ACK_KEY) === "1") {
        return true;
      }
    } catch (_error) {
      // Storage unavailable: still ask so the cost is never hidden.
    }
  }
  const route = normalizeRoutePreference(
    panel?.state?.routeStatus?.requestedRoute || panel?.fields?.route?.value,
  );
  const model = (panel?.fields?.model?.value && String(panel.fields.model.value).trim())
    || panel?.state?.routeStatus?.model
    || "default";
  const routeLabel = ROUTE_LABELS[route] || route;
  let confirmed = true;
  try {
    if (typeof globalThis.confirm === "function") {
      confirmed = globalThis.confirm(
        `Submit this edit through ${routeLabel} (model: ${model})? This calls the provider and costs money.`,
      );
    }
  } catch (_error) {
    // Non-interactive contexts (tests/harnesses) proceed without blocking.
  }
  if (confirmed && !isExamplePrompt) {
    try {
      _lsSet(PAID_SUBMIT_ACK_KEY, "1");
    } catch (_error) {
      // Best-effort persistence only.
    }
  }
  return confirmed;
}

async function submitAgentEdit(panel, { taskOverride } = {}) {
  // A staged demo leaves panel.state.__demoMode set, which routes Apply/Reject
  // to the demo handlers and would mask this real edit with the demo's result.
  // Tear down any active demo first so the picker can never interfere with a
  // real generation. No-op (and safe) when no demo is active.
  panel?.previewPicker?.clearActiveDemo?.(panel);
  if (panel?.state?.rebaselinePending || panel?.state?.inFlightRebaseline) {
    renderAgentPanel(panel);
    return panel.state.inFlightRebaseline || undefined;
  }
  if (panel.state.inFlightSubmit) {
    const staleSubmitEpoch = panel.state.submitEpoch;
    const submitStartedAtMs = Number(panel?.state?.submitStartedAtMs);
    const submitDeadlineMs = submitFlow.currentSubmitDeadlineMs(panel);
    const nowMs = submitFlow.currentSubmitNowMs();
    const activity = submitActivityByPanel.get(panel);
    const submitAgeMs = nowMs - submitStartedAtMs;
    const submitInactivityMs = nowMs - (activity?.lastActivityAtMs ?? submitStartedAtMs);
    const submitAbsoluteDeadlineMs = submitFlow.currentSubmitAbsoluteDeadlineMs();
    if (
      Number.isFinite(submitStartedAtMs)
      && Number.isFinite(submitDeadlineMs)
      && submitDeadlineMs > 0
      && (submitInactivityMs >= submitDeadlineMs || submitAgeMs >= submitAbsoluteDeadlineMs)
    ) {
      const staleAbortController = panel.state.submitAbortController;
      const recoveryObligations = transition(panel, "SUBMIT_STALE_IN_FLIGHT_RECOVERY", {
        submitEpoch: staleSubmitEpoch,
        debugPayload: {
          stale_in_flight_submit: true,
          submit_age_ms: submitAgeMs,
          submit_inactivity_ms: submitInactivityMs,
          submit_deadline_ms: submitDeadlineMs,
          submit_absolute_deadline_ms: submitAbsoluteDeadlineMs,
          ...(panel?.state?.lastSubmit && typeof panel.state.lastSubmit === "object"
            ? { last_submit: clonePlainData(panel.state.lastSubmit) }
            : {}),
        },
      });
      fulfillLifecycleTransitionObligations(panel, recoveryObligations);
      try {
        staleAbortController?.abort();
      } catch (_error) {
        // Best-effort stale cleanup only.
      }
    } else {
      return panel.state.inFlightSubmit;
    }
  }
  let submitPromise = null;
  let submitEpoch = null;
  let submitAbortController = null;
  const submitRunPromise = (async () => {
    let submitHttpStatus = null;
    let submitDeadlineMs = submitFlow.currentSubmitDeadlineMs(panel);
    const submitAbsoluteDeadlineMs = submitFlow.currentSubmitAbsoluteDeadlineMs();
    const submitScopeActivationEpoch = Number.isFinite(panel?.state?.scopeActivationEpoch)
      ? panel.state.scopeActivationEpoch
      : 0;
    const isCurrentSubmit = () => (
      panel?.state?.submitEpoch === submitEpoch
      && panel?.state?.scopeActivationEpoch === submitScopeActivationEpoch
    );
    // Re-resolve the prompt element from the live DOM at submit time: a durable
    // panel re-render can replace the textarea, leaving panel.fields.prompt as a
    // stale, detached reference whose .value reads empty — a false "MissingTask".
    const promptEl = getPanelElementById(panel, PANEL_IDS.prompt) || panel.fields.prompt;
    if (promptEl && promptEl !== panel.fields.prompt) {
      panel.fields.prompt = promptEl;
    }
    const readinessState = submitReadinessState(panel);
    if (!readinessState.ready) {
      const obligations = transition(panel, "SUBMIT_READINESS_FAILURE", {
        debugPayload: {
          failure: null,
          readiness: readinessState,
          route_status: clonePlainData(panel.state.routeStatus),
          status_snapshot: clonePlainData(panel.state.statusSnapshot),
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      restoreLayoutPreviewBaseline(panel);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    // ── T11: Active-canvas scope guard before submit ────────────────────
    // Compare the panel's tracked chat scope against the live canvas scope.
    // If the canvas changed (user loaded a different workflow), auto-switch
    // the panel scope AFTER preserving the old scope's drafts.  If the
    // mismatch is unresolvable (e.g., tab divergence), block the submit.
    const scopeAssertion = assertPanelScopeMatchesActiveCanvas(panel, { caller: "submit" });
    if (!scopeAssertion.ok) {
      const currentChatScopeId = panel.state.chatScopeId;
      const currentDraft = submitFlow.capturePromptDraft(panel);

      // ── Preserve old scope's drafts before any mutation ─────────────
      if (currentChatScopeId) {
        if (currentDraft != null) {
          saveScopeDraft(currentChatScopeId, currentDraft);
        }
        // Also save a full scope snapshot so chat/turn/history survive.
        saveScopeSnapshot(currentChatScopeId, panel);
      }

      // ── Determine if auto-switch is safe ────────────────────────────
      const canAutoSwitch =
        scopeAssertion.reason === "panel_has_no_scope" ||
        scopeAssertion.reason === "graph_diverged" ||
        scopeAssertion.reason === "canvas_is_empty";

      if (canAutoSwitch) {
        // Emit scope switch transition to update chatScopeId/chatScopeFingerprint.
        const newCanvasScope = resolveActiveCanvasScope();
        const scopeSwitchObligations = transition(panel, "SCOPE_SWITCH", {
          scopeId: newCanvasScope?.scopeId || null,
          fingerprint: newCanvasScope?.fingerprint || null,
          debugPayload: {
            reason: `submit_auto_switch:${scopeAssertion.reason}`,
            previousScopeId: currentChatScopeId,
            newScopeId: newCanvasScope?.scopeId || null,
            scopeAssertion,
          },
        });
        fulfillLifecycleTransitionObligations(panel, scopeSwitchObligations);

        // Restore the arriving scope's prompt draft if one exists.
        const arrivingScopeId = newCanvasScope?.scopeId;
        if (arrivingScopeId && promptEl && typeof promptEl.value === "string") {
          const arrivingDraft = getScopeDraft(arrivingScopeId);
          if (arrivingDraft != null && typeof arrivingDraft === "string") {
            promptEl.value = arrivingDraft;
            try {
              if (typeof promptEl.dispatchEvent === "function" && typeof Event === "function") {
                promptEl.dispatchEvent(new Event("input", { bubbles: true }));
              }
            } catch (_e) { /* no-op */ }
          }
        }
      } else {
        // Unsafe mismatch (e.g., tab divergence, empty panel with scoped canvas).
        // Block the submit with debug metadata.
        const failure = agentPanelFailure("ScopeMismatch", "The active canvas scope does not match the panel scope. Submit is blocked.", {
          retryable: false,
          graph_unchanged: true,
          next_action: "Reload the page or create a new conversation from the current canvas.",
          scope_mismatch_reason: scopeAssertion.reason,
          panel_scope_id: scopeAssertion.panelScopeId,
          canvas_scope_id: scopeAssertion.canvasScopeId,
          scope_debug: scopeAssertion.debug,
        });
        const obligations = transition(panel, "SUBMIT_SCOPE_MISMATCH", {
          failure,
          debugPayload: {
            ...failure,
            scopeAssertion,
          },
        });
        fulfillLifecycleTransitionObligations(panel, obligations);
        renderLifecycleTransition(panel, obligations);
        return;
      }
    }

    const explicitTask = typeof taskOverride === "string" ? taskOverride.trim() : "";
    const task = explicitTask || (promptEl && typeof promptEl.value === "string" ? promptEl.value : "").trim();
    if (!task) {
      const failure = agentPanelFailure("MissingTask", "Enter an edit instruction before submitting.", {
        retryable: true,
        next_action: "Describe the workflow change in the prompt region, then submit again.",
      });
      const obligations = transition(panel, "SUBMIT_MISSING_TASK", {
        failure,
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
        debugPayload: failure,
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    // Paid-submit confirmation gate: ask once per browser, and always for the
    // exact welcome-example prompts. Nothing has been mutated yet, so a cancel
    // simply aborts the submit and leaves the draft prompt in place.
    if (!(await confirmPaidSubmitGate(panel, task))) {
      return;
    }

    // Clear the prompt box immediately on submit — the task is already captured
    // in `task`, and the rebaseline retry resubmits from lastSubmit.task, not here.
    if (promptEl && typeof promptEl.value === "string") {
      promptEl.value = "";
      try {
        if (typeof promptEl.dispatchEvent === "function" && typeof Event === "function") {
          promptEl.dispatchEvent(new Event("input", { bubbles: true }));
        }
      } catch (_e) { /* no-op: input event is best-effort */ }
    }

    const pendingMessage = `Submitting: ${task.slice(0, 80)}${task.length > 80 ? "..." : ""}`;
    // The user just sent a message — always jump the thread to the newest
    // content regardless of where they had scrolled.
    ensureThreadRenderState(panel).forceScrollOnNextRender = true;
    const startObligations = commitOptimisticSubmit(panel, {
      lastSubmit: null,
      debugPayload: {
        task,
      },
    });
    submitEpoch = startObligations.submitEpoch;

    // ── Pin the user's message before ANY await ─────────────────────────
    // The scope-switch rehydrate (SCOPE_SWITCH → rehydrateChat → recover
    // fetch) can resolve mid-submit and CHAT_REHYDRATE_NO_SESSION used to
    // wipe chatMessages — deleting the optimistic bubble the submit had just
    // painted ("my sent message disappears").  Paint the user line + pending
    // agent bubble HERE, before buildSubmitSnapshot yields, so the thread
    // shows the message the instant Submit is hit.  The submit_epoch field
    // (not the idempotency key) is what reconciliation uses to preserve
    // in-flight optimistic entries, so a pre-snapshot placeholder key is safe.
    if (!Array.isArray(panel.state.chatMessages)) {
      panel.state.chatMessages = [];
    }
    clearPendingResponseMessages(panel);
    panel.state.chatMessages.push(mutableTranscriptMessage({
      role: "user",
      text: task,
      optimistic: true,
      local_id: `submit-user:${submitEpoch}`,
      submit_epoch: submitEpoch,
      timestamp: new Date().toISOString(),
    }));
    const pendingProgress = createExecutorProgressSnapshot({ decide: "active" });
    panel.state.executorProgress = pendingProgress;
    panel.state.chatMessages.push(
      makePendingResponseChatMessage(panel, task, pendingProgress, submitEpoch),
    );
    panel.state.transcriptMessages = panel.state.chatMessages
      .map(mutableTranscriptMessage)
      .filter(Boolean);
    ensureThreadRenderState(panel).forceScrollOnNextRender = true;
    markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);

    let snapshot;
    try {
      snapshot = await buildSubmitSnapshot(panel);
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
    } catch (e) {
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
      const failure = agentPanelFailure("SerializeError", String(e), {
        retryable: true,
        next_action: "Make sure the canvas can serialize, then retry.",
      });
      const obligations = transition(panel, "SUBMIT_SERIALIZE_ERROR", {
        submitEpoch,
        failure,
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
        debugPayload: failure,
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    submitDeadlineMs = submitFlow.currentSubmitDeadlineMs(panel);
    const submitStartObligations = transition(panel, "SUBMIT_START", {
      submitEpoch,
      lastSubmit: {
        task,
        route: snapshot.route,
        pipeline_mode: snapshot.pipelineMode,
        model: snapshot.model,
        client_graph_hash: snapshot.graphHash,
        client_structural_graph_hash: snapshot.structuralHash,
        client_live_canvas_token: snapshot.liveCanvasToken,
        idempotency_key: snapshot.idempotencyKey,
      },
      debugPayload: {
        task,
        route: snapshot.route,
        pipeline_mode: snapshot.pipelineMode,
        model: snapshot.model,
        client_graph_hash: snapshot.graphHash,
        client_structural_graph_hash: snapshot.structuralHash,
        client_live_canvas_token: snapshot.liveCanvasToken,
        idempotency_key: snapshot.idempotencyKey,
      },
      submitStartedAtMs: submitFlow.currentSubmitNowMs(),
      submitDeadlineMs,
    });
    fulfillLifecycleTransitionObligations(panel, submitStartObligations);
    // Preserve the epoch allocated before serialization; SUBMIT_START above
    // returns the current epoch when payload.submitEpoch is supplied.
    submitEpoch = panel.state.submitEpoch;
    submitFlow.beginSubmitActivity(panel, submitEpoch);
    // The optimistic user bubble + pending agent message were already pinned
    // BEFORE buildSubmitSnapshot (see above) so the user's line is visible the
    // instant they hit Submit and cannot be raced by a rehydrate wipe.
    pushHistory(panel, "pending", pendingMessage);
    pushTurnStatus(panel, "pending", {
      task,
      message: pendingMessage,
    });
    renderLifecycleTransition(panel, submitStartObligations);

    let result;
    const automaticRetryCount = submitFlow.currentSubmitAutomaticRetryCount();
    const retryContext = {
      sessionId: panel.state.sessionId || null,
      turnId: panel.state.turnId || null,
    };
    try {
      for (let attemptIndex = 0; attemptIndex <= automaticRetryCount; attemptIndex += 1) {
        submitAbortController = new AbortController();
        submitHttpStatus = null;
        transition(panel, "SUBMIT_ABORT_CONTROLLER", {
          submitEpoch,
          controller: submitAbortController,
        });
        const failureContextForAttempt = (extras = {}) => submitFlow.buildSubmitFailureContext(panel, snapshot, {
          sessionId: retryContext.sessionId,
          turnId: retryContext.turnId,
          ...extras,
        });
        try {
          const body = submitFlow.buildSubmitBody(snapshot, task, panel, {
            sessionIdOverride: retryContext.sessionId,
          });
          const res = await submitFlow.runSubmitFetchWithDeadline(
            fetch("/vibecomfy/agent-executor", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
              signal: submitAbortController.signal,
            }),
            {
              panel,
              snapshot,
              submitAbortController,
              submitEpoch,
              deadlineMs: submitDeadlineMs,
              absoluteDeadlineMs: submitAbsoluteDeadlineMs,
            },
          );
          submitHttpStatus = Number.isFinite(res?.status) ? Number(res.status) : null;
          if (!isCurrentSubmit()) {
            transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
            return;
          }
          const rawResult = await res.json();
          try {
            result = normalizeAgentEditResponse(rawResult, { endpoint: "submit", allowLegacy: true });
          } catch (error) {
            if (res.ok) {
              throw agentPanelFailure("MalformedResponse", "The backend returned an incomplete candidate envelope.", {
                stage: rawResult?.stage || "agent-executor",
                retryable: true,
                graph_unchanged: true,
                next_action: "Retry the request or inspect the raw response in the debug panel.",
                raw_response: rawResult,
                cause: String(error),
                ...failureContextForAttempt({
                  httpStatus: submitHttpStatus,
                  timeoutMs: submitDeadlineMs,
                }),
              });
            }
            throw error;
          }
          if (!isCurrentSubmit()) {
            transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
            return;
          }
          const submitIdentity = readRoundtripTurnIdentity(result, { endpoint: "submit:identity" });
          if (typeof submitIdentity?.sessionId === "string" && submitIdentity.sessionId) {
            retryContext.sessionId = submitIdentity.sessionId;
            // Persisting the value remains a side effect, but sessionId itself is
            // committed through the terminal submit transition below.
            _persistActiveSession(submitIdentity.sessionId, panel?.state?.chatScopeId || null);
          }
          if (typeof submitIdentity?.turnId === "string" && submitIdentity.turnId) {
            retryContext.turnId = submitIdentity.turnId;
          }
          commitSessionArtifactPathsFromResponse(panel, result);
          if (!res.ok || result?.ok === false || result.raw?.error) {
            const backendFailure = result.raw && typeof result.raw === "object"
              ? submitFlow.markBackendSubmitFailure(
                  submitFlow.mergeSubmitFailureContext(
                    result.raw,
                    failureContextForAttempt({
                      httpStatus: submitHttpStatus,
                      timeoutMs: submitDeadlineMs,
                    }),
                  ),
                )
              : submitFlow.markBackendSubmitFailure(
                  submitFlow.mergeSubmitFailureContext(
                    {
                      kind: "RequestError",
                      message: res.statusText,
                    },
                    failureContextForAttempt({
                      httpStatus: submitHttpStatus,
                      timeoutMs: submitDeadlineMs,
                    }),
                  ),
                );
            throw backendFailure;
          }
          const outcome = result.outcome;
          const submitCandidate = readRoundtripApplyCandidate(result, { endpoint: "submit:candidate" });
          const candidateGraph = prepareCandidateGraphForPanel(submitCandidate?.graph || null);
          if (!submitFlow.isSubmitResponseValid(outcome, candidateGraph)) {
            throw agentPanelFailure("MalformedResponse", "The backend returned an incomplete candidate envelope.", {
              stage: result.raw?.stage || "agent-executor",
              retryable: true,
              graph_unchanged: true,
              next_action: "Retry the request or inspect the raw response in the debug panel.",
              raw_response: result.raw,
              ...failureContextForAttempt({
                httpStatus: submitHttpStatus,
                timeoutMs: submitDeadlineMs,
              }),
            });
          }
          break;
        } catch (error) {
          if (!isCurrentSubmit()) {
            transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
            return;
          }
          const failure = submitFlow.normalizeSubmitFailure(
            error,
            failureContextForAttempt({
              httpStatus: submitHttpStatus,
              timeoutMs: submitDeadlineMs,
            }),
          );
          if (typeof failure?.session_id === "string" && failure.session_id) {
            retryContext.sessionId = failure.session_id;
          }
          if (typeof failure?.turn_id === "string" && failure.turn_id) {
            retryContext.turnId = failure.turn_id;
          }
          if (submitFlow.shouldAutoRetrySubmitFailure(error, failure, { attemptIndex, maxAutomaticRetryCount: automaticRetryCount })) {
            continue;
          }
          throw failure;
        }
      }
    } catch (e) {
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
      // Submit failed/cancelled: restore the instruction we cleared on submit so
      // the user can retry without retyping it.
      if (promptEl && typeof promptEl.value === "string" && !promptEl.value) {
        promptEl.value = task;
        try {
          if (typeof promptEl.dispatchEvent === "function" && typeof Event === "function") {
            promptEl.dispatchEvent(new Event("input", { bubbles: true }));
          }
        } catch (_e) { /* no-op */ }
      }
      if (e?.name === "AbortError") {
        clearPendingResponseMessages(panel);
        const obligations = transition(panel, "SUBMIT_ABORT", {
          submitEpoch,
          message: "Request cancelled.",
          syntheticAgentMessage: {
            role: "agent",
            text: "Request cancelled.",
            session_id: panel.state.sessionId || null,
            synthetic: true,
            local_id: `cancelled:${Date.now()}`,
          },
          debugPayload: {
            cancelled: true,
            last_submit: panel.state.lastSubmit,
          },
        });
        fulfillLifecycleTransitionObligations(panel, obligations);
        pushHistory(panel, "cancelled", task);
        pushTurnStatus(panel, "cancelled", {
          session_id: panel.state.sessionId,
          task,
          message: "Request cancelled.",
        });
        renderLifecycleTransition(panel, obligations);
        return;
      }
      const failure = submitFlow.normalizeSubmitFailure(
        e,
        submitFlow.buildSubmitFailureContext(panel, snapshot, {
          httpStatus: submitHttpStatus,
          timeoutMs: submitDeadlineMs,
        }),
      );
      clearPendingResponseMessages(panel);
      const obligations = commitTerminalResponse(panel, {
        submitEpoch,
        failure,
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      pushHistory(panel, "failure", failure.kind || "NetworkError");
      pushTurnStatus(panel, "failed", {
        session_id: failure.session_id,
        turn_id: failure.turn_id,
        baseline_turn_id: failure.baseline_turn_id,
        task,
        failure_kind: failure.kind,
        failure_stage: failure.stage,
        message: failure.user_facing_message || failure.message || failure.error,
        audit_ref: failure.audit_ref,
        raw_payload: failure,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: failure.turn_id,
        session_id: failure.session_id,
        failure,
        message: failure.user_facing_message || failure.message || failure.error,
      });
      renderLifecycleTransition(panel, obligations);
      return;
    }

    // Clarify terminal: the agent ended the turn with `clarify("...")` instead of
    // landing edits. The canonical outcome can arrive without any candidate graph,
    // so branch out BEFORE the candidate path and never enter AWAITING_REVIEW for
    // clarify-only turns. Otherwise we'd render an "Apply Candidate" button over a
    // no-op/unchanged graph. Instead surface the question and leave the prompt open
    // so the user can answer in the same session.
    const outcome = result.outcome;
    const turnIdentity = readRoundtripTurnIdentity(result, { endpoint: "submit:identity" });
    const applyCandidate = readRoundtripApplyCandidate(result, { endpoint: "submit:candidate" });
    const candidateGraph = prepareCandidateGraphForPanel(applyCandidate?.graph || null);
    const eligibility = applyCandidate?.eligibility || null;
    const resultSessionId = turnIdentity?.sessionId || null;
    const resultTurnId = turnIdentity?.turnId || null;
    const resultBaselineTurnId = turnIdentity?.baselineTurnId || null;
    if (outcomeRequiresClarification(outcome) && !candidateGraph) {
      const fallbackMessage =
        (typeof result.message === "string" && result.message.trim())
          ? result.message.trim()
          : null;
      const clarifyMessage =
        clarificationMessageFromOutcome(outcome, fallbackMessage)
          || fallbackMessage
          || "The agent needs clarification before it can edit the graph.";
      const clarification = {
        message: clarifyMessage,
        turn_id: resultTurnId,
        session_id: resultSessionId,
      };
      const obligations = commitTerminalResponse(panel, {
        submitEpoch,
        result,
        outcome,
        candidateGraph: null,
        auditRef: result.auditRef || null,
        clarification,
        message: clarifyMessage,
        lastSubmitFieldChanges: normalizeFieldChangesFromSubmit(result.raw || result),
        debugPayload: {
          ...(result.raw || result),
          last_submit: panel.state.lastSubmit,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      promotePendingResponseMessage(panel, result, { message: clarifyMessage });
      clearPendingResponseMessages(panel);
      reconcileResponseBatchTurns(panel, result.raw || result);
      pushHistory(panel, "clarify", clarifyMessage);
      pushTurnStatus(panel, "clarify", {
        session_id: resultSessionId,
        turn_id: resultTurnId,
        baseline_turn_id: resultBaselineTurnId,
        task,
        message: clarifyMessage,
        clarification_required: true,
        clarification_message: clarifyMessage,
        audit_ref: result.auditRef,
        raw_payload: result.raw || result,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: resultTurnId,
        session_id: resultSessionId,
        clarification: panel.state.clarification,
        message: clarifyMessage,
      });
      renderLifecycleTransition(panel, obligations);
      return;
    }

    if (outcomeRequiresCustomNodes(outcome)) {
      handleRequiresCustomNodesSubmitResponse(panel, {
        submitEpoch,
        result,
        outcome,
        task,
        resultSessionId,
        resultTurnId,
        resultBaselineTurnId,
      });
      return;
    }

    if (outcomeIsNoop(outcome)) {
      const noopMessage =
        (typeof result.message === "string" && result.message.trim())
          ? result.message.trim()
          : (typeof outcome.reason === "string" && outcome.reason.trim())
            ? outcome.reason.trim()
            : "No change needed.";
      const lastSubmitFieldChanges = normalizeFieldChangesFromSubmit(result.raw || result);
      const changeDetails = result.raw?.change_details && typeof result.raw.change_details === "object"
        ? clonePlainData(result.raw.change_details)
        : null;
      const obligations = commitTerminalResponse(panel, {
        submitEpoch,
        result,
        outcome,
        candidateGraph: null,
        auditRef: result.auditRef || null,
        message: noopMessage,
        lastSubmitFieldChanges,
        changeDetails,
        debugPayload: {
          ...(result.raw || result),
          last_submit: panel.state.lastSubmit,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      promotePendingResponseMessage(panel, result, { message: noopMessage });
      clearPendingResponseMessages(panel);
      reconcileResponseBatchTurns(panel, result.raw || result);
      pushHistory(panel, "noop", noopMessage);
      pushTurnStatus(panel, "noop", {
        session_id: resultSessionId,
        turn_id: resultTurnId,
        baseline_turn_id: resultBaselineTurnId,
        task,
        message: noopMessage,
        graph_unchanged: true,
        audit_ref: result.auditRef,
        raw_payload: result.raw || result,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: resultTurnId,
        session_id: resultSessionId,
        outcome,
        message: noopMessage,
        changeDetails,
      });
      renderLifecycleTransition(panel, obligations);
      return;
    }

    let arrivalSnapshot;
    try {
      arrivalSnapshot = await buildCanvasSnapshot();
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
    } catch (e) {
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
      const failure = agentPanelFailure("SerializeError", `Could not serialize the current canvas after the candidate arrived: ${String(e)}`, {
        retryable: true,
        graph_unchanged: true,
        next_action: "Make sure the current canvas can serialize, then submit again.",
      });
      const obligations = transition(panel, "ARRIVAL_SERIALIZE_FAILURE", {
        submitEpoch,
        result: result.raw || result,
        failure,
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
        debugPayload: {
          ...failure,
          last_submit: panel.state.lastSubmit,
          response: result.raw || result,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      clearPendingResponseMessages(panel);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    const expectedArrivalStructuralHash = panel.state.lastSubmit?.client_structural_graph_hash;
    const structuralChangedForDiagnostics =
      typeof expectedArrivalStructuralHash === "string"
      && expectedArrivalStructuralHash
      && arrivalSnapshot.structuralHash !== expectedArrivalStructuralHash;

    const candidateGraphHash =
      applyCandidate?.candidateGraphHash
      || applyCandidate?.graphHash
      || await sha256HexUtf8(canonicalJsonString(candidateGraph));
    if (!isCurrentSubmit()) {
      transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
      return;
    }
    const normalizedEligibility = applyFlow.normalizeCandidateApplyEligibility(candidateGraph, eligibility);
    const runtimeDependencies = Array.isArray(result.runtimeDependencies)
      ? clonePlainData(result.runtimeDependencies)
      : [];
    const registryPlaceholderTypes = new Set(
      runtimeDependencies
        .filter((entry) => entry?.availability === "registry_resolvable")
        .map((entry) => entry.class_type)
        .filter((classType) => typeof classType === "string" && classType),
    );
    const candidateNeedsRegistryPlaceholder = Array.isArray(candidateGraph?.nodes)
      && candidateGraph.nodes.some((node) => registryPlaceholderTypes.has(node?.type));
    const changeDetails = result.raw?.change_details && typeof result.raw.change_details === "object"
      ? clonePlainData(result.raw.change_details)
      : null;
    const lastSubmitFieldChanges = normalizeFieldChangesFromSubmit(result.raw || result);
    const candidateDebugPayload = scrubDebugPayload({
      ...(result.raw || result),
      last_submit: panel.state.lastSubmit,
      arrival_structural_mismatch: structuralChangedForDiagnostics,
      arrival_client_graph_hash: arrivalSnapshot.graphHash,
      arrival_client_structural_graph_hash: arrivalSnapshot.structuralHash,
    });
    const candidateObligations = commitTerminalResponse(panel,
      {
        submitEpoch,
        result,
        outcome,
        candidateGraph,
        candidateGraphHash,
        serverSubmitGraphHash: applyCandidate?.submitGraphHash || null,
        // A registry-backed placeholder is reviewable and applyable, but not
        // executable.  A reload after installing the pack rehydrates real
        // LiteGraph classes from /object_info and removes this local block.
        queueAllowed: Boolean(result.queueAllowed) && !candidateNeedsRegistryPlaceholder,
        runtimeDependencies,
        auditRef: result.auditRef || null,
        clarification: outcomeHasClarificationPrompt(outcome)
          ? {
              message: clarificationMessageFromOutcome(outcome, result.message || null),
              turn_id: resultTurnId,
              session_id: resultSessionId,
            }
          : null,
        applyEligibility: normalizedEligibility,
        lastSubmitFieldChanges,
        changeDetails,
        debugPayload: candidateDebugPayload,
      },
    );
    fulfillLifecycleTransitionObligations(panel, candidateObligations);
    promotePendingResponseMessage(panel, result);
    clearPendingResponseMessages(panel);
    reconcileResponseBatchTurns(panel, result.raw || result);
    pushHistory(panel, "candidate", resultTurnId ? `turn ${resultTurnId}` : "candidate");
    pushTurnStatus(panel, "candidate", {
      session_id: resultSessionId,
      turn_id: resultTurnId,
      baseline_turn_id: resultBaselineTurnId,
      task,
      message: result.message || (resultTurnId ? `turn ${resultTurnId}` : "candidate"),
      audit_ref: result.auditRef,
      raw_payload: result.raw || result,
    });
    rememberTurnDetailSnapshot(panel, {
      turn_id: resultTurnId,
      session_id: resultSessionId,
      candidateGraphPresent: Boolean(candidateGraph),
      candidateTransaction: panel.state.candidateTransaction,
      candidateReport: result.report || null,
      applyEligibility: normalizedEligibility,
      queueAllowed: Boolean(result.queueAllowed) && !candidateNeedsRegistryPlaceholder,
      canvasApplyAllowed: Boolean(applyCandidate?.applyable === true || normalizedEligibility?.applyable === true),
      auditRef: result.auditRef || null,
      debugPayload: {
        ...scrubDebugPayload(result.raw || result),
        last_submit: panel.state.lastSubmit,
      },
      fieldChanges: panel.state.lastSubmitFieldChanges,
      changeDetails: panel.state.changeDetails,
      message: result.message || null,
    });
    try {
      await activateLayoutPreviewIfNeeded(panel, arrivalSnapshot);
    } catch (error) {
      console.warn("[vibecomfy] layout preview activation failed:", safePreviewLogDetail(error));
    }
    renderLifecycleTransition(panel, candidateObligations);

    if (panel.state.previewEnabled) {
      createIntentGraphAdapter(app).repaint();
      refreshPreviewDomOverlay();
    }
  })();

  // Own the guard for the complete attempt, including response projection,
  // arrival serialization/hash work, terminal commit, and preview activation.
  // Cleanup is reducer-owned and keyed by both epoch and promise identity, so a
  // superseded attempt's finally callback cannot clear a newer submission.
  submitPromise = submitRunPromise.finally(() => {
    transition(panel, "SUBMIT_FINALLY", {
      submitEpoch,
      promise: submitPromise,
      controller: submitAbortController,
    });
  });
  transition(panel, "SUBMIT_IN_FLIGHT", { submitEpoch, promise: submitPromise });
  return panel.state.inFlightSubmit;
}

function stopAgentSubmit(panel) {
  const controller = panel?.state?.submitAbortController;
  if (!controller) {
    renderAgentPanel(panel);
    return false;
  }
  controller.abort();
  const obligations = transition(panel, "STOP_ABORT", {
    message: "Request cancelled.",
    syntheticAgentMessage: {
      role: "agent",
      text: "Request cancelled.",
      session_id: panel.state.sessionId || null,
      synthetic: true,
      local_id: `cancelled:${Date.now()}`,
    },
    debugPayload: {
      cancelled: true,
      last_submit: panel.state.lastSubmit,
    },
  });
  fulfillLifecycleTransitionObligations(panel, obligations);
  const task = panel.state.lastSubmit?.task || "";
  pushHistory(panel, "cancelled", task);
  pushTurnStatus(panel, "cancelled", {
    session_id: panel.state.sessionId,
    task,
    message: "Request cancelled.",
  });
  renderLifecycleTransition(panel, obligations);
  return true;
}

function widgetReferenceNodeFor(uidOrId) {
  const key = String(uidOrId);
  const liveNodes = Array.isArray(app?.graph?._nodes) ? app.graph._nodes : [];
  return liveNodes.find((node) => (
    String(getUid(node) || "") === key
    || String(node?.id ?? "") === key
  )) || null;
}

async function postAgentLifecycleAction(endpoint, body, action) {
  const response = await fetch(`/vibecomfy/agent-edit/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const rawPayload = await response.json();
  const payload = normalizeAuxiliaryAgentPayload(rawPayload, action);
  if (!response.ok || payload?.ok === false || payload.raw?.error) {
    throw payload.raw || payload || { kind: `${action}Error`, message: response.statusText };
  }
  return payload;
}

async function reconcilePreparedTransactionState(panel) {
  return rebaselineUndoFlow.reconcilePreparedTransactionState(panel);
}

async function rollbackPreparedAgentCandidate(panel, snapshot, options = {}) {
  return rebaselineUndoFlow.rollbackPreparedAgentCandidate(panel, snapshot, options);
}

async function rejectAgentCandidate(panel) {
  return rebaselineUndoFlow.rejectAgentCandidate(panel);
}

export async function postAgentRebaseline(panel, options = {}) {
  return rebaselineUndoFlow.postAgentRebaseline(panel, options);
}

async function rebaselineCurrentCanvas(panel) {
  return rebaselineUndoFlow.rebaselineCurrentCanvas(panel);
}

async function undoLastApply(panel) {
  return rebaselineUndoFlow.undoLastApply(panel);
}

// ── T-059: Rebaseline / undo flow behind injected boundaries ─────────────
// Build the dependency object once from roundtrip's live singletons. The
// lifecycle reducer remains the authority for panel state and preview-cache
// clears; this flow only drives those existing transitions and clear seams.
// Keep the native restore seam lexically owned by undoLastApply so the frozen
// native-authority inventory continues to classify the same access owner.
const rebaselineUndoFlow = createRebaselineUndoFlow({
  PANEL_STATE,
  agentPanelFailure,
  app,
  applyGraphDeltaInPlace,
  applyGraphInPlaceWithIntentDecoration: applyFlow.applyGraphInPlaceWithIntentDecoration,
  applyGraphLayoutInPlace,
  boundedBrowserTransactionError,
  buildActionIdempotencyKey,
  buildCanvasSnapshot,
  buildInverseDeltaOps,
  clearLayoutPreviewState,
  clonePlainData,
  commitReconcileReceipts,
  commitRollbackFailure,
  commitRollbackStarted,
  commitRollbackSuccess,
  extractRebaselineRecovery,
  fulfillLifecycleTransitionObligations,
  isLayoutAuthorityTransaction,
  isLegacyUndoCacheEntryV1,
  isV2ApplyCandidate: applyFlow.isV2ApplyCandidate,
  layoutGraphHash,
  normalizeAuxiliaryAgentPayload,
  normalizeCandidateTransaction,
  pendingTransactionSnapshotByPanel,
  postAgentLifecycleAction,
  pushHistory,
  pushTurnStatus,
  recoveryForPanelState,
  rememberTurnDetailSnapshot,
  renderAgentPanel,
  renderLifecycleTransition,
  restoreLayoutPreviewBaseline,
  restoreUndoGraph: loadGraphDataWithoutScopeSwitch,
  submitAgentEdit,
  syntheticFailureAgentMessage,
  transactionAllowsRejectOrFailClosedDiscard,
  transition,
});

async function openRoundtrip() {
  let graph;
  try {
    graph = captureSerializedGraphForAgent();
  } catch (e) {
    return errorModal({ kind: "SerializeError", message: String(e) });
  }
  let result;
  try {
    const res = await fetch("/vibecomfy/roundtrip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ graph }),
    });
    result = await res.json();
    if (!res.ok || result?.error) {
      return errorModal({ kind: result?.kind, message: result?.error || res.statusText });
    }
  } catch (e) {
    return errorModal({ kind: "NetworkError", message: String(e) });
  }
  renderDiffModal({ graph: result.graph, report: result.report });
}

function openAgentEdit() {
  const panel = openAgentPanel({ mode: AGENT_PANEL_MOUNT_MODE.LAUNCHER });
  panel.root.dataset.lastCommand = "agent-edit";
  renderAgentPanel(panel);
}

// Always-visible edge tab so the agent panel is discoverable without hunting
// through the right-click / Extensions menu. Toggles the panel open/closed.
function ensureAgentLauncher() {
  if (document.getElementById("vibecomfy-agent-launcher")) {
    return;
  }
  const btn = document.createElement("button");
  btn.id = "vibecomfy-agent-launcher";
  btn.type = "button";
  btn.title = "Open the VibeComfy agent edit panel";
  const launcherLogo = document.createElement("img");
  launcherLogo.src = VIBECOMFY_LOGO_URL;
  launcherLogo.alt = "";
  Object.assign(launcherLogo.style, { width: "32px", height: "32px", display: "block", flexShrink: "0" });
  btn.appendChild(launcherLogo);
  Object.assign(btn.style, {
    position: "fixed",
    right: "0px",
    top: "45%",
    zIndex: "100000",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "0",
    padding: "8px 6px",
    background: "#1b1d22",
    color: "#f47f18",
    border: "1px solid #f47f18",
    borderRight: "none",
    borderRadius: "8px 0 0 8px",
    cursor: "pointer",
    fontSize: "12px",
    fontWeight: "700",
    letterSpacing: "0.04em",
    boxShadow: "0 2px 12px rgba(0,0,0,0.45)",
  });
  btn.addEventListener("click", () => {
    const panel = ensureAgentPanel();
    if (
      panel.root.dataset.open === "1"
      && panel.state.mountMode === AGENT_PANEL_MOUNT_MODE.LAUNCHER
    ) {
      closeAgentPanel(panel);
    } else {
      openAgentEdit();
    }
  });
  document.body.appendChild(btn);
}

function ensureAgentSidebarTab() {
  const manager = app?.extensionManager;
  if (!manager || typeof manager.registerSidebarTab !== "function") {
    return false;
  }
  const runtime = getAgentPanelRuntime();
  if (runtime.agentSidebarTabRegistered) {
    return true;
  }
  const tab = {
    id: AGENT_SIDEBAR_TAB_ID,
    title: "VibeComfy",
    tooltip: "Open the VibeComfy agent edit panel",
    icon: "pi pi-sparkles",
    type: "custom",
    render: mountAgentSidebarPanel,
    mount: mountAgentSidebarPanel,
  };
  try {
    manager.registerSidebarTab(tab);
    runtime.agentSidebarTabRegistered = true;
    return true;
  } catch (error) {
    try {
      manager.registerSidebarTab(
        AGENT_SIDEBAR_TAB_ID,
        "VibeComfy",
        "pi pi-sparkles",
        mountAgentSidebarPanel,
      );
      runtime.agentSidebarTabRegistered = true;
      return true;
    } catch (fallbackError) {
      console.warn("[vibecomfy] failed to register agent sidebar tab", fallbackError || error);
      return false;
    }
  }
}

// ── DOM helpers ───────────────────────────────────────────────────────────
function el(tag, text) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  return node;
}

function button(label, onClick) {
  const node = el("button", label);
  node.onclick = onClick;
  Object.assign(node.style, {
    margin: "0",
    padding: "7px 10px",
    borderRadius: "6px",
    border: "1px solid #414855",
    background: "#272b33",
    color: "#edf2f7",
    cursor: "pointer",
    fontFamily: "monospace",
    fontSize: "12px",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  });
  return node;
}

/**
 * Attach an immediate hover tooltip to a button.
 *
 * Reads tooltip text from the element's `data-tooltip` attribute (preferred) or
 * `title` attribute (fallback). The browser's native `title` tooltip has a
 * multi-second delay; this helper shows the text instantly on mouseenter/focus
 * and removes it on mouseleave/blur.
 */
function attachInstantTooltip(element) {
  let tooltip = null;

  function tooltipText() {
    return element.getAttribute("data-tooltip")
      || element.getAttribute("title")
      || "";
  }

  function show() {
    const text = tooltipText();
    if (!text) return;
    hide();
    tooltip = el("div", text);
    Object.assign(tooltip.style, {
      position: "fixed",
      zIndex: "100000",
      background: "#171a20",
      color: "#edf2f7",
      border: "1px solid #414855",
      borderRadius: "6px",
      padding: "5px 8px",
      fontSize: "11px",
      fontFamily: "monospace",
      whiteSpace: "nowrap",
      pointerEvents: "none",
      boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
    });
    document.body.appendChild(tooltip);
    const rect = element.getBoundingClientRect();
    const tipRect = tooltip.getBoundingClientRect();
    let top = rect.top - tipRect.height - 6;
    let left = rect.left + rect.width / 2 - tipRect.width / 2;
    left = Math.max(6, Math.min(left, window.innerWidth - tipRect.width - 6));
    top = Math.max(6, top);
    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
  }

  function hide() {
    if (tooltip && tooltip.parentNode) {
      tooltip.parentNode.removeChild(tooltip);
    }
    tooltip = null;
  }

  function refresh() {
    if (tooltip) tooltip.textContent = tooltipText();
  }

  element.addEventListener("mouseenter", show);
  element.addEventListener("mouseleave", hide);
  element.addEventListener("focus", show);
  element.addEventListener("blur", hide);

  element._vibecomfyRefreshTooltip = refresh;
}

function makeUndoIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "16");
  svg.setAttribute("height", "16");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  Object.assign(svg.style, {
    display: "block",
    flex: "0 0 auto",
  });
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  // Simple, open left-pointing arrow. Avoids the tight arc of the old undo
  // icon, which collapsed into a circle at 16x16.
  path.setAttribute("d", "M20 12H4M4 12l5-5M4 12l5 5");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2.5");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);
  return svg;
}

function makeOverlay() {
  const overlay = el("div");
  Object.assign(overlay.style, {
    position: "fixed",
    inset: "0",
    background: "rgba(0,0,0,0.6)",
    zIndex: "10000",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  });
  document.body.appendChild(overlay);
  return overlay;
}

function makeBox(overlay) {
  const box = el("div");
  Object.assign(box.style, {
    background: "#222",
    color: "#eee",
    padding: "16px",
    maxHeight: "80vh",
    overflow: "auto",
    borderRadius: "8px",
    minWidth: "360px",
    fontFamily: "monospace",
  });
  overlay.appendChild(box);
  return box;
}

function openChooseEngineOverlay(panel, { onResolved }) {
  if (!panel?.shell || typeof document === "undefined") {
    return null;
  }
  // Idempotent mount — remove any existing welcome overlay first.
  const existing = getPanelElementById(panel, PANEL_IDS.welcomeOverlay);
  if (existing && typeof existing.remove === "function") {
    existing.remove();
  }

  // Constrain the overlay to the panel area (mirrors the "Having issues?" modal,
  // which appends to panel.shell with position:absolute). panel.shell is a
  // positioned ancestor, so inset:0 anchors to the panel, not the viewport.
  // Deliberately NO click-outside / Escape close — the user must pick an engine.
  const overlay = el("div");
  overlay.id = PANEL_IDS.welcomeOverlay;
  Object.assign(overlay.style, {
    position: "absolute",
    inset: "0",
    zIndex: "10001",
    background: "rgba(0,0,0,0.6)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "16px",
    boxSizing: "border-box",
  });

  const box = el("div");
  Object.assign(box.style, {
    width: "min(460px, 100%)",
    maxHeight: "100%",
    overflow: "auto",
    background: "#222",
    color: "#eee",
    padding: "16px",
    borderRadius: "8px",
    fontFamily: "monospace",
    boxSizing: "border-box",
  });
  overlay.appendChild(box);

  // ── header ──
  const titleRow = el("div");
  Object.assign(titleRow.style, {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginBottom: "2px",
  });
  const titleLogo = el("img");
  titleLogo.src = VIBECOMFY_LOGO_URL;
  titleLogo.alt = "VibeComfy";
  Object.assign(titleLogo.style, { width: "24px", height: "24px", display: "block", flexShrink: "0" });
  titleRow.appendChild(titleLogo);
  const title = el("div", "Choose Your Engine");
  Object.assign(title.style, {
    fontSize: "17px",
    fontWeight: "700",
    color: "#edf2f7",
  });
  titleRow.appendChild(title);
  box.appendChild(titleRow);

  const subtitle = el("div", "Choose who does the thinking. You can change this later.");
  Object.assign(subtitle.style, {
    fontSize: "11px",
    color: "#8d93a1",
    marginBottom: "14px",
  });
  box.appendChild(subtitle);

  // Countdown timer handle so the thank-you screen can never fire twice.
  let countdownTimer = null;
  function clearCountdown() {
    if (countdownTimer != null) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  }

  // Tear down the overlay (and any pending countdown) exactly once.
  function teardownOverlay() {
    clearCountdown();
    if (panel?.state?.chooseEngineRefresh === updateConfirmEnabled) {
      panel.state.chooseEngineRefresh = null;
    }
    if (overlay && typeof overlay.remove === "function") {
      overlay.remove();
    }
  }

  // Commit the chosen route WITHOUT removing the overlay or calling onResolved —
  // the thank-you screen and the final onResolved happen after a short delay.
  function commitRoute(route) {
    setPersistedAgentProvider(route);
    panel.fields.route.value = route;
    pollerPopulateRouteSelect(panel.fields.route, null, { selectedRoute: route }, agentStatusDeps());
    pollerRefreshAgentStatus(panel, { quiet: true }, agentStatusDeps());
  }

  // ── card colors ──
  const claudeColor = "#e6a817";
  const codexColor = "#02d4b3";
  const openrouterColor = "#7e8ba3";

  // Selection state. Each card registers a setSelected() that lights it up and
  // reveals its extra content; selecting one deselects the others.
  let selectedRoute = null;
  const cardRegistry = []; // { route, setSelected(bool) }
  let openrouterKeyInput = null;
  let openrouterErrorNode = null;

  // ── card helper ──
  // makeCard returns { card, body, setSelected }. The card is a single-select
  // radio-like tile; `body` is an (initially hidden) container directly under
  // the description for per-card revealed content.
  function makeCard(label, description, accentColor, route) {
    const card = el("div");
    Object.assign(card.style, {
      border: "1px solid #333a45",
      borderRadius: "8px",
      background: "#1a1d24",
      padding: "12px",
      cursor: "pointer",
      marginBottom: "8px",
      transition: "background 0.15s, border-color 0.15s, box-shadow 0.15s",
    });

    const labelNode = el("div", label);
    Object.assign(labelNode.style, {
      fontWeight: "700",
      fontSize: "13px",
      color: accentColor,
      marginBottom: "4px",
    });
    card.appendChild(labelNode);

    const descNode = el("div", description);
    Object.assign(descNode.style, {
      fontSize: "11px",
      color: "#9da1ac",
      lineHeight: "1.45",
    });
    card.appendChild(descNode);

    // Per-card revealed content lives here (hidden until selected).
    const body = el("div");
    Object.assign(body.style, {
      display: "none",
      marginTop: "10px",
      flexDirection: "column",
      gap: "8px",
    });
    card.appendChild(body);

    function setSelected(isSelected) {
      if (isSelected) {
        card.style.borderColor = accentColor;
        card.style.background = "#242830";
        card.style.boxShadow = `0 0 0 1px ${accentColor}, 0 0 12px -2px ${accentColor}`;
        body.style.display = "flex";
      } else {
        card.style.borderColor = "#333a45";
        card.style.background = "#1a1d24";
        card.style.boxShadow = "none";
        body.style.display = "none";
      }
    }
    setSelected(false);

    card.onmouseenter = function () {
      if (selectedRoute !== route) card.style.background = "#21242b";
    };
    card.onmouseleave = function () {
      if (selectedRoute !== route) card.style.background = "#1a1d24";
    };

    card.onclick = function () { selectRoute(route); };

    return { card, body, setSelected };
  }

  // ── cards (order: Claude, OpenRouter, Codex) ──
  const claudeCard = makeCard(
    "Claude",
    "The sharpest hand. Uses your local Claude CLI.",
    claudeColor,
    "anthropic",
  );
  const openrouterCard = makeCard(
    "OpenRouter",
    "OpenRouter-backed models. Pay as you go — your key, your bill.",
    openrouterColor,
    "openrouter",
  );
  const codexCard = makeCard(
    "Codex",
    "Sanctioned. Uses your local Codex CLI login. This should be okay.",
    codexColor,
    "openai-codex",
  );

  cardRegistry.push({ route: "anthropic", setSelected: claudeCard.setSelected });
  cardRegistry.push({ route: "openrouter", setSelected: openrouterCard.setSelected });
  cardRegistry.push({ route: "openai-codex", setSelected: codexCard.setSelected });

  // ── Claude revealed content: ToS warning (no buttons) ──
  const claudeWarning = el(
    "div",
    "VibeComfy drives your local `claude` CLI in headless mode. Anthropic’s terms don’t explicitly sanction automated CLI use — use at your own risk.",
  );
  Object.assign(claudeWarning.style, {
    fontSize: "11px",
    lineHeight: "1.45",
    color: "#e6c98a",
    padding: "8px",
    borderRadius: "4px",
    border: `1px solid ${claudeColor}`,
    background: "#2a230f",
  });
  claudeCard.body.appendChild(claudeWarning);

  // ── OpenRouter revealed content: key field + "where do I get a key?" + error ──
  openrouterKeyInput = el("input");
  openrouterKeyInput.onclick = function (event) { event.stopPropagation(); };
  openrouterKeyInput.type = "password";
  openrouterKeyInput.placeholder = "Paste your OpenRouter API key...";
  Object.assign(openrouterKeyInput.style, {
    width: "100%",
    boxSizing: "border-box",
    padding: "6px 8px",
    borderRadius: "4px",
    border: "1px solid #414855",
    background: "#0d0f14",
    color: "#edf2f7",
    fontFamily: "monospace",
    fontSize: "12px",
  });
  openrouterKeyInput.oninput = function () { updateConfirmEnabled(); };
  openrouterCard.body.appendChild(openrouterKeyInput);

  const keyLink = el("a", "Where do I get a key?");
  keyLink.onclick = function (event) { event.stopPropagation(); };
  keyLink.href = "https://openrouter.ai/settings/keys";
  keyLink.target = "_blank";
  keyLink.rel = "noopener";
  Object.assign(keyLink.style, {
    fontSize: "11px",
    color: openrouterColor,
    textDecoration: "underline",
    cursor: "pointer",
  });
  openrouterCard.body.appendChild(keyLink);

  const openrouterStoredKeyNode = el("div");
  Object.assign(openrouterStoredKeyNode.style, {
    display: "none",
    fontSize: "11px",
    color: "#b8d9c7",
    padding: "6px 8px",
    borderRadius: "4px",
    background: "#142218",
    border: "1px solid #2f6842",
  });
  openrouterCard.body.appendChild(openrouterStoredKeyNode);

  openrouterErrorNode = el("div");
  Object.assign(openrouterErrorNode.style, {
    display: "none",
    fontSize: "11px",
    color: "#e07070",
    padding: "6px 8px",
    borderRadius: "4px",
    background: "#2a1a1a",
  });
  openrouterCard.body.appendChild(openrouterErrorNode);

  // Vertical order: Claude (top), OpenRouter (middle), Codex (bottom).
  box.appendChild(claudeCard.card);
  box.appendChild(openrouterCard.card);
  box.appendChild(codexCard.card);

  // ── Confirm button (below all cards) ──
  const confirmBtn = button("Confirm Selection", function () {
    onConfirm();
  });
  Object.assign(confirmBtn.style, {
    width: "100%",
    marginTop: "6px",
  });
  box.appendChild(confirmBtn);

  function openrouterKeyOk() {
    return hasStoredOpenRouterCredential(panel) || !!(openrouterKeyInput && openrouterKeyInput.value.trim());
  }

  function confirmEnabled() {
    if (!selectedRoute) return false;
    if (selectedRoute === "openrouter") return openrouterKeyOk();
    return true;
  }

  function updateConfirmEnabled() {
    const storedOpenRouterKey = hasStoredOpenRouterCredential(panel);
    if (openrouterStoredKeyNode) {
      openrouterStoredKeyNode.style.display = storedOpenRouterKey ? "block" : "none";
      openrouterStoredKeyNode.textContent = storedOpenRouterKey
        ? "Saved OpenRouter key present. Paste a new key only if you want to replace it."
        : "";
    }
    if (openrouterKeyInput) {
      openrouterKeyInput.placeholder = storedOpenRouterKey
        ? "Optional replacement OpenRouter API key..."
        : "Paste your OpenRouter API key...";
    }
    const enabled = confirmEnabled();
    confirmBtn.disabled = !enabled;
    if (enabled) {
      Object.assign(confirmBtn.style, {
        opacity: "1",
        cursor: "pointer",
        background: "#2f6f8f",
        borderColor: "#3f93bd",
        color: "#edf2f7",
      });
    } else {
      Object.assign(confirmBtn.style, {
        opacity: "0.5",
        cursor: "not-allowed",
        background: "#272b33",
        borderColor: "#414855",
        color: "#edf2f7",
      });
    }
  }

  function selectRoute(route) {
    selectedRoute = route;
    cardRegistry.forEach(function (entry) {
      entry.setSelected(entry.route === route);
    });
    if (openrouterErrorNode) openrouterErrorNode.style.display = "none";
    updateConfirmEnabled();
  }

  // ── thank-you screen + deferred resolution ──
  function showThankYouAndClose(route) {
    // Replace the box's contents with a centered thank-you screen.
    box.innerHTML = "";
    Object.assign(box.style, {
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      textAlign: "center",
      gap: "10px",
    });

    const heading = el("div", "Thank you for making your choice.");
    Object.assign(heading.style, {
      fontSize: "16px",
      fontWeight: "700",
      color: "#edf2f7",
    });
    box.appendChild(heading);

    const subtext = el("div", "You can change this anytime in Settings.");
    Object.assign(subtext.style, {
      fontSize: "12px",
      color: "#8d93a1",
    });
    box.appendChild(subtext);

    let remaining = 2;
    const countdownLine = el("div", "Closing in " + remaining + "…");
    Object.assign(countdownLine.style, {
      fontSize: "12px",
      color: "#9da1ac",
      marginTop: "4px",
    });
    box.appendChild(countdownLine);

    clearCountdown();
    countdownTimer = setInterval(function () {
      remaining -= 1;
      if (remaining > 0) {
        countdownLine.textContent = "Closing in " + remaining + "…";
      } else {
        clearCountdown();
        teardownOverlay();
        if (typeof onResolved === "function") {
          onResolved(route);
        }
      }
    }, 1000);
  }

  function showResearchContributionChoice(route) {
    box.innerHTML = "";
    Object.assign(box.style, {
      display: "flex",
      flexDirection: "column",
      alignItems: "stretch",
      justifyContent: "center",
      textAlign: "left",
      gap: "12px",
    });

    const heading = el("div", "Contribute agent research?");
    Object.assign(heading.style, {
      fontSize: "16px",
      fontWeight: "700",
      color: "#edf2f7",
    });
    box.appendChild(heading);

    const subtext = el("div", "Let your agent contribute discovered workflow research for future searches.");
    Object.assign(subtext.style, {
      fontSize: "12px",
      lineHeight: "1.45",
      color: "#9da1ac",
    });
    box.appendChild(subtext);

    const statusLine = el("div", "");
    Object.assign(statusLine.style, {
      minHeight: "16px",
      fontSize: "11px",
      color: "#8d93a1",
    });
    box.appendChild(statusLine);

    const buttonRow = el("div");
    Object.assign(buttonRow.style, {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: "8px",
    });

    async function choose(enabled) {
      yesBtn.disabled = true;
      noBtn.disabled = true;
      statusLine.textContent = enabled ? "Starting research contribution…" : "Saving preference…";
      try {
        await saveResearchContributionSetting(panel, enabled, { trigger: enabled });
      } finally {
        showThankYouAndClose(route);
      }
    }

    const yesBtn = button("Yes", () => choose(true));
    const noBtn = button("No", () => choose(false));
    buttonRow.appendChild(yesBtn);
    buttonRow.appendChild(noBtn);
    box.appendChild(buttonRow);
  }

  async function onConfirm() {
    if (!confirmEnabled()) return;
    const route = selectedRoute;

    if (route === "openrouter") {
      const apiKey = openrouterKeyInput.value.trim();
      if (!apiKey && !hasStoredOpenRouterCredential(panel)) return;
      if (apiKey) {
        confirmBtn.disabled = true;
        confirmBtn.textContent = "Storing…";
        Object.assign(confirmBtn.style, { opacity: "0.5", cursor: "not-allowed" });
        openrouterErrorNode.style.display = "none";

        let stored = false;
        try {
          const result = await storeOpenRouterCredential(panel, apiKey);
          stored = Boolean(result?.stored);
          openrouterErrorNode.textContent = result?.message || "Failed to store key.";
          openrouterErrorNode.style.display = stored ? "none" : "block";
        } catch (e) {
          openrouterErrorNode.textContent = "Credential save failed: " + String(e);
          openrouterErrorNode.style.display = "block";
        }

        if (!stored) {
          // Stay on the screen; restore the button.
          confirmBtn.textContent = "Confirm Selection";
          updateConfirmEnabled();
          return;
        }
      }
    }

    commitRoute(route);
    showResearchContributionChoice(route);
  }

  // Initial disabled state.
  panel.state.chooseEngineRefresh = updateConfirmEnabled;
  updateConfirmEnabled();

  panel.shell.appendChild(overlay);
  return overlay;
}


function row(uid, color, label, tooltip) {
  const node = el("div", `${label} ${uid}`);
  node.style.color = color;
  if (tooltip) node.title = tooltip;
  return node;
}

// ── Diff modal (legacy round-trip command) ───────────────────────────────
function renderDiffModal({ graph, report, message = null }) {
  const overlay = makeOverlay();
  const box = makeBox(overlay);
  box.appendChild(el("h3", "Round-trip (VibeComfy)"));
  if (message) {
    const msg = el("p", message);
    msg.style.whiteSpace = "pre-wrap";
    msg.style.maxWidth = "640px";
    box.appendChild(msg);
  }

  const rows = collectDiffRows(report);
  for (const item of rows) {
    const line = el("div", item.text);
    line.style.color = item.color;
    if (item.title) {
      line.title = item.title;
    }
    box.appendChild(line);
  }

  const removedNamed = report?.change?.content_edits?.removed_named || [];
  const schemaLess = (report?.recovery || []).filter((item) => item?.schema_less === true);
  const needsConfirm = removedNamed.length > 0 || schemaLess.length > 0;
  const applyBtn = button("Apply", () => doApply(graph, overlay, applyBtn, needsConfirm, removedNamed.length, schemaLess.length));
  if (needsConfirm) {
    applyBtn.style.opacity = "0.7";
    applyBtn.style.background = "#555";
  }
  box.appendChild(applyBtn);
  box.appendChild(button("Cancel", () => overlay.remove()));
}

function doApply(graph, overlay, applyBtn, needsConfirm, removedCount, schemaLessCount) {
  if (needsConfirm && applyBtn.dataset.confirmed !== "1") {
    applyBtn.dataset.confirmed = "1";
    applyBtn.textContent = `${removedCount} nodes will be removed and ${schemaLessCount} are schema-less; apply anyway?`;
    return;
  }
  loadGraphDataWithoutScopeSwitch(graph);
  overlay.remove();
  toast("Round-trip applied");
}

function toast(msg) {
  if (app.extensionManager?.toast?.add) {
    app.extensionManager.toast.add({ severity: "success", summary: msg, life: 3000 });
  } else {
    console.log(`VibeComfy: ${msg}`);
  }
}

registerRoundtripExtension(app, {
  openRoundtrip,
  openAgentEdit,
  patchIntentNodePrototype,
  configureDiagnostics() {
    return diagnosticsReporting;
  },
  checkFrontendVersion,
  registerDefaultExecutionModeSetting,
  registerOnDemandSchemasSetting,
  installGraphConfigureIntentFallback,
  installIntentNodeFallback,
  installAgentPreviewOverlay,
  repairLiveIntentNodesFromCandidate,
  installQueueGuard,
  ensureAgentTurnListener,
  ensureExecutorPhaseListener,
  installAgentPanelDebugHook,
  ensureAgentPanel,
  prefetchAgentStatus() {
    // Prefetch agent status at extension setup so the route/model controls are
    // ready before the launcher is first clicked (same path as openAgentPanel).
    // Safe on the not-yet-mounted shell: refreshAgentStatus mutates only
    // panel.state/fields and its renders are guarded by isAgentPanelRootConnected.
    pollerRefreshAgentStatus(currentAgentPanel(), { quiet: true }, agentStatusDeps());
  },
  // The right-edge launcher is the sole production entry point. Keep the
  // historical ComfyUI sidebar mount available only to explicit test/dev
  // harnesses so users do not see duplicate VibeComfy controls on both sides.
  ensureAgentSidebarTab,
  ensureAgentLauncher,
});
