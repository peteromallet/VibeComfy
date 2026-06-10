import { markAgentPanelDirtyAfterCommit, SETTINGS_STATUS_RENDER_SECTIONS } from "./panel_scheduler.js";
import { RENDER_SECTIONS } from "./agent_edit_lifecycle.js";

export const ROUTE_STATUS_KIND = Object.freeze({
  LOADING: "loading_status",
  READY: "ready",
  MISSING_OPTIONS: "missing_route_options",
  MALFORMED: "malformed_status",
  UNAVAILABLE: "status_unavailable",
});

const AGENT_STATUS_RETRY_DELAYS_MS = Object.freeze([250, 1000, 3000]);

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

export function clearAgentStatusRetry(panel) {
  const retry = panel?.state?.statusRetry;
  if (retry?.timerId) {
    clearTimeout(retry.timerId);
  }
  if (panel?.state) {
    panel.state.statusRetry = null;
  }
}

export function scheduleAgentStatusRetry(panel, route, model, { quiet = true } = {}, deps = {}) {
  if (!panel?.state) {
    return;
  }
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
    refreshAgentStatus(panel, { quiet }, deps);
  }, delayMs);
  panel.state.statusRetry = { route, model, attempts, exhausted: false, timerId };
}

export async function refreshAgentStatus(panel, { quiet = false } = {}, deps = {}) {
  const {
    normalizeRoutePreference,
    normalizeModelPreference,
    renderAgentPanel,
    nextMacrotask,
    populateRouteSelect,
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
  if (typeof document !== "undefined") {
    renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
  }
  try {
    // Keep the initial "loading" paint observable, then let tests/users observe
    // the completed state after the request has actually been issued.
    await nextMacrotask();
    const res = await fetch(buildStatusUrl(route, model));
    let status = null;
    try {
      status = await res.json();
    } catch (error) {
      if (Number.isFinite(requestEpoch) && panel.state.statusRequestEpoch !== requestEpoch) {
        return;
      }
      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", error);
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
      });
      panel.fields.route.value = route;
      if (typeof document !== "undefined") {
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
    const requestedRoute = normalizeRoutePreference(status?.requested_route || route);
    const routeOptions = routeOptionsFromStatus(status);
    if (!status || typeof status !== "object" || Array.isArray(status)) {
      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", status);
      panel.state.routeStatus = {
        kind: ROUTE_STATUS_KIND.MALFORMED,
        requestedRoute,
        model,
      };
      panel.state.settingsMessage = "Malformed status payload; route/model controls disabled.";
      populateRouteSelect(panel.fields.route, null, {
        placeholderLabel: "Malformed status payload",
        selectedRoute: requestedRoute,
      });
      panel.fields.route.value = requestedRoute;
    } else if (!routeOptions) {
      console.warn("[vibecomfy] status payload missing route_options", status);
      panel.state.routeStatus = {
        kind: ROUTE_STATUS_KIND.MISSING_OPTIONS,
        requestedRoute,
        model,
      };
      panel.state.settingsMessage = "Status missing route options; route/model controls disabled.";
      populateRouteSelect(panel.fields.route, null, {
        placeholderLabel: "Route options unavailable",
        selectedRoute: requestedRoute,
      });
      panel.fields.route.value = requestedRoute;
    } else {
      populateRouteSelect(panel.fields.route, routeOptions, { selectedRoute: requestedRoute });
      panel.fields.route.value = requestedRoute;
      if (!routeOptions[requestedRoute]) {
        console.warn("[vibecomfy] status payload missing descriptor for requested route", {
          requestedRoute,
          routeOptions,
        });
        panel.state.routeStatus = {
          kind: ROUTE_STATUS_KIND.MALFORMED,
          requestedRoute,
          model,
        };
        panel.state.settingsMessage = "Malformed status payload; route/model controls disabled.";
      } else {
        panel.state.routeStatus = {
          kind: ROUTE_STATUS_KIND.READY,
          requestedRoute,
          model,
        };
        if (!quiet) {
          const availability = status?.provider_available === false ? "provider unavailable" : "provider ready";
          panel.state.settingsMessage = `${status?.requested_route || route} → ${status?.route || route} (${availability})`;
        }
      }
    }
    if (typeof status?.model === "string" && !panel.fields.model.value.trim()) {
      panel.fields.model.value = status.model;
    }
  } catch (e) {
    if (Number.isFinite(requestEpoch) && panel.state.statusRequestEpoch !== requestEpoch) {
      return;
    }
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
    });
    panel.fields.route.value = route;
    scheduleAgentStatusRetry(panel, route, model, { quiet: true }, deps);
  }
  if (typeof document === "undefined") {
    return;
  }
  const statusDirtySections = Array.isArray(panel?.state?.chatMessages) && panel.state.chatMessages.length
    ? [...SETTINGS_STATUS_RENDER_SECTIONS, RENDER_SECTIONS.META, RENDER_SECTIONS.THREAD]
    : SETTINGS_STATUS_RENDER_SECTIONS;
  markAgentPanelDirtyAfterCommit(panel, statusDirtySections, "status");
}
