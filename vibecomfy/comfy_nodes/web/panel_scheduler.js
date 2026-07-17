// panel_scheduler.js — Render scheduling for the active agent panel.
//
// A queued callback is authority-bearing work. It is fenced by the concrete
// panel object plus that panel's workflow activation identity, so a callback
// created for a departed workflow or replaced panel can never render (or count
// as a flush for) the new owner.

import { RENDER_SECTIONS, normalizeObligationDirtySections } from "./agent_edit_lifecycle.js";
import { currentAgentPanel, getAgentPanelRuntime } from "./panel_runtime.js";

const ALL_AGENT_PANEL_RENDER_SECTIONS = Object.freeze(Object.values(RENDER_SECTIONS));
export const SETTINGS_STATUS_RENDER_SECTIONS = Object.freeze([
  RENDER_SECTIONS.THREAD,
  RENDER_SECTIONS.SETTINGS,
  RENDER_SECTIONS.COMPOSER,
  RENDER_SECTIONS.NOTICE,
]);
const AGENT_PANEL_RENDER_TIMEOUT_MS = 100;

let renderGateway = null;

export function setRenderGateway(fn) {
  renderGateway = typeof fn === "function" ? fn : null;
  getAgentPanelRuntime().renderDirtyAgentPanelSections = renderGateway;
}

export function normalizeDirtySectionList(sections) {
  if (sections === undefined) {
    return undefined;
  }
  if (sections == null) {
    return [];
  }
  const normalized = normalizeObligationDirtySections({
    render: false,
    dirtySections: sections,
  });
  return Array.isArray(normalized?.dirtySections) ? normalized.dirtySections : [];
}

export function agentPanelPendingDirtySections(panel) {
  if (!panel) {
    return [];
  }
  if (!Array.isArray(panel.pendingDirtySections)) {
    panel.pendingDirtySections = [];
  }
  return panel.pendingDirtySections;
}

export function isAgentPanelRootConnected(panel) {
  if (typeof document === "undefined") {
    return false;
  }
  return Boolean(panel?.root?.isConnected);
}

function _panelActivationIdentity(panel) {
  return {
    panelId: typeof panel?.panelId === "string" ? panel.panelId : null,
    scopeActivationEpoch: Number.isFinite(panel?.state?.scopeActivationEpoch)
      ? panel.state.scopeActivationEpoch
      : 0,
    chatScopeId: typeof panel?.state?.chatScopeId === "string"
      ? panel.state.chatScopeId
      : null,
  };
}

function _samePanelActivation(left, right) {
  return Boolean(left && right)
    && left.panelId === right.panelId
    && left.scopeActivationEpoch === right.scopeActivationEpoch
    && left.chatScopeId === right.chatScopeId;
}

function _scheduledOwnerIsCurrent(scheduled, runtime) {
  const panel = scheduled?.panel;
  return Boolean(panel)
    && panel === runtime?.agentPanel
    && !panel.__renderScheduleRevoked
    && _samePanelActivation(scheduled.activation, _panelActivationIdentity(panel));
}

function _revokeQueuedCycle(runtime) {
  if (typeof runtime._cancelScheduledAgentPanelRender === "function") {
    runtime._cancelScheduledAgentPanelRender();
  }
  for (const scheduled of Array.isArray(runtime._scheduledAgentPanelRenders)
    ? runtime._scheduledAgentPanelRenders
    : []) {
    if (scheduled?.panel?.__renderScheduleGeneration === scheduled.scheduleGeneration) {
      scheduled.panel.__renderFlushPending = false;
    }
  }
  runtime._cancelScheduledAgentPanelRender = null;
  runtime._scheduledAgentPanelRender = null;
  runtime._scheduledAgentPanelRenders = [];
  runtime._scheduledAgentPanelRenderQueued = false;
  runtime._agentPanelRenderScheduleGeneration += 1;
}

export function hasPendingAgentPanelFlush(panel = currentAgentPanel()) {
  return Boolean(
    panel
    && panel.__renderFlushPending
    && !panel.__renderScheduleRevoked
    && _samePanelActivation(
      panel.__renderScheduledActivation,
      _panelActivationIdentity(panel),
    ),
  );
}

export function noteAgentPanelCommit(panel, commitKind) {
  const at = new Date().toISOString();
  if (commitKind === "status") {
    if (panel?.state) {
      panel.state.statusCommitAt = at;
    }
  } else if (commitKind === "rehydrate") {
    if (panel?.state) {
      panel.state.rehydrateCommitAt = at;
    }
  }
  return at;
}

export function markAgentPanelDirty(panel, sections, options = {}) {
  if (!panel) {
    return [];
  }
  const nextSections = normalizeDirtySectionList(sections);
  if (!Array.isArray(nextSections) || !nextSections.length) {
    return agentPanelPendingDirtySections(panel);
  }
  const pending = agentPanelPendingDirtySections(panel);
  const seen = new Set(pending);
  for (const section of nextSections) {
    if (!seen.has(section)) {
      pending.push(section);
      seen.add(section);
    }
  }
  if (options.schedule !== false && isAgentPanelRootConnected(panel)) {
    scheduleRenderAgentPanel("dirty-sections", panel, undefined, { dirtyOnly: true });
  }
  return pending;
}

export function markAllAgentPanelDirty(panel) {
  return markAgentPanelDirty(panel, ALL_AGENT_PANEL_RENDER_SECTIONS);
}

export function consumeAgentPanelDirtySections(panel, fallbackSections = ALL_AGENT_PANEL_RENDER_SECTIONS) {
  if (!panel) {
    return [];
  }
  const pending = agentPanelPendingDirtySections(panel).slice();
  panel.pendingDirtySections = [];
  const fallback = normalizeDirtySectionList(fallbackSections);
  if (!pending.length && (!Array.isArray(fallback) || !fallback.length)) {
    return ALL_AGENT_PANEL_RENDER_SECTIONS.slice();
  }
  return normalizeDirtySectionList([
    ...pending,
    ...(Array.isArray(fallback) ? fallback : []),
  ]) || [];
}

export function markAgentPanelDirtyAfterCommit(panel, sections, commitKind) {
  if (!panel) {
    return [];
  }
  noteAgentPanelCommit(panel, commitKind);
  const normalized = normalizeDirtySectionList(sections);
  if (Array.isArray(normalized) && normalized.length) {
    panel.__marksAfterCommit = Number.isFinite(panel.__marksAfterCommit)
      ? panel.__marksAfterCommit + 1
      : 1;
    if (panel.state) {
      panel.state.marksAfterCommit = panel.__marksAfterCommit;
    }
  }
  return markAgentPanelDirty(panel, normalized);
}

export function ensureScheduledAgentPanelDirtyFlush(panel, reason = "dirty-sections") {
  if (
    panel
    && agentPanelPendingDirtySections(panel).length
    && !hasPendingAgentPanelFlush()
    && isAgentPanelRootConnected(panel)
  ) {
    scheduleRenderAgentPanel(reason, panel, undefined, { dirtyOnly: true });
  }
}

export function scheduleRenderAgentPanel(reason = "scheduled", panel = currentAgentPanel(), fallbackSections = undefined, options = {}) {
  // Validate dirty sections before any early-return so unknown
  // sections (including RENDER_SECTIONS.CANDIDATE if ever introduced)
  // are rejected even when the panel root is disconnected.
  const safeFallback = fallbackSections !== undefined
    ? normalizeDirtySectionList(fallbackSections)
    : undefined;

  const runtime = panel?.__agentPanelRuntime || getAgentPanelRuntime();
  if (!isAgentPanelRootConnected(panel) || panel !== runtime.agentPanel) {
    return;
  }
  if (safeFallback !== undefined) {
    markAgentPanelDirty(panel, safeFallback, { schedule: false });
  }
  const nextScheduled = {
    panel,
    activation: _panelActivationIdentity(panel),
    reason,
    fallbackSections: safeFallback,
    dirtyOnly: Boolean(options.dirtyOnly),
  };
  const scheduledBatch = Array.isArray(runtime._scheduledAgentPanelRenders)
    ? runtime._scheduledAgentPanelRenders
    : [];
  if (runtime._scheduledAgentPanelRenderQueued) {
    const existingIndex = scheduledBatch.findIndex((entry) => entry?.panel === panel);
    const existing = existingIndex >= 0 ? scheduledBatch[existingIndex] : null;
    if (existing && _samePanelActivation(existing.activation, nextScheduled.activation)) {
      nextScheduled.scheduleGeneration = existing.scheduleGeneration;
      scheduledBatch[existingIndex] = nextScheduled;
      runtime._scheduledAgentPanelRenders = scheduledBatch;
      runtime._scheduledAgentPanelRender = nextScheduled;
      return;
    }
    // A different panel or workflow activation owns this new work. Revoke the
    // old cycle and arm a fresh callback; never let its callback flush the new
    // activation merely because both happened before the next frame.
    _revokeQueuedCycle(runtime);
  }
  const scheduleGeneration = runtime._agentPanelRenderScheduleGeneration + 1;
  runtime._agentPanelRenderScheduleGeneration = scheduleGeneration;
  nextScheduled.scheduleGeneration = scheduleGeneration;
  runtime._scheduledAgentPanelRender = nextScheduled;
  runtime._scheduledAgentPanelRenders = [nextScheduled];
  panel.__renderScheduleGeneration = scheduleGeneration;
  panel.__renderScheduledActivation = nextScheduled.activation;
  panel.__renderFlushPending = true;
  panel.__renderScheduleRevoked = false;
  const flush = () => {
    if (runtime._agentPanelRenderScheduleGeneration !== scheduleGeneration) {
      return;
    }
    const gateway = renderGateway || runtime.renderDirtyAgentPanelSections;
    const scheduledBatch = Array.isArray(runtime._scheduledAgentPanelRenders)
      && runtime._scheduledAgentPanelRenders.length
      ? runtime._scheduledAgentPanelRenders.slice()
      : [runtime._scheduledAgentPanelRender].filter(Boolean);
    runtime._scheduledAgentPanelRender = null;
    runtime._scheduledAgentPanelRenders = [];
    runtime._scheduledAgentPanelRenderQueued = false;
    runtime._cancelScheduledAgentPanelRender = null;
    const currentBatch = scheduledBatch.filter((scheduled) =>
      scheduled?.scheduleGeneration === scheduleGeneration
      && _scheduledOwnerIsCurrent(scheduled, runtime));
    for (const scheduled of scheduledBatch) {
      if (scheduled?.panel?.__renderScheduleGeneration === scheduleGeneration) {
        scheduled.panel.__renderFlushPending = false;
      }
    }
    for (const scheduled of currentBatch) {
      if (!isAgentPanelRootConnected(scheduled.panel)) {
        continue;
      }
      scheduled.panel.__renderFlushCount = Number.isFinite(scheduled.panel.__renderFlushCount)
        ? scheduled.panel.__renderFlushCount + 1
        : 1;
      scheduled.panel.__lastRenderFlushReason = typeof scheduled.reason === "string"
        ? scheduled.reason
        : "";
      if (
        scheduled.dirtyOnly
        && scheduled.fallbackSections === undefined
        && !agentPanelPendingDirtySections(scheduled.panel).length
      ) {
        continue;
      }
      if (typeof gateway === "function") {
        gateway(scheduled.panel, {
          render: true,
          dirtySections: scheduled.fallbackSections,
        });
      }
    }
  };
  runtime._scheduledAgentPanelRenderQueued = true;
  let flushed = false;
  let timeoutId = null;
  let animationFrameId = null;
  const cancel = () => {
    if (flushed) {
      return;
    }
    flushed = true;
    if (timeoutId !== null && typeof clearTimeout === "function") {
      clearTimeout(timeoutId);
    }
    if (animationFrameId !== null && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(animationFrameId);
    }
  };
  const flushOnce = () => {
    if (flushed) {
      return;
    }
    flushed = true;
    if (timeoutId !== null && typeof clearTimeout === "function") {
      clearTimeout(timeoutId);
    }
    if (runtime._agentPanelRenderScheduleGeneration !== scheduleGeneration) {
      return;
    }
    flush();
  };
  runtime._cancelScheduledAgentPanelRender = cancel;
  if (typeof requestAnimationFrame === "function") {
    animationFrameId = requestAnimationFrame(flushOnce);
    if (typeof setTimeout === "function") {
      timeoutId = setTimeout(flushOnce, AGENT_PANEL_RENDER_TIMEOUT_MS);
    }
  } else if (typeof queueMicrotask === "function") {
    queueMicrotask(flushOnce);
  } else if (typeof Promise !== "undefined") {
    Promise.resolve().then(flushOnce);
  } else if (typeof setTimeout === "function") {
    timeoutId = setTimeout(flushOnce, 0);
  } else {
    flushOnce();
  }
}
