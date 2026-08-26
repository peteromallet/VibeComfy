import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  createSubmitFlow,
  matchPipelineMode,
  normalizePipelineMode,
} from "../../vibecomfy/comfy_nodes/web/agent_submit_flow.js";
import { createBrowserHarness } from "./harness.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WEB_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");
const PIPELINE_MODE_KEY = "vibecomfy_agent_pipeline_mode";
const PROVIDER_KEY = "vibecomfy_agent_provider";

// Single source constants, duplicated here VERBATIM so any drift in the UI
// strings breaks these assertions (copy-parity is the contract).
const COPY_STAGED =
  "Structures each request into multiple steps (Decide → Research → Execute → Review). Works better with smaller models.";
const COPY_THREADED =
  "One instance gets all tools in one pass. Works better with larger models.";
const PLACEHOLDER_TEXT = "Choose agent mode…";
const MODE_HEADING = "How should the agent work?";
const TILE_LABEL_STAGED = "Staged pipeline";
const TILE_LABEL_THREADED = "Single-thread";
const CONTINUE_LABEL = "Continue";

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

const READY_AUTO_STATUS = {
  "/vibecomfy/agent/status?route=auto": {
    status: 200,
    body: {
      ok: true,
      provider_available: true,
      route: "arnold",
      requested_route: "auto",
      route_options: {
        auto: {
          requested_route: "auto",
          normalized_route: "arnold",
          browser_api_key_allowed: false,
        },
      },
    },
  },
};

const READY_CODEX_STATUS = {
  "/vibecomfy/agent/status?route=openai-codex": {
    status: 200,
    body: {
      ok: true,
      provider_available: true,
      route: "openai-codex",
      requested_route: "openai-codex",
      route_options: {
        "openai-codex": {
          requested_route: "openai-codex",
          normalized_route: "arnold",
          browser_api_key_allowed: false,
        },
      },
    },
  },
};

function okSubmitResponse(captureInto) {
  return async ({ options }) => {
    if (captureInto) captureInto.push(JSON.parse(options.body));
    return {
      status: 200,
      body: {
        ok: true,
        session_id: "pipeline-session",
        turn_id: "0000",
        baseline_turn_id: null,
        outcome: { kind: "noop", reason: "done" },
        graph_unchanged: true,
        canvas_apply_allowed: false,
        apply_allowed: false,
        queue_allowed: false,
        message: "done",
      },
    };
  };
}

function findButton(harness, label) {
  const matches = harness.document.body.querySelectorAll(
    (node) => node.tagName === "BUTTON" && node.textContent === label,
  );
  return matches[0] ?? null;
}

// Tiles are composite cards whose textContent concatenates label + copy;
// locate the exact-text label child and return the clickable parent card.
function findTileByLabel(harness, label) {
  const nodes = harness.document.body.querySelectorAll(
    (node) => node.tagName === "DIV" && node.textContent === label,
  );
  const labelNode = nodes[0];
  return labelNode?.parentNode ?? null;
}

async function source(name) {
  return readFile(path.join(WEB_ROOT, name), "utf8");
}

function functionBody(text, name) {
  const start = text.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} should exist`);
  let depth = 0;
  let opened = false;
  for (let i = start; i < text.length; i += 1) {
    const ch = text[i];
    if (ch === "{") {
      depth += 1;
      opened = true;
    } else if (ch === "}") {
      depth -= 1;
      if (opened && depth === 0) {
        return text.slice(start, i + 1);
      }
    }
  }
  assert.fail(`${name} body never closed`);
}

async function bootPanel(harness) {
  await harness.loadExtension();
  await harness.setup();
  await harness.invokeCommand("VibeComfy.AgentEdit");
  await waitFor(() => harness.requests.some((entry) => entry.url === "/vibecomfy/agent/status?route=auto"));
}

// ── normalizer boundary semantics (A6: named flips) ─────────────────────────

test("browser mode normalizer keeps aliases at the boundary", () => {
  assert.equal(normalizePipelineMode(undefined), "staged");
  assert.equal(normalizePipelineMode("full"), "staged");
  assert.equal(normalizePipelineMode("two_step"), "threaded");
  assert.equal(normalizePipelineMode(" THREADED "), "threaded");
  assert.equal(normalizePipelineMode("unknown"), "staged");
});

test("matchPipelineMode distinguishes explicit choices from unset/blank/invalid", () => {
  // Explicit fixtures (canonical + legacy aliases, whitespace tolerated).
  assert.deepEqual(matchPipelineMode("staged"), "staged");
  assert.deepEqual(matchPipelineMode(" STAGED "), "staged");
  assert.deepEqual(matchPipelineMode("full"), "staged");
  assert.deepEqual(matchPipelineMode("threaded"), "threaded");
  assert.deepEqual(matchPipelineMode("two_step"), "threaded");
  assert.deepEqual(matchPipelineMode(" THREADED "), "threaded");
  // Unset / blank / invalid are NEVER coerced into a choice.
  assert.equal(matchPipelineMode(undefined), null);
  assert.equal(matchPipelineMode(null), null);
  assert.equal(matchPipelineMode(""), null);
  assert.equal(matchPipelineMode("   "), null);
  assert.equal(matchPipelineMode("unknown"), null);
  assert.equal(matchPipelineMode(42), null);
});

test("submit body always emits a canonical mode", () => {
  const flow = createSubmitFlow({
    submitWatchdogDepsState: {},
    submitActivityByPanel: new WeakMap(),
    pendingTransactionSnapshotByPanel: new WeakMap(),
    readOnDemandSchemasSetting: () => false,
    api: { clientId: "client" },
  });
  const body = flow.buildSubmitBody(
    {
      graph: { nodes: [], links: [] },
      route: "auto",
      pipelineMode: "two_step",
      graphHash: "full",
      structuralHash: "structural",
      liveCanvasToken: "live:1",
      idempotencyKey: "idempotent",
    },
    "edit",
    { state: {} },
  );

  assert.equal(body.pipeline_mode, "threaded");
});

// ── A1: single-funnel ownership static assertions ───────────────────────────

test("submit funnel ownership: one caller, funnel-hosted guard, shared flow body emitter", async () => {
  const roundtrip = await source("vibecomfy_roundtrip.js");

  // Exactly ONE production invocation of the snapshot builder.
  const callSites = [...roundtrip.matchAll(/await\s+buildSubmitSnapshot\s*\(/g)];
  assert.equal(callSites.length, 1, "buildSubmitSnapshot must have exactly one await-call site");

  // The explicit-mode guard lives INSIDE the funnel, before any body-relevant
  // serialization work happens.
  const funnel = functionBody(roundtrip, "buildSubmitSnapshot");
  const guardAt = funnel.indexOf("PIPELINE_MODE_REQUIRED_ERROR_CODE");
  const serializeAt = funnel.indexOf("canonicalJsonString(graph)");
  assert.ok(guardAt !== -1, "funnel must reject unset preferences");
  assert.ok(serializeAt !== -1, "funnel must serialize");
  assert.ok(guardAt < serializeAt, "guard must fire before body materialization");
  assert.ok(
    funnel.includes("readPipelineModeChoice()"),
    "presence comes from the explicit-choice reader, never normalizePipelineMode",
  );

  // Executor POST body emission is owned solely by agent_submit_flow.js.
  const flowSource = await source("agent_submit_flow.js");
  assert.match(flowSource, /pipeline_mode:\s*normalizePipelineMode\(snapshot\.pipelineMode\)/);

  // Every close path clears the module-scope sentinel.
  const teardownFn = functionBody(roundtrip, "teardownOverlay");
  assert.ok(teardownFn.includes("clearChooseEngineFlowOpen"), "teardownOverlay clears the sentinel");
  const closeFn = functionBody(roundtrip, "closeChooseEngineOverlay");
  assert.ok(closeFn.includes("clearChooseEngineFlowOpen"), "closeChooseEngineOverlay clears the sentinel");
  // Post-commit screens own their lifetime — refreshes may not interrupt.
  assert.ok(closeFn.includes('"research"') && closeFn.includes('"thanks"'), "close suppresses during research/thank-you");
});

// ── A2/A5/A6: live-panel behavior ───────────────────────────────────────────

test("panel exposes staged/threaded selection, persists it, and submits it", async () => {
  globalThis.localStorage?.clear?.();
  globalThis.localStorage?.removeItem(PROVIDER_KEY);
  globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);

  const submitBodies = [];
  const harness = await createBrowserHarness({
    responses: {
      ...READY_AUTO_STATUS,
      "/vibecomfy/agent-executor": okSubmitResponse(submitBodies),
    },
    seedPipelineMode: false,
  });

  try {
    // A6 explicit fixture: this case exercises an ALREADY-CHOSEN user
    // (stored staged), not the silent default.
    globalThis.localStorage.setItem(PIPELINE_MODE_KEY, "staged");
    await bootPanel(harness);

    const mode = harness.document.getElementById("vibecomfy-agent-panel-pipeline-mode");
    assert.deepEqual(mode.children.map((option) => option.value), ["", "staged", "threaded"]);
    assert.equal(mode.children[0].disabled, true, "placeholder option is disabled");
    assert.equal(mode.children[0].textContent, PLACEHOLDER_TEXT);
    assert.equal(mode.value, "staged");

    const hint = harness.document.getElementById("vibecomfy-agent-panel-pipeline-mode-hint");
    assert.equal(hint.textContent, COPY_STAGED, "Settings subtext shows consequence-first copy");

    mode.value = "threaded";
    mode.onchange();
    assert.equal(globalThis.localStorage.getItem(PIPELINE_MODE_KEY), "threaded");
    assert.equal(mode.value, "threaded", "select is re-synced through the shared writer");
    assert.equal(hint.textContent, COPY_THREADED, "subtext follows the choice (copy parity)");

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "edit it";
    await waitFor(() => !harness.document.getElementById("vibecomfy-agent-panel-submit").disabled);
    await harness.document.getElementById("vibecomfy-agent-panel-submit").click();
    await waitFor(() => submitBodies.length > 0);
    assert.equal(submitBodies[0].pipeline_mode, "threaded");
  } finally {
    await harness.dispose();
  }
});

test("unset preference blocks submit at the funnel and opens the mode ask (no request)", async () => {
  globalThis.localStorage?.clear?.();

  const submitBodies = [];
  const harness = await createBrowserHarness({
    responses: {
      ...READY_CODEX_STATUS,
      ...READY_AUTO_STATUS,
      "/vibecomfy/agent-executor": okSubmitResponse(submitBodies),
    },
    seedPipelineMode: false,
  });

  try {
    // Provider decided earlier; only the HOW question is missing.
    globalThis.localStorage.setItem(PROVIDER_KEY, "openai-codex");
    await bootPanel(harness);

    // Auto-adoption-with-missing-mode: overlay mounts AT the mode step even
    // though the provider was resolvable (gate evaluates mode first).
    await waitFor(() => Boolean(harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay")));
    await waitFor(() => Boolean(findButton(harness, CONTINUE_LABEL)));

    const prompt = harness.document.getElementById("vibecomfy-agent-panel-prompt");
    prompt.value = "explain this workflow";
    await waitFor(() => !harness.document.getElementById("vibecomfy-agent-panel-submit").disabled);
    await harness.document.getElementById("vibecomfy-agent-panel-submit").click();

    await waitFor(() => Boolean(findButton(harness, CONTINUE_LABEL)), 3000);
    const boxText = harness.textDump();
    assert.ok(boxText.includes(MODE_HEADING), "mode question owns the screen after blocked submit");
    assert.equal(
      harness.requests.some((entry) => entry.url === "/vibecomfy/agent-executor"),
      false,
      "no executor request may leave without an explicit mode",
    );
    assert.equal(submitBodies.length, 0);
    assert.equal(prompt.value, "explain this workflow", "draft is handed back on cancel");
    assert.equal(globalThis.localStorage.getItem(PIPELINE_MODE_KEY), null, "cancel stores nothing");

    // Tile copy parity (overlay side of A2).
    assert.ok(boxText.includes(COPY_STAGED), "overlay staged copy is exact");
    assert.ok(boxText.includes(COPY_THREADED), "overlay threaded copy is exact");

    // Choose single-thread → completes onboarding cleanly (no research prompt).
    const threadedTile = findTileByLabel(harness, TILE_LABEL_THREADED);
    assert.ok(threadedTile, "single-thread tile rendered");
    threadedTile.click();
    findButton(harness, CONTINUE_LABEL).click();

    await waitFor(() => !harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay"));
    assert.equal(globalThis.localStorage.getItem(PIPELINE_MODE_KEY), "threaded");
    assert.notEqual(
      globalThis.localStorage.getItem("vibecomfy_research_contribution_enabled"),
      "1",
      "mode-only completion never asks — research contribution stays unanswered",
    );
    // The cancelled turn is honestly narrated in the thread instead.
    const dump = harness.textDump();
    assert.ok(dump.includes("Choose how you want the agent to work before submitting."),
      "cancel narration appears in the thread");
    // Now the SAME prompt submits successfully with the chosen mode.
    await waitFor(() => !harness.document.getElementById("vibecomfy-agent-panel-submit").disabled);
    await harness.document.getElementById("vibecomfy-agent-panel-submit").click();
    await waitFor(() => submitBodies.length > 0);
    assert.equal(submitBodies[0].pipeline_mode, "threaded");
  } finally {
    globalThis.localStorage?.removeItem(PROVIDER_KEY);
    globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);
    await harness.dispose();
  }
});

test("explicit choice stays submit-eligible when localStorage writes fail (recoverable)", async () => {
  globalThis.localStorage?.clear?.();

  const submitBodies = [];
  const harness = await createBrowserHarness({
    responses: {
      ...READY_CODEX_STATUS,
      ...READY_AUTO_STATUS,
      "/vibecomfy/agent-executor": okSubmitResponse(submitBodies),
    },
    seedPipelineMode: false,
  });

  try {
    globalThis.localStorage.setItem(PROVIDER_KEY, "openai-codex");
    await bootPanel(harness);
    await waitFor(() => Boolean(harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay")));

    // Mock a throwing-storage world AFTER load: an explicit choice must remain
    // usable for this page session instead of dead-ending the user.
    let rejectedWrites = 0;
    const previousStorage = globalThis.localStorage;
    globalThis.localStorage = {
      getItem: (key) => previousStorage.getItem(key),
      removeItem: (key) => previousStorage.removeItem(key),
      setItem: () => {
        rejectedWrites += 1;
        throw new Error("quota exceeded");
      },
      _clear: () => {},
    };

    const mode = harness.document.getElementById("vibecomfy-agent-panel-pipeline-mode");
    mode.value = "staged";
    mode.onchange();

    assert.ok(rejectedWrites >= 1, "_lsSet failure actually simulated");
    assert.equal(previousStorage.getItem(PIPELINE_MODE_KEY), null, "nothing persisted");
    assert.equal(mode.value, "staged", "field reflects the explicit session choice");

    // Pick through the live flow too: overlay Continue persists via the SAME
    // helper chain, closes cleanly, and the submit is allowed.
    const stagedTile = findTileByLabel(harness, TILE_LABEL_STAGED);
    stagedTile.click();
    findButton(harness, CONTINUE_LABEL).click();
    await waitFor(() => !harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay"));

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "edit it";
    await waitFor(() => !harness.document.getElementById("vibecomfy-agent-panel-submit").disabled);
    await harness.document.getElementById("vibecomfy-agent-panel-submit").click();
    await waitFor(() => submitBodies.length > 0);
    assert.equal(submitBodies[0].pipeline_mode, "staged", "session choice flows through despite ls failure");
  } finally {
    globalThis.localStorage?.removeItem(PROVIDER_KEY);
    globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);
    await harness.dispose();
  }
});

// ── A4-trimmed rehydrate matrix: rehydration never writes the preference ────

test("chat rehydration leaves a CONFLICTING stored mode untouched (pref wins)", async () => {
  globalThis.localStorage?.clear?.();
  const sessionId = "rehydrate-conflicting-mode";
  const chatUrl = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(sessionId)}`;
  const harness = await createBrowserHarness({
    responses: {
      [chatUrl]: {
        status: 200,
        body: {
          ok: true,
          exists: true,
          session_id: sessionId,
          pipeline_mode: "threaded",
          latest_turn_id: null,
          messages: [],
          latest_candidate: null,
          latest_turn_lifecycle: null,
        },
      },
      ...READY_AUTO_STATUS,
    },
    seedPipelineMode: false,
  });

  try {
    globalThis.localStorage.setItem(PIPELINE_MODE_KEY, "staged");
    globalThis.localStorage.setItem("vibecomfy_active_session_id", sessionId);
    await bootPanel(harness);
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrl));

    const mode = harness.document.getElementById("vibecomfy-agent-panel-pipeline-mode");
    await waitFor(() => mode !== null);
    assert.equal(mode.value, "staged", "server-side historical mode cannot overwrite the user's choice");
    assert.equal(globalThis.localStorage.getItem(PIPELINE_MODE_KEY), "staged", "storage untouched");
  } finally {
    await harness.dispose();
  }
});

test("chat rehydration leaves an ABSENT mode unset (never fabricates a default)", async () => {
  globalThis.localStorage?.clear?.();
  const sessionId = "rehydrate-absent-mode";
  const chatUrl = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(sessionId)}`;
  const harness = await createBrowserHarness({
    responses: {
      [chatUrl]: {
        status: 200,
        body: {
          ok: true,
          exists: true,
          session_id: sessionId,
          pipeline_mode: "threaded",
          latest_turn_id: null,
          messages: [],
          latest_candidate: null,
          latest_turn_lifecycle: null,
        },
      },
      ...READY_AUTO_STATUS,
    },
    seedPipelineMode: false,
  });

  try {
    globalThis.localStorage.setItem("vibecomfy_active_session_id", sessionId);
    await bootPanel(harness);
    await waitFor(() => harness.requests.some((entry) => entry.url === chatUrl));

    const mode = harness.document.getElementById("vibecomfy-agent-panel-pipeline-mode");
    await waitFor(() => mode !== null);
    assert.equal(mode.value, "", "unset stays honestly unset — placeholder selected");
    assert.equal(globalThis.localStorage.getItem(PIPELINE_MODE_KEY), null, "no silent default write-back");
  } finally {
    await harness.dispose();
  }
});
