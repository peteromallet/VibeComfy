const AGENT_PANEL_SINGLETON_KEY = "__vibecomfyAgentPanelSingleton";

let fallbackRecord = null;

function createAgentPanelRuntimeState() {
  return {
    agentPanel: null,
    panelsCreated: 0,
    agentSidebarTabRegistered: false,
    agentTurnEventListener: null,
    agentTurnEventListenerRegistered: false,
    changedNodeFeedbackTimer: null,
    changedNodeFeedbackVisuals: [],
    queueGuardHook: null,
    queueGuardContext: null,
    queueGuardFallbackWarning: null,
    queueGuardFallbackWarned: false,
    queueGuardBlockNotice: null,
    queueGuardBlockedTurnKeys: new Set(),
    _previewForegroundInstallReport: null,
    _adapterCapabilities: null,
    _progressPulseInjected: false,
    _scheduledAgentPanelRender: null,
    _scheduledAgentPanelRenders: [],
    _scheduledAgentPanelRenderQueued: false,
    _agentPanelFlushCount: 0,
    _lastAgentPanelFlushReason: "",
    lastThreadRender: null,
    _lastThreadRender: null,
    lastNoticeRender: null,
    _lastNoticeRender: null,
    _statusCommitAt: null,
    _rehydrateCommitAt: null,
    _marksAfterCommit: 0,
    _overlayDrawModelCache: null,
  };
}

function backfillRuntimeShape(runtime) {
  if (!runtime || typeof runtime !== "object") {
    return createAgentPanelRuntimeState();
  }
  if (!(runtime.queueGuardBlockedTurnKeys instanceof Set)) {
    runtime.queueGuardBlockedTurnKeys = new Set(
      Array.isArray(runtime.queueGuardBlockedTurnKeys) ? runtime.queueGuardBlockedTurnKeys : [],
    );
  }
  if (!Array.isArray(runtime.changedNodeFeedbackVisuals)) {
    runtime.changedNodeFeedbackVisuals = [];
  }
  if (!Object.prototype.hasOwnProperty.call(runtime, "panelsCreated") || !Number.isFinite(runtime.panelsCreated)) {
    runtime.panelsCreated = 0;
  }
  const defaults = createAgentPanelRuntimeState();
  for (const [key, value] of Object.entries(defaults)) {
    if (!Object.prototype.hasOwnProperty.call(runtime, key) || runtime[key] === undefined) {
      runtime[key] = key === "queueGuardBlockedTurnKeys"
        ? new Set()
        : Array.isArray(value)
          ? []
          : value;
    }
  }
  return runtime;
}

export function agentPanelSingletonHost() {
  return typeof window !== "undefined" ? window : null;
}

export function agentPanelSingletonRecord(create = false) {
  const host = agentPanelSingletonHost();
  if (!host) {
    if (!create) {
      return fallbackRecord;
    }
    if (!fallbackRecord) {
      fallbackRecord = { runtime: createAgentPanelRuntimeState() };
    } else {
      fallbackRecord.runtime = backfillRuntimeShape(fallbackRecord.runtime);
    }
    return fallbackRecord;
  }
  const current = host[AGENT_PANEL_SINGLETON_KEY];
  if (current && typeof current === "object") {
    if (!current.runtime || typeof current.runtime !== "object") {
      current.runtime = createAgentPanelRuntimeState();
      if (Object.prototype.hasOwnProperty.call(current, "panel")) {
        current.runtime.agentPanel = current.panel || null;
      }
      if (Number.isFinite(current.panelsCreated)) {
        current.runtime.panelsCreated = current.panelsCreated;
      }
    }
    current.runtime = backfillRuntimeShape(current.runtime);
    return current;
  }
  if (!create) {
    return null;
  }
  const record = { runtime: createAgentPanelRuntimeState() };
  host[AGENT_PANEL_SINGLETON_KEY] = record;
  return record;
}

export function getAgentPanelRuntime() {
  return agentPanelSingletonRecord(true).runtime;
}

export function currentAgentPanel() {
  return getAgentPanelRuntime().agentPanel || null;
}

export function setCurrentAgentPanel(panel) {
  const runtime = getAgentPanelRuntime();
  runtime.agentPanel = panel || null;
  return runtime.agentPanel;
}

export function panelsCreatedCount() {
  const sharedCount = getAgentPanelRuntime().panelsCreated;
  return Number.isFinite(sharedCount) ? sharedCount : 0;
}

export function nextAgentPanelId() {
  const runtime = getAgentPanelRuntime();
  const nextCount = Number.isFinite(runtime.panelsCreated) ? runtime.panelsCreated + 1 : 1;
  runtime.panelsCreated = nextCount;
  return `${Date.now()}-${nextCount}`;
}
