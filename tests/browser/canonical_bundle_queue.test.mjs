import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
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

const WORKTREE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const PYTHON_FIXTURE_CODE = `
import hashlib
import json
import os
from vibecomfy.testing.canonical import canonical_digest
from vibecomfy.workflow_bundle import ApprovedProjectionRecord

api_projection = (
    {"workflow_revision": "t19-python-fixed"}
    if os.environ.get("T19_FIXTURE_PROFILE", "ascii") == "ascii"
    else {
        "ascii": "plain",
        "unicode": "café {[]}\\\"quoted\\\" \\\\path",
        "integral_float": 7.0,
        "small_exponent": 1e-7,
        "negative_zero": -0.0,
    }
)
record = ApprovedProjectionRecord(
    revision_id=os.environ.get("T19_FIXTURE_REVISION", "t19-python-revision"),
    selected_variant=None,
    input_binding={},
    api_projection=api_projection,
    ui_projection={},
    api_digest=canonical_digest(api_projection),
)
canonical = record.to_canonical_bytes()
roundtrip = ApprovedProjectionRecord.from_canonical_bytes(canonical)
print(json.dumps({
    "canonical": canonical.decode("utf-8"),
    "revision_id": roundtrip.revision_id,
    "api_digest": roundtrip.api_digest,
    "record_digest": hashlib.sha256(canonical).hexdigest(),
}))
`;

function pythonApprovedFixture(t, revisionId = "t19-python-revision", profile = "ascii") {
  const configured = typeof process.env.VIBECOMFY_PYTHON === "string" && process.env.VIBECOMFY_PYTHON
    ? process.env.VIBECOMFY_PYTHON
    : null;
  const candidates = [...new Set([configured, "python3", "python"].filter(Boolean))];
  for (const executable of candidates) {
    const result = spawnSync(executable, ["-c", PYTHON_FIXTURE_CODE], {
      cwd: WORKTREE_ROOT,
      encoding: "utf8",
      env: {
        ...process.env,
        PYTHONPATH: [WORKTREE_ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
        VIBECOMFY_HEADLESS: "1",
        T19_FIXTURE_REVISION: revisionId,
        T19_FIXTURE_PROFILE: profile,
      },
    });
    if (result.error?.code === "ENOENT") continue;
    if (result.error) throw result.error;
    if (result.status !== 0) {
      throw new Error(`Python canonical fixture failed under ${executable}: ${result.stderr || result.stdout}`);
    }
    try {
      return JSON.parse(result.stdout);
    } catch (error) {
      throw new Error(`Python canonical fixture emitted invalid JSON under ${executable}: ${error.message}`);
    }
  }
  t.skip("no python interpreter available for the cross-language canonical fixture");
  return null;
}

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
    transactionId: "tx-queue-plan",
    candidateId: "candidate-queue-plan",
    planHash: "queue-plan",
    generation: 1,
    leaseNonce: "queue-lease",
    ...overrides,
  };
}

test("owned queue boundary has no native prompt or captured queue bypass", async () => {
  const source = await readFile(new URL("../../vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js", import.meta.url), "utf8");
  const adapterSource = await readFile(new URL("../../vibecomfy/comfy_nodes/web/comfy_adapter.js", import.meta.url), "utf8");
  for (const ownedSource of [source, adapterSource]) {
    assert.doesNotMatch(ownedSource, /\/prompt/);
    assert.doesNotMatch(ownedSource, /(?:originalQueuePrompt|capturedOriginalQueuePrompt|original\.queuePrompt)/);
  }
});

test("harness surfaces queue lifecycle listener exceptions", async () => {
  const harness = await createBrowserHarness({ withQueuePrompt: true, withApiQueuePrompt: true });
  try {
    const listenerError = new Error("listener exploded");
    harness.api.addEventListener("progress", () => { throw listenerError; });
    harness.dispatchApiEvent("progress", { prompt_id: "foreign" });
    assert.equal(harness.eventListenerErrors.length, 1);
    assert.equal(harness.eventListenerErrors[0].error, listenerError);
  } finally {
    await harness.dispose();
  }
});

test("setup-time queue and graph descriptor faults disable the adapter without lower transport", async () => {
  for (const fault of ["missing", "nonconfigurable", "unwritable", "accessor_throw", "nonextensible"]) {
    const queueHarness = await createBrowserHarness({
      withQueuePrompt: true,
      withApiQueuePrompt: true,
      setupQueuePromptFault: fault,
      responses: { "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } } },
    });
    try {
      const extension = await queueHarness.loadExtension();
      await queueHarness.setup();
      await queueHarness.invokeCommand("VibeComfy.AgentEdit");
      const runtime = (await queueHarness.loadPanelRuntime()).getAgentPanelRuntime();
      assert.equal(runtime.queueGuardHook?.installed, false, `queue setup fault ${fault}`);
      assert.equal(queueHarness.apiQueuePromptCalls.length, 0, `queue setup fault ${fault}`);
      assert.equal(queueHarness.queuePromptCalls.length, 0, `queue setup fault ${fault}`);
      void extension;
    } finally {
      await queueHarness.dispose();
    }
  }
  for (const fault of ["missing", "nonconfigurable", "unwritable", "accessor_throw", "nonextensible"]) {
    const graphHarness = await createBrowserHarness({
      withQueuePrompt: true,
      withApiQueuePrompt: true,
      setupGraphMutationFault: fault,
      responses: { "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } } },
    });
    try {
      const extension = await graphHarness.loadExtension();
      await graphHarness.setup();
      await graphHarness.invokeCommand("VibeComfy.AgentEdit");
      const runtime = (await graphHarness.loadPanelRuntime()).getAgentPanelRuntime();
      assert.equal(runtime.queueGuardMutationHook?.installed, false, `graph setup fault ${fault}`);
      if (typeof graphHarness.app.queuePrompt === "function") {
        assert.equal(graphHarness.app.queuePrompt("external"), null, `graph setup fault ${fault}`);
      }
      assert.equal(graphHarness.apiQueuePromptCalls.length, 0, `graph setup fault ${fault}`);
      void extension;
    } finally {
      await graphHarness.dispose();
    }
  }
});

function seedApprovedRecord(runtimeModule, runtime, panel, fixture, overrides = {}) {
  const canonical = overrides.canonical ?? fixture.canonical;
  const parsed = JSON.parse(canonical);
  const context = approvedContext(fixture, panel, overrides);
  const transaction = makeValidCandidateTransactionV2({
    sessionId: context.sessionId,
    turnId: context.turnId,
    workflowId: context.workflowId,
    planHash: context.planHash,
    state: "finalized",
    generation: context.generation,
    leaseNonce: context.leaseNonce,
    overrides: {
      revision_id: context.revisionId,
      parent_revision: context.parentRevision,
    },
  });
  panel.state.sessionId = context.sessionId;
  panel.state.turnId = context.turnId;
  panel.state.candidateTransaction = transaction;
  context.workflowId = transaction.candidate_authority.workflow_id;
  context.graph = runtime.queueGuardMutationHook?.graph || null;
  context.queueWrapper = runtime.queueGuardHook?.wrapper || null;
  context.mutationGraph = runtime.queueGuardMutationHook?.graph || null;
  context.mutationWrapper = runtime.queueGuardMutationHook?.wrapper || null;
  runtimeModule.saveScopeApprovedRecord("queue-scope", {
    canonical,
    revisionId: context.revisionId,
    parentRevision: context.parentRevision,
    sessionId: context.sessionId,
    turnId: context.turnId,
    workflowId: context.workflowId,
    transactionId: context.transactionId,
    candidateId: context.candidateId,
    planHash: context.planHash,
    generation: context.generation,
    leaseNonce: context.leaseNonce,
    transactionRevision: context.transactionRevision,
    transactionParentRevision: context.transactionParentRevision,
    apiDigest: overrides.recordApiDigest ?? parsed.api_digest,
    recordDigest: overrides.recordRecordDigest ?? sha256HexFromString(canonical),
    scopeActivation: context.scopeActivation,
    approvalIdentity: context.approvalIdentity,
    invalidationGeneration: runtime.queueGuardInvalidationGeneration,
    graph: context.graph,
    queueWrapper: context.queueWrapper,
    mutationGraph: context.mutationGraph,
    mutationWrapper: context.mutationWrapper,
  });
  context.invalidationGeneration = runtime.queueGuardInvalidationGeneration;
  runtime.queueGuardApproval = context;
  runtime.queueGuardContext = context;
  return context;
}

async function setupQueueHarness(options = {}) {
  const harness = await createBrowserHarness({
    withQueuePrompt: true,
    withApiQueuePrompt: true,
    responses: { "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } } },
    ...options,
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

async function runDeferredRealFinalizeCase(t, { mutateBeforeRelease = null, mutateResponse = null } = {}) {
  const sessionId = "session-t19-deferred";
  const turnId = "deferred-0001";
  const planHash = "t19-deferred-plan";
  const graph = { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }], links: [] };
  const candidateGraph = { nodes: [...graph.nodes, { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } }], links: [] };
  const deltaOps = [{ op: "add_node", scope_path: "", uid: "uid-2", node_id: "2", class_type: "SaveImage", fields: { properties: { vibecomfy_uid: "uid-2" } }, inputs: {} }];
  const candidateTransaction = makeValidCandidateTransactionV2({ sessionId, turnId, planHash, deltaOps });
  candidateTransaction.revision_id = "c".repeat(64);
  candidateTransaction.parent_revision = "";
  const pythonFixture = pythonApprovedFixture(t, candidateTransaction.revision_id, "rich");
  if (!pythonFixture) return null;
  const preparedTransaction = makeValidCandidateTransactionV2({ sessionId, turnId, planHash, deltaOps, state: "prepared", generation: 1, leaseNonce: "deferred-lease", overrides: { revision_id: candidateTransaction.revision_id, parent_revision: "" } });
  const finalizedTransaction = makeValidCandidateTransactionV2({ sessionId, turnId, planHash, deltaOps, state: "finalized", generation: 1, leaseNonce: "deferred-lease", overrides: { revision_id: candidateTransaction.revision_id, parent_revision: "" } });
  for (const transaction of [preparedTransaction, finalizedTransaction]) {
    transaction.revision_id = candidateTransaction.revision_id;
    transaction.parent_revision = "";
  }
  bindTransactionHashes(null, candidateTransaction, candidateGraph, graph);
  bindTransactionHashes(null, preparedTransaction, candidateGraph, graph);
  bindTransactionHashes(null, finalizedTransaction, candidateGraph, graph);
  const approval = { revision_id: candidateTransaction.revision_id, parent_revision: "", api_digest: pythonFixture.api_digest, record_digest: pythonFixture.record_digest };
  let activeCycle = {
    sessionId,
    turnId,
    planHash,
    graph,
    candidateGraph,
    candidateTransaction,
    preparedTransaction,
    finalizedTransaction,
    pythonFixture,
    approval,
    deferFinalize: true,
  };
  let releaseFinalize;
  let finalizeRequested;
  const finalizeRequestedPromise = new Promise((resolve) => { finalizeRequested = resolve; });
  const finalizeGate = new Promise((resolve) => { releaseFinalize = resolve; });
  const candidateFields = (cycle) => ({
    agent_edit_protocol: "v2_delta",
    outcome: { kind: "candidate", changes: [] },
    candidate: { state: "candidate", graph: cycle.candidateGraph, graph_hash: cycle.candidateTransaction.hashes.candidate_graph_hash, plan_hash: cycle.planHash },
    graph: cycle.candidateGraph,
    candidate_graph_hash: cycle.candidateTransaction.hashes.candidate_graph_hash,
    delta_ops: cycle.candidateTransaction.plan.delta_ops_envelope.ops,
    delta_ops_envelope: structuredClone(cycle.candidateTransaction.plan.delta_ops_envelope),
    candidate_transaction: cycle.candidateTransaction,
  });
  const harness = await createBrowserHarness({
    graph,
    withQueuePrompt: true,
    withApiQueuePrompt: true,
    withGraphMutation: true,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
      "/vibecomfy/agent/status?route=auto": { status: 200, body: { ok: true, provider_available: true, route: "arnold", requested_route: "auto", route_options: { auto: { requested_route: "auto", normalized_route: "arnold", browser_api_key_allowed: false } } } },
      "/vibecomfy/agent-executor": () => ({ status: 200, body: { ok: true, session_id: activeCycle.sessionId, turn_id: activeCycle.turnId, baseline_turn_id: null, ...candidateFields(activeCycle), eligibility: { applyable: true, reason: "applyable", message: "Apply is allowed.", warnings: [] }, canvas_apply_allowed: true, apply_allowed: true, queue_allowed: true, message: "T19 deferred candidate." } }),
      "/vibecomfy/agent-edit/prepare": async ({ options }) => {
        const body = JSON.parse(options.body);
        const cycle = activeCycle;
        assert.equal(body.session_id, cycle.sessionId);
        return { status: 200, body: { ok: true, action: "prepare", session_id: cycle.sessionId, turn_id: cycle.turnId, revision_id: cycle.candidateTransaction.revision_id, parent_revision: "", receipt: { plan_hash: cycle.planHash, generation: 1, lease_nonce: cycle.preparedTransaction?.lease_nonce ?? "deferred-lease" }, candidate_transaction: cycle.preparedTransaction } };
      },
      "/vibecomfy/agent-edit/finalize": async ({ options }) => {
        const body = JSON.parse(options.body);
        const cycle = activeCycle;
        assert.equal(body.revision_id, cycle.candidateTransaction.revision_id);
        if (cycle.deferFinalize) {
          finalizeRequested();
          await finalizeGate;
        }
        const response = {
          ok: true,
          action: "finalize",
          session_id: cycle.sessionId,
          turn_id: cycle.turnId,
          plan_hash: cycle.planHash,
          generation: 1,
          revision_id: cycle.candidateTransaction.revision_id,
          parent_revision: "",
          candidate_transaction: cycle.finalizedTransaction,
          approved_record_canonical: cycle.pythonFixture.canonical,
          receipt: {
            seq: 1,
            event_type: "finalized",
            turn_id: cycle.turnId,
            plan_hash: cycle.planHash,
            generation: 1,
            timestamp: "2026-09-05T00:00:00+00:00",
            receipt: { turn_id: cycle.turnId, plan_hash: cycle.planHash, generation: 1, revision_id: cycle.candidateTransaction.revision_id, parent_revision: "", phase: "finalized", approval: cycle.approval },
          },
        };
        if (cycle.mutateResponse) cycle.mutateResponse(response, cycle);
        else mutateResponse?.(response, cycle);
        return { status: 200, body: response };
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
    panel.state.chatScopeId = scope.scopeId;
    panel.state.chatScopeFingerprint = scope.fingerprint;
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "deferred finalize";
    panel.buttons.submit.disabled = false;
    await harness.clickButton("Submit");
    for (let index = 0; index < 30 && panel.state.phase !== "AWAITING_REVIEW"; index += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(panel.state.phase, "AWAITING_REVIEW");
    panel.state.chatRehydratePending = false;
    panel.buttons.apply.disabled = false;
    panel.buttons.apply.click();
    await finalizeRequestedPromise;
    await mutateBeforeRelease?.({ harness, panel, scope, candidateTransaction, finalizedTransaction, runtime: (await harness.loadPanelRuntime()).getAgentPanelRuntime() });
    releaseFinalize();
    for (let index = 0; index < 100 && harness.requests.filter((entry) => entry.url === "/vibecomfy/agent-edit/finalize").length < 1; index += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 20));
    const runtimeModule = await harness.loadPanelRuntime();
    return {
      harness,
      extension,
      panel,
      scope,
      pythonFixture,
      runtime: runtimeModule.getAgentPanelRuntime(),
      runtimeModule,
      setFinalizeCycle(cycle) {
        activeCycle = { ...cycle, deferFinalize: false };
      },
    };
  } catch (error) {
    await harness.dispose();
    throw error;
  } finally {
    if (originalGlobalApp === undefined) delete globalThis.app;
    else globalThis.app = originalGlobalApp;
  }
}

test("real apply/finalize publishes the Python canonical record and queues exact decoded projections", async (t) => {
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
  const pythonFixture = pythonApprovedFixture(t, candidateTransaction.revision_id);
  if (!pythonFixture) return;
  const preparedTransaction = makeValidCandidateTransactionV2({ sessionId, turnId, planHash, deltaOps, state: "prepared", generation: 1, leaseNonce: "t19-real-lease", overrides: { revision_id: candidateTransaction.revision_id, parent_revision: "" } });
  const finalizedTransaction = makeValidCandidateTransactionV2({ sessionId, turnId, planHash, deltaOps, state: "finalized", generation: 1, leaseNonce: "t19-real-lease", overrides: { revision_id: candidateTransaction.revision_id, parent_revision: "" } });
  preparedTransaction.revision_id = candidateTransaction.revision_id;
  preparedTransaction.parent_revision = "";
  finalizedTransaction.revision_id = candidateTransaction.revision_id;
  finalizedTransaction.parent_revision = "";
  const record = JSON.parse(pythonFixture.canonical);
  const canonical = pythonFixture.canonical;
  const approval = {
    revision_id: pythonFixture.revision_id,
    parent_revision: "",
    api_digest: pythonFixture.api_digest,
    record_digest: pythonFixture.record_digest,
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
        return { status: 200, body: {
          ok: true,
          action: "finalize",
          session_id: sessionId,
          turn_id: turnId,
          revision_id: candidateTransaction.revision_id,
          parent_revision: "",
          candidate_transaction: finalizedTransaction,
          approved_record_canonical: canonical,
          receipt: {
            seq: 1,
            event_type: "finalized",
            turn_id: turnId,
            plan_hash: planHash,
            generation: 1,
            timestamp: "2026-09-05T00:00:00+00:00",
            receipt: {
              turn_id: turnId,
              plan_hash: planHash,
              generation: 1,
              revision_id: candidateTransaction.revision_id,
              parent_revision: "",
              phase: "finalized",
              approval,
            },
          },
        } };
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
    let savedRecord = runtimeModule.getScopeApprovedRecord(scope.scopeId);
    for (let index = 0; index < 100 && !savedRecord; index += 1) {
      await new Promise((resolve) => setTimeout(resolve, 10));
      savedRecord = runtimeModule.getScopeApprovedRecord(scope.scopeId);
    }
    assert.ok(savedRecord);
    assert.equal(savedRecord.canonical, pythonFixture.canonical);
    assert.equal(savedRecord.apiDigest, approval.api_digest);
    assert.equal(savedRecord.recordDigest, approval.record_digest);
    const result = harness.app.queuePrompt("live-canvas-is-ignored", { output: "ignored" });
    assert.deepEqual(result, { prompt_id: "prompt-1" });
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.deepEqual(harness.apiQueuePromptCalls, [[0, {
      output: JSON.parse(pythonFixture.canonical).api_projection,
      workflow: JSON.parse(pythonFixture.canonical).ui_projection,
    }]]);
    assert.equal(runtime.queueGuardPromptAttempt.promptId, "prompt-1");
  } finally {
    if (originalGlobalApp === undefined) delete globalThis.app;
    else globalThis.app = originalGlobalApp;
    await harness.dispose();
  }
});

test("deferred real finalize rejects every changed custody dimension before publication", async (t) => {
  const mutateTx = (panel, change) => {
    const transaction = structuredClone(panel.state.candidateTransaction);
    change(transaction);
    panel.state.candidateTransaction = transaction;
  };
  const cases = [
    ["revision", ({ panel }) => mutateTx(panel, (transaction) => { transaction.revision_id = "stale-revision"; })],
    ["parent", ({ panel }) => mutateTx(panel, (transaction) => { transaction.parent_revision = "stale-parent"; })],
    ["session", ({ panel }) => { panel.state.sessionId = "stale-session"; mutateTx(panel, (transaction) => { transaction.session_id = "stale-session"; }); }],
    ["turn", ({ panel }) => { panel.state.turnId = "stale-turn"; mutateTx(panel, (transaction) => { transaction.turn_id = "stale-turn"; }); }],
    ["workflow", ({ panel }) => mutateTx(panel, (transaction) => { transaction.candidate_authority.workflow_id = "stale-workflow"; })],
    ["transaction", ({ panel }) => mutateTx(panel, (transaction) => { transaction.candidate_authority.transaction_id = "stale-transaction"; })],
    ["candidate", ({ panel }) => mutateTx(panel, (transaction) => { transaction.candidate_authority.candidate_id = "stale-candidate"; })],
    ["prepared workflow", ({ panel }) => mutateTx(panel, (transaction) => { transaction.prepared_authority.workflow_id = "stale-prepared-workflow"; })],
    ["prepared transaction", ({ panel }) => mutateTx(panel, (transaction) => { transaction.prepared_authority.transaction_id = "stale-prepared-transaction"; })],
    ["prepared candidate", ({ panel }) => mutateTx(panel, (transaction) => { transaction.prepared_authority.candidate_id = "stale-prepared-candidate"; })],
    ["plan", ({ panel }) => mutateTx(panel, (transaction) => { transaction.plan_hash = "stale-plan"; })],
    ["generation", ({ panel }) => mutateTx(panel, (transaction) => { transaction.generation = 2; })],
    ["lease", ({ panel }) => mutateTx(panel, (transaction) => { transaction.lease_nonce = "stale-lease"; })],
    ["prepared generation", ({ panel }) => mutateTx(panel, (transaction) => { transaction.prepared_authority.generation = 9007199254740992; })],
    ["prepared lease", ({ panel }) => mutateTx(panel, (transaction) => { transaction.prepared_authority.lease_nonce = "stale-prepared-lease"; })],
    ["scope activation", ({ panel }) => { panel.state.scopeActivationEpoch += 1; }],
    ["ordinary graph mutation", ({ harness }) => { harness.app.canvas.graph.change(); }],
    ["fresh graph", ({ harness }) => { harness.replaceLiveGraph({ nodes: [{ id: 9, type: "Fresh" }], links: [] }); }],
    ["A to B graph", ({ harness }) => { harness.replaceLiveGraph({ nodes: [{ id: 10, type: "B" }], links: [] }); }],
    ["A to B scope", ({ harness, panel }) => { panel.state.chatScopeId = "scope-B"; panel.state.scopeActivationEpoch += 1; harness.replaceLiveGraph({ nodes: [{ id: 11, type: "B" }], links: [] }); }],
  ];
  for (const [name, mutate] of cases) {
    const result = await runDeferredRealFinalizeCase(t, { mutateBeforeRelease: mutate });
    if (!result) return;
    try {
      assert.equal(result.runtimeModule.getScopeApprovedRecord(result.scope.scopeId), null, name);
      assert.equal(result.harness.apiQueuePromptCalls.length, 0, name);
      assert.equal(result.harness.queuePromptCalls.length, 0, name);
      assert.notEqual(result.panel.state.phase, "READY", name);
      assert.notEqual(result.panel.state.phase, "FINALIZED", name);
      // The candidate lifecycle context may remain visible, but no approved
      // record custody may be minted by a stale response.
      assert.equal(result.runtime.queueGuardApproval?.approvalIdentity ?? null, null, name);
    } finally {
      await result.harness.dispose();
    }
  }
});

test("deferred real finalize positive control publishes the Python canonical record", async (t) => {
  const result = await runDeferredRealFinalizeCase(t);
  if (!result) return;
  try {
    const saved = result.runtimeModule.getScopeApprovedRecord(result.scope.scopeId);
    assert.ok(saved);
    assert.equal(saved.canonical, result.pythonFixture.canonical);
    assert.equal(saved.recordDigest, result.pythonFixture.record_digest);
    assert.equal(saved.apiDigest, result.pythonFixture.api_digest);
    assert.equal(result.panel.state.phase, "FINALIZED");
    assert.deepEqual(result.harness.app.queuePrompt("rich-finalized-record"), { prompt_id: "prompt-1" });
    assert.deepEqual(result.harness.apiQueuePromptCalls[0], [0, {
      output: { ...JSON.parse(result.pythonFixture.canonical).api_projection, negative_zero: 0 },
      workflow: JSON.parse(result.pythonFixture.canonical).ui_projection,
    }]);
    assert.equal(Object.is(result.harness.apiQueuePromptPayloadRefs[0].output.negative_zero, -0), true);
    assert.equal(result.harness.queuePromptCalls.length, 0);
  } finally {
    await result.harness.dispose();
  }
});

test("literal Python canonical bytes retain their known UTF-8 digest across the queue boundary", async (t) => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const panel = extension.ensureAgentPanel();
    const pythonFixture = pythonApprovedFixture(t);
    if (!pythonFixture) return;
    const fixture = {
      canonical: pythonFixture.canonical,
      receipt: {
        revision_id: pythonFixture.revision_id,
        api_digest: pythonFixture.api_digest,
        record_digest: pythonFixture.record_digest,
      },
    };
    seedApprovedRecord(runtimeModule, runtime, panel, fixture, {
      revisionId: pythonFixture.revision_id,
      recordDigest: pythonFixture.record_digest,
      recordRecordDigest: pythonFixture.record_digest,
    });
    assert.equal(sha256HexFromString(pythonFixture.canonical), pythonFixture.record_digest);
    assert.deepEqual(harness.app.queuePrompt("ignored"), { prompt_id: "prompt-1" });
    assert.deepEqual(harness.apiQueuePromptCalls[0], [0, {
      output: { workflow_revision: "t19-python-fixed" },
      workflow: {},
    }]);
  } finally {
    await harness.dispose();
  }
});

test("token-spelling tamper is rejected against the exact Python api_projection bytes", async (t) => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const pythonFixture = pythonApprovedFixture(t, "t19-token-tamper", "rich");
    if (!pythonFixture) return;
    const panel = extension.ensureAgentPanel();
    const fixture = { canonical: pythonFixture.canonical, receipt: { revision_id: pythonFixture.revision_id, api_digest: pythonFixture.api_digest, record_digest: pythonFixture.record_digest } };
    const context = seedApprovedRecord(runtimeModule, runtime, panel, fixture, { revisionId: pythonFixture.revision_id, recordDigest: pythonFixture.record_digest, recordRecordDigest: pythonFixture.record_digest });
    const tamperedCanonical = pythonFixture.canonical.replace('"negative_zero":-0.0', '"negative_zero":-0');
    assert.notEqual(tamperedCanonical, pythonFixture.canonical);
    const tamperedRecordDigest = sha256HexFromString(tamperedCanonical);
    const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
    runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical: tamperedCanonical, recordDigest: tamperedRecordDigest });
    runtime.queueGuardApproval = runtime.queueGuardContext = { ...context, recordDigest: tamperedRecordDigest, receipt: { ...context.receipt, record_digest: tamperedRecordDigest } };
    assert.equal(harness.app.queuePrompt("tampered-token"), null);
    assert.equal(runtime.queueGuardBlockNotice?.code, "approved_record_digest_mismatch");
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.equal(harness.apiQueuePromptCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("real-shaped finalize rejects each independent receipt, transaction, approval, and request conflict", async (t) => {
  const conflicts = [
    ["outer event turn", (response) => { response.receipt.turn_id = "outer-turn-conflict"; }],
    ["outer event plan", (response) => { response.receipt.plan_hash = "outer-plan-conflict"; }],
    ["outer event generation", (response) => { response.receipt.generation = 2; }],
    ["top-level plan", (response) => { response.plan_hash = "top-level-plan-conflict"; }],
    ["top-level generation", (response) => { response.generation = 2; }],
    ["nested receipt turn", (response) => { response.receipt.receipt.turn_id = "nested-turn-conflict"; }],
    ["nested receipt plan", (response) => { response.receipt.receipt.plan_hash = "nested-plan-conflict"; }],
    ["nested receipt revision", (response) => { response.receipt.receipt.revision_id = "nested-revision-conflict"; }],
    ["nested receipt parent", (response) => { response.receipt.receipt.parent_revision = "nested-parent-conflict"; }],
    ["nested unsafe generation", (response) => { response.receipt.receipt.generation = 9007199254740992; }],
    ["nested NaN generation", (response) => { response.receipt.receipt.generation = Number.NaN; }],
    ["nested Infinity generation", (response) => { response.receipt.receipt.generation = Number.POSITIVE_INFINITY; }],
    ["transaction plan", (response) => { response.candidate_transaction.plan_hash = "transaction-plan-conflict"; }],
    ["transaction session", (response) => { response.candidate_transaction.session_id = "transaction-session-conflict"; }],
    ["transaction turn", (response) => { response.candidate_transaction.turn_id = "transaction-turn-conflict"; }],
    ["transaction revision", (response) => { response.candidate_transaction.revision_id = "transaction-revision-conflict"; }],
    ["transaction parent", (response) => { response.candidate_transaction.parent_revision = "transaction-parent-conflict"; }],
    ["transaction generation", (response) => { response.candidate_transaction.generation = 2; }],
    ["transaction lease", (response) => { response.candidate_transaction.lease_nonce = "transaction-lease-conflict"; }],
    ["authority workflow", (response) => { response.candidate_transaction.candidate_authority.workflow_id = "authority-workflow-conflict"; }],
    ["authority transaction", (response) => { response.candidate_transaction.candidate_authority.transaction_id = "authority-transaction-conflict"; }],
    ["authority candidate", (response) => { response.candidate_transaction.candidate_authority.candidate_id = "authority-candidate-conflict"; }],
    ["prepared workflow", (response) => { response.candidate_transaction.prepared_authority.workflow_id = "prepared-workflow-conflict"; }],
    ["prepared transaction", (response) => { response.candidate_transaction.prepared_authority.transaction_id = "prepared-transaction-conflict"; }],
    ["prepared candidate", (response) => { response.candidate_transaction.prepared_authority.candidate_id = "prepared-candidate-conflict"; }],
    ["prepared session", (response) => { response.candidate_transaction.prepared_authority.session_id = "prepared-session-conflict"; }],
    ["prepared turn", (response) => { response.candidate_transaction.prepared_authority.turn_id = "prepared-turn-conflict"; }],
    ["prepared plan", (response) => { response.candidate_transaction.prepared_authority.plan_hash = "prepared-plan-conflict"; }],
    ["prepared generation", (response) => { response.candidate_transaction.prepared_authority.generation = 9007199254740992; }],
    ["prepared lease", (response) => { response.candidate_transaction.prepared_authority.lease_nonce = "prepared-lease-conflict"; }],
    ["missing prepared authority", (response) => { delete response.candidate_transaction.prepared_authority; }],
    ["null prepared authority", (response) => { response.candidate_transaction.prepared_authority = null; }],
    ["empty prepared authority", (response) => { response.candidate_transaction.prepared_authority = {}; }],
    ["candidate authority alias conflict", (response) => {
      response.candidate_transaction.candidateAuthority = structuredClone(response.candidate_transaction.candidate_authority);
      response.candidate_transaction.candidateAuthority.workflow_id = "candidate-alias-workflow-conflict";
    }],
    ["prepared authority alias conflict", (response) => {
      response.candidate_transaction.preparedAuthority = structuredClone(response.candidate_transaction.prepared_authority);
      response.candidate_transaction.preparedAuthority.lease_nonce = "prepared-alias-lease-conflict";
    }],
    ["approval revision", (response) => { response.receipt.receipt.approval.revision_id = "approval-revision-conflict"; }],
    ["approval parent", (response) => { response.receipt.receipt.approval.parent_revision = "approval-parent-conflict"; }],
    ["approval api digest", (response) => { response.receipt.receipt.approval.api_digest = "0".repeat(64); }],
    ["approval record digest", (response) => { response.receipt.receipt.approval.record_digest = "0".repeat(64); }],
    ["captured request revision", (response) => { response.revision_id = "request-revision-conflict"; }],
    ["captured request parent", (response) => { response.parent_revision = "request-parent-conflict"; }],
  ];
  for (const [name, mutateResponse] of conflicts) {
    const result = await runDeferredRealFinalizeCase(t, { mutateResponse });
    if (!result) return;
    try {
      assert.equal(result.runtimeModule.getScopeApprovedRecord(result.scope.scopeId), null, name);
      assert.equal(result.harness.apiQueuePromptCalls.length, 0, name);
      assert.equal(result.harness.queuePromptCalls.length, 0, name);
    } finally {
      await result.harness.dispose();
    }
  }
});

test("real reduced replay finalize response cannot fresh-publish without transaction or canonical bytes", async (t) => {
  const result = await runDeferredRealFinalizeCase(t, {
    mutateResponse(response) {
      delete response.candidate_transaction;
      delete response.approved_record_canonical;
    },
  });
  if (!result) return;
  try {
    assert.equal(result.runtimeModule.getScopeApprovedRecord(result.scope.scopeId), null);
    assert.equal(result.harness.apiQueuePromptCalls.length, 0);
    assert.equal(result.harness.queuePromptCalls.length, 0);
    assert.notEqual(result.panel.state.phase, "READY");
  } finally {
    await result.harness.dispose();
  }
});

test("canonical queue blocker matrix never calls either queue function", async () => {
  const cases = [
    ["missing record", "missing_approved_record", (fixture, runtimeModule) => runtimeModule.saveScopeApprovedRecord("queue-scope", null)],
    ["extra schema key", "approved_record_schema", (fixture, runtimeModule, runtime, context) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical: canonicalJsonString({ ...JSON.parse(fixture.canonical), extra: true }) });
    }],
    ["wrong selected variant type", "approved_record_types", (fixture, runtimeModule) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical: canonicalJsonString({ ...JSON.parse(fixture.canonical), selected_variant: 3 }) });
    }],
    ["stale revision", "approved_record_digest_mismatch", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardApproval = runtime.queueGuardContext = { ...context, revisionId: "rev-other" };
    }],
    ["stale parent", "approved_record_digest_mismatch", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardApproval = runtime.queueGuardContext = { ...context, parentRevision: "parent-other", receipt: { ...context.receipt, parent_revision: "parent-other" } };
    }],
    ["binding mismatch", "input_binding_mismatch", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardApproval = runtime.queueGuardContext = { ...context, inputBinding: { node: "other" } };
    }],
    ["API digest mismatch", "approved_record_digest_mismatch", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardApproval = runtime.queueGuardContext = { ...context, receipt: { ...context.receipt, api_digest: "0".repeat(64) } };
    }],
    ["record digest mismatch", "approved_record_digest_mismatch", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardApproval = runtime.queueGuardContext = { ...context, receipt: { ...context.receipt, record_digest: "0".repeat(64) } };
    }],
    ["unsafe positive integer", "malformed_approved_record", (fixture, runtimeModule, runtime, context) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      const record = JSON.parse(fixture.canonical);
      record.api_projection = { unsafe: 9007199254740992 };
      record.api_digest = sha256Hex(record.api_projection);
      const canonical = canonicalJsonString(record);
      const recordDigest = sha256HexFromString(canonical);
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical, apiDigest: record.api_digest, recordDigest });
      runtime.queueGuardApproval = runtime.queueGuardContext = { ...context, receipt: { ...context.receipt, api_digest: record.api_digest, record_digest: recordDigest } };
    }],
    ["unsafe negative integer", "malformed_approved_record", (fixture, runtimeModule, runtime, context) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      const record = JSON.parse(fixture.canonical);
      record.api_projection = { unsafe: -9007199254740992 };
      record.api_digest = sha256Hex(record.api_projection);
      const canonical = canonicalJsonString(record);
      const recordDigest = sha256HexFromString(canonical);
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical, apiDigest: record.api_digest, recordDigest });
      runtime.queueGuardApproval = runtime.queueGuardContext = { ...context, receipt: { ...context.receipt, api_digest: record.api_digest, record_digest: recordDigest } };
    }],
    ["non-finite value", "malformed_approved_record", (fixture, runtimeModule) => {
      const saved = runtimeModule.getScopeApprovedRecord("queue-scope");
      runtimeModule.saveScopeApprovedRecord("queue-scope", { ...saved, canonical: fixture.canonical.replace('"api_digest"', '"bad":NaN,"api_digest"') });
    }],
    ["queue disabled", "queue_disabled", (fixture, runtimeModule, runtime, context) => {
      runtime.queueGuardApproval = runtime.queueGuardContext = { ...context, queueAllowed: false };
    }],
  ];
  for (const [name, expectedCode, mutate] of cases) {
    const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
    try {
      const fixture = approvedFixture();
      const panel = extension.ensureAgentPanel();
      seedApprovedRecord(runtimeModule, runtime, panel, fixture);
      mutate(fixture, runtimeModule, runtime, runtime.queueGuardContext);
      assert.equal(harness.app.queuePrompt("canvas"), null, name);
      assert.equal(runtime.queueGuardBlockNotice?.code, expectedCode, name);
      assert.equal(harness.queuePromptCalls.length, 0, name);
      assert.equal(harness.apiQueuePromptCalls.length, 0, name);
    } finally {
      await harness.dispose();
    }
  }
});

test("replaced queue hook fails closed without transport", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    harness.setQueuePromptHookFault("replaced");
    assert.equal(harness.app.queuePrompt("caller"), null);
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.equal(harness.apiQueuePromptCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("each graph hook fault is isolated behind a healthy queue hook", async () => {
  for (const mode of ["missing", "replaced", "defineproperty_replaced", "unwritable"]) {
    const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
    try {
      seedApprovedRecord(runtimeModule, runtime, extension.ensureAgentPanel(), approvedFixture());
      assert.equal(runtime.queueGuardHook?.healthy?.(), true, mode);
      harness.setGraphMutationHookFault(mode);
      assert.equal(harness.app.queuePrompt(`graph-${mode}`), null, mode);
      assert.equal(runtime.queueGuardBlockNotice?.code, "mutation_hook_unverifiable", mode);
      assert.equal(harness.queuePromptCalls.length, 0, mode);
      assert.equal(harness.apiQueuePromptCalls.length, 0, mode);
    } finally {
      await harness.dispose();
    }
  }
});

test("defineProperty hook replacement fails closed without transport", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    seedApprovedRecord(runtimeModule, runtime, extension.ensureAgentPanel(), fixture);
    const wrapper = runtime.queueGuardHook.wrapper;
    harness.setQueuePromptHookFault("defineproperty_replaced");
    assert.equal(runtime.queueGuardHook.healthy(), false);
    assert.equal(wrapper("caller"), null);
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.equal(harness.apiQueuePromptCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("API queue transport absence is an observable fail-closed blocker", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness({ withApiQueuePrompt: false });
  try {
    const fixture = approvedFixture();
    seedApprovedRecord(runtimeModule, runtime, extension.ensureAgentPanel(), fixture);
    assert.equal(harness.app.queuePrompt("caller"), null);
    assert.equal(runtime.queueGuardBlockNotice?.code, "api_queue_unavailable");
    assert.equal(harness.queuePromptCalls.length, 0);
    assert.equal(harness.apiQueuePromptCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("retained old graph callbacks cannot invalidate a replacement live graph scope", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    const oldGraph = harness.app.canvas.graph;
    const before = runtime.queueGuardInvalidationGeneration;
    harness.replaceLiveGraph({ nodes: [{ id: 2, type: "Replacement", properties: { vibecomfy_uid: "uid-2" } }], links: [] });
    oldGraph.change();
    assert.equal(runtime.queueGuardInvalidationGeneration, before);
    assert.equal(harness.app.queuePrompt("caller"), null);
    assert.equal(harness.apiQueuePromptCalls.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("A to B to reused A rebinds graph custody and never restores A approval", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    const graphA = harness.app.canvas.graph;
    const oldAWrapper = runtime.queueGuardMutationHook.wrapper;
    harness.replaceLiveGraph({ nodes: [{ id: 2, type: "B", properties: { vibecomfy_uid: "uid-b" } }], links: [] });
    panel.state.scopeActivationEpoch += 1;
    assert.equal(harness.app.queuePrompt("B-before-finalize"), null);
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    harness.reuseLiveGraph(graphA);
    panel.state.scopeActivationEpoch += 1;
    assert.equal(harness.app.queuePrompt("A-reused"), null);
    assert.equal(harness.apiQueuePromptCalls.length, 0);
    assert.equal(runtime.queueGuardMutationHook.graph, graphA);
    assert.notEqual(runtime.queueGuardMutationHook.wrapper, oldAWrapper);
  } finally {
    await harness.dispose();
  }
});

test("real finalized A to B to A loadGraphData transition requires new approval", async (t) => {
  const result = await runDeferredRealFinalizeCase(t);
  if (!result) return;
  const originalGlobalApp = globalThis.app;
  globalThis.app = result.harness.app;
  try {
    const { harness, panel, runtime, runtimeModule, scope, extension, setFinalizeCycle } = result;
    const graphA = harness.getCurrentGraph();
    const graphObjectA = harness.app.canvas.graph;
    const oldAWrapper = runtime.queueGuardMutationHook.wrapper;
    const activationA = panel.state.scopeActivationEpoch;
    const workflow = harness.app.extensionManager.workflow;
    const workflowA = workflow.vibecomfyScopeMetadata.workflow_id;
    workflow.vibecomfyScopeMetadata.workflow_id = "223e4567-e89b-12d3-a456-426614174001";
    const graphB = structuredClone(graphA);
    graphB.nodes[0].properties.vibecomfy_uid = "uid-b";
    harness.app.loadGraphData(graphB);
    const scopeB = extension.resolveActiveCanvasScope();
    assert.ok(scopeB?.scopeId);
    assert.notEqual(scopeB.scopeId, scope.scopeId);
    assert.equal(harness.app.canvas.graph, graphObjectA);
    assert.notEqual(panel.state.scopeActivationEpoch, activationA);
    assert.notEqual(runtime.queueGuardMutationHook.wrapper, oldAWrapper);
    assert.equal(runtime.queueGuardMutationHook.scopeActivation, panel.state.scopeActivationEpoch);

    const bSessionId = "session-t19-deferred";
    const bTurnId = "deferred-0001";
    const bPlanHash = "plan-t19-b";
    const bCandidateGraph = { nodes: [...graphB.nodes, { id: 3, type: "SaveImage", properties: { vibecomfy_uid: "uid-b-save" } }], links: [] };
    const bDeltaOps = [{ op: "add_node", scope_path: "", uid: "uid-b-save", node_id: "3", class_type: "SaveImage", fields: { properties: { vibecomfy_uid: "uid-b-save" } }, inputs: {} }];
    const bWorkflowId = workflow.vibecomfyScopeMetadata.workflow_id;
    const bCandidate = makeValidCandidateTransactionV2({ sessionId: bSessionId, turnId: bTurnId, workflowId: bWorkflowId, planHash: bPlanHash, deltaOps: bDeltaOps });
    bCandidate.revision_id = "d".repeat(64);
    bCandidate.parent_revision = "";
    const bFixture = pythonApprovedFixture(t, bCandidate.revision_id, "rich");
    if (!bFixture) return;
    const bPrepared = makeValidCandidateTransactionV2({ sessionId: bSessionId, turnId: bTurnId, workflowId: bWorkflowId, planHash: bPlanHash, deltaOps: bDeltaOps, state: "prepared", generation: 1, leaseNonce: "lease-t19-b", overrides: { revision_id: bCandidate.revision_id, parent_revision: "" } });
    const bFinalized = makeValidCandidateTransactionV2({ sessionId: bSessionId, turnId: bTurnId, workflowId: bWorkflowId, planHash: bPlanHash, deltaOps: bDeltaOps, state: "finalized", generation: 1, leaseNonce: "lease-t19-b", overrides: { revision_id: bCandidate.revision_id, parent_revision: "" } });
    for (const transaction of [bCandidate, bPrepared, bFinalized]) {
      transaction.revision_id = bCandidate.revision_id;
      transaction.parent_revision = "";
      bindTransactionHashes(null, transaction, bCandidateGraph, graphB);
    }
    assert.ok(normalizeCandidateTransaction(bCandidate), JSON.stringify(bCandidate));
    const bApproval = { revision_id: bCandidate.revision_id, parent_revision: "", api_digest: bFixture.api_digest, record_digest: bFixture.record_digest };
    setFinalizeCycle({
      sessionId: bSessionId,
      turnId: bTurnId,
      planHash: bPlanHash,
      graph: graphB,
      candidateGraph: bCandidateGraph,
      candidateTransaction: bCandidate,
      preparedTransaction: bPrepared,
      finalizedTransaction: bFinalized,
      pythonFixture: bFixture,
      approval: bApproval,
      deferFinalize: false,
    });
    panel.state.chatScopeId = scopeB.scopeId;
    panel.state.chatScopeFingerprint = scopeB.fingerprint;
    harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "finalize B";
    panel.buttons.submit.disabled = false;
    await harness.clickButton("Submit");
    for (let index = 0; index < 40 && panel.state.phase !== "AWAITING_REVIEW"; index += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(panel.state.phase, "AWAITING_REVIEW");
    assert.ok(normalizeCandidateTransaction(panel.state.candidateTransaction), JSON.stringify(panel.state.candidateTransaction));
    panel.state.chatRehydratePending = false;
    panel.buttons.apply.disabled = false;
    panel.buttons.apply.click();
    for (let index = 0; index < 100 && panel.state.phase !== "FINALIZED"; index += 1) await new Promise((resolve) => setTimeout(resolve, 10));
    assert.equal(panel.state.phase, "FINALIZED", JSON.stringify({ failure: panel.state.failure, message: panel.state.message, requests: harness.requests }));
    assert.ok(runtimeModule.getScopeApprovedRecord(scopeB.scopeId));

    // The retained A wrapper is stale after the real scope transition and
    // must not revoke B's newly published approval.
    oldAWrapper();
    assert.ok(runtimeModule.getScopeApprovedRecord(scopeB.scopeId));
    harness.app.canvas.graph.change();
    assert.equal(runtimeModule.getScopeApprovedRecord(scopeB.scopeId), null);
    assert.equal(harness.app.queuePrompt("B-after-mutation"), null);

    workflow.vibecomfyScopeMetadata.workflow_id = workflowA;
    harness.app.loadGraphData(graphA);
    assert.equal(harness.app.canvas.graph, graphObjectA);
    assert.equal(runtimeModule.getScopeApprovedRecord(scope.scopeId), null);
    assert.equal(harness.app.queuePrompt("A-reused-before-new-approval"), null);
    assert.equal(runtime.queueGuardBlockNotice?.code, "missing_approved_record");
    assert.equal(harness.apiQueuePromptCalls.length, 0);
    assert.equal(harness.queuePromptCalls.length, 0);
  } finally {
    if (originalGlobalApp === undefined) delete globalThis.app;
    else globalThis.app = originalGlobalApp;
    await result.harness.dispose();
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

test("live authority mutation after real publication is a named fail-closed cause", async (t) => {
  const mutations = [
    ["revision", (panel) => { panel.state.candidateTransaction.revision_id = "rev-mutated"; }],
    ["parent", (panel) => { panel.state.candidateTransaction.parent_revision = "parent-mutated"; }],
    ["session", (panel) => { panel.state.candidateTransaction.session_id = "session-mutated"; }],
    ["turn", (panel) => { panel.state.candidateTransaction.turn_id = "turn-mutated"; }],
    ["plan", (panel) => { panel.state.candidateTransaction.plan_hash = "plan-mutated"; }],
    ["generation", (panel) => { panel.state.candidateTransaction.generation = 2; }],
    ["lease", (panel) => { panel.state.candidateTransaction.lease_nonce = "lease-mutated"; }],
    ["transaction", (panel) => { panel.state.candidateTransaction.candidate_authority.transaction_id = "tx-mutated"; }],
    ["candidate", (panel) => { panel.state.candidateTransaction.candidate_authority.candidate_id = "candidate-mutated"; }],
    ["workflow", (panel) => { panel.state.candidateTransaction.candidate_authority.workflow_id = "workflow-mutated"; }],
    ["prepared session", (panel) => { panel.state.candidateTransaction.prepared_authority.session_id = "prepared-session-mutated"; }],
    ["prepared turn", (panel) => { panel.state.candidateTransaction.prepared_authority.turn_id = "prepared-turn-mutated"; }],
    ["prepared plan", (panel) => { panel.state.candidateTransaction.prepared_authority.plan_hash = "prepared-plan-mutated"; }],
    ["prepared generation", (panel) => { panel.state.candidateTransaction.prepared_authority.generation = 9007199254740992; }],
    ["prepared lease", (panel) => { panel.state.candidateTransaction.prepared_authority.lease_nonce = "prepared-lease-mutated"; }],
    ["missing prepared authority", (panel) => { delete panel.state.candidateTransaction.prepared_authority; }],
    ["null prepared authority", (panel) => { panel.state.candidateTransaction.prepared_authority = null; }],
    ["empty prepared authority", (panel) => { panel.state.candidateTransaction.prepared_authority = {}; }],
    ["candidate authority alias conflict", (panel) => {
      panel.state.candidateTransaction.candidateAuthority = structuredClone(panel.state.candidateTransaction.candidate_authority);
      panel.state.candidateTransaction.candidateAuthority.workflow_id = "candidate-alias-workflow-mutated";
    }],
    ["prepared authority alias conflict", (panel) => {
      panel.state.candidateTransaction.preparedAuthority = structuredClone(panel.state.candidateTransaction.prepared_authority);
      panel.state.candidateTransaction.preparedAuthority.lease_nonce = "prepared-alias-lease-mutated";
    }],
    ["activation", (panel) => { panel.state.scopeActivationEpoch += 1; }],
    ["fresh graph", (_panel, harness) => { harness.replaceLiveGraph({ nodes: [{ id: 7, type: "Fresh" }], links: [] }); }],
    ["ordinary graph", (_panel, harness) => { harness.app.canvas.graph.change(); }],
  ];
  for (const [name, mutate] of mutations) {
    const result = await runDeferredRealFinalizeCase(t);
    if (!result) return;
    const { harness, panel, runtimeModule, runtime } = result;
    try {
      if (!["fresh graph", "ordinary graph"].includes(name)) {
        panel.state.candidateTransaction = structuredClone(panel.state.candidateTransaction);
      }
      mutate(panel, harness);
      assert.equal(harness.app.queuePrompt("caller"), null, name);
      assert.equal(runtime.queueGuardBlockNotice?.code, ["fresh graph", "ordinary graph"].includes(name) ? "missing_approved_record" : "queue_attempt_stale", name);
      assert.equal(harness.queuePromptCalls.length, 0, name);
      assert.equal(harness.apiQueuePromptCalls.length, 0, name);
    } finally {
      await harness.dispose();
    }
  }
});

test("safe numeric spellings remain queueable", async (t) => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const pythonFixture = pythonApprovedFixture(t, "t19-safe-numbers", "rich");
    if (!pythonFixture) return;
    const fixture = {
      canonical: pythonFixture.canonical,
      receipt: {
        revision_id: pythonFixture.revision_id,
        api_digest: pythonFixture.api_digest,
        record_digest: pythonFixture.record_digest,
      },
    };
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture, {
      revisionId: pythonFixture.revision_id,
      apiDigest: pythonFixture.api_digest,
      recordDigest: pythonFixture.record_digest,
      recordRecordDigest: pythonFixture.record_digest,
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
    assert.equal(runtime.queueGuardPromptAttempt.promptId, "prompt-1");
    harness.dispatchApiEvent("execution_start", { prompt_id: "foreign" });
    harness.dispatchApiEvent("executing", { prompt_id: "foreign", node: null });
    harness.dispatchApiEvent("progress", {});
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "pending");
    harness.dispatchApiEvent("execution_start", { prompt_id: "prompt-1" });
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "running");
    harness.dispatchApiEvent("executing", { prompt_id: "prompt-1", node: null });
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "ended_observation");
    assert.equal(harness.apiEventListeners.execution_error?.length, 1);
    harness.dispatchApiEvent("execution_error", { prompt_id: "prompt-1", error: "boom" });
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "error", JSON.stringify({ lifecycle: runtime.queueGuardLifecycle, context: runtime.queueGuardPromptAttempt }));
    harness.dispatchApiEvent("executing", { prompt_id: "prompt-1", node: null });
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "error");
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
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "unsupported");
    assert.equal(runtime.queueGuardPromptAttempt.operationUnsupported, "delete");
    harness.dispatchApiEvent("execution_start", { prompt_id: "prompt-1" });
    harness.dispatchApiEvent("progress", { prompt_id: "prompt-1" });
    harness.dispatchApiEvent("executed", { prompt_id: "prompt-1" });
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "unsupported");
    assert.equal(runtime.queueGuardLifecycle.error.includes("delete"), true);
  } finally {
    await harness.dispose();
  }
});

test("prompt lifecycle remains scoped when a newer prompt supersedes an older attempt", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const fixture = approvedFixture();
    const panel = extension.ensureAgentPanel();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    assert.deepEqual(harness.app.queuePrompt("p1"), { prompt_id: "prompt-1" });
    harness.dispatchApiEvent("execution_error", { prompt_id: "prompt-1", error: "p1 failed" });
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "error");
    assert.equal(runtime.queueGuardBlockNotice.promptId, "prompt-1");
    assert.throws(() => extension.requestQueuePromptOperation("cancel"), /cancel.*prompt-1/);
    assert.equal(runtime.queueGuardPromptAttempt.operationUnsupported, "cancel");
    assert.deepEqual(harness.app.queuePrompt("p2"), { prompt_id: "prompt-2" });
    assert.equal(runtime.queueGuardLifecycle, null);
    assert.equal(runtime.queueGuardBlockNotice, null);
    harness.dispatchApiEvent("execution_error", { prompt_id: "prompt-1", error: "late p1" });
    assert.equal(runtime.queueGuardPromptAttempt.promptId, "prompt-2");
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "pending");
    harness.dispatchApiEvent("execution_start", { prompt_id: "prompt-2" });
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "running");
    harness.dispatchApiEvent("executed", { prompt_id: "prompt-1" });
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "running");
  } finally {
    await harness.dispose();
  }
});

test("prior lifecycle diagnostics survive failed P2 attempts and generic invalidation", async () => {
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness();
  try {
    const panel = extension.ensureAgentPanel();
    const fixture = approvedFixture();
    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    assert.deepEqual(harness.app.queuePrompt("p1"), { prompt_id: "prompt-1" });
    harness.dispatchApiEvent("execution_error", { prompt_id: "prompt-1", error: "p1 failed" });
    const priorLifecycle = runtime.queueGuardLifecycle;
    const priorBlock = runtime.queueGuardBlockNotice;
    assert.equal(priorBlock?.code, "queue_prompt_lifecycle_error");

    const validCandidateTransaction = structuredClone(panel.state.candidateTransaction);
    panel.state.candidateTransaction = structuredClone(panel.state.candidateTransaction);
    panel.state.candidateTransaction.revision_id = "stale-p2-revision";
    assert.equal(harness.app.queuePrompt("stale-p2"), null);
    assert.deepEqual(runtime.queueGuardLifecycle, priorLifecycle);
    assert.deepEqual(runtime.queueGuardBlockNotice, priorBlock);

    panel.state.candidateTransaction = validCandidateTransaction;
    const originalApiQueuePrompt = harness.api.queuePrompt;
    const toastCountBeforeApiFailure = harness.toasts.length;
    harness.api.queuePrompt = undefined;
    assert.equal(harness.app.queuePrompt("unavailable-p2"), null);
    assert.deepEqual(runtime.queueGuardLifecycle, priorLifecycle);
    assert.deepEqual(runtime.queueGuardBlockNotice, priorBlock);
    assert.ok(harness.toasts.slice(toastCountBeforeApiFailure).some((entry) => String(entry?.summary || entry?.detail || "").includes("queuePrompt is unavailable")));
    harness.api.queuePrompt = originalApiQueuePrompt;

    harness.app.canvas.graph.change();
    assert.deepEqual(runtime.queueGuardLifecycle, priorLifecycle);
    assert.deepEqual(runtime.queueGuardBlockNotice, priorBlock);

    seedApprovedRecord(runtimeModule, runtime, panel, fixture);
    assert.deepEqual(harness.app.queuePrompt("valid-p2"), { prompt_id: "prompt-2" });
    assert.equal(runtime.queueGuardLifecycle, null);
    assert.equal(runtime.queueGuardBlockNotice, null);
  } finally {
    await harness.dispose();
  }
});

test("deferred lower prompt result cannot overwrite the newer prompt diagnostics", async () => {
  const deferred = [];
  const { harness, extension, runtimeModule, runtime } = await setupQueueHarness({
    apiQueuePromptResponder: () => new Promise((resolve, reject) => deferred.push({ resolve, reject })),
  });
  try {
    const fixture = approvedFixture();
    seedApprovedRecord(runtimeModule, runtime, extension.ensureAgentPanel(), fixture);
    const p1 = harness.app.queuePrompt("p1");
    const p2 = harness.app.queuePrompt("p2");
    assert.equal(deferred.length, 2);
    deferred[1].resolve({ prompt_id: "prompt-2" });
    assert.deepEqual(await p2, { prompt_id: "prompt-2" });
    deferred[0].resolve({ prompt_id: "prompt-1" });
    await assert.rejects(p1, /stale/);
    assert.equal(runtime.queueGuardPromptAttempt.promptId, "prompt-2");
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "pending");
    harness.dispatchApiEvent("execution_error", { prompt_id: "prompt-1", error: "late p1" });
    assert.equal(runtime.queueGuardPromptAttempt.promptId, "prompt-2");
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "pending");
    harness.dispatchApiEvent("execution_start", { prompt_id: "prompt-2" });
    assert.equal(runtime.queueGuardPromptAttempt.lifecycleState, "running");
  } finally {
    await harness.dispose();
  }
});
