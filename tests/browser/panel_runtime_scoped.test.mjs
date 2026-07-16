import test from "node:test";
import assert from "node:assert/strict";

// ── Dynamic import ────────────────────────────────────────────────────────
// panel_runtime.js uses a fallback record when window is absent (Node.js),
// so all scope snapshot/draft/queue-guard functions are testable here.

let _importCounter = 0;

async function loadRuntime() {
  const url = new URL(
    "../../vibecomfy/comfy_nodes/web/panel_runtime.js",
    import.meta.url,
  ).href;
  // Counter + high-resolution time to guarantee unique module instances.
  _importCounter += 1;
  return await import(`${url}?c=${_importCounter}&t=${performance.now()}`);
}

// ── Helpers ───────────────────────────────────────────────────────────────

function makePanel(overrides = {}) {
  const state = {
    phase: "IDLE",
    sessionId: null,
    turnId: null,
    chatScopeId: null,
    chatScopeFingerprint: null,
    candidateScopeId: null,
    submittingScopeId: null,
    candidateGraph: null,
    candidateGraphHash: null,
    message: null,
    failure: null,
    undoStack: [],
    applyAllowed: false,
    canvasApplyAllowed: false,
    queueAllowed: false,
    submitEpoch: 0,
    chatRehydrateEpoch: 0,
    chatMessages: null,
    turns: null,
    history: null,
    // DOM references (excluded from snapshot)
    buttons: { submit: {}, stop: {}, apply: {}, reject: {}, undo: {} },
    sections: { meta: {}, composer: {}, thread: {} },
    fields: {},
    root: {},
    composerButtons: {},
    // Ephemeral render state (excluded from snapshot)
    pendingDirtySections: [],
    __renderErrors: [],
    __renderFailureCounts: {},
    mountMode: "inline",
    mountContainer: null,
    // In-flight async state (nulled in snapshot)
    submitAbortController: new AbortController(),
    inFlightSubmit: Promise.resolve(),
    inFlightApply: null,
    inFlightRebaseline: null,
    // Non-lifecycle user data
    history: ["entry1", "entry2"],
    ...overrides,
  };
  return { state };
}

// ── SCOPE_SNAPSHOT_EXCLUDE ────────────────────────────────────────────────

test("SCOPE_SNAPSHOT_EXCLUDE contains undoStack (SD3: canvas-affine)", async () => {
  // We verify indirectly by saving a snapshot and confirming undoStack is absent.
  const { saveScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  const panel = makePanel({
    chatScopeId: "scope-test",
    sessionId: "sess-test",
    undoStack: [{ op: "undo-me", turn: "001" }],
  });

  saveScopeSnapshot("scope-test", panel);
  const runtime = getAgentPanelRuntime();
  const snapshot = runtime._scopeSnapshots.get("scope-test");

  assert.ok(snapshot, "snapshot must exist");
  // undoStack must NOT be in the snapshot.
  assert.equal(
    Object.prototype.hasOwnProperty.call(snapshot, "undoStack"),
    false,
    "undoStack must be excluded from scope snapshots (SD3)",
  );
});

test("SCOPE_SNAPSHOT_EXCLUDE excludes DOM reference fields", async () => {
  const { saveScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  const panel = makePanel({
    chatScopeId: "scope-dom",
    sessionId: "sess-dom",
  });

  saveScopeSnapshot("scope-dom", panel);
  const runtime = getAgentPanelRuntime();
  const snapshot = runtime._scopeSnapshots.get("scope-dom");

  assert.ok(snapshot, "snapshot must exist");
  // DOM references must not be in the snapshot.
  for (const domField of ["buttons", "sections", "fields", "root", "composerButtons"]) {
    assert.equal(
      Object.prototype.hasOwnProperty.call(snapshot, domField),
      false,
      `DOM field "${domField}" must be excluded from scope snapshots`,
    );
  }
});

test("SCOPE_SNAPSHOT_EXCLUDE excludes ephemeral render state", async () => {
  const { saveScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  const panel = makePanel({
    chatScopeId: "scope-render",
    pendingDirtySections: ["META"],
    __renderErrors: ["oops"],
    mountMode: "sidebar",
  });

  saveScopeSnapshot("scope-render", panel);
  const runtime = getAgentPanelRuntime();
  const snapshot = runtime._scopeSnapshots.get("scope-render");

  for (const ephemeralField of ["pendingDirtySections", "__renderErrors", "__renderFailureCounts", "mountMode", "mountContainer"]) {
    assert.equal(
      Object.prototype.hasOwnProperty.call(snapshot, ephemeralField),
      false,
      `Ephemeral field "${ephemeralField}" must be excluded from scope snapshots`,
    );
  }
});

test("scopeActivationEpoch is runtime-affine and never restored from a workflow snapshot", async () => {
  const { saveScopeSnapshot, restoreScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();
  const panel = makePanel({
    chatScopeId: "scope-activation",
    scopeActivationEpoch: 4,
    sessionId: "sess-activation",
  });

  saveScopeSnapshot("scope-activation", panel);
  const snapshot = getAgentPanelRuntime()._scopeSnapshots.get("scope-activation");
  assert.equal(
    Object.prototype.hasOwnProperty.call(snapshot, "scopeActivationEpoch"),
    false,
  );

  panel.state.scopeActivationEpoch = 9;
  restoreScopeSnapshot("scope-activation", panel);
  assert.equal(panel.state.scopeActivationEpoch, 9);
});

// ── saveScopeSnapshot / restoreScopeSnapshot ──────────────────────────────

test("saveScopeSnapshot captures all panel.state fields except excluded ones", async () => {
  const { saveScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  const panel = makePanel({
    chatScopeId: "scope-A",
    chatScopeFingerprint: "fp-aaa",
    sessionId: "sess-A",
    turnId: "turn-001",
    phase: "AWAITING_REVIEW",
    candidateGraph: { nodes: [{ id: 1, type: "KSampler" }] },
    candidateGraphHash: "hash-001",
    candidateScopeId: "scope-A",
    message: "candidate ready",
    queueAllowed: true,
    canvasApplyAllowed: true,
    applyAllowed: true,
    submitEpoch: 3,
    chatRehydrateEpoch: 5,
    chatMessages: [{ role: "user", text: "hello" }],
    turns: [{ turn_id: "turn-001" }],
    history: ["entry1", "entry2"],
  });

  saveScopeSnapshot("scope-A", panel);
  const runtime = getAgentPanelRuntime();
  const snapshot = runtime._scopeSnapshots.get("scope-A");

  assert.ok(snapshot, "snapshot must exist");
  // Lifecycle fields are captured.
  assert.equal(snapshot.chatScopeId, "scope-A");
  assert.equal(snapshot.chatScopeFingerprint, "fp-aaa");
  assert.equal(snapshot.sessionId, "sess-A");
  assert.equal(snapshot.turnId, "turn-001");
  assert.equal(snapshot.phase, "AWAITING_REVIEW");
  assert.deepEqual(snapshot.candidateGraph, { nodes: [{ id: 1, type: "KSampler" }] });
  assert.equal(snapshot.candidateGraphHash, "hash-001");
  assert.equal(snapshot.candidateScopeId, "scope-A");
  assert.equal(snapshot.message, "candidate ready");
  assert.equal(snapshot.queueAllowed, true);
  assert.equal(snapshot.canvasApplyAllowed, true);
  assert.equal(snapshot.applyAllowed, true);
  assert.equal(snapshot.submitEpoch, 3);
  assert.equal(snapshot.chatRehydrateEpoch, 5);
  // Non-lifecycle data is captured.
  assert.deepEqual(snapshot.chatMessages, [{ role: "user", text: "hello" }]);
  assert.deepEqual(snapshot.turns, [{ turn_id: "turn-001" }]);
  assert.deepEqual(snapshot.history, ["entry1", "entry2"]);
  // Metadata stamps.
  assert.equal(snapshot._snapshotScopeId, "scope-A");
  assert.ok(typeof snapshot._snapshotCapturedAt === "string");
});

test("saveScopeSnapshot nulls out in-flight async state", async () => {
  const { saveScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  const panel = makePanel({
    chatScopeId: "scope-inflight",
    submitAbortController: new AbortController(),
    inFlightSubmit: Promise.resolve("submitting"),
    inFlightApply: Promise.resolve("applying"),
    inFlightRebaseline: Promise.resolve("rebaselining"),
  });

  saveScopeSnapshot("scope-inflight", panel);
  const runtime = getAgentPanelRuntime();
  const snapshot = runtime._scopeSnapshots.get("scope-inflight");

  assert.equal(snapshot.submitAbortController, null);
  assert.equal(snapshot.inFlightSubmit, null);
  assert.equal(snapshot.inFlightApply, null);
  assert.equal(snapshot.inFlightRebaseline, null);
});

test("restoreScopeSnapshot merges snapshot back onto panel.state", async () => {
  const { saveScopeSnapshot, restoreScopeSnapshot } = await loadRuntime();

  // First panel: save its state as scope-A.
  const panelA = makePanel({
    chatScopeId: "scope-A",
    sessionId: "sess-A",
    turnId: "turn-A1",
    phase: "AWAITING_REVIEW",
    message: "scope A candidate",
    queueAllowed: true,
    submitEpoch: 5,
    chatMessages: [{ role: "agent", text: "result A" }],
    history: ["A-entry"],
  });

  saveScopeSnapshot("scope-A", panelA);

  // Second panel: different state (simulating scope switch to B then back to A).
  const panelB = makePanel({
    chatScopeId: "scope-B",
    sessionId: "sess-B",
    turnId: "turn-B1",
    phase: "IDLE",
    message: null,
    queueAllowed: false,
    submitEpoch: 1,
    chatMessages: [{ role: "user", text: "edit B" }],
    history: ["B-entry"],
  });
  // Preserve undoStack — it must survive restore.
  panelB.state.undoStack = [{ op: "apply", turn: "999" }];

  const restored = restoreScopeSnapshot("scope-A", panelB);
  assert.equal(restored, true, "must return true when snapshot found");

  // Scope-A state is restored.
  assert.equal(panelB.state.chatScopeId, "scope-A");
  assert.equal(panelB.state.sessionId, "sess-A");
  assert.equal(panelB.state.turnId, "turn-A1");
  assert.equal(panelB.state.phase, "AWAITING_REVIEW");
  assert.equal(panelB.state.message, "scope A candidate");
  assert.equal(panelB.state.queueAllowed, true);
  assert.equal(panelB.state.submitEpoch, 5);
  assert.deepEqual(panelB.state.chatMessages, [{ role: "agent", text: "result A" }]);
  assert.deepEqual(panelB.state.history, ["A-entry"]);

  // Snapshot metadata keys are NOT written to panel.state.
  assert.equal(
    Object.prototype.hasOwnProperty.call(panelB.state, "_snapshotScopeId"),
    false,
    "_snapshotScopeId must not leak onto panel.state",
  );
  assert.equal(
    Object.prototype.hasOwnProperty.call(panelB.state, "_snapshotCapturedAt"),
    false,
    "_snapshotCapturedAt must not leak onto panel.state",
  );
});

test("restoreScopeSnapshot preserves undoStack (SD3: never overwritten)", async () => {
  const { saveScopeSnapshot, restoreScopeSnapshot } = await loadRuntime();

  // Panel with undoStack + scope data.
  const panel = makePanel({
    chatScopeId: "scope-undo",
    sessionId: "sess-undo",
    undoStack: [{ op: "apply", turn: "001" }, { op: "rebaseline", turn: "002" }],
    message: "some message",
  });

  saveScopeSnapshot("scope-undo", panel);

  // Clear message but keep undoStack (simulates scope switch away and back).
  panel.state.message = null;
  panel.state.sessionId = null;
  panel.state.chatScopeId = null;
  // undoStack must survive untouched.
  assert.deepEqual(panel.state.undoStack, [{ op: "apply", turn: "001" }, { op: "rebaseline", turn: "002" }]);

  restoreScopeSnapshot("scope-undo", panel);

  // undoStack is preserved exactly as it was before restore.
  assert.deepEqual(
    panel.state.undoStack,
    [{ op: "apply", turn: "001" }, { op: "rebaseline", turn: "002" }],
    "undoStack must survive restoreScopeSnapshot unchanged (SD3)",
  );
  // But other state is restored.
  assert.equal(panel.state.message, "some message");
  assert.equal(panel.state.sessionId, "sess-undo");
  assert.equal(panel.state.chatScopeId, "scope-undo");
});

test("restoreScopeSnapshot returns false for unknown scopeId", async () => {
  const { restoreScopeSnapshot } = await loadRuntime();
  const panel = makePanel({ chatScopeId: "scope-nope" });
  const result = restoreScopeSnapshot("never-saved", panel);
  assert.equal(result, false);
});

test("restoreScopeSnapshot returns false for null/empty scopeId", async () => {
  const { restoreScopeSnapshot } = await loadRuntime();
  const panel = makePanel();
  assert.equal(restoreScopeSnapshot(null, panel), false);
  assert.equal(restoreScopeSnapshot("", panel), false);
  assert.equal(restoreScopeSnapshot(undefined, panel), false);
});

test("restoreScopeSnapshot returns false for null/undefined panel", async () => {
  const { restoreScopeSnapshot } = await loadRuntime();
  assert.equal(restoreScopeSnapshot("scope-A", null), false);
  assert.equal(restoreScopeSnapshot("scope-A", undefined), false);
  assert.equal(restoreScopeSnapshot("scope-A", {}), false);
});

test("restoreScopeSnapshot leaves keys not in snapshot unchanged (merge semantics)", async () => {
  const { saveScopeSnapshot, restoreScopeSnapshot } = await loadRuntime();

  // Save a snapshot with known fields.
  const panel = makePanel({
    chatScopeId: "scope-merge",
    sessionId: "sess-merge",
    turnId: "turn-original",
  });
  saveScopeSnapshot("scope-merge", panel);

  // After snapshot, add a NEW key that did NOT exist at snapshot time.
  // This key is not in any LIFECYCLE_STATE_FIELDS and not in the snapshot.
  panel.state._customAfterSnapshot = "survived";
  // Also change some existing keys.
  panel.state.sessionId = "sess-overwritten";
  panel.state.turnId = "turn-overwritten";

  restoreScopeSnapshot("scope-merge", panel);

  // Keys that were in the snapshot are restored.
  assert.equal(panel.state.sessionId, "sess-merge");
  assert.equal(panel.state.turnId, "turn-original");
  // Key added AFTER snapshot was saved survives (merge semantics).
  assert.equal(
    panel.state._customAfterSnapshot,
    "survived",
    "keys added after snapshot should survive restore (merge semantics)",
  );
});

// ── forgetScopeSnapshot ──────────────────────────────────────────────────

test("forgetScopeSnapshot clears snapshot and draft for a scope", async () => {
  const { saveScopeSnapshot, saveScopeDraft, forgetScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  const panel = makePanel({ chatScopeId: "scope-forget", sessionId: "sess-forget" });
  saveScopeSnapshot("scope-forget", panel);
  saveScopeDraft("scope-forget", "draft text");

  const runtime = getAgentPanelRuntime();
  assert.ok(runtime._scopeSnapshots.has("scope-forget"));
  assert.ok(runtime._scopeDrafts.has("scope-forget"));

  forgetScopeSnapshot("scope-forget");

  assert.equal(runtime._scopeSnapshots.has("scope-forget"), false);
  assert.equal(runtime._scopeDrafts.has("scope-forget"), false);
});

test("forgetScopeSnapshot is safe for unknown scopeId", async () => {
  const { forgetScopeSnapshot } = await loadRuntime();
  // Must not throw.
  forgetScopeSnapshot("nonexistent");
  forgetScopeSnapshot(null);
  forgetScopeSnapshot("");
});

// ── saveScopeDraft / getScopeDraft ────────────────────────────────────────

test("saveScopeDraft and getScopeDraft round-trip", async () => {
  const { saveScopeDraft, getScopeDraft } = await loadRuntime();

  saveScopeDraft("scope-draft", "my prompt draft");
  assert.equal(getScopeDraft("scope-draft"), "my prompt draft");

  // Overwrite.
  saveScopeDraft("scope-draft", "updated draft");
  assert.equal(getScopeDraft("scope-draft"), "updated draft");
});

test("saveScopeDraft with null clears draft", async () => {
  const { saveScopeDraft, getScopeDraft } = await loadRuntime();

  saveScopeDraft("scope-draft", "some text");
  assert.equal(getScopeDraft("scope-draft"), "some text");

  saveScopeDraft("scope-draft", null);
  assert.equal(getScopeDraft("scope-draft"), null);
});

test("saveScopeDraft with empty string clears draft", async () => {
  const { saveScopeDraft, getScopeDraft } = await loadRuntime();

  saveScopeDraft("scope-draft", "some text");
  saveScopeDraft("scope-draft", "");
  assert.equal(getScopeDraft("scope-draft"), null);
});

test("saveScopeDraft with undefined clears draft", async () => {
  const { saveScopeDraft, getScopeDraft } = await loadRuntime();

  saveScopeDraft("scope-draft", "text");
  saveScopeDraft("scope-draft", undefined);
  assert.equal(getScopeDraft("scope-draft"), null);
});

test("getScopeDraft returns null for unknown scopeId", async () => {
  const { getScopeDraft } = await loadRuntime();
  assert.equal(getScopeDraft("never-saved"), null);
  assert.equal(getScopeDraft(null), null);
  assert.equal(getScopeDraft(""), null);
});

test("saveScopeDraft is no-op for null/empty scopeId", async () => {
  const { saveScopeDraft, getAgentPanelRuntime } = await loadRuntime();

  saveScopeDraft(null, "text");
  saveScopeDraft("", "text");
  saveScopeDraft(undefined, "text");

  const runtime = getAgentPanelRuntime();
  assert.equal(runtime._scopeDrafts.size, 0);
});

test("drafts are independent across scopes", async () => {
  const { saveScopeDraft, getScopeDraft } = await loadRuntime();

  saveScopeDraft("scope-A", "draft A");
  saveScopeDraft("scope-B", "draft B");

  assert.equal(getScopeDraft("scope-A"), "draft A");
  assert.equal(getScopeDraft("scope-B"), "draft B");

  // Clearing scope A does not affect scope B.
  saveScopeDraft("scope-A", null);
  assert.equal(getScopeDraft("scope-A"), null);
  assert.equal(getScopeDraft("scope-B"), "draft B");
});

// ── Queue guard context isolation ─────────────────────────────────────────

test("saveScopeQueueGuardContext and getScopeQueueGuardContext round-trip", async () => {
  const { saveScopeQueueGuardContext, getScopeQueueGuardContext } = await loadRuntime();

  const ctx = { sessionId: "sess-qg", turnId: "turn-qg", prompt: "test prompt" };
  saveScopeQueueGuardContext("scope-qg", ctx);

  const result = getScopeQueueGuardContext("scope-qg");
  assert.deepEqual(result, ctx);
});

test("saveScopeQueueGuardContext with null clears context", async () => {
  const { saveScopeQueueGuardContext, getScopeQueueGuardContext, getAgentPanelRuntime } = await loadRuntime();

  saveScopeQueueGuardContext("scope-qg", { sessionId: "sess" });
  assert.ok(getScopeQueueGuardContext("scope-qg") !== null);

  saveScopeQueueGuardContext("scope-qg", null);
  assert.equal(getScopeQueueGuardContext("scope-qg"), null);

  const runtime = getAgentPanelRuntime();
  assert.equal(runtime._scopeQueueGuardContexts.has("scope-qg"), false);
});

test("saveScopeQueueGuardContext with undefined clears context", async () => {
  const { saveScopeQueueGuardContext, getScopeQueueGuardContext } = await loadRuntime();

  saveScopeQueueGuardContext("scope-qg", { sessionId: "sess" });
  saveScopeQueueGuardContext("scope-qg", undefined);
  assert.equal(getScopeQueueGuardContext("scope-qg"), null);
});

test("getScopeQueueGuardContext returns null for unknown scopeId", async () => {
  const { getScopeQueueGuardContext } = await loadRuntime();
  assert.equal(getScopeQueueGuardContext("never-saved"), null);
  assert.equal(getScopeQueueGuardContext(null), null);
  assert.equal(getScopeQueueGuardContext(""), null);
});

test("saveScopeQueueGuardContext is no-op for null/empty scopeId", async () => {
  const { saveScopeQueueGuardContext, getAgentPanelRuntime } = await loadRuntime();

  saveScopeQueueGuardContext(null, { sessionId: "sess" });
  saveScopeQueueGuardContext("", { sessionId: "sess" });

  const runtime = getAgentPanelRuntime();
  assert.equal(runtime._scopeQueueGuardContexts.size, 0);
});

test("forgetScopeQueueGuardContext clears a specific scope", async () => {
  const { saveScopeQueueGuardContext, forgetScopeQueueGuardContext, getScopeQueueGuardContext } = await loadRuntime();

  saveScopeQueueGuardContext("scope-A", { sessionId: "sess-A" });
  saveScopeQueueGuardContext("scope-B", { sessionId: "sess-B" });

  forgetScopeQueueGuardContext("scope-A");

  assert.equal(getScopeQueueGuardContext("scope-A"), null);
  assert.deepEqual(getScopeQueueGuardContext("scope-B"), { sessionId: "sess-B" });
});

test("forgetScopeQueueGuardContext is safe for unknown scopeId", async () => {
  const { forgetScopeQueueGuardContext } = await loadRuntime();
  // Must not throw.
  forgetScopeQueueGuardContext("nonexistent");
  forgetScopeQueueGuardContext(null);
  forgetScopeQueueGuardContext("");
});

test("queue guard contexts are independent across scopes", async () => {
  const { saveScopeQueueGuardContext, getScopeQueueGuardContext, forgetScopeQueueGuardContext } = await loadRuntime();

  saveScopeQueueGuardContext("scope-A", { sessionId: "sess-A", prompt: "edit A" });
  saveScopeQueueGuardContext("scope-B", { sessionId: "sess-B", prompt: "edit B" });

  // Forgetting scope B should not affect scope A.
  forgetScopeQueueGuardContext("scope-B");
  assert.deepEqual(getScopeQueueGuardContext("scope-A"), { sessionId: "sess-A", prompt: "edit A" });
  assert.equal(getScopeQueueGuardContext("scope-B"), null);
});

// ── Snapshot value cloning ────────────────────────────────────────────────

test("saveScopeSnapshot deep-clones objects (no shared references)", async () => {
  const { saveScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  const panel = makePanel({
    chatScopeId: "scope-clone",
    candidateGraph: { nodes: [{ id: 1, widgets_values: ["hello"] }] },
    chatMessages: [{ role: "user", text: "hello" }],
  });

  saveScopeSnapshot("scope-clone", panel);
  const runtime = getAgentPanelRuntime();
  const snapshot = runtime._scopeSnapshots.get("scope-clone");

  // Mutate original — snapshot must be unaffected.
  panel.state.candidateGraph.nodes[0].widgets_values[0] = "MUTATED";
  panel.state.chatMessages[0].text = "MUTATED";

  assert.deepEqual(
    snapshot.candidateGraph,
    { nodes: [{ id: 1, widgets_values: ["hello"] }] },
  );
  assert.deepEqual(
    snapshot.chatMessages,
    [{ role: "user", text: "hello" }],
  );
});

test("restoreScopeSnapshot deep-clones restored values (no shared references)", async () => {
  const { saveScopeSnapshot, restoreScopeSnapshot } = await loadRuntime();

  const panel = makePanel({ chatScopeId: "scope-ref" });
  panel.state.candidateGraph = { nodes: [{ id: 1, widgets_values: ["original"] }] };

  saveScopeSnapshot("scope-ref", panel);

  // Clear then restore.
  panel.state.candidateGraph = null;
  restoreScopeSnapshot("scope-ref", panel);

  // The restored graph should be a deep clone — mutate it and re-restore.
  panel.state.candidateGraph.nodes[0].widgets_values[0] = "MUTATED";
  assert.equal(panel.state.candidateGraph.nodes[0].widgets_values[0], "MUTATED");

  // Restore again — should get the original back (proving deep clone).
  restoreScopeSnapshot("scope-ref", panel);
  assert.deepEqual(
    panel.state.candidateGraph,
    { nodes: [{ id: 1, widgets_values: ["original"] }] },
  );
});

// ── Snapshot metadata stamps ──────────────────────────────────────────────

test("snapshot metadata is stamped with scopeId and timestamp", async () => {
  const { saveScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  const panel = makePanel({ chatScopeId: "scope-meta" });
  saveScopeSnapshot("scope-meta", panel);

  const runtime = getAgentPanelRuntime();
  const snapshot = runtime._scopeSnapshots.get("scope-meta");

  assert.equal(snapshot._snapshotScopeId, "scope-meta");
  assert.ok(typeof snapshot._snapshotCapturedAt === "string");
  // ISO 8601 timestamp format.
  assert.ok(
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(snapshot._snapshotCapturedAt),
    `expected ISO timestamp, got "${snapshot._snapshotCapturedAt}"`,
  );
});

test("snapshot metadata does not survive onto panel.state after restore (metadata stripping)", async () => {
  const { saveScopeSnapshot, restoreScopeSnapshot } = await loadRuntime();

  const panel = makePanel({ chatScopeId: "scope-metastrip", sessionId: "sess-ms" });
  saveScopeSnapshot("scope-metastrip", panel);

  // Restore onto a fresh panel.
  const fresh = makePanel();
  restoreScopeSnapshot("scope-metastrip", fresh);

  assert.equal(
    Object.prototype.hasOwnProperty.call(fresh.state, "_snapshotScopeId"),
    false,
  );
  assert.equal(
    Object.prototype.hasOwnProperty.call(fresh.state, "_snapshotCapturedAt"),
    false,
  );
  // But real fields are restored.
  assert.equal(fresh.state.sessionId, "sess-ms");
});

// ── saveScopeSnapshot guard clauses ───────────────────────────────────────

test("saveScopeSnapshot is no-op for null/empty scopeId", async () => {
  const { saveScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  const panel = makePanel({ chatScopeId: "scope-guard" });
  saveScopeSnapshot(null, panel);
  saveScopeSnapshot("", panel);

  const runtime = getAgentPanelRuntime();
  assert.equal(runtime._scopeSnapshots.size, 0);
});

test("saveScopeSnapshot is no-op for null/missing panel or panel.state", async () => {
  const { saveScopeSnapshot, getAgentPanelRuntime } = await loadRuntime();

  saveScopeSnapshot("scope-guard", null);
  saveScopeSnapshot("scope-guard", undefined);
  saveScopeSnapshot("scope-guard", {});
  saveScopeSnapshot("scope-guard", { state: null });

  const runtime = getAgentPanelRuntime();
  assert.equal(runtime._scopeSnapshots.size, 0);
});

// ── getScopeQueueGuardContext type safety ─────────────────────────────────

test("getScopeQueueGuardContext rejects non-object stored values", async () => {
  const { getAgentPanelRuntime, getScopeQueueGuardContext } = await loadRuntime();

  // Bypass the setter to store a non-object value.
  const runtime = getAgentPanelRuntime();
  runtime._scopeQueueGuardContexts.set("scope-bad", "not-an-object");

  assert.equal(getScopeQueueGuardContext("scope-bad"), null);
});

test("getScopeQueueGuardContext rejects falsy stored values", async () => {
  const { getAgentPanelRuntime, getScopeQueueGuardContext } = await loadRuntime();

  const runtime = getAgentPanelRuntime();
  runtime._scopeQueueGuardContexts.set("scope-false", false);
  runtime._scopeQueueGuardContexts.set("scope-zero", 0);

  assert.equal(getScopeQueueGuardContext("scope-false"), null);
  assert.equal(getScopeQueueGuardContext("scope-zero"), null);
});
