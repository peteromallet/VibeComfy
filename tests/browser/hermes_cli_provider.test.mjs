import test from "node:test";
import assert from "node:assert/strict";

import { createSubmitFlow } from "../../vibecomfy/comfy_nodes/web/agent_submit_flow.js";
import {
  CANONICAL_AGENT_PROVIDERS,
  ROUTE_ALIASES,
  ROUTE_LABELS,
  getPersistedAgentProvider,
  normalizeRoutePreference,
  setPersistedAgentProvider,
} from "../../vibecomfy/comfy_nodes/web/agent_status_poller.js";
import { createBrowserHarness } from "./harness.mjs";

const PIPELINE_MODE_KEY = "vibecomfy_agent_pipeline_mode";
const PROVIDER_KEY = "vibecomfy_agent_provider";
const HERMES_DESCRIPTION =
  "Uses your locally installed Hermes CLI and its configured default model.";

const READY_AUTO_STATUS = {
  "/vibecomfy/agent/status?route=auto": {
    status: 200,
    body: {
      ok: true,
      ready: true,
      provider_available: true,
      route: "auto",
      requested_route: "auto",
      route_options: {
        auto: {
          requested_route: "auto",
          normalized_route: "auto",
          browser_api_key_allowed: false,
        },
      },
    },
  },
};

const READY_HERMES_STATUS = {
  "/vibecomfy/agent/status?route=hermes-cli": {
    status: 200,
    body: {
      ok: true,
      ready: true,
      provider_available: true,
      route: "hermes-cli",
      model: "stale-model-from-another-provider",
      requested_route: "hermes-cli",
      route_options: {
        "hermes-cli": {
          requested_route: "hermes-cli",
          normalized_route: "hermes-cli",
          browser_api_key_allowed: false,
        },
      },
    },
  },
};

function waitFor(predicate, timeoutMs = 3000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      if (predicate()) return resolve();
      if (Date.now() - started > timeoutMs) return reject(new Error("timed out"));
      setTimeout(poll, 5);
    };
    poll();
  });
}

function findButton(harness, label) {
  return harness.document.body.querySelectorAll(
    (node) => node.tagName === "BUTTON" && node.textContent === label,
  )[0] ?? null;
}

function findCard(harness, label) {
  const labelNode = harness.document.body.querySelectorAll(
    (node) => node.tagName === "DIV" && node.textContent === label,
  )[0];
  return labelNode?.parentNode ?? null;
}

function installStorage() {
  const values = new Map();
  globalThis.localStorage = {
    clear: () => values.clear(),
    getItem: (key) => values.get(String(key)) ?? null,
    removeItem: (key) => values.delete(String(key)),
    setItem: (key, value) => values.set(String(key), String(value)),
  };
}

test("Hermes CLI is a canonical browser provider and its short alias normalizes at the boundary", () => {
  installStorage();

  assert.equal(ROUTE_ALIASES.hermes, "hermes-cli");
  assert.equal(ROUTE_ALIASES["hermes-cli"], "hermes-cli");
  assert.equal(ROUTE_LABELS["hermes-cli"], "Hermes");
  assert.equal(CANONICAL_AGENT_PROVIDERS.has("hermes-cli"), true);
  assert.equal(normalizeRoutePreference("hermes"), "hermes-cli");
  assert.equal(normalizeRoutePreference("hermes-cli"), "hermes-cli");

  setPersistedAgentProvider("hermes-cli");
  assert.equal(getPersistedAgentProvider(), "hermes-cli");
});

test("Hermes CLI submit body preserves the canonical route and uses the Hermes profile with no model override", () => {
  const flow = createSubmitFlow({
    submitWatchdogDepsState: {},
    submitActivityByPanel: new WeakMap(),
    pendingTransactionSnapshotByPanel: new WeakMap(),
    readOnDemandSchemasSetting: () => false,
    api: { clientId: "browser-client" },
  });
  const body = flow.buildSubmitBody(
    {
      graph: { nodes: [], links: [] },
      workflowId: "workflow",
      route: "hermes-cli",
      pipelineMode: "staged",
      graphHash: "full",
      structuralHash: "structural",
      liveCanvasToken: "live:1",
      idempotencyKey: "idempotent",
    },
    "edit the workflow",
    { state: {} },
  );

  assert.equal(body.route, "hermes-cli");
  assert.equal(body.profile, "hermes");
  assert.equal(body.model, undefined, "the locally configured Hermes default model is not overridden");
});

test("Choose Your Engine offers a credential-free Hermes card and persists hermes-cli", async () => {
  globalThis.localStorage?.clear?.();
  const harness = await createBrowserHarness({
    responses: {
      ...READY_AUTO_STATUS,
      ...READY_HERMES_STATUS,
    },
    seedPipelineMode: false,
  });

  try {
    globalThis.localStorage.setItem(PIPELINE_MODE_KEY, "staged");
    await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => Boolean(findButton(harness, "Confirm Selection")));

    const hermesCard = findCard(harness, "Hermes");
    assert.ok(hermesCard, "the fourth engine card is rendered");
    assert.equal(hermesCard.children[1].textContent, HERMES_DESCRIPTION);
    assert.equal(
      hermesCard.children[2].children.length,
      0,
      "the Hermes card has no API-key or other credential controls",
    );

    hermesCard.click();
    const confirm = findButton(harness, "Confirm Selection");
    assert.equal(confirm.disabled, false, "Hermes can be confirmed without an API key");
    await confirm.click();

    assert.equal(globalThis.localStorage.getItem(PROVIDER_KEY), "hermes-cli");
    await waitFor(() => harness.requests.some(
      (entry) => entry.url === "/vibecomfy/agent/status?route=hermes-cli",
    ));
  } finally {
    globalThis.localStorage?.removeItem(PROVIDER_KEY);
    globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);
    await harness.dispose();
  }
});
