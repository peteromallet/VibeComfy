import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createBrowserHarness } from "./harness.mjs";
import { canonicalJsonString, sha256Hex, sha256HexFromString } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";
import { makeValidCandidateTransactionV2, bindTransactionHashes } from "./authority_factory.mjs";
import { normalizeCandidateTransaction } from "../../vibecomfy/comfy_nodes/web/agent_edit_transaction.js";

function approvedFixture() {
  const apiProjection = { "1": { class_type: "Input", inputs: {} } };
  const uiProjection = { nodes: [], links: [] };
  const record = {
    revision_id: "rev-queue-1",
    selected_variant: null,
    input_binding: {},
    api_projection: apiProjection,
    ui_projection: uiProjection,
    api_digest: sha256Hex(apiProjection),
  };
  const canonical = canonicalJsonString(record);
  return {
    canonical,
    receipt: {
      revision_id: record.revision_id,
      api_digest: record.api_digest,
      record_digest: sha256HexFromString(canonical),
    },
  };
}

const PYTHON_CANONICAL = "{\"api_digest\":\"f4ca373f764462eef8bf6670712b4748516ca0dd1d1a8c375acec29e7f933a34\",\"api_projection\":{\"workflow_revision\":\"t19-python-fixed\"},\"input_binding\":{},\"revision_id\":\"t19-python-revision\",\"selected_variant\":null,\"ui_projection\":{}}";
const PYTHON_CANONICAL_DIGEST = "e188fc940f054123b290472d04e5412d942e789cd6f31a105262112f13b1c500";

function approvedContext(fixture, panel, overrides = {}) {
  const revisionId = overrides.revisionId ?? fixture.receipt.revision_id;
  const parentRevision = overrides.parentRevision ?? "";
  const apiDigest = overrides.apiDigest ?? fixture.receipt.api_digest;
  const recordDigest = overrides.recordDigest ?? fixture.receipt.record_digest;
  return {
    scopeId: "queue-scope",
    scopeActivation: panel.state.scopeActivationEpoch ?? 0,
    sessionId: "queue-session",
    turnId: "queue-turn",
    queueAllowed: true,
    revisionId,
    parentRevision,
    transactionRevision: revisionId,
    transactionParentRevision: parentRevision,
    receiptRevision: revisionId,
    receiptParentRevision: parentRevision,
    inputBinding: {},
    receipt: { revision_id: revisionId, parent_revision: parentRevision, api_digest: apiDigest, record_digest: recordDigest },
    approvalIdentity: `${revisionId}:${parentRevision}:${apiDigest}:${recordDigest}`,
    ...overrides,
  };
}

test("owned queue boundary has no native prompt or captured queue bypass", async () => {
  const source = await readFile(new URL("../../vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js", import.meta.url), "utf8");
  assert.doesNotMatch(source, /\/prompt/);
  assert.doesNotMatch(source, /(?:originalQueuePrompt|capturedOriginalQueuePrompt|original\.queuePrompt)/);
});

function seedApprovedRecord(runtimeModule, runtime, panel, fixture, overrides = {}) {
  const canonical = overrides.canonical ?? fixture.canonical;
  const parsed = JSON.parse(canonical);
  const context = approvedContext(fixture, panel, overrides);
  runtimeModule.saveScopeApprovedRecord("queue-scope", {
    canonical,
    revisionId: context.revisionId,
    parentRevision: context.parentRevision,
    sessionId: context.sessionId,
    turnId: context.turnId,
    transactionRevision: context.transactionRevision,
    transactionParentRevision: context.transactionParentRevision,
    apiDigest: overrides.recordApiDigest ?? parsed.api_digest,
    recordDigest: overrides.recordRecordDigest ?? sha256HexFromString(canonical),
    scopeActivation: context.scopeActivation,
    approvalIdentity: context.approvalIdentity,
    invalidationGeneration: runtime.queueGuardInvalidationGeneration,
  });
  context.invalidationGeneration = runtime.queueGuardInvalidationGeneration;
  runtime.queueGuardContext = context;
  return context;
}

async function setupQueueHarness() {
  const harness = await createBrowserHarness({
    withQueuePrompt: true,
    withApiQueuePrompt: true,
    responses: { "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } } },
  });
  const extension = await harness.loadExtension();
  await harness.setup();
  await harness.invokeCommand("VibeComfy.AgentEdit");
  const panel = extension.ensureAgentPanel();
  panel.state.chatScopeId = "queue-scope";
  const runtimeModule = await harness.loadPanelRuntime();
  const runtime = runtimeModule.getAgentPanelRuntime();
  return { harness, extension, panel, runtimeModule, runtime };
}

test("real apply/finalize publishes the Python canonical record and queues exact decoded projections", async () => {
  const sessionId = "session-t19-real";
  const turnId = "0001";
  const planHash = "t19-real-plan";
  const graph = { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" }, outputs: [{ name: "IMAGE", links: [] }] }], links: [] };
  const candidateGraph = {
    nodes: [
      ...graph.nodes,
      { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" }, inputs: [{ name: "images", link: null }] },
    ],
    links: [],
  };
  const deltaOps = [{
    op: "add_node",
    scope_path: "",
    uid: "uid-2",
    node_id: "2",
    class_type: "SaveImage",
    fields: { properties: { vibecomfy_uid: "uid-2" } },
    inputs: {},
  }];
  const candidateTransaction = makeValidCandidateTransactionV2({ sessionId, turnId, planHash, deltaOps });
  candidateTransaction.revision_id = "b".repeat(64);
  candidateTransaction.parent_revision = "";
  const preparedTransaction = makeValidCandidateTransactionV2({ sessionId, turnId, planHash, deltaOps, state: "prepared", generation: 1, leaseNonce: "t19-real-lease", overrides: { revision_id: candidateTransaction.revision_id, parent_revision: "" } });
  const finalizedTransaction = makeValidCandidateTransactionV2({ sessionId, turnId, planHash, deltaOps, state: "finalized", generation: 1, leaseNonce: "t19-real-lease", overrides: { revision_id: candidateTransaction.revision_id, parent_revision: "" } });
  preparedTransaction.revision_id = candidateTransaction.revision_id;
  preparedTransaction.parent_revision = "";
  finalizedTransaction.revision_id = candidateTransaction.revision_id;
  finalizedTransaction.parent_revision = "";
  const record = {
    revision_id: candidateTransaction.revision_id,
    selected_variant: null,
    input_binding: {},
    api_projection: { "1": { class_type: "Input", inputs: {} } },
    ui_projection: { nodes: [], links: [] },
    api_digest: sha256Hex({ "1": { class_type: "Input", inputs: {} } }),
  };
  const canonical = canonicalJsonString(record);
  const approval = {
    revision_id: candidateTransaction.revision_id,
    parent_revision: "",
    api_digest: record.api_digest,
    record_digest: sha256HexFromString(canonical),
  };
  bindTransactionHashes(null, candidateTransaction, candidateGraph, graph);
  bindTransactionHashes(null, preparedTransaction, candidateGraph, graph);
  bindTransactionHashes(null, finalizedTransaction, candidateGraph, graph);
  assert.ok(normalizeCandidateTransaction(candidateTransaction));
  assert.ok(normalizeCandidateTransaction(preparedTransaction));
  const candidateFields = {
    agent_edit_protocol: "v2_delta",
    outcome: { kind: "candidate", changes: [] },
    candidate: { state: "candidate", graph: candidateGraph, graph_hash: candidateTransaction.hashes.candidate_graph_hash, plan_hash: planHash },
    graph: candidateGraph,
    candidate_graph_hash: candidateTransaction.hashes.candidate_graph_hash,
    delta_ops: candidateTransaction.plan.delta_ops_envelope.ops,
    delta_ops_envelope: structuredClone(candidateTransaction.plan.delta_ops_envelope),
    candidate_transaction: candidateTransaction,
  };
  const harness = await createBrowserHarness({
    graph,
    withQueuePrompt: true,
    withApiQueuePrompt: true,
    withGraphMutation: true,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": { status: 200, body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: { auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false } } } },
      "/vibecomfy/agent-executor": { status: 200, body: {
        ok: true,
        session_id: sessionId,
        turn_id: turnId,
        baseline_turn_id: null,
        ...candidateFields,
        eligibility: { applyable: true, reason: "applyable", message: "Apply is allowed.", warnings: [] },
        canvas_apply_allowed: true,
        apply_allowed: true,
        queue_allowed: true,
        message: "T19 candidate ready.",
      } },
      "/vibecomfy/agent-edit/prepare": async ({ options }) => {
        return { status: 200, body: { ok: true, action: "prepare", session_id: sessionId, turn_id: turnId, revision_id: candidateTransaction.revision_id, parent_revision: "", receipt: { plan_hash: planHash, generation: 1, lease_nonce: "t19-real-lease" }, candidate_transaction: preparedTransaction } };
      },
      "/vibecomfy/agent-edit/finalize": async ({ options }) => {
        const body = JSON.parse(options.body);
        assert.equal(body.revision_id, candidateTransaction.revision_id);
        assert.equal(body.parent_revision, "");
        return { status: 200, body: { ok: true, action: "finalize", session_id: sessionId, turn_id: turnId, revision_id: candidateTransaction.revision_id, parent_revision: "", candidate_transaction: finalizedTransaction, approved_record_canonical: canonical, receipt: { revision_id: candidateTransaction.revision_id, parent_revision: "", receipt: { approval }, phase: "finalized" } } };
      },
    },
  });
  const originalGlobalApp = globalThis.app;
  globalThis.app = harness.app;
  try {
    const extension = await harness.loadExtension();
    await harness.setup();
    await harness.invokeCommand("VibeComfy.AgentEdit");
    const panel = extension.ensureAgentPanel();
    const scope = extension.resolveActiveCanvasScope();
    assert.ok(scope?.scopeId);
    panel.state.chatScopeId = scope.scopeId;
    panel.state.chatScopeFingerprint = scope.fingerprint;
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "add a saver";
    panel.buttons.submit.disabled = false;
    await harness.clickButton("Submit");
    for (let index = 0; index < 20 && panel.state.phase !== "AWAITING_REVIEW"; index += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    assert.equal(panel.state.phase, "AWAITING_REVIEW", JSON.stringify({ failure: panel.state.failure, message: panel.state.message, requests: harness.requests }));
    panel.state.chatRehydratePending = false;
    panel.buttons.apply.disabled = false;
    panel.buttons.apply.click();
    for (let index = 0; index < 100 && !harness.requests.some((entry) => entry.url === "/vibecomfy/agent-edit/finalize"); index += 1) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    assert.equal(harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/finalize").length, 1, JSON.stringify({ phase: panel.state.phase, failure: panel.state.failure, requests: harness.requests }));
    const runtimeModule = await harness.loadPanelRuntime();
    const runtime = runtimeModule.getAgentPanelRuntime();
    const savedRecord = runtimeModule.getScopeApprovedRecord(scope.scopeId);
    assert.ok(savedRecord);
    assert.equal(savedRecord.canonical, canonical);
    assert.equal(savedRecord.apiDigest, approval.api_digest);
    assert.equal(savedRecord.recordDigest, approval.record_digest);
    const result = harness.app.queuePrompt("live-canvas-is-ignored", { output: "ignored" });
    assert.deepEqual(result, { prompt_id: "prompt-1" }, JSON.stringify({ phase: panel.state.phase, finalizedReceipt: panel.state.finalizedReceipt, accepted: panel.state.responseCompartments, savedRecord, queueGuard: runtime.queueGuardContext, notice: runtime.queueGuardBlockNotice, requests: harness.requests }));
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.deepEqual(harness.apiQueuePromptCalls, [[0, {
      output: { "1": { class_type: "Input", inputs: {} } },
      workflow: { nodes: [], links: [] },
    }]]);
    assert.equal(runtime.queueGuardContext.promptId, "prompt-1");
  } finally {
    if (originalGlobalApp === undefined) delete globalThis.app;
    else globalThis.app = originalGlobalApp;
    await harness.dispose();
  }
});

test("literal Python canonical bytes retain their known UTF-8 digest across the queue boundary", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const panel = extension.ensureAgentPanel();
    const fixture = {
      canonical: PYTHON_CANONICAL,
      receipt: {
        revision_id: "t19-python-revision",
        api_digest: "f4ca373f764462eef8bf6670712b4748516ca0dd1d1a8c375acec29e7f933a34",
        record_digest: PYTHON_CANONICAL_DIGEST,
      },
    };
    seedApprovedRecord(runtimeModule, runtime, panel, fixture, {
      revisionId: "t19-python-revision",
      recordDigest: PYTHON_CANONICAL_DIGEST,
      recordRecordDigest: PYTHON_CANONICAL_DIGEST,
    });
    assert.equal(sha256HexFromString(PYTHON_CANONICAL), PYTHON_CANONICAL_DIGEST);
    assert.deepEqual(harness.app.queuePrompt("ignored"), { prompt_id: "prompt-1" });
    assert.deepEqual(harness.apiQueuePromptCalls[0], [0, {
      output: { workflow_revision: "t19-python-fixed" },
      workflow: {},
    }]);
  } finally {
    await harness.dispose();
  }
});

test("canonical queue blocker matrix never calls either queue function", async () => {
  const cases = [
    ["missing record", (fixture, runtimeModule) => runtimeModule.saveScopeApprovedRecord("queue-scope", null)],
    ["extra schema key", (fixture, runtimeModule, runtime, context) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical: canonicalJsonString({ ...JSON.parse(fixture.canonical), extra: true }) });
    }],
    ["wrong selected variant type", (fixture, runtimeModule) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical: canonicalJsonString({ ...JSON.parse(fixture.canonical), selected_variant: 3 }) });
    }],
    ["stale revision", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardContext = { ...context, revisionId: "rev-other" };
    }],
    ["stale parent", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardContext = { ...context, parentRevision: "parent-other", receipt: { ...context.receipt, parent_revision: "parent-other" } };
    }],
    ["binding mismatch", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardContext = { ...context, inputBinding: { node: "other" } };
    }],
    ["API digest mismatch", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardContext = { ...context, receipt: { ...context.receipt, api_digest: "0".repeat(64) } };
    }],
    ["record digest mismatch", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardContext = { ...context, receipt: { ...context.receipt, record_digest: "0".repeat(64) } };
    }],
    ["unsafe positive integer", (fixture, runtimeModule) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      const record = JSON.parse(fixture.canonical);
      record.api_projection = { unsafe: 9007199254740992 };
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical: canonicalJsonString(record) });
    }],
    ["unsafe negative integer", (fixture, runtimeModule) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      const record = JSON.parse(fixture.canonical);
      record.api_projection = { unsafe: -9007199254740992 };
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical: canonicalJsonString(record) });
    }],
    ["non-finite value", (fixture, runtimeModule) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical: fixture.canonical.replace('"api_digest"', '"bad":NaN,"api_digest"') });
    }],
    ["queue disabled", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardContext = { ...context, queueAllowed: false };
    }],
  ];
  for (const [name, mutate] of cases) {
    const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
    try {
      const fixture = approvedFixture();
      const panel = extension.ensureAgentPanel();
      seedApprovedRecord(runtimeModule, runtime, panel, fixture);
      mutate(fixture, runtimeModule, runtime, runtime.queueGuardContext);
      assert.equal(harness.app.queuePrompt("canvas"), null, name);
      assert.equal(harness.queuePromptCalls.length, 0, name);
      assert.equal(harness.apiQueuePromptCalls.length, 0, name);
    } finally {
      await harness.dispose();
    }
  }
});

test("replaced queue hook and graph mutation fail closed without transport", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    const wrapper = harness.app.queuePrompt;
    harness.setQueuePromptHookFault("replaced");
    assert.equal(wrapper("caller"), null);
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.equal(harness.apiQueuePromptCalls.length, 0);
    harness.app.queuePrompt = wrapper;
    for (const mode of ["missing", "replaced"]) {
      harness.setGraphMutationHookFault(mode);
      assert.equal(wrapper("caller"), null, mode);
      assert.equal(harness.apiQueuePromptCalls.length, 0, mode);
      if (mode === "missing") harness.app.canvas.graph.change = runtime.queueGuardMutationHook.wrapper;
    }
  } finally {
    await harness.dispose();
  }
});

test("ordinary graph change invalidates the approved canonical custody", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    const before = runtime.queueGuardInvalidationGeneration;
    harness.app.canvas.graph.change();
    assert.equal(runtime.queueGuardInvalidationGeneration, before + 1);
    assert.equal(runtimeModule.getScopeApprovedRecord("queue-scope"), null);
    assert.equal(harness.app.queuePrompt("caller"), null);
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.equal(harness.apiQueuePromptCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("safe numeric spellings remain queueable", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    const record = JSON.parse(fixture.canonical);
    record.api_projection = { negative_zero: -0, float: 1.25, exponent: 1e3 };
    const canonical = canonicalJsonString(record).replace('"negative_zero":0', '"negative_zero":-0');
    const recordDigest = sha256HexFromString(canonical);
    seedApprovedRecord(runtimeModule, runtime, panel, fixture, {
      canonical,
      recordDigest,
      recordRecordDigest: recordDigest,
    });
    assert.deepEqual(harness.app.queuePrompt("caller"), { prompt_id: "prompt-1" });
    assert.equal(harness.apiQueuePromptCalls.length, 1);
  } finally {
    await harness.dispose();
  }
});

test("each successful queue decodes a fresh projection from canonical bytes", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    assert.deepEqual(harness.app.queuePrompt("caller"), { prompt_id: "prompt-1" });
    harness.apiQueuePromptPayloadRefs[0].output["1"].inputs.mutated = true;
    assert.deepEqual(harness.app.queuePrompt("caller"), { prompt_id: "prompt-2" });
    assert.deepEqual(harness.apiQueuePromptCalls[1][1], {
      output: { "1": { class_type: "Input", inputs: {} } },
      workflow: { nodes: [], links: [] },
    });
  } finally {
    await harness.dispose();
  }
});

test("queue attribution requires a real prompt_id and ignores foreign lifecycle events", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    const originalQueuePrompt = harness.api.queuePrompt;
    harness.api.queuePrompt = () => ({ accepted: true });
    assert.throws(() => harness.app.queuePrompt("caller"), /no nonblank prompt_id/);
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.equal(harness.apiQueuePromptCalls.length, 0);
    harness.api.queuePrompt = originalQueuePrompt;

    assert.deepEqual(harness.app.queuePrompt({ output: "ignored" }), { prompt_id: "prompt-1" });
    assert.equal(runtime.queueGuardContext.promptId, "prompt-1");
    harness.dispatchApiEvent("execution_start", { prompt_id: "foreign" });
    harness.dispatchApiEvent("executing", { prompt_id: "foreign", node: null });
    harness.dispatchApiEvent("progress", {});
    assert.equal(runtime.queueGuardContext.lifecycleState, "pending");
    harness.dispatchApiEvent("execution_start", { prompt_id: "prompt-1" });
    assert.equal(runtime.queueGuardContext.lifecycleState, "running");
    harness.dispatchApiEvent("executing", { prompt_id: "prompt-1", node: null });
    assert.equal(runtime.queueGuardContext.lifecycleState, "ended_observation");
    assert.equal(harness.apiEventListeners.execution_error?.length, 1);
    harness.dispatchApiEvent("execution_error", { prompt_id: "prompt-1", error: "boom" });
    assert.equal(runtime.queueGuardContext.lifecycleState, "error", JSON.stringify({ lifecycle: runtime.queueGuardLifecycle, context: runtime.queueGuardContext }));
    harness.dispatchApiEvent("executing", { prompt_id: "prompt-1", node: null });
    assert.equal(runtime.queueGuardContext.lifecycleState, "error");
  } finally {
    await harness.dispose();
  }
});

test("cancel and delete expose unsupported tracked-prompt errors without transport", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    assert.deepEqual(harness.app.queuePrompt("caller"), { prompt_id: "prompt-1" });
    assert.throws(() => extension.requestQueuePromptOperation("cancel"), /cancel.*prompt-1/);
    assert.throws(() => extension.requestQueuePromptOperation("delete"), /delete.*prompt-1/);
    assert.equal(harness.interruptCalls.length, 0);
    assert.equal(harness.deleteItemCalls.length, 0);
    assert.equal(runtime.queueGuardContext.lifecycleState, "unsupported");
    assert.equal(runtime.queueGuardContext.operationUnsupported, "delete");
    harness.dispatchApiEvent("execution_start", { prompt_id: "prompt-1" });
    harness.dispatchApiEvent("progress", { prompt_id: "prompt-1" });
    harness.dispatchApiEvent("executed", { prompt_id: "prompt-1" });
    assert.equal(runtime.queueGuardContext.lifecycleState, "unsupported");
    assert.equal(runtime.queueGuardLifecycle.error.includes("delete"), true);
  } finally {
    await harness.dispose();
  }
});
