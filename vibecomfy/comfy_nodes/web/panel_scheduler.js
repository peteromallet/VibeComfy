import { RENDER_SECTIONS, normalizeObligationDirtySections } from "./agent_edit_lifecycle.js";
import { currentAgentPanel, getAgentPanelRuntime } from "./panel_runtime.js";

export const ALL_AGENT_PANEL_RENDER_SECTIONS = Object.freeze(Object.values(RENDER_SECTIONS));
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

export function hasPendingAgentPanelFlush() {
  const runtime = getAgentPanelRuntime();
  return Boolean(runtime._scheduledAgentPanelRenderQueued || runtime._scheduledAgentPanelRender);
}

export function noteAgentPanelCommit(panel, commitKind) {
  const runtime = getAgentPanelRuntime();
  const at = new Date().toISOString();
  if (commitKind === "status") {
    runtime._statusCommitAt = at;
    if (panel?.state) {
      panel.state.statusCommitAt = at;
    }
  } else if (commitKind === "rehydrate") {
    runtime._rehydrateCommitAt = at;
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
    const runtime = getAgentPanelRuntime();
    runtime._marksAfterCommit += 1;
    if (panel.state) {
      panel.state.marksAfterCommit = runtime._marksAfterCommit;
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
  if (!isAgentPanelRootConnected(panel)) {
    return;
  }
  const runtime = getAgentPanelRuntime();
  if (fallbackSections !== undefined) {
    markAgentPanelDirty(panel, fallbackSections, { schedule: false });
  }
  const nextScheduled = {
    panel,
    reason,
    fallbackSections,
    dirtyOnly: Boolean(options.dirtyOnly),
  };
  const scheduledBatch = Array.isArray(runtime._scheduledAgentPanelRenders)
    ? runtime._scheduledAgentPanelRenders
    : [];
  if (runtime._scheduledAgentPanelRenderQueued) {
    const existingIndex = scheduledBatch.findIndex((entry) => entry?.panel === panel);
    if (existingIndex >= 0) {
      scheduledBatch[existingIndex] = nextScheduled;
    } else {
      scheduledBatch.push(nextScheduled);
    }
    runtime._scheduledAgentPanelRenders = scheduledBatch;
    runtime._scheduledAgentPanelRender = nextScheduled;
    return;
  }
  runtime._scheduledAgentPanelRender = nextScheduled;
  runtime._scheduledAgentPanelRenders = [nextScheduled];
  const flush = () => {
    const gateway = renderGateway || getAgentPanelRuntime().renderDirtyAgentPanelSections;
    const scheduledBatch = Array.isArray(runtime._scheduledAgentPanelRenders)
      && runtime._scheduledAgentPanelRenders.length
      ? runtime._scheduledAgentPanelRenders.slice()
      : [runtime._scheduledAgentPanelRender].filter(Boolean);
    runtime._scheduledAgentPanelRender = null;
    runtime._scheduledAgentPanelRenders = [];
    runtime._scheduledAgentPanelRenderQueued = false;
    runtime._agentPanelFlushCount += 1;
    const lastScheduled = scheduledBatch[scheduledBatch.length - 1];
    runtime._lastAgentPanelFlushReason = typeof lastScheduled?.reason === "string" ? lastScheduled.reason : "";
    for (const scheduled of scheduledBatch) {
      if (!isAgentPanelRootConnected(scheduled?.panel)) {
        continue;
      }
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
  const flushOnce = () => {
    if (flushed) {
      return;
    }
    flushed = true;
    if (timeoutId !== null && typeof clearTimeout === "function") {
      clearTimeout(timeoutId);
    }
    flush();
  };
  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(flushOnce);
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
