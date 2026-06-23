// ── Agent Status Poller (Sprint 1 — extracted status/settings/credential ownership) ──
// This module owns status polling, route-select population, settings persistence,
// OpenRouter credential storage, provider test flow, and choose-engine gate sync.
// All monolith-local render/lifecycle callbacks are passed through explicit deps
// injection; this module does NOT import from other vibecomfy web modules.

// ── Constants ───────────────────────────────────────────────────────────────

export const ROUTE_STATUS_KIND = Object.freeze({
  LOADING: "loading_status",
  READY: "ready",
  MISSING_OPTIONS: "missing_route_options",
  MALFORMED: "malformed_status",
  UNAVAILABLE: "status_unavailable",
});

const AGENT_STATUS_RETRY_DELAYS_MS = Object.freeze([250, 1000, 3000]);

const ROUTE_ALIASES = Object.freeze({
  auto: "auto",
  arnold: "auto",
  openrouter: "openrouter",
  deepseek: "openrouter",
  anthropic: "anthropic",
  claude: "anthropic",
  "openai-codex": "openai-codex",
  codex: "openai-codex",
});

const ROUTE_LABELS = Object.freeze({
  auto: "auto",
  openrouter: "openrouter",
  anthropic: "anthropic",
  "openai-codex": "openai-codex",
});

const CANONICAL_AGENT_PROVIDERS = new Set(["anthropic", "openai-codex", "openrouter"]);

// ── localStorage helpers (safe wrappers — tolerate missing/throwing storage) ──

const LS_AGENT_PROVIDER_KEY = "vibecomfy_agent_provider";

export function _lsGet(key) {
  try {
    const storage = typeof localStorage !== "undefined" && localStorage !== null
      ? localStorage
      : globalThis?.localStorage;
    if (!storage) {
      return null;
    }
    return storage.getItem(key);
  } catch (_e) {
    return null;
  }
}

export function _lsSet(key, value) {
  try {
    const storage = typeof localStorage !== "undefined" && localStorage !== null
      ? localStorage
      : globalThis?.localStorage;
    if (!storage) {
      return;
    }
    storage.setItem(key, value);
  } catch (_e) {
    // Best-effort: silently swallow set errors (private browsing, quota, etc.)
  }
}

export function _lsRemove(key) {
  try {
    const storage = typeof localStorage !== "undefined" && localStorage !== null
      ? localStorage
      : globalThis?.localStorage;
    if (!storage) {
      return;
    }
    storage.removeItem(key);
  } catch (_e) {
    // Best-effort.
  }
}

export function getPersistedAgentProvider() {
  const raw = _lsGet(LS_AGENT_PROVIDER_KEY);
  if (raw == null) return null;
  if (raw === "deepseek") return "openrouter";
  if (CANONICAL_AGENT_PROVIDERS.has(raw)) return raw;
  return null;
}

export function setPersistedAgentProvider(value) {
  if (value == null) {
    _lsRemove(LS_AGENT_PROVIDER_KEY);
    return;
  }
  _lsSet(LS_AGENT_PROVIDER_KEY, String(value));
}

// ── Pure helpers ────────────────────────────────────────────────────────────

export function buildStatusUrl(route, model) {
  const params = new URLSearchParams();
  if (route) {
    params.set("route", route);
  }
  if (model) {
    params.set("model", model);
  }
  const query = params.toString();
  return query ? `/vibecomfy/agent/status?${query}` : "/vibecomfy/agent/status";
}

export function routeStatusState(panel) {
  return panel?.state?.routeStatus || { kind: ROUTE_STATUS_KIND.LOADING };
}

export function routeOptionsFromStatus(status) {
  if (!status || typeof status !== "object" || Array.isArray(status)) {
    return null;
  }
  const options = status.route_options;
  if (!options || typeof options !== "object" || Array.isArray(options)) {
    return null;
  }
  return options;
}

export function projectRouteStatus(status, request = {}) {
  const route = normalizeRoutePreference(request.route);
  const model = normalizeModelPreference(request.model);
  const quiet = Boolean(request.quiet);
  const isStatusObject = Boolean(status && typeof status === "object" && !Array.isArray(status));
  const routeOptions = routeOptionsFromStatus(status);
  const requestedRoute = normalizeRoutePreferenceForStatus(
    isStatusObject ? (status.requested_route || route) : route,
    routeOptions,
  );
  const routeStatusBase = { requestedRoute, model };

  if (!isStatusObject) {
    return {
      issue: "malformed_status",
      routeStatus: {
        kind: ROUTE_STATUS_KIND.MALFORMED,
        ...routeStatusBase,
      },
      routeOptions: null,
      selectedRoute: requestedRoute,
      placeholderLabel: "Malformed status payload",
      settingsMessage: "Malformed status payload; route/model controls disabled.",
    };
  }

  if (!routeOptions) {
    return {
      issue: "missing_route_options",
      routeStatus: {
        kind: ROUTE_STATUS_KIND.MISSING_OPTIONS,
        ...routeStatusBase,
      },
      routeOptions: null,
      selectedRoute: requestedRoute,
      placeholderLabel: "Route options unavailable",
      settingsMessage: "Status missing route options; route/model controls disabled.",
    };
  }

  if (!routeOptions[requestedRoute]) {
    return {
      issue: "missing_route_descriptor",
      routeStatus: {
        kind: ROUTE_STATUS_KIND.MALFORMED,
        ...routeStatusBase,
      },
      routeOptions,
      selectedRoute: requestedRoute,
      placeholderLabel: null,
      settingsMessage: "Malformed status payload; route/model controls disabled.",
    };
  }

  if (status.ready === false) {
    return {
      issue: null,
      routeStatus: {
        kind: ROUTE_STATUS_KIND.UNAVAILABLE,
        ...routeStatusBase,
      },
      routeOptions,
      selectedRoute: requestedRoute,
      placeholderLabel: null,
      settingsMessage: status.reason || "Provider unavailable.",
    };
  }

  const availability = status.provider_available === false ? "provider unavailable" : "provider ready";
  return {
    issue: null,
    routeStatus: {
      kind: ROUTE_STATUS_KIND.READY,
      ...routeStatusBase,
    },
    routeOptions,
    selectedRoute: requestedRoute,
    placeholderLabel: null,
    settingsMessage: quiet
      ? null
      : `${status.requested_route || route} → ${status.route || route} (${availability})`,
  };
}

export function normalizeRoutePreference(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  return ROUTE_ALIASES[normalized] || "openrouter";
}

function normalizeRoutePreferenceForStatus(value, routeOptions) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  if (normalized && routeOptions && Object.prototype.hasOwnProperty.call(routeOptions, normalized)) {
    return normalized;
  }
  return normalizeRoutePreference(normalized);
}

export function normalizeModelPreference(value) {
  const normalized = String(value || "").trim();
  return normalized ? normalized : null;
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

function recordAgentStatusDiagnostic(panel, diagnostic) {
  if (!panel?.state || !diagnostic || typeof diagnostic !== "object") {
    return;
  }
  panel.state.lastAgentStatusDiagnostic = {
    at: new Date().toISOString(),
    ...diagnostic,
  };
}

// ── DOM helpers (module-local) ──────────────────────────────────────────────

function clearNode(node) {
  while (node.children.length) {
    node.removeChild(node.children[0]);
  }
}

function optionEl(value, label, ownerDocument) {
  const doc = ownerDocument || (typeof document !== "undefined" ? document : null);
  if (!doc) {
    throw new ReferenceError("document is not defined");
  }
  const node = doc.createElement("option");
  node.value = value;
  node.textContent = label;
  return node;
}

// ── Route descriptor lookup ─────────────────────────────────────────────────

function getRouteOptions(panel) {
  return routeOptionsFromStatus(panel.state.statusSnapshot);
}

function getRouteDescriptor(panel, route) {
  const normalized = normalizeRoutePreference(
    route !== undefined ? route : panel.fields.route.value,
  );
  return getRouteOptions(panel)?.[normalized] || null;
}

// ── storedReadyProviderFromStatus (choose-engine gate helper) ───────────────

function storedReadyProviderFromStatus(panel) {
  const status = panel?.state?.statusSnapshot;
  const routeStatus = routeStatusState(panel);
  if (!status || routeStatus.kind !== ROUTE_STATUS_KIND.READY || status.provider_available === false) {
    return null;
  }
  const resolvedRoute = normalizeRoutePreference(
    status.route || status.route_metadata?.normalized_route || status.requested_route,
  );
  if (resolvedRoute === "openrouter" && status.credential_presence?.openrouter_api_key) {
    return "openrouter";
  }
  return null;
}

// ── clearAgentStatusRetry ───────────────────────────────────────────────────

export function clearAgentStatusRetry(panel) {
  const retry = panel?.state?.statusRetry;
  if (retry?.timerId) {
    clearTimeout(retry.timerId);
  }
  if (panel?.state) {
    panel.state.statusRetry = null;
  }
}

// ── scheduleAgentStatusRetry ────────────────────────────────────────────────

export function scheduleAgentStatusRetry(panel, route, model, { quiet = true } = {}, deps = {}) {
  if (!panel?.state) {
    return;
  }
  const { refreshAgentStatus: refreshFn } = deps;
  const prior = panel.state.statusRetry;
  const priorAttempts =
    prior?.route === route && prior?.model === model && Number.isFinite(prior?.attempts)
      ? prior.attempts
      : 0;
  const attempts = priorAttempts + 1;
  if (attempts > AGENT_STATUS_RETRY_DELAYS_MS.length) {
    panel.state.statusRetry = { route, model, attempts: priorAttempts, exhausted: true, timerId: null };
    return;
  }
  const delayMs = AGENT_STATUS_RETRY_DELAYS_MS[attempts - 1];
  const timerId = setTimeout(() => {
    if (!panel?.state?.statusRetry || panel.state.statusRetry.timerId !== timerId) {
      return;
    }
    panel.state.statusRetry.timerId = null;
    if (typeof refreshFn === "function") {
      refreshFn(panel, { quiet }, deps);
    }
  }, delayMs);
  panel.state.statusRetry = { route, model, attempts, exhausted: false, timerId };
}

// ── populateRouteSelect ─────────────────────────────────────────────────────

export function populateRouteSelect(selectNode, routeOptions, {
  placeholderLabel = "Loading route/model status…",
  selectedRoute = selectNode.value,
} = {}, deps = {}) {
  const ownerDocument = selectNode?.ownerDocument || (typeof document !== "undefined" ? document : null);
  if (!ownerDocument) {
    return;
  }
  const preferredRoute = normalizeRoutePreference(selectedRoute);
  const knownRoutes = Object.keys(ROUTE_LABELS).filter((route) => routeOptions?.[route]);
  const extraRoutes = Object.keys(routeOptions || {}).filter((route) => !ROUTE_LABELS[route]);
  const desired = [...knownRoutes, ...extraRoutes];
  clearNode(selectNode);
  if (!desired.length) {
    const node = optionEl(preferredRoute, placeholderLabel, ownerDocument);
    node.disabled = true;
    node.selected = true;
    selectNode.appendChild(node);
    selectNode.value = preferredRoute;
    return;
  }
  for (const route of desired) {
    const descriptor = routeOptions?.[route] || null;
    const label = ROUTE_LABELS[route] || route;
    const node = optionEl(route, label, ownerDocument);
    if (descriptor?.normalized_route && descriptor.normalized_route !== route) {
      node.title = `${label} → ${descriptor.normalized_route}`;
    }
    selectNode.appendChild(node);
  }
  selectNode.value = desired.includes(preferredRoute) ? preferredRoute : desired[0];
}

// ── refreshAgentStatus ──────────────────────────────────────────────────────

export async function refreshAgentStatus(panel, { quiet = false } = {}, deps = {}) {
  const {
    renderAgentPanel,
    nextMacrotask,
    markAgentPanelDirtyAfterCommit,
    SETTINGS_STATUS_RENDER_SECTIONS,
    RENDER_SECTIONS,
    syncChooseEngineGate: syncGateFn,
  } = deps;

  const route = normalizeRoutePreference(panel.fields.route.value);
  const model = normalizeModelPreference(panel.fields.model.value);
  const requestEpoch =
    (Number.isFinite(panel.state.statusRequestEpoch) ? panel.state.statusRequestEpoch : 0) + 1;
  panel.state.statusRequestEpoch = requestEpoch;
  const priorRetry = panel.state.statusRetry;
  const retryAttempts =
    priorRetry?.route === route && priorRetry?.model === model && Number.isFinite(priorRetry?.attempts)
      ? priorRetry.attempts
      : 0;
  if (priorRetry?.timerId) {
    clearTimeout(priorRetry.timerId);
  }
  panel.state.statusRetry = retryAttempts > 0
    ? { route, model, attempts: retryAttempts, exhausted: false, timerId: null }
    : null;
  panel.state.routeStatus = {
    kind: ROUTE_STATUS_KIND.LOADING,
    requestedRoute: route,
    model,
  };
  if (typeof document !== "undefined" && typeof renderAgentPanel === "function") {
    renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
  }
  try {
    // Keep the initial "loading" paint observable, then let tests/users observe
    // the completed state after the request has actually been issued.
    if (typeof nextMacrotask === "function") {
      await nextMacrotask();
    }
    const statusUrl = buildStatusUrl(route, model);
    const res = await fetch(statusUrl);
    let status = null;
    try {
      status = await res.json();
      recordAgentStatusDiagnostic(panel, {
        url: statusUrl,
        ok: res.ok,
        httpStatus: res.status,
        payload: scrubDebugPayload(status),
      });
    } catch (error) {
      if (Number.isFinite(requestEpoch) && panel.state.statusRequestEpoch !== requestEpoch) {
        return;
      }
      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", error);
      recordAgentStatusDiagnostic(panel, {
        url: statusUrl,
        ok: false,
        httpStatus: res.status,
        error: `Malformed JSON: ${String(error?.message || error)}`,
      });
      panel.state.statusSnapshot = null;
      panel.state.routeStatus = {
        kind: ROUTE_STATUS_KIND.MALFORMED,
        requestedRoute: route,
        model,
        detail: String(error),
      };
      panel.state.settingsMessage = "Malformed status payload; route/model controls disabled.";
      populateRouteSelect(panel.fields.route, null, {
        placeholderLabel: "Malformed status payload",
        selectedRoute: route,
      }, deps);
      panel.fields.route.value = route;
      if (typeof document !== "undefined" && typeof markAgentPanelDirtyAfterCommit === "function") {
        markAgentPanelDirtyAfterCommit(panel, SETTINGS_STATUS_RENDER_SECTIONS, "status");
      }
      return;
    }
    if (Number.isFinite(requestEpoch) && panel.state.statusRequestEpoch !== requestEpoch) {
      return;
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    clearAgentStatusRetry(panel);
    panel.state.statusSnapshot = status;
    const projected = projectRouteStatus(status, { route, model, quiet });
    const requestedRoute = projected.routeStatus.requestedRoute;
    if (projected.issue === "malformed_status") {
      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", status);
    } else if (projected.issue === "missing_route_options") {
      console.warn("[vibecomfy] status payload missing route_options", status);
    } else if (projected.issue === "missing_route_descriptor") {
      console.warn("[vibecomfy] status payload missing descriptor for requested route", {
        requestedRoute,
        routeOptions: projected.routeOptions,
      });
    }
    panel.state.routeStatus = projected.routeStatus;
    if (projected.settingsMessage != null) {
      panel.state.settingsMessage = projected.settingsMessage;
    }
    if (projected.routeOptions) {
      populateRouteSelect(panel.fields.route, projected.routeOptions, {
        selectedRoute: requestedRoute,
      }, deps);
    } else {
      populateRouteSelect(panel.fields.route, null, {
        placeholderLabel: projected.placeholderLabel || "Status unavailable",
        selectedRoute: requestedRoute,
      }, deps);
    }
    panel.fields.route.value = requestedRoute;
    if (typeof status?.model === "string" && !panel.fields.model.value.trim()) {
      panel.fields.model.value = status.model;
    }
  } catch (e) {
    if (Number.isFinite(requestEpoch) && panel.state.statusRequestEpoch !== requestEpoch) {
      return;
    }
    const priorStatusDiagnostic = panel.state.lastAgentStatusDiagnostic || null;
    recordAgentStatusDiagnostic(panel, {
      url: buildStatusUrl(route, model),
      ok: false,
      httpStatus: priorStatusDiagnostic?.httpStatus ?? null,
      error: String(e?.message || e),
      payload: priorStatusDiagnostic?.payload || null,
    });
    panel.state.settingsMessage = `Status unavailable: ${String(e)}`;
    panel.state.statusSnapshot = null;
    panel.state.routeStatus = {
      kind: ROUTE_STATUS_KIND.UNAVAILABLE,
      requestedRoute: route,
      model,
      detail: String(e),
    };
    populateRouteSelect(panel.fields.route, null, {
      placeholderLabel: "Status unavailable",
      selectedRoute: route,
    }, deps);
    panel.fields.route.value = route;
    scheduleAgentStatusRetry(panel, route, model, { quiet: true }, deps);
  }
  if (typeof document === "undefined") {
    return;
  }
  // choose-engine gate refresh hooks
  if (typeof syncGateFn === "function") {
    syncGateFn(panel, deps);
  }
  if (typeof panel?.state?.chooseEngineRefresh === "function") {
    panel.state.chooseEngineRefresh();
  }
  const statusDirtySections = Array.isArray(panel?.state?.chatMessages) && panel.state.chatMessages.length
    ? [...SETTINGS_STATUS_RENDER_SECTIONS, RENDER_SECTIONS.META, RENDER_SECTIONS.THREAD]
    : SETTINGS_STATUS_RENDER_SECTIONS;
  if (typeof markAgentPanelDirtyAfterCommit === "function") {
    markAgentPanelDirtyAfterCommit(panel, statusDirtySections, "status");
  }
}

// ── syncChooseEngineGate ────────────────────────────────────────────────────

export function syncChooseEngineGate(panel, deps = {}) {
  if (!panel?.shell || typeof document === "undefined") {
    return;
  }
  const { closeChooseEngineOverlay, openChooseEngineOverlay } = deps;
  const persisted = getPersistedAgentProvider();
  if (persisted) {
    if (typeof closeChooseEngineOverlay === "function") {
      closeChooseEngineOverlay(panel);
    }
    return;
  }
  const readyProvider = storedReadyProviderFromStatus(panel);
  if (readyProvider) {
    setPersistedAgentProvider(readyProvider);
    populateRouteSelect(panel.fields.route, routeOptionsFromStatus(panel.state.statusSnapshot), {
      selectedRoute: readyProvider,
    }, deps);
    panel.fields.route.value = readyProvider;
    if (typeof closeChooseEngineOverlay === "function") {
      closeChooseEngineOverlay(panel);
    }
    return;
  }
  if (routeStatusState(panel).kind !== ROUTE_STATUS_KIND.LOADING) {
    if (typeof openChooseEngineOverlay === "function") {
      openChooseEngineOverlay(panel, { onResolved: () => {} });
    }
  }
}

// ── storeOpenRouterCredential ───────────────────────────────────────────────

export async function storeOpenRouterCredential(panel, apiKey, descriptor = null) {
  try {
    const res = await fetch("/vibecomfy/agent/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "openrouter", api_key: apiKey }),
    });
    const result = await res.json();
    const message = result?.stored
      ? "Stored OpenRouter API key."
      : (result?.reason || descriptor?.guidance || "Browser credential was not stored.");
    panel.state.settingsMessage = message;
    panel.state.settingsMessageKind = result?.stored ? "success" : "error";
    if (result?.stored) {
      panel.state.lastAutoSavedOpenRouterKey = apiKey;
    }
    return { stored: Boolean(result?.stored), message };
  } catch (e) {
    const message = `Credential save failed: ${String(e)}`;
    panel.state.settingsMessage = message;
    panel.state.settingsMessageKind = "error";
    return { stored: false, message };
  }
}

// ── persistAgentSettings ────────────────────────────────────────────────────

export async function persistAgentSettings(panel, {
  includeCredential = false,
} = {}, deps = {}) {
  if (!panel) {
    return;
  }
  const {
    clearCredentialInput,
    renderAgentPanel,
    SETTINGS_STATUS_RENDER_SECTIONS,
    refreshAgentStatus: refreshFn,
  } = deps;

  const route = normalizeRoutePreference(panel.fields.route.value);
  const model = normalizeModelPreference(panel.fields.model.value);
  const descriptor = getRouteDescriptor(panel, route);

  if (routeStatusState(panel).kind !== ROUTE_STATUS_KIND.READY || !descriptor) {
    panel.state.settingsMessage = "Route/model controls are unavailable until /vibecomfy/agent/status returns a valid payload.";
    panel.state.settingsMessageKind = "error";
    if (typeof renderAgentPanel === "function") {
      renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
    }
    return;
  }

  const apiKey = String(panel.fields.apiKey.value || "").trim();

  setPersistedAgentProvider(route);
  let savedMessage = `✓ Saved ${route}${model ? ` / ${model}` : " / default model"}.`;
  panel.state.settingsMessage = savedMessage;
  panel.state.settingsMessageKind = "success";

  if (includeCredential && apiKey && !descriptor.browser_api_key_allowed) {
    savedMessage = descriptor.guidance || "Browser credential was not stored.";
    panel.state.settingsMessage = savedMessage;
    panel.state.settingsMessageKind = "error";
    if (typeof clearCredentialInput === "function") {
      clearCredentialInput(panel);
    }
  } else if (includeCredential && apiKey && apiKey !== panel.state.lastAutoSavedOpenRouterKey) {
    const result = await storeOpenRouterCredential(panel, apiKey, descriptor);
    if (result.stored && typeof clearCredentialInput === "function") {
      clearCredentialInput(panel);
    }
    savedMessage = result.stored ? `✓ ${result.message}` : result.message;
  }

  if (typeof refreshFn === "function") {
    await refreshFn(panel, { quiet: Boolean(apiKey) }, deps);
  }

  panel.state.settingsMessage = savedMessage;
  if (typeof renderAgentPanel === "function") {
    renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
  }
}

// ── testAgentSettings ───────────────────────────────────────────────────────

export async function testAgentSettings(panel, deps = {}) {
  if (!panel) {
    return;
  }
  const {
    renderAgentPanel,
    SETTINGS_STATUS_RENDER_SECTIONS,
    RENDER_SECTIONS,
    refreshAgentStatus: refreshFn,
  } = deps;

  const route = normalizeRoutePreference(panel.fields.route.value);
  const model = normalizeModelPreference(panel.fields.model.value);

  panel.state.providerTestInFlight = true;
  panel.state.settingsMessage = "Testing provider status…";
  panel.state.settingsMessageKind = "pending";

  if (typeof renderAgentPanel === "function") {
    renderAgentPanel(panel, { dirtySections: [...SETTINGS_STATUS_RENDER_SECTIONS, RENDER_SECTIONS.COMPOSER] });
  }

  try {
    if (typeof refreshFn === "function") {
      await refreshFn(panel, { quiet: true }, deps);
    }
    const routeStatus = routeStatusState(panel);
    const status = panel.state.statusSnapshot;

    if (routeStatus.kind === ROUTE_STATUS_KIND.READY && status?.provider_available !== false) {
      const resolvedRoute = String(status?.route_metadata?.normalized_route || status?.route || route);
      const requestedRoute = String(status?.requested_route || route);
      const modelLabel = status?.model || model || "default";
      panel.state.settingsMessage =
        `Provider test passed: ${requestedRoute} → ${resolvedRoute} (${modelLabel}).`;
      panel.state.settingsMessageKind = "success";
    } else if (routeStatus.kind === ROUTE_STATUS_KIND.READY) {
      const resolvedRoute = String(status?.route_metadata?.normalized_route || status?.route || route);
      panel.state.settingsMessage =
        `Provider test failed: ${route} → ${resolvedRoute} is unavailable.`;
      panel.state.settingsMessageKind = "error";
    }
  } finally {
    panel.state.providerTestInFlight = false;
    if (typeof renderAgentPanel === "function") {
      renderAgentPanel(panel, { dirtySections: [...SETTINGS_STATUS_RENDER_SECTIONS, RENDER_SECTIONS.COMPOSER] });
    }
  }
}

// ── configureAgentStatusDeps (one-shot injection convenience) ───────────────

export function configureAgentStatusDeps(deps) {
  return {
    refreshAgentStatus: (panel, opts) => refreshAgentStatus(panel, opts, deps),
    routeStatusState,
    populateRouteSelect: (selectNode, routeOptions, opts) => populateRouteSelect(selectNode, routeOptions, opts, deps),
    persistAgentSettings: (panel, opts) => persistAgentSettings(panel, opts, deps),
    storeOpenRouterCredential: (panel, apiKey, descriptor) => storeOpenRouterCredential(panel, apiKey, descriptor),
    testAgentSettings: (panel) => testAgentSettings(panel, deps),
    syncChooseEngineGate: (panel) => syncChooseEngineGate(panel, deps),
    scheduleAgentStatusRetry: (panel, route, model, opts) => scheduleAgentStatusRetry(panel, route, model, opts, deps),
    clearAgentStatusRetry,
    buildStatusUrl,
    routeOptionsFromStatus,
    ROUTE_STATUS_KIND,
    getPersistedAgentProvider,
    setPersistedAgentProvider,
  };
}
