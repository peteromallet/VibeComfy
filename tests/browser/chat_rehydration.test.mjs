import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  PANEL_STATE,
  createAgentEditState,
  ingestChatRehydratePayload,
  transition,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";
import { readFieldChanges } from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract.js";
import { readRoundtripFieldChanges } from "../../vibecomfy/comfy_nodes/web/agent_turn_reducer.js";
import { createBrowserHarness } from "./harness.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");

function source(name) {
  return readFileSync(path.join(WEB_ROOT, name), "utf8");
}

const roundtripSource = source("vibecomfy_roundtrip.js");
const lifecycleSource = source("agent_edit_lifecycle.js");

function sourceBetween(moduleSource, startMarker, endMarker) {
  const start = moduleSource.indexOf(startMarker);
  const end = moduleSource.indexOf(endMarker, start + startMarker.length);
  assert.notEqual(start, -1, `missing source marker: ${startMarker}`);
  assert.notEqual(end, -1, `missing source marker: ${endMarker}`);
  return moduleSource.slice(start, end);
}

function snakePropertyReferences(block, owner) {
  const escapedOwner = owner.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(String.raw`\b${escapedOwner}\.([A-Za-z0-9_]*_[A-Za-z0-9_]*)`, "g");
  return [...new Set([...block.matchAll(pattern)].map((match) => match[1]))].sort();
}

function assertAliasReferenceOrder(block, { canonical, wire, precedence }, owner) {
  const propertyIndex = block.indexOf(`${canonical}:`);
  const camelIndex = block.indexOf(`${owner}.${canonical}`, propertyIndex);
  const snakeIndex = block.indexOf(`${owner}.${wire}`, propertyIndex);
  assert.notEqual(propertyIndex, -1, `missing canonical output property ${canonical}`);
  assert.notEqual(camelIndex, -1, `missing ${owner}.${canonical}`);
  assert.notEqual(snakeIndex, -1, `missing ${owner}.${wire}`);
  if (precedence === "snake-first") {
    assert.ok(snakeIndex < camelIndex, `${wire} must remain ahead of ${canonical}`);
  } else {
    assert.ok(camelIndex < snakeIndex, `${canonical} must remain ahead of ${wire}`);
  }
}

const TOP_LEVEL_ALIAS_TABLE = Object.freeze([
  { canonical: "sessionId", wire: "session_id", precedence: "camel-first" },
  { canonical: "sessionPath", wire: "session_path", precedence: "camel-first" },
  { canonical: "detailJsonPath", wire: "detail_json_path", precedence: "camel-first" },
  { canonical: "sessionPathResolved", wire: "session_path_resolved", precedence: "camel-first" },
  { canonical: "detailJsonPathResolved", wire: "detail_json_path_resolved", precedence: "camel-first" },
  { canonical: "latestTurnId", wire: "latest_turn_id", precedence: "camel-first" },
  { canonical: "baselineTurnId", wire: "baseline_turn_id", precedence: "camel-first" },
  { canonical: "baselineGraphHash", wire: "baseline_graph_hash", precedence: "camel-first" },
  { canonical: "baselineGraphHashKind", wire: "baseline_graph_hash_kind", precedence: "camel-first" },
  { canonical: "baselineGraphHashVersion", wire: "baseline_graph_hash_version", precedence: "camel-first" },
  { canonical: "baselineSource", wire: "baseline_source", precedence: "camel-first" },
  { canonical: "baselineRebaselineId", wire: "baseline_rebaseline_id", precedence: "camel-first" },
  { canonical: "baselineGraphSourcePath", wire: "baseline_graph_source_path", precedence: "camel-first" },
  { canonical: "pipelineMode", wire: "pipeline_mode", precedence: "camel-first" },
  { canonical: "latestTurnLifecycle", wire: "latest_turn_lifecycle", precedence: "camel-first" },
  { canonical: "latestCandidate", wire: "latest_candidate", precedence: "camel-first" },
]);

const LIFECYCLE_ALIAS_TABLE = Object.freeze([
  { canonical: "turnId", wire: "turn_id", precedence: "camel-first" },
  { canonical: "agentEditProtocol", wire: "agent_edit_protocol", precedence: "camel-first" },
  { canonical: "transactionReceipts", wire: "transaction_receipts", precedence: "camel-first" },
  // The candidate reader receives a single snake-keyed adapter object; its
  // source expression intentionally checks the wire key before the camel key.
  { canonical: "candidateTransaction", wire: "candidate_transaction", precedence: "snake-first" },
]);

const MESSAGE_ALIAS_TABLE = Object.freeze([
  { canonical: "entryType", wire: "entry_type", precedence: "camel-first" },
]);

function emptyFieldChangeBundle() {
  return {
    directChanges: [],
    outcomeChanges: [],
    legacyChanges: [],
    batchTurnChanges: [],
    all: [],
  };
}

let normalizeFieldChangesFromMessageForTest = null;

function fieldChangeNormalizer() {
  if (normalizeFieldChangesFromMessageForTest) {
    return normalizeFieldChangesFromMessageForTest;
  }
  // These transport helpers are deliberately private. Execute their exact
  // production source with the two real imported selectors, rather than adding
  // a production-only export merely for tests.
  const helperSource = sourceBetween(
    roundtripSource,
    "function _isFieldChangeLike",
    "\nfunction changeDetailsForMessage",
  );
  normalizeFieldChangesFromMessageForTest = Function(
    "readRoundtripFieldChanges",
    "readFieldChanges",
    `${helperSource}\nreturn normalizeFieldChangesFromMessage;`,
  )(readRoundtripFieldChanges, readFieldChanges);
  return normalizeFieldChangesFromMessageForTest;
}

function readyStatusResponse() {
  return {
    status: 200,
    body: {
      ok: true,
      ready: true,
      provider_available: true,
      route: "deepseek",
      requested_route: "auto",
      route_options: {
        auto: {
          requested_route: "auto",
          normalized_route: "deepseek",
          browser_api_key_allowed: false,
        },
      },
    },
  };
}

async function waitFor(predicate, label, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.fail(`timed out waiting for ${label}`);
}

async function withRoundtripRehydrate(rawPayload, callback, { savedSessionId = "saved-rehydrate-route" } = {}) {
  const chatUrl = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(savedSessionId)}`;
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": readyStatusResponse(),
      [chatUrl]: { status: 200, body: rawPayload },
    },
  });
  globalThis.localStorage.setItem("vibecomfy_active_session_id", savedSessionId);

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();
    const panel = extensionModule.ensureAgentPanel();
    await callback({ harness, extensionModule, panel, chatUrl, openPanel: async () => {
      await harness.invokeCommand("VibeComfy.AgentEdit");
      await waitFor(
        () => harness.requests.some((request) => request.url === chatUrl)
          && panel.state.chatRehydratePending === false
          && (panel.state.chatLoaded === true || typeof panel.state.chatError === "string"),
        "chat rehydrate completion",
      );
    } });
  } finally {
    await harness.dispose();
  }
}

test("aliases: the transport normalizer's exact snake/camel table and precedence stay pinned", () => {
  const payloadBlock = sourceBetween(
    roundtripSource,
    "function normalizeChatRehydratePayload",
    "\nfunction normalizeAuxiliaryAgentPayload",
  );
  const lifecycleBlock = sourceBetween(
    payloadBlock,
    "latestTurnLifecycle:",
    "\n    latestCandidate:",
  );
  const messageBlock = sourceBetween(
    roundtripSource,
    "function normalizeChatMessagePayload",
    "\nfunction normalizeChatRehydratePayload",
  );

  assert.deepEqual(
    snakePropertyReferences(payloadBlock, "rawPayload"),
    TOP_LEVEL_ALIAS_TABLE.map(({ wire }) => wire).sort(),
  );
  assert.deepEqual(
    snakePropertyReferences(lifecycleBlock, "lifecycle"),
    LIFECYCLE_ALIAS_TABLE.map(({ wire }) => wire).sort(),
  );
  assert.deepEqual(
    snakePropertyReferences(messageBlock, "message"),
    MESSAGE_ALIAS_TABLE.map(({ wire }) => wire).sort(),
  );

  for (const alias of TOP_LEVEL_ALIAS_TABLE) {
    assertAliasReferenceOrder(payloadBlock, alias, "rawPayload");
  }
  for (const alias of LIFECYCLE_ALIAS_TABLE) {
    assertAliasReferenceOrder(lifecycleBlock, alias, "lifecycle");
  }
  for (const alias of MESSAGE_ALIAS_TABLE) {
    assertAliasReferenceOrder(messageBlock, alias, "message");
  }

  assert.match(payloadBlock, /ok:\s*typeof rawPayload\.ok === "boolean" \? rawPayload\.ok : null/);
  assert.match(payloadBlock, /exists:\s*typeof rawPayload\.exists === "boolean" \? rawPayload\.exists : null/);
  assert.match(payloadBlock, /messages:\s*Array\.isArray\(rawPayload\.messages\)/);
  assert.match(messageBlock, /readRoundtripTurnIdentity\(response\)/);
  assert.match(messageBlock, /readTurnIdentity\(message,[\s\S]*allowLegacy:\s*true/);
});

test("aliases: a snake_case wire payload reaches canonical lifecycle state", async () => {
  const snakePayload = {
    ok: true,
    exists: true,
    session_id: "session-snake",
    session_path: "out/sessions/session-snake",
    detail_json_path: "out/sessions/session-snake/detail.json",
    session_path_resolved: "/resolved/session-snake",
    detail_json_path_resolved: "/resolved/session-snake/detail.json",
    latest_turn_id: "turn-0009",
    baseline_turn_id: "turn-0008",
    baseline_graph_hash: "hash-snake",
    baseline_graph_hash_kind: "structural",
    baseline_graph_hash_version: 2,
    baseline_source: "accepted",
    baseline_rebaseline_id: "rebaseline-snake",
    baseline_graph_source_path: "/graphs/snake.json",
    latest_turn_lifecycle: {
      turn_id: "turn-0009",
      state: "finalized",
      disposition: "finalized",
      agent_edit_protocol: "v2_delta",
      transaction_receipts: [{ event_type: "finalized", plan_hash: "plan-snake" }],
    },
    messages: [
      {
        role: "user",
        text: "first snake message",
        turn_id: "turn-0009",
        local_id: "local-snake",
        progress_label: "Queued",
        status: "submitted",
      },
      {
        role: "agent",
        text: "second snake message",
        turn_id: "turn-0009",
        entry_type: "response",
        status: "finalized",
        field_changes: [
          { uid: "node-snake", field_path: "inputs.prompt", old: "before", new: "after" },
        ],
      },
    ],
  };

  await withRoundtripRehydrate(snakePayload, async ({ panel, openPanel }) => {
    await openPanel();

    assert.deepEqual(panel.state.chatMessages, [
      {
        role: "user",
        text: "first snake message",
        turn_id: "turn-0009",
        session_id: "session-snake",
        local_id: "local-snake",
        progress_label: "Queued",
      },
      {
        role: "agent",
        text: "second snake message",
        turn_id: "turn-0009",
        session_id: "session-snake",
      },
    ]);
    assert.equal(panel.state.responseDetails["turn-0009"].turn.status, "finalized");
    assert.equal(panel.state.sessionId, "session-snake");
    assert.deepEqual(
      [
        panel.state.chatSessionPath,
        panel.state.chatDetailJsonPath,
        panel.state.chatSessionPathResolved,
        panel.state.chatDetailJsonPathResolved,
      ],
      [
        "out/sessions/session-snake",
        "out/sessions/session-snake/detail.json",
        "/resolved/session-snake",
        "/resolved/session-snake/detail.json",
      ],
    );
    assert.deepEqual(
      [
        panel.state.baselineTurnId,
        panel.state.baselineGraphHash,
        panel.state.baselineGraphHashKind,
        panel.state.baselineGraphHashVersion,
        panel.state.baselineSource,
        panel.state.baselineRebaselineId,
        panel.state.baselineGraphSourcePath,
      ],
      [
        "turn-0008",
        "hash-snake",
        "structural",
        2,
        "accepted",
        "rebaseline-snake",
        "/graphs/snake.json",
      ],
    );
    assert.equal(panel.state.phase, PANEL_STATE.FINALIZED);
    assert.equal(panel.state.turnId, "turn-0009");
    assert.deepEqual(
      [panel.state.applyAllowed, panel.state.canvasApplyAllowed, panel.state.queueAllowed],
      [false, false, false],
    );
    assert.deepEqual(
      {
        turnId: panel.state.debugPayload.rehydrated_terminal_disposition.turnId,
        agentEditProtocol: panel.state.debugPayload.rehydrated_terminal_disposition.agentEditProtocol,
        transactionReceipts:
          panel.state.debugPayload.rehydrated_terminal_disposition.transactionReceipts,
      },
      {
        turnId: "turn-0009",
        agentEditProtocol: "v2_delta",
        transactionReceipts: [{ event_type: "finalized", plan_hash: "plan-snake" }],
      },
    );
  });
});

test("aliases: camelCase wins when both top-level and lifecycle aliases are present", async () => {
  const camelPayload = {
    ok: true,
    exists: true,
    sessionId: "session-camel",
    session_id: "session-shadowed",
    sessionPath: "out/sessions/session-camel",
    session_path: "out/sessions/session-shadowed",
    detailJsonPath: "out/sessions/session-camel/detail.json",
    detail_json_path: "out/sessions/session-shadowed/detail.json",
    sessionPathResolved: "/resolved/session-camel",
    session_path_resolved: "/resolved/session-shadowed",
    detailJsonPathResolved: "/resolved/session-camel/detail.json",
    detail_json_path_resolved: "/resolved/session-shadowed/detail.json",
    latestTurnId: "turn-camel",
    latest_turn_id: "turn-shadowed",
    baselineTurnId: "baseline-camel",
    baseline_turn_id: "baseline-shadowed",
    baselineGraphHash: "hash-camel",
    baseline_graph_hash: "hash-shadowed",
    baselineGraphHashKind: "layout",
    baseline_graph_hash_kind: "shadowed-kind",
    baselineGraphHashVersion: 0,
    baseline_graph_hash_version: 99,
    baselineSource: "rebaseline",
    baseline_source: "shadowed-source",
    baselineRebaselineId: "rebaseline-camel",
    baseline_rebaseline_id: "rebaseline-shadowed",
    baselineGraphSourcePath: "/graphs/camel.json",
    baseline_graph_source_path: "/graphs/shadowed.json",
    latestTurnLifecycle: {
      turnId: "turn-camel",
      turn_id: "turn-nested-shadowed",
      state: "rejected",
      disposition: "rejected",
      agentEditProtocol: "camel-protocol",
      agent_edit_protocol: "shadowed-protocol",
      transactionReceipts: [{ event_type: "rejected", source: "camel" }],
      transaction_receipts: [{ event_type: "rejected", source: "shadowed" }],
    },
    latest_turn_lifecycle: {
      turn_id: "turn-object-shadowed",
      state: "rollback_complete",
      disposition: "rolled_back",
    },
    messages: [
      {
        role: "agent",
        text: "camel message",
        turnId: "turn-camel",
        sessionId: "message-session-camel",
        localId: "local-camel",
        progressLabel: "Done",
        entryType: "response",
        status: "rejected",
        changes: [
          { uid: "node-camel", fieldPath: "widgets.seed", old: 1, new: 2 },
        ],
      },
    ],
  };

  await withRoundtripRehydrate(camelPayload, async ({ panel, openPanel }) => {
    await openPanel();

    assert.equal(panel.state.sessionId, "session-camel");
    assert.deepEqual(panel.state.chatMessages, [
      {
        role: "agent",
        text: "camel message",
        turn_id: "turn-camel",
        session_id: "message-session-camel",
        local_id: "local-camel",
        progress_label: "Done",
      },
    ]);
    assert.deepEqual(
      [
        panel.state.chatSessionPath,
        panel.state.chatDetailJsonPath,
        panel.state.chatSessionPathResolved,
        panel.state.chatDetailJsonPathResolved,
      ],
      [
        "out/sessions/session-camel",
        "out/sessions/session-camel/detail.json",
        "/resolved/session-camel",
        "/resolved/session-camel/detail.json",
      ],
    );
    assert.deepEqual(
      [
        panel.state.baselineTurnId,
        panel.state.baselineGraphHash,
        panel.state.baselineGraphHashKind,
        panel.state.baselineGraphHashVersion,
        panel.state.baselineSource,
        panel.state.baselineRebaselineId,
        panel.state.baselineGraphSourcePath,
      ],
      [
        "baseline-camel",
        "hash-camel",
        "layout",
        0,
        "rebaseline",
        "rebaseline-camel",
        "/graphs/camel.json",
      ],
    );
    assert.equal(panel.state.phase, PANEL_STATE.IDLE);
    assert.equal(panel.state.turnId, "turn-camel");
    assert.deepEqual(
      {
        turnId: panel.state.debugPayload.rehydrated_terminal_disposition.turnId,
        agentEditProtocol: panel.state.debugPayload.rehydrated_terminal_disposition.agentEditProtocol,
        transactionReceipts:
          panel.state.debugPayload.rehydrated_terminal_disposition.transactionReceipts,
      },
      {
        turnId: "turn-camel",
        agentEditProtocol: "camel-protocol",
        transactionReceipts: [{ event_type: "rejected", source: "camel" }],
      },
    );
  });
});

test("field-changes: every supported source and fieldPath alias maps to the canonical bundle", () => {
  const normalize = fieldChangeNormalizer();
  const actual = normalize({
    changes: [
      { uid: 12, fieldPath: "inputs.prompt", old: "before", new: "after" },
    ],
    outcome: {
      changes: [
        { uid: "node-outcome", field_path: "widgets.seed", old: 1, new: 2 },
      ],
    },
    field_changes: [
      { uid: "node-legacy", fieldPath: "mode", old: 0, new: 4 },
    ],
    change_details: {
      batch_turns: [
        {
          turn_number: 3,
          field_changes: [
            { uid: "node-batch-snake", field_path: "inputs.image", old: null, new: "7:0" },
          ],
        },
        {
          turnNumber: 4,
          fieldChanges: [
            { uid: "node-batch-camel", fieldPath: "widgets.steps", old: 20, new: 30 },
          ],
        },
      ],
    },
  });

  const direct = { uid: "12", field_path: "inputs.prompt", old: "before", new: "after" };
  const outcome = { uid: "node-outcome", field_path: "widgets.seed", old: 1, new: 2 };
  const legacy = { uid: "node-legacy", field_path: "mode", old: 0, new: 4 };
  const batchSnake = {
    uid: "node-batch-snake",
    field_path: "inputs.image",
    old: undefined,
    new: "7:0",
  };
  const batchCamel = { uid: "node-batch-camel", field_path: "widgets.steps", old: 20, new: 30 };
  assert.deepEqual(actual, {
    directChanges: [direct],
    outcomeChanges: [outcome],
    legacyChanges: [legacy],
    batchTurnChanges: [
      { turn_number: 3, changes: [batchSnake] },
      { turn_number: 4, changes: [batchCamel] },
    ],
    all: [direct, outcome, legacy, batchSnake, batchCamel],
  });

  const camelOuterBatch = {
    uid: "node-camel-outer-batch",
    field_path: "widgets.cfg",
    old: 6,
    new: 7,
  };
  assert.deepEqual(
    normalize({
      changeDetails: {
        batchTurns: [
          {
            turnNumber: 8,
            fieldChanges: [
              { uid: "node-camel-outer-batch", fieldPath: "widgets.cfg", old: 6, new: 7 },
            ],
          },
        ],
      },
    }),
    {
      directChanges: [],
      outcomeChanges: [],
      legacyChanges: [],
      batchTurnChanges: [{ turn_number: 8, changes: [camelOuterBatch] }],
      all: [camelOuterBatch],
    },
  );
});

test("field-changes: all compacts net changes by uid and field_path without rewriting source buckets", () => {
  const normalize = fieldChangeNormalizer();
  const actual = normalize({
    changes: [
      { uid: "node-net-zero", field_path: "seed", old: 0, new: 1 },
      { uid: "node-updated", field_path: "prompt", old: "a", new: "b" },
      { uid: "node-stable", field_path: "steps", old: 10, new: 11 },
    ],
    outcome: {
      changes: [
        { uid: "node-updated", field_path: "prompt", old: "b", new: "c" },
        { uid: "node-net-zero", field_path: "seed", old: 1, new: 0 },
      ],
    },
    field_changes: [
      { uid: "node-noop", field_path: "mode", old: { value: 2 }, new: { value: 2 } },
    ],
    batch_turns: [
      {
        turn_number: 5,
        field_changes: [
          { uid: "node-updated", field_path: "prompt", old: "c", new: "d" },
        ],
      },
    ],
  });

  assert.equal(actual.directChanges.length, 3);
  assert.equal(actual.outcomeChanges.length, 2);
  assert.equal(actual.legacyChanges.length, 1, "source buckets retain no-op entries");
  assert.equal(actual.batchTurnChanges[0].changes.length, 1);
  assert.deepEqual(actual.all, [
    { uid: "node-updated", field_path: "prompt", old: "a", new: "d" },
    { uid: "node-stable", field_path: "steps", old: 10, new: 11 },
  ]);
});

test("field-changes: empty, malformed, and missing-field inputs fail closed", () => {
  const normalize = fieldChangeNormalizer();
  for (const value of [undefined, null, "not-an-object", 42, [], {}]) {
    assert.deepEqual(normalize(value), emptyFieldChangeBundle());
  }
  assert.deepEqual(
    normalize({ fieldChanges: [{ uid: "camel-container", fieldPath: "ignored", old: 1, new: 2 }] }),
    emptyFieldChangeBundle(),
    "message.fieldChanges is not a supported top-level source alias",
  );

  const malformed = normalize({
    changes: [
      null,
      7,
      {},
      { uid: "", fieldPath: "inputs.prompt", old: 1, new: 2 },
      { uid: "node-empty-path", field_path: "", old: 1, new: 2 },
      { uid: "node-wrong-contract", field: "inputs.prompt", previous: 1, current: 2 },
      { uid: "node-missing-values", field_path: "inputs.prompt" },
    ],
  });
  assert.deepEqual(malformed.directChanges, [
    { uid: "node-missing-values", field_path: "inputs.prompt", old: undefined, new: undefined },
  ]);
  assert.deepEqual(malformed.outcomeChanges, []);
  assert.deepEqual(malformed.legacyChanges, []);
  assert.deepEqual(malformed.batchTurnChanges, []);
  assert.deepEqual(malformed.all, [], "equal missing old/new values compact to a net no-op");
});

test("ingestion e2e: fresh projection preserves order and commits only canonical transcript fields", () => {
  const panel = {
    state: {
      ...createAgentEditState(),
      chatMessages: [{ role: "user", text: "replace me", local_id: "old-local" }],
      chatLoaded: false,
      chatError: "old error",
    },
  };
  const payload = {
    sessionId: "session-fresh",
    messages: [
      {
        role: "agent",
        reply: "agent arrives first",
        turnId: "turn-0002",
        timestamp: "2026-08-11T10:02:00Z",
        status: "complete",
        debug_payload: { must_not_leak: true },
      },
      {
        role: "user",
        message: "user arrives second",
        turn_id: "turn-0001",
        localId: "local-fresh",
        progressLabel: "Done",
        status: "submitted",
      },
    ],
  };
  const beforeIngest = structuredClone(panel.state);
  const ingested = ingestChatRehydratePayload(panel.state, payload);

  assert.deepEqual(panel.state, beforeIngest, "pure ingest must not mutate panel state");
  assert.deepEqual(ingested.chatMessages, [
    {
      role: "agent",
      text: "agent arrives first",
      turn_id: "turn-0002",
      session_id: "session-fresh",
      timestamp: "2026-08-11T10:02:00Z",
    },
    {
      role: "user",
      text: "user arrives second",
      turn_id: "turn-0001",
      session_id: "session-fresh",
      local_id: "local-fresh",
      progress_label: "Done",
    },
  ]);
  assert.equal(ingested.responseDetails["turn-0002"].turn.status, "complete");
  assert.equal(ingested.responseDetails["turn-0001"].turn.status, "submitted");

  const obligations = transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    ...payload,
    ingestedChatRehydratePayload: ingested,
  });
  assert.deepEqual(panel.state.chatMessages, ingested.chatMessages);
  assert.deepEqual(panel.state.transcriptMessages, ingested.chatMessages);
  assert.equal(panel.state.chatLoaded, true);
  assert.equal(panel.state.chatRehydratePending, false);
  assert.equal(panel.state.chatError, null);
  assert.equal(panel.state.sessionId, "session-fresh");
  assert.equal(obligations.persistSession, "session-fresh");
});

test("ingestion e2e: overlapping submit rehydrate suppresses identity matches and is idempotent", () => {
  const panel = {
    state: {
      ...createAgentEditState(),
      phase: PANEL_STATE.SUBMITTING,
      submitEpoch: 7,
      chatMessages: [
        {
          role: "user",
          text: "optimistic duplicate",
          turn_id: "turn-overlap",
          optimistic: true,
          submit_epoch: 7,
        },
        {
          role: "agent",
          text: "keep current optimistic",
          turn_id: "turn-pending",
          pending_response: true,
          submit_epoch: 7,
        },
        {
          role: "agent",
          text: "drop stale optimistic",
          turn_id: "turn-stale",
          executor_pending: true,
          submit_epoch: 6,
        },
        {
          role: "agent",
          text: "drop nonoptimistic",
          turn_id: "turn-local-durable",
        },
        {
          role: "agent",
          text: "drop identity-free optimistic",
          optimistic: true,
          submit_epoch: 7,
        },
      ],
    },
  };
  const payload = {
    sessionId: "session-overlap",
    messages: [
      { role: "agent", text: "durable first", turn_id: "turn-before" },
      { role: "user", text: "durable overlap", turn_id: "turn-overlap" },
    ],
  };

  const firstIngest = ingestChatRehydratePayload(panel.state, payload);
  const expected = [
    {
      role: "agent",
      text: "durable first",
      turn_id: "turn-before",
      session_id: "session-overlap",
    },
    {
      role: "user",
      text: "durable overlap",
      turn_id: "turn-overlap",
      session_id: "session-overlap",
    },
    {
      role: "agent",
      text: "keep current optimistic",
      turn_id: "turn-pending",
      pending_response: true,
      submit_epoch: 7,
    },
  ];
  assert.deepEqual(firstIngest.chatMessages, expected);
  transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    ...payload,
    ingestedChatRehydratePayload: firstIngest,
  });
  assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING);
  assert.deepEqual(panel.state.chatMessages, expected);

  const secondIngest = ingestChatRehydratePayload(panel.state, payload);
  assert.deepEqual(secondIngest.chatMessages, expected);
  transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    ...payload,
    ingestedChatRehydratePayload: secondIngest,
  });
  assert.deepEqual(panel.state.chatMessages, expected);
  assert.equal(panel.state.chatMessages.length, 3, "re-ingestion must not accumulate overlap duplicates");
});

test("ingestion e2e: terminal lifecycle disposition clears candidate authority and disables every gate", () => {
  const panel = {
    state: {
      ...createAgentEditState(),
      phase: PANEL_STATE.AWAITING_REVIEW,
      sessionId: "session-terminal",
      turnId: "turn-terminal",
      candidateGraph: { nodes: [{ id: 1 }] },
      candidateGraphHash: "candidate-hash",
      applyAllowed: true,
      canvasApplyAllowed: true,
      queueAllowed: true,
      chatMessages: [],
    },
  };
  const payload = {
    sessionId: "session-terminal",
    latestTurnId: "turn-terminal",
    latestCandidate: null,
    latestTurnLifecycle: {
      turnId: "turn-terminal",
      state: "rollback_complete",
      disposition: "rolled_back",
      transactionReceipts: [
        {
          event_type: "rollback_complete",
          receipt: { plan_hash: "terminal-plan", rollback_at: "2026-08-11T12:00:00Z" },
        },
      ],
    },
    messages: [
      { role: "agent", text: "rolled back", turn_id: "turn-terminal", status: "terminal" },
    ],
  };
  const ingested = ingestChatRehydratePayload(panel.state, payload);
  const obligations = transition(panel, "CHAT_REHYDRATE_SUCCESS", {
    ...payload,
    ingestedChatRehydratePayload: ingested,
  });

  assert.equal(panel.state.phase, PANEL_STATE.ROLLBACK_COMPLETE);
  assert.equal(panel.state.candidateGraph, null);
  assert.equal(panel.state.candidateGraphHash, null);
  assert.deepEqual(
    [panel.state.applyAllowed, panel.state.canvasApplyAllowed, panel.state.queueAllowed],
    [false, false, false],
  );
  assert.deepEqual(panel.state.rollbackReceipt, {
    plan_hash: "terminal-plan",
    rollback_at: "2026-08-11T12:00:00Z",
  });
  assert.equal(panel.state.responseDetails["turn-terminal"].turn.status, "terminal");
  assert.equal(
    panel.state.debugPayload.rehydrated_terminal_disposition.disposition,
    "rolled_back",
  );
  assert.equal(obligations.invalidateCandidate, true);
  assert.equal(obligations.clearCandidatePreview, true);
  assert.equal(obligations.queueGuardClear, true);
});

test("ingestion e2e: malformed raw transport data preserves the existing canonical conversation", async () => {
  await withRoundtripRehydrate("not-an-object", async ({ panel, openPanel }) => {
    const existing = [
      {
        role: "user",
        text: "preserve me",
        turn_id: "turn-existing",
        session_id: "session-existing",
      },
      {
        role: "agent",
        text: "preserve me too",
        turn_id: "turn-existing",
        session_id: "session-existing",
      },
    ];
    Object.assign(panel.state, {
      sessionId: "session-existing",
      chatMessages: structuredClone(existing),
      transcriptMessages: structuredClone(existing),
      chatLoaded: true,
      chatError: null,
      chatSessionPath: "old/session/path",
      chatDetailJsonPath: "old/detail/path",
    });

    await openPanel();

    assert.deepEqual(panel.state.chatMessages, existing);
    assert.deepEqual(panel.state.transcriptMessages, existing);
    assert.equal(panel.state.sessionId, "session-existing");
    assert.equal(panel.state.chatLoaded, false);
    assert.equal(panel.state.chatRehydratePending, false);
    assert.match(panel.state.chatError, /chat endpoint must return an object/);
    assert.equal(panel.state.chatSessionPath, null);
    assert.equal(panel.state.chatDetailJsonPath, null);
  });
});

test("boundary: transport normalizers stay roundtrip-owned and ingest stays lifecycle-owned", () => {
  assert.match(roundtripSource, /^function normalizeChatRehydratePayload\(/m);
  assert.match(roundtripSource, /^function normalizeFieldChangesFromMessage\(/m);
  assert.doesNotMatch(lifecycleSource, /^\s*(?:export\s+)?function normalizeChatRehydratePayload\(/m);
  assert.doesNotMatch(lifecycleSource, /^\s*(?:export\s+)?function normalizeFieldChangesFromMessage\(/m);

  assert.match(lifecycleSource, /^export function ingestChatRehydratePayload\(/m);
  assert.doesNotMatch(roundtripSource, /^\s*(?:export\s+)?function ingestChatRehydratePayload\(/m);
  assert.match(
    roundtripSource,
    /ingestChatRehydratePayload\(\s*panel\.state,\s*lifecyclePayload,?\s*\)/,
  );
});
