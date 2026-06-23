import test from "node:test";
import assert from "node:assert/strict";

import { createBrowserHarness } from "./harness.mjs";

import {
  deriveAgentActivityState,
  normalizeAgentTurnPayload,
  formatActivityHeadline,
  formatOutcomeCounts,
  formatStatementAction,
} from "../../vibecomfy/comfy_nodes/web/agent_turn_feed.js";
import {
  createExecutorProgressSnapshot,
} from "../../vibecomfy/comfy_nodes/web/executor_progress.js";

// ── Helpers ─────────────────────────────────────────────────────────────────

async function waitFor(predicate, { attempts = 50 } = {}) {
  for (let index = 0; index < attempts; index += 1) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error("waitFor timed out");
}

function makeCanonicalTurn(overrides = {}) {
  const payload = normalizeAgentTurnPayload({
    session_id: overrides.session_id || "sess-render",
    turn_id: overrides.turn_id || "0001",
    turn_number: overrides.turn_number ?? 1,
    status: overrides.status || "in_progress",
    message: overrides.message || "Agent is working on your request.",
    statement_count: overrides.statement_count ?? (Array.isArray(overrides.statements) ? overrides.statements.length : 0),
    landed_op_count: overrides.landed_op_count ?? 0,
    statements: overrides.statements || [],
    done_summary: overrides.done_summary || null,
    diagnostics: overrides.diagnostics || null,
    budget: overrides.budget || null,
    clarification_message: overrides.clarification_message || null,
    clarification_required: overrides.clarification_required || false,
    ...overrides,
  });
  const canonical = deriveAgentActivityState(payload);
  return { entry: payload, canonical };
}

function makeTurnEntry(overrides = {}, explicitCanonicalActivity = undefined) {
  const { entry, canonical } = makeCanonicalTurn(overrides);
  const turnId = entry.turn_id;
  const sessionId = entry.session_id;
  const canonicalActivity = explicitCanonicalActivity !== undefined
    ? explicitCanonicalActivity
    : canonical;
  return {
    session_id: sessionId,
    turn_id: turnId,
    turn_key: `${sessionId}/${turnId}`,
    turn_number: entry.turn_number ?? 1,
    entry_type: overrides.entry_type || "batch",
    status: entry.status,
    message: overrides.message || null,
    statement_count: entry.statement_count || 0,
    landed_op_count: entry.landed_op_count || 0,
    statements: overrides.statements || [],
    done_summary: overrides.done_summary || null,
    diagnostics: overrides.diagnostics || null,
    budget: overrides.budget || null,
    clarification_message: overrides.clarification_message || null,
    clarification_required: overrides.clarification_required || false,
    canonical_activity: canonicalActivity,
  };
}

// ── Pure-helper contract tests ────────────────────────────────────────────

test("formatActivityHeadline — answer-only turn: falls back to done() message", () => {
  const { canonical } = makeCanonicalTurn({
    session_id: "sess-a",
    turn_id: "0001",
    turn_number: 1,
    status: "done",
    message: "Answer only, no edits.",
    statement_count: 1,
    landed_op_count: 0,
    statements: [{ op_kind: "done", status: "done", message: "All done" }],
    done_summary: "Answered without graph changes.",
  });
  const headline = formatActivityHeadline(canonical, null);
  assert.ok(headline.length > 0);
  assert.match(headline, /All done|Answered without graph changes/);
  assert.doesNotMatch(headline.toLowerCase(), /\bnull\b/);
});

test("formatActivityHeadline — edit-plus-done uses last substantive statement", () => {
  const { canonical } = makeCanonicalTurn({
    session_id: "sess-b",
    turn_id: "0002",
    turn_number: 2,
    status: "done",
    statement_count: 4,
    landed_op_count: 3,
    statements: [
      { op_kind: "query", status: "done", message: "Queried available samplers" },
      { op_kind: "add_node", status: "done", message: "Added KScheduler node", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected scheduler to pipeline", landed: true, ok: true },
      { op_kind: "done", status: "done", message: "Finished editing" },
    ],
    done_summary: "Added scheduler node.",
  });
  const headline = formatActivityHeadline(canonical, null);
  assert.ok(headline.length > 0);
  assert.notEqual(headline, "Finished editing");
  assert.match(headline, /Connected scheduler|Added KScheduler/);
});

test("formatOutcomeCounts — answer-only", () => {
  const { canonical } = makeCanonicalTurn({
    status: "done",
    statement_count: 1,
    landed_op_count: 0,
    statements: [{ op_kind: "done", status: "done" }],
    done_summary: "Answer only.",
  });
  assert.equal(formatOutcomeCounts(canonical, null), "Answer only — no graph changes");
});

test("formatOutcomeCounts — edit-plus-done with applied count", () => {
  const { canonical } = makeCanonicalTurn({
    status: "done",
    statement_count: 5,
    landed_op_count: 4,
    statements: [
      { op_kind: "query", status: "done" },
      { op_kind: "add_node", status: "done", landed: true, ok: true },
      { op_kind: "set_field", status: "done", landed: true, ok: true },
      { op_kind: "connect", status: "done", landed: true, ok: true },
      { op_kind: "done", status: "done" },
    ],
  });
  assert.match(formatOutcomeCounts(canonical, null), /4 changes applied/);
});

test("formatOutcomeCounts — clarify", () => {
  const { canonical } = makeCanonicalTurn({
    status: "clarify",
    clarification_message: "How should I configure the sampler?",
    clarification_required: true,
    statement_count: 1,
    landed_op_count: 0,
    statements: [{ op_kind: "clarify", status: "active", message: "Need clarification" }],
  });
  assert.equal(formatOutcomeCounts(canonical, null), "Clarification needed");
});

test("formatOutcomeCounts — error with diagnostics", () => {
  const { canonical } = makeCanonicalTurn({
    status: "error",
    statement_count: 2,
    landed_op_count: 1,
    statements: [
      { op_kind: "query", status: "done", ok: true },
      { op_kind: "apply_op", status: "error", ok: false },
    ],
    diagnostics: [{ code: "ERR_1", message: "First" }, { code: "ERR_2", message: "Second" }],
  });
  assert.match(formatOutcomeCounts(canonical, null), /Error: 2 diagnostics/);
});

test("formatOutcomeCounts — budget_exhausted", () => {
  const { canonical } = makeCanonicalTurn({
    status: "budget_exhausted",
    statement_count: 3,
    landed_op_count: 1,
    statements: [
      { op_kind: "query", status: "done" },
      { op_kind: "add_node", status: "done", landed: true, ok: true },
      { op_kind: "done", status: "done" },
    ],
    budget: { remaining_batches: 2, consecutive_errors: 1 },
  });
  const text = formatOutcomeCounts(canonical, null);
  assert.match(text, /Budget exhausted/);
  assert.match(text, /2 turns left/);
});

test("formatStatementAction — handles null/empty", () => {
  for (const input of [null, {}, { op_kind: null }]) {
    const result = formatStatementAction(input);
    assert.ok(typeof result === "string" && result.length > 0);
    assert.ok(!["null", "undefined"].includes(result));
  }
});

test("formatStatementAction — humanized labels", () => {
  assert.match(formatStatementAction({ op_kind: "add_node", message: "Added a KScheduler" }), /Added node/i);
  assert.match(formatStatementAction({ op_kind: "query", message: "Queried all samplers" }), /Queried/i);
  assert.match(formatStatementAction({ op_kind: "set_field", message: "Updated cfg" }), /Set field/i);
  assert.match(formatStatementAction({ op_kind: "connect", message: "Connected output" }), /Connected/i);
  assert.match(formatStatementAction({ op_kind: "remove_node", message: "Deleted node" }), /Removed node/i);
});

// ── Canonical derivation tests ────────────────────────────────────────────

test("canonical derivation — answer-only yields 'answered' outcome, no graph changes", () => {
  const { canonical } = makeCanonicalTurn({
    session_id: "sess-answered",
    turn_id: "0100",
    turn_number: 1,
    status: "done",
    message: "Here is your answer.",
    statement_count: 1,
    landed_op_count: 0,
    statements: [{ op_kind: "done", status: "done", message: "Turn complete" }],
    done_summary: "Answered without graph changes.",
  });
  assert.equal(canonical.outcome.kind, "answered");
  assert.equal(canonical.outcome.graph_changes, false);
  assert.match(canonical.outcome.summary, /Answered/i);
  assert.equal(canonical.latest_substantive_statement, null);
  assert.equal(formatOutcomeCounts(canonical, null), "Answer only — no graph changes");
});

test("canonical derivation — edit-plus-done excludes done() from latest substantive", () => {
  const { canonical } = makeCanonicalTurn({
    session_id: "sess-edit-done",
    turn_id: "0200",
    turn_number: 3,
    status: "done",
    statement_count: 5,
    landed_op_count: 3,
    statements: [
      { op_kind: "query", status: "done", message: "Queried available nodes" },
      { op_kind: "add_node", status: "done", message: "Added Upscale node", landed: true, ok: true },
      { op_kind: "connect", status: "done", message: "Connected pipeline", landed: true, ok: true },
      { op_kind: "set_field", status: "done", message: "Set upscale_factor to 2x", landed: true, ok: true },
      { op_kind: "done", status: "done", message: "Finished editing" },
    ],
    done_summary: "Added Upscale node and connected.",
  });
  assert.equal(canonical.outcome.kind, "done");
  assert.ok(canonical.outcome.landed_ops >= 3);
  assert.ok(canonical.latest_substantive_statement);
  assert.notEqual(canonical.latest_substantive_statement.op_kind, "done");
  assert.equal(canonical.latest_substantive_statement.op_kind, "set_field");
  assert.notEqual(formatActivityHeadline(canonical, null), "Finished editing");
  assert.match(formatOutcomeCounts(canonical, null), /3 changes applied/);
});

test("canonical derivation — clarify has correct kind and fully-done phase_progress", () => {
  const { canonical } = makeCanonicalTurn({
    session_id: "sess-clarify",
    turn_id: "0300",
    turn_number: 2,
    status: "clarify",
    clarification_required: true,
    clarification_message: "Should I replace the sampler?",
    statement_count: 1,
    landed_op_count: 0,
    statements: [{ op_kind: "clarify", status: "active", message: "Need clarification" }],
  });
  assert.equal(canonical.outcome.kind, "clarify");
  assert.equal(canonical.outcome.clarification_required, true);
  assert.ok(canonical.outcome.clarification_message.includes("sampler"));
  assert.equal(canonical.phase_progress.decide, "done");
  assert.equal(canonical.phase_progress.execute, "done");
  assert.equal(formatOutcomeCounts(canonical, null), "Clarification needed");
});

test("canonical derivation — error has diagnostics in outcome and canonical", () => {
  const { canonical } = makeCanonicalTurn({
    session_id: "sess-error",
    turn_id: "0400",
    turn_number: 2,
    status: "error",
    statement_count: 2,
    landed_op_count: 1,
    statements: [
      { op_kind: "query", status: "done", message: "Queried nodes", ok: true },
      { op_kind: "apply_op", status: "error", message: "Failed to apply", ok: false },
    ],
    diagnostics: [{ code: "NODE_NOT_FOUND", message: "Target node was removed" }],
  });
  assert.equal(canonical.outcome.kind, "error");
  assert.match(canonical.outcome.summary, /NODE_NOT_FOUND|Target node was removed/);
  assert.ok(canonical.outcome.diagnostics);
  assert.ok(canonical.diagnostics);
  assert.match(formatOutcomeCounts(canonical, null), /Error: 1 diagnostic/);
});

test("canonical derivation — budget_exhausted has budget info", () => {
  const { canonical } = makeCanonicalTurn({
    session_id: "sess-budget",
    turn_id: "0500",
    turn_number: 2,
    status: "budget_exhausted",
    statement_count: 3,
    landed_op_count: 1,
    statements: [
      { op_kind: "query", status: "done" },
      { op_kind: "add_node", status: "done", landed: true, ok: true },
      { op_kind: "done", status: "done" },
    ],
    budget: { remaining_batches: 0, consecutive_errors: 2 },
  });
  assert.equal(canonical.outcome.kind, "budget_exhausted");
  assert.match(canonical.outcome.summary, /Budget exhausted/);
  assert.ok(canonical.outcome.budget);
  assert.equal(canonical.outcome.budget.remaining_batches, 0);
  const text = formatOutcomeCounts(canonical, null);
  assert.match(text, /Budget exhausted/);
  assert.match(text, /0 turns left/);
});

// ── Browser rendering tests ────────────────────────────────────────────────

test("DOM: Decide secondary text renders from progress label and clears on next phase", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();
    panel.root.dataset.open = "1";
    panel.state.sessionId = "session-decision";
    panel.state.turns = [];
    panel.state.executorProgress = createExecutorProgressSnapshot({ decide: "active" });
    panel.state.chatMessages = [
      {
        role: "agent",
        text: "",
        pending_response: true,
        executor_pending: true,
        progress: panel.state.executorProgress,
        local_id: "pending-decision",
      },
    ];

    mod.resetThreadRenderState(panel);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    panel.state.chatMessages[0].progress_label = "Deciding: Research node choices, then edit the workflow.";
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const secondaryNode = () => harness.document.body.querySelectorAll(
      (node) => node.dataset?.vibecomfyProgressSecondary === "1",
    )[0];
    assert.match(secondaryNode().textContent, /Deciding: Research node choices, then edit the workflow\./);
    assert.equal(
      harness.document.body.querySelectorAll((node) => node.dataset?.vibecomfyExecutorStage === "decide")[0]
        ?.dataset?.vibecomfyExecutorStatus,
      "active",
    );

    panel.state.executorProgress = createExecutorProgressSnapshot({
      decide: "done",
      research: "active",
    });
    panel.state.chatMessages[0].progress = panel.state.executorProgress;
    panel.state.chatMessages[0].progress_label = null;
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    assert.equal(
      harness.document.body.querySelectorAll((node) => node.dataset?.vibecomfyExecutorStage === "research")[0]
        ?.dataset?.vibecomfyExecutorStatus,
      "active",
    );
    assert.doesNotMatch(secondaryNode()?.textContent || "", /Research node choices/);
  } finally {
    await harness.dispose();
  }
});

test("DOM: phase strip present while pending and legacy activity rows stay hidden", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const activeTurn = makeTurnEntry({
      session_id: "sess-active",
      turn_id: "0001",
      turn_number: 0,
      status: "in_progress",
      message: "Agent is working on your edit.",
      statement_count: 3,
      landed_op_count: 1,
      statements: [
        { op_kind: "query", status: "done", message: "Queried nodes" },
        { op_kind: "add_node", status: "done", message: "Added Preview node", landed: true, ok: true },
        { op_kind: "done", status: "done" },
      ],
    });

    panel.state.turns = [activeTurn];
    panel.state.executorProgress = activeTurn.canonical_activity.phase_progress;
    panel.state.chatMessages = [
      {
        role: "agent",
        text: "Added Preview node",
        pending_response: true,
        progress: activeTurn.canonical_activity.phase_progress,
        progress_label: activeTurn.canonical_activity.headline,
        canonical_activity: activeTurn.canonical_activity,
      },
    ];

    mod.resetThreadRenderState(panel);
    mod.markAgentPanelDirty(panel, ["THREAD"]);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const text = harness.textDump();
    assert.match(text, /Decide/);
    assert.match(text, /Research/);
    assert.match(text, /Execute/);
    assert.match(text, /Review/);

    const phaseStrip = harness.document.body.querySelectorAll(
      (node) => node.dataset?.vibecomfyPhaseSource === "canonical",
    );
    assert.ok(phaseStrip.length >= 1);
    const stages = phaseStrip[0].querySelectorAll((node) => node.dataset?.vibecomfyExecutorStage);
    const secondary = phaseStrip[0].querySelectorAll(
      (node) => node.dataset?.vibecomfyProgressSecondary === "1",
    )[0];
    assert.ok(secondary, "current step text should render as secondary progress text");
    assert.match(secondary.textContent, /Added Preview node/);
    assert.ok(
      phaseStrip[0].children.indexOf(secondary) > phaseStrip[0].children.indexOf(stages[stages.length - 1]),
      "secondary progress text should appear below/after the stage strip",
    );

    const pendingBubble = phaseStrip[0].parentNode?.parentNode;
    assert.ok(pendingBubble, "phase strip should live inside the pending bubble");
    const detailToggle = pendingBubble.querySelectorAll(
      (node) => node.textContent === "\u25b6 details" && typeof node.onclick === "function",
    )[0];
    assert.ok(detailToggle, "pending bubble should expose details");
    detailToggle.click();
    const expandedPendingText = harness.textDump();
    assert.match(expandedPendingText, /Turn details:/);
    assert.match(expandedPendingText, /Queried nodes/i);
    assert.match(expandedPendingText, /Added node/i);

    const historyRegion = harness.document.getElementById("vibecomfy-agent-panel-region-history");
    assert.equal(
      historyRegion?.style.display,
      "none",
      "pending response bubble should suppress the duplicate below-thread activity strip",
    );
    const liveActivityRows = historyRegion.querySelectorAll(
      (node) => node.className === "vibecomfy-batch-row",
    );
    assert.equal(liveActivityRows.length, 0);

    assert.doesNotMatch(text, /In progress\.\.\./);

    // Clear pending -> the legacy below-thread activity strip stays disabled.
    panel.state.chatMessages = [];
    panel.state.turns = [];
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const activityRows = historyRegion.querySelectorAll(
      (node) => node.className === "vibecomfy-batch-row",
    );
    assert.equal(activityRows.length, 0);
    assert.equal(historyRegion?.style.display, "none");
    assert.doesNotMatch(harness.textDump(), /In progress\.\.\./);
  } finally {
    await harness.dispose();
  }
});

test("DOM: pending bubble details include per-action rows, counts, diagnostics, no unsafe fields", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const activeTurn = makeTurnEntry({
      session_id: "sess-expanded",
      turn_id: "0001",
      turn_number: 0,
      status: "in_progress",
      message: "Applying graph edits.",
      statement_count: 5,
      landed_op_count: 3,
      statements: [
        { op_kind: "query", status: "done", message: "Queried all nodes" },
        { op_kind: "add_node", status: "done", message: "Added Upscale node", landed: true, ok: true },
        { op_kind: "connect", status: "done", message: "Connected Upscale to output", landed: true, ok: true },
        { op_kind: "set_field", status: "done", message: "Set upscale_factor to 2x", ok: true },
        { op_kind: "set_value", status: "done", message: "Updated sampler cfg", landed: true, ok: true },
      ],
      diagnostics: [
        { code: "NODE_ID_TAKEN", message: "Node id 9 already occupied; reassigned to 12" },
      ],
    });

    panel.state.turns = [activeTurn];
    panel.state.chatMessages = [
      {
        role: "agent",
        text: "Applying graph edits.",
        pending_response: true,
        progress: activeTurn.canonical_activity.phase_progress,
        progress_label: activeTurn.canonical_activity.headline,
        canonical_activity: activeTurn.canonical_activity,
      },
    ];
    panel.state.executorProgress = activeTurn.canonical_activity.phase_progress;

    mod.resetThreadRenderState(panel);
    mod.markAgentPanelDirty(panel, ["THREAD"]);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const historyRegion = harness.document.getElementById("vibecomfy-agent-panel-region-history");
    const rows = historyRegion.querySelectorAll(
      (node) => node.className === "vibecomfy-batch-row",
    );
    assert.equal(rows.length, 0);
    assert.equal(historyRegion?.style.display, "none");

    const detailToggle = harness.document.body.querySelectorAll(
      (node) => node.textContent === "\u25b6 details" && typeof node.onclick === "function",
    )[0];
    assert.ok(detailToggle, "pending bubble should expose details");
    detailToggle.click();
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const expandedText = harness.textDump();

    // Per-action rows appear.  formatStatementAction for query/search yields
    // "Search: <message>" while for other op_kinds it yields the humanized
    // label without the message.  Match on what actually renders.
    assert.match(expandedText, /Queried all nodes/i,
      "query message should appear (via formatStatementAction for query)");
    assert.match(expandedText, /Added node/i,
      "add_node action label should appear");
    assert.match(expandedText, /Connected/i,
      "connect action label should appear");
    assert.match(expandedText, /Set field/i,
      "set_field action label should appear");
    assert.match(expandedText, /Set value/i,
      "set_value action label should appear");

    // Counts
    assert.match(expandedText, /5 statements/i);
    assert.match(expandedText, /3 landed/);

    // Diagnostics
    assert.match(expandedText, /NODE_ID_TAKEN/i);
    assert.match(expandedText, /reassigned to 12/i);

    // No duplicate "In progress..."
    assert.doesNotMatch(expandedText, /In progress\.\.\./);

    // No unsafe fields
    for (const unsafe of ["diff", "raw_batch", "raw_source", "provider_metadata", "file_path", "full_report"]) {
      assert.doesNotMatch(expandedText, new RegExp(`\\b${unsafe}\\b`, "i"), `no ${unsafe} leak`);
    }

    assert.equal(
      historyRegion.querySelectorAll((node) => node.className === "vibecomfy-batch-row").length,
      0,
    );
  } finally {
    await harness.dispose();
  }
});

test("DOM: answer-only renders 'Answered without graph changes' in chat, no not-landed leak, no candidate controls", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const { canonical } = makeCanonicalTurn({
      session_id: "sess-answer",
      turn_id: "0001",
      turn_number: 1,
      status: "done",
      message: "The current graph uses an Euler sampler.",
      statement_count: 1,
      landed_op_count: 0,
      statements: [{ op_kind: "done", status: "done", message: "Turn complete" }],
      done_summary: "Answered without graph changes.",
    });

    assert.equal(canonical.outcome.kind, "answered");
    assert.equal(canonical.outcome.graph_changes, false);
    assert.equal(formatOutcomeCounts(canonical, null), "Answer only — no graph changes");

    panel.state.chatMessages = [
      { role: "agent", text: canonical.outcome.summary, turn_id: "0001", source: "agent-edit" },
    ];
    panel.state.turns = [];

    mod.resetThreadRenderState(panel);
    mod.markAgentPanelDirty(panel, ["THREAD"]);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const text = harness.textDump();
    assert.match(text, /Answered without graph changes/i);
    assert.doesNotMatch(text, /not landed/i);

    const applyBtn = harness.document.getElementById("vibecomfy-agent-panel-apply");
    const rejectBtn = harness.document.getElementById("vibecomfy-agent-panel-reject");
    assert.ok(applyBtn); assert.ok(rejectBtn);
    assert.equal(applyBtn.disabled, true);
    assert.equal(rejectBtn.disabled, true);
  } finally {
    await harness.dispose();
  }
});

test("DOM: edit-plus-done surfaces done_summary, done() not the visible latest, applied count correct", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const { canonical } = makeCanonicalTurn({
      session_id: "sess-edit",
      turn_id: "0001",
      turn_number: 1,
      status: "done",
      message: "Edit applied successfully.",
      statement_count: 4,
      landed_op_count: 3,
      statements: [
        { op_kind: "query", status: "done", message: "Queried available models" },
        { op_kind: "add_node", status: "done", message: "Added ImageUpscaleWithModel", landed: true, ok: true },
        { op_kind: "set_field", status: "done", message: "Set cfg to 7.5", landed: true, ok: true, field_path: "KSampler.cfg" },
        { op_kind: "done", status: "done", message: "Finished editing" },
      ],
      done_summary: "Added upscale node and changed cfg to 7.5.",
    });

    assert.equal(canonical.outcome.kind, "done");
    assert.ok(canonical.latest_substantive_statement);
    assert.notEqual(canonical.latest_substantive_statement.op_kind, "done");
    assert.equal(canonical.latest_substantive_statement.op_kind, "set_field");
    assert.match(formatOutcomeCounts(canonical, null), /3 changes applied/);

    panel.state.chatMessages = [
      { role: "agent", text: canonical.outcome.summary, turn_id: "0001", source: "agent-edit" },
    ];
    panel.state.turns = [];

    mod.resetThreadRenderState(panel);
    mod.markAgentPanelDirty(panel, ["THREAD"]);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const text = harness.textDump();
    assert.match(text, /Added upscale node and changed cfg/i);
    assert.doesNotMatch(text, /Finished editing/i);
  } finally {
    await harness.dispose();
  }
});

test("DOM: failed/clarify/budget-exhausted canonical outcomes lead with correct copy", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const err = makeCanonicalTurn({
      session_id: "sess-err", turn_id: "0001", turn_number: 1, status: "error",
      statement_count: 2, landed_op_count: 1,
      statements: [
        { op_kind: "add_node", status: "done", message: "Added sampler", landed: true, ok: true },
        { op_kind: "apply_op", status: "error", message: "Failed: node not found", ok: false },
      ],
      diagnostics: [{ code: "NODE_NOT_FOUND", message: "Target node was removed during execution" }],
    }).canonical;

    const clarify = makeCanonicalTurn({
      session_id: "sess-clarify", turn_id: "0002", turn_number: 2, status: "clarify",
      clarification_message: "Which sampler: Euler or DPM++?",
      clarification_required: true,
      statement_count: 1, landed_op_count: 0,
      statements: [{ op_kind: "clarify", status: "active", message: "Need clarification" }],
    }).canonical;

    const budget = makeCanonicalTurn({
      session_id: "sess-budget", turn_id: "0003", turn_number: 3, status: "budget_exhausted",
      statement_count: 3, landed_op_count: 1,
      statements: [
        { op_kind: "query", status: "done", message: "Queried nodes" },
        { op_kind: "add_node", status: "done", message: "Added Preview node", landed: true, ok: true },
        { op_kind: "done", status: "done" },
      ],
      budget: { remaining_batches: 0, consecutive_errors: 3 },
    }).canonical;

    assert.equal(err.outcome.kind, "error");
    assert.match(formatOutcomeCounts(err, null), /Error: 1 diagnostic/);

    assert.equal(clarify.outcome.kind, "clarify");
    assert.equal(formatOutcomeCounts(clarify, null), "Clarification needed");
    assert.match(clarify.outcome.clarification_message, /Euler or DPM\+\+/);

    assert.equal(budget.outcome.kind, "budget_exhausted");
    const budgetText = formatOutcomeCounts(budget, null);
    assert.match(budgetText, /Budget exhausted/);
    assert.match(budgetText, /0 turns left/);

    // Render as chat messages
    panel.state.chatMessages = [
      { role: "agent", text: err.outcome.summary, turn_id: "0001", source: "agent-edit" },
      { role: "agent", text: clarify.outcome.clarification_message, turn_id: "0002", source: "agent-edit" },
      { role: "agent", text: budget.outcome.summary, turn_id: "0003", source: "agent-edit" },
    ];
    panel.state.turns = [];

    mod.resetThreadRenderState(panel);
    mod.markAgentPanelDirty(panel, ["THREAD"]);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const text = harness.textDump();
    assert.match(text, /NODE_NOT_FOUND|Target node was removed/);
    assert.match(text, /Euler or DPM\+\+/);
    assert.match(text, /Budget exhausted/);
    assert.doesNotMatch(text, /In progress\.\.\./);
  } finally {
    await harness.dispose();
  }
});

// ── Route-scoped rendering tests ──────────────────────────────────────────

test("DOM: respond-route turn renders as normal assistant message, no candidate controls", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const { canonical } = makeCanonicalTurn({
      session_id: "sess-respond-ui",
      turn_id: "0001",
      turn_number: 1,
      status: "done",
      route: "respond",
      message: "This graph uses an Euler sampler with cfg=7.5 for img2img generation.",
      statement_count: 1,
      landed_op_count: 0,
      statements: [{ op_kind: "done", status: "done", message: "Turn complete" }],
      done_summary: "Answered without graph changes.",
    });

    assert.equal(canonical.outcome.kind, "answered");
    assert.equal(canonical.outcome.graph_changes, false);

    panel.state.chatMessages = [
      { role: "agent", text: canonical.outcome.summary, turn_id: "0001", source: "agent-edit" },
    ];
    panel.state.turns = [];

    mod.resetThreadRenderState(panel);
    mod.markAgentPanelDirty(panel, ["THREAD"]);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const text = harness.textDump();
    assert.match(text, /Answered without graph changes/i);
    assert.doesNotMatch(text, /not landed/i);

    // Apply/Reject must be disabled for non-applyable respond route
    const applyBtn = harness.document.getElementById("vibecomfy-agent-panel-apply");
    const rejectBtn = harness.document.getElementById("vibecomfy-agent-panel-reject");
    assert.ok(applyBtn, "apply button should exist");
    assert.ok(rejectBtn, "reject button should exist");
    assert.equal(applyBtn.disabled, true, "apply must be disabled for respond route");
    assert.equal(rejectBtn.disabled, true, "reject must be disabled for respond route");

    // No internal gate string leakage in DOM
    assert.doesNotMatch(text, /no_candidate_reason/i);
    assert.doesNotMatch(text, /route_not_applyable/i);
  } finally {
    await harness.dispose();
  }
});

test("DOM: research-route turn renders as normal assistant message, no candidate controls", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const { canonical } = makeCanonicalTurn({
      session_id: "sess-research-ui",
      turn_id: "0001",
      turn_number: 1,
      status: "done",
      route: "research",
      message: "LTX Video supports i2v with up to 768px resolution. PIL can be omitted.",
      statement_count: 1,
      landed_op_count: 0,
      statements: [{ op_kind: "done", status: "done", message: "Turn complete" }],
      done_summary: "Researched LTX compatibility without graph changes.",
    });

    assert.equal(canonical.outcome.kind, "answered");
    assert.equal(canonical.outcome.graph_changes, false);

    panel.state.chatMessages = [
      { role: "agent", text: canonical.outcome.summary, turn_id: "0001", source: "agent-edit" },
    ];
    panel.state.turns = [];

    mod.resetThreadRenderState(panel);
    mod.markAgentPanelDirty(panel, ["THREAD"]);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const text = harness.textDump();
    assert.match(text, /Researched LTX compatibility/i);
    assert.doesNotMatch(text, /not landed/i);

    // Apply/Reject must be disabled for non-applyable research route
    const applyBtn = harness.document.getElementById("vibecomfy-agent-panel-apply");
    const rejectBtn = harness.document.getElementById("vibecomfy-agent-panel-reject");
    assert.equal(applyBtn.disabled, true, "apply must be disabled for research route");
    assert.equal(rejectBtn.disabled, true, "reject must be disabled for research route");

    // No internal gate string leakage in DOM
    assert.doesNotMatch(text, /no_candidate_reason/i);
    assert.doesNotMatch(text, /route_not_applyable/i);
    assert.doesNotMatch(text, /research_summary/i, "internal research_summary field must not leak");
    assert.doesNotMatch(text, /research_source_count/i, "internal research_source_count must not leak");
  } finally {
    await harness.dispose();
  }
});

test("DOM: multi-turn chat renders respond → revise → research chronologically", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const respondCanonical = makeCanonicalTurn({
      session_id: "sess-multi", turn_id: "0001", turn_number: 1,
      status: "done", route: "respond",
      message: "The graph uses an Euler sampler.",
      statement_count: 1, landed_op_count: 0,
      statements: [{ op_kind: "done", status: "done" }],
      done_summary: "Answered: graph uses Euler sampler.",
    }).canonical;

    const reviseCanonical = makeCanonicalTurn({
      session_id: "sess-multi", turn_id: "0002", turn_number: 2,
      status: "done", route: "revise",
      message: "Added KScheduler node.",
      statement_count: 3, landed_op_count: 2,
      statements: [
        { op_kind: "add_node", status: "done", message: "Added KScheduler", landed: true, ok: true },
        { op_kind: "connect", status: "done", message: "Connected", landed: true, ok: true },
        { op_kind: "done", status: "done" },
      ],
      done_summary: "Added scheduler node.",
    }).canonical;

    const researchCanonical = makeCanonicalTurn({
      session_id: "sess-multi", turn_id: "0003", turn_number: 3,
      status: "done", route: "research",
      message: "PIL is compatible with 2.1 but requires additional nodes for 3.0.",
      statement_count: 1, landed_op_count: 0,
      statements: [{ op_kind: "done", status: "done" }],
      done_summary: "Researched PIL compatibility.",
    }).canonical;

    panel.state.chatMessages = [
      { role: "agent", text: respondCanonical.outcome.summary, turn_id: "0001", source: "agent-edit" },
      { role: "agent", text: reviseCanonical.outcome.summary, turn_id: "0002", source: "agent-edit" },
      { role: "agent", text: researchCanonical.outcome.summary, turn_id: "0003", source: "agent-edit" },
    ];
    panel.state.turns = [];

    mod.resetThreadRenderState(panel);
    mod.markAgentPanelDirty(panel, ["THREAD"]);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const text = harness.textDump();
    // Verify all three messages render in order
    assert.match(text, /graph uses Euler sampler/i);
    assert.match(text, /Added scheduler node/i);
    assert.match(text, /Researched PIL compatibility/i);

    // Confirm chronological ordering: respond text before revise text before research text
    const posRespond = text.indexOf("Euler sampler");
    const posRevise = text.indexOf("scheduler node");
    const posResearch = text.indexOf("PIL compatibility");
    assert.ok(posRespond < posRevise, "respond message must appear before revise message");
    assert.ok(posRevise < posResearch, "revise message must appear before research message");

    // No internal leakage
    assert.doesNotMatch(text, /no_candidate_reason/i);
    assert.doesNotMatch(text, /route_not_applyable/i);
  } finally {
    await harness.dispose();
  }
});

test("DOM: candidate-route controls are preserved for revise route", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const { canonical } = makeCanonicalTurn({
      session_id: "sess-revise-ui",
      turn_id: "0001",
      turn_number: 1,
      status: "done",
      route: "revise",
      message: "Added upscale node and configured pipeline.",
      statement_count: 3,
      landed_op_count: 2,
      statements: [
        { op_kind: "add_node", status: "done", message: "Added node", landed: true, ok: true },
        { op_kind: "set_field", status: "done", message: "Set cfg", landed: true, ok: true },
        { op_kind: "done", status: "done" },
      ],
      done_summary: "Added upscale node and configured cfg.",
    });

    assert.equal(canonical.outcome.kind, "done");
    assert.ok(canonical.outcome.landed_ops >= 2);

    panel.state.chatMessages = [
      { role: "agent", text: canonical.outcome.summary, turn_id: "0001", source: "agent-edit" },
    ];
    panel.state.turns = [];

    mod.resetThreadRenderState(panel);
    mod.markAgentPanelDirty(panel, ["THREAD"]);
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const text = harness.textDump();
    assert.match(text, /Added upscale node and configured cfg/i);
    assert.doesNotMatch(text, /not landed/i);

    // Apply/Reject buttons exist (candidate route preserves them)
    const applyBtn = harness.document.getElementById("vibecomfy-agent-panel-apply");
    const rejectBtn = harness.document.getElementById("vibecomfy-agent-panel-reject");
    assert.ok(applyBtn, "apply button must exist for candidate route");
    assert.ok(rejectBtn, "reject button must exist for candidate route");

    // No internal leakage
    assert.doesNotMatch(text, /no_candidate_reason/i);
    assert.doesNotMatch(text, /route_not_applyable/i);
  } finally {
    await harness.dispose();
  }
});

test("DOM: all non-applyable routes (clarify, inspect, respond, research) suppress candidate controls", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
    },
  });

  try {
    const mod = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    await waitFor(() => harness.requests.some((r) => r.url === "/vibecomfy/agent/status?route=auto"));

    const panel = mod.ensureAgentPanel();

    const routeMessages = {
      clarify: "Should I replace the sampler with an upscaler?",
      inspect: "This workflow loads an image, applies VAE decode, and saves the output.",
      respond: "The graph uses an Euler sampler with cfg=7.5.",
      research: "LTX Video supports i2v at 768px; PIL is unnecessary for this pipeline.",
    };

    for (const [route, msg] of Object.entries(routeMessages)) {
      const { canonical } = makeCanonicalTurn({
        session_id: `sess-${route}-ui`,
        turn_id: "0001",
        turn_number: 1,
        status: route === "clarify" ? "clarify" : "done",
        route,
        message: msg,
        clarification_required: route === "clarify" ? true : false,
        clarification_message: route === "clarify" ? msg : null,
        statement_count: 1,
        landed_op_count: 0,
        statements: route === "clarify"
          ? [{ op_kind: "clarify", status: "active", message: "Need clarification" }]
          : [{ op_kind: "done", status: "done", message: "Turn complete" }],
        done_summary: route === "clarify" ? null : `Completed: ${route}.`,
      });

      panel.state.sessionId = `sess-${route}-ui`;
      panel.state.chatMessages = [
        { role: "agent", text: canonical.outcome.summary || msg, turn_id: "0001", source: "agent-edit" },
      ];
      panel.state.turns = [];

      mod.resetThreadRenderState(panel);
      mod.markAgentPanelDirty(panel, ["THREAD"]);
      mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

      const text = harness.textDump();
      const applyBtn = harness.document.getElementById("vibecomfy-agent-panel-apply");
      const rejectBtn = harness.document.getElementById("vibecomfy-agent-panel-reject");

      assert.equal(applyBtn.disabled, true, `apply must be disabled for ${route} route`);
      assert.equal(rejectBtn.disabled, true, `reject must be disabled for ${route} route`);
      assert.doesNotMatch(text, /no_candidate_reason/i, `${route} route must not leak no_candidate_reason`);
      assert.doesNotMatch(text, /route_not_applyable/i, `${route} route must not leak route_not_applyable`);
    }
  } finally {
    await harness.dispose();
  }
});
