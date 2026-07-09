import test from "node:test";
import assert from "node:assert/strict";

import {
  RENDER_SECTIONS,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

import {
  SETTINGS_STATUS_RENDER_SECTIONS,
} from "../../vibecomfy/comfy_nodes/web/panel_scheduler.js";

import {
  ROUTE_ALIASES,
  ROUTE_LABELS,
  CANONICAL_AGENT_PROVIDERS,
  ROUTE_STATUS_KIND,
  getPersistedAgentProvider,
  setPersistedAgentProvider,
  buildStatusUrl,
  buildVibeComfyInfoUrl,
  routeStatusState,
  routeOptionsFromStatus,
  getRouteOptions,
  getRouteDescriptor,
  normalizeRoutePreference,
  projectRouteStatus,
  clearAgentStatusRetry,
  scheduleAgentStatusRetry,
  populateRouteSelect,
  refreshAgentStatus,
  refreshVibeComfyInfo,
  syncChooseEngineGate,
  storeOpenRouterCredential,
  persistAgentSettings,
  testAgentSettings,
  configureAgentStatusDeps,
} from "../../vibecomfy/comfy_nodes/web/agent_status_poller.js";

// ── Global mocks ──────────────────────────────────────────────────────────

const originalConsole = globalThis.console;

let _mocksInstalled = false;

function installMocks() {
  if (_mocksInstalled) return;
  _mocksInstalled = true;

  // localStorage fake
  const store = new Map();
  globalThis.localStorage = {
    getItem(key) {
      const val = store.get(String(key));
      return val === undefined ? null : val;
    },
    setItem(key, value) {
      store.set(String(key), String(value));
    },
    removeItem(key) {
      store.delete(String(key));
    },
    _clear() {
      store.clear();
    },
    _dump() {
      return Object.fromEntries(store);
    },
  };

  // FakeElement for DOM mocks
  class FakeElement {
    constructor(tagName) {
      this.tagName = String(tagName).toUpperCase();
      this.children = [];
      this.parentNode = null;
      this.value = "";
      this.disabled = false;
      this.selected = false;
      this.title = "";
      this.textContent = "";
      this.id = "";
      this.ownerDocument = globalThis.document;
    }
    appendChild(child) {
      if (child.parentNode) child.parentNode.removeChild(child);
      child.parentNode = this;
      this.children.push(child);
      return child;
    }
    removeChild(child) {
      const idx = this.children.indexOf(child);
      if (idx >= 0) {
        this.children.splice(idx, 1);
        child.parentNode = null;
      }
      return child;
    }
  }

  globalThis.document = {
    createElement(tagName) {
      return new FakeElement(tagName);
    },
    body: new FakeElement("body"),
    head: new FakeElement("head"),
  };
  globalThis.document.body.ownerDocument = globalThis.document;

  // setTimeout/clearTimeout fakes
  const timers = [];
  globalThis.setTimeout = (fn, ms) => {
    const id = timers.length + 1;
    timers.push({ id, fn, ms });
    return id;
  };
  globalThis.clearTimeout = (id) => {
    const idx = timers.findIndex((t) => t.id === id);
    if (idx >= 0) timers.splice(idx, 1);
  };
  globalThis._getTimers = () => timers;
  globalThis._flushTimers = async () => {
    while (timers.length) {
      const batch = timers.splice(0);
      for (const t of batch) {
        t.fn();
      }
    }
    await Promise.resolve();
  };

  // console capture
  const logs = { warn: [], error: [] };
  globalThis.console = {
    ...originalConsole,
    warn: (...args) => logs.warn.push(args.map(String).join(" ")),
    error: (...args) => logs.error.push(args.map(String).join(" ")),
    _logs() { return logs; },
  };
}

installMocks();

// ── Fetch mock helpers ────────────────────────────────────────────────────

function mockFetch(handler) {
  globalThis.fetch = async (url, options) => {
    const result = handler(url, options);
    if (typeof result === "function") return result(url, options);
    if (result instanceof Error) throw result;
    return result;
  };
}

function makeFetchResponse(body, { ok = true, status = 200 } = {}) {
  let _jsonThrows = false;
  let _jsonError = null;
  return {
    ok,
    status,
    async json() {
      if (_jsonThrows) throw _jsonError || new Error("Malformed JSON");
      return JSON.parse(JSON.stringify(body));
    },
    _setJsonThrows(err) {
      _jsonThrows = true;
      _jsonError = err || new Error("Malformed JSON");
    },
  };
}

// ── Panel factory ─────────────────────────────────────────────────────────

function makeSelectElement(value) {
  const el = globalThis.document.createElement("select");
  el.value = value || "";
  return el;
}

/**
 * Build a representative panel object for tests.
 *
 * NOTES on field naming:
 *  - `fields.route` must be a DOM-like select element (has .children, .value).
 *  - `fields.model` is a plain { value } object.
 *  - `fields.apiKey` (camelCase) is a plain { value } object — matches the
 *    source code's `panel.fields.apiKey.value` read on line 602.
 */
function makePanel(overrides = {}) {
  const routeValue = (overrides.fields?.route?.value) || (typeof overrides.fields?.route === "string" ? overrides.fields.route : "auto");
  const modelValue = (overrides.fields?.model?.value) || "";

  const fields = {
    route: makeSelectElement(routeValue),
    model: { value: modelValue },
    apiKey: { value: "" },
  };

  // Apply field overrides (for example, set a different route value or apiKey)
  if (overrides.fields) {
    if (overrides.fields.route !== undefined) {
      fields.route = overrides.fields.route.children
        ? overrides.fields.route
        : makeSelectElement(String(overrides.fields.route.value || overrides.fields.route || "auto"));
    }
    if (overrides.fields.model !== undefined) {
      fields.model = typeof overrides.fields.model === "object" ? overrides.fields.model : { value: String(overrides.fields.model || "") };
    }
    if (overrides.fields.apiKey !== undefined) {
      fields.apiKey = typeof overrides.fields.apiKey === "object" ? overrides.fields.apiKey : { value: String(overrides.fields.apiKey || "") };
    }
  }

  const state = {
    routeStatus: { kind: ROUTE_STATUS_KIND.LOADING },
    statusSnapshot: null,
    statusRetry: null,
    statusRequestEpoch: 0,
    settingsMessage: "",
    settingsMessageKind: "success",
    lastAgentStatusDiagnostic: null,
    vibeComfyInfoSnapshot: null,
    vibeComfyInfoStatus: { kind: "loading" },
    vibeComfyInfoRequestEpoch: 0,
    lastVibeComfyInfoDiagnostic: null,
    providerTestInFlight: false,
    lastAutoSavedOpenRouterKey: null,
    chatMessages: [],
    chooseEngineRefresh: null,
    ...(overrides.state || {}),
  };

  return {
    fields,
    state,
    shell: overrides.shell !== undefined ? overrides.shell : {},
    ...(overrides.extra || {}),
  };
}

function makeDeps(overrides = {}) {
  return {
    renderAgentPanel: () => {},
    nextMacrotask: () => Promise.resolve(),
    markAgentPanelDirtyAfterCommit: () => {},
    SETTINGS_STATUS_RENDER_SECTIONS,
    RENDER_SECTIONS,
    syncChooseEngineGate: () => {},
    closeChooseEngineOverlay: () => {},
    openChooseEngineOverlay: () => {},
    refreshAgentStatus: async () => {},
    ...overrides,
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// Pure helpers
// ═══════════════════════════════════════════════════════════════════════════

test("buildStatusUrl — constructs URL with route and model", () => {
  assert.equal(buildStatusUrl("arnold", "default"), "/vibecomfy/agent/status?route=arnold&model=default");
  assert.equal(buildStatusUrl("openrouter", "gpt-4o"), "/vibecomfy/agent/status?route=openrouter&model=gpt-4o");
  assert.equal(buildStatusUrl("", ""), "/vibecomfy/agent/status");
  assert.equal(buildStatusUrl("anthropic", ""), "/vibecomfy/agent/status?route=anthropic");
  assert.equal(buildStatusUrl("", "claude-3"), "/vibecomfy/agent/status?model=claude-3");
});

test("buildVibeComfyInfoUrl — constructs the runtime identity endpoint URL", () => {
  assert.equal(buildVibeComfyInfoUrl(), "/vibecomfy/info");
});

test("routeStatusState — reads panel.routeStatus", () => {
  const panel = makePanel({ state: { routeStatus: { kind: ROUTE_STATUS_KIND.READY, requestedRoute: "auto" } } });
  const rs = routeStatusState(panel);
  assert.equal(rs.kind, ROUTE_STATUS_KIND.READY);
  assert.equal(rs.requestedRoute, "auto");

  assert.deepEqual(routeStatusState(null), { kind: ROUTE_STATUS_KIND.LOADING });
  assert.deepEqual(routeStatusState({}), { kind: ROUTE_STATUS_KIND.LOADING });
  assert.deepEqual(routeStatusState({ state: {} }), { kind: ROUTE_STATUS_KIND.LOADING });
});

test("routeOptionsFromStatus — extracts route_options safely", () => {
  assert.equal(routeOptionsFromStatus(null), null);
  assert.equal(routeOptionsFromStatus(undefined), null);
  assert.equal(routeOptionsFromStatus("string"), null);
  assert.equal(routeOptionsFromStatus(42), null);
  assert.equal(routeOptionsFromStatus([]), null);
  assert.equal(routeOptionsFromStatus({}), null);
  assert.equal(routeOptionsFromStatus({ route_options: [] }), null);
  assert.equal(routeOptionsFromStatus({ route_options: "string" }), null);
  assert.equal(routeOptionsFromStatus({ route_options: 42 }), null);

  const opts = { auto: { normalized_route: "arnold" } };
  assert.deepEqual(routeOptionsFromStatus({ ok: true, route_options: opts }), opts);
});

test("SETTINGS_STATUS_RENDER_SECTIONS preserves status rerender sections", () => {
  assert.deepEqual(SETTINGS_STATUS_RENDER_SECTIONS, [
    RENDER_SECTIONS.THREAD,
    RENDER_SECTIONS.SETTINGS,
    RENDER_SECTIONS.COMPOSER,
    RENDER_SECTIONS.NOTICE,
  ]);
  assert.equal(SETTINGS_STATUS_RENDER_SECTIONS.includes(RENDER_SECTIONS.DEVELOPER), false);
});

test("projectRouteStatus — projects ProviderStatus payloads to frontend RouteStatus", () => {
  const ready = projectRouteStatus({
    ok: true,
    ready: true,
    provider_available: true,
    route: "arnold",
    requested_route: "auto",
    route_options: {
      auto: { normalized_route: "arnold", available: true },
    },
  }, { route: "auto", model: "default" });
  assert.deepEqual(ready.routeStatus, {
    kind: ROUTE_STATUS_KIND.READY,
    requestedRoute: "auto",
    model: "default",
  });
  assert.equal(ready.settingsMessage, "auto → arnold (provider ready)");
  assert.equal(ready.routeOptions.auto.normalized_route, "arnold");

  const unavailable = projectRouteStatus({
    ok: true,
    ready: false,
    reason: "Provider quota exceeded",
    route_options: {
      openrouter: { normalized_route: "openrouter", available: false },
    },
  }, { route: "openrouter" });
  assert.equal(unavailable.routeStatus.kind, ROUTE_STATUS_KIND.UNAVAILABLE);
  assert.equal(unavailable.settingsMessage, "Provider quota exceeded");

  const malformed = projectRouteStatus(["not", "provider", "status"], { route: "anthropic" });
  assert.equal(malformed.routeStatus.kind, ROUTE_STATUS_KIND.MALFORMED);
  assert.equal(malformed.routeOptions, null);
  assert.equal(malformed.placeholderLabel, "Malformed status payload");

  const missingOptions = projectRouteStatus({ ok: true, ready: true }, { route: "auto" });
  assert.equal(missingOptions.routeStatus.kind, ROUTE_STATUS_KIND.MISSING_OPTIONS);
  assert.equal(missingOptions.issue, "missing_route_options");
});

test("projectRouteStatus — covers loading, malformed, missing, mismatch, unavailable, ready, and provider unavailable states", () => {
  assert.deepEqual(routeStatusState({ state: {} }), { kind: ROUTE_STATUS_KIND.LOADING });

  const malformed = projectRouteStatus(null, { route: "openrouter", model: "gpt-4o" });
  assert.equal(malformed.issue, "malformed_status");
  assert.deepEqual(malformed.routeStatus, {
    kind: ROUTE_STATUS_KIND.MALFORMED,
    requestedRoute: "openrouter",
    model: "gpt-4o",
  });
  assert.equal(malformed.routeOptions, null);
  assert.equal(malformed.selectedRoute, "openrouter");
  assert.equal(malformed.placeholderLabel, "Malformed status payload");

  const missingOptions = projectRouteStatus(
    { ok: true, ready: true, route: "openrouter", requested_route: "openrouter" },
    { route: "openrouter" },
  );
  assert.equal(missingOptions.issue, "missing_route_options");
  assert.equal(missingOptions.routeStatus.kind, ROUTE_STATUS_KIND.MISSING_OPTIONS);
  assert.equal(missingOptions.placeholderLabel, "Route options unavailable");

  const routeMismatch = projectRouteStatus({
    ok: true,
    ready: true,
    route: "arnold",
    requested_route: "anthropic",
    route_options: {
      openrouter: { normalized_route: "openrouter", available: true },
    },
  }, { route: "anthropic" });
  assert.equal(routeMismatch.issue, "missing_route_descriptor");
  assert.deepEqual(routeMismatch.routeStatus, {
    kind: ROUTE_STATUS_KIND.MALFORMED,
    requestedRoute: "anthropic",
    model: null,
  });
  assert.equal(routeMismatch.selectedRoute, "anthropic");
  assert.equal(routeMismatch.placeholderLabel, null);

  const unavailable = projectRouteStatus({
    ok: true,
    ready: false,
    reason: "Route disabled by policy",
    route: "anthropic",
    requested_route: "anthropic",
    provider_available: false,
    route_options: {
      anthropic: { normalized_route: "anthropic", available: false },
    },
  }, { route: "anthropic" });
  assert.equal(unavailable.issue, null);
  assert.deepEqual(unavailable.routeStatus, {
    kind: ROUTE_STATUS_KIND.UNAVAILABLE,
    requestedRoute: "anthropic",
    model: null,
  });
  assert.equal(unavailable.settingsMessage, "Route disabled by policy");

  const ready = projectRouteStatus({
    ok: true,
    ready: true,
    route: "openrouter",
    requested_route: "openrouter",
    provider_available: true,
    route_options: {
      openrouter: { normalized_route: "openrouter", available: true },
    },
  }, { route: "openrouter", model: "gpt-4o" });
  assert.equal(ready.issue, null);
  assert.deepEqual(ready.routeStatus, {
    kind: ROUTE_STATUS_KIND.READY,
    requestedRoute: "openrouter",
    model: "gpt-4o",
  });
  assert.equal(ready.settingsMessage, "openrouter → openrouter (provider ready)");

  const providerUnavailable = projectRouteStatus({
    ok: true,
    ready: true,
    route: "openrouter",
    requested_route: "openrouter",
    provider_available: false,
    route_options: {
      openrouter: { normalized_route: "openrouter", available: true },
    },
  }, { route: "openrouter", model: "gpt-4o" });
  assert.deepEqual(providerUnavailable.routeStatus, {
    kind: ROUTE_STATUS_KIND.READY,
    requestedRoute: "openrouter",
    model: "gpt-4o",
  });
  assert.equal(providerUnavailable.settingsMessage, "openrouter → openrouter (provider unavailable)");

  const quiet = projectRouteStatus({
    ok: true,
    ready: true,
    route: "arnold",
    requested_route: "auto",
    provider_available: true,
    route_options: {
      auto: { normalized_route: "arnold", available: true },
    },
  }, { route: "auto", quiet: true });
  assert.equal(quiet.routeStatus.kind, ROUTE_STATUS_KIND.READY);
  assert.equal(quiet.settingsMessage, null);

  const legacyDeepseek = projectRouteStatus({
    ok: true,
    ready: true,
    route: "deepseek",
    requested_route: "deepseek",
    provider_available: true,
    route_options: {
      deepseek: { normalized_route: "deepseek", available: true },
      openrouter: { normalized_route: "openrouter", available: true },
    },
  }, { route: "deepseek" });
  assert.equal(legacyDeepseek.issue, null);
  assert.deepEqual(legacyDeepseek.routeStatus, {
    kind: ROUTE_STATUS_KIND.READY,
    requestedRoute: "deepseek",
    model: null,
  });
  assert.equal(legacyDeepseek.selectedRoute, "deepseek");
});

test("transition table: route/provider projection states stay canonical", () => {
  const cases = [
    {
      name: "loading reducer state before provider payload",
      stateInput: { state: {} },
      expectedRouteStatus: { kind: ROUTE_STATUS_KIND.LOADING },
    },
    {
      name: "malformed provider payload",
      status: null,
      request: { route: "openrouter", model: "gpt-4o" },
      expectedIssue: "malformed_status",
      expectedRouteStatus: {
        kind: ROUTE_STATUS_KIND.MALFORMED,
        requestedRoute: "openrouter",
        model: "gpt-4o",
      },
      expectedPlaceholder: "Malformed status payload",
    },
    {
      name: "missing route options",
      status: { ok: true, ready: true, route: "openrouter", requested_route: "openrouter" },
      request: { route: "openrouter" },
      expectedIssue: "missing_route_options",
      expectedRouteStatus: {
        kind: ROUTE_STATUS_KIND.MISSING_OPTIONS,
        requestedRoute: "openrouter",
        model: null,
      },
      expectedPlaceholder: "Route options unavailable",
    },
    {
      name: "requested route descriptor mismatch",
      status: {
        ok: true,
        ready: true,
        route: "arnold",
        requested_route: "anthropic",
        route_options: {
          openrouter: { normalized_route: "openrouter", available: true },
        },
      },
      request: { route: "anthropic" },
      expectedIssue: "missing_route_descriptor",
      expectedRouteStatus: {
        kind: ROUTE_STATUS_KIND.MALFORMED,
        requestedRoute: "anthropic",
        model: null,
      },
    },
    {
      name: "provider route unavailable",
      status: {
        ok: true,
        ready: false,
        reason: "Route disabled by policy",
        route: "anthropic",
        requested_route: "anthropic",
        provider_available: false,
        route_options: {
          anthropic: { normalized_route: "anthropic", available: false },
        },
      },
      request: { route: "anthropic" },
      expectedIssue: null,
      expectedRouteStatus: {
        kind: ROUTE_STATUS_KIND.UNAVAILABLE,
        requestedRoute: "anthropic",
        model: null,
      },
      expectedSettingsMessage: "Route disabled by policy",
    },
    {
      name: "ready route with provider available",
      status: {
        ok: true,
        ready: true,
        route: "openrouter",
        requested_route: "openrouter",
        provider_available: true,
        route_options: {
          openrouter: { normalized_route: "openrouter", available: true },
        },
      },
      request: { route: "openrouter", model: "gpt-4o" },
      expectedIssue: null,
      expectedRouteStatus: {
        kind: ROUTE_STATUS_KIND.READY,
        requestedRoute: "openrouter",
        model: "gpt-4o",
      },
      expectedSettingsMessage: "openrouter → openrouter (provider ready)",
    },
    {
      name: "ready route with provider unavailable projects route ready but provider message unavailable",
      status: {
        ok: true,
        ready: true,
        route: "openrouter",
        requested_route: "openrouter",
        provider_available: false,
        route_options: {
          openrouter: { normalized_route: "openrouter", available: true },
        },
      },
      request: { route: "openrouter", model: "gpt-4o" },
      expectedIssue: null,
      expectedRouteStatus: {
        kind: ROUTE_STATUS_KIND.READY,
        requestedRoute: "openrouter",
        model: "gpt-4o",
      },
      expectedSettingsMessage: "openrouter → openrouter (provider unavailable)",
    },
  ];

  for (const testCase of cases) {
    const projection = testCase.stateInput
      ? { routeStatus: routeStatusState(testCase.stateInput) }
      : projectRouteStatus(testCase.status, testCase.request);

    assert.deepEqual(projection.routeStatus, testCase.expectedRouteStatus, testCase.name);
    if ("expectedIssue" in testCase) {
      assert.equal(projection.issue, testCase.expectedIssue, testCase.name);
    }
    if ("expectedPlaceholder" in testCase) {
      assert.equal(projection.placeholderLabel, testCase.expectedPlaceholder, testCase.name);
    }
    if ("expectedSettingsMessage" in testCase) {
      assert.equal(projection.settingsMessage, testCase.expectedSettingsMessage, testCase.name);
    }
  }
});

test("getPersistedAgentProvider / setPersistedAgentProvider — localStorage roundtrip", () => {
  globalThis.localStorage._clear();

  assert.equal(getPersistedAgentProvider(), null);

  setPersistedAgentProvider("deepseek");
  assert.equal(getPersistedAgentProvider(), "deepseek");

  setPersistedAgentProvider("openrouter");
  assert.equal(getPersistedAgentProvider(), "openrouter");

  setPersistedAgentProvider("anthropic");
  assert.equal(getPersistedAgentProvider(), "anthropic");

  setPersistedAgentProvider("openai-codex");
  assert.equal(getPersistedAgentProvider(), "openai-codex");

  setPersistedAgentProvider("bogus");
  assert.equal(getPersistedAgentProvider(), null);

  setPersistedAgentProvider("openrouter");
  setPersistedAgentProvider(null);
  assert.equal(getPersistedAgentProvider(), null);
});

// ═══════════════════════════════════════════════════════════════════════════
// Retry scheduling
// ═══════════════════════════════════════════════════════════════════════════

test("clearAgentStatusRetry — clears timer and state", () => {
  const panel = makePanel({
    state: { statusRetry: { route: "auto", model: "default", attempts: 2, exhausted: false, timerId: 42 } },
  });
  clearAgentStatusRetry(panel);
  assert.equal(panel.state.statusRetry, null);

  clearAgentStatusRetry(null);
  clearAgentStatusRetry({});
});

test("scheduleAgentStatusRetry — schedules retries with backoff", () => {
  const refreshes = [];
  const deps = makeDeps({ refreshAgentStatus: (p, opts) => refreshes.push({ p, opts }) });
  const panel = makePanel();

  scheduleAgentStatusRetry(panel, "auto", "default", { quiet: true }, deps);
  assert.equal(panel.state.statusRetry.attempts, 1);
  assert.equal(panel.state.statusRetry.exhausted, false);
  assert.ok(panel.state.statusRetry.timerId !== null);

  panel.state.statusRetry = { route: "auto", model: "default", attempts: 3, exhausted: false, timerId: null };
  scheduleAgentStatusRetry(panel, "auto", "default", { quiet: true }, deps);
  assert.equal(panel.state.statusRetry.attempts, 3);
  assert.equal(panel.state.statusRetry.exhausted, true);

  clearAgentStatusRetry(panel);
});

// ═══════════════════════════════════════════════════════════════════════════
// populateRouteSelect
// ═══════════════════════════════════════════════════════════════════════════

test("populateRouteSelect — populates with route options", () => {
  const selectNode = makeSelectElement("auto");
  const routeOptions = {
    auto: { normalized_route: "arnold" },
    deepseek: { browser_api_key_allowed: true },
    openrouter: { browser_api_key_allowed: true },
    anthropic: { available: true },
    "openai-codex": { available: true },
  };

  populateRouteSelect(selectNode, routeOptions, { selectedRoute: "deepseek" }, makeDeps());

  assert.deepEqual(selectNode.children.map((entry) => entry.value), [
    "auto",
    "deepseek",
    "openrouter",
    "anthropic",
    "openai-codex",
  ]);
  assert.equal(selectNode.value, "deepseek");
  assert.equal(selectNode.children[1].textContent, "deepseek");

  const emptySelect = makeSelectElement("auto");
  populateRouteSelect(emptySelect, null, { placeholderLabel: "No routes", selectedRoute: "auto" }, makeDeps());
  assert.equal(emptySelect.children.length, 1);
  assert.equal(emptySelect.children[0].disabled, true);
  assert.equal(emptySelect.children[0].textContent, "No routes");
});

// ═══════════════════════════════════════════════════════════════════════════
// storeOpenRouterCredential
// ═══════════════════════════════════════════════════════════════════════════

test("storeOpenRouterCredential — stores successfully", async () => {
  mockFetch((url, options) => {
    if (url === "/vibecomfy/agent/credentials" && options.method === "POST") {
      return makeFetchResponse({ stored: true });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const result = await storeOpenRouterCredential(panel, "sk-test-key-123", { guidance: "store it" });

  assert.equal(result.stored, true);
  assert.equal(result.message, "Stored OpenRouter API key.");
  assert.equal(panel.state.settingsMessage, "Stored OpenRouter API key.");
  assert.equal(panel.state.settingsMessageKind, "success");
  assert.equal(panel.state.lastAutoSavedOpenRouterKey, "sk-test-key-123");
});

test("storeOpenRouterCredential — handles server rejection", async () => {
  mockFetch((url, options) => {
    if (url === "/vibecomfy/agent/credentials" && options.method === "POST") {
      return makeFetchResponse({ stored: false, reason: "rate-limited" });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const result = await storeOpenRouterCredential(panel, "sk-bad-key", { guidance: "use a valid key" });

  assert.equal(result.stored, false);
  assert.equal(result.message, "rate-limited");
  assert.equal(panel.state.settingsMessageKind, "error");
});

test("storeOpenRouterCredential — handles network error", async () => {
  mockFetch(() => { throw new Error("Network failure"); });

  const panel = makePanel();
  const result = await storeOpenRouterCredential(panel, "sk-key", null);

  assert.equal(result.stored, false);
  assert.ok(result.message.includes("Credential save failed"), `got: ${result.message}`);
  assert.equal(panel.state.settingsMessageKind, "error");
});

test("storeOpenRouterCredential — handles malformed JSON in credential response", async () => {
  mockFetch((url) => {
    if (url === "/vibecomfy/agent/credentials") {
      const res = makeFetchResponse({ stored: true });
      res._setJsonThrows(new Error("Unexpected token"));
      return res;
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const result = await storeOpenRouterCredential(panel, "sk-key", null);

  assert.equal(result.stored, false);
  assert.ok(result.message.includes("Credential save failed"), `got: ${result.message}`);
  assert.equal(panel.state.settingsMessageKind, "error");
});

// ═══════════════════════════════════════════════════════════════════════════
// refreshAgentStatus — route status state transitions
// ═══════════════════════════════════════════════════════════════════════════

test("refreshAgentStatus — LOADING → READY transition", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: true,
        provider_available: true,
        route: "arnold",
        requested_route: "auto",
        model: "default",
        route_options: {
          auto: { normalized_route: "arnold", available: true },
          openrouter: { browser_api_key_allowed: true },
        },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.READY);
  assert.equal(panel.state.routeStatus.requestedRoute, "auto");
  assert.ok(panel.state.statusSnapshot, "should have statusSnapshot");
  assert.equal(panel.state.statusSnapshot.route, "arnold");
  assert.ok(panel.state.settingsMessage.includes("provider ready"), `got: ${panel.state.settingsMessage}`);
});

test("refreshAgentStatus — LOADING → UNAVAILABLE (fetch throws)", async () => {
  mockFetch(() => { throw new Error("Connection refused"); });

  const panel = makePanel();
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.UNAVAILABLE);
  assert.equal(panel.state.statusSnapshot, null);
  assert.ok(panel.state.settingsMessage.includes("Status unavailable"), `got: ${panel.state.settingsMessage}`);
  assert.ok(panel.state.statusRetry, "should schedule retry");
});

test("refreshAgentStatus — LOADING → UNAVAILABLE (HTTP error status)", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({ error: "down" }, { ok: false, status: 503 });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.UNAVAILABLE);
  assert.equal(panel.state.statusSnapshot, null);
});

test("refreshAgentStatus — LOADING → MALFORMED (JSON parse error in .json())", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      const res = makeFetchResponse({});
      res._setJsonThrows(new SyntaxError("Unexpected token '<'"));
      return res;
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MALFORMED);
  assert.equal(panel.state.statusSnapshot, null);
  assert.ok(panel.state.settingsMessage.includes("Malformed status payload"), `got: ${panel.state.settingsMessage}`);
});

test("refreshAgentStatus — LOADING → MISSING_OPTIONS (valid JSON, no route_options)", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: true,
        provider_available: true,
        route: "arnold",
        requested_route: "auto",
        model: "default",
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MISSING_OPTIONS);
  assert.equal(panel.state.routeStatus.requestedRoute, "auto");
  assert.ok(panel.state.settingsMessage.includes("missing route options"), `got: ${panel.state.settingsMessage}`);
});

test("refreshAgentStatus — LOADING → UNAVAILABLE (ready === false)", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: false,
        reason: "Provider quota exceeded",
        provider_available: false,
        route: "arnold",
        requested_route: "auto",
        model: "default",
        route_options: {
          auto: { normalized_route: "arnold", available: false },
        },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.UNAVAILABLE);
  assert.ok(panel.state.settingsMessage.includes("Provider quota exceeded"), `got: ${panel.state.settingsMessage}`);
});

test("refreshAgentStatus — LOADING → MALFORMED (status is an array, not object)", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse(["unexpected", "array"]);
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  // Note: panel.state.statusSnapshot is set BEFORE the is-object check in refreshAgentStatus,
  // so for array/null/scalar responses it will contain the non-object value rather than null.
  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MALFORMED);
  assert.ok(Array.isArray(panel.state.statusSnapshot), "statusSnapshot should hold the array value");
});

test("refreshAgentStatus — LOADING → MALFORMED (requested route missing from route_options)", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: true,
        provider_available: true,
        route: "openrouter",
        requested_route: "anthropic",
        model: "claude-3",
        route_options: {
          openrouter: { browser_api_key_allowed: true },
        },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel({ fields: { route: makeSelectElement("anthropic") } });
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MALFORMED);
  assert.ok(panel.state.settingsMessage.includes("Malformed"), `got: ${panel.state.settingsMessage}`);
});

test("refreshAgentStatus — quiet mode suppresses success message", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: true,
        provider_available: true,
        route: "arnold",
        requested_route: "auto",
        model: "default",
        route_options: {
          auto: { normalized_route: "arnold", available: true },
        },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  panel.state.settingsMessage = "";
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: true }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.READY);
  assert.equal(panel.state.settingsMessage, "");
});

test("refreshAgentStatus — stale epoch prevents state overwrite", async () => {
  let resolveJson;
  const jsonPromise = new Promise((r) => { resolveJson = r; });

  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return {
        ok: true,
        status: 200,
        async json() {
          await jsonPromise;
          return { ok: true, ready: true, route: "arnold", route_options: { auto: { normalized_route: "arnold" } } };
        },
      };
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  panel.state.routeStatus = { kind: ROUTE_STATUS_KIND.LOADING };
  const deps = makeDeps();

  const refreshPromise = refreshAgentStatus(panel, {}, deps);

  panel.state.statusRequestEpoch = 999;

  resolveJson({ ok: true, ready: true, route: "arnold", route_options: { auto: { normalized_route: "arnold" } } });
  await refreshPromise;

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.LOADING);
});

// ═══════════════════════════════════════════════════════════════════════════
// persistAgentSettings
// ═══════════════════════════════════════════════════════════════════════════

test("persistAgentSettings — persists when READY", async () => {
  globalThis.localStorage._clear();

  const panel = makePanel({
    fields: { route: makeSelectElement("openrouter"), model: { value: "gpt-4o" } },
    state: {
      routeStatus: { kind: ROUTE_STATUS_KIND.READY, requestedRoute: "openrouter", model: "gpt-4o" },
      statusSnapshot: {
        ok: true, route: "openrouter",
        route_options: { openrouter: { normalized_route: "openrouter", browser_api_key_allowed: true } },
      },
    },
  });

  let refreshCalled = false;
  const deps = makeDeps({ refreshAgentStatus: async () => { refreshCalled = true; } });

  mockFetch(() => makeFetchResponse({ error: "unexpected" }, { status: 404 }));

  await persistAgentSettings(panel, { includeCredential: false }, deps);

  assert.equal(panel.state.settingsMessage, "✓ Saved openrouter / gpt-4o.");
  assert.equal(panel.state.settingsMessageKind, "success");
  assert.equal(getPersistedAgentProvider(), "openrouter");
  assert.equal(refreshCalled, true);
});

test("persistAgentSettings — blocks when routeStatus is not READY", async () => {
  const panel = makePanel({
    fields: { route: makeSelectElement("openrouter") },
    state: { routeStatus: { kind: ROUTE_STATUS_KIND.LOADING } },
  });

  const deps = makeDeps();
  await persistAgentSettings(panel, {}, deps);

  assert.equal(panel.state.settingsMessageKind, "error");
  assert.ok(panel.state.settingsMessage.includes("unavailable until"), `got: ${panel.state.settingsMessage}`);
});

test("persistAgentSettings — persists with credential when includeCredential=true", async () => {
  globalThis.localStorage._clear();

  const panel = makePanel({
    fields: { route: makeSelectElement("openrouter"), model: { value: "gpt-4o" }, apiKey: { value: "sk-new-key" } },
    state: {
      routeStatus: { kind: ROUTE_STATUS_KIND.READY, requestedRoute: "openrouter" },
      statusSnapshot: {
        ok: true, route: "openrouter",
        route_options: { openrouter: { normalized_route: "openrouter", browser_api_key_allowed: true } },
      },
    },
  });

  let refreshCalled = false;
  const deps = makeDeps({ refreshAgentStatus: async () => { refreshCalled = true; } });

  mockFetch((url, options) => {
    if (url === "/vibecomfy/agent/credentials" && options.method === "POST") {
      return makeFetchResponse({ stored: true });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  await persistAgentSettings(panel, { includeCredential: true }, deps);

  assert.equal(getPersistedAgentProvider(), "openrouter");
  assert.equal(panel.state.lastAutoSavedOpenRouterKey, "sk-new-key");
  assert.ok(panel.state.settingsMessage.includes("Stored OpenRouter API key"), `got: ${panel.state.settingsMessage}`);
});

test("persistAgentSettings — does not post browser credential for routes that reject browser keys", async () => {
  globalThis.localStorage._clear();

  const panel = makePanel({
    fields: { route: makeSelectElement("openai-codex"), model: { value: "" }, apiKey: { value: "sk-should-not-post" } },
    state: {
      routeStatus: { kind: ROUTE_STATUS_KIND.READY, requestedRoute: "openai-codex" },
      statusSnapshot: {
        ok: true,
        route: "arnold",
        requested_route: "openai-codex",
        route_options: {
          "openai-codex": {
            normalized_route: "arnold",
            browser_api_key_allowed: false,
            guidance: "Browser keys are not accepted.",
          },
        },
      },
    },
  });

  let posted = false;
  const deps = makeDeps({
    refreshAgentStatus: async () => {},
    clearCredentialInput: (p) => { p.fields.apiKey.value = ""; },
  });

  mockFetch((url) => {
    if (url === "/vibecomfy/agent/credentials") posted = true;
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  await persistAgentSettings(panel, { includeCredential: true }, deps);

  assert.equal(posted, false);
  assert.equal(panel.fields.apiKey.value, "");
  assert.equal(panel.state.settingsMessageKind, "error");
  assert.match(panel.state.settingsMessage, /Browser keys are not accepted/);
});

// ═══════════════════════════════════════════════════════════════════════════
// testAgentSettings
// ═══════════════════════════════════════════════════════════════════════════

test("testAgentSettings — reports success when provider available", async () => {
  const panel = makePanel({
    fields: { route: makeSelectElement("openrouter"), model: { value: "gpt-4o" } },
  });

  const deps = makeDeps({
    refreshAgentStatus: async (p) => {
      p.state.routeStatus = { kind: ROUTE_STATUS_KIND.READY, requestedRoute: "openrouter", model: "gpt-4o" };
      p.state.statusSnapshot = {
        ok: true, route: "openrouter", requested_route: "openrouter",
        model: "gpt-4o", provider_available: true,
        route_metadata: { normalized_route: "openrouter" },
      };
    },
  });

  await testAgentSettings(panel, deps);

  assert.equal(panel.state.providerTestInFlight, false);
  assert.equal(panel.state.settingsMessageKind, "success");
  assert.ok(panel.state.settingsMessage.includes("Provider test passed"), `got: ${panel.state.settingsMessage}`);
});

test("testAgentSettings — reports failure when provider unavailable", async () => {
  const panel = makePanel({
    fields: { route: makeSelectElement("openrouter"), model: { value: "gpt-4o" } },
  });

  const deps = makeDeps({
    refreshAgentStatus: async (p) => {
      p.state.routeStatus = { kind: ROUTE_STATUS_KIND.READY, requestedRoute: "openrouter" };
      p.state.statusSnapshot = { ok: true, route: "openrouter", provider_available: false };
    },
  });

  await testAgentSettings(panel, deps);

  assert.equal(panel.state.settingsMessageKind, "error");
  assert.ok(panel.state.settingsMessage.includes("Provider test failed"), `got: ${panel.state.settingsMessage}`);
});

test("testAgentSettings — no-op on null panel", async () => {
  await testAgentSettings(null, makeDeps());
});

// ═══════════════════════════════════════════════════════════════════════════
// syncChooseEngineGate
// ═══════════════════════════════════════════════════════════════════════════

test("syncChooseEngineGate — closes overlay when persisted provider exists", () => {
  globalThis.localStorage._clear();
  setPersistedAgentProvider("openrouter");

  let closeCalled = false;
  let openCalled = false;
  const deps = makeDeps({
    closeChooseEngineOverlay: () => { closeCalled = true; },
    openChooseEngineOverlay: () => { openCalled = true; },
  });

  const panel = makePanel({ shell: {} });
  syncChooseEngineGate(panel, deps);

  assert.equal(closeCalled, true);
  assert.equal(openCalled, false);
});

test("syncChooseEngineGate — closes overlay when ready provider found via status", () => {
  globalThis.localStorage._clear();

  let closeCalled = false;
  const deps = makeDeps({
    closeChooseEngineOverlay: () => { closeCalled = true; },
  });

  const panel = makePanel({
    shell: {},
    state: {
      routeStatus: { kind: ROUTE_STATUS_KIND.READY },
      statusSnapshot: {
        ok: true, route: "openrouter", provider_available: true,
        credential_presence: { deepseek_api_key: true },
        route_options: { openrouter: { normalized_route: "openrouter" } },
      },
    },
  });

  syncChooseEngineGate(panel, deps);

  assert.equal(closeCalled, true);
  assert.equal(getPersistedAgentProvider(), "openrouter");
  assert.equal(panel.fields.route.value, "openrouter");
  assert.deepEqual(panel.state.routeStatus, {
    kind: ROUTE_STATUS_KIND.READY,
    requestedRoute: "openrouter",
    model: null,
  });
  assert.equal(panel.state.settingsMessage, "openrouter → openrouter (provider ready)");
  assert.equal(panel.state.settingsMessageKind, "success");
});

test("syncChooseEngineGate — auto-selects DeepSeek provider when status has DeepSeek credential", () => {
  globalThis.localStorage._clear();

  let closeCalled = false;
  const panel = makePanel({
    shell: {},
    fields: { route: makeSelectElement("auto") },
    state: {
      routeStatus: { kind: ROUTE_STATUS_KIND.READY },
      statusSnapshot: {
        ok: true,
        route: "deepseek",
        requested_route: "deepseek",
        provider_available: true,
        credential_presence: { deepseek_api_key: true },
        route_options: {
          deepseek: { normalized_route: "deepseek", available: true },
          openrouter: { normalized_route: "openrouter", available: true },
        },
      },
    },
  });

  syncChooseEngineGate(panel, makeDeps({
    closeChooseEngineOverlay: () => { closeCalled = true; },
  }));

  assert.equal(closeCalled, true);
  assert.equal(getPersistedAgentProvider(), "deepseek");
  assert.equal(panel.fields.route.value, "deepseek");
  assert.deepEqual(panel.state.routeStatus, {
    kind: ROUTE_STATUS_KIND.READY,
    requestedRoute: "deepseek",
    model: null,
  });
  assert.equal(panel.state.settingsMessage, "deepseek → deepseek (provider ready)");
  assert.equal(panel.state.settingsMessageKind, "success");
});

test("syncChooseEngineGate — opens overlay when status not loading and no provider", () => {
  globalThis.localStorage._clear();

  let openCalled = false;
  const deps = makeDeps({
    openChooseEngineOverlay: () => { openCalled = true; },
  });

  const panel = makePanel({
    shell: {},
    state: { routeStatus: { kind: ROUTE_STATUS_KIND.UNAVAILABLE }, statusSnapshot: null },
  });

  syncChooseEngineGate(panel, deps);

  assert.equal(openCalled, true);
});

test("syncChooseEngineGate — no-op when no shell", () => {
  globalThis.localStorage._clear();

  let openCalled = false;
  const deps = makeDeps({ openChooseEngineOverlay: () => { openCalled = true; } });
  const panel = makePanel({ shell: null, state: { routeStatus: { kind: ROUTE_STATUS_KIND.UNAVAILABLE } } });

  syncChooseEngineGate(panel, deps);
  assert.equal(openCalled, false);
});

// ═══════════════════════════════════════════════════════════════════════════
// configureAgentStatusDeps
// ═══════════════════════════════════════════════════════════════════════════

test("configureAgentStatusDeps — returns all expected keys", () => {
  const configured = configureAgentStatusDeps(makeDeps());

  const expected = [
    "refreshAgentStatus", "refreshVibeComfyInfo", "routeStatusState", "populateRouteSelect",
    "persistAgentSettings", "storeOpenRouterCredential", "testAgentSettings",
    "syncChooseEngineGate", "scheduleAgentStatusRetry", "clearAgentStatusRetry",
    "buildStatusUrl", "buildVibeComfyInfoUrl", "routeOptionsFromStatus", "getRouteOptions", "getRouteDescriptor", "ROUTE_STATUS_KIND",
    "getPersistedAgentProvider", "setPersistedAgentProvider",
  ];

  for (const key of expected) {
    assert.ok(key in configured, `missing key: "${key}"`);
  }
  assert.equal(typeof configured.refreshAgentStatus, "function");
  assert.equal(typeof configured.refreshVibeComfyInfo, "function");
  assert.equal(configured.ROUTE_STATUS_KIND, ROUTE_STATUS_KIND);
});

// ═══════════════════════════════════════════════════════════════════════════
// Malformed / invalid-contract fetch behavior (distinct from fixture shape)
// ═══════════════════════════════════════════════════════════════════════════

test("refreshAgentStatus — malformed JSON: HTML error page instead of JSON", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return {
        ok: true,
        status: 200,
        async json() { throw new SyntaxError("Unexpected token '<', \"<!DOCTYPE \"... is not valid JSON"); },
      };
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MALFORMED);
  assert.ok(panel.state.lastAgentStatusDiagnostic, "should capture diagnostic");
  assert.equal(panel.state.lastAgentStatusDiagnostic.ok, false);
  assert.ok(
    panel.state.lastAgentStatusDiagnostic.error.includes("Malformed JSON"),
    `got: ${panel.state.lastAgentStatusDiagnostic.error}`,
  );
});

test("refreshAgentStatus — invalid contract: status body is a string", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse("just a string, not an object");
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  await refreshAgentStatus(panel, {}, makeDeps());

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MALFORMED);
});

test("refreshAgentStatus — invalid contract: status body is a number", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse(42);
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  await refreshAgentStatus(panel, {}, makeDeps());

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MALFORMED);
});

test("refreshAgentStatus — invalid contract: null status body", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse(null);
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  await refreshAgentStatus(panel, {}, makeDeps());

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MALFORMED);
});

test("refreshAgentStatus — valid JSON, completely wrong contract shape (no route_options, no ok)", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        data: { items: [1, 2, 3] },
        meta: { page: 1 },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  await refreshAgentStatus(panel, {}, makeDeps());

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MISSING_OPTIONS);
});

test("refreshAgentStatus — route_options is a string (not an object)", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true, ready: true, route: "arnold",
        route_options: "should-be-object",
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  await refreshAgentStatus(panel, {}, makeDeps());

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MISSING_OPTIONS);
});

test("refreshAgentStatus — route_options is an array (not an object)", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true, ready: true, route: "arnold",
        route_options: [{ route: "auto" }, { route: "openrouter" }],
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  await refreshAgentStatus(panel, {}, makeDeps());

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MISSING_OPTIONS);
});

// ═══════════════════════════════════════════════════════════════════════════
// Pre-migration parity: route/provider normalization (T2)
// ═══════════════════════════════════════════════════════════════════════════

test("route/provider owner exports preserve DeepSeek as a distinct route", () => {
  globalThis.localStorage._clear();

  assert.equal(ROUTE_ALIASES.deepseek, "deepseek");
  assert.equal(ROUTE_LABELS.deepseek, "deepseek");
  assert.equal(CANONICAL_AGENT_PROVIDERS.has("deepseek"), true);
  assert.equal(normalizeRoutePreference("deepseek"), "deepseek");
  assert.equal(normalizeRoutePreference("unknown-route"), "deepseek");

  assert.equal(getRouteOptions(makePanel()), null);
  const panel = makePanel({
    fields: { route: makeSelectElement("deepseek") },
    state: {
      statusSnapshot: {
        ok: true,
        route_options: {
          deepseek: {
            requested_route: "deepseek",
            normalized_route: "deepseek",
            browser_api_key_allowed: true,
            guidance: "Paste a DeepSeek key.",
          },
          openrouter: {
            requested_route: "openrouter",
            normalized_route: "openrouter",
            browser_api_key_allowed: true,
          },
        },
      },
    },
  });
  assert.equal(getRouteOptions(panel), panel.state.statusSnapshot.route_options);
  assert.deepEqual(getRouteDescriptor(panel, "deepseek"), panel.state.statusSnapshot.route_options.deepseek);

  // Canonical providers stay as-is; DeepSeek remains a valid persisted provider.
  setPersistedAgentProvider("deepseek");
  assert.equal(getPersistedAgentProvider(), "deepseek");
  setPersistedAgentProvider("openrouter");
  assert.equal(getPersistedAgentProvider(), "openrouter");
  setPersistedAgentProvider("anthropic");
  assert.equal(getPersistedAgentProvider(), "anthropic");
  setPersistedAgentProvider("openai-codex");
  assert.equal(getPersistedAgentProvider(), "openai-codex");

  // claude and codex are NOT remapped by the persistence getter — they are not
  // persisted provider names. These aliases are handled by normalizeRoutePreference()
  // during polling, not during persistence read-back.
  setPersistedAgentProvider("claude");
  assert.equal(getPersistedAgentProvider(), null, "claude is not a canonical provider");
  setPersistedAgentProvider("codex");
  assert.equal(getPersistedAgentProvider(), null, "codex is not a canonical provider");

  // Unknown providers return null
  setPersistedAgentProvider("unknown");
  assert.equal(getPersistedAgentProvider(), null);
  setPersistedAgentProvider("");
  assert.equal(getPersistedAgentProvider(), null);
});

test("refreshAgentStatus — single fetch path: exactly one /vibecomfy/agent/status request per invocation", async () => {
  let fetchCalls = 0;
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      fetchCalls += 1;
      return makeFetchResponse({
        ok: true,
        ready: true,
        provider_available: true,
        route: "openrouter",
        requested_route: "openrouter",
        model: "gpt-4o",
        route_options: {
          openrouter: { normalized_route: "openrouter", available: true, browser_api_key_allowed: true },
          deepseek: { normalized_route: "deepseek", available: true },
        },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel({ fields: { route: makeSelectElement("openrouter"), model: { value: "gpt-4o" } } });
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: true }, deps);

  assert.equal(fetchCalls, 1, "refreshAgentStatus must issue exactly one status fetch");
  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.READY);
  assert.equal(panel.state.routeStatus.requestedRoute, "openrouter");
  assert.ok(panel.state.statusSnapshot, "should have statusSnapshot after single fetch");
});

test("refreshAgentStatus — disables route/model controls synchronously before status fetch", async () => {
  let fetchCalled = false;
  let releaseMacrotask;
  const macrotask = new Promise((resolve) => { releaseMacrotask = resolve; });
  const renderCalls = [];

  mockFetch((url) => {
    fetchCalled = true;
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: true,
        provider_available: true,
        route: "openrouter",
        requested_route: "openrouter",
        route_options: {
          openrouter: { normalized_route: "openrouter", available: true },
        },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel({
    fields: {
      route: makeSelectElement("openrouter"),
      model: { value: "gpt-4o", disabled: false },
    },
  });
  panel.fields.route.disabled = false;
  const deps = makeDeps({
    nextMacrotask: () => macrotask,
    renderAgentPanel: (_panel, opts) => {
      renderCalls.push({
        routeDisabled: _panel.fields.route.disabled,
        modelDisabled: _panel.fields.model.disabled,
        dirtySections: opts?.dirtySections,
      });
    },
  });

  const refreshPromise = refreshAgentStatus(panel, { quiet: true }, deps);

  assert.equal(panel.fields.route.disabled, true);
  assert.equal(panel.fields.model.disabled, true);
  assert.equal(fetchCalled, false, "fetch should wait until after the initial loading render yields");
  assert.deepEqual(renderCalls, [{
    routeDisabled: true,
    modelDisabled: true,
    dirtySections: SETTINGS_STATUS_RENDER_SECTIONS,
  }]);

  releaseMacrotask();
  await refreshPromise;
  assert.equal(fetchCalled, true);
});

test("refreshAgentStatus — invalidates status sections and active transcript surfaces after fetch", async () => {
  const markCalls = [];
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: true,
        provider_available: true,
        route: "openrouter",
        requested_route: "openrouter",
        route_options: {
          openrouter: { normalized_route: "openrouter", available: true },
        },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel({
    fields: { route: makeSelectElement("openrouter") },
    state: { chatMessages: [{ role: "assistant", content: "prior message" }] },
  });
  await refreshAgentStatus(panel, { quiet: true }, makeDeps({
    markAgentPanelDirtyAfterCommit: (_panel, sections, commitKind) => {
      markCalls.push({ sections, commitKind });
    },
  }));

  assert.deepEqual(markCalls, [{
    sections: [...SETTINGS_STATUS_RENDER_SECTIONS, RENDER_SECTIONS.META, RENDER_SECTIONS.THREAD],
    commitKind: "status",
  }]);
});

test("refreshAgentStatus — status readiness coupled to panel UI state (routeStatus, settingsMessage, statusSnapshot)", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: true,
        provider_available: true,
        route: "arnold",
        requested_route: "anthropic",
        model: "claude-3",
        route_options: {
          anthropic: { normalized_route: "arnold", available: true, browser_api_key_allowed: false },
          openrouter: { normalized_route: "openrouter", available: true, browser_api_key_allowed: true },
        },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel({ fields: { route: makeSelectElement("anthropic"), model: { value: "claude-3" } } });
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  // Status readiness is reflected in panel.state
  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.READY);
  assert.equal(panel.state.routeStatus.requestedRoute, "anthropic");
  assert.equal(panel.state.routeStatus.model, "claude-3");

  // settingsMessage carries the resolved route
  assert.ok(
    panel.state.settingsMessage.includes("anthropic → arnold"),
    `settingsMessage should reflect route resolution, got: ${panel.state.settingsMessage}`,
  );
  assert.ok(
    panel.state.settingsMessage.includes("provider ready"),
    `settingsMessage should include readiness, got: ${panel.state.settingsMessage}`,
  );

  // statusSnapshot holds the raw payload
  assert.ok(panel.state.statusSnapshot, "statusSnapshot should be populated");
  assert.equal(panel.state.statusSnapshot.route, "arnold");
  assert.equal(panel.state.statusSnapshot.requested_route, "anthropic");

  // Route select should be populated with available routes
  assert.ok(panel.fields.route.children.length >= 2, "route select should have multiple options");
  assert.equal(panel.fields.route.value, "anthropic");
});

test("refreshAgentStatus — malformed status text propagated to settingsMessage and routeStatus", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: true,
        provider_available: true,
        route: "arnold",
        requested_route: "auto",
        // Missing route_options — will trigger MISSING_OPTIONS
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.MISSING_OPTIONS);
  assert.ok(
    panel.state.settingsMessage.includes("missing route options"),
    `settingsMessage should mention missing route options, got: ${panel.state.settingsMessage}`,
  );
});

test("refreshAgentStatus — unavailable status text propagated to settingsMessage", async () => {
  mockFetch((url) => {
    if (url.startsWith("/vibecomfy/agent/status")) {
      return makeFetchResponse({
        ok: true,
        ready: false,
        reason: "All providers exhausted. Check your API keys.",
        provider_available: false,
        route: "openrouter",
        requested_route: "openrouter",
        route_options: {
          openrouter: { normalized_route: "openrouter", available: false },
        },
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel({ fields: { route: makeSelectElement("openrouter") } });
  const deps = makeDeps();

  await refreshAgentStatus(panel, { quiet: false }, deps);

  assert.equal(panel.state.routeStatus.kind, ROUTE_STATUS_KIND.UNAVAILABLE);
  assert.ok(
    panel.state.settingsMessage.includes("All providers exhausted"),
    `settingsMessage should carry the reason, got: ${panel.state.settingsMessage}`,
  );
});

test("refreshVibeComfyInfo — fetches runtime identity independently of route status and rerenders developer diagnostics", async () => {
  const markCalls = [];
  mockFetch((url) => {
    if (url === "/vibecomfy/info") {
      return makeFetchResponse({
        git_sha: "abc123",
        git_branch: "main",
        git_dirty: true,
        web_source_hash: "feedface",
        served_web_path: "/srv/vibecomfy/web",
        start_time_utc: "2026-07-09T16:10:00Z",
        uptime_seconds: 42.5,
      });
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel({
    state: {
      routeStatus: { kind: ROUTE_STATUS_KIND.UNAVAILABLE, requestedRoute: "auto", model: null },
      settingsMessage: "Status unavailable: Error: backend down",
    },
  });

  await refreshVibeComfyInfo(panel, makeDeps({
    markAgentPanelDirtyAfterCommit: (_panel, sections, commitKind) => {
      markCalls.push({ sections, commitKind });
    },
  }));

  assert.equal(panel.state.vibeComfyInfoStatus.kind, "ready");
  assert.equal(panel.state.vibeComfyInfoSnapshot.git_sha, "abc123");
  assert.equal(panel.state.vibeComfyInfoSnapshot.web_source_hash, "feedface");
  assert.equal(panel.state.settingsMessage, "Status unavailable: Error: backend down");
  assert.deepEqual(markCalls, [{
    sections: [RENDER_SECTIONS.DEVELOPER],
    commitKind: "info",
  }]);
});

test("refreshVibeComfyInfo — malformed payload stores diagnostic and clears the snapshot", async () => {
  mockFetch((url) => {
    if (url === "/vibecomfy/info") {
      return makeFetchResponse("not-an-object");
    }
    return makeFetchResponse({ error: "unexpected" }, { status: 404 });
  });

  const panel = makePanel();
  await refreshVibeComfyInfo(panel, makeDeps());

  assert.equal(panel.state.vibeComfyInfoStatus.kind, "malformed");
  assert.equal(panel.state.vibeComfyInfoSnapshot, null);
  assert.ok(panel.state.lastVibeComfyInfoDiagnostic, "should capture info diagnostic");
  assert.ok(
    panel.state.lastVibeComfyInfoDiagnostic.error.includes("expected JSON object"),
    `got: ${panel.state.lastVibeComfyInfoDiagnostic.error}`,
  );
});

test("refreshVibeComfyInfo — unavailable responses keep an error diagnostic on the owned state surface", async () => {
  mockFetch(() => {
    throw new Error("Connection refused");
  });

  const panel = makePanel();
  await refreshVibeComfyInfo(panel, makeDeps());

  assert.equal(panel.state.vibeComfyInfoStatus.kind, "unavailable");
  assert.equal(panel.state.vibeComfyInfoSnapshot, null);
  assert.ok(panel.state.lastVibeComfyInfoDiagnostic, "should capture info diagnostic");
  assert.ok(
    panel.state.lastVibeComfyInfoDiagnostic.error.includes("Connection refused"),
    `got: ${panel.state.lastVibeComfyInfoDiagnostic.error}`,
  );
});
