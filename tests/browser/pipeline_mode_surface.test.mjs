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

test("composer mode overrides one conversation while Settings remains the default", async () => {
  globalThis.localStorage?.clear?.();
  globalThis.localStorage.setItem(PIPELINE_MODE_KEY, "staged");

  const submitBodies = [];
  const harness = await createBrowserHarness({
    responses: {
      ...READY_AUTO_STATUS,
      "/vibecomfy/agent-executor": okSubmitResponse(submitBodies),
    },
    seedPipelineMode: false,
  });

  try {
    await bootPanel(harness);
    const settingsMode = harness.document.getElementById(
      "vibecomfy-agent-panel-pipeline-mode",
    );
    const composerMode = harness.document.getElementById(
      "vibecomfy-agent-panel-composer-pipeline-mode",
    );
    const info = harness.document.getElementById(
      "vibecomfy-agent-panel-composer-pipeline-mode-info",
    );

    // The module's storage-failure mirror intentionally survives harnesses;
    // write the default through the real Settings handler for this panel.
    settingsMode.value = "staged";
    settingsMode.onchange();
    assert.equal(settingsMode.parentNode.textContent.includes("Default agent mode"), true);
    assert.deepEqual(
      composerMode.children.map((option) => option.value),
      ["", "staged", "threaded"],
    );
    assert.equal(composerMode.value, "staged", "composer inherits the Settings default");
    assert.match(info.getAttribute("data-tooltip"), /^AGENT MODE\n\nSTAGED — Guided\n/);
    assert.match(info.getAttribute("data-tooltip"), /\n\nTHREADED — Direct\n/);
    assert.match(info.getAttribute("data-tooltip"), /default from Settings/);

    composerMode.value = "threaded";
    composerMode.onchange();
    assert.equal(composerMode.value, "threaded");
    assert.equal(settingsMode.value, "staged", "conversation override leaves Settings alone");
    assert.equal(globalThis.localStorage.getItem(PIPELINE_MODE_KEY), "staged");

    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "edit it";
    await waitFor(() => !harness.document.getElementById("vibecomfy-agent-panel-submit").disabled);
    await harness.document.getElementById("vibecomfy-agent-panel-submit").click();
    await waitFor(() => submitBodies.length > 0);
    assert.equal(submitBodies[0].pipeline_mode, "threaded");

    await harness.document.getElementById("vibecomfy-agent-panel-new-conversation").click();
    assert.equal(
      composerMode.value,
      "staged",
      "a new conversation starts from the Settings default",
    );
  } finally {
    globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);
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
// ── RW1 [G1]: contract-test the REAL WeakSet sentinel through the REAL gate ──
// Every decision below flows through the production deps object built by
// roundtrip's own agentStatusDeps() (real isChooseEngineFlowOpen closure) —
// no fake injection anywhere. The sentinel is module-private, so it is
// asserted BEHAVIORALLY: gate open/skip/close decisions that could not happen
// unless the WeakSet really held (or lacked) the panel entry.
//
// Mirror constraint: readPipelineModeChoice prefers the page-load session
// mirror over storage, so these flows enter via a STORAGE-borne mode choice
// (engine-cards first screen); no Continue write happens before the probe
// steps, letting the later storage.removeItem legitimately flip the gate back
// to mode-missing within the same module instance.

const RESEARCH_HEADING = "Contribute agent research?";
const THANKS_HEADING = "Thank you for making your choice.";
const CONFIRM_LABEL = "Confirm Selection";
const CLAUDE_LABEL = "Claude";

test("live flow sentinel survives a status refresh during engine cards (same overlay, selection kept)", async () => {
  globalThis.localStorage?.clear?.();
  globalThis.localStorage?.removeItem(PROVIDER_KEY);
  globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);

  const harness = await createBrowserHarness({
    responses: {
      ...READY_AUTO_STATUS,
      ...READY_CODEX_STATUS,
    },
    seedPipelineMode: false,
  });

  try {
    // Storage-borne staged choice + no provider: the overlay mounts straight
    // at the engine-cards screen and marks the sentinel (roundtrip :9506).
    globalThis.localStorage.setItem(PIPELINE_MODE_KEY, "staged");
    await bootPanel(harness);

    await waitFor(() => Boolean(harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay")));
    await waitFor(() => Boolean(findButton(harness, CONFIRM_LABEL)));

    const overlayBefore = harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay");
    const nodesBefore = overlayBefore.querySelectorAll(() => true);

    // Make a real selection so the "must not reset selection" claim bites.
    const claudeCard = findTileByLabel(harness, CLAUDE_LABEL);
    assert.ok(claudeCard, "claude card rendered on the engine-cards screen");
    claudeCard.click();
    assert.equal(claudeCard.style.borderColor, "#e6a817", "selection visibly applied");

    // Synthetic status refresh through the ONLY public re-entry: the panel
    // command re-runs openAgentPanel → refreshAgentStatus → syncChooseEngineGate
    // with the production deps (real WeakSet view).
    const statusRequestsBefore = harness.requests.filter((entry) =>
      entry.url.startsWith("/vibecomfy/agent/status"),
    ).length;
    await harness.invokeCommand("VibeComfy.AgentEdit");
    const statusRequestsAfter = harness.requests.filter((entry) =>
      entry.url.startsWith("/vibecomfy/agent/status"),
    ).length;
    assert.ok(statusRequestsAfter > statusRequestsBefore, "synthetic refresh actually ran");

    const overlayAfter = harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay");
    assert.ok(overlayAfter, "overlay still mounted after the refresh");
    assert.equal(
      overlayAfter,
      overlayBefore,
      "flow-open sentinel made the gate SKIP the idempotent remount (second-open skip)",
    );
    const nodesAfter = overlayAfter.querySelectorAll(() => true);
    assert.equal(nodesAfter.length, nodesBefore.length, "box was not rebuilt under the user");
    nodesAfter.forEach((node, index) => {
      assert.equal(node, nodesBefore[index], `overlay node ${index} kept its identity`);
    });
    assert.equal(claudeCard.style.borderColor, "#e6a817", "card selection survived the refresh");
    assert.ok(findButton(harness, CONFIRM_LABEL), "confirm affordance still live");
  } finally {
    globalThis.localStorage?.removeItem(PROVIDER_KEY);
    globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);
    await harness.dispose();
  }
});

test("thank-you countdown teardown clears the sentinel; a later unset re-asks once (real gate remount)", async () => {
  globalThis.localStorage?.clear?.();
  globalThis.localStorage?.removeItem(PROVIDER_KEY);
  globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);
  globalThis.localStorage?.removeItem("vibecomfy_research_contribution_enabled");

  let triggerCount = 0;
  const settingsBodies = [];
  const harness = await createBrowserHarness({
    responses: {
      ...READY_AUTO_STATUS,
      ...READY_CODEX_STATUS,
      "/vibecomfy/agent/settings": async ({ options }) => {
        if (options?.method === "POST") {
          const body = JSON.parse(options.body);
          settingsBodies.push(body);
          return { status: 200, body: { ok: true, research_contribution_enabled: body.research_contribution_enabled } };
        }
        return { status: 200, body: { ok: true, research_contribution_enabled: false } };
      },
      "/vibecomfy/agent/research-contribution/run": async () => {
        triggerCount += 1;
        return { status: 200, body: { ok: true, triggered: true } };
      },
    },
    seedPipelineMode: false,
  });

  try {
    // Engine-cards entry again (storage-borne mode, mirror untouched).
    globalThis.localStorage.setItem(PIPELINE_MODE_KEY, "staged");
    await bootPanel(harness);
    await waitFor(() => Boolean(findButton(harness, CONFIRM_LABEL)));

    const codexCard = findTileByLabel(harness, "Codex");
    assert.ok(codexCard, "codex card rendered");
    codexCard.click();
    findButton(harness, CONFIRM_LABEL).click();
    await waitFor(() => harness.textDump().includes(RESEARCH_HEADING));

    // Decline research: full lifecycle → thanks screen → real 2-tick countdown
    // → internal teardownOverlay() clears the sentinel (roundtrip :9564/:10066).
    findButton(harness, "No").click();
    await waitFor(() => harness.textDump().includes(THANKS_HEADING));
    await waitFor(
      () => !harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay"),
      6000,
    );
    assert.equal(globalThis.localStorage.getItem(PROVIDER_KEY), "openai-codex", "route commit persisted");
    assert.equal(globalThis.localStorage.getItem("vibecomfy_research_contribution_enabled"), "0");

    // Control: with the mode still present, a refresh must stay SILENT
    // (ask-once). The gate consults the real sentinel; !modeMissing prevents
    // any remount regardless.
    await harness.invokeCommand("VibeComfy.AgentEdit");
    assert.equal(
      harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay"),
      null,
      "completed flow is never flappily re-asked",
    );

    // Now the discriminating step: the user explicitly clears their stored
    // answer. Because this flow never wrote the session mirror, the gate
    // honestly sees mode-missing. If the countdown teardown had leaked the
    // WeakSet entry, flowOpen would suppress this remount forever (the exact
    // regression silence G1 froze). Cleared sentinel → gate REMOUNTS at the
    // mode question, keyed off the REAL isChooseEngineFlowOpen closure.
    globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => Boolean(findButton(harness, CONTINUE_LABEL)));
    const reopened = harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay");
    assert.ok(reopened, "unset answer re-asks: gate proved the sentinel was cleared");
    assert.equal(findButton(harness, CONFIRM_LABEL), null, "fresh ask starts at the mode step");
    assert.match(harness.textDump(), /How should the agent work\?/);

    // Remounted flow re-marks the sentinel — a further refresh must again be
    // a no-op on element identity, and mode-only Continue closes WITHOUT the
    // research prompt (the other :9564 caller, mode-only completion :9984).
    await harness.invokeCommand("VibeComfy.AgentEdit");
    assert.equal(
      harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay"),
      reopened,
      "reopened flow is itself sentinel-guarded",
    );
    const stagedTile = findTileByLabel(harness, TILE_LABEL_STAGED);
    stagedTile.click();
    findButton(harness, CONTINUE_LABEL).click();
    await waitFor(() => !harness.document.getElementById("vibecomfy-agent-panel-welcome-overlay"));
    assert.doesNotMatch(harness.textDump(), new RegExp(RESEARCH_HEADING.replace("?", "\\?")), "mode-only completion skips research");
    assert.equal(globalThis.localStorage.getItem(PIPELINE_MODE_KEY), "staged");
    assert.equal(triggerCount, 0, "decline path never triggers a research run");
    assert.deepEqual(settingsBodies, [{ research_contribution_enabled: false }]);
  } finally {
    globalThis.localStorage?.removeItem(PROVIDER_KEY);
    globalThis.localStorage?.removeItem(PIPELINE_MODE_KEY);
    globalThis.localStorage?.removeItem("vibecomfy_research_contribution_enabled");
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

// ── B2-T1/B2-T2: staged-chrome gate derives from the EXPLICIT getter only ───

// Boundary-based extractor: functionBody()'s brace counter mis-parses
// signatures containing object-literal defaults (`deps = {}`).
function fnSource(text, name) {
  const start = text.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} should exist`);
  const next = text.indexOf("\nfunction ", start + 1);
  return text.slice(start, next === -1 ? text.length : next);
}

test("pipeline chrome gating derives from the conversation choice with Settings fallback", async () => {
  const rt = await source("vibecomfy_roundtrip.js");
  const thread = await source("panel_thread.js");

  // The single display gate consults the per-conversation resolver and NEVER
  // the forgiving normalizer / silent staged default.
  const gate = fnSource(rt, "pipelineChromeEnabled");
  assert.match(
    gate,
    /readConversationPipelineModeChoice\(panel\)/,
    "gate reads the conversation-aware resolver",
  );
  assert.match(gate, /=== "staged"/, "only an explicit staged choice shows staged chrome");
  assert.doesNotMatch(gate, /DEFAULT_PIPELINE_MODE|normalizePipelineMode/);

  // Every thread-side renderer receives the same conversation-aware getter.
  for (const wrapper of ["renderChatBubbleNode", "reconcileChatBubbles", "populateAgentBubbleDetail"]) {
    assert.match(
      fnSource(rt, wrapper),
      /pipelineModeChoice:\s*\(\) => readConversationPipelineModeChoice\(panel\)/,
      `${wrapper} injects the conversation-aware getter`,
    );
  }

  // Threaded/unset pending bubbles keep an honest placeholder — never blank,
  // never staged copy (half-gated UX tripwire at source level).
  assert.match(thread, /NEUTRAL_PENDING_LABEL = "Working…"/);
  assert.match(fnSource(thread, "renderExecutorProgressRow"), /vibecomfyPendingNeutral/);
  assert.match(
    fnSource(thread, "populateAgentBubbleDetail"),
    /stagedChromeForDeps\(panel, deps\) && ordinarySnapshot\?\.progress/,
    "staged Progress detail section gated on explicit staging",
  );
  // Both keyed signatures include the current explicit mode so a Settings
  // switch invalidates cached DOM (B2-T2).
  const sigParts = thread.match(/explicitPipelineModeForDeps\(panel, deps\) \|\| "unset"/g) || [];
  assert.ok(sigParts.length >= 2, "bubble + detail signatures both key on explicit mode");
  // Renderer layer never reaches for a default-coercing helper.
  assert.doesNotMatch(thread, /DEFAULT_PIPELINE_MODE/);
  assert.doesNotMatch(thread, /normalizePipelineMode/);

  // Live switching reuses the existing scheduler primitive from the REAL
  // Settings onchange handler — no event bus.
  assert.match(rt, /scheduleRenderAgentPanel\("pipeline-mode-change", panel, \[/);
  assert.match(rt, /scheduleRenderAgentPanel\("conversation-pipeline-mode-change", panel, \[/);
});
