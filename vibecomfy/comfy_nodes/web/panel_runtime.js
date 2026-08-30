import { jsonClone as cloneJsonData } from "./json_clone.js";

const AGENT_PANEL_SINGLETON_KEY = "__vibecomfyAgentPanelSingleton";

let fallbackRecord = null;

function createAgentPanelRuntimeState() {
  return {
    agentPanel: null,
    panelsCreated: 0,
    agentSidebarTabRegistered: false,
    agentTurnEventListener: null,
    agentTurnEventListenerRegistered: false,
    changedNodeFeedbackTimer: null,
    changedNodeFeedbackVisuals: [],
    queueGuardHook: null,
    queueGuardContext: null,
    queueGuardFallbackWarning: null,
    queueGuardFallbackWarned: false,
    queueGuardBlockNotice: null,
    queueGuardBlockedTurnKeys: new Set(),
    _previewForegroundInstallReport: null,
    _adapterCapabilities: null,
    _progressPulseInjected: false,
    _scheduledAgentPanelRender: null,
    _scheduledAgentPanelRenders: [],
    _scheduledAgentPanelRenderQueued: false,
    _cancelScheduledAgentPanelRender: null,
    // Monotonic owner token for one queued render cycle. A callback may flush
    // only the cycle that created it; replacement panels and new workflow
    // activations revoke older cycles instead of letting their callbacks
    // satisfy the new owner.
    _agentPanelRenderScheduleGeneration: 0,
    _overlayDrawModelCache: null,
    // ── T7: Per-scope runtime snapshot maps ───────────────────────────────
    // Keyed by scopeId.  Each entry is a plain object capturing the
    // panel.state snapshot for that scope (all lifecycle + non-lifecycle
    // fields EXCEPT undoStack, DOM references, and ephemeral render state).
    _scopeSnapshots: new Map(),
    // Per-scope draft prompt text (captured from DOM on scope switch).
    _scopeDrafts: new Map(),
    // ── T9: Per-scope queue guard context isolation ────────────────────────
    // Each scope's queue guard context (session/turn/prompt metadata used by
    // the native queuePrompt hook) is saved here on scope switch and restored
    // when the user returns to that scope.  Cleared per-scope on new
    // conversation.
    _scopeQueueGuardContexts: new Map(),
  };
}

function backfillRuntimeShape(runtime) {
  if (!runtime || typeof runtime !== "object") {
    return createAgentPanelRuntimeState();
  }
  if (!(runtime.queueGuardBlockedTurnKeys instanceof Set)) {
    runtime.queueGuardBlockedTurnKeys = new Set(
      Array.isArray(runtime.queueGuardBlockedTurnKeys) ? runtime.queueGuardBlockedTurnKeys : [],
    );
  }
  if (!Array.isArray(runtime.changedNodeFeedbackVisuals)) {
    runtime.changedNodeFeedbackVisuals = [];
  }
  if (!Object.prototype.hasOwnProperty.call(runtime, "panelsCreated") || !Number.isFinite(runtime.panelsCreated)) {
    runtime.panelsCreated = 0;
  }
  // ── T7: Backfill per-scope snapshot maps ────────────────────────────────
  if (!(runtime._scopeSnapshots instanceof Map)) {
    runtime._scopeSnapshots = new Map();
  }
  if (!(runtime._scopeDrafts instanceof Map)) {
    runtime._scopeDrafts = new Map();
  }
  // ── T9: Backfill per-scope queue guard context map ─────────────────────
  if (!(runtime._scopeQueueGuardContexts instanceof Map)) {
    runtime._scopeQueueGuardContexts = new Map();
  }
  const defaults = createAgentPanelRuntimeState();
  for (const [key, value] of Object.entries(defaults)) {
    if (!Object.prototype.hasOwnProperty.call(runtime, key) || runtime[key] === undefined) {
      if (key === "queueGuardBlockedTurnKeys") {
        runtime[key] = new Set();
      } else if (key === "_scopeSnapshots" || key === "_scopeDrafts" || key === "_scopeQueueGuardContexts") {
        runtime[key] = new Map();
      } else {
        runtime[key] = Array.isArray(value) ? [] : value;
      }
    }
  }
  return runtime;
}

export function agentPanelSingletonHost() {
  return typeof window !== "undefined" ? window : null;
}

export function agentPanelSingletonRecord(create = false) {
  const host = agentPanelSingletonHost();
  if (!host) {
    if (!create) {
      return fallbackRecord;
    }
    if (!fallbackRecord) {
      fallbackRecord = { runtime: createAgentPanelRuntimeState() };
    } else {
      fallbackRecord.runtime = backfillRuntimeShape(fallbackRecord.runtime);
    }
    return fallbackRecord;
  }
  const current = host[AGENT_PANEL_SINGLETON_KEY];
  if (current && typeof current === "object") {
    if (!current.runtime || typeof current.runtime !== "object") {
      current.runtime = createAgentPanelRuntimeState();
      if (Object.prototype.hasOwnProperty.call(current, "panel")) {
        current.runtime.agentPanel = current.panel || null;
      }
      if (Number.isFinite(current.panelsCreated)) {
        current.runtime.panelsCreated = current.panelsCreated;
      }
    }
    current.runtime = backfillRuntimeShape(current.runtime);
    return current;
  }
  if (!create) {
    return null;
  }
  const record = { runtime: createAgentPanelRuntimeState() };
  host[AGENT_PANEL_SINGLETON_KEY] = record;
  return record;
}

export function getAgentPanelRuntime() {
  return agentPanelSingletonRecord(true).runtime;
}

export function currentAgentPanel() {
  return getAgentPanelRuntime().agentPanel || null;
}

export function setCurrentAgentPanel(panel) {
  const runtime = getAgentPanelRuntime();
  const previous = runtime.agentPanel || null;
  if (previous !== (panel || null)) {
    if (typeof runtime._cancelScheduledAgentPanelRender === "function") {
      runtime._cancelScheduledAgentPanelRender();
    }
    runtime._cancelScheduledAgentPanelRender = null;
    runtime._agentPanelRenderScheduleGeneration += 1;
    runtime._scheduledAgentPanelRender = null;
    runtime._scheduledAgentPanelRenders = [];
    runtime._scheduledAgentPanelRenderQueued = false;
    if (previous && typeof previous === "object") {
      previous.__renderFlushPending = false;
      previous.__renderScheduleRevoked = true;
    }
  }
  runtime.agentPanel = panel || null;
  if (runtime.agentPanel && typeof runtime.agentPanel === "object") {
    runtime.agentPanel.__agentPanelRuntime = runtime;
    runtime.agentPanel.__renderScheduleRevoked = false;
  }
  return runtime.agentPanel;
}

export function panelsCreatedCount() {
  const sharedCount = getAgentPanelRuntime().panelsCreated;
  return Number.isFinite(sharedCount) ? sharedCount : 0;
}

export function nextAgentPanelId() {
  const runtime = getAgentPanelRuntime();
  const nextCount = Number.isFinite(runtime.panelsCreated) ? runtime.panelsCreated + 1 : 1;
  runtime.panelsCreated = nextCount;
  return `${Date.now()}-${nextCount}`;
}

// ── T7: Per-scope runtime snapshot maps ────────────────────────────────────
//
// These functions manage the save/restore lifecycle of panel.state across
// scope switches.  Each scope gets its own snapshot of the complete panel
// state (all lifecycle + non-lifecycle fields) EXCEPT:
//   - undoStack      (SD3: undo history is canvas-affine, not scope-affine)
//   - DOM references  (buttons, sections, root — reconstructed per panel mount)
//   - Ephemeral render state (pendingDirtySections, __renderErrors, etc.)
//
// Draft prompt text is stored separately in _scopeDrafts so it can be
// captured from the DOM at switch time and restored into the DOM afterwards.

// Fields that are NEVER included in scope snapshots.
const SCOPE_SNAPSHOT_EXCLUDE = new Set([
  "undoStack",
  // Monotonic activation token for the visible singleton panel. It belongs
  // to the browser runtime, not to any workflow snapshot: restoring an older
  // scope must never roll this token back and make a departed async response
  // current again.
  "scopeActivationEpoch",
  "buttons",
  "sections",
  "fields",
  "root",
  "composerButtons",
  "pendingDirtySections",
  "__renderErrors",
  "__renderFailureCounts",
  "mountMode",
  "mountContainer",
  // Live choose-engine overlay hooks are UI callbacks, not durable scope
  // state.  Passing one to jsonClone would stringify it to undefined and
  // then make JSON.parse(undefined) throw during a scope switch.
  "chooseEngineRefresh",
  "chooseEngineNavigateTo",
]);

/**
 * Snapshot cloning uses the same JSON-family contract as the shared clone
 * authority: JSON values are copied without aliases, unsupported graphs (for
 * example cycles or BigInt) reject, and own __proto__ data keys survive.
 */
function _cloneForSnapshot(value) {
  return cloneJsonData(value);
}

function _setOwnDataProperty(target, key, value) {
  Object.defineProperty(target, key, {
    value,
    enumerable: true,
    writable: true,
    configurable: true,
  });
}

/**
 * Save the current panel.state into the runtime snapshot map for the given
 * scopeId.  The snapshot includes all own enumerable properties of panel.state
 * EXCEPT those listed in SCOPE_SNAPSHOT_EXCLUDE.
 *
 * In-flight async state (AbortController, Promises) is nulled out — it cannot
 * be meaningfully restored across scope switches.
 *
 * @param {string} scopeId  The scope id to save under
 * @param {object} panel    The panel object (must have .state)
 */
export function saveScopeSnapshot(scopeId, panel) {
  if (!scopeId || !panel || !panel.state) {
    return;
  }
  const runtime = getAgentPanelRuntime();
  const snapshot = {};
  for (const [key, val] of Object.entries(panel.state)) {
    if (SCOPE_SNAPSHOT_EXCLUDE.has(key)) {
      continue;
    }
    // Keep future live callback fields out of the JSON snapshot boundary too.
    // Nested functions retain the existing JSON-clone semantics, while a
    // top-level function must never reach JSON.parse(undefined).
    if (typeof val === "function") {
      continue;
    }
    // Null out in-flight async state — it belongs to the scope being left.
    if (key === "submitAbortController" || key === "inFlightSubmit"
        || key === "inFlightApply" || key === "inFlightRebaseline") {
      _setOwnDataProperty(snapshot, key, null);
      continue;
    }
    _setOwnDataProperty(snapshot, key, _cloneForSnapshot(val));
  }
  // Stamp with metadata for diagnostics.
  snapshot._snapshotScopeId = scopeId;
  snapshot._snapshotCapturedAt = new Date().toISOString();
  runtime._scopeSnapshots.set(scopeId, snapshot);
}

/**
 * Restore panel.state from a previously saved scope snapshot.
 * Returns true if a snapshot was found and restored, false otherwise.
 *
 * Fields NOT present in the snapshot are left unchanged (merge semantics).
 * The undoStack field on panel.state is NEVER touched (SD3).
 *
 * @param {string} scopeId  The scope id to restore from
 * @param {object} panel    The panel object (must have .state)
 * @returns {boolean}       true if a snapshot was restored
 */
export function restoreScopeSnapshot(scopeId, panel) {
  if (!scopeId || !panel || !panel.state) {
    return false;
  }
  const runtime = getAgentPanelRuntime();
  const snapshot = runtime._scopeSnapshots.get(scopeId);
  if (!snapshot || typeof snapshot !== "object") {
    return false;
  }
  // Restore all snapshot keys onto panel.state (merge — keys not in snapshot
  // are left as-is, so fresh non-lifecycle fields added after snapshot capture
  // survive the restore).
  for (const [key, val] of Object.entries(snapshot)) {
    if (key === "undoStack" || key === "_snapshotScopeId" || key === "_snapshotCapturedAt") {
      continue;
    }
    _setOwnDataProperty(panel.state, key, _cloneForSnapshot(val));
  }
  return true;
}

/**
 * Forget a scope's snapshot.  Called when a scope is explicitly discarded
 * (new conversation, workflow closed, etc.).
 *
 * @param {string} scopeId  The scope id to forget
 */
export function forgetScopeSnapshot(scopeId) {
  if (!scopeId) {
    return;
  }
  const runtime = getAgentPanelRuntime();
  runtime._scopeSnapshots.delete(scopeId);
  runtime._scopeDrafts.delete(scopeId);
}

/**
 * Save the current prompt draft text for a scope.  Callers should read the
 * prompt element value from the DOM and pass it here before switching scopes.
 *
 * @param {string} scopeId  The scope id
 * @param {string|null} draftText  The prompt text (null to clear)
 */
export function saveScopeDraft(scopeId, draftText) {
  if (!scopeId) {
    return;
  }
  const runtime = getAgentPanelRuntime();
  if (draftText == null || draftText === "") {
    runtime._scopeDrafts.delete(scopeId);
  } else {
    runtime._scopeDrafts.set(scopeId, String(draftText));
  }
}

/**
 * Retrieve the saved prompt draft text for a scope.
 *
 * @param {string} scopeId  The scope id
 * @returns {string|null}   The saved draft text, or null if none
 */
export function getScopeDraft(scopeId) {
  if (!scopeId) {
    return null;
  }
  const runtime = getAgentPanelRuntime();
  const draft = runtime._scopeDrafts.get(scopeId);
  return typeof draft === "string" ? draft : null;
}

// ── T9: Per-scope queue guard context isolation ────────────────────────────
// The queue guard context (session/turn/prompt metadata) is a singleton on
// the runtime.  To prevent a scope switch or new-conversation in scope A
// from silently dropping scope B's guard state, we save/restore it per scope.

/**
 * Save the current queueGuardContext for the given scope.
 * Called before a scope switch or when clearing guard for the current scope.
 *
 * @param {string} scopeId  The scope id
 * @param {object|null} context  The queue guard context (null to clear)
 */
export function saveScopeQueueGuardContext(scopeId, context) {
  if (!scopeId) {
    return;
  }
  const runtime = getAgentPanelRuntime();
  if (context === null || context === undefined) {
    runtime._scopeQueueGuardContexts.delete(scopeId);
  } else {
    runtime._scopeQueueGuardContexts.set(scopeId, context);
  }
}

/**
 * Look up the saved queue guard context for a scope.
 *
 * @param {string} scopeId  The scope id
 * @returns {object|null}  The saved context, or null
 */
export function getScopeQueueGuardContext(scopeId) {
  if (!scopeId) {
    return null;
  }
  const runtime = getAgentPanelRuntime();
  const ctx = runtime._scopeQueueGuardContexts.get(scopeId);
  return ctx && typeof ctx === "object" ? ctx : null;
}

/**
 * Forget the queue guard context for a scope (e.g. on new conversation).
 *
 * @param {string} scopeId  The scope id
 */
export function forgetScopeQueueGuardContext(scopeId) {
  if (!scopeId) {
    return;
  }
  const runtime = getAgentPanelRuntime();
  runtime._scopeQueueGuardContexts.delete(scopeId);
}
