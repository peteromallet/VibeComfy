export const AGENT_PANEL_SINGLETON_KEY = "__vibecomfyAgentPanelSingleton";

const RUNTIME_DEFAULTS = Object.freeze({
  agentSidebarTabRegistered: false,
  agentTurnEventListener: null,
  agentTurnEventListenerRegistered: false,
  changedNodeFeedbackTimer: null,
  changedNodeFeedbackVisuals: () => [],
  queueGuardHook: null,
  queueGuardContext: null,
  queueGuardFallbackWarning: null,
  queueGuardFallbackWarned: false,
  queueGuardBlockNotice: null,
  queueGuardBlockedTurnKeys: () => new Set(),
  _adapterCapabilities: null,
  _previewForegroundInstallReport: null,
  _progressPulseInjected: false,
  _scheduledAgentPanelRender: null,
  _scheduledAgentPanelRenderQueued: false,
  _agentPanelFlushCount: 0,
  _lastAgentPanelFlushReason: "",
  _lastThreadRender: null,
  _lastNoticeRender: null,
  _statusCommitAt: null,
  _rehydrateCommitAt: null,
  _marksAfterCommit: 0,
  _overlayDrawModelCache: null,
});

function singletonHost() {
  if (typeof window !== "undefined" && window) {
    return window;
  }
  if (typeof globalThis !== "undefined" && globalThis) {
    return globalThis;
  }
  return null;
}

function cloneDefaultValue(value) {
  return typeof value === "function" ? value() : value;
}

function ensureRuntimeRecord(runtime) {
  const next = runtime && typeof runtime === "object" ? runtime : {};
  for (const [key, value] of Object.entries(RUNTIME_DEFAULTS)) {
    if (!(key in next)) {
      next[key] = cloneDefaultValue(value);
    }
  }
  if (!(next.queueGuardBlockedTurnKeys instanceof Set)) {
    next.queueGuardBlockedTurnKeys = new Set(Array.isArray(next.queueGuardBlockedTurnKeys) ? next.queueGuardBlockedTurnKeys : []);
  }
  if (!Array.isArray(next.changedNodeFeedbackVisuals)) {
    next.changedNodeFeedbackVisuals = [];
  }
  return next;
}

function upgradeSingletonRecord(record) {
  const next = record && typeof record === "object" ? record : {};
  if (!("panel" in next)) {
    next.panel = null;
  }
  if (!Number.isFinite(next.panelsCreated)) {
    next.panelsCreated = 0;
  }
  next.runtime = ensureRuntimeRecord(next.runtime);
  return next;
}

function agentPanelSingletonRecord(create = false) {
  const host = singletonHost();
  if (!host) {
    return null;
  }
  const current = host[AGENT_PANEL_SINGLETON_KEY];
  if (current && typeof current === "object") {
    const upgraded = upgradeSingletonRecord(current);
    host[AGENT_PANEL_SINGLETON_KEY] = upgraded;
    return upgraded;
  }
  if (!create) {
    return null;
  }
  const record = upgradeSingletonRecord({
    panel: null,
    panelsCreated: 0,
  });
  host[AGENT_PANEL_SINGLETON_KEY] = record;
  return record;
}

export function panelRuntime() {
  return agentPanelSingletonRecord(true)?.runtime || ensureRuntimeRecord({});
}

export function currentAgentPanel() {
  return agentPanelSingletonRecord(false)?.panel || null;
}

export function setCurrentAgentPanel(panel) {
  const record = agentPanelSingletonRecord(true);
  if (!record) {
    return panel || null;
  }
  record.panel = panel || null;
  return record.panel;
}

export function panelsCreatedCount() {
  const sharedCount = agentPanelSingletonRecord(false)?.panelsCreated;
  return Number.isFinite(sharedCount) ? sharedCount : 0;
}

export function nextAgentPanelId() {
  const record = agentPanelSingletonRecord(true);
  const nextCount = Number.isFinite(record?.panelsCreated) ? record.panelsCreated + 1 : 1;
  if (record) {
    record.panelsCreated = nextCount;
  }
  return `${Date.now()}-${nextCount}`;
}
